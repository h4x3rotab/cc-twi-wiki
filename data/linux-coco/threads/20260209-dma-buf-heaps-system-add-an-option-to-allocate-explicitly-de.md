---
title: 'dma-buf: heaps: system: add an option to allocate explicitly decrypted memory'
date: 2026-02-09
last_reply: 2026-02-23
message_count: 20
participants: ['Jiri Pirko', 'John Stultz', 'Jason Gunthorpe', 'kernel test robot', 'Leon Romanovsky', 'Marek Szyprowski']
---

## [1] Jiri Pirko — 2026-02-09

From: Jiri Pirko <jiri@nvidia.com>

Confidential computing (CoCo) VMs/guests, such as AMD SEV and Intel TDX,
run with encrypted/protected memory which creates a challenge
for devices that do not support DMA to it (no TDISP support).

For kernel-only DMA operations, swiotlb bounce buffering provides a
transparent solution by copying data through decrypted memory.
However, the only way to get this memory into userspace is via the DMA
API's dma_alloc_pages()/dma_mmap_pages() type interfaces which limits
the use of the memory to a single DMA device, and is incompatible with
pin_user_pages().

These limitations are particularly problematic for the RDMA subsystem
which makes heavy use of pin_user_pages() and expects flexible memory
usage between many different DMA devices.

This patch series enables userspace to explicitly request decrypted
(shared) memory allocations from the dma-buf system heap.
Userspace can mmap this memory and pass the dma-buf fd to other
existing importers such as RDMA or DRM devices to access the
memory. The DMA API is improved to allow the dma heap exporter to DMA
map the shared memory to each importing device.

Jiri Pirko (5):
  dma-mapping: avoid random addr value print out on error path
  dma-mapping: introduce DMA_ATTR_CC_DECRYPTED for pre-decrypted memory
  dma-buf: heaps: use designated initializer for exp_info
  dma-buf: heaps: allow heap to specify valid heap flags
  dma-buf: heaps: system: add an option to allocate explicitly decrypted
    memory

 drivers/dma-buf/dma-heap.c          |  5 +-
 drivers/dma-buf/heaps/cma_heap.c    |  7 ++-
 drivers/dma-buf/heaps/system_heap.c | 96 ++++++++++++++++++++++++++---
 include/linux/dma-heap.h            |  3 +
 include/linux/dma-mapping.h         |  7 +++
 include/trace/events/dma.h          |  3 +-
 include/uapi/linux/dma-heap.h       | 12 +++-
 kernel/dma/direct.h                 | 14 ++++-
 8 files changed, 128 insertions(+), 19 deletions(-)

---

## [2] Jiri Pirko — 2026-02-09
*Subject: [PATCH 1/5] dma-mapping: avoid random addr value print out on error path*

From: Jiri Pirko <jiri@nvidia.com>

dma_addr is unitialized in dma_direct_map_phys() when swiotlb is forced
and DMA_ATTR_MMIO is set which leads to random value print out in
warning. Fix that by just returning DMA_MAPPING_ERROR.

Fixes: e53d29f957b3 ("dma-mapping: convert dma_direct_*map_page to be phys_addr_t based")
Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
 kernel/dma/direct.h | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
index da2fadf45bcd..62f0d9d0ba02 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -88,7 +88,7 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 
 	if (is_swiotlb_force_bounce(dev)) {
 		if (attrs & DMA_ATTR_MMIO)
-			goto err_overflow;
+			return DMA_MAPPING_ERROR;
 
 		return swiotlb_map(dev, phys, size, dir, attrs);
 	}

---

## [3] Jiri Pirko — 2026-02-09
*Subject: [PATCH 2/5] dma-mapping: introduce DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

From: Jiri Pirko <jiri@nvidia.com>

This is only relevant inside confidential computing (CoCo) virtual
machines, not on the hypervisor side.

Current CoCo designs don't place a vIOMMU in front of untrusted devices.
Instead, the DMA API forces all untrusted device DMA through swiotlb
bounce buffers (is_swiotlb_force_bounce()) which copies data into
decrypted memory on behalf of the device.

When a caller has already arranged for the memory to be decrypted
via set_memory_decrypted(), the DMA API needs to know so it can map
directly using the unencrypted physical address rather than bounce
buffering. Following the pattern of DMA_ATTR_MMIO, add
DMA_ATTR_CC_DECRYPTED for this purpose. Like the MMIO case, only the
caller knows what kind of memory it has and must inform the DMA API
for it to work correctly.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
 include/linux/dma-mapping.h |  7 +++++++
 include/trace/events/dma.h  |  3 ++-
 kernel/dma/direct.h         | 14 +++++++++++---
 3 files changed, 20 insertions(+), 4 deletions(-)

diff --git a/include/linux/dma-mapping.h b/include/linux/dma-mapping.h
index aa36a0d1d9df..052235feb853 100644
--- a/include/linux/dma-mapping.h
+++ b/include/linux/dma-mapping.h
@@ -78,6 +78,13 @@
  */
 #define DMA_ATTR_MMIO		(1UL << 10)
 
+/*
+ * DMA_ATTR_CC_DECRYPTED: Indicates memory that has been explicitly decrypted
+ * (shared) for confidential computing guests. The caller must have
+ * called set_memory_decrypted(). A struct page is required.
+ */
+#define DMA_ATTR_CC_DECRYPTED	(1UL << 11)
+
 /*
  * A dma_addr_t can hold any valid DMA or bus address for the platform.  It can
  * be given to a device to use as a DMA source or target.  It is specific to a
diff --git a/include/trace/events/dma.h b/include/trace/events/dma.h
index b3fef140ae15..b3c2cee8841a 100644
--- a/include/trace/events/dma.h
+++ b/include/trace/events/dma.h
@@ -32,7 +32,8 @@ TRACE_DEFINE_ENUM(DMA_NONE);
 		{ DMA_ATTR_ALLOC_SINGLE_PAGES, "ALLOC_SINGLE_PAGES" }, \
 		{ DMA_ATTR_NO_WARN, "NO_WARN" }, \
 		{ DMA_ATTR_PRIVILEGED, "PRIVILEGED" }, \
-		{ DMA_ATTR_MMIO, "MMIO" })
+		{ DMA_ATTR_MMIO, "MMIO" }, \
+		{ DMA_ATTR_CC_DECRYPTED, "CC_DECRYPTED" })
 
 DECLARE_EVENT_CLASS(dma_map,
 	TP_PROTO(struct device *dev, phys_addr_t phys_addr, dma_addr_t dma_addr,
diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
index 62f0d9d0ba02..ae5bc1919e1c 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -87,16 +87,24 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 	dma_addr_t dma_addr;
 
 	if (is_swiotlb_force_bounce(dev)) {
-		if (attrs & DMA_ATTR_MMIO)
-			return DMA_MAPPING_ERROR;
+		if (!(attrs & DMA_ATTR_CC_DECRYPTED)) {
+			if (attrs & DMA_ATTR_MMIO)
+				return DMA_MAPPING_ERROR;
 
-		return swiotlb_map(dev, phys, size, dir, attrs);
+			return swiotlb_map(dev, phys, size, dir, attrs);
+		}
+	} else if (attrs & DMA_ATTR_CC_DECRYPTED) {
+		return DMA_MAPPING_ERROR;
 	}
 
 	if (attrs & DMA_ATTR_MMIO) {
 		dma_addr = phys;
 		if (unlikely(!dma_capable(dev, dma_addr, size, false)))
 			goto err_overflow;
+	} else if (attrs & DMA_ATTR_CC_DECRYPTED) {
+		dma_addr = phys_to_dma_unencrypted(dev, phys);
+		if (unlikely(!dma_capable(dev, dma_addr, size, false)))
+			goto err_overflow;
 	} else {
 		dma_addr = phys_to_dma(dev, phys);
 		if (unlikely(!dma_capable(dev, dma_addr, size, true)) ||

---

## [4] Jiri Pirko — 2026-02-09
*Subject: [PATCH 3/5] dma-buf: heaps: use designated initializer for exp_info*

From: Jiri Pirko <jiri@nvidia.com>

Use designated initializer for dma_heap_export_info instead of
separate field assignments and avoid the need to explicitly
zero fields in preparation to follow-up patch.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
 drivers/dma-buf/heaps/cma_heap.c    | 7 ++++---
 drivers/dma-buf/heaps/system_heap.c | 9 ++++-----
 2 files changed, 8 insertions(+), 8 deletions(-)

diff --git a/drivers/dma-buf/heaps/cma_heap.c b/drivers/dma-buf/heaps/cma_heap.c
index 42f88193eab9..d12c98be7fa9 100644
--- a/drivers/dma-buf/heaps/cma_heap.c
+++ b/drivers/dma-buf/heaps/cma_heap.c
@@ -388,7 +388,10 @@ static const struct dma_heap_ops cma_heap_ops = {
 
 static int __init __add_cma_heap(struct cma *cma, const char *name)
 {
-	struct dma_heap_export_info exp_info;
+	struct dma_heap_export_info exp_info = {
+		.name = name,
+		.ops = &cma_heap_ops,
+	};
 	struct cma_heap *cma_heap;
 
 	cma_heap = kzalloc(sizeof(*cma_heap), GFP_KERNEL);
@@ -396,8 +399,6 @@ static int __init __add_cma_heap(struct cma *cma, const char *name)
 		return -ENOMEM;
 	cma_heap->cma = cma;
 
-	exp_info.name = name;
-	exp_info.ops = &cma_heap_ops;
 	exp_info.priv = cma_heap;
 
 	cma_heap->heap = dma_heap_add(&exp_info);
diff --git a/drivers/dma-buf/heaps/system_heap.c b/drivers/dma-buf/heaps/system_heap.c
index 4c782fe33fd4..124dca56e4d8 100644
--- a/drivers/dma-buf/heaps/system_heap.c
+++ b/drivers/dma-buf/heaps/system_heap.c
@@ -427,13 +427,12 @@ static const struct dma_heap_ops system_heap_ops = {
 
 static int __init system_heap_create(void)
 {
-	struct dma_heap_export_info exp_info;
+	struct dma_heap_export_info exp_info = {
+		.name = "system",
+		.ops = &system_heap_ops,
+	};
 	struct dma_heap *sys_heap;
 
-	exp_info.name = "system";
-	exp_info.ops = &system_heap_ops;
-	exp_info.priv = NULL;
-
 	sys_heap = dma_heap_add(&exp_info);
 	if (IS_ERR(sys_heap))
 		return PTR_ERR(sys_heap);

---

## [5] Jiri Pirko — 2026-02-09
*Subject: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap flags*

From: Jiri Pirko <jiri@nvidia.com>

Currently the flags, which are unused, are validated for all heaps.
Since the follow-up patch introduces a flag valid for only one of the
heaps, allow to specify the valid flags per-heap.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
 drivers/dma-buf/dma-heap.c | 5 ++++-
 include/linux/dma-heap.h   | 2 ++
 2 files changed, 6 insertions(+), 1 deletion(-)

diff --git a/drivers/dma-buf/dma-heap.c b/drivers/dma-buf/dma-heap.c
index 8ab49924f8b7..4751bcef4b19 100644
--- a/drivers/dma-buf/dma-heap.c
+++ b/drivers/dma-buf/dma-heap.c
@@ -28,6 +28,7 @@
  * @name:		used for debugging/device-node name
  * @ops:		ops struct for this heap
  * @priv:		private data for this heap
+ * @valid_heap_flags:	valid heap flags for this heap
  * @heap_devt:		heap device node
  * @list:		list head connecting to list of heaps
  * @heap_cdev:		heap char device
@@ -38,6 +39,7 @@ struct dma_heap {
 	const char *name;
 	const struct dma_heap_ops *ops;
 	void *priv;
+	u64 valid_heap_flags;
 	dev_t heap_devt;
 	struct list_head list;
 	struct cdev heap_cdev;
@@ -105,7 +107,7 @@ static long dma_heap_ioctl_allocate(struct file *file, void *data)
 	if (heap_allocation->fd_flags & ~DMA_HEAP_VALID_FD_FLAGS)
 		return -EINVAL;
 
-	if (heap_allocation->heap_flags & ~DMA_HEAP_VALID_HEAP_FLAGS)
+	if (heap_allocation->heap_flags & ~heap->valid_heap_flags)
 		return -EINVAL;
 
 	fd = dma_heap_buffer_alloc(heap, heap_allocation->len,
@@ -246,6 +248,7 @@ struct dma_heap *dma_heap_add(const struct dma_heap_export_info *exp_info)
 	heap->name = exp_info->name;
 	heap->ops = exp_info->ops;
 	heap->priv = exp_info->priv;
+	heap->valid_heap_flags = exp_info->valid_heap_flags;
 
 	/* Find unused minor number */
 	ret = xa_alloc(&dma_heap_minors, &minor, heap,
diff --git a/include/linux/dma-heap.h b/include/linux/dma-heap.h
index 27d15f60950a..7cfb531a9281 100644
--- a/include/linux/dma-heap.h
+++ b/include/linux/dma-heap.h
@@ -31,6 +31,7 @@ struct dma_heap_ops {
  * @name:	used for debugging/device-node name
  * @ops:	ops struct for this heap
  * @priv:	heap exporter private data
+ * @valid_heap_flags:	valid heap flags for this heap
  *
  * Information needed to export a new dmabuf heap.
  */
@@ -38,6 +39,7 @@ struct dma_heap_export_info {
 	const char *name;
 	const struct dma_heap_ops *ops;
 	void *priv;
+	u64 valid_heap_flags;
 };
 
 void *dma_heap_get_drvdata(struct dma_heap *heap);

---

## [6] Jiri Pirko — 2026-02-09
*Subject: [PATCH 5/5] dma-buf: heaps: system: add an option to allocate explicitly decrypted memory*

From: Jiri Pirko <jiri@nvidia.com>

Add a new DMA_HEAP_FLAG_DECRYPTED heap flag to allow userspace to
allocate decrypted (shared) memory from the dma-buf system heap for
confidential computing (CoCo) VMs.

On CoCo VMs, guest memory is encrypted by default. The hardware uses an
encryption bit in page table entries (C-bit on AMD SEV, "shared" bit on
Intel TDX) to control whether a given memory access is encrypted or
decrypted. The kernel's direct map is set up with encryption enabled,
so pages returned by alloc_pages() are encrypted in the direct map
by default. To make this memory usable for devices that do not support
DMA to encrypted memory (no TDISP support), it has to be explicitly
decrypted. A couple of things are needed to properly handle
decrypted memory for the dma-buf use case:

- set_memory_decrypted() on the direct map after allocation:
  Besides clearing the encryption bit in the direct map PTEs, this
  also notifies the hypervisor about the page state change. On free,
  the inverse set_memory_encrypted() must be called before returning
  pages to the allocator. If re-encryption fails, pages
  are intentionally leaked to prevent decrypted memory from being
  reused as private.

- pgprot_decrypted() for userspace and kernel virtual mappings:
  Any new mapping of the decrypted pages, be it to userspace via
  mmap or to kernel vmalloc space via vmap, creates PTEs independent
  of the direct map. These must also have the encryption bit cleared,
  otherwise accesses through them would see encrypted (garbage) data.

- DMA_ATTR_CC_DECRYPTED for DMA mapping:
  Since the pages are already decrypted, the DMA API needs to be
  informed via DMA_ATTR_CC_DECRYPTED so it can map them correctly
  as unencrypted for device access.

On non-CoCo VMs the flag is rejected with -EOPNOTSUPP to prevent
misuse by userspace that does not understand the security implications
of explicitly decrypted memory.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
 drivers/dma-buf/heaps/system_heap.c | 87 +++++++++++++++++++++++++++--
 include/linux/dma-heap.h            |  1 +
 include/uapi/linux/dma-heap.h       | 12 +++-
 3 files changed, 94 insertions(+), 6 deletions(-)

diff --git a/drivers/dma-buf/heaps/system_heap.c b/drivers/dma-buf/heaps/system_heap.c
index 124dca56e4d8..0f80ecb660ec 100644
--- a/drivers/dma-buf/heaps/system_heap.c
+++ b/drivers/dma-buf/heaps/system_heap.c
@@ -10,6 +10,7 @@
  *	Andrew F. Davis <afd@ti.com>
  */
 
+#include <linux/cc_platform.h>
 #include <linux/dma-buf.h>
 #include <linux/dma-mapping.h>
 #include <linux/dma-heap.h>
@@ -17,7 +18,9 @@
 #include <linux/highmem.h>
 #include <linux/mm.h>
 #include <linux/module.h>
+#include <linux/pgtable.h>
 #include <linux/scatterlist.h>
+#include <linux/set_memory.h>
 #include <linux/slab.h>
 #include <linux/vmalloc.h>
 
@@ -29,6 +32,7 @@ struct system_heap_buffer {
 	struct sg_table sg_table;
 	int vmap_cnt;
 	void *vaddr;
+	bool decrypted;
 };
 
 struct dma_heap_attachment {
@@ -36,6 +40,7 @@ struct dma_heap_attachment {
 	struct sg_table table;
 	struct list_head list;
 	bool mapped;
+	bool decrypted;
 };
 
 #define LOW_ORDER_GFP (GFP_HIGHUSER | __GFP_ZERO)
@@ -52,6 +57,34 @@ static gfp_t order_flags[] = {HIGH_ORDER_GFP, HIGH_ORDER_GFP, LOW_ORDER_GFP};
 static const unsigned int orders[] = {8, 4, 0};
 #define NUM_ORDERS ARRAY_SIZE(orders)
 
+static int system_heap_set_page_decrypted(struct page *page)
+{
+	unsigned long addr = (unsigned long)page_address(page);
+	unsigned int nr_pages = 1 << compound_order(page);
+	int ret;
+
+	ret = set_memory_decrypted(addr, nr_pages);
+	if (ret)
+		pr_warn_ratelimited("dma-buf system heap: failed to decrypt page at %p\n",
+				    page_address(page));
+
+	return ret;
+}
+
+static int system_heap_set_page_encrypted(struct page *page)
+{
+	unsigned long addr = (unsigned long)page_address(page);
+	unsigned int nr_pages = 1 << compound_order(page);
+	int ret;
+
+	ret = set_memory_encrypted(addr, nr_pages);
+	if (ret)
+		pr_warn_ratelimited("dma-buf system heap: failed to re-encrypt page at %p, leaking memory\n",
+				    page_address(page));
+
+	return ret;
+}
+
 static int dup_sg_table(struct sg_table *from, struct sg_table *to)
 {
 	struct scatterlist *sg, *new_sg;
@@ -90,6 +123,7 @@ static int system_heap_attach(struct dma_buf *dmabuf,
 	a->dev = attachment->dev;
 	INIT_LIST_HEAD(&a->list);
 	a->mapped = false;
+	a->decrypted = buffer->decrypted;
 
 	attachment->priv = a;
 
@@ -119,9 +153,11 @@ static struct sg_table *system_heap_map_dma_buf(struct dma_buf_attachment *attac
 {
 	struct dma_heap_attachment *a = attachment->priv;
 	struct sg_table *table = &a->table;
+	unsigned long attrs;
 	int ret;
 
-	ret = dma_map_sgtable(attachment->dev, table, direction, 0);
+	attrs = a->decrypted ? DMA_ATTR_CC_DECRYPTED : 0;
+	ret = dma_map_sgtable(attachment->dev, table, direction, attrs);
 	if (ret)
 		return ERR_PTR(ret);
 
@@ -188,8 +224,13 @@ static int system_heap_mmap(struct dma_buf *dmabuf, struct vm_area_struct *vma)
 	unsigned long addr = vma->vm_start;
 	unsigned long pgoff = vma->vm_pgoff;
 	struct scatterlist *sg;
+	pgprot_t prot;
 	int i, ret;
 
+	prot = vma->vm_page_prot;
+	if (buffer->decrypted)
+		prot = pgprot_decrypted(prot);
+
 	for_each_sgtable_sg(table, sg, i) {
 		unsigned long n = sg->length >> PAGE_SHIFT;
 
@@ -206,8 +247,7 @@ static int system_heap_mmap(struct dma_buf *dmabuf, struct vm_area_struct *vma)
 		if (addr + size > vma->vm_end)
 			size = vma->vm_end - addr;
 
-		ret = remap_pfn_range(vma, addr, page_to_pfn(page),
-				size, vma->vm_page_prot);
+		ret = remap_pfn_range(vma, addr, page_to_pfn(page), size, prot);
 		if (ret)
 			return ret;
 
@@ -225,6 +265,7 @@ static void *system_heap_do_vmap(struct system_heap_buffer *buffer)
 	struct page **pages = vmalloc(sizeof(struct page *) * npages);
 	struct page **tmp = pages;
 	struct sg_page_iter piter;
+	pgprot_t prot;
 	void *vaddr;
 
 	if (!pages)
@@ -235,7 +276,10 @@ static void *system_heap_do_vmap(struct system_heap_buffer *buffer)
 		*tmp++ = sg_page_iter_page(&piter);
 	}
 
-	vaddr = vmap(pages, npages, VM_MAP, PAGE_KERNEL);
+	prot = PAGE_KERNEL;
+	if (buffer->decrypted)
+		prot = pgprot_decrypted(prot);
+	vaddr = vmap(pages, npages, VM_MAP, prot);
 	vfree(pages);
 
 	if (!vaddr)
@@ -296,6 +340,14 @@ static void system_heap_dma_buf_release(struct dma_buf *dmabuf)
 	for_each_sgtable_sg(table, sg, i) {
 		struct page *page = sg_page(sg);
 
+		/*
+		 * Intentionally leak pages that cannot be re-encrypted
+		 * to prevent decrypted memory from being reused.
+		 */
+		if (buffer->decrypted &&
+		    system_heap_set_page_encrypted(page))
+			continue;
+
 		__free_pages(page, compound_order(page));
 	}
 	sg_free_table(table);
@@ -344,6 +396,7 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	DEFINE_DMA_BUF_EXPORT_INFO(exp_info);
 	unsigned long size_remaining = len;
 	unsigned int max_order = orders[0];
+	bool decrypted = heap_flags & DMA_HEAP_FLAG_DECRYPTED;
 	struct dma_buf *dmabuf;
 	struct sg_table *table;
 	struct scatterlist *sg;
@@ -351,6 +404,15 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	struct page *page, *tmp_page;
 	int i, ret = -ENOMEM;
 
+	if (decrypted) {
+		if (!cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+			return ERR_PTR(-EOPNOTSUPP);
+#ifdef CONFIG_HIGHMEM
+		/* Sanity check, should not happen. */
+		return ERR_PTR(-EINVAL);
+#endif
+	}
+
 	buffer = kzalloc(sizeof(*buffer), GFP_KERNEL);
 	if (!buffer)
 		return ERR_PTR(-ENOMEM);
@@ -359,6 +421,7 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	mutex_init(&buffer->lock);
 	buffer->heap = heap;
 	buffer->len = len;
+	buffer->decrypted = decrypted;
 
 	INIT_LIST_HEAD(&pages);
 	i = 0;
@@ -393,6 +456,14 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 		list_del(&page->lru);
 	}
 
+	if (decrypted) {
+		for_each_sgtable_sg(table, sg, i) {
+			ret = system_heap_set_page_decrypted(sg_page(sg));
+			if (ret)
+				goto free_pages;
+		}
+	}
+
 	/* create the dmabuf */
 	exp_info.exp_name = dma_heap_get_name(heap);
 	exp_info.ops = &system_heap_buf_ops;
@@ -410,6 +481,13 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	for_each_sgtable_sg(table, sg, i) {
 		struct page *p = sg_page(sg);
 
+		/*
+		 * Intentionally leak pages that cannot be re-encrypted
+		 * to prevent decrypted memory from being reused.
+		 */
+		if (buffer->decrypted &&
+		    system_heap_set_page_encrypted(p))
+			continue;
 		__free_pages(p, compound_order(p));
 	}
 	sg_free_table(table);
@@ -430,6 +508,7 @@ static int __init system_heap_create(void)
 	struct dma_heap_export_info exp_info = {
 		.name = "system",
 		.ops = &system_heap_ops,
+		.valid_heap_flags = DMA_HEAP_FLAG_DECRYPTED,
 	};
 	struct dma_heap *sys_heap;
 
diff --git a/include/linux/dma-heap.h b/include/linux/dma-heap.h
index 7cfb531a9281..295a7eaa19ca 100644
--- a/include/linux/dma-heap.h
+++ b/include/linux/dma-heap.h
@@ -10,6 +10,7 @@
 #define _DMA_HEAPS_H
 
 #include <linux/types.h>
+#include <uapi/linux/dma-heap.h>
 
 struct dma_heap;
 
diff --git a/include/uapi/linux/dma-heap.h b/include/uapi/linux/dma-heap.h
index a4cf716a49fa..6552c88e52f6 100644
--- a/include/uapi/linux/dma-heap.h
+++ b/include/uapi/linux/dma-heap.h
@@ -18,8 +18,16 @@
 /* Valid FD_FLAGS are O_CLOEXEC, O_RDONLY, O_WRONLY, O_RDWR */
 #define DMA_HEAP_VALID_FD_FLAGS (O_CLOEXEC | O_ACCMODE)
 
-/* Currently no heap flags */
-#define DMA_HEAP_VALID_HEAP_FLAGS (0ULL)
+/**
+ * DMA_HEAP_FLAG_DECRYPTED - Allocate decrypted (shared) memory
+ *
+ * For confidential computing guests (AMD SEV, Intel TDX), this flag
+ * requests that the allocated memory be marked as decrypted (shared
+ * with the host).
+ */
+#define DMA_HEAP_FLAG_DECRYPTED		(1ULL << 0)
+
+#define DMA_HEAP_VALID_HEAP_FLAGS (DMA_HEAP_FLAG_DECRYPTED)
 
 /**
  * struct dma_heap_allocation_data - metadata passed from userspace for

---

## [7] John Stultz — 2026-02-09
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap flags*

On Mon, Feb 9, 2026 at 7:38 AM Jiri Pirko <jiri@resnulli.us> wrote:
>
> From: Jiri Pirko <jiri@nvidia.com>

I'm not really in this space anymore, so take my feedback with a grain of salt.

While the heap allocate flags argument is unused, it was intended to
be used for generic allocation flags that would apply to all or at
least a wide majority of heaps.

It was definitely not added to allow for per-heap or heap specific
flags (as this patch tries to utilize it). That was the mess we had
with ION driver that we were trying to avoid.

The intent of dma-buf heaps is to try to abstract all the different
device memory constraints so there only needs to be a [usage] ->
[heap] mapping, and otherwise userland can be generalized so that it
doesn't need to be re-written to work with different devices/memory
types.  Adding heap-specific allocation flags prevents that
generalization.

So instead of adding heap specific flags, the general advice has been
to add a separate heap name for the flag property.

Now, there has been many discussions around "protected buffers" (which
doesn't seem to map exactly to this confidental computing primitive,
but sounds like it might be related) , which have bounced between
being a allocation flag or a device specific heap without much
resolution. I appreciate in this patch seires you've pushed your
concept down into a DMA_ATTR_, as I do feel the kernel should have a
deeper sense of protected buffers (or any general propery like this)
as a concept if it is going to be a generic allocation flag, instead
of it being a somewhat thin creation of the outer heap-driver layer.

But, it seems like the use case here is still far too narrow for a top
level allocation flag.

So I'd advocate against introducing heap-specific flags like this.

thanks
-john

---

## [8] Jason Gunthorpe — 2026-02-09
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap
 flags*

On Mon, Feb 09, 2026 at 12:08:03PM -0800, John Stultz wrote:
> On Mon, Feb 9, 2026 at 7:38 AM Jiri Pirko <jiri@resnulli.us> wrote:
> >

I don't know alot about DMA heaps..

On a CC VM system the shared/private property is universal and applies
to every physical address. Not every address can dynamically change
between shared and private, but every address does have a
shared/private state.

By default userspace process generally run exclusively in private
memory and there are very few ways for userspace to even access shared
memory.

From a heaps perspective the API would be very strange, and perhaps
even security dangerous, if it is returning shared memory to userspace
without userspace knowing this is happening.

I'd advocate that the right design is for userspace to positively
signal via this flag that it wants/accepts shared memory and without
the flag shared memory should never be returned.

Even if the underyling heap only has shared memory in it (eg it is
mmio or something).

Otherwise making it implicit, perhaps based on heap name, sounds very
tricky for userspace to actually use fully securely.

Again, I don't know alot about heaps, but perhaps the missing part
here is that on a CC system all existing heaps, other than the one
using normal system pages, should be disabled for now. They can come
back once they are audited as to their shared/private state and
respect the new flag.

Another view is to ignore this affirmative handshake and just make it
implicit on something like the heap name and hope userspace lucks into
something that works for it, and doesn't accidently place, or become
tricked into placing, sensitive information into shared heap memory.

Again I know nothing about heaps, but this is a fuller picture of the
security sensitivity and what to think about with heaps and CC VM
systems.

> Now, there has been many discussions around "protected buffers" (which
> doesn't seem to map exactly to this confidental computing primitive,

I'm not sure what protected buffers are, but this CC VM shared/private
(or encrypted/decrypted) is a core kernel property that applies to
every physical address in the CC VM.

I assume protected buffers are something more platform specific and
hidden?

> But, it seems like the use case here is still far too narrow for a top
> level allocation flag.

CC certainly is a narrow use case, but within CC I don't think it is
narrow at all..

Jason

---

## [9] Jiri Pirko — 2026-02-10
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap
 flags*

Mon, Feb 09, 2026 at 09:08:03PM +0100, jstultz@google.com wrote:
>On Mon, Feb 9, 2026 at 7:38 AM Jiri Pirko <jiri@resnulli.us> wrote:
>>

Right, my original idea was to add a separate heap. Then I spotted the
flags and seemed like a great fit. Was not aware or the history or
original intention. Would be probably good to document it for
future generations.

So instead of flag, I will add heap named something
like "system_cc_decrypted" to implement this.

Thanks!

---

## [10] Jiri Pirko — 2026-02-10
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap
 flags*

Tue, Feb 10, 2026 at 01:29:27AM +0100, jgg@ziepe.ca wrote:
>On Mon, Feb 09, 2026 at 12:08:03PM -0800, John Stultz wrote:
>> On Mon, Feb 9, 2026 at 7:38 AM Jiri Pirko <jiri@resnulli.us> wrote:

We can have the same behaviour with the separate heap, can't we?
Userpace positively signals it wants/accepts the shared memory by
choosing "system_cc_decrypted" heap name.

[...]

---

## [11] kernel test robot — 2026-02-10
*Subject: Re: [PATCH 5/5] dma-buf: heaps: system: add an option to allocate
 explicitly decrypted memory*

Hi Jiri,

kernel test robot noticed the following build errors:

[auto build test ERROR on drm-misc/drm-misc-next]
[also build test ERROR on drm-tip/drm-tip trace/for-next linus/master v6.19]
[cannot apply to next-20260209]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Jiri-Pirko/dma-mapping-avoid-random-addr-value-print-out-on-error-path/20260209-234013
base:   https://gitlab.freedesktop.org/drm/misc/kernel.git drm-misc-next
patch link:    https://lore.kernel.org/r/20260209153809.250835-6-jiri%40resnulli.us
patch subject: [PATCH 5/5] dma-buf: heaps: system: add an option to allocate explicitly decrypted memory
config: s390-allmodconfig (https://download.01.org/0day-ci/archive/20260210/202602101926.lsquJdb1-lkp@intel.com/config)
compiler: clang version 18.1.8 (https://github.com/llvm/llvm-project 3b5b5c1ec4a3095ab096dd780e84d7ab81f3d7ff)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260210/202602101926.lsquJdb1-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202602101926.lsquJdb1-lkp@intel.com/

All errors (new ones prefixed by >>):

>> drivers/dma-buf/heaps/system_heap.c:66:8: error: call to undeclared function 'set_memory_decrypted'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
      66 |         ret = set_memory_decrypted(addr, nr_pages);
         |               ^
>> drivers/dma-buf/heaps/system_heap.c:80:8: error: call to undeclared function 'set_memory_encrypted'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
      80 |         ret = set_memory_encrypted(addr, nr_pages);
         |               ^
   2 errors generated.


vim +/set_memory_decrypted +66 drivers/dma-buf/heaps/system_heap.c

    59	
    60	static int system_heap_set_page_decrypted(struct page *page)
    61	{
    62		unsigned long addr = (unsigned long)page_address(page);
    63		unsigned int nr_pages = 1 << compound_order(page);
    64		int ret;
    65	
  > 66		ret = set_memory_decrypted(addr, nr_pages);
    67		if (ret)
    68			pr_warn_ratelimited("dma-buf system heap: failed to decrypt page at %p\n",
    69					    page_address(page));
    70	
    71		return ret;
    72	}
    73	
    74	static int system_heap_set_page_encrypted(struct page *page)
    75	{
    76		unsigned long addr = (unsigned long)page_address(page);
    77		unsigned int nr_pages = 1 << compound_order(page);
    78		int ret;
    79	
  > 80		ret = set_memory_encrypted(addr, nr_pages);
    81		if (ret)
    82			pr_warn_ratelimited("dma-buf system heap: failed to re-encrypt page at %p, leaking memory\n",
    83					    page_address(page));
    84	
    85		return ret;
    86	}
    87

---

## [12] Jason Gunthorpe — 2026-02-10
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap
 flags*

On Tue, Feb 10, 2026 at 10:14:08AM +0100, Jiri Pirko wrote:

> >I'd advocate that the right design is for userspace to positively
> >signal via this flag that it wants/accepts shared memory and without

So what do the other heap names do? Always private? Do you ever get
heaps that are unknowably private or shared (eg MMIO backed?)

Jason

---

## [13] Leon Romanovsky — 2026-02-10
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap
 flags*

On Tue, Feb 10, 2026 at 10:05:14AM +0100, Jiri Pirko wrote:
> Mon, Feb 09, 2026 at 09:08:03PM +0100, jstultz@google.com wrote:
> >On Mon, Feb 9, 2026 at 7:38 AM Jiri Pirko <jiri@resnulli.us> wrote:

It is problematic to expose a user‑visible API that depends on a name.
Such a design limits our ability to extend the functionality in the
future, should new use cases arise.

Thanks

> 
> Thanks!

---

## [14] Jiri Pirko — 2026-02-10
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap
 flags*

Tue, Feb 10, 2026 at 01:43:57PM +0100, jgg@ziepe.ca wrote:
>On Tue, Feb 10, 2026 at 10:14:08AM +0100, Jiri Pirko wrote:
>

If I understand the code correctly, you may get something like this:
$ ls /dev/dma_heap/
default_cma_region
protected,secure-video
protected,secure-video-record
protected,trusted-ui
system

The "protected*" ones are created by tee. I believe they handle
memory that is inaccesible to CPU.

---

## [15] Jason Gunthorpe — 2026-02-10
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap
 flags*

On Tue, Feb 10, 2026 at 03:49:02PM +0100, Jiri Pirko wrote:
> Tue, Feb 10, 2026 at 01:43:57PM +0100, jgg@ziepe.ca wrote:
> >On Tue, Feb 10, 2026 at 10:14:08AM +0100, Jiri Pirko wrote:

If that is the only list of options then maybe just the name will work
Ok.

I *think* CMA and system should be reliably CC private.

The protected ones seem to have their own internal definition, and
probably can't exist on CC VM systems..

Meaning we don't have any shared things leaking through which would be
the point.

Jason

---

## [16] kernel test robot — 2026-02-11
*Subject: Re: [PATCH 5/5] dma-buf: heaps: system: add an option to allocate
 explicitly decrypted memory*

Hi Jiri,

kernel test robot noticed the following build errors:

[auto build test ERROR on drm-misc/drm-misc-next]
[also build test ERROR on drm-tip/drm-tip trace/for-next linus/master v6.19]
[cannot apply to next-20260209]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Jiri-Pirko/dma-mapping-avoid-random-addr-value-print-out-on-error-path/20260209-234013
base:   https://gitlab.freedesktop.org/drm/misc/kernel.git drm-misc-next
patch link:    https://lore.kernel.org/r/20260209153809.250835-6-jiri%40resnulli.us
patch subject: [PATCH 5/5] dma-buf: heaps: system: add an option to allocate explicitly decrypted memory
config: s390-allyesconfig (https://download.01.org/0day-ci/archive/20260211/202602110149.tBUPP0bh-lkp@intel.com/config)
compiler: s390-linux-gcc (GCC) 15.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260211/202602110149.tBUPP0bh-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202602110149.tBUPP0bh-lkp@intel.com/

All errors (new ones prefixed by >>):

   drivers/dma-buf/heaps/system_heap.c: In function 'system_heap_set_page_decrypted':
>> drivers/dma-buf/heaps/system_heap.c:66:15: error: implicit declaration of function 'set_memory_decrypted' [-Wimplicit-function-declaration]
      66 |         ret = set_memory_decrypted(addr, nr_pages);
         |               ^~~~~~~~~~~~~~~~~~~~
   drivers/dma-buf/heaps/system_heap.c: In function 'system_heap_set_page_encrypted':
>> drivers/dma-buf/heaps/system_heap.c:80:15: error: implicit declaration of function 'set_memory_encrypted' [-Wimplicit-function-declaration]
      80 |         ret = set_memory_encrypted(addr, nr_pages);
         |               ^~~~~~~~~~~~~~~~~~~~


vim +/set_memory_decrypted +66 drivers/dma-buf/heaps/system_heap.c

    59	
    60	static int system_heap_set_page_decrypted(struct page *page)
    61	{
    62		unsigned long addr = (unsigned long)page_address(page);
    63		unsigned int nr_pages = 1 << compound_order(page);
    64		int ret;
    65	
  > 66		ret = set_memory_decrypted(addr, nr_pages);
    67		if (ret)
    68			pr_warn_ratelimited("dma-buf system heap: failed to decrypt page at %p\n",
    69					    page_address(page));
    70	
    71		return ret;
    72	}
    73	
    74	static int system_heap_set_page_encrypted(struct page *page)
    75	{
    76		unsigned long addr = (unsigned long)page_address(page);
    77		unsigned int nr_pages = 1 << compound_order(page);
    78		int ret;
    79	
  > 80		ret = set_memory_encrypted(addr, nr_pages);
    81		if (ret)
    82			pr_warn_ratelimited("dma-buf system heap: failed to re-encrypt page at %p, leaking memory\n",
    83					    page_address(page));
    84	
    85		return ret;
    86	}
    87

---

## [17] John Stultz — 2026-02-10
*Subject: Re: [PATCH 4/5] dma-buf: heaps: allow heap to specify valid heap flags*

On Tue, Feb 10, 2026 at 4:48 AM Leon Romanovsky <leon@kernel.org> wrote:
> On Tue, Feb 10, 2026 at 10:05:14AM +0100, Jiri Pirko wrote:
> > Mon, Feb 09, 2026 at 09:08:03PM +0100, jstultz@google.com wrote:

Yes, how userland chooses a heap name is an open problem.

 The difficulty is that userland is the only thing that knows what
devices the buffer will be shared (and this knowledge may be
incomplete if userland passes a buffer between processes) with, so it
has to pick.  But the kernel doesn't give it a way to solve the
constraints of what memory types work with what devices. There have
been some proposals for device sysfs directories to have links to heap
types they support, but that also requires every driver to understand
every heap type. And then you get to the fact that performance is what
folks really want, not compatibility and that may require some system
specific knowledge to decide.

The working solution right now is to have the system provide a  [use]
-> [heap] mapping for a specific system.

I think of this as similar to the vfs and /etc/fstab. So /home/ might
be /dev/sdb1 on one device or dev/sda1 on another.  You need some
system specific configuration.

In Android, this mapping is done by Gralloc, so buffers are requested
for a use and then Gralloc decides which heap to allocated from.

Unfortunately there doesn't seem to be a similar standard convention
elsewhere.  And I'll admit even then the enumeration of uses/pipelines
in some general form is also difficult problem (and is somewhat more
bounded for Android).

thanks
-john

---

## [18] Marek Szyprowski — 2026-02-12
*Subject: Re: [PATCH 1/5] dma-mapping: avoid random addr value print out on
 error path*

On 09.02.2026 16:38, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
>

I will take this patch when v7.0-rc1 is out, as this fix definitely has 
to be applied regardless of the discussion about the remaining patches.

> ---
>   kernel/dma/direct.h | 2 +-

Best regards

---

## [19] Jiri Pirko — 2026-02-12
*Subject: Re: [PATCH 1/5] dma-mapping: avoid random addr value print out on
 error path*

Thu, Feb 12, 2026 at 12:03:49PM +0100, m.szyprowski@samsung.com wrote:
>On 09.02.2026 16:38, Jiri Pirko wrote:
>> From: Jiri Pirko <jiri@nvidia.com>

Makes sense. Thanks!

---

## [20] Marek Szyprowski — 2026-02-23
*Subject: Re: [PATCH 1/5] dma-mapping: avoid random addr value print out on
 error path*

On 09.02.2026 16:38, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
>

Applied to dma-mapping-fixes, thanks!

> ---
>   kernel/dma/direct.h | 2 +-

Best regards

---
