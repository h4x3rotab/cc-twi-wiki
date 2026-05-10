---
title: 'Extend KVM_HC_MAP_GPA_RANGE api to allow retry'
date: 2026-02-06
last_reply: 2026-03-05
message_count: 9
participants: ['Sagi Shahar', 'Michael Roth', 'Tom Lendacky', 'Sean Christopherson']
---

## [1] Sagi Shahar — 2026-02-06

In some cases, userspace might decide to split MAP_GPA requests and
retry them the next time the guest runs. One common case is MAP_GPA
requests received right before intrahost migration when userspace
might decide to complete the request after the migration is complete
to reduce blackout time.

This is v3 of the series, v1[1] and v2[2] were posted as standalone
patches.

Changes from v2:
 * Rebased on top of v6.19-rc8.
 * Updated documentation.
 * Restricted SNP error codes to match TDX restrictions.

[1] https://lore.kernel.org/kvm/20260114003015.1386066-1-sagis@google.com/
[2] https://lore.kernel.org/lkml/20260115225238.2837449-1-sagis@google.com/

Sagi Shahar (1):
  KVM: SEV: Restrict userspace return codes for KVM_HC_MAP_GPA_RANGE

Vishal Annapurve (1):
  KVM: TDX: Allow userspace to return errors to guest for MAPGPA

 Documentation/virt/kvm/api.rst |  3 +++
 arch/x86/kvm/svm/sev.c         | 12 ++++++++++--
 arch/x86/kvm/vmx/tdx.c         | 15 +++++++++++++--
 arch/x86/kvm/x86.h             |  6 ++++++
 4 files changed, 32 insertions(+), 4 deletions(-)

---

## [2] Sagi Shahar — 2026-02-06
*Subject: [PATCH v3 1/2] KVM: TDX: Allow userspace to return errors to guest
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

Signed-off-by: Vishal Annapurve <vannapurve@google.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
---
 Documentation/virt/kvm/api.rst |  3 +++
 arch/x86/kvm/vmx/tdx.c         | 15 +++++++++++++--
 arch/x86/kvm/x86.h             |  6 ++++++
 3 files changed, 22 insertions(+), 2 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 01a3abef8abb..9978cd9d897e 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -8679,6 +8679,9 @@ block sizes is exposed in KVM_CAP_ARM_SUPPORTED_BLOCK_SIZES as a
 
 This capability, if enabled, will cause KVM to exit to userspace
 with KVM_EXIT_HYPERCALL exit reason to process some hypercalls.
+Userspace may fail the hypercall by setting hypercall.ret to EINVAL
+or may request the hypercall to be retried the next time the guest run
+by setting hypercall.ret to EAGAIN.
 
 Calling KVM_CHECK_EXTENSION for this capability will return a bitmask
 of hypercalls that can be configured to exit to userspace.
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..056a44b9d78b 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1186,10 +1186,21 @@ static void __tdx_map_gpa(struct vcpu_tdx *tdx);
 
 static int tdx_complete_vmcall_map_gpa(struct kvm_vcpu *vcpu)
 {
+	u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 
-	if (vcpu->run->hypercall.ret) {
-		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+	if (hypercall_ret) {
+		if (hypercall_ret == EAGAIN) {
+			tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
+		} else if (vcpu->run->hypercall.ret == EINVAL) {
+			tdvmcall_set_return_code(
+				vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+		} else {
+			WARN_ON_ONCE(
+				kvm_is_valid_map_gpa_range_ret(hypercall_ret));
+			return -EINVAL;
+		}
+
 		tdx->vp_enter_args.r11 = tdx->map_gpa_next;
 		return 1;
 	}
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index fdab0ad49098..3d464d12423a 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -706,6 +706,12 @@ int kvm_sev_es_string_io(struct kvm_vcpu *vcpu, unsigned int size,
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

## [3] Sagi Shahar — 2026-02-06
*Subject: [PATCH v3 2/2] KVM: SEV: Restrict userspace return codes for KVM_HC_MAP_GPA_RANGE*

To align with the updated TDX api that allows userspace to request
that guests retry MAP_GPA operations, make sure that userspace is only
returning EINVAL or EAGAIN as possible error codes.

Signed-off-by: Sagi Shahar <sagis@google.com>
---
 arch/x86/kvm/svm/sev.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f59c65abe3cf..5f78e4c3eb5d 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3722,9 +3722,13 @@ static int snp_rmptable_psmash(kvm_pfn_t pfn)
 
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
@@ -3815,10 +3819,14 @@ static void __snp_complete_one_psc(struct vcpu_svm *svm)
 
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

## [4] Michael Roth — 2026-02-17
*Subject: Re: [PATCH v3 1/2] KVM: TDX: Allow userspace to return errors to
 guest for MAPGPA*

On Fri, Feb 06, 2026 at 10:28:28PM +0000, Sagi Shahar wrote:
> From: Vishal Annapurve <vannapurve@google.com>
> 

Maybe slightly more readable?

    switch (hypercall_ret) {
    case EAGAIN:
        tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
        /* fallthrough */
    case EINVAL:
        tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
        /* fallthrough */
    case 0:
        break;
    case default:
        WARN_ON_ONCE(kvm_is_valid_map_gpa_range_ret(hypercall_ret));
        return -EINVAL;
    }

    tdx->vp_enter_args.r11 = tdx->map_gpa_next;
    return 1;

Either way:

Reviewed-by: Michael Roth <michael.roth@amd.com>

> diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
> index fdab0ad49098..3d464d12423a 100644

---

## [5] Michael Roth — 2026-02-17
*Subject: Re: [PATCH v3 2/2] KVM: SEV: Restrict userspace return codes for
 KVM_HC_MAP_GPA_RANGE*

On Fri, Feb 06, 2026 at 10:28:29PM +0000, Sagi Shahar wrote:
> To align with the updated TDX api that allows userspace to request
> that guests retry MAP_GPA operations, make sure that userspace is only

Reviewed-by: Michael Roth <michael.roth@amd.com>

> ---
>  arch/x86/kvm/svm/sev.c | 12 ++++++++++--

---

## [6] Tom Lendacky — 2026-02-17
*Subject: Re: [PATCH v3 1/2] KVM: TDX: Allow userspace to return errors to
 guest for MAPGPA*

On 2/17/26 12:05, Michael Roth wrote:
> On Fri, Feb 06, 2026 at 10:28:28PM +0000, Sagi Shahar wrote:
>> From: Vishal Annapurve <vannapurve@google.com>

I think you want a break here, not a fallthrough, so that you don't set
the return code twice with the last one not being correct for EAGAIN.

Thanks,
Tom

>     case EINVAL:
>         tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);

---

## [7] Michael Roth — 2026-02-17
*Subject: Re: [PATCH v3 1/2] KVM: TDX: Allow userspace to return errors to
 guest for MAPGPA*

On Tue, Feb 17, 2026 at 12:45:52PM -0600, Tom Lendacky wrote:
> On 2/17/26 12:05, Michael Roth wrote:
> > On Fri, Feb 06, 2026 at 10:28:28PM +0000, Sagi Shahar wrote:

Doh, thanks for the catch. I guess a break for the EINVAL case as well would
be more consistent then.

    switch (hypercall_ret) {
    case EAGAIN:
        tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
        break;
    case EINVAL:
        tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
        break;
    case 0:
        break;
    case default:
        WARN_ON_ONCE(kvm_is_valid_map_gpa_range_ret(hypercall_ret));
        return -EINVAL;
    }
  
    tdx->vp_enter_args.r11 = tdx->map_gpa_next;
    return 1;

Thanks,

Mike

> >     switch (hypercall_ret) {
> >     case EAGAIN:

---

## [8] Sean Christopherson — 2026-02-17
*Subject: Re: [PATCH v3 1/2] KVM: TDX: Allow userspace to return errors to
 guest for MAPGPA*

On Tue, Feb 17, 2026, Michael Roth wrote:
> On Tue, Feb 17, 2026 at 12:45:52PM -0600, Tom Lendacky wrote:
> > On 2/17/26 12:05, Michael Roth wrote:

Heh, except then KVM will fail to handle the next chunk on success.  I like the
idea of a switch statement, so what if we add that and dedup the error handling?

static int tdx_complete_vmcall_map_gpa(struct kvm_vcpu *vcpu)
{
	u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
	struct vcpu_tdx *tdx = to_tdx(vcpu);
	long rc;

	switch (hypercall_ret) {
	case 0:
		break;
	case EAGAIN:
		rc = TDVMCALL_STATUS_RETRY;
		goto propagate_error;
	case EINVAL:
		rc = TDVMCALL_STATUS_INVALID_OPERAND;
		goto propagate_error;
	default:
		WARN_ON_ONCE(kvm_is_valid_map_gpa_range_ret(hypercall_ret));
		return -EINVAL;
	}

	tdx->map_gpa_next += TDX_MAP_GPA_MAX_LEN;
	if (tdx->map_gpa_next >= tdx->map_gpa_end)
		return 1;

	/*
	 * Stop processing the remaining part if there is a pending interrupt,
	 * which could be qualified to deliver.  Skip checking pending RVI for
	 * TDVMCALL_MAP_GPA, see comments in tdx_protected_apic_has_interrupt().
	 */
	if (kvm_vcpu_has_events(vcpu)) {
		rc = TDVMCALL_STATUS_RETRY;
		goto propagate_error;
	}

	__tdx_map_gpa(tdx);
	return 0;

propagate_error:
	tdvmcall_set_return_code(vcpu, rc);
	tdx->vp_enter_args.r11 = tdx->map_gpa_next;
	return 1;
}

---

## [9] Sagi Shahar — 2026-03-05
*Subject: Re: [PATCH v3 1/2] KVM: TDX: Allow userspace to return errors to
 guest for MAPGPA*

On Tue, Feb 17, 2026 at 1:20 PM Sean Christopherson <seanjc@google.com> wrote:
>
> On Tue, Feb 17, 2026, Michael Roth wrote:

Thanks for the review. I updated the code and sent out v4 for review.

---
