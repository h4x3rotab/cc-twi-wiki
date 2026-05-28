---
title: 'KVM: SEV: Add support for IBPB-on-Entry and BTB Isolation'
date: 2026-04-02
last_reply: 2026-05-08
message_count: 10
participants: ['Kim Phillips', 'Pawan Gupta', 'Borislav Petkov']
---

## [1] Kim Phillips — 2026-04-02

IBPB-on-Entry and BTB Isolation are supplemental Spectre V2 mitigations
available to SNP guests.

Patch 1 fixes a longstanding bug where users weren't able
to force Automatic IBRS on SNP enabled machines using spectre_v2=eibrs.

Patch 2 fixes another longstanding bug where users couldn't
select legacy / toggling SPEC_CTRL[IBRS] on AMD systems.  Users of
the BTB Isolation feature may use IBRS to mitigate possible
performance degradation caused by BTB Isolation.

Patches 3 and 4 deal with a minor code refactoring as a result of
Sean's review of the v2 IBPB-on-Entry series.

Patch 5 adds support for IBPB-on-Entry.

Patch 6 adds support for BTB Isolation.

Based on current tip/master v7.0-rc6-423-g8726fc6dc93c
https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip

This v3 series now also available here:

https://github.com/AMDESE/linux/tree/btb-isol-latest

Advance qemu bits (to add feature on/off switches) available here:

https://github.com/AMDESE/qemu/tree/btb-isol-latest

Qemu bits will be posted upstream once kernel bits are merged.
They depend on Naveen Rao's "target/i386: SEV: Add support for
enabling VMSA SEV features":

https://lore.kernel.org/qemu-devel/cover.1761648149.git.naveen@kernel.org/

v3:
   - Merged IBPB-on-Entry and BTB Isolation into single patchseries
   - Addressed comments from Sean Christopherson, Pawan Gupta, kernel test robot
   - Simplified unnecessarily complicated logic in spectre_v2=eibrs-with-SNP fix
   - Reworded, rebased features on top of new SNP_ONLY_MASK etc. changes

v2:
[IBPB-on-Entry]
     - https://lore.kernel.org/kvm/20260203222405.4065706-1-kim.phillips@amd.com/
     - Change first patch's title (Nikunj)
     - Add reviews-by (Nikunj, Tom)
     - Change second patch's description to more generally explain what the patch does (Boris)
     - Add new, third patch renaming SNP_FEATURES_PRESENT->SNP_FEATURES_IMPL
[BTB Isolation]
     - https://lore.kernel.org/kvm/20260311130611.2201214-1-kim.phillips@amd.com/
     - Patch 1/3:
       - Address Dave Hansen's comment to adhere to using the IBRS_ENHANCED
         Intel feature flag also for AutoIBRS.

v1:
[IBPB-on-Entry] https://lore.kernel.org/kvm/20260126224205.1442196-1-kim.phillips@amd.com/
[BTB Isolation] https://lore.kernel.org/kvm/20260224180157.725159-1-kim.phillips@amd.com/

Kim Phillips (6):
  cpu/bugs: Allow forcing Automatic IBRS with SNP active using
    spectre_v2=eibrs
  cpu/bugs: Allow spectre_v2=ibrs on x86 vendors other than Intel
  KVM: SEV: Disallow setting SNP-only features for non-SNP guests via a
    single mask
  KVM: SEV: Advertise SVM_SEV_FEAT_SNP_ACTIVE
  KVM: SEV: Add support for IBPB-on-Entry
  KVM: SEV: Add support for SNP BTB Isolation

 arch/x86/include/asm/cpufeatures.h |  1 +
 arch/x86/include/asm/svm.h         |  7 +++++++
 arch/x86/kernel/cpu/bugs.c         | 18 +++++++++++-------
 arch/x86/kernel/cpu/common.c       |  6 +-----
 arch/x86/kvm/svm/sev.c             | 18 +++++++++++++++---
 5 files changed, 35 insertions(+), 15 deletions(-)


base-commit: 8726fc6dc93c62232fa625c1c91b97e21fff02b6

---

## [2] Kim Phillips — 2026-04-02
*Subject: [PATCH v3 1/6] cpu/bugs: Allow forcing Automatic IBRS with SNP active using spectre_v2=eibrs*

spectre_v2=eibrs currently enables retpolines when SNP is enabled,
instead of AutoIBRS (EIBRS) because the commit that disabled
AutoIBRS if SNP is enabled stopped short of enabling
X86_FEATURE_IBRS_ENHANCED.

Change the logic to enable X86_FEATURE_IBRS_ENHANCED, and move the
decision to switch to retpolines in the default/"auto" case in
spectre_v2_select_mitigation().  This allows the existing
spectre_v2=eibrs logic to work as intended.

Also emit a performance loss warning for using AutoIBRS with
SNP enabled.

Fixes: acaa4b5c4c85 ("x86/speculation: Do not enable Automatic IBRS if SEV-SNP is enabled")
Reported-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: Pawan Gupta <pawan.kumar.gupta@linux.intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Sean Christopherson <seanjc@google.com>
Cc: stable@kernel.org
Reported-by: kernel test robot <lkp@intel.com>
Closes: https://lore.kernel.org/oe-kbuild-all/202603121136.bc8zNsHS-lkp@intel.com/
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v3:
 - Addressed Pawan Gupta's comment and remove wrong SPECTRE_V2_CMD_FORCE ("=on") check
 - Addressed kernel test robot's !A || A && B is equivalent to !A || B warning
 - Preferred to add new AutoIBRS with SEV-SNP enabled performance warning instead
   of muting legacy IBRS in use vs. eIBRS messaging in the context of SNP, since
   SNP users' IBRS performance varies whether they enable SNP BTB Isolation

v2: https://lore.kernel.org/kvm/20260311130611.2201214-2-kim.phillips@amd.com/
 - Address Dave Hansen's comment to adhere to using the IBRS_ENHANCED
   Intel feature flag also for AutoIBRS.

v1:
 https://lore.kernel.org/kvm/20260224180157.725159-2-kim.phillips@amd.com/

 arch/x86/kernel/cpu/bugs.c   | 10 +++++++++-
 arch/x86/kernel/cpu/common.c |  6 +-----
 2 files changed, 10 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kernel/cpu/bugs.c b/arch/x86/kernel/cpu/bugs.c
index 83f51cab0b1e..dfefbde10646 100644
--- a/arch/x86/kernel/cpu/bugs.c
+++ b/arch/x86/kernel/cpu/bugs.c
@@ -1658,6 +1658,7 @@ static inline const char *spectre_v2_module_string(void) { return ""; }
 #define SPECTRE_V2_LFENCE_MSG "WARNING: LFENCE mitigation is not recommended for this CPU, data leaks possible!\n"
 #define SPECTRE_V2_EIBRS_EBPF_MSG "WARNING: Unprivileged eBPF is enabled with eIBRS on, data leaks possible via Spectre v2 BHB attacks!\n"
 #define SPECTRE_V2_EIBRS_LFENCE_EBPF_SMT_MSG "WARNING: Unprivileged eBPF is enabled with eIBRS+LFENCE mitigation and SMT, data leaks possible via Spectre v2 BHB attacks!\n"
+#define SPECTRE_V2_EIBRS_SNP_PERF_MSG "WARNING: AutoIBRS mitigation selected on SEV-SNP enabled CPU, this may cause unnecessary performance loss\n"
 #define SPECTRE_V2_IBRS_PERF_MSG "WARNING: IBRS mitigation selected on Enhanced IBRS CPU, this may cause unnecessary performance loss\n"
 
 #ifdef CONFIG_BPF_SYSCALL
@@ -2181,7 +2182,12 @@ static void __init spectre_v2_select_mitigation(void)
 			break;
 		fallthrough;
 	case SPECTRE_V2_CMD_FORCE:
-		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED)) {
+		/*
+		 * Don't use AutoIBRS when SNP is enabled because it degrades
+		 * host userspace indirect branch performance.
+		 */
+		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED) &&
+		    !boot_cpu_has(X86_FEATURE_SEV_SNP)) {
 			spectre_v2_enabled = SPECTRE_V2_EIBRS;
 			break;
 		}
@@ -2257,6 +2263,8 @@ static void __init spectre_v2_apply_mitigation(void)
 		return;
 
 	case SPECTRE_V2_EIBRS:
+		if (boot_cpu_has(X86_FEATURE_SEV_SNP))
+			pr_warn(SPECTRE_V2_EIBRS_SNP_PERF_MSG);
 		break;
 
 	case SPECTRE_V2_IBRS:
diff --git a/arch/x86/kernel/cpu/common.c b/arch/x86/kernel/cpu/common.c
index 4e1f0c4afe3a..0cdcbbedf883 100644
--- a/arch/x86/kernel/cpu/common.c
+++ b/arch/x86/kernel/cpu/common.c
@@ -1485,13 +1485,9 @@ static void __init cpu_set_bug_bits(struct cpuinfo_x86 *c)
 	/*
 	 * AMD's AutoIBRS is equivalent to Intel's eIBRS - use the Intel feature
 	 * flag and protect from vendor-specific bugs via the whitelist.
-	 *
-	 * Don't use AutoIBRS when SNP is enabled because it degrades host
-	 * userspace indirect branch performance.
 	 */
 	if ((x86_arch_cap_msr & ARCH_CAP_IBRS_ALL) ||
-	    (cpu_has(c, X86_FEATURE_AUTOIBRS) &&
-	     !cpu_feature_enabled(X86_FEATURE_SEV_SNP))) {
+	    cpu_has(c, X86_FEATURE_AUTOIBRS)) {
 		setup_force_cpu_cap(X86_FEATURE_IBRS_ENHANCED);
 		if (!cpu_matches(cpu_vuln_whitelist, NO_EIBRS_PBRSB) &&
 		    !(x86_arch_cap_msr & ARCH_CAP_PBRSB_NO))

---

## [3] Kim Phillips — 2026-04-02
*Subject: [PATCH v3 2/6] cpu/bugs: Allow spectre_v2=ibrs on x86 vendors other than Intel*

This is to prepare to allow legacy IBRS toggling on AMD systems,
where the BTB Isolation SEV-SNP feature can use it to optimize the
quick VM exit to re-entry path.

There is no reason this wasn't allowed in the first place, therefore
adding the cc: stable and Fixes: tags.

Fixes: 7c693f54c873 ("x86/speculation: Add spectre_v2=ibrs option to support Kernel IBRS")
Reported-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Pawan Gupta <pawan.kumar.gupta@linux.intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Sean Christopherson <seanjc@google.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v3: No changes
v2: No changes
    https://lore.kernel.org/kvm/20260311130611.2201214-3-kim.phillips@amd.com/
v1: https://lore.kernel.org/kvm/20260224180157.725159-3-kim.phillips@amd.com/

 arch/x86/kernel/cpu/bugs.c | 8 ++------
 1 file changed, 2 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kernel/cpu/bugs.c b/arch/x86/kernel/cpu/bugs.c
index dfefbde10646..eed5a72a870c 100644
--- a/arch/x86/kernel/cpu/bugs.c
+++ b/arch/x86/kernel/cpu/bugs.c
@@ -2153,11 +2153,6 @@ static void __init spectre_v2_select_mitigation(void)
 		spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
 	}
 
-	if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && boot_cpu_data.x86_vendor != X86_VENDOR_INTEL) {
-		pr_err("IBRS selected but not Intel CPU. Switching to AUTO select\n");
-		spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
-	}
-
 	if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && !boot_cpu_has(X86_FEATURE_IBRS)) {
 		pr_err("IBRS selected but CPU doesn't have IBRS. Switching to AUTO select\n");
 		spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
@@ -2250,7 +2245,8 @@ static void __init spectre_v2_apply_mitigation(void)
 		pr_err(SPECTRE_V2_EIBRS_EBPF_MSG);
 
 	if (spectre_v2_in_ibrs_mode(spectre_v2_enabled)) {
-		if (boot_cpu_has(X86_FEATURE_AUTOIBRS)) {
+		if (boot_cpu_has(X86_FEATURE_AUTOIBRS) &&
+		    spectre_v2_enabled != SPECTRE_V2_IBRS) {
 			msr_set_bit(MSR_EFER, _EFER_AUTOIBRS);
 		} else {
 			x86_spec_ctrl_base |= SPEC_CTRL_IBRS;

---

## [4] Kim Phillips — 2026-04-02
*Subject: [PATCH v3 3/6] KVM: SEV: Disallow setting SNP-only features for non-SNP guests via a single mask*

As SNP-only features get added, adding them to the valid_vmsa_features mask
in __sev_guest_init() often gets neglected.  Add SVM_SEV_FEAT_SNP_ONLY_MASK
to help group these common features together.

Suggested-by: Sean Christopherson <seanjc@google.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Link: https://lore.kernel.org/kvm/aaWog_UjW-M3412C@google.com/
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v3: new

 arch/x86/include/asm/svm.h | 2 ++
 arch/x86/kvm/svm/sev.c     | 2 +-
 2 files changed, 3 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index edde36097ddc..7e3f9d92351a 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -307,6 +307,8 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
 #define SVM_SEV_FEAT_SECURE_TSC				BIT(9)
 
+#define SVM_SEV_FEAT_SNP_ONLY_MASK	SVM_SEV_FEAT_SECURE_TSC
+
 #define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
 
 struct vmcb_seg {
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 3f9c1aa39a0a..2b4f3c05e282 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -456,7 +456,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 		return -EINVAL;
 
 	if (!snp_active)
-		valid_vmsa_features &= ~SVM_SEV_FEAT_SECURE_TSC;
+		valid_vmsa_features &= ~SVM_SEV_FEAT_SNP_ONLY_MASK;
 
 	if (data->vmsa_features & ~valid_vmsa_features)
 		return -EINVAL;

---

## [5] Kim Phillips — 2026-04-02
*Subject: [PATCH v3 4/6] KVM: SEV: Advertise SVM_SEV_FEAT_SNP_ACTIVE*

Allow userspace to set the flag in kvm_sev_init.flags.

KVM still needs to set the flag for backwards compatibility, but
disallowing SVM_SEV_FEAT_SNP_ACTIVE for an SNP guest is "bizarre."

Suggested-by: Sean Christopherson <seanjc@google.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Link: https://lore.kernel.org/kvm/aaWog_UjW-M3412C@google.com/
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v3: new

 arch/x86/include/asm/svm.h | 3 ++-
 arch/x86/kvm/svm/sev.c     | 8 ++++++--
 2 files changed, 8 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index 7e3f9d92351a..4f844a72890c 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -307,7 +307,8 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
 #define SVM_SEV_FEAT_SECURE_TSC				BIT(9)
 
-#define SVM_SEV_FEAT_SNP_ONLY_MASK	SVM_SEV_FEAT_SECURE_TSC
+#define SVM_SEV_FEAT_SNP_ONLY_MASK	(SVM_SEV_FEAT_SNP_ACTIVE | \
+					 SVM_SEV_FEAT_SECURE_TSC)
 
 #define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 2b4f3c05e282..9663424c0cf0 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3165,8 +3165,12 @@ void __init sev_hardware_setup(void)
 	    cpu_feature_enabled(X86_FEATURE_NO_NESTED_DATA_BP))
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
 
-	if (sev_snp_enabled && tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
-		sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+	if (sev_snp_enabled) {
+		sev_supported_vmsa_features |= SVM_SEV_FEAT_SNP_ACTIVE;
+
+		if (tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
+			sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+	}
 }
 
 void sev_hardware_unsetup(void)

---

## [6] Kim Phillips — 2026-04-02
*Subject: [PATCH v3 5/6] KVM: SEV: Add support for IBPB-on-Entry*

AMD EPYC 5th generation and above processors support IBPB-on-Entry
for SNP guests.  By invoking an Indirect Branch Prediction Barrier
(IBPB) on VMRUN, old indirect branch predictions are prevented
from influencing indirect branches within the guest.

SNP guests may choose to enable IBPB-on-Entry by setting
SEV_FEATURES bit 21 (IbpbOnEntry).

Host support for IBPB on Entry is indicated by CPUID
Fn8000_001F[IbpbOnEntry], bit 31.

If supported, indicate support for IBPB on Entry in
sev_supported_vmsa_features bit 23 (IbpbOnEntry).

For more info, refer to page 615, Section 15.36.17 "Side-Channel
Protection", AMD64 Architecture Programmer's Manual Volume 2: System
Programming Part 2, Pub. 24593 Rev. 3.42 - March 2024 (see Link).

Link: https://bugzilla.kernel.org/attachment.cgi?id=306250
Cc: Sean Christopherson <seanjc@google.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
v3: Rebased on top of new SNP_ONLY_MASK etc. changes
v2: https://lore.kernel.org/kvm/20260203222405.4065706-3-kim.phillips@amd.com/
    - Added Tom's Reviewed-by.
v1: https://lore.kernel.org/kvm/20260126224205.1442196-3-kim.phillips@amd.com/

 arch/x86/include/asm/cpufeatures.h | 1 +
 arch/x86/include/asm/svm.h         | 4 +++-
 arch/x86/kvm/svm/sev.c             | 3 +++
 3 files changed, 7 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index dbe104df339b..236411a1a86a 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -459,6 +459,7 @@
 #define X86_FEATURE_ALLOWED_SEV_FEATURES (19*32+27) /* Allowed SEV Features */
 #define X86_FEATURE_SVSM		(19*32+28) /* "svsm" SVSM present */
 #define X86_FEATURE_HV_INUSE_WR_ALLOWED	(19*32+30) /* Allow Write to in-use hypervisor-owned pages */
+#define X86_FEATURE_IBPB_ON_ENTRY	(19*32+31) /* SEV-SNP IBPB on VM Entry */
 
 /* AMD-defined Extended Feature 2 EAX, CPUID level 0x80000021 (EAX), word 20 */
 #define X86_FEATURE_NO_NESTED_DATA_BP	(20*32+ 0) /* No Nested Data Breakpoints */
diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index 4f844a72890c..2a2b8705b2c0 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -306,9 +306,11 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_ALTERNATE_INJECTION		BIT(4)
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
 #define SVM_SEV_FEAT_SECURE_TSC				BIT(9)
+#define SVM_SEV_FEAT_IBPB_ON_ENTRY			BIT(21)
 
 #define SVM_SEV_FEAT_SNP_ONLY_MASK	(SVM_SEV_FEAT_SNP_ACTIVE | \
-					 SVM_SEV_FEAT_SECURE_TSC)
+					 SVM_SEV_FEAT_SECURE_TSC | \
+					 SVM_SEV_FEAT_IBPB_ON_ENTRY)
 
 #define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 9663424c0cf0..561023486253 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3170,6 +3170,9 @@ void __init sev_hardware_setup(void)
 
 		if (tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
 			sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+
+		if (cpu_feature_enabled(X86_FEATURE_IBPB_ON_ENTRY))
+			sev_supported_vmsa_features |= SVM_SEV_FEAT_IBPB_ON_ENTRY;
 	}
 }

---

## [7] Kim Phillips — 2026-04-02
*Subject: [PATCH v3 6/6] KVM: SEV: Add support for SNP BTB Isolation*

Advertise support for BTB Isolation via SEV_VMSA_FEATURES when SNP is
enabled, as all hardware that supports SNP also support BTB Isolation.
BTB Isolation is an optional feature that can be enabled by the guest to
ensure its guest Branch Target Buffers (BTBs) are not
affected by any context outside that guest.

SNP-active guests may choose to enable the Branch Target Buffer
Isolation mode through SEV_FEATURES bit 7 (BTBIsolation).

For more info, refer to page 615, Section 15.36.17 "Side-Channel
Protection", AMD64 Architecture Programmer's Manual Volume 2: System
Programming Part 2, Pub. 24593 Rev. 3.42 - March 2024 (see Link).

Link: https://bugzilla.kernel.org/attachment.cgi?id=306250
Cc: Sean Christopherson <seanjc@google.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v3: Reworded, Rebased on top of new SNP_ONLY_MASK etc. changes
v2: https://lore.kernel.org/kvm/20260203222405.4065706-3-kim.phillips@amd.com/
    - Added Tom's Reviewed-by.
v1: https://lore.kernel.org/kvm/20260126224205.1442196-3-kim.phillips@amd.com/

 arch/x86/include/asm/svm.h | 2 ++
 arch/x86/kvm/svm/sev.c     | 7 ++++++-
 2 files changed, 8 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index 2a2b8705b2c0..d3a15a40a09b 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -305,10 +305,12 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_RESTRICTED_INJECTION		BIT(3)
 #define SVM_SEV_FEAT_ALTERNATE_INJECTION		BIT(4)
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
+#define SVM_SEV_FEAT_BTB_ISOLATION			BIT(7)
 #define SVM_SEV_FEAT_SECURE_TSC				BIT(9)
 #define SVM_SEV_FEAT_IBPB_ON_ENTRY			BIT(21)
 
 #define SVM_SEV_FEAT_SNP_ONLY_MASK	(SVM_SEV_FEAT_SNP_ACTIVE | \
+					 SVM_SEV_FEAT_BTB_ISOLATION | \
 					 SVM_SEV_FEAT_SECURE_TSC | \
 					 SVM_SEV_FEAT_IBPB_ON_ENTRY)
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 561023486253..733423000bc8 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3166,7 +3166,12 @@ void __init sev_hardware_setup(void)
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
 
 	if (sev_snp_enabled) {
-		sev_supported_vmsa_features |= SVM_SEV_FEAT_SNP_ACTIVE;
+		/*
+		 * Some SNP-only features such as BTB Isolation are
+		 * available on all systems that support SNP.
+		 */
+		sev_supported_vmsa_features |= SVM_SEV_FEAT_SNP_ACTIVE |
+					       SVM_SEV_FEAT_BTB_ISOLATION;
 
 		if (tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
 			sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;

---

## [8] Pawan Gupta — 2026-04-28
*Subject: Re: [PATCH v3 1/6] cpu/bugs: Allow forcing Automatic IBRS with SNP
 active using spectre_v2=eibrs*

On Thu, Apr 02, 2026 at 03:25:53PM -0500, Kim Phillips wrote:
> spectre_v2=eibrs currently enables retpolines when SNP is enabled,
> instead of AutoIBRS (EIBRS) because the commit that disabled

The retpoline switch happens in force case(=on) too.

> spectre_v2_select_mitigation().  This allows the existing
> spectre_v2=eibrs logic to work as intended.

Reviewed-by: Pawan Gupta <pawan.kumar.gupta@linux.intel.com>

---

## [9] Kim Phillips — 2026-04-28
*Subject: Re: [PATCH v3 1/6] cpu/bugs: Allow forcing Automatic IBRS with SNP
 active using spectre_v2=eibrs*

On 4/28/26 11:49 AM, Pawan Gupta wrote:
> On Thu, Apr 02, 2026 at 03:25:53PM -0500, Kim Phillips wrote:
>> spectre_v2=eibrs currently enables retpolines when SNP is enabled,

That's right, for default/"=auto"/"=on", if SNP is enabled, retpolines.
If SNP is not enabled, AutoIBRS.  I'm assuming that's the desired
behaviour.

I'll amend the commit text in the next version if more reasons
arise to submit one.

>> spectre_v2_select_mitigation().  This allows the existing
>> spectre_v2=eibrs logic to work as intended.

Thanks,

Kim

---

## [10] Borislav Petkov — 2026-05-08
*Subject: Re: [PATCH v3 0/6] KVM: SEV: Add support for IBPB-on-Entry and BTB
 Isolation*

On Thu, Apr 02, 2026 at 03:25:52PM -0500, Kim Phillips wrote:
> IBPB-on-Entry and BTB Isolation are supplemental Spectre V2 mitigations
> available to SNP guests.

Sashiko has a bunch of comments, pls address them:

https://sashiko.dev/#/patchset/20260402202558.195005-1-kim.phillips%40amd.com

Thx.

---
