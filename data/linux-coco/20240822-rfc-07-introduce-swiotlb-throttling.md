---
title: '[RFC 0/7] Introduce swiotlb throttling'
date: 2024-08-22
last_reply: 2024-08-30
message_count: 43
participants: ['mhkelley58@gmail.com', 'Bart Van Assche', 'Michael Kelley', 'Petr Tesařík', 'hch@lst.de', 'Robin Murphy']
---

## [1] mhkelley58@gmail.com — 2024-08-22

From: Michael Kelley <mhklinux@outlook.com>

Background
==========
Linux device drivers may make DMA map/unmap calls in contexts that
cannot block, such as in an interrupt handler. Consequently, when a
DMA map call must use a bounce buffer, the allocation of swiotlb
memory must always succeed immediately. If swiotlb memory is
exhausted, the DMA map call cannot wait for memory to be released. The
call fails, which usually results in an I/O error.

Bounce buffers are usually used infrequently for a few corner cases,
so the default swiotlb memory allocation of 64 MiB is more than
sufficient to avoid running out and causing errors. However, recently
introduced Confidential Computing (CoCo) VMs must use bounce buffers
for all DMA I/O because the VM's memory is encrypted. In CoCo VMs
a new heuristic allocates ~6% of the VM's memory, up to 1 GiB, for
swiotlb memory. This large allocation reduces the likelihood of a
spike in usage causing DMA map failures. Unfortunately for most
workloads, this insurance against spikes comes at the cost of
potentially "wasting" hundreds of MiB's of the VM's memory, as swiotlb
memory can't be used for other purposes.

Approach
========
The goal is to significantly reduce the amount of memory reserved as
swiotlb memory in CoCo VMs, while not unduly increasing the risk of
DMA map failures due to memory exhaustion.

To reach this goal, this patch set introduces the concept of swiotlb
throttling, which can delay swiotlb allocation requests when swiotlb
memory usage is high. This approach depends on the fact that some
DMA map requests are made from contexts where it's OK to block.
Throttling such requests is acceptable to spread out a spike in usage.

Because it's not possible to detect at runtime whether a DMA map call
is made in a context that can block, the calls in key device drivers
must be updated with a MAY_BLOCK attribute, if appropriate. When this
attribute is set and swiotlb memory usage is above a threshold, the
swiotlb allocation code can serialize swiotlb memory usage to help
ensure that it is not exhausted.

In general, storage device drivers can take advantage of the MAY_BLOCK
option, while network device drivers cannot. The Linux block layer
already allows storage requests to block when the BLK_MQ_F_BLOCKING
flag is present on the request queue. In a CoCo VM environment,
relatively few device types are used for storage devices, and updating
these drivers is feasible. This patch set updates the NVMe driver and
the Hyper-V storvsc synthetic storage driver. A few other drivers
might also need to be updated to handle the key CoCo VM storage
devices.

Because network drivers generally cannot use swiotlb throttling, it is
still possible for swiotlb memory to become exhausted. But blunting
the maximum swiotlb memory used by storage devices can significantly
reduce the peak usage, and a smaller amount of swiotlb memory can be
allocated in a CoCo VM. Also, usage by storage drivers is likely to
overall be larger than for network drivers, especially when large
numbers of disk devices are in use, each with many I/O requests in-
flight.

swiotlb throttling does not affect the context requirements of DMA
unmap calls. These always complete without blocking, even if the
corresponding DMA map call was throttled.

Patches
=======
Patches 1 and 2 implement the core of swiotlb throttling. They define
DMA attribute flag DMA_ATTR_MAY_BLOCK that device drivers use to
indicate that a DMA map call is allowed to block, and therefore can be
throttled. They update swiotlb_tbl_map_single() to detect this flag and
implement the throttling. Similarly, swiotlb_tbl_unmap_single() is
updated to handle a previously throttled request that has now freed
its swiotlb memory.

Patch 3 adds the dma_recommend_may_block() call that device drivers
can use to know if there's benefit in using the MAY_BLOCK option on
DMA map calls. If not in a CoCo VM, this call returns "false" because
swiotlb is not being used for all DMA I/O. This allows the driver to
set the BLK_MQ_F_BLOCKING flag on blk-mq request queues only when
there is benefit.

Patch 4 updates the SCSI-specific DMA map calls to add a "_attrs"
variant to allow passing the MAY_BLOCK attribute.

Patch 5 adds the MAY_BLOCK option to the Hyper-V storvsc driver, which
is used for storage in CoCo VMs in the Azure public cloud.

Patches 6 and 7 add the MAY_BLOCK option to the NVMe PCI host driver.

Discussion
==========
* Since swiotlb isn't visible to device drivers, I've specifically
named the DMA attribute as MAY_BLOCK instead of MAY_THROTTLE or
something swiotlb specific. While this patch set consumes MAY_BLOCK
only on the DMA direct path to do throttling in the swiotlb code,
there might be other uses in the future outside of CoCo VMs, or
perhaps on the IOMMU path.

* The swiotlb throttling code in this patch set throttles by
serializing the use of swiotlb memory when usage is above a designated
threshold: i.e., only one new swiotlb request is allowed to proceed at
a time. When the corresponding unmap is done to release its swiotlb
memory, the next request is allowed to proceed. This serialization is
global and without knowledge of swiotlb areas. From a storage I/O
performance standpoint, the serialization is a bit restrictive, but
the code isn't trying to optimize for being above the threshold. If a
workload regularly runs above the threshold, the size of the swiotlb
memory should be increased.

* Except for knowing how much swiotlb memory is currently allocated,
throttle accounting is done without locking or atomic operations. For
example, multiple requests could proceed in parallel when usage is
just under the threshold, putting usage above the threshold by the
aggregate size of the parallel requests. The threshold must already be
set relatively conservatively because of drivers that can't enable
throttling, so this slop in the accounting shouldn't be a problem.
It's better than the potential bottleneck of a globally synchronized
reservation mechanism.

* In a CoCo VM, mapping a scatter/gather list makes an independent
swiotlb request for each entry. Throttling each independent request
wouldn't really work, so the code throttles only the first SGL entry.
Once that entry passes any throttle, subsequent entries in the SGL
proceed without throttling. When the SGL is unmapped, entries 1 thru
N-1 are unmapped first, then entry 0 is unmapped, allowing the next
serialized request to proceed.

Open Topics
===========
1. swiotlb allocations from Xen and the IOMMU code don't make use of
throttling. This could be added if beneficial.

2. The throttling values are currently exposed and adjustable in
/sys/kernel/debug/swiotlb. Should any of this be moved so it is
visible even without CONFIG_DEBUG_FS?

3. I have not changed the current heuristic for the swiotlb memory
size in CoCo VMs. It's not clear to me how to link this to whether the
key storage drivers have been updated to allow throttling. For now,
the benefit of reduced swiotlb memory size must be realized using the
swiotlb= kernel boot line option.

4. I need to update the swiotlb documentation to describe throttling.

This patch set is built against linux-next-20240816.

Michael Kelley (7):
  swiotlb: Introduce swiotlb throttling
  dma: Handle swiotlb throttling for SGLs
  dma: Add function for drivers to know if allowing blocking is useful
  scsi_lib_dma: Add _attrs variant of scsi_dma_map()
  scsi: storvsc: Enable swiotlb throttling
  nvme: Move BLK_MQ_F_BLOCKING indicator to struct nvme_ctrl
  nvme: Enable swiotlb throttling for NVMe PCI devices

 drivers/nvme/host/core.c    |   4 +-
 drivers/nvme/host/nvme.h    |   2 +-
 drivers/nvme/host/pci.c     |  18 ++++--
 drivers/nvme/host/tcp.c     |   3 +-
 drivers/scsi/scsi_lib_dma.c |  13 ++--
 drivers/scsi/storvsc_drv.c  |   9 ++-
 include/linux/dma-mapping.h |  13 ++++
 include/linux/swiotlb.h     |  15 ++++-
 include/scsi/scsi_cmnd.h    |   7 ++-
 kernel/dma/Kconfig          |  13 ++++
 kernel/dma/direct.c         |  41 +++++++++++--
 kernel/dma/direct.h         |   1 +
 kernel/dma/mapping.c        |  10 ++++
 kernel/dma/swiotlb.c        | 114 ++++++++++++++++++++++++++++++++----
 14 files changed, 227 insertions(+), 36 deletions(-)

---

## [2] mhkelley58@gmail.com — 2024-08-22
*Subject: [RFC 1/7] swiotlb: Introduce swiotlb throttling*

From: Michael Kelley <mhklinux@outlook.com>

Implement throttling of swiotlb map requests. Because throttling requires
temporarily pending some requests, throttling can only be used by map
requests made in contexts that can block. Detecting such contexts at
runtime is infeasible, so device driver code must be updated to add
DMA_ATTR_MAY_BLOCK on map requests done in a context that can block.
Even if a map request is throttled, the corresponding unmap request will
never block, so unmap has no context restrictions, just like current code.
If a swiotlb map request does *not* have DMA_ATTR_MAY_BLOCK, no throttling
is done and there is no functional change.

The goal of throttling is to reduce peak usage of swiotlb memory,
particularly in environments like CoCo VMs which must use bounce buffering
for all DMA I/O. These VMs currently allocate up to 1 GiB for swiotlb
memory to ensure that it isn't exhausted. But for many workloads, this
memory is effectively wasted because it can't be used for other purposes.
Throttling can lower the swiotlb memory requirements without unduly raising
the risk of exhaustion, thus making several hundred MiBs of additional
memory available for general usage.

The high-level implementation is as follows:

1.  Each struct io_tlb_mem has a semaphore that is initialized to 1.  A
semaphore is used instead of a mutex because the semaphore likely won't
be released by the same thread that obtained it.

2. Each struct io_tlb_mem has a swiotlb space usage level above which
throttling is done. This usage level is initialized to 70% of the total
size of that io_tlb_mem, and is tunable at runtime via /sys if
CONFIG_DEBUG_FS is set.

3. When swiotlb_tbl_map_single() is invoked with throttling allowed, if
the current usage of that io_tlb_mem is above the throttle level, the
semaphore must be obtained before proceeding. The semaphore is then
released by the corresponding swiotlb unmap call. If the semaphore is
already held when swiotlb_tbl_map_single() must obtain it, the calling
thread blocks until the semaphore is available. Once the thread obtains
the semaphore, it proceeds to allocate swiotlb space in the usual way.
The swiotlb map call saves throttling information in the io_tlb_slot, and
then swiotlb unmap uses that information to determine if the semaphore
is held. If so, it releases the semaphore, potentially allowing a
queued request to proceed. Overall, the semaphore queues multiple waiters
and wakes them up in the order in which they waited. Effectively, the
semaphore single threads map/unmap pairs to reduce peak usage.

4. A "low throttle" level is also implemented and initialized to 65% of
the total size of the io_tlb_mem. If the current usage is between the
throttle level and the low throttle level, AND the semaphore is held, the
requestor must obtain the semaphore. Consider if throttling occurs, so
that one map request holds the semaphore, and three others are queued
waiting for the semaphore. If swiotlb usage then drops because of
unrelated unmap's, a new incoming map request may not get throttled, and
bypass the three requests waiting in the semaphore queue. There's not
a forward progress issue because the requests in the queue will complete
as long as the underlying I/Os make forward progress. But to somewhat
address the fairness issue, the low throttle level provides hysteresis
in that new incoming requests continue to queue on the semaphore as long
as used swiotlb memory is above that lower limit.

5. SGLs are handled in a subsequent patch.

In #3 above the check for being above the throttle level is an
instantaneous check with no locking and no reservation of space, to avoid
atomic operations. Consequently, multiple threads could all make the check
and decide they are under the throttle level. They can all proceed without
obtaining the semaphore, and potentially generate a peak in usage.
Furthermore, other DMA map requests that don't have throttling enabled
proceed without even checking, and hence can also push usage toward a peak.
So throttling can blunt and reduce peaks in swiotlb memory usage, but
does it not guarantee to prevent exhaustion.

Signed-off-by: Michael Kelley <mhklinux@outlook.com>
---
 include/linux/dma-mapping.h |   8 +++
 include/linux/swiotlb.h     |  15 ++++-
 kernel/dma/Kconfig          |  13 ++++
 kernel/dma/swiotlb.c        | 114 ++++++++++++++++++++++++++++++++----
 4 files changed, 136 insertions(+), 14 deletions(-)

diff --git a/include/linux/dma-mapping.h b/include/linux/dma-mapping.h
index f693aafe221f..7b78294813be 100644
--- a/include/linux/dma-mapping.h
+++ b/include/linux/dma-mapping.h
@@ -62,6 +62,14 @@
  */
 #define DMA_ATTR_PRIVILEGED		(1UL << 9)
 
+/*
+ * DMA_ATTR_MAY_BLOCK: Indication by a driver that the DMA map request is
+ * allowed to block. This flag must only be used on DMA map requests made in
+ * contexts that allow blocking. The corresponding unmap request will not
+ * block.
+ */
+#define DMA_ATTR_MAY_BLOCK		(1UL << 10)
+
 /*
  * A dma_addr_t can hold any valid DMA or bus address for the platform.  It can
  * be given to a device to use as a DMA source or target.  It is specific to a
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..10d07d0ee00c 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -89,6 +89,10 @@ struct io_tlb_pool {
  * @defpool:	Default (initial) IO TLB memory pool descriptor.
  * @pool:	IO TLB memory pool descriptor (if not dynamic).
  * @nslabs:	Total number of IO TLB slabs in all pools.
+ * @high_throttle: Slab count above which requests are throttled.
+ * @low_throttle: Slab count abouve which requests are throttled when
+ *		throttle_sem is already held.
+ * @throttle_sem: Semaphore that throttled requests must obtain.
  * @debugfs:	The dentry to debugfs.
  * @force_bounce: %true if swiotlb bouncing is forced
  * @for_alloc:  %true if the pool is used for memory allocation
@@ -104,10 +108,17 @@ struct io_tlb_pool {
  *		in debugfs.
  * @transient_nslabs: The total number of slots in all transient pools that
  *		are currently used across all areas.
+ * @high_throttle_count: Count of requests throttled because high_throttle
+ *		was exceeded.
+ * @low_throttle_count: Count of requests throttled because low_throttle was
+ *		exceeded and throttle_sem was already held.
  */
 struct io_tlb_mem {
 	struct io_tlb_pool defpool;
 	unsigned long nslabs;
+	unsigned long high_throttle;
+	unsigned long low_throttle;
+	struct semaphore throttle_sem;
 	struct dentry *debugfs;
 	bool force_bounce;
 	bool for_alloc;
@@ -118,11 +129,11 @@ struct io_tlb_mem {
 	struct list_head pools;
 	struct work_struct dyn_alloc;
 #endif
-#ifdef CONFIG_DEBUG_FS
 	atomic_long_t total_used;
 	atomic_long_t used_hiwater;
 	atomic_long_t transient_nslabs;
-#endif
+	unsigned long high_throttle_count;
+	unsigned long low_throttle_count;
 };
 
 struct io_tlb_pool *__swiotlb_find_pool(struct device *dev, phys_addr_t paddr);
diff --git a/kernel/dma/Kconfig b/kernel/dma/Kconfig
index c06e56be0ca1..d45ba62f58c8 100644
--- a/kernel/dma/Kconfig
+++ b/kernel/dma/Kconfig
@@ -103,6 +103,19 @@ config SWIOTLB_DYNAMIC
 
 	  If unsure, say N.
 
+config SWIOTLB_THROTTLE
+	bool "Throttle DMA map requests from enabled drivers"
+	default n
+	depends on SWIOTLB
+	help
+	  Enable throttling of DMA map requests to help avoid exhausting
+	  bounce buffer space, causing request failures. Throttling
+	  applies only where the calling driver has enabled blocking in
+	  DMA map requests. This option is most useful in CoCo VMs where
+	  all DMA operations must go through bounce buffers.
+
+	  If unsure, say N.
+
 config DMA_BOUNCE_UNALIGNED_KMALLOC
 	bool
 	depends on SWIOTLB
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index df68d29740a0..940b95cf02b7 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -34,6 +34,7 @@
 #include <linux/init.h>
 #include <linux/memblock.h>
 #include <linux/mm.h>
+#include <linux/semaphore.h>
 #include <linux/pfn.h>
 #include <linux/rculist.h>
 #include <linux/scatterlist.h>
@@ -71,12 +72,15 @@
  *		from each index.
  * @pad_slots:	Number of preceding padding slots. Valid only in the first
  *		allocated non-padding slot.
+ * @throttled:  Boolean indicating the slot is used by a request that was
+ *		throttled. Valid only in the first allocated non-padding slot.
  */
 struct io_tlb_slot {
 	phys_addr_t orig_addr;
 	size_t alloc_size;
 	unsigned short list;
-	unsigned short pad_slots;
+	u8 pad_slots;
+	u8 throttled;
 };
 
 static bool swiotlb_force_bounce;
@@ -249,6 +253,31 @@ static inline unsigned long nr_slots(u64 val)
 	return DIV_ROUND_UP(val, IO_TLB_SIZE);
 }
 
+#ifdef CONFIG_SWIOTLB_THROTTLE
+static void init_throttling(struct io_tlb_mem *mem)
+{
+	sema_init(&mem->throttle_sem, 1);
+
+	/*
+	 * The default thresholds are somewhat arbitrary. They are
+	 * conservative to allow space for devices that can't throttle and
+	 * because the determination of whether to throttle is done without
+	 * any atomicity. The low throttle exists to provide a modest amount
+	 * of hysteresis so that the system doesn't flip rapidly between
+	 * throttling and not throttling when usage fluctuates near the high
+	 * throttle level.
+	 */
+	mem->high_throttle = (mem->nslabs * 70) / 100;
+	mem->low_throttle = (mem->nslabs * 65) / 100;
+}
+#else
+static void init_throttling(struct io_tlb_mem *mem)
+{
+	mem->high_throttle = 0;
+	mem->low_throttle = 0;
+}
+#endif
+
 /*
  * Early SWIOTLB allocation may be too early to allow an architecture to
  * perform the desired operations.  This function allows the architecture to
@@ -415,6 +444,8 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 
 	if (flags & SWIOTLB_VERBOSE)
 		swiotlb_print_info();
+
+	init_throttling(&io_tlb_default_mem);
 }
 
 void __init swiotlb_init(bool addressing_limit, unsigned int flags)
@@ -511,6 +542,7 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 	swiotlb_init_io_tlb_pool(mem, virt_to_phys(vstart), nslabs, true,
 				 nareas);
 	add_mem_pool(&io_tlb_default_mem, mem);
+	init_throttling(&io_tlb_default_mem);
 
 	swiotlb_print_info();
 	return 0;
@@ -947,7 +979,7 @@ static unsigned int wrap_area_index(struct io_tlb_pool *mem, unsigned int index)
  * function gives imprecise results because there's no locking across
  * multiple areas.
  */
-#ifdef CONFIG_DEBUG_FS
+#if defined(CONFIG_DEBUG_FS) || defined(CONFIG_SWIOTLB_THROTTLE)
 static void inc_used_and_hiwater(struct io_tlb_mem *mem, unsigned int nslots)
 {
 	unsigned long old_hiwater, new_used;
@@ -966,14 +998,14 @@ static void dec_used(struct io_tlb_mem *mem, unsigned int nslots)
 	atomic_long_sub(nslots, &mem->total_used);
 }
 
-#else /* !CONFIG_DEBUG_FS */
+#else /* !CONFIG_DEBUG_FS && !CONFIG_SWIOTLB_THROTTLE*/
 static void inc_used_and_hiwater(struct io_tlb_mem *mem, unsigned int nslots)
 {
 }
 static void dec_used(struct io_tlb_mem *mem, unsigned int nslots)
 {
 }
-#endif /* CONFIG_DEBUG_FS */
+#endif /* CONFIG_DEBUG_FS || CONFIG_SWIOTLB_THROTTLE */
 
 #ifdef CONFIG_SWIOTLB_DYNAMIC
 #ifdef CONFIG_DEBUG_FS
@@ -1277,7 +1309,7 @@ static int swiotlb_find_slots(struct device *dev, phys_addr_t orig_addr,
 
 #endif /* CONFIG_SWIOTLB_DYNAMIC */
 
-#ifdef CONFIG_DEBUG_FS
+#if defined(CONFIG_DEBUG_FS) || defined(CONFIG_SWIOTLB_THROTTLE)
 
 /**
  * mem_used() - get number of used slots in an allocator
@@ -1293,7 +1325,7 @@ static unsigned long mem_used(struct io_tlb_mem *mem)
 	return atomic_long_read(&mem->total_used);
 }
 
-#else /* !CONFIG_DEBUG_FS */
+#else /* !CONFIG_DEBUG_FS && !CONFIG_SWIOTLB_THROTTLE */
 
 /**
  * mem_pool_used() - get number of used slots in a memory pool
@@ -1373,6 +1405,7 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 	unsigned int offset;
 	struct io_tlb_pool *pool;
+	bool throttle = false;
 	unsigned int i;
 	size_t size;
 	int index;
@@ -1398,6 +1431,32 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	dev_WARN_ONCE(dev, alloc_align_mask > ~PAGE_MASK,
 		"Alloc alignment may prevent fulfilling requests with max mapping_size\n");
 
+	if (IS_ENABLED(CONFIG_SWIOTLB_THROTTLE) && attrs & DMA_ATTR_MAY_BLOCK) {
+		unsigned long used = atomic_long_read(&mem->total_used);
+
+		/*
+		 * Determining whether to throttle is intentionally done without
+		 * atomicity. For example, multiple requests could proceed in
+		 * parallel when usage is just under the threshold, putting
+		 * usage above the threshold by the aggregate size of the
+		 * parallel requests. The thresholds must already be set
+		 * conservatively because of drivers that can't enable
+		 * throttling, so this slop in the accounting shouldn't be
+		 * problem. It's better than the potential bottleneck of a
+		 * globally synchronzied reservation mechanism.
+		 */
+		if (used > mem->high_throttle) {
+			throttle = true;
+			mem->high_throttle_count++;
+		} else if ((used > mem->low_throttle) &&
+					(mem->throttle_sem.count <= 0)) {
+			throttle = true;
+			mem->low_throttle_count++;
+		}
+		if (throttle)
+			down(&mem->throttle_sem);
+	}
+
 	offset = swiotlb_align_offset(dev, alloc_align_mask, orig_addr);
 	size = ALIGN(mapping_size + offset, alloc_align_mask + 1);
 	index = swiotlb_find_slots(dev, orig_addr, size, alloc_align_mask, &pool);
@@ -1406,6 +1465,8 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 			dev_warn_ratelimited(dev,
 	"swiotlb buffer is full (sz: %zd bytes), total %lu (slots), used %lu (slots)\n",
 				 size, mem->nslabs, mem_used(mem));
+		if (throttle)
+			up(&mem->throttle_sem);
 		return (phys_addr_t)DMA_MAPPING_ERROR;
 	}
 
@@ -1424,6 +1485,7 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	offset &= (IO_TLB_SIZE - 1);
 	index += pad_slots;
 	pool->slots[index].pad_slots = pad_slots;
+	pool->slots[index].throttled = throttle;
 	for (i = 0; i < (nr_slots(size) - pad_slots); i++)
 		pool->slots[index + i].orig_addr = slot_addr(orig_addr, i);
 	tlb_addr = slot_addr(pool->start, index) + offset;
@@ -1440,7 +1502,7 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
 	return tlb_addr;
 }
 
-static void swiotlb_release_slots(struct device *dev, phys_addr_t tlb_addr,
+static bool swiotlb_release_slots(struct device *dev, phys_addr_t tlb_addr,
 				  struct io_tlb_pool *mem)
 {
 	unsigned long flags;
@@ -1448,8 +1510,10 @@ static void swiotlb_release_slots(struct device *dev, phys_addr_t tlb_addr,
 	int index, nslots, aindex;
 	struct io_tlb_area *area;
 	int count, i;
+	bool throttled;
 
 	index = (tlb_addr - offset - mem->start) >> IO_TLB_SHIFT;
+	throttled = mem->slots[index].throttled;
 	index -= mem->slots[index].pad_slots;
 	nslots = nr_slots(mem->slots[index].alloc_size + offset);
 	aindex = index / mem->area_nslabs;
@@ -1478,6 +1542,7 @@ static void swiotlb_release_slots(struct device *dev, phys_addr_t tlb_addr,
 		mem->slots[i].orig_addr = INVALID_PHYS_ADDR;
 		mem->slots[i].alloc_size = 0;
 		mem->slots[i].pad_slots = 0;
+		mem->slots[i].throttled = 0;
 	}
 
 	/*
@@ -1492,6 +1557,8 @@ static void swiotlb_release_slots(struct device *dev, phys_addr_t tlb_addr,
 	spin_unlock_irqrestore(&area->lock, flags);
 
 	dec_used(dev->dma_io_tlb_mem, nslots);
+
+	return throttled;
 }
 
 #ifdef CONFIG_SWIOTLB_DYNAMIC
@@ -1501,6 +1568,9 @@ static void swiotlb_release_slots(struct device *dev, phys_addr_t tlb_addr,
  * @dev:	Device which mapped the buffer.
  * @tlb_addr:	Physical address within a bounce buffer.
  * @pool:       Pointer to the transient memory pool to be checked and deleted.
+ * @throttled:	If the function returns %true, return boolean indicating
+ *		if the transient allocation was throttled. Not set if the
+ *		function returns %false.
  *
  * Check whether the address belongs to a transient SWIOTLB memory pool.
  * If yes, then delete the pool.
@@ -1508,11 +1578,18 @@ static void swiotlb_release_slots(struct device *dev, phys_addr_t tlb_addr,
  * Return: %true if @tlb_addr belonged to a transient pool that was released.
  */
 static bool swiotlb_del_transient(struct device *dev, phys_addr_t tlb_addr,
-		struct io_tlb_pool *pool)
+		struct io_tlb_pool *pool, bool *throttled)
 {
+	unsigned int offset;
+	int index;
+
 	if (!pool->transient)
 		return false;
 
+	offset = swiotlb_align_offset(dev, 0, tlb_addr);
+	index = (tlb_addr - offset - pool->start) >> IO_TLB_SHIFT;
+	*throttled = pool->slots[index].throttled;
+
 	dec_used(dev->dma_io_tlb_mem, pool->nslabs);
 	swiotlb_del_pool(dev, pool);
 	dec_transient_used(dev->dma_io_tlb_mem, pool->nslabs);
@@ -1522,7 +1599,7 @@ static bool swiotlb_del_transient(struct device *dev, phys_addr_t tlb_addr,
 #else  /* !CONFIG_SWIOTLB_DYNAMIC */
 
 static inline bool swiotlb_del_transient(struct device *dev,
-		phys_addr_t tlb_addr, struct io_tlb_pool *pool)
+		phys_addr_t tlb_addr, struct io_tlb_pool *pool, bool *throttled)
 {
 	return false;
 }
@@ -1536,6 +1613,8 @@ void __swiotlb_tbl_unmap_single(struct device *dev, phys_addr_t tlb_addr,
 		size_t mapping_size, enum dma_data_direction dir,
 		unsigned long attrs, struct io_tlb_pool *pool)
 {
+	bool throttled;
+
 	/*
 	 * First, sync the memory before unmapping the entry
 	 */
@@ -1544,9 +1623,11 @@ void __swiotlb_tbl_unmap_single(struct device *dev, phys_addr_t tlb_addr,
 		swiotlb_bounce(dev, tlb_addr, mapping_size,
 						DMA_FROM_DEVICE, pool);
 
-	if (swiotlb_del_transient(dev, tlb_addr, pool))
-		return;
-	swiotlb_release_slots(dev, tlb_addr, pool);
+	if (!swiotlb_del_transient(dev, tlb_addr, pool, &throttled))
+		throttled = swiotlb_release_slots(dev, tlb_addr, pool);
+
+	if (throttled)
+		up(&dev->dma_io_tlb_mem->throttle_sem);
 }
 
 void __swiotlb_sync_single_for_device(struct device *dev, phys_addr_t tlb_addr,
@@ -1719,6 +1800,14 @@ static void swiotlb_create_debugfs_files(struct io_tlb_mem *mem,
 		return;
 
 	debugfs_create_ulong("io_tlb_nslabs", 0400, mem->debugfs, &mem->nslabs);
+	debugfs_create_ulong("high_throttle", 0600, mem->debugfs,
+			&mem->high_throttle);
+	debugfs_create_ulong("low_throttle", 0600, mem->debugfs,
+			&mem->low_throttle);
+	debugfs_create_ulong("high_throttle_count", 0600, mem->debugfs,
+			&mem->high_throttle_count);
+	debugfs_create_ulong("low_throttle_count", 0600, mem->debugfs,
+			&mem->low_throttle_count);
 	debugfs_create_file("io_tlb_used", 0400, mem->debugfs, mem,
 			&fops_io_tlb_used);
 	debugfs_create_file("io_tlb_used_hiwater", 0600, mem->debugfs, mem,
@@ -1841,6 +1930,7 @@ static int rmem_swiotlb_device_init(struct reserved_mem *rmem,
 		INIT_LIST_HEAD_RCU(&mem->pools);
 #endif
 		add_mem_pool(mem, pool);
+		init_throttling(mem);
 
 		rmem->priv = mem;

---

## [3] mhkelley58@gmail.com — 2024-08-22
*Subject: [RFC 2/7] dma: Handle swiotlb throttling for SGLs*

From: Michael Kelley <mhklinux@outlook.com>

When a DMA map request is for a SGL, each SGL entry results in an
independent mapping operation. If the mapping requires a bounce buffer
due to running in a CoCo VM or due to swiotlb=force on the boot line,
swiotlb is invoked. If swiotlb throttling is enabled for the request,
each SGL entry results in a separate throttling operation. This is
problematic because a thread may be holding swiotlb memory while waiting
for memory to become free.

Resolve this problem by only allowing throttling on the 0th SGL
entry. When unmapping the SGL, unmap entries 1 thru N-1 first, then
unmap entry 0 so that the throttle isn't released until all swiotlb
memory has been freed.

Signed-off-by: Michael Kelley <mhklinux@outlook.com>
---
This approach to SGLs muddies the line between DMA direct and swiotlb
throttling functionality. To keep the MAY_BLOCK attr fully generic, it
should propagate to the mapping of all SGL entries.

An alternate approach is to define an additional DMA attribute that
is internal to the DMA layer. Instead of clearing MAX_BLOCK, this
attr is added by dma_direct_map_sg() when mapping SGL entries other
than the 0th entry. swiotlb would do throttling only when MAY_BLOCK
is set and this new attr is not set.

This approach has a modest amount of additional complexity. Given
that we currently have no other users of the MAY_BLOCK attr, the
conceptual cleanliness may not be warranted until we do.

Thoughts?

 kernel/dma/direct.c | 35 ++++++++++++++++++++++++++++++-----
 1 file changed, 30 insertions(+), 5 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 4480a3cd92e0..80e03c0838d4 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -438,6 +438,18 @@ void dma_direct_sync_sg_for_cpu(struct device *dev,
 		arch_sync_dma_for_cpu_all();
 }
 
+static void dma_direct_unmap_sgl_entry(struct device *dev,
+		struct scatterlist *sgl, enum dma_data_direction dir,
+		unsigned long attrs)
+
+{
+	if (sg_dma_is_bus_address(sgl))
+		sg_dma_unmark_bus_address(sgl);
+	else
+		dma_direct_unmap_page(dev, sgl->dma_address,
+				      sg_dma_len(sgl), dir, attrs);
+}
+
 /*
  * Unmaps segments, except for ones marked as pci_p2pdma which do not
  * require any further action as they contain a bus address.
@@ -449,12 +461,20 @@ void dma_direct_unmap_sg(struct device *dev, struct scatterlist *sgl,
 	int i;
 
 	for_each_sg(sgl,  sg, nents, i) {
-		if (sg_dma_is_bus_address(sg))
-			sg_dma_unmark_bus_address(sg);
-		else
-			dma_direct_unmap_page(dev, sg->dma_address,
-					      sg_dma_len(sg), dir, attrs);
+		/*
+		 * Skip the 0th SGL entry in case this SGL consists of
+		 * throttled swiotlb mappings. In such a case, any other
+		 * entries should be unmapped first since unmapping the
+		 * 0th entry will release the throttle semaphore.
+		 */
+		if (!i)
+			continue;
+		dma_direct_unmap_sgl_entry(dev, sg, dir, attrs);
 	}
+
+	/* Now do the 0th SGL entry */
+	if (nents)
+		dma_direct_unmap_sgl_entry(dev, sgl, dir, attrs);
 }
 #endif
 
@@ -492,6 +512,11 @@ int dma_direct_map_sg(struct device *dev, struct scatterlist *sgl, int nents,
 			ret = -EIO;
 			goto out_unmap;
 		}
+
+		/* Allow only the 0th SGL entry to block */
+		if (!i)
+			attrs &= ~DMA_ATTR_MAY_BLOCK;
+
 		sg_dma_len(sg) = sg->length;
 	}

---

## [4] mhkelley58@gmail.com — 2024-08-22
*Subject: [RFC 3/7] dma: Add function for drivers to know if allowing blocking is useful*

From: Michael Kelley <mhklinux@outlook.com>

With the addition of swiotlb throttling functionality, storage
device drivers may want to know whether using the DMA_ATTR_MAY_BLOCK
attribute is useful. In a CoCo VM or environment where swiotlb=force
is used, the MAY_BLOCK attribute enables swiotlb throttling. But if
throttling is not enable or useful, storage device drivers probably
do not want to set BLK_MQ_F_BLOCKING at the blk-mq request queue level.

Add function dma_recommend_may_block() that indicates whether
the underlying implementation of the DMA map calls would benefit
from allowing blocking. If the kernel was built with
CONFIG_SWIOTLB_THROTTLE, and swiotlb=force is set (on the kernel
command line or due to being a CoCo VM), this function returns
true. Otherwise it returns false.

Signed-off-by: Michael Kelley <mhklinux@outlook.com>
---
 include/linux/dma-mapping.h |  5 +++++
 kernel/dma/direct.c         |  6 ++++++
 kernel/dma/direct.h         |  1 +
 kernel/dma/mapping.c        | 10 ++++++++++
 4 files changed, 22 insertions(+)

diff --git a/include/linux/dma-mapping.h b/include/linux/dma-mapping.h
index 7b78294813be..ec2edf068218 100644
--- a/include/linux/dma-mapping.h
+++ b/include/linux/dma-mapping.h
@@ -145,6 +145,7 @@ int dma_set_mask(struct device *dev, u64 mask);
 int dma_set_coherent_mask(struct device *dev, u64 mask);
 u64 dma_get_required_mask(struct device *dev);
 bool dma_addressing_limited(struct device *dev);
+bool dma_recommend_may_block(struct device *dev);
 size_t dma_max_mapping_size(struct device *dev);
 size_t dma_opt_mapping_size(struct device *dev);
 unsigned long dma_get_merge_boundary(struct device *dev);
@@ -252,6 +253,10 @@ static inline bool dma_addressing_limited(struct device *dev)
 {
 	return false;
 }
+static inline bool dma_recommend_may_block(struct device *dev)
+{
+	return false;
+}
 static inline size_t dma_max_mapping_size(struct device *dev)
 {
 	return 0;
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 80e03c0838d4..34d14e4ace64 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -649,6 +649,12 @@ bool dma_direct_all_ram_mapped(struct device *dev)
 				      check_ram_in_range_map);
 }
 
+bool dma_direct_recommend_may_block(struct device *dev)
+{
+	return IS_ENABLED(CONFIG_SWIOTLB_THROTTLE) &&
+			is_swiotlb_force_bounce(dev);
+}
+
 size_t dma_direct_max_mapping_size(struct device *dev)
 {
 	/* If SWIOTLB is active, use its maximum mapping size */
diff --git a/kernel/dma/direct.h b/kernel/dma/direct.h
index d2c0b7e632fc..63516a540276 100644
--- a/kernel/dma/direct.h
+++ b/kernel/dma/direct.h
@@ -21,6 +21,7 @@ bool dma_direct_need_sync(struct device *dev, dma_addr_t dma_addr);
 int dma_direct_map_sg(struct device *dev, struct scatterlist *sgl, int nents,
 		enum dma_data_direction dir, unsigned long attrs);
 bool dma_direct_all_ram_mapped(struct device *dev);
+bool dma_direct_recommend_may_block(struct device *dev);
 size_t dma_direct_max_mapping_size(struct device *dev);
 
 #if defined(CONFIG_ARCH_HAS_SYNC_DMA_FOR_DEVICE) || \
diff --git a/kernel/dma/mapping.c b/kernel/dma/mapping.c
index b1c18058d55f..832982bafd5a 100644
--- a/kernel/dma/mapping.c
+++ b/kernel/dma/mapping.c
@@ -858,6 +858,16 @@ bool dma_addressing_limited(struct device *dev)
 }
 EXPORT_SYMBOL_GPL(dma_addressing_limited);
 
+bool dma_recommend_may_block(struct device *dev)
+{
+	const struct dma_map_ops *ops = get_dma_ops(dev);
+
+	if (dma_map_direct(dev, ops))
+		return dma_direct_recommend_may_block(dev);
+	return false;
+}
+EXPORT_SYMBOL_GPL(dma_recommend_may_block);
+
 size_t dma_max_mapping_size(struct device *dev)
 {
 	const struct dma_map_ops *ops = get_dma_ops(dev);

---

## [5] mhkelley58@gmail.com — 2024-08-22
*Subject: [RFC 4/7] scsi_lib_dma: Add _attrs variant of scsi_dma_map()*

From: Michael Kelley <mhklinux@outlook.com>

Extend the SCSI DMA mapping interfaces by adding the "_attrs" variant
of scsi_dma_map(). This variant allows passing DMA_ATTR_* values, such
as is needed to support swiotlb throttling. The existing scsi_dma_map()
interface is unchanged, so no incompatibilities are introduced.

Signed-off-by: Michael Kelley <mhklinux@outlook.com>
---
 drivers/scsi/scsi_lib_dma.c | 13 +++++++------
 include/scsi/scsi_cmnd.h    |  7 +++++--
 2 files changed, 12 insertions(+), 8 deletions(-)

diff --git a/drivers/scsi/scsi_lib_dma.c b/drivers/scsi/scsi_lib_dma.c
index 5723915275ad..34453a79be97 100644
--- a/drivers/scsi/scsi_lib_dma.c
+++ b/drivers/scsi/scsi_lib_dma.c
@@ -14,30 +14,31 @@
 #include <scsi/scsi_host.h>
 
 /**
- * scsi_dma_map - perform DMA mapping against command's sg lists
+ * scsi_dma_map_attrs - perform DMA mapping against command's sg lists
  * @cmd:	scsi command
+ * @attrs:	DMA attribute flags
  *
  * Returns the number of sg lists actually used, zero if the sg lists
  * is NULL, or -ENOMEM if the mapping failed.
  */
-int scsi_dma_map(struct scsi_cmnd *cmd)
+int scsi_dma_map_attrs(struct scsi_cmnd *cmd, unsigned long attrs)
 {
 	int nseg = 0;
 
 	if (scsi_sg_count(cmd)) {
 		struct device *dev = cmd->device->host->dma_dev;
 
-		nseg = dma_map_sg(dev, scsi_sglist(cmd), scsi_sg_count(cmd),
-				  cmd->sc_data_direction);
+		nseg = dma_map_sg_attrs(dev, scsi_sglist(cmd),
+			scsi_sg_count(cmd), cmd->sc_data_direction, attrs);
 		if (unlikely(!nseg))
 			return -ENOMEM;
 	}
 	return nseg;
 }
-EXPORT_SYMBOL(scsi_dma_map);
+EXPORT_SYMBOL(scsi_dma_map_attrs);
 
 /**
- * scsi_dma_unmap - unmap command's sg lists mapped by scsi_dma_map
+ * scsi_dma_unmap - unmap command's sg lists mapped by scsi_dma_map_attrs
  * @cmd:	scsi command
  */
 void scsi_dma_unmap(struct scsi_cmnd *cmd)
diff --git a/include/scsi/scsi_cmnd.h b/include/scsi/scsi_cmnd.h
index 45c40d200154..6603003bc588 100644
--- a/include/scsi/scsi_cmnd.h
+++ b/include/scsi/scsi_cmnd.h
@@ -170,11 +170,14 @@ extern void scsi_kunmap_atomic_sg(void *virt);
 blk_status_t scsi_alloc_sgtables(struct scsi_cmnd *cmd);
 void scsi_free_sgtables(struct scsi_cmnd *cmd);
 
+#define scsi_dma_map(cmd) scsi_dma_map_attrs(cmd, 0)
+
 #ifdef CONFIG_SCSI_DMA
-extern int scsi_dma_map(struct scsi_cmnd *cmd);
+extern int scsi_dma_map_attrs(struct scsi_cmnd *cmd, unsigned long attrs);
 extern void scsi_dma_unmap(struct scsi_cmnd *cmd);
 #else /* !CONFIG_SCSI_DMA */
-static inline int scsi_dma_map(struct scsi_cmnd *cmd) { return -ENOSYS; }
+static inline int scsi_dma_map_attrs(struct scsi_cmnd *cmd, unsigned long attrs)
+						{ return -ENOSYS; }
 static inline void scsi_dma_unmap(struct scsi_cmnd *cmd) { }
 #endif /* !CONFIG_SCSI_DMA */

---

## [6] mhkelley58@gmail.com — 2024-08-22
*Subject: [RFC 5/7] scsi: storvsc: Enable swiotlb throttling*

From: Michael Kelley <mhklinux@outlook.com>

In a CoCo VM, all DMA-based I/O must use swiotlb bounce buffers
because DMA cannot be done to private (encrypted) portions of VM
memory. The bounce buffer memory is marked shared (decrypted) at
boot time, so I/O is done to/from the bounce buffer memory and then
copied by the CPU to/from the final target memory (i.e, "bounced").
Storage devices can be large consumers of bounce buffer memory because it
is possible to have large numbers of I/Os in flight across multiple
devices. Bounce buffer memory must be pre-allocated at boot time, and
it is difficult to know how much memory to allocate to handle peak
storage I/O loads. Consequently, bounce buffer memory is typically
over-provisioned, which wastes memory, and may still not avoid a peak
that exhausts bounce buffer memory and cause storage I/O errors.

To solve this problem for Coco VMs running on Hyper-V, update the
storvsc driver to permit bounce buffer throttling. First, use
scsi_dma_map_attrs() instead of scsi_dma_map(). Then gate the
throttling behavior on a DMA layer check indicating that throttling is
useful, so that no change occurs in a non-CoCo VM. If throttling is
useful, pass the DMA_ATTR_MAY_BLOCK attribute, and set the block queue
flag indicating that the I/O request submission path may sleep, which
could happen when throttling. With these options in place, DMA map
requests are pended when necessary to reduce the likelihood of usage
peaks caused by storvsc that could exhaust bounce buffer memory and
generate errors.

Signed-off-by: Michael Kelley <mhklinux@outlook.com>
---
 drivers/scsi/storvsc_drv.c | 9 ++++++++-
 1 file changed, 8 insertions(+), 1 deletion(-)

diff --git a/drivers/scsi/storvsc_drv.c b/drivers/scsi/storvsc_drv.c
index 7ceb982040a5..7bedd5502d07 100644
--- a/drivers/scsi/storvsc_drv.c
+++ b/drivers/scsi/storvsc_drv.c
@@ -457,6 +457,7 @@ struct hv_host_device {
 	struct workqueue_struct *handle_error_wq;
 	struct work_struct host_scan_work;
 	struct Scsi_Host *host;
+	unsigned long dma_attrs;
 };
 
 struct storvsc_scan_work {
@@ -1810,7 +1811,7 @@ static int storvsc_queuecommand(struct Scsi_Host *host, struct scsi_cmnd *scmnd)
 		payload->range.len = length;
 		payload->range.offset = offset_in_hvpg;
 
-		sg_count = scsi_dma_map(scmnd);
+		sg_count = scsi_dma_map_attrs(scmnd, host_dev->dma_attrs);
 		if (sg_count < 0) {
 			ret = SCSI_MLQUEUE_DEVICE_BUSY;
 			goto err_free_payload;
@@ -2030,6 +2031,12 @@ static int storvsc_probe(struct hv_device *device,
 	 *    have an offset that is a multiple of HV_HYP_PAGE_SIZE.
 	 */
 	host->sg_tablesize = (max_xfer_bytes >> HV_HYP_PAGE_SHIFT) + 1;
+
+	if (dma_recommend_may_block(&device->device)) {
+		host->queuecommand_may_block = true;
+		host_dev->dma_attrs = DMA_ATTR_MAY_BLOCK;
+	}
+
 	/*
 	 * For non-IDE disks, the host supports multiple channels.
 	 * Set the number of HW queues we are supporting.

---

## [7] mhkelley58@gmail.com — 2024-08-22
*Subject: [RFC 6/7] nvme: Move BLK_MQ_F_BLOCKING indicator to struct nvme_ctrl*

From: Michael Kelley <mhklinux@outlook.com>

The NVMe setting that controls the BLK_MQ_F_BLOCKING flag on the
request queue is currently a flag in struct nvme_ctrl_ops, where
it is not writable. A new use case needs this flag to be writable
based on a determination made during the NVMe device probe function.

Move this setting to struct nvme_ctrl, and update the only user to
set it in the new location.

No functional change.

Signed-off-by: Michael Kelley <mhklinux@outlook.com>
---
 drivers/nvme/host/core.c | 4 ++--
 drivers/nvme/host/nvme.h | 2 +-
 drivers/nvme/host/tcp.c  | 3 ++-
 3 files changed, 5 insertions(+), 4 deletions(-)

diff --git a/drivers/nvme/host/core.c b/drivers/nvme/host/core.c
index 33fa01c599ad..f1ce325471f1 100644
--- a/drivers/nvme/host/core.c
+++ b/drivers/nvme/host/core.c
@@ -4495,7 +4495,7 @@ int nvme_alloc_admin_tag_set(struct nvme_ctrl *ctrl, struct blk_mq_tag_set *set,
 		set->reserved_tags = 2;
 	set->numa_node = ctrl->numa_node;
 	set->flags = BLK_MQ_F_NO_SCHED;
-	if (ctrl->ops->flags & NVME_F_BLOCKING)
+	if (ctrl->blocking)
 		set->flags |= BLK_MQ_F_BLOCKING;
 	set->cmd_size = cmd_size;
 	set->driver_data = ctrl;
@@ -4565,7 +4565,7 @@ int nvme_alloc_io_tag_set(struct nvme_ctrl *ctrl, struct blk_mq_tag_set *set,
 		set->reserved_tags = 1;
 	set->numa_node = ctrl->numa_node;
 	set->flags = BLK_MQ_F_SHOULD_MERGE;
-	if (ctrl->ops->flags & NVME_F_BLOCKING)
+	if (ctrl->blocking)
 		set->flags |= BLK_MQ_F_BLOCKING;
 	set->cmd_size = cmd_size,
 	set->driver_data = ctrl;
diff --git a/drivers/nvme/host/nvme.h b/drivers/nvme/host/nvme.h
index ae5314d32943..28709f166cab 100644
--- a/drivers/nvme/host/nvme.h
+++ b/drivers/nvme/host/nvme.h
@@ -338,6 +338,7 @@ struct nvme_ctrl {
 	unsigned int shutdown_timeout;
 	unsigned int kato;
 	bool subsystem;
+	bool blocking;
 	unsigned long quirks;
 	struct nvme_id_power_state psd[32];
 	struct nvme_effects_log *effects;
@@ -546,7 +547,6 @@ struct nvme_ctrl_ops {
 	unsigned int flags;
 #define NVME_F_FABRICS			(1 << 0)
 #define NVME_F_METADATA_SUPPORTED	(1 << 1)
-#define NVME_F_BLOCKING			(1 << 2)
 
 	const struct attribute_group **dev_attr_groups;
 	int (*reg_read32)(struct nvme_ctrl *ctrl, u32 off, u32 *val);
diff --git a/drivers/nvme/host/tcp.c b/drivers/nvme/host/tcp.c
index 9ea6be0b0392..6b9fdf7dc1ac 100644
--- a/drivers/nvme/host/tcp.c
+++ b/drivers/nvme/host/tcp.c
@@ -2658,7 +2658,7 @@ static const struct blk_mq_ops nvme_tcp_admin_mq_ops = {
 static const struct nvme_ctrl_ops nvme_tcp_ctrl_ops = {
 	.name			= "tcp",
 	.module			= THIS_MODULE,
-	.flags			= NVME_F_FABRICS | NVME_F_BLOCKING,
+	.flags			= NVME_F_FABRICS,
 	.reg_read32		= nvmf_reg_read32,
 	.reg_read64		= nvmf_reg_read64,
 	.reg_write32		= nvmf_reg_write32,
@@ -2762,6 +2762,7 @@ static struct nvme_tcp_ctrl *nvme_tcp_alloc_ctrl(struct device *dev,
 	if (ret)
 		goto out_kfree_queues;
 
+	ctrl->ctrl.blocking = true;
 	return ctrl;
 out_kfree_queues:
 	kfree(ctrl->queues);

---

## [8] mhkelley58@gmail.com — 2024-08-22
*Subject: [RFC 7/7] nvme: Enable swiotlb throttling for NVMe PCI devices*

From: Michael Kelley <mhklinux@outlook.com>

In a CoCo VM, all DMA-based I/O must use swiotlb bounce buffers
because DMA cannot be done to private (encrypted) portions of VM
memory. The bounce buffer memory is marked shared (decrypted) at
boot time, so I/O is done to/from the bounce buffer memory and then
copied by the CPU to/from the final target memory (i.e, "bounced").
Storage devices can be large consumers of bounce buffer memory because
it is possible to have large numbers of I/Os in flight across multiple
devices. Bounce buffer memory must be pre-allocated at boot time, and
it is difficult to know how much memory to allocate to handle peak
storage I/O loads. Consequently, bounce buffer memory is typically
over-provisioned, which wastes memory, and may still not avoid a peak
that exhausts bounce buffer memory and cause storage I/O errors.

For Coco VMs running with NVMe PCI devices, update the driver to
permit bounce buffer throttling. Gate the throttling behavior
on a DMA layer check indicating that throttling is useful, so that
no change occurs in a non-CoCo VM. If throttling is useful, enable
the BLK_MQ_F_BLOCKING flag, and pass the DMA_ATTR_MAY_BLOCK attribute
into dma_map_bvec() and dma_map_sgtable() calls. With these options in
place, DMA map requests are pended when necessary to reduce the
likelihood of usage peaks caused by the NVMe driver that could exhaust
bounce buffer memory and generate errors.

Signed-off-by: Michael Kelley <mhklinux@outlook.com>
---
 drivers/nvme/host/pci.c | 18 ++++++++++++++----
 1 file changed, 14 insertions(+), 4 deletions(-)

diff --git a/drivers/nvme/host/pci.c b/drivers/nvme/host/pci.c
index 6cd9395ba9ec..2c39943a87f8 100644
--- a/drivers/nvme/host/pci.c
+++ b/drivers/nvme/host/pci.c
@@ -156,6 +156,7 @@ struct nvme_dev {
 	dma_addr_t host_mem_descs_dma;
 	struct nvme_host_mem_buf_desc *host_mem_descs;
 	void **host_mem_desc_bufs;
+	unsigned long dma_attrs;
 	unsigned int nr_allocated_queues;
 	unsigned int nr_write_queues;
 	unsigned int nr_poll_queues;
@@ -735,7 +736,8 @@ static blk_status_t nvme_setup_prp_simple(struct nvme_dev *dev,
 	unsigned int offset = bv->bv_offset & (NVME_CTRL_PAGE_SIZE - 1);
 	unsigned int first_prp_len = NVME_CTRL_PAGE_SIZE - offset;
 
-	iod->first_dma = dma_map_bvec(dev->dev, bv, rq_dma_dir(req), 0);
+	iod->first_dma = dma_map_bvec(dev->dev, bv, rq_dma_dir(req),
+					dev->dma_attrs);
 	if (dma_mapping_error(dev->dev, iod->first_dma))
 		return BLK_STS_RESOURCE;
 	iod->dma_len = bv->bv_len;
@@ -754,7 +756,8 @@ static blk_status_t nvme_setup_sgl_simple(struct nvme_dev *dev,
 {
 	struct nvme_iod *iod = blk_mq_rq_to_pdu(req);
 
-	iod->first_dma = dma_map_bvec(dev->dev, bv, rq_dma_dir(req), 0);
+	iod->first_dma = dma_map_bvec(dev->dev, bv, rq_dma_dir(req),
+					dev->dma_attrs);
 	if (dma_mapping_error(dev->dev, iod->first_dma))
 		return BLK_STS_RESOURCE;
 	iod->dma_len = bv->bv_len;
@@ -800,7 +803,7 @@ static blk_status_t nvme_map_data(struct nvme_dev *dev, struct request *req,
 		goto out_free_sg;
 
 	rc = dma_map_sgtable(dev->dev, &iod->sgt, rq_dma_dir(req),
-			     DMA_ATTR_NO_WARN);
+			     dev->dma_attrs | DMA_ATTR_NO_WARN);
 	if (rc) {
 		if (rc == -EREMOTEIO)
 			ret = BLK_STS_TARGET;
@@ -828,7 +831,8 @@ static blk_status_t nvme_map_metadata(struct nvme_dev *dev, struct request *req,
 	struct nvme_iod *iod = blk_mq_rq_to_pdu(req);
 	struct bio_vec bv = rq_integrity_vec(req);
 
-	iod->meta_dma = dma_map_bvec(dev->dev, &bv, rq_dma_dir(req), 0);
+	iod->meta_dma = dma_map_bvec(dev->dev, &bv, rq_dma_dir(req),
+					dev->dma_attrs);
 	if (dma_mapping_error(dev->dev, iod->meta_dma))
 		return BLK_STS_IOERR;
 	cmnd->rw.metadata = cpu_to_le64(iod->meta_dma);
@@ -3040,6 +3044,12 @@ static struct nvme_dev *nvme_pci_alloc_dev(struct pci_dev *pdev,
 	 * a single integrity segment for the separate metadata pointer.
 	 */
 	dev->ctrl.max_integrity_segments = 1;
+
+	if (dma_recommend_may_block(dev->dev)) {
+		dev->ctrl.blocking = true;
+		dev->dma_attrs = DMA_ATTR_MAY_BLOCK;
+	}
+
 	return dev;
 
 out_put_device:

---

## [9] Bart Van Assche — 2024-08-22
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On 8/22/24 11:37 AM, mhkelley58@gmail.com wrote:
> Linux device drivers may make DMA map/unmap calls in contexts that
> cannot block, such as in an interrupt handler.

Although I really appreciate your work, what alternatives have been
considered? How many drivers perform DMA mapping from atomic context?
Would it be feasible to modify these drivers such that DMA mapping
always happens in a context in which sleeping is allowed?

Thanks,

Bart.

---

## [10] Michael Kelley — 2024-08-23
*Subject: RE: [RFC 0/7] Introduce swiotlb throttling*

From: Bart Van Assche <bvanassche@acm.org> Sent: Thursday, August 22, 2024 12:29 PM
> 
> On 8/22/24 11:37 AM, mhkelley58@gmail.com wrote:

I had assumed that allowing DMA mapping from interrupt context is a
long-time fundamental requirement that can't be changed.  It's been
allowed at least for the past 20 years, as Linus added this statement to
kernel documentation in 2005:

   The streaming DMA mapping routines can be called from interrupt context.

But I don't have any idea how many drivers actually do that. There are
roughly 1700 call sites in kernel code/drivers that call one of the
dma_map_*() variants, so looking through them all doesn't seem
feasible. From the limited samples I looked at, block device drivers
typically do not call dma_map_*() from interrupt context, though they
do call dma_unmap_*(). Network drivers _do_ call dma_map_*()
from interrupt context, and that seems likely to be an artifact of the
generic networking framework that the drivers fit into. I haven't looked
at any other device types. 

Christoph Hellwig, or anyone else who knows the history and current
reality better than I do, please jump in. :-)

Michael

---

## [11] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Fri, 23 Aug 2024 02:20:41 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Bart Van Assche <bvanassche@acm.org> Sent: Thursday, August 22, 2024 12:29 PM
> > 

Besides, calls from interrupt context are not the only calls which are
not allowed to schedule (e.g. lock nesting comes to mind). Even if we
agreed to make DMA mapping routines blocking, I believe the easiest way
would be to start adding DMA_ATTR_MAY_BLOCK until it would be used by
all drivers. ;-)

But most importantly, if streaming DMA could block, there would be no
need for a SWIOTLB, because you could simply allocate a bounce buffer
from the buddy allocator when it's needed.

Petr T

---

## [12] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

Hi all,

upfront, I've had more time to consider this idea, because Michael
kindly shared it with me back in February.

On Thu, 22 Aug 2024 11:37:11 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

FTR most I/O errors are recoverable, but the recovery usually takes
a lot of time. Plus the errors are logged and usually treated as
important by monitoring software. In short, I agree it's a poor choice.

> Bounce buffers are usually used infrequently for a few corner cases,
> so the default swiotlb memory allocation of 64 MiB is more than

It may be worth mentioning that page encryption state can be changed by
a hypercall, but that's a costly (and non-atomic) operation. It's much
faster to copy the data to a page which is already unencrypted (a
bounce buffer).

> Approach
> ========

Before somebody asks, the general agreement for decades has been that
there should be no global state indicating whether the kernel is in
atomic context. Instead, if a function needs to know, it should take an
explicit parameter.

IOW this MAY_BLOCK attribute follows an unquestioned kernel design
pattern.

> When this
> attribute is set and swiotlb memory usage is above a threshold, the

The system can also handle network packet loss much better than I/O
errors, mainly because lost packets have always been part of normal
operation, unlike I/O errors. After all, that's why we unmount all
filesystems on removable media before physically unplugging (or
ejecting) them.

> swiotlb throttling does not affect the context requirements of DMA
> unmap calls. These always complete without blocking, even if the

I once introduced a similar flag and called it MAY_SLEEP. I chose
MAY_SLEEP, because there is already a might_sleep() annotation, but I
don't have a strong opinion unless your semantics is supposed to be
different from might_sleep(). If it is, then I strongly prefer
MAY_BLOCK to prevent confusing the two.

> * The swiotlb throttling code in this patch set throttles by
> serializing the use of swiotlb memory when usage is above a designated

With CONFIG_SWIOTLB_DYNAMIC, this could happen automatically in the
future. But let's get the basic functionality first.

> * Except for knowing how much swiotlb memory is currently allocated,
> throttle accounting is done without locking or atomic operations. For

Agreed.

> * In a CoCo VM, mapping a scatter/gather list makes an independent
> swiotlb request for each entry. Throttling each independent request

Yes. It should be possible to control the thresholds through sysctl.

> 3. I have not changed the current heuristic for the swiotlb memory
> size in CoCo VMs. It's not clear to me how to link this to whether the

This sounds fine for now.

> 4. I need to update the swiotlb documentation to describe throttling.
> 

OK, I'm going try it out.

Thank you for making this happen!

Petr T

---

## [13] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 1/7] swiotlb: Introduce swiotlb throttling*

On Thu, 22 Aug 2024 11:37:12 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

Are these struct members needed if CONFIG_SWIOTLB_THROTTLE is not set?

>  	struct dentry *debugfs;
>  	bool force_bounce;

I think this should not be removed but changed to:
#if defined(CONFIG_DEBUG_FS) || defined(CONFIG_SWIOTLB_THROTTLE)

>  	atomic_long_t total_used;
>  	atomic_long_t used_hiwater;

And these two should be guarded by #ifdef CONFIG_SWIOTLB_THROTTLE.

>  };
>  


If I didn't know anything about the concept, this description would
confuse me... The short description should be something like: "Throttle
the use of DMA bounce buffers." Do not mention "enabled drivers" here;
it's sufficient to mention the limitations in the help text.

In addition, the help text should make it clear that this throttling
does not apply if bounce buffers are not needed; except for CoCo VMs,
this is the most common case. I mean, your description does mention CoCo
VMs, but e.g. distributions may wonder what the impact would be if they
enable this option and the kernel then runs on bare metal.

> +
> +	  If unsure, say N.

I'm not sure this flag is needed for each slot.

SWIOTLB mappings should be throttled when the total SWIOTLB usage is
above a threshold. Conversely, it can be unthrottled when the total
usage goes below a threshold, and it should not matter if that happens
due to an unmap of the exact buffer which previously pushed the usage
over the edge, or due to an unmap of any other unrelated buffer.

I had a few more comments to the rest of this patch, but they're moot
if this base logic gets redone.

Petr T

>  };
>

---

## [14] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 2/7] dma: Handle swiotlb throttling for SGLs*

On Thu, 22 Aug 2024 11:37:13 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

If we agree to change the unthrottling logic (see my comment to your
RFC 1/7), we'll need an additional attribute to delay unthrottling when
unmapping sg list entries 1 to N-1. This attribute could convey that
the mapping is the non-initial segment of an sg list and it could then
be also used to disable blocking in swiotlb_tbl_map_single().

> 
>  kernel/dma/direct.c | 35 ++++++++++++++++++++++++++++++-----

Nitpick: This parameter should probably be called "sg", because it is
never used to do any operation on the whole list. Similarly, the
function could be called dma_direct_unmap_sg_entry(), because there is
no dma_direct_unmap_sgl() either...

> +		unsigned long attrs)
> +

I wonder if nents can ever be zero here, but it's nowhere enforced and
dma_map_sg_attrs() is exported, so I agree, let's play it safe.

> +		dma_direct_unmap_sgl_entry(dev, sgl, dir, attrs);
>  }

Are you sure? I think the modified value of attrs is first used in the
next loop iteration, so the conditional should be removed, or else both
segment index 0 and 1 will keep the flag.

Petr T

> +			attrs &= ~DMA_ATTR_MAY_BLOCK;
> +

---

## [15] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 3/7] dma: Add function for drivers to know if allowing
 blocking is useful*

On Thu, 22 Aug 2024 11:37:14 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

LGTM.

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  include/linux/dma-mapping.h |  5 +++++

---

## [16] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 4/7] scsi_lib_dma: Add _attrs variant of scsi_dma_map()*

On Thu, 22 Aug 2024 11:37:15 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

LGTM.

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  drivers/scsi/scsi_lib_dma.c | 13 +++++++------

---

## [17] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 5/7] scsi: storvsc: Enable swiotlb throttling*

On Thu, 22 Aug 2024 11:37:16 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

LGTM, but I'm not familiar with this driver or the SCSI layer. In
particular, I don't know if it's OK to change the value of
host->queuecommand_may_block after scsi_host_alloc() initialized it
from a scsi host template, although it seems to be fine.

Petr T

> ---
>  drivers/scsi/storvsc_drv.c | 9 ++++++++-

---

## [18] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 6/7] nvme: Move BLK_MQ_F_BLOCKING indicator to struct
 nvme_ctrl*

On Thu, 22 Aug 2024 11:37:17 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

LGTM.

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  drivers/nvme/host/core.c | 4 ++--

---

## [19] Petr Tesařík — 2024-08-23
*Subject: Re: [RFC 7/7] nvme: Enable swiotlb throttling for NVMe PCI devices*

On Thu, 22 Aug 2024 11:37:18 -0700
mhkelley58@gmail.com wrote:

> From: Michael Kelley <mhklinux@outlook.com>
> 

LGTM.

Reviewed-by: Petr Tesarik <ptesarik@suse.com>

Petr T

> ---
>  drivers/nvme/host/pci.c | 18 ++++++++++++++----

---

## [20] Michael Kelley — 2024-08-23
*Subject: RE: [RFC 0/7] Introduce swiotlb throttling*

From: Petr Tesa��k <petr@tesarici.cz> Sent: Thursday, August 22, 2024 11:45 PM
> 
> Hi all,

My intent is that the semantics are the same as might_sleep(). I
vacillated between MAY_SLEEP and MAY_BLOCK. The kernel seems
to treat "sleep" and "block" as equivalent, because blk-mq has
the BLK_MQ_F_BLOCKING flag, and SCSI has the 
queuecommand_may_block flag that is translated to
BLK_MQ_F_BLOCKING. So I settled on MAY_BLOCK, but as you
point out, that's inconsistent with might_sleep(). Either way will
be inconsistent somewhere, and I don't have a preference.

> 
> > * The swiotlb throttling code in this patch set throttles by

Good point.  I was thinking about creating /sys/kernel/swiotlb, but
sysctl is better.

Michael

> 
> > 3. I have not changed the current heuristic for the swiotlb memory

---

## [21] Michael Kelley — 2024-08-23
*Subject: RE: [RFC 1/7] swiotlb: Introduce swiotlb throttling*

From: Petr Tesa��k <petr@tesarici.cz> Sent: Friday, August 23, 2024 12:41 AM
> 
> On Thu, 22 Aug 2024 11:37:12 -0700

They are not needed. But I specifically left them unguarded because
the #ifdef just clutters things here (and in the code as needed to make
things compile) without adding any real value. The amount of memory
saved is miniscule as there's rarely more than one instance of io_tbl_mem.

> 
> >  	struct dentry *debugfs;

Same thought here.

> 
> >  	atomic_long_t total_used;

And here.

> 
> >  };

OK. I'll work on the text per your comments.

> 
> > +

I think I understand what you are proposing. But I don't see a way
to make it work without adding global synchronization beyond
the current atomic counter for the number of used slabs. At a minimum
we would need a global spin lock instead of the atomic counter. The spin
lock would protect the (non-atomic) slab count along with some other
accounting, and that's more global references. As described in the
cover letter, I was trying to avoid doing that.

If you can see how to do what you propose with just the current
atomic counter, please describe.

Michael

> 
> I had a few more comments to the rest of this patch, but they're moot

---

## [22] Michael Kelley — 2024-08-23
*Subject: RE: [RFC 2/7] dma: Handle swiotlb throttling for SGLs*

From: Petr Tesa��k <petr@tesarici.cz> Sent: Friday, August 23, 2024 1:03 AM
> 
> On Thu, 22 Aug 2024 11:37:13 -0700

OK.  I agree.

> 
> > +		unsigned long attrs)

Yep -- my thinking exactly.

> 
> > +		dma_direct_unmap_sgl_entry(dev, sgl, dir, attrs);

I don't understand your comment. If it's present, the MAY_BLOCK flag
is used for the index 0 SGL entry, and then is cleared before the loop is
run again for the index 1 and subsequent SGL entries. But it would
still work with the conditional removed, and maybe the CPU overhead
of always clearing the flag is the same as doing the conditional.

Michael

> 
> Petr T

---

## [23] Michael Kelley — 2024-08-23
*Subject: RE: [RFC 5/7] scsi: storvsc: Enable swiotlb throttling*

From: Petr Tesa��k <petr@tesarici.cz> Sent: Friday, August 23, 2024 1:20 AM
> 
> On Thu, 22 Aug 2024 11:37:16 -0700

Yes, it's OK to change the value after scsi_host_alloc().
The flag isn't consumed until scsi_add_host() is called
later in storvsc_probe().

Note this maps to BLK_MQ_F_BLOCKING, which you can see in
/sys/kernel/debug/block/<device>/hctx0/flags. Same for NVMe
devices with my Patches 6 and 7. When debugging, I've been
checking that /sys entry to make sure the behavior is as expected. :-)

Michael

> 
> > ---

---

## [24] hch@lst.de — 2024-08-24
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Fri, Aug 23, 2024 at 02:20:41AM +0000, Michael Kelley wrote:
> Christoph Hellwig, or anyone else who knows the history and current
> reality better than I do, please jump in. :-)

It's not just interrupt context, but any context that does not allow
blocking.  There is plenty of that as seen by the moving of nvme
to specifically request a blocking context for I/O submission in this
path.

That being said there are probably more contexts that can block than
those that can't, so allowing for that option is a good thing.

---

## [25] Christoph Hellwig — 2024-08-24
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Thu, Aug 22, 2024 at 11:37:11AM -0700, mhkelley58@gmail.com wrote:
> Because it's not possible to detect at runtime whether a DMA map call
> is made in a context that can block, the calls in key device drivers

One thing I've been doing for a while but haven't gotten to due to
my lack of semantic patching skills is that we really want to split
the few flags useful for dma_map* from DMA_ATTR_* which largely
only applies to dma_alloc.

Only DMA_ATTR_WEAK_ORDERING (if we can't just kill it entirely)
and for now DMA_ATTR_NO_WARN is used for both.

DMA_ATTR_SKIP_CPU_SYNC and your new SLEEP/BLOCK attribute is only
useful for mapping, and the rest is for allocation only.

So I'd love to move to a DMA_MAP_* namespace for the mapping flags
before adding more on potentially widely used ones.

With a little grace period we can then also phase out DMA_ATTR_NO_WARN
for allocations, as the gfp_t can control that much better.

> In general, storage device drivers can take advantage of the MAY_BLOCK
> option, while network device drivers cannot. The Linux block layer

Note that this also in general involves changes to the block drivers
to set that flag, which is a bit annoying, but I guess there is not
easy way around it without paying the price for the BLK_MQ_F_BLOCKING
overhead everywhere.

---

## [26] Petr Tesařík — 2024-08-24
*Subject: Re: [RFC 2/7] dma: Handle swiotlb throttling for SGLs*

On Fri, 23 Aug 2024 20:42:08 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Petr Tesařík <petr@tesarici.cz> Sent: Friday, August 23, 2024 1:03 AM
> > 

Yes, this was my original thinking, but then I somehow got caught up in
it and went on to thinking that the condition was not only unnecessary,
but wrong. You're right, the code is perfectly fine as it is.

Sorry for the noise.

Petr T

---

## [27] Petr Tesařík — 2024-08-24
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Fri, 23 Aug 2024 20:40:16 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Petr Tesařík <petr@tesarici.cz> Sent: Thursday, August 22, 2024 11:45 PM
>[...]

Fair enough. Let's stay with MAY_BLOCK then, so you don't have to
change it everywhere.

>[...]
> > > Open Topics

That still leaves the question where it should go.

Under /proc/sys/kernel? Or should we make a /proc/sys/kernel/dma
subdirectory to make room for more dma-related controls?

Petr T

---

## [28] Michael Kelley — 2024-08-26
*Subject: RE: [RFC 0/7] Introduce swiotlb throttling*

From: Christoph Hellwig <hch@lst.de> Sent: Saturday, August 24, 2024 1:16 AM
> 
> On Thu, Aug 22, 2024 at 11:37:11AM -0700, mhkelley58@gmail.com wrote:

OK, this makes sense to me. The DMA_ATTR_* symbols are currently
defined as just values that are not part of an enum or any other higher
level abstraction, and the "attrs" parameter to the dma_* functions is
just "unsigned long". Are you thinking that the separate namespace is
based only on the symbolic name (i.e., DMA_MAP_* vs DMA_ATTR_*),
with the values being disjoint? That seems straightforward to me.
Changing the "attrs" parameter to an enum is a much bigger change ....

For a transition period we can have both DMA_ATTR_SKIP_CPU_SYNC
and DMA_MAP_SKIP_CPU_SYNC, and then work to change all
occurrences of the former to the latter.

I'll have to look more closely at WEAK_ORDERING and NO_WARN.

There are also a couple of places where DMA_ATTR_NO_KERNEL_MAPPING
is used for dma_map_* calls, but those are clearly bogus since that
attribute is never tested in the map path.

> 
> With a little grace period we can then also phase out DMA_ATTR_NO_WARN

Agreed. I assumed there was some cost to BLK_MQ_F_BLOCKING since
the default is !BLK_MQ_F_BLOCKING, but I don't really know what
that is. Do you have a short summary, just for my education?

Michael

---

## [29] Michael Kelley — 2024-08-26
*Subject: RE: [RFC 0/7] Introduce swiotlb throttling*

From: Petr Tesařík <petr@tesarici.cz> Sent: Saturday, August 24, 2024 1:06 PM
> 
> On Fri, 23 Aug 2024 20:40:16 +0000

I would be good with /proc/sys/kernel/swiotlb (or "dma"). There
are only two entries (high_throttle and low_throttle), but just
dumping everything directly in /proc/sys/kernel doesn't seem like
a good long-term approach.  Even though there are currently a lot
of direct entries in /proc/sys/kernel, that may be historical, and not
changeable due to backwards compatibility requirements.

Michael

Michael

---

## [30] Petr Tesařík — 2024-08-26
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Mon, 26 Aug 2024 16:24:53 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Petr Tesařík <petr@tesarici.cz> Sent: Saturday, August 24, 2024 1:06 PM
> > 

I think SWIOTLB is a bit too narrow. How many controls would we add
under /proc/sys/kernel/swiotlb? The chances seem higher if we call it
/proc/sys/kernel/dma/swiotlb_{low,high}_throttle, and it follows the
paths in source code (which are subject to change any time, however).
Anyway, I don't want to get into bikeshedding; I'm fine with whatever
you send in the end. :-)

BTW those entries directly under /proc/sys/kernel are not all
historical. The io_uring_* controls were added just last year, see
commit 76d3ccecfa18.

Petr T

---

## [31] Michael Kelley — 2024-08-27
*Subject: RE: [RFC 0/7] Introduce swiotlb throttling*

From: Petr Tesařík <petr@tesarici.cz> Sent: Monday, August 26, 2024 12:28 PM
> 
> On Mon, 26 Aug 2024 16:24:53 +0000

Note that there could be multiple instances of the throttle values, since
a DMA restricted pool has its own struct io_tlb_mem that is separate
from the default. I wrote the code so that throttling is independently
applied to a restricted pool as well, though I haven't tested it.

So the typical case is that we'll have high and low throttle values for the
default swiotlb pool, but we could also have high and low throttle
values for any restricted pools.

Maybe the /proc pathnames would need to be:

   /proc/sys/kernel/dma/swiotlb_default/high_throttle
   /proc/sys/kernel/dma/swiotlb_default/low_throttle
   /proc/sys/kernel/dma/swiotlb_<rpoolname>/high_throttle
   /proc/sys/kernel/dma/swiotlb_<rpoolname>/low_throttle

Or we could throw all the throttles directly into the "dma" directory,
though that makes for fairly long names in lieu of a deeper directory
structure:

   /proc/sys/kernel/dma/default_swiotlb_high_throttle
   /proc/sys/kernel/dma/default_swiotlb_low_throttle
   /proc/sys/kernel/dma/<rpoolname>_swiotlb_high_throttle
   /proc/sys/kernel/dma/<rpoolname_>swiotlb_low_throttle

Thoughts?

Michael

---

## [32] Christoph Hellwig — 2024-08-27
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Mon, Aug 26, 2024 at 03:27:30PM +0000, Michael Kelley wrote:
> OK, this makes sense to me. The DMA_ATTR_* symbols are currently
> defined as just values that are not part of an enum or any other higher

Yes. Although initially I'd just keep ATTR for the allocation and then
maybe do a scripted run to convert it.

> Changing the "attrs" parameter to an enum is a much bigger change ....

I don't think an enum makes much sense as we have bits defined.  A
__bitwise type would be nice, but not required.

> For a transition period we can have both DMA_ATTR_SKIP_CPU_SYNC
> and DMA_MAP_SKIP_CPU_SYNC, and then work to change all

Yeah, these kinds of bogus things is what I'd like to kill..


> > Note that this also in general involves changes to the block drivers
> > to set that flag, which is a bit annoying, but I guess there is not

I think the biggest issue is that synchronize_srcu is pretty damn
expensive, but there's also a whole bunch of places that unconditionally
defer to the workqueue.

---

## [33] Petr Tesařík — 2024-08-27
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Tue, 27 Aug 2024 00:26:36 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Petr Tesařík <petr@tesarici.cz> Sent: Monday, August 26, 2024 12:28 PM
> > 

Good point. I didn't think about it.

> So the typical case is that we'll have high and low throttle values for the
> default swiotlb pool, but we could also have high and low throttle

If a subdirectory is needed anyway, then we may ditch the dma
directory idea and place swiotlb subdirectories directly under
/proc/sys/kernel.

> Or we could throw all the throttles directly into the "dma" directory,
> though that makes for fairly long names in lieu of a deeper directory

I have already said I don't care much as long as the naming and/or
placement is not downright confusing. If the default values are
adjusted, they will end up in a config file under /etc/sysctl.d, and
admins will copy&paste it from Stack Exchange.

I mean, you're probably the most interested person on the planet, so
make a choice, and we'll adapt. ;-)

Petr T

---

## [34] Petr Tesařík — 2024-08-27
*Subject: Re: [RFC 1/7] swiotlb: Introduce swiotlb throttling*

On Fri, 23 Aug 2024 20:41:15 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Petr Tesařík <petr@tesarici.cz> Sent: Friday, August 23, 2024 12:41 AM
> > 

I have thought about this for a few days. And I'm still not convinced.
You have made it clear in multiple places that the threshold is a soft
limit, and there are many ways the SWIOTLB utilization may exceed the
threshold. In fact I'm not even 100% sure that an atomic counter is
needed, because the check is racy anyway. Another task may increase
(or decrease) the counter between atomic_long_read(&mem->total_used)
and a subsequent down(&mem->throttle_sem).

I consider it a feature, not a flaw, because the real important checks
happen later while searching for free slots, and those are protected
with a spinlock.

> If you can see how to do what you propose with just the current
> atomic counter, please describe.

I think I'm certainly missing something obvious, but let me open the
discussion to improve my understanding of the matter.

Suppose we don't protect the slab count with anything. What is the
worst possible outcome? IIUC the worst scenario is that multiple tasks
unmap swiotlb buffers simultaneously and all of them believe that their
action made the total usage go below the low threshold, so all of them
try to release the semaphore.

That's obviously not good, but AFAICS all that's needed is a
test_and_clear_bit() on a per-io_tlb_mem throttled flag just before
calling up(). Since up() would acquire the semaphore's spinlock, and
there's only one semaphore per io_tlb_mem, adding an atomic flag doesn't
look like too much overhead to me, especially if it ends up in the same
cache line as the semaphore.

Besides, this all happens only in the slow path, i.e. only after the
current utilization has just dropped below the low threshold, not if
the utilization was already below the threshold before freeing up some
slots.

I have briefly considered subtracting the low threshold as initial bias
from mem->total_used and using atomic_long_add_negative() to avoid the
need for an extra throttled flag, but at this point I'm not sure it can
be implemented without any races. We can try to figure out the details
if it sounds like a good idea.

Petr T

---

## [35] Michael Kelley — 2024-08-27
*Subject: RE: [RFC 1/7] swiotlb: Introduce swiotlb throttling*

From: Petr Tesařík <petr@tesarici.cz> Sent: Tuesday, August 27, 2024 8:56 AM
> 
> On Fri, 23 Aug 2024 20:41:15 +0000

Atomic operations are expensive at the memory bus level, particularly
in high CPU count systems with NUMA topologies. However,
maintaining an imprecise global count doesn't work because the
divergence from reality can become unbounded over time. The
alternative is to sum up all the per-area counters each time a
reasonably good global value is needed, and that can be expensive itself
with high area counts. A hybrid might be to maintain an imprecise global
count, but periodically update it by summing up all the per-area counters
so that the divergence from reality isn't unbounded.

> Another task may increase
> (or decrease) the counter between atomic_long_read(&mem->total_used)

Yes, the semaphore management is the problem. Presumably we want
each throttled request to wait on the semaphore, forming an ordered
queue of waiters. Each up() on the semaphore releases one of those
waiters. We don’t want to release all the waiters when the slab count
transitions from "above throttle" to "below throttle" because that
creates a thundering herd problem.

So consider this example scenario:
1) Two waiters ("A" and "B") are queued the semaphore, each wanting 2 slabs.
2) An unrelated swiotlb unmap frees 10 slabs, taking the slab count
from 2 above threshold to 8 below threshold. This does up() on
the semaphore and awakens "A".
3) "A" does his request for 2 slabs, and the slab count is now 6 below
threshold.
4) "A" does swiotlb unmap.  The slab count goes from 6 below threshold back
to 8 below threshold, so no semaphore operation is done. "B" is still waiting.
5) System-wide, swiotlb requests decline, and the slab count never goes above
the threshold again. At this point, "B" is still waiting and never gets awakened.

An ordered queue of waiters is incompatible with wakeups determined solely
on whether the slab count is below the threshold after swiotlb unmap. You
would have to wait up all waiters and let them re-contend for the slots that
are available below the threshold, with most probably losing out and going
back on the semaphore wait queue (i.e., a thundering herd).

Separately, what does a swiotlb unmap do if it takes the slab count from above
threshold to below threshold, and there are no waiters? It should not do up()
in that case, but how can it make that decision in a way that doesn't race
with a swiotlb map operation running at the same time?

Michael

> 
> Besides, this all happens only in the slow path, i.e. only after the

---

## [36] Petr Tesařík — 2024-08-28
*Subject: Re: [RFC 1/7] swiotlb: Introduce swiotlb throttling*

On Tue, 27 Aug 2024 17:30:59 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Petr Tesařík <petr@tesarici.cz> Sent: Tuesday, August 27, 2024 8:56 AM
> > 

Sure, the CPU must ensure exclusive access to the underlying memory and
cache coherency across all CPUs. I know how these things work...

> maintaining an imprecise global count doesn't work because the
> divergence from reality can become unbounded over time. The

Yes, this is what I had in mind, but I'm not sure which option is
worse. Let me run a micro-benchmark on a 192-core AmpereOne system.

> > Another task may increase
> > (or decrease) the counter between atomic_long_read(&mem->total_used)

Ah, right, the semaphore must be released as many times as it is
acquired. Thank you for your patience.

> Separately, what does a swiotlb unmap do if it takes the slab count from above
> threshold to below threshold, and there are no waiters? It should not do up()

Hm, this confirms my gut feeling that the atomic counter alone would
not be sufficient.

I think I can follow your reasoning now:

1. Kernels which enable CONFIG_SWIOTLB_THROTTLE are likely to have
   CONFIG_DEBUG_FS as well, so the price for an atomic operation on
   total_used is already paid.
2. There are no pre-existing per-io_tlb_mem ordering constraints on
   unmap, except the used counter, which is insufficient.
3. Slot data is already protected by its area spinlock, so adding
   something there does not increase the price.

I don't have an immediate idea, but I still believe we can do better.
For one thing, your scheme is susceptible to excessive throttling in
degenerate cases, e.g.:

1. A spike in network traffic temporarily increases swiotlb usage above
   the threshold, but it is not throttled because the network driver
   does not use SWIOTLB_ATTR_MAY_BLOCK.
2. A slow disk "Snail" maps a buffer and acquires the semaphore.
3. A fast disk "Cheetah" tries to map a buffer and goes on the
   semaphore wait queue.
4. Network buffers are unmapped, dropping usage below the threshold,
   but since the throttle flag was not set, the semaphore is not
   touched.
5. "Cheetah" is unnecessarily waiting for "Snail" to finish.

You may have never hit this scenario in your testing, because you
presumably had only fast virtual block devices.

I'm currently thinking along the lines of waking up the semaphore
on unmap whenever current usage is above the threshold and there is a
waiter.

As a side note, I get your concerns about the thundering herd effect,
but keep in mind that bounce buffers are not necessarily equal. If four
devices are blocked on mapping a single slot, you can actually wake up
all of them after you release four slots. For SG lists, you even add
explicit logic to trigger the wakeup only on the last segment...

BTW as we talk about the semaphore queue, it reminds me of an issue I
had with your proposed patch:

> @@ -1398,6 +1431,32 @@ phys_addr_t swiotlb_tbl_map_single(struct device *dev, phys_addr_t orig_addr,
>  	dev_WARN_ONCE(dev, alloc_align_mask > ~PAGE_MASK,
                                              ^^^^^^^^^^^^^^^^^^

Is it safe to access the semaphore count like this without taking the
semaphore spinlock? If it is, then it deserves a comment to explain why
you can ignore this comment in include/linux/semaphore.h:

/* Please don't access any members of this structure directly */

Petr T

> +			throttle = true;
> +			mem->low_throttle_count++;

---

## [37] Michael Kelley — 2024-08-28
*Subject: RE: [RFC 1/7] swiotlb: Introduce swiotlb throttling*

From: Petr Tesařík <petr@tesarici.cz> Sent: Tuesday, August 27, 2024 10:16 PM
> 
> On Tue, 27 Aug 2024 17:30:59 +0000

I'm unsure if that is true. But my thinking that the atomic total_used is
needed by throttling may have been faulty.  Certainly, if CONFIG_DEBUG_FS
is set, then the cost is already paid. But if not, CONFIG_SWIOTLB_THROTTLE
in my current code adds the atomic total_used cost for *all* swiotlb map
and unmap requests. But the cost of a computed-on-the-fly value (by
summing across all areas) would be paid only by MAY_BLOCK map
requests (and not on unmap), so that decreases the overall cost. And I
had not thought of the hybrid approach until I wrote my previous
response to you. Both seem worth further thinking/investigation.

> 2. There are no pre-existing per-io_tlb_mem ordering constraints on
>    unmap, except the used counter, which is insufficient.

Agreed.

> 3. Slot data is already protected by its area spinlock, so adding
>    something there does not increase the price.

Agreed.

> 
> I don't have an immediate idea, but I still believe we can do better.

My approach was to explicitly not worry about this scenario. :-)  I
stated in the patch set cover letter that throttled requests are
serialized (though maybe not clearly enough). And if a workload
regularly runs above the threshold, the size of the swiotlb memory
should probably be increased. I'm open to an approach that does
better than serialization of throttled requests if it doesn't get
too complicated, but I think it's of secondary importance.

> 
> I'm currently thinking along the lines of waking up the semaphore

Agreed. But the accounting to do that correctly probably requires
a spin lock, and I didn't want to go there.

> For SG lists, you even add
> explicit logic to trigger the wakeup only on the last segment...

Yes. I'm my thinking, that's just part of the serialization of throttled
requests. Throttled request "A", which used an SGL, shouldn't release
the semaphore and hand off ownership to request "B" until all
the swiotlb memory allocated by "A"s SGL has been released.

> 
> BTW as we talk about the semaphore queue, it reminds me of an issue I

Yes, this is a bit of a hack for the RFC patch set. The semaphore code
doesn't offer an API to find out if a semaphore is held. In my mind, the
right solution is to add a semaphore API to get the current "count"
of the semaphore (or maybe just a boolean indicating if it is held),
and then use that API. I would add the API as this patch set goes
from RFC to PATCH status. (Mutex's have such an API.)

The API would provide only an instantaneous value, and in the absence
of any higher-level synchronization, the value could change immediately
after it is read. But that's OK in the swiotlb throttling use case because
the throttling tolerates "errors" due to such a change. The
implementation of the API doesn't need to obtain the semaphore spin
lock as long as the read of the count field is atomic (i.e., doesn't tear),
which it should be.

Michael

> 
> > +			throttle = true;

---

## [38] Robin Murphy — 2024-08-28
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On 2024-08-22 7:37 pm, mhkelley58@gmail.com wrote:
> From: Michael Kelley <mhklinux@outlook.com>
> 

Isn't that fundamentally the same thing that SWIOTLB_DYNAMIC was already 
meant to address? Of course the implementation of that is still young 
and has plenty of scope to be made more effective, and some of the ideas 
here could very much help with that, but I'm struggling a little to see 
what's really beneficial about having a completely disjoint mechanism 
for sitting around doing nothing in the precise circumstances where it 
would seem most possible to allocate a transient buffer and get on with it.

Thanks,
Robin.

> To reach this goal, this patch set introduces the concept of swiotlb
> throttling, which can delay swiotlb allocation requests when swiotlb

---

## [39] Petr Tesařík — 2024-08-28
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Wed, 28 Aug 2024 13:02:31 +0100
Robin Murphy <robin.murphy@arm.com> wrote:

> On 2024-08-22 7:37 pm, mhkelley58@gmail.com wrote:
> > From: Michael Kelley <mhklinux@outlook.com>

This question can be probably best answered by Michael, but let me give
my understanding of the differences. First the similarity: Yes, one
of the key new concepts is that swiotlb allocation may block, and I
introduced a similar attribute in one of my dynamic SWIOTLB patches; it
was later dropped, but dynamic SWIOTLB would still benefit from it.

More importantly, dynamic SWIOTLB may deplete memory following an I/O
spike. I do have some ideas how memory could be returned back to the
allocator, but the code is not ready (unlike this patch series).
Moreover, it may still be a better idea to throttle the devices
instead, because returning DMA'able memory is not always cheap. In a
CoCo VM, this memory must be re-encrypted, and that requires a
hypercall that I'm told is expensive.

In short, IIUC it is faster in a CoCo VM to delay some requests a bit
than to grow the swiotlb.

Michael, please add your insights.

Petr T

> > To reach this goal, this patch set introduces the concept of swiotlb
> > throttling, which can delay swiotlb allocation requests when swiotlb

---

## [40] Michael Kelley — 2024-08-28
*Subject: RE: [RFC 0/7] Introduce swiotlb throttling*

From: Petr Tesa��k <petr@tesarici.cz> Sent: Wednesday, August 28, 2024 6:04 AM
> 
> On Wed, 28 Aug 2024 13:02:31 +0100

The other limitation of SWIOTLB_DYNAMIC is that growing swiotlb
memory requires large chunks of physically contiguous memory,
which may be impossible to get after a system has been running a
while. With a major rework of swiotlb memory allocation code, it might
be possible to get by with a piecewise assembly of smaller contiguous
memory chunks, but getting many smaller chunks could also be
challenging.

Growing swiotlb memory also must be done as a background async
operation if the DMA map operation can't block. So transient buffers
are needed, which must be encrypted and decrypted on every round
trip in a CoCo VM. The transient buffer memory comes from the
atomic pool, which typically isn't that large and could itself become
exhausted. So we're somewhat playing whack-a-mole on the memory
allocation problem.

We discussed the limitations of SWIOTLB_DYNAMIC in large CoCo VMs
at the time SWIOTLB_DYNAMIC was being developed, and I think there
was general agreement that throttling would be better for the CoCo
VM scenario.

Broadly, throttling DMA map requests seems like a fundamentally more
robust approach than growing swiotlb memory. And starting down
the path of allowing designated DMA map requests to block might have
broader benefits as well, perhaps on the IOMMU path.

These points are all arguable, and your point about having two somewhat
overlapping mechanisms is valid. Between the two, my personal viewpoint
is that throttling is the better approach, but I'm probably biased by my
background in the CoCo VM world. Petr and others may see the tradeoffs
differently.

Michael

---

## [41] Petr Tesařík — 2024-08-28
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On Wed, 28 Aug 2024 16:30:04 +0000
Michael Kelley <mhklinux@outlook.com> wrote:

> From: Petr Tesařík <petr@tesarici.cz> Sent: Wednesday, August 28, 2024 6:04 AM
> > 

Note that this situation can be somewhat improved with the
SWIOTLB_ATTR_MAY_BLOCK flag, because a new SWIOTLB chunk can then be
allocated immediately, removing the need to allocate a transient pool
from the atomic pool.

> We discussed the limitations of SWIOTLB_DYNAMIC in large CoCo VMs
> at the time SWIOTLB_DYNAMIC was being developed, and I think there

For CoCo VMs, throttling indeed seems to be better. Embedded devices
seem to benefit more from growing the swiotlb on demand.

As usual, YMMV.

Petr T

---

## [42] Robin Murphy — 2024-08-28
*Subject: Re: [RFC 0/7] Introduce swiotlb throttling*

On 2024-08-28 2:03 pm, Petr Tesařík wrote:
> On Wed, 28 Aug 2024 13:02:31 +0100
> Robin Murphy <robin.murphy@arm.com> wrote:

Sure, making a hypercall in order to progress is expensive relative to 
being able to progress without doing that, but waiting on a lock for an 
unbounded time in the hope that other drivers might release their DMA 
mappings soon represents a potentially unbounded expense, since it 
doesn't even carry any promise of progress at all - oops userspace just 
filled up SWIOTLB with a misguided dma-buf import and now the OS has 
livelocked on stalled I/O threads fighting to retry :(

As soon as we start tracking thresholds etc. then that should equally 
put us in the position to be able to manage the lifecycle of both 
dynamic and transient pools more effectively - larger allocations which 
can be reused by multiple mappings until the I/O load drops again could 
amortise that initial cost quite a bit.

Furthermore I'm not entirely convinced that the rationale for throttling 
being beneficial is even all that sound. Serialising requests doesn't 
make them somehow use less memory, it just makes them use it... 
serially. If a single CPU is capable of queueing enough requests at once 
to fill the SWIOTLB, this is going to do absolutely nothing; if two CPUs 
are capable of queueing enough requests together to fill the SWIOTLB, 
making them take slightly longer to do so doesn't inherently mean 
anything more than reaching the same outcome more slowly. At worst, if a 
thread is blocked from polling for completion and releasing a bunch of 
mappings of already-finished descriptors because it's stuck on an unfair 
lock trying to get one last one submitted, then throttling has actively 
harmed the situation.

AFAICS this is dependent on rather particular assumptions of driver 
behaviour in terms of DMA mapping patterns and interrupts, plus the 
overall I/O workload shape, and it's not clear to me how well that 
really generalises.

> In short, IIUC it is faster in a CoCo VM to delay some requests a bit
> than to grow the swiotlb.

I'm not necessarily disputing that for the cases where the assumptions 
do hold, it's still more a question of why those two things should be 
separate and largely incompatible (I've only skimmed the patches here, 
but my impression is that it doesn't look like they'd play all that 
nicely together if both enabled). To me it would make far more sense for 
this to be a tuneable policy of a more holistic SWIOTLB_DYNAMIC itself, 
i.e. blockable calls can opportunistically wait for free space up to a 
well-defined timeout, but then also fall back to synchronously 
allocating a new pool in order to assure a definite outcome of success 
or system-is-dying-level failure.

Thanks,
Robin.

---

## [43] Michael Kelley — 2024-08-30
*Subject: RE: [RFC 0/7] Introduce swiotlb throttling*

From: Robin Murphy <robin.murphy@arm.com> Sent: Wednesday, August 28, 2024 12:50 PM
> 
> On 2024-08-28 2:03 pm, Petr Tesa��k wrote:

FWIW, the implementation in this patch set guarantees forward
progress for throttled requests as long as drivers that use MAY_BLOCK
are well-behaved.

> - oops userspace just
> filled up SWIOTLB with a misguided dma-buf import and now the OS has

I'm not understanding what you envision here. Could you elaborate?
With the current implementation of SWIOTLB_DYNAMIC, dynamic
pools are already allocated with size MAX_PAGE_ORDER (or smaller
if that size isn't available). That size really isn't big enough in CoCo
VMs with more than 16 vCPUs since we want to split the allocation
into per-CPU areas. To fix this, we would need to support swiotlb
pools that are stitched together from multiple contiguous physical
memory ranges. That probably could be done, but I don't see how
it's related to thresholds.

> 
> Furthermore I'm not entirely convinced that the rationale for throttling

I don't get your point. My intent with throttling is that it caps the
system-wide high-water mark for swiotlb memory usage, without
causing I/O errors due to DMA map failures. Without
SWIOTLB_DYNAMIC, the original boot-time allocation size is the limit
for swiotlb memory usage, and DMA map fails if the system-wide
high-water mark tries to rise above that limit. With SWIOTLB_DYNAMIC,
the current code continues to allocate additional system memory and
turn it into swiotlb memory, with no limit. There probably *should*
be a limit, even for SWIOTLB_DYNAMIC.
 
I've run "fio" loads with and without throttling as implemented in this
patch set. Without SWIOTLB_DYNAMIC and no throttling, it's pretty
easy to reach the limit and get I/O errors due to DMA map failure. With
throttling and the same "fio" load, the usage high-water mark stays
near the throttling threshold, with no I/O errors. The limit should be
set large enough for a workload to operate below the throttling
threshold. But if the threshold is exceeded, throttling should avoid a
big failure due to DMA map failures.

My mental model here is somewhat like blk-mq tags. There's a fixed
number allocated with the storage controller. Block I/O requests must
get a tag, and if one isn't available, the requesting thread is pended
until one becomes available. The fixed number of tags is the limit, but
the requestor doesn't get an error if a tag isn't available -- it just
waits. The fixed number of tags necessarily imposes a kind of
resource limit on block I/O requests, rather than just always allocating
an additional tag if there's a request that can't get an existing tag. I think
the same model makes sense for swiotlb memory when the device
driver can support it.

> At worst, if a
> thread is blocked from polling for completion and releasing a bunch of

OK, yes, I can understand there might be an issue with a driver (like
NVMe) that supports polling. I'll look at that more closely and see
if there is.

> 
> AFAICS this is dependent on rather particular assumptions of driver

As I've mulled over your comments the past day, I'm not sure the two
things really are incompatible or even overlapping. To me it seems like
SWIOTLB_DYNAMIC is about whether the swiotlb memory is pre-allocated
at boot time, or allocated as needed. But SWIOTLB_DYNAMIC currently
doesn't have a limit to how much it will allocate, and it probably should.
(Though SWIOTLB_DYNAMIC has a limit imposed upon it if there's isn't
enough contiguous physical memory to grow the swiotlb pool.) Given a
limit, both the pre-allocate case and allocate-as-needed case have the
same question about what to do when the limit is reached. In both cases,
we're generally forced to set the limit pretty high, because DMA map
failures occur if you broach the limit. Throttling is about dealing with
the limit in a better way when permitted by the driver. That in turn
allows setting a tighter limit and not having to overprovision the
swiotlb memory.

> To me it would make far more sense for
> this to be a tuneable policy of a more holistic SWIOTLB_DYNAMIC itself,

Yes, I can see value in the kind of interaction you describe before any
limits are approached. But to me the primary question is dealing better
with the limit.

Michael 

> 
> Thanks,

---
