---
title: 'Extend KVM_HC_MAP_GPA_RANGE api to allow retry'
date: 2026-03-05
last_reply: 2026-05-29
message_count: 4
participants: ['Sagi Shahar', 'Sean Christopherson']
---

## [1] Sagi Shahar — 2026-03-05

In some cases, userspace might decide to split MAP_GPA requests and
retry them the next time the guest runs. One common case is MAP_GPA
requests received right before intrahost migration when userspace
might decide to complete the request after the migration is complete
to reduce blackout time.

This is v4 of the series.

Changes from v3[1]:
 * Rebased on top of v7.0-rc2.
 * Switch "if" statement to switch-case in tdx_complete_vmcall_map_gpa()
   as suggested by Michael Roth.

[1] https://lore.kernel.org/lkml/20260206222829.3758171-1-sagis@google.com/

Sagi Shahar (1):
  KVM: SEV: Restrict userspace return codes for KVM_HC_MAP_GPA_RANGE

Vishal Annapurve (1):
  KVM: TDX: Allow userspace to return errors to guest for MAPGPA

 Documentation/virt/kvm/api.rst |  3 +++
 arch/x86/kvm/svm/sev.c         | 12 ++++++++++--
 arch/x86/kvm/vmx/tdx.c         | 28 +++++++++++++++++++++-------
 arch/x86/kvm/x86.h             |  6 ++++++
 4 files changed, 40 insertions(+), 9 deletions(-)

---

## [2] Sagi Shahar — 2026-03-05
*Subject: [PATCH v4 1/2] KVM: TDX: Allow userspace to return errors to guest
 for MAPGPA*

From: Vishal Annapurve <vannapurve@google.com>

MAPGPA request from TDX VMs gets split into chunks by KVM using a loop
of userspace exits until the complete range is handled.

In some cases userspace VMM might decide to break the MAPGPA operation
and continue it later. For example: in the case of intrahost migration
userspace might decide to continue the MAPGPA operation after the
migration is completed.

Allow userspace to signal to TDX guests that the MAPGPA operation should
be retried the next time the guest is scheduled.

This is potentially a breaking change since if userspace sets
hypercall.ret to a value other than EBUSY or EINVAL an EINVAL error code
will be returned to userspace. As of now QEMU never sets hypercall.ret
to a non-zero value after handling KVM_EXIT_HYPERCALL so this change
should be safe.

Reviewed-by: Michael Roth <michael.roth@amd.com>
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
---
 Documentation/virt/kvm/api.rst |  3 +++
 arch/x86/kvm/vmx/tdx.c         | 28 +++++++++++++++++++++-------
 arch/x86/kvm/x86.h             |  6 ++++++
 3 files changed, 30 insertions(+), 7 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 6f85e1b321dd..027f7fadd757 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -8808,6 +8808,9 @@ block sizes is exposed in KVM_CAP_ARM_SUPPORTED_BLOCK_SIZES as a
 
 This capability, if enabled, will cause KVM to exit to userspace
 with KVM_EXIT_HYPERCALL exit reason to process some hypercalls.
+Userspace may fail the hypercall by setting hypercall.ret to EINVAL
+or may request the hypercall to be retried the next time the guest run
+by setting hypercall.ret to EAGAIN.
 
 Calling KVM_CHECK_EXTENSION for this capability will return a bitmask
 of hypercalls that can be configured to exit to userspace.
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c5065f84b78b..f47d5e34f3fc 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1186,12 +1186,22 @@ static void __tdx_map_gpa(struct vcpu_tdx *tdx);
 
 static int tdx_complete_vmcall_map_gpa(struct kvm_vcpu *vcpu)
 {
+	u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	long rc;
 
-	if (vcpu->run->hypercall.ret) {
-		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
-		tdx->vp_enter_args.r11 = tdx->map_gpa_next;
-		return 1;
+	switch (hypercall_ret) {
+	case 0:
+		break;
+	case EAGAIN:
+		rc = TDVMCALL_STATUS_RETRY;
+		goto propagate_error;
+	case EINVAL:
+		rc = TDVMCALL_STATUS_INVALID_OPERAND;
+		goto propagate_error;
+	default:
+		WARN_ON_ONCE(kvm_is_valid_map_gpa_range_ret(hypercall_ret));
+		return -EINVAL;
 	}
 
 	tdx->map_gpa_next += TDX_MAP_GPA_MAX_LEN;
@@ -1204,13 +1214,17 @@ static int tdx_complete_vmcall_map_gpa(struct kvm_vcpu *vcpu)
 	 * TDVMCALL_MAP_GPA, see comments in tdx_protected_apic_has_interrupt().
 	 */
 	if (kvm_vcpu_has_events(vcpu)) {
-		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
-		tdx->vp_enter_args.r11 = tdx->map_gpa_next;
-		return 1;
+		rc = TDVMCALL_STATUS_RETRY;
+		goto propagate_error;
 	}
 
 	__tdx_map_gpa(tdx);
 	return 0;
+
+propagate_error:
+	tdvmcall_set_return_code(vcpu, rc);
+	tdx->vp_enter_args.r11 = tdx->map_gpa_next;
+	return 1;
 }
 
 static void __tdx_map_gpa(struct vcpu_tdx *tdx)
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 94d4f07aaaa0..9dc6da955c2a 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -720,6 +720,12 @@ int kvm_sev_es_string_io(struct kvm_vcpu *vcpu, unsigned int size,
 			 unsigned int port, void *data,  unsigned int count,
 			 int in);
 
+static inline bool kvm_is_valid_map_gpa_range_ret(u64 hypercall_ret)
+{
+	return !hypercall_ret || hypercall_ret == EINVAL ||
+	       hypercall_ret == EAGAIN;
+}
+
 static inline bool user_exit_on_hypercall(struct kvm *kvm, unsigned long hc_nr)
 {
 	return kvm->arch.hypercall_exit_enabled & BIT(hc_nr);

---

## [3] Sagi Shahar — 2026-03-05
*Subject: [PATCH v4 2/2] KVM: SEV: Restrict userspace return codes for KVM_HC_MAP_GPA_RANGE*

To align with the updated TDX api that allows userspace to request
that guests retry MAP_GPA operations, make sure that userspace is only
returning EINVAL or EAGAIN as possible error codes.

Reviewed-by: Michael Roth <michael.roth@amd.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
---
 arch/x86/kvm/svm/sev.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 3f9c1aa39a0a..04076262f087 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3718,9 +3718,13 @@ static int snp_rmptable_psmash(kvm_pfn_t pfn)
 
 static int snp_complete_psc_msr(struct kvm_vcpu *vcpu)
 {
+	u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
 	struct vcpu_svm *svm = to_svm(vcpu);
 
-	if (vcpu->run->hypercall.ret)
+	if (!kvm_is_valid_map_gpa_range_ret(hypercall_ret))
+		return -EINVAL;
+
+	if (hypercall_ret)
 		set_ghcb_msr(svm, GHCB_MSR_PSC_RESP_ERROR);
 	else
 		set_ghcb_msr(svm, GHCB_MSR_PSC_RESP);
@@ -3811,10 +3815,14 @@ static void __snp_complete_one_psc(struct vcpu_svm *svm)
 
 static int snp_complete_one_psc(struct kvm_vcpu *vcpu)
 {
+	u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
 	struct vcpu_svm *svm = to_svm(vcpu);
 	struct psc_buffer *psc = svm->sev_es.ghcb_sa;
 
-	if (vcpu->run->hypercall.ret) {
+	if (!kvm_is_valid_map_gpa_range_ret(hypercall_ret))
+		return -EINVAL;
+
+	if (hypercall_ret) {
 		snp_complete_psc(svm, VMGEXIT_PSC_ERROR_GENERIC);
 		return 1; /* resume guest */
 	}

---

## [4] Sean Christopherson — 2026-05-29
*Subject: Re: [PATCH v4 0/2] Extend KVM_HC_MAP_GPA_RANGE api to allow retry*

On Thu, 05 Mar 2026 22:26:25 +0000, Sagi Shahar wrote:
> In some cases, userspace might decide to split MAP_GPA requests and
> retry them the next time the guest runs. One common case is MAP_GPA

Applied to kvm-x86 misc, thanks!

[1/2] KVM: TDX: Allow userspace to return errors to guest for MAPGPA
      https://github.com/kvm-x86/linux/commit/3e2dec1ede0a
[2/2] KVM: SEV: Restrict userspace return codes for KVM_HC_MAP_GPA_RANGE
      https://github.com/kvm-x86/linux/commit/5d40e5b49442

--
https://github.com/kvm-x86/linux/tree/next

---
