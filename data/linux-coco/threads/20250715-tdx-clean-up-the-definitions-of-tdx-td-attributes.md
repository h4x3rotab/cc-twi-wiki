---
title: 'TDX: Clean up the definitions of TDX TD ATTRIBUTES'
date: 2025-07-15
last_reply: 2025-09-12
message_count: 13
participants: ['Xiaoyao Li', 'Sean Christopherson', 'Edgecombe, Rick P', 'Binbin Wu', 'Kiryl Shutsemau']
---

## [1] Xiaoyao Li — 2025-07-15

The main purpose of this series was to remove redundant macros between
core TDX and KVM, along with a typo fix. They were implemented as patch1
and patch2.

During the review of v1 and v2, there was encouragement to refine the
names of the macros related to TD attributes to clarify their scope.
Thus patch3 and patch 4 are added.

Discussion details can be found in previrous versions.


Changes in v3:
 - use the changelog provided by Rick for patch 1;
 - collect Reviewed-by on patch 4;
 - Add patch 3;

v2: https://lore.kernel.org/all/20250711132620.262334-1-xiaoyao.li@intel.com/
Changes in v2:
 - collect Reviewed-by;
 - Explains the impact of the change in patch 1 changelog;
 - Add patch 3.

v1: https://lore.kernel.org/all/20250708080314.43081-1-xiaoyao.li@intel.com/ 

Xiaoyao Li (4):
  x86/tdx: Fix the typo in TDX_ATTR_MIGRTABLE
  KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_*
  x86/tdx: Rename TDX_ATTR_* to TDX_TD_ATTR_*
  KVM: TDX: Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS

 arch/x86/coco/tdx/debug.c         | 26 ++++++++--------
 arch/x86/coco/tdx/tdx.c           |  8 ++---
 arch/x86/include/asm/shared/tdx.h | 50 +++++++++++++++----------------
 arch/x86/kvm/vmx/tdx.c            |  4 +--
 arch/x86/kvm/vmx/tdx_arch.h       |  6 ----
 5 files changed, 44 insertions(+), 50 deletions(-)

---

## [2] Xiaoyao Li — 2025-07-15
*Subject: [PATCH v3 1/4] x86/tdx: Fix the typo in TDX_ATTR_MIGRTABLE*

The TD scoped TDCS attributes are defined by bit positions. In the guest
side of the TDX code, the 'tdx_attributes' string array holds pretty
print names for these attributes, which are generated via macros and
defines. Today these pretty print names are only used to print the
attribute names to dmesg.

Unfortunately there is a typo in the define for the migratable bit.
Change the defines TDX_ATTR_MIGRTABLE* to TDX_ATTR_MIGRATABLE*. Update
the sole user, the tdx_attributes array, to use the fixed name.

Since these defines control the string printed to dmesg, the change is
user visible. But the risk of breakage is almost zero since it is not
exposed in any interface expected to be consumed programmatically.

Fixes: 564ea84c8c14 ("x86/tdx: Dump attributes and TD_CTLS on boot")
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
Changes in v3:
 - Use the rewritten changelog from Rick.

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

## [3] Xiaoyao Li — 2025-07-15
*Subject: [PATCH v3 2/4] KVM: TDX: Remove redundant definitions of TDX_TD_ATTR_**

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

## [4] Xiaoyao Li — 2025-07-15
*Subject: [PATCH v3 3/4] x86/tdx: Rename TDX_ATTR_* to TDX_TD_ATTR_**

The macros TDX_ATTR_* and DEF_TDX_ATTR_* are related to TD attributes,
which are TD-scope attributes. Naming them as TDX_ATTR_* can be somewhat
confusing and might mislead people into thinking they are TDX global
things.

Rename TDX_ATTR_* to TDX_TD_ATTR_* to explicitly clarify they are
TD-scope things.

Suggested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 arch/x86/coco/tdx/debug.c         | 26 ++++++++--------
 arch/x86/coco/tdx/tdx.c           |  8 ++---
 arch/x86/include/asm/shared/tdx.h | 50 +++++++++++++++----------------
 arch/x86/kvm/vmx/tdx.c            |  4 +--
 4 files changed, 44 insertions(+), 44 deletions(-)

diff --git a/arch/x86/coco/tdx/debug.c b/arch/x86/coco/tdx/debug.c
index 28990c2ab0a1..8e477db4ce0a 100644
--- a/arch/x86/coco/tdx/debug.c
+++ b/arch/x86/coco/tdx/debug.c
@@ -7,21 +7,21 @@
 #include <linux/printk.h>
 #include <asm/tdx.h>
 
-#define DEF_TDX_ATTR_NAME(_name) [TDX_ATTR_##_name##_BIT] = __stringify(_name)
+#define DEF_TDX_TD_ATTR_NAME(_name) [TDX_TD_ATTR_##_name##_BIT] = __stringify(_name)
 
 static __initdata const char *tdx_attributes[] = {
-	DEF_TDX_ATTR_NAME(DEBUG),
-	DEF_TDX_ATTR_NAME(HGS_PLUS_PROF),
-	DEF_TDX_ATTR_NAME(PERF_PROF),
-	DEF_TDX_ATTR_NAME(PMT_PROF),
-	DEF_TDX_ATTR_NAME(ICSSD),
-	DEF_TDX_ATTR_NAME(LASS),
-	DEF_TDX_ATTR_NAME(SEPT_VE_DISABLE),
-	DEF_TDX_ATTR_NAME(MIGRATABLE),
-	DEF_TDX_ATTR_NAME(PKS),
-	DEF_TDX_ATTR_NAME(KL),
-	DEF_TDX_ATTR_NAME(TPA),
-	DEF_TDX_ATTR_NAME(PERFMON),
+	DEF_TDX_TD_ATTR_NAME(DEBUG),
+	DEF_TDX_TD_ATTR_NAME(HGS_PLUS_PROF),
+	DEF_TDX_TD_ATTR_NAME(PERF_PROF),
+	DEF_TDX_TD_ATTR_NAME(PMT_PROF),
+	DEF_TDX_TD_ATTR_NAME(ICSSD),
+	DEF_TDX_TD_ATTR_NAME(LASS),
+	DEF_TDX_TD_ATTR_NAME(SEPT_VE_DISABLE),
+	DEF_TDX_TD_ATTR_NAME(MIGRATABLE),
+	DEF_TDX_TD_ATTR_NAME(PKS),
+	DEF_TDX_TD_ATTR_NAME(KL),
+	DEF_TDX_TD_ATTR_NAME(TPA),
+	DEF_TDX_TD_ATTR_NAME(PERFMON),
 };
 
 #define DEF_TD_CTLS_NAME(_name) [TD_CTLS_##_name##_BIT] = __stringify(_name)
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..186915a17c50 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -238,14 +238,14 @@ static void __noreturn tdx_panic(const char *msg)
  *
  * TDX 1.0 does not allow the guest to disable SEPT #VE on its own. The VMM
  * controls if the guest will receive such #VE with TD attribute
- * TDX_ATTR_SEPT_VE_DISABLE.
+ * TDX_TD_ATTR_SEPT_VE_DISABLE.
  *
  * Newer TDX modules allow the guest to control if it wants to receive SEPT
  * violation #VEs.
  *
  * Check if the feature is available and disable SEPT #VE if possible.
  *
- * If the TD is allowed to disable/enable SEPT #VEs, the TDX_ATTR_SEPT_VE_DISABLE
+ * If the TD is allowed to disable/enable SEPT #VEs, the TDX_TD_ATTR_SEPT_VE_DISABLE
  * attribute is no longer reliable. It reflects the initial state of the
  * control for the TD, but it will not be updated if someone (e.g. bootloader)
  * changes it before the kernel starts. Kernel must check TDCS_TD_CTLS bit to
@@ -254,14 +254,14 @@ static void __noreturn tdx_panic(const char *msg)
 static void disable_sept_ve(u64 td_attr)
 {
 	const char *msg = "TD misconfiguration: SEPT #VE has to be disabled";
-	bool debug = td_attr & TDX_ATTR_DEBUG;
+	bool debug = td_attr & TDX_TD_ATTR_DEBUG;
 	u64 config, controls;
 
 	/* Is this TD allowed to disable SEPT #VE */
 	tdg_vm_rd(TDCS_CONFIG_FLAGS, &config);
 	if (!(config & TDCS_CONFIG_FLEXIBLE_PENDING_VE)) {
 		/* No SEPT #VE controls for the guest: check the attribute */
-		if (td_attr & TDX_ATTR_SEPT_VE_DISABLE)
+		if (td_attr & TDX_TD_ATTR_SEPT_VE_DISABLE)
 			return;
 
 		/* Relax SEPT_VE_DISABLE check for debug TD for backtraces */
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 11f3cf30b1ac..049638e3da74 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -20,31 +20,31 @@
 #define TDG_VM_RD			7
 #define TDG_VM_WR			8
 
-/* TDX attributes */
-#define TDX_ATTR_DEBUG_BIT		0
-#define TDX_ATTR_DEBUG			BIT_ULL(TDX_ATTR_DEBUG_BIT)
-#define TDX_ATTR_HGS_PLUS_PROF_BIT	4
-#define TDX_ATTR_HGS_PLUS_PROF		BIT_ULL(TDX_ATTR_HGS_PLUS_PROF_BIT)
-#define TDX_ATTR_PERF_PROF_BIT		5
-#define TDX_ATTR_PERF_PROF		BIT_ULL(TDX_ATTR_PERF_PROF_BIT)
-#define TDX_ATTR_PMT_PROF_BIT		6
-#define TDX_ATTR_PMT_PROF		BIT_ULL(TDX_ATTR_PMT_PROF_BIT)
-#define TDX_ATTR_ICSSD_BIT		16
-#define TDX_ATTR_ICSSD			BIT_ULL(TDX_ATTR_ICSSD_BIT)
-#define TDX_ATTR_LASS_BIT		27
-#define TDX_ATTR_LASS			BIT_ULL(TDX_ATTR_LASS_BIT)
-#define TDX_ATTR_SEPT_VE_DISABLE_BIT	28
-#define TDX_ATTR_SEPT_VE_DISABLE	BIT_ULL(TDX_ATTR_SEPT_VE_DISABLE_BIT)
-#define TDX_ATTR_MIGRATABLE_BIT		29
-#define TDX_ATTR_MIGRATABLE		BIT_ULL(TDX_ATTR_MIGRATABLE_BIT)
-#define TDX_ATTR_PKS_BIT		30
-#define TDX_ATTR_PKS			BIT_ULL(TDX_ATTR_PKS_BIT)
-#define TDX_ATTR_KL_BIT			31
-#define TDX_ATTR_KL			BIT_ULL(TDX_ATTR_KL_BIT)
-#define TDX_ATTR_TPA_BIT		62
-#define TDX_ATTR_TPA			BIT_ULL(TDX_ATTR_TPA_BIT)
-#define TDX_ATTR_PERFMON_BIT		63
-#define TDX_ATTR_PERFMON		BIT_ULL(TDX_ATTR_PERFMON_BIT)
+/* TDX TD attributes */
+#define TDX_TD_ATTR_DEBUG_BIT		0
+#define TDX_TD_ATTR_DEBUG		BIT_ULL(TDX_TD_ATTR_DEBUG_BIT)
+#define TDX_TD_ATTR_HGS_PLUS_PROF_BIT	4
+#define TDX_TD_ATTR_HGS_PLUS_PROF	BIT_ULL(TDX_TD_ATTR_HGS_PLUS_PROF_BIT)
+#define TDX_TD_ATTR_PERF_PROF_BIT	5
+#define TDX_TD_ATTR_PERF_PROF		BIT_ULL(TDX_TD_ATTR_PERF_PROF_BIT)
+#define TDX_TD_ATTR_PMT_PROF_BIT	6
+#define TDX_TD_ATTR_PMT_PROF		BIT_ULL(TDX_TD_ATTR_PMT_PROF_BIT)
+#define TDX_TD_ATTR_ICSSD_BIT		16
+#define TDX_TD_ATTR_ICSSD		BIT_ULL(TDX_TD_ATTR_ICSSD_BIT)
+#define TDX_TD_ATTR_LASS_BIT		27
+#define TDX_TD_ATTR_LASS		BIT_ULL(TDX_TD_ATTR_LASS_BIT)
+#define TDX_TD_ATTR_SEPT_VE_DISABLE_BIT	28
+#define TDX_TD_ATTR_SEPT_VE_DISABLE	BIT_ULL(TDX_TD_ATTR_SEPT_VE_DISABLE_BIT)
+#define TDX_TD_ATTR_MIGRATABLE_BIT	29
+#define TDX_TD_ATTR_MIGRATABLE		BIT_ULL(TDX_TD_ATTR_MIGRATABLE_BIT)
+#define TDX_TD_ATTR_PKS_BIT		30
+#define TDX_TD_ATTR_PKS			BIT_ULL(TDX_TD_ATTR_PKS_BIT)
+#define TDX_TD_ATTR_KL_BIT		31
+#define TDX_TD_ATTR_KL			BIT_ULL(TDX_TD_ATTR_KL_BIT)
+#define TDX_TD_ATTR_TPA_BIT		62
+#define TDX_TD_ATTR_TPA			BIT_ULL(TDX_TD_ATTR_TPA_BIT)
+#define TDX_TD_ATTR_PERFMON_BIT		63
+#define TDX_TD_ATTR_PERFMON		BIT_ULL(TDX_TD_ATTR_PERFMON_BIT)
 
 /* TDX TD-Scope Metadata. To be used by TDG.VM.WR and TDG.VM.RD */
 #define TDCS_CONFIG_FLAGS		0x1110000300000016
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index efb7d589b672..c539c2e6109f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -62,7 +62,7 @@ void tdh_vp_wr_failed(struct vcpu_tdx *tdx, char *uclass, char *op, u32 field,
 	pr_err("TDH_VP_WR[%s.0x%x]%s0x%llx failed: 0x%llx\n", uclass, field, op, val, err);
 }
 
-#define KVM_SUPPORTED_TD_ATTRS (TDX_ATTR_SEPT_VE_DISABLE)
+#define KVM_SUPPORTED_TD_ATTRS (TDX_TD_ATTR_SEPT_VE_DISABLE)
 
 static __always_inline struct kvm_tdx *to_kvm_tdx(struct kvm *kvm)
 {
@@ -700,7 +700,7 @@ int tdx_vcpu_create(struct kvm_vcpu *vcpu)
 	vcpu->arch.l1_tsc_scaling_ratio = kvm_tdx->tsc_multiplier;
 
 	vcpu->arch.guest_state_protected =
-		!(to_kvm_tdx(vcpu->kvm)->attributes & TDX_ATTR_DEBUG);
+		!(to_kvm_tdx(vcpu->kvm)->attributes & TDX_TD_ATTR_DEBUG);
 
 	if ((kvm_tdx->xfam & XFEATURE_MASK_XTILE) == XFEATURE_MASK_XTILE)
 		vcpu->arch.xfd_no_write_intercept = true;

---

## [5] Xiaoyao Li — 2025-07-15
*Subject: [PATCH v3 4/4] KVM: TDX: Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS*

Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS to include
"TDX" in the name, making it clear that it pertains to TDX.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c539c2e6109f..9473610d32e6 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -62,7 +62,7 @@ void tdh_vp_wr_failed(struct vcpu_tdx *tdx, char *uclass, char *op, u32 field,
 	pr_err("TDH_VP_WR[%s.0x%x]%s0x%llx failed: 0x%llx\n", uclass, field, op, val, err);
 }
 
-#define KVM_SUPPORTED_TD_ATTRS (TDX_TD_ATTR_SEPT_VE_DISABLE)
+#define KVM_SUPPORTED_TDX_TD_ATTRS (TDX_TD_ATTR_SEPT_VE_DISABLE)
 
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

## [6] Sean Christopherson — 2025-07-15
*Subject: Re: [PATCH v3 0/4] TDX: Clean up the definitions of TDX TD ATTRIBUTES*

On Tue, Jul 15, 2025, Xiaoyao Li wrote:
> Xiaoyao Li (4):
>   x86/tdx: Fix the typo in TDX_ATTR_MIGRTABLE

Acked-by: Sean Christopherson <seanjc@google.com>

---

## [7] Edgecombe, Rick P — 2025-07-15
*Subject: Re: [PATCH v3 3/4] x86/tdx: Rename TDX_ATTR_* to TDX_TD_ATTR_**

On Tue, 2025-07-15 at 17:13 +0800, Xiaoyao Li wrote:
> The macros TDX_ATTR_* and DEF_TDX_ATTR_* are related to TD attributes,
> which are TD-scope attributes. Naming them as TDX_ATTR_* can be somewhat

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [8] Edgecombe, Rick P — 2025-07-15
*Subject: Re: [PATCH v3 2/4] KVM: TDX: Remove redundant definitions of
 TDX_TD_ATTR_**

On Tue, 2025-07-15 at 17:13 +0800, Xiaoyao Li wrote:
> There are definitions of TD attributes bits inside asm/shared/tdx.h as
> TDX_ATTR_*.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [9] Edgecombe, Rick P — 2025-07-15
*Subject: Re: [PATCH v3 0/4] TDX: Clean up the definitions of TDX TD ATTRIBUTES*

On Tue, 2025-07-15 at 08:10 -0700, Sean Christopherson wrote:
> Acked-by: Sean Christopherson <seanjc@google.com>

LGTM too. I guess we have what we need to try to send this through the tip tree.
How about that for a plan? We can wait a few days and see if Dave swings by.

---

## [10] Binbin Wu — 2025-07-17
*Subject: Re: [PATCH v3 3/4] x86/tdx: Rename TDX_ATTR_* to TDX_TD_ATTR_**

On 7/15/2025 5:13 PM, Xiaoyao Li wrote:
> The macros TDX_ATTR_* and DEF_TDX_ATTR_* are related to TD attributes,
> which are TD-scope attributes. Naming them as TDX_ATTR_* can be somewhat
It seems that tdx_attributes is limited to hold td attributes.
For the same reason, is it better to rename tdx_attributes to tdx_td_attributes?

Otherwise,
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> Rename TDX_ATTR_* to TDX_TD_ATTR_* to explicitly clarify they are
> TD-scope things.

---

## [11] Xiaoyao Li — 2025-09-12
*Subject: Re: [PATCH v3 0/4] TDX: Clean up the definitions of TDX TD ATTRIBUTES*

Dear tip/tdx maintainers,

Kindly ping on this series.

It got Acked-by from KVM maintainer and Reviewed-by from other folks. 
There is one comment from Binbin on tdx_attributes[]. What's your 
preference on it? Would you consider applying this series and leave that 
comment to a separate patch or expect a next version of this series with 
that comment addressed?

On 7/15/2025 5:13 PM, Xiaoyao Li wrote:
> The main purpose of this series was to remove redundant macros between
> core TDX and KVM, along with a typo fix. They were implemented as patch1

---

## [12] Kiryl Shutsemau — 2025-09-12
*Subject: Re: [PATCH v3 3/4] x86/tdx: Rename TDX_ATTR_* to TDX_TD_ATTR_**

On Tue, Jul 15, 2025 at 05:13:11PM +0800, Xiaoyao Li wrote:
> The macros TDX_ATTR_* and DEF_TDX_ATTR_* are related to TD attributes,
> which are TD-scope attributes. Naming them as TDX_ATTR_* can be somewhat

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

---

## [13] Kiryl Shutsemau — 2025-09-12
*Subject: Re: [PATCH v3 4/4] KVM: TDX: Rename KVM_SUPPORTED_TD_ATTRS to
 KVM_SUPPORTED_TDX_TD_ATTRS*

On Tue, Jul 15, 2025 at 05:13:12PM +0800, Xiaoyao Li wrote:
> Rename KVM_SUPPORTED_TD_ATTRS to KVM_SUPPORTED_TDX_TD_ATTRS to include
> "TDX" in the name, making it clear that it pertains to TDX.

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

---
