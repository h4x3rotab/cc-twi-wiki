---
title: 'dma-buf: heaps: system: add an option to allocate explicitly shared/decrypted memory'
date: 2026-03-25
last_reply: 2026-04-26
message_count: 25
participants: ['Jiri Pirko', 'Marek Szyprowski', 'Jason Gunthorpe', 'T.J. Mercier', 'Jason Gunthorpe', 'Sumit Semwal', 'Brian Starkey', 'Maxime Ripard', 'Aneesh Kumar K.V', 'Petr Tesarik']
---

## [1] Jiri Pirko — 2026-03-25

From: Jiri Pirko <jiri@nvidia.com>

Confidential computing (CoCo) VMs/guests, such as AMD SEV and Intel TDX,
run with private/encrypted memory which creates a challenge
for devices that do not support DMA to it (no TDISP support).

For kernel-only DMA operations, swiotlb bounce buffering provides a
transparent solution by copying data through shared memory.
However, the only way to get this memory into userspace is via the DMA
API's dma_alloc_pages()/dma_mmap_pages() type interfaces which limits
the use of the memory to a single DMA device, and is incompatible with
pin_user_pages().

These limitations are particularly problematic for the RDMA subsystem
which makes heavy use of pin_user_pages() and expects flexible memory
usage between many different DMA devices.

This patch series enables userspace to explicitly request shared
(decrypted) memory allocations from new dma-buf system_cc_shared heap.
Userspace can mmap this memory and pass the dma-buf fd to other
existing importers such as RDMA or DRM devices to access the
memory. The DMA API is improved to allow the dma heap exporter to DMA
map the shared memory to each importing device.

Based on dma-mapping-for-next e7442a68cd1ee797b585f045d348781e9c0dde0d

Jiri Pirko (2):
  dma-mapping: introduce DMA_ATTR_CC_SHARED for shared memory
  dma-buf: heaps: system: add system_cc_shared heap for explicitly
    shared memory

 drivers/dma-buf/heaps/system_heap.c | 103 ++++++++++++++++++++++++++--
 include/linux/dma-mapping.h         |  10 +++
 include/trace/events/dma.h          |   3 +-
 kernel/dma/direct.h                 |  14 +++-
 kernel/dma/mapping.c                |  13 +++-
 5 files changed, 132 insertions(+), 11 deletions(-)

---

## [2] Jiri Pirko — 2026-03-25
*Subject: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for shared memory*

From: Jiri Pirko <jiri@nvidia.com>

Current CC designs don't place a vIOMMU in front of untrusted devices.
Instead, the DMA API forces all untrusted device DMA through swiotlb
bounce buffers (is_swiotlb_force_bounce()) which copies data into
shared memory on behalf of the device.

When a caller has already arranged for the memory to be shared
via set_memory_decrypted(), the DMA API needs to know so it can map
directly using the unencrypted physical address rather than bounce
buffering. Following the pattern of DMA_ATTR_MMIO, add
DMA_ATTR_CC_SHARED for this purpose. Like the MMIO case, only the
caller knows what kind of memory it has and must inform the DMA API
for it to work correctly.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
v4->v5:
- rebased on top od dma-mapping-for-next
- s/decrypted/shared/
v3->v4:
- added some sanity checks to dma_map_phys and dma_unmap_phys
- enhanced documentation of DMA_ATTR_CC_DECRYPTED attr
v1->v2:
- rebased on top of recent dma-mapping-fixes
---
 include/linux/dma-mapping.h | 10 ++++++++++
 include/trace/events/dma.h  |  3 ++-
 kernel/dma/direct.h         | 14 +++++++++++---
 kernel/dma/mapping.c        | 13 +++++++++++--
 4 files changed, 34 insertions(+), 6 deletions(-)

diff --git a/include/linux/dma-mapping.h b/include/linux/dma-mapping.h
index 677c51ab7510..db8ab24a54f4 100644
--- a/include/linux/dma-mapping.h
+++ b/include/linux/dma-mapping.h
@@ -92,6 +92,16 @@
  * flushing.
  */
 #define DMA_ATTR_REQUIRE_COHERENT	(1UL << 12)
+/*
+ * DMA_ATTR_CC_SHARED: Indicates the DMA mapping is shared (decrypted) for
+ * confidential computing guests. For normal system memory the caller must have
+ * called set_memory_decrypted(), and pgprot_decrypted must be used when
+ * creating CPU PTEs for the mapping. The same shared semantic may be passed
+ * to the vIOMMU when it sets up the IOPTE. For MMIO use together with
+ * DMA_ATTR_MMIO to indicate shared MMIO. Unless DMA_ATTR_MMIO is provided
+ * a struct page is required.
+ */
+#define DMA_ATTR_CC_SHARED	(1UL << 13)
 
 /*
  * A dma_addr_t can hold any valid DMA or bus address for the platform.  It can
diff --git a/include/trace/events/dma.h b/include/trace/events/dma.h
index 63597b004424..31c9ddf72c9d 100644
--- a/include/trace/events/dma.h
+++ b/include/trace/events/dma.h
@@ -34,7 +34,8 @@ TRACE_DEFINE_ENUM(DMA_NONE);
 		{ DMA_ATTR_PRIVILEGED, "PRIVILEGED" }, \
 		{ DMA_ATTR_MMIO, "MMIO" }, \
 		{ DMA_ATTR_DEBUGGING_IGNORE_CACHELINES, "CACHELINES_OVERLAP" }, \
-		{ DMA_ATTR_REQUIRE_COHERENT, "REQUIRE_COHERENT" })
+		{ DMA_ATTR_REQUIRE_COHERENT, "REQUIRE_COHERENT" }, \
+		{ DMA_ATTR_CC_SHARED, "CC_SHARED" })
 
 DECLARE_EVENT_CLASS(dma_map,
 	TP_PROTO(struct device *dev, phys_addr_t phys_addr, dma_addr_t dma_addr,
diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
index b86ff65496fc..7140c208c123 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -89,16 +89,24 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
 	dma_addr_t dma_addr;
 
 	if (is_swiotlb_force_bounce(dev)) {
-		if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
-			return DMA_MAPPING_ERROR;
+		if (!(attrs & DMA_ATTR_CC_SHARED)) {
+			if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
+				return DMA_MAPPING_ERROR;
 
-		return swiotlb_map(dev, phys, size, dir, attrs);
+			return swiotlb_map(dev, phys, size, dir, attrs);
+		}
+	} else if (attrs & DMA_ATTR_CC_SHARED) {
+		return DMA_MAPPING_ERROR;
 	}
 
 	if (attrs & DMA_ATTR_MMIO) {
 		dma_addr = phys;
 		if (unlikely(!dma_capable(dev, dma_addr, size, false)))
 			goto err_overflow;
+	} else if (attrs & DMA_ATTR_CC_SHARED) {
+		dma_addr = phys_to_dma_unencrypted(dev, phys);
+		if (unlikely(!dma_capable(dev, dma_addr, size, false)))
+			goto err_overflow;
 	} else {
 		dma_addr = phys_to_dma(dev, phys);
 		if (unlikely(!dma_capable(dev, dma_addr, size, true)) ||
diff --git a/kernel/dma/mapping.c b/kernel/dma/mapping.c
index df3eccc7d4ca..23ed8eb9233e 100644
--- a/kernel/dma/mapping.c
+++ b/kernel/dma/mapping.c
@@ -157,6 +157,7 @@ dma_addr_t dma_map_phys(struct device *dev, phys_addr_t phys, size_t size,
 {
 	const struct dma_map_ops *ops = get_dma_ops(dev);
 	bool is_mmio = attrs & DMA_ATTR_MMIO;
+	bool is_cc_shared = attrs & DMA_ATTR_CC_SHARED;
 	dma_addr_t addr = DMA_MAPPING_ERROR;
 
 	BUG_ON(!valid_dma_direction(dir));
@@ -168,8 +169,11 @@ dma_addr_t dma_map_phys(struct device *dev, phys_addr_t phys, size_t size,
 		return DMA_MAPPING_ERROR;
 
 	if (dma_map_direct(dev, ops) ||
-	    (!is_mmio && arch_dma_map_phys_direct(dev, phys + size)))
+	    (!is_mmio && !is_cc_shared &&
+	     arch_dma_map_phys_direct(dev, phys + size)))
 		addr = dma_direct_map_phys(dev, phys, size, dir, attrs, true);
+	else if (is_cc_shared)
+		return DMA_MAPPING_ERROR;
 	else if (use_dma_iommu(dev))
 		addr = iommu_dma_map_phys(dev, phys, size, dir, attrs);
 	else if (ops->map_phys)
@@ -206,11 +210,16 @@ void dma_unmap_phys(struct device *dev, dma_addr_t addr, size_t size,
 {
 	const struct dma_map_ops *ops = get_dma_ops(dev);
 	bool is_mmio = attrs & DMA_ATTR_MMIO;
+	bool is_cc_shared = attrs & DMA_ATTR_CC_SHARED;
 
 	BUG_ON(!valid_dma_direction(dir));
+
 	if (dma_map_direct(dev, ops) ||
-	    (!is_mmio && arch_dma_unmap_phys_direct(dev, addr + size)))
+	    (!is_mmio && !is_cc_shared &&
+	     arch_dma_unmap_phys_direct(dev, addr + size)))
 		dma_direct_unmap_phys(dev, addr, size, dir, attrs, true);
+	else if (is_cc_shared)
+		return;
 	else if (use_dma_iommu(dev))
 		iommu_dma_unmap_phys(dev, addr, size, dir, attrs);
 	else if (ops->unmap_phys)

---

## [3] Jiri Pirko — 2026-03-25
*Subject: [PATCH v5 2/2] dma-buf: heaps: system: add system_cc_shared heap for explicitly shared memory*

From: Jiri Pirko <jiri@nvidia.com>

Add a new "system_cc_shared" dma-buf heap to allow userspace to
allocate shared (decrypted) memory for confidential computing (CoCo)
VMs.

On CoCo VMs, guest memory is private by default. The hardware uses an
encryption bit in page table entries (C-bit on AMD SEV, "shared" bit on
Intel TDX) to control whether a given memory access is private or
shared. The kernel's direct map is set up as private,
so pages returned by alloc_pages() are private in the direct map
by default. To make this memory usable for devices that do not support
DMA to private memory (no TDISP support), it has to be explicitly
shared. A couple of things are needed to properly handle
shared memory for the dma-buf use case:

- set_memory_decrypted() on the direct map after allocation:
  Besides clearing the encryption bit in the direct map PTEs, this
  also notifies the hypervisor about the page state change. On free,
  the inverse set_memory_encrypted() must be called before returning
  pages to the allocator. If re-encryption fails, pages
  are intentionally leaked to prevent shared memory from being
  reused as private.

- pgprot_decrypted() for userspace and kernel virtual mappings:
  Any new mapping of the shared pages, be it to userspace via
  mmap or to kernel vmalloc space via vmap, creates PTEs independent
  of the direct map. These must also have the encryption bit cleared,
  otherwise accesses through them would see encrypted (garbage) data.

- DMA_ATTR_CC_SHARED for DMA mapping:
  Since the pages are already shared, the DMA API needs to be
  informed via DMA_ATTR_CC_SHARED so it can map them correctly
  as unencrypted for device access.

On non-CoCo VMs, the system_cc_shared heap is not registered
to prevent misuse by userspace that does not understand
the security implications of explicitly shared memory.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
v4->v5:
- bools renamed: s/decrypted/cc_decrypted/
- other renames: s/decrypted/decrypted/ - this included name of the heap
v2->v3:
- removed couple of leftovers from headers
v1->v2:
- fixed build errors on s390 by including mem_encrypt.h
- converted system heap flag implementation to a separate heap
---
 drivers/dma-buf/heaps/system_heap.c | 103 ++++++++++++++++++++++++++--
 1 file changed, 98 insertions(+), 5 deletions(-)

diff --git a/drivers/dma-buf/heaps/system_heap.c b/drivers/dma-buf/heaps/system_heap.c
index b3650d8fd651..03c2b87cb111 100644
--- a/drivers/dma-buf/heaps/system_heap.c
+++ b/drivers/dma-buf/heaps/system_heap.c
@@ -10,17 +10,25 @@
  *	Andrew F. Davis <afd@ti.com>
  */
 
+#include <linux/cc_platform.h>
 #include <linux/dma-buf.h>
 #include <linux/dma-mapping.h>
 #include <linux/dma-heap.h>
 #include <linux/err.h>
 #include <linux/highmem.h>
+#include <linux/mem_encrypt.h>
 #include <linux/mm.h>
+#include <linux/set_memory.h>
 #include <linux/module.h>
+#include <linux/pgtable.h>
 #include <linux/scatterlist.h>
 #include <linux/slab.h>
 #include <linux/vmalloc.h>
 
+struct system_heap_priv {
+	bool cc_shared;
+};
+
 struct system_heap_buffer {
 	struct dma_heap *heap;
 	struct list_head attachments;
@@ -29,6 +37,7 @@ struct system_heap_buffer {
 	struct sg_table sg_table;
 	int vmap_cnt;
 	void *vaddr;
+	bool cc_shared;
 };
 
 struct dma_heap_attachment {
@@ -36,6 +45,7 @@ struct dma_heap_attachment {
 	struct sg_table table;
 	struct list_head list;
 	bool mapped;
+	bool cc_shared;
 };
 
 #define LOW_ORDER_GFP (GFP_HIGHUSER | __GFP_ZERO)
@@ -52,6 +62,34 @@ static gfp_t order_flags[] = {HIGH_ORDER_GFP, HIGH_ORDER_GFP, LOW_ORDER_GFP};
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
@@ -90,6 +128,7 @@ static int system_heap_attach(struct dma_buf *dmabuf,
 	a->dev = attachment->dev;
 	INIT_LIST_HEAD(&a->list);
 	a->mapped = false;
+	a->cc_shared = buffer->cc_shared;
 
 	attachment->priv = a;
 
@@ -119,9 +158,11 @@ static struct sg_table *system_heap_map_dma_buf(struct dma_buf_attachment *attac
 {
 	struct dma_heap_attachment *a = attachment->priv;
 	struct sg_table *table = &a->table;
+	unsigned long attrs;
 	int ret;
 
-	ret = dma_map_sgtable(attachment->dev, table, direction, 0);
+	attrs = a->cc_shared ? DMA_ATTR_CC_SHARED : 0;
+	ret = dma_map_sgtable(attachment->dev, table, direction, attrs);
 	if (ret)
 		return ERR_PTR(ret);
 
@@ -188,8 +229,13 @@ static int system_heap_mmap(struct dma_buf *dmabuf, struct vm_area_struct *vma)
 	unsigned long addr = vma->vm_start;
 	unsigned long pgoff = vma->vm_pgoff;
 	struct scatterlist *sg;
+	pgprot_t prot;
 	int i, ret;
 
+	prot = vma->vm_page_prot;
+	if (buffer->cc_shared)
+		prot = pgprot_decrypted(prot);
+
 	for_each_sgtable_sg(table, sg, i) {
 		unsigned long n = sg->length >> PAGE_SHIFT;
 
@@ -206,8 +252,7 @@ static int system_heap_mmap(struct dma_buf *dmabuf, struct vm_area_struct *vma)
 		if (addr + size > vma->vm_end)
 			size = vma->vm_end - addr;
 
-		ret = remap_pfn_range(vma, addr, page_to_pfn(page),
-				size, vma->vm_page_prot);
+		ret = remap_pfn_range(vma, addr, page_to_pfn(page), size, prot);
 		if (ret)
 			return ret;
 
@@ -225,6 +270,7 @@ static void *system_heap_do_vmap(struct system_heap_buffer *buffer)
 	struct page **pages = vmalloc(sizeof(struct page *) * npages);
 	struct page **tmp = pages;
 	struct sg_page_iter piter;
+	pgprot_t prot;
 	void *vaddr;
 
 	if (!pages)
@@ -235,7 +281,10 @@ static void *system_heap_do_vmap(struct system_heap_buffer *buffer)
 		*tmp++ = sg_page_iter_page(&piter);
 	}
 
-	vaddr = vmap(pages, npages, VM_MAP, PAGE_KERNEL);
+	prot = PAGE_KERNEL;
+	if (buffer->cc_shared)
+		prot = pgprot_decrypted(prot);
+	vaddr = vmap(pages, npages, VM_MAP, prot);
 	vfree(pages);
 
 	if (!vaddr)
@@ -296,6 +345,14 @@ static void system_heap_dma_buf_release(struct dma_buf *dmabuf)
 	for_each_sgtable_sg(table, sg, i) {
 		struct page *page = sg_page(sg);
 
+		/*
+		 * Intentionally leak pages that cannot be re-encrypted
+		 * to prevent shared memory from being reused.
+		 */
+		if (buffer->cc_shared &&
+		    system_heap_set_page_encrypted(page))
+			continue;
+
 		__free_pages(page, compound_order(page));
 	}
 	sg_free_table(table);
@@ -347,6 +404,8 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	DEFINE_DMA_BUF_EXPORT_INFO(exp_info);
 	unsigned long size_remaining = len;
 	unsigned int max_order = orders[0];
+	struct system_heap_priv *priv = dma_heap_get_drvdata(heap);
+	bool cc_shared = priv->cc_shared;
 	struct dma_buf *dmabuf;
 	struct sg_table *table;
 	struct scatterlist *sg;
@@ -362,6 +421,7 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	mutex_init(&buffer->lock);
 	buffer->heap = heap;
 	buffer->len = len;
+	buffer->cc_shared = cc_shared;
 
 	INIT_LIST_HEAD(&pages);
 	i = 0;
@@ -396,6 +456,14 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 		list_del(&page->lru);
 	}
 
+	if (cc_shared) {
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
@@ -413,6 +481,13 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	for_each_sgtable_sg(table, sg, i) {
 		struct page *p = sg_page(sg);
 
+		/*
+		 * Intentionally leak pages that cannot be re-encrypted
+		 * to prevent shared memory from being reused.
+		 */
+		if (buffer->cc_shared &&
+		    system_heap_set_page_encrypted(p))
+			continue;
 		__free_pages(p, compound_order(p));
 	}
 	sg_free_table(table);
@@ -428,6 +503,14 @@ static const struct dma_heap_ops system_heap_ops = {
 	.allocate = system_heap_allocate,
 };
 
+static struct system_heap_priv system_heap_priv = {
+	.cc_shared = false,
+};
+
+static struct system_heap_priv system_heap_cc_shared_priv = {
+	.cc_shared = true,
+};
+
 static int __init system_heap_create(void)
 {
 	struct dma_heap_export_info exp_info;
@@ -435,8 +518,18 @@ static int __init system_heap_create(void)
 
 	exp_info.name = "system";
 	exp_info.ops = &system_heap_ops;
-	exp_info.priv = NULL;
+	exp_info.priv = &system_heap_priv;
+
+	sys_heap = dma_heap_add(&exp_info);
+	if (IS_ERR(sys_heap))
+		return PTR_ERR(sys_heap);
+
+	if (IS_ENABLED(CONFIG_HIGHMEM) ||
+	    !cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+		return 0;
 
+	exp_info.name = "system_cc_shared";
+	exp_info.priv = &system_heap_cc_shared_priv;
 	sys_heap = dma_heap_add(&exp_info);
 	if (IS_ERR(sys_heap))
 		return PTR_ERR(sys_heap);

---

## [4] Marek Szyprowski — 2026-03-27
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly shared/decrypted memory*

On 25.03.2026 20:23, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
>

I would like to merge this to dma-mapping-next, but I feel a bit 
uncomfortable with my lack of knowledge about CoCo and friends. Could 
those who know a bit more about it provide some Reviewed-by tags?

Best regards

---

## [5] Jason Gunthorpe — 2026-03-27
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to allocate
 explicitly shared/decrypted memory*

On Fri, Mar 27, 2026 at 10:38:10AM +0100, Marek Szyprowski wrote:
> On 25.03.2026 20:23, Jiri Pirko wrote:
> > From: Jiri Pirko <jiri@nvidia.com>

I'm confident in the CC stuff, I was hoping to see someone from dmabuf
heap land ack that the uAPI design is OK.. TJ?

Jason

---

## [6] T.J. Mercier — 2026-03-27
*Subject: Re: [PATCH v5 2/2] dma-buf: heaps: system: add system_cc_shared heap
 for explicitly shared memory*

On Wed, Mar 25, 2026 at 12:23 PM Jiri Pirko <jiri@resnulli.us> wrote:
>
> From: Jiri Pirko <jiri@nvidia.com>

Reviewed-by: T.J. Mercier <tjmercier@google.com>

---

## [7] T.J. Mercier — 2026-03-27
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to allocate
 explicitly shared/decrypted memory*

On Fri, Mar 27, 2026 at 5:10 AM Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Fri, Mar 27, 2026 at 10:38:10AM +0100, Marek Szyprowski wrote:

Hi, yes LGTM. From a uAPI perspective it's just another dma-buf heap.

---

## [8] Jason Gunthorpe — 2026-03-31
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

On Wed, Mar 25, 2026 at 08:23:51PM +0100, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
> 

Reviewed-by: Jason Gunthorpe <jgg@nvidia.com>

Jason

---

## [9] Jason Gunthorpe — 2026-03-31
*Subject: Re: [PATCH v5 2/2] dma-buf: heaps: system: add system_cc_shared heap
 for explicitly shared memory*

On Wed, Mar 25, 2026 at 08:23:52PM +0100, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
> 

Reviewed-by: Jason Gunthorpe <jgg@nvidia.com>

Jason

---

## [10] Sumit Semwal — 2026-04-02
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to allocate
 explicitly shared/decrypted memory*

Hello Jiri,

On Thu, 26 Mar 2026 at 00:53, Jiri Pirko <jiri@resnulli.us> wrote:
>
> From: Jiri Pirko <jiri@nvidia.com>

Thank you for the patch series, it looks good to me.

Marek, if you are ok, please could you take it through your tree, with my
Acked-by: Sumit Semwal <sumit.semwal@linaro.org>

Best,
Sumit.
>
> Based on dma-mapping-for-next e7442a68cd1ee797b585f045d348781e9c0dde0d

---

## [11] Marek Szyprowski — 2026-04-02
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly shared/decrypted memory*

On 02.04.2026 06:41, Sumit Semwal wrote:
> On Thu, 26 Mar 2026 at 00:53, Jiri Pirko <jiri@resnulli.us> wrote:
>> From: Jiri Pirko <jiri@nvidia.com>

I've applied both patches to dma-mapping-for-next. Thanks!

Best regards

---

## [12] Brian Starkey — 2026-04-02
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to allocate
 explicitly shared/decrypted memory*

Hi,

I know I'm late to the party here...

Like John, I'm also not very close to this stuff any more, but I agree
with the other discussions: makes sense for this to be a separate
heap, and cc_shared makes sense too.

I'm not clear why the heap depends on !CONFIG_HIGHMEM, but I also
don't know anything about SEV/TDX.

-Brian

On Wed, Mar 25, 2026 at 08:23:50PM +0000, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
>

---

## [13] Jason Gunthorpe — 2026-04-02
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to allocate
 explicitly shared/decrypted memory*

On Thu, Apr 02, 2026 at 10:52:34AM +0100, Brian Starkey wrote:
> I'm not clear why the heap depends on !CONFIG_HIGHMEM, but I also
> don't know anything about SEV/TDX.

It is because the CC apis, set_memory_decrypted()/etc are slightly
mis-designed. They take in a vaddr to represent the address instead of
a phys_addr_t or a page *

This means the user has to use page_address() and then the whole thing
is incompatible with highmem.

Which is fine, highmem and CC are never turned on together.

Jason

---

## [14] Maxime Ripard — 2026-04-02
*Subject: Re: [PATCH v5 2/2] dma-buf: heaps: system: add system_cc_shared heap
 for explicitly shared memory*

Hi Jiri,

On Wed, Mar 25, 2026 at 08:23:52PM +0100, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
> 

I'm a bit late to the party, sorry.

This new heap must be documented in
Documentation/userspace-api/dma-buf-heaps.rst, but (and especially since
it seems like it was merged already) it can be done as a follow-up
patch.

Maxime

---

## [15] Jiri Pirko — 2026-04-02
*Subject: Re: [PATCH v5 2/2] dma-buf: heaps: system: add system_cc_shared heap
 for explicitly shared memory*

Thu, Apr 02, 2026 at 02:23:12PM +0200, mripard@redhat.com wrote:
>Hi Jiri,
>

Okay, will send a follow-up. Thanks!

>
>Maxime

---

## [16] Jiri Pirko — 2026-04-02
*Subject: Re: [PATCH v5 0/2] dma-buf: heaps: system: add an option to allocate
 explicitly shared/decrypted memory*

Thu, Apr 02, 2026 at 02:02:54PM +0200, jgg@ziepe.ca wrote:
>On Thu, Apr 02, 2026 at 10:52:34AM +0100, Brian Starkey wrote:
>> I'm not clear why the heap depends on !CONFIG_HIGHMEM, but I also

Yeah, I was wondering if it is worth sanitizing it, but decided to be on
the safe side, for unlikely oddities future may bring sake :)

---

## [17] Aneesh Kumar K.V — 2026-04-20
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

Jiri Pirko <jiri@resnulli.us> writes:

> From: Jiri Pirko <jiri@nvidia.com>
>

What is this check for? If we are requesting a DMA mapping with
DMA_ATTR_CC_SHARED, shouldn’t it be allowed? If not, how would we reach
the conditional below where we convert the physical address to a DMA
address using phys_to_dma_unencrypted()?. Also, how is this supposed to
interact with is_swiotlb_force_bounce()?”

>  
>  	if (attrs & DMA_ATTR_MMIO) {

-aneesh

---

## [18] Jiri Pirko — 2026-04-20
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

Mon, Apr 20, 2026 at 08:34:06AM +0200, aneesh.kumar@kernel.org wrote:
>Jiri Pirko <jiri@resnulli.us> writes:
>

This is defensive. Only allows to map with DMA_ATTR_CC_SHARED set to
dev dev that does not support CC natively. This can be of course lifted,
if you have a case.


>the conditional below where we convert the physical address to a DMA
>address using phys_to_dma_unencrypted()?. Also, how is this supposed to

You reach there when is_swiotlb_force_bounce(dev) is true and
DMA_ATTR_CC_SHARED is set. What am I missing?



>
>>

---

## [19] Aneesh Kumar K.V — 2026-04-21
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

Jiri Pirko <jiri@resnulli.us> writes:

> Mon, Apr 20, 2026 at 08:34:06AM +0200, aneesh.kumar@kernel.org wrote:
>>Jiri Pirko <jiri@resnulli.us> writes:

So a swiotlb_force_bounce will not use swiotlb bouncing if
DMA_ATTR_CC_SHARED is set ? 

>
>

-aneesh

---

## [20] Jiri Pirko — 2026-04-21
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

Tue, Apr 21, 2026 at 11:42:03AM +0200, aneesh.kumar@kernel.org wrote:
>Jiri Pirko <jiri@resnulli.us> writes:
>

Correct. Bouncing does not make sense in this case, as shared memory is
already being mapped.


>
>>

---

## [21] Jason Gunthorpe — 2026-04-21
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

On Tue, Apr 21, 2026 at 01:53:31PM +0200, Jiri Pirko wrote:
> >> You reach there when is_swiotlb_force_bounce(dev) is true and
> >> DMA_ATTR_CC_SHARED is set. What am I missing?

It is a little bit mangled, there are many reasons force_swiotlb can
be set, but we loose them as it flows through - swiotlb_init()
just has a simple SWIOTLB_FORCE

Ideally DMA_ATTR_CC_SHARED would skip swiotlb only if it is being
selected for CC reasons. For instance if you have the swiotlb force
command line parameter I would still expect it bounce shared memory.

Arguably I think this arch flow is misdesigned, the
is_swiotlb_force_bounce() should not be used for CC. dma_capable() is
the correct API to check if the device can DMA to the presented
address, and it will trigger swiotlb_map() just the same without
creating this gap.

Jason

---

## [22] Petr Tesarik — 2026-04-22
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

On Tue, 21 Apr 2026 09:10:04 -0300
Jason Gunthorpe <jgg@ziepe.ca> wrote:

> On Tue, Apr 21, 2026 at 01:53:31PM +0200, Jiri Pirko wrote:
> > >> You reach there when is_swiotlb_force_bounce(dev) is true and

Seconded.

Then again, the whole DMA mapping logic is extremely convoluted, with
dmaops, direct, CMA, and swiotlb, so I'm no longer sure there is one
undisputable way where CC shared mappings should be added to the mix.

Has anyone considered a cleaner design yet? If yes, I'm volunteering to
help implement it. If not, then please ignore me as a random rant.

Petr T

---

## [23] Aneesh Kumar K.V — 2026-04-22
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Tue, Apr 21, 2026 at 01:53:31PM +0200, Jiri Pirko wrote:
>> >> You reach there when is_swiotlb_force_bounce(dev) is true and

Something like this?

static inline dma_addr_t dma_direct_map_phys(struct device *dev,
		phys_addr_t phys, size_t size, enum dma_data_direction dir,
		unsigned long attrs, bool flush)
{
	dma_addr_t dma_addr;

	if (is_swiotlb_force_bounce(dev)) {
		if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT))
			return DMA_MAPPING_ERROR;

		return swiotlb_map(dev, phys, size, dir, attrs);
	}

	if (attrs & DMA_ATTR_MMIO) {
		dma_addr = phys;
		if (unlikely(!dma_capable(dev, dma_addr, size, false, attrs)))
			goto err_overflow;
		goto dma_mapped;
	} else if (attrs & DMA_ATTR_CC_SHARED) {
		dma_addr = phys_to_dma_unencrypted(dev, phys);
	} else {
		dma_addr = phys_to_dma_encrypted(dev, phys);
	}

	if (unlikely(!dma_capable(dev, dma_addr, size, true, attrs)) ||
	    dma_kmalloc_needs_bounce(dev, size, dir)) {
		if (is_swiotlb_active(dev) &&
		    !(attrs & DMA_ATTR_REQUIRE_COHERENT))
			return swiotlb_map(dev, phys, size, dir, attrs);
		goto err_overflow;
	}

dma_mapped:
	if (!dev_is_dma_coherent(dev) &&
	    !(attrs & (DMA_ATTR_SKIP_CPU_SYNC | DMA_ATTR_MMIO))) {
		arch_sync_dma_for_device(phys, size, dir);
		if (flush)
			arch_sync_dma_flush();
	}
	return dma_addr;

and dma_capable() now does
static inline bool dma_capable(struct device *dev, dma_addr_t addr, size_t size,
		bool is_ram, unsigned long attrs)
{
....

	/*
	 * if phys addr attribute is encrypted but the
	 * device is forcing an encrypted dma addr
	 */
	if (!(attrs & DMA_ATTR_CC_SHARED) && force_dma_unencrypted(dev))
		return false;
...

}


-aneesh

---

## [24] Jason Gunthorpe — 2026-04-24
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

On Wed, Apr 22, 2026 at 02:48:37PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

Yeah that reads pretty sanely.

> static inline dma_addr_t dma_direct_map_phys(struct device *dev,
> 		phys_addr_t phys, size_t size, enum dma_data_direction dir,

I suspect P2P is probably broken on CC because this doesn't make
sense..

This should flow into the
phys_to_dma_unencrypted/phys_to_dma_encrypted block as well AFAICT, it
shouldn't just assign phys. Assigning phys to dma on a CC system is
always wrong, right?

It is is more like

        /* To be updated, callers should specify MMIO | CC_SHARED instead of
	 * implying it. */
        if (attrs & DMA_ATTR_MMIO)
	   attrs |= DMA_ATTR_CC_SHARED;

        if (attrs & DMA_ATTR_CC_SHARED) {
 		dma_addr = phys_to_dma_unencrypted(dev, phys);
 	} else {
 		dma_addr = phys_to_dma_encrypted(dev, phys);
 	}

        if (!dma_capable()) {
            if (attrs & (DMA_ATTR_MMIO | DMA_ATTR_REQUIRE_COHERENT)
	       fail
        }

> and dma_capable() now does
> static inline bool dma_capable(struct device *dev, dma_addr_t addr, size_t size,

Yeah

And with the above little edits it works for MMIO now too.

Jason

---

## [25] Jason Gunthorpe — 2026-04-26
*Subject: Re: [PATCH v5 1/2] dma-mapping: introduce DMA_ATTR_CC_SHARED for
 shared memory*

> > static inline dma_addr_t dma_direct_map_phys(struct device *dev,
> > 		phys_addr_t phys, size_t size, enum dma_data_direction dir,

Actually, I suppose it is fully broken because it will jump to swiotlb
and then should fail.

> This should flow into the
> phys_to_dma_unencrypted/phys_to_dma_encrypted block as well AFAICT, it

So no need for this if, we can go directly to marking the MMIO callers
with DMA_ATTR_CC_SHARED once this is fixed for mmio:

>         if (attrs & DMA_ATTR_CC_SHARED) {
>  		dma_addr = phys_to_dma_unencrypted(dev, phys);

Jasn

---
