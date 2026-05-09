---
title: "x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's\n 0-based level"
date: 2026-01-20
last_reply: 2026-04-03
message_count: 6
participants: ['Sean Christopherson', 'Edgecombe, Rick P', 'Huang, Kai', 'Kiryl Shutsemau', 'Yan Zhao']
---

## [1] Sean Christopherson — 2026-01-20

Rework the TDX APIs to take the kernel's 1-based pg_level enum, not the
TDX-Module's 0-based level.  The APIs are _kernel_ APIs, not TDX-Module
APIs, and the kernel (and KVM) uses "enum pg_level" literally everywhere.

Using "enum pg_level" eliminates ambiguity when looking at the APIs (it's
NOT clear that "int level" refers to the TDX-Module's level), and will
allow for using existing helpers like page_level_size() when support for
hugepages is added to the S-EPT APIs.

No functional change intended.

Cc: Kai Huang <kai.huang@intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Yan Zhao <yan.y.zhao@intel.com>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---

Compile-tested only.  Came across this when looking at the S-EPT hugepage
series, specifically this code:
  
   unsigned long npages = 1 << (level * PTE_SHIFT);

which I was _sure_ was broken, until I realized @level wasn't what I thought
it was.
 
 arch/x86/include/asm/tdx.h  | 14 ++++----------
 arch/x86/kvm/vmx/tdx.c      | 11 ++++-------
 arch/x86/virt/vmx/tdx/tdx.c | 26 ++++++++++++++++++--------
 3 files changed, 26 insertions(+), 25 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 6b338d7f01b7..bc0d03e70fd6 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -189,19 +189,13 @@ static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
 	return ret;
 }
 
-static inline int pg_level_to_tdx_sept_level(enum pg_level level)
-{
-        WARN_ON_ONCE(level == PG_LEVEL_NONE);
-        return level - 1;
-}
-
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
 u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
-u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, enum pg_level level, struct page *page, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page);
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2);
-u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, int level, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level, struct page *page, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, enum pg_level level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mng_key_config(struct tdx_td *td);
 u64 tdh_mng_create(struct tdx_td *td, u16 hkid);
 u64 tdh_vp_create(struct tdx_td *td, struct tdx_vp *vp);
@@ -217,7 +211,7 @@ u64 tdh_vp_rd(struct tdx_vp *vp, u64 field, u64 *data);
 u64 tdh_vp_wr(struct tdx_vp *vp, u64 field, u64 data, u64 mask);
 u64 tdh_phymem_page_reclaim(struct page *page, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size);
 u64 tdh_mem_track(struct tdx_td *tdr);
-u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, enum pg_level level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..c47f4de2f19c 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1648,14 +1648,13 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 			    enum pg_level level, kvm_pfn_t pfn)
 {
-	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	struct page *page = pfn_to_page(pfn);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 entry, level_state;
 	u64 err;
 
-	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, tdx_level, page, &entry, &level_state);
+	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, level, page, &entry, &level_state);
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
@@ -1699,12 +1698,11 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, void *private_spt)
 {
-	int tdx_level = pg_level_to_tdx_sept_level(level);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	struct page *page = virt_to_page(private_spt);
 	u64 err, entry, level_state;
 
-	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level, page, &entry,
+	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, level, page, &entry,
 			       &level_state);
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
@@ -1788,7 +1786,6 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 					 enum pg_level level, u64 mirror_spte)
 {
 	struct page *page = pfn_to_page(spte_to_pfn(mirror_spte));
-	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
@@ -1808,7 +1805,7 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 		return;
 
 	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
-			      tdx_level, &entry, &level_state);
+			      level, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
 		return;
 
@@ -1824,7 +1821,7 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * Race with TDH.VP.ENTER due to (0-step mitigation) and Guest TDCALLs.
 	 */
 	err = tdh_do_no_vcpus(tdh_mem_page_remove, kvm, &kvm_tdx->td, gpa,
-			      tdx_level, &entry, &level_state);
+			      level, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
 		return;
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5ce4ebe99774..22c0f832cb37 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1516,6 +1516,12 @@ static void tdx_clflush_page(struct page *page)
 	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
 }
 
+static int pg_level_to_tdx_sept_level(enum pg_level level)
+{
+	WARN_ON_ONCE(level == PG_LEVEL_NONE);
+	return level - 1;
+}
+
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;
@@ -1556,10 +1562,11 @@ u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_mem_page_add);
 
-u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, enum pg_level level,
+		     struct page *page, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
-		.rcx = gpa | level,
+		.rcx = gpa | pg_level_to_tdx_sept_level(level),
 		.rdx = tdx_tdr_pa(td),
 		.r8 = page_to_phys(page),
 	};
@@ -1587,10 +1594,11 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_addcx);
 
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level,
+		     struct page *page, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
-		.rcx = gpa | level,
+		.rcx = gpa | pg_level_to_tdx_sept_level(level),
 		.rdx = tdx_tdr_pa(td),
 		.r8 = page_to_phys(page),
 	};
@@ -1606,10 +1614,11 @@ u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_mem_page_aug);
 
-u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, int level, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, enum pg_level level,
+			u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
-		.rcx = gpa | level,
+		.rcx = gpa | pg_level_to_tdx_sept_level(level),
 		.rdx = tdx_tdr_pa(td),
 	};
 	u64 ret;
@@ -1822,10 +1831,11 @@ u64 tdh_mem_track(struct tdx_td *td)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_mem_track);
 
-u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, enum pg_level level,
+			u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
-		.rcx = gpa | level,
+		.rcx = gpa | pg_level_to_tdx_sept_level(level),
 		.rdx = tdx_tdr_pa(td),
 	};
 	u64 ret;

base-commit: 24d479d26b25bce5faea3ddd9fa8f3a6c3129ea7

---

## [2] Edgecombe, Rick P — 2026-01-20
*Subject: Re: [PATCH] x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's
 0-based level*

On Tue, 2026-01-20 at 12:39 -0800, Sean Christopherson wrote:
> > Rework the TDX APIs to take the kernel's 1-based pg_level enum, not the
> > TDX-Module's 0-based level.  The APIs are _kernel_ APIs, not TDX-Module

Makes sense.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

> > 
> > Cc: Kai Huang <kai.huang@intel.com>

The line increase is just from wrapped lines, so it's kinda less code.

> > 
> > diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
                                                         ^WTH, oops.
> > +u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, enum pg_level level, u64 *ext_err1, u64 *ext_err2);
> >  u64 tdh_phymem_cache_wb(bool resume);

---

## [3] Huang, Kai — 2026-01-20
*Subject: Re: [PATCH] x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's
 0-based level*

On Tue, 2026-01-20 at 12:39 -0800, Sean Christopherson wrote:
> Rework the TDX APIs to take the kernel's 1-based pg_level enum, not the
> TDX-Module's 0-based level.  The APIs are _kernel_ APIs, not TDX-Module

Tested that running/destroying TD worked fine:

Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Kai Huang <kai.huang@intel.com>

---

## [4] Kiryl Shutsemau — 2026-01-21
*Subject: Re: [PATCH] x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's
 0-based level*

On Tue, Jan 20, 2026 at 12:39:37PM -0800, Sean Christopherson wrote:
> Rework the TDX APIs to take the kernel's 1-based pg_level enum, not the
> TDX-Module's 0-based level.  The APIs are _kernel_ APIs, not TDX-Module

Acked-by: Kiryl Shutsemau <kas@kernel.org>

---

## [5] Yan Zhao — 2026-01-22
*Subject: Re: [PATCH] x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's
 0-based level*

Reviewed-by: Yan Zhao <yan.y.zhao@intel.com>
Tested-by: Yan Zhao <yan.y.zhao@intel.com>

On Tue, Jan 20, 2026 at 12:39:37PM -0800, Sean Christopherson wrote:
> Rework the TDX APIs to take the kernel's 1-based pg_level enum, not the
> TDX-Module's 0-based level.  The APIs are _kernel_ APIs, not TDX-Module

---

## [6] Sean Christopherson — 2026-04-03
*Subject: Re: [PATCH] x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's
 0-based level*

On Tue, Jan 20, 2026, Sean Christopherson wrote:
> Rework the TDX APIs to take the kernel's 1-based pg_level enum, not the
> TDX-Module's 0-based level.  The APIs are _kernel_ APIs, not TDX-Module

This still applies cleanly, any chance this can be picked up for 7.1 to avoid
prototype conflicts in ongoing work?

---
