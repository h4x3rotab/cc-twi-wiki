---
title: 'struct page to PFN conversion for TDX guest private memory'
date: 2026-04-30
last_reply: 2026-05-27
message_count: 26
participants: ['Yan Zhao', 'Ackerley Tng', 'Edgecombe, Rick P', 'Sean Christopherson', 'Dave Hansen', 'Xiaoyao Li', 'Kiryl Shutsemau']
---

## [1] Yan Zhao — 2026-04-30

Hi

This is v2 of the struct page to PFN conversion series, which converts TDX
guest private memory mapping/unmapping APIs from taking struct page to
taking PFN as input.

v2 is based on v7.1.0-rc1 + Sean's 4 cleanup patches (see details in
section "Base" below). The purpose is to get Dave's Ack, so Sean can take
it from the KVM x86 tree. The full stack of v2 is available at [14].

Compared to v1, v2:
- Rewrote commit messages of patches 1/2 (the conversion patches for
  mapping and unmapping) by specifically explaining the downside of
  assuming guest private memory must be backed by struct page, and
  incorporating Dave's rewording that also works for Sean.

- Updated patch 2 (which is for unmapping) to use tdx_quirk_reset_paddr()
  directly for unmapping guest private memory, and added patch 3 to drop
  the exported function tdx_quirk_reset_page() by having KVM invoke
  tdx_quirk_reset_paddr() in all scenarios, as suggested by Paolo and
  Xiaoyao.

- Split patch 4 (moving mk_keyed_paddr() to .c) out of patch 2, so patch 2
  can focus on the struct page to PFN conversion for unmapping.

Note: as agreed in v1, Kirill's concern about AUG "level" will be addressed
in a separate patch later.


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
how KVM and guest_memfd manage memory [7]. So, Sean suggested converting
from using struct page to PFN for SEAMCALL wrappers operating on guest
private memory [8].

This series therefore converts struct page to PFN for guest private memory
while keeping struct page for TDX control pages, and uses kvm_pfn_t for
type safety.


Sanity check
------------
Reasonable PFN sanity checks in the guest private memory mapping/unmapping
APIs are still agreed upon [9][10], such as checking TDX convertibility to
avoid SEAMCALL failure.

However, we decided not to provide any in-kernel sanity checks to avoid
introducing unnecessary overhead, both because those failures are supposed
to only occur when there are kernel bugs, and due to the lack of
satisfactory tiny checks to ensure convertibility. When unexpected
non-TDX-convertible PFNs are passed in, just let SEAMCALLs fail or have
#MCs or #PFs generated, which are obvious enough in themselves.


Base:
----
This v2 is rebased on top of v7.1.0-rc1 (kvm/next, commit 39f1c201b93f) +
the first 4 patches from Sean's v5 "TDX: Dynamic PAMT + S-EPT Hugepage"
series [11].

Note: due to the instability of v7.1.0-rc1, I also applied series [12] and
[13] to pass CI.


Changelogs:
-----------
v1 [1] --> v2:
    1. Updated patch logs of patches 1/2. (Dave).
    2. Added patch 3 to drop tdx_quirk_reset_page() and export
       tdx_quirk_reset_paddr() only. (Paolo, Xiaoyao)
    3. Split out patch 4 to move mk_keyed_paddr() from .h to .c.
    4. Rebased to v7.1.0-rc1 + Sean's 4 cleanup patches.

Sean's original patch [0] --> v1:
    1. Rebased to kvm-x86-next-2026.03.13.
    2. Split to 2 patches for easy review.  (Rick)
    3. Replaced "u64 pfn" with "kvm_pfn_t pfn"  (Rick)
    4. Dropped using PFN as input to tdx_reclaim_page(). (Rick)
    5. Move mk_keyed_paddr() from tdx.h to tdx.c. 

Thanks
Yan

[0] https://lore.kernel.org/kvm/20260129011517.3545883-26-seanjc@google.com
[1] https://lore.kernel.org/all/20260319005605.8965-1-yan.y.zhao@intel.com
[2] https://lore.kernel.org/all/30d0cef5-82d5-4325-b149-0e99833b8785@intel.com
[3] https://lore.kernel.org/kvm/f4240495-120b-4124-b91a-b365e45bf50a@intel.com
[4] https://lore.kernel.org/kvm/435b8d81-b4de-4933-b0ae-357dea311488@intel.com
[5] https://lore.kernel.org/kvm/1b236a64-d511-49a2-9962-55f4b1eb08e3@intel.com
[6] https://lore.kernel.org/all/20241010182427.1434605-1-seanjc@google.com
[7] https://lore.kernel.org/all/aWgyhmTJphGQqO0Y@google.com
[8] https://lore.kernel.org/all/aWe1tKpFw-As6VKg@google.com
[9] https://lore.kernel.org/all/aWkVLViKBgiVGgaI@google.com
[10] https://lore.kernel.org/all/d119c824-4770-41d2-a926-4ab5268ea3a6@intel.com
[11] https://lore.kernel.org/all/20260129011517.3545883-1-seanjc@google.com
[12] https://lore.kernel.org/all/20260423155611.216805954@infradead.org
[13] https://lore.kernel.org/all/20260428024746.1040531-1-binbin.wu@linux.intel.com
[14] https://github.com/intel-staging/tdx/tree/struct_page_to_pfn_v2


Sean Christopherson (2):
  x86/tdx: Use PFN directly for mapping guest private memory
  x86/tdx: Use PFN directly for unmapping guest private memory

Yan Zhao (2):
  x86/tdx: Drop exported function tdx_quirk_reset_page()
  x86/virt/tdx: Move mk_keyed_paddr() to tdx.c due to no external users

 arch/x86/include/asm/tdx.h  | 21 ++++++-------------
 arch/x86/kvm/vmx/tdx.c      | 17 ++++++++--------
 arch/x86/virt/vmx/tdx/tdx.c | 40 +++++++++++++++++++++----------------
 3 files changed, 37 insertions(+), 41 deletions(-)

---

## [2] Yan Zhao — 2026-04-30
*Subject: [PATCH v2 1/4] x86/tdx: Use PFN directly for mapping guest private memory*

From: Sean Christopherson <seanjc@google.com>

Remove struct page assumptions/constraints in the SEAMCALL wrapper APIs for
mapping guest private memory and have them take PFN directly.

Having core TDX make assumptions that guest private memory must be backed
by struct page (and/or folio) will create subtle dependencies on how
KVM/guest_memfd allocates/manages memory (e.g., whether it uses memory
allocated from core MM, if the memory is refcounted, or if the folio is
split) that are easily avoided. [1].

KVM's MMUs work with PFNs. This is very much an intentional design choice.
It ensures that the KVM MMUs remain flexible and are not too tied to the
regular CPU MMUs and the kernel code around them. Using 'struct page' for
TDX guest memory is not a good fit anywhere near the KVM MMU code [2].

Use "kvm_pfn_t pfn" for type safety. Using this KVM type is appropriate
since APIs tdh_mem_page_add() and tdh_mem_page_aug() are exported to KVM
only.

[ Yan: Replace "u64 pfn" with "kvm_pfn_t pfn" ]

Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Link: https://lore.kernel.org/all/aWgyhmTJphGQqO0Y@google.com [1]
Link: https://lore.kernel.org/all/ac7V0g2q2hN3dU5u@google.com [2]
---
 arch/x86/include/asm/tdx.h  |  6 ++++--
 arch/x86/kvm/vmx/tdx.c      |  7 +++----
 arch/x86/virt/vmx/tdx/tdx.c | 19 ++++++++++++-------
 3 files changed, 19 insertions(+), 13 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 0cb77ed4adc5..619aed134c83 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -6,6 +6,7 @@
 #include <linux/init.h>
 #include <linux/bits.h>
 #include <linux/mmzone.h>
+#include <linux/kvm_types.h>
 
 #include <asm/errno.h>
 #include <asm/ptrace.h>
@@ -189,11 +190,12 @@ static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
 
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
-u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, kvm_pfn_t pfn, struct page *source,
+		     u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, enum pg_level level, struct page *page,
 		     u64 *ext_err1, u64 *ext_err2);
 u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page);
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level, struct page *page,
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level, kvm_pfn_t pfn,
 		     u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, enum pg_level level, u64 *ext_err1,
 			u64 *ext_err2);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 77aea8920a4a..9b47dd257ff4 100644
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
 
@@ -1639,12 +1639,11 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 			    enum pg_level level, kvm_pfn_t pfn)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	struct page *page = pfn_to_page(pfn);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 entry, level_state;
 	u64 err;
 
-	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, level, page, &entry, &level_state);
+	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, level, pfn, &entry, &level_state);
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a6e77afafa79..b24b81cea5ea 100644
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
 static int pg_level_to_tdx_sept_level(enum pg_level level)
 {
 	WARN_ON_ONCE(level == PG_LEVEL_NONE);
@@ -1594,17 +1598,18 @@ u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page)
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
@@ -1647,16 +1652,16 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_addcx);
 
 u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, enum pg_level level,
-		     struct page *page, u64 *ext_err1, u64 *ext_err2)
+		     kvm_pfn_t pfn, u64 *ext_err1, u64 *ext_err2)
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

---

## [3] Yan Zhao — 2026-04-30
*Subject: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest private memory*

From: Sean Christopherson <seanjc@google.com>

Remove struct page assumptions/constraints in APIs for unmapping guest
private memory and have them take physical address directly.

Having core TDX make assumptions that guest private memory must be backed
by struct page (and/or folio) will create subtle dependencies on how
KVM/guest_memfd allocates/manages memory (e.g., whether it uses memory
allocated from core MM, if the memory is refcounted, or if the folio is
split) that are easily avoided. [1].

KVM's MMUs work with PFNs. This is very much an intentional design choice.
It ensures that the KVM MMUs remain flexible and are not too tightly tied
to the regular CPU MMUs and the kernel code around them. Using
"struct page" for TDX guest memory is not a good fit anywhere near the KVM
MMU code [2].

Therefore, for unmapping guest private memory: export
tdx_quirk_reset_paddr() for direct KVM invocation, and convert the SEAMCALL
wrapper API tdh_phymem_page_wbinvd_hkid() to take PFN as input (thus
updating mk_keyed_paddr() and tdh_phymem_page_wbinvd_tdr()).

Intentionally have KVM pass PAGE_SIZE (rather than KVM_HPAGE_SIZE(level))
to tdx_quirk_reset_paddr() in tdx_sept_remove_private_spte() to avoid
mixing in huge page changes. The KVM_BUG_ON() check for !PG_LEVEL_4K in
tdx_sept_remove_private_spte() justifies using PAGE_SIZE.

Do not convert tdx_reclaim_page() to use PFN as input since it currently
does not remove guest private memory.

Use "kvm_pfn_t pfn" for type safety. Using this KVM type is appropriate
since APIs tdh_phymem_page_wbinvd_hkid() and tdx_quirk_reset_paddr() are
exported to KVM only.

[Yan: Use kvm_pfn_t,exclude tdx_reclaim_page(),use tdx_quirk_reset_paddr()]

Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Link: https://lore.kernel.org/all/aWgyhmTJphGQqO0Y@google.com [1]
Link: https://lore.kernel.org/all/ac7V0g2q2hN3dU5u@google.com [2]
---
 arch/x86/include/asm/tdx.h  | 14 +++++---------
 arch/x86/kvm/vmx/tdx.c      |  6 +++---
 arch/x86/virt/vmx/tdx/tdx.c |  9 +++++----
 3 files changed, 13 insertions(+), 16 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 619aed134c83..65f7d874fb5a 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -154,6 +154,7 @@ u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
 void tdx_quirk_reset_page(struct page *page);
+void tdx_quirk_reset_paddr(unsigned long base, unsigned long size);
 
 struct tdx_td {
 	/* TD root structure: */
@@ -177,15 +178,10 @@ struct tdx_vp {
 	struct page **tdcx_pages;
 };
 
-static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
+static inline u64 mk_keyed_paddr(u16 hkid, kvm_pfn_t pfn)
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
@@ -218,7 +214,7 @@ u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, enum pg_level level,
 			u64 *ext_err1, u64 *ext_err2);
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, kvm_pfn_t pfn);
 #else
 static inline void tdx_init(void) { }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 9b47dd257ff4..a2aadc6d0174 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1774,8 +1774,8 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 					 enum pg_level level, u64 mirror_spte)
 {
-	struct page *page = pfn_to_page(spte_to_pfn(mirror_spte));
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 
@@ -1814,11 +1814,11 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
 		return;
 
-	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, page);
+	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, pfn);
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
-	tdx_quirk_reset_page(page);
+	tdx_quirk_reset_paddr(PFN_PHYS(pfn), PAGE_SIZE);
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index b24b81cea5ea..e5a37ea2d4a0 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -710,7 +710,7 @@ static __init int tdmrs_set_up_pamt_all(struct tdmr_info_list *tdmr_list,
  * to normal kernel memory. Systems with the X86_BUG_TDX_PW_MCE erratum need to
  * do the conversion explicitly via MOVDIR64B.
  */
-static void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
+void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
 {
 	const void *zero_page = (const void *)page_address(ZERO_PAGE(0));
 	unsigned long phys, end;
@@ -729,6 +729,7 @@ static void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
 	 */
 	mb();
 }
+EXPORT_SYMBOL_FOR_KVM(tdx_quirk_reset_paddr);
 
 void tdx_quirk_reset_page(struct page *page)
 {
@@ -1920,17 +1921,17 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td)
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

## [4] Yan Zhao — 2026-04-30
*Subject: [PATCH v2 3/4] x86/tdx: Drop exported function tdx_quirk_reset_page()*

KVM invokes tdx_quirk_reset_page() to reset TDX control pages (including
S-EPT pages, TDR page, etc.), as all those pages are allocated by KVM TDX
and thus always have struct page.

However, it's also reasonable for KVM to reset those TDX control pages via
tdx_quirk_reset_paddr() directly, eliminating the need to export two
parallel APIs. Keeping tdx_quirk_reset_page() as a one-line helper in the
header file is also unnecessary.

No functional change intended.

Suggested-by: Paolo Bonzini <pbonzini@redhat.com>
Suggested-by: Xiaoyao Li <xiaoyao.li@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
---
 arch/x86/include/asm/tdx.h  | 1 -
 arch/x86/kvm/vmx/tdx.c      | 4 ++--
 arch/x86/virt/vmx/tdx/tdx.c | 6 ------
 3 files changed, 2 insertions(+), 9 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 65f7d874fb5a..9c63deaa0e8f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -153,7 +153,6 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
-void tdx_quirk_reset_page(struct page *page);
 void tdx_quirk_reset_paddr(unsigned long base, unsigned long size);
 
 struct tdx_td {
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index a2aadc6d0174..9bd4fd748e2a 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -343,7 +343,7 @@ static int tdx_reclaim_page(struct page *page)
 
 	r = __tdx_reclaim_page(page);
 	if (!r)
-		tdx_quirk_reset_page(page);
+		tdx_quirk_reset_paddr(page_to_phys(page), PAGE_SIZE);
 	return r;
 }
 
@@ -597,7 +597,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
 
-	tdx_quirk_reset_page(kvm_tdx->td.tdr_page);
+	tdx_quirk_reset_paddr(page_to_phys(kvm_tdx->td.tdr_page), PAGE_SIZE);
 
 	__free_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index e5a37ea2d4a0..deb67e68f85f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -731,12 +731,6 @@ void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_quirk_reset_paddr);
 
-void tdx_quirk_reset_page(struct page *page)
-{
-	tdx_quirk_reset_paddr(page_to_phys(page), PAGE_SIZE);
-}
-EXPORT_SYMBOL_FOR_KVM(tdx_quirk_reset_page);
-
 static __init void tdmr_quirk_reset_pamt(struct tdmr_info *tdmr)
 
 {

---

## [5] Yan Zhao — 2026-04-30
*Subject: [PATCH v2 4/4] x86/virt/tdx: Move mk_keyed_paddr() to tdx.c due to no external users*

Move mk_keyed_paddr() from tdx.h to tdx.c to avoid unnecessary header
inclusion and improve encapsulation since there are no users outside of
tdx.c.

No functional change intended.
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
---
 arch/x86/include/asm/tdx.h  | 6 ------
 arch/x86/virt/vmx/tdx/tdx.c | 6 ++++++
 2 files changed, 6 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 9c63deaa0e8f..503f9a3f46d6 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -177,12 +177,6 @@ struct tdx_vp {
 	struct page **tdcx_pages;
 };
 
-static inline u64 mk_keyed_paddr(u16 hkid, kvm_pfn_t pfn)
-{
-	/* KeyID bits are just above the physical address bits. */
-	return PFN_PHYS(pfn) | ((u64)hkid << boot_cpu_data.x86_phys_bits);
-}
-
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
 u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, kvm_pfn_t pfn, struct page *source,
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index deb67e68f85f..967482ae3c80 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1911,6 +1911,12 @@ u64 tdh_phymem_cache_wb(bool resume)
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

---

## [6] Ackerley Tng — 2026-04-30
*Subject: Re: [PATCH v2 1/4] x86/tdx: Use PFN directly for mapping guest
 private memory*

Yan Zhao <yan.y.zhao@intel.com> writes:

> From: Sean Christopherson <seanjc@google.com>
>

Thanks for this :)

> Having core TDX make assumptions that guest private memory must be backed
> by struct page (and/or folio) will create subtle dependencies on how

Thanks for your help, Yan!

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

> Signed-off-by: Sean Christopherson <seanjc@google.com>
> Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>

---

## [7] Ackerley Tng — 2026-04-30
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

Yan Zhao <yan.y.zhao@intel.com> writes:

>
> [...snip...]

Could this be updated to use phys_addr_t base and size_t size instead of
generic unsigned long?

>  {
>  	const void *zero_page = (const void *)page_address(ZERO_PAGE(0));

Should mk_keyed_paddr() be updated to have a return type of phys_addr_t?
I guess in this case since mk_keyed_paddr() is pretty much an internal
function, returning u64 also makes sense to indicate that it should only
be used to set 64 bit registers.

>
>  	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

---

## [8] Ackerley Tng — 2026-04-30
*Subject: Re: [PATCH v2 3/4] x86/tdx: Drop exported function tdx_quirk_reset_page()*

Yan Zhao <yan.y.zhao@intel.com> writes:

> KVM invokes tdx_quirk_reset_page() to reset TDX control pages (including
> S-EPT pages, TDR page, etc.), as all those pages are allocated by KVM TDX

Thanks for the cleanup!

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

>
> [...snip...]

---

## [9] Edgecombe, Rick P — 2026-04-30
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, 2026-04-30 at 11:17 -0700, Ackerley Tng wrote:
> Yan Zhao <yan.y.zhao@intel.com> writes:
> 

A type is a really good idea. It could look like a virtual address, despite the
paddr in the name.

I added it to the cleanup list. But I would prefer to keep this series focused
on resolving the critical controversy around the struct page/pfn type, rather
than adding in more things to debate. If you don't mind.

> 
> >   {

Yea, this is used to construct u64 inputs for seamcall args. So I think it
should keep returning u64s. Maybe instead it would be better to have a function
name pattern that denotes that purpose. We have some more helpers like this
coming.

But similarly, I'd like to not grow a snowballing cleanup series for this one.

---

## [10] Sean Christopherson — 2026-04-30
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, Apr 30, 2026, Rick P Edgecombe wrote:
> On Thu, 2026-04-30 at 11:17 -0700, Ackerley Tng wrote:
> > >   {

+1.  IMO, we should treat the TDX-Module as an extension of hardware and pass in
u64s where the spec says it takes a 64-bit value.

---

## [11] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

On 4/30/26 12:20, Sean Christopherson wrote:
>> Yea, this is used to construct u64 inputs for seamcall args. So I think it
>> should keep returning u64s.

+2

In this very specific case 'phys_addr_t' is 100% the *WRONG* type for
mk_keyed_paddr(). Why? Because the thing being returned is *NOT* *A*
*PHYSICAL* *ADDRESS*. It's a composite type that contains a special
physical address plus some metadata in a special "hardware" format. It's
as much of a 'phys_addr_t' as a PTE is a 'phys_addr_t'. Yeah, they
contain and are constructed partly from physical addresses, but they are
not physical addresses themselves.

At the same time, if the kernel has a type-safe way of representing
something that's also a 64-bit value, we should use it. Just because the
TDX spec takes a 64-bit virtual address doesn't mean we should use a u64
and not a "struct foo *".

Let's please just not go back to a sea of u64's everywhere. Use common
sense. Use the kernel's type system where appropriate, but don't
over-apply it.

IOW, I agree with Sean. But please don't take Sean's advise too far here.

---

## [12] Ackerley Tng — 2026-04-30
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

Dave Hansen <dave.hansen@intel.com> writes:

> On 4/30/26 12:20, Sean Christopherson wrote:
>>> Yea, this is used to construct u64 inputs for seamcall args. So I think it

Got it, thanks!

> At the same time, if the kernel has a type-safe way of representing
> something that's also a 64-bit value, we should use it. Just because the

---

## [13] Ackerley Tng — 2026-04-30
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

"Edgecombe, Rick P" <rick.p.edgecombe@intel.com> writes:

> On Thu, 2026-04-30 at 11:17 -0700, Ackerley Tng wrote:
>> Yan Zhao <yan.y.zhao@intel.com> writes:

No worries, please go ahead :)

>>
>> >   {

Makes sense, let's go :)

---

## [14] Xiaoyao Li — 2026-05-07
*Subject: Re: [PATCH v2 1/4] x86/tdx: Use PFN directly for mapping guest
 private memory*

On 4/30/2026 9:49 AM, Yan Zhao wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

...
> +static void tdx_clflush_pfn(kvm_pfn_t pfn)
> +{

If the pfn is not in the kernel direct map, we will get #PF, right?

There is on-going attempt to remove the direct map for guest_memfd. The 
good news is TDX is excluded. [1]

[1] https://lore.kernel.org/all/20260410151746.61150-9-kalyazin@amazon.com/

---

## [15] Xiaoyao Li — 2026-05-07
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

On 4/30/2026 9:49 AM, Yan Zhao wrote:
> From: Sean Christopherson<seanjc@google.com>
> 

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

---

## [16] Xiaoyao Li — 2026-05-07
*Subject: Re: [PATCH v2 3/4] x86/tdx: Drop exported function
 tdx_quirk_reset_page()*

On 4/30/2026 9:50 AM, Yan Zhao wrote:
> KVM invokes tdx_quirk_reset_page() to reset TDX control pages (including
> S-EPT pages, TDR page, etc.), as all those pages are allocated by KVM TDX

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

> ---
>   arch/x86/include/asm/tdx.h  | 1 -

---

## [17] Xiaoyao Li — 2026-05-07
*Subject: Re: [PATCH v2 4/4] x86/virt/tdx: Move mk_keyed_paddr() to tdx.c due
 to no external users*

On 4/30/2026 9:50 AM, Yan Zhao wrote:
> Move mk_keyed_paddr() from tdx.h to tdx.c to avoid unnecessary header
> inclusion and improve encapsulation since there are no users outside of

Missing a new blank line.

> Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

> ---
>   arch/x86/include/asm/tdx.h  | 6 ------

---

## [18] Yan Zhao — 2026-05-07
*Subject: Re: [PATCH v2 1/4] x86/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, May 07, 2026 at 03:49:09PM +0800, Xiaoyao Li wrote:
> On 4/30/2026 9:49 AM, Yan Zhao wrote:
> > From: Sean Christopherson <seanjc@google.com>
Thanks!

> > +static void tdx_clflush_pfn(kvm_pfn_t pfn)
> > +{
Right.

There's no simple interface like pfn_range_is_mapped() that tells whether a PFN
has direct map or not if removing direct map is supported.

So, as PFNs not in the kernel direct map are unexpected for TDX, this series
leaves #PF, which is obvious enough for debugging.

> There is on-going attempt to remove the direct map for guest_memfd. The good
> news is TDX is excluded. [1]
We can see if any code refinement is necessary if TDX is included in the future.

 
> [1] https://lore.kernel.org/all/20260410151746.61150-9-kalyazin@amazon.com/

---

## [19] Sean Christopherson — 2026-05-07
*Subject: Re: [PATCH v2 1/4] x86/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, May 07, 2026, Yan Zhao wrote:
> On Thu, May 07, 2026 at 03:49:09PM +0800, Xiaoyao Li wrote:
> > On 4/30/2026 9:49 AM, Yan Zhao wrote:

Yeah, I wouldn't worry too much about that effort.  The onus will firmly be on
that series to do the right thing for TDX (and any other unique code).

---

## [20] Kiryl Shutsemau — 2026-05-22
*Subject: Re: [PATCH v2 1/4] x86/tdx: Use PFN directly for mapping guest
 private memory*

On Thu, Apr 30, 2026 at 09:49:29AM +0800, Yan Zhao wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

Acked-by: Kiryl Shutsemau <kas@kernel.org>

---

## [21] Kiryl Shutsemau — 2026-05-22
*Subject: Re: [PATCH v2 2/4] x86/tdx: Use PFN directly for unmapping guest
 private memory*

On Thu, Apr 30, 2026 at 09:49:48AM +0800, Yan Zhao wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

Acked-by: Kiryl Shutsemau <kas@kernel.org>

---

## [22] Kiryl Shutsemau — 2026-05-22
*Subject: Re: [PATCH v2 3/4] x86/tdx: Drop exported function
 tdx_quirk_reset_page()*

On Thu, Apr 30, 2026 at 09:50:01AM +0800, Yan Zhao wrote:
> KVM invokes tdx_quirk_reset_page() to reset TDX control pages (including
> S-EPT pages, TDR page, etc.), as all those pages are allocated by KVM TDX

Acked-by: Kiryl Shutsemau <kas@kernel.org>

---

## [23] Kiryl Shutsemau — 2026-05-22
*Subject: Re: [PATCH v2 4/4] x86/virt/tdx: Move mk_keyed_paddr() to tdx.c due
 to no external users*

On Thu, Apr 30, 2026 at 09:50:14AM +0800, Yan Zhao wrote:
> Move mk_keyed_paddr() from tdx.h to tdx.c to avoid unnecessary header
> inclusion and improve encapsulation since there are no users outside of

Add a new line before SoB.

> Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>

Otherwise:

Acked-by: Kiryl Shutsemau <kas@kernel.org>

---

## [24] Sean Christopherson — 2026-05-26
*Subject: Re: [PATCH v2 0/4] struct page to PFN conversion for TDX guest
 private memory*

On Thu, Apr 30, 2026, Yan Zhao wrote:
> Hi
> 

Dave, any concerns?

I'd like to get these into the KVM x86 tree sooner than later, so that we at
least have a fighting chance of landing the S-EPT cleanup (prep work for D-PAMT)
in 7.2.

---

## [25] Dave Hansen — 2026-05-26
*Subject: Re: [PATCH v2 0/4] struct page to PFN conversion for TDX guest
 private memory*

On 5/26/26 12:37, Sean Christopherson wrote:
>> v2 is based on v7.1.0-rc1 + Sean's 4 cleanup patches (see details in
>> section "Base" below). The purpose is to get Dave's Ack, so Sean can take

These look fine to me. They make the code marginally cleaner and the
changelogs are much better at describing the problem now.

Going to Linus via the KVM route is fine with me:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [26] Sean Christopherson — 2026-05-27
*Subject: Re: [PATCH v2 0/4] struct page to PFN conversion for TDX guest
 private memory*

On Thu, 30 Apr 2026 09:48:52 +0800, Yan Zhao wrote:
> This is v2 of the struct page to PFN conversion series, which converts TDX
> guest private memory mapping/unmapping APIs from taking struct page to

Applied to kvm-x86 mmu, thanks!

[1/4] x86/tdx: Use PFN directly for mapping guest private memory
      https://github.com/kvm-x86/linux/commit/6ad0badd765c
[2/4] x86/tdx: Use PFN directly for unmapping guest private memory
      https://github.com/kvm-x86/linux/commit/4c7a1247646c
[3/4] x86/tdx: Drop exported function tdx_quirk_reset_page()
      https://github.com/kvm-x86/linux/commit/4a72a6dc447d
[4/4] x86/virt/tdx: Move mk_keyed_paddr() to tdx.c due to no external users
      https://github.com/kvm-x86/linux/commit/3f330fbb918f

--
https://github.com/kvm-x86/linux/tree/next

---
