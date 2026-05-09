---
title: 'dma-buf: heaps: system: add an option to allocate explicitly decrypted memory'
date: 2026-03-05
last_reply: 2026-03-24
message_count: 29
participants: ['Jiri Pirko', 'Leon Romanovsky', 'Petr Tesarik', 'Jason Gunthorpe', 'Peter Gonda', 'Mostafa Saleh']
---

## [1] Jiri Pirko — 2026-03-05

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

Jiri Pirko (2):
  dma-mapping: introduce DMA_ATTR_CC_DECRYPTED for pre-decrypted memory
  dma-buf: heaps: system: add system_cc_decrypted heap for explicitly
    decrypted memory

 drivers/dma-buf/heaps/system_heap.c | 103 ++++++++++++++++++++++++++--
 include/linux/dma-mapping.h         |   6 ++
 include/trace/events/dma.h          |   3 +-
 kernel/dma/direct.h                 |  14 +++-
 4 files changed, 117 insertions(+), 9 deletions(-)

---

## [2] Jiri Pirko — 2026-03-05
*Subject: [PATCH net-next v3 1/2] dma-mapping: introduce DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

From: Jiri Pirko <jiri@nvidia.com>

Current CC designs don't place a vIOMMU in front of untrusted devices.
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
v1->v2:
- rebased on top of recent dma-mapping-fixes
---
 include/linux/dma-mapping.h |  6 ++++++
 include/trace/events/dma.h  |  3 ++-
 kernel/dma/direct.h         | 14 +++++++++++---
 3 files changed, 19 insertions(+), 4 deletions(-)

diff --git a/include/linux/dma-mapping.h b/include/linux/dma-mapping.h
index 29973baa0581..ae3d85e494ec 100644
--- a/include/linux/dma-mapping.h
+++ b/include/linux/dma-mapping.h
@@ -85,6 +85,12 @@
  * a cacheline must have this attribute for this to be considered safe.
  */
 #define DMA_ATTR_CPU_CACHE_CLEAN	(1UL << 11)
+/*
+ * DMA_ATTR_CC_DECRYPTED: Indicates memory that has been explicitly decrypted
+ * (shared) for confidential computing guests. The caller must have
+ * called set_memory_decrypted(). A struct page is required.
+ */
+#define DMA_ATTR_CC_DECRYPTED	(1UL << 12)
 
 /*
  * A dma_addr_t can hold any valid DMA or bus address for the platform.  It can
diff --git a/include/trace/events/dma.h b/include/trace/events/dma.h
index 33e99e792f1a..b8082d5177c4 100644
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
index e89f175e9c2d..c047a9d0fda3 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -84,16 +84,24 @@ static inline dma_addr_t dma_direct_map_phys(struct device *dev,
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

## [3] Jiri Pirko — 2026-03-05
*Subject: [PATCH net-next v3 2/2] dma-buf: heaps: system: add system_cc_decrypted heap for explicitly decrypted memory*

From: Jiri Pirko <jiri@nvidia.com>

Add a new "system_cc_decrypted" dma-buf heap to allow userspace to
allocate decrypted (shared) memory for confidential computing (CoCo)
VMs.

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

On non-CoCo VMs, the system_cc_decrypted heap is not registered
to prevent misuse by userspace that does not understand
the security implications of explicitly decrypted memory.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
v2->v3:
- removed couple of leftovers from headers
v1->v2:
- fixed build errors on s390 by including mem_encrypt.h
- converted system heap flag implementation to a separate heap
---
 drivers/dma-buf/heaps/system_heap.c | 103 ++++++++++++++++++++++++++--
 1 file changed, 98 insertions(+), 5 deletions(-)

diff --git a/drivers/dma-buf/heaps/system_heap.c b/drivers/dma-buf/heaps/system_heap.c
index b3650d8fd651..a525e9aaaffa 100644
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
+	bool decrypted;
+};
+
 struct system_heap_buffer {
 	struct dma_heap *heap;
 	struct list_head attachments;
@@ -29,6 +37,7 @@ struct system_heap_buffer {
 	struct sg_table sg_table;
 	int vmap_cnt;
 	void *vaddr;
+	bool decrypted;
 };
 
 struct dma_heap_attachment {
@@ -36,6 +45,7 @@ struct dma_heap_attachment {
 	struct sg_table table;
 	struct list_head list;
 	bool mapped;
+	bool decrypted;
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
+	a->decrypted = buffer->decrypted;
 
 	attachment->priv = a;
 
@@ -119,9 +158,11 @@ static struct sg_table *system_heap_map_dma_buf(struct dma_buf_attachment *attac
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
 
@@ -188,8 +229,13 @@ static int system_heap_mmap(struct dma_buf *dmabuf, struct vm_area_struct *vma)
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
+	if (buffer->decrypted)
+		prot = pgprot_decrypted(prot);
+	vaddr = vmap(pages, npages, VM_MAP, prot);
 	vfree(pages);
 
 	if (!vaddr)
@@ -296,6 +345,14 @@ static void system_heap_dma_buf_release(struct dma_buf *dmabuf)
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
@@ -347,6 +404,8 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	DEFINE_DMA_BUF_EXPORT_INFO(exp_info);
 	unsigned long size_remaining = len;
 	unsigned int max_order = orders[0];
+	struct system_heap_priv *priv = dma_heap_get_drvdata(heap);
+	bool decrypted = priv->decrypted;
 	struct dma_buf *dmabuf;
 	struct sg_table *table;
 	struct scatterlist *sg;
@@ -362,6 +421,7 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
 	mutex_init(&buffer->lock);
 	buffer->heap = heap;
 	buffer->len = len;
+	buffer->decrypted = decrypted;
 
 	INIT_LIST_HEAD(&pages);
 	i = 0;
@@ -396,6 +456,14 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
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
@@ -413,6 +481,13 @@ static struct dma_buf *system_heap_allocate(struct dma_heap *heap,
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
@@ -428,6 +503,14 @@ static const struct dma_heap_ops system_heap_ops = {
 	.allocate = system_heap_allocate,
 };
 
+static struct system_heap_priv system_heap_priv = {
+	.decrypted = false,
+};
+
+static struct system_heap_priv system_heap_cc_decrypted_priv = {
+	.decrypted = true,
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
 
+	exp_info.name = "system_cc_decrypted";
+	exp_info.priv = &system_heap_cc_decrypted_priv;
 	sys_heap = dma_heap_add(&exp_info);
 	if (IS_ERR(sys_heap))
 		return PTR_ERR(sys_heap);

---

## [4] Jiri Pirko — 2026-03-05
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

The "net-next" in [PATCH] brackets is obviously incorrect, ignore
this bad string please.

---

## [5] Leon Romanovsky — 2026-03-08
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Thu, Mar 05, 2026 at 01:36:40PM +0100, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
> 

While adding the new attribute is fine, I would expect additional checks in
dma_map_phys() to ensure the attribute cannot be misused. For example,
WARN_ON(attrs & (DMA_ATTR_CC_DECRYPTED | DMA_ATTR_MMIO)), along with a check
that we are taking the direct path only.

Thanks

---

## [6] Jiri Pirko — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

Sun, Mar 08, 2026 at 11:19:48AM +0100, leon@kernel.org wrote:
>On Thu, Mar 05, 2026 at 01:36:40PM +0100, Jiri Pirko wrote:
>> From: Jiri Pirko <jiri@nvidia.com>

Okay, I will add the check.

---

## [7] Petr Tesarik — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Thu,  5 Mar 2026 13:36:40 +0100
Jiri Pirko <jiri@resnulli.us> wrote:

> From: Jiri Pirko <jiri@nvidia.com>
> 

I don't want to start a bikeshedding discussion, so if everyone else
likes this name, let's keep it. But maybe the "_CC" (meaning
Confidential Comptuing) is not necessary. IIUC it's the same concept as
set_page_encrypted(), set_page_decrypted(), which does not refer to
CoCo either.

Just my two cents
Petr T

---

## [8] Jiri Pirko — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

Mon, Mar 09, 2026 at 01:56:10PM +0100, ptesarik@suse.com wrote:
>On Thu,  5 Mar 2026 13:36:40 +0100
>Jiri Pirko <jiri@resnulli.us> wrote:

Do I understand that correctly that you suggest DMA_ATTR_DECRYPTED ?
It's not uapi, so this is flexible for possible future renames.

---

## [9] Jason Gunthorpe — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Sun, Mar 08, 2026 at 12:19:48PM +0200, Leon Romanovsky wrote:

> > +/*
> > + * DMA_ATTR_CC_DECRYPTED: Indicates memory that has been explicitly decrypted

DECRYPYED and MMIO is something that needs to work, VFIO (inside a
TVM) should be using that combination.

Jason

---

## [10] Jason Gunthorpe — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Mon, Mar 09, 2026 at 01:56:10PM +0100, Petr Tesarik wrote:
> I don't want to start a bikeshedding discussion, so if everyone else
> likes this name, let's keep it. But maybe the "_CC" (meaning

Frankly I hate that AMD got their "encrypted" "decrypted" naming baked
into the CC related APIs.

I'm not at all convinced that they "do not refer to CoCo" in the way
Linux uses them and other arches absolutely make them 100% tied to coco.

If we are going to bikeshed the name it should be DMA_ATTR_CC_SHARED

Jason

---

## [11] Leon Romanovsky — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Mon, Mar 09, 2026 at 10:15:30AM -0300, Jason Gunthorpe wrote:
> On Sun, Mar 08, 2026 at 12:19:48PM +0200, Leon Romanovsky wrote:
> 

So this sentence "A struct page is required" from the comment above is
not accurate.

Thanks

> 
> Jason

---

## [12] Jason Gunthorpe — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Mon, Mar 09, 2026 at 04:02:33PM +0200, Leon Romanovsky wrote:
> On Mon, Mar 09, 2026 at 10:15:30AM -0300, Jason Gunthorpe wrote:
> > On Sun, Mar 08, 2026 at 12:19:48PM +0200, Leon Romanovsky wrote:

It would be clearer to say "Unless DMA_ATTR_MMIO is provided a struct
page is required"

We need to audit if that works properly, IIRC it does, but I don't
remember.. Jiri?

Jason

---

## [13] Peter Gonda — 2026-03-09
*Subject: Re: [PATCH net-next v3 2/2] dma-buf: heaps: system: add
 system_cc_decrypted heap for explicitly decrypted memory*

Great feature to have thanks Jiri! A couple naive questions.

On Thu, Mar 5, 2026 at 5:38 AM Jiri Pirko <jiri@resnulli.us> wrote:
>
> From: Jiri Pirko <jiri@nvidia.com>

So this only works on new mappings? What if there are existing
mappings to the memory that will be converted to shared?

It's also slightly worse than just reading ciphertext. If another
process writes to the memory with the incorrect mapping it could cause
corruption on AMD SEV, or an RMP violation on AMD SEV-SNP. Can we
update the existing mappings?

---

## [14] Jason Gunthorpe — 2026-03-09
*Subject: Re: [PATCH net-next v3 2/2] dma-buf: heaps: system: add
 system_cc_decrypted heap for explicitly decrypted memory*

On Mon, Mar 09, 2026 at 09:39:44AM -0600, Peter Gonda wrote:
> Great feature to have thanks Jiri! A couple naive questions.
> 

The set_memory_decrypted() is called during system_heap_allocate(), it
is not possible to change dynamically between encrypted/decrypted.

Once the heap is created every PTE is always created with the correct
pgprot.

Jason

---

## [15] Jiri Pirko — 2026-03-09
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

Mon, Mar 09, 2026 at 04:18:57PM +0100, jgg@ziepe.ca wrote:
>On Mon, Mar 09, 2026 at 04:02:33PM +0200, Leon Romanovsky wrote:
>> On Mon, Mar 09, 2026 at 10:15:30AM -0300, Jason Gunthorpe wrote:

How can you do set_memory_decrypted if you don't have page/folio ?

---

## [16] Jiri Pirko — 2026-03-11
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

Mon, Mar 09, 2026 at 02:17:36PM +0100, jgg@ziepe.ca wrote:
>On Mon, Mar 09, 2026 at 01:56:10PM +0100, Petr Tesarik wrote:
>> I don't want to start a bikeshedding discussion, so if everyone else

On the other hand, the encrypted/decrypted helpers could be always
renamed if it makes sense. Better to perhaps have DMA_ATTR_DECRYPTED to
have things consistently named now? If someone renames them all in the
future, so be it.

---

## [17] Jason Gunthorpe — 2026-03-11
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Mon, Mar 09, 2026 at 06:51:21PM +0100, Jiri Pirko wrote:
> Mon, Mar 09, 2026 at 04:18:57PM +0100, jgg@ziepe.ca wrote:
> >On Mon, Mar 09, 2026 at 04:02:33PM +0200, Leon Romanovsky wrote:

Alot of device MMIO is decrypted by nature and can't be encrypted, so
you'd have to use both flags. eg in VFIO we'd want to do this.

Jason

---

## [18] Jiri Pirko — 2026-03-12
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

Thu, Mar 12, 2026 at 01:34:08AM +0100, jgg@ziepe.ca wrote:
>On Mon, Mar 09, 2026 at 06:51:21PM +0100, Jiri Pirko wrote:
>> Mon, Mar 09, 2026 at 04:18:57PM +0100, jgg@ziepe.ca wrote:

Why both flags? Why MMIO flag is not enough? You still want to hit
"if (attrs & DMA_ATTR_MMIO) {" path, don't you?

I mean, CC_DECRYPTED says the memory to be mapped was explicitly
decrypted before the call. MMIO was not explicitly decrypted, it is
decrypted by definition. For me that does not fit the CC_DECRYPTED
semantics.

What am I missing?

---

## [19] Jason Gunthorpe — 2026-03-12
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

On Thu, Mar 12, 2026 at 10:03:37AM +0100, Jiri Pirko wrote:
> >Alot of device MMIO is decrypted by nature and can't be encrypted, so
> >you'd have to use both flags. eg in VFIO we'd want to do this.

Because we will eventually have both decrypted and encrypted MMIO.

> I mean, CC_DECRYPTED says the memory to be mapped was explicitly
> decrypted before the call. MMIO was not explicitly decrypted, it is

I would say CC_DECRYPTED means that pgprot_decrypted must be used to
form a PTE, and !CC_DECRYPTED means that pgprot_encrypted() was used

This flag should someday flow down into the vIOMMU driver and set the
corresponding C bit the IOPTE (for AMD) exactly as the pgprot does.

Less about set_memory_encrypted as that is only for DRAM.

Jason

---

## [20] Jiri Pirko — 2026-03-12
*Subject: Re: [PATCH net-next v3 1/2] dma-mapping: introduce
 DMA_ATTR_CC_DECRYPTED for pre-decrypted memory*

Thu, Mar 12, 2026 at 01:06:06PM +0100, jgg@ziepe.ca wrote:
>On Thu, Mar 12, 2026 at 10:03:37AM +0100, Jiri Pirko wrote:
>> >Alot of device MMIO is decrypted by nature and can't be encrypted, so

Okay, that makes sense. Thanks!

---

## [21] Mostafa Saleh — 2026-03-17
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

Hi Jiri,

On Thu, Mar 05, 2026 at 01:36:39PM +0100, Jiri Pirko wrote:
> From: Jiri Pirko <jiri@nvidia.com>
> 

I have been looking into a similar problem with restricted-dma[1] and
the inability of the DMA API to recognize that a block of memory is
already decrypted.

However, in your case, adding a new attr “DMA_ATTR_CC_DECRYPTED” works
well as dma-buf owns the memory, and is both responsible for the
set_memory_decrypted() and passing the DMA attrs.

On the other hand, for restricted-dma, the memory decryption is deep
in the DMA direct memory allocation and the DMA API callers (for ex
virtio drivers) are clueless about it and can’t pass any attrs.
My proposal was specific to restricted-dma and won’t work for your case.

I am wondering if the kernel should have a more solid, unified method
for identifying already-decrypted memory instead. Perhaps we need a
way for the DMA API to natively recognize the encryption state of a
physical page (working alongside force_dma_unencrypted(dev)), rather
than relying on caller-provided attributes?

[1] https://lore.kernel.org/all/20260305170335.963568-1-smostafa@google.com/

Thanks,
Mostafa


> 
> Jiri Pirko (2):

---

## [22] Jiri Pirko — 2026-03-17
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

Tue, Mar 17, 2026 at 02:24:13PM +0100, smostafa@google.com wrote:
>Hi Jiri,
>

I actually had it originally implemented probably in the similar way you
suggest. I had a bit in page/folio struct to indicate the
"shared/decrypted" state. However I was told that adding such bit is
basically a no-go. Isn't that right?


>
>[1] https://lore.kernel.org/all/20260305170335.963568-1-smostafa@google.com/

---

## [23] Mostafa Saleh — 2026-03-17
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

On Tue, Mar 17, 2026 at 02:37:02PM +0100, Jiri Pirko wrote:
> Tue, Mar 17, 2026 at 02:24:13PM +0100, smostafa@google.com wrote:
> >Hi Jiri,

Yes, I believe it’s discouraged to add new fields to the struct page.
But I see the memory encryption API is spilling in different places
and I am not sure if that’s a good enough justification for that or
maybe we just need to re-architect it.
For the restricted-dma stuff, we don’t actually care about the
address, a device can either handle encryption or not, so relying on
force_dma_unencrypted(struct device *) which is implemented by the
architecture is enough, and we just need to integrate that so it
can be used from SWIOTLB and DMA-direct (and other places)
consistently. (although that might not be a simple as it sounds)

I am not sure in the dma-buf case if that would be enough, but
another way to have this per page and to avoid encoding this in
struct page, is to push this problem to the arch code and it can
rely on things as the page table (I believe ARM CCA have a bit
for that)

Anyway, I think there should be some boundaries in the kernel that
defines that instead of each subsystem having its assumptions,
especially memory encryption/decryption problems that can easily
cause security issues.

Thanks,
Mostafa

> 
> >

---

## [24] Jason Gunthorpe — 2026-03-24
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

On Tue, Mar 17, 2026 at 01:24:13PM +0000, Mostafa Saleh wrote:

> On the other hand, for restricted-dma, the memory decryption is deep
> in the DMA direct memory allocation and the DMA API callers (for ex

How is this any different from CC?

If the device cannot dma to "encrypted" memory, whatever that means
for you, then the DMA API:
 - Makes dma alloc coherent return "decrypted" memory, and the built
   in mapping of coherent memory knows about this
 - Makes dma_map_xxx use SWIOTLB to bounce to decrypted memory

There is no need for something like virtio drivers to be aware of
any of this.

On the other hand if the driver deliberately allocates decrypted
memory without using DMA API alloc coherent then it knows it did it
and can pass the flag to map it.

> I am wondering if the kernel should have a more solid, unified method
> for identifying already-decrypted memory instead. Perhaps we need a

Definately not, we do not want the DMA API inspecting things like
this.

Jason

---

## [25] Mostafa Saleh — 2026-03-24
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

On Tue, Mar 24, 2026 at 12:01 PM Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Tue, Mar 17, 2026 at 01:24:13PM +0000, Mostafa Saleh wrote:

The problem is that the DMA API currently gets confused by this; it
can end up double decrypting the memory or using the wrong functions
as mentioned in [1]
In addition to the complexity it adds to the already complicated DMA
code. I don't have a strong opinion on how to solve this, but I
believe we need clear boundaries (and wrappers) for cases where memory
encryption is expected as it is starting to spill into the kernel.

[1] https://lore.kernel.org/all/20260305170335.963568-1-smostafa@google.com/

Thanks,
Mostafa


> > I am wondering if the kernel should have a more solid, unified method
> > for identifying already-decrypted memory instead. Perhaps we need a

---

## [26] Jason Gunthorpe — 2026-03-24
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

On Tue, Mar 24, 2026 at 12:14:36PM +0000, Mostafa Saleh wrote:
> On Tue, Mar 24, 2026 at 12:01 PM Jason Gunthorpe <jgg@ziepe.ca> wrote:
> >

I fully belive there are bugs, but the API design is sound. If you use
the coherent allocations from the DMA API then it knows decryption has
happened when it generates a dma_addr_t and there should be no issue.

Now, if drivers are using the DMA API wrong, like trying to double map
coherent allocations then they are broken. I also would not be
surprised to find cases like this.

Jason

---

## [27] Mostafa Saleh — 2026-03-24
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

On Tue, Mar 24, 2026 at 12:24 PM Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Tue, Mar 24, 2026 at 12:14:36PM +0000, Mostafa Saleh wrote:

But it's not about drivers in that case, it's about many places
(SWIOTLB and DMA-direct) calling set_memory_decrypted() without clear
ownership so in some cases they step on each other's toes, and I don't
think that will get simpler with yet another caller in this series

I am fine with the API design you mentioned, but I believe that it
needs clear documentation specifying who is responsible for
decryption. The code should provide wrappers checking for these cases
instead of having is_swiotlb_for_alloc() and force_dma_unencrypted()
everywhere in DMA-direct.

Thanks,
Mostafa

> Jason

---

## [28] Jason Gunthorpe — 2026-03-24
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

On Tue, Mar 24, 2026 at 05:36:23PM +0000, Mostafa Saleh wrote:
> But it's not about drivers in that case, it's about many places
> (SWIOTLB and DMA-direct) calling set_memory_decrypted() without clear

I don't understand how this can be, ownership is clear. SWIOTLB owns
the buffer, dma alloc coherent owns the buffer, user owns the
buffer. There should be no other cases, and they don't step on each
other unless the APIs are being used wrong.

> I am fine with the API design you mentioned, but I believe that it
> needs clear documentation specifying who is responsible for

Redoingt how dma-api works internally is some other project... It
would be nice if swiotlb would sort of recursively DMA map using the
new flag instead of open coding it but that is pretty minor.

Jason

---

## [29] Mostafa Saleh — 2026-03-24
*Subject: Re: [PATCH net-next v3 0/2] dma-buf: heaps: system: add an option to
 allocate explicitly decrypted memory*

On Tue, Mar 24, 2026 at 5:57 PM Jason Gunthorpe <jgg@ziepe.ca> wrote:
>
> On Tue, Mar 24, 2026 at 05:36:23PM +0000, Mostafa Saleh wrote:

Logically, that's the case, but the DMA-direct code currently loses
this information and assumes it can encrypt/decrypt any memory even
the SWIOTLB one.
That's what I am fixing in my series. When I respin, I can try to
introduce some more helpers around that to make it easier to integrate
new cases.

Thanks,
Mostafa

> > I am fine with the API design you mentioned, but I believe that it
> > needs clear documentation specifying who is responsible for

---
