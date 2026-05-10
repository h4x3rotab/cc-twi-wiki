---
title: 'TDX: Clean up the definitions of TDX ATTRIBUTES'
date: 2025-07-08
last_reply: 2025-07-09
message_count: 12
participants: ['Xiaoyao Li', 'Huang, Kai', 'Sean Christopherson', 'Edgecombe, Rick P']
---

## [1] Xiaoyao Li — 2025-07-08

It's a simple series. Patch 1 fixes the typo and Patch 2 removes the
redundant definitions of TD ATTRIBUTES bits.

Although some duplications were identified during the community review
of TDX KVM base support[1][2], a few slipped through unnoticed due to
the simultaneous evolution of the TD guest part.

[1] https://lore.kernel.org/all/e5387c7c-9df8-4e39-bbe9-23e8bb09e527@intel.com/
[2] https://lore.kernel.org/all/25bf543723a176bf910f27ede288f3d20f20aed1.camel@intel.com/

Xiaoyao Li (2):
  x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE
  KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_*

 arch/x86/coco/tdx/debug.c         | 2 +-
 arch/x86/include/asm/shared/tdx.h | 4 ++--
 arch/x86/kvm/vmx/tdx.c            | 4 ++--
 arch/x86/kvm/vmx/tdx_arch.h       | 6 ------
 4 files changed, 5 insertions(+), 11 deletions(-)


base-commit: e4775f57ad51a5a7f1646ac058a3d00c8eec1e98

---

## [2] Xiaoyao Li — 2025-07-08
*Subject: [PATCH 1/2] x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE*

Fix the typo of TDX_ATTR_MIGRTABLE to TDX_ATTR_MIGRATABLE.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 arch/x86/coco/tdx/debug.c         | 2 +-
 arch/x86/include/asm/shared/tdx.h | 4 ++--
 2 files changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/debug.c b/arch/x86/coco/tdx/debug.c
index cef847c8bb67..28990c2ab0a1 100644
--- a/arch/x86/coco/tdx/debug.c
+++ b/arch/x86/coco/tdx/debug.c
@@ -17,7 +17,7 @@ static __initdata const char *tdx_attributes[] = {
 	DEF_TDX_ATTR_NAME(ICSSD),
 	DEF_TDX_ATTR_NAME(LASS),
 	DEF_TDX_ATTR_NAME(SEPT_VE_DISABLE),
-	DEF_TDX_ATTR_NAME(MIGRTABLE),
+	DEF_TDX_ATTR_NAME(MIGRATABLE),
 	DEF_TDX_ATTR_NAME(PKS),
 	DEF_TDX_ATTR_NAME(KL),
 	DEF_TDX_ATTR_NAME(TPA),
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 8bc074c8d7c6..11f3cf30b1ac 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -35,8 +35,8 @@
 #define TDX_ATTR_LASS			BIT_ULL(TDX_ATTR_LASS_BIT)
 #define TDX_ATTR_SEPT_VE_DISABLE_BIT	28
 #define TDX_ATTR_SEPT_VE_DISABLE	BIT_ULL(TDX_ATTR_SEPT_VE_DISABLE_BIT)
-#define TDX_ATTR_MIGRTABLE_BIT		29
-#define TDX_ATTR_MIGRTABLE		BIT_ULL(TDX_ATTR_MIGRTABLE_BIT)
+#define TDX_ATTR_MIGRATABLE_BIT		29
+#define TDX_ATTR_MIGRATABLE		BIT_ULL(TDX_ATTR_MIGRATABLE_BIT)
 #define TDX_ATTR_PKS_BIT		30
 #define TDX_ATTR_PKS			BIT_ULL(TDX_ATTR_PKS_BIT)
 #define TDX_ATTR_KL_BIT			31

---

## [3] Xiaoyao Li — 2025-07-08
*Subject: [PATCH 2/2] KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_**

There are definitions of TD attributes bits inside asm/shared/tdx.h as
TDX_ATTR_*.

Remove KVM's definitions and use the ones in asm/shared/tdx.h

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 arch/x86/kvm/vmx/tdx.c      | 4 ++--
 arch/x86/kvm/vmx/tdx_arch.h | 6 ------
 2 files changed, 2 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c539c2e6109f..efb7d589b672 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -62,7 +62,7 @@ void tdh_vp_wr_failed(struct vcpu_tdx *tdx, char *uclass, char *op, u32 field,
 	pr_err("TDH_VP_WR[%s.0x%x]%s0x%llx failed: 0x%llx\n", uclass, field, op, val, err);
 }
 
-#define KVM_SUPPORTED_TD_ATTRS (TDX_TD_ATTR_SEPT_VE_DISABLE)
+#define KVM_SUPPORTED_TD_ATTRS (TDX_ATTR_SEPT_VE_DISABLE)
 
 static __always_inline struct kvm_tdx *to_kvm_tdx(struct kvm *kvm)
 {
@@ -700,7 +700,7 @@ int tdx_vcpu_create(struct kvm_vcpu *vcpu)
 	vcpu->arch.l1_tsc_scaling_ratio = kvm_tdx->tsc_multiplier;
 
 	vcpu->arch.guest_state_protected =
-		!(to_kvm_tdx(vcpu->kvm)->attributes & TDX_TD_ATTR_DEBUG);
+		!(to_kvm_tdx(vcpu->kvm)->attributes & TDX_ATTR_DEBUG);
 
 	if ((kvm_tdx->xfam & XFEATURE_MASK_XTILE) == XFEATURE_MASK_XTILE)
 		vcpu->arch.xfd_no_write_intercept = true;
diff --git a/arch/x86/kvm/vmx/tdx_arch.h b/arch/x86/kvm/vmx/tdx_arch.h
index a30e880849e3..350143b9b145 100644
--- a/arch/x86/kvm/vmx/tdx_arch.h
+++ b/arch/x86/kvm/vmx/tdx_arch.h
@@ -75,12 +75,6 @@ struct tdx_cpuid_value {
 	u32 edx;
 } __packed;
 
-#define TDX_TD_ATTR_DEBUG		BIT_ULL(0)
-#define TDX_TD_ATTR_SEPT_VE_DISABLE	BIT_ULL(28)
-#define TDX_TD_ATTR_PKS			BIT_ULL(30)
-#define TDX_TD_ATTR_KL			BIT_ULL(31)
-#define TDX_TD_ATTR_PERFMON		BIT_ULL(63)
-
 #define TDX_EXT_EXIT_QUAL_TYPE_MASK	GENMASK(3, 0)
 #define TDX_EXT_EXIT_QUAL_TYPE_PENDING_EPT_VIOLATION  6
 /*

---

## [4] Huang, Kai — 2025-07-08
*Subject: Re: [PATCH 1/2] x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE*

On Tue, 2025-07-08 at 16:03 +0800, Xiaoyao Li wrote:
> Fix the typo of TDX_ATTR_MIGRTABLE to TDX_ATTR_MIGRATABLE.
> 

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [5] Huang, Kai — 2025-07-08
*Subject: Re: [PATCH 2/2] KVM: TDX: Remove redundant definitions of
 TDX_TD_ATTR_**

On Tue, 2025-07-08 at 16:03 +0800, Xiaoyao Li wrote:
> There are definitions of TD attributes bits inside asm/shared/tdx.h as
> TDX_ATTR_*.

Nit: Missing period at the end of the sentence.

> 
> Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [6] Sean Christopherson — 2025-07-08
*Subject: Re: [PATCH 2/2] KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_**

On Tue, Jul 08, 2025, Xiaoyao Li wrote:
> There are definitions of TD attributes bits inside asm/shared/tdx.h as
> TDX_ATTR_*.

Would it make sense to rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_ATTRS?
The names from common code lack the TD qualifier, and I think it'd be helpful for
readers to have have TDX in the name (even though I agree "TD" is more precise).

---

## [7] Edgecombe, Rick P — 2025-07-08
*Subject: Re: [PATCH 1/2] x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE*

On Tue, 2025-07-08 at 16:03 +0800, Xiaoyao Li wrote:
> Fix the typo of TDX_ATTR_MIGRTABLE to TDX_ATTR_MIGRATABLE.

Can you add a little more. Something that explains the impact of the change.
These names are stringified and printed out. So it will actually fix the dmesg
output as well. But not any kind of machine readable proc or anything like that.

> 
> Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [8] Xiaoyao Li — 2025-07-08
*Subject: Re: [PATCH 2/2] KVM: TDX: Remove redundant definitions of
 TDX_TD_ATTR_**

On 7/8/2025 10:03 PM, Sean Christopherson wrote:
> On Tue, Jul 08, 2025, Xiaoyao Li wrote:
>> There are definitions of TD attributes bits inside asm/shared/tdx.h as

Personally, I prefer adding _TD_ to the common header, i.e., rename 
TDX_ATTR_SEPT_VE_DISABLE to TDX_TD_ATTR_SEPT_VE_DISABLE, or just 
TD_ATTR_SEPT_VE_DISABLE if dropping TDX prefix is acceptable.

Because TDX_ATTR OR TDX_ATTRIBUTES is ambiguous to me. There are other 
attributes defined in TDX spec, e.g., TDSYSINFO_STRUCT.ATTRIBUTES, GPA 
attributes.

---

## [9] Edgecombe, Rick P — 2025-07-08
*Subject: Re: [PATCH 2/2] KVM: TDX: Remove redundant definitions of
 TDX_TD_ATTR_**

On Tue, 2025-07-08 at 07:03 -0700, Sean Christopherson wrote:
> > diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
> > index c539c2e6109f..efb7d589b672 100644

It's useful to know that these are per-TD attributes and not per-TDX module.
Especially for TDX_TD_ATTR_DEBUG. I kind of prefer the KVM naming scheme that is
removed in this patch.

---

## [10] Sean Christopherson — 2025-07-08
*Subject: Re: [PATCH 2/2] KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_**

On Tue, Jul 08, 2025, Rick P Edgecombe wrote:
> On Tue, 2025-07-08 at 07:03 -0700, Sean Christopherson wrote:
> > > diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c

Heh, as does Xiaoyao, and me too.  I thought I was just being nitpicky :-)

Though in that case, I think I'd prefer KVM_SUPPORTED_TDX_TD_ATTRS.

---

## [11] Xiaoyao Li — 2025-07-09
*Subject: Re: [PATCH 2/2] KVM: TDX: Remove redundant definitions of
 TDX_TD_ATTR_**

On 7/8/2025 10:44 PM, Sean Christopherson wrote:
> On Tue, Jul 08, 2025, Rick P Edgecombe wrote:
>> On Tue, 2025-07-08 at 07:03 -0700, Sean Christopherson wrote:

To me, since the MACRO is only used inside kvm/vmx/tdx.c, it's OK 
without the _TDX_ prefix.

However, doing the rename is simple. So I'm going to rename it in a 
separate patch in the v2 unless being told unnecessary.

---

## [12] Xiaoyao Li — 2025-07-09
*Subject: Re: [PATCH 1/2] x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE*

On 7/8/2025 10:20 PM, Edgecombe, Rick P wrote:
> On Tue, 2025-07-08 at 16:03 +0800, Xiaoyao Li wrote:
>> Fix the typo of TDX_ATTR_MIGRTABLE to TDX_ATTR_MIGRATABLE.

Good catch! I will add more in next version.

>>
>> Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---
