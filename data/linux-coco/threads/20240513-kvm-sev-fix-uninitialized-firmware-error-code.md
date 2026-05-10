---
title: 'KVM: SEV: Fix uninitialized firmware error code'
date: 2024-05-13
last_reply: 2024-05-15
message_count: 2
participants: ['Michael Roth', 'Nathan Chancellor']
---

## [1] Michael Roth — 2024-05-13

The current code triggers a clang warning due to passing back an
uninitialized firmware return code in cases where an attestation request
is aborted before getting sent to userspace. Since firmware has not been
involved at this point the appropriate value is 0.

Reported-by: Nathan Chancellor <nathan@kernel.org>
Closes: https://lore.kernel.org/kvm/20240513151920.GA3061950@thelio-3990X/
Fixes: 32fde9e18b3f ("KVM: SEV: Provide support for SNP_EXTENDED_GUEST_REQUEST NAE event")
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c | 3 +--
 1 file changed, 1 insertion(+), 2 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 57c2c8025547..59c0d89a4d52 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4048,7 +4048,6 @@ static int snp_begin_ext_guest_req(struct kvm_vcpu *vcpu)
 	int vmm_ret = SNP_GUEST_VMM_ERR_GENERIC;
 	struct vcpu_svm *svm = to_svm(vcpu);
 	unsigned long data_npages;
-	sev_ret_code fw_err;
 	gpa_t data_gpa;
 
 	if (!sev_snp_guest(vcpu->kvm))
@@ -4075,7 +4074,7 @@ static int snp_begin_ext_guest_req(struct kvm_vcpu *vcpu)
 	return 0; /* forward request to userspace */
 
 abort_request:
-	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(vmm_ret, fw_err));
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(vmm_ret, 0));
 	return 1; /* resume guest */
 }

---

## [2] Nathan Chancellor — 2024-05-15
*Subject: Re: [PATCH] KVM: SEV: Fix uninitialized firmware error code*

On Mon, May 13, 2024 at 12:27:04PM -0500, Michael Roth wrote:
> The current code triggers a clang warning due to passing back an
> uninitialized firmware return code in cases where an attestation request

This obviously resolves the warning:

Tested-by: Nathan Chancellor <nathan@kernel.org> # build

> ---
>  arch/x86/kvm/svm/sev.c | 3 +--

---
