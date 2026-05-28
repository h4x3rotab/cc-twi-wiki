---
title: 'dma-mapping: Use DMA_ATTR_CC_SHARED through direct, pool and swiotlb paths'
date: 2026-05-12
last_reply: 2026-05-21
message_count: 67
participants: ['Aneesh Kumar K.V (Arm)', 'Mostafa Saleh', 'Jason Gunthorpe', 'Alexey Kardashevskiy', 'Jiri Pirko', 'Christian Borntraeger']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-05-12

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

Aneesh Kumar K.V (Arm) (13):
  dma-direct: swiotlb: handle swiotlb alloc/free outside
    __dma_direct_alloc_pages
  dma-direct: use DMA_ATTR_CC_SHARED in alloc/free paths
  dma-pool: track decrypted atomic pools and select them via attrs
  dma: swiotlb: track pool encryption state and honor DMA_ATTR_CC_SHARED
  dma-mapping: make dma_pgprot() honor DMA_ATTR_CC_SHARED
  dma-direct: pass attrs to dma_capable() for DMA_ATTR_CC_SHARED checks
  dma-direct: make dma_direct_map_phys() honor DMA_ATTR_CC_SHARED
  dma-direct: set decrypted flag for remapped DMA allocations
  dma-direct: select DMA address encoding from DMA_ATTR_CC_SHARED
  dma-pool: fix page leak in atomic_pool_expand() cleanup
  dma-direct: rename ret to cpu_addr in alloc helpers
  dma-direct: return struct page from dma_direct_alloc_from_pool()
  x86/amd-gart: preserve the direct DMA address until GART mapping
    succeeds

 arch/arm64/mm/init.c                 |   4 +-
 arch/powerpc/platforms/pseries/svm.c |   2 +-
 arch/s390/mm/init.c                  |   2 +-
 arch/x86/kernel/amd_gart_64.c        |  36 ++--
 arch/x86/kernel/pci-dma.c            |   4 +-
 drivers/iommu/dma-iommu.c            |   2 +-
 drivers/xen/swiotlb-xen.c            |  10 +-
 include/linux/dma-direct.h           |  19 ++-
 include/linux/dma-map-ops.h          |   2 +-
 include/linux/swiotlb.h              |   8 +-
 kernel/dma/direct.c                  | 243 ++++++++++++++++++++-------
 kernel/dma/direct.h                  |  40 ++---
 kernel/dma/mapping.c                 |  16 +-
 kernel/dma/pool.c                    | 165 +++++++++++-------
 kernel/dma/swiotlb.c                 | 109 +++++++++---
 15 files changed, 459 insertions(+), 203 deletions(-)


base-commit: 50897c955902c93ae71c38698abb910525ebdc89

---

## [2] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 01/13] dma-direct: swiotlb: handle swiotlb alloc/free outside __dma_direct_alloc_pages*

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

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 44 +++++++++++++++++++++++++++++++++++++-------
 1 file changed, 37 insertions(+), 7 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index ec887f443741..b958f150718a 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -125,9 +125,6 @@ static struct page *__dma_direct_alloc_pages(struct device *dev, size_t size,
 
 	WARN_ON_ONCE(!PAGE_ALIGNED(size));
 
-	if (is_swiotlb_for_alloc(dev))
-		return dma_direct_alloc_swiotlb(dev, size);
-
 	gfp |= dma_direct_optimal_gfp_mask(dev, &phys_limit);
 	page = dma_alloc_contiguous(dev, size, gfp);
 	if (page) {
@@ -204,6 +201,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)
 {
 	bool remap = false, set_uncached = false;
+	bool mark_mem_decrypt = true;
 	struct page *page;
 	void *ret;
 
@@ -250,11 +248,21 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
@@ -281,7 +289,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 			goto out_free_pages;
 	} else {
 		ret = page_address(page);
-		if (dma_set_decrypted(dev, ret, size))
+		if (mark_mem_decrypt && dma_set_decrypted(dev, ret, size))
 			goto out_leak_pages;
 	}
 
@@ -298,7 +306,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	return ret;
 
 out_encrypt_pages:
-	if (dma_set_encrypted(dev, page_address(page), size))
+	if (mark_mem_decrypt && dma_set_encrypted(dev, page_address(page), size))
 		return NULL;
 out_free_pages:
 	__dma_direct_free_pages(dev, page, size);
@@ -310,6 +318,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 void dma_direct_free(struct device *dev, size_t size,
 		void *cpu_addr, dma_addr_t dma_addr, unsigned long attrs)
 {
+	bool mark_mem_encrypted = true;
 	unsigned int page_order = get_order(size);
 
 	if ((attrs & DMA_ATTR_NO_KERNEL_MAPPING) &&
@@ -338,12 +347,15 @@ void dma_direct_free(struct device *dev, size_t size,
 	    dma_free_from_pool(dev, cpu_addr, PAGE_ALIGN(size)))
 		return;
 
+	if (swiotlb_find_pool(dev, dma_to_phys(dev, dma_addr)))
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
 
@@ -359,6 +371,19 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	if (force_dma_unencrypted(dev) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (is_swiotlb_for_alloc(dev)) {
+		page = dma_direct_alloc_swiotlb(dev, size);
+		if (!page)
+			return NULL;
+
+		if (PageHighMem(page)) {
+			swiotlb_free(dev, page, size);
+			return NULL;
+		}
+		ret = page_address(page);
+		goto setup_page;
+	}
+
 	page = __dma_direct_alloc_pages(dev, size, gfp, false);
 	if (!page)
 		return NULL;
@@ -366,6 +391,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	ret = page_address(page);
 	if (dma_set_decrypted(dev, ret, size))
 		goto out_leak_pages;
+setup_page:
 	memset(ret, 0, size);
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
 	return page;
@@ -378,13 +404,17 @@ void dma_direct_free_pages(struct device *dev, size_t size,
 		enum dma_data_direction dir)
 {
 	void *vaddr = page_address(page);
+	bool mark_mem_encrypted = true;
 
 	/* If cpu_addr is not from an atomic pool, dma_free_from_pool() fails */
 	if (IS_ENABLED(CONFIG_DMA_COHERENT_POOL) &&
 	    dma_free_from_pool(dev, vaddr, size))
 		return;
 
-	if (dma_set_encrypted(dev, vaddr, size))
+	if (swiotlb_find_pool(dev, page_to_phys(page)))
+		mark_mem_encrypted = false;
+
+	if (mark_mem_encrypted && dma_set_encrypted(dev, vaddr, size))
 		return;
 	__dma_direct_free_pages(dev, page, size);
 }

---

## [3] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 02/13] dma-direct: use DMA_ATTR_CC_SHARED in alloc/free paths*

Propagate force_dma_unencrypted() into DMA_ATTR_CC_SHARED in the
dma-direct allocation path and use the attribute to drive the related
decisions.

This updates dma_direct_alloc(), dma_direct_free(), and
dma_direct_alloc_pages() to fold the forced unencrypted case into attrs.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 44 ++++++++++++++++++++++++++++++++++++--------
 1 file changed, 36 insertions(+), 8 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index b958f150718a..0c2e1f8436ce 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -201,16 +201,31 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
@@ -244,7 +259,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	 * Remapping or decrypting memory may block, allocate the memory from
 	 * the atomic pools instead if we aren't allowed block.
 	 */
-	if ((remap || force_dma_unencrypted(dev)) &&
+	if ((remap || (attrs & DMA_ATTR_CC_SHARED)) &&
 	    dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
@@ -318,11 +333,20 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 void dma_direct_free(struct device *dev, size_t size,
 		void *cpu_addr, dma_addr_t dma_addr, unsigned long attrs)
 {
-	bool mark_mem_encrypted = true;
+	bool mark_mem_encrypted = false;
 	unsigned int page_order = get_order(size);
 
-	if ((attrs & DMA_ATTR_NO_KERNEL_MAPPING) &&
-	    !force_dma_unencrypted(dev) && !is_swiotlb_for_alloc(dev)) {
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
@@ -365,10 +389,14 @@ void dma_direct_free(struct device *dev, size_t size,
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

---

## [4] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 03/13] dma-pool: track decrypted atomic pools and select them via attrs*

Teach the atomic DMA pool code to distinguish between encrypted and
decrypted pools, and make pool allocation select the matching pool based
on DMA attributes.

Introduce a dma_gen_pool wrapper that records whether a pool is
decrypted, initialize that state when the atomic pools are created, and
use it when expanding and resizing the pools.  Update dma_alloc_from_pool()
to take attrs and skip pools whose encrypted/decrypted state does not
match DMA_ATTR_CC_SHARED.  Update dma_free_from_pool() accordingly.

Also pass DMA_ATTR_CC_SHARED from the swiotlb atomic allocation path
so decrypted swiotlb allocations are taken from the correct atomic pool.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/dma-iommu.c   |   2 +-
 include/linux/dma-map-ops.h |   2 +-
 kernel/dma/direct.c         |  11 ++-
 kernel/dma/pool.c           | 163 +++++++++++++++++++++++-------------
 kernel/dma/swiotlb.c        |   7 +-
 5 files changed, 122 insertions(+), 63 deletions(-)

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
index 0c2e1f8436ce..dc2907439b3d 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -162,7 +162,7 @@ static bool dma_direct_use_pool(struct device *dev, gfp_t gfp)
 }
 
 static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
-		dma_addr_t *dma_handle, gfp_t gfp)
+		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)
 {
 	struct page *page;
 	u64 phys_limit;
@@ -172,7 +172,8 @@ static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
 		return NULL;
 
 	gfp |= dma_direct_optimal_gfp_mask(dev, &phys_limit);
-	page = dma_alloc_from_pool(dev, size, &ret, gfp, dma_coherent_ok);
+	page = dma_alloc_from_pool(dev, size, &ret, gfp, attrs,
+				   dma_coherent_ok);
 	if (!page)
 		return NULL;
 	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
@@ -261,7 +262,8 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	 */
 	if ((remap || (attrs & DMA_ATTR_CC_SHARED)) &&
 	    dma_direct_use_pool(dev, gfp))
-		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
+		return dma_direct_alloc_from_pool(dev, size, dma_handle,
+						  gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
 		page = dma_direct_alloc_swiotlb(dev, size);
@@ -397,7 +399,8 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 		attrs |= DMA_ATTR_CC_SHARED;
 
 	if ((attrs & DMA_ATTR_CC_SHARED) && dma_direct_use_pool(dev, gfp))
-		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
+		return dma_direct_alloc_from_pool(dev, size, dma_handle,
+						  gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
 		page = dma_direct_alloc_swiotlb(dev, size);
diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index 2b2fbb709242..75f0eba48a23 100644
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
@@ -76,7 +82,7 @@ static bool cma_in_zone(gfp_t gfp)
 	return true;
 }
 
-static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
+static int atomic_pool_expand(struct dma_gen_pool *dma_pool, size_t pool_size,
 			      gfp_t gfp)
 {
 	unsigned int order;
@@ -113,12 +119,15 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 	 * Memory in the atomic DMA pools must be unencrypted, the pools do not
 	 * shrink so no re-encryption occurs in dma_direct_free().
 	 */
-	ret = set_memory_decrypted((unsigned long)page_to_virt(page),
+	if (dma_pool->unencrypted) {
+		ret = set_memory_decrypted((unsigned long)page_to_virt(page),
 				   1 << order);
-	if (ret)
-		goto remove_mapping;
-	ret = gen_pool_add_virt(pool, (unsigned long)addr, page_to_phys(page),
-				pool_size, NUMA_NO_NODE);
+		if (ret)
+			goto remove_mapping;
+	}
+
+	ret = gen_pool_add_virt(dma_pool->pool, (unsigned long)addr,
+				page_to_phys(page), pool_size, NUMA_NO_NODE);
 	if (ret)
 		goto encrypt_mapping;
 
@@ -126,11 +135,15 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 	return 0;
 
 encrypt_mapping:
-	ret = set_memory_encrypted((unsigned long)page_to_virt(page),
-				   1 << order);
-	if (WARN_ON_ONCE(ret)) {
-		/* Decrypt succeeded but encrypt failed, purposely leak */
-		goto out;
+	if (dma_pool->unencrypted) {
+		int rc;
+
+		rc = set_memory_encrypted((unsigned long)page_to_virt(page),
+					  1 << order);
+		if (WARN_ON_ONCE(rc)) {
+			/* Decrypt succeeded but encrypt failed, purposely leak */
+			goto out;
+		}
 	}
 remove_mapping:
 #ifdef CONFIG_DMA_DIRECT_REMAP
@@ -142,46 +155,52 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
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
@@ -207,21 +226,22 @@ static int __init dma_atomic_pool_init(void)
 
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
 
@@ -230,19 +250,44 @@ static int __init dma_atomic_pool_init(void)
 }
 postcore_initcall(dma_atomic_pool_init);
 
-static inline struct gen_pool *dma_guess_pool(struct gen_pool *prev, gfp_t gfp)
+static inline struct dma_gen_pool *__dma_guess_pool(struct dma_gen_pool *first,
+		struct dma_gen_pool *second, struct dma_gen_pool *third)
+{
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
 {
-	if (prev == NULL) {
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
 
@@ -272,16 +317,20 @@ static struct page *__dma_alloc_from_pool(struct device *dev, size_t size,
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
@@ -296,12 +345,14 @@ struct page *dma_alloc_from_pool(struct device *dev, size_t size,
 
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
index 1abd3e6146f4..ab4eccbaa076 100644
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

## [5] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and honor DMA_ATTR_CC_SHARED*

Teach swiotlb to distinguish between encrypted and decrypted bounce
buffer pools, and make allocation and mapping paths select a pool whose
state matches the requested DMA attributes.

Add a decrypted flag to io_tlb_mem, initialize it for the default and
restricted pools, and propagate DMA_ATTR_CC_SHARED into swiotlb pool
allocation. Reject swiotlb alloc/map requests when the selected pool does
not match the required encrypted/decrypted state.

Also return DMA addresses with the matching phys_to_dma_{encrypted,
unencrypted} helper so the DMA address encoding stays consistent with the
chosen pool.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 include/linux/dma-direct.h |  10 ++++
 include/linux/swiotlb.h    |   8 ++-
 kernel/dma/direct.c        |  14 +++--
 kernel/dma/swiotlb.c       | 108 +++++++++++++++++++++++++++----------
 4 files changed, 107 insertions(+), 33 deletions(-)

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
index 3dae0f592063..b3fa3c6e0169 100644
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
 
 static inline bool is_swiotlb_for_alloc(struct device *dev)
@@ -290,7 +293,8 @@ static inline bool is_swiotlb_for_alloc(struct device *dev)
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
index dc2907439b3d..97ae4fa10521 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -104,9 +104,10 @@ static void __dma_direct_free_pages(struct device *dev, struct page *page,
 	dma_free_contiguous(dev, page, size);
 }
 
-static struct page *dma_direct_alloc_swiotlb(struct device *dev, size_t size)
+static struct page *dma_direct_alloc_swiotlb(struct device *dev, size_t size,
+		unsigned long attrs)
 {
-	struct page *page = swiotlb_alloc(dev, size);
+	struct page *page = swiotlb_alloc(dev, size, attrs);
 
 	if (page && !dma_coherent_ok(dev, page_to_phys(page), size)) {
 		swiotlb_free(dev, page, size);
@@ -266,8 +267,12 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
@@ -374,6 +379,7 @@ void dma_direct_free(struct device *dev, size_t size,
 		return;
 
 	if (swiotlb_find_pool(dev, dma_to_phys(dev, dma_addr)))
+		/* Swiotlb doesn't need a page attribute update on free */
 		mark_mem_encrypted = false;
 
 	if (is_vmalloc_addr(cpu_addr)) {
@@ -403,7 +409,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 						  gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
-		page = dma_direct_alloc_swiotlb(dev, size);
+		page = dma_direct_alloc_swiotlb(dev, size, attrs);
 		if (!page)
 			return NULL;
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index ab4eccbaa076..065663be282c 100644
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
+		unsigned int nareas, u64 phys_limit, unsigned long attrs,
+		gfp_t gfp)
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
 
@@ -1232,6 +1255,7 @@ static int swiotlb_find_slots(struct device *dev, phys_addr_t orig_addr,
 	nslabs = nr_slots(alloc_size);
 	phys_limit = min_not_zero(*dev->dma_mask, dev->bus_dma_limit);
 	pool = swiotlb_alloc_pool(dev, nslabs, nslabs, 1, phys_limit,
+				  mem->unencrypted ? DMA_ATTR_CC_SHARED : 0,
 				  GFP_NOWAIT);
 	if (!pool)
 		return -1;
@@ -1394,6 +1418,7 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 		enum dma_data_direction dir, unsigned long attrs)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
+	bool require_decrypted = false;
 	unsigned int offset;
 	struct io_tlb_pool *pool;
 	unsigned int i;
@@ -1411,6 +1436,16 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
 		pr_warn_once("Memory encryption is active and system is using DMA bounce buffers\n");
 
+	/*
+	 * if we are trying to swiotlb map a decrypted paddr or the paddr is encrypted
+	 * but the device is forcing decryption, use decrypted io_tlb_mem
+	 */
+	if ((attrs & DMA_ATTR_CC_SHARED) || force_dma_unencrypted(dev))
+		require_decrypted = true;
+
+	if (require_decrypted != mem->unencrypted)
+		return (phys_addr_t)DMA_MAPPING_ERROR;
+
 	/*
 	 * The default swiotlb memory pool is allocated with PAGE_SIZE
 	 * alignment. If a mapping is requested with larger alignment,
@@ -1608,8 +1643,14 @@ dma_addr_t swiotlb_map(struct device *dev, phys_addr_t paddr, size_t size,
 	if (swiotlb_addr == (phys_addr_t)DMA_MAPPING_ERROR)
 		return DMA_MAPPING_ERROR;
 
-	/* Ensure that the address returned is DMA'ble */
-	dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
+	/*
+	 * Use the allocated io_tlb_mem encryption type to determine dma addr.
+	 */
+	if (dev->dma_io_tlb_mem->unencrypted)
+		dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
+	else
+		dma_addr = phys_to_dma_encrypted(dev, swiotlb_addr);
+
 	if (unlikely(!dma_capable(dev, dma_addr, size, true))) {
 		__swiotlb_tbl_unmap_single(dev, swiotlb_addr, size, dir,
 			attrs | DMA_ATTR_SKIP_CPU_SYNC,
@@ -1773,7 +1814,8 @@ static inline void swiotlb_create_debugfs_files(struct io_tlb_mem *mem,
 
 #ifdef CONFIG_DMA_RESTRICTED_POOL
 
-struct page *swiotlb_alloc(struct device *dev, size_t size)
+struct page *swiotlb_alloc(struct device *dev, size_t size,
+		unsigned long attrs)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 	struct io_tlb_pool *pool;
@@ -1784,6 +1826,9 @@ struct page *swiotlb_alloc(struct device *dev, size_t size)
 	if (!mem)
 		return NULL;
 
+	if (mem->unencrypted != !!(attrs & DMA_ATTR_CC_SHARED))
+		return NULL;
+
 	align = (1 << (get_order(size) + PAGE_SHIFT)) - 1;
 	index = swiotlb_find_slots(dev, 0, size, align, &pool);
 	if (index == -1)
@@ -1853,9 +1898,18 @@ static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
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

## [6] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 05/13] dma-mapping: make dma_pgprot() honor DMA_ATTR_CC_SHARED*

Fold encrypted/decrypted pgprot selection into dma_pgprot() so callers
do not need to adjust the page protection separately.

Update dma_pgprot() to apply pgprot_decrypted() when
DMA_ATTR_CC_SHARED is set and pgprot_encrypted() otherwise Convert
the dma-direct allocation and mmap paths to pass DMA_ATTR_CC_SHARED
instead of open-coding force_dma_unencrypted() handling around
dma_pgprot().

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c  |  8 +++-----
 kernel/dma/mapping.c | 16 ++++++++++++----
 2 files changed, 15 insertions(+), 9 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 97ae4fa10521..ac315dd046c4 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -298,9 +298,6 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	if (remap) {
 		pgprot_t prot = dma_pgprot(dev, PAGE_KERNEL, attrs);
 
-		if (force_dma_unencrypted(dev))
-			prot = pgprot_decrypted(prot);
-
 		/* remove any dirty cache lines on the kernel alias */
 		arch_dma_prep_coherent(page, size);
 
@@ -603,9 +600,10 @@ int dma_direct_mmap(struct device *dev, struct vm_area_struct *vma,
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
index 23ed8eb9233e..44f715f3aa2d 100644
--- a/kernel/dma/mapping.c
+++ b/kernel/dma/mapping.c
@@ -543,13 +543,21 @@ EXPORT_SYMBOL(dma_get_sgtable_attrs);
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

## [7] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 06/13] dma-direct: pass attrs to dma_capable() for DMA_ATTR_CC_SHARED checks*

Teach dma_capable() about DMA_ATTR_CC_SHARED so the capability
check can reject encrypted DMA addresses for devices that require
unencrypted/shared DMA.

Also propagate DMA_ATTR_CC_SHARED in swiotlb_map() when the selected
SWIOTLB pool is decrypted so the capability check sees the correct DMA
address attribute.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/x86/kernel/amd_gart_64.c | 30 ++++++++++++++++--------------
 drivers/xen/swiotlb-xen.c     | 10 +++++++---
 include/linux/dma-direct.h    |  9 ++++++++-
 kernel/dma/direct.h           |  6 +++---
 kernel/dma/swiotlb.c          |  8 +++++---
 5 files changed, 39 insertions(+), 24 deletions(-)

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
index 2cbf2b588f5b..fa6734461d4c 100644
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
@@ -248,12 +248,16 @@ static dma_addr_t xen_swiotlb_map_phys(struct device *dev, phys_addr_t phys,
 		return DMA_MAPPING_ERROR;
 
 	phys = map;
+	/* This always return an encrypted addr */
 	dev_addr = xen_phys_to_dma(dev, map);
 
+	if (WARN_ON(dev->dma_io_tlb_mem->unencrypted))
+		attrs |= DMA_ATTR_CC_SHARED;
+
 	/*
 	 * Ensure that the address returned is DMA'ble
 	 */
-	if (unlikely(!dma_capable(dev, dev_addr, size, true))) {
+	if (unlikely(!dma_capable(dev, dev_addr, size, true, attrs))) {
 		__swiotlb_tbl_unmap_single(dev, map, size, dir,
 				attrs | DMA_ATTR_SKIP_CPU_SYNC,
 				swiotlb_find_pool(dev, map));
diff --git a/include/linux/dma-direct.h b/include/linux/dma-direct.h
index 94fad4e7c11e..9dbe198b2c4a 100644
--- a/include/linux/dma-direct.h
+++ b/include/linux/dma-direct.h
@@ -135,12 +135,19 @@ static inline bool force_dma_unencrypted(struct device *dev)
 #endif /* CONFIG_ARCH_HAS_FORCE_DMA_UNENCRYPTED */
 
 static inline bool dma_capable(struct device *dev, dma_addr_t addr, size_t size,
-		bool is_ram)
+		bool is_ram, unsigned long attrs)
 {
 	dma_addr_t end = addr + size - 1;
 
 	if (addr == DMA_MAPPING_ERROR)
 		return false;
+	/*
+	 * if phys addr attribute is encrypted but the
+	 * device is forcing an unencrypted dma addr
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
index 065663be282c..9f87ebe42797 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -1646,12 +1646,14 @@ dma_addr_t swiotlb_map(struct device *dev, phys_addr_t paddr, size_t size,
 	/*
 	 * Use the allocated io_tlb_mem encryption type to determine dma addr.
 	 */
-	if (dev->dma_io_tlb_mem->unencrypted)
+	if (dev->dma_io_tlb_mem->unencrypted) {
 		dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
-	else
+		attrs |= DMA_ATTR_CC_SHARED;
+	} else {
 		dma_addr = phys_to_dma_encrypted(dev, swiotlb_addr);
+	}
 
-	if (unlikely(!dma_capable(dev, dma_addr, size, true))) {
+	if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs))) {
 		__swiotlb_tbl_unmap_single(dev, swiotlb_addr, size, dir,
 			attrs | DMA_ATTR_SKIP_CPU_SYNC,
 			swiotlb_find_pool(dev, swiotlb_addr));

---

## [8] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 07/13] dma-direct: make dma_direct_map_phys() honor DMA_ATTR_CC_SHARED*

Teach dma_direct_map_phys() to select the DMA address encoding based on
DMA_ATTR_CC_SHARED.

Use phys_to_dma_unencrypted() for decrypted mappings and
phys_to_dma_encrypted() otherwise. If a device requires unencrypted DMA
but the source physical address is still encrypted, force the mapping
through swiotlb so the DMA address and backing memory attributes remain
consistent.

Update the arm64, x86, s390 and powerpc secure-guest setup to not use
swiotlb force option

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
 kernel/dma/direct.h                  | 38 +++++++++++++---------------
 6 files changed, 24 insertions(+), 30 deletions(-)

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
index 1f72efc2a579..843dbd445124 100644
--- a/arch/s390/mm/init.c
+++ b/arch/s390/mm/init.c
@@ -149,7 +149,7 @@ static void __init pv_init(void)
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
index ac315dd046c4..5aaa813c5509 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -691,8 +691,10 @@ size_t dma_direct_max_mapping_size(struct device *dev)
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
index e05dc7649366..4e35264ab6f8 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -89,36 +89,32 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 	dma_addr_t dma_addr;
 
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

## [9] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 08/13] dma-direct: set decrypted flag for remapped DMA allocations*

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
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 56 ++++++++++++++++++++++++++++++++++++---------
 1 file changed, 45 insertions(+), 11 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 5aaa813c5509..f5da6e992d83 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -204,6 +204,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 {
 	bool remap = false, set_uncached = false;
 	bool mark_mem_decrypt = false;
+	bool allow_highmem = true;
 	struct page *page;
 	void *ret;
 
@@ -222,6 +223,15 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
@@ -280,7 +290,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	}
 
 	/* we always manually zero the memory once we are done */
-	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, true);
+	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, allow_highmem);
 	if (!page)
 		return NULL;
 
@@ -295,6 +305,14 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
 
@@ -305,31 +323,39 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
 	__dma_direct_free_pages(dev, page, size);
 	return NULL;
+
 out_leak_pages:
 	return NULL;
 }
@@ -384,8 +410,16 @@ void dma_direct_free(struct device *dev, size_t size,
 	} else {
 		if (IS_ENABLED(CONFIG_ARCH_HAS_DMA_CLEAR_UNCACHED))
 			arch_dma_clear_uncached(cpu_addr, size);
-		if (mark_mem_encrypted && dma_set_encrypted(dev, cpu_addr, size))
+	}
+
+	if (mark_mem_encrypted) {
+		void *lm_addr;
+
+		lm_addr = phys_to_virt(dma_to_phys(dev, dma_addr));
+		if (set_memory_encrypted((unsigned long)lm_addr, PFN_UP(size))) {
+			pr_warn_ratelimited("leaking DMA memory that can't be re-encrypted\n");
 			return;
+		}
 	}
 
 	__dma_direct_free_pages(dev, dma_direct_to_page(dev, dma_addr), size);

---

## [10] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 09/13] dma-direct: select DMA address encoding from DMA_ATTR_CC_SHARED*

Make the dma-direct helpers derive the DMA address encoding from
DMA_ATTR_CC_SHARED instead of implicitly relying on
force_dma_unencrypted() inside phys_to_dma_direct()

Pass an explicit unencrypted/decrypted state into phys_to_dma_direct(),
make the alloc paths return DMA addresses that match the requested
buffer encryption state. Also only call dma_set_decrypted()
DMA_ATTR_CC_SHARED is actually set.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 48 ++++++++++++++++++++++++++++-----------------
 1 file changed, 30 insertions(+), 18 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index f5da6e992d83..1e9f9ff7b9d3 100644
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
 	phys_addr_t phys = (phys_addr_t)(max_pfn - 1) << PAGE_SHIFT;
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
@@ -177,7 +180,8 @@ static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
 				   dma_coherent_ok);
 	if (!page)
 		return NULL;
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
+					 !!(attrs & DMA_ATTR_CC_SHARED));
 	return ret;
 }
 
@@ -193,9 +197,11 @@ static void *dma_direct_alloc_no_mapping(struct device *dev, size_t size,
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
 
@@ -340,7 +346,8 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		ret = uncached_cpu_addr;
 	}
 
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page),
+					 !!(attrs & DMA_ATTR_CC_SHARED));
 	return ret;
 
 
@@ -457,11 +464,12 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
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
@@ -471,8 +479,12 @@ void dma_direct_free_pages(struct device *dev, size_t size,
 		struct page *page, dma_addr_t dma_addr,
 		enum dma_data_direction dir)
 {
+	/*
+	 * if the device had requested for an unencrypted buffer,
+	 * convert it to encrypted on free
+	 */
+	bool mark_mem_encrypted =  force_dma_unencrypted(dev);
 	void *vaddr = page_address(page);
-	bool mark_mem_encrypted = true;
 
 	/* If cpu_addr is not from an atomic pool, dma_free_from_pool() fails */
 	if (IS_ENABLED(CONFIG_DMA_COHERENT_POOL) &&

---

## [11] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 10/13] dma-pool: fix page leak in atomic_pool_expand() cleanup*

atomic_pool_expand() frees the allocated pages from the remove_mapping
error path only when CONFIG_DMA_DIRECT_REMAP is enabled.

When CONFIG_DMA_DIRECT_REMAP is disabled, failures after page allocation,
such as gen_pool_add_virt(), jump to remove_mapping and return without
freeing the pages.

Move __free_pages(page, order) out of the CONFIG_DMA_DIRECT_REMAP block so
that cleanup paths always release the allocation.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/pool.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index 75f0eba48a23..5abd30c5119f 100644
--- a/kernel/dma/pool.c
+++ b/kernel/dma/pool.c
@@ -149,8 +149,8 @@ static int atomic_pool_expand(struct dma_gen_pool *dma_pool, size_t pool_size,
 #ifdef CONFIG_DMA_DIRECT_REMAP
 	dma_common_free_remap(addr, pool_size);
 free_page:
-	__free_pages(page, order);
 #endif
+	__free_pages(page, order);
 out:
 	return ret;
 }

---

## [12] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 11/13] dma-direct: rename ret to cpu_addr in alloc helpers*

ret in dma_direct_alloc() and dma_direct_alloc_pages() holds the returned
CPU mapping, not a generic return value. Rename it to cpu_addr and update
the remaining uses to match.

This makes the allocation paths easier to follow and keeps the local naming
consistent with what the variable actually represents.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 31 +++++++++++++++----------------
 1 file changed, 15 insertions(+), 16 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 1e9f9ff7b9d3..902008e40ea1 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -212,7 +212,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	bool mark_mem_decrypt = false;
 	bool allow_highmem = true;
 	struct page *page;
-	void *ret;
+	void *cpu_addr;
 
 	/*
 	 * DMA_ATTR_CC_SHARED is not a caller-visible dma_alloc_*()
@@ -326,34 +326,33 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
@@ -437,7 +436,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 {
 	unsigned long attrs = 0;
 	struct page *page;
-	void *ret;
+	void *cpu_addr;
 
 	if (force_dma_unencrypted(dev))
 		attrs |= DMA_ATTR_CC_SHARED;
@@ -455,7 +454,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 			swiotlb_free(dev, page, size);
 			return NULL;
 		}
-		ret = page_address(page);
+		cpu_addr = page_address(page);
 		goto setup_page;
 	}
 
@@ -463,11 +462,11 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
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

## [13] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 12/13] dma-direct: return struct page from dma_direct_alloc_from_pool()*

Commit 5b138c534fda ("dma-direct: factor out a dma_direct_alloc_from_pool
helper") changed dma_direct_alloc_from_pool() to return the CPU address
from dma_alloc_from_pool(). That fits dma_direct_alloc(), but
dma_direct_alloc_pages() also uses the helper and expects a struct page *.

Fix this by making dma_direct_alloc_from_pool() return the struct page *
again, and pass the CPU address back through an out-parameter for the
dma_direct_alloc() caller.

Fixes: 5b138c534fda ("dma-direct: factor out a dma_direct_alloc_from_pool helper")
Cc: stable@vger.kernel.org

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 21 ++++++++++++---------
 1 file changed, 12 insertions(+), 9 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 902008e40ea1..5103a04df99f 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -165,24 +165,24 @@ static bool dma_direct_use_pool(struct device *dev, gfp_t gfp)
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
@@ -278,9 +278,12 @@ void *dma_direct_alloc(struct device *dev, size_t size,
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
@@ -443,7 +446,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 
 	if ((attrs & DMA_ATTR_CC_SHARED) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle,
-						  gfp, attrs);
+						  &cpu_addr, gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
 		page = dma_direct_alloc_swiotlb(dev, size, attrs);

---

## [14] Aneesh Kumar K.V (Arm) — 2026-05-12
*Subject: [PATCH v4 13/13] x86/amd-gart: preserve the direct DMA address until GART mapping succeeds*

gart_alloc_coherent() first allocates memory through dma_direct_alloc(),
which returns a direct-mapped DMA address in dma_addr. When force_iommu is
enabled, the buffer is then remapped.

Do not overwrite dma_addr before dma_map_area() has succeeded. Keep the
dma_map_area result in a temporary variable so the direct DMA address
remains available for dma_direct_free() on the error path.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/x86/kernel/amd_gart_64.c | 10 ++++++----
 1 file changed, 6 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kernel/amd_gart_64.c b/arch/x86/kernel/amd_gart_64.c
index b5f1f031d45b..a109649c5649 100644
--- a/arch/x86/kernel/amd_gart_64.c
+++ b/arch/x86/kernel/amd_gart_64.c
@@ -467,18 +467,20 @@ gart_alloc_coherent(struct device *dev, size_t size, dma_addr_t *dma_addr,
 		    gfp_t flag, unsigned long attrs)
 {
 	void *vaddr;
+	dma_addr_t dma_map_addr;
 
 	vaddr = dma_direct_alloc(dev, size, dma_addr, flag, attrs);
 	if (!vaddr ||
 	    !force_iommu || dev->coherent_dma_mask <= DMA_BIT_MASK(24))
 		return vaddr;
 
-	*dma_addr = dma_map_area(dev, virt_to_phys(vaddr), size,
-				 DMA_BIDIRECTIONAL,
-				 (1UL << get_order(size)) - 1, attrs);
+	dma_map_addr = dma_map_area(dev, virt_to_phys(vaddr), size,
+				     DMA_BIDIRECTIONAL,
+				     (1UL << get_order(size)) - 1, attrs);
 	flush_gart();
-	if (unlikely(*dma_addr == DMA_MAPPING_ERROR))
+	if (unlikely(dma_map_addr == DMA_MAPPING_ERROR))
 		goto out_free;
+	*dma_addr = dma_map_addr;
 	return vaddr;
 out_free:
 	dma_direct_free(dev, size, vaddr, *dma_addr, attrs);

---

## [15] Mostafa Saleh — 2026-05-13
*Subject: Re: [PATCH v4 01/13] dma-direct: swiotlb: handle swiotlb alloc/free
 outside __dma_direct_alloc_pages*

On Tue, May 12, 2026 at 02:33:56PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Move swiotlb allocation out of __dma_direct_alloc_pages() and handle it in
> dma_direct_alloc() / dma_direct_alloc_pages().

I am ok with that approach, but Jason was mentioning we shouldn’t
special case swiotlb and make the allocator return the memory state
(similar to the dma_page [1]) . I am also OK if you want to merge that
part of my series with is.

[1] https://lore.kernel.org/linux-iommu/20260408194750.2280873-1-smostafa@google.com/

>  			goto out_leak_pages;
>  	}

My understanding is that rmem_swiotlb_device_init() asserts that there
is no PageHighMem()? Also a similar check doesn’t exist in
dma_direct_alloc().

Thanks,
Mostafa


> +			swiotlb_free(dev, page, size);
> +			return NULL;

---

## [16] Mostafa Saleh — 2026-05-13
*Subject: Re: [PATCH v4 02/13] dma-direct: use DMA_ATTR_CC_SHARED in
 alloc/free paths*

On Tue, May 12, 2026 at 02:33:57PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Propagate force_dma_unencrypted() into DMA_ATTR_CC_SHARED in the
> dma-direct allocation path and use the attribute to drive the related

What about dma_direct_free_pages()? Nothing inside uses attrs, but
that’s quite similar to dma_direct_alloc_pages()

Also, at this point, shouldn’t this patch also remove
force_dma_unencrypted() calls from dma_set_decrypted() and
dma_set_encrypted()?

Thanks,
Mostafa

>  
>  	if (is_swiotlb_for_alloc(dev)) {

---

## [17] Mostafa Saleh — 2026-05-13
*Subject: Re: [PATCH v4 03/13] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Tue, May 12, 2026 at 02:33:58PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Teach the atomic DMA pool code to distinguish between encrypted and
> decrypted pools, and make pool allocation select the matching pool based

I believe that’s a good start, although we might need to have more
fine grained policies in the future as CC guests might need
encrypted pools

Reviewed-by: Mostafa Saleh <smostafa@google.com>

Thanks,
Mostafa

>  
> -	ret = atomic_pool_expand(pool, pool_size, gfp);

nit: If we fail to find a matching pool, a slightly misleading message
is printed as pool_found = false

>  		pool_found = true;
> -		page = __dma_alloc_from_pool(dev, size, pool, cpu_addr,

---

## [18] Mostafa Saleh — 2026-05-13
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 12, 2026 at 02:33:59PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Teach swiotlb to distinguish between encrypted and decrypted bounce
> buffer pools, and make allocation and mapping paths select a pool whose

This breaks pKVM as it doesn’t set CC_ATTR_MEM_ENCRYPT, so all virtio
traffic now fails.

Also, by design, some drivers are clueless about bouncing, so
I believe that the pool should have a way to control it’s property
(encrypted or decrypted) and that takes priority over whatever
attributes comes from allocation.
And that brings us to the same point whether it’s better to return
the memory along with it’s state or we pass the requested state.
I think for other cases it’s fine for the device/DMA-API to dictate
the attrs, but not in restricted-dma case, the firmware just knows better.

Thanks,
Mostafa

>  
> -		set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),

---

## [19] Jason Gunthorpe — 2026-05-13
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Wed, May 13, 2026 at 02:27:14PM +0000, Mostafa Saleh wrote:

> > +		/*
> > +		 * if platform supports memory encryption,

How will pKVM signal what kind of memory the DMA needs then?

Does it use set_memory_decrypted()? How can it use
set_memory_decrypted() without offering CC_ATTR_MEM_ENCRYPT ?

> Also, by design, some drivers are clueless about bouncing, so

Oh? What does this mean? We take quite a dim view of drivers mis-using
the DMA API..

> I believe that the pool should have a way to control it’s property
> (encrypted or decrypted) and that takes priority over whatever

We should get here because dma_capable() fails, and then swiotlb needs
to return something that makes dma_capable() succeed. Yes, it should
return details about the thing it decided, but it shouldn't have been
pre-created with some idea how to make dma_capable() work.

If dma_capable() can fail, then swiotlb should know exactly what to do
to fix it.

If pkvm wants to use the hacky scheme where you force a swiotlb pool
configuration during arch init with force swiotlb that's a somewhat
different flow and, sure the forced pool should force do whatever it
is forced to.

But lets try to keep them seperated in the discussion..

> And that brings us to the same point whether it’s better to return
> the memory along with it’s state or we pass the requested state.

The memory type must be returned back at some level so downstream
things can do the right transformation of the phys_addr_t.

One of the aspirational CC things that should work is a T=1 device
tries to DMA from a decrypted page, finds the address is above the dma
limit of the device, so it bounces it with SWIOTLB to an encrypted low
address page and then the DMA API internal flow switiches from working
with decrypted to encrypted phys_addr_t.

If we can make that work then maybe the flows are designed correctly.

Jason

---

## [20] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v4 01/13] dma-direct: swiotlb: handle swiotlb alloc/free
 outside __dma_direct_alloc_pages*

Mostafa Saleh <smostafa@google.com> writes:

> On Tue, May 12, 2026 at 02:33:56PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> Move swiotlb allocation out of __dma_direct_alloc_pages() and handle it in

I was not sure whether we need dma_page. As shown in this series, we can
simplify the allocation and free paths without adding new abstractions
like dma_page.

>
>>  			goto out_leak_pages;

The reason I added that HighMem check is that __dma_direct_alloc_pages()
already has that check.

	page = dma_alloc_contiguous(dev, size, gfp);
	if (page) {
		if (dma_coherent_ok(dev, page_to_phys(page), size) &&
		    (allow_highmem || !PageHighMem(page)))
			return page;

		dma_free_contiguous(dev, page, size);
	}

I understand that the current usage of swiotlb alloc is restricted to
restricted memory, and it will not return HighMem pages. I will drop
this hunk from the patch.

-aneesh

---

## [21] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v4 02/13] dma-direct: use DMA_ATTR_CC_SHARED in
 alloc/free paths*

Mostafa Saleh <smostafa@google.com> writes:

> On Tue, May 12, 2026 at 02:33:57PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> Propagate force_dma_unencrypted() into DMA_ATTR_CC_SHARED in the

The final change have 

void dma_direct_free_pages(struct device *dev, size_t size,
...
{
	/*
	 * if the device had requested for an unencrypted buffer,
	 * convert it to encrypted on free
	 */
	bool mark_mem_encrypted =  force_dma_unencrypted(dev);

That got added by "dma-direct: select DMA address encoding from DMA_ATTR_CC_SHARED "

I'll move that hunk into this patch. The overall goal is 

dma_direct_alloc(.. attrs)
{

	if (force_dma_unencrypted(dev))
		attrs |= DMA_ATTR_CC_SHARED;
}

dma_direct_free(.. attrs)
{
	if (force_dma_unencrypted(dev)) {
		attrs |= DMA_ATTR_CC_SHARED;
		mark_mem_encrypted = true;
	}

	if (swiotlb_find_pool(dev, dma_to_phys(dev, dma_addr)))
		mark_mem_encrypted = false;

}

dma_direct_alloc_pages()
{
	if (force_dma_unencrypted(dev))
		attrs |= DMA_ATTR_CC_SHARED;

}

dma_direct_free_pages()
{
	bool mark_mem_encrypted =  force_dma_unencrypted(dev);

	if (swiotlb_find_pool(dev, page_to_phys(page)))
		mark_mem_encrypted = false;

}

-aneesh

---

## [22] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Mostafa Saleh <smostafa@google.com> writes:

> On Tue, May 12, 2026 at 02:33:59PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> Teach swiotlb to distinguish between encrypted and decrypted bounce

Is it that the pKVM guest kernel does not have awareness of
encrypted/decrypted DMA allocations? Instead, the firmware attaches
hypervisor-shared pages to the device via restricted-dma-pool? The
kernel then has swiotlb->for_alloc = true, and hence all DMA allocations
go through the restricted-dma-pool?

Given that pKVM supports pkvm_set_memory_encrypted() and
pkvm_set_memory_decrypted(), can we consider adding CC_ATTR_MEM_ENCRYPT
support to pKVM? It would also be good to investigate whether we can set
force_dma_unencrypted(dev) to true where needed.

I agree that this patch, as it stands, can break pKVM because we are now
missing the set_memory_decrypted() call required for pKVM to work.

We now mark the swiotlb io_tlb_mem as unencrypted/encrypted in the guest
using struct io_tlb_mem->unencrypted. I am not clear what we can use for
pKVM to conditionalize this so that it works for both protected and
unprotected guests.

-aneesh

---

## [23] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Jason Gunthorpe <jgg@ziepe.ca> writes:

>> And that brings us to the same point whether it’s better to return
>> the memory along with it’s state or we pass the requested state.

That is what this patch series aims to do. dma_direct_map_phys() will
derive the DMA address based on the attributes of the physical address:

if (attrs & DMA_ATTR_CC_SHARED)
        dma_addr = phys_to_dma_unencrypted(dev, phys);
else
        dma_addr = phys_to_dma_encrypted(dev, phys);

If that fails the dma_capable() check, we fall back to swiotlb_map():

if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs)))
        return swiotlb_map(dev, phys, size, dir, attrs);

We currently do not have an encrypted SWIOTLB pool, but once that is
supported, swiotlb_map() should do the right thing and return the
correct encrypted dma_addr_t based on io_tlb_mem->unencrypted:

if (dev->dma_io_tlb_mem->unencrypted) {
        dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
        attrs |= DMA_ATTR_CC_SHARED;
} else {
        dma_addr = phys_to_dma_encrypted(dev, swiotlb_addr);
}

-aneesh

---

## [24] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v4 03/13] dma-pool: track decrypted atomic pools and
 select them via attrs*

Mostafa Saleh <smostafa@google.com> writes:

...

>>  struct page *dma_alloc_from_pool(struct device *dev, size_t size,
>> -		void **cpu_addr, gfp_t gfp,

The message printed is

	WARN(1, "Failed to get suitable pool for %s\n", dev_name(dev));

That is correct, isn’t it? The kernel failed to find a pool with the
correct encryption attribute. For example, the request was for an
encrypted allocation from the pool, but no encrypted pool was available.

>
>>  		pool_found = true;

-aneesh

---

## [25] Mostafa Saleh — 2026-05-14
*Subject: Re: [PATCH v4 03/13] dma-pool: track decrypted atomic pools and
 select them via attrs*

On Thu, May 14, 2026 at 8:01 AM Aneesh Kumar K.V
<aneesh.kumar@kernel.org> wrote:
>
> Mostafa Saleh <smostafa@google.com> writes:

Sure, I’d prefer a clearer print in that case, especially since that’s new code:
“Only {encrypted/decrypted} pool found for a {encrypted/decrypted} alloction”

But no strong opinion.

Thanks,
Mostafa



> >
> >>              pool_found = true;

---

## [26] Mostafa Saleh — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Wed, May 13, 2026 at 02:24:50PM -0300, Jason Gunthorpe wrote:
> On Wed, May 13, 2026 at 02:27:14PM +0000, Mostafa Saleh wrote:
> 

pKVM (hypervisor) doesn’t signal anything.
The VMM when running protected guests will use restricted dma-pools
for emulated vritio devices in the guest, which gets decrypted by
the guest kernel and hence shared with the host kernel, and then
traffic is bounced via the pool.

It’s also worth noting that bouncing here isn't just about visibility.
Because memory sharing operates at page granularity, bouncing sub-page
allocations through the restricted pool prevents adjacent, sensitive
guest data from being exposed to the untrusted host.

> 
> > Also, by design, some drivers are clueless about bouncing, so

Maybe clueless is not the right word, I mean when virtio drivers use
the DMA API they don’t know whether it’s going to bounce or not as
that is decided by dma-direct (and in other cases by dma-iommu,
but not for pKVM).

> 
> > I believe that the pool should have a way to control it’s property

That sounds neat, but at the end we have force_dma_unencrypted() in
dma_capable() which is just hardcoded to true/false by the platform.
How is that different from having the state static by the pool?

> 
> If dma_capable() can fail, then swiotlb should know exactly what to do

dma_capable() returns a bool, I don’t think it can know what exactly
went wrong (based on address, size, attrs, dev...)

> 
> If pkvm wants to use the hacky scheme where you force a swiotlb pool

While we can debate the aesthetics of the setup , this is
the exisitng behaviour for Linux, which existed for years
and pKVM relies on and is used extensively.
And, this patch alters that long-standing logic and introduces
a functional regression.

We can address this by either adjusting this patch or by changing
pKVM guests to be more aligned with other CCA guests which is
something I have been wondering about if it would help reduce
bouncing.

> 
> > And that brings us to the same point whether it’s better to return

Agreed, I believe that will be needed at least for
SWIOTLB/restricted-dma -> dma-API interactions.

> 
> One of the aspirational CC things that should work is a T=1 device

Mmm, I am not sure I understand this one, shouldn’t the device also be
notified about the switch in memory state, if it expects to read/write
decrypted memory, how would that work if the kernel changes it to an
encrypted one?

Thanks,
Mostafa
> 
> Jason

---

## [27] Mostafa Saleh — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu, May 14, 2026 at 11:24:42AM +0530, Aneesh Kumar K.V wrote:
> Mostafa Saleh <smostafa@google.com> writes:
> 

Yes.

> 
> Given that pKVM supports pkvm_set_memory_encrypted() and

I was looking in to that, but it didn't work because
force_dma_unencrypted() is broken with restricted-dma due to the
double decryption issue, that's when I sent my first series [1]

May be we should land some basic fixes for that path so we can
convert pKVM, then we do the full rework.

I will revive my old work and see if I can send a RFC.

[1] https://lore.kernel.org/all/20260305170335.963568-1-smostafa@google.com/

> 
> I agree that this patch, as it stands, can break pKVM because we are now

There is no problem with non-protected guests as they don't use memory
encryption, my initial thought was that th encrpyted/decrypted is
per-pool property which is decided by FW (device-tree).

Thanks,
Mostafa

> 
> -aneesh

---

## [28] Jason Gunthorpe — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

> > How will pKVM signal what kind of memory the DMA needs then?
> > 

That really does sound like CC and set_memory_decrypted() to me..

> It’s also worth noting that bouncing here isn't just about visibility.
> Because memory sharing operates at page granularity, bouncing sub-page

That's a somewhat different problem, we have the dev->trusted stuff
that is supposed to deal with this kind of security. We need it for
IOMMU based systems too, eg hot plug thunderbolt should have it.

Then CC issue is more that the DMA API can't decrypt random passed in
memory because doing so often requires changing the PTEs pointing at
the page so it would break everything if done transparently.

> > > I believe that the pool should have a way to control it’s property
> > > (encrypted or decrypted) and that takes priority over whatever

For now, the next step is it becomes per-device and dynamic during the
device lifecycle.

> How is that different from having the state static by the pool?

statically attached pools to the device are not so flexible when
devices have dynamically changing capabilities..

> > If dma_capable() can fail, then swiotlb should know exactly what to do
> > to fix it.

Yes, but I think the design is swiotlb is supposed to re-inspect what
is going on against the limits dma_capable checks and then select the
correct remedy..

> While we can debate the aesthetics of the setup , this is
> the exisitng behaviour for Linux, which existed for years

Yeah, Aneesh needs to do something here, I'm pointing out it is
entirely seperate thing from the CC path we are working on which is
decoupling CC from reylying on force swiotlb.

> We can address this by either adjusting this patch or by changing
> pKVM guests to be more aligned with other CCA guests which is

Every time I look at pkvm I think it is just ARM CCA with a different
design and no access to the unique HW features..

> > If we can make that work then maybe the flows are designed correctly.
> 

Nothing on the device changes. In a CC world we put the device in a
T=0 or T=1 state before the driver loads and the expectation from the
DMA API is that the device will only use that T=x DMA type during
operation.

A T=1 state device can access all of memory, private or shared. Any
information the platform may need is encoded in the dma_addr_t or in
the S1 IOPTEs.

So we never need to tell the device driver what kind of memory the DMA
is targetting, and we NEVER expect a device in T=1 mode to have to
issue a T=0 DMA to use the DMA API.

In a pkvm world it should be the same, the S2 table for the SMMU will
control what the device can access, and if the SMMU points to a
"private" or "shared" page is not something the device needs to know
or care about.

Jason

---

## [29] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Mostafa Saleh <smostafa@google.com> writes:

> On Thu, May 14, 2026 at 11:24:42AM +0530, Aneesh Kumar K.V wrote:
>> Mostafa Saleh <smostafa@google.com> writes:

With this series, can you check whether the only change needed is
something like the following?

modified   kernel/dma/swiotlb.c
@@ -1905,7 +1905,8 @@ static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
 		 * if platform supports memory encryption,
 		 * restricted mem pool is decrypted by default
 		 */
-		if (cc_platform_has(CC_ATTR_MEM_ENCRYPT)) {
+		//if (cc_platform_has(CC_ATTR_MEM_ENCRYPT)) {
+		if (true) {
 			mem->unencrypted = true;
 			set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),
 					     rmem->size >> PAGE_SHIFT);

>
>> 

What I meant was that we need a generic way to identify a pKVM guest, so
that we can use it in the conditional above.

-aneesh

---

## [30] Mostafa Saleh — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu, May 14, 2026 at 06:18:05PM +0530, Aneesh Kumar K.V wrote:
> Mostafa Saleh <smostafa@google.com> writes:
> 

Yes, that boots, but I will need to do more tests.

> 
> >

I have this patch, with that I can boot with your series unmodified,
but I will need to do more testing.

From d795b4c4ee2437587616b2b342e9996afe6d6680 Mon Sep 17 00:00:00 2001
From: Mostafa Saleh <smostafa@google.com>
Date: Thu, 14 May 2026 13:46:15 +0000
Subject: [PATCH] arm64/coco: Add pKVM as a CC platform

pKVM does support memory encryption, expose that to the rest of
the kernel through cc_platform_has()

At the moment, all devices inside the guest are emulated which
requires its memory to be shared back to the host (decrypted), so
set force_dma_unencrypted() to always return true.

Signed-off-by: Mostafa Saleh <smostafa@google.com>
---
 arch/arm64/include/asm/hypervisor.h           |  6 ++++++
 arch/arm64/include/asm/mem_encrypt.h          |  3 ++-
 arch/arm64/kernel/rsi.c                       | 12 ------------
 arch/arm64/mm/init.c                          | 13 +++++++++++++
 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c |  5 +++++
 5 files changed, 26 insertions(+), 13 deletions(-)

diff --git a/arch/arm64/include/asm/hypervisor.h b/arch/arm64/include/asm/hypervisor.h
index a12fd897c877..1b0e15f290be 100644
--- a/arch/arm64/include/asm/hypervisor.h
+++ b/arch/arm64/include/asm/hypervisor.h
@@ -10,8 +10,14 @@ void kvm_arm_target_impl_cpu_init(void);

 #ifdef CONFIG_ARM_PKVM_GUEST
 void pkvm_init_hyp_services(void);
+bool is_protected_kvm_guest(void);
 #else
 static inline void pkvm_init_hyp_services(void) { };
+
+static inline bool is_protected_kvm_guest(void)
+{
+	return false;
+}
 #endif

 static inline void kvm_arch_init_hyp_services(void)
diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index 314b2b52025f..636f45b4d8af 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -2,6 +2,7 @@
 #ifndef __ASM_MEM_ENCRYPT_H
 #define __ASM_MEM_ENCRYPT_H

+#include <asm/hypervisor.h>
 #include <asm/rsi.h>

 struct device;
@@ -20,7 +21,7 @@ int realm_register_memory_enc_ops(void);

 static inline bool force_dma_unencrypted(struct device *dev)
 {
-	return is_realm_world();
+	return is_realm_world() || is_protected_kvm_guest();
 }

 /*
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 92160f2e57ff..25ca75ce1a4d 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -7,7 +7,6 @@
 #include <linux/memblock.h>
 #include <linux/psci.h>
 #include <linux/swiotlb.h>
-#include <linux/cc_platform.h>
 #include <linux/platform_device.h>

 #include <asm/io.h>
@@ -23,17 +22,6 @@ EXPORT_SYMBOL(prot_ns_shared);
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);

-bool cc_platform_has(enum cc_attr attr)
-{
-	switch (attr) {
-	case CC_ATTR_MEM_ENCRYPT:
-		return is_realm_world();
-	default:
-		return false;
-	}
-}
-EXPORT_SYMBOL_GPL(cc_platform_has);
-
 static bool rsi_version_matches(void)
 {
 	unsigned long ver_lower, ver_higher;
diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
index acf67c7064db..a087ac5b15f7 100644
--- a/arch/arm64/mm/init.c
+++ b/arch/arm64/mm/init.c
@@ -12,6 +12,7 @@
 #include <linux/swap.h>
 #include <linux/init.h>
 #include <linux/cache.h>
+#include <linux/cc_platform.h>
 #include <linux/mman.h>
 #include <linux/nodemask.h>
 #include <linux/initrd.h>
@@ -36,6 +37,7 @@

 #include <asm/boot.h>
 #include <asm/fixmap.h>
+#include <asm/hypervisor.h>
 #include <asm/kasan.h>
 #include <asm/kernel-pgtable.h>
 #include <asm/kvm_host.h>
@@ -414,6 +416,17 @@ void dump_mem_limit(void)
 	}
 }

+bool cc_platform_has(enum cc_attr attr)
+{
+	switch (attr) {
+	case CC_ATTR_MEM_ENCRYPT:
+		return is_realm_world() || is_protected_kvm_guest();
+	default:
+		return false;
+	}
+}
+EXPORT_SYMBOL_GPL(cc_platform_has);
+
 #ifdef CONFIG_EXECMEM
 static u64 module_direct_base __ro_after_init = 0;
 static u64 module_plt_base __ro_after_init = 0;
diff --git a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
index 4230b817a80b..297e6d6019b8 100644
--- a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
+++ b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
@@ -95,6 +95,11 @@ static int mmio_guard_ioremap_hook(phys_addr_t phys, size_t size,
 	return 0;
 }

+bool is_protected_kvm_guest(void)
+{
+	return !!pkvm_granule;
+}
+
 void pkvm_init_hyp_services(void)
 {
 	int i;
--
2.54.0.563.g4f69b47b94-goog


Thanks,
Mostafa
> 
> -aneesh

---

## [31] Jason Gunthorpe — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu, May 14, 2026 at 06:18:05PM +0530, Aneesh Kumar K.V wrote:
> > There is no problem with non-protected guests as they don't use memory
> > encryption, my initial thought was that th encrpyted/decrypted is

If I understood Mostafa's remarks I think different devices in the
guest need shared/decrypted and some don't? Ie a virtio hypervisor
device needs shared while a real PCI device doesn't? Is that right?

In CC terms that would be a mixture of T=0 and T=1 devices hardwired
and signaled by firwmare..

Ideally we'd have a flow where if the arch precreates a swiotlb pool
with special parameters this overrides all other decision making. Then
this series is about making CC NOT use that flow... ??

Jason

---

## [32] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Mostafa Saleh <smostafa@google.com> writes:

> On Thu, May 14, 2026 at 06:18:05PM +0530, Aneesh Kumar K.V wrote:
>> Mostafa Saleh <smostafa@google.com> writes:

Thanks, I can add this to the series once you complete the required testing.

>
> From d795b4c4ee2437587616b2b342e9996afe6d6680 Mon Sep 17 00:00:00 2001


-aneesh

---

## [33] Mostafa Saleh — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu, May 14, 2026 at 09:35:29AM -0300, Jason Gunthorpe wrote:
> > > How will pKVM signal what kind of memory the DMA needs then?
> > > 

I see that it is used only for dma-iommu and for PCI devices.
However, I think that should be a problem with other CCA solutions
with emulated devices as they are untrusted. As I'd expect they
would have virtio devices.

> 
> Then CC issue is more that the DMA API can't decrypt random passed in

Pools can be per-device also. A device can have mutiple pools with
different memory attrs, which then can be matched by the DMA code
at runtime, it's not as flexible, but removes some complexity from
the guest code.

> 
> > > If dma_capable() can fail, then swiotlb should know exactly what to do

I see, but that’s not part of this series, and probably would require
some rework so dma_capable() can return an error code (ERANGE, EPERM...)
so that caller can deal with that.

> 
> > While we can debate the aesthetics of the setup , this is

I am looking into converting pKVM to use the CC stuff, I replied with
a patch to Aneesh in this thread. However, I need to do more testing
and make sure there are not any unwanted consequences.

> 
> > We can address this by either adjusting this patch or by changing

I see that's because dma-iommu chooses the attrs for iommu_map().

In pKVM, dma_addr_t and IOPTE are the same for private and shared,
so nothing differs in that case.
We don’t expect pass-through devices to interact with shared
memory (T=0) at the moment.
However, I can see use cases for that, where the host and the guest
collaborate with device passthrough and require zero copy.

One other interesting case for device-passthrough is non-coherent
devices which then require private pools for bouncing.

Thanks,
Mostafa

> 
> Jason

---

## [34] Mostafa Saleh — 2026-05-14
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu, May 14, 2026 at 11:37:33AM -0300, Jason Gunthorpe wrote:
> On Thu, May 14, 2026 at 06:18:05PM +0530, Aneesh Kumar K.V wrote:
> > > There is no problem with non-protected guests as they don't use memory

In upstream, device passthrough is not supported, but that case is
supported in Android and we plan to upstream it (it currently
depends on the SMMUv3 series first)

> 
> In CC terms that would be a mixture of T=0 and T=1 devices hardwired

Yes, I believe that will be needed, we do this at android by a per-pool
property added in the device tree.

Thanks,
Mostafa

> 
> Jason

---

## [35] Jason Gunthorpe — 2026-05-15
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu, May 14, 2026 at 02:43:39PM +0000, Mostafa Saleh wrote:
> > That's a somewhat different problem, we have the dev->trusted stuff
> > that is supposed to deal with this kind of security. We need it for

Yes, any security solution with an out of TCB device should be using either
memory encryption so the kernel already bounces or this trusted stuff
and a force strict dma-iommu so the dma layer is careful.

This is more policy from userspace what devices they want in or out of
their TCB. Like you make accept the device into T=1 but then still
want to keep it out of your TCB with the vIOMMU, I can see good
arguments for something like that.

> > > While we can debate the aesthetics of the setup , this is
> > > the exisitng behaviour for Linux, which existed for years

Yeah, it is a nice patch and I think it will help reduce the
complexity if it aligns to CCA type stuff.

> > In a pkvm world it should be the same, the S2 table for the SMMU will
> > control what the device can access, and if the SMMU points to a

Long term the DMA API path through the dma-iommu will pass the
ATTR_CC_SHARED through to iommu_map so when the arch requires a
different IOPTE it can construct it.

> In pKVM, dma_addr_t and IOPTE are the same for private and shared,
> so nothing differs in that case.

Yes, so you don't have to worry.

> We don’t expect pass-through devices to interact with shared
> memory (T=0) at the moment.

Once you add the CC patch it becomes immediately possible though
because the user can allocate a CC shared DMA HEAP and feed that all
over the place.

> One other interesting case for device-passthrough is non-coherent
> devices which then require private pools for bouncing.

Why does shared/private matter for bouncing? Why do you need to bounce
at all? Do cmo's not work in pkvm guests?

Jason

---

## [36] Alexey Kardashevskiy — 2026-05-16
*Subject: Re: [PATCH v4 03/13] dma-pool: track decrypted atomic pools and
 select them via attrs*

On 12/5/26 19:03, Aneesh Kumar K.V (Arm) wrote:
> Teach the atomic DMA pool code to distinguish between encrypted and
> decrypted pools, and make pool allocation select the matching pool based


v3 of this just crashed here with dma_pool!=NULL but dma_pool->pool==NULL. continuing debugging... Thanks,


>   			continue;
> -		gen_pool_free(pool, (unsigned long)start, size);

---

## [37] Jiri Pirko — 2026-05-17
*Subject: Re: [PATCH v4 00/13] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Tue, May 12, 2026 at 11:03:55AM +0200, aneesh.kumar@kernel.org wrote:
>This series propagates DMA_ATTR_CC_SHARED through the dma-direct,
>dma-pool, and swiotlb paths so that encrypted and decrypted DMA buffers

FWIW, the patchset in general looks good to me. I tested this with my
system_cc_shared dmabuf flow, works flawlessly.

Thanks!

---

## [38] Alexey Kardashevskiy — 2026-05-18
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On 12/5/26 19:03, Aneesh Kumar K.V (Arm) wrote:
> Teach swiotlb to distinguish between encrypted and decrypted bounce
> buffer pools, and make allocation and mapping paths select a pool whose

here we know it is shared so ...


> -		page = dma_direct_alloc_swiotlb(dev, size);
> +		page = dma_direct_alloc_swiotlb(dev, size, attrs);

... is not this needed here
attrs |= DMA_ATTR_CC_SHARED;

?

and then the setup_page label below can do the right thing, which I tried, with enforcing io_tlb_default_mem.for_alloc=1, it works - accepted device can still do DMA to shared memory. Thanks,



>   			mark_mem_decrypt = false;
>   			goto setup_page;

---

## [39] Alexey Kardashevskiy — 2026-05-18
*Subject: Re: [PATCH v4 03/13] dma-pool: track decrypted atomic pools and
 select them via attrs*

On 16/5/26 22:53, Alexey Kardashevskiy wrote:
> On 12/5/26 19:03, Aneesh Kumar K.V (Arm) wrote:
>> Teach the atomic DMA pool code to distinguish between encrypted and


This clause could go to the else branch.


>>       if (ret)
>>           goto encrypt_mapping;


dma_direct_free:
   dma_free_from_pool (loop over pools) -> false
     [here was a crash which I fixed by "if (!dma_pool->pool) continue"]
   swiotlb_find_pool (loop again) -> false
     __dma_direct_free_pages
       swiotlb_free
         swiotlb_find_pool (loop again)
       dma_free_contiguous => done.

so that works but kinda hard to follow and there is some room for optimization. I do not normally have swiottlb when I test this and there is too many of this swiotlb stuff on the real direct dma mapping path imho. Thanks,
> 
>

---

## [40] Aneesh Kumar K.V — 2026-05-18
*Subject: Re: [PATCH v4 00/13] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Jiri Pirko <jiri@resnulli.us> writes:

> Tue, May 12, 2026 at 11:03:55AM +0200, aneesh.kumar@kernel.org wrote:
>>This series propagates DMA_ATTR_CC_SHARED through the dma-direct,
Thanks, Can I add

Tested-by: Jiri Pirko <jiri@resnulli.us>

-aneesh

---

## [41] Aneesh Kumar K.V — 2026-05-18
*Subject: Re: [PATCH v4 03/13] dma-pool: track decrypted atomic pools and
 select them via attrs*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 16/5/26 22:53, Alexey Kardashevskiy wrote:
>> On 12/5/26 19:03, Aneesh Kumar K.V (Arm) wrote:

...

>>> -static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
>>> +static int atomic_pool_expand(struct dma_gen_pool *dma_pool, size_t pool_size,

Can you clarify this better? 

>>>       if (ret)
>>>           goto encrypt_mapping;

...

>>>   bool dma_free_from_pool(struct device *dev, void *start, size_t size)
>>>   {

I will work on this in the next update. I can possibly drop the
swiotlb_find_pool from the swiotlb_free() path.

>> 
>> 


-aneesh

---

## [42] Jiri Pirko — 2026-05-18
*Subject: Re: [PATCH v4 00/13] dma-mapping: Use DMA_ATTR_CC_SHARED through
 direct, pool and swiotlb paths*

Mon, May 18, 2026 at 10:23:58AM +0200, aneesh.kumar@kernel.org wrote:
>Jiri Pirko <jiri@resnulli.us> writes:
>

Tested-by: Jiri Pirko <jiri@nvidia.com>

Thanks.

---

## [43] Christian Borntraeger — 2026-05-18
*Subject: Re: [PATCH v4 07/13] dma-direct: make dma_direct_map_phys() honor
 DMA_ATTR_CC_SHARED*

cc Halil, Matt, Jaehoon.
Can you have a look what this means for virtio on secure execution?

Am 12.05.26 um 11:04 schrieb Aneesh Kumar K.V (Arm):
> Teach dma_direct_map_phys() to select the DMA address encoding based on
> DMA_ATTR_CC_SHARED.

---

## [44] Mostafa Saleh — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Thu, May 14, 2026 at 08:13:25PM +0530, Aneesh Kumar K.V wrote:
> >> 
> >> What I meant was that we need a generic way to identify a pKVM guest, so

I am still running more tests, but looking more into it. Setting
force_dma_unencrypted() to true for pKVM guests is wrong, as the
guest shouldn’t try to decrypt arbitrary memory as it can include
sensitive information (for example in case of virtio sub-page
allocation) and should strictly rely on the restricted-dma-pool
for that.

However, with my patch and setting force_dma_unencrypted() to false
on top of this series, it fails on pKVM due to a missing shared
attribute as Alexey mentioned, as now SWIOTLB rejects non shared
attrs, so, the DMA-API has to pass it. With that, I can boot again:

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 5103a04df99f..b19aeec03f27 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -286,6 +286,8 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	}
 
 	if (is_swiotlb_for_alloc(dev)) {
+		attrs |= DMA_ATTR_CC_SHARED;
+
 		page = dma_direct_alloc_swiotlb(dev, size, attrs);
 		if (page) {
 			/*
@@ -449,6 +451,8 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 						  &cpu_addr, gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
+		attrs |= DMA_ATTR_CC_SHARED;
+
 		page = dma_direct_alloc_swiotlb(dev, size, attrs);
 		if (!page)
 			return NULL;
diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
index 4e35264ab6f8..8ee5bbf78cfb 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -92,6 +92,7 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 		if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
 			return DMA_MAPPING_ERROR;
 
+		attrs |= DMA_ATTR_CC_SHARED;
 		return swiotlb_map(dev, phys, size, dir, attrs);
 	}

---

## [45] Mostafa Saleh — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Fri, May 15, 2026 at 07:51:13PM -0300, Jason Gunthorpe wrote:
> On Thu, May 14, 2026 at 02:43:39PM +0000, Mostafa Saleh wrote:
> > > That's a somewhat different problem, we have the dev->trusted stuff

At the moment, in iommu_dma_map_phys(), if a non coherent device
tries to map an unaligned address or size it will be bounced.
In pKVM, dma-iommu is used for assigned devices which operate on
private memory, so bouncing that through the SWIOTLB would leak
information from the guest as the SWIOTLB is decrypted.
In that case, the device needs a pool which remains private.

Thanks,
Mostafa

> 
> Jason

---

## [46] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Mostafa Saleh <smostafa@google.com> writes:

> On Thu, May 14, 2026 at 08:13:25PM +0530, Aneesh Kumar K.V wrote:
>> >> 

How about the below?

modified   kernel/dma/direct.c
@@ -278,6 +278,10 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	}
 
 	if (is_swiotlb_for_alloc(dev)) {
+
+		if (dev->dma_io_tlb_mem->unencrypted)
+			attrs |= DMA_ATTR_CC_SHARED;
+
 		page = dma_direct_alloc_swiotlb(dev, size, attrs);
 		if (page) {
 			/*
@@ -451,6 +455,10 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 						  &cpu_addr, gfp, attrs);
 
 	if (is_swiotlb_for_alloc(dev)) {
+
+		if (dev->dma_io_tlb_mem->unencrypted)
+			attrs |= DMA_ATTR_CC_SHARED;
+
 		page = dma_direct_alloc_swiotlb(dev, size, attrs);
 		if (!page)
 			return NULL;
modified   kernel/dma/direct.h
@@ -92,6 +92,9 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 		if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
 			return DMA_MAPPING_ERROR;
 
+		if (dev->dma_io_tlb_mem->unencrypted)
+			attrs |= DMA_ATTR_CC_SHARED;
+
 		return swiotlb_map(dev, phys, size, dir, attrs);
 	}
 


>
>

That would be useful. I can then carry the patch as a dependent change,
which can also be merged separately

>
> Re force_dma_unencrypted(), I am looking into a safe way to use it

---

## [47] Jason Gunthorpe — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 11:04:37AM +0000, Mostafa Saleh wrote:
> On Thu, May 14, 2026 at 08:13:25PM +0530, Aneesh Kumar K.V wrote:
> > >> 

??

Where does force_dma_unencrypted() cause arbitary memory passed into
the DMA API to be decrypted? That should never happen???

Jason

---

## [48] Jason Gunthorpe — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 11:06:52AM +0000, Mostafa Saleh wrote:

> > > One other interesting case for device-passthrough is non-coherent
> > > devices which then require private pools for bouncing.

Sure, that's fine.

> In pKVM, dma-iommu is used for assigned devices which operate on
> private memory, so bouncing that through the SWIOTLB would leak

Yes, a device that can do private access should not be using a shared
SWIOTLB, that should be part of the selection logic inside the SWIOTLB
stuff..

Jason

---

## [49] Mostafa Saleh — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 10:29:11AM -0300, Jason Gunthorpe wrote:
> On Tue, May 19, 2026 at 11:04:37AM +0000, Mostafa Saleh wrote:
> > On Thu, May 14, 2026 at 08:13:25PM +0530, Aneesh Kumar K.V wrote:

Sorry, maybe arbitrary is not the right expression again :)
I mean that, with emulated devices that use the DMA-API under pKVM,
they will map memory coming from other layers (VFS, net) through
vitrio-block, virtio-net... These can be smaller than a page, and
using force_dma_unencrypted() will share the whole page.
And as discussed, that leaks sensitive information to the untrusted
host.
I am currently investigating passing iova/phys/size
to force_dma_unencrypted() and then we can share pages inplace only
if possible without leaking extra information.
I am trying to get some performance results first. But the tricky part
is to get the semantics right, I believe in that case those devices
shouldn’t use restricted-dma-pools as those should always force
bouncing. Instead bouncing happens through the default SWIOTLB pool,
if not possible to decrypt in place.

Thanks,
Mostafa

> 
> Jason

---

## [50] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Mostafa Saleh <smostafa@google.com> writes:

> On Tue, May 19, 2026 at 10:29:11AM -0300, Jason Gunthorpe wrote:
>> On Tue, May 19, 2026 at 11:04:37AM +0000, Mostafa Saleh wrote:

Don't we PAGE_ALIGN these requests?

dma_direct_alloc
	size = PAGE_ALIGN(size);

iommu_dma_alloc_pages
	size_t alloc_size = PAGE_ALIGN(size);



> using force_dma_unencrypted() will share the whole page.
> And as discussed, that leaks sensitive information to the untrusted

-aneesh

---

## [51] Mostafa Saleh — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 07:30:16PM +0530, Aneesh Kumar K.V wrote:
> Mostafa Saleh <smostafa@google.com> writes:
> 

For allocation, yes, and that's fine because we bring memory from
the pool.
But not for mapping, as dma_direct_map_phys(), where the memory is
allocated from the driver or other parts in the kernel and the page
may be shared with other kernel components.

Thanks,
Mostafa

> 
> > using force_dma_unencrypted() will share the whole page.

---

## [52] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Mostafa Saleh <smostafa@google.com> writes:

> On Tue, May 19, 2026 at 07:30:16PM +0530, Aneesh Kumar K.V wrote:
>> Mostafa Saleh <smostafa@google.com> writes:

But if we are using restricted-dma-pool, we also have:

mem->force_bounce = true;
mem->for_alloc = true;

So, will we use the swiotlb buffers for mapping and copy only the shared
content into those swiotlb buffers?

-aneesh

---

## [53] Mostafa Saleh — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 07:47:48PM +0530, Aneesh Kumar K.V wrote:
> Mostafa Saleh <smostafa@google.com> writes:
> 

True, that's why under pKVM, force_dma_unencrypted() should never
cause any memory to be decrypted and so we set it to false.
As in case of any bugs, the guest does not leak any information,
similar to what just happened initially here due to missing attrs.

However, as I mentioned to Jason, I think with some tweaks to
force_dma_unencrypted() we can make it work under pKVM for aligned
memory which eliminates some of the bouncing.
I am currently investigating that.

Thanks,
Mostafa

> 
> -aneesh

---

## [54] Jason Gunthorpe — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 01:41:42PM +0000, Mostafa Saleh wrote:
> On Tue, May 19, 2026 at 10:29:11AM -0300, Jason Gunthorpe wrote:
> > On Tue, May 19, 2026 at 11:04:37AM +0000, Mostafa Saleh wrote:

force_dma_unencrypted() should only trigger swiotlb and that never
memcpy's more than necessary?

Where does it do otherwise? That sounds like a bug?

Jason

---

## [55] Jason Gunthorpe — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 02:27:54PM +0000, Mostafa Saleh wrote:
> However, as I mentioned to Jason, I think with some tweaks to
> force_dma_unencrypted() we can make it work under pKVM for aligned

force_dma_unencrypted() literally means that memory passed into the
DMA API *without* DMA_ATTR_CC_SHARED cannot be DMA'd from.

It should not mean anything else. The DMA API should never decrypt
passed in memory. You always have to bounce.

Jason

---

## [56] Mostafa Saleh — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 11:35:29AM -0300, Jason Gunthorpe wrote:
> On Tue, May 19, 2026 at 01:41:42PM +0000, Mostafa Saleh wrote:
> > On Tue, May 19, 2026 at 10:29:11AM -0300, Jason Gunthorpe wrote:

Agh, I got confused and thought that it can be triggered from dma_map()
too. I need to figure out why that made pKVM guests boot with broken
restricted-dma-pool then.

However, it should not alway use SWIOTLB? It can trigger decryption for
any memory returned from __dma_direct_alloc_pages() which can come
from alloc_pages_node().

Thanks,
Mostafa


> 
> Jason

---

## [57] Jason Gunthorpe — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 02:45:35PM +0000, Mostafa Saleh wrote:
> However, it should not alway use SWIOTLB? It can trigger decryption for
> any memory returned from __dma_direct_alloc_pages() which can come

The alloc coherent flow is seperate and different, these are not pages
'passed into the DMA API' but pages fully allocated internally and
owned by it.

Yes, it should cause decrypted *allocation*.

Jason

---

## [58] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> Mostafa Saleh <smostafa@google.com> writes:
>

if we get force_dma_unencrypted(dev) correct, we won't need the above.

for dma_direct_alloc and dma_direct_alloc_pages() we have

	if (force_dma_unencrypted(dev))
		attrs |= DMA_ATTR_CC_SHARED;


for dma_direct_map_phys(), if we have swiotlb bouncing forced,

swiotlb_tbl_map_single():

	if ((attrs & DMA_ATTR_CC_SHARED) || force_dma_unencrypted(dev))
		require_decrypted = true;

-aneesh

---

## [59] Jason Gunthorpe — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 08:37:54PM +0530, Aneesh Kumar K.V wrote:

> if we get force_dma_unencrypted(dev) correct, we won't need the above.
> 

IMHO I really do prefer the DMA_ATTR_CC_SHARED flows closer to the
thing that did the decryption. While the above is possibly sound it is
very obtuse to be guessing what kind of memory swiotlb decided to
return..

Can we pass a pointer to the attrs into the swiotlb stuff and it can
update it based on the kind of memory it has allocated?

Jason

---

## [60] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Tue, May 19, 2026 at 08:37:54PM +0530, Aneesh Kumar K.V wrote:
>

Yes, that also resulted in simpler and cleaner code.

swiotlb_tbl_map_single
	/*
	 * If the physical address is encrypted but the device requires
	 * decrypted DMA, use a decrypted io_tlb_mem and update the
	 * attributes so the caller knows that a decrypted io_tlb_mem
	 * was used.
	 */
	if (!(*attrs & DMA_ATTR_CC_SHARED) && force_dma_unencrypted(dev))
		*attrs |= DMA_ATTR_CC_SHARED;

	if (mem->unencrypted != !!(*attrs & DMA_ATTR_CC_SHARED))
		return (phys_addr_t)DMA_MAPPING_ERROR;

and

@@ -1640,19 +1654,14 @@ dma_addr_t swiotlb_map(struct device *dev, phys_addr_t paddr, size_t size,
 
 	trace_swiotlb_bounced(dev, phys_to_dma(dev, paddr), size);
 
-	swiotlb_addr = swiotlb_tbl_map_single(dev, paddr, size, 0, dir, attrs);
+	swiotlb_addr = swiotlb_tbl_map_single(dev, paddr, size, 0, dir, &attrs);
 	if (swiotlb_addr == (phys_addr_t)DMA_MAPPING_ERROR)
 		return DMA_MAPPING_ERROR;
 
-	/*
-	 * Use the allocated io_tlb_mem encryption type to determine dma addr.
-	 */
-	if (dev->dma_io_tlb_mem->unencrypted) {
+	if (attrs & DMA_ATTR_CC_SHARED)
 		dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
-		attrs |= DMA_ATTR_CC_SHARED;
-	} else {
+	else
 		dma_addr = phys_to_dma_encrypted(dev, swiotlb_addr);
-	}
 
 	if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs))) {
 		__swiotlb_tbl_unmap_single(dev, swiotlb_addr, size, dir,

---

## [61] Jason Gunthorpe — 2026-05-19
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 19, 2026 at 09:35:30PM +0530, Aneesh Kumar K.V wrote:
> Yes, that also resulted in simpler and cleaner code.
> 

Yeah, exactly that is so much clearer now that the mem->unecrypted is
tied directly.

That logic is reversed though, the incoming ATTR_CC doesn't matter for
swiotlb, that is just the source of the memcpy.

/* swiotlb pool is incorrect for this device */
if (mem->unencrypted != force_dma_unencrypted(dev))
    return (phys_addr_t)DMA_MAPPING_ERROR;

/* Force attrs to match the kind of memory in the pool */
if (mem->unencrypted)
     *attrs |= DMA_ATTR_CC_SHARED;
else
     *attrs &= ~DMA_ATTR_CC_SHARED;


Attrs should be forced to whatever memory swiotlb selected.

Jason

---

## [62] Aneesh Kumar K.V — 2026-05-20
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Tue, May 19, 2026 at 09:35:30PM +0530, Aneesh Kumar K.V wrote:
>> Yes, that also resulted in simpler and cleaner code.

But that will not handle a T=1 device that wants to use swiotlb to
bounce unencrypted memory. That is:

force_dma_unencrypted(dev) == 0  /* T=1 device */
attrs = DMA_ATTR_CC_SHARED;

In that case, it should use an unencrypted io_tlb_mem:
mem->unencrypted == 1

-aneesh

---

## [63] Jason Gunthorpe — 2026-05-20
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Wed, May 20, 2026 at 09:27:27AM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

No! The DMA_ATTR_CC_SHARED only states the nature of the source
memory, the DMA transfer will always happen under T=1

It is perfectly fine to memcpy from shared to private and do a T=1 DMA
from the private memory if we have to bounce.

Jason

---

## [64] Aneesh Kumar K.V — 2026-05-21
*Subject: Re: [PATCH v4 13/13] x86/amd-gart: preserve the direct DMA address
 until GART mapping succeeds*

"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> writes:

> gart_alloc_coherent() first allocates memory through dma_direct_alloc(),
> which returns a direct-mapped DMA address in dma_addr. When force_iommu is

This needs corresponding changes on the gart_free_coherent() side as well.

https://sashiko.dev/#/patchset/20260512090408.794195-1-aneesh.kumar%40kernel.org?part=13

I will avoid making that change as part of this series, since I assume
it would require specific testing.

-aneesh

---

## [65] Aneesh Kumar K.V — 2026-05-21
*Subject: Re: [PATCH v4 07/13] dma-direct: make dma_direct_map_phys() honor
 DMA_ATTR_CC_SHARED*

"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> writes:

> diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
> index e05dc7649366..4e35264ab6f8 100644

I guess we need this change on top of the above

modified   kernel/dma/direct.h
@@ -88,6 +88,13 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
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
 		if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
 			return DMA_MAPPING_ERROR;

---

## [66] Mostafa Saleh — 2026-05-21
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

On Tue, May 12, 2026 at 10:05 AM Aneesh Kumar K.V (Arm)
<aneesh.kumar@kernel.org> wrote:
> @@ -1411,6 +1436,16 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
>         if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))

I don't think swiotlb needs to know about force_dma_unencrypted(), the
dma/direct caller should have all the information to pass the
appropriate flags.

Thanks.
Mostafa

> +               require_decrypted = true;
> +

---

## [67] Aneesh Kumar K.V — 2026-05-21
*Subject: Re: [PATCH v4 04/13] dma: swiotlb: track pool encryption state and
 honor DMA_ATTR_CC_SHARED*

Mostafa Saleh <smostafa@google.com> writes:

> On Tue, May 12, 2026 at 10:05 AM Aneesh Kumar K.V (Arm)
> <aneesh.kumar@kernel.org> wrote:

Based on other email threads, this is now updated to

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

---
