---
title: 'KVM: Avoid literal numbers as return values'
date: 2025-12-05
last_reply: 2025-12-05
message_count: 5
participants: ['Juergen Gross', 'Sean Christopherson']
---

## [1] Juergen Gross — 2025-12-05

This series is the first part of replacing the use of literal numbers
(0 and 1) as return values with either true/false or with defines.

This work is a prelude of getting rid of the magic value "1" for
"return to guest". I started in x86 KVM host code doing that and soon
stumbled over lots of other use cases of the magic "1" as return value,
especially in MSR emulation where a comment even implied this "1" was
due to the "return to guest" semantics.

A detailed analysis of all related code paths revealed that there was
indeed a rather clean interface between the functions using the MSR
emulation "1" and those using the "return to guest" "1". 

A few functions just using "0" and "1" instead of bool are changed,
tooi (patches 1-4).

The rest of the series is cleaning up the MSR emulation code by using
new proper defines for return values 0 and 1.

The whole series should not result in any functional change.

Juergen Gross (10):
  KVM: Switch coalesced_mmio_in_range() to return bool
  KVM/x86: Use bool for the err parameter of kvm_complete_insn_gp()
  KVM/x86: Let x86_emulate_ops.set_cr() return a bool
  KVM/x86: Let x86_emulate_ops.set_dr() return a bool
  KVM/x86: Add KVM_MSR_RET_* defines for values 0 and 1
  KVM/x86: Use defines for APIC related MSR emulation
  KVM/x86: Use defines for Hyper-V related MSR emulation
  KVM/x86: Use defines for VMX related MSR emulation
  KVM/x86: Use defines for SVM related MSR emulation
  KVM/x86: Use defines for common related MSR emulation

 arch/x86/include/asm/kvm_host.h |  14 +-
 arch/x86/kvm/emulate.c          |   2 +-
 arch/x86/kvm/hyperv.c           | 110 +++++++-------
 arch/x86/kvm/kvm_emulate.h      |   4 +-
 arch/x86/kvm/lapic.c            |  48 +++----
 arch/x86/kvm/mtrr.c             |  12 +-
 arch/x86/kvm/pmu.c              |  12 +-
 arch/x86/kvm/smm.c              |   2 +-
 arch/x86/kvm/svm/pmu.c          |  12 +-
 arch/x86/kvm/svm/svm.c          |  54 +++----
 arch/x86/kvm/vmx/main.c         |   2 +-
 arch/x86/kvm/vmx/nested.c       |  18 +--
 arch/x86/kvm/vmx/pmu_intel.c    |  20 +--
 arch/x86/kvm/vmx/tdx.c          |  18 +--
 arch/x86/kvm/vmx/tdx.h          |   2 +-
 arch/x86/kvm/vmx/vmx.c          | 122 ++++++++--------
 arch/x86/kvm/x86.c              | 246 ++++++++++++++++----------------
 arch/x86/kvm/x86.h              |  10 +-
 arch/x86/kvm/xen.c              |  14 +-
 virt/kvm/coalesced_mmio.c       |  14 +-
 20 files changed, 372 insertions(+), 364 deletions(-)

---

## [2] Juergen Gross — 2025-12-05
*Subject: [PATCH 02/10] KVM/x86: Use bool for the err parameter of kvm_complete_insn_gp()*

The err parameter of kvm_complete_insn_gp() is just a flag, so bool
is the appropriate type for it.

Just converting the function itself for now is fine, as the implicit
conversion from int to bool is doing the right thing. Most callers
will be changed later to use bool, too.

As vmx_complete_emulated_msr is defined to kvm_complete_insn_gp, the
same parameter modification should be applied to
vt_complete_emulated_msr(), tdx_complete_emulated_msr() and
svm_complete_emulated_msr().

No change of functionality intended.

Signed-off-by: Juergen Gross <jgross@suse.com>
---
 arch/x86/include/asm/kvm_host.h | 4 ++--
 arch/x86/kvm/svm/svm.c          | 2 +-
 arch/x86/kvm/vmx/main.c         | 2 +-
 arch/x86/kvm/vmx/tdx.c          | 2 +-
 arch/x86/kvm/vmx/tdx.h          | 2 +-
 arch/x86/kvm/x86.c              | 2 +-
 6 files changed, 7 insertions(+), 7 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 48598d017d6f..2b289708b56b 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1930,7 +1930,7 @@ struct kvm_x86_ops {
 
 	void (*migrate_timers)(struct kvm_vcpu *vcpu);
 	void (*recalc_intercepts)(struct kvm_vcpu *vcpu);
-	int (*complete_emulated_msr)(struct kvm_vcpu *vcpu, int err);
+	int (*complete_emulated_msr)(struct kvm_vcpu *vcpu, bool err);
 
 	void (*vcpu_deliver_sipi_vector)(struct kvm_vcpu *vcpu, u8 vector);
 
@@ -2409,7 +2409,7 @@ bool kvm_arch_can_dequeue_async_page_present(struct kvm_vcpu *vcpu);
 extern bool kvm_find_async_pf_gfn(struct kvm_vcpu *vcpu, gfn_t gfn);
 
 int kvm_skip_emulated_instruction(struct kvm_vcpu *vcpu);
-int kvm_complete_insn_gp(struct kvm_vcpu *vcpu, int err);
+int kvm_complete_insn_gp(struct kvm_vcpu *vcpu, bool err);
 
 void __user *__x86_set_memory_region(struct kvm *kvm, int id, gpa_t gpa,
 				     u32 size);
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 9d29b2e7e855..f354cf0b6c1c 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -2777,7 +2777,7 @@ static int svm_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	return 0;
 }
 
-static int svm_complete_emulated_msr(struct kvm_vcpu *vcpu, int err)
+static int svm_complete_emulated_msr(struct kvm_vcpu *vcpu, bool err)
 {
 	struct vcpu_svm *svm = to_svm(vcpu);
 	if (!err || !sev_es_guest(vcpu->kvm) || WARN_ON_ONCE(!svm->sev_es.ghcb))
diff --git a/arch/x86/kvm/vmx/main.c b/arch/x86/kvm/vmx/main.c
index 0eb2773b2ae2..2f1b9a75fe47 100644
--- a/arch/x86/kvm/vmx/main.c
+++ b/arch/x86/kvm/vmx/main.c
@@ -202,7 +202,7 @@ static void vt_recalc_intercepts(struct kvm_vcpu *vcpu)
 	vmx_recalc_intercepts(vcpu);
 }
 
-static int vt_complete_emulated_msr(struct kvm_vcpu *vcpu, int err)
+static int vt_complete_emulated_msr(struct kvm_vcpu *vcpu, bool err)
 {
 	if (is_td_vcpu(vcpu))
 		return tdx_complete_emulated_msr(vcpu, err);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0a49c863c811..6b99c8dbd8cc 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2028,7 +2028,7 @@ static int tdx_handle_ept_violation(struct kvm_vcpu *vcpu)
 	return ret;
 }
 
-int tdx_complete_emulated_msr(struct kvm_vcpu *vcpu, int err)
+int tdx_complete_emulated_msr(struct kvm_vcpu *vcpu, bool err)
 {
 	if (err) {
 		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ca39a9391db1..19a066868d45 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -174,7 +174,7 @@ static __always_inline void td_##lclass##_clearbit##bits(struct vcpu_tdx *tdx,	\
 
 
 bool tdx_interrupt_allowed(struct kvm_vcpu *vcpu);
-int tdx_complete_emulated_msr(struct kvm_vcpu *vcpu, int err);
+int tdx_complete_emulated_msr(struct kvm_vcpu *vcpu, bool err);
 
 TDX_BUILD_TDVPS_ACCESSORS(16, VMCS, vmcs);
 TDX_BUILD_TDVPS_ACCESSORS(32, VMCS, vmcs);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index c9c2aa6f4705..f7c84d9ea9de 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -950,7 +950,7 @@ void kvm_requeue_exception(struct kvm_vcpu *vcpu, unsigned int nr,
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_requeue_exception);
 
-int kvm_complete_insn_gp(struct kvm_vcpu *vcpu, int err)
+int kvm_complete_insn_gp(struct kvm_vcpu *vcpu, bool err)
 {
 	if (err)
 		kvm_inject_gp(vcpu, 0);

---

## [3] Juergen Gross — 2025-12-05
*Subject: [PATCH 08/10] KVM/x86: Use defines for VMX related MSR emulation*

Instead of "0" and "1" use the related KVM_MSR_RET_* defines in the
emulation code of VMX related MSR registers.

No change of functionality intended.

Signed-off-by: Juergen Gross <jgross@suse.com>
---
 arch/x86/kvm/vmx/nested.c    |  18 +++---
 arch/x86/kvm/vmx/pmu_intel.c |  20 +++----
 arch/x86/kvm/vmx/tdx.c       |  16 +++---
 arch/x86/kvm/vmx/vmx.c       | 104 +++++++++++++++++------------------
 4 files changed, 79 insertions(+), 79 deletions(-)

diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index bcea087b642f..76e8dc811bae 100644
--- a/arch/x86/kvm/vmx/nested.c
+++ b/arch/x86/kvm/vmx/nested.c
@@ -1325,7 +1325,7 @@ static int vmx_restore_vmx_basic(struct vcpu_vmx *vmx, u64 data)
 		return -EINVAL;
 
 	vmx->nested.msrs.basic = data;
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 static void vmx_get_control_msr(struct nested_vmx_msrs *msrs, u32 msr_index,
@@ -1378,7 +1378,7 @@ vmx_restore_control_msr(struct vcpu_vmx *vmx, u32 msr_index, u64 data)
 	vmx_get_control_msr(&vmx->nested.msrs, msr_index, &lowp, &highp);
 	*lowp = data;
 	*highp = data >> 32;
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 static int vmx_restore_vmx_misc(struct vcpu_vmx *vmx, u64 data)
@@ -1426,7 +1426,7 @@ static int vmx_restore_vmx_misc(struct vcpu_vmx *vmx, u64 data)
 	vmx->nested.msrs.misc_low = data;
 	vmx->nested.msrs.misc_high = data >> 32;
 
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 static int vmx_restore_vmx_ept_vpid_cap(struct vcpu_vmx *vmx, u64 data)
@@ -1440,7 +1440,7 @@ static int vmx_restore_vmx_ept_vpid_cap(struct vcpu_vmx *vmx, u64 data)
 
 	vmx->nested.msrs.ept_caps = data;
 	vmx->nested.msrs.vpid_caps = data >> 32;
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 static u64 *vmx_get_fixed0_msr(struct nested_vmx_msrs *msrs, u32 msr_index)
@@ -1467,7 +1467,7 @@ static int vmx_restore_fixed0_msr(struct vcpu_vmx *vmx, u32 msr_index, u64 data)
 		return -EINVAL;
 
 	*vmx_get_fixed0_msr(&vmx->nested.msrs, msr_index) = data;
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 /*
@@ -1525,12 +1525,12 @@ int vmx_set_vmx_msr(struct kvm_vcpu *vcpu, u32 msr_index, u64 data)
 		return vmx_restore_vmx_ept_vpid_cap(vmx, data);
 	case MSR_IA32_VMX_VMCS_ENUM:
 		vmx->nested.msrs.vmcs_enum = data;
-		return 0;
+		return KVM_MSR_RET_OK;
 	case MSR_IA32_VMX_VMFUNC:
 		if (data & ~vmcs_config.nested.vmfunc_controls)
 			return -EINVAL;
 		vmx->nested.msrs.vmfunc_controls = data;
-		return 0;
+		return KVM_MSR_RET_OK;
 	default:
 		/*
 		 * The rest of the VMX capability MSRs do not support restore.
@@ -1611,10 +1611,10 @@ int vmx_get_vmx_msr(struct nested_vmx_msrs *msrs, u32 msr_index, u64 *pdata)
 		*pdata = msrs->vmfunc_controls;
 		break;
 	default:
-		return 1;
+		return KVM_MSR_RET_ERR;
 	}
 
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 /*
diff --git a/arch/x86/kvm/vmx/pmu_intel.c b/arch/x86/kvm/vmx/pmu_intel.c
index de1d9785c01f..8bab64a748b8 100644
--- a/arch/x86/kvm/vmx/pmu_intel.c
+++ b/arch/x86/kvm/vmx/pmu_intel.c
@@ -374,10 +374,10 @@ static int intel_pmu_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		} else if (intel_pmu_handle_lbr_msrs_access(vcpu, msr_info, true)) {
 			break;
 		}
-		return 1;
+		return KVM_MSR_RET_ERR;
 	}
 
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
@@ -391,14 +391,14 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	switch (msr) {
 	case MSR_CORE_PERF_FIXED_CTR_CTRL:
 		if (data & pmu->fixed_ctr_ctrl_rsvd)
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		if (pmu->fixed_ctr_ctrl != data)
 			reprogram_fixed_counters(pmu, data);
 		break;
 	case MSR_IA32_PEBS_ENABLE:
 		if (data & pmu->pebs_enable_rsvd)
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		if (pmu->pebs_enable != data) {
 			diff = pmu->pebs_enable ^ data;
@@ -408,13 +408,13 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_DS_AREA:
 		if (is_noncanonical_msr_address(data, vcpu))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		pmu->ds_area = data;
 		break;
 	case MSR_PEBS_DATA_CFG:
 		if (data & pmu->pebs_data_cfg_rsvd)
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		pmu->pebs_data_cfg = data;
 		break;
@@ -423,7 +423,7 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		    (pmc = get_gp_pmc(pmu, msr, MSR_IA32_PMC0))) {
 			if ((msr & MSR_PMC_FULL_WIDTH_BIT) &&
 			    (data & ~pmu->counter_bitmask[KVM_PMC_GP]))
-				return 1;
+				return KVM_MSR_RET_ERR;
 
 			if (!msr_info->host_initiated &&
 			    !(msr & MSR_PMC_FULL_WIDTH_BIT))
@@ -439,7 +439,7 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 			    (pmu->raw_event_mask & HSW_IN_TX_CHECKPOINTED))
 				reserved_bits ^= HSW_IN_TX_CHECKPOINTED;
 			if (data & reserved_bits)
-				return 1;
+				return KVM_MSR_RET_ERR;
 
 			if (data != pmc->eventsel) {
 				pmc->eventsel = data;
@@ -450,10 +450,10 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 			break;
 		}
 		/* Not a known PMU MSR. */
-		return 1;
+		return KVM_MSR_RET_ERR;
 	}
 
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 /*
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 6b99c8dbd8cc..9c798de48272 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2236,15 +2236,15 @@ int tdx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr)
 		msr->data = FEAT_CTL_LOCKED;
 		if (vcpu->arch.mcg_cap & MCG_LMCE_P)
 			msr->data |= FEAT_CTL_LMCE_ENABLED;
-		return 0;
+		return KVM_MSR_RET_OK;
 	case MSR_IA32_MCG_EXT_CTL:
 		if (!msr->host_initiated && !(vcpu->arch.mcg_cap & MCG_LMCE_P))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr->data = vcpu->arch.mcg_ext_ctl;
-		return 0;
+		return KVM_MSR_RET_OK;
 	default:
 		if (!tdx_has_emulated_msr(msr->index))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		return kvm_get_msr_common(vcpu, msr);
 	}
@@ -2256,15 +2256,15 @@ int tdx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr)
 	case MSR_IA32_MCG_EXT_CTL:
 		if ((!msr->host_initiated && !(vcpu->arch.mcg_cap & MCG_LMCE_P)) ||
 		    (msr->data & ~MCG_EXT_CTL_LMCE_EN))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vcpu->arch.mcg_ext_ctl = msr->data;
-		return 0;
+		return KVM_MSR_RET_OK;
 	default:
 		if (tdx_is_read_only_msr(msr->index))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		if (!tdx_has_emulated_msr(msr->index))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		return kvm_set_msr_common(vcpu, msr);
 	}
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 365c4ce283e5..a3282a5830ca 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -662,7 +662,7 @@ static int vmx_set_guest_uret_msr(struct vcpu_vmx *vmx,
 				  struct vmx_uret_msr *msr, u64 data)
 {
 	unsigned int slot = msr - vmx->guest_uret_msrs;
-	int ret = 0;
+	int ret = KVM_MSR_RET_OK;
 
 	if (msr->load_into_hardware) {
 		preempt_disable();
@@ -1958,7 +1958,7 @@ int vmx_get_feature_msr(u32 msr, u64 *data)
 	switch (msr) {
 	case KVM_FIRST_EMULATED_VMX_MSR ... KVM_LAST_EMULATED_VMX_MSR:
 		if (!nested)
-			return 1;
+			return KVM_MSR_RET_ERR;
 		return vmx_get_vmx_msr(&vmcs_config.nested, msr, data);
 	default:
 		return KVM_MSR_RET_UNSUPPORTED;
@@ -1993,18 +1993,18 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	case MSR_IA32_TSX_CTRL:
 		if (!msr_info->host_initiated &&
 		    !(vcpu->arch.arch_capabilities & ARCH_CAP_TSX_CTRL_MSR))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		goto find_uret_msr;
 	case MSR_IA32_UMWAIT_CONTROL:
 		if (!msr_info->host_initiated && !vmx_has_waitpkg(vmx))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		msr_info->data = vmx->msr_ia32_umwait_control;
 		break;
 	case MSR_IA32_SPEC_CTRL:
 		if (!msr_info->host_initiated &&
 		    !guest_has_spec_ctrl_msr(vcpu))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		msr_info->data = to_vmx(vcpu)->spec_ctrl;
 		break;
@@ -2021,14 +2021,14 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		if (!kvm_mpx_supported() ||
 		    (!msr_info->host_initiated &&
 		     !guest_cpu_cap_has(vcpu, X86_FEATURE_MPX)))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = vmcs_read64(GUEST_BNDCFGS);
 		break;
 	case MSR_IA32_MCG_EXT_CTL:
 		if (!msr_info->host_initiated &&
 		    !(vmx->msr_ia32_feature_control &
 		      FEAT_CTL_LMCE_ENABLED))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = vcpu->arch.mcg_ext_ctl;
 		break;
 	case MSR_IA32_FEAT_CTL:
@@ -2037,16 +2037,16 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	case MSR_IA32_SGXLEPUBKEYHASH0 ... MSR_IA32_SGXLEPUBKEYHASH3:
 		if (!msr_info->host_initiated &&
 		    !guest_cpu_cap_has(vcpu, X86_FEATURE_SGX_LC))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = to_vmx(vcpu)->msr_ia32_sgxlepubkeyhash
 			[msr_info->index - MSR_IA32_SGXLEPUBKEYHASH0];
 		break;
 	case KVM_FIRST_EMULATED_VMX_MSR ... KVM_LAST_EMULATED_VMX_MSR:
 		if (!guest_cpu_cap_has(vcpu, X86_FEATURE_VMX))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (vmx_get_vmx_msr(&vmx->nested.msrs, msr_info->index,
 				    &msr_info->data))
-			return 1;
+			return KVM_MSR_RET_ERR;
 #ifdef CONFIG_KVM_HYPERV
 		/*
 		 * Enlightened VMCS v1 doesn't have certain VMCS fields but
@@ -2062,19 +2062,19 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_RTIT_CTL:
 		if (!vmx_pt_mode_is_host_guest())
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = vmx->pt_desc.guest.ctl;
 		break;
 	case MSR_IA32_RTIT_STATUS:
 		if (!vmx_pt_mode_is_host_guest())
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = vmx->pt_desc.guest.status;
 		break;
 	case MSR_IA32_RTIT_CR3_MATCH:
 		if (!vmx_pt_mode_is_host_guest() ||
 			!intel_pt_validate_cap(vmx->pt_desc.caps,
 						PT_CAP_cr3_filtering))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = vmx->pt_desc.guest.cr3_match;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_BASE:
@@ -2083,7 +2083,7 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 					PT_CAP_topa_output) &&
 			 !intel_pt_validate_cap(vmx->pt_desc.caps,
 					PT_CAP_single_range_output)))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = vmx->pt_desc.guest.output_base;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_MASK:
@@ -2092,14 +2092,14 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 					PT_CAP_topa_output) &&
 			 !intel_pt_validate_cap(vmx->pt_desc.caps,
 					PT_CAP_single_range_output)))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		msr_info->data = vmx->pt_desc.guest.output_mask;
 		break;
 	case MSR_IA32_RTIT_ADDR0_A ... MSR_IA32_RTIT_ADDR3_B:
 		index = msr_info->index - MSR_IA32_RTIT_ADDR0_A;
 		if (!vmx_pt_mode_is_host_guest() ||
 		    (index >= 2 * vmx->pt_desc.num_address_ranges))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (index % 2)
 			msr_info->data = vmx->pt_desc.guest.addr_b[index / 2];
 		else
@@ -2127,7 +2127,7 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		return kvm_get_msr_common(vcpu, msr_info);
 	}
 
-	return 0;
+	return KVM_MSR_RET_OK;
 }
 
 static u64 nested_vmx_truncate_sysenter_addr(struct kvm_vcpu *vcpu,
@@ -2180,7 +2180,7 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 {
 	struct vcpu_vmx *vmx = to_vmx(vcpu);
 	struct vmx_uret_msr *msr;
-	int ret = 0;
+	int ret = KVM_MSR_RET_OK;
 	u32 msr_index = msr_info->index;
 	u64 data = msr_info->data;
 	u32 index;
@@ -2241,7 +2241,7 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_DEBUGCTLMSR:
 		if (!vmx_is_valid_debugctl(vcpu, data, msr_info->host_initiated))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		data &= vmx_get_supported_debugctl(vcpu, msr_info->host_initiated);
 
@@ -2254,15 +2254,15 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		if (intel_pmu_lbr_is_enabled(vcpu) && !to_vmx(vcpu)->lbr_desc.event &&
 		    (data & DEBUGCTLMSR_LBR))
 			intel_pmu_create_guest_lbr_event(vcpu);
-		return 0;
+		return KVM_MSR_RET_OK;
 	case MSR_IA32_BNDCFGS:
 		if (!kvm_mpx_supported() ||
 		    (!msr_info->host_initiated &&
 		     !guest_cpu_cap_has(vcpu, X86_FEATURE_MPX)))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (is_noncanonical_msr_address(data & PAGE_MASK, vcpu) ||
 		    (data & MSR_IA32_BNDCFGS_RSVD))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		if (is_guest_mode(vcpu) &&
 		    ((vmx->nested.msrs.entry_ctls_high & VM_ENTRY_LOAD_BNDCFGS) ||
@@ -2273,21 +2273,21 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_UMWAIT_CONTROL:
 		if (!msr_info->host_initiated && !vmx_has_waitpkg(vmx))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		/* The reserved bit 1 and non-32 bit [63:32] should be zero */
 		if (data & (BIT_ULL(1) | GENMASK_ULL(63, 32)))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		vmx->msr_ia32_umwait_control = data;
 		break;
 	case MSR_IA32_SPEC_CTRL:
 		if (!msr_info->host_initiated &&
 		    !guest_has_spec_ctrl_msr(vcpu))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		if (kvm_spec_ctrl_test_value(data))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		vmx->spec_ctrl = data;
 		if (!data)
@@ -2312,9 +2312,9 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	case MSR_IA32_TSX_CTRL:
 		if (!msr_info->host_initiated &&
 		    !(vcpu->arch.arch_capabilities & ARCH_CAP_TSX_CTRL_MSR))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (data & ~(TSX_CTRL_RTM_DISABLE | TSX_CTRL_CPUID_CLEAR))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		goto find_uret_msr;
 	case MSR_IA32_CR_PAT:
 		ret = kvm_set_msr_common(vcpu, msr_info);
@@ -2333,12 +2333,12 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		     !(to_vmx(vcpu)->msr_ia32_feature_control &
 		       FEAT_CTL_LMCE_ENABLED)) ||
 		    (data & ~MCG_EXT_CTL_LMCE_EN))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vcpu->arch.mcg_ext_ctl = data;
 		break;
 	case MSR_IA32_FEAT_CTL:
 		if (!is_vmx_feature_control_msr_valid(vmx, msr_info))
-			return 1;
+			return KVM_MSR_RET_ERR;
 
 		vmx->msr_ia32_feature_control = data;
 		if (msr_info->host_initiated && data == 0)
@@ -2363,70 +2363,70 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		    (!guest_cpu_cap_has(vcpu, X86_FEATURE_SGX_LC) ||
 		    ((vmx->msr_ia32_feature_control & FEAT_CTL_LOCKED) &&
 		    !(vmx->msr_ia32_feature_control & FEAT_CTL_SGX_LC_ENABLED))))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vmx->msr_ia32_sgxlepubkeyhash
 			[msr_index - MSR_IA32_SGXLEPUBKEYHASH0] = data;
 		break;
 	case KVM_FIRST_EMULATED_VMX_MSR ... KVM_LAST_EMULATED_VMX_MSR:
 		if (!msr_info->host_initiated)
-			return 1; /* they are read-only */
+			return KVM_MSR_RET_ERR; /* they are read-only */
 		if (!guest_cpu_cap_has(vcpu, X86_FEATURE_VMX))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		return vmx_set_vmx_msr(vcpu, msr_index, data);
 	case MSR_IA32_RTIT_CTL:
 		if (!vmx_pt_mode_is_host_guest() ||
 			vmx_rtit_ctl_check(vcpu, data) ||
 			vmx->nested.vmxon)
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vmcs_write64(GUEST_IA32_RTIT_CTL, data);
 		vmx->pt_desc.guest.ctl = data;
 		pt_update_intercept_for_msr(vcpu);
 		break;
 	case MSR_IA32_RTIT_STATUS:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (data & MSR_IA32_RTIT_STATUS_MASK)
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vmx->pt_desc.guest.status = data;
 		break;
 	case MSR_IA32_RTIT_CR3_MATCH:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (!intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_cr3_filtering))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vmx->pt_desc.guest.cr3_match = data;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_BASE:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (!intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_topa_output) &&
 		    !intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_single_range_output))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (!pt_output_base_valid(vcpu, data))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vmx->pt_desc.guest.output_base = data;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_MASK:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (!intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_topa_output) &&
 		    !intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_single_range_output))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		vmx->pt_desc.guest.output_mask = data;
 		break;
 	case MSR_IA32_RTIT_ADDR0_A ... MSR_IA32_RTIT_ADDR3_B:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		index = msr_info->index - MSR_IA32_RTIT_ADDR0_A;
 		if (index >= 2 * vmx->pt_desc.num_address_ranges)
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (is_noncanonical_msr_address(data, vcpu))
-			return 1;
+			return KVM_MSR_RET_ERR;
 		if (index % 2)
 			vmx->pt_desc.guest.addr_b[index / 2] = data;
 		else
@@ -2445,20 +2445,20 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		if (data & PERF_CAP_LBR_FMT) {
 			if ((data & PERF_CAP_LBR_FMT) !=
 			    (kvm_caps.supported_perf_cap & PERF_CAP_LBR_FMT))
-				return 1;
+				return KVM_MSR_RET_ERR;
 			if (!cpuid_model_is_consistent(vcpu))
-				return 1;
+				return KVM_MSR_RET_ERR;
 		}
 		if (data & PERF_CAP_PEBS_FORMAT) {
 			if ((data & PERF_CAP_PEBS_MASK) !=
 			    (kvm_caps.supported_perf_cap & PERF_CAP_PEBS_MASK))
-				return 1;
+				return KVM_MSR_RET_ERR;
 			if (!guest_cpu_cap_has(vcpu, X86_FEATURE_DS))
-				return 1;
+				return KVM_MSR_RET_ERR;
 			if (!guest_cpu_cap_has(vcpu, X86_FEATURE_DTES64))
-				return 1;
+				return KVM_MSR_RET_ERR;
 			if (!cpuid_model_is_consistent(vcpu))
-				return 1;
+				return KVM_MSR_RET_ERR;
 		}
 		ret = kvm_set_msr_common(vcpu, msr_info);
 		break;

---

## [4] Sean Christopherson — 2025-12-05
*Subject: Re: [PATCH 00/10] KVM: Avoid literal numbers as return values*

On Fri, Dec 05, 2025, Juergen Gross wrote:
> This series is the first part of replacing the use of literal numbers
> (0 and 1) as return values with either true/false or with defines.

Sorry, but NAK to using true/false.  IMO, it's far worse than 0/1.  At least 0/1
draws from the kernel's 0/-errno approach.  With booleans, the polarity is often
hard to discern without a priori knowledge of the pattern, and even then it can
be confusing.  E.g. for me, returning "true" when .set_{c,d}r() fails is unexpected,
and results in unintuitive code like this:

                if (!kvm_dr6_valid(val))
			return true;

For isolated APIs whose values aren't intented to be propagated back up to the
.handle_exit() call site, I would much rather return 0/-EINVAL.

Do you have a sketch of what the end goal/result will look like?  IIRC, last time
anyone looked at doing this (which was a few years ago, but I don't think KVM has
changed _that_ much), we backed off because a partial conversion would leave KVM
in an unwieldy and somewhat scary state.

> This work is a prelude of getting rid of the magic value "1" for
> "return to guest". I started in x86 KVM host code doing that and soon

Ya, we've started chipping away at the MSR stuff.  The big challenge is avoiding
subtle ABI changes related to the fixups done by kvm_do_msr_access().

---

## [5] Jürgen Groß — 2025-12-05
*Subject: Re: [PATCH 00/10] KVM: Avoid literal numbers as return values*

On 05.12.25 15:16, Sean Christopherson wrote:
> On Fri, Dec 05, 2025, Juergen Gross wrote:
>> This series is the first part of replacing the use of literal numbers

I don't see "return 1;" being much better here.

> For isolated APIs whose values aren't intented to be propagated back up to the
> .handle_exit() call site, I would much rather return 0/-EINVAL.

Fine with me (I agree this would be more readable).

> Do you have a sketch of what the end goal/result will look like?  IIRC, last time
> anyone looked at doing this (which was a few years ago, but I don't think KVM has

In the end I'd like to get rid of most "return 1;" and several "return 0;"
instances in KVM.

The main reason is that it is sometimes very hard to determine what the
current "return 1" is meant to say ("error" or "return to guest" or just
"okay"). This is especially true in some of the low level MSR emulation
code, e.g. in kvm_pmu_get_msr(): only after examining the call paths I was
sure the "return 0" wasn't meant to return to qemu, but to indicate success.

I have already started to replace the "return 1;" instances in the exit
handlers with "return KVM_RET_GUEST;", but the MSR emulation code convinced
me to analyze it first and to clear it up before changing any of its "1"
return values by accident to "KVM_RET_GUEST".

In the end my plan is to cover all archs to replace the literal "1"s with
"KVM_RET_GUEST" where appropriate, and as many other literal "1"s as possible
with more meaningful defines.

I hoped to get this done much earlier and faster, but this is quite a yak to
shave. :-)

I realized that pushing out patches as soon as possible is the only way to
get this finished at all, as this is a moving target with all the work of
others which might interfere. So my revised plan is to do one arch after
the other and in each arch to cover stuff like the MSR emulation first in
order not to mix things up again.

>> This work is a prelude of getting rid of the magic value "1" for
>> "return to guest". I started in x86 KVM host code doing that and soon

Right.

This whole work was triggered by my accidental "fix" of kvm_mmu_page_fault()
replacing a "1" with "RET_PF_RETRY", which you stopped from hitting upstream.


Juergen

---
