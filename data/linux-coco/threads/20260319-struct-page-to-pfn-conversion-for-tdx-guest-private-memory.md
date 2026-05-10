---
title: 'struct page to PFN conversion for TDX guest private memory'
date: 2026-03-19
last_reply: 2026-04-09
message_count: 35
participants: ['Yan Zhao', 'Xiaoyao Li', 'Kiryl Shutsemau', 'Edgecombe, Rick P', 'Dave Hansen', 'Sean Christopherson', 'Ackerley Tng', 'Paolo Bonzini']
---

## [1] Yan Zhao — 2026-03-19

This series converts TDX SEAMCALL APIs for mapping/unmapping guest private
memory from taking struct page to PFN as input.

Background
----------
TDX SEAMCALL wrappers take struct page as input, which provides:
1. Type safety
2. Make it harder to misuse and make it obvious that physical pages in RAM
   are expected from just looking at the API declaration [2][3][4][5].

This is appropriate for SEAMCALL wrappers for TDX control pages (e.g., TDR
page, TDCS pages, TDX SEPT pages), since KVM manages and allocates those
pages explicitly from core MM.

However, unlike TDX control pages, KVM guest memory is not necessarily
backed by refcounted struct page or even struct page (e.g., VM_PFNMAP
memory [6]). Taking struct page as input for SEAMCALL wrappers for
mapping/unmapping guest private memory imposes unnecessary assumptions on
how KVM and guest_memfd manage memory, even though today all TD private
memory is allocated from guest_memfd, which only allocates memory backed by
struct page.

To avoid baking in assumptions throughout KVM about guest memory being
backed by page (or further folio for future TDX private huge pages [7]),
Sean suggested converting from using struct page to PFN for SEAMCALL
wrappers operating on guest private memory [8].

This series therefore converts struct page to PFN for guest private memory
while keeping struct page for TDX control pages, and uses kvm_pfn_t for
type safety.

Sanity check
------------
Reasonable PFN sanity checks in SEAMCALL wrapper APIs (such as checking TDX
convertibility to avoid SEAMCALL failure) are still agreed upon [9][10].

However, as those failures are supposed to only occur when there're kernel
bugs, we decided not to provide any in-kernel sanity checks to keep the
code simple. i.e., when non-TDX-convertible PFNs are passed in, we let
SEAMCALLs fail. Though non-TDX-convertible PFNs may also produce MCEs or
page fault exceptions, this is a separate issue than struct page to PFN
conversion, and such exceptions are obvious enough in themselves.


Changes from Sean's original patch [1]:
---------------------------------------
1. Rebased to latest kvm-x86 next
2. Split to 2 patches for easy review.  (Rick)
3. Replaced "u64 pfn" with "kvm_pfn_t pfn"  (Rick)
4. Dropped using PFN as input to tdx_reclaim_page(). (Rick)
5. Move mk_keyed_paddr() from tdx.h to tdx.c. 

Thanks
Yan

[1] https://lore.kernel.org/kvm/20260129011517.3545883-26-seanjc@google.com
[2] https://lore.kernel.org/all/30d0cef5-82d5-4325-b149-0e99833b8785@intel.com
[3] https://lore.kernel.org/kvm/f4240495-120b-4124-b91a-b365e45bf50a@intel.com
[4] https://lore.kernel.org/kvm/435b8d81-b4de-4933-b0ae-357dea311488@intel.com
[5] https://lore.kernel.org/kvm/1b236a64-d511-49a2-9962-55f4b1eb08e3@intel.com
[6] https://lore.kernel.org/all/20241010182427.1434605-1-seanjc@google.com
[7] https://lore.kernel.org/all/aW3G6yZuvclYABzP@yzhao56-desk.sh.intel.com/
[8] https://lore.kernel.org/all/aWe1tKpFw-As6VKg@google.com
[9] https://lore.kernel.org/all/aWkVLViKBgiVGgaI@google.com
[10] https://lore.kernel.org/all/d119c824-4770-41d2-a926-4ab5268ea3a6@intel.com/


Sean Christopherson (2):
  x86/virt/tdx: Use PFN directly for mapping guest private memory
  x86/virt/tdx: Use PFN directly for unmapping guest private memory

 arch/x86/include/asm/tdx.h  | 20 +++++---------------
 arch/x86/kvm/vmx/tdx.c      | 17 ++++++++---------
 arch/x86/virt/vmx/tdx/tdx.c | 36 ++++++++++++++++++++++++------------
 3 files changed, 37 insertions(+), 36 deletions(-)


base-commit: 3d6cdcc8883b5726513d245eef0e91cabfc397f7

---

## [2] Yan Zhao — 2026-03-19
*Subject: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest private memory*

From: Sean Christopherson <seanjc@google.com>

Remove the completely unnecessary assumption that memory mapped into a TDX
guest is backed by refcounted struct page memory. From KVM's point of view,
TDH_MEM_PAGE_ADD and TDH_MEM_PAGE_AUG are glorified writes to PTEs, so they
have no business placing requirements on how KVM and guest_memfd manage
memory.

Rip out the misguided struct page assumptions/constraints and instead have
the two SEAMCALL wrapper APIs take PFN directly. This ensures that for
future huge page support in S-EPT, the kernel doesn't pick up even worse
assumptions like "a hugepage must be contained in a single folio".

Use "kvm_pfn_t pfn" for type safety. Using this KVM type is appropriate
since APIs tdh_mem_page_add() and tdh_mem_page_aug() are exported to KVM
only.

[ Yan: Replace "u64 pfn" with "kvm_pfn_t pfn" ]

Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
---
 arch/x86/include/asm/tdx.h  |  5 +++--
 arch/x86/kvm/vmx/tdx.c      |  7 +++----
 arch/x86/virt/vmx/tdx/tdx.c | 20 +++++++++++++-------
 3 files changed, 19 insertions(+), 13 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index a149740b24e8..f3f0b1872176 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -6,6 +6,7 @@
 #include <linux/init.h>
 #include <linux/bits.h>
 #include <linux/mmzone.h>
+#include <linux/kvm_types.h>
 
 #include <asm/errno.h>
 #include <asm/ptrace.h>
@@ -195,10 +196,10 @@ static inline int pg_level_to_tdx_sept_level(enum pg_level level)
 
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
-u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, kvm_pfn_t pfn, struct page *source, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page);
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, kvm_pfn_t pfn, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, int level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mng_key_config(struct tdx_td *td);
 u64 tdh_mng_create(struct tdx_td *td, u16 hkid);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 1e47c194af53..1f1abc5b5655 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1624,8 +1624,8 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 	    KVM_BUG_ON(!kvm_tdx->page_add_src, kvm))
 		return -EIO;
 
-	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
-			       kvm_tdx->page_add_src, &entry, &level_state);
+	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn, kvm_tdx->page_add_src,
+			       &entry, &level_state);
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
@@ -1640,12 +1640,11 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	struct page *page = pfn_to_page(pfn);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 entry, level_state;
 	u64 err;
 
-	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, tdx_level, page, &entry, &level_state);
+	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, tdx_level, pfn, &entry, &level_state);
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index cb9b3210ab71..a9dd75190c67 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -30,7 +30,6 @@
 #include <linux/suspend.h>
 #include <linux/syscore_ops.h>
 #include <linux/idr.h>
-#include <linux/kvm_types.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -1568,6 +1567,11 @@ static void tdx_clflush_page(struct page *page)
 	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
 }
 
+static void tdx_clflush_pfn(kvm_pfn_t pfn)
+{
+	clflush_cache_range(__va(PFN_PHYS(pfn)), PAGE_SIZE);
+}
+
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;
@@ -1588,17 +1592,18 @@ u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_mng_addcx);
 
-u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, kvm_pfn_t pfn, struct page *source,
+		     u64 *ext_err1, u64 *ext_err2)
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
@@ -1639,16 +1644,17 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_addcx);
 
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, kvm_pfn_t pfn,
+		     u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
 		.rcx = gpa | level,
 		.rdx = tdx_tdr_pa(td),
-		.r8 = page_to_phys(page),
+		.r8 = PFN_PHYS(pfn),
 	};
 	u64 ret;
 
-	tdx_clflush_page(page);
+	tdx_clflush_pfn(pfn);
 	ret = seamcall_ret(TDH_MEM_PAGE_AUG, &args);
 
 	*ext_err1 = args.rcx;

---

## [3] Yan Zhao — 2026-03-19
*Subject: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest private memory*

From: Sean Christopherson <seanjc@google.com>

Remove the completely unnecessary assumptions that memory unmapped from a
TDX guest is backed by refcounted struct page memory.

APIs tdh_phymem_page_wbinvd_hkid(), tdx_quirk_reset_page() are used when
unmapping guest private memory from S-EPT. Since mapping of guest private
memory places no requirements on how KVM and guest_memfd manage memory,
neither does guest private memory unmapping.

Rip out the misguided struct page assumptions/constraints by having the two
APIs take PFN directly. This ensures that for future huge page support in
S-EPT, the kernel doesn't pick up even worse assumptions like "a hugepage
must be contained in a single folio".

Use "kvm_pfn_t pfn" for type safety. Using this KVM type is appropriate
since APIs tdh_phymem_page_wbinvd_hkid() and tdx_quirk_reset_page() are
exported to KVM only.

Update mk_keyed_paddr(), which is invoked by tdh_phymem_page_wbinvd_hkid(),
to take PFN as parameter accordingly. Opportunistically, move
mk_keyed_paddr() from tdx.h to tdx.c since there are no external users.

Have tdx_reclaim_page() remain using struct page as parameter since it's
currently not used for removing guest private memory yet.

[Yan: Use kvm_pfn_t, drop reclaim API param update, move mk_keyed_paddr()]

Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
---
 arch/x86/include/asm/tdx.h  | 15 ++-------------
 arch/x86/kvm/vmx/tdx.c      | 10 +++++-----
 arch/x86/virt/vmx/tdx/tdx.c | 16 +++++++++++-----
 3 files changed, 18 insertions(+), 23 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index f3f0b1872176..6ceb4cd9ff21 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -153,7 +153,7 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
-void tdx_quirk_reset_page(struct page *page);
+void tdx_quirk_reset_page(kvm_pfn_t pfn);
 
 struct tdx_td {
 	/* TD root structure: */
@@ -177,17 +177,6 @@ struct tdx_vp {
 	struct page **tdcx_pages;
 };
 
-static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
-{
-	u64 ret;
-
-	ret = page_to_phys(page);
-	/* KeyID bits are just above the physical address bits: */
-	ret |= (u64)hkid << boot_cpu_data.x86_phys_bits;
-
-	return ret;
-}
-
 static inline int pg_level_to_tdx_sept_level(enum pg_level level)
 {
         WARN_ON_ONCE(level == PG_LEVEL_NONE);
@@ -219,7 +208,7 @@ u64 tdh_mem_track(struct tdx_td *tdr);
 u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, kvm_pfn_t pfn);
 #else
 static inline void tdx_init(void) { }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 1f1abc5b5655..75ad3debcd84 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -343,7 +343,7 @@ static int tdx_reclaim_page(struct page *page)
 
 	r = __tdx_reclaim_page(page);
 	if (!r)
-		tdx_quirk_reset_page(page);
+		tdx_quirk_reset_page(page_to_pfn(page));
 	return r;
 }
 
@@ -597,7 +597,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
-	tdx_quirk_reset_page(kvm_tdx->td.tdr_page);
+	tdx_quirk_reset_page(page_to_pfn(kvm_tdx->td.tdr_page));
 
 	__free_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
@@ -1776,9 +1776,9 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 					 enum pg_level level, u64 mirror_spte)
 {
-	struct page *page = pfn_to_page(spte_to_pfn(mirror_spte));
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 
@@ -1817,11 +1817,11 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
 		return;
 
-	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, page);
+	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn);
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
-	tdx_quirk_reset_page(page);
+	tdx_quirk_reset_page(pfn);
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a9dd75190c67..2f9d07ad1a9a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -730,9 +730,9 @@ static void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
 	mb();
 }
 
-void tdx_quirk_reset_page(struct page *page)
+void tdx_quirk_reset_page(kvm_pfn_t pfn)
 {
-	tdx_quirk_reset_paddr(page_to_phys(page), PAGE_SIZE);
+	tdx_quirk_reset_paddr(PFN_PHYS(pfn), PAGE_SIZE);
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_quirk_reset_page);
 
@@ -1907,21 +1907,27 @@ u64 tdh_phymem_cache_wb(bool resume)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_cache_wb);
 
+static inline u64 mk_keyed_paddr(u16 hkid, kvm_pfn_t pfn)
+{
+	/* KeyID bits are just above the physical address bits. */
+	return PFN_PHYS(pfn) | ((u64)hkid << boot_cpu_data.x86_phys_bits);
+}
+
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td)
 {
 	struct tdx_module_args args = {};
 
-	args.rcx = mk_keyed_paddr(tdx_global_keyid, td->tdr_page);
+	args.rcx = mk_keyed_paddr(tdx_global_keyid, page_to_pfn(td->tdr_page));
 
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_tdr);
 
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, kvm_pfn_t pfn)
 {
 	struct tdx_module_args args = {};
 
-	args.rcx = mk_keyed_paddr(hkid, page);
+	args.rcx = mk_keyed_paddr(hkid, pfn);
 
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }

---

## [4] Xiaoyao Li — 2026-03-19
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On 3/19/2026 8:58 AM, Yan Zhao wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

So why keep the function tdx_quirk_reset_page() but expect passing in 
the kvm_pfn_t? It looks werid that the name indicates to reset a page 
but what gets passed in is a pfn.

I think we have 2 options:

1. Drop helper tdx_quirk_reset_page() and use tdx_quirk_reset_paddr() 
directly.

2. keep tdx_quirk_reset_page() as-is for the cases of tdx_reclaim_page() 
and tdx_reclaim_td_control_pages() that have the struct page. But only 
change tdx_sept_remove_private_spte() to use tdx_quirk_reset_paddr() 
directly.

---

## [5] Yan Zhao — 2026-03-19
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, Mar 19, 2026 at 11:20:48AM +0800, Xiaoyao Li wrote:
> On 3/19/2026 8:58 AM, Yan Zhao wrote:
> > From: Sean Christopherson <seanjc@google.com>
I thought about introducing tdx_quirk_reset_pfn(). But considering
tdx_quirk_reset_pfn() has to be an exported API, I'm reluctant to do that.

Given that even with tdx_quirk_reset_pfn(), it still expects TDX convertible
RAM, I think having tdx_quirk_reset_page() to take pfn is still acceptable.

We just don't want KVM to do pfn --> struct page --> pfn conversions.

---

## [6] Xiaoyao Li — 2026-03-19
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On 3/19/2026 2:45 PM, Yan Zhao wrote:
> On Thu, Mar 19, 2026 at 11:20:48AM +0800, Xiaoyao Li wrote:
>> On 3/19/2026 8:58 AM, Yan Zhao wrote:
[...]
>>> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
>>> index a9dd75190c67..2f9d07ad1a9a 100644

Only tdx_sept_remove_private_spte() is doing such conversions. While 
tdx_reclaim_page() and tdx_reclaim_td_control_pages() already have the 
struct page natively.

So why not considering option 2?

   2. keep tdx_quirk_reset_page() as-is for the cases of
      tdx_reclaim_page() and tdx_reclaim_td_control_pages() that have the
      struct page. But only change tdx_sept_remove_private_spte() to use
      tdx_quirk_reset_paddr() directly.

It will need export tdx_quirk_reset_paddr() for KVM. I think it will be OK?

---

## [7] Yan Zhao — 2026-03-19
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, Mar 19, 2026 at 04:56:10PM +0800, Xiaoyao Li wrote:
> On 3/19/2026 2:45 PM, Yan Zhao wrote:
> > On Thu, Mar 19, 2026 at 11:20:48AM +0800, Xiaoyao Li wrote:
Unlike requiring KVM to call pfn_to_page() before invoking guest private memory
related APIs, Having tdx_reclaim_page() and tdx_reclaim_td_control_pages() to
call page_to_pfn() does not impose unnecessary assumptions of how KVM allocates
memory. So, I think it's fine for them to invoke tdx_quirk_reset_page() which
takes PFN as input.

> So why not considering option 2?
> 
I don't think it's necessary. But if we have to export an extra API, IMHO,
tdx_quirk_reset_pfn() is better than tdx_quirk_reset_paddr(). Otherwise,
why not only expose tdx_quirk_reset_paddr()?

---

## [8] Kiryl Shutsemau — 2026-03-19
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 19, 2026 at 08:57:03AM +0800, Yan Zhao wrote:
> @@ -1639,16 +1644,17 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
>  }

This is pre-existing problem, but shouldn't we respect @level here?
Flush size need to take page size into account.

---

## [9] Kiryl Shutsemau — 2026-03-19
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, Mar 19, 2026 at 08:58:08AM +0800, Yan Zhao wrote:
> @@ -1817,11 +1817,11 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
>  	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))

The same problem. @level is ignored.

---

## [10] Yan Zhao — 2026-03-19
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 19, 2026 at 10:39:14AM +0000, Kiryl Shutsemau wrote:
> On Thu, Mar 19, 2026 at 08:57:03AM +0800, Yan Zhao wrote:
> > @@ -1639,16 +1644,17 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
Hmm, flush size is fixed to PAGE_SIZE, because this series is based on the
upstream code where huge page is not supported, so there's 
"if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))" in KVM.

Though tdh_mem_page_aug() is an API, it is currently only exported to KVM and
uses type kvm_pfn_t. So, is it still acceptable to assume flush size to be
PAGE_SIZE? Honoring level will soon be introduced by huge page patches.

If you think it needs to be fixed before huge page series, what about fixing it
in a separate cleanup patch? IMO, it would be better placed after Sean's cleanup
patch [1], so we can use page_level_size() instead of inventing the wheel.

[1] https://lore.kernel.org/kvm/20260129011517.3545883-2-seanjc@google.com/

---

## [11] Yan Zhao — 2026-03-19
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 19, 2026 at 07:59:53PM +0800, Yan Zhao wrote:
> On Thu, Mar 19, 2026 at 10:39:14AM +0000, Kiryl Shutsemau wrote:
> > On Thu, Mar 19, 2026 at 08:57:03AM +0800, Yan Zhao wrote:
BTW, the cleanup patch would then essentially look like the one in the huge page
series [2]...
[2] https://lore.kernel.org/kvm/20260129011517.3545883-27-seanjc@google.com/

So,  if a cleanup patch before the huge page series is required, maybe just
adding WARN_ON_ONCE(level != PG_LEVEL_4K) in that patch?

> [1] https://lore.kernel.org/kvm/20260129011517.3545883-2-seanjc@google.com/

---

## [12] Kiryl Shutsemau — 2026-03-19
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 19, 2026 at 07:59:53PM +0800, Yan Zhao wrote:
> On Thu, Mar 19, 2026 at 10:39:14AM +0000, Kiryl Shutsemau wrote:
> > On Thu, Mar 19, 2026 at 08:57:03AM +0800, Yan Zhao wrote:

It caught my eye because previously size to flush was passed down to
tdx_clflush_page() in the struct page (although never used there).
With switching to pfn, we give up this information and it has to be
passed separately. It would be easy to miss that in huge page patches,
if we don't pass down level here.

> 
> If you think it needs to be fixed before huge page series, what about fixing it

I am okay with a separate patch.

---

## [13] Edgecombe, Rick P — 2026-03-19
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, 2026-03-19 at 12:57 +0000, Kiryl Shutsemau wrote:
> > Though tdh_mem_page_aug() is an API, it is currently only exported to KVM
> > and

I feel like we argued about this before. But it would be more correct to just
drop level and make it 4k only until huge pages? Otherwise we are tweaking dead
behavior.

---

## [14] Dave Hansen — 2026-03-19
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On 3/18/26 17:57, Yan Zhao wrote:
> Remove the completely unnecessary assumption that memory mapped into a TDX
> guest is backed by refcounted struct page memory. From KVM's point of view,

I think this goes a bit too far.

It's one thing to say that it's more convenient for KVM to stick with
pfns because it's what KVM uses now. Or, that the goals of using 'struct
page' can be accomplished other ways. It's quite another to say what
other bits of the codebase have "business" doing.

Sean, can we tone this down a _bit_ to help guide folks in the future?

> Rip out the misguided struct page assumptions/constraints and instead have

Could we maybe tone down the editorializing a bit, please? Folks can
have honest disagreements about this stuff while not being "misguided".

> the two SEAMCALL wrapper APIs take PFN directly. This ensures that for
> future huge page support in S-EPT, the kernel doesn't pick up even worse

I don't really understand what this is saying.

Is the concern that KVM might want to set up page tables for memory that
differ from how it was allocated? I'm a bit worried that this assumes
something about folios that doesn't always hold.

I think the hugetlbfs gigantic support uses folios in at least a few
spots today.

---

## [15] Edgecombe, Rick P — 2026-03-19
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, 2026-03-19 at 16:56 +0800, Xiaoyao Li wrote:
> > > >     }
> > > > -void tdx_quirk_reset_page(struct page *page)

The kernel has APIs that take non-struct page arg forms and operate on a "page".
For example free_page(), clear_page(), etc. So keeping the "_page" name seems
not too horrible to me.

> > I thought about introducing tdx_quirk_reset_pfn(). But considering
> > tdx_quirk_reset_pfn() has to be an exported API, I'm reluctant to do that.

Yea exporting two functions that do the same thing doesn't seem the right
balance.

> > 
> > Given that even with tdx_quirk_reset_pfn(), it still expects TDX convertible

We can assume struct pages have pfn's pretty safely. So pfn->page, and
especially allocated from far away code, is the cleanup target here.

> 
> Only tdx_sept_remove_private_spte() is doing such conversions. While 

Exporting tdx_quirk_reset_paddr() seems reasonable, except then we have pfn, PA
and struct page across the API. It increases the asymmetry.

We did discuss converting the whole API over to PFN for symmetry. It could
eliminate the control page and guest memory differences.

But this way seems like a more manageable step that addresses the biggest issue.
If we don't want to do a massive cleanup, there will be some stuff left for the
future.

---

## [16] Kiryl Shutsemau — 2026-03-20
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 19, 2026 at 05:27:48PM +0000, Edgecombe, Rick P wrote:
> On Thu, 2026-03-19 at 12:57 +0000, Kiryl Shutsemau wrote:
> > > Though tdh_mem_page_aug() is an API, it is currently only exported to KVM

I guess. But you add one more thing on the list to remember when adding
huge page support. This kind of stuff is easy to miss.

---

## [17] Edgecombe, Rick P — 2026-03-20
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Fri, 2026-03-20 at 12:59 +0000, Kiryl Shutsemau wrote:
> > I feel like we argued about this before. But it would be more correct to
> > just drop level and make it 4k only until huge pages? Otherwise we are

I guess I'm fine either way. I'm not sure Dave will like adding dead branches
though. I suppose huge pages is close enough that we are looking to merge prep
work anyway.

---

## [18] Dave Hansen — 2026-03-20
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On 3/20/26 10:31, Edgecombe, Rick P wrote:
> On Fri, 2026-03-20 at 12:59 +0000, Kiryl Shutsemau wrote:
>>> I feel like we argued about this before. But it would be more correct to

Can we add something that will BUG_ON() or fail to compile when the huge
page support comes around?

I'd much rather have:

	BUG_ON(level != PG_LEVEL_4K);
	tdx_clflush_pfn(pfn);

That go implementing a level argument to tdx_clflush_pfn() now. Then
nobody has to remember. The list to remember is in the code.

---

## [19] Edgecombe, Rick P — 2026-03-20
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Fri, 2026-03-20 at 10:38 -0700, Dave Hansen wrote:
> Can we add something that will BUG_ON() or fail to compile when the huge
> page support comes around?

I like it, but I'm afraid to add BUG_ON()s. Could we do a WARN instead?

Especially since... the ridiculous thing about this is that the clflush is only
needed if CLFLUSH_BEFORE_ALLOC is set in the tdx metadata, which we have yet to
see in any modules. The spec is apparently to give TDX module flexibility for
the future.

In the base series we debated just ignoring it, but at the time it was simpler
to just always flush. So if CLFLUSH_BEFORE_ALLOC never comes along, it is
possible the function will never do any useful work in its life. Tough case for
a BUG_ON().

---

## [20] Yan Zhao — 2026-03-25
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 19, 2026 at 11:05:09AM -0700, Dave Hansen wrote:
> On 3/18/26 17:57, Yan Zhao wrote:
> > Remove the completely unnecessary assumption that memory mapped into a TDX
I explained the background in the cover letter, thinking we could add the link
to the final patches when they are merged.

I can expand the patch logs by providing background explanation as well.

> Sean, can we tone this down a _bit_ to help guide folks in the future?
Sorry for being lazy and not expanding the patch logs from Sean's original
patch tagged "DO NOT MERGE".

> > Rip out the misguided struct page assumptions/constraints and instead have
> 
You are right. I need to make it clear.

> > the two SEAMCALL wrapper APIs take PFN directly. This ensures that for
> > future huge page support in S-EPT, the kernel doesn't pick up even worse
Below is the background of this problem. I'll try to include a short summary in
the next version's patch logs.

In TDX huge page v3, I added logic that assumes PFNs are contained in a single
folio in both TDX's map/unmap paths [1][2]:
	if (start_idx + npages > folio_nr_pages(folio))
		return TDX_OPERAND_INVALID;
This not only assumes the PFNs have corresponding struct page, but also assumes
they must be contained in a single folio, since with only base_page + npages,
it's not easy to get the ith page's pointer without first ensuring the pages are
contained in a single folio.

This should work since current KVM/guest_memfd only allocates memory with
struct page and maps them into S-EPT at a level lower than or equal to the
backend folio size. That is, a single S-EPT mapping cannot span multiple backend
folios.

However, Ackerley's 1G hugetlb-based gmem splits the backend folio [3] ahead of
splitting/unmapping them from S-EPT [4], due to implementation limitations
mentioned at [5]. It makes the warning in [1] hit upon invoking TDX's unmap
callback.

Moreover, Google's future gmem may manage PFNs independently in the future, so
TDX's private memory may have no corresponding struct page, and KVM would map
them via VM_PFNMAP, similar to mapping pass-through MMIOs or other PFNs without
struct page or with non-refcounted struct page in normal VMs. Given that KVM has
suffered a lot from handling VM_PFNMAP memory for non-refcounted struct page [6]
in normal VMs, and TDX mapping/unmapping callbacks have no semantic reason to
dictate where and how KVM/guest_memfd should allocate and map memory, Sean
suggested dropping the unnecessary assumption that memory to be mapped/unmapped
to/from S-EPT must be contained in a single folio (though he didn't object
reasonable sanity checks on if the PFNs are TDX convertible).


[1] https://lore.kernel.org/kvm/20260106101929.24937-1-yan.y.zhao@intel.com
[2] https://lore.kernel.org/kvm/20260106101826.24870-1-yan.y.zhao@intel.com
[3] https://github.com/googleprodkernel/linux-cc/blob/wip-gmem-conversions-hugetlb-restructuring-12-08-25/virt/kvm/guest_memfd.c#L909
[4] https://github.com/googleprodkernel/linux-cc/blob/wip-gmem-conversions-hugetlb-restructuring-12-08-25/virt/kvm/guest_memfd.c#L918
[5] https://lore.kernel.org/kvm/diqzqzrzdfvh.fsf@google.com/
[6] https://lore.kernel.org/all/20241010182427.1434605-1-seanjc@google.com

---

## [21] Edgecombe, Rick P — 2026-03-25
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Wed, 2026-03-25 at 17:10 +0800, Yan Zhao wrote:
> > I don't really understand what this is saying.
> > 

While this patchset is kind of pre-work for TDX huge pages, the reason
to separate it out and push it earlier is because it has some value on
it's own. So I'd think to focus mostly on the impact of the change
today.

How about this justification:
1. Because KVM handles guest memory as PFNs, and the SEAMCALLs under
discussion are only used there, PFN is more natural.

2. The struct page was partly making sure we didn't pass a wrong arg
(typical type safety) and partly ensuring that KVM doesn't pass non-
convertible memory, however the SEAMCALLs themselves can check this for
the kernel. So the case is already covered by warnings.

In conclusion, the PFN is more natural and the original purpose of
struct page is already covered.


Sean said somewhere IIRC that he would have NAKed the struct page thing
if he had seen it, for even the base support. And the two points above
don't actually require discussion of even huge pages. So does it
actually add any value to dive into the issues you list below?

> 
> In TDX huge page v3, I added logic that assumes PFNs are contained in

I think we can adapt to such changes when they eventually come up. It's
not just about not merging code to be used by out-of-tree code. It also
shrinks what we have to consider at each stage. So we can eventually
get there.

>  so TDX's private memory may have no corresponding struct page, and
> KVM would map them via VM_PFNMAP, similar to mapping pass-through

---

## [22] Yan Zhao — 2026-03-27
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 26, 2026 at 12:57:26AM +0800, Edgecombe, Rick P wrote:
> On Wed, 2026-03-25 at 17:10 +0800, Yan Zhao wrote:
> > > I don't really understand what this is saying.
I wanted to mention the issues listed below because I'm not sure if anyone has
the same question as me: why do we have to convert struct page to PFN if they
can both achieve the same purpose, given that currently all private memory
allocated by gmem has struct page backing?

The background can also reduce confusion if the patch log mentions hugepage and
single folio.

So, maybe also avoid mentioning hugepage and single folio things if you think
it's better to just mention the above two points?

> > In TDX huge page v3, I added logic that assumes PFNs are contained in
> > a single folio in both TDX's map/unmap paths [1][2]:
Ok.

> >  so TDX's private memory may have no corresponding struct page, and
> > KVM would map them via VM_PFNMAP, similar to mapping pass-through

---

## [23] Sean Christopherson — 2026-03-31
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Fri, Mar 27, 2026, Yan Zhao wrote:
> On Thu, Mar 26, 2026 at 12:57:26AM +0800, Edgecombe, Rick P wrote:
> > On Wed, 2026-03-25 at 17:10 +0800, Yan Zhao wrote:

Most importantly, having core TDX make assumptions based on the struct page and/or
folio will create subtle dependencies that are easily avoided.

> > Sean said somewhere IIRC that he would have NAKed the struct page thing
> > if he had seen it, for even the base support.

Yes.

> > And the two points above don't actually require discussion of even huge
> > pages. So does it actually add any value to dive into the issues you list

From https://lore.kernel.org/all/aWgyhmTJphGQqO0Y@google.com:

 : I'm not at all opposed to backing guest_memfd with "struct page", quite the
 : opposite.  What I don't want is to bake assumptions into KVM code that doesn't
 : _require_ struct page, because that has cause KVM immense pain in the past.
 : 
 : And I'm strongly opposed to KVM special-casing TDX or anything else, precisely
 : because we struggled through all that pain so that KVM would work better with
 : memory that isn't backed by "struct page", or more specifically, memory that has
 : an associated "struct page", but isn't managed by core MM, e.g. isn't refcounted.

---

## [24] Sean Christopherson — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Mar 19, 2026, Dave Hansen wrote:
> On 3/18/26 17:57, Yan Zhao wrote:
> > Remove the completely unnecessary assumption that memory mapped into a TDX

I strongly disagree on this one.  IMO, super low level APIs have no business
placing unnecessary requirements on callers.  Requiring that the target memory
be convertible?  A-ok because that's an actual requirement of the architecture.
Requiring or assuming anything about "struct page" or folios?  Not ok.

This isn't a convenience thing, it's a core tenent of KVM guest memory managment.
KVM's MMUs work with PFNs, full stop.  A PFN might have been acquired via GUP and
thus a refcounted struct page, but there is a hard boundary in KVM between getting
the page via GUP and installing the PFN into KVM's MMU.

KVM didn't always have a hard boundary, and it took us literally years to undo
the resulting messes.  And the TDX hugepage support that was posted that pulled
information from "struct page" and/or its folio re-introduced the exact type of
flawed assumptions that we spent years purging from KVM.

So yeah, what I wrote was a strongly worded statement, but that was 100% intentional,
because I want to be crystal clear that requiring KVM to pass a struct page is a
complete non-starter for me.

> > Rip out the misguided struct page assumptions/constraints and instead have
> 

FWIW, I'm not trying to say the intent or people's viewpoints were misguided, I'm
saying the code itself is misguided.  AFAICT, the "struct page" stuff was added
to try to harden the TDX implementation, e.g. to guard against effective UAF of
memory that was assigned to a TD.  But my viewpoint is that requiring a struct
page made the overall implemenation _less_ robust, and thus the code is misguided
because its justfication/reasoning was flawed.

> > the two SEAMCALL wrapper APIs take PFN directly. This ensures that for
> > future huge page support in S-EPT, the kernel doesn't pick up even worse

Heh, the concern is that taking a page/folio in the SEAMCALL wrappers will lead
to assumptions that don't always hold.  Specifically, the TDX hugepage support[*]
was building up assumptions that KVM would never attempt to install a hugepage
that didn't fit into a single folio:

+	if (start_idx + npages > folio_nr_pages(folio))
+		return TDX_OPERAND_INVALID;

[*] https://lore.kernel.org/all/20250807094132.4453-1-yan.y.zhao@intel.com

> I think the hugetlbfs gigantic support uses folios in at least a few
> spots today.

Yes, and the in-progress guest_memfd+HugeTLB work will also use folios.  The
potential hiccup with the above folio_nr_pages() assumption is that KVM may want
to shatter folios to 4KiB granularity for tracking purposes, but still map
hugepage when memory is known to be physically contiguous.

That's where a lot of this is coming from.  Taking a "struct page" is a bad
enough assumption on its own (that all TDX private memory is backed by struct page),
but even worse it's a slippery slope to even more bad assumptions (e.g. about how
guest_memfd internally manages its folios).

---

## [25] Dave Hansen — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On 4/2/26 13:47, Sean Christopherson wrote:
> On Thu, Mar 19, 2026, Dave Hansen wrote:
>> On 3/18/26 17:57, Yan Zhao wrote:

I think I understand the motivation now. All I'm saying is that instead
of something like:

	Remove the completely unnecessary assumption that memory mapped
	into a TDX guest is backed by refcounted struct page memory.

I'd rather see something along the lines of

	KVM's MMUs work with PFNs. This is very much an intentional
	design choice. It ensures that the KVM MMUs remains flexible
	and are not too tied to the regular CPU MMUs and the kernel code
	around	them.

	Using 'struct page' for TDX memory is not a good fit anywhere
	near the KVM MMU code.

Would you disagree strongly with that kind of rewording?

---

## [26] Sean Christopherson — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Apr 02, 2026, Dave Hansen wrote:
> On 4/2/26 13:47, Sean Christopherson wrote:
> > On Thu, Mar 19, 2026, Dave Hansen wrote:

Not at all, works for me.

---

## [27] Ackerley Tng — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

Yan Zhao <yan.y.zhao@intel.com> writes:

>
> [...snip...]

Perhaps in some future patch, are we considering also passing pfn
instead of struct page for source? Would we also update
kvm_tdx->page_add_src to be a kvm_pfn_t?

>  	};
>  	u64 ret;

---

## [28] Sean Christopherson — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Apr 02, 2026, Ackerley Tng wrote:
> Yan Zhao <yan.y.zhao@intel.com> writes:
> 

Probably?

I assume you're asking in the context of in-place conversion, where KVM will
allow a single guest_memfd page to be both the source and the dest?

Right now, KVM requires the source page to be a GUP'able page, specifically so
that KVM can obtain a reference and ensure the page isn't freed until KVM is done
with it.  If/when the source and dest are one and the same, then I don't think
we'd want to GUP the page (and there would be no need to since this would all run
while holding gmem's filemap_invalidate_lock()), at which point, yeah, passing a
"struct page" doesn't make much sense, and passing kvm_pfn_t or u64 or whatever
seems like the obvious choice.

---

## [29] Edgecombe, Rick P — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, 2026-04-02 at 16:23 -0700, Ackerley Tng wrote:
> Yan Zhao <yan.y.zhao@intel.com> writes:
> 

Can you remind me, with the new API we were going to do an in-place add right?
Then I'd wonder if we could maybe change tdh_mem_page_add() to only have a
single pfn arg. The passing of ->src_page is kind of awkward already.

Like Ira was playing around with here:
https://lore.kernel.org/kvm/20251105-tdx-init-in-place-v1-1-1196b67d0423@intel.com/

---

## [30] Sean Christopherson — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Apr 02, 2026, Rick P Edgecombe wrote:
> On Thu, 2026-04-02 at 16:23 -0700, Ackerley Tng wrote:
> > Yan Zhao <yan.y.zhao@intel.com> writes:

No.  In-place ADD will be supported, but it won't be mandatory.  Practically
speaking, we can't make it mandatory unless we're willing to completely rip out
support for per-VM attributes (or at least, per-VM PRIVATE tracking).  I suppose
we could require in-place ADD when using per-gmem attributes, but I don't see
the point given that TDH_MEM_PAGE_ADD itself takes a source and dest.

---

## [31] Edgecombe, Rick P — 2026-04-02
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, 2026-04-02 at 16:46 -0700, Sean Christopherson wrote:
> > Can you remind me, with the new API we were going to do an in-place add
> > right?

Thanks. It might still be cleaner to copy clear text from the GUPed page to the
destination page and let the tdh_mem_page_add() call in the map path do it in-
place? Especially if we want to support in-place add as an option, it would make
the code more uniform.

But it sounds like we don't need to decide now.

---

## [32] Paolo Bonzini — 2026-04-04
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On 3/19/26 09:56, Yan Zhao wrote:
> On Thu, Mar 19, 2026 at 04:56:10PM +0800, Xiaoyao Li wrote:
>> So why not considering option 2?

That works for me, it seems the cleanest.

Paolo

---

## [33] Yan Zhao — 2026-04-07
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On Sat, Apr 04, 2026 at 08:39:00AM +0200, Paolo Bonzini wrote:
> On 3/19/26 09:56, Yan Zhao wrote:
> > On Thu, Mar 19, 2026 at 04:56:10PM +0800, Xiaoyao Li wrote:
Hi Paolo,
To avoid misunderstanding: you think only exporting tdx_quirk_reset_paddr() is
the cleanest, right? :)

Thanks
Yan

---

## [34] Yan Zhao — 2026-04-09
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On Tue, Apr 07, 2026 at 08:44:10AM +0800, Yan Zhao wrote:
> On Sat, Apr 04, 2026 at 08:39:00AM +0200, Paolo Bonzini wrote:
> > On 3/19/26 09:56, Yan Zhao wrote:
Could I rename tdx_quirk_reset_page() to tdx_quirk_phymem_page_reset() and only
export tdx_quirk_phymem_page_reset()?

The "phymem_page" is similar to that in tdh_phymem_page_wbinvd_hkid(), indicating
it's operating on physical memory of page size, so it does not confuse people
even though it takes PFN as input. Another benefit is that callers have no need
to specify size, which is always PAGE_SIZE.

---

## [35] Yan Zhao — 2026-04-09
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, Mar 19, 2026 at 10:48:08AM +0000, Kiryl Shutsemau wrote:
> On Thu, Mar 19, 2026 at 08:58:08AM +0800, Yan Zhao wrote:
> > @@ -1817,11 +1817,11 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
There's a "KVM_BUG_ON(level != PG_LEVEL_4K, kvm)" in
tdx_sept_remove_private_spte() before invoking
tdh_phymem_page_wbinvd_hkid() and tdx_quirk_reset_page().

So it should be fine.

---
