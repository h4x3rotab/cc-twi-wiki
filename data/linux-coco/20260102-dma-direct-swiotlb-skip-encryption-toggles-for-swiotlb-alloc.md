---
title: 'dma-direct: swiotlb: Skip encryption toggles for swiotlb allocations'
date: 2026-01-02
last_reply: 2026-01-20
message_count: 11
participants: ['Aneesh Kumar K.V (Arm)', 'Robin Murphy', 'Marek Szyprowski']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-01-02

Swiotlb backing pages are already mapped decrypted via
swiotlb_update_mem_attributes(), so dma-direct does not need to call
set_memory_decrypted() during allocation or re-encrypt the memory on
free.

Handle swiotlb-backed buffers explicitly: obtain the DMA address and
zero the linear mapping for lowmem pages, and bypass the decrypt/encrypt
transitions when allocating/freeing from the swiotlb pool (detected via
swiotlb_find_pool()).

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 56 +++++++++++++++++++++++++++++++++++++--------
 1 file changed, 46 insertions(+), 10 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index faf1e41afde8..c4ef4457bd74 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -104,15 +104,27 @@ static void __dma_direct_free_pages(struct device *dev, struct page *page,
 	dma_free_contiguous(dev, page, size);
 }
 
-static struct page *dma_direct_alloc_swiotlb(struct device *dev, size_t size)
+static struct page *dma_direct_alloc_swiotlb(struct device *dev, size_t size,
+					     dma_addr_t *dma_handle)
 {
-	struct page *page = swiotlb_alloc(dev, size);
+	void *lm_addr;
+	struct page *page;
+
+	page = swiotlb_alloc(dev, size);
+	if (!page)
+		return NULL;
 
-	if (page && !dma_coherent_ok(dev, page_to_phys(page), size)) {
+	if (!dma_coherent_ok(dev, page_to_phys(page), size)) {
 		swiotlb_free(dev, page, size);
 		return NULL;
 	}
+	/* If HighMem let caller take care of creating a mapping */
+	if (PageHighMem(page))
+		return page;
 
+	lm_addr = page_address(page);
+	memset(lm_addr, 0, size);
+	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
 	return page;
 }
 
@@ -125,9 +137,6 @@ static struct page *__dma_direct_alloc_pages(struct device *dev, size_t size,
 
 	WARN_ON_ONCE(!PAGE_ALIGNED(size));
 
-	if (is_swiotlb_for_alloc(dev))
-		return dma_direct_alloc_swiotlb(dev, size);
-
 	gfp |= dma_direct_optimal_gfp_mask(dev, &phys_limit);
 	page = dma_alloc_contiguous(dev, size, gfp);
 	if (page) {
@@ -204,6 +213,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		dma_addr_t *dma_handle, gfp_t gfp, unsigned long attrs)
 {
 	bool remap = false, set_uncached = false;
+	bool mark_mem_decrypt = true;
 	bool allow_highmem = true;
 	struct page *page;
 	void *ret;
@@ -251,6 +261,14 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	    dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (is_swiotlb_for_alloc(dev)) {
+		page = dma_direct_alloc_swiotlb(dev, size, dma_handle);
+		if (page) {
+			mark_mem_decrypt = false;
+			goto setup_page;
+		}
+		return NULL;
+	}
 
 	if (force_dma_unencrypted(dev))
 		/*
@@ -266,6 +284,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	if (!page)
 		return NULL;
 
+setup_page:
 	/*
 	 * dma_alloc_contiguous can return highmem pages depending on a
 	 * combination the cma= arguments and per-arch setup.  These need to be
@@ -295,7 +314,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 		ret = page_address(page);
 	}
 
-	if (force_dma_unencrypted(dev)) {
+	if (mark_mem_decrypt && force_dma_unencrypted(dev)) {
 		void *lm_addr;
 
 		lm_addr = page_address(page);
@@ -316,7 +335,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	return ret;
 
 out_encrypt_pages:
-	if (dma_set_encrypted(dev, page_address(page), size))
+	if (mark_mem_decrypt && dma_set_encrypted(dev, page_address(page), size))
 		return NULL;
 out_free_pages:
 	__dma_direct_free_pages(dev, page, size);
@@ -328,6 +347,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 void dma_direct_free(struct device *dev, size_t size,
 		void *cpu_addr, dma_addr_t dma_addr, unsigned long attrs)
 {
+	bool mark_mem_encrypted = true;
 	unsigned int page_order = get_order(size);
 
 	if ((attrs & DMA_ATTR_NO_KERNEL_MAPPING) &&
@@ -356,6 +376,9 @@ void dma_direct_free(struct device *dev, size_t size,
 	    dma_free_from_pool(dev, cpu_addr, PAGE_ALIGN(size)))
 		return;
 
+	if (swiotlb_find_pool(dev, dma_to_phys(dev, dma_addr)))
+		mark_mem_encrypted = false;
+
 	if (is_vmalloc_addr(cpu_addr)) {
 		vunmap(cpu_addr);
 	} else {
@@ -363,7 +386,7 @@ void dma_direct_free(struct device *dev, size_t size,
 			arch_dma_clear_uncached(cpu_addr, size);
 	}
 
-	if (force_dma_unencrypted(dev)) {
+	if (mark_mem_encrypted && force_dma_unencrypted(dev)) {
 		void *lm_addr;
 
 		lm_addr = phys_to_virt(dma_to_phys(dev, dma_addr));
@@ -385,6 +408,15 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	if (force_dma_unencrypted(dev) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (is_swiotlb_for_alloc(dev)) {
+		page = dma_direct_alloc_swiotlb(dev, size, dma_handle);
+		if (page && PageHighMem(page)) {
+			swiotlb_free(dev, page, size);
+			return NULL;
+		}
+		return page;
+	}
+
 	page = __dma_direct_alloc_pages(dev, size, gfp, false);
 	if (!page)
 		return NULL;
@@ -404,13 +436,17 @@ void dma_direct_free_pages(struct device *dev, size_t size,
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

## [2] Robin Murphy — 2026-01-08
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for swiotlb
 allocations*

On 2026-01-02 3:54 pm, Aneesh Kumar K.V (Arm) wrote:
> Swiotlb backing pages are already mapped decrypted via
> swiotlb_update_mem_attributes(), so dma-direct does not need to call

swiotlb_update_mem_attributes() only applies to the default SWIOTLB 
buffer, while the dma_direct_alloc_swiotlb() path is only for private 
restricted pools (because the whole point is that restricted DMA devices 
cannot use the regular allocator/default pools). There is no redundancy 
here AFAICS.

Thanks,
Robin.

> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

---

## [3] Aneesh Kumar K.V — 2026-01-09
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for
 swiotlb allocations*

Robin Murphy <robin.murphy@arm.com> writes:

> On 2026-01-02 3:54 pm, Aneesh Kumar K.V (Arm) wrote:
>> Swiotlb backing pages are already mapped decrypted via

But rmem_swiotlb_device_init() is also marking the entire pool decrypted

	set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),
			     rmem->size >> PAGE_SHIFT);

-aneesh

>
> Thanks,

---

## [4] Robin Murphy — 2026-01-12
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for swiotlb
 allocations*

On 2026-01-09 2:51 am, Aneesh Kumar K.V wrote:
> Robin Murphy <robin.murphy@arm.com> writes:
> 

OK, so why doesn't the commit message mention that instead of saying 
something which fails to justify the patch at all? ;)

Furthermore, how much does this actually matter? The "real" restricted 
DMA use-case is on systems where dma_set_decrypted() is a no-op anyway. 
I know we used restricted DMA as a hack in the early days of CCA 
prototyping, but is it intended to actually deploy that as a supported 
and recommended mechanism now?

Note also that the swiotlb_alloc path is essentially an emergency 
fallback, which doesn't work for all situations anyway - any restricted 
device that actually needs to make significant coherent allocations (or 
rather, that firmware cannot assume won't want to do so) should really 
have a proper coherent pool alongside its restricted one. The expected 
use-case here is for something like a wifi driver that only needs to 
allocate one or two small coherent buffers once at startup, then do 
everything else with streaming DMA.

Thanks,
Robin.

> 
> -aneesh

---

## [5] Aneesh Kumar K.V — 2026-01-12
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for
 swiotlb allocations*

Robin Murphy <robin.murphy@arm.com> writes:

> On 2026-01-09 2:51 am, Aneesh Kumar K.V wrote:
>> Robin Murphy <robin.murphy@arm.com> writes:


I was aiming to bring more consistency in how swiotlb buffers are
handled, specifically by treating all swiotlb memory as decrypted
buffers, which is also how the current code behaves.

If we are concluding that restricted DMA is not used in conjunction with
memory encryption, then we could, in fact, remove the
set_memory_decrypted() call from rmem_swiotlb_device_init() and
instead add failure conditions for force_dma_unencrypted(dev) in
is_swiotlb_for_alloc(). However, it’s worth noting that the initial
commit did take the memory encryption feature into account
(0b84e4f8b793eb4045fd64f6f514165a7974cd16).

Please let me know if you think this needs to be fixed.

-aneesh

---

## [6] Aneesh Kumar K.V — 2026-01-14
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for
 swiotlb allocations*

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> Robin Murphy <robin.murphy@arm.com> writes:
>

Something like.

dma-direct: restricted-dma: Do not mark the restricted DMA pool unencrypted

As per commit f4111e39a52a ("swiotlb: Add restricted DMA alloc/free
support"), the restricted-dma-pool is used in conjunction with the
shared-dma-pool. Since allocations from the shared-dma-pool are not
marked unencrypted, skip marking the restricted-dma-pool as unencrypted
as well. We do not expect systems using the restricted-dma-pool to have
memory encryption or to run with confidential computing features enabled.

If a device requires unencrypted access (force_dma_unencrypted(dev)),
the dma-direct allocator will mark the restricted-dma-pool allocation as
unencrypted.

The only disadvantage is that, when running on a CC guest with a
different hypervisor page size, restricted-dma-pool allocation sizes
must now be aligned to the hypervisor page size. This alignment would
not be required if the entire pool were marked unencrypted. However, the
new code enables the use of the restricted-dma-pool for trusted devices.
Previously, because the entire pool was marked unencrypted, trusted
devices were unable to allocate from it.

There is still an open question regarding allocations from the
shared-dma-pool. Currently, they are not marked unencrypted.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

1 file changed, 2 deletions(-)
kernel/dma/swiotlb.c | 2 --

modified   kernel/dma/swiotlb.c
@@ -1835,8 +1835,6 @@ static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
 			return -ENOMEM;
 		}
 
-		set_memory_decrypted((unsigned long)phys_to_virt(rmem->base),
-				     rmem->size >> PAGE_SHIFT);
 		swiotlb_init_io_tlb_pool(pool, rmem->base, nslabs,
 					 false, nareas);
 		mem->force_bounce = true;

---

## [7] Marek Szyprowski — 2026-01-19
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for
 swiotlb allocations*

On 14.01.2026 10:49, Aneesh Kumar K.V wrote:
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:
>> Robin Murphy <robin.murphy@arm.com> writes:

Robin, could You review this? Is it ready for applying?

Best regards

---

## [8] Robin Murphy — 2026-01-19
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for swiotlb
 allocations*

On 19/01/2026 9:52 am, Marek Szyprowski wrote:
> On 14.01.2026 10:49, Aneesh Kumar K.V wrote:
>> Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

But wouldn't this break the actual intended use of restricted pools for 
streaming DMA bouncing, which does depend on the buffer being 
pre-decrypted/shared? (Since streaming DMA mappings definitely need to 
be supported in nowait contexts)

Thanks,
Robin.

---

## [9] Aneesh Kumar K.V — 2026-01-19
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for
 swiotlb allocations*

Robin Murphy <robin.murphy@arm.com> writes:

> On 19/01/2026 9:52 am, Marek Szyprowski wrote:
>> On 14.01.2026 10:49, Aneesh Kumar K.V wrote:

Only if we are using a restricted pool with encrypted memory.

If we assume that swiotlb bounce buffers are always decrypted, then
allocations from that pool can safely skip the decrypt/encrypt
transitions. However, we still need to address coherent allocations via
the shared-dma-pool, which are explicitly marked as unencrypted.

Given this, I’m wondering whether the best approach is to revisit the
original patch I posted, which moved swiotlb allocations out of
__dma_direct_alloc_pages(). With that separation in place, we could then
fix up dma_alloc_from_dev_coherent() accordingly.

If the conclusion is that systems with encrypted memory will, in
practice, never use restricted-dma-pool or shared-dma-pool, then we can
take this patch?

If you can suggest the approach you would like to see taken with
restricted-dma-pool/shared-dma-pool, I can work on the final change.

-aneesh

---

## [10] Robin Murphy — 2026-01-19
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for swiotlb
 allocations*

On 19/01/2026 3:53 pm, Aneesh Kumar K.V wrote:
> Robin Murphy <robin.murphy@arm.com> writes:
> 

But if the conclusion is that it doesn't matter then that can only mean
we don't need this patch either.

We've identified that the combination of restricted DMA and a
"meaningful" memory encryption API is theoretically slightly broken and
can't ever have worked properly, so how do we benefit from churning it
to just be theoretically more broken in a different way? That makes even
less sense than invasive churn to "fix" the theoretical problem that
hasn't been an issue in practice.

> If you can suggest the approach you would like to see taken with
> restricted-dma-pool/shared-dma-pool, I can work on the final change.

TBH my first choice is "do nothing"; second would be something like the
below, then wait and see if any future CoCo development does justify
changing our expectations.

Thanks,
Robin.

----->8-----

diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index a547c7693135..3786a81eac40 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -1784,6 +1784,10 @@ bool swiotlb_free(struct device *dev, struct page *page, size_t size)
  
  	swiotlb_release_slots(dev, tlb_addr, pool);
  
+	/* We really don't expect this combination, and making it work is a pain */
+	dev_WARN_ONCE(dev, cc_platform_has(CC_ATTR_MEM_ENCRYPT)),
+		      "Freeing coherent allocation potentially corrupts restricted DMA pool\n");
+
  	return true;
  }

---

## [11] Aneesh Kumar K.V — 2026-01-20
*Subject: Re: [PATCH] dma-direct: swiotlb: Skip encryption toggles for
 swiotlb allocations*

Robin Murphy <robin.murphy@arm.com> writes:

> On 19/01/2026 3:53 pm, Aneesh Kumar K.V wrote:
>> Robin Murphy <robin.murphy@arm.com> writes:

I think we should go with the original patch. I do not see it as more
broken. It is based on the simple assumption that swiotlb buffers are
always decrypted. Based on that assumption, it moves the allocation from
swiotlb out of __dma_direct_alloc_pages() and avoids the decrypt/encrypt
transition for swiotlb buffers.

For coherent allocations from the shared-dma-pool, we need to ensure
that every architecture does the right thing. For Arm CCA, we use
ioremap, which should mark the memory as decrypted/shared.

When we add trusted device support, we must also ensure that such a pool
is never attached to a trusted device. Therefore, there should never be
a need to mark that memory as encrypted/private.

-aneesh

---
