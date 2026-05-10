---
title: 'KVM: SEV: Add support for BTB Isolation'
date: 2026-02-24
last_reply: 2026-02-24
message_count: 7
participants: ['Kim Phillips', 'Dave Hansen', 'Jim Mattson', 'Borislav Petkov']
---

## [1] Kim Phillips — 2026-02-24

This feature ensures SNP guest Branch Target Buffers (BTBs) are not
affected by context outside that guest.

The first patch fixes a longstanding bug where users couldn't select
Automatic IBRS on AMD machines using spectre_v2=eibrs on the kcmdline.

The second patch fixes another longstanding bug where users couldn't
select legacy / toggling SPEC_CTRL[IBRS] on AMD systems, which may
be used by users of the BTB Isolation feature.

The third patch adds support for the feature by adding it to the
supported features bitmask.

Based on git://git.kernel.org/pub/scm/virt/kvm/kvm.git next,
currently b1195183ed42 (tag: tags/kvm-7.0-1, kvm/queue, kvm/next).

This series also available here:

https://github.com/AMDESE/linux/tree/btb-isol-latest

Advance qemu bits (to add btb-isol=on/off switch) available here:

https://github.com/AMDESE/qemu/tree/btb-isol-latest

Qemu bits will be posted upstream once kernel bits are merged.
They depend on Naveen Rao's "target/i386: SEV: Add support for
enabling VMSA SEV features":

https://lore.kernel.org/qemu-devel/cover.1761648149.git.naveen@kernel.org/

Kim Phillips (3):
  cpu/bugs: Fix selecting Automatic IBRS using spectre_v2=eibrs
  cpu/bugs: Allow spectre_v2=ibrs on x86 vendors other than Intel
  KVM: SEV: Add support for SNP BTB Isolation

 arch/x86/include/asm/svm.h |  1 +
 arch/x86/kernel/cpu/bugs.c | 16 +++++++---------
 arch/x86/kvm/svm/sev.c     |  3 +++
 3 files changed, 11 insertions(+), 9 deletions(-)


base-commit: b1195183ed42f1522fae3fe44ebee3af437aa000

---

## [2] Kim Phillips — 2026-02-24
*Subject: [PATCH 1/3] cpu/bugs: Fix selecting Automatic IBRS using spectre_v2=eibrs*

The original commit that added support for Automatic IBRS neglected
to amend a condition to include AUTOIBRS in addition to the
X86_FEATURE_IBRS_ENHANCED check.  Fix that, and another couple
of minor outliers.

Fixes: e7862eda309e ("x86/cpu: Support AMD Automatic IBRS")
Reported-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
 arch/x86/kernel/cpu/bugs.c | 9 ++++++---
 1 file changed, 6 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kernel/cpu/bugs.c b/arch/x86/kernel/cpu/bugs.c
index d0a2847a4bb0..4eefbff4b19a 100644
--- a/arch/x86/kernel/cpu/bugs.c
+++ b/arch/x86/kernel/cpu/bugs.c
@@ -2136,7 +2136,8 @@ static void __init spectre_v2_select_mitigation(void)
 	if ((spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS ||
 	     spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS_LFENCE ||
 	     spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS_RETPOLINE) &&
-	    !boot_cpu_has(X86_FEATURE_IBRS_ENHANCED)) {
+	    !(boot_cpu_has(X86_FEATURE_IBRS_ENHANCED) ||
+	      boot_cpu_has(X86_FEATURE_AUTOIBRS))) {
 		pr_err("EIBRS selected but CPU doesn't have Enhanced or Automatic IBRS. Switching to AUTO select\n");
 		spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
 	}
@@ -2182,7 +2183,8 @@ static void __init spectre_v2_select_mitigation(void)
 			break;
 		fallthrough;
 	case SPECTRE_V2_CMD_FORCE:
-		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED)) {
+		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED) ||
+		    boot_cpu_has(X86_FEATURE_AUTOIBRS)) {
 			spectre_v2_enabled = SPECTRE_V2_EIBRS;
 			break;
 		}
@@ -2262,7 +2264,8 @@ static void __init spectre_v2_apply_mitigation(void)
 
 	case SPECTRE_V2_IBRS:
 		setup_force_cpu_cap(X86_FEATURE_KERNEL_IBRS);
-		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED))
+		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED) ||
+		    boot_cpu_has(X86_FEATURE_AUTOIBRS))
 			pr_warn(SPECTRE_V2_IBRS_PERF_MSG);
 		break;

---

## [3] Kim Phillips — 2026-02-24
*Subject: [PATCH 2/3] cpu/bugs: Allow spectre_v2=ibrs on x86 vendors other than Intel*

This is to prepare to allow legacy IBRS toggling on AMD systems,
where the BTB Isolation SEV-SNP feature can use it to optimize the
quick VM exit to re-entry path.

There is no reason this wasn't allowed in the first place, therefore
adding the cc: stable and Fixes: tags.

Fixes: 7c693f54c873 ("x86/speculation: Add spectre_v2=ibrs option to support Kernel IBRS")
Reported-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Pawan Gupta <pawan.kumar.gupta@linux.intel.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
 arch/x86/kernel/cpu/bugs.c | 7 +------
 1 file changed, 1 insertion(+), 6 deletions(-)

diff --git a/arch/x86/kernel/cpu/bugs.c b/arch/x86/kernel/cpu/bugs.c
index 4eefbff4b19a..67eff5fba629 100644
--- a/arch/x86/kernel/cpu/bugs.c
+++ b/arch/x86/kernel/cpu/bugs.c
@@ -2154,11 +2154,6 @@ static void __init spectre_v2_select_mitigation(void)
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
@@ -2247,7 +2242,7 @@ static void __init spectre_v2_apply_mitigation(void)
 		pr_err(SPECTRE_V2_EIBRS_EBPF_MSG);
 
 	if (spectre_v2_in_ibrs_mode(spectre_v2_enabled)) {
-		if (boot_cpu_has(X86_FEATURE_AUTOIBRS)) {
+		if (boot_cpu_has(X86_FEATURE_AUTOIBRS) && spectre_v2_enabled != SPECTRE_V2_IBRS) {
 			msr_set_bit(MSR_EFER, _EFER_AUTOIBRS);
 		} else {
 			x86_spec_ctrl_base |= SPEC_CTRL_IBRS;

---

## [4] Kim Phillips — 2026-02-24
*Subject: [PATCH 3/3] KVM: SEV: Add support for SNP BTB Isolation*

This feature ensures SNP guest Branch Target Buffers (BTBs) are not
affected by context outside that guest.  CPU hardware tracks each
guest's BTB entries and can flush the BTB if it has been determined
to be contaminated with any prediction information originating outside
the particular guest's context.

To mitigate possible performance penalties incurred by these flushes,
it is recommended that the hypervisor runs with SPEC_CTRL[IBRS] set.
Note that using Automatic IBRS is not an equivalent option here, since
it behaves differently when SEV-SNP is active.  See commit acaa4b5c4c85
("x86/speculation: Do not enable Automatic IBRS if SEV-SNP is enabled")
for more details.

Indicate support for BTB Isolation in sev_supported_vmsa_features,
bit 7.

SNP-active guests can enable (BTB) Isolation through SEV_Status
bit 9 (SNPBTBIsolation).

For more info, refer to page 615, Section 15.36.17 "Side-Channel
Protection", AMD64 Architecture Programmer's Manual Volume 2: System
Programming Part 2, Pub. 24593 Rev. 3.42 - March 2024 (see Link).

Link: https://bugzilla.kernel.org/attachment.cgi?id=306250
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
 arch/x86/include/asm/svm.h | 1 +
 arch/x86/kvm/svm/sev.c     | 3 +++
 2 files changed, 4 insertions(+)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index edde36097ddc..2038461c1316 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -305,6 +305,7 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_RESTRICTED_INJECTION		BIT(3)
 #define SVM_SEV_FEAT_ALTERNATE_INJECTION		BIT(4)
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
+#define SVM_SEV_FEAT_BTB_ISOLATION			BIT(7)
 #define SVM_SEV_FEAT_SECURE_TSC				BIT(9)
 
 #define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index ea515cf41168..3c0278871114 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3167,6 +3167,9 @@ void __init sev_hardware_setup(void)
 
 	if (sev_snp_enabled && tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+
+	if (sev_snp_enabled)
+		sev_supported_vmsa_features |= SVM_SEV_FEAT_BTB_ISOLATION;
 }
 
 void sev_hardware_unsetup(void)

---

## [5] Dave Hansen — 2026-02-24
*Subject: Re: [PATCH 1/3] cpu/bugs: Fix selecting Automatic IBRS using
 spectre_v2=eibrs*

On 2/24/26 10:01, Kim Phillips wrote:
> @@ -2136,7 +2136,8 @@ static void __init spectre_v2_select_mitigation(void)
>  	if ((spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS ||

Didn't we agree to just use the "Intel feature" name? See this existing
code:

>         /*
>          * AMD's AutoIBRS is equivalent to Intel's eIBRS - use the Intel feature

You're probably not seeing X86_FEATURE_IBRS_ENHANCED because it doesn't
get forced under SNP.

---

## [6] Jim Mattson — 2026-02-24
*Subject: Re: [PATCH 1/3] cpu/bugs: Fix selecting Automatic IBRS using spectre_v2=eibrs*

On Tue, Feb 24, 2026 at 10:23 AM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 2/24/26 10:01, Kim Phillips wrote:

Aren't they quite different? IIRC, IBRS_ENHANCED protects host
userspace from guest indirect branch steering (i.e. VMSCAPE style
attacks), but AUTOIBRS does not.

---

## [7] Borislav Petkov — 2026-02-24
*Subject: Re: [PATCH 1/3] cpu/bugs: Fix selecting Automatic IBRS using spectre_v2=eibrs*

On February 24, 2026 6:22:36 PM UTC, Dave Hansen <dave.hansen@intel.com> wrote:
>On 2/24/26 10:01, Kim Phillips wrote:
>> @@ -2136,7 +2136,8 @@ static void __init spectre_v2_select_mitigation(void)

Set the Intel flag somewhere in the SNP init path...?

---
