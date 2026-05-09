---
title: '[RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for TDISP using TSM'
date: 2025-05-29
last_reply: 2025-07-15
message_count: 68
participants: ['Xu Yilun', 'Aneesh Kumar K.V', 'Jason Gunthorpe', 'Alexey Kardashevskiy', 'dan.j.williams@intel.com', 'Jonathan Cameron']
---

## [1] Xu Yilun — 2025-05-29

This series is the generic host side (KVM/VFIO/IOMMUFD) support for the
whole life cycle of private device assignment. It follows the
previously discussed flow chart [1], aim to better illustrate the
overall flow of private device assignment, find out and narrow down the
gaps of different vendors, and reach some common directions.

This series is based on Dan's Core TSM infrastructure series [2].  To
give a clear overview of what components are needed, it also includes
some existing WIP patchsets in community.

This series has 3 sections:

Patch 1 - 11 deal with the private MMIO mapping in KVM MMU via DMABUF.
Leverage Jason & Vivek's latest VFIO dmabuf series [3], see Patch 2 - 4.
The concern for get_pfn() kAPI [4] is not addressed so are marked as
HACK, will investigate later.

Patch 12 - 22 is about TSM Bind/Unbind/Guest request management in VFIO
& IOMMUFD. Picks some of Shameer's patch in [5], see Patch 12 & 14.

Patch 23 - 30 is a solution to meet the TDX specific sequence
enforcement on various device Unbind cases, including converting device
back to shared, hot unplug, TD destroy. Start with a tdx_tsm driver
prototype and finally implement the Unbind enforcement inside the
driver. To be honest it is still awkward to me, but I need help.

This series don't include the VMEXIT handle for GHCI/GHCB calls for
Bind/Unbind/Guest request, cause it involves vendor specific code. The
general idea is KVM should just pass these calls to QEMU, QEMU parses
out the command and call the newly introduced VFIO/IOMMUFD IOCTLs.

With additional TDX Connect specific patches (not published), passed
engineering test for trusted DMA in TD.

[1]: https://lore.kernel.org/all/aCYsNSFQJZzHVOFI@yilunxu-OptiPlex-7050/
[2]: https://lore.kernel.org/all/20250516054732.2055093-1-dan.j.williams@intel.com/
[3]: https://lore.kernel.org/kvm/20250307052248.405803-1-vivek.kasireddy@intel.com/
[4]: https://lore.kernel.org/all/20250107142719.179636-1-yilun.xu@linux.intel.com/
[5]: https://lore.kernel.org/all/20250319173202.78988-3-shameerali.kolothum.thodi@huawei.com/


Alexey Kardashevskiy (1):
  iommufd/vdevice: Add TSM Guest request uAPI

Dan Williams (2):
  coco/tdx_tsm: Introduce a "tdx" subsystem and "tsm" device
  coco/tdx_tsm: TEE Security Manager driver for TDX

Shameer Kolothum (2):
  iommufd/device: Associate a kvm pointer to iommufd_device
  iommu/arm-smmu-v3-iommufd: Pass in kvm pointer to viommu_alloc

Vivek Kasireddy (3):
  vfio: Export vfio device get and put registration helpers
  vfio/pci: Share the core device pointer while invoking feature
    functions
  vfio/pci: Allow MMIO regions to be exported through dma-buf

Wu Hao (1):
  coco/tdx_tsm: Add connect()/disconnect() handlers prototype

Xu Yilun (21):
  HACK: dma-buf: Introduce dma_buf_get_pfn_unlocked() kAPI
  fixup! vfio/pci: fix dma-buf revoke typo on reset
  HACK: vfio/pci: Support get_pfn() callback for dma-buf
  KVM: Support vfio_dmabuf backed MMIO region
  KVM: x86/mmu: Handle page fault for vfio_dmabuf backed MMIO
  KVM: x86/mmu: Handle page fault for private MMIO
  vfio/pci: Export vfio dma-buf specific info for importers
  KVM: vfio_dmabuf: Fetch VFIO specific dma-buf data for sanity check
  fixup! iommufd/selftest: Sync iommufd_device_bind() change to selftest
  fixup: iommu/selftest: Sync .viommu_alloc() change to selftest
  iommufd/viommu: track the kvm pointer & its refcount in viommu core
  iommufd/device: Add TSM Bind/Unbind for TIO support
  iommufd/viommu: Add trusted IOMMU configuration handlers for vdev
  vfio/pci: Add TSM TDI bind/unbind IOCTLs for TEE-IO support
  vfio/pci: Do TSM Unbind before zapping bars
  fixup! PCI/TSM: Change the guest request type definition
  coco/tdx_tsm: Add bind()/unbind()/guest_req() handlers prototype
  PCI/TSM: Add PCI driver callbacks to handle TSM requirements
  vfio/pci: Implement TSM handlers for MMIO
  iommufd/vdevice: Implement TSM handlers for trusted DMA
  coco/tdx_tsm: Manage TDX Module enforced operation sequences for
    Unbind

 Documentation/virt/kvm/api.rst                |   7 +
 arch/x86/Kconfig                              |   1 +
 arch/x86/kvm/mmu/mmu.c                        |  25 +-
 drivers/dma-buf/dma-buf.c                     |  87 +++-
 .../arm/arm-smmu-v3/arm-smmu-v3-iommufd.c     |   1 +
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h   |   1 +
 drivers/iommu/iommufd/device.c                |  89 +++-
 drivers/iommu/iommufd/iommufd_private.h       |  10 +
 drivers/iommu/iommufd/main.c                  |   3 +
 drivers/iommu/iommufd/selftest.c              |   3 +-
 drivers/iommu/iommufd/viommu.c                | 202 ++++++++-
 drivers/vfio/iommufd.c                        |  24 +-
 drivers/vfio/pci/Makefile                     |   1 +
 drivers/vfio/pci/vfio_pci.c                   |   1 +
 drivers/vfio/pci/vfio_pci_config.c            |  26 +-
 drivers/vfio/pci/vfio_pci_core.c              | 161 ++++++-
 drivers/vfio/pci/vfio_pci_dmabuf.c            | 411 ++++++++++++++++++
 drivers/vfio/pci/vfio_pci_priv.h              |  26 ++
 drivers/vfio/vfio_main.c                      |   2 +
 drivers/virt/coco/host/Kconfig                |  10 +
 drivers/virt/coco/host/Makefile               |   3 +
 drivers/virt/coco/host/tdx_tsm.c              | 328 ++++++++++++++
 drivers/virt/coco/host/tdx_tsm_bus.c          |  70 +++
 include/linux/dma-buf.h                       |  13 +
 include/linux/iommu.h                         |   4 +-
 include/linux/iommufd.h                       |  12 +-
 include/linux/kvm_host.h                      |  25 +-
 include/linux/pci-tsm.h                       |  19 +-
 include/linux/pci.h                           |   3 +
 include/linux/tdx_tsm_bus.h                   |  17 +
 include/linux/vfio.h                          |  27 ++
 include/linux/vfio_pci_core.h                 |   3 +
 include/uapi/linux/iommufd.h                  |  36 ++
 include/uapi/linux/kvm.h                      |   1 +
 include/uapi/linux/vfio.h                     |  67 +++
 virt/kvm/Kconfig                              |   6 +
 virt/kvm/Makefile.kvm                         |   1 +
 virt/kvm/kvm_main.c                           |  32 +-
 virt/kvm/kvm_mm.h                             |  19 +
 virt/kvm/vfio_dmabuf.c                        | 151 +++++++
 40 files changed, 1868 insertions(+), 60 deletions(-)
 create mode 100644 drivers/vfio/pci/vfio_pci_dmabuf.c
 create mode 100644 drivers/virt/coco/host/tdx_tsm.c
 create mode 100644 drivers/virt/coco/host/tdx_tsm_bus.c
 create mode 100644 include/linux/tdx_tsm_bus.h
 create mode 100644 virt/kvm/vfio_dmabuf.c


base-commit: 88c473f04098a0f5ac6fbaceaad2daa842006b6a

---

## [2] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 01/30] HACK: dma-buf: Introduce dma_buf_get_pfn_unlocked() kAPI*

This is just to illustrate the idea that dma-buf provides a new buffer
sharing mode - importer mapping. Exporter provides the target memory
resource description, importer decides what's the best way to map the
memory based on the information of target memory and importing device.

The get_pfn() kAPI is an initial attempt of this idea, obviously it is
not a full description for all kinds of memory types. But it enables
the FD based MMIO mapping in KVM to support private device assignement,
There are other concerns discussed [1] for this implementation, need
further investigation to work out a improved solution.

For now, no change to the previous version. [1]

[1]: https://lore.kernel.org/all/20250107142719.179636-2-yilun.xu@linux.intel.com/

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/dma-buf/dma-buf.c | 87 +++++++++++++++++++++++++++++++--------
 include/linux/dma-buf.h   | 13 ++++++
 2 files changed, 83 insertions(+), 17 deletions(-)

diff --git a/drivers/dma-buf/dma-buf.c b/drivers/dma-buf/dma-buf.c
index 5baa83b85515..58752f0bee36 100644
--- a/drivers/dma-buf/dma-buf.c
+++ b/drivers/dma-buf/dma-buf.c
@@ -630,10 +630,10 @@ struct dma_buf *dma_buf_export(const struct dma_buf_export_info *exp_info)
 	size_t alloc_size = sizeof(struct dma_buf);
 	int ret;
 
-	if (WARN_ON(!exp_info->priv || !exp_info->ops
-		    || !exp_info->ops->map_dma_buf
-		    || !exp_info->ops->unmap_dma_buf
-		    || !exp_info->ops->release))
+	if (WARN_ON(!exp_info->priv || !exp_info->ops ||
+		    (!!exp_info->ops->map_dma_buf != !!exp_info->ops->unmap_dma_buf) ||
+		    (!exp_info->ops->map_dma_buf && !exp_info->ops->get_pfn) ||
+		    !exp_info->ops->release))
 		return ERR_PTR(-EINVAL);
 
 	if (WARN_ON(exp_info->ops->cache_sgt_mapping &&
@@ -909,7 +909,7 @@ dma_buf_dynamic_attach(struct dma_buf *dmabuf, struct device *dev,
 	struct dma_buf_attachment *attach;
 	int ret;
 
-	if (WARN_ON(!dmabuf || !dev))
+	if (WARN_ON(!dmabuf))
 		return ERR_PTR(-EINVAL);
 
 	if (WARN_ON(importer_ops && !importer_ops->move_notify))
@@ -941,7 +941,7 @@ dma_buf_dynamic_attach(struct dma_buf *dmabuf, struct device *dev,
 	 */
 	if (dma_buf_attachment_is_dynamic(attach) !=
 	    dma_buf_is_dynamic(dmabuf)) {
-		struct sg_table *sgt;
+		struct sg_table *sgt = NULL;
 
 		dma_resv_lock(attach->dmabuf->resv, NULL);
 		if (dma_buf_is_dynamic(attach->dmabuf)) {
@@ -950,13 +950,16 @@ dma_buf_dynamic_attach(struct dma_buf *dmabuf, struct device *dev,
 				goto err_unlock;
 		}
 
-		sgt = __map_dma_buf(attach, DMA_BIDIRECTIONAL);
-		if (!sgt)
-			sgt = ERR_PTR(-ENOMEM);
-		if (IS_ERR(sgt)) {
-			ret = PTR_ERR(sgt);
-			goto err_unpin;
+		if (dev && dmabuf->ops->map_dma_buf) {
+			sgt = __map_dma_buf(attach, DMA_BIDIRECTIONAL);
+			if (!sgt)
+				sgt = ERR_PTR(-ENOMEM);
+			if (IS_ERR(sgt)) {
+				ret = PTR_ERR(sgt);
+				goto err_unpin;
+			}
 		}
+
 		dma_resv_unlock(attach->dmabuf->resv);
 		attach->sgt = sgt;
 		attach->dir = DMA_BIDIRECTIONAL;
@@ -1119,7 +1122,8 @@ struct sg_table *dma_buf_map_attachment(struct dma_buf_attachment *attach,
 
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf))
+	if (WARN_ON(!attach || !attach->dmabuf || !attach->dev ||
+		    !attach->dmabuf->ops->map_dma_buf))
 		return ERR_PTR(-EINVAL);
 
 	dma_resv_assert_held(attach->dmabuf->resv);
@@ -1195,7 +1199,8 @@ dma_buf_map_attachment_unlocked(struct dma_buf_attachment *attach,
 
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf))
+	if (WARN_ON(!attach || !attach->dmabuf || !attach->dev ||
+		    !attach->dmabuf->ops->map_dma_buf))
 		return ERR_PTR(-EINVAL);
 
 	dma_resv_lock(attach->dmabuf->resv, NULL);
@@ -1222,7 +1227,8 @@ void dma_buf_unmap_attachment(struct dma_buf_attachment *attach,
 {
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf || !sg_table))
+	if (WARN_ON(!attach || !attach->dmabuf || !attach->dev ||
+		    !attach->dmabuf->ops->unmap_dma_buf || !sg_table))
 		return;
 
 	dma_resv_assert_held(attach->dmabuf->resv);
@@ -1254,7 +1260,8 @@ void dma_buf_unmap_attachment_unlocked(struct dma_buf_attachment *attach,
 {
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf || !sg_table))
+	if (WARN_ON(!attach || !attach->dmabuf || !attach->dev ||
+		    !attach->dmabuf->ops->unmap_dma_buf || !sg_table))
 		return;
 
 	dma_resv_lock(attach->dmabuf->resv, NULL);
@@ -1263,6 +1270,52 @@ void dma_buf_unmap_attachment_unlocked(struct dma_buf_attachment *attach,
 }
 EXPORT_SYMBOL_NS_GPL(dma_buf_unmap_attachment_unlocked, "DMA_BUF");
 
+/**
+ * dma_buf_get_pfn_unlocked -
+ * @attach:	[in]	attachment to get pfn from
+ * @pgoff:	[in]	page offset of the buffer against the start of dma_buf
+ * @pfn:	[out]	returns the pfn of the buffer
+ * @max_order	[out]	returns the max mapping order of the buffer
+ */
+int dma_buf_get_pfn_unlocked(struct dma_buf_attachment *attach,
+			     pgoff_t pgoff, u64 *pfn, int *max_order)
+{
+	struct dma_buf *dmabuf = attach->dmabuf;
+	int ret;
+
+	if (WARN_ON(!attach || !attach->dmabuf ||
+		    !attach->dmabuf->ops->get_pfn))
+		return -EINVAL;
+
+	/*
+	 * Open:
+	 *
+	 * When dma_buf is dynamic but dma_buf move is disabled, the buffer
+	 * should be pinned before use, See dma_buf_map_attachment() for
+	 * reference.
+	 *
+	 * But for now no pin is intended inside dma_buf_get_pfn(), otherwise
+	 * need another API to unpin the dma_buf. So just fail out this case.
+	 */
+	if (dma_buf_is_dynamic(attach->dmabuf) &&
+	    !IS_ENABLED(CONFIG_DMABUF_MOVE_NOTIFY))
+		return -ENOENT;
+
+	dma_resv_lock(attach->dmabuf->resv, NULL);
+	ret = dmabuf->ops->get_pfn(attach, pgoff, pfn, max_order);
+	/*
+	 * Open:
+	 *
+	 * Is dma_resv_wait_timeout() needed? I assume no. The DMA buffer
+	 * content synchronization could be done when the buffer is to be
+	 * mapped by importer.
+	 */
+	dma_resv_unlock(attach->dmabuf->resv);
+
+	return ret;
+}
+EXPORT_SYMBOL_NS_GPL(dma_buf_get_pfn_unlocked, "DMA_BUF");
+
 /**
  * dma_buf_move_notify - notify attachments that DMA-buf is moving
  *
@@ -1662,7 +1715,7 @@ static int dma_buf_debug_show(struct seq_file *s, void *unused)
 		attach_count = 0;
 
 		list_for_each_entry(attach_obj, &buf_obj->attachments, node) {
-			seq_printf(s, "\t%s\n", dev_name(attach_obj->dev));
+			seq_printf(s, "\t%s\n", attach_obj->dev ? dev_name(attach_obj->dev) : NULL);
 			attach_count++;
 		}
 		dma_resv_unlock(buf_obj->resv);
diff --git a/include/linux/dma-buf.h b/include/linux/dma-buf.h
index 36216d28d8bd..b16183edfb3a 100644
--- a/include/linux/dma-buf.h
+++ b/include/linux/dma-buf.h
@@ -194,6 +194,17 @@ struct dma_buf_ops {
 	 * if the call would block.
 	 */
 
+	/**
+	 * @get_pfn:
+	 *
+	 * This is called by dma_buf_get_pfn(). It is used to get the pfn
+	 * of the buffer positioned by the page offset against the start of
+	 * the dma_buf. It can only be called if @attach has been called
+	 * successfully.
+	 */
+	int (*get_pfn)(struct dma_buf_attachment *attach, pgoff_t pgoff,
+		       u64 *pfn, int *max_order);
+
 	/**
 	 * @release:
 	 *
@@ -629,6 +640,8 @@ dma_buf_map_attachment_unlocked(struct dma_buf_attachment *attach,
 void dma_buf_unmap_attachment_unlocked(struct dma_buf_attachment *attach,
 				       struct sg_table *sg_table,
 				       enum dma_data_direction direction);
+int dma_buf_get_pfn_unlocked(struct dma_buf_attachment *attach,
+			     pgoff_t pgoff, u64 *pfn, int *max_order);
 
 int dma_buf_mmap(struct dma_buf *, struct vm_area_struct *,
 		 unsigned long);

---

## [3] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 02/30] vfio: Export vfio device get and put registration helpers*

From: Vivek Kasireddy <vivek.kasireddy@intel.com>

These helpers are useful for managing additional references taken
on the device from other associated VFIO modules.

Original-patch-by: Jason Gunthorpe <jgg@nvidia.com>
Signed-off-by: Vivek Kasireddy <vivek.kasireddy@intel.com>
---
 drivers/vfio/vfio_main.c | 2 ++
 include/linux/vfio.h     | 2 ++
 2 files changed, 4 insertions(+)

diff --git a/drivers/vfio/vfio_main.c b/drivers/vfio/vfio_main.c
index 1fd261efc582..620a3ee5d04d 100644
--- a/drivers/vfio/vfio_main.c
+++ b/drivers/vfio/vfio_main.c
@@ -171,11 +171,13 @@ void vfio_device_put_registration(struct vfio_device *device)
 	if (refcount_dec_and_test(&device->refcount))
 		complete(&device->comp);
 }
+EXPORT_SYMBOL_GPL(vfio_device_put_registration);
 
 bool vfio_device_try_get_registration(struct vfio_device *device)
 {
 	return refcount_inc_not_zero(&device->refcount);
 }
+EXPORT_SYMBOL_GPL(vfio_device_try_get_registration);
 
 /*
  * VFIO driver API
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index 707b00772ce1..ba65bbdffd0b 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -293,6 +293,8 @@ static inline void vfio_put_device(struct vfio_device *device)
 int vfio_register_group_dev(struct vfio_device *device);
 int vfio_register_emulated_iommu_dev(struct vfio_device *device);
 void vfio_unregister_group_dev(struct vfio_device *device);
+bool vfio_device_try_get_registration(struct vfio_device *device);
+void vfio_device_put_registration(struct vfio_device *device);
 
 int vfio_assign_device_set(struct vfio_device *device, void *set_id);
 unsigned int vfio_device_set_open_count(struct vfio_device_set *dev_set);

---

## [4] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 03/30] vfio/pci: Share the core device pointer while invoking feature functions*

From: Vivek Kasireddy <vivek.kasireddy@intel.com>

There is no need to share the main device pointer (struct vfio_device *)
with all the feature functions as they only need the core device
pointer. Therefore, extract the core device pointer once in the
caller (vfio_pci_core_ioctl_feature) and share it instead.

Signed-off-by: Vivek Kasireddy <vivek.kasireddy@intel.com>
---
 drivers/vfio/pci/vfio_pci_core.c | 30 +++++++++++++-----------------
 1 file changed, 13 insertions(+), 17 deletions(-)

diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index 35f9046af315..adfcbc2231cb 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -300,11 +300,9 @@ static int vfio_pci_runtime_pm_entry(struct vfio_pci_core_device *vdev,
 	return 0;
 }
 
-static int vfio_pci_core_pm_entry(struct vfio_device *device, u32 flags,
+static int vfio_pci_core_pm_entry(struct vfio_pci_core_device *vdev, u32 flags,
 				  void __user *arg, size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	int ret;
 
 	ret = vfio_check_feature(flags, argsz, VFIO_DEVICE_FEATURE_SET, 0);
@@ -321,12 +319,10 @@ static int vfio_pci_core_pm_entry(struct vfio_device *device, u32 flags,
 }
 
 static int vfio_pci_core_pm_entry_with_wakeup(
-	struct vfio_device *device, u32 flags,
+	struct vfio_pci_core_device *vdev, u32 flags,
 	struct vfio_device_low_power_entry_with_wakeup __user *arg,
 	size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	struct vfio_device_low_power_entry_with_wakeup entry;
 	struct eventfd_ctx *efdctx;
 	int ret;
@@ -377,11 +373,9 @@ static void vfio_pci_runtime_pm_exit(struct vfio_pci_core_device *vdev)
 	up_write(&vdev->memory_lock);
 }
 
-static int vfio_pci_core_pm_exit(struct vfio_device *device, u32 flags,
+static int vfio_pci_core_pm_exit(struct vfio_pci_core_device *vdev, u32 flags,
 				 void __user *arg, size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	int ret;
 
 	ret = vfio_check_feature(flags, argsz, VFIO_DEVICE_FEATURE_SET, 0);
@@ -1474,11 +1468,10 @@ long vfio_pci_core_ioctl(struct vfio_device *core_vdev, unsigned int cmd,
 }
 EXPORT_SYMBOL_GPL(vfio_pci_core_ioctl);
 
-static int vfio_pci_core_feature_token(struct vfio_device *device, u32 flags,
-				       uuid_t __user *arg, size_t argsz)
+static int vfio_pci_core_feature_token(struct vfio_pci_core_device *vdev,
+				       u32 flags, uuid_t __user *arg,
+				       size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	uuid_t uuid;
 	int ret;
 
@@ -1505,16 +1498,19 @@ static int vfio_pci_core_feature_token(struct vfio_device *device, u32 flags,
 int vfio_pci_core_ioctl_feature(struct vfio_device *device, u32 flags,
 				void __user *arg, size_t argsz)
 {
+	struct vfio_pci_core_device *vdev =
+		container_of(device, struct vfio_pci_core_device, vdev);
+
 	switch (flags & VFIO_DEVICE_FEATURE_MASK) {
 	case VFIO_DEVICE_FEATURE_LOW_POWER_ENTRY:
-		return vfio_pci_core_pm_entry(device, flags, arg, argsz);
+		return vfio_pci_core_pm_entry(vdev, flags, arg, argsz);
 	case VFIO_DEVICE_FEATURE_LOW_POWER_ENTRY_WITH_WAKEUP:
-		return vfio_pci_core_pm_entry_with_wakeup(device, flags,
+		return vfio_pci_core_pm_entry_with_wakeup(vdev, flags,
 							  arg, argsz);
 	case VFIO_DEVICE_FEATURE_LOW_POWER_EXIT:
-		return vfio_pci_core_pm_exit(device, flags, arg, argsz);
+		return vfio_pci_core_pm_exit(vdev, flags, arg, argsz);
 	case VFIO_DEVICE_FEATURE_PCI_VF_TOKEN:
-		return vfio_pci_core_feature_token(device, flags, arg, argsz);
+		return vfio_pci_core_feature_token(vdev, flags, arg, argsz);
 	default:
 		return -ENOTTY;
 	}

---

## [5] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 04/30] vfio/pci: Allow MMIO regions to be exported through dma-buf*

From: Vivek Kasireddy <vivek.kasireddy@intel.com>

>From Jason Gunthorpe:
"dma-buf has become a way to safely acquire a handle to non-struct page
memory that can still have lifetime controlled by the exporter. Notably
RDMA can now import dma-buf FDs and build them into MRs which allows for
PCI P2P operations. Extend this to allow vfio-pci to export MMIO memory
from PCI device BARs.

The patch design loosely follows the pattern in commit
db1a8dd916aa ("habanalabs: add support for dma-buf exporter") except this
does not support pinning.

Instead, this implements what, in the past, we've called a revocable
attachment using move. In normal situations the attachment is pinned, as a
BAR does not change physical address. However when the VFIO device is
closed, or a PCI reset is issued, access to the MMIO memory is revoked.

Revoked means that move occurs, but an attempt to immediately re-map the
memory will fail. In the reset case a future move will be triggered when
MMIO access returns. As both close and reset are under userspace control
it is expected that userspace will suspend use of the dma-buf before doing
these operations, the revoke is purely for kernel self-defense against a
hostile userspace."

Following enhancements are made to the original patch:
- Add support for creating dmabuf from multiple areas (or ranges)

Cc: Alex Williamson <alex.williamson@redhat.com>
Cc: Simona Vetter <simona.vetter@ffwll.ch>
Cc: Christian König <christian.koenig@amd.com>
Original-patch-by: Jason Gunthorpe <jgg@nvidia.com>
Signed-off-by: Vivek Kasireddy <vivek.kasireddy@intel.com>
---
 drivers/vfio/pci/Makefile          |   1 +
 drivers/vfio/pci/vfio_pci_config.c |  22 +-
 drivers/vfio/pci/vfio_pci_core.c   |  20 +-
 drivers/vfio/pci/vfio_pci_dmabuf.c | 359 +++++++++++++++++++++++++++++
 drivers/vfio/pci/vfio_pci_priv.h   |  23 ++
 include/linux/vfio_pci_core.h      |   1 +
 include/uapi/linux/vfio.h          |  25 ++
 7 files changed, 446 insertions(+), 5 deletions(-)
 create mode 100644 drivers/vfio/pci/vfio_pci_dmabuf.c

diff --git a/drivers/vfio/pci/Makefile b/drivers/vfio/pci/Makefile
index cf00c0a7e55c..c33ec0cbe930 100644
--- a/drivers/vfio/pci/Makefile
+++ b/drivers/vfio/pci/Makefile
@@ -2,6 +2,7 @@
 
 vfio-pci-core-y := vfio_pci_core.o vfio_pci_intrs.o vfio_pci_rdwr.o vfio_pci_config.o
 vfio-pci-core-$(CONFIG_VFIO_PCI_ZDEV_KVM) += vfio_pci_zdev.o
+vfio-pci-core-$(CONFIG_DMA_SHARED_BUFFER) += vfio_pci_dmabuf.o
 obj-$(CONFIG_VFIO_PCI_CORE) += vfio-pci-core.o
 
 vfio-pci-y := vfio_pci.o
diff --git a/drivers/vfio/pci/vfio_pci_config.c b/drivers/vfio/pci/vfio_pci_config.c
index 14437396d721..efccbb2d2a42 100644
--- a/drivers/vfio/pci/vfio_pci_config.c
+++ b/drivers/vfio/pci/vfio_pci_config.c
@@ -589,10 +589,12 @@ static int vfio_basic_config_write(struct vfio_pci_core_device *vdev, int pos,
 		virt_mem = !!(le16_to_cpu(*virt_cmd) & PCI_COMMAND_MEMORY);
 		new_mem = !!(new_cmd & PCI_COMMAND_MEMORY);
 
-		if (!new_mem)
+		if (!new_mem) {
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
-		else
+			vfio_pci_dma_buf_move(vdev, true);
+		} else {
 			down_write(&vdev->memory_lock);
+		}
 
 		/*
 		 * If the user is writing mem/io enable (new_mem/io) and we
@@ -627,6 +629,8 @@ static int vfio_basic_config_write(struct vfio_pci_core_device *vdev, int pos,
 		*virt_cmd &= cpu_to_le16(~mask);
 		*virt_cmd |= cpu_to_le16(new_cmd & mask);
 
+		if (__vfio_pci_memory_enabled(vdev))
+			vfio_pci_dma_buf_move(vdev, false);
 		up_write(&vdev->memory_lock);
 	}
 
@@ -707,12 +711,16 @@ static int __init init_pci_cap_basic_perm(struct perm_bits *perm)
 static void vfio_lock_and_set_power_state(struct vfio_pci_core_device *vdev,
 					  pci_power_t state)
 {
-	if (state >= PCI_D3hot)
+	if (state >= PCI_D3hot) {
 		vfio_pci_zap_and_down_write_memory_lock(vdev);
-	else
+		vfio_pci_dma_buf_move(vdev, true);
+	} else {
 		down_write(&vdev->memory_lock);
+	}
 
 	vfio_pci_set_power_state(vdev, state);
+	if (__vfio_pci_memory_enabled(vdev))
+		vfio_pci_dma_buf_move(vdev, false);
 	up_write(&vdev->memory_lock);
 }
 
@@ -900,7 +908,10 @@ static int vfio_exp_config_write(struct vfio_pci_core_device *vdev, int pos,
 
 		if (!ret && (cap & PCI_EXP_DEVCAP_FLR)) {
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
+			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
+			if (__vfio_pci_memory_enabled(vdev))
+				vfio_pci_dma_buf_move(vdev, true);
 			up_write(&vdev->memory_lock);
 		}
 	}
@@ -982,7 +993,10 @@ static int vfio_af_config_write(struct vfio_pci_core_device *vdev, int pos,
 
 		if (!ret && (cap & PCI_AF_CAP_FLR) && (cap & PCI_AF_CAP_TP)) {
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
+			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
+			if (__vfio_pci_memory_enabled(vdev))
+				vfio_pci_dma_buf_move(vdev, true);
 			up_write(&vdev->memory_lock);
 		}
 	}
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index adfcbc2231cb..116964057b0b 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -287,6 +287,8 @@ static int vfio_pci_runtime_pm_entry(struct vfio_pci_core_device *vdev,
 	 * semaphore.
 	 */
 	vfio_pci_zap_and_down_write_memory_lock(vdev);
+	vfio_pci_dma_buf_move(vdev, true);
+
 	if (vdev->pm_runtime_engaged) {
 		up_write(&vdev->memory_lock);
 		return -EINVAL;
@@ -370,6 +372,8 @@ static void vfio_pci_runtime_pm_exit(struct vfio_pci_core_device *vdev)
 	 */
 	down_write(&vdev->memory_lock);
 	__vfio_pci_runtime_pm_exit(vdev);
+	if (__vfio_pci_memory_enabled(vdev))
+		vfio_pci_dma_buf_move(vdev, false);
 	up_write(&vdev->memory_lock);
 }
 
@@ -690,6 +694,8 @@ void vfio_pci_core_close_device(struct vfio_device *core_vdev)
 #endif
 	vfio_pci_core_disable(vdev);
 
+	vfio_pci_dma_buf_cleanup(vdev);
+
 	mutex_lock(&vdev->igate);
 	if (vdev->err_trigger) {
 		eventfd_ctx_put(vdev->err_trigger);
@@ -1222,7 +1228,10 @@ static int vfio_pci_ioctl_reset(struct vfio_pci_core_device *vdev,
 	 */
 	vfio_pci_set_power_state(vdev, PCI_D0);
 
+	vfio_pci_dma_buf_move(vdev, true);
 	ret = pci_try_reset_function(vdev->pdev);
+	if (__vfio_pci_memory_enabled(vdev))
+		vfio_pci_dma_buf_move(vdev, false);
 	up_write(&vdev->memory_lock);
 
 	return ret;
@@ -1511,6 +1520,8 @@ int vfio_pci_core_ioctl_feature(struct vfio_device *device, u32 flags,
 		return vfio_pci_core_pm_exit(vdev, flags, arg, argsz);
 	case VFIO_DEVICE_FEATURE_PCI_VF_TOKEN:
 		return vfio_pci_core_feature_token(vdev, flags, arg, argsz);
+	case VFIO_DEVICE_FEATURE_DMA_BUF:
+		return vfio_pci_core_feature_dma_buf(vdev, flags, arg, argsz);
 	default:
 		return -ENOTTY;
 	}
@@ -2087,6 +2098,7 @@ int vfio_pci_core_init_dev(struct vfio_device *core_vdev)
 	INIT_LIST_HEAD(&vdev->dummy_resources_list);
 	INIT_LIST_HEAD(&vdev->ioeventfds_list);
 	INIT_LIST_HEAD(&vdev->sriov_pfs_item);
+	INIT_LIST_HEAD(&vdev->dmabufs);
 	init_rwsem(&vdev->memory_lock);
 	xa_init(&vdev->ctx);
 
@@ -2469,11 +2481,17 @@ static int vfio_pci_dev_set_hot_reset(struct vfio_device_set *dev_set,
 	 * cause the PCI config space reset without restoring the original
 	 * state (saved locally in 'vdev->pm_save').
 	 */
-	list_for_each_entry(vdev, &dev_set->device_list, vdev.dev_set_list)
+	list_for_each_entry(vdev, &dev_set->device_list, vdev.dev_set_list) {
+		vfio_pci_dma_buf_move(vdev, true);
 		vfio_pci_set_power_state(vdev, PCI_D0);
+	}
 
 	ret = pci_reset_bus(pdev);
 
+	list_for_each_entry(vdev, &dev_set->device_list, vdev.dev_set_list)
+		if (__vfio_pci_memory_enabled(vdev))
+			vfio_pci_dma_buf_move(vdev, false);
+
 	vdev = list_last_entry(&dev_set->device_list,
 			       struct vfio_pci_core_device, vdev.dev_set_list);
 
diff --git a/drivers/vfio/pci/vfio_pci_dmabuf.c b/drivers/vfio/pci/vfio_pci_dmabuf.c
new file mode 100644
index 000000000000..a4c313ca5bda
--- /dev/null
+++ b/drivers/vfio/pci/vfio_pci_dmabuf.c
@@ -0,0 +1,359 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES.
+ */
+#include <linux/dma-buf.h>
+#include <linux/pci-p2pdma.h>
+#include <linux/dma-resv.h>
+
+#include "vfio_pci_priv.h"
+
+MODULE_IMPORT_NS("DMA_BUF");
+
+struct vfio_pci_dma_buf {
+	struct dma_buf *dmabuf;
+	struct vfio_pci_core_device *vdev;
+	struct list_head dmabufs_elm;
+	unsigned int nr_ranges;
+	struct vfio_region_dma_range *dma_ranges;
+	unsigned int orig_nents;
+	bool revoked;
+};
+
+static int vfio_pci_dma_buf_attach(struct dma_buf *dmabuf,
+				   struct dma_buf_attachment *attachment)
+{
+	struct vfio_pci_dma_buf *priv = dmabuf->priv;
+	int rc;
+
+	rc = pci_p2pdma_distance_many(priv->vdev->pdev, &attachment->dev, 1,
+				      true);
+	if (rc < 0)
+		attachment->peer2peer = false;
+	return 0;
+}
+
+static void vfio_pci_dma_buf_unpin(struct dma_buf_attachment *attachment)
+{
+}
+
+static int vfio_pci_dma_buf_pin(struct dma_buf_attachment *attachment)
+{
+	/*
+	 * Uses the dynamic interface but must always allow for
+	 * dma_buf_move_notify() to do revoke
+	 */
+	return -EINVAL;
+}
+
+static int populate_sgt(struct dma_buf_attachment *attachment,
+			enum dma_data_direction dir,
+			struct sg_table *sgt, size_t sgl_size)
+{
+	struct vfio_pci_dma_buf *priv = attachment->dmabuf->priv;
+	struct vfio_region_dma_range *dma_ranges = priv->dma_ranges;
+	size_t offset, chunk_size;
+	struct scatterlist *sgl;
+	dma_addr_t dma_addr;
+	phys_addr_t phys;
+	int i, j, ret;
+
+	for_each_sgtable_sg(sgt, sgl, j)
+		sgl->length = 0;
+
+	sgl = sgt->sgl;
+	for (i = 0; i < priv->nr_ranges; i++) {
+		phys = pci_resource_start(priv->vdev->pdev,
+					  dma_ranges[i].region_index);
+		phys += dma_ranges[i].offset;
+
+		/*
+		 * Break the BAR's physical range up into max sized SGL's
+		 * according to the device's requirement.
+		 */
+		for (offset = 0; offset != dma_ranges[i].length;) {
+			chunk_size = min(dma_ranges[i].length - offset,
+					 sgl_size);
+
+			/*
+			 * Since the memory being mapped is a device memory
+			 * it could never be in CPU caches.
+			 */
+			dma_addr = dma_map_resource(attachment->dev,
+						    phys + offset,
+						    chunk_size, dir,
+						    DMA_ATTR_SKIP_CPU_SYNC);
+			ret = dma_mapping_error(attachment->dev, dma_addr);
+			if (ret)
+				goto err;
+
+			sg_set_page(sgl, NULL, chunk_size, 0);
+			sg_dma_address(sgl) = dma_addr;
+			sg_dma_len(sgl) = chunk_size;
+			sgl = sg_next(sgl);
+			offset += chunk_size;
+		}
+	}
+
+	return 0;
+err:
+	for_each_sgtable_sg(sgt, sgl, j) {
+		if (!sg_dma_len(sgl))
+			continue;
+
+		dma_unmap_resource(attachment->dev, sg_dma_address(sgl),
+				   sg_dma_len(sgl),
+				   dir, DMA_ATTR_SKIP_CPU_SYNC);
+	}
+
+	return ret;
+}
+
+static struct sg_table *
+vfio_pci_dma_buf_map(struct dma_buf_attachment *attachment,
+		     enum dma_data_direction dir)
+{
+	size_t sgl_size = dma_get_max_seg_size(attachment->dev);
+	struct vfio_pci_dma_buf *priv = attachment->dmabuf->priv;
+	struct sg_table *sgt;
+	unsigned int nents;
+	int ret;
+
+	dma_resv_assert_held(priv->dmabuf->resv);
+
+	if (!attachment->peer2peer)
+		return ERR_PTR(-EPERM);
+
+	if (priv->revoked)
+		return ERR_PTR(-ENODEV);
+
+	sgt = kzalloc(sizeof(*sgt), GFP_KERNEL);
+	if (!sgt)
+		return ERR_PTR(-ENOMEM);
+
+	nents = DIV_ROUND_UP(priv->dmabuf->size, sgl_size);
+	ret = sg_alloc_table(sgt, nents, GFP_KERNEL);
+	if (ret)
+		goto err_kfree_sgt;
+
+	ret = populate_sgt(attachment, dir, sgt, sgl_size);
+	if (ret)
+		goto err_free_sgt;
+
+	/*
+	 * Because we are not going to include a CPU list we want to have some
+	 * chance that other users will detect this by setting the orig_nents to
+	 * 0 and using only nents (length of DMA list) when going over the sgl
+	 */
+	priv->orig_nents = sgt->orig_nents;
+	sgt->orig_nents = 0;
+	return sgt;
+
+err_free_sgt:
+	sg_free_table(sgt);
+err_kfree_sgt:
+	kfree(sgt);
+	return ERR_PTR(ret);
+}
+
+static void vfio_pci_dma_buf_unmap(struct dma_buf_attachment *attachment,
+				   struct sg_table *sgt,
+				   enum dma_data_direction dir)
+{
+	struct vfio_pci_dma_buf *priv = attachment->dmabuf->priv;
+	struct scatterlist *sgl;
+	int i;
+
+	for_each_sgtable_dma_sg(sgt, sgl, i)
+		dma_unmap_resource(attachment->dev,
+				   sg_dma_address(sgl),
+				   sg_dma_len(sgl),
+				   dir, DMA_ATTR_SKIP_CPU_SYNC);
+
+	sgt->orig_nents = priv->orig_nents;
+	sg_free_table(sgt);
+	kfree(sgt);
+}
+
+static void vfio_pci_dma_buf_release(struct dma_buf *dmabuf)
+{
+	struct vfio_pci_dma_buf *priv = dmabuf->priv;
+
+	/*
+	 * Either this or vfio_pci_dma_buf_cleanup() will remove from the list.
+	 * The refcount prevents both.
+	 */
+	if (priv->vdev) {
+		down_write(&priv->vdev->memory_lock);
+		list_del_init(&priv->dmabufs_elm);
+		up_write(&priv->vdev->memory_lock);
+		vfio_device_put_registration(&priv->vdev->vdev);
+	}
+	kfree(priv);
+}
+
+static const struct dma_buf_ops vfio_pci_dmabuf_ops = {
+	.attach = vfio_pci_dma_buf_attach,
+	.map_dma_buf = vfio_pci_dma_buf_map,
+	.pin = vfio_pci_dma_buf_pin,
+	.unpin = vfio_pci_dma_buf_unpin,
+	.release = vfio_pci_dma_buf_release,
+	.unmap_dma_buf = vfio_pci_dma_buf_unmap,
+};
+
+static int check_dma_ranges(struct vfio_pci_dma_buf *priv,
+			    uint64_t *dmabuf_size)
+{
+	struct vfio_region_dma_range *dma_ranges = priv->dma_ranges;
+	struct pci_dev *pdev = priv->vdev->pdev;
+	resource_size_t bar_size;
+	int i;
+
+	for (i = 0; i < priv->nr_ranges; i++) {
+		/*
+		 * For PCI the region_index is the BAR number like
+		 * everything else.
+		 */
+		if (dma_ranges[i].region_index >= VFIO_PCI_ROM_REGION_INDEX)
+			return -EINVAL;
+
+		if (!PAGE_ALIGNED(dma_ranges[i].offset) ||
+		    !PAGE_ALIGNED(dma_ranges[i].length))
+			return -EINVAL;
+
+		bar_size = pci_resource_len(pdev, dma_ranges[i].region_index);
+		if (dma_ranges[i].offset > bar_size ||
+		    dma_ranges[i].offset + dma_ranges[i].length > bar_size)
+			return -EINVAL;
+
+		*dmabuf_size += dma_ranges[i].length;
+	}
+
+	return 0;
+}
+
+int vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
+				  struct vfio_device_feature_dma_buf __user *arg,
+				  size_t argsz)
+{
+	struct vfio_device_feature_dma_buf get_dma_buf;
+	struct vfio_region_dma_range *dma_ranges;
+	DEFINE_DMA_BUF_EXPORT_INFO(exp_info);
+	struct vfio_pci_dma_buf *priv;
+	uint64_t dmabuf_size = 0;
+	int ret;
+
+	ret = vfio_check_feature(flags, argsz, VFIO_DEVICE_FEATURE_GET,
+				 sizeof(get_dma_buf));
+	if (ret != 1)
+		return ret;
+
+	if (copy_from_user(&get_dma_buf, arg, sizeof(get_dma_buf)))
+		return -EFAULT;
+
+	dma_ranges = memdup_array_user(&arg->dma_ranges,
+				      get_dma_buf.nr_ranges,
+				      sizeof(*dma_ranges));
+	if (IS_ERR(dma_ranges))
+		return PTR_ERR(dma_ranges);
+
+	priv = kzalloc(sizeof(*priv), GFP_KERNEL);
+	if (!priv) {
+		kfree(dma_ranges);
+		return -ENOMEM;
+	}
+
+	priv->vdev = vdev;
+	priv->nr_ranges = get_dma_buf.nr_ranges;
+	priv->dma_ranges = dma_ranges;
+
+	ret = check_dma_ranges(priv, &dmabuf_size);
+	if (ret)
+		goto err_free_priv;
+
+	if (!vfio_device_try_get_registration(&vdev->vdev)) {
+		ret = -ENODEV;
+		goto err_free_priv;
+	}
+
+	exp_info.ops = &vfio_pci_dmabuf_ops;
+	exp_info.size = dmabuf_size;
+	exp_info.flags = get_dma_buf.open_flags;
+	exp_info.priv = priv;
+
+	priv->dmabuf = dma_buf_export(&exp_info);
+	if (IS_ERR(priv->dmabuf)) {
+		ret = PTR_ERR(priv->dmabuf);
+		goto err_dev_put;
+	}
+
+	/* dma_buf_put() now frees priv */
+	INIT_LIST_HEAD(&priv->dmabufs_elm);
+	down_write(&vdev->memory_lock);
+	dma_resv_lock(priv->dmabuf->resv, NULL);
+	priv->revoked = !__vfio_pci_memory_enabled(vdev);
+	list_add_tail(&priv->dmabufs_elm, &vdev->dmabufs);
+	dma_resv_unlock(priv->dmabuf->resv);
+	up_write(&vdev->memory_lock);
+
+	/*
+	 * dma_buf_fd() consumes the reference, when the file closes the dmabuf
+	 * will be released.
+	 */
+	return dma_buf_fd(priv->dmabuf, get_dma_buf.open_flags);
+
+err_dev_put:
+	vfio_device_put_registration(&vdev->vdev);
+err_free_priv:
+	kfree(dma_ranges);
+	kfree(priv);
+	return ret;
+}
+
+void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev, bool revoked)
+{
+	struct vfio_pci_dma_buf *priv;
+	struct vfio_pci_dma_buf *tmp;
+
+	lockdep_assert_held_write(&vdev->memory_lock);
+
+	list_for_each_entry_safe(priv, tmp, &vdev->dmabufs, dmabufs_elm) {
+		/*
+		 * Returns true if a reference was successfully obtained.
+		 * The caller must interlock with the dmabuf's release
+		 * function in some way, such as RCU, to ensure that this
+		 * is not called on freed memory.
+		 */
+		if (!get_file_rcu(&priv->dmabuf->file))
+			continue;
+
+		if (priv->revoked != revoked) {
+			dma_resv_lock(priv->dmabuf->resv, NULL);
+			priv->revoked = revoked;
+			dma_buf_move_notify(priv->dmabuf);
+			dma_resv_unlock(priv->dmabuf->resv);
+		}
+		dma_buf_put(priv->dmabuf);
+	}
+}
+
+void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev)
+{
+	struct vfio_pci_dma_buf *priv;
+	struct vfio_pci_dma_buf *tmp;
+
+	down_write(&vdev->memory_lock);
+	list_for_each_entry_safe(priv, tmp, &vdev->dmabufs, dmabufs_elm) {
+		if (!get_file_rcu(&priv->dmabuf->file))
+			continue;
+
+		dma_resv_lock(priv->dmabuf->resv, NULL);
+		list_del_init(&priv->dmabufs_elm);
+		priv->vdev = NULL;
+		priv->revoked = true;
+		dma_buf_move_notify(priv->dmabuf);
+		dma_resv_unlock(priv->dmabuf->resv);
+		vfio_device_put_registration(&vdev->vdev);
+		dma_buf_put(priv->dmabuf);
+	}
+	up_write(&vdev->memory_lock);
+}
diff --git a/drivers/vfio/pci/vfio_pci_priv.h b/drivers/vfio/pci/vfio_pci_priv.h
index a9972eacb293..6f3e8eafdc35 100644
--- a/drivers/vfio/pci/vfio_pci_priv.h
+++ b/drivers/vfio/pci/vfio_pci_priv.h
@@ -107,4 +107,27 @@ static inline bool vfio_pci_is_vga(struct pci_dev *pdev)
 	return (pdev->class >> 8) == PCI_CLASS_DISPLAY_VGA;
 }
 
+#ifdef CONFIG_DMA_SHARED_BUFFER
+int vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
+				  struct vfio_device_feature_dma_buf __user *arg,
+				  size_t argsz);
+void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev);
+void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev, bool revoked);
+#else
+static int
+vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
+			      struct vfio_device_feature_dma_buf __user *arg,
+			      size_t argsz)
+{
+	return -ENOTTY;
+}
+static inline void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev)
+{
+}
+static inline void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev,
+					 bool revoked)
+{
+}
+#endif
+
 #endif
diff --git a/include/linux/vfio_pci_core.h b/include/linux/vfio_pci_core.h
index fbb472dd99b3..da5d8955ae56 100644
--- a/include/linux/vfio_pci_core.h
+++ b/include/linux/vfio_pci_core.h
@@ -94,6 +94,7 @@ struct vfio_pci_core_device {
 	struct vfio_pci_core_device	*sriov_pf_core_dev;
 	struct notifier_block	nb;
 	struct rw_semaphore	memory_lock;
+	struct list_head	dmabufs;
 };
 
 /* Will be exported for vfio pci drivers usage */
diff --git a/include/uapi/linux/vfio.h b/include/uapi/linux/vfio.h
index 5764f315137f..9445fa36efd3 100644
--- a/include/uapi/linux/vfio.h
+++ b/include/uapi/linux/vfio.h
@@ -1468,6 +1468,31 @@ struct vfio_device_feature_bus_master {
 };
 #define VFIO_DEVICE_FEATURE_BUS_MASTER 10
 
+/**
+ * Upon VFIO_DEVICE_FEATURE_GET create a dma_buf fd for the
+ * regions selected.
+ *
+ * open_flags are the typical flags passed to open(2), eg O_RDWR, O_CLOEXEC,
+ * etc. offset/length specify a slice of the region to create the dmabuf from.
+ * nr_ranges is the total number of (P2P DMA) ranges that comprise the dmabuf.
+ *
+ * Return: The fd number on success, -1 and errno is set on failure.
+ */
+#define VFIO_DEVICE_FEATURE_DMA_BUF 11
+
+struct vfio_region_dma_range {
+	__u32	region_index;
+	__u32	__pad;
+	__u64	offset;
+	__u64	length;
+};
+
+struct vfio_device_feature_dma_buf {
+	__u32	open_flags;
+	__u32	nr_ranges;
+	struct vfio_region_dma_range dma_ranges[];
+};
+
 /* -------- API for Type1 VFIO IOMMU -------- */
 
 /**

---

## [6] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 05/30] fixup! vfio/pci: fix dma-buf revoke typo on reset*

Fixed the patch:

  vfio/pci: Allow MMIO regions to be exported through dma-buf

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/vfio_pci_config.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/drivers/vfio/pci/vfio_pci_config.c b/drivers/vfio/pci/vfio_pci_config.c
index efccbb2d2a42..7ac062bd5044 100644
--- a/drivers/vfio/pci/vfio_pci_config.c
+++ b/drivers/vfio/pci/vfio_pci_config.c
@@ -911,7 +911,7 @@ static int vfio_exp_config_write(struct vfio_pci_core_device *vdev, int pos,
 			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
 			if (__vfio_pci_memory_enabled(vdev))
-				vfio_pci_dma_buf_move(vdev, true);
+				vfio_pci_dma_buf_move(vdev, false);
 			up_write(&vdev->memory_lock);
 		}
 	}
@@ -996,7 +996,7 @@ static int vfio_af_config_write(struct vfio_pci_core_device *vdev, int pos,
 			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
 			if (__vfio_pci_memory_enabled(vdev))
-				vfio_pci_dma_buf_move(vdev, true);
+				vfio_pci_dma_buf_move(vdev, false);
 			up_write(&vdev->memory_lock);
 		}
 	}

---

## [7] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 06/30] HACK: vfio/pci: Support get_pfn() callback for dma-buf*

This is to support private device/MMMIO assignment, but is an
incomplete implementation as discussed. In this case, VFIO PCI act as
the exporter for MMIO regions and KVM is the importer. KVM imports the
dma-buf FD and gets MMIO pfn through dma_buf_ops.get_pfn(), then map
the pfn in KVM MMU. KVM should also react to dma-buf move notify, unmap
all pfns when VFIO revokes the MMIOs. I.e VFIO controls the lifetime of
the MMIOs.

Previously, KVM uses follow_pfn() to get the MMIO pfn. With dma-buf,
KVM no longer needs to firstly map the MMIOs to host page table. It
also solves the concern in Confidential Computing (CC) that host is not
allowed to have mapping to private resources owned by guest.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/vfio_pci_dmabuf.c | 34 ++++++++++++++++++++++++++++++
 1 file changed, 34 insertions(+)

diff --git a/drivers/vfio/pci/vfio_pci_dmabuf.c b/drivers/vfio/pci/vfio_pci_dmabuf.c
index a4c313ca5bda..cf9a90448856 100644
--- a/drivers/vfio/pci/vfio_pci_dmabuf.c
+++ b/drivers/vfio/pci/vfio_pci_dmabuf.c
@@ -174,6 +174,39 @@ static void vfio_pci_dma_buf_unmap(struct dma_buf_attachment *attachment,
 	kfree(sgt);
 }
 
+static int vfio_pci_dma_buf_get_pfn(struct dma_buf_attachment *attachment,
+				    pgoff_t pgoff, u64 *pfn, int *max_order)
+{
+	struct vfio_pci_dma_buf *priv = attachment->dmabuf->priv;
+	struct vfio_region_dma_range *dma_ranges = priv->dma_ranges;
+	u64 offset = pgoff << PAGE_SHIFT;
+	int i;
+
+	dma_resv_assert_held(priv->dmabuf->resv);
+
+	if (priv->revoked)
+		return -ENODEV;
+
+	if (offset >= priv->dmabuf->size)
+		return -EINVAL;
+
+	for (i = 0; i < priv->nr_ranges; i++) {
+		if (offset < dma_ranges[i].length)
+			break;
+
+		offset -= dma_ranges[i].length;
+	}
+
+	*pfn = PHYS_PFN(pci_resource_start(priv->vdev->pdev, dma_ranges[i].region_index) +
+			dma_ranges[i].offset + offset);
+
+	/* TODO: large page mapping is yet to be supported */
+	if (max_order)
+		*max_order = 0;
+
+	return 0;
+}
+
 static void vfio_pci_dma_buf_release(struct dma_buf *dmabuf)
 {
 	struct vfio_pci_dma_buf *priv = dmabuf->priv;
@@ -198,6 +231,7 @@ static const struct dma_buf_ops vfio_pci_dmabuf_ops = {
 	.unpin = vfio_pci_dma_buf_unpin,
 	.release = vfio_pci_dma_buf_release,
 	.unmap_dma_buf = vfio_pci_dma_buf_unmap,
+	.get_pfn = vfio_pci_dma_buf_get_pfn,
 };
 
 static int check_dma_ranges(struct vfio_pci_dma_buf *priv,

---

## [8] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 07/30] KVM: Support vfio_dmabuf backed MMIO region*

Extend KVM_SET_USER_MEMORY_REGION2 to support mapping vfio_dmabuf
backed MMIO region into a guest.

The main purpose of this change is for KVM to map MMIO resources
without firstly mapping into the host, similar to what is done in
guest_memfd. The immediate use case is for CoCo VMs to support private
MMIO.

Similar to private guest memory, private MMIO is also not intended to be
accessed by host. The host access to private MMIO would be rejected by
private devices (known as TDI in TDISP spec) and cause the TDI exit the
secure state. The further impact to the system may vary according to
device implementation. The TDISP spec doesn't mandate any error
reporting or logging, the TLP may be handled as an Unsupported Request,
or just be dropped. In my test environment, an AER NonFatalErr is
reported and no further impact. So from HW perspective, disallowing
host access to private MMIO is not that critical but nice to have.

But stick to find pfn via userspace mapping while allowing the pfn been
privately mapped conflicts with the private mapping concept. And it
virtually allows userspace to map any address as private. Before
fault in, KVM cannot distinguish if a userspace addr is for private
MMIO and safe to host access.

Rely on userspace mapping also means private MMIO mapping should follow
userspace mapping change via mmu_notifier. This conflicts with the
current design that mmu_notifier never impacts private mapping. It also
makes no sense to support mmu_notifier just for private MMIO, private
MMIO mapping should be fixed when CoCo-VM accepts the private MMIO, any
following mapping change without guest permission should be invalid.

So the choice here is to eliminate userspace mapping and switch to use
the FD based MMIO resources.

There is still need to switch the memory attribute (shared <-> private)
for private MMIO, when guest switches the device attribute between
shared & private. Unlike memory, MMIO region has only one physical
backend so it is a bit like in-place conversion, which for private
memory, requires much effort on how to invalidate user mapping when
converting to private. But for MMIO, it is expected that VMM never
needs to access assigned MMIO for feature emulation, so always disallow
userspace MMIO mapping and use FD based MMIO resources for 'private
capable' MMIO region.

The dma-buf is chosen as the FD based backend, it meets the need for KVM
to aquire the non-struct page memory that can still have lifetime
controlled by VFIO. It provides the option to disallow userspace mmap as
long as the exporter doesn't provide dma_buf_ops.mmap() callback. The
concern is it now just supports mapping into device's default_domain via
DMA APIs. Some clue I can found to extend dma-buf APIs for subsystems
like IOMMUFD [1] or KVM. The adding of dma_buf_get_pfn_unlocked() in this
series is for this purpose.

An alternative is VFIO provides a dedicated FD for KVM. But considering
IOMMUFD may use dma-buf for MMIO mapping [2], it is better to have a
unified export mechanism for the same purpose in VFIO.

Open: Currently store the dmabuf fd parameter in
kvm_userspace_memory_region2::guest_memfd. It may be confusing but avoids
introducing another API format for IOCTL(KVM_SET_USER_MEMORY_REGION3).

[1] https://lore.kernel.org/all/YwywgciH6BiWz4H1@nvidia.com/
[2] https://lore.kernel.org/kvm/14-v4-0de2f6c78ed0+9d1-iommufd_jgg@nvidia.com/

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 Documentation/virt/kvm/api.rst |   7 ++
 include/linux/kvm_host.h       |  18 +++++
 include/uapi/linux/kvm.h       |   1 +
 virt/kvm/Kconfig               |   6 ++
 virt/kvm/Makefile.kvm          |   1 +
 virt/kvm/kvm_main.c            |  32 +++++++--
 virt/kvm/kvm_mm.h              |  19 +++++
 virt/kvm/vfio_dmabuf.c         | 125 +++++++++++++++++++++++++++++++++
 8 files changed, 205 insertions(+), 4 deletions(-)
 create mode 100644 virt/kvm/vfio_dmabuf.c

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 47c7c3f92314..2962b0e30f81 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6307,6 +6307,13 @@ state.  At VM creation time, all memory is shared, i.e. the PRIVATE attribute
 is '0' for all gfns.  Userspace can control whether memory is shared/private by
 toggling KVM_MEMORY_ATTRIBUTE_PRIVATE via KVM_SET_MEMORY_ATTRIBUTES as needed.
 
+Userspace can set KVM_MEM_VFIO_DMABUF in flags to indicate the memory region is
+backed by a userspace unmappable dma_buf exported by VFIO. The backend resource
+is one piece of MMIO region of the device. The slot is unmappable so it is
+allowed to be converted to private. KVM binds the memory region to a given
+dma_buf fd range of [0, memory_size]. For now, the dma_buf fd is filled in
+'guest_memfd' field, and the guest_memfd_offset must be 0;
+
 S390:
 ^^^^^
 
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 291d49b9bf05..d16f47c3d008 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -612,6 +612,10 @@ struct kvm_memory_slot {
 		pgoff_t pgoff;
 	} gmem;
 #endif
+
+#ifdef CONFIG_KVM_VFIO_DMABUF
+	struct dma_buf_attachment *dmabuf_attach;
+#endif
 };
 
 static inline bool kvm_slot_can_be_private(const struct kvm_memory_slot *slot)
@@ -2571,4 +2575,18 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 				    struct kvm_pre_fault_memory *range);
 #endif
 
+#ifdef CONFIG_KVM_VFIO_DMABUF
+int kvm_vfio_dmabuf_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
+			    gfn_t gfn, kvm_pfn_t *pfn, int *max_order);
+#else
+static inline int kvm_vfio_dmabuf_get_pfn(struct kvm *kvm,
+					  struct kvm_memory_slot *slot,
+					  gfn_t gfn, kvm_pfn_t *pfn,
+					  int *max_order);
+{
+	KVM_BUG_ON(1, kvm);
+	return -EIO;
+}
+#endif
+
 #endif
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index b6ae8ad8934b..a4e05fe46918 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -51,6 +51,7 @@ struct kvm_userspace_memory_region2 {
 #define KVM_MEM_LOG_DIRTY_PAGES	(1UL << 0)
 #define KVM_MEM_READONLY	(1UL << 1)
 #define KVM_MEM_GUEST_MEMFD	(1UL << 2)
+#define KVM_MEM_VFIO_DMABUF	(1UL << 3)
 
 /* for KVM_IRQ_LINE */
 struct kvm_irq_level {
diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index 727b542074e7..9e6832dfa297 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -119,6 +119,7 @@ config KVM_PRIVATE_MEM
 config KVM_GENERIC_PRIVATE_MEM
        select KVM_GENERIC_MEMORY_ATTRIBUTES
        select KVM_PRIVATE_MEM
+       select KVM_VFIO_DMABUF
        bool
 
 config HAVE_KVM_ARCH_GMEM_PREPARE
@@ -128,3 +129,8 @@ config HAVE_KVM_ARCH_GMEM_PREPARE
 config HAVE_KVM_ARCH_GMEM_INVALIDATE
        bool
        depends on KVM_PRIVATE_MEM
+
+config KVM_VFIO_DMABUF
+       bool
+       select DMA_SHARED_BUFFER
+       select DMABUF_MOVE_NOTIFY
diff --git a/virt/kvm/Makefile.kvm b/virt/kvm/Makefile.kvm
index 724c89af78af..c08e98f13f65 100644
--- a/virt/kvm/Makefile.kvm
+++ b/virt/kvm/Makefile.kvm
@@ -13,3 +13,4 @@ kvm-$(CONFIG_HAVE_KVM_IRQ_ROUTING) += $(KVM)/irqchip.o
 kvm-$(CONFIG_HAVE_KVM_DIRTY_RING) += $(KVM)/dirty_ring.o
 kvm-$(CONFIG_HAVE_KVM_PFNCACHE) += $(KVM)/pfncache.o
 kvm-$(CONFIG_KVM_PRIVATE_MEM) += $(KVM)/guest_memfd.o
+kvm-$(CONFIG_KVM_VFIO_DMABUF) += $(KVM)/vfio_dmabuf.o
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index e85b33a92624..f2ee111038ef 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -957,6 +957,8 @@ static void kvm_free_memslot(struct kvm *kvm, struct kvm_memory_slot *slot)
 {
 	if (slot->flags & KVM_MEM_GUEST_MEMFD)
 		kvm_gmem_unbind(slot);
+	else if (slot->flags & KVM_MEM_VFIO_DMABUF)
+		kvm_vfio_dmabuf_unbind(slot);
 
 	kvm_destroy_dirty_bitmap(slot);
 
@@ -1529,13 +1531,19 @@ static void kvm_replace_memslot(struct kvm *kvm,
 static int check_memory_region_flags(struct kvm *kvm,
 				     const struct kvm_userspace_memory_region2 *mem)
 {
+	u32 private_mask = KVM_MEM_GUEST_MEMFD | KVM_MEM_VFIO_DMABUF;
+	u32 private_flag = mem->flags & private_mask;
 	u32 valid_flags = KVM_MEM_LOG_DIRTY_PAGES;
 
+	/* private flags are mutually exclusive. */
+	if (private_flag & (private_flag - 1))
+		return -EINVAL;
+
 	if (kvm_arch_has_private_mem(kvm))
-		valid_flags |= KVM_MEM_GUEST_MEMFD;
+		valid_flags |= private_flag;
 
 	/* Dirty logging private memory is not currently supported. */
-	if (mem->flags & KVM_MEM_GUEST_MEMFD)
+	if (private_flag)
 		valid_flags &= ~KVM_MEM_LOG_DIRTY_PAGES;
 
 	/*
@@ -1543,8 +1551,7 @@ static int check_memory_region_flags(struct kvm *kvm,
 	 * read-only memslots have emulated MMIO, not page fault, semantics,
 	 * and KVM doesn't allow emulated MMIO for private memory.
 	 */
-	if (kvm_arch_has_readonly_mem(kvm) &&
-	    !(mem->flags & KVM_MEM_GUEST_MEMFD))
+	if (kvm_arch_has_readonly_mem(kvm) && !private_flag)
 		valid_flags |= KVM_MEM_READONLY;
 
 	if (mem->flags & ~valid_flags)
@@ -2049,6 +2056,21 @@ static int kvm_set_memory_region(struct kvm *kvm,
 		r = kvm_gmem_bind(kvm, new, mem->guest_memfd, mem->guest_memfd_offset);
 		if (r)
 			goto out;
+	} else if (mem->flags & KVM_MEM_VFIO_DMABUF) {
+		if (mem->guest_memfd_offset) {
+			r = -EINVAL;
+			goto out;
+		}
+
+		/*
+		 * Open: May be confusing that store the dmabuf fd parameter in
+		 * kvm_userspace_memory_region2::guest_memfd. But this avoids
+		 * introducing another format for
+		 * IOCTL(KVM_SET_USER_MEMORY_REGIONX).
+		 */
+		r = kvm_vfio_dmabuf_bind(kvm, new, mem->guest_memfd);
+		if (r)
+			goto out;
 	}
 
 	r = kvm_set_memslot(kvm, old, new, change);
@@ -2060,6 +2082,8 @@ static int kvm_set_memory_region(struct kvm *kvm,
 out_unbind:
 	if (mem->flags & KVM_MEM_GUEST_MEMFD)
 		kvm_gmem_unbind(new);
+	else if (mem->flags & KVM_MEM_VFIO_DMABUF)
+		kvm_vfio_dmabuf_unbind(new);
 out:
 	kfree(new);
 	return r;
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index acef3f5c582a..faefc252c337 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -93,4 +93,23 @@ static inline void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 }
 #endif /* CONFIG_KVM_PRIVATE_MEM */
 
+#ifdef CONFIG_KVM_VFIO_DMABUF
+int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
+			 unsigned int fd);
+void kvm_vfio_dmabuf_unbind(struct kvm_memory_slot *slot);
+#else
+static inline int kvm_vfio_dmabuf_bind(struct kvm *kvm,
+				       struct kvm_memory_slot *slot,
+				       unsigned int fd);
+{
+	WARN_ON_ONCE(1);
+	return -EIO;
+}
+
+static inline void kvm_vfio_dmabuf_unbind(struct kvm_memory_slot *slot)
+{
+	WARN_ON_ONCE(1);
+}
+#endif /* CONFIG_KVM_VFIO_DMABUF */
+
 #endif /* __KVM_MM_H__ */
diff --git a/virt/kvm/vfio_dmabuf.c b/virt/kvm/vfio_dmabuf.c
new file mode 100644
index 000000000000..c427ab39c68a
--- /dev/null
+++ b/virt/kvm/vfio_dmabuf.c
@@ -0,0 +1,125 @@
+// SPDX-License-Identifier: GPL-2.0
+#include <linux/dma-buf.h>
+#include <linux/kvm_host.h>
+#include <linux/vfio.h>
+
+#include "kvm_mm.h"
+
+MODULE_IMPORT_NS("DMA_BUF");
+
+struct kvm_vfio_dmabuf {
+	struct kvm *kvm;
+	struct kvm_memory_slot *slot;
+};
+
+static void kv_dmabuf_move_notify(struct dma_buf_attachment *attach)
+{
+	struct kvm_vfio_dmabuf *kv_dmabuf = attach->importer_priv;
+	struct kvm_memory_slot *slot = kv_dmabuf->slot;
+	struct kvm *kvm = kv_dmabuf->kvm;
+	bool flush = false;
+
+	struct kvm_gfn_range gfn_range = {
+		.start = slot->base_gfn,
+		.end = slot->base_gfn + slot->npages,
+		.slot = slot,
+		.may_block = true,
+		.attr_filter = KVM_FILTER_PRIVATE | KVM_FILTER_SHARED,
+	};
+
+	KVM_MMU_LOCK(kvm);
+	kvm_mmu_invalidate_begin(kvm);
+	flush |= kvm_mmu_unmap_gfn_range(kvm, &gfn_range);
+	if (flush)
+		kvm_flush_remote_tlbs(kvm);
+
+	kvm_mmu_invalidate_end(kvm);
+	KVM_MMU_UNLOCK(kvm);
+}
+
+static const struct dma_buf_attach_ops kv_dmabuf_attach_ops = {
+	.allow_peer2peer = true,
+	.move_notify = kv_dmabuf_move_notify,
+};
+
+int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
+			 unsigned int fd)
+{
+	size_t size = slot->npages << PAGE_SHIFT;
+	struct dma_buf_attachment *attach;
+	struct kvm_vfio_dmabuf *kv_dmabuf;
+	struct dma_buf *dmabuf;
+	int ret;
+
+	dmabuf = dma_buf_get(fd);
+	if (IS_ERR(dmabuf))
+		return PTR_ERR(dmabuf);
+
+	if (size != dmabuf->size) {
+		ret = -EINVAL;
+		goto err_dmabuf;
+	}
+
+	kv_dmabuf = kzalloc(sizeof(*kv_dmabuf), GFP_KERNEL);
+	if (!kv_dmabuf) {
+		ret = -ENOMEM;
+		goto err_dmabuf;
+	}
+
+	kv_dmabuf->kvm = kvm;
+	kv_dmabuf->slot = slot;
+	attach = dma_buf_dynamic_attach(dmabuf, NULL, &kv_dmabuf_attach_ops,
+					kv_dmabuf);
+	if (IS_ERR(attach)) {
+		ret = PTR_ERR(attach);
+		goto err_kv_dmabuf;
+	}
+
+	slot->dmabuf_attach = attach;
+
+	return 0;
+
+err_kv_dmabuf:
+	kfree(kv_dmabuf);
+err_dmabuf:
+	dma_buf_put(dmabuf);
+	return ret;
+}
+
+void kvm_vfio_dmabuf_unbind(struct kvm_memory_slot *slot)
+{
+	struct dma_buf_attachment *attach = slot->dmabuf_attach;
+	struct kvm_vfio_dmabuf *kv_dmabuf;
+	struct dma_buf *dmabuf;
+
+	if (WARN_ON_ONCE(!attach))
+		return;
+
+	kv_dmabuf = attach->importer_priv;
+	dmabuf = attach->dmabuf;
+	dma_buf_detach(dmabuf, attach);
+	kfree(kv_dmabuf);
+	dma_buf_put(dmabuf);
+}
+
+/*
+ * The return value matters. If return -EFAULT, userspace will try to do
+ * page attribute (shared <-> private) conversion.
+ */
+int kvm_vfio_dmabuf_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
+			    gfn_t gfn, kvm_pfn_t *pfn, int *max_order)
+{
+	struct dma_buf_attachment *attach = slot->dmabuf_attach;
+	pgoff_t pgoff = gfn - slot->base_gfn;
+	int ret;
+
+	if (WARN_ON_ONCE(!attach))
+		return -EFAULT;
+
+	ret = dma_buf_get_pfn_unlocked(attach, pgoff, pfn, max_order);
+	if (ret)
+		return -EIO;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(kvm_vfio_dmabuf_get_pfn);

---

## [9] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 08/30] KVM: x86/mmu: Handle page fault for vfio_dmabuf backed MMIO*

Add support for resolving page faults on vfio_dmabuf backed MMIO. Now
only support setup KVM MMU mapping on shared roots, i.e. vfio_dmabuf
works for shared assigned devices.

Further work is to support private MMIO for private assigned
devices (known as TDI in TDISP spec).

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/kvm/mmu/mmu.c   | 16 ++++++++++++++++
 include/linux/kvm_host.h |  5 +++++
 2 files changed, 21 insertions(+)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 63bb77ee1bb1..40d33bd6b532 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4523,6 +4523,22 @@ static int __kvm_mmu_faultin_pfn(struct kvm_vcpu *vcpu,
 	if (fault->is_private)
 		return kvm_mmu_faultin_pfn_private(vcpu, fault);
 
+	/* vfio_dmabuf slot is also applicable for shared mapping */
+	if (kvm_slot_is_vfio_dmabuf(fault->slot)) {
+		int max_order, r;
+
+		r = kvm_vfio_dmabuf_get_pfn(vcpu->kvm, fault->slot, fault->gfn,
+					    &fault->pfn, &max_order);
+		if (r)
+			return r;
+
+		fault->max_level = min(kvm_max_level_for_order(max_order),
+				       fault->max_level);
+		fault->map_writable = !(fault->slot->flags & KVM_MEM_READONLY);
+
+		return RET_PF_CONTINUE;
+	}
+
 	foll |= FOLL_NOWAIT;
 	fault->pfn = __kvm_faultin_pfn(fault->slot, fault->gfn, foll,
 				       &fault->map_writable, &fault->refcounted_page);
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index d16f47c3d008..b850d3cff83c 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -623,6 +623,11 @@ static inline bool kvm_slot_can_be_private(const struct kvm_memory_slot *slot)
 	return slot && (slot->flags & KVM_MEM_GUEST_MEMFD);
 }
 
+static inline bool kvm_slot_is_vfio_dmabuf(const struct kvm_memory_slot *slot)
+{
+	return slot && (slot->flags & KVM_MEM_VFIO_DMABUF);
+}
+
 static inline bool kvm_slot_dirty_track_enabled(const struct kvm_memory_slot *slot)
 {
 	return slot->flags & KVM_MEM_LOG_DIRTY_PAGES;

---

## [10] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 09/30] KVM: x86/mmu: Handle page fault for private MMIO*

Add support for resolving page faults on private MMIO. This is part of
the effort to enable private assigned devices (known as TDI in TDISP
spec).

Private MMIOs are set to KVM as vfio_dmabuf typed memory slot, which is
another type of can-be-private memory slot just like the gmem slot.
Like gmem slot, KVM needs to map its GFN as shared or private based on
the current state of the GFN's memory attribute. When page fault
happens for private MMIO but private <-> shared conversion is needed,
KVM still exits to userspace with exit reason KVM_EXIT_MEMORY_FAULT and
toggles KVM_MEMORY_EXIT_FLAG_PRIVATE. Unlike gmem slot, vfio_dmabuf
slot has only one backend MMIO resource, the switching of GFN's
attribute won't change the way of getting PFN, the vfio_dmabuf specific
way, kvm_vfio_dmabuf_get_pfn().

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/kvm/mmu/mmu.c   | 9 +++++++--
 include/linux/kvm_host.h | 2 +-
 2 files changed, 8 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 40d33bd6b532..547fb645692b 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4501,8 +4501,13 @@ static int kvm_mmu_faultin_pfn_private(struct kvm_vcpu *vcpu,
 		return -EFAULT;
 	}
 
-	r = kvm_gmem_get_pfn(vcpu->kvm, fault->slot, fault->gfn, &fault->pfn,
-			     &fault->refcounted_page, &max_order);
+	if (kvm_slot_is_vfio_dmabuf(fault->slot))
+		r = kvm_vfio_dmabuf_get_pfn(vcpu->kvm, fault->slot, fault->gfn,
+					    &fault->pfn, &max_order);
+	else
+		r = kvm_gmem_get_pfn(vcpu->kvm, fault->slot, fault->gfn,
+				     &fault->pfn, &fault->refcounted_page,
+				     &max_order);
 	if (r) {
 		kvm_mmu_prepare_memory_fault_exit(vcpu, fault);
 		return r;
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index b850d3cff83c..dd9c876374b8 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -620,7 +620,7 @@ struct kvm_memory_slot {
 
 static inline bool kvm_slot_can_be_private(const struct kvm_memory_slot *slot)
 {
-	return slot && (slot->flags & KVM_MEM_GUEST_MEMFD);
+	return slot && (slot->flags & (KVM_MEM_GUEST_MEMFD | KVM_MEM_VFIO_DMABUF));
 }
 
 static inline bool kvm_slot_is_vfio_dmabuf(const struct kvm_memory_slot *slot)

---

## [11] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 10/30] vfio/pci: Export vfio dma-buf specific info for importers*

Export vfio dma-buf specific info by attaching vfio_dma_buf_data in
struct dma_buf::priv. Provide a helper vfio_dma_buf_get_data() for
importers to fetch these data. Exporters identify VFIO dma-buf by
successfully getting these data.

VFIO dma-buf supports disabling host access to these exported MMIO
regions when the device is converted to private. Exporters like KVM
need to identify this type of dma-buf to decide if it is good to use.
KVM only allows host unaccessible MMIO regions been mapped in private
roots.

Export struct kvm * handler attached to the vfio device. This
allows KVM to do another sanity check. MMIO should only be assigned to
a CoCo VM if its owner device is already assigned to the same VM.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/vfio_pci_dmabuf.c | 18 ++++++++++++++++++
 include/linux/vfio.h               | 18 ++++++++++++++++++
 2 files changed, 36 insertions(+)

diff --git a/drivers/vfio/pci/vfio_pci_dmabuf.c b/drivers/vfio/pci/vfio_pci_dmabuf.c
index cf9a90448856..4011545db3ad 100644
--- a/drivers/vfio/pci/vfio_pci_dmabuf.c
+++ b/drivers/vfio/pci/vfio_pci_dmabuf.c
@@ -10,6 +10,8 @@
 MODULE_IMPORT_NS("DMA_BUF");
 
 struct vfio_pci_dma_buf {
+	struct vfio_dma_buf_data export_data;
+
 	struct dma_buf *dmabuf;
 	struct vfio_pci_core_device *vdev;
 	struct list_head dmabufs_elm;
@@ -300,6 +302,8 @@ int vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
 	priv->nr_ranges = get_dma_buf.nr_ranges;
 	priv->dma_ranges = dma_ranges;
 
+	priv->export_data.kvm = vdev->vdev.kvm;
+
 	ret = check_dma_ranges(priv, &dmabuf_size);
 	if (ret)
 		goto err_free_priv;
@@ -391,3 +395,17 @@ void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev)
 	}
 	up_write(&vdev->memory_lock);
 }
+
+/*
+ * Only vfio/pci implements this, so put the helper here for now.
+ */
+struct vfio_dma_buf_data *vfio_dma_buf_get_data(struct dma_buf *dmabuf)
+{
+	struct vfio_pci_dma_buf *priv = dmabuf->priv;
+
+	if (dmabuf->ops != &vfio_pci_dmabuf_ops)
+		return ERR_PTR(-EINVAL);
+
+	return &priv->export_data;
+}
+EXPORT_SYMBOL_GPL(vfio_dma_buf_get_data);
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index ba65bbdffd0b..d521d2c01a92 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -9,6 +9,7 @@
 #define VFIO_H
 
 
+#include <linux/dma-buf.h>
 #include <linux/iommu.h>
 #include <linux/mm.h>
 #include <linux/workqueue.h>
@@ -383,4 +384,21 @@ int vfio_virqfd_enable(void *opaque, int (*handler)(void *, void *),
 void vfio_virqfd_disable(struct virqfd **pvirqfd);
 void vfio_virqfd_flush_thread(struct virqfd **pvirqfd);
 
+/*
+ * DMA-buf - generic
+ */
+struct vfio_dma_buf_data {
+	struct kvm *kvm;
+};
+
+#if IS_ENABLED(CONFIG_DMA_SHARED_BUFFER) && IS_ENABLED(CONFIG_VFIO_PCI_CORE)
+struct vfio_dma_buf_data *vfio_dma_buf_get_data(struct dma_buf *dmabuf);
+#else
+static inline
+struct vfio_dma_buf_data *vfio_dma_buf_get_data(struct dma_buf *dmabuf)
+{
+	return NULL;
+}
+#endif
+
 #endif /* VFIO_H */

---

## [12] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 11/30] KVM: vfio_dmabuf: Fetch VFIO specific dma-buf data for sanity check*

Fetch VFIO specific dma-buf data to see if the dma-buf is eligible to
be assigned to CoCo VM as private MMIO.

KVM expects host unaccessible MMIO regions been mapped in private
roots. So need to identify VFIO dma-buf by successfully getting VFIO
specific dma-buf data. VFIO dma-buf also provides the struct kvm *kvm
handler for KVM to check if the owner device of the MMIO region is
already assigned to the same CoCo VM.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 virt/kvm/vfio_dmabuf.c | 26 ++++++++++++++++++++++++++
 1 file changed, 26 insertions(+)

diff --git a/virt/kvm/vfio_dmabuf.c b/virt/kvm/vfio_dmabuf.c
index c427ab39c68a..ef695039402f 100644
--- a/virt/kvm/vfio_dmabuf.c
+++ b/virt/kvm/vfio_dmabuf.c
@@ -12,6 +12,22 @@ struct kvm_vfio_dmabuf {
 	struct kvm_memory_slot *slot;
 };
 
+static struct vfio_dma_buf_data *kvm_vfio_dma_buf_get_data(struct dma_buf *dmabuf)
+{
+	struct vfio_dma_buf_data *(*fn)(struct dma_buf *dmabuf);
+	struct vfio_dma_buf_data *ret;
+
+	fn = symbol_get(vfio_dma_buf_get_data);
+	if (!fn)
+		return ERR_PTR(-ENOENT);
+
+	ret = fn(dmabuf);
+
+	symbol_put(vfio_dma_buf_get_data);
+
+	return ret;
+}
+
 static void kv_dmabuf_move_notify(struct dma_buf_attachment *attach)
 {
 	struct kvm_vfio_dmabuf *kv_dmabuf = attach->importer_priv;
@@ -48,6 +64,7 @@ int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	size_t size = slot->npages << PAGE_SHIFT;
 	struct dma_buf_attachment *attach;
 	struct kvm_vfio_dmabuf *kv_dmabuf;
+	struct vfio_dma_buf_data *data;
 	struct dma_buf *dmabuf;
 	int ret;
 
@@ -60,6 +77,15 @@ int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		goto err_dmabuf;
 	}
 
+	data = kvm_vfio_dma_buf_get_data(dmabuf);
+	if (IS_ERR(data))
+		goto err_dmabuf;
+
+	if (data->kvm != kvm) {
+		ret = -EINVAL;
+		goto err_dmabuf;
+	}
+
 	kv_dmabuf = kzalloc(sizeof(*kv_dmabuf), GFP_KERNEL);
 	if (!kv_dmabuf) {
 		ret = -ENOMEM;

---

## [13] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 12/30] iommufd/device: Associate a kvm pointer to iommufd_device*

From: Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>

Add a struct kvm * to iommufd_device_bind() fn and associate it
with idev if bind is successful.

Signed-off-by: Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>
Reviewed-by: Jason Gunthorpe <jgg@nvidia.com>

---
This patch and next Shameer's patch are part of the series:

  https://lore.kernel.org/all/20250319173202.78988-3-shameerali.kolothum.thodi@huawei.com/
---
 drivers/iommu/iommufd/device.c          | 5 ++++-
 drivers/iommu/iommufd/iommufd_private.h | 2 ++
 drivers/vfio/iommufd.c                  | 2 +-
 include/linux/iommufd.h                 | 4 +++-
 4 files changed, 10 insertions(+), 3 deletions(-)

diff --git a/drivers/iommu/iommufd/device.c b/drivers/iommu/iommufd/device.c
index 2111bad72c72..37ef6bec2009 100644
--- a/drivers/iommu/iommufd/device.c
+++ b/drivers/iommu/iommufd/device.c
@@ -152,6 +152,7 @@ void iommufd_device_destroy(struct iommufd_object *obj)
  * iommufd_device_bind - Bind a physical device to an iommu fd
  * @ictx: iommufd file descriptor
  * @dev: Pointer to a physical device struct
+ * @kvm: Pointer to struct kvm if device belongs to a KVM VM
  * @id: Output ID number to return to userspace for this device
  *
  * A successful bind establishes an ownership over the device and returns
@@ -165,7 +166,8 @@ void iommufd_device_destroy(struct iommufd_object *obj)
  * The caller must undo this with iommufd_device_unbind()
  */
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
-					   struct device *dev, u32 *id)
+					   struct device *dev, struct kvm *kvm,
+					   u32 *id)
 {
 	struct iommufd_device *idev;
 	struct iommufd_group *igroup;
@@ -215,6 +217,7 @@ struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
 	if (!iommufd_selftest_is_mock_dev(dev))
 		iommufd_ctx_get(ictx);
 	idev->dev = dev;
+	idev->kvm = kvm;
 	idev->enforce_cache_coherency =
 		device_iommu_capable(dev, IOMMU_CAP_ENFORCE_CACHE_COHERENCY);
 	/* The calling driver is a user until iommufd_device_unbind() */
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 80e8c76d25f2..297e4e2a12d1 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -424,6 +424,8 @@ struct iommufd_device {
 	struct list_head group_item;
 	/* always the physical device */
 	struct device *dev;
+	/* ..and kvm if available */
+	struct kvm *kvm;
 	bool enforce_cache_coherency;
 	/* protect iopf_enabled counter */
 	struct mutex iopf_lock;
diff --git a/drivers/vfio/iommufd.c b/drivers/vfio/iommufd.c
index c8c3a2d53f86..3441d24538a8 100644
--- a/drivers/vfio/iommufd.c
+++ b/drivers/vfio/iommufd.c
@@ -115,7 +115,7 @@ int vfio_iommufd_physical_bind(struct vfio_device *vdev,
 {
 	struct iommufd_device *idev;
 
-	idev = iommufd_device_bind(ictx, vdev->dev, out_device_id);
+	idev = iommufd_device_bind(ictx, vdev->dev, vdev->kvm, out_device_id);
 	if (IS_ERR(idev))
 		return PTR_ERR(idev);
 	vdev->iommufd_device = idev;
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 34b6e6ca4bfa..2b2d6095309c 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -24,6 +24,7 @@ struct iommufd_ctx;
 struct iommufd_device;
 struct iommufd_viommu_ops;
 struct page;
+struct kvm;
 
 enum iommufd_object_type {
 	IOMMUFD_OBJ_NONE,
@@ -52,7 +53,8 @@ struct iommufd_object {
 };
 
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
-					   struct device *dev, u32 *id);
+					   struct device *dev, struct kvm *kvm,
+					   u32 *id);
 void iommufd_device_unbind(struct iommufd_device *idev);
 
 int iommufd_device_attach(struct iommufd_device *idev, ioasid_t pasid,

---

## [14] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 13/30] fixup! iommufd/selftest: Sync iommufd_device_bind() change to selftest*

Sync up the additional struct kvm * parameter.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/iommufd/selftest.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/drivers/iommu/iommufd/selftest.c b/drivers/iommu/iommufd/selftest.c
index 18d9a216eb30..d070807757f2 100644
--- a/drivers/iommu/iommufd/selftest.c
+++ b/drivers/iommu/iommufd/selftest.c
@@ -992,7 +992,7 @@ static int iommufd_test_mock_domain(struct iommufd_ucmd *ucmd,
 		goto out_sobj;
 	}
 
-	idev = iommufd_device_bind(ucmd->ictx, &sobj->idev.mock_dev->dev,
+	idev = iommufd_device_bind(ucmd->ictx, &sobj->idev.mock_dev->dev, NULL,
 				   &idev_id);
 	if (IS_ERR(idev)) {
 		rc = PTR_ERR(idev);

---

## [15] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 14/30] iommu/arm-smmu-v3-iommufd: Pass in kvm pointer to viommu_alloc*

From: Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>

No functional changes.

This will be used in a later patch to add support to use
KVM VMID in ARM SMMUv3 s2 stage configuration.

Signed-off-by: Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>
---
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c | 1 +
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h         | 1 +
 drivers/iommu/iommufd/viommu.c                      | 3 ++-
 include/linux/iommu.h                               | 4 +++-
 4 files changed, 7 insertions(+), 2 deletions(-)

diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c
index e4fd8d522af8..5ee2b24e7bcf 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c
@@ -383,6 +383,7 @@ static const struct iommufd_viommu_ops arm_vsmmu_ops = {
 };
 
 struct iommufd_viommu *arm_vsmmu_alloc(struct device *dev,
+				       struct kvm *kvm,
 				       struct iommu_domain *parent,
 				       struct iommufd_ctx *ictx,
 				       unsigned int viommu_type)
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
index dd1ad56ce863..94b695b60c26 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
@@ -1060,6 +1060,7 @@ struct arm_vsmmu {
 #if IS_ENABLED(CONFIG_ARM_SMMU_V3_IOMMUFD)
 void *arm_smmu_hw_info(struct device *dev, u32 *length, u32 *type);
 struct iommufd_viommu *arm_vsmmu_alloc(struct device *dev,
+				       struct kvm *kvm,
 				       struct iommu_domain *parent,
 				       struct iommufd_ctx *ictx,
 				       unsigned int viommu_type);
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 01df2b985f02..488905989b7c 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -47,7 +47,8 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 		goto out_put_hwpt;
 	}
 
-	viommu = ops->viommu_alloc(idev->dev, hwpt_paging->common.domain,
+	viommu = ops->viommu_alloc(idev->dev, idev->kvm,
+				   hwpt_paging->common.domain,
 				   ucmd->ictx, cmd->type);
 	if (IS_ERR(viommu)) {
 		rc = PTR_ERR(viommu);
diff --git a/include/linux/iommu.h b/include/linux/iommu.h
index ccce8a751e2a..3675a5a6cea0 100644
--- a/include/linux/iommu.h
+++ b/include/linux/iommu.h
@@ -47,6 +47,7 @@ struct iommufd_ctx;
 struct iommufd_viommu;
 struct msi_desc;
 struct msi_msg;
+struct kvm;
 
 #define IOMMU_FAULT_PERM_READ	(1 << 0) /* read */
 #define IOMMU_FAULT_PERM_WRITE	(1 << 1) /* write */
@@ -661,7 +662,8 @@ struct iommu_ops {
 	int (*def_domain_type)(struct device *dev);
 
 	struct iommufd_viommu *(*viommu_alloc)(
-		struct device *dev, struct iommu_domain *parent_domain,
+		struct device *dev, struct kvm *kvm,
+		struct iommu_domain *parent_domain,
 		struct iommufd_ctx *ictx, unsigned int viommu_type);
 
 	const struct iommu_domain_ops *default_domain_ops;

---

## [16] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 15/30] fixup: iommu/selftest: Sync .viommu_alloc() change to selftest*

Sync up the additional struct kvm * parameter.

Signed-off-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/iommufd/selftest.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/drivers/iommu/iommufd/selftest.c b/drivers/iommu/iommufd/selftest.c
index d070807757f2..90e6d1d3aa62 100644
--- a/drivers/iommu/iommufd/selftest.c
+++ b/drivers/iommu/iommufd/selftest.c
@@ -734,6 +734,7 @@ static struct iommufd_viommu_ops mock_viommu_ops = {
 };
 
 static struct iommufd_viommu *mock_viommu_alloc(struct device *dev,
+						struct kvm *kvm,
 						struct iommu_domain *domain,
 						struct iommufd_ctx *ictx,
 						unsigned int viommu_type)

---

## [17] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 16/30] iommufd/viommu: track the kvm pointer & its refcount in viommu core*

Track the kvm pointer and its refcount in viommu core. The kvm pointer
will be used later to support TSM Bind feature, which tells the secure
firmware the connection between a vPCI device and a CoCo VM.

There is existing need to reference kvm pointer in viommu [1], but in
that series kvm pointer is used & tracked in platform iommu drivers.
While in Confidential Computing (CC) case, viommu should manage a
generic routine for TSM Bind, i.e. call pci_tsm_bind(pdev, kvm, tdi_id)
So it is better the viommu core keeps and tracks the kvm pointer.

[1] https://lore.kernel.org/all/20250319173202.78988-5-shameerali.kolothum.thodi@huawei.com/

Signed-off-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/iommufd/viommu.c | 62 ++++++++++++++++++++++++++++++++++
 include/linux/iommufd.h        |  3 ++
 2 files changed, 65 insertions(+)

diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 488905989b7c..2fcef3f8d1a5 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -1,8 +1,68 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /* Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES
  */
+#if IS_ENABLED(CONFIG_KVM)
+#include <linux/kvm_host.h>
+#endif
+
 #include "iommufd_private.h"
 
+#if IS_ENABLED(CONFIG_KVM)
+static void viommu_get_kvm_safe(struct iommufd_viommu *viommu, struct kvm *kvm)
+{
+	void (*pfn)(struct kvm *kvm);
+	bool (*fn)(struct kvm *kvm);
+	bool ret;
+
+	if (!kvm)
+		return;
+
+	pfn = symbol_get(kvm_put_kvm);
+	if (WARN_ON(!pfn))
+		return;
+
+	fn = symbol_get(kvm_get_kvm_safe);
+	if (WARN_ON(!fn)) {
+		symbol_put(kvm_put_kvm);
+		return;
+	}
+
+	ret = fn(kvm);
+	symbol_put(kvm_get_kvm_safe);
+	if (!ret) {
+		symbol_put(kvm_put_kvm);
+		return;
+	}
+
+	viommu->put_kvm = pfn;
+	viommu->kvm = kvm;
+}
+
+static void viommu_put_kvm(struct iommufd_viommu *viommu)
+{
+	if (!viommu->kvm)
+		return;
+
+	if (WARN_ON(!viommu->put_kvm))
+		goto clear;
+
+	viommu->put_kvm(viommu->kvm);
+	viommu->put_kvm = NULL;
+	symbol_put(kvm_put_kvm);
+
+clear:
+	viommu->kvm = NULL;
+}
+#else
+static void viommu_get_kvm_safe(struct iommufd_viommu *viommu, struct kvm *kvm)
+{
+}
+
+static void viommu_put_kvm(struct iommufd_viommu *viommu)
+{
+}
+#endif
+
 void iommufd_viommu_destroy(struct iommufd_object *obj)
 {
 	struct iommufd_viommu *viommu =
@@ -10,6 +70,7 @@ void iommufd_viommu_destroy(struct iommufd_object *obj)
 
 	if (viommu->ops && viommu->ops->destroy)
 		viommu->ops->destroy(viommu);
+	viommu_put_kvm(viommu);
 	refcount_dec(&viommu->hwpt->common.obj.users);
 	xa_destroy(&viommu->vdevs);
 }
@@ -68,6 +129,7 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	 * on its own.
 	 */
 	viommu->iommu_dev = __iommu_get_iommu_dev(idev->dev);
+	viommu_get_kvm_safe(viommu, idev->kvm);
 
 	cmd->out_viommu_id = viommu->obj.id;
 	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 2b2d6095309c..2712421802b9 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -104,6 +104,9 @@ struct iommufd_viommu {
 	struct rw_semaphore veventqs_rwsem;
 
 	unsigned int type;
+
+	struct kvm *kvm;
+	void (*put_kvm)(struct kvm *kvm);
 };
 
 /**

---

## [18] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 17/30] iommufd/device: Add TSM Bind/Unbind for TIO support*

Add new kAPIs against iommufd_device to support TSM Bind/Unbind
commands issued by CoCo-VM. The TSM bind means VMM does all
preparations for private device assignement, lock down the device by
transiting it to TDISP CONFIG_LOCKED or RUN state (when in RUN state,
TSM could still block any accessing to/from device), so that the device
is ready for attestation by CoCo-VM.

The interfaces are added against IOMMUFD because IOMMUFD builds several
abstract objects applicable for private device assignment, e.g. viommu
for secure iommu & kvm, vdevice for vBDF. IOMMUFD links them up to
finish all configurations required by secure firmware. That also means
TSM Bind interface should be called after viommu & vdevice allocation.

Suggested-by: Jason Gunthorpe <jgg@nvidia.com>
Originally-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/iommufd/device.c          | 84 +++++++++++++++++++++++++
 drivers/iommu/iommufd/iommufd_private.h |  6 ++
 drivers/iommu/iommufd/viommu.c          | 44 +++++++++++++
 include/linux/iommufd.h                 |  3 +
 4 files changed, 137 insertions(+)

diff --git a/drivers/iommu/iommufd/device.c b/drivers/iommu/iommufd/device.c
index 37ef6bec2009..984780c66ab2 100644
--- a/drivers/iommu/iommufd/device.c
+++ b/drivers/iommu/iommufd/device.c
@@ -3,6 +3,7 @@
  */
 #include <linux/iommu.h>
 #include <linux/iommufd.h>
+#include <linux/pci.h>
 #include <linux/pci-ats.h>
 #include <linux/slab.h>
 #include <uapi/linux/iommufd.h>
@@ -1561,3 +1562,86 @@ int iommufd_get_hw_info(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &idev->obj);
 	return rc;
 }
+
+/**
+ * iommufd_device_tsm_bind - Move a device to TSM Bind state
+ * @idev: device to attach
+ * @vdev_id: Input a IOMMUFD_OBJ_VDEVICE
+ *
+ * This configures for device Confidential Computing(CC), and moves the device
+ * to the TSM Bind state. Once this completes the device is locked down (TDISP
+ * CONFIG_LOCKED or RUN), waiting for guest's attestation.
+ *
+ * This function is undone by calling iommufd_device_tsm_unbind().
+ */
+int iommufd_device_tsm_bind(struct iommufd_device *idev, u32 vdevice_id)
+{
+	struct iommufd_vdevice *vdev;
+	int rc;
+
+	if (!dev_is_pci(idev->dev))
+		return -ENODEV;
+
+	vdev = container_of(iommufd_get_object(idev->ictx, vdevice_id, IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	if (vdev->dev != idev->dev) {
+		rc = -EINVAL;
+		goto out_put_vdev;
+	}
+
+	mutex_lock(&idev->igroup->lock);
+	if (idev->vdev) {
+		rc = -EEXIST;
+		goto out_unlock;
+	}
+
+	rc = iommufd_vdevice_tsm_bind(vdev);
+	if (rc)
+		goto out_unlock;
+
+	idev->vdev = vdev;
+	refcount_inc(&vdev->obj.users);
+	mutex_unlock(&idev->igroup->lock);
+
+	/*
+	 * Pairs with iommufd_device_tsm_unbind() - catches caller bugs attempting
+	 * to destroy a bound device.
+	 */
+	refcount_inc(&idev->obj.users);
+	goto out_put_vdev;
+
+out_unlock:
+	mutex_unlock(&idev->igroup->lock);
+out_put_vdev:
+	iommufd_put_object(idev->ictx, &vdev->obj);
+	return rc;
+}
+EXPORT_SYMBOL_NS_GPL(iommufd_device_tsm_bind, "IOMMUFD");
+
+/**
+ * iommufd_device_tsm_unbind - Move a device out of TSM bind state
+ * @idev: device to detach
+ *
+ * Undo iommufd_device_tsm_bind(). This removes all Confidential Computing
+ * configurations, Once this completes the device is unlocked (TDISP
+ * CONFIG_UNLOCKED).
+ */
+void iommufd_device_tsm_unbind(struct iommufd_device *idev)
+{
+	mutex_lock(&idev->igroup->lock);
+	if (!idev->vdev) {
+		mutex_unlock(&idev->igroup->lock);
+		return;
+	}
+
+	iommufd_vdevice_tsm_unbind(idev->vdev);
+	refcount_dec(&idev->vdev->obj.users);
+	idev->vdev = NULL;
+	mutex_unlock(&idev->igroup->lock);
+
+	refcount_dec(&idev->obj.users);
+}
+EXPORT_SYMBOL_NS_GPL(iommufd_device_tsm_unbind, "IOMMUFD");
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 297e4e2a12d1..29af8616e4aa 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -430,6 +430,7 @@ struct iommufd_device {
 	/* protect iopf_enabled counter */
 	struct mutex iopf_lock;
 	unsigned int iopf_enabled;
+	struct iommufd_vdevice *vdev;
 };
 
 static inline struct iommufd_device *
@@ -615,8 +616,13 @@ struct iommufd_vdevice {
 	struct iommufd_viommu *viommu;
 	struct device *dev;
 	u64 id; /* per-vIOMMU virtual ID */
+	struct mutex tsm_lock;
+	bool tsm_bound;
 };
 
+int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev);
+void iommufd_vdevice_tsm_unbind(struct iommufd_vdevice *vdev);
+
 #ifdef CONFIG_IOMMUFD_TEST
 int iommufd_test(struct iommufd_ucmd *ucmd);
 void iommufd_selftest_destroy(struct iommufd_object *obj);
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 2fcef3f8d1a5..296143e21368 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -4,6 +4,7 @@
 #if IS_ENABLED(CONFIG_KVM)
 #include <linux/kvm_host.h>
 #endif
+#include <linux/pci-tsm.h>
 
 #include "iommufd_private.h"
 
@@ -193,11 +194,13 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 		goto out_put_idev;
 	}
 
+	vdev->ictx = ucmd->ictx; //This is a unrelated fix for vdevice alloc
 	vdev->id = virt_id;
 	vdev->dev = idev->dev;
 	get_device(idev->dev);
 	vdev->viommu = viommu;
 	refcount_inc(&viommu->obj.users);
+	mutex_init(&vdev->tsm_lock);
 
 	curr = xa_cmpxchg(&viommu->vdevs, virt_id, NULL, vdev, GFP_KERNEL);
 	if (curr) {
@@ -220,3 +223,44 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &viommu->obj);
 	return rc;
 }
+
+int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev)
+{
+	struct kvm *kvm;
+	int rc;
+
+	mutex_lock(&vdev->tsm_lock);
+	if (vdev->tsm_bound) {
+		rc = -EEXIST;
+		goto out_unlock;
+	}
+
+	kvm = vdev->viommu->kvm;
+	if (!kvm) {
+		rc = -ENOENT;
+		goto out_unlock;
+	}
+
+	rc = pci_tsm_bind(to_pci_dev(vdev->dev), kvm, vdev->id);
+	if (rc)
+		goto out_unlock;
+
+	vdev->tsm_bound = true;
+
+out_unlock:
+	mutex_unlock(&vdev->tsm_lock);
+	return rc;
+}
+
+void iommufd_vdevice_tsm_unbind(struct iommufd_vdevice *vdev)
+{
+	mutex_lock(&vdev->tsm_lock);
+	if (!vdev->tsm_bound)
+		goto out_unlock;
+
+	pci_tsm_unbind(to_pci_dev(vdev->dev));
+	vdev->tsm_bound = false;
+
+out_unlock:
+	mutex_unlock(&vdev->tsm_lock);
+}
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 2712421802b9..5f9a286232ac 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -63,6 +63,9 @@ int iommufd_device_replace(struct iommufd_device *idev, ioasid_t pasid,
 			   u32 *pt_id);
 void iommufd_device_detach(struct iommufd_device *idev, ioasid_t pasid);
 
+int iommufd_device_tsm_bind(struct iommufd_device *idev, u32 vdevice_id);
+void iommufd_device_tsm_unbind(struct iommufd_device *idev);
+
 struct iommufd_ctx *iommufd_device_to_ictx(struct iommufd_device *idev);
 u32 iommufd_device_to_id(struct iommufd_device *idev);

---

## [19] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 18/30] iommufd/viommu: Add trusted IOMMU configuration handlers for vdev*

Add handlers for setting up/removing trusted IOMMU configurations
against vdevice. IOMMUFD calls these handlers on TSM bind/unbind. Most
vendors extend the trusted IOMMU engine for private device assignment,
thus require extra IOMMU configuration for TSM bind. E.g. Intel TDX
Connect requires host to build extra trusted Device Conext Table
entries (but not present), while AMD requires to clear Domain-ID on
non-secure DTE.

Existing DMA setup flow against IOMMUFD are driven by userspace, usually
start with allocating a domain, then attach the domain to the device.
While trusted DMA setup is embedded in TSM bind/unbind() IOCTLs. This is
because platform secure firmwares have various configuration
enforcements for trusted. E.g. Intel TDX Connect enforces trusted IOPT
detach after TDI STOP but before TDI metadata free. Using coarser uAPIs
like TSM bind/unbind that wrap all trusted configurations prevent these
low level complexities propagating to userspace.

Coarser uAPI means userspace lose the flexibility to attach different
domains to trusted part of the device. Also it cannot operate on the
trusted domain. That seems not a problem cause VMM is out of the TCB so
secure firmware either disallows VMM touching the trusted domain or only
allows a fixed configuration set. E.g. TDX Connect enforces all assigned
devices in the same VM must share the same trusted domain. It also
specifies every value of the trusted Context Table entries. So just
setup everything for trusted DMA in IOMMU driver is a reasonable choice.

OPEN: Should these handlers be viommu ops or vdevice ops?

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/iommufd/iommufd_private.h |  1 +
 drivers/iommu/iommufd/viommu.c          | 41 ++++++++++++++++++++++++-
 include/linux/iommufd.h                 |  2 ++
 3 files changed, 43 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 29af8616e4aa..0db9a0e53a77 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -618,6 +618,7 @@ struct iommufd_vdevice {
 	u64 id; /* per-vIOMMU virtual ID */
 	struct mutex tsm_lock;
 	bool tsm_bound;
+	bool trusted_dma_enabled;
 };
 
 int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev);
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 296143e21368..8437e936c278 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -224,6 +224,37 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	return rc;
 }
 
+static int iommufd_vdevice_enable_trusted_dma(struct iommufd_vdevice *vdev)
+{
+	struct iommufd_viommu *viommu = vdev->viommu;
+	int rc;
+
+	if (vdev->trusted_dma_enabled)
+		return 0;
+
+	if (viommu->ops->setup_trusted_vdev) {
+		rc = viommu->ops->setup_trusted_vdev(viommu, vdev->id);
+		if (rc)
+			return rc;
+	}
+
+	vdev->trusted_dma_enabled = true;
+	return 0;
+}
+
+static void iommufd_vdevice_disable_trusted_dma(struct iommufd_vdevice *vdev)
+{
+	struct iommufd_viommu *viommu = vdev->viommu;
+
+	if (!vdev->trusted_dma_enabled)
+		return;
+
+	if (viommu->ops->remove_trusted_vdev)
+		viommu->ops->remove_trusted_vdev(viommu, vdev->id);
+
+	vdev->trusted_dma_enabled = false;
+}
+
 int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev)
 {
 	struct kvm *kvm;
@@ -241,12 +272,19 @@ int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev)
 		goto out_unlock;
 	}
 
-	rc = pci_tsm_bind(to_pci_dev(vdev->dev), kvm, vdev->id);
+	rc = iommufd_vdevice_enable_trusted_dma(vdev);
 	if (rc)
 		goto out_unlock;
 
+	rc = pci_tsm_bind(to_pci_dev(vdev->dev), kvm, vdev->id);
+	if (rc)
+		goto out_disable_trusted_dma;
+
 	vdev->tsm_bound = true;
+	goto out_unlock;
 
+out_disable_trusted_dma:
+	iommufd_vdevice_disable_trusted_dma(vdev);
 out_unlock:
 	mutex_unlock(&vdev->tsm_lock);
 	return rc;
@@ -259,6 +297,7 @@ void iommufd_vdevice_tsm_unbind(struct iommufd_vdevice *vdev)
 		goto out_unlock;
 
 	pci_tsm_unbind(to_pci_dev(vdev->dev));
+	iommufd_vdevice_disable_trusted_dma(vdev);
 	vdev->tsm_bound = false;
 
 out_unlock:
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 5f9a286232ac..d73e8d3b9b95 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -136,6 +136,8 @@ struct iommufd_viommu_ops {
 		const struct iommu_user_data *user_data);
 	int (*cache_invalidate)(struct iommufd_viommu *viommu,
 				struct iommu_user_data_array *array);
+	int (*setup_trusted_vdev)(struct iommufd_viommu *viommu, u64 vdev_id);
+	void (*remove_trusted_vdev)(struct iommufd_viommu *viommu, u64 vdev_id);
 };
 
 #if IS_ENABLED(CONFIG_IOMMUFD)

---

## [20] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for TEE-IO support*

Add new IOCTLs to do TSM based TDI bind/unbind. These IOCTLs are
expected to be called by userspace when CoCo VM issues TDI bind/unbind
command to VMM. Specifically for TDX Connect, these commands are some
secure Hypervisor call named GHCI (Guest-Hypervisor Communication
Interface).

The TSM TDI bind/unbind operations are expected to be initiated by a
running CoCo VM, which already have the legacy assigned device in place.
The TSM bind operation is to request VMM make all secure configurations
to support device work as a TDI, and then issue TDISP messages to move
the TDI to CONFIG_LOCKED or RUN state, waiting for guest's attestation.

Do TSM Unbind before vfio_pci_core_disable(), otherwise will lead
device to TDISP ERROR state.

Suggested-by: Jason Gunthorpe <jgg@nvidia.com>
Signed-off-by: Wu Hao <hao.wu@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/iommufd.c           | 22 ++++++++++
 drivers/vfio/pci/vfio_pci_core.c | 74 ++++++++++++++++++++++++++++++++
 include/linux/vfio.h             |  7 +++
 include/linux/vfio_pci_core.h    |  1 +
 include/uapi/linux/vfio.h        | 42 ++++++++++++++++++
 5 files changed, 146 insertions(+)

diff --git a/drivers/vfio/iommufd.c b/drivers/vfio/iommufd.c
index 3441d24538a8..33fd20ffaeee 100644
--- a/drivers/vfio/iommufd.c
+++ b/drivers/vfio/iommufd.c
@@ -297,3 +297,25 @@ void vfio_iommufd_emulated_detach_ioas(struct vfio_device *vdev)
 	vdev->iommufd_attached = false;
 }
 EXPORT_SYMBOL_GPL(vfio_iommufd_emulated_detach_ioas);
+
+int vfio_iommufd_tsm_bind(struct vfio_device *vdev, u32 vdevice_id)
+{
+	lockdep_assert_held(&vdev->dev_set->lock);
+
+	if (WARN_ON(!vdev->iommufd_device))
+		return -EINVAL;
+
+	return iommufd_device_tsm_bind(vdev->iommufd_device, vdevice_id);
+}
+EXPORT_SYMBOL_GPL(vfio_iommufd_tsm_bind);
+
+void vfio_iommufd_tsm_unbind(struct vfio_device *vdev)
+{
+	lockdep_assert_held(&vdev->dev_set->lock);
+
+	if (WARN_ON(!vdev->iommufd_device))
+		return;
+
+	iommufd_device_tsm_unbind(vdev->iommufd_device);
+}
+EXPORT_SYMBOL_GPL(vfio_iommufd_tsm_unbind);
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index 116964057b0b..92544e54c9c3 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -692,6 +692,13 @@ void vfio_pci_core_close_device(struct vfio_device *core_vdev)
 #if IS_ENABLED(CONFIG_EEH)
 	eeh_dev_release(vdev->pdev);
 #endif
+
+	if (vdev->is_tsm_bound) {
+		vfio_iommufd_tsm_unbind(&vdev->vdev);
+		pci_release_regions(vdev->pdev);
+		vdev->is_tsm_bound = false;
+	}
+
 	vfio_pci_core_disable(vdev);
 
 	vfio_pci_dma_buf_cleanup(vdev);
@@ -1447,6 +1454,69 @@ static int vfio_pci_ioctl_ioeventfd(struct vfio_pci_core_device *vdev,
 				  ioeventfd.fd);
 }
 
+static int vfio_pci_ioctl_tsm_bind(struct vfio_pci_core_device *vdev,
+				   void __user *arg)
+{
+	unsigned long minsz = offsetofend(struct vfio_pci_tsm_bind, vdevice_id);
+	struct vfio_pci_tsm_bind tsm_bind;
+	struct pci_dev *pdev = vdev->pdev;
+	int ret;
+
+	if (copy_from_user(&tsm_bind, arg, minsz))
+		return -EFAULT;
+
+	if (tsm_bind.argsz < minsz || tsm_bind.flags)
+		return -EINVAL;
+
+	mutex_lock(&vdev->vdev.dev_set->lock);
+
+	/* To ensure no host side MMIO access is possible */
+	ret = pci_request_regions_exclusive(pdev, "vfio-pci-tsm");
+	if (ret)
+		goto out_unlock;
+
+	ret = vfio_iommufd_tsm_bind(&vdev->vdev, tsm_bind.vdevice_id);
+	if (ret)
+		goto out_release_region;
+
+	vdev->is_tsm_bound = true;
+	mutex_unlock(&vdev->vdev.dev_set->lock);
+
+	return 0;
+
+out_release_region:
+	pci_release_regions(pdev);
+out_unlock:
+	mutex_unlock(&vdev->vdev.dev_set->lock);
+	return ret;
+}
+
+static int vfio_pci_ioctl_tsm_unbind(struct vfio_pci_core_device *vdev,
+				     void __user *arg)
+{
+	unsigned long minsz = offsetofend(struct vfio_pci_tsm_unbind, flags);
+	struct vfio_pci_tsm_unbind tsm_unbind;
+	struct pci_dev *pdev = vdev->pdev;
+
+	if (copy_from_user(&tsm_unbind, arg, minsz))
+		return -EFAULT;
+
+	if (tsm_unbind.argsz < minsz || tsm_unbind.flags)
+		return -EINVAL;
+
+	mutex_lock(&vdev->vdev.dev_set->lock);
+
+	if (!vdev->is_tsm_bound)
+		return 0;
+
+	vfio_iommufd_tsm_unbind(&vdev->vdev);
+	pci_release_regions(pdev);
+	vdev->is_tsm_bound = false;
+	mutex_unlock(&vdev->vdev.dev_set->lock);
+
+	return 0;
+}
+
 long vfio_pci_core_ioctl(struct vfio_device *core_vdev, unsigned int cmd,
 			 unsigned long arg)
 {
@@ -1471,6 +1541,10 @@ long vfio_pci_core_ioctl(struct vfio_device *core_vdev, unsigned int cmd,
 		return vfio_pci_ioctl_reset(vdev, uarg);
 	case VFIO_DEVICE_SET_IRQS:
 		return vfio_pci_ioctl_set_irqs(vdev, uarg);
+	case VFIO_DEVICE_TSM_BIND:
+		return vfio_pci_ioctl_tsm_bind(vdev, uarg);
+	case VFIO_DEVICE_TSM_UNBIND:
+		return vfio_pci_ioctl_tsm_unbind(vdev, uarg);
 	default:
 		return -ENOTTY;
 	}
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index d521d2c01a92..747b94bb9758 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -70,6 +70,7 @@ struct vfio_device {
 	struct iommufd_device *iommufd_device;
 	struct ida pasids;
 	u8 iommufd_attached:1;
+	u8 iommufd_tsm_bound:1;
 #endif
 	u8 cdev_opened:1;
 #ifdef CONFIG_DEBUG_FS
@@ -155,6 +156,8 @@ int vfio_iommufd_emulated_bind(struct vfio_device *vdev,
 void vfio_iommufd_emulated_unbind(struct vfio_device *vdev);
 int vfio_iommufd_emulated_attach_ioas(struct vfio_device *vdev, u32 *pt_id);
 void vfio_iommufd_emulated_detach_ioas(struct vfio_device *vdev);
+int vfio_iommufd_tsm_bind(struct vfio_device *vdev, u32 vdevice_id);
+void vfio_iommufd_tsm_unbind(struct vfio_device *vdev);
 #else
 static inline struct iommufd_ctx *
 vfio_iommufd_device_ictx(struct vfio_device *vdev)
@@ -190,6 +193,10 @@ vfio_iommufd_get_dev_id(struct vfio_device *vdev, struct iommufd_ctx *ictx)
 	((int (*)(struct vfio_device *vdev, u32 *pt_id)) NULL)
 #define vfio_iommufd_emulated_detach_ioas \
 	((void (*)(struct vfio_device *vdev)) NULL)
+#define vfio_iommufd_tsm_bind \
+	((int (*)(struct vfio_device *vdev, u32 vdevice_id)) NULL)
+#define vfio_iommufd_tsm_unbind \
+	((void (*)(struct vfio_device *vdev)) NULL)
 #endif
 
 static inline bool vfio_device_cdev_opened(struct vfio_device *device)
diff --git a/include/linux/vfio_pci_core.h b/include/linux/vfio_pci_core.h
index da5d8955ae56..b2982100221f 100644
--- a/include/linux/vfio_pci_core.h
+++ b/include/linux/vfio_pci_core.h
@@ -80,6 +80,7 @@ struct vfio_pci_core_device {
 	bool			needs_pm_restore:1;
 	bool			pm_intx_masked:1;
 	bool			pm_runtime_engaged:1;
+	bool			is_tsm_bound:1;
 	struct pci_saved_state	*pci_saved_state;
 	struct pci_saved_state	*pm_save;
 	int			ioeventfds_nr;
diff --git a/include/uapi/linux/vfio.h b/include/uapi/linux/vfio.h
index 9445fa36efd3..16bd93a5b427 100644
--- a/include/uapi/linux/vfio.h
+++ b/include/uapi/linux/vfio.h
@@ -1493,6 +1493,48 @@ struct vfio_device_feature_dma_buf {
 	struct vfio_region_dma_range dma_ranges[];
 };
 
+/*
+ * Upon VFIO_DEVICE_TSM_BIND, Put the device in TSM Bind state.
+ *
+ * @argsz:	User filled size of this data.
+ * @flags:	Must be 0.
+ * @vdevice_id:	Input the target id which can represent an vdevice allocated
+ *		via iommufd subsystem.
+ *
+ * The vdevice holds all virtualization information needed for TSM Bind.
+ * TSM Bind means host finishes all host side trusted configurations to build
+ * a Tee Device Interface(TDI), then put the TDI in TDISP CONFIG_LOCKED or RUN
+ * state, waiting for guest's attestation. IOMMUFD finds all virtualization
+ * information from vdevice_id, and executes the TSM Bind. VFIO should be aware
+ * some operations (e.g. reset, toggle MSE, private MMIO access) to physical
+ * device impacts TSM Bind, so never do them or do them only after TSM Unbind.
+ * This IOCTL is only allowed on cdev fds.
+ */
+struct vfio_pci_tsm_bind {
+	__u32	argsz;
+	__u32	flags;
+	__u32	vdevice_id;
+	__u32	pad;
+};
+
+#define VFIO_DEVICE_TSM_BIND		_IO(VFIO_TYPE, VFIO_BASE + 22)
+
+/*
+ * Upon VFIO_DEVICE_TSM_UNBIND, put the device in TSM Unbind state.
+ *
+ * @argsz:	User filled size of this data.
+ * @flags:	Must be 0.
+ *
+ * TSM Unbind means host removes all trusted configurations, and put the TDI in
+ * CONFIG_UNLOCKED TDISP state.
+ */
+struct vfio_pci_tsm_unbind {
+	__u32	argsz;
+	__u32	flags;
+};
+
+#define VFIO_DEVICE_TSM_UNBIND		_IO(VFIO_TYPE, VFIO_BASE + 23)
+
 /* -------- API for Type1 VFIO IOMMU -------- */
 
 /**

---

## [21] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 20/30] vfio/pci: Do TSM Unbind before zapping bars*

When device is TSM Bound, some of its MMIO regions are controlled by
secure firmware. E.g. TDX Connect would require these MMIO regions
mappeed in S-EPT and never unmapped until device Unbound. Zapping bars
irrespective of TSM Bound state may cause unexpected secure firmware
errors. It is always safe to do TSM Unbind first, transiting the device
to shared, then do whatever needed as before.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/vfio_pci_config.c |  4 +++
 drivers/vfio/pci/vfio_pci_core.c   | 41 +++++++++++++++++++-----------
 drivers/vfio/pci/vfio_pci_priv.h   |  3 +++
 3 files changed, 33 insertions(+), 15 deletions(-)

diff --git a/drivers/vfio/pci/vfio_pci_config.c b/drivers/vfio/pci/vfio_pci_config.c
index 7ac062bd5044..4ffe661c9e59 100644
--- a/drivers/vfio/pci/vfio_pci_config.c
+++ b/drivers/vfio/pci/vfio_pci_config.c
@@ -590,6 +590,7 @@ static int vfio_basic_config_write(struct vfio_pci_core_device *vdev, int pos,
 		new_mem = !!(new_cmd & PCI_COMMAND_MEMORY);
 
 		if (!new_mem) {
+			vfio_pci_tsm_unbind(vdev);
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
 			vfio_pci_dma_buf_move(vdev, true);
 		} else {
@@ -712,6 +713,7 @@ static void vfio_lock_and_set_power_state(struct vfio_pci_core_device *vdev,
 					  pci_power_t state)
 {
 	if (state >= PCI_D3hot) {
+		vfio_pci_tsm_unbind(vdev);
 		vfio_pci_zap_and_down_write_memory_lock(vdev);
 		vfio_pci_dma_buf_move(vdev, true);
 	} else {
@@ -907,6 +909,7 @@ static int vfio_exp_config_write(struct vfio_pci_core_device *vdev, int pos,
 						 &cap);
 
 		if (!ret && (cap & PCI_EXP_DEVCAP_FLR)) {
+			vfio_pci_tsm_unbind(vdev);
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
 			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
@@ -992,6 +995,7 @@ static int vfio_af_config_write(struct vfio_pci_core_device *vdev, int pos,
 						&cap);
 
 		if (!ret && (cap & PCI_AF_CAP_FLR) && (cap & PCI_AF_CAP_TP)) {
+			vfio_pci_tsm_unbind(vdev);
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
 			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index 92544e54c9c3..a8437fcecca1 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -286,6 +286,7 @@ static int vfio_pci_runtime_pm_entry(struct vfio_pci_core_device *vdev,
 	 * The vdev power related flags are protected with 'memory_lock'
 	 * semaphore.
 	 */
+	vfio_pci_tsm_unbind(vdev);
 	vfio_pci_zap_and_down_write_memory_lock(vdev);
 	vfio_pci_dma_buf_move(vdev, true);
 
@@ -693,11 +694,7 @@ void vfio_pci_core_close_device(struct vfio_device *core_vdev)
 	eeh_dev_release(vdev->pdev);
 #endif
 
-	if (vdev->is_tsm_bound) {
-		vfio_iommufd_tsm_unbind(&vdev->vdev);
-		pci_release_regions(vdev->pdev);
-		vdev->is_tsm_bound = false;
-	}
+	__vfio_pci_tsm_unbind(vdev);
 
 	vfio_pci_core_disable(vdev);
 
@@ -1222,6 +1219,7 @@ static int vfio_pci_ioctl_reset(struct vfio_pci_core_device *vdev,
 	if (!vdev->reset_works)
 		return -EINVAL;
 
+	vfio_pci_tsm_unbind(vdev);
 	vfio_pci_zap_and_down_write_memory_lock(vdev);
 
 	/*
@@ -1491,12 +1489,32 @@ static int vfio_pci_ioctl_tsm_bind(struct vfio_pci_core_device *vdev,
 	return ret;
 }
 
+void __vfio_pci_tsm_unbind(struct vfio_pci_core_device *vdev)
+{
+	struct pci_dev *pdev = vdev->pdev;
+
+	lockdep_assert_held(&vdev->vdev.dev_set->lock);
+
+	if (!vdev->is_tsm_bound)
+		return;
+
+	vfio_iommufd_tsm_unbind(&vdev->vdev);
+	pci_release_regions(pdev);
+	vdev->is_tsm_bound = false;
+}
+
+void vfio_pci_tsm_unbind(struct vfio_pci_core_device *vdev)
+{
+	mutex_lock(&vdev->vdev.dev_set->lock);
+	__vfio_pci_tsm_unbind(vdev);
+	mutex_unlock(&vdev->vdev.dev_set->lock);
+}
+
 static int vfio_pci_ioctl_tsm_unbind(struct vfio_pci_core_device *vdev,
 				     void __user *arg)
 {
 	unsigned long minsz = offsetofend(struct vfio_pci_tsm_unbind, flags);
 	struct vfio_pci_tsm_unbind tsm_unbind;
-	struct pci_dev *pdev = vdev->pdev;
 
 	if (copy_from_user(&tsm_unbind, arg, minsz))
 		return -EFAULT;
@@ -1504,15 +1522,7 @@ static int vfio_pci_ioctl_tsm_unbind(struct vfio_pci_core_device *vdev,
 	if (tsm_unbind.argsz < minsz || tsm_unbind.flags)
 		return -EINVAL;
 
-	mutex_lock(&vdev->vdev.dev_set->lock);
-
-	if (!vdev->is_tsm_bound)
-		return 0;
-
-	vfio_iommufd_tsm_unbind(&vdev->vdev);
-	pci_release_regions(pdev);
-	vdev->is_tsm_bound = false;
-	mutex_unlock(&vdev->vdev.dev_set->lock);
+	vfio_pci_tsm_unbind(vdev);
 
 	return 0;
 }
@@ -2526,6 +2536,7 @@ static int vfio_pci_dev_set_hot_reset(struct vfio_device_set *dev_set,
 			break;
 		}
 
+		__vfio_pci_tsm_unbind(vdev);
 		/*
 		 * Take the memory write lock for each device and zap BAR
 		 * mappings to prevent the user accessing the device while in
diff --git a/drivers/vfio/pci/vfio_pci_priv.h b/drivers/vfio/pci/vfio_pci_priv.h
index 6f3e8eafdc35..e5bf27f46a73 100644
--- a/drivers/vfio/pci/vfio_pci_priv.h
+++ b/drivers/vfio/pci/vfio_pci_priv.h
@@ -130,4 +130,7 @@ static inline void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev,
 }
 #endif
 
+void __vfio_pci_tsm_unbind(struct vfio_pci_core_device *vdev);
+void vfio_pci_tsm_unbind(struct vfio_pci_core_device *vdev);
+
 #endif

---

## [22] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 21/30] iommufd/vdevice: Add TSM Guest request uAPI*

From: Alexey Kardashevskiy <aik@amd.com>

Add TSM Guest request uAPI against iommufd_vdevice to forward various
TSM attestation & acceptance requests from guest to TSM driver/secure
firmware. This uAPI takes function only after TSM Bind.

After a vPCI device is locked down by TSM Bind, CoCo VM should attest
and accept the device in its TEE. These operations needs interaction
with secure firmware and the device, but doesn't impact the device
management from host's POV. It doesn't change the fact that host should
not touch some part of the device (see TDISP spec) to keep the trusted
assignment, and host could exit trusted assignment and roll back
everything by TSM Unbind.

So the TSM Guest request becomes a passthrough channel for CoCo VM to
exchange request/response blobs with TSM driver/secure firmware. The
definition of this IOCTL illustates this idea.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/iommufd/iommufd_private.h |  1 +
 drivers/iommu/iommufd/main.c            |  3 ++
 drivers/iommu/iommufd/viommu.c          | 39 +++++++++++++++++++++++++
 include/uapi/linux/iommufd.h            | 28 ++++++++++++++++++
 4 files changed, 71 insertions(+)

diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 0db9a0e53a77..610dc2efcdd5 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -609,6 +609,7 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_viommu_destroy(struct iommufd_object *obj);
 int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_vdevice_destroy(struct iommufd_object *obj);
+int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd);
 
 struct iommufd_vdevice {
 	struct iommufd_object obj;
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 3df468f64e7d..17c5b2cb6ab1 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -320,6 +320,7 @@ union ucmd_buffer {
 	struct iommu_veventq_alloc veventq;
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
+	struct iommu_vdevice_tsm_guest_request gr;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -379,6 +380,8 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 __reserved),
 	IOCTL_OP(IOMMU_VIOMMU_ALLOC, iommufd_viommu_alloc_ioctl,
 		 struct iommu_viommu_alloc, out_viommu_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_GUEST_REQUEST, iommufd_vdevice_tsm_guest_request_ioctl,
+		 struct iommu_vdevice_tsm_guest_request, resp_uptr),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 8437e936c278..c64ce1a9f87d 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -303,3 +303,42 @@ void iommufd_vdevice_tsm_unbind(struct iommufd_vdevice *vdev)
 out_unlock:
 	mutex_unlock(&vdev->tsm_lock);
 }
+
+int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_tsm_guest_request *cmd = ucmd->cmd;
+	struct pci_tsm_guest_req_info info = {
+		.type = cmd->type,
+		.type_info = u64_to_user_ptr(cmd->type_info_uptr),
+		.type_info_len = cmd->type_info_len,
+		.req = u64_to_user_ptr(cmd->req_uptr),
+		.req_len = cmd->req_len,
+		.resp = u64_to_user_ptr(cmd->resp_uptr),
+		.resp_len = cmd->resp_len,
+	};
+	struct iommufd_vdevice *vdev;
+	int rc;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	mutex_lock(&vdev->tsm_lock);
+	if (!vdev->tsm_bound) {
+		rc = -ENOENT;
+		goto out_unlock;
+	}
+
+	rc = pci_tsm_guest_req(to_pci_dev(vdev->dev), &info);
+	if (rc)
+		goto out_unlock;
+
+	cmd->resp_len = info.resp_len;
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+out_unlock:
+	mutex_unlock(&vdev->tsm_lock);
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index f29b6c44655e..b8170fe3d700 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -56,6 +56,7 @@ enum {
 	IOMMUFD_CMD_VDEVICE_ALLOC = 0x91,
 	IOMMUFD_CMD_IOAS_CHANGE_PROCESS = 0x92,
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
+	IOMMUFD_CMD_VDEVICE_TSM_GUEST_REQUEST = 0x94,
 };
 
 /**
@@ -1141,4 +1142,31 @@ struct iommu_veventq_alloc {
 	__u32 __reserved;
 };
 #define IOMMU_VEVENTQ_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VEVENTQ_ALLOC)
+
+/**
+ * struct iommu_vdevice_tsm_guest_request - ioctl(IOMMU_VDEVICE_TSM_GUEST_REQUEST)
+ * @size: sizeof(struct iommu_vdevice_tsm_guest_request)
+ * @vdevice_id: vDevice ID the guest request is for
+ * @type: identify the format of the following blobs
+ * @type_info_len: the blob size for @type_info_uptr
+ * @req_len: the blob size for @req_uptr, filled by guest
+ * @resp_len: for input, the blob size for @resp_uptr, filled by guest
+ *	      for output, the size of actual response data, filled by host
+ * @type_info_uptr: extra input/output info, e.g. firmware error code
+ * @req_uptr: request data buffer filled by guest
+ * @resp_uptr: response data buffer filled by host
+ */
+struct iommu_vdevice_tsm_guest_request {
+	__u32 size;
+	__u32 vdevice_id;
+	__u32 type;
+	__u32 type_info_len;
+	__u32 req_len;
+	__u32 resp_len;
+	__aligned_u64 type_info_uptr;
+	__aligned_u64 req_uptr;
+	__aligned_u64 resp_uptr;
+};
+#define IOMMU_VDEVICE_TSM_GUEST_REQUEST _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_GUEST_REQUEST)
+
 #endif

---

## [23] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 22/30] fixup! PCI/TSM: Change the guest request type definition*

Move the guest_request_type to IOMMUFD uAPI header file so that
userspace could use it for IOMMUFD uAPI -
IOMMU_VDEVICE_TSM_GUEST_REQUEST.

Add __user marker to all blob pointers to indicate the TSM drivers'
responsibility to read out/fill in user data.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/pci-tsm.h      | 12 ++++--------
 include/uapi/linux/iommufd.h |  8 ++++++++
 2 files changed, 12 insertions(+), 8 deletions(-)

diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 1920ca591a42..737767f8a9c5 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -107,10 +107,6 @@ static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
 	return PCI_FUNC(pdev->devfn) == 0;
 }
 
-enum pci_tsm_guest_req_type {
-	PCI_TSM_GUEST_REQ_TDXC,
-};
-
 /**
  * struct pci_tsm_guest_req_info - parameter for pci_tsm_ops.guest_req()
  * @type: identify the format of the following blobs
@@ -123,12 +119,12 @@ enum pci_tsm_guest_req_type {
  *	      for output, the size of actual response data filled by host
  */
 struct pci_tsm_guest_req_info {
-	enum pci_tsm_guest_req_type type;
-	void *type_info;
+	u32 type;
+	void __user *type_info;
 	size_t type_info_len;
-	void *req;
+	void __user *req;
 	size_t req_len;
-	void *resp;
+	void __user *resp;
 	size_t resp_len;
 };
 
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index b8170fe3d700..7196bc295669 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -1143,6 +1143,14 @@ struct iommu_veventq_alloc {
 };
 #define IOMMU_VEVENTQ_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VEVENTQ_ALLOC)
 
+/**
+ * enum pci_tsm_guest_req_type - Specify the format of guest request blobs
+ * @PCI_TSM_GUEST_REQ_TDXC: Intel TDX Connect specific type
+ */
+enum pci_tsm_guest_req_type {
+	PCI_TSM_GUEST_REQ_TDXC,
+};
+
 /**
  * struct iommu_vdevice_tsm_guest_request - ioctl(IOMMU_VDEVICE_TSM_GUEST_REQUEST)
  * @size: sizeof(struct iommu_vdevice_tsm_guest_request)

---

## [24] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 23/30] coco/tdx_tsm: Introduce a "tdx" subsystem and "tsm" device*

From: Dan Williams <dan.j.williams@intel.com>

TDX depends on a platform firmware module that is invoked via
instructions similar to vmenter (i.e. enter into a new privileged
"root-mode" context to manage private memory and private device
mechanisms). It is a software construct that depends on the CPU vmxon
state to enable invocation of TDX-module ABIs. Unlike other
Trusted Execution Environment (TEE) platform implementations that employ
a firmware module running on a PCI device with an MMIO mailbox for
communication, TDX has no hardware device to point to as the "TSM".

The "/sys/devices/virtual" hierarchy is intended for "software
constructs which need sysfs interface", which aligns with what TDX
needs.

The new tdx_subsys will export global attributes populated by the
TDX-module "sysinfo". A tdx_tsm device is published on this bus to
enable a typical driver model for the low level "TEE Security Manager"
(TSM) flows that talk TDISP to capable PCIe devices.
For now, this is only the base tdx_subsys and tdx_tsm device
registration with attribute definition and TSM driver to follow later.

Recall that TDX guest would also use TSM to authenticate assigned
devices and it surely needs a virtual software construct to enable guest
side TSM flow. A tdx_guest_tsm device would be published on tdx_subsys
to indicate the guest is capable of communicate to firmware for TIO via
TDVMCALLs.

Create some common helpers for TDX host/guest to create software devices
on tdx_subsys.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Wu Hao <hao.wu@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/Kconfig                     |  1 +
 drivers/virt/coco/host/Kconfig       |  3 ++
 drivers/virt/coco/host/Makefile      |  2 +
 drivers/virt/coco/host/tdx_tsm_bus.c | 70 ++++++++++++++++++++++++++++
 include/linux/tdx_tsm_bus.h          | 17 +++++++
 5 files changed, 93 insertions(+)
 create mode 100644 drivers/virt/coco/host/tdx_tsm_bus.c
 create mode 100644 include/linux/tdx_tsm_bus.h

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 4b9f378e05f6..fb6cc23b02e3 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1925,6 +1925,7 @@ config INTEL_TDX_HOST
 	depends on CONTIG_ALLOC
 	depends on !KEXEC_CORE
 	depends on X86_MCE
+	select TDX_TSM_BUS
 	help
 	  Intel Trust Domain Extensions (TDX) protects guest VMs from malicious
 	  host and certain physical attacks.  This option enables necessary TDX
diff --git a/drivers/virt/coco/host/Kconfig b/drivers/virt/coco/host/Kconfig
index 4fbc6ef34f12..c04b0446cd5f 100644
--- a/drivers/virt/coco/host/Kconfig
+++ b/drivers/virt/coco/host/Kconfig
@@ -4,3 +4,6 @@
 #
 config TSM
 	tristate
+
+config TDX_TSM_BUS
+	bool
diff --git a/drivers/virt/coco/host/Makefile b/drivers/virt/coco/host/Makefile
index be0aba6007cd..ce1ab15ac8d3 100644
--- a/drivers/virt/coco/host/Makefile
+++ b/drivers/virt/coco/host/Makefile
@@ -4,3 +4,5 @@
 
 obj-$(CONFIG_TSM) += tsm.o
 tsm-y := tsm-core.o
+
+obj-$(CONFIG_TDX_TSM_BUS) += tdx_tsm_bus.o
diff --git a/drivers/virt/coco/host/tdx_tsm_bus.c b/drivers/virt/coco/host/tdx_tsm_bus.c
new file mode 100644
index 000000000000..9f4875ebf032
--- /dev/null
+++ b/drivers/virt/coco/host/tdx_tsm_bus.c
@@ -0,0 +1,70 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#include <linux/device.h>
+#include <linux/tdx_tsm_bus.h>
+
+static struct tdx_tsm_dev *alloc_tdx_tsm_dev(void)
+{
+	struct tdx_tsm_dev *tsm = kzalloc(sizeof(*tsm), GFP_KERNEL);
+	struct device *dev;
+
+	if (!tsm)
+		return ERR_PTR(-ENOMEM);
+
+	dev = &tsm->dev;
+	dev->bus = &tdx_subsys;
+	device_initialize(dev);
+
+	return tsm;
+}
+
+DEFINE_FREE(tdx_tsm_dev_put, struct tdx_tsm_dev *,
+	if (!IS_ERR_OR_NULL(_T)) put_device(&_T->dev))
+struct tdx_tsm_dev *init_tdx_tsm_dev(const char *name)
+{
+	struct device *dev;
+	int ret;
+
+	struct tdx_tsm_dev *tsm __free(tdx_tsm_dev_put) = alloc_tdx_tsm_dev();
+	if (IS_ERR(tsm))
+		return tsm;
+
+	dev = &tsm->dev;
+	ret = dev_set_name(dev, name);
+	if (ret)
+		return ERR_PTR(ret);
+
+	ret = device_add(dev);
+	if (ret)
+		return ERR_PTR(ret);
+
+	return no_free_ptr(tsm);
+}
+EXPORT_SYMBOL_GPL(init_tdx_tsm_dev);
+
+static int tdx_match(struct device *dev, const struct device_driver *drv)
+{
+	if (!strcmp(dev_name(dev), drv->name))
+		return 1;
+
+	return 0;
+}
+
+static int tdx_uevent(const struct device *dev, struct kobj_uevent_env *env)
+{
+	return add_uevent_var(env, "MODALIAS=%s", dev_name(dev));
+}
+
+const struct bus_type tdx_subsys = {
+	.name = "tdx",
+	.match = tdx_match,
+	.uevent = tdx_uevent,
+};
+EXPORT_SYMBOL_GPL(tdx_subsys);
+
+static int tdx_tsm_dev_init(void)
+{
+	return subsys_virtual_register(&tdx_subsys, NULL);
+}
+arch_initcall(tdx_tsm_dev_init);
diff --git a/include/linux/tdx_tsm_bus.h b/include/linux/tdx_tsm_bus.h
new file mode 100644
index 000000000000..ef7af97ba230
--- /dev/null
+++ b/include/linux/tdx_tsm_bus.h
@@ -0,0 +1,17 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/* Copyright(c) 2024 Intel Corporation. */
+
+#ifndef __TDX_TSM_BUS_H
+#define __TDX_TSM_BUS_H
+
+#include <linux/device.h>
+
+struct tdx_tsm_dev {
+	struct device dev;
+};
+
+extern const struct bus_type tdx_subsys;
+
+struct tdx_tsm_dev *init_tdx_tsm_dev(const char *name);
+
+#endif

---

## [25] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 24/30] coco/tdx_tsm: TEE Security Manager driver for TDX*

From: Dan Williams <dan.j.williams@intel.com>

Recall that a TEE Security Manager (TSM) is a platform agent that speaks
the TEE Device Interface Security Protocol (TDISP) to PCIe devices and
manages private memory resources for the platform. The tdx_tsm driver
loads against a device of the same name registered at TDX Module
initialization time. The device lives on the "tdx" bus which is a
virtual subsystem that hosts the TDX module sysfs ABI.

It allows for device-security enumeration and initialization flows to be
deferred from TDX Module init time. Crucially, when / if TDX Module
init moves earlier in x86 initialization flow this driver is still
guaranteed to run after IOMMU and PCI init (i.e. subsys_initcall() vs
device_initcall()).

The ability to unload the module, or unbind the driver is also useful
for debug and coarse grained transitioning between PCI TSM operation and
PCI CMA operation (native kernel PCI device authentication).

For now this is the basic boilerplate with sysfs attributes and
operation flows to be added later.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Wu Hao <hao.wu@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/host/Kconfig   |   7 ++
 drivers/virt/coco/host/Makefile  |   1 +
 drivers/virt/coco/host/tdx_tsm.c | 189 +++++++++++++++++++++++++++++++
 3 files changed, 197 insertions(+)
 create mode 100644 drivers/virt/coco/host/tdx_tsm.c

diff --git a/drivers/virt/coco/host/Kconfig b/drivers/virt/coco/host/Kconfig
index c04b0446cd5f..f2b05b15a24e 100644
--- a/drivers/virt/coco/host/Kconfig
+++ b/drivers/virt/coco/host/Kconfig
@@ -7,3 +7,10 @@ config TSM
 
 config TDX_TSM_BUS
 	bool
+
+config TDX_TSM
+	depends on INTEL_TDX_HOST
+	select TDX_TSM_BUS
+	select PCI_TSM
+	select TSM
+	tristate "TDX TEE Security Manager Driver"
diff --git a/drivers/virt/coco/host/Makefile b/drivers/virt/coco/host/Makefile
index ce1ab15ac8d3..38ee9c96b921 100644
--- a/drivers/virt/coco/host/Makefile
+++ b/drivers/virt/coco/host/Makefile
@@ -6,3 +6,4 @@ obj-$(CONFIG_TSM) += tsm.o
 tsm-y := tsm-core.o
 
 obj-$(CONFIG_TDX_TSM_BUS) += tdx_tsm_bus.o
+obj-$(CONFIG_TDX_TSM) += tdx_tsm.o
diff --git a/drivers/virt/coco/host/tdx_tsm.c b/drivers/virt/coco/host/tdx_tsm.c
new file mode 100644
index 000000000000..72f3705fe7bb
--- /dev/null
+++ b/drivers/virt/coco/host/tdx_tsm.c
@@ -0,0 +1,189 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+#include <linux/bitfield.h>
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
+#include <linux/tdx_tsm_bus.h>
+#include <linux/tsm.h>
+#include <asm/tdx.h>
+
+#define TDISP_FUNC_ID		GENMASK(15, 0)
+#define TDISP_FUNC_ID_SEGMENT		GENMASK(23, 16)
+#define TDISP_FUNC_ID_SEG_VALID		BIT(24)
+
+static inline u32 tdisp_func_id(struct pci_dev *pdev)
+{
+	u32 func_id;
+
+	func_id = FIELD_PREP(TDISP_FUNC_ID_SEGMENT, pci_domain_nr(pdev->bus));
+	if (func_id)
+		func_id |= TDISP_FUNC_ID_SEG_VALID;
+	func_id |= FIELD_PREP(TDISP_FUNC_ID,
+			      PCI_DEVID(pdev->bus->number, pdev->devfn));
+
+	return func_id;
+}
+
+struct tdx_tsm {
+	struct pci_tsm_pf0 pci;
+	u32 func_id;
+};
+
+static struct tdx_tsm *to_tdx_tsm(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct tdx_tsm, pci.tsm);
+}
+
+struct tdx_tdi {
+	struct pci_tdi tdi;
+	u32 func_id;
+};
+
+static struct tdx_tdi *to_tdx_tdi(struct pci_tdi *tdi)
+{
+	return container_of(tdi, struct tdx_tdi, tdi);
+}
+
+static struct pci_tdi *tdx_tsm_bind(struct pci_dev *pdev,
+				    struct pci_dev *dsm_dev,
+				    struct kvm *kvm, u64 tdi_id)
+{
+	struct tdx_tdi *ttdi __free(kfree) =
+		kzalloc(sizeof(*ttdi), GFP_KERNEL);
+	if (!ttdi)
+		return NULL;
+
+	ttdi->func_id = tdisp_func_id(pdev);
+	ttdi->tdi.pdev = pdev;
+	ttdi->tdi.dsm_dev = pci_dev_get(dsm_dev);
+	ttdi->tdi.kvm = kvm;
+
+	/*TODO: TDX Module required operations */
+
+	return &no_free_ptr(ttdi)->tdi;
+}
+
+static void tdx_tsm_unbind(struct pci_tdi *tdi)
+{
+	struct tdx_tdi *ttdi = to_tdx_tdi(tdi);
+
+	/*TODO: TDX Module required operations */
+
+	pci_dev_put(ttdi->tdi.dsm_dev);
+	kfree(ttdi);
+}
+
+static int tdx_tsm_guest_req(struct pci_dev *pdev,
+			     struct pci_tsm_guest_req_info *info)
+{
+	return -ENXIO;
+}
+
+static int tdx_tsm_connect(struct pci_dev *pdev)
+{
+	return -ENXIO;
+}
+
+static void tdx_tsm_disconnect(struct pci_dev *pdev)
+{
+}
+
+static struct pci_tsm *tdx_tsm_pci_probe(struct pci_dev *pdev)
+{
+	if (is_pci_tsm_pf0(pdev)) {
+		int rc;
+
+		struct tdx_tsm *ttsm __free(kfree) =
+			kzalloc(sizeof(*ttsm), GFP_KERNEL);
+		if (!ttsm)
+			return NULL;
+
+		rc = pci_tsm_pf0_initialize(pdev, &ttsm->pci);
+		if (rc)
+			return NULL;
+
+		ttsm->func_id = tdisp_func_id(pdev);
+
+		pci_info(pdev, "PF tsm enabled\n");
+		return &no_free_ptr(ttsm)->pci.tsm;
+	}
+
+	/* for VF and MFD */
+	struct pci_tsm *pci_tsm __free(kfree) =
+		kzalloc(sizeof(*pci_tsm), GFP_KERNEL);
+	if (!pci_tsm)
+		return NULL;
+
+	pci_tsm_initialize(pdev, pci_tsm);
+
+	pci_info(pdev, "VF/MFD tsm enabled\n");
+	return no_free_ptr(pci_tsm);
+}
+
+static void tdx_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	if (is_pci_tsm_pf0(tsm->pdev)) {
+		struct tdx_tsm *ttsm = to_tdx_tsm(tsm);
+
+		pci_info(tsm->pdev, "PF tsm disabled\n");
+		kfree(ttsm);
+
+		return;
+	}
+
+	/* for VF and MFD */
+	kfree(tsm);
+}
+
+static const struct pci_tsm_ops tdx_pci_tsm_ops = {
+	.probe = tdx_tsm_pci_probe,
+	.remove = tdx_tsm_pci_remove,
+	.connect = tdx_tsm_connect,
+	.disconnect = tdx_tsm_disconnect,
+	.bind = tdx_tsm_bind,
+	.unbind = tdx_tsm_unbind,
+	.guest_req = tdx_tsm_guest_req,
+};
+
+static void unregister_tsm(void *tsm_core)
+{
+	tsm_unregister(tsm_core);
+}
+
+static int tdx_tsm_probe(struct device *dev)
+{
+	struct tsm_core_dev *tsm_core;
+
+	tsm_core = tsm_register(dev, NULL, &tdx_pci_tsm_ops);
+	if (IS_ERR(tsm_core)) {
+		dev_err(dev, "failed to register TSM: (%pe)\n", tsm_core);
+		return PTR_ERR(tsm_core);
+	}
+
+	return devm_add_action_or_reset(dev, unregister_tsm, tsm_core);
+}
+
+static struct device_driver tdx_tsm_driver = {
+	.probe = tdx_tsm_probe,
+	.bus = &tdx_subsys,
+	.owner = THIS_MODULE,
+	.name = KBUILD_MODNAME,
+	.mod_name = KBUILD_MODNAME,
+};
+
+static int __init tdx_tsm_init(void)
+{
+	return driver_register(&tdx_tsm_driver);
+}
+module_init(tdx_tsm_init);
+
+static void __exit tdx_tsm_exit(void)
+{
+	driver_unregister(&tdx_tsm_driver);
+}
+module_exit(tdx_tsm_exit);
+
+MODULE_IMPORT_NS("TDX");
+MODULE_LICENSE("GPL");
+MODULE_ALIAS("tdx_tsm");
+MODULE_DESCRIPTION("TDX TEE Security Manager");

---

## [26] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 25/30] coco/tdx_tsm: Add connect()/disconnect() handlers prototype*

From: Wu Hao <hao.wu@intel.com>

Add basic skeleton for connect()/disconnect() handlers. The major steps
are SPDM setup first and then IDE selective stream setup.

No detailed TDX Connect implementation.

Signed-off-by: Wu Hao <hao.wu@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/host/tdx_tsm.c | 55 +++++++++++++++++++++++++++++++-
 1 file changed, 54 insertions(+), 1 deletion(-)

diff --git a/drivers/virt/coco/host/tdx_tsm.c b/drivers/virt/coco/host/tdx_tsm.c
index 72f3705fe7bb..d1a8384d8339 100644
--- a/drivers/virt/coco/host/tdx_tsm.c
+++ b/drivers/virt/coco/host/tdx_tsm.c
@@ -79,13 +79,66 @@ static int tdx_tsm_guest_req(struct pci_dev *pdev,
 	return -ENXIO;
 }
 
+static int tdx_tsm_spdm_session_setup(struct tdx_tsm *ttsm)
+{
+	return 0;
+}
+
+static int tdx_tsm_spdm_session_teardown(struct tdx_tsm *ttsm)
+{
+	return 0;
+}
+
+static int tdx_tsm_ide_stream_setup(struct tdx_tsm *ttsm)
+{
+	return 0;
+}
+
+static int tdx_tsm_ide_stream_teardown(struct tdx_tsm *ttsm)
+{
+	return 0;
+}
+
 static int tdx_tsm_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct tdx_tsm *ttsm = to_tdx_tsm(pdev->tsm);
+	int ret;
+
+	ret = tdx_tsm_spdm_session_setup(ttsm);
+	if (ret) {
+		pci_err(pdev, "fail to setup spdm session\n");
+		return ret;
+	}
+
+	ret = tdx_tsm_ide_stream_setup(ttsm);
+	if (ret) {
+		pci_err(pdev, "fail to setup ide stream\n");
+		tdx_tsm_spdm_session_teardown(ttsm);
+		return ret;
+	}
+
+	pci_dbg(pdev, "%s complete\n", __func__);
+	return ret;
 }
 
 static void tdx_tsm_disconnect(struct pci_dev *pdev)
 {
+	struct tdx_tsm *ttsm = to_tdx_tsm(pdev->tsm);
+	int ret;
+
+	ret = tdx_tsm_ide_stream_teardown(ttsm);
+	if (ret) {
+		pci_err(pdev, "fail to teardown ide stream\n");
+		return;
+	}
+
+	ret = tdx_tsm_spdm_session_teardown(ttsm);
+	if (ret) {
+		pci_err(pdev, "fail to teadown spdm session\n");
+		return;
+	}
+
+	pci_dbg(pdev, "%s complete\n", __func__);
 }
 
 static struct pci_tsm *tdx_tsm_pci_probe(struct pci_dev *pdev)

---

## [27] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 26/30] coco/tdx_tsm: Add bind()/unbind()/guest_req() handlers prototype*

Add basic skeleton for bind()/unbind()/guest_req() handlers.

Specifically, tdx_tdi_devifmt/devif_create() declare the TDI ownership
to TD. tdx_tdi_mmiomt_create() declares the MMIO ownership to TD.
tdx_tdi_request(TDX_TDI_REQ_BIND) locks the TDI.

No detailed TDX Connect implementation.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/host/tdx_tsm.c | 83 ++++++++++++++++++++++++++++++--
 1 file changed, 80 insertions(+), 3 deletions(-)

diff --git a/drivers/virt/coco/host/tdx_tsm.c b/drivers/virt/coco/host/tdx_tsm.c
index d1a8384d8339..beb65f45b478 100644
--- a/drivers/virt/coco/host/tdx_tsm.c
+++ b/drivers/virt/coco/host/tdx_tsm.c
@@ -44,10 +44,49 @@ static struct tdx_tdi *to_tdx_tdi(struct pci_tdi *tdi)
 	return container_of(tdi, struct tdx_tdi, tdi);
 }
 
+static int tdx_tdi_devifmt_create(struct tdx_tdi *ttdi)
+{
+	return 0;
+}
+
+static void tdx_tdi_devifmt_free(struct tdx_tdi *ttdi)
+{
+}
+
+static int tdx_tdi_mmiomt_create(struct tdx_tdi *ttdi)
+{
+	return 0;
+}
+
+static void tdx_tdi_mmiomt_free(struct tdx_tdi *ttdi)
+{
+}
+
+static int tdx_tdi_devif_create(struct tdx_tdi *ttdi)
+{
+	return 0;
+}
+
+static void tdx_tdi_devif_free(struct tdx_tdi *ttdi)
+{
+}
+
+#define TDX_TDI_REQ_BIND	1
+#define TDX_TDI_REQ_START	2
+#define TDX_TDI_REQ_GET_STATE	3
+#define TDX_TDI_REQ_STOP	4
+
+static int tdx_tdi_request(struct tdx_tdi *ttdi, unsigned int req)
+{
+	return 0;
+}
+
 static struct pci_tdi *tdx_tsm_bind(struct pci_dev *pdev,
 				    struct pci_dev *dsm_dev,
 				    struct kvm *kvm, u64 tdi_id)
 {
+	int ret;
+
 	struct tdx_tdi *ttdi __free(kfree) =
 		kzalloc(sizeof(*ttdi), GFP_KERNEL);
 	if (!ttdi)
@@ -58,17 +97,55 @@ static struct pci_tdi *tdx_tsm_bind(struct pci_dev *pdev,
 	ttdi->tdi.dsm_dev = pci_dev_get(dsm_dev);
 	ttdi->tdi.kvm = kvm;
 
-	/*TODO: TDX Module required operations */
+	ret = tdx_tdi_devifmt_create(ttdi);
+	if (ret) {
+		pci_err(pdev, "fail to init devifmt\n");
+		goto put_dsm_dev;
+	}
+
+	ret = tdx_tdi_devif_create(ttdi);
+	if (ret) {
+		pci_err(pdev, "%s fail to init devif\n", __func__);
+		goto devifmt_free;
+	}
+
+	ret = tdx_tdi_mmiomt_create(ttdi);
+	if (ret) {
+		pci_err(pdev, "%s fail to create mmiomt\n", __func__);
+		goto devif_free;
+	}
+
+	ret = tdx_tdi_request(ttdi, TDX_TDI_REQ_BIND);
+	if (ret) {
+		pci_err(pdev, "%s fial to request bind\n", __func__);
+		goto mmiomt_free;
+	}
 
 	return &no_free_ptr(ttdi)->tdi;
+
+mmiomt_free:
+	tdx_tdi_mmiomt_free(ttdi);
+devif_free:
+	tdx_tdi_devif_free(ttdi);
+devifmt_free:
+	tdx_tdi_devifmt_free(ttdi);
+put_dsm_dev:
+	pci_dev_put(dsm_dev);
+	return NULL;
 }
 
 static void tdx_tsm_unbind(struct pci_tdi *tdi)
 {
 	struct tdx_tdi *ttdi = to_tdx_tdi(tdi);
 
-	/*TODO: TDX Module required operations */
-
+	/*
+	 * TODO: In fact devif cannot be freed before TDI's private MMIOs and
+	 * private DMA are unmapped. Will handle this restriction later.
+	 */
+	tdx_tdi_request(ttdi, TDX_TDI_REQ_STOP);
+	tdx_tdi_mmiomt_free(ttdi);
+	tdx_tdi_devif_free(ttdi);
+	tdx_tdi_devifmt_free(ttdi);
 	pci_dev_put(ttdi->tdi.dsm_dev);
 	kfree(ttdi);
 }

---

## [28] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 27/30] PCI/TSM: Add PCI driver callbacks to handle TSM requirements*

Add optional PCI driver callbacks to notify TSM events. For now, these
handlers may be called during pci_tsm_unbind(). By calling these
handlers, TSM driver askes for external collaboration to finish entire
TSM unbind flow.

If platform TSM driver could finish TSM bind/unbind all by itself, don't
call these handlers.

Host may need to configure various system components according to
platform trusted firmware's requirements. E.g. for Intel TDX Connect,
host should do private MMIO mapping in S-EPT, trusted DMA setup, device
ownership claiming and device TDISP state transition. Some operations are
out of control of PCI TSM, so need collaboration by external components
like IOMMU driver, KVM.

Further more, trusted firmware may enforce executing these operations
in a fixed sequence. E.g. Intel TDX Connect enforces the following
sequences for TSM unbind:

  1. STOP TDI via TDISP message STOP_INTERFACE
  2. Private MMIO unmap from Secure EPT
  3. Trusted Device Context Table cleanup for the TDI
  4. TDI ownership reclaim and metadata free

PCI TSM could do Step 1 and 4, but need KVM for Step 2 and IOMMU driver
for Step 3. While it is possible TSM provides finer grained APIs like
tdi_stop() & tdi_free(), and the caller ensures the sequence, it is
better these specific enforcement could be managed in platform TSM
driver. By introducing TSM handlers, platform TSM driver controls the
operation sequence and notify other components to do the real work.

Currently add 3 callbacks for TDX Connect. disable_mmio() is for
VFIO to invalidate MMIO so that KVM could unmap them from S-EPT.
recover_mmio() is to re-validate MMIO so that KVM could map them
again for shared assigned device. disable_trusted_dma() is to cleanup
trusted IOMMU setup.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/pci-tsm.h | 7 +++++++
 include/linux/pci.h     | 3 +++
 2 files changed, 10 insertions(+)

diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 737767f8a9c5..ed549724eb5b 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -157,6 +157,13 @@ struct pci_tsm_ops {
 	int (*accept)(struct pci_dev *pdev);
 };
 
+/* pci drivers callbacks for TSM */
+struct pci_tsm_handlers {
+	void (*disable_mmio)(struct pci_dev *dev);
+	void (*recover_mmio)(struct pci_dev *dev);
+	void (*disable_trusted_dma)(struct pci_dev *dev);
+};
+
 enum pci_doe_proto {
 	PCI_DOE_PROTO_CMA = 1,
 	PCI_DOE_PROTO_SSESSION = 2,
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 5f37957da18f..4f768b4658e8 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -545,6 +545,7 @@ struct pci_dev {
 #endif
 #ifdef CONFIG_PCI_TSM
 	struct pci_tsm *tsm;		/* TSM operation state */
+	void *trusted_dma_owner;
 #endif
 	u16		acs_cap;	/* ACS Capability offset */
 	u8		supported_speeds; /* Supported Link Speeds Vector */
@@ -957,6 +958,7 @@ struct module;
  * @sriov_get_vf_total_msix: PF driver callback to get the total number of
  *              MSI-X vectors available for distribution to the VFs.
  * @err_handler: See Documentation/PCI/pci-error-recovery.rst
+ * @tsm_handler: Optional driver callbacks to handle TSM requirements.
  * @groups:	Sysfs attribute groups.
  * @dev_groups: Attributes attached to the device that will be
  *              created once it is bound to the driver.
@@ -982,6 +984,7 @@ struct pci_driver {
 	int  (*sriov_set_msix_vec_count)(struct pci_dev *vf, int msix_vec_count); /* On PF */
 	u32  (*sriov_get_vf_total_msix)(struct pci_dev *pf);
 	const struct pci_error_handlers *err_handler;
+	struct pci_tsm_handlers *tsm_handler;
 	const struct attribute_group **groups;
 	const struct attribute_group **dev_groups;
 	struct device_driver	driver;

---

## [29] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 28/30] vfio/pci: Implement TSM handlers for MMIO*

VFIO invalidates MMIOs on disable_mmio() so that KVM could unmap them
from S-EPT. VFIO re-validate MMIOs on recover_mmio() so that KVM could
map them again for shared assigned device.

For now these handlers are mainly for Intel TDX Connect, but should
have no impact since other platform TSM drivers don't call these
handlers.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/vfio_pci.c      |  1 +
 drivers/vfio/pci/vfio_pci_core.c | 26 ++++++++++++++++++++++++++
 include/linux/vfio_pci_core.h    |  1 +
 3 files changed, 28 insertions(+)

diff --git a/drivers/vfio/pci/vfio_pci.c b/drivers/vfio/pci/vfio_pci.c
index 5ba39f7623bb..df25a3083fb0 100644
--- a/drivers/vfio/pci/vfio_pci.c
+++ b/drivers/vfio/pci/vfio_pci.c
@@ -202,6 +202,7 @@ static struct pci_driver vfio_pci_driver = {
 	.remove			= vfio_pci_remove,
 	.sriov_configure	= vfio_pci_sriov_configure,
 	.err_handler		= &vfio_pci_core_err_handlers,
+	.tsm_handler		= &vfio_pci_core_tsm_handlers,
 	.driver_managed_dma	= true,
 };
 
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index a8437fcecca1..405461583e2f 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -20,6 +20,7 @@
 #include <linux/mutex.h>
 #include <linux/notifier.h>
 #include <linux/pci.h>
+#include <linux/pci-tsm.h>
 #include <linux/pfn_t.h>
 #include <linux/pm_runtime.h>
 #include <linux/slab.h>
@@ -1452,6 +1453,31 @@ static int vfio_pci_ioctl_ioeventfd(struct vfio_pci_core_device *vdev,
 				  ioeventfd.fd);
 }
 
+static void vfio_pci_core_tsm_disable_mmio(struct pci_dev *pdev)
+{
+	struct vfio_pci_core_device *vdev = dev_get_drvdata(&pdev->dev);
+
+	down_write(&vdev->memory_lock);
+	vfio_pci_dma_buf_move(vdev, true);
+	up_write(&vdev->memory_lock);
+}
+
+static void vfio_pci_core_tsm_recover_mmio(struct pci_dev *pdev)
+{
+	struct vfio_pci_core_device *vdev = dev_get_drvdata(&pdev->dev);
+
+	down_write(&vdev->memory_lock);
+	if (__vfio_pci_memory_enabled(vdev))
+		vfio_pci_dma_buf_move(vdev, false);
+	up_write(&vdev->memory_lock);
+}
+
+struct pci_tsm_handlers vfio_pci_core_tsm_handlers = {
+	.disable_mmio = vfio_pci_core_tsm_disable_mmio,
+	.recover_mmio = vfio_pci_core_tsm_recover_mmio,
+};
+EXPORT_SYMBOL_GPL(vfio_pci_core_tsm_handlers);
+
 static int vfio_pci_ioctl_tsm_bind(struct vfio_pci_core_device *vdev,
 				   void __user *arg)
 {
diff --git a/include/linux/vfio_pci_core.h b/include/linux/vfio_pci_core.h
index b2982100221f..7da71b861d87 100644
--- a/include/linux/vfio_pci_core.h
+++ b/include/linux/vfio_pci_core.h
@@ -111,6 +111,7 @@ void vfio_pci_core_release_dev(struct vfio_device *core_vdev);
 int vfio_pci_core_register_device(struct vfio_pci_core_device *vdev);
 void vfio_pci_core_unregister_device(struct vfio_pci_core_device *vdev);
 extern const struct pci_error_handlers vfio_pci_core_err_handlers;
+extern struct pci_tsm_handlers vfio_pci_core_tsm_handlers;
 int vfio_pci_core_sriov_configure(struct vfio_pci_core_device *vdev,
 				  int nr_virtfn);
 long vfio_pci_core_ioctl(struct vfio_device *core_vdev, unsigned int cmd,

---

## [30] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 29/30] iommufd/vdevice: Implement TSM handlers for trusted DMA*

IOMMUFD implements disable_trusted_dma() handler to clean up trusted
DMA configuration when device is to be unbound.

For now these handlers are mainly for Intel TDX Connect, but should
have no impact since other platform TSM drivers don't call these
handlers.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/iommufd/viommu.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index c64ce1a9f87d..b7281a4422ff 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -255,8 +255,16 @@ static void iommufd_vdevice_disable_trusted_dma(struct iommufd_vdevice *vdev)
 	vdev->trusted_dma_enabled = false;
 }
 
+static void pci_driver_disable_trusted_dma(struct pci_dev *pdev)
+{
+	struct iommufd_vdevice *vdev = pdev->trusted_dma_owner;
+
+	iommufd_vdevice_disable_trusted_dma(vdev);
+}
+
 int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev)
 {
+	struct pci_dev *pdev = to_pci_dev(vdev->dev);
 	struct kvm *kvm;
 	int rc;
 
@@ -272,6 +280,9 @@ int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev)
 		goto out_unlock;
 	}
 
+	pdev->trusted_dma_owner = vdev;
+	pdev->driver->tsm_handler->disable_trusted_dma = pci_driver_disable_trusted_dma;
+
 	rc = iommufd_vdevice_enable_trusted_dma(vdev);
 	if (rc)
 		goto out_unlock;
@@ -292,12 +303,16 @@ int iommufd_vdevice_tsm_bind(struct iommufd_vdevice *vdev)
 
 void iommufd_vdevice_tsm_unbind(struct iommufd_vdevice *vdev)
 {
+	struct pci_dev *pdev = to_pci_dev(vdev->dev);
+
 	mutex_lock(&vdev->tsm_lock);
 	if (!vdev->tsm_bound)
 		goto out_unlock;
 
 	pci_tsm_unbind(to_pci_dev(vdev->dev));
 	iommufd_vdevice_disable_trusted_dma(vdev);
+	pdev->trusted_dma_owner = NULL;
+	pdev->driver->tsm_handler->disable_trusted_dma = NULL;
 	vdev->tsm_bound = false;
 
 out_unlock:

---

## [31] Xu Yilun — 2025-05-29
*Subject: [RFC PATCH 30/30] coco/tdx_tsm: Manage TDX Module enforced operation sequences for Unbind*

Implement TDX Connect enforced sequences for TSM unbind. The enforced
sequences are:

  1. STOP TDI via TDISP message STOP_INTERFACE
  2. Private MMIO unmap from Secure EPT
  3. Trusted Device Context Table cleanup for the TDI
  4. TDI ownership reclaim and metadata free

Step 2 is the responsibility of KVM, step 3 is for IOMMU driver. So
TDX TSM driver needs to invoke TSM handlers for external collaboration.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/host/tdx_tsm.c | 17 +++++++++++++----
 1 file changed, 13 insertions(+), 4 deletions(-)

diff --git a/drivers/virt/coco/host/tdx_tsm.c b/drivers/virt/coco/host/tdx_tsm.c
index beb65f45b478..66d6019812ca 100644
--- a/drivers/virt/coco/host/tdx_tsm.c
+++ b/drivers/virt/coco/host/tdx_tsm.c
@@ -87,6 +87,15 @@ static struct pci_tdi *tdx_tsm_bind(struct pci_dev *pdev,
 {
 	int ret;
 
+	if (!pdev->trusted_dma_owner ||
+	    !pdev->driver->tsm_handler ||
+	    !pdev->driver->tsm_handler->disable_mmio ||
+	    !pdev->driver->tsm_handler->recover_mmio ||
+	    !pdev->driver->tsm_handler->disable_trusted_dma) {
+		pci_err(pdev, "%s no driver or driver not support bind\n", __func__);
+		return NULL;
+	}
+
 	struct tdx_tdi *ttdi __free(kfree) =
 		kzalloc(sizeof(*ttdi), GFP_KERNEL);
 	if (!ttdi)
@@ -137,15 +146,15 @@ static struct pci_tdi *tdx_tsm_bind(struct pci_dev *pdev,
 static void tdx_tsm_unbind(struct pci_tdi *tdi)
 {
 	struct tdx_tdi *ttdi = to_tdx_tdi(tdi);
+	struct pci_dev *pdev = tdi->pdev;
 
-	/*
-	 * TODO: In fact devif cannot be freed before TDI's private MMIOs and
-	 * private DMA are unmapped. Will handle this restriction later.
-	 */
 	tdx_tdi_request(ttdi, TDX_TDI_REQ_STOP);
+	pdev->driver->tsm_handler->disable_mmio(pdev);
+	pdev->driver->tsm_handler->disable_trusted_dma(pdev);
 	tdx_tdi_mmiomt_free(ttdi);
 	tdx_tdi_devif_free(ttdi);
 	tdx_tdi_devifmt_free(ttdi);
+	pdev->driver->tsm_handler->recover_mmio(pdev);
 	pci_dev_put(ttdi->tdi.dsm_dev);
 	kfree(ttdi);
 }

---

## [32] Aneesh Kumar K.V — 2025-06-01
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> Add new IOCTLs to do TSM based TDI bind/unbind. These IOCTLs are
> expected to be called by userspace when CoCo VM issues TDI bind/unbind

Any reason these need to be a vfio ioctl instead of iommufd ioctl?
For ex: https://lore.kernel.org/all/20250529133757.462088-3-aneesh.kumar@kernel.org/

>
> Suggested-by: Jason Gunthorpe <jgg@nvidia.com>

This should be part of pci_tsm_bind() ? 

> +
> +	ret = vfio_iommufd_tsm_bind(&vdev->vdev, tsm_bind.vdevice_id);


-aneesh

---

## [33] Aneesh Kumar K.V — 2025-06-02
*Subject: Re: [RFC PATCH 20/30] vfio/pci: Do TSM Unbind before zapping bars*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> When device is TSM Bound, some of its MMIO regions are controlled by
> secure firmware. E.g. TDX Connect would require these MMIO regions

Don't we need to re-bind the vdev with tsm_bind for the continued use of TDI?

>  		} else {
> @@ -712,6 +713,7 @@ static void vfio_lock_and_set_power_state(struct vfio_pci_core_device *vdev,

Do we really need to check vdev->is_tsm_bound? The tsm_ops lock already
ensures that concurrent TSM operations can't happen, and repeated calls
to bind()/unbind() seem to be handled safely by pci_tsm_bind and pci_tsm_unbind.

> +}
> +

If is_tsm_bound is no longer needed, and pci_release_regions /
request_region_exclusive are now handled within pci_tsm_unbind / bind,
do we still need mutex_lock() to guard this path?

> +
>  static int vfio_pci_ioctl_tsm_unbind(struct vfio_pci_core_device *vdev,

---

## [34] Aneesh Kumar K.V — 2025-06-02
*Subject: Re: [RFC PATCH 17/30] iommufd/device: Add TSM Bind/Unbind for TIO
 support*

Xu Yilun <yilun.xu@linux.intel.com> writes:

....

> +/**
> + * iommufd_device_tsm_bind - Move a device to TSM Bind state

Do we really need this refcount_inc? As I understand it, the objects
aren't being pinned directly. Instead, the reference count seems to be
used more as a way to establish an object hierarchy, ensuring that
objects are freed in the correct order.

In vfio_pci_core_close_device(), you’re decrementing the reference, and
on the iommufd side, we’re covered because the VFIO bind operation takes
a file reference (fget)—so iommufd_fops_release() won’t be called
prematurely.

Wouldn’t it be simpler to skip the reference count increment altogether
and just call tsm_unbind in the virtual device’s destroy callback?
(iommufd_vdevice_destroy())

> +	goto out_put_vdev;
> +

-aneesh

---

## [35] Aneesh Kumar K.V — 2025-06-02
*Subject: Re: [RFC PATCH 27/30] PCI/TSM: Add PCI driver callbacks to handle
 TSM requirements*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> Add optional PCI driver callbacks to notify TSM events. For now, these
> handlers may be called during pci_tsm_unbind(). By calling these

It looks like the TSM feature is currently interacting with several
components: struct pci_driver, VFIO, iommufd, and pci_tsm_ops.

Should we consider limiting this scattering? Would it make sense to
encapsulate this logic within pci_tsm_ops?

-aneesh

---

## [36] Jason Gunthorpe — 2025-06-02
*Subject: Re: [RFC PATCH 10/30] vfio/pci: Export vfio dma-buf specific info
 for importers*

On Thu, May 29, 2025 at 01:34:53PM +0800, Xu Yilun wrote:
> Export vfio dma-buf specific info by attaching vfio_dma_buf_data in
> struct dma_buf::priv. Provide a helper vfio_dma_buf_get_data() for

This doesn't seem right, it should be encapsulated into the standard
DMABUF API in some way.

Jason

---

## [37] Jason Gunthorpe — 2025-06-02
*Subject: Re: [RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for TDISP
 using TSM*

On Thu, May 29, 2025 at 01:34:43PM +0800, Xu Yilun wrote:

> This series has 3 sections:

I really think this is too big to try to progress, even in RFC
form.
 
> Patch 1 - 11 deal with the private MMIO mapping in KVM MMU via DMABUF.
> Leverage Jason & Vivek's latest VFIO dmabuf series [3], see Patch 2 - 4.

I would probably split this out entirely into its own topic. It
doesn't seem directly related to TSM as KVM can use DMABUF for good
reasons independently .

> Patch 12 - 22 is about TSM Bind/Unbind/Guest request management in VFIO
> & IOMMUFD. Picks some of Shameer's patch in [5], see Patch 12 & 14.

This is some reasonable topic on its own after Dan's series
 
> Patch 23 - 30 is a solution to meet the TDX specific sequence
> enforcement on various device Unbind cases, including converting device

Then you have a series or two to implement TDX using the infrastructure.

Jason

---

## [38] Xu Yilun — 2025-06-02
*Subject: Re: [RFC PATCH 20/30] vfio/pci: Do TSM Unbind before zapping bars*

On Mon, Jun 02, 2025 at 10:50:11AM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

I choose not to re-bind because host basically cannot recover
everything. The guest does 'bind', 'attest', 'accept' to make a trusted
device, but for this series VFIO is only aware of 'bind' and can only
recover 'bind', which doesn't make much sense.  So I think just make
guest fully aware of TDISP rules, guest should expect writing MSE breaks
private state, and should do 'bind', 'attest', 'accept' again for
recovery if it wants to.

> 
> >  		} else {

It is mainly for pci_release_regions(). I remember there is a concern
about whether pci_request/release_region() should be in VFIO driver,
maybe lets solve that concern first in that thread.

> 
> > +}

We may still need the dev_set->lock. The vfio_pci/iommufd_device_tsm_bind()
not only does pci_tsm_bind(), but also secure IOMMU setup which affects
all devices in the dev_set.

Maybe I worried too much, I doesn't know there exists a real secure device
set.

Thanks,
Yilun

---

## [39] Aneesh Kumar K.V — 2025-06-02
*Subject: Re: [RFC PATCH 20/30] vfio/pci: Do TSM Unbind before zapping bars*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> When device is TSM Bound, some of its MMIO regions are controlled by
> secure firmware. E.g. TDX Connect would require these MMIO regions

For a secure device mmio range instead of vfio_pci_zap_and_down_write_memory_lock()
-> unmap_mapping_range() we want the vfio_pci_dma_buf_move right? Also
is that expected to get called twice as below?

vfio_pci_tsm_unbind-> pci_tsm_unbind -> tdx_tsm_unbind ->
tsm_handler->disable_mmio() -> vfio_pci_core_tsm_disable_mmio -> vfio_pci_dma_buf_move(vdev, true);

-aneesh

---

## [40] Xu Yilun — 2025-06-02
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Sun, Jun 01, 2025 at 04:15:32PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

A general reason is, the device driver - VFIO should be aware of the
bound state, and some operations break the bound state. VFIO should also
know some operations on bound may crash kernel because of platform TSM
firmware's enforcement. E.g. zapping MMIO, because private MMIO mapping
in secure page tables cannot be unmapped before TDI STOP [1].

Specifically, for TDX Connect, the firmware enforces MMIO unmapping in
S-EPT would fail if TDI is bound. For AMD there seems also some
requirement about this but I need Alexey's confirmation.

[1] https://lore.kernel.org/all/aDnXxk46kwrOcl0i@yilunxu-OptiPlex-7050/

> 
> >

I'm not quite sure. My feelig is this method is specific for VFIO
driver. Many other drivers just request regions on probe(), they can
never bind successfully if pci tsm hide this implementation internally.

Thanks,
Yilun

---

## [41] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 20/30] vfio/pci: Do TSM Unbind before zapping bars*

On Mon, Jun 02, 2025 at 07:30:15PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

Yes.

> Also is that expected to get called twice as below?

Yes for TDX Connect. First time zap the private MMIOs during unbind.
Second time block all mmio mapping.

Other platforms don't need these tsm handlers. They don't have this
awkwardness.

Thanks,
Yilun

> 
> vfio_pci_tsm_unbind-> pci_tsm_unbind -> tdx_tsm_unbind ->

---

## [42] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 10/30] vfio/pci: Export vfio dma-buf specific info
 for importers*

On Mon, Jun 02, 2025 at 10:30:09AM -0300, Jason Gunthorpe wrote:
> On Thu, May 29, 2025 at 01:34:53PM +0800, Xu Yilun wrote:
> > Export vfio dma-buf specific info by attaching vfio_dma_buf_data in

OK.

> 
> Jason

---

## [43] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 27/30] PCI/TSM: Add PCI driver callbacks to handle
 TSM requirements*

On Mon, Jun 02, 2025 at 06:36:37PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

I'm keeping on trying which is a better solution. Encapsulating all in
pci_tsm_ops is the most attactive one from SW POV, but only if the TSM
operations has no impact/dependency to other components. Unfortunately
it is not true, e.g. the private MMIO mapping/unmapping is actually
a writting to leaf S-EPT entry, but it requires non-leaf page-table-page
management in KVM.

Thanks,
Yilun

> 
> -aneesh

---

## [44] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 17/30] iommufd/device: Add TSM Bind/Unbind for TIO
 support*

On Mon, Jun 02, 2025 at 06:13:16PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

The idev refcount is not necessary, it is just to "catch caller bug".

> aren't being pinned directly. Instead, the reference count seems to be
> used more as a way to establish an object hierarchy, ensuring that

Correct.

> 
> Wouldn’t it be simpler to skip the reference count increment altogether

The vdevice refcount is the main concern, there is also an IOMMU_DESTROY
ioctl. User could just free the vdevice instance if no refcount, while VFIO
is still in bound state. That seems not the correct free order.

Thanks,
Yilun

> 
> > +	goto out_put_vdev;

---

## [45] Jason Gunthorpe — 2025-06-03
*Subject: Re: [RFC PATCH 17/30] iommufd/device: Add TSM Bind/Unbind for TIO
 support*

On Tue, Jun 03, 2025 at 02:20:51PM +0800, Xu Yilun wrote:
> > Wouldn’t it be simpler to skip the reference count increment altogether
> > and just call tsm_unbind in the virtual device’s destroy callback?

Freeing the vdevice should automatically unbind it..

Jason

---

## [46] Aneesh Kumar K.V — 2025-06-04
*Subject: Re: [RFC PATCH 17/30] iommufd/device: Add TSM Bind/Unbind for TIO
 support*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Tue, Jun 03, 2025 at 02:20:51PM +0800, Xu Yilun wrote:
>> > Wouldn’t it be simpler to skip the reference count increment altogether

One challenge I ran into during implementation was the dependency of
vfio on iommufd_device. When vfio needs to perform a tsm_unbind,
it only has access to an iommufd_device.

However, TSM operations like binding and unbinding are handled at the
iommufd_vdevice level. The issue? There’s no direct link from
iommufd_device back to iommufd_vdevice.

To address this, I modified the following structures:

modified   drivers/iommu/iommufd/iommufd_private.h
@@ -428,6 +428,7 @@ struct iommufd_device {
 	/* protect iopf_enabled counter */
 	struct mutex iopf_lock;
 	unsigned int iopf_enabled;
+	struct iommufd_vdevice *vdev;
 };
 
 static inline struct iommufd_device *
@@ -613,6 +614,7 @@ struct iommufd_vdevice {
 	struct iommufd_object obj;
 	struct iommufd_ctx *ictx;
 	struct iommufd_viommu *viommu;
+	struct iommufd_device *idev;
 	struct device *dev;
 	struct mutex	mutex;	/* mutex to synchronize updates to tsm_bound */
 	u64 id; /* per-vIOMMU virtual ID */

These fields are updated during tsm_bind and tsm_unbind, so they must be
protected by the appropriate locks:

Updating vdevice->idev requires holding vdev->mutex (vdev_lock).
Updating device->vdev requires idev->igroup->lock (idev_lock).

tsm_unbind in vdevice_destroy:

vdevice_destroy() ends up calling tsm_unbind() while holding only the
vdev_lock. At first glance, this seems unsafe. But in practice, it's
fine because the corresponding iommufd_device has already been destroyed
when the VFIO device file descriptor was closed—triggering
vfio_df_iommufd_unbind().

I’ve added an in-code comment to explain why tsm_unbind() is safe here
without acquiring the idev_lock. Hope that is ok.

-aneesh

---

## [47] Jason Gunthorpe — 2025-06-04
*Subject: Re: [RFC PATCH 17/30] iommufd/device: Add TSM Bind/Unbind for TIO
 support*

On Wed, Jun 04, 2025 at 02:10:43PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@nvidia.com> writes:
> 

VFIO should never do that except by destroying the idevice..

> However, TSM operations like binding and unbinding are handled at the
> iommufd_vdevice level. The issue? There’s no direct link from

Yes.
 
> To address this, I modified the following structures:
> 

Locking will be painful:

> Updating vdevice->idev requires holding vdev->mutex (vdev_lock).
> Updating device->vdev requires idev->igroup->lock (idev_lock).

I wonder if that can work on the destory paths..

You also have to prevent more than one vdevice from being created for
an idevice, I don't think we do that today.

> tsm_unbind in vdevice_destroy:
> 

This needs some kind of fixing the idevice should destroy the vdevices
during idevice destruction so we don't get this out of order where the
idevice is destroyed before the vdevice.

This should be a separate patch as it is an immediate bug fix..

Jason

---

## [48] Aneesh Kumar K.V — 2025-06-04
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Sun, Jun 01, 2025 at 04:15:32PM +0530, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

According to the TDISP specification (Section 11.2.6), clearing either
the Bus Master Enable (BME) or Memory Space Enable (MSE) bits will cause
the TDI to transition to an error state. To handle this gracefully, it
seems necessary to unbind the TDI before modifying the BME or MSE bits.

If I understand correctly, we also need to unmap the Stage-2 mapping due
to the issue described in commit
abafbc551fddede3e0a08dee1dcde08fc0eb8476. Are there any additional
reasons we would want to unmap the Stage-2 mapping for the BAR (as done
in vfio_pci_zap_and_down_write_memory_lock)?

Additionally, with TDX, it appears that before unmapping the Stage-2
mapping for the BAR, we should first unbind the TDI (ie, move it to the
"unlock" state?) Is this step related Section 11.2.6 of the TDISP spec,
or is it driven by a different requirement?

-aneesh

---

## [49] Xu Yilun — 2025-06-05
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Wed, Jun 04, 2025 at 07:07:18PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

Yes. But now the suggestion is never let VFIO do unbind, instead VFIO
should block these operations when device is bound.

> 
> If I understand correctly, we also need to unmap the Stage-2 mapping due

I think no more reason. 

> 
> Additionally, with TDX, it appears that before unmapping the Stage-2

No, this is not device side TDISP requirement. It is host side
requirement to fix DMA silent drop issue. TDX enforces CPU S2 PT share
with IOMMU S2 PT (does ARM do the same?), so unmap CPU S2 PT in KVM equals
unmap IOMMU S2 PT.

If we allow IOMMU S2 PT unmapped when TDI is running, host could fool
guest by just unmap some PT entry and suppress the fault event. Guest
thought a DMA writting is successful but it is not and may cause
data integrity issue.

This is not a TDX specific problem, but different vendors has different
mechanisms for this. For TDX, firmware fails the MMIO unmap for S2. For
AMD, will trigger some HW protection called "ASID fence" [1]. Not sure
how ARM handles this?

https://lore.kernel.org/all/aDnXxk46kwrOcl0i@yilunxu-OptiPlex-7050/

Thanks,
Yilun

> 
> -aneesh

---

## [50] Aneesh Kumar K.V — 2025-06-05
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> Add new IOCTLs to do TSM based TDI bind/unbind. These IOCTLs are
> expected to be called by userspace when CoCo VM issues TDI bind/unbind

....

> +
> +	/* To ensure no host side MMIO access is possible */

I am hitting failures here with similar changes. Can you share the Qemu
changes needed to make this pci_request_regions_exclusive successful.
Also after the TDI is unbound, we want the region ownership backto
"vfio-pci" so that things continue to work as non-secure device. I don't
see we doing that. I could add a pci_bar_deactivate/pci_bar_activate in
userspace which will result in vfio_unmap()/vfio_map(). But that doesn't
release the region ownership.


> +	ret = vfio_iommufd_tsm_bind(&vdev->vdev, tsm_bind.vdevice_id);
> +	if (ret)

-aneesh

---

## [51] Jason Gunthorpe — 2025-06-05
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Thu, Jun 05, 2025 at 05:41:17PM +0800, Xu Yilun wrote:

> No, this is not device side TDISP requirement. It is host side
> requirement to fix DMA silent drop issue. TDX enforces CPU S2 PT share

So, TDX prevents *any* unmap, even of normal memory, from the S2 while
a guest is running?  Seems extreme?

MMIO isn't special, if you have a rule like that for such a security
reason it should cover all of the S2.

> This is not a TDX specific problem, but different vendors has different
> mechanisms for this. For TDX, firmware fails the MMIO unmap for S2. For

This seems even more extreme, if the guest gets a bad DMA address into
the device then the entire device gets killed? No chance to debug it?

Jason

---

## [52] Jason Gunthorpe — 2025-06-05
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Thu, Jun 05, 2025 at 05:33:52PM +0530, Aneesh Kumar K.V wrote:

> > +
> > +	/* To ensure no host side MMIO access is possible */

Again, IMHO, we should not be doing this dynamically. VFIO should do
pci_request_regions_exclusive() once at the very start and it should
stay that way.

There is no reason to change it dynamically.

The only decision to make is if all vfio should switch to exclusive
mode or if we need to make it optional for userspace.

Jason

---

## [53] Aneesh Kumar K.V — 2025-06-05
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Wed, Jun 04, 2025 at 07:07:18PM +0530, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

MMIO/BAR Unmapping:
If the stage-2 mapping is removed while the device is in a locked state—a
scenario that ARM permits—the granule transitions to the RIPAS_DESTROYED and
HIPAS_UNASSIGNED states. Any MMIO or CPU access to such a granule will trigger a
non-emulatable data abort, which is forwarded to the non-secure hypervisor
(e.g., KVM).

However, at this point, the system cannot make further progress. The unmapping
was initiated by the host without coordination from the guest, leaving the
granule in a broken state.

A more robust workflow would involve the guest first transitioning the granule
to RIPAS_EMPTY, followed by the host unmapping the stage-2 entry.

IOMMU Page Table Unmap:
Both the CPU and the SMMU can share the stage-2 page table. If the non-secure
host unmaps an entry from this shared page table, the affected granule again
transitions to RIPAS_DESTROYED and HIPAS_UNASSIGNED.

In this case, a DMA transaction—(SMMU is configured by the Realm Management
Monitor,RMM)—can be terminated. This typically results in an event being
recorded in the event queue which can be read by RMM.

However, interrupt delivery remains under non-secure host control, and
the guest may not be immediately aware that the DMA transaction was
terminated. I am currently confirming this behavior with the design team
and will follow up once I have clarity.

-aneesh

---

## [54] Aneesh Kumar K.V — 2025-06-05
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Thu, Jun 05, 2025 at 05:33:52PM +0530, Aneesh Kumar K.V wrote:
>

We only need the exclusive mode when the device is operating in secure
mode, correct? That suggests we’ll need to dynamically toggle this
setting based on the device’s security state.

-aneesh

---

## [55] Jason Gunthorpe — 2025-06-05
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Thu, Jun 05, 2025 at 09:47:01PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@nvidia.com> writes:
> 

No, if the decision is that VFIO should allow this to be controlled by
userspace then userspace will tell iommufd to run in regions_exclusive
mode prior to opening the vfio cdev and VFIO will still do it once at
open time and never change it.

The only thing request_regions does is block other drivers outside
vfio from using this memory space. There is no reason at all to change
this dynamically. A CC VMM using VFIO will never use a driver outside
VFIO to touch the VFIO controlled memory.

Jason

---

## [56] Xu Yilun — 2025-06-06
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Thu, Jun 05, 2025 at 12:09:16PM -0300, Jason Gunthorpe wrote:
> On Thu, Jun 05, 2025 at 05:41:17PM +0800, Xu Yilun wrote:
> 

Prevents any unmap *not intended* by guest, even for normal memory.

Guest could show its unmapping intention by issuing an "page release"
firmware call then host is OK to unmap. This for normal memory.

For MMIO, Guest implicitly hwo the intention by unbind the TDI first.

> 
> MMIO isn't special, if you have a rule like that for such a security

It does.

Thanks,
Yilun

> 
> > This is not a TDX specific problem, but different vendors has different

---

## [57] Xu Yilun — 2025-06-06
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Thu, Jun 05, 2025 at 01:33:39PM -0300, Jason Gunthorpe wrote:
> On Thu, Jun 05, 2025 at 09:47:01PM +0530, Aneesh Kumar K.V wrote:
> > Jason Gunthorpe <jgg@nvidia.com> writes:

Jason has described the suggested static lockdown flow and we could
try on that.  I just wanna help position your immediate failure.

Maybe you still have QEMU mmapped the MMIO region.

int vfio_pci_core_mmap()
{
...

	if (!vdev->barmap[index]) {
		ret = pci_request_selected_regions(pdev,
						   1 << index, "vfio-pci");
...
}

Even for static lockdown, userspace should not mmap the MMIOs anymore.

Thanks,
Yilun

> > >> Also after the TDI is unbound, we want the region ownership backto
> > >> "vfio-pci" so that things continue to work as non-secure device. I don't

---

## [58] Aneesh Kumar K.V — 2025-06-06
*Subject: Re: [RFC PATCH 17/30] iommufd/device: Add TSM Bind/Unbind for TIO
 support*

Jason Gunthorpe <jgg@nvidia.com> writes:

....

>> tsm_unbind in vdevice_destroy:
>> 

Something like below?

diff --git a/drivers/iommu/iommufd/device.c b/drivers/iommu/iommufd/device.c
index 86244403b532..a49b293bd516 100644
--- a/drivers/iommu/iommufd/device.c
+++ b/drivers/iommu/iommufd/device.c
@@ -221,6 +221,8 @@ struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
 	refcount_inc(&idev->obj.users);
 	/* igroup refcount moves into iommufd_device */
 	idev->igroup = igroup;
+	idev->vdev   = NULL;
+	mutex_init(&idev->lock);
 
 	/*
 	 * If the caller fails after this success it must call
@@ -282,6 +284,12 @@ EXPORT_SYMBOL_NS_GPL(iommufd_ctx_has_group, "IOMMUFD");
  */
 void iommufd_device_unbind(struct iommufd_device *idev)
 {
+	/* this will be unlocked while destroying the idev obj */
+	mutex_lock(&idev->lock);
+
+	if (idev->vdev)
+		/* extra refcount taken during vdevice alloc */
+		iommufd_object_destroy_user(idev->ictx, &idev->vdev->obj);
 	iommufd_object_destroy_user(idev->ictx, &idev->obj);
 }
 EXPORT_SYMBOL_NS_GPL(iommufd_device_unbind, "IOMMUFD");
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 9ccc83341f32..d85bd8b38751 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -425,6 +425,10 @@ struct iommufd_device {
 	/* always the physical device */
 	struct device *dev;
 	bool enforce_cache_coherency;
+	/* to protect the following members*/
+	struct mutex lock;
+	/* if there is a vdevice mapping the idev */
+	struct iommufd_vdevice *vdev;
 };
 
 static inline struct iommufd_device *
@@ -606,6 +610,7 @@ struct iommufd_vdevice {
 	struct iommufd_ctx *ictx;
 	struct iommufd_viommu *viommu;
 	struct device *dev;
+	struct iommufd_device *idev;
 	u64 id; /* per-vIOMMU virtual ID */
 };
 
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 3df468f64e7d..c38303df536f 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -172,6 +172,11 @@ int iommufd_object_remove(struct iommufd_ctx *ictx,
 		ictx->vfio_ioas = NULL;
 	xa_unlock(&ictx->objects);
 
+	if (obj->type == IOMMUFD_OBJ_DEVICE) {
+		/* idevice should be freed with lock held */
+		struct iommufd_device *idev = container_of(obj, struct iommufd_device, obj);
+		mutex_unlock(&idev->lock);
+	}
 	/*
 	 * Since users is zero any positive users_shortterm must be racing
 	 * iommufd_put_object(), or we have a bug.
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 01df2b985f02..17f189bc9e2c 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -84,15 +84,24 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	return rc;
 }
 
+/* This will be called from iommufd_device_unbind  */
 void iommufd_vdevice_destroy(struct iommufd_object *obj)
 {
 	struct iommufd_vdevice *vdev =
 		container_of(obj, struct iommufd_vdevice, obj);
 	struct iommufd_viommu *viommu = vdev->viommu;
+	struct iommufd_device *idev = vdev->idev;
+
+	/*
+	 * since we have an refcount on idev, it can't be freed.
+	 */
+	lockdep_assert_held(&idev->lock);
 
 	/* xa_cmpxchg is okay to fail if alloc failed xa_cmpxchg previously */
 	xa_cmpxchg(&viommu->vdevs, vdev->id, vdev, NULL, GFP_KERNEL);
 	refcount_dec(&viommu->obj.users);
+	idev->vdev = NULL;
+	refcount_dec(&idev->obj.users);
 	put_device(vdev->dev);
 }
 
@@ -124,10 +133,15 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 		goto out_put_idev;
 	}
 
+	mutex_lock(&idev->lock);
+	if (idev->vdev) {
+		rc = -EINVAL;
+		goto out_put_idev_unlock;
+	}
 	vdev = iommufd_object_alloc(ucmd->ictx, vdev, IOMMUFD_OBJ_VDEVICE);
 	if (IS_ERR(vdev)) {
 		rc = PTR_ERR(vdev);
-		goto out_put_idev;
+		goto out_put_idev_unlock;
 	}
 
 	vdev->id = virt_id;
@@ -147,10 +161,18 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	if (rc)
 		goto out_abort;
 	iommufd_object_finalize(ucmd->ictx, &vdev->obj);
-	goto out_put_idev;
+	/* don't allow idev free without vdev free */
+	refcount_inc(&idev->obj.users);
+	vdev->idev = idev;
+	/* vdev lifecycle now managed by idev */
+	idev->vdev = vdev;
+	refcount_inc(&vdev->obj.users);
+	goto out_put_idev_unlock;
 
 out_abort:
 	iommufd_object_abort_and_destroy(ucmd->ictx, &vdev->obj);
+out_put_idev_unlock:
+	mutex_unlock(&idev->lock);
 out_put_idev:
 	iommufd_put_object(ucmd->ictx, &idev->obj);
 out_put_viommu:

---

## [59] Aneesh Kumar K.V — 2025-06-06
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Thu, Jun 05, 2025 at 09:47:01PM +0530, Aneesh Kumar K.V wrote:
>> Jason Gunthorpe <jgg@nvidia.com> writes:

So this will be handled by setting
vdevice::flags = IOMMUFD_PCI_REGION_EXCLUSIVE in
iommufd_vdevice_alloc_ioctl()? And we set this flag when starting a
secure guest, regardless of whether the device is TEE-capable or not

and vfio_pci_core_mmap() will do

	if (!vdev->barmap[index]) {

		if (core_vdev->iommufd_device &&
		    iommufd_vdevice_region_exclusive(core_vdev->iommufd_device))
			ret = pci_request_selected_regions_exclusive(pdev,
							1 << index, "vfio-pci");
		else
			ret = pci_request_selected_regions(pdev,
						1 << index, "vfio-pci");




>
> The only thing request_regions does is block other drivers outside

-aneesh

---

## [60] Jason Gunthorpe — 2025-06-06
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Fri, Jun 06, 2025 at 03:02:49PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@nvidia.com> writes:
> 

Not like that.. I would suggest a global vfio sysfs or module parameter, or
maybe a iommufd ictx global option:

 IOMMU_OPTION(IOMMU_OPTION_OP_SET, IOMMU_OPTION_EXCLUSIVE_RANGES)

You want something simple here, not tied to vdevice or very dynamic.

The use cases for non-exclusive ranges are very narrow, IMHO

> and vfio_pci_core_mmap() will do
> 

And IMHO, these should be moved to probe time or at least FD open
time, not at mmap time...

Jason

---

## [61] Alexey Kardashevskiy — 2025-06-11
*Subject: Re: [RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for TDISP
 using TSM*

Hi,

Is there a QEMU tree using this somewhere?
Also it would be nice to have this tree pushed somewhere, saves time. Thanks,



On 29/5/25 15:34, Xu Yilun wrote:
> This series is the generic host side (KVM/VFIO/IOMMUFD) support for the
> whole life cycle of private device assignment. It follows the

---

## [62] Aneesh Kumar K.V — 2025-06-16
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Wed, Jun 04, 2025 at 07:07:18PM +0530, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

I am still trying to find more details here. How did the guest conclude
DMA writing is successful? Guest would timeout waiting for DMA to complete
if the host hides the interrupt delivery of failed DMA transfer?

>
> This is not a TDX specific problem, but different vendors has different

-aneesh

---

## [63] Xu Yilun — 2025-06-18
*Subject: Re: [RFC PATCH 19/30] vfio/pci: Add TSM TDI bind/unbind IOCTLs for
 TEE-IO support*

On Mon, Jun 16, 2025 at 01:46:42PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

Traditionally VMM is the trusted entity. If there is no IOMMU fault
reported, guest assumes DMA writing is successful.

> Guest would timeout waiting for DMA to complete

There is no *generic* machanism to detect or wait for a single DMA
write completion. They are "posted" in terms of PCIe.

Thanks,
Yilun

> if the host hides the interrupt delivery of failed DMA transfer?
>

---

## [64] Xu Yilun — 2025-06-20
*Subject: Re: [RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for TDISP
 using TSM*

On Mon, Jun 02, 2025 at 10:37:27AM -0300, Jason Gunthorpe wrote:
> On Thu, May 29, 2025 at 01:34:43PM +0800, Xu Yilun wrote:
> 

Sorry, I missed this message...

Yeah, I just try to give a overview of what components we need, what the
expect flow would be like for the first time. Also vendors need as much
components as possible to enable their own HW and verify this flow works.

We could split into small topics then.

>  
> > Patch 1 - 11 deal with the private MMIO mapping in KVM MMU via DMABUF.

Yes, since I'm not work on improving this for now, I'll not include this
part next time. Will start independent thread if there is update.

> 
> > Patch 12 - 22 is about TSM Bind/Unbind/Guest request management in VFIO

OK, I'll just focus on this for next version.

>  
> > Patch 23 - 30 is a solution to meet the TDX specific sequence

Yeah, this should happen after "IOMMUFD for trusted".

Thanks,
Yilun

> 
> Jason

---

## [65] Alexey Kardashevskiy — 2025-06-21
*Subject: Re: [RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for TDISP
 using TSM*

On 11/6/25 11:55, Alexey Kardashevskiy wrote:
> Hi,
> 

Ping? Thanks,


> Also it would be nice to have this tree pushed somewhere, saves time. Thanks,



> 
>

---

## [66] Xu Yilun — 2025-06-25
*Subject: Re: [RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for TDISP
 using TSM*

On Sat, Jun 21, 2025 at 11:07:24AM +1000, Alexey Kardashevskiy wrote:
> 
> 

Sorry for late. I've finally got a public tree.

https://github.com/yiliu1765/qemu/tree/zhenzhong/devsec_tsm

Again, I think the changes are far from good, just work for enabling.

Thanks,
Yilun

---

## [67] dan.j.williams@intel.com — 2025-07-11
*Subject: Re: [RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for TDISP
 using TSM*

Xu Yilun wrote:
> On Sat, Jun 21, 2025 at 11:07:24AM +1000, Alexey Kardashevskiy wrote:
> > 

At some point I want to stage a merge tree QEMU bits here:

https://git.kernel.org/pub/scm/linux/kernel/git/devsec/qemu.git/ (not
created yet)

...unless Paolo or others in QEMU community are open to running a
staging branch in qemu.git. At some point we need to collide all the
QEMU POC branches, and I expect that needs to happen and show some
success before the upstream projects start ingesting all these changes.

---

## [68] Jonathan Cameron — 2025-07-15
*Subject: Re: [RFC PATCH 00/30] Host side (KVM/VFIO/IOMMUFD) support for
 TDISP using TSM*

On Fri, 11 Jul 2025 16:08:16 -0700
dan.j.williams@intel.com wrote:

> Xu Yilun wrote:
> > On Sat, Jun 21, 2025 at 11:07:24AM +1000, Alexey Kardashevskiy wrote:  

Qemu relies heavily on gitlab infrastructure for testing - so annoying though it
is maybe we need to host the qemu tree there - possibly mirrored to
kernel.org.

Jonathan

---
