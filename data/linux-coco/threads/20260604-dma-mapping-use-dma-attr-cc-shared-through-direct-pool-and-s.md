---
title: 'dma-mapping: Use DMA_ATTR_CC_SHARED through direct, pool and swiotlb paths'
date: 2026-06-04
last_reply: 2026-06-29
message_count: 67
participants: ['Aneesh Kumar K.V (Arm)', 'JAEHOON KIM', 'Petr Tesarik', 'Catalin Marinas', 'Jason Gunthorpe', 'Alexey Kardashevskiy']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-06-04

This series propagates DMA_ATTR_CC_SHARED through the dma-direct,
dma-pool, and swiotlb paths so that encrypted and decrypted DMA buffers
are handled consistently.

Today, the direct DMA path mostly relies on force_dma_unencrypted() for
shared/decrypted buffer handling. This series consolidates the
force_dma_unencrypted() checks in the top-level functions and ensures
that the remaining DMA interfaces use DMA attributes to make the correct
decisions.

The series:
- moves swiotlb-backed allocations out of __dma_direct_alloc_pages(),
- propagates DMA_ATTR_CC_SHARED through the dma-direct alloc/free
  paths
- teaches the atomic DMA pools to track encrypted versus decrypted
  state
- tracks swiotlb pool encryption state and enforces strict pool
  selection
- centralizes encrypted/decrypted pgprot handling in dma_pgprot() using
  DMA attributes
- passes DMA attributes down to dma_capable() so capability checks can
  validate whether the selected DMA address encoding matches
  DMA_ATTR_CC_SHARED
- makes dma_direct_map_phys() choose the DMA address encoding from
  DMA_ATTR_CC_SHARED and fall back to swiotlb when a shared DMA request
  cannot use the direct mapping, which lets arm64 and x86 CCA guests stop
  relying on SWIOTLB_FORCE for DMA mappings
- use the selected swiotlb pool state to derive the returned DMA
  address.

Changes since v5:
https://lore.kernel.org/all/20260522042815.370873-1-aneesh.kumar@kernel.org
* Add Tested-by
* Drop the pKVM patch, which has now been posted separately:
  https://lore.kernel.org/all/20260603110522.3331819-1-smostafa@google.com
* Remove the DO_NOT_MERGE tag from the s390 change.
* Add a patch to drop the SWIOTLB_FORCE flag.
* Rebase onto the latest kernel.

Changes since v4:
https://lore.kernel.org/all/20260512090408.794195-1-aneesh.kumar@kernel.org
* Add new patches based on Sashiko review:
  swiotlb: Preserve allocation virtual address for dynamic pools
  dma: free atomic pool pages by physical address
  dma: swiotlb: handle set_memory_decrypted() failures
  dma: swiotlb: free dynamic pools from process context
  iommu/dma: Check atomic pool allocation result directly
* Include pKVM and s390 changes as dependent patches. These are not yet
  ready to merge and are waiting for subsystem testing feedback.
* Drop the AMD GART patch because it requires wider testing.
* Update swiotlb_tbl_map_single() to take attrs by reference.
* Switch swiotlb_free() to use rcu_work.
* Avoid calling swiotlb_find_pool() multiple times in the free path.
* Make DMA_ATTR_MMIO imply DMA_ATTR_CC_SHARED for devices requiring unencrypted DMA.

Changes from v3:
https://lore.kernel.org/all/20260427055509.898190-1-aneesh.kumar@kernel.org
* Handle DMA_ATTR_MMIO correctly in dma_direct_map_phys()
* Address most of sashiko review
* Rebase to latest kernel
* drop SWIOTLB_FORCE for s390 and powerpc secure guest.

Changes from v2:
https://lore.kernel.org/all/20260420061415.3650870-1-aneesh.kumar@kernel.org
* pass attrs to dma_capable() and update direct, swiotlb, Xen swiotlb, and
  x86 GART paths so the capability checks see the DMA address attr value
  DMA_ATTR_CC_SHARED.
* rework dma_direct_map_phys() so DMA_ATTR_CC_SHARED selects
  phys_to_dma_unencrypted() while the default path uses
  phys_to_dma_encrypted(), with swiotlb fallback when the requested
  shared/private state cannot be satisfied by a direct DMA address.
* stop relying on SWIOTLB_FORCE for arm64 and x86 CC guest DMA mappings;
  swiotlb is still enabled there, but shared mappings is now selected
  through the generic dma_direct_map_phys()/dma_capable() decision instead
  of a global force-bounce flag.

Changes from v1:
https://lore.kernel.org/all/20260417085900.3062416-1-aneesh.kumar@kernel.org
* rebased to latest kernel (change from DMA_ATTR_CC_DECRYPTED -> DMA_ATTR_CC_SHARED)
* update the alloc path so DMA_ATTR_CC_SHARED is not a caller-visible attribute.

Cc: Robin Murphy <robin.murphy@arm.com>
Cc: Marek Szyprowski <m.szyprowski@samsung.com>
Cc: Will Deacon <will@kernel.org>
Cc: Marc Zyngier <maz@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Jiri Pirko <jiri@resnulli.us>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Mostafa Saleh <smostafa@google.com>
Cc: Petr Tesarik <ptesarik@suse.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: linuxppc-dev@lists.ozlabs.org
Cc: linux-s390@vger.kernel.org
Cc: Madhavan Srinivasan <maddy@linux.ibm.com>
Cc: Michael Ellerman <mpe@ellerman.id.au>
Cc: Nicholas Piggin <npiggin@gmail.com>
Cc: "Christophe Leroy (CS GROUP)" <chleroy@kernel.org>
Cc: Alexander Gordeev <agordeev@linux.ibm.com>
Cc: Gerald Schaefer <gerald.schaefer@linux.ibm.com>
Cc: Heiko Carstens <hca@linux.ibm.com>
Cc: Vasily Gorbik <gor@linux.ibm.com>
Cc: Christian Borntraeger <borntraeger@linux.ibm.com>
Cc: Sven Schnelle <svens@linux.ibm.com>
Cc: x86@kernel.org


Aneesh Kumar K.V (Arm) (20):
  s390: Expose protected virtualization through cc_platform_has()
  dma-direct: swiotlb: handle swiotlb alloc/free outside
    __dma_direct_alloc_pages
  dma-direct: use DMA_ATTR_CC_SHARED in alloc/free paths
  dma-pool: track decrypted atomic pools and select them via attrs
  dma: swiotlb: pass mapping attributes by reference
  dma: swiotlb: track pool encryption state and honor DMA_ATTR_CC_SHARED
  dma-mapping: make dma_pgprot() honor DMA_ATTR_CC_SHARED
  dma-direct: pass attrs to dma_capable() for DMA_ATTR_CC_SHARED checks
  dma-direct: make dma_direct_map_phys() honor DMA_ATTR_CC_SHARED
  dma-direct: set decrypted flag for remapped DMA allocations
  dma-direct: select DMA address encoding from DMA_ATTR_CC_SHARED
  dma-pool: fix page leak in atomic_pool_expand() cleanup
  dma-direct: rename ret to cpu_addr in alloc helpers
  dma-direct: return struct page from dma_direct_alloc_from_pool()
  iommu/dma: Check atomic pool allocation result directly
  dma: swiotlb: free dynamic pools from process context
  dma: swiotlb: handle set_memory_decrypted() failures
  dma: free atomic pool pages by physical address
  swiotlb: Preserve allocation virtual address for dynamic pools
  swiotlb: remove unused SWIOTLB_FORCE flag

 arch/arm64/mm/init.c                 |   4 +-
 arch/powerpc/platforms/pseries/svm.c |   2 +-
 arch/s390/Kconfig                    |   1 +
 arch/s390/mm/init.c                  |  16 +-
 arch/x86/kernel/amd_gart_64.c        |  30 +--
 arch/x86/kernel/pci-dma.c            |   4 +-
 drivers/iommu/dma-iommu.c            |  15 +-
 drivers/xen/swiotlb-xen.c            |   8 +-
 include/linux/dma-direct.h           |  20 +-
 include/linux/dma-map-ops.h          |   3 +-
 include/linux/swiotlb.h              |  21 +-
 kernel/dma/direct.c                  | 275 +++++++++++++++++++--------
 kernel/dma/direct.h                  |  47 ++---
 kernel/dma/mapping.c                 |  16 +-
 kernel/dma/pool.c                    | 221 +++++++++++++++------
 kernel/dma/swiotlb.c                 | 273 ++++++++++++++++++++------
 16 files changed, 692 insertions(+), 264 deletions(-)


base-commit: ba3e43a9e601636f5edb54e259a74f96ca3b8fd8

---

## [2] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 01/20] s390: Expose protected virtualization through cc_platform_has()*

Protected virtualization guests use memory encryption, so advertise that to
the rest of the kernel through cc_platform_has(CC_ATTR_MEM_ENCRYPT).

s390 already forces DMA mappings to be unencrypted for protected
virtualization guests through force_dma_unencrypted(). Add
ARCH_HAS_CC_PLATFORM and provide the matching cc_platform_has()
implementation

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
Cc: Halil Pasic <pasic@linux.ibm.com>
Cc: Matthew Rosato <mjrosato@linux.ibm.com>
Cc: Jaehoon  Kim <jhkim@linux.ibm.com>
---
 arch/s390/Kconfig   |  1 +
 arch/s390/mm/init.c | 14 ++++++++++++++
 2 files changed, 15 insertions(+)

diff --git a/arch/s390/Kconfig b/arch/s390/Kconfig
index ecbcbb781e40..9b5e6029e043 100644
--- a/arch/s390/Kconfig
+++ b/arch/s390/Kconfig
@@ -87,6 +87,7 @@ config S390
 	select ARCH_ENABLE_SPLIT_PMD_PTLOCK if PGTABLE_LEVELS > 2
 	select ARCH_ENABLE_THP_MIGRATION if TRANSPARENT_HUGEPAGE
 	select ARCH_HAS_CC_CAN_LINK
+	select ARCH_HAS_CC_PLATFORM
 	select ARCH_HAS_CPU_FINALIZE_INIT
 	select ARCH_HAS_CURRENT_STACK_POINTER
 	select ARCH_HAS_DEBUG_VIRTUAL
diff --git a/arch/s390/mm/init.c b/arch/s390/mm/init.c
index 1f72efc2a579..ad3c6d92b801 100644
--- a/arch/s390/mm/init.c
+++ b/arch/s390/mm/init.c
@@ -50,6 +50,7 @@
 #include <linux/virtio_anchor.h>
 #include <linux/virtio_config.h>
 #include <linux/execmem.h>
+#include <linux/cc_platform.h>
 
 pgd_t swapper_pg_dir[PTRS_PER_PGD] __section(".bss..swapper_pg_dir");
 pgd_t invalid_pg_dir[PTRS_PER_PGD] __section(".bss..invalid_pg_dir");
@@ -140,6 +141,19 @@ bool force_dma_unencrypted(struct device *dev)
 	return is_prot_virt_guest();
 }
 
+
+bool cc_platform_has(enum cc_attr attr)
+{
+	switch (attr) {
+	case CC_ATTR_MEM_ENCRYPT:
+		return is_prot_virt_guest();
+
+	default:
+		return false;
+	}
+}
+EXPORT_SYMBOL_GPL(cc_platform_has);
+
 /* protected virtualization */
 static void __init pv_init(void)
 {

---

## [3] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 02/20] dma-direct: swiotlb: handle swiotlb alloc/free outside __dma_direct_alloc_pages*

Move swiotlb allocation out of __dma_direct_alloc_pages() and handle it in
dma_direct_alloc() / dma_direct_alloc_pages().

This is needed for follow-up changes that simplify the handling of
memory encryption/decryption based on the DMA attribute flags.

swiotlb backing pages are already mapped decrypted by
swiotlb_update_mem_attributes() and rmem_swiotlb_device_init(), so
dma-direct should not call dma_set_decrypted() on allocation nor
dma_set_encrypted() on free for swiotlb-backed memory.

Update alloc/free paths to detect swiotlb-backed pages and skip
encrypt/decrypt transitions for those paths. Keep the existing highmem
rejection in dma_direct_alloc_pages() for swiotlb allocations.

Only for "restricted-dma-pool", we currently set `for_alloc = true`, while
rmem_swiotlb_device_init() decrypts the whole pool up front. This pool is
typically used together with "shared-dma-pool", where the shared region is
accessed after remap/ioremap and the returned address is suitable for
decrypted memory access. So existing code paths remain valid.

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 include/linux/swiotlb.h |  6 ++++
 kernel/dma/direct.c     | 71 ++++++++++++++++++++++++++++++-----------
 kernel/dma/swiotlb.c    |  6 ++++
 3 files changed, 65 insertions(+), 18 deletions(-)

diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..133bb8ca9032 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -284,6 +284,8 @@ extern void swiotlb_print_info(void);
 #ifdef CONFIG_DMA_RESTRICTED_POOL
 struct page *swiotlb_alloc(struct device *dev, size_t size);
 bool swiotlb_free(struct device *dev, struct page *page, size_t size);
+void swiotlb_free_from_pool(struct device *dev, phys_addr_t tlb_addr,
+		size_t size, struct io_tlb_pool *pool);
 
 static inline bool is_swiotlb_for_alloc(struct device *dev)
 {
@@ -299,6 +301,10 @@ static inline bool swiotlb_free(struct device *dev, struct page *page,
 {
 	return false;
 }
+static inline void swiotlb_free_from_pool(struct device *dev, phys_addr_t tlb_addr,
+		size_t size, struct io_tlb_pool *pool)
+{
+}
 static inline bool is_swiotlb_for_alloc(struct device *dev)
 {
 	return false;
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 583c5922bca2..a741c8a2ee66 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -96,14 +96,6 @@ static int dma_set_encrypted(struct device *dev, void *vaddr, size_t size)
 	return ret;
 }
 
-static void __dma_direct_free_pages(struct device *dev, struct page *page,
-				    size_t size)
-{
-	if (swiotlb_free(dev, page, size))
-		return;
-	dma_free_contiguous(dev, page, size);
-}
-
 static struct page *dma_direct_alloc_swiotlb(struct device *dev, size_t size)
 {
 	struct page *page = swiotlb_alloc(dev, size);
@@ -125,9 +117,6 @@ static struct page *__dma_direct_alloc_pages(struct device *dev, size_t size,
 
 	WARN_ON_ONCE(!PAGE_ALIGNED(size));
 
-	if (is_swiotlb_for_alloc(dev))
-		return dma_direct_alloc_swiotlb(dev, size);
-
 	gfp |= dma_direct_optimal_gfp_mask(dev, &phys_limit);
 	page = dma_alloc_contiguous(dev, size, gfp);
 	if (page) {
@@ -204,6 +193,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)
 {
 	bool remap = false, set_uncached = false;
+	bool mark_mem_decrypt = true;
 	struct page *page;
 	void *ret;
 
@@ -250,11 +240,21 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	    dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (is_swiotlb_for_alloc(dev)) {
+		page = dma_direct_alloc_swiotlb(dev, size);
+		if (page) {
+			mark_mem_decrypt = false;
+			goto setup_page;
+		}
+		return NULL;
+	}
+
 	/* we always manually zero the memory once we are done */
 	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, true);
 	if (!page)
 		return NULL;
 
+setup_page:
 	/*
 	 * dma_alloc_contiguous can return highmem pages depending on a
 	 * combination the cma= arguments and per-arch setup.  These need to be
@@ -281,7 +281,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 			goto out_free_pages;
 	} else {
 		ret = page_address(page);
-		if (dma_set_decrypted(dev, ret, size))
+		if (mark_mem_decrypt && dma_set_decrypted(dev, ret, size))
 			goto out_leak_pages;
 	}
 
@@ -298,10 +298,11 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	return ret;
 
 out_encrypt_pages:
-	if (dma_set_encrypted(dev, page_address(page), size))
+	if (mark_mem_decrypt && dma_set_encrypted(dev, page_address(page), size))
 		return NULL;
 out_free_pages:
-	__dma_direct_free_pages(dev, page, size);
+	if (!swiotlb_free(dev, page, size))
+		dma_free_contiguous(dev, page, size);
 	return NULL;
 out_leak_pages:
 	return NULL;
@@ -310,6 +311,9 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 void dma_direct_free(struct device *dev, size_t size,
 		void *cpu_addr, dma_addr_t dma_addr, unsigned long attrs)
 {
+	phys_addr_t phys;
+	bool mark_mem_encrypted = true;
+	struct io_tlb_pool *swiotlb_pool;
 	unsigned int page_order = get_order(size);
 
 	if ((attrs & DMA_ATTR_NO_KERNEL_MAPPING) &&
@@ -338,16 +342,25 @@ void dma_direct_free(struct device *dev, size_t size,
 	    dma_free_from_pool(dev, cpu_addr, PAGE_ALIGN(size)))
 		return;
 
+	phys = dma_to_phys(dev, dma_addr);
+	swiotlb_pool = swiotlb_find_pool(dev, phys);
+	if (swiotlb_pool)
+		/* Swiotlb doesn't need a page attribute update on free */
+		mark_mem_encrypted = false;
+
 	if (is_vmalloc_addr(cpu_addr)) {
 		vunmap(cpu_addr);
 	} else {
 		if (IS_ENABLED(CONFIG_ARCH_HAS_DMA_CLEAR_UNCACHED))
 			arch_dma_clear_uncached(cpu_addr, size);
-		if (dma_set_encrypted(dev, cpu_addr, size))
+		if (mark_mem_encrypted && dma_set_encrypted(dev, cpu_addr, size))
 			return;
 	}
 
-	__dma_direct_free_pages(dev, dma_direct_to_page(dev, dma_addr), size);
+	if (swiotlb_pool)
+		swiotlb_free_from_pool(dev, phys, size, swiotlb_pool);
+	else
+		dma_free_contiguous(dev, dma_direct_to_page(dev, dma_addr), size);
 }
 
 struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
@@ -359,6 +372,15 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	if (force_dma_unencrypted(dev) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (is_swiotlb_for_alloc(dev)) {
+		page = dma_direct_alloc_swiotlb(dev, size);
+		if (!page)
+			return NULL;
+
+		ret = page_address(page);
+		goto setup_page;
+	}
+
 	page = __dma_direct_alloc_pages(dev, size, gfp, false);
 	if (!page)
 		return NULL;
@@ -366,6 +388,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	ret = page_address(page);
 	if (dma_set_decrypted(dev, ret, size))
 		goto out_leak_pages;
+setup_page:
 	memset(ret, 0, size);
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
 	return page;
@@ -377,16 +400,28 @@ void dma_direct_free_pages(struct device *dev, size_t size,
 		struct page *page, dma_addr_t dma_addr,
 		enum dma_data_direction dir)
 {
+	phys_addr_t phys;
 	void *vaddr = page_address(page);
+	struct io_tlb_pool *swiotlb_pool;
+	bool mark_mem_encrypted = true;
 
 	/* If cpu_addr is not from an atomic pool, dma_free_from_pool() fails */
 	if (IS_ENABLED(CONFIG_DMA_COHERENT_POOL) &&
 	    dma_free_from_pool(dev, vaddr, size))
 		return;
 
-	if (dma_set_encrypted(dev, vaddr, size))
+	phys = page_to_phys(page);
+	swiotlb_pool = swiotlb_find_pool(dev, phys);
+	if (swiotlb_pool)
+		mark_mem_encrypted = false;
+
+	if (mark_mem_encrypted && dma_set_encrypted(dev, vaddr, size))
 		return;
-	__dma_direct_free_pages(dev, page, size);
+
+	if (swiotlb_pool)
+		swiotlb_free_from_pool(dev, phys, size, swiotlb_pool);
+	else
+		dma_free_contiguous(dev, page, size);
 }
 
 #if defined(CONFIG_ARCH_HAS_SYNC_DMA_FOR_DEVICE) || \
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index 1abd3e6146f4..ac03a6856c2e 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -1809,6 +1809,12 @@ bool swiotlb_free(struct device *dev, struct page *page, size_t size)
 	return true;
 }
 
+void swiotlb_free_from_pool(struct device *dev, phys_addr_t tlb_addr, size_t size,
+		struct io_tlb_pool *pool)
+{
+	swiotlb_release_slots(dev, tlb_addr, pool);
+}
+
 static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
 				    struct device *dev)
 {

---

## [4] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 03/20] dma-direct: use DMA_ATTR_CC_SHARED in alloc/free paths*

Propagate force_dma_unencrypted() into DMA_ATTR_CC_SHARED in the
dma-direct allocation path and use the attribute to drive the related
decisions.

This updates dma_direct_alloc(), dma_direct_free(), and
dma_direct_alloc_pages() to fold the forced unencrypted case into attrs.

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 53 +++++++++++++++++++++++++++++++++++++--------
 1 file changed, 44 insertions(+), 9 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index a741c8a2ee66..90dc5057a0c0 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -193,16 +193,31 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)
 {
 	bool remap = false, set_uncached = false;
-	bool mark_mem_decrypt = true;
+	bool mark_mem_decrypt = false;
 	struct page *page;
 	void *ret;
 
+	/*
+	 * DMA_ATTR_CC_SHARED is not a caller-visible dma_alloc_*()
+	 * attribute. The direct allocator uses it internally after it has
+	 * decided that the backing pages must be shared/decrypted, so the
+	 * rest of the allocation path can consistently select DMA addresses,
+	 * choose compatible pools and restore encryption on free.
+	 */
+	if (attrs & DMA_ATTR_CC_SHARED)
+		return NULL;
+
+	if (force_dma_unencrypted(dev)) {
+		attrs |= DMA_ATTR_CC_SHARED;
+		mark_mem_decrypt = true;
+	}
+
 	size = PAGE_ALIGN(size);
 	if (attrs & DMA_ATTR_NO_WARN)
 		gfp |= __GFP_NOWARN;
 
-	if ((attrs & DMA_ATTR_NO_KERNEL_MAPPING) &&
-	    !force_dma_unencrypted(dev) && !is_swiotlb_for_alloc(dev))
+	if (((attrs & (DMA_ATTR_NO_KERNEL_MAPPING | DMA_ATTR_CC_SHARED)) ==
+	     DMA_ATTR_NO_KERNEL_MAPPING) && !is_swiotlb_for_alloc(dev))
 		return dma_direct_alloc_no_mapping(dev, size, dma_handle, gfp);
 
 	if (!dev_is_dma_coherent(dev)) {
@@ -236,7 +251,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	 * Remapping or decrypting memory may block, allocate the memory from
 	 * the atomic pools instead if we aren't allowed block.
 	 */
-	if ((remap || force_dma_unencrypted(dev)) &&
+	if ((remap || (attrs & DMA_ATTR_CC_SHARED)) &&
 	    dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
@@ -312,12 +327,24 @@ void dma_direct_free(struct device *dev, size_t size,
 		void *cpu_addr, dma_addr_t dma_addr, unsigned long attrs)
 {
 	phys_addr_t phys;
-	bool mark_mem_encrypted = true;
+	bool mark_mem_encrypted = false;
 	struct io_tlb_pool *swiotlb_pool;
 	unsigned int page_order = get_order(size);
 
-	if ((attrs & DMA_ATTR_NO_KERNEL_MAPPING) &&
-	    !force_dma_unencrypted(dev) && !is_swiotlb_for_alloc(dev)) {
+	/* see dma_direct_alloc() for details */
+	WARN_ON(attrs & DMA_ATTR_CC_SHARED);
+
+	/*
+	 * if the device had requested for an unencrypted buffer,
+	 * convert it to encrypted on free
+	 */
+	if (force_dma_unencrypted(dev)) {
+		attrs |= DMA_ATTR_CC_SHARED;
+		mark_mem_encrypted = true;
+	}
+
+	if (((attrs & (DMA_ATTR_NO_KERNEL_MAPPING | DMA_ATTR_CC_SHARED)) ==
+	     DMA_ATTR_NO_KERNEL_MAPPING) && !is_swiotlb_for_alloc(dev)) {
 		/* cpu_addr is a struct page cookie, not a kernel address */
 		dma_free_contiguous(dev, cpu_addr, size);
 		return;
@@ -366,10 +393,14 @@ void dma_direct_free(struct device *dev, size_t size,
 struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 		dma_addr_t *dma_handle, enum dma_data_direction dir, gfp_t gfp)
 {
+	unsigned long attrs = 0;
 	struct page *page;
 	void *ret;
 
-	if (force_dma_unencrypted(dev) && dma_direct_use_pool(dev, gfp))
+	if (force_dma_unencrypted(dev))
+		attrs |= DMA_ATTR_CC_SHARED;
+
+	if ((attrs & DMA_ATTR_CC_SHARED) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
 	if (is_swiotlb_for_alloc(dev)) {
@@ -403,7 +434,11 @@ void dma_direct_free_pages(struct device *dev, size_t size,
 	phys_addr_t phys;
 	void *vaddr = page_address(page);
 	struct io_tlb_pool *swiotlb_pool;
-	bool mark_mem_encrypted = true;
+	/*
+	 * if the device had requested for an unencrypted buffer,
+	 * convert it to encrypted on free
+	 */
+	bool mark_mem_encrypted = force_dma_unencrypted(dev);
 
 	/* If cpu_addr is not from an atomic pool, dma_free_from_pool() fails */
 	if (IS_ENABLED(CONFIG_DMA_COHERENT_POOL) &&

---

## [5] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and select them via attrs*

Teach the atomic DMA pool code to distinguish between encrypted and
unencrypted pools, and make pool allocation select the matching pool based
on DMA attributes.

Introduce a dma_gen_pool wrapper that records whether a pool is
unencrypted, initialize that state when the atomic pools are created, and
use it when expanding and resizing the pools. Update dma_alloc_from_pool()
to take attrs and skip pools whose encrypted state does not match
DMA_ATTR_CC_SHARED. Update dma_free_from_pool() accordingly.

Also pass DMA_ATTR_CC_SHARED from the swiotlb atomic allocation path so
decrypted swiotlb allocations are taken from the correct atomic pool.

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Reviewed-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/dma-iommu.c   |   2 +-
 include/linux/dma-map-ops.h |   2 +-
 kernel/dma/direct.c         |  11 ++-
 kernel/dma/pool.c           | 167 +++++++++++++++++++++++-------------
 kernel/dma/swiotlb.c        |   7 +-
 5 files changed, 123 insertions(+), 66 deletions(-)

diff --git a/drivers/iommu/dma-iommu.c b/drivers/iommu/dma-iommu.c
index 54d96e847f16..c2595bee3d41 100644
--- a/drivers/iommu/dma-iommu.c
+++ b/drivers/iommu/dma-iommu.c
@@ -1673,7 +1673,7 @@ void *iommu_dma_alloc(struct device *dev, size_t size, dma_addr_t *handle,
 	if (IS_ENABLED(CONFIG_DMA_DIRECT_REMAP) &&
 	    !gfpflags_allow_blocking(gfp) && !coherent)
 		page = dma_alloc_from_pool(dev, PAGE_ALIGN(size), &cpu_addr,
-					       gfp, NULL);
+					   gfp, attrs, NULL);
 	else
 		cpu_addr = iommu_dma_alloc_pages(dev, size, &page, gfp, attrs);
 	if (!cpu_addr)
diff --git a/include/linux/dma-map-ops.h b/include/linux/dma-map-ops.h
index 6a1832a73cad..696b2c3a2305 100644
--- a/include/linux/dma-map-ops.h
+++ b/include/linux/dma-map-ops.h
@@ -212,7 +212,7 @@ void *dma_common_pages_remap(struct page **pages, size_t size, pgprot_t prot,
 void dma_common_free_remap(void *cpu_addr, size_t size);
 
 struct page *dma_alloc_from_pool(struct device *dev, size_t size,
-		void **cpu_addr, gfp_t flags,
+		void **cpu_addr, gfp_t flags, unsigned long attrs,
 		bool (*phys_addr_ok)(struct device *, phys_addr_t, size_t));
 bool dma_free_from_pool(struct device *dev, void *start, size_t size);
 
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 90dc5057a0c0..681f16a984ab 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -154,7 +154,7 @@ static bool dma_direct_use_pool(struct device *dev, gfp_t gfp)
 }
 
 static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
-		dma_addr_t *dma_handle, gfp_t gfp)
+		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)
 {
 	struct page *page;
 	u64 phys_limit;
@@ -164,7 +164,8 @@ static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
 		return NULL;
 
 	gfp |= dma_direct_optimal_gfp_mask(dev, &phys_limit);
-	page = dma_alloc_from_pool(dev, size, &ret, gfp, dma_coherent_ok);
+	page = dma_alloc_from_pool(dev, size, &ret, gfp, attrs,
+				   dma_coherent_ok);
 	if (!page)
 		return NULL;
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
@@ -253,7 +254,8 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	 */
 	if ((remap || (attrs & DMA_ATTR_CC_SHARED)) &&
 	    dma_direct_use_pool(dev, gfp))
-		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
+		return dma_direct_alloc_from_pool(dev, size, dma_handle,
+						  gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
 		page = dma_direct_alloc_swiotlb(dev, size);
@@ -401,7 +403,8 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 		attrs |= DMA_ATTR_CC_SHARED;
 
 	if ((attrs & DMA_ATTR_CC_SHARED) && dma_direct_use_pool(dev, gfp))
-		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
+		return dma_direct_alloc_from_pool(dev, size, dma_handle,
+						  gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
 		page = dma_direct_alloc_swiotlb(dev, size);
diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index 2b2fbb709242..be78474a6c49 100644
--- a/kernel/dma/pool.c
+++ b/kernel/dma/pool.c
@@ -12,12 +12,18 @@
 #include <linux/set_memory.h>
 #include <linux/slab.h>
 #include <linux/workqueue.h>
+#include <linux/cc_platform.h>
 
-static struct gen_pool *atomic_pool_dma __ro_after_init;
+struct dma_gen_pool {
+	bool unencrypted;
+	struct gen_pool *pool;
+};
+
+static struct dma_gen_pool atomic_pool_dma __ro_after_init;
 static unsigned long pool_size_dma;
-static struct gen_pool *atomic_pool_dma32 __ro_after_init;
+static struct dma_gen_pool atomic_pool_dma32 __ro_after_init;
 static unsigned long pool_size_dma32;
-static struct gen_pool *atomic_pool_kernel __ro_after_init;
+static struct dma_gen_pool atomic_pool_kernel __ro_after_init;
 static unsigned long pool_size_kernel;
 
 /* Size can be defined by the coherent_pool command line */
@@ -76,11 +82,12 @@ static bool cma_in_zone(gfp_t gfp)
 	return true;
 }
 
-static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
+static int atomic_pool_expand(struct dma_gen_pool *dma_pool, size_t pool_size,
 			      gfp_t gfp)
 {
 	unsigned int order;
 	struct page *page = NULL;
+	bool leak_pages = false;
 	void *addr;
 	int ret = -ENOMEM;
 
@@ -113,12 +120,17 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 	 * Memory in the atomic DMA pools must be unencrypted, the pools do not
 	 * shrink so no re-encryption occurs in dma_direct_free().
 	 */
-	ret = set_memory_decrypted((unsigned long)page_to_virt(page),
-				   1 << order);
-	if (ret)
-		goto remove_mapping;
-	ret = gen_pool_add_virt(pool, (unsigned long)addr, page_to_phys(page),
-				pool_size, NUMA_NO_NODE);
+	if (dma_pool->unencrypted) {
+		ret = set_memory_decrypted((unsigned long)page_to_virt(page),
+					   1 << order);
+		if (ret) {
+			leak_pages = true;
+			goto remove_mapping;
+		}
+	}
+
+	ret = gen_pool_add_virt(dma_pool->pool, (unsigned long)addr,
+				page_to_phys(page), pool_size, NUMA_NO_NODE);
 	if (ret)
 		goto encrypt_mapping;
 
@@ -126,62 +138,67 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 	return 0;
 
 encrypt_mapping:
-	ret = set_memory_encrypted((unsigned long)page_to_virt(page),
-				   1 << order);
-	if (WARN_ON_ONCE(ret)) {
-		/* Decrypt succeeded but encrypt failed, purposely leak */
-		goto out;
-	}
+	if (dma_pool->unencrypted &&
+	    set_memory_encrypted((unsigned long)page_to_virt(page), 1 << order))
+		leak_pages = true;
+
 remove_mapping:
 #ifdef CONFIG_DMA_DIRECT_REMAP
 	dma_common_free_remap(addr, pool_size);
 free_page:
-	__free_pages(page, order);
+	if (!leak_pages)
+		__free_pages(page, order);
 #endif
 out:
 	return ret;
 }
 
-static void atomic_pool_resize(struct gen_pool *pool, gfp_t gfp)
+static void atomic_pool_resize(struct dma_gen_pool *dma_pool, gfp_t gfp)
 {
-	if (pool && gen_pool_avail(pool) < atomic_pool_size)
-		atomic_pool_expand(pool, gen_pool_size(pool), gfp);
+	if (dma_pool->pool && gen_pool_avail(dma_pool->pool) < atomic_pool_size)
+		atomic_pool_expand(dma_pool, gen_pool_size(dma_pool->pool), gfp);
 }
 
 static void atomic_pool_work_fn(struct work_struct *work)
 {
 	if (IS_ENABLED(CONFIG_ZONE_DMA))
-		atomic_pool_resize(atomic_pool_dma,
+		atomic_pool_resize(&atomic_pool_dma,
 				   GFP_KERNEL | GFP_DMA);
 	if (IS_ENABLED(CONFIG_ZONE_DMA32))
-		atomic_pool_resize(atomic_pool_dma32,
+		atomic_pool_resize(&atomic_pool_dma32,
 				   GFP_KERNEL | GFP_DMA32);
-	atomic_pool_resize(atomic_pool_kernel, GFP_KERNEL);
+	atomic_pool_resize(&atomic_pool_kernel, GFP_KERNEL);
 }
 
-static __init struct gen_pool *__dma_atomic_pool_init(size_t pool_size,
-						      gfp_t gfp)
+static __init struct dma_gen_pool *__dma_atomic_pool_init(struct dma_gen_pool *dma_pool,
+		size_t pool_size, gfp_t gfp)
 {
-	struct gen_pool *pool;
 	int ret;
 
-	pool = gen_pool_create(PAGE_SHIFT, NUMA_NO_NODE);
-	if (!pool)
+	dma_pool->pool = gen_pool_create(PAGE_SHIFT, NUMA_NO_NODE);
+	if (!dma_pool->pool)
 		return NULL;
 
-	gen_pool_set_algo(pool, gen_pool_first_fit_order_align, NULL);
+	gen_pool_set_algo(dma_pool->pool, gen_pool_first_fit_order_align, NULL);
+
+	/* if platform is using memory encryption atomic pools are by default decrypted. */
+	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+		dma_pool->unencrypted = true;
+	else
+		dma_pool->unencrypted = false;
 
-	ret = atomic_pool_expand(pool, pool_size, gfp);
+	ret = atomic_pool_expand(dma_pool, pool_size, gfp);
 	if (ret) {
-		gen_pool_destroy(pool);
+		gen_pool_destroy(dma_pool->pool);
+		dma_pool->pool = NULL;
 		pr_err("DMA: failed to allocate %zu KiB %pGg pool for atomic allocation\n",
 		       pool_size >> 10, &gfp);
 		return NULL;
 	}
 
 	pr_info("DMA: preallocated %zu KiB %pGg pool for atomic allocations\n",
-		gen_pool_size(pool) >> 10, &gfp);
-	return pool;
+		gen_pool_size(dma_pool->pool) >> 10, &gfp);
+	return dma_pool;
 }
 
 #ifdef CONFIG_ZONE_DMA32
@@ -207,21 +224,22 @@ static int __init dma_atomic_pool_init(void)
 
 	/* All memory might be in the DMA zone(s) to begin with */
 	if (has_managed_zone(ZONE_NORMAL)) {
-		atomic_pool_kernel = __dma_atomic_pool_init(atomic_pool_size,
-						    GFP_KERNEL);
-		if (!atomic_pool_kernel)
+		__dma_atomic_pool_init(&atomic_pool_kernel, atomic_pool_size, GFP_KERNEL);
+		if (!atomic_pool_kernel.pool)
 			ret = -ENOMEM;
 	}
+
 	if (has_managed_dma()) {
-		atomic_pool_dma = __dma_atomic_pool_init(atomic_pool_size,
-						GFP_KERNEL | GFP_DMA);
-		if (!atomic_pool_dma)
+		__dma_atomic_pool_init(&atomic_pool_dma, atomic_pool_size,
+				       GFP_KERNEL | GFP_DMA);
+		if (!atomic_pool_dma.pool)
 			ret = -ENOMEM;
 	}
+
 	if (has_managed_dma32) {
-		atomic_pool_dma32 = __dma_atomic_pool_init(atomic_pool_size,
-						GFP_KERNEL | GFP_DMA32);
-		if (!atomic_pool_dma32)
+		__dma_atomic_pool_init(&atomic_pool_dma32, atomic_pool_size,
+				       GFP_KERNEL | GFP_DMA32);
+		if (!atomic_pool_dma32.pool)
 			ret = -ENOMEM;
 	}
 
@@ -230,19 +248,44 @@ static int __init dma_atomic_pool_init(void)
 }
 postcore_initcall(dma_atomic_pool_init);
 
-static inline struct gen_pool *dma_guess_pool(struct gen_pool *prev, gfp_t gfp)
+static inline struct dma_gen_pool *__dma_guess_pool(struct dma_gen_pool *first,
+		struct dma_gen_pool *second, struct dma_gen_pool *third)
 {
-	if (prev == NULL) {
+	if (first->pool)
+		return first;
+	if (second && second->pool)
+		return second;
+	if (third && third->pool)
+		return third;
+	return NULL;
+}
+
+static inline struct dma_gen_pool *dma_guess_pool(struct dma_gen_pool *prev,
+		gfp_t gfp)
+{
+	if (!prev) {
 		if (gfp & GFP_DMA)
-			return atomic_pool_dma ?: atomic_pool_dma32 ?: atomic_pool_kernel;
+			return __dma_guess_pool(&atomic_pool_dma,
+						&atomic_pool_dma32,
+						&atomic_pool_kernel);
+
 		if (gfp & GFP_DMA32)
-			return atomic_pool_dma32 ?: atomic_pool_dma ?: atomic_pool_kernel;
-		return atomic_pool_kernel ?: atomic_pool_dma32 ?: atomic_pool_dma;
+			return __dma_guess_pool(&atomic_pool_dma32,
+						&atomic_pool_dma,
+						&atomic_pool_kernel);
+
+		return __dma_guess_pool(&atomic_pool_kernel,
+					&atomic_pool_dma32,
+					&atomic_pool_dma);
 	}
-	if (prev == atomic_pool_kernel)
-		return atomic_pool_dma32 ? atomic_pool_dma32 : atomic_pool_dma;
-	if (prev == atomic_pool_dma32)
-		return atomic_pool_dma;
+
+	if (prev == &atomic_pool_kernel)
+		return __dma_guess_pool(&atomic_pool_dma32,
+					&atomic_pool_dma, NULL);
+
+	if (prev == &atomic_pool_dma32)
+		return __dma_guess_pool(&atomic_pool_dma, NULL, NULL);
+
 	return NULL;
 }
 
@@ -272,16 +315,20 @@ static struct page *__dma_alloc_from_pool(struct device *dev, size_t size,
 }
 
 struct page *dma_alloc_from_pool(struct device *dev, size_t size,
-		void **cpu_addr, gfp_t gfp,
+		void **cpu_addr, gfp_t gfp, unsigned long attrs,
 		bool (*phys_addr_ok)(struct device *, phys_addr_t, size_t))
 {
-	struct gen_pool *pool = NULL;
+	struct dma_gen_pool *dma_pool = NULL;
 	struct page *page;
 	bool pool_found = false;
 
-	while ((pool = dma_guess_pool(pool, gfp))) {
+	while ((dma_pool = dma_guess_pool(dma_pool, gfp))) {
+
+		if (dma_pool->unencrypted != !!(attrs & DMA_ATTR_CC_SHARED))
+			continue;
+
 		pool_found = true;
-		page = __dma_alloc_from_pool(dev, size, pool, cpu_addr,
+		page = __dma_alloc_from_pool(dev, size, dma_pool->pool, cpu_addr,
 					     phys_addr_ok);
 		if (page)
 			return page;
@@ -296,12 +343,14 @@ struct page *dma_alloc_from_pool(struct device *dev, size_t size,
 
 bool dma_free_from_pool(struct device *dev, void *start, size_t size)
 {
-	struct gen_pool *pool = NULL;
+	struct dma_gen_pool *dma_pool = NULL;
+
+	while ((dma_pool = dma_guess_pool(dma_pool, 0))) {
 
-	while ((pool = dma_guess_pool(pool, 0))) {
-		if (!gen_pool_has_addr(pool, (unsigned long)start, size))
+		if (!gen_pool_has_addr(dma_pool->pool, (unsigned long)start, size))
 			continue;
-		gen_pool_free(pool, (unsigned long)start, size);
+
+		gen_pool_free(dma_pool->pool, (unsigned long)start, size);
 		return true;
 	}
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index ac03a6856c2e..be4d418d92ac 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -612,6 +612,7 @@ static struct page *swiotlb_alloc_tlb(struct device *dev, size_t bytes,
 		u64 phys_limit, gfp_t gfp)
 {
 	struct page *page;
+	unsigned long attrs = 0;
 
 	/*
 	 * Allocate from the atomic pools if memory is encrypted and
@@ -623,8 +624,12 @@ static struct page *swiotlb_alloc_tlb(struct device *dev, size_t bytes,
 		if (!IS_ENABLED(CONFIG_DMA_COHERENT_POOL))
 			return NULL;
 
+		/* swiotlb considered decrypted by default */
+		if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+			attrs = DMA_ATTR_CC_SHARED;
+
 		return dma_alloc_from_pool(dev, bytes, &vaddr, gfp,
-					   dma_coherent_ok);
+					   attrs, dma_coherent_ok);
 	}
 
 	gfp &= ~GFP_ZONEMASK;

---

## [6] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 05/20] dma: swiotlb: pass mapping attributes by reference*

Change swiotlb_tbl_map_single() to take the DMA mapping attributes by
reference and update the direct callers accordingly.

This is a preparatory change for a follow-up patch which updates the
attributes based on the selected swiotlb pool. Keeping the signature change
separate makes the follow-up patch easier to review.

No functional change in this patch.

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/dma-iommu.c | 2 +-
 drivers/xen/swiotlb-xen.c | 2 +-
 include/linux/swiotlb.h   | 2 +-
 kernel/dma/swiotlb.c      | 6 +++---
 4 files changed, 6 insertions(+), 6 deletions(-)

diff --git a/drivers/iommu/dma-iommu.c b/drivers/iommu/dma-iommu.c
index c2595bee3d41..725c7adb0a8d 100644
--- a/drivers/iommu/dma-iommu.c
+++ b/drivers/iommu/dma-iommu.c
@@ -1180,7 +1180,7 @@ static phys_addr_t iommu_dma_map_swiotlb(struct device *dev, phys_addr_t phys,
 	trace_swiotlb_bounced(dev, phys, size);
 
 	phys = swiotlb_tbl_map_single(dev, phys, size, iova_mask(iovad), dir,
-			attrs);
+				      &attrs);
 
 	/*
 	 * Untrusted devices should not see padding areas with random leftover
diff --git a/drivers/xen/swiotlb-xen.c b/drivers/xen/swiotlb-xen.c
index 2cbf2b588f5b..8c4abe65cd49 100644
--- a/drivers/xen/swiotlb-xen.c
+++ b/drivers/xen/swiotlb-xen.c
@@ -243,7 +243,7 @@ static dma_addr_t xen_swiotlb_map_phys(struct device *dev, phys_addr_t phys,
 	 */
 	trace_swiotlb_bounced(dev, dev_addr, size);
 
-	map = swiotlb_tbl_map_single(dev, phys, size, 0, dir, attrs);
+	map = swiotlb_tbl_map_single(dev, phys, size, 0, dir, &attrs);
 	if (map == (phys_addr_t)DMA_MAPPING_ERROR)
 		return DMA_MAPPING_ERROR;
 
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 133bb8ca9032..29187cec90d8 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -238,7 +238,7 @@ static inline phys_addr_t default_swiotlb_limit(void)
 
 phys_addr_t swiotlb_tbl_map_single(struct device *hwdev, phys_addr_t phys,
 		size_t mapping_size, unsigned int alloc_aligned_mask,
-		enum dma_data_direction dir, unsigned long attrs);
+		enum dma_data_direction dir, unsigned long *attrs);
 dma_addr_t swiotlb_map(struct device *dev, phys_addr_t phys,
 		size_t size, enum dma_data_direction dir, unsigned long attrs);
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index be4d418d92ac..78ce05857c00 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -1391,7 +1391,7 @@ static unsigned long mem_used(struct io_tlb_mem *mem)
  */
 phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 		size_t mapping_size, unsigned int alloc_align_mask,
-		enum dma_data_direction dir, unsigned long attrs)
+		enum dma_data_direction dir, unsigned long *attrs)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 	unsigned int offset;
@@ -1425,7 +1425,7 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	size = ALIGN(mapping_size + offset, alloc_align_mask + 1);
 	index = swiotlb_find_slots(dev, orig_addr, size, alloc_align_mask, &pool);
 	if (index == -1) {
-		if (!(attrs & DMA_ATTR_NO_WARN))
+		if (!(*attrs & DMA_ATTR_NO_WARN))
 			dev_warn_ratelimited(dev,
 	"swiotlb buffer is full (sz: %zd bytes), total %lu (slots), used %lu (slots)\n",
 				 size, mem->nslabs, mem_used(mem));
@@ -1604,7 +1604,7 @@ dma_addr_t swiotlb_map(struct device *dev, phys_addr_t paddr, size_t size,
 
 	trace_swiotlb_bounced(dev, phys_to_dma(dev, paddr), size);
 
-	swiotlb_addr = swiotlb_tbl_map_single(dev, paddr, size, 0, dir, attrs);
+	swiotlb_addr = swiotlb_tbl_map_single(dev, paddr, size, 0, dir, &attrs);
 	if (swiotlb_addr == (phys_addr_t)DMA_MAPPING_ERROR)
 		return DMA_MAPPING_ERROR;

---

## [7] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 06/20] dma: swiotlb: track pool encryption state and honor DMA_ATTR_CC_SHARED*

Teach swiotlb to distinguish between encrypted and decrypted bounce
buffer pools, and make allocation and mapping paths select a pool whose
state matches the requested DMA attributes.

Add a unencrypted flag to io_tlb_mem, initialize it for the default and
restricted pools, and propagate DMA_ATTR_CC_SHARED into swiotlb pool
allocation. Reject swiotlb alloc/map requests when the selected pool does
not match the required encrypted/decrypted state.

Also return DMA addresses with the matching phys_to_dma_{encrypted,
unencrypted} helper so the DMA address encoding stays consistent with the
chosen pool.

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 include/linux/dma-direct.h |  10 +++
 include/linux/swiotlb.h    |   8 +-
 kernel/dma/direct.c        |  13 +++-
 kernel/dma/swiotlb.c       | 154 ++++++++++++++++++++++++++++---------
 4 files changed, 142 insertions(+), 43 deletions(-)

diff --git a/include/linux/dma-direct.h b/include/linux/dma-direct.h
index c249912456f9..94fad4e7c11e 100644
--- a/include/linux/dma-direct.h
+++ b/include/linux/dma-direct.h
@@ -77,6 +77,10 @@ static inline dma_addr_t dma_range_map_max(const struct bus_dma_region *map)
 #ifndef phys_to_dma_unencrypted
 #define phys_to_dma_unencrypted		phys_to_dma
 #endif
+
+#ifndef phys_to_dma_encrypted
+#define phys_to_dma_encrypted		phys_to_dma
+#endif
 #else
 static inline dma_addr_t __phys_to_dma(struct device *dev, phys_addr_t paddr)
 {
@@ -90,6 +94,12 @@ static inline dma_addr_t phys_to_dma_unencrypted(struct device *dev,
 {
 	return dma_addr_unencrypted(__phys_to_dma(dev, paddr));
 }
+
+static inline dma_addr_t phys_to_dma_encrypted(struct device *dev,
+		phys_addr_t paddr)
+{
+	return dma_addr_encrypted(__phys_to_dma(dev, paddr));
+}
 /*
  * If memory encryption is supported, phys_to_dma will set the memory encryption
  * bit in the DMA address, and dma_to_phys will clear it.
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 29187cec90d8..4dcbf3931be1 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -81,6 +81,7 @@ struct io_tlb_pool {
 	struct list_head node;
 	struct rcu_head rcu;
 	bool transient;
+	bool unencrypted;
 #endif
 };
 
@@ -111,6 +112,7 @@ struct io_tlb_mem {
 	struct dentry *debugfs;
 	bool force_bounce;
 	bool for_alloc;
+	bool unencrypted;
 #ifdef CONFIG_SWIOTLB_DYNAMIC
 	bool can_grow;
 	u64 phys_limit;
@@ -282,7 +284,8 @@ static inline void swiotlb_sync_single_for_cpu(struct device *dev,
 extern void swiotlb_print_info(void);
 
 #ifdef CONFIG_DMA_RESTRICTED_POOL
-struct page *swiotlb_alloc(struct device *dev, size_t size);
+struct page *swiotlb_alloc(struct device *dev, size_t size,
+		unsigned long attrs);
 bool swiotlb_free(struct device *dev, struct page *page, size_t size);
 void swiotlb_free_from_pool(struct device *dev, phys_addr_t tlb_addr,
 		size_t size, struct io_tlb_pool *pool);
@@ -292,7 +295,8 @@ static inline bool is_swiotlb_for_alloc(struct device *dev)
 	return dev->dma_io_tlb_mem->for_alloc;
 }
 #else
-static inline struct page *swiotlb_alloc(struct device *dev, size_t size)
+static inline struct page *swiotlb_alloc(struct device *dev, size_t size,
+		unsigned long attrs)
 {
 	return NULL;
 }
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 681f16a984ab..0b4a26c6b6fd 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -96,9 +96,10 @@ static int dma_set_encrypted(struct device *dev, void *vaddr, size_t size)
 	return ret;
 }
 
-static struct page *dma_direct_alloc_swiotlb(struct device *dev, size_t size)
+static struct page *dma_direct_alloc_swiotlb(struct device *dev, size_t size,
+		unsigned long attrs)
 {
-	struct page *page = swiotlb_alloc(dev, size);
+	struct page *page = swiotlb_alloc(dev, size, attrs);
 
 	if (page && !dma_coherent_ok(dev, page_to_phys(page), size)) {
 		swiotlb_free(dev, page, size);
@@ -258,8 +259,12 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 						  gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
-		page = dma_direct_alloc_swiotlb(dev, size);
+		page = dma_direct_alloc_swiotlb(dev, size, attrs);
 		if (page) {
+			/*
+			 * swiotlb allocations comes from pool already marked
+			 * decrypted
+			 */
 			mark_mem_decrypt = false;
 			goto setup_page;
 		}
@@ -407,7 +412,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 						  gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
-		page = dma_direct_alloc_swiotlb(dev, size);
+		page = dma_direct_alloc_swiotlb(dev, size, attrs);
 		if (!page)
 			return NULL;
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index 78ce05857c00..2bf3981db35d 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -259,10 +259,21 @@ void __init swiotlb_update_mem_attributes(void)
 	struct io_tlb_pool *mem = &io_tlb_default_mem.defpool;
 	unsigned long bytes;
 
+	/*
+	 * if platform support memory encryption, swiotlb buffers are
+	 * decrypted by default.
+	 */
+	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+		io_tlb_default_mem.unencrypted = true;
+	else
+		io_tlb_default_mem.unencrypted = false;
+
 	if (!mem->nslabs || mem->late_alloc)
 		return;
 	bytes = PAGE_ALIGN(mem->nslabs << IO_TLB_SHIFT);
-	set_memory_decrypted((unsigned long)mem->vaddr, bytes >> PAGE_SHIFT);
+
+	if (io_tlb_default_mem.unencrypted)
+		set_memory_decrypted((unsigned long)mem->vaddr, bytes >> PAGE_SHIFT);
 }
 
 static void swiotlb_init_io_tlb_pool(struct io_tlb_pool *mem, phys_addr_t start,
@@ -505,8 +516,10 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 	if (!mem->slots)
 		goto error_slots;
 
-	set_memory_decrypted((unsigned long)vstart,
-			     (nslabs << IO_TLB_SHIFT) >> PAGE_SHIFT);
+	if (io_tlb_default_mem.unencrypted)
+		set_memory_decrypted((unsigned long)vstart,
+				     (nslabs << IO_TLB_SHIFT) >> PAGE_SHIFT);
+
 	swiotlb_init_io_tlb_pool(mem, virt_to_phys(vstart), nslabs, true,
 				 nareas);
 	add_mem_pool(&io_tlb_default_mem, mem);
@@ -539,7 +552,9 @@ void __init swiotlb_exit(void)
 	tbl_size = PAGE_ALIGN(mem->end - mem->start);
 	slots_size = PAGE_ALIGN(array_size(sizeof(*mem->slots), mem->nslabs));
 
-	set_memory_encrypted(tbl_vaddr, tbl_size >> PAGE_SHIFT);
+	if (io_tlb_default_mem.unencrypted)
+		set_memory_encrypted(tbl_vaddr, tbl_size >> PAGE_SHIFT);
+
 	if (mem->late_alloc) {
 		area_order = get_order(array_size(sizeof(*mem->areas),
 			mem->nareas));
@@ -563,6 +578,7 @@ void __init swiotlb_exit(void)
  * @gfp:	GFP flags for the allocation.
  * @bytes:	Size of the buffer.
  * @phys_limit:	Maximum allowed physical address of the buffer.
+ * @unencrypted: true to allocate unencrypted memory, false for encrypted memory
  *
  * Allocate pages from the buddy allocator. If successful, make the allocated
  * pages decrypted that they can be used for DMA.
@@ -570,7 +586,8 @@ void __init swiotlb_exit(void)
  * Return: Decrypted pages, %NULL on allocation failure, or ERR_PTR(-EAGAIN)
  * if the allocated physical address was above @phys_limit.
  */
-static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes, u64 phys_limit)
+static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes,
+		u64 phys_limit, bool unencrypted)
 {
 	unsigned int order = get_order(bytes);
 	struct page *page;
@@ -588,13 +605,13 @@ static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes, u64 phys_limit)
 	}
 
 	vaddr = phys_to_virt(paddr);
-	if (set_memory_decrypted((unsigned long)vaddr, PFN_UP(bytes)))
+	if (unencrypted && set_memory_decrypted((unsigned long)vaddr, PFN_UP(bytes)))
 		goto error;
 	return page;
 
 error:
 	/* Intentional leak if pages cannot be encrypted again. */
-	if (!set_memory_encrypted((unsigned long)vaddr, PFN_UP(bytes)))
+	if (unencrypted && !set_memory_encrypted((unsigned long)vaddr, PFN_UP(bytes)))
 		__free_pages(page, order);
 	return NULL;
 }
@@ -604,30 +621,26 @@ static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes, u64 phys_limit)
  * @dev:	Device for which a memory pool is allocated.
  * @bytes:	Size of the buffer.
  * @phys_limit:	Maximum allowed physical address of the buffer.
+ * @attrs:	DMA attributes for the allocation.
  * @gfp:	GFP flags for the allocation.
  *
  * Return: Allocated pages, or %NULL on allocation failure.
  */
 static struct page *swiotlb_alloc_tlb(struct device *dev, size_t bytes,
-		u64 phys_limit, gfp_t gfp)
+		u64 phys_limit, unsigned long attrs, gfp_t gfp)
 {
 	struct page *page;
-	unsigned long attrs = 0;
 
 	/*
 	 * Allocate from the atomic pools if memory is encrypted and
 	 * the allocation is atomic, because decrypting may block.
 	 */
-	if (!gfpflags_allow_blocking(gfp) && dev && force_dma_unencrypted(dev)) {
+	if (!gfpflags_allow_blocking(gfp) && (attrs & DMA_ATTR_CC_SHARED)) {
 		void *vaddr;
 
 		if (!IS_ENABLED(CONFIG_DMA_COHERENT_POOL))
 			return NULL;
 
-		/* swiotlb considered decrypted by default */
-		if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
-			attrs = DMA_ATTR_CC_SHARED;
-
 		return dma_alloc_from_pool(dev, bytes, &vaddr, gfp,
 					   attrs, dma_coherent_ok);
 	}
@@ -638,7 +651,8 @@ static struct page *swiotlb_alloc_tlb(struct device *dev, size_t bytes,
 	else if (phys_limit <= DMA_BIT_MASK(32))
 		gfp |= __GFP_DMA32;
 
-	while (IS_ERR(page = alloc_dma_pages(gfp, bytes, phys_limit))) {
+	while (IS_ERR(page = alloc_dma_pages(gfp, bytes, phys_limit,
+					     !!(attrs & DMA_ATTR_CC_SHARED)))) {
 		if (IS_ENABLED(CONFIG_ZONE_DMA32) &&
 		    phys_limit < DMA_BIT_MASK(64) &&
 		    !(gfp & (__GFP_DMA32 | __GFP_DMA)))
@@ -657,15 +671,18 @@ static struct page *swiotlb_alloc_tlb(struct device *dev, size_t bytes,
  * swiotlb_free_tlb() - free a dynamically allocated IO TLB buffer
  * @vaddr:	Virtual address of the buffer.
  * @bytes:	Size of the buffer.
+ * @unencrypted: true if @vaddr was allocated decrypted and must be
+ *	re-encrypted before being freed
  */
-static void swiotlb_free_tlb(void *vaddr, size_t bytes)
+static void swiotlb_free_tlb(void *vaddr, size_t bytes, bool unencrypted)
 {
 	if (IS_ENABLED(CONFIG_DMA_COHERENT_POOL) &&
 	    dma_free_from_pool(NULL, vaddr, bytes))
 		return;
 
 	/* Intentional leak if pages cannot be encrypted again. */
-	if (!set_memory_encrypted((unsigned long)vaddr, PFN_UP(bytes)))
+	if (!unencrypted ||
+	    !set_memory_encrypted((unsigned long)vaddr, PFN_UP(bytes)))
 		__free_pages(virt_to_page(vaddr), get_order(bytes));
 }
 
@@ -676,6 +693,7 @@ static void swiotlb_free_tlb(void *vaddr, size_t bytes)
  * @nslabs:	Desired (maximum) number of slabs.
  * @nareas:	Number of areas.
  * @phys_limit:	Maximum DMA buffer physical address.
+ * @attrs:	DMA attributes for the allocation.
  * @gfp:	GFP flags for the allocations.
  *
  * Allocate and initialize a new IO TLB memory pool. The actual number of
@@ -686,7 +704,8 @@ static void swiotlb_free_tlb(void *vaddr, size_t bytes)
  */
 static struct io_tlb_pool *swiotlb_alloc_pool(struct device *dev,
 		unsigned long minslabs, unsigned long nslabs,
-		unsigned int nareas, u64 phys_limit, gfp_t gfp)
+		unsigned int nareas, u64 phys_limit,
+		unsigned long attrs, gfp_t gfp)
 {
 	struct io_tlb_pool *pool;
 	unsigned int slot_order;
@@ -704,9 +723,10 @@ static struct io_tlb_pool *swiotlb_alloc_pool(struct device *dev,
 	if (!pool)
 		goto error;
 	pool->areas = (void *)pool + sizeof(*pool);
+	pool->unencrypted = !!(attrs & DMA_ATTR_CC_SHARED);
 
 	tlb_size = nslabs << IO_TLB_SHIFT;
-	while (!(tlb = swiotlb_alloc_tlb(dev, tlb_size, phys_limit, gfp))) {
+	while (!(tlb = swiotlb_alloc_tlb(dev, tlb_size, phys_limit, attrs, gfp))) {
 		if (nslabs <= minslabs)
 			goto error_tlb;
 		nslabs = ALIGN(nslabs >> 1, IO_TLB_SEGSIZE);
@@ -724,7 +744,8 @@ static struct io_tlb_pool *swiotlb_alloc_pool(struct device *dev,
 	return pool;
 
 error_slots:
-	swiotlb_free_tlb(page_address(tlb), tlb_size);
+	swiotlb_free_tlb(page_address(tlb), tlb_size,
+			 !!(attrs & DMA_ATTR_CC_SHARED));
 error_tlb:
 	kfree(pool);
 error:
@@ -742,7 +763,9 @@ static void swiotlb_dyn_alloc(struct work_struct *work)
 	struct io_tlb_pool *pool;
 
 	pool = swiotlb_alloc_pool(NULL, IO_TLB_MIN_SLABS, default_nslabs,
-				  default_nareas, mem->phys_limit, GFP_KERNEL);
+				  default_nareas, mem->phys_limit,
+				  mem->unencrypted ? DMA_ATTR_CC_SHARED : 0,
+				  GFP_KERNEL);
 	if (!pool) {
 		pr_warn_ratelimited("Failed to allocate new pool");
 		return;
@@ -762,7 +785,7 @@ static void swiotlb_dyn_free(struct rcu_head *rcu)
 	size_t tlb_size = pool->end - pool->start;
 
 	free_pages((unsigned long)pool->slots, get_order(slots_size));
-	swiotlb_free_tlb(pool->vaddr, tlb_size);
+	swiotlb_free_tlb(pool->vaddr, tlb_size, pool->unencrypted);
 	kfree(pool);
 }
 
@@ -1037,13 +1060,11 @@ static void dec_transient_used(struct io_tlb_mem *mem, unsigned int nslots)
  * Return: Index of the first allocated slot, or -1 on error.
  */
 static int swiotlb_search_pool_area(struct device *dev, struct io_tlb_pool *pool,
-		int area_index, phys_addr_t orig_addr, size_t alloc_size,
-		unsigned int alloc_align_mask)
+		int area_index, phys_addr_t orig_addr, dma_addr_t tbl_dma_addr,
+		size_t alloc_size, unsigned int alloc_align_mask)
 {
 	struct io_tlb_area *area = pool->areas + area_index;
 	unsigned long boundary_mask = dma_get_seg_boundary(dev);
-	dma_addr_t tbl_dma_addr =
-		phys_to_dma_unencrypted(dev, pool->start) & boundary_mask;
 	unsigned long max_slots = get_max_slots(boundary_mask);
 	unsigned int iotlb_align_mask = dma_get_min_align_mask(dev);
 	unsigned int nslots = nr_slots(alloc_size), stride;
@@ -1056,6 +1077,8 @@ static int swiotlb_search_pool_area(struct device *dev, struct io_tlb_pool *pool
 	BUG_ON(!nslots);
 	BUG_ON(area_index >= pool->nareas);
 
+	tbl_dma_addr &= boundary_mask;
+
 	/*
 	 * Historically, swiotlb allocations >= PAGE_SIZE were guaranteed to be
 	 * page-aligned in the absence of any other alignment requirements.
@@ -1167,6 +1190,7 @@ static int swiotlb_search_area(struct device *dev, int start_cpu,
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 	struct io_tlb_pool *pool;
+	dma_addr_t tbl_dma_addr;
 	int area_index;
 	int index = -1;
 
@@ -1175,9 +1199,15 @@ static int swiotlb_search_area(struct device *dev, int start_cpu,
 		if (cpu_offset >= pool->nareas)
 			continue;
 		area_index = (start_cpu + cpu_offset) & (pool->nareas - 1);
+
+		if (mem->unencrypted)
+			tbl_dma_addr = phys_to_dma_unencrypted(dev, pool->start);
+		else
+			tbl_dma_addr = phys_to_dma_encrypted(dev, pool->start);
+
 		index = swiotlb_search_pool_area(dev, pool, area_index,
-						 orig_addr, alloc_size,
-						 alloc_align_mask);
+						 orig_addr, tbl_dma_addr,
+						 alloc_size, alloc_align_mask);
 		if (index >= 0) {
 			*retpool = pool;
 			break;
@@ -1207,6 +1237,7 @@ static int swiotlb_find_slots(struct device *dev, phys_addr_t orig_addr,
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 	struct io_tlb_pool *pool;
+	dma_addr_t tbl_dma_addr;
 	unsigned long nslabs;
 	unsigned long flags;
 	u64 phys_limit;
@@ -1232,11 +1263,17 @@ static int swiotlb_find_slots(struct device *dev, phys_addr_t orig_addr,
 	nslabs = nr_slots(alloc_size);
 	phys_limit = min_not_zero(*dev->dma_mask, dev->bus_dma_limit);
 	pool = swiotlb_alloc_pool(dev, nslabs, nslabs, 1, phys_limit,
+				  mem->unencrypted ? DMA_ATTR_CC_SHARED : 0,
 				  GFP_NOWAIT);
 	if (!pool)
 		return -1;
 
-	index = swiotlb_search_pool_area(dev, pool, 0, orig_addr,
+	if (mem->unencrypted)
+		tbl_dma_addr = phys_to_dma_unencrypted(dev, pool->start);
+	else
+		tbl_dma_addr = phys_to_dma_encrypted(dev, pool->start);
+
+	index = swiotlb_search_pool_area(dev, pool, 0, orig_addr, tbl_dma_addr,
 					 alloc_size, alloc_align_mask);
 	if (index < 0) {
 		swiotlb_dyn_free(&pool->rcu);
@@ -1281,15 +1318,23 @@ static int swiotlb_find_slots(struct device *dev, phys_addr_t orig_addr,
 		size_t alloc_size, unsigned int alloc_align_mask,
 		struct io_tlb_pool **retpool)
 {
+	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 	struct io_tlb_pool *pool;
+	dma_addr_t tbl_dma_addr;
 	int start, i;
 	int index;
 
-	*retpool = pool = &dev->dma_io_tlb_mem->defpool;
+	*retpool = pool = &mem->defpool;
+	if (mem->unencrypted)
+		tbl_dma_addr = phys_to_dma_unencrypted(dev, pool->start);
+	else
+		tbl_dma_addr = phys_to_dma_encrypted(dev, pool->start);
+
 	i = start = raw_smp_processor_id() & (pool->nareas - 1);
 	do {
 		index = swiotlb_search_pool_area(dev, pool, i, orig_addr,
-						 alloc_size, alloc_align_mask);
+						 tbl_dma_addr, alloc_size,
+						 alloc_align_mask);
 		if (index >= 0)
 			return index;
 		if (++i >= pool->nareas)
@@ -1372,9 +1417,19 @@ static unsigned long mem_used(struct io_tlb_mem *mem)
  *			any pre- or post-padding for alignment
  * @alloc_align_mask:	Required start and end alignment of the allocated buffer
  * @dir:		DMA direction
- * @attrs:		Optional DMA attributes for the map operation
+ * @attrs:		Optional DMA attributes for the map operation, updated
+ *			to match the selected SWIOTLB pool
  *
  * Find and allocate a suitable sequence of IO TLB slots for the request.
+ * The device's SWIOTLB pool must match the device's current DMA encryption
+ * requirements. If the device requires decrypted DMA, bouncing is done through
+ * an unencrypted pool and the mapping is marked shared. If the device can DMA
+ * to encrypted memory, bouncing is done through an encrypted pool even when the
+ * original DMA address was unencrypted. Enabling encrypted DMA for a device is
+ * therefore expected to update its default io_tlb_mem to an encrypted pool, so
+ * later bounce mappings for both encrypted and decrypted original memory use
+ * that encrypted pool.
+ *
  * The allocated space starts at an alignment specified by alloc_align_mask,
  * and the size of the allocated space is rounded up so that the total amount
  * of allocated space is a multiple of (alloc_align_mask + 1). If
@@ -1411,6 +1466,16 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
 		pr_warn_once("Memory encryption is active and system is using DMA bounce buffers\n");
 
+	/* swiotlb pool is incorrect for this device */
+	if (unlikely(mem->unencrypted != force_dma_unencrypted(dev)))
+		return (phys_addr_t)DMA_MAPPING_ERROR;
+
+	/* Force attrs to match the kind of memory in the pool */
+	if (mem->unencrypted)
+		*attrs |= DMA_ATTR_CC_SHARED;
+	else
+		*attrs &= ~DMA_ATTR_CC_SHARED;
+
 	/*
 	 * The default swiotlb memory pool is allocated with PAGE_SIZE
 	 * alignment. If a mapping is requested with larger alignment,
@@ -1608,8 +1673,11 @@ dma_addr_t swiotlb_map(struct device *dev, phys_addr_t paddr, size_t size,
 	if (swiotlb_addr == (phys_addr_t)DMA_MAPPING_ERROR)
 		return DMA_MAPPING_ERROR;
 
-	/* Ensure that the address returned is DMA'ble */
-	dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
+	if (attrs & DMA_ATTR_CC_SHARED)
+		dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
+	else
+		dma_addr = phys_to_dma_encrypted(dev, swiotlb_addr);
+
 	if (unlikely(!dma_capable(dev, dma_addr, size, true))) {
 		__swiotlb_tbl_unmap_single(dev, swiotlb_addr, size, dir,
 			attrs | DMA_ATTR_SKIP_CPU_SYNC,
@@ -1773,7 +1841,7 @@ static inline void swiotlb_create_debugfs_files(struct io_tlb_mem *mem,
 
 #ifdef CONFIG_DMA_RESTRICTED_POOL
 
-struct page *swiotlb_alloc(struct device *dev, size_t size)
+struct page *swiotlb_alloc(struct device *dev, size_t size, unsigned long attrs)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 	struct io_tlb_pool *pool;
@@ -1784,6 +1852,9 @@ struct page *swiotlb_alloc(struct device *dev, size_t size)
 	if (!mem)
 		return NULL;
 
+	if (mem->unencrypted != !!(attrs & DMA_ATTR_CC_SHARED))
+		return NULL;
+
 	align = (1 << (get_order(size) + PAGE_SHIFT)) - 1;
 	index = swiotlb_find_slots(dev, 0, size, align, &pool);
 	if (index == -1)
@@ -1859,9 +1930,18 @@ static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
 			kfree(mem);
 			return -ENOMEM;
 		}
+		/*
+		 * if platform supports memory encryption,
+		 * restricted mem pool is decrypted by default
+		 */
+		if (cc_platform_has(CC_ATTR_MEM_ENCRYPT)) {
+			mem->unencrypted = true;
+			set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),
+					     rmem->size >> PAGE_SHIFT);
+		} else {
+			mem->unencrypted = false;
+		}
 
-		set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),
-				     rmem->size >> PAGE_SHIFT);
 		swiotlb_init_io_tlb_pool(pool, rmem->base, nslabs,
 					 false, nareas);
 		mem->force_bounce = true;

---

## [8] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 07/20] dma-mapping: make dma_pgprot() honor DMA_ATTR_CC_SHARED*

Fold encrypted/decrypted pgprot selection into dma_pgprot() so callers
do not need to adjust the page protection separately.

Update dma_pgprot() to apply pgprot_decrypted() when
DMA_ATTR_CC_SHARED is set and pgprot_encrypted() otherwise Convert
the dma-direct allocation and mmap paths to pass DMA_ATTR_CC_SHARED
instead of open-coding force_dma_unencrypted() handling around
dma_pgprot().

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c  |  8 +++-----
 kernel/dma/mapping.c | 16 ++++++++++++----
 2 files changed, 15 insertions(+), 9 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 0b4a26c6b6fd..e4cba322386d 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -290,9 +290,6 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	if (remap) {
 		pgprot_t prot = dma_pgprot(dev, PAGE_KERNEL, attrs);
 
-		if (force_dma_unencrypted(dev))
-			prot = pgprot_decrypted(prot);
-
 		/* remove any dirty cache lines on the kernel alias */
 		arch_dma_prep_coherent(page, size);
 
@@ -614,9 +611,10 @@ int dma_direct_mmap(struct device *dev, struct vm_area_struct *vma,
 	unsigned long pfn = PHYS_PFN(dma_to_phys(dev, dma_addr));
 	int ret = -ENXIO;
 
-	vma->vm_page_prot = dma_pgprot(dev, vma->vm_page_prot, attrs);
 	if (force_dma_unencrypted(dev))
-		vma->vm_page_prot = pgprot_decrypted(vma->vm_page_prot);
+		attrs |= DMA_ATTR_CC_SHARED;
+
+	vma->vm_page_prot = dma_pgprot(dev, vma->vm_page_prot, attrs);
 
 	if (dma_mmap_from_dev_coherent(dev, vma, cpu_addr, size, &ret))
 		return ret;
diff --git a/kernel/dma/mapping.c b/kernel/dma/mapping.c
index e6b07f160d20..3f4ae283c466 100644
--- a/kernel/dma/mapping.c
+++ b/kernel/dma/mapping.c
@@ -539,13 +539,21 @@ EXPORT_SYMBOL(dma_get_sgtable_attrs);
  */
 pgprot_t dma_pgprot(struct device *dev, pgprot_t prot, unsigned long attrs)
 {
+	pgprot_t dma_prot;
+
 	if (dev_is_dma_coherent(dev))
-		return prot;
+		dma_prot = prot;
 #ifdef CONFIG_ARCH_HAS_DMA_WRITE_COMBINE
-	if (attrs & DMA_ATTR_WRITE_COMBINE)
-		return pgprot_writecombine(prot);
+	else if (attrs & DMA_ATTR_WRITE_COMBINE)
+		dma_prot = pgprot_writecombine(prot);
 #endif
-	return pgprot_dmacoherent(prot);
+	else
+		dma_prot = pgprot_dmacoherent(prot);
+
+	if (attrs & DMA_ATTR_CC_SHARED)
+		return pgprot_decrypted(dma_prot);
+	else
+		return pgprot_encrypted(dma_prot);
 }
 #endif /* CONFIG_MMU */

---

## [9] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 08/20] dma-direct: pass attrs to dma_capable() for DMA_ATTR_CC_SHARED checks*

Teach dma_capable() about DMA_ATTR_CC_SHARED so the capability
check can reject encrypted DMA addresses for devices that require
unencrypted/shared DMA.

Also propagate DMA_ATTR_CC_SHARED in swiotlb_map() when the selected
SWIOTLB pool is decrypted so the capability check sees the correct DMA
address attribute.

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/x86/kernel/amd_gart_64.c | 30 ++++++++++++++++--------------
 drivers/xen/swiotlb-xen.c     |  6 +++---
 include/linux/dma-direct.h    | 10 +++++++++-
 kernel/dma/direct.h           |  6 +++---
 kernel/dma/swiotlb.c          |  2 +-
 5 files changed, 32 insertions(+), 22 deletions(-)

diff --git a/arch/x86/kernel/amd_gart_64.c b/arch/x86/kernel/amd_gart_64.c
index e8000a56732e..b5f1f031d45b 100644
--- a/arch/x86/kernel/amd_gart_64.c
+++ b/arch/x86/kernel/amd_gart_64.c
@@ -180,22 +180,23 @@ static void iommu_full(struct device *dev, size_t size, int dir)
 }
 
 static inline int
-need_iommu(struct device *dev, unsigned long addr, size_t size)
+need_iommu(struct device *dev, unsigned long addr, size_t size, unsigned long attrs)
 {
-	return force_iommu || !dma_capable(dev, addr, size, true);
+	return force_iommu || !dma_capable(dev, addr, size, true, attrs);
 }
 
 static inline int
-nonforced_iommu(struct device *dev, unsigned long addr, size_t size)
+nonforced_iommu(struct device *dev, unsigned long addr, size_t size,
+		unsigned long attrs)
 {
-	return !dma_capable(dev, addr, size, true);
+	return !dma_capable(dev, addr, size, true, attrs);
 }
 
 /* Map a single continuous physical area into the IOMMU.
  * Caller needs to check if the iommu is needed and flush.
  */
 static dma_addr_t dma_map_area(struct device *dev, dma_addr_t phys_mem,
-				size_t size, int dir, unsigned long align_mask)
+		size_t size, int dir, unsigned long align_mask, unsigned long attrs)
 {
 	unsigned long npages = iommu_num_pages(phys_mem, size, PAGE_SIZE);
 	unsigned long iommu_page;
@@ -206,7 +207,7 @@ static dma_addr_t dma_map_area(struct device *dev, dma_addr_t phys_mem,
 
 	iommu_page = alloc_iommu(dev, npages, align_mask);
 	if (iommu_page == -1) {
-		if (!nonforced_iommu(dev, phys_mem, size))
+		if (!nonforced_iommu(dev, phys_mem, size, attrs))
 			return phys_mem;
 		if (panic_on_overflow)
 			panic("dma_map_area overflow %lu bytes\n", size);
@@ -231,10 +232,10 @@ static dma_addr_t gart_map_phys(struct device *dev, phys_addr_t paddr,
 	if (unlikely(attrs & DMA_ATTR_MMIO))
 		return DMA_MAPPING_ERROR;
 
-	if (!need_iommu(dev, paddr, size))
+	if (!need_iommu(dev, paddr, size, attrs))
 		return paddr;
 
-	bus = dma_map_area(dev, paddr, size, dir, 0);
+	bus = dma_map_area(dev, paddr, size, dir, 0, attrs);
 	flush_gart();
 
 	return bus;
@@ -289,7 +290,7 @@ static void gart_unmap_sg(struct device *dev, struct scatterlist *sg, int nents,
 
 /* Fallback for dma_map_sg in case of overflow */
 static int dma_map_sg_nonforce(struct device *dev, struct scatterlist *sg,
-			       int nents, int dir)
+		int nents, int dir, unsigned long attrs)
 {
 	struct scatterlist *s;
 	int i;
@@ -301,8 +302,8 @@ static int dma_map_sg_nonforce(struct device *dev, struct scatterlist *sg,
 	for_each_sg(sg, s, nents, i) {
 		unsigned long addr = sg_phys(s);
 
-		if (nonforced_iommu(dev, addr, s->length)) {
-			addr = dma_map_area(dev, addr, s->length, dir, 0);
+		if (nonforced_iommu(dev, addr, s->length, attrs)) {
+			addr = dma_map_area(dev, addr, s->length, dir, 0, attrs);
 			if (addr == DMA_MAPPING_ERROR) {
 				if (i > 0)
 					gart_unmap_sg(dev, sg, i, dir, 0);
@@ -401,7 +402,7 @@ static int gart_map_sg(struct device *dev, struct scatterlist *sg, int nents,
 		s->dma_address = addr;
 		BUG_ON(s->length == 0);
 
-		nextneed = need_iommu(dev, addr, s->length);
+		nextneed = need_iommu(dev, addr, s->length, attrs);
 
 		/* Handle the previous not yet processed entries */
 		if (i > start) {
@@ -449,7 +450,7 @@ static int gart_map_sg(struct device *dev, struct scatterlist *sg, int nents,
 
 	/* When it was forced or merged try again in a dumb way */
 	if (force_iommu || iommu_merge) {
-		out = dma_map_sg_nonforce(dev, sg, nents, dir);
+		out = dma_map_sg_nonforce(dev, sg, nents, dir, attrs);
 		if (out > 0)
 			return out;
 	}
@@ -473,7 +474,8 @@ gart_alloc_coherent(struct device *dev, size_t size, dma_addr_t *dma_addr,
 		return vaddr;
 
 	*dma_addr = dma_map_area(dev, virt_to_phys(vaddr), size,
-			DMA_BIDIRECTIONAL, (1UL << get_order(size)) - 1);
+				 DMA_BIDIRECTIONAL,
+				 (1UL << get_order(size)) - 1, attrs);
 	flush_gart();
 	if (unlikely(*dma_addr == DMA_MAPPING_ERROR))
 		goto out_free;
diff --git a/drivers/xen/swiotlb-xen.c b/drivers/xen/swiotlb-xen.c
index 8c4abe65cd49..e2538824ef52 100644
--- a/drivers/xen/swiotlb-xen.c
+++ b/drivers/xen/swiotlb-xen.c
@@ -212,7 +212,7 @@ static dma_addr_t xen_swiotlb_map_phys(struct device *dev, phys_addr_t phys,
 	BUG_ON(dir == DMA_NONE);
 
 	if (attrs & DMA_ATTR_MMIO) {
-		if (unlikely(!dma_capable(dev, phys, size, false))) {
+		if (unlikely(!dma_capable(dev, phys, size, false, attrs))) {
 			dev_err_once(
 				dev,
 				"DMA addr %pa+%zu overflow (mask %llx, bus limit %llx).\n",
@@ -231,7 +231,7 @@ static dma_addr_t xen_swiotlb_map_phys(struct device *dev, phys_addr_t phys,
 	 * we can safely return the device addr and not worry about bounce
 	 * buffering it.
 	 */
-	if (dma_capable(dev, dev_addr, size, true) &&
+	if (dma_capable(dev, dev_addr, size, true, attrs) &&
 	    !dma_kmalloc_needs_bounce(dev, size, dir) &&
 	    !range_straddles_page_boundary(phys, size) &&
 		!xen_arch_need_swiotlb(dev, phys, dev_addr) &&
@@ -253,7 +253,7 @@ static dma_addr_t xen_swiotlb_map_phys(struct device *dev, phys_addr_t phys,
 	/*
 	 * Ensure that the address returned is DMA'ble
 	 */
-	if (unlikely(!dma_capable(dev, dev_addr, size, true))) {
+	if (unlikely(!dma_capable(dev, dev_addr, size, true, attrs))) {
 		__swiotlb_tbl_unmap_single(dev, map, size, dir,
 				attrs | DMA_ATTR_SKIP_CPU_SYNC,
 				swiotlb_find_pool(dev, map));
diff --git a/include/linux/dma-direct.h b/include/linux/dma-direct.h
index 94fad4e7c11e..daa31a1adf7b 100644
--- a/include/linux/dma-direct.h
+++ b/include/linux/dma-direct.h
@@ -135,12 +135,20 @@ static inline bool force_dma_unencrypted(struct device *dev)
 #endif /* CONFIG_ARCH_HAS_FORCE_DMA_UNENCRYPTED */
 
 static inline bool dma_capable(struct device *dev, dma_addr_t addr, size_t size,
-		bool is_ram)
+		bool is_ram, unsigned long attrs)
 {
 	dma_addr_t end = addr + size - 1;
 
 	if (addr == DMA_MAPPING_ERROR)
 		return false;
+	/*
+	 * The DMA address was derived from encrypted RAM, but this device
+	 * requires unencrypted DMA addresses. Treat it as not DMA-capable
+	 * so the caller can fall back to a suitable SWIOTLB pool.
+	 */
+	if (!(attrs & DMA_ATTR_CC_SHARED) && force_dma_unencrypted(dev))
+		return false;
+
 	if (is_ram && !IS_ENABLED(CONFIG_ARCH_DMA_ADDR_T_64BIT) &&
 	    min(addr, end) < phys_to_dma(dev, PFN_PHYS(min_low_pfn)))
 		return false;
diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
index 7140c208c123..e05dc7649366 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -101,15 +101,15 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 
 	if (attrs & DMA_ATTR_MMIO) {
 		dma_addr = phys;
-		if (unlikely(!dma_capable(dev, dma_addr, size, false)))
+		if (unlikely(!dma_capable(dev, dma_addr, size, false, attrs)))
 			goto err_overflow;
 	} else if (attrs & DMA_ATTR_CC_SHARED) {
 		dma_addr = phys_to_dma_unencrypted(dev, phys);
-		if (unlikely(!dma_capable(dev, dma_addr, size, false)))
+		if (unlikely(!dma_capable(dev, dma_addr, size, false, attrs)))
 			goto err_overflow;
 	} else {
 		dma_addr = phys_to_dma(dev, phys);
-		if (unlikely(!dma_capable(dev, dma_addr, size, true)) ||
+		if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs)) ||
 		    dma_kmalloc_needs_bounce(dev, size, dir)) {
 			if (is_swiotlb_active(dev) &&
 			    !(attrs & DMA_ATTR_REQUIRE_COHERENT))
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index 2bf3981db35d..f4e8b241a1c4 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -1678,7 +1678,7 @@ dma_addr_t swiotlb_map(struct device *dev, phys_addr_t paddr, size_t size,
 	else
 		dma_addr = phys_to_dma_encrypted(dev, swiotlb_addr);
 
-	if (unlikely(!dma_capable(dev, dma_addr, size, true))) {
+	if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs))) {
 		__swiotlb_tbl_unmap_single(dev, swiotlb_addr, size, dir,
 			attrs | DMA_ATTR_SKIP_CPU_SYNC,
 			swiotlb_find_pool(dev, swiotlb_addr));

---

## [10] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 09/20] dma-direct: make dma_direct_map_phys() honor DMA_ATTR_CC_SHARED*

Teach dma_direct_map_phys() to select the DMA address encoding based on
DMA_ATTR_CC_SHARED.

Use phys_to_dma_unencrypted() for decrypted mappings and
phys_to_dma_encrypted() otherwise. If a device requires unencrypted DMA
but the source physical address is still encrypted, force the mapping
through swiotlb so the DMA address and backing memory attributes remain
consistent.

Update the arm64, x86, s390 and powerpc secure-guest setup to not use
swiotlb force option

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
Changes from v3:
* Handle DMA_ATTR_MMIO
---
 arch/arm64/mm/init.c                 |  4 +--
 arch/powerpc/platforms/pseries/svm.c |  2 +-
 arch/s390/mm/init.c                  |  2 +-
 arch/x86/kernel/pci-dma.c            |  4 +--
 kernel/dma/direct.c                  |  4 ++-
 kernel/dma/direct.h                  | 45 +++++++++++++++-------------
 6 files changed, 31 insertions(+), 30 deletions(-)

diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
index 97987f850a33..acf67c7064db 100644
--- a/arch/arm64/mm/init.c
+++ b/arch/arm64/mm/init.c
@@ -338,10 +338,8 @@ void __init arch_mm_preinit(void)
 	unsigned int flags = SWIOTLB_VERBOSE;
 	bool swiotlb = max_pfn > PFN_DOWN(arm64_dma_phys_limit);
 
-	if (is_realm_world()) {
+	if (is_realm_world())
 		swiotlb = true;
-		flags |= SWIOTLB_FORCE;
-	}
 
 	if (IS_ENABLED(CONFIG_DMA_BOUNCE_UNALIGNED_KMALLOC) && !swiotlb) {
 		/*
diff --git a/arch/powerpc/platforms/pseries/svm.c b/arch/powerpc/platforms/pseries/svm.c
index 384c9dc1899a..7a403dbd35ee 100644
--- a/arch/powerpc/platforms/pseries/svm.c
+++ b/arch/powerpc/platforms/pseries/svm.c
@@ -29,7 +29,7 @@ static int __init init_svm(void)
 	 * need to use the SWIOTLB buffer for DMA even if dma_capable() says
 	 * otherwise.
 	 */
-	ppc_swiotlb_flags |= SWIOTLB_ANY | SWIOTLB_FORCE;
+	ppc_swiotlb_flags |= SWIOTLB_ANY;
 
 	/* Share the SWIOTLB buffer with the host. */
 	swiotlb_update_mem_attributes();
diff --git a/arch/s390/mm/init.c b/arch/s390/mm/init.c
index ad3c6d92b801..581af1483c42 100644
--- a/arch/s390/mm/init.c
+++ b/arch/s390/mm/init.c
@@ -163,7 +163,7 @@ static void __init pv_init(void)
 	virtio_set_mem_acc_cb(virtio_require_restricted_mem_acc);
 
 	/* make sure bounce buffers are shared */
-	swiotlb_init(true, SWIOTLB_FORCE | SWIOTLB_VERBOSE);
+	swiotlb_init(true, SWIOTLB_VERBOSE);
 	swiotlb_update_mem_attributes();
 }
 
diff --git a/arch/x86/kernel/pci-dma.c b/arch/x86/kernel/pci-dma.c
index 6267363e0189..75cf8f6ae8cd 100644
--- a/arch/x86/kernel/pci-dma.c
+++ b/arch/x86/kernel/pci-dma.c
@@ -59,10 +59,8 @@ static void __init pci_swiotlb_detect(void)
 	 * bounce buffers as the hypervisor can't access arbitrary VM memory
 	 * that is not explicitly shared with it.
 	 */
-	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT)) {
+	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
 		x86_swiotlb_enable = true;
-		x86_swiotlb_flags |= SWIOTLB_FORCE;
-	}
 }
 #else
 static inline void __init pci_swiotlb_detect(void)
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index e4cba322386d..6d0ce3cfd8cc 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -702,8 +702,10 @@ size_t dma_direct_max_mapping_size(struct device *dev)
 {
 	/* If SWIOTLB is active, use its maximum mapping size */
 	if (is_swiotlb_active(dev) &&
-	    (dma_addressing_limited(dev) || is_swiotlb_force_bounce(dev)))
+	    (dma_addressing_limited(dev) || is_swiotlb_force_bounce(dev) ||
+	     force_dma_unencrypted(dev)))
 		return swiotlb_max_mapping_size(dev);
+
 	return SIZE_MAX;
 }
 
diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
index e05dc7649366..f3fc28f352ba 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -88,37 +88,40 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 {
 	dma_addr_t dma_addr;
 
+	/*
+	 * For a device requiring unencrypted DMA, MMIO memory is treated
+	 * as shared by default.
+	 */
+	if (force_dma_unencrypted(dev) && (attrs & DMA_ATTR_MMIO))
+		attrs |= DMA_ATTR_CC_SHARED;
+
 	if (is_swiotlb_force_bounce(dev)) {
-		if (!(attrs & DMA_ATTR_CC_SHARED)) {
-			if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
-				return DMA_MAPPING_ERROR;
+		if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
+			return DMA_MAPPING_ERROR;
 
-			return swiotlb_map(dev, phys, size, dir, attrs);
-		}
-	} else if (attrs & DMA_ATTR_CC_SHARED) {
-		return DMA_MAPPING_ERROR;
+		return swiotlb_map(dev, phys, size, dir, attrs);
 	}
 
-	if (attrs & DMA_ATTR_MMIO) {
-		dma_addr = phys;
-		if (unlikely(!dma_capable(dev, dma_addr, size, false, attrs)))
-			goto err_overflow;
-	} else if (attrs & DMA_ATTR_CC_SHARED) {
+	if (attrs & DMA_ATTR_CC_SHARED)
 		dma_addr = phys_to_dma_unencrypted(dev, phys);
+	else
+		dma_addr = phys_to_dma_encrypted(dev, phys);
+
+	if (attrs & DMA_ATTR_MMIO) {
 		if (unlikely(!dma_capable(dev, dma_addr, size, false, attrs)))
 			goto err_overflow;
-	} else {
-		dma_addr = phys_to_dma(dev, phys);
-		if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs)) ||
-		    dma_kmalloc_needs_bounce(dev, size, dir)) {
-			if (is_swiotlb_active(dev) &&
-			    !(attrs & DMA_ATTR_REQUIRE_COHERENT))
-				return swiotlb_map(dev, phys, size, dir, attrs);
+		goto dma_mapped;
+	}
 
-			goto err_overflow;
-		}
+	if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs)) ||
+	    dma_kmalloc_needs_bounce(dev, size, dir)) {
+		if (is_swiotlb_active(dev) &&
+		    !(attrs & DMA_ATTR_REQUIRE_COHERENT))
+			return swiotlb_map(dev, phys, size, dir, attrs);
+		goto err_overflow;
 	}
 
+dma_mapped:
 	if (!dev_is_dma_coherent(dev) &&
 	    !(attrs & (DMA_ATTR_SKIP_CPU_SYNC | DMA_ATTR_MMIO))) {
 		arch_sync_dma_for_device(phys, size, dir);

---

## [11] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 10/20] dma-direct: set decrypted flag for remapped DMA allocations*

Devices that are DMA non-coherent and require a remap were skipping
dma_set_decrypted(), leaving DMA buffers encrypted even when the device
requires unencrypted access. Move the call after the if (remap) branch
so that both the direct and remapped allocation paths correctly mark the
allocation as decrypted (or fail cleanly) before use.

Fix dma_direct_alloc() and dma_direct_free() to apply set_memory_*() to
the linear-map alias of the backing pages instead of the remapped CPU
address. Also disallow highmem pages for DMA_ATTR_CC_SHARED, because
highmem buffers do not provide a usable linear-map address.

Fixes: f3c962226dbe ("dma-direct: clean up the remapping checks in dma_direct_alloc")
Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 55 ++++++++++++++++++++++++++++++++++++---------
 1 file changed, 44 insertions(+), 11 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 6d0ce3cfd8cc..9ce4fff6c112 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -196,6 +196,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 {
 	bool remap = false, set_uncached = false;
 	bool mark_mem_decrypt = false;
+	bool allow_highmem = true;
 	struct page *page;
 	void *ret;
 
@@ -214,6 +215,15 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		mark_mem_decrypt = true;
 	}
 
+	if (attrs & DMA_ATTR_CC_SHARED)
+		/*
+		 * Unencrypted/shared DMA requires a linear-mapped buffer
+		 * address to look up the PFN and set architecture-required PFN
+		 * attributes. This is not possible with HighMem. Avoid HighMem
+		 * allocation.
+		 */
+		allow_highmem = false;
+
 	size = PAGE_ALIGN(size);
 	if (attrs & DMA_ATTR_NO_WARN)
 		gfp |= __GFP_NOWARN;
@@ -272,7 +282,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	}
 
 	/* we always manually zero the memory once we are done */
-	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, true);
+	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, allow_highmem);
 	if (!page)
 		return NULL;
 
@@ -287,6 +297,14 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		set_uncached = false;
 	}
 
+	if (mark_mem_decrypt) {
+		void *lm_addr;
+
+		lm_addr = page_address(page);
+		if (set_memory_decrypted((unsigned long)lm_addr, PFN_UP(size)))
+			goto out_leak_pages;
+	}
+
 	if (remap) {
 		pgprot_t prot = dma_pgprot(dev, PAGE_KERNEL, attrs);
 
@@ -297,29 +315,36 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		ret = dma_common_contiguous_remap(page, size, prot,
 				__builtin_return_address(0));
 		if (!ret)
-			goto out_free_pages;
+			goto out_encrypt_pages;
 	} else {
 		ret = page_address(page);
-		if (mark_mem_decrypt && dma_set_decrypted(dev, ret, size))
-			goto out_leak_pages;
 	}
 
 	memset(ret, 0, size);
 
 	if (set_uncached) {
+		void *uncached_cpu_addr;
+
 		arch_dma_prep_coherent(page, size);
-		ret = arch_dma_set_uncached(ret, size);
-		if (IS_ERR(ret))
-			goto out_encrypt_pages;
+		uncached_cpu_addr = arch_dma_set_uncached(ret, size);
+		if (IS_ERR(uncached_cpu_addr))
+			goto out_free_remap_pages;
+		ret = uncached_cpu_addr;
 	}
 
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
 	return ret;
 
+
+out_free_remap_pages:
+	if (remap)
+		dma_common_free_remap(ret, size);
+
 out_encrypt_pages:
-	if (mark_mem_decrypt && dma_set_encrypted(dev, page_address(page), size))
-		return NULL;
-out_free_pages:
+	if (mark_mem_decrypt &&
+	    dma_set_encrypted(dev, page_address(page), size))
+		goto out_leak_pages;
+
 	if (!swiotlb_free(dev, page, size))
 		dma_free_contiguous(dev, page, size);
 	return NULL;
@@ -384,8 +409,16 @@ void dma_direct_free(struct device *dev, size_t size,
 	} else {
 		if (IS_ENABLED(CONFIG_ARCH_HAS_DMA_CLEAR_UNCACHED))
 			arch_dma_clear_uncached(cpu_addr, size);
-		if (mark_mem_encrypted && dma_set_encrypted(dev, cpu_addr, size))
+	}
+
+	if (mark_mem_encrypted) {
+		void *lm_addr;
+
+		lm_addr = phys_to_virt(phys);
+		if (set_memory_encrypted((unsigned long)lm_addr, PFN_UP(size))) {
+			pr_warn_ratelimited("leaking DMA memory that can't be re-encrypted\n");
 			return;
+		}
 	}
 
 	if (swiotlb_pool)

---

## [12] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 11/20] dma-direct: select DMA address encoding from DMA_ATTR_CC_SHARED*

Make the dma-direct helpers derive the DMA address encoding from
DMA_ATTR_CC_SHARED instead of implicitly relying on
force_dma_unencrypted() inside phys_to_dma_direct()

Pass an explicit unencrypted/decrypted state into phys_to_dma_direct(),
make the alloc paths return DMA addresses that match the requested buffer
encryption state. Also only call dma_set_decrypted() when
DMA_ATTR_CC_SHARED is actually set.

Tested-by: Jiri Pirko <jiri@nvidia.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 42 +++++++++++++++++++++++++-----------------
 1 file changed, 25 insertions(+), 17 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 9ce4fff6c112..aa3489aa10a0 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -24,11 +24,11 @@
 u64 zone_dma_limit __ro_after_init = DMA_BIT_MASK(24);
 
 static inline dma_addr_t phys_to_dma_direct(struct device *dev,
-		phys_addr_t phys)
+		phys_addr_t phys, bool unencrypted)
 {
-	if (force_dma_unencrypted(dev))
+	if (unencrypted)
 		return phys_to_dma_unencrypted(dev, phys);
-	return phys_to_dma(dev, phys);
+	return phys_to_dma_encrypted(dev, phys);
 }
 
 static inline struct page *dma_direct_to_page(struct device *dev,
@@ -39,8 +39,9 @@ static inline struct page *dma_direct_to_page(struct device *dev,
 
 u64 dma_direct_get_required_mask(struct device *dev)
 {
+	bool require_decrypted = force_dma_unencrypted(dev);
 	phys_addr_t phys = ((phys_addr_t)max_pfn << PAGE_SHIFT) - 1;
-	u64 max_dma = phys_to_dma_direct(dev, phys);
+	u64 max_dma = phys_to_dma_direct(dev, phys, require_decrypted);
 
 	return (1ULL << (fls64(max_dma) - 1)) * 2 - 1;
 }
@@ -69,7 +70,8 @@ static gfp_t dma_direct_optimal_gfp_mask(struct device *dev, u64 *phys_limit)
 
 bool dma_coherent_ok(struct device *dev, phys_addr_t phys, size_t size)
 {
-	dma_addr_t dma_addr = phys_to_dma_direct(dev, phys);
+	bool require_decrypted = force_dma_unencrypted(dev);
+	dma_addr_t dma_addr = phys_to_dma_direct(dev, phys, require_decrypted);
 
 	if (dma_addr == DMA_MAPPING_ERROR)
 		return false;
@@ -79,17 +81,18 @@ bool dma_coherent_ok(struct device *dev, phys_addr_t phys, size_t size)
 
 static int dma_set_decrypted(struct device *dev, void *vaddr, size_t size)
 {
-	if (!force_dma_unencrypted(dev))
-		return 0;
-	return set_memory_decrypted((unsigned long)vaddr, PFN_UP(size));
+	int ret;
+
+	ret = set_memory_decrypted((unsigned long)vaddr, PFN_UP(size));
+	if (ret)
+		pr_warn_ratelimited("leaking DMA memory that can't be decrypted\n");
+	return ret;
 }
 
 static int dma_set_encrypted(struct device *dev, void *vaddr, size_t size)
 {
 	int ret;
 
-	if (!force_dma_unencrypted(dev))
-		return 0;
 	ret = set_memory_encrypted((unsigned long)vaddr, PFN_UP(size));
 	if (ret)
 		pr_warn_ratelimited("leaking DMA memory that can't be re-encrypted\n");
@@ -169,7 +172,8 @@ static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
 				   dma_coherent_ok);
 	if (!page)
 		return NULL;
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
+					 !!(attrs & DMA_ATTR_CC_SHARED));
 	return ret;
 }
 
@@ -185,9 +189,11 @@ static void *dma_direct_alloc_no_mapping(struct device *dev, size_t size,
 	/* remove any dirty cache lines on the kernel alias */
 	if (!PageHighMem(page))
 		arch_dma_prep_coherent(page, size);
-
-	/* return the page pointer as the opaque cookie */
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	/*
+	 * return the page pointer as the opaque cookie.
+	 * Never used for unencrypted allocation
+	 */
+	*dma_handle = phys_to_dma_encrypted(dev, page_to_phys(page));
 	return page;
 }
 
@@ -332,7 +338,8 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		ret = uncached_cpu_addr;
 	}
 
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
+					 !!(attrs & DMA_ATTR_CC_SHARED));
 	return ret;
 
 
@@ -455,11 +462,12 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 		return NULL;
 
 	ret = page_address(page);
-	if (dma_set_decrypted(dev, ret, size))
+	if ((attrs & DMA_ATTR_CC_SHARED) && dma_set_decrypted(dev, ret, size))
 		goto out_leak_pages;
 setup_page:
 	memset(ret, 0, size);
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
+					 !!(attrs & DMA_ATTR_CC_SHARED));
 	return page;
 out_leak_pages:
 	return NULL;

---

## [13] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 12/20] dma-pool: fix page leak in atomic_pool_expand() cleanup*

atomic_pool_expand() frees the allocated pages from the remove_mapping
error path only when CONFIG_DMA_DIRECT_REMAP is enabled.

When CONFIG_DMA_DIRECT_REMAP is disabled, failures after page allocation,
such as gen_pool_add_virt(), jump to remove_mapping and return without
freeing the pages.

Move __free_pages(page, order) out of the CONFIG_DMA_DIRECT_REMAP block so
that cleanup paths always release the allocation.

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/pool.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index be78474a6c49..e7df8d279e75 100644
--- a/kernel/dma/pool.c
+++ b/kernel/dma/pool.c
@@ -146,9 +146,9 @@ static int atomic_pool_expand(struct dma_gen_pool *dma_pool, size_t pool_size,
 #ifdef CONFIG_DMA_DIRECT_REMAP
 	dma_common_free_remap(addr, pool_size);
 free_page:
+#endif
 	if (!leak_pages)
 		__free_pages(page, order);
-#endif
 out:
 	return ret;
 }

---

## [14] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 13/20] dma-direct: rename ret to cpu_addr in alloc helpers*

ret in dma_direct_alloc() and dma_direct_alloc_pages() holds the returned
CPU mapping, not a generic return value. Rename it to cpu_addr and update
the remaining uses to match.

This makes the allocation paths easier to follow and keeps the local naming
consistent with what the variable actually represents.

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 31 +++++++++++++++----------------
 1 file changed, 15 insertions(+), 16 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index aa3489aa10a0..4e446aa4130e 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -204,7 +204,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	bool mark_mem_decrypt = false;
 	bool allow_highmem = true;
 	struct page *page;
-	void *ret;
+	void *cpu_addr;
 
 	/*
 	 * DMA_ATTR_CC_SHARED is not a caller-visible dma_alloc_*()
@@ -318,34 +318,33 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		arch_dma_prep_coherent(page, size);
 
 		/* create a coherent mapping */
-		ret = dma_common_contiguous_remap(page, size, prot,
-				__builtin_return_address(0));
-		if (!ret)
+		cpu_addr = dma_common_contiguous_remap(page, size, prot,
+					__builtin_return_address(0));
+		if (!cpu_addr)
 			goto out_encrypt_pages;
 	} else {
-		ret = page_address(page);
+		cpu_addr = page_address(page);
 	}
 
-	memset(ret, 0, size);
+	memset(cpu_addr, 0, size);
 
 	if (set_uncached) {
 		void *uncached_cpu_addr;
 
 		arch_dma_prep_coherent(page, size);
-		uncached_cpu_addr = arch_dma_set_uncached(ret, size);
+		uncached_cpu_addr = arch_dma_set_uncached(cpu_addr, size);
 		if (IS_ERR(uncached_cpu_addr))
 			goto out_free_remap_pages;
-		ret = uncached_cpu_addr;
+		cpu_addr = uncached_cpu_addr;
 	}
 
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
 					 !!(attrs & DMA_ATTR_CC_SHARED));
-	return ret;
-
+	return cpu_addr;
 
 out_free_remap_pages:
 	if (remap)
-		dma_common_free_remap(ret, size);
+		dma_common_free_remap(cpu_addr, size);
 
 out_encrypt_pages:
 	if (mark_mem_decrypt &&
@@ -439,7 +438,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 {
 	unsigned long attrs = 0;
 	struct page *page;
-	void *ret;
+	void *cpu_addr;
 
 	if (force_dma_unencrypted(dev))
 		attrs |= DMA_ATTR_CC_SHARED;
@@ -453,7 +452,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 		if (!page)
 			return NULL;
 
-		ret = page_address(page);
+		cpu_addr = page_address(page);
 		goto setup_page;
 	}
 
@@ -461,11 +460,11 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	if (!page)
 		return NULL;
 
-	ret = page_address(page);
-	if ((attrs & DMA_ATTR_CC_SHARED) && dma_set_decrypted(dev, ret, size))
+	cpu_addr = page_address(page);
+	if ((attrs & DMA_ATTR_CC_SHARED) && dma_set_decrypted(dev, cpu_addr, size))
 		goto out_leak_pages;
 setup_page:
-	memset(ret, 0, size);
+	memset(cpu_addr, 0, size);
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
 					 !!(attrs & DMA_ATTR_CC_SHARED));
 	return page;

---

## [15] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 14/20] dma-direct: return struct page from dma_direct_alloc_from_pool()*

Commit 5b138c534fda ("dma-direct: factor out a dma_direct_alloc_from_pool
helper") changed dma_direct_alloc_from_pool() to return the CPU address
from dma_alloc_from_pool(). That fits dma_direct_alloc(), but
dma_direct_alloc_pages() also uses the helper and expects a struct page *.

Fix this by making dma_direct_alloc_from_pool() return the struct page *
again, and pass the CPU address back through an out-parameter for the
dma_direct_alloc() caller.

Fixes: 5b138c534fda ("dma-direct: factor out a dma_direct_alloc_from_pool helper")
Cc: stable@vger.kernel.org

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 21 ++++++++++++---------
 1 file changed, 12 insertions(+), 9 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 4e446aa4130e..e0ab9ff3f1d6 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -157,24 +157,24 @@ static bool dma_direct_use_pool(struct device *dev, gfp_t gfp)
 	return !gfpflags_allow_blocking(gfp) && !is_swiotlb_for_alloc(dev);
 }
 
-static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
-		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)
+static struct page *dma_direct_alloc_from_pool(struct device *dev, size_t size,
+		dma_addr_t *dma_handle, void **cpu_addr, gfp_t gfp,
+		unsigned long attrs)
 {
 	struct page *page;
 	u64 phys_limit;
-	void *ret;
 
 	if (WARN_ON_ONCE(!IS_ENABLED(CONFIG_DMA_COHERENT_POOL)))
 		return NULL;
 
 	gfp |= dma_direct_optimal_gfp_mask(dev, &phys_limit);
-	page = dma_alloc_from_pool(dev, size, &ret, gfp, attrs,
+	page = dma_alloc_from_pool(dev, size, cpu_addr, gfp, attrs,
 				   dma_coherent_ok);
 	if (!page)
 		return NULL;
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
 					 !!(attrs & DMA_ATTR_CC_SHARED));
-	return ret;
+	return page;
 }
 
 static void *dma_direct_alloc_no_mapping(struct device *dev, size_t size,
@@ -270,9 +270,12 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	 * the atomic pools instead if we aren't allowed block.
 	 */
 	if ((remap || (attrs & DMA_ATTR_CC_SHARED)) &&
-	    dma_direct_use_pool(dev, gfp))
-		return dma_direct_alloc_from_pool(dev, size, dma_handle,
-						  gfp, attrs);
+	    dma_direct_use_pool(dev, gfp)) {
+		page = dma_direct_alloc_from_pool(dev, size,
+					dma_handle, &cpu_addr,
+					gfp, attrs);
+		return page ? cpu_addr : NULL;
+	}
 
 	if (is_swiotlb_for_alloc(dev)) {
 		page = dma_direct_alloc_swiotlb(dev, size, attrs);
@@ -445,7 +448,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 
 	if ((attrs & DMA_ATTR_CC_SHARED) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle,
-						  gfp, attrs);
+						  &cpu_addr, gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
 		page = dma_direct_alloc_swiotlb(dev, size, attrs);

---

## [16] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 15/20] iommu/dma: Check atomic pool allocation result directly*

The non-blocking, non-coherent allocation path uses dma_alloc_from_pool(),
which returns the allocated page and fills cpu_addr only on success.

Do not rely on cpu_addr to detect allocation failure in this path. Check
the returned page directly before using it for the IOMMU mapping.

Fixes: 9420139f516d ("dma-pool: fix coherent pool allocations for IOMMU mappings")
Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/dma-iommu.c | 11 +++++++----
 1 file changed, 7 insertions(+), 4 deletions(-)

diff --git a/drivers/iommu/dma-iommu.c b/drivers/iommu/dma-iommu.c
index 725c7adb0a8d..52c599f4472c 100644
--- a/drivers/iommu/dma-iommu.c
+++ b/drivers/iommu/dma-iommu.c
@@ -1671,13 +1671,16 @@ void *iommu_dma_alloc(struct device *dev, size_t size, dma_addr_t *handle,
 	}
 
 	if (IS_ENABLED(CONFIG_DMA_DIRECT_REMAP) &&
-	    !gfpflags_allow_blocking(gfp) && !coherent)
+	    !gfpflags_allow_blocking(gfp) && !coherent) {
 		page = dma_alloc_from_pool(dev, PAGE_ALIGN(size), &cpu_addr,
 					   gfp, attrs, NULL);
-	else
+		if (!page)
+			return NULL;
+	} else {
 		cpu_addr = iommu_dma_alloc_pages(dev, size, &page, gfp, attrs);
-	if (!cpu_addr)
-		return NULL;
+		if (!cpu_addr)
+			return NULL;
+	}
 
 	*handle = __iommu_dma_map(dev, page_to_phys(page), size, ioprot,
 			dev->coherent_dma_mask);

---

## [17] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 16/20] dma: swiotlb: free dynamic pools from process context*

swiotlb_dyn_free() is used after removing a dynamic swiotlb pool from
RCU-protected lists. It can call swiotlb_free_tlb(), which may need to
restore the encryption state of an unencrypted pool with
set_memory_encrypted() before freeing the pages.

RCU callbacks run in atomic context, but set_memory_encrypted() is not
guaranteed to be atomic-safe on all architectures. For example, page
attribute updates may allocate page tables or take sleeping locks.

Use queue_rcu_work() for dynamic pool freeing instead. This keeps the RCU
grace period before freeing a published pool, while running the actual pool
teardown from workqueue context. Use the same helper for the transient-pool
error path, since that path may also be reached from atomic DMA mapping
context.

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 include/linux/swiotlb.h |  4 ++--
 kernel/dma/swiotlb.c    | 19 +++++++++++--------
 2 files changed, 13 insertions(+), 10 deletions(-)

diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 4dcbf3931be1..526f82e9da45 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -64,7 +64,7 @@ extern void __init swiotlb_update_mem_attributes(void);
  * @areas:	Array of memory area descriptors.
  * @slots:	Array of slot descriptors.
  * @node:	Member of the IO TLB memory pool list.
- * @rcu:	RCU head for swiotlb_dyn_free().
+ * @dyn_free:	RCU work item used to free the pool from process context.
  * @transient:  %true if transient memory pool.
  */
 struct io_tlb_pool {
@@ -79,7 +79,7 @@ struct io_tlb_pool {
 	struct io_tlb_slot *slots;
 #ifdef CONFIG_SWIOTLB_DYNAMIC
 	struct list_head node;
-	struct rcu_head rcu;
+	struct rcu_work dyn_free;
 	bool transient;
 	bool unencrypted;
 #endif
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index f4e8b241a1c4..4c56f64602ea 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -774,13 +774,10 @@ static void swiotlb_dyn_alloc(struct work_struct *work)
 	add_mem_pool(mem, pool);
 }
 
-/**
- * swiotlb_dyn_free() - RCU callback to free a memory pool
- * @rcu:	RCU head in the corresponding struct io_tlb_pool.
- */
-static void swiotlb_dyn_free(struct rcu_head *rcu)
+static void swiotlb_dyn_free_work(struct work_struct *work)
 {
-	struct io_tlb_pool *pool = container_of(rcu, struct io_tlb_pool, rcu);
+	struct io_tlb_pool *pool =
+		container_of(to_rcu_work(work), struct io_tlb_pool, dyn_free);
 	size_t slots_size = array_size(sizeof(*pool->slots), pool->nslabs);
 	size_t tlb_size = pool->end - pool->start;
 
@@ -789,6 +786,12 @@ static void swiotlb_dyn_free(struct rcu_head *rcu)
 	kfree(pool);
 }
 
+static void swiotlb_schedule_dyn_free(struct io_tlb_pool *pool)
+{
+	INIT_RCU_WORK(&pool->dyn_free, swiotlb_dyn_free_work);
+	queue_rcu_work(system_wq, &pool->dyn_free);
+}
+
 /**
  * __swiotlb_find_pool() - find the IO TLB pool for a physical address
  * @dev:        Device which has mapped the DMA buffer.
@@ -835,7 +838,7 @@ static void swiotlb_del_pool(struct device *dev, struct io_tlb_pool *pool)
 	list_del_rcu(&pool->node);
 	spin_unlock_irqrestore(&dev->dma_io_tlb_lock, flags);
 
-	call_rcu(&pool->rcu, swiotlb_dyn_free);
+	swiotlb_schedule_dyn_free(pool);
 }
 
 #endif	/* CONFIG_SWIOTLB_DYNAMIC */
@@ -1276,7 +1279,7 @@ static int swiotlb_find_slots(struct device *dev, phys_addr_t orig_addr,
 	index = swiotlb_search_pool_area(dev, pool, 0, orig_addr, tbl_dma_addr,
 					 alloc_size, alloc_align_mask);
 	if (index < 0) {
-		swiotlb_dyn_free(&pool->rcu);
+		swiotlb_schedule_dyn_free(pool);
 		return -1;
 	}

---

## [18] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 17/20] dma: swiotlb: handle set_memory_decrypted() failures*

Check the return value when converting swiotlb pools between encrypted and
decrypted mappings. If the default pool cannot be decrypted after early
initialization, mark the pool fully used so it cannot satisfy future bounce
allocations.

For late initialization, return the `set_memory_decrypted()` failure. For
restricted DMA pools, fail device initialization if the reserved pool
cannot be decrypted.

This prevents swiotlb from using pools whose encryption attributes do not
match their metadata, and avoids returning pages with uncertain encryption
state back to the allocator.

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/swiotlb.c | 80 +++++++++++++++++++++++++++++++++++---------
 1 file changed, 65 insertions(+), 15 deletions(-)

diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index 4c56f64602ea..14d834ca298b 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -248,6 +248,23 @@ static inline unsigned long nr_slots(u64 val)
 	return DIV_ROUND_UP(val, IO_TLB_SIZE);
 }
 
+static void swiotlb_mark_pool_used(struct io_tlb_pool *pool)
+{
+	unsigned long i;
+
+	for (i = 0; i < pool->nareas; i++) {
+		pool->areas[i].index = 0;
+		pool->areas[i].used = pool->area_nslabs;
+	}
+
+	for (i = 0; i < pool->nslabs; i++) {
+		pool->slots[i].list = 0;
+		pool->slots[i].orig_addr = INVALID_PHYS_ADDR;
+		pool->slots[i].alloc_size = 0;
+		pool->slots[i].pad_slots = 0;
+	}
+}
+
 /*
  * Early SWIOTLB allocation may be too early to allow an architecture to
  * perform the desired operations.  This function allows the architecture to
@@ -272,8 +289,16 @@ void __init swiotlb_update_mem_attributes(void)
 		return;
 	bytes = PAGE_ALIGN(mem->nslabs << IO_TLB_SHIFT);
 
-	if (io_tlb_default_mem.unencrypted)
-		set_memory_decrypted((unsigned long)mem->vaddr, bytes >> PAGE_SHIFT);
+	if (io_tlb_default_mem.unencrypted) {
+		int ret;
+
+		ret = set_memory_decrypted((unsigned long)mem->vaddr,
+					   bytes >> PAGE_SHIFT);
+		if (ret) {
+			pr_warn("Failed to decrypt default memory pool, disabling it\n");
+			swiotlb_mark_pool_used(mem);
+		}
+	}
 }
 
 static void swiotlb_init_io_tlb_pool(struct io_tlb_pool *mem, phys_addr_t start,
@@ -442,9 +467,10 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 {
 	struct io_tlb_pool *mem = &io_tlb_default_mem.defpool;
 	unsigned long nslabs = ALIGN(size >> IO_TLB_SHIFT, IO_TLB_SEGSIZE);
+	unsigned int order, area_order, slot_order;
+	bool leak_pages = false;
 	unsigned int nareas;
 	unsigned char *vstart = NULL;
-	unsigned int order, area_order;
 	bool retried = false;
 	int rc = 0;
 
@@ -504,6 +530,7 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 			(PAGE_SIZE << order) >> 20);
 	}
 
+	rc = -ENOMEM;
 	nareas = limit_nareas(default_nareas, nslabs);
 	area_order = get_order(array_size(sizeof(*mem->areas), nareas));
 	mem->areas = (struct io_tlb_area *)
@@ -511,14 +538,20 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 	if (!mem->areas)
 		goto error_area;
 
+	slot_order = get_order(array_size(sizeof(*mem->slots), nslabs));
 	mem->slots = (void *)__get_free_pages(GFP_KERNEL | __GFP_ZERO,
-		get_order(array_size(sizeof(*mem->slots), nslabs)));
+					      slot_order);
 	if (!mem->slots)
 		goto error_slots;
 
-	if (io_tlb_default_mem.unencrypted)
-		set_memory_decrypted((unsigned long)vstart,
-				     (nslabs << IO_TLB_SHIFT) >> PAGE_SHIFT);
+	if (io_tlb_default_mem.unencrypted) {
+		rc = set_memory_decrypted((unsigned long)vstart,
+					  (nslabs << IO_TLB_SHIFT) >> PAGE_SHIFT);
+		if (rc) {
+			leak_pages = true;
+			goto error_decrypt;
+		}
+	}
 
 	swiotlb_init_io_tlb_pool(mem, virt_to_phys(vstart), nslabs, true,
 				 nareas);
@@ -527,16 +560,20 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 	swiotlb_print_info();
 	return 0;
 
+error_decrypt:
+	free_pages((unsigned long)mem->slots, slot_order);
 error_slots:
 	free_pages((unsigned long)mem->areas, area_order);
 error_area:
-	free_pages((unsigned long)vstart, order);
-	return -ENOMEM;
+	if (!leak_pages)
+		free_pages((unsigned long)vstart, order);
+	return rc;
 }
 
 void __init swiotlb_exit(void)
 {
 	struct io_tlb_pool *mem = &io_tlb_default_mem.defpool;
+	bool leak_pages = false;
 	unsigned long tbl_vaddr;
 	size_t tbl_size, slots_size;
 	unsigned int area_order;
@@ -552,19 +589,23 @@ void __init swiotlb_exit(void)
 	tbl_size = PAGE_ALIGN(mem->end - mem->start);
 	slots_size = PAGE_ALIGN(array_size(sizeof(*mem->slots), mem->nslabs));
 
-	if (io_tlb_default_mem.unencrypted)
-		set_memory_encrypted(tbl_vaddr, tbl_size >> PAGE_SHIFT);
+	if (io_tlb_default_mem.unencrypted) {
+		if (set_memory_encrypted(tbl_vaddr, tbl_size >> PAGE_SHIFT))
+			leak_pages = true;
+	}
 
 	if (mem->late_alloc) {
 		area_order = get_order(array_size(sizeof(*mem->areas),
 			mem->nareas));
 		free_pages((unsigned long)mem->areas, area_order);
-		free_pages(tbl_vaddr, get_order(tbl_size));
+		if (!leak_pages)
+			free_pages(tbl_vaddr, get_order(tbl_size));
 		free_pages((unsigned long)mem->slots, get_order(slots_size));
 	} else {
 		memblock_free(mem->areas,
 			array_size(sizeof(*mem->areas), mem->nareas));
-		memblock_phys_free(mem->start, tbl_size);
+		if (!leak_pages)
+			memblock_phys_free(mem->start, tbl_size);
 		memblock_free(mem->slots, slots_size);
 	}
 
@@ -1938,9 +1979,18 @@ static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
 		 * restricted mem pool is decrypted by default
 		 */
 		if (cc_platform_has(CC_ATTR_MEM_ENCRYPT)) {
+			int ret;
+
 			mem->unencrypted = true;
-			set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),
-					     rmem->size >> PAGE_SHIFT);
+			ret = set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),
+						   rmem->size >> PAGE_SHIFT);
+			if (ret) {
+				dev_err(dev, "Failed to decrypt restricted DMA pool\n");
+				kfree(pool->areas);
+				kfree(pool->slots);
+				kfree(mem);
+				return ret;
+			}
 		} else {
 			mem->unencrypted = false;
 		}

---

## [19] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 18/20] dma: free atomic pool pages by physical address*

dma_direct_alloc_pages() may satisfy atomic allocations from the coherent
atomic pools. The pool allocation is keyed by the virtual address stored in
the gen_pool, but the pages API returns only the backing struct page.

On architectures with CONFIG_DMA_DIRECT_REMAP, atomic pool chunks are added
to the gen_pool using their remapped virtual address.
dma_direct_free_pages() reconstructs a linear-map address with
page_address(page) and passes that to dma_free_from_pool(). That address
does not match the gen_pool virtual range, so the pool lookup can fail and
the code can fall through to freeing a pool-owned page through the normal
page allocator path.

Add a page-based pool free helper that looks up the owning pool chunk by
physical address, translates it back to the gen_pool virtual address, and
frees that address to the pool. Use it from dma_direct_free_pages() while
keeping the existing virtual-address helper for coherent allocation frees.

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 include/linux/dma-map-ops.h |  1 +
 kernel/dma/direct.c         |  4 +--
 kernel/dma/pool.c           | 54 +++++++++++++++++++++++++++++++++++++
 3 files changed, 57 insertions(+), 2 deletions(-)

diff --git a/include/linux/dma-map-ops.h b/include/linux/dma-map-ops.h
index 696b2c3a2305..8be059e69935 100644
--- a/include/linux/dma-map-ops.h
+++ b/include/linux/dma-map-ops.h
@@ -215,6 +215,7 @@ struct page *dma_alloc_from_pool(struct device *dev, size_t size,
 		void **cpu_addr, gfp_t flags, unsigned long attrs,
 		bool (*phys_addr_ok)(struct device *, phys_addr_t, size_t));
 bool dma_free_from_pool(struct device *dev, void *start, size_t size);
+bool dma_free_from_pool_page(struct device *dev, struct page *page, size_t size);
 
 int dma_direct_set_offset(struct device *dev, phys_addr_t cpu_start,
 		dma_addr_t dma_start, u64 size);
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index e0ab9ff3f1d6..58f7ea1be963 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -488,9 +488,9 @@ void dma_direct_free_pages(struct device *dev, size_t size,
 	 */
 	bool mark_mem_encrypted = force_dma_unencrypted(dev);
 
-	/* If cpu_addr is not from an atomic pool, dma_free_from_pool() fails */
+	/* If page is not from an atomic pool, dma_free_from_pool_page() fails */
 	if (IS_ENABLED(CONFIG_DMA_COHERENT_POOL) &&
-	    dma_free_from_pool(dev, vaddr, size))
+	    dma_free_from_pool_page(dev, page, size))
 		return;
 
 	phys = page_to_phys(page);
diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index e7df8d279e75..43b8101d860f 100644
--- a/kernel/dma/pool.c
+++ b/kernel/dma/pool.c
@@ -356,3 +356,57 @@ bool dma_free_from_pool(struct device *dev, void *start, size_t size)
 
 	return false;
 }
+
+struct dma_pool_phys_match {
+	phys_addr_t phys;
+	size_t size;
+	unsigned long addr;
+	bool found;
+};
+
+static void dma_pool_find_phys(struct gen_pool *pool, struct gen_pool_chunk *chunk,
+			       void *data)
+{
+	struct dma_pool_phys_match *match = data;
+	phys_addr_t end = match->phys + match->size - 1;
+	phys_addr_t chunk_end;
+
+	if (match->found)
+		return;
+
+	chunk_end = chunk->phys_addr + (chunk->end_addr - chunk->start_addr);
+	if (match->phys < chunk->phys_addr || end > chunk_end)
+		return;
+
+	match->addr = chunk->start_addr + (match->phys - chunk->phys_addr);
+	match->found = true;
+}
+
+static bool dma_free_from_pool_phys(struct dma_gen_pool *dma_pool, phys_addr_t phys,
+				    size_t size)
+{
+	struct dma_pool_phys_match match = {
+		.phys = phys,
+		.size = size,
+	};
+
+	gen_pool_for_each_chunk(dma_pool->pool, dma_pool_find_phys, &match);
+	if (!match.found)
+		return false;
+
+	gen_pool_free(dma_pool->pool, match.addr, size);
+	return true;
+}
+
+bool dma_free_from_pool_page(struct device *dev, struct page *page, size_t size)
+{
+	struct dma_gen_pool *dma_pool = NULL;
+	phys_addr_t phys = page_to_phys(page);
+
+	while ((dma_pool = dma_guess_pool(dma_pool, 0))) {
+		if (dma_free_from_pool_phys(dma_pool, phys, size))
+			return true;
+	}
+
+	return false;
+}

---

## [20] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 19/20] swiotlb: Preserve allocation virtual address for dynamic pools*

swiotlb_alloc_tlb() can allocate from the DMA atomic pool when a decrypted
pool is needed from atomic context. With CONFIG_DMA_DIRECT_REMAP, the
atomic pool is backed by remapped virtual addresses, which are not the same
as the direct-map addresses returned by phys_to_virt().

swiotlb_init_io_tlb_pool() currently reconstructs the pool virtual address
from the physical start address. For atomic-pool backed allocations this
stores the wrong address in pool->vaddr. Later, swiotlb_free_tlb() passes
that address to dma_free_from_pool(), which will fail to recognize the
chunk

Pass the virtual address returned by the allocation path into
swiotlb_init_io_tlb_pool(), and store that address in pool->vaddr. This
keeps the pool free path using the same virtual address as the allocator.

Tested-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Mostafa Saleh <smostafa@google.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/swiotlb.c | 32 +++++++++++++++++++-------------
 1 file changed, 19 insertions(+), 13 deletions(-)

diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index 14d834ca298b..e4bd8c9eaeda 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -302,9 +302,9 @@ void __init swiotlb_update_mem_attributes(void)
 }
 
 static void swiotlb_init_io_tlb_pool(struct io_tlb_pool *mem, phys_addr_t start,
-		unsigned long nslabs, bool late_alloc, unsigned int nareas)
+		void *vaddr, unsigned long nslabs, bool late_alloc,
+		unsigned int nareas)
 {
-	void *vaddr = phys_to_virt(start);
 	unsigned long bytes = nslabs << IO_TLB_SHIFT, i;
 
 	mem->nslabs = nslabs;
@@ -445,7 +445,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 		return;
 	}
 
-	swiotlb_init_io_tlb_pool(mem, __pa(tlb), nslabs, false, nareas);
+	swiotlb_init_io_tlb_pool(mem, __pa(tlb), tlb, nslabs, false, nareas);
 	add_mem_pool(&io_tlb_default_mem, mem);
 
 	if (flags & SWIOTLB_VERBOSE)
@@ -553,7 +553,7 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 		}
 	}
 
-	swiotlb_init_io_tlb_pool(mem, virt_to_phys(vstart), nslabs, true,
+	swiotlb_init_io_tlb_pool(mem, virt_to_phys(vstart), vstart, nslabs, true,
 				 nareas);
 	add_mem_pool(&io_tlb_default_mem, mem);
 
@@ -664,25 +664,26 @@ static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes,
  * @phys_limit:	Maximum allowed physical address of the buffer.
  * @attrs:	DMA attributes for the allocation.
  * @gfp:	GFP flags for the allocation.
+ * @vaddr:	Receives the virtual address for the allocated buffer.
  *
  * Return: Allocated pages, or %NULL on allocation failure.
  */
 static struct page *swiotlb_alloc_tlb(struct device *dev, size_t bytes,
-		u64 phys_limit, unsigned long attrs, gfp_t gfp)
+		u64 phys_limit, unsigned long attrs, gfp_t gfp, void **vaddr)
 {
 	struct page *page;
 
+	*vaddr = NULL;
+
 	/*
 	 * Allocate from the atomic pools if memory is encrypted and
 	 * the allocation is atomic, because decrypting may block.
 	 */
 	if (!gfpflags_allow_blocking(gfp) && (attrs & DMA_ATTR_CC_SHARED)) {
-		void *vaddr;
-
 		if (!IS_ENABLED(CONFIG_DMA_COHERENT_POOL))
 			return NULL;
 
-		return dma_alloc_from_pool(dev, bytes, &vaddr, gfp,
+		return dma_alloc_from_pool(dev, bytes, vaddr, gfp,
 					   attrs, dma_coherent_ok);
 	}
 
@@ -705,6 +706,8 @@ static struct page *swiotlb_alloc_tlb(struct device *dev, size_t bytes,
 			return NULL;
 	}
 
+	if (page)
+		*vaddr = phys_to_virt(page_to_phys(page));
 	return page;
 }
 
@@ -750,6 +753,7 @@ static struct io_tlb_pool *swiotlb_alloc_pool(struct device *dev,
 {
 	struct io_tlb_pool *pool;
 	unsigned int slot_order;
+	void *tlb_vaddr;
 	struct page *tlb;
 	size_t pool_size;
 	size_t tlb_size;
@@ -767,7 +771,8 @@ static struct io_tlb_pool *swiotlb_alloc_pool(struct device *dev,
 	pool->unencrypted = !!(attrs & DMA_ATTR_CC_SHARED);
 
 	tlb_size = nslabs << IO_TLB_SHIFT;
-	while (!(tlb = swiotlb_alloc_tlb(dev, tlb_size, phys_limit, attrs, gfp))) {
+	while (!(tlb = swiotlb_alloc_tlb(dev, tlb_size, phys_limit, attrs, gfp,
+					 &tlb_vaddr))) {
 		if (nslabs <= minslabs)
 			goto error_tlb;
 		nslabs = ALIGN(nslabs >> 1, IO_TLB_SEGSIZE);
@@ -781,12 +786,12 @@ static struct io_tlb_pool *swiotlb_alloc_pool(struct device *dev,
 	if (!pool->slots)
 		goto error_slots;
 
-	swiotlb_init_io_tlb_pool(pool, page_to_phys(tlb), nslabs, true, nareas);
+	swiotlb_init_io_tlb_pool(pool, page_to_phys(tlb), tlb_vaddr, nslabs,
+				 true, nareas);
 	return pool;
 
 error_slots:
-	swiotlb_free_tlb(page_address(tlb), tlb_size,
-			 !!(attrs & DMA_ATTR_CC_SHARED));
+	swiotlb_free_tlb(tlb_vaddr, tlb_size, !!(attrs & DMA_ATTR_CC_SHARED));
 error_tlb:
 	kfree(pool);
 error:
@@ -1995,7 +2000,8 @@ static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
 			mem->unencrypted = false;
 		}
 
-		swiotlb_init_io_tlb_pool(pool, rmem->base, nslabs,
+		swiotlb_init_io_tlb_pool(pool, rmem->base, phys_to_virt(rmem->base),
+					 nslabs,
 					 false, nareas);
 		mem->force_bounce = true;
 		mem->for_alloc = true;

---

## [21] Aneesh Kumar K.V (Arm) — 2026-06-04
*Subject: [PATCH v6 20/20] swiotlb: remove unused SWIOTLB_FORCE flag*

SWIOTLB_FORCE has no remaining in-tree users. Forced bouncing is now
controlled through the swiotlb=force command line option via
swiotlb_force_bounce.

Remove the unused flag and simplify the force_bounce initialization.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 include/linux/swiotlb.h | 1 -
 kernel/dma/swiotlb.c    | 3 +--
 2 files changed, 1 insertion(+), 3 deletions(-)

diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 526f82e9da45..af88ca7182f4 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -15,7 +15,6 @@ struct page;
 struct scatterlist;
 
 #define SWIOTLB_VERBOSE	(1 << 0) /* verbose initialization */
-#define SWIOTLB_FORCE	(1 << 1) /* force bounce buffering */
 #define SWIOTLB_ANY	(1 << 2) /* allow any memory for the buffer */
 
 /*
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index e4bd8c9eaeda..81cc4928e949 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -400,8 +400,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 	if (swiotlb_force_disable)
 		return;
 
-	io_tlb_default_mem.force_bounce =
-		swiotlb_force_bounce || (flags & SWIOTLB_FORCE);
+	io_tlb_default_mem.force_bounce = swiotlb_force_bounce;
 
 #ifdef CONFIG_SWIOTLB_DYNAMIC
 	if (!remap)

---

## [22] JAEHOON KIM — 2026-06-05
*Subject: Re: [PATCH v6 01/20] s390: Expose protected virtualization through
 cc_platform_has()*

On 6/4/2026 3:39 AM, Aneesh Kumar K.V (Arm) wrote:
> Protected virtualization guests use memory encryption, so advertise that to
> the rest of the kernel through cc_platform_has(CC_ATTR_MEM_ENCRYPT).

Tested-by: Jaehoon Kim <jhkim@linux.ibm.com>

Tested on s390 PV guest with swiotlb_dynamic configuration. SWIOTLB
bounce buffer allocation and dynamic pool management work correctly.
Also concurrent I/O stress completed successfully.

Thanks,
Jaehoon.

> ---
> Cc: Halil Pasic <pasic@linux.ibm.com>

---

## [23] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 02/20] dma-direct: swiotlb: handle swiotlb alloc/free
 outside __dma_direct_alloc_pages*

On Thu,  4 Jun 2026 14:09:41 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Move swiotlb allocation out of __dma_direct_alloc_pages() and handle it in
> dma_direct_alloc() / dma_direct_alloc_pages().

What's the reason to pass the buffer size if it's not used?

Other than that, this patch looks good to me.

Petr T

> +{
> +	swiotlb_release_slots(dev, tlb_addr, pool);

---

## [24] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 03/20] dma-direct: use DMA_ATTR_CC_SHARED in
 alloc/free paths*

On Thu,  4 Jun 2026 14:09:42 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Propagate force_dma_unencrypted() into DMA_ATTR_CC_SHARED in the
> dma-direct allocation path and use the attribute to drive the related

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  kernel/dma/direct.c | 53 +++++++++++++++++++++++++++++++++++++--------

---

## [25] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 05/20] dma: swiotlb: pass mapping attributes by
 reference*

On Thu,  4 Jun 2026 14:09:44 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Change swiotlb_tbl_map_single() to take the DMA mapping attributes by
> reference and update the direct callers accordingly.

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Thanks
Petr T

> ---
>  drivers/iommu/dma-iommu.c | 2 +-

---

## [26] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Thu,  4 Jun 2026 14:09:43 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Teach the atomic DMA pool code to distinguish between encrypted and
> unencrypted pools, and make pool allocation select the matching pool based

FWIW this also looks good to me, but I don't think I'm the best person
to review changed to DMA generic pools.

Petr T

> ---
>  drivers/iommu/dma-iommu.c   |   2 +-

---

## [27] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 06/20] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu,  4 Jun 2026 14:09:45 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Teach swiotlb to distinguish between encrypted and decrypted bounce
> buffer pools, and make allocation and mapping paths select a pool whose

IIUC this is a copy of the unencrypted member in the corresponding
struct io_tlb_mem. In other words, if pools are allocated dynamically,
all pools must have the same encryption state, correct?

>  #endif
>  };

If my assumption above is correct, then I prefer to add a struct
io_tlb_mem *mem parameter here and calculate the allocation attributes
inside this function, so you don't have to repeat it in the callers.

>  {
>  	struct page *page;

You're removing the check that dev is non-NULL. This is fine, because
the only call with dev == NULL is from swiotlb_dyn_alloc(), and that one
uses GFP_KERNEL (i.e. allows blocking). However, if this is an intended
optimization, I'd rather have it in a separate commit, with this
explanation why it's OK to do it.

The rest of the patch looks good to me.

Petr T

>  		void *vaddr;
>

---

## [28] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 08/20] dma-direct: pass attrs to dma_capable() for
 DMA_ATTR_CC_SHARED checks*

On Thu,  4 Jun 2026 14:09:47 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Teach dma_capable() about DMA_ATTR_CC_SHARED so the capability
> check can reject encrypted DMA addresses for devices that require

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  arch/x86/kernel/amd_gart_64.c | 30 ++++++++++++++++--------------

---

## [29] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 13/20] dma-direct: rename ret to cpu_addr in alloc
 helpers*

On Thu,  4 Jun 2026 14:09:52 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> ret in dma_direct_alloc() and dma_direct_alloc_pages() holds the returned
> CPU mapping, not a generic return value. Rename it to cpu_addr and update

I wondered if cpu_addr is descriptive enough (a CPU address could
theoretically be virtual or physical), but I can see that a few other
places already use cpu_addr to hold virtual addresses, so yeah, let's
keep this name.

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  kernel/dma/direct.c | 31 +++++++++++++++----------------

---

## [30] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 14/20] dma-direct: return struct page from
 dma_direct_alloc_from_pool()*

On Thu,  4 Jun 2026 14:09:53 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Commit 5b138c534fda ("dma-direct: factor out a dma_direct_alloc_from_pool
> helper") changed dma_direct_alloc_from_pool() to return the CPU address

While I totally agree with the reasoning and the fix, it's interesting
that this bug has been apparently present in the kernel for 5+ years
without anybody hitting nasty memory corruption bugs.

How can it be? Is the buggy code path never actually used in practice?
Does it hint at a missed opportunity to simplify the code?

Anyway, these these thoughts are intended for a possible future
cleanup. For now, let's apply the fix as is, of course.

Petr T

> Tested-by: Michael Kelley <mhklinux@outlook.com>
> Tested-by: Mostafa Saleh <smostafa@google.com>

---

## [31] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 15/20] iommu/dma: Check atomic pool allocation result
 directly*

On Thu,  4 Jun 2026 14:09:54 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> The non-blocking, non-coherent allocation path uses dma_alloc_from_pool(),
> which returns the allocated page and fills cpu_addr only on success.

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  drivers/iommu/dma-iommu.c | 11 +++++++----

---

## [32] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 16/20] dma: swiotlb: free dynamic pools from process
 context*

On Thu,  4 Jun 2026 14:09:55 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> swiotlb_dyn_free() is used after removing a dynamic swiotlb pool from
> RCU-protected lists. It can call swiotlb_free_tlb(), which may need to

Good catch!

> Use queue_rcu_work() for dynamic pool freeing instead. This keeps the RCU
> grace period before freeing a published pool, while running the actual pool

Strictly speaking, it's not necessary, because this is in the error
path just after allocating a transient pool. There are only two
possible scenarios:

a. The transient buffer was allocated from a sleeping context, and then
   it's also OK to decrypt memory.

b. The transient buffer was allocated in atomic context, but then it was
   allocated from a coherent pool and it is returned to that pool
   rather than decrypted.

However, it's also fine to queue an RCU work. The logic is definitely
cleaner and easier to maintain.

> Tested-by: Michael Kelley <mhklinux@outlook.com>
> Tested-by: Mostafa Saleh <smostafa@google.com>

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  include/linux/swiotlb.h |  4 ++--

---

## [33] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 17/20] dma: swiotlb: handle set_memory_decrypted()
 failures*

On Thu,  4 Jun 2026 14:09:56 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Check the return value when converting swiotlb pools between encrypted and
> decrypted mappings. If the default pool cannot be decrypted after early

This works fine, but instead of effectively leaking the memory, we
could return it to the buddy allocator and reset nslabs to zero as if
SWIOTLB was not even initialized.

OTOH I don't want to overthink this, because the system is probably not
too useful after such a boot-time failure, so unless you _want_ to
improve the error path, you can simply add:

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> Tested-by: Michael Kelley <mhklinux@outlook.com>
> Tested-by: Mostafa Saleh <smostafa@google.com>

---

## [34] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 19/20] swiotlb: Preserve allocation virtual address
 for dynamic pools*

On Thu,  4 Jun 2026 14:09:58 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> swiotlb_alloc_tlb() can allocate from the DMA atomic pool when a decrypted
> pool is needed from atomic context. With CONFIG_DMA_DIRECT_REMAP, the

Hm, so the old code was broken; you may want to add:

Fixes: 79636caad361 ("swiotlb: if swiotlb is full, fall back to a transient memory pool")

And of course:

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Thank you!
Petr T

> ---
>  kernel/dma/swiotlb.c | 32 +++++++++++++++++++-------------

---

## [35] Catalin Marinas — 2026-06-09
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On Thu, Jun 04, 2026 at 02:09:39PM +0530, Aneesh Kumar K.V (Arm) wrote:
> This series propagates DMA_ATTR_CC_SHARED through the dma-direct,
> dma-pool, and swiotlb paths so that encrypted and decrypted DMA buffers

Please check Sashiko's reports, it has some good points:

https://sashiko.dev/#/patchset/20260604083959.1265923-1-aneesh.kumar@kernel.org

I think the main one is the swiotlb_tbl_map_single() changes which break
AMD SME host support. There cc_platform_has(CC_ATTR_MEM_ENCRYPT) is true
but force_dma_unencrypted() is false. Normally you'd not end up on this
path but you can have swiotlb=force.

> Aneesh Kumar K.V (Arm) (20):
>   s390: Expose protected virtualization through cc_platform_has()

Patch 10 above...

>   dma-direct: select DMA address encoding from DMA_ATTR_CC_SHARED
>   dma-pool: fix page leak in atomic_pool_expand() cleanup

Patch 12...

>   dma-direct: rename ret to cpu_addr in alloc helpers
>   dma-direct: return struct page from dma_direct_alloc_from_pool()

and I think patches 14, 15 are independent fixes. Some of them even have
Fixes: tags and Cc: stable. Please move them to the beginning of the
series to avoid inadvertent dependencies and make them harder to
backport. It's also easier to follow the series without random fixes for
mainline in the middle.

>   dma: swiotlb: free dynamic pools from process context
>   dma: swiotlb: handle set_memory_decrypted() failures

---

## [36] Catalin Marinas — 2026-06-09
*Subject: Re: [PATCH v6 01/20] s390: Expose protected virtualization through
 cc_platform_has()*

On Thu, Jun 04, 2026 at 02:09:40PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Protected virtualization guests use memory encryption, so advertise that to
> the rest of the kernel through cc_platform_has(CC_ATTR_MEM_ENCRYPT).

Nit: just drop the --- line if you did intend to cc those people.
Nothing wrong for them to end up in the commit log (proof that they've
been cc'ed if they did not reply ;)).

---

## [37] Petr Tesarik — 2026-06-09
*Subject: Re: [PATCH v6 20/20] swiotlb: remove unused SWIOTLB_FORCE flag*

On Thu,  4 Jun 2026 14:09:59 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> SWIOTLB_FORCE has no remaining in-tree users. Forced bouncing is now
> controlled through the swiotlb=force command line option via

These constants are kernel-internal, so let's not leave a hole in the
bitmask... I mean, what about changing SWIOTLB_ANY to (1 << 1) after
you remove SWIOTLB_FORCE?

Other than that, LGTM.

I consider this whole series a big step towards saner handling of
encrypted/decrypted memory for DMA buffers. Thank you for your effort!

Petr T

>  
>  /*

---

## [38] Catalin Marinas — 2026-06-09
*Subject: Re: [PATCH v6 14/20] dma-direct: return struct page from
 dma_direct_alloc_from_pool()*

On Thu, Jun 04, 2026 at 02:09:53PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Commit 5b138c534fda ("dma-direct: factor out a dma_direct_alloc_from_pool
> helper") changed dma_direct_alloc_from_pool() to return the CPU address

Nit: remove the empty line after Cc: stable. It may confuse tooling.

---

## [39] Jason Gunthorpe — 2026-06-09
*Subject: Re: [PATCH v6 14/20] dma-direct: return struct page from
 dma_direct_alloc_from_pool()*

On Thu, Jun 04, 2026 at 02:09:53PM +0530, Aneesh Kumar K.V (Arm) wrote:
> @@ -270,9 +270,12 @@ void *dma_direct_alloc(struct device *dev, size_t size,
>  	 * the atomic pools instead if we aren't allowed block.

You should probably put this at the start of the series so it can be
backported

Reviewed-by: Jason Gunthorpe <jgg@nvidia.com>

To Petr's question I think this just shows nobody is really stressing
the PCI dma paths on CC VMs today.

	if (force_dma_unencrypted(dev) && dma_direct_use_pool(dev, gfp))
		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);

For instance the places even calling dma_alloc_pages() don't look like
things people would use in a CC VM.

Jason

---

## [40] Jason Gunthorpe — 2026-06-09
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Thu, Jun 04, 2026 at 02:09:43PM +0530, Aneesh Kumar K.V (Arm) wrote:
>  struct page *dma_alloc_from_pool(struct device *dev, size_t size,
> -		void **cpu_addr, gfp_t gfp,

I don't think you should be overloading DMA_ATTR_CC_SHARED like this.

	/*
	 * DMA_ATTR_CC_SHARED is not a caller-visible dma_alloc_*()
	 * attribute. The direct allocator uses it internally after it has
	 * decided that the backing pages must be shared/decrypted, so the
	 * rest of the allocation path can consistently select DMA addresses,
	 * choose compatible pools and restore encryption on free.
	 */
	if (attrs & DMA_ATTR_CC_SHARED)
		return NULL;

	if (force_dma_unencrypted(dev)) {
		attrs |= DMA_ATTR_CC_SHARED;
		mark_mem_decrypt = true;
	}

It is fine to have a bit inside the attrs that is only used by the
internal logic, but it needs to have a clearer name
__DMA_ATTR_REQUIRE_CC_SHARED perhaps.

The sashiko note does look legit though:

	if (IS_ENABLED(CONFIG_DMA_DIRECT_REMAP) &&
	    !gfpflags_allow_blocking(gfp) && !coherent) {
		page = dma_alloc_from_pool(dev, PAGE_ALIGN(size), &cpu_addr,
					   gfp, attrs, NULL);
		if (!page)
			return NULL;

I don't see anything doing the force_dma_unencrypted test along this
callchain..

I guess it should be done one step up in dma_alloc_attrs() instead of
in dma_direct_alloc()?

Jason

---

## [41] Jason Gunthorpe — 2026-06-09
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On Tue, Jun 09, 2026 at 02:43:08PM +0100, Catalin Marinas wrote:
> On Thu, Jun 04, 2026 at 02:09:39PM +0530, Aneesh Kumar K.V (Arm) wrote:
> > This series propagates DMA_ATTR_CC_SHARED through the dma-direct,

IMHO that's an AMD issue, not with the design of this series..

The series is right, a device that is !force_dma_decrypted() must be
considerd to be a trusted device and we must never place any DMA
mappings for a trusted device into shared memory.

That AMD has done somethine insane:

bool force_dma_unencrypted(struct device *dev)
{
	/*
	 * For SEV, all DMA must be to unencrypted addresses.
	 */
	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
		return true;

	/*
	 * For SME, all DMA must be to unencrypted addresses if the
	 * device does not support DMA to addresses that include the
	 * encryption mask.
	 */
	if (cc_platform_has(CC_ATTR_HOST_MEM_ENCRYPT)) {
		u64 dma_enc_mask = DMA_BIT_MASK(__ffs64(sme_me_mask));
		u64 dma_dev_mask = min_not_zero(dev->coherent_dma_mask,
						dev->bus_dma_limit);

		if (dma_dev_mask <= dma_enc_mask)
			return true;
	}

Is an AMD issue. We already have an address mask limit system built
into the DMA API, arch code should not be co-opting the CC mechanism
to create a special pool for address limited devices.

The correct thing is to ensure the DMA API is checking any address
limits on the actual true dma_addr_t, not on an intermediate like a
phys_addr before it is adjusted with any C bit. Then it is a normal
low address swiotlb bounce like any other.

I think we can ignore this Sashiko remark, in real systems the use of
swiotlb for 64 bit devices is very rare. Though it would be good to
remove this code from AMD...

Jason

---

## [42] Aneesh Kumar K.V — 2026-06-10
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Thu, Jun 04, 2026 at 02:09:43PM +0530, Aneesh Kumar K.V (Arm) wrote:
>>  struct page *dma_alloc_from_pool(struct device *dev, size_t size,

Are you suggesting adding another attribute in addition to
DMA_ATTR_CC_SHARED?

Is the idea that __DMA_ATTR_REQUIRE_CC_SHARED would be used in the
allocation path to request a CC_SHARED allocation, while
DMA_ATTR_CC_SHARED would be used in the mapping path to describe the
attribute of the address?



>
> The sashiko note does look legit though:

Yes, I'll move it there.

-aneesh

---

## [43] Aneesh Kumar K.V — 2026-06-10
*Subject: Re: [PATCH v6 06/20] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Petr Tesarik <ptesarik@suse.com> writes:

> On Thu,  4 Jun 2026 14:09:45 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

...

>>  /*
>>   * If memory encryption is supported, phys_to_dma will set the memory encryption

That is correct. The reason we have the unencrypted member in struct
io_tlb_pool is that we need it in swiotlb_dyn_free().

When freeing memory from an unencrypted pool, we need to convert the
memory back to private/encrypted

>
>>  #endif

....

>> @@ -604,30 +621,26 @@ static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes, u64 phys_limit)
>>   * @dev:	Device for which a memory pool is allocated.

Will switch to that. That is, we will use struct io_tlb_mem->unencrypted
to determine the pool attribute instead of using unsigned long attrs

>
>>  {

I'll add that back.

-aneesh

---

## [44] Jason Gunthorpe — 2026-06-10
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Wed, Jun 10, 2026 at 01:37:26PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

Yeah, it is a thought at least

Maybe a comment is good enough.

I just find it hard to follow when we have this dual usage. Like the
code above for dma_pool->unencrypted is completely wrong if it is an
"attribute of an address". Easy to cut & paste that into the wrong
context.

Especially if you move things up higher.. having the alloc set both
CC_SHARED and REQUIRE_CC_SHARED or maybe ALLOC_CC_SHARED would make it
clearer that the alloc code lives under that callchain

Jason

---

## [45] Aneesh Kumar K.V — 2026-06-11
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Wed, Jun 10, 2026 at 01:37:26PM +0530, Aneesh Kumar K.V wrote:
>> Jason Gunthorpe <jgg@ziepe.ca> writes:

If we are adding DMA_ATTR_ALLOC_SHARED, should we also allow
dma_alloc_attrs() to take that attribute value?

Does this look okay? 
(Note: Parts of the documentation text were updated using Codex.)

modified   Documentation/core-api/dma-attributes.rst
@@ -179,3 +179,32 @@ interface when building their uAPIs, when possible.
 
 It must never be used in an in-kernel driver that only works with
 kernel memory.
+
+DMA_ATTR_CC_SHARED
+------------------
+
+This attribute indicates that a DMA mapping is shared, or decrypted, for
+confidential computing guests. For normal system memory, the caller must
+already have marked the memory decrypted with set_memory_decrypted(). CPU
+PTEs for the mapping must use pgprot_decrypted(), and the same shared
+semantic may be passed to a vIOMMU when it sets up the IOPTE.
+
+This attribute describes an existing mapping. It does not allocate shared
+backing pages and must not be passed to dma_alloc_attrs(). For MMIO, use
+this together with DMA_ATTR_MMIO to indicate shared MMIO. Unless
+DMA_ATTR_MMIO is provided, the mapping requires a struct page.
+
+DMA_ATTR_ALLOC_CC_SHARED
+------------------------
+
+This attribute indicates that a dma_alloc_attrs() allocation must use
+shared, or decrypted, backing pages for confidential computing guests.
+Allocation paths use this request when they select shared DMA pools,
+decrypt newly allocated pages or restore encryption on free.
+
+DMA_ATTR_ALLOC_CC_SHARED differs from DMA_ATTR_CC_SHARED in that it
+requests shared backing memory from the allocation path. DMA_ATTR_CC_SHARED
+describes an already-shared mapping and requires the caller to have
+prepared normal system memory before mapping it. Callers that need shared
+memory from dma_alloc_attrs() should request DMA_ATTR_ALLOC_CC_SHARED
+instead of DMA_ATTR_CC_SHARED.
modified   include/linux/dma-mapping.h
@@ -103,6 +103,13 @@
  */
 #define DMA_ATTR_CC_SHARED	(1UL << 13)
 
+/*
+ * DMA_ATTR_ALLOC_CC_SHARED: Allocates DMA memory as shared (decrypted) for
+ * confidential computing guests. Unlike DMA_ATTR_CC_SHARED, this attribute
+ * is used by dma_alloc_attrs() paths that create shared backing pages;
+ * DMA_ATTR_CC_SHARED describes an already-shared mapping.
+ */
+#define DMA_ATTR_ALLOC_CC_SHARED	(1UL << 14)
 /*
  * A dma_addr_t can hold any valid DMA or bus address for the platform.  It can
  * be given to a device to use as a DMA source or target.  It is specific to a

---

## [46] Aneesh Kumar K.V — 2026-06-11
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> The sashiko note does look legit though:
>

I think we should do something similar to what dma_map_phys() does here,
considering that we only support DMA direct with DMA_ATTR_CC_SHARED/DMA_ATTR_ALLOC_CC_SHARED.

@@ -637,6 +637,7 @@ void *dma_alloc_attrs(struct device *dev, size_t size, dma_addr_t *dma_handle,
 {
 	const struct dma_map_ops *ops = get_dma_ops(dev);
 	void *cpu_addr;
+	bool is_cc_shared;
 
 	WARN_ON_ONCE(!dev->coherent_dma_mask);
 
@@ -657,8 +658,17 @@ void *dma_alloc_attrs(struct device *dev, size_t size, dma_addr_t *dma_handle,
 	/* let the implementation decide on the zone to allocate from: */
 	flag &= ~(__GFP_DMA | __GFP_DMA32 | __GFP_HIGHMEM);
 
+	if (force_dma_unencrypted(dev))
+		attrs |= DMA_ATTR_ALLOC_CC_SHARED;
+
+	is_cc_shared = attrs & DMA_ATTR_CC_SHARED;
+
 	if (dma_alloc_direct(dev, ops) || arch_dma_alloc_direct(dev)) {
 		cpu_addr = dma_direct_alloc(dev, size, dma_handle, flag, attrs);
+	} else if (is_cc_shared) {
+		trace_dma_alloc(dev, NULL, 0, size, DMA_BIDIRECTIONAL, flag,
+				attrs);
+		return NULL;
 	} else if (use_dma_iommu(dev)) {
 		cpu_addr = iommu_dma_alloc(dev, size, dma_handle, flag, attrs);
 	} else if (ops->alloc) {

-aneesh

---

## [47] Aneesh Kumar K.V — 2026-06-11
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Catalin Marinas <catalin.marinas@arm.com> writes:

> On Thu, Jun 04, 2026 at 02:09:39PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> This series propagates DMA_ATTR_CC_SHARED through the dma-direct,

I would consider the above similar to a trusted device requiring swiotlb
bouncing. At some point, based on real-world use cases, we may need to
add protected io_tlb_mem pools. We have not done that yet because no
such use case has come so far.

-aneesh

---

## [48] Jason Gunthorpe — 2026-06-11
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Thu, Jun 11, 2026 at 10:21:50AM +0530, Aneesh Kumar K.V wrote:

> If we are adding DMA_ATTR_ALLOC_SHARED, should we also allow
> dma_alloc_attrs() to take that attribute value?

I don't think we should..

It is hard to see any reason to allocate shared memory through the DMA
API. The way the DMA API works only the device that it is allocated
for can access that memory, so it is effectively private to the
device. Thus what purpose is shared device private memory?

> +DMA_ATTR_CC_SHARED
> +------------------

Yes, though we need to fix a few ATTR_MMIO users to make this
statement true

> +DMA_ATTR_ALLOC_CC_SHARED
> +------------------------

The semantic is right, but I would make it a private attribute since
no driver should use it.

Jason

---

## [49] Jason Gunthorpe — 2026-06-11
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Thu, Jun 11, 2026 at 10:55:47AM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

Yeah, I think that's the right idea for now..

> +	if (force_dma_unencrypted(dev))
> +		attrs |= DMA_ATTR_ALLOC_CC_SHARED;

But it would be clearer to put the test in the iommu_ functions I
think, since they are the ones that have the issue. We will need to
fix it someday..

I think we can ignore the op-> functions, arches cannot support CC and
still use dma_map_ops..

Jason

---

## [50] Petr Tesarik — 2026-06-11
*Subject: Re: [PATCH v6 04/20] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Thu, 11 Jun 2026 08:37:40 -0300
Jason Gunthorpe <jgg@ziepe.ca> wrote:

> On Thu, Jun 11, 2026 at 10:55:47AM +0530, Aneesh Kumar K.V wrote:
> > Jason Gunthorpe <jgg@ziepe.ca> writes:

Hm, sounds reasonable. Should we probably enforce this at configure or
build time?

Petr T

---

## [51] Alexey Kardashevskiy — 2026-06-17
*Subject: Re: [PATCH v6 03/20] dma-direct: use DMA_ATTR_CC_SHARED in alloc/free
 paths*

On 4/6/26 18:39, Aneesh Kumar K.V (Arm) wrote:
> Propagate force_dma_unencrypted() into DMA_ATTR_CC_SHARED in the
> dma-direct allocation path and use the attribute to drive the related

Why this limit?

Context: I am looking for a memory pool for a few shared pages (to do some guest<->host communication), SWIOTLB seems like the right fit but swiotlb_alloc() is not exported and dma_direct_alloc(DMA_ATTR_CC_SHARED) is not allowed.  Thanks,


> +	 */
> +	if (attrs & DMA_ATTR_CC_SHARED)

---

## [52] Aneesh Kumar K.V — 2026-06-17
*Subject: Re: [PATCH v6 03/20] dma-direct: use DMA_ATTR_CC_SHARED in
 alloc/free paths*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 4/6/26 18:39, Aneesh Kumar K.V (Arm) wrote:
>> Propagate force_dma_unencrypted() into DMA_ATTR_CC_SHARED in the

swiotlb is not the right pool to use for that, right?
CCA had a similar requirement for ITS pages and ended up creating a genpool:
b08e2f42e86b ("irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor")

-aneesh

---

## [53] Jason Gunthorpe — 2026-06-17
*Subject: Re: [PATCH v6 03/20] dma-direct: use DMA_ATTR_CC_SHARED in
 alloc/free paths*

On Wed, Jun 17, 2026 at 10:50:39AM +1000, Alexey Kardashevskiy wrote:
> > @@ -193,16 +193,31 @@ void *dma_direct_alloc(struct device *dev, size_t size,
> >   		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)

Then setup your struct device so that the DMA API knows the
guest<->host channel requires unecrypted and it will work correctly.

I think this is a reasonable API to use for that, and I was just
advocating that hyperv should be using it too.

But it all relies on a properly setup struct device.

Jason

---

## [54] Alexey Kardashevskiy — 2026-06-18
*Subject: Re: [PATCH v6 03/20] dma-direct: use DMA_ATTR_CC_SHARED in alloc/free
 paths*

On 18/6/26 01:41, Jason Gunthorpe wrote:
> On Wed, Jun 17, 2026 at 10:50:39AM +1000, Alexey Kardashevskiy wrote:
>>> @@ -193,16 +193,31 @@ void *dma_direct_alloc(struct device *dev, size_t size,

Sounds good but how do I do that in practice? DMA_ATTR_CC_SHARED is not externally available so I'll have to trick the DMA layer into using SWIOTLB (which is still all shared, right?) as I specifically want to skip page conversions. Setting low DMA mask won't guarantee that the DMA layer won't allocate a page outside of SWIOTLB and convert it. Manually do

dev->dma_io_tlb_mem->force_bounce = true;
dev->dma_io_tlb_mem->for_allow = true;

?
Or follow the Aneesh'es genpool approach? Thanks,


> 
> Jason

---

## [55] Alexey Kardashevskiy — 2026-06-18
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On 10/6/26 00:47, Jason Gunthorpe wrote:
> On Tue, Jun 09, 2026 at 02:43:08PM +0100, Catalin Marinas wrote:
>> On Thu, Jun 04, 2026 at 02:09:39PM +0530, Aneesh Kumar K.V (Arm) wrote:


swiotlb=force forces swiotlb, not decryption.

> That AMD has done somethine insane:
> 


So when I try "mem_encrypt=on iommu=pt swiotlb=force" with this patchset, it fails to boot. But it boots with a hack like this:

===
@@ -39,7 +41,7 @@ bool force_dma_unencrypted(struct device *dev)
                         return true;
         }
  
-       return false;
+       return swiotlb_force_bounce;
  }
===

Or we say "mem_encrypt=on iommu=pt swiotlb=force" combo is just weird and we won't be supporting which bit in this? Thanks,


> 
> Is an AMD issue. We already have an address mask limit system built

---

## [56] Aneesh Kumar K.V — 2026-06-18
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 10/6/26 00:47, Jason Gunthorpe wrote:
>> On Tue, Jun 09, 2026 at 02:43:08PM +0100, Catalin Marinas wrote:

Something like?

modified   arch/x86/mm/mem_encrypt.c
@@ -34,6 +34,13 @@ bool force_dma_unencrypted(struct device *dev)
 		u64 dma_enc_mask = DMA_BIT_MASK(__ffs64(sme_me_mask));
 		u64 dma_dev_mask = min_not_zero(dev->coherent_dma_mask,
 						dev->bus_dma_limit);
+		/*
+		 * With memory encryption enabled, SWIOTLB is marked decrypted.
+		 * If SWIOTLB bouncing is forced, treat the device as requiring
+		 * decrypted DMA.
+		 */
+		if (is_swiotlb_force_bounce(dev))
+			return true;
 
 		if (dma_dev_mask <= dma_enc_mask)
 			return true;



-aneesh

---

## [57] Jason Gunthorpe — 2026-06-18
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On Thu, Jun 18, 2026 at 09:37:22AM +0100, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

If force_dma_decrypted() == true then swiotlb must allocate from a
decrypted memory pool. It is right there in the name!

The hypervisor environment should *never* set force_dma_decrypted()
because all devices can access all hypervisor memory, up to their IOVA
limits.

> > So when I try "mem_encrypt=on iommu=pt swiotlb=force" with this
> > patchset, it fails to boot. But it boots with a hack like this:

On the host side I expect this to cause swiotlb to allocate encrypted
memory and bounce to it.

>  		u64 dma_enc_mask = DMA_BIT_MASK(__ffs64(sme_me_mask));
>  		u64 dma_dev_mask = min_not_zero(dev->coherent_dma_mask,

And this is more insane logic. The right fix is to allocate the
swiotlb bounce from the *encrypted* pools when running on the
hypervisor which requires undoing this abuse of force_dma_decrypted().

Jason

---

## [58] Alexey Kardashevskiy — 2026-06-19
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On 19/6/26 01:37, Jason Gunthorpe wrote:
> On Thu, Jun 18, 2026 at 09:37:22AM +0100, Aneesh Kumar K.V wrote:
>> Alexey Kardashevskiy <aik@amd.com> writes:

True. But we do not have encrypted swiotlb pool today, right?

> 
>>> So when I try "mem_encrypt=on iommu=pt swiotlb=force" with this

+1.

But how does the kernel decide if it is this swiotlb pool or just some page which happens to be below the IOVA limit?

swiotlb can be for bouncing (with all these dma_sync_single_for_cpu) or, if dev->dma_io_tlb_mem->for_alloc = true, for coherent allocation (no need in dma_sync_single_for_cpu).

I am looking for a way to set up my "sev-guest" device such as when dma_alloc_attrs(snp_dev->dev,...) happens, it allocates a page from the shared swiotlb pool (with no actual bouncing) and there is no obvious way to trick the DMA layer into doing that.


> 
> Jason

---

## [59] Jason Gunthorpe — 2026-06-19
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On Fri, Jun 19, 2026 at 12:05:45PM +1000, Alexey Kardashevskiy wrote:

> > > > > IMHO that's an AMD issue, not with the design of this series..
> > > > > 

"encrypted" is just normal struct page memory, that's the default for
swiotlb.

I think it was a big mistake for the AMD SME stuff to overload the
decrypted/encrypted CC stuff which should mean shared/private in a
guest context to also mean things about physical memory encryption in
the host. It is really confusing.

The SME side is just a bad arch choice, the real world doesn't work
well if you set high address bits in your dma_addr_t. I think AMD
needs to use those restricted swiotlb pool where it allocates this
very special "SME Disabled" memory that will have a low
dma_addr_t. Then alloc and bouncing will get memory with a suitable
dma_addr_t. This has nothing to do with force_dma_unencrypted() which
is only a CC guest concept and nothing else in the OS should ever
touch decrypted memory.

> > And this is more insane logic. The right fix is to allocate the
> > swiotlb bounce from the *encrypted* pools when running on the

You mean in swiotlb_tbl_unmap_single() ? It checks the address against
the pool's range?

> swiotlb can be for bouncing (with all these dma_sync_single_for_cpu)
> or, if dev->dma_io_tlb_mem->for_alloc = true, for coherent

Whats a "sev-guest" device?

> dma_alloc_attrs(snp_dev->dev,...) happens, it allocates a page from
> the shared swiotlb pool (with no actual bouncing) and there is no

Why do you need this?

Jason

---

## [60] Aneesh Kumar K.V — 2026-06-19
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Thu, Jun 18, 2026 at 09:37:22AM +0100, Aneesh Kumar K.V wrote:
>> Alexey Kardashevskiy <aik@amd.com> writes:

Agreed. If the device can do encrypted DMA and requires bouncing, it
should bounce through encrypted pools. We don't support encrypted pools
now and that means, we mark the option ("mem_encrypt=on iommu=pt
swiotlb=force") not supported for now? 

-aneesh

---

## [61] Jason Gunthorpe — 2026-06-19
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On Fri, Jun 19, 2026 at 01:14:13PM +0100, Aneesh Kumar K.V wrote:
> > And this is more insane logic. The right fix is to allocate the
> > swiotlb bounce from the *encrypted* pools when running on the

?? if you don't have a CC system then the swiotlb is "encrypted"
meaning ordinary struct page system memory.

The hypervisor should not be triggering any CC special stuff here, it
is not a CC guest.

Agree we don't need to worry about swiotlb=force with a trusted device
in the GUEST for now, but it should be something to fix eventually.

Jason

---

## [62] Aneesh Kumar K.V — 2026-06-19
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Fri, Jun 19, 2026 at 01:14:13PM +0100, Aneesh Kumar K.V wrote:
>> > And this is more insane logic. The right fix is to allocate the

If i understand this correctly, the setup Alexey is referring to here is
bare metal system with memory encryption enabled and dma address doesn't
need C bit cleared because it is handled in iommu. ( I consider this as
memory encryption that is handled transparently, device can access any
address because that encryption details are now managed by iommu).

Thinking about this more, I guess we should mark the swiotlb as
cc_shared only with  CC_ATTR_GUEST_MEM_ENCRYPT instead of
CC_ATTR_MEM_ENCRYPT as we have below.


	/*
	 * if platform support memory encryption, swiotlb buffers are
	 * shared by default.
	 */
	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
		io_tlb_default_mem.cc_shared = true;
	else
		io_tlb_default_mem.cc_shared = false;

....
	if (io_tlb_default_mem.cc_shared)
		set_memory_decrypted((unsigned long)mem->vaddr, bytes >> PAGE_SHIFT);

So we consider swiotlb as encrypted pool in such config.

Now we have the case of host memory encryption where the C-bit needs to
be cleared in dma_addr_t. That requires special handling in the kernel, and
I believe we need to mark swiotlb as unencrypted in this configuration.

I am still not clear whether there is a config option or runtime check
we can use to identify this case.

-aneesh

---

## [63] Aneesh Kumar K.V — 2026-06-19
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Fri, Jun 19, 2026 at 12:05:45PM +1000, Alexey Kardashevskiy wrote:
>

Agreed. This would make the code much simpler.

-aneesh

---

## [64] Jason Gunthorpe — 2026-06-19
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On Fri, Jun 19, 2026 at 02:36:19PM +0100, Aneesh Kumar K.V wrote:
> >> Agreed. If the device can do encrypted DMA and requires bouncing, it
> >> should bounce through encrypted pools. We don't support encrypted pools

This is how I understand it too, if the iommu is turned on then it can
take the high PA with the C bit set and map it to an IOVA that matches
the device's dma limit.

> ( I consider this as memory encryption that is handled
> transparently, device can access any address because that encryption

Compared to the guest side there are some important host side differences:

 - On the host the iommu can fix it because this is only a matter of
   IOVA range not access control. On a guest even a IOMMU cannot
   permit access to private memory
 - On the host the state of the device is driven by the dma limit
   which is not set until after the driver probes. On guest the state is
   set by the tsm and device security level before the driver
   probes
 - Both flows end up using pgprot_decrypted and set_memory_decrypted()
   to create their special pools, but for completely different
   reasons.
 - The memory coming from the special swiotlb pool must NOT be used by
   a trusted device on a CC guest, while there is no problem for any
   device to use it on the host.

> Thinking about this more, I guess we should mark the swiotlb as
> cc_shared only with  CC_ATTR_GUEST_MEM_ENCRYPT instead of

The name cc_shared should be used for GUEST scenarios only.

I guess there is some merit in keeping swiotlb using "decrypted" to
mean it usinig pgprot_decrypted and set_memory_decyped() which AMD
gives meaning to on both host and guest.

IDK what AMD should do on the host by default. I guess it should setup
a swiotlb pool of low dma addrs "unencrypted", but not "cc_shared"?

But if we are operating on the host then this pool is not limited to
only T=0 devices, every device can "safely" use it. (ignoring this
destroys the security memory encryption on bare metal was supposed to
provide)

> Now we have the case of host memory encryption where the C-bit needs to
> be cleared in dma_addr_t. That requires special handling in the kernel, and

I think we need to split the two things up, they have different
behaviors and need different flags and labels to make it all work
right.

> I am still not clear whether there is a config option or runtime check
> we can use to identify this case.

The dma api has to detect, after the driver sets the dma limit, that
none of system memory is usable when:
 - The direct path is being used
 - phys to dma for 0 is outside the dma limit

Then it should assume the arch has setup a swiotlb pool for it to use
to fix the high memory problem.

Similar hackery would be needed in the dma alloc path to know that
decrypted can be used to fix the high memory problem like for GUEST.

I guess some 'dev_cannot_reach_memory(dev)' sort of test in a
few key places? Setup with a static branch to be a nop on everything
but AMD, compiled out on every other arch.

Jason

---

## [65] Alexey Kardashevskiy — 2026-06-22
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

On 19/6/26 22:03, Jason Gunthorpe wrote:
> On Fri, Jun 19, 2026 at 12:05:45PM +1000, Alexey Kardashevskiy wrote:
> 
It is a bit in the PTE which says "encrypted", what do you mean by overloaded?...

> The SME side is just a bad arch choice, the real world doesn't work
> well if you set high address bits in your dma_addr_t. I think AMD

The generic __init iommu_subsys_init(void) calls iommu_set_default_translated() if CC_ATTR_MEM_ENCRYPT (==force the use of IOMMU) and eliminates the bouncing by default, pretty much. We (AMD) do not really want to force Cbit in DMA handles and it is not happening unless "iommu=pt".

> Then alloc and bouncing will get memory with a suitable
> dma_addr_t. This has nothing to do with force_dma_unencrypted() which

True.

Although, with "iommu=pt" enabled, dma handles from swiotlb should not have Cbit so these swiotlb pages  have to be unencrypted.

As you mentioned in another mail in the thread, DMAing to unencrypted memory with mem_encrypt=on make no sense security wise. May be enforce either mem_encrypt=on or iommu=pt is allowed at the same time but not both? I am worried though that some weirdo still has a use case for it.


>>> And this is more insane logic. The right fix is to allocate the
>>> swiotlb bounce from the *encrypted* pools when running on the

It is a platform device, presented in SNP VMs as /dev/sev-guest and the guest userspace calls ioctls on it when it needs VM attestation report/certificates/etc.

The sev-guest driver makes calls to the HV (GHCB protocol) to:
1) get report/certificates/measurements from the HV <- this is done via shared memory as the HV writes to it;
2) asks the HV to get the digests from the PSP <- this is done via encrypted memory (buuuut it is software encrypted and as far as the hw is concerned - it is shared - no Cbit, no RMP - these buffers contain plaintext headers of the PSP requests and cyphertext of the request/response body).

>> dma_alloc_attrs(snp_dev->dev,...) happens, it allocates a page from
>> the shared swiotlb pool (with no actual bouncing) and there is no

/dev/sev-guest uses only shared memory (from the HW standpoint), and it is normally lot less than 1MB. If hugepages are used, then today it allocates 4K pages (they come encrypted and likely backed with a 2M page), the driver converts them to shared to make that GHCB call. The conversion smashes backing 2M page to 4K pages (+RMP +IOPDE as there is possible ongoing DMA), which is a problem (I have mentioned it as "TMPM" before - a hw/fw helper to do the smashing).

The idea here is that if swiotlb is already shared, the sev-guest could use that memory pool.

Thanks,


> 
> Jason

---

## [66] Aneesh Kumar K.V — 2026-06-29
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Fri, Jun 19, 2026 at 02:36:19PM +0100, Aneesh Kumar K.V wrote:
>> >> Agreed. If the device can do encrypted DMA and requires bouncing, it

Agreed.

>> Thinking about this more, I guess we should mark the swiotlb as
>> cc_shared only with  CC_ATTR_GUEST_MEM_ENCRYPT instead of

Are you suggesting to change the struct io_tlb_mem::cc_shared back to
struct io_tlb_mem::unencrypted?. If we want to split cc_shared and
unencrypted as two flags, I think we will add quiet a lot of code
duplication.

> IDK what AMD should do on the host by default. I guess it should setup
> a swiotlb pool of low dma addrs "unencrypted", but not "cc_shared"?

If by low DMA address you mean using an address with the C-bit
cleared. Currently the SME code uses force_dma_unencrypted() as the hook to
determine whether the C-bit needs to be cleared. Therefore,
force_dma_unencrypted(dev) must be true to use such a pool.

The current code already does this and uses the swiotlb pool correctly
on SME. The challenge arises when we want to force SWIOTLB
bouncing even for devices that can handle encrypted DMA addresses (more
on that below). For such a config force_dma_uencrypted(dev) will return
false and swiotlb will be marked cc_shared/decrypted = true; This trip
the new check we added.

	/* swiotlb pool is incorrect for this device */
	if (unlikely(mem->cc_shared != force_dma_unencrypted(dev)))
		return (phys_addr_t)DMA_MAPPING_ERROR;

We can also do

	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT)) {
		/* swiotlb pool is incorrect for this device */
		if (unlikely(mem->cc_shared != force_dma_unencrypted(dev)))
			return (phys_addr_t)DMA_MAPPING_ERROR;

		/* Force attrs to match the kind of memory in the pool */
		if (mem->cc_shared)
			*attrs |= DMA_ATTR_CC_SHARED;
		else
			*attrs &= ~DMA_ATTR_CC_SHARED;
	} else {
		/*
		 * Host memory encryption where device requires an
		 * unencrypted dma_addr_t due to dma mask limit
    		 */
		if (force_dma_unencrypted(dev))
			*attrs |= DMA_ATTR_CC_SHARED;
		else
			*attrs &= ~DMA_ATTR_CC_SHARED;
	}


Here I see value in having DMA_ATTR_UNENCRYPTED. The question is do we
need to split this into two flags and introduce the resulting code
duplication.

>
> But if we are operating on the host then this pool is not limited to

If we are not able to reach the memory because of the memory encryption
bit, then isn't dev_cannot_reach_memory(dev) the same as
force_dma_unencrypted(dev)? If so, that is how it is already done.

I am wondering whether we can keep this simpler by ignoring the
swiotlb=force kernel parameter and keeping cc_shared as it is, even
though that can be confusing when looking at SME.

The three configurations we need to consider here are:

1) SEV-SNP guest
2) SME host with iommu=translated
3) SME host with iommu=passthrough

IIUC, all of the above work with the current code because we mark the
swiotlb as cc_shared/decrypted when CC_ATTR_MEM_ENCRYPT is set (i.e.,
this applies to an SME host as well).

The challenge arises when the user forces swiotlb bouncing with the
swiotlb=force command-line option. At that point, all devices, including
those whose DMA mask can handle encrypted DMA addresses, are forced to
use SWIOTLB. That becomes a problem because SWIOTLB is marked as
decrypted by default.

How about something like the following?

x86/dma: Disable forced SWIOTLB bouncing for SME IOMMU passthrough

With host memory encryption and IOMMU passthrough, DMA address handling
depends on whether a device can address the C-bit. Devices that cannot
address it need DMA addresses with the C-bit cleared, while devices that
can address encrypted memory should keep using encrypted DMA addresses.

The default swiotlb pool is marked shared when memory encryption is active.
Forcing all devices through that pool would also force devices capable of
encrypted DMA to use shared mappings. Clear the global swiotlb-force-bounce
state in this mode, and warn when this overrides an explicit swiotlb=force
command-line request.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

modified   arch/x86/kernel/pci-dma.c
@@ -51,8 +51,24 @@ static void __init pci_swiotlb_detect(void)
 	 * Set swiotlb to 1 so that bounce buffers are allocated and used for
 	 * devices that can't support DMA to encrypted memory.
 	 */
-	if (cc_platform_has(CC_ATTR_HOST_MEM_ENCRYPT))
+	if (cc_platform_has(CC_ATTR_HOST_MEM_ENCRYPT)) {
 		x86_swiotlb_enable = true;
+		/*
+		 * With host memory encryption and IOMMU passthrough, devices
+		 * that cannot address the C-bit need DMA addresses with the
+		 * C-bit cleared, while devices that can address encrypted
+		 * memory should keep using encrypted DMA addresses.
+		 *
+		 * The default SWIOTLB pool is marked shared when memory
+		 * encryption is active, so forcing all devices through it would
+		 * also force devices that support encrypted DMA to use shared
+		 * mappings. Disable global forced bouncing in this mode.
+		 */
+		if (iommu_default_passthrough() &&
+		    clear_swiotlb_force_bounce())
+			pr_warn("Ignoring swiotlb=force with host memory encryption and "
+				"IOMMU passthrough\n");
+	}
 
 	/*
 	 * Guest with guest memory encryption currently perform all DMA through
modified   include/linux/swiotlb.h
@@ -40,6 +40,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 	int (*remap)(void *tlb, unsigned long nslabs));
 extern void __init swiotlb_update_mem_attributes(void);
+bool __init clear_swiotlb_force_bounce(void);
 
 #ifdef CONFIG_SWIOTLB
 
modified   kernel/dma/swiotlb.c
@@ -208,6 +208,15 @@ unsigned long swiotlb_size_or_default(void)
 	return default_nslabs << IO_TLB_SHIFT;
 }
 
+bool __init clear_swiotlb_force_bounce(void)
+{
+	if (!swiotlb_force_bounce)
+		return false;
+
+	swiotlb_force_bounce = false;
+	return true;
+}
+
 void __init swiotlb_adjust_size(unsigned long size)
 {
 	/*

---

## [67] Aneesh Kumar K.V — 2026-06-29
*Subject: Re: [PATCH v6 00/20] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Alexey,

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> The current code already does this and uses the swiotlb pool correctly
> on SME. The challenge arises when we want to force SWIOTLB

Can you help to test this patch?

commit 0275ed870ff8dadb4890fe8342e84b294f657c43
Author: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Date:   Mon Jun 29 11:55:08 2026 +0530

    swiotlb: Return unencrypted DMA addresses for SME bounce buffers
    
    On hosts with memory encryption, the default swiotlb pool is marked shared
    and decrypted when memory encryption is active.
    
    Make host-memory-encryption swiotlb mappings consistently return
    unencrypted DMA addresses. This applies regardless of whether the device
    itself requires unencrypted DMA due to its DMA mask, because the bounce
    buffer memory backing the mapping is already unencrypted. It also preserves
    swiotlb=force for devices that can address encrypted memory: forced bounce
    mappings use the unencrypted swiotlb pool and receive unencrypted DMA
    addresses.
    
    Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index a62e1571ec95..9ba23cf8d97b 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -1514,15 +1514,26 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
 		pr_warn_once("Memory encryption is active and system is using DMA bounce buffers\n");
 
-	/* swiotlb pool is incorrect for this device */
-	if (unlikely(mem->cc_shared != force_dma_unencrypted(dev)))
-		return (phys_addr_t)DMA_MAPPING_ERROR;
+	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT)) {
+		/* swiotlb pool is incorrect for this device */
+		if (unlikely(mem->cc_shared != force_dma_unencrypted(dev)))
+			return (phys_addr_t)DMA_MAPPING_ERROR;
 
-	/* Force attrs to match the kind of memory in the pool */
-	if (mem->cc_shared)
+		/* Force attrs to match the kind of memory in the pool */
+		if (mem->cc_shared)
+			*attrs |= DMA_ATTR_CC_SHARED;
+		else
+			*attrs &= ~DMA_ATTR_CC_SHARED;
+	} else if (cc_platform_has(CC_ATTR_HOST_MEM_ENCRYPT)) {
+		/*
+		 * On hosts with memory encryption, SWIOTLB-backed memory
+		 * is unencrypted memory. DMA addresses returned for bounce
+		 * buffers must therefore have the C-bit cleared, even for
+		 * devices that can address encrypted memory. This also
+		 * preserves swiotlb=force for those devices.
+		 */
 		*attrs |= DMA_ATTR_CC_SHARED;
-	else
-		*attrs &= ~DMA_ATTR_CC_SHARED;
+	}
 
 	/*
 	 * The default swiotlb memory pool is allocated with PAGE_SIZE

---
