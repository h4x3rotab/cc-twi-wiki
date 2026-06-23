---
title: '[RFC PATCH 0/6] Support virtio-mem memory hotplug in TDX guests'
date: 2026-06-04
last_reply: 2026-06-15
message_count: 9
participants: ['Zhenzhong Duan', 'Kiryl Shutsemau']
---

## [1] Zhenzhong Duan — 2026-06-04

This RFC series explores the start-private memory approach for virtio-mem
CoCo support using TDG.MEM.PAGE.RELEASE. We are seeking feedback from
Kiryl on the CoCo guest implementation, MM experts on the callback
infrastructure and virtio-mem integration, and broader virtio/CoCo
community input on the overall approach. We are not seeking x86 maintainer
review at this stage.

== Background ==

In Confidential Computing (CoCo) guests like TDX, memory hotplug
operations face unique challenges:

1. Newly added memory must be explicitly "accepted" by the guest using
TDG.MEM.PAGE.ACCEPT TDCALL before it can be safely accessed. Accessing
unaccepted memory triggers VM exits and guest crashes.
2. Hypervisor may perform no-op unplug operations, leaving old memory in
place. Re-accepting this already-accepted memory during re-plug operations
returns errors.
3. State management become much more complex, "accepted"/"unccepted" plus
"plugged"/"unplugged".
4. Initial virtio-mem memory may be start-private or start-shared.

A previous series [1][2] supports start-private memory and utilized memory
hotplug notifiers to call tdx_accept_memory() before pages are freed to
the buddy allocator. However, this approach has limitations:

1. virtio-mem operates memory at subblock granularity (e.g., 2MB chunks
within 128MB memory blocks), while generic memory notifiers operate on entire
memory blocks, causing acceptance of unplugged subblocks with no backing
memory.
2. Re-accepting already-accepted memory returns errors. Ignoring these errors
can mislead the guest into believing re-accepted memory is zeroed when it
contains stale data.

Currently, virtio-mem spec doesn't define what kind of hotplugged memory
should be supported for CoCo guest, shared or private or both. There is a
newer series [3][4] supporting start-shared memory in discuss. It converts
shared->private before online (via set_memory_encrypted-> MapGPA + ACCEPT),
and back to shared on unplug (via set_memory_decrypted).

== About this series ==

This series takes a different direction, supporting start-private memory
and addressing the limitations of previous series [1] by implementing a
callback-based infrastructure that integrates TDX memory acceptance and
release operations with proper subblock granularity. See Rick and Paolo's
discussion about using TDG.MEM.PAGE.RELEASE in [1].

The goal is not to compete with existing efforts, but rather to kick off
discussion and seek for suggestions from mm expert whether utilizing
callback-based infrastructure and PAGE.RELEASE API is a viable scheme.

We chose the generic post-plug and pre-unplug callback approach because
it provides a simple proof-of-concept that can support kexec/kdump
scenarios, though it does not support lazy acceptance. We rely on
community discussion to identify better, more upstreamable solutions if
the start-private direction is ultimately adopted.

== More details ==

**Post-plug callbacks** are registered by TDX guests during early boot and
triggered by virtio-mem after successfully requesting memory from the
hypervisor. The callback invokes tdx_accept_memory(), which performs
TDG.MEM.PAGE.ACCEPT TDCALL on the exact memory range that was plugged,
providing subblock-aware granularity. Note that tdx_accept_memory() may
not be fully self-consistent in all environments, as some pages may
remain in an "accepted" state while others do not, since page release is
not supported across all TDX module versions.

**Pre-unplug callbacks** are registered during early boot and invoked by
virtio-mem before requesting memory removal from the hypervisor. The
callback executes tdx_release_memory(), which performs
TDG.MEM.PAGE.RELEASE TDCALL with an optimization strategy that attempts
1GB/2MB page releases first before falling back to 4KB pages for maximum
efficiency. Unlike acceptance operations, tdx_release_memory() maintains
full self-consistency since page acceptance is universally supported
across TDX implementations.

**Error handling strategy** prioritizes system stability by marking the
virtio-mem device as broken whenever TDX operations fail:

1. Post-plug failures: If memory acceptance fails after successful
hypervisor allocation, the device is marked as broken to prevent memory
corruption. The hypervisor-side memory is leaked for the device lifetime.
2. Pre-unplug failures: If TDX memory release fails, the device is marked as
broken and no hypervisor unplug is attempted.
3. Hypervisor unplug failures: If the hypervisor unplug fails after
successful TDX release, the system attempts to re-accept the memory for
consistency. If re-acceptance fails, the device is marked as broken.

This approach avoids complex recovery mechanisms that could fail and
cause state corruption, choosing instead to fail safely by disabling the
device when TDX operations cannot maintain consistent state between guest
and hypervisor.

**PAGE.RELEASE configuration** requires explicit enablement by the
hypervisor during TD creation. The hypervisor must set the
CONFIG_FLAGS.PAGE_RELEASE flag in the TD's configuration to enable
TDG.MEM.PAGE.RELEASE functionality within the guest. Without this
configuration, guests cannot perform memory release operations and must
rely on the hypervisor to handle private memory release. This series
focuses on guest-side changes and does not include hypervisor
modifications, which can be added in future versions if needed.

== Testing ==
Tested with qemu [2] which supports start-private memory:
Basic memory hotplug/unplug test.
Basic kexec/kdump functions test with zero/half/full memory plugged.

Interestingly, it also pass with qemu [4] which supports start-shared memory,
because acceptance triggers memory convert implicitly, but it's slow as
implicit conversion is 4K page granularity.

== Future work ==
support lazy accept

Thanks
Zhenzhong

[1] kernel: https://lore.kernel.org/kvm/20260324-tdx-hotplug-fixes-v1-0-8f29f2c17278@redhat.com/
[2] qemu: https://lore.kernel.org/qemu-devel/20260226140001.3622334-1-marcandre.lureau@redhat.com/
[3] kernel: https://lore.kernel.org/lkml/20260401-coco-v1-1-b9c3072e2d9c@redhat.com/
[4] qemu: https://lore.kernel.org/qemu-devel/20260504-rdm5-v4-0-bdf61e57c1e1@redhat.com/


Zhenzhong Duan (6):
  mm/memory_hotplug: Add memory post-plug callback infrastructure
  mm/memory_hotplug: Add memory pre-unplug callback infrastructure
  virtio-mem: Integrate memory acceptance and release callbacks
  x86/tdx: Register memory post-plug callback for TDX guests
  x86/tdx: Register memory pre-unplug callback for TDX guests
  x86/tdx: Release private memory before private->shared conversion

 arch/x86/include/asm/shared/tdx.h |   2 +
 include/linux/memory_hotplug.h    |  21 ++++
 arch/x86/coco/tdx/tdx.c           | 174 ++++++++++++++++++++++++++++++
 drivers/virtio/virtio_mem.c       |  80 ++++++++++++--
 mm/memory_hotplug.c               |  40 +++++++
 5 files changed, 307 insertions(+), 10 deletions(-)

---

## [2] Zhenzhong Duan — 2026-06-04
*Subject: [RFC PATCH 1/6] mm/memory_hotplug: Add memory post-plug callback infrastructure*

In confidential computing environments like TDX, newly added memory must be
explicitly "accepted" by the guest before it can be safely accessed. When
virtio-mem or other memory hotplug drivers add memory to a TDX guest, the
memory pages are initially in an "unaccepted" state. Accessing unaccepted
memory triggers VM exits and can cause guest crashes. The guest must call
TDX hypercalls to accept each page before use.

This callback infrastructure allows the TDX guest code to register a
handler that will be invoked after memory is plugged, ensuring all newly
added memory is properly accepted before being made available to the
kernel's memory management subsystem.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 include/linux/memory_hotplug.h | 11 +++++++++++
 mm/memory_hotplug.c            | 20 ++++++++++++++++++++
 2 files changed, 31 insertions(+)

diff --git a/include/linux/memory_hotplug.h b/include/linux/memory_hotplug.h
index 815e908c4135..39f0a35a5112 100644
--- a/include/linux/memory_hotplug.h
+++ b/include/linux/memory_hotplug.h
@@ -28,6 +28,8 @@ enum mmop {
 	MMOP_ONLINE_MOVABLE,
 };
 
+typedef int (*memory_post_plug_callback_t)(u64 addr, u64 size);
+
 #ifdef CONFIG_MEMORY_HOTPLUG
 struct page *pfn_to_online_page(unsigned long pfn);
 
@@ -176,6 +178,9 @@ static inline void pgdat_kswapd_lock_init(pg_data_t *pgdat)
 	mutex_init(&pgdat->kswapd_lock);
 }
 
+void set_memory_post_plug_callback(memory_post_plug_callback_t callback);
+int memory_post_plug_call(u64 addr, u64 size);
+
 #else /* ! CONFIG_MEMORY_HOTPLUG */
 #define pfn_to_online_page(pfn)			\
 ({						\
@@ -221,6 +226,12 @@ static inline bool mhp_supports_memmap_on_memory(void)
 static inline void pgdat_kswapd_lock(pg_data_t *pgdat) {}
 static inline void pgdat_kswapd_unlock(pg_data_t *pgdat) {}
 static inline void pgdat_kswapd_lock_init(pg_data_t *pgdat) {}
+
+static inline void set_memory_post_plug_callback(memory_post_plug_callback_t callback) {}
+static inline int memory_post_plug_call(u64 addr, u64 size)
+{
+	return 0;
+}
 #endif /* ! CONFIG_MEMORY_HOTPLUG */
 
 /*
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index 40c7915dabe0..73054ed016fd 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -1729,6 +1729,26 @@ bool mhp_range_allowed(u64 start, u64 size, bool need_mapping)
 	return false;
 }
 
+static memory_post_plug_callback_t memory_post_plug_callback __ro_after_init;
+
+void set_memory_post_plug_callback(memory_post_plug_callback_t callback)
+{
+	/* Fatal error to set callback twice in boot stage */
+	if (memory_post_plug_callback)
+		panic("memory_post_plug_callback is already registered\n");
+
+	memory_post_plug_callback = callback;
+}
+
+int memory_post_plug_call(u64 addr, u64 size)
+{
+	if (!memory_post_plug_callback)
+		return 0;
+
+	return (*memory_post_plug_callback)(addr, size);
+}
+EXPORT_SYMBOL_GPL(memory_post_plug_call);
+
 #ifdef CONFIG_MEMORY_HOTREMOVE
 /*
  * Scan pfn range [start,end) to find movable/migratable pages (LRU and

---

## [3] Zhenzhong Duan — 2026-06-04
*Subject: [RFC PATCH 2/6] mm/memory_hotplug: Add memory pre-unplug callback infrastructure*

In confidential computing environments like TDX, memory that was
previously accepted by the guest could be explicitly "released" back to
the hypervisor before it is unplugged, because hypervisor can do no-op
for the unplug operation without guest awares, then replug will fail
with re-accept error.

This callback infrastructure allows the TDX guest code to register a
handler that will be invoked after kernel removes memory from its memory
management subsystem but before it is unplugged, ensuring all memory
pages are properly released via TDG.MEM.PAGE.RELEASE TDCALL. Then re-plug
triggers TDG.MEM.PAGE.ACCEPT on pages in "unaccepted" state and succeed.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 include/linux/memory_hotplug.h | 10 ++++++++++
 mm/memory_hotplug.c            | 20 ++++++++++++++++++++
 2 files changed, 30 insertions(+)

diff --git a/include/linux/memory_hotplug.h b/include/linux/memory_hotplug.h
index 39f0a35a5112..5bb77670b6cf 100644
--- a/include/linux/memory_hotplug.h
+++ b/include/linux/memory_hotplug.h
@@ -29,6 +29,7 @@ enum mmop {
 };
 
 typedef int (*memory_post_plug_callback_t)(u64 addr, u64 size);
+typedef int (*memory_pre_unplug_callback_t)(u64 addr, u64 size);
 
 #ifdef CONFIG_MEMORY_HOTPLUG
 struct page *pfn_to_online_page(unsigned long pfn);
@@ -278,6 +279,9 @@ extern int remove_memory(u64 start, u64 size);
 extern void __remove_memory(u64 start, u64 size);
 extern int offline_and_remove_memory(u64 start, u64 size);
 
+void set_memory_pre_unplug_callback(memory_pre_unplug_callback_t callback);
+int memory_pre_unplug_call(u64 addr, u64 size);
+
 #else
 static inline void try_offline_node(int nid) {}
 
@@ -293,6 +297,12 @@ static inline int remove_memory(u64 start, u64 size)
 }
 
 static inline void __remove_memory(u64 start, u64 size) {}
+
+static inline void set_memory_pre_unplug_callback(memory_pre_unplug_callback_t callback) {}
+static inline int memory_pre_unplug_call(u64 addr, u64 size)
+{
+	return 0;
+}
 #endif /* CONFIG_MEMORY_HOTREMOVE */
 
 #ifdef CONFIG_MEMORY_HOTPLUG
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index 73054ed016fd..fcb6f85c40d0 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -2451,4 +2451,24 @@ int offline_and_remove_memory(u64 start, u64 size)
 	return rc;
 }
 EXPORT_SYMBOL_GPL(offline_and_remove_memory);
+
+static memory_pre_unplug_callback_t memory_pre_unplug_callback __ro_after_init;
+
+void set_memory_pre_unplug_callback(memory_pre_unplug_callback_t callback)
+{
+	/* Fatal error to set callback twice in boot stage */
+	if (memory_pre_unplug_callback)
+		panic("memory_pre_unplug_callback is already registered\n");
+
+	memory_pre_unplug_callback = callback;
+}
+
+int memory_pre_unplug_call(u64 addr, u64 size)
+{
+	if (!memory_pre_unplug_callback)
+		return 0;
+
+	return (*memory_pre_unplug_callback)(addr, size);
+}
+EXPORT_SYMBOL_GPL(memory_pre_unplug_call);
 #endif /* CONFIG_MEMORY_HOTREMOVE */

---

## [4] Zhenzhong Duan — 2026-06-04
*Subject: [RFC PATCH 3/6] virtio-mem: Integrate memory acceptance and release callbacks*

Integrate the memory post-plug and pre-unplug callbacks into virtio-mem's
plug and unplug operations to support TDX memory acceptance and release.

For memory plugging, call the post-plug callback after successfully
requesting memory from the hypervisor to ensure newly added memory is
accepted by TDX guests. If acceptance fails, return -EINVAL to mark the
device as broken rather than attempting rollback, since unplug operations
may also fail and partial acceptance creates difficult-to-recover state.

For memory unplugging, call the pre-unplug callback before requesting
memory removal from the hypervisor to allow TDX guests to release memory
pages. If release fails, return -EINVAL to mark the device as broken.

If the hypervisor unplug request fails after successful memory release,
attempt to re-accept the memory to restore consistent state for retry. If
re-acceptance fails, mark the device as broken to prevent corruption.

The config_changed check is moved to the wrapper functions to ensure
callbacks are not invoked unnecessarily when operations will be retried.

This integration ensures proper memory lifecycle management in
confidential computing environments while maintaining backward
compatibility with non-TDX systems where the callbacks are no-ops.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 drivers/virtio/virtio_mem.c | 80 ++++++++++++++++++++++++++++++++-----
 1 file changed, 70 insertions(+), 10 deletions(-)

diff --git a/drivers/virtio/virtio_mem.c b/drivers/virtio/virtio_mem.c
index 48051e9e98ab..12b8229dab0d 100644
--- a/drivers/virtio/virtio_mem.c
+++ b/drivers/virtio/virtio_mem.c
@@ -1416,8 +1416,8 @@ static uint64_t virtio_mem_send_request(struct virtio_mem *vm,
 	return virtio16_to_cpu(vm->vdev, vm->resp.type);
 }
 
-static int virtio_mem_send_plug_request(struct virtio_mem *vm, uint64_t addr,
-					uint64_t size)
+static int _virtio_mem_send_plug_request(struct virtio_mem *vm, uint64_t addr,
+					 uint64_t size)
 {
 	const uint64_t nb_vm_blocks = size / vm->device_block_size;
 	const struct virtio_mem_req req = {
@@ -1427,9 +1427,6 @@ static int virtio_mem_send_plug_request(struct virtio_mem *vm, uint64_t addr,
 	};
 	int rc = -ENOMEM;
 
-	if (atomic_read(&vm->config_changed))
-		return -EAGAIN;
-
 	dev_dbg(&vm->vdev->dev, "plugging memory: 0x%llx - 0x%llx\n", addr,
 		addr + size - 1);
 
@@ -1454,8 +1451,8 @@ static int virtio_mem_send_plug_request(struct virtio_mem *vm, uint64_t addr,
 	return rc;
 }
 
-static int virtio_mem_send_unplug_request(struct virtio_mem *vm, uint64_t addr,
-					  uint64_t size)
+static int _virtio_mem_send_unplug_request(struct virtio_mem *vm, uint64_t addr,
+					   uint64_t size)
 {
 	const uint64_t nb_vm_blocks = size / vm->device_block_size;
 	const struct virtio_mem_req req = {
@@ -1465,9 +1462,6 @@ static int virtio_mem_send_unplug_request(struct virtio_mem *vm, uint64_t addr,
 	};
 	int rc = -ENOMEM;
 
-	if (atomic_read(&vm->config_changed))
-		return -EAGAIN;
-
 	dev_dbg(&vm->vdev->dev, "unplugging memory: 0x%llx - 0x%llx\n", addr,
 		addr + size - 1);
 
@@ -1489,6 +1483,72 @@ static int virtio_mem_send_unplug_request(struct virtio_mem *vm, uint64_t addr,
 	return rc;
 }
 
+static int virtio_mem_send_plug_request(struct virtio_mem *vm, uint64_t addr,
+					uint64_t size)
+{
+	int ret;
+
+	if (atomic_read(&vm->config_changed))
+		return -EAGAIN;
+
+	ret = _virtio_mem_send_plug_request(vm, addr, size);
+	if (ret)
+		return ret;
+
+	/*
+	 * If memory acceptance fails, we cannot safely rollback to the pre-plug
+	 * state because the unplug operation may also fail (e.g., hypervisor
+	 * out of memory, VM migration in progress). Additionally, acceptance
+	 * failures may be partial, leaving some pages accepted and others not,
+	 * creating inconsistent memory state that is difficult to track and
+	 * recover from.
+	 *
+	 * Rather than attempting complex state recovery that may fail, we treat
+	 * acceptance failure as a critical error and return -EINVAL. This causes
+	 * the caller to set the broken flag and stop processing further requests,
+	 * preventing potential memory corruption or system instability. As a
+	 * consequence, the hypervisor-side memory for the failing range is
+	 * leaked for the lifetime of the device.
+	 */
+	if (memory_post_plug_call(addr, size))
+		return -EINVAL;
+
+	return 0;
+}
+
+static int virtio_mem_send_unplug_request(struct virtio_mem *vm, uint64_t addr,
+					  uint64_t size)
+{
+	int ret;
+
+	if (atomic_read(&vm->config_changed))
+		return -EAGAIN;
+
+	/*
+	 * If memory release fails, treat it as a critical error similar to
+	 * acceptance failure. See virtio_mem_send_plug_request() for detailed
+	 * rationale on why we avoid complex error recovery.
+	 */
+	ret = memory_pre_unplug_call(addr, size);
+	if (ret)
+		return -EINVAL;
+
+	ret = _virtio_mem_send_unplug_request(vm, addr, size);
+	/*
+	 * If the hypervisor unplug request fails (e.g., out of memory, VM
+	 * migration), the operation will be retried later. Since we already
+	 * released the memory from TDX perspective, we must re-accept it to
+	 * restore consistent state for the next retry. If re-acceptance fails,
+	 * treat it as critical error to prevent state corruption. As a
+	 * consequence, the hypervisor-side memory for the failing range is
+	 * leaked for the lifetime of the device.
+	 */
+	if (ret && memory_post_plug_call(addr, size))
+		return -EINVAL;
+
+	return ret;
+}
+
 static int virtio_mem_send_unplug_all_request(struct virtio_mem *vm)
 {
 	const struct virtio_mem_req req = {

---

## [5] Zhenzhong Duan — 2026-06-04
*Subject: [RFC PATCH 4/6] x86/tdx: Register memory post-plug callback for TDX guests*

Register a callback to handle memory acceptance after memory plugging in
TDX guests. When memory is added by virtio-mem or other memory hotplug
drivers, the TDX guest must accept the memory pages using
TDG.MEM.PAGE.ACCEPT TDCALL before they can be safely accessed.

The callback uses the existing tdx_accept_memory() function to accept all
pages in the newly plugged memory range. Without this callback, newly
added memory would remain in "unaccepted" state, and any access to these
pages would trigger VM exits and potentially cause guest crashes. The
callback is registered during TDX setup and remains active for the
lifetime of the guest, ensuring all dynamically added memory is properly
accepted before being made available to the kernel's memory management
subsystem.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 arch/x86/coco/tdx/tdx.c | 21 +++++++++++++++++++++
 1 file changed, 21 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 186915a17c50..d93ba092d311 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -326,6 +326,25 @@ static void reduce_unnecessary_ve(void)
 	enable_cpu_topology_enumeration();
 }
 
+static int tdx_memory_post_plug(u64 addr, u64 size)
+{
+	u64 end;
+
+	if (!PAGE_ALIGNED(addr) || !PAGE_ALIGNED(size))
+		return -EINVAL;
+
+	if (check_add_overflow(addr, size, &end))
+		return -EINVAL;
+
+	if (tdx_accept_memory(addr, end))
+		return 0;
+
+	pr_err("Failed to accept memory [0x%llx, 0x%llx)\n",
+	       (unsigned long long)addr, (unsigned long long)end);
+
+	return -EINVAL;
+}
+
 static void tdx_setup(u64 *cc_mask)
 {
 	struct tdx_module_args args = {};
@@ -359,6 +378,8 @@ static void tdx_setup(u64 *cc_mask)
 	disable_sept_ve(td_attr);
 
 	reduce_unnecessary_ve();
+
+	set_memory_post_plug_callback(tdx_memory_post_plug);
 }
 
 /*

---

## [6] Zhenzhong Duan — 2026-06-04
*Subject: [RFC PATCH 5/6] x86/tdx: Register memory pre-unplug callback for TDX guests*

Add support for releasing memory pages before unplugging in TDX guests.
When memory is about to be unplugged by virtio-mem or other memory
hotplug drivers, the TDX guest should release the memory pages back to the
hypervisor using TDG.MEM.PAGE.RELEASE TDCALL to be more robust for buggy
VMM behavior, e.g., VMM may do nothing for unplug request.

The implementation detects TDG.MEM.PAGE.RELEASE support and optimizes
release operations by trying larger page sizes 1G/2M before falling back
to 4K pages. If release fails, the function re-accepts any released pages
to maintain consistency. Without proper memory release, re-plugging memory
in TDX guests fails when guest accepts those memory because hypervisor can
do no-op to memory unplug request and memory is already in "accepted"
state.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 arch/x86/include/asm/shared/tdx.h |   2 +
 arch/x86/coco/tdx/tdx.c           | 135 ++++++++++++++++++++++++++++++
 2 files changed, 137 insertions(+)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 049638e3da74..910ec1e57528 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -19,6 +19,7 @@
 #define TDG_MEM_PAGE_ACCEPT		6
 #define TDG_VM_RD			7
 #define TDG_VM_WR			8
+#define TDG_MEM_PAGE_RELEASE		30
 
 /* TDX TD attributes */
 #define TDX_TD_ATTR_DEBUG_BIT		0
@@ -54,6 +55,7 @@
 
 /* TDCS_CONFIG_FLAGS bits */
 #define TDCS_CONFIG_FLEXIBLE_PENDING_VE	BIT_ULL(1)
+#define TDCS_CONFIG_PAGE_RELEASE	BIT_ULL(6)
 
 /* TDCS_TD_CTLS bits */
 #define TD_CTLS_PENDING_VE_DISABLE_BIT	0
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index d93ba092d311..0abfb3505093 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -345,6 +345,139 @@ static int tdx_memory_post_plug(u64 addr, u64 size)
 	return -EINVAL;
 }
 
+static bool tdx_page_release_supported;
+
+static void detect_mem_page_release(void)
+{
+	u64 config = 0;
+
+	tdg_vm_rd(TDCS_CONFIG_FLAGS, &config);
+
+	tdx_page_release_supported = !!(config & TDCS_CONFIG_PAGE_RELEASE);
+}
+
+static unsigned long try_release_one(phys_addr_t start, unsigned long len,
+				     enum pg_level pg_level)
+{
+	unsigned long release_size = page_level_size(pg_level);
+	struct tdx_module_args args = {};
+	u8 page_size;
+	u64 ret;
+
+	if (!IS_ALIGNED(start, release_size))
+		return 0;
+
+	if (len < release_size)
+		return 0;
+
+	/*
+	 * Pass the page physical address to TDX module to release the
+	 * private page and to put it in PENDING state.
+	 *
+	 * Bits 2:0 of RCX encode page size: 0 - 4K, 1 - 2M, 2 - 1G.
+	 */
+	switch (pg_level) {
+	case PG_LEVEL_4K:
+		page_size = TDX_PS_4K;
+		break;
+	case PG_LEVEL_2M:
+		page_size = TDX_PS_2M;
+		break;
+	case PG_LEVEL_1G:
+		page_size = TDX_PS_1G;
+		break;
+	default:
+		return 0;
+	}
+
+	args.rcx = start | page_size;
+	ret = __tdcall(TDG_MEM_PAGE_RELEASE, &args);
+	if (ret)
+		return 0;
+
+	return release_size;
+}
+
+static bool _tdx_release_memory(phys_addr_t start, phys_addr_t end, phys_addr_t *cur)
+{
+	*cur = start;
+
+	while (*cur < end) {
+		unsigned long len = end - *cur;
+		unsigned long release_size;
+
+		/*
+		 * Try larger release first. It speeds up process by cutting
+		 * number of hypercalls (if successful).
+		 */
+
+		release_size = try_release_one(*cur, len, PG_LEVEL_1G);
+		if (!release_size)
+			release_size = try_release_one(*cur, len, PG_LEVEL_2M);
+		if (!release_size)
+			release_size = try_release_one(*cur, len, PG_LEVEL_4K);
+		if (!release_size)
+			return false;
+		*cur += release_size;
+	}
+
+	return true;
+}
+
+/*
+ * Release memory pages back to the hypervisor in TDX guests.
+ *
+ * @start: Physical start address of memory range to release
+ * @end:   Physical end address of memory range to release
+ *
+ * Uses TDG.MEM.PAGE.RELEASE TDCALL to transition private pages back to
+ * pending state. If PAGE_RELEASE is not supported by the TDX
+ * configuration, returns true (success) as no action is needed.
+ *
+ * On partial failure, automatically re-accepts any successfully released
+ * pages to restore consistent memory state. Re-acceptance failure is
+ * treated as a fatal error since it indicates severe TDX module issues.
+ *
+ * Returns: true on success, false on failure
+ */
+static bool tdx_release_memory(phys_addr_t start, phys_addr_t end)
+{
+	phys_addr_t released = start;
+	bool ret;
+
+	if (!tdx_page_release_supported)
+		return true;
+
+	ret = _tdx_release_memory(start, end, &released);
+	if (!ret) {
+		pr_err("Failed to release memory [0x%llx, 0x%llx)\n",
+		       (unsigned long long)start, (unsigned long long)end);
+
+		/*
+		 * Re-accept any pages that were successfully released before
+		 * the failure occurred. This should never fail since we're
+		 * just restoring the previous accepted state.
+		 */
+		if (!tdx_accept_memory(start, released))
+			panic("%s Failed to re-accept memory\n", __func__);
+	}
+
+	return ret;
+}
+
+static int tdx_memory_pre_unplug(u64 addr, u64 size)
+{
+	u64 end;
+
+	if (!PAGE_ALIGNED(addr) || !PAGE_ALIGNED(size))
+		return -EINVAL;
+
+	if (check_add_overflow(addr, size, &end))
+		return -EINVAL;
+
+	return tdx_release_memory(addr, end) ? 0 : -EINVAL;
+}
+
 static void tdx_setup(u64 *cc_mask)
 {
 	struct tdx_module_args args = {};
@@ -380,6 +513,8 @@ static void tdx_setup(u64 *cc_mask)
 	reduce_unnecessary_ve();
 
 	set_memory_post_plug_callback(tdx_memory_post_plug);
+	detect_mem_page_release();
+	set_memory_pre_unplug_callback(tdx_memory_pre_unplug);
 }
 
 /*

---

## [7] Zhenzhong Duan — 2026-06-04
*Subject: [RFC PATCH 6/6] x86/tdx: Release private memory before private->shared conversion*

TDX supports a PAGE.RELEASE feature, when configured, host can only
remove a private page until guest releases it and puts it in a PENDING
state through TDG.MEM.PAGE.RELEASE.

When TDX PAGE.RELEASE is supported, release private memory pages before
converting them to shared state, this ensures pages transition from
accepted to pending state.

The release operation helps handle scenarios where the hypervisor may
retain old private pages during conversion. Without proper release,
subsequent shared->private conversions could encounter re-acceptance
errors when attempting to accept pages that are still in accepted state.

If the release operation fails, abort the conversion to prevent
inconsistent memory state. Note that if tdx_map_gpa() fails after
successful release, we cannot safely rollback because the GPA mapping may
have partially succeeded, creating a mix of shared and private pages that
cannot be reliably tracked or recovered.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 arch/x86/coco/tdx/tdx.c | 18 ++++++++++++++++++
 1 file changed, 18 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 0abfb3505093..ecee6df92395 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -1121,7 +1121,25 @@ static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 {
 	phys_addr_t start = __pa(vaddr);
 	phys_addr_t end   = __pa(vaddr + numpages * PAGE_SIZE);
+	bool release_required = !enc && tdx_page_release_supported;
 
+	/*
+	 * For private->shared conversion, release memory pages first.
+	 * This transitions pages from accepted to pending state to be
+	 * more robust with buggy VMM, e.g., VMM may keep old pages,
+	 * when converting back to private, re-accept error triggers.
+	 */
+	if (release_required && !tdx_release_memory(start, end))
+		return false;
+
+	/*
+	 * Update the GPA mapping state. If this fails, we cannot rollback
+	 * by calling tdx_accept_memory() because tdx_map_gpa() may have
+	 * partially succeeded, creating a mix of shared and private pages.
+	 * Attempting to accept the entire range would fail on pages that
+	 * are still in shared state, and we have no way to determine which
+	 * pages are in which state after partial failure.
+	 */
 	if (!tdx_map_gpa(start, end, enc))
 		return false;

---

## [8] Kiryl Shutsemau — 2026-06-12
*Subject: Re: [RFC PATCH 0/6] Support virtio-mem memory hotplug in TDX guests*

On Thu, Jun 04, 2026 at 05:35:45AM -0400, Zhenzhong Duan wrote:
> 2. Re-accepting already-accepted memory returns errors. Ignoring these errors
> can mislead the guest into believing re-accepted memory is zeroed when it

Re-accepting concern is valid, but often overblown. Reaccepting memory
that never got allocated is fine.

> == About this series ==
> 

You are presenting these callbacks as generic memory hotplug thingy, but
it is only plugged into virtio mem. ACPI hotplug won't accept/release
memory unless I miss something. Are you expecting them to cover non
virtio cases too?

And these callbacks feels like very ad-hoc solution.

> See Rick and Paolo's
> discussion about using TDG.MEM.PAGE.RELEASE in [1].

Having RELEASE in hotplug path without addressing private->shared
conversion first is odd. That's the most obvious path that has to be
covered first.

Hm?

> == Future work ==
> support lazy accept

It would be nice to have some outline on how we will get there to
understand if this patchset is stepping stone or dead end that has to be
thrown away later on.

Hot[un]plug is often used to manager overcommited host. Eager accept
might be counter-productive.

---

## [9] Duan, Zhenzhong — 2026-06-15
*Subject: RE: [RFC PATCH 0/6] Support virtio-mem memory hotplug in TDX guests*

>-----Original Message-----
>From: Kiryl Shutsemau <kas@kernel.org>

> Reaccepting memory that never got allocated is fine.

I don't quite understand. "Reaccepting" implies accepting memory that was
already accepted earlier. For that to happen, the memory must have already
been allocated on the VMM side, correct?

>
>> == About this series ==

You are right, I didn't add ACPI hotplug in this series. I'm working on RFCv2
supporting both virtio-mem and ACPI hotplug in eager/lazy accept mode.

>
>And these callbacks feels like very ad-hoc solution.

OK, will drop the callbacks in RFCv2.

>
>> See Rick and Paolo's

This patch series assumes that memory is plugged in as private memory
and must remain private prior to being unplugged. During the unplugging
process, memory is allocated from the buddy system and marked as
FAKE_OFFLINE. Because all free memory within the buddy system is
strictly private, shared memory can never be unplugged.

Shared memory is originally converted from private memory allocated by
the buddy system. Consequently, the driver must convert any shared
memory back to private and return it to the buddy system before it can
be unplugged.

>
>> == Future work ==

I realized the callbacks are specially used for eager accept, they are not
useful for lazy accept. So, I will drop them in RFCv2.

>
>Hot[un]plug is often used to manager overcommited host. Eager accept

Agree, I should have taken lazy accept into consideration from start.

Thanks
Zhenzhong

---
