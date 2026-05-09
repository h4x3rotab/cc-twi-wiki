---
title: 'KVM: SEV: Track SNP launch state and disallow invalid\n userspace interactions'
date: 2026-02-02
last_reply: 2026-02-02
message_count: 1
participants: ['Jethro Beekman']
---

## [1] Jethro Beekman — 2026-02-02

Calling any of the SNP_LAUNCH_ ioctls after SNP_LAUNCH_FINISH results in a
kernel page fault due to RMP violation. Track SNP launch state and exit early.

vCPUs created after SNP_LAUNCH_FINISH won't have a guest VMSA automatically
created during SNP_LAUNCH_FINISH by converting the kernel-allocated VMSA. Don't
allocate a VMSA page, so that the vCPU is in a state similar to what it would
be after SNP AP destroy. This ensures pre_sev_run() prevents the vCPU from
running even if userspace makes the vCPU runnable.

Signed-off-by: Jethro Beekman <jethro@fortanix.com>
---
 arch/x86/kvm/svm/sev.c | 43 ++++++++++++++++++++++++++----------------
 arch/x86/kvm/svm/svm.h |  1 +
 2 files changed, 28 insertions(+), 16 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f59c65abe3cf..cdaca10b8773 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2205,6 +2205,9 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (!sev_snp_guest(kvm))
 		return -ENOTTY;
 
+	if (sev->snp_finished)
+		return -EINVAL;
+
 	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
 		return -EFAULT;
 
@@ -2369,7 +2372,7 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	void __user *src;
 	int ret = 0;
 
-	if (!sev_snp_guest(kvm) || !sev->snp_context)
+	if (!sev_snp_guest(kvm) || !sev->snp_context || sev->snp_finished)
 		return -EINVAL;
 
 	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
@@ -2502,7 +2505,7 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (!sev_snp_guest(kvm))
 		return -ENOTTY;
 
-	if (!sev->snp_context)
+	if (!sev->snp_context || sev->snp_finished)
 		return -EINVAL;
 
 	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
@@ -2548,13 +2551,15 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	data->gctx_paddr = __psp_pa(sev->snp_context);
 	ret = sev_issue_cmd(kvm, SEV_CMD_SNP_LAUNCH_FINISH, data, &argp->error);
 
-	/*
-	 * Now that there will be no more SNP_LAUNCH_UPDATE ioctls, private pages
-	 * can be given to the guest simply by marking the RMP entry as private.
-	 * This can happen on first access and also with KVM_PRE_FAULT_MEMORY.
-	 */
-	if (!ret)
+	if (!ret) {
+		sev->snp_finished = true;
+		/*
+		 * Now that there will be no more SNP_LAUNCH_UPDATE ioctls, private pages
+		 * can be given to the guest simply by marking the RMP entry as private.
+		 * This can happen on first access and also with KVM_PRE_FAULT_MEMORY.
+		 */
 		kvm->arch.pre_fault_allowed = true;
+	}
 
 	kfree(id_auth);
 
@@ -3253,6 +3258,9 @@ void sev_free_vcpu(struct kvm_vcpu *vcpu)
 
 	svm = to_svm(vcpu);
 
+	if (!svm->sev_es.vmsa)
+		goto skip_vmsa_free;
+
 	/*
 	 * If it's an SNP guest, then the VMSA was marked in the RMP table as
 	 * a guest-owned page. Transition the page to hypervisor state before
@@ -4653,6 +4661,7 @@ void sev_init_vmcb(struct vcpu_svm *svm, bool init_event)
 
 int sev_vcpu_create(struct kvm_vcpu *vcpu)
 {
+	struct kvm_sev_info *sev = to_kvm_sev_info(vcpu->kvm);
 	struct vcpu_svm *svm = to_svm(vcpu);
 	struct page *vmsa_page;
 
@@ -4661,15 +4670,17 @@ int sev_vcpu_create(struct kvm_vcpu *vcpu)
 	if (!sev_es_guest(vcpu->kvm))
 		return 0;
 
-	/*
-	 * SEV-ES guests require a separate (from the VMCB) VMSA page used to
-	 * contain the encrypted register state of the guest.
-	 */
-	vmsa_page = snp_safe_alloc_page();
-	if (!vmsa_page)
-		return -ENOMEM;
+	if (!sev->snp_finished) {
+		/*
+		 * SEV-ES guests require a separate (from the VMCB) VMSA page used to
+		 * contain the encrypted register state of the guest.
+		 */
+		vmsa_page = snp_safe_alloc_page();
+		if (!vmsa_page)
+			return -ENOMEM;
 
-	svm->sev_es.vmsa = page_address(vmsa_page);
+		svm->sev_es.vmsa = page_address(vmsa_page);
+	}
 
 	vcpu->arch.guest_tsc_protected = snp_is_secure_tsc_enabled(vcpu->kvm);
 
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 01be93a53d07..59c328c13b2a 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -96,6 +96,7 @@ struct kvm_sev_info {
 	bool active;		/* SEV enabled guest */
 	bool es_active;		/* SEV-ES enabled guest */
 	bool need_init;		/* waiting for SEV_INIT2 */
+	bool snp_finished;	/* SNP guest measurement has been finalized */
 	unsigned int asid;	/* ASID used for this guest */
 	unsigned int handle;	/* SEV firmware handle */
 	int fd;			/* SEV device fd */

---
