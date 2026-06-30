---
title: '[RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage'
date: 2026-01-28
last_reply: 2026-06-30
message_count: 155
participants: ['Sean Christopherson', 'Konrad Rzeszutek Wilk', 'Dave Hansen', 'Edgecombe, Rick P', 'Yan Zhao', 'Huang, Kai']
---

## [1] Sean Christopherson — 2026-01-28

This is a combined series of Dynamic PAMT (from Rick), and S-EPT hugepage
support (from Yan).  Except for some last minute tweaks to the DPAMT array
args stuff, a version of this based on a Google-internal kernel has been
moderately well tested (thanks Vishal!).  But overall it's still firmly RFC
as I have deliberately NOT addressed others feedback from v4 of DPAMT and v3
of S-EPT hugepage (mostly lack of cycles), and there's at least one patch in
here that shouldn't be merged as-is (the quick-and-dirty switch from struct
page to raw pfns).

My immediate goal is to solidify the designs for DPAMT and S-EPT hugepage.
Given the substantial design changes I am proposing, posting an end-to-end
RFC seemed like a much better method than trying to communicate my thoughts
piecemeal.

As for landing these series, I think the fastest overall approach would be
to land patches 1-4 asap (tangentially related cleanups and fixes), agree
on a design (hopefully), and then hand control back to Rick and Yan to polish
their respective series for merge.

I also want to land the VMXON series[*] before DPAMT, because there's a nasty
wart where KVM wires up a DPAMT-specific hook even if DPAMT is disabled,
because KVM's ordering needs to set the vendor hooks before tdx_sysinfo is
ready.  Decoupling VMXON from KVM solves that problem, because it lets the
TDX subsystem parse sysinfo before TDX is loaded.

Beyond that dependency, I am comfortable landing both DPAMT and S-EPT hugepage
support without any other prereqs, i.e. without an in-tree way to light up
the S-EPT hugepage code due to lack of hugepage support in guest_memfd.
Outside of the guest_memfd arch hook for in-place conversion, S-EPT hugepage
support doesn't have any direction dependencies/conflicts with guest_memfd
hugepage or in-place conversion support (which is great, because it means we
didn't totally botch the design!).  E.g. Vishal's been able to test this code
precisely because it applies relatively cleanly on an internal branch with a
whole pile of guest_memfd changes.

Applies on kvm-x86 next (specifically kvm-x86-next-2026.01.23).

[*] https://lore.kernel.org/all/20251206011054.494190-1-seanjc@google.com

P.S. I apologize if I clobbered any of the Author attribution or SoBs.  I
     was moving patches around and synchronizing between an internal tree
     and this upstream version, so things may have gotten a bit wonky.

Isaku Yamahata (1):
  KVM: x86/tdp_mmu: Alloc external_spt page for mirror page table
    splitting

Kiryl Shutsemau (12):
  x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>
  x86/tdx: Add helpers to check return status codes
  x86/virt/tdx: Allocate page bitmap for Dynamic PAMT
  x86/virt/tdx: Allocate reference counters for PAMT memory
  x86/virt/tdx: Improve PAMT refcounts allocation for sparse memory
  x86/virt/tdx: Add tdx_alloc/free_control_page() helpers
  x86/virt/tdx: Optimize tdx_alloc/free_control_page() helpers
  KVM: TDX: Allocate PAMT memory for TD and vCPU control structures
  KVM: TDX: Get/put PAMT pages when (un)mapping private memory
  x86/virt/tdx: Enable Dynamic PAMT
  Documentation/x86: Add documentation for TDX's Dynamic PAMT
  x86/virt/tdx: Get/Put DPAMT page pair if and only if mapping size is
    4KB

Rick Edgecombe (3):
  x86/virt/tdx: Simplify tdmr_get_pamt_sz()
  x86/tdx: Add APIs to support get/put of DPAMT entries from KVM, under
    spinlock
  KVM: x86/mmu: Prevent hugepage promotion for mirror roots in fault
    path

Sean Christopherson (22):
  x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's 0-based level
  KVM: x86/mmu: Update iter->old_spte if cmpxchg64 on mirror SPTE
    "fails"
  KVM: TDX: Account all non-transient page allocations for per-TD
    structures
  KVM: x86: Make "external SPTE" ops that can fail RET0 static calls
  KVM: TDX: Drop kvm_x86_ops.link_external_spt(), use
    .set_external_spte() for all
  KVM: x86/mmu: Fold set_external_spte_present() into its sole caller
  KVM: x86/mmu: Plumb the SPTE _pointer_ into the TDP MMU's
    handle_changed_spte()
  KVM: x86/mmu: Propagate mirror SPTE removal to S-EPT in
    handle_changed_spte()
  KVM: x86: Rework .free_external_spt() into .reclaim_external_sp()
  KVM: Allow owner of kvm_mmu_memory_cache to provide a custom page
    allocator
  KVM: x86/mmu: Allocate/free S-EPT pages using
    tdx_{alloc,free}_control_page()
  *** DO NOT MERGE *** x86/virt/tdx: Don't assume guest memory is backed
    by struct page
  x86/virt/tdx: Extend "reset page" quirk to support huge pages
  KVM: x86/mmu: Plumb the old_spte into kvm_x86_ops.set_external_spte()
  KVM: TDX: Hoist tdx_sept_remove_private_spte() above
    set_private_spte()
  KVM: TDX: Handle removal of leaf SPTEs in .set_private_spte()
  KVM: TDX: Add helper to handle mapping leaf SPTE into S-EPT
  KVM: TDX: Move S-EPT page demotion TODO to tdx_sept_set_private_spte()
  KVM: x86/mmu: Add Dynamic PAMT support in TDP MMU for vCPU-induced
    page split
  KVM: guest_memfd: Add helpers to get start/end gfns give
    gmem+slot+pgoff
  *** DO NOT MERGE *** KVM: guest_memfd: Add pre-zap arch hook for
    shared<=>private conversion
  KVM: x86/mmu: Add support for splitting S-EPT hugepages on conversion

Xiaoyao Li (1):
  x86/virt/tdx: Add API to demote a 2MB mapping to 512 4KB mappings

Yan Zhao (6):
  x86/virt/tdx: Enhance tdh_mem_page_aug() to support huge pages
  x86/virt/tdx: Enhance tdh_phymem_page_wbinvd_hkid() to invalidate huge
    pages
  KVM: TDX: Add core support for splitting/demoting 2MiB S-EPT to 4KiB
  KVM: x86: Introduce hugepage_set_guest_inhibit()
  KVM: TDX: Honor the guest's accept level contained in an EPT violation
  KVM: TDX: Turn on PG_LEVEL_2M

 Documentation/arch/x86/tdx.rst              |  21 +
 arch/x86/coco/tdx/tdx.c                     |  10 +-
 arch/x86/include/asm/kvm-x86-ops.h          |   9 +-
 arch/x86/include/asm/kvm_host.h             |  36 +-
 arch/x86/include/asm/shared/tdx.h           |   1 +
 arch/x86/include/asm/shared/tdx_errno.h     | 104 +++
 arch/x86/include/asm/tdx.h                  | 127 ++--
 arch/x86/include/asm/tdx_global_metadata.h  |   1 +
 arch/x86/kvm/Kconfig                        |   1 +
 arch/x86/kvm/mmu.h                          |   4 +
 arch/x86/kvm/mmu/mmu.c                      |  34 +-
 arch/x86/kvm/mmu/mmu_internal.h             |  11 -
 arch/x86/kvm/mmu/tdp_mmu.c                  | 315 ++++----
 arch/x86/kvm/mmu/tdp_mmu.h                  |   2 +
 arch/x86/kvm/vmx/tdx.c                      | 468 +++++++++---
 arch/x86/kvm/vmx/tdx.h                      |   5 +-
 arch/x86/kvm/vmx/tdx_arch.h                 |   3 +
 arch/x86/kvm/vmx/tdx_errno.h                |  40 -
 arch/x86/virt/vmx/tdx/tdx.c                 | 762 +++++++++++++++++---
 arch/x86/virt/vmx/tdx/tdx.h                 |   6 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |   7 +
 include/linux/kvm_host.h                    |   5 +
 include/linux/kvm_types.h                   |   2 +
 virt/kvm/Kconfig                            |   4 +
 virt/kvm/guest_memfd.c                      |  71 +-
 virt/kvm/kvm_main.c                         |   7 +-
 26 files changed, 1576 insertions(+), 480 deletions(-)
 create mode 100644 arch/x86/include/asm/shared/tdx_errno.h
 delete mode 100644 arch/x86/kvm/vmx/tdx_errno.h


base-commit: e81f7c908e1664233974b9f20beead78cde6343a

---

## [2] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 01/45] x86/tdx: Use pg_level in TDX APIs, not the
 TDX-Module's 0-based level*

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
Acked-by: Kiryl Shutsemau <kas@kernel.org>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
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
index 5df9d32d2058..561461c9d131 100644
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

---

## [3] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if cmpxchg64
 on mirror SPTE "fails"*

Pass a pointer to iter->old_spte, not simply its value, when setting an
external SPTE in __tdp_mmu_set_spte_atomic(), so that the iterator's value
will be updated if the cmpxchg64 to freeze the mirror SPTE fails.  The bug
is currently benign as TDX is mutualy exclusive with all paths that do
"local" retry", e.g. clear_dirty_gfn_range() and wrprot_gfn_range().

Fixes: 77ac7079e66d ("KVM: x86/tdp_mmu: Propagate building mirror page tables")
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 10 +++++-----
 1 file changed, 5 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 9c26038f6b77..0feda295859a 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -509,10 +509,10 @@ static void *get_external_spt(gfn_t gfn, u64 new_spte, int level)
 }
 
 static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sptep,
-						 gfn_t gfn, u64 old_spte,
+						 gfn_t gfn, u64 *old_spte,
 						 u64 new_spte, int level)
 {
-	bool was_present = is_shadow_present_pte(old_spte);
+	bool was_present = is_shadow_present_pte(*old_spte);
 	bool is_present = is_shadow_present_pte(new_spte);
 	bool is_leaf = is_present && is_last_spte(new_spte, level);
 	int ret = 0;
@@ -525,7 +525,7 @@ static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sp
 	 * page table has been modified. Use FROZEN_SPTE similar to
 	 * the zapping case.
 	 */
-	if (!try_cmpxchg64(rcu_dereference(sptep), &old_spte, FROZEN_SPTE))
+	if (!try_cmpxchg64(rcu_dereference(sptep), old_spte, FROZEN_SPTE))
 		return -EBUSY;
 
 	/*
@@ -541,7 +541,7 @@ static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sp
 		ret = kvm_x86_call(link_external_spt)(kvm, gfn, level, external_spt);
 	}
 	if (ret)
-		__kvm_tdp_mmu_write_spte(sptep, old_spte);
+		__kvm_tdp_mmu_write_spte(sptep, *old_spte);
 	else
 		__kvm_tdp_mmu_write_spte(sptep, new_spte);
 	return ret;
@@ -670,7 +670,7 @@ static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
 			return -EBUSY;
 
 		ret = set_external_spte_present(kvm, iter->sptep, iter->gfn,
-						iter->old_spte, new_spte, iter->level);
+						&iter->old_spte, new_spte, iter->level);
 		if (ret)
 			return ret;
 	} else {

---

## [4] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 03/45] KVM: TDX: Account all non-transient page
 allocations for per-TD structures*

Account all non-transient allocations associated with a single TD (or its
vCPUs), as KVM's ABI is that allocations that are active for the lifetime
of a VM are accounted.  Leave temporary allocations, i.e. allocations that
are freed within a single function/ioctl, unaccounted, to again align with
KVM's existing behavior, e.g. see commit dd103407ca31 ("KVM: X86: Remove
unnecessary GFP_KERNEL_ACCOUNT for temporary variables").

Fixes: 8d032b683c29 ("KVM: TDX: create/destroy VM structure")
Fixes: a50f673f25e0 ("KVM: TDX: Do TDX specific vcpu initialization")
Cc: stable@vger.kernel.org
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 12 ++++++------
 1 file changed, 6 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 561461c9d131..5688c77616e3 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2397,7 +2397,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	atomic_inc(&nr_configured_hkid);
 
-	tdr_page = alloc_page(GFP_KERNEL);
+	tdr_page = alloc_page(GFP_KERNEL_ACCOUNT);
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2405,12 +2405,12 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	/* TDVPS = TDVPR(4K page) + TDCX(multiple 4K pages), -1 for TDVPR. */
 	kvm_tdx->td.tdcx_nr_pages = tdx_sysinfo->td_ctrl.tdvps_base_size / PAGE_SIZE - 1;
 	tdcs_pages = kcalloc(kvm_tdx->td.tdcs_nr_pages, sizeof(*kvm_tdx->td.tdcs_pages),
-			     GFP_KERNEL);
+			     GFP_KERNEL_ACCOUNT);
 	if (!tdcs_pages)
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL);
+		tdcs_pages[i] = alloc_page(GFP_KERNEL_ACCOUNT);
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2885,7 +2885,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL);
+	page = alloc_page(GFP_KERNEL_ACCOUNT);
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2898,14 +2898,14 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	tdx->vp.tdvpr_pa = page_to_phys(tdx->vp.tdvpr_page);
 
 	tdx->vp.tdcx_pages = kcalloc(kvm_tdx->td.tdcx_nr_pages, sizeof(*tdx->vp.tdcx_pages),
-			       	     GFP_KERNEL);
+				     GFP_KERNEL_ACCOUNT);
 	if (!tdx->vp.tdcx_pages) {
 		ret = -ENOMEM;
 		goto free_tdvpr;
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL);
+		page = alloc_page(GFP_KERNEL_ACCOUNT);
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;

---

## [5] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 04/45] KVM: x86: Make "external SPTE" ops that can fail
 RET0 static calls*

Define kvm_x86_ops .link_external_spt(), .set_external_spte(), and
.free_external_spt() as RET0 static calls so that an unexpected call to a
a default operation doesn't consume garbage.

Fixes: 77ac7079e66d ("KVM: x86/tdp_mmu: Propagate building mirror page tables")
Fixes: 94faba8999b9 ("KVM: x86/tdp_mmu: Propagate tearing down mirror page tables")
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index de709fb5bd76..c18a033bee7e 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -94,9 +94,9 @@ KVM_X86_OP_OPTIONAL_RET0(set_tss_addr)
 KVM_X86_OP_OPTIONAL_RET0(set_identity_map_addr)
 KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
-KVM_X86_OP_OPTIONAL(link_external_spt)
-KVM_X86_OP_OPTIONAL(set_external_spte)
-KVM_X86_OP_OPTIONAL(free_external_spt)
+KVM_X86_OP_OPTIONAL_RET0(link_external_spt)
+KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
+KVM_X86_OP_OPTIONAL_RET0(free_external_spt)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)

---

## [6] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 05/45] KVM: TDX: Drop kvm_x86_ops.link_external_spt(),
 use .set_external_spte() for all*

Drop the dedicated .link_external_spt() for linking non-leaf S-EPT pages,
and instead funnel everything through .set_external_spte().  Using separate
hooks doesn't help prevent TDP MMU details from bleeding into TDX, and vice
versa; to the contrary, dedicated callbacks will result in _more_ pollution
when hugepage support is added, e.g. will require the TDP MMU to know
details about the splitting rules for TDX that aren't all that relevant to
the TDP MMU.

Ideally, KVM would provide a single pair of hooks to set S-EPT entries,
one hook for setting SPTEs under write-lock and another for settings SPTEs
under read-lock (e.g. to ensure the entire operation is "atomic", to allow
for failure, etc.).  Sadly, TDX's requirement that all child S-EPT entries
are removed before the parent makes that impractical: the TDP MMU
deliberately prunes non-leaf SPTEs and _then_ processes its children, thus
making it quite important for the TDP MMU to differentiate between zapping
leaf and non-leaf S-EPT entries.

However, that's the _only_ case that's truly special, and even that case
could be shoehorned into a single hook; it's just wouldn't be a net
positive.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  1 -
 arch/x86/include/asm/kvm_host.h    |  3 --
 arch/x86/kvm/mmu/tdp_mmu.c         | 37 +++---------------
 arch/x86/kvm/vmx/tdx.c             | 61 ++++++++++++++++++++----------
 4 files changed, 48 insertions(+), 54 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index c18a033bee7e..57eb1f4832ae 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -94,7 +94,6 @@ KVM_X86_OP_OPTIONAL_RET0(set_tss_addr)
 KVM_X86_OP_OPTIONAL_RET0(set_identity_map_addr)
 KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
-KVM_X86_OP_OPTIONAL_RET0(link_external_spt)
 KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
 KVM_X86_OP_OPTIONAL_RET0(free_external_spt)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index e441f270f354..d12ca0f8a348 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1853,9 +1853,6 @@ struct kvm_x86_ops {
 	void (*load_mmu_pgd)(struct kvm_vcpu *vcpu, hpa_t root_hpa,
 			     int root_level);
 
-	/* Update external mapping with page table link. */
-	int (*link_external_spt)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				void *external_spt);
 	/* Update the external page table from spte getting set. */
 	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				 u64 mirror_spte);
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 0feda295859a..56ad056e6042 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -495,31 +495,17 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 	call_rcu(&sp->rcu_head, tdp_mmu_free_sp_rcu_callback);
 }
 
-static void *get_external_spt(gfn_t gfn, u64 new_spte, int level)
-{
-	if (is_shadow_present_pte(new_spte) && !is_last_spte(new_spte, level)) {
-		struct kvm_mmu_page *sp = spte_to_child_sp(new_spte);
-
-		WARN_ON_ONCE(sp->role.level + 1 != level);
-		WARN_ON_ONCE(sp->gfn != gfn);
-		return sp->external_spt;
-	}
-
-	return NULL;
-}
-
 static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sptep,
 						 gfn_t gfn, u64 *old_spte,
 						 u64 new_spte, int level)
 {
-	bool was_present = is_shadow_present_pte(*old_spte);
-	bool is_present = is_shadow_present_pte(new_spte);
-	bool is_leaf = is_present && is_last_spte(new_spte, level);
-	int ret = 0;
-
-	KVM_BUG_ON(was_present, kvm);
+	int ret;
 
 	lockdep_assert_held(&kvm->mmu_lock);
+
+	if (KVM_BUG_ON(is_shadow_present_pte(*old_spte), kvm))
+		return -EIO;
+
 	/*
 	 * We need to lock out other updates to the SPTE until the external
 	 * page table has been modified. Use FROZEN_SPTE similar to
@@ -528,18 +514,7 @@ static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sp
 	if (!try_cmpxchg64(rcu_dereference(sptep), old_spte, FROZEN_SPTE))
 		return -EBUSY;
 
-	/*
-	 * Use different call to either set up middle level
-	 * external page table, or leaf.
-	 */
-	if (is_leaf) {
-		ret = kvm_x86_call(set_external_spte)(kvm, gfn, level, new_spte);
-	} else {
-		void *external_spt = get_external_spt(gfn, new_spte, level);
-
-		KVM_BUG_ON(!external_spt, kvm);
-		ret = kvm_x86_call(link_external_spt)(kvm, gfn, level, external_spt);
-	}
+	ret = kvm_x86_call(set_external_spte)(kvm, gfn, level, new_spte);
 	if (ret)
 		__kvm_tdp_mmu_write_spte(sptep, *old_spte);
 	else
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 5688c77616e3..30494f9ceb31 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1664,18 +1664,58 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+static struct page *tdx_spte_to_external_spt(struct kvm *kvm, gfn_t gfn,
+					     u64 new_spte, enum pg_level level)
+{
+	struct kvm_mmu_page *sp = spte_to_child_sp(new_spte);
+
+	if (KVM_BUG_ON(!sp->external_spt, kvm) ||
+	    KVM_BUG_ON(sp->role.level + 1 != level, kvm) ||
+	    KVM_BUG_ON(sp->gfn != gfn, kvm))
+		return NULL;
+
+	return virt_to_page(sp->external_spt);
+}
+
+static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
+				     enum pg_level level, u64 mirror_spte)
+{
+	gpa_t gpa = gfn_to_gpa(gfn);
+	u64 err, entry, level_state;
+	struct page *external_spt;
+
+	external_spt = tdx_spte_to_external_spt(kvm, gfn, mirror_spte, level);
+	if (!external_spt)
+		return -EIO;
+
+	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, level, external_spt,
+			       &entry, &level_state);
+	if (unlikely(tdx_operand_busy(err)))
+		return -EBUSY;
+
+	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
+		return -EIO;
+
+	return 0;
+}
+
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, u64 mirror_spte)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
 
+	if (KVM_BUG_ON(!is_shadow_present_pte(mirror_spte), kvm))
+		return -EIO;
+
+	if (!is_last_spte(mirror_spte, level))
+		return tdx_sept_link_private_spt(kvm, gfn, level, mirror_spte);
+
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return -EIO;
 
-	WARN_ON_ONCE(!is_shadow_present_pte(mirror_spte) ||
-		     (mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
+	WARN_ON_ONCE((mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
 	/*
 	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()
@@ -1695,23 +1735,7 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	return tdx_mem_page_aug(kvm, gfn, level, pfn);
 }
 
-static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, void *private_spt)
-{
-	gpa_t gpa = gfn_to_gpa(gfn);
-	struct page *page = virt_to_page(private_spt);
-	u64 err, entry, level_state;
 
-	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, level, page, &entry,
-			       &level_state);
-	if (unlikely(tdx_operand_busy(err)))
-		return -EBUSY;
-
-	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
-		return -EIO;
-
-	return 0;
-}
 
 /*
  * Ensure shared and private EPTs to be flushed on all vCPUs.
@@ -3592,7 +3616,6 @@ void __init tdx_hardware_setup(void)
 	 */
 	vt_x86_ops.vm_size = max_t(unsigned int, vt_x86_ops.vm_size, sizeof(struct kvm_tdx));
 
-	vt_x86_ops.link_external_spt = tdx_sept_link_private_spt;
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
 	vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
 	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;

---

## [7] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 06/45] KVM: x86/mmu: Fold set_external_spte_present()
 into its sole caller*

Fold set_external_spte_present() into __tdp_mmu_set_spte_atomic() in
anticipation of supporting hugepage splitting, at which point other paths
will also set shadow-present external SPTEs.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 82 +++++++++++++++++---------------------
 1 file changed, 36 insertions(+), 46 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 56ad056e6042..6fb48b217f5b 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -495,33 +495,6 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 	call_rcu(&sp->rcu_head, tdp_mmu_free_sp_rcu_callback);
 }
 
-static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sptep,
-						 gfn_t gfn, u64 *old_spte,
-						 u64 new_spte, int level)
-{
-	int ret;
-
-	lockdep_assert_held(&kvm->mmu_lock);
-
-	if (KVM_BUG_ON(is_shadow_present_pte(*old_spte), kvm))
-		return -EIO;
-
-	/*
-	 * We need to lock out other updates to the SPTE until the external
-	 * page table has been modified. Use FROZEN_SPTE similar to
-	 * the zapping case.
-	 */
-	if (!try_cmpxchg64(rcu_dereference(sptep), old_spte, FROZEN_SPTE))
-		return -EBUSY;
-
-	ret = kvm_x86_call(set_external_spte)(kvm, gfn, level, new_spte);
-	if (ret)
-		__kvm_tdp_mmu_write_spte(sptep, *old_spte);
-	else
-		__kvm_tdp_mmu_write_spte(sptep, new_spte);
-	return ret;
-}
-
 /**
  * handle_changed_spte - handle bookkeeping associated with an SPTE change
  * @kvm: kvm instance
@@ -626,6 +599,8 @@ static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
 							 struct tdp_iter *iter,
 							 u64 new_spte)
 {
+	u64 *raw_sptep = rcu_dereference(iter->sptep);
+
 	/*
 	 * The caller is responsible for ensuring the old SPTE is not a FROZEN
 	 * SPTE.  KVM should never attempt to zap or manipulate a FROZEN SPTE,
@@ -638,31 +613,46 @@ static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
 		int ret;
 
 		/*
-		 * Users of atomic zapping don't operate on mirror roots,
-		 * so don't handle it and bug the VM if it's seen.
+		 * KVM doesn't currently support zapping or splitting mirror
+		 * SPTEs while holding mmu_lock for read.
 		 */
-		if (KVM_BUG_ON(!is_shadow_present_pte(new_spte), kvm))
+		if (KVM_BUG_ON(is_shadow_present_pte(iter->old_spte), kvm) ||
+		    KVM_BUG_ON(!is_shadow_present_pte(new_spte), kvm))
 			return -EBUSY;
 
-		ret = set_external_spte_present(kvm, iter->sptep, iter->gfn,
-						&iter->old_spte, new_spte, iter->level);
+		/*
+		 * Temporarily freeze the SPTE until the external PTE operation
+		 * has completed, e.g. so that concurrent faults don't attempt
+		 * to install a child PTE in the external page table before the
+		 * parent PTE has been written.
+		 */
+		if (!try_cmpxchg64(raw_sptep, &iter->old_spte, FROZEN_SPTE))
+			return -EBUSY;
+
+		/*
+		 * Update the external PTE.  On success, set the mirror SPTE to
+		 * the desired value.  On failure, restore the old SPTE so that
+		 * the SPTE isn't frozen in perpetuity.
+		 */
+		ret = kvm_x86_call(set_external_spte)(kvm, iter->gfn,
+						      iter->level, new_spte);
 		if (ret)
-			return ret;
-	} else {
-		u64 *sptep = rcu_dereference(iter->sptep);
-
-		/*
-		 * Note, fast_pf_fix_direct_spte() can also modify TDP MMU SPTEs
-		 * and does not hold the mmu_lock.  On failure, i.e. if a
-		 * different logical CPU modified the SPTE, try_cmpxchg64()
-		 * updates iter->old_spte with the current value, so the caller
-		 * operates on fresh data, e.g. if it retries
-		 * tdp_mmu_set_spte_atomic()
-		 */
-		if (!try_cmpxchg64(sptep, &iter->old_spte, new_spte))
-			return -EBUSY;
+			__kvm_tdp_mmu_write_spte(iter->sptep, iter->old_spte);
+		else
+			__kvm_tdp_mmu_write_spte(iter->sptep, new_spte);
+		return ret;
 	}
 
+	/*
+	 * Note, fast_pf_fix_direct_spte() can also modify TDP MMU SPTEs and
+	 * does not hold the mmu_lock.  On failure, i.e. if a different logical
+	 * CPU modified the SPTE, try_cmpxchg64() updates iter->old_spte with
+	 * the current value, so the caller operates on fresh data, e.g. if it
+	 * retries tdp_mmu_set_spte_atomic()
+	 */
+	if (!try_cmpxchg64(raw_sptep, &iter->old_spte, new_spte))
+		return -EBUSY;
+
 	return 0;
 }

---

## [8] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 07/45] KVM: x86/mmu: Plumb the SPTE _pointer_ into the
 TDP MMU's handle_changed_spte()*

Plumb the SPTE pointer into handle_changed_spte() so that remove leaf
mirror entries can be forwarded to TDX in handle_changed_spte(), instead
of effectively requiring callers to manually do so.  Relying on each
caller to invoke .remove_external_spte() is confusing and brittle, e.g.
subtly relies tdp_mmu_set_spte_atomic() never removing SPTEs.  This will
also allow consolidating all S-EPT updates into a single kvm_x86_ops hook.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 21 +++++++++++----------
 1 file changed, 11 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 6fb48b217f5b..8743cd020d12 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -320,9 +320,9 @@ void kvm_tdp_mmu_alloc_root(struct kvm_vcpu *vcpu, bool mirror)
 	}
 }
 
-static void handle_changed_spte(struct kvm *kvm, int as_id, gfn_t gfn,
-				u64 old_spte, u64 new_spte, int level,
-				bool shared);
+static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
+				gfn_t gfn, u64 old_spte, u64 new_spte,
+				int level, bool shared);
 
 static void tdp_account_mmu_page(struct kvm *kvm, struct kvm_mmu_page *sp)
 {
@@ -471,7 +471,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 			old_spte = kvm_tdp_mmu_write_spte(sptep, old_spte,
 							  FROZEN_SPTE, level);
 		}
-		handle_changed_spte(kvm, kvm_mmu_page_as_id(sp), gfn,
+		handle_changed_spte(kvm, kvm_mmu_page_as_id(sp), sptep, gfn,
 				    old_spte, FROZEN_SPTE, level, shared);
 
 		if (is_mirror_sp(sp)) {
@@ -499,6 +499,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
  * handle_changed_spte - handle bookkeeping associated with an SPTE change
  * @kvm: kvm instance
  * @as_id: the address space of the paging structure the SPTE was a part of
+ * @sptep: pointer to the SPTE
  * @gfn: the base GFN that was mapped by the SPTE
  * @old_spte: The value of the SPTE before the change
  * @new_spte: The value of the SPTE after the change
@@ -511,9 +512,9 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
  * dirty logging updates are handled in common code, not here (see make_spte()
  * and fast_pf_fix_direct_spte()).
  */
-static void handle_changed_spte(struct kvm *kvm, int as_id, gfn_t gfn,
-				u64 old_spte, u64 new_spte, int level,
-				bool shared)
+static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
+				gfn_t gfn, u64 old_spte, u64 new_spte,
+				int level, bool shared)
 {
 	bool was_present = is_shadow_present_pte(old_spte);
 	bool is_present = is_shadow_present_pte(new_spte);
@@ -685,8 +686,8 @@ static inline int __must_check tdp_mmu_set_spte_atomic(struct kvm *kvm,
 	if (ret)
 		return ret;
 
-	handle_changed_spte(kvm, iter->as_id, iter->gfn, iter->old_spte,
-			    new_spte, iter->level, true);
+	handle_changed_spte(kvm, iter->as_id, iter->sptep, iter->gfn,
+			    iter->old_spte, new_spte, iter->level, true);
 
 	return 0;
 }
@@ -720,7 +721,7 @@ static u64 tdp_mmu_set_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 
 	old_spte = kvm_tdp_mmu_write_spte(sptep, old_spte, new_spte, level);
 
-	handle_changed_spte(kvm, as_id, gfn, old_spte, new_spte, level, false);
+	handle_changed_spte(kvm, as_id, sptep, gfn, old_spte, new_spte, level, false);
 
 	/*
 	 * Users that do non-atomic setting of PTEs don't operate on mirror

---

## [9] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal to
 S-EPT in handle_changed_spte()*

Invoke .remove_external_spte() in handle_changed_spte() as appropriate
instead of relying on callers to do the right thing.  Relying on callers
to invoke .remove_external_spte() is confusing and brittle, e.g. subtly
relies tdp_mmu_set_spte_atomic() never removing SPTEs, and removing an
S-EPT entry in tdp_mmu_set_spte() is bizarre (yeah, the VM is bugged so
it doesn't matter in practice, but it's still weird).

Implementing rules-based logic in a common chokepoint will also make it
easier to reason about the correctness of splitting hugepages when support
for S-EPT hugepages comes along.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 43 +++++++++++++-------------------------
 1 file changed, 14 insertions(+), 29 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 8743cd020d12..27ac520f2a89 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -359,25 +359,6 @@ static void tdp_mmu_unlink_sp(struct kvm *kvm, struct kvm_mmu_page *sp)
 	spin_unlock(&kvm->arch.tdp_mmu_pages_lock);
 }
 
-static void remove_external_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
-				 int level)
-{
-	/*
-	 * External (TDX) SPTEs are limited to PG_LEVEL_4K, and external
-	 * PTs are removed in a special order, involving free_external_spt().
-	 * But remove_external_spte() will be called on non-leaf PTEs via
-	 * __tdp_mmu_zap_root(), so avoid the error the former would return
-	 * in this case.
-	 */
-	if (!is_last_spte(old_spte, level))
-		return;
-
-	/* Zapping leaf spte is allowed only when write lock is held. */
-	lockdep_assert_held_write(&kvm->mmu_lock);
-
-	kvm_x86_call(remove_external_spte)(kvm, gfn, level, old_spte);
-}
-
 /**
  * handle_removed_pt() - handle a page table removed from the TDP structure
  *
@@ -473,11 +454,6 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 		}
 		handle_changed_spte(kvm, kvm_mmu_page_as_id(sp), sptep, gfn,
 				    old_spte, FROZEN_SPTE, level, shared);
-
-		if (is_mirror_sp(sp)) {
-			KVM_BUG_ON(shared, kvm);
-			remove_external_spte(kvm, gfn, old_spte, level);
-		}
 	}
 
 	if (is_mirror_sp(sp) &&
@@ -590,10 +566,21 @@ static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 	 * the paging structure.  Note the WARN on the PFN changing without the
 	 * SPTE being converted to a hugepage (leaf) or being zapped.  Shadow
 	 * pages are kernel allocations and should never be migrated.
+	 *
+	 * When removing leaf entries from a mirror, immediately propagate the
+	 * changes to the external page tables.  Note, non-leaf mirror entries
+	 * are handled by handle_removed_pt(), as TDX requires that all leaf
+	 * entries are removed before the owning page table.  Note #2, writes
+	 * to make mirror PTEs shadow-present are propagated to external page
+	 * tables by __tdp_mmu_set_spte_atomic(), as KVM needs to ensure the
+	 * external page table was successfully updated before marking the
+	 * mirror SPTE present.
 	 */
 	if (was_present && !was_leaf &&
 	    (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed)))
 		handle_removed_pt(kvm, spte_to_child_pt(old_spte, level), shared);
+	else if (was_leaf && is_mirror_sptep(sptep) && !is_leaf)
+		kvm_x86_call(remove_external_spte)(kvm, gfn, level, old_spte);
 }
 
 static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
@@ -725,12 +712,10 @@ static u64 tdp_mmu_set_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 
 	/*
 	 * Users that do non-atomic setting of PTEs don't operate on mirror
-	 * roots, so don't handle it and bug the VM if it's seen.
+	 * roots.  Bug the VM as this path doesn't propagate such writes to the
+	 * external page tables.
 	 */
-	if (is_mirror_sptep(sptep)) {
-		KVM_BUG_ON(is_shadow_present_pte(new_spte), kvm);
-		remove_external_spte(kvm, gfn, old_spte, level);
-	}
+	KVM_BUG_ON(is_mirror_sptep(sptep) && is_shadow_present_pte(new_spte), kvm);
 
 	return old_spte;
 }

---

## [10] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 09/45] KVM: x86: Rework .free_external_spt() into .reclaim_external_sp()*

Massage .free_external_spt() into .reclaim_external_sp() to free up (pun
intended) "free" for actually freeing memory, and to allow TDX to do more
than just "free" the S-EPT entry.  Specifically, nullify external_spt to
leak the S-EPT page if reclaiming the page fails, as that detail and
implementation choice has no business living in the TDP MMU.

Use "sp" instead of "spt" even though "spt" is arguably more accurate, as
"spte" and "spt" are dangerously close in name, and because the key
parameter is a kvm_mmu_page, not a pointer to an S-EPT page table.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  2 +-
 arch/x86/include/asm/kvm_host.h    |  4 ++--
 arch/x86/kvm/mmu/tdp_mmu.c         | 13 ++-----------
 arch/x86/kvm/vmx/tdx.c             | 27 ++++++++++++---------------
 4 files changed, 17 insertions(+), 29 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 57eb1f4832ae..c17cedc485c9 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -95,8 +95,8 @@ KVM_X86_OP_OPTIONAL_RET0(set_identity_map_addr)
 KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
 KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
-KVM_X86_OP_OPTIONAL_RET0(free_external_spt)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
+KVM_X86_OP_OPTIONAL(reclaim_external_sp)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index d12ca0f8a348..b35a07ed11fb 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1858,8 +1858,8 @@ struct kvm_x86_ops {
 				 u64 mirror_spte);
 
 	/* Update external page tables for page table about to be freed. */
-	int (*free_external_spt)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				 void *external_spt);
+	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
+				    struct kvm_mmu_page *sp);
 
 	/* Update external page table from spte getting removed, and flush TLB. */
 	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 27ac520f2a89..18764dbc97ea 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -456,17 +456,8 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 				    old_spte, FROZEN_SPTE, level, shared);
 	}
 
-	if (is_mirror_sp(sp) &&
-	    WARN_ON(kvm_x86_call(free_external_spt)(kvm, base_gfn, sp->role.level,
-						    sp->external_spt))) {
-		/*
-		 * Failed to free page table page in mirror page table and
-		 * there is nothing to do further.
-		 * Intentionally leak the page to prevent the kernel from
-		 * accessing the encrypted page.
-		 */
-		sp->external_spt = NULL;
-	}
+	if (is_mirror_sp(sp))
+		kvm_x86_call(reclaim_external_sp)(kvm, base_gfn, sp);
 
 	call_rcu(&sp->rcu_head, tdp_mmu_free_sp_rcu_callback);
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 30494f9ceb31..66bc3ceb5e17 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1783,27 +1783,24 @@ static void tdx_track(struct kvm *kvm)
 	kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);
 }
 
-static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, void *private_spt)
+static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
+					struct kvm_mmu_page *sp)
 {
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-
 	/*
-	 * free_external_spt() is only called after hkid is freed when TD is
-	 * tearing down.
 	 * KVM doesn't (yet) zap page table pages in mirror page table while
 	 * TD is active, though guest pages mapped in mirror page table could be
 	 * zapped during TD is active, e.g. for shared <-> private conversion
 	 * and slot move/deletion.
+	 *
+	 * In other words, KVM should only free mirror page tables after the
+	 * TD's hkid is freed, when the TD is being torn down.
+	 *
+	 * If the S-EPT PTE can't be removed for any reason, intentionally leak
+	 * the page to prevent the kernel from accessing the encrypted page.
 	 */
-	if (KVM_BUG_ON(is_hkid_assigned(kvm_tdx), kvm))
-		return -EIO;
-
-	/*
-	 * The HKID assigned to this TD was already freed and cache was
-	 * already flushed. We don't have to flush again.
-	 */
-	return tdx_reclaim_page(virt_to_page(private_spt));
+	if (KVM_BUG_ON(is_hkid_assigned(to_kvm_tdx(kvm)), kvm) ||
+	    tdx_reclaim_page(virt_to_page(sp->external_spt)))
+		sp->external_spt = NULL;
 }
 
 static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
@@ -3617,7 +3614,7 @@ void __init tdx_hardware_setup(void)
 	vt_x86_ops.vm_size = max_t(unsigned int, vt_x86_ops.vm_size, sizeof(struct kvm_tdx));
 
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
-	vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
+	vt_x86_ops.reclaim_external_sp = tdx_sept_reclaim_private_sp;
 	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;
 	vt_x86_ops.protected_apic_has_interrupt = tdx_protected_apic_has_interrupt;
 }

---

## [11] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 10/45] x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Today there are two separate locations where TDX error codes are defined:
         arch/x86/include/asm/tdx.h
         arch/x86/kvm/vmx/tdx_errno.h

They have some overlap that is already defined similarly. Reduce the
duplication and prepare to introduce some helpers for these error codes in
the central place by unifying them. Join them at:
        asm/shared/tdx_errno.h
...and update the headers that contained the duplicated definitions to
include the new unified header.

"asm/shared" is used for sharing TDX code between the early compressed
code and the normal kernel code. While the compressed code for the guest
doesn't use these error code header definitions today, it does make the
types of calls that return the values they define. So place the defines in
"shared" location so that it can, but leave such cleanups for future
changes.

Opportunistically massage some comments. Also, adjust
_BITUL()->_BITULL() to address 32 bit build errors after the move.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/shared/tdx.h             |  1 +
 .../vmx => include/asm/shared}/tdx_errno.h    | 27 +++++++++++++++----
 arch/x86/include/asm/tdx.h                    | 20 --------------
 arch/x86/kvm/vmx/tdx.h                        |  1 -
 4 files changed, 23 insertions(+), 26 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (65%)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 8bc074c8d7c6..6a1646fc2b2f 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -4,6 +4,7 @@
 
 #include <linux/bits.h>
 #include <linux/types.h>
+#include <asm/shared/tdx_errno.h>
 
 #define TDX_HYPERCALL_STANDARD  0
 
diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
similarity index 65%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/shared/tdx_errno.h
index 6ff4672c4181..3aa74f6a6119 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -1,14 +1,16 @@
 /* SPDX-License-Identifier: GPL-2.0 */
-/* architectural status code for SEAMCALL */
+#ifndef _X86_SHARED_TDX_ERRNO_H
+#define _X86_SHARED_TDX_ERRNO_H
 
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
+#include <asm/trapnr.h>
 
+/* Upper 32 bit of the TDX error code encodes the status */
 #define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
 
 /*
- * TDX SEAMCALL Status Codes (returned in RAX)
+ * TDX SEAMCALL Status Codes
  */
+#define TDX_SUCCESS				0ULL
 #define TDX_NON_RECOVERABLE_VCPU		0x4000000100000000ULL
 #define TDX_NON_RECOVERABLE_TD			0x4000000200000000ULL
 #define TDX_NON_RECOVERABLE_TD_NON_ACCESSIBLE	0x6000000500000000ULL
@@ -17,6 +19,7 @@
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
+#define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
@@ -28,6 +31,20 @@
 #define TDX_EPT_ENTRY_STATE_INCORRECT		0xC0000B0D00000000ULL
 #define TDX_METADATA_FIELD_NOT_READABLE		0xC0000C0200000000ULL
 
+/*
+ * SW-defined error codes.
+ *
+ * Bits 47:40 == 0xFF indicate Reserved status code class that never used by
+ * TDX module.
+ */
+#define TDX_ERROR			_BITULL(63)
+#define TDX_NON_RECOVERABLE		_BITULL(62)
+#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
+#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _ULL(0xFFFF0000))
+
+#define TDX_SEAMCALL_GP			(TDX_SW_ERROR | X86_TRAP_GP)
+#define TDX_SEAMCALL_UD			(TDX_SW_ERROR | X86_TRAP_UD)
+
 /*
  * TDX module operand ID, appears in 31:0 part of error code as
  * detail information
@@ -37,4 +54,4 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#endif /* _X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index bc0d03e70fd6..c3c574511094 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -12,26 +12,6 @@
 #include <asm/trapnr.h>
 #include <asm/shared/tdx.h>
 
-/*
- * SW-defined error codes.
- *
- * Bits 47:40 == 0xFF indicate Reserved status code class that never used by
- * TDX module.
- */
-#define TDX_ERROR			_BITUL(63)
-#define TDX_NON_RECOVERABLE		_BITUL(62)
-#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
-#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _UL(0xFFFF0000))
-
-#define TDX_SEAMCALL_GP			(TDX_SW_ERROR | X86_TRAP_GP)
-#define TDX_SEAMCALL_UD			(TDX_SW_ERROR | X86_TRAP_UD)
-
-/*
- * TDX module SEAMCALL leaf function error codes
- */
-#define TDX_SUCCESS		0ULL
-#define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
-
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index 45b5183ccb36..ce2720a028ad 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -3,7 +3,6 @@
 #define __KVM_X86_VMX_TDX_H
 
 #include "tdx_arch.h"
-#include "tdx_errno.h"
 
 #ifdef CONFIG_KVM_INTEL_TDX
 #include "common.h"

---

## [12] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 11/45] x86/tdx: Add helpers to check return status codes*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

The TDX error code has a complex structure. The upper 32 bits encode the
status code (higher level information), while the lower 32 bits provide
clues about the error, such as operand ID, CPUID leaf, MSR index, etc.

In practice, the kernel logic cares mostly about the status code. Whereas
the error details are more often dumped to warnings to be used as
debugging breadcrumbs. This results in a lot of code that masks the status
code and then checks the resulting value. Future code to support Dynamic
PAMT will add yet more SEAMCALL error code checking. To prepare for this,
do some cleanup to reduce the boiler plate error code parsing.

Since the lower bits that contain details are needed for both error
printing and a few cases where the logical code flow does depend on them,
don’t reduce the boiler plate by masking the detail bits inside the
SEAMCALL wrappers, returning only the status code. Instead, create some
helpers to perform the needed masking and comparisons.

For the status code based checks, create a macro for generating the
helpers based on the name. Name the helpers IS_TDX_FOO(), based on the
discussion in the Link.

Many of the checks that consult the error details are only done in a
single place. It could be argued that there is not any code savings by
adding helpers for these checks. Add helpers for them anyway so that the
checks look consistent when uses with checks that are used in multiple
places (e.g. sc_retry_prerr()).

Finally, update the code that previously open coded the bit math to use
the helpers.

Link: https://lore.kernel.org/kvm/aJNycTvk1GEWgK_Q@google.com/
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/tdx/tdx.c                 | 10 +++---
 arch/x86/include/asm/shared/tdx_errno.h | 47 ++++++++++++++++++++++++-
 arch/x86/include/asm/tdx.h              |  2 +-
 arch/x86/kvm/vmx/tdx.c                  | 40 +++++++++------------
 arch/x86/virt/vmx/tdx/tdx.c             |  8 ++---
 5 files changed, 73 insertions(+), 34 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..167c5b273c40 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -129,9 +129,9 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 
 	ret = __tdcall(TDG_MR_REPORT, &args);
 	if (ret) {
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
+		if (IS_TDX_OPERAND_INVALID(ret))
 			return -ENXIO;
-		else if (TDCALL_RETURN_CODE(ret) == TDCALL_OPERAND_BUSY)
+		else if (IS_TDX_OPERAND_BUSY(ret))
 			return -EBUSY;
 		return -EIO;
 	}
@@ -165,9 +165,9 @@ int tdx_mcall_extend_rtmr(u8 index, u8 *data)
 
 	ret = __tdcall(TDG_MR_RTMR_EXTEND, &args);
 	if (ret) {
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
+		if (IS_TDX_OPERAND_INVALID(ret))
 			return -ENXIO;
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_OPERAND_BUSY)
+		if (IS_TDX_OPERAND_BUSY(ret))
 			return -EBUSY;
 		return -EIO;
 	}
@@ -316,7 +316,7 @@ static void reduce_unnecessary_ve(void)
 {
 	u64 err = tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
 
-	if (err == TDX_SUCCESS)
+	if (IS_TDX_SUCCESS(err))
 		return;
 
 	/*
diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index 3aa74f6a6119..e302aed31b50 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -5,7 +5,7 @@
 #include <asm/trapnr.h>
 
 /* Upper 32 bit of the TDX error code encodes the status */
-#define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
+#define TDX_STATUS_MASK				0xFFFFFFFF00000000ULL
 
 /*
  * TDX SEAMCALL Status Codes
@@ -54,4 +54,49 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
+#ifndef __ASSEMBLER__
+#include <linux/bits.h>
+#include <linux/types.h>
+
+static inline u64 TDX_STATUS(u64 err)
+{
+	return err & TDX_STATUS_MASK;
+}
+
+static inline bool IS_TDX_NON_RECOVERABLE(u64 err)
+{
+	return (err & TDX_NON_RECOVERABLE) == TDX_NON_RECOVERABLE;
+}
+
+static inline bool IS_TDX_SEAMCALL_VMFAILINVALID(u64 err)
+{
+	return (err & TDX_SEAMCALL_VMFAILINVALID) ==
+		TDX_SEAMCALL_VMFAILINVALID;
+}
+
+static inline bool IS_TDX_SEAMCALL_GP(u64 err)
+{
+	return err == TDX_SEAMCALL_GP;
+}
+
+static inline bool IS_TDX_SEAMCALL_UD(u64 err)
+{
+	return err == TDX_SEAMCALL_UD;
+}
+
+#define DEFINE_TDX_ERRNO_HELPER(error)			\
+	static inline bool IS_##error(u64 err)	\
+	{						\
+		return TDX_STATUS(err) == error;	\
+	}
+
+DEFINE_TDX_ERRNO_HELPER(TDX_SUCCESS);
+DEFINE_TDX_ERRNO_HELPER(TDX_RND_NO_ENTROPY);
+DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_INVALID);
+DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_BUSY);
+DEFINE_TDX_ERRNO_HELPER(TDX_VCPU_NOT_ASSOCIATED);
+DEFINE_TDX_ERRNO_HELPER(TDX_FLUSHVP_NOT_DONE);
+DEFINE_TDX_ERRNO_HELPER(TDX_SW_ERROR);
+
+#endif /* __ASSEMBLER__ */
 #endif /* _X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index c3c574511094..441a26988d3b 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -117,7 +117,7 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 		preempt_disable();
 		ret = __seamcall_dirty_cache(func, fn, args);
 		preempt_enable();
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
+	} while (IS_TDX_RND_NO_ENTROPY(ret) && --retry);
 
 	return ret;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 66bc3ceb5e17..4ef414ee27b4 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -220,12 +220,6 @@ static DEFINE_MUTEX(tdx_lock);
 
 static atomic_t nr_configured_hkid;
 
-static bool tdx_operand_busy(u64 err)
-{
-	return (err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_BUSY;
-}
-
-
 /*
  * A per-CPU list of TD vCPUs associated with a given CPU.
  * Protected by interrupt mask. Only manipulated by the CPU owning this per-CPU
@@ -312,7 +306,7 @@ static inline void tdx_disassociate_vp(struct kvm_vcpu *vcpu)
 	lockdep_assert_held_write(&kvm->mmu_lock);				\
 										\
 	__err = tdh_func(args);							\
-	if (unlikely(tdx_operand_busy(__err))) {				\
+	if (unlikely(IS_TDX_OPERAND_BUSY(__err))) {				\
 		WRITE_ONCE(__kvm_tdx->wait_for_sept_zap, true);			\
 		kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);	\
 										\
@@ -400,7 +394,7 @@ static void tdx_flush_vp(void *_arg)
 		 * migration.  No other thread uses TDVPR in those cases.
 		 */
 		err = tdh_vp_flush(&to_tdx(vcpu)->vp);
-		if (unlikely(err && err != TDX_VCPU_NOT_ASSOCIATED)) {
+		if (unlikely(!IS_TDX_VCPU_NOT_ASSOCIATED(err))) {
 			/*
 			 * This function is called in IPI context. Do not use
 			 * printk to avoid console semaphore.
@@ -467,7 +461,7 @@ static void smp_func_do_phymem_cache_wb(void *unused)
 	/*
 	 * TDH.PHYMEM.CACHE.WB flushes caches associated with any TDX private
 	 * KeyID on the package or core.  The TDX module may not finish the
-	 * cache flush but return TDX_INTERRUPTED_RESUMEABLE instead.  The
+	 * cache flush but return TDX_ERR_INTERRUPTED_RESUMEABLE instead.  The
 	 * kernel should retry it until it returns success w/o rescheduling.
 	 */
 	for (i = TDX_SEAMCALL_RETRIES; i > 0; i--) {
@@ -522,7 +516,7 @@ void tdx_mmu_release_hkid(struct kvm *kvm)
 	 * associations, as all vCPU fds have been released at this stage.
 	 */
 	err = tdh_mng_vpflushdone(&kvm_tdx->td);
-	if (err == TDX_FLUSHVP_NOT_DONE)
+	if (IS_TDX_FLUSHVP_NOT_DONE(err))
 		goto out;
 	if (TDX_BUG_ON(err, TDH_MNG_VPFLUSHDONE, kvm)) {
 		pr_err("tdh_mng_vpflushdone() failed. HKID %d is leaked.\n",
@@ -937,7 +931,7 @@ static __always_inline u32 tdx_to_vmx_exit_reason(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u32 exit_reason;
 
-	switch (tdx->vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) {
+	switch (TDX_STATUS(tdx->vp_enter_ret)) {
 	case TDX_SUCCESS:
 	case TDX_NON_RECOVERABLE_VCPU:
 	case TDX_NON_RECOVERABLE_TD:
@@ -1011,7 +1005,7 @@ static fastpath_t tdx_exit_handlers_fastpath(struct kvm_vcpu *vcpu)
 	 * EXIT_FASTPATH_REENTER_GUEST to exit fastpath, otherwise, the
 	 * requester may be blocked endlessly.
 	 */
-	if (unlikely(tdx_operand_busy(vp_enter_ret)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(vp_enter_ret)))
 		return EXIT_FASTPATH_EXIT_HANDLED;
 
 	return EXIT_FASTPATH_NONE;
@@ -1107,7 +1101,7 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	if (unlikely(tdx->vp_enter_ret == EXIT_REASON_EPT_MISCONFIG))
 		return EXIT_FASTPATH_NONE;
 
-	if (unlikely((tdx->vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR))
+	if (unlikely(IS_TDX_SW_ERROR(tdx->vp_enter_ret)))
 		return EXIT_FASTPATH_NONE;
 
 	trace_kvm_exit(vcpu, KVM_ISA_VMX);
@@ -1636,7 +1630,7 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 
 	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
 			       kvm_tdx->page_add_src, &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_ADD, entry, level_state, kvm))
@@ -1655,7 +1649,7 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	u64 err;
 
 	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, level, page, &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_AUG, entry, level_state, kvm))
@@ -1690,7 +1684,7 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, level, external_spt,
 			       &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
 	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
@@ -2011,7 +2005,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	 * Handle TDX SW errors, including TDX_SEAMCALL_UD, TDX_SEAMCALL_GP and
 	 * TDX_SEAMCALL_VMFAILINVALID.
 	 */
-	if (unlikely((vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR)) {
+	if (unlikely(IS_TDX_SW_ERROR(vp_enter_ret))) {
 		KVM_BUG_ON(!kvm_rebooting, vcpu->kvm);
 		goto unhandled_exit;
 	}
@@ -2022,7 +2016,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 		 * not enabled, TDX_NON_RECOVERABLE must be set.
 		 */
 		WARN_ON_ONCE(vcpu->arch.guest_state_protected &&
-				!(vp_enter_ret & TDX_NON_RECOVERABLE));
+			     !IS_TDX_NON_RECOVERABLE(vp_enter_ret));
 		vcpu->run->exit_reason = KVM_EXIT_FAIL_ENTRY;
 		vcpu->run->fail_entry.hardware_entry_failure_reason = exit_reason.full;
 		vcpu->run->fail_entry.cpu = vcpu->arch.last_vmentry_cpu;
@@ -2036,7 +2030,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	}
 
 	WARN_ON_ONCE(exit_reason.basic != EXIT_REASON_TRIPLE_FAULT &&
-		     (vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) != TDX_SUCCESS);
+		     !IS_TDX_SUCCESS(vp_enter_ret));
 
 	switch (exit_reason.basic) {
 	case EXIT_REASON_TRIPLE_FAULT:
@@ -2470,7 +2464,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	err = tdh_mng_create(&kvm_tdx->td, kvm_tdx->hkid);
 	mutex_unlock(&tdx_lock);
 
-	if (err == TDX_RND_NO_ENTROPY) {
+	if (IS_TDX_RND_NO_ENTROPY(err)) {
 		ret = -EAGAIN;
 		goto free_packages;
 	}
@@ -2511,7 +2505,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	kvm_tdx->td.tdcs_pages = tdcs_pages;
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
 		err = tdh_mng_addcx(&kvm_tdx->td, tdcs_pages[i]);
-		if (err == TDX_RND_NO_ENTROPY) {
+		if (IS_TDX_RND_NO_ENTROPY(err)) {
 			/* Here it's hard to allow userspace to retry. */
 			ret = -EAGAIN;
 			goto teardown;
@@ -2523,7 +2517,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	}
 
 	err = tdh_mng_init(&kvm_tdx->td, __pa(td_params), &rcx);
-	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_INVALID) {
+	if (IS_TDX_OPERAND_INVALID(err)) {
 		/*
 		 * Because a user gives operands, don't warn.
 		 * Return a hint to the user because it's sometimes hard for the
@@ -2837,7 +2831,7 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 		return -EINVAL;
 
 	cmd->hw_error = tdh_mr_finalize(&kvm_tdx->td);
-	if (tdx_operand_busy(cmd->hw_error))
+	if (IS_TDX_OPERAND_BUSY(cmd->hw_error))
 		return -EBUSY;
 	if (TDX_BUG_ON(cmd->hw_error, TDH_MR_FINALIZE, kvm))
 		return -EIO;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 22c0f832cb37..783bf704f2cd 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -82,16 +82,16 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 {
 	u64 sret = sc_retry(func, fn, args);
 
-	if (sret == TDX_SUCCESS)
+	if (IS_TDX_SUCCESS(sret))
 		return 0;
 
-	if (sret == TDX_SEAMCALL_VMFAILINVALID)
+	if (IS_TDX_SEAMCALL_VMFAILINVALID(sret))
 		return -ENODEV;
 
-	if (sret == TDX_SEAMCALL_GP)
+	if (IS_TDX_SEAMCALL_GP(sret))
 		return -EOPNOTSUPP;
 
-	if (sret == TDX_SEAMCALL_UD)
+	if (IS_TDX_SEAMCALL_UD(sret))
 		return -EACCES;
 
 	err_func(fn, sret, args);

---

## [13] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 12/45] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

From: Rick Edgecombe <rick.p.edgecombe@intel.com>

For each memory region that the TDX module might use (TDMR), the three
separate PAMT allocations are needed. One for each supported page size
(1GB, 2MB, 4KB). These store information on each page in the TDMR. In
Linux, they are allocated out of one physically contiguous block, in order
to more efficiently use some internal TDX module book keeping resources.
So some simple math is needed to break the single large allocation into
three smaller allocations for each page size.

There are some commonalities in the math needed to calculate the base and
size for each smaller allocation, and so an effort was made to share logic
across the three. Unfortunately doing this turned out naturally tortured,
with a loop iterating over the three page sizes, only to call into a
function with a case statement for each page size. In the future Dynamic
PAMT will add more logic that is special to the 4KB page size, making the
benefit of the math sharing even more questionable.

Three is not a very high number, so get rid of the loop and just duplicate
the small calculation three times. In doing so, setup for future Dynamic
PAMT changes and drop a net 33 lines of code.

Since the loop that iterates over it is gone, further simplify the code by
dropping the array of intermediate size and base storage. Just store the
values to their final locations. Accept the small complication of having
to clear tdmr->pamt_4k_base in the error path, so that tdmr_do_pamt_func()
will not try to operate on the TDMR struct when attempting to free it.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 93 ++++++++++++-------------------------
 1 file changed, 29 insertions(+), 64 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 783bf704f2cd..0c4c873bff80 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -445,31 +445,21 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
  */
-static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-				      u16 pamt_entry_size)
+static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz)
 {
 	unsigned long pamt_sz, nr_pamt_entries;
+	const int tdx_pg_size_shift[] = { PAGE_SHIFT, PMD_SHIFT, PUD_SHIFT };
+	const u16 pamt_entry_size[TDX_PS_NR] = {
+		tdx_sysinfo.tdmr.pamt_4k_entry_size,
+		tdx_sysinfo.tdmr.pamt_2m_entry_size,
+		tdx_sysinfo.tdmr.pamt_1g_entry_size,
+	};
 
-	switch (pgsz) {
-	case TDX_PS_4K:
-		nr_pamt_entries = tdmr->size >> PAGE_SHIFT;
-		break;
-	case TDX_PS_2M:
-		nr_pamt_entries = tdmr->size >> PMD_SHIFT;
-		break;
-	case TDX_PS_1G:
-		nr_pamt_entries = tdmr->size >> PUD_SHIFT;
-		break;
-	default:
-		WARN_ON_ONCE(1);
-		return 0;
-	}
+	nr_pamt_entries = tdmr->size >> tdx_pg_size_shift[pgsz];
+	pamt_sz = nr_pamt_entries * pamt_entry_size[pgsz];
 
-	pamt_sz = nr_pamt_entries * pamt_entry_size;
 	/* TDX requires PAMT size must be 4K aligned */
-	pamt_sz = ALIGN(pamt_sz, PAGE_SIZE);
-
-	return pamt_sz;
+	return PAGE_ALIGN(pamt_sz);
 }
 
 /*
@@ -507,28 +497,21 @@ static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
  * within @tdmr, and set up PAMTs for @tdmr.
  */
 static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
-			    struct list_head *tmb_list,
-			    u16 pamt_entry_size[])
+			    struct list_head *tmb_list)
 {
-	unsigned long pamt_base[TDX_PS_NR];
-	unsigned long pamt_size[TDX_PS_NR];
-	unsigned long tdmr_pamt_base;
 	unsigned long tdmr_pamt_size;
 	struct page *pamt;
-	int pgsz, nid;
-
+	int nid;
 	nid = tdmr_get_nid(tdmr, tmb_list);
 
 	/*
 	 * Calculate the PAMT size for each TDX supported page size
 	 * and the total PAMT size.
 	 */
-	tdmr_pamt_size = 0;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-		pamt_size[pgsz] = tdmr_get_pamt_sz(tdmr, pgsz,
-					pamt_entry_size[pgsz]);
-		tdmr_pamt_size += pamt_size[pgsz];
-	}
+	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M);
+	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G);
+	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
 
 	/*
 	 * Allocate one chunk of physically contiguous memory for all
@@ -536,26 +519,18 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * in overlapped TDMRs.
 	 */
 	pamt = alloc_contig_pages(tdmr_pamt_size >> PAGE_SHIFT, GFP_KERNEL,
-			nid, &node_online_map);
-	if (!pamt)
+				  nid, &node_online_map);
+	if (!pamt) {
+		/*
+		 * tdmr->pamt_4k_base is zero so the
+		 * error path will skip freeing.
+		 */
 		return -ENOMEM;
-
-	/*
-	 * Break the contiguous allocation back up into the
-	 * individual PAMTs for each page size.
-	 */
-	tdmr_pamt_base = page_to_pfn(pamt) << PAGE_SHIFT;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-		pamt_base[pgsz] = tdmr_pamt_base;
-		tdmr_pamt_base += pamt_size[pgsz];
 	}
 
-	tdmr->pamt_4k_base = pamt_base[TDX_PS_4K];
-	tdmr->pamt_4k_size = pamt_size[TDX_PS_4K];
-	tdmr->pamt_2m_base = pamt_base[TDX_PS_2M];
-	tdmr->pamt_2m_size = pamt_size[TDX_PS_2M];
-	tdmr->pamt_1g_base = pamt_base[TDX_PS_1G];
-	tdmr->pamt_1g_size = pamt_size[TDX_PS_1G];
+	tdmr->pamt_4k_base = page_to_phys(pamt);
+	tdmr->pamt_2m_base = tdmr->pamt_4k_base + tdmr->pamt_4k_size;
+	tdmr->pamt_1g_base = tdmr->pamt_2m_base + tdmr->pamt_2m_size;
 
 	return 0;
 }
@@ -586,10 +561,7 @@ static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 	tdmr_get_pamt(tdmr, &pamt_base, &pamt_size);
 
 	/* Do nothing if PAMT hasn't been allocated for this TDMR */
-	if (!pamt_size)
-		return;
-
-	if (WARN_ON_ONCE(!pamt_base))
+	if (!pamt_base)
 		return;
 
 	pamt_func(pamt_base, pamt_size);
@@ -615,14 +587,12 @@ static void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
 
 /* Allocate and set up PAMTs for all TDMRs */
 static int tdmrs_set_up_pamt_all(struct tdmr_info_list *tdmr_list,
-				 struct list_head *tmb_list,
-				 u16 pamt_entry_size[])
+				 struct list_head *tmb_list)
 {
 	int i, ret = 0;
 
 	for (i = 0; i < tdmr_list->nr_consumed_tdmrs; i++) {
-		ret = tdmr_set_up_pamt(tdmr_entry(tdmr_list, i), tmb_list,
-				pamt_entry_size);
+		ret = tdmr_set_up_pamt(tdmr_entry(tdmr_list, i), tmb_list);
 		if (ret)
 			goto err;
 	}
@@ -903,18 +873,13 @@ static int construct_tdmrs(struct list_head *tmb_list,
 			   struct tdmr_info_list *tdmr_list,
 			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
-	u16 pamt_entry_size[TDX_PS_NR] = {
-		sysinfo_tdmr->pamt_4k_entry_size,
-		sysinfo_tdmr->pamt_2m_entry_size,
-		sysinfo_tdmr->pamt_1g_entry_size,
-	};
 	int ret;
 
 	ret = fill_out_tdmrs(tmb_list, tdmr_list);
 	if (ret)
 		return ret;
 
-	ret = tdmrs_set_up_pamt_all(tdmr_list, tmb_list, pamt_entry_size);
+	ret = tdmrs_set_up_pamt_all(tdmr_list, tmb_list);
 	if (ret)
 		return ret;

---

## [14] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 13/45] x86/virt/tdx: Allocate page bitmap for Dynamic PAMT*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

The Physical Address Metadata Table (PAMT) holds TDX metadata for physical
memory and must be allocated by the kernel during TDX module
initialization.

The exact size of the required PAMT memory is determined by the TDX module
and may vary between TDX module versions. Currently it is approximately
0.4% of the system memory. This is a significant commitment, especially if
it is not known upfront whether the machine will run any TDX guests.

For normal PAMT, each memory region that the TDX module might use (TDMR)
needs three separate PAMT allocations. One for each supported page size
(1GB, 2MB, 4KB).

At a high level, Dynamic PAMT still has the 1GB and 2MB levels allocated
on TDX module initialization, but the 4KB level allocated dynamically at
TD runtime. However, in the details, the TDX module still needs some per
4KB page data. The TDX module exposed how many bits per page need to be
allocated (currently it is 1). The bits-per-page value can then be used to
calculate the size to pass in place of the 4KB allocations in the TDMR,
which TDX specs call "PAMT_PAGE_BITMAP".

So in effect, Dynamic PAMT just needs a different (smaller) size
allocation for the 4KB level part of the allocation. Although it is
functionally something different, it is passed in the same way the 4KB page
size PAMT allocation is.

Begin to implement Dynamic PAMT in the kernel by reading the bits-per-page
needed for Dynamic PAMT. Calculate the size needed for the bitmap,
and use it instead of the 4KB size determined for normal PAMT, in the case
of Dynamic PAMT. In doing so, reduce the static allocations to
approximately 0.004%, a 100x improvement.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Enhanced log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h                  |  5 +++++
 arch/x86/include/asm/tdx_global_metadata.h  |  1 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 19 ++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  7 +++++++
 4 files changed, 31 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 441a26988d3b..57d5f07e3735 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -130,6 +130,11 @@ int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
+static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
+{
+	return false; /* To be enabled when kernel is ready */
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 060a2ad744bf..5eb808b23997 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -15,6 +15,7 @@ struct tdx_sys_info_tdmr {
 	u16 pamt_4k_entry_size;
 	u16 pamt_2m_entry_size;
 	u16 pamt_1g_entry_size;
+	u8  pamt_page_bitmap_entry_bits;
 };
 
 struct tdx_sys_info_td_ctrl {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0c4c873bff80..517c6759c3ca 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -441,6 +441,18 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
 	return 0;
 }
 
+static unsigned long tdmr_get_pamt_bitmap_sz(struct tdmr_info *tdmr)
+{
+	unsigned long pamt_sz, nr_pamt_entries;
+	int bits_per_entry;
+
+	bits_per_entry = tdx_sysinfo.tdmr.pamt_page_bitmap_entry_bits;
+	nr_pamt_entries = tdmr->size >> PAGE_SHIFT;
+	pamt_sz = DIV_ROUND_UP(nr_pamt_entries * bits_per_entry, BITS_PER_BYTE);
+
+	return PAGE_ALIGN(pamt_sz);
+}
+
 /*
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
@@ -508,7 +520,12 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * Calculate the PAMT size for each TDX supported page size
 	 * and the total PAMT size.
 	 */
-	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		/* With Dynamic PAMT, PAMT_4K is replaced with a bitmap */
+		tdmr->pamt_4k_size = tdmr_get_pamt_bitmap_sz(tdmr);
+	} else {
+		tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	}
 	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M);
 	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G);
 	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..00ab0e550636 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -33,6 +33,13 @@ static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 		sysinfo_tdmr->pamt_2m_entry_size = val;
 	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000012, &val)))
 		sysinfo_tdmr->pamt_1g_entry_size = val;
+	/*
+	 * Don't fail here if tdx_supports_dynamic_pamt() isn't supported. The
+	 * TDX code can fallback to normal PAMT if it's not supported.
+	 */
+	if (!ret && tdx_supports_dynamic_pamt(&tdx_sysinfo) &&
+	    !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
+		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;
 
 	return ret;
 }

---

## [15] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 14/45] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

The PAMT memory holds metadata for TDX protected memory. With Dynamic
PAMT, the 4KB range of PAMT is allocated on demand. The kernel supplies
the TDX module with a page pair that covers 2MB of host physical memory.

The kernel must provide this page pair before using pages from the range
for TDX. If this is not done, any SEAMCALL that attempts to use the memory
will fail.

Allocate reference counters for every 2MB range to track PAMT memory usage.
This is necessary to accurately determine when PAMT memory needs to be
allocated and when it can be freed.

This allocation will currently consume 2 MB for every 1 TB of address
space from 0 to max_pfn (highest pfn of RAM). The allocation size will
depend on how the ram is physically laid out. In a worse case scenario
where the entire 52 bit address space is covered this would be 8GB. Then
the DPAMT refcount allocations could hypothetically exceed the savings
from Dynamic PAMT, which is 4GB per TB. This is probably unlikely.

However, future changes will reduce this refcount overhead to make DPAMT
always a net win.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 47 ++++++++++++++++++++++++++++++++++++-
 1 file changed, 46 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 517c6759c3ca..db48bf2ce601 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -30,6 +30,7 @@
 #include <linux/suspend.h>
 #include <linux/idr.h>
 #include <linux/kvm_types.h>
+#include <linux/vmalloc.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -51,6 +52,16 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
+/*
+ * On a machine with Dynamic PAMT, the kernel maintains a reference counter
+ * for every 2M range. The counter indicates how many users there are for
+ * the PAMT memory of the 2M range.
+ *
+ * The kernel allocates PAMT memory when the first user arrives and
+ * frees it when the last user has left.
+ */
+static atomic_t *pamt_refcounts;
+
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
 
@@ -184,6 +195,34 @@ int tdx_cpu_enable(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_cpu_enable);
 
+/*
+ * Allocate PAMT reference counters for all physical memory.
+ *
+ * It consumes 2MiB for every 1TiB of physical memory.
+ */
+static int init_pamt_metadata(void)
+{
+	size_t size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	pamt_refcounts = __vmalloc(size, GFP_KERNEL | __GFP_ZERO);
+	if (!pamt_refcounts)
+		return -ENOMEM;
+
+	return 0;
+}
+
+static void free_pamt_metadata(void)
+{
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	vfree(pamt_refcounts);
+	pamt_refcounts = NULL;
+}
+
 /*
  * Add a memory region as a TDX memory block.  The caller must make sure
  * all memory regions are added in address ascending order and don't
@@ -1083,10 +1122,14 @@ static int init_tdx_module(void)
 	 */
 	get_online_mems();
 
-	ret = build_tdx_memlist(&tdx_memlist);
+	ret = init_pamt_metadata();
 	if (ret)
 		goto out_put_tdxmem;
 
+	ret = build_tdx_memlist(&tdx_memlist);
+	if (ret)
+		goto err_free_pamt_metadata;
+
 	/* Allocate enough space for constructing TDMRs */
 	ret = alloc_tdmr_list(&tdx_tdmr_list, &tdx_sysinfo.tdmr);
 	if (ret)
@@ -1136,6 +1179,8 @@ static int init_tdx_module(void)
 	free_tdmr_list(&tdx_tdmr_list);
 err_free_tdxmem:
 	free_tdx_memlist(&tdx_memlist);
+err_free_pamt_metadata:
+	free_pamt_metadata();
 	goto out_put_tdxmem;
 }

---

## [16] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 15/45] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

init_pamt_metadata() allocates PAMT refcounts for all physical memory up
to max_pfn. It might be suboptimal if the physical memory layout is
discontinuous and has large holes.

The refcount allocation vmalloc allocation. This is necessary to support a
large allocation size. The virtually contiguous property also makes it
easy to find a specific 2MB range’s refcount since it can simply be
indexed.

Since vmalloc mappings support remapping during normal kernel runtime,
switch to an approach that only populates refcount pages for the vmalloc
mapping when there is actually memory for that range. This means any holes
in the physical address space won’t use actual physical memory.

The validity of this memory optimization is based on a couple assumptions:
1. Physical holes in the ram layout are commonly large enough for it to be
   worth it.
2. An alternative approach that looks the refcounts via some more layered
   data structure wouldn’t overly complicate the lookups. Or at least
   more than the complexity of managing the vmalloc mapping.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 122 ++++++++++++++++++++++++++++++++++--
 1 file changed, 118 insertions(+), 4 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index db48bf2ce601..f6e80aba5895 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -195,30 +195,135 @@ int tdx_cpu_enable(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_cpu_enable);
 
+/* Find PAMT refcount for a given physical address */
+static atomic_t *tdx_find_pamt_refcount(unsigned long pfn)
+{
+	/* Find which PMD a PFN is in. */
+	unsigned long index = pfn >> (PMD_SHIFT - PAGE_SHIFT);
+
+	return &pamt_refcounts[index];
+}
+
+/* Map a page into the PAMT refcount vmalloc region */
+static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)
+{
+	struct page *page;
+	pte_t entry;
+
+	page = alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!page)
+		return -ENOMEM;
+
+	entry = mk_pte(page, PAGE_KERNEL);
+
+	spin_lock(&init_mm.page_table_lock);
+	/*
+	 * PAMT refcount populations can overlap due to rounding of the
+	 * start/end pfn. Make sure the PAMT range is only populated once.
+	 */
+	if (pte_none(ptep_get(pte)))
+		set_pte_at(&init_mm, addr, pte, entry);
+	else
+		__free_page(page);
+	spin_unlock(&init_mm.page_table_lock);
+
+	return 0;
+}
+
 /*
- * Allocate PAMT reference counters for all physical memory.
+ * Allocate PAMT reference counters for the given PFN range.
  *
  * It consumes 2MiB for every 1TiB of physical memory.
  */
+static int alloc_pamt_refcount(unsigned long start_pfn, unsigned long end_pfn)
+{
+	unsigned long refcount_first, refcount_last;
+	unsigned long mapping_start, mapping_end;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	/*
+	 * 'start_pfn' is inclusive and 'end_pfn' is exclusive. Find the
+	 * range of refcounts the pfn range will need.
+	 */
+	refcount_first = (unsigned long)tdx_find_pamt_refcount(start_pfn);
+	refcount_last   = (unsigned long)tdx_find_pamt_refcount(end_pfn - 1);
+
+	/*
+	 * Calculate the page aligned range that includes the refcounts. The
+	 * teardown logic needs to handle potentially overlapping refcount
+	 * mappings resulting from the alignments.
+	 */
+	mapping_start = round_down(refcount_first, PAGE_SIZE);
+	mapping_end   = round_up(refcount_last + sizeof(*pamt_refcounts), PAGE_SIZE);
+
+
+	return apply_to_page_range(&init_mm, mapping_start, mapping_end - mapping_start,
+				   pamt_refcount_populate, NULL);
+}
+
+/*
+ * Reserve vmalloc range for PAMT reference counters. It covers all physical
+ * address space up to max_pfn. It is going to be populated from
+ * build_tdx_memlist() only for present memory that available for TDX use.
+ *
+ * It reserves 2MiB of virtual address space for every 1TiB of physical memory.
+ */
 static int init_pamt_metadata(void)
 {
-	size_t size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);
+	struct vm_struct *area;
+	size_t size;
 
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
-	pamt_refcounts = __vmalloc(size, GFP_KERNEL | __GFP_ZERO);
-	if (!pamt_refcounts)
+	size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);
+
+	area = get_vm_area(size, VM_SPARSE);
+	if (!area)
 		return -ENOMEM;
 
+	pamt_refcounts = area->addr;
 	return 0;
 }
 
+/* Unmap a page from the PAMT refcount vmalloc region */
+static int pamt_refcount_depopulate(pte_t *pte, unsigned long addr, void *data)
+{
+	struct page *page;
+	pte_t entry;
+
+	spin_lock(&init_mm.page_table_lock);
+
+	entry = ptep_get(pte);
+	/* refcount allocation is sparse, may not be populated */
+	if (!pte_none(entry)) {
+		pte_clear(&init_mm, addr, pte);
+		page = pte_page(entry);
+		__free_page(page);
+	}
+
+	spin_unlock(&init_mm.page_table_lock);
+
+	return 0;
+}
+
+/* Unmap all PAMT refcount pages and free vmalloc range */
 static void free_pamt_metadata(void)
 {
+	size_t size;
+
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return;
 
+	size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+	size = round_up(size, PAGE_SIZE);
+
+	apply_to_existing_page_range(&init_mm,
+				     (unsigned long)pamt_refcounts,
+				     size, pamt_refcount_depopulate,
+				     NULL);
 	vfree(pamt_refcounts);
 	pamt_refcounts = NULL;
 }
@@ -289,10 +394,19 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 		ret = add_tdx_memblock(tmb_list, start_pfn, end_pfn, nid);
 		if (ret)
 			goto err;
+
+		/* Allocated PAMT refcountes for the memblock */
+		ret = alloc_pamt_refcount(start_pfn, end_pfn);
+		if (ret)
+			goto err;
 	}
 
 	return 0;
 err:
+	/*
+	 * Only free TDX memory blocks here, PAMT refcount pages
+	 * will be freed in the init_tdx_module() error path.
+	 */
 	free_tdx_memlist(tmb_list);
 	return ret;
 }

---

## [17] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 16/45] x86/virt/tdx: Add tdx_alloc/free_control_page() helpers*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Add helpers to use when allocating or preparing pages that are gifted to
the TDX-Module for use as control/S-EPT pages, and thus need DPAMT backing.
Make them handle races internally for the case of multiple callers trying
operate on the same 2MB range simultaneously.

While the TDX initialization code in arch/x86 uses pages with 2MB
alignment, KVM will need to hand 4KB pages for it to use. Under DPAMT,
these pages will need DPAMT backing 4KB backing.

Add tdx_alloc_control_page() and tdx_free_control_page() to handle both
page allocation and DPAMT installation. Make them behave like normal
alloc/free functions where allocation can fail in the case of no memory,
but free (with any necessary DPAMT release) always succeeds. Do this so
they can support the existing TDX flows that require cleanups to succeed.
Also create tdx_pamt_put()/tdx_pamt_get() to handle installing DPAMT 4KB
backing for pages that are already allocated (such as external page tables,
or S-EPT pages).

Allocate the pages as GFP_KERNEL_ACCOUNT based on that the allocations
will be easily user triggerable.

Since the source of these pages is the page allocator, multiple TDs could
each get 4KB pages that are covered by the same 2MB range. When this
happens only one page pair needs to be installed to cover the 2MB range.
Similarly, when one page is freed, the DPAMT backing cannot be freed until
all TDX pages in the range are no longer in use. Have the helpers manage
these races internally.

So the requirements are that:

1. Free path cannot fail (i.e. no TDX module BUSY errors).
2. Allocation paths need to handle finding that DPAMT backing is already
   installed, and only return an error in the case of no memory, not in the
   case of losing races with other’s trying to operate on the same DPAMT
   range.
3. Free paths cannot fail, and also need to clean up the DPAMT backing
   when the last page in the 2MB range is no longer needed by TDX.

Previous changes allocated refcounts to be used to track how many 4KB
pages are in use by TDX for each 2MB region. So update those inside the
helpers and use them to decide when to actually install the DPAMT backing
pages.

tdx_pamt_put() needs to guarantee the DPAMT is installed before returning
so that racing threads don’t tell the TDX module to operate on the page
before it’s installed. Take a lock while adjusting the refcount and doing
the actual TDH.PHYMEM.PAMT.ADD/REMOVE to make sure these happen
atomically. The lock is heavyweight, but will be optimized in future
changes. Just do the simple solution before any complex improvements.

TDH.PHYMEM.PAMT.ADD/REMOVE take exclusive locks at the granularity each
2MB range. A simultaneous attempt to operate on the same 2MB region would
result in a BUSY error code returned from the SEAMCALL. Since the
invocation of SEAMCALLs are behind a lock, this won’t conflict.

Besides the contention between TDH.PHYMEM.PAMT.ADD/REMOVE, many other
SEAMCALLs take the same 2MB granularity locks as shared. This means any
attempt to operate on the page by the TDX module while simultaneously
doing PAMT.ADD/REMOVE will result in a BUSY error. This should not happen,
as the PAMT pages always has to be installed before giving the pages to
the TDX module anyway.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  |  24 +++-
 arch/x86/virt/vmx/tdx/tdx.c | 264 ++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |   2 +
 3 files changed, 289 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 57d5f07e3735..fa29be18498c 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -16,6 +16,7 @@
 
 #include <uapi/asm/mce.h>
 #include <asm/tdx_global_metadata.h>
+#include <linux/mm.h>
 #include <linux/pgtable.h>
 
 /*
@@ -135,11 +136,32 @@ static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 	return false; /* To be enabled when kernel is ready */
 }
 
+void tdx_quirk_reset_page(struct page *page);
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
-void tdx_quirk_reset_page(struct page *page);
+struct page *__tdx_alloc_control_page(gfp_t gfp);
+void __tdx_free_control_page(struct page *page);
+
+static inline unsigned long tdx_alloc_control_page(gfp_t gfp)
+{
+	struct page *page = __tdx_alloc_control_page(gfp);
+
+	if (!page)
+		return 0;
+
+	return (unsigned long)page_address(page);
+}
+
+static inline void tdx_free_control_page(unsigned long addr)
+{
+	if (!addr)
+		return;
+
+	__tdx_free_control_page(virt_to_page(addr));
+}
 
 struct tdx_td {
 	/* TD root structure: */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f6e80aba5895..682c8a228b53 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1824,6 +1824,50 @@ u64 tdh_mng_rd(struct tdx_td *td, u64 field, u64 *data)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_mng_rd);
 
+/* Number PAMT pages to be provided to TDX module per 2M region of PA */
+static int tdx_dpamt_entry_pages(void)
+{
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
+}
+
+/*
+ * For SEAMCALLs that pass a bundle of pages, the TDX spec treats the registers
+ * like an array, as they are ordered in the struct.  The effective array size
+ * is (obviously) limited by the number or registers, relative to the starting
+ * register.  Fill the register array at a given starting register, with sanity
+ * checks to avoid overflowing the args structure.
+ */
+static void dpamt_copy_regs_array(struct tdx_module_args *args, void *reg,
+				  u64 *pamt_pa_array, bool copy_to_regs)
+{
+	int size = tdx_dpamt_entry_pages() * sizeof(*pamt_pa_array);
+
+	if (WARN_ON_ONCE(reg + size > (void *)args) + sizeof(*args))
+		return;
+
+	/* Copy PAMT page PA's to/from the struct per the TDX ABI. */
+	if (copy_to_regs)
+		memcpy(reg, pamt_pa_array, size);
+	else
+		memcpy(pamt_pa_array, reg, size);
+}
+
+#define dpamt_copy_from_regs(dst, args, reg)	\
+	dpamt_copy_regs_array(args, &(args)->reg, dst, false)
+
+#define dpamt_copy_to_regs(args, reg, src)	\
+	dpamt_copy_regs_array(args, &(args)->reg, src, true)
+
+/*
+ * When declaring PAMT arrays on the stack, use the maximum theoretical number
+ * of entries that can be squeezed into a SEAMCALL, as stack allocations are
+ * practically free, i.e. any wasted space is a non-issue.
+ */
+#define MAX_NR_DPAMT_ARGS (sizeof(struct tdx_module_args) / sizeof(u64))
+
 u64 tdh_mr_extend(struct tdx_td *td, u64 gpa, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
@@ -2020,6 +2064,226 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
 
+static int alloc_pamt_array(u64 *pa_array)
+{
+	struct page *page;
+	int i;
+
+	for (i = 0; i < tdx_dpamt_entry_pages(); i++) {
+		page = alloc_page(GFP_KERNEL_ACCOUNT);
+		if (!page)
+			goto err;
+		pa_array[i] = page_to_phys(page);
+	}
+
+	return 0;
+err:
+	/*
+	 * Zero the rest of the array to help with
+	 * freeing in error paths.
+	 */
+	for (; i < tdx_dpamt_entry_pages(); i++)
+		pa_array[i] = 0;
+	return -ENOMEM;
+}
+
+static void free_pamt_array(u64 *pa_array)
+{
+	for (int i = 0; i < tdx_dpamt_entry_pages(); i++) {
+		if (!pa_array[i])
+			break;
+
+		/*
+		 * Reset pages unconditionally to cover cases
+		 * where they were passed to the TDX module.
+		 */
+		tdx_quirk_reset_paddr(pa_array[i], PAGE_SIZE);
+
+		__free_page(phys_to_page(pa_array[i]));
+	}
+}
+
+/*
+ * Calculate the arg needed for operating on the DPAMT backing for
+ * a given 4KB page.
+ */
+static u64 pamt_2mb_arg(struct page *page)
+{
+	unsigned long hpa_2mb = ALIGN_DOWN(page_to_phys(page), PMD_SIZE);
+
+	return hpa_2mb | TDX_PS_2M;
+}
+
+/*
+ * Add PAMT backing for the given page. Return's negative error code
+ * for kernel side error conditions (-ENOMEM) and 1 for TDX Module
+ * error. In the case of TDX module error, the return code is stored
+ * in tdx_err.
+ */
+static u64 tdh_phymem_pamt_add(struct page *page, u64 *pamt_pa_array)
+{
+	struct tdx_module_args args = {
+		.rcx = pamt_2mb_arg(page)
+	};
+
+	dpamt_copy_to_regs(&args, rdx, pamt_pa_array);
+
+	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+}
+
+/* Remove PAMT backing for the given page. */
+static u64 tdh_phymem_pamt_remove(struct page *page, u64 *pamt_pa_array)
+{
+	struct tdx_module_args args = {
+		.rcx = pamt_2mb_arg(page),
+	};
+	u64 ret;
+
+	ret = seamcall_ret(TDH_PHYMEM_PAMT_REMOVE, &args);
+	if (ret)
+		return ret;
+
+	dpamt_copy_from_regs(pamt_pa_array, &args, rdx);
+	return 0;
+}
+
+/* Serializes adding/removing PAMT memory */
+static DEFINE_SPINLOCK(pamt_lock);
+
+/* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
+static int tdx_pamt_get(struct page *page)
+{
+	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
+	atomic_t *pamt_refcount;
+	u64 tdx_status;
+	int ret;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	ret = alloc_pamt_array(pamt_pa_array);
+	if (ret)
+		goto out_free;
+
+	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+
+	scoped_guard(spinlock, &pamt_lock) {
+		/*
+		 * If the pamt page is already added (i.e. refcount >= 1),
+		 * then just increment the refcount.
+		 */
+		if (atomic_read(pamt_refcount)) {
+			atomic_inc(pamt_refcount);
+			goto out_free;
+		}
+
+		/* Try to add the pamt page and take the refcount 0->1. */
+		tdx_status = tdh_phymem_pamt_add(page, pamt_pa_array);
+		if (WARN_ON_ONCE(!IS_TDX_SUCCESS(tdx_status))) {
+			ret = -EIO;
+			goto out_free;
+		}
+
+		atomic_inc(pamt_refcount);
+	}
+
+	return 0;
+
+out_free:
+	/*
+	 * pamt_pa_array is populated or zeroed up to tdx_dpamt_entry_pages()
+	 * above. free_pamt_array() can handle either case.
+	 */
+	free_pamt_array(pamt_pa_array);
+	return ret;
+}
+
+/*
+ * Drop PAMT refcount for the given page and free PAMT memory if it is no
+ * longer needed.
+ */
+static void tdx_pamt_put(struct page *page)
+{
+	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
+	atomic_t *pamt_refcount;
+	u64 tdx_status;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+
+	scoped_guard(spinlock, &pamt_lock) {
+		/*
+		 * If the there are more than 1 references on the pamt page,
+		 * don't remove it yet. Just decrement the refcount.
+		 */
+		if (atomic_read(pamt_refcount) > 1) {
+			atomic_dec(pamt_refcount);
+			return;
+		}
+
+		/* Try to remove the pamt page and take the refcount 1->0. */
+		tdx_status = tdh_phymem_pamt_remove(page, pamt_pa_array);
+
+		/*
+		 * Don't free pamt_pa_array as it could hold garbage when
+		 * tdh_phymem_pamt_remove() fails.  Don't panic/BUG_ON(), as
+		 * there is no risk of data corruption, but do yell loudly as
+		 * failure indicates a kernel bug, memory is being leaked, and
+		 * the dangling PAMT entry may cause future operations to fail.
+		 */
+		if (WARN_ON_ONCE(!IS_TDX_SUCCESS(tdx_status)))
+			return;
+
+		atomic_dec(pamt_refcount);
+	}
+
+	/*
+	 * pamt_pa_array is populated up to tdx_dpamt_entry_pages() by the TDX
+	 * module with pages, or remains zero inited. free_pamt_array() can
+	 * handle either case. Just pass it unconditionally.
+	 */
+	free_pamt_array(pamt_pa_array);
+}
+
+/*
+ * Return a page that can be gifted to the TDX-Module for use as a "control"
+ * page, i.e. pages that are used for control and S-EPT structures for a given
+ * TDX guest, and bound to said guest's HKID and thus obtain TDX protections,
+ * including PAMT tracking.
+ */
+struct page *__tdx_alloc_control_page(gfp_t gfp)
+{
+	struct page *page;
+
+	page = alloc_page(gfp);
+	if (!page)
+		return NULL;
+
+	if (tdx_pamt_get(page)) {
+		__free_page(page);
+		return NULL;
+	}
+
+	return page;
+}
+EXPORT_SYMBOL_FOR_KVM(__tdx_alloc_control_page);
+
+/*
+ * Free a page that was gifted to the TDX-Module for use as a control/S-EPT
+ * page. After this, the page is no longer protected by TDX.
+ */
+void __tdx_free_control_page(struct page *page)
+{
+	if (!page)
+		return;
+
+	tdx_pamt_put(page);
+	__free_page(page);
+}
+EXPORT_SYMBOL_FOR_KVM(__tdx_free_control_page);
+
 #ifdef CONFIG_KEXEC_CORE
 void tdx_cpu_flush_cache_for_kexec(void)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 82bb82be8567..46c4214b79fb 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,8 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_PHYMEM_PAMT_ADD		58
+#define TDH_PHYMEM_PAMT_REMOVE		59
 
 /*
  * SEAMCALL leaf:

---

## [18] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 17/45] x86/virt/tdx: Optimize tdx_alloc/free_control_page()
 helpers*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Optimize the PAMT alloc/free helpers to avoid taking the global lock when
possible.

The recently introduced PAMT alloc/free helpers maintain a refcount to
keep track of when it is ok to reclaim and free a 4KB PAMT page. This
refcount is protected by a global lock in order to guarantee that races
don’t result in the PAMT getting freed while another caller requests it
be mapped. But a global lock is a bit heavyweight, especially since the
refcounts can be (already are) updated atomically.

A simple approach would be to increment/decrement the refcount outside of
the lock before actually adjusting the PAMT, and only adjust the PAMT if
the refcount transitions from/to 0. This would correctly allocate and free
the PAMT page without getting out of sync. But there it leaves a race
where a simultaneous caller could see the refcount already incremented and
return before it is actually mapped.

So treat the refcount 0->1 case as a special case. On add, if the refcount
is zero *don’t* increment the refcount outside the lock (to 1). Always
take the lock in that case and only set the refcount to 1 after the PAMT
is actually added. This way simultaneous adders, when PAMT is not
installed yet, will take the slow lock path.

On the 1->0 case, it is ok to return from tdx_pamt_put() when the DPAMT is
not actually freed yet, so the basic approach works. Just decrement the
refcount before  taking the lock. Only do the lock and removal of the PAMT
when the refcount goes to zero.

There is an asymmetry between tdx_pamt_get() and tdx_pamt_put() in that
tdx_pamt_put() goes 1->0 outside the lock, but tdx_pamt_get() does 0-1
inside the lock. Because of this, there is a special race where
tdx_pamt_put() could decrement the refcount to zero before the PAMT is
actually removed, and tdx_pamt_get() could try to do a PAMT.ADD when the
page is already mapped. Luckily the TDX module will tell return a special
error that tells us we hit this case. So handle it specially by looking
for the error code.

The optimization is a little special, so make the code extra commented
and verbose.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Clean up code, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/shared/tdx_errno.h |  2 +
 arch/x86/virt/vmx/tdx/tdx.c             | 69 +++++++++++++++++++------
 2 files changed, 54 insertions(+), 17 deletions(-)

diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index e302aed31b50..acf7197527da 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -21,6 +21,7 @@
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
 #define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
+#define TDX_HPA_RANGE_NOT_FREE			0xC000030400000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
 #define TDX_KEY_STATE_INCORRECT			0xC000081100000000ULL
@@ -94,6 +95,7 @@ DEFINE_TDX_ERRNO_HELPER(TDX_SUCCESS);
 DEFINE_TDX_ERRNO_HELPER(TDX_RND_NO_ENTROPY);
 DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_INVALID);
 DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_BUSY);
+DEFINE_TDX_ERRNO_HELPER(TDX_HPA_RANGE_NOT_FREE);
 DEFINE_TDX_ERRNO_HELPER(TDX_VCPU_NOT_ASSOCIATED);
 DEFINE_TDX_ERRNO_HELPER(TDX_FLUSHVP_NOT_DONE);
 DEFINE_TDX_ERRNO_HELPER(TDX_SW_ERROR);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 682c8a228b53..d333d2790913 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2161,16 +2161,23 @@ static int tdx_pamt_get(struct page *page)
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
+	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+
+	/*
+	 * If the pamt page is already added (i.e. refcount >= 1),
+	 * then just increment the refcount.
+	 */
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
 	ret = alloc_pamt_array(pamt_pa_array);
 	if (ret)
 		goto out_free;
 
-	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
-
 	scoped_guard(spinlock, &pamt_lock) {
 		/*
-		 * If the pamt page is already added (i.e. refcount >= 1),
-		 * then just increment the refcount.
+		 * Lost race to other tdx_pamt_add(). Other task has already allocated
+		 * PAMT memory for the HPA.
 		 */
 		if (atomic_read(pamt_refcount)) {
 			atomic_inc(pamt_refcount);
@@ -2179,12 +2186,30 @@ static int tdx_pamt_get(struct page *page)
 
 		/* Try to add the pamt page and take the refcount 0->1. */
 		tdx_status = tdh_phymem_pamt_add(page, pamt_pa_array);
-		if (WARN_ON_ONCE(!IS_TDX_SUCCESS(tdx_status))) {
+		if (IS_TDX_SUCCESS(tdx_status)) {
+			/*
+			 * The refcount is zero, and this locked path is the only way to
+			 * increase it from 0-1. If the PAMT.ADD was successful, set it
+			 * to 1 (obviously).
+			 */
+			atomic_set(pamt_refcount, 1);
+		} else if (IS_TDX_HPA_RANGE_NOT_FREE(tdx_status)) {
+			/*
+			 * Less obviously, another CPU's call to tdx_pamt_put() could have
+			 * decremented the refcount before entering its lock section.
+			 * In this case, the PAMT is not actually removed yet. Luckily
+			 * TDX module tells about this case, so increment the refcount
+			 * 0-1, so tdx_pamt_put() skips its pending PAMT.REMOVE.
+			 *
+			 * The call didn't need the pages though, so free them.
+			 */
+			atomic_set(pamt_refcount, 1);
+			goto out_free;
+		} else {
+			WARN_ON_ONCE(1);
 			ret = -EIO;
 			goto out_free;
 		}
-
-		atomic_inc(pamt_refcount);
 	}
 
 	return 0;
@@ -2213,15 +2238,21 @@ static void tdx_pamt_put(struct page *page)
 
 	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
 
+	/*
+	 * If the there are more than 1 references on the pamt page,
+	 * don't remove it yet. Just decrement the refcount.
+	 *
+	 * Unlike the paired call in tdx_pamt_get(), decrement the refcount
+	 * outside the lock even if it's the special 0<->1 transition. See
+	 * special logic around HPA_RANGE_NOT_FREE in tdx_pamt_get().
+	 */
+	if (!atomic_dec_and_test(pamt_refcount))
+		return;
+
 	scoped_guard(spinlock, &pamt_lock) {
-		/*
-		 * If the there are more than 1 references on the pamt page,
-		 * don't remove it yet. Just decrement the refcount.
-		 */
-		if (atomic_read(pamt_refcount) > 1) {
-			atomic_dec(pamt_refcount);
+		/* Lost race with tdx_pamt_get(). */
+		if (atomic_read(pamt_refcount))
 			return;
-		}
 
 		/* Try to remove the pamt page and take the refcount 1->0. */
 		tdx_status = tdh_phymem_pamt_remove(page, pamt_pa_array);
@@ -2233,10 +2264,14 @@ static void tdx_pamt_put(struct page *page)
 		 * failure indicates a kernel bug, memory is being leaked, and
 		 * the dangling PAMT entry may cause future operations to fail.
 		 */
-		if (WARN_ON_ONCE(!IS_TDX_SUCCESS(tdx_status)))
+		if (WARN_ON_ONCE(!IS_TDX_SUCCESS(tdx_status))) {
+			/*
+			 * Since the refcount was optimistically decremented above
+			 * outside the lock, revert it if there is a failure.
+			 */
+			atomic_inc(pamt_refcount);
 			return;
-
-		atomic_dec(pamt_refcount);
+		}
 	}
 
 	/*

---

## [19] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 18/45] KVM: TDX: Allocate PAMT memory for TD and vCPU
 control structures*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

TDX TD control structures are provided to the TDX module at 4KB page size
and require PAMT backing. This means for Dynamic PAMT they need to also
have 4KB backings installed. Use the recently introduce TDX APIs for
allocating/freeing control pages, which handle DPAMT maintenance, to
allocate/free TD and vCPU pages for TDX guests.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
[sean: handle alloc+free+reclaim in one patch]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 35 ++++++++++++++---------------------
 1 file changed, 14 insertions(+), 21 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 4ef414ee27b4..323aae4300a1 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -360,7 +360,7 @@ static void tdx_reclaim_control_page(struct page *ctrl_page)
 	if (tdx_reclaim_page(ctrl_page))
 		return;
 
-	__free_page(ctrl_page);
+	__tdx_free_control_page(ctrl_page);
 }
 
 struct tdx_flush_vp_arg {
@@ -597,7 +597,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 
 	tdx_quirk_reset_page(kvm_tdx->td.tdr_page);
 
-	__free_page(kvm_tdx->td.tdr_page);
+	__tdx_free_control_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 }
 
@@ -2412,7 +2412,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	atomic_inc(&nr_configured_hkid);
 
-	tdr_page = alloc_page(GFP_KERNEL_ACCOUNT);
+	tdr_page = __tdx_alloc_control_page(GFP_KERNEL_ACCOUNT);
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2425,7 +2425,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL_ACCOUNT);
+		tdcs_pages[i] = __tdx_alloc_control_page(GFP_KERNEL_ACCOUNT);
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2543,10 +2543,8 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 teardown:
 	/* Only free pages not yet added, so start at 'i' */
 	for (; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i]) {
-			__free_page(tdcs_pages[i]);
-			tdcs_pages[i] = NULL;
-		}
+		__tdx_free_control_page(tdcs_pages[i]);
+		tdcs_pages[i] = NULL;
 	}
 	if (!kvm_tdx->td.tdcs_pages)
 		kfree(tdcs_pages);
@@ -2561,16 +2559,13 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	free_cpumask_var(packages);
 
 free_tdcs:
-	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i])
-			__free_page(tdcs_pages[i]);
-	}
+	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++)
+		__tdx_free_control_page(tdcs_pages[i]);
 	kfree(tdcs_pages);
 	kvm_tdx->td.tdcs_pages = NULL;
 
 free_tdr:
-	if (tdr_page)
-		__free_page(tdr_page);
+	__tdx_free_control_page(tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 
 free_hkid:
@@ -2900,7 +2895,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL_ACCOUNT);
+	page = __tdx_alloc_control_page(GFP_KERNEL_ACCOUNT);
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2920,7 +2915,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL_ACCOUNT);
+		page = __tdx_alloc_control_page(GFP_KERNEL_ACCOUNT);
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;
@@ -2942,7 +2937,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 			 * method, but the rest are freed here.
 			 */
 			for (; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-				__free_page(tdx->vp.tdcx_pages[i]);
+				__tdx_free_control_page(tdx->vp.tdcx_pages[i]);
 				tdx->vp.tdcx_pages[i] = NULL;
 			}
 			return -EIO;
@@ -2970,16 +2965,14 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 
 free_tdcx:
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		if (tdx->vp.tdcx_pages[i])
-			__free_page(tdx->vp.tdcx_pages[i]);
+		__tdx_free_control_page(tdx->vp.tdcx_pages[i]);
 		tdx->vp.tdcx_pages[i] = NULL;
 	}
 	kfree(tdx->vp.tdcx_pages);
 	tdx->vp.tdcx_pages = NULL;
 
 free_tdvpr:
-	if (tdx->vp.tdvpr_page)
-		__free_page(tdx->vp.tdvpr_page);
+	__tdx_free_control_page(tdx->vp.tdvpr_page);
 	tdx->vp.tdvpr_page = NULL;
 	tdx->vp.tdvpr_pa = 0;

---

## [20] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

Extend "struct kvm_mmu_memory_cache" to support a custom page allocator
so that x86's TDX can update per-page metadata on allocation and free().

Name the allocator page_get() to align with __get_free_page(), e.g. to
communicate that it returns an "unsigned long", not a "struct page", and
to avoid collisions with macros, e.g. with alloc_page.

Suggested-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 include/linux/kvm_types.h | 2 ++
 virt/kvm/kvm_main.c       | 7 ++++++-
 2 files changed, 8 insertions(+), 1 deletion(-)

diff --git a/include/linux/kvm_types.h b/include/linux/kvm_types.h
index a568d8e6f4e8..87fa9deffdb7 100644
--- a/include/linux/kvm_types.h
+++ b/include/linux/kvm_types.h
@@ -112,6 +112,8 @@ struct kvm_mmu_memory_cache {
 	gfp_t gfp_custom;
 	u64 init_value;
 	struct kmem_cache *kmem_cache;
+	unsigned long (*page_get)(gfp_t gfp);
+	void (*page_free)(unsigned long addr);
 	int capacity;
 	int nobjs;
 	void **objects;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 571cf0d6ec01..7015edce5bd8 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -356,7 +356,10 @@ static inline void *mmu_memory_cache_alloc_obj(struct kvm_mmu_memory_cache *mc,
 	if (mc->kmem_cache)
 		return kmem_cache_alloc(mc->kmem_cache, gfp_flags);
 
-	page = (void *)__get_free_page(gfp_flags);
+	if (mc->page_get)
+		page = (void *)mc->page_get(gfp_flags);
+	else
+		page = (void *)__get_free_page(gfp_flags);
 	if (page && mc->init_value)
 		memset64(page, mc->init_value, PAGE_SIZE / sizeof(u64));
 	return page;
@@ -416,6 +419,8 @@ void kvm_mmu_free_memory_cache(struct kvm_mmu_memory_cache *mc)
 	while (mc->nobjs) {
 		if (mc->kmem_cache)
 			kmem_cache_free(mc->kmem_cache, mc->objects[--mc->nobjs]);
+		else if (mc->page_free)
+			mc->page_free((unsigned long)mc->objects[--mc->nobjs]);
 		else
 			free_page((unsigned long)mc->objects[--mc->nobjs]);
 	}

---

## [21] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages using tdx_{alloc,free}_control_page()*

Now that kvm_mmu_memory_cache supports custom page allocators, wire up the
S-EPT cache to use tdx_{alloc,free}_control_page() (arguably S-EPT pages
aren't "control" pages, but they're not guest pages either).  Using the
TDX APIs will make S-EPT pages naturally play nice with Dynamic PAMT, by
virtue of adding/removing PAMT entries when S-EPT pages are allocated and
freed, as opposed to when they are added/removed from the S-EPT tree.

Inserting into the PAMT entries on allocation does mean KVM will create
unnecessary PAMT entries, e.g. once a vCPU stops faulting in memory, the
remaining pages in the MMU cache will go unused.  But in practice, odds
are very good the containing 2MiB page will have other in-use S-EPT pages,
i.e. will create PAMT entries anyways.  And _if_ creating PAMT entries on
allocation is problematic for memory consumption, that can be resolved by
tweaking KVM's cache size.

Suggested-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  2 ++
 arch/x86/include/asm/kvm_host.h    | 18 +++++++++---------
 arch/x86/kvm/mmu/mmu.c             |  6 ++++--
 arch/x86/kvm/mmu/mmu_internal.h    | 11 -----------
 arch/x86/kvm/mmu/tdp_mmu.c         |  5 +++--
 arch/x86/kvm/vmx/tdx.c             | 13 ++++++++++++-
 6 files changed, 30 insertions(+), 25 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index c17cedc485c9..17dddada69fc 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -94,6 +94,8 @@ KVM_X86_OP_OPTIONAL_RET0(set_tss_addr)
 KVM_X86_OP_OPTIONAL_RET0(set_identity_map_addr)
 KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
+KVM_X86_OP_OPTIONAL(alloc_external_sp)
+KVM_X86_OP_OPTIONAL(free_external_sp)
 KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
 KVM_X86_OP_OPTIONAL(reclaim_external_sp)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index b35a07ed11fb..6e84dbc89e79 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -867,10 +867,7 @@ struct kvm_vcpu_arch {
 	struct kvm_mmu_memory_cache mmu_shadow_page_cache;
 	struct kvm_mmu_memory_cache mmu_shadowed_info_cache;
 	struct kvm_mmu_memory_cache mmu_page_header_cache;
-	/*
-	 * This cache is to allocate external page table. E.g. private EPT used
-	 * by the TDX module.
-	 */
+	/* Used to allocate S-EPT pages (gifted to the TDX-Module). */
 	struct kvm_mmu_memory_cache mmu_external_spt_cache;
 
 	/*
@@ -1853,18 +1850,21 @@ struct kvm_x86_ops {
 	void (*load_mmu_pgd)(struct kvm_vcpu *vcpu, hpa_t root_hpa,
 			     int root_level);
 
-	/* Update the external page table from spte getting set. */
+	/*
+	 * Callbacks to allocate and free external page tables, a.k.a. S-EPT,
+	 * and to propagate changes in mirror page tables to the external page
+	 * tables.
+	 */
+	unsigned long (*alloc_external_sp)(gfp_t gfp);
+	void (*free_external_sp)(unsigned long addr);
 	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				 u64 mirror_spte);
-
-	/* Update external page tables for page table about to be freed. */
 	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
 				    struct kvm_mmu_page *sp);
-
-	/* Update external page table from spte getting removed, and flush TLB. */
 	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				     u64 mirror_spte);
 
+
 	bool (*has_wbinvd_exit)(void);
 
 	u64 (*get_l2_tsc_offset)(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 3911ac9bddfd..9b5a6861e2a4 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -6690,11 +6690,13 @@ int kvm_mmu_create(struct kvm_vcpu *vcpu)
 	vcpu->arch.mmu_page_header_cache.kmem_cache = mmu_page_header_cache;
 	vcpu->arch.mmu_page_header_cache.gfp_zero = __GFP_ZERO;
 
-	vcpu->arch.mmu_shadow_page_cache.init_value =
-		SHADOW_NONPRESENT_VALUE;
+	vcpu->arch.mmu_shadow_page_cache.init_value = SHADOW_NONPRESENT_VALUE;
 	if (!vcpu->arch.mmu_shadow_page_cache.init_value)
 		vcpu->arch.mmu_shadow_page_cache.gfp_zero = __GFP_ZERO;
 
+	vcpu->arch.mmu_external_spt_cache.page_get = kvm_x86_ops.alloc_external_sp;
+	vcpu->arch.mmu_external_spt_cache.page_free = kvm_x86_ops.free_external_sp;
+
 	vcpu->arch.mmu = &vcpu->arch.root_mmu;
 	vcpu->arch.walk_mmu = &vcpu->arch.root_mmu;
 
diff --git a/arch/x86/kvm/mmu/mmu_internal.h b/arch/x86/kvm/mmu/mmu_internal.h
index 73cdcbccc89e..6bb97f660793 100644
--- a/arch/x86/kvm/mmu/mmu_internal.h
+++ b/arch/x86/kvm/mmu/mmu_internal.h
@@ -157,17 +157,6 @@ static inline bool is_mirror_sp(const struct kvm_mmu_page *sp)
 	return sp->role.is_mirror;
 }
 
-static inline void kvm_mmu_alloc_external_spt(struct kvm_vcpu *vcpu, struct kvm_mmu_page *sp)
-{
-	/*
-	 * external_spt is allocated for TDX module to hold private EPT mappings,
-	 * TDX module will initialize the page by itself.
-	 * Therefore, KVM does not need to initialize or access external_spt.
-	 * KVM only interacts with sp->spt for private EPT operations.
-	 */
-	sp->external_spt = kvm_mmu_memory_cache_alloc(&vcpu->arch.mmu_external_spt_cache);
-}
-
 static inline gfn_t kvm_gfn_root_bits(const struct kvm *kvm, const struct kvm_mmu_page *root)
 {
 	/*
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 18764dbc97ea..01e3e4f4baa5 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -55,7 +55,8 @@ void kvm_mmu_uninit_tdp_mmu(struct kvm *kvm)
 
 static void tdp_mmu_free_sp(struct kvm_mmu_page *sp)
 {
-	free_page((unsigned long)sp->external_spt);
+	if (sp->external_spt)
+		kvm_x86_call(free_external_sp)((unsigned long)sp->external_spt);
 	free_page((unsigned long)sp->spt);
 	kmem_cache_free(mmu_page_header_cache, sp);
 }
@@ -1246,7 +1247,7 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 		sp = tdp_mmu_alloc_sp(vcpu);
 		tdp_mmu_init_child_sp(sp, &iter);
 		if (is_mirror_sp(sp))
-			kvm_mmu_alloc_external_spt(vcpu, sp);
+			sp->external_spt = kvm_mmu_memory_cache_alloc(&vcpu->arch.mmu_external_spt_cache);
 
 		sp->nx_huge_page_disallowed = fault->huge_page_disallowed;
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 323aae4300a1..0946eba2de23 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1790,7 +1790,9 @@ static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
 	 * TD's hkid is freed, when the TD is being torn down.
 	 *
 	 * If the S-EPT PTE can't be removed for any reason, intentionally leak
-	 * the page to prevent the kernel from accessing the encrypted page.
+	 * the page to prevent the kernel from accessing the encrypted page,
+	 * and if Dynamic PAMT is enabled, to avoid inducing a failure on
+	 * removal of the still-used PAMT entry.
 	 */
 	if (KVM_BUG_ON(is_hkid_assigned(to_kvm_tdx(kvm)), kvm) ||
 	    tdx_reclaim_page(virt_to_page(sp->external_spt)))
@@ -3600,6 +3602,15 @@ void __init tdx_hardware_setup(void)
 	 */
 	vt_x86_ops.vm_size = max_t(unsigned int, vt_x86_ops.vm_size, sizeof(struct kvm_tdx));
 
+	/*
+	 * TDX uses the external_spt cache to allocate S-EPT page table pages,
+	 * which (a) don't need to be initialized by KVM as the TDX-Module will
+	 * initialize the page (using the guest's encryption key), and (b) need
+	 * to use a custom allocator to be compatible with Dynamic PAMT.
+	 */
+	vt_x86_ops.alloc_external_sp = tdx_alloc_control_page;
+	vt_x86_ops.free_external_sp = tdx_free_control_page;
+
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
 	vt_x86_ops.reclaim_external_sp = tdx_sept_reclaim_private_sp;
 	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;

---

## [22] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 21/45] x86/tdx: Add APIs to support get/put of DPAMT
 entries from KVM, under spinlock*

From: Rick Edgecombe <rick.p.edgecombe@intel.com>

Implement a PAMT "caching" scheme, similar to KVM's pre-allocated cache of
MMU assets, along with APIs to allow KVM to pre-allocate PAMT pages before
acquiring its mmu_lock spinlock, but wait until S-EPT entries are created
to actually update the Dynamic PAMT.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  | 17 ++++++++++
 arch/x86/virt/vmx/tdx/tdx.c | 65 +++++++++++++++++++++++++++++++++----
 2 files changed, 76 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index fa29be18498c..c39e2920d0c3 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -136,6 +136,23 @@ static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 	return false; /* To be enabled when kernel is ready */
 }
 
+/* Simple structure for pre-allocating Dynamic PAMT pages outside of locks. */
+struct tdx_pamt_cache {
+	struct list_head page_list;
+	int cnt;
+};
+
+static inline void tdx_init_pamt_cache(struct tdx_pamt_cache *cache)
+{
+	INIT_LIST_HEAD(&cache->page_list);
+	cache->cnt = 0;
+}
+
+void tdx_free_pamt_cache(struct tdx_pamt_cache *cache);
+int tdx_topup_pamt_cache(struct tdx_pamt_cache *cache, unsigned long npages);
+int tdx_pamt_get(struct page *page, struct tdx_pamt_cache *cache);
+void tdx_pamt_put(struct page *page);
+
 void tdx_quirk_reset_page(struct page *page);
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index d333d2790913..53b29c827520 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2064,13 +2064,34 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
 
-static int alloc_pamt_array(u64 *pa_array)
+static struct page *tdx_alloc_page_pamt_cache(struct tdx_pamt_cache *cache)
+{
+	struct page *page;
+
+	page = list_first_entry_or_null(&cache->page_list, struct page, lru);
+	if (page) {
+		list_del(&page->lru);
+		cache->cnt--;
+	}
+
+	return page;
+}
+
+static struct page *alloc_dpamt_page(struct tdx_pamt_cache *cache)
+{
+	if (cache)
+		return tdx_alloc_page_pamt_cache(cache);
+
+	return alloc_page(GFP_KERNEL_ACCOUNT);
+}
+
+static int alloc_pamt_array(u64 *pa_array, struct tdx_pamt_cache *cache)
 {
 	struct page *page;
 	int i;
 
 	for (i = 0; i < tdx_dpamt_entry_pages(); i++) {
-		page = alloc_page(GFP_KERNEL_ACCOUNT);
+		page = alloc_dpamt_page(cache);
 		if (!page)
 			goto err;
 		pa_array[i] = page_to_phys(page);
@@ -2151,7 +2172,7 @@ static u64 tdh_phymem_pamt_remove(struct page *page, u64 *pamt_pa_array)
 static DEFINE_SPINLOCK(pamt_lock);
 
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
-static int tdx_pamt_get(struct page *page)
+int tdx_pamt_get(struct page *page, struct tdx_pamt_cache *cache)
 {
 	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
 	atomic_t *pamt_refcount;
@@ -2170,7 +2191,7 @@ static int tdx_pamt_get(struct page *page)
 	if (atomic_inc_not_zero(pamt_refcount))
 		return 0;
 
-	ret = alloc_pamt_array(pamt_pa_array);
+	ret = alloc_pamt_array(pamt_pa_array, cache);
 	if (ret)
 		goto out_free;
 
@@ -2222,12 +2243,13 @@ static int tdx_pamt_get(struct page *page)
 	free_pamt_array(pamt_pa_array);
 	return ret;
 }
+EXPORT_SYMBOL_FOR_KVM(tdx_pamt_get);
 
 /*
  * Drop PAMT refcount for the given page and free PAMT memory if it is no
  * longer needed.
  */
-static void tdx_pamt_put(struct page *page)
+void tdx_pamt_put(struct page *page)
 {
 	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
 	atomic_t *pamt_refcount;
@@ -2281,6 +2303,37 @@ static void tdx_pamt_put(struct page *page)
 	 */
 	free_pamt_array(pamt_pa_array);
 }
+EXPORT_SYMBOL_FOR_KVM(tdx_pamt_put);
+
+void tdx_free_pamt_cache(struct tdx_pamt_cache *cache)
+{
+	struct page *page;
+
+	while ((page = tdx_alloc_page_pamt_cache(cache)))
+		__free_page(page);
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_free_pamt_cache);
+
+int tdx_topup_pamt_cache(struct tdx_pamt_cache *cache, unsigned long npages)
+{
+	if (WARN_ON_ONCE(!tdx_supports_dynamic_pamt(&tdx_sysinfo)))
+		return 0;
+
+	npages *= tdx_dpamt_entry_pages();
+
+	while (cache->cnt < npages) {
+		struct page *page = alloc_page(GFP_KERNEL_ACCOUNT);
+
+		if (!page)
+			return -ENOMEM;
+
+		list_add(&page->lru, &cache->page_list);
+		cache->cnt++;
+	}
+
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_topup_pamt_cache);
 
 /*
  * Return a page that can be gifted to the TDX-Module for use as a "control"
@@ -2296,7 +2349,7 @@ struct page *__tdx_alloc_control_page(gfp_t gfp)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page)) {
+	if (tdx_pamt_get(page, NULL)) {
 		__free_page(page);
 		return NULL;
 	}

---

## [23] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when (un)mapping
 private memory*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Add Dynamic PAMT support to KVM's S-EPT MMU by "getting" a PAMT page when
adding guest memory (PAGE.ADD or PAGE.AUG), and "putting" the page when
removing guest memory (PAGE.REMOVE).

To access the per-vCPU PAMT caches without plumbing @vcpu throughout the
TDP MMU, begrudginly use kvm_get_running_vcpu() to get the vCPU, and bug
the VM If KVM attempts to set an S-EPT without an active vCPU.  KVM only
supports creating _new_ mappings in page (pre)fault paths, all of which
require an active vCPU.

The PAMT memory holds metadata for TDX-protected memory. With Dynamic
PAMT, PAMT_4K is allocated on demand. The kernel supplies the TDX module
with a few pages that cover 2M of host physical memory.

PAMT memory can be reclaimed when the last user is gone. It can happen
in a few code paths:

- On TDH.PHYMEM.PAGE.RECLAIM in tdx_reclaim_td_control_pages() and
  tdx_reclaim_page().

- On TDH.MEM.PAGE.REMOVE in tdx_sept_drop_private_spte().

- In tdx_sept_zap_private_spte() for pages that were in the queue to be
  added with TDH.MEM.PAGE.ADD, but it never happened due to an error.

- In tdx_sept_free_private_spt() for SEPT pages;

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Minor log tweak]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  1 +
 arch/x86/include/asm/kvm_host.h    |  1 +
 arch/x86/kvm/mmu/mmu.c             |  4 +++
 arch/x86/kvm/vmx/tdx.c             | 44 ++++++++++++++++++++++++++----
 arch/x86/kvm/vmx/tdx.h             |  2 ++
 5 files changed, 47 insertions(+), 5 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 17dddada69fc..394dc29483a7 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -99,6 +99,7 @@ KVM_X86_OP_OPTIONAL(free_external_sp)
 KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
 KVM_X86_OP_OPTIONAL(reclaim_external_sp)
+KVM_X86_OP_OPTIONAL_RET0(topup_external_cache)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 6e84dbc89e79..a6e4ab76b1b2 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1863,6 +1863,7 @@ struct kvm_x86_ops {
 				    struct kvm_mmu_page *sp);
 	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				     u64 mirror_spte);
+	int (*topup_external_cache)(struct kvm_vcpu *vcpu, int min);
 
 
 	bool (*has_wbinvd_exit)(void);
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 9b5a6861e2a4..4ecbf216d96f 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -605,6 +605,10 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 					       PT64_ROOT_MAX_LEVEL);
 		if (r)
 			return r;
+
+		r = kvm_x86_call(topup_external_cache)(vcpu, PT64_ROOT_MAX_LEVEL);
+		if (r)
+			return r;
 	}
 	r = kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_shadow_page_cache,
 				       PT64_ROOT_MAX_LEVEL);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0946eba2de23..d74a2547e512 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -683,6 +683,8 @@ int tdx_vcpu_create(struct kvm_vcpu *vcpu)
 	if (!irqchip_split(vcpu->kvm))
 		return -EINVAL;
 
+	tdx_init_pamt_cache(&tdx->pamt_cache);
+
 	fpstate_set_confidential(&vcpu->arch.guest_fpu);
 	vcpu->arch.apic->guest_apic_protected = true;
 	INIT_LIST_HEAD(&tdx->vt.pi_wakeup_list);
@@ -868,6 +870,8 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	int i;
 
+	tdx_free_pamt_cache(&tdx->pamt_cache);
+
 	if (vcpu->cpu != -1) {
 		KVM_BUG_ON(tdx->state == VCPU_TD_STATE_INITIALIZED, vcpu->kvm);
 		tdx_flush_vp_on_cpu(vcpu);
@@ -1615,6 +1619,14 @@ void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int pgd_level)
 	td_vmcs_write64(to_tdx(vcpu), SHARED_EPT_POINTER, root_hpa);
 }
 
+static int tdx_topup_external_pamt_cache(struct kvm_vcpu *vcpu, int min)
+{
+	if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
+		return 0;
+
+	return tdx_topup_pamt_cache(&to_tdx(vcpu)->pamt_cache, min);
+}
+
 static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 			    kvm_pfn_t pfn)
 {
@@ -1696,8 +1708,15 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, u64 mirror_spte)
 {
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct page *page = pfn_to_page(pfn);
+	int ret;
+
+	if (KVM_BUG_ON(!vcpu, kvm))
+		return -EINVAL;
 
 	if (KVM_BUG_ON(!is_shadow_present_pte(mirror_spte), kvm))
 		return -EIO;
@@ -1711,6 +1730,10 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	WARN_ON_ONCE((mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
+	ret = tdx_pamt_get(page, &tdx->pamt_cache);
+	if (ret)
+		return ret;
+
 	/*
 	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()
 	 * before kvm_tdx->state.  Userspace must not be allowed to pre-fault
@@ -1723,14 +1746,17 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * If the TD isn't finalized/runnable, then userspace is initializing
 	 * the VM image via KVM_TDX_INIT_MEM_REGION; ADD the page to the TD.
 	 */
-	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
-		return tdx_mem_page_add(kvm, gfn, level, pfn);
+	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
+		ret = tdx_mem_page_aug(kvm, gfn, level, pfn);
+	else
+		ret = tdx_mem_page_add(kvm, gfn, level, pfn);
 
-	return tdx_mem_page_aug(kvm, gfn, level, pfn);
+	if (ret)
+		tdx_pamt_put(page);
+
+	return ret;
 }
 
-
-
 /*
  * Ensure shared and private EPTs to be flushed on all vCPUs.
  * tdh_mem_track() is the only caller that increases TD epoch. An increase in
@@ -1847,6 +1873,7 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 		return;
 
 	tdx_quirk_reset_page(page);
+	tdx_pamt_put(page);
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
@@ -3614,5 +3641,12 @@ void __init tdx_hardware_setup(void)
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
 	vt_x86_ops.reclaim_external_sp = tdx_sept_reclaim_private_sp;
 	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;
+
+	/*
+	 * FIXME: Wire up the PAMT hook iff DPAMT is supported, once VMXON is
+	 *        moved out of KVM and tdx_bringup() is folded into here.
+	 */
+	vt_x86_ops.topup_external_cache = tdx_topup_external_pamt_cache;
+
 	vt_x86_ops.protected_apic_has_interrupt = tdx_protected_apic_has_interrupt;
 }
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ce2720a028ad..f444fc84d93b 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -73,6 +73,8 @@ struct vcpu_tdx {
 
 	u64 map_gpa_next;
 	u64 map_gpa_end;
+
+	struct tdx_pamt_cache pamt_cache;
 };
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err);

---

## [24] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 23/45] x86/virt/tdx: Enable Dynamic PAMT*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

The Physical Address Metadata Table (PAMT) holds TDX metadata for
physical memory and must be allocated by the kernel during TDX module
initialization.

The exact size of the required PAMT memory is determined by the TDX
module and may vary between TDX module versions, but currently it is
approximately 0.4% of the system memory. This is a significant
commitment, especially if it is not known upfront whether the machine
will run any TDX guests.

The Dynamic PAMT feature reduces static PAMT allocations. PAMT_1G and
PAMT_2M levels are still allocated on TDX module initialization, but the
PAMT_4K level is allocated dynamically, reducing static allocations to
approximately 0.004% of the system memory.

All pieces are in place. Enable Dynamic PAMT if it is supported.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  | 6 +++++-
 arch/x86/virt/vmx/tdx/tdx.c | 8 ++++++++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 3 files changed, 13 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index c39e2920d0c3..56bdfbce4289 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -12,6 +12,10 @@
 #include <asm/trapnr.h>
 #include <asm/shared/tdx.h>
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD		BIT_ULL(18)
+#define TDX_FEATURES0_DYNAMIC_PAMT		BIT_ULL(36)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -133,7 +137,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT;
 }
 
 /* Simple structure for pre-allocating Dynamic PAMT pages outside of locks. */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 53b29c827520..90407493bb45 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1068,6 +1068,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
+#define TDX_SYS_CONFIG_DYNAMIC_PAMT	BIT(16)
+
 static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
@@ -1095,6 +1097,12 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
+
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		pr_info("Enable Dynamic PAMT\n");
+		args.r8 |= TDX_SYS_CONFIG_DYNAMIC_PAMT;
+	}
+
 	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
 
 	/* Free the array as it is not required anymore. */
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 46c4214b79fb..096c78a1d438 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -86,9 +86,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [25] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 24/45] Documentation/x86: Add documentation for TDX's
 Dynamic PAMT*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Expand TDX documentation to include information on the Dynamic PAMT
feature.

The new section explains PAMT support in the TDX module and how Dynamic
PAMT affects the kernel memory use.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 Documentation/arch/x86/tdx.rst | 21 +++++++++++++++++++++
 1 file changed, 21 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 61670e7df2f7..8d45d31fee29 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -99,6 +99,27 @@ initialize::
 
   [..] virt/tdx: module initialization failed ...
 
+Dynamic PAMT
+------------
+
+PAMT is memory that the TDX module needs to keep data about each page
+(think like struct page). It needs to handed to the TDX module for its
+exclusive use. For normal PAMT, this is installed when the TDX module
+is first loaded and comes to about 0.4% of system memory.
+
+Dynamic PAMT is a TDX feature that allows VMM to allocate part of the
+PAMT as needed (the parts for tracking 4KB size pages). The other page
+sizes (1GB and 2MB) are still allocated statically at the time of
+TDX module initialization. This reduces the amount of memory that TDX
+uses while TDs are not in use.
+
+When Dynamic PAMT is in use, dmesg shows it like:
+  [..] virt/tdx: Enable Dynamic PAMT
+  [..] virt/tdx: 10092 KB allocated for PAMT
+  [..] virt/tdx: module initialized
+
+Dynamic PAMT is enabled automatically if supported.
+
 TDX Interaction to Other Kernel Components
 ------------------------------------------

---

## [26] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 25/45] *** DO NOT MERGE *** x86/virt/tdx: Don't assume
 guest memory is backed by struct page*

Remove the completely unnecessary assumptions that memory mapped into a
TDX guest is backed by refcounted struct page memory.  TDH_MEM_PAGE_ADD
and TDH_MEM_PAGE_AUG are glorified writes to PTEs, they have no business
placing requirements on how KVM and guest_memfd manage memory.

Rip out the misguided struct page assumptions/constraints before hugepage
support is added for S-EPT, e.g. so the kernel doesn't pick up even worse
assumptions like "a hugepage must be contained in a single folio".

TODO (before merge): Replace "u64 pfn" with something type-safe.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  | 25 ++++++---------
 arch/x86/kvm/vmx/tdx.c      | 33 ++++++++++---------
 arch/x86/virt/vmx/tdx/tdx.c | 63 +++++++++++++++++++------------------
 3 files changed, 59 insertions(+), 62 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 56bdfbce4289..1f57f7721286 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -154,10 +154,10 @@ static inline void tdx_init_pamt_cache(struct tdx_pamt_cache *cache)
 
 void tdx_free_pamt_cache(struct tdx_pamt_cache *cache);
 int tdx_topup_pamt_cache(struct tdx_pamt_cache *cache, unsigned long npages);
-int tdx_pamt_get(struct page *page, struct tdx_pamt_cache *cache);
-void tdx_pamt_put(struct page *page);
+int tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache);
+void tdx_pamt_put(u64 pfn);
 
-void tdx_quirk_reset_page(struct page *page);
+void tdx_quirk_reset_page(u64 pfn);
 
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
@@ -206,23 +206,18 @@ struct tdx_vp {
 	struct page **tdcx_pages;
 };
 
-static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
+static inline u64 mk_keyed_paddr(u16 hkid, u64 pfn)
 {
-	u64 ret;
-
-	ret = page_to_phys(page);
-	/* KeyID bits are just above the physical address bits: */
-	ret |= (u64)hkid << boot_cpu_data.x86_phys_bits;
-
-	return ret;
+	/* KeyID bits are just above the physical address bits. */
+	return PFN_PHYS(pfn) | ((u64)hkid << boot_cpu_data.x86_phys_bits);
 }
 
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
-u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, u64 pfn, struct page *source, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, enum pg_level level, struct page *page, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page);
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level, struct page *page, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level, u64 pfn, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, enum pg_level level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mng_key_config(struct tdx_td *td);
 u64 tdh_mng_create(struct tdx_td *td, u16 hkid);
@@ -237,12 +232,12 @@ u64 tdh_mng_init(struct tdx_td *td, u64 td_params, u64 *extended_err);
 u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid);
 u64 tdh_vp_rd(struct tdx_vp *vp, u64 field, u64 *data);
 u64 tdh_vp_wr(struct tdx_vp *vp, u64 field, u64 data, u64 mask);
-u64 tdh_phymem_page_reclaim(struct page *page, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size);
+u64 tdh_phymem_page_reclaim(u64 pfn, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size);
 u64 tdh_mem_track(struct tdx_td *tdr);
 u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, enum pg_level level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, u64 pfn);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d74a2547e512..4ac312376ac9 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -318,11 +318,11 @@ static inline void tdx_disassociate_vp(struct kvm_vcpu *vcpu)
 })
 
 /* TDH.PHYMEM.PAGE.RECLAIM is allowed only when destroying the TD. */
-static int __tdx_reclaim_page(struct page *page)
+static int __tdx_reclaim_page(kvm_pfn_t pfn)
 {
 	u64 err, rcx, rdx, r8;
 
-	err = tdh_phymem_page_reclaim(page, &rcx, &rdx, &r8);
+	err = tdh_phymem_page_reclaim(pfn, &rcx, &rdx, &r8);
 
 	/*
 	 * No need to check for TDX_OPERAND_BUSY; all TD pages are freed
@@ -337,11 +337,12 @@ static int __tdx_reclaim_page(struct page *page)
 
 static int tdx_reclaim_page(struct page *page)
 {
+	kvm_pfn_t pfn = page_to_pfn(page);
 	int r;
 
-	r = __tdx_reclaim_page(page);
+	r = __tdx_reclaim_page(pfn);
 	if (!r)
-		tdx_quirk_reset_page(page);
+		tdx_quirk_reset_page(pfn);
 	return r;
 }
 
@@ -583,7 +584,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 	if (!kvm_tdx->td.tdr_page)
 		return;
 
-	if (__tdx_reclaim_page(kvm_tdx->td.tdr_page))
+	if (__tdx_reclaim_page(page_to_pfn(kvm_tdx->td.tdr_page)))
 		return;
 
 	/*
@@ -595,7 +596,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
-	tdx_quirk_reset_page(kvm_tdx->td.tdr_page);
+	tdx_quirk_reset_page(page_to_pfn(kvm_tdx->td.tdr_page));
 
 	__tdx_free_control_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
@@ -1640,8 +1641,8 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 	    KVM_BUG_ON(!kvm_tdx->page_add_src, kvm))
 		return -EIO;
 
-	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
-			       kvm_tdx->page_add_src, &entry, &level_state);
+	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn, kvm_tdx->page_add_src,
+			       &entry, &level_state);
 	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
@@ -1655,12 +1656,11 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 			    enum pg_level level, kvm_pfn_t pfn)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	struct page *page = pfn_to_page(pfn);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 entry, level_state;
 	u64 err;
 
-	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, level, page, &entry, &level_state);
+	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, level, pfn, &entry, &level_state);
 	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
@@ -1712,7 +1712,6 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
-	struct page *page = pfn_to_page(pfn);
 	int ret;
 
 	if (KVM_BUG_ON(!vcpu, kvm))
@@ -1730,7 +1729,7 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	WARN_ON_ONCE((mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
-	ret = tdx_pamt_get(page, &tdx->pamt_cache);
+	ret = tdx_pamt_get(pfn, &tdx->pamt_cache);
 	if (ret)
 		return ret;
 
@@ -1752,7 +1751,7 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 		ret = tdx_mem_page_add(kvm, gfn, level, pfn);
 
 	if (ret)
-		tdx_pamt_put(page);
+		tdx_pamt_put(pfn);
 
 	return ret;
 }
@@ -1828,8 +1827,8 @@ static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
 static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 					 enum pg_level level, u64 mirror_spte)
 {
-	struct page *page = pfn_to_page(spte_to_pfn(mirror_spte));
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 
@@ -1868,12 +1867,12 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
 		return;
 
-	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, page);
+	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn);
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
-	tdx_quirk_reset_page(page);
-	tdx_pamt_put(page);
+	tdx_quirk_reset_page(pfn);
+	tdx_pamt_put(pfn);
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 90407493bb45..85c31ed9b9d1 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -799,9 +799,9 @@ static void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
 	mb();
 }
 
-void tdx_quirk_reset_page(struct page *page)
+void tdx_quirk_reset_page(u64 pfn)
 {
-	tdx_quirk_reset_paddr(page_to_phys(page), PAGE_SIZE);
+	tdx_quirk_reset_paddr(PFN_PHYS(pfn), PAGE_SIZE);
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_quirk_reset_page);
 
@@ -1665,6 +1665,11 @@ static void tdx_clflush_page(struct page *page)
 	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
 }
 
+static void tdx_clflush_pfn(u64 pfn)
+{
+	clflush_cache_range(__va(PFN_PHYS(pfn)), PAGE_SIZE);
+}
+
 static int pg_level_to_tdx_sept_level(enum pg_level level)
 {
 	WARN_ON_ONCE(level == PG_LEVEL_NONE);
@@ -1691,17 +1696,17 @@ u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_mng_addcx);
 
-u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, u64 pfn, struct page *source, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
 		.rcx = gpa,
 		.rdx = tdx_tdr_pa(td),
-		.r8 = page_to_phys(page),
+		.r8 = PFN_PHYS(pfn),
 		.r9 = page_to_phys(source),
 	};
 	u64 ret;
 
-	tdx_clflush_page(page);
+	tdx_clflush_pfn(pfn);
 	ret = seamcall_ret(TDH_MEM_PAGE_ADD, &args);
 
 	*ext_err1 = args.rcx;
@@ -1743,17 +1748,17 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_addcx);
 
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level,
-		     struct page *page, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level, u64 pfn,
+		     u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
 		.rcx = gpa | pg_level_to_tdx_sept_level(level),
 		.rdx = tdx_tdr_pa(td),
-		.r8 = page_to_phys(page),
+		.r8 = PFN_PHYS(pfn),
 	};
 	u64 ret;
 
-	tdx_clflush_page(page);
+	tdx_clflush_pfn(pfn);
 	ret = seamcall_ret(TDH_MEM_PAGE_AUG, &args);
 
 	*ext_err1 = args.rcx;
@@ -1997,10 +2002,10 @@ EXPORT_SYMBOL_FOR_KVM(tdh_vp_init);
  * So despite the names, they must be interpted specially as described by the spec. Return
  * them only for error reporting purposes.
  */
-u64 tdh_phymem_page_reclaim(struct page *page, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size)
+u64 tdh_phymem_page_reclaim(u64 pfn, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size)
 {
 	struct tdx_module_args args = {
-		.rcx = page_to_phys(page),
+		.rcx = PFN_PHYS(pfn),
 	};
 	u64 ret;
 
@@ -2056,17 +2061,17 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td)
 {
 	struct tdx_module_args args = {};
 
-	args.rcx = mk_keyed_paddr(tdx_global_keyid, td->tdr_page);
+	args.rcx = mk_keyed_paddr(tdx_global_keyid, page_to_pfn(td->tdr_page));
 
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_tdr);
 
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, u64 pfn)
 {
 	struct tdx_module_args args = {};
 
-	args.rcx = mk_keyed_paddr(hkid, page);
+	args.rcx = mk_keyed_paddr(hkid, pfn);
 
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
@@ -2136,11 +2141,9 @@ static void free_pamt_array(u64 *pa_array)
  * Calculate the arg needed for operating on the DPAMT backing for
  * a given 4KB page.
  */
-static u64 pamt_2mb_arg(struct page *page)
+static u64 pamt_2mb_arg(u64 pfn)
 {
-	unsigned long hpa_2mb = ALIGN_DOWN(page_to_phys(page), PMD_SIZE);
-
-	return hpa_2mb | TDX_PS_2M;
+	return ALIGN_DOWN(PFN_PHYS(pfn), PMD_SIZE) | TDX_PS_2M;
 }
 
 /*
@@ -2149,10 +2152,10 @@ static u64 pamt_2mb_arg(struct page *page)
  * error. In the case of TDX module error, the return code is stored
  * in tdx_err.
  */
-static u64 tdh_phymem_pamt_add(struct page *page, u64 *pamt_pa_array)
+static u64 tdh_phymem_pamt_add(u64 pfn, u64 *pamt_pa_array)
 {
 	struct tdx_module_args args = {
-		.rcx = pamt_2mb_arg(page)
+		.rcx = pamt_2mb_arg(pfn)
 	};
 
 	dpamt_copy_to_regs(&args, rdx, pamt_pa_array);
@@ -2161,10 +2164,10 @@ static u64 tdh_phymem_pamt_add(struct page *page, u64 *pamt_pa_array)
 }
 
 /* Remove PAMT backing for the given page. */
-static u64 tdh_phymem_pamt_remove(struct page *page, u64 *pamt_pa_array)
+static u64 tdh_phymem_pamt_remove(u64 pfn, u64 *pamt_pa_array)
 {
 	struct tdx_module_args args = {
-		.rcx = pamt_2mb_arg(page),
+		.rcx = pamt_2mb_arg(pfn),
 	};
 	u64 ret;
 
@@ -2180,7 +2183,7 @@ static u64 tdh_phymem_pamt_remove(struct page *page, u64 *pamt_pa_array)
 static DEFINE_SPINLOCK(pamt_lock);
 
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
-int tdx_pamt_get(struct page *page, struct tdx_pamt_cache *cache)
+int tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache)
 {
 	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
 	atomic_t *pamt_refcount;
@@ -2190,7 +2193,7 @@ int tdx_pamt_get(struct page *page, struct tdx_pamt_cache *cache)
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
-	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+	pamt_refcount = tdx_find_pamt_refcount(pfn);
 
 	/*
 	 * If the pamt page is already added (i.e. refcount >= 1),
@@ -2214,7 +2217,7 @@ int tdx_pamt_get(struct page *page, struct tdx_pamt_cache *cache)
 		}
 
 		/* Try to add the pamt page and take the refcount 0->1. */
-		tdx_status = tdh_phymem_pamt_add(page, pamt_pa_array);
+		tdx_status = tdh_phymem_pamt_add(pfn, pamt_pa_array);
 		if (IS_TDX_SUCCESS(tdx_status)) {
 			/*
 			 * The refcount is zero, and this locked path is the only way to
@@ -2257,7 +2260,7 @@ EXPORT_SYMBOL_FOR_KVM(tdx_pamt_get);
  * Drop PAMT refcount for the given page and free PAMT memory if it is no
  * longer needed.
  */
-void tdx_pamt_put(struct page *page)
+void tdx_pamt_put(u64 pfn)
 {
 	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
 	atomic_t *pamt_refcount;
@@ -2266,7 +2269,7 @@ void tdx_pamt_put(struct page *page)
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return;
 
-	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+	pamt_refcount = tdx_find_pamt_refcount(pfn);
 
 	/*
 	 * If the there are more than 1 references on the pamt page,
@@ -2285,7 +2288,7 @@ void tdx_pamt_put(struct page *page)
 			return;
 
 		/* Try to remove the pamt page and take the refcount 1->0. */
-		tdx_status = tdh_phymem_pamt_remove(page, pamt_pa_array);
+		tdx_status = tdh_phymem_pamt_remove(pfn, pamt_pa_array);
 
 		/*
 		 * Don't free pamt_pa_array as it could hold garbage when
@@ -2357,7 +2360,7 @@ struct page *__tdx_alloc_control_page(gfp_t gfp)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page, NULL)) {
+	if (tdx_pamt_get(page_to_pfn(page), NULL)) {
 		__free_page(page);
 		return NULL;
 	}
@@ -2375,7 +2378,7 @@ void __tdx_free_control_page(struct page *page)
 	if (!page)
 		return;
 
-	tdx_pamt_put(page);
+	tdx_pamt_put(page_to_pfn(page));
 	__free_page(page);
 }
 EXPORT_SYMBOL_FOR_KVM(__tdx_free_control_page);

---

## [27] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 26/45] x86/virt/tdx: Enhance tdh_mem_page_aug() to
 support huge pages*

From: Yan Zhao <yan.y.zhao@intel.com>

Enhance the SEAMCALL wrapper tdh_mem_page_aug() to support huge pages.

The SEAMCALL TDH_MEM_PAGE_AUG currently supports adding physical memory to
the S-EPT up to 2MB in size.

While keeping the "level" parameter in the tdh_mem_page_aug() wrapper to
allow callers to specify the physical memory size, introduce the parameters
"folio" and "start_idx" to specify the physical memory starting from the
page at "start_idx" within the "folio". The specified physical memory must
be fully contained within a single folio.

Invoke tdx_clflush_page() for each 4KB segment of the physical memory being
added. tdx_clflush_page() performs CLFLUSH operations conservatively to
prevent dirty cache lines from writing back later and corrupting TD memory.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
[sean: remove the page+folio assumptions]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 85c31ed9b9d1..37776ea56eb7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1756,9 +1756,13 @@ u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level, u64 pfn,
 		.rdx = tdx_tdr_pa(td),
 		.r8 = PFN_PHYS(pfn),
 	};
+	unsigned long npages = page_level_size(level) / PAGE_SIZE;
+	unsigned long i;
 	u64 ret;
 
-	tdx_clflush_pfn(pfn);
+	for (i = 0; i < npages; i++)
+		tdx_clflush_pfn(pfn + i);
+
 	ret = seamcall_ret(TDH_MEM_PAGE_AUG, &args);
 
 	*ext_err1 = args.rcx;

---

## [28] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 27/45] x86/virt/tdx: Enhance tdh_phymem_page_wbinvd_hkid()
 to invalidate huge pages*

From: Yan Zhao <yan.y.zhao@intel.com>

After removing a TD's private page, the TDX module does not write back and
invalidate cache lines associated with the page and its keyID (i.e., the
TD's guest keyID). The SEAMCALL wrapper tdh_phymem_page_wbinvd_hkid()
enables the caller to provide the TD's guest keyID and physical memory
address to invoke the SEAMCALL TDH_PHYMEM_PAGE_WBINVD to perform cache line
invalidation.

Enhance the SEAMCALL wrapper tdh_phymem_page_wbinvd_hkid() to support cache
line invalidation for huge pages by introducing the parameters "folio",
"start_idx", and "npages". These parameters specify the physical memory
starting from the page at "start_idx" within a "folio" and spanning
"npages" contiguous PFNs. Return TDX_OPERAND_INVALID if the specified
memory is not entirely contained within a single folio.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Suggested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  |  2 +-
 arch/x86/kvm/vmx/tdx.c      |  2 +-
 arch/x86/virt/vmx/tdx/tdx.c | 16 ++++++++++++----
 3 files changed, 14 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 1f57f7721286..8ceaebc6c1a9 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -237,7 +237,7 @@ u64 tdh_mem_track(struct tdx_td *tdr);
 u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, enum pg_level level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, u64 pfn);
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, u64 pfn, enum pg_level level);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 4ac312376ac9..90133e8f5c53 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1867,7 +1867,7 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
 		return;
 
-	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn);
+	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn, level);
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 37776ea56eb7..367df9366d57 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2071,13 +2071,21 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_tdr);
 
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, u64 pfn)
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, u64 pfn, enum pg_level level)
 {
-	struct tdx_module_args args = {};
+	unsigned long npages = page_level_size(level) / PAGE_SIZE;
+	u64 err;
 
-	args.rcx = mk_keyed_paddr(hkid, pfn);
+	for (unsigned long i = 0; i < npages; i++) {
+		struct tdx_module_args args = {
+			.rcx = mk_keyed_paddr(hkid, pfn + i),
+		};
 
-	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
+		err = seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
+		if (err)
+			break;
+	}
+	return err;
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);

---

## [29] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 28/45] x86/virt/tdx: Extend "reset page" quirk to
 support huge pages*

Extend the APIs for "resetting" TDX pages to workaround the TDX_PW_MCE
erratum to support huge pages, e.g. so that KVM can pass in the pfn+level
without having to manually calculate the size in multiple locations.

No functional change intended (because KVM doesn't currently support
anything but level=PG_LEVEL_4K).

Suggested-by: Vishal Annapurve <vannapurve@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  | 7 ++++++-
 arch/x86/kvm/vmx/tdx.c      | 2 +-
 arch/x86/virt/vmx/tdx/tdx.c | 6 +++---
 3 files changed, 10 insertions(+), 5 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 8ceaebc6c1a9..e61b0b3cc403 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -157,7 +157,12 @@ int tdx_topup_pamt_cache(struct tdx_pamt_cache *cache, unsigned long npages);
 int tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache);
 void tdx_pamt_put(u64 pfn);
 
-void tdx_quirk_reset_page(u64 pfn);
+void __tdx_quirk_reset_page(u64 pfn, enum pg_level level);
+
+static inline void tdx_quirk_reset_page(u64 pfn)
+{
+	__tdx_quirk_reset_page(pfn, PG_LEVEL_4K);
+}
 
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 90133e8f5c53..aca556923822 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1871,7 +1871,7 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
-	tdx_quirk_reset_page(pfn);
+	__tdx_quirk_reset_page(pfn, level);
 	tdx_pamt_put(pfn);
 }
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 367df9366d57..411e5feef39f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -799,11 +799,11 @@ static void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
 	mb();
 }
 
-void tdx_quirk_reset_page(u64 pfn)
+void __tdx_quirk_reset_page(u64 pfn, enum pg_level level)
 {
-	tdx_quirk_reset_paddr(PFN_PHYS(pfn), PAGE_SIZE);
+	tdx_quirk_reset_paddr(PFN_PHYS(pfn), page_level_size(level));
 }
-EXPORT_SYMBOL_FOR_KVM(tdx_quirk_reset_page);
+EXPORT_SYMBOL_FOR_KVM(__tdx_quirk_reset_page);
 
 static void tdmr_quirk_reset_pamt(struct tdmr_info *tdmr)
 {

---

## [30] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 29/45] x86/virt/tdx: Get/Put DPAMT page pair if and
 only if mapping size is 4KB*

From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Elide the guts of getting/putting a Dynamic PAMT entry when the associated
mapping is greater than 4KiB, in which case static PAMT pages are used and
there's no need to (un)install extra PAMT pages.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Yan: Move level checking to callers of tdx_pamt_{get/put}()]
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
[sean: move level checking back to tdx_pamt_{get/put}()]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  | 16 ++++++++++++++--
 arch/x86/kvm/vmx/tdx.c      |  6 +++---
 arch/x86/virt/vmx/tdx/tdx.c | 12 ++++++------
 3 files changed, 23 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e61b0b3cc403..50feea01b066 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -154,8 +154,20 @@ static inline void tdx_init_pamt_cache(struct tdx_pamt_cache *cache)
 
 void tdx_free_pamt_cache(struct tdx_pamt_cache *cache);
 int tdx_topup_pamt_cache(struct tdx_pamt_cache *cache, unsigned long npages);
-int tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache);
-void tdx_pamt_put(u64 pfn);
+int __tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache);
+void __tdx_pamt_put(u64 pfn);
+
+static inline int tdx_pamt_get(u64 pfn, enum pg_level level,
+			       struct tdx_pamt_cache *cache)
+{
+	return level == PG_LEVEL_4K ? __tdx_pamt_get(pfn, cache) : 0;
+}
+
+static inline void tdx_pamt_put(u64 pfn, enum pg_level level)
+{
+	if (level == PG_LEVEL_4K)
+		__tdx_pamt_put(pfn);
+}
 
 void __tdx_quirk_reset_page(u64 pfn, enum pg_level level);
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index aca556923822..bd5d902da303 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1729,7 +1729,7 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	WARN_ON_ONCE((mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
-	ret = tdx_pamt_get(pfn, &tdx->pamt_cache);
+	ret = tdx_pamt_get(pfn, level, &tdx->pamt_cache);
 	if (ret)
 		return ret;
 
@@ -1751,7 +1751,7 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 		ret = tdx_mem_page_add(kvm, gfn, level, pfn);
 
 	if (ret)
-		tdx_pamt_put(pfn);
+		tdx_pamt_put(pfn, level);
 
 	return ret;
 }
@@ -1872,7 +1872,7 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 		return;
 
 	__tdx_quirk_reset_page(pfn, level);
-	tdx_pamt_put(pfn);
+	tdx_pamt_put(pfn, level);
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 411e5feef39f..cff325fdec79 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2195,7 +2195,7 @@ static u64 tdh_phymem_pamt_remove(u64 pfn, u64 *pamt_pa_array)
 static DEFINE_SPINLOCK(pamt_lock);
 
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
-int tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache)
+int __tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache)
 {
 	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
 	atomic_t *pamt_refcount;
@@ -2266,13 +2266,13 @@ int tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache)
 	free_pamt_array(pamt_pa_array);
 	return ret;
 }
-EXPORT_SYMBOL_FOR_KVM(tdx_pamt_get);
+EXPORT_SYMBOL_FOR_KVM(__tdx_pamt_get);
 
 /*
  * Drop PAMT refcount for the given page and free PAMT memory if it is no
  * longer needed.
  */
-void tdx_pamt_put(u64 pfn)
+void __tdx_pamt_put(u64 pfn)
 {
 	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
 	atomic_t *pamt_refcount;
@@ -2326,7 +2326,7 @@ void tdx_pamt_put(u64 pfn)
 	 */
 	free_pamt_array(pamt_pa_array);
 }
-EXPORT_SYMBOL_FOR_KVM(tdx_pamt_put);
+EXPORT_SYMBOL_FOR_KVM(__tdx_pamt_put);
 
 void tdx_free_pamt_cache(struct tdx_pamt_cache *cache)
 {
@@ -2372,7 +2372,7 @@ struct page *__tdx_alloc_control_page(gfp_t gfp)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page_to_pfn(page), NULL)) {
+	if (__tdx_pamt_get(page_to_pfn(page), NULL)) {
 		__free_page(page);
 		return NULL;
 	}
@@ -2390,7 +2390,7 @@ void __tdx_free_control_page(struct page *page)
 	if (!page)
 		return;
 
-	tdx_pamt_put(page_to_pfn(page));
+	__tdx_pamt_put(page_to_pfn(page));
 	__free_page(page);
 }
 EXPORT_SYMBOL_FOR_KVM(__tdx_free_control_page);

---

## [31] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 30/45] x86/virt/tdx: Add API to demote a 2MB mapping to
 512 4KB mappings*

From: Xiaoyao Li <xiaoyao.li@intel.com>

Introduce SEAMCALL wrapper tdh_mem_page_demote() to invoke
TDH_MEM_PAGE_DEMOTE, which splits a 2MB or a 1GB mapping in S-EPT into
512 4KB or 2MB mappings respectively.  TDH_MEM_PAGE_DEMOTE walks the
S-EPT to locate the huge entry/mapping to split, and replaces the huge
entry with a new S-EPT page table containing the equivalent 512 smaller
mappings.

Parameters "gpa" and "level" specify the huge mapping to split, and
parameter "new_sept_page" specifies the 4KB page to be added as the S-EPT
page. Invoke tdx_clflush_page() before adding the new S-EPT page
conservatively to prevent dirty cache lines from writing back later and
corrupting TD memory.

tdh_mem_page_demote() may fail, e.g., due to S-EPT walk error. Callers must
check function return value and can retrieve the extended error info from
the output parameters "ext_err1", and "ext_err2".

The TDX module has many internal locks. To avoid staying in SEAM mode for
too long, SEAMCALLs return a BUSY error code to the kernel instead of
spinning on the locks. Depending on the specific SEAMCALL, the caller may
need to handle this error in specific ways (e.g., retry). Therefore, return
the SEAMCALL error code directly to the caller without attempting to handle
it in the core kernel.

Enable tdh_mem_page_demote() only on TDX modules that support feature
TDX_FEATURES0.ENHANCE_DEMOTE_INTERRUPTIBILITY, which does not return error
TDX_INTERRUPTED_RESTARTABLE on basic TDX (i.e., without TD partition) [2].

This is because error TDX_INTERRUPTED_RESTARTABLE is difficult to handle.
The TDX module provides no guaranteed maximum retry count to ensure forward
progress of the demotion. Interrupt storms could then result in a DoS if
host simply retries endlessly for TDX_INTERRUPTED_RESTARTABLE. Disabling
interrupts before invoking the SEAMCALL also doesn't work because NMIs can
also trigger TDX_INTERRUPTED_RESTARTABLE. Therefore, the tradeoff for basic
TDX is to disable the TDX_INTERRUPTED_RESTARTABLE error given the
reasonable execution time for demotion. [1]

Allocate (or dequeue from the cache) PAMT pages when Dynamic PAMT is
enabled, as TDH.MEM.PAGE.DEMOTE takes a DPAMT page pair in R12 and R13, to
store physical memory metadata for the 2MB guest private memory (after a
successful split).  Take care to use seamcall_saved_ret() to handle
registers above R11.

Free the Dynamic PAMT pages after SEAMCALL TDH_MEM_PAGE_DEMOTE fails since
the guest private memory is still mapped at 2MB level.

Link: https://lore.kernel.org/kvm/99f5585d759328db973403be0713f68e492b492a.camel@intel.com [1]
Link: https://lore.kernel.org/all/fbf04b09f13bc2ce004ac97ee9c1f2c965f44fdf.camel@intel.com [2]
Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Isaku Yamahata <isaku.yamahata@intel.com>
Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Co-developed-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
[sean: squash all demote support into a single patch]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  |  9 +++++++
 arch/x86/virt/vmx/tdx/tdx.c | 54 +++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 3 files changed, 64 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 50feea01b066..483441de7fe0 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -15,6 +15,7 @@
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_NO_RBP_MOD		BIT_ULL(18)
 #define TDX_FEATURES0_DYNAMIC_PAMT		BIT_ULL(36)
+#define TDX_FEATURES0_ENHANCE_DEMOTE_INTERRUPTIBILITY	BIT_ULL(51)
 
 #ifndef __ASSEMBLER__
 
@@ -140,6 +141,11 @@ static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 	return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT;
 }
 
+static inline bool tdx_supports_demote_nointerrupt(const struct tdx_sys_info *sysinfo)
+{
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_ENHANCE_DEMOTE_INTERRUPTIBILITY;
+}
+
 /* Simple structure for pre-allocating Dynamic PAMT pages outside of locks. */
 struct tdx_pamt_cache {
 	struct list_head page_list;
@@ -240,6 +246,9 @@ u64 tdh_mng_key_config(struct tdx_td *td);
 u64 tdh_mng_create(struct tdx_td *td, u16 hkid);
 u64 tdh_vp_create(struct tdx_td *td, struct tdx_vp *vp);
 u64 tdh_mng_rd(struct tdx_td *td, u64 field, u64 *data);
+u64 tdh_mem_page_demote(struct tdx_td *td, u64 gpa, enum pg_level level, u64 pfn,
+			struct page *new_sp, struct tdx_pamt_cache *pamt_cache,
+			u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mr_extend(struct tdx_td *td, u64 gpa, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mr_finalize(struct tdx_td *td);
 u64 tdh_vp_flush(struct tdx_vp *vp);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index cff325fdec79..823ec092b4e4 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1841,6 +1841,9 @@ u64 tdh_mng_rd(struct tdx_td *td, u64 field, u64 *data)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_mng_rd);
 
+static int alloc_pamt_array(u64 *pa_array, struct tdx_pamt_cache *cache);
+static void free_pamt_array(u64 *pa_array);
+
 /* Number PAMT pages to be provided to TDX module per 2M region of PA */
 static int tdx_dpamt_entry_pages(void)
 {
@@ -1885,6 +1888,57 @@ static void dpamt_copy_regs_array(struct tdx_module_args *args, void *reg,
  */
 #define MAX_NR_DPAMT_ARGS (sizeof(struct tdx_module_args) / sizeof(u64))
 
+u64 tdh_mem_page_demote(struct tdx_td *td, u64 gpa, enum pg_level level, u64 pfn,
+			struct page *new_sp, struct tdx_pamt_cache *pamt_cache,
+			u64 *ext_err1, u64 *ext_err2)
+{
+	bool dpamt = tdx_supports_dynamic_pamt(&tdx_sysinfo) && level == PG_LEVEL_2M;
+	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
+	struct tdx_module_args args = {
+		.rcx = gpa | pg_level_to_tdx_sept_level(level),
+		.rdx = tdx_tdr_pa(td),
+		.r8 = page_to_phys(new_sp),
+	};
+	u64 ret;
+
+	if (!tdx_supports_demote_nointerrupt(&tdx_sysinfo))
+		return TDX_SW_ERROR;
+
+	if (dpamt) {
+		if (alloc_pamt_array(pamt_pa_array, pamt_cache))
+			return TDX_SW_ERROR;
+
+		dpamt_copy_to_regs(&args, r12, pamt_pa_array);
+	}
+
+	/* Flush the new S-EPT page to be added */
+	tdx_clflush_page(new_sp);
+
+	ret = seamcall_saved_ret(TDH_MEM_PAGE_DEMOTE, &args);
+
+	*ext_err1 = args.rcx;
+	*ext_err2 = args.rdx;
+
+	if (dpamt) {
+		if (ret) {
+			free_pamt_array(pamt_pa_array);
+		} else {
+			/*
+			 * Set the PAMT refcount for the guest private memory,
+			 * i.e. for the hugepage that was just demoted to 512
+			 * smaller pages.
+			 */
+			atomic_t *pamt_refcount;
+
+			pamt_refcount = tdx_find_pamt_refcount(pfn);
+			WARN_ON_ONCE(atomic_cmpxchg_release(pamt_refcount, 0,
+							    PTRS_PER_PMD));
+		}
+	}
+	return ret;
+}
+EXPORT_SYMBOL_FOR_KVM(tdh_mem_page_demote);
+
 u64 tdh_mr_extend(struct tdx_td *td, u64 gpa, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 096c78a1d438..a6c0fa53ece9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -24,6 +24,7 @@
 #define TDH_MNG_KEY_CONFIG		8
 #define TDH_MNG_CREATE			9
 #define TDH_MNG_RD			11
+#define TDH_MEM_PAGE_DEMOTE		15
 #define TDH_MR_EXTEND			16
 #define TDH_MR_FINALIZE			17
 #define TDH_VP_FLUSH			18

---

## [32] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 31/45] KVM: x86/mmu: Prevent hugepage promotion for
 mirror roots in fault path*

From: Rick Edgecombe <rick.p.edgecombe@intel.com>

Disallow hugepage promotion in the TDP MMU for mirror roots as KVM doesn't
currently support promoting S-EPT entries due to the complexity incurred
by the TDX-Module's rules for hugepage promotion.

 - The current TDX-Module requires all 4KB leafs to be either all PENDING
   or all ACCEPTED before a successful promotion to 2MB. This requirement
   prevents successful page merging after partially converting a 2MB
   range from private to shared and then back to private, which is the
   primary scenario necessitating page promotion.

 - The TDX-Module effectively requires a break-before-make sequence (to
   satisfy its TLB flushing rules), i.e. creates a window of time where a
   different vCPU can encounter faults on a SPTE that KVM is trying to
   promote to a hugepage.  To avoid unexpected BUSY errors, KVM would need
   to FREEZE the non-leaf SPTE before replacing it with a huge SPTE.

Disable hugepage promotion for all map() operations, as supporting page
promotion when building the initial image is still non-trivial, and the
vast majority of images are ~4MB or less, i.e. the benefit of creating
hugepages during TD build time is minimal.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Co-developed-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
[sean: check root, add comment, rewrite changelog]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/mmu.c     |  3 ++-
 arch/x86/kvm/mmu/tdp_mmu.c | 12 +++++++++++-
 2 files changed, 13 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 4ecbf216d96f..45650f70eeab 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -3419,7 +3419,8 @@ void disallowed_hugepage_adjust(struct kvm_page_fault *fault, u64 spte, int cur_
 	    cur_level == fault->goal_level &&
 	    is_shadow_present_pte(spte) &&
 	    !is_large_pte(spte) &&
-	    spte_to_child_sp(spte)->nx_huge_page_disallowed) {
+	    ((spte_to_child_sp(spte)->nx_huge_page_disallowed) ||
+	     is_mirror_sp(spte_to_child_sp(spte)))) {
 		/*
 		 * A small SPTE exists for this pfn, but FNAME(fetch),
 		 * direct_map(), or kvm_tdp_mmu_map() would like to create a
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 01e3e4f4baa5..f8ebdd0c6114 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1222,7 +1222,17 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 	for_each_tdp_pte(iter, kvm, root, fault->gfn, fault->gfn + 1) {
 		int r;
 
-		if (fault->nx_huge_page_workaround_enabled)
+		/*
+		 * Don't replace a page table (non-leaf) SPTE with a huge SPTE
+		 * (a.k.a. hugepage promotion) if the NX hugepage workaround is
+		 * enabled, as doing so will cause significant thrashing if one
+		 * or more leaf SPTEs needs to be executable.
+		 *
+		 * Disallow hugepage promotion for mirror roots as KVM doesn't
+		 * (yet) support promoting S-EPT entries while holding mmu_lock
+		 * for read (due to complexity induced by the TDX-Module APIs).
+		 */
+		if (fault->nx_huge_page_workaround_enabled || is_mirror_sp(root))
 			disallowed_hugepage_adjust(fault, iter.old_spte, iter.level);
 
 		/*

---

## [33] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 32/45] KVM: x86/mmu: Plumb the old_spte into kvm_x86_ops.set_external_spte()*

Plumb the old SPTE into .set_external_spte() so that the callback can be
used to handle removal and splitting of leaf SPTEs.  Rename mirror_spte to
new_spte to follow the TDP MMU's naming, and to make it more obvious what
value the parameter holds.

Opportunistically tweak the ordering of parameters to match the pattern of
most TDP MMU functions, which do "old, new, level".

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  4 ++--
 arch/x86/kvm/mmu/tdp_mmu.c      |  4 ++--
 arch/x86/kvm/vmx/tdx.c          | 14 +++++++-------
 3 files changed, 11 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index a6e4ab76b1b2..67deec8e205e 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1857,8 +1857,8 @@ struct kvm_x86_ops {
 	 */
 	unsigned long (*alloc_external_sp)(gfp_t gfp);
 	void (*free_external_sp)(unsigned long addr);
-	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				 u64 mirror_spte);
+	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, u64 old_spte,
+				 u64 new_spte, enum pg_level level);
 	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
 				    struct kvm_mmu_page *sp);
 	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index f8ebdd0c6114..271dd6f875a6 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -614,8 +614,8 @@ static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
 		 * the desired value.  On failure, restore the old SPTE so that
 		 * the SPTE isn't frozen in perpetuity.
 		 */
-		ret = kvm_x86_call(set_external_spte)(kvm, iter->gfn,
-						      iter->level, new_spte);
+		ret = kvm_x86_call(set_external_spte)(kvm, iter->gfn, iter->old_spte,
+						      new_spte, iter->level);
 		if (ret)
 			__kvm_tdp_mmu_write_spte(iter->sptep, iter->old_spte);
 		else
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index bd5d902da303..e451acdb0978 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1705,29 +1705,29 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
-static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, u64 mirror_spte)
+static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
+				     u64 new_spte, enum pg_level level)
 {
 	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
+	kvm_pfn_t pfn = spte_to_pfn(new_spte);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	int ret;
 
 	if (KVM_BUG_ON(!vcpu, kvm))
 		return -EINVAL;
 
-	if (KVM_BUG_ON(!is_shadow_present_pte(mirror_spte), kvm))
+	if (KVM_BUG_ON(!is_shadow_present_pte(new_spte), kvm))
 		return -EIO;
 
-	if (!is_last_spte(mirror_spte, level))
-		return tdx_sept_link_private_spt(kvm, gfn, level, mirror_spte);
+	if (!is_last_spte(new_spte, level))
+		return tdx_sept_link_private_spt(kvm, gfn, level, new_spte);
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return -EIO;
 
-	WARN_ON_ONCE((mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
+	WARN_ON_ONCE((new_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
 	ret = tdx_pamt_get(pfn, level, &tdx->pamt_cache);
 	if (ret)

---

## [34] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 33/45] KVM: TDX: Hoist tdx_sept_remove_private_spte()
 above set_private_spte()*

Move tdx_sept_remove_private_spte() (and its tdx_track() helper) above
tdx_sept_set_private_spte() in anticipation of routing all non-atomic
S-EPT writes (with the exception of reclaiming non-leaf pages) through
the "set" API.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 194 ++++++++++++++++++++---------------------
 1 file changed, 97 insertions(+), 97 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index e451acdb0978..0f3d27699a3d 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1670,6 +1670,52 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+/*
+ * Ensure shared and private EPTs to be flushed on all vCPUs.
+ * tdh_mem_track() is the only caller that increases TD epoch. An increase in
+ * the TD epoch (e.g., to value "N + 1") is successful only if no vCPUs are
+ * running in guest mode with the value "N - 1".
+ *
+ * A successful execution of tdh_mem_track() ensures that vCPUs can only run in
+ * guest mode with TD epoch value "N" if no TD exit occurs after the TD epoch
+ * being increased to "N + 1".
+ *
+ * Kicking off all vCPUs after that further results in no vCPUs can run in guest
+ * mode with TD epoch value "N", which unblocks the next tdh_mem_track() (e.g.
+ * to increase TD epoch to "N + 2").
+ *
+ * TDX module will flush EPT on the next TD enter and make vCPUs to run in
+ * guest mode with TD epoch value "N + 1".
+ *
+ * kvm_make_all_cpus_request() guarantees all vCPUs are out of guest mode by
+ * waiting empty IPI handler ack_kick().
+ *
+ * No action is required to the vCPUs being kicked off since the kicking off
+ * occurs certainly after TD epoch increment and before the next
+ * tdh_mem_track().
+ */
+static void tdx_track(struct kvm *kvm)
+{
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	u64 err;
+
+	/* If TD isn't finalized, it's before any vcpu running. */
+	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
+		return;
+
+	/*
+	 * The full sequence of TDH.MEM.TRACK and forcing vCPUs out of guest
+	 * mode must be serialized, as TDH.MEM.TRACK will fail if the previous
+	 * tracking epoch hasn't completed.
+	 */
+	lockdep_assert_held_write(&kvm->mmu_lock);
+
+	err = tdh_do_no_vcpus(tdh_mem_track, kvm, &kvm_tdx->td);
+	TDX_BUG_ON(err, TDH_MEM_TRACK, kvm);
+
+	kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);
+}
+
 static struct page *tdx_spte_to_external_spt(struct kvm *kvm, gfn_t gfn,
 					     u64 new_spte, enum pg_level level)
 {
@@ -1705,6 +1751,57 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
+					 enum pg_level level, u64 mirror_spte)
+{
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
+	gpa_t gpa = gfn_to_gpa(gfn);
+	u64 err, entry, level_state;
+
+	lockdep_assert_held_write(&kvm->mmu_lock);
+
+	/*
+	 * HKID is released after all private pages have been removed, and set
+	 * before any might be populated. Warn if zapping is attempted when
+	 * there can't be anything populated in the private EPT.
+	 */
+	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
+		return;
+
+	/* TODO: handle large pages. */
+	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
+		return;
+
+	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
+			      level, &entry, &level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
+		return;
+
+	/*
+	 * TDX requires TLB tracking before dropping private page.  Do
+	 * it here, although it is also done later.
+	 */
+	tdx_track(kvm);
+
+	/*
+	 * When zapping private page, write lock is held. So no race condition
+	 * with other vcpu sept operation.
+	 * Race with TDH.VP.ENTER due to (0-step mitigation) and Guest TDCALLs.
+	 */
+	err = tdh_do_no_vcpus(tdh_mem_page_remove, kvm, &kvm_tdx->td, gpa,
+			      level, &entry, &level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
+		return;
+
+	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn, level);
+	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
+		return;
+
+	__tdx_quirk_reset_page(pfn, level);
+	tdx_pamt_put(pfn, level);
+}
+
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				     u64 new_spte, enum pg_level level)
 {
@@ -1756,52 +1853,6 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 	return ret;
 }
 
-/*
- * Ensure shared and private EPTs to be flushed on all vCPUs.
- * tdh_mem_track() is the only caller that increases TD epoch. An increase in
- * the TD epoch (e.g., to value "N + 1") is successful only if no vCPUs are
- * running in guest mode with the value "N - 1".
- *
- * A successful execution of tdh_mem_track() ensures that vCPUs can only run in
- * guest mode with TD epoch value "N" if no TD exit occurs after the TD epoch
- * being increased to "N + 1".
- *
- * Kicking off all vCPUs after that further results in no vCPUs can run in guest
- * mode with TD epoch value "N", which unblocks the next tdh_mem_track() (e.g.
- * to increase TD epoch to "N + 2").
- *
- * TDX module will flush EPT on the next TD enter and make vCPUs to run in
- * guest mode with TD epoch value "N + 1".
- *
- * kvm_make_all_cpus_request() guarantees all vCPUs are out of guest mode by
- * waiting empty IPI handler ack_kick().
- *
- * No action is required to the vCPUs being kicked off since the kicking off
- * occurs certainly after TD epoch increment and before the next
- * tdh_mem_track().
- */
-static void tdx_track(struct kvm *kvm)
-{
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	u64 err;
-
-	/* If TD isn't finalized, it's before any vcpu running. */
-	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
-		return;
-
-	/*
-	 * The full sequence of TDH.MEM.TRACK and forcing vCPUs out of guest
-	 * mode must be serialized, as TDH.MEM.TRACK will fail if the previous
-	 * tracking epoch hasn't completed.
-	 */
-	lockdep_assert_held_write(&kvm->mmu_lock);
-
-	err = tdh_do_no_vcpus(tdh_mem_track, kvm, &kvm_tdx->td);
-	TDX_BUG_ON(err, TDH_MEM_TRACK, kvm);
-
-	kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);
-}
-
 static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
 					struct kvm_mmu_page *sp)
 {
@@ -1824,57 +1875,6 @@ static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
 		sp->external_spt = NULL;
 }
 
-static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
-					 enum pg_level level, u64 mirror_spte)
-{
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
-	gpa_t gpa = gfn_to_gpa(gfn);
-	u64 err, entry, level_state;
-
-	lockdep_assert_held_write(&kvm->mmu_lock);
-
-	/*
-	 * HKID is released after all private pages have been removed, and set
-	 * before any might be populated. Warn if zapping is attempted when
-	 * there can't be anything populated in the private EPT.
-	 */
-	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
-		return;
-
-	/* TODO: handle large pages. */
-	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return;
-
-	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
-			      level, &entry, &level_state);
-	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
-		return;
-
-	/*
-	 * TDX requires TLB tracking before dropping private page.  Do
-	 * it here, although it is also done later.
-	 */
-	tdx_track(kvm);
-
-	/*
-	 * When zapping private page, write lock is held. So no race condition
-	 * with other vcpu sept operation.
-	 * Race with TDH.VP.ENTER due to (0-step mitigation) and Guest TDCALLs.
-	 */
-	err = tdh_do_no_vcpus(tdh_mem_page_remove, kvm, &kvm_tdx->td, gpa,
-			      level, &entry, &level_state);
-	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
-		return;
-
-	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn, level);
-	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
-		return;
-
-	__tdx_quirk_reset_page(pfn, level);
-	tdx_pamt_put(pfn, level);
-}
-
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
 			   int trig_mode, int vector)
 {

---

## [35] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 34/45] KVM: TDX: Handle removal of leaf SPTEs in .set_private_spte()*

Drop kvm_x86_ops.remove_external_spte(), and instead handling the removal
of leaf SPTEs in the S-EPT (a.k.a. external root) in .set_private_spte().
This will allow extending tdx_sept_set_private_spte() to support splitting
a huge S-EPT entry without needing yet another kvm_x86_ops hook.

Bug the VM if the callback fails, as redundant KVM_BUG_ON() calls are
benign (the WARN will fire if and only if the VM isn't already bugged) and
handle_changed_spte() is most definitely not prepared to handle failure.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  1 -
 arch/x86/include/asm/kvm_host.h    |  2 --
 arch/x86/kvm/mmu/tdp_mmu.c         | 20 +++++++++++---------
 arch/x86/kvm/vmx/tdx.c             | 21 ++++++++++++---------
 4 files changed, 23 insertions(+), 21 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 394dc29483a7..3ca56fe6b951 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -97,7 +97,6 @@ KVM_X86_OP(load_mmu_pgd)
 KVM_X86_OP_OPTIONAL(alloc_external_sp)
 KVM_X86_OP_OPTIONAL(free_external_sp)
 KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
-KVM_X86_OP_OPTIONAL(remove_external_spte)
 KVM_X86_OP_OPTIONAL(reclaim_external_sp)
 KVM_X86_OP_OPTIONAL_RET0(topup_external_cache)
 KVM_X86_OP(has_wbinvd_exit)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 67deec8e205e..385f1cf32d70 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1861,8 +1861,6 @@ struct kvm_x86_ops {
 				 u64 new_spte, enum pg_level level);
 	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
 				    struct kvm_mmu_page *sp);
-	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				     u64 mirror_spte);
 	int (*topup_external_cache)(struct kvm_vcpu *vcpu, int min);
 
 
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 271dd6f875a6..d49aecba18d8 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -559,20 +559,22 @@ static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 	 * SPTE being converted to a hugepage (leaf) or being zapped.  Shadow
 	 * pages are kernel allocations and should never be migrated.
 	 *
-	 * When removing leaf entries from a mirror, immediately propagate the
-	 * changes to the external page tables.  Note, non-leaf mirror entries
-	 * are handled by handle_removed_pt(), as TDX requires that all leaf
-	 * entries are removed before the owning page table.  Note #2, writes
-	 * to make mirror PTEs shadow-present are propagated to external page
-	 * tables by __tdp_mmu_set_spte_atomic(), as KVM needs to ensure the
-	 * external page table was successfully updated before marking the
-	 * mirror SPTE present.
+	 * When modifying leaf entries in mirrored page tables, propagate the
+	 * changes to the external SPTE.  Bug the VM on failure, as callers
+	 * aren't prepared to handle errors, e.g. due to lock contention in the
+	 * TDX-Module.  Note, changes to non-leaf mirror SPTEs are handled by
+	 * handle_removed_pt() (the TDX-Module requires that child entries are
+	 * removed before the parent SPTE), and changes to non-present mirror
+	 * SPTEs are handled by __tdp_mmu_set_spte_atomic() (KVM needs to set
+	 * the external SPTE while the mirror SPTE is frozen so that installing
+	 * a new SPTE is effectively an atomic operation).
 	 */
 	if (was_present && !was_leaf &&
 	    (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed)))
 		handle_removed_pt(kvm, spte_to_child_pt(old_spte, level), shared);
 	else if (was_leaf && is_mirror_sptep(sptep) && !is_leaf)
-		kvm_x86_call(remove_external_spte)(kvm, gfn, level, old_spte);
+		KVM_BUG_ON(kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
+							   new_spte, level), kvm);
 }
 
 static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0f3d27699a3d..9f7789c5f0a7 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1751,11 +1751,11 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
-static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
-					 enum pg_level level, u64 mirror_spte)
+static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
+					enum pg_level level, u64 old_spte)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
+	kvm_pfn_t pfn = spte_to_pfn(old_spte);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 
@@ -1767,16 +1767,16 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * there can't be anything populated in the private EPT.
 	 */
 	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
-		return;
+		return -EIO;
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return;
+		return -EIO;
 
 	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
 			      level, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
-		return;
+		return -EIO;
 
 	/*
 	 * TDX requires TLB tracking before dropping private page.  Do
@@ -1792,14 +1792,15 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	err = tdh_do_no_vcpus(tdh_mem_page_remove, kvm, &kvm_tdx->td, gpa,
 			      level, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
-		return;
+		return -EIO;
 
 	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn, level);
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
-		return;
+		return -EIO;
 
 	__tdx_quirk_reset_page(pfn, level);
 	tdx_pamt_put(pfn, level);
+	return 0;
 }
 
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
@@ -1811,6 +1812,9 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	int ret;
 
+	if (is_shadow_present_pte(old_spte))
+		return tdx_sept_remove_private_spte(kvm, gfn, level, old_spte);
+
 	if (KVM_BUG_ON(!vcpu, kvm))
 		return -EINVAL;
 
@@ -3639,7 +3643,6 @@ void __init tdx_hardware_setup(void)
 
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
 	vt_x86_ops.reclaim_external_sp = tdx_sept_reclaim_private_sp;
-	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;
 
 	/*
 	 * FIXME: Wire up the PAMT hook iff DPAMT is supported, once VMXON is

---

## [36] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 35/45] KVM: TDX: Add helper to handle mapping leaf SPTE
 into S-EPT*

Add a helper, tdx_sept_map_leaf_spte(), to wrap and isolate PAGE.ADD and
PAGE.AUG operations, and thus complete tdx_sept_set_private_spte()'s
transition into a "dispatch" routine for setting/writing S-EPT entries.

Opportunistically tweak the prototypes for tdx_sept_remove_private_spte()
and tdx_sept_link_private_spt() to align with tdx_sept_set_private_spte()
and tdx_sept_map_leaf_spte().

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 97 ++++++++++++++++++++++--------------------
 1 file changed, 51 insertions(+), 46 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 9f7789c5f0a7..e6ac4aca8114 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1670,6 +1670,50 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+static int tdx_sept_map_leaf_spte(struct kvm *kvm, gfn_t gfn, u64 new_spte,
+				  enum pg_level level)
+{
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	kvm_pfn_t pfn = spte_to_pfn(new_spte);
+	int ret;
+
+	/* TODO: handle large pages. */
+	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
+		return -EIO;
+
+	if (KVM_BUG_ON(!vcpu, kvm))
+		return -EINVAL;
+
+	WARN_ON_ONCE((new_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
+
+	ret = tdx_pamt_get(pfn, level, &to_tdx(vcpu)->pamt_cache);
+	if (ret)
+		return ret;
+
+	/*
+	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()
+	 * before kvm_tdx->state.  Userspace must not be allowed to pre-fault
+	 * arbitrary memory until the initial memory image is finalized.  Pairs
+	 * with the smp_wmb() in tdx_td_finalize().
+	 */
+	smp_rmb();
+
+	/*
+	 * If the TD isn't finalized/runnable, then userspace is initializing
+	 * the VM image via KVM_TDX_INIT_MEM_REGION; ADD the page to the TD.
+	 */
+	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
+		ret = tdx_mem_page_aug(kvm, gfn, level, pfn);
+	else
+		ret = tdx_mem_page_add(kvm, gfn, level, pfn);
+
+	if (ret)
+		tdx_pamt_put(pfn, level);
+
+	return ret;
+}
+
 /*
  * Ensure shared and private EPTs to be flushed on all vCPUs.
  * tdh_mem_track() is the only caller that increases TD epoch. An increase in
@@ -1729,14 +1773,14 @@ static struct page *tdx_spte_to_external_spt(struct kvm *kvm, gfn_t gfn,
 	return virt_to_page(sp->external_spt);
 }
 
-static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, u64 mirror_spte)
+static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn, u64 new_spte,
+				     enum pg_level level)
 {
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 	struct page *external_spt;
 
-	external_spt = tdx_spte_to_external_spt(kvm, gfn, mirror_spte, level);
+	external_spt = tdx_spte_to_external_spt(kvm, gfn, new_spte, level);
 	if (!external_spt)
 		return -EIO;
 
@@ -1752,7 +1796,7 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 }
 
 static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
-					enum pg_level level, u64 old_spte)
+					u64 old_spte, enum pg_level level)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	kvm_pfn_t pfn = spte_to_pfn(old_spte);
@@ -1806,55 +1850,16 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				     u64 new_spte, enum pg_level level)
 {
-	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	kvm_pfn_t pfn = spte_to_pfn(new_spte);
-	struct vcpu_tdx *tdx = to_tdx(vcpu);
-	int ret;
-
 	if (is_shadow_present_pte(old_spte))
-		return tdx_sept_remove_private_spte(kvm, gfn, level, old_spte);
-
-	if (KVM_BUG_ON(!vcpu, kvm))
-		return -EINVAL;
+		return tdx_sept_remove_private_spte(kvm, gfn, old_spte, level);
 
 	if (KVM_BUG_ON(!is_shadow_present_pte(new_spte), kvm))
 		return -EIO;
 
 	if (!is_last_spte(new_spte, level))
-		return tdx_sept_link_private_spt(kvm, gfn, level, new_spte);
+		return tdx_sept_link_private_spt(kvm, gfn, new_spte, level);
 
-	/* TODO: handle large pages. */
-	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return -EIO;
-
-	WARN_ON_ONCE((new_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
-
-	ret = tdx_pamt_get(pfn, level, &tdx->pamt_cache);
-	if (ret)
-		return ret;
-
-	/*
-	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()
-	 * before kvm_tdx->state.  Userspace must not be allowed to pre-fault
-	 * arbitrary memory until the initial memory image is finalized.  Pairs
-	 * with the smp_wmb() in tdx_td_finalize().
-	 */
-	smp_rmb();
-
-	/*
-	 * If the TD isn't finalized/runnable, then userspace is initializing
-	 * the VM image via KVM_TDX_INIT_MEM_REGION; ADD the page to the TD.
-	 */
-	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
-		ret = tdx_mem_page_aug(kvm, gfn, level, pfn);
-	else
-		ret = tdx_mem_page_add(kvm, gfn, level, pfn);
-
-	if (ret)
-		tdx_pamt_put(pfn, level);
-
-	return ret;
+	return tdx_sept_map_leaf_spte(kvm, gfn, new_spte, level);
 }
 
 static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,

---

## [37] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 36/45] KVM: TDX: Move S-EPT page demotion TODO to tdx_sept_set_private_spte()*

Now that handle_changed_spte() can handles all mirror SPTE updates, move
the TDP MMU's assertion that it doesn't replace a shadow-present mirror
SPTE with another shadow-present SPTE into TDX, in the form of a TODO
that calls out that KVM needs to add support for splitting/demoting
hugepage.

Drop the "!is_leaf" condition so that an unexpected/unsupported update to
a shadow-present S-EPT triggers a KVM_BUG_ON(), versus being silently
ignored (well, silent until it causes explosions in the future).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 9 +--------
 arch/x86/kvm/vmx/tdx.c     | 5 ++++-
 2 files changed, 5 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index d49aecba18d8..3b0da898824a 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -572,7 +572,7 @@ static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 	if (was_present && !was_leaf &&
 	    (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed)))
 		handle_removed_pt(kvm, spte_to_child_pt(old_spte, level), shared);
-	else if (was_leaf && is_mirror_sptep(sptep) && !is_leaf)
+	else if (was_leaf && is_mirror_sptep(sptep))
 		KVM_BUG_ON(kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
 							   new_spte, level), kvm);
 }
@@ -704,13 +704,6 @@ static u64 tdp_mmu_set_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 
 	handle_changed_spte(kvm, as_id, sptep, gfn, old_spte, new_spte, level, false);
 
-	/*
-	 * Users that do non-atomic setting of PTEs don't operate on mirror
-	 * roots.  Bug the VM as this path doesn't propagate such writes to the
-	 * external page tables.
-	 */
-	KVM_BUG_ON(is_mirror_sptep(sptep) && is_shadow_present_pte(new_spte), kvm);
-
 	return old_spte;
 }
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index e6ac4aca8114..59b7ba36d3d9 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1850,7 +1850,10 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				     u64 new_spte, enum pg_level level)
 {
-	if (is_shadow_present_pte(old_spte))
+	/* TODO: Support replacing huge SPTE with non-leaf SPTE. (a.k.a. demotion). */
+	if (KVM_BUG_ON(is_shadow_present_pte(old_spte) && is_shadow_present_pte(new_spte), kvm))
+		return -EIO;
+	else if (is_shadow_present_pte(old_spte))
 		return tdx_sept_remove_private_spte(kvm, gfn, old_spte, level);
 
 	if (KVM_BUG_ON(!is_shadow_present_pte(new_spte), kvm))

---

## [38] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 37/45] KVM: x86/tdp_mmu: Alloc external_spt page for
 mirror page table splitting*

From: Isaku Yamahata <isaku.yamahata@intel.com>

Enhance tdp_mmu_alloc_sp_for_split() to allocate a page table page for the
external page table for splitting the mirror page table.

Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Co-developed-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
[sean: use kvm_x86_ops.alloc_external_sp()]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 13 +++++++++++--
 1 file changed, 11 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 3b0da898824a..4f5b80f0ca03 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1447,7 +1447,7 @@ bool kvm_tdp_mmu_wrprot_slot(struct kvm *kvm,
 	return spte_set;
 }
 
-static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(void)
+static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct tdp_iter *iter)
 {
 	struct kvm_mmu_page *sp;
 
@@ -1461,6 +1461,15 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(void)
 		return NULL;
 	}
 
+	if (is_mirror_sptep(iter->sptep)) {
+		sp->external_spt = (void *)kvm_x86_call(alloc_external_sp)(GFP_KERNEL_ACCOUNT);
+		if (!sp->external_spt) {
+			free_page((unsigned long)sp->spt);
+			kmem_cache_free(mmu_page_header_cache, sp);
+			return NULL;
+		}
+	}
+
 	return sp;
 }
 
@@ -1540,7 +1549,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
 			else
 				write_unlock(&kvm->mmu_lock);
 
-			sp = tdp_mmu_alloc_sp_for_split();
+			sp = tdp_mmu_alloc_sp_for_split(&iter);
 
 			if (shared)
 				read_lock(&kvm->mmu_lock);

---

## [39] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 38/45] KVM: x86/mmu: Add Dynamic PAMT support in TDP
 MMU for vCPU-induced page split*

Extend the TDP MMU to support vCPU-induced hugepage splits in mirror roots
when Dynamic PAMT is enabled.  I.e. top-up the PAMT cache when allocating
a new child page table, so that if the split is successful, there will be
a PAMT paging waiting to associated with the new less/non-huge mapping.

Note, the allocation is for the guest memory, not the S-EPT page, as PAMT
pages are accounted up front by .alloc_external_sp().

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 25 ++++++++++++++++---------
 arch/x86/kvm/vmx/tdx.c     |  3 +++
 2 files changed, 19 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 4f5b80f0ca03..e32034bfca5a 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1456,21 +1456,28 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct tdp_iter *iter)
 		return NULL;
 
 	sp->spt = (void *)get_zeroed_page(GFP_KERNEL_ACCOUNT);
-	if (!sp->spt) {
-		kmem_cache_free(mmu_page_header_cache, sp);
-		return NULL;
-	}
+	if (!sp->spt)
+		goto err_spt;
 
 	if (is_mirror_sptep(iter->sptep)) {
 		sp->external_spt = (void *)kvm_x86_call(alloc_external_sp)(GFP_KERNEL_ACCOUNT);
-		if (!sp->external_spt) {
-			free_page((unsigned long)sp->spt);
-			kmem_cache_free(mmu_page_header_cache, sp);
-			return NULL;
-		}
+		if (!sp->external_spt)
+			goto err_external_spt;
+
+		if (kvm_x86_call(topup_external_cache)(kvm_get_running_vcpu(), 1))
+			goto err_external_split;
 	}
 
 	return sp;
+
+err_external_split:
+	kvm_x86_call(free_external_sp)((unsigned long)sp->external_spt);
+err_external_spt:
+	free_page((unsigned long)sp->spt);
+err_spt:
+	kmem_cache_free(mmu_page_header_cache, sp);
+	return NULL;
+
 }
 
 /* Note, the caller is responsible for initializing @sp. */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 59b7ba36d3d9..e90610540a0b 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1625,6 +1625,9 @@ static int tdx_topup_external_pamt_cache(struct kvm_vcpu *vcpu, int min)
 	if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
 		return 0;
 
+	if (WARN_ON_ONCE(!vcpu))
+		return -EIO;
+
 	return tdx_topup_pamt_cache(&to_tdx(vcpu)->pamt_cache, min);
 }

---

## [40] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 39/45] KVM: TDX: Add core support for
 splitting/demoting 2MiB S-EPT to 4KiB*

From: Yan Zhao <yan.y.zhao@intel.com>

Add support for splitting, a.k.a. demoting, a 2MiB S-EPT hugepage to its
512 constituent 4KiB pages.  As per the TDX-Module rules, first invoke
MEM.RANGE.BLOCK to put the huge S-EPTE entry into a splittable state, then
do MEM.TRACK and kick all vCPUs outside of guest mode to flush TLBs, and
finally do MEM.PAGE.DEMOTE to demote/split the huge S-EPT entry.

Assert the mmu_lock is held for write, as the BLOCK => TRACK => DEMOTE
sequence needs to be "atomic" to guarantee success (and because mmu_lock
must be held for write to use tdh_do_no_vcpus()).

Note, even with kvm->mmu_lock held for write, tdh_mem_page_demote() may
contend with tdh_vp_enter() and potentially with the guest's S-EPT entry
operations.  Therefore, wrap the call with tdh_do_no_vcpus() to kick other
vCPUs out of the guest and prevent tdh_vp_enter() to ensure success.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
[sean: wire up via tdx_sept_link_private_spt(), massage changelog]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 51 +++++++++++++++++++++++++++++++++++++++---
 1 file changed, 48 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index e90610540a0b..af63364c8713 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1776,6 +1776,52 @@ static struct page *tdx_spte_to_external_spt(struct kvm *kvm, gfn_t gfn,
 	return virt_to_page(sp->external_spt);
 }
 
+/*
+ * Split a huge mapping into the target level.  Currently only supports 2MiB
+ * mappings (KVM doesn't yet support 1GiB mappings for TDX guests).
+ *
+ * Invoke "BLOCK + TRACK + kick off vCPUs (inside tdx_track())" since DEMOTE
+ * now does not support yet the NON-BLOCKING-RESIZE feature. No UNBLOCK is
+ * needed after a successful DEMOTE.
+ *
+ * Under write mmu_lock, kick off all vCPUs (inside tdh_do_no_vcpus()) to ensure
+ * DEMOTE will succeed on the second invocation if the first invocation returns
+ * BUSY.
+ */
+static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
+				       u64 new_spte, enum pg_level level)
+{
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	gpa_t gpa = gfn_to_gpa(gfn);
+	u64 err, entry, level_state;
+	struct page *external_spt;
+
+	lockdep_assert_held_write(&kvm->mmu_lock);
+
+	external_spt = tdx_spte_to_external_spt(kvm, gfn, new_spte, level);
+	if (!external_spt)
+		return -EIO;
+
+	if (KVM_BUG_ON(!vcpu || vcpu->kvm != kvm, kvm))
+		return -EIO;
+
+	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
+			      level, &entry, &level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
+		return -EIO;
+
+	tdx_track(kvm);
+
+	err = tdh_do_no_vcpus(tdh_mem_page_demote, kvm, &kvm_tdx->td, gpa,
+			      level, spte_to_pfn(old_spte), external_spt,
+			      &to_tdx(vcpu)->pamt_cache, &entry, &level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_DEMOTE, entry, level_state, kvm))
+		return -EIO;
+
+	return 0;
+}
+
 static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn, u64 new_spte,
 				     enum pg_level level)
 {
@@ -1853,9 +1899,8 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				     u64 new_spte, enum pg_level level)
 {
-	/* TODO: Support replacing huge SPTE with non-leaf SPTE. (a.k.a. demotion). */
-	if (KVM_BUG_ON(is_shadow_present_pte(old_spte) && is_shadow_present_pte(new_spte), kvm))
-		return -EIO;
+	if (is_shadow_present_pte(old_spte) && is_shadow_present_pte(new_spte))
+		return tdx_sept_split_private_spte(kvm, gfn, old_spte, new_spte, level);
 	else if (is_shadow_present_pte(old_spte))
 		return tdx_sept_remove_private_spte(kvm, gfn, old_spte, level);

---

## [41] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 40/45] KVM: x86: Introduce hugepage_set_guest_inhibit()*

From: Yan Zhao <yan.y.zhao@intel.com>

TDX requires guests to accept S-EPT mappings created by the host KVM. Due
to the current implementation of the TDX module, if a guest accepts a GFN
at a lower level after KVM maps it at a higher level, the TDX module will
emulate an EPT violation VMExit to KVM instead of returning a size mismatch
error to the guest. If KVM fails to perform page splitting in the VMExit
handler, the guest's accept operation will be triggered again upon
re-entering the guest, causing a repeated EPT violation VMExit.

To facilitate passing the guest's accept level information to the KVM MMU
core and to prevent the repeated mapping of a GFN at different levels due
to different accept levels specified by different vCPUs, introduce the
interface hugepage_set_guest_inhibit(). This interface specifies across
vCPUs that mapping at a certain level is inhibited from the guest.

Intentionally don't provide an API to clear KVM_LPAGE_GUEST_INHIBIT_FLAG
for the time being, as detecting that it's ok to (re)install a hugepage is
tricky (and costly if KVM wants to be 100% accurate), and KVM doesn't
currently support hugepage promotion (only direct installation of
hugepages) for S-EPT.

As a result, the only scenario where clearing the flag would likely allow
KVM to install a hugepage is when an entire 2MiB / 1GiB range is converted
to shared or private.  But if the guest is accepting at 4KiB granulairty,
odds are good the guest is using the memory for something "special" and
will never convert the entire range to shared (and/or back to private).
Punt that optimization to the future, if it's ever needed.

Link: https://lore.kernel.org/all/a6ffe23fb97e64109f512fa43e9f6405236ed40a.camel@intel.com [1]
Suggested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
[sean: explain *why* the flag is never cleared]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu.h     |  4 ++++
 arch/x86/kvm/mmu/mmu.c | 21 ++++++++++++++++++---
 2 files changed, 22 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/mmu.h b/arch/x86/kvm/mmu.h
index 830f46145692..fa6a8daf4b05 100644
--- a/arch/x86/kvm/mmu.h
+++ b/arch/x86/kvm/mmu.h
@@ -322,4 +322,8 @@ static inline bool kvm_is_gfn_alias(struct kvm *kvm, gfn_t gfn)
 {
 	return gfn & kvm_gfn_direct_bits(kvm);
 }
+
+void hugepage_set_guest_inhibit(struct kvm_memory_slot *slot, gfn_t gfn, int level);
+bool hugepage_test_guest_inhibit(struct kvm_memory_slot *slot, gfn_t gfn, int level);
+
 #endif
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 45650f70eeab..c2765bfc8492 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -718,12 +718,14 @@ static struct kvm_lpage_info *lpage_info_slot(gfn_t gfn,
 }
 
 /*
- * The most significant bit in disallow_lpage tracks whether or not memory
- * attributes are mixed, i.e. not identical for all gfns at the current level.
+ * The most 2 significant bits in disallow_lpage tracks whether or not memory
+ * attributes are mixed, i.e. not identical for all gfns at the current level,
+ * or whether or not guest inhibits the current level of hugepage at the gfn.
  * The lower order bits are used to refcount other cases where a hugepage is
  * disallowed, e.g. if KVM has shadow a page table at the gfn.
  */
 #define KVM_LPAGE_MIXED_FLAG	BIT(31)
+#define KVM_LPAGE_GUEST_INHIBIT_FLAG   BIT(30)
 
 static void update_gfn_disallow_lpage_count(const struct kvm_memory_slot *slot,
 					    gfn_t gfn, int count)
@@ -736,7 +738,8 @@ static void update_gfn_disallow_lpage_count(const struct kvm_memory_slot *slot,
 
 		old = linfo->disallow_lpage;
 		linfo->disallow_lpage += count;
-		WARN_ON_ONCE((old ^ linfo->disallow_lpage) & KVM_LPAGE_MIXED_FLAG);
+		WARN_ON_ONCE((old ^ linfo->disallow_lpage) &
+			     (KVM_LPAGE_MIXED_FLAG | KVM_LPAGE_GUEST_INHIBIT_FLAG));
 	}
 }
 
@@ -1648,6 +1651,18 @@ static bool __kvm_rmap_zap_gfn_range(struct kvm *kvm,
 				 start, end - 1, can_yield, true, flush);
 }
 
+bool hugepage_test_guest_inhibit(struct kvm_memory_slot *slot, gfn_t gfn, int level)
+{
+	return lpage_info_slot(gfn, slot, level)->disallow_lpage & KVM_LPAGE_GUEST_INHIBIT_FLAG;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(hugepage_test_guest_inhibit);
+
+void hugepage_set_guest_inhibit(struct kvm_memory_slot *slot, gfn_t gfn, int level)
+{
+	lpage_info_slot(gfn, slot, level)->disallow_lpage |= KVM_LPAGE_GUEST_INHIBIT_FLAG;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(hugepage_set_guest_inhibit);
+
 bool kvm_unmap_gfn_range(struct kvm *kvm, struct kvm_gfn_range *range)
 {
 	bool flush = false;

---

## [42] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 41/45] KVM: TDX: Honor the guest's accept level
 contained in an EPT violation*

From: Yan Zhao <yan.y.zhao@intel.com>

TDX requires guests to accept S-EPT mappings created by the host KVM. Due
to the current implementation of the TDX module, if a guest accepts a GFN
at a lower level after KVM maps it at a higher level, the TDX module will
synthesize an EPT Violation VM-Exit to KVM instead of returning a size
mismatch error to the guest. If KVM fails to perform page splitting in the
EPT Violation handler, the guest's ACCEPT operation will be triggered
again upon re-entering the guest, causing a repeated EPT Violation VM-Exit.

To ensure forward progress, honor the guest's accept level if an EPT
Violation VMExit contains guest accept level (the TDX-Module provides the
level when synthesizing a VM-Exit in response to a failed guest ACCEPT).

(1) Set the guest inhibit bit in the lpage info to prevent KVM's MMU
    from mapping at a higher level than the guest's accept level.

(2) Split any existing mapping higher than the guest's accept level.

For now, take mmu_lock for write across the entire operation to keep things
simple.  This can/will be revisited when the TDX-Module adds support for
NON-BLOCKING-RESIZE, at which point KVM can split the hugepage without
needing to handle UNBLOCK failure if the DEMOTE fails.

To avoid unnecessarily contending mmu_lock, check if the inhibit flag is
already set before acquiring mmu_lock, e.g. so that a vCPUs doing ACCEPT
on a region of memory aren't completely serialized.  Note, this relies on
(a) setting the inhibit after performing the split, and (b) never clearing
the flag, e.g. to avoid false positives and potentially triggering the
zero-step mitigation.

Note: EPT Violation VM-Exits without the guest's accept level are *never*
caused by the guest's ACCEPT operation, but are instead occur if the guest
accesses of memory before said memory is accepted.  Since KVM can't obtain
the guest accept level info from such EPT Violations (the ACCEPT operation
hasn't occurred yet), KVM may still map at a higher level than the later
guest's ACCEPT level.

So, the typical guest/KVM interaction flow is:
- If guest accesses private memory without first accepting it,
  (like non-Linux guests):
  1. Guest accesses a private memory.
  2. KVM finds it can map the GFN at 2MB. So, AUG at 2MB.
  3. Guest accepts the GFN at 4KB.
  4. KVM receives an EPT violation with eeq_type of ACCEPT + 4KB level.
  5. KVM splits the 2MB mapping.
  6. Guest accepts successfully and accesses the page.

- If guest first accepts private memory before accessing it,
  (like Linux guests):
  1. Guest accepts a private memory at 4KB.
  2. KVM receives an EPT violation with eeq_type of ACCEPT + 4KB level.
  3. KVM AUG at 4KB.
  4. Guest accepts successfully and accesses the page.

Link: https://lore.kernel.org/all/a6ffe23fb97e64109f512fa43e9f6405236ed40a.camel@intel.com
Suggested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c  | 11 ++++++
 arch/x86/kvm/mmu/tdp_mmu.h  |  2 +
 arch/x86/kvm/vmx/tdx.c      | 76 +++++++++++++++++++++++++++++++++++++
 arch/x86/kvm/vmx/tdx_arch.h |  3 ++
 4 files changed, 92 insertions(+)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index e32034bfca5a..0cdc6782e508 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1619,6 +1619,17 @@ void kvm_tdp_mmu_try_split_huge_pages(struct kvm *kvm,
 	}
 }
 
+/* Split huge pages for the current root. */
+int kvm_tdp_mmu_split_huge_pages(struct kvm_vcpu *vcpu, gfn_t start, gfn_t end,
+				 int target_level)
+{
+	struct kvm_mmu_page *root = root_to_sp(vcpu->arch.mmu->root.hpa);
+
+	return tdp_mmu_split_huge_pages_root(vcpu->kvm, root, start, end,
+					     target_level, false);
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_tdp_mmu_split_huge_pages);
+
 static bool tdp_mmu_need_write_protect(struct kvm *kvm, struct kvm_mmu_page *sp)
 {
 	/*
diff --git a/arch/x86/kvm/mmu/tdp_mmu.h b/arch/x86/kvm/mmu/tdp_mmu.h
index bd62977c9199..cdb0b4ecaa37 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.h
+++ b/arch/x86/kvm/mmu/tdp_mmu.h
@@ -97,6 +97,8 @@ void kvm_tdp_mmu_try_split_huge_pages(struct kvm *kvm,
 				      const struct kvm_memory_slot *slot,
 				      gfn_t start, gfn_t end,
 				      int target_level, bool shared);
+int kvm_tdp_mmu_split_huge_pages(struct kvm_vcpu *vcpu, gfn_t start, gfn_t end,
+				 int target_level);
 
 static inline void kvm_tdp_mmu_walk_lockless_begin(void)
 {
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index af63364c8713..098954f5e07c 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -13,6 +13,7 @@
 #include "tdx.h"
 #include "vmx.h"
 #include "mmu/spte.h"
+#include "mmu/tdp_mmu.h"
 #include "common.h"
 #include "posted_intr.h"
 #include "irq.h"
@@ -1958,6 +1959,77 @@ static inline bool tdx_is_sept_violation_unexpected_pending(struct kvm_vcpu *vcp
 	return !(eq & EPT_VIOLATION_PROT_MASK) && !(eq & EPT_VIOLATION_EXEC_FOR_RING3_LIN);
 }
 
+static bool tdx_is_mismatched_accepted(struct kvm_vcpu *vcpu)
+{
+	return (to_tdx(vcpu)->ext_exit_qualification & TDX_EXT_EXIT_QUAL_TYPE_MASK) ==
+	       TDX_EXT_EXIT_QUAL_TYPE_ACCEPT;
+}
+
+static int tdx_get_ept_violation_level(struct kvm_vcpu *vcpu)
+{
+	u64 ext_exit_qual = to_tdx(vcpu)->ext_exit_qualification;
+
+	return (((ext_exit_qual & TDX_EXT_EXIT_QUAL_INFO_MASK) >>
+		 TDX_EXT_EXIT_QUAL_INFO_SHIFT) & GENMASK(2, 0)) + 1;
+}
+
+/*
+ * An EPT violation can be either due to the guest's ACCEPT operation or
+ * due to the guest's access of memory before the guest accepts the
+ * memory.
+ *
+ * Type TDX_EXT_EXIT_QUAL_TYPE_ACCEPT in the extended exit qualification
+ * identifies the former case, which must also contain a valid guest
+ * accept level.
+ *
+ * For the former case, honor guest's accept level by setting guest inhibit bit
+ * on levels above the guest accept level and split the existing mapping for the
+ * faulting GFN if it's with a higher level than the guest accept level.
+ *
+ * Do nothing if the EPT violation is due to the latter case. KVM will map the
+ * GFN without considering the guest's accept level (unless the guest inhibit
+ * bit is already set).
+ */
+static int tdx_handle_mismatched_accept(struct kvm_vcpu *vcpu, gfn_t gfn)
+{
+	struct kvm_memory_slot *slot = kvm_vcpu_gfn_to_memslot(vcpu, gfn);
+	struct kvm *kvm = vcpu->kvm;
+	gfn_t start, end;
+	int level, r;
+
+	if (!slot || !tdx_is_mismatched_accepted(vcpu))
+		return 0;
+
+	if (WARN_ON_ONCE(!VALID_PAGE(vcpu->arch.mmu->root.hpa)))
+		return 0;
+
+	level = tdx_get_ept_violation_level(vcpu);
+	if (level > PG_LEVEL_2M)
+		return 0;
+
+	if (hugepage_test_guest_inhibit(slot, gfn, level + 1))
+		return 0;
+
+	guard(write_lock)(&kvm->mmu_lock);
+
+	start = gfn_round_for_level(gfn, level);
+	end = start + KVM_PAGES_PER_HPAGE(level);
+
+	r = kvm_tdp_mmu_split_huge_pages(vcpu, start, end, level);
+	if (r)
+		return r;
+
+	/*
+	 * No TLB flush is required, as the "BLOCK + TRACK + kick off vCPUs"
+	 * sequence required by the TDX-Module includes a TLB flush.
+	 */
+	hugepage_set_guest_inhibit(slot, gfn, level + 1);
+	if (level == PG_LEVEL_4K)
+		hugepage_set_guest_inhibit(slot, gfn, level + 2);
+
+	return 0;
+}
+
 static int tdx_handle_ept_violation(struct kvm_vcpu *vcpu)
 {
 	unsigned long exit_qual;
@@ -1983,6 +2055,10 @@ static int tdx_handle_ept_violation(struct kvm_vcpu *vcpu)
 		 */
 		exit_qual = EPT_VIOLATION_ACC_WRITE;
 
+		ret = tdx_handle_mismatched_accept(vcpu, gpa_to_gfn(gpa));
+		if (ret)
+			return ret;
+
 		/* Only private GPA triggers zero-step mitigation */
 		local_retry = true;
 	} else {
diff --git a/arch/x86/kvm/vmx/tdx_arch.h b/arch/x86/kvm/vmx/tdx_arch.h
index a30e880849e3..af006a73ee05 100644
--- a/arch/x86/kvm/vmx/tdx_arch.h
+++ b/arch/x86/kvm/vmx/tdx_arch.h
@@ -82,7 +82,10 @@ struct tdx_cpuid_value {
 #define TDX_TD_ATTR_PERFMON		BIT_ULL(63)
 
 #define TDX_EXT_EXIT_QUAL_TYPE_MASK	GENMASK(3, 0)
+#define TDX_EXT_EXIT_QUAL_TYPE_ACCEPT  1
 #define TDX_EXT_EXIT_QUAL_TYPE_PENDING_EPT_VIOLATION  6
+#define TDX_EXT_EXIT_QUAL_INFO_MASK	GENMASK(63, 32)
+#define TDX_EXT_EXIT_QUAL_INFO_SHIFT	32
 /*
  * TD_PARAMS is provided as an input to TDH_MNG_INIT, the size of which is 1024B.
  */

---

## [43] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 42/45] KVM: guest_memfd: Add helpers to get start/end
 gfns give gmem+slot+pgoff*

Add helpers for getting a gfn given a gmem slot+pgoff, and for getting a
gfn given a starting or ending pgoff, i.e. an offset that may be beyond
the range of the memslot binding.  Providing helpers will avoid duplicate
boilerplate code "if" future code also needs to iterate over gfn ranges.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 virt/kvm/guest_memfd.c | 21 +++++++++++++++++----
 1 file changed, 17 insertions(+), 4 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 923c51a3a525..51dbb309188f 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -59,6 +59,21 @@ static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
 	return gfn - slot->base_gfn + slot->gmem.pgoff;
 }
 
+static gfn_t kvm_gmem_get_gfn(struct kvm_memory_slot *slot, pgoff_t pgoff)
+{
+	return slot->base_gfn + pgoff - slot->gmem.pgoff;
+}
+
+static gfn_t kvm_gmem_get_start_gfn(struct kvm_memory_slot *slot, pgoff_t start)
+{
+	return kvm_gmem_get_gfn(slot, max(slot->gmem.pgoff, start));
+}
+
+static gfn_t kvm_gmem_get_end_gfn(struct kvm_memory_slot *slot, pgoff_t end)
+{
+	return kvm_gmem_get_gfn(slot, min(slot->gmem.pgoff + slot->npages, end));
+}
+
 static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 				    pgoff_t index, struct folio *folio)
 {
@@ -167,11 +182,9 @@ static void __kvm_gmem_invalidate_begin(struct gmem_file *f, pgoff_t start,
 	unsigned long index;
 
 	xa_for_each_range(&f->bindings, index, slot, start, end - 1) {
-		pgoff_t pgoff = slot->gmem.pgoff;
-
 		struct kvm_gfn_range gfn_range = {
-			.start = slot->base_gfn + max(pgoff, start) - pgoff,
-			.end = slot->base_gfn + min(pgoff + slot->npages, end) - pgoff,
+			.start = kvm_gmem_get_start_gfn(slot, start),
+			.end = kvm_gmem_get_end_gfn(slot, end),
 			.slot = slot,
 			.may_block = true,
 			.attr_filter = attr_filter,

---

## [44] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 43/45] *** DO NOT MERGE *** KVM: guest_memfd: Add
 pre-zap arch hook for shared<=>private conversion*

Add a gmem "pre-zap" hook to allow arch code to take action before a
shared<=>private conversion, and just as importantly, to let arch code
reject/fail a conversion, e.g. if the conversion requires new page tables
and KVM hits in OOM situation.

The new hook will be used by TDX to split hugepages as necessary to avoid
overzapping PTEs, which for all intents and purposes corrupts guest data
for TDX VMs (memory is wiped when private PTEs are removed).

TODO: Wire this up the convert path, not the PUNCH_HOLE path, once in-place
      conversion is supported.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/Kconfig       |  1 +
 arch/x86/kvm/mmu/tdp_mmu.c |  8 ++++++
 include/linux/kvm_host.h   |  5 ++++
 virt/kvm/Kconfig           |  4 +++
 virt/kvm/guest_memfd.c     | 50 ++++++++++++++++++++++++++++++++++++--
 5 files changed, 66 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/Kconfig b/arch/x86/kvm/Kconfig
index d916bd766c94..5f8d8daf4289 100644
--- a/arch/x86/kvm/Kconfig
+++ b/arch/x86/kvm/Kconfig
@@ -138,6 +138,7 @@ config KVM_INTEL_TDX
 	depends on INTEL_TDX_HOST
 	select KVM_GENERIC_MEMORY_ATTRIBUTES
 	select HAVE_KVM_ARCH_GMEM_POPULATE
+	select HAVE_KVM_ARCH_GMEM_CONVERT
 	help
 	  Provides support for launching Intel Trust Domain Extensions (TDX)
 	  confidential VMs on Intel processors.
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 0cdc6782e508..c46ebdacdb50 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1630,6 +1630,14 @@ int kvm_tdp_mmu_split_huge_pages(struct kvm_vcpu *vcpu, gfn_t start, gfn_t end,
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_tdp_mmu_split_huge_pages);
 
+#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CONVERT
+int kvm_arch_gmem_convert(struct kvm *kvm, gfn_t start, gfn_t end,
+			  bool to_private)
+{
+	return 0;
+}
+#endif /* CONFIG_HAVE_KVM_ARCH_GMEM_CONVERT */
+
 static bool tdp_mmu_need_write_protect(struct kvm *kvm, struct kvm_mmu_page *sp)
 {
 	/*
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 782f4d670793..c0bafff274b6 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2588,6 +2588,11 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages
 		       kvm_gmem_populate_cb post_populate, void *opaque);
 #endif
 
+#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CONVERT
+int kvm_arch_gmem_convert(struct kvm *kvm, gfn_t start, gfn_t end,
+			  bool to_private);
+#endif
+
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
 void kvm_arch_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 #endif
diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index 267c7369c765..05d69eaa50ae 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -125,3 +125,7 @@ config HAVE_KVM_ARCH_GMEM_INVALIDATE
 config HAVE_KVM_ARCH_GMEM_POPULATE
        bool
        depends on KVM_GUEST_MEMFD
+
+config HAVE_KVM_ARCH_GMEM_CONVERT
+       bool
+       depends on KVM_GUEST_MEMFD
\ No newline at end of file
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 51dbb309188f..b01f333a5e95 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -164,6 +164,46 @@ static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
 	return folio;
 }
 
+#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CONVERT
+static int __kvm_gmem_convert(struct gmem_file *f, pgoff_t start, pgoff_t end,
+			      bool to_private)
+{
+	struct kvm_memory_slot *slot;
+	unsigned long index;
+	int r;
+
+	xa_for_each_range(&f->bindings, index, slot, start, end - 1) {
+		r = kvm_arch_gmem_convert(f->kvm,
+					  kvm_gmem_get_start_gfn(slot, start),
+					  kvm_gmem_get_end_gfn(slot, end),
+					  to_private);
+		if (r)
+			return r;
+	}
+	return 0;
+}
+
+static int kvm_gmem_convert(struct inode *inode, pgoff_t start, pgoff_t end,
+			    bool to_private)
+{
+	struct gmem_file *f;
+	int r;
+
+	kvm_gmem_for_each_file(f, inode->i_mapping) {
+		r = __kvm_gmem_convert(f, start, end, to_private);
+		if (r)
+			return r;
+	}
+	return 0;
+}
+#else
+static int kvm_gmem_convert(struct inode *inode, pgoff_t start, pgoff_t end,
+			    bool to_private)
+{
+	return 0;
+}
+#endif
+
 static enum kvm_gfn_range_filter kvm_gmem_get_invalidate_filter(struct inode *inode)
 {
 	if (GMEM_I(inode)->flags & GUEST_MEMFD_FLAG_INIT_SHARED)
@@ -244,6 +284,7 @@ static long kvm_gmem_punch_hole(struct inode *inode, loff_t offset, loff_t len)
 {
 	pgoff_t start = offset >> PAGE_SHIFT;
 	pgoff_t end = (offset + len) >> PAGE_SHIFT;
+	int r;
 
 	/*
 	 * Bindings must be stable across invalidation to ensure the start+end
@@ -253,13 +294,18 @@ static long kvm_gmem_punch_hole(struct inode *inode, loff_t offset, loff_t len)
 
 	kvm_gmem_invalidate_begin(inode, start, end);
 
-	truncate_inode_pages_range(inode->i_mapping, offset, offset + len - 1);
+	/*
+	 * For demonstration purposes, pretend this is a private=>shared conversion.
+	 */
+	r = kvm_gmem_convert(inode, start, end, false);
+	if (!r)
+		truncate_inode_pages_range(inode->i_mapping, offset, offset + len - 1);
 
 	kvm_gmem_invalidate_end(inode, start, end);
 
 	filemap_invalidate_unlock(inode->i_mapping);
 
-	return 0;
+	return r;
 }
 
 static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)

---

## [45] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 44/45] KVM: x86/mmu: Add support for splitting S-EPT
 hugepages on conversion*

Add support for splitting S-EPT hugepages in preparation for converting a
subset of a hugepage to be shared, as KVM must precisely zap/remove S-EPT
entries to avoid clobbering guest memory (the lifetime of guest private
memory is tied to the S-EPT).  I.e. KVM needs to first split a hugepage so
that only the to-be-converted small pages can be zapped.

To avoid unnecessary work, e.g. if only the tail/end page of massive region
isn't aligned to the conversion, explicitly detect unaligned head and tail
pages relative to the max page size support by KVM, i.e. head/tail pages
that will undergo partial conversion.

To support splitting an S-EPT hugepage without a vCPU, add a per-VM PAMT
cache, along with a mutex to guard the cache.  Using a mutex, e.g. versus
a spinlock, is important at it allows KVM to allocate memory *without*
dropping the lock, i.e. so that the PAMT cache can be topped-up as needed
without needed to juggle arch.tdp_mmu_external_cache_lock.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  8 +++-
 arch/x86/kvm/mmu/mmu.c          |  2 +-
 arch/x86/kvm/mmu/tdp_mmu.c      | 72 +++++++++++++++++++++++++++++++--
 arch/x86/kvm/vmx/tdx.c          | 34 +++++++++++++---
 arch/x86/kvm/vmx/tdx.h          |  2 +
 5 files changed, 107 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 385f1cf32d70..54dea90a53dc 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1563,6 +1563,12 @@ struct kvm_arch {
 	 * the code to do so.
 	 */
 	spinlock_t tdp_mmu_pages_lock;
+
+	/*
+	 * Protect the per-VM cache of pre-allocate pages used to populate the
+	 * Dynamic PAMT when splitting S-EPT huge pages without a vCPU.
+	 */
+	struct mutex tdp_mmu_external_cache_lock;
 #endif /* CONFIG_X86_64 */
 
 	/*
@@ -1861,7 +1867,7 @@ struct kvm_x86_ops {
 				 u64 new_spte, enum pg_level level);
 	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
 				    struct kvm_mmu_page *sp);
-	int (*topup_external_cache)(struct kvm_vcpu *vcpu, int min);
+	int (*topup_external_cache)(struct kvm *kvm, struct kvm_vcpu *vcpu, int min);
 
 
 	bool (*has_wbinvd_exit)(void);
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index c2765bfc8492..62bf6bec2df2 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -606,7 +606,7 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 		if (r)
 			return r;
 
-		r = kvm_x86_call(topup_external_cache)(vcpu, PT64_ROOT_MAX_LEVEL);
+		r = kvm_x86_call(topup_external_cache)(vcpu->kvm, vcpu, PT64_ROOT_MAX_LEVEL);
 		if (r)
 			return r;
 	}
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index c46ebdacdb50..3181406c5e0b 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1447,7 +1447,8 @@ bool kvm_tdp_mmu_wrprot_slot(struct kvm *kvm,
 	return spte_set;
 }
 
-static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct tdp_iter *iter)
+static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
+						       struct tdp_iter *iter)
 {
 	struct kvm_mmu_page *sp;
 
@@ -1464,7 +1465,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct tdp_iter *iter)
 		if (!sp->external_spt)
 			goto err_external_spt;
 
-		if (kvm_x86_call(topup_external_cache)(kvm_get_running_vcpu(), 1))
+		if (kvm_x86_call(topup_external_cache)(kvm, kvm_get_running_vcpu(), 1))
 			goto err_external_split;
 	}
 
@@ -1556,7 +1557,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
 			else
 				write_unlock(&kvm->mmu_lock);
 
-			sp = tdp_mmu_alloc_sp_for_split(&iter);
+			sp = tdp_mmu_alloc_sp_for_split(kvm, &iter);
 
 			if (shared)
 				read_lock(&kvm->mmu_lock);
@@ -1631,9 +1632,74 @@ int kvm_tdp_mmu_split_huge_pages(struct kvm_vcpu *vcpu, gfn_t start, gfn_t end,
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_tdp_mmu_split_huge_pages);
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CONVERT
+static int __tdp_mmu_split_mirror_huge_pages(struct kvm *kvm,
+					     struct kvm_mmu_page *root,
+					     gfn_t gfn, int target_level)
+{
+	gfn_t end = gfn + KVM_PAGES_PER_HPAGE(target_level + 1);
+
+	return tdp_mmu_split_huge_pages_root(kvm, root, gfn, end, target_level, false);
+}
+
+static int tdp_mmu_split_mirror_huge_pages(struct kvm *kvm,
+					    struct kvm_mmu_page *root,
+					    gfn_t start, gfn_t end, int level)
+{
+
+	gfn_t head = gfn_round_for_level(start, level + 1);
+	gfn_t tail = gfn_round_for_level(end, level + 1);
+	int r;
+
+	if (head != start) {
+		r = __tdp_mmu_split_mirror_huge_pages(kvm, root, head, level);
+		if (r)
+			return r;
+	}
+
+	if (tail != end && (head != tail || head == start)) {
+		r = __tdp_mmu_split_mirror_huge_pages(kvm, root, tail, level);
+		if (r)
+			return r;
+	}
+
+	return 0;
+}
+
 int kvm_arch_gmem_convert(struct kvm *kvm, gfn_t start, gfn_t end,
 			  bool to_private)
 {
+	struct kvm_mmu_page *root;
+	int r;
+
+	/*
+	 * When converting from private=>shared, KVM must first split potential
+	 * hugepages, as KVM mustn't overzap private mappings for TDX guests,
+	 * i.e. must zap _exactly_ [start, end).  Split potential hugepages at
+	 * the head and tail of the to-be-converted (and thus zapped) range so
+	 * that KVM doesn't overzap due to dropping a hugepage that doesn't
+	 * fall wholly inside the range.
+	 */
+	if (to_private || !kvm_has_mirrored_tdp(kvm))
+		return 0;
+
+	/*
+	 * Acquire the external cache lock, a.k.a. the Dynamic PAMT lock, to
+	 * protect the per-VM cache of pre-allocate pages used to populate the
+	 * Dynamic PAMT when splitting S-EPT huge pages.
+	 */
+	guard(mutex)(&kvm->arch.tdp_mmu_external_cache_lock);
+
+	guard(write_lock)(&kvm->mmu_lock);
+
+	/*
+	 * TODO: Also split from PG_LEVEL_1G => PG_LEVEL_2M when KVM supports
+	 *       1GiB S-EPT pages.
+	 */
+	__for_each_tdp_mmu_root_yield_safe(kvm, root, 0, KVM_MIRROR_ROOTS) {
+		r = tdp_mmu_split_mirror_huge_pages(kvm, root, start, end, PG_LEVEL_4K);
+		if (r)
+			return r;
+	}
 	return 0;
 }
 #endif /* CONFIG_HAVE_KVM_ARCH_GMEM_CONVERT */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 098954f5e07c..774d395e5c73 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -607,6 +607,8 @@ void tdx_vm_destroy(struct kvm *kvm)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
+	tdx_free_pamt_cache(&kvm_tdx->pamt_cache);
+
 	tdx_reclaim_td_control_pages(kvm);
 
 	kvm_tdx->state = TD_STATE_UNINITIALIZED;
@@ -629,6 +631,8 @@ int tdx_vm_init(struct kvm *kvm)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
+	tdx_init_pamt_cache(&kvm_tdx->pamt_cache);
+
 	kvm->arch.has_protected_state = true;
 	/*
 	 * TDX Module doesn't allow the hypervisor to modify the EOI-bitmap,
@@ -1621,15 +1625,32 @@ void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int pgd_level)
 	td_vmcs_write64(to_tdx(vcpu), SHARED_EPT_POINTER, root_hpa);
 }
 
-static int tdx_topup_external_pamt_cache(struct kvm_vcpu *vcpu, int min)
+static struct tdx_pamt_cache *tdx_get_pamt_cache(struct kvm *kvm,
+						 struct kvm_vcpu *vcpu)
 {
+	if (KVM_BUG_ON(vcpu && vcpu->kvm != kvm, kvm))
+		return NULL;
+
+	if (vcpu)
+		return &to_tdx(vcpu)->pamt_cache;
+
+	lockdep_assert_held(&kvm->arch.tdp_mmu_external_cache_lock);
+	return &to_kvm_tdx(kvm)->pamt_cache;
+}
+
+static int tdx_topup_external_pamt_cache(struct kvm *kvm,
+					 struct kvm_vcpu *vcpu, int min)
+{
+	struct tdx_pamt_cache *pamt_cache;
+
 	if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
 		return 0;
 
-	if (WARN_ON_ONCE(!vcpu))
+	pamt_cache = tdx_get_pamt_cache(kvm, vcpu);
+	if (!pamt_cache)
 		return -EIO;
 
-	return tdx_topup_pamt_cache(&to_tdx(vcpu)->pamt_cache, min);
+	return tdx_topup_pamt_cache(pamt_cache, min);
 }
 
 static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
@@ -1792,8 +1813,8 @@ static struct page *tdx_spte_to_external_spt(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				       u64 new_spte, enum pg_level level)
 {
-	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct tdx_pamt_cache *pamt_cache;
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 	struct page *external_spt;
@@ -1804,7 +1825,8 @@ static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 	if (!external_spt)
 		return -EIO;
 
-	if (KVM_BUG_ON(!vcpu || vcpu->kvm != kvm, kvm))
+	pamt_cache = tdx_get_pamt_cache(kvm, kvm_get_running_vcpu());
+	if (!pamt_cache)
 		return -EIO;
 
 	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
@@ -1816,7 +1838,7 @@ static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 
 	err = tdh_do_no_vcpus(tdh_mem_page_demote, kvm, &kvm_tdx->td, gpa,
 			      level, spte_to_pfn(old_spte), external_spt,
-			      &to_tdx(vcpu)->pamt_cache, &entry, &level_state);
+			      pamt_cache, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_DEMOTE, entry, level_state, kvm))
 		return -EIO;
 
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index f444fc84d93b..57d7e70ffe7d 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -48,6 +48,8 @@ struct kvm_tdx {
 	 * Set/unset is protected with kvm->mmu_lock.
 	 */
 	bool wait_for_sept_zap;
+
+	struct tdx_pamt_cache pamt_cache;
 };
 
 /* TDX module vCPU states */

---

## [46] Sean Christopherson — 2026-01-28
*Subject: [RFC PATCH v5 45/45] KVM: TDX: Turn on PG_LEVEL_2M*

From: Yan Zhao <yan.y.zhao@intel.com>

Turn on PG_LEVEL_2M in tdx_gmem_private_max_mapping_level() when TDX huge
page is enabled and TD is RUNNABLE.

Introduce a module parameter named "tdx_huge_page" for kvm-intel.ko to
enable/disable TDX huge page. Turn TDX huge page off if the TDX module does
not support TDX_FEATURES0.ENHANCED_DEMOTE_INTERRUPTIBILITY.

Force page size to 4KB during TD build time to simplify code design, since
- tdh_mem_page_add() only adds private pages at 4KB.
- The amount of initial memory pages is usually limited (e.g. ~4MB in a
  typical linux TD).

Update the warnings and KVM_BUG_ON() info to match the conditions when 2MB
mappings are permitted.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 37 ++++++++++++++++++++++++++++++-------
 1 file changed, 30 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 774d395e5c73..8f9b4ad9871f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -55,6 +55,8 @@
 
 bool enable_tdx __ro_after_init;
 module_param_named(tdx, enable_tdx, bool, 0444);
+static bool __read_mostly enable_tdx_huge_page = true;
+module_param_named(tdx_huge_page, enable_tdx_huge_page, bool, 0444);
 
 #define TDX_SHARED_BIT_PWL_5 gpa_to_gfn(BIT_ULL(51))
 #define TDX_SHARED_BIT_PWL_4 gpa_to_gfn(BIT_ULL(47))
@@ -1703,8 +1705,9 @@ static int tdx_sept_map_leaf_spte(struct kvm *kvm, gfn_t gfn, u64 new_spte,
 	kvm_pfn_t pfn = spte_to_pfn(new_spte);
 	int ret;
 
-	/* TODO: handle large pages. */
-	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
+	/* TODO: Support hugepages when building the initial TD image. */
+	if (KVM_BUG_ON(level != PG_LEVEL_4K &&
+		       to_kvm_tdx(kvm)->state != TD_STATE_RUNNABLE, kvm))
 		return -EIO;
 
 	if (KVM_BUG_ON(!vcpu, kvm))
@@ -1885,10 +1888,6 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
 		return -EIO;
 
-	/* TODO: handle large pages. */
-	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return -EIO;
-
 	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
 			      level, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
@@ -3474,12 +3473,34 @@ int tdx_vcpu_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 	return ret;
 }
 
+/*
+ * For private pages:
+ *
+ * Force KVM to map at 4KB level when !enable_tdx_huge_page (e.g., due to
+ * incompatible TDX module) or before TD state is RUNNABLE.
+ *
+ * Always allow KVM to map at 2MB level in other cases, though KVM may still map
+ * the page at 4KB (i.e., passing in PG_LEVEL_4K to AUG) due to
+ * (1) the backend folio is 4KB,
+ * (2) disallow_lpage restrictions:
+ *     - mixed private/shared pages in the 2MB range
+ *     - level misalignment due to slot base_gfn, slot size, and ugfn
+ *     - guest_inhibit bit set due to guest's 4KB accept level
+ * (3) page merging is disallowed (e.g., when part of a 2MB range has been
+ *     mapped at 4KB level during TD build time).
+ */
 int tdx_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 {
 	if (!is_private)
 		return 0;
 
-	return PG_LEVEL_4K;
+	if (!enable_tdx_huge_page)
+		return PG_LEVEL_4K;
+
+	if (unlikely(to_kvm_tdx(kvm)->state != TD_STATE_RUNNABLE))
+		return PG_LEVEL_4K;
+
+	return PG_LEVEL_2M;
 }
 
 static int tdx_online_cpu(unsigned int cpu)
@@ -3665,6 +3686,8 @@ static int __init __tdx_bringup(void)
 	if (misc_cg_set_capacity(MISC_CG_RES_TDX, tdx_get_nr_guest_keyids()))
 		goto get_sysinfo_err;
 
+	if (enable_tdx_huge_page && !tdx_supports_demote_nointerrupt(tdx_sysinfo))
+		enable_tdx_huge_page = false;
 	/*
 	 * Leave hardware virtualization enabled after TDX is enabled
 	 * successfully.  TDX CPU hotplug depends on this.

---

## [47] Sean Christopherson — 2026-01-29
*Subject: Re: [RFC PATCH v5 41/45] KVM: TDX: Honor the guest's accept level
 contained in an EPT violation*

On Wed, Jan 28, 2026, Sean Christopherson wrote:
> +int kvm_tdp_mmu_split_huge_pages(struct kvm_vcpu *vcpu, gfn_t start, gfn_t end,
> +				 int target_level)

This is wrong, mmu->root.hpa is the shared root, not the mirror root.  Dittof for
the sanity check in tdx_handle_mismatched_accept().

Rather than operate on the vCPU's root, I think it makes sense to add an API to
operate on all mirror roots.  In practice, there can only be one valid mirror
root, so KVM isn't actually doing more work.  Then TDX can reuse that API for
splitting the head+tail pages when preparing for a partial shared=>private
conversion.

Slotted in before this patch:

---
From: Sean Christopherson <seanjc@google.com>
Date: Thu, 29 Jan 2026 15:21:30 +0000
Subject: [PATCH] KVM: x86/mmu: Add a TDP MMU API to split hugepages for mirror
 roots

Add an exported API to split hugepages in mirror roots for a given gfn
range.  TDX will use the API to split hugepages in preparation for
partially converting a hugepage from private to shared, and for splitting
a hugepage to match the guest's ACCEPT level.

For all intents and purposes, no functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 39 ++++++++++++++++++++++++++++----------
 arch/x86/kvm/mmu/tdp_mmu.h |  2 ++
 2 files changed, 31 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index e32034bfca5a..a45d8ee91481 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1597,6 +1597,26 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
 	return 0;
 }
 
+static int tdp_mmu_split_huge_pages(struct kvm *kvm, int as_id,
+				    enum kvm_tdp_mmu_root_types type,
+				    gfn_t start, gfn_t end,
+				    int target_level, bool shared)
+{
+	struct kvm_mmu_page *root;
+	int r;
+
+	kvm_lockdep_assert_mmu_lock_held(kvm, shared);
+
+	__for_each_tdp_mmu_root_yield_safe(kvm, root, as_id, type) {
+		r = tdp_mmu_split_huge_pages_root(kvm, root, start, end,
+						  target_level, shared);
+		if (r) {
+			kvm_tdp_mmu_put_root(kvm, root);
+			return r;
+		}
+	}
+	return 0;
+}
 
 /*
  * Try to split all huge pages mapped by the TDP MMU down to the target level.
@@ -1606,18 +1626,17 @@ void kvm_tdp_mmu_try_split_huge_pages(struct kvm *kvm,
 				      gfn_t start, gfn_t end,
 				      int target_level, bool shared)
 {
-	struct kvm_mmu_page *root;
-	int r = 0;
+	tdp_mmu_split_huge_pages(kvm, slot->as_id, KVM_VALID_ROOTS, start, end,
+				 target_level, shared);
+}
 
-	kvm_lockdep_assert_mmu_lock_held(kvm, shared);
-	for_each_valid_tdp_mmu_root_yield_safe(kvm, root, slot->as_id) {
-		r = tdp_mmu_split_huge_pages_root(kvm, root, start, end, target_level, shared);
-		if (r) {
-			kvm_tdp_mmu_put_root(kvm, root);
-			break;
-		}
-	}
+int kvm_tdp_mmu_mirrors_split_huge_pages(struct kvm *kvm, gfn_t start,
+					 gfn_t end, int target_level)
+{
+	return tdp_mmu_split_huge_pages(kvm, 0, KVM_MIRROR_ROOTS, start, end,
+					target_level, false);
 }
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_tdp_mmu_mirrors_split_huge_pages);
 
 static bool tdp_mmu_need_write_protect(struct kvm *kvm, struct kvm_mmu_page *sp)
 {
diff --git a/arch/x86/kvm/mmu/tdp_mmu.h b/arch/x86/kvm/mmu/tdp_mmu.h
index bd62977c9199..a6919de10ca2 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.h
+++ b/arch/x86/kvm/mmu/tdp_mmu.h
@@ -97,6 +97,8 @@ void kvm_tdp_mmu_try_split_huge_pages(struct kvm *kvm,
 				      const struct kvm_memory_slot *slot,
 				      gfn_t start, gfn_t end,
 				      int target_level, bool shared);
+int kvm_tdp_mmu_mirrors_split_huge_pages(struct kvm *kvm, gfn_t start,
+					 gfn_t end, int target_level);
 
 static inline void kvm_tdp_mmu_walk_lockless_begin(void)
 {

base-commit: 86c3bb72bf5c6201636529ee4609334b0887c6e3
--

---

## [48] Sean Christopherson — 2026-01-29
*Subject: Re: [RFC PATCH v5 44/45] KVM: x86/mmu: Add support for splitting
 S-EPT hugepages on conversion*

On Wed, Jan 28, 2026, Sean Christopherson wrote:
>  #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CONVERT
> +static int __tdp_mmu_split_mirror_huge_pages(struct kvm *kvm,

This needs to call kvm_tdp_mmu_put_root() on failure.  But if we instead add
kvm_tdp_mmu_mirrors_split_huge_pages() for use in handling mismatched ACCEPT,
this code goes away.

And then the bulk of this code can live in tdx.c instead of tdp_mmu.c, and the
pamt mutex can live in kvm_tdx instead of kvm_arch.

Compile tested only...

---
From: Sean Christopherson <seanjc@google.com>
Date: Thu, 22 Jan 2026 07:36:47 -0800
Subject: [PATCH] KVM: x86/mmu: Add support for splitting S-EPT hugepages on
 conversion

Add support for splitting S-EPT hugepages in preparation for converting a
subset of a hugepage to be shared, as KVM must precisely zap/remove S-EPT
entries to avoid clobbering guest memory (the lifetime of guest private
memory is tied to the S-EPT).  I.e. KVM needs to first split a hugepage so
that only the to-be-converted small pages can be zapped.

To avoid unnecessary work, e.g. if only the tail/end page of massive region
isn't aligned to the conversion, explicitly detect unaligned head and tail
pages relative to the max page size support by KVM, i.e. head/tail pages
that will undergo partial conversion.

To support splitting an S-EPT hugepage without a vCPU, add a per-VM PAMT
cache, along with a mutex to guard the cache.  Using a mutex, e.g. versus
a spinlock, is important at it allows KVM to allocate memory *without*
dropping the lock, i.e. so that the PAMT cache can be topped-up as needed
without needed to juggle arch.tdp_mmu_external_cache_lock.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  1 +
 arch/x86/include/asm/kvm_host.h    |  3 +-
 arch/x86/kvm/mmu/mmu.c             |  2 +-
 arch/x86/kvm/mmu/tdp_mmu.c         |  7 ++-
 arch/x86/kvm/vmx/tdx.c             | 96 ++++++++++++++++++++++++++++--
 arch/x86/kvm/vmx/tdx.h             |  3 +
 arch/x86/kvm/x86.c                 |  2 +-
 7 files changed, 102 insertions(+), 12 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 3ca56fe6b951..6083fb07cd3b 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -149,6 +149,7 @@ KVM_X86_OP_OPTIONAL(alloc_apic_backing_page)
 KVM_X86_OP_OPTIONAL_RET0(gmem_prepare)
 KVM_X86_OP_OPTIONAL_RET0(gmem_max_mapping_level)
 KVM_X86_OP_OPTIONAL(gmem_invalidate)
+KVM_X86_OP_OPTIONAL_RET0(gmem_convert)
 
 #undef KVM_X86_OP
 #undef KVM_X86_OP_OPTIONAL
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 385f1cf32d70..cd3e7dc6ab9b 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1861,7 +1861,7 @@ struct kvm_x86_ops {
 				 u64 new_spte, enum pg_level level);
 	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
 				    struct kvm_mmu_page *sp);
-	int (*topup_external_cache)(struct kvm_vcpu *vcpu, int min);
+	int (*topup_external_cache)(struct kvm *kvm, struct kvm_vcpu *vcpu, int min);
 
 
 	bool (*has_wbinvd_exit)(void);
@@ -1950,6 +1950,7 @@ struct kvm_x86_ops {
 	void *(*alloc_apic_backing_page)(struct kvm_vcpu *vcpu);
 	int (*gmem_prepare)(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 	void (*gmem_invalidate)(kvm_pfn_t start, kvm_pfn_t end);
+	int (*gmem_convert)(struct kvm *kvm, gfn_t start, gfn_t end, bool to_private);
 	int (*gmem_max_mapping_level)(struct kvm *kvm, kvm_pfn_t pfn, bool is_private);
 };
 
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index c2765bfc8492..62bf6bec2df2 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -606,7 +606,7 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 		if (r)
 			return r;
 
-		r = kvm_x86_call(topup_external_cache)(vcpu, PT64_ROOT_MAX_LEVEL);
+		r = kvm_x86_call(topup_external_cache)(vcpu->kvm, vcpu, PT64_ROOT_MAX_LEVEL);
 		if (r)
 			return r;
 	}
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index a45d8ee91481..a32192c35099 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1447,7 +1447,8 @@ bool kvm_tdp_mmu_wrprot_slot(struct kvm *kvm,
 	return spte_set;
 }
 
-static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct tdp_iter *iter)
+static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
+						       struct tdp_iter *iter)
 {
 	struct kvm_mmu_page *sp;
 
@@ -1464,7 +1465,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct tdp_iter *iter)
 		if (!sp->external_spt)
 			goto err_external_spt;
 
-		if (kvm_x86_call(topup_external_cache)(kvm_get_running_vcpu(), 1))
+		if (kvm_x86_call(topup_external_cache)(kvm, kvm_get_running_vcpu(), 1))
 			goto err_external_split;
 	}
 
@@ -1556,7 +1557,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
 			else
 				write_unlock(&kvm->mmu_lock);
 
-			sp = tdp_mmu_alloc_sp_for_split(&iter);
+			sp = tdp_mmu_alloc_sp_for_split(kvm, &iter);
 
 			if (shared)
 				read_lock(&kvm->mmu_lock);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 9f2ef46f87b0..c4050d94fb4d 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -607,6 +607,8 @@ void tdx_vm_destroy(struct kvm *kvm)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
+	tdx_free_pamt_cache(&kvm_tdx->pamt_cache);
+
 	tdx_reclaim_td_control_pages(kvm);
 
 	kvm_tdx->state = TD_STATE_UNINITIALIZED;
@@ -629,6 +631,8 @@ int tdx_vm_init(struct kvm *kvm)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
+	tdx_init_pamt_cache(&kvm_tdx->pamt_cache);
+
 	kvm->arch.has_protected_state = true;
 	/*
 	 * TDX Module doesn't allow the hypervisor to modify the EOI-bitmap,
@@ -1285,6 +1289,66 @@ static int tdx_map_gpa(struct kvm_vcpu *vcpu)
 	return 1;
 }
 
+static int __tdx_sept_split_huge_pages(struct kvm *kvm, gfn_t gfn, int target_level)
+{
+	gfn_t end = gfn + KVM_PAGES_PER_HPAGE(target_level + 1);
+
+	return kvm_tdp_mmu_mirrors_split_huge_pages(kvm, gfn, end, target_level);
+}
+
+static int tdx_sept_split_huge_pages(struct kvm *kvm, gfn_t start, gfn_t end,
+				     int target_level)
+{
+
+	gfn_t head = gfn_round_for_level(start, target_level + 1);
+	gfn_t tail = gfn_round_for_level(end, target_level + 1);
+	int r;
+
+	if (head != start) {
+		r = __tdx_sept_split_huge_pages(kvm, head, target_level);
+		if (r)
+			return r;
+	}
+
+	if (tail != end && (head != tail || head == start)) {
+		r = __tdx_sept_split_huge_pages(kvm, tail, target_level);
+		if (r)
+			return r;
+	}
+
+	return 0;
+}
+
+static int tdx_gmem_convert(struct kvm *kvm, gfn_t start, gfn_t end,
+			    bool to_private)
+{
+	/*
+	 * When converting from private=>shared, KVM must first split potential
+	 * hugepages, as KVM mustn't overzap private mappings for TDX guests,
+	 * i.e. must zap _exactly_ [start, end).  Split potential hugepages at
+	 * the head and tail of the to-be-converted (and thus zapped) range so
+	 * that KVM doesn't overzap due to dropping a hugepage that doesn't
+	 * fall wholly inside the range.
+	 */
+	if (to_private || !kvm_has_mirrored_tdp(kvm))
+		return 0;
+
+	/*
+	 * Acquire the external cache lock, a.k.a. the Dynamic PAMT lock, to
+	 * protect the per-VM cache of pre-allocate pages used to populate the
+	 * Dynamic PAMT when splitting S-EPT huge pages.
+	 */
+	guard(mutex)(&to_kvm_tdx(kvm)->pamt_cache_lock);
+
+	guard(write_lock)(&kvm->mmu_lock);
+
+	/*
+	 * TODO: Also split from PG_LEVEL_1G => PG_LEVEL_2M when KVM supports
+	 *       1GiB S-EPT pages.
+	 */
+	return tdx_sept_split_huge_pages(kvm, start, end, PG_LEVEL_4K);
+}
+
 static int tdx_report_fatal_error(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
@@ -1621,15 +1685,32 @@ void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int pgd_level)
 	td_vmcs_write64(to_tdx(vcpu), SHARED_EPT_POINTER, root_hpa);
 }
 
-static int tdx_topup_external_pamt_cache(struct kvm_vcpu *vcpu, int min)
+static struct tdx_pamt_cache *tdx_get_pamt_cache(struct kvm *kvm,
+						 struct kvm_vcpu *vcpu)
 {
+	if (KVM_BUG_ON(vcpu && vcpu->kvm != kvm, kvm))
+		return NULL;
+
+	if (vcpu)
+		return &to_tdx(vcpu)->pamt_cache;
+
+	lockdep_assert_held(&to_kvm_tdx(kvm)->pamt_cache_lock);
+	return &to_kvm_tdx(kvm)->pamt_cache;
+}
+
+static int tdx_topup_external_pamt_cache(struct kvm *kvm,
+					 struct kvm_vcpu *vcpu, int min)
+{
+	struct tdx_pamt_cache *pamt_cache;
+
 	if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
 		return 0;
 
-	if (WARN_ON_ONCE(!vcpu))
+	pamt_cache = tdx_get_pamt_cache(kvm, vcpu);
+	if (!pamt_cache)
 		return -EIO;
 
-	return tdx_topup_pamt_cache(&to_tdx(vcpu)->pamt_cache, min);
+	return tdx_topup_pamt_cache(pamt_cache, min);
 }
 
 static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
@@ -1792,8 +1873,8 @@ static struct page *tdx_spte_to_external_spt(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				       u64 new_spte, enum pg_level level)
 {
-	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct tdx_pamt_cache *pamt_cache;
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 	struct page *external_spt;
@@ -1804,7 +1885,8 @@ static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 	if (!external_spt)
 		return -EIO;
 
-	if (KVM_BUG_ON(!vcpu || vcpu->kvm != kvm, kvm))
+	pamt_cache = tdx_get_pamt_cache(kvm, kvm_get_running_vcpu());
+	if (!pamt_cache)
 		return -EIO;
 
 	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
@@ -1816,7 +1898,7 @@ static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 
 	err = tdh_do_no_vcpus(tdh_mem_page_demote, kvm, &kvm_tdx->td, gpa,
 			      level, spte_to_pfn(old_spte), external_spt,
-			      &to_tdx(vcpu)->pamt_cache, &entry, &level_state);
+			      pamt_cache, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_DEMOTE, entry, level_state, kvm))
 		return -EIO;
 
@@ -3776,6 +3858,8 @@ void __init tdx_hardware_setup(void)
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
 	vt_x86_ops.reclaim_external_sp = tdx_sept_reclaim_private_sp;
 
+	vt_x86_ops.gmem_convert = tdx_gmem_convert;
+
 	/*
 	 * FIXME: Wire up the PAMT hook iff DPAMT is supported, once VMXON is
 	 *        moved out of KVM and tdx_bringup() is folded into here.
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index f444fc84d93b..2bb4604a64ca 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -48,6 +48,9 @@ struct kvm_tdx {
 	 * Set/unset is protected with kvm->mmu_lock.
 	 */
 	bool wait_for_sept_zap;
+
+	struct tdx_pamt_cache pamt_cache;
+	struct mutex pamt_cache_lock;
 };
 
 /* TDX module vCPU states */
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index c80cc60e7862..c3d71ba9a1dc 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -14061,7 +14061,7 @@ void kvm_arch_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end)
 int kvm_arch_gmem_convert(struct kvm *kvm, gfn_t start, gfn_t end,
 			  bool to_private)
 {
-       return 0;
+       return kvm_x86_call(gmem_convert)(kvm, start, end, to_private);
 }
 #endif
 #endif

base-commit: b2791d61e9774d8575525816e864d2e09ee9090a
--

---

## [49] Konrad Rzeszutek Wilk — 2026-01-29
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On Wed, Jan 28, 2026 at 05:14:32PM -0800, Sean Christopherson wrote:
> This is a combined series of Dynamic PAMT (from Rick), and S-EPT hugepage
> support (from Yan).  Except for some last minute tweaks to the DPAMT array

What does PAMT stand for? Is there a design document somewhere?

> of S-EPT hugepage (mostly lack of cycles), and there's at least one patch in
> here that shouldn't be merged as-is (the quick-and-dirty switch from struct

Should they be split out as non-RFC then?

> on a design (hopefully), and then hand control back to Rick and Yan to polish
> their respective series for merge.

Can there be test-cases? Or simple code posted for QEMU which is the
tool that 99% of kernel engineers use?

> Outside of the guest_memfd arch hook for in-place conversion, S-EPT hugepage
> support doesn't have any direction dependencies/conflicts with guest_memfd

---

## [50] Dave Hansen — 2026-01-29
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On 1/29/26 09:13, Konrad Rzeszutek Wilk wrote:
> On Wed, Jan 28, 2026 at 05:14:32PM -0800, Sean Christopherson wrote:
>> This is a combined series of Dynamic PAMT (from Rick), and S-EPT hugepage

It's all in here (I hope):

https://lore.kernel.org/kvm/20250918232224.2202592-1-rick.p.edgecombe@intel.com/

---

## [51] Dave Hansen — 2026-01-29
*Subject: Re: [RFC PATCH v5 01/45] x86/tdx: Use pg_level in TDX APIs, not the
 TDX-Module's 0-based level*

On 1/28/26 17:14, Sean Christopherson wrote:
> Rework the TDX APIs to take the kernel's 1-based pg_level enum, not the
> TDX-Module's 0-based level.  The APIs are _kernel_ APIs, not TDX-Module

Yup, totally the right thing to do: push the TDX-isms as deep in the
code as possible. pg_level_to_tdx_sept_level() is a bit wordy, but I can
live with it:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [52] Dave Hansen — 2026-01-29
*Subject: Re: [RFC PATCH v5 10/45] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On 1/28/26 17:14, Sean Christopherson wrote:
...
> "asm/shared" is used for sharing TDX code between the early compressed
> code and the normal kernel code. While the compressed code for the guest

This is beating around the bush a bit. Should this read:

	Place the new header is in "asm/shared". It doesn't need to be
	there, but Google's kernel fork has early compressed use of
	these things and mainline will too soon.

or what? Can we be more direct, please?

---

## [53] Dave Hansen — 2026-01-29
*Subject: Re: [RFC PATCH v5 11/45] x86/tdx: Add helpers to check return status
 codes*

On 1/28/26 17:14, Sean Christopherson wrote:
...
>  	err = tdh_mng_vpflushdone(&kvm_tdx->td);
> -	if (err == TDX_FLUSHVP_NOT_DONE)

I really despise the non-csopeable, non-ctaggable, non-greppable names
like this. Sometimes it's unavoidable. Is it really unavoidable here?

Something like this is succinct enough and doesn't have any magic ##
macro definitions:

	TDX_ERR_EQ(err, TDX_FLUSHVP_NOT_DONE)

But, honestly, if I were trying to push a 45-patch series, I probably
wouldn't tangle this up as part of it. It's not _that_ desperately in
need of munging it a quarter of the way into this series.

---

## [54] Sean Christopherson — 2026-01-29
*Subject: Re: [RFC PATCH v5 11/45] x86/tdx: Add helpers to check return status codes*

On Thu, Jan 29, 2026, Dave Hansen wrote:
> On 1/28/26 17:14, Sean Christopherson wrote:
> ...

FWIW, I have zero preference on this.  I included the patch purely because it was
already there.

> But, honestly, if I were trying to push a 45-patch series, I probably
> wouldn't tangle this up as part of it. It's not _that_ desperately in

For sure.  The 45 patches are definitely not intended to land as one.  I posted
the mega-series to propose an end-to-end design for DPAMT + S-EPT hugepage support.
I don't have the bandwidth or brainpower to hash out a KVM design in two different
series.

---

## [55] Edgecombe, Rick P — 2026-01-29
*Subject: Re: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if
 cmpxchg64 on mirror SPTE "fails"*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Pass a pointer to iter->old_spte, not simply its value, when setting an
> external SPTE in __tdp_mmu_set_spte_atomic(), so that the iterator's value

Might be being dense here, but is the bug that if cmpxchg64 *succeeds* and
set_external_spte() fails? Then old_spte is not updated and the local retry will
expect the wrong old_spte.

>   The bug
> is currently benign as TDX is mutualy exclusive with all paths that do

---

## [56] Edgecombe, Rick P — 2026-01-29
*Subject: Re: [RFC PATCH v5 03/45] KVM: TDX: Account all non-transient page
 allocations for per-TD structures*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Account all non-transient allocations associated with a single TD (or its
> vCPUs), as KVM's ABI is that allocations that are active for the lifetime

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [57] Edgecombe, Rick P — 2026-01-29
*Subject: Re: [RFC PATCH v5 04/45] KVM: x86: Make "external SPTE" ops that can
 fail RET0 static calls*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Define kvm_x86_ops .link_external_spt(), .set_external_spte(), and
> .free_external_spt() as RET0 static calls so that an unexpected call to a

We don't want to crash unnecessarily, but do we want to get some sort of notice?

---

## [58] Sean Christopherson — 2026-01-29
*Subject: Re: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if
 cmpxchg64 on mirror SPTE "fails"*

On Thu, Jan 29, 2026, Rick P Edgecombe wrote:
> On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> > Pass a pointer to iter->old_spte, not simply its value, when setting an

No, the bug is if the cmpxchg64 fails.  On failure, the current mismatching value
is stored in the "old" param.  KVM relies on the iter->old_spte holding the
current value when restarting an operation without re-reading the SPTE from memory.

E.g. in __tdp_mmu_zap_root(), if tdp_mmu_set_spte_atomic() fails, iter->old_spte
*must* hold the current in-memroy value, otherwise the loop will hang because it
will re-attempt cmpxchg64 using the stale iter->old_spte.

static void __tdp_mmu_zap_root(struct kvm *kvm, struct kvm_mmu_page *root,
			       bool shared, int zap_level)
{
	struct tdp_iter iter;

	for_each_tdp_pte_min_level_all(iter, root, zap_level) {
retry:
		if (tdp_mmu_iter_cond_resched(kvm, &iter, false, shared))
			continue;

		if (!is_shadow_present_pte(iter.old_spte))
			continue;

		if (iter.level > zap_level)
			continue;

		if (!shared)
			tdp_mmu_iter_set_spte(kvm, &iter, SHADOW_NONPRESENT_VALUE);
		else if (tdp_mmu_set_spte_atomic(kvm, &iter, SHADOW_NONPRESENT_VALUE))
			goto retry;
	}
}

> >   The bug
> > is currently benign as TDX is mutualy exclusive with all paths that do

---

## [59] Edgecombe, Rick P — 2026-01-29
*Subject: Re: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if
 cmpxchg64 on mirror SPTE "fails"*

On Thu, 2026-01-29 at 14:23 -0800, Sean Christopherson wrote:
> No, the bug is if the cmpxchg64 fails.  On failure, the current mismatching value
> is stored in the "old" param.  KVM relies on the iter->old_spte holding the

Ah, I see. Sorry. Just went and refreshed up on the difference between
cmpxchg64() and try_cmpxchg64(). I see now that the log is accurate since it
refers to the behavior of the instruction, but specifying try_cmpxchg64() might
be a little clearer since cmpxchg() doesn't automatically update the 'old'
passed in. In either case:

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [60] Edgecombe, Rick P — 2026-01-30
*Subject: Re: [RFC PATCH v5 11/45] x86/tdx: Add helpers to check return status
 codes*

On Thu, 2026-01-29 at 12:35 -0800, Sean Christopherson wrote:
> On Thu, Jan 29, 2026, Dave Hansen wrote:
> > On 1/28/26 17:14, Sean Christopherson wrote:

I like the editor friendliness. The only downside is that it puts the onus on
the caller to make sure supported defines are passed into TDX_ERR_EQ(). Today
there are a few special cases like IS_TDX_NON_RECOVERABLE().

I don't know, I'm ok either way. I lean towards keeping it as in this patch
because we already had an error code bit interpretation bug:
https://lore.kernel.org/kvm/24d2f165-f854-4996-89cf-28d644c592a3@intel.com/

So the centralization of bit interpretation seems like a real win.

> 
> FWIW, I have zero preference on this.  I included the patch purely because it was

Ha, actually we all had a long thread on this:
https://lore.kernel.org/kvm/70484aa1b553ca250d893f80b2687b5d915e5309.camel@intel.com/

I see now that we closed it with you but never got Dave's final buy in.

---

## [61] Sean Christopherson — 2026-01-29
*Subject: Re: [RFC PATCH v5 04/45] KVM: x86: Make "external SPTE" ops that can
 fail RET0 static calls*

On Thu, Jan 29, 2026, Rick P Edgecombe wrote:
> On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> > Define kvm_x86_ops .link_external_spt(), .set_external_spte(), and

Hmm, that's probably doable, but definitely in a separate patch.  E.g. something
like:

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 6083fb07cd3b..270149f84bb4 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -3,6 +3,13 @@
 BUILD_BUG_ON(1)
 #endif
 
+#ifndef KVM_X86_OP_OPTIONAL
+#define KVM_X86_OP_OPTIONAL KVM_X86_OP
+#define KVM_X86_OP_OPTIONAL_RET0 KVM_X86_OP
+#define KVM_X86_OP_OPTIONAL_WARN KVM_X86_OP
+#define KVM_X86_OP_OPTIONAL_RET0_WARN KVM_X86_OP
+#endif
+
 /*
  * KVM_X86_OP() and KVM_X86_OP_OPTIONAL() are used to help generate
  * both DECLARE/DEFINE_STATIC_CALL() invocations and
@@ -94,11 +101,11 @@ KVM_X86_OP_OPTIONAL_RET0(set_tss_addr)
 KVM_X86_OP_OPTIONAL_RET0(set_identity_map_addr)
 KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
-KVM_X86_OP_OPTIONAL(alloc_external_sp)
-KVM_X86_OP_OPTIONAL(free_external_sp)
-KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
-KVM_X86_OP_OPTIONAL(reclaim_external_sp)
-KVM_X86_OP_OPTIONAL_RET0(topup_external_cache)
+KVM_X86_OP_OPTIONAL_WARN(alloc_external_sp)
+KVM_X86_OP_OPTIONAL_WARN(free_external_sp)
+KVM_X86_OP_OPTIONAL_RET0_WARN(set_external_spte)
+KVM_X86_OP_OPTIONAL_WARN(reclaim_external_sp)
+KVM_X86_OP_OPTIONAL_RET0_WARN(topup_external_cache)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index cd3e7dc6ab9b..663c9943c0dd 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2004,8 +2004,6 @@ extern struct kvm_x86_ops kvm_x86_ops;
 
 #define KVM_X86_OP(func) \
        DECLARE_STATIC_CALL(kvm_x86_##func, *(((struct kvm_x86_ops *)0)->func));
-#define KVM_X86_OP_OPTIONAL KVM_X86_OP
-#define KVM_X86_OP_OPTIONAL_RET0 KVM_X86_OP
 #include <asm/kvm-x86-ops.h>
 
 int kvm_x86_vendor_init(struct kvm_x86_init_ops *ops);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index c3d71ba9a1dc..1748f44c81c0 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -143,8 +143,6 @@ struct kvm_x86_ops kvm_x86_ops __read_mostly;
 #define KVM_X86_OP(func)                                            \
        DEFINE_STATIC_CALL_NULL(kvm_x86_##func,                      \
                                *(((struct kvm_x86_ops *)0)->func));
-#define KVM_X86_OP_OPTIONAL KVM_X86_OP
-#define KVM_X86_OP_OPTIONAL_RET0 KVM_X86_OP
 #include <asm/kvm-x86-ops.h>
 EXPORT_STATIC_CALL_GPL(kvm_x86_get_cs_db_l_bits);
 EXPORT_STATIC_CALL_GPL(kvm_x86_cache_reg);
@@ -9965,6 +9963,17 @@ static struct notifier_block pvclock_gtod_notifier = {
 };
 #endif
 
+static void kvm_static_call_warn(void)
+{
+       WARN_ON_ONCE(1);
+}
+
+static long kvm_static_call_warn_return0(void)
+{
+       WARN_ON_ONCE(1);
+       return 0;
+}
+
 static inline void kvm_ops_update(struct kvm_x86_init_ops *ops)
 {
        memcpy(&kvm_x86_ops, ops->runtime_ops, sizeof(kvm_x86_ops));
@@ -9977,6 +9986,12 @@ static inline void kvm_ops_update(struct kvm_x86_init_ops *ops)
 #define KVM_X86_OP_OPTIONAL_RET0(func) \
        static_call_update(kvm_x86_##func, (void *)kvm_x86_ops.func ? : \
                                           (void *)__static_call_return0);
+#define KVM_X86_OP_OPTIONAL_WARN(func) \
+       static_call_update(kvm_x86_##func, (void *)kvm_x86_ops.func ? : \
+                                          (void *)kvm_static_call_warn);
+#define KVM_X86_OP_OPTIONAL_RET0_WARN(func) \
+       static_call_update(kvm_x86_##func, (void *)kvm_x86_ops.func ? : \
+                                          (void *)kvm_static_call_warn_return0);
 #include <asm/kvm-x86-ops.h>
 #undef __KVM_X86_OP

---

## [62] Sean Christopherson — 2026-01-29
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add tdx_alloc/free_control_page()
 helpers*

On Wed, Jan 28, 2026, Sean Christopherson wrote:
> +/*
> + * For SEAMCALLs that pass a bundle of pages, the TDX spec treats the registers

The above closing ')' after args is misplaced, this should be 

	if (WARN_ON_ONCE(reg + size > (void *)args + sizeof(*args)))

I'm still in disbelief that I managed to end up with such a horrid bug that
compiled without any warnings.  *sigh*

---

## [63] Edgecombe, Rick P — 2026-01-30
*Subject: Re: [RFC PATCH v5 04/45] KVM: x86: Make "external SPTE" ops that can
 fail RET0 static calls*

On Thu, 2026-01-29 at 17:28 -0800, Sean Christopherson wrote:
> 
> Hmm, that's probably doable, but definitely in a separate patch. 

I think it would be a good change. But after more consideration, I
think the original patch is good on its own. Better to turn a bug into
a deterministic thing, than an opportunity to consume stack. Seems to
be what you intended.

Another idea would be to have a variant that returns an error instead
of 0 so the callers can have there error logic triggered, but it's all
incremental value on top of this.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [64] Edgecombe, Rick P — 2026-01-30
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop
 kvm_x86_ops.link_external_spt(), use .set_external_spte() for all*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Drop the dedicated .link_external_spt() for linking non-leaf S-EPT
> pages, and instead funnel everything through .set_external_spte(). 

It has better handling of the external_spt == NULL case too, by
actually returning an error, but one naming nit below to take or leave.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

> ---
>  arch/x86/include/asm/kvm-x86-ops.h |  1 -

The "external" abstraction wraps the "S-EPT" knowledge and naming (for
maybe increasingly dubious reasons), but in the TDX code, inside the
abstraction, it uses the sept naming. so I might have called it
sept_pt.

---

## [65] Yan Zhao — 2026-02-03
*Subject: Re: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if
 cmpxchg64 on mirror SPTE "fails"*

On Wed, Jan 28, 2026 at 05:14:34PM -0800, Sean Christopherson wrote:
> Pass a pointer to iter->old_spte, not simply its value, when setting an
> external SPTE in __tdp_mmu_set_spte_atomic(), so that the iterator's value
Do we need to add a comment explaining that when the above try_cmpxchg64()
succeeds, the value of *old_spte is unmodified?

>  	else
>  		__kvm_tdp_mmu_write_spte(sptep, new_spte);

---

## [66] Yan Zhao — 2026-02-03
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop
 kvm_x86_ops.link_external_spt(), use .set_external_spte() for all*

On Wed, Jan 28, 2026 at 05:14:37PM -0800, Sean Christopherson wrote:
> Drop the dedicated .link_external_spt() for linking non-leaf S-EPT pages,
> and instead funnel everything through .set_external_spte().  Using separate
Why not move this check of is_shadow_present_pte() to tdx_sept_set_private_spte()
as well? 

Or also check !is_shadow_present_pte(new_spte) in TDP MMU?

  	
>  	 * We need to lock out other updates to the SPTE until the external
>  	 * page table has been modified. Use FROZEN_SPTE similar to
Could we remove the KVM_BUG_ON()s, and ...

> +	return virt_to_page(sp->external_spt);
> +}
add a KVM_BUG_ON() here?
It could save KVM_BUG_ON()s and have KVM_BUG_ON() match -EIO :)

And as Rick also mentioned, better to remove external in external_spt, e.g.
something like pt_page.

And mirror_spte --> new_spte?

> +		return -EIO;
> +
Also check this for tdx_sept_link_private_spt()?

  
>  	/*
>  	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()

---

## [67] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if
 cmpxchg64 on mirror SPTE "fails"*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Pass a pointer to iter->old_spte, not simply its value, when setting an
> external SPTE in __tdp_mmu_set_spte_atomic(), so that the iterator's value

Reviewed-by: Kai Huang <kai.huang@intel.com>

Btw, do we need to cc stable?

---

## [68] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 03/45] KVM: TDX: Account all non-transient page
 allocations for per-TD structures*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Account all non-transient allocations associated with a single TD (or its
> vCPUs), as KVM's ABI is that allocations that are active for the lifetime

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [69] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 04/45] KVM: x86: Make "external SPTE" ops that can
 fail RET0 static calls*

On Fri, 2026-01-30 at 17:32 +0000, Edgecombe, Rick P wrote:
> On Thu, 2026-01-29 at 17:28 -0800, Sean Christopherson wrote:
> > 

Makes sense.

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [70] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Extend "struct kvm_mmu_memory_cache" to support a custom page allocator
> so that x86's TDX can update per-page metadata on allocation and free().

I thought it could be more generic for allocating an object, but not just a
page.

E.g., I thought we might be able to use it to allocate a structure which has
"pair of DPAMT pages" so it could be assigned to 'struct kvm_mmu_page'.  But
it seems you abandoned this idea.  May I ask why?  Just want to understand
the reasoning here.

Anyway:

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  include/linux/kvm_types.h | 2 ++

---

## [71] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> Now that kvm_mmu_memory_cache supports custom page allocators, wire up the
> S-EPT cache to use tdx_{alloc,free}_control_page() (arguably S-EPT pages

Reviewed-by: Kai Huang <kai.huang@intel.com>

Some nits below ..


[...]

>  	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
>  				 u64 mirror_spte);

The above two comments are still useful to me.

Not sure why do you want to remove them, especially in _this_ patch?

>  	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
>  				     u64 mirror_spte);

Unintentional change?

>  	bool (*has_wbinvd_exit)(void);
>  

Ditto.  Not sure this adjustment is intentional?

---

## [72] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop kvm_x86_ops.link_external_spt(),
 use .set_external_spte() for all*

On Tue, Feb 03, 2026, Yan Zhao wrote:
> On Wed, Jan 28, 2026 at 05:14:37PM -0800, Sean Christopherson wrote:
> >  static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sptep,

The series gets there eventually, but as of this commit, @old_spte isn't plumbed
into tdx_sept_set_private_spte().

> Or also check !is_shadow_present_pte(new_spte) in TDP MMU?

Not sure I understand this suggestion.
   	
> > diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
> > index 5688c77616e3..30494f9ceb31 100644

We could, but I don't want to, because if we're going to bother with sanity checks,
I want the resulting WARNs to be precise.  I.e. I want the WARN to capture *why*
tdx_spte_to_external_spt() failed, to make debug/triage easier.

> And as Rick also mentioned, better to remove external in external_spt, e.g.
> something like pt_page.

Yeah, maybe sept_spt?

> And mirror_spte --> new_spte?

Hmm, ya, I made that change later, but it can probably be shifted here.

> > -	WARN_ON_ONCE(!is_shadow_present_pte(mirror_spte) ||
> > -		     (mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);

Eh, we could, but I don't think it's necessary.  make_nonleaf_spte() is hardcoded
to set full permissions (and I don't see that changing any time soon), whereas
leaf SPTE protections are much more dynamic.

---

## [73] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if
 cmpxchg64 on mirror SPTE "fails"*

On Tue, Feb 03, 2026, Kai Huang wrote:
> On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> > Pass a pointer to iter->old_spte, not simply its value, when setting an

Probably not?  The bug is benign until dirty logging comes along, and if someone
backports that support (if it ever manifests) to an older kernel, it's firmly
that person's responsibility to pick up dependencies like this.

---

## [74] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

On Tue, Feb 03, 2026, Kai Huang wrote:
> On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> > Extend "struct kvm_mmu_memory_cache" to support a custom page allocator

Because that requires more complexity and there's no known use case, and I don't
see an obvious way for a use case to come along.  All of the motiviations for a
custom allocation scheme that I can think of apply only to full pages, or fit
nicely in a kmem_cache.

Specifically, the "cache" logic is already bifurcated between "kmem_cache' and
"page" usage.  Further splitting the "page" case doesn't require modifications to
the "kmem_cache" case, whereas providing a fully generic solution would require
additional changes, e.g. to handle this code:

	page = (void *)__get_free_page(gfp_flags);
	if (page && mc->init_value)
		memset64(page, mc->init_value, PAGE_SIZE / sizeof(u64));

It certainly wouldn't be much complexity, but this code is already a bit awkward,
so I don't think it makes sense to add support for something that will probably
never be used.

---

## [75] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Tue, Feb 03, 2026, Kai Huang wrote:
> On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> >  	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,

My intent was to replace the individual comments with a more generic comment for
all of the "external" hooks.  For things like "and flush TLB", IMO those comments
belong at the call sites, not at this point.  E.g. _KVM_ doesn't require a TLB
flush in all cases.  And so for the definition of the hooks, I would prefer a more
generic comment, so that if there are details that matter to the usage, they are
documented there.

> >  	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
> >  				     u64 mirror_spte);

Ya.

> 
> >  	bool (*has_wbinvd_exit)(void);

Heh, I'm pretty sure it was intentional, but yeah, doesn't belong here.

---

## [76] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 11/45] x86/tdx: Add helpers to check return status codes*

On Fri, Jan 30, 2026, Rick P Edgecombe wrote:
> On Thu, 2026-01-29 at 12:35 -0800, Sean Christopherson wrote:
> > On Thu, Jan 29, 2026, Dave Hansen wrote:

Eh, that's easy enough to handle with a static_assert().

> Today there are a few special cases like IS_TDX_NON_RECOVERABLE().

Why bother with a wrapper for that one?  It's a single bit, just test that bit.
For me, providing IS_TDX_NON_RECOVERABLE() is _more_ confusing, because it
suggests that there's a NON_RECOVERABLE error, when in fact (IIUC) it's more or
less a modifier.

> I don't know, I'm ok either way. I lean towards keeping it as in this patch
> because we already had an error code bit interpretation bug:

Oh, it's _that_ discussion :-)

What I meant was, "I don't have a strong preference between TDX_ERR_EQ() and
this patch".  What I didn't like was tdx_operand_invalid(), because that reads
like a command and it's not at all clear that it's macro-like in behavior.

I'd vote for IS_TDX_ERR() over TDX_ERR_EQ(), but either works for me (as does
this patch).

> I see now that we closed it with you but never got Dave's final buy in.

---

## [77] Edgecombe, Rick P — 2026-02-03
*Subject: Re: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

On Tue, 2026-02-03 at 12:12 -0800, Sean Christopherson wrote:
> > E.g., I thought we might be able to use it to allocate a structure which has
> > "pair of DPAMT pages" so it could be assigned to 'struct kvm_mmu_page'.  But

The thing that the design needlessly works around is that we can rely on that
there are only two DPAMT pages per 2MB range. We don't need the dynamic page
count allocations.

This means we don't need to pass around the list of pages that lets arch/x86
take as many pages as it needs. We can maybe just pass in a struct like Kai was
suggesting to the get/put helpers. So I was in the process of trying to morph
this series in that direction to get rid of the complexity resulting from the
dynamic assumption. 

This was what I had done in response to v4 discussions, so now retrofitting it
into this new ops scheme. Care to warn me off of this before I have something to
show?

---

## [78] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

On Tue, Feb 03, 2026, Rick P Edgecombe wrote:
> On Tue, 2026-02-03 at 12:12 -0800, Sean Christopherson wrote:
> > > E.g., I thought we might be able to use it to allocate a structure which has

That's largely orthogonal to this change.  This change is about preparing the
DPAMT when S-EPT page is allocated versus being installed.  The fact that DPAMT
requires at most two pages versus a more dynamic maximum is irrelevant.

The caches aren't about dynamic sizes (though they play nicely with them), they're
about:

  (a) not having to deal with allocating under spinlock
  (b) not having to free memory that goes unused (for a single page fault)
  (c) batching allocations for performance reasons (with the caveat that I doubt
      anyone has measured the performance impact in many, many years).

None of those talking points change at all if KVM needs to provide 2 pages versus
N pages.  The max number of pages needed for page tables is pretty much the same
thing as DPAMT, just with a higher max (4/5 vs. 2).  In both cases, the allocated
pages may or may not be consumed for any given fault.

For the leaf pages (including the hugepage splitting cases), which don't utilize
KVM's kvm_mmu_memory_cache, I wouldn't expect the KVM details to change all that
much.  In fact, they shouldn't change at all, because tracking 2 pages versus N
pages in "struct tdx_pamt_cache" is a detail that is 100% buried in the TDX subsystem
(which was pretty much the entire goal of my design).

Though maybe I'm misunderstanding what you have in mind?

---

## [79] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Tue, 2026-02-03 at 12:17 -0800, Sean Christopherson wrote:
> On Tue, Feb 03, 2026, Kai Huang wrote:
> > On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:

I see.  You actually mentioned "propagate changes in mirror page tables to
the external pages" in the new comment, so all make sense to me now.

---

## [80] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

On Tue, 2026-02-03 at 12:12 -0800, Sean Christopherson wrote:
> On Tue, Feb 03, 2026, Kai Huang wrote:
> > On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:

For this particular piece of code, we can add a helper for allocating normal
page table pages, get rid of mc->init_value completely and hook mc-
>page_get() to that helper.

A bonus is we can then call that helper in all places when KVM needs to
allocate a page for normal page table instead of just calling
get_zerod_pages() directly, e.g., like the one in
tdp_mmu_alloc_sp_for_split(), so that we can have a consistent way for
allocating normal page table pages.

---

## [81] Huang, Kai — 2026-02-03
*Subject: Re: [RFC PATCH v5 02/45] KVM: x86/mmu: Update iter->old_spte if
 cmpxchg64 on mirror SPTE "fails"*

On Tue, 2026-02-03 at 12:06 -0800, Sean Christopherson wrote:
> On Tue, Feb 03, 2026, Kai Huang wrote:
> > On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:

Makes sense. :-)

---

## [82] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 04/45] KVM: x86: Make "external SPTE" ops that can
 fail RET0 static calls*

On Fri, Jan 30, 2026, Rick P Edgecombe wrote:
> On Thu, 2026-01-29 at 17:28 -0800, Sean Christopherson wrote:
> > 

I don't like that idea, at all.  First and foremost, I don't want to litter KVM
with WARNs for things that simply can't happen.  I'm fine adding infrastructure
that hides the sanity checks, but I don't want to bleed that into callers.

The other aspect I dislike is that returning a specific errno could lead to all
sorts of weirdness and hidden dependencies.

All in all, I think we'd be increasing the chances of creating bugs just to harden
against issues that in all likelihood will never happen.

---

## [83] Sean Christopherson — 2026-02-03
*Subject: Re: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

On Tue, Feb 03, 2026, Kai Huang wrote:
> On Tue, 2026-02-03 at 12:12 -0800, Sean Christopherson wrote:
> > On Tue, Feb 03, 2026, Kai Huang wrote:

Hmm, I like the idea, but I don't think it would be a net positive.  In practice,
x86's "normal" page tables stop being normal, because KVM now initializes all
SPTEs with BIT(63)=1 on x86-64.  And that would also incur an extra RETPOLINE on
all those allocations.

> A bonus is we can then call that helper in all places when KVM needs to
> allocate a page for normal page table instead of just calling

Huh.  Actually, that's a bug, but not the one you probably expect.  At a glance,
it looks like KVM incorrectly zeroing the page instead of initializing it with
SHADOW_NONPRESENT_VALUE.  But it's actually a "performance" bug, because KVM
doesn't actually need to pre-initialize the page: either the page will never be
used, or every SPTE will be initialized as a child SPTE.

So that one _should_ be different, e.g. should be:

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index a32192c35099..36afd67601fc 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1456,7 +1456,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
        if (!sp)
                return NULL;
 
-       sp->spt = (void *)get_zeroed_page(GFP_KERNEL_ACCOUNT);
+       sp->spt = (void *)__get_free_page(GFP_KERNEL_ACCOUNT);
        if (!sp->spt)
                goto err_spt;
 
> so that we can have a consistent way for allocating normal page table pages.

---

## [84] Yan Zhao — 2026-02-04
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop
 kvm_x86_ops.link_external_spt(), use .set_external_spte() for all*

On Tue, Feb 03, 2026 at 08:05:05PM +0000, Sean Christopherson wrote:
> On Tue, Feb 03, 2026, Yan Zhao wrote:
> > On Wed, Jan 28, 2026 at 05:14:37PM -0800, Sean Christopherson wrote:
Sorry. The accurate expression should be 
"what about moving !is_shadow_present_pte(new_spte) to TDP MMU as well?".

>    	
> > > diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
Ok.
 
> > And as Rick also mentioned, better to remove external in external_spt, e.g.
> > something like pt_page.
Hmm, here sept_spt is of type struct page, while sp->spt and sp->external_spt
represents VA. Not sure if it will cause confusion.

But I don't have strong opinion :)

> > And mirror_spte --> new_spte?
> 
Makes sense.

---

## [85] Huang, Kai — 2026-02-04
*Subject: Re: [RFC PATCH v5 19/45] KVM: Allow owner of kvm_mmu_memory_cache to
 provide a custom page allocator*

On Tue, 2026-02-03 at 18:16 -0800, Sean Christopherson wrote:
> On Tue, Feb 03, 2026, Kai Huang wrote:
> > On Tue, 2026-02-03 at 12:12 -0800, Sean Christopherson wrote:

No argument on this.  People hate indirect calls I guess. :-)

> 
> > A bonus is we can then call that helper in all places when KVM needs to

If we look from "performance" perspective, yeah indeed, albeit we probably
not gonna see any performance difference.

But no more arguments.  I just think it will be less error-prone if we have
a consistent way for allocating the same object (no matter what it is), but
it's just a theoretical thing.

---

## [86] Yan Zhao — 2026-02-04
*Subject: Re: [RFC PATCH v5 06/45] KVM: x86/mmu: Fold
 set_external_spte_present() into its sole caller*

On Wed, Jan 28, 2026 at 05:14:38PM -0800, Sean Christopherson wrote:
> Fold set_external_spte_present() into __tdp_mmu_set_spte_atomic() in
> anticipation of supporting hugepage splitting, at which point other paths
Should this be -EIO instead?
Though -EBUSY was introduced by commit 94faba8999b9 ('KVM: x86/tdp_mmu:
Propagate tearing down mirror page tables')

> -		ret = set_external_spte_present(kvm, iter->sptep, iter->gfn,
> -						&iter->old_spte, new_spte, iter->level);
Add "lockdep_assert_held(&kvm->mmu_lock)" for this case?


> +		/*
> +		 * Temporarily freeze the SPTE until the external PTE operation

---

## [87] Yan Zhao — 2026-02-04
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Wed, Jan 28, 2026 at 05:14:40PM -0800, Sean Christopherson wrote:
> Invoke .remove_external_spte() in handle_changed_spte() as appropriate
> instead of relying on callers to do the right thing.  Relying on callers
Should we check !is_present instead of !is_leaf?
e.g. a transition from a present leaf entry to a present non-leaf entry could
also trigger this if case.

Besides, need "KVM_BUG_ON(shared, kvm)" in this case.
> +		kvm_x86_call(remove_external_spte)(kvm, gfn, level, old_spte);
>  }

---

## [88] Yan Zhao — 2026-02-04
*Subject: Re: [RFC PATCH v5 09/45] KVM: x86: Rework .free_external_spt() into
 .reclaim_external_sp()*

On Wed, Jan 28, 2026 at 05:14:41PM -0800, Sean Christopherson wrote:
> Massage .free_external_spt() into .reclaim_external_sp() to free up (pun
> intended) "free" for actually freeing memory, and to allow TDX to do more
Do you think "free" is still better than "reclaim" though TDX actually
invokes tdx_reclaim_page() to reclaim it on the TDX side?

Naming it free_external_sp can be interpreted as freeing the sp->external_spt
externally (vs freeing it in tdp_mmu_free_sp_rcu_callback(). This naming also
allows for the future possibility of freeing sp->external_spt before the HKID is
freed (though this is unlikely).

>  	/* Update external page table from spte getting removed, and flush TLB. */
>  	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
Passing in "sp" and having "reclaim_private_sp" in the function name is bit
confusing.
Strictly speaking, only sp->external_spt is private, while the sp and sp->spt
are just mirroring the external spt.

But I understand it's for setting sp->external_spt to NULL on error.

>  {
> -	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);

---

## [89] Sean Christopherson — 2026-02-04
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On Thu, Jan 29, 2026, Konrad Rzeszutek Wilk wrote:
> On Wed, Jan 28, 2026 at 05:14:32PM -0800, Sean Christopherson wrote:
> > This is a combined series of Dynamic PAMT (from Rick), and S-EPT hugepage

Yeah, I'll do that soonish.  I posted the kitchen sink so that people could
review the entire thing without having to chase down 4+ series/patches.

> > on a design (hopefully), and then hand control back to Rick and Yan to polish
> > their respective series for merge.

No?  The core limitation is that KVM doesn't yet support hugepages for private
memory.  No amount userspace code can overcome that limitation.

We can and do have tests and VMM support, but it's all out-of-tree (for now).
All I'm saying here is that I'm ok landing the S-EPT hugepage code in advance of
guest_memfd hugepage support, e.g. so that we don't end up in a stalemate due to
cyclical dependecies, or one big megaseries.

---

## [90] Dave Hansen — 2026-02-04
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On 2/4/26 06:38, Sean Christopherson wrote:
...
> We can and do have tests and VMM support, but it's all out-of-tree (for now).
> All I'm saying here is that I'm ok landing the S-EPT hugepage code in advance of

Does "landing" mean having it sit in some topic branch, or pushing to Linus?

I'm all for getting these hellish dependency chains out of the way, but
we usually try pretty hard to avoid having dead/unreachable code in
mainline.

If it is something you want to do in mainline, we should probably do a
bit of cross-x86/kvm brainstorming to make sure there's no other option.

---

## [91] Sean Christopherson — 2026-02-04
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Wed, Feb 04, 2026, Yan Zhao wrote:
> On Wed, Jan 28, 2026 at 05:14:40PM -0800, Sean Christopherson wrote:
> > @@ -590,10 +566,21 @@ static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,

No, the !is_leaf check is very intentional.  At this point in the series, S-EPT
doesn't support hugepages.  If KVM manages to install a leaf SPTE and replaces
that SPTE with a non-leaf SPTE, then we absolutely want the KVM_BUG_ON() in
tdx_sept_remove_private_spte() to fire:

	/* TODO: handle large pages. */
	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
		return -EIO;


And then later on, when S-EPT gains support for hugepages, "KVM: TDX: Add core
support for splitting/demoting 2MiB S-EPT to 4KiB" doesn't need to touch code
outside of arch/x86/kvm/vmx/tdx.c, because everything has already been plumbed
in.

> Besides, need "KVM_BUG_ON(shared, kvm)" in this case.

Eh, we have lockdep_assert_held_write() in the S-EPT paths that require mmu_lock
to be held for write.  I don't think a KVM_BUG_ON() here would add meaningful
value.

---

## [92] Yan Zhao — 2026-02-05
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Wed, Feb 04, 2026 at 06:23:38PM -0800, Sean Christopherson wrote:
> On Wed, Feb 04, 2026, Yan Zhao wrote:
> > On Wed, Jan 28, 2026 at 05:14:40PM -0800, Sean Christopherson wrote:
But the op is named remove_external_spte().
And the check of "level != PG_LEVEL_4K" is for removing large leaf entries.
Relying on this check is tricky and confusing.

> And then later on, when S-EPT gains support for hugepages, "KVM: TDX: Add core
> support for splitting/demoting 2MiB S-EPT to 4KiB" doesn't need to touch code
I haven't looked at the later patches for huge pages, but plumbing here directly
for splitting does not look right when it's invoked under shared mmu_lock.
See the comment below.
 
> > Besides, need "KVM_BUG_ON(shared, kvm)" in this case.
> 
Hmm, I think KVM_BUG_ON(shared, kvm) is still useful.
If KVM invokes remove_external_spte() under shared mmu_lock, it needs to freeze
the entry first, similar to the sequence in __tdp_mmu_set_spte_atomic().

i.e., invoking external x86 ops in handle_changed_spte() for mirror roots should
be !shared only.

Relying on the TDX code's lockdep_assert_held_write() for warning seems less
clear than having an explicit check here.

---

## [93] Yan Zhao — 2026-02-05
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

> +void tdx_quirk_reset_page(struct page *page);
Looks this change is unnecessary.

>  int tdx_guest_keyid_alloc(void);
>  u32 tdx_get_nr_guest_keyids(void);
This function is not invoked when !tdx_supports_dynamic_pamt().
So, probably we can just return the count below?

> +	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
> +}

---

## [94] Yan Zhao — 2026-02-05
*Subject: Re: [RFC PATCH v5 09/45] KVM: x86: Rework .free_external_spt() into
 .reclaim_external_sp()*

On Wed, Feb 04, 2026 at 05:45:39PM +0800, Yan Zhao wrote:
> On Wed, Jan 28, 2026 at 05:14:41PM -0800, Sean Christopherson wrote:
> > Massage .free_external_spt() into .reclaim_external_sp() to free up (pun
Oh. I found there's a free_external_sp() in patch 20.

So, maybe reclaim_external_sp() --> remove_external_spt() ?

Still think "sp" is not good :)

> >  	/* Update external page table from spte getting removed, and flush TLB. */
> >  	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,

---

## [95] Sean Christopherson — 2026-02-05
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On Wed, Feb 04, 2026, Dave Hansen wrote:
> On 2/4/26 06:38, Sean Christopherson wrote:
> ...

I was thinking pushing to Linus' tree, but a topic branch could likely provide
almost as much value?

> I'm all for getting these hellish dependency chains out of the way, but
> we usually try pretty hard to avoid having dead/unreachable code in

I'm a-ok starting with a topic branch.  If maintaining that branch becomes too
costly, then we can always revisit things.  And that would probably be good
motiviation to beat guest_memfd hugepage into shape :-)

---

## [96] Dave Hansen — 2026-02-05
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On 2/5/26 07:53, Sean Christopherson wrote:
> I'm a-ok starting with a topic branch.  If maintaining that branch becomes too
> costly, then we can always revisit things.  And that would probably be good

Sounds like a plan.

---

## [97] Sean Christopherson — 2026-02-05
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Thu, Feb 05, 2026, Yan Zhao wrote:
> On Wed, Feb 04, 2026 at 06:23:38PM -0800, Sean Christopherson wrote:
> > On Wed, Feb 04, 2026, Yan Zhao wrote:

I agree that the naming at this point in the series is unfortunate, but I don't
see it as outright wrong.  That the TDP MMU could theoretically replace the leaf
SPTE with a non-leaf SPTE doesn't change the fact that the old leaf SPTE *is*
being removed.

> Relying on this check is tricky and confusing.

If it's still confusing at the end of the series, then I'm happy to discuss how
we can make it less confusion.  But as of this point in the series, I unfortunately
don't see a better way to achieve my end goals (reducing the number of kvm_x86_ops
hooks, and reducing how many TDX specific details bleed into common MMU code).

There are "different" ways to incrementally move from where were at today, to where
I want KVM to be, but I don't see them as "better".  I.e. AFAICT, there's no way
to move incrementally with reviewable patches while also maintaining perfect/ideal
naming and flow.

> > And then later on, when S-EPT gains support for hugepages, "KVM: TDX: Add core
> > support for splitting/demoting 2MiB S-EPT to 4KiB" doesn't need to touch code

Please do.  As above, I don't think it's realistic to completely avoid some amount
of "eww" in the intermediate stages.

> but plumbing here directly for splitting does not look right when it's
> invoked under shared mmu_lock.

Sure, but...

> Relying on the TDX code's lockdep_assert_held_write() for warning seems less
> clear than having an explicit check here.

...that's TDX's responsibility to enforce, and I don't see any justification for
something more than a lockdep assertion.  As I've said elsewhere, several times,
at some point we have to commit to getting the code right.  Adding KVM_BUG_ON() in
Every. Single. Call. does not yield more maintainable code.  There are myriad
things KVM can screw up, many of which have far, far more harmful impact than
calling an S-EPT hook with mmu_lock held for read instead of write.

The bar for adding a KVM_BUG_ON() is not simply "this shouldn't happen".  It's,
this shouldn't happen *and* at least one of (not a complete list):

  - we've either screwed this up badly more than once
  - it's really hard to get right
  - we might not notice if we do screw it up
  - KVM might corrupt data if we continue on

---

## [98] Sean Christopherson — 2026-02-05
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add tdx_alloc/free_control_page()
 helpers*

On Thu, Feb 05, 2026, Yan Zhao wrote:
> > diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> > index f6e80aba5895..682c8a228b53 100644

Or maybe WARN_ON_ONCE() and return 0?  I have no strong preference.

> > +	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
> > +}

---

## [99] Sean Christopherson — 2026-02-05
*Subject: Re: [RFC PATCH v5 09/45] KVM: x86: Rework .free_external_spt() into .reclaim_external_sp()*

On Thu, Feb 05, 2026, Yan Zhao wrote:
> On Wed, Feb 04, 2026 at 05:45:39PM +0800, Yan Zhao wrote:
> > On Wed, Jan 28, 2026 at 05:14:41PM -0800, Sean Christopherson wrote:

I think my vote would be for reclaim_external_spt().  I don't like "remove", because
similar to "free", I think most readers will assume success is guaranteed.

---

## [100] Sean Christopherson — 2026-02-05
*Subject: Re: [RFC PATCH v5 06/45] KVM: x86/mmu: Fold set_external_spte_present()
 into its sole caller*

On Wed, Feb 04, 2026, Yan Zhao wrote:
> On Wed, Jan 28, 2026 at 05:14:38PM -0800, Sean Christopherson wrote:
> > @@ -626,6 +599,8 @@ static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,

Yeah, probably.

> Though -EBUSY was introduced by commit 94faba8999b9 ('KVM: x86/tdp_mmu:
> Propagate tearing down mirror page tables')

No, because I don't want to unnecessarily bleed TDX details into common MMU.  Ah,
but there was a pre-existing lockdep in set_external_spte_present().  So I guess
that's arguably a functional change and should be called out in the changelog.

But I still want to drop the assertion (or maybe move it to TDX in a prep patch),
because ultimately the requirements around locking come from TDX, not from the
TDP MMU.

---

## [101] Sean Christopherson — 2026-02-05
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop kvm_x86_ops.link_external_spt(),
 use .set_external_spte() for all*

On Wed, Feb 04, 2026, Yan Zhao wrote:
> On Tue, Feb 03, 2026 at 08:05:05PM +0000, Sean Christopherson wrote:
> > On Tue, Feb 03, 2026, Yan Zhao wrote:

It's already there, in __tdp_mmu_set_spte_atomic():

		/*
		 * KVM doesn't currently support zapping or splitting mirror
		 * SPTEs while holding mmu_lock for read.
		 */
		if (KVM_BUG_ON(is_shadow_present_pte(iter->old_spte), kvm) ||
		    KVM_BUG_ON(!is_shadow_present_pte(new_spte), kvm))
			return -EBUSY;


> > > And as Rick also mentioned, better to remove external in external_spt, e.g.
> > > something like pt_page.

How about sept_pt?

---

## [102] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Thu, Feb 05, 2026 at 02:33:16PM -0800, Sean Christopherson wrote:
> On Thu, Feb 05, 2026, Yan Zhao wrote:
> > On Wed, Feb 04, 2026 at 06:23:38PM -0800, Sean Christopherson wrote:
Hmm, I can't agree with that. But I won't insist if you think it's ok :)


> > Relying on this check is tricky and confusing.
> 
Ok.

> > > And then later on, when S-EPT gains support for hugepages, "KVM: TDX: Add core
> > > support for splitting/demoting 2MiB S-EPT to 4KiB" doesn't need to touch code
WIP. Found some issues. Will comment after investigating further.

> > but plumbing here directly for splitting does not look right when it's
> > invoked under shared mmu_lock.
My concern is that handle_changed_spte() can be invoked by callers other than
tdp_mmu_set_spte(). e.g.,

tdp_mmu_set_spte_atomic
  | __tdp_mmu_set_spte_atomic
  |     | kvm_x86_call(set_external_spte)
  | handle_changed_spte
        | kvm_x86_call(set_external_spte)

When !is_frozen_spte(new_spte) and was_leaf, set_external_spte() may be invoked
twice for splitting under shared mmu_lock.

Therefore, I think it would be better to check for !shared and only invoke
set_external_spte() when !shared.

BTW: in the patch log, you mentioned that

: Invoke .remove_external_spte() in handle_changed_spte() as appropriate
: instead of relying on callers to do the right thing.  Relying on callers
: to invoke .remove_external_spte() is confusing and brittle, e.g. subtly
: relies tdp_mmu_set_spte_atomic() never removing SPTEs, and removing an
: S-EPT entry in tdp_mmu_set_spte() is bizarre (yeah, the VM is bugged so
: it doesn't matter in practice, but it's still weird).

However, when tdp_mmu_set_spte_atomic() removes SPTEs in the future, it will
still need to follow the sequence in __tdp_mmu_set_spte_atomic() :
1. freeze, 2. set_external_spte(). 3. set the new_spte 4. handle_changed_spte().

So, do you think we should leave set_external_spte() in tdp_mmu_set_spte() for
exclusive mmu_lock scenarios instead of moving it to handle_changed_spte()?

> at some point we have to commit to getting the code right.  Adding KVM_BUG_ON() in
> Every. Single. Call. does not yield more maintainable code.  There are myriad
Thanks for sharing this bar.

---

## [103] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop
 kvm_x86_ops.link_external_spt(), use .set_external_spte() for all*

On Thu, Feb 05, 2026 at 03:14:29PM -0800, Sean Christopherson wrote:
> On Wed, Feb 04, 2026, Yan Zhao wrote:
> > On Tue, Feb 03, 2026 at 08:05:05PM +0000, Sean Christopherson wrote:

Ok. I was wondering why we don't include it directly in this patch, but it
doesn't matter.

> > > > And as Rick also mentioned, better to remove external in external_spt, e.g.
> > > > something like pt_page.
LGTM.

---

## [104] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 06/45] KVM: x86/mmu: Fold
 set_external_spte_present() into its sole caller*

> > > -		ret = set_external_spte_present(kvm, iter->sptep, iter->gfn,
> > > -						&iter->old_spte, new_spte, iter->level);
LGTM.

---

## [105] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 09/45] KVM: x86: Rework .free_external_spt() into
 .reclaim_external_sp()*

On Thu, Feb 05, 2026 at 02:38:08PM -0800, Sean Christopherson wrote:
> On Thu, Feb 05, 2026, Yan Zhao wrote:
> > On Wed, Feb 04, 2026 at 05:45:39PM +0800, Yan Zhao wrote:
Ok. reclaim_external_spt() looks good to me.

---

## [106] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On Thu, Feb 05, 2026 at 02:35:25PM -0800, Sean Christopherson wrote:
> On Thu, Feb 05, 2026, Yan Zhao wrote:
> > > diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
"WARN_ON_ONCE() and return 0" looks good to me.

> > > +	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
> > > +}

---

## [107] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

> diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
> index 18764dbc97ea..01e3e4f4baa5 100644
Strictly speaking, external_spt is not a control page. Its alloc/free are
different from normal control pages managed by TDX's code.

(1) alloc
tdx_alloc_control_page
  __tdx_alloc_control_page
    __tdx_pamt_get 
      spin_lock(&pamt_lock)   ==> under process context
      spin_unlock(&pamt_lock)

(2) free
tdp_mmu_free_sp_rcu_callback
  tdp_mmu_free_sp
    kvm_x86_call(free_external_sp)
     tdx_free_control_page
        __tdx_free_control_page
          __tdx_pamt_put
            spin_lock(&pamt_lock)   ==> under softirq context
            spin_unlock(&pamt_lock)

So, invoking __tdx_pamt_put() in the RCU callback triggers deadlock warning
(see the bottom for details).

> +	/*
> +	 * TDX uses the external_spt cache to allocate S-EPT page table pages,

 ================================
 WARNING: inconsistent lock state
 6.19.0-rc6-upstream+ #1078 Tainted: G S   U
 --------------------------------
 inconsistent {SOFTIRQ-ON-W} -> {IN-SOFTIRQ-W} usage.
 swapper/7/0 [HC0[0]:SC1[1]:HE1:SE0] takes:
 ffffffff9067b6f8 (pamt_lock){+.?.}-{3:3}, at: __tdx_pamt_put+0x80/0xf0
 {SOFTIRQ-ON-W} state was registered at:
   __lock_acquire+0x405/0xc10
   lock_acquire.part.0+0x9c/0x210
   lock_acquire+0x5e/0x100
   _raw_spin_lock+0x37/0x80
   __tdx_pamt_get+0xb8/0x150
   __tdx_alloc_control_page+0x2e/0x60
   __tdx_td_init+0x65/0x740 [kvm_intel]
   tdx_td_init+0x147/0x240 [kvm_intel]
   tdx_vm_ioctl+0x125/0x260 [kvm_intel]
   vt_mem_enc_ioctl+0x17/0x30 [kvm_intel]
   kvm_arch_vm_ioctl+0x4e0/0xb40 [kvm]
   kvm_vm_ioctl+0x4f4/0xaf0 [kvm]
   __x64_sys_ioctl+0x9d/0xf0
   x64_sys_call+0xf38/0x1da0
   do_syscall_64+0xc5/0xfc0
   entry_SYSCALL_64_after_hwframe+0x77/0x7f
 irq event stamp: 252814
 hardirqs last  enabled at (252814): [<ffffffff8fa6f41a>] _raw_spin_unlock_irqrestore+0x5a/0x80
 hardirqs last disabled at (252813): [<ffffffff8fa6f096>] _raw_spin_lock_irqsave+0x76/0x90
 softirqs last  enabled at (252798): [<ffffffff8e60f139>] handle_softirqs+0x309/0x460
 softirqs last disabled at (252805): [<ffffffff8e60f401>] __irq_exit_rcu+0xe1/0x160

 other info that might help us debug this:
  Possible unsafe locking scenario:

        CPU0
        ----
   lock(pamt_lock);
   <Interrupt>
     lock(pamt_lock);

  *** DEADLOCK ***

 1 lock held by swapper/7/0:
  #0: ffffffff9077d660 (rcu_callback){....}-{0:0}, at: rcu_do_batch+0x153/0x620

 stack backtrace:
 CPU: 7 UID: 0 PID: 0 Comm: swapper/7 Tainted: G S   U              6.19.0-rc6-upstream+ #1078 PREEMPT(voluntary)  b8f4b38003dc2ca73352cf9d3d544aa826c4f5a9
 Tainted: [S]=CPU_OUT_OF_SPEC, [U]=USER
 Hardware name: Intel Corporation ArcherCity/ArcherCity, BIOS EGSDCRB1.SYS.0101.D29.2303301937 03/30/2023
 Call Trace:
  <IRQ>
  show_stack+0x49/0x60
  dump_stack_lvl+0x6f/0xb0
  dump_stack+0x10/0x16
  print_usage_bug.part.0+0x264/0x350
  mark_lock_irq+0x4d6/0x9e0
  ? stack_trace_save+0x4a/0x70
  ? save_trace+0x66/0x2b0
  mark_lock+0x1cf/0x6a0
  mark_usage+0x4c/0x130
  __lock_acquire+0x405/0xc10
  ? __this_cpu_preempt_check+0x13/0x20
  lock_acquire.part.0+0x9c/0x210
  ? __tdx_pamt_put+0x80/0xf0
  lock_acquire+0x5e/0x100
  ? __tdx_pamt_put+0x80/0xf0
  _raw_spin_lock+0x37/0x80
  ? __tdx_pamt_put+0x80/0xf0
  __tdx_pamt_put+0x80/0xf0
  ? __this_cpu_preempt_check+0x13/0x20
  ? sched_clock_noinstr+0x9/0x10
  __tdx_free_control_page+0x22/0x40
  tdx_free_control_page+0x38/0x50 [kvm_intel c135d3571385e160f086f9f6195fc72e4b6aa2b1]
  tdp_mmu_free_sp_rcu_callback+0x24/0x50 [kvm 3932b137c28c130169e7e3615041bcec6cefc090]
  ? rcu_do_batch+0x1dc/0x620
  rcu_do_batch+0x1e1/0x620
  ? rcu_do_batch+0x153/0x620
  rcu_core+0x37d/0x4d0
  rcu_core_si+0xe/0x20
  handle_softirqs+0xdc/0x460
  ? hrtimer_interrupt+0x154/0x290
  __irq_exit_rcu+0xe1/0x160
  irq_exit_rcu+0xe/0x30
  sysvec_apic_timer_interrupt+0xc0/0xf0
  </IRQ>
  <TASK>
  asm_sysvec_apic_timer_interrupt+0x1b/0x20
 RIP: 0010:cpuidle_enter_state+0x122/0x7a0

---

## [108] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 37/45] KVM: x86/tdp_mmu: Alloc external_spt page
 for mirror page table splitting*

On Wed, Jan 28, 2026 at 05:15:09PM -0800, Sean Christopherson wrote:
> From: Isaku Yamahata <isaku.yamahata@intel.com>
> 
tdp_mmu_alloc_sp_for_split() is invoked in tdp_mmu_split_huge_pages_root() after
rcu_read_unlock() is called.

So, it's incorrect to invoke is_mirror_sptep() which internally contains
rcu_dereference(), resulting in "WARNING: suspicious RCU usage".

> +		sp->external_spt = (void *)kvm_x86_call(alloc_external_sp)(GFP_KERNEL_ACCOUNT);
> +		if (!sp->external_spt) {

---

## [109] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 44/45] KVM: x86/mmu: Add support for splitting
 S-EPT hugepages on conversion*

On Wed, Jan 28, 2026 at 05:15:16PM -0800, Sean Christopherson wrote:
> Add support for splitting S-EPT hugepages in preparation for converting a
> subset of a hugepage to be shared, as KVM must precisely zap/remove S-EPT
Missing "spin_lock_init(&kvm->arch.tdp_mmu_external_cache_lock);" in
kvm_mmu_init_tdp_mmu().

Will check the patch you replied next week.

>  #endif /* CONFIG_X86_64 */

---

## [110] Yan Zhao — 2026-02-06
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Wed, Jan 28, 2026 at 05:14:54PM -0800, Sean Christopherson wrote:
> From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> 
If this external cache is for PAMT pages allocation for guest pages only, here
the min count should be 1 instead of PT64_ROOT_MAX_LEVEL?


> +		if (r)
> +			return r;
...
>  void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
> @@ -3614,5 +3641,12 @@ void __init tdx_hardware_setup(void)

---

## [111] Sean Christopherson — 2026-02-06
*Subject: Re: [RFC PATCH v5 44/45] KVM: x86/mmu: Add support for splitting
 S-EPT hugepages on conversion*

On Fri, Feb 06, 2026, Yan Zhao wrote:
> On Wed, Jan 28, 2026 at 05:15:16PM -0800, Sean Christopherson wrote:
> > Add support for splitting S-EPT hugepages in preparation for converting a

It has the same bug.  FWIW, I found and fixed the bug on our internal branch, but I
either missed the fixup when synchronizing back to the upstream branch, or I found
the issue after posting.

@@ -634,6 +642,7 @@ int tdx_vm_init(struct kvm *kvm)
        struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
        tdx_init_pamt_cache(&kvm_tdx->pamt_cache);
+       mutex_init(&kvm_tdx->pamt_cache_lock);
 
        kvm->arch.has_protected_state = true;
        /*

---

## [112] Sean Christopherson — 2026-02-06
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Fri, Feb 06, 2026, Yan Zhao wrote:
> > diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
> > index 18764dbc97ea..01e3e4f4baa5 100644

Yeah, I called that out in the changelog.  I'm definitley not wedded to
tdx_{alloc,free}_control_page(), but I am very much against tdx_{alloc,free}_page().

  (arguably S-EPT pages aren't "control" pages, but they're not guest pages either)

> (1) alloc
> tdx_alloc_control_page

Hrm.  I can think of two options.  Option #1 would be to use a raw spinlock and
disable IRQs:

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 823ec092b4e4..6348085d7dcb 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2246,7 +2246,7 @@ static u64 tdh_phymem_pamt_remove(u64 pfn, u64 *pamt_pa_array)
 }
 
 /* Serializes adding/removing PAMT memory */
-static DEFINE_SPINLOCK(pamt_lock);
+static DEFINE_RAW_SPINLOCK(pamt_lock);
 
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
 int __tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache)
@@ -2272,7 +2272,7 @@ int __tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache)
        if (ret)
                goto out_free;
 
-       scoped_guard(spinlock, &pamt_lock) {
+       scoped_guard(raw_spinlock_irqsave, &pamt_lock) {
                /*
                 * Lost race to other tdx_pamt_add(). Other task has already allocated
                 * PAMT memory for the HPA.
@@ -2348,7 +2348,7 @@ void __tdx_pamt_put(u64 pfn)
        if (!atomic_dec_and_test(pamt_refcount))
                return;
 
-       scoped_guard(spinlock, &pamt_lock) {
+       scoped_guard(raw_spinlock_irqsave, &pamt_lock) {
                /* Lost race with tdx_pamt_get(). */
                if (atomic_read(pamt_refcount))
                        return;

--

Option #2 would be to immediately free the page in tdx_sept_reclaim_private_sp(),
so that pages that freed via handle_removed_pt() don't defer freeing the S-EPT
page table (which, IIUC, is safe since the TDX-Module forces TLB flushes and exits).

I really, really don't like this option (if it even works).

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ae7b9beb3249..4726011ad624 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2014,7 +2014,15 @@ static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
         */
        if (KVM_BUG_ON(is_hkid_assigned(to_kvm_tdx(kvm)), kvm) ||
            tdx_reclaim_page(virt_to_page(sp->external_spt)))
-               sp->external_spt = NULL;
+               goto out;
+
+       /*
+        * Immediately free the control page, as the TDX subsystem doesn't
+        * support freeing pages from RCU callbacks.
+        */
+       tdx_free_control_page((unsigned long)sp->external_spt);
+out:
+       sp->external_spt = NULL;
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
--

---

## [113] Sean Christopherson — 2026-02-06
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Fri, Feb 06, 2026, Yan Zhao wrote:
> On Wed, Jan 28, 2026 at 05:14:54PM -0800, Sean Christopherson wrote:
> > diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h

Oh!  Right.  Hmm, with that in mind, it seems like topup_external_cache() isn't
quite the right interace.  It's not at all clear that, unlike the other caches,
the DPAMT cache isn't tied to the page tables, it's tied to the physical memory
being mapped into the guest.

At the very least, it seems like we should drop the @min parameter?

	int (*topup_external_cache)(struct kvm *kvm, struct kvm_vcpu *vcpu);

Though if someone has a name that better captures what the cache is used for,
without bleeding too many details into common x86...

---

## [114] Sean Christopherson — 2026-02-06
*Subject: Re: [RFC PATCH v5 37/45] KVM: x86/tdp_mmu: Alloc external_spt page
 for mirror page table splitting*

On Fri, Feb 06, 2026, Yan Zhao wrote:
> On Wed, Jan 28, 2026 at 05:15:09PM -0800, Sean Christopherson wrote:
> > From: Isaku Yamahata <isaku.yamahata@intel.com>

Ah, now I see why the previous code pass in a bool.  I don't love passing a bool,
but passing @iter is outright dangerous, so I guess this?

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index a32192c35099..4d92c0d19d7c 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1448,7 +1448,7 @@ bool kvm_tdp_mmu_wrprot_slot(struct kvm *kvm,
 }
 
 static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
-                                                      struct tdp_iter *iter)
+                                                      bool is_mirror_sp)
 {
        struct kvm_mmu_page *sp;
 
@@ -1460,7 +1460,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
        if (!sp->spt)
                goto err_spt;
 
-       if (is_mirror_sptep(iter->sptep)) {
+       if (is_mirror_sp) {
                sp->external_spt = (void *)kvm_x86_call(alloc_external_sp)(GFP_KERNEL_ACCOUNT);
                if (!sp->external_spt)
                        goto err_external_spt;
@@ -1525,6 +1525,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
                                         gfn_t start, gfn_t end,
                                         int target_level, bool shared)
 {
+       const bool is_mirror_root = is_mirror_sp(root);
        struct kvm_mmu_page *sp = NULL;
        struct tdp_iter iter;
 
@@ -1557,7 +1558,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
                        else
                                write_unlock(&kvm->mmu_lock);
 
-                       sp = tdp_mmu_alloc_sp_for_split(kvm, &iter);
+                       sp = tdp_mmu_alloc_sp_for_split(kvm, is_mirror_root);
 
                        if (shared)
                                read_lock(&kvm->mmu_lock);

---

## [115] Sean Christopherson — 2026-02-06
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Fri, Feb 06, 2026, Yan Zhao wrote:
> On Thu, Feb 05, 2026 at 02:33:16PM -0800, Sean Christopherson wrote:
> > On Thu, Feb 05, 2026, Yan Zhao wrote:

If the code is read through a TDX lens, then I agree, it's seems wrong.  Because
then you *know* that TDX doesn't support back-to-back remove()=>add() operations
to handle a page split.

But from a TDP MMU perspective, this is entirely logical (ignoring that
link_external_spt() is gone at this point in the series).

	else if (was_leaf && is_mirror_sptep(sptep) && !is_leaf) {
		kvm_x86_call(remove_external_spte)(kvm, gfn, level, old_spte);

		/*
		 * Link the new page table if a hugepage is being split, i.e.
		 * if a leaf SPTE is being replaced with a non-leaf SPTE.
		 */
		if (is_present)
			kvm_x86_call(link_external_spt)(kvm, gfn, level, ...);
	}

And that is *exactly* why I want to get rid of the hyper-specific kvm_x86_ops
hooks.  They bleed all kinds of implementation details all over the TDP MMU, which
makes it difficult to read and understand the relevant TDP MMU code if you don't
already know the TDX rules.  And I absolutely do not want to effectively require
others to understand TDX's rules to be able to make changes to the TDP MMU.

> > > Relying on the TDX code's lockdep_assert_held_write() for warning seems less
> > > clear than having an explicit check here.

But we don't support that yet.  I was going to punt dealing with that to the future,
but now that I've looked at it, I honestly think the problem is that I didn't go
far enough with the cleanup.  I shouldn't have hedged.

What I said in "KVM: TDX: Drop kvm_x86_ops.link_external_spt(), use .set_external_spte()
for all":

 : Ideally, KVM would provide a single pair of hooks to set S-EPT entries,
 : one hook for setting SPTEs under write-lock and another for settings SPTEs
 : under read-lock (e.g. to ensure the entire operation is "atomic", to allow
 : for failure, etc.).  Sadly, TDX's requirement that all child S-EPT entries
 : are removed before the parent makes that impractical: the TDP MMU
 : deliberately prunes non-leaf SPTEs and _then_ processes its children, thus
 : making it quite important for the TDP MMU to differentiate between zapping
 : leaf and non-leaf S-EPT entries.

isn't quite right.  Ideally, KVM would provide *one* hook to set S-EPT entries.
Because the API to actually *set* the external SPTE shouldn't be any different
for read-lock vs. write-lost.  I.e. the child S-EPT case remains the sole
exception.  More below.

> Therefore, I think it would be better to check for !shared and only invoke
> set_external_spte() when !shared.

No.  I am dead set against conditionally invoking set_external_spte() based on
shared vs. exclusive.  The rules for how SPTE updates are forwarded to TDX, and
how TDX reacts to those updates, need to be defined purely on state transitions,
i.e. on old_spte vs. new_spte.

Actually, even that isn't a strong enough statement.  *All* updates need to be
forwarded to TDX, and then TDX can react as appropriate.

> BTW: in the patch log, you mentioned that
> 

Nope, as above, 100% the opposite.  Over ~3 patches, e.g.

 1. Drop the KVM_BUG_ON()s or move them to TDX
 2. Morph the !is_frozen_spte() check into a KVM_MMU_WARN_ON()
 3. Rework the code to rely on __handle_changed_spte() to propagate writes to S-EPT

That way, the _only_ path that updates external SPTEs is this:

	if (was_present && !was_leaf &&
	    (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed)))
		handle_removed_pt(kvm, spte_to_child_pt(old_spte, level), shared);
	else if (is_mirror_sptep(sptep))
		return kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
						       new_spte, level);

which is fully aligned with handle_changed_spte()'s role for !mirror roots: it
exists to react to changes (the sole exception to that being aging SPTEs, which
is a special case).

Compile-tested only.

---
 arch/x86/kvm/mmu/tdp_mmu.c | 118 ++++++++++++++++++-------------------
 1 file changed, 59 insertions(+), 59 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 847f2fcb6740..33a321aedac0 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -464,7 +464,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 }
 
 /**
- * handle_changed_spte - handle bookkeeping associated with an SPTE change
+ * __handle_changed_spte - handle bookkeeping associated with an SPTE change
  * @kvm: kvm instance
  * @as_id: the address space of the paging structure the SPTE was a part of
  * @sptep: pointer to the SPTE
@@ -480,9 +480,9 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
  * dirty logging updates are handled in common code, not here (see make_spte()
  * and fast_pf_fix_direct_spte()).
  */
-static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
-				gfn_t gfn, u64 old_spte, u64 new_spte,
-				int level, bool shared)
+static int __handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
+				 gfn_t gfn, u64 old_spte, u64 new_spte,
+				 int level, bool shared)
 {
 	bool was_present = is_shadow_present_pte(old_spte);
 	bool is_present = is_shadow_present_pte(new_spte);
@@ -518,7 +518,7 @@ static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 	}
 
 	if (old_spte == new_spte)
-		return;
+		return 0;
 
 	trace_kvm_tdp_mmu_spte_changed(as_id, gfn, level, old_spte, new_spte);
 
@@ -547,7 +547,7 @@ static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 			       "a temporary frozen SPTE.\n"
 			       "as_id: %d gfn: %llx old_spte: %llx new_spte: %llx level: %d",
 			       as_id, gfn, old_spte, new_spte, level);
-		return;
+		return 0;
 	}
 
 	if (is_leaf != was_leaf)
@@ -559,30 +559,31 @@ static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 	 * SPTE being converted to a hugepage (leaf) or being zapped.  Shadow
 	 * pages are kernel allocations and should never be migrated.
 	 *
-	 * When modifying leaf entries in mirrored page tables, propagate the
-	 * changes to the external SPTE.  Bug the VM on failure, as callers
-	 * aren't prepared to handle errors, e.g. due to lock contention in the
-	 * TDX-Module.  Note, changes to non-leaf mirror SPTEs are handled by
-	 * handle_removed_pt() (the TDX-Module requires that child entries are
-	 * removed before the parent SPTE), and changes to non-present mirror
-	 * SPTEs are handled by __tdp_mmu_set_spte_atomic() (KVM needs to set
-	 * the external SPTE while the mirror SPTE is frozen so that installing
-	 * a new SPTE is effectively an atomic operation).
+	 * When modifying leaf entries in mirrored page tables, propagate all
+	 * changes to the external SPTE.
 	 */
 	if (was_present && !was_leaf &&
 	    (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed)))
 		handle_removed_pt(kvm, spte_to_child_pt(old_spte, level), shared);
-	else if (was_leaf && is_mirror_sptep(sptep))
-		KVM_BUG_ON(kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
-							   new_spte, level), kvm);
+	else if (is_mirror_sptep(sptep))
+		return kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
+						       new_spte, level);
+
+	return 0;
+}
+
+static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
+				gfn_t gfn, u64 old_spte, u64 new_spte,
+				int level, bool shared)
+{
+	KVM_BUG_ON(__handle_changed_spte(kvm, as_id, sptep, gfn, old_spte,
+					 new_spte, level, shared), kvm);
 }
 
 static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
 							 struct tdp_iter *iter,
 							 u64 new_spte)
 {
-	u64 *raw_sptep = rcu_dereference(iter->sptep);
-
 	/*
 	 * The caller is responsible for ensuring the old SPTE is not a FROZEN
 	 * SPTE.  KVM should never attempt to zap or manipulate a FROZEN SPTE,
@@ -591,40 +592,6 @@ static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
 	 */
 	WARN_ON_ONCE(iter->yielded || is_frozen_spte(iter->old_spte));
 
-	if (is_mirror_sptep(iter->sptep) && !is_frozen_spte(new_spte)) {
-		int ret;
-
-		/*
-		 * KVM doesn't currently support zapping or splitting mirror
-		 * SPTEs while holding mmu_lock for read.
-		 */
-		if (KVM_BUG_ON(is_shadow_present_pte(iter->old_spte), kvm) ||
-		    KVM_BUG_ON(!is_shadow_present_pte(new_spte), kvm))
-			return -EBUSY;
-
-		/*
-		 * Temporarily freeze the SPTE until the external PTE operation
-		 * has completed, e.g. so that concurrent faults don't attempt
-		 * to install a child PTE in the external page table before the
-		 * parent PTE has been written.
-		 */
-		if (!try_cmpxchg64(raw_sptep, &iter->old_spte, FROZEN_SPTE))
-			return -EBUSY;
-
-		/*
-		 * Update the external PTE.  On success, set the mirror SPTE to
-		 * the desired value.  On failure, restore the old SPTE so that
-		 * the SPTE isn't frozen in perpetuity.
-		 */
-		ret = kvm_x86_call(set_external_spte)(kvm, iter->gfn, iter->old_spte,
-						      new_spte, iter->level);
-		if (ret)
-			__kvm_tdp_mmu_write_spte(iter->sptep, iter->old_spte);
-		else
-			__kvm_tdp_mmu_write_spte(iter->sptep, new_spte);
-		return ret;
-	}
-
 	/*
 	 * Note, fast_pf_fix_direct_spte() can also modify TDP MMU SPTEs and
 	 * does not hold the mmu_lock.  On failure, i.e. if a different logical
@@ -632,7 +599,7 @@ static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
 	 * the current value, so the caller operates on fresh data, e.g. if it
 	 * retries tdp_mmu_set_spte_atomic()
 	 */
-	if (!try_cmpxchg64(raw_sptep, &iter->old_spte, new_spte))
+	if (!try_cmpxchg64(rcu_dereference(iter->sptep), &iter->old_spte, new_spte))
 		return -EBUSY;
 
 	return 0;
@@ -663,14 +630,44 @@ static inline int __must_check tdp_mmu_set_spte_atomic(struct kvm *kvm,
 
 	lockdep_assert_held_read(&kvm->mmu_lock);
 
-	ret = __tdp_mmu_set_spte_atomic(kvm, iter, new_spte);
+	/* KVM should never freeze SPTEs using higher level APIs. */
+	KVM_MMU_WARN_ON(is_frozen_spte(new_spte));
+
+	/*
+	  * Temporarily freeze the SPTE until the external PTE operation has
+	  * completed (unless the new SPTE itself will be frozen), e.g. so that
+	  * concurrent faults don't attempt to install a child PTE in the
+	  * external page table before the parent PTE has been written, or try
+	  * to re-install a page table before the old one was removed.
+	  */
+	if (is_mirror_sptep(iter->sptep))
+		ret = __tdp_mmu_set_spte_atomic(kvm, iter, FROZEN_SPTE);
+	else
+		ret = __tdp_mmu_set_spte_atomic(kvm, iter, new_spte);
 	if (ret)
 		return ret;
 
-	handle_changed_spte(kvm, iter->as_id, iter->sptep, iter->gfn,
-			    iter->old_spte, new_spte, iter->level, true);
+	ret = __handle_changed_spte(kvm, iter->as_id, iter->sptep, iter->gfn,
+				    iter->old_spte, new_spte, iter->level, true);
 
-	return 0;
+	/*
+	 * Unfreeze the mirror SPTE.  If updating the external SPTE failed,
+	 * restore the old SPTE so that the SPTE isn't frozen in perpetuity,
+	 * otherwise set the mirror SPTE to the new desired value.
+	 */
+	if (is_mirror_sptep(iter->sptep)) {
+		if (ret)
+			__kvm_tdp_mmu_write_spte(iter->sptep, iter->old_spte);
+		else
+			__kvm_tdp_mmu_write_spte(iter->sptep, new_spte);
+	} else {
+		/*
+		 * Bug the VM if handling the change failed, as failure is only
+		 * allowed if KVM couldn't update the external SPTE.
+		 */
+		KVM_BUG_ON(ret, kvm);
+	}
+	return ret;
 }
 
 /*
@@ -1325,6 +1322,9 @@ static void kvm_tdp_mmu_age_spte(struct kvm *kvm, struct tdp_iter *iter)
 {
 	u64 new_spte;
 
+	if (WARN_ON_ONCE(is_mirror_sptep(iter->sptep)))
+		return;
+
 	if (spte_ad_enabled(iter->old_spte)) {
 		iter->old_spte = tdp_mmu_clear_spte_bits_atomic(iter->sptep,
 								shadow_accessed_mask);

base-commit: c86be62d601ede14cbad1d0fb5af9b67d4172342
--

---

## [116] Edgecombe, Rick P — 2026-02-06
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Fri, 2026-02-06 at 08:03 -0800, Sean Christopherson wrote:
> > If this external cache is for PAMT pages allocation for guest pages only,
> > here

From the TDX perspective we have 4 types of pages that are needed to service
faults:
1. "Control pages" (i.e. external page tables themselves)
2. Private guest memory pages
3. DPAMT backing pages for control pages
4. DPAMT backing pages for private pages

(3) is totally hidden now, but we need a hook to allocate (4). But from core
MMU's perspective we hide the existence of DPAMT backing pages. So we don't want
to leak that concept.

The page we need is kind of like something to "prepare" the private page before
installing it. It actually isn't that related to the mirror/external concept. So
if we separate it from "external" and make it about installing private guest
memory, it fits better conceptually I think. But it could be a bit confusing for
other types of VMs who have to trace to see if anything special is happening
inside the op for their private memory. In that case it could be:

(*topup_private_mem_prepare_cache)(struct kvm_vcpu *vcpu)


The core MMU doesn't know about DPAMT backing pages, but it does know about the
set_external_spte op that consumes this cache. So how about the slightly
misleading:

(*topup_set_external_spte_cache)(struct kvm_vcpu *vcpu)


It is easier for other VM types to ignore, and not that semantically wrong from
what is happening on the TDX side.

---

## [117] Sean Christopherson — 2026-02-06
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Fri, Feb 06, 2026, Rick P Edgecombe wrote:
> On Fri, 2026-02-06 at 08:03 -0800, Sean Christopherson wrote:
> > > If this external cache is for PAMT pages allocation for guest pages only,

Heh, there is no way around that.  Common KVM needs to know that the cache is
tied to mapping a page into the guest, otherwise the parameters don't make any
sense whatsoever.  All we can do is minimize the bleeding.

> The page we need is kind of like something to "prepare" the private page before
> installing it. It actually isn't that related to the mirror/external concept. So

topup + prepare is redundant and confusing.

> The core MMU doesn't know about DPAMT backing pages, but it does know about the
> set_external_spte op that consumes this cache. So how about the slightly

I really, really, want to avoid "SPTE", because the cache isn't for the SPTE in
any way, it's for the memory that's _pointed_ at by the SPTE.  And the confusion
is exactly what prompted this thread: I forgot that it's not every SPTE in the
chain that needs DPAMT backing, it's only the page that's being mapped into the
guest.

How about?

  (*topup_private_mapping_cache)

Because it's not just "private memory" it's specifically the mapping.  E.g. for
the hugepage split case, the primary memory is already assigned and mapped into
the guest, but a topup is still needed because KVM is creating a new/different
mapping.

> It is easier for other VM types to ignore, and not that semantically wrong from
> what is happening on the TDX side.

---

## [118] Edgecombe, Rick P — 2026-02-06
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Fri, 2026-02-06 at 15:18 -0800, Sean Christopherson wrote:
> How about?
> 

Sure.

---

## [119] Yan Zhao — 2026-02-09
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Fri, Feb 06, 2026 at 07:01:14AM -0800, Sean Christopherson wrote:
> > (1) alloc
> > tdx_alloc_control_page

This option can get rid of the warning.

However, given the pamt_lock is a global lock, which may be acquired even in the
softirq context, not sure if this irq disabled version is good.

For your reference, I measured some test data by concurrently launching and
destroying 4 TDs for 3 rounds:

                               t0 ---------------------
scoped_guard(spinlock, &pamt_lock) {       |->T1=t1-t0 |
                               t1 ----------           |
 ...                                                   |
                               t2 ----------           |->T3=t4-t0
 tdh_phymem_pamt_add/remove()              |->T2=t3-t2 |
                               t3 ----------           |
 ...                                                   |
                               t4 ---------------------
}

(1) for __tdx_pamt_get()

       avg us   min us   max us
------|---------------------------
  T1  |   4       0       69
  T2  |   4       2       18
  T3  |  10       3       83


(2) for__tdx_pamt_put()

       avg us   min us   max us
------|---------------------------
  T1  |   0        0       5
  T2  |   2        1      11
  T3  |   3        2      15

 
> Option #2 would be to immediately free the page in tdx_sept_reclaim_private_sp(),
> so that pages that freed via handle_removed_pt() don't defer freeing the S-EPT
I don't like its asymmetry with tdx_sept_link_private_spt().

However, do you think it would be good to have the PAMT pages of the sept pages
allocated from (*topup_private_mapping_cache) [1]?

private_mapping could also include non-leaf mappings.
So, we could invoke tdx_pamt_get() in tdx_sept_link_private_spt() for symmetry.

[1] https://lore.kernel.org/all/aYZ2qft-akOYwkOk@google.com/
> diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
> index ae7b9beb3249..4726011ad624 100644

---

## [120] Huang, Kai — 2026-02-09
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Fri, 2026-02-06 at 15:18 -0800, Sean Christopherson wrote:
> On Fri, Feb 06, 2026, Rick P Edgecombe wrote:
> > On Fri, 2026-02-06 at 08:03 -0800, Sean Christopherson wrote:

Actually, maybe we can even get rid of the DPAMT cache for the actual
private pages w/o introducing new field to 'kvm_mmu_page':

The point is:

  Once we know the PFN and the actual mapping level, we can know whether we
  need DPAMT pages for that PFN.  If we can know outside of MMU lock, then
  we can call tdx_pamt_get(PFN) directly w/o needing the "cache".

In the fault path, we already know the PFN after kvm_mmu_faultin_pfn(),
which is outside of MMU lock.

What we still don't know is the actual mapping level, which is currently
done in kvm_tdp_mmu_map() via kvm_mmu_hugepage_adjust().

However I don't see why we cannot move kvm_mmu_hugepage_adjust() out of it
to, e.g., right after kvm_mmu_faultin_pfn()?

If we can do this, then AFAICT we can just do:

  r = kvm_x86_call(prepare_pfn)(vcpu, fault, pfn);

in which we can just call tdx_pamt_get(pfn) based on the mapping level?

Similar can be done for kvm_tdp_mmu_map_private_pfn() which already takes
the 'pfn' as parameter.

For the split path, we obviously can also know the 'pfn' from the huge SPTE.

I kinda do wish we could get rid of the new 'struct tdx_pamt_cache' pool if
possible.

Anything I missed?

---

## [121] Huang, Kai — 2026-02-09
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

> 
> Option #2 would be to immediately free the page in tdx_sept_reclaim_private_sp(),

I don't think this is so bad, given we already have a bunch of

	is_mirror_sp(sp)
		kvm_x86_call(xx_external_spt)(..);

in TDP MMU code?

I suppose this won't make a lot of difference, but does below make you
slightly happier?

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 3181406c5e0b..3588265098a8 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -55,8 +55,7 @@ void kvm_mmu_uninit_tdp_mmu(struct kvm *kvm)
 
 static void tdp_mmu_free_sp(struct kvm_mmu_page *sp)
 {
-       if (sp->external_spt)
-               kvm_x86_call(free_external_sp)((unsigned long)sp-
>external_spt);
+       WARN_ON_ONCE(sp->external_spt);
        free_page((unsigned long)sp->spt);
        kmem_cache_free(mmu_page_header_cache, sp);
 }
@@ -457,8 +456,17 @@ static void handle_removed_pt(struct kvm *kvm,
tdp_ptep_t pt, bool shared)
                                    old_spte, FROZEN_SPTE, level, shared);
        }
 
-       if (is_mirror_sp(sp))
+       if (is_mirror_sp(sp)) {
                kvm_x86_call(reclaim_external_sp)(kvm, base_gfn, sp);
+               /*
+                * Immediately free the control page, as the TDX subsystem
doesn't
+                * support freeing pages from RCU callbacks.
+                */
+               if (sp->external_spt) {
+                       kvm_x86_call(free_external_sp)((unsigned long)sp-
>external_spt);
+                       sp->external_spt = NULL;
+               }
+       }
 
        call_rcu(&sp->rcu_head, tdp_mmu_free_sp_rcu_callback);
 }

---

## [122] Edgecombe, Rick P — 2026-02-09
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Mon, 2026-02-09 at 10:33 +0000, Huang, Kai wrote:
> In the fault path, we already know the PFN after
> kvm_mmu_faultin_pfn(), which is outside of MMU lock.

What about the adjustments in disallowed_hugepage_adjust()?

---

## [123] Huang, Kai — 2026-02-09
*Subject: Re: [RFC PATCH v5 22/45] KVM: TDX: Get/put PAMT pages when
 (un)mapping private memory*

On Mon, 2026-02-09 at 17:08 +0000, Edgecombe, Rick P wrote:
> On Mon, 2026-02-09 at 10:33 +0000, Huang, Kai wrote:
> > In the fault path, we already know the PFN after

AFAICT that's for preventing replacing existing small leafs with a huge
mapping, which is not supported by TDX in this series (PROMOTE isn't
supported).

Even we want to support PROMOTE in the future, it doesn't impact the logic
that we don't need to call tdx_pamt_get(pfn) if the fault->goal_level is 2M.
When KVM tries to replace the existing small leafs with huge SPTE for TDX,
the PROMOTE returns the now-unneeded PAMT pages and KVM can just free that.

There's no impact to non-TDX case too, I believe, because moving
kvm_mmu_hugepage_adjust() out of kvm_tdp_mmu_map() only moves it out, but
doesn't change the whole logic.

---

## [124] Sean Christopherson — 2026-02-09
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Mon, Feb 09, 2026, Kai Huang wrote:
> > Option #2 would be to immediately free the page in tdx_sept_reclaim_private_sp(),
> > so that pages that freed via handle_removed_pt() don't defer freeing the S-EPT

Heh, slightly, but I still don't love it :-D

> diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
> index 3181406c5e0b..3588265098a8 100644

Doesn't work, because sp->external_spt will be non-NULL when KVM is freeing
unused pages in tdp_mmu_split_huge_pages_root() and kvm_tdp_mmu_map().  That's
solvable, but it's part of the asymmetry I don't love.  AFAICT, unless we do
something truly awful, there's no way to avoid having common KVM free unused
S-EPT pages.

That said, while I don't love the asymmetry, it's not a deal breaker, especially
if we make the asymmetry super obvious and cleanly delineated.  Specifically, if
we differentiate between freeing unused page tables and freeing used (linked at
any point) page tables.

This would also allow us to address the naming than Yan doesn't like around
reclaim_external_sp(), because we could have both free_external_sp() and
free_unused_external_spt(), where the lack of "unused" gives the reader a hint
that there's interesting work to be done for in-use external page tables.

This won't apply cleanly due to other fixups.  It's also at:

  https://github.com/sean-jc/linux.git x86/tdx_huge_sept

---
 arch/x86/include/asm/kvm-x86-ops.h |  8 ++++----
 arch/x86/include/asm/kvm_host.h    | 10 +++++-----
 arch/x86/kvm/mmu/mmu.c             |  4 ++--
 arch/x86/kvm/mmu/tdp_mmu.c         | 27 +++++++++++++++++----------
 arch/x86/kvm/vmx/tdx.c             | 22 +++++++++++++++-------
 5 files changed, 43 insertions(+), 28 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 87826176fa8d..9593d8d97f6b 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -94,11 +94,11 @@ KVM_X86_OP_OPTIONAL_RET0(set_tss_addr)
 KVM_X86_OP_OPTIONAL_RET0(set_identity_map_addr)
 KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
-KVM_X86_OP_OPTIONAL(alloc_external_sp)
-KVM_X86_OP_OPTIONAL(free_external_sp)
-KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
-KVM_X86_OP_OPTIONAL(reclaim_external_sp)
+KVM_X86_OP_OPTIONAL_RET0(alloc_external_spt)
+KVM_X86_OP_OPTIONAL(free_external_spt)
+KVM_X86_OP_OPTIONAL(free_unused_external_spt)
 KVM_X86_OP_OPTIONAL_RET0(topup_private_mapping_cache)
+KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 7ff72c04d575..5fc25508548b 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1855,13 +1855,13 @@ struct kvm_x86_ops {
 	 * and to propagate changes in mirror page tables to the external page
 	 * tables.
 	 */
-	unsigned long (*alloc_external_sp)(gfp_t gfp);
-	void (*free_external_sp)(unsigned long addr);
+	unsigned long (*alloc_external_spt)(gfp_t gfp);
+	void (*free_external_spt)(struct kvm *kvm, gfn_t gfn,
+				  struct kvm_mmu_page *sp);
+	void (*free_unused_external_spt)(unsigned long external_spt);
+	int (*topup_private_mapping_cache)(struct kvm *kvm, struct kvm_vcpu *vcpu);
 	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				 u64 new_spte, enum pg_level level);
-	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
-				    struct kvm_mmu_page *sp);
-	int (*topup_private_mapping_cache)(struct kvm *kvm, struct kvm_vcpu *vcpu);
 
 	bool (*has_wbinvd_exit)(void);
 
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 6a911aec075b..2ad417ac6e1f 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -6714,8 +6714,8 @@ int kvm_mmu_create(struct kvm_vcpu *vcpu)
 	if (!vcpu->arch.mmu_shadow_page_cache.init_value)
 		vcpu->arch.mmu_shadow_page_cache.gfp_zero = __GFP_ZERO;
 
-	vcpu->arch.mmu_external_spt_cache.page_get = kvm_x86_ops.alloc_external_sp;
-	vcpu->arch.mmu_external_spt_cache.page_free = kvm_x86_ops.free_external_sp;
+	vcpu->arch.mmu_external_spt_cache.page_get = kvm_x86_ops.alloc_external_spt;
+	vcpu->arch.mmu_external_spt_cache.page_free = kvm_x86_ops.free_unused_external_spt;
 
 	vcpu->arch.mmu = &vcpu->arch.root_mmu;
 	vcpu->arch.walk_mmu = &vcpu->arch.root_mmu;
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index b7c13316181b..d43db86b12a7 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -53,12 +53,18 @@ void kvm_mmu_uninit_tdp_mmu(struct kvm *kvm)
 	rcu_barrier();
 }
 
-static void tdp_mmu_free_sp(struct kvm_mmu_page *sp)
+static void __tdp_mmu_free_sp(struct kvm_mmu_page *sp)
+{
+	free_page((unsigned long)sp->spt);
+	kmem_cache_free(mmu_page_header_cache, sp);
+}
+
+static void tdp_mmu_free_unused_sp(struct kvm_mmu_page *sp)
 {
 	if (sp->external_spt)
-		kvm_x86_call(free_external_sp)((unsigned long)sp->external_spt);
-	free_page((unsigned long)sp->spt);
-	kmem_cache_free(mmu_page_header_cache, sp);
+		kvm_x86_call(free_unused_external_spt)((unsigned long)sp->external_spt);
+
+	__tdp_mmu_free_sp(sp);
 }
 
 /*
@@ -74,7 +80,8 @@ static void tdp_mmu_free_sp_rcu_callback(struct rcu_head *head)
 	struct kvm_mmu_page *sp = container_of(head, struct kvm_mmu_page,
 					       rcu_head);
 
-	tdp_mmu_free_sp(sp);
+	WARN_ON_ONCE(sp->external_spt);
+	__tdp_mmu_free_sp(sp);
 }
 
 void kvm_tdp_mmu_put_root(struct kvm *kvm, struct kvm_mmu_page *root)
@@ -458,7 +465,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 	}
 
 	if (is_mirror_sp(sp))
-		kvm_x86_call(reclaim_external_sp)(kvm, base_gfn, sp);
+		kvm_x86_call(free_external_spt)(kvm, base_gfn, sp);
 
 	call_rcu(&sp->rcu_head, tdp_mmu_free_sp_rcu_callback);
 }
@@ -1266,7 +1273,7 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 		 * failed, e.g. because a different task modified the SPTE.
 		 */
 		if (r) {
-			tdp_mmu_free_sp(sp);
+			tdp_mmu_free_unused_sp(sp);
 			goto retry;
 		}
 
@@ -1461,7 +1468,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
 		goto err_spt;
 
 	if (is_mirror_sp) {
-		sp->external_spt = (void *)kvm_x86_call(alloc_external_sp)(GFP_KERNEL_ACCOUNT);
+		sp->external_spt = (void *)kvm_x86_call(alloc_external_spt)(GFP_KERNEL_ACCOUNT);
 		if (!sp->external_spt)
 			goto err_external_spt;
 
@@ -1472,7 +1479,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
 	return sp;
 
 err_external_split:
-	kvm_x86_call(free_external_sp)((unsigned long)sp->external_spt);
+	kvm_x86_call(free_unused_external_spt)((unsigned long)sp->external_spt);
 err_external_spt:
 	free_page((unsigned long)sp->spt);
 err_spt:
@@ -1594,7 +1601,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
 	 * installs its own sp in place of the last sp we tried to split.
 	 */
 	if (sp)
-		tdp_mmu_free_sp(sp);
+		tdp_mmu_free_unused_sp(sp);
 
 	return 0;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 957fa59e9a65..aae7af26fe02 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1994,8 +1994,8 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 	return tdx_sept_map_leaf_spte(kvm, gfn, new_spte, level);
 }
 
-static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
-					struct kvm_mmu_page *sp)
+static void tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
+				      struct kvm_mmu_page *sp)
 {
 	/*
 	 * KVM doesn't (yet) zap page table pages in mirror page table while
@@ -2013,7 +2013,16 @@ static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
 	 */
 	if (KVM_BUG_ON(is_hkid_assigned(to_kvm_tdx(kvm)), kvm) ||
 	    tdx_reclaim_page(virt_to_page(sp->external_spt)))
-		sp->external_spt = NULL;
+		goto out;
+
+	/*
+	 * Immediately free the S-EPT page as the TDX subsystem doesn't support
+	 * freeing pages from RCU callbacks, and more importantly because
+	 * TDH.PHYMEM.PAGE.RECLAIM ensures there are no outstanding readers.
+	 */
+	tdx_free_control_page((unsigned long)sp->external_spt);
+out:
+	sp->external_spt = NULL;
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
@@ -3874,11 +3883,10 @@ void __init tdx_hardware_setup(void)
 	 * initialize the page (using the guest's encryption key), and (b) need
 	 * to use a custom allocator to be compatible with Dynamic PAMT.
 	 */
-	vt_x86_ops.alloc_external_sp = tdx_alloc_control_page;
-	vt_x86_ops.free_external_sp = tdx_free_control_page;
-
+	vt_x86_ops.alloc_external_spt = tdx_alloc_control_page;
+	vt_x86_ops.free_unused_external_spt = tdx_free_control_page;
+	vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
-	vt_x86_ops.reclaim_external_sp = tdx_sept_reclaim_private_sp;
 
 	vt_x86_ops.gmem_convert = tdx_gmem_convert;
 

base-commit: 0191132f233a66b5cb1ae9a09c18c6d6669c284a
--

---

## [125] Sean Christopherson — 2026-02-09
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Mon, Feb 09, 2026, Yan Zhao wrote:
> On Fri, Feb 06, 2026 at 07:01:14AM -0800, Sean Christopherson wrote:
> > @@ -2348,7 +2348,7 @@ void __tdx_pamt_put(u64 pfn)

FWIW, the SEAMCALL itself disables IRQs (and everything else), so it's not _that_
big of a change.  But yeah, waiting on the spinlock with IRQs disabled isn't
exactly idea.

> For your reference, I measured some test data by concurrently launching and
> destroying 4 TDs for 3 rounds:

Hrm, dunno about "good", but it's definitely not terrible.  To get the cache
management right, it means adding yet another use of kvm_get_running_vcpu(), which
I really dislike.

On the other hand, if we combine that with TDX freeing in-use S-EPT page tables,
unless I'm overly simplifying things, it would avoid having to extend
kvm_mmu_memory_cache with the page_{get,free}() hook, and would then eliminate
two kvm_x86_ops hooks, because the alloc/free of _unused_ S-EPT page tables is
no different than regular page tables.

As a bonus, we could keep the topup_external_cache() name and just clarify that
the parameter specifies the number of page table pages, i.e. account for the +1
for the mapping page in TDX code.

All in all, I'm kinda leaning in this direction, because as much as I dislike
kvm_get_running_vcpu(), it does minimize the number of kvm_x86_ops hooks.

Something like this?  Also pushed to 

  https://github.com/sean-jc/linux.git x86/tdx_huge_sept_alt

if it doesn't apply.

---
 arch/x86/include/asm/kvm-x86-ops.h |  6 +--
 arch/x86/include/asm/kvm_host.h    | 15 ++------
 arch/x86/kvm/mmu/mmu.c             |  3 --
 arch/x86/kvm/mmu/tdp_mmu.c         | 23 +++++++-----
 arch/x86/kvm/vmx/tdx.c             | 60 ++++++++++++++++++++----------
 5 files changed, 61 insertions(+), 46 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 6083fb07cd3b..4b865617a421 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -94,11 +94,9 @@ KVM_X86_OP_OPTIONAL_RET0(set_tss_addr)
 KVM_X86_OP_OPTIONAL_RET0(set_identity_map_addr)
 KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
-KVM_X86_OP_OPTIONAL(alloc_external_sp)
-KVM_X86_OP_OPTIONAL(free_external_sp)
-KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
-KVM_X86_OP_OPTIONAL(reclaim_external_sp)
+KVM_X86_OP_OPTIONAL(reclaim_external_spt)
 KVM_X86_OP_OPTIONAL_RET0(topup_external_cache)
+KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index cd3e7dc6ab9b..d3c31eaf18b1 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1850,19 +1850,12 @@ struct kvm_x86_ops {
 	void (*load_mmu_pgd)(struct kvm_vcpu *vcpu, hpa_t root_hpa,
 			     int root_level);
 
-	/*
-	 * Callbacks to allocate and free external page tables, a.k.a. S-EPT,
-	 * and to propagate changes in mirror page tables to the external page
-	 * tables.
-	 */
-	unsigned long (*alloc_external_sp)(gfp_t gfp);
-	void (*free_external_sp)(unsigned long addr);
+	void (*reclaim_external_spt)(struct kvm *kvm, gfn_t gfn,
+				     struct kvm_mmu_page *sp);
+	int (*topup_external_cache)(struct kvm *kvm, struct kvm_vcpu *vcpu,
+				    int min_nr_spts);
 	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				 u64 new_spte, enum pg_level level);
-	void (*reclaim_external_sp)(struct kvm *kvm, gfn_t gfn,
-				    struct kvm_mmu_page *sp);
-	int (*topup_external_cache)(struct kvm *kvm, struct kvm_vcpu *vcpu, int min);
-
 
 	bool (*has_wbinvd_exit)(void);
 
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 62bf6bec2df2..f7cf456d9404 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -6714,9 +6714,6 @@ int kvm_mmu_create(struct kvm_vcpu *vcpu)
 	if (!vcpu->arch.mmu_shadow_page_cache.init_value)
 		vcpu->arch.mmu_shadow_page_cache.gfp_zero = __GFP_ZERO;
 
-	vcpu->arch.mmu_external_spt_cache.page_get = kvm_x86_ops.alloc_external_sp;
-	vcpu->arch.mmu_external_spt_cache.page_free = kvm_x86_ops.free_external_sp;
-
 	vcpu->arch.mmu = &vcpu->arch.root_mmu;
 	vcpu->arch.walk_mmu = &vcpu->arch.root_mmu;
 
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index fef856323821..732548a678d8 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -53,14 +53,18 @@ void kvm_mmu_uninit_tdp_mmu(struct kvm *kvm)
 	rcu_barrier();
 }
 
-static void tdp_mmu_free_sp(struct kvm_mmu_page *sp)
+static void __tdp_mmu_free_sp(struct kvm_mmu_page *sp)
 {
-	if (sp->external_spt)
-		kvm_x86_call(free_external_sp)((unsigned long)sp->external_spt);
 	free_page((unsigned long)sp->spt);
 	kmem_cache_free(mmu_page_header_cache, sp);
 }
 
+static void tdp_mmu_free_unused_sp(struct kvm_mmu_page *sp)
+{
+	free_page((unsigned long)sp->external_spt);
+	__tdp_mmu_free_sp(sp);
+}
+
 /*
  * This is called through call_rcu in order to free TDP page table memory
  * safely with respect to other kernel threads that may be operating on
@@ -74,7 +78,8 @@ static void tdp_mmu_free_sp_rcu_callback(struct rcu_head *head)
 	struct kvm_mmu_page *sp = container_of(head, struct kvm_mmu_page,
 					       rcu_head);
 
-	tdp_mmu_free_sp(sp);
+	WARN_ON_ONCE(sp->external_spt);
+	__tdp_mmu_free_sp(sp);
 }
 
 void kvm_tdp_mmu_put_root(struct kvm *kvm, struct kvm_mmu_page *root)
@@ -458,7 +463,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 	}
 
 	if (is_mirror_sp(sp))
-		kvm_x86_call(reclaim_external_sp)(kvm, base_gfn, sp);
+		kvm_x86_call(reclaim_external_spt)(kvm, base_gfn, sp);
 
 	call_rcu(&sp->rcu_head, tdp_mmu_free_sp_rcu_callback);
 }
@@ -1266,7 +1271,7 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 		 * failed, e.g. because a different task modified the SPTE.
 		 */
 		if (r) {
-			tdp_mmu_free_sp(sp);
+			tdp_mmu_free_unused_sp(sp);
 			goto retry;
 		}
 
@@ -1461,7 +1466,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
 		goto err_spt;
 
 	if (is_mirror_sp) {
-		sp->external_spt = (void *)kvm_x86_call(alloc_external_sp)(GFP_KERNEL_ACCOUNT);
+		sp->external_spt = (void *)__get_free_page(GFP_KERNEL_ACCOUNT);
 		if (!sp->external_spt)
 			goto err_external_spt;
 
@@ -1472,7 +1477,7 @@ static struct kvm_mmu_page *tdp_mmu_alloc_sp_for_split(struct kvm *kvm,
 	return sp;
 
 err_external_split:
-	kvm_x86_call(free_external_sp)((unsigned long)sp->external_spt);
+	free_page((unsigned long)sp->external_spt);
 err_external_spt:
 	free_page((unsigned long)sp->spt);
 err_spt:
@@ -1594,7 +1599,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
 	 * installs its own sp in place of the last sp we tried to split.
 	 */
 	if (sp)
-		tdp_mmu_free_sp(sp);
+		tdp_mmu_free_unused_sp(sp);
 
 	return 0;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ae7b9beb3249..b0fc17baa1fc 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1701,7 +1701,7 @@ static struct tdx_pamt_cache *tdx_get_pamt_cache(struct kvm *kvm,
 }
 
 static int tdx_topup_external_pamt_cache(struct kvm *kvm,
-					 struct kvm_vcpu *vcpu, int min)
+					 struct kvm_vcpu *vcpu, int min_nr_spts)
 {
 	struct tdx_pamt_cache *pamt_cache;
 
@@ -1712,7 +1712,11 @@ static int tdx_topup_external_pamt_cache(struct kvm *kvm,
 	if (!pamt_cache)
 		return -EIO;
 
-	return tdx_topup_pamt_cache(pamt_cache, min);
+	/*
+	 * Each S-EPT page tables requires a DPAMT pair, plus one more for the
+	 * memory being mapped into the guest.
+	 */
+	return tdx_topup_pamt_cache(pamt_cache, min_nr_spts + 1);
 }
 
 static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
@@ -1911,23 +1915,41 @@ static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn, u64 new_spte,
 				     enum pg_level level)
 {
+	struct tdx_pamt_cache *pamt_cache;
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 	struct page *external_spt;
+	int r;
 
 	external_spt = tdx_spte_to_external_spt(kvm, gfn, new_spte, level);
 	if (!external_spt)
 		return -EIO;
 
+	pamt_cache = tdx_get_pamt_cache(kvm, kvm_get_running_vcpu());
+	if (!pamt_cache)
+		return -EIO;
+
+	r = tdx_pamt_get(page_to_pfn(external_spt), PG_LEVEL_4K, pamt_cache);
+	if (r)
+		return r;
+
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, level, external_spt,
 			       &entry, &level_state);
-	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
-		return -EBUSY;
+	if (unlikely(IS_TDX_OPERAND_BUSY(err))) {
+		r = -EBUSY;
+		goto err;
+	}
 
-	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
-		return -EIO;
+	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm)) {
+		r = -EIO;
+		goto err;
+	}
 
 	return 0;
+
+err:
+	tdx_pamt_put(page_to_pfn(external_spt), PG_LEVEL_4K);
+	return r;
 }
 
 static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
@@ -1995,8 +2017,8 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 	return tdx_sept_map_leaf_spte(kvm, gfn, new_spte, level);
 }
 
-static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
-					struct kvm_mmu_page *sp)
+static void tdx_sept_reclaim_private_spt(struct kvm *kvm, gfn_t gfn,
+					 struct kvm_mmu_page *sp)
 {
 	/*
 	 * KVM doesn't (yet) zap page table pages in mirror page table while
@@ -2014,7 +2036,16 @@ static void tdx_sept_reclaim_private_sp(struct kvm *kvm, gfn_t gfn,
 	 */
 	if (KVM_BUG_ON(is_hkid_assigned(to_kvm_tdx(kvm)), kvm) ||
 	    tdx_reclaim_page(virt_to_page(sp->external_spt)))
-		sp->external_spt = NULL;
+		goto out;
+
+	/*
+	 * Immediately free the S-EPT page as the TDX subsystem doesn't support
+	 * freeing pages from RCU callbacks, and more importantly because
+	 * TDH.PHYMEM.PAGE.RECLAIM ensures there are no outstanding readers.
+	 */
+	tdx_free_control_page((unsigned long)sp->external_spt);
+out:
+	sp->external_spt = NULL;
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
@@ -3869,17 +3900,8 @@ void __init tdx_hardware_setup(void)
 	 */
 	vt_x86_ops.vm_size = max_t(unsigned int, vt_x86_ops.vm_size, sizeof(struct kvm_tdx));
 
-	/*
-	 * TDX uses the external_spt cache to allocate S-EPT page table pages,
-	 * which (a) don't need to be initialized by KVM as the TDX-Module will
-	 * initialize the page (using the guest's encryption key), and (b) need
-	 * to use a custom allocator to be compatible with Dynamic PAMT.
-	 */
-	vt_x86_ops.alloc_external_sp = tdx_alloc_control_page;
-	vt_x86_ops.free_external_sp = tdx_free_control_page;
-
+	vt_x86_ops.reclaim_external_spt = tdx_sept_reclaim_private_spt;
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
-	vt_x86_ops.reclaim_external_sp = tdx_sept_reclaim_private_sp;
 
 	vt_x86_ops.gmem_convert = tdx_gmem_convert;
 

base-commit: 7adb9e428488cf7873a122043385a50dc1eebc8f

---

## [126] Dave Hansen — 2026-02-09
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On 2/6/26 07:01, Sean Christopherson wrote:
>  /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
>  int __tdx_pamt_get(u64 pfn, struct tdx_pamt_cache *cache)

Why does this need to be a raw spinlock? irqsave, sure, but raw?

The page allocator locks are used in this context and aren't raw.

---

## [127] Sean Christopherson — 2026-02-09
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Mon, Feb 09, 2026, Dave Hansen wrote:
> On 2/6/26 07:01, Sean Christopherson wrote:
> >  /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */

Huh, TIL.  (And just when I thought I finally had my head wrapped around RT "spinlocks"):

  The hard interrupt related suffixes for spin_lock / spin_unlock operations
  (_irq, _irqsave / _irqrestore) do not affect the CPU’s interrupt disabled state.

Ah, and running RCU callbacks from soft IRQ context is straight up disallowed for
PREEMPT_RT.

  /* By default, use RCU_SOFTIRQ instead of rcuc kthreads. */
  static bool use_softirq = !IS_ENABLED(CONFIG_PREEMPT_RT);
  #ifndef CONFIG_PREEMPT_RT
  module_param(use_softirq, bool, 0444);
  #endif

So yeah, just spinlock_irqsave should be fine.  Though the way things are trending,
it'll be a moot point if KVM ends up freeing S-EPT page tables from task context.

> The page allocator locks are used in this context and aren't raw.

---

## [128] Dave Hansen — 2026-02-09
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On 2/9/26 01:25, Yan Zhao wrote:
> However, given the pamt_lock is a global lock, which may be acquired
> even in the softirq context, not sure if this irq disabled version

Generally, we try to avoid crap that's not scalable because it's hard to
retrofit. But in this case, I'm just not sure how much of a bottleneck
this lock is going to be in the real world.

Let's be honest: starting and shutting down VMs in a loop doesn't mint
money for cloud providers like running VMs does, so it's not exactly a
real-world thing.

That said, if this global lock _actually_ ever starts to bite anyone for
real, it's not going to be rocket science to turn the single lock into 5
or 10 or NR_CPUs, or whatever. So I think we can just keep it as-is and
avert our eyes for the time being.

---

## [129] Yan Zhao — 2026-02-10
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Mon, Feb 09, 2026 at 04:07:08PM -0800, Dave Hansen wrote:
> On 2/9/26 01:25, Yan Zhao wrote:
> > However, given the pamt_lock is a global lock, which may be acquired
Hmm. One clarification: I'm not concerned about the global spinlock. My
concern is the attempt in the #1 solution [1] to turn off irq before acquiring
spinlock (spin_lock_irqsave()) to address the deadlock issue reported in [2].

[1] https://lore.kernel.org/all/aYYCOiMvWfSJR1AL@google.com/
[2] https://lore.kernel.org/all/aYW5CbUvZrLogsWF@yzhao56-desk.sh.intel.com/

---

## [130] Yan Zhao — 2026-02-10
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

On Mon, Feb 09, 2026 at 03:20:38PM -0800, Sean Christopherson wrote:
> On Mon, Feb 09, 2026, Yan Zhao wrote:
> > On Fri, Feb 06, 2026 at 07:01:14AM -0800, Sean Christopherson wrote:
Right. Though the SEAMCALL itself disables IRQs (which is no more than 18us from
my measurement), the time spent waiting for acquiring the spinlock with IRQs
disabled may scale with the number of contending threads. e.g.
When there're 4 threads trying to acquire the spinlock, the most unlucky thread
needs to wait with IRQs disabled for 3x18us=54us in the worst case.

> > For your reference, I measured some test data by concurrently launching and
> > destroying 4 TDs for 3 rounds:
It lacks the following change in tdx_sept_split_private_spte().

@@ -1836,46 +1841,70 @@ static int tdx_sept_split_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
        if (!pamt_cache)
                return -EIO;

+       r = tdx_pamt_get(page_to_pfn(external_spt), PG_LEVEL_4K, pamt_cache);
+       if (r)
+               return r;
+
        err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
                              level, &entry, &level_state);
-       if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
-               return -EIO;
+       if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm)) {
+               r = -EIO;
+               goto err;
+       }

        tdx_track(kvm);

        err = tdh_do_no_vcpus(tdh_mem_page_demote, kvm, &kvm_tdx->td, gpa,
                              level, spte_to_pfn(old_spte), external_spt,
                              pamt_cache, &entry, &level_state);
-       if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_DEMOTE, entry, level_state, kvm))
-               return -EIO;
+       if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_DEMOTE, entry, level_state, kvm)) {
+               r = -EIO;
+               goto err;
+       }

        return 0;
+err:
+       tdx_pamt_put(page_to_pfn(external_spt), PG_LEVEL_4K);
+       return r;
 }


Otherwise, LGTM except for the nits below.

> ---
>  arch/x86/include/asm/kvm-x86-ops.h |  6 +--
Nit:
S-EPT root page is a control page and it has no corresponding sp->external_spt.

So, do you think it would be good to check the root level?

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ae8b8438ae99..fff05052de27 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1643,16 +1643,23 @@ static struct tdx_pamt_cache *tdx_get_pamt_cache(struct kvm *kvm,
 static int tdx_topup_external_pamt_cache(struct kvm *kvm,
                                         struct kvm_vcpu *vcpu, int min_nr_spts)
 {
+       int root_level = (kvm_gfn_direct_bits(kvm) == TDX_SHARED_BIT_PWL_5) ? 5 :4;
        struct tdx_pamt_cache *pamt_cache;

        if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
                return 0;

        pamt_cache = tdx_get_pamt_cache(kvm, vcpu);
        if (!pamt_cache)
                return -EIO;

+       /*
+        * S-EPT root page is one of tdcs_pages whose PAMT pages have been installed in
+        * __tdx_td_init().
+        */
+       if (min_nr_spts == root_level)
+               min_nr_spts--;
+
        /*
         * Each S-EPT page tables requires a DPAMT pair, plus one more for the
         * memory being mapped into the guest.


>  }
>  
This creates another asymmetry, where there's nowhere to invoke
tdx_alloc_control_page() for the sp->external_spt.

Calling tdx_free_control_page() here could be confusing because:
- tdx_sept_reclaim_private_spt() is called only for non-root sps, whose
  sp->external_spt is not allocated via tdx_alloc_control_page().
- The S-EPT root page is allocated via __tdx_alloc_control_page() by
  __tdx_td_init(), but has no corresponding sp->external_spt.

So, could we just invoke 
"__tdx_pamt_put(page_to_pfn(virt_to_page(sp->external_spt)))" in 
tdx_sept_reclaim_private_sp()?

After tdx_sept_reclaim_private_spt() returns, sp goes back to unused by the
external page table. So, TDP MMU can invoke tdp_mmu_free_sp() without needing to
differentiate whether it's unused or not.

Something like below?

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 732548a678d8..d621e94d73c2 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -53,18 +53,15 @@ void kvm_mmu_uninit_tdp_mmu(struct kvm *kvm)
        rcu_barrier();
 }

-static void __tdp_mmu_free_sp(struct kvm_mmu_page *sp)
+static void tdp_mmu_free_sp(struct kvm_mmu_page *sp)
 {
+       free_page((unsigned long)sp->external_spt);
        free_page((unsigned long)sp->spt);
        kmem_cache_free(mmu_page_header_cache, sp);
 }

-static void tdp_mmu_free_unused_sp(struct kvm_mmu_page *sp)
-{
-       free_page((unsigned long)sp->external_spt);
-       __tdp_mmu_free_sp(sp);
-}
-
 /*
  * This is called through call_rcu in order to free TDP page table memory
  * safely with respect to other kernel threads that may be operating on
@@ -78,8 +75,7 @@ static void tdp_mmu_free_sp_rcu_callback(struct rcu_head *head)
        struct kvm_mmu_page *sp = container_of(head, struct kvm_mmu_page,
                                               rcu_head);

-       WARN_ON_ONCE(sp->external_spt);
-       __tdp_mmu_free_sp(sp);
+       tdp_mmu_free_sp(sp);
 }

 void kvm_tdp_mmu_put_root(struct kvm *kvm, struct kvm_mmu_page *root)
@@ -1271,7 +1267,7 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
                 * failed, e.g. because a different task modified the SPTE.
                 */
                if (r) {
-                       tdp_mmu_free_unused_sp(sp);
+                       tdp_mmu_free_sp(sp);
                        goto retry;
                }

@@ -1599,7 +1595,7 @@ static int tdp_mmu_split_huge_pages_root(struct kvm *kvm,
         * installs its own sp in place of the last sp we tried to split.
         */
        if (sp)
-               tdp_mmu_free_unused_sp(sp);
+               tdp_mmu_free_sp(sp);

        return 0;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index b0fc17baa1fc..fbaf43b8cd46 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2035,17 +2035,12 @@ static void tdx_sept_reclaim_private_spt(struct kvm *kvm, gfn_t gfn,
         * removal of the still-used PAMT entry.
         */
        if (KVM_BUG_ON(is_hkid_assigned(to_kvm_tdx(kvm)), kvm) ||
-           tdx_reclaim_page(virt_to_page(sp->external_spt)))
-               goto out;
+           tdx_reclaim_page(virt_to_page(sp->external_spt))) {
+               sp->external_spt = NULL;
+               return;
+       }

-       /*
-        * Immediately free the S-EPT page as the TDX subsystem doesn't support
-        * freeing pages from RCU callbacks, and more importantly because
-        * TDH.PHYMEM.PAGE.RECLAIM ensures there are no outstanding readers.
-        */
-       tdx_free_control_page((unsigned long)sp->external_spt);
-out:
-       sp->external_spt = NULL;
+       __tdx_pamt_put(page_to_pfn(virt_to_page(sp->external_spt)));
 }

 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,

---

## [131] Yan Zhao — 2026-02-10
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Fri, Feb 06, 2026 at 09:41:38AM -0800, Sean Christopherson wrote:
> On Fri, Feb 06, 2026, Yan Zhao wrote:
> > On Thu, Feb 05, 2026 at 02:33:16PM -0800, Sean Christopherson wrote:
Ok. I can understand your reasoning of checking !is_leaf now.
Thanks for the explanation!

Though I still think checking !is_present before calling op remove_external_spte()
in this patch is better, I have no strong opinion :)

... 
> Nope, as above, 100% the opposite.  Over ~3 patches, e.g.
> 
LGTM overall.

>  arch/x86/kvm/mmu/tdp_mmu.c | 118 ++++++++++++++++++-------------------
>  1 file changed, 59 insertions(+), 59 deletions(-)
For TDX's future implementation of set_external_spte() for split splitting,
could we add a new param "bool shared" to op set_external_spte() in the
future? i.e.,
- when tdx_sept_split_private_spte() is invoked under write mmu_lock, it calls
  tdh_do_no_vcpus() to retry BUSY error, and TDX_BUG_ON_2() then.
- when tdx_sept_split_private_spte() is invoked under read mmu_lock
  (in the future when calling tdh_mem_range_block() in unnecessary), it could
  directly return BUSY to TDP MMU on contention.


> +	return 0;
> +}
Do we need "WARN_ON_ONCE(is_mirror_sptep(sptep) && shared)" here ? 

> +	KVM_BUG_ON(__handle_changed_spte(kvm, as_id, sptep, gfn, old_spte,
> +					 new_spte, level, shared), kvm);



>  
>  static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
What about
	KVM_MMU_WARN_ON(is_frozen_spte(new_spte) ||
			is_frozen_spte(iter->old_spte) || iter->yielded);

> +	/*
> +	  * Temporarily freeze the SPTE until the external PTE operation has
and invoking open code try_cmpxchg64() directly?

>  	if (ret)
>  		return ret;
One concern for tdp_mmu_set_spte_atomic() to handle mirror SPTEs:
- Previously
  1. set *iter->sptep to FROZEN_SPTE.
  2. kvm_x86_call(set_external_spte)(old_spte, new_spte)
  3. set *iter->sptep to new_spte

- Now with this diff
  1. set *iter->sptep to FROZEN_SPTE.
  2. __handle_changed_spte()
     --> kvm_x86_call(set_external_spte)(iter->sptep, old_spte, new_spte)
  3. set *iter->sptep to new_spte 

  what if __handle_changed_spte() reads *iter->sptep in step 2?
  Passing in "bool is_mirror_sp" to __handle_changed_spte() instead?

---

## [132] Huang, Kai — 2026-02-10
*Subject: Re: [RFC PATCH v5 20/45] KVM: x86/mmu: Allocate/free S-EPT pages
 using tdx_{alloc,free}_control_page()*

> 
> Doesn't work, because sp->external_spt will be non-NULL when KVM is freeing

That's a bit unfortunate.

I hate to say, but should we just use option 1?  :-)

As Dave mentioned, we can always improve the locking when there's real
performance issue.

---

## [133] Dave Hansen — 2026-02-10
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On 1/28/26 17:14, Sean Christopherson wrote:
> +static void tdx_pamt_put(struct page *page)
> +{

This looks funky.

Right now, this is:

	spin_lock(pamt_lock)
	atomic_inc/dec(fine-grained-refcount)
	tdcall_blah_blah()
	spin_unlock(pamt_lock)

Where it *always* acquires the global lock when DPAMT is supported.
Couldn't we optimize it so that it only acquires it when it has to keep
the refcount stable at zero?

Roughly:

	slow_path = atomic_dec_and_lock(fine-grained-refcount,
					pamt_lock)
	if (!slow_path)
		goto out;

	// fine-grained-refcount==0 and must stay that way with
	// pamt_lock held. Remove the DPAMT pages:
	tdh_phymem_pamt_remove(page, pamt_pa_array)
out:	
	spin_unlock(pamt_lock)

On the acquire side, you do:

	fast_path = atomic_inc_not_zero(fine-grained-refcount)
	if (fast_path)
		return;

	// slow path:
	spin_lock(pamt_lock)

	// Was the race lost with another 0=>1 increment?
	if (atomic_read(fine-grained-refcount) > 0)
		goto out_inc

	tdh_phymem_pamt_add(page, pamt_pa_array)
	// Inc after the TDCALL so another thread won't race ahead of us
	// and try to use a non-existent PAMT entry
out_inc:
	atomic_inc(fine-grained-refcount)
	spin_unlock(pamt_lock)

Then, at least only the 0=>1 and 1=>0 transitions need the global lock.
The fast paths only touch the refcount which isn't shared nearly as much
as the global lock.

BTW, this probably still needs to be spin_lock_irq(), not what I wrote
above, but that's not a big deal to add.

I've stared at this for a bit and don't see any holes. Does anyone else
see any?

---

## [134] Sean Christopherson — 2026-02-10
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Tue, Feb 10, 2026, Yan Zhao wrote:
> On Fri, Feb 06, 2026 at 09:41:38AM -0800, Sean Christopherson wrote:
> > On Fri, Feb 06, 2026, Yan Zhao wrote:

Yeah, I have no objection to using @shared for things like that.

> > +	return 0;
> > +}

No, because I want to call this code for all paths, including the fault path.

> > +	KVM_BUG_ON(__handle_changed_spte(kvm, as_id, sptep, gfn, old_spte,
> > +					 new_spte, level, shared), kvm);

No, because __tdp_mmu_set_spte_atomic() is still used by kvm_tdp_mmu_age_spte(),
and the yielded/frozen rules apply there as well.

> > +	/*
> > +	 * Unfreeze the mirror SPTE.  If updating the external SPTE failed,

Note, iter->sptep isn't passed to set_external_spte(), the invocation for that is:

		return kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
						       new_spte, level);

>   3. set *iter->sptep to new_spte 
> 

For the most part, "don't do that".  There are an infinite number of "what ifs".
I agree that re-reading iter->sptep is slightly more likely than other "what ifs",
but then if we convert to a boolean it creates the "what if we swap the order of
@as_id and @is_mirror_sp"?  Given that @old_spte is provided, IMO re-reading the
SPTE from memory will stand out.

That said, I think we can have the best of both worlds.  Rather than pass @as_id
and @sptep, pass the @sp, i.e. the owning kvm_mmu_page.  That would address your
concern about re-reading the sptep, without needing another boolean.

E.g. slotted in as a cleanup somewhere earlier:

---
 arch/x86/kvm/mmu/tdp_mmu.c | 29 +++++++++++++++--------------
 1 file changed, 15 insertions(+), 14 deletions(-)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 732548a678d8..d395da35d5e4 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -326,7 +326,7 @@ void kvm_tdp_mmu_alloc_root(struct kvm_vcpu *vcpu, bool mirror)
 	}
 }
 
-static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
+static void handle_changed_spte(struct kvm *kvm, struct kvm_mmu_page *sp,
 				gfn_t gfn, u64 old_spte, u64 new_spte,
 				int level, bool shared);
 
@@ -458,8 +458,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 			old_spte = kvm_tdp_mmu_write_spte(sptep, old_spte,
 							  FROZEN_SPTE, level);
 		}
-		handle_changed_spte(kvm, kvm_mmu_page_as_id(sp), sptep, gfn,
-				    old_spte, FROZEN_SPTE, level, shared);
+		handle_changed_spte(kvm, sp, gfn, old_spte, FROZEN_SPTE, level, shared);
 	}
 
 	if (is_mirror_sp(sp))
@@ -471,8 +470,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
 /**
  * __handle_changed_spte - handle bookkeeping associated with an SPTE change
  * @kvm: kvm instance
- * @as_id: the address space of the paging structure the SPTE was a part of
- * @sptep: pointer to the SPTE
+ * @sp: the page table in which the SPTE resides
  * @gfn: the base GFN that was mapped by the SPTE
  * @old_spte: The value of the SPTE before the change
  * @new_spte: The value of the SPTE after the change
@@ -485,7 +483,7 @@ static void handle_removed_pt(struct kvm *kvm, tdp_ptep_t pt, bool shared)
  * dirty logging updates are handled in common code, not here (see make_spte()
  * and fast_pf_fix_direct_spte()).
  */
-static int __handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
+static int __handle_changed_spte(struct kvm *kvm, struct kvm_mmu_page *sp,
 				 gfn_t gfn, u64 old_spte, u64 new_spte,
 				 int level, bool shared)
 {
@@ -494,6 +492,7 @@ static int __handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 	bool was_leaf = was_present && is_last_spte(old_spte, level);
 	bool is_leaf = is_present && is_last_spte(new_spte, level);
 	bool pfn_changed = spte_to_pfn(old_spte) != spte_to_pfn(new_spte);
+	int as_id = kvm_mmu_page_as_id(sp);
 
 	WARN_ON_ONCE(level > PT64_ROOT_MAX_LEVEL);
 	WARN_ON_ONCE(level < PG_LEVEL_4K);
@@ -570,19 +569,19 @@ static int __handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 	if (was_present && !was_leaf &&
 	    (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed)))
 		handle_removed_pt(kvm, spte_to_child_pt(old_spte, level), shared);
-	else if (is_mirror_sptep(sptep))
+	else if (is_mirror_sp(sp))
 		return kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
 						       new_spte, level);
 
 	return 0;
 }
 
-static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
+static void handle_changed_spte(struct kvm *kvm, struct kvm_mmu_page *sp,
 				gfn_t gfn, u64 old_spte, u64 new_spte,
 				int level, bool shared)
 {
-	KVM_BUG_ON(__handle_changed_spte(kvm, as_id, sptep, gfn, old_spte,
-					 new_spte, level, shared), kvm);
+	KVM_BUG_ON(__handle_changed_spte(kvm, sp, gfn, old_spte, new_spte,
+					 level, shared), kvm);
 }
 
 static inline int __must_check __tdp_mmu_set_spte_atomic(struct kvm *kvm,
@@ -631,6 +630,7 @@ static inline int __must_check tdp_mmu_set_spte_atomic(struct kvm *kvm,
 						       struct tdp_iter *iter,
 						       u64 new_spte)
 {
+	struct kvm_mmu_page *sp = sptep_to_sp(rcu_dereference(iter->sptep));
 	int ret;
 
 	lockdep_assert_held_read(&kvm->mmu_lock);
@@ -652,8 +652,8 @@ static inline int __must_check tdp_mmu_set_spte_atomic(struct kvm *kvm,
 	if (ret)
 		return ret;
 
-	ret = __handle_changed_spte(kvm, iter->as_id, iter->sptep, iter->gfn,
-				    iter->old_spte, new_spte, iter->level, true);
+	ret = __handle_changed_spte(kvm, sp, iter->gfn, iter->old_spte,
+				    new_spte, iter->level, true);
 
 	/*
 	 * Unfreeze the mirror SPTE.  If updating the external SPTE failed,
@@ -678,7 +678,6 @@ static inline int __must_check tdp_mmu_set_spte_atomic(struct kvm *kvm,
 /*
  * tdp_mmu_set_spte - Set a TDP MMU SPTE and handle the associated bookkeeping
  * @kvm:	      KVM instance
- * @as_id:	      Address space ID, i.e. regular vs. SMM
  * @sptep:	      Pointer to the SPTE
  * @old_spte:	      The current value of the SPTE
  * @new_spte:	      The new value that will be set for the SPTE
@@ -691,6 +690,8 @@ static inline int __must_check tdp_mmu_set_spte_atomic(struct kvm *kvm,
 static u64 tdp_mmu_set_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 			    u64 old_spte, u64 new_spte, gfn_t gfn, int level)
 {
+	struct kvm_mmu_page *sp = sptep_to_sp(rcu_dereference(sptep));
+
 	lockdep_assert_held_write(&kvm->mmu_lock);
 
 	/*
@@ -704,7 +705,7 @@ static u64 tdp_mmu_set_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,
 
 	old_spte = kvm_tdp_mmu_write_spte(sptep, old_spte, new_spte, level);
 
-	handle_changed_spte(kvm, as_id, sptep, gfn, old_spte, new_spte, level, false);
+	handle_changed_spte(kvm, sp, gfn, old_spte, new_spte, level, false);
 
 	return old_spte;
 }

base-commit: f9d48449fbf9aff6cdced4703cdfdfc1d2e49efe
--

>   Passing in "bool is_mirror_sp" to __handle_changed_spte() instead?

---

## [135] Edgecombe, Rick P — 2026-02-10
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On Tue, 2026-02-10 at 09:44 -0800, Dave Hansen wrote:
> This looks funky.
> 


This is pretty much what the next patch does "x86/virt/tdx: Optimize
tdx_alloc/free_control_page() helpers", although it doesn't use the
atomic_dec_and_lock() helpers. There are a few extra considerations. The get/put
fast paths can race, so inside the lock it has to double check that work or
otherwise handle the race. This lead the code to be complex enough that it was
split into too patches "dumb and correct" and "smart and complicated".

I'm wasn't familiar with atomic_dec_and_lock(). I'm guess the atomic part
doesn't cover both decrementing *and* taking the lock?

---

## [136] Dave Hansen — 2026-02-10
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On 2/10/26 14:15, Edgecombe, Rick P wrote:
> I'm wasn't familiar with atomic_dec_and_lock(). I'm guess the atomic
> part doesn't cover both decrementing *and* taking the lock?

Right. Only 1=>0 is under the lock. All other decs are outside the lock.

It doesn't do the atomic and the lock "atomically together" somehow.

---

## [137] Huang, Kai — 2026-02-10
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On Tue, 2026-02-10 at 14:19 -0800, Dave Hansen wrote:
> On 2/10/26 14:15, Edgecombe, Rick P wrote:
> > I'm wasn't familiar with atomic_dec_and_lock(). I'm guess the atomic

Sorry I am a bit confused.  But I think the "1=>0 and lock" are atomic
together?

If so, I think we can avoid the "race" mentioned by Rick, which is handled
by "x86/virt/tdx: Optimize tdx_alloc/free_control_page() helpers".

Kirill described the race [*].  Quote it here:

---

  Consider the following scenario

	CPU0				CPU1

  tdx_pamt_put()
    atomic_dec_and_test() == true
    				    tdx_pamt_get()
				      atomic_inc_not_zero() == false
					tdx_pamt_add()
					  <takes pamt_lock>
					  // CPU0 never removed PAMTmemory
					  tdh_phymem_pamt_add() ==  
							HPA_RANGE_NOT_FREE
					  atomic_set(1);
					  <drops pamt_lock>
  <takes pamt_lock>
  // Lost the race to CPU1
  atomic_read() > 0
  <drop pamt_lock>

---

But with atomic_dec_and_lock() (assuming "1=>0 and lock" is atomic), I think
this race won't happen.  In tdx_pamt_put() on CPU0, the lock will always be
grabbed when refcount becomes 0, so PAMT pages are guaranteed to be freed. 
Therefore tdx_pamt_get() on CPU1 should never meet "HPA_RANGE_NOT_FREE".

[*]
https://lore.kernel.org/kvm/bfaswqmlsyycr3alibn6f422cjtpd6ybssjekvrrz4zdwgwfcz@pxy25ra4sln2/

---

## [138] Dave Hansen — 2026-02-10
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On 2/10/26 14:46, Huang, Kai wrote:
> Sorry I am a bit confused.  But I think the "1=>0 and lock" are atomic
> together?

Maybe I'm being pedantic. The 1=>0 happens under the lock, but the 1=>0
and the lock acquisition itself are not atomic. You can see them
happening at different times:

int _atomic_dec_and_lock(atomic_t *atomic, spinlock_t *lock)
{
        /* Subtract 1 from counter unless that drops it to 0...
        if (atomic_add_unless(atomic, -1, 1))
                return 0;

        /* Otherwise do it the slow way */
        spin_lock(lock);
        if (atomic_dec_and_test(atomic))
                return 1;
        spin_unlock(lock);
        return 0;
}

tl;dr: Kirill was right, atomic_dec_and_test() doesn't work by itself here.

But I think atomic_dec_and_lock() will.

Does anyone disagree?

---

## [139] Huang, Kai — 2026-02-10
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On Tue, 2026-02-10 at 14:50 -0800, Dave Hansen wrote:
> On 2/10/26 14:46, Huang, Kai wrote:
> > Sorry I am a bit confused.  But I think the "1=>0 and lock" are atomic

Oh I see.  Thanks.

> 
> int _atomic_dec_and_lock(atomic_t *atomic, spinlock_t *lock)

Agreed.

---

## [140] Edgecombe, Rick P — 2026-02-11
*Subject: Re: [RFC PATCH v5 16/45] x86/virt/tdx: Add
 tdx_alloc/free_control_page() helpers*

On Tue, 2026-02-10 at 09:44 -0800, Dave Hansen wrote:
> 	slow_path = atomic_dec_and_lock(fine-grained-refcount,
> 					pamt_lock)

I guess if it returns 0, the lock is not held. So we can just return.

> 
> 	// fine-grained-refcount==0 and must stay that way with

I don't see any issues. It is largely similar to the version in the next patch
except we don't need to handle the HPA_RANGE_NOT_FREE case specially. It does
this without taking the lock in any more cases. So seems like a nice code
reduction.

It probably is still worth keeping the comment about the get/put race somewhere.
I'll see if I can slot it in somewhere.

---

## [141] Yan Zhao — 2026-02-11
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Tue, Feb 10, 2026 at 11:52:09AM -0800, Sean Christopherson wrote:
> > For TDX's future implementation of set_external_spte() for split splitting,
> > could we add a new param "bool shared" to op set_external_spte() in the
Great.

> > > +	return 0;
> > > +}
Hmm. IIUC, handle_changed_spte() can't be invoked for mirror root under read
mmu_lock.
For read mmu_lock + mirror scenarios, they need to invoke
tdp_mmu_set_spte_atomic() --> __handle_changed_spte(). 

> > > @@ -663,14 +630,44 @@ static inline int __must_check tdp_mmu_set_spte_atomic(struct kvm *kvm,
> > >  
I see.

> > > +	/*
> > > +	 * Unfreeze the mirror SPTE.  If updating the external SPTE failed,
Oh, sorry. It should be
2. __handle_changed_spte(iter->sptep, old_spte, new_spte)
   --> kvm_x86_call(set_external_spte)(old_spte, new_spte)

My concern is that what we pass to __handle_changed_spte() here are
"iter->sptep, iter->old_spte, new_spte".

     ret = __handle_changed_spte(kvm, iter->as_id, iter->sptep, iter->gfn,
                                 iter->old_spte, new_spte, iter->level, true);

i.e., new_spte is the target value which we haven't written it to iter->sptep
yet. We'll write the target value new_spte to iter->sptep after
__handle_changed_spte() succeeds. So, upon invoking __handle_changed_spte() in
tdp_mmu_set_spte_atomic(), iter->sptep just holds value FROZEN_SPTE.

So, re-reading iter->sptep will get a different value (which is FROZEN_SPTE)
from the new_spte passed to __handle_changed_spte().

Besides, __handle_changed_spte() contains code like
"kvm_update_page_stats(kvm, level, is_leaf ? 1 : -1);", which may have
incorrectly updated the stats even if kvm_x86_call(set_external_spte)() fails
later and the new_spte is never written to iter->sptep.


> >   3. set *iter->sptep to new_spte 
> > 
As my above concern, re-reading SPTE in __handle_changed_spte() will just get
value FROZEN_SPTE instead of the value of new_spte.

> That said, I think we can have the best of both worlds.  Rather than pass @as_id
> and @sptep, pass the @sp, i.e. the owning kvm_mmu_page.  That would address your
Hmm, my intention of passing boolean is to avoid re-reading sptep, because
in step 2, we pass new_spte instead of the real value in sptep (which is
FROZEN_SPTE for mirror sp) to __handle_changed_spte().
So, passing @sp may not help?

---

## [142] Yan Zhao — 2026-02-11
*Subject: Re: [RFC PATCH v5 44/45] KVM: x86/mmu: Add support for splitting
 S-EPT hugepages on conversion*

On Thu, Jan 29, 2026 at 07:39:27AM -0800, Sean Christopherson wrote:
> Compile tested only...
It passed my local tests with the fix [1].

[1] https://lore.kernel.org/all/aYX-RpxDYrI65XRC@google.com.

> @@ -1950,6 +1950,7 @@ struct kvm_x86_ops {
>  	void *(*alloc_apic_backing_page)(struct kvm_vcpu *vcpu);
Since tdx_gmem_convert() only performs S-EPT splitting on the specified range,
would it make sense to rename the op gmem_convert() to something like
gmem_split_private_mapping()?
(This would also involve renaming
kvm_gmem_convert() to kvm_gmem_split_private_mapping(), and
kvm_arch_gmem_convert() to kvm_arch_gmem_split_private_mapping()).

This way, it's natural for it to be called by kvm_gmem_set_attributes() for
private-to-shared conversions, kvm_gmem_punch_hole(), or kvm_gmem_error_folio().

> +static int tdx_gmem_convert(struct kvm *kvm, gfn_t start, gfn_t end,
> +			    bool to_private)
Thanks for the change from spinlock to mutex, which is a smart approach that
eliminates the need to release the lock for topup.

However, I have a question about kvm_tdp_mmu_try_split_huge_pages(), which is
called by dirty page tracking related functions. I'm not sure if we might want
to invoke them from a non-vCPU thread for mirror roots in the future. If that's
the case, would they need some way to acquire this lock?

> +	guard(write_lock)(&kvm->mmu_lock);
> +

---

## [143] Yan Zhao — 2026-02-11
*Subject: Re: [RFC PATCH v5 37/45] KVM: x86/tdp_mmu: Alloc external_spt page
 for mirror page table splitting*

On Fri, Feb 06, 2026 at 08:09:06AM -0800, Sean Christopherson wrote:
> > So, it's incorrect to invoke is_mirror_sptep() which internally contains
> > rcu_dereference(), resulting in "WARNING: suspicious RCU usage".

LGTM.

> diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
> index a32192c35099..4d92c0d19d7c 100644

---

## [144] Huang, Kai — 2026-02-13
*Subject: Re: [RFC PATCH v5 43/45] *** DO NOT MERGE *** KVM: guest_memfd: Add
 pre-zap arch hook for shared<=>private conversion*

On Wed, 2026-01-28 at 17:15 -0800, Sean Christopherson wrote:
> --- a/virt/kvm/Kconfig
> +++ b/virt/kvm/Kconfig

Just FYI:

It appears something went wrong when editing this file.  I got below warning
when playing with this series:

virt/kvm/Kconfig:131:warning: no new line at end of file

---

## [145] Sean Christopherson — 2026-02-13
*Subject: Re: [RFC PATCH v5 44/45] KVM: x86/mmu: Add support for splitting
 S-EPT hugepages on conversion*

On Wed, Feb 11, 2026, Yan Zhao wrote:
> However, I have a question about kvm_tdp_mmu_try_split_huge_pages(), which is
> called by dirty page tracking related functions. I'm not sure if we might want

More than likely, yes.  But that's a far future problem, at least as far as
upstream is concerned.  I.e. I don't want to plan _that_ far ahead in terms of
writing code to avoid churn.

---

## [146] Sean Christopherson — 2026-02-13
*Subject: Re: [RFC PATCH v5 08/45] KVM: x86/mmu: Propagate mirror SPTE removal
 to S-EPT in handle_changed_spte()*

On Wed, Feb 11, 2026, Yan Zhao wrote:
> On Tue, Feb 10, 2026 at 11:52:09AM -0800, Sean Christopherson wrote:
> > > > +static void handle_changed_spte(struct kvm *kvm, int as_id, tdp_ptep_t sptep,

Oh, sorry, I misread that.  Now I see what you're saying.  I think I'd still prefer
to omit the WARN?  Because there's nothing inherently wrong with using
handle_changed_spte().  E.g. if the caller can somehow guarantee success, then
using handle_changed_spte() is a-ok.

> Besides, __handle_changed_spte() contains code like
> "kvm_update_page_stats(kvm, level, is_leaf ? 1 : -1);", which may have

Oof, now _that_ is an actual problem.  This is the least-ugly fix I can come up
with.  Note, this will mean the trace order is "wrong" when removing a non-mirror
page table, as KVM will zap the page table before its children.  I doubt that'll
be a problem in practice, so I'm inclined to take the simpler code.

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index d395da35d5e4..4ba789f2824d 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -493,6 +493,7 @@ static int __handle_changed_spte(struct kvm *kvm, struct kvm_mmu_page *sp,
        bool is_leaf = is_present && is_last_spte(new_spte, level);
        bool pfn_changed = spte_to_pfn(old_spte) != spte_to_pfn(new_spte);
        int as_id = kvm_mmu_page_as_id(sp);
+       int r;
 
        WARN_ON_ONCE(level > PT64_ROOT_MAX_LEVEL);
        WARN_ON_ONCE(level < PG_LEVEL_4K);
@@ -524,8 +525,6 @@ static int __handle_changed_spte(struct kvm *kvm, struct kvm_mmu_page *sp,
        if (old_spte == new_spte)
                return 0;
 
-       trace_kvm_tdp_mmu_spte_changed(as_id, gfn, level, old_spte, new_spte);
-
        if (is_leaf)
                check_spte_writable_invariants(new_spte);
 
@@ -554,9 +553,6 @@ static int __handle_changed_spte(struct kvm *kvm, struct kvm_mmu_page *sp,
                return 0;
        }
 
-       if (is_leaf != was_leaf)
-               kvm_update_page_stats(kvm, level, is_leaf ? 1 : -1);
-
        /*
         * Recursively handle child PTs if the change removed a subtree from
         * the paging structure.  Note the WARN on the PFN changing without the
@@ -567,11 +563,19 @@ static int __handle_changed_spte(struct kvm *kvm, struct kvm_mmu_page *sp,
         * changes to the external SPTE.
         */
        if (was_present && !was_leaf &&
-           (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed)))
+           (is_leaf || !is_present || WARN_ON_ONCE(pfn_changed))) {
                handle_removed_pt(kvm, spte_to_child_pt(old_spte, level), shared);
-       else if (is_mirror_sp(sp))
-               return kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
-                                                      new_spte, level);
+       } else if (is_mirror_sp(sp)) {
+               r = kvm_x86_call(set_external_spte)(kvm, gfn, old_spte,
+                                                   new_spte, level);
+               if (r)
+                       return r;
+       }
+
+       trace_kvm_tdp_mmu_spte_changed(as_id, gfn, level, old_spte, new_spte);
+
+       if (is_leaf != was_leaf)
+               kvm_update_page_stats(kvm, level, is_leaf ? 1 : -1);
 
        return 0;
 }

> > >   3. set *iter->sptep to new_spte 
> > > 

It won't prevent someone that's bound and determined to introduce a bug from
re-reading the sptep, but it most definitely helps.  To get at the sptep, someone
would have to compute its index based off @gfn and then look it up in @sp->spt.
At that point, they've earned the bug :-)

---

## [147] Edgecombe, Rick P — 2026-02-18
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop
 kvm_x86_ops.link_external_spt(), use .set_external_spte() for all*

On Tue, 2026-02-03 at 20:05 +0000, Sean Christopherson wrote:
> > And mirror_spte --> new_spte?
> 

Sorry for the late comment on the tiny detail, but things seemed to have calmed
down enough to attempt to merge these discussions into the snarl.

It doesn't quite fit in this patch because the set_external_spte() op also uses
the mirror_pte name. So then you need to either expand the scope of the patch to
change "mirror" to "new" across the callchain, or creating a small mismatch
between tdx_sept_set_private_spte() and tdx_sept_link_private_spt().

The patch where it happens in this series needs to add the old_pte, forcing
mirror_spte to grow some new nomenclature. So on balance I think it fits better
there, and we should leave it alone here. We can update it in
tdx_sept_link_private_spt() in "KVM: x86/mmu: Plumb the old_spte into
kvm_x86_ops.set_external_spte()".

---

## [148] Sean Christopherson — 2026-02-20
*Subject: Re: [RFC PATCH v5 05/45] KVM: TDX: Drop kvm_x86_ops.link_external_spt(),
 use .set_external_spte() for all*

On Wed, Feb 18, 2026, Rick P Edgecombe wrote:
> On Tue, 2026-02-03 at 20:05 +0000, Sean Christopherson wrote:
> > > And mirror_spte --> new_spte?

No argument from me.

---

## [149] Edgecombe, Rick P — 2026-04-15
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> As for landing these series, I think the fastest overall approach would be
> to land patches 1-4 asap (tangentially related cleanups and fixes), agree

Sean, were you still planning to do this? I see you're, I think, asking for Dave
to pull patch 1 here:
https://lore.kernel.org/kvm/ac_bMKD7YGhMwUCf@google.com/

But actually he acked the version in this series, so another option is you could
just take patches 1-4?

Please let me know if you are ok with that plan. We are growing stacks ahead of
DPAMT and the other splintered pre-req work and looking to reduce it. It could
be nice if we could take all the pre-req work through the same tree for that
reason, and most of it is on the KVM side. Is it reasonable?

---

## [150] Sean Christopherson — 2026-04-17
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On Wed, Apr 15, 2026, Rick P Edgecombe wrote:
> On Wed, 2026-01-28 at 17:14 -0800, Sean Christopherson wrote:
> > As for landing these series, I think the fastest overall approach would be

Oh, right.  I forgot about that.

> so another option is you could just take patches 1-4?

Yeah, I think that makes the most sense.

> Please let me know if you are ok with that plan. We are growing stacks ahead of
> DPAMT and the other splintered pre-req work and looking to reduce it. It could

Ya.  I'll apply 1-4 and create a stable tag for patch 1's commit for 7.2.  If
it won't throw a wrench in things for you, I'll wait until 7.1-rc2 to get 'em
applied.  I've been burned more than a few times when using rc1 as the base for
topic branches.

Dave, holler if this doesn't work for you.

---

## [151] Edgecombe, Rick P — 2026-04-17
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On Fri, 2026-04-17 at 09:59 -0700, Sean Christopherson wrote:
> > Ya.  I'll apply 1-4 and create a stable tag for patch 1's commit for 7.2. 
> > If it won't throw a wrench in things for you, I'll wait until 7.1-rc2 to get

Sounds great from my side. Thanks!

---

## [152] Sean Christopherson — 2026-05-18
*Subject: Re: [RFC PATCH v5 00/45] TDX: Dynamic PAMT + S-EPT Hugepage*

On Wed, 28 Jan 2026 17:14:32 -0800, Sean Christopherson wrote:
> This is a combined series of Dynamic PAMT (from Rick), and S-EPT hugepage
> support (from Yan).  Except for some last minute tweaks to the DPAMT array

Applied 1-4 to kvm-x86 mmu.  Please yell if this was unexpected in any way.
I'm pretty sure this is what we agreed on, but the last few week have been a
bit chaotic...

[01/45] x86/tdx: Use pg_level in TDX APIs, not the TDX-Module's 0-based level
        https://github.com/kvm-x86/linux/commit/4487492b92a4
[02/45] KVM: x86/mmu: Update iter->old_spte if cmpxchg64 on mirror SPTE "fails"
        https://github.com/kvm-x86/linux/commit/02eaaffdd865
[03/45] KVM: TDX: Account all non-transient page allocations for per-TD structures
        https://github.com/kvm-x86/linux/commit/a8b2924676ec
[04/45] KVM: x86: Make "external SPTE" ops that can fail RET0 static calls
        https://github.com/kvm-x86/linux/commit/e1a31ca28c9d

--
https://github.com/kvm-x86/linux/tree/next

---

## [153] Yan Zhao — 2026-06-11
*Subject: Re: [RFC PATCH v5 30/45] x86/virt/tdx: Add API to demote a 2MB
 mapping to 512 4KB mappings*

> +u64 tdh_mem_page_demote(struct tdx_td *td, u64 gpa, enum pg_level level, u64 pfn,
> +			struct page *new_sp, struct tdx_pamt_cache *pamt_cache,
Note for the next posting:

When DPAMT is enabled, part of the DEMOTE SEAMCALL performs the same function as
PAMT.ADD for the guest page, with the DPAMT page pair specified at args.r12 and
args.r13. So, DEMOTE has the same contention issue as PAMT.ADD [1].
Consider the following scenario:

      CPU 0                                     CPU 1

(1) DEMOTE adds pfn A1=0x1b090c,         (2) PAMT.ADD adds pfn YY, pfn ZZ as
pfn B1=0x119b4f as DPAMT pages            DPAMT pages for pfn A2=0x1b090d.
for guest page XX=0x511a00

(1) CPU0 needs to acquire a shared lock on page A1's 2MB PAMT entry.
    Since A1 and B1 are added as DPAMT pages, they don't necessarily have DPAMT
    pages installed for their own 2MB ranges.
(2) Assume there're no DPAMT pages installed for A1's 2MB range.
    CPU1 installs DPAMT pages YY, ZZ for page A2, acquiring an exclusive lock
    on page A2's 2MB PAMT entry.

Because pages A1 and A2 reside within the same 2MB range, either DEMOTE or
PAMT.ADD will return TDX_OPERAND_BUSY [2].

Though KVM holds write mmu_lock before invoking DEMOTE, which prevents
concurrent PAMT.ADD within one TD, the above BUSY error could occur if a second
TD invokes PAMT.ADD while the first TD is invoking DEMOTE.

So, fix this issue by acquiring the global pamt_lock around DEMOTE. See the new
implementation [3].

Since this contention should occur rarely (e.g., when there's a second TD
invoking PAMT.ADD concurrently while the first TD is invoking DEMOTE, and the
DPAMT page pair to add for DEMOTE must reside in the 2MB target range as
PAMT.ADD),  a possible optimization is to avoid holding the global pamt_lock in
the first invocation of tdh_mem_page_demote() (e.g., by indicating try or fast
mode); only acquire the global pamt_lock if the first try returns busy, ensuring
the second invocation must succeed.

[1] https://lore.kernel.org/kvm/aNX6V6OSIwly1hu4@yzhao56-desk.sh.intel.com
[2] The contention is verified with an internal POC.
    Error logs:
    a.1) DEMOTE adds PAMT pages pfn1=0x19c0a0, pfn2=0x1b572f for guest pfn=0x519800
      2) __tdx_pamt_get() adds PAMT pages for pfn=0x19c0a1.
      3) DEMOTE returns error 0x800002000000000c.
    b.1) DEMOTE adds PAMT pages pfn1=0x1b090c, pfn2=0x119b4f for guest pfn=0x511a00
      2) __tdx_pamt_get() adds PAMT pages for pfn=0x1b090d
      3) PAMT.ADD returns error 0x8000020000000001.

[3] New implementation:
u64 tdh_mem_page_demote(struct tdx_td *td, u64 gpa, enum pg_level level, u64 pfn,
                        struct page *new_sp, struct tdx_pamt_cache *pamt_cache,  
                        u64 *ext_err1, u64 *ext_err2)                            
{                                                                                
        bool dpamt = tdx_supports_dynamic_pamt(&tdx_sysinfo) && level == PG_LEVEL_2M;
        struct page *pamt_pages[TDX_DPAMT_ENTRY_PAGE_CNT];                       
        struct tdx_module_args args = {                                          
                .rcx = gpa | pg_level_to_tdx_sept_level(level),                  
                .rdx = tdx_tdr_pa(td),                                           
                .r8 = page_to_phys(new_sp),                                      
        };                                                                       
        atomic_t *pamt_refcount;                                                 
        u64 ret;                                                                 
                                                                                 
        if (!tdx_supports_demote_nointerrupt(&tdx_sysinfo))                      
                return TDX_SW_ERROR;                                             
                                                                                 
        /* Flush the new S-EPT page to be added */                               
        tdx_clflush_page(new_sp);                                                
                                                                                 
        if (dpamt) {                                                             
                if (alloc_pamt_array(pamt_pages, pamt_cache))                    
                        return TDX_SW_ERROR;                                     
                                                                                 
                args.r12 = page_to_phys(pamt_pages[0]);                          
                args.r13 = page_to_phys(pamt_pages[1]);                          
                                                                                 
                /*                                                               
                 * Before demotion, the 2MB guest memory range is not managed    
                 * by DPAMT, so its pamt_refcount should be 0.                   
                 * Set it to 512 after demotion succeeds, since removing of each 
                 * 4KB mapping will reduce the refcount by 1.                    
                 */                                                              
                pamt_refcount = tdx_find_pamt_refcount(pfn);                     
                                                                                 
                spin_lock(&pamt_lock);                                           
        } 
	ret = seamcall_saved_ret(TDH_MEM_PAGE_DEMOTE, &args);

        if (dpamt) {
                if (!ret)
                        WARN_ON_ONCE(atomic_cmpxchg_release(pamt_refcount, 0, PTRS_PER_PMD));

                spin_unlock(&pamt_lock);

                if (ret)
                        free_pamt_array(pamt_pages);
        }

        *ext_err1 = args.rcx;
        *ext_err2 = args.rdx;

        return ret;
}

---

## [154] Edgecombe, Rick P — 2026-06-29
*Subject: Re: [RFC PATCH v5 30/45] x86/virt/tdx: Add API to demote a 2MB
 mapping to 512 4KB mappings*

On Thu, 2026-06-11 at 16:44 +0800, Yan Zhao wrote:

Nice find.

> Since this contention should occur rarely (e.g., when there's a second TD
> invoking PAMT.ADD concurrently while the first TD is invoking DEMOTE, and the

Yes, let's not do it for the initial implementation. 

> 
> [1] https://lore.kernel.org/kvm/aNX6V6OSIwly1hu4@yzhao56-desk.sh.intel.com

Can we just not do huge pages if we don't have DPAMT? Actually, weren't we
already going to do it like that?

>                                 
>                 if (alloc_pamt_array(pamt_pages, pamt_cache))                    

It feels kind of hacky. The refcount stuff is already a bit hard to follow.

>                                                                                  
>                 spin_lock(&pamt_lock);

---

## [155] Yan Zhao — 2026-06-30
*Subject: Re: [RFC PATCH v5 30/45] x86/virt/tdx: Add API to demote a 2MB
 mapping to 512 4KB mappings*

On Tue, Jun 30, 2026 at 05:07:13AM +0800, Edgecombe, Rick P wrote:
> On Thu, 2026-06-11 at 16:44 +0800, Yan Zhao wrote:
> 
Ok. I can put the optimization in the TODO list.

> > 
> > [1] https://lore.kernel.org/kvm/aNX6V6OSIwly1hu4@yzhao56-desk.sh.intel.com
Yes, we can.
I wasn't aware we're going to disallow huge page if we don't have DPAMT.
I thought we could have huge page with and without DPAMT.

> already going to do it like that?
Is this to avoid the "if (dpamt)" check here?
We may still need to check "level == PG_LEVEL_2M" here, since DPAMT related
code is not necessary if the demotion is from 1GB to 2MB.
(This tdh_mem_page_demote() implementation could support 1GB --> 2MB demotion
theoretically).
Or maybe for now just warn and return TDX_SW_ERROR if level != PG_LEVEL_2M ?

> > ������������������������������� 
> > ��������������� if (alloc_pamt_array(pamt_pages, pamt_cache))������������������� 
After demotion, there would be 512 4KB mappings for this 2MB range.
Then, in later tdx_sept_remove_leaf_spte(), tdx_pamt_put() would be invoked
for 512 times. That's why we need to set the refcount to 512 after a successful
demotion here.

> 
> > ��������������������������������������������������������������������������������

---
