---
title: 'KVM: SEV: Add support for the ALLOWED_SEV_FEATURES feature'
date: 2024-08-22
last_reply: 2024-08-25
message_count: 5
participants: ['Kim Phillips', 'Sean Christopherson', 'Thomas Gleixner']
---

## [1] Kim Phillips — 2024-08-22

AMD EPYC 5th generation processors have introduced a feature that allows
the hypervisor to control the SEV_FEATURES that are set for, or by, a
guest.  ALLOWED_SEV_FEATURES can be used by the hypervisor to enforce
that SEV-ES and SEV-SNP guests cannot enable features that the
hypervisor does not want to be enabled.

Patch 1/2 adds support to detect the feature.

Patch 2/2 configures the ALLOWED_SEV_FEATURES field in the VMCB
according to the features the hypervisor supports.

Based on tip/master commit a2767e7f31ad ("Merge branch into tip/master: 'x86/timers'")

v2:
 - Added some SEV_FEATURES require to be explicitly allowed by
   ALLOWED_SEV_FEATURES wording (Sean).
 - Added Nikunj's Reviewed-by.

v1:
 https://lore.kernel.org/lkml/20240802015732.3192877-1-kim.phillips@amd.com/

Kim Phillips (2):
  x86/cpufeatures: Add "Allowed SEV Features" Feature
  KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB Field

 arch/x86/include/asm/cpufeatures.h | 1 +
 arch/x86/include/asm/svm.h         | 6 +++++-
 arch/x86/kvm/svm/sev.c             | 5 +++++
 3 files changed, 11 insertions(+), 1 deletion(-)

---

## [2] Kim Phillips — 2024-08-22
*Subject: [PATCH v2 1/2] x86/cpufeatures: Add "Allowed SEV Features" Feature*

Add CPU feature detection for "Allowed SEV Features" to allow the
Hypervisor to enforce that SEV-ES and SEV-SNP guest VMs cannot
enable features (via SEV_FEATURES) that the Hypervisor does not
support or wish to be enabled.

Signed-off-by: Kishon Vijay Abraham I <kvijayab@amd.com>
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v2: no changes

 arch/x86/include/asm/cpufeatures.h | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index dd4682857c12..0c73da91a041 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -447,6 +447,7 @@
 #define X86_FEATURE_V_TSC_AUX		(19*32+ 9) /* Virtual TSC_AUX */
 #define X86_FEATURE_SME_COHERENT	(19*32+10) /* AMD hardware-enforced cache coherency */
 #define X86_FEATURE_DEBUG_SWAP		(19*32+14) /* "debug_swap" AMD SEV-ES full debug state swap support */
+#define X86_FEATURE_ALLOWED_SEV_FEATURES (19*32+27) /* AMD Allowed SEV Features */
 #define X86_FEATURE_SVSM		(19*32+28) /* "svsm" SVSM present */
 
 /* AMD-defined Extended Feature 2 EAX, CPUID level 0x80000021 (EAX), word 20 */

---

## [3] Kim Phillips — 2024-08-22
*Subject: [PATCH v2 2/2] KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB Field*

AMD EPYC 5th generation processors have introduced a feature that allows
the hypervisor to control the SEV_FEATURES that are set for, or by, a
guest [1].  ALLOWED_SEV_FEATURES can be used by the hypervisor to enforce
that SEV-ES and SEV-SNP guests cannot enable features that the
hypervisor does not want to be enabled.

When ALLOWED_SEV_FEATURES is enabled, a VMRUN will fail if any
non-reserved bits are 1 in SEV_FEATURES but are 0 in
ALLOWED_SEV_FEATURES.

Some SEV_FEATURES (currently PmcVirtualization and SecureAvic according
to Appendix B, Table B-4) require an opt-in via ALLOWED_SEV_FEATURES,
i.e. are off-by-default, whereas all other features are effectively
on-by-default, but still honor ALLOWED_SEV_FEATURES.

[1] Section 15.36.20 "Allowed SEV Features", AMD64 Architecture
    Programmer's Manual, Pub. 24593 Rev. 3.42 - March 2024:
    https://bugzilla.kernel.org/attachment.cgi?id=306250

Signed-off-by: Kishon Vijay Abraham I <kvijayab@amd.com>
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
Reviewed-by: Nikunj A. Dadhania <nikunj@amd.com>
---
v2:
 - Added some SEV_FEATURES require to be explicitly allowed by
   ALLOWED_SEV_FEATURES wording (Sean).
 - Added Nikunj's Reviewed-by.

v1:
 https://lore.kernel.org/lkml/20240802015732.3192877-3-kim.phillips@amd.com/

 arch/x86/include/asm/svm.h | 6 +++++-
 arch/x86/kvm/svm/sev.c     | 5 +++++
 2 files changed, 10 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index f0dea3750ca9..59516ad2028b 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -158,7 +158,9 @@ struct __attribute__ ((__packed__)) vmcb_control_area {
 	u64 avic_physical_id;	/* Offset 0xf8 */
 	u8 reserved_7[8];
 	u64 vmsa_pa;		/* Used for an SEV-ES guest */
-	u8 reserved_8[720];
+	u8 reserved_8[40];
+	u64 allowed_sev_features;	/* Offset 0x138 */
+	u8 reserved_9[672];
 	/*
 	 * Offset 0x3e0, 32 bytes reserved
 	 * for use by hypervisor/software.
@@ -294,6 +296,8 @@ static_assert((X2AVIC_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AVIC_
 	(SVM_SEV_FEAT_RESTRICTED_INJECTION |	\
 	 SVM_SEV_FEAT_ALTERNATE_INJECTION)
 
+#define VMCB_ALLOWED_SEV_FEATURES_VALID		BIT_ULL(63)
+
 struct vmcb_seg {
 	u16 selector;
 	u16 attrib;
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index a16c873b3232..d12b4d615b32 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -899,6 +899,7 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 static int __sev_launch_update_vmsa(struct kvm *kvm, struct kvm_vcpu *vcpu,
 				    int *error)
 {
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
 	struct sev_data_launch_update_vmsa vmsa;
 	struct vcpu_svm *svm = to_svm(vcpu);
 	int ret;
@@ -908,6 +909,10 @@ static int __sev_launch_update_vmsa(struct kvm *kvm, struct kvm_vcpu *vcpu,
 		return -EINVAL;
 	}
 
+	if (cpu_feature_enabled(X86_FEATURE_ALLOWED_SEV_FEATURES))
+		svm->vmcb->control.allowed_sev_features = VMCB_ALLOWED_SEV_FEATURES_VALID |
+							  sev->vmsa_features;
+
 	/* Perform some pre-encryption checks against the VMSA */
 	ret = sev_es_sync_vmsa(svm);
 	if (ret)

---

## [4] Sean Christopherson — 2024-08-22
*Subject: Re: [PATCH v2 2/2] KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB Field*

On Thu, Aug 22, 2024, Kim Phillips wrote:
> AMD EPYC 5th generation processors have introduced a feature that allows
> the hypervisor to control the SEV_FEATURES that are set for, or by, a

This may need additional uAPI so that userspace can opt-in.  Dunno.  I hope guests
aren't abusing features, but IIUC, flipping this on has the potential to break
existing VMs, correct?

---

## [5] Thomas Gleixner — 2024-08-25
*Subject: Re: [PATCH v2 1/2] x86/cpufeatures: Add "Allowed SEV Features" Feature*

On Thu, Aug 22 2024 at 17:19, Kim Phillips wrote:
> Add CPU feature detection for "Allowed SEV Features" to allow the
> Hypervisor to enforce that SEV-ES and SEV-SNP guest VMs cannot

This Signed-off-by chain is wrong. Either the patch is authored by
Kishon, then the changelog needs a From: Kishon... line or you need
Co-developed-by. See Documentation/process ....

Thanks

        tglx

---
