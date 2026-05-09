---
title: 'KVM: SEV: Add support for IBPB-on-Entry'
date: 2026-01-26
last_reply: 2026-02-02
message_count: 19
participants: ['Kim Phillips', 'Nikunj A. Dadhania', 'Tom Lendacky', 'Borislav Petkov']
---

## [1] Kim Phillips — 2026-01-26

AMD EPYC 5th generation and above processors support IBPB-on-Entry
for SNP guests.  By invoking an Indirect Branch Prediction Barrier
(IBPB) on VMRUN, old indirect branch predictions are prevented
from influencing indirect branches within the guest.

The first patch is guest-side support which unmasks the Zen5+ feature
bit to allow kernel guests to set the feature.

The second patch is host-side support that checks the CPUID and
then sets the feature bit in the VMSA supported features mask.

Based on https://github.com/kvm-x86/linux kvm-x86/next
(kvm-x86-next-2026.01.23, e81f7c908e16).

This series also available here:

https://github.com/AMDESE/linux/tree/ibpb-on-entry-latest

Advance qemu bits (to add ibpb-on-entry=on/off switch) available here:

https://github.com/AMDESE/qemu/tree/ibpb-on-entry-latest

Qemu bits will be posted upstream once kernel bits are merged.
They depend on Naveen Rao's "target/i386: SEV: Add support for
enabling VMSA SEV features":

https://lore.kernel.org/qemu-devel/cover.1761648149.git.naveen@kernel.org/

Kim Phillips (2):
  KVM: SEV: IBPB-on-Entry guest support
  KVM: SEV: Add support for IBPB-on-Entry

 arch/x86/boot/compressed/sev.c     | 1 +
 arch/x86/coco/sev/core.c           | 1 +
 arch/x86/include/asm/cpufeatures.h | 1 +
 arch/x86/include/asm/msr-index.h   | 5 ++++-
 arch/x86/include/asm/svm.h         | 1 +
 arch/x86/kvm/svm/sev.c             | 9 ++++++++-
 6 files changed, 16 insertions(+), 2 deletions(-)


base-commit: e81f7c908e1664233974b9f20beead78cde6343a

---

## [2] Kim Phillips — 2026-01-26
*Subject: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

The SEV-SNP IBPB-on-Entry feature does not require a guest-side
implementation. The feature was added in Zen5 h/w, after the first
SNP Zen implementation, and thus was not accounted for when the
initial set of SNP features were added to the kernel.

In its abundant precaution, commit 8c29f0165405 ("x86/sev: Add SEV-SNP
guest feature negotiation support") included SEV_STATUS' IBPB-on-Entry
bit as a reserved bit, thereby masking guests from using the feature.

Unmask the bit, to allow guests to take advantage of the feature on
hypervisor kernel versions that support it: Amend the SEV_STATUS MSR
SNP_RESERVED_MASK to exclude bit 23 (IbpbOnEntry).

Fixes: 8c29f0165405 ("x86/sev: Add SEV-SNP guest feature negotiation support")
Cc: Nikunj A Dadhania <nikunj@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
CC: Borislav Petkov (AMD) <bp@alien8.de>
CC: Michael Roth <michael.roth@amd.com>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
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

## [3] Kim Phillips — 2026-01-26
*Subject: [PATCH 2/2] KVM: SEV: Add support for IBPB-on-Entry*

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
---
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

## [4] Nikunj A. Dadhania — 2026-01-27
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On 1/27/2026 4:12 AM, Kim Phillips wrote:
>  KVM: SEV: IBPB-on-Entry guest support

The subject line should have the prefix "x86/sev" instead
of "KVM: SEV". The below subject line would be more appropriate:

x86/sev: Allow IBPB-on-Entry feature for SNP guests

> The SEV-SNP IBPB-on-Entry feature does not require a guest-side
> implementation. The feature was added in Zen5 h/w, after the first

Apart from the above comments:

Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>

> ---
>  arch/x86/boot/compressed/sev.c   | 1 +

---

## [5] Nikunj A. Dadhania — 2026-01-27
*Subject: Re: [PATCH 2/2] KVM: SEV: Add support for IBPB-on-Entry*

On 1/27/2026 4:12 AM, Kim Phillips wrote:
> AMD EPYC 5th generation and above processors support IBPB-on-Entry
> for SNP guests.  By invoking an Indirect Branch Prediction Barrier

The early return seems to split up the SNP features unnecessarily.

Keeping everything under `if (sev_snp_enabled)` is cleaner IMO - 
it's clear that these features belong together. Plus, when
someone adds the next SNP feature, they won't have to think about
whether it goes before or after the return. The comment about 
"SNP specific" features becomes redundant as well.

> +	if (tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
>  		sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;

Regards,
Nikunj

---

## [6] Kim Phillips — 2026-01-27
*Subject: Re: [PATCH 2/2] KVM: SEV: Add support for IBPB-on-Entry*

On 1/27/26 12:38 AM, Nikunj A. Dadhania wrote:

Hi Nikunj,

> On 1/27/2026 4:12 AM, Kim Phillips wrote:
>> diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
The SNP 'togetherness' semantics are maintained whether under an
'if (sev_snp_enabled)' body, or after an 'if (!sev_snp_enabled) return;'.

Only SNP-specific things are being done in the trailing part of the function,
so it naturally lends itself to do the early return.  It  makes it more
readable by eliminating the unnecessary indentation created by an
'if (sev_snp_enabled)' body.

Meanwhile, I agree with your comments on the first patch in the series.

Thanks for your review,

Kim

---

## [7] Tom Lendacky — 2026-01-28
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On 1/26/26 16:42, Kim Phillips wrote:
> The SEV-SNP IBPB-on-Entry feature does not require a guest-side
> implementation. The feature was added in Zen5 h/w, after the first

With the change to the subject line...

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/boot/compressed/sev.c   | 1 +

---

## [8] Tom Lendacky — 2026-01-28
*Subject: Re: [PATCH 2/2] KVM: SEV: Add support for IBPB-on-Entry*

On 1/26/26 16:42, Kim Phillips wrote:
> AMD EPYC 5th generation and above processors support IBPB-on-Entry
> for SNP guests.  By invoking an Indirect Branch Prediction Barrier

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/include/asm/cpufeatures.h | 1 +

---

## [9] Borislav Petkov — 2026-01-28
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On Mon, Jan 26, 2026 at 04:42:04PM -0600, Kim Phillips wrote:
> The SEV-SNP IBPB-on-Entry feature does not require a guest-side
> implementation. The feature was added in Zen5 h/w, after the first

Do not explain what the patch does.

> Fixes: 8c29f0165405 ("x86/sev: Add SEV-SNP guest feature negotiation support")
> Cc: Nikunj A Dadhania <nikunj@amd.com>

I guess...

> diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
> index 4d3566bb1a93..9016a6b00bc7 100644

Why isn't this part of SNP_FEATURES_PRESENT?

If this feature doesn't require guest-side support, then it is trivially
present, no?

> +#define MSR_AMD64_SNP_RESV_BIT		24
>  #define MSR_AMD64_SNP_RESERVED_MASK	GENMASK_ULL(63, MSR_AMD64_SNP_RESV_BIT)

I guess this is a fix of sorts and I could take it in now once all review
comments have been addressed...

---

## [10] Kim Phillips — 2026-01-28
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

Hi Boris,

On 1/28/26 1:23 PM, Borislav Petkov wrote:
> On Mon, Jan 26, 2026 at 04:42:04PM -0600, Kim Phillips wrote:
>> The SEV-SNP IBPB-on-Entry feature does not require a guest-side

For that last paragraph, how about:

"Allow guests to make use of IBPB-on-Entry when supported by the
hypervisor, as the bit is now architecturally defined and safe to
expose."

?

>> Fixes: 8c29f0165405 ("x86/sev: Add SEV-SNP guest feature negotiation support")
>> Cc: Nikunj A Dadhania <nikunj@amd.com>

Hopefully a bitfield will be carved out for these
no-explicit-guest-implementation-required bits by hardware such that we
won't need to do this again.

>> diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
>> index 4d3566bb1a93..9016a6b00bc7 100644

SNP_FEATURES_PRESENT is for the non-trivial variety: Its bits get set as
part of the patchseries that add the explicit guest support *code*.

I believe 'features' like PREVENT_HOST_IBS are similar in this regard.

>> +#define MSR_AMD64_SNP_RESV_BIT		24
>>   #define MSR_AMD64_SNP_RESERVED_MASK	GENMASK_ULL(63, MSR_AMD64_SNP_RESV_BIT)

Cool, thanks.

Kim

---

## [11] Borislav Petkov — 2026-01-29
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On Wed, Jan 28, 2026 at 06:38:29PM -0600, Kim Phillips wrote:
> For that last paragraph, how about:
> 

Better.

> SNP_FEATURES_PRESENT is for the non-trivial variety: Its bits get set as
> part of the patchseries that add the explicit guest support *code*.

Yes, and I'm asking why can't SNP_FEATURES_PRESENT contain *all* SNP features?

---

## [12] Kim Phillips — 2026-01-29
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On 1/29/26 4:51 AM, Borislav Petkov wrote:
> On Wed, Jan 28, 2026 at 06:38:29PM -0600, Kim Phillips wrote:
>> SNP_FEATURES_PRESENT is for the non-trivial variety: Its bits get set as

Not *all* SNP features are implemented in all guest kernel versions, and,
well, for those that don't require explicit guest code support, perhaps it's
because they aren't necessarily well defined and validated in all hardware
versions...

Kim

---

## [13] Borislav Petkov — 2026-01-30
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On Thu, Jan 29, 2026 at 04:32:49PM -0600, Kim Phillips wrote:
> Not *all* SNP features are implemented in all guest kernel versions, and,
> well, for those that don't require explicit guest code support, perhaps it's

Ok, can you add *this* feature to SNP_FEATURES_PRESENT? If not, why not?

---

## [14] Tom Lendacky — 2026-01-30
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On 1/30/26 06:32, Borislav Petkov wrote:
> On Thu, Jan 29, 2026 at 04:32:49PM -0600, Kim Phillips wrote:
>> Not *all* SNP features are implemented in all guest kernel versions, and,

It can be added. Any of the features added to SNP_FEATURES_PRESENT that
aren't set in the SNP_FEATURES_IMPL_REQ bitmap are really a no-op. The
SNP_FEATURES_PRESENT bitmap is meant to contain whatever bits are set in
SNP_FEATURES_IMPL_REQ when an implementation has been implemented for the
guest.

But, yeah, we could add all the bits that aren't set in
SNP_FEATURES_IMPL_REQ to SNP_FEATURES_PRESENT if it makes it clearer.

If we do that, it should probably be a separate patch (?) that also
rewords the comment above SNP_FEATURES_PRESENT

Thanks,
Tom

>

---

## [15] Borislav Petkov — 2026-01-30
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On Fri, Jan 30, 2026 at 08:56:07AM -0600, Tom Lendacky wrote:
> It can be added. Any of the features added to SNP_FEATURES_PRESENT that
> aren't set in the SNP_FEATURES_IMPL_REQ bitmap are really a no-op. The

Right, that's the question. SNP_FEATURES_PRESENT is used in the masking
operation to get the unsupported features.

But when we say a SNP feature is present, then, even if it doesn't need guest
implementation, that feature is still present nonetheless.

So our nomenclature is kinda imprecise here.

I'd say, we can always rename SNP_FEATURES_PRESENT to denote what it is there
for, i.e., the narrower functionality of the masking.

Or, if we want to gather there *all* features that are present, then we can
start adding them...

> If we do that, it should probably be a separate patch (?) that also
> rewords the comment above SNP_FEATURES_PRESENT

... yes, as a separate patch.

Question is, what do we really wanna do here?

Does it make sense and is it useful to have SNP_FEATURES_PRESENT contain *all*
guest SNP features...

Thx.

---

## [16] Tom Lendacky — 2026-02-02
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On 1/30/26 09:45, Borislav Petkov wrote:
> On Fri, Jan 30, 2026 at 08:56:07AM -0600, Tom Lendacky wrote:
>> It can be added. Any of the features added to SNP_FEATURES_PRESENT that

I guess it really depends on the persons point of view. I agree that
renaming the SNP_FEATURES_PRESENT to SNP_FEATURES_IMPL(EMENTED) would
match up nicely with SNP_FEATURES_IMPL_REQ. Maybe that's all that is
needed...

Thanks,
Tom


> 
> Thx.

---

## [17] Borislav Petkov — 2026-02-02
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On Mon, Feb 02, 2026 at 09:38:50AM -0600, Tom Lendacky wrote:
> I guess it really depends on the persons point of view. I agree that
> renaming the SNP_FEATURES_PRESENT to SNP_FEATURES_IMPL(EMENTED) would

I guess...

I still think it would be useful to have a common place that says which things
in SEV_STATUS are supported and present in a guest, no?

Or are we going to dump that MSR like Joerg's patch from a while ago and
that'll tell us what the guest supports?

Hmm.

---

## [18] Tom Lendacky — 2026-02-02
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On 2/2/26 09:49, Borislav Petkov wrote:
> On Mon, Feb 02, 2026 at 09:38:50AM -0600, Tom Lendacky wrote:
>> I guess it really depends on the persons point of view. I agree that

But I can see that getting stale because it isn't required to be updated
for features that don't require an implementation in order for the guest
to boot successfully. Whereas the SNP_FEATURES_IMPL_REQ is set with
known values that require an implementation and all the reserved bits
set. So it takes actual updating to get one of those features to work
that are represented in that bitmap.

> 
> Or are we going to dump that MSR like Joerg's patch from a while ago and

That will tell us what the guest is running with, not what it can run with.

Thanks,
Tom

> 
> Hmm.

---

## [19] Borislav Petkov — 2026-02-02
*Subject: Re: [PATCH 1/2] KVM: SEV: IBPB-on-Entry guest support*

On Mon, Feb 02, 2026 at 10:09:19AM -0600, Tom Lendacky wrote:
> But I can see that getting stale because it isn't required to be updated
> for features that don't require an implementation in order for the guest

Ok, I guess we can rename that define SNP_FEATURES_IMPL to denote is the
counterpart of SNP_FEATURES_IMPL_REQ, so to speak.

@Kim, you can send a new version with the define renamed.

Due to it being too close to the merge window, it'll wait for after and then
it can go to stable later but I don't think that's a problem.

> That will tell us what the guest is running with, not what it can run with.

hm, ok, let's think about this more then. I don't have a clear use case for
a this-is-what-a-SNP-guest-can-run-with so let's deal with that later...

Thx.

---
