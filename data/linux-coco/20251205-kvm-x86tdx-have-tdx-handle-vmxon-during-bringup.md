---
title: 'KVM: x86/tdx: Have TDX handle VMXON during bringup'
date: 2025-12-05
last_reply: 2026-01-27
message_count: 40
participants: ['Sean Christopherson', 'dan.j.williams@intel.com', 'Chao Gao', 'Xu Yilun', 'Dave Hansen', 'Huang, Kai', 'Binbin Wu']
---

## [1] Sean Christopherson — 2025-12-05

The idea here is to extract _only_ VMXON+VMXOFF and EFER.SVME toggling.  AFAIK
there's no second user of SVM, i.e. no equivalent to TDX, but I wanted to keep
things as symmetrical as possible.

TDX isn't a hypervisor, and isn't trying to be a hypervisor. Specifically, TDX
should _never_ have it's own VMCSes (that are visible to the host; the
TDX-Module has it's own VMCSes to do SEAMCALL/SEAMRET), and so there is simply
no reason to move that functionality out of KVM.

With that out of the way, dealing with VMXON/VMXOFF and EFER.SVME is a fairly
simple refcounting game.

Decently tested, and it seems like the core idea is sound, so I dropped the
RFC.  But the side of things definitely needs testing.

Note, this is based on kvm-x86/next, which doesn't have
EXPORT_SYMBOL_FOR_KVM(), and so the virt/hw.c exports need to be fixed up.
I'm sending now instead of waiting for -rc1 because I'm assuming I'll need to
spin at least v3 anyways :-)

v2:
 - Initialize the TDX-Module via subsys initcall instead of during
   tdx_init(). [Rick]
 - Isolate the __init and __ro_after_init changes. [Rick]
 - Use ida_is_empty() instead of manually tracking HKID usage. [Dan]
 - Don't do weird things with the refcounts when virt_rebooting is
   true. [Chao]
 - Drop unnecessary setting of virt_rebooting in KVM code. [Chao]
 - Rework things to have less X86_FEATURE_FOO code. [Rick]
 - Consolidate the CPU hotplug callbacks. [Chao]

v1 (RFC):
 - https://lore.kernel.org/all/20251010220403.987927-1-seanjc@google.com

Chao Gao (1):
  x86/virt/tdx: KVM: Consolidate TDX CPU hotplug handling

Sean Christopherson (6):
  KVM: x86: Move kvm_rebooting to x86
  KVM: x86: Extract VMXON and EFER.SVME enablement to kernel
  KVM: x86/tdx: Do VMXON and TDX-Module initialization during subsys
    init
  x86/virt/tdx: Tag a pile of functions as __init, and globals as
    __ro_after_init
  x86/virt/tdx: Use ida_is_empty() to detect if any TDs may be running
  KVM: Bury kvm_{en,dis}able_virtualization() in kvm_main.c once more

 Documentation/arch/x86/tdx.rst              |  26 --
 arch/x86/events/intel/pt.c                  |   1 -
 arch/x86/include/asm/kvm_host.h             |   3 +-
 arch/x86/include/asm/reboot.h               |  11 -
 arch/x86/include/asm/tdx.h                  |   4 -
 arch/x86/include/asm/virt.h                 |  26 ++
 arch/x86/include/asm/vmx.h                  |  11 +
 arch/x86/kernel/cpu/common.c                |   2 +
 arch/x86/kernel/crash.c                     |   3 +-
 arch/x86/kernel/reboot.c                    |  63 +---
 arch/x86/kernel/smp.c                       |   5 +-
 arch/x86/kvm/svm/svm.c                      |  34 +-
 arch/x86/kvm/svm/vmenter.S                  |  10 +-
 arch/x86/kvm/vmx/tdx.c                      | 209 ++----------
 arch/x86/kvm/vmx/vmcs.h                     |  11 -
 arch/x86/kvm/vmx/vmenter.S                  |   2 +-
 arch/x86/kvm/vmx/vmx.c                      | 127 +-------
 arch/x86/kvm/x86.c                          |  20 +-
 arch/x86/virt/Makefile                      |   2 +
 arch/x86/virt/hw.c                          | 340 ++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 315 ++++++++++--------
 arch/x86/virt/vmx/tdx/tdx.h                 |   8 -
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  10 +-
 include/linux/kvm_host.h                    |  10 +-
 virt/kvm/kvm_main.c                         |  31 +-
 25 files changed, 657 insertions(+), 627 deletions(-)
 create mode 100644 arch/x86/include/asm/virt.h
 create mode 100644 arch/x86/virt/hw.c


base-commit: 5d3e2d9ba9ed68576c70c127e4f7446d896f2af2

---

## [2] Sean Christopherson — 2025-12-05
*Subject: [PATCH v2 1/7] KVM: x86: Move kvm_rebooting to x86*

Move kvm_rebooting, which is only read by x86, to KVM x86 so that it can
be moved again to core x86 code.  Add a "shutdown" arch hook to facilate
setting the flag in KVM x86.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c       | 13 +++++++++++++
 arch/x86/kvm/x86.h       |  1 +
 include/linux/kvm_host.h |  2 +-
 virt/kvm/kvm_main.c      | 14 +++++++-------
 4 files changed, 22 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 0c6d899d53dd..80cb882f19e2 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -694,6 +694,9 @@ static void drop_user_return_notifiers(void)
 		kvm_on_user_return(&msrs->urn);
 }
 
+__visible bool kvm_rebooting;
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
+
 /*
  * Handle a fault on a hardware virtualization (VMX or SVM) instruction.
  *
@@ -13100,6 +13103,16 @@ int kvm_arch_enable_virtualization_cpu(void)
 	return 0;
 }
 
+void kvm_arch_shutdown(void)
+{
+	/*
+	 * Set kvm_rebooting to indicate that KVM has asynchronously disabled
+	 * hardware virtualization, i.e. that relevant errors and exceptions
+	 * aren't entirely unexpected.
+	 */
+	kvm_rebooting = true;
+}
+
 void kvm_arch_disable_virtualization_cpu(void)
 {
 	kvm_x86_call(disable_virtualization_cpu)();
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index fdab0ad49098..40993348a967 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -54,6 +54,7 @@ struct kvm_host_values {
 	u64 arch_capabilities;
 };
 
+extern bool kvm_rebooting;
 void kvm_spurious_fault(void);
 
 #define SIZE_OF_MEMSLOTS_HASHTABLE \
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index d93f75b05ae2..a453fe6ce05a 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -1621,6 +1621,7 @@ static inline void kvm_create_vcpu_debugfs(struct kvm_vcpu *vcpu) {}
 #endif
 
 #ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
+void kvm_arch_shutdown(void);
 /*
  * kvm_arch_{enable,disable}_virtualization() are called on one CPU, under
  * kvm_usage_lock, immediately after/before 0=>1 and 1=>0 transitions of
@@ -2302,7 +2303,6 @@ static inline bool kvm_check_request(int req, struct kvm_vcpu *vcpu)
 
 #ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
 extern bool enable_virt_at_load;
-extern bool kvm_rebooting;
 #endif
 
 extern unsigned int halt_poll_ns;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index f1f6a71b2b5f..3278ee9381bd 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -5586,13 +5586,15 @@ bool enable_virt_at_load = true;
 module_param(enable_virt_at_load, bool, 0444);
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(enable_virt_at_load);
 
-__visible bool kvm_rebooting;
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
-
 static DEFINE_PER_CPU(bool, virtualization_enabled);
 static DEFINE_MUTEX(kvm_usage_lock);
 static int kvm_usage_count;
 
+__weak void kvm_arch_shutdown(void)
+{
+
+}
+
 __weak void kvm_arch_enable_virtualization(void)
 {
 
@@ -5646,10 +5648,9 @@ static int kvm_offline_cpu(unsigned int cpu)
 
 static void kvm_shutdown(void)
 {
+	kvm_arch_shutdown();
+
 	/*
-	 * Disable hardware virtualization and set kvm_rebooting to indicate
-	 * that KVM has asynchronously disabled hardware virtualization, i.e.
-	 * that relevant errors and exceptions aren't entirely unexpected.
 	 * Some flavors of hardware virtualization need to be disabled before
 	 * transferring control to firmware (to perform shutdown/reboot), e.g.
 	 * on x86, virtualization can block INIT interrupts, which are used by
@@ -5658,7 +5659,6 @@ static void kvm_shutdown(void)
 	 * 100% comprehensive.
 	 */
 	pr_info("kvm: exiting hardware virtualization\n");
-	kvm_rebooting = true;
 	on_each_cpu(kvm_disable_virtualization_cpu, NULL, 1);
 }

---

## [3] Sean Christopherson — 2025-12-05
*Subject: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement to kernel*

Move the innermost VMXON and EFER.SVME management logic out of KVM and
into to core x86 so that TDX can force VMXON without having to rely on
KVM being loaded, e.g. to do SEAMCALLs during initialization.

Implement a per-CPU refcounting scheme so that "users", e.g. KVM and the
future TDX code, can co-exist without pulling the rug out from under each
other.

To avoid having to choose between SVM and VMX, simply refuse to enable
either if both are somehow supported.  No known CPU supports both SVM and
VMX, and it's comically unlikely such a CPU will ever exist.

For lack of a better name, call the new file "hw.c", to yield "virt
hardware" when combined with its parent directory.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/events/intel/pt.c      |   1 -
 arch/x86/include/asm/kvm_host.h |   3 +-
 arch/x86/include/asm/reboot.h   |  11 --
 arch/x86/include/asm/virt.h     |  26 +++
 arch/x86/include/asm/vmx.h      |  11 ++
 arch/x86/kernel/cpu/common.c    |   2 +
 arch/x86/kernel/crash.c         |   3 +-
 arch/x86/kernel/reboot.c        |  63 +-----
 arch/x86/kernel/smp.c           |   5 +-
 arch/x86/kvm/svm/svm.c          |  34 +---
 arch/x86/kvm/svm/vmenter.S      |  10 +-
 arch/x86/kvm/vmx/tdx.c          |   3 +-
 arch/x86/kvm/vmx/vmcs.h         |  11 --
 arch/x86/kvm/vmx/vmenter.S      |   2 +-
 arch/x86/kvm/vmx/vmx.c          | 127 +-----------
 arch/x86/kvm/x86.c              |  17 +-
 arch/x86/kvm/x86.h              |   1 -
 arch/x86/virt/Makefile          |   2 +
 arch/x86/virt/hw.c              | 340 ++++++++++++++++++++++++++++++++
 19 files changed, 422 insertions(+), 250 deletions(-)
 create mode 100644 arch/x86/include/asm/virt.h
 create mode 100644 arch/x86/virt/hw.c

diff --git a/arch/x86/events/intel/pt.c b/arch/x86/events/intel/pt.c
index e8cf29d2b10c..9092f0f9de72 100644
--- a/arch/x86/events/intel/pt.c
+++ b/arch/x86/events/intel/pt.c
@@ -1590,7 +1590,6 @@ void intel_pt_handle_vmx(int on)
 
 	local_irq_restore(flags);
 }
-EXPORT_SYMBOL_GPL(intel_pt_handle_vmx);
 
 /*
  * PMU callbacks
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 5a3bfa293e8b..47b535c1c3bd 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -40,7 +40,8 @@
 #include <asm/irq_remapping.h>
 #include <asm/kvm_page_track.h>
 #include <asm/kvm_vcpu_regs.h>
-#include <asm/reboot.h>
+#include <asm/virt.h>
+
 #include <hyperv/hvhdk.h>
 
 #define __KVM_HAVE_ARCH_VCPU_DEBUGFS
diff --git a/arch/x86/include/asm/reboot.h b/arch/x86/include/asm/reboot.h
index ecd58ea9a837..a671a1145906 100644
--- a/arch/x86/include/asm/reboot.h
+++ b/arch/x86/include/asm/reboot.h
@@ -25,17 +25,6 @@ void __noreturn machine_real_restart(unsigned int type);
 #define MRR_BIOS	0
 #define MRR_APM		1
 
-typedef void (cpu_emergency_virt_cb)(void);
-#if IS_ENABLED(CONFIG_KVM_X86)
-void cpu_emergency_register_virt_callback(cpu_emergency_virt_cb *callback);
-void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback);
-void cpu_emergency_disable_virtualization(void);
-#else
-static inline void cpu_emergency_register_virt_callback(cpu_emergency_virt_cb *callback) {}
-static inline void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback) {}
-static inline void cpu_emergency_disable_virtualization(void) {}
-#endif /* CONFIG_KVM_X86 */
-
 typedef void (*nmi_shootdown_cb)(int, struct pt_regs*);
 void nmi_shootdown_cpus(nmi_shootdown_cb callback);
 void run_crash_ipi_callback(struct pt_regs *regs);
diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
new file mode 100644
index 000000000000..77a366afd9f7
--- /dev/null
+++ b/arch/x86/include/asm/virt.h
@@ -0,0 +1,26 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef _ASM_X86_VIRT_H
+#define _ASM_X86_VIRT_H
+
+#include <asm/reboot.h>
+
+typedef void (cpu_emergency_virt_cb)(void);
+
+#if IS_ENABLED(CONFIG_KVM_X86)
+extern bool virt_rebooting;
+
+void __init x86_virt_init(void);
+
+int x86_virt_get_cpu(int feat);
+void x86_virt_put_cpu(int feat);
+
+int x86_virt_emergency_disable_virtualization_cpu(void);
+
+void x86_virt_register_emergency_callback(cpu_emergency_virt_cb *callback);
+void x86_virt_unregister_emergency_callback(cpu_emergency_virt_cb *callback);
+#else
+static __always_inline void x86_virt_init(void) {}
+static inline int x86_virt_emergency_disable_virtualization_cpu(void) { return -ENOENT; }
+#endif
+
+#endif /* _ASM_X86_VIRT_H */
diff --git a/arch/x86/include/asm/vmx.h b/arch/x86/include/asm/vmx.h
index c85c50019523..d2c7eb1c5f12 100644
--- a/arch/x86/include/asm/vmx.h
+++ b/arch/x86/include/asm/vmx.h
@@ -20,6 +20,17 @@
 #include <asm/trapnr.h>
 #include <asm/vmxfeatures.h>
 
+struct vmcs_hdr {
+	u32 revision_id:31;
+	u32 shadow_vmcs:1;
+};
+
+struct vmcs {
+	struct vmcs_hdr hdr;
+	u32 abort;
+	char data[];
+};
+
 #define VMCS_CONTROL_BIT(x)	BIT(VMX_FEATURE_##x & 0x1f)
 
 /*
diff --git a/arch/x86/kernel/cpu/common.c b/arch/x86/kernel/cpu/common.c
index 02d97834a1d4..a55cb572d2b4 100644
--- a/arch/x86/kernel/cpu/common.c
+++ b/arch/x86/kernel/cpu/common.c
@@ -70,6 +70,7 @@
 #include <asm/traps.h>
 #include <asm/sev.h>
 #include <asm/tdx.h>
+#include <asm/virt.h>
 #include <asm/posted_intr.h>
 #include <asm/runtime-const.h>
 
@@ -2124,6 +2125,7 @@ static __init void identify_boot_cpu(void)
 	cpu_detect_tlb(&boot_cpu_data);
 	setup_cr_pinning();
 
+	x86_virt_init();
 	tsx_init();
 	tdx_init();
 	lkgs_init();
diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index 335fd2ee9766..cd796818d94d 100644
--- a/arch/x86/kernel/crash.c
+++ b/arch/x86/kernel/crash.c
@@ -42,6 +42,7 @@
 #include <asm/crash.h>
 #include <asm/cmdline.h>
 #include <asm/sev.h>
+#include <asm/virt.h>
 
 /* Used while preparing memory map entries for second kernel */
 struct crash_memmap_data {
@@ -111,7 +112,7 @@ void native_machine_crash_shutdown(struct pt_regs *regs)
 
 	crash_smp_send_stop();
 
-	cpu_emergency_disable_virtualization();
+	x86_virt_emergency_disable_virtualization_cpu();
 
 	/*
 	 * Disable Intel PT to stop its logging
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index 964f6b0a3d68..0f1d14ed955b 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -26,6 +26,7 @@
 #include <asm/cpu.h>
 #include <asm/nmi.h>
 #include <asm/smp.h>
+#include <asm/virt.h>
 
 #include <linux/ctype.h>
 #include <linux/mc146818rtc.h>
@@ -531,51 +532,6 @@ static inline void kb_wait(void)
 static inline void nmi_shootdown_cpus_on_restart(void);
 
 #if IS_ENABLED(CONFIG_KVM_X86)
-/* RCU-protected callback to disable virtualization prior to reboot. */
-static cpu_emergency_virt_cb __rcu *cpu_emergency_virt_callback;
-
-void cpu_emergency_register_virt_callback(cpu_emergency_virt_cb *callback)
-{
-	if (WARN_ON_ONCE(rcu_access_pointer(cpu_emergency_virt_callback)))
-		return;
-
-	rcu_assign_pointer(cpu_emergency_virt_callback, callback);
-}
-EXPORT_SYMBOL_GPL(cpu_emergency_register_virt_callback);
-
-void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback)
-{
-	if (WARN_ON_ONCE(rcu_access_pointer(cpu_emergency_virt_callback) != callback))
-		return;
-
-	rcu_assign_pointer(cpu_emergency_virt_callback, NULL);
-	synchronize_rcu();
-}
-EXPORT_SYMBOL_GPL(cpu_emergency_unregister_virt_callback);
-
-/*
- * Disable virtualization, i.e. VMX or SVM, to ensure INIT is recognized during
- * reboot.  VMX blocks INIT if the CPU is post-VMXON, and SVM blocks INIT if
- * GIF=0, i.e. if the crash occurred between CLGI and STGI.
- */
-void cpu_emergency_disable_virtualization(void)
-{
-	cpu_emergency_virt_cb *callback;
-
-	/*
-	 * IRQs must be disabled as KVM enables virtualization in hardware via
-	 * function call IPIs, i.e. IRQs need to be disabled to guarantee
-	 * virtualization stays disabled.
-	 */
-	lockdep_assert_irqs_disabled();
-
-	rcu_read_lock();
-	callback = rcu_dereference(cpu_emergency_virt_callback);
-	if (callback)
-		callback();
-	rcu_read_unlock();
-}
-
 static void emergency_reboot_disable_virtualization(void)
 {
 	local_irq_disable();
@@ -587,16 +543,11 @@ static void emergency_reboot_disable_virtualization(void)
 	 * We can't take any locks and we may be on an inconsistent state, so
 	 * use NMIs as IPIs to tell the other CPUs to disable VMX/SVM and halt.
 	 *
-	 * Do the NMI shootdown even if virtualization is off on _this_ CPU, as
-	 * other CPUs may have virtualization enabled.
+	 * Safely force _this_ CPU out of VMX/SVM operation, and if necessary,
+	 * blast NMIs to force other CPUs out of VMX/SVM as well.k
 	 */
-	if (rcu_access_pointer(cpu_emergency_virt_callback)) {
-		/* Safely force _this_ CPU out of VMX/SVM operation. */
-		cpu_emergency_disable_virtualization();
-
-		/* Disable VMX/SVM and halt on other CPUs. */
+	if (!x86_virt_emergency_disable_virtualization_cpu())
 		nmi_shootdown_cpus_on_restart();
-	}
 }
 #else
 static void emergency_reboot_disable_virtualization(void) { }
@@ -874,10 +825,10 @@ static int crash_nmi_callback(unsigned int val, struct pt_regs *regs)
 		shootdown_callback(cpu, regs);
 
 	/*
-	 * Prepare the CPU for reboot _after_ invoking the callback so that the
-	 * callback can safely use virtualization instructions, e.g. VMCLEAR.
+	 * Disable virtualization, as both VMX and SVM can block INIT and thus
+	 * prevent AP bringup, e.g. in a kdump kernel or in firmware.
 	 */
-	cpu_emergency_disable_virtualization();
+	x86_virt_emergency_disable_virtualization_cpu();
 
 	atomic_dec(&waiting_for_crash_ipi);
 
diff --git a/arch/x86/kernel/smp.c b/arch/x86/kernel/smp.c
index b014e6d229f9..cbf95fe2b207 100644
--- a/arch/x86/kernel/smp.c
+++ b/arch/x86/kernel/smp.c
@@ -35,6 +35,7 @@
 #include <asm/trace/irq_vectors.h>
 #include <asm/kexec.h>
 #include <asm/reboot.h>
+#include <asm/virt.h>
 
 /*
  *	Some notes on x86 processor bugs affecting SMP operation:
@@ -124,7 +125,7 @@ static int smp_stop_nmi_callback(unsigned int val, struct pt_regs *regs)
 	if (raw_smp_processor_id() == atomic_read(&stopping_cpu))
 		return NMI_HANDLED;
 
-	cpu_emergency_disable_virtualization();
+	x86_virt_emergency_disable_virtualization_cpu();
 	stop_this_cpu(NULL);
 
 	return NMI_HANDLED;
@@ -136,7 +137,7 @@ static int smp_stop_nmi_callback(unsigned int val, struct pt_regs *regs)
 DEFINE_IDTENTRY_SYSVEC(sysvec_reboot)
 {
 	apic_eoi();
-	cpu_emergency_disable_virtualization();
+	x86_virt_emergency_disable_virtualization_cpu();
 	stop_this_cpu(NULL);
 }
 
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 24d59ccfa40d..c09648cc3bd2 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -44,6 +44,7 @@
 #include <asm/traps.h>
 #include <asm/reboot.h>
 #include <asm/fpu/api.h>
+#include <asm/virt.h>
 
 #include <trace/events/ipi.h>
 
@@ -476,27 +477,9 @@ static __always_inline struct sev_es_save_area *sev_es_host_save_area(struct svm
 	return &sd->save_area->host_sev_es_save;
 }
 
-static inline void kvm_cpu_svm_disable(void)
-{
-	uint64_t efer;
-
-	wrmsrq(MSR_VM_HSAVE_PA, 0);
-	rdmsrq(MSR_EFER, efer);
-	if (efer & EFER_SVME) {
-		/*
-		 * Force GIF=1 prior to disabling SVM, e.g. to ensure INIT and
-		 * NMI aren't blocked.
-		 */
-		stgi();
-		wrmsrq(MSR_EFER, efer & ~EFER_SVME);
-	}
-}
-
 static void svm_emergency_disable_virtualization_cpu(void)
 {
-	kvm_rebooting = true;
-
-	kvm_cpu_svm_disable();
+	wrmsrq(MSR_VM_HSAVE_PA, 0);
 }
 
 static void svm_disable_virtualization_cpu(void)
@@ -505,7 +488,7 @@ static void svm_disable_virtualization_cpu(void)
 	if (tsc_scaling)
 		__svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 
-	kvm_cpu_svm_disable();
+	x86_virt_put_cpu(X86_FEATURE_SVM);
 
 	amd_pmu_disable_virt();
 }
@@ -514,12 +497,12 @@ static int svm_enable_virtualization_cpu(void)
 {
 
 	struct svm_cpu_data *sd;
-	uint64_t efer;
 	int me = raw_smp_processor_id();
+	int r;
 
-	rdmsrq(MSR_EFER, efer);
-	if (efer & EFER_SVME)
-		return -EBUSY;
+	r = x86_virt_get_cpu(X86_FEATURE_SVM);
+	if (r)
+		return r;
 
 	sd = per_cpu_ptr(&svm_data, me);
 	sd->asid_generation = 1;
@@ -527,8 +510,6 @@ static int svm_enable_virtualization_cpu(void)
 	sd->next_asid = sd->max_asid + 1;
 	sd->min_asid = max_sev_asid + 1;
 
-	wrmsrq(MSR_EFER, efer | EFER_SVME);
-
 	wrmsrq(MSR_VM_HSAVE_PA, sd->save_area_pa);
 
 	if (static_cpu_has(X86_FEATURE_TSCRATEMSR)) {
@@ -539,7 +520,6 @@ static int svm_enable_virtualization_cpu(void)
 		__svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 	}
 
-
 	/*
 	 * Get OSVW bits.
 	 *
diff --git a/arch/x86/kvm/svm/vmenter.S b/arch/x86/kvm/svm/vmenter.S
index 3392bcadfb89..d47c5c93c991 100644
--- a/arch/x86/kvm/svm/vmenter.S
+++ b/arch/x86/kvm/svm/vmenter.S
@@ -298,16 +298,16 @@ SYM_FUNC_START(__svm_vcpu_run)
 	RESTORE_GUEST_SPEC_CTRL_BODY
 	RESTORE_HOST_SPEC_CTRL_BODY (%_ASM_SP)
 
-10:	cmpb $0, _ASM_RIP(kvm_rebooting)
+10:	cmpb $0, _ASM_RIP(virt_rebooting)
 	jne 2b
 	ud2
-30:	cmpb $0, _ASM_RIP(kvm_rebooting)
+30:	cmpb $0, _ASM_RIP(virt_rebooting)
 	jne 4b
 	ud2
-50:	cmpb $0, _ASM_RIP(kvm_rebooting)
+50:	cmpb $0, _ASM_RIP(virt_rebooting)
 	jne 6b
 	ud2
-70:	cmpb $0, _ASM_RIP(kvm_rebooting)
+70:	cmpb $0, _ASM_RIP(virt_rebooting)
 	jne 8b
 	ud2
 
@@ -394,7 +394,7 @@ SYM_FUNC_START(__svm_sev_es_vcpu_run)
 	RESTORE_GUEST_SPEC_CTRL_BODY
 	RESTORE_HOST_SPEC_CTRL_BODY %sil
 
-3:	cmpb $0, kvm_rebooting(%rip)
+3:	cmpb $0, virt_rebooting(%rip)
 	jne 2b
 	ud2
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..21e67a47ad4e 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -6,6 +6,7 @@
 #include <linux/misc_cgroup.h>
 #include <linux/mmu_context.h>
 #include <asm/tdx.h>
+#include <asm/virt.h>
 #include "capabilities.h"
 #include "mmu.h"
 #include "x86_ops.h"
@@ -1994,7 +1995,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	 * TDX_SEAMCALL_VMFAILINVALID.
 	 */
 	if (unlikely((vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR)) {
-		KVM_BUG_ON(!kvm_rebooting, vcpu->kvm);
+		KVM_BUG_ON(!virt_rebooting, vcpu->kvm);
 		goto unhandled_exit;
 	}
 
diff --git a/arch/x86/kvm/vmx/vmcs.h b/arch/x86/kvm/vmx/vmcs.h
index b25625314658..2ab6ade006c7 100644
--- a/arch/x86/kvm/vmx/vmcs.h
+++ b/arch/x86/kvm/vmx/vmcs.h
@@ -13,17 +13,6 @@
 
 #define ROL16(val, n) ((u16)(((u16)(val) << (n)) | ((u16)(val) >> (16 - (n)))))
 
-struct vmcs_hdr {
-	u32 revision_id:31;
-	u32 shadow_vmcs:1;
-};
-
-struct vmcs {
-	struct vmcs_hdr hdr;
-	u32 abort;
-	char data[];
-};
-
 DECLARE_PER_CPU(struct vmcs *, current_vmcs);
 
 /*
diff --git a/arch/x86/kvm/vmx/vmenter.S b/arch/x86/kvm/vmx/vmenter.S
index 4426d34811fc..8a481dae9cae 100644
--- a/arch/x86/kvm/vmx/vmenter.S
+++ b/arch/x86/kvm/vmx/vmenter.S
@@ -310,7 +310,7 @@ SYM_INNER_LABEL_ALIGN(vmx_vmexit, SYM_L_GLOBAL)
 	RET
 
 .Lfixup:
-	cmpb $0, _ASM_RIP(kvm_rebooting)
+	cmpb $0, _ASM_RIP(virt_rebooting)
 	jne .Lvmfail
 	ud2
 .Lvmfail:
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 4cbe8c84b636..dd13bae22a1e 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -48,6 +48,7 @@
 #include <asm/msr.h>
 #include <asm/mwait.h>
 #include <asm/spec-ctrl.h>
+#include <asm/virt.h>
 #include <asm/vmx.h>
 
 #include <trace/events/ipi.h>
@@ -577,7 +578,6 @@ noinline void invept_error(unsigned long ext, u64 eptp)
 	vmx_insn_failed("invept failed: ext=0x%lx eptp=%llx\n", ext, eptp);
 }
 
-static DEFINE_PER_CPU(struct vmcs *, vmxarea);
 DEFINE_PER_CPU(struct vmcs *, current_vmcs);
 /*
  * We maintain a per-CPU linked-list of VMCS loaded on that CPU. This is needed
@@ -784,53 +784,17 @@ static int vmx_set_guest_uret_msr(struct vcpu_vmx *vmx,
 	return ret;
 }
 
-/*
- * Disable VMX and clear CR4.VMXE (even if VMXOFF faults)
- *
- * Note, VMXOFF causes a #UD if the CPU is !post-VMXON, but it's impossible to
- * atomically track post-VMXON state, e.g. this may be called in NMI context.
- * Eat all faults as all other faults on VMXOFF faults are mode related, i.e.
- * faults are guaranteed to be due to the !post-VMXON check unless the CPU is
- * magically in RM, VM86, compat mode, or at CPL>0.
- */
-static int kvm_cpu_vmxoff(void)
-{
-	asm goto("1: vmxoff\n\t"
-			  _ASM_EXTABLE(1b, %l[fault])
-			  ::: "cc", "memory" : fault);
-
-	cr4_clear_bits(X86_CR4_VMXE);
-	return 0;
-
-fault:
-	cr4_clear_bits(X86_CR4_VMXE);
-	return -EIO;
-}
-
 void vmx_emergency_disable_virtualization_cpu(void)
 {
 	int cpu = raw_smp_processor_id();
 	struct loaded_vmcs *v;
 
-	kvm_rebooting = true;
-
-	/*
-	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be
-	 * set in task context.  If this races with VMX is disabled by an NMI,
-	 * VMCLEAR and VMXOFF may #UD, but KVM will eat those faults due to
-	 * kvm_rebooting set.
-	 */
-	if (!(__read_cr4() & X86_CR4_VMXE))
-		return;
-
 	list_for_each_entry(v, &per_cpu(loaded_vmcss_on_cpu, cpu),
 			    loaded_vmcss_on_cpu_link) {
 		vmcs_clear(v->vmcs);
 		if (v->shadow_vmcs)
 			vmcs_clear(v->shadow_vmcs);
 	}
-
-	kvm_cpu_vmxoff();
 }
 
 static void __loaded_vmcs_clear(void *arg)
@@ -2928,34 +2892,9 @@ int vmx_check_processor_compat(void)
 	return 0;
 }
 
-static int kvm_cpu_vmxon(u64 vmxon_pointer)
-{
-	u64 msr;
-
-	cr4_set_bits(X86_CR4_VMXE);
-
-	asm goto("1: vmxon %[vmxon_pointer]\n\t"
-			  _ASM_EXTABLE(1b, %l[fault])
-			  : : [vmxon_pointer] "m"(vmxon_pointer)
-			  : : fault);
-	return 0;
-
-fault:
-	WARN_ONCE(1, "VMXON faulted, MSR_IA32_FEAT_CTL (0x3a) = 0x%llx\n",
-		  rdmsrq_safe(MSR_IA32_FEAT_CTL, &msr) ? 0xdeadbeef : msr);
-	cr4_clear_bits(X86_CR4_VMXE);
-
-	return -EFAULT;
-}
-
 int vmx_enable_virtualization_cpu(void)
 {
 	int cpu = raw_smp_processor_id();
-	u64 phys_addr = __pa(per_cpu(vmxarea, cpu));
-	int r;
-
-	if (cr4_read_shadow() & X86_CR4_VMXE)
-		return -EBUSY;
 
 	/*
 	 * This can happen if we hot-added a CPU but failed to allocate
@@ -2964,15 +2903,7 @@ int vmx_enable_virtualization_cpu(void)
 	if (kvm_is_using_evmcs() && !hv_get_vp_assist_page(cpu))
 		return -EFAULT;
 
-	intel_pt_handle_vmx(1);
-
-	r = kvm_cpu_vmxon(phys_addr);
-	if (r) {
-		intel_pt_handle_vmx(0);
-		return r;
-	}
-
-	return 0;
+	return x86_virt_get_cpu(X86_FEATURE_VMX);
 }
 
 static void vmclear_local_loaded_vmcss(void)
@@ -2989,12 +2920,9 @@ void vmx_disable_virtualization_cpu(void)
 {
 	vmclear_local_loaded_vmcss();
 
-	if (kvm_cpu_vmxoff())
-		kvm_spurious_fault();
+	x86_virt_put_cpu(X86_FEATURE_VMX);
 
 	hv_reset_evmcs();
-
-	intel_pt_handle_vmx(0);
 }
 
 struct vmcs *alloc_vmcs_cpu(bool shadow, int cpu, gfp_t flags)
@@ -3072,47 +3000,6 @@ int alloc_loaded_vmcs(struct loaded_vmcs *loaded_vmcs)
 	return -ENOMEM;
 }
 
-static void free_kvm_area(void)
-{
-	int cpu;
-
-	for_each_possible_cpu(cpu) {
-		free_vmcs(per_cpu(vmxarea, cpu));
-		per_cpu(vmxarea, cpu) = NULL;
-	}
-}
-
-static __init int alloc_kvm_area(void)
-{
-	int cpu;
-
-	for_each_possible_cpu(cpu) {
-		struct vmcs *vmcs;
-
-		vmcs = alloc_vmcs_cpu(false, cpu, GFP_KERNEL);
-		if (!vmcs) {
-			free_kvm_area();
-			return -ENOMEM;
-		}
-
-		/*
-		 * When eVMCS is enabled, alloc_vmcs_cpu() sets
-		 * vmcs->revision_id to KVM_EVMCS_VERSION instead of
-		 * revision_id reported by MSR_IA32_VMX_BASIC.
-		 *
-		 * However, even though not explicitly documented by
-		 * TLFS, VMXArea passed as VMXON argument should
-		 * still be marked with revision_id reported by
-		 * physical CPU.
-		 */
-		if (kvm_is_using_evmcs())
-			vmcs->hdr.revision_id = vmx_basic_vmcs_revision_id(vmcs_config.basic);
-
-		per_cpu(vmxarea, cpu) = vmcs;
-	}
-	return 0;
-}
-
 static void fix_pmode_seg(struct kvm_vcpu *vcpu, int seg,
 		struct kvm_segment *save)
 {
@@ -8380,8 +8267,6 @@ void vmx_hardware_unsetup(void)
 
 	if (nested)
 		nested_vmx_hardware_unsetup();
-
-	free_kvm_area();
 }
 
 void vmx_vm_destroy(struct kvm *kvm)
@@ -8686,10 +8571,6 @@ __init int vmx_hardware_setup(void)
 			return r;
 	}
 
-	r = alloc_kvm_area();
-	if (r && nested)
-		nested_vmx_hardware_unsetup();
-
 	kvm_set_posted_intr_wakeup_handler(pi_wakeup_handler);
 
 	/*
@@ -8715,7 +8596,7 @@ __init int vmx_hardware_setup(void)
 
 	kvm_caps.inapplicable_quirks &= ~KVM_X86_QUIRK_IGNORE_GUEST_PAT;
 
-	return r;
+	return 0;
 }
 
 void vmx_exit(void)
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 80cb882f19e2..f650f79d3d5a 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -83,6 +83,8 @@
 #include <asm/intel_pt.h>
 #include <asm/emulate_prefix.h>
 #include <asm/sgx.h>
+#include <asm/virt.h>
+
 #include <clocksource/hyperv_timer.h>
 
 #define CREATE_TRACE_POINTS
@@ -694,9 +696,6 @@ static void drop_user_return_notifiers(void)
 		kvm_on_user_return(&msrs->urn);
 }
 
-__visible bool kvm_rebooting;
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
-
 /*
  * Handle a fault on a hardware virtualization (VMX or SVM) instruction.
  *
@@ -707,7 +706,7 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
 noinstr void kvm_spurious_fault(void)
 {
 	/* Fault while not rebooting.  We want the trace. */
-	BUG_ON(!kvm_rebooting);
+	BUG_ON(!virt_rebooting);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_spurious_fault);
 
@@ -12999,12 +12998,12 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_vcpu_deliver_sipi_vector);
 
 void kvm_arch_enable_virtualization(void)
 {
-	cpu_emergency_register_virt_callback(kvm_x86_ops.emergency_disable_virtualization_cpu);
+	x86_virt_register_emergency_callback(kvm_x86_ops.emergency_disable_virtualization_cpu);
 }
 
 void kvm_arch_disable_virtualization(void)
 {
-	cpu_emergency_unregister_virt_callback(kvm_x86_ops.emergency_disable_virtualization_cpu);
+	x86_virt_unregister_emergency_callback(kvm_x86_ops.emergency_disable_virtualization_cpu);
 }
 
 int kvm_arch_enable_virtualization_cpu(void)
@@ -13106,11 +13105,11 @@ int kvm_arch_enable_virtualization_cpu(void)
 void kvm_arch_shutdown(void)
 {
 	/*
-	 * Set kvm_rebooting to indicate that KVM has asynchronously disabled
+	 * Set virt_rebooting to indicate that KVM has asynchronously disabled
 	 * hardware virtualization, i.e. that relevant errors and exceptions
 	 * aren't entirely unexpected.
 	 */
-	kvm_rebooting = true;
+	virt_rebooting = true;
 }
 
 void kvm_arch_disable_virtualization_cpu(void)
@@ -13127,7 +13126,7 @@ void kvm_arch_disable_virtualization_cpu(void)
 	 * disable virtualization arrives.  Handle the extreme edge case here
 	 * instead of trying to account for it in the normal flows.
 	 */
-	if (in_task() || WARN_ON_ONCE(!kvm_rebooting))
+	if (in_task() || WARN_ON_ONCE(!virt_rebooting))
 		drop_user_return_notifiers();
 	else
 		__module_get(THIS_MODULE);
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 40993348a967..fdab0ad49098 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -54,7 +54,6 @@ struct kvm_host_values {
 	u64 arch_capabilities;
 };
 
-extern bool kvm_rebooting;
 void kvm_spurious_fault(void);
 
 #define SIZE_OF_MEMSLOTS_HASHTABLE \
diff --git a/arch/x86/virt/Makefile b/arch/x86/virt/Makefile
index ea343fc392dc..6e485751650c 100644
--- a/arch/x86/virt/Makefile
+++ b/arch/x86/virt/Makefile
@@ -1,2 +1,4 @@
 # SPDX-License-Identifier: GPL-2.0-only
 obj-y	+= svm/ vmx/
+
+obj-$(subst m,y,$(CONFIG_KVM_X86)) += hw.o
\ No newline at end of file
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
new file mode 100644
index 000000000000..986e780cf438
--- /dev/null
+++ b/arch/x86/virt/hw.c
@@ -0,0 +1,340 @@
+// SPDX-License-Identifier: GPL-2.0-only
+#include <linux/cpu.h>
+#include <linux/cpumask.h>
+#include <linux/errno.h>
+#include <linux/kvm_types.h>
+#include <linux/list.h>
+#include <linux/percpu.h>
+
+#include <asm/perf_event.h>
+#include <asm/processor.h>
+#include <asm/virt.h>
+#include <asm/vmx.h>
+
+static int x86_virt_feature __ro_after_init;
+
+__visible bool virt_rebooting;
+EXPORT_SYMBOL_GPL(virt_rebooting);
+
+static DEFINE_PER_CPU(int, virtualization_nr_users);
+
+static cpu_emergency_virt_cb __rcu *kvm_emergency_callback;
+
+void x86_virt_register_emergency_callback(cpu_emergency_virt_cb *callback)
+{
+	if (WARN_ON_ONCE(rcu_access_pointer(kvm_emergency_callback)))
+		return;
+
+	rcu_assign_pointer(kvm_emergency_callback, callback);
+}
+EXPORT_SYMBOL_FOR_MODULES(x86_virt_register_emergency_callback, "kvm");
+
+void x86_virt_unregister_emergency_callback(cpu_emergency_virt_cb *callback)
+{
+	if (WARN_ON_ONCE(rcu_access_pointer(kvm_emergency_callback) != callback))
+		return;
+
+	rcu_assign_pointer(kvm_emergency_callback, NULL);
+	synchronize_rcu();
+}
+EXPORT_SYMBOL_FOR_MODULES(x86_virt_unregister_emergency_callback, "kvm");
+
+static void x86_virt_invoke_kvm_emergency_callback(void)
+{
+	cpu_emergency_virt_cb *kvm_callback;
+
+	kvm_callback = rcu_dereference(kvm_emergency_callback);
+	if (kvm_callback)
+		kvm_callback();
+}
+
+#if IS_ENABLED(CONFIG_KVM_INTEL)
+static DEFINE_PER_CPU(struct vmcs *, root_vmcs);
+
+static int x86_virt_cpu_vmxon(void)
+{
+	u64 vmxon_pointer = __pa(per_cpu(root_vmcs, raw_smp_processor_id()));
+	u64 msr;
+
+	cr4_set_bits(X86_CR4_VMXE);
+
+	asm goto("1: vmxon %[vmxon_pointer]\n\t"
+			  _ASM_EXTABLE(1b, %l[fault])
+			  : : [vmxon_pointer] "m"(vmxon_pointer)
+			  : : fault);
+	return 0;
+
+fault:
+	WARN_ONCE(1, "VMXON faulted, MSR_IA32_FEAT_CTL (0x3a) = 0x%llx\n",
+		  rdmsrq_safe(MSR_IA32_FEAT_CTL, &msr) ? 0xdeadbeef : msr);
+	cr4_clear_bits(X86_CR4_VMXE);
+
+	return -EFAULT;
+}
+
+static int x86_vmx_get_cpu(void)
+{
+	int r;
+
+	if (cr4_read_shadow() & X86_CR4_VMXE)
+		return -EBUSY;
+
+	intel_pt_handle_vmx(1);
+
+	r = x86_virt_cpu_vmxon();
+	if (r) {
+		intel_pt_handle_vmx(0);
+		return r;
+	}
+
+	return 0;
+}
+
+/*
+ * Disable VMX and clear CR4.VMXE (even if VMXOFF faults)
+ *
+ * Note, VMXOFF causes a #UD if the CPU is !post-VMXON, but it's impossible to
+ * atomically track post-VMXON state, e.g. this may be called in NMI context.
+ * Eat all faults as all other faults on VMXOFF faults are mode related, i.e.
+ * faults are guaranteed to be due to the !post-VMXON check unless the CPU is
+ * magically in RM, VM86, compat mode, or at CPL>0.
+ */
+static int x86_vmx_put_cpu(void)
+{
+	int r = -EIO;
+
+	asm goto("1: vmxoff\n\t"
+		 _ASM_EXTABLE(1b, %l[fault])
+		 ::: "cc", "memory" : fault);
+	r = 0;
+
+fault:
+	cr4_clear_bits(X86_CR4_VMXE);
+	intel_pt_handle_vmx(0);
+	return r;
+}
+
+static int x86_vmx_emergency_disable_virtualization_cpu(void)
+{
+	virt_rebooting = true;
+
+	/*
+	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be
+	 * set in task context.  If this races with VMX being disabled via NMI,
+	 * VMCLEAR and VMXOFF may #UD, but the kernel will eat those faults due
+	 * to virt_rebooting being set.
+	 */
+	if (!(__read_cr4() & X86_CR4_VMXE))
+		return -ENOENT;
+
+	x86_virt_invoke_kvm_emergency_callback();
+
+	x86_vmx_put_cpu();
+	return 0;
+}
+
+static __init void x86_vmx_exit(void)
+{
+	int cpu;
+
+	for_each_possible_cpu(cpu) {
+		free_page((unsigned long)per_cpu(root_vmcs, cpu));
+		per_cpu(root_vmcs, cpu) = NULL;
+	}
+}
+
+static __init int x86_vmx_init(void)
+{
+	u64 basic_msr;
+	u32 rev_id;
+	int cpu;
+
+	if (!cpu_feature_enabled(X86_FEATURE_VMX))
+		return -EOPNOTSUPP;
+
+	rdmsrq(MSR_IA32_VMX_BASIC, basic_msr);
+
+	/* IA-32 SDM Vol 3B: VMCS size is never greater than 4kB. */
+	if (WARN_ON_ONCE(vmx_basic_vmcs_size(basic_msr) > PAGE_SIZE))
+		return -EIO;
+
+	/*
+	 * Even if eVMCS is enabled (or will be enabled?), and even though not
+	 * explicitly documented by TLFS, the root VMCS  passed to VMXON should
+	 * still be marked with the revision_id reported by the physical CPU.
+	 */
+	rev_id = vmx_basic_vmcs_revision_id(basic_msr);
+
+	for_each_possible_cpu(cpu) {
+		int node = cpu_to_node(cpu);
+		struct page *page;
+		struct vmcs *vmcs;
+
+		page = __alloc_pages_node(node, GFP_KERNEL | __GFP_ZERO , 0);
+		if (!page) {
+			x86_vmx_exit();
+			return -ENOMEM;
+		}
+
+		vmcs = page_address(page);
+		vmcs->hdr.revision_id = rev_id;
+		per_cpu(root_vmcs, cpu) = vmcs;
+	}
+
+	return 0;
+}
+#else
+static int x86_vmx_get_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static int x86_vmx_put_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static int x86_vmx_emergency_disable_virtualization_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static __init int x86_vmx_init(void) { return -EOPNOTSUPP; }
+#endif
+
+#if IS_ENABLED(CONFIG_KVM_AMD)
+static int x86_svm_get_cpu(void)
+{
+	u64 efer;
+
+	rdmsrq(MSR_EFER, efer);
+	if (efer & EFER_SVME)
+		return -EBUSY;
+
+	wrmsrq(MSR_EFER, efer | EFER_SVME);
+	return 0;
+}
+
+static int x86_svm_put_cpu(void)
+{
+	int r = -EIO;
+	u64 efer;
+
+	/*
+	 * Force GIF=1 prior to disabling SVM, e.g. to ensure INIT and
+	 * NMI aren't blocked.
+	 */
+	asm goto("1: stgi\n\t"
+		 _ASM_EXTABLE(1b, %l[fault])
+		 ::: "memory" : fault);
+	r = 0;
+
+fault:
+	rdmsrq(MSR_EFER, efer);
+	wrmsrq(MSR_EFER, efer & ~EFER_SVME);
+	return r;
+}
+
+static int x86_svm_emergency_disable_virtualization_cpu(void)
+{
+	u64 efer;
+
+	virt_rebooting = true;
+
+	rdmsrq(MSR_EFER, efer);
+	if (!(efer & EFER_SVME))
+		return -ENOENT;
+
+	x86_virt_invoke_kvm_emergency_callback();
+
+	return x86_svm_put_cpu();
+}
+
+static __init int x86_svm_init(void)
+{
+	if (!cpu_feature_enabled(X86_FEATURE_SVM))
+		return -EOPNOTSUPP;
+
+	return 0;
+}
+
+#else
+static int x86_svm_get_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static int x86_svm_put_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static int x86_svm_emergency_disable_virtualization_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static __init int x86_svm_init(void) { return -EOPNOTSUPP; }
+#endif
+
+#define x86_virt_call(fn)				\
+({							\
+	int __r;					\
+							\
+	if (IS_ENABLED(CONFIG_KVM_INTEL) &&		\
+	    cpu_feature_enabled(X86_FEATURE_VMX))	\
+		__r = x86_vmx_##fn();			\
+	else if (IS_ENABLED(CONFIG_KVM_AMD) &&		\
+		 cpu_feature_enabled(X86_FEATURE_SVM))	\
+		__r = x86_svm_##fn();			\
+	else						\
+		__r = -EOPNOTSUPP;			\
+							\
+	__r;						\
+})
+
+int x86_virt_get_cpu(int feat)
+{
+	int r;
+
+	if (!x86_virt_feature || x86_virt_feature != feat)
+		return -EOPNOTSUPP;
+
+	if (this_cpu_inc_return(virtualization_nr_users) > 1)
+		return 0;
+
+	r = x86_virt_call(get_cpu);
+	if (r)
+		WARN_ON_ONCE(this_cpu_dec_return(virtualization_nr_users));
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(x86_virt_get_cpu);
+
+void x86_virt_put_cpu(int feat)
+{
+	if (WARN_ON_ONCE(!this_cpu_read(virtualization_nr_users)) ||
+	    this_cpu_dec_return(virtualization_nr_users))
+		return;
+
+	BUG_ON(x86_virt_call(put_cpu) && !virt_rebooting);
+}
+EXPORT_SYMBOL_GPL(x86_virt_put_cpu);
+
+/*
+ * Disable virtualization, i.e. VMX or SVM, to ensure INIT is recognized during
+ * reboot.  VMX blocks INIT if the CPU is post-VMXON, and SVM blocks INIT if
+ * GIF=0, i.e. if the crash occurred between CLGI and STGI.
+ */
+int x86_virt_emergency_disable_virtualization_cpu(void)
+{
+	if (!x86_virt_feature)
+		return -EOPNOTSUPP;
+
+	/*
+	 * IRQs must be disabled as virtualization is enabled in hardware via
+	 * function call IPIs, i.e. IRQs need to be disabled to guarantee
+	 * virtualization stays disabled.
+	 */
+	lockdep_assert_irqs_disabled();
+
+	/*
+	 * Do the NMI shootdown even if virtualization is off on _this_ CPU, as
+	 * other CPUs may have virtualization enabled.
+	 *
+	 * TODO: Track whether or not virtualization might be enabled on other
+	 *	 CPUs?  May not be worth avoiding the NMI shootdown...
+	 */
+	(void)x86_virt_call(emergency_disable_virtualization_cpu);
+	return 0;
+}
+
+void __init x86_virt_init(void)
+{
+	bool is_vmx = !x86_vmx_init();
+	bool is_svm = !x86_svm_init();
+
+	if (!is_vmx && !is_svm)
+		return;
+
+	if (WARN_ON_ONCE(is_vmx && is_svm))
+		return;
+
+	x86_virt_feature = is_vmx ? X86_FEATURE_VMX : X86_FEATURE_SVM;
+}

---

## [4] Sean Christopherson — 2025-12-05
*Subject: [PATCH v2 3/7] KVM: x86/tdx: Do VMXON and TDX-Module initialization
 during subsys init*

Now that VMXON can be done without bouncing through KVM, do TDX-Module
initialization during subsys init (specifically before module_init() so
that it runs before KVM when both are built-in).  Aside from the obvious
benefits of separating core TDX code from KVM, this will allow tagging a
pile of TDX functions and globals as being __init and __ro_after_init.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 Documentation/arch/x86/tdx.rst |  26 -----
 arch/x86/include/asm/tdx.h     |   4 -
 arch/x86/kvm/vmx/tdx.c         | 169 ++++++--------------------------
 arch/x86/virt/vmx/tdx/tdx.c    | 170 ++++++++++++++++++---------------
 arch/x86/virt/vmx/tdx/tdx.h    |   8 --
 5 files changed, 124 insertions(+), 253 deletions(-)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 61670e7df2f7..2e0a15d6f7d1 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -60,32 +60,6 @@ Besides initializing the TDX module, a per-cpu initialization SEAMCALL
 must be done on one cpu before any other SEAMCALLs can be made on that
 cpu.
 
-The kernel provides two functions, tdx_enable() and tdx_cpu_enable() to
-allow the user of TDX to enable the TDX module and enable TDX on local
-cpu respectively.
-
-Making SEAMCALL requires VMXON has been done on that CPU.  Currently only
-KVM implements VMXON.  For now both tdx_enable() and tdx_cpu_enable()
-don't do VMXON internally (not trivial), but depends on the caller to
-guarantee that.
-
-To enable TDX, the caller of TDX should: 1) temporarily disable CPU
-hotplug; 2) do VMXON and tdx_enable_cpu() on all online cpus; 3) call
-tdx_enable().  For example::
-
-        cpus_read_lock();
-        on_each_cpu(vmxon_and_tdx_cpu_enable());
-        ret = tdx_enable();
-        cpus_read_unlock();
-        if (ret)
-                goto no_tdx;
-        // TDX is ready to use
-
-And the caller of TDX must guarantee the tdx_cpu_enable() has been
-successfully done on any cpu before it wants to run any other SEAMCALL.
-A typical usage is do both VMXON and tdx_cpu_enable() in CPU hotplug
-online callback, and refuse to online if tdx_cpu_enable() fails.
-
 User can consult dmesg to see whether the TDX module has been initialized.
 
 If the TDX module is initialized successfully, dmesg shows something
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 6b338d7f01b7..a149740b24e8 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -145,8 +145,6 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 #define seamcall(_fn, _args)		sc_retry(__seamcall, (_fn), (_args))
 #define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
 #define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
-int tdx_cpu_enable(void);
-int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
@@ -223,8 +221,6 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 #else
 static inline void tdx_init(void) { }
-static inline int tdx_cpu_enable(void) { return -ENODEV; }
-static inline int tdx_enable(void)  { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 21e67a47ad4e..d0161dc3d184 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -59,7 +59,7 @@ module_param_named(tdx, enable_tdx, bool, 0444);
 #define TDX_SHARED_BIT_PWL_5 gpa_to_gfn(BIT_ULL(51))
 #define TDX_SHARED_BIT_PWL_4 gpa_to_gfn(BIT_ULL(47))
 
-static enum cpuhp_state tdx_cpuhp_state;
+static enum cpuhp_state tdx_cpuhp_state __ro_after_init;
 
 static const struct tdx_sys_info *tdx_sysinfo;
 
@@ -3304,17 +3304,7 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 
 static int tdx_online_cpu(unsigned int cpu)
 {
-	unsigned long flags;
-	int r;
-
-	/* Sanity check CPU is already in post-VMXON */
-	WARN_ON_ONCE(!(cr4_read_shadow() & X86_CR4_VMXE));
-
-	local_irq_save(flags);
-	r = tdx_cpu_enable();
-	local_irq_restore(flags);
-
-	return r;
+	return 0;
 }
 
 static int tdx_offline_cpu(unsigned int cpu)
@@ -3353,51 +3343,6 @@ static int tdx_offline_cpu(unsigned int cpu)
 	return -EBUSY;
 }
 
-static void __do_tdx_cleanup(void)
-{
-	/*
-	 * Once TDX module is initialized, it cannot be disabled and
-	 * re-initialized again w/o runtime update (which isn't
-	 * supported by kernel).  Only need to remove the cpuhp here.
-	 * The TDX host core code tracks TDX status and can handle
-	 * 'multiple enabling' scenario.
-	 */
-	WARN_ON_ONCE(!tdx_cpuhp_state);
-	cpuhp_remove_state_nocalls_cpuslocked(tdx_cpuhp_state);
-	tdx_cpuhp_state = 0;
-}
-
-static void __tdx_cleanup(void)
-{
-	cpus_read_lock();
-	__do_tdx_cleanup();
-	cpus_read_unlock();
-}
-
-static int __init __do_tdx_bringup(void)
-{
-	int r;
-
-	/*
-	 * TDX-specific cpuhp callback to call tdx_cpu_enable() on all
-	 * online CPUs before calling tdx_enable(), and on any new
-	 * going-online CPU to make sure it is ready for TDX guest.
-	 */
-	r = cpuhp_setup_state_cpuslocked(CPUHP_AP_ONLINE_DYN,
-					 "kvm/cpu/tdx:online",
-					 tdx_online_cpu, tdx_offline_cpu);
-	if (r < 0)
-		return r;
-
-	tdx_cpuhp_state = r;
-
-	r = tdx_enable();
-	if (r)
-		__do_tdx_cleanup();
-
-	return r;
-}
-
 static int __init __tdx_bringup(void)
 {
 	const struct tdx_sys_info_td_conf *td_conf;
@@ -3417,34 +3362,18 @@ static int __init __tdx_bringup(void)
 		}
 	}
 
-	/*
-	 * Enabling TDX requires enabling hardware virtualization first,
-	 * as making SEAMCALLs requires CPU being in post-VMXON state.
-	 */
-	r = kvm_enable_virtualization();
-	if (r)
-		return r;
-
-	cpus_read_lock();
-	r = __do_tdx_bringup();
-	cpus_read_unlock();
-
-	if (r)
-		goto tdx_bringup_err;
-
-	r = -EINVAL;
 	/* Get TDX global information for later use */
 	tdx_sysinfo = tdx_get_sysinfo();
-	if (WARN_ON_ONCE(!tdx_sysinfo))
-		goto get_sysinfo_err;
+	if (!tdx_sysinfo)
+		return -EINVAL;
 
 	/* Check TDX module and KVM capabilities */
 	if (!tdx_get_supported_attrs(&tdx_sysinfo->td_conf) ||
 	    !tdx_get_supported_xfam(&tdx_sysinfo->td_conf))
-		goto get_sysinfo_err;
+		return -EINVAL;
 
 	if (!(tdx_sysinfo->features.tdx_features0 & MD_FIELD_ID_FEATURES0_TOPOLOGY_ENUM))
-		goto get_sysinfo_err;
+		return -EINVAL;
 
 	/*
 	 * TDX has its own limit of maximum vCPUs it can support for all
@@ -3479,34 +3408,31 @@ static int __init __tdx_bringup(void)
 	if (td_conf->max_vcpus_per_td < num_present_cpus()) {
 		pr_err("Disable TDX: MAX_VCPU_PER_TD (%u) smaller than number of logical CPUs (%u).\n",
 				td_conf->max_vcpus_per_td, num_present_cpus());
-		goto get_sysinfo_err;
+		return -EINVAL;
 	}
 
 	if (misc_cg_set_capacity(MISC_CG_RES_TDX, tdx_get_nr_guest_keyids()))
-		goto get_sysinfo_err;
+		return -EINVAL;
 
 	/*
-	 * Leave hardware virtualization enabled after TDX is enabled
-	 * successfully.  TDX CPU hotplug depends on this.
+	 * TDX-specific cpuhp callback to disallow offlining the last CPU in a
+	 * packing while KVM is running one or more TDs.  Reclaiming HKIDs
+	 * requires doing PAGE.WBINVD on every package, i.e. offlining all CPUs
+	 * of a package would prevent reclaiming the HKID.
 	 */
+	r = cpuhp_setup_state(CPUHP_AP_ONLINE_DYN, "kvm/cpu/tdx:online",
+			      tdx_online_cpu, tdx_offline_cpu);
+	if (r < 0)
+		goto err_cpuhup;
+
+	tdx_cpuhp_state = r;
 	return 0;
 
-get_sysinfo_err:
-	__tdx_cleanup();
-tdx_bringup_err:
-	kvm_disable_virtualization();
+err_cpuhup:
+	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
 	return r;
 }
 
-void tdx_cleanup(void)
-{
-	if (enable_tdx) {
-		misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
-		__tdx_cleanup();
-		kvm_disable_virtualization();
-	}
-}
-
 int __init tdx_bringup(void)
 {
 	int r, i;
@@ -3538,56 +3464,14 @@ int __init tdx_bringup(void)
 		goto success_disable_tdx;
 	}
 
-	if (!cpu_feature_enabled(X86_FEATURE_MOVDIR64B)) {
-		pr_err("tdx: MOVDIR64B is required for TDX\n");
-		goto success_disable_tdx;
-	}
-
-	if (!cpu_feature_enabled(X86_FEATURE_SELFSNOOP)) {
-		pr_err("Self-snoop is required for TDX\n");
-		goto success_disable_tdx;
-	}
-
 	if (!cpu_feature_enabled(X86_FEATURE_TDX_HOST_PLATFORM)) {
-		pr_err("tdx: no TDX private KeyIDs available\n");
+		pr_err("TDX not supported by the host platform\n");
 		goto success_disable_tdx;
 	}
 
-	if (!enable_virt_at_load) {
-		pr_err("tdx: tdx requires kvm.enable_virt_at_load=1\n");
-		goto success_disable_tdx;
-	}
-
-	/*
-	 * Ideally KVM should probe whether TDX module has been loaded
-	 * first and then try to bring it up.  But TDX needs to use SEAMCALL
-	 * to probe whether the module is loaded (there is no CPUID or MSR
-	 * for that), and making SEAMCALL requires enabling virtualization
-	 * first, just like the rest steps of bringing up TDX module.
-	 *
-	 * So, for simplicity do everything in __tdx_bringup(); the first
-	 * SEAMCALL will return -ENODEV when the module is not loaded.  The
-	 * only complication is having to make sure that initialization
-	 * SEAMCALLs don't return TDX_SEAMCALL_VMFAILINVALID in other
-	 * cases.
-	 */
 	r = __tdx_bringup();
-	if (r) {
-		/*
-		 * Disable TDX only but don't fail to load module if the TDX
-		 * module could not be loaded.  No need to print message saying
-		 * "module is not loaded" because it was printed when the first
-		 * SEAMCALL failed.  Don't bother unwinding the S-EPT hooks or
-		 * vm_size, as kvm_x86_ops have already been finalized (and are
-		 * intentionally not exported).  The S-EPT code is unreachable,
-		 * and allocating a few more bytes per VM in a should-be-rare
-		 * failure scenario is a non-issue.
-		 */
-		if (r == -ENODEV)
-			goto success_disable_tdx;
-
+	if (r)
 		enable_tdx = 0;
-	}
 
 	return r;
 
@@ -3596,6 +3480,15 @@ int __init tdx_bringup(void)
 	return 0;
 }
 
+void tdx_cleanup(void)
+{
+	if (!enable_tdx)
+		return;
+
+	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
+	cpuhp_remove_state(tdx_cpuhp_state);
+}
+
 void __init tdx_hardware_setup(void)
 {
 	KVM_SANITY_CHECK_VM_STRUCT_SIZE(kvm_tdx);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index eac403248462..8282c9b1b48b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -28,6 +28,7 @@
 #include <linux/log2.h>
 #include <linux/acpi.h>
 #include <linux/suspend.h>
+#include <linux/syscore_ops.h>
 #include <linux/idr.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
@@ -38,6 +39,7 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+#include <asm/virt.h>
 #include "tdx.h"
 
 static u32 tdx_global_keyid __ro_after_init;
@@ -50,13 +52,11 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
-static enum tdx_module_status_t tdx_module_status;
-static DEFINE_MUTEX(tdx_module_lock);
-
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo;
+static bool tdx_module_initialized;
 
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
@@ -141,26 +141,15 @@ static int try_init_module_global(void)
 }
 
 /**
- * tdx_cpu_enable - Enable TDX on local cpu
- *
- * Do one-time TDX module per-cpu initialization SEAMCALL (and TDX module
- * global initialization SEAMCALL if not done) on local cpu to make this
- * cpu be ready to run any other SEAMCALLs.
- *
- * Always call this function via IPI function calls.
- *
- * Return 0 on success, otherwise errors.
+ * Enable VMXON and then do one-time TDX module per-cpu initialization SEAMCALL
+ * (and TDX module global initialization SEAMCALL if not done) on local cpu to
+ * make this cpu be ready to run any other SEAMCALLs.
  */
-int tdx_cpu_enable(void)
+static int tdx_cpu_enable(void)
 {
 	struct tdx_module_args args = {};
 	int ret;
 
-	if (!boot_cpu_has(X86_FEATURE_TDX_HOST_PLATFORM))
-		return -ENODEV;
-
-	lockdep_assert_irqs_disabled();
-
 	if (__this_cpu_read(tdx_lp_initialized))
 		return 0;
 
@@ -181,7 +170,56 @@ int tdx_cpu_enable(void)
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(tdx_cpu_enable);
+
+static int tdx_online_cpu(unsigned int cpu)
+{
+	int ret;
+
+	guard(irqsave)();
+
+	ret = x86_virt_get_cpu(X86_FEATURE_VMX);
+	if (ret)
+		return ret;
+
+	ret = tdx_cpu_enable();
+	if (ret)
+		x86_virt_put_cpu(X86_FEATURE_VMX);
+
+	return ret;
+}
+
+static int tdx_offline_cpu(unsigned int cpu)
+{
+	x86_virt_put_cpu(X86_FEATURE_VMX);
+	return 0;
+}
+
+static void tdx_shutdown_cpu(void *ign)
+{
+	x86_virt_put_cpu(X86_FEATURE_VMX);
+}
+
+static void tdx_shutdown(void)
+{
+	on_each_cpu(tdx_shutdown_cpu, NULL, 1);
+}
+
+static int tdx_suspend(void)
+{
+	x86_virt_put_cpu(X86_FEATURE_VMX);
+	return 0;
+}
+
+static void tdx_resume(void)
+{
+	WARN_ON_ONCE(x86_virt_get_cpu(X86_FEATURE_VMX));
+}
+
+static struct syscore_ops tdx_syscore_ops = {
+	.suspend = tdx_suspend,
+	.resume = tdx_resume,
+	.shutdown = tdx_shutdown,
+};
 
 /*
  * Add a memory region as a TDX memory block.  The caller must make sure
@@ -1156,67 +1194,50 @@ static int init_tdx_module(void)
 	goto out_put_tdxmem;
 }
 
-static int __tdx_enable(void)
+static int tdx_enable(void)
 {
+	enum cpuhp_state state;
 	int ret;
 
+	if (!cpu_feature_enabled(X86_FEATURE_TDX_HOST_PLATFORM)) {
+		pr_err("TDX not supported by the host platform\n");
+		return -ENODEV;
+	}
+
+	if (!cpu_feature_enabled(X86_FEATURE_XSAVE)) {
+		pr_err("XSAVE is required for TDX\n");
+		return -EINVAL;
+	}
+
+	if (!cpu_feature_enabled(X86_FEATURE_MOVDIR64B)) {
+		pr_err("MOVDIR64B is required for TDX\n");
+		return -EINVAL;
+	}
+
+	if (!cpu_feature_enabled(X86_FEATURE_SELFSNOOP)) {
+		pr_err("Self-snoop is required for TDX\n");
+		return -ENODEV;
+	}
+
+	state = cpuhp_setup_state(CPUHP_AP_ONLINE_DYN, "virt/tdx:online",
+				  tdx_online_cpu, tdx_offline_cpu);
+	if (state < 0)
+		return state;
+
 	ret = init_tdx_module();
 	if (ret) {
-		pr_err("module initialization failed (%d)\n", ret);
-		tdx_module_status = TDX_MODULE_ERROR;
+		pr_err("TDX-Module initialization failed (%d)\n", ret);
+		cpuhp_remove_state(state);
 		return ret;
 	}
 
-	pr_info("module initialized\n");
-	tdx_module_status = TDX_MODULE_INITIALIZED;
+	register_syscore_ops(&tdx_syscore_ops);
 
+	tdx_module_initialized = true;
+	pr_info("TDX-Module initialized\n");
 	return 0;
 }
-
-/**
- * tdx_enable - Enable TDX module to make it ready to run TDX guests
- *
- * This function assumes the caller has: 1) held read lock of CPU hotplug
- * lock to prevent any new cpu from becoming online; 2) done both VMXON
- * and tdx_cpu_enable() on all online cpus.
- *
- * This function requires there's at least one online cpu for each CPU
- * package to succeed.
- *
- * This function can be called in parallel by multiple callers.
- *
- * Return 0 if TDX is enabled successfully, otherwise error.
- */
-int tdx_enable(void)
-{
-	int ret;
-
-	if (!boot_cpu_has(X86_FEATURE_TDX_HOST_PLATFORM))
-		return -ENODEV;
-
-	lockdep_assert_cpus_held();
-
-	mutex_lock(&tdx_module_lock);
-
-	switch (tdx_module_status) {
-	case TDX_MODULE_UNINITIALIZED:
-		ret = __tdx_enable();
-		break;
-	case TDX_MODULE_INITIALIZED:
-		/* Already initialized, great, tell the caller. */
-		ret = 0;
-		break;
-	default:
-		/* Failed to initialize in the previous attempts */
-		ret = -EINVAL;
-		break;
-	}
-
-	mutex_unlock(&tdx_module_lock);
-
-	return ret;
-}
-EXPORT_SYMBOL_GPL(tdx_enable);
+subsys_initcall(tdx_enable);
 
 static bool is_pamt_page(unsigned long phys)
 {
@@ -1467,15 +1488,10 @@ void __init tdx_init(void)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void)
 {
-	const struct tdx_sys_info *p = NULL;
+	if (!tdx_module_initialized)
+		return NULL;
 
-	/* Make sure all fields in @tdx_sysinfo have been populated */
-	mutex_lock(&tdx_module_lock);
-	if (tdx_module_status == TDX_MODULE_INITIALIZED)
-		p = (const struct tdx_sys_info *)&tdx_sysinfo;
-	mutex_unlock(&tdx_module_lock);
-
-	return p;
+	return (const struct tdx_sys_info *)&tdx_sysinfo;
 }
 EXPORT_SYMBOL_GPL(tdx_get_sysinfo);
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 82bb82be8567..dde219c823b4 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -91,14 +91,6 @@ struct tdmr_info {
  * Do not put any hardware-defined TDX structure representations below
  * this comment!
  */
-
-/* Kernel defined TDX module status during module initialization. */
-enum tdx_module_status_t {
-	TDX_MODULE_UNINITIALIZED,
-	TDX_MODULE_INITIALIZED,
-	TDX_MODULE_ERROR
-};
-
 struct tdx_memblock {
 	struct list_head list;
 	unsigned long start_pfn;

---

## [5] Sean Christopherson — 2025-12-05
*Subject: [PATCH v2 4/7] x86/virt/tdx: Tag a pile of functions as __init, and
 globals as __ro_after_init*

Now that TDX-Module initialization is done during subsys init, tag all
related functions as __init, and relevant data as __ro_after_init.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c                 | 115 ++++++++++----------
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  10 +-
 2 files changed, 64 insertions(+), 61 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 8282c9b1b48b..d49645797fe4 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -55,8 +55,8 @@ static struct tdmr_info_list tdx_tdmr_list;
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
-static struct tdx_sys_info tdx_sysinfo;
-static bool tdx_module_initialized;
+static struct tdx_sys_info tdx_sysinfo __ro_after_init;
+static bool tdx_module_initialized __ro_after_init;
 
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
@@ -226,8 +226,9 @@ static struct syscore_ops tdx_syscore_ops = {
  * all memory regions are added in address ascending order and don't
  * overlap.
  */
-static int add_tdx_memblock(struct list_head *tmb_list, unsigned long start_pfn,
-			    unsigned long end_pfn, int nid)
+static __init int add_tdx_memblock(struct list_head *tmb_list,
+				   unsigned long start_pfn,
+				   unsigned long end_pfn, int nid)
 {
 	struct tdx_memblock *tmb;
 
@@ -245,7 +246,7 @@ static int add_tdx_memblock(struct list_head *tmb_list, unsigned long start_pfn,
 	return 0;
 }
 
-static void free_tdx_memlist(struct list_head *tmb_list)
+static __init void free_tdx_memlist(struct list_head *tmb_list)
 {
 	/* @tmb_list is protected by mem_hotplug_lock */
 	while (!list_empty(tmb_list)) {
@@ -263,7 +264,7 @@ static void free_tdx_memlist(struct list_head *tmb_list)
  * ranges off in a secondary structure because memblock is modified
  * in memory hotplug while TDX memory regions are fixed.
  */
-static int build_tdx_memlist(struct list_head *tmb_list)
+static __init int build_tdx_memlist(struct list_head *tmb_list)
 {
 	unsigned long start_pfn, end_pfn;
 	int i, nid, ret;
@@ -295,7 +296,7 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
-static int read_sys_metadata_field(u64 field_id, u64 *data)
+static __init int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
 	int ret;
@@ -317,7 +318,7 @@ static int read_sys_metadata_field(u64 field_id, u64 *data)
 
 #include "tdx_global_metadata.c"
 
-static int check_features(struct tdx_sys_info *sysinfo)
+static __init int check_features(struct tdx_sys_info *sysinfo)
 {
 	u64 tdx_features0 = sysinfo->features.tdx_features0;
 
@@ -330,7 +331,7 @@ static int check_features(struct tdx_sys_info *sysinfo)
 }
 
 /* Calculate the actual TDMR size */
-static int tdmr_size_single(u16 max_reserved_per_tdmr)
+static __init int tdmr_size_single(u16 max_reserved_per_tdmr)
 {
 	int tdmr_sz;
 
@@ -344,8 +345,8 @@ static int tdmr_size_single(u16 max_reserved_per_tdmr)
 	return ALIGN(tdmr_sz, TDMR_INFO_ALIGNMENT);
 }
 
-static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
-			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
+static __init int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
+				  struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	size_t tdmr_sz, tdmr_array_sz;
 	void *tdmr_array;
@@ -376,7 +377,7 @@ static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
 	return 0;
 }
 
-static void free_tdmr_list(struct tdmr_info_list *tdmr_list)
+static __init void free_tdmr_list(struct tdmr_info_list *tdmr_list)
 {
 	free_pages_exact(tdmr_list->tdmrs,
 			tdmr_list->max_tdmrs * tdmr_list->tdmr_sz);
@@ -405,8 +406,8 @@ static inline u64 tdmr_end(struct tdmr_info *tdmr)
  * preallocated @tdmr_list, following all the special alignment
  * and size rules for TDMR.
  */
-static int fill_out_tdmrs(struct list_head *tmb_list,
-			  struct tdmr_info_list *tdmr_list)
+static __init int fill_out_tdmrs(struct list_head *tmb_list,
+				 struct tdmr_info_list *tdmr_list)
 {
 	struct tdx_memblock *tmb;
 	int tdmr_idx = 0;
@@ -482,8 +483,8 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
  */
-static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-				      u16 pamt_entry_size)
+static __init unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
+					     u16 pamt_entry_size)
 {
 	unsigned long pamt_sz, nr_pamt_entries;
 
@@ -514,7 +515,7 @@ static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
  * PAMT.  This node will have some memory covered by the TDMR.  The
  * relative amount of memory covered is not considered.
  */
-static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
+static __init int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
 {
 	struct tdx_memblock *tmb;
 
@@ -543,9 +544,9 @@ static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
  * Allocate PAMTs from the local NUMA node of some memory in @tmb_list
  * within @tdmr, and set up PAMTs for @tdmr.
  */
-static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
-			    struct list_head *tmb_list,
-			    u16 pamt_entry_size[])
+static __init int tdmr_set_up_pamt(struct tdmr_info *tdmr,
+				   struct list_head *tmb_list,
+				   u16 pamt_entry_size[])
 {
 	unsigned long pamt_base[TDX_PS_NR];
 	unsigned long pamt_size[TDX_PS_NR];
@@ -615,7 +616,7 @@ static void tdmr_get_pamt(struct tdmr_info *tdmr, unsigned long *pamt_base,
 	*pamt_size = pamt_sz;
 }
 
-static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
+static __init void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 		void (*pamt_func)(unsigned long base, unsigned long size))
 {
 	unsigned long pamt_base, pamt_size;
@@ -632,17 +633,17 @@ static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 	pamt_func(pamt_base, pamt_size);
 }
 
-static void free_pamt(unsigned long pamt_base, unsigned long pamt_size)
+static __init  void free_pamt(unsigned long pamt_base, unsigned long pamt_size)
 {
 	free_contig_range(pamt_base >> PAGE_SHIFT, pamt_size >> PAGE_SHIFT);
 }
 
-static void tdmr_free_pamt(struct tdmr_info *tdmr)
+static __init void tdmr_free_pamt(struct tdmr_info *tdmr)
 {
 	tdmr_do_pamt_func(tdmr, free_pamt);
 }
 
-static void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
+static __init void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
 {
 	int i;
 
@@ -651,9 +652,9 @@ static void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
 }
 
 /* Allocate and set up PAMTs for all TDMRs */
-static int tdmrs_set_up_pamt_all(struct tdmr_info_list *tdmr_list,
-				 struct list_head *tmb_list,
-				 u16 pamt_entry_size[])
+static __init int tdmrs_set_up_pamt_all(struct tdmr_info_list *tdmr_list,
+					struct list_head *tmb_list,
+					u16 pamt_entry_size[])
 {
 	int i, ret = 0;
 
@@ -702,12 +703,13 @@ void tdx_quirk_reset_page(struct page *page)
 }
 EXPORT_SYMBOL_GPL(tdx_quirk_reset_page);
 
-static void tdmr_quirk_reset_pamt(struct tdmr_info *tdmr)
+static __init void tdmr_quirk_reset_pamt(struct tdmr_info *tdmr)
+
 {
 	tdmr_do_pamt_func(tdmr, tdx_quirk_reset_paddr);
 }
 
-static void tdmrs_quirk_reset_pamt_all(struct tdmr_info_list *tdmr_list)
+static __init void tdmrs_quirk_reset_pamt_all(struct tdmr_info_list *tdmr_list)
 {
 	int i;
 
@@ -715,7 +717,7 @@ static void tdmrs_quirk_reset_pamt_all(struct tdmr_info_list *tdmr_list)
 		tdmr_quirk_reset_pamt(tdmr_entry(tdmr_list, i));
 }
 
-static unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
+static __init unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
 {
 	unsigned long pamt_size = 0;
 	int i;
@@ -730,8 +732,8 @@ static unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
 	return pamt_size / 1024;
 }
 
-static int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx, u64 addr,
-			      u64 size, u16 max_reserved_per_tdmr)
+static __init int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx,
+				     u64 addr, u64 size, u16 max_reserved_per_tdmr)
 {
 	struct tdmr_reserved_area *rsvd_areas = tdmr->reserved_areas;
 	int idx = *p_idx;
@@ -764,10 +766,10 @@ static int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx, u64 addr,
  * those holes fall within @tdmr, set up a TDMR reserved area to cover
  * the hole.
  */
-static int tdmr_populate_rsvd_holes(struct list_head *tmb_list,
-				    struct tdmr_info *tdmr,
-				    int *rsvd_idx,
-				    u16 max_reserved_per_tdmr)
+static __init int tdmr_populate_rsvd_holes(struct list_head *tmb_list,
+					   struct tdmr_info *tdmr,
+					   int *rsvd_idx,
+					   u16 max_reserved_per_tdmr)
 {
 	struct tdx_memblock *tmb;
 	u64 prev_end;
@@ -828,10 +830,10 @@ static int tdmr_populate_rsvd_holes(struct list_head *tmb_list,
  * overlaps with @tdmr, set up a TDMR reserved area to cover the
  * overlapping part.
  */
-static int tdmr_populate_rsvd_pamts(struct tdmr_info_list *tdmr_list,
-				    struct tdmr_info *tdmr,
-				    int *rsvd_idx,
-				    u16 max_reserved_per_tdmr)
+static __init int tdmr_populate_rsvd_pamts(struct tdmr_info_list *tdmr_list,
+					   struct tdmr_info *tdmr,
+					   int *rsvd_idx,
+					   u16 max_reserved_per_tdmr)
 {
 	int i, ret;
 
@@ -866,7 +868,7 @@ static int tdmr_populate_rsvd_pamts(struct tdmr_info_list *tdmr_list,
 }
 
 /* Compare function called by sort() for TDMR reserved areas */
-static int rsvd_area_cmp_func(const void *a, const void *b)
+static __init int rsvd_area_cmp_func(const void *a, const void *b)
 {
 	struct tdmr_reserved_area *r1 = (struct tdmr_reserved_area *)a;
 	struct tdmr_reserved_area *r2 = (struct tdmr_reserved_area *)b;
@@ -885,10 +887,10 @@ static int rsvd_area_cmp_func(const void *a, const void *b)
  * Populate reserved areas for the given @tdmr, including memory holes
  * (via @tmb_list) and PAMTs (via @tdmr_list).
  */
-static int tdmr_populate_rsvd_areas(struct tdmr_info *tdmr,
-				    struct list_head *tmb_list,
-				    struct tdmr_info_list *tdmr_list,
-				    u16 max_reserved_per_tdmr)
+static __init int tdmr_populate_rsvd_areas(struct tdmr_info *tdmr,
+					   struct list_head *tmb_list,
+					   struct tdmr_info_list *tdmr_list,
+					   u16 max_reserved_per_tdmr)
 {
 	int ret, rsvd_idx = 0;
 
@@ -913,9 +915,9 @@ static int tdmr_populate_rsvd_areas(struct tdmr_info *tdmr,
  * Populate reserved areas for all TDMRs in @tdmr_list, including memory
  * holes (via @tmb_list) and PAMTs.
  */
-static int tdmrs_populate_rsvd_areas_all(struct tdmr_info_list *tdmr_list,
-					 struct list_head *tmb_list,
-					 u16 max_reserved_per_tdmr)
+static __init int tdmrs_populate_rsvd_areas_all(struct tdmr_info_list *tdmr_list,
+						struct list_head *tmb_list,
+						u16 max_reserved_per_tdmr)
 {
 	int i;
 
@@ -936,9 +938,9 @@ static int tdmrs_populate_rsvd_areas_all(struct tdmr_info_list *tdmr_list,
  * to cover all TDX memory regions in @tmb_list based on the TDX module
  * TDMR global information in @sysinfo_tdmr.
  */
-static int construct_tdmrs(struct list_head *tmb_list,
-			   struct tdmr_info_list *tdmr_list,
-			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
+static __init int construct_tdmrs(struct list_head *tmb_list,
+				  struct tdmr_info_list *tdmr_list,
+				  struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	u16 pamt_entry_size[TDX_PS_NR] = {
 		sysinfo_tdmr->pamt_4k_entry_size,
@@ -970,7 +972,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
-static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
+static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
+				    u64 global_keyid)
 {
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
@@ -1063,7 +1066,7 @@ static int config_global_keyid(void)
 	return ret;
 }
 
-static int init_tdmr(struct tdmr_info *tdmr)
+static __init int init_tdmr(struct tdmr_info *tdmr)
 {
 	u64 next;
 
@@ -1094,7 +1097,7 @@ static int init_tdmr(struct tdmr_info *tdmr)
 	return 0;
 }
 
-static int init_tdmrs(struct tdmr_info_list *tdmr_list)
+static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 {
 	int i;
 
@@ -1113,7 +1116,7 @@ static int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
-static int init_tdx_module(void)
+static __init int init_tdx_module(void)
 {
 	int ret;
 
@@ -1194,7 +1197,7 @@ static int init_tdx_module(void)
 	goto out_put_tdxmem;
 }
 
-static int tdx_enable(void)
+static __init int tdx_enable(void)
 {
 	enum cpuhp_state state;
 	int ret;
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..360963bc9328 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -7,7 +7,7 @@
  * Include this file to other C file instead.
  */
 
-static int get_tdx_sys_info_features(struct tdx_sys_info_features *sysinfo_features)
+static __init int get_tdx_sys_info_features(struct tdx_sys_info_features *sysinfo_features)
 {
 	int ret = 0;
 	u64 val;
@@ -18,7 +18,7 @@ static int get_tdx_sys_info_features(struct tdx_sys_info_features *sysinfo_featu
 	return ret;
 }
 
-static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
+static __init int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	int ret = 0;
 	u64 val;
@@ -37,7 +37,7 @@ static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 	return ret;
 }
 
-static int get_tdx_sys_info_td_ctrl(struct tdx_sys_info_td_ctrl *sysinfo_td_ctrl)
+static __init int get_tdx_sys_info_td_ctrl(struct tdx_sys_info_td_ctrl *sysinfo_td_ctrl)
 {
 	int ret = 0;
 	u64 val;
@@ -52,7 +52,7 @@ static int get_tdx_sys_info_td_ctrl(struct tdx_sys_info_td_ctrl *sysinfo_td_ctrl
 	return ret;
 }
 
-static int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf)
+static __init int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf)
 {
 	int ret = 0;
 	u64 val;
@@ -85,7 +85,7 @@ static int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf
 	return ret;
 }
 
-static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
+static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;

---

## [6] Sean Christopherson — 2025-12-05
*Subject: [PATCH v2 5/7] x86/virt/tdx: KVM: Consolidate TDX CPU hotplug handling*

From: Chao Gao <chao.gao@intel.com>

The core kernel registers a CPU hotplug callback to do VMX and TDX init
and deinit while KVM registers a separate CPU offline callback to block
offlining the last online CPU in a socket.

Splitting TDX-related CPU hotplug handling across two components is odd
and adds unnecessary complexity.

Consolidate TDX-related CPU hotplug handling by integrating KVM's
tdx_offline_cpu() to the one in the core kernel.

Also move nr_configured_hkid to the core kernel because tdx_offline_cpu()
references it. Since HKID allocation and free are handled in the core
kernel, it's more natural to track used HKIDs there.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c      | 67 +------------------------------------
 arch/x86/virt/vmx/tdx/tdx.c | 49 +++++++++++++++++++++++++--
 2 files changed, 47 insertions(+), 69 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d0161dc3d184..d9dd6070baa0 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -59,8 +59,6 @@ module_param_named(tdx, enable_tdx, bool, 0444);
 #define TDX_SHARED_BIT_PWL_5 gpa_to_gfn(BIT_ULL(51))
 #define TDX_SHARED_BIT_PWL_4 gpa_to_gfn(BIT_ULL(47))
 
-static enum cpuhp_state tdx_cpuhp_state __ro_after_init;
-
 static const struct tdx_sys_info *tdx_sysinfo;
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err)
@@ -219,8 +217,6 @@ static int init_kvm_tdx_caps(const struct tdx_sys_info_td_conf *td_conf,
  */
 static DEFINE_MUTEX(tdx_lock);
 
-static atomic_t nr_configured_hkid;
-
 static bool tdx_operand_busy(u64 err)
 {
 	return (err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_BUSY;
@@ -268,7 +264,6 @@ static inline void tdx_hkid_free(struct kvm_tdx *kvm_tdx)
 {
 	tdx_guest_keyid_free(kvm_tdx->hkid);
 	kvm_tdx->hkid = -1;
-	atomic_dec(&nr_configured_hkid);
 	misc_cg_uncharge(MISC_CG_RES_TDX, kvm_tdx->misc_cg, 1);
 	put_misc_cg(kvm_tdx->misc_cg);
 	kvm_tdx->misc_cg = NULL;
@@ -2399,8 +2394,6 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	ret = -ENOMEM;
 
-	atomic_inc(&nr_configured_hkid);
-
 	tdr_page = alloc_page(GFP_KERNEL);
 	if (!tdr_page)
 		goto free_hkid;
@@ -3302,51 +3295,10 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 	return PG_LEVEL_4K;
 }
 
-static int tdx_online_cpu(unsigned int cpu)
-{
-	return 0;
-}
-
-static int tdx_offline_cpu(unsigned int cpu)
-{
-	int i;
-
-	/* No TD is running.  Allow any cpu to be offline. */
-	if (!atomic_read(&nr_configured_hkid))
-		return 0;
-
-	/*
-	 * In order to reclaim TDX HKID, (i.e. when deleting guest TD), need to
-	 * call TDH.PHYMEM.PAGE.WBINVD on all packages to program all memory
-	 * controller with pconfig.  If we have active TDX HKID, refuse to
-	 * offline the last online cpu.
-	 */
-	for_each_online_cpu(i) {
-		/*
-		 * Found another online cpu on the same package.
-		 * Allow to offline.
-		 */
-		if (i != cpu && topology_physical_package_id(i) ==
-				topology_physical_package_id(cpu))
-			return 0;
-	}
-
-	/*
-	 * This is the last cpu of this package.  Don't offline it.
-	 *
-	 * Because it's hard for human operator to understand the
-	 * reason, warn it.
-	 */
-#define MSG_ALLPKG_ONLINE \
-	"TDX requires all packages to have an online CPU. Delete all TDs in order to offline all CPUs of a package.\n"
-	pr_warn_ratelimited(MSG_ALLPKG_ONLINE);
-	return -EBUSY;
-}
-
 static int __init __tdx_bringup(void)
 {
 	const struct tdx_sys_info_td_conf *td_conf;
-	int r, i;
+	int i;
 
 	for (i = 0; i < ARRAY_SIZE(tdx_uret_msrs); i++) {
 		/*
@@ -3414,23 +3366,7 @@ static int __init __tdx_bringup(void)
 	if (misc_cg_set_capacity(MISC_CG_RES_TDX, tdx_get_nr_guest_keyids()))
 		return -EINVAL;
 
-	/*
-	 * TDX-specific cpuhp callback to disallow offlining the last CPU in a
-	 * packing while KVM is running one or more TDs.  Reclaiming HKIDs
-	 * requires doing PAGE.WBINVD on every package, i.e. offlining all CPUs
-	 * of a package would prevent reclaiming the HKID.
-	 */
-	r = cpuhp_setup_state(CPUHP_AP_ONLINE_DYN, "kvm/cpu/tdx:online",
-			      tdx_online_cpu, tdx_offline_cpu);
-	if (r < 0)
-		goto err_cpuhup;
-
-	tdx_cpuhp_state = r;
 	return 0;
-
-err_cpuhup:
-	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
-	return r;
 }
 
 int __init tdx_bringup(void)
@@ -3486,7 +3422,6 @@ void tdx_cleanup(void)
 		return;
 
 	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
-	cpuhp_remove_state(tdx_cpuhp_state);
 }
 
 void __init tdx_hardware_setup(void)
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index d49645797fe4..5cf008bffa94 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -58,6 +58,8 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
+static atomic_t nr_configured_hkid;
+
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
@@ -190,6 +192,40 @@ static int tdx_online_cpu(unsigned int cpu)
 
 static int tdx_offline_cpu(unsigned int cpu)
 {
+	int i;
+
+	/* No TD is running.  Allow any cpu to be offline. */
+	if (!atomic_read(&nr_configured_hkid))
+		goto done;
+
+	/*
+	 * In order to reclaim TDX HKID, (i.e. when deleting guest TD), need to
+	 * call TDH.PHYMEM.PAGE.WBINVD on all packages to program all memory
+	 * controller with pconfig.  If we have active TDX HKID, refuse to
+	 * offline the last online cpu.
+	 */
+	for_each_online_cpu(i) {
+		/*
+		 * Found another online cpu on the same package.
+		 * Allow to offline.
+		 */
+		if (i != cpu && topology_physical_package_id(i) ==
+				topology_physical_package_id(cpu))
+			goto done;
+	}
+
+	/*
+	 * This is the last cpu of this package.  Don't offline it.
+	 *
+	 * Because it's hard for human operator to understand the
+	 * reason, warn it.
+	 */
+#define MSG_ALLPKG_ONLINE \
+	"TDX requires all packages to have an online CPU. Delete all TDs in order to offline all CPUs of a package.\n"
+	pr_warn_ratelimited(MSG_ALLPKG_ONLINE);
+	return -EBUSY;
+
+done:
 	x86_virt_put_cpu(X86_FEATURE_VMX);
 	return 0;
 }
@@ -1506,15 +1542,22 @@ EXPORT_SYMBOL_GPL(tdx_get_nr_guest_keyids);
 
 int tdx_guest_keyid_alloc(void)
 {
-	return ida_alloc_range(&tdx_guest_keyid_pool, tdx_guest_keyid_start,
-			       tdx_guest_keyid_start + tdx_nr_guest_keyids - 1,
-			       GFP_KERNEL);
+	int ret;
+
+	ret = ida_alloc_range(&tdx_guest_keyid_pool, tdx_guest_keyid_start,
+			      tdx_guest_keyid_start + tdx_nr_guest_keyids - 1,
+			      GFP_KERNEL);
+	if (ret >= 0)
+		atomic_inc(&nr_configured_hkid);
+
+	return ret;
 }
 EXPORT_SYMBOL_GPL(tdx_guest_keyid_alloc);
 
 void tdx_guest_keyid_free(unsigned int keyid)
 {
 	ida_free(&tdx_guest_keyid_pool, keyid);
+	atomic_dec(&nr_configured_hkid);
 }
 EXPORT_SYMBOL_GPL(tdx_guest_keyid_free);

---

## [7] Sean Christopherson — 2025-12-05
*Subject: [PATCH v2 6/7] x86/virt/tdx: Use ida_is_empty() to detect if any TDs
 may be running*

Drop nr_configured_hkid and instead use ida_is_empty() to detect if any
HKIDs have been allocated/configured.

Suggested-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 17 ++++-------------
 1 file changed, 4 insertions(+), 13 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5cf008bffa94..ef77135ec373 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -58,8 +58,6 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
-static atomic_t nr_configured_hkid;
-
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
@@ -195,7 +193,7 @@ static int tdx_offline_cpu(unsigned int cpu)
 	int i;
 
 	/* No TD is running.  Allow any cpu to be offline. */
-	if (!atomic_read(&nr_configured_hkid))
+	if (ida_is_empty(&tdx_guest_keyid_pool))
 		goto done;
 
 	/*
@@ -1542,22 +1540,15 @@ EXPORT_SYMBOL_GPL(tdx_get_nr_guest_keyids);
 
 int tdx_guest_keyid_alloc(void)
 {
-	int ret;
-
-	ret = ida_alloc_range(&tdx_guest_keyid_pool, tdx_guest_keyid_start,
-			      tdx_guest_keyid_start + tdx_nr_guest_keyids - 1,
-			      GFP_KERNEL);
-	if (ret >= 0)
-		atomic_inc(&nr_configured_hkid);
-
-	return ret;
+	return ida_alloc_range(&tdx_guest_keyid_pool, tdx_guest_keyid_start,
+			       tdx_guest_keyid_start + tdx_nr_guest_keyids - 1,
+			       GFP_KERNEL);
 }
 EXPORT_SYMBOL_GPL(tdx_guest_keyid_alloc);
 
 void tdx_guest_keyid_free(unsigned int keyid)
 {
 	ida_free(&tdx_guest_keyid_pool, keyid);
-	atomic_dec(&nr_configured_hkid);
 }
 EXPORT_SYMBOL_GPL(tdx_guest_keyid_free);

---

## [8] Sean Christopherson — 2025-12-05
*Subject: [PATCH v2 7/7] KVM: Bury kvm_{en,dis}able_virtualization() in
 kvm_main.c once more*

Now that TDX handles doing VMXON without KVM's involvement, bury the
top-level APIs to enable and disable virtualization back in kvm_main.c.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 include/linux/kvm_host.h |  8 --------
 virt/kvm/kvm_main.c      | 17 +++++++++++++----
 2 files changed, 13 insertions(+), 12 deletions(-)

diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index a453fe6ce05a..ac9332104793 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2596,12 +2596,4 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 				    struct kvm_pre_fault_memory *range);
 #endif
 
-#ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
-int kvm_enable_virtualization(void);
-void kvm_disable_virtualization(void);
-#else
-static inline int kvm_enable_virtualization(void) { return 0; }
-static inline void kvm_disable_virtualization(void) { }
-#endif
-
 #endif
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 3278ee9381bd..ac2633e9cd80 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -1111,6 +1111,9 @@ static inline struct kvm_io_bus *kvm_get_bus_for_destruction(struct kvm *kvm,
 					 !refcount_read(&kvm->users_count));
 }
 
+static int kvm_enable_virtualization(void);
+static void kvm_disable_virtualization(void);
+
 static struct kvm *kvm_create_vm(unsigned long type, const char *fdname)
 {
 	struct kvm *kvm = kvm_arch_alloc_vm();
@@ -5693,7 +5696,7 @@ static struct syscore_ops kvm_syscore_ops = {
 	.shutdown = kvm_shutdown,
 };
 
-int kvm_enable_virtualization(void)
+static int kvm_enable_virtualization(void)
 {
 	int r;
 
@@ -5738,9 +5741,8 @@ int kvm_enable_virtualization(void)
 	--kvm_usage_count;
 	return r;
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_enable_virtualization);
 
-void kvm_disable_virtualization(void)
+static void kvm_disable_virtualization(void)
 {
 	guard(mutex)(&kvm_usage_lock);
 
@@ -5751,7 +5753,6 @@ void kvm_disable_virtualization(void)
 	cpuhp_remove_state(CPUHP_AP_KVM_ONLINE);
 	kvm_arch_disable_virtualization();
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_disable_virtualization);
 
 static int kvm_init_virtualization(void)
 {
@@ -5767,6 +5768,14 @@ static void kvm_uninit_virtualization(void)
 		kvm_disable_virtualization();
 }
 #else /* CONFIG_KVM_GENERIC_HARDWARE_ENABLING */
+static int kvm_enable_virtualization(void)
+{
+	return 0;
+}
+static void kvm_disable_virtualization(void)
+{
+
+}
 static int kvm_init_virtualization(void)
 {
 	return 0;

---

## [9] dan.j.williams@intel.com — 2025-12-06
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

Sean Christopherson wrote:
> Move the innermost VMXON and EFER.SVME management logic out of KVM and
> into to core x86 so that TDX can force VMXON without having to rely on
[..]

Only patch organization and naming choice questions from me. I only
looked at the VMX side of things since I previously made an attempt at
moving that. I gave a cursory look at the SVM details.

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

> diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
> index 80cb882f19e2..f650f79d3d5a 100644

...a short stay for this symbol in kvm/x86.c? It raises my curiosity why
patch1 is separate. Patch1 looked like the start of a series of
incremental conversions, patch2 is a combo move. I am ok either way,
just questioning consistency. I.e. if combo move then patch1 folds in
here, if incremental, perhaps split out other combo conversions like
emergency_disable_virtualization_cpu()? The aspect of "this got moved
twice in the same patchset" is what poked me.

[..]
> diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
> new file mode 100644

Hmm, why kvm_ and not virt_?

[..]
> +#if IS_ENABLED(CONFIG_KVM_INTEL)
> +static DEFINE_PER_CPU(struct vmcs *, root_vmcs);

Perhaps introduce a CONFIG_INTEL_VMX for this? For example, KVM need not
be enabled if all one wants to do is use TDX to setup PCIe Link
Encryption. ...or were you expecting?

#if IS_ENABLED(CONFIG_KVM_INTEL) || IS_ENABLED(...<other VMX users>...)

---

## [10] dan.j.williams@intel.com — 2025-12-06
*Subject: Re: [PATCH v2 3/7] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during subsys init*

Sean Christopherson wrote:
> Now that VMXON can be done without bouncing through KVM, do TDX-Module
> initialization during subsys init (specifically before module_init() so

yes!

> 
> @@ -3304,17 +3304,7 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)

Given this routine now has nothing to do...

> +	 * TDX-specific cpuhp callback to disallow offlining the last CPU in a
> +	 * packing while KVM is running one or more TDs.  Reclaiming HKIDs

...the @startup param can be NULL. That also saves some grep pain no
more multiple implementations of a "tdx_online_cpu".

Along those lines, should tdx_offline_cpu() become
kvm_tdx_offline_cpu()?

[..]
>  /*
>   * Add a memory region as a TDX memory block.  The caller must make sure

Almost commented about this being able to be __init now, but then I see
you have a combo patch for that later.

With or without the additional tdx_{on,off}line_cpu fixups:

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [11] Chao Gao — 2025-12-08
*Subject: Re: [PATCH v2 0/7] KVM: x86/tdx: Have TDX handle VMXON during bringup*

On Fri, Dec 05, 2025 at 05:10:47PM -0800, Sean Christopherson wrote:
>The idea here is to extract _only_ VMXON+VMXOFF and EFER.SVME toggling.  AFAIK
>there's no second user of SVM, i.e. no equivalent to TDX, but I wanted to keep

I ran tests on an EMR system, including performing CPU hot-{un}plug,
unloading/reloading kvm-intel.ko and launching TDs. No issue found.
So,

Tested-by: Chao Gao <chao.gao@intel.com>

---

## [12] Sean Christopherson — 2025-12-08
*Subject: Re: [PATCH v2 3/7] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during subsys init*

On Sat, Dec 06, 2025, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> Given this routine now has nothing to do...

I think the fixups you're looking for are in patch 5, "/virt/tdx: KVM: Consolidate
TDX CPU hotplug handling", or did I misunderstand?

---

## [13] dan.j.williams@intel.com — 2025-12-09
*Subject: Re: [PATCH v2 3/7] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during subsys init*

Sean Christopherson wrote:
[..]
> > With or without the additional tdx_{on,off}line_cpu fixups:
> 

Oh, yes, all addressed there. Should have finished going through it
before replying.

---

## [14] dan.j.williams@intel.com — 2025-12-09
*Subject: Re: [PATCH v2 4/7] x86/virt/tdx: Tag a pile of functions as __init,
 and globals as __ro_after_init*

Sean Christopherson wrote:
> Now that TDX-Module initialization is done during subsys init, tag all
> related functions as __init, and relevant data as __ro_after_init.

Looks good,

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [15] dan.j.williams@intel.com — 2025-12-09
*Subject: Re: [PATCH v2 5/7] x86/virt/tdx: KVM: Consolidate TDX CPU hotplug
 handling*

Sean Christopherson wrote:
> From: Chao Gao <chao.gao@intel.com>
> 

Looks good,

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [16] dan.j.williams@intel.com — 2025-12-09
*Subject: Re: [PATCH v2 6/7] x86/virt/tdx: Use ida_is_empty() to detect if any
 TDs may be running*

Sean Christopherson wrote:
> Drop nr_configured_hkid and instead use ida_is_empty() to detect if any
> HKIDs have been allocated/configured.

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [17] dan.j.williams@intel.com — 2025-12-09
*Subject: Re: [PATCH v2 7/7] KVM: Bury kvm_{en,dis}able_virtualization() in
 kvm_main.c once more*

Sean Christopherson wrote:
> Now that TDX handles doing VMXON without KVM's involvement, bury the
> top-level APIs to enable and disable virtualization back in kvm_main.c.

Looks good,

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [18] Chao Gao — 2025-12-09
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

>--- /dev/null
>+++ b/arch/x86/include/asm/virt.h

asm/reboot.h isn't used.

>+
>+typedef void (cpu_emergency_virt_cb)(void);

Why does this need to be "__always_inline" rather than just "inline"?

> static void emergency_reboot_disable_virtualization(void)
> {

								 ^ stray "k".

I don't understand the "if necessary" part. My understanding is this code
issues NMIs if CPUs support VMX or SVM. If so, I think the code snippet below
would be more readable:

	if (cpu_feature_enabled(X86_FEATURE_VMX) ||
	    cpu_feature_enabled(X86_FEATURE_SVM)) {
		x86_virt_emergency_disable_virtualization_cpu();
		nmi_shootdown_cpus_on_restart();
	}

Then x86_virt_emergency_disable_virtualization_cpu() wouldn't need to return
anything. And readers wouldn't need to trace down the function to understand
when NMIs are "necessary" and when they are not.

> 	 */
>-	if (rcu_access_pointer(cpu_emergency_virt_callback)) {

<snip>

>+#define x86_virt_call(fn)				\
>+({							\

Should we assert that preemption is disabled? Calling this API when preemption
is enabled is wrong.

Maybe use __this_cpu_inc_return(), which already verifies preemption status.

<snip>

>+int x86_virt_emergency_disable_virtualization_cpu(void)
>+{

This comment is misplaced. NMIs are issued by the caller.

>+	(void)x86_virt_call(emergency_disable_virtualization_cpu);
>+	return 0;

---

## [19] Chao Gao — 2025-12-09
*Subject: Re: [PATCH v2 3/7] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during subsys init*

On Fri, Dec 05, 2025 at 05:10:50PM -0800, Sean Christopherson wrote:
>Now that VMXON can be done without bouncing through KVM, do TDX-Module
>initialization during subsys init (specifically before module_init() so

With this patch applied, other parts of the document will be stale and need
updates, i.e.,:

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 2e0a15d6f7d1..3d5bc68e3bcb 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -66,12 +66,12 @@ If the TDX module is initialized successfully, dmesg shows something
 like below::
 
   [..] virt/tdx: 262668 KBs allocated for PAMT
-  [..] virt/tdx: module initialized
+  [..] virt/tdx: TDX-Module initialized
 
 If the TDX module failed to initialize, dmesg also shows it failed to
 initialize::
 
-  [..] virt/tdx: module initialization failed ...
+  [..] virt/tdx: TDX-Module initialization failed ...
 
 TDX Interaction to Other Kernel Components
 ------------------------------------------
@@ -102,11 +102,6 @@ removal but depends on the BIOS to behave correctly.
 CPU Hotplug
 ~~~~~~~~~~~
 
-TDX module requires the per-cpu initialization SEAMCALL must be done on
-one cpu before any other SEAMCALLs can be made on that cpu.  The kernel
-provides tdx_cpu_enable() to let the user of TDX to do it when the user
-wants to use a new cpu for TDX task.
-
 TDX doesn't support physical (ACPI) CPU hotplug.  During machine boot,
 TDX verifies all boot-time present logical CPUs are TDX compatible before
 enabling TDX.  A non-buggy BIOS should never support hot-add/removal of

> static int __init __tdx_bringup(void)
> {

...

>-	/*
>-	 * Ideally KVM should probe whether TDX module has been loaded

Previously, loading kvm-intel.ko (with tdx=1) would succeed even if there was
no TDX module loaded by BIOS. IIUC, the behavior changes here; the lack of TDX
module becomes fatal and kvm-intel.ko loading would fail.

Is this intentional?

>-
>+	if (r)

---

## [20] Chao Gao — 2025-12-09
*Subject: Re: [PATCH v2 4/7] x86/virt/tdx: Tag a pile of functions as __init,
 and globals as __ro_after_init*

On Fri, Dec 05, 2025 at 05:10:51PM -0800, Sean Christopherson wrote:
>Now that TDX-Module initialization is done during subsys init, tag all
>related functions as __init, and relevant data as __ro_after_init.

Reviewed-by: Chao Gao <chao.gao@intel.com>

Two nits:

1. do_global_key_config() and config_global_keyid() can be tagged as __init.
2. Double space after the __init tag of free_pamt()

>-static void free_pamt(unsigned long pamt_base, unsigned long pamt_size)
>+static __init  void free_pamt(unsigned long pamt_base, unsigned long pamt_size)

	       ^^

> {
> 	free_contig_range(pamt_base >> PAGE_SHIFT, pamt_size >> PAGE_SHIFT);

---

## [21] Chao Gao — 2025-12-09
*Subject: Re: [PATCH v2 6/7] x86/virt/tdx: Use ida_is_empty() to detect if any
 TDs may be running*

On Fri, Dec 05, 2025 at 05:10:53PM -0800, Sean Christopherson wrote:
>Drop nr_configured_hkid and instead use ida_is_empty() to detect if any
>HKIDs have been allocated/configured.

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [22] Chao Gao — 2025-12-09
*Subject: Re: [PATCH v2 7/7] KVM: Bury kvm_{en,dis}able_virtualization() in
 kvm_main.c once more*

On Fri, Dec 05, 2025 at 05:10:54PM -0800, Sean Christopherson wrote:
>Now that TDX handles doing VMXON without KVM's involvement, bury the
>top-level APIs to enable and disable virtualization back in kvm_main.c.

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [23] Chao Gao — 2025-12-09
*Subject: Re: [PATCH v2 1/7] KVM: x86: Move kvm_rebooting to x86*

On Fri, Dec 05, 2025 at 05:10:48PM -0800, Sean Christopherson wrote:
>Move kvm_rebooting, which is only read by x86, to KVM x86 so that it can
>be moved again to core x86 code.  Add a "shutdown" arch hook to facilate

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [24] Sean Christopherson — 2025-12-09
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Sat, Dec 06, 2025, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> > @@ -694,9 +696,6 @@ static void drop_user_return_notifiers(void)

Because it affects non-x86 architectures.  It should be a complete nop, but I
wanted to isolate what I could.

> Patch1 looked like the start of a series of incremental conversions, patch2
> is a combo move. I am ok either way, just questioning consistency. I.e. if

Yeah, I got lazy to a large extent.  I'm not super optimistic that we won't end
up with one big "move all this stuff" patch, but I agree it doesn't need to be
_this_ big.

> [..]
> > diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c

I was trying to capture that this callback can _only_ be used by KVM, because
KVM is the only in-tree hypervisor.  That's also why the exports are only for
KVM (and will use EXPORT_SYMBOL_FOR_KVM() when I post the next version).

> [..]
> > +#if IS_ENABLED(CONFIG_KVM_INTEL)

I don't think we need anything at this time.  INTEL_TDX_HOST depends on KVM_INTEL,
and so without a user that needs VMXON without KVM_INTEL, I think we're good as-is.

 config INTEL_TDX_HOST
	bool "Intel Trust Domain Extensions (TDX) host support"
	depends on CPU_SUP_INTEL
	depends on X86_64
	depends on KVM_INTEL

---

## [25] dan.j.williams@intel.com — 2025-12-10
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

Sean Christopherson wrote:
> On Sat, Dec 06, 2025, dan.j.williams@intel.com wrote:
> > Sean Christopherson wrote:

Ok.

[..]
> > > +static cpu_emergency_virt_cb __rcu *kvm_emergency_callback;
> > 

Oh, true, that makes sense.

> > [..]
> > > +#if IS_ENABLED(CONFIG_KVM_INTEL)

...but INTEL_TDX_HOST, it turns out, does not have any functional
dependencies on KVM_INTEL. At least, not since I last checked. Yes, it
would be silly and result in dead code today to do a build with:

CONFIG_INTEL_TDX_HOST=y
CONFIG_KVM_INTEL=n

However, when the TDX Connect support arrives you could have:

CONFIG_INTEL_TDX_HOST=y
CONFIG_KVM_INTEL=n
CONFIG_TDX_HOST_SERVICES=y

Where "TDX Host Services" is a driver for PCIe Link Encryption and TDX
Module update. Whether such configuration freedom has any practical
value is a separate question.

I am ok if the answer is, "wait until someone shows up who really wants
PCIe Link Encryption without KVM".

---

## [26] Sean Christopherson — 2025-12-10
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Wed, Dec 10, 2025, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> > On Sat, Dec 06, 2025, dan.j.williams@intel.com wrote:

Ya, that's my answer.  At the very least, wait until TDX_HOST_SERVICES comes
along.

---

## [27] Sean Christopherson — 2025-12-12
*Subject: Re: [PATCH v2 3/7] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during subsys init*

On Tue, Dec 09, 2025, Chao Gao wrote:
> On Fri, Dec 05, 2025 at 05:10:50PM -0800, Sean Christopherson wrote:
> > static int __init __tdx_bringup(void)

Nope, definitely not intentional.  I think this as fixup?

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d0161dc3d184..4e0372f12e6d 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3365,7 +3365,7 @@ static int __init __tdx_bringup(void)
        /* Get TDX global information for later use */
        tdx_sysinfo = tdx_get_sysinfo();
        if (!tdx_sysinfo)
-               return -EINVAL;
+               return -ENODEV;
 
        /* Check TDX module and KVM capabilities */
        if (!tdx_get_supported_attrs(&tdx_sysinfo->td_conf) ||
@@ -3470,8 +3470,20 @@ int __init tdx_bringup(void)
        }
 
        r = __tdx_bringup();
-       if (r)
-               enable_tdx = 0;
+       if (r) {
+               /*
+                * Disable TDX only but don't fail to load module if the TDX
+                * module could not be loaded.  No need to print message saying
+                * "module is not loaded" because it was printed when the first
+                * SEAMCALL failed.  Don't bother unwinding the S-EPT hooks or
+                * vm_size, as kvm_x86_ops have already been finalized (and are
+                * intentionally not exported).  The S-EPT code is unreachable,
+                * and allocating a few more bytes per VM in a should-be-rare
+                * failure scenario is a non-issue.
+                */
+               if (r == -ENODEV)
+                       goto success_disable_tdx;
+       }
 
        return r;

---

## [28] Xu Yilun — 2025-12-17
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

> >+#define x86_virt_call(fn)				\
> >+({							\

Is it better we explicitly assert the preemption for x86_virt_get_cpu()
rather than embed the check in __this_cpu_inc_return()? We are not just
protecting the racing for the reference counter. We should ensure the
"counter increase + x86_virt_call(get_cpu)" can't be preempted.

Thanks,
Yilun

---

## [29] Sean Christopherson — 2025-12-17
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Wed, Dec 17, 2025, Xu Yilun wrote:
> > >+#define x86_virt_call(fn)				\
> > >+({							\

I always forget that the double-underscores have the checks.  

> Is it better we explicitly assert the preemption for x86_virt_get_cpu()
> rather than embed the check in __this_cpu_inc_return()? We are not just

I don't have a strong preference.  Using __this_cpu_inc_return() without any
nearby preemption_{enable,disable}() calls makes it quite clears that preemption
is expected to be disabled by the caller.  But I'm also ok being explicit.

---

## [30] Xu Yilun — 2025-12-19
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Wed, Dec 17, 2025 at 11:01:59AM -0800, Sean Christopherson wrote:
> On Wed, Dec 17, 2025, Xu Yilun wrote:
> > > >+#define x86_virt_call(fn)				\

Looking into __this_cpu_inc_return(), it finally calls
check_preemption_disabled() which doesn't strictly requires preemption.
It only ensures the context doesn't switch to another CPU. If the caller
is in cpuhp context, preemption is possible.

But in this x86_virt_get_cpu(), we need to ensure preemption disabled,
otherwise caller A increases counter but hasn't do actual VMXON yet and
get preempted. Caller B opts in and get the wrong info that VMX is
already on, and fails on following vmx operations.

On a second thought, maybe we disable preemption inside
x86_virt_get_cpu() to protect the counter-vmxon racing, this is pure
internal thing for this kAPI.

Thanks,
Yilun

---

## [31] Sean Christopherson — 2025-12-19
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Fri, Dec 19, 2025, Xu Yilun wrote:
> On Wed, Dec 17, 2025 at 11:01:59AM -0800, Sean Christopherson wrote:
> > On Wed, Dec 17, 2025, Xu Yilun wrote:

Hmm, right, the cpuhp thread is is_percpu_thread(), and KVM's hooks aren't
considered atomic and so run with IRQs enabled.  In practice, it's "fine", because
TDX also exclusively does x86_virt_get_cpu() from cpuhp, i.e. the two users are
mutually exclusive, but relying on that behavior is gross.

> But in this x86_virt_get_cpu(), we need to ensure preemption disabled,
> otherwise caller A increases counter but hasn't do actual VMXON yet and

Ya, that'd be my preference.


Kai, question for you (or anyone else that might know):

Is there any **need** for tdx_cpu_enable() and try_init_module_global() to run
with IRQs disabled?  AFAICT, the lockdep_assert_irqs_disabled() checks added by
commit 6162b310bc21 ("x86/virt/tdx: Add skeleton to enable TDX on demand") were
purely because, _when the code was written_, KVM enabled virtualization via IPI
function calls.

But by the time the KVM code landed upstream in commit fcdbdf63431c ("KVM: VMX:
Initialize TDX during KVM module load"), that was no longer true, thanks to
commit 9a798b1337af ("KVM: Register cpuhp and syscore callbacks when enabling
hardware") setting the stage for doing everything from task context.

However, rather than update the kernel side, e.g. to drop the lockdep assertions
and related comments, commit 9a798b1337af instead did this:

	local_irq_save(flags);
	r = tdx_cpu_enable();
	local_irq_restore(flags);

Somewhat frustratingly, I poked at this when the reworked code was first posted
(https://lore.kernel.org/all/ZyJOiPQnBz31qLZ7@google.com), but it just got swept
under the rug :-(

  : > > +	/* tdx_cpu_enable() must be called with IRQ disabled */
  : > 
  : > I don't find this comment helpfu.  If it explained _why_ tdx_cpu_enable() requires
  : > IRQs to be disabled, then I'd feel differently, but as is, IMO it doesn't add value.
  : 
  : I'll remove the comment.
  : 
  : > 
  : > > +	local_irq_save(flags);
  : > > +	r = tdx_cpu_enable();
  : > > +	local_irq_restore(flags);

Unless TDX _needs_ IRQs to be disabled, I would strongly prefer to drop that code
in prep patches so that it doesn't become even harder to disentagle the history
to figure out why tdx_online_cpu() disables IRQs:

  static int tdx_online_cpu(unsigned int cpu)
  {
	int ret;

	guard(irqsave)();  <=============== why is this here!?!?!

	ret = x86_virt_get_cpu(X86_FEATURE_VMX);
	if (ret)
		return ret;

	ret = tdx_cpu_enable();
	if (ret)
		x86_virt_put_cpu(X86_FEATURE_VMX);

	return ret;
  }

Side topic, KVM's change in behavior also means this comment is stale (though I
think it's worth keeping the assertion, but with a comment saying it's hardening
and paranoia, not a strick requirement).

	/*
	 * IRQs must be disabled as virtualization is enabled in hardware via
	 * function call IPIs, i.e. IRQs need to be disabled to guarantee
	 * virtualization stays disabled.
	 */
	lockdep_assert_irqs_disabled();

---

## [32] Dave Hansen — 2025-12-19
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On 12/19/25 07:40, Sean Christopherson wrote:
> Is there any **need** for tdx_cpu_enable() and try_init_module_global() to run
> with IRQs disabled?  AFAICT, the lockdep_assert_irqs_disabled() checks added by

Yeah, the intent was to prevent "rmmod kvm_intel" from running while TDX
was being initialized. The way it ended up, though, I think TDX init
would have been called in a KVM path _anyway_, which makes this double
useless.

---

## [33] Dave Hansen — 2025-12-19
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On 12/5/25 17:10, Sean Christopherson wrote:
> Move the innermost VMXON and EFER.SVME management logic out of KVM and
> into to core x86 so that TDX can force VMXON without having to rely on

Yeah, that's totally a "please share your drugs" moment, if it happens.

> +static int x86_vmx_get_cpu(void)
> +{
...> +#define x86_virt_call(fn)				\
> +({							\
> +	int __r;					\

I'm not a super big fan of this. I know you KVM folks love your macros
and wrapping function calls in them because you hate grep. ;)

I don't like a foo_get_cpu() call having such fundamentally different
semantics than good old get_cpu() itself. *Especially* when the calls
look like:

	r = x86_virt_call(get_cpu);

and get_cpu() itself it not invovled one bit. This 100% looks like it's
some kind of virt-specific call for get_cpu().

I think it's probably OK to make this get_hw_ref() or inc_hw_ref() or
something to get it away from getting confused with get_cpu().

IMNHO, the macro magic is overkill. A couple of global function pointers
would probably be fine because none of this code is even remotely
performance sensitive. A couple static_call()s would be fine too because
those at least make it blatantly obvious that the thing being called is
variable. A good ol' ops structure would also make things obvious, but
are probably also overkill-adjecent for this.

P.S. In a perfect world, the renames would also be in their own patches,
but I think I can live with it as-is.

---

## [34] Sean Christopherson — 2025-12-19
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Fri, Dec 19, 2025, Dave Hansen wrote:
> On 12/5/25 17:10, Sean Christopherson wrote:
> > +static int x86_vmx_get_cpu(void)

Heh, kvm_x86_call() exists _because_ I like grep and search functionality.  The
number of times I couldn't find something because I was searching for full words
and forgot about the kvm_x86_ prefix...

> I don't like a foo_get_cpu() call having such fundamentally different
> semantics than good old get_cpu() itself. *Especially* when the calls

Oof, yeah, didn't think about a collision with {get,put}_cpu().  How about 
x86_virt_{get,put}_ref()?  I like how the callers read, e.g. "get a reference to
VMX or SVM":

  x86_virt_get_ref(X86_FEATURE_VMX);
  x86_virt_put_ref(X86_FEATURE_VMX);

  x86_virt_get_ref(X86_FEATURE_SVM);
  x86_virt_put_ref(X86_FEATURE_SVM);

> IMNHO, the macro magic is overkill. A couple of global function pointers
> would probably be fine because none of this code is even remotely

Agreed.  I'm not even entirely sure why I took this approach.  I suspect I carried
over the basic concept from code that wanted to run before wiring up function
pointers, and never revisited the implementation once the dust settled.

I haven't tested yet, but I've got this:

  struct x86_virt_ops {
	int feature;
	int (*enable_virtualization_cpu)(void);
	int (*disable_virtualization_cpu)(void);
	void (*emergency_disable_virtualization_cpu)(void);
  };
  static struct x86_virt_ops virt_ops __ro_after_init;

and then usage like:

  int x86_virt_get_ref(int feat)
  {
	int r;

	if (!virt_ops.feature || virt_ops.feature != feat)
		return -EOPNOTSUPP;

	if (this_cpu_inc_return(virtualization_nr_users) > 1)
		return 0;

	r = virt_ops.enable_virtualization_cpu();
	if (r)
		WARN_ON_ONCE(this_cpu_dec_return(virtualization_nr_users));

	return r;
  }
  EXPORT_SYMBOL_GPL(x86_virt_get_ref);

  void x86_virt_put_ref(int feat)
  {
	if (WARN_ON_ONCE(!this_cpu_read(virtualization_nr_users)) ||
	    this_cpu_dec_return(virtualization_nr_users))
		return;

	BUG_ON(virt_ops.disable_virtualization_cpu() && !virt_rebooting);
  }
  EXPORT_SYMBOL_GPL(x86_virt_put_ref);

> P.S. In a perfect world, the renames would also be in their own patches,
> but I think I can live with it as-is.

Ya, I'll chunk the patch up.

---

## [35] Dave Hansen — 2025-12-19
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On 12/19/25 10:35, Sean Christopherson wrote:
> I haven't tested yet, but I've got this:
> 

Yeah, that's much easier to follow, and fixes the naming collision thanks!

---

## [36] Huang, Kai — 2025-12-19
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Fri, 2025-12-19 at 07:40 -0800, Sean Christopherson wrote:
> Kai, question for you (or anyone else that might know):
> 

The other intention was to make tdx_cpu_enable() as IRQ safe, since it was
supposed to be able to be called by multiple in-kernel users but not just
KVM (i.e., also for TDX connect).

But right currently we don't need to call them with IRQ disabled.

---

## [37] Xu Yilun — 2025-12-24
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Wed, Dec 10, 2025 at 06:20:17AM -0800, Sean Christopherson wrote:
> On Wed, Dec 10, 2025, dan.j.williams@intel.com wrote:
> > Sean Christopherson wrote:

I've tested the PCIe Link Encryption without KVM, with the kernel
config:

  CONFIG_INTEL_TDX_HOST=y
  CONFIG_KVM_INTEL=n
  CONFIG_TDX_HOST_SERVICES=y

and

--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -0,0 +1,10 @@
+config TDX_HOST_SERVICES
+       tristate "TDX Host Services Driver"
+       depends on INTEL_TDX_HOST
+       default m

Finally I enabled the combination successfully with a patch below, do we
need the change when TDX_HOST_SERVICES comes?

------------8<----------------------

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 80527299f859..e3e90d1fcad3 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1898,7 +1898,6 @@ config INTEL_TDX_HOST
        bool "Intel Trust Domain Extensions (TDX) host support"
        depends on CPU_SUP_INTEL
        depends on X86_64
-       depends on KVM_INTEL
        depends on X86_X2APIC
        select ARCH_KEEP_MEMBLOCK
        depends on CONTIG_ALLOC
diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
index 77a366afd9f7..26bbf0f21575 100644
--- a/arch/x86/include/asm/virt.h
+++ b/arch/x86/include/asm/virt.h
@@ -6,7 +6,7 @@

 typedef void (cpu_emergency_virt_cb)(void);

-#if IS_ENABLED(CONFIG_KVM_X86)
+#if IS_ENABLED(CONFIG_KVM_X86) || IS_ENABLED(CONFIG_INTEL_TDX_HOST)
 extern bool virt_rebooting;

 void __init x86_virt_init(void);
diff --git a/arch/x86/kvm/Kconfig b/arch/x86/kvm/Kconfig
index 278f08194ec8..28fe309093ed 100644
--- a/arch/x86/kvm/Kconfig
+++ b/arch/x86/kvm/Kconfig
@@ -134,7 +134,7 @@ config X86_SGX_KVM
 config KVM_INTEL_TDX
        bool "Intel Trust Domain Extensions (TDX) support"
        default y
-       depends on INTEL_TDX_HOST
+       depends on INTEL_TDX_HOST && KVM_INTEL
        select KVM_GENERIC_MEMORY_ATTRIBUTES
        select HAVE_KVM_ARCH_GMEM_POPULATE
        help
diff --git a/arch/x86/virt/Makefile b/arch/x86/virt/Makefile
index 6e485751650c..85ed7a06ed88 100644
--- a/arch/x86/virt/Makefile
+++ b/arch/x86/virt/Makefile
@@ -1,4 +1,5 @@
 # SPDX-License-Identifier: GPL-2.0-only
 obj-y  += svm/ vmx/

-obj-$(subst m,y,$(CONFIG_KVM_X86)) += hw.o
\ No newline at end of file
+obj-$(CONFIG_INTEL_TDX_HOST) += hw.o
+obj-$(subst m,y,$(CONFIG_KVM_X86)) += hw.o
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
index 986e780cf438..31ea89069a93 100644
--- a/arch/x86/virt/hw.c
+++ b/arch/x86/virt/hw.c
@@ -48,7 +48,7 @@ static void x86_virt_invoke_kvm_emergency_callback(void)
                kvm_callback();
 }

-#if IS_ENABLED(CONFIG_KVM_INTEL)
+#if IS_ENABLED(CONFIG_KVM_INTEL) || IS_ENABLED(CONFIG_INTEL_TDX_HOST)
 static DEFINE_PER_CPU(struct vmcs *, root_vmcs);

 static int x86_virt_cpu_vmxon(void)
@@ -257,7 +257,8 @@ static __init int x86_svm_init(void) { return -EOPNOTSUPP; }
 ({                                                     \
        int __r;                                        \
                                                        \
-       if (IS_ENABLED(CONFIG_KVM_INTEL) &&             \
+       if ((IS_ENABLED(CONFIG_KVM_INTEL) ||            \
+            IS_ENABLED(CONFIG_INTEL_TDX_HOST)) &&      \
            cpu_feature_enabled(X86_FEATURE_VMX))       \
                __r = x86_vmx_##fn();                   \
        else if (IS_ENABLED(CONFIG_KVM_AMD) &&          \

>

---

## [38] Sean Christopherson — 2025-12-30
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Wed, Dec 24, 2025, Xu Yilun wrote:
> On Wed, Dec 10, 2025 at 06:20:17AM -0800, Sean Christopherson wrote:
> > On Wed, Dec 10, 2025, dan.j.williams@intel.com wrote:

Ya, we'll need something along those lines.  What exactly we want the Kconfig
soup to look like is TBD though, e.g. it may or may not make sense to have a
common config that says "I want virtualization!"?

---

## [39] Dave Hansen — 2026-01-05
*Subject: Re: [PATCH v2 1/7] KVM: x86: Move kvm_rebooting to x86*

On 12/5/25 17:10, Sean Christopherson wrote:
> Move kvm_rebooting, which is only read by x86, to KVM x86 so that it can
> be moved again to core x86 code.  Add a "shutdown" arch hook to facilate

For the pure code move:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

That said, I wouldn't mind some clarification around 'kvm_rebooting' and
a small bit of documentation about what kvm_arch_shutdown() is conceptually.

It doesn't have to be in this set, but maybe:

/*
 * Override this to make global, arch-specific changes which
 * prepare the system to disable hardware virtualization support.
 */
__weak void kvm_arch_shutdown(void)
{
}

and something like:

void kvm_arch_shutdown(void)
{
	/*
	 * Indicate that hardware virtualization support will soon be
	 * disabled asynchronously. Attempts to use hardware
	 * virtualization will start generating errors and exceptions.
	 *
	 * Start being more tolerant of those conditions.
	 */
	kvm_rebooting = true;
	smp_wmb();
}

The barrier is almost certainly not needed in practice. But I do find it
helpful as an indicator that other CPUs are going to be reading this
thing and we have zero clue what they're doing.

---

## [40] Binbin Wu — 2026-01-27
*Subject: Re: [PATCH v2 2/7] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On 12/19/2025 11:40 PM, Sean Christopherson wrote:
> On Fri, Dec 19, 2025, Xu Yilun wrote:
>> On Wed, Dec 17, 2025 at 11:01:59AM -0800, Sean Christopherson wrote:

Side topic:
Isn't the name of check_preemption_disabled() confusing and arguably misleading?

---
