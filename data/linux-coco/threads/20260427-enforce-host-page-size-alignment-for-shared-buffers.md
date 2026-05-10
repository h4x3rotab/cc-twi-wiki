---
title: 'Enforce host page-size alignment for shared buffers'
date: 2026-04-27
last_reply: 2026-05-06
message_count: 18
participants: ['Aneesh Kumar K.V (Arm)', 'Marc Zyngier', 'Jason Gunthorpe', 'Jason Gunthorpe', 'Will Deacon', 'Suzuki K Poulose']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-04-27

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

Changes from v3:
https://lore.kernel.org/all/20260309102625.2315725-1-aneesh.kumar@kernel.org
* Fix build error reported by kernel test robot <lkp@intel.com>

Changes from v2:
https://lore.kernel.org/all/20251221160920.297689-1-aneesh.kumar@kernel.org
* Rebase to latest kernel
* Consider swiotlb always decrypted and don't align when allocating from swiotlb.

Changes from v1:
* Rename the helper to mem_encrypt_align
* Improve the commit message
* Handle DMA allocations from contiguous memory
* Handle DMA allocations from the pool
* swiotlb is still considered unencrypted. Support for an encrypted swiotlb pool
  is left as TODO and is independent of this series.

Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Marc Zyngier <maz@kernel.org>
Cc: Marek Szyprowski <m.szyprowski@samsung.com>
Cc: Robin Murphy <robin.murphy@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Cc: Thomas Gleixner <tglx@kernel.org>
Cc: Will Deacon <will@kernel.org>

Aneesh Kumar K.V (Arm) (3):
  dma-direct: swiotlb: handle swiotlb alloc/free outside
    __dma_direct_alloc_pages
  swiotlb: dma: its: Enforce host page-size alignment for shared buffers
  coco: guest: arm64: Query host IPA-change alignment via RHI

 arch/arm64/include/asm/mem_encrypt.h |  3 ++
 arch/arm64/include/asm/rhi.h         | 24 ++++++++++++
 arch/arm64/include/asm/rsi.h         |  2 +
 arch/arm64/include/asm/rsi_cmds.h    | 10 +++++
 arch/arm64/include/asm/rsi_smc.h     |  7 ++++
 arch/arm64/kernel/Makefile           |  2 +-
 arch/arm64/kernel/rhi.c              | 54 ++++++++++++++++++++++++++
 arch/arm64/kernel/rsi.c              | 13 +++++++
 arch/arm64/mm/mem_encrypt.c          | 27 +++++++++++--
 drivers/irqchip/irq-gic-v3-its.c     | 20 ++++++----
 include/linux/mem_encrypt.h          | 14 +++++++
 kernel/dma/contiguous.c              | 10 +++++
 kernel/dma/direct.c                  | 58 ++++++++++++++++++++++++----
 kernel/dma/pool.c                    |  4 +-
 kernel/dma/swiotlb.c                 | 21 ++++++----
 15 files changed, 240 insertions(+), 29 deletions(-)
 create mode 100644 arch/arm64/include/asm/rhi.h
 create mode 100644 arch/arm64/kernel/rhi.c

---

## [2] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [PATCH v4 1/3] dma-direct: swiotlb: handle swiotlb alloc/free outside __dma_direct_alloc_pages*

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

## [3] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [PATCH v4 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers*

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

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/mm/mem_encrypt.c      | 19 +++++++++++++++----
 drivers/irqchip/irq-gic-v3-its.c | 20 +++++++++++++-------
 include/linux/mem_encrypt.h      | 14 ++++++++++++++
 kernel/dma/contiguous.c          | 10 ++++++++++
 kernel/dma/direct.c              | 16 ++++++++++++++--
 kernel/dma/pool.c                |  4 +++-
 kernel/dma/swiotlb.c             | 21 +++++++++++++--------
 7 files changed, 82 insertions(+), 22 deletions(-)

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
index 07584c5e36fb..1e01c9ac697f 100644
--- a/include/linux/mem_encrypt.h
+++ b/include/linux/mem_encrypt.h
@@ -11,6 +11,8 @@
 #define __MEM_ENCRYPT_H__
 
 #ifndef __ASSEMBLY__
+#include <linux/align.h>
+#include <vdso/page.h>
 
 #ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
 
@@ -54,6 +56,18 @@
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
index 9fd73700ddcf..b5cf8cd65e77 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -261,7 +261,7 @@ void __init swiotlb_update_mem_attributes(void)
 
 	if (!mem->nslabs || mem->late_alloc)
 		return;
-	bytes = PAGE_ALIGN(mem->nslabs << IO_TLB_SHIFT);
+	bytes = mem_decrypt_align(mem->nslabs << IO_TLB_SHIFT);
 	set_memory_decrypted((unsigned long)mem->vaddr, bytes >> PAGE_SHIFT);
 }
 
@@ -318,8 +318,8 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 		unsigned int flags,
 		int (*remap)(void *tlb, unsigned long nslabs))
 {
-	size_t bytes = PAGE_ALIGN(nslabs << IO_TLB_SHIFT);
 	void *tlb;
+	size_t bytes = mem_decrypt_align(nslabs << IO_TLB_SHIFT);
 
 	/*
 	 * By default allocate the bounce buffer memory from low memory, but
@@ -327,9 +327,9 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
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
@@ -338,7 +338,7 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 	}
 
 	if (remap && remap(tlb, nslabs) < 0) {
-		memblock_free(tlb, PAGE_ALIGN(bytes));
+		memblock_free(tlb, bytes);
 		pr_warn("%s: Failed to remap %zu bytes\n", __func__, bytes);
 		return NULL;
 	}
@@ -460,7 +460,7 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 		swiotlb_adjust_nareas(num_possible_cpus());
 
 retry:
-	order = get_order(nslabs << IO_TLB_SHIFT);
+	order = get_order(mem_decrypt_align(nslabs << IO_TLB_SHIFT));
 	nslabs = SLABS_PER_PAGE << order;
 
 	while ((SLABS_PER_PAGE << order) > IO_TLB_MIN_SLABS) {
@@ -469,6 +469,8 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 		if (vstart)
 			break;
 		order--;
+		if (order < get_order(mem_decrypt_granule_size()))
+			break;
 		nslabs = SLABS_PER_PAGE << order;
 		retried = true;
 	}
@@ -536,7 +538,7 @@ void __init swiotlb_exit(void)
 
 	pr_info("tearing down default memory pool\n");
 	tbl_vaddr = (unsigned long)phys_to_virt(mem->start);
-	tbl_size = PAGE_ALIGN(mem->end - mem->start);
+	tbl_size = mem_decrypt_align(mem->end - mem->start);
 	slots_size = PAGE_ALIGN(array_size(sizeof(*mem->slots), mem->nslabs));
 
 	set_memory_encrypted(tbl_vaddr, tbl_size >> PAGE_SHIFT);
@@ -572,11 +574,13 @@ void __init swiotlb_exit(void)
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
@@ -659,6 +663,7 @@ static void swiotlb_free_tlb(void *vaddr, size_t bytes)
 	    dma_free_from_pool(NULL, vaddr, bytes))
 		return;
 
+	bytes = mem_decrypt_align(bytes);
 	/* Intentional leak if pages cannot be encrypted again. */
 	if (!set_memory_encrypted((unsigned long)vaddr, PFN_UP(bytes)))
 		__free_pages(virt_to_page(vaddr), get_order(bytes));

---

## [4] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change alignment via RHI*

Add the Realm Host Interface support needed to query host configuration
from a Realm guest. Define the RHI hostconf SMCs, add rsi_host_call(), and
use them during Realm initialization to retrieve the host IPA-change
alignment size.

Expose that alignment through realm_get_hyp_pagesize() and
mem_decrypt_granule_size() so shared-buffer allocation and
encryption/decryption paths can honor the ipa change page-size requirement.

If the host reports an invalid alignment (when alginment value is not
multiple of 4K), do not enable Realm support.

This provides the host alignment information required by the shared buffer
alignment changes.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  3 ++
 arch/arm64/include/asm/rhi.h         | 24 +++++++++++++
 arch/arm64/include/asm/rsi.h         |  2 ++
 arch/arm64/include/asm/rsi_cmds.h    | 10 ++++++
 arch/arm64/include/asm/rsi_smc.h     |  7 ++++
 arch/arm64/kernel/Makefile           |  2 +-
 arch/arm64/kernel/rhi.c              | 54 ++++++++++++++++++++++++++++
 arch/arm64/kernel/rsi.c              | 13 +++++++
 arch/arm64/mm/mem_encrypt.c          |  8 +++++
 9 files changed, 122 insertions(+), 1 deletion(-)
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
index fe627100d199..3e72dd9584ed 100644
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
index 000000000000..7cd6c5102464
--- /dev/null
+++ b/arch/arm64/kernel/rhi.c
@@ -0,0 +1,54 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#include <linux/mm.h>
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
+	ret = rsi_host_call(lm_alias(&hyp_pagesize_rhicall));
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	if (hyp_pagesize_rhicall.gprs[0] != RHI_HOSTCONF_VER_1_0)
+		goto err_out;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_FEATURES;
+	ret = rsi_host_call(lm_alias(&hyp_pagesize_rhicall));
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	if (!(hyp_pagesize_rhicall.gprs[0] & __RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT))
+		goto err_out;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT;
+	ret = rsi_host_call(lm_alias(&hyp_pagesize_rhicall));
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
index 9e846ce4ef9c..ff735c04e236 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -14,8 +14,10 @@
 #include <asm/mem_encrypt.h>
 #include <asm/pgtable.h>
 #include <asm/rsi.h>
+#include <asm/rhi.h>
 
 static struct realm_config config;
+static unsigned long ipa_change_alignment = PAGE_SIZE;
 
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
@@ -139,6 +141,11 @@ static int realm_ioremap_hook(phys_addr_t phys, size_t size, pgprot_t *prot)
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
@@ -147,6 +154,12 @@ void __init arm64_rsi_init(void)
 		return;
 	if (WARN_ON(rsi_get_realm_config(&config)))
 		return;
+
+	ipa_change_alignment = rhi_get_ipa_change_alignment();
+	/* If we don't get a correct alignment response, don't enable realm */
+	if (!ipa_change_alignment)
+		return;
+
 	prot_ns_shared = __phys_to_pte_val(BIT(config.ipa_bits - 1));
 
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

## [5] Marc Zyngier — 2026-04-27
*Subject: Re: [PATCH v4 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers*

On Mon, 27 Apr 2026 07:31:07 +0100,
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:
> 
> When running private-memory guests, the guest kernel must apply additional

I thought that was being fixed, and that there was now a strong
guarantee that RMM and host are aligned on the page size. Even more,
S2 is totally irrelevant here. The only thing that matters is the host
page size vs the guest page size. Nothing else.

> 
> Introduce a new helper, mem_decrypt_align(), to allow callers to enforce

[...]

> diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
> index 291d7668cc8d..239d7e3bc16f 100644

Here's the non-obfuscated version of the two hunks above (and let it
be on the record that New Order is a terrible, overrated band):

diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 291d7668cc8da..a4d555aaee241 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -216,6 +216,7 @@ static struct page *its_alloc_pages_node(int node, gfp_t gfp,
 	struct page *page;
 	int ret = 0;
 
+	order = get_order(mem_decrypt_align(PAGE_SIZE << order));
 	page = alloc_pages_node(node, gfp | gfp_flags_quirk, order);
 
 	if (!page)
@@ -245,6 +246,7 @@ static void its_free_pages(void *addr, unsigned int order)
 	 * If the memory cannot be encrypted again then we must leak the pages.
 	 * set_memory_encrypted() will already have WARNed.
 	 */
+	order = get_order(mem_decrypt_align(PAGE_SIZE << order));
 	if (set_memory_encrypted((unsigned long)addr, 1 << order))
 		return;
 	free_pages((unsigned long)addr, order);

>  static struct gen_pool *itt_pool;
> @@ -268,11 +272,13 @@ static void *itt_alloc_pool(int node, int size)

You already taught its_alloc_pages_node() about the decrypt granule
size stuff. I don't think we need to see more of it (and you don't
mess with the call that is just above it).

>  		if (!page)
>  			break;

I'd rather see something like mem_decrypt_align(PAGE_SIZE), which
keeps the intent clear.

	M.

---

## [6] Marc Zyngier — 2026-04-27
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change alignment via RHI*

On Mon, 27 Apr 2026 07:31:08 +0100,
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:
> 
> Add the Realm Host Interface support needed to query host configuration

I don't understand what "IPA-change" means. What you are after is the
host's sharing granule size.

> 
> Expose that alignment through realm_get_hyp_pagesize() and

Errr... What guarantees that *rhi_call is *IPA contiguous*? This is
incredibly fragile. You should at the very least check that this isn't
vmalloc'd.

> +
> +	return res.a0;

Why the "hyp_" prefix? This has absolutely nothing to with the
hypervisor.

> +unsigned long rhi_get_ipa_change_alignment(void)
> +{

Why can't this be part of rsi.c? This is an RSI call, and it should be
part of the RSI initialisation.

> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
> index 9e846ce4ef9c..ff735c04e236 100644

Again, this has nothing to do with the hypervisor, but the host. And
ipa_change_alignment is still a wording I can't wrap my small head
around.

> +
>  void __init arm64_rsi_init(void)

But at the same time, you override a global value with an error, and
then paper over it in mem_decrypt_granule_size()...

> +
>  	prot_ns_shared = __phys_to_pte_val(BIT(config.ipa_bits - 1));

If you didn't mess with ipa_change_alignment above, you shouldn't need
this max().

	M.

---

## [7] Jason Gunthorpe — 2026-04-27
*Subject: Re: [PATCH v4 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

On Mon, Apr 27, 2026 at 10:27:23AM +0100, Marc Zyngier wrote:
> > With CCA, although Stage-2 mappings managed by the RMM still operate at a
> > 4K granularity, shared pages must nonetheless be aligned to the

Yes, the RMM and host are supposed to be aligned on page size, but
this means the guest now has this mem_decrypt_granule_size() value
that it has to deal with, and it won't always be 4k.

The spec introduction of RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT is
fixing a defect in earlier RMM specs that just assumed it was always
4k.

AFAIK this is unfixable in ARM's architecture..

> Even more, S2 is totally irrelevant here. The only thing that
> matters is the host page size vs the guest page size. Nothing else.

Yeah

Or rather more specifically the RMM now has
RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT which says exactly the minimum
supported shared/private conversion granule and the VM must obey it.

It doesn't actually matter *WHY* the RMM chooses a size, whatever it
is the guest must follow it.

It would probably be helpful to focus on this a little more, as really
this series is implementing a new RMM feature. It is good to explain
why this feature was added to RMM in the cover letter, but I would
focus the patch commentary on explaining the process of introducing
mem_decrypt_granule_size()

Jason

---

## [8] Jason Gunthorpe — 2026-04-27
*Subject: Re: [PATCH v4 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

On Mon, Apr 27, 2026 at 12:01:07PM +0530, Aneesh Kumar K.V (Arm) wrote:
> When running private-memory guests, the guest kernel must apply additional
> constraints when allocating buffers that are shared with the hypervisor.

This patch has way too much stuff in it.

I think your patch structure should be changed around

1) Patch to add mem_decrypt_granule_size(), and explain it as
   the alignment & size of what can be passed to
   set_memory_encrypted/decrypted()

2) Add support for mem_decrypt_granule_size() to ARM

Then patches going caller by caller of set_memory_decrypted() to make
them follow the new rule:

3) its

4) swiotlb 

3) dma_alloc_coherent

etc.

don't forget about the new dma buf heaps too:

drivers/dma-buf/heaps/system_heap.c:    ret = set_memory_decrypted(addr, nr_pages);

It is worth calling out in the cover letter that all the ARM CCA
relevant places are fixed but drivers/hv/ is left for future.

> @@ -33,18 +32,30 @@ int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops)
>  

This should go in the ARM patch adding mem_decrypt_granule_size() to CCA

> diff --git a/include/linux/mem_encrypt.h b/include/linux/mem_encrypt.h
> index 07584c5e36fb..1e01c9ac697f 100644

I know it seems a bit small, but put this in its own patch and explain
how it works. I'd also like to see a kdoc here, and add a kdoc to
set_memory_decrypted() that links back so people have a better chance
to know about this.

Jason

---

## [9] Aneesh Kumar K.V — 2026-04-28
*Subject: Re: [PATCH v4 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Marc Zyngier <maz@kernel.org> writes:

> On Mon, 27 Apr 2026 07:31:07 +0100,
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

Yes, the latest RMM update includes the ability to change the granule
size.

The section above in the commit message was intended to explain that the
S2 mapping size is irrelevant. I agree it is not clear as written, so I
will reword it to improve clarity.

>
>> 

I will include this in the next revision.


>>  static struct gen_pool *itt_pool;
>> @@ -268,11 +272,13 @@ static void *itt_alloc_pool(int node, int size)

The helper was added based on feedback from a previous version. I assume
you are suggesting that only this caller should switch?


-aneesh

---

## [10] Aneesh Kumar K.V — 2026-04-28
*Subject: Re: [PATCH v4 2/3] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Mon, Apr 27, 2026 at 12:01:07PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> When running private-memory guests, the guest kernel must apply additional

Okay, I’ll update all the above in the next revision.

-aneesh

---

## [11] Aneesh Kumar K.V — 2026-04-28
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change
 alignment via RHI*

Marc Zyngier <maz@kernel.org> writes:

> On Mon, 27 Apr 2026 07:31:08 +0100,
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

This is part of the RHI specification, and the call is named
RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT. The intent is to determine the
alignment requirements for changing IPA attributes (protected vs.
unprotected IPA

>
>> 


I didn’t quite follow that. We have other RSI calls (even RMI calls)
that do similar things, and the caller understands that the address
should be IPA-contiguous. Are you suggesting that all RSI calls should
add checks for this?. or are you suggesting to update the API to

unsigned long rsi_host_call(unsigned long rhi_call_phys) ?

>> +
>> +	return res.a0;

Sure will update "hyp_" reference to host. 


>> +unsigned long rhi_get_ipa_change_alignment(void)
>> +{

This is an RHI call as per the specification, hence it has been added to
rhi.c.

>> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
>> index 9e846ce4ef9c..ff735c04e236 100644


I believe I received similar feedback on my previous version as well,
which I didn’t quite follow.

rhi_get_ipa_change_alignment() only returns an error when the host
returns a size that is not 4K-aligned. Otherwise, it returns the
host-determined size, or defaults to guest PAGE_SIZE if the RHI call
itself is not supported.

	ipa_change_align = hyp_pagesize_rhicall.gprs[0];
	/* This error needs special handling in the caller */
	if (ipa_change_align & (SZ_4K - 1))
		return 0;

	return ipa_change_align;

err_out:
	/*
	 * For failure condition assume host is built with 4K page size
	 * and hence ipa change alignment can be guest PAGE_SIZE.
	 */
	return PAGE_SIZE;

>
>> +

size_t mem_decrypt_granule_size(void)
{
	if (is_realm_world())
		return max(PAGE_SIZE, realm_get_hyp_pagesize());
	return PAGE_SIZE;
}

That needs to use max(), because we should align to the guest PAGE_SIZE
if it is larger than the host-specified alignment value.

-aneesh

---

## [12] Marc Zyngier — 2026-04-28
*Subject: Re: [PATCH v4 2/3] swiotlb: dma: its: Enforce host page-size alignment for shared buffers*

On Tue, 28 Apr 2026 13:20:53 +0100,
Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:
> 
> Marc Zyngier <maz@kernel.org> writes:

Even better, remove it. Nothing CCA-specific should be in this patch.

[...]

> >>  static struct gen_pool *itt_pool;
> >> @@ -268,11 +272,13 @@ static void *itt_alloc_pool(int node, int size)

I don't know what you mean by 'this'. What I'd like to see is this
last hunk be changed to:

	gen_pool_add(itt_pool, (unsigned long)page_address(page),
		     mem_decrypt_align(PAGE_SIZE), node);

and the previous hunk simply dropped.

Thanks,

	M.

---

## [13] Marc Zyngier — 2026-04-28
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change alignment via RHI*

On Tue, 28 Apr 2026 13:49:46 +0100,
Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:
> 
> Marc Zyngier <maz@kernel.org> writes:

This really is a terrible name. Why the 'change' part? It doesn't
change, it is a constant.

Oh well...

[...]

> >> +static inline unsigned long rsi_host_call(struct rsi_host_call *rhi_call)
> >> +{

Does it? Where is it documented?  All you get is a pointer, so all
bets are off.

> Are you suggesting that all RSI calls should
> add checks for this?. or are you suggesting to update the API to

I'm suggesting that this API is subtly broken because it makes random
assumption about the physical contiguity of the VA space. It does so
without any check, without any documentation.

Simply changing the parameter to phys_addr_t could at the very least
capture some of the requirements, but I'd like something in big bold
letters.

>
> >> +

News flash: this is the Linux kernel, not an ARM spec. We organise
things based on the logical use, not on the TLA associated with it.

And RHI is implemented in terms of RSI. In rsi.c it goes. We don't
need this pointless proliferation of helper files that only result in
equally pointless global symbols.

> 
> >> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c

And you didn't think of asking? Sometimes I wonder what these patch
reviews are for... Just to waste some more electrons, I guess :-/.

> 
> rhi_get_ipa_change_alignment() only returns an error when the host

You encode the error as 0. You override ipa_change_alignment with 0.

Then...

> >> +size_t mem_decrypt_granule_size(void)
> >> +{

... you need to correct that back to PAGE_SIZE because you have stored
something smaller than PAGE_SIZE.

Isn't the problem really obvious? ipa_change_alignment can *NEVER* go
down. It should never be allowed to reduce, because that's exactly
the property you are trying to enforce.

	M.

---

## [14] Will Deacon — 2026-04-28
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change
 alignment via RHI*

[+Seb for the ITS]

On Mon, Apr 27, 2026 at 12:01:08PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add the Realm Host Interface support needed to query host configuration
> from a Realm guest. Define the RHI hostconf SMCs, add rsi_host_call(), and

[...]

> diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
> index 38c62c9e4e74..f5d64bc29c20 100644

No, this should be indirected via 'struct arm64_mem_crypt_ops' because
there's nothing particularly unique to realms here. For pKVM protected
guests using a smaller page-size than the host, we'd presumably need
something similar for the ITS (where restricted-dma isn't used).

Will

---

## [15] Suzuki K Poulose — 2026-04-28
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change
 alignment via RHI*

On 28/04/2026 14:49, Marc Zyngier wrote:
> On Tue, 28 Apr 2026 13:49:46 +0100,
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

Agreed, it was supposed to mean IPA_STATE_CHANGE.

> 
> Oh well...

...

>>>> +unsigned long rhi_get_ipa_change_alignment(void)
>>>> +{

RHI (Realm Host Interface) is not really the same as RSI. The former is
a service mechanism for Realms with the "Non-secure Hypervisor".  And
this single call is just one of the services. There are further more
services that will eventually come up (e.g., Device Assignment, Boot
Sync Protocol, Firmware Activity Log etc).

RSI (to be precise, RSI_HOST_CALL) is the transport to talk to the Host,
as that is the only way for the Realm to reach the Host. So, tbh, it
does make sense to keep this in rhic ?

Suzuki

---

## [16] Aneesh Kumar K.V — 2026-04-29
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change
 alignment via RHI*

Marc Zyngier <maz@kernel.org> writes:

> On Tue, 28 Apr 2026 13:49:46 +0100,
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

Sure, I will update rhi_get_ipa_change_alignment() to always return the
max value.

-aneesh

---

## [17] Aneesh Kumar K.V — 2026-04-29
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change
 alignment via RHI*

Will Deacon <will@kernel.org> writes:

> [+Seb for the ITS]
>

Sure, I will rework this to use struct arm64_mem_crypt_ops in the next revision.

-aneesh

---

## [18] Aneesh Kumar K.V — 2026-05-06
*Subject: Re: [PATCH v4 3/3] coco: guest: arm64: Query host IPA-change
 alignment via RHI*

Marc Zyngier <maz@kernel.org> writes:

> On Tue, 28 Apr 2026 13:49:46 +0100,
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

How about rhi_get_host_sharing_alignment()? or can you suggest a better
name I can switch to?

> Oh well...
>

We have multiple rmi and rsi calls that takes ipa values. asm/rmi_cmds.h
and asm/rsi_cmds.h. Some of them takes phys_addr_t while others take
unsigned long. The spec mention these as 64 bits values. May be we
should switch them all to u64. x86 also having similar discussion 
https://lore.kernel.org/all/afOrd7JYkUfe7wcZ@google.com

>
>> Are you suggesting that all RSI calls should


virt_to_phys() emits a WARN if the address is not part of the linear
map. Are you suggesting that we should add additional checks to the call
sites that pass such addresses?

Sorry, it’s still not clear to me how you want these calls to be
updated.

The pattern I’ve been following is:

Lower-level calls that use arm_smccc_1_1_invoke() take parameters as
unsigned long. I initially wanted to switch this to u64, but since
kvm/rmi.c uses unsigned long, it was decided to keep it consistent.

This approach is used in cases where the same argument is passed across
multiple calls, for example:

phys_addr_t rd_phys = virt_to_phys(realm->rd);
rmi_vdev_create(rd_phys, ...);
rmi_vdev_lock(rd_phys, ...);

For calls like rsi_host_call(), I chose to pass a struct pointer to
maintain better type safety:

static inline unsigned long rsi_host_call(struct rsi_host_call *rhi_call)
{
	phys_addr_t addr = virt_to_phys(rhi_call);

	arm_smccc_1_1_invoke(SMC_RSI_HOST_CALL, addr, &res);
}

Note that virt_to_phys() will WARN if the address is not part of the
linear map

Could you clarify what changes you would like to see in these
interfaces?

-aneesh

---
