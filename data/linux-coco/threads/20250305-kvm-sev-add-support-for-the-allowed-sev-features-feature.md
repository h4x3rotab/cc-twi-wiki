---
title: 'KVM: SEV: Add support for the ALLOWED_SEV_FEATURES feature'
date: 2025-03-05
last_reply: 2025-03-06
message_count: 9
participants: ['Kim Phillips', 'Gupta, Pankaj', 'Borislav Petkov', 'Tom Lendacky']
---

## [1] Kim Phillips — 2025-03-05

AMD EPYC 5th generation processors have introduced a feature that allows
the hypervisor to control the SEV_FEATURES that are set for, or by, a
guest [1].  ALLOWED_SEV_FEATURES can be used by the hypervisor to enforce
that SEV-ES and SEV-SNP guests cannot enable features that the
hypervisor does not want to be enabled.

Patch 1/2 adds support to detect the feature.

Patch 2/2 configures the ALLOWED_SEV_FEATURES field in the VMCB
according to the features the hypervisor supports.

Tested SNP by setting random feature bits to the sev_features
assignment in wakeup_cpu_via_vmgexit() (but not its ghcb_set_rax).

Tested SEV-ES by manipulating the save->sev_features assignment
in sev_es_sync_vmsa().  Note that SEV-ES "allows" operation only
works on features available in SEV-ES, i.e., it ignores SNP-only
features.  Zen5 SEV-ES features are DEBUG_SWAP, PREVENT_HOST_IBS,
VMGEXIT_PARAMETER, PMC_VIRTUALIZATION, and IBS_VIRTUALIZATION.

Based on x86-kvm/next.

[1] Section 15.36.20 "Allowed SEV Features", AMD64 Architecture
    Programmer's Manual, Pub. 24593 Rev. 3.42 - March 2024:
    https://bugzilla.kernel.org/attachment.cgi?id=306250

v4:
 - Revert the user-opt in (Sean, sorry for the misunderstanding)
 - this basically undoes v3 uAPI changes and makes the feature
   always-on, if available
 - rebased on top of x86-kvm/next

v3: https://lore.kernel.org/kvm/20250207233410.130813-1-kim.phillips@amd.com/
 - Assign allowed_sev_features based on user-provided vmsa_features mask (Sean)
 - Users now have to explicitly opt-in with a qemu "allowed-sev-features=on" switch.
 - Rebased on top of 6.14-rc1 and reworked authorship chain (tglx)

v2: https://lore.kernel.org/lkml/20240822221938.2192109-1-kim.phillips@amd.com/
 - Added some SEV_FEATURES require to be explicitly allowed by
   ALLOWED_SEV_FEATURES wording (Sean).
 - Added Nikunj's Reviewed-by.

v1: https://lore.kernel.org/lkml/20240802015732.3192877-3-kim.phillips@amd.com/

Kim Phillips (1):
  KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB Field

Kishon Vijay Abraham I (1):
  x86/cpufeatures: Add "Allowed SEV Features" Feature

 arch/x86/include/asm/cpufeatures.h |  1 +
 arch/x86/include/asm/svm.h         |  7 ++++++-
 arch/x86/kvm/svm/sev.c             | 13 +++++++++++++
 3 files changed, 20 insertions(+), 1 deletion(-)


base-commit: 7d2154117a02832ab3643fe2da4cdc9d2090dcb2

---

## [2] Kim Phillips — 2025-03-05
*Subject: [PATCH v4 1/2] x86/cpufeatures: Add "Allowed SEV Features" Feature*

From: Kishon Vijay Abraham I <kvijayab@amd.com>

Add CPU feature detection for "Allowed SEV Features" to allow the
Hypervisor to enforce that SEV-ES and SEV-SNP guest VMs cannot
enable features (via SEV_FEATURES) that the Hypervisor does not
support or wish to be enabled.

Signed-off-by: Kishon Vijay Abraham I <kvijayab@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
 arch/x86/include/asm/cpufeatures.h | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index 8f8aaf94dc00..6a12c8c48bd2 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -454,6 +454,7 @@
 #define X86_FEATURE_DEBUG_SWAP		(19*32+14) /* "debug_swap" SEV-ES full debug state swap support */
 #define X86_FEATURE_RMPREAD		(19*32+21) /* RMPREAD instruction */
 #define X86_FEATURE_SEGMENTED_RMP	(19*32+23) /* Segmented RMP support */
+#define X86_FEATURE_ALLOWED_SEV_FEATURES (19*32+27) /* Allowed SEV Features */
 #define X86_FEATURE_SVSM		(19*32+28) /* "svsm" SVSM present */
 #define X86_FEATURE_HV_INUSE_WR_ALLOWED	(19*32+30) /* Allow Write to in-use hypervisor-owned pages */

---

## [3] Kim Phillips — 2025-03-05
*Subject: [PATCH v4 2/2] KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB Field*

AMD EPYC 5th generation processors have introduced a feature that allows
the hypervisor to control the SEV_FEATURES that are set for, or by, a
guest [1].  ALLOWED_SEV_FEATURES can be used by the hypervisor to enforce
that SEV-ES and SEV-SNP guests cannot enable features that the
hypervisor does not want to be enabled.

Always enable ALLOWED_SEV_FEATURES.  A VMRUN will fail if any
non-reserved bits are 1 in SEV_FEATURES but are 0 in
ALLOWED_SEV_FEATURES.

Some SEV_FEATURES - currently PmcVirtualization and SecureAvic
(see Appendix B, Table B-4) - require an opt-in via ALLOWED_SEV_FEATURES,
i.e. are off-by-default, whereas all other features are effectively
on-by-default, but still honor ALLOWED_SEV_FEATURES.

[1] Section 15.36.20 "Allowed SEV Features", AMD64 Architecture
    Programmer's Manual, Pub. 24593 Rev. 3.42 - March 2024:
    https://bugzilla.kernel.org/attachment.cgi?id=306250

Co-developed-by: Kishon Vijay Abraham I <kvijayab@amd.com>
Signed-off-by: Kishon Vijay Abraham I <kvijayab@amd.com>
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
 arch/x86/include/asm/svm.h |  7 ++++++-
 arch/x86/kvm/svm/sev.c     | 13 +++++++++++++
 2 files changed, 19 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index 9b7fa99ae951..b382fd251e5b 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -159,7 +159,10 @@ struct __attribute__ ((__packed__)) vmcb_control_area {
 	u64 avic_physical_id;	/* Offset 0xf8 */
 	u8 reserved_7[8];
 	u64 vmsa_pa;		/* Used for an SEV-ES guest */
-	u8 reserved_8[720];
+	u8 reserved_8[40];
+	u64 allowed_sev_features;	/* Offset 0x138 */
+	u64 guest_sev_features;		/* Offset 0x140 */
+	u8 reserved_9[664];
 	/*
 	 * Offset 0x3e0, 32 bytes reserved
 	 * for use by hypervisor/software.
@@ -291,6 +294,8 @@ static_assert((X2AVIC_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AVIC_
 #define SVM_SEV_FEAT_ALTERNATE_INJECTION		BIT(4)
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
 
+#define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
+
 struct vmcb_seg {
 	u16 selector;
 	u16 attrib;
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 0bc708ee2788..7f6cb950edcf 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -793,6 +793,14 @@ static int sev_launch_update_data(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return ret;
 }
 
+static u64 allowed_sev_features(struct kvm_sev_info *sev)
+{
+	if (cpu_feature_enabled(X86_FEATURE_ALLOWED_SEV_FEATURES))
+		return sev->vmsa_features | VMCB_ALLOWED_SEV_FEATURES_VALID;
+
+	return 0;
+}
+
 static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 {
 	struct kvm_vcpu *vcpu = &svm->vcpu;
@@ -891,6 +899,7 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 static int __sev_launch_update_vmsa(struct kvm *kvm, struct kvm_vcpu *vcpu,
 				    int *error)
 {
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
 	struct sev_data_launch_update_vmsa vmsa;
 	struct vcpu_svm *svm = to_svm(vcpu);
 	int ret;
@@ -900,6 +909,8 @@ static int __sev_launch_update_vmsa(struct kvm *kvm, struct kvm_vcpu *vcpu,
 		return -EINVAL;
 	}
 
+	svm->vmcb->control.allowed_sev_features = allowed_sev_features(sev);
+
 	/* Perform some pre-encryption checks against the VMSA */
 	ret = sev_es_sync_vmsa(svm);
 	if (ret)
@@ -2426,6 +2437,8 @@ static int snp_launch_update_vmsa(struct kvm *kvm, struct kvm_sev_cmd *argp)
 		struct vcpu_svm *svm = to_svm(vcpu);
 		u64 pfn = __pa(svm->sev_es.vmsa) >> PAGE_SHIFT;
 
+		svm->vmcb->control.allowed_sev_features = allowed_sev_features(sev);
+
 		ret = sev_es_sync_vmsa(svm);
 		if (ret)
 			return ret;

---

## [4] Gupta, Pankaj — 2025-03-06
*Subject: Re: [PATCH v4 2/2] KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB
 Field*

On 3/6/2025 1:38 AM, Kim Phillips wrote:
> AMD EPYC 5th generation processors have introduced a feature that allows
> the hypervisor to control the SEV_FEATURES that are set for, or by, a

Just thinking, if dumping error in logs would be
useful for Admin in case of failure Or maybe we
want to leave this to userspace?

In any case, this patch looks good to me.

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>


> +	u8 reserved_9[664];
>   	/*

---

## [5] Gupta, Pankaj — 2025-03-06
*Subject: Re: [PATCH v4 1/2] x86/cpufeatures: Add "Allowed SEV Features"
 Feature*

On 3/6/2025 1:38 AM, Kim Phillips wrote:
> From: Kishon Vijay Abraham I <kvijayab@amd.com>
> 

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

> ---
>   arch/x86/include/asm/cpufeatures.h | 1 +

---

## [6] Borislav Petkov — 2025-03-06
*Subject: Re: [PATCH v4 1/2] x86/cpufeatures: Add "Allowed SEV Features"
 Feature*

On Wed, Mar 05, 2025 at 06:38:04PM -0600, Kim Phillips wrote:
> From: Kishon Vijay Abraham I <kvijayab@amd.com>
> 

I guess this goes thru Sean:

Acked-by: Borislav Petkov (AMD) <bp@alien8.de>

---

## [7] Tom Lendacky — 2025-03-06
*Subject: Re: [PATCH v4 2/2] KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB
 Field*

On 3/5/25 18:38, Kim Phillips wrote:
> AMD EPYC 5th generation processors have introduced a feature that allows
> the hypervisor to control the SEV_FEATURES that are set for, or by, a

I think you can move this to sev_es_init_vmcb() and have it just in that
one place instead of each launch update routine.

Thanks,
Tom

> +
>  	/* Perform some pre-encryption checks against the VMSA */

---

## [8] Kim Phillips — 2025-03-06
*Subject: Re: [PATCH v4 2/2] KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB
 Field*

On 3/5/25 11:28 PM, Gupta, Pankaj wrote:
> On 3/6/2025 1:38 AM, Kim Phillips wrote:
>> diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h

Agreed.  I'll add the following in the next version:

[  435.580838] kvm_amd: allowed_sev_features:8000000000000001
[  435.587738] kvm_amd: guest_sev_features: 0000000000000081

diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 8abeab91d329..bff6e9c34586 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -3435,6 +3435,8 @@ static void dump_vmcb(struct kvm_vcpu *vcpu)
         pr_err("%-20s%016llx\n", "avic_logical_id:", control->avic_logical_id);
         pr_err("%-20s%016llx\n", "avic_physical_id:", control->avic_physical_id);
         pr_err("%-20s%016llx\n", "vmsa_pa:", control->vmsa_pa);
+       pr_err("%-20s%016llx\n", "allowed_sev_features:", control->allowed_sev_features);
+       pr_err("%-20s%016llx\n", "guest_sev_features:", control->guest_sev_features);
         pr_err("VMCB State Save Area:\n");
         pr_err("%-5s s: %04x a: %04x l: %08x b: %016llx\n",
                "es:",

Thank you for your review!

Kim

---

## [9] Kim Phillips — 2025-03-06
*Subject: Re: [PATCH v4 2/2] KVM: SEV: Configure "ALLOWED_SEV_FEATURES" VMCB
 Field*

On 3/6/25 1:27 PM, Tom Lendacky wrote:
> On 3/5/25 18:38, Kim Phillips wrote:
>> diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c

Agreed.  I'll remove the above and add the following in the next version:

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 0bc708ee2788..f9ec139901ef 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4449,6 +4449,7 @@ void sev_vcpu_after_set_cpuid(struct vcpu_svm *svm)
  
  static void sev_es_init_vmcb(struct vcpu_svm *svm)
  {
+       struct kvm_sev_info *sev = to_kvm_sev_info(svm->vcpu.kvm);
         struct vmcb *vmcb = svm->vmcb01.ptr;
         struct kvm_vcpu *vcpu = &svm->vcpu;
  
@@ -4464,6 +4465,10 @@ static void sev_es_init_vmcb(struct vcpu_svm *svm)
         if (svm->sev_es.vmsa && !svm->sev_es.snp_has_guest_vmsa)
                 svm->vmcb->control.vmsa_pa = __pa(svm->sev_es.vmsa);
  
+       if (cpu_feature_enabled(X86_FEATURE_ALLOWED_SEV_FEATURES))
+               svm->vmcb->control.allowed_sev_features = sev->vmsa_features |
+                                                         VMCB_ALLOWED_SEV_FEATURES_VALID;
+
         /* Can't intercept CR register access, HV can't modify CR registers */
         svm_clr_intercept(svm, INTERCEPT_CR0_READ);
         svm_clr_intercept(svm, INTERCEPT_CR4_READ);

Thanks for your review!

Kim

---
