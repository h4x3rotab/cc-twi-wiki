---
title: '[RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are properly aligned'
date: 2025-09-05
last_reply: 2025-09-12
message_count: 16
participants: ['Aneesh Kumar K.V (Arm)', 'Thomas Gleixner', 'Catalin Marinas', 'Jason Gunthorpe', 'Suzuki K Poulose', 'Steven Price']
---

## [1] Aneesh Kumar K.V (Arm) — 2025-09-05

When running with private memory guests, the guest kernel must allocate
memory with specific constraints when sharing it with the hypervisor.

These shared memory buffers are also accessed by the host kernel, which
means they must be aligned to the host kernel's page size.

This patch introduces a new helper, arch_shared_mem_alignment(), which
can be used to enforce proper alignment of shared buffers.

The actual implementation of arch_shared_mem_alignment() is deferred
to a follow-up patch.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  6 ++++++
 arch/arm64/mm/init.c                 |  4 +++-
 arch/arm64/mm/mem_encrypt.c          |  6 ++++++
 drivers/irqchip/irq-gic-v3-its.c     |  8 ++++++--
 include/linux/mem_encrypt.h          |  7 +++++++
 include/linux/swiotlb.h              |  7 ++++---
 kernel/dma/direct.c                  |  7 +++++++
 kernel/dma/pool.c                    |  1 +
 kernel/dma/swiotlb.c                 | 28 +++++++++++++++++-----------
 9 files changed, 57 insertions(+), 17 deletions(-)

diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index d77c10cd5b79..aaaa1079ba30 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -17,6 +17,12 @@ int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
 bool force_dma_unencrypted(struct device *dev);
 
+#define arch_shared_mem_alignment arch_shared_mem_alignment
+static inline long arch_shared_mem_alignment(void)
+{
+	return PAGE_SIZE;
+}
+
 int realm_register_memory_enc_ops(void);
 
 /*
diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
index ea84a61ed508..389070e9ee65 100644
--- a/arch/arm64/mm/init.c
+++ b/arch/arm64/mm/init.c
@@ -337,12 +337,14 @@ void __init bootmem_init(void)
 
 void __init arch_mm_preinit(void)
 {
+	unsigned int swiotlb_align = PAGE_SIZE;
 	unsigned int flags = SWIOTLB_VERBOSE;
 	bool swiotlb = max_pfn > PFN_DOWN(arm64_dma_phys_limit);
 
 	if (is_realm_world()) {
 		swiotlb = true;
 		flags |= SWIOTLB_FORCE;
+		swiotlb_align = arch_shared_mem_alignment();
 	}
 
 	if (IS_ENABLED(CONFIG_DMA_BOUNCE_UNALIGNED_KMALLOC) && !swiotlb) {
@@ -356,7 +358,7 @@ void __init arch_mm_preinit(void)
 		swiotlb = true;
 	}
 
-	swiotlb_init(swiotlb, flags);
+	swiotlb_init(swiotlb, swiotlb_align, flags);
 	swiotlb_update_mem_attributes();
 
 	/*
diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
index 645c099fd551..170ee4b61e50 100644
--- a/arch/arm64/mm/mem_encrypt.c
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -46,6 +46,12 @@ int set_memory_decrypted(unsigned long addr, int numpages)
 	if (likely(!crypt_ops) || WARN_ON(!PAGE_ALIGNED(addr)))
 		return 0;
 
+	if (WARN_ON(!IS_ALIGNED(addr, arch_shared_mem_alignment())))
+		return 0;
+
+	if (WARN_ON(!IS_ALIGNED(numpages << PAGE_SHIFT, arch_shared_mem_alignment())))
+		return 0;
+
 	return crypt_ops->decrypt(addr, numpages);
 }
 EXPORT_SYMBOL_GPL(set_memory_decrypted);
diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 467cb78435a9..e2142bbca13b 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -213,16 +213,20 @@ static gfp_t gfp_flags_quirk;
 static struct page *its_alloc_pages_node(int node, gfp_t gfp,
 					 unsigned int order)
 {
+	long new_order;
 	struct page *page;
 	int ret = 0;
 
-	page = alloc_pages_node(node, gfp | gfp_flags_quirk, order);
+	/* align things to hypervisor page size */
+	new_order = get_order(ALIGN((PAGE_SIZE << order), arch_shared_mem_alignment()));
+
+	page = alloc_pages_node(node, gfp | gfp_flags_quirk, new_order);
 
 	if (!page)
 		return NULL;
 
 	ret = set_memory_decrypted((unsigned long)page_address(page),
-				   1 << order);
+				   1 << new_order);
 	/*
 	 * If set_memory_decrypted() fails then we don't know what state the
 	 * page is in, so we can't free it. Instead we leak it.
diff --git a/include/linux/mem_encrypt.h b/include/linux/mem_encrypt.h
index 07584c5e36fb..c24563e7363a 100644
--- a/include/linux/mem_encrypt.h
+++ b/include/linux/mem_encrypt.h
@@ -54,6 +54,13 @@
 #define dma_addr_canonical(x)		(x)
 #endif
 
+#ifndef arch_shared_mem_alignment
+static inline long arch_shared_mem_alignment(void)
+{
+	return PAGE_SIZE;
+}
+#endif
+
 #endif	/* __ASSEMBLY__ */
 
 #endif	/* __MEM_ENCRYPT_H__ */
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index b27de03f2466..739edb380e54 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -36,8 +36,9 @@ struct scatterlist;
 #define IO_TLB_DEFAULT_SIZE (64UL<<20)
 
 unsigned long swiotlb_size_or_default(void);
-void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
-	int (*remap)(void *tlb, unsigned long nslabs));
+void __init swiotlb_init_remap(bool addressing_limit, unsigned int alignment,
+			       unsigned int flags,
+			       int (*remap)(void *tlb, unsigned long nslabs));
 int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 	int (*remap)(void *tlb, unsigned long nslabs));
 extern void __init swiotlb_update_mem_attributes(void);
@@ -181,7 +182,7 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 	return mem && mem->force_bounce;
 }
 
-void swiotlb_init(bool addressing_limited, unsigned int flags);
+void swiotlb_init(bool addressing_limited, unsigned int alignment, unsigned int flags);
 void __init swiotlb_exit(void);
 void swiotlb_dev_init(struct device *dev);
 size_t swiotlb_max_mapping_size(struct device *dev);
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 24c359d9c879..5db5baad5efa 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -255,6 +255,9 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	    dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (force_dma_unencrypted(dev))
+		/*  align to hypervisor size */
+		size = ALIGN(size, arch_shared_mem_alignment());
 	/* we always manually zero the memory once we are done */
 	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, true);
 	if (!page)
@@ -364,6 +367,10 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	if (force_dma_unencrypted(dev) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (force_dma_unencrypted(dev))
+		/*  align to hypervisor size */
+		size = ALIGN(size, arch_shared_mem_alignment());
+
 	page = __dma_direct_alloc_pages(dev, size, gfp, false);
 	if (!page)
 		return NULL;
diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index 7b04f7575796..cf4c659b3db9 100644
--- a/kernel/dma/pool.c
+++ b/kernel/dma/pool.c
@@ -196,6 +196,7 @@ static int __init dma_atomic_pool_init(void)
 		unsigned long pages = totalram_pages() / (SZ_1G / SZ_128K);
 		pages = min_t(unsigned long, pages, MAX_ORDER_NR_PAGES);
 		atomic_pool_size = max_t(size_t, pages << PAGE_SHIFT, SZ_128K);
+		WARN_ON(!IS_ALIGNED(atomic_pool_size, arch_shared_mem_alignment()));
 	}
 	INIT_WORK(&atomic_pool_work, atomic_pool_work_fn);
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index abcf3fa63a56..a8f46d2ce058 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -316,21 +316,22 @@ static void add_mem_pool(struct io_tlb_mem *mem, struct io_tlb_pool *pool)
 }
 
 static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
-		unsigned int flags,
-		int (*remap)(void *tlb, unsigned long nslabs))
+				unsigned int alignment, unsigned int flags,
+				int (*remap)(void *tlb, unsigned long nslabs))
 {
-	size_t bytes = PAGE_ALIGN(nslabs << IO_TLB_SHIFT);
+	size_t bytes;
 	void *tlb;
 
+	bytes = ALIGN((nslabs << IO_TLB_SHIFT), alignment);
 	/*
 	 * By default allocate the bounce buffer memory from low memory, but
 	 * allow to pick a location everywhere for hypervisors with guest
 	 * memory encryption.
 	 */
 	if (flags & SWIOTLB_ANY)
-		tlb = memblock_alloc(bytes, PAGE_SIZE);
+		tlb = memblock_alloc(bytes, alignment);
 	else
-		tlb = memblock_alloc_low(bytes, PAGE_SIZE);
+		tlb = memblock_alloc_low(bytes, alignment);
 
 	if (!tlb) {
 		pr_warn("%s: Failed to allocate %zu bytes tlb structure\n",
@@ -339,7 +340,7 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 	}
 
 	if (remap && remap(tlb, nslabs) < 0) {
-		memblock_free(tlb, PAGE_ALIGN(bytes));
+		memblock_free(tlb, bytes);
 		pr_warn("%s: Failed to remap %zu bytes\n", __func__, bytes);
 		return NULL;
 	}
@@ -351,8 +352,9 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
  * Statically reserve bounce buffer space and initialize bounce buffer data
  * structures for the software IO TLB used to implement the DMA API.
  */
-void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
-		int (*remap)(void *tlb, unsigned long nslabs))
+void __init swiotlb_init_remap(bool addressing_limit, unsigned int alignment,
+			       unsigned int flags,
+			       int (*remap)(void *tlb, unsigned long nslabs))
 {
 	struct io_tlb_pool *mem = &io_tlb_default_mem.defpool;
 	unsigned long nslabs;
@@ -382,7 +384,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 
 	nslabs = default_nslabs;
 	nareas = limit_nareas(default_nareas, nslabs);
-	while ((tlb = swiotlb_memblock_alloc(nslabs, flags, remap)) == NULL) {
+	while ((tlb = swiotlb_memblock_alloc(nslabs, alignment, flags, remap)) == NULL) {
 		if (nslabs <= IO_TLB_MIN_SLABS)
 			return;
 		nslabs = ALIGN(nslabs >> 1, IO_TLB_SEGSIZE);
@@ -417,9 +419,9 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 		swiotlb_print_info();
 }
 
-void __init swiotlb_init(bool addressing_limit, unsigned int flags)
+void __init swiotlb_init(bool addressing_limit, unsigned int alignment, unsigned int flags)
 {
-	swiotlb_init_remap(addressing_limit, flags, NULL);
+	swiotlb_init_remap(addressing_limit, alignment, flags, NULL);
 }
 
 /*
@@ -464,6 +466,10 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 	order = get_order(nslabs << IO_TLB_SHIFT);
 	nslabs = SLABS_PER_PAGE << order;
 
+	WARN_ON(!IS_ALIGNED(order << PAGE_SHIFT, arch_shared_mem_alignment()));
+	WARN_ON(!IS_ALIGNED(default_nslabs << IO_TLB_SHIFT, arch_shared_mem_alignment()));
+	WARN_ON(!IS_ALIGNED(IO_TLB_MIN_SLABS << IO_TLB_SHIFT, arch_shared_mem_alignment()));
+
 	while ((SLABS_PER_PAGE << order) > IO_TLB_MIN_SLABS) {
 		vstart = (void *)__get_free_pages(gfp_mask | __GFP_NOWARN,
 						  order);

---

## [2] Thomas Gleixner — 2025-09-05
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Fri, Sep 05 2025 at 11:24, Aneesh Kumar K. V. wrote:
> When running with private memory guests, the guest kernel must allocate
> memory with specific constraints when sharing it with the hypervisor.

# git grep "This patch" Documentation/process/

> can be used to enforce proper alignment of shared buffers.
>

This does too many things at once and breaks all swiotlb users except
arm64. Seriously?

> -void swiotlb_init(bool addressing_limited, unsigned int flags);
> +void swiotlb_init(bool addressing_limited, unsigned int alignment, unsigned int flags);

Why do you need this alignment argument in the first place?

In quite some other places you use arch_shared_mem_alignment(), which
defaults to PAGE_SIZE if the architecture does not implement it's own
variant. What's preventing you from using that in the init functions as
well?

Thanks,

        tglx

---

## [3] Catalin Marinas — 2025-09-05
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

Hi Aneesh,

On Fri, Sep 05, 2025 at 11:24:41AM +0530, Aneesh Kumar K.V (Arm) wrote:
> When running with private memory guests, the guest kernel must allocate
> memory with specific constraints when sharing it with the hypervisor.

So this is the case where the guest page size is smaller than the host
one. Just trying to understand what would go wrong if we don't do
anything here. Let's say the guest uses 4K pages and the host a 64K
pages. Within a 64K range, only a 4K is shared/decrypted. If the host
does not explicitly access the other 60K around the shared 4K, can
anything still go wrong? Is the hardware ok with speculative loads from
non-shared ranges?

> diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
> index ea84a61ed508..389070e9ee65 100644

I think there's too much change just to pass down an alignment. We have
IO_TLB_MIN_SLABS, we could add an IO_TLB_MIN_ALIGN that's PAGE_SIZE by
default but can be overridden to something dynamic for arm64.

> diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
> index 467cb78435a9..e2142bbca13b 100644

At some point this could move to the DMA API.

> diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
> index 24c359d9c879..5db5baad5efa 100644

You align the size but does __dma_direct_alloc_pages() guarantee a
natural alignment? Digging through cma_alloc_aligned(), it guarantees
the minimum of size and CONFIG_CMA_ALIGNMENT. The latter can be
configured to a page order of 2.

> @@ -382,7 +384,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
>  

We also have the dynamic swiotlb allocations via swiotlb_dyn_alloc() ->
swiotlb_alloc_pool() -> swiotlb_alloc_tlb(). I don't see any alignment
guarantees.

TBH, I'm not too keen on this patch. It feels like a problem to be
solved by the host - don't advertise smaller page sizes to guest or cope
with sub-page memory sharing. Currently the streaming DMA is handled via
bouncing but we may, at some point, just allow set_memory_decrypted() on
the DMA-mapped page. The above requirements will not allow this.

I cannot come up with a better solution though. I hope the hardware can
cope with sub-page shared/non-shared ranges.

---

## [4] Jason Gunthorpe — 2025-09-05
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Fri, Sep 05, 2025 at 02:13:34PM +0100, Catalin Marinas wrote:
> Hi Aneesh,
> 

+1 I'm also confused by this description.

I thought the issue here was in the RMM. The GPT or S2 min granule
could be > 4k and in this case an unaligned set_memory_decrypted()
from the guest would have to fail inside the RMM as impossible to
execute?

Though I'm a little unclear on when and why the S2 needs to be
manipulated. Can't the S2 fully map both the protected and unprotected
IPA space and rely on the GPT for protection?

I do remember having a discussion that set_memory_decrypted() has
nothing to do with the VM's S1 granule size, and it is a mistake to
have linked these together. The VM needs to understand what
granularity the RMM will support set_memory_decrypted() for and follow
that.

I don't recall there is also an issue on the hypervisor? I thought GPT
faults on ARM were going to work well, ie we could cleanly segfault
the VMM process if it touches any protected memory that may have been
mapped into it, and speculation was safe?

> > @@ -213,16 +213,20 @@ static gfp_t gfp_flags_quirk;
> >  static struct page *its_alloc_pages_node(int node, gfp_t gfp,

I don't think we should be open coding these patterns.

Esepcially given the above, it makes no sense to 'alloc page' and then
'decrypt page' on ARM CCA. decryption is not really a OS page level
operation. I suggest coming with some series to clean these up into a
more sensible API.

Everything wanting decrypted memory should be going through some more
general API that has some opportunity to use pools.

DMA API may be one choice, but I know we will need more options in
RDMA land :|

Jason

---

## [5] Catalin Marinas — 2025-09-05
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Fri, Sep 05, 2025 at 01:22:58PM -0300, Jason Gunthorpe wrote:
> On Fri, Sep 05, 2025 at 02:13:34PM +0100, Catalin Marinas wrote:
> > > @@ -213,16 +213,20 @@ static gfp_t gfp_flags_quirk;

I proposed something like GFP_DECRYPTED last year but never got around
to post a proper patch (and also add vmalloc() support):

https://lore.kernel.org/linux-arm-kernel/ZmNJdSxSz-sYpVgI@arm.com/

The GIC ITS code would have been one of the very few users, so we ended
up with open-coding the call to set_memory_decrypted().

---

## [6] Aneesh Kumar K.V — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

Thomas Gleixner <tglx@linutronix.de> writes:

> On Fri, Sep 05 2025 at 11:24, Aneesh Kumar K. V. wrote:
>> When running with private memory guests, the guest kernel must allocate

This patch is required to ensure that a guest using a 4K page size can
safely share pages with a non-secure host that uses a 64K page size.
Without this, the non-secure host may inadvertently map protected
memory.

Memory attribute tracking in the non-secure host (via
set_guest_memory_attributes()) operates in units of the host's
PAGE_SIZE. Attempting to set memory attributes at 4K granularity—when
the host uses 64K pages—will fail with -EINVAL. This makes it impossible
to correctly manage mixed-private/shared regions without enforcing
alignment between guest and host page sizes or introducing finer-grained
handling.


-aneesh

---

## [7] Suzuki K Poulose — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

Hi

On 05/09/2025 17:22, Jason Gunthorpe wrote:
> On Fri, Sep 05, 2025 at 02:13:34PM +0100, Catalin Marinas wrote:
>> Hi Aneesh,

Correct.

>> anything here. Let's say the guest uses 4K pages and the host a 64K
>> pages. Within a 64K range, only a 4K is shared/decrypted. If the host

There are two cases here:

a) Guest memfd as it exists today, with shared pages coming from a 
different pool
b) Guest memfd with mmap support, where shared pages are from the 
guest_memfd.

In either case, guest_memfd tracks the page attributes at PAGE_SIZE
level (64K in this case). Sub-page level tracking is going to make it
complicated. Even with that in place,

with (a), we cannot "punch holes" in the private vs shared pools, to
maintain the sharing, as they are again in PAGE_SIZE. May be we can
relax this for guest_memfd.

with (b) coming in, mapping the shared pages into VMM (e.g., for virtio)
will map the entire 64K page into the userspace (with private and shared
bits) and thus opens up the security loophole of VMM bringing down the
Host with "protected memory" for other operations.

We did bring this up in one of the earlier guest_memfd upstream calls,
and the recommendation was to fix this in the Guest, aligning the
operations to the Host page size [0].

e.g., pKVM guests simply fail the boot if the Guest page size is not
aligned to the Host.

>> anything still go wrong? Is the hardware ok with speculative loads from
>> non-shared ranges?

> 
> +1 I'm also confused by this description.


> 
> Though I'm a little unclear on when and why the S2 needs to be

As mentioned above, the problem lies with the "Host" unable to satisfy
an unaligned request. If we can make that work with the Host, RMM
doesn't need to worry about it.


> 
> I do remember having a discussion that set_memory_decrypted() has

Granularity is determined by the Host (not RMM).

> 
> I don't recall there is also an issue on the hypervisor? I thought GPT

The issue is with the VMM passing this around back to the Kernel and
causing a GPT in the Kernel.


Suzuki


[0] 
https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?pli=1&tab=t.0


> 
>>> @@ -213,16 +213,20 @@ static gfp_t gfp_flags_quirk;

---

## [8] Aneesh Kumar K.V — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

Catalin Marinas <catalin.marinas@arm.com> writes:

> Hi Aneesh,
>

With features like guest_memfd, the goal is to explicitly prevent the
host from mapping private memory, rather than relying on the host to
avoid accessing those regions.

As per Arm ARM:
RVJLXG: Accesses are checked against the GPC configuration for the
physical granule being accessed, regardless of the stage 1 and stage 2
translation configuration.

For example, if GPCCR_EL3.PGS is configured to a smaller granule size
than the configured stage 1 and stage 2 translation granule size,
accesses are checked at the GPCCR_EL3.PGS granule size.

>> diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
>> index ea84a61ed508..389070e9ee65 100644

I will check this.

>
>> @@ -382,7 +384,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,

-aneesh

---

## [9] Catalin Marinas — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Mon, Sep 08, 2025 at 03:07:00PM +0530, Aneesh Kumar K.V wrote:
> Catalin Marinas <catalin.marinas@arm.com> writes:
> > On Fri, Sep 05, 2025 at 11:24:41AM +0530, Aneesh Kumar K.V (Arm) wrote:

Yes, if all the memory is private. At some point the guest will start
sharing memory with the host. In theory, the host could map more than it
was given access to as long as it doesn't touch the area around the
shared range. Not ideal and it may not match the current guest_memfd API
but I'd like to understand all the options we have.

> As per Arm ARM:
> RVJLXG: Accesses are checked against the GPC configuration for the

OK, so this rule doesn't say anything about the granule size at stage 1
or stage 2. The check is purely done based on the PGS field
configuration. The need for the host granule size to match PGS is just a
software construct.

> For example, if GPCCR_EL3.PGS is configured to a smaller granule size
> than the configured stage 1 and stage 2 translation granule size,

I assume GPCCR_EL3.PGS is pre-configured on the system as 4K and part of
the RMM spec.

---

## [10] Suzuki K Poulose — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On 08/09/2025 12:40, Catalin Marinas wrote:
> On Mon, Sep 08, 2025 at 03:07:00PM +0530, Aneesh Kumar K.V wrote:
>> Catalin Marinas <catalin.marinas@arm.com> writes:

The kernel may be taught not to touch the area, but it is tricky when
the shared page gets mapped into the usespace and what it does with it.

> but I'd like to understand all the options we have.
> 

True. The GPC Page Size is going to be 4K. At present the RMM S2 page
size is fixed to 4K. Please note that the future RMM versions may allow
the Host to change the S2 for Realm (Globally) to something other than
4K. (e.g., a 64K host could change it to 64K S2), which allows the host
to manage the Realm S2 better (and efficient).

Irrespective of that, the patch is trying to deal with Host pagesize
(which affects sharing) vs the Realm alignment for sharing pages.

Suzuki



Suzuki

---

## [11] Jason Gunthorpe — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Mon, Sep 08, 2025 at 02:47:21PM +0100, Suzuki K Poulose wrote:
> On 08/09/2025 12:40, Catalin Marinas wrote:
> > On Mon, Sep 08, 2025 at 03:07:00PM +0530, Aneesh Kumar K.V wrote:

But what happes?

The entire reason we have this nasty hyper-restrictive memfd private
memory is beacuse Intel takes a machine check if anything does it
wrong, and that is fatal and can't be handled.

Is ARM like that? I thought ARM had good faults on GPT violation that
could be handled in the same way as a normal page fault?

If ARM has proper faulting then you don't have an issue mapping 64K
into a userspace and just segfaulting the VMM if it does something
wrong.

If not, then sure you need all this unmapping stuff like Intel does :\

> True. The GPC Page Size is going to be 4K. At present the RMM S2 page
> size is fixed to 4K.

A 4k S2 is a pointless thing to do if the VMM is only going to approve
64k shared/private transitions :(

Jason

---

## [12] Steven Price — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On 08/09/2025 15:58, Jason Gunthorpe wrote:
> On Mon, Sep 08, 2025 at 02:47:21PM +0100, Suzuki K Poulose wrote:
>> On 08/09/2025 12:40, Catalin Marinas wrote:

Arm does indeed trigger a 'good fault' in these situations, but...

> If ARM has proper faulting then you don't have an issue mapping 64K
> into a userspace and just segfaulting the VMM if it does something

...the VMM can cause problems. If the VMM touches the memory itself then
things are simple - we can detect that the fault was from user space and
trigger a SIGBUS to kill of the VMM.

But the VMM can also attempt to pass the address into the kernel and
cause the kernel to do a get_user_pages() call (and this is something we
want to support for shared memory). The problem is if the kernel then
touches the parts of the page which are protected we get a fault with no
(easy) way to relate back to the VMM.

guest_memfd provided a nice way around this - a dedicated allocator
which doesn't allow mmap(). This meant we don't need to worry about user
space handing protected memory into the kernel. It's now getting
extended to support mmap() but only when shared, and there was a lot of
discussion about how to ensure that there are no mmap regions when
converting memory back to private.

> If not, then sure you need all this unmapping stuff like Intel does :\

We don't strictly need it, but given the complexity of handling a GPT
violation caused by the kernel, and since the infrastructure is needed
for Intel, it's made sense to largely follow the same path.

>> True. The GPC Page Size is going to be 4K. At present the RMM S2 page
>> size is fixed to 4K.

Indeed. The intention is that longer term the RMM would use the same S2
page size as the host's page size. But we'd like to support
(confidential) guests running with 4k page size under a 64k host/S2.

Short-term the RMM can use a smaller page size with everything still
working, but that's obviously not as efficient.

Steve

---

## [13] Catalin Marinas — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Mon, Sep 08, 2025 at 04:39:13PM +0100, Steven Price wrote:
> On 08/09/2025 15:58, Jason Gunthorpe wrote:
> > If ARM has proper faulting then you don't have an issue mapping 64K

Similarly for uaccess.

> But the VMM can also attempt to pass the address into the kernel and
> cause the kernel to do a get_user_pages() call (and this is something we

I assume the host has a mechanism to check that the memory has been
marked as shared by the guest and the guest cannot claim it back as
private while the host is accessing it (I should dig out the CCA spec).

> guest_memfd provided a nice way around this - a dedicated allocator
> which doesn't allow mmap(). This meant we don't need to worry about user

That's indeed problematic and we don't have a simple way to check that
a user VMM address won't fault when accessed via the linear map. The
vma checks we get with mmap are (host) page size based.

Can we instead only allow mismatched (or smaller) granule sizes in the
guest if the VMM doesn't use the mmap() interface? It's not like
trapping TCR_EL1 but simply rejecting such unaligned memory slots since
the host will need to check that the memory has indeed been shared. KVM
can advertise higher granules only, though the guest can ignore them.

---

## [14] Jason Gunthorpe — 2025-09-08
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Mon, Sep 08, 2025 at 04:39:13PM +0100, Steven Price wrote:

> guest_memfd provided a nice way around this - a dedicated allocator
> which doesn't allow mmap(). This meant we don't need to worry about user

Yes, you probably have to loose mmap() support in this scenario unless
the kernel has lot more work to make things like O_DIRECT aware of
this sub-page safety requirement.

But, IMHO, this is an optimization argument. Unaligned smaller buffers
can memory copy in the VMM using read/write on the memfd. That is safe
on ARM.

I think the need should be made clear in the commit message what the
issue is. As I see it:

1) The RMM may have a 64K S2 or something else and just cannot do
   shared/private at all using 4k

2) The hypervisor wants mmap() of 64K pages to support O_DIRECT.
   Kernel cannot safely support O_DIRECT on partially GPT protected
   64k pages. If userspace tricks the kernel into accessing something
   GPT protected we cannot handle the kernel fault.

Therefor, the VM has to align shared/private pools to some size
specified by the hypervisor that accommodates 1 and 2 above.

Jason

---

## [15] Steven Price — 2025-09-10
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On 08/09/2025 18:25, Catalin Marinas wrote:
> On Mon, Sep 08, 2025 at 04:39:13PM +0100, Steven Price wrote:
>> On 08/09/2025 15:58, Jason Gunthorpe wrote:

Yes, mismatched granules sizes could be supported if we disallowed
mmap(). This is assuming the RMM supports the required size - which is
currently true, but the intention is to optimise the S2 in the future by
matching the host page size.

But I'm not sure how useful that would be. The VMMs of today don't
expect to have to perform read()/write() calls to access the guest's
memory, so any user space emulation would need to also be updated to
deal with this restriction.

But that seems like a lot of effort to support something that doesn't
seem to have a use case. Whereas there's an obvious use case for the
guest and VMM sharing one (or often more) pages of (mapped) memory. The
part that CCA makes this tricky is that we need to pick the VMM's page
size rather than the guest's.

Steve

---

## [16] Catalin Marinas — 2025-09-12
*Subject: Re: [RFC PATCH] arm64: swiotlb: dma: its: Ensure shared buffers are
 properly aligned*

On Wed, Sep 10, 2025 at 11:08:19AM +0100, Steven Price wrote:
> On 08/09/2025 18:25, Catalin Marinas wrote:
> > On Mon, Sep 08, 2025 at 04:39:13PM +0100, Steven Price wrote:

Given that the vmas in Linux are page-aligned, it's too intrusive to
support sub-page granularity in the host (if at all possible). So, based
on the discussion here, we do need the guest to play along and share
mappings with the granularity of the host page size. Of course, one way
is to mandate that the guest uses the same page size as the host.

The original patch needs some more changes mentioned in this thread. It
is missing places where we have set_memory_decrypted() but the size is
not guaranteed to be aligned. I would also replace the
arch_shared_mem_alignment() name with something that resembles the
mem-encrypt API (e.g. mem_encrypt_align(size) for lack of inspiration;
the default would return 'size' so there's no change for other
architectures). Using 'shared' is confusing since the notion of sharing
is not limited to confidential compute.

It does feel like this could be handled at a higher level (e.g. the
virtio code or specific device drivers doing DMA) but it won't be
generic enough. Bouncing of decrypted DMA via swiotlb is already
generic.

BTW, with device assignment, we need a second, encrypted swiotlb as it's
used for bouncing small buffers. Unless we mandate that all devices
assigned to realms are fully coherent.

---
