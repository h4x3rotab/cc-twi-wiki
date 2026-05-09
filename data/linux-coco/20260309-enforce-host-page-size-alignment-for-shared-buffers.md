---
title: 'Enforce host page-size alignment for shared buffers'
date: 2026-03-09
last_reply: 2026-03-23
message_count: 10
participants: ['Aneesh Kumar K.V (Arm)', 'Suzuki K Poulose', 'kernel test robot']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-03-09

Hi all,

This patch series addresses alignment requirements for buffers shared between
private-memory guests and the host.

When running private-memory guests, the guest kernel must apply additional
constraints when allocating buffers that are shared with the hypervisor. These
shared buffers are also accessed by the host kernel and therefore must be
aligned to the host’s page size.

Architectures such as Arm can tolerate realm physical address space PFNs being
mapped as shared memory, as incorrect accesses are detected and reported as GPC
faults. However, relying on this mechanism alone is unsafe and can still lead to
kernel crashes.

This is particularly likely when guest_memfd allocations are mmapped and
accessed from userspace. Once exposed to userspace, it is not possible to
guarantee that applications will only access the intended 4K shared region
rather than the full 64K page mapped into their address space. Such userspace
addresses may also be passed back into the kernel and accessed via the linear
map, potentially resulting in a GPC fault and a kernel crash.

To address this, the series introduces a new helpers,
mem_decrypt_granule_size() and mem_decrypt_align(), which allows callers to
enforce the required alignment for shared buffers.


Changes from v2:
* Rebase to latest kernel
* Consider swiotlb always decrypted and don't align when allocating from swiotlb.

Changes from v1:
* Rename the helper to mem_encrypt_align
* Improve the commit message
* Handle DMA allocations from contiguous memory
* Handle DMA allocations from the pool
* swiotlb is still considered unencrypted. Support for an encrypted swiotlb pool
  is left as TODO and is independent of this series.


Aneesh Kumar K.V (Arm) (3):
  dma-direct: swiotlb: handle swiotlb alloc/free outside
    __dma_direct_alloc_pages
  swiotlb: dma: its: Enforce host page-size alignment for shared buffers
  coco: guest: arm64: Add Realm Host Interface and hostconf RHI

 arch/arm64/include/asm/mem_encrypt.h |  3 ++
 arch/arm64/include/asm/rhi.h         | 24 ++++++++++++
 arch/arm64/include/asm/rsi.h         |  2 +
 arch/arm64/include/asm/rsi_cmds.h    | 10 +++++
 arch/arm64/include/asm/rsi_smc.h     |  7 ++++
 arch/arm64/kernel/Makefile           |  2 +-
 arch/arm64/kernel/rhi.c              | 53 +++++++++++++++++++++++++
 arch/arm64/kernel/rsi.c              | 13 +++++++
 arch/arm64/mm/mem_encrypt.c          | 27 +++++++++++--
 drivers/irqchip/irq-gic-v3-its.c     | 20 ++++++----
 include/linux/mem_encrypt.h          | 12 ++++++
 kernel/dma/contiguous.c              | 10 +++++
 kernel/dma/direct.c                  | 58 ++++++++++++++++++++++++----
 kernel/dma/pool.c                    |  4 +-
 kernel/dma/swiotlb.c                 | 21 ++++++----
 15 files changed, 237 insertions(+), 29 deletions(-)
 create mode 100644 arch/arm64/include/asm/rhi.h
 create mode 100644 arch/arm64/kernel/rhi.c

---

## [2] Aneesh Kumar K.V (Arm) — 2026-03-09
*Subject: [PATCH v3 1/3] dma-direct: swiotlb: handle swiotlb alloc/free outside __dma_direct_alloc_pages*

Move swiotlb allocation out of __dma_direct_alloc_pages() and handle it in
dma_direct_alloc() / dma_direct_alloc_pages().

This is needed for follow-up changes that align shared decrypted buffers to
hypervisor page size. swiotlb pool memory is decrypted as a whole and does
not need per-allocation alignment handling.

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

Cc: Marc Zyngier <maz@kernel.org>
Cc: Thomas Gleixner <tglx@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Marek Szyprowski <m.szyprowski@samsung.com>
Cc: Robin Murphy <robin.murphy@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 44 +++++++++++++++++++++++++++++++++++++-------
 1 file changed, 37 insertions(+), 7 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 8f43a930716d..c2a43e4ef902 100644
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

## [3] Aneesh Kumar K.V (Arm) — 2026-03-09
*Subject: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers*

When running private-memory guests, the guest kernel must apply additional
constraints when allocating buffers that are shared with the hypervisor.

These shared buffers are also accessed by the host kernel and therefore
must be aligned to the host’s page size, and have a size that is a multiple
of the host page size.

On non-secure hosts, set_guest_memory_attributes() tracks memory at the
host PAGE_SIZE granularity. This creates a mismatch when the guest applies
attributes at 4K boundaries while the host uses 64K pages. In such cases,
set_guest_memory_attributes() call returns -EINVAL, preventing the
conversion of memory regions from private to shared.

Architectures such as Arm can tolerate realm physical address space
(protected memory) PFNs being mapped as shared memory, as incorrect
accesses are detected and reported as GPC faults. However, relying on this
mechanism is unsafe and can still lead to kernel crashes.

This is particularly likely when guest_memfd allocations are mmapped and
accessed from userspace. Once exposed to userspace, we cannot guarantee
that applications will only access the intended 4K shared region rather
than the full 64K page mapped into their address space. Such userspace
addresses may also be passed back into the kernel and accessed via the
linear map, resulting in a GPC fault and a kernel crash.

With CCA, although Stage-2 mappings managed by the RMM still operate at a
4K granularity, shared pages must nonetheless be aligned to the
host-managed page size and sized as whole host pages to avoid the issues
described above.

Introduce a new helper, mem_decrypt_align(), to allow callers to enforce
the required alignment and size constraints for shared buffers.

The architecture-specific implementation of mem_decrypt_align() will be
provided in a follow-up patch.

Note on restricted-dma-pool:
rmem_swiotlb_device_init() uses reserved-memory regions described by
firmware. Those regions are not changed in-kernel to satisfy host granule
alignment. This is intentional: we do not expect restricted-dma-pool
allocations to be used with CCA. If restricted-dma-pool is intended for CCA
shared use, firmware must provide base/size aligned to the host IPA-change
granule.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Thomas Gleixner <tglx@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Marek Szyprowski <m.szyprowski@samsung.com>
Cc: Robin Murphy <robin.murphy@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/mm/mem_encrypt.c      | 19 +++++++++++++++----
 drivers/irqchip/irq-gic-v3-its.c | 20 +++++++++++++-------
 include/linux/mem_encrypt.h      | 12 ++++++++++++
 kernel/dma/contiguous.c          | 10 ++++++++++
 kernel/dma/direct.c              | 16 ++++++++++++++--
 kernel/dma/pool.c                |  4 +++-
 kernel/dma/swiotlb.c             | 21 +++++++++++++--------
 7 files changed, 80 insertions(+), 22 deletions(-)

diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
index ee3c0ab04384..38c62c9e4e74 100644
--- a/arch/arm64/mm/mem_encrypt.c
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -17,8 +17,7 @@
 #include <linux/compiler.h>
 #include <linux/err.h>
 #include <linux/mm.h>
-
-#include <asm/mem_encrypt.h>
+#include <linux/mem_encrypt.h>
 
 static const struct arm64_mem_crypt_ops *crypt_ops;
 
@@ -33,18 +32,30 @@ int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops)
 
 int set_memory_encrypted(unsigned long addr, int numpages)
 {
-	if (likely(!crypt_ops) || WARN_ON(!PAGE_ALIGNED(addr)))
+	if (likely(!crypt_ops))
 		return 0;
 
+	if (WARN_ON(!IS_ALIGNED(addr, mem_decrypt_granule_size())))
+		return -EINVAL;
+
+	if (WARN_ON(!IS_ALIGNED(numpages << PAGE_SHIFT, mem_decrypt_granule_size())))
+		return -EINVAL;
+
 	return crypt_ops->encrypt(addr, numpages);
 }
 EXPORT_SYMBOL_GPL(set_memory_encrypted);
 
 int set_memory_decrypted(unsigned long addr, int numpages)
 {
-	if (likely(!crypt_ops) || WARN_ON(!PAGE_ALIGNED(addr)))
+	if (likely(!crypt_ops))
 		return 0;
 
+	if (WARN_ON(!IS_ALIGNED(addr, mem_decrypt_granule_size())))
+		return -EINVAL;
+
+	if (WARN_ON(!IS_ALIGNED(numpages << PAGE_SHIFT, mem_decrypt_granule_size())))
+		return -EINVAL;
+
 	return crypt_ops->decrypt(addr, numpages);
 }
 EXPORT_SYMBOL_GPL(set_memory_decrypted);
diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 291d7668cc8d..239d7e3bc16f 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -213,16 +213,17 @@ static gfp_t gfp_flags_quirk;
 static struct page *its_alloc_pages_node(int node, gfp_t gfp,
 					 unsigned int order)
 {
+	unsigned int new_order;
 	struct page *page;
 	int ret = 0;
 
-	page = alloc_pages_node(node, gfp | gfp_flags_quirk, order);
-
+	new_order = get_order(mem_decrypt_align((PAGE_SIZE << order)));
+	page = alloc_pages_node(node, gfp | gfp_flags_quirk, new_order);
 	if (!page)
 		return NULL;
 
 	ret = set_memory_decrypted((unsigned long)page_address(page),
-				   1 << order);
+				   1 << new_order);
 	/*
 	 * If set_memory_decrypted() fails then we don't know what state the
 	 * page is in, so we can't free it. Instead we leak it.
@@ -241,13 +242,16 @@ static struct page *its_alloc_pages(gfp_t gfp, unsigned int order)
 
 static void its_free_pages(void *addr, unsigned int order)
 {
+	int new_order;
+
+	new_order = get_order(mem_decrypt_align((PAGE_SIZE << order)));
 	/*
 	 * If the memory cannot be encrypted again then we must leak the pages.
 	 * set_memory_encrypted() will already have WARNed.
 	 */
-	if (set_memory_encrypted((unsigned long)addr, 1 << order))
+	if (set_memory_encrypted((unsigned long)addr, 1 << new_order))
 		return;
-	free_pages((unsigned long)addr, order);
+	free_pages((unsigned long)addr, new_order);
 }
 
 static struct gen_pool *itt_pool;
@@ -268,11 +272,13 @@ static void *itt_alloc_pool(int node, int size)
 		if (addr)
 			break;
 
-		page = its_alloc_pages_node(node, GFP_KERNEL | __GFP_ZERO, 0);
+		page = its_alloc_pages_node(node, GFP_KERNEL | __GFP_ZERO,
+					    get_order(mem_decrypt_granule_size()));
 		if (!page)
 			break;
 
-		gen_pool_add(itt_pool, (unsigned long)page_address(page), PAGE_SIZE, node);
+		gen_pool_add(itt_pool, (unsigned long)page_address(page),
+			     mem_decrypt_granule_size(), node);
 	} while (!addr);
 
 	return (void *)addr;
diff --git a/include/linux/mem_encrypt.h b/include/linux/mem_encrypt.h
index 07584c5e36fb..6cf39845058e 100644
--- a/include/linux/mem_encrypt.h
+++ b/include/linux/mem_encrypt.h
@@ -54,6 +54,18 @@
 #define dma_addr_canonical(x)		(x)
 #endif
 
+#ifndef mem_decrypt_granule_size
+static inline size_t mem_decrypt_granule_size(void)
+{
+	return PAGE_SIZE;
+}
+#endif
+
+static inline size_t mem_decrypt_align(size_t size)
+{
+	return ALIGN(size, mem_decrypt_granule_size());
+}
+
 #endif	/* __ASSEMBLY__ */
 
 #endif	/* __MEM_ENCRYPT_H__ */
diff --git a/kernel/dma/contiguous.c b/kernel/dma/contiguous.c
index c56004d314dc..2b7ff68be0c4 100644
--- a/kernel/dma/contiguous.c
+++ b/kernel/dma/contiguous.c
@@ -46,6 +46,7 @@
 #include <linux/dma-map-ops.h>
 #include <linux/cma.h>
 #include <linux/nospec.h>
+#include <linux/dma-direct.h>
 
 #ifdef CONFIG_CMA_SIZE_MBYTES
 #define CMA_SIZE_MBYTES CONFIG_CMA_SIZE_MBYTES
@@ -374,6 +375,15 @@ struct page *dma_alloc_contiguous(struct device *dev, size_t size, gfp_t gfp)
 #ifdef CONFIG_DMA_NUMA_CMA
 	int nid = dev_to_node(dev);
 #endif
+	/*
+	 * for untrusted device, we require the dma buffers to be aligned to
+	 * the mem_decrypt_align(PAGE_SIZE) so that we can set the memory
+	 * attributes correctly.
+	 */
+	if (force_dma_unencrypted(dev)) {
+		if (get_order(mem_decrypt_granule_size()) > CONFIG_CMA_ALIGNMENT)
+			return NULL;
+	}
 
 	/* CMA can be used only in the context which permits sleeping */
 	if (!gfpflags_allow_blocking(gfp))
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index c2a43e4ef902..34eccd047e9b 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -257,6 +257,9 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		return NULL;
 	}
 
+	if (force_dma_unencrypted(dev))
+		size = mem_decrypt_align(size);
+
 	/* we always manually zero the memory once we are done */
 	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, true);
 	if (!page)
@@ -350,6 +353,9 @@ void dma_direct_free(struct device *dev, size_t size,
 	if (swiotlb_find_pool(dev, dma_to_phys(dev, dma_addr)))
 		mark_mem_encrypted = false;
 
+	if (mark_mem_encrypted && force_dma_unencrypted(dev))
+		size = mem_decrypt_align(size);
+
 	if (is_vmalloc_addr(cpu_addr)) {
 		vunmap(cpu_addr);
 	} else {
@@ -384,6 +390,9 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 		goto setup_page;
 	}
 
+	if (force_dma_unencrypted(dev))
+		size = mem_decrypt_align(size);
+
 	page = __dma_direct_alloc_pages(dev, size, gfp, false);
 	if (!page)
 		return NULL;
@@ -414,8 +423,11 @@ void dma_direct_free_pages(struct device *dev, size_t size,
 	if (swiotlb_find_pool(dev, page_to_phys(page)))
 		mark_mem_encrypted = false;
 
-	if (mark_mem_encrypted && dma_set_encrypted(dev, vaddr, size))
-		return;
+	if (mark_mem_encrypted && force_dma_unencrypted(dev)) {
+		size = mem_decrypt_align(size);
+		if (dma_set_encrypted(dev, vaddr, size))
+			return;
+	}
 	__dma_direct_free_pages(dev, page, size);
 }
 
diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index 2b2fbb709242..b5f10ba3e855 100644
--- a/kernel/dma/pool.c
+++ b/kernel/dma/pool.c
@@ -83,7 +83,9 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 	struct page *page = NULL;
 	void *addr;
 	int ret = -ENOMEM;
+	unsigned int min_encrypt_order = get_order(mem_decrypt_granule_size());
 
+	pool_size = mem_decrypt_align(pool_size);
 	/* Cannot allocate larger than MAX_PAGE_ORDER */
 	order = min(get_order(pool_size), MAX_PAGE_ORDER);
 
@@ -94,7 +96,7 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 							 order, false);
 		if (!page)
 			page = alloc_pages(gfp | __GFP_NOWARN, order);
-	} while (!page && order-- > 0);
+	} while (!page && order-- > min_encrypt_order);
 	if (!page)
 		goto out;
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index d8e6f1d889d5..a9e6e4775ec6 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -260,7 +260,7 @@ void __init swiotlb_update_mem_attributes(void)
 
 	if (!mem->nslabs || mem->late_alloc)
 		return;
-	bytes = PAGE_ALIGN(mem->nslabs << IO_TLB_SHIFT);
+	bytes = mem_decrypt_align(mem->nslabs << IO_TLB_SHIFT);
 	set_memory_decrypted((unsigned long)mem->vaddr, bytes >> PAGE_SHIFT);
 }
 
@@ -317,8 +317,8 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 		unsigned int flags,
 		int (*remap)(void *tlb, unsigned long nslabs))
 {
-	size_t bytes = PAGE_ALIGN(nslabs << IO_TLB_SHIFT);
 	void *tlb;
+	size_t bytes = mem_decrypt_align(nslabs << IO_TLB_SHIFT);
 
 	/*
 	 * By default allocate the bounce buffer memory from low memory, but
@@ -326,9 +326,9 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 	 * memory encryption.
 	 */
 	if (flags & SWIOTLB_ANY)
-		tlb = memblock_alloc(bytes, PAGE_SIZE);
+		tlb = memblock_alloc(bytes, mem_decrypt_granule_size());
 	else
-		tlb = memblock_alloc_low(bytes, PAGE_SIZE);
+		tlb = memblock_alloc_low(bytes, mem_decrypt_granule_size());
 
 	if (!tlb) {
 		pr_warn("%s: Failed to allocate %zu bytes tlb structure\n",
@@ -337,7 +337,7 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 	}
 
 	if (remap && remap(tlb, nslabs) < 0) {
-		memblock_free(tlb, PAGE_ALIGN(bytes));
+		memblock_free(tlb, bytes);
 		pr_warn("%s: Failed to remap %zu bytes\n", __func__, bytes);
 		return NULL;
 	}
@@ -459,7 +459,7 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 		swiotlb_adjust_nareas(num_possible_cpus());
 
 retry:
-	order = get_order(nslabs << IO_TLB_SHIFT);
+	order = get_order(mem_decrypt_align(nslabs << IO_TLB_SHIFT));
 	nslabs = SLABS_PER_PAGE << order;
 
 	while ((SLABS_PER_PAGE << order) > IO_TLB_MIN_SLABS) {
@@ -468,6 +468,8 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 		if (vstart)
 			break;
 		order--;
+		if (order < get_order(mem_decrypt_granule_size()))
+			break;
 		nslabs = SLABS_PER_PAGE << order;
 		retried = true;
 	}
@@ -535,7 +537,7 @@ void __init swiotlb_exit(void)
 
 	pr_info("tearing down default memory pool\n");
 	tbl_vaddr = (unsigned long)phys_to_virt(mem->start);
-	tbl_size = PAGE_ALIGN(mem->end - mem->start);
+	tbl_size = mem_decrypt_align(mem->end - mem->start);
 	slots_size = PAGE_ALIGN(array_size(sizeof(*mem->slots), mem->nslabs));
 
 	set_memory_encrypted(tbl_vaddr, tbl_size >> PAGE_SHIFT);
@@ -571,11 +573,13 @@ void __init swiotlb_exit(void)
  */
 static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes, u64 phys_limit)
 {
-	unsigned int order = get_order(bytes);
+	unsigned int order;
 	struct page *page;
 	phys_addr_t paddr;
 	void *vaddr;
 
+	bytes = mem_decrypt_align(bytes);
+	order = get_order(bytes);
 	page = alloc_pages(gfp, order);
 	if (!page)
 		return NULL;
@@ -658,6 +662,7 @@ static void swiotlb_free_tlb(void *vaddr, size_t bytes)
 	    dma_free_from_pool(NULL, vaddr, bytes))
 		return;
 
+	bytes = mem_decrypt_align(bytes);
 	/* Intentional leak if pages cannot be encrypted again. */
 	if (!set_memory_encrypted((unsigned long)vaddr, PFN_UP(bytes)))
 		__free_pages(virt_to_page(vaddr), get_order(bytes));

---

## [4] Aneesh Kumar K.V (Arm) — 2026-03-09
*Subject: [PATCH v3 3/3] coco: guest: arm64: Add Realm Host Interface and hostconf RHI*

- describe the Realm Host Interface SMC IDs and result codes in a new
  asm/rhi.h header
- expose struct rsi_host_call plus an rsi_host_call() helper so we can
  invoke SMC_RSI_HOST_CALL from C code
 - add RHI hostconf SMC IDs and helper to query version, features, and IPA
   change alignment
 - derive the realm hypervisor page size during init and abort realm setup
   on invalid alignment

This provides the host page-size discovery needed by previous patch that
align shared buffer allocation/decryption to host requirements.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Thomas Gleixner <tglx@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Marek Szyprowski <m.szyprowski@samsung.com>
Cc: Robin Murphy <robin.murphy@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  3 ++
 arch/arm64/include/asm/rhi.h         | 24 +++++++++++++
 arch/arm64/include/asm/rsi.h         |  2 ++
 arch/arm64/include/asm/rsi_cmds.h    | 10 ++++++
 arch/arm64/include/asm/rsi_smc.h     |  7 ++++
 arch/arm64/kernel/Makefile           |  2 +-
 arch/arm64/kernel/rhi.c              | 53 ++++++++++++++++++++++++++++
 arch/arm64/kernel/rsi.c              | 13 +++++++
 arch/arm64/mm/mem_encrypt.c          |  8 +++++
 9 files changed, 121 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/rhi.h
 create mode 100644 arch/arm64/kernel/rhi.c

diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index 314b2b52025f..5541911eb028 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -16,6 +16,9 @@ int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops);
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
 
+#define mem_decrypt_granule_size mem_decrypt_granule_size
+size_t mem_decrypt_granule_size(void);
+
 int realm_register_memory_enc_ops(void);
 
 static inline bool force_dma_unencrypted(struct device *dev)
diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
new file mode 100644
index 000000000000..0895dd92ea1d
--- /dev/null
+++ b/arch/arm64/include/asm/rhi.h
@@ -0,0 +1,24 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#ifndef __ASM_RHI_H_
+#define __ASM_RHI_H_
+
+#include <linux/types.h>
+
+#define SMC_RHI_CALL(func)				\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
+			   ARM_SMCCC_SMC_64,		\
+			   ARM_SMCCC_OWNER_STANDARD_HYP,\
+			   (func))
+
+unsigned long rhi_get_ipa_change_alignment(void);
+#define RHI_HOSTCONF_VER_1_0		0x10000
+#define RHI_HOSTCONF_VERSION		SMC_RHI_CALL(0x004E)
+
+#define __RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT BIT(0)
+#define RHI_HOSTCONF_FEATURES		SMC_RHI_CALL(0x004F)
+#define RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT	SMC_RHI_CALL(0x0050)
+#endif
diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index 88b50d660e85..ae54fb3b1429 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -67,4 +67,6 @@ static inline int rsi_set_memory_range_shared(phys_addr_t start,
 	return rsi_set_memory_range(start, end, RSI_RIPAS_EMPTY,
 				    RSI_CHANGE_DESTROYED);
 }
+
+unsigned long realm_get_hyp_pagesize(void);
 #endif /* __ASM_RSI_H_ */
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 2c8763876dfb..a341ce0eeda1 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -159,4 +159,14 @@ static inline unsigned long rsi_attestation_token_continue(phys_addr_t granule,
 	return res.a0;
 }
 
+static inline unsigned long rsi_host_call(struct rsi_host_call *rhi_call)
+{
+	phys_addr_t addr = virt_to_phys(rhi_call);
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_HOST_CALL, addr, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index e19253f96c94..9ee8b5c7612e 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -182,6 +182,13 @@ struct realm_config {
  */
 #define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
 
+struct rsi_host_call {
+	union {
+		u16 imm;
+		u64 padding0;
+	};
+	u64 gprs[31];
+} __aligned(0x100);
 /*
  * Make a Host call.
  *
diff --git a/arch/arm64/kernel/Makefile b/arch/arm64/kernel/Makefile
index 76f32e424065..fcb67f50ea89 100644
--- a/arch/arm64/kernel/Makefile
+++ b/arch/arm64/kernel/Makefile
@@ -34,7 +34,7 @@ obj-y			:= debug-monitors.o entry.o irq.o fpsimd.o		\
 			   cpufeature.o alternative.o cacheinfo.o		\
 			   smp.o smp_spin_table.o topology.o smccc-call.o	\
 			   syscall.o proton-pack.o idle.o patching.o pi/	\
-			   rsi.o jump_label.o
+			   rsi.o jump_label.o rhi.o
 
 obj-$(CONFIG_COMPAT)			+= sys32.o signal32.o			\
 					   sys_compat.o
diff --git a/arch/arm64/kernel/rhi.c b/arch/arm64/kernel/rhi.c
new file mode 100644
index 000000000000..d2141b5283e1
--- /dev/null
+++ b/arch/arm64/kernel/rhi.c
@@ -0,0 +1,53 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#include <asm/rsi.h>
+#include <asm/rhi.h>
+
+/* we need an aligned rhicall for rsi_host_call. slab is not yet ready */
+static struct rsi_host_call hyp_pagesize_rhicall;
+unsigned long rhi_get_ipa_change_alignment(void)
+{
+	long ret;
+	unsigned long ipa_change_align;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_VERSION;
+	ret = rsi_host_call(&hyp_pagesize_rhicall);
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	if (hyp_pagesize_rhicall.gprs[0] != RHI_HOSTCONF_VER_1_0)
+		goto err_out;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_FEATURES;
+	ret = rsi_host_call(&hyp_pagesize_rhicall);
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	if (!(hyp_pagesize_rhicall.gprs[0] & __RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT))
+		goto err_out;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT;
+	ret = rsi_host_call(&hyp_pagesize_rhicall);
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	ipa_change_align = hyp_pagesize_rhicall.gprs[0];
+	/* This error needs special handling in the caller */
+	if (ipa_change_align & (SZ_4K - 1))
+		return 0;
+
+	return ipa_change_align;
+
+err_out:
+	/*
+	 * For failure condition assume host is built with 4K page size
+	 * and hence ipa change alignment can be guest PAGE_SIZE.
+	 */
+	return PAGE_SIZE;
+}
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index c64a06f58c0b..6e35cb947745 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -13,8 +13,10 @@
 #include <asm/io.h>
 #include <asm/mem_encrypt.h>
 #include <asm/rsi.h>
+#include <asm/rhi.h>
 
 static struct realm_config config;
+static unsigned long ipa_change_alignment = PAGE_SIZE;
 
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
@@ -138,6 +140,11 @@ static int realm_ioremap_hook(phys_addr_t phys, size_t size, pgprot_t *prot)
 	return 0;
 }
 
+unsigned long realm_get_hyp_pagesize(void)
+{
+	return ipa_change_alignment;
+}
+
 void __init arm64_rsi_init(void)
 {
 	if (arm_smccc_1_1_get_conduit() != SMCCC_CONDUIT_SMC)
@@ -146,6 +153,12 @@ void __init arm64_rsi_init(void)
 		return;
 	if (WARN_ON(rsi_get_realm_config(&config)))
 		return;
+
+	ipa_change_alignment = rhi_get_ipa_change_alignment();
+	/* If we don't get a correct alignment response, don't enable realm */
+	if (!ipa_change_alignment)
+		return;
+
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
index 38c62c9e4e74..f5d64bc29c20 100644
--- a/arch/arm64/mm/mem_encrypt.c
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -59,3 +59,11 @@ int set_memory_decrypted(unsigned long addr, int numpages)
 	return crypt_ops->decrypt(addr, numpages);
 }
 EXPORT_SYMBOL_GPL(set_memory_decrypted);
+
+size_t mem_decrypt_granule_size(void)
+{
+	if (is_realm_world())
+		return max(PAGE_SIZE, realm_get_hyp_pagesize());
+	return PAGE_SIZE;
+}
+EXPORT_SYMBOL_GPL(mem_decrypt_granule_size);

---

## [5] Suzuki K Poulose — 2026-03-09
*Subject: Re: [PATCH v3 3/3] coco: guest: arm64: Add Realm Host Interface and
 hostconf RHI*

Hi Aneesh

On 09/03/2026 10:26, Aneesh Kumar K.V (Arm) wrote:
> - describe the Realm Host Interface SMC IDs and result codes in a new
>    asm/rhi.h header

minor nit: We reset the alignment to 0 if this fails. see below.

> +	/* If we don't get a correct alignment response, don't enable realm */

Do we need to enforce this ? If the Host doesn't implement this, we 
could proceed and the guest might encounter failures in "sharing" in
the worst case. Otherwise, it could proceed. Eitherway, RMM guarantees
that the "state" of the PFNs are stable as reported by the RSI
calls and the Guest knows exactly what has happened.

Suzuki


> +	if (!ipa_change_alignment)
> +		return;



>   	prot_ns_shared = BIT(config.ipa_bits - 1);
>

---

## [6] kernel test robot — 2026-03-09
*Subject: Re: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on arm64/for-next/core]
[also build test ERROR on tip/irq/core arm/for-next arm/fixes kvmarm/next soc/for-next linus/master v7.0-rc3 next-20260306]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/dma-direct-swiotlb-handle-swiotlb-alloc-free-outside-__dma_direct_alloc_pages/20260309-182834
base:   https://git.kernel.org/pub/scm/linux/kernel/git/arm64/linux.git for-next/core
patch link:    https://lore.kernel.org/r/20260309102625.2315725-3-aneesh.kumar%40kernel.org
patch subject: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers
config: x86_64-rhel-9.4-rust (https://download.01.org/0day-ci/archive/20260309/202603091444.4H1PFs01-lkp@intel.com/config)
compiler: clang version 20.1.8 (https://github.com/llvm/llvm-project 87f0227cb60147a26a1eeb4fb06e3b505e9c7261)
rustc: rustc 1.88.0 (6b00bc388 2025-06-23)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260309/202603091444.4H1PFs01-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603091444.4H1PFs01-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/x86/kernel/asm-offsets.c:9:
   In file included from include/linux/crypto.h:15:
   In file included from include/linux/completion.h:12:
   In file included from include/linux/swait.h:7:
   In file included from include/linux/spinlock.h:59:
   In file included from include/linux/irqflags.h:18:
   In file included from arch/x86/include/asm/irqflags.h:5:
   In file included from arch/x86/include/asm/processor-flags.h:6:
>> include/linux/mem_encrypt.h:60:9: error: use of undeclared identifier 'PAGE_SIZE'
      60 |         return PAGE_SIZE;
         |                ^
>> include/linux/mem_encrypt.h:66:9: error: call to undeclared function 'ALIGN'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
      66 |         return ALIGN(size, mem_decrypt_granule_size());
         |                ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:98:11: warning: array index 3 is past the end of the array (that has type 'unsigned long[1]') [-Warray-bounds]
      98 |                 return (set->sig[3] | set->sig[2] |
         |                         ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:98:25: warning: array index 2 is past the end of the array (that has type 'unsigned long[1]') [-Warray-bounds]
      98 |                 return (set->sig[3] | set->sig[2] |
         |                                       ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:99:4: warning: array index 1 is past the end of the array (that has type 'unsigned long[1]') [-Warray-bounds]
      99 |                         set->sig[1] | set->sig[0]) == 0;
         |                         ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:101:11: warning: array index 1 is past the end of the array (that has type 'unsigned long[1]') [-Warray-bounds]
     101 |                 return (set->sig[1] | set->sig[0]) == 0;
         |                         ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:114:11: warning: array index 3 is past the end of the array (that has type 'const unsigned long[1]') [-Warray-bounds]
     114 |                 return  (set1->sig[3] == set2->sig[3]) &&
         |                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:114:27: warning: array index 3 is past the end of the array (that has type 'const unsigned long[1]') [-Warray-bounds]
     114 |                 return  (set1->sig[3] == set2->sig[3]) &&


vim +/PAGE_SIZE +60 include/linux/mem_encrypt.h

    56	
    57	#ifndef mem_decrypt_granule_size
    58	static inline size_t mem_decrypt_granule_size(void)
    59	{
  > 60		return PAGE_SIZE;
    61	}
    62	#endif
    63	
    64	static inline size_t mem_decrypt_align(size_t size)
    65	{
  > 66		return ALIGN(size, mem_decrypt_granule_size());
    67	}
    68

---

## [7] kernel test robot — 2026-03-09
*Subject: Re: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on arm64/for-next/core]
[also build test ERROR on tip/irq/core arm/for-next arm/fixes kvmarm/next soc/for-next linus/master v7.0-rc3 next-20260306]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/dma-direct-swiotlb-handle-swiotlb-alloc-free-outside-__dma_direct_alloc_pages/20260309-182834
base:   https://git.kernel.org/pub/scm/linux/kernel/git/arm64/linux.git for-next/core
patch link:    https://lore.kernel.org/r/20260309102625.2315725-3-aneesh.kumar%40kernel.org
patch subject: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers
config: x86_64-rhel-9.4 (https://download.01.org/0day-ci/archive/20260309/202603091555.ZRQIMCqJ-lkp@intel.com/config)
compiler: gcc-14 (Debian 14.2.0-19) 14.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260309/202603091555.ZRQIMCqJ-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603091555.ZRQIMCqJ-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/x86/include/asm/processor-flags.h:6,
                    from arch/x86/include/asm/irqflags.h:5,
                    from include/linux/irqflags.h:18,
                    from include/linux/spinlock.h:59,
                    from include/linux/swait.h:7,
                    from include/linux/completion.h:12,
                    from include/linux/crypto.h:15,
                    from arch/x86/kernel/asm-offsets.c:9:
   include/linux/mem_encrypt.h: In function 'mem_decrypt_granule_size':
>> include/linux/mem_encrypt.h:60:16: error: 'PAGE_SIZE' undeclared (first use in this function)
      60 |         return PAGE_SIZE;
         |                ^~~~~~~~~
   include/linux/mem_encrypt.h:60:16: note: each undeclared identifier is reported only once for each function it appears in
   include/linux/mem_encrypt.h: In function 'mem_decrypt_align':
>> include/linux/mem_encrypt.h:66:16: error: implicit declaration of function 'ALIGN' [-Wimplicit-function-declaration]
      66 |         return ALIGN(size, mem_decrypt_granule_size());
         |                ^~~~~
   make[3]: *** [scripts/Makefile.build:184: arch/x86/kernel/asm-offsets.s] Error 1
   make[3]: Target 'prepare' not remade because of errors.
   make[2]: *** [Makefile:1333: prepare0] Error 2
   make[2]: Target 'prepare' not remade because of errors.
   make[1]: *** [Makefile:248: __sub-make] Error 2
   make[1]: Target 'prepare' not remade because of errors.
   make: *** [Makefile:248: __sub-make] Error 2
   make: Target 'prepare' not remade because of errors.


vim +/PAGE_SIZE +60 include/linux/mem_encrypt.h

    56	
    57	#ifndef mem_decrypt_granule_size
    58	static inline size_t mem_decrypt_granule_size(void)
    59	{
  > 60		return PAGE_SIZE;
    61	}
    62	#endif
    63	
    64	static inline size_t mem_decrypt_align(size_t size)
    65	{
  > 66		return ALIGN(size, mem_decrypt_granule_size());
    67	}
    68

---

## [8] kernel test robot — 2026-03-09
*Subject: Re: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on arm64/for-next/core]
[also build test ERROR on tip/irq/core arm/for-next arm/fixes kvmarm/next soc/for-next linus/master v7.0-rc3 next-20260306]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/dma-direct-swiotlb-handle-swiotlb-alloc-free-outside-__dma_direct_alloc_pages/20260309-182834
base:   https://git.kernel.org/pub/scm/linux/kernel/git/arm64/linux.git for-next/core
patch link:    https://lore.kernel.org/r/20260309102625.2315725-3-aneesh.kumar%40kernel.org
patch subject: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers
config: i386-randconfig-013-20260309 (https://download.01.org/0day-ci/archive/20260309/202603092323.myqT3tXw-lkp@intel.com/config)
compiler: gcc-14 (Debian 14.2.0-19) 14.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260309/202603092323.myqT3tXw-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603092323.myqT3tXw-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/x86/include/asm/processor-flags.h:6,
                    from arch/x86/include/asm/irqflags.h:5,
                    from include/linux/irqflags.h:18,
                    from include/linux/spinlock.h:59,
                    from include/linux/swait.h:7,
                    from include/linux/completion.h:12,
                    from include/linux/crypto.h:15,
                    from arch/x86/kernel/asm-offsets.c:9:
   include/linux/mem_encrypt.h: In function 'mem_decrypt_granule_size':
>> include/linux/mem_encrypt.h:60:16: error: 'PAGE_SIZE' undeclared (first use in this function)
      60 |         return PAGE_SIZE;
         |                ^~~~~~~~~
   include/linux/mem_encrypt.h:60:16: note: each undeclared identifier is reported only once for each function it appears in
   include/linux/mem_encrypt.h: In function 'mem_decrypt_align':
>> include/linux/mem_encrypt.h:66:16: error: implicit declaration of function 'ALIGN' [-Wimplicit-function-declaration]
      66 |         return ALIGN(size, mem_decrypt_granule_size());
         |                ^~~~~
   make[3]: *** [scripts/Makefile.build:184: arch/x86/kernel/asm-offsets.s] Error 1 shuffle=4157930943
   make[3]: Target 'prepare' not remade because of errors.
   make[2]: *** [Makefile:1333: prepare0] Error 2 shuffle=4157930943
   make[2]: Target 'prepare' not remade because of errors.
   make[1]: *** [Makefile:248: __sub-make] Error 2 shuffle=4157930943
   make[1]: Target 'prepare' not remade because of errors.
   make: *** [Makefile:248: __sub-make] Error 2 shuffle=4157930943
   make: Target 'prepare' not remade because of errors.


vim +/PAGE_SIZE +60 include/linux/mem_encrypt.h

    56	
    57	#ifndef mem_decrypt_granule_size
    58	static inline size_t mem_decrypt_granule_size(void)
    59	{
  > 60		return PAGE_SIZE;
    61	}
    62	#endif
    63	
    64	static inline size_t mem_decrypt_align(size_t size)
    65	{
  > 66		return ALIGN(size, mem_decrypt_granule_size());
    67	}
    68

---

## [9] kernel test robot — 2026-03-09
*Subject: Re: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on arm64/for-next/core]
[also build test ERROR on tip/irq/core arm/for-next arm/fixes kvmarm/next soc/for-next linus/master v7.0-rc3 next-20260306]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/dma-direct-swiotlb-handle-swiotlb-alloc-free-outside-__dma_direct_alloc_pages/20260309-182834
base:   https://git.kernel.org/pub/scm/linux/kernel/git/arm64/linux.git for-next/core
patch link:    https://lore.kernel.org/r/20260309102625.2315725-3-aneesh.kumar%40kernel.org
patch subject: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers
config: i386-randconfig-012-20260309 (https://download.01.org/0day-ci/archive/20260309/202603092320.JgtItJg0-lkp@intel.com/config)
compiler: clang version 20.1.8 (https://github.com/llvm/llvm-project 87f0227cb60147a26a1eeb4fb06e3b505e9c7261)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260309/202603092320.JgtItJg0-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603092320.JgtItJg0-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/x86/kernel/asm-offsets.c:9:
   In file included from include/linux/crypto.h:15:
   In file included from include/linux/completion.h:12:
   In file included from include/linux/swait.h:7:
   In file included from include/linux/spinlock.h:59:
   In file included from include/linux/irqflags.h:18:
   In file included from arch/x86/include/asm/irqflags.h:5:
   In file included from arch/x86/include/asm/processor-flags.h:6:
>> include/linux/mem_encrypt.h:60:9: error: use of undeclared identifier 'PAGE_SIZE'
      60 |         return PAGE_SIZE;
         |                ^
>> include/linux/mem_encrypt.h:66:9: error: call to undeclared function 'ALIGN'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
      66 |         return ALIGN(size, mem_decrypt_granule_size());
         |                ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:98:11: warning: array index 3 is past the end of the array (that has type 'unsigned long[2]') [-Warray-bounds]
      98 |                 return (set->sig[3] | set->sig[2] |
         |                         ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:98:25: warning: array index 2 is past the end of the array (that has type 'unsigned long[2]') [-Warray-bounds]
      98 |                 return (set->sig[3] | set->sig[2] |
         |                                       ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:114:11: warning: array index 3 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     114 |                 return  (set1->sig[3] == set2->sig[3]) &&
         |                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:114:27: warning: array index 3 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     114 |                 return  (set1->sig[3] == set2->sig[3]) &&
         |                                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:115:5: warning: array index 2 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     115 |                         (set1->sig[2] == set2->sig[2]) &&
         |                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kernel/asm-offsets.c:14:
   In file included from include/linux/suspend.h:5:
   In file included from include/linux/swap.h:9:
   In file included from include/linux/memcontrol.h:13:
   In file included from include/linux/cgroup.h:17:
   In file included from include/linux/fs.h:5:
   In file included from include/linux/fs/super.h:5:
   In file included from include/linux/fs/super_types.h:13:
   In file included from include/linux/percpu-rwsem.h:7:
   In file included from include/linux/rcuwait.h:6:
   In file included from include/linux/sched/signal.h:6:
   include/linux/signal.h:115:21: warning: array index 2 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     115 |                         (set1->sig[2] == set2->sig[2]) &&


vim +/PAGE_SIZE +60 include/linux/mem_encrypt.h

    56	
    57	#ifndef mem_decrypt_granule_size
    58	static inline size_t mem_decrypt_granule_size(void)
    59	{
  > 60		return PAGE_SIZE;
    61	}
    62	#endif
    63	
    64	static inline size_t mem_decrypt_align(size_t size)
    65	{
  > 66		return ALIGN(size, mem_decrypt_granule_size());
    67	}
    68

---

## [10] Aneesh Kumar K.V — 2026-03-23
*Subject: Re: [PATCH v3 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

kernel test robot <lkp@intel.com> writes:

> Hi Aneesh,
>

Fixed this by including

modified   include/linux/mem_encrypt.h
@@ -11,6 +11,8 @@
 #define __MEM_ENCRYPT_H__
 
 #ifndef __ASSEMBLY__
+#include <linux/align.h>
+#include <vdso/page.h>
 
 #ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
 


Will include this in the next patch update.

The other alternative is to switch that to a macro 

modified   include/linux/mem_encrypt.h
@@ -55,16 +55,10 @@
 #endif
 
 #ifndef mem_decrypt_granule_size
-static inline size_t mem_decrypt_granule_size(void)
-{
-	return PAGE_SIZE;
-}
+#define mem_decrypt_granule_size()     PAGE_SIZE
 #endif
 
-static inline size_t mem_decrypt_align(size_t size)
-{
-	return ALIGN(size, mem_decrypt_granule_size());
-}
+#define mem_decrypt_align(size)        ALIGN((size), mem_decrypt_granule_size())

---
