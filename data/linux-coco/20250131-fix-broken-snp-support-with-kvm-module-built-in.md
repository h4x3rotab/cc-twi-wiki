---
title: 'Fix broken SNP support with KVM module built-in'
date: 2025-01-31
last_reply: 2025-02-05
message_count: 12
participants: ['Ashish Kalra', 'Sean Christopherson', 'Vasant Hegde']
---

## [1] Ashish Kalra — 2025-01-31

From: Ashish Kalra <ashish.kalra@amd.com>

This patch-set fixes the current SNP host enabling code and effectively SNP
which is broken with respect to the KVM module being built-in.

Essentially SNP host enabling code should be invoked before KVM
initialization, which is currently not the case when KVM is built-in.

SNP host support is currently enabled in snp_rmptable_init() which is
invoked as a device_initcall(). Here device_initcall() is used as
snp_rmptable_init() expects AMD IOMMU SNP support to be enabled prior
to it and the AMD IOMMU driver enables SNP support after PCI bus enumeration.

This patch-set adds support to call snp_rmptable_init() early and
directly from iommu_snp_enable() (after checking and enabling IOMMU
SNP support) which enables SNP host support before KVM initialization
with kvm_amd module built-in.

Additionally the patch-set adds support to initialize PSP SEV driver
during KVM module probe time.

This patch-set has been tested with the following cases/scenarios:
1). kvm_amd module built-in.
2). kvm_amd module built-in with intremap=off kernel command line.
3). kvm_amd module built-in with iommu=off kernel command line.
4). kvm_amd built as a module.
5). kvm_amd built as module with iommu=off kernel command line.

v2:
- Drop calling iommu_snp_enable() early before enabling IOMMUs as
IOMMU subsystem gets initialized via subsys_initcall() and hence
snp_rmptable_init() cannot be invoked via subsys_initcall().
- Instead add support to call snp_rmptable_init() early and
directly via iommu_snp_enable().
- Fix commit logs.

Fixes: c3b86e61b756 ("x86/cpufeatures: Enable/unmask SEV-SNP CPU feature")

Ashish Kalra (1):
  x86/sev: Fix broken SNP support with KVM module built-in

Sean Christopherson (3):
  crypto: ccp: Add external API interface for PSP module initialization
  KVM: SVM: Ensure PSP module is initialized if KVM module is built-in
  iommu/amd: Enable Host SNP support after enabling IOMMU SNP support

 arch/x86/include/asm/sev.h  |  2 ++
 arch/x86/kvm/svm/sev.c      | 10 ++++++++++
 arch/x86/virt/svm/sev.c     | 23 +++++++----------------
 drivers/crypto/ccp/sp-dev.c | 14 ++++++++++++++
 drivers/iommu/amd/init.c    | 18 ++++++++++++++----
 include/linux/psp-sev.h     |  9 +++++++++
 6 files changed, 56 insertions(+), 20 deletions(-)

---

## [2] Ashish Kalra — 2025-01-31
*Subject: [PATCH v2 1/4] crypto: ccp: Add external API interface for PSP module initialization*

From: Sean Christopherson <seanjc@google.com>

KVM is dependent on the PSP SEV driver and PSP SEV driver needs to be
loaded before KVM module. In case of module loading any dependent
modules are automatically loaded but in case of built-in modules there
is no inherent mechanism available to specify dependencies between
modules and ensure that any dependent modules are loaded implicitly.

Add a new external API interface for PSP module initialization which
allows PSP SEV driver to be loaded explicitly if KVM is built-in.

Signed-off-by: Sean Christopherson <seanjc@google.com>
Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sp-dev.c | 14 ++++++++++++++
 include/linux/psp-sev.h     |  9 +++++++++
 2 files changed, 23 insertions(+)

diff --git a/drivers/crypto/ccp/sp-dev.c b/drivers/crypto/ccp/sp-dev.c
index 7eb3e4668286..3467f6db4f50 100644
--- a/drivers/crypto/ccp/sp-dev.c
+++ b/drivers/crypto/ccp/sp-dev.c
@@ -19,6 +19,7 @@
 #include <linux/types.h>
 #include <linux/ccp.h>
 
+#include "sev-dev.h"
 #include "ccp-dev.h"
 #include "sp-dev.h"
 
@@ -253,8 +254,12 @@ struct sp_device *sp_get_psp_master_device(void)
 static int __init sp_mod_init(void)
 {
 #ifdef CONFIG_X86
+	static bool initialized;
 	int ret;
 
+	if (initialized)
+		return 0;
+
 	ret = sp_pci_init();
 	if (ret)
 		return ret;
@@ -263,6 +268,8 @@ static int __init sp_mod_init(void)
 	psp_pci_init();
 #endif
 
+	initialized = true;
+
 	return 0;
 #endif
 
@@ -279,6 +286,13 @@ static int __init sp_mod_init(void)
 	return -ENODEV;
 }
 
+#if IS_BUILTIN(CONFIG_KVM_AMD) && IS_ENABLED(CONFIG_KVM_AMD_SEV)
+int __init sev_module_init(void)
+{
+	return sp_mod_init();
+}
+#endif
+
 static void __exit sp_mod_exit(void)
 {
 #ifdef CONFIG_X86
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 903ddfea8585..f3cad182d4ef 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -814,6 +814,15 @@ struct sev_data_snp_commit {
 
 #ifdef CONFIG_CRYPTO_DEV_SP_PSP
 
+/**
+ * sev_module_init - perform PSP SEV module initialization
+ *
+ * Returns:
+ * 0 if the PSP module is successfully initialized
+ * negative value if the PSP module initialization fails
+ */
+int sev_module_init(void);
+
 /**
  * sev_platform_init - perform SEV INIT command
  *

---

## [3] Ashish Kalra — 2025-01-31
*Subject: [PATCH v2 2/4] KVM: SVM: Ensure PSP module is initialized if KVM module is built-in*

From: Sean Christopherson <seanjc@google.com>

The kernel's initcall infrastructure lacks the ability to express
dependencies between initcalls, whereas the modules infrastructure
automatically handles dependencies via symbol loading.  Ensure the
PSP SEV driver is initialized before proceeding in sev_hardware_setup()
if KVM is built-in as the dependency isn't handled by the initcall
infrastructure.

Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index a2a794c32050..0dbb25442ec1 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2972,6 +2972,16 @@ void __init sev_hardware_setup(void)
 	    WARN_ON_ONCE(!boot_cpu_has(X86_FEATURE_FLUSHBYASID)))
 		goto out;
 
+	/*
+	 * The kernel's initcall infrastructure lacks the ability to express
+	 * dependencies between initcalls, whereas the modules infrastructure
+	 * automatically handles dependencies via symbol loading.  Ensure the
+	 * PSP SEV driver is initialized before proceeding if KVM is built-in,
+	 * as the dependency isn't handled by the initcall infrastructure.
+	 */
+	if (IS_BUILTIN(CONFIG_KVM_AMD) && sev_module_init())
+		goto out;
+
 	/* Retrieve SEV CPUID information */
 	cpuid(0x8000001f, &eax, &ebx, &ecx, &edx);

---

## [4] Ashish Kalra — 2025-01-31
*Subject: [PATCH v2 3/4] x86/sev: Fix broken SNP support with KVM module built-in*

From: Ashish Kalra <ashish.kalra@amd.com>

This patch fixes issues with enabling SNP host support and effectively
SNP support which is broken with respect to the KVM module being
built-in.

SNP host support is enabled in snp_rmptable_init() which is invoked as a
device_initcall(). Here device_initcall() is used as snp_rmptable_init()
expects AMD IOMMU SNP support to be enabled prior to it and the AMD
IOMMU driver enables SNP support after PCI bus enumeration.

Now, if kvm_amd module is built-in, it gets initialized before SNP host
support is enabled in snp_rmptable_init() :

[   10.131811] kvm_amd: TSC scaling supported
[   10.136384] kvm_amd: Nested Virtualization enabled
[   10.141734] kvm_amd: Nested Paging enabled
[   10.146304] kvm_amd: LBR virtualization supported
[   10.151557] kvm_amd: SEV enabled (ASIDs 100 - 509)
[   10.156905] kvm_amd: SEV-ES enabled (ASIDs 1 - 99)
[   10.162256] kvm_amd: SEV-SNP enabled (ASIDs 1 - 99)
[   10.171508] kvm_amd: Virtual VMLOAD VMSAVE supported
[   10.177052] kvm_amd: Virtual GIF supported
...
...
[   10.201648] kvm_amd: in svm_enable_virtualization_cpu

And then svm_x86_ops->enable_virtualization_cpu()
(svm_enable_virtualization_cpu) programs MSR_VM_HSAVE_PA as following:
wrmsrl(MSR_VM_HSAVE_PA, sd->save_area_pa);

So VM_HSAVE_PA is non-zero before SNP support is enabled on all CPUs.

snp_rmptable_init() gets invoked after svm_enable_virtualization_cpu()
as following :
...
[   11.256138] kvm_amd: in svm_enable_virtualization_cpu
...
[   11.264918] SEV-SNP: in snp_rmptable_init

This triggers a #GP exception in snp_rmptable_init() when snp_enable()
is invoked to set SNP_EN in SYSCFG MSR:

[   11.294289] unchecked MSR access error: WRMSR to 0xc0010010 (tried to write 0x0000000003fc0000) at rIP: 0xffffffffaf5d5c28 (native_write_msr+0x8/0x30)
...
[   11.294404] Call Trace:
[   11.294482]  <IRQ>
[   11.294513]  ? show_stack_regs+0x26/0x30
[   11.294522]  ? ex_handler_msr+0x10f/0x180
[   11.294529]  ? search_extable+0x2b/0x40
[   11.294538]  ? fixup_exception+0x2dd/0x340
[   11.294542]  ? exc_general_protection+0x14f/0x440
[   11.294550]  ? asm_exc_general_protection+0x2b/0x30
[   11.294557]  ? __pfx_snp_enable+0x10/0x10
[   11.294567]  ? native_write_msr+0x8/0x30
[   11.294570]  ? __snp_enable+0x5d/0x70
[   11.294575]  snp_enable+0x19/0x20
[   11.294578]  __flush_smp_call_function_queue+0x9c/0x3a0
[   11.294586]  generic_smp_call_function_single_interrupt+0x17/0x20
[   11.294589]  __sysvec_call_function+0x20/0x90
[   11.294596]  sysvec_call_function+0x80/0xb0
[   11.294601]  </IRQ>
[   11.294603]  <TASK>
[   11.294605]  asm_sysvec_call_function+0x1f/0x30
...
[   11.294631]  arch_cpu_idle+0xd/0x20
[   11.294633]  default_idle_call+0x34/0xd0
[   11.294636]  do_idle+0x1f1/0x230
[   11.294643]  ? complete+0x71/0x80
[   11.294649]  cpu_startup_entry+0x30/0x40
[   11.294652]  start_secondary+0x12d/0x160
[   11.294655]  common_startup_64+0x13e/0x141
[   11.294662]  </TASK>

This #GP exception is getting triggered due to the following errata for
AMD family 19h Models 10h-1Fh Processors:

Processor may generate spurious #GP(0) Exception on WRMSR instruction:
Description:
The Processor will generate a spurious #GP(0) Exception on a WRMSR
instruction if the following conditions are all met:
- the target of the WRMSR is a SYSCFG register.
- the write changes the value of SYSCFG.SNPEn from 0 to 1.
- One of the threads that share the physical core has a non-zero
value in the VM_HSAVE_PA MSR.

The document being referred to above:
https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/revision-guides/57095-PUB_1_01.pdf

To summarize, with kvm_amd module being built-in, KVM/SVM initialization
happens before host SNP is enabled and this SVM initialization
sets VM_HSAVE_PA to non-zero, which then triggers a #GP when
SYSCFG.SNPEn is being set and this will subsequently cause
SNP_INIT(_EX) to fail with INVALID_CONFIG error as SYSCFG[SnpEn] is not
set on all CPUs.

This patch fixes the current SNP host enabling code and effectively SNP
which is broken with respect to the KVM module being built-in.

Essentially SNP host enabling code should be invoked before KVM
initialization, which is currently not the case when KVM is built-in.

Now, snp_rmptable_init() will be called early from iommu_snp_enable()
directly and not invoked via device_initcall() which enables SNP host
support before KVM initialization with kvm_amd module built-in.

Fixes: c3b86e61b756 ("x86/cpufeatures: Enable/unmask SEV-SNP CPU feature")
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h |  2 ++
 arch/x86/virt/svm/sev.c    | 23 +++++++----------------
 2 files changed, 9 insertions(+), 16 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 5d9685f92e5c..1581246491b5 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -531,6 +531,7 @@ static inline void __init snp_secure_tsc_init(void) { }
 
 #ifdef CONFIG_KVM_AMD_SEV
 bool snp_probe_rmptable_info(void);
+int snp_rmptable_init(void);
 int snp_lookup_rmpentry(u64 pfn, bool *assigned, int *level);
 void snp_dump_hva_rmpentry(unsigned long address);
 int psmash(u64 pfn);
@@ -541,6 +542,7 @@ void kdump_sev_callback(void);
 void snp_fixup_e820_tables(void);
 #else
 static inline bool snp_probe_rmptable_info(void) { return false; }
+static inline int snp_rmptable_init(void) { return -ENOSYS; }
 static inline int snp_lookup_rmpentry(u64 pfn, bool *assigned, int *level) { return -ENODEV; }
 static inline void snp_dump_hva_rmpentry(unsigned long address) {}
 static inline int psmash(u64 pfn) { return -ENODEV; }
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 1dcc027ec77e..42e74a5a7d78 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -505,19 +505,19 @@ static bool __init setup_rmptable(void)
  * described in the SNP_INIT_EX firmware command description in the SNP
  * firmware ABI spec.
  */
-static int __init snp_rmptable_init(void)
+int __init snp_rmptable_init(void)
 {
 	unsigned int i;
 	u64 val;
 
-	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
-		return 0;
+	if (WARN_ON_ONCE(!cc_platform_has(CC_ATTR_HOST_SEV_SNP)))
+		return -ENOSYS;
 
-	if (!amd_iommu_snp_en)
-		goto nosnp;
+	if (WARN_ON_ONCE(!amd_iommu_snp_en))
+		return -ENOSYS;
 
 	if (!setup_rmptable())
-		goto nosnp;
+		return -ENOSYS;
 
 	/*
 	 * Check if SEV-SNP is already enabled, this can happen in case of
@@ -530,7 +530,7 @@ static int __init snp_rmptable_init(void)
 	/* Zero out the RMP bookkeeping area */
 	if (!clear_rmptable_bookkeeping()) {
 		free_rmp_segment_table();
-		goto nosnp;
+		return -ENOSYS;
 	}
 
 	/* Zero out the RMP entries */
@@ -562,17 +562,8 @@ static int __init snp_rmptable_init(void)
 	crash_kexec_post_notifiers = true;
 
 	return 0;
-
-nosnp:
-	cc_platform_clear(CC_ATTR_HOST_SEV_SNP);
-	return -ENOSYS;
 }
 
-/*
- * This must be called after the IOMMU has been initialized.
- */
-device_initcall(snp_rmptable_init);
-
 static void set_rmp_segment_info(unsigned int segment_shift)
 {
 	rmp_segment_shift = segment_shift;

---

## [5] Ashish Kalra — 2025-01-31
*Subject: [PATCH v2 4/4] iommu/amd: Enable Host SNP support after enabling IOMMU SNP support*

From: Sean Christopherson <seanjc@google.com>

This patch fixes the current SNP host enabling code and effectively SNP
which is broken with respect to the KVM module being built-in.

SNP check on IOMMU is done during IOMMU PCI init (IOMMU_PCI_INIT stage).
And for that reason snp_rmptable_init() is currently invoked via
device_initcall() and cannot be invoked via subsys_initcall() as core
IOMMU subsystem gets initialized via subsys_initcall().

Essentially SNP host enabling code should be invoked before KVM
initialization, which is currently not the case when KVM is built-in
as SNP host support is enabled via device_initcall() which is
required as SNP check on IOMMU is done during IOMMU PCI init.

Hence, call snp_rmptable_init() early and directly from
iommu_snp_enable() (after checking and enabling IOMMU SNP support)
which enables SNP host support before KVM initialization with
kvm_amd module built-in.

Add additional handling for `iommu=off` or `amd_iommu=off` options.

If IOMMU initialization fails and iommu_snp_enable() is never reached,
CC_ATTR_HOST_SEV_SNP will be left set but that will cause PSP driver's
SNP_INIT to fail as IOMMU SNP sanity checks in SNP firmware will fail
as below:

[    9.723114] ccp 0000:23:00.1: sev enabled
[    9.727602] ccp 0000:23:00.1: psp enabled
[    9.732527] ccp 0000:a2:00.1: enabling device (0000 -> 0002)
[    9.739098] ccp 0000:a2:00.1: no command queues available
[    9.745167] ccp 0000:a2:00.1: psp enabled
[    9.805337] ccp 0000:23:00.1: SEV-SNP: failed to INIT rc -5, error 0x3
[    9.866426] ccp 0000:23:00.1: SEV API:1.53 build:5
...
and that will cause CC_ATTR_HOST_SEV_SNP flag to be cleared.

Fixes: 04d65a9dbb33 ("iommu/amd: Don't rely on external callers to enable IOMMU SNP support")
Co-developed-by: Vasant Hegde <vasant.hegde@amd.com>
Signed-off-by: Vasant Hegde <vasant.hegde@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/iommu/amd/init.c | 18 ++++++++++++++----
 1 file changed, 14 insertions(+), 4 deletions(-)

diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index c5cd92edada0..ee887aa4442f 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -3194,7 +3194,7 @@ static bool __init detect_ivrs(void)
 	return true;
 }
 
-static void iommu_snp_enable(void)
+static __init void iommu_snp_enable(void)
 {
 #ifdef CONFIG_KVM_AMD_SEV
 	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
@@ -3219,6 +3219,11 @@ static void iommu_snp_enable(void)
 		goto disable_snp;
 	}
 
+	if (snp_rmptable_init()) {
+		pr_warn("SNP: RMP initialization failed, SNP cannot be supported.\n");
+		goto disable_snp;
+	}
+
 	pr_info("IOMMU SNP support enabled.\n");
 	return;
 
@@ -3426,18 +3431,23 @@ void __init amd_iommu_detect(void)
 	int ret;
 
 	if (no_iommu || (iommu_detected && !gart_iommu_aperture))
-		return;
+		goto disable_snp;
 
 	if (!amd_iommu_sme_check())
-		return;
+		goto disable_snp;
 
 	ret = iommu_go_to_state(IOMMU_IVRS_DETECTED);
 	if (ret)
-		return;
+		goto disable_snp;
 
 	amd_iommu_detected = true;
 	iommu_detected = 1;
 	x86_init.iommu.iommu_init = amd_iommu_init;
+	return;
+
+disable_snp:
+	if (cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+		cc_platform_clear(CC_ATTR_HOST_SEV_SNP);
 }
 
 /****************************************************************************

---

## [6] Sean Christopherson — 2025-01-30
*Subject: Re: [PATCH v2 3/4] x86/sev: Fix broken SNP support with KVM module built-in*

On Fri, Jan 31, 2025, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 
  ^^^^^^^^^^

> ---
>  arch/x86/include/asm/sev.h |  2 ++

There's the wee little problem that snp_rmptable_init() is never called as of
this patch.  Dropping the device_initcall() needs to happen in the same patch
that wires up the IOMMU code to invoke snp_rmptable_init().  At a glance, I don't
see anything in this patch that can reasonably go in before the IOMMU change.

---

## [7] Sean Christopherson — 2025-01-30
*Subject: Re: [PATCH v2 4/4] iommu/amd: Enable Host SNP support after enabling
 IOMMU SNP support*

On Fri, Jan 31, 2025, Ashish Kalra wrote:
> From: Sean Christopherson <seanjc@google.com>
> 
  ^^^^^^^^^^
> ---
>  drivers/iommu/amd/init.c | 18 ++++++++++++++----

If you're feeling nitpicky, adding "__init" could be done in a separate patch.

>  {
>  #ifdef CONFIG_KVM_AMD_SEV

This handles initial failure, but it won't handle the case where amd_iommu_prepare()
fails, as the iommu_go_to_state() call from amd_iommu_enable() will get
short-circuited.  I don't see any pleasant options.  Maybe this?

diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index c5cd92edada0..436e47f13f8f 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -3318,6 +3318,8 @@ static int __init iommu_go_to_state(enum iommu_init_state state)
                ret = state_next();
        }
 
+       if (ret && !amd_iommu_snp_en && cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+               cc_platform_clear(CC_ATTR_HOST_SEV_SNP);
        return ret;
 }
 

Somewhat of a side topic, what happens if the RMP is fully configured and _then_
IOMMU initialization fails?  I.e. if amd_iommu_init_pci() or amd_iommu_enable_interrupts()
fails?  Is that even survivable?

>  
>  	amd_iommu_detected = true;

---

## [8] Kalra, Ashish — 2025-01-30
*Subject: Re: [PATCH v2 3/4] x86/sev: Fix broken SNP support with KVM module
 built-in*

Hello Sean,

On 1/30/2025 7:41 PM, Sean Christopherson wrote:
> On Fri, Jan 31, 2025, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

The issue with that is the IOMMU and x86 maintainers are different, so i believe that we will
need to split the dropping of device_initcall() in platform code and the code to wire up the
IOMMU driver to invoke snp_rmptable_init(), to get the patch merged in different trees ?
  
>At a glance, I don't see anything in this patch that can reasonably go in before the IOMMU change.
This patch prepares snp_rmptable_init() to be called via iommu_snp_enable(), so i assume this
is a pre-patch before the IOMMU change.

Thanks,
Ashish

---

## [9] Sean Christopherson — 2025-01-31
*Subject: Re: [PATCH v2 3/4] x86/sev: Fix broken SNP support with KVM module built-in*

On Thu, Jan 30, 2025, Ashish Kalra wrote:
> On 1/30/2025 7:41 PM, Sean Christopherson wrote:
> > On Fri, Jan 31, 2025, Ashish Kalra wrote:

No, that's pure insanity and not how patches that touch multiple subsystems are
handled.  This all goes through one tree, with Acks from the necessary parties.

---

## [10] Kalra, Ashish — 2025-01-31
*Subject: Re: [PATCH v2 4/4] iommu/amd: Enable Host SNP support after enabling
 IOMMU SNP support*

Hello Sean,

On 1/30/2025 7:48 PM, Sean Christopherson wrote:
> On Fri, Jan 31, 2025, Ashish Kalra wrote:
>> From: Sean Christopherson <seanjc@google.com>

This is surely hackish but it will work.

Though to add here, as mentioned in the patch commit logs, IOMMU needs to enabled for SNP_INIT to succeed. 

If IOMMU initialization fails and iommu_snp_enable() is never reached, CC_ATTR_HOST_SEV_SNP will be
left set but that will cause PSP driver's SNP_INIT to fail with invalid configuration error as 
IOMMU SNP sanity checks in SNP firmware will fail (if IOMMUs are not enabled) as below: 

[    9.723114] ccp 0000:23:00.1: sev enabled
[    9.727602] ccp 0000:23:00.1: psp enabled
[    9.732527] ccp 0000:a2:00.1: enabling device (0000 -> 0002)
[    9.739098] ccp 0000:a2:00.1: no command queues available
[    9.745167] ccp 0000:a2:00.1: psp enabled
[    9.805337] ccp 0000:23:00.1: SEV-SNP: failed to INIT rc -5, error 0x3
[    9.866426] ccp 0000:23:00.1: SEV API:1.53 build:5
...
and that will cause CC_ATTR_HOST_SEV_SNP flag to be cleared. 

> 
> Somewhat of a side topic, what happens if the RMP is fully configured and _then_

Actually, SNP firmware initializes the IOMMU to perform RMP enforcement during SNP_INIT,
but as i mentioned above if IOMMU is not enabled then SNP_INIT will fail. 

Thanks,
Ashish

> 
>>

---

## [11] Vasant Hegde — 2025-02-05
*Subject: Re: [PATCH v2 4/4] iommu/amd: Enable Host SNP support after enabling
 IOMMU SNP support*

Hi ,

On 1/31/2025 7:18 AM, Sean Christopherson wrote:
> On Fri, Jan 31, 2025, Ashish Kalra wrote:
>> From: Sean Christopherson <seanjc@google.com>

I think we should clear when `amd_iommu_snp_en` is true. May be below check is
enough?

	if (ret && amd_iommu_snp_en)


-Vasant

---

## [12] Sean Christopherson — 2025-02-05
*Subject: Re: [PATCH v2 4/4] iommu/amd: Enable Host SNP support after enabling
 IOMMU SNP support*

On Wed, Feb 05, 2025, Vasant Hegde wrote:
> On 1/31/2025 7:18 AM, Sean Christopherson wrote:
> > On Fri, Jan 31, 2025, Ashish Kalra wrote:

That doesn't address the case where amd_iommu_prepare() fails, because amd_iommu_snp_en
will be %false (it's init value) and the RMP will be uninitialized, i.e.
CC_ATTR_HOST_SEV_SNP will be incorrectly left set.

And conversely, IMO clearing CC_ATTR_HOST_SEV_SNP after initializing the IOMMU
and RMP is wrong as well.  Such a host is probably hosted regardless, but from
the CPU's perspective, SNP is supported and enabled.

> May be below check is enough?
>

---
