---
title: 'Fix broken SNP support with KVM module built-in'
date: 2025-01-22
last_reply: 2025-01-29
message_count: 15
participants: ['Ashish Kalra', 'Tom Lendacky', 'Vasant Hegde', 'Sean Christopherson']
---

## [1] Ashish Kalra — 2025-01-22

From: Ashish Kalra <ashish.kalra@amd.com>

This patch-set fixes the current SNP host enabling code and effectively SNP
which is broken with respect to the KVM module being built-in.

Essentially SNP host enabling code should be invoked before KVM
initialization, which is currently not the case when KVM is built-in.

SNP host support is enabled in snp_rmptable_init() which is invoked as a
device_initcall(). Here device_initcall() is used as snp_rmptable_init()
expects AMD IOMMU SNP support to be enabled prior to it and the AMD
IOMMU driver enables SNP support after PCI bus enumeration.

The first pre-patch in this patch-set is the AMD IOMMU driver patch
which moves SNP enable check before enabling IOMMUs. With this patch
applied, the final patch in this patch-set calls snp_rmptable_init()
early with subsys_initcall() which then enables SNP host support before
KVM initialization with kvm_amd module built-in. The other two pre-patches
in the patch-set ensure that the dependent PSP SEV driver is initialized
before KVM module if KVM module is built-in.

Fixes: c3b86e61b756 ("x86/cpufeatures: Enable/unmask SEV-SNP CPU feature")

Ashish Kalra (1):
  x86/sev: Fix broken SNP support with KVM module built-in

Sean Christopherson (2):
  crypto: ccp: Add external API interface for PSP module initialization
  KVM: SVM: Ensure PSP module initialized before built-in KVM module

Vasant Hegde (1):
  iommu/amd: Check SNP support before enabling IOMMU

 arch/x86/kvm/svm/sev.c      | 10 ++++++++++
 arch/x86/virt/svm/sev.c     |  2 +-
 drivers/crypto/ccp/sp-dev.c | 12 ++++++++++++
 drivers/crypto/ccp/sp-dev.h |  1 +
 drivers/iommu/amd/init.c    |  3 ++-
 include/linux/psp-sev.h     | 11 +++++++++++
 6 files changed, 37 insertions(+), 2 deletions(-)

---

## [2] Ashish Kalra — 2025-01-22
*Subject: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

From: Vasant Hegde <vasant.hegde@amd.com>

iommu_snp_enable() checks for IOMMU feature support and page table
compatibility. Ideally this check should be done before enabling
IOMMUs. Currently its done after enabling IOMMUs. Also its causes
issue if kvm_amd is builtin.

Hence move SNP enable check before enabling IOMMUs.

Fixes: 04d65a9dbb33 ("iommu/amd: Don't rely on external callers to enable IOMMU SNP support")
Cc: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Vasant Hegde <vasant.hegde@amd.com>
---
 drivers/iommu/amd/init.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index c5cd92edada0..419a0bc8eeea 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -3256,13 +3256,14 @@ static int __init state_next(void)
 		}
 		break;
 	case IOMMU_ACPI_FINISHED:
+		/* SNP enable has to be called after early_amd_iommu_init() */
+		iommu_snp_enable();
 		early_enable_iommus();
 		x86_platform.iommu_shutdown = disable_iommus;
 		init_state = IOMMU_ENABLED;
 		break;
 	case IOMMU_ENABLED:
 		register_syscore_ops(&amd_iommu_syscore_ops);
-		iommu_snp_enable();
 		ret = amd_iommu_init_pci();
 		init_state = ret ? IOMMU_INIT_ERROR : IOMMU_PCI_INIT;
 		break;

---

## [3] Ashish Kalra — 2025-01-22
*Subject: [PATCH 2/4] crypto: ccp: Add external API interface for PSP module initialization*

From: Sean Christopherson <seanjc@google.com>

Add a new external API interface for PSP module initialization which
allows PSP SEV driver to be initialized explicitly before proceeding
with SEV/SNP initialization with KVM if KVM is built-in as the
dependency between modules is not supported/handled by the initcall
infrastructure and the dependent PSP module is not implicitly loaded
before KVM module if KVM module is built-in.

Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 drivers/crypto/ccp/sp-dev.c | 12 ++++++++++++
 drivers/crypto/ccp/sp-dev.h |  1 +
 include/linux/psp-sev.h     | 11 +++++++++++
 3 files changed, 24 insertions(+)

diff --git a/drivers/crypto/ccp/sp-dev.c b/drivers/crypto/ccp/sp-dev.c
index 7eb3e4668286..a0cdc03984cb 100644
--- a/drivers/crypto/ccp/sp-dev.c
+++ b/drivers/crypto/ccp/sp-dev.c
@@ -253,8 +253,12 @@ struct sp_device *sp_get_psp_master_device(void)
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
@@ -263,6 +267,7 @@ static int __init sp_mod_init(void)
 	psp_pci_init();
 #endif
 
+	initialized = true;
 	return 0;
 #endif
 
@@ -279,6 +284,13 @@ static int __init sp_mod_init(void)
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
diff --git a/drivers/crypto/ccp/sp-dev.h b/drivers/crypto/ccp/sp-dev.h
index 6f9d7063257d..3f5f7491bec1 100644
--- a/drivers/crypto/ccp/sp-dev.h
+++ b/drivers/crypto/ccp/sp-dev.h
@@ -148,6 +148,7 @@ int sp_request_psp_irq(struct sp_device *sp, irq_handler_t handler,
 		       const char *name, void *data);
 void sp_free_psp_irq(struct sp_device *sp, void *data);
 struct sp_device *sp_get_psp_master_device(void);
+int __init sev_module_init(void);
 
 #ifdef CONFIG_CRYPTO_DEV_SP_CCP
 
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 903ddfea8585..1cf197fca93d 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -814,6 +814,15 @@ struct sev_data_snp_commit {
 
 #ifdef CONFIG_CRYPTO_DEV_SP_PSP
 
+/**
+ * sev_module_init - perform PSP module initialization
+ *
+ * Returns:
+ * 0 if the PSP module is successfully initialized
+ * -%ENODEV    if the PSP module initialization fails
+ */
+int __init sev_module_init(void);
+
 /**
  * sev_platform_init - perform SEV INIT command
  *
@@ -948,6 +957,8 @@ void snp_free_firmware_page(void *addr);
 
 #else	/* !CONFIG_CRYPTO_DEV_SP_PSP */
 
+static inline int __init sev_module_init(void) { return -ENODEV }
+
 static inline int
 sev_platform_status(struct sev_user_data_status *status, int *error) { return -ENODEV; }

---

## [4] Ashish Kalra — 2025-01-22
*Subject: [PATCH 3/4] KVM: SVM: Ensure PSP module initialized before built-in KVM module*

From: Sean Christopherson <seanjc@google.com>

The kernel's initcall infrastructure lacks the ability to express
dependencies between initcalls, where as the modules infrastructure
automatically handles dependencies via symbol loading. Ensure the
PSP SEV driver is initialized before proceeding in sev_hardware_setup()
if KVM is built-in as the dependency isn't handled by the initcall
infrastructure.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/svm/sev.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 5a13c5224942..de404d493759 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2972,6 +2972,16 @@ void __init sev_hardware_setup(void)
 	    WARN_ON_ONCE(!boot_cpu_has(X86_FEATURE_FLUSHBYASID)))
 		goto out;
 
+	/*
+	 * The kernel's initcall infrastructure lacks the ability to express
+	 * dependencies between initcalls, where as the modules infrastructure
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

## [5] Ashish Kalra — 2025-01-22
*Subject: [PATCH 4/4] x86/sev: Fix broken SNP support with KVM module built-in*

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

With the AMD IOMMU driver patch applied which moves SNP enable check
before enabling IOMMUs, snp_rmptable_init() can now be called early
with subsys_initcall() which enables SNP host support before KVM
initialization with kvm_amd module built-in.

Fixes: c3b86e61b756 ("x86/cpufeatures: Enable/unmask SEV-SNP CPU feature")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/virt/svm/sev.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 1dcc027ec77e..d5dc4889c445 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -571,7 +571,7 @@ static int __init snp_rmptable_init(void)
 /*
  * This must be called after the IOMMU has been initialized.
  */
-device_initcall(snp_rmptable_init);
+subsys_initcall(snp_rmptable_init);
 
 static void set_rmp_segment_info(unsigned int segment_shift)
 {

---

## [6] Tom Lendacky — 2025-01-22
*Subject: Re: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

On 1/21/25 19:00, Ashish Kalra wrote:
> From: Vasant Hegde <vasant.hegde@amd.com>
> 

Why should it be done before enabling the IOMMUs? In other words, at
some more detail here.

> issue if kvm_amd is builtin.
> 

Ashish, as the submitter, this requires your Signed-off-by:.

> ---
>  drivers/iommu/amd/init.c | 3 ++-

This comment doesn't really explain anything, so I think it should
either be improved or just remove it.

Thanks,
Tom

> +		iommu_snp_enable();
>  		early_enable_iommus();

---

## [7] Tom Lendacky — 2025-01-22
*Subject: Re: [PATCH 2/4] crypto: ccp: Add external API interface for PSP
 module initialization*

On 1/21/25 19:00, Ashish Kalra wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

This is big run on sentence. Please start off describing the issue and
why this fixes it.

> 
> Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>

Your SOB should come after Sean's.

> Signed-off-by: Sean Christopherson <seanjc@google.com>
> ---

This definition is within CONFIG_X86, but...

>  	int ret;
>  

Add a blank line.

>  	return 0;
>  #endif

Why is this declared both here and below? Please just have it one place.

>  
>  #ifdef CONFIG_CRYPTO_DEV_SP_CCP

There are more possible return values in the sp_mod_init() path than
just ENODEV. So maybe just say that it returns a negative value on error
unless you want to chase them all down.

> + */
> +int __init sev_module_init(void);

Remove the "__init".

Although I'm not sure this is even needed since it will only be called
by KVM and CONFIG_KVM_AMD_SEV depends on CONFIG_CRYPTO_DEV_SP_PSP. Plus,
the function itself is only defined under a specific config.

Thanks,
Tom

> +
>  static inline int

---

## [8] Tom Lendacky — 2025-01-22
*Subject: Re: [PATCH 3/4] KVM: SVM: Ensure PSP module initialized before
 built-in KVM module*

On 1/21/25 19:00, Ashish Kalra wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

Requires your Signed-off-by:

> ---
>  arch/x86/kvm/svm/sev.c | 10 ++++++++++

s/where as/whereas/

Thanks,
Tom

> +	 * automatically handles dependencies via symbol loading.  Ensure the
> +	 * PSP SEV driver is initialized before proceeding if KVM is built-in,

---

## [9] Tom Lendacky — 2025-01-22
*Subject: Re: [PATCH 4/4] x86/sev: Fix broken SNP support with KVM module
 built-in*

On 1/21/25 19:00, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Should this be the second patch in the series, since the first patch is
what allows the change from device_initcall() to subsys_initcall()?

> 
> SNP host support is enabled in snp_rmptable_init() which is invoked as a

This comment is slightly stale now. Maybe modify it to indicate that the
IOMMU SNP check must have been done.

Thanks,
Tom

>   */
> -device_initcall(snp_rmptable_init);

---

## [10] Vasant Hegde — 2025-01-22
*Subject: Re: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

Hi Tom,


On 1/22/2025 8:52 PM, Tom Lendacky wrote:
> On 1/21/25 19:00, Ashish Kalra wrote:
>> From: Vasant Hegde <vasant.hegde@amd.com>

Sure. Basically IOMMU enable stage checks for SNP support. I will update it.

> 
>> issue if kvm_amd is builtin.

Sure. I will remove it.

-Vasant

---

## [11] Kalra, Ashish — 2025-01-24
*Subject: Re: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

Hello All,

On 1/22/2025 11:07 AM, Vasant Hegde wrote:
> Hi Tom,
> 

We have hit a blocker issue with this patch. 

With discussions with the AMD IOMMU team, here is the AMD IOMMU initialization flow:

IOMMU initialization happens in various stages.

1) Detect IOMMU Presence
   start_kernel() -> mm_core_init() -> mem_init() -> pci_iommu_alloc() -> amd_iommu_detect()
   At this stage memory subsystem is not initialized completely. So we just detect the IOMMU presence.

2) Interrupt Remapping
   During APIC init it checks for IOMMU interrupt remapping. At this stage, we initialize the IOMMU and
   enable the IOMMU.
   start_kernel() -> x86_late_time_init() -> apic_intr_mode_init() -> x86_64_probe_apic() -> 
		enable_IR_x2apic() -> irq_remapping_prepare() -> amd_iommu_prepare()

3) PCI init
   This is done using rootfs_initcall(pci_iommu_init);
   pci_iommu_init() -> amd_iommu_init()
   At this stage we enable the IOMMU interrupt, probe device etc. IOMMU is ready to use.

IOMMU SNP check
  Core IOMMU subsystem init is done during iommu_subsys_init() via subsys_initcall.
  This function does change the DMA mode depending on kernel config.
  Hence, SNP check should be done after subsys_initcall. That's why its done currently during IOMMU PCI init (IOMMU_PCI_INIT stage).
  And for that reason snp_rmptable_init() is currently invoked via device_initcall().
 
The summary is that we cannot move snp_rmptable_init() to subsys_initcall as core IOMMU subsystem gets initialized via subsys_initcall.

As discussed internally, we have 2 possible options to fix this: 

1 ) Similar to calling sp_mod_init() to explicitly initialize the PSP driver, we call snp_rmptable_init() from KVM_AMD if it's built-in. 
    So that we don't need changes to IOMMU driver ... as IOMMU driver does SNP check as part of rootfs_initcall()  (amd_iommu_init())
 
2) Rework it such that  
   Core IOMMU (iommu_subsys_init()) initialized (as currently) via subsys_initcall
   FIX: 
   And then we add a fix to invoke snp_rmptable_init() via a subsys_initcall_sync() (instead of device_initcall()).
   (again as core IOMMU subsystem init is called by subsys_initcall()) 
   --> snp_rmptable_init() will additionally need to call iommu_snp_enable() to check and enable SNP support on the IOMMU.

Issues with option (1): 

Here, snp_rmptable_init() is still invoked via device_initcall() for normal module loading case and i remember Sean had concerns of enabling
host SNP at device_initcall level generally as it is too late, though looking at AMD IOMMU driver initialization flow, i don't think there is
much of a choice here.

One other possibility is moving snp_rmptable_init() call to KVM initialization, but that has issues with PSP driver loading and
initializing before KVM (with module loading case) and that will cause PSP's SEV/SNP init to fail as SNP is not enabled yet.
 
But again that will work when SEV/SNP init will move to KVM module load time where PSP module will be simply be loaded and initialized
before KVM, but will not attempt to do SEV/SNP init.
 
This approach is quite fragile and will need to be tested and needs to work with multiple scenarios and cases as explained above, there is
a good chance of this breaking something.

And that's why option (2) is preferred. 

Issues with option (2): 

How to call iommu_snp_enable() from snp_rmptable_init() ?

We probably can't call iommu_snp_enable() explicitly from snp_rmptable_init() as i remember the last time we proposed this, it was rejected as
maintainers were not in favor of core kernel code calling driver functions, though the AMD IOMMU driver is always built-in ?

Therefore, probably the approach will be something like AMD_IOMMU driver registering some kind of callback interface and that callback is 
invoked via snp_rmptable_init() to check and enable SNP support on the IOMMU. 

Boris, it will be nice to have your feedback/thoughts on this approach/option? 

Looking fwd. to more feedback/thoughts/comments on the above.

Thanks,
Ashish

---

## [12] Sean Christopherson — 2025-01-24
*Subject: Re: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

On Fri, Jan 24, 2025, Ashish Kalra wrote:
> With discussions with the AMD IOMMU team, here is the AMD IOMMU
> initialization flow:

..

> IOMMU SNP check
>   Core IOMMU subsystem init is done during iommu_subsys_init() via

Just explicitly invoke RMP initialization during IOMMU SNP setup.  Pretending
there's no connection when snp_rmptable_init() checks amd_iommu_snp_en and has
a comment saying it needs to come after IOMMU SNP setup is ridiculous.

Compile tested only.

---
From: Sean Christopherson <seanjc@google.com>
Date: Fri, 24 Jan 2025 16:25:58 -0800
Subject: [PATCH] x86/sev: iommu/amd: Explicitly init SNP's RMP table during
 IOMMU SNP setup

Explicitly initialize the RMP table during IOMMU SNP setup, as there is a
hard dependency on the IOMMU being configured first, and dancing around
the dependency with initcall shenanigans and a comment is all kinds of
stupid.

The RMP is blatantly not a device; initializing it via a device_initcall()
is confusing and "works" only because of dumb luck: due to kernel build
order, when the the PSP driver is built-in, its effective device_initcall()
just so happens to be invoked after snp_rmptable_init().

That all falls apart if the order is changed in any way.  E.g. if KVM
is built-in and attempts to access the RMP during its device_initcall(),
chaos ensues.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/sev.h |  1 +
 arch/x86/virt/svm/sev.c    | 25 ++++++++-----------------
 drivers/iommu/amd/init.c   |  7 ++++++-
 3 files changed, 15 insertions(+), 18 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 91f08af31078..30da0fc15923 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -503,6 +503,7 @@ static inline void snp_kexec_begin(void) { }
 
 #ifdef CONFIG_KVM_AMD_SEV
 bool snp_probe_rmptable_info(void);
+int __init snp_rmptable_init(void);
 int snp_lookup_rmpentry(u64 pfn, bool *assigned, int *level);
 void snp_dump_hva_rmpentry(unsigned long address);
 int psmash(u64 pfn);
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 9a6a943d8e41..d932aa21340b 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -189,19 +189,19 @@ void __init snp_fixup_e820_tables(void)
  * described in the SNP_INIT_EX firmware command description in the SNP
  * firmware ABI spec.
  */
-static int __init snp_rmptable_init(void)
+int __init snp_rmptable_init(void)
 {
 	u64 max_rmp_pfn, calc_rmp_sz, rmptable_size, rmp_end, val;
 	void *rmptable_start;
 
-	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
-		return 0;
+	if (WARN_ON_ONCE(!cc_platform_has(CC_ATTR_HOST_SEV_SNP)))
+		return -ENOSYS;
 
-	if (!amd_iommu_snp_en)
-		goto nosnp;
+	if (WARN_ON_ONCE(!amd_iommu_snp_en))
+		return -ENOSYS;
 
 	if (!probed_rmp_size)
-		goto nosnp;
+		return -ENOSYS;
 
 	rmp_end = probed_rmp_base + probed_rmp_size - 1;
 
@@ -218,13 +218,13 @@ static int __init snp_rmptable_init(void)
 	if (calc_rmp_sz > probed_rmp_size) {
 		pr_err("Memory reserved for the RMP table does not cover full system RAM (expected 0x%llx got 0x%llx)\n",
 		       calc_rmp_sz, probed_rmp_size);
-		goto nosnp;
+		return -ENOSYS;
 	}
 
 	rmptable_start = memremap(probed_rmp_base, probed_rmp_size, MEMREMAP_WB);
 	if (!rmptable_start) {
 		pr_err("Failed to map RMP table\n");
-		goto nosnp;
+		return -ENOMEM;
 	}
 
 	/*
@@ -261,17 +261,8 @@ static int __init snp_rmptable_init(void)
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
 static struct rmpentry *get_rmpentry(u64 pfn)
 {
 	if (WARN_ON_ONCE(pfn > rmptable_max_pfn))
diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index 0e0a531042ac..d00530156a72 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -3171,7 +3171,7 @@ static bool __init detect_ivrs(void)
 	return true;
 }
 
-static void iommu_snp_enable(void)
+static __init void iommu_snp_enable(void)
 {
 #ifdef CONFIG_KVM_AMD_SEV
 	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
@@ -3196,6 +3196,11 @@ static void iommu_snp_enable(void)
 		goto disable_snp;
 	}
 
+	if (snp_rmptable_init()) {
+		pr_warn("SNP: RMP initialization failed, SNP cannot be supported.\n");
+		goto disable_snp;
+	}
+
 	pr_info("IOMMU SNP support enabled.\n");
 	return;
 

base-commit: ac80076177131f6e3291737c851a6fe32cc03fd3

---

## [13] Kalra, Ashish — 2025-01-27
*Subject: Re: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

Hello Sean,

On 1/24/2025 6:39 PM, Sean Christopherson wrote:
> On Fri, Jan 24, 2025, Ashish Kalra wrote:
>> With discussions with the AMD IOMMU team, here is the AMD IOMMU

Thanks for the suggestion and the patch, i have tested it works for all cases
and scenarios. I will post the next version of the patch-set based on this
patch.

Ashish

> Compile tested only.
>

---

## [14] Sean Christopherson — 2025-01-27
*Subject: Re: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

On Mon, Jan 27, 2025, Ashish Kalra wrote:
> Hello Sean,
> 

One thing I didn't account for: if IOMMU initialization fails and iommu_snp_enable()
is never reached, CC_ATTR_HOST_SEV_SNP will be left set.

I don't see any great options.  Something like the below might work?  And maybe
keep a device_initcall() in arch/x86/virt/svm/sev.c that sanity checks that SNP
really is fully enabled?  Dunno, hopefully someone has a better idea.

diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index 0e0a531042ac..6d62ee8e0055 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -3295,6 +3295,9 @@ static int __init iommu_go_to_state(enum iommu_init_state state)
                ret = state_next();
        }
 
+       if (ret && !amd_iommu_snp_en)
+               cc_platform_clear(CC_ATTR_HOST_SEV_SNP);
+
        return ret;
 }

---

## [15] Vasant Hegde — 2025-01-29
*Subject: Re: [PATCH 1/4] iommu/amd: Check SNP support before enabling IOMMU*

Hi Sean,


On 1/28/2025 2:42 AM, Sean Christopherson wrote:
> On Mon, Jan 27, 2025, Ashish Kalra wrote:
>> Hello Sean,

We did explore few other options. But I don't see any other better option.

Below code works fine.  But we still need to handle `iommu=off` or
`amd_iommu=off` kernel command line. Below change will take care of this
scenario. Does this looks OK?

----
commit 8e9296346e8f6a0831a5f6076c81a636bf044a41
Author: Vasant Hegde <vasant.hegde@amd.com>
Date:   Wed Jan 29 14:47:04 2025 +0530

    iommu/amd: SNP fix

    Signed-off-by: Vasant Hegde <vasant.hegde@amd.com>

diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index c5cd92edada0..08802316411f 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -3426,18 +3426,24 @@ void __init amd_iommu_detect(void)
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
+	/* Disable SNP if amd_iommu is not enabled */
+	if (cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+		cc_platform_clear(CC_ATTR_HOST_SEV_SNP);
 }

 /****************************************************************************




> keep a device_initcall() in arch/x86/virt/svm/sev.c that sanity checks that SNP
> really is fully enabled?  Dunno, hopefully someone has a better idea.

That will not solve the initial problem this series trying to solve (i. e.
kvm_amd as built and making sure SNP init happens before device_initcall() path).

I think with your patch and above changes it should work fine.

-Vasant


> 
> diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c

---
