---
title: '[RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX VM in TD mode'
date: 2024-05-22
last_reply: 2024-05-28
message_count: 8
participants: ['Dexuan Cui', 'Kirill A. Shutemov', 'Dave Hansen', 'Michael Kelley', 'Tom Lendacky']
---

## [1] Dexuan Cui — 2024-05-22

A TDX VM on Hyper-V may run in TD mode or Partitioned TD mode (L2). For
the former, the VM has not enabled the Hyper-V TSC page (which is defined
in drivers/clocksource/hyperv_timer.c: "... tsc_pg __bss_decrypted ...")
because, for such a VM, the hypervisor requires that the page should be
shared, but currently the __bss_decrypted is not working for such a VM
yet.

Hyper-V TSC page can work as a clocksource device similar to KVM pv
clock, and it's also used by the Hyper-V timer code to get the current
time: see hv_init_tsc_clocksource(), which sets the global function
pointer hv_read_reference_counter to read_hv_clock_tsc(); when
Hyper-V TSC page is not enabled, hv_read_reference_counter defaults to
be drivers/hv/hv_common.c: __hv_read_ref_counter(), which is suboptimal
as it uses the slow MSR interface to get the time info.

The attribute __bss_decrypted was added for a native SNP VM by the
commit 45f46b1ac95e ("clocksource: hyper-v: Mark hyperv tsc page unencrypted in sev-snp enlightened guest")

The attribute works for SNP because of the commit below
commit b3f0907c71e0 ("x86/mm: Add .bss..decrypted section to hold shared variables")

The attribute is not working for TDX because __startup_64() ->
sme_postprocess_startup() is not for TDX; we can't just call
set_memory_decrypted() in sme_postprocess_startup() because
sme_postprocess_startup() runs too early and set_memory_decrypted() is not
working there yet.

This RFC patch calls set_memory_decrypted() in a later place, i.e., in
start_kernel() -> setup_arch() -> init_hypervisor_platform() ->
ms_hyperv_init_platform(), so set_memory_decrypted() works there;
accordingly, mem_encrypt_free_decrypted_mem() -> set_memory_encrypted()
must be called for TDX now.

When a TDX VM runs in Partitioned TD mode (L2), the Hyper-V TSC page should
be a private page, so set_memory_decrypted() should not be called for the
page in such a VM. Introduce a global variable "tdx_partitioned_td_l2" to
handle this type of VM differently.

BTW, the 4KB Hyper-V TSC page is enabled very early in
hv_init_tsc_clocksource(), where set_memory_decrypted() is not working yet,
so we can't simply call set_memory_decrypted() in hv_init_tsc_clocksource()
for a TDX VM in TD mode, and we need to get the attribute __bss_decrypted
to work for such a VM.

The changes to arch/x86/kernel/cpu/mshyperv.c and
arch/x86/mm/mem_encrypt_amd.c are not satisfying to me. I wish there
could be a better way to support __bss_decrypted for a native TDX VM
so that a TDX VM on KVM could also benefit from __bss_decrypted, if
some one wants to use it in future. BTW, kvm_init_platform() has
similar code for SNP.

This is just a RFC patch. I apprecite your insight. Thanks!

Signed-off-by: Dexuan Cui <decui@microsoft.com>
---
 arch/x86/coco/core.c           | 15 +++++++++++++++
 arch/x86/coco/tdx/tdx.c        |  2 ++
 arch/x86/hyperv/ivm.c          |  3 ++-
 arch/x86/include/asm/tdx.h     |  1 +
 arch/x86/kernel/cpu/mshyperv.c |  8 ++++++--
 arch/x86/mm/mem_encrypt_amd.c  |  3 ++-
 6 files changed, 28 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/core.c b/arch/x86/coco/core.c
index b31ef2424d194..61cec405f1084 100644
--- a/arch/x86/coco/core.c
+++ b/arch/x86/coco/core.c
@@ -15,6 +15,7 @@
 
 #include <asm/archrandom.h>
 #include <asm/coco.h>
+#include <asm/tdx.h>
 #include <asm/processor.h>
 
 enum cc_vendor cc_vendor __ro_after_init = CC_VENDOR_NONE;
@@ -25,8 +26,22 @@ static struct cc_attr_flags {
 	      __resv		: 63;
 } cc_flags;
 
+static bool noinstr intel_cc_platform_td_l2(enum cc_attr attr)
+{
+	switch (attr) {
+	case CC_ATTR_GUEST_MEM_ENCRYPT:
+	case CC_ATTR_MEM_ENCRYPT:
+		return true;
+	default:
+		return false;
+	}
+}
+
 static bool noinstr intel_cc_platform_has(enum cc_attr attr)
 {
+	if (tdx_partitioned_td_l2)
+		return intel_cc_platform_td_l2(attr);
+
 	switch (attr) {
 	case CC_ATTR_GUEST_UNROLL_STRING_IO:
 	case CC_ATTR_HOTPLUG_DISABLED:
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index abf3cd591afd3..8e6ab42add7c0 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -39,6 +39,8 @@
 
 #define TDREPORT_SUBTYPE_0	0
 
+bool tdx_partitioned_td_l2 __ro_after_init;
+
 /* Called from __tdx_hypercall() for unrecoverable failure */
 noinstr void __noreturn __tdx_hypercall_failed(void)
 {
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index 768d73de0d098..52cd44e507846 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -626,7 +626,7 @@ static bool hv_is_private_mmio(u64 addr)
 	return false;
 }
 
-void __init hv_vtom_init(void)
+void __init hv_vtom_init(void) /* TODO: rename the function for TDX */
 {
 	enum hv_isolation_type type = hv_get_isolation_type();
 
@@ -650,6 +650,7 @@ void __init hv_vtom_init(void)
 
 	case HV_ISOLATION_TYPE_TDX:
 		cc_vendor = CC_VENDOR_INTEL;
+		tdx_partitioned_td_l2 = true;
 		break;
 
 	default:
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index eba178996d845..ddcc9ef82dc99 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -66,6 +66,7 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport);
 
 u64 tdx_hcall_get_quote(u8 *buf, size_t size);
 
+extern bool tdx_partitioned_td_l2;
 #else
 
 static inline void tdx_early_init(void) { };
diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index e0fd57a8ba840..7c336bc020c9f 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -18,6 +18,7 @@
 #include <linux/kexec.h>
 #include <linux/i8253.h>
 #include <linux/random.h>
+#include <linux/set_memory.h>
 #include <asm/processor.h>
 #include <asm/hypervisor.h>
 #include <asm/hyperv-tlfs.h>
@@ -449,8 +450,11 @@ static void __init ms_hyperv_init_platform(void)
 			ms_hyperv.hints &= ~HV_X64_APIC_ACCESS_RECOMMENDED;
 
 			if (!ms_hyperv.paravisor_present) {
-				/* To be supported: more work is required.  */
-				ms_hyperv.features &= ~HV_MSR_REFERENCE_TSC_AVAILABLE;
+				unsigned long vaddr = (unsigned long)__start_bss_decrypted;
+				unsigned long vaddr_end = (unsigned long)__end_bss_decrypted;
+
+				for (; vaddr < vaddr_end; vaddr += PMD_SIZE)
+					set_memory_decrypted(vaddr, PMD_SIZE >> PAGE_SHIFT);
 
 				/* HV_MSR_CRASH_CTL is unsupported. */
 				ms_hyperv.misc_features &= ~HV_FEATURE_GUEST_CRASH_MSR_AVAILABLE;
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 422602f6039b8..0ddb9e5d222c3 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -25,6 +25,7 @@
 #include <asm/fixmap.h>
 #include <asm/setup.h>
 #include <asm/mem_encrypt.h>
+#include <asm/tdx.h>
 #include <asm/bootparam.h>
 #include <asm/set_memory.h>
 #include <asm/cacheflush.h>
@@ -529,7 +530,7 @@ void __init mem_encrypt_free_decrypted_mem(void)
 	 * CC_ATTR_MEM_ENCRYPT, aren't necessarily equivalent in a Hyper-V VM
 	 * using vTOM, where sme_me_mask is always zero.
 	 */
-	if (sme_me_mask) {
+	if (sme_me_mask || (cc_vendor == CC_VENDOR_INTEL && !tdx_partitioned_td_l2)) {
 		r = set_memory_encrypted(vaddr, npages);
 		if (r) {
 			pr_warn("failed to free unused decrypted pages\n");

---

## [2] Kirill A. Shutemov — 2024-05-23
*Subject: Re: [RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX
 VM in TD mode*

On Wed, May 22, 2024 at 07:24:41PM -0700, Dexuan Cui wrote:
> A TDX VM on Hyper-V may run in TD mode or Partitioned TD mode (L2). For
> the former, the VM has not enabled the Hyper-V TSC page (which is defined

I don't see how it is safe. It opens guest clock for manipulations form
VMM. Could you elaborate on security implications?

> Hyper-V TSC page can work as a clocksource device similar to KVM pv
> clock, and it's also used by the Hyper-V timer code to get the current

Why can't the guest just read the TSC directly? Why do we need the page?
I am confused.

---

## [3] Dave Hansen — 2024-05-23
*Subject: Re: [RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX
 VM in TD mode*

On 5/22/24 19:24, Dexuan Cui wrote:
...
> +static bool noinstr intel_cc_platform_td_l2(enum cc_attr attr)
> +{

On its face, this _looks_ rather troubling.  It just hijacks all of the
attributes.  It totally bifurcates the code.  Anything that gets added
to intel_cc_platform_has() now needs to be considered for addition to
intel_cc_platform_td_l2().

> --- a/arch/x86/mm/mem_encrypt_amd.c
> +++ b/arch/x86/mm/mem_encrypt_amd.c
...
> @@ -529,7 +530,7 @@ void __init mem_encrypt_free_decrypted_mem(void)
>  	 * CC_ATTR_MEM_ENCRYPT, aren't necessarily equivalent in a Hyper-V VM

If _ever_ there were a place for a new CC_ attribute, this would be it.
It's also a bit concerning that now we've got a (cc_vendor ==
CC_VENDOR_INTEL) check in an amd.c file.

So all of that on top of Kirill's "why do we need this in the first
place" questions leave me really scratching my head on this one.

---

## [4] Dexuan Cui — 2024-05-24
*Subject: RE: [RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX
 VM in TD mode*

> From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> Sent: Thursday, May 23, 2024 5:06 AM

The intention of the patch is not to enable Hyper-V TSC page as a clocksource
in such a VM. The default clocksource is still TSC.

The intention of the patch is to enable Hyper-V TSC page only for Hyper-V
timer. My understanding is that: "Hyper-V timer + Hyper-V TSC page" should
be as safe as "local APIC timer + TSC" because the VM needs the hypervisor
to emulate the timers, anyway. The guest may get a bad value of Hyper-V
TSC page from a malicious hypervisor, and consequently the Hyper-V timer
may fire too early or too late, but the similar thing can also happen to a local
APIC timer, if a malicious hypervisor decides to deliver the timer interrupt
too early or too late.

> > Hyper-V TSC page can work as a clocksource device similar to KVM pv
> > clock, and it's also used by the Hyper-V timer code to get the current

Both Hyper-V TSC page and Hyper-V Reference Counter MSR return the
absolute time in the unit of 0.1us since the VM starts to run, i.e. the "frequency"
is 10M, which has a higher resolution than the emulated local APIC timer. 

Hyper-V timer depends on Hyper-V TSC page or Hyper-V Reference Counter MSR
as it also uses the absolute time in the unit of 0.1us. We could potentially read the
TSC and convert it to the absolute time in the unit of 0.1us, but the required math
calculation is not very easy and can be unreliable (e.g. I suppose an AP's TSC is 0
when it's just being brought up online? But the Hyper-V TSC page value on the AP
should be much bigger than 0) And, there will be an inaccuracy with the Hyper-V
side conversion that may use a slightly different math calculation (e.g. slightly
different TSC frequency or 'multi' or 'shift' values).

It turns out the local APIC timer in such a VM also works! So probably the VM
can just use local APIC timer and doesn't use Hyper-V timer. However, I noticed a
strange thing: in my 128-VP VM, each local APIC timer constantly generates
100 interrupts per second, even if the VM is idle. Trying to find out why. I do
enable tickles in my .config:

CONFIG_NO_HZ_COMMON=y
# CONFIG_HZ_PERIODIC is not set
# CONFIG_NO_HZ_IDLE is not set
CONFIG_NO_HZ_FULL=y
CONFIG_NO_HZ=y
CONFIG_HZ_100=y
CONFIG_HZ=100

Thanks,
-- Dexuan

---

## [5] Dexuan Cui — 2024-05-24
*Subject: RE: [RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX
 VM in TD mode*

> From: Dave Hansen <dave.hansen@intel.com>
> Sent: Thursday, May 23, 2024 7:26 AM

Maybe the bifurcation is necessary? TD mode is different from
Partitioned TD mode (L2), after all. Another reason for the bifurcation
is:  currently online/offline'ing is disallowed for a TD VM, but actually
Hyper-V is able to support CPU online/offline'ing for a TD VM in
Partitioned TD mode (L2) -- how can we allow online/offline'ing for such
a VM?

BTW, the bifurcation code is copied from amd_cc_platform_has(), where
an AMD SNP VM may run in the vTOM mode.

> > --- a/arch/x86/mm/mem_encrypt_amd.c
> > +++ b/arch/x86/mm/mem_encrypt_amd.c
Not sure how to add a new CC attribute for the __bss_decrypted support.

For the cpu online/offline'ing support, I'm not sure how to add a new
CC attribute and not introduce the bifurcation.

> It's also a bit concerning that now we've got a (cc_vendor ==
> CC_VENDOR_INTEL) check in an amd.c file.
I agree my change here is ugly...
Currently the __bss_decrypted support is only used for SNP.
Not sure if we should get it to work for TDX as well.

> So all of that on top of Kirill's "why do we need this in the first
> place" questions leave me really scratching my head on this one.
Probably I'll just use local APIC timer in such a VM or delay enabling
Hyper-V TSC page to a later place where set_memory_decrypted()
works for me. However, I still would like to find out how to allow
CPU online/offline'ing for a TDX VM in Partitioned TD mode (L2).

Thanks,
Dexuan

---

## [6] Michael Kelley — 2024-05-24
*Subject: RE: [RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX
 VM in TD mode*

From: Dexuan Cui <decui@microsoft.com> Sent: Friday, May 24, 2024 1:46 AM
> 
> > From: Dave Hansen <dave.hansen@intel.com>

FWIW, the above won't work in a kernel built with CONFIG_TDX_GUEST=y
but CONFIG_AMD_MEM_ENCRYPT=n. mem_encrypt_free_decrypted_mem()
in arch/x86/mm/mem_encrypt_amd.c won't get built, and an empty stub is used.

> > >  		r = set_memory_encrypted(vaddr, npages);
> > >  		if (r) {

My thoughts:

__bss_decrypted is named as if it applies to any CoCo VM, but really
it is specific to AMD SEV. It was originally used for a GHCB page, which
is SEV-specific, and then it proved to be convenient for the Hyper-V TSC
page. Ideally, we could fix __bss_decrypted to work generally in a
TDX VM without any dependency on code specific to a hypervisor. But
looking at some of the details, that may be non-trivial.

A narrower solution is to remove the Hyper-V TSC page from
__bss_decrypted, and use Hyper-V specific code on both TDX and
SEV-SNP to decrypt just that page (not the entire __bss_decrypted), 
based on whether the Hyper-V guest is running with a paravisor.
From Dexuan's patch, it looks like set_memory_decrypted()
works on TDX at the time that ms_hyperv_init_platform() runs.
Does it also work on SEV-SNP? The code in kvm_init_platform()
uses early_set_mem_enc_dec_hypercall() with
kvm_sev_hc_page_enc_status(), which is SEV only.  So maybe
the normal set_memory_decrypted() doesn't work on SEV at
that point, though I'm not at all clear on what kvm_init_platform is
trying to do.  Shouldn't __bss_decrypted already be set up correctly?

The issue of taking CPUs offline is separate. Is the inability to take
a CPU offline with TDX an architectural limitation? Or just a
current Linux implementation limitation? And what about in an
L2 TDX VM?  If the existence of a limitation in a L2 TDX VM is
dependent on the hypervisor/paravisor, then can cc_platform_has()
check some architectural flag (that's independent of the host
hypervisor) to know if it is running in an L2 TDX VM and return false
for CC_ATTR_HOTPLUG_DISABLED? If a host/paravisor combo doesn't
allow taking a L2 TDX VM CPU offline, then it would be up to that
combo to implement the appropriate restriction. It's not hard to add
a CPUHP state that would prevent it.

Michael

---

## [7] kirill.shutemov@linux.intel.com — 2024-05-28
*Subject: Re: [RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX
 VM in TD mode*

On Fri, May 24, 2024 at 08:45:42AM +0000, Dexuan Cui wrote:
> > From: Dave Hansen <dave.hansen@intel.com>
> > Sent: Thursday, May 23, 2024 7:26 AM

I would like to keep the same code paths for all TDX guests level, if
possible.

> TD mode is different from
> Partitioned TD mode (L2), after all. Another reason for the bifurcation

This is going to be fixed by kexec patchset. It was wrong to block offline
based on TDX enumeration. It has to be stopped for MADT wake up method, if
reset vector is not supported.

---

## [8] Tom Lendacky — 2024-05-28
*Subject: Re: [RFC PATCH] clocksource: hyper-v: Enable the tsc_page for a TDX
 VM in TD mode*

On 5/24/24 17:44, Michael Kelley wrote:
> From: Dexuan Cui <decui@microsoft.com> Sent: Friday, May 24, 2024 1:46 AM
>>> From: Dave Hansen <dave.hansen@intel.com>

> 
> My thoughts:

IIRC, it was originally used for KVM clock, not the GHCB page, since
plain SEV doesn't use a GHCB, see:

b3f0907c71e0 ("x86/mm: Add .bss..decrypted section to hold shared variables")

> is SEV-specific, and then it proved to be convenient for the Hyper-V TSC
> page. Ideally, we could fix __bss_decrypted to work generally in a

In reality, TDX should also make this area shared as that is how this
section is meant to be setup. But up till now, I don't think TDX used
anything in the __bss_decrypted section, so it was never moved to a
common location and has remained SEV specific.

> 
> A narrower solution is to remove the Hyper-V TSC page from

This is to inform the hypervisor that these pages are now shared, see
below.

> the normal set_memory_decrypted() doesn't work on SEV at
> that point, though I'm not at all clear on what kvm_init_platform is

With SEV, yes, the pagetable is set up correctly. And specific to SNP,
the RMP is set up correctly because of the page state change (PSC) call
which also notifies the hypervisor of the state change.

But since the RMP PSC is SNP specific, SEV and SEV-ES require the
separate hypercall to notify the hypervisor of the state change.

Thanks,
Tom

>

---
