---
title: '[RFC PATCH 0/4] KVM: x86/tdx: Have TDX handle VMXON during bringup'
date: 2025-10-10
last_reply: 2025-11-14
message_count: 24
participants: ['Sean Christopherson', 'Chao Gao', 'Edgecombe, Rick P', 'dan.j.williams@intel.com', 'Alexey Kardashevskiy']
---

## [1] Sean Christopherson — 2025-10-10

This is a sort of middle ground between fully yanking core virtualization
support out of KVM, and unconditionally doing VMXON during boot[0].

I got quite far long on rebasing some internal patches we have to extract the
core virtualization bits out of KVM x86, but as I paged back in all of the
things we had punted on (because they were waaay out of scope for our needs),
I realized more and more that providing truly generic virtualization
instrastructure is vastly different than providing infrastructure that can be
shared by multiple instances of KVM (or things very similar to KVM)[1].

So while I still don't want to blindly do VMXON, I also think that trying to
actually support another in-tree hypervisor, without an imminent user to drive
the development, is a waste of resources, and would saddle KVM with a pile of
pointless complexity.

The idea here is to extract _only_ VMXON+VMXOFF and EFER.SVME toggling.  AFAIK
there's no second user of SVM, i.e. no equivalent to TDX, but I wanted to keep
things as symmetrical as possible.

Emphasis on "only", because leaving VMCS tracking and clearing in KVM is
another key difference from Xin's series.  The "light bulb" moment on that
front is that TDX isn't a hypervisor, and isn't trying to be a hypervisor.
Specifically, TDX should _never_ have it's own VMCSes (that are visible to the
host; the TDX-Module has it's own VMCSes to do SEAMCALL/SEAMRET), and so there
is simply no reason to move that functionality out of KVM.

With that out of the way, dealing with VMXON/VMXOFF and EFER.SVME is a fairly
simple refcounting game.

Oh, and I didn't bother looking to see if it would work, but if TDX only needs
VMXON during boot, then the TDX use of VMXON could be transient.  I.e. TDX
could simply blast on_each_cpu() and forego the cpuhp and syscore hooks (a
non-emergency reboot during init isn't possible).  I don't particuarly care
what TDX does, as it's a fairly minor detail all things concerned.  I went with
the "harder" approach, e.g. to validate keeping the VMXON users count elevated
would do the right thing with respect to CPU offlining, etc.

Lightly tested (see the hacks below to verify the TDX side appears to do what
it's supposed to do), but it seems to work?  Heavily RFC, e.g. the third patch
in particular needs to be chunked up, I'm sure there's polishing to be done,
etc.

[0] https://lore.kernel.org/all/20250909182828.1542362-1-xin@zytor.com
[1] https://lore.kernel.org/all/aOl5EutrdL_OlVOO@google.com

Sean Christopherson (4):
  KVM: x86: Move kvm_rebooting to x86
  KVM: x86: Extract VMXON and EFER.SVME enablement to kernel
  KVM: x86/tdx: Do VMXON and TDX-Module initialization during tdx_init()
  KVM: Bury kvm_{en,dis}able_virtualization() in kvm_main.c once more

 Documentation/arch/x86/tdx.rst              |  26 --
 arch/x86/events/intel/pt.c                  |   1 -
 arch/x86/include/asm/reboot.h               |   3 -
 arch/x86/include/asm/tdx.h                  |   4 -
 arch/x86/include/asm/virt.h                 |  21 ++
 arch/x86/include/asm/vmx.h                  |  11 +
 arch/x86/kernel/cpu/common.c                |   2 +
 arch/x86/kernel/reboot.c                    |  11 -
 arch/x86/kvm/svm/svm.c                      |  34 +-
 arch/x86/kvm/svm/vmenter.S                  |  10 +-
 arch/x86/kvm/vmx/tdx.c                      | 190 +++---------
 arch/x86/kvm/vmx/vmcs.h                     |  11 -
 arch/x86/kvm/vmx/vmenter.S                  |   2 +-
 arch/x86/kvm/vmx/vmx.c                      | 128 +-------
 arch/x86/kvm/x86.c                          |  18 +-
 arch/x86/virt/Makefile                      |   2 +
 arch/x86/virt/hw.c                          | 327 ++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 292 +++++++++--------
 arch/x86/virt/vmx/tdx/tdx.h                 |   8 -
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  10 +-
 include/linux/kvm_host.h                    |  10 +-
 virt/kvm/kvm_main.c                         |  31 +-
 22 files changed, 622 insertions(+), 530 deletions(-)
 create mode 100644 arch/x86/include/asm/virt.h
 create mode 100644 arch/x86/virt/hw.c


base-commit: efcebc8f7aeeba15feb1a5bde70af74d96bf1a76

---

## [2] Sean Christopherson — 2025-10-10
*Subject: [RFC PATCH 1/4] KVM: x86: Move kvm_rebooting to x86*

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c       | 13 +++++++++++++
 arch/x86/kvm/x86.h       |  1 +
 include/linux/kvm_host.h |  2 +-
 virt/kvm/kvm_main.c      | 14 +++++++-------
 4 files changed, 22 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index fe3dc3eb4331..910a51370768 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -705,6 +705,9 @@ static void drop_user_return_notifiers(void)
 		kvm_on_user_return(&msrs->urn);
 }
 
+__visible bool kvm_rebooting;
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
+
 /*
  * Handle a fault on a hardware virtualization (VMX or SVM) instruction.
  *
@@ -13076,6 +13079,16 @@ int kvm_arch_enable_virtualization_cpu(void)
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
index f3dc77f006f9..d2ebe3232f55 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -54,6 +54,7 @@ struct kvm_host_values {
 	u64 arch_capabilities;
 };
 
+extern bool kvm_rebooting;
 void kvm_spurious_fault(void);
 
 #define SIZE_OF_MEMSLOTS_HASHTABLE \
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 680ca838f018..c4f18e6b1604 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -1619,6 +1619,7 @@ static inline void kvm_create_vcpu_debugfs(struct kvm_vcpu *vcpu) {}
 #endif
 
 #ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
+void kvm_arch_shutdown(void);
 /*
  * kvm_arch_{enable,disable}_virtualization() are called on one CPU, under
  * kvm_usage_lock, immediately after/before 0=>1 and 1=>0 transitions of
@@ -2300,7 +2301,6 @@ static inline bool kvm_check_request(int req, struct kvm_vcpu *vcpu)
 
 #ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
 extern bool enable_virt_at_load;
-extern bool kvm_rebooting;
 #endif
 
 extern unsigned int halt_poll_ns;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index b7a0ae2a7b20..4b61889289f0 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -5571,13 +5571,15 @@ bool enable_virt_at_load = true;
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
 
@@ -5631,10 +5633,9 @@ static int kvm_offline_cpu(unsigned int cpu)
 
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
@@ -5643,7 +5644,6 @@ static void kvm_shutdown(void)
 	 * 100% comprehensive.
 	 */
 	pr_info("kvm: exiting hardware virtualization\n");
-	kvm_rebooting = true;
 	on_each_cpu(kvm_disable_virtualization_cpu, NULL, 1);
 }

---

## [3] Sean Christopherson — 2025-10-10
*Subject: [RFC PATCH 2/4] KVM: x86: Extract VMXON and EFER.SVME enablement to kernel*

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/events/intel/pt.c    |   1 -
 arch/x86/include/asm/reboot.h |   3 -
 arch/x86/include/asm/virt.h   |  21 +++
 arch/x86/include/asm/vmx.h    |  11 ++
 arch/x86/kernel/cpu/common.c  |   2 +
 arch/x86/kernel/reboot.c      |  11 --
 arch/x86/kvm/svm/svm.c        |  34 +---
 arch/x86/kvm/svm/vmenter.S    |  10 +-
 arch/x86/kvm/vmx/tdx.c        |   3 +-
 arch/x86/kvm/vmx/vmcs.h       |  11 --
 arch/x86/kvm/vmx/vmenter.S    |   2 +-
 arch/x86/kvm/vmx/vmx.c        | 128 +------------
 arch/x86/kvm/x86.c            |  15 +-
 arch/x86/kvm/x86.h            |   1 -
 arch/x86/virt/Makefile        |   2 +
 arch/x86/virt/hw.c            | 327 ++++++++++++++++++++++++++++++++++
 16 files changed, 392 insertions(+), 190 deletions(-)
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
diff --git a/arch/x86/include/asm/reboot.h b/arch/x86/include/asm/reboot.h
index ecd58ea9a837..512733fec370 100644
--- a/arch/x86/include/asm/reboot.h
+++ b/arch/x86/include/asm/reboot.h
@@ -28,11 +28,8 @@ void __noreturn machine_real_restart(unsigned int type);
 typedef void (cpu_emergency_virt_cb)(void);
 #if IS_ENABLED(CONFIG_KVM_X86)
 void cpu_emergency_register_virt_callback(cpu_emergency_virt_cb *callback);
-void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback);
 void cpu_emergency_disable_virtualization(void);
 #else
-static inline void cpu_emergency_register_virt_callback(cpu_emergency_virt_cb *callback) {}
-static inline void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback) {}
 static inline void cpu_emergency_disable_virtualization(void) {}
 #endif /* CONFIG_KVM_X86 */
 
diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
new file mode 100644
index 000000000000..d691a8532baa
--- /dev/null
+++ b/arch/x86/include/asm/virt.h
@@ -0,0 +1,21 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef _ASM_X86_VIRT_H
+#define _ASM_X86_VIRT_H
+
+#include <asm/reboot.h>
+
+#if IS_ENABLED(CONFIG_KVM_X86)
+extern bool virt_rebooting;
+
+void __init x86_virt_init(void);
+
+int x86_virt_get_cpu(int feat);
+void x86_virt_put_cpu(int feat);
+
+void x86_virt_register_emergency_callback(cpu_emergency_virt_cb *callback);
+void x86_virt_unregister_emergency_callback(cpu_emergency_virt_cb *callback);
+#else
+static __always_inline void x86_virt_init(void) {}
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
index f98ec9c7fc07..9e10a45f0924 100644
--- a/arch/x86/kernel/cpu/common.c
+++ b/arch/x86/kernel/cpu/common.c
@@ -70,6 +70,7 @@
 #include <asm/traps.h>
 #include <asm/sev.h>
 #include <asm/tdx.h>
+#include <asm/virt.h>
 #include <asm/posted_intr.h>
 #include <asm/runtime-const.h>
 
@@ -2119,6 +2120,7 @@ static __init void identify_boot_cpu(void)
 	cpu_detect_tlb(&boot_cpu_data);
 	setup_cr_pinning();
 
+	x86_virt_init();
 	tsx_init();
 	tdx_init();
 	lkgs_init();
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index 964f6b0a3d68..ed7b3fa0d995 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -541,17 +541,6 @@ void cpu_emergency_register_virt_callback(cpu_emergency_virt_cb *callback)
 
 	rcu_assign_pointer(cpu_emergency_virt_callback, callback);
 }
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
 
 /*
  * Disable virtualization, i.e. VMX or SVM, to ensure INIT is recognized during
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 153c12dbf3eb..183894732d0e 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -44,6 +44,7 @@
 #include <asm/traps.h>
 #include <asm/reboot.h>
 #include <asm/fpu/api.h>
+#include <asm/virt.h>
 
 #include <trace/events/ipi.h>
 
@@ -473,27 +474,11 @@ static __always_inline struct sev_es_save_area *sev_es_host_save_area(struct svm
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
+	virt_rebooting = true;
 
-	kvm_cpu_svm_disable();
+	wrmsrq(MSR_VM_HSAVE_PA, 0);
 }
 
 static void svm_disable_virtualization_cpu(void)
@@ -502,7 +487,7 @@ static void svm_disable_virtualization_cpu(void)
 	if (tsc_scaling)
 		__svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 
-	kvm_cpu_svm_disable();
+	x86_virt_put_cpu(X86_FEATURE_SVM);
 
 	amd_pmu_disable_virt();
 }
@@ -511,12 +496,12 @@ static int svm_enable_virtualization_cpu(void)
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
@@ -524,8 +509,6 @@ static int svm_enable_virtualization_cpu(void)
 	sd->next_asid = sd->max_asid + 1;
 	sd->min_asid = max_sev_asid + 1;
 
-	wrmsrq(MSR_EFER, efer | EFER_SVME);
-
 	wrmsrq(MSR_VM_HSAVE_PA, sd->save_area_pa);
 
 	if (static_cpu_has(X86_FEATURE_TSCRATEMSR)) {
@@ -536,7 +519,6 @@ static int svm_enable_virtualization_cpu(void)
 		__svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 	}
 
-
 	/*
 	 * Get OSVW bits.
 	 *
diff --git a/arch/x86/kvm/svm/vmenter.S b/arch/x86/kvm/svm/vmenter.S
index 235c4af6b692..c61cd7830751 100644
--- a/arch/x86/kvm/svm/vmenter.S
+++ b/arch/x86/kvm/svm/vmenter.S
@@ -269,16 +269,16 @@ SYM_FUNC_START(__svm_vcpu_run)
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
 
@@ -365,7 +365,7 @@ SYM_FUNC_START(__svm_sev_es_vcpu_run)
 	RESTORE_GUEST_SPEC_CTRL_BODY
 	RESTORE_HOST_SPEC_CTRL_BODY %sil
 
-3:	cmpb $0, kvm_rebooting(%rip)
+3:	cmpb $0, virt_rebooting(%rip)
 	jne 2b
 	ud2
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 097304bf1e1d..bbf5ee7ec6ba 100644
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
@@ -2069,7 +2070,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
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
index 0a6cf5bff2aa..476b65362a6f 100644
--- a/arch/x86/kvm/vmx/vmenter.S
+++ b/arch/x86/kvm/vmx/vmenter.S
@@ -293,7 +293,7 @@ SYM_INNER_LABEL_ALIGN(vmx_vmexit, SYM_L_GLOBAL)
 	RET
 
 .Lfixup:
-	cmpb $0, _ASM_RIP(kvm_rebooting)
+	cmpb $0, _ASM_RIP(virt_rebooting)
 	jne .Lvmfail
 	ud2
 .Lvmfail:
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 546272a5d34d..229abfa13836 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -49,6 +49,7 @@
 #include <asm/msr.h>
 #include <asm/mwait.h>
 #include <asm/spec-ctrl.h>
+#include <asm/virt.h>
 #include <asm/vmx.h>
 
 #include <trace/events/ipi.h>
@@ -468,7 +469,6 @@ noinline void invept_error(unsigned long ext, u64 eptp)
 	vmx_insn_failed("invept failed: ext=0x%lx eptp=%llx\n", ext, eptp);
 }
 
-static DEFINE_PER_CPU(struct vmcs *, vmxarea);
 DEFINE_PER_CPU(struct vmcs *, current_vmcs);
 /*
  * We maintain a per-CPU linked-list of VMCS loaded on that CPU. This is needed
@@ -675,44 +675,13 @@ static int vmx_set_guest_uret_msr(struct vcpu_vmx *vmx,
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
+	WARN_ON_ONCE(!virt_rebooting);
+	virt_rebooting = true;
 
 	list_for_each_entry(v, &per_cpu(loaded_vmcss_on_cpu, cpu),
 			    loaded_vmcss_on_cpu_link) {
@@ -720,8 +689,6 @@ void vmx_emergency_disable_virtualization_cpu(void)
 		if (v->shadow_vmcs)
 			vmcs_clear(v->shadow_vmcs);
 	}
-
-	kvm_cpu_vmxoff();
 }
 
 static void __loaded_vmcs_clear(void *arg)
@@ -2819,34 +2786,9 @@ int vmx_check_processor_compat(void)
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
@@ -2855,15 +2797,7 @@ int vmx_enable_virtualization_cpu(void)
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
@@ -2880,12 +2814,9 @@ void vmx_disable_virtualization_cpu(void)
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
@@ -2963,47 +2894,6 @@ int alloc_loaded_vmcs(struct loaded_vmcs *loaded_vmcs)
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
@@ -8328,8 +8218,6 @@ void vmx_hardware_unsetup(void)
 
 	if (nested)
 		nested_vmx_hardware_unsetup();
-
-	free_kvm_area();
 }
 
 void vmx_vm_destroy(struct kvm *kvm)
@@ -8634,10 +8522,6 @@ __init int vmx_hardware_setup(void)
 			return r;
 	}
 
-	r = alloc_kvm_area();
-	if (r && nested)
-		nested_vmx_hardware_unsetup();
-
 	kvm_set_posted_intr_wakeup_handler(pi_wakeup_handler);
 
 	/*
@@ -8663,7 +8547,7 @@ __init int vmx_hardware_setup(void)
 
 	kvm_caps.inapplicable_quirks &= ~KVM_X86_QUIRK_IGNORE_GUEST_PAT;
 
-	return r;
+	return 0;
 }
 
 static void vmx_cleanup_l1d_flush(void)
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 910a51370768..9cfed304035f 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -84,6 +84,8 @@
 #include <asm/intel_pt.h>
 #include <asm/emulate_prefix.h>
 #include <asm/sgx.h>
+#include <asm/virt.h>
+
 #include <clocksource/hyperv_timer.h>
 
 #define CREATE_TRACE_POINTS
@@ -705,9 +707,6 @@ static void drop_user_return_notifiers(void)
 		kvm_on_user_return(&msrs->urn);
 }
 
-__visible bool kvm_rebooting;
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
-
 /*
  * Handle a fault on a hardware virtualization (VMX or SVM) instruction.
  *
@@ -718,7 +717,7 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
 noinstr void kvm_spurious_fault(void)
 {
 	/* Fault while not rebooting.  We want the trace. */
-	BUG_ON(!kvm_rebooting);
+	BUG_ON(!virt_rebooting);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_spurious_fault);
 
@@ -12975,12 +12974,12 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_vcpu_deliver_sipi_vector);
 
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
@@ -13082,11 +13081,11 @@ int kvm_arch_enable_virtualization_cpu(void)
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
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index d2ebe3232f55..f3dc77f006f9 100644
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
index 000000000000..12e59cd3da2d
--- /dev/null
+++ b/arch/x86/virt/hw.c
@@ -0,0 +1,327 @@
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
+static bool x86_virt_initialized __ro_after_init;
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
+static int x86_vmx_cpu_vmxoff(void)
+{
+	asm goto("1: vmxoff\n\t"
+		 _ASM_EXTABLE(1b, %l[fault])
+		 ::: "cc", "memory" : fault);
+
+	cr4_clear_bits(X86_CR4_VMXE);
+	return 0;
+
+fault:
+	cr4_clear_bits(X86_CR4_VMXE);
+	return -EIO;
+}
+
+static void x86_vmx_put_cpu(void)
+{
+	if (x86_vmx_cpu_vmxoff())
+		BUG_ON(!virt_rebooting);
+
+	intel_pt_handle_vmx(0);
+}
+
+static void x86_vmx_emergency_disable_virtualization_cpu(void)
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
+		return;
+
+	x86_virt_invoke_kvm_emergency_callback();
+
+	x86_vmx_cpu_vmxoff();
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
+static __init cpu_emergency_virt_cb *x86_vmx_init(void)
+{
+	u64 basic_msr;
+	u32 rev_id;
+	int cpu;
+
+	rdmsrq(MSR_IA32_VMX_BASIC, basic_msr);
+
+	/* IA-32 SDM Vol 3B: VMCS size is never greater than 4kB. */
+	if (WARN_ON_ONCE(vmx_basic_vmcs_size(basic_msr) > PAGE_SIZE))
+		return NULL;
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
+			return NULL;
+		}
+
+		vmcs = page_address(page);
+		vmcs->hdr.revision_id = rev_id;
+		per_cpu(root_vmcs, cpu) = vmcs;
+	}
+
+	return x86_vmx_emergency_disable_virtualization_cpu;
+}
+#else
+static int x86_vmx_get_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static void x86_vmx_put_cpu(void) { BUILD_BUG_ON(1); }
+static __init cpu_emergency_virt_cb *x86_vmx_init(void) { BUILD_BUG_ON(1); return NULL; }
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
+static void x86_svm_put_cpu(void)
+{
+	u64 efer;
+
+	rdmsrq(MSR_EFER, efer);
+	if (efer & EFER_SVME) {
+		/*
+		 * Force GIF=1 prior to disabling SVM, e.g. to ensure INIT and
+		 * NMI aren't blocked.
+		 */
+		asm goto("1: stgi\n\t"
+			 _ASM_EXTABLE(1b, %l[fault])
+			 ::: "memory" : fault);
+		wrmsrq(MSR_EFER, efer & ~EFER_SVME);
+	}
+	return;
+
+fault:
+	wrmsrq(MSR_EFER, efer & ~EFER_SVME);
+	BUG_ON(!virt_rebooting);
+}
+static void x86_svm_emergency_disable_virtualization_cpu(void)
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
+		return;
+
+	x86_virt_invoke_kvm_emergency_callback();
+
+	x86_svm_put_cpu();
+}
+static __init cpu_emergency_virt_cb *x86_svm_init(void)
+{
+	return x86_svm_emergency_disable_virtualization_cpu;
+}
+#else
+static int x86_svm_get_cpu(void) { BUILD_BUG_ON(1); return -EOPNOTSUPP; }
+static void x86_svm_put_cpu(void) { BUILD_BUG_ON(1); }
+static __init cpu_emergency_virt_cb *x86_svm_init(void) { BUILD_BUG_ON(1); return NULL; }
+#endif
+
+static __always_inline bool x86_virt_is_vmx(void)
+{
+	return IS_ENABLED(CONFIG_KVM_INTEL) &&
+	       cpu_feature_enabled(X86_FEATURE_VMX);
+}
+
+static __always_inline bool x86_virt_is_svm(void)
+{
+	return IS_ENABLED(CONFIG_KVM_AMD) &&
+	       cpu_feature_enabled(X86_FEATURE_SVM);
+}
+
+int x86_virt_get_cpu(int feat)
+{
+	int r;
+
+	if (!x86_virt_initialized)
+		return -EOPNOTSUPP;
+
+	if (this_cpu_inc_return(virtualization_nr_users) > 1)
+		return 0;
+
+	if (x86_virt_is_vmx() && feat == X86_FEATURE_VMX)
+		r = x86_vmx_get_cpu();
+	else if (x86_virt_is_svm() && feat == X86_FEATURE_SVM)
+		r = x86_svm_get_cpu();
+	else
+		r = -EOPNOTSUPP;
+
+	if (r)
+		WARN_ON_ONCE(this_cpu_dec_return(virtualization_nr_users));
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(x86_virt_get_cpu);
+
+void x86_virt_put_cpu(int feat)
+{
+	if (WARN_ON_ONCE(!this_cpu_read(virtualization_nr_users)))
+		return;
+
+	if (this_cpu_dec_return(virtualization_nr_users) && !virt_rebooting)
+		return;
+
+	if (x86_virt_is_vmx() && feat == X86_FEATURE_VMX)
+		x86_vmx_put_cpu();
+	else if (x86_virt_is_svm() && feat == X86_FEATURE_SVM)
+		x86_svm_put_cpu();
+	else
+		WARN_ON_ONCE(1);
+}
+EXPORT_SYMBOL_GPL(x86_virt_put_cpu);
+
+void __init x86_virt_init(void)
+{
+	cpu_emergency_virt_cb *vmx_cb = NULL, *svm_cb = NULL;
+
+	if (x86_virt_is_vmx())
+		vmx_cb = x86_vmx_init();
+
+	if (x86_virt_is_svm())
+		svm_cb = x86_svm_init();
+
+	if (!vmx_cb && !svm_cb)
+		return;
+
+	if (WARN_ON_ONCE(vmx_cb && svm_cb))
+		return;
+
+	cpu_emergency_register_virt_callback(vmx_cb ? : svm_cb);
+	x86_virt_initialized = true;
+}

---

## [4] Sean Christopherson — 2025-10-10
*Subject: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module initialization
 during tdx_init()*

TODO: Split this up, write changelogs.

Cc: Chao Gao <chao.gao@intel.com>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Xin Li (Intel) <xin@zytor.com>
Cc: Kai Huang <kai.huang@intel.com>
Cc: Adrian Hunter <adrian.hunter@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 Documentation/arch/x86/tdx.rst              |  26 --
 arch/x86/include/asm/tdx.h                  |   4 -
 arch/x86/kvm/vmx/tdx.c                      | 187 +++----------
 arch/x86/virt/vmx/tdx/tdx.c                 | 292 +++++++++++---------
 arch/x86/virt/vmx/tdx/tdx.h                 |   8 -
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  10 +-
 6 files changed, 201 insertions(+), 326 deletions(-)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 719043cd8b46..3c96f92051af 100644
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
index 7ddef3a69866..650917b49862 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -122,8 +122,6 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 #define seamcall(_fn, _args)		sc_retry(__seamcall, (_fn), (_args))
 #define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
 #define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
-int tdx_cpu_enable(void);
-int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
@@ -196,8 +194,6 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 #else
 static inline void tdx_init(void) { }
-static inline int tdx_cpu_enable(void) { return -ENODEV; }
-static inline int tdx_enable(void)  { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index bbf5ee7ec6ba..d89382971076 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -46,7 +46,7 @@ module_param_named(tdx, enable_tdx, bool, 0444);
 #define TDX_SHARED_BIT_PWL_5 gpa_to_gfn(BIT_ULL(51))
 #define TDX_SHARED_BIT_PWL_4 gpa_to_gfn(BIT_ULL(47))
 
-static enum cpuhp_state tdx_cpuhp_state;
+static enum cpuhp_state tdx_cpuhp_state __ro_after_init;
 
 static const struct tdx_sys_info *tdx_sysinfo;
 
@@ -3345,17 +3345,7 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 
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
@@ -3394,51 +3384,6 @@ static int tdx_offline_cpu(unsigned int cpu)
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
@@ -3462,34 +3407,18 @@ static int __init __tdx_bringup(void)
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
@@ -3524,34 +3453,31 @@ static int __init __tdx_bringup(void)
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
@@ -3563,6 +3489,16 @@ int __init tdx_bringup(void)
 	if (!enable_tdx)
 		return 0;
 
+	if (!cpu_feature_enabled(X86_FEATURE_TDX_HOST_PLATFORM)) {
+		pr_err("TDX not supported by the host platform\n");
+		goto success_disable_tdx;
+	}
+
+	if (!cpu_feature_enabled(X86_FEATURE_OSXSAVE)) {
+		pr_err("OSXSAVE is required for TDX\n");
+		return -EINVAL;
+	}
+
 	if (!enable_ept) {
 		pr_err("EPT is required for TDX\n");
 		goto success_disable_tdx;
@@ -3578,61 +3514,9 @@ int __init tdx_bringup(void)
 		goto success_disable_tdx;
 	}
 
-	if (!cpu_feature_enabled(X86_FEATURE_OSXSAVE)) {
-		pr_err("tdx: OSXSAVE is required for TDX\n");
-		goto success_disable_tdx;
-	}
-
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
-	if (!cpu_feature_enabled(X86_FEATURE_TDX_HOST_PLATFORM)) {
-		pr_err("tdx: no TDX private KeyIDs available\n");
-		goto success_disable_tdx;
-	}
-
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
 
@@ -3641,6 +3525,15 @@ int __init tdx_bringup(void)
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
index c7a9a087ccaf..bf1c1cdd9690 100644
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
 
-static struct tdx_sys_info tdx_sysinfo;
+static struct tdx_sys_info tdx_sysinfo __ro_after_init;
+static bool tdx_module_initialized __ro_after_init;
 
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
 
@@ -181,15 +170,65 @@ int tdx_cpu_enable(void)
 
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
 
@@ -207,7 +246,7 @@ static int add_tdx_memblock(struct list_head *tmb_list, unsigned long start_pfn,
 	return 0;
 }
 
-static void free_tdx_memlist(struct list_head *tmb_list)
+static __init void free_tdx_memlist(struct list_head *tmb_list)
 {
 	/* @tmb_list is protected by mem_hotplug_lock */
 	while (!list_empty(tmb_list)) {
@@ -225,7 +264,7 @@ static void free_tdx_memlist(struct list_head *tmb_list)
  * ranges off in a secondary structure because memblock is modified
  * in memory hotplug while TDX memory regions are fixed.
  */
-static int build_tdx_memlist(struct list_head *tmb_list)
+static __init int build_tdx_memlist(struct list_head *tmb_list)
 {
 	unsigned long start_pfn, end_pfn;
 	int i, nid, ret;
@@ -257,7 +296,7 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
-static int read_sys_metadata_field(u64 field_id, u64 *data)
+static __init int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
 	int ret;
@@ -279,7 +318,7 @@ static int read_sys_metadata_field(u64 field_id, u64 *data)
 
 #include "tdx_global_metadata.c"
 
-static int check_features(struct tdx_sys_info *sysinfo)
+static __init int check_features(struct tdx_sys_info *sysinfo)
 {
 	u64 tdx_features0 = sysinfo->features.tdx_features0;
 
@@ -292,7 +331,7 @@ static int check_features(struct tdx_sys_info *sysinfo)
 }
 
 /* Calculate the actual TDMR size */
-static int tdmr_size_single(u16 max_reserved_per_tdmr)
+static __init int tdmr_size_single(u16 max_reserved_per_tdmr)
 {
 	int tdmr_sz;
 
@@ -306,8 +345,8 @@ static int tdmr_size_single(u16 max_reserved_per_tdmr)
 	return ALIGN(tdmr_sz, TDMR_INFO_ALIGNMENT);
 }
 
-static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
-			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
+static __init int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
+				  struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	size_t tdmr_sz, tdmr_array_sz;
 	void *tdmr_array;
@@ -338,7 +377,7 @@ static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
 	return 0;
 }
 
-static void free_tdmr_list(struct tdmr_info_list *tdmr_list)
+static __init void free_tdmr_list(struct tdmr_info_list *tdmr_list)
 {
 	free_pages_exact(tdmr_list->tdmrs,
 			tdmr_list->max_tdmrs * tdmr_list->tdmr_sz);
@@ -367,8 +406,8 @@ static inline u64 tdmr_end(struct tdmr_info *tdmr)
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
@@ -444,8 +483,8 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
  */
-static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-				      u16 pamt_entry_size)
+static __init unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
+					     u16 pamt_entry_size)
 {
 	unsigned long pamt_sz, nr_pamt_entries;
 
@@ -476,7 +515,7 @@ static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
  * PAMT.  This node will have some memory covered by the TDMR.  The
  * relative amount of memory covered is not considered.
  */
-static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
+static __init int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
 {
 	struct tdx_memblock *tmb;
 
@@ -505,9 +544,9 @@ static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
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
@@ -577,7 +616,7 @@ static void tdmr_get_pamt(struct tdmr_info *tdmr, unsigned long *pamt_base,
 	*pamt_size = pamt_sz;
 }
 
-static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
+static __init void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 		void (*pamt_func)(unsigned long base, unsigned long size))
 {
 	unsigned long pamt_base, pamt_size;
@@ -594,17 +633,17 @@ static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
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
 
@@ -613,9 +652,9 @@ static void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
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
 
@@ -654,12 +693,12 @@ static void reset_tdx_pages(unsigned long base, unsigned long size)
 	mb();
 }
 
-static void tdmr_reset_pamt(struct tdmr_info *tdmr)
+static __init void tdmr_reset_pamt(struct tdmr_info *tdmr)
 {
 	tdmr_do_pamt_func(tdmr, reset_tdx_pages);
 }
 
-static void tdmrs_reset_pamt_all(struct tdmr_info_list *tdmr_list)
+static __init void tdmrs_reset_pamt_all(struct tdmr_info_list *tdmr_list)
 {
 	int i;
 
@@ -667,7 +706,7 @@ static void tdmrs_reset_pamt_all(struct tdmr_info_list *tdmr_list)
 		tdmr_reset_pamt(tdmr_entry(tdmr_list, i));
 }
 
-static unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
+static __init unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
 {
 	unsigned long pamt_size = 0;
 	int i;
@@ -682,8 +721,8 @@ static unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
 	return pamt_size / 1024;
 }
 
-static int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx, u64 addr,
-			      u64 size, u16 max_reserved_per_tdmr)
+static __init int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx,
+				     u64 addr, u64 size, u16 max_reserved_per_tdmr)
 {
 	struct tdmr_reserved_area *rsvd_areas = tdmr->reserved_areas;
 	int idx = *p_idx;
@@ -716,10 +755,10 @@ static int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx, u64 addr,
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
@@ -780,10 +819,10 @@ static int tdmr_populate_rsvd_holes(struct list_head *tmb_list,
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
 
@@ -818,7 +857,7 @@ static int tdmr_populate_rsvd_pamts(struct tdmr_info_list *tdmr_list,
 }
 
 /* Compare function called by sort() for TDMR reserved areas */
-static int rsvd_area_cmp_func(const void *a, const void *b)
+static __init int rsvd_area_cmp_func(const void *a, const void *b)
 {
 	struct tdmr_reserved_area *r1 = (struct tdmr_reserved_area *)a;
 	struct tdmr_reserved_area *r2 = (struct tdmr_reserved_area *)b;
@@ -837,10 +876,10 @@ static int rsvd_area_cmp_func(const void *a, const void *b)
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
 
@@ -865,9 +904,9 @@ static int tdmr_populate_rsvd_areas(struct tdmr_info *tdmr,
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
 
@@ -888,9 +927,9 @@ static int tdmrs_populate_rsvd_areas_all(struct tdmr_info_list *tdmr_list,
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
@@ -922,7 +961,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
-static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
+static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
+				    u64 global_keyid)
 {
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
@@ -1015,7 +1055,7 @@ static int config_global_keyid(void)
 	return ret;
 }
 
-static int init_tdmr(struct tdmr_info *tdmr)
+static __init int init_tdmr(struct tdmr_info *tdmr)
 {
 	u64 next;
 
@@ -1046,7 +1086,7 @@ static int init_tdmr(struct tdmr_info *tdmr)
 	return 0;
 }
 
-static int init_tdmrs(struct tdmr_info_list *tdmr_list)
+static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 {
 	int i;
 
@@ -1065,7 +1105,7 @@ static int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
-static int init_tdx_module(void)
+static __init int init_tdx_module(void)
 {
 	int ret;
 
@@ -1154,68 +1194,45 @@ static int init_tdx_module(void)
 	goto out_put_tdxmem;
 }
 
-static int __tdx_enable(void)
+static __init int tdx_enable(void)
 {
+	enum cpuhp_state state;
 	int ret;
 
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
-
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
@@ -1445,11 +1462,6 @@ void __init tdx_init(void)
 		return;
 	}
 
-#if defined(CONFIG_ACPI) && defined(CONFIG_SUSPEND)
-	pr_info("Disable ACPI S3. Turn off TDX in the BIOS to use ACPI S3.\n");
-	acpi_suspend_lowlevel = NULL;
-#endif
-
 	/*
 	 * Just use the first TDX KeyID as the 'global KeyID' and
 	 * leave the rest for TDX guests.
@@ -1458,22 +1470,30 @@ void __init tdx_init(void)
 	tdx_guest_keyid_start = tdx_keyid_start + 1;
 	tdx_nr_guest_keyids = nr_tdx_keyids - 1;
 
+	err = tdx_enable();
+	if (err)
+		goto err_enable;
+
+#if defined(CONFIG_ACPI) && defined(CONFIG_SUSPEND)
+	pr_info("Disable ACPI S3. Turn off TDX in the BIOS to use ACPI S3.\n");
+	acpi_suspend_lowlevel = NULL;
+#endif
+
 	setup_force_cpu_cap(X86_FEATURE_TDX_HOST_PLATFORM);
 
 	check_tdx_erratum();
+	return;
+
+err_enable:
+	unregister_memory_notifier(&tdx_memory_nb);
 }
 
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

## [5] Sean Christopherson — 2025-10-10
*Subject: [RFC PATCH 4/4] KVM: Bury kvm_{en,dis}able_virtualization() in
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
index c4f18e6b1604..8eb1b0908e1e 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2595,12 +2595,4 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
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
index 4b61889289f0..6bec30b6b6c1 100644
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
@@ -5678,7 +5681,7 @@ static struct syscore_ops kvm_syscore_ops = {
 	.shutdown = kvm_shutdown,
 };
 
-int kvm_enable_virtualization(void)
+static int kvm_enable_virtualization(void)
 {
 	int r;
 
@@ -5723,9 +5726,8 @@ int kvm_enable_virtualization(void)
 	--kvm_usage_count;
 	return r;
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_enable_virtualization);
 
-void kvm_disable_virtualization(void)
+static void kvm_disable_virtualization(void)
 {
 	guard(mutex)(&kvm_usage_lock);
 
@@ -5736,7 +5738,6 @@ void kvm_disable_virtualization(void)
 	cpuhp_remove_state(CPUHP_AP_KVM_ONLINE);
 	kvm_arch_disable_virtualization();
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_disable_virtualization);
 
 static int kvm_init_virtualization(void)
 {
@@ -5752,6 +5753,14 @@ static void kvm_uninit_virtualization(void)
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

## [6] Chao Gao — 2025-10-13
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

>-static int __tdx_enable(void)
>+static __init int tdx_enable(void)

...

>@@ -1445,11 +1462,6 @@ void __init tdx_init(void)
> 		return;

IIRC, existing TDX modules require all CPUs to have completed per-CPU
initialization before TDMR/PAMT initialization.

But at this point, APs are not online, so tdx_enable() will fail here.

---

## [7] Chao Gao — 2025-10-13
*Subject: Re: [RFC PATCH 2/4] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

>+static void x86_svm_emergency_disable_virtualization_cpu(void)
>+{

copy-paste error.

>+void __init x86_virt_init(void)
>+{

To be consistent with x86_virt_{get,put}_cpu(), perhaps we can have a common
emergency callback and let reboot.c call it directly, with the common callback
routing to svm/vmx code according to the hardware type.

>+	x86_virt_initialized = true;
>+}

---

## [8] Sean Christopherson — 2025-10-13
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

On Mon, Oct 13, 2025, Chao Gao wrote:
> >-static int __tdx_enable(void)
> >+static __init int tdx_enable(void)

Ah.  Maybe invoke tdx_enable() through a subsys_initcall() then?

---

## [9] Sean Christopherson — 2025-10-13
*Subject: Re: [RFC PATCH 2/4] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Mon, Oct 13, 2025, Chao Gao wrote:
> >+void __init x86_virt_init(void)
> >+{

Oh, yeah, that's a much better idea, especially if x86_virt_init() runs
unconditionally during boot (as proposed).  cpu_emergency_disable_virtualization()
can be dropped entirely (it'd just be a one-line wrapper).

---

## [10] Edgecombe, Rick P — 2025-10-13
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

On Fri, 2025-10-10 at 15:04 -0700, Sean Christopherson wrote:
> TODO: Split this up, write changelogs.
> 
[snip]
> -
>  static int __init __tdx_bringup(void)

Could pass NULL instead of tdx_online_cpu() and delete this version of
tdx_online_cpu(). Also could remove the error handling too.

Also, can we name the two tdx_offline_cpu()'s differently? This one is all about
keyid's being in use. tdx_hkid_offline_cpu()?

> +	if (r < 0)
> +		goto err_cpuhup;

Why change this condition from goto success_disable_tdx?

> +	}
> +

I think the previous discussion was that there should be a probe and enable
step. We could not fail KVM init if TDX is not supported (probe), but not try to
cleanly handle any other unexpected error (fail enabled).

The existing code mostly has the "probe" type checks in tdx_bringup(), and the
"enable" type checks in __tdx_bringup(). But now the gutted __tdx_bringup() is
very probe-y. Ideally we could separate these into named "install" and "probe"
functions. I don't know if this would be good to do this as part of this series
or later though.

>  	return r;
>  

[snip]

>  
>  /*

One easy thing to break this up would be to do this __init adjustments in a
follow on patch.

---

## [11] Sean Christopherson — 2025-10-13
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

On Mon, Oct 13, 2025, Rick P Edgecombe wrote:
> On Fri, 2025-10-10 at 15:04 -0700, Sean Christopherson wrote:
> > @@ -3524,34 +3453,31 @@ static int __init __tdx_bringup(void)

Oh, nice, I didn't realize (or forgot) the startup call is optional.
 
> Also could remove the error handling too.

No.  Partly on prinicple, but also because CPUHP_AP_ONLINE_DYN can fail if the
kernel runs out of dynamic entries (currently limited to 40).  The kernel WARNs
if it runs out of entries, but KVM should still do the right thing.

> Also, can we name the two tdx_offline_cpu()'s differently? This one is all about
> keyid's being in use. tdx_hkid_offline_cpu()?

Ya.  And change the description to "kvm/cpu/tdx:hkid_packages"?  Or something
like that.

> > +	if (r < 0)
> > +		goto err_cpuhup;

Ah, a copy+paste goof.  I originally moved the code to tdx_enable(), then realized
it as checking OSXSAVE, not XSAVE, and so needed to be done later in boot.  When
I copied it back to KVM, I forgot to restore the goto.

> >  	r = __tdx_bringup();
> > -	if (r) {

Ya, for sure.

---

## [12] Edgecombe, Rick P — 2025-10-13
*Subject: Re: [RFC PATCH 2/4] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Fri, 2025-10-10 at 15:04 -0700, Sean Christopherson wrote:

> +
> +int x86_virt_get_cpu(int feat)

Not sure if I missed some previous discussion or future plans, but doing this
via X86_FEATURE_FOO seems excessive. We could just have x86_virt_get_cpu(void)
afaict? Curious if there is a plan for other things to go here?

---

## [13] dan.j.williams@intel.com — 2025-10-13
*Subject: Re: [RFC PATCH 0/4] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

[ Add Alexey for question below about SEV-TIO needing to enable SNP from
the PSP driver? ]

Sean Christopherson wrote:
> This is a sort of middle ground between fully yanking core virtualization
> support out of KVM, and unconditionally doing VMXON during boot[0].

Thanks for this, Sean!

> I got quite far long on rebasing some internal patches we have to extract the
> core virtualization bits out of KVM x86, but as I paged back in all of the

Alexey did mention in the TEE I/O call that the PSP driver does need to
turn on SVM. Added him to the Cc to clarify if SEV-TIO needs at least
SVM enabled outside of KVM in some cases.

> Emphasis on "only", because leaving VMCS tracking and clearing in KVM is
> another key difference from Xin's series.  The "light bulb" moment on that

With the work-in-progress "Host Services", the expectation is that VMX
would remain on especially because there is no current way to de-init
TDX.

Now, the "TDX always-on even outside of Host Services" this series is
proposing gives me slight pause. I.e. Any resources that TDX gobbles, or
features that TDX is incompatible (ACPI S3), need a trip through a BIOS
menu to turn off.  However, if that becomes a problem in practice we can
circle back later to fix that up.

> could simply blast on_each_cpu() and forego the cpuhp and syscore hooks (a
> non-emergency reboot during init isn't possible).  I don't particuarly care

Sounds good and I read this as "hey, this is the form I would like to
see, when someone else cleans this up and sends it back to me as a
non-RFC".

Thanks again!

---

## [14] Sean Christopherson — 2025-10-13
*Subject: Re: [RFC PATCH 0/4] KVM: x86/tdx: Have TDX handle VMXON during bringup*

On Mon, Oct 13, 2025, dan.j.williams@intel.com wrote:
> > Emphasis on "only", because leaving VMCS tracking and clearing in KVM is
> > another key difference from Xin's series.  The "light bulb" moment on that

What are Host Services?

> Now, the "TDX always-on even outside of Host Services" this series is
> proposing gives me slight pause. I.e. Any resources that TDX gobbles, or

Oooh, by "TDX always-on" you mean invoking tdx_enable() during boot, as opposed
to throwing it into a loadable module.  To be honest, I completely missed the
whole PAMT allocation and imcompatible features side of things.

And Rick already pointed out that doing tdx_enable() during tdx_init() would be
far too early.

So it seems like the simple answer is to continue to have __tdx_bringup() invoke
tdx_enable(), but without all the caveats about the caller needed to hold the
CPUs lock, be post-VMXON, etc.

> > could simply blast on_each_cpu() and forego the cpuhp and syscore hooks (a
> > non-emergency reboot during init isn't possible).  I don't particuarly care

Actually, I think I can take it forward.  Knock wood, but I don't think there's
all that much left to be done.  Heck, even writing the code for the initial RFC
was a pretty short adventure once I had my head wrapped around the concept.

---

## [15] Sean Christopherson — 2025-10-13
*Subject: Re: [RFC PATCH 2/4] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Mon, Oct 13, 2025, Rick P Edgecombe wrote:
> On Fri, 2025-10-10 at 15:04 -0700, Sean Christopherson wrote:
> 

I want to avoid potential problems due to kvm-amd.ko doing x86_virt_get_cpu() and
succeeding on an Intel CPU, and vice versa.  The obvious alternative would be to
have wrappers for VMX and SVM and then do whatever internally, but we'd need some
form of tracking internally no matter what, and I prefer X86_FEATURE_{SVM,VMX}
over one or more booleans.

FWIW, after Chao's feedback, this is what I have locally (a little less foo),
where x86_virt_feature is set during x86_virt_init().

int x86_virt_get_cpu(int feat)
{
	int r;

	if (!x86_virt_feature || x86_virt_feature != feat)
		return -EOPNOTSUPP;

	if (this_cpu_inc_return(virtualization_nr_users) > 1)
		return 0;

	r = x86_virt_call(get_cpu);
	if (r)
		WARN_ON_ONCE(this_cpu_dec_return(virtualization_nr_users));

	return r;
}
EXPORT_SYMBOL_GPL(x86_virt_get_cpu);

---

## [16] dan.j.williams@intel.com — 2025-10-13
*Subject: Re: [RFC PATCH 0/4] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

Sean Christopherson wrote:
> On Mon, Oct 13, 2025, dan.j.williams@intel.com wrote:
> > > Emphasis on "only", because leaving VMCS tracking and clearing in KVM is

That is my catch all name for TDX things that are independent of VMs.
Also called "tdx-host" in the preview patches [1]. This is capabilities
like updating the TDX Module at runtime, and the TEE I/O (TDX Connect)
stuff like establishing PCI device link encryption even if you never
assign that device to a VM.

[1]: http://lore.kernel.org/20250919142237.418648-2-dan.j.williams@intel.com

> > Now, the "TDX always-on even outside of Host Services" this series is
> > proposing gives me slight pause. I.e. Any resources that TDX gobbles, or

Yeah, I like the option to hold off on paying any costs until absolutely
necessary.

The tdx-host driver will also be a direct tdx_enable() consumer, and it
is already prepared for resolving the "multiple consumers to race to
enable" case.

> > > non-emergency reboot during init isn't possible).  I don't particuarly care
> > > what TDX does, as it's a fairly minor detail all things concerned.  I went with

Ack.

---

## [17] Alexey Kardashevskiy — 2025-10-14
*Subject: Re: [RFC PATCH 0/4] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

On 14/10/25 09:22, dan.j.williams@intel.com wrote:
> [ Add Alexey for question below about SEV-TIO needing to enable SNP from
> the PSP driver? ]

Nah, the PSP driver needs to enable those encrypted flavors of KVM (SEV, SEV-ES, SEV-SNP) in the PSP (set up memory keys or RMP) but the basic SVM does not need that, and EFER.SVME enables just it. When those SEV* are needed - KVM calls the PSP driver to enable those in the PSP, and shuts SEV* down when the last SEV* VM stops (or when kvm_amd unloads?). And the PSP cannot see EFER.SVME at any moment to act differently.

So until KVM tries VMRUN'ing a vCPU (+few more instructions), EFER.SVME does not matter afaict. Thanks,

---

## [18] Chao Gao — 2025-10-14
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

On Mon, Oct 13, 2025 at 01:59:21PM -0700, Sean Christopherson wrote:
>On Mon, Oct 13, 2025, Rick P Edgecombe wrote:
>> On Fri, 2025-10-10 at 15:04 -0700, Sean Christopherson wrote:

Is it a good idea to consolidate the two tdx_offline_cpu() functions, i.e.,
integrate KVM's version into x86 core?

From 97165f9933f48d588f5390e2d543d9880c03532d Mon Sep 17 00:00:00 2001
From: Chao Gao <chao.gao@intel.com>
Date: Tue, 14 Oct 2025 01:00:06 -0700
Subject: [PATCH] x86/virt/tdx: Consolidate TDX CPU hotplug handling

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
---
 arch/x86/kvm/vmx/tdx.c      | 67 +------------------------------------
 arch/x86/virt/vmx/tdx/tdx.c | 49 +++++++++++++++++++++++++--
 2 files changed, 47 insertions(+), 69 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d89382971076..beac8ab4cbc1 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -46,8 +46,6 @@ module_param_named(tdx, enable_tdx, bool, 0444);
 #define TDX_SHARED_BIT_PWL_5 gpa_to_gfn(BIT_ULL(51))
 #define TDX_SHARED_BIT_PWL_4 gpa_to_gfn(BIT_ULL(47))
 
-static enum cpuhp_state tdx_cpuhp_state __ro_after_init;
-
 static const struct tdx_sys_info *tdx_sysinfo;
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err)
@@ -206,8 +204,6 @@ static int init_kvm_tdx_caps(const struct tdx_sys_info_td_conf *td_conf,
  */
 static DEFINE_MUTEX(tdx_lock);
 
-static atomic_t nr_configured_hkid;
-
 static bool tdx_operand_busy(u64 err)
 {
	return (err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_BUSY;
@@ -255,7 +251,6 @@ static inline void tdx_hkid_free(struct kvm_tdx *kvm_tdx)
 {
	tdx_guest_keyid_free(kvm_tdx->hkid);
	kvm_tdx->hkid = -1;
-	atomic_dec(&nr_configured_hkid);
	misc_cg_uncharge(MISC_CG_RES_TDX, kvm_tdx->misc_cg, 1);
	put_misc_cg(kvm_tdx->misc_cg);
	kvm_tdx->misc_cg = NULL;
@@ -2487,8 +2482,6 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
	ret = -ENOMEM;
 
-	atomic_inc(&nr_configured_hkid);
-
	tdr_page = alloc_page(GFP_KERNEL);
	if (!tdr_page)
		goto free_hkid;
@@ -3343,51 +3336,10 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
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
@@ -3459,23 +3411,7 @@ static int __init __tdx_bringup(void)
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
@@ -3531,7 +3467,6 @@ void tdx_cleanup(void)
		return;
 
	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
-	cpuhp_remove_state(tdx_cpuhp_state);
 }
 
 void __init tdx_hardware_setup(void)
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index bf1c1cdd9690..201ecb4ad20d 100644
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
@@ -1505,15 +1541,22 @@ EXPORT_SYMBOL_GPL(tdx_get_nr_guest_keyids);
 
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

## [19] dan.j.williams@intel.com — 2025-10-14
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

Chao Gao wrote:
> On Mon, Oct 13, 2025 at 01:59:21PM -0700, Sean Christopherson wrote:
> >On Mon, Oct 13, 2025, Rick P Edgecombe wrote:

This looks good to me, some additional cleanup opportunities below:

> From 97165f9933f48d588f5390e2d543d9880c03532d Mon Sep 17 00:00:00 2001
> From: Chao Gao <chao.gao@intel.com>
[..]
> +	 */
> +#define MSG_ALLPKG_ONLINE \

Why the define?

> +	return -EBUSY;
> +

So, ida has an ida_is_empty() helper. I believe you can just use that
in the offline helper and delete @nr_configured_hkid.

---

## [20] Sean Christopherson — 2025-10-14
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

On Tue, Oct 14, 2025, dan.j.williams@intel.com wrote:
> Chao Gao wrote:
> > >> Also, can we name the two tdx_offline_cpu()'s differently? This one is all about

+1.  This crossed my mind as well, but for once I reeled myself in as I'm very
susceptible to self-induced scope creep :-)

---

## [21] Edgecombe, Rick P — 2025-10-14
*Subject: Re: [RFC PATCH 3/4] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during tdx_init()*

On Tue, 2025-10-14 at 16:35 +0800, Chao Gao wrote:
> Is it a good idea to consolidate the two tdx_offline_cpu() functions, i.e.,
> integrate KVM's version into x86 core?

+1

It fixes a bug too. Currently in __tdx_td_init() if misc_cg_try_charge() fails,
it will decrement nr_configured_hkid in the error path before it got
incremented.

And the cgroups stuff that got plucked from the past seems to have the same
problem. Ideally we could move MISC_CG_RES_TDX accounting too with this change
because it also fits, and it would fix that too.

---

## [22] Chao Gao — 2025-10-17
*Subject: Re: [RFC PATCH 2/4] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

> void vmx_emergency_disable_virtualization_cpu(void)
> {

This is unnecessary as virt_rebooting has been set to true ...

>+static void x86_vmx_emergency_disable_virtualization_cpu(void)
>+{

... here.

and ditto for SVM.

>+
>+	/*

<snip>

>+void x86_virt_put_cpu(int feat)
>+{

any reason to check virt_rebooting here?

It seems unnecessary because both the emergency reboot case and shutdown case
work fine without it, and keeping it might prevent us from discovering real
bugs, e.g., KVM or TDX failing to decrease the refcount.

>+
>+	if (x86_virt_is_vmx() && feat == X86_FEATURE_VMX)

---

## [23] Sean Christopherson — 2025-10-17
*Subject: Re: [RFC PATCH 2/4] KVM: x86: Extract VMXON and EFER.SVME enablement
 to kernel*

On Fri, Oct 17, 2025, Chao Gao wrote:
> > void vmx_emergency_disable_virtualization_cpu(void)
> > {

Yeah, I wasn't sure what to do.  I agree it's redundant, but it's harmless,
whereas not having virt_rebooting set would be Very Bad (TM).  I think you're
probably right, and we should just assume we aren't terrible at programming.
Setting the flag in KVM could even hide latent bugs, e.g. if code runs before
x86_virt_invoke_kvm_emergency_callback().

> >+	/*
> >+	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be

*sigh*

I simply misread my own code (and I suspect I pivoted on what I was doing).  I
just spent ~10 minutes typing up various responses about how the emergency code
needs to _force_ VMX/SVM off, but I kept overlooking the fact that the emergency
hooks bypass the refcounting (which is obviously very intentional).  /facepalm

So yeah, I agree that exempting the refcount on virt_rebooting is bad here.
E.g. if kvm_shutdown() runs before tdx_shutdown(), then KVM will pull the rug
out from under TDX, and hw/virt.c will attempt to disable virtualization twice.
Which is "fine" thanks to the hardening, but gross and unnecessary.

Thanks so much!

> >+
> >+	if (x86_virt_is_vmx() && feat == X86_FEATURE_VMX)

---

## [24] dan.j.williams@intel.com — 2025-11-14
*Subject: Re: [RFC PATCH 0/4] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

dan.j.williams@ wrote:
[..]
> > > Sounds good and I read this as "hey, this is the form I would like to
> > > see, when someone else cleans this up and sends it back to me as a

FYI, this series is now included in tsm.git#staging [1]. Chao had one
fixup to it [2].

Recall that tsm.git#staging is where all of us working on PCI Device
Security (TDX, SEV, and CCA) can start tripping over each others
implementations [3] in a unified tree. 

The initial core work in that tree is a v6.19 candidate as long as at
least one arch implementation is also ready. SEV looks nearly ready [4].
CCA will sit out as it is going through a specification update. TDX is
ready save for this vmxon dependency.

I recall being concerned about the new TDX always-on stance, but I now
think it is ok. Just puts more pressure on the dynamic-PAMT work to
land. In the meantime, disabling TDX in the BIOS is a stopgap for those
that can not tolerate the static-PAMT overhead.

[1]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging
[2]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/commit/?id=406cd719d2a2
[3]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/commit/?id=e3d238ddeec0
[4]: http://lore.kernel.org/20251111063819.4098701-1-aik@amd.com

---
