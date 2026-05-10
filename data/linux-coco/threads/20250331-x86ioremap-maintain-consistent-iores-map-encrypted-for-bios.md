---
title: 'x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for\n BIOS data'
date: 2025-03-31
last_reply: 2025-04-03
message_count: 11
participants: ['Dan Williams', 'Nikolay Borisov', 'Kirill Shutemov', 'Tom Lendacky', 'Dave Hansen', 'Naveen N Rao', 'Naveen N Rao']
---

## [1] Dan Williams — 2025-03-31

Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
address space) via /dev/mem results in an SEPT violation.

The cause is ioremap() (via xlate_dev_mem_ptr()) establishing an
unencrypted mapping where the kernel had established an encrypted
mapping previously.

Teach __ioremap_check_other() that this address space shall always be
mapped as encrypted as historically it is memory resident data, not MMIO
with side-effects.

Cc: <x86@kernel.org>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Kirill Shutemov <kirill.shutemov@linux.intel.com>
Reported-by: Nikolay Borisov <nik.borisov@suse.com>
Closes: http://lore.kernel.org/20250318113604.297726-1-nik.borisov@suse.com [1]
Tested-by: Nikolay Borisov <nik.borisov@suse.com>
Fixes: 9aa6ea69852c ("x86/tdx: Make pages shared in ioremap()")
Cc: <stable@vger.kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/mm/ioremap.c |    4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/mm/ioremap.c b/arch/x86/mm/ioremap.c
index 42c90b420773..9e81286a631e 100644
--- a/arch/x86/mm/ioremap.c
+++ b/arch/x86/mm/ioremap.c
@@ -122,6 +122,10 @@ static void __ioremap_check_other(resource_size_t addr, struct ioremap_desc *des
 		return;
 	}
 
+	/* Ensure BIOS data (see devmem_is_allowed()) is consistently mapped */
+	if (PHYS_PFN(addr) < 256)
+		desc->flags |= IORES_MAP_ENCRYPTED;
+
 	if (!IS_ENABLED(CONFIG_EFI))
 		return;

---

## [2] Nikolay Borisov — 2025-04-01
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

On 1.04.25 г. 2:14 ч., Dan Williams wrote:
> Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
> address space) via /dev/mem results in an SEPT violation.

Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>

> ---
>   arch/x86/mm/ioremap.c |    4 ++++

Side question: Is it guaranteed that this region will be mapped with 4k 
pages and not some larger size? I.e should the 256 constant be dependent 
on the current page size?

> +
>   	if (!IS_ENABLED(CONFIG_EFI))

---

## [3] Kirill Shutemov — 2025-04-01
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

On Mon, Mar 31, 2025 at 04:14:40PM -0700, Dan Williams wrote:
> Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
> address space) via /dev/mem results in an SEPT violation.

I am not sure if all AMD platforms would survive that.

Tom?

> 
> Cc: <x86@kernel.org>

Maybe
	if (addr < BIOS_END)

?

> +		desc->flags |= IORES_MAP_ENCRYPTED;
> +

---

## [4] Tom Lendacky — 2025-04-01
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

On 4/1/25 02:57, Kirill Shutemov wrote:
> On Mon, Mar 31, 2025 at 04:14:40PM -0700, Dan Williams wrote:
>> Nikolay reports [1] that accessing BIOS data (first 1MB of the physical

I haven't tested this, yet, but with SME the BIOS is not encrypted, so
that would need an unencrypted mapping.

Could you qualify your mapping with a TDX check? Or can you do something
in the /dev/mem support to map appropriately?

I'm adding @Naveen since he is preparing a patch to prevent /dev/mem
from accessing ROM areas under SNP as those can trigger #VC for a page
that is mapped encrypted but has not been validated. He's looking at
possibly adding something to x86_platform_ops that can be overridden.
The application would get a bad return code vs an exception.

Thanks,
Tom

> 
>>

---

## [5] Dave Hansen — 2025-04-01
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

On 4/1/25 08:07, Tom Lendacky wrote:
> I haven't tested this, yet, but with SME the BIOS is not encrypted, so
> that would need an unencrypted mapping.

How many more /dev/mem band-aids will we need for TDX and SEV before we
just throw up our hands and turn it off?

Maybe the x86_platform_ops call should just be "Do we allow /dev/mem at
all?"

---

## [6] Naveen N Rao — 2025-04-03
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

On Tue, Apr 01, 2025 at 10:07:18AM -0500, Tom Lendacky wrote:
> On 4/1/25 02:57, Kirill Shutemov wrote:
> > On Mon, Mar 31, 2025 at 04:14:40PM -0700, Dan Williams wrote:

The thought with x86_platform_ops was that TDX may want to differ and 
setup separate ranges to deny access to. For SEV-SNP, we primarily want 
to disallow the video ROM range at this point. Something like the below.

If this is not something TDX wants, then we should be able to add a 
check for SNP in devmem_is_allowed() directly without the 
x86_platform_ops.


- Naveen


---
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 583df2c6a2e3..fa9f23200ee4 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -761,6 +761,18 @@ static u64 __init get_jump_table_addr(void)
 	return ret;
 }
 
+bool sev_snp_mem_access_allowed(unsigned long pfn)
+{
+	/*
+	 * Reject access to ROM address range (0xc0000 to 0xfffff) for SEV-SNP guests
+	 * as that address range is not validated, so access can cause #VC exception
+	 */
+	if (pfn >= 0xc0 && pfn <= 0xff)
+		return 0;
+
+	return 1;
+}
+
 static void __head
 early_set_pages_state(unsigned long vaddr, unsigned long paddr,
 		      unsigned long npages, enum psc_op op)
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ba7999f66abe..f94522da9eb5 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -454,6 +454,7 @@ static inline int pvalidate(unsigned long vaddr, bool rmp_psize, bool validate)
 struct snp_guest_request_ioctl;
 
 void setup_ghcb(void);
+bool sev_snp_mem_access_allowed(unsigned long pfn);
 void early_snp_set_memory_private(unsigned long vaddr, unsigned long paddr,
 				  unsigned long npages);
 void early_snp_set_memory_shared(unsigned long vaddr, unsigned long paddr,
@@ -496,6 +497,7 @@ static inline void sev_enable(struct boot_params *bp) { }
 static inline int pvalidate(unsigned long vaddr, bool rmp_psize, bool validate) { return 0; }
 static inline int rmpadjust(unsigned long vaddr, bool rmp_psize, unsigned long attrs) { return 0; }
 static inline void setup_ghcb(void) { }
+static inline bool sev_snp_mem_access_allowed(unsigned long pfn) { return true; }
 static inline void __init
 early_snp_set_memory_private(unsigned long vaddr, unsigned long paddr, unsigned long npages) { }
 static inline void __init
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 36698cc9fb44..0add7878e413 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -307,6 +307,7 @@ struct x86_hyper_runtime {
  * @realmode_reserve:		reserve memory for realmode trampoline
  * @realmode_init:		initialize realmode trampoline
  * @hyper:			x86 hypervisor specific runtime callbacks
+ * @mem_access_allowed:	filter accesses to pfn
  */
 struct x86_platform_ops {
 	unsigned long (*calibrate_cpu)(void);
@@ -324,6 +325,7 @@ struct x86_platform_ops {
 	void (*set_legacy_features)(void);
 	void (*realmode_reserve)(void);
 	void (*realmode_init)(void);
+	bool (*mem_access_allowed)(unsigned long pfn);
 	struct x86_hyper_runtime hyper;
 	struct x86_guest guest;
 };
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index 0a2bbd674a6d..83217de27b46 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -142,6 +142,7 @@ static bool enc_cache_flush_required_noop(void) { return false; }
 static void enc_kexec_begin_noop(void) {}
 static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
+static bool mem_access_allowed_noop(unsigned long pfn) { return true; }
 
 struct x86_platform_ops x86_platform __ro_after_init = {
 	.calibrate_cpu			= native_calibrate_cpu_early,
@@ -156,6 +157,7 @@ struct x86_platform_ops x86_platform __ro_after_init = {
 	.restore_sched_clock_state	= tsc_restore_sched_clock_state,
 	.realmode_reserve		= reserve_real_mode,
 	.realmode_init			= init_real_mode,
+	.mem_access_allowed		= mem_access_allowed_noop,
 	.hyper.pin_vcpu			= x86_op_int_noop,
 	.hyper.is_private_mmio		= is_private_mmio_noop,
 
diff --git a/arch/x86/mm/init.c b/arch/x86/mm/init.c
index bfa444a7dbb0..64750d710f9f 100644
--- a/arch/x86/mm/init.c
+++ b/arch/x86/mm/init.c
@@ -867,6 +867,9 @@ void __init poking_init(void)
  */
 int devmem_is_allowed(unsigned long pagenr)
 {
+	if (!x86_platform.mem_access_allowed(pagenr))
+		return 0;
+
 	if (region_intersects(PFN_PHYS(pagenr), PAGE_SIZE,
 				IORESOURCE_SYSTEM_RAM, IORES_DESC_NONE)
 			!= REGION_DISJOINT) {
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 7490ff6d83b1..75e2d86cdab9 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -532,6 +532,7 @@ void __init sme_early_init(void)
 		 * parsing has happened.
 		 */
 		x86_init.resources.dmi_setup = snp_dmi_setup;
+		x86_platform.mem_access_allowed = sev_snp_mem_access_allowed;
 	}
 
 	/*

---

## [7] Dan Williams — 2025-04-02
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

Nikolay Borisov wrote:
> 
> 

True, if in some future kernel PAGE_SHIFT changes for x86 then both
devmem and this code would be confused.

I will submit a follow-on patch to clean that up.

That said, I expect PAGE_SHIFT != 12 breaks many other places besides
this in x86. I wrote it this way just for symmetry with
devmem_is_allowed().

---

## [8] Dan Williams — 2025-04-02
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

Kirill Shutemov wrote:
[..]
> > diff --git a/arch/x86/mm/ioremap.c b/arch/x86/mm/ioremap.c
> > index 42c90b420773..9e81286a631e 100644

Looks good to me.

---

## [9] Dan Williams — 2025-04-02
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

Dave Hansen wrote:
> On 4/1/25 08:07, Tom Lendacky wrote:
> > I haven't tested this, yet, but with SME the BIOS is not encrypted, so

I think the problem is bigger than this, we have no data structure
besides the iomem resource tree for maintaining mapping consistency and
this problem gets worse with the impending TEE I/O work where devices
are going to be dynamically transitioning from shared-to-private and
back for their MMIO.

> Maybe the x86_platform_ops call should just be "Do we allow /dev/mem at
> all?"

At least x86_platform_ops is the answer if TDX and SEV-SNP have
different answers to the question of whether the first 1MB of address
should always be mapped encrypted or unencrypted.

---

## [10] Dan Williams — 2025-04-02
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

Naveen N Rao wrote:
> On Tue, Apr 01, 2025 at 10:07:18AM -0500, Tom Lendacky wrote:
> > On 4/1/25 02:57, Kirill Shutemov wrote:

So I think there are 2 problems is a range consistently mapped by early
init code + various ioremap callers, and for encrypted mappings is there
potential unvalidated access that needs to be prevented outright.

The theoretical use case I have in mind is that userspace PCI drivers
have no real reason to be blocked in a confidential VM. Most of the
validation work to transition MMIO from shared to private is driven by
userspace anyway so it is unfortunate that after the end of that
conversion devmem and PCI-sysfs still block mappings.

However, there is no need to do pre-enabling for a theoretical use case.
So I am ok if devmem_is_allowed() globally says no for TVMs and then see
who screams with a practical problem that causes.

---

## [11] Naveen N Rao — 2025-04-03
*Subject: Re: [PATCH] x86/ioremap: Maintain consistent IORES_MAP_ENCRYPTED for
 BIOS data*

On Wed, Apr 02, 2025 at 02:36:37PM -0700, Dan Williams wrote:
> Naveen N Rao wrote:
> > On Tue, Apr 01, 2025 at 10:07:18AM -0500, Tom Lendacky wrote:

That makes sense. I have posted that patch with some changes:
https://lore.kernel.org/all/20250403120228.2344377-1-naveen@kernel.org/T/#u

It should be trivial to add a change for Intel to block the first 1MB 
for TVMs.


Thanks,
Naveen

---
