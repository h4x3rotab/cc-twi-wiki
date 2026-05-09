---
title: '[RFC PATCH 0/7] KVM: SEV-SNP support for running an SVSM'
date: 2024-08-27
last_reply: 2024-11-28
message_count: 9
participants: ['Tom Lendacky', 'Borislav Petkov']
---

## [1] Tom Lendacky — 2024-08-27

This series is meant to start the discussion around running a guest with
a Secure VM Service Module (SVSM) and how to transition a vCPU between
one VM Privilege Level (VMPL) and another. This is Proof-of-Concept level
code, so definitely not something looking to be merged.

When running under an SVSM, VMPL switches are needed for validating memory
and creating vCPU VM Save Area (VMSA) pages. Going forward, different
services running in the SVSM will require VMPL switching, e.g. a virtual
TPM service or Alternate Injection support. Therefore VMPL switches need
to be as fast as possible. The implementation in this series has KVM
managing the creation of VMPL levels and transitioning between the levels
without transitioning to the userspace VMM.

Going forward, the userspace VMM may need to be aware of VMPL levels. It
may be necessary to transition VMPL creation (AP Creation at a specific
VMPL level) to the userspace VMM. But keeping VMPL switching within KVM
is highly desired for performance reasons.

This PoC code does have some restrictions. For example, when running with
Restricted Injection, all injections are blocked as the SVSM is not
expecting any injections (currently). This allows for a single APIC
instance for now.

The patches can be further split and the change logs improved, but wanted
to get this out and get the discussion going.

Implemented in this RFC:
  - APIC ID list retrieval to allow for only measuring the BSP and
    allowing the guest to start all of the APs without having to use a
    broadcast SIPI
  - vCPU creation at a specific VMPL
  - vCPU execution at a specific VMPL
  - Maintain per-VMPL SEV features
  - Implement minimal Restricted Injection
    - Blocks all injection when enabled
  - SVSM support
     - SNP init flag for SVSM support
     - Measuring data with specific VMPL permissions
     - Measuring only the BSP

Things not yet implemented:
  - APIC instance separation
  - Restricted Injection support that is multi-VMPL aware


The series is based off of a slightly older kvm next branch:
  git://git.kernel.org/pub/scm/virt/kvm/kvm.git next

  7c626ce4bae1 ("Linux 6.11-rc3")

---

Carlos Bilbao (1):
  KVM: SVM: Maintain per-VMPL SEV features in kvm_sev_info

Tom Lendacky (6):
  KVM: SVM: Implement GET_AP_APIC_IDS NAE event
  KVM: SEV: Allow for VMPL level specification in AP create
  KVM: SVM: Invoke a specified VMPL level VMSA for the vCPU
  KVM: SVM: Prevent injection when restricted injection is active
  KVM: SVM: Support launching an SVSM with Restricted Injection set
  KVM: SVM: Support initialization of an SVSM

 arch/x86/include/asm/sev-common.h |   7 +
 arch/x86/include/asm/svm.h        |   9 +
 arch/x86/include/uapi/asm/kvm.h   |  10 +
 arch/x86/include/uapi/asm/svm.h   |   3 +
 arch/x86/kvm/svm/sev.c            | 530 +++++++++++++++++++++++++-----
 arch/x86/kvm/svm/svm.c            |  25 +-
 arch/x86/kvm/svm/svm.h            |  71 +++-
 arch/x86/kvm/x86.c                |   9 +
 include/uapi/linux/kvm.h          |   3 +
 9 files changed, 575 insertions(+), 92 deletions(-)

---

## [2] Tom Lendacky — 2024-08-27
*Subject: [RFC PATCH 1/7] KVM: SVM: Implement GET_AP_APIC_IDS NAE event*

Implement the GET_APIC_IDS NAE event to gather and return the list of
APIC IDs for all vCPUs in the guest.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/asm/sev-common.h |  1 +
 arch/x86/include/uapi/asm/svm.h   |  1 +
 arch/x86/kvm/svm/sev.c            | 84 ++++++++++++++++++++++++++++++-
 3 files changed, 85 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/sev-common.h b/arch/x86/include/asm/sev-common.h
index 98726c2b04f8..d63c861ef91f 100644
--- a/arch/x86/include/asm/sev-common.h
+++ b/arch/x86/include/asm/sev-common.h
@@ -136,6 +136,7 @@ enum psc_op {
 
 #define GHCB_HV_FT_SNP			BIT_ULL(0)
 #define GHCB_HV_FT_SNP_AP_CREATION	BIT_ULL(1)
+#define GHCB_HV_FT_APIC_ID_LIST		BIT_ULL(4)
 #define GHCB_HV_FT_SNP_MULTI_VMPL	BIT_ULL(5)
 
 /*
diff --git a/arch/x86/include/uapi/asm/svm.h b/arch/x86/include/uapi/asm/svm.h
index 1814b413fd57..f8fa3c4c0322 100644
--- a/arch/x86/include/uapi/asm/svm.h
+++ b/arch/x86/include/uapi/asm/svm.h
@@ -115,6 +115,7 @@
 #define SVM_VMGEXIT_AP_CREATE_ON_INIT		0
 #define SVM_VMGEXIT_AP_CREATE			1
 #define SVM_VMGEXIT_AP_DESTROY			2
+#define SVM_VMGEXIT_GET_APIC_IDS		0x80000017
 #define SVM_VMGEXIT_SNP_RUN_VMPL		0x80000018
 #define SVM_VMGEXIT_HV_FEATURES			0x8000fffd
 #define SVM_VMGEXIT_TERM_REQUEST		0x8000fffe
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 532df12b43c5..199bdc7c7db1 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -39,7 +39,9 @@
 #define GHCB_VERSION_DEFAULT	2ULL
 #define GHCB_VERSION_MIN	1ULL
 
-#define GHCB_HV_FT_SUPPORTED	(GHCB_HV_FT_SNP | GHCB_HV_FT_SNP_AP_CREATION)
+#define GHCB_HV_FT_SUPPORTED	(GHCB_HV_FT_SNP			| \
+				 GHCB_HV_FT_SNP_AP_CREATION	| \
+				 GHCB_HV_FT_APIC_ID_LIST)
 
 /* enable/disable SEV support */
 static bool sev_enabled = true;
@@ -3390,6 +3392,10 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 			if (!kvm_ghcb_rax_is_valid(svm))
 				goto vmgexit_err;
 		break;
+	case SVM_VMGEXIT_GET_APIC_IDS:
+		if (!kvm_ghcb_rax_is_valid(svm))
+			goto vmgexit_err;
+		break;
 	case SVM_VMGEXIT_NMI_COMPLETE:
 	case SVM_VMGEXIT_AP_HLT_LOOP:
 	case SVM_VMGEXIT_AP_JUMP_TABLE:
@@ -4124,6 +4130,77 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 	return 1; /* resume guest */
 }
 
+struct sev_apic_id_desc {
+	u32	num_entries;
+	u32	apic_ids[];
+};
+
+static void sev_get_apic_ids(struct vcpu_svm *svm)
+{
+	struct ghcb *ghcb = svm->sev_es.ghcb;
+	struct kvm_vcpu *vcpu = &svm->vcpu, *loop_vcpu;
+	struct kvm *kvm = vcpu->kvm;
+	unsigned int id_desc_size;
+	struct sev_apic_id_desc *desc;
+	kvm_pfn_t pfn;
+	gpa_t gpa;
+	u64 pages;
+	unsigned long i;
+	int n;
+
+	pages = vcpu->arch.regs[VCPU_REGS_RAX];
+
+	/* Each APIC ID is 32-bits in size, so make sure there is room */
+	n = atomic_read(&kvm->online_vcpus);
+	/*TODO: is this possible? */
+	if (n < 0)
+		return;
+
+	id_desc_size = sizeof(*desc);
+	id_desc_size += n * sizeof(desc->apic_ids[0]);
+	if (id_desc_size > (pages * PAGE_SIZE)) {
+		vcpu->arch.regs[VCPU_REGS_RAX] = PFN_UP(id_desc_size);
+		return;
+	}
+
+	gpa = svm->vmcb->control.exit_info_1;
+
+	ghcb_set_sw_exit_info_1(ghcb, 2);
+	ghcb_set_sw_exit_info_2(ghcb, 5);
+
+	if (!page_address_valid(vcpu, gpa))
+		return;
+
+	pfn = gfn_to_pfn(kvm, gpa_to_gfn(gpa));
+	if (is_error_noslot_pfn(pfn))
+		return;
+
+	if (!pages)
+		return;
+
+	/* Allocate a buffer to hold the APIC IDs */
+	desc = kvzalloc(id_desc_size, GFP_KERNEL_ACCOUNT);
+	if (!desc)
+		return;
+
+	desc->num_entries = n;
+	kvm_for_each_vcpu(i, loop_vcpu, kvm) {
+		/*TODO: is this possible? */
+		if (i > n)
+			break;
+
+		desc->apic_ids[i] = loop_vcpu->vcpu_id;
+	}
+
+	if (!kvm_write_guest(kvm, gpa, desc, id_desc_size)) {
+		/* IDs were successfully written */
+		ghcb_set_sw_exit_info_1(ghcb, 0);
+		ghcb_set_sw_exit_info_2(ghcb, 0);
+	}
+
+	kvfree(desc);
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4404,6 +4481,11 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 	case SVM_VMGEXIT_EXT_GUEST_REQUEST:
 		ret = snp_handle_ext_guest_req(svm, control->exit_info_1, control->exit_info_2);
 		break;
+	case SVM_VMGEXIT_GET_APIC_IDS:
+		sev_get_apic_ids(svm);
+
+		ret = 1;
+		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
 		vcpu_unimpl(vcpu,
 			    "vmgexit: unsupported event - exit_info_1=%#llx, exit_info_2=%#llx\n",

---

## [3] Tom Lendacky — 2024-08-27
*Subject: [RFC PATCH 2/7] KVM: SEV: Allow for VMPL level specification in AP create*

Update AP creation to support ADD/DESTROY of VMSAs at levels other than
VMPL0 in order to run under an SVSM at VMPL1 or lower. To maintain
backwards compatibility, the VMPL is specified in bits 16 to 19 of the
AP Creation request in SW_EXITINFO1 of the GHCB.

In order to track the VMSAs at different levels, create arrays for the
VMSAs, GHCBs, registered GHCBs and others. When switching VMPL levels,
these entries will be used to set the VMSA and GHCB physical addresses
in the VMCB for the VMPL level.

In order ensure that the proper responses are returned in the proper GHCB,
the GHCB must be unmapped at the current level and saved for restoration
later when switching back to that VMPL level.

Additional checks are applied to prevent a non-VMPL0 vCPU from being able
to perform an AP creation request at VMPL0. Additionally, a vCPU cannot
replace its own VMSA.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/asm/svm.h      |   9 ++
 arch/x86/include/uapi/asm/svm.h |   2 +
 arch/x86/kvm/svm/sev.c          | 146 +++++++++++++++++++++++---------
 arch/x86/kvm/svm/svm.c          |   6 +-
 arch/x86/kvm/svm/svm.h          |  45 ++++++++--
 arch/x86/kvm/x86.c              |   9 ++
 6 files changed, 169 insertions(+), 48 deletions(-)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index f0dea3750ca9..26339d94c00f 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -294,6 +294,15 @@ static_assert((X2AVIC_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AVIC_
 	(SVM_SEV_FEAT_RESTRICTED_INJECTION |	\
 	 SVM_SEV_FEAT_ALTERNATE_INJECTION)
 
+enum {
+	SVM_SEV_VMPL0 = 0,
+	SVM_SEV_VMPL1,
+	SVM_SEV_VMPL2,
+	SVM_SEV_VMPL3,
+
+	SVM_SEV_VMPL_MAX
+};
+
 struct vmcb_seg {
 	u16 selector;
 	u16 attrib;
diff --git a/arch/x86/include/uapi/asm/svm.h b/arch/x86/include/uapi/asm/svm.h
index f8fa3c4c0322..4a963dd12bb4 100644
--- a/arch/x86/include/uapi/asm/svm.h
+++ b/arch/x86/include/uapi/asm/svm.h
@@ -115,6 +115,8 @@
 #define SVM_VMGEXIT_AP_CREATE_ON_INIT		0
 #define SVM_VMGEXIT_AP_CREATE			1
 #define SVM_VMGEXIT_AP_DESTROY			2
+#define SVM_VMGEXIT_AP_VMPL_MASK		GENMASK(19, 16)
+#define SVM_VMGEXIT_AP_VMPL_SHIFT		16
 #define SVM_VMGEXIT_GET_APIC_IDS		0x80000017
 #define SVM_VMGEXIT_SNP_RUN_VMPL		0x80000018
 #define SVM_VMGEXIT_HV_FEATURES			0x8000fffd
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 199bdc7c7db1..c22b6f51ec81 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -807,7 +807,7 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 {
 	struct kvm_vcpu *vcpu = &svm->vcpu;
 	struct kvm_sev_info *sev = &to_kvm_svm(vcpu->kvm)->sev_info;
-	struct sev_es_save_area *save = svm->sev_es.vmsa;
+	struct sev_es_save_area *save = vmpl_vmsa(svm, SVM_SEV_VMPL0);
 	struct xregs_state *xsave;
 	const u8 *s;
 	u8 *d;
@@ -920,11 +920,11 @@ static int __sev_launch_update_vmsa(struct kvm *kvm, struct kvm_vcpu *vcpu,
 	 * the VMSA memory content (i.e it will write the same memory region
 	 * with the guest's key), so invalidate it first.
 	 */
-	clflush_cache_range(svm->sev_es.vmsa, PAGE_SIZE);
+	clflush_cache_range(vmpl_vmsa(svm, SVM_SEV_VMPL0), PAGE_SIZE);
 
 	vmsa.reserved = 0;
 	vmsa.handle = to_kvm_sev_info(kvm)->handle;
-	vmsa.address = __sme_pa(svm->sev_es.vmsa);
+	vmsa.address = __sme_pa(vmpl_vmsa(svm, SVM_SEV_VMPL0));
 	vmsa.len = PAGE_SIZE;
 	ret = sev_issue_cmd(kvm, SEV_CMD_LAUNCH_UPDATE_VMSA, &vmsa, error);
 	if (ret)
@@ -2452,7 +2452,7 @@ static int snp_launch_update_vmsa(struct kvm *kvm, struct kvm_sev_cmd *argp)
 
 	kvm_for_each_vcpu(i, vcpu, kvm) {
 		struct vcpu_svm *svm = to_svm(vcpu);
-		u64 pfn = __pa(svm->sev_es.vmsa) >> PAGE_SHIFT;
+		u64 pfn = __pa(vmpl_vmsa(svm, SVM_SEV_VMPL0)) >> PAGE_SHIFT;
 
 		ret = sev_es_sync_vmsa(svm);
 		if (ret)
@@ -2464,7 +2464,7 @@ static int snp_launch_update_vmsa(struct kvm *kvm, struct kvm_sev_cmd *argp)
 			return ret;
 
 		/* Issue the SNP command to encrypt the VMSA */
-		data.address = __sme_pa(svm->sev_es.vmsa);
+		data.address = __sme_pa(vmpl_vmsa(svm, SVM_SEV_VMPL0));
 		ret = __sev_issue_cmd(argp->sev_fd, SEV_CMD_SNP_LAUNCH_UPDATE,
 				      &data, &argp->error);
 		if (ret) {
@@ -3178,16 +3178,16 @@ void sev_free_vcpu(struct kvm_vcpu *vcpu)
 	 * releasing it back to the system.
 	 */
 	if (sev_snp_guest(vcpu->kvm)) {
-		u64 pfn = __pa(svm->sev_es.vmsa) >> PAGE_SHIFT;
+		u64 pfn = __pa(vmpl_vmsa(svm, SVM_SEV_VMPL0)) >> PAGE_SHIFT;
 
 		if (kvm_rmp_make_shared(vcpu->kvm, pfn, PG_LEVEL_4K))
 			goto skip_vmsa_free;
 	}
 
 	if (vcpu->arch.guest_state_protected)
-		sev_flush_encrypted_page(vcpu, svm->sev_es.vmsa);
+		sev_flush_encrypted_page(vcpu, vmpl_vmsa(svm, SVM_SEV_VMPL0));
 
-	__free_page(virt_to_page(svm->sev_es.vmsa));
+	__free_page(virt_to_page(vmpl_vmsa(svm, SVM_SEV_VMPL0)));
 
 skip_vmsa_free:
 	if (svm->sev_es.ghcb_sa_free)
@@ -3385,13 +3385,19 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 		if (!kvm_ghcb_sw_scratch_is_valid(svm))
 			goto vmgexit_err;
 		break;
-	case SVM_VMGEXIT_AP_CREATION:
+	case SVM_VMGEXIT_AP_CREATION: {
+		unsigned int request;
+
 		if (!sev_snp_guest(vcpu->kvm))
 			goto vmgexit_err;
-		if (lower_32_bits(control->exit_info_1) != SVM_VMGEXIT_AP_DESTROY)
+
+		request = lower_32_bits(control->exit_info_1);
+		request &= ~SVM_VMGEXIT_AP_VMPL_MASK;
+		if (request != SVM_VMGEXIT_AP_DESTROY)
 			if (!kvm_ghcb_rax_is_valid(svm))
 				goto vmgexit_err;
 		break;
+	}
 	case SVM_VMGEXIT_GET_APIC_IDS:
 		if (!kvm_ghcb_rax_is_valid(svm))
 			goto vmgexit_err;
@@ -3850,9 +3856,10 @@ static int __sev_snp_update_protected_guest_state(struct kvm_vcpu *vcpu)
 
 	/* Clear use of the VMSA */
 	svm->vmcb->control.vmsa_pa = INVALID_PAGE;
+	tgt_vmpl_vmsa_hpa(svm) = INVALID_PAGE;
 
-	if (VALID_PAGE(svm->sev_es.snp_vmsa_gpa)) {
-		gfn_t gfn = gpa_to_gfn(svm->sev_es.snp_vmsa_gpa);
+	if (VALID_PAGE(tgt_vmpl_vmsa_gpa(svm))) {
+		gfn_t gfn = gpa_to_gfn(tgt_vmpl_vmsa_gpa(svm));
 		struct kvm_memory_slot *slot;
 		kvm_pfn_t pfn;
 
@@ -3870,32 +3877,54 @@ static int __sev_snp_update_protected_guest_state(struct kvm_vcpu *vcpu)
 		/*
 		 * From this point forward, the VMSA will always be a
 		 * guest-mapped page rather than the initial one allocated
-		 * by KVM in svm->sev_es.vmsa. In theory, svm->sev_es.vmsa
-		 * could be free'd and cleaned up here, but that involves
-		 * cleanups like wbinvd_on_all_cpus() which would ideally
-		 * be handled during teardown rather than guest boot.
-		 * Deferring that also allows the existing logic for SEV-ES
-		 * VMSAs to be re-used with minimal SNP-specific changes.
+		 * by KVM in svm->sev_es.vmsa_info[vmpl].vmsa. In theory,
+		 * svm->sev_es.vmsa_info[vmpl].vmsa could be free'd and cleaned
+		 * up here, but that involves cleanups like wbinvd_on_all_cpus()
+		 * which would ideally be handled during teardown rather than
+		 * guest boot. Deferring that also allows the existing logic for
+		 * SEV-ES VMSAs to be re-used with minimal SNP-specific changes.
 		 */
-		svm->sev_es.snp_has_guest_vmsa = true;
+		tgt_vmpl_has_guest_vmsa(svm) = true;
 
 		/* Use the new VMSA */
 		svm->vmcb->control.vmsa_pa = pfn_to_hpa(pfn);
+		tgt_vmpl_vmsa_hpa(svm) = pfn_to_hpa(pfn);
+
+		/*
+		 * Since the vCPU may not have gone through the LAUNCH_UPDATE_VMSA path,
+		 * be sure to mark the guest state as protected and enable LBR virtualization.
+		 */
+		vcpu->arch.guest_state_protected = true;
+		svm_enable_lbrv(vcpu);
 
 		/* Mark the vCPU as runnable */
 		vcpu->arch.pv.pv_unhalted = false;
 		vcpu->arch.mp_state = KVM_MP_STATE_RUNNABLE;
 
-		svm->sev_es.snp_vmsa_gpa = INVALID_PAGE;
+		tgt_vmpl_vmsa_gpa(svm) = INVALID_PAGE;
 
 		/*
 		 * gmem pages aren't currently migratable, but if this ever
 		 * changes then care should be taken to ensure
-		 * svm->sev_es.vmsa is pinned through some other means.
+		 * svm->sev_es.vmsa_info[vmpl].vmsa is pinned through some other
+		 * means.
 		 */
 		kvm_release_pfn_clean(pfn);
 	}
 
+	if (cur_vmpl(svm) != tgt_vmpl(svm)) {
+		/* Unmap the current GHCB */
+		sev_es_unmap_ghcb(svm);
+
+		/* Save the GHCB GPA of the current VMPL */
+		svm->sev_es.ghcb_gpa[cur_vmpl(svm)] = svm->vmcb->control.ghcb_gpa;
+
+		/* Set the GHCB_GPA for the target VMPL and make it the current VMPL */
+		svm->vmcb->control.ghcb_gpa = svm->sev_es.ghcb_gpa[tgt_vmpl(svm)];
+
+		cur_vmpl(svm) = tgt_vmpl(svm);
+	}
+
 	/*
 	 * When replacing the VMSA during SEV-SNP AP creation,
 	 * mark the VMCB dirty so that full state is always reloaded.
@@ -3918,10 +3947,10 @@ void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu)
 
 	mutex_lock(&svm->sev_es.snp_vmsa_mutex);
 
-	if (!svm->sev_es.snp_ap_waiting_for_reset)
+	if (!tgt_vmpl_ap_waiting_for_reset(svm))
 		goto unlock;
 
-	svm->sev_es.snp_ap_waiting_for_reset = false;
+	tgt_vmpl_ap_waiting_for_reset(svm) = false;
 
 	ret = __sev_snp_update_protected_guest_state(vcpu);
 	if (ret)
@@ -3939,12 +3968,24 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 	struct vcpu_svm *target_svm;
 	unsigned int request;
 	unsigned int apic_id;
+	unsigned int vmpl;
 	bool kick;
 	int ret;
 
 	request = lower_32_bits(svm->vmcb->control.exit_info_1);
 	apic_id = upper_32_bits(svm->vmcb->control.exit_info_1);
 
+	vmpl = (request & SVM_VMGEXIT_AP_VMPL_MASK) >> SVM_VMGEXIT_AP_VMPL_SHIFT;
+	request &= ~SVM_VMGEXIT_AP_VMPL_MASK;
+
+	/* Validate the requested VMPL level */
+	if (vmpl >= SVM_SEV_VMPL_MAX) {
+		vcpu_unimpl(vcpu, "vmgexit: invalid VMPL level [%u] from guest\n",
+			    vmpl);
+		return -EINVAL;
+	}
+	vmpl = array_index_nospec(vmpl, SVM_SEV_VMPL_MAX);
+
 	/* Validate the APIC ID */
 	target_vcpu = kvm_get_vcpu_by_id(vcpu->kvm, apic_id);
 	if (!target_vcpu) {
@@ -3966,13 +4007,22 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 
 	mutex_lock(&target_svm->sev_es.snp_vmsa_mutex);
 
-	target_svm->sev_es.snp_vmsa_gpa = INVALID_PAGE;
-	target_svm->sev_es.snp_ap_waiting_for_reset = true;
+	vmpl_vmsa_gpa(target_svm, vmpl) = INVALID_PAGE;
+	vmpl_ap_waiting_for_reset(target_svm, vmpl) = true;
 
-	/* Interrupt injection mode shouldn't change for AP creation */
+	/* VMPL0 can only be replaced by another vCPU running VMPL0 */
+	if (vmpl == SVM_SEV_VMPL0 &&
+	    (vcpu == target_vcpu ||
+	     vmpl_vmsa_hpa(svm, SVM_SEV_VMPL0) != svm->vmcb->control.vmsa_pa)) {
+		ret = -EINVAL;
+		goto out;
+	}
+
+	/* Perform common AP creation validation */
 	if (request < SVM_VMGEXIT_AP_DESTROY) {
 		u64 sev_features;
 
+		/* Interrupt injection mode shouldn't change for AP creation */
 		sev_features = vcpu->arch.regs[VCPU_REGS_RAX];
 		sev_features ^= sev->vmsa_features;
 
@@ -3982,13 +4032,8 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 			ret = -EINVAL;
 			goto out;
 		}
-	}
 
-	switch (request) {
-	case SVM_VMGEXIT_AP_CREATE_ON_INIT:
-		kick = false;
-		fallthrough;
-	case SVM_VMGEXIT_AP_CREATE:
+		/* Validate the input VMSA page */
 		if (!page_address_valid(vcpu, svm->vmcb->control.exit_info_2)) {
 			vcpu_unimpl(vcpu, "vmgexit: invalid AP VMSA address [%#llx] from guest\n",
 				    svm->vmcb->control.exit_info_2);
@@ -4010,8 +4055,17 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 			ret = -EINVAL;
 			goto out;
 		}
+	}
 
-		target_svm->sev_es.snp_vmsa_gpa = svm->vmcb->control.exit_info_2;
+	switch (request) {
+	case SVM_VMGEXIT_AP_CREATE_ON_INIT:
+		/* Delay switching to the new VMSA */
+		kick = false;
+		fallthrough;
+	case SVM_VMGEXIT_AP_CREATE:
+		/* Switch to new VMSA on the next VMRUN */
+		target_svm->sev_es.snp_target_vmpl = vmpl;
+		vmpl_vmsa_gpa(target_svm, vmpl) = svm->vmcb->control.exit_info_2 & PAGE_MASK;
 		break;
 	case SVM_VMGEXIT_AP_DESTROY:
 		break;
@@ -4298,7 +4352,7 @@ static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 		gfn = get_ghcb_msr_bits(svm, GHCB_MSR_GPA_VALUE_MASK,
 					GHCB_MSR_GPA_VALUE_POS);
 
-		svm->sev_es.ghcb_registered_gpa = gfn_to_gpa(gfn);
+		svm->sev_es.ghcb_registered_gpa[cur_vmpl(svm)] = gfn_to_gpa(gfn);
 
 		set_ghcb_msr_bits(svm, gfn, GHCB_MSR_GPA_VALUE_MASK,
 				  GHCB_MSR_GPA_VALUE_POS);
@@ -4579,8 +4633,8 @@ static void sev_es_init_vmcb(struct vcpu_svm *svm)
 	 * the VMSA will be NULL if this vCPU is the destination for intrahost
 	 * migration, and will be copied later.
 	 */
-	if (svm->sev_es.vmsa && !svm->sev_es.snp_has_guest_vmsa)
-		svm->vmcb->control.vmsa_pa = __pa(svm->sev_es.vmsa);
+	if (cur_vmpl_vmsa(svm) && !cur_vmpl_has_guest_vmsa(svm))
+		svm->vmcb->control.vmsa_pa = __pa(cur_vmpl_vmsa(svm));
 
 	/* Can't intercept CR register access, HV can't modify CR registers */
 	svm_clr_intercept(svm, INTERCEPT_CR0_READ);
@@ -4643,16 +4697,30 @@ void sev_es_vcpu_reset(struct vcpu_svm *svm)
 {
 	struct kvm_vcpu *vcpu = &svm->vcpu;
 	struct kvm_sev_info *sev = &to_kvm_svm(vcpu->kvm)->sev_info;
+	unsigned int i;
+	u64 sev_info;
 
 	/*
 	 * Set the GHCB MSR value as per the GHCB specification when emulating
 	 * vCPU RESET for an SEV-ES guest.
 	 */
-	set_ghcb_msr(svm, GHCB_MSR_SEV_INFO((__u64)sev->ghcb_version,
-					    GHCB_VERSION_MIN,
-					    sev_enc_bit));
+	sev_info = GHCB_MSR_SEV_INFO((__u64)sev->ghcb_version, GHCB_VERSION_MIN,
+				     sev_enc_bit);
+	set_ghcb_msr(svm, sev_info);
+	svm->sev_es.ghcb_gpa[SVM_SEV_VMPL0] = sev_info;
 
 	mutex_init(&svm->sev_es.snp_vmsa_mutex);
+
+	/*
+	 * When not running under SNP, the "current VMPL" tracking for a guest
+	 * is always 0 and the base tracking of GPAs and SPAs will be as before
+	 * multiple VMPL support. However, under SNP, multiple VMPL levels can
+	 * be run, so initialize these values appropriately.
+	 */
+	for (i = 1; i < SVM_SEV_VMPL_MAX; i++) {
+		svm->sev_es.vmsa_info[i].hpa = INVALID_PAGE;
+		svm->sev_es.ghcb_gpa[i] = sev_info;
+	}
 }
 
 void sev_es_prepare_switch_to_guest(struct vcpu_svm *svm, struct sev_es_save_area *hostsa)
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index d6f252555ab3..ca4bc53fb14a 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -1463,8 +1463,10 @@ static int svm_vcpu_create(struct kvm_vcpu *vcpu)
 	svm->vmcb01.pa = __sme_set(page_to_pfn(vmcb01_page) << PAGE_SHIFT);
 	svm_switch_vmcb(svm, &svm->vmcb01);
 
-	if (vmsa_page)
-		svm->sev_es.vmsa = page_address(vmsa_page);
+	if (vmsa_page) {
+		vmpl_vmsa(svm, SVM_SEV_VMPL0) = page_address(vmsa_page);
+		vmpl_vmsa_hpa(svm, SVM_SEV_VMPL0) = __pa(page_address(vmsa_page));
+	}
 
 	svm->guest_state_loaded = false;
 
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 76107c7d0595..45a37d16b6f7 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -198,9 +198,39 @@ struct svm_nested_state {
 	bool force_msr_bitmap_recalc;
 };
 
-struct vcpu_sev_es_state {
-	/* SEV-ES support */
+#define vmpl_vmsa(s, v)				((s)->sev_es.vmsa_info[(v)].vmsa)
+#define vmpl_vmsa_gpa(s, v)			((s)->sev_es.vmsa_info[(v)].gpa)
+#define vmpl_vmsa_hpa(s, v)			((s)->sev_es.vmsa_info[(v)].hpa)
+#define vmpl_ap_waiting_for_reset(s, v)		((s)->sev_es.vmsa_info[(v)].ap_waiting_for_reset)
+#define vmpl_has_guest_vmsa(s, v)		((s)->sev_es.vmsa_info[(v)].has_guest_vmsa)
+
+#define cur_vmpl(s)				((s)->sev_es.snp_current_vmpl)
+#define cur_vmpl_vmsa(s)			vmpl_vmsa((s), cur_vmpl(s))
+#define cur_vmpl_vmsa_gpa(s)			vmpl_vmsa_gpa((s), cur_vmpl(s))
+#define cur_vmpl_vmsa_hpa(s)			vmpl_vmsa_hpa((s), cur_vmpl(s))
+#define cur_vmpl_ap_waiting_for_reset(s)	vmpl_ap_waiting_for_reset((s), cur_vmpl(s))
+#define cur_vmpl_has_guest_vmsa(s)		vmpl_has_guest_vmsa((s), cur_vmpl(s))
+
+#define tgt_vmpl(s)				((s)->sev_es.snp_target_vmpl)
+#define tgt_vmpl_vmsa(s)			vmpl_vmsa((s), tgt_vmpl(s))
+#define tgt_vmpl_vmsa_gpa(s)			vmpl_vmsa_gpa((s), tgt_vmpl(s))
+#define tgt_vmpl_vmsa_hpa(s)			vmpl_vmsa_hpa((s), tgt_vmpl(s))
+#define tgt_vmpl_ap_waiting_for_reset(s)	vmpl_ap_waiting_for_reset((s), tgt_vmpl(s))
+#define tgt_vmpl_has_guest_vmsa(s)		vmpl_has_guest_vmsa((s), tgt_vmpl(s))
+
+struct sev_vmsa_info {
+	/* SEV-ES and SEV-SNP */
 	struct sev_es_save_area *vmsa;
+
+	/* SEV-SNP for multi VMPL support */
+	gpa_t gpa;
+	hpa_t hpa;
+	bool  ap_waiting_for_reset;
+	bool  has_guest_vmsa;
+};
+
+struct vcpu_sev_es_state {
+	/* SEV-ES/SEV-SNP support */
 	struct ghcb *ghcb;
 	u8 valid_bitmap[16];
 	struct kvm_host_map ghcb_map;
@@ -219,12 +249,13 @@ struct vcpu_sev_es_state {
 	u16 psc_inflight;
 	bool psc_2m;
 
-	u64 ghcb_registered_gpa;
+	gpa_t ghcb_gpa[SVM_SEV_VMPL_MAX];
+	u64 ghcb_registered_gpa[SVM_SEV_VMPL_MAX];
+	struct sev_vmsa_info vmsa_info[SVM_SEV_VMPL_MAX];
 
 	struct mutex snp_vmsa_mutex; /* Used to handle concurrent updates of VMSA. */
-	gpa_t snp_vmsa_gpa;
-	bool snp_ap_waiting_for_reset;
-	bool snp_has_guest_vmsa;
+	unsigned int snp_current_vmpl;
+	unsigned int snp_target_vmpl;
 };
 
 struct vcpu_svm {
@@ -380,7 +411,7 @@ static __always_inline bool sev_snp_guest(struct kvm *kvm)
 
 static inline bool ghcb_gpa_is_registered(struct vcpu_svm *svm, u64 val)
 {
-	return svm->sev_es.ghcb_registered_gpa == val;
+	return svm->sev_es.ghcb_registered_gpa[cur_vmpl(svm)] == val;
 }
 
 static inline void vmcb_mark_all_dirty(struct vmcb *vmcb)
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index ef3d3511e4af..3efc3a89499c 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -11469,6 +11469,15 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		kvm_vcpu_block(vcpu);
 		kvm_vcpu_srcu_read_lock(vcpu);
 
+		/*
+		 * It is possible that the vCPU has never run before. If the
+		 * request is to update the protected guest state (AP Create),
+		 * then ensure that the vCPU can now run.
+		 */
+		if (kvm_test_request(KVM_REQ_UPDATE_PROTECTED_GUEST_STATE, vcpu) &&
+		    vcpu->arch.mp_state == KVM_MP_STATE_UNINITIALIZED)
+			vcpu->arch.mp_state = KVM_MP_STATE_RUNNABLE;
+
 		if (kvm_apic_accept_events(vcpu) < 0) {
 			r = 0;
 			goto out;

---

## [4] Tom Lendacky — 2024-08-27
*Subject: [RFC PATCH 3/7] KVM: SVM: Invoke a specified VMPL level VMSA for the vCPU*

Implement the SNP Run VMPL NAE event and MSR protocol to allow a guest to
request a different VMPL level VMSA be run for the vCPU. This allows the
guest to "call" an SVSM to process an SVSM request.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/asm/sev-common.h |   6 ++
 arch/x86/kvm/svm/sev.c            | 126 +++++++++++++++++++++++++++++-
 arch/x86/kvm/svm/svm.c            |  13 +++
 arch/x86/kvm/svm/svm.h            |  18 ++++-
 4 files changed, 158 insertions(+), 5 deletions(-)

diff --git a/arch/x86/include/asm/sev-common.h b/arch/x86/include/asm/sev-common.h
index d63c861ef91f..6f7134aada83 100644
--- a/arch/x86/include/asm/sev-common.h
+++ b/arch/x86/include/asm/sev-common.h
@@ -114,6 +114,8 @@ enum psc_op {
 
 /* GHCB Run at VMPL Request/Response */
 #define GHCB_MSR_VMPL_REQ		0x016
+#define GHCB_MSR_VMPL_LEVEL_POS		32
+#define GHCB_MSR_VMPL_LEVEL_MASK	GENMASK_ULL(7, 0)
 #define GHCB_MSR_VMPL_REQ_LEVEL(v)			\
 	/* GHCBData[39:32] */				\
 	(((u64)(v) & GENMASK_ULL(7, 0) << 32) |		\
@@ -121,6 +123,10 @@ enum psc_op {
 	GHCB_MSR_VMPL_REQ)
 
 #define GHCB_MSR_VMPL_RESP		0x017
+#define GHCB_MSR_VMPL_ERROR_POS		32
+#define GHCB_MSR_VMPL_ERROR_MASK	GENMASK_ULL(31, 0)
+#define GHCB_MSR_VMPL_RSVD_POS		12
+#define GHCB_MSR_VMPL_RSVD_MASK		GENMASK_ULL(19, 0)
 #define GHCB_MSR_VMPL_RESP_VAL(v)			\
 	/* GHCBData[63:32] */				\
 	(((u64)(v) & GENMASK_ULL(63, 32)) >> 32)
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index c22b6f51ec81..e0f5122061e6 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3421,6 +3421,10 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 		    control->exit_info_1 == control->exit_info_2)
 			goto vmgexit_err;
 		break;
+	case SVM_VMGEXIT_SNP_RUN_VMPL:
+		if (!sev_snp_guest(vcpu->kvm))
+			goto vmgexit_err;
+		break;
 	default:
 		reason = GHCB_ERR_INVALID_EVENT;
 		goto vmgexit_err;
@@ -3935,21 +3939,25 @@ static int __sev_snp_update_protected_guest_state(struct kvm_vcpu *vcpu)
 }
 
 /*
- * Invoked as part of svm_vcpu_reset() processing of an init event.
+ * Invoked as part of svm_vcpu_reset() processing of an init event
+ * or as part of switching to a new VMPL.
  */
-void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu)
+bool sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_svm *svm = to_svm(vcpu);
+	bool init = false;
 	int ret;
 
 	if (!sev_snp_guest(vcpu->kvm))
-		return;
+		return false;
 
 	mutex_lock(&svm->sev_es.snp_vmsa_mutex);
 
 	if (!tgt_vmpl_ap_waiting_for_reset(svm))
 		goto unlock;
 
+	init = true;
+
 	tgt_vmpl_ap_waiting_for_reset(svm) = false;
 
 	ret = __sev_snp_update_protected_guest_state(vcpu);
@@ -3958,6 +3966,8 @@ void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu)
 
 unlock:
 	mutex_unlock(&svm->sev_es.snp_vmsa_mutex);
+
+	return init;
 }
 
 static int sev_snp_ap_creation(struct vcpu_svm *svm)
@@ -4255,6 +4265,92 @@ static void sev_get_apic_ids(struct vcpu_svm *svm)
 	kvfree(desc);
 }
 
+static int __sev_run_vmpl_vmsa(struct vcpu_svm *svm, unsigned int new_vmpl)
+{
+	struct kvm_vcpu *vcpu = &svm->vcpu;
+	struct vmpl_switch_sa *old_vmpl_sa;
+	struct vmpl_switch_sa *new_vmpl_sa;
+	unsigned int old_vmpl;
+
+	if (new_vmpl >= SVM_SEV_VMPL_MAX)
+		return -EINVAL;
+	new_vmpl = array_index_nospec(new_vmpl, SVM_SEV_VMPL_MAX);
+
+	old_vmpl = svm->sev_es.snp_current_vmpl;
+	svm->sev_es.snp_target_vmpl = new_vmpl;
+
+	if (svm->sev_es.snp_target_vmpl == svm->sev_es.snp_current_vmpl ||
+	    sev_snp_init_protected_guest_state(vcpu))
+		return 0;
+
+	/* If the VMSA is not valid, return an error */
+	if (!VALID_PAGE(vmpl_vmsa_hpa(svm, new_vmpl)))
+		return -EINVAL;
+
+	/* Unmap the current GHCB */
+	sev_es_unmap_ghcb(svm);
+
+	/* Save some current VMCB values */
+	svm->sev_es.ghcb_gpa[old_vmpl]		= svm->vmcb->control.ghcb_gpa;
+
+	old_vmpl_sa = &svm->sev_es.vssa[old_vmpl];
+	old_vmpl_sa->int_state			= svm->vmcb->control.int_state;
+	old_vmpl_sa->exit_int_info		= svm->vmcb->control.exit_int_info;
+	old_vmpl_sa->exit_int_info_err		= svm->vmcb->control.exit_int_info_err;
+	old_vmpl_sa->cr0			= vcpu->arch.cr0;
+	old_vmpl_sa->cr2			= vcpu->arch.cr2;
+	old_vmpl_sa->cr4			= vcpu->arch.cr4;
+	old_vmpl_sa->cr8			= vcpu->arch.cr8;
+	old_vmpl_sa->efer			= vcpu->arch.efer;
+
+	/* Restore some previous VMCB values */
+	svm->vmcb->control.vmsa_pa		= vmpl_vmsa_hpa(svm, new_vmpl);
+	svm->vmcb->control.ghcb_gpa		= svm->sev_es.ghcb_gpa[new_vmpl];
+
+	new_vmpl_sa = &svm->sev_es.vssa[new_vmpl];
+	svm->vmcb->control.int_state		= new_vmpl_sa->int_state;
+	svm->vmcb->control.exit_int_info	= new_vmpl_sa->exit_int_info;
+	svm->vmcb->control.exit_int_info_err	= new_vmpl_sa->exit_int_info_err;
+	vcpu->arch.cr0				= new_vmpl_sa->cr0;
+	vcpu->arch.cr2				= new_vmpl_sa->cr2;
+	vcpu->arch.cr4				= new_vmpl_sa->cr4;
+	vcpu->arch.cr8				= new_vmpl_sa->cr8;
+	vcpu->arch.efer				= new_vmpl_sa->efer;
+
+	svm->sev_es.snp_current_vmpl = new_vmpl;
+
+	vmcb_mark_all_dirty(svm->vmcb);
+
+	return 0;
+}
+
+static void sev_run_vmpl_vmsa(struct vcpu_svm *svm)
+{
+	struct ghcb *ghcb = svm->sev_es.ghcb;
+	struct kvm_vcpu *vcpu = &svm->vcpu;
+	unsigned int vmpl;
+	int ret;
+
+	/* TODO: Does this need to be synced for original VMPL ... */
+	ghcb_set_sw_exit_info_1(ghcb, 0);
+	ghcb_set_sw_exit_info_2(ghcb, 0);
+
+	if (!sev_snp_guest(vcpu->kvm))
+		goto err;
+
+	vmpl = lower_32_bits(svm->vmcb->control.exit_info_1);
+
+	ret = __sev_run_vmpl_vmsa(svm, vmpl);
+	if (ret)
+		goto err;
+
+	return;
+
+err:
+	ghcb_set_sw_exit_info_1(ghcb, 2);
+	ghcb_set_sw_exit_info_2(ghcb, 0);
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4366,6 +4462,25 @@ static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 
 		ret = snp_begin_psc_msr(svm, control->ghcb_gpa);
 		break;
+	case GHCB_MSR_VMPL_REQ: {
+		unsigned int vmpl;
+
+		vmpl = get_ghcb_msr_bits(svm, GHCB_MSR_VMPL_LEVEL_MASK, GHCB_MSR_VMPL_LEVEL_POS);
+
+		/*
+		 * Set as successful in advance, since this value will be saved
+		 * as part of the VMPL switch and then restored if switching
+		 * back to the calling VMPL level.
+		 */
+		set_ghcb_msr_bits(svm, 0, GHCB_MSR_VMPL_ERROR_MASK, GHCB_MSR_VMPL_ERROR_POS);
+		set_ghcb_msr_bits(svm, 0, GHCB_MSR_VMPL_RSVD_MASK, GHCB_MSR_VMPL_RSVD_POS);
+		set_ghcb_msr_bits(svm, GHCB_MSR_VMPL_RESP, GHCB_MSR_INFO_MASK, GHCB_MSR_INFO_POS);
+
+		if (__sev_run_vmpl_vmsa(svm, vmpl))
+			set_ghcb_msr_bits(svm, 1, GHCB_MSR_VMPL_ERROR_MASK, GHCB_MSR_VMPL_ERROR_POS);
+
+		break;
+	}
 	case GHCB_MSR_TERM_REQ: {
 		u64 reason_set, reason_code;
 
@@ -4538,6 +4653,11 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 	case SVM_VMGEXIT_GET_APIC_IDS:
 		sev_get_apic_ids(svm);
 
+		ret = 1;
+		break;
+	case SVM_VMGEXIT_SNP_RUN_VMPL:
+		sev_run_vmpl_vmsa(svm);
+
 		ret = 1;
 		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index ca4bc53fb14a..586c26627bb1 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4253,6 +4253,19 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu,
 	}
 	vcpu->arch.regs_dirty = 0;
 
+	if (sev_snp_is_rinj_active(vcpu)) {
+		/*
+		 * When SEV-SNP is running with restricted injection, the V_IRQ
+		 * bit may be cleared on exit because virtual interrupt support
+		 * is ignored. To support multiple VMPLs, some of which may not
+		 * be running with restricted injection, ensure to reset the
+		 * V_IRQ bit if a virtual interrupt is meant to be active (the
+		 * virtual interrupt priority mask is non-zero).
+		 */
+		if (svm->vmcb->control.int_ctl & V_INTR_PRIO_MASK)
+			svm->vmcb->control.int_ctl |= V_IRQ_MASK;
+	}
+
 	if (unlikely(svm->vmcb->control.exit_code == SVM_EXIT_NMI))
 		kvm_before_interrupt(vcpu, KVM_HANDLING_NMI);
 
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 45a37d16b6f7..d1ef349556f7 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -198,6 +198,18 @@ struct svm_nested_state {
 	bool force_msr_bitmap_recalc;
 };
 
+struct vmpl_switch_sa {
+	u32 int_state;
+	u32 exit_int_info;
+	u32 exit_int_info_err;
+
+	unsigned long cr0;
+	unsigned long cr2;
+	unsigned long cr4;
+	unsigned long cr8;
+	u64 efer;
+};
+
 #define vmpl_vmsa(s, v)				((s)->sev_es.vmsa_info[(v)].vmsa)
 #define vmpl_vmsa_gpa(s, v)			((s)->sev_es.vmsa_info[(v)].gpa)
 #define vmpl_vmsa_hpa(s, v)			((s)->sev_es.vmsa_info[(v)].hpa)
@@ -256,6 +268,8 @@ struct vcpu_sev_es_state {
 	struct mutex snp_vmsa_mutex; /* Used to handle concurrent updates of VMSA. */
 	unsigned int snp_current_vmpl;
 	unsigned int snp_target_vmpl;
+
+	struct vmpl_switch_sa vssa[SVM_SEV_VMPL_MAX];
 };
 
 struct vcpu_svm {
@@ -776,7 +790,7 @@ int sev_cpu_init(struct svm_cpu_data *sd);
 int sev_dev_get_attr(u32 group, u64 attr, u64 *val);
 extern unsigned int max_sev_asid;
 void sev_handle_rmp_fault(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code);
-void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu);
+bool sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu);
 int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 void sev_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn);
@@ -800,7 +814,7 @@ static inline int sev_cpu_init(struct svm_cpu_data *sd) { return 0; }
 static inline int sev_dev_get_attr(u32 group, u64 attr, u64 *val) { return -ENXIO; }
 #define max_sev_asid 0
 static inline void sev_handle_rmp_fault(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code) {}
-static inline void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu) {}
+static inline bool sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu) { return false; }
 static inline int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order)
 {
 	return 0;

---

## [5] Tom Lendacky — 2024-08-27
*Subject: [RFC PATCH 4/7] KVM: SVM: Maintain per-VMPL SEV features in kvm_sev_info*

From: Carlos Bilbao <carlos.bilbao@amd.com>

Make struct kvm_sev_info maintain separate SEV features per VMPL, allowing
distinct SEV features depending on VMs privilege level.

Signed-off-by: Carlos Bilbao <carlos.bilbao@amd.com>
Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/kvm/svm/sev.c | 22 +++++++++++++++-------
 arch/x86/kvm/svm/svm.h |  4 ++--
 2 files changed, 17 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index e0f5122061e6..c6c9306c86ef 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -144,7 +144,7 @@ static bool sev_vcpu_has_debug_swap(struct vcpu_svm *svm)
 	struct kvm_vcpu *vcpu = &svm->vcpu;
 	struct kvm_sev_info *sev = &to_kvm_svm(vcpu->kvm)->sev_info;
 
-	return sev->vmsa_features & SVM_SEV_FEAT_DEBUG_SWAP;
+	return sev->vmsa_features[cur_vmpl(svm)] & SVM_SEV_FEAT_DEBUG_SWAP;
 }
 
 /* Must be called with the sev_bitmap_lock held */
@@ -428,7 +428,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 
 	sev->active = true;
 	sev->es_active = es_active;
-	sev->vmsa_features = data->vmsa_features;
+	sev->vmsa_features[SVM_SEV_VMPL0] = data->vmsa_features;
 	sev->ghcb_version = data->ghcb_version;
 
 	/*
@@ -440,7 +440,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 		sev->ghcb_version = GHCB_VERSION_DEFAULT;
 
 	if (vm_type == KVM_X86_SNP_VM)
-		sev->vmsa_features |= SVM_SEV_FEAT_SNP_ACTIVE;
+		sev->vmsa_features[SVM_SEV_VMPL0] |= SVM_SEV_FEAT_SNP_ACTIVE;
 
 	ret = sev_asid_new(sev);
 	if (ret)
@@ -468,7 +468,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	sev_asid_free(sev);
 	sev->asid = 0;
 e_no_asid:
-	sev->vmsa_features = 0;
+	sev->vmsa_features[SVM_SEV_VMPL0] = 0;
 	sev->es_active = false;
 	sev->active = false;
 	return ret;
@@ -852,7 +852,7 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 	save->xss  = svm->vcpu.arch.ia32_xss;
 	save->dr6  = svm->vcpu.arch.dr6;
 
-	save->sev_features = sev->vmsa_features;
+	save->sev_features = sev->vmsa_features[SVM_SEV_VMPL0];
 
 	/*
 	 * Skip FPU and AVX setup with KVM_SEV_ES_INIT to avoid
@@ -1985,7 +1985,7 @@ static void sev_migrate_from(struct kvm *dst_kvm, struct kvm *src_kvm)
 	dst->pages_locked = src->pages_locked;
 	dst->enc_context_owner = src->enc_context_owner;
 	dst->es_active = src->es_active;
-	dst->vmsa_features = src->vmsa_features;
+	memcpy(dst->vmsa_features, src->vmsa_features, sizeof(dst->vmsa_features));
 
 	src->asid = 0;
 	src->active = false;
@@ -4034,8 +4034,16 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 
 		/* Interrupt injection mode shouldn't change for AP creation */
 		sev_features = vcpu->arch.regs[VCPU_REGS_RAX];
-		sev_features ^= sev->vmsa_features;
 
+		/*
+		 * The SNPActive feature must at least be set. If the SEV
+		 * features of this AP are zero, this is the first vCPU created at
+		 * this VMPL.
+		 */
+		if (!sev->vmsa_features[vmpl])
+			sev->vmsa_features[vmpl] = sev_features | SVM_SEV_FEAT_SNP_ACTIVE;
+
+		sev_features ^= sev->vmsa_features[vmpl];
 		if (sev_features & SVM_SEV_FEAT_INT_INJ_MODES) {
 			vcpu_unimpl(vcpu, "vmgexit: invalid AP injection mode [%#lx] from guest\n",
 				    vcpu->arch.regs[VCPU_REGS_RAX]);
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index d1ef349556f7..55f1f6ffb871 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -87,7 +87,7 @@ struct kvm_sev_info {
 	unsigned long pages_locked; /* Number of pages locked */
 	struct list_head regions_list;  /* List of registered regions */
 	u64 ap_jump_table;	/* SEV-ES AP Jump Table address */
-	u64 vmsa_features;
+	u64 vmsa_features[SVM_SEV_VMPL_MAX];
 	u16 ghcb_version;	/* Highest guest GHCB protocol version allowed */
 	struct kvm *enc_context_owner; /* Owner of copied encryption context */
 	struct list_head mirror_vms; /* List of VMs mirroring */
@@ -416,7 +416,7 @@ static __always_inline bool sev_snp_guest(struct kvm *kvm)
 #ifdef CONFIG_KVM_AMD_SEV
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
 
-	return (sev->vmsa_features & SVM_SEV_FEAT_SNP_ACTIVE) &&
+	return (sev->vmsa_features[SVM_SEV_VMPL0] & SVM_SEV_FEAT_SNP_ACTIVE) &&
 	       !WARN_ON_ONCE(!sev_es_guest(kvm));
 #else
 	return false;

---

## [6] Tom Lendacky — 2024-08-27
*Subject: [RFC PATCH 5/7] KVM: SVM: Prevent injection when restricted injection is active*

Prevent injection of exceptions/interrupts when restricted injection is
active. This is not full support for restricted injection, but the SVSM
is not expecting any injections at all.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/kvm/svm/sev.c | 30 ++++++++++++++++++++++++++++++
 arch/x86/kvm/svm/svm.c |  6 ++++++
 arch/x86/kvm/svm/svm.h |  3 +++
 3 files changed, 39 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index c6c9306c86ef..4324a72d35ea 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -5227,3 +5227,33 @@ int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn)
 
 	return level;
 }
+
+bool sev_snp_is_rinj_active(struct kvm_vcpu *vcpu)
+{
+	struct kvm_sev_info *sev;
+	int vmpl;
+
+	if (!sev_snp_guest(vcpu->kvm))
+		return false;
+
+	sev = &to_kvm_svm(vcpu->kvm)->sev_info;
+	vmpl = to_svm(vcpu)->sev_es.snp_current_vmpl;
+
+	return sev->vmsa_features[vmpl] & SVM_SEV_FEAT_RESTRICTED_INJECTION;
+}
+
+bool sev_snp_nmi_blocked(struct kvm_vcpu *vcpu)
+{
+	WARN_ON_ONCE(!sev_snp_is_rinj_active(vcpu));
+
+	/* NMIs are blocked when restricted injection is active */
+	return true;
+}
+
+bool sev_snp_interrupt_blocked(struct kvm_vcpu *vcpu)
+{
+	WARN_ON_ONCE(!sev_snp_is_rinj_active(vcpu));
+
+	/* Interrupts are blocked when restricted injection is active */
+	return true;
+}
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 586c26627bb1..632c74cb41f4 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -3780,6 +3780,9 @@ bool svm_nmi_blocked(struct kvm_vcpu *vcpu)
 	if (!gif_set(svm))
 		return true;
 
+	if (sev_snp_is_rinj_active(vcpu))
+		return sev_snp_nmi_blocked(vcpu);
+
 	if (is_guest_mode(vcpu) && nested_exit_on_nmi(svm))
 		return false;
 
@@ -3812,6 +3815,9 @@ bool svm_interrupt_blocked(struct kvm_vcpu *vcpu)
 	if (!gif_set(svm))
 		return true;
 
+	if (sev_snp_is_rinj_active(vcpu))
+		return sev_snp_interrupt_blocked(vcpu);
+
 	if (is_guest_mode(vcpu)) {
 		/* As long as interrupts are being delivered...  */
 		if ((svm->nested.ctl.int_ctl & V_INTR_MASKING_MASK)
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 55f1f6ffb871..029eb54a8472 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -761,6 +761,9 @@ void sev_es_vcpu_reset(struct vcpu_svm *svm);
 void sev_vcpu_deliver_sipi_vector(struct kvm_vcpu *vcpu, u8 vector);
 void sev_es_prepare_switch_to_guest(struct vcpu_svm *svm, struct sev_es_save_area *hostsa);
 void sev_es_unmap_ghcb(struct vcpu_svm *svm);
+bool sev_snp_is_rinj_active(struct kvm_vcpu *vcpu);
+bool sev_snp_nmi_blocked(struct kvm_vcpu *vcpu);
+bool sev_snp_interrupt_blocked(struct kvm_vcpu *vcpu);
 
 #ifdef CONFIG_KVM_AMD_SEV
 int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp);

---

## [7] Tom Lendacky — 2024-08-27
*Subject: [RFC PATCH 6/7] KVM: SVM: Support launching an SVSM with Restricted Injection set*

Allow Restricted Injection to be set in SEV_FEATURES. When set,
attempts to inject any interrupts other than #HV will make VMRUN fail.
This is done to further reduce the security exposure within the SVSM.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/kvm/svm/sev.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 4324a72d35ea..3aa9489786ee 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3078,6 +3078,7 @@ void __init sev_hardware_setup(void)
 		sev_es_debug_swap_enabled = false;
 
 	sev_supported_vmsa_features = 0;
+	sev_supported_vmsa_features |= SVM_SEV_FEAT_RESTRICTED_INJECTION;
 	if (sev_es_debug_swap_enabled)
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
 }

---

## [8] Tom Lendacky — 2024-08-27
*Subject: [RFC PATCH 7/7] KVM: SVM: Support initialization of an SVSM*

Allow for setting VMPL permission as part of the launch sequence and
ssing an SNP init flag, limit measuring of the guest vCPUs, to just the
BSP.

Indicate full multi-VMPL support to the guest through the GHCB feature
bitmap.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/uapi/asm/kvm.h |  10 +++
 arch/x86/kvm/svm/sev.c          | 123 ++++++++++++++++++++++++--------
 arch/x86/kvm/svm/svm.h          |   1 +
 include/uapi/linux/kvm.h        |   3 +
 4 files changed, 107 insertions(+), 30 deletions(-)

diff --git a/arch/x86/include/uapi/asm/kvm.h b/arch/x86/include/uapi/asm/kvm.h
index bf57a824f722..c60557bb4253 100644
--- a/arch/x86/include/uapi/asm/kvm.h
+++ b/arch/x86/include/uapi/asm/kvm.h
@@ -465,6 +465,7 @@ struct kvm_sync_regs {
 /* vendor-specific groups and attributes for system fd */
 #define KVM_X86_GRP_SEV			1
 #  define KVM_X86_SEV_VMSA_FEATURES	0
+#  define KVM_X86_SEV_SNP_INIT_FLAGS	1
 
 struct kvm_vmx_nested_state_data {
 	__u8 vmcs12[KVM_STATE_NESTED_VMX_VMCS_SIZE];
@@ -703,6 +704,8 @@ enum sev_cmd_id {
 	KVM_SEV_SNP_LAUNCH_UPDATE,
 	KVM_SEV_SNP_LAUNCH_FINISH,
 
+	KVM_SEV_SNP_LAUNCH_UPDATE_VMPLS,
+
 	KVM_SEV_NR_MAX,
 };
 
@@ -856,6 +859,13 @@ struct kvm_sev_snp_launch_update {
 	__u64 pad2[4];
 };
 
+struct kvm_sev_snp_launch_update_vmpls {
+	struct kvm_sev_snp_launch_update lu;
+	__u8 vmpl3_perms;
+	__u8 vmpl2_perms;
+	__u8 vmpl1_perms;
+};
+
 #define KVM_SEV_SNP_ID_BLOCK_SIZE	96
 #define KVM_SEV_SNP_ID_AUTH_SIZE	4096
 #define KVM_SEV_SNP_FINISH_DATA_SIZE	32
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 3aa9489786ee..25d5fe0dab5a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -41,7 +41,10 @@
 
 #define GHCB_HV_FT_SUPPORTED	(GHCB_HV_FT_SNP			| \
 				 GHCB_HV_FT_SNP_AP_CREATION	| \
-				 GHCB_HV_FT_APIC_ID_LIST)
+				 GHCB_HV_FT_APIC_ID_LIST	| \
+				 GHCB_HV_FT_SNP_MULTI_VMPL)
+
+#define SNP_SUPPORTED_INIT_FLAGS	KVM_SEV_SNP_SVSM
 
 /* enable/disable SEV support */
 static bool sev_enabled = true;
@@ -329,6 +332,12 @@ static void sev_unbind_asid(struct kvm *kvm, unsigned int handle)
 	sev_decommission(handle);
 }
 
+static bool verify_init_flags(struct kvm_sev_init *data, unsigned long vm_type)
+{
+	return (vm_type != KVM_X86_SNP_VM) ? !data->flags
+					   : !(data->flags & ~SNP_SUPPORTED_INIT_FLAGS);
+}
+
 /*
  * This sets up bounce buffers/firmware pages to handle SNP Guest Request
  * messages (e.g. attestation requests). See "SNP Guest Request" in the GHCB
@@ -414,7 +423,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	if (kvm->created_vcpus)
 		return -EINVAL;
 
-	if (data->flags)
+	if (!verify_init_flags(data, vm_type))
 		return -EINVAL;
 
 	if (data->vmsa_features & ~valid_vmsa_features)
@@ -430,6 +439,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	sev->es_active = es_active;
 	sev->vmsa_features[SVM_SEV_VMPL0] = data->vmsa_features;
 	sev->ghcb_version = data->ghcb_version;
+	sev->snp_init_flags = data->flags;
 
 	/*
 	 * Currently KVM supports the full range of mandatory features defined
@@ -468,6 +478,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	sev_asid_free(sev);
 	sev->asid = 0;
 e_no_asid:
+	sev->snp_init_flags = 0;
 	sev->vmsa_features[SVM_SEV_VMPL0] = 0;
 	sev->es_active = false;
 	sev->active = false;
@@ -2152,7 +2163,9 @@ int sev_dev_get_attr(u32 group, u64 attr, u64 *val)
 	case KVM_X86_SEV_VMSA_FEATURES:
 		*val = sev_supported_vmsa_features;
 		return 0;
-
+	case KVM_X86_SEV_SNP_INIT_FLAGS:
+		*val = SNP_SUPPORTED_INIT_FLAGS;
+		return 0;
 	default:
 		return -ENXIO;
 	}
@@ -2260,6 +2273,9 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 
 struct sev_gmem_populate_args {
 	__u8 type;
+	__u8 vmpl1_perms;
+	__u8 vmpl2_perms;
+	__u8 vmpl3_perms;
 	int sev_fd;
 	int fw_error;
 };
@@ -2309,6 +2325,9 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 		fw_args.address = __sme_set(pfn_to_hpa(pfn + i));
 		fw_args.page_size = PG_LEVEL_TO_RMP(PG_LEVEL_4K);
 		fw_args.page_type = sev_populate_args->type;
+		fw_args.vmpl1_perms = sev_populate_args->vmpl1_perms;
+		fw_args.vmpl2_perms = sev_populate_args->vmpl2_perms;
+		fw_args.vmpl3_perms = sev_populate_args->vmpl3_perms;
 
 		ret = __sev_issue_cmd(sev_populate_args->sev_fd, SEV_CMD_SNP_LAUNCH_UPDATE,
 				      &fw_args, &sev_populate_args->fw_error);
@@ -2355,34 +2374,27 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 	return ret;
 }
 
-static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
+static int __snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp,
+			       struct kvm_sev_snp_launch_update_vmpls *params)
 {
-	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
 	struct sev_gmem_populate_args sev_populate_args = {0};
-	struct kvm_sev_snp_launch_update params;
 	struct kvm_memory_slot *memslot;
 	long npages, count;
 	void __user *src;
 	int ret = 0;
 
-	if (!sev_snp_guest(kvm) || !sev->snp_context)
-		return -EINVAL;
-
-	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
-		return -EFAULT;
-
 	pr_debug("%s: GFN start 0x%llx length 0x%llx type %d flags %d\n", __func__,
-		 params.gfn_start, params.len, params.type, params.flags);
+		 params->lu.gfn_start, params->lu.len, params->lu.type, params->lu.flags);
 
-	if (!PAGE_ALIGNED(params.len) || params.flags ||
-	    (params.type != KVM_SEV_SNP_PAGE_TYPE_NORMAL &&
-	     params.type != KVM_SEV_SNP_PAGE_TYPE_ZERO &&
-	     params.type != KVM_SEV_SNP_PAGE_TYPE_UNMEASURED &&
-	     params.type != KVM_SEV_SNP_PAGE_TYPE_SECRETS &&
-	     params.type != KVM_SEV_SNP_PAGE_TYPE_CPUID))
+	if (!PAGE_ALIGNED(params->lu.len) || params->lu.flags ||
+	    (params->lu.type != KVM_SEV_SNP_PAGE_TYPE_NORMAL &&
+	     params->lu.type != KVM_SEV_SNP_PAGE_TYPE_ZERO &&
+	     params->lu.type != KVM_SEV_SNP_PAGE_TYPE_UNMEASURED &&
+	     params->lu.type != KVM_SEV_SNP_PAGE_TYPE_SECRETS &&
+	     params->lu.type != KVM_SEV_SNP_PAGE_TYPE_CPUID))
 		return -EINVAL;
 
-	npages = params.len / PAGE_SIZE;
+	npages = params->lu.len / PAGE_SIZE;
 
 	/*
 	 * For each GFN that's being prepared as part of the initial guest
@@ -2405,17 +2417,20 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	 */
 	mutex_lock(&kvm->slots_lock);
 
-	memslot = gfn_to_memslot(kvm, params.gfn_start);
+	memslot = gfn_to_memslot(kvm, params->lu.gfn_start);
 	if (!kvm_slot_can_be_private(memslot)) {
 		ret = -EINVAL;
 		goto out;
 	}
 
 	sev_populate_args.sev_fd = argp->sev_fd;
-	sev_populate_args.type = params.type;
-	src = params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO ? NULL : u64_to_user_ptr(params.uaddr);
+	sev_populate_args.type = params->lu.type;
+	sev_populate_args.vmpl1_perms = params->vmpl1_perms;
+	sev_populate_args.vmpl2_perms = params->vmpl2_perms;
+	sev_populate_args.vmpl3_perms = params->vmpl3_perms;
+	src = params->lu.type == KVM_SEV_SNP_PAGE_TYPE_ZERO ? NULL : u64_to_user_ptr(params->lu.uaddr);
 
-	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages,
+	count = kvm_gmem_populate(kvm, params->lu.gfn_start, src, npages,
 				  sev_gmem_post_populate, &sev_populate_args);
 	if (count < 0) {
 		argp->error = sev_populate_args.fw_error;
@@ -2423,13 +2438,16 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 			 __func__, count, argp->error);
 		ret = -EIO;
 	} else {
-		params.gfn_start += count;
-		params.len -= count * PAGE_SIZE;
-		if (params.type != KVM_SEV_SNP_PAGE_TYPE_ZERO)
-			params.uaddr += count * PAGE_SIZE;
+		params->lu.gfn_start += count;
+		params->lu.len -= count * PAGE_SIZE;
+		if (params->lu.type != KVM_SEV_SNP_PAGE_TYPE_ZERO)
+			params->lu.uaddr += count * PAGE_SIZE;
 
 		ret = 0;
-		if (copy_to_user(u64_to_user_ptr(argp->data), &params, sizeof(params)))
+
+		/* Only copy the original LAUNCH_UPDATE area back */
+		if (copy_to_user(u64_to_user_ptr(argp->data), params,
+				 sizeof(struct kvm_sev_snp_launch_update)))
 			ret = -EFAULT;
 	}
 
@@ -2439,6 +2457,40 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return ret;
 }
 
+static int snp_launch_update_vmpls(struct kvm *kvm, struct kvm_sev_cmd *argp)
+{
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
+	struct kvm_sev_snp_launch_update_vmpls params;
+
+	if (!sev_snp_guest(kvm) || !sev->snp_context)
+		return -EINVAL;
+
+	if (copy_from_user(&params, (void __user *)(uintptr_t)argp->data, sizeof(params)))
+		return -EFAULT;
+
+	return __snp_launch_update(kvm, argp, &params);
+}
+
+static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
+{
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
+	struct kvm_sev_snp_launch_update_vmpls params;
+
+	if (!sev_snp_guest(kvm) || !sev->snp_context)
+		return -EINVAL;
+
+	/* Copy only the kvm_sev_snp_launch_update portion */
+	if (copy_from_user(&params, (void __user *)(uintptr_t)argp->data,
+			   sizeof(struct kvm_sev_snp_launch_update)))
+		return -EFAULT;
+
+	params.vmpl1_perms = 0;
+	params.vmpl2_perms = 0;
+	params.vmpl3_perms = 0;
+
+	return __snp_launch_update(kvm, argp, &params);
+}
+
 static int snp_launch_update_vmsa(struct kvm *kvm, struct kvm_sev_cmd *argp)
 {
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
@@ -2454,6 +2506,10 @@ static int snp_launch_update_vmsa(struct kvm *kvm, struct kvm_sev_cmd *argp)
 		struct vcpu_svm *svm = to_svm(vcpu);
 		u64 pfn = __pa(vmpl_vmsa(svm, SVM_SEV_VMPL0)) >> PAGE_SHIFT;
 
+		/* If SVSM support is requested, only measure the boot vCPU */
+		if ((sev->snp_init_flags & KVM_SEV_SNP_SVSM) && vcpu->vcpu_id != 0)
+			continue;
+
 		ret = sev_es_sync_vmsa(svm);
 		if (ret)
 			return ret;
@@ -2482,6 +2538,10 @@ static int snp_launch_update_vmsa(struct kvm *kvm, struct kvm_sev_cmd *argp)
 		 * MSR_IA32_DEBUGCTLMSR when guest_state_protected is not set.
 		 */
 		svm_enable_lbrv(vcpu);
+
+		/* If SVSM support is requested, no more vCPUs are measured. */
+		if (sev->snp_init_flags & KVM_SEV_SNP_SVSM)
+			break;
 	}
 
 	return 0;
@@ -2507,7 +2567,7 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (params.flags)
 		return -EINVAL;
 
-	/* Measure all vCPUs using LAUNCH_UPDATE before finalizing the launch flow. */
+	/* Measure vCPUs using LAUNCH_UPDATE before we finalize the launch flow. */
 	ret = snp_launch_update_vmsa(kvm, argp);
 	if (ret)
 		return ret;
@@ -2665,6 +2725,9 @@ int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 	case KVM_SEV_SNP_LAUNCH_UPDATE:
 		r = snp_launch_update(kvm, &sev_cmd);
 		break;
+	case KVM_SEV_SNP_LAUNCH_UPDATE_VMPLS:
+		r = snp_launch_update_vmpls(kvm, &sev_cmd);
+		break;
 	case KVM_SEV_SNP_LAUNCH_FINISH:
 		r = snp_launch_finish(kvm, &sev_cmd);
 		break;
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 029eb54a8472..97a1b1b4cb5f 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -98,6 +98,7 @@ struct kvm_sev_info {
 	void *guest_req_buf;    /* Bounce buffer for SNP Guest Request input */
 	void *guest_resp_buf;   /* Bounce buffer for SNP Guest Request output */
 	struct mutex guest_req_mutex; /* Must acquire before using bounce buffers */
+	unsigned int snp_init_flags;
 };
 
 struct kvm_svm {
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 637efc055145..49833912432a 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -1399,6 +1399,9 @@ struct kvm_enc_region {
 #define KVM_GET_SREGS2             _IOR(KVMIO,  0xcc, struct kvm_sregs2)
 #define KVM_SET_SREGS2             _IOW(KVMIO,  0xcd, struct kvm_sregs2)
 
+/* Enable SVSM support */
+#define KVM_SEV_SNP_SVSM			(1 << 0)
+
 #define KVM_DIRTY_LOG_MANUAL_PROTECT_ENABLE    (1 << 0)
 #define KVM_DIRTY_LOG_INITIALLY_SET            (1 << 1)

---

## [9] Borislav Petkov — 2024-11-28
*Subject: Re: [RFC PATCH 1/7] KVM: SVM: Implement GET_AP_APIC_IDS NAE event*

On Tue, Aug 27, 2024 at 04:59:25PM -0500, Tom Lendacky wrote:
> @@ -4124,6 +4130,77 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
>  	return 1; /* resume guest */

"count" - like in the spec. :-P

> +	u32	apic_ids[];
> +};

Probably should be "num_pages" and a comment should explain what it is:

"State to Hypervisor: is the
number of guest contiguous pages
provided to hold the list of APIC
IDs"

Makes it much easier to follow the code.

> +	/* Each APIC ID is 32-bits in size, so make sure there is room */
> +	n = atomic_read(&kvm->online_vcpus);

It doesn't look like it but if you wanna be real paranoid you can slap
a WARN_ONCE() here or so to scream loudly.

> +	id_desc_size = sizeof(*desc);
> +	id_desc_size += n * sizeof(desc->apic_ids[0]);

Uuh, more magic numbers. I guess we need this:

https://lore.kernel.org/r/20241113204425.889854-1-huibo.wang@amd.com

and more.

And can we write those only once at the end of the function?

> +	if (!page_address_valid(vcpu, gpa))
> +		return;

Looking at the tree, that gfn_to_pfn() thing is gone now and we're supposed to
it this way.  Not tested ofc:

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 5af227ba15a3..47e1f72a574d 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4134,7 +4134,7 @@ static void sev_get_apic_ids(struct vcpu_svm *svm)
 	struct kvm *kvm = vcpu->kvm;
 	unsigned int id_desc_size;
 	struct sev_apic_id_desc *desc;
-	kvm_pfn_t pfn;
+	struct page *page;
 	gpa_t gpa;
 	u64 pages;
 	unsigned long i;
@@ -4163,8 +4163,8 @@ static void sev_get_apic_ids(struct vcpu_svm *svm)
 	if (!page_address_valid(vcpu, gpa))
 		return;
 
-	pfn = gfn_to_pfn(kvm, gpa_to_gfn(gpa));
-	if (is_error_noslot_pfn(pfn))
+	page = gfn_to_page(kvm, gpa_to_gfn(gpa));
+	if (!page)
 		return;
 
 	if (!pages)

> +	if (is_error_noslot_pfn(pfn))
> +		return;

That test needs to go right under the assignment of "pages".

> +	/* Allocate a buffer to hold the APIC IDs */
> +	desc = kvzalloc(id_desc_size, GFP_KERNEL_ACCOUNT);

Well:

#define kvm_for_each_vcpu(idx, vcpup, kvm)                 \
        xa_for_each_range(&kvm->vcpu_array, idx, vcpup, 0, \
                          (atomic_read(&kvm->online_vcpus) - 1))
			   ^^^^^^^^^^^^^^

but, what's stopping kvm_vm_ioctl_create_vcpu() from incrementing it?

I'm guessing this would happen when you start the guest only but I haz no
idea.

> +		if (i > n)
> +			break;

---
