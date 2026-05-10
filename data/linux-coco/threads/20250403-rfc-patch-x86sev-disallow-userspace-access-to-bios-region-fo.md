---
title: '[RFC PATCH] x86/sev: Disallow userspace access to BIOS region for SEV-SNP guests'
date: 2025-04-03
last_reply: 2025-04-10
message_count: 16
participants: ['Naveen N Rao (AMD)', 'Dan Williams', 'Tom Lendacky', 'Dave Hansen', 'Nikolay Borisov', 'Kees Cook']
---

## [1] Naveen N Rao (AMD) — 2025-04-03

Commit 9704c07bf9f7 ("x86/kernel: Validate ROM memory before accessing
when SEV-SNP is active") added code to validate the ROM region from
0xc0000 to 0xfffff in a SEV-SNP guest since that region can be accessed
during kernel boot. That address range is not part of the system RAM, so
it needed to be validated separately.

Commit 0f4a1e80989a ("x86/sev: Skip ROM range scans and validation for
SEV-SNP guests") reverted those changes and instead chose to prevent the
guest from accessing the ROM region since SEV-SNP guests did not rely on
data from that region. However, while the kernel itself no longer
accessed the ROM region, there are userspace programs that probe this
region through /dev/mem and they started crashing due to this change. In
particular, fwupd (up until versions released last year that no longer
link against libsmbios) and smbios utilities such as smbios-sys-info
crash with a cryptic message in dmesg:
  Wrong/unhandled opcode bytes: 0x8b, exit_code: 0x404, rIP: 0x7fe5404d3840
  SEV: Unsupported exit-code 0x404 in #VC exception (IP: 0x7fe5404d3840)

Deny access to the BIOS region (rather than just the video ROM range)
via /dev/mem to address this. Restrict changes to CONFIG_STRICT_DEVMEM=y
which is enabled by default on x86. Add a new x86_platform_ops callback
so Intel can customize the address range to block.

Fixes: 0f4a1e80989a ("x86/sev: Skip ROM range scans and validation for SEV-SNP guests")
Signed-off-by: Naveen N Rao (AMD) <naveen@kernel.org>
---
 arch/x86/coco/sev/core.c        | 13 +++++++++++++
 arch/x86/include/asm/sev.h      |  2 ++
 arch/x86/include/asm/x86_init.h |  2 ++
 arch/x86/kernel/x86_init.c      |  2 ++
 arch/x86/mm/init.c              |  3 +++
 arch/x86/mm/mem_encrypt_amd.c   |  1 +
 6 files changed, 23 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index b0c1a7a57497..4e10701536d4 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -43,6 +43,7 @@
 #include <asm/apic.h>
 #include <asm/cpuid.h>
 #include <asm/cmdline.h>
+#include <asm/e820/types.h>
 
 #define DR7_RESET_VALUE        0x400
 
@@ -761,6 +762,18 @@ static u64 __init get_jump_table_addr(void)
 	return ret;
 }
 
+bool sev_snp_pfn_access_allowed(unsigned long pfn)
+{
+	/*
+	 * Reject access to BIOS address range (0xa0000 to 0x100000) for SEV-SNP guests
+	 * as that address range is not validated, so access can cause #VC exception
+	 */
+	if (pfn << PAGE_SHIFT >= BIOS_BEGIN && pfn << PAGE_SHIFT < BIOS_END)
+		return 0;
+
+	return 1;
+}
+
 static void __head
 early_set_pages_state(unsigned long vaddr, unsigned long paddr,
 		      unsigned long npages, enum psc_op op)
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ba7999f66abe..721498c0a055 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -454,6 +454,7 @@ static inline int pvalidate(unsigned long vaddr, bool rmp_psize, bool validate)
 struct snp_guest_request_ioctl;
 
 void setup_ghcb(void);
+bool sev_snp_pfn_access_allowed(unsigned long pfn);
 void early_snp_set_memory_private(unsigned long vaddr, unsigned long paddr,
 				  unsigned long npages);
 void early_snp_set_memory_shared(unsigned long vaddr, unsigned long paddr,
@@ -496,6 +497,7 @@ static inline void sev_enable(struct boot_params *bp) { }
 static inline int pvalidate(unsigned long vaddr, bool rmp_psize, bool validate) { return 0; }
 static inline int rmpadjust(unsigned long vaddr, bool rmp_psize, unsigned long attrs) { return 0; }
 static inline void setup_ghcb(void) { }
+static inline bool sev_snp_pfn_access_allowed(unsigned long pfn) { return true; }
 static inline void __init
 early_snp_set_memory_private(unsigned long vaddr, unsigned long paddr, unsigned long npages) { }
 static inline void __init
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 36698cc9fb44..d559587dee48 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -307,6 +307,7 @@ struct x86_hyper_runtime {
  * @realmode_reserve:		reserve memory for realmode trampoline
  * @realmode_init:		initialize realmode trampoline
  * @hyper:			x86 hypervisor specific runtime callbacks
+ * @pfn_access_allowed:		filter accesses to pages
  */
 struct x86_platform_ops {
 	unsigned long (*calibrate_cpu)(void);
@@ -324,6 +325,7 @@ struct x86_platform_ops {
 	void (*set_legacy_features)(void);
 	void (*realmode_reserve)(void);
 	void (*realmode_init)(void);
+	bool (*pfn_access_allowed)(unsigned long pfn);
 	struct x86_hyper_runtime hyper;
 	struct x86_guest guest;
 };
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index 0a2bbd674a6d..3679a92a3881 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -142,6 +142,7 @@ static bool enc_cache_flush_required_noop(void) { return false; }
 static void enc_kexec_begin_noop(void) {}
 static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
+static bool pfn_access_allowed_noop(unsigned long pfn) { return true; }
 
 struct x86_platform_ops x86_platform __ro_after_init = {
 	.calibrate_cpu			= native_calibrate_cpu_early,
@@ -156,6 +157,7 @@ struct x86_platform_ops x86_platform __ro_after_init = {
 	.restore_sched_clock_state	= tsc_restore_sched_clock_state,
 	.realmode_reserve		= reserve_real_mode,
 	.realmode_init			= init_real_mode,
+	.pfn_access_allowed		= pfn_access_allowed_noop,
 	.hyper.pin_vcpu			= x86_op_int_noop,
 	.hyper.is_private_mmio		= is_private_mmio_noop,
 
diff --git a/arch/x86/mm/init.c b/arch/x86/mm/init.c
index bfa444a7dbb0..9a82ebc02011 100644
--- a/arch/x86/mm/init.c
+++ b/arch/x86/mm/init.c
@@ -867,6 +867,9 @@ void __init poking_init(void)
  */
 int devmem_is_allowed(unsigned long pagenr)
 {
+	if (!x86_platform.pfn_access_allowed(pagenr))
+		return 0;
+
 	if (region_intersects(PFN_PHYS(pagenr), PAGE_SIZE,
 				IORESOURCE_SYSTEM_RAM, IORES_DESC_NONE)
 			!= REGION_DISJOINT) {
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 7490ff6d83b1..526f2ba40788 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -532,6 +532,7 @@ void __init sme_early_init(void)
 		 * parsing has happened.
 		 */
 		x86_init.resources.dmi_setup = snp_dmi_setup;
+		x86_platform.pfn_access_allowed = sev_snp_pfn_access_allowed;
 	}
 
 	/*

base-commit: 1c13554a1d43317fe9009837ef6524f808e107b7

---

## [2] Dan Williams — 2025-04-03
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

Naveen N Rao (AMD) wrote:
> Commit 9704c07bf9f7 ("x86/kernel: Validate ROM memory before accessing
> when SEV-SNP is active") added code to validate the ROM region from

Is there any driving need to allow devmem at all for TVM access at this
point?

I would be in favor of making this clearly tied to devmem, call it
".devmem_is_allowed" for symmetry with the mm/init.c helper, and make
the default implementation be:

static bool platform_devmem_is_allowed(unsigned long pfn)
{
	return !cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT));
}

...if a TVM technology wants more leniency, it can override.

---

## [3] Naveen N Rao — 2025-04-07
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

On Thu, Apr 03, 2025 at 12:06:29PM -0700, Dan Williams wrote:
> Naveen N Rao (AMD) wrote:
> > Commit 9704c07bf9f7 ("x86/kernel: Validate ROM memory before accessing
<snip>
> 
> Is there any driving need to allow devmem at all for TVM access at this

I'm not fully aware of the history here, but I suppose a TVM should 
appear as any other VM for userspace. For that reason, I didn't want to 
block access to /dev/mem any more than was necessary. Admittedly, I have 
limited insight into which utilities may be using /dev/mem today.

Tom/Boris, do you see a problem blocking access to /dev/mem for SEV 
guests?


- Naveen

---

## [4] Tom Lendacky — 2025-04-08
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region for
 SEV-SNP guests*

On 4/7/25 08:13, Naveen N Rao wrote:
> On Thu, Apr 03, 2025 at 12:06:29PM -0700, Dan Williams wrote:
>> Naveen N Rao (AMD) wrote:

Not sure why we would suddenly not allow that.

Thanks,
Tom

> 
>

---

## [5] Dave Hansen — 2025-04-08
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region for
 SEV-SNP guests*

On 4/8/25 06:43, Tom Lendacky wrote:
>> Tom/Boris, do you see a problem blocking access to /dev/mem for SEV 
>> guests?

Both TDX and SEV-SNP have issues with allowing access to /dev/mem.
Disallowing access to the individually troublesome regions can fix
_part_ of the problem. But suddenly blocking access is guaranteed to fix
*ALL* the problems forever.

Or, maybe we just start returning 0's for all reads and throw away all
writes. That is probably less likely to break userspace that doesn't
know what it's doing in the first place.

---

## [6] Dan Williams — 2025-04-08
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

Dave Hansen wrote:
> On 4/8/25 06:43, Tom Lendacky wrote:
> >> Tom/Boris, do you see a problem blocking access to /dev/mem for SEV 

...or at least solicits practical use cases for why the kernel needs to
poke holes in the policy.

> Or, maybe we just start returning 0's for all reads and throw away all
> writes. That is probably less likely to break userspace that doesn't

Yes, and a bulk of the regression risk has already been pipe-cleaned by
KERNEL_LOCKDOWN that shuts down /dev/mem and PCI resource file mmap in
many scenarios.

Here is an updated patch that includes some consideration for mapping
zeros for known legacy compatibility use cases.

-- 8< --
From: Dan Williams <dan.j.williams@intel.com>
Subject: [PATCH] x86: Restrict /dev/mem access for potentially unaccepted
 memory by default

Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
address space) via /dev/mem results in an SEPT violation.

The cause is ioremap() (via xlate_dev_mem_ptr()) establishes an
unencrypted mapping where the kernel had established an encrypted
mapping previously.

An initial attempt to fix this revealed that TDX and SEV-SNP have
different expectations about which and when address ranges can be mapped
via /dev/mem.

Rather than develop a precise set of allowed /dev/mem capable TVM
address ranges, lean on the observation that KERNEL_LOCKDOWN is already
blocking /dev/mem access in many cases to do the same by default for x86
TVMs. This can still be later relaxed as specific needs arise, but in
the meantime close off this source of mismatched IORES_MAP_ENCRYPTED
expectations.

Note that this is careful to map zeroes rather than reject mappings of
the BIOS data space.

Cc: <x86@kernel.org>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Kirill Shutemov <kirill.shutemov@linux.intel.com>
Reported-by: Nikolay Borisov <nik.borisov@suse.com>
Closes: http://lore.kernel.org/20250318113604.297726-1-nik.borisov@suse.com [1]
Fixes: 9aa6ea69852c ("x86/tdx: Make pages shared in ioremap()")
Cc: <stable@vger.kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/Kconfig                |  2 ++
 arch/x86/include/asm/x86_init.h |  2 ++
 arch/x86/kernel/x86_init.c      |  6 ++++++
 arch/x86/mm/init.c              | 14 +++++++++++---
 4 files changed, 21 insertions(+), 3 deletions(-)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 15f346f02af0..6d4f94a79314 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -888,6 +888,7 @@ config INTEL_TDX_GUEST
 	depends on X86_64 && CPU_SUP_INTEL
 	depends on X86_X2APIC
 	depends on EFI_STUB
+	depends on STRICT_DEVMEM
 	select ARCH_HAS_CC_PLATFORM
 	select X86_MEM_ENCRYPT
 	select X86_MCE
@@ -1507,6 +1508,7 @@ config AMD_MEM_ENCRYPT
 	bool "AMD Secure Memory Encryption (SME) support"
 	depends on X86_64 && CPU_SUP_AMD
 	depends on EFI_STUB
+	depends on STRICT_DEVMEM
 	select DMA_COHERENT_POOL
 	select ARCH_USE_MEMREMAP_PROT
 	select INSTRUCTION_DECODER
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 213cf5379a5a..0ae436b34b88 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -305,6 +305,7 @@ struct x86_hyper_runtime {
  * 				semantics.
  * @realmode_reserve:		reserve memory for realmode trampoline
  * @realmode_init:		initialize realmode trampoline
+ * @devmem_is_allowed		restrict /dev/mem and PCI sysfs resource access
  * @hyper:			x86 hypervisor specific runtime callbacks
  */
 struct x86_platform_ops {
@@ -323,6 +324,7 @@ struct x86_platform_ops {
 	void (*set_legacy_features)(void);
 	void (*realmode_reserve)(void);
 	void (*realmode_init)(void);
+	bool (*devmem_is_allowed)(unsigned long pfn);
 	struct x86_hyper_runtime hyper;
 	struct x86_guest guest;
 };
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index 0a2bbd674a6d..346301375bd4 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -143,6 +143,11 @@ static void enc_kexec_begin_noop(void) {}
 static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
 
+static bool platform_devmem_is_allowed(unsigned long pfn)
+{
+	return !cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT);
+}
+
 struct x86_platform_ops x86_platform __ro_after_init = {
 	.calibrate_cpu			= native_calibrate_cpu_early,
 	.calibrate_tsc			= native_calibrate_tsc,
@@ -156,6 +161,7 @@ struct x86_platform_ops x86_platform __ro_after_init = {
 	.restore_sched_clock_state	= tsc_restore_sched_clock_state,
 	.realmode_reserve		= reserve_real_mode,
 	.realmode_init			= init_real_mode,
+	.devmem_is_allowed		= platform_devmem_is_allowed,
 	.hyper.pin_vcpu			= x86_op_int_noop,
 	.hyper.is_private_mmio		= is_private_mmio_noop,
 
diff --git a/arch/x86/mm/init.c b/arch/x86/mm/init.c
index bfa444a7dbb0..c8679ae1bc8b 100644
--- a/arch/x86/mm/init.c
+++ b/arch/x86/mm/init.c
@@ -867,6 +867,8 @@ void __init poking_init(void)
  */
 int devmem_is_allowed(unsigned long pagenr)
 {
+	bool platform_allowed = x86_platform.devmem_is_allowed(pagenr);
+
 	if (region_intersects(PFN_PHYS(pagenr), PAGE_SIZE,
 				IORESOURCE_SYSTEM_RAM, IORES_DESC_NONE)
 			!= REGION_DISJOINT) {
@@ -885,14 +887,20 @@ int devmem_is_allowed(unsigned long pagenr)
 	 * restricted resource under CONFIG_STRICT_DEVMEM.
 	 */
 	if (iomem_is_exclusive(pagenr << PAGE_SHIFT)) {
-		/* Low 1MB bypasses iomem restrictions. */
-		if (pagenr < 256)
+		/*
+		 * Low 1MB bypasses iomem restrictions unless the
+		 * platform says "no", in which case map zeroes
+		 */
+		if (pagenr < 256) {
+			if (!platform_allowed)
+				return 2;
 			return 1;
+		}
 
 		return 0;
 	}
 
-	return 1;
+	return platform_allowed;
 }
 
 void free_init_pages(const char *what, unsigned long begin, unsigned long end)

---

## [7] Nikolay Borisov — 2025-04-09
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region for
 SEV-SNP guests*

On 9.04.25 г. 2:55 ч., Dan Williams wrote:
> Dave Hansen wrote:
>> On 4/8/25 06:43, Tom Lendacky wrote:

That'll work but I hate the way this interface works. The sole user of 
this 0/1/2 convention is page_is_allowed() and the check for 1  inside 
write_mem(). The proper patch will need to document this...

Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>

>   			return 1;
> +		}

---

## [8] Dan Williams — 2025-04-09
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

Nikolay Borisov wrote:
> 
> 

That's good feedback. I will introduce some defines for those magic
values: DEVMEM_{ALLOW,DENY,ZEROES}.

> Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>

Thanks for taking a look.

---

## [9] Kees Cook — 2025-04-09
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

On Tue, Apr 08, 2025 at 04:55:08PM -0700, Dan Williams wrote:
> Dave Hansen wrote:
> > On 4/8/25 06:43, Tom Lendacky wrote:

I am reminded of this discussion:
https://lore.kernel.org/all/CAPcyv4iVt=peUAk1qx_EfKn7aGJM=XwRUpJftBhkUgQEti2bJA@mail.gmail.com/

As in, mmap will bypass this restriction, so if you really want the low
1MiB to be unreadable, a solution for mmap is still needed...

-Kees

---

## [10] Dan Williams — 2025-04-09
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

Kees Cook wrote:
> On Tue, Apr 08, 2025 at 04:55:08PM -0700, Dan Williams wrote:
> > Dave Hansen wrote:
[..]
> > diff --git a/arch/x86/mm/init.c b/arch/x86/mm/init.c
> > index bfa444a7dbb0..c8679ae1bc8b 100644

Glad you remembered that!

This needs a self-test to verify the assumptions here. I can circle back
next week or so take a look at turning this into a bigger series. If
someone has cycles to take this on before that I would not say no to
some help.

---

## [11] Nikolay Borisov — 2025-04-10
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region for
 SEV-SNP guests*

On 9.04.25 г. 21:39 ч., Dan Williams wrote:
> Kees Cook wrote:
>> On Tue, Apr 08, 2025 at 04:55:08PM -0700, Dan Williams wrote:


Can't we simply treat return value of 2 for range_is_allowed the same 
way as if 0 was returned in mmap_mem and simply fail the call with -EPERM?

---

## [12] Kees Cook — 2025-04-10
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

On Thu, Apr 10, 2025 at 03:03:55PM +0300, Nikolay Borisov wrote:
> 
> 

The historical concern was that EPERM would break old tools. I don't
have any current evidence either way, though.

---

## [13] Nikolay Borisov — 2025-04-10
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region for
 SEV-SNP guests*

On 10.04.25 г. 19:32 ч., Kees Cook wrote:
> On Thu, Apr 10, 2025 at 03:03:55PM +0300, Nikolay Borisov wrote:
>>

Right, but we are only about to return 2 in a TVM context, so chances of 
running old tools are slim to none. Also it's perfectly valid to have 
mmap fail for a number of reasons, so old tools should be equipped with 
handling it returning -EPERM, no ?

>

---

## [14] Dan Williams — 2025-04-10
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

Nikolay Borisov wrote:
[..]
> >> Can't we simply treat return value of 2 for range_is_allowed the same way as
> >> if 0 was returned in mmap_mem and simply fail the call with -EPERM?

In practice that is yet another return code since the caller does not
know why the "2" is being returned and it is not clear how safe it is to
now start denying mmap in the !TVM case. So, perhaps something like this:

enum devmem_policy {
	DEVMEM_DENY,
	DEVMEM_ALLOW,
	DEVMEM_ZERO_RW, /* XXX: fix mmap_mem to install zeroes? */
	DEVMEM_ZERO_RW_DENY_MMAP,
};

The hope is that legacy tools are either fine with open() failures due
to the prevalance of lockdown, fine with read/write of zeroes to BIOS
data due to the prevalance of CONFIG_STRICT_DEVMEM, or otherwise would
not notice / break when mmap() starts failing for BIOS data in the TVM
case. The !TVM case continues with the current gap for mmap.

Or, rip the bandaid and do this to see who screams:

enum devmem_policy {
	DEVMEM_DENY,
	DEVMEM_ALLOW,
	DEVMEM_ZERO_RW_DENY_MMAP,
};

---

## [15] Nikolay Borisov — 2025-04-10
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region for
 SEV-SNP guests*

On 10.04.25 г. 22:20 ч., Dan Williams wrote:
> Nikolay Borisov wrote:
> [..]

What I meant by "returning 2" is returning 2 from the call to 
range_is_allowed in mmap_mem and handling this value inside mmap_mem, 
not returning 2 to user space :) In essence something along the lines of:



diff --git a/drivers/char/mem.c b/drivers/char/mem.c
index 169eed162a7f..8273066b6637 100644
--- a/drivers/char/mem.c
+++ b/drivers/char/mem.c
@@ -359,7 +359,8 @@ static int mmap_mem(struct file *file, struct 
vm_area_struct *vma)
         if (!private_mapping_ok(vma))
                 return -ENOSYS;

-       if (!range_is_allowed(vma->vm_pgoff, size))
+       int ret = range_is_allowed(vma->vm_pgoff, size);
+       if (!ret || ret == 2)
                 return -EPERM;

         if (!phys_mem_access_prot_allowed(file, vma->vm_pgoff, size,


> enum devmem_policy {
> 	DEVMEM_DENY,

---

## [16] Dan Williams — 2025-04-10
*Subject: Re: [RFC PATCH] x86/sev: Disallow userspace access to BIOS region
 for SEV-SNP guests*

Nikolay Borisov wrote:
> 
> 

Oh, no, I was not confused about that, just the conflict that "2" means
that mmap is ok currently.

> In essence something along the lines of:
> 

Right, the issue is that this potentially breaks userspace that had
glommed onto the idea that it can always mmap BIOS data even if the R/W
path returns zeros.

It is arguably a bug that we allow that bypass, but it has been shipping
for a while. I think it is reasonable for TVMs to try to shut this down
completely, but the question is whether doing this instead:

   if (!ret || ret == 3)

...allows the TVM case to not disturb legacy expectations?

However, my vote is to special case 2 as EPERM as you have it here.
Because, if that works, it solves both the TVM need and silently closes
this weird hole hopefully before userspace actually starts depending on
it. We can always switch to 3 or do the work to map zeros if that proves
to be a regression.

---
