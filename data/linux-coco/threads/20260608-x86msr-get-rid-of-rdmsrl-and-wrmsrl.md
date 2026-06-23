---
title: 'x86/msr: Get rid of rdmsrl() and wrmsrl()'
date: 2026-06-08
last_reply: 2026-06-08
message_count: 2
participants: ['Juergen Gross']
---

## [1] Juergen Gross — 2026-06-08

rdsmrl() and wrmsrl() are deprecated aliases of rdmsrq() and wrmsrq().

Switch all users and remove the deprecated variants.

Juergen Gross (4):
  x86/msr: Switch rdmsrl() users to rdmsrq()
  x86/msr: Remove rdmsrl()
  x86/msr: Switch wrmsrl() users to wrmsrq()
  x86/msr: Remove wrmsrl()

 arch/x86/events/amd/uncore.c          | 4 ++--
 arch/x86/events/intel/core.c          | 4 ++--
 arch/x86/include/asm/msr.h            | 5 -----
 arch/x86/kernel/cpu/resctrl/monitor.c | 4 ++--
 arch/x86/kernel/process_64.c          | 2 +-
 arch/x86/kvm/pmu.c                    | 6 +++---
 arch/x86/kvm/vmx/tdx.c                | 6 +++---
 drivers/hv/mshv_vtl_main.c            | 4 ++--
 drivers/idle/intel_idle.c             | 6 +++---
 9 files changed, 18 insertions(+), 23 deletions(-)

---

## [2] Juergen Gross — 2026-06-08
*Subject: [PATCH 3/4] x86/msr: Switch wrmsrl() users to wrmsrq()*

wrmsrl() is a deprecated synonym for wrmsrq(). Switch its users to
wrmsrq().

Signed-off-by: Juergen Gross <jgross@suse.com>
---
 arch/x86/events/amd/uncore.c          | 2 +-
 arch/x86/events/intel/core.c          | 4 ++--
 arch/x86/kernel/cpu/resctrl/monitor.c | 2 +-
 arch/x86/kernel/process_64.c          | 2 +-
 arch/x86/kvm/pmu.c                    | 6 +++---
 arch/x86/kvm/vmx/tdx.c                | 6 +++---
 drivers/hv/mshv_vtl_main.c            | 2 +-
 drivers/idle/intel_idle.c             | 2 +-
 8 files changed, 13 insertions(+), 13 deletions(-)

diff --git a/arch/x86/events/amd/uncore.c b/arch/x86/events/amd/uncore.c
index 98ef4bf9911a..7dc6af4231cc 100644
--- a/arch/x86/events/amd/uncore.c
+++ b/arch/x86/events/amd/uncore.c
@@ -975,7 +975,7 @@ static void amd_uncore_umc_read(struct perf_event *event)
 	 * that the counter never gets a chance to saturate.
 	 */
 	if (new & BIT_ULL(63 - COUNTER_SHIFT)) {
-		wrmsrl(hwc->event_base, 0);
+		wrmsrq(hwc->event_base, 0);
 		local64_set(&hwc->prev_count, 0);
 	} else {
 		local64_set(&hwc->prev_count, new);
diff --git a/arch/x86/events/intel/core.c b/arch/x86/events/intel/core.c
index dd1e3aa75ee9..e9baa64dc962 100644
--- a/arch/x86/events/intel/core.c
+++ b/arch/x86/events/intel/core.c
@@ -3166,12 +3166,12 @@ static void intel_pmu_config_acr(int idx, u64 mask, u32 reload)
 	}
 
 	if (cpuc->acr_cfg_b[idx] != mask) {
-		wrmsrl(msr_b + msr_offset, mask);
+		wrmsrq(msr_b + msr_offset, mask);
 		cpuc->acr_cfg_b[idx] = mask;
 	}
 	/* Only need to update the reload value when there is a valid config value. */
 	if (mask && cpuc->acr_cfg_c[idx] != reload) {
-		wrmsrl(msr_c + msr_offset, reload);
+		wrmsrq(msr_c + msr_offset, reload);
 		cpuc->acr_cfg_c[idx] = reload;
 	}
 }
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index c5ed0bc1f831..e4918c32a822 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -532,7 +532,7 @@ static void resctrl_abmc_config_one_amd(void *info)
 {
 	union l3_qos_abmc_cfg *abmc_cfg = info;
 
-	wrmsrl(MSR_IA32_L3_QOS_ABMC_CFG, abmc_cfg->full);
+	wrmsrq(MSR_IA32_L3_QOS_ABMC_CFG, abmc_cfg->full);
 }
 
 /*
diff --git a/arch/x86/kernel/process_64.c b/arch/x86/kernel/process_64.c
index b85e715ebb30..d44afbe005bb 100644
--- a/arch/x86/kernel/process_64.c
+++ b/arch/x86/kernel/process_64.c
@@ -708,7 +708,7 @@ __switch_to(struct task_struct *prev_p, struct task_struct *next_p)
 
 	/* Reset hw history on AMD CPUs */
 	if (cpu_feature_enabled(X86_FEATURE_AMD_WORKLOAD_CLASS))
-		wrmsrl(MSR_AMD_WORKLOAD_HRST, 0x1);
+		wrmsrq(MSR_AMD_WORKLOAD_HRST, 0x1);
 
 	return prev_p;
 }
diff --git a/arch/x86/kvm/pmu.c b/arch/x86/kvm/pmu.c
index e218352e3423..aee70e5dc15d 100644
--- a/arch/x86/kvm/pmu.c
+++ b/arch/x86/kvm/pmu.c
@@ -1313,14 +1313,14 @@ static void kvm_pmu_load_guest_pmcs(struct kvm_vcpu *vcpu)
 		pmc = &pmu->gp_counters[i];
 
 		if (pmc->counter != rdpmc(i))
-			wrmsrl(gp_counter_msr(i), pmc->counter);
-		wrmsrl(gp_eventsel_msr(i), pmc->eventsel_hw);
+			wrmsrq(gp_counter_msr(i), pmc->counter);
+		wrmsrq(gp_eventsel_msr(i), pmc->eventsel_hw);
 	}
 	for (i = 0; i < pmu->nr_arch_fixed_counters; i++) {
 		pmc = &pmu->fixed_counters[i];
 
 		if (pmc->counter != rdpmc(INTEL_PMC_FIXED_RDPMC_BASE | i))
-			wrmsrl(fixed_counter_msr(i), pmc->counter);
+			wrmsrq(fixed_counter_msr(i), pmc->counter);
 	}
 }
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 04ce321ebdf3..cb50e23c39ca 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -823,7 +823,7 @@ static void tdx_prepare_switch_to_host(struct kvm_vcpu *vcpu)
 		return;
 
 	++vcpu->stat.host_state_reload;
-	wrmsrl(MSR_KERNEL_GS_BASE, vt->msr_host_kernel_gs_base);
+	wrmsrq(MSR_KERNEL_GS_BASE, vt->msr_host_kernel_gs_base);
 
 	vt->guest_state_loaded = false;
 }
@@ -1048,10 +1048,10 @@ static void tdx_load_host_xsave_state(struct kvm_vcpu *vcpu)
 
 	/*
 	 * Likewise, even if a TDX hosts didn't support XSS both arms of
-	 * the comparison would be 0 and the wrmsrl would be skipped.
+	 * the comparison would be 0 and the wrmsrq would be skipped.
 	 */
 	if (kvm_host.xss != (kvm_tdx->xfam & kvm_caps.supported_xss))
-		wrmsrl(MSR_IA32_XSS, kvm_host.xss);
+		wrmsrq(MSR_IA32_XSS, kvm_host.xss);
 }
 
 #define TDX_DEBUGCTL_PRESERVED (DEBUGCTLMSR_BTF | \
diff --git a/drivers/hv/mshv_vtl_main.c b/drivers/hv/mshv_vtl_main.c
index f5d27f28d6ad..0d3d4161974f 100644
--- a/drivers/hv/mshv_vtl_main.c
+++ b/drivers/hv/mshv_vtl_main.c
@@ -596,7 +596,7 @@ static int mshv_vtl_get_set_reg(struct hv_register_assoc *regs, bool set)
 		} else {
 			/* Handle MSRs */
 			if (set)
-				wrmsrl(reg_table[i].msr_addr, *reg64);
+				wrmsrq(reg_table[i].msr_addr, *reg64);
 			else
 				rdmsrq(reg_table[i].msr_addr, *reg64);
 		}
diff --git a/drivers/idle/intel_idle.c b/drivers/idle/intel_idle.c
index 15c698291b32..67d5993c7387 100644
--- a/drivers/idle/intel_idle.c
+++ b/drivers/idle/intel_idle.c
@@ -2379,7 +2379,7 @@ static void intel_c1_demotion_toggle(void *enable)
 		msr_val |= NHM_C1_AUTO_DEMOTE | SNB_C1_AUTO_UNDEMOTE;
 	else
 		msr_val &= ~(NHM_C1_AUTO_DEMOTE | SNB_C1_AUTO_UNDEMOTE);
-	wrmsrl(MSR_PKG_CST_CONFIG_CONTROL, msr_val);
+	wrmsrq(MSR_PKG_CST_CONFIG_CONTROL, msr_val);
 }
 
 static ssize_t intel_c1_demotion_store(struct device *dev,

---
