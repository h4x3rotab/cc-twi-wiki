---
title: 'x86/sev: Fix host kdump support for SNP'
date: 2024-08-27
last_reply: 2024-09-03
message_count: 12
participants: ['Ashish Kalra', 'Borislav Petkov', 'Sean Christopherson', 'kernel test robot', 'Paolo Bonzini']
---

## [1] Ashish Kalra — 2024-08-27

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
[  564.282209] in snp_shutdown_on_panic after decommision, wbinvd + df_flush required
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

To fix this, added support to do SNP_DECOMMISION of all active SNP VMs
in the panic notifier before doing SNP_SHUTDOWN_EX, but then
SNP_DECOMMISION tags all CPUs on which guest has been activated to do
a WBINVD. This causes SNP_DF_FLUSH command failure with the following
flow: SNP_DECOMMISION -> SNP_SHUTDOWN_EX -> SNP_DF_FLUSH ->
failure with WBINVD_REQUIRED.

When panic notifier is invoked all other CPUs have already been
shutdown, so it is not possible to do a wbinvd_on_all_cpus() after
SNP_DECOMMISION has been executed. This eventually causes SNP_SHUTDOWN_EX
to fail after SNP_DECOMMISION.

Adding fix to do SNP_DECOMMISION and subsequent WBINVD on all CPUs
during NMI shutdown of CPUs as part of disabling virtualization on
all CPUs via cpu_emergency_disable_virtualization ->
svm_emergency_disable().

This fixes and enables crashkernel/kdump on SNP host.

Fixes: c3b86e61b756 ("x86/cpufeatures: Enable/unmask SEV-SNP CPU feature")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 39 ++++++++++++++++++
 arch/x86/kvm/svm/svm.c | 91 ++++++++++++++++++++++++++++++++++++++++++
 arch/x86/kvm/svm/svm.h |  3 +-
 3 files changed, 132 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 0b851ef937f2..34ddea43c4e6 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -89,6 +89,7 @@ static unsigned int nr_asids;
 static unsigned long *sev_asid_bitmap;
 static unsigned long *sev_reclaim_asid_bitmap;
 
+static void **snp_asid_to_gctx_pages_map;
 static int snp_decommission_context(struct kvm *kvm);
 
 struct enc_region {
@@ -2248,6 +2249,9 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 		goto e_free_context;
 	}
 
+	if (snp_asid_to_gctx_pages_map)
+		snp_asid_to_gctx_pages_map[sev_get_asid(kvm)] = sev->snp_context;
+
 	return 0;
 
 e_free_context:
@@ -2884,9 +2888,35 @@ static int snp_decommission_context(struct kvm *kvm)
 	snp_free_firmware_page(sev->snp_context);
 	sev->snp_context = NULL;
 
+	if (snp_asid_to_gctx_pages_map)
+		snp_asid_to_gctx_pages_map[sev_get_asid(kvm)] = NULL;
+
 	return 0;
 }
 
+/*
+ * NOTE: called in NMI context from sev_emergency_disable().
+ */
+void snp_decommision_all(void)
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
 void sev_vm_destroy(struct kvm *kvm)
 {
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
@@ -3052,6 +3082,13 @@ void __init sev_hardware_setup(void)
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
@@ -3094,6 +3131,8 @@ void sev_hardware_unsetup(void)
 
 	misc_cg_set_capacity(MISC_CG_RES_SEV, 0);
 	misc_cg_set_capacity(MISC_CG_RES_SEV_ES, 0);
+
+	kfree(snp_asid_to_gctx_pages_map);
 }
 
 int sev_cpu_init(struct svm_cpu_data *sd)
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index e13c54d93964..a8f64a1710c2 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -17,6 +17,7 @@
 #include <linux/highmem.h>
 #include <linux/amd-iommu.h>
 #include <linux/sched.h>
+#include <linux/delay.h>
 #include <linux/trace_events.h>
 #include <linux/slab.h>
 #include <linux/hashtable.h>
@@ -248,6 +249,8 @@ static unsigned long iopm_base;
 
 DEFINE_PER_CPU(struct svm_cpu_data, svm_data);
 
+static DEFINE_SPINLOCK(snp_decommision_lock);
+
 /*
  * Only MSR_TSC_AUX is switched via the user return hook.  EFER is switched via
  * the VMCB, and the SYSCALL/SYSENTER MSRs are handled by VMLOAD/VMSAVE.
@@ -594,9 +597,97 @@ static inline void kvm_cpu_svm_disable(void)
 
 static void svm_emergency_disable(void)
 {
+	static atomic_t waiting_for_cpus_synchronized;
+	static bool synchronize_cpus_initiated;
+	static bool snp_decommision_handled;
+	static atomic_t cpus_synchronized;
+
 	kvm_rebooting = true;
 
 	kvm_cpu_svm_disable();
+
+	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+		return;
+
+	/*
+	 * SNP_SHUTDOWN_EX fails when SNP VMs are active as the firmware checks
+	 * every encryption-capable ASID to verify that it is not in use by a
+	 * guest and a DF_FLUSH is not required. If a DF_FLUSH is required,
+	 * the firmware returns DFFLUSH_REQUIRED. To address this, SNP_DECOMMISION
+	 * is required to shutdown all active SNP VMs, but SNP_DECOMMISION tags all
+	 * CPUs that guest was activated on to do a WBINVD. When panic notifier
+	 * is invoked all other CPUs have already been shutdown, so it is not
+	 * possible to do a wbinvd_on_all_cpus() after SNP_DECOMMISION has been
+	 * executed. This eventually causes SNP_SHUTDOWN_EX to fail after
+	 * SNP_DECOMMISION. To fix this, do SNP_DECOMMISION and subsequent WBINVD
+	 * on all CPUs during NMI shutdown of CPUs as part of disabling
+	 * virtualization on all CPUs via cpu_emergency_disable_virtualization().
+	 */
+
+	spin_lock(&snp_decommision_lock);
+
+	/*
+	 * exit early for call from native_machine_crash_shutdown()
+	 * as SNP_DECOMMISSION has already been done as part of
+	 * NMI shutdown of the CPUs.
+	 */
+	if (snp_decommision_handled) {
+		spin_unlock(&snp_decommision_lock);
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
+		spin_unlock(&snp_decommision_lock);
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
+		spin_lock(&snp_decommision_lock);
+
+		atomic_set(&cpus_synchronized, 1);
+	} else {
+		atomic_dec(&waiting_for_cpus_synchronized);
+		/*
+		 * drop the lock to let other CPUs contiune to reach
+		 * synchronization.
+		 */
+		spin_unlock(&snp_decommision_lock);
+
+		while (atomic_read(&cpus_synchronized) == 0)
+		       mdelay(1);
+
+		/* Try to re-acquire lock after CPUs are synchronized */
+		spin_lock(&snp_decommision_lock);
+	}
+
+	if (!snp_decommision_handled) {
+		snp_decommision_all();
+		snp_decommision_handled = true;
+	}
+	spin_unlock(&snp_decommision_lock);
+	wbinvd();
 }
 
 static void svm_hardware_disable(void)
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 76107c7d0595..2f933b941b8d 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -749,6 +749,7 @@ void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu);
 int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 void sev_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn);
+void snp_decommision_all(void);
 #else
 static inline struct page *snp_safe_alloc_page_node(int node, gfp_t gfp)
 {
@@ -779,7 +780,7 @@ static inline int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn)
 {
 	return 0;
 }
-
+static void snp_decommision_all(void);
 #endif
 
 /* vmenter.S */

---

## [2] Borislav Petkov — 2024-08-29
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

On August 27, 2024 10:38:04 PM GMT+02:00, Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>From: Ashish Kalra <ashish.kalra@amd.com>
>

Why would SNP_SHUTDOWN be allowed *at all* if there are active SNP guests and there's potential to lose guest data in the process?!

I don't think you want to be on the receiving end of those customer support calls at your cloud provider...

---

## [3] Kalra, Ashish — 2024-08-29
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

Hello Boris,

On 8/29/2024 3:34 AM, Borislav Petkov wrote:
> On August 27, 2024 10:38:04 PM GMT+02:00, Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

If SNP_SHUTDOWN is not done, then crashkernel panics during boot as the crashdump attached to the fix/patch here shows, so essentially if SNP_DECOMMISSION followed by SNP_SHUTDOWN is not done then we can't boot crashkernel in case of any active SNP guests (which i will believe is an important requirement for cloud providers).

Additionally, in case of SNP_DECOMMISSION, the firmware marks the ASID of the guest as not runnable and then transitions the SNP guest context page into a Firmware page (so that is one RMP table change) and for SNP_SHUTDOWN_EX, the firmware transitions all pages associated with the IOMMU to the Reclaim state (which then the HV marks as hypervisor pages), these IOMMU pages are the event log, PPR log, and completion wait buffers of the IOMMU.

Aside from the IOMMU pages mentioned above, the firmware will not automatically reclaim or modify any other pages in the RMP table and also does not reset the RMP table.

So essentially all host memory (and guest data) will still be available and saved by crashkernel.

Thanks, Ashish

---

## [4] Borislav Petkov — 2024-08-29
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

On Thu, Aug 29, 2024 at 09:30:54AM -0500, Kalra, Ashish wrote:
> Hello Boris,
> 

Read my question again pls.

---

## [5] Sean Christopherson — 2024-08-29
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

On Thu, Aug 29, 2024, Borislav Petkov wrote:
> On August 27, 2024 10:38:04 PM GMT+02:00, Ashish Kalra <Ashish.Kalra@amd.com> wrote:
> >From: Ashish Kalra <ashish.kalra@amd.com>

Because if the host is panicking, guests are hosed regardless.  Unless I'm
misreading things, the goal here is to ensure the crashkernel can actually capture
a kdump.

---

## [6] Borislav Petkov — 2024-08-29
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

On Thu, Aug 29, 2024 at 07:50:16AM -0700, Sean Christopherson wrote:
> Because if the host is panicking, guests are hosed regardless.

Are they?

I read "active SNP VMs"...

I guess if it reaches svm_emergency_disable() we're hosed anyway and that's
what you mean but I'm not sure...

---

## [7] Kalra, Ashish — 2024-08-29
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

On 8/29/2024 9:50 AM, Sean Christopherson wrote:

> On Thu, Aug 29, 2024, Borislav Petkov wrote:
>> On August 27, 2024 10:38:04 PM GMT+02:00, Ashish Kalra <Ashish.Kalra@amd.com> wrote:

Yes, that is the main goal here to ensure that crashkernel can boot and capture a kdump on a SNP enabled host regardless of SNP VMs running.

Thanks, Ashish

---

## [8] kernel test robot — 2024-08-29
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

Hi Ashish,

kernel test robot noticed the following build warnings:

[auto build test WARNING on kvm/queue]
[also build test WARNING on linus/master v6.11-rc5 next-20240829]
[cannot apply to kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Ashish-Kalra/x86-sev-Fix-host-kdump-support-for-SNP/20240828-044035
base:   https://git.kernel.org/pub/scm/virt/kvm/kvm.git queue
patch link:    https://lore.kernel.org/r/20240827203804.4989-1-Ashish.Kalra%40amd.com
patch subject: [PATCH] x86/sev: Fix host kdump support for SNP
config: x86_64-buildonly-randconfig-002-20240829 (https://download.01.org/0day-ci/archive/20240829/202408292344.yuQ5sYEz-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20240829/202408292344.yuQ5sYEz-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202408292344.yuQ5sYEz-lkp@intel.com/

All warnings (new ones prefixed by >>):

   In file included from arch/x86/kvm/svm/avic.c:28:
>> arch/x86/kvm/svm/svm.h:783:13: warning: 'snp_decommision_all' declared 'static' but never defined [-Wunused-function]
     783 | static void snp_decommision_all(void);
         |             ^~~~~~~~~~~~~~~~~~~
--
   In file included from arch/x86/kvm/svm/svm.c:50:
>> arch/x86/kvm/svm/svm.h:783:13: warning: 'snp_decommision_all' used but never defined
     783 | static void snp_decommision_all(void);
         |             ^~~~~~~~~~~~~~~~~~~


vim +783 arch/x86/kvm/svm/svm.h

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
 > 783	static void snp_decommision_all(void);
   784	#endif
   785

---

## [9] Kalra, Ashish — 2024-08-30
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

Hello Boris,

On 8/29/2024 10:16 AM, Kalra, Ashish wrote:
> On 8/29/2024 9:50 AM, Sean Christopherson wrote:
>

Are you convinced with Sean's feedback here that this is a required feature to fix ?

And it is important to reiterate this again:

SNP_DECOMMISSION mainly unbinds the ASID from SNP context and marks the ASID as unusable and then transitions the SNP guest context page to a FW page and SNP_SHUTDOWN_EX transitions all pages associated with the IOMMU to reclaim state which the HV then transitions to hypervisor state, all these page state changes are in the RMP table, so there is no loss of guest data as such and the complete host memory is captured with the crashkernel boot. There are no processes which are being killed and host/guest memory is not being altered or modified in any way.

Additionally, i believe that the support staff will absolutely need this kind of support which enables crashkernel/kdump for SNP hosts.

Thanks, Ashish

---

## [10] kernel test robot — 2024-08-31
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

Hi Ashish,

kernel test robot noticed the following build warnings:

[auto build test WARNING on kvm/queue]
[also build test WARNING on linus/master v6.11-rc5 next-20240830]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Ashish-Kalra/x86-sev-Fix-host-kdump-support-for-SNP/20240828-044035
base:   https://git.kernel.org/pub/scm/virt/kvm/kvm.git queue
patch link:    https://lore.kernel.org/r/20240827203804.4989-1-Ashish.Kalra%40amd.com
patch subject: [PATCH] x86/sev: Fix host kdump support for SNP
config: i386-buildonly-randconfig-006-20240831 (https://download.01.org/0day-ci/archive/20240831/202408311530.cYa27OX8-lkp@intel.com/config)
compiler: clang version 18.1.5 (https://github.com/llvm/llvm-project 617a15a9eac96088ae5e9134248d8236e34b91b1)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20240831/202408311530.cYa27OX8-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202408311530.cYa27OX8-lkp@intel.com/

All warnings (new ones prefixed by >>):

   In file included from arch/x86/kvm/svm/svm.c:50:
>> arch/x86/kvm/svm/svm.h:783:13: warning: function 'snp_decommision_all' has internal linkage but is not defined [-Wundefined-internal]
     783 | static void snp_decommision_all(void);
         |             ^
   arch/x86/kvm/svm/svm.c:686:3: note: used here
     686 |                 snp_decommision_all();
         |                 ^
   1 warning generated.


vim +/snp_decommision_all +783 arch/x86/kvm/svm/svm.h

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
 > 783	static void snp_decommision_all(void);
   784	#endif
   785

---

## [11] Paolo Bonzini — 2024-09-02
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

On Tue, Aug 27, 2024 at 10:40 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
> +void snp_decommision_all(void)

Should be spelled snp_decommission_all (with two "s").

> +static DEFINE_SPINLOCK(snp_decommision_lock);

Same here.

>  /*
>   * Only MSR_TSC_AUX is switched via the user return hook.  EFER is switched via

Same here, and below throughout the function (also SNP_DECOMMISSION).

Please create a new function sev_emergency_disable(), with a stub in
svm.h if CONFIG_KVM_AMD_

> @@ -749,6 +749,7 @@ void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu);
>  int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);

This should be inline (and after the change above it should be
sev_emergency_disable(), not snp_decommission_all(), that is exported
from sev.c).

Thanks,

Paolo

---

## [12] Borislav Petkov — 2024-09-03
*Subject: Re: [PATCH] x86/sev: Fix host kdump support for SNP*

On Fri, Aug 30, 2024 at 04:08:35PM -0500, Kalra, Ashish wrote:
> Are you convinced with Sean's feedback here that this is a required feature to fix ?

Yes.

Thx.

---
