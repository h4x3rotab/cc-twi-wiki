---
title: 'TDX: Clean up the definitions of TDX ATTRIBUTES'
date: 2025-07-11
last_reply: 2025-07-15
message_count: 9
participants: ['Xiaoyao Li', 'Edgecombe, Rick P']
---

## [1] Xiaoyao Li — 2025-07-11

Although some duplications were identified during the community review
of TDX KVM base support[1][2], a few slipped through unnoticed due to
the simultaneous evolution of the TD guest part.

Patch 1 fixes the typo. Patch 2 removes the redundant definitions of
TD ATTRIBUTES bits. Patch 3 rename KVM_SUPPORTED_TD_ATTRS to include
"TDX" in it, based on Sean's preference[3].

Note, this series doesn't rename TDX_ATTR_* in asm/shared/tdx.h to
TDX_TD_ATTR_*, so that KVM_SUPPORTED_TDX_TD_ATTRS in patch 3 looks
a little inconsistent. Because I'm not sure what the preference of tip
maintainers on the name is. So I only honor KVM maintainer's preference
and leave the stuff outside KVM unchanged.

[1] https://lore.kernel.org/all/e5387c7c-9df8-4e39-bbe9-23e8bb09e527@intel.com/
[2] https://lore.kernel.org/all/25bf543723a176bf910f27ede288f3d20f20aed1.camel@intel.com/
[3] https://lore.kernel.org/all/aG0uyLwxqfKSX72s@google.com/


Changes in v2:
 - collect Reviewed-by;
 - Explains the impact of the change in patch 1 changelog;
 - Add patch 3.

v1: https://lore.kernel.org/all/20250708080314.43081-1-xiaoyao.li@intel.com/ 

Xiaoyao Li (3):
  x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE
  KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_*
  KVM: TDX: Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS

 arch/x86/coco/tdx/debug.c         | 2 +-
 arch/x86/include/asm/shared/tdx.h | 4 ++--
 arch/x86/kvm/vmx/tdx.c            | 6 +++---
 arch/x86/kvm/vmx/tdx_arch.h       | 6 ------
 4 files changed, 6 insertions(+), 12 deletions(-)


base-commit: e4775f57ad51a5a7f1646ac058a3d00c8eec1e98
prerequisite-patch-id: 96c55dfc551bf62e0b18e75547ba3bf671e30ee8

---

## [2] Xiaoyao Li — 2025-07-11
*Subject: [PATCH v2 1/3] x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE*

Fix the typo from TDX_ATTR_MIGRTABLE to TDX_ATTR_MIGRATABLE.

Since the names are stringified and printed out to dmesg in
tdx_dump_attributes(), this correction will also fix the dmesg output.
But not any kind of machine readable proc or anything like that.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
Changes in v2:
 - Add the impact of the change in the commit message. (provided by Rick)
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

## [3] Xiaoyao Li — 2025-07-11
*Subject: [PATCH v2 2/3] KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_**

There are definitions of TD attributes bits inside asm/shared/tdx.h as
TDX_ATTR_*.

Remove KVM's definitions and use the ones in asm/shared/tdx.h

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
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

## [4] Xiaoyao Li — 2025-07-11
*Subject: [PATCH v2 3/3] KVM: TDX: Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS*

Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS to include
"TDX" in the name, making it clear that it pertains to TDX.

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index efb7d589b672..90fb6ba245dd 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -62,7 +62,7 @@ void tdh_vp_wr_failed(struct vcpu_tdx *tdx, char *uclass, char *op, u32 field,
 	pr_err("TDH_VP_WR[%s.0x%x]%s0x%llx failed: 0x%llx\n", uclass, field, op, val, err);
 }
 
-#define KVM_SUPPORTED_TD_ATTRS (TDX_ATTR_SEPT_VE_DISABLE)
+#define KVM_SUPPORTED_TDX_TD_ATTRS (TDX_ATTR_SEPT_VE_DISABLE)
 
 static __always_inline struct kvm_tdx *to_kvm_tdx(struct kvm *kvm)
 {
@@ -76,7 +76,7 @@ static __always_inline struct vcpu_tdx *to_tdx(struct kvm_vcpu *vcpu)
 
 static u64 tdx_get_supported_attrs(const struct tdx_sys_info_td_conf *td_conf)
 {
-	u64 val = KVM_SUPPORTED_TD_ATTRS;
+	u64 val = KVM_SUPPORTED_TDX_TD_ATTRS;
 
 	if ((val & td_conf->attributes_fixed1) != td_conf->attributes_fixed1)
 		return 0;

---

## [5] Edgecombe, Rick P — 2025-07-11
*Subject: Re: [PATCH v2 1/3] x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE*

On Fri, 2025-07-11 at 21:26 +0800, Xiaoyao Li wrote:
> Fix the typo from TDX_ATTR_MIGRTABLE to TDX_ATTR_MIGRATABLE.
> 

> But not any kind of machine readable proc or anything like that.

Thanks for adding the impact. This is such a small patch that I hate to generate
a v3, but this is too imprecise for a tip commit log.

Here is how I would write it, what do you think?


x86/tdx: Fix the typo in TDX_ATTR_MIGRTABLE

The TD scoped TDCS attributes are defined by a bit position. In the guest side
of the TDX code, the 'tdx_attributes' string array holds pretty print names for
these attributes, which are generated via macros and defines. Today these pretty
print names are only used to print the attribute names to dmesg.

Unfortunately there is a typo in define for the migratable bit define. Change
the defines TDX_ATTR_MIGRTABLE* to TDX_ATTR_MIGRATABLE*. Update the sole user,
the tdx_attributes array, to use the fixed name.

Since these defines control the string printed to dmesg, the change is user
visible. But the risk of breakage is almost zero since is not exposed in any
interface expected to be consumed programatically.

Fixes: 564ea84c8c14 ("x86/tdx: Dump attributes and TD_CTLS on boot")
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>

---

## [6] Edgecombe, Rick P — 2025-07-11
*Subject: Re: [PATCH v2 0/3] TDX: Clean up the definitions of TDX ATTRIBUTES*

On Fri, 2025-07-11 at 21:26 +0800, Xiaoyao Li wrote:
> Note, this series doesn't rename TDX_ATTR_* in asm/shared/tdx.h to
> TDX_TD_ATTR_*, so that KVM_SUPPORTED_TDX_TD_ATTRS in patch 3 looks

I prefer the names with "TD" based on the argument that it's clearer that it is
TD scoped. My read was that Sean has the same reasoning. This series changes KVM
code to use the non-"TD" defines. So I feel Sean's opinion counts here. We don't
have any x86 maintainer NAK on the other direction, so it doesn't seem like a
reason to give up trying.

That said I think this series is an overall improvement. We could always add TD
to the names later. But the sooner we do it, the less we'll have to change.

---

## [7] Edgecombe, Rick P — 2025-07-11
*Subject: Re: [PATCH v2 3/3] KVM: TDX: Rename KVM_SUPPORTED_TD_ATTRS to
 KVM_SUPPORTED_TDX_TD_ATTRS*

On Fri, 2025-07-11 at 21:26 +0800, Xiaoyao Li wrote:
> Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS to include
> "TDX" in the name, making it clear that it pertains to TDX.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [8] Xiaoyao Li — 2025-07-15
*Subject: Re: [PATCH v2 1/3] x86/tdx: Fix the typo of TDX_ATTR_MIGRTABLE*

On 7/12/2025 1:51 AM, Edgecombe, Rick P wrote:
> On Fri, 2025-07-11 at 21:26 +0800, Xiaoyao Li wrote:
>> Fix the typo from TDX_ATTR_MIGRTABLE to TDX_ATTR_MIGRATABLE.

It's way better than mine!

I use it in v3 with few fix (by gpt).

thanks!

> 
> x86/tdx: Fix the typo in TDX_ATTR_MIGRTABLE

---

## [9] Xiaoyao Li — 2025-07-15
*Subject: Re: [PATCH v2 0/3] TDX: Clean up the definitions of TDX ATTRIBUTES*

On 7/12/2025 2:02 AM, Edgecombe, Rick P wrote:
> On Fri, 2025-07-11 at 21:26 +0800, Xiaoyao Li wrote:
>> Note, this series doesn't rename TDX_ATTR_* in asm/shared/tdx.h to

Just sent the v3 which adds one additional patch to rename it.

---
