---
title: 'KVM: TDX: Allow userspace to return errors to guest for MAPGPA'
date: 2026-01-15
last_reply: 2026-01-23
message_count: 2
participants: ['Sagi Shahar', 'Sean Christopherson']
---

## [1] Sagi Shahar — 2026-01-15

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
 arch/x86/kvm/vmx/tdx.c | 8 +++++++-
 1 file changed, 7 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..9bd4ffbdfecf 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1189,7 +1189,13 @@ static int tdx_complete_vmcall_map_gpa(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 
 	if (vcpu->run->hypercall.ret) {
-		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+		if (vcpu->run->hypercall.ret == EAGAIN)
+			tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
+		else if (vcpu->run->hypercall.ret == EINVAL)
+			tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+		else
+			return -EINVAL;
+
 		tdx->vp_enter_args.r11 = tdx->map_gpa_next;
 		return 1;
 	}

---

## [2] Sean Christopherson — 2026-01-23
*Subject: Re: [PATCH v2] KVM: TDX: Allow userspace to return errors to guest
 for MAPGPA*

+Mike and Tom

On Thu, Jan 15, 2026, Sagi Shahar wrote:
> From: Vishal Annapurve <vannapurve@google.com>
> 

Because no good deed goes unpunished, please update the KVM_CAP_EXIT_HYPERCALL
section in Documentation/virt/kvm/api.rst.

We also need to give snp_complete_psc_msr() and snp_complete_one_psc() similar
treatment (and update docs accordingly, too).  AFAICT, SNP doesn't have a "retry"
error code, so I think all we can do is restrict userspace to EAGAIN and EINVAL?
(Restricting SNP guests to EINVAL seems like it would create unnecessary pain for
userspace)

E.g. something like this?

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f9aad5c1447e..14ad4daefaf7 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3732,9 +3732,13 @@ static int snp_rmptable_psmash(kvm_pfn_t pfn)
 
 static int snp_complete_psc_msr(struct kvm_vcpu *vcpu)
 {
+       u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
        struct vcpu_svm *svm = to_svm(vcpu);
 
-       if (vcpu->run->hypercall.ret)
+       if (!kvm_is_valid_map_gpa_range_ret(hypercall_ret))
+               return -EINVAL;
+
+       if (hypercall_ret)
                set_ghcb_msr(svm, GHCB_MSR_PSC_RESP_ERROR);
        else
                set_ghcb_msr(svm, GHCB_MSR_PSC_RESP);
@@ -3825,10 +3829,14 @@ static void __snp_complete_one_psc(struct vcpu_svm *svm)
 
 static int snp_complete_one_psc(struct kvm_vcpu *vcpu)
 {
+       u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
        struct vcpu_svm *svm = to_svm(vcpu);
        struct psc_buffer *psc = svm->sev_es.ghcb_sa;
 
-       if (vcpu->run->hypercall.ret) {
+       if (!kvm_is_valid_map_gpa_range_ret(hypercall_ret))
+               return -EINVAL;
+
+       if (hypercall_ret) {
                snp_complete_psc(svm, VMGEXIT_PSC_ERROR_GENERIC);
                return 1; /* resume guest */
        }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..4aa1edfef698 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1186,10 +1186,19 @@ static void __tdx_map_gpa(struct vcpu_tdx *tdx);
 
 static int tdx_complete_vmcall_map_gpa(struct kvm_vcpu *vcpu)
 {
+       u64 hypercall_ret = READ_ONCE(vcpu->run->hypercall.ret);
        struct vcpu_tdx *tdx = to_tdx(vcpu);
 
-       if (vcpu->run->hypercall.ret) {
-               tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+       if (hypercall_ret) {
+               if (hypercall_ret == EAGAIN) {
+                       tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
+               } else if (vcpu->run->hypercall.ret == EINVAL) {
+                       tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+               } else {
+                       WARN_ON_ONCE(kvm_is_valid_map_gpa_range_ret(hypercall_ret));
+                       return -EINVAL;
+               }
+
                tdx->vp_enter_args.r11 = tdx->map_gpa_next;
                return 1;
        }
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index fdab0ad49098..5c2c1924addf 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -706,6 +706,13 @@ int kvm_sev_es_string_io(struct kvm_vcpu *vcpu, unsigned int size,
                         unsigned int port, void *data,  unsigned int count,
                         int in);
 
+static inline bool kvm_is_valid_map_gpa_range_ret(u64 hypercall_ret)
+{
+       return !hypercall_ret ||
+              hypercall_ret == EINVAL ||
+              hypercall_ret == EAGAIN;
+}
+
 static inline bool user_exit_on_hypercall(struct kvm *kvm, unsigned long hc_nr)
 {
        return kvm->arch.hypercall_exit_enabled & BIT(hc_nr);

---
