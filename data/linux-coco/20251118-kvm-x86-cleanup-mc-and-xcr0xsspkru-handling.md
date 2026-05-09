---
title: 'KVM: x86: Cleanup #MC and XCR0/XSS/PKRU handling'
date: 2025-11-18
last_reply: 2025-11-21
message_count: 9
participants: ['Sean Christopherson', 'Tony Lindgren', 'Binbin Wu']
---

## [1] Sean Christopherson — 2025-11-18

Optimize XCR0/XSS loads that are currently done on every VM-Enter and VM-Exit,
by handling them outside of KVM's fastpath inner loop.

Context switching at entry/exit is unnecessary behavior inherited from a
hack-a-fix that papered over an egregious #MC handling bug where the kernel #MC
handler would call schedule() from atomic contexts.  The resulting #GP due to
trying to swap FPU state with a guest XCR0/XSS was "fixed" by loading the host
values before handling #MCs from the guest.

Thankfully, the #MC mess has long since been cleaned up, so it's once again
safe to swap XCR0/XSS outside of the fastpath (but with IRQs still disabled!).

Note, Binbin's kvm_load_xfeatures() still applies cleanly on top, so I
deliberately didn't include it here (but am still planning on applying it).

v2:
 - Collect reviews. [Jon, Rick]
 - Fix TDX (suprisingly, not servicing host IRQs is problematic, /s). [Tony]

v1: https://lore.kernel.org/all/20251030224246.3456492-1-seanjc@google.com

Sean Christopherson (4):
  KVM: SVM: Handle #MCs in guest outside of fastpath
  KVM: VMX: Handle #MCs on VM-Enter/TD-Enter outside of the fastpath
  KVM: x86: Load guest/host XCR0 and XSS outside of the fastpath run
    loop
  KVM: x86: Load guest/host PKRU outside of the fastpath run loop

 arch/x86/kvm/svm/svm.c | 20 ++++++++---------
 arch/x86/kvm/vmx/tdx.c |  3 ---
 arch/x86/kvm/vmx/vmx.c | 20 +++++++++--------
 arch/x86/kvm/x86.c     | 51 +++++++++++++++++++++++++++++-------------
 arch/x86/kvm/x86.h     |  2 --
 5 files changed, 55 insertions(+), 41 deletions(-)


base-commit: 4531ff85d9251ff429a633bdb55209d3360f39f2

---

## [2] Sean Christopherson — 2025-11-18
*Subject: [PATCH v2 1/4] KVM: SVM: Handle #MCs in guest outside of fastpath*

Handle Machine Checks (#MC) that happen in the guest (by forwarding them
to the host) outside of KVM's fastpath so that as much host state as
possible is re-loaded before invoking the kernel's #MC handler.  The only
requirement is that KVM invokes the #MC handler before enabling IRQs (and
even that could _probably_ be relaxed to handling #MCs before enabling
preemption).

Waiting to handle #MCs until "more" host state is loaded hardens KVM
against flaws in the #MC handler, which has historically been quite
brittle. E.g. prior to commit 5567d11c21a1 ("x86/mce: Send #MC singal from
task work"), the #MC code could trigger a schedule() with IRQs and
preemption disabled.  That led to a KVM hack-a-fix in commit 1811d979c716
("x86/kvm: move kvm_load/put_guest_xcr0 into atomic context").

Note, except for #MCs on VM-Enter, VMX already handles #MCs outside of the
fastpath.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Jon Kohler <jon@nutanix.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/svm/svm.c | 18 +++++++++---------
 1 file changed, 9 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 9aac0eb3a490..bf34378ebe2d 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4321,14 +4321,6 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	vcpu->arch.regs_avail &= ~SVM_REGS_LAZY_LOAD_SET;
 
-	/*
-	 * We need to handle MC intercepts here before the vcpu has a chance to
-	 * change the physical cpu
-	 */
-	if (unlikely(svm->vmcb->control.exit_code ==
-		     SVM_EXIT_EXCP_BASE + MC_VECTOR))
-		svm_handle_mce(vcpu);
-
 	trace_kvm_exit(vcpu, KVM_ISA_SVM);
 
 	svm_complete_interrupts(vcpu);
@@ -4631,8 +4623,16 @@ static int svm_check_intercept(struct kvm_vcpu *vcpu,
 
 static void svm_handle_exit_irqoff(struct kvm_vcpu *vcpu)
 {
-	if (to_svm(vcpu)->vmcb->control.exit_code == SVM_EXIT_INTR)
+	switch (to_svm(vcpu)->vmcb->control.exit_code) {
+	case SVM_EXIT_EXCP_BASE + MC_VECTOR:
+		svm_handle_mce(vcpu);
+		break;
+	case SVM_EXIT_INTR:
 		vcpu->arch.at_instruction_boundary = true;
+		break;
+	default:
+		break;
+	}
 }
 
 static void svm_setup_mce(struct kvm_vcpu *vcpu)

---

## [3] Sean Christopherson — 2025-11-18
*Subject: [PATCH v2 2/4] KVM: VMX: Handle #MCs on VM-Enter/TD-Enter outside of
 the fastpath*

Handle Machine Checks (#MC) that happen on VM-Enter (VMX or TDX) outside
of KVM's fastpath so that as much host state as possible is re-loaded
before invoking the kernel's #MC handler.  The only requirement is that
KVM invokes the #MC handler before enabling IRQs (and even that could
_probably_ be related to handling #MCs before enabling preemption).

Waiting to handle #MCs until "more" host state is loaded hardens KVM
against flaws in the #MC handler, which has historically been quite
brittle. E.g. prior to commit 5567d11c21a1 ("x86/mce: Send #MC singal from
task work"), the #MC code could trigger a schedule() with IRQs and
preemption disabled.  That led to a KVM hack-a-fix in commit 1811d979c716
("x86/kvm: move kvm_load/put_guest_xcr0 into atomic context").

Note, vmx_handle_exit_irqoff() is common to VMX and TDX guests.

Cc: Tony Lindgren <tony.lindgren@linux.intel.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Jon Kohler <jon@nutanix.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c |  3 ---
 arch/x86/kvm/vmx/vmx.c | 16 +++++++++++-----
 2 files changed, 11 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index e6105a527372..2d7a4d52ccfb 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1110,9 +1110,6 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	if (unlikely((tdx->vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR))
 		return EXIT_FASTPATH_NONE;
 
-	if (unlikely(vmx_get_exit_reason(vcpu).basic == EXIT_REASON_MCE_DURING_VMENTRY))
-		kvm_machine_check();
-
 	trace_kvm_exit(vcpu, KVM_ISA_VMX);
 
 	if (unlikely(tdx_failed_vmentry(vcpu)))
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index fdcc519348cd..f369c499b2c3 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -7062,10 +7062,19 @@ void vmx_handle_exit_irqoff(struct kvm_vcpu *vcpu)
 	if (to_vt(vcpu)->emulation_required)
 		return;
 
-	if (vmx_get_exit_reason(vcpu).basic == EXIT_REASON_EXTERNAL_INTERRUPT)
+	switch (vmx_get_exit_reason(vcpu).basic) {
+	case EXIT_REASON_EXTERNAL_INTERRUPT:
 		handle_external_interrupt_irqoff(vcpu, vmx_get_intr_info(vcpu));
-	else if (vmx_get_exit_reason(vcpu).basic == EXIT_REASON_EXCEPTION_NMI)
+		break;
+	case EXIT_REASON_EXCEPTION_NMI:
 		handle_exception_irqoff(vcpu, vmx_get_intr_info(vcpu));
+		break;
+	case EXIT_REASON_MCE_DURING_VMENTRY:
+		kvm_machine_check();
+		break;
+	default:
+		break;
+	}
 }
 
 /*
@@ -7528,9 +7537,6 @@ fastpath_t vmx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	if (unlikely(vmx->fail))
 		return EXIT_FASTPATH_NONE;
 
-	if (unlikely((u16)vmx_get_exit_reason(vcpu).basic == EXIT_REASON_MCE_DURING_VMENTRY))
-		kvm_machine_check();
-
 	trace_kvm_exit(vcpu, KVM_ISA_VMX);
 
 	if (unlikely(vmx_get_exit_reason(vcpu).failed_vmentry))

---

## [4] Sean Christopherson — 2025-11-18
*Subject: [PATCH v2 3/4] KVM: x86: Load guest/host XCR0 and XSS outside of the
 fastpath run loop*

Move KVM's swapping of XFEATURE masks, i.e. XCR0 and XSS, out of the
fastpath loop now that the guts of the #MC handler runs in task context,
i.e. won't invoke schedule() with preemption disabled and clobber state
(or crash the kernel) due to trying to context switch XSTATE with a mix
of host and guest state.

For all intents and purposes, this reverts commit 1811d979c716 ("x86/kvm:
move kvm_load/put_guest_xcr0 into atomic context"), which papered over an
egregious bug/flaw in the #MC handler where it would do schedule() even
though IRQs are disabled.  E.g. the call stack from the commit:

  kvm_load_guest_xcr0
  ...
  kvm_x86_ops->run(vcpu)
    vmx_vcpu_run
      vmx_complete_atomic_exit
        kvm_machine_check
          do_machine_check
            do_memory_failure
              memory_failure
                lock_page

Commit 1811d979c716 "fixed" the immediate issue of XRSTORS exploding, but
completely ignored that scheduling out a vCPU task while IRQs and
preemption is wildly broken.  Thankfully, commit 5567d11c21a1 ("x86/mce:
Send #MC singal from task work") (somewhat incidentally?) fixed that flaw
by pushing the meat of the work to the user-return path, i.e. to task
context.

KVM has also hardened itself against #MC goofs by moving #MC forwarding to
kvm_x86_ops.handle_exit_irqoff(), i.e. out of the fastpath.  While that's
by no means a robust fix, restoring as much state as possible before
handling the #MC will hopefully provide some measure of protection in the
event that #MC handling goes off the rails again.

Note, KVM always intercepts XCR0 writes for vCPUs without protected state,
e.g. there's no risk of consuming a stale XCR0 when determining if a PKRU
update is needed; kvm_load_host_xfeatures() only reads, and never writes,
vcpu->arch.xcr0.

Deferring the XCR0 and XSS loads shaves ~300 cycles off the fastpath for
Intel, and ~500 cycles for AMD.  E.g. using INVD in KVM-Unit-Test's
vmexit.c, which an extra hack to enable CR4.OXSAVE, latency numbers for
AMD Turin go from ~2000 => 1500, and for Intel Emerald Rapids, go from
~1300 => ~1000.

Cc: Jon Kohler <jon@nutanix.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Jon Kohler <jon@nutanix.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 39 ++++++++++++++++++++++++++-------------
 1 file changed, 26 insertions(+), 13 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index f98c5afa3e41..d8d547c5e014 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -1216,13 +1216,12 @@ void kvm_lmsw(struct kvm_vcpu *vcpu, unsigned long msw)
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_lmsw);
 
-void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu)
+static void kvm_load_guest_xfeatures(struct kvm_vcpu *vcpu)
 {
 	if (vcpu->arch.guest_state_protected)
 		return;
 
 	if (kvm_is_cr4_bit_set(vcpu, X86_CR4_OSXSAVE)) {
-
 		if (vcpu->arch.xcr0 != kvm_host.xcr0)
 			xsetbv(XCR_XFEATURE_ENABLED_MASK, vcpu->arch.xcr0);
 
@@ -1230,6 +1229,27 @@ void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu)
 		    vcpu->arch.ia32_xss != kvm_host.xss)
 			wrmsrq(MSR_IA32_XSS, vcpu->arch.ia32_xss);
 	}
+}
+
+static void kvm_load_host_xfeatures(struct kvm_vcpu *vcpu)
+{
+	if (vcpu->arch.guest_state_protected)
+		return;
+
+	if (kvm_is_cr4_bit_set(vcpu, X86_CR4_OSXSAVE)) {
+		if (vcpu->arch.xcr0 != kvm_host.xcr0)
+			xsetbv(XCR_XFEATURE_ENABLED_MASK, kvm_host.xcr0);
+
+		if (guest_cpu_cap_has(vcpu, X86_FEATURE_XSAVES) &&
+		    vcpu->arch.ia32_xss != kvm_host.xss)
+			wrmsrq(MSR_IA32_XSS, kvm_host.xss);
+	}
+}
+
+void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu)
+{
+	if (vcpu->arch.guest_state_protected)
+		return;
 
 	if (cpu_feature_enabled(X86_FEATURE_PKU) &&
 	    vcpu->arch.pkru != vcpu->arch.host_pkru &&
@@ -1251,17 +1271,6 @@ void kvm_load_host_xsave_state(struct kvm_vcpu *vcpu)
 		if (vcpu->arch.pkru != vcpu->arch.host_pkru)
 			wrpkru(vcpu->arch.host_pkru);
 	}
-
-	if (kvm_is_cr4_bit_set(vcpu, X86_CR4_OSXSAVE)) {
-
-		if (vcpu->arch.xcr0 != kvm_host.xcr0)
-			xsetbv(XCR_XFEATURE_ENABLED_MASK, kvm_host.xcr0);
-
-		if (guest_cpu_cap_has(vcpu, X86_FEATURE_XSAVES) &&
-		    vcpu->arch.ia32_xss != kvm_host.xss)
-			wrmsrq(MSR_IA32_XSS, kvm_host.xss);
-	}
-
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_load_host_xsave_state);
 
@@ -11311,6 +11320,8 @@ static int vcpu_enter_guest(struct kvm_vcpu *vcpu)
 	if (vcpu->arch.guest_fpu.xfd_err)
 		wrmsrq(MSR_IA32_XFD_ERR, vcpu->arch.guest_fpu.xfd_err);
 
+	kvm_load_guest_xfeatures(vcpu);
+
 	if (unlikely(vcpu->arch.switch_db_regs &&
 		     !(vcpu->arch.switch_db_regs & KVM_DEBUGREG_AUTO_SWITCH))) {
 		set_debugreg(DR7_FIXED_1, 7);
@@ -11397,6 +11408,8 @@ static int vcpu_enter_guest(struct kvm_vcpu *vcpu)
 	vcpu->mode = OUTSIDE_GUEST_MODE;
 	smp_wmb();
 
+	kvm_load_host_xfeatures(vcpu);
+
 	/*
 	 * Sync xfd before calling handle_exit_irqoff() which may
 	 * rely on the fact that guest_fpu::xfd is up-to-date (e.g.

---

## [5] Sean Christopherson — 2025-11-18
*Subject: [PATCH v2 4/4] KVM: x86: Load guest/host PKRU outside of the fastpath
 run loop*

Move KVM's swapping of PKRU outside of the fastpath loop, as there is no
KVM code anywhere in the fastpath that accesses guest/userspace memory,
i.e. that can consume protection keys.

As documented by commit 1be0e61c1f25 ("KVM, pkeys: save/restore PKRU when
guest/host switches"), KVM just needs to ensure the host's PKRU is loaded
when KVM (or the kernel at-large) may access userspace memory.  And at the
time of commit 1be0e61c1f25, KVM didn't have a fastpath, and PKU was
strictly contained to VMX, i.e. there was no reason to swap PKRU outside
of vmx_vcpu_run().

Over time, the "need" to swap PKRU close to VM-Enter was likely falsely
solidified by the association with XFEATUREs in commit 37486135d3a7
("KVM: x86: Fix pkru save/restore when guest CR4.PKE=0, move it to x86.c"),
and XFEATURE swapping was in turn moved close to VM-Enter/VM-Exit as a
KVM hack-a-fix ution for an #MC handler bug by commit 1811d979c716
("x86/kvm: move kvm_load/put_guest_xcr0 into atomic context").

Deferring the PKRU loads shaves ~40 cycles off the fastpath for Intel,
and ~60 cycles for AMD.  E.g. using INVD in KVM-Unit-Test's vmexit.c,
with extra hacks to enable CR4.PKE and PKRU=(-1u & ~0x3), latency numbers
for AMD Turin go from ~1560 => ~1500, and for Intel Emerald Rapids, go
from ~810 => ~770.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Jon Kohler <jon@nutanix.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/svm/svm.c |  2 --
 arch/x86/kvm/vmx/vmx.c |  4 ----
 arch/x86/kvm/x86.c     | 14 ++++++++++----
 arch/x86/kvm/x86.h     |  2 --
 4 files changed, 10 insertions(+), 12 deletions(-)

diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index bf34378ebe2d..1c67c1a6771d 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4246,7 +4246,6 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		svm_set_dr6(vcpu, DR6_ACTIVE_LOW);
 
 	clgi();
-	kvm_load_guest_xsave_state(vcpu);
 
 	/*
 	 * Hardware only context switches DEBUGCTL if LBR virtualization is
@@ -4289,7 +4288,6 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	    vcpu->arch.host_debugctl != svm->vmcb->save.dbgctl)
 		update_debugctlmsr(vcpu->arch.host_debugctl);
 
-	kvm_load_host_xsave_state(vcpu);
 	stgi();
 
 	/* Any pending NMI will happen here */
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index f369c499b2c3..9b8a6405da95 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -7475,8 +7475,6 @@ fastpath_t vmx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	if (vcpu->guest_debug & KVM_GUESTDBG_SINGLESTEP)
 		vmx_set_interrupt_shadow(vcpu, 0);
 
-	kvm_load_guest_xsave_state(vcpu);
-
 	pt_guest_enter(vmx);
 
 	atomic_switch_perf_msrs(vmx);
@@ -7520,8 +7518,6 @@ fastpath_t vmx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	pt_guest_exit(vmx);
 
-	kvm_load_host_xsave_state(vcpu);
-
 	if (is_guest_mode(vcpu)) {
 		/*
 		 * Track VMLAUNCH/VMRESUME that have made past guest state
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index d8d547c5e014..9586a26eb27e 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -1246,7 +1246,7 @@ static void kvm_load_host_xfeatures(struct kvm_vcpu *vcpu)
 	}
 }
 
-void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu)
+static void kvm_load_guest_pkru(struct kvm_vcpu *vcpu)
 {
 	if (vcpu->arch.guest_state_protected)
 		return;
@@ -1257,9 +1257,8 @@ void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu)
 	     kvm_is_cr4_bit_set(vcpu, X86_CR4_PKE)))
 		wrpkru(vcpu->arch.pkru);
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_load_guest_xsave_state);
 
-void kvm_load_host_xsave_state(struct kvm_vcpu *vcpu)
+static void kvm_load_host_pkru(struct kvm_vcpu *vcpu)
 {
 	if (vcpu->arch.guest_state_protected)
 		return;
@@ -1272,7 +1271,6 @@ void kvm_load_host_xsave_state(struct kvm_vcpu *vcpu)
 			wrpkru(vcpu->arch.host_pkru);
 	}
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_load_host_xsave_state);
 
 #ifdef CONFIG_X86_64
 static inline u64 kvm_guest_supported_xfd(struct kvm_vcpu *vcpu)
@@ -11350,6 +11348,12 @@ static int vcpu_enter_guest(struct kvm_vcpu *vcpu)
 
 	guest_timing_enter_irqoff();
 
+	/*
+	 * Swap PKRU with hardware breakpoints disabled to minimize the number
+	 * of flows where non-KVM code can run with guest state loaded.
+	 */
+	kvm_load_guest_pkru(vcpu);
+
 	for (;;) {
 		/*
 		 * Assert that vCPU vs. VM APICv state is consistent.  An APICv
@@ -11378,6 +11382,8 @@ static int vcpu_enter_guest(struct kvm_vcpu *vcpu)
 		++vcpu->stat.exits;
 	}
 
+	kvm_load_host_pkru(vcpu);
+
 	/*
 	 * Do this here before restoring debug registers on the host.  And
 	 * since we do this before handling the vmexit, a DR access vmexit
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index f3dc77f006f9..24c754b0db2e 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -622,8 +622,6 @@ static inline void kvm_machine_check(void)
 #endif
 }
 
-void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu);
-void kvm_load_host_xsave_state(struct kvm_vcpu *vcpu);
 int kvm_spec_ctrl_test_value(u64 value);
 int kvm_handle_memory_failure(struct kvm_vcpu *vcpu, int r,
 			      struct x86_exception *e);

---

## [6] Tony Lindgren — 2025-11-19
*Subject: Re: [PATCH v2 2/4] KVM: VMX: Handle #MCs on VM-Enter/TD-Enter
 outside of the fastpath*

On Tue, Nov 18, 2025 at 02:23:26PM -0800, Sean Christopherson wrote:
> Handle Machine Checks (#MC) that happen on VM-Enter (VMX or TDX) outside
> of KVM's fastpath so that as much host state as possible is re-loaded

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [7] Binbin Wu — 2025-11-21
*Subject: Re: [PATCH v2 2/4] KVM: VMX: Handle #MCs on VM-Enter/TD-Enter outside
 of the fastpath*

On 11/19/2025 6:23 AM, Sean Christopherson wrote:
> Handle Machine Checks (#MC) that happen on VM-Enter (VMX or TDX) outside
> of KVM's fastpath so that as much host state as possible is re-loaded

I think the bug in v1 is because the fact that the function is the common path
for both VMX and TDX is overlooked. Do you think it is worth a comment to
tell the function is the common path for both VMX and TDX?

Otherwise,
Reviewed-by: Binbin Wu <binbin.wu@linxu.intel.com>


>   	if (to_vt(vcpu)->emulation_required)
>   		return;

---

## [8] Sean Christopherson — 2025-11-21
*Subject: Re: [PATCH v2 0/4] KVM: x86: Cleanup #MC and XCR0/XSS/PKRU handling*

On Tue, 18 Nov 2025 14:23:24 -0800, Sean Christopherson wrote:
> Optimize XCR0/XSS loads that are currently done on every VM-Enter and VM-Exit,
> by handling them outside of KVM's fastpath inner loop.

Applied to kvm-x86 misc, thanks!

[1/4] KVM: SVM: Handle #MCs in guest outside of fastpath
      https://github.com/kvm-x86/linux/commit/ebd1a3365500
[2/4] KVM: VMX: Handle #MCs on VM-Enter/TD-Enter outside of the fastpath
      https://github.com/kvm-x86/linux/commit/63669bd1d50f
[3/4] KVM: x86: Load guest/host XCR0 and XSS outside of the fastpath run loop
      https://github.com/kvm-x86/linux/commit/75c69c82f211
[4/4] KVM: x86: Load guest/host PKRU outside of the fastpath run loop
      https://github.com/kvm-x86/linux/commit/7649412af3ea

--
https://github.com/kvm-x86/linux/tree/next

---

## [9] Sean Christopherson — 2025-11-21
*Subject: Re: [PATCH v2 2/4] KVM: VMX: Handle #MCs on VM-Enter/TD-Enter outside
 of the fastpath*

On Fri, Nov 21, 2025, Binbin Wu wrote:
> On 11/19/2025 6:23 AM, Sean Christopherson wrote:
> > diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c

Probably not?  Addressing that quirk crossed my mind as well, but there are so
many dependencies and so much interaction between VMX and TDX code that I think
we just need get used to things and not assuming TDX is isolated.  I.e. trying
to add comments and/or tweak names will probably be a game of whack-a-mole, and
will likely cause confusion, e.g. due to some flows being commented and others
not.

---
