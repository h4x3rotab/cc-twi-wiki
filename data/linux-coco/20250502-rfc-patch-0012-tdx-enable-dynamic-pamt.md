---
title: '[RFC, PATCH 00/12] TDX: Enable Dynamic PAMT'
date: 2025-05-02
last_reply: 2025-05-07
message_count: 22
participants: ['Kirill A. Shutemov', 'Huang, Kai', 'Yan Zhao', 'Vishal Annapurve', 'Dave Hansen']
---

## [1] Kirill A. Shutemov — 2025-05-02

This RFC patchset enables Dynamic PAMT in TDX. It is not intended to be
applied, but rather to receive early feedback on the feature design and
enabling.

From our perspective, this feature has a lower priority compared to huge
page support. I will rebase this patchset on top of Yan's huge page
enabling at a later time, as it requires additional work.

Any feedback is welcome. We are open to ideas.

=========================================================================

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

PAMT memory is dynamically allocated as pages gain TDX protections.
It is reclaimed when TDX protections have been removed from all
pages in a contiguous area.

TODO:
  - Rebase on top of Yan's huge page support series. Demotion requires
    additional handling with Dynamic PAMT;
  - Get better vmalloc API from core-mm and simplify patch 02/12.

Kirill A. Shutemov (12):
  x86/virt/tdx: Allocate page bitmap for Dynamic PAMT
  x86/virt/tdx: Allocate reference counters for PAMT memory
  x86/virt/tdx: Add wrappers for TDH.PHYMEM.PAMT.ADD/REMOVE
  x86/virt/tdx: Account PAMT memory and print if in /proc/meminfo
  KVM: TDX: Add tdx_pamt_get()/put() helpers
  KVM: TDX: Allocate PAMT memory in __tdx_td_init()
  KVM: TDX: Allocate PAMT memory in tdx_td_vcpu_init()
  KVM: x86/tdp_mmu: Add phys_prepare() and phys_cleanup() to kvm_x86_ops
  KVM: TDX: Preallocate PAMT pages to be used in page fault path
  KVM: TDX: Hookup phys_prepare() and phys_cleanup() kvm_x86_ops
  KVM: TDX: Reclaim PAMT memory
  x86/virt/tdx: Enable Dynamic PAMT

 arch/x86/include/asm/kvm-x86-ops.h          |   2 +
 arch/x86/include/asm/kvm_host.h             |   5 +
 arch/x86/include/asm/set_memory.h           |   2 +
 arch/x86/include/asm/tdx.h                  |  22 ++
 arch/x86/include/asm/tdx_global_metadata.h  |   1 +
 arch/x86/kvm/mmu/mmu.c                      |  10 +
 arch/x86/kvm/mmu/tdp_mmu.c                  |  47 ++++-
 arch/x86/kvm/vmx/main.c                     |   2 +
 arch/x86/kvm/vmx/tdx.c                      | 215 ++++++++++++++++++--
 arch/x86/kvm/vmx/tdx_errno.h                |   1 +
 arch/x86/kvm/vmx/x86_ops.h                  |   9 +
 arch/x86/mm/Makefile                        |   2 +
 arch/x86/mm/meminfo.c                       |  11 +
 arch/x86/mm/pat/set_memory.c                |   2 +-
 arch/x86/virt/vmx/tdx/tdx.c                 | 211 ++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.h                 |   5 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |   3 +
 virt/kvm/kvm_main.c                         |   1 +
 18 files changed, 522 insertions(+), 29 deletions(-)
 create mode 100644 arch/x86/mm/meminfo.c

---

## [2] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 01/12] x86/virt/tdx: Allocate page bitmap for Dynamic PAMT*

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

With Dynamic PAMT, the kernel no longer needs to allocate PAMT_4K on
boot, but instead must allocate a page bitmap. The TDX module determines
how many bits per page need to be allocated (currently it is 1).

Allocate the bitmap if the kernel boots on a machine with Dynamic PAMT.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h                  |  5 +++++
 arch/x86/include/asm/tdx_global_metadata.h  |  1 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 23 ++++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  3 +++
 4 files changed, 31 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 26ffc792e673..9701876d4e16 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -125,6 +125,11 @@ int tdx_enable(void);
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
index f5e2a937c1e7..c8bfd765e451 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -470,6 +470,18 @@ static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
 	return pamt_sz;
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
+	return ALIGN(pamt_sz, PAGE_SIZE);
+}
+
 /*
  * Locate a NUMA node which should hold the allocation of the @tdmr
  * PAMT.  This node will have some memory covered by the TDMR.  The
@@ -522,7 +534,16 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * and the total PAMT size.
 	 */
 	tdmr_pamt_size = 0;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
+	pgsz = TDX_PS_4K;
+
+	/* With Dynamic PAMT, PAMT_4K is replaced with a bitmap */
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		pamt_size[pgsz] = tdmr_get_pamt_bitmap_sz(tdmr);
+		tdmr_pamt_size += pamt_size[pgsz];
+		pgsz++;
+	}
+
+	for (; pgsz < TDX_PS_NR; pgsz++) {
 		pamt_size[pgsz] = tdmr_get_pamt_sz(tdmr, pgsz,
 					pamt_entry_size[pgsz]);
 		tdmr_pamt_size += pamt_size[pgsz];
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..683925bcc9eb 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -33,6 +33,9 @@ static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 		sysinfo_tdmr->pamt_2m_entry_size = val;
 	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000012, &val)))
 		sysinfo_tdmr->pamt_1g_entry_size = val;
+	if (!ret && tdx_supports_dynamic_pamt(&tdx_sysinfo) &&
+	    !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
+		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;
 
 	return ret;
 }

---

## [3] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for PAMT memory*

The PAMT memory holds metadata for TDX-protected memory. With Dynamic
PAMT, PAMT_4K is allocated on demand. The kernel supplies the TDX module
with a page pair that covers 2M of host physical memory.

The kernel must provide this page pair before using pages from the range
for TDX. If this is not done, any SEAMCALL that attempts to use the
memory will fail.

Allocate reference counters for every 2M range to track PAMT memory
usage. This is necessary to accurately determine when PAMT memory needs
to be allocated and when it can be freed.

This allocation will consume 2MiB for every 1TiB of physical memory.

Tracking PAMT memory usage on the kernel side duplicates what TDX module
does.  It is possible to avoid this by lazily allocating PAMT memory on
SEAMCALL failure and freeing it based on hints provided by the TDX
module when the last user of PAMT memory is no longer present.

However, this approach complicates serialization.

The TDX module takes locks when dealing with PAMT: a shared lock on any
SEAMCALL that uses explicit HPA and an exclusive lock on PAMT.ADD and
PAMT.REMOVE. Any SEAMCALL that uses explicit HPA as an operand may fail
if it races with PAMT.ADD/REMOVE.

Since PAMT is a global resource, to prevent failure the kernel would
need global locking (per-TD is not sufficient). Or, it has to retry on
TDX_OPERATOR_BUSY.

Both options are not ideal, and tracking PAMT usage on the kernel side
seems like a reasonable alternative.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 113 +++++++++++++++++++++++++++++++++++-
 1 file changed, 111 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c8bfd765e451..00e07a0c908a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -29,6 +29,7 @@
 #include <linux/acpi.h>
 #include <linux/suspend.h>
 #include <linux/idr.h>
+#include <linux/vmalloc.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -50,6 +51,8 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
+static atomic_t *pamt_refcounts;
+
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
 
@@ -1035,9 +1038,108 @@ static int config_global_keyid(void)
 	return ret;
 }
 
+atomic_t *tdx_get_pamt_refcount(unsigned long hpa)
+{
+	return &pamt_refcounts[hpa / PMD_SIZE];
+}
+EXPORT_SYMBOL_GPL(tdx_get_pamt_refcount);
+
+static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)
+{
+	unsigned long vaddr;
+	pte_t entry;
+
+	if (!pte_none(ptep_get(pte)))
+		return 0;
+
+	vaddr = __get_free_page(GFP_KERNEL | __GFP_ZERO);
+	if (!vaddr)
+		return -ENOMEM;
+
+	entry = pfn_pte(PFN_DOWN(__pa(vaddr)), PAGE_KERNEL);
+
+	spin_lock(&init_mm.page_table_lock);
+	if (pte_none(ptep_get(pte)))
+		set_pte_at(&init_mm, addr, pte, entry);
+	else
+		free_page(vaddr);
+	spin_unlock(&init_mm.page_table_lock);
+
+	return 0;
+}
+
+static int pamt_refcount_depopulate(pte_t *pte, unsigned long addr,
+				    void *data)
+{
+	unsigned long vaddr;
+
+	vaddr = (unsigned long)__va(PFN_PHYS(pte_pfn(ptep_get(pte))));
+
+	spin_lock(&init_mm.page_table_lock);
+	if (!pte_none(ptep_get(pte))) {
+		pte_clear(&init_mm, addr, pte);
+		free_page(vaddr);
+	}
+	spin_unlock(&init_mm.page_table_lock);
+
+	return 0;
+}
+
+static int alloc_tdmr_pamt_refcount(struct tdmr_info *tdmr)
+{
+	unsigned long start, end;
+
+	start = (unsigned long)tdx_get_pamt_refcount(tdmr->base);
+	end = (unsigned long)tdx_get_pamt_refcount(tdmr->base + tdmr->size);
+	start = round_down(start, PAGE_SIZE);
+	end = round_up(end, PAGE_SIZE);
+
+	return apply_to_page_range(&init_mm, start, end - start,
+				   pamt_refcount_populate, NULL);
+}
+
+static int init_pamt_metadata(void)
+{
+	size_t size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+	struct vm_struct *area;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	/*
+	 * Reserve vmalloc range for PAMT reference counters. It covers all
+	 * physical address space up to max_pfn. It is going to be populated
+	 * from init_tdmr() only for present memory that available for TDX use.
+	 */
+	area = get_vm_area(size, VM_IOREMAP);
+	if (!area)
+		return -ENOMEM;
+
+	pamt_refcounts = area->addr;
+	return 0;
+}
+
+static void free_pamt_metadata(void)
+{
+	size_t size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+
+	size = round_up(size, PAGE_SIZE);
+	apply_to_existing_page_range(&init_mm,
+				     (unsigned long)pamt_refcounts,
+				     size, pamt_refcount_depopulate,
+				     NULL);
+	vfree(pamt_refcounts);
+	pamt_refcounts = NULL;
+}
+
 static int init_tdmr(struct tdmr_info *tdmr)
 {
 	u64 next;
+	int ret;
+
+	ret = alloc_tdmr_pamt_refcount(tdmr);
+	if (ret)
+		return ret;
 
 	/*
 	 * Initializing a TDMR can be time consuming.  To avoid long
@@ -1048,7 +1150,6 @@ static int init_tdmr(struct tdmr_info *tdmr)
 		struct tdx_module_args args = {
 			.rcx = tdmr->base,
 		};
-		int ret;
 
 		ret = seamcall_prerr_ret(TDH_SYS_TDMR_INIT, &args);
 		if (ret)
@@ -1134,10 +1235,15 @@ static int init_tdx_module(void)
 	if (ret)
 		goto err_reset_pamts;
 
+	/* Reserve vmalloc range for PAMT reference counters */
+	ret = init_pamt_metadata();
+	if (ret)
+		goto err_reset_pamts;
+
 	/* Initialize TDMRs to complete the TDX module initialization */
 	ret = init_tdmrs(&tdx_tdmr_list);
 	if (ret)
-		goto err_reset_pamts;
+		goto err_free_pamt_metadata;
 
 	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));
 
@@ -1149,6 +1255,9 @@ static int init_tdx_module(void)
 	put_online_mems();
 	return ret;
 
+err_free_pamt_metadata:
+	free_pamt_metadata();
+
 err_reset_pamts:
 	/*
 	 * Part of PAMTs may already have been initialized by the

---

## [4] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 03/12] x86/virt/tdx: Add wrappers for TDH.PHYMEM.PAMT.ADD/REMOVE*

On a system with Dynamic PAMT enabled, the kernel must allocate memory
for PAMT_4K as needed and reclaim it when it is no longer in use.

The TDX module requires space to store 16 bytes of metadata per page or
8k for every 2M range of physical memory. The TDX module takes this 8k
of memory as a pair of 4k pages. These pages do not need to be contiguous.

The number of pages needed to cover 2M range can grow if size of PAMT
entry increases. tdx_nr_pamt_pages() reports needed number of pages.

TDH.PHYMEM.PAMT.ADD populates PAMT_4K for a given HPA. The kernel must
provide addresses for two pages, covering a 2M range starting from HPA.

TDH.PHYMEM.PAMT.REMOVE withdraws PAMT_4K memory for a given HPA,
returning the addresses of the pages used for PAMT_4K before the call.

Add wrappers for these SEAMCALLs.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  9 ++++++++
 arch/x86/virt/vmx/tdx/tdx.c | 45 +++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  2 ++
 3 files changed, 56 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 9701876d4e16..a134cf3ecd17 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -130,6 +130,11 @@ static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 	return false; /* To be enabled when kernel is ready */
 }
 
+static inline int tdx_nr_pamt_pages(const struct tdx_sys_info *sysinfo)
+{
+	return sysinfo->tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
@@ -197,6 +202,9 @@ u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u6
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_phymem_pamt_add(unsigned long hpa, struct list_head *pamt_pages);
+u64 tdh_phymem_pamt_remove(unsigned long hpa, struct list_head *pamt_pages);
+
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
@@ -204,6 +212,7 @@ static inline int tdx_enable(void)  { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
+static inline int tdx_nr_pamt_pages(const struct tdx_sys_info *sysinfo) { return 0; }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLER__ */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 00e07a0c908a..29defdb7f6bc 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1999,3 +1999,48 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+
+u64 tdh_phymem_pamt_add(unsigned long hpa, struct list_head *pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	struct page *page;
+	u64 *p;
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	p = &args.rdx;
+	list_for_each_entry(page, pamt_pages, lru) {
+		*p = page_to_phys(page);
+		p++;
+	}
+
+	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+}
+EXPORT_SYMBOL_GPL(tdh_phymem_pamt_add);
+
+u64 tdh_phymem_pamt_remove(unsigned long hpa, struct list_head *pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	struct page *page;
+	u64 *p, ret;
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	ret = seamcall_ret(TDH_PHYMEM_PAMT_REMOVE, &args);
+	if (ret)
+		return ret;
+
+	p = &args.rdx;
+	for (int i = 0; i < tdx_nr_pamt_pages(&tdx_sysinfo); i++) {
+		page = phys_to_page(*p);
+		list_add(&page->lru, pamt_pages);
+		p++;
+	}
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tdh_phymem_pamt_remove);
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

## [5] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 04/12] x86/virt/tdx: Account PAMT memory and print if in /proc/meminfo*

PAMT memory can add up to substantial portion of system memory.

Account these pages and print them into /proc/meminfo as TDX.

When no TD running PAMT memory consumption suppose to be zero.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/set_memory.h |  2 ++
 arch/x86/include/asm/tdx.h        |  2 ++
 arch/x86/mm/Makefile              |  2 ++
 arch/x86/mm/meminfo.c             | 11 +++++++++++
 arch/x86/mm/pat/set_memory.c      |  2 +-
 arch/x86/virt/vmx/tdx/tdx.c       | 26 ++++++++++++++++++++++++--
 6 files changed, 42 insertions(+), 3 deletions(-)
 create mode 100644 arch/x86/mm/meminfo.c

diff --git a/arch/x86/include/asm/set_memory.h b/arch/x86/include/asm/set_memory.h
index 8d9f1c9aaa4c..e729e9f86e67 100644
--- a/arch/x86/include/asm/set_memory.h
+++ b/arch/x86/include/asm/set_memory.h
@@ -90,6 +90,8 @@ int set_direct_map_default_noflush(struct page *page);
 int set_direct_map_valid_noflush(struct page *page, unsigned nr, bool valid);
 bool kernel_page_present(struct page *page);
 
+void direct_pages_meminfo(struct seq_file *m);
+
 extern int kernel_set_to_readonly;
 
 #endif /* _ASM_X86_SET_MEMORY_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index a134cf3ecd17..8091bf5b43cc 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -205,6 +205,7 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 u64 tdh_phymem_pamt_add(unsigned long hpa, struct list_head *pamt_pages);
 u64 tdh_phymem_pamt_remove(unsigned long hpa, struct list_head *pamt_pages);
 
+void tdx_meminfo(struct seq_file *m);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
@@ -213,6 +214,7 @@ static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
 static inline int tdx_nr_pamt_pages(const struct tdx_sys_info *sysinfo) { return 0; }
+static inline void tdx_meminfo(struct seq_file *m) {}
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLER__ */
diff --git a/arch/x86/mm/Makefile b/arch/x86/mm/Makefile
index 32035d5be5a0..311d60801871 100644
--- a/arch/x86/mm/Makefile
+++ b/arch/x86/mm/Makefile
@@ -38,6 +38,8 @@ CFLAGS_fault.o := -I $(src)/../include/asm/trace
 
 obj-$(CONFIG_X86_32)		+= pgtable_32.o iomap_32.o
 
+obj-$(CONFIG_PROC_FS)		+= meminfo.o
+
 obj-$(CONFIG_HUGETLB_PAGE)	+= hugetlbpage.o
 obj-$(CONFIG_PTDUMP)		+= dump_pagetables.o
 obj-$(CONFIG_PTDUMP_DEBUGFS)	+= debug_pagetables.o
diff --git a/arch/x86/mm/meminfo.c b/arch/x86/mm/meminfo.c
new file mode 100644
index 000000000000..7bdb5df014de
--- /dev/null
+++ b/arch/x86/mm/meminfo.c
@@ -0,0 +1,11 @@
+#include <linux/proc_fs.h>
+#include <linux/seq_file.h>
+
+#include <asm/set_memory.h>
+#include <asm/tdx.h>
+
+void arch_report_meminfo(struct seq_file *m)
+{
+	direct_pages_meminfo(m);
+	tdx_meminfo(m);
+}
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index def3d9284254..59432b92e80e 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -118,7 +118,7 @@ static void collapse_page_count(int level)
 	direct_pages_count[level - 1] -= PTRS_PER_PTE;
 }
 
-void arch_report_meminfo(struct seq_file *m)
+void direct_pages_meminfo(struct seq_file *m)
 {
 	seq_printf(m, "DirectMap4k:    %8lu kB\n",
 			direct_pages_count[PG_LEVEL_4K] << 2);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 29defdb7f6bc..74bd81acef7b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2000,13 +2000,28 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
 
+static atomic_long_t tdx_pamt_count = ATOMIC_LONG_INIT(0);
+
+void tdx_meminfo(struct seq_file *m)
+{
+	unsigned long usage;
+
+	if (!cpu_feature_enabled(X86_FEATURE_TDX_HOST_PLATFORM))
+		return;
+
+	usage = atomic_long_read(&tdx_pamt_count) *
+		tdx_nr_pamt_pages(&tdx_sysinfo) * PAGE_SIZE / SZ_1K;
+
+	seq_printf(m, "TDX:		%8lu kB\n", usage);
+}
+
 u64 tdh_phymem_pamt_add(unsigned long hpa, struct list_head *pamt_pages)
 {
 	struct tdx_module_args args = {
 		.rcx = hpa,
 	};
 	struct page *page;
-	u64 *p;
+	u64 *p, ret;
 
 	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
 
@@ -2016,7 +2031,12 @@ u64 tdh_phymem_pamt_add(unsigned long hpa, struct list_head *pamt_pages)
 		p++;
 	}
 
-	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+	ret = seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+
+	if (!ret)
+		atomic_long_inc(&tdx_pamt_count);
+
+	return ret;
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_pamt_add);
 
@@ -2034,6 +2054,8 @@ u64 tdh_phymem_pamt_remove(unsigned long hpa, struct list_head *pamt_pages)
 	if (ret)
 		return ret;
 
+	atomic_long_dec(&tdx_pamt_count);
+
 	p = &args.rdx;
 	for (int i = 0; i < tdx_nr_pamt_pages(&tdx_sysinfo); i++) {
 		page = phys_to_page(*p);

---

## [6] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 05/12] KVM: TDX: Add tdx_pamt_get()/put() helpers*

Introduce a pair of helpers to allocate and free memory for a given 2M
range. The range is represented by struct page for any memory in the
range and the PAMT memory by a list of pages.

Use per-2M refcounts to detect when PAMT memory has to be allocated and
when it can be freed.

pamt_lock spinlock serializes against races between multiple
tdx_pamt_add() as well as tdx_pamt_add() vs tdx_pamt_put().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h   |   2 +
 arch/x86/kvm/vmx/tdx.c       | 123 +++++++++++++++++++++++++++++++++++
 arch/x86/kvm/vmx/tdx_errno.h |   1 +
 3 files changed, 126 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 8091bf5b43cc..42449c054938 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -135,6 +135,8 @@ static inline int tdx_nr_pamt_pages(const struct tdx_sys_info *sysinfo)
 	return sysinfo->tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
 }
 
+atomic_t *tdx_get_pamt_refcount(unsigned long hpa);
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index b952bc673271..ea7e2d93fb44 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -207,6 +207,10 @@ static bool tdx_operand_busy(u64 err)
 	return (err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_BUSY;
 }
 
+static bool tdx_hpa_range_not_free(u64 err)
+{
+	return (err & TDX_SEAMCALL_STATUS_MASK) == TDX_HPA_RANGE_NOT_FREE;
+}
 
 /*
  * A per-CPU list of TD vCPUs associated with a given CPU.
@@ -276,6 +280,125 @@ static inline void tdx_disassociate_vp(struct kvm_vcpu *vcpu)
 	vcpu->cpu = -1;
 }
 
+static DEFINE_SPINLOCK(pamt_lock);
+
+static void tdx_free_pamt_pages(struct list_head *pamt_pages)
+{
+	struct page *page;
+
+	while ((page = list_first_entry_or_null(pamt_pages, struct page, lru))) {
+		list_del(&page->lru);
+		__free_page(page);
+	}
+}
+
+static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)
+{
+	for (int i = 0; i < tdx_nr_pamt_pages(tdx_sysinfo); i++) {
+		struct page *page = alloc_page(GFP_KERNEL);
+		if (!page)
+			goto fail;
+		list_add(&page->lru, pamt_pages);
+	}
+	return 0;
+fail:
+	tdx_free_pamt_pages(pamt_pages);
+	return -ENOMEM;
+}
+
+static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
+			struct list_head *pamt_pages)
+{
+	u64 err;
+
+	hpa = ALIGN_DOWN(hpa, SZ_2M);
+
+	spin_lock(&pamt_lock);
+
+	/* Lost race to other tdx_pamt_add() */
+	if (atomic_read(pamt_refcount) != 0) {
+		atomic_inc(pamt_refcount);
+		spin_unlock(&pamt_lock);
+		tdx_free_pamt_pages(pamt_pages);
+		return 0;
+	}
+
+	err = tdh_phymem_pamt_add(hpa | TDX_PS_2M, pamt_pages);
+
+	if (err)
+		tdx_free_pamt_pages(pamt_pages);
+
+	/*
+	 * tdx_hpa_range_not_free() is true if current task won race
+	 * against tdx_pamt_put().
+	 */
+	if (err && !tdx_hpa_range_not_free(err)) {
+		spin_unlock(&pamt_lock);
+		pr_tdx_error(TDH_PHYMEM_PAMT_ADD, err);
+		return -EIO;
+	}
+
+	atomic_set(pamt_refcount, 1);
+	spin_unlock(&pamt_lock);
+	return 0;
+}
+
+static int tdx_pamt_get(struct page *page)
+{
+	unsigned long hpa = page_to_phys(page);
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+
+	if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
+		return 0;
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	WARN_ON_ONCE(atomic_read(pamt_refcount) < 0);
+
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
+	if (tdx_alloc_pamt_pages(&pamt_pages))
+		return -ENOMEM;
+
+	return tdx_pamt_add(pamt_refcount, hpa, &pamt_pages);
+}
+
+static void tdx_pamt_put(struct page *page)
+{
+	unsigned long hpa = page_to_phys(page);
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+	u64 err;
+
+	if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
+		return;
+
+	hpa = ALIGN_DOWN(hpa, SZ_2M);
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	if (!atomic_dec_and_test(pamt_refcount))
+		return;
+
+	spin_lock(&pamt_lock);
+
+	/* Lost race against tdx_pamt_add()? */
+	if (atomic_read(pamt_refcount) != 0) {
+		spin_unlock(&pamt_lock);
+		return;
+	}
+
+	err = tdh_phymem_pamt_remove(hpa | TDX_PS_2M, &pamt_pages);
+	spin_unlock(&pamt_lock);
+
+	if (err) {
+		pr_tdx_error(TDH_PHYMEM_PAMT_REMOVE, err);
+		return;
+	}
+
+	tdx_free_pamt_pages(&pamt_pages);
+}
+
 static void tdx_clear_page(struct page *page)
 {
 	const void *zero_page = (const void *) page_to_virt(ZERO_PAGE(0));
diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/kvm/vmx/tdx_errno.h
index 6ff4672c4181..c8a471d6b991 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/kvm/vmx/tdx_errno.h
@@ -18,6 +18,7 @@
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
+#define TDX_HPA_RANGE_NOT_FREE			0xC000030400000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
 #define TDX_KEY_STATE_INCORRECT			0xC000081100000000ULL

---

## [7] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 06/12] KVM: TDX: Allocate PAMT memory in __tdx_td_init()*

Allocate PAMT memory for TDH.MNG.CREATE and TDH.MNG.ADDCX.

PAMT memory that is associated with pages successfully added to the TD
with TDH.MNG.ADDCX will be removed in tdx_reclaim_page() on
tdx_reclaim_control_page().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 41 +++++++++++++++++++++++++++++++----------
 1 file changed, 31 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ea7e2d93fb44..59bbae2df485 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -399,6 +399,31 @@ static void tdx_pamt_put(struct page *page)
 	tdx_free_pamt_pages(&pamt_pages);
 }
 
+static struct page *tdx_alloc_page(void)
+{
+	struct page *page;
+
+	page = alloc_page(GFP_KERNEL);
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
+
+static void tdx_free_page(struct page *page)
+{
+	if (!page)
+		return;
+
+	tdx_pamt_put(page);
+	__free_page(page);
+}
+
 static void tdx_clear_page(struct page *page)
 {
 	const void *zero_page = (const void *) page_to_virt(ZERO_PAGE(0));
@@ -2499,7 +2524,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	atomic_inc(&nr_configured_hkid);
 
-	tdr_page = alloc_page(GFP_KERNEL);
+	tdr_page = tdx_alloc_page();
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2512,7 +2537,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL);
+		tdcs_pages[i] = tdx_alloc_page();
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2633,10 +2658,8 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 teardown:
 	/* Only free pages not yet added, so start at 'i' */
 	for (; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i]) {
-			__free_page(tdcs_pages[i]);
-			tdcs_pages[i] = NULL;
-		}
+		tdx_free_page(tdcs_pages[i]);
+		tdcs_pages[i] = NULL;
 	}
 	if (!kvm_tdx->td.tdcs_pages)
 		kfree(tdcs_pages);
@@ -2652,15 +2675,13 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 free_tdcs:
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i])
-			__free_page(tdcs_pages[i]);
+		tdx_free_page(tdcs_pages[i]);
 	}
 	kfree(tdcs_pages);
 	kvm_tdx->td.tdcs_pages = NULL;
 
 free_tdr:
-	if (tdr_page)
-		__free_page(tdr_page);
+	tdx_free_page(tdr_page);
 	kvm_tdx->td.tdr_page = 0;
 
 free_hkid:

---

## [8] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 07/12] KVM: TDX: Allocate PAMT memory in tdx_td_vcpu_init()*

Allocate PAMT memory for TDH.VP.CREATE and TDH.VP.ADDCX.

PAMT memory that is associated with pages successfully added to the TD
with TDH.VP.ADDCX will be removed in tdx_reclaim_page() on
tdx_reclaim_control_page().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 13 ++++++-------
 1 file changed, 6 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 59bbae2df485..18c4ae00cd8d 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2983,7 +2983,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL);
+	page = tdx_alloc_page();
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2996,7 +2996,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL);
+		page = tdx_alloc_page();
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;
@@ -3020,7 +3020,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 			 * method, but the rest are freed here.
 			 */
 			for (; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-				__free_page(tdx->vp.tdcx_pages[i]);
+				tdx_free_page(tdx->vp.tdcx_pages[i]);
 				tdx->vp.tdcx_pages[i] = NULL;
 			}
 			return -EIO;
@@ -3039,16 +3039,15 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 
 free_tdcx:
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		if (tdx->vp.tdcx_pages[i])
-			__free_page(tdx->vp.tdcx_pages[i]);
+		tdx_free_page(tdx->vp.tdcx_pages[i]);
 		tdx->vp.tdcx_pages[i] = NULL;
 	}
 	kfree(tdx->vp.tdcx_pages);
 	tdx->vp.tdcx_pages = NULL;
 
 free_tdvpr:
-	if (tdx->vp.tdvpr_page)
-		__free_page(tdx->vp.tdvpr_page);
+	tdx_free_page(tdx->vp.tdvpr_page);
+
 	tdx->vp.tdvpr_page = 0;
 
 	return ret;

---

## [9] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and phys_cleanup() to kvm_x86_ops*

The functions kvm_x86_ops::link_external_spt() and
kvm_x86_ops::set_external_spte() are used to assign new memory to a VM.
When using TDX with Dynamic PAMT enabled, the assigned memory must be
covered by PAMT.

The new function kvm_x86_ops::phys_prepare() is called before
link_external_spt() and set_external_spte() to ensure that the memory is
ready to be assigned to the virtual machine. In the case of TDX, it
makes sure that the memory is covered by PAMT.

kvm_x86_ops::phys_prepare() is called in a context where struct kvm_vcpu
is available, allowing the implementation to allocate memory from a
per-VCPU pool.

The function kvm_x86_ops::phys_cleanup() frees PAMT memory in case of
failure.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  2 ++
 arch/x86/include/asm/kvm_host.h    |  3 ++
 arch/x86/kvm/mmu/tdp_mmu.c         | 47 +++++++++++++++++++++++++++---
 3 files changed, 48 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 79406bf07a1c..37081d04e82f 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -99,6 +99,8 @@ KVM_X86_OP_OPTIONAL(link_external_spt)
 KVM_X86_OP_OPTIONAL(set_external_spte)
 KVM_X86_OP_OPTIONAL(free_external_spt)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
+KVM_X86_OP_OPTIONAL(phys_prepare)
+KVM_X86_OP_OPTIONAL(phys_cleanup)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 6c06f3d6e081..91958c55f918 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1813,6 +1813,9 @@ struct kvm_x86_ops {
 	int (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				    kvm_pfn_t pfn_for_gfn);
 
+	int (*phys_prepare)(struct kvm_vcpu *vcpu, kvm_pfn_t pfn);
+	void (*phys_cleanup)(kvm_pfn_t pfn);
+
 	bool (*has_wbinvd_exit)(void);
 
 	u64 (*get_l2_tsc_offset)(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 405874f4d088..f6c836b2e6fc 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1137,6 +1137,26 @@ void kvm_tdp_mmu_invalidate_roots(struct kvm *kvm,
 	}
 }
 
+static int tdp_mmu_install_spte(struct kvm_vcpu *vcpu,
+				struct tdp_iter *iter,
+				u64 spte)
+{
+	kvm_pfn_t pfn = 0;
+	int ret = 0;
+
+	if (is_mirror_sptep(iter->sptep) && !is_frozen_spte(spte)) {
+		pfn = spte_to_pfn(spte);
+		ret = static_call(kvm_x86_phys_prepare)(vcpu, pfn);
+	}
+	if (ret)
+		return ret;
+	ret = tdp_mmu_set_spte_atomic(vcpu->kvm, iter, spte);
+	if (pfn && ret)
+		static_call(kvm_x86_phys_cleanup)(pfn);
+
+	return ret;
+}
+
 /*
  * Installs a last-level SPTE to handle a TDP page fault.
  * (NPT/EPT violation/misconfiguration)
@@ -1170,7 +1190,7 @@ static int tdp_mmu_map_handle_target_level(struct kvm_vcpu *vcpu,
 
 	if (new_spte == iter->old_spte)
 		ret = RET_PF_SPURIOUS;
-	else if (tdp_mmu_set_spte_atomic(vcpu->kvm, iter, new_spte))
+	else if (tdp_mmu_install_spte(vcpu, iter, new_spte))
 		return RET_PF_RETRY;
 	else if (is_shadow_present_pte(iter->old_spte) &&
 		 (!is_last_spte(iter->old_spte, iter->level) ||
@@ -1211,7 +1231,7 @@ static int tdp_mmu_map_handle_target_level(struct kvm_vcpu *vcpu,
  * Returns: 0 if the new page table was installed. Non-0 if the page table
  *          could not be installed (e.g. the atomic compare-exchange failed).
  */
-static int tdp_mmu_link_sp(struct kvm *kvm, struct tdp_iter *iter,
+static int __tdp_mmu_link_sp(struct kvm *kvm, struct tdp_iter *iter,
 			   struct kvm_mmu_page *sp, bool shared)
 {
 	u64 spte = make_nonleaf_spte(sp->spt, !kvm_ad_enabled);
@@ -1230,6 +1250,25 @@ static int tdp_mmu_link_sp(struct kvm *kvm, struct tdp_iter *iter,
 	return 0;
 }
 
+static int tdp_mmu_link_sp(struct kvm_vcpu *vcpu, struct tdp_iter *iter,
+			   struct kvm_mmu_page *sp, bool shared)
+{
+	kvm_pfn_t pfn = 0;
+	int ret = 0;
+
+	if (sp->external_spt) {
+		pfn = __pa(sp->external_spt) >> PAGE_SHIFT;
+		ret = static_call(kvm_x86_phys_prepare)(vcpu, pfn);
+		if (ret)
+			return ret;
+	}
+	ret = __tdp_mmu_link_sp(vcpu->kvm, iter, sp, shared);
+	if (pfn && ret)
+		static_call(kvm_x86_phys_cleanup)(pfn);
+
+	return ret;
+}
+
 static int tdp_mmu_split_huge_page(struct kvm *kvm, struct tdp_iter *iter,
 				   struct kvm_mmu_page *sp, bool shared);
 
@@ -1288,7 +1327,7 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 			KVM_BUG_ON(is_mirror_sptep(iter.sptep), vcpu->kvm);
 			r = tdp_mmu_split_huge_page(kvm, &iter, sp, true);
 		} else {
-			r = tdp_mmu_link_sp(kvm, &iter, sp, true);
+			r = tdp_mmu_link_sp(vcpu, &iter, sp, true);
 		}
 
 		/*
@@ -1514,7 +1553,7 @@ static int tdp_mmu_split_huge_page(struct kvm *kvm, struct tdp_iter *iter,
 	 * correctness standpoint since the translation will be the same either
 	 * way.
 	 */
-	ret = tdp_mmu_link_sp(kvm, iter, sp, shared);
+	ret = __tdp_mmu_link_sp(kvm, iter, sp, shared);
 	if (ret)
 		goto out;

---

## [10] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 09/12] KVM: TDX: Preallocate PAMT pages to be used in page fault path*

Preallocate a page to be used in the link_external_spt() and
set_external_spte() paths.

In the worst-case scenario, handling a page fault might require a
tdx_nr_pamt_pages() pages for each page table level.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/kvm_host.h |  2 ++
 arch/x86/kvm/mmu/mmu.c          | 10 ++++++++++
 2 files changed, 12 insertions(+)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 91958c55f918..a5661499a176 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -849,6 +849,8 @@ struct kvm_vcpu_arch {
 	 */
 	struct kvm_mmu_memory_cache mmu_external_spt_cache;
 
+	struct kvm_mmu_memory_cache pamt_page_cache;
+
 	/*
 	 * QEMU userspace and the guest each have their own FPU state.
 	 * In vcpu_run, we switch between the user and guest FPU contexts.
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index a284dce227a0..7bfa0dc50440 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -616,6 +616,15 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 		if (r)
 			return r;
 	}
+
+	if (vcpu->kvm->arch.vm_type == KVM_X86_TDX_VM) {
+		int nr = tdx_nr_pamt_pages(tdx_get_sysinfo());
+		r = kvm_mmu_topup_memory_cache(&vcpu->arch.pamt_page_cache,
+					       nr * PT64_ROOT_MAX_LEVEL);
+		if (r)
+			return r;
+	}
+
 	return kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_page_header_cache,
 					  PT64_ROOT_MAX_LEVEL);
 }
@@ -626,6 +635,7 @@ static void mmu_free_memory_caches(struct kvm_vcpu *vcpu)
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadow_page_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadowed_info_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_external_spt_cache);
+	kvm_mmu_free_memory_cache(&vcpu->arch.pamt_page_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_page_header_cache);
 }

---

## [11] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 10/12] KVM: TDX: Hookup phys_prepare() and phys_cleanup() kvm_x86_ops*

Allocate PAMT memory from a per-VCPU pool in kvm_x86_ops::phys_prepare()
and release memory in kvm_x86_ops::phys_cleanup().

The TDP code invokes these callbacks to handle PAMT memory management.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kvm/vmx/main.c    |  2 ++
 arch/x86/kvm/vmx/tdx.c     | 30 ++++++++++++++++++++++++++++++
 arch/x86/kvm/vmx/x86_ops.h |  9 +++++++++
 virt/kvm/kvm_main.c        |  1 +
 4 files changed, 42 insertions(+)

diff --git a/arch/x86/kvm/vmx/main.c b/arch/x86/kvm/vmx/main.c
index 94d5d907d37b..665a3dbd4ba5 100644
--- a/arch/x86/kvm/vmx/main.c
+++ b/arch/x86/kvm/vmx/main.c
@@ -63,6 +63,8 @@ static __init int vt_hardware_setup(void)
 		vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
 		vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;
 		vt_x86_ops.protected_apic_has_interrupt = tdx_protected_apic_has_interrupt;
+		vt_x86_ops.phys_prepare = tdx_phys_prepare;
+		vt_x86_ops.phys_cleanup = tdx_phys_cleanup;
 	}
 
 	return 0;
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 18c4ae00cd8d..0f06ae7ff6b9 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1958,6 +1958,36 @@ int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	return tdx_sept_drop_private_spte(kvm, gfn, level, page);
 }
 
+int tdx_phys_prepare(struct kvm_vcpu *vcpu, kvm_pfn_t pfn)
+{
+	unsigned long hpa = pfn << PAGE_SHIFT;
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+
+	if (!tdx_supports_dynamic_pamt(tdx_sysinfo))
+		return 0;
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
+	for (int i = 0; i < tdx_nr_pamt_pages(tdx_sysinfo); i++) {
+		struct page *page;
+		void *p;
+
+		p = kvm_mmu_memory_cache_alloc(&vcpu->arch.pamt_page_cache);
+		page = virt_to_page(p);
+		list_add(&page->lru, &pamt_pages);
+	}
+
+	return tdx_pamt_add(pamt_refcount, hpa, &pamt_pages);
+}
+
+void tdx_phys_cleanup(kvm_pfn_t pfn)
+{
+	tdx_pamt_put(pfn_to_page(pfn));
+}
+
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,
 			   int trig_mode, int vector)
 {
diff --git a/arch/x86/kvm/vmx/x86_ops.h b/arch/x86/kvm/vmx/x86_ops.h
index 6bf8be570b2e..111f16c3039f 100644
--- a/arch/x86/kvm/vmx/x86_ops.h
+++ b/arch/x86/kvm/vmx/x86_ops.h
@@ -158,6 +158,8 @@ int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 			      enum pg_level level, kvm_pfn_t pfn);
 int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 				 enum pg_level level, kvm_pfn_t pfn);
+int tdx_phys_prepare(struct kvm_vcpu *vcpu, kvm_pfn_t pfn);
+void tdx_phys_cleanup(kvm_pfn_t pfn);
 
 void tdx_flush_tlb_current(struct kvm_vcpu *vcpu);
 void tdx_flush_tlb_all(struct kvm_vcpu *vcpu);
@@ -224,6 +226,13 @@ static inline int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	return -EOPNOTSUPP;
 }
 
+static inline int tdx_phys_prepare(struct kvm_vcpu *vcpu, kvm_pfn_t pfn)
+{
+	return -EOPNOTSUPP;
+}
+
+static inline void tdx_phys_cleanup(kvm_pfn_t pfn) {}
+
 static inline void tdx_flush_tlb_current(struct kvm_vcpu *vcpu) {}
 static inline void tdx_flush_tlb_all(struct kvm_vcpu *vcpu) {}
 static inline void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int root_level) {}
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 69782df3617f..c3ba3ca37940 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -436,6 +436,7 @@ void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 	BUG_ON(!p);
 	return p;
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_memory_cache_alloc);
 #endif
 
 static void kvm_vcpu_init(struct kvm_vcpu *vcpu, struct kvm *kvm, unsigned id)

---

## [12] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 11/12] KVM: TDX: Reclaim PAMT memory*

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

Add tdx_pamt_put() in these code paths.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 8 +++++++-
 1 file changed, 7 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0f06ae7ff6b9..352f7b41f611 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -487,8 +487,11 @@ static int tdx_reclaim_page(struct page *page)
 	int r;
 
 	r = __tdx_reclaim_page(page);
-	if (!r)
+	if (!r) {
 		tdx_clear_page(page);
+		tdx_pamt_put(page);
+	}
+
 	return r;
 }
 
@@ -737,6 +740,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 		return;
 	}
 	tdx_clear_page(kvm_tdx->td.tdr_page);
+	tdx_pamt_put(kvm_tdx->td.tdr_page);
 
 	__free_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
@@ -1768,6 +1772,7 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
 		return -EIO;
 	}
 	tdx_clear_page(page);
+	tdx_pamt_put(page);
 	tdx_unpin(kvm, page);
 	return 0;
 }
@@ -1848,6 +1853,7 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level) &&
 	    !KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm)) {
 		atomic64_dec(&kvm_tdx->nr_premapped);
+		tdx_pamt_put(page);
 		tdx_unpin(kvm, page);
 		return 0;
 	}

---

## [13] Kirill A. Shutemov — 2025-05-02
*Subject: [RFC, PATCH 12/12] x86/virt/tdx: Enable Dynamic PAMT*

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
---
 arch/x86/include/asm/tdx.h  | 6 +++++-
 arch/x86/virt/vmx/tdx/tdx.c | 8 ++++++++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 3 files changed, 13 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 42449c054938..5744f98d193e 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -32,6 +32,10 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_DYNAMIC_PAMT	BIT_ULL(36)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -127,7 +131,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT;
 }
 
 static inline int tdx_nr_pamt_pages(const struct tdx_sys_info *sysinfo)
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 74bd81acef7b..f35566c0588d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -945,6 +945,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
+#define TDX_SYS_CONFIG_DYNAMIC_PAMT	BIT(16)
+
 static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
@@ -972,6 +974,12 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
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

## [14] Huang, Kai — 2025-05-05
*Subject: Re: [RFC, PATCH 01/12] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Fri, 2025-05-02 at 16:08 +0300, Kirill A. Shutemov wrote:
> --- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
> +++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c

Currently the global metadata reading code is auto-generated by script, which is
not in upstream yet.  It doesn't support generating code to support reading some
field "enumerated by" some TDX feature either.

I'll try to upstream the script and add also the "enumerated by" support in the
script.

---

## [15] Huang, Kai — 2025-05-05
*Subject: Re: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

> +static atomic_t *pamt_refcounts;
> +

It's not quite clear why this function needs to be exported in this patch.  IMO
it's better to move the export to the patch which actually needs it.

Looking at patch 5, tdx_pamt_get()/put() use it, and they are in KVM code.  But
I think we should just put them here in this file.  tdx_alloc_page() and
tdx_free_page() should be in this file too.

And instead of exporting tdx_get_pamt_refcount(), the TDX core code here can
export tdx_alloc_page() and tdx_free_page(), providing two high level helpers to
allow the TDX users (e.g., KVM) to allocate/free TDX private pages.  How PAMT
pages are allocated is then hidden in the core TDX code.

> +
> +static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)

IIUC, populating refcount based on TDMR will slightly waste memory.  The reason
is IIUC we don't need to populate the refcount for a 2M range if the range is
completely marked as reserved in TDMR, because it's not possible for the kernel
to use such range for TDX.

Populating based on the list of TDX memory blocks should be better.  In
practice, the difference should be unnoticeable, but conceptually, using TDX
memory blocks is better.

> +
> +static int init_pamt_metadata(void)

---

## [16] Huang, Kai — 2025-05-05
*Subject: Re: [RFC, PATCH 05/12] KVM: TDX: Add tdx_pamt_get()/put() helpers*

On Fri, 2025-05-02 at 16:08 +0300, Kirill A. Shutemov wrote:
> Introduce a pair of helpers to allocate and free memory for a given 2M
> range. The range is represented by struct page for any memory in the

Maybe elaborate a little bit on _why_ using spinlock?

> 
> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

This at least needs to be in the same patch which exports it.  But as replied to
patch 2, I think we should just move the code in this patch to TDX core code.

>  int tdx_guest_keyid_alloc(void);
>  u32 tdx_get_nr_guest_keyids(void);

Just curious, Can the lock be per-2M-range?

> +
> +	/* Lost race to other tdx_pamt_add() */

It's unfortunate multiple caller of tdx_pamt_add() needs to firstly allocate
PAMT pages by the caller out of the spinlock and then free them here.

I am thinking if we make tdx_pamt_add() return:

	* > 0: PAMT pages already added (another tdx_pamt_add() won)
	* = 0: PAMT pages added successfully
	* < 0: error code

.. then we at least could move tdx_free_pamt_pages() to the caller too.

> +		return 0;
> +	}

Seems we are calling tdx_free_pamt_pages() within spinlock, which is not
consistent with above when another tdx_pamt_add() has won the race.

> +
> +	/*

I had hard time to figure out why we need to handle tdx_hpa_range_not_free()
explicitly.  IIUC, it is because atomic_dec_and_test() is used in
tdx_pamt_put(), in which case the atomic_t can reach to 0 outside of the
spinlock thus tdh_phymem_pamt_add() can be called when there's still PAMT pages
populated.

But ...

> +
> +	atomic_set(pamt_refcount, 1);

... if we set the initial value of pamt_refcount to -1, and use
atomic_inc_unless_negetive() here:

	if (atomic_inc_unless_negative(pamt_refcount))
		return 0;

	if (tdx_alloc_pamt_pages(&pamt_pages))
		return -ENOMEM;

	spin_lock(&pamt_lock);
	ret = tdx_pamt_add(hpa, &pamt_pages);
	if (ret >= 0)
		atomic_inc(pamt_refcount, 0);
	spin_unlock(&pamt_lock);
	
	/*
	 * If another tdx_pamt_get() won the race, or in case of
	 * error, PAMT pages are not used and can be freed.
	 */
	if (ret)
		tdx_free_pamt_pages(&pamt_pages);

	return ret >= 0 ? 0 : ret;

and ...

> +
> +	if (tdx_alloc_pamt_pages(&pamt_pages))

... use atomic_dec_if_possible() here, we should be able to avoid the special
handling of tdx_hpa_range_not_free() in tdx_pamt_get().  Someething like:

	if (atomic_dec_if_positive(pamt_refcount) >= 0)
		return;

	spin_lock(&pamt_lock);
	
	/* tdx_pamt_get() called more than once */
	if (atomic_read(pamt_refcount) > 0) {
		spin_unlock(&pamt_lock);
		return;
	}

	err = tdh_phymem_pamt_remove(hpa | TDX_PS_2M, &pamt_pages);
	atomic_set(pamt_refcount, -1);
	spin_unlock(&pamt_lock);

	tdx_free_pamt_pages(&pamt_pages);

Hmm.. am I missing anything?
			
> +
> +	spin_lock(&pamt_lock);

---

## [17] Huang, Kai — 2025-05-05
*Subject: Re: [RFC, PATCH 06/12] KVM: TDX: Allocate PAMT memory in
 __tdx_td_init()*

On Fri, 2025-05-02 at 16:08 +0300, Kirill A. Shutemov wrote:
>  
> +static struct page *tdx_alloc_page(void)

IMO the two should be moved to the TDX core code, and exported for KVM to use.

They can be used for other kernel components for TDX Connect.

---

## [18] Yan Zhao — 2025-05-06
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Fri, May 02, 2025 at 04:08:24PM +0300, Kirill A. Shutemov wrote:
> The functions kvm_x86_ops::link_external_spt() and
> kvm_x86_ops::set_external_spte() are used to assign new memory to a VM.
Why not invoke phys_prepare() and phys_cleanup() in set_external_spte_present()?
Or in tdx_sept_set_private_spte()/tdx_sept_link_private_spt()?

> The function kvm_x86_ops::phys_cleanup() frees PAMT memory in case of
> failure.

---

## [19] Yan Zhao — 2025-05-07
*Subject: Re: [RFC, PATCH 05/12] KVM: TDX: Add tdx_pamt_get()/put() helpers*

On Mon, May 05, 2025 at 08:44:26PM +0800, Huang, Kai wrote:
> On Fri, 2025-05-02 at 16:08 +0300, Kirill A. Shutemov wrote:
> > +static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
Me too.
Could we introduce smaller locks each covering a 2M range?

And could we deposit 2 pamt pages per-2M hpa range no matter if it's finally
mapped as a huge page or not?

---

## [20] Vishal Annapurve — 2025-05-06
*Subject: Re: [RFC, PATCH 05/12] KVM: TDX: Add tdx_pamt_get()/put() helpers*

On Tue, May 6, 2025 at 6:04 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> On Mon, May 05, 2025 at 08:44:26PM +0800, Huang, Kai wrote:

Are you suggesting to keep 2 PAMT pages allocated for each private 2M
page even if it's mapped as a hugepage? It will lead to wastage of
memory of 4 MB per 1GB of guest memory range. For large VM sizes that
will amount to high values.

---

## [21] Yan Zhao — 2025-05-07
*Subject: Re: [RFC, PATCH 05/12] KVM: TDX: Add tdx_pamt_get()/put() helpers*

On Tue, May 06, 2025 at 06:15:40PM -0700, Vishal Annapurve wrote:
> On Tue, May 6, 2025 at 6:04 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
> >
Ok. I'm thinking of the possibility to aligning the time of PAMT page allocation
to that of physical page allocation.

---

## [22] Dave Hansen — 2025-05-07
*Subject: Re: [RFC, PATCH 05/12] KVM: TDX: Add tdx_pamt_get()/put() helpers*

On 5/5/25 05:44, Huang, Kai wrote:
>> +static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
>> +			struct list_head *pamt_pages)

Folks, please keep it simple.

If there's lock contention on this, we'll fix the lock contention, or
hash the physical address into a fixed number of locks. But having it be
per-2M-range sounds awful. Then you have to size it, and allocate it and
then resize it if there's ever hotplug, etc...

Kirill, could you put together some kind of torture test for this,
please? I would imagine a workload which is sitting in a loop setting up
and tearing down VMs on a bunch of CPUs would do it.

That ^ would be the worst possible case, I think. If you don't see lock
contention there, you'll hopefully never see it on real systems.

I *suspect* that real systems will get bottlenecked somewhere in the
page conversion process rather than on this lock. But it should be a
pretty simple experiment to run.

---
