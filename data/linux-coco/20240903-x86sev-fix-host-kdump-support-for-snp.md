---
title: 'x86/sev: Fix host kdump support for SNP'
date: 2024-09-03
last_reply: 2024-09-12
message_count: 13
participants: ['Ashish Kalra', 'Sean Christopherson', 'kernel test robot', 'Paolo Bonzini', 'Michael Roth']
---

## [1] Ashish Kalra — 2024-09-03

From: Ashish Kalra <ashish.kalra@amd.com>

With active SNP VMs, SNP_SHUTDOWN_EX invoked during panic notifiers causes
crashkernel boot failure with the following signature:

[  563.497112] sysrq: Trigger a crash
[  563.508415] Kernel panic - not syncing: sysrq triggered crash
[  563.522002] CPU: 10 UID: 0 PID: 4661 Comm: bash Kdump: loaded Not tainted 6.11.0-rc3-next-20240813-snp-host-f2a41ff576cc-dirty #61
[  563.549762] Hardware name: AMD Corporation ETHANOL_X/ETHANOL_X, BIOS RXM100AB 10/17/2022
[  563.566266] Call Trace:
[  563.576430]  <TASK>
[  563.585932]  dump_stack_lvl+0x2b/0x90
[  563.597244]  dump_stack+0x14/0x20
[  563.608141]  panic+0x3b9/0x400
[  563.618801]  ? srso_alias_return_thunk+0x5/0xfbef5
[  563.631271]  sysrq_handle_crash+0x19/0x20
[  563.642696]  __handle_sysrq+0xf9/0x290
[  563.653691]  ? srso_alias_return_thunk+0x5/0xfbef5
[  563.666126]  write_sysrq_trigger+0x60/0x80
...
...
[  564.186804] in panic
[  564.194287] in panic_other_cpus_shutdown
[  564.203674] kexec: in crash_smp_send_stop
[  564.213205] kexec: in kdump_nmi_shootdown_cpus
[  564.224338] Kernel Offset: 0x35a00000 from 0xffffffff81000000 (relocation range: 0xffffffff80000000-0xffffffffbfffffff)
[  564.282209] in snp_shutdown_on_panic after decommission, wbinvd + df_flush required
[  564.462217] ccp 0000:23:00.1: SEV-SNP DF_FLUSH failed with error 14
[  564.676920] kexec: in native_machine_crash_shutdown
early console in extract_kernel
input_data: 0x000000007410d2cc
input_len: 0x0000000000ce98b2
output: 0x0000000071600000
output_len: 0x000000000379eb8c
kernel_total_size: 0x0000000002c30000
needed_size: 0x0000000003800000
trampoline_32bit: 0x0000000000000000

Invalid physical address chosen!

Physical KASLR disabled: no suitable memory region!

Virtual KASLR using RDRAND RDTSC...

Decompressing Linux... Parsing ELF... Performing relocations... done.
Booting the kernel (entry_offset: 0x0000000000000bda).
[    0.000000] Linux version 6.11.0-rc3-next-20240813-snp-host-f2a41ff576cc-dirty (amd@ethanolx7e2ehost) (gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0, GNU ld (GNU Binutils) 2.40) #61 SMP Mon Aug 19 19:59:02 UTC 2024
[    0.000000] Command line: BOOT_IMAGE=/vmlinuz-6.11.0-rc3-next-20240813-snp-host-f2a41ff576cc-dirty root=UUID=4b87a03b-0e78-42ca-a8ad-997e63bba4e0 ro console=tty0 console=ttyS0,115200n8 earlyprintk=ttyS0,115200n8 amd_iommu_dump=1 reset_devices systemd.unit=kdump-tools-dump.service nr_cpus=1 irqpoll nousb elfcorehdr=1916276K
[    0.000000] KERNEL supported cpus:
...
...
[    1.671804] AMD-Vi: Using global IVHD EFR:0x841f77e022094ace, EFR2:0x0
[    1.679835] AMD-Vi: Translation is already enabled - trying to copy translation structures
[    1.689363] AMD-Vi: Copied DEV table from previous kernel.
[    1.864369] AMD-Vi: Completion-Wait loop timed out
[    2.038289] AMD-Vi: Completion-Wait loop timed out
[    2.212215] AMD-Vi: Completion-Wait loop timed out
[    2.386141] AMD-Vi: Completion-Wait loop timed out
[    2.560068] AMD-Vi: Completion-Wait loop timed out
[    2.733997] AMD-Vi: Completion-Wait loop timed out
[    2.907927] AMD-Vi: Completion-Wait loop timed out
[    3.081855] AMD-Vi: Completion-Wait loop timed out
[    3.225500] AMD-Vi: Completion-Wait loop timed out
[    3.231083] ..TIMER: vector=0x30 apic1=0 pin1=2 apic2=-1 pin2=-1
d out
[    3.579592] AMD-Vi: Completion-Wait loop timed out
[    3.753164] AMD-Vi: Completion-Wait loop timed out
[    3.815762] Kernel panic - not syncing: timer doesn't work through Interrupt-remapped IO-APIC
[    3.825347] CPU: 0 UID: 0 PID: 0 Comm: swapper/0 Not tainted 6.11.0-rc3-next-20240813-snp-host-f2a41ff576cc-dirty #61
[    3.837188] Hardware name: AMD Corporation ETHANOL_X/ETHANOL_X, BIOS RXM100AB 10/17/2022
[    3.846215] Call Trace:
[    3.848939]  <TASK>
[    3.851277]  dump_stack_lvl+0x2b/0x90
[    3.855354]  dump_stack+0x14/0x20
[    3.859050]  panic+0x3b9/0x400
[    3.862454]  panic_if_irq_remap+0x21/0x30
[    3.866925]  setup_IO_APIC+0x8aa/0xa50
[    3.871106]  ? __pfx_amd_iommu_enable_faulting+0x10/0x10
[    3.877032]  ? __cpuhp_setup_state+0x5e/0xd0
[    3.881793]  apic_intr_mode_init+0x6a/0xf0
[    3.886360]  x86_late_time_init+0x28/0x40
[    3.890832]  start_kernel+0x6a8/0xb50
[    3.894914]  x86_64_start_reservations+0x1c/0x30
[    3.900064]  x86_64_start_kernel+0xbf/0x110
[    3.904729]  ? setup_ghcb+0x12/0x130
[    3.908716]  common_startup_64+0x13e/0x141
[    3.913283]  </TASK>
[    3.915715] in panic
[    3.918149] in panic_other_cpus_shutdown
[    3.922523] ---[ end Kernel panic - not syncing: timer doesn't work through Interrupt-remapped IO-APIC ]---

This happens as SNP_SHUTDOWN_EX fails when SNP VMs are active as the
firmware checks every encryption-capable ASID to verify that it is
not in use by a guest and a DF_FLUSH is not required. If a DF_FLUSH
is required, the firmware returns DFFLUSH_REQUIRED.

To fix this, added support to do SNP_DECOMMISSION of all active SNP VMs
in the panic notifier before doing SNP_SHUTDOWN_EX, but then
SNP_DECOMMISSION tags all CPUs on which guest has been activated to do
a WBINVD. This causes SNP_DF_FLUSH command failure with the following
flow: SNP_DECOMMISSION -> SNP_SHUTDOWN_EX -> SNP_DF_FLUSH ->
failure with WBINVD_REQUIRED.

When panic notifier is invoked all other CPUs have already been
shutdown, so it is not possible to do a wbinvd_on_all_cpus() after
SNP_DECOMMISSION has been executed. This eventually causes SNP_SHUTDOWN_EX
to fail after SNP_DECOMMISSION.

Adding fix to do SNP_DECOMMISSION and subsequent WBINVD on all CPUs
during NMI shutdown of CPUs as part of disabling virtualization on
all CPUs via cpu_emergency_disable_virtualization ->
svm_emergency_disable().

SNP_DECOMMISSION unbinds the ASID from SNP context and marks the ASID
as unusable and then transitions the SNP guest context page to a
firmware page and SNP_SHUTDOWN_EX transitions all pages associated
with the IOMMU to reclaim state which the hypervisor then transitions
to hypervisor state, all these page state changes are in the RMP
table, so there is no loss of guest data as such and the complete
host memory is captured with the crashkernel boot. There are no
processes which are being killed and host/guest memory is not
being altered or modified in any way.

This fixes and enables crashkernel/kdump on SNP host.

v2:
- rename all instances of decommision to decommission
- created a new function sev_emergency_disable() which is exported from 
sev.c and calls __snp_decommission_all() to do SNP_DECOMMISSION
- added more information to commit message

Fixes: c3b86e61b756 ("x86/cpufeatures: Enable/unmask SEV-SNP CPU feature")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 133 +++++++++++++++++++++++++++++++++++++++++
 arch/x86/kvm/svm/svm.c |   2 +
 arch/x86/kvm/svm/svm.h |   3 +-
 3 files changed, 137 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 714c517dd4b7..30f286a3afb0 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -16,6 +16,7 @@
 #include <linux/psp-sev.h>
 #include <linux/pagemap.h>
 #include <linux/swap.h>
+#include <linux/delay.h>
 #include <linux/misc_cgroup.h>
 #include <linux/processor.h>
 #include <linux/trace_events.h>
@@ -89,6 +90,8 @@ static unsigned int nr_asids;
 static unsigned long *sev_asid_bitmap;
 static unsigned long *sev_reclaim_asid_bitmap;
 
+static DEFINE_SPINLOCK(snp_decommission_lock);
+static void **snp_asid_to_gctx_pages_map;
 static int snp_decommission_context(struct kvm *kvm);
 
 struct enc_region {
@@ -2248,6 +2251,9 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 		goto e_free_context;
 	}
 
+	if (snp_asid_to_gctx_pages_map)
+		snp_asid_to_gctx_pages_map[sev_get_asid(kvm)] = sev->snp_context;
+
 	return 0;
 
 e_free_context:
@@ -2884,9 +2890,126 @@ static int snp_decommission_context(struct kvm *kvm)
 	snp_free_firmware_page(sev->snp_context);
 	sev->snp_context = NULL;
 
+	if (snp_asid_to_gctx_pages_map)
+		snp_asid_to_gctx_pages_map[sev_get_asid(kvm)] = NULL;
+
 	return 0;
 }
 
+static void __snp_decommission_all(void)
+{
+	struct sev_data_snp_addr data = {};
+	int ret, asid;
+
+	if (!snp_asid_to_gctx_pages_map)
+		return;
+
+	for (asid = 1; asid < min_sev_asid; asid++) {
+		if (snp_asid_to_gctx_pages_map[asid]) {
+			data.address = __sme_pa(snp_asid_to_gctx_pages_map[asid]);
+			ret = sev_do_cmd(SEV_CMD_SNP_DECOMMISSION, &data, NULL);
+			if (!ret) {
+				snp_free_firmware_page(snp_asid_to_gctx_pages_map[asid]);
+				snp_asid_to_gctx_pages_map[asid] = NULL;
+			}
+		}
+	}
+}
+
+/*
+ * NOTE: called in NMI context from svm_emergency_disable().
+ */
+void sev_emergency_disable(void)
+{
+	static atomic_t waiting_for_cpus_synchronized;
+	static bool synchronize_cpus_initiated;
+	static bool snp_decommission_handled;
+	static atomic_t cpus_synchronized;
+
+	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+		return;
+
+	/*
+	 * SNP_SHUTDOWN_EX fails when SNP VMs are active as the firmware checks
+	 * every encryption-capable ASID to verify that it is not in use by a
+	 * guest and a DF_FLUSH is not required. If a DF_FLUSH is required,
+	 * the firmware returns DFFLUSH_REQUIRED. To address this, SNP_DECOMMISSION
+	 * is required to shutdown all active SNP VMs, but SNP_DECOMMISSION tags all
+	 * CPUs that guest was activated on to do a WBINVD. When panic notifier
+	 * is invoked all other CPUs have already been shutdown, so it is not
+	 * possible to do a wbinvd_on_all_cpus() after SNP_DECOMMISSION has been
+	 * executed. This eventually causes SNP_SHUTDOWN_EX to fail after
+	 * SNP_DECOMMISSION. To fix this, do SNP_DECOMMISSION and subsequent WBINVD
+	 * on all CPUs during NMI shutdown of CPUs as part of disabling
+	 * virtualization on all CPUs via cpu_emergency_disable_virtualization().
+	 */
+
+	spin_lock(&snp_decommission_lock);
+
+	/*
+	 * exit early for call from native_machine_crash_shutdown()
+	 * as SNP_DECOMMISSION has already been done as part of
+	 * NMI shutdown of the CPUs.
+	 */
+	if (snp_decommission_handled) {
+		spin_unlock(&snp_decommission_lock);
+		return;
+	}
+
+	/*
+	 * Synchronize all CPUs handling NMI before issuing
+	 * SNP_DECOMMISSION.
+	 */
+	if (!synchronize_cpus_initiated) {
+		/*
+		 * one CPU handling panic, the other CPU is initiator for
+		 * CPU synchronization.
+		 */
+		atomic_set(&waiting_for_cpus_synchronized, num_online_cpus() - 2);
+		synchronize_cpus_initiated = true;
+		/*
+		 * Ensure CPU synchronization parameters are setup before dropping
+		 * the lock to let other CPUs continue to reach synchronization.
+		 */
+		wmb();
+
+		spin_unlock(&snp_decommission_lock);
+
+		/*
+		 * This will not cause system to hang forever as the CPU
+		 * handling panic waits for maximum one second for
+		 * other CPUs to stop in nmi_shootdown_cpus().
+		 */
+		while (atomic_read(&waiting_for_cpus_synchronized) > 0)
+		       mdelay(1);
+
+		/* Reacquire the lock once CPUs are synchronized */
+		spin_lock(&snp_decommission_lock);
+
+		atomic_set(&cpus_synchronized, 1);
+	} else {
+		atomic_dec(&waiting_for_cpus_synchronized);
+		/*
+		 * drop the lock to let other CPUs contiune to reach
+		 * synchronization.
+		 */
+		spin_unlock(&snp_decommission_lock);
+
+		while (atomic_read(&cpus_synchronized) == 0)
+		       mdelay(1);
+
+		/* Try to re-acquire lock after CPUs are synchronized */
+		spin_lock(&snp_decommission_lock);
+	}
+
+	if (!snp_decommission_handled) {
+		__snp_decommission_all();
+		snp_decommission_handled = true;
+	}
+	spin_unlock(&snp_decommission_lock);
+	wbinvd();
+}
+
 void sev_vm_destroy(struct kvm *kvm)
 {
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
@@ -3052,6 +3175,13 @@ void __init sev_hardware_setup(void)
 	sev_es_supported = true;
 	sev_snp_supported = sev_snp_enabled && cc_platform_has(CC_ATTR_HOST_SEV_SNP);
 
+	if (sev_snp_supported) {
+		snp_asid_to_gctx_pages_map = kmalloc_array(min_sev_asid,
+							   sizeof(void *),
+							   GFP_KERNEL | __GFP_ZERO);
+		if (!snp_asid_to_gctx_pages_map)
+			pr_warn("Could not allocate SNP asid to guest context map\n");
+	}
 out:
 	if (boot_cpu_has(X86_FEATURE_SEV))
 		pr_info("SEV %s (ASIDs %u - %u)\n",
@@ -3094,6 +3224,9 @@ void sev_hardware_unsetup(void)
 
 	misc_cg_set_capacity(MISC_CG_RES_SEV, 0);
 	misc_cg_set_capacity(MISC_CG_RES_SEV_ES, 0);
+
+	kfree(snp_asid_to_gctx_pages_map);
+	snp_asid_to_gctx_pages_map = NULL;
 }
 
 int sev_cpu_init(struct svm_cpu_data *sd)
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index ecf4303422ed..899f4481107c 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -597,6 +597,8 @@ static void svm_emergency_disable(void)
 	kvm_rebooting = true;
 
 	kvm_cpu_svm_disable();
+
+	sev_emergency_disable();
 }
 
 static void svm_hardware_disable(void)
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 43fa6a16eb19..644101327c19 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -763,6 +763,7 @@ void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu);
 int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 void sev_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn);
+void sev_emergency_disable(void);
 #else
 static inline struct page *snp_safe_alloc_page_node(int node, gfp_t gfp)
 {
@@ -793,7 +794,7 @@ static inline int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn)
 {
 	return 0;
 }
-
+static void sev_emergency_disable(void) {}
 #endif
 
 /* vmenter.S */

---

## [2] Sean Christopherson — 2024-09-03
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

On Tue, Sep 03, 2024, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> [    1.671804] AMD-Vi: Using global IVHD EFR:0x841f77e022094ace, EFR2:0x0

Exactly what happens?  I.e. why does the PSP (sorry, ASP) need to be full shutdown
in order to get a kdump?  The changelogs for the original SNP panic/kdump support
are frustratingly unhelpful.  They all describe what the patch does, but say
nothing about _why_.

> when SNP VMs are active as the firmware checks every encryption-capable ASID
> to verify that it is not in use by a guest and a DF_FLUSH is not required. If

...

> diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
> index 714c517dd4b7..30f286a3afb0 100644

NULL pointer deref if this races with snp_decommission_context() from task
context.

> +			ret = sev_do_cmd(SEV_CMD_SNP_DECOMMISSION, &data, NULL);
> +			if (!ret) {

And what happens if SEV_CMD_SNP_DECOMMISSION fails?

> +				snp_free_firmware_page(snp_asid_to_gctx_pages_map[asid]);
> +				snp_asid_to_gctx_pages_map[asid] = NULL;

Define "active".

> +	 * every encryption-capable ASID to verify that it is not in use by a
> +	 * guest and a DF_FLUSH is not required. If a DF_FLUSH is required,

And what happens when num_online_cpus() == 1?

> +		synchronize_cpus_initiated = true;
> +		/*

Yeah, no.  This is horrific.  If the panic path doesn't provide the necessary
infrastructure to ensure the necessary ordering between the initiating CPU and
responding CPUs, then rework the panic path.

---

## [3] Kalra, Ashish — 2024-09-03
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hello Sean,

On 9/3/2024 2:52 PM, Sean Christopherson wrote:
> On Tue, Sep 03, 2024, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

If SNP_SHUTDOWN_EX is not issued, or more accurately if SNP_SHUTDOWN_EX is not issued with IOMMU_SNP_SHUTDOWN set to 1, i.e, to disable SNP enforcement by IOMMU, then IOMMUs are initialized in an IRQ remapping configuration by early_enable_iommus() during crashkernel boot, which causes the above crash in check_timer().

Also, SNP_SHUTDOWN_EX is required to tear down the RMP CPU/IOMMU TMRs.

Additionally, if IOMMU SNP_SHUTDOWN is not done and all pages associated with the IOMMU are not transitioned to Reclaim state (and then subsequently by HV to hypervisor state) there is a really high probability of a fatal RMP page fault due to collision with a new page allocation during kexec boot due to collision with one of these IOMMU pages.

So we really need SNP_SHUTDOWN_EX with IOMMU_SNP_SHUTDOWN=1 for kexec/crashkernel boot.

>
>> when SNP VMs are active as the firmware checks every encryption-capable ASID

Yes this race needs to be handled.

I am looking at if i can do SNP_DECOMMISSION on all (SNP) ASIDs, and continue with the loop if SNP_DECOMMISSION fails with INVALID_GUEST error as the guest has already been decommissioned via snp_decommission_context().

>> +			ret = sev_do_cmd(SEV_CMD_SNP_DECOMMISSION, &data, NULL);
>> +			if (!ret) {

As mentioned above, will add additional handling for cases where INVALID_GUEST kind of errors are returned.

But, if errors like UPDATE_FAILED are returned, this will eventually cause SNP_SHUTDOWN failure and then lead to crashkernel boot failure as discussed above.

>
>> +				snp_free_firmware_page(snp_asid_to_gctx_pages_map[asid]);
Yes, will add fix for that.
>> +		synchronize_cpus_initiated = true;
>> +		/*

The issue here is that panic path will ensure that all (other) CPUs have been shutdown via NMI by checking that they have executed the NMI shutdown callback.

But the above synchronization is specifically required for SNP case, as we don't want to execute the SNP_DECOMMISSION command (to destroy SNP guest context) while one or more CPUs are still in the NMI VMEXIT path and still in the process of saving the vCPU state (and still modifying SNP guest context?) during this VMEXIT path. Therefore, we ensure that all the CPUs have saved the vCPU state and entered NMI context before issuing SNP_DECOMMISSION. The point is that this is a specific SNP requirement (and that's why this specific handling in sev_emergency_disable()) and i don't know how we will be able to enforce it in the generic panic path ?

Thanks, Ashish

---

## [4] kernel test robot — 2024-09-04
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hi Ashish,

kernel test robot noticed the following build warnings:

[auto build test WARNING on kvm/queue]
[also build test WARNING on linus/master v6.11-rc6 next-20240904]
[cannot apply to kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Ashish-Kalra/x86-sev-Fix-host-kdump-support-for-SNP/20240904-031215
base:   https://git.kernel.org/pub/scm/virt/kvm/kvm.git queue
patch link:    https://lore.kernel.org/r/20240903191033.28365-1-Ashish.Kalra%40amd.com
patch subject: [PATCH v2] x86/sev: Fix host kdump support for SNP
config: x86_64-randconfig-r073-20240904 (https://download.01.org/0day-ci/archive/20240904/202409041737.FSl6a7vH-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20240904/202409041737.FSl6a7vH-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202409041737.FSl6a7vH-lkp@intel.com/

All warnings (new ones prefixed by >>):

   In file included from arch/x86/kvm/kvm-asm-offsets.c:11:
>> arch/x86/kvm/svm/svm.h:783:13: warning: 'sev_emergency_disable' defined but not used [-Wunused-function]
     783 | static void sev_emergency_disable(void) {}
         |             ^~~~~~~~~~~~~~~~~~~~~


vim +/sev_emergency_disable +783 arch/x86/kvm/svm/svm.h

   763	
   764	static inline void sev_free_vcpu(struct kvm_vcpu *vcpu) {}
   765	static inline void sev_vm_destroy(struct kvm *kvm) {}
   766	static inline void __init sev_set_cpu_caps(void) {}
   767	static inline void __init sev_hardware_setup(void) {}
   768	static inline void sev_hardware_unsetup(void) {}
   769	static inline int sev_cpu_init(struct svm_cpu_data *sd) { return 0; }
   770	static inline int sev_dev_get_attr(u32 group, u64 attr, u64 *val) { return -ENXIO; }
   771	#define max_sev_asid 0
   772	static inline void sev_handle_rmp_fault(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code) {}
   773	static inline void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu) {}
   774	static inline int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order)
   775	{
   776		return 0;
   777	}
   778	static inline void sev_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end) {}
   779	static inline int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn)
   780	{
   781		return 0;
   782	}
 > 783	static void sev_emergency_disable(void) {}
   784	#endif
   785

---

## [5] Paolo Bonzini — 2024-09-04
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

On 9/4/24 00:58, Kalra, Ashish wrote:
> The issue here is that panic path will ensure that all (other) CPUs
> have been shutdown via NMI by checking that they have executed the

I think a simple way to do this is to _first_ kick out other
CPUs through NMI, and then the one that is executing
emergency_reboot_disable_virtualization().  This also makes
emergency_reboot_disable_virtualization() and
native_machine_crash_shutdown() more similar, in that
the latter already stops other CPUs before disabling
virtualization on the one that orchestrates the shutdown.

Something like (incomplete, it has to also add the bool argument
to cpu_emergency_virt_callback and the actual callbacks):

diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index 340af8155658..3df25fbe969d 100644
--- a/arch/x86/kernel/crash.c
+++ b/arch/x86/kernel/crash.c
@@ -111,7 +111,7 @@ void native_machine_crash_shutdown(struct pt_regs *regs)
  
  	crash_smp_send_stop();
  
-	cpu_emergency_disable_virtualization();
+	cpu_emergency_disable_virtualization(true);
  
  	/*
  	 * Disable Intel PT to stop its logging
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index 0e0a4cf6b5eb..7a86ec786987 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -558,7 +558,7 @@ EXPORT_SYMBOL_GPL(cpu_emergency_unregister_virt_callback);
   * reboot.  VMX blocks INIT if the CPU is post-VMXON, and SVM blocks INIT if
   * GIF=0, i.e. if the crash occurred between CLGI and STGI.
   */
-void cpu_emergency_disable_virtualization(void)
+void cpu_emergency_disable_virtualization(bool last)
  {
  	cpu_emergency_virt_cb *callback;
  
@@ -572,7 +572,7 @@ void cpu_emergency_disable_virtualization(void)
  	rcu_read_lock();
  	callback = rcu_dereference(cpu_emergency_virt_callback);
  	if (callback)
-		callback();
+		callback(last);
  	rcu_read_unlock();
  }
  
@@ -591,11 +591,11 @@ static void emergency_reboot_disable_virtualization(void)
  	 * other CPUs may have virtualization enabled.
  	 */
  	if (rcu_access_pointer(cpu_emergency_virt_callback)) {
-		/* Safely force _this_ CPU out of VMX/SVM operation. */
-		cpu_emergency_disable_virtualization();
-
  		/* Disable VMX/SVM and halt on other CPUs. */
  		nmi_shootdown_cpus_on_restart();
+
+		/* Safely force _this_ CPU out of VMX/SVM operation. */
+		cpu_emergency_disable_virtualization(true);
  	}
  }
  #else
@@ -877,7 +877,7 @@ static int crash_nmi_callback(unsigned int val, struct pt_regs *regs)
  	 * Prepare the CPU for reboot _after_ invoking the callback so that the
  	 * callback can safely use virtualization instructions, e.g. VMCLEAR.
  	 */
-	cpu_emergency_disable_virtualization();
+	cpu_emergency_disable_virtualization(false);
  
  	atomic_dec(&waiting_for_crash_ipi);
  
diff --git a/arch/x86/kernel/smp.c b/arch/x86/kernel/smp.c
index 18266cc3d98c..9a863348d1a7 100644
--- a/arch/x86/kernel/smp.c
+++ b/arch/x86/kernel/smp.c
@@ -124,7 +124,7 @@ static int smp_stop_nmi_callback(unsigned int val, struct pt_regs *regs)
  	if (raw_smp_processor_id() == atomic_read(&stopping_cpu))
  		return NMI_HANDLED;
  
-	cpu_emergency_disable_virtualization();
+	cpu_emergency_disable_virtualization(false);
  	stop_this_cpu(NULL);
  
  	return NMI_HANDLED;
@@ -136,7 +136,7 @@ static int smp_stop_nmi_callback(unsigned int val, struct pt_regs *regs)
  DEFINE_IDTENTRY_SYSVEC(sysvec_reboot)
  {
  	apic_eoi();
-	cpu_emergency_disable_virtualization();
+	cpu_emergency_disable_virtualization(false);
  	stop_this_cpu(NULL);
  }
  

And then a second patch adds sev_emergency_disable() and only
executes it if last == true.

Paolo

---

## [6] Kalra, Ashish — 2024-09-04
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hello Paolo,

On 9/4/2024 5:29 AM, Paolo Bonzini wrote:
> On 9/4/24 00:58, Kalra, Ashish wrote:
>> The issue here is that panic path will ensure that all (other) CPUs
This implementation will not work as we need to do wbinvd on all other CPUs after SNP_DECOMMISSION has been issued.

When the last CPU executes sev_emergency_disable() and issues SNP_DECOMMISSION, by that time all other CPUs have entered the NMI halt loop and then they won't be able to do a wbinvd and hence SNP_SHUTDOWN will eventually fail.

One way this can work is if all other CPUs can still execute sev_emergency_disable() and in case of last == false, do a spin busy till the last cpu kicks them out of the spin loop and then they do a wbinvd after exiting the spin busy, but then cpu_emergency_disable_virtualization() is/has to be called before atomic_dec(&waiting_for_crash_ipi) in crash_nmi_callback(), so this spin busy in other CPUs will force the last CPU to wait forever (or till it times out waiting for all other CPUs to execute the NMI callback) which makes all of this looks quite fragile.

Thanks, Ashish

---

## [7] Kalra, Ashish — 2024-09-04
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hello Sean,

>>>  e_free_context:
>>> @@ -2884,9 +2890,126 @@ static int snp_decommission_context(struct kvm *kvm)

Actually looking at this again, this is why we really need all CPUs synchronizing in NMI context before one CPU in NMI context takes control and issues SNP_DECOMMISSION on all SNP VMs.

If there are sev_vm_destroy() -> snp_decommision_context() executing,  when they start handling NMI they would have either already issued SNP_DECOMMISSION for this VM and/or reclaimed the SNP guest context page (transitioned to FW state after SNP_DECOMMISSION). In both cases when we issue SNP_DECOMMISSION here in __snp_decommission_all(), the command will fail with INVALID_GUEST/INVALID_ADDRESS error, so we can simply ignore this error and assume that the VM has already been decommissioned and continue with decommissioning the other VMs.

I actually tested some of these scenarios and they work as above.

>>> +			ret = sev_do_cmd(SEV_CMD_SNP_DECOMMISSION, &data, NULL);
>>> +			if (!ret) {

As mentioned above, we can ignore the failure here as the VM may have already been decommissioned.

In the case where SNP_DECOMMISSION fails without the VM being already decommissioned, crashkernel boot will fail.

Thanks, Ashish

---

## [8] Michael Roth — 2024-09-04
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

On Wed, Sep 04, 2024 at 12:37:17PM -0500, Kalra, Ashish wrote:
> Hello Paolo,
> 

Hi Ashish,

Your patch (and Paolo's suggested rework) came up in the PUCK call this
morning and I mentioned this point. I was asked to raise some of the
points here so we can continue the discussion on-list:

Have we confirmed that WBINVD actually has to happen after the
SNP_DECOMISSION call? Or do we just need to ensure that the WBINVD was
issued after the last VMEXIT, and that the guest will never VMENTER
again after the WBINVD?

Because if WBINVD can be done prior to SNP_DECOMISSION, then Paolo was
suggesting we could just have:

  kvm_cpu_svm_disable() {
    ...
    WBINVD
  }

  cpu_emergency_disable_virtualization() {
    kvm_cpu_svm_disable()
  }

  smp_stop_nmi_callback() {
    if (raw_smp_processor_id() == atomic_read(&stopping_cpu)) {
      return NMI_HANDLED;
    }
    cpu_emergency_disable_virtualization()
    return NMI_HANDLED
  }


The panic'ing CPU can then:

  1) WBINVD itself (e.g. via cpu_emergency_disable_virtualization())
  2) issue SNP_DECOMMISSION for all ASIDs

That would avoid much of the additional synchronization handling since it
fits more cleanly into existing panic flow. But it's contingent on
whether WBINVD can happen before SNP_DECOMMISION or not so need to
confirm that.

Sean and Paolo also raised some other points (feel free to add if I
missed anything):

  - Since there's a lot of high-level design aspects that need to be
    accounted for, it would be good to have the patch have some sort of
    pseudocode/graph/etc so it's easier to reason about different
    approaches. It would also be good to include this in the commit
    message (generally it's encouraged to describe "why" rather than "how",
    but this is an exceptional case where both are useful to reader).

  - Sean inquired about making the target kdump kernel more agnostic to
    whether or not SNP_SHUTDOWN was done properly, since that might
    allow for capturing state even for edge cases where we can't go
    through the normal cleanup path. I mentioned we'd tried this to some
    degree but hit issues with the IOMMU, and when working around that
    there was another issue but I don't quite recall the specifics.
    Can you post a quick recap of what the issues are with that approach
    so we can determine whether or not this is still an option?

-Mike

> 
> Thanks, Ashish

---

## [9] Kalra, Ashish — 2024-09-04
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hello Mike,

On 9/4/2024 2:54 PM, Michael Roth wrote:
> On Wed, Sep 04, 2024 at 12:37:17PM -0500, Kalra, Ashish wrote:
>> Hello Paolo,

Something similar is already happening in crash_nmi_callback() :

static int crash_nmi_callback(unsigned int val, struct pt_regs *regs)
{
        ...
        if (shootdown_callback)
                shootdown_callback(cpu, regs);

        cpu_emergency_disable_virtualization();

        ...

shootdown_callback() -> kdump_nmi_callback() -> kdump_sev_callback() - > WBINVD

and that does not help and still causes SNP_SHUTDOWN_EX to fail after SNP_DECOMMISSION with DFFLUSH_REQUIRED error and then subsequently issuing DF_FLUSH command after SNP_SHUTDOWN failing with WBINVD_REQUIRED error.

>
>   smp_stop_nmi_callback() {

No, WBINVD needs to happen after SNP_DECOMMISSION has been issued, followed by a DF_FLUSH for SNP_SHUTDOWN_EX to succeed.

from the SNP FW ABI specs for SNP_DECOMMISSION command:

The firmware marks the ASID of the guest as not runnable. Then the firmware records that each CPU core on each of the CCXs that the guest was activated on requires a WBINVD followed by a single DF_FLUSH command to ensure that all unencrypted data in the caches are invalidated before reusing the ASID.

and from the SNP FW ABI specs for SNP_DF_FLUSH command:

8.13     SNP_DF_FLUSH command:

8.13.2     Actions

For each core marked for cache invalidation, the firmware checks that the core has executed a WBINVD instruction. If not, the firmware returns WBINVD_REQUIRED. The commands that mark cores for cache invalidation include SNP_DECOMMISSION ...

I understand this Actions section as saying WBINVD and DF_FLUSH would have to be after the decommission.

> Sean and Paolo also raised some other points (feel free to add if I
> missed anything):

Yes, i believe without SNP_SHUTDOWN, early_enable_iommus() configure the IOMMUs into an IRQ remapping configuration causing the crash in io_apic.c::check_timer().

It looks like in this case, we enable IRQ remapping configuration *earlier* than when it needs to be enabled and which causes the panic as indicated:

EMERGENCY [    1.376701] Kernel panic - not syncing: timer doesn't work through Interrupt-remapped IO-APIC


Next, we tried with amd_iommu=off, with that we don't get the irq remapping panic during crashkernel boot, but boot still hangs before starting kdump tools.

So eventually we discovered that irqremapping is required for x2apic and with amd_iommu=off we don't enable irqremapping at all.

And without irqremapping enabled, NVMe is not being detected and RootFS not getting mounted (during crashkernel boot):

...

[   67.902284] nvme nvme0: I/O tag 8 (0008) QID 0 timeout, disable controller
[   67.915403] nvme nvme1: I/O tag 12 (000c) QID 0 timeout, disable controller
[   67.928880] nvme nvme0: Identify Controller failed (-4)
[   67.940465] nvme nvme1: Identify Controller failed (-4)
[   67.951758] nvme 0000:41:00.0: probe with driver nvme failed with error -5
[   67.964865] nvme 0000:01:00.0: probe with driver nvme failed with error -5

...

Gave up waiting for root file system device.

...

Thanks, Ashish

---

## [10] Sean Christopherson — 2024-09-04
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

On Wed, Sep 04, 2024, Ashish Kalra wrote:
> On 9/4/2024 2:54 PM, Michael Roth wrote:
> >   - Sean inquired about making the target kdump kernel more agnostic to

I assume the problem is that IOMMU setup fails in the kdump kernel, not that it
does the setup earlier.  That's that part I want to understand.

Based on the SNP ABI:

  The firmware initializes the IOMMU to perform RMP enforcement. The firmware also
  transitions the event log, PPR log, and completion wait buffers of the IOMMU to
  an RMP page state that is read only to the hypervisor and cannot be assigned to
  guests.

and commit f366a8dac1b8 ("iommu/amd: Clean up RMP entries for IOMMU pages during
SNP shutdown"), my understanding is that the pages used for the IOMMU logs are
forced to read-only for the IOMMU, and so attempting to access those pages in the
kdump kernel will result in an RMP #PF.

That's quite unfortunate, as it means my idea of eating RMP #PFs doesn't really
work, because that idea is based on the assumption that only guest private memory
would generate unexpected RMP #PFs  :-(

> Next, we tried with amd_iommu=off, with that we don't get the irq remapping
> panic during crashkernel boot, but boot still hangs before starting kdump

Yeah, that makes sense, as does failing to boot if the system isn't configured
properly, i.e. can't send interrupts to all CPUs.

---

## [11] Ashish Kalra — 2024-09-06
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hello Sean,

On 9/4/2024 5:23 PM, Sean Christopherson wrote:
> On Wed, Sep 04, 2024, Ashish Kalra wrote:
>> On 9/4/2024 2:54 PM, Michael Roth wrote:

Here is a deeper understanding of this issue:

It looks like this is happening: when we do SNP_SHUTDOWN without IOMMU_SNP_SHUTDOWN during panic, kdump boot runs with iommu snp 
enforcement still enabled and IOMMU completion wait buffers (cwb) still locked and exclusivity still setup on those, and then in 
kdump boot, we allocate new iommu completion wait buffers and try to use them, but we get a iommu command completion wait time-out,
due to the locked in (prev) completion wait buffers, the newly allocated completion wait buffers are not getting used for iommu 
command execution and completion indication :

[    1.711588] AMD-Vi: early_amd_iommu_init: irq remaping enabled
[    1.718972] AMD-Vi: in early_enable_iommus
[    1.723543] AMD-Vi: Translation is already enabled - trying to copy translation structures
[    1.733333] AMD-Vi: Copied DEV table from previous kernel.
[    1.739566] CPU: 0 UID: 0 PID: 0 Comm: swapper/0 Not tainted 6.11.0-rc6-next-20240903-snp-host-f2a41ff576cc+ #78
[    1.750920] Hardware name: AMD Corporation ETHANOL_X/ETHANOL_X, BIOS RXM100AB 10/17/2022
[    1.759950] Call Trace:
[    1.762677]  <TASK>
[    1.765018]  dump_stack_lvl+0x70/0x90
[    1.769109]  dump_stack+0x14/0x20
[    1.772809]  iommu_completion_wait.part.0.isra.0+0x38/0x140
[    1.779035]  amd_iommu_flush_all_caches+0xa3/0x240
[    1.784383]  ? memcpy_toio+0x25/0xc0
[    1.788372]  early_enable_iommus+0x151/0x880
[    1.793140]  state_next+0xe67/0x22b0
[    1.797130]  ? __raw_callee_save___native_queued_spin_unlock+0x19/0x30
[    1.804421]  amd_iommu_enable+0x24/0x60
[    1.808702]  irq_remapping_enable+0x1f/0x50
[    1.813371]  enable_IR_x2apic+0x155/0x260
[    1.817848]  x86_64_probe_apic+0x13/0x70
[    1.822226]  apic_intr_mode_init+0x39/0xf0
[    1.826799]  x86_late_time_init+0x28/0x40
[    1.831266]  start_kernel+0x6ad/0xb50
[    1.835436]  x86_64_start_reservations+0x1c/0x30
[    1.840591]  x86_64_start_kernel+0xbf/0x110
[    1.845256]  ? setup_ghcb+0x12/0x130
[    1.849247]  common_startup_64+0x13e/0x141
[    1.853821]  </TASK>
[    2.077901] AMD-Vi: Completion-Wait loop timed out
...

And because of this the iommu command, in this case which is for enabling irq remapping does not succeed and that eventually causes 
timer to fail without irq remapping support enabled.

Once IOMMU SNP support is enabled, to enforce RMP enforcement the IOMMU completion wait buffers are setup as read-only and 
exclusivity set on these and additionally the IOMMU registers used to mark the exclusivity on the store addresses associated with 
these CWB is also locked. This enforcement of SNP in the IOMMU is only disabled with the IOMMU_SNP_SHUTDOWN parameter with 
SNP_SHUTDOWN_EX command.

From the AMD IOMMU specifications:

2.12.2.2 SEV-SNP COMPLETION_WAIT Store Restrictions On systems that are SNP-enabled, the store address associated with any host 
COMPLETION_WAIT command (s=1) is restricted. The Store Address must fall within the address range specified by the Completion Store 
Base and Completion Store Limit registers. When the system is SNP-enabled, the memory within this range will be marked in the RMP 
using a special immutable state by the PSP. This memory region will be readable by the CPU but not writable.

2.12.2.3 SEV-SNP Exclusion Range Restrictions The exclusion range feature is not supported on systems that are SNP-enabled. 
Additionally, the Exclusion Base and Exclusion Range Limit registers are re-purposed to act as the Completion Store Base and Limit 
registers.

Therefore, we need to disable IOMMU SNP enforcement with SNP_SHUTDOWN_EX command before the kdump kernel starts booting as we can't 
setup IOMMU CWB again in kdump as SEV-SNP exclusion base and range limit registers are locked as IOMMU SNP support is still enabled.

I tried to use the previous kernel's CWB (cmd_sem) as below: 

static int __init alloc_cwwb_sem(struct amd_iommu *iommu)
{
        if (!is_kdump_kernel())
                iommu->cmd_sem = iommu_alloc_4k_pages(iommu, GFP_KERNEL, 1);
        else {
                if (check_feature(FEATURE_SNP)) {
                        u64 cwwb_sem_paddr;

                        cwwb_sem_paddr = readq(iommu->mmio_base + MMIO_EXCL_BASE_OFFSET);
                        iommu->cmd_sem = iommu_phys_to_virt(cwwb_sem_paddr);
        		return iommu->cmd_sem ? 0 : -ENOMEM;
                }
        }

        return iommu->cmd_sem ? 0 : -ENOMEM;
}

I tried this, but this fails as i believe the kdump kernel will not have these previous kernel's allocated IOMMU CWB in the kernel 
direct map : 

[    1.708959] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.714327] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x100805000, cmd_sem_vaddr 0xffff9f5340805000
[    1.726309] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.731676] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x1050051000, cmd_sem_vaddr 0xffff9f6290051000
[    1.743742] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.749109] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x1050052000, cmd_sem_vaddr 0xffff9f6290052000
[    1.761177] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.766542] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x100808000, cmd_sem_vaddr 0xffff9f5340808000
[    1.778509] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.783877] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x1050053000, cmd_sem_vaddr 0xffff9f6290053000
[    1.795942] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.801300] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x100809000, cmd_sem_vaddr 0xffff9f5340809000
[    1.813268] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.818636] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x1050054000, cmd_sem_vaddr 0xffff9f6290054000
[    1.830701] AMD-Vi: in alloc_cwwb_sem kdump kernel
[    1.836069] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x10080a000, cmd_sem_vaddr 0xffff9f534080a000
[    1.848039] AMD-Vi: early_amd_iommu_init: irq remaping enabled
[    1.855431] AMD-Vi: in early_enable_iommus
[    1.860032] AMD-Vi: Translation is already enabled - trying to copy translation structures
[    1.869812] AMD-Vi: Copied DEV table from previous kernel.
[    1.875958] AMD-Vi: in build_completion_wait, paddr = 0x100805000
[    1.882766] BUG: unable to handle page fault for address: ffff9f5340805000
[    1.890441] #PF: supervisor read access in kernel mode
[    1.896177] #PF: error_code(0x0000) - not-present page

....

I think that memremap(..,..,MEMREMAP_WB) will also fail for the same reason as memremap(.., MEMREMAP_WB) for the RAM region will 
again use the kernel directmap.

So it looks like we need to support IOMMU_SNP_SHUTDOWN with SNP_SHUTDOWN_EX command before kdump kernel starts booting.

Thanks,
Ashish

---

## [12] Ashish Kalra — 2024-09-09
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hello Sean,

On 9/4/2024 5:23 PM, Sean Christopherson wrote:
>> On Wed, Sep 04, 2024, Ashish Kalra wrote:
>>> On 9/4/2024 2:54 PM, Michael Roth wrote:

>Here is a deeper understanding of this issue:

>It looks like this is happening: when we do SNP_SHUTDOWN without IOMMU_SNP_SHUTDOWN during panic, kdump boot runs with iommu snp 
>enforcement still enabled and IOMMU completion wait buffers (cwb) still locked and exclusivity still setup on those, and then in 

>[    1.711588] AMD-Vi: early_amd_iommu_init: irq remaping enabled
>[    1.718972] AMD-Vi: in early_enable_iommus

>And because of this the iommu command, in this case which is for enabling irq remapping does not succeed and that eventually causes 
>timer to fail without irq remapping support enabled.

>Once IOMMU SNP support is enabled, to enforce RMP enforcement the IOMMU completion wait buffers are setup as read-only and 
>exclusivity set on these and additionally the IOMMU registers used to mark the exclusivity on the store addresses associated with 

>From the AMD IOMMU specifications:

>2.12.2.2 SEV-SNP COMPLETION_WAIT Store Restrictions On systems that are SNP-enabled, the store address associated with any host 
>COMPLETION_WAIT command (s=1) is restricted. The Store Address must fall within the address range specified by the Completion Store 

>2.12.2.3 SEV-SNP Exclusion Range Restrictions The exclusion range feature is not supported on systems that are SNP-enabled. 
>Additionally, the Exclusion Base and Exclusion Range Limit registers are re-purposed to act as the Completion Store Base and Limit 

>Therefore, we need to disable IOMMU SNP enforcement with SNP_SHUTDOWN_EX command before the kdump kernel starts booting as we can't 
>setup IOMMU CWB again in kdump as SEV-SNP exclusion base and range limit registers are locked as IOMMU SNP support is still enabled.

>I tried to use the previous kernel's CWB (cmd_sem) as below: 

>static int __init alloc_cwwb_sem(struct amd_iommu *iommu)
>{

>I tried this, but this fails as i believe the kdump kernel will not have these previous kernel's allocated IOMMU CWB in the kernel 
>direct map : 

>[    1.708959] AMD-Vi: in alloc_cwwb_sem kdump kernel
>[    1.714327] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x100805000, cmd_sem_vaddr 0xffff9f5340805000

>....

>I think that memremap(..,..,MEMREMAP_WB) will also fail for the same reason as memremap(.., MEMREMAP_WB) for the RAM region will 
>again use the kernel directmap.

To follow up on this:

I am able to use memremap() to map the previous kernel's allocated CWB buffers and try to reuse the same CWB buffers in the
kdump kernel, obviously, memremap() does not return a direct pointer to kernel directmap as the previous kernel's CWB buffers 
will be in a RAM address which is not directly mapped into kdump kernel's directmap.
 
And these memremap() mappings seem to be correct, because if i do a memset(0) on these, i get a RMP #PF violation due
to these buffers being setup as RO in the RMP table, so that means that memremap() seems to have done the mapping correctly.

I am getting inconsistent IOMMU command completion wait timeout's with these reused CWB buffers (which are used as
semaphores to indicate IOMMU command completions) and i am still debugging those issues.

Thanks,
Ashish

---

## [13] Ashish Kalra — 2024-09-12
*Subject: Re: [PATCH v2] x86/sev: Fix host kdump support for SNP*

Hello Sean,

On 9/4/2024 5:23 PM, Sean Christopherson wrote:
>> On Wed, Sep 04, 2024, Ashish Kalra wrote:
>>> On 9/4/2024 2:54 PM, Michael Roth wrote:

>Here is a deeper understanding of this issue:

>It looks like this is happening: when we do SNP_SHUTDOWN without IOMMU_SNP_SHUTDOWN during panic, kdump boot runs with iommu snp 
>enforcement still enabled and IOMMU completion wait buffers (cwb) still locked and exclusivity still setup on those, and then in 

>[    1.711588] AMD-Vi: early_amd_iommu_init: irq remaping enabled
>[    1.718972] AMD-Vi: in early_enable_iommus

>And because of this the iommu command, in this case which is for enabling irq remapping does not succeed and that eventually causes 
>timer to fail without irq remapping support enabled.

>Once IOMMU SNP support is enabled, to enforce RMP enforcement the IOMMU completion wait buffers are setup as read-only and 
>exclusivity set on these and additionally the IOMMU registers used to mark the exclusivity on the store addresses associated with 

>From the AMD IOMMU specifications:

>2.12.2.2 SEV-SNP COMPLETION_WAIT Store Restrictions On systems that are SNP-enabled, the store address associated with any host 
>COMPLETION_WAIT command (s=1) is restricted. The Store Address must fall within the address range specified by the Completion Store 

>2.12.2.3 SEV-SNP Exclusion Range Restrictions The exclusion range feature is not supported on systems that are SNP-enabled. 
>Additionally, the Exclusion Base and Exclusion Range Limit registers are re-purposed to act as the Completion Store Base and Limit 

>Therefore, we need to disable IOMMU SNP enforcement with SNP_SHUTDOWN_EX command before the kdump kernel starts booting as we can't 
>setup IOMMU CWB again in kdump as SEV-SNP exclusion base and range limit registers are locked as IOMMU SNP support is still enabled.

>I tried to use the previous kernel's CWB (cmd_sem) as below: 

>static int __init alloc_cwwb_sem(struct amd_iommu *iommu)
>{

>I tried this, but this fails as i believe the kdump kernel will not have these previous kernel's allocated IOMMU CWB in the kernel 
>direct map : 

>[    1.708959] AMD-Vi: in alloc_cwwb_sem kdump kernel
>[    1.714327] AMD-Vi: in alloc_cwwb_sem SNP feature enabled, cmd_sem_paddr 0x100805000, cmd_sem_vaddr 0xffff9f5340805000

>....

>I think that memremap(..,..,MEMREMAP_WB) will also fail for the same reason as memremap(.., MEMREMAP_WB) for the RAM region will 
>again use the kernel directmap.

More follow-up on this: 

Fixed crashkernel/kdump boot with IOMMU SNP support still enabled prior to kdump boot by reusing the pages of the previous 
kernel for IOMMU completion wait buffers, command buffer and device table and memremap them during kdump boot, with this change in 
the IOMMU driver kdump boots and is able to complete saving the core image.

With this IOMMU driver fix, there is no need to do SNP_DECOMMISSION during panic() and kdump kernel boot will be more agnostic to 
whether or not SNP_SHUTDOWN is done properly (or even done at all), i.e., even with active SNP guests.

As mentioned earlier as SNP is not shutdown and IOMMU SNP support is still enabled prior to kdump boot, all the MMIO registers 
mentioned in AMD IOMMU specs (as below) are locked:

2.12.2.1 SEV-SNP Register Locks
The following IOMMU registers become locked and are no longer writeable after the system
becomes SNP-enabled:
- Device Table Base Address Register [MMIO Offset 0000h]
- Command Buffer Base Address Register [MMIO Offset 0008h]
- Event Log Base Address Register [MMIO Offset 0010h]
- IOMMU Control Register [MMIO Offset 0018h] fields:
- MMIO Offset 0018h[IOMMUEn]
- MMIO Offset 0018h[DevTblSegEn]
- IOMMU Exclusion Base Register / Completion Store Base Register [MMIO Offset 0020h]
- IOMMU Exclusion Range Limit Register / Completion Store Limit Register [MMIO Offset 0028h]
- PPR Log Base Address Register [MMIO Offset 0038h]
- Guest Virtual APIC Log Base Address Register [MMIO Offset 00E0h]
- Guest Virtual APIC Log Tail Address Register [MMIO Offset 00E8h]
- PPR Log B Base Address Register [MMIO Offset 00F0h]
- Event Log B Base Address Register [MMIO Offset 00F8h]
- Device Table Segment n Base Address Register

As Device Table Base Address Register, Command Buffer Base Address Register and Completion Store Base Register and Completion Store
Limit Register are locked, the writes look to them are ignored, they don’t cause any errors, but as writes are being ignored these 
registers are not updated with new allocations for device table, command buffer and CWB buffers during IOMMU driver init when doing 
kdump boot and these are required to initialize the IOMMU and enable irq remapping support in the kdump kernel.
 
Therefore, we reuse the pages of the previous kernel for CWB buffers, command buffer and device table and memremap them during 
kdump boot and essentially work with an already enabled SNP configuration and re-using the previous kernel’s data structures.

So now this will be an IOMMU driver change and we can skip the need to do SNP_DECOMMISSION and this should work in all situations 
irrespective of SNP_SHUTDOWN done prior to kdump boot.

Thanks,
Ashish

---
