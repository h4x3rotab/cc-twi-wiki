---
title: 'KVM: SEV: Enable SNP AP CPU hotplug'
date: 2026-02-02
last_reply: 2026-02-02
message_count: 1
participants: ['Jethro Beekman']
---

## [1] Jethro Beekman — 2026-02-02

The GHCB protocol states that after AP CREATE (as opposed to CREATE_ON_INIT),
the hypervisor must immediately proceed to VMRUN. Update vCPU state on AP
CREATE so this happens.

vCPUs created after SNP_LAUNCH_FINISH don't go through snp_launch_update_vmsa.
Ensure the vCPU state is updated properly during VMCB initialization.

Signed-off-by: Jethro Beekman <jethro@fortanix.com>
---
 arch/x86/kvm/svm/sev.c | 43 ++++++++++++++++++++++++------------------
 1 file changed, 25 insertions(+), 18 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index cdaca10b8773..9af1bd5b2071 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -960,6 +960,19 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 	return 0;
 }
 
+static void sev_es_finalize_vcpu(struct kvm_vcpu *vcpu)
+{
+	vcpu->arch.guest_state_protected = true;
+	/*
+	 * SEV-ES (and thus SNP) guest mandates LBR Virtualization to
+	 * be _always_ ON. Enable it only after setting
+	 * guest_state_protected because KVM_SET_MSRS allows dynamic
+	 * toggling of LBRV (for performance reason) on write access to
+	 * MSR_IA32_DEBUGCTLMSR when guest_state_protected is not set.
+	 */
+	svm_enable_lbrv(vcpu);
+}
+
 static int __sev_launch_update_vmsa(struct kvm *kvm, struct kvm_vcpu *vcpu,
 				    int *error)
 {
@@ -999,15 +1012,9 @@ static int __sev_launch_update_vmsa(struct kvm *kvm, struct kvm_vcpu *vcpu,
 	 * do xsave/xrstor on it.
 	 */
 	fpstate_set_confidential(&vcpu->arch.guest_fpu);
-	vcpu->arch.guest_state_protected = true;
 
-	/*
-	 * SEV-ES guest mandates LBR Virtualization to be _always_ ON. Enable it
-	 * only after setting guest_state_protected because KVM_SET_MSRS allows
-	 * dynamic toggling of LBRV (for performance reason) on write access to
-	 * MSR_IA32_DEBUGCTLMSR when guest_state_protected is not set.
-	 */
-	svm_enable_lbrv(vcpu);
+	sev_es_finalize_vcpu(vcpu);
+
 	return 0;
 }
 
@@ -2480,15 +2487,7 @@ static int snp_launch_update_vmsa(struct kvm *kvm, struct kvm_sev_cmd *argp)
 			return ret;
 		}
 
-		svm->vcpu.arch.guest_state_protected = true;
-		/*
-		 * SEV-ES (and thus SNP) guest mandates LBR Virtualization to
-		 * be _always_ ON. Enable it only after setting
-		 * guest_state_protected because KVM_SET_MSRS allows dynamic
-		 * toggling of LBRV (for performance reason) on write access to
-		 * MSR_IA32_DEBUGCTLMSR when guest_state_protected is not set.
-		 */
-		svm_enable_lbrv(vcpu);
+		sev_es_finalize_vcpu(vcpu);
 	}
 
 	return 0;
@@ -4030,6 +4029,10 @@ static void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu)
 	/* Use the new VMSA */
 	svm->vmcb->control.vmsa_pa = pfn_to_hpa(pfn);
 
+	/* vCPU was added after SNP_LAUNCH_FINISH */
+	if (!vcpu->arch.guest_state_protected)
+		sev_es_finalize_vcpu(vcpu);
+
 	/* Mark the vCPU as runnable */
 	kvm_set_mp_state(vcpu, KVM_MP_STATE_RUNNABLE);
 
@@ -4111,8 +4114,12 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 	 * Unless Creation is deferred until INIT, signal the vCPU to update
 	 * its state.
 	 */
-	if (request != SVM_VMGEXIT_AP_CREATE_ON_INIT)
+	if (request != SVM_VMGEXIT_AP_CREATE_ON_INIT) {
+		if (target_vcpu->arch.mp_state == KVM_MP_STATE_UNINITIALIZED ||
+			target_vcpu->arch.mp_state == KVM_MP_STATE_INIT_RECEIVED)
+				kvm_set_mp_state(target_vcpu, KVM_MP_STATE_RUNNABLE);
 		kvm_make_request_and_kick(KVM_REQ_UPDATE_PROTECTED_GUEST_STATE, target_vcpu);
+	}
 
 	return 0;
 }

---
