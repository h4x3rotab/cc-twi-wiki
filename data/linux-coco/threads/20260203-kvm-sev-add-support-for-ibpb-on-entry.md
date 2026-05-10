---
title: 'KVM: SEV: Add support for IBPB-on-Entry'
date: 2026-02-03
last_reply: 2026-03-02
message_count: 6
participants: ['Kim Phillips', 'Borislav Petkov', 'Sean Christopherson']
---

## [1] Kim Phillips — 2026-02-03

AMD EPYC 5th generation and above processors support IBPB-on-Entry
for SNP guests.  By invoking an Indirect Branch Prediction Barrier
(IBPB) on VMRUN, old indirect branch predictions are prevented
from influencing indirect branches within the guest.

The first patch is guest-side support which unmasks the Zen5+ feature
bit to allow kernel guests to set the feature.

The second patch is host-side support that checks the CPUID and
then sets the feature bit in the VMSA supported features mask.

The third patch is a trivial #define rename that was a result of
the review discussion from v1's 2/2, to clarify SEV features
that are implemented in the guest.

Based on https://github.com/kvm-x86/linux kvm-x86/next
(currently v6.19-rc6-182-ge944fe2c09f4).

This v2 series now also available here:

https://github.com/AMDESE/linux/tree/ibpb-on-entry-latest

Advance qemu bits (to add ibpb-on-entry=on/off switch) available here:

https://github.com/AMDESE/qemu/tree/ibpb-on-entry-latest

Qemu bits will be posted upstream once kernel bits are merged.
They depend on Naveen Rao's "target/i386: SEV: Add support for
enabling VMSA SEV features":

https://lore.kernel.org/qemu-devel/cover.1761648149.git.naveen@kernel.org/
---
v2:
     - Change first patch's title (Nikunj)
     - Add reviews-by (Nikunj, Tom)
     - Change second patch's description to more generally explain what the patch does (Boris)
     - Add new, third patch renaming SNP_FEATURES_PRESENT->SNP_FEATURES_IMPL

v1: https://lore.kernel.org/kvm/20260126224205.1442196-1-kim.phillips@amd.com/

Kim Phillips (3):
  x86/sev: Allow IBPB-on-Entry feature for SNP guests
  KVM: SEV: Add support for IBPB-on-Entry
  x86/sev: Rename SNP_FEATURES_PRESENT->SNP_FEATURES_IMPL

 arch/x86/boot/compressed/sev.c     | 7 ++++---
 arch/x86/coco/sev/core.c           | 1 +
 arch/x86/include/asm/cpufeatures.h | 1 +
 arch/x86/include/asm/msr-index.h   | 5 ++++-
 arch/x86/include/asm/svm.h         | 1 +
 arch/x86/kvm/svm/sev.c             | 9 ++++++++-
 6 files changed, 19 insertions(+), 5 deletions(-)


base-commit: e944fe2c09f405a2e2d147145c9b470084bc4c9a

---

## [2] Kim Phillips — 2026-02-03
*Subject: [PATCH v2 1/3] x86/sev: Allow IBPB-on-Entry feature for SNP guests*

The SEV-SNP IBPB-on-Entry feature does not require a guest-side
implementation. The feature was added in Zen5 h/w, after the first
SNP Zen implementation, and thus was not accounted for when the
initial set of SNP features were added to the kernel.

In its abundant precaution, commit 8c29f0165405 ("x86/sev: Add SEV-SNP
guest feature negotiation support") included SEV_STATUS' IBPB-on-Entry
bit as a reserved bit, thereby masking guests from using the feature.

Allow guests to make use of IBPB-on-Entry when supported by the
hypervisor, as the bit is now architecturally defined and safe to
expose.

Fixes: 8c29f0165405 ("x86/sev: Add SEV-SNP guest feature negotiation support")
Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: Michael Roth <michael.roth@amd.com>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v2:
 - Change title (Nikunj)
 - Add reviews-by (Nikunj, Tom)
 - Change the description to more generally explain what the patch does (Boris)
v1: https://lore.kernel.org/kvm/20260126224205.1442196-2-kim.phillips@amd.com/

 arch/x86/boot/compressed/sev.c   | 1 +
 arch/x86/coco/sev/core.c         | 1 +
 arch/x86/include/asm/msr-index.h | 5 ++++-
 3 files changed, 6 insertions(+), 1 deletion(-)

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index c8c1464b3a56..2b639703b8dd 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -188,6 +188,7 @@ bool sev_es_check_ghcb_fault(unsigned long address)
 				 MSR_AMD64_SNP_RESERVED_BIT13 |		\
 				 MSR_AMD64_SNP_RESERVED_BIT15 |		\
 				 MSR_AMD64_SNP_SECURE_AVIC |		\
+				 MSR_AMD64_SNP_RESERVED_BITS19_22 |	\
 				 MSR_AMD64_SNP_RESERVED_MASK)
 
 #ifdef CONFIG_AMD_SECURE_AVIC
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 9ae3b11754e6..13f608117411 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -122,6 +122,7 @@ static const char * const sev_status_feat_names[] = {
 	[MSR_AMD64_SNP_VMSA_REG_PROT_BIT]	= "VMSARegProt",
 	[MSR_AMD64_SNP_SMT_PROT_BIT]		= "SMTProt",
 	[MSR_AMD64_SNP_SECURE_AVIC_BIT]		= "SecureAVIC",
+	[MSR_AMD64_SNP_IBPB_ON_ENTRY_BIT]	= "IBPBOnEntry",
 };
 
 /*
diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index 4d3566bb1a93..9016a6b00bc7 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -735,7 +735,10 @@
 #define MSR_AMD64_SNP_SMT_PROT		BIT_ULL(MSR_AMD64_SNP_SMT_PROT_BIT)
 #define MSR_AMD64_SNP_SECURE_AVIC_BIT	18
 #define MSR_AMD64_SNP_SECURE_AVIC	BIT_ULL(MSR_AMD64_SNP_SECURE_AVIC_BIT)
-#define MSR_AMD64_SNP_RESV_BIT		19
+#define MSR_AMD64_SNP_RESERVED_BITS19_22 GENMASK_ULL(22, 19)
+#define MSR_AMD64_SNP_IBPB_ON_ENTRY_BIT	23
+#define MSR_AMD64_SNP_IBPB_ON_ENTRY	BIT_ULL(MSR_AMD64_SNP_IBPB_ON_ENTRY_BIT)
+#define MSR_AMD64_SNP_RESV_BIT		24
 #define MSR_AMD64_SNP_RESERVED_MASK	GENMASK_ULL(63, MSR_AMD64_SNP_RESV_BIT)
 #define MSR_AMD64_SAVIC_CONTROL		0xc0010138
 #define MSR_AMD64_SAVIC_EN_BIT		0

---

## [3] Kim Phillips — 2026-02-03
*Subject: [PATCH v2 2/3] KVM: SEV: Add support for IBPB-on-Entry*

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
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
v2: Added Tom's Reviewed-by.
v1: https://lore.kernel.org/kvm/20260126224205.1442196-3-kim.phillips@amd.com/

 arch/x86/include/asm/cpufeatures.h | 1 +
 arch/x86/include/asm/svm.h         | 1 +
 arch/x86/kvm/svm/sev.c             | 9 ++++++++-
 3 files changed, 10 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index c01fdde465de..3ce5dff36f78 100644
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
index edde36097ddc..eebc65ec948f 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -306,6 +306,7 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_ALTERNATE_INJECTION		BIT(4)
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
 #define SVM_SEV_FEAT_SECURE_TSC				BIT(9)
+#define SVM_SEV_FEAT_IBPB_ON_ENTRY			BIT(21)
 
 #define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index ea515cf41168..8a6d25db0c00 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3165,8 +3165,15 @@ void __init sev_hardware_setup(void)
 	    cpu_feature_enabled(X86_FEATURE_NO_NESTED_DATA_BP))
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
 
-	if (sev_snp_enabled && tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
+	if (!sev_snp_enabled)
+		return;
+	/* the following feature bit checks are SNP specific */
+
+	if (tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+
+	if (cpu_feature_enabled(X86_FEATURE_IBPB_ON_ENTRY))
+		sev_supported_vmsa_features |= SVM_SEV_FEAT_IBPB_ON_ENTRY;
 }
 
 void sev_hardware_unsetup(void)

---

## [4] Kim Phillips — 2026-02-03
*Subject: [PATCH v2 3/3] x86/sev: Rename SNP_FEATURES_PRESENT->SNP_FEATURES_IMPL*

Rename SNP_FEATURES_PRESENT->SNP_FEATURES_IMPL to denote its
counterpart relationship with SNP_FEATURES_IMPL_REQ.

Fixes: 8c29f0165405 ("x86/sev: Add SEV-SNP guest feature negotiation support")
Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Suggested-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Nikunj A Dadhania <nikunj@amd.com>
Cc: Michael Roth <michael.roth@amd.com>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v2: new this series

 arch/x86/boot/compressed/sev.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 2b639703b8dd..aca5313d193c 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -198,11 +198,11 @@ bool sev_es_check_ghcb_fault(unsigned long address)
 #endif
 
 /*
- * SNP_FEATURES_PRESENT is the mask of SNP features that are implemented
+ * SNP_FEATURES_IMPL is the mask of SNP features that are implemented
  * by the guest kernel. As and when a new feature is implemented in the
  * guest kernel, a corresponding bit should be added to the mask.
  */
-#define SNP_FEATURES_PRESENT	(MSR_AMD64_SNP_DEBUG_SWAP |	\
+#define SNP_FEATURES_IMPL	(MSR_AMD64_SNP_DEBUG_SWAP |	\
 				 MSR_AMD64_SNP_SECURE_TSC |	\
 				 SNP_FEATURE_SECURE_AVIC)
 
@@ -211,7 +211,7 @@ u64 snp_get_unsupported_features(u64 status)
 	if (!(status & MSR_AMD64_SEV_SNP_ENABLED))
 		return 0;
 
-	return status & SNP_FEATURES_IMPL_REQ & ~SNP_FEATURES_PRESENT;
+	return status & SNP_FEATURES_IMPL_REQ & ~SNP_FEATURES_IMPL;
 }
 
 void snp_check_features(void)

---

## [5] Borislav Petkov — 2026-02-28
*Subject: Re: [PATCH v2 2/3] KVM: SEV: Add support for IBPB-on-Entry*

Sean, ack for the KVM bits and me taking them thru tip?

On Tue, Feb 03, 2026 at 04:24:04PM -0600, Kim Phillips wrote:
> AMD EPYC 5th generation and above processors support IBPB-on-Entry
> for SNP guests.  By invoking an Indirect Branch Prediction Barrier

---

## [6] Sean Christopherson — 2026-03-02
*Subject: Re: [PATCH v2 2/3] KVM: SEV: Add support for IBPB-on-Entry*

On Sat, Feb 28, 2026, Borislav Petkov wrote:
> Sean, ack for the KVM bits and me taking them thru tip?

Ya, should be fine for this to go through tip.

> On Tue, Feb 03, 2026 at 04:24:04PM -0600, Kim Phillips wrote:
> > AMD EPYC 5th generation and above processors support IBPB-on-Entry

...

> > diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
> > index ea515cf41168..8a6d25db0c00 100644

I think I'd prefer to nest the if-statement, e.g.

	if (sev_snp_enabled) {
		if (tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
			sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;

		if (cpu_feature_enabled(X86_FEATURE_IBPB_ON_ENTRY))
			sev_supported_vmsa_features |= SVM_SEV_FEAT_IBPB_ON_ENTRY;
	}

I'm mildly concerned that'll we'll overlook the early return and unintentionally
bury common code in the SNP-section tail.

More importantly, this patch is buggy.  __sev_guest_init() needs to disallow
setting SVM_SEV_FEAT_IBPB_ON_ENTRY for non-SNP guests.

As a follow-up, I also think we should advertise SVM_SEV_FEAT_SNP_ACTIVE and
allow userspace to set the flag in kvm_sev_init.flags.  KVM still needs to set
the flag for backwards compatibility, but disallowing SVM_SEV_FEAT_SNP_ACTIVE
for an SNP guest is bizarre.

E.g. across 2 or 3 patches:

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index edde36097ddc..7db1bfce4cca 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -307,6 +307,10 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_DEBUG_SWAP                                BIT(5)
 #define SVM_SEV_FEAT_SECURE_TSC                                BIT(9)
 
+#define SVM_SEV_FEAT_SNP_ONLY_MASK     (SVM_SEV_FEAT_SNP_ACTIVE | \
+                                        SVM_SEV_FEAT_SECURE_TSC | \
+                                        SVM_SEV_FEAT_IBPB_ON_ENTRY)
+
 #define VMCB_ALLOWED_SEV_FEATURES_VALID                        BIT_ULL(63)
 
 struct vmcb_seg {
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 41385573629e..b2fe0fa11f90 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -500,7 +500,7 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
                return -EINVAL;
 
        if (!snp_active)
-               valid_vmsa_features &= ~SVM_SEV_FEAT_SECURE_TSC;
+               valid_vmsa_features &= ~SVM_SEV_FEAT_SNP_ONLY_MASK;
 
        if (data->vmsa_features & ~valid_vmsa_features)
                return -EINVAL;
@@ -3218,8 +3218,15 @@ void __init sev_hardware_setup(void)
            cpu_feature_enabled(X86_FEATURE_NO_NESTED_DATA_BP))
                sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
 
-       if (sev_snp_enabled && tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
-               sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+       if (sev_snp_enabled) {
+               sev_supported_vmsa_features |= SVM_SEV_FEAT_SNP_ACTIVE;
+
+               if (tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
+                       sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+
+               if (cpu_feature_enabled(X86_FEATURE_IBPB_ON_ENTRY))
+                       sev_supported_vmsa_features |= SVM_SEV_FEAT_IBPB_ON_ENTRY;
+       }
 }
 
 void sev_hardware_unsetup(void)

---
