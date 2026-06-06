---
title: 'KVM/x86: Drop "1" as MSR emulation return value'
date: 2026-05-28
last_reply: 2026-05-29
message_count: 12
participants: ['Juergen Gross', 'Sean Christopherson', 'David Woodhouse']
---

## [1] Juergen Gross — 2026-05-28

Get rid of the literal "1" used as general error return value in KVM
MSR emulation. It can easily be replaced by negative errno values
instead.

This is meant to avoid confusion with the literal "1" used as return
value for "return to guest".

Changes in V2:
- series carved out from initial "KVM: Avoid literal numbers as return
  values" series
- don't use new KVM_MSR_RET_* defines, but 0 and -errno

Juergen Gross (6):
  KVM/x86: Change comment before KVM_MSR_RET_* defines
  KVM/x86: Return -errno instead of "1" for APIC related MSR emulation
  KVM/x86: Return -errno instead of "1" for Hyper-V related MSR
    emulation
  KVM/x86: Return -errno instead of "1" for VMX related MSR emulation
  KVM/x86: Return -errno instead of "1" for SVM related MSR emulation
  KVM/x86: Return -errno instead of "1" for common MSR emulation

 arch/x86/kvm/hyperv.c        |  72 ++++++++++++-------------
 arch/x86/kvm/lapic.c         |  39 +++++++-------
 arch/x86/kvm/mtrr.c          |   6 +--
 arch/x86/kvm/pmu.c           |   8 +--
 arch/x86/kvm/svm/pmu.c       |   4 +-
 arch/x86/kvm/svm/svm.c       |  36 ++++++-------
 arch/x86/kvm/vmx/nested.c    |   2 +-
 arch/x86/kvm/vmx/pmu_intel.c |  16 +++---
 arch/x86/kvm/vmx/tdx.c       |  10 ++--
 arch/x86/kvm/vmx/vmx.c       |  96 ++++++++++++++++-----------------
 arch/x86/kvm/x86.c           | 102 +++++++++++++++++------------------
 arch/x86/kvm/x86.h           |   4 +-
 arch/x86/kvm/xen.c           |  10 ++--
 13 files changed, 202 insertions(+), 203 deletions(-)

---

## [2] Juergen Gross — 2026-05-28
*Subject: [PATCH v2 4/6] KVM/x86: Return -errno instead of "1" for VMX related MSR emulation*

Instead of a literal "1" for signalling an error, use a negative errno
value in the emulation code of VMX related MSR registers.

Signed-off-by: Juergen Gross <jgross@suse.com>
---
V2:
- use -errno instead of KVM_MSR_RET_ERR
---
 arch/x86/kvm/vmx/nested.c    |  2 +-
 arch/x86/kvm/vmx/pmu_intel.c | 16 +++---
 arch/x86/kvm/vmx/tdx.c       | 10 ++--
 arch/x86/kvm/vmx/vmx.c       | 96 ++++++++++++++++++------------------
 4 files changed, 62 insertions(+), 62 deletions(-)

diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index 3fe88f29be7a..2236f15ffab2 100644
--- a/arch/x86/kvm/vmx/nested.c
+++ b/arch/x86/kvm/vmx/nested.c
@@ -1611,7 +1611,7 @@ int vmx_get_vmx_msr(struct nested_vmx_msrs *msrs, u32 msr_index, u64 *pdata)
 		*pdata = msrs->vmfunc_controls;
 		break;
 	default:
-		return 1;
+		return -EINVAL;
 	}
 
 	return 0;
diff --git a/arch/x86/kvm/vmx/pmu_intel.c b/arch/x86/kvm/vmx/pmu_intel.c
index 27eb76e6b6a0..4f7e354c4b50 100644
--- a/arch/x86/kvm/vmx/pmu_intel.c
+++ b/arch/x86/kvm/vmx/pmu_intel.c
@@ -362,7 +362,7 @@ static int intel_pmu_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		} else if (intel_pmu_handle_lbr_msrs_access(vcpu, msr_info, true)) {
 			break;
 		}
-		return 1;
+		return -EINVAL;
 	}
 
 	return 0;
@@ -379,14 +379,14 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	switch (msr) {
 	case MSR_CORE_PERF_FIXED_CTR_CTRL:
 		if (data & pmu->fixed_ctr_ctrl_rsvd)
-			return 1;
+			return -EINVAL;
 
 		if (pmu->fixed_ctr_ctrl != data)
 			reprogram_fixed_counters(pmu, data);
 		break;
 	case MSR_IA32_PEBS_ENABLE:
 		if (data & pmu->pebs_enable_rsvd)
-			return 1;
+			return -EINVAL;
 
 		if (pmu->pebs_enable != data) {
 			diff = pmu->pebs_enable ^ data;
@@ -396,13 +396,13 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_DS_AREA:
 		if (is_noncanonical_msr_address(data, vcpu))
-			return 1;
+			return -EINVAL;
 
 		pmu->ds_area = data;
 		break;
 	case MSR_PEBS_DATA_CFG:
 		if (data & pmu->pebs_data_cfg_rsvd)
-			return 1;
+			return -EINVAL;
 
 		pmu->pebs_data_cfg = data;
 		break;
@@ -411,7 +411,7 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		    (pmc = get_gp_pmc(pmu, msr, MSR_IA32_PMC0))) {
 			if ((msr & MSR_PMC_FULL_WIDTH_BIT) &&
 			    (data & ~pmu->counter_bitmask[KVM_PMC_GP]))
-				return 1;
+				return -EINVAL;
 
 			if (!msr_info->host_initiated &&
 			    !(msr & MSR_PMC_FULL_WIDTH_BIT))
@@ -427,7 +427,7 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 			    (pmu->raw_event_mask & HSW_IN_TX_CHECKPOINTED))
 				reserved_bits ^= HSW_IN_TX_CHECKPOINTED;
 			if (data & reserved_bits)
-				return 1;
+				return -EINVAL;
 
 			if (data != pmc->eventsel) {
 				pmc->eventsel = data;
@@ -439,7 +439,7 @@ static int intel_pmu_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 			break;
 		}
 		/* Not a known PMU MSR. */
-		return 1;
+		return -EINVAL;
 	}
 
 	return 0;
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 04ce321ebdf3..acc3242af4f4 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2158,12 +2158,12 @@ int tdx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr)
 		return 0;
 	case MSR_IA32_MCG_EXT_CTL:
 		if (!msr->host_initiated && !(vcpu->arch.mcg_cap & MCG_LMCE_P))
-			return 1;
+			return -EINVAL;
 		msr->data = vcpu->arch.mcg_ext_ctl;
 		return 0;
 	default:
 		if (!tdx_has_emulated_msr(msr->index))
-			return 1;
+			return -EACCES;
 
 		return kvm_get_msr_common(vcpu, msr);
 	}
@@ -2175,15 +2175,15 @@ int tdx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr)
 	case MSR_IA32_MCG_EXT_CTL:
 		if ((!msr->host_initiated && !(vcpu->arch.mcg_cap & MCG_LMCE_P)) ||
 		    (msr->data & ~MCG_EXT_CTL_LMCE_EN))
-			return 1;
+			return -EINVAL;
 		vcpu->arch.mcg_ext_ctl = msr->data;
 		return 0;
 	default:
 		if (tdx_is_read_only_msr(msr->index))
-			return 1;
+			return -EACCES;
 
 		if (!tdx_has_emulated_msr(msr->index))
-			return 1;
+			return -EACCES;
 
 		return kvm_set_msr_common(vcpu, msr);
 	}
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index b9103de01428..2eee599fca30 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -2076,7 +2076,7 @@ int vmx_get_feature_msr(u32 msr, u64 *data)
 	switch (msr) {
 	case KVM_FIRST_EMULATED_VMX_MSR ... KVM_LAST_EMULATED_VMX_MSR:
 		if (!nested)
-			return 1;
+			return -EINVAL;
 		return vmx_get_vmx_msr(&vmcs_config.nested, msr, data);
 	default:
 		return KVM_MSR_RET_UNSUPPORTED;
@@ -2111,18 +2111,18 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	case MSR_IA32_TSX_CTRL:
 		if (!msr_info->host_initiated &&
 		    !(vcpu->arch.arch_capabilities & ARCH_CAP_TSX_CTRL_MSR))
-			return 1;
+			return -EINVAL;
 		goto find_uret_msr;
 	case MSR_IA32_UMWAIT_CONTROL:
 		if (!msr_info->host_initiated && !vmx_has_waitpkg(vmx))
-			return 1;
+			return -EINVAL;
 
 		msr_info->data = vmx->msr_ia32_umwait_control;
 		break;
 	case MSR_IA32_SPEC_CTRL:
 		if (!msr_info->host_initiated &&
 		    !guest_has_spec_ctrl_msr(vcpu))
-			return 1;
+			return -EINVAL;
 
 		msr_info->data = to_vmx(vcpu)->spec_ctrl;
 		break;
@@ -2139,14 +2139,14 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		if (!kvm_mpx_supported() ||
 		    (!msr_info->host_initiated &&
 		     !guest_cpu_cap_has(vcpu, X86_FEATURE_MPX)))
-			return 1;
+			return -EINVAL;
 		msr_info->data = vmcs_read64(GUEST_BNDCFGS);
 		break;
 	case MSR_IA32_MCG_EXT_CTL:
 		if (!msr_info->host_initiated &&
 		    !(vmx->msr_ia32_feature_control &
 		      FEAT_CTL_LMCE_ENABLED))
-			return 1;
+			return -EINVAL;
 		msr_info->data = vcpu->arch.mcg_ext_ctl;
 		break;
 	case MSR_IA32_FEAT_CTL:
@@ -2155,16 +2155,16 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	case MSR_IA32_SGXLEPUBKEYHASH0 ... MSR_IA32_SGXLEPUBKEYHASH3:
 		if (!msr_info->host_initiated &&
 		    !guest_cpu_cap_has(vcpu, X86_FEATURE_SGX_LC))
-			return 1;
+			return -EINVAL;
 		msr_info->data = to_vmx(vcpu)->msr_ia32_sgxlepubkeyhash
 			[msr_info->index - MSR_IA32_SGXLEPUBKEYHASH0];
 		break;
 	case KVM_FIRST_EMULATED_VMX_MSR ... KVM_LAST_EMULATED_VMX_MSR:
 		if (!guest_cpu_cap_has(vcpu, X86_FEATURE_VMX))
-			return 1;
+			return -EINVAL;
 		if (vmx_get_vmx_msr(&vmx->nested.msrs, msr_info->index,
 				    &msr_info->data))
-			return 1;
+			return -EINVAL;
 #ifdef CONFIG_KVM_HYPERV
 		/*
 		 * Enlightened VMCS v1 doesn't have certain VMCS fields but
@@ -2180,19 +2180,19 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_RTIT_CTL:
 		if (!vmx_pt_mode_is_host_guest())
-			return 1;
+			return -EINVAL;
 		msr_info->data = vmx->pt_desc.guest.ctl;
 		break;
 	case MSR_IA32_RTIT_STATUS:
 		if (!vmx_pt_mode_is_host_guest())
-			return 1;
+			return -EINVAL;
 		msr_info->data = vmx->pt_desc.guest.status;
 		break;
 	case MSR_IA32_RTIT_CR3_MATCH:
 		if (!vmx_pt_mode_is_host_guest() ||
 			!intel_pt_validate_cap(vmx->pt_desc.caps,
 						PT_CAP_cr3_filtering))
-			return 1;
+			return -EINVAL;
 		msr_info->data = vmx->pt_desc.guest.cr3_match;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_BASE:
@@ -2201,7 +2201,7 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 					PT_CAP_topa_output) &&
 			 !intel_pt_validate_cap(vmx->pt_desc.caps,
 					PT_CAP_single_range_output)))
-			return 1;
+			return -EINVAL;
 		msr_info->data = vmx->pt_desc.guest.output_base;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_MASK:
@@ -2210,14 +2210,14 @@ int vmx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 					PT_CAP_topa_output) &&
 			 !intel_pt_validate_cap(vmx->pt_desc.caps,
 					PT_CAP_single_range_output)))
-			return 1;
+			return -EINVAL;
 		msr_info->data = vmx->pt_desc.guest.output_mask;
 		break;
 	case MSR_IA32_RTIT_ADDR0_A ... MSR_IA32_RTIT_ADDR3_B:
 		index = msr_info->index - MSR_IA32_RTIT_ADDR0_A;
 		if (!vmx_pt_mode_is_host_guest() ||
 		    (index >= 2 * vmx->pt_desc.num_address_ranges))
-			return 1;
+			return -EINVAL;
 		if (index % 2)
 			msr_info->data = vmx->pt_desc.guest.addr_b[index / 2];
 		else
@@ -2359,7 +2359,7 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_DEBUGCTLMSR:
 		if (!vmx_is_valid_debugctl(vcpu, data, msr_info->host_initiated))
-			return 1;
+			return -EINVAL;
 
 		data &= vmx_get_supported_debugctl(vcpu, msr_info->host_initiated);
 
@@ -2377,10 +2377,10 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		if (!kvm_mpx_supported() ||
 		    (!msr_info->host_initiated &&
 		     !guest_cpu_cap_has(vcpu, X86_FEATURE_MPX)))
-			return 1;
+			return -EINVAL;
 		if (is_noncanonical_msr_address(data & PAGE_MASK, vcpu) ||
 		    (data & MSR_IA32_BNDCFGS_RSVD))
-			return 1;
+			return -EINVAL;
 
 		if (is_guest_mode(vcpu) &&
 		    ((vmx->nested.msrs.entry_ctls_high & VM_ENTRY_LOAD_BNDCFGS) ||
@@ -2391,21 +2391,21 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		break;
 	case MSR_IA32_UMWAIT_CONTROL:
 		if (!msr_info->host_initiated && !vmx_has_waitpkg(vmx))
-			return 1;
+			return -EINVAL;
 
 		/* The reserved bit 1 and non-32 bit [63:32] should be zero */
 		if (data & (BIT_ULL(1) | GENMASK_ULL(63, 32)))
-			return 1;
+			return -EINVAL;
 
 		vmx->msr_ia32_umwait_control = data;
 		break;
 	case MSR_IA32_SPEC_CTRL:
 		if (!msr_info->host_initiated &&
 		    !guest_has_spec_ctrl_msr(vcpu))
-			return 1;
+			return -EINVAL;
 
 		if (kvm_spec_ctrl_test_value(data))
-			return 1;
+			return -EINVAL;
 
 		vmx->spec_ctrl = data;
 		if (!data)
@@ -2430,9 +2430,9 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	case MSR_IA32_TSX_CTRL:
 		if (!msr_info->host_initiated &&
 		    !(vcpu->arch.arch_capabilities & ARCH_CAP_TSX_CTRL_MSR))
-			return 1;
+			return -EINVAL;
 		if (data & ~(TSX_CTRL_RTM_DISABLE | TSX_CTRL_CPUID_CLEAR))
-			return 1;
+			return -EINVAL;
 		goto find_uret_msr;
 	case MSR_IA32_CR_PAT:
 		ret = kvm_set_msr_common(vcpu, msr_info);
@@ -2451,12 +2451,12 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		     !(to_vmx(vcpu)->msr_ia32_feature_control &
 		       FEAT_CTL_LMCE_ENABLED)) ||
 		    (data & ~MCG_EXT_CTL_LMCE_EN))
-			return 1;
+			return -EINVAL;
 		vcpu->arch.mcg_ext_ctl = data;
 		break;
 	case MSR_IA32_FEAT_CTL:
 		if (!is_vmx_feature_control_msr_valid(vmx, msr_info))
-			return 1;
+			return -EINVAL;
 
 		vmx->msr_ia32_feature_control = data;
 		if (msr_info->host_initiated && data == 0)
@@ -2481,70 +2481,70 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		    (!guest_cpu_cap_has(vcpu, X86_FEATURE_SGX_LC) ||
 		    ((vmx->msr_ia32_feature_control & FEAT_CTL_LOCKED) &&
 		    !(vmx->msr_ia32_feature_control & FEAT_CTL_SGX_LC_ENABLED))))
-			return 1;
+			return -EINVAL;
 		vmx->msr_ia32_sgxlepubkeyhash
 			[msr_index - MSR_IA32_SGXLEPUBKEYHASH0] = data;
 		break;
 	case KVM_FIRST_EMULATED_VMX_MSR ... KVM_LAST_EMULATED_VMX_MSR:
 		if (!msr_info->host_initiated)
-			return 1; /* they are read-only */
+			return -EINVAL; /* they are read-only */
 		if (!guest_cpu_cap_has(vcpu, X86_FEATURE_VMX))
-			return 1;
+			return -EINVAL;
 		return vmx_set_vmx_msr(vcpu, msr_index, data);
 	case MSR_IA32_RTIT_CTL:
 		if (!vmx_pt_mode_is_host_guest() ||
 			vmx_rtit_ctl_check(vcpu, data) ||
 			vmx->nested.vmxon)
-			return 1;
+			return -EINVAL;
 		vmcs_write64(GUEST_IA32_RTIT_CTL, data);
 		vmx->pt_desc.guest.ctl = data;
 		pt_update_intercept_for_msr(vcpu);
 		break;
 	case MSR_IA32_RTIT_STATUS:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return -EINVAL;
 		if (data & MSR_IA32_RTIT_STATUS_MASK)
-			return 1;
+			return -EINVAL;
 		vmx->pt_desc.guest.status = data;
 		break;
 	case MSR_IA32_RTIT_CR3_MATCH:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return -EINVAL;
 		if (!intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_cr3_filtering))
-			return 1;
+			return -EINVAL;
 		vmx->pt_desc.guest.cr3_match = data;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_BASE:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return -EINVAL;
 		if (!intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_topa_output) &&
 		    !intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_single_range_output))
-			return 1;
+			return -EINVAL;
 		if (!pt_output_base_valid(vcpu, data))
-			return 1;
+			return -EINVAL;
 		vmx->pt_desc.guest.output_base = data;
 		break;
 	case MSR_IA32_RTIT_OUTPUT_MASK:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return -EINVAL;
 		if (!intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_topa_output) &&
 		    !intel_pt_validate_cap(vmx->pt_desc.caps,
 					   PT_CAP_single_range_output))
-			return 1;
+			return -EINVAL;
 		vmx->pt_desc.guest.output_mask = data;
 		break;
 	case MSR_IA32_RTIT_ADDR0_A ... MSR_IA32_RTIT_ADDR3_B:
 		if (!pt_can_write_msr(vmx))
-			return 1;
+			return -EINVAL;
 		index = msr_info->index - MSR_IA32_RTIT_ADDR0_A;
 		if (index >= 2 * vmx->pt_desc.num_address_ranges)
-			return 1;
+			return -EINVAL;
 		if (is_noncanonical_msr_address(data, vcpu))
-			return 1;
+			return -EINVAL;
 		if (index % 2)
 			vmx->pt_desc.guest.addr_b[index / 2] = data;
 		else
@@ -2563,20 +2563,20 @@ int vmx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 		if (data & PERF_CAP_LBR_FMT) {
 			if ((data & PERF_CAP_LBR_FMT) !=
 			    (kvm_caps.supported_perf_cap & PERF_CAP_LBR_FMT))
-				return 1;
+				return -EINVAL;
 			if (!cpuid_model_is_consistent(vcpu))
-				return 1;
+				return -EINVAL;
 		}
 		if (data & PERF_CAP_PEBS_FORMAT) {
 			if ((data & PERF_CAP_PEBS_MASK) !=
 			    (kvm_caps.supported_perf_cap & PERF_CAP_PEBS_MASK))
-				return 1;
+				return -EINVAL;
 			if (!guest_cpu_cap_has(vcpu, X86_FEATURE_DS))
-				return 1;
+				return -EINVAL;
 			if (!guest_cpu_cap_has(vcpu, X86_FEATURE_DTES64))
-				return 1;
+				return -EINVAL;
 			if (!cpuid_model_is_consistent(vcpu))
-				return 1;
+				return -EINVAL;
 		}
 		ret = kvm_set_msr_common(vcpu, msr_info);
 		break;

---

## [3] Juergen Gross — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

Please disregard this series, there is one complication sashiko made me
aware of.


Juergen

On 28.05.26 13:35, Juergen Gross wrote:
> Get rid of the literal "1" used as general error return value in KVM
> MSR emulation. It can easily be replaced by negative errno values

---

## [4] Sean Christopherson — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On Thu, May 28, 2026, Juergen Gross wrote:
> Please disregard this series, there is one complication sashiko made me
> aware of.

Sashiko beat me to the punch. :-)

See commit 2368048bf5c2 ("KVM: x86: Signal #GP, not -EPERM, on bad WRMSR(MCi_CTL/STATUS)")
for a real world example of how things can and will go wrong.

---

## [5] Jürgen Groß — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On 28.05.26 15:09, Sean Christopherson wrote:
> On Thu, May 28, 2026, Juergen Gross wrote:
>> Please disregard this series, there is one complication sashiko made me

Yeah, with Sashiko's pointer it was easy to spot.

Question now is whether the already existing cases of -errno passed as return
value are wrong or on purpose. If the latter, there should be a comment for
that, otherwise they need to be fixed..

Disentangling the MSR emulation return values from the "normal" ones ("return
to guest"/"return to user mode") will be quite interesting with the overloaded
semantics of "1".


Juergen

---

## [6] Sean Christopherson — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On Thu, May 28, 2026, Jürgen Groß wrote:
> On 28.05.26 15:09, Sean Christopherson wrote:
> > On Thu, May 28, 2026, Juergen Gross wrote:

What are the existing cases?

> If the latter, there should be a comment for
> that, otherwise they need to be fixed..

LOL, "interesting".

---

## [7] Jürgen Groß — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On 28.05.26 15:21, Sean Christopherson wrote:
> On Thu, May 28, 2026, Jürgen Groß wrote:
>> On 28.05.26 15:09, Sean Christopherson wrote:

Have a look at:

kvm_hv_msr_get_crash_data()
kvm_hv_msr_set_crash_data()
svm_get_msr()
svm_set_msr()


Juergen

---

## [8] Jürgen Groß — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On 28.05.26 15:21, Sean Christopherson wrote:
> On Thu, May 28, 2026, Jürgen Groß wrote:
>> On 28.05.26 15:09, Sean Christopherson wrote:

Found another one:

kvm_xen_write_hypercall_page() (called by kvm_set_msr_common())


Juergen

---

## [9] David Woodhouse — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On Thu, 2026-05-28 at 16:33 +0200, Jürgen Groß wrote:
> On 28.05.26 15:21, Sean Christopherson wrote:
> > On Thu, May 28, 2026, Jürgen Groß wrote:

You mean in the case where it's using the user-provided hypercall page,
and can't copy from the buffer that the VMM provided?

I think that's correct to return -errno via PTR_ERR() and let the guest
die?

The rest return 0 or 1.

---

## [10] Jürgen Groß — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On 28.05.26 17:32, David Woodhouse wrote:
> On Thu, 2026-05-28 at 16:33 +0200, Jürgen Groß wrote:
>> On 28.05.26 15:21, Sean Christopherson wrote:

Yes.

> 
> I think that's correct to return -errno via PTR_ERR() and let the guest

In this case I think a comment in this regard would be nice, as it would
prevent others stumbling over it asking the same question again.


Juergen

---

## [11] Jürgen Groß — 2026-05-28
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On 28.05.26 15:21, Sean Christopherson wrote:
> On Thu, May 28, 2026, Jürgen Groß wrote:
>> On 28.05.26 15:09, Sean Christopherson wrote:

What do you think about the following idea:

Lets pass struct msr_info * down to all functions which get their return
value passed up. Then extend msr_info with a bool "return_to_guest" (valid
only if !host_initiated), which should be set instead of passing "1" up to
the caller (probably using an inline helper). Then the return value could
be 0 or -errno, and after MSR emulation the return_to_guest indicator can
be tested if needed.


Juergen

---

## [12] Juergen Gross — 2026-05-29
*Subject: Re: [PATCH v2 0/6] KVM/x86: Drop "1" as MSR emulation return value*

On 28.05.26 17:50, Jürgen Groß wrote:
> On 28.05.26 15:21, Sean Christopherson wrote:
>> On Thu, May 28, 2026, Jürgen Groß wrote:

In the end I think it is less error prone to define a struct kvm_msr_ret_t
used as return type, consisting of an int and a bool with the same semantics
as above. Helpers will still be a good idea IMHO.

I'll have a try how it looks like.


Juergen

---
