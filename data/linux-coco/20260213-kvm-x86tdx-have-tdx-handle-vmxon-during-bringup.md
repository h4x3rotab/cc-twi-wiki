---
title: 'KVM: x86/tdx: Have TDX handle VMXON during bringup'
date: 2026-02-13
last_reply: 2026-03-05
message_count: 38
participants: ['Sean Christopherson', 'dan.j.williams@intel.com', 'Huang, Kai', 'Chao Gao', 'Dave Hansen', 'Sagi Shahar']
---

## [1] Sean Christopherson — 2026-02-13

Assuming I didn't break anything between v2 and v3, I think this is ready to
rip.  Given the scope of the KVM changes, and that they extend outside of x86,
my preference is to take this through the KVM tree.  But a stable topic branch
in tip would work too, though I think we'd want it sooner than later so that
it can be used as a base. 

Chao, I deliberately omitted your Tested-by, as I shuffled things around enough
while splitting up the main patch that I'm not 100% positive I didn't regress
anything relative to v2.


The idea here is to extract _only_ VMXON+VMXOFF and EFER.SVME toggling.  AFAIK
there's no second user of SVM, i.e. no equivalent to TDX, but I wanted to keep
things as symmetrical as possible.

TDX isn't a hypervisor, and isn't trying to be a hypervisor. Specifically, TDX
should _never_ have it's own VMCSes (that are visible to the host; the
TDX-Module has it's own VMCSes to do SEAMCALL/SEAMRET), and so there is simply
no reason to move that functionality out of KVM.

With that out of the way, dealing with VMXON/VMXOFF and EFER.SVME is a fairly
simple refcounting game.

v3:
 - https://lore.kernel.org/all/20251206011054.494190-1-seanjc@google.com
 - Split up the move from KVM => virt into smaller patches. [Dan]
 - Collect reviews. [Dan, Chao, Dave]
 - Update sample dmesg output and hotplug angle in docs. [Chao]
 - Add comments in kvm_arch_shutdown() to try and explain the madness. [Dave]
 - Add a largely superfluous smp_wmb() in kvm_arch_shutdown() to provide a
   convienent location for documenting the flow. [Dave]
 - Disable preemption in x86_virt_{get,put}_ref() so that changes in how
   KVM and/or TDX use the APIs doesn't result in bugs. [Xu]
 - Add a patch to drop the bogus "IRQs must be disabled" rule in
   tdx_cpu_enable().
 - Tag more TDX helpers as __init. [Chao]
 - Don't treat loading kvm-intel.ko with tdx=1 as fatal if the system doesn't
   have a TDX-Module available. [Chao]

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

Sean Christopherson (15):
  KVM: x86: Move kvm_rebooting to x86
  KVM: VMX: Move architectural "vmcs" and "vmcs_hdr" structures to
    public vmx.h
  KVM: x86: Move "kvm_rebooting" to kernel as "virt_rebooting"
  KVM: VMX: Unconditionally allocate root VMCSes during boot CPU bringup
  x86/virt: Force-clear X86_FEATURE_VMX if configuring root VMCS fails
  KVM: VMX: Move core VMXON enablement to kernel
  KVM: SVM: Move core EFER.SVME enablement to kernel
  KVM: x86: Move bulk of emergency virtualizaton logic to virt subsystem
  x86/virt: Add refcounting of VMX/SVM usage to support multiple
    in-kernel users
  x86/virt/tdx: Drop the outdated requirement that TDX be enabled in IRQ
    context
  KVM: x86/tdx: Do VMXON and TDX-Module initialization during subsys
    init
  x86/virt/tdx: Tag a pile of functions as __init, and globals as
    __ro_after_init
  x86/virt/tdx: Use ida_is_empty() to detect if any TDs may be running
  KVM: Bury kvm_{en,dis}able_virtualization() in kvm_main.c once more
  KVM: TDX: Fold tdx_bringup() into tdx_hardware_setup()

 Documentation/arch/x86/tdx.rst              |  36 +-
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
 arch/x86/kvm/vmx/main.c                     |  19 +-
 arch/x86/kvm/vmx/tdx.c                      | 210 ++----------
 arch/x86/kvm/vmx/tdx.h                      |   8 +-
 arch/x86/kvm/vmx/vmcs.h                     |  11 -
 arch/x86/kvm/vmx/vmenter.S                  |   2 +-
 arch/x86/kvm/vmx/vmx.c                      | 138 +-------
 arch/x86/kvm/x86.c                          |  29 +-
 arch/x86/virt/Makefile                      |   2 +
 arch/x86/virt/hw.c                          | 359 ++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 321 +++++++++--------
 arch/x86/virt/vmx/tdx/tdx.h                 |   8 -
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  10 +-
 include/linux/kvm_host.h                    |  16 +-
 virt/kvm/kvm_main.c                         |  31 +-
 27 files changed, 717 insertions(+), 656 deletions(-)
 create mode 100644 arch/x86/include/asm/virt.h
 create mode 100644 arch/x86/virt/hw.c


base-commit: 183bb0ce8c77b0fd1fb25874112bc8751a461e49

---

## [2] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 01/16] KVM: x86: Move kvm_rebooting to x86*

Move kvm_rebooting, which is only read by x86, to KVM x86 so that it can
be moved again to core x86 code.  Add a "shutdown" arch hook to facilate
setting the flag in KVM x86, along with a pile of comments to provide more
context around what KVM x86 is doing and why.

Reviewed-by: Chao Gao <chao.gao@intel.com>
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c       | 22 ++++++++++++++++++++++
 arch/x86/kvm/x86.h       |  1 +
 include/linux/kvm_host.h |  8 +++++++-
 virt/kvm/kvm_main.c      | 14 +++++++-------
 4 files changed, 37 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index db3f393192d9..77edc24f8309 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -700,6 +700,9 @@ static void drop_user_return_notifiers(void)
 		kvm_on_user_return(&msrs->urn);
 }
 
+__visible bool kvm_rebooting;
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
+
 /*
  * Handle a fault on a hardware virtualization (VMX or SVM) instruction.
  *
@@ -13178,6 +13181,25 @@ int kvm_arch_enable_virtualization_cpu(void)
 	return 0;
 }
 
+void kvm_arch_shutdown(void)
+{
+	/*
+	 * Set kvm_rebooting to indicate that KVM has asynchronously disabled
+	 * hardware virtualization, i.e. that errors and/or exceptions on SVM
+	 * and VMX instructions are expected and should be ignored.
+	 */
+	kvm_rebooting = true;
+
+	/*
+	 * Ensure kvm_rebooting is visible before IPIs are sent to other CPUs
+	 * to disable virtualization.  Effectively pairs with the reception of
+	 * the IPI (kvm_rebooting is read in task/exception context, but only
+	 * _needs_ to be read as %true after the IPI function callback disables
+	 * virtualization).
+	 */
+	smp_wmb();
+}
+
 void kvm_arch_disable_virtualization_cpu(void)
 {
 	kvm_x86_call(disable_virtualization_cpu)();
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 94d4f07aaaa0..b314649e5c02 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -54,6 +54,7 @@ struct kvm_host_values {
 	u64 arch_capabilities;
 };
 
+extern bool kvm_rebooting;
 void kvm_spurious_fault(void);
 
 #define SIZE_OF_MEMSLOTS_HASHTABLE \
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 2c7d76262898..981b55c0a3a7 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -1630,6 +1630,13 @@ static inline void kvm_create_vcpu_debugfs(struct kvm_vcpu *vcpu) {}
 #endif
 
 #ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
+/*
+ * kvm_arch_shutdown() is invoked immediately prior to forcefully disabling
+ * hardware virtualization on all CPUs via IPI function calls (in preparation
+ * for shutdown or reboot), e.g. to allow arch code to prepare for disabling
+ * virtualization while KVM may be actively running vCPUs.
+ */
+void kvm_arch_shutdown(void);
 /*
  * kvm_arch_{enable,disable}_virtualization() are called on one CPU, under
  * kvm_usage_lock, immediately after/before 0=>1 and 1=>0 transitions of
@@ -2305,7 +2312,6 @@ static inline bool kvm_check_request(int req, struct kvm_vcpu *vcpu)
 
 #ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
 extern bool enable_virt_at_load;
-extern bool kvm_rebooting;
 #endif
 
 extern unsigned int halt_poll_ns;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 571cf0d6ec01..e081e7244299 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -5593,13 +5593,15 @@ bool enable_virt_at_load = true;
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
 
@@ -5653,10 +5655,9 @@ static int kvm_offline_cpu(unsigned int cpu)
 
 static void kvm_shutdown(void *data)
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
@@ -5665,7 +5666,6 @@ static void kvm_shutdown(void *data)
 	 * 100% comprehensive.
 	 */
 	pr_info("kvm: exiting hardware virtualization\n");
-	kvm_rebooting = true;
 	on_each_cpu(kvm_disable_virtualization_cpu, NULL, 1);
 }

---

## [3] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 02/16] KVM: VMX: Move architectural "vmcs" and "vmcs_hdr"
 structures to public vmx.h*

Move "struct vmcs" and "struct vmcs_hdr" to asm/vmx.h in anticipation of
moving VMXON/VMXOFF to the core kernel (VMXON requires a "root" VMCS with
the appropriate revision ID in its header).

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/vmx.h | 11 +++++++++++
 arch/x86/kvm/vmx/vmcs.h    | 11 -----------
 2 files changed, 11 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/vmx.h b/arch/x86/include/asm/vmx.h
index b92ff87e3560..37080382df54 100644
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
diff --git a/arch/x86/kvm/vmx/vmcs.h b/arch/x86/kvm/vmx/vmcs.h
index 66d747e265b1..1f16ddeae9cb 100644
--- a/arch/x86/kvm/vmx/vmcs.h
+++ b/arch/x86/kvm/vmx/vmcs.h
@@ -22,17 +22,6 @@
 #define VMCS12_IDX_TO_ENC(idx) ROL16(idx, 10)
 #define ENC_TO_VMCS12_IDX(enc) ROL16(enc, 6)
 
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

---

## [4] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 03/16] KVM: x86: Move "kvm_rebooting" to kernel as "virt_rebooting"*

Move "kvm_rebooting" to the kernel, exported for KVM, as one of many steps
towards extracting the innermost VMXON and EFER.SVME management logic out
of KVM and into to core x86.

For lack of a better name, call the new file "hw.c", to yield "virt
hardware" when combined with its parent directory.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/virt.h | 11 +++++++++++
 arch/x86/kvm/svm/svm.c      |  3 ++-
 arch/x86/kvm/svm/vmenter.S  | 10 +++++-----
 arch/x86/kvm/vmx/tdx.c      |  3 ++-
 arch/x86/kvm/vmx/vmenter.S  |  2 +-
 arch/x86/kvm/vmx/vmx.c      |  5 +++--
 arch/x86/kvm/x86.c          | 17 ++++++++---------
 arch/x86/kvm/x86.h          |  1 -
 arch/x86/virt/Makefile      |  2 ++
 arch/x86/virt/hw.c          |  7 +++++++
 10 files changed, 41 insertions(+), 20 deletions(-)
 create mode 100644 arch/x86/include/asm/virt.h
 create mode 100644 arch/x86/virt/hw.c

diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
new file mode 100644
index 000000000000..131b9bf9ef3c
--- /dev/null
+++ b/arch/x86/include/asm/virt.h
@@ -0,0 +1,11 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef _ASM_X86_VIRT_H
+#define _ASM_X86_VIRT_H
+
+#include <linux/types.h>
+
+#if IS_ENABLED(CONFIG_KVM_X86)
+extern bool virt_rebooting;
+#endif
+
+#endif /* _ASM_X86_VIRT_H */
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 8f8bc863e214..0ae66c770ebc 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -44,6 +44,7 @@
 #include <asm/traps.h>
 #include <asm/reboot.h>
 #include <asm/fpu/api.h>
+#include <asm/virt.h>
 
 #include <trace/events/ipi.h>
 
@@ -495,7 +496,7 @@ static inline void kvm_cpu_svm_disable(void)
 
 static void svm_emergency_disable_virtualization_cpu(void)
 {
-	kvm_rebooting = true;
+	virt_rebooting = true;
 
 	kvm_cpu_svm_disable();
 }
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
index 5df9d32d2058..0c790eb0bfa6 100644
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
index 967b58a8ab9d..fc6e3b620866 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -48,6 +48,7 @@
 #include <asm/msr.h>
 #include <asm/mwait.h>
 #include <asm/spec-ctrl.h>
+#include <asm/virt.h>
 #include <asm/vmx.h>
 
 #include <trace/events/ipi.h>
@@ -814,13 +815,13 @@ void vmx_emergency_disable_virtualization_cpu(void)
 	int cpu = raw_smp_processor_id();
 	struct loaded_vmcs *v;
 
-	kvm_rebooting = true;
+	virt_rebooting = true;
 
 	/*
 	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be
 	 * set in task context.  If this races with VMX is disabled by an NMI,
 	 * VMCLEAR and VMXOFF may #UD, but KVM will eat those faults due to
-	 * kvm_rebooting set.
+	 * virt_rebooting set.
 	 */
 	if (!(__read_cr4() & X86_CR4_VMXE))
 		return;
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 77edc24f8309..69937d14f5e1 100644
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
@@ -700,9 +702,6 @@ static void drop_user_return_notifiers(void)
 		kvm_on_user_return(&msrs->urn);
 }
 
-__visible bool kvm_rebooting;
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
-
 /*
  * Handle a fault on a hardware virtualization (VMX or SVM) instruction.
  *
@@ -713,7 +712,7 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_rebooting);
 noinstr void kvm_spurious_fault(void)
 {
 	/* Fault while not rebooting.  We want the trace. */
-	BUG_ON(!kvm_rebooting);
+	BUG_ON(!virt_rebooting);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_spurious_fault);
 
@@ -13184,16 +13183,16 @@ int kvm_arch_enable_virtualization_cpu(void)
 void kvm_arch_shutdown(void)
 {
 	/*
-	 * Set kvm_rebooting to indicate that KVM has asynchronously disabled
+	 * Set virt_rebooting to indicate that KVM has asynchronously disabled
 	 * hardware virtualization, i.e. that errors and/or exceptions on SVM
 	 * and VMX instructions are expected and should be ignored.
 	 */
-	kvm_rebooting = true;
+	virt_rebooting = true;
 
 	/*
-	 * Ensure kvm_rebooting is visible before IPIs are sent to other CPUs
+	 * Ensure virt_rebooting is visible before IPIs are sent to other CPUs
 	 * to disable virtualization.  Effectively pairs with the reception of
-	 * the IPI (kvm_rebooting is read in task/exception context, but only
+	 * the IPI (virt_rebooting is read in task/exception context, but only
 	 * _needs_ to be read as %true after the IPI function callback disables
 	 * virtualization).
 	 */
@@ -13214,7 +13213,7 @@ void kvm_arch_disable_virtualization_cpu(void)
 	 * disable virtualization arrives.  Handle the extreme edge case here
 	 * instead of trying to account for it in the normal flows.
 	 */
-	if (in_task() || WARN_ON_ONCE(!kvm_rebooting))
+	if (in_task() || WARN_ON_ONCE(!virt_rebooting))
 		drop_user_return_notifiers();
 	else
 		__module_get(THIS_MODULE);
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index b314649e5c02..94d4f07aaaa0 100644
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
index 000000000000..df3dc18d19b4
--- /dev/null
+++ b/arch/x86/virt/hw.c
@@ -0,0 +1,7 @@
+// SPDX-License-Identifier: GPL-2.0-only
+#include <linux/kvm_types.h>
+
+#include <asm/virt.h>
+
+__visible bool virt_rebooting;
+EXPORT_SYMBOL_FOR_KVM(virt_rebooting);

---

## [5] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 04/16] KVM: VMX: Unconditionally allocate root VMCSes
 during boot CPU bringup*

Allocate the root VMCS (misleading called "vmxarea" and "kvm_area" in KVM)
for each possible CPU during early boot CPU bringup, before early TDX
initialization, so that TDX can eventually do VMXON on-demand (to make
SEAMCALLs) without needing to load kvm-intel.ko.  Allocate the pages early
on, e.g. instead of trying to do so on-demand, to avoid having to juggle
allocation failures at runtime.

Opportunistically rename the per-CPU pointers to better reflect the role
of the VMCS.  Use Intel's "root VMCS" terminology, e.g. from various VMCS
patents[1][2] and older SDMs, not the more opaque "VMXON region" used in
recent versions of the SDM.  While it's possible the VMCS passed to VMXON
no longer serves as _the_ root VMCS on modern CPUs, it is still in effect
a "root mode VMCS", as described in the patents.

Link: https://patentimages.storage.googleapis.com/c7/e4/32/d7a7def5580667/WO2013101191A1.pdf [1]
Link: https://patentimages.storage.googleapis.com/13/f6/8d/1361fab8c33373/US20080163205A1.pdf [2]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/virt.h  | 13 ++++++-
 arch/x86/kernel/cpu/common.c |  2 +
 arch/x86/kvm/vmx/vmx.c       | 58 ++---------------------------
 arch/x86/virt/hw.c           | 71 ++++++++++++++++++++++++++++++++++++
 4 files changed, 89 insertions(+), 55 deletions(-)

diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
index 131b9bf9ef3c..0da6db4f5b0c 100644
--- a/arch/x86/include/asm/virt.h
+++ b/arch/x86/include/asm/virt.h
@@ -2,10 +2,21 @@
 #ifndef _ASM_X86_VIRT_H
 #define _ASM_X86_VIRT_H
 
-#include <linux/types.h>
+#include <linux/percpu-defs.h>
+
+#include <asm/reboot.h>
 
 #if IS_ENABLED(CONFIG_KVM_X86)
 extern bool virt_rebooting;
+
+void __init x86_virt_init(void);
+
+#if IS_ENABLED(CONFIG_KVM_INTEL)
+DECLARE_PER_CPU(struct vmcs *, root_vmcs);
+#endif
+
+#else
+static __always_inline void x86_virt_init(void) {}
 #endif
 
 #endif /* _ASM_X86_VIRT_H */
diff --git a/arch/x86/kernel/cpu/common.c b/arch/x86/kernel/cpu/common.c
index e7ab22fce3b5..dda9e41292db 100644
--- a/arch/x86/kernel/cpu/common.c
+++ b/arch/x86/kernel/cpu/common.c
@@ -71,6 +71,7 @@
 #include <asm/traps.h>
 #include <asm/sev.h>
 #include <asm/tdx.h>
+#include <asm/virt.h>
 #include <asm/posted_intr.h>
 #include <asm/runtime-const.h>
 
@@ -2143,6 +2144,7 @@ static __init void identify_boot_cpu(void)
 	cpu_detect_tlb(&boot_cpu_data);
 	setup_cr_pinning();
 
+	x86_virt_init();
 	tsx_init();
 	tdx_init();
 	lkgs_init();
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index fc6e3b620866..abd4830f71d8 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -580,7 +580,6 @@ noinline void invept_error(unsigned long ext, u64 eptp)
 	vmx_insn_failed("invept failed: ext=0x%lx eptp=%llx\n", ext, eptp);
 }
 
-static DEFINE_PER_CPU(struct vmcs *, vmxarea);
 DEFINE_PER_CPU(struct vmcs *, current_vmcs);
 /*
  * We maintain a per-CPU linked-list of VMCS loaded on that CPU. This is needed
@@ -2934,6 +2933,9 @@ static bool __kvm_is_vmx_supported(void)
 		return false;
 	}
 
+	if (!per_cpu(root_vmcs, cpu))
+		return false;
+
 	return true;
 }
 
@@ -3008,7 +3010,7 @@ static int kvm_cpu_vmxon(u64 vmxon_pointer)
 int vmx_enable_virtualization_cpu(void)
 {
 	int cpu = raw_smp_processor_id();
-	u64 phys_addr = __pa(per_cpu(vmxarea, cpu));
+	u64 phys_addr = __pa(per_cpu(root_vmcs, cpu));
 	int r;
 
 	if (cr4_read_shadow() & X86_CR4_VMXE)
@@ -3129,47 +3131,6 @@ int alloc_loaded_vmcs(struct loaded_vmcs *loaded_vmcs)
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
@@ -8566,8 +8527,6 @@ void vmx_hardware_unsetup(void)
 
 	if (nested)
 		nested_vmx_hardware_unsetup();
-
-	free_kvm_area();
 }
 
 void vmx_vm_destroy(struct kvm *kvm)
@@ -8870,10 +8829,6 @@ __init int vmx_hardware_setup(void)
 			return r;
 	}
 
-	r = alloc_kvm_area();
-	if (r)
-		goto err_kvm_area;
-
 	kvm_set_posted_intr_wakeup_handler(pi_wakeup_handler);
 
 	/*
@@ -8900,11 +8855,6 @@ __init int vmx_hardware_setup(void)
 	kvm_caps.inapplicable_quirks &= ~KVM_X86_QUIRK_IGNORE_GUEST_PAT;
 
 	return 0;
-
-err_kvm_area:
-	if (nested)
-		nested_vmx_hardware_unsetup();
-	return r;
 }
 
 void vmx_exit(void)
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
index df3dc18d19b4..56972f594d90 100644
--- a/arch/x86/virt/hw.c
+++ b/arch/x86/virt/hw.c
@@ -1,7 +1,78 @@
 // SPDX-License-Identifier: GPL-2.0-only
+#include <linux/cpu.h>
+#include <linux/cpumask.h>
+#include <linux/errno.h>
 #include <linux/kvm_types.h>
+#include <linux/list.h>
+#include <linux/percpu.h>
 
+#include <asm/perf_event.h>
+#include <asm/processor.h>
 #include <asm/virt.h>
+#include <asm/vmx.h>
 
 __visible bool virt_rebooting;
 EXPORT_SYMBOL_FOR_KVM(virt_rebooting);
+
+#if IS_ENABLED(CONFIG_KVM_INTEL)
+DEFINE_PER_CPU(struct vmcs *, root_vmcs);
+EXPORT_PER_CPU_SYMBOL(root_vmcs);
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
+		page = __alloc_pages_node(node, GFP_KERNEL | __GFP_ZERO, 0);
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
+static __init int x86_vmx_init(void) { return -EOPNOTSUPP; }
+#endif
+
+void __init x86_virt_init(void)
+{
+	x86_vmx_init();
+}

---

## [6] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 05/16] x86/virt: Force-clear X86_FEATURE_VMX if configuring
 root VMCS fails*

If allocating and configuring a root VMCS fails, clear X86_FEATURE_VMX in
all CPUs so that KVM doesn't need to manually check root_vmcs.  As added
bonuses, clearing VMX will reflect that VMX is unusable in /proc/cpuinfo,
and will avoid a futile auto-probe of kvm-intel.ko.

WARN if allocating a root VMCS page fails, e.g. to help users figure out
why VMX is broken in the unlikely scenario something goes sideways during
boot (and because the allocation should succeed unless there's a kernel
bug).  Tweak KVM's error message to suggest checking kernel logs if VMX is
unsupported (in addition to checking BIOS).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/vmx.c |  7 ++++---
 arch/x86/virt/hw.c     | 14 ++++++++++++--
 2 files changed, 16 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index abd4830f71d8..e767835a4f3a 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -2927,14 +2927,15 @@ static bool __kvm_is_vmx_supported(void)
 		return false;
 	}
 
-	if (!this_cpu_has(X86_FEATURE_MSR_IA32_FEAT_CTL) ||
-	    !this_cpu_has(X86_FEATURE_VMX)) {
+	if (!this_cpu_has(X86_FEATURE_MSR_IA32_FEAT_CTL)) {
 		pr_err("VMX not enabled (by BIOS) in MSR_IA32_FEAT_CTL on CPU %d\n", cpu);
 		return false;
 	}
 
-	if (!per_cpu(root_vmcs, cpu))
+	if (!this_cpu_has(X86_FEATURE_VMX)) {
+		pr_err("VMX not fully enabled on CPU %d.  Check kernel logs and/or BIOS\n", cpu);
 		return false;
+	}
 
 	return true;
 }
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
index 56972f594d90..40495872fdfb 100644
--- a/arch/x86/virt/hw.c
+++ b/arch/x86/virt/hw.c
@@ -28,7 +28,7 @@ static __init void x86_vmx_exit(void)
 	}
 }
 
-static __init int x86_vmx_init(void)
+static __init int __x86_vmx_init(void)
 {
 	u64 basic_msr;
 	u32 rev_id;
@@ -56,7 +56,7 @@ static __init int x86_vmx_init(void)
 		struct vmcs *vmcs;
 
 		page = __alloc_pages_node(node, GFP_KERNEL | __GFP_ZERO, 0);
-		if (!page) {
+		if (WARN_ON_ONCE(!page)) {
 			x86_vmx_exit();
 			return -ENOMEM;
 		}
@@ -68,6 +68,16 @@ static __init int x86_vmx_init(void)
 
 	return 0;
 }
+
+static __init int x86_vmx_init(void)
+{
+	int r;
+
+	r = __x86_vmx_init();
+	if (r)
+		setup_clear_cpu_cap(X86_FEATURE_VMX);
+	return r;
+}
 #else
 static __init int x86_vmx_init(void) { return -EOPNOTSUPP; }
 #endif

---

## [7] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 06/16] KVM: VMX: Move core VMXON enablement to kernel*

Move the innermost VMXON+VMXOFF logic out of KVM and into to core x86 so
that TDX can (eventually) force VMXON without having to rely on KVM being
loaded, e.g. to do SEAMCALLs during initialization.

Opportunistically update the comment regarding emergency disabling via NMI
to clarify that virt_rebooting will be set by _another_ emergency callback,
i.e. that virt_rebooting doesn't need to be set before VMCLEAR, only
before _this_ invocation does VMXOFF.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/events/intel/pt.c  |  1 -
 arch/x86/include/asm/virt.h |  6 +--
 arch/x86/kvm/vmx/vmx.c      | 73 +++----------------------------
 arch/x86/virt/hw.c          | 85 ++++++++++++++++++++++++++++++++++++-
 4 files changed, 92 insertions(+), 73 deletions(-)

diff --git a/arch/x86/events/intel/pt.c b/arch/x86/events/intel/pt.c
index 44524a387c58..b5726b50e77d 100644
--- a/arch/x86/events/intel/pt.c
+++ b/arch/x86/events/intel/pt.c
@@ -1591,7 +1591,6 @@ void intel_pt_handle_vmx(int on)
 
 	local_irq_restore(flags);
 }
-EXPORT_SYMBOL_FOR_KVM(intel_pt_handle_vmx);
 
 /*
  * PMU callbacks
diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
index 0da6db4f5b0c..cca0210a5c16 100644
--- a/arch/x86/include/asm/virt.h
+++ b/arch/x86/include/asm/virt.h
@@ -2,8 +2,6 @@
 #ifndef _ASM_X86_VIRT_H
 #define _ASM_X86_VIRT_H
 
-#include <linux/percpu-defs.h>
-
 #include <asm/reboot.h>
 
 #if IS_ENABLED(CONFIG_KVM_X86)
@@ -12,7 +10,9 @@ extern bool virt_rebooting;
 void __init x86_virt_init(void);
 
 #if IS_ENABLED(CONFIG_KVM_INTEL)
-DECLARE_PER_CPU(struct vmcs *, root_vmcs);
+int x86_vmx_enable_virtualization_cpu(void);
+int x86_vmx_disable_virtualization_cpu(void);
+void x86_vmx_emergency_disable_virtualization_cpu(void);
 #endif
 
 #else
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index e767835a4f3a..36238cc694fd 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -786,41 +786,16 @@ static int vmx_set_guest_uret_msr(struct vcpu_vmx *vmx,
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
 
-	virt_rebooting = true;
-
 	/*
 	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be
-	 * set in task context.  If this races with VMX is disabled by an NMI,
-	 * VMCLEAR and VMXOFF may #UD, but KVM will eat those faults due to
-	 * virt_rebooting set.
+	 * set in task context.  If this races with _another_ emergency call
+	 * from NMI context, VMCLEAR may #UD, but KVM will eat those faults due
+	 * to virt_rebooting being set by the interrupting NMI callback.
 	 */
 	if (!(__read_cr4() & X86_CR4_VMXE))
 		return;
@@ -832,7 +807,7 @@ void vmx_emergency_disable_virtualization_cpu(void)
 			vmcs_clear(v->shadow_vmcs);
 	}
 
-	kvm_cpu_vmxoff();
+	x86_vmx_emergency_disable_virtualization_cpu();
 }
 
 static void __loaded_vmcs_clear(void *arg)
@@ -2988,34 +2963,9 @@ int vmx_check_processor_compat(void)
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
-	u64 phys_addr = __pa(per_cpu(root_vmcs, cpu));
-	int r;
-
-	if (cr4_read_shadow() & X86_CR4_VMXE)
-		return -EBUSY;
 
 	/*
 	 * This can happen if we hot-added a CPU but failed to allocate
@@ -3024,15 +2974,7 @@ int vmx_enable_virtualization_cpu(void)
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
+	return x86_vmx_enable_virtualization_cpu();
 }
 
 static void vmclear_local_loaded_vmcss(void)
@@ -3049,12 +2991,9 @@ void vmx_disable_virtualization_cpu(void)
 {
 	vmclear_local_loaded_vmcss();
 
-	if (kvm_cpu_vmxoff())
-		kvm_spurious_fault();
+	x86_vmx_disable_virtualization_cpu();
 
 	hv_reset_evmcs();
-
-	intel_pt_handle_vmx(0);
 }
 
 struct vmcs *alloc_vmcs_cpu(bool shadow, int cpu, gfp_t flags)
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
index 40495872fdfb..dc426c2bc24a 100644
--- a/arch/x86/virt/hw.c
+++ b/arch/x86/virt/hw.c
@@ -15,8 +15,89 @@ __visible bool virt_rebooting;
 EXPORT_SYMBOL_FOR_KVM(virt_rebooting);
 
 #if IS_ENABLED(CONFIG_KVM_INTEL)
-DEFINE_PER_CPU(struct vmcs *, root_vmcs);
-EXPORT_PER_CPU_SYMBOL(root_vmcs);
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
+int x86_vmx_enable_virtualization_cpu(void)
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
+EXPORT_SYMBOL_FOR_KVM(x86_vmx_enable_virtualization_cpu);
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
+int x86_vmx_disable_virtualization_cpu(void)
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
+EXPORT_SYMBOL_FOR_KVM(x86_vmx_disable_virtualization_cpu);
+
+void x86_vmx_emergency_disable_virtualization_cpu(void)
+{
+	virt_rebooting = true;
+
+	/*
+	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be
+	 * set in task context.  If this races with _another_ emergency call
+	 * from NMI context, VMXOFF may #UD, but kernel will eat those faults
+	 * due to virt_rebooting being set by the interrupting NMI callback.
+	 */
+	if (!(__read_cr4() & X86_CR4_VMXE))
+		return;
+
+	x86_vmx_disable_virtualization_cpu();
+}
+EXPORT_SYMBOL_FOR_KVM(x86_vmx_emergency_disable_virtualization_cpu);
 
 static __init void x86_vmx_exit(void)
 {

---

## [8] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 07/16] KVM: SVM: Move core EFER.SVME enablement to kernel*

Move the innermost EFER.SVME logic out of KVM and into to core x86 to land
the SVM support alongside VMX support.  This will allow providing a more
unified API from the kernel to KVM, and will allow moving the bulk of the
emergency disabling insanity out of KVM without having a weird split
between kernel and KVM for SVM vs. VMX.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/virt.h |  6 +++++
 arch/x86/kvm/svm/svm.c      | 33 +++++------------------
 arch/x86/virt/hw.c          | 53 +++++++++++++++++++++++++++++++++++++
 3 files changed, 65 insertions(+), 27 deletions(-)

diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
index cca0210a5c16..9a0753eaa20c 100644
--- a/arch/x86/include/asm/virt.h
+++ b/arch/x86/include/asm/virt.h
@@ -15,6 +15,12 @@ int x86_vmx_disable_virtualization_cpu(void);
 void x86_vmx_emergency_disable_virtualization_cpu(void);
 #endif
 
+#if IS_ENABLED(CONFIG_KVM_AMD)
+int x86_svm_enable_virtualization_cpu(void);
+int x86_svm_disable_virtualization_cpu(void);
+void x86_svm_emergency_disable_virtualization_cpu(void);
+#endif
+
 #else
 static __always_inline void x86_virt_init(void) {}
 #endif
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 0ae66c770ebc..5f033bf3ba83 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -478,27 +478,9 @@ static __always_inline struct sev_es_save_area *sev_es_host_save_area(struct svm
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
-	virt_rebooting = true;
-
-	kvm_cpu_svm_disable();
+	wrmsrq(MSR_VM_HSAVE_PA, 0);
 }
 
 static void svm_disable_virtualization_cpu(void)
@@ -507,7 +489,7 @@ static void svm_disable_virtualization_cpu(void)
 	if (tsc_scaling)
 		__svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 
-	kvm_cpu_svm_disable();
+	x86_svm_disable_virtualization_cpu();
 
 	amd_pmu_disable_virt();
 }
@@ -516,12 +498,12 @@ static int svm_enable_virtualization_cpu(void)
 {
 
 	struct svm_cpu_data *sd;
-	uint64_t efer;
 	int me = raw_smp_processor_id();
+	int r;
 
-	rdmsrq(MSR_EFER, efer);
-	if (efer & EFER_SVME)
-		return -EBUSY;
+	r = x86_svm_enable_virtualization_cpu();
+	if (r)
+		return r;
 
 	sd = per_cpu_ptr(&svm_data, me);
 	sd->asid_generation = 1;
@@ -529,8 +511,6 @@ static int svm_enable_virtualization_cpu(void)
 	sd->next_asid = sd->max_asid + 1;
 	sd->min_asid = max_sev_asid + 1;
 
-	wrmsrq(MSR_EFER, efer | EFER_SVME);
-
 	wrmsrq(MSR_VM_HSAVE_PA, sd->save_area_pa);
 
 	if (static_cpu_has(X86_FEATURE_TSCRATEMSR)) {
@@ -541,7 +521,6 @@ static int svm_enable_virtualization_cpu(void)
 		__svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 	}
 
-
 	/*
 	 * Get OSVW bits.
 	 *
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
index dc426c2bc24a..014e9dfab805 100644
--- a/arch/x86/virt/hw.c
+++ b/arch/x86/virt/hw.c
@@ -163,6 +163,59 @@ static __init int x86_vmx_init(void)
 static __init int x86_vmx_init(void) { return -EOPNOTSUPP; }
 #endif
 
+#if IS_ENABLED(CONFIG_KVM_AMD)
+int x86_svm_enable_virtualization_cpu(void)
+{
+	u64 efer;
+
+	if (!cpu_feature_enabled(X86_FEATURE_SVM))
+		return -EOPNOTSUPP;
+
+	rdmsrq(MSR_EFER, efer);
+	if (efer & EFER_SVME)
+		return -EBUSY;
+
+	wrmsrq(MSR_EFER, efer | EFER_SVME);
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM(x86_svm_enable_virtualization_cpu);
+
+int x86_svm_disable_virtualization_cpu(void)
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
+EXPORT_SYMBOL_FOR_KVM(x86_svm_disable_virtualization_cpu);
+
+void x86_svm_emergency_disable_virtualization_cpu(void)
+{
+	u64 efer;
+
+	virt_rebooting = true;
+
+	rdmsrq(MSR_EFER, efer);
+	if (!(efer & EFER_SVME))
+		return;
+
+	x86_svm_disable_virtualization_cpu();
+}
+EXPORT_SYMBOL_FOR_KVM(x86_svm_emergency_disable_virtualization_cpu);
+#endif
+
 void __init x86_virt_init(void)
 {
 	x86_vmx_init();

---

## [9] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 08/16] KVM: x86: Move bulk of emergency virtualizaton logic
 to virt subsystem*

Move the majority of the code related to disabling hardware virtualization
in emergency from KVM into the virt subsystem so that virt can take full
ownership of the state of SVM/VMX.  This will allow refcounting usage of
SVM/VMX so that KVM and the TDX subsystem can enable VMX without stomping
on each other.

To route the emergency callback to the "right" vendor code, add to avoid
mixing vendor and generic code, implement a x86_virt_ops structure to
track the emergency callback, along with the SVM vs. VMX (vs. "none")
feature that is active.

To avoid having to choose between SVM and VMX, simply refuse to enable
either if both are somehow supported.  No known CPU supports both SVM and
VMX, and it's comically unlikely such a CPU will ever exist.

Leave KVM's clearing of loaded VMCSes and MSR_VM_HSAVE_PA in KVM, via a
callback explicitly scoped to KVM.  Loading VMCSes and saving/restoring
host state are firmly tied to running VMs, and thus are (a) KVM's
responsibility and (b) operations that are still exclusively reserved for
KVM (as far as in-tree code is concerned).  I.e. the contract being
established is that non-KVM subsystems can utilize virtualization, but for
all intents and purposes cannot act as full-blown hypervisors.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |   3 +-
 arch/x86/include/asm/reboot.h   |  11 ---
 arch/x86/include/asm/virt.h     |   9 ++-
 arch/x86/kernel/crash.c         |   3 +-
 arch/x86/kernel/reboot.c        |  63 ++--------------
 arch/x86/kernel/smp.c           |   5 +-
 arch/x86/kvm/vmx/vmx.c          |  11 ---
 arch/x86/kvm/x86.c              |   4 +-
 arch/x86/virt/hw.c              | 123 +++++++++++++++++++++++++++++---
 9 files changed, 138 insertions(+), 94 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index ff07c45e3c73..0bda52fbcae5 100644
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
index 9a0753eaa20c..2c35534437e0 100644
--- a/arch/x86/include/asm/virt.h
+++ b/arch/x86/include/asm/virt.h
@@ -4,6 +4,8 @@
 
 #include <asm/reboot.h>
 
+typedef void (cpu_emergency_virt_cb)(void);
+
 #if IS_ENABLED(CONFIG_KVM_X86)
 extern bool virt_rebooting;
 
@@ -12,17 +14,20 @@ void __init x86_virt_init(void);
 #if IS_ENABLED(CONFIG_KVM_INTEL)
 int x86_vmx_enable_virtualization_cpu(void);
 int x86_vmx_disable_virtualization_cpu(void);
-void x86_vmx_emergency_disable_virtualization_cpu(void);
 #endif
 
 #if IS_ENABLED(CONFIG_KVM_AMD)
 int x86_svm_enable_virtualization_cpu(void);
 int x86_svm_disable_virtualization_cpu(void);
-void x86_svm_emergency_disable_virtualization_cpu(void);
 #endif
 
+int x86_virt_emergency_disable_virtualization_cpu(void);
+
+void x86_virt_register_emergency_callback(cpu_emergency_virt_cb *callback);
+void x86_virt_unregister_emergency_callback(cpu_emergency_virt_cb *callback);
 #else
 static __always_inline void x86_virt_init(void) {}
+static inline int x86_virt_emergency_disable_virtualization_cpu(void) { return -ENOENT; }
 #endif
 
 #endif /* _ASM_X86_VIRT_H */
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
index 6032fa9ec753..0bab8863375a 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -27,6 +27,7 @@
 #include <asm/cpu.h>
 #include <asm/nmi.h>
 #include <asm/smp.h>
+#include <asm/virt.h>
 
 #include <linux/ctype.h>
 #include <linux/mc146818rtc.h>
@@ -532,51 +533,6 @@ static inline void kb_wait(void)
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
-EXPORT_SYMBOL_FOR_KVM(cpu_emergency_register_virt_callback);
-
-void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback)
-{
-	if (WARN_ON_ONCE(rcu_access_pointer(cpu_emergency_virt_callback) != callback))
-		return;
-
-	rcu_assign_pointer(cpu_emergency_virt_callback, NULL);
-	synchronize_rcu();
-}
-EXPORT_SYMBOL_FOR_KVM(cpu_emergency_unregister_virt_callback);
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
@@ -588,16 +544,11 @@ static void emergency_reboot_disable_virtualization(void)
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
@@ -875,10 +826,10 @@ static int crash_nmi_callback(unsigned int val, struct pt_regs *regs)
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
 
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 36238cc694fd..c02fd7e91809 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -791,23 +791,12 @@ void vmx_emergency_disable_virtualization_cpu(void)
 	int cpu = raw_smp_processor_id();
 	struct loaded_vmcs *v;
 
-	/*
-	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be
-	 * set in task context.  If this races with _another_ emergency call
-	 * from NMI context, VMCLEAR may #UD, but KVM will eat those faults due
-	 * to virt_rebooting being set by the interrupting NMI callback.
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
-	x86_vmx_emergency_disable_virtualization_cpu();
 }
 
 static void __loaded_vmcs_clear(void *arg)
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 69937d14f5e1..4f30acd639f3 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -13076,12 +13076,12 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_vcpu_deliver_sipi_vector);
 
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
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
index 014e9dfab805..73c8309ba3fb 100644
--- a/arch/x86/virt/hw.c
+++ b/arch/x86/virt/hw.c
@@ -11,9 +11,45 @@
 #include <asm/virt.h>
 #include <asm/vmx.h>
 
+struct x86_virt_ops {
+	int feature;
+	void (*emergency_disable_virtualization_cpu)(void);
+};
+static struct x86_virt_ops virt_ops __ro_after_init;
+
 __visible bool virt_rebooting;
 EXPORT_SYMBOL_FOR_KVM(virt_rebooting);
 
+static cpu_emergency_virt_cb __rcu *kvm_emergency_callback;
+
+void x86_virt_register_emergency_callback(cpu_emergency_virt_cb *callback)
+{
+	if (WARN_ON_ONCE(rcu_access_pointer(kvm_emergency_callback)))
+		return;
+
+	rcu_assign_pointer(kvm_emergency_callback, callback);
+}
+EXPORT_SYMBOL_FOR_KVM(x86_virt_register_emergency_callback);
+
+void x86_virt_unregister_emergency_callback(cpu_emergency_virt_cb *callback)
+{
+	if (WARN_ON_ONCE(rcu_access_pointer(kvm_emergency_callback) != callback))
+		return;
+
+	rcu_assign_pointer(kvm_emergency_callback, NULL);
+	synchronize_rcu();
+}
+EXPORT_SYMBOL_FOR_KVM(x86_virt_unregister_emergency_callback);
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
 #if IS_ENABLED(CONFIG_KVM_INTEL)
 static DEFINE_PER_CPU(struct vmcs *, root_vmcs);
 
@@ -42,6 +78,9 @@ int x86_vmx_enable_virtualization_cpu(void)
 {
 	int r;
 
+	if (virt_ops.feature != X86_FEATURE_VMX)
+		return -EOPNOTSUPP;
+
 	if (cr4_read_shadow() & X86_CR4_VMXE)
 		return -EBUSY;
 
@@ -82,22 +121,24 @@ int x86_vmx_disable_virtualization_cpu(void)
 }
 EXPORT_SYMBOL_FOR_KVM(x86_vmx_disable_virtualization_cpu);
 
-void x86_vmx_emergency_disable_virtualization_cpu(void)
+static void x86_vmx_emergency_disable_virtualization_cpu(void)
 {
 	virt_rebooting = true;
 
 	/*
 	 * Note, CR4.VMXE can be _cleared_ in NMI context, but it can only be
 	 * set in task context.  If this races with _another_ emergency call
-	 * from NMI context, VMXOFF may #UD, but kernel will eat those faults
-	 * due to virt_rebooting being set by the interrupting NMI callback.
+	 * from NMI context, VMCLEAR (in KVM) and VMXOFF may #UD, but KVM and
+	 * the kernel will eat those faults due to virt_rebooting being set by
+	 * the interrupting NMI callback.
 	 */
 	if (!(__read_cr4() & X86_CR4_VMXE))
 		return;
 
+	x86_virt_invoke_kvm_emergency_callback();
+
 	x86_vmx_disable_virtualization_cpu();
 }
-EXPORT_SYMBOL_FOR_KVM(x86_vmx_emergency_disable_virtualization_cpu);
 
 static __init void x86_vmx_exit(void)
 {
@@ -111,6 +152,11 @@ static __init void x86_vmx_exit(void)
 
 static __init int __x86_vmx_init(void)
 {
+	const struct x86_virt_ops vmx_ops = {
+		.feature = X86_FEATURE_VMX,
+		.emergency_disable_virtualization_cpu = x86_vmx_emergency_disable_virtualization_cpu,
+	};
+
 	u64 basic_msr;
 	u32 rev_id;
 	int cpu;
@@ -147,6 +193,7 @@ static __init int __x86_vmx_init(void)
 		per_cpu(root_vmcs, cpu) = vmcs;
 	}
 
+	memcpy(&virt_ops, &vmx_ops, sizeof(virt_ops));
 	return 0;
 }
 
@@ -161,6 +208,7 @@ static __init int x86_vmx_init(void)
 }
 #else
 static __init int x86_vmx_init(void) { return -EOPNOTSUPP; }
+static __init void x86_vmx_exit(void) { }
 #endif
 
 #if IS_ENABLED(CONFIG_KVM_AMD)
@@ -168,7 +216,7 @@ int x86_svm_enable_virtualization_cpu(void)
 {
 	u64 efer;
 
-	if (!cpu_feature_enabled(X86_FEATURE_SVM))
+	if (virt_ops.feature != X86_FEATURE_SVM)
 		return -EOPNOTSUPP;
 
 	rdmsrq(MSR_EFER, efer);
@@ -201,7 +249,7 @@ int x86_svm_disable_virtualization_cpu(void)
 }
 EXPORT_SYMBOL_FOR_KVM(x86_svm_disable_virtualization_cpu);
 
-void x86_svm_emergency_disable_virtualization_cpu(void)
+static void x86_svm_emergency_disable_virtualization_cpu(void)
 {
 	u64 efer;
 
@@ -211,12 +259,71 @@ void x86_svm_emergency_disable_virtualization_cpu(void)
 	if (!(efer & EFER_SVME))
 		return;
 
+	x86_virt_invoke_kvm_emergency_callback();
+
 	x86_svm_disable_virtualization_cpu();
 }
-EXPORT_SYMBOL_FOR_KVM(x86_svm_emergency_disable_virtualization_cpu);
+
+static __init int x86_svm_init(void)
+{
+	const struct x86_virt_ops svm_ops = {
+		.feature = X86_FEATURE_SVM,
+		.emergency_disable_virtualization_cpu = x86_svm_emergency_disable_virtualization_cpu,
+	};
+
+	if (!cpu_feature_enabled(X86_FEATURE_SVM))
+		return -EOPNOTSUPP;
+
+	memcpy(&virt_ops, &svm_ops, sizeof(virt_ops));
+	return 0;
+}
+#else
+static __init int x86_svm_init(void) { return -EOPNOTSUPP; }
 #endif
 
+/*
+ * Disable virtualization, i.e. VMX or SVM, to ensure INIT is recognized during
+ * reboot.  VMX blocks INIT if the CPU is post-VMXON, and SVM blocks INIT if
+ * GIF=0, i.e. if the crash occurred between CLGI and STGI.
+ */
+int x86_virt_emergency_disable_virtualization_cpu(void)
+{
+	/* Ensure the !feature check can't get false positives. */
+	BUILD_BUG_ON(!X86_FEATURE_SVM || !X86_FEATURE_VMX);
+
+	if (!virt_ops.feature)
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
+	virt_ops.emergency_disable_virtualization_cpu();
+	return 0;
+}
+
 void __init x86_virt_init(void)
 {
-	x86_vmx_init();
+	/*
+	 * Attempt to initialize both SVM and VMX, and simply use whichever one
+	 * is present.  Rsefuse to enable/use SVM or VMX if both are somehow
+	 * supported.  No known CPU supports both SVM and VMX.
+	 */
+	bool has_vmx = !x86_vmx_init();
+	bool has_svm = !x86_svm_init();
+
+	if (WARN_ON_ONCE(has_vmx && has_svm)) {
+		x86_vmx_exit();
+		memset(&virt_ops, 0, sizeof(virt_ops));
+	}
 }

---

## [10] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 09/16] x86/virt: Add refcounting of VMX/SVM usage to
 support multiple in-kernel users*

Implement a per-CPU refcounting scheme so that "users" of hardware
virtualization, e.g. KVM and the future TDX code, can co-exist without
pulling the rug out from under each other.  E.g. if KVM were to disable
VMX on module unload or when the last KVM VM was destroyed, SEAMCALLs from
the TDX subsystem would #UD and panic the kernel.

Disable preemption in the get/put APIs to ensure virtualization is fully
enabled/disabled before returning to the caller.  E.g. if the task were
preempted after a 0=>1 transition, the new task would see a 1=>2 and thus
return without enabling virtualization.  Explicitly disable preemption
instead of requiring the caller to do so, because the need to disable
preemption is an artifact of the implementation.  E.g. from KVM's
perspective there is no _need_ to disable preemption as KVM guarantees the
pCPU on which it is running is stable (but preemption is enabled).

Opportunistically abstract away SVM vs. VMX in the public APIs by using
X86_FEATURE_{SVM,VMX} to communicate what technology the caller wants to
enable and use.

Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/virt.h | 11 ++-----
 arch/x86/kvm/svm/svm.c      |  4 +--
 arch/x86/kvm/vmx/vmx.c      |  4 +--
 arch/x86/virt/hw.c          | 64 +++++++++++++++++++++++++++----------
 4 files changed, 53 insertions(+), 30 deletions(-)

diff --git a/arch/x86/include/asm/virt.h b/arch/x86/include/asm/virt.h
index 2c35534437e0..1558a0673d06 100644
--- a/arch/x86/include/asm/virt.h
+++ b/arch/x86/include/asm/virt.h
@@ -11,15 +11,8 @@ extern bool virt_rebooting;
 
 void __init x86_virt_init(void);
 
-#if IS_ENABLED(CONFIG_KVM_INTEL)
-int x86_vmx_enable_virtualization_cpu(void);
-int x86_vmx_disable_virtualization_cpu(void);
-#endif
-
-#if IS_ENABLED(CONFIG_KVM_AMD)
-int x86_svm_enable_virtualization_cpu(void);
-int x86_svm_disable_virtualization_cpu(void);
-#endif
+int x86_virt_get_ref(int feat);
+void x86_virt_put_ref(int feat);
 
 int x86_virt_emergency_disable_virtualization_cpu(void);
 
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 5f033bf3ba83..539fb4306dce 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -489,7 +489,7 @@ static void svm_disable_virtualization_cpu(void)
 	if (tsc_scaling)
 		__svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 
-	x86_svm_disable_virtualization_cpu();
+	x86_virt_put_ref(X86_FEATURE_SVM);
 
 	amd_pmu_disable_virt();
 }
@@ -501,7 +501,7 @@ static int svm_enable_virtualization_cpu(void)
 	int me = raw_smp_processor_id();
 	int r;
 
-	r = x86_svm_enable_virtualization_cpu();
+	r = x86_virt_get_ref(X86_FEATURE_SVM);
 	if (r)
 		return r;
 
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index c02fd7e91809..6200cf4dbd26 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -2963,7 +2963,7 @@ int vmx_enable_virtualization_cpu(void)
 	if (kvm_is_using_evmcs() && !hv_get_vp_assist_page(cpu))
 		return -EFAULT;
 
-	return x86_vmx_enable_virtualization_cpu();
+	return x86_virt_get_ref(X86_FEATURE_VMX);
 }
 
 static void vmclear_local_loaded_vmcss(void)
@@ -2980,7 +2980,7 @@ void vmx_disable_virtualization_cpu(void)
 {
 	vmclear_local_loaded_vmcss();
 
-	x86_vmx_disable_virtualization_cpu();
+	x86_virt_put_ref(X86_FEATURE_VMX);
 
 	hv_reset_evmcs();
 }
diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
index 73c8309ba3fb..c898f16fe612 100644
--- a/arch/x86/virt/hw.c
+++ b/arch/x86/virt/hw.c
@@ -13,6 +13,8 @@
 
 struct x86_virt_ops {
 	int feature;
+	int (*enable_virtualization_cpu)(void);
+	int (*disable_virtualization_cpu)(void);
 	void (*emergency_disable_virtualization_cpu)(void);
 };
 static struct x86_virt_ops virt_ops __ro_after_init;
@@ -20,6 +22,8 @@ static struct x86_virt_ops virt_ops __ro_after_init;
 __visible bool virt_rebooting;
 EXPORT_SYMBOL_FOR_KVM(virt_rebooting);
 
+static DEFINE_PER_CPU(int, virtualization_nr_users);
+
 static cpu_emergency_virt_cb __rcu *kvm_emergency_callback;
 
 void x86_virt_register_emergency_callback(cpu_emergency_virt_cb *callback)
@@ -74,13 +78,10 @@ static int x86_virt_cpu_vmxon(void)
 	return -EFAULT;
 }
 
-int x86_vmx_enable_virtualization_cpu(void)
+static int x86_vmx_enable_virtualization_cpu(void)
 {
 	int r;
 
-	if (virt_ops.feature != X86_FEATURE_VMX)
-		return -EOPNOTSUPP;
-
 	if (cr4_read_shadow() & X86_CR4_VMXE)
 		return -EBUSY;
 
@@ -94,7 +95,6 @@ int x86_vmx_enable_virtualization_cpu(void)
 
 	return 0;
 }
-EXPORT_SYMBOL_FOR_KVM(x86_vmx_enable_virtualization_cpu);
 
 /*
  * Disable VMX and clear CR4.VMXE (even if VMXOFF faults)
@@ -105,7 +105,7 @@ EXPORT_SYMBOL_FOR_KVM(x86_vmx_enable_virtualization_cpu);
  * faults are guaranteed to be due to the !post-VMXON check unless the CPU is
  * magically in RM, VM86, compat mode, or at CPL>0.
  */
-int x86_vmx_disable_virtualization_cpu(void)
+static int x86_vmx_disable_virtualization_cpu(void)
 {
 	int r = -EIO;
 
@@ -119,7 +119,6 @@ int x86_vmx_disable_virtualization_cpu(void)
 	intel_pt_handle_vmx(0);
 	return r;
 }
-EXPORT_SYMBOL_FOR_KVM(x86_vmx_disable_virtualization_cpu);
 
 static void x86_vmx_emergency_disable_virtualization_cpu(void)
 {
@@ -154,6 +153,8 @@ static __init int __x86_vmx_init(void)
 {
 	const struct x86_virt_ops vmx_ops = {
 		.feature = X86_FEATURE_VMX,
+		.enable_virtualization_cpu = x86_vmx_enable_virtualization_cpu,
+		.disable_virtualization_cpu = x86_vmx_disable_virtualization_cpu,
 		.emergency_disable_virtualization_cpu = x86_vmx_emergency_disable_virtualization_cpu,
 	};
 
@@ -212,13 +213,10 @@ static __init void x86_vmx_exit(void) { }
 #endif
 
 #if IS_ENABLED(CONFIG_KVM_AMD)
-int x86_svm_enable_virtualization_cpu(void)
+static int x86_svm_enable_virtualization_cpu(void)
 {
 	u64 efer;
 
-	if (virt_ops.feature != X86_FEATURE_SVM)
-		return -EOPNOTSUPP;
-
 	rdmsrq(MSR_EFER, efer);
 	if (efer & EFER_SVME)
 		return -EBUSY;
@@ -226,9 +224,8 @@ int x86_svm_enable_virtualization_cpu(void)
 	wrmsrq(MSR_EFER, efer | EFER_SVME);
 	return 0;
 }
-EXPORT_SYMBOL_FOR_KVM(x86_svm_enable_virtualization_cpu);
 
-int x86_svm_disable_virtualization_cpu(void)
+static int x86_svm_disable_virtualization_cpu(void)
 {
 	int r = -EIO;
 	u64 efer;
@@ -247,7 +244,6 @@ int x86_svm_disable_virtualization_cpu(void)
 	wrmsrq(MSR_EFER, efer & ~EFER_SVME);
 	return r;
 }
-EXPORT_SYMBOL_FOR_KVM(x86_svm_disable_virtualization_cpu);
 
 static void x86_svm_emergency_disable_virtualization_cpu(void)
 {
@@ -268,6 +264,8 @@ static __init int x86_svm_init(void)
 {
 	const struct x86_virt_ops svm_ops = {
 		.feature = X86_FEATURE_SVM,
+		.enable_virtualization_cpu = x86_svm_enable_virtualization_cpu,
+		.disable_virtualization_cpu = x86_svm_disable_virtualization_cpu,
 		.emergency_disable_virtualization_cpu = x86_svm_emergency_disable_virtualization_cpu,
 	};
 
@@ -281,6 +279,41 @@ static __init int x86_svm_init(void)
 static __init int x86_svm_init(void) { return -EOPNOTSUPP; }
 #endif
 
+int x86_virt_get_ref(int feat)
+{
+	int r;
+
+	/* Ensure the !feature check can't get false positives. */
+	BUILD_BUG_ON(!X86_FEATURE_SVM || !X86_FEATURE_VMX);
+
+	if (!virt_ops.feature || virt_ops.feature != feat)
+		return -EOPNOTSUPP;
+
+	guard(preempt)();
+
+	if (this_cpu_inc_return(virtualization_nr_users) > 1)
+		return 0;
+
+	r = virt_ops.enable_virtualization_cpu();
+	if (r)
+		WARN_ON_ONCE(this_cpu_dec_return(virtualization_nr_users));
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_KVM(x86_virt_get_ref);
+
+void x86_virt_put_ref(int feat)
+{
+	guard(preempt)();
+
+	if (WARN_ON_ONCE(!this_cpu_read(virtualization_nr_users)) ||
+	    this_cpu_dec_return(virtualization_nr_users))
+		return;
+
+	BUG_ON(virt_ops.disable_virtualization_cpu() && !virt_rebooting);
+}
+EXPORT_SYMBOL_FOR_KVM(x86_virt_put_ref);
+
 /*
  * Disable virtualization, i.e. VMX or SVM, to ensure INIT is recognized during
  * reboot.  VMX blocks INIT if the CPU is post-VMXON, and SVM blocks INIT if
@@ -288,9 +321,6 @@ static __init int x86_svm_init(void) { return -EOPNOTSUPP; }
  */
 int x86_virt_emergency_disable_virtualization_cpu(void)
 {
-	/* Ensure the !feature check can't get false positives. */
-	BUILD_BUG_ON(!X86_FEATURE_SVM || !X86_FEATURE_VMX);
-
 	if (!virt_ops.feature)
 		return -EOPNOTSUPP;

---

## [11] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 10/16] x86/virt/tdx: Drop the outdated requirement that TDX
 be enabled in IRQ context*

Remove TDX's outdated requirement that per-CPU enabling be done via IPI
function call, which was a stale artifact leftover from early versions of
the TDX enablement series.  The requirement that IRQs be disabled should
have been dropped as part of the revamped series that relied on a the KVM
rework to enable VMX at module load.

In other words, the kernel's "requirement" was never a requirement at all,
but instead a reflection of how KVM enabled VMX (via IPI callback) when
the TDX subsystem code was merged.

Note, accessing per-CPU information is safe even without disabling IRQs,
as tdx_online_cpu() is invoked via a cpuhp callback, i.e. from a per-CPU
thread.

Link: https://lore.kernel.org/all/ZyJOiPQnBz31qLZ7@google.com
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c      | 9 +--------
 arch/x86/virt/vmx/tdx/tdx.c | 4 ----
 2 files changed, 1 insertion(+), 12 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0c790eb0bfa6..582469118b79 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3294,17 +3294,10 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 
 static int tdx_online_cpu(unsigned int cpu)
 {
-	unsigned long flags;
-	int r;
-
 	/* Sanity check CPU is already in post-VMXON */
 	WARN_ON_ONCE(!(cr4_read_shadow() & X86_CR4_VMXE));
 
-	local_irq_save(flags);
-	r = tdx_cpu_enable();
-	local_irq_restore(flags);
-
-	return r;
+	return tdx_cpu_enable();
 }
 
 static int tdx_offline_cpu(unsigned int cpu)
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5ce4ebe99774..dfd82fac0498 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -148,8 +148,6 @@ static int try_init_module_global(void)
  * global initialization SEAMCALL if not done) on local cpu to make this
  * cpu be ready to run any other SEAMCALLs.
  *
- * Always call this function via IPI function calls.
- *
  * Return 0 on success, otherwise errors.
  */
 int tdx_cpu_enable(void)
@@ -160,8 +158,6 @@ int tdx_cpu_enable(void)
 	if (!boot_cpu_has(X86_FEATURE_TDX_HOST_PLATFORM))
 		return -ENODEV;
 
-	lockdep_assert_irqs_disabled();
-
 	if (__this_cpu_read(tdx_lp_initialized))
 		return 0;

---

## [12] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 11/16] KVM: x86/tdx: Do VMXON and TDX-Module initialization
 during subsys init*

Now that VMXON can be done without bouncing through KVM, do TDX-Module
initialization during subsys init (specifically before module_init() so
that it runs before KVM when both are built-in).  Aside from the obvious
benefits of separating core TDX code from KVM, this will allow tagging a
pile of TDX functions and globals as being __init and __ro_after_init.

Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 Documentation/arch/x86/tdx.rst |  36 +------
 arch/x86/include/asm/tdx.h     |   4 -
 arch/x86/kvm/vmx/tdx.c         | 148 ++++++-----------------------
 arch/x86/virt/vmx/tdx/tdx.c    | 168 +++++++++++++++++++--------------
 arch/x86/virt/vmx/tdx/tdx.h    |   8 --
 5 files changed, 130 insertions(+), 234 deletions(-)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 61670e7df2f7..ff6b110291bc 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -60,44 +60,18 @@ Besides initializing the TDX module, a per-cpu initialization SEAMCALL
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
@@ -129,9 +103,9 @@ CPU Hotplug
 ~~~~~~~~~~~
 
 TDX module requires the per-cpu initialization SEAMCALL must be done on
-one cpu before any other SEAMCALLs can be made on that cpu.  The kernel
-provides tdx_cpu_enable() to let the user of TDX to do it when the user
-wants to use a new cpu for TDX task.
+one cpu before any other SEAMCALLs can be made on that cpu.  The kernel,
+via the CPU hotplug framework, performs the necessary initialization when
+a CPU is first brought online.
 
 TDX doesn't support physical (ACPI) CPU hotplug.  During machine boot,
 TDX verifies all boot-time present logical CPUs are TDX compatible before
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
index 582469118b79..0ac01c119336 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -59,7 +59,7 @@ module_param_named(tdx, enable_tdx, bool, 0444);
 #define TDX_SHARED_BIT_PWL_5 gpa_to_gfn(BIT_ULL(51))
 #define TDX_SHARED_BIT_PWL_4 gpa_to_gfn(BIT_ULL(47))
 
-static enum cpuhp_state tdx_cpuhp_state;
+static enum cpuhp_state tdx_cpuhp_state __ro_after_init;
 
 static const struct tdx_sys_info *tdx_sysinfo;
 
@@ -3294,10 +3294,7 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 
 static int tdx_online_cpu(unsigned int cpu)
 {
-	/* Sanity check CPU is already in post-VMXON */
-	WARN_ON_ONCE(!(cr4_read_shadow() & X86_CR4_VMXE));
-
-	return tdx_cpu_enable();
+	return 0;
 }
 
 static int tdx_offline_cpu(unsigned int cpu)
@@ -3336,51 +3333,6 @@ static int tdx_offline_cpu(unsigned int cpu)
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
@@ -3400,34 +3352,18 @@ static int __init __tdx_bringup(void)
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
+		return -ENODEV;
 
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
@@ -3462,34 +3398,31 @@ static int __init __tdx_bringup(void)
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
@@ -3521,39 +3454,11 @@ int __init tdx_bringup(void)
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
 	if (r) {
 		/*
@@ -3568,8 +3473,6 @@ int __init tdx_bringup(void)
 		 */
 		if (r == -ENODEV)
 			goto success_disable_tdx;
-
-		enable_tdx = 0;
 	}
 
 	return r;
@@ -3579,6 +3482,15 @@ int __init tdx_bringup(void)
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
index dfd82fac0498..feea8dd6920d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -28,6 +28,7 @@
 #include <linux/log2.h>
 #include <linux/acpi.h>
 #include <linux/suspend.h>
+#include <linux/syscore_ops.h>
 #include <linux/idr.h>
 #include <linux/kvm_types.h>
 #include <asm/page.h>
@@ -39,6 +40,7 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+#include <asm/virt.h>
 #include "tdx.h"
 
 static u32 tdx_global_keyid __ro_after_init;
@@ -51,13 +53,11 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
-static enum tdx_module_status_t tdx_module_status;
-static DEFINE_MUTEX(tdx_module_lock);
-
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo;
+static bool tdx_module_initialized;
 
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
@@ -142,22 +142,15 @@ static int try_init_module_global(void)
 }
 
 /**
- * tdx_cpu_enable - Enable TDX on local cpu
- *
- * Do one-time TDX module per-cpu initialization SEAMCALL (and TDX module
- * global initialization SEAMCALL if not done) on local cpu to make this
- * cpu be ready to run any other SEAMCALLs.
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
 	if (__this_cpu_read(tdx_lp_initialized))
 		return 0;
 
@@ -178,7 +171,58 @@ int tdx_cpu_enable(void)
 
 	return 0;
 }
-EXPORT_SYMBOL_FOR_KVM(tdx_cpu_enable);
+
+static int tdx_online_cpu(unsigned int cpu)
+{
+	int ret;
+
+	ret = x86_virt_get_ref(X86_FEATURE_VMX);
+	if (ret)
+		return ret;
+
+	ret = tdx_cpu_enable();
+	if (ret)
+		x86_virt_put_ref(X86_FEATURE_VMX);
+
+	return ret;
+}
+
+static int tdx_offline_cpu(unsigned int cpu)
+{
+	x86_virt_put_ref(X86_FEATURE_VMX);
+	return 0;
+}
+
+static void tdx_shutdown_cpu(void *ign)
+{
+	x86_virt_put_ref(X86_FEATURE_VMX);
+}
+
+static void tdx_shutdown(void *ign)
+{
+	on_each_cpu(tdx_shutdown_cpu, NULL, 1);
+}
+
+static int tdx_suspend(void *ign)
+{
+	x86_virt_put_ref(X86_FEATURE_VMX);
+	return 0;
+}
+
+static void tdx_resume(void *ign)
+{
+	WARN_ON_ONCE(x86_virt_get_ref(X86_FEATURE_VMX));
+}
+
+static const struct syscore_ops tdx_syscore_ops = {
+	.suspend = tdx_suspend,
+	.resume = tdx_resume,
+	.shutdown = tdx_shutdown,
+};
+
+static struct syscore tdx_syscore = {
+	.ops = &tdx_syscore_ops,
+};
 
 /*
  * Add a memory region as a TDX memory block.  The caller must make sure
@@ -1153,67 +1197,50 @@ static int init_tdx_module(void)
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
+	register_syscore(&tdx_syscore);
 
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
-EXPORT_SYMBOL_FOR_KVM(tdx_enable);
+subsys_initcall(tdx_enable);
 
 static bool is_pamt_page(unsigned long phys)
 {
@@ -1464,15 +1491,10 @@ void __init tdx_init(void)
 
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
 EXPORT_SYMBOL_FOR_KVM(tdx_get_sysinfo);
 
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

## [13] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 12/16] x86/virt/tdx: Tag a pile of functions as __init, and
 globals as __ro_after_init*

Now that TDX-Module initialization is done during subsys init, tag all
related functions as __init, and relevant data as __ro_after_init.

Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c                 | 119 ++++++++++----------
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  10 +-
 2 files changed, 66 insertions(+), 63 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index feea8dd6920d..05d634caa4e8 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -56,8 +56,8 @@ static struct tdmr_info_list tdx_tdmr_list;
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
-static struct tdx_sys_info tdx_sysinfo;
-static bool tdx_module_initialized;
+static struct tdx_sys_info tdx_sysinfo __ro_after_init;
+static bool tdx_module_initialized __ro_after_init;
 
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
@@ -229,8 +229,9 @@ static struct syscore tdx_syscore = {
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
 
@@ -248,7 +249,7 @@ static int add_tdx_memblock(struct list_head *tmb_list, unsigned long start_pfn,
 	return 0;
 }
 
-static void free_tdx_memlist(struct list_head *tmb_list)
+static __init void free_tdx_memlist(struct list_head *tmb_list)
 {
 	/* @tmb_list is protected by mem_hotplug_lock */
 	while (!list_empty(tmb_list)) {
@@ -266,7 +267,7 @@ static void free_tdx_memlist(struct list_head *tmb_list)
  * ranges off in a secondary structure because memblock is modified
  * in memory hotplug while TDX memory regions are fixed.
  */
-static int build_tdx_memlist(struct list_head *tmb_list)
+static __init int build_tdx_memlist(struct list_head *tmb_list)
 {
 	unsigned long start_pfn, end_pfn;
 	int i, nid, ret;
@@ -298,7 +299,7 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
-static int read_sys_metadata_field(u64 field_id, u64 *data)
+static __init int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
 	int ret;
@@ -320,7 +321,7 @@ static int read_sys_metadata_field(u64 field_id, u64 *data)
 
 #include "tdx_global_metadata.c"
 
-static int check_features(struct tdx_sys_info *sysinfo)
+static __init int check_features(struct tdx_sys_info *sysinfo)
 {
 	u64 tdx_features0 = sysinfo->features.tdx_features0;
 
@@ -333,7 +334,7 @@ static int check_features(struct tdx_sys_info *sysinfo)
 }
 
 /* Calculate the actual TDMR size */
-static int tdmr_size_single(u16 max_reserved_per_tdmr)
+static __init int tdmr_size_single(u16 max_reserved_per_tdmr)
 {
 	int tdmr_sz;
 
@@ -347,8 +348,8 @@ static int tdmr_size_single(u16 max_reserved_per_tdmr)
 	return ALIGN(tdmr_sz, TDMR_INFO_ALIGNMENT);
 }
 
-static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
-			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
+static __init int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
+				  struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	size_t tdmr_sz, tdmr_array_sz;
 	void *tdmr_array;
@@ -379,7 +380,7 @@ static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
 	return 0;
 }
 
-static void free_tdmr_list(struct tdmr_info_list *tdmr_list)
+static __init void free_tdmr_list(struct tdmr_info_list *tdmr_list)
 {
 	free_pages_exact(tdmr_list->tdmrs,
 			tdmr_list->max_tdmrs * tdmr_list->tdmr_sz);
@@ -408,8 +409,8 @@ static inline u64 tdmr_end(struct tdmr_info *tdmr)
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
@@ -485,8 +486,8 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
  */
-static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-				      u16 pamt_entry_size)
+static __init unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
+					     u16 pamt_entry_size)
 {
 	unsigned long pamt_sz, nr_pamt_entries;
 
@@ -517,7 +518,7 @@ static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
  * PAMT.  This node will have some memory covered by the TDMR.  The
  * relative amount of memory covered is not considered.
  */
-static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
+static __init int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
 {
 	struct tdx_memblock *tmb;
 
@@ -546,9 +547,9 @@ static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
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
@@ -618,7 +619,7 @@ static void tdmr_get_pamt(struct tdmr_info *tdmr, unsigned long *pamt_base,
 	*pamt_size = pamt_sz;
 }
 
-static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
+static __init void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 		void (*pamt_func)(unsigned long base, unsigned long size))
 {
 	unsigned long pamt_base, pamt_size;
@@ -635,17 +636,17 @@ static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 	pamt_func(pamt_base, pamt_size);
 }
 
-static void free_pamt(unsigned long pamt_base, unsigned long pamt_size)
+static __init void free_pamt(unsigned long pamt_base, unsigned long pamt_size)
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
 
@@ -654,9 +655,9 @@ static void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
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
 
@@ -705,12 +706,13 @@ void tdx_quirk_reset_page(struct page *page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_quirk_reset_page);
 
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
 
@@ -718,7 +720,7 @@ static void tdmrs_quirk_reset_pamt_all(struct tdmr_info_list *tdmr_list)
 		tdmr_quirk_reset_pamt(tdmr_entry(tdmr_list, i));
 }
 
-static unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
+static __init unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
 {
 	unsigned long pamt_size = 0;
 	int i;
@@ -733,8 +735,8 @@ static unsigned long tdmrs_count_pamt_kb(struct tdmr_info_list *tdmr_list)
 	return pamt_size / 1024;
 }
 
-static int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx, u64 addr,
-			      u64 size, u16 max_reserved_per_tdmr)
+static __init int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx,
+				     u64 addr, u64 size, u16 max_reserved_per_tdmr)
 {
 	struct tdmr_reserved_area *rsvd_areas = tdmr->reserved_areas;
 	int idx = *p_idx;
@@ -767,10 +769,10 @@ static int tdmr_add_rsvd_area(struct tdmr_info *tdmr, int *p_idx, u64 addr,
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
@@ -831,10 +833,10 @@ static int tdmr_populate_rsvd_holes(struct list_head *tmb_list,
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
 
@@ -869,7 +871,7 @@ static int tdmr_populate_rsvd_pamts(struct tdmr_info_list *tdmr_list,
 }
 
 /* Compare function called by sort() for TDMR reserved areas */
-static int rsvd_area_cmp_func(const void *a, const void *b)
+static __init int rsvd_area_cmp_func(const void *a, const void *b)
 {
 	struct tdmr_reserved_area *r1 = (struct tdmr_reserved_area *)a;
 	struct tdmr_reserved_area *r2 = (struct tdmr_reserved_area *)b;
@@ -888,10 +890,10 @@ static int rsvd_area_cmp_func(const void *a, const void *b)
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
 
@@ -916,9 +918,9 @@ static int tdmr_populate_rsvd_areas(struct tdmr_info *tdmr,
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
 
@@ -939,9 +941,9 @@ static int tdmrs_populate_rsvd_areas_all(struct tdmr_info_list *tdmr_list,
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
@@ -973,7 +975,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
-static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
+static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
+				    u64 global_keyid)
 {
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
@@ -1008,7 +1011,7 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 	return ret;
 }
 
-static int do_global_key_config(void *unused)
+static __init int do_global_key_config(void *unused)
 {
 	struct tdx_module_args args = {};
 
@@ -1026,7 +1029,7 @@ static int do_global_key_config(void *unused)
  * KVM) can ensure success by ensuring sufficient CPUs are online and
  * can run SEAMCALLs.
  */
-static int config_global_keyid(void)
+static __init int config_global_keyid(void)
 {
 	cpumask_var_t packages;
 	int cpu, ret = -EINVAL;
@@ -1066,7 +1069,7 @@ static int config_global_keyid(void)
 	return ret;
 }
 
-static int init_tdmr(struct tdmr_info *tdmr)
+static __init int init_tdmr(struct tdmr_info *tdmr)
 {
 	u64 next;
 
@@ -1097,7 +1100,7 @@ static int init_tdmr(struct tdmr_info *tdmr)
 	return 0;
 }
 
-static int init_tdmrs(struct tdmr_info_list *tdmr_list)
+static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 {
 	int i;
 
@@ -1116,7 +1119,7 @@ static int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
-static int init_tdx_module(void)
+static __init int init_tdx_module(void)
 {
 	int ret;
 
@@ -1197,7 +1200,7 @@ static int init_tdx_module(void)
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

## [14] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 13/16] x86/virt/tdx: KVM: Consolidate TDX CPU hotplug handling*

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

Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c      | 67 +------------------------------------
 arch/x86/virt/vmx/tdx/tdx.c | 49 +++++++++++++++++++++++++--
 2 files changed, 47 insertions(+), 69 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0ac01c119336..fea3dfc7ac8b 100644
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
@@ -3292,51 +3285,10 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
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
@@ -3404,23 +3356,7 @@ static int __init __tdx_bringup(void)
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
@@ -3488,7 +3424,6 @@ void tdx_cleanup(void)
 		return;
 
 	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
-	cpuhp_remove_state(tdx_cpuhp_state);
 }
 
 void __init tdx_hardware_setup(void)
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 05d634caa4e8..ddbab87d2467 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -59,6 +59,8 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
+static atomic_t nr_configured_hkid;
+
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
@@ -189,6 +191,40 @@ static int tdx_online_cpu(unsigned int cpu)
 
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
 	x86_virt_put_ref(X86_FEATURE_VMX);
 	return 0;
 }
@@ -1509,15 +1545,22 @@ EXPORT_SYMBOL_FOR_KVM(tdx_get_nr_guest_keyids);
 
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
 EXPORT_SYMBOL_FOR_KVM(tdx_guest_keyid_alloc);
 
 void tdx_guest_keyid_free(unsigned int keyid)
 {
 	ida_free(&tdx_guest_keyid_pool, keyid);
+	atomic_dec(&nr_configured_hkid);
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_guest_keyid_free);

---

## [15] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 14/16] x86/virt/tdx: Use ida_is_empty() to detect if any
 TDs may be running*

Drop nr_configured_hkid and instead use ida_is_empty() to detect if any
HKIDs have been allocated/configured.

Suggested-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 17 ++++-------------
 1 file changed, 4 insertions(+), 13 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ddbab87d2467..bdee937b84d4 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -59,8 +59,6 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
-static atomic_t nr_configured_hkid;
-
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
@@ -194,7 +192,7 @@ static int tdx_offline_cpu(unsigned int cpu)
 	int i;
 
 	/* No TD is running.  Allow any cpu to be offline. */
-	if (!atomic_read(&nr_configured_hkid))
+	if (ida_is_empty(&tdx_guest_keyid_pool))
 		goto done;
 
 	/*
@@ -1545,22 +1543,15 @@ EXPORT_SYMBOL_FOR_KVM(tdx_get_nr_guest_keyids);
 
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
 EXPORT_SYMBOL_FOR_KVM(tdx_guest_keyid_alloc);
 
 void tdx_guest_keyid_free(unsigned int keyid)
 {
 	ida_free(&tdx_guest_keyid_pool, keyid);
-	atomic_dec(&nr_configured_hkid);
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_guest_keyid_free);

---

## [16] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 15/16] KVM: Bury kvm_{en,dis}able_virtualization() in
 kvm_main.c once more*

Now that TDX handles doing VMXON without KVM's involvement, bury the
top-level APIs to enable and disable virtualization back in kvm_main.c.

No functional change intended.

Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 include/linux/kvm_host.h |  8 --------
 virt/kvm/kvm_main.c      | 17 +++++++++++++----
 2 files changed, 13 insertions(+), 12 deletions(-)

diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 981b55c0a3a7..760e0ec2c8eb 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2605,12 +2605,4 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
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
index e081e7244299..737b74b15bb5 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -1112,6 +1112,9 @@ static inline struct kvm_io_bus *kvm_get_bus_for_destruction(struct kvm *kvm,
 					 !refcount_read(&kvm->users_count));
 }
 
+static int kvm_enable_virtualization(void);
+static void kvm_disable_virtualization(void);
+
 static struct kvm *kvm_create_vm(unsigned long type, const char *fdname)
 {
 	struct kvm *kvm = kvm_arch_alloc_vm();
@@ -5704,7 +5707,7 @@ static struct syscore kvm_syscore = {
 	.ops = &kvm_syscore_ops,
 };
 
-int kvm_enable_virtualization(void)
+static int kvm_enable_virtualization(void)
 {
 	int r;
 
@@ -5749,9 +5752,8 @@ int kvm_enable_virtualization(void)
 	--kvm_usage_count;
 	return r;
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_enable_virtualization);
 
-void kvm_disable_virtualization(void)
+static void kvm_disable_virtualization(void)
 {
 	guard(mutex)(&kvm_usage_lock);
 
@@ -5762,7 +5764,6 @@ void kvm_disable_virtualization(void)
 	cpuhp_remove_state(CPUHP_AP_KVM_ONLINE);
 	kvm_arch_disable_virtualization();
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_disable_virtualization);
 
 static int kvm_init_virtualization(void)
 {
@@ -5778,6 +5779,14 @@ static void kvm_uninit_virtualization(void)
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

## [17] Sean Christopherson — 2026-02-13
*Subject: [PATCH v3 16/16] KVM: TDX: Fold tdx_bringup() into tdx_hardware_setup()*

Now that TDX doesn't need to manually enable virtualization through _KVM_
APIs during setup, fold tdx_bringup() into tdx_hardware_setup() where the
code belongs, e.g. so that KVM doesn't leave the S-EPT kvm_x86_ops wired
up when TDX is disabled.

The weird ordering (and naming) was necessary to allow KVM TDX to use
kvm_enable_virtualization(), which in turn had a hard dependency on
kvm_x86_ops.enable_virtualization_cpu and thus kvm_x86_vendor_init().

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/main.c | 19 ++++++++-----------
 arch/x86/kvm/vmx/tdx.c  | 39 +++++++++++++++------------------------
 arch/x86/kvm/vmx/tdx.h  |  8 ++------
 3 files changed, 25 insertions(+), 41 deletions(-)

diff --git a/arch/x86/kvm/vmx/main.c b/arch/x86/kvm/vmx/main.c
index a46ccd670785..dbebddf648be 100644
--- a/arch/x86/kvm/vmx/main.c
+++ b/arch/x86/kvm/vmx/main.c
@@ -29,10 +29,15 @@ static __init int vt_hardware_setup(void)
 	if (ret)
 		return ret;
 
+	return enable_tdx ? tdx_hardware_setup() : 0;
+}
+
+static void vt_hardware_unsetup(void)
+{
 	if (enable_tdx)
-		tdx_hardware_setup();
+		tdx_hardware_unsetup();
 
-	return 0;
+	vmx_hardware_unsetup();
 }
 
 static int vt_vm_init(struct kvm *kvm)
@@ -869,7 +874,7 @@ struct kvm_x86_ops vt_x86_ops __initdata = {
 
 	.check_processor_compatibility = vmx_check_processor_compat,
 
-	.hardware_unsetup = vmx_hardware_unsetup,
+	.hardware_unsetup = vt_op(hardware_unsetup),
 
 	.enable_virtualization_cpu = vmx_enable_virtualization_cpu,
 	.disable_virtualization_cpu = vt_op(disable_virtualization_cpu),
@@ -1029,7 +1034,6 @@ struct kvm_x86_init_ops vt_init_ops __initdata = {
 static void __exit vt_exit(void)
 {
 	kvm_exit();
-	tdx_cleanup();
 	vmx_exit();
 }
 module_exit(vt_exit);
@@ -1043,11 +1047,6 @@ static int __init vt_init(void)
 	if (r)
 		return r;
 
-	/* tdx_init() has been taken */
-	r = tdx_bringup();
-	if (r)
-		goto err_tdx_bringup;
-
 	/*
 	 * TDX and VMX have different vCPU structures.  Calculate the
 	 * maximum size/align so that kvm_init() can use the larger
@@ -1074,8 +1073,6 @@ static int __init vt_init(void)
 	return 0;
 
 err_kvm_init:
-	tdx_cleanup();
-err_tdx_bringup:
 	vmx_exit();
 	return r;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index fea3dfc7ac8b..d354022ba9c9 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3285,7 +3285,12 @@ int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 	return PG_LEVEL_4K;
 }
 
-static int __init __tdx_bringup(void)
+void tdx_hardware_unsetup(void)
+{
+	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
+}
+
+static int __init __tdx_hardware_setup(void)
 {
 	const struct tdx_sys_info_td_conf *td_conf;
 	int i;
@@ -3359,7 +3364,7 @@ static int __init __tdx_bringup(void)
 	return 0;
 }
 
-int __init tdx_bringup(void)
+int __init tdx_hardware_setup(void)
 {
 	int r, i;
 
@@ -3395,7 +3400,7 @@ int __init tdx_bringup(void)
 		goto success_disable_tdx;
 	}
 
-	r = __tdx_bringup();
+	r = __tdx_hardware_setup();
 	if (r) {
 		/*
 		 * Disable TDX only but don't fail to load module if the TDX
@@ -3409,31 +3414,12 @@ int __init tdx_bringup(void)
 		 */
 		if (r == -ENODEV)
 			goto success_disable_tdx;
+
+		return r;
 	}
 
-	return r;
-
-success_disable_tdx:
-	enable_tdx = 0;
-	return 0;
-}
-
-void tdx_cleanup(void)
-{
-	if (!enable_tdx)
-		return;
-
-	misc_cg_set_capacity(MISC_CG_RES_TDX, 0);
-}
-
-void __init tdx_hardware_setup(void)
-{
 	KVM_SANITY_CHECK_VM_STRUCT_SIZE(kvm_tdx);
 
-	/*
-	 * Note, if the TDX module can't be loaded, KVM TDX support will be
-	 * disabled but KVM will continue loading (see tdx_bringup()).
-	 */
 	vt_x86_ops.vm_size = max_t(unsigned int, vt_x86_ops.vm_size, sizeof(struct kvm_tdx));
 
 	vt_x86_ops.link_external_spt = tdx_sept_link_private_spt;
@@ -3441,4 +3427,9 @@ void __init tdx_hardware_setup(void)
 	vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
 	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;
 	vt_x86_ops.protected_apic_has_interrupt = tdx_protected_apic_has_interrupt;
+	return 0;
+
+success_disable_tdx:
+	enable_tdx = 0;
+	return 0;
 }
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index 45b5183ccb36..b5cd2ffb303e 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -8,9 +8,8 @@
 #ifdef CONFIG_KVM_INTEL_TDX
 #include "common.h"
 
-void tdx_hardware_setup(void);
-int tdx_bringup(void);
-void tdx_cleanup(void);
+int tdx_hardware_setup(void);
+void tdx_hardware_unsetup(void);
 
 extern bool enable_tdx;
 
@@ -187,9 +186,6 @@ TDX_BUILD_TDVPS_ACCESSORS(8, MANAGEMENT, management);
 TDX_BUILD_TDVPS_ACCESSORS(64, STATE_NON_ARCH, state_non_arch);
 
 #else
-static inline int tdx_bringup(void) { return 0; }
-static inline void tdx_cleanup(void) {}
-
 #define enable_tdx	0
 
 struct kvm_tdx {

---

## [18] dan.j.williams@intel.com — 2026-02-16
*Subject: Re: [PATCH v3 05/16] x86/virt: Force-clear X86_FEATURE_VMX if
 configuring root VMCS fails*

Sean Christopherson wrote:
> If allocating and configuring a root VMCS fails, clear X86_FEATURE_VMX in
> all CPUs so that KVM doesn't need to manually check root_vmcs.  As added
[..]
> diff --git a/arch/x86/virt/hw.c b/arch/x86/virt/hw.c
> index 56972f594d90..40495872fdfb 100644
[..]
> @@ -56,7 +56,7 @@ static __init int x86_vmx_init(void)
>  		struct vmcs *vmcs;

Is the warn_alloc() deep in this path not sufficient? Either way, this
patch looks good to me.

---

## [19] dan.j.williams@intel.com — 2026-02-16
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

Sean Christopherson wrote:
> Assuming I didn't break anything between v2 and v3, I think this is ready to
> rip.  Given the scope of the KVM changes, and that they extend outside of x86,

I went through the rest of the patches, the finer grained splits make
sense. No significant concerns, so for the series:

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

...I expect Chao or Yilun to have a chance to offer a Tested-by per your
comment above.

---

## [20] Huang, Kai — 2026-02-17
*Subject: Re: [PATCH v3 10/16] x86/virt/tdx: Drop the outdated requirement that
 TDX be enabled in IRQ context*

On Fri, 2026-02-13 at 17:26 -0800, Sean Christopherson wrote:
> Remove TDX's outdated requirement that per-CPU enabling be done via IPI
> function call, which was a stale artifact leftover from early versions of

Hi Sean,

The first call of tdx_cpu_enable() will also call into
try_init_module_global() (in order to do TDH_SYS_INIT), which also has a
lockdep_assert_irqs_disabled() + a raw spinlock to make sure TDH_SYS_INIT is
only called once when tdx_cpu_enable() are called from IRQ disabled context.

This patch only changes tdx_cpu_enable() but doesn't change
try_init_module_global(), thus the first call of tdx_cpu_enable() will still
trigger the lockdep_assert_irqs_disabled() failure warning.

I've tried this series on my local and I did see such WARNING during
boot[*].  We need to fix that too.

But hmm, Chao's "Runtime TDX module update" series actually needs to call
tdx_cpu_enable() when IRQ disabled, IIUC, since it is called via
stop_machine_cpuslocked():

https://lore.kernel.org/kvm/20260212143606.534586-18-chao.gao@intel.com/

Maybe we can just keep tdx_cpu_enabled() as-is?

[*] lockdep WARNING():

[    7.755642] ------------[ cut here ]------------
[    7.756639] __lockdep_enabled && this_cpu_read(hardirqs_enabled)
[    7.756642] WARNING: arch/x86/virt/vmx/tdx/tdx.c:119 at
try_init_module_global+0x189/0x1c0, CPU#0: cpuhp/0/21

---

## [21] Sean Christopherson — 2026-02-17
*Subject: Re: [PATCH v3 10/16] x86/virt/tdx: Drop the outdated requirement that
 TDX be enabled in IRQ context*

On Tue, Feb 17, 2026, Kai Huang wrote:
> On Fri, 2026-02-13 at 17:26 -0800, Sean Christopherson wrote:
> > Remove TDX's outdated requirement that per-CPU enabling be done via IPI

Can't we simply delete the lockdep assert there as well?  It should be totally
fine to have a function that can be called from task or IRQ context, so long as
the function is prepared for that possibility.  I.e. just because it _can_ be
called from IRQ context doesn't mean it _must_ be called from IRQ context.

E.g. as a fixup

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index bdee937b84d4..f8f5e046159b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -106,8 +106,7 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 
 /*
  * Do the module global initialization once and return its result.
- * It can be done on any cpu.  It's always called with interrupts
- * disabled.
+ * It can be done on any cpu, and from task or IRQ context.
  */
 static int try_init_module_global(void)
 {
@@ -116,8 +115,6 @@ static int try_init_module_global(void)
        static bool sysinit_done;
        static int sysinit_ret;
 
-       lockdep_assert_irqs_disabled();
-
        raw_spin_lock(&sysinit_lock);
 
        if (sysinit_done)

---

## [22] Sean Christopherson — 2026-02-17
*Subject: Re: [PATCH v3 05/16] x86/virt: Force-clear X86_FEATURE_VMX if
 configuring root VMCS fails*

On Mon, Feb 16, 2026, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> > If allocating and configuring a root VMCS fails, clear X86_FEATURE_VMX in

Not sure, I don't have much experience with warn_alloc() in practice.  Reading
the code, my initial reaction is that I don't want to rely on warn_alloc() since
it's ratelimited.  Multiple allocation failures during boot seems unlikely, but
at the same time, the cost of the WARN_ON_ONCE() here is really just the handful
of bytes for the bug_table entry.

---

## [23] Huang, Kai — 2026-02-17
*Subject: Re: [PATCH v3 10/16] x86/virt/tdx: Drop the outdated requirement that
 TDX be enabled in IRQ context*

On Tue, 2026-02-17 at 07:25 -0800, Sean Christopherson wrote:
> On Tue, Feb 17, 2026, Kai Huang wrote:
> > On Fri, 2026-02-13 at 17:26 -0800, Sean Christopherson wrote:

Yeah we can.  LGTM.

---

## [24] Chao Gao — 2026-02-25
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

On Fri, Feb 13, 2026 at 05:26:46PM -0800, Sean Christopherson wrote:
>Assuming I didn't break anything between v2 and v3, I think this is ready to
>rip.  Given the scope of the KVM changes, and that they extend outside of x86,

I tested CPU hotplug/unplug, kvm-intel.ko loading/reloading, TD launches, and
loading kvm-intel.ko with tdx=1 when the TDX Module wasn't loaded. No issues
were found with this v3.

Tested-by: Chao Gao <chao.gao@intel.com>

---

## [25] Chao Gao — 2026-02-26
*Subject: Re: [PATCH v3 07/16] KVM: SVM: Move core EFER.SVME enablement to
 kernel*

>-static inline void kvm_cpu_svm_disable(void)
>-{

There's a functional change here. The new x86_svm_disable_virtualization_cpu()
doesn't reset MSR_VM_HSAVE_PA, but the old kvm_cpu_svm_disable() does.


>+int x86_svm_disable_virtualization_cpu(void)
>+{

---

## [26] Chao Gao — 2026-02-26
*Subject: Re: [PATCH v3 08/16] KVM: x86: Move bulk of emergency virtualizaton
 logic to virt subsystem*

On Fri, Feb 13, 2026 at 05:26:54PM -0800, Sean Christopherson wrote:
>Move the majority of the code related to disabling hardware virtualization
>in emergency from KVM into the virt subsystem so that virt can take full

							     ^^^ and

>-void cpu_emergency_disable_virtualization(void)
>-{

...

>+static void x86_virt_invoke_kvm_emergency_callback(void)
>+{

The RCU lock is dropped here. I assume this is intentional since the function
is only called with IRQs disabled, in which case the RCU lock isn't needed.

<snip>

>+int x86_virt_emergency_disable_virtualization_cpu(void)
>+{

The comment is stale. Since this patch just moves the comment, it should be
fine to keep it as-is and fix it in a separate series.

>+	lockdep_assert_irqs_disabled();
>+

			^^^^^^^ Refuse

LGTM aside from the two typos above.

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [27] Dave Hansen — 2026-02-26
*Subject: Re: [PATCH v3 06/16] KVM: VMX: Move core VMXON enablement to kernel*

On 2/13/26 17:26, Sean Christopherson wrote:
> Move the innermost VMXON+VMXOFF logic out of KVM and into to core x86 so
> that TDX can (eventually) force VMXON without having to rely on KVM being

For the x86 side:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

I'm also very much OK with this going through the KVM tree.

---

## [28] Dave Hansen — 2026-02-26
*Subject: Re: [PATCH v3 11/16] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during subsys init*

On 2/13/26 17:26, Sean Christopherson wrote:
> Now that VMXON can be done without bouncing through KVM, do TDX-Module
> initialization during subsys init (specifically before module_init() so
...
>  Documentation/arch/x86/tdx.rst |  36 +------
>  arch/x86/include/asm/tdx.h     |   4 -

It's hard to argue with a diffstat like that.

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [29] Sean Christopherson — 2026-02-26
*Subject: Re: [PATCH v3 07/16] KVM: SVM: Move core EFER.SVME enablement to kernel*

On Thu, Feb 26, 2026, Chao Gao wrote:
> >-static inline void kvm_cpu_svm_disable(void)
> >-{

Doh.  I'll squash this as fixup, assuming there are no other goofs:

diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 5f033bf3ba83..fc08450cb4b7 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -490,6 +490,7 @@ static void svm_disable_virtualization_cpu(void)
                __svm_write_tsc_multiplier(SVM_TSC_RATIO_DEFAULT);
 
        x86_svm_disable_virtualization_cpu();
+       wrmsrq(MSR_VM_HSAVE_PA, 0);
 
        amd_pmu_disable_virt();
 }

Very nice catch!

P.S. This reminded me that there's a lurking wart with __sev_snp_init_locked()
where it forces MSR_VM_HSAVE_PA to '0' on all CPUs.  That's firmly a "hypervisor"
thing so it doesn't really fit here (and code wise it's also kludgy), just thought
I'd mention it in case someone has a brilliant idea and/or runs into problems with
it.  IIRC, we ran into a problem where __sev_snp_init_locked() clobbered KVM's
value, but I think the underlying problem was effectively fixed by commit
6f1d5a3513c2 ("KVM: SVM: Add support to initialize SEV/SNP functionality in KVM").

---

## [30] Chao Gao — 2026-02-27
*Subject: Re: [PATCH v3 09/16] x86/virt: Add refcounting of VMX/SVM usage to
 support multiple in-kernel users*

On Fri, Feb 13, 2026 at 05:26:55PM -0800, Sean Christopherson wrote:
>Implement a per-CPU refcounting scheme so that "users" of hardware
>virtualization, e.g. KVM and the future TDX code, can co-exist without

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [31] Chao Gao — 2026-02-27
*Subject: Re: [PATCH v3 11/16] KVM: x86/tdx: Do VMXON and TDX-Module
 initialization during subsys init*

On Fri, Feb 13, 2026 at 05:26:57PM -0800, Sean Christopherson wrote:
>Now that VMXON can be done without bouncing through KVM, do TDX-Module
>initialization during subsys init (specifically before module_init() so

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [32] Sagi Shahar — 2026-03-03
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during bringup*

On Fri, Feb 13, 2026 at 7:27 PM Sean Christopherson <seanjc@google.com> wrote:
>
> Assuming I didn't break anything between v2 and v3, I think this is ready to

Tested running TDs and TDX module update using "Runtime TDX Module
update support" patches [1]
Tested-by: Sagi Shahar <sagishah@gmail.com>

[1] https://lore.kernel.org/lkml/20260123145645.90444-1-chao.gao@intel.com/

---

## [33] Sagi Shahar — 2026-03-03
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during bringup*

On Tue, Mar 3, 2026 at 3:39 PM Sagi Shahar <sagis@google.com> wrote:
>
> On Fri, Feb 13, 2026 at 7:27 PM Sean Christopherson <seanjc@google.com> wrote:

Actually, looking at the "Runtime TDX Module update support" patches I
don't think I ran those with this version of the patches since the
"tdx_module_status" changes are incompatible. So it was just the
patches in this patchset.

---

## [34] Sean Christopherson — 2026-03-05
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during bringup*

On Fri, 13 Feb 2026 17:26:46 -0800, Sean Christopherson wrote:
> Assuming I didn't break anything between v2 and v3, I think this is ready to
> rip.  Given the scope of the KVM changes, and that they extend outside of x86,

Applied to kvm-x86 vmxon, with the minor fixups.  I'll make sure not to touch
the hashes at this point, but holler if anyone wants an "official" stable tag.

[01/16] KVM: x86: Move kvm_rebooting to x86
        https://github.com/kvm-x86/linux/commit/4059172b2a78
[02/16] KVM: VMX: Move architectural "vmcs" and "vmcs_hdr" structures to public vmx.h
        https://github.com/kvm-x86/linux/commit/3c75e6a5da3c
[03/16] KVM: x86: Move "kvm_rebooting" to kernel as "virt_rebooting"
        https://github.com/kvm-x86/linux/commit/a1450a8156c6
[04/16] KVM: VMX: Unconditionally allocate root VMCSes during boot CPU bringup
        https://github.com/kvm-x86/linux/commit/405b7c27934e
[05/16] x86/virt: Force-clear X86_FEATURE_VMX if configuring root VMCS fails
        https://github.com/kvm-x86/linux/commit/95e4adb24ff6
[06/16] KVM: VMX: Move core VMXON enablement to kernel
        https://github.com/kvm-x86/linux/commit/920da4f75519
[07/16] KVM: SVM: Move core EFER.SVME enablement to kernel
        https://github.com/kvm-x86/linux/commit/32d76cdfa122
[08/16] KVM: x86: Move bulk of emergency virtualizaton logic to virt subsystem
        https://github.com/kvm-x86/linux/commit/428afac5a8ea
[09/16] x86/virt: Add refcounting of VMX/SVM usage to support multiple in-kernel users
        https://github.com/kvm-x86/linux/commit/8528a7f9c91d
[10/16] x86/virt/tdx: Drop the outdated requirement that TDX be enabled in IRQ context
        https://github.com/kvm-x86/linux/commit/0efe5dc16169
[11/16] KVM: x86/tdx: Do VMXON and TDX-Module initialization during subsys init
        https://github.com/kvm-x86/linux/commit/165e77353831
[12/16] x86/virt/tdx: Tag a pile of functions as __init, and globals as __ro_after_init
        https://github.com/kvm-x86/linux/commit/9900400e20c0
[13/16] x86/virt/tdx: KVM: Consolidate TDX CPU hotplug handling
        https://github.com/kvm-x86/linux/commit/eac90a5ba0aa
[14/16] x86/virt/tdx: Use ida_is_empty() to detect if any TDs may be running
        https://github.com/kvm-x86/linux/commit/afe31de159bf
[15/16] KVM: Bury kvm_{en,dis}able_virtualization() in kvm_main.c once more
        https://github.com/kvm-x86/linux/commit/d30372d0b7e6
[16/16] KVM: TDX: Fold tdx_bringup() into tdx_hardware_setup()
        https://github.com/kvm-x86/linux/commit/f630de1f8d70

--
https://github.com/kvm-x86/linux/tree/next

---

## [35] dan.j.williams@intel.com — 2026-03-05
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

Sean Christopherson wrote:
> On Fri, 13 Feb 2026 17:26:46 -0800, Sean Christopherson wrote:
> > Assuming I didn't break anything between v2 and v3, I think this is ready to

Thanks, Sean!

Please do make an official stable tag that I can use for coordinating
the initial TDX Connect enabling series. While there is no strict
dependency I do not want it to be the case that a bisect of TDX Connect
bounces between a world where you need to load kvm_intel before the PCI
layer can do link encryption operations and keep it loaded etc.

My proposal, unless you or Dave holler, is to take the first round of
TDX Connect enabling through the tsm.git tree with acks. This round does
not have kvm entanglements, i.e. IOMMU coordination and device
assignment come later. It also does not have much in the way of core x86
entanglements beyond new seamcall exports.

---

## [36] Dave Hansen — 2026-03-05
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during
 bringup*

On 3/5/26 10:50, dan.j.williams@intel.com wrote:
> My proposal, unless you or Dave holler, is to take the first round of
> TDX Connect enabling through the tsm.git tree with acks. This round does

Sounds sane to me.

---

## [37] Sean Christopherson — 2026-03-05
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during bringup*

On Thu, Mar 05, 2026, Dave Hansen wrote:
> On 3/5/26 10:50, dan.j.williams@intel.com wrote:
> > My proposal, unless you or Dave holler, is to take the first round of

+1.  If there aren't any KVM changes, ignorance is bliss :-)

---

## [38] Sean Christopherson — 2026-03-05
*Subject: Re: [PATCH v3 00/16] KVM: x86/tdx: Have TDX handle VMXON during bringup*

On Thu, Mar 05, 2026, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> > On Fri, 13 Feb 2026 17:26:46 -0800, Sean Christopherson wrote:

With a timestamp, in case fixups on top are needed:

kvm-x86-vmxon-2026.03.05

---
