---
title: 'Add iommufd ioctls to support TSM operations'
date: 2026-05-25
last_reply: 2026-05-27
message_count: 14
participants: ['Aneesh Kumar K.V (Arm)', 'Anthony Krowiak', 'Alexey Kardashevskiy', 'Dan Williams (nvidia)', 'Tian, Kevin', 'Jason Gunthorpe']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-05-25

This patch series adds iommufd ioctl support for TSM-related operations.
These ioctls allow VMMs to perform TSM management tasks such as bind and
unbind operations, and to handle guest requests.

Changes from v4:
https://lore.kernel.org/all/20260427061005.901854-1-aneesh.kumar@kernel.org
* Switch VFIO/iommufd to use struct file *kvm_file instead of relying on
  kvm->users_count references.
* Define TSM request scope values globally in iommufd.
* Rename the ioctl to IOMMU_VDEVICE_TSM_REQ.
* Address other review feedback.

Changes from v2:
https://lore.kernel.org/all/20260309111704.2330479-1-aneesh.kumar@kernel.org
* Bump the series revision to v4 to keep it in sync with the dependent CCA DA
  patchsets. There was no v3 posting.
* Drop [PATCH v2 1/3] iommufd/viommu: Allow associating a KVM VM fd with a
  vIOMMU
* Add two new patches to associate a struct kvm * with iommufd objects:
  iommufd/device: Associate a kvm pointer to iommufd_device
  iommufd/viommu: Associate a kvm pointer to iommufd_viommu
* Address review feedback

Changes from v1:
https://lore.kernel.org/all/20250728135216.48084-8-aneesh.kumar@kernel.org
* Rebase onto the latest kernel
* Address review feedback
* Drop the TSM map ioctl; the KVM prefault patch will be used instead to
  ensure that private memory is preallocated

Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Bjorn Helgaas <helgaas@kernel.org>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Joerg Roedel <joro@8bytes.org>
Cc: Jonathan Cameron <jic23@kernel.org>
Cc: Kevin Tian <kevin.tian@intel.com>
Cc: Nicolin Chen <nicolinc@nvidia.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>
Cc: Paolo Bonzini <pbonzini@redhat.com>
Cc: Tony Krowiak <akrowiak@linux.ibm.com>
Cc: Halil Pasic <pasic@linux.ibm.com>
Cc: Jason Herne <jjherne@linux.ibm.com>
Cc: Harald Freudenberger <freude@linux.ibm.com>
Cc: Holger Dengler <dengler@linux.ibm.com>
Cc: Heiko Carstens <hca@linux.ibm.com>
Cc: Vasily Gorbik <gor@linux.ibm.com>
Cc: Alexander Gordeev <agordeev@linux.ibm.com>
Cc: Christian Borntraeger <borntraeger@linux.ibm.com>
Cc: Sven Schnelle <svens@linux.ibm.com>
Cc: Alex Williamson <alex@shazbot.org>
Cc: Matthew Rosato <mjrosato@linux.ibm.com>
Cc: Farhan Ali <alifm@linux.ibm.com>
Cc: Eric Farman <farman@linux.ibm.com>
Cc: linux-s390@vger.kernel.org

Aneesh Kumar K.V (Arm) (3):
  vfio: cache KVM VM file references instead of raw struct kvm pointers
  iommufd/tsm: add vdevice TSM bind/unbind ioctl
  iommufd/vdevice: add TSM request ioctl

Nicolin Chen (1):
  iommufd/viommu: Keep a reference to the KVM file

Shameer Kolothum (1):
  iommufd/device: Associate KVM file pointer with iommufd_device

 drivers/iommu/iommufd/Makefile          |   2 +
 drivers/iommu/iommufd/device.c          |   7 +-
 drivers/iommu/iommufd/iommufd_private.h |  16 +++
 drivers/iommu/iommufd/main.c            |   6 ++
 drivers/iommu/iommufd/selftest.c        |   2 +-
 drivers/iommu/iommufd/tsm.c             | 130 ++++++++++++++++++++++++
 drivers/iommu/iommufd/viommu.c          |   9 ++
 drivers/s390/crypto/vfio_ap_ops.c       |   5 +-
 drivers/vfio/device_cdev.c              |  10 +-
 drivers/vfio/group.c                    |  14 ++-
 drivers/vfio/iommufd.c                  |   3 +-
 drivers/vfio/pci/vfio_pci_zdev.c        |   7 +-
 drivers/vfio/vfio.h                     |  16 ++-
 drivers/vfio/vfio_main.c                |  81 ++++++++-------
 drivers/virt/coco/tsm-core.c            |  58 +++++++++++
 include/linux/iommufd.h                 |   5 +-
 include/linux/kvm_host.h                |   3 +
 include/linux/pci-tsm.h                 |   9 +-
 include/linux/tsm.h                     |  42 ++++++++
 include/linux/vfio.h                    |  17 +++-
 include/uapi/linux/iommufd.h            | 106 +++++++++++++++++++
 virt/kvm/kvm_main.c                     |   2 +
 22 files changed, 478 insertions(+), 72 deletions(-)
 create mode 100644 drivers/iommu/iommufd/tsm.c


base-commit: 50897c955902c93ae71c38698abb910525ebdc89

---

## [2] Aneesh Kumar K.V (Arm) — 2026-05-25
*Subject: [PATCH v5 1/5] vfio: cache KVM VM file references instead of raw struct kvm pointers*

VFIO currently records struct kvm pointers on vfio_group, vfio_device_file
and the opened vfio_device. Switch VFIO to track the VM's struct file
instead, so VFIO and iommufd can use normal file references for VM lifetime
instead of depending on KVM's internal struct kvm refcounting.

KVM_CREATE_DEVICE binds the KVM VM lifetime to the KVM device fd lifetime.
For KVM_DEV_TYPE_VFIO, the KVM VFIO device fd also takes references to each
VFIO file added through KVM_DEV_VFIO_FILE_ADD. The KVM VFIO device fd
therefore owns both the internal KVM reference and the VFIO file references
in kvf->file.

KVM_DEV_VFIO_FILE_ADD further installs the VM file association into the
VFIO file. VFIO converts the struct kvm pointer to a VM file reference with
get_file_active(&kvm->_file), because the KVM device fd can keep struct kvm
alive after the original VM fd is already in final release.

The association intentionally pins the VM file until KVM_DEV_VFIO_FILE_DEL
or until the KVM VFIO device fd is released. This gives VFIO/iommufd a
stable VM file reference source without taking a dependency on KVM's struct
kvm lifetime. The KVM VFIO device release path clears the VFIO-side
association before dropping its VFIO file references.

When a VFIO device is opened or bound, VFIO takes an additional reference
from the associated VM file and stores it in vfio_device::kvm_file for
driver and iommufd use. That open-time reference is released from
vfio_device_put_kvm() when the VFIO device is closed or unbound.

This gives the ownership model:

  - KVM device fd pins struct kvm through kvm->users_count
  - KVM VFIO device fd pins VFIO files through kvf->file
  - VFIO group/device-file state pins the VM file while associated with KVM
  - vfio_device::kvm_file pins the VM file during active VFIO device use

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/s390/crypto/vfio_ap_ops.c |  5 +-
 drivers/vfio/device_cdev.c        | 10 ++--
 drivers/vfio/group.c              | 14 +++---
 drivers/vfio/pci/vfio_pci_zdev.c  |  7 +--
 drivers/vfio/vfio.h               | 16 ++++--
 drivers/vfio/vfio_main.c          | 81 ++++++++++++++++---------------
 include/linux/kvm_host.h          |  3 ++
 include/linux/vfio.h              | 17 ++++++-
 virt/kvm/kvm_main.c               |  2 +
 9 files changed, 91 insertions(+), 64 deletions(-)

diff --git a/drivers/s390/crypto/vfio_ap_ops.c b/drivers/s390/crypto/vfio_ap_ops.c
index 44b3a1dcc1b3..05996a8fd860 100644
--- a/drivers/s390/crypto/vfio_ap_ops.c
+++ b/drivers/s390/crypto/vfio_ap_ops.c
@@ -2054,11 +2054,12 @@ static int vfio_ap_mdev_open_device(struct vfio_device *vdev)
 {
 	struct ap_matrix_mdev *matrix_mdev =
 		container_of(vdev, struct ap_matrix_mdev, vdev);
+	struct kvm *kvm = vfio_device_get_kvm(vdev);
 
-	if (!vdev->kvm)
+	if (!kvm)
 		return -EINVAL;
 
-	return vfio_ap_mdev_set_kvm(matrix_mdev, vdev->kvm);
+	return vfio_ap_mdev_set_kvm(matrix_mdev, kvm);
 }
 
 static void vfio_ap_mdev_close_device(struct vfio_device *vdev)
diff --git a/drivers/vfio/device_cdev.c b/drivers/vfio/device_cdev.c
index 54abf312cf04..ca75ab8eb7bd 100644
--- a/drivers/vfio/device_cdev.c
+++ b/drivers/vfio/device_cdev.c
@@ -56,7 +56,7 @@ int vfio_device_fops_cdev_open(struct inode *inode, struct file *filep)
 static void vfio_df_get_kvm_safe(struct vfio_device_file *df)
 {
 	spin_lock(&df->kvm_ref_lock);
-	vfio_device_get_kvm_safe(df->device, df->kvm);
+	vfio_device_get_kvm_safe(df->device, df->kvm_file);
 	spin_unlock(&df->kvm_ref_lock);
 }
 
@@ -133,10 +133,10 @@ long vfio_df_ioctl_bind_iommufd(struct vfio_device_file *df,
 	}
 
 	/*
-	 * Before the device open, get the KVM pointer currently
-	 * associated with the device file (if there is) and obtain
-	 * a reference.  This reference is held until device closed.
-	 * Save the pointer in the device for use by drivers.
+	 * Before the device open, get the VM struct file currently
+	 * associated with the device file (if there is one) and obtain a
+	 * reference. This reference is held until the device is closed.
+	 * Save the file in the device for use by drivers.
 	 */
 	vfio_df_get_kvm_safe(df);
 
diff --git a/drivers/vfio/group.c b/drivers/vfio/group.c
index b2299e5bc6df..8950cfb9405d 100644
--- a/drivers/vfio/group.c
+++ b/drivers/vfio/group.c
@@ -163,7 +163,7 @@ static int vfio_group_ioctl_set_container(struct vfio_group *group,
 static void vfio_device_group_get_kvm_safe(struct vfio_device *device)
 {
 	spin_lock(&device->group->kvm_ref_lock);
-	vfio_device_get_kvm_safe(device, device->group->kvm);
+	vfio_device_get_kvm_safe(device, device->group->kvm_file);
 	spin_unlock(&device->group->kvm_ref_lock);
 }
 
@@ -181,10 +181,10 @@ static int vfio_df_group_open(struct vfio_device_file *df)
 	mutex_lock(&device->dev_set->lock);
 
 	/*
-	 * Before the first device open, get the KVM pointer currently
-	 * associated with the group (if there is one) and obtain a reference
-	 * now that will be held until the open_count reaches 0 again.  Save
-	 * the pointer in the device for use by drivers.
+	 * Before the first device open, get the VM struct file currently
+	 * associated with the group (if there is one) and obtain a
+	 * reference now that will be held until the open_count reaches 0
+	 * again. Save the file in the device for use by drivers.
 	 */
 	if (device->open_count == 0)
 		vfio_device_group_get_kvm_safe(device);
@@ -862,9 +862,7 @@ bool vfio_group_enforced_coherent(struct vfio_group *group)
 
 void vfio_group_set_kvm(struct vfio_group *group, struct kvm *kvm)
 {
-	spin_lock(&group->kvm_ref_lock);
-	group->kvm = kvm;
-	spin_unlock(&group->kvm_ref_lock);
+	vfio_kvm_file_replace(&group->kvm_file, &group->kvm_ref_lock, kvm);
 }
 
 /**
diff --git a/drivers/vfio/pci/vfio_pci_zdev.c b/drivers/vfio/pci/vfio_pci_zdev.c
index 0990fdb146b7..a9d8e6aa3839 100644
--- a/drivers/vfio/pci/vfio_pci_zdev.c
+++ b/drivers/vfio/pci/vfio_pci_zdev.c
@@ -144,15 +144,16 @@ int vfio_pci_info_zdev_add_caps(struct vfio_pci_core_device *vdev,
 int vfio_pci_zdev_open_device(struct vfio_pci_core_device *vdev)
 {
 	struct zpci_dev *zdev = to_zpci(vdev->pdev);
+	struct kvm *kvm = vfio_device_get_kvm(&vdev->vdev);
 
 	if (!zdev)
 		return -ENODEV;
 
-	if (!vdev->vdev.kvm)
+	if (!kvm)
 		return 0;
 
 	if (zpci_kvm_hook.kvm_register)
-		return zpci_kvm_hook.kvm_register(zdev, vdev->vdev.kvm);
+		return zpci_kvm_hook.kvm_register(zdev, kvm);
 
 	return -ENOENT;
 }
@@ -161,7 +162,7 @@ void vfio_pci_zdev_close_device(struct vfio_pci_core_device *vdev)
 {
 	struct zpci_dev *zdev = to_zpci(vdev->pdev);
 
-	if (!zdev || !vdev->vdev.kvm)
+	if (!zdev || !vfio_device_get_kvm(&vdev->vdev))
 		return;
 
 	if (zpci_kvm_hook.kvm_unregister)
diff --git a/drivers/vfio/vfio.h b/drivers/vfio/vfio.h
index e4b72e79b7e3..41032104eb36 100644
--- a/drivers/vfio/vfio.h
+++ b/drivers/vfio/vfio.h
@@ -22,8 +22,8 @@ struct vfio_device_file {
 
 	u8 access_granted;
 	u32 devid; /* only valid when iommufd is valid */
-	spinlock_t kvm_ref_lock; /* protect kvm field */
-	struct kvm *kvm;
+	spinlock_t kvm_ref_lock; /* protect kvm_file */
+	struct file *kvm_file;
 	struct iommufd_ctx *iommufd; /* protected by struct vfio_device_set::lock */
 };
 
@@ -88,7 +88,7 @@ struct vfio_group {
 #endif
 	enum vfio_group_type		type;
 	struct mutex			group_lock;
-	struct kvm			*kvm;
+	struct file			*kvm_file;
 	struct file			*opened_file;
 	struct iommufd_ctx		*iommufd;
 	spinlock_t			kvm_ref_lock;
@@ -434,11 +434,17 @@ static inline void vfio_virqfd_exit(void)
 #endif
 
 #if IS_ENABLED(CONFIG_KVM)
-void vfio_device_get_kvm_safe(struct vfio_device *device, struct kvm *kvm);
+void vfio_kvm_file_replace(struct file **dst, spinlock_t *lock, struct kvm *kvm);
+void vfio_device_get_kvm_safe(struct vfio_device *device, struct file *kvm_file);
 void vfio_device_put_kvm(struct vfio_device *device);
 #else
+static inline void vfio_kvm_file_replace(struct file **dst,
+		spinlock_t *lock, struct kvm *kvm)
+{
+}
+
 static inline void vfio_device_get_kvm_safe(struct vfio_device *device,
-					    struct kvm *kvm)
+					    struct file *kvm_file)
 {
 }
 
diff --git a/drivers/vfio/vfio_main.c b/drivers/vfio/vfio_main.c
index 6222376ab6ab..88c85a7b98c0 100644
--- a/drivers/vfio/vfio_main.c
+++ b/drivers/vfio/vfio_main.c
@@ -442,55 +442,61 @@ void vfio_unregister_group_dev(struct vfio_device *device)
 EXPORT_SYMBOL_GPL(vfio_unregister_group_dev);
 
 #if IS_ENABLED(CONFIG_KVM)
-void vfio_device_get_kvm_safe(struct vfio_device *device, struct kvm *kvm)
+void vfio_kvm_file_replace(struct file **dst, spinlock_t *lock, struct kvm *kvm)
 {
-	void (*pfn)(struct kvm *kvm);
-	bool (*fn)(struct kvm *kvm);
-	bool ret;
+	struct file *old_kvm_file, *new_kvm_file = NULL;
 
-	lockdep_assert_held(&device->dev_set->lock);
+	/*
+	 * @kvm can outlive the VM fd and its final __fput(). Only take a
+	 * new reference if the VM file is still active.
+	 */
+	if (kvm)
+		new_kvm_file = get_file_active(&kvm->_file);
 
-	if (!kvm)
-		return;
+	spin_lock(lock);
+	old_kvm_file = *dst;
+	*dst = new_kvm_file;
+	spin_unlock(lock);
 
-	pfn = symbol_get(kvm_put_kvm);
-	if (WARN_ON(!pfn))
-		return;
+	if (old_kvm_file)
+		fput(old_kvm_file);
+}
 
-	fn = symbol_get(kvm_get_kvm_safe);
-	if (WARN_ON(!fn)) {
-		symbol_put(kvm_put_kvm);
-		return;
-	}
+void vfio_device_get_kvm_safe(struct vfio_device *device, struct file *kvm_file)
+{
+	lockdep_assert_held(&device->dev_set->lock);
 
-	ret = fn(kvm);
-	symbol_put(kvm_get_kvm_safe);
-	if (!ret) {
-		symbol_put(kvm_put_kvm);
-		return;
-	}
+	/*
+	 * Take a VM file reference if the KVM fd is still active.
+	 */
+	if (kvm_file)
+		kvm_file = get_file(kvm_file);
 
-	device->put_kvm = pfn;
-	device->kvm = kvm;
+	device->kvm_file = kvm_file;
 }
 
 void vfio_device_put_kvm(struct vfio_device *device)
 {
+	struct file *kvm_file;
+
 	lockdep_assert_held(&device->dev_set->lock);
 
-	if (!device->kvm)
+	kvm_file = device->kvm_file;
+	if (!kvm_file)
 		return;
 
-	if (WARN_ON(!device->put_kvm))
-		goto clear;
+	device->kvm_file = NULL;
+	fput(kvm_file);
+}
 
-	device->put_kvm(device->kvm);
-	device->put_kvm = NULL;
-	symbol_put(kvm_put_kvm);
+struct kvm *vfio_device_get_kvm(struct vfio_device *device)
+{
+	if (!device->kvm_file)
+		return NULL;
 
-clear:
-	device->kvm = NULL;
+	return device->kvm_file->private_data;
 }
+EXPORT_SYMBOL_GPL(vfio_device_get_kvm);
 #endif
 
 /* true if the vfio_device has open_device() called but not close_device() */
@@ -1518,13 +1524,10 @@ static void vfio_device_file_set_kvm(struct file *file, struct kvm *kvm)
 	struct vfio_device_file *df = file->private_data;
 
 	/*
-	 * The kvm is first recorded in the vfio_device_file, and will
-	 * be propagated to vfio_device::kvm when the file is bound to
-	 * iommufd successfully in the vfio device cdev path.
+	 * Cache the VM file reference associated with this VFIO file so it
+	 * can be pinned into vfio_device while the device is open.
 	 */
-	spin_lock(&df->kvm_ref_lock);
-	df->kvm = kvm;
-	spin_unlock(&df->kvm_ref_lock);
+	vfio_kvm_file_replace(&df->kvm_file, &df->kvm_ref_lock, kvm);
 }
 
 /**
@@ -1532,8 +1535,8 @@ static void vfio_device_file_set_kvm(struct file *file, struct kvm *kvm)
  * @file: VFIO group file or VFIO device file
  * @kvm: KVM to link
  *
- * When a VFIO device is first opened the KVM will be available in
- * device->kvm if one was associated with the file.
+ * When a VFIO device is first opened, VFIO caches a VM file reference if
+ * one was associated with the file.
  */
 void vfio_file_set_kvm(struct file *file, struct kvm *kvm)
 {
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 4c14aee1fb06..31afac5fb0ea 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -45,6 +45,8 @@
 #include <asm/kvm_host.h>
 #include <linux/kvm_dirty_ring.h>
 
+struct file;
+
 #ifndef KVM_MAX_VCPU_IDS
 #define KVM_MAX_VCPU_IDS KVM_MAX_VCPUS
 #endif
@@ -861,6 +863,7 @@ struct kvm {
 	struct srcu_struct srcu;
 	struct srcu_struct irq_srcu;
 	pid_t userspace_pid;
+	struct file __rcu *_file;
 	bool override_halt_poll_ns;
 	unsigned int max_halt_poll_ns;
 	u32 dirty_ring_size;
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index 31b826efba00..bca1d00f7845 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -22,8 +22,22 @@ struct kvm;
 struct iommufd_ctx;
 struct iommufd_device;
 struct iommufd_access;
+struct vfio_device;
 struct vfio_info_cap;
 
+#if IS_ENABLED(CONFIG_KVM)
+/*
+ * Return the KVM associated with @vdev's kvm_file. The returned pointer
+ * is valid only while VFIO device open holds the kvm_file reference.
+ */
+struct kvm *vfio_device_get_kvm(struct vfio_device *vdev);
+#else
+static inline struct kvm *vfio_device_get_kvm(struct vfio_device *vdev)
+{
+	return NULL;
+}
+#endif
+
 /*
  * VFIO devices can be placed in a set, this allows all devices to share this
  * structure and the VFIO core will provide a lock that is held around
@@ -54,7 +68,7 @@ struct vfio_device {
 	struct list_head dev_set_list;
 	unsigned int migration_flags;
 	u8 precopy_info_v2;
-	struct kvm *kvm;
+	struct file *kvm_file;
 
 	/* Members below here are private, not for driver use */
 	unsigned int index;
@@ -66,7 +80,6 @@ struct vfio_device {
 	unsigned int open_count;
 	struct completion comp;
 	struct iommufd_access *iommufd_access;
-	void (*put_kvm)(struct kvm *kvm);
 	struct inode *inode;
 #if IS_ENABLED(CONFIG_IOMMUFD)
 	struct iommufd_device *iommufd_device;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 89489996fbc1..011819c5c47c 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -1351,6 +1351,7 @@ static int kvm_vm_release(struct inode *inode, struct file *filp)
 
 	kvm_irqfd_release(kvm);
 
+	RCU_INIT_POINTER(kvm->_file, NULL);
 	kvm_put_kvm(kvm);
 	return 0;
 }
@@ -5500,6 +5501,7 @@ static int kvm_dev_ioctl_create_vm(unsigned long type)
 		r = PTR_ERR(file);
 		goto put_kvm;
 	}
+	rcu_assign_pointer(kvm->_file, file);
 
 	/*
 	 * Don't call kvm_put_kvm anymore at this point; file->f_op is

---

## [3] Aneesh Kumar K.V (Arm) — 2026-05-25
*Subject: [PATCH v5 2/5] iommufd/device: Associate KVM file pointer with iommufd_device*

From: Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>

TSM vDevice support needs access to the KVM associated with a VFIO device
after the device has been bound to iommufd.

Extend iommufd_device_bind() to accept the device's KVM file and store it
in the iommufd_device. The KVM file reference is owned by VFIO and is
already held for the duration of the device open path.

Signed-off-by: Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>
Reviewed-by: Jason Gunthorpe <jgg@nvidia.com>
[nicolinc: fix build error in iommufd_test_mock_domain()]
Signed-off-by: Nicolin Chen <nicolinc@nvidia.com>
[aneesh.kumar: Switch to use kvm_file]
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/device.c          | 7 ++++++-
 drivers/iommu/iommufd/iommufd_private.h | 2 ++
 drivers/iommu/iommufd/selftest.c        | 2 +-
 drivers/vfio/iommufd.c                  | 3 ++-
 include/linux/iommufd.h                 | 4 +++-
 5 files changed, 14 insertions(+), 4 deletions(-)

diff --git a/drivers/iommu/iommufd/device.c b/drivers/iommu/iommufd/device.c
index 170a7005f0bc..718abdc0e627 100644
--- a/drivers/iommu/iommufd/device.c
+++ b/drivers/iommu/iommufd/device.c
@@ -203,6 +203,7 @@ void iommufd_device_destroy(struct iommufd_object *obj)
  * iommufd_device_bind - Bind a physical device to an iommu fd
  * @ictx: iommufd file descriptor
  * @dev: Pointer to a physical device struct
+ * @kvm_file: VM file if device belongs to a KVM VM
  * @id: Output ID number to return to userspace for this device
  *
  * A successful bind establishes an ownership over the device and returns
@@ -216,7 +217,9 @@ void iommufd_device_destroy(struct iommufd_object *obj)
  * The caller must undo this with iommufd_device_unbind()
  */
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
-					   struct device *dev, u32 *id)
+					   struct device *dev,
+					   struct file *kvm_file,
+					   u32 *id)
 {
 	struct iommufd_device *idev;
 	struct iommufd_group *igroup;
@@ -266,6 +269,8 @@ struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
 	if (!iommufd_selftest_is_mock_dev(dev))
 		iommufd_ctx_get(ictx);
 	idev->dev = dev;
+	/* reference is already taken in vfio_df_ioctl_bind_iommufd() */
+	idev->kvm_file = kvm_file;
 	idev->enforce_cache_coherency =
 		device_iommu_capable(dev, IOMMU_CAP_ENFORCE_CACHE_COHERENCY);
 	/* The calling driver is a user until iommufd_device_unbind() */
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 6ac1965199e9..44eb026c206d 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -488,6 +488,8 @@ struct iommufd_device {
 	struct list_head group_item;
 	/* always the physical device */
 	struct device *dev;
+	/* ..and the VM file if available */
+	struct file *kvm_file;
 	bool enforce_cache_coherency;
 	struct iommufd_vdevice *vdev;
 	bool destroying;
diff --git a/drivers/iommu/iommufd/selftest.c b/drivers/iommu/iommufd/selftest.c
index af07c642a526..a193390f9d07 100644
--- a/drivers/iommu/iommufd/selftest.c
+++ b/drivers/iommu/iommufd/selftest.c
@@ -1069,7 +1069,7 @@ static int iommufd_test_mock_domain(struct iommufd_ucmd *ucmd,
 		goto out_sobj;
 	}
 
-	idev = iommufd_device_bind(ucmd->ictx, &sobj->idev.mock_dev->dev,
+	idev = iommufd_device_bind(ucmd->ictx, &sobj->idev.mock_dev->dev, NULL,
 				   &idev_id);
 	if (IS_ERR(idev)) {
 		rc = PTR_ERR(idev);
diff --git a/drivers/vfio/iommufd.c b/drivers/vfio/iommufd.c
index a38d262c6028..d2d0bd9382a1 100644
--- a/drivers/vfio/iommufd.c
+++ b/drivers/vfio/iommufd.c
@@ -119,7 +119,8 @@ int vfio_iommufd_physical_bind(struct vfio_device *vdev,
 {
 	struct iommufd_device *idev;
 
-	idev = iommufd_device_bind(ictx, vdev->dev, out_device_id);
+	idev = iommufd_device_bind(ictx, vdev->dev, vdev->kvm_file,
+				   out_device_id);
 	if (IS_ERR(idev))
 		return PTR_ERR(idev);
 	vdev->iommufd_device = idev;
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 6e7efe83bc5d..0a0bb4abfbd2 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -59,7 +59,9 @@ struct iommufd_object {
 };
 
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
-					   struct device *dev, u32 *id);
+					   struct device *dev,
+					   struct file *kvm_file,
+					   u32 *id);
 void iommufd_device_unbind(struct iommufd_device *idev);
 
 int iommufd_device_attach(struct iommufd_device *idev, ioasid_t pasid,

---

## [4] Aneesh Kumar K.V (Arm) — 2026-05-25
*Subject: [PATCH v5 3/5] iommufd/viommu: Keep a reference to the KVM file*

From: Nicolin Chen <nicolinc@nvidia.com>

The TSM vDevice operations need access to the KVM associated with the
device's vIOMMU. Save the device's KVM file in the iommufd_viommu when the
vIOMMU is allocated, and take a file reference so it remains valid for the
lifetime of the vIOMMU.

Release the reference when the vIOMMU is destroyed.

Based on an original patch by Shameer Kolothum <shameerali.kolothum.thodi@huawei.com>

[nicolinc: hold kvm's users_count]
Signed-off-by: Nicolin Chen <nicolinc@nvidia.com>
[aneesh.kumar: Switch to use kvm_file]
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/viommu.c | 5 +++++
 include/linux/iommufd.h        | 1 +
 2 files changed, 6 insertions(+)

diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 4081deda9b33..bf5d58d55939 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -1,6 +1,7 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /* Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES
  */
+#include <linux/file.h>
 #include "iommufd_private.h"
 
 void iommufd_viommu_destroy(struct iommufd_object *obj)
@@ -11,6 +12,8 @@ void iommufd_viommu_destroy(struct iommufd_object *obj)
 	if (viommu->ops && viommu->ops->destroy)
 		viommu->ops->destroy(viommu);
 	refcount_dec(&viommu->hwpt->common.obj.users);
+	if (viommu->kvm_file)
+		fput(viommu->kvm_file);
 	xa_destroy(&viommu->vdevs);
 }
 
@@ -76,6 +79,8 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	}
 
 	xa_init(&viommu->vdevs);
+	if (idev->kvm_file)
+		viommu->kvm_file = get_file(idev->kvm_file);
 	viommu->type = cmd->type;
 	viommu->ictx = ucmd->ictx;
 	viommu->hwpt = hwpt_paging;
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 0a0bb4abfbd2..3267717f676d 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -103,6 +103,7 @@ struct iommufd_viommu {
 	struct iommufd_ctx *ictx;
 	struct iommu_device *iommu_dev;
 	struct iommufd_hwpt_paging *hwpt;
+	struct file *kvm_file;
 
 	const struct iommufd_viommu_ops *ops;

---

## [5] Aneesh Kumar K.V (Arm) — 2026-05-25
*Subject: [PATCH v5 4/5] iommufd/tsm: add vdevice TSM bind/unbind ioctl*

Introduce IOMMU_VDEVICE_TSM_OP to allow userspace to issue TSM bind/unbind
operations for an iommufd vdevice.

The new ioctl:
- looks up the vdevice object from vdevice_id
- resolves the associated KVM VM from the vIOMMU KVM file reference
- dispatches bind/unbind via tsm_bind()/tsm_unbind()

Also add common TSM helpers in tsm-core and wire vdevice teardown to unbind
the device from TSM state.

This provides iommufd plumbing to bind a TDI to a confidential guest through
the TSM layer.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/Makefile          |  2 +
 drivers/iommu/iommufd/iommufd_private.h |  8 ++++
 drivers/iommu/iommufd/main.c            |  3 ++
 drivers/iommu/iommufd/tsm.c             | 62 +++++++++++++++++++++++++
 drivers/iommu/iommufd/viommu.c          |  4 ++
 drivers/virt/coco/tsm-core.c            | 19 ++++++++
 include/linux/tsm.h                     | 17 +++++++
 include/uapi/linux/iommufd.h            | 26 +++++++++++
 8 files changed, 141 insertions(+)
 create mode 100644 drivers/iommu/iommufd/tsm.c

diff --git a/drivers/iommu/iommufd/Makefile b/drivers/iommu/iommufd/Makefile
index 71d692c9a8f4..431089089ee9 100644
--- a/drivers/iommu/iommufd/Makefile
+++ b/drivers/iommu/iommufd/Makefile
@@ -10,6 +10,8 @@ iommufd-y := \
 	vfio_compat.o \
 	viommu.o
 
+iommufd-$(CONFIG_TSM) += tsm.o
+
 iommufd-$(CONFIG_IOMMUFD_TEST) += selftest.o
 
 obj-$(CONFIG_IOMMUFD) += iommufd.o
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 44eb026c206d..8eea0c2c332b 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -699,6 +699,14 @@ void iommufd_vdevice_destroy(struct iommufd_object *obj);
 void iommufd_vdevice_abort(struct iommufd_object *obj);
 int iommufd_hw_queue_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_hw_queue_destroy(struct iommufd_object *obj);
+#ifdef CONFIG_TSM
+int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd);
+#else
+static inline int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
+{
+	return -EOPNOTSUPP;
+}
+#endif
 
 static inline struct iommufd_vdevice *
 iommufd_get_vdevice(struct iommufd_ctx *ictx, u32 id)
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 8c6d43601afb..d73e6b391c6f 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -432,6 +432,7 @@ union ucmd_buffer {
 	struct iommu_veventq_alloc veventq;
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
+	struct iommu_vdevice_tsm_op tsm_op;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -493,6 +494,8 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 __reserved),
 	IOCTL_OP(IOMMU_VIOMMU_ALLOC, iommufd_viommu_alloc_ioctl,
 		 struct iommu_viommu_alloc, out_viommu_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_OP, iommufd_vdevice_tsm_op_ioctl,
+		 struct iommu_vdevice_tsm_op, vdevice_id),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/tsm.c b/drivers/iommu/iommufd/tsm.c
new file mode 100644
index 000000000000..09ee668dbed9
--- /dev/null
+++ b/drivers/iommu/iommufd/tsm.c
@@ -0,0 +1,62 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#include <linux/tsm.h>
+#include "iommufd_private.h"
+
+/**
+ * iommufd_vdevice_tsm_op_ioctl - Handle vdevice TSM operations
+ * @ucmd: user command data for IOMMU_VDEVICE_TSM_OP
+ *
+ * Currently only supports TSM bind/unbind operations
+ * Resolve @iommu_vdevice_tsm_op::vdevice_id to a vdevice and dispatch the
+ * requested bind/unbind operation through the TSM core.
+ *
+ * Return: 0 on success, or a negative error code on failure.
+ */
+int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
+{
+	int rc;
+	struct kvm *kvm = NULL;
+	struct iommufd_vdevice *vdev;
+	struct iommu_vdevice_tsm_op *cmd = ucmd->cmd;
+
+	if (cmd->flags)
+		return -EOPNOTSUPP;
+
+	vdev = iommufd_get_vdevice(ucmd->ictx, cmd->vdevice_id);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	if (vdev->viommu->kvm_file)
+		kvm = vdev->viommu->kvm_file->private_data;
+
+	if (!kvm) {
+		rc = -ENODEV;
+		goto out_put_vdev;
+	}
+
+	/* tsm layer will take care of parallel calls to tsm_bind/unbind */
+	switch (cmd->type) {
+	case IOMMU_VDEVICE_TSM_BIND:
+		rc = tsm_bind(vdev->idev->dev, kvm, vdev->virt_id);
+		break;
+	case IOMMU_VDEVICE_TSM_UNBIND:
+		rc = tsm_unbind(vdev->idev->dev);
+		break;
+	default:
+		rc = -EINVAL;
+		goto out_put_vdev;
+	}
+
+	if (rc)
+		goto out_put_vdev;
+
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index bf5d58d55939..1b9379fcba84 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -3,6 +3,8 @@
  */
 #include <linux/file.h>
 #include "iommufd_private.h"
+#include <linux/cleanup.h>
+#include <linux/tsm.h>
 
 void iommufd_viommu_destroy(struct iommufd_object *obj)
 {
@@ -124,6 +126,8 @@ void iommufd_vdevice_abort(struct iommufd_object *obj)
 
 	lockdep_assert_held(&idev->igroup->lock);
 
+	tsm_unbind(idev->dev);
+
 	if (vdev->destroy)
 		vdev->destroy(vdev);
 	/* xa_cmpxchg is okay to fail if alloc failed xa_cmpxchg previously */
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index e784993353d8..3870d08ffe0d 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -108,6 +108,25 @@ void tsm_unregister(struct tsm_dev *tsm_dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id)
+{
+	if (!dev_is_pci(dev))
+		return -EINVAL;
+
+	return pci_tsm_bind(to_pci_dev(dev), kvm, tdi_id);
+}
+EXPORT_SYMBOL_GPL(tsm_bind);
+
+int tsm_unbind(struct device *dev)
+{
+	if (!dev_is_pci(dev))
+		return -EINVAL;
+
+	pci_tsm_unbind(to_pci_dev(dev));
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_unbind);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 381c53244c83..7b6df827321b 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -123,4 +123,21 @@ int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
+
+struct kvm;
+#ifdef CONFIG_TSM
+int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id);
+int tsm_unbind(struct device *dev);
+#else
+static inline int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id)
+{
+	return -EINVAL;
+}
+
+static inline int tsm_unbind(struct device *dev)
+{
+	return 0;
+}
+#endif
+
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index e998dfbd6960..66398efa31d1 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -57,6 +57,7 @@ enum {
 	IOMMUFD_CMD_IOAS_CHANGE_PROCESS = 0x92,
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
 	IOMMUFD_CMD_HW_QUEUE_ALLOC = 0x94,
+	IOMMUFD_CMD_VDEVICE_TSM_OP = 0x95,
 };
 
 /**
@@ -1143,6 +1144,31 @@ struct iommu_vdevice_alloc {
 };
 #define IOMMU_VDEVICE_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_ALLOC)
 
+/**
+ * enum iommu_vdevice_tsm_op_type - operation type for struct iommu_vdevice_tsm_op
+ * @IOMMU_VDEVICE_TSM_BIND: Bind a vDevice to TSM
+ * @IOMMU_VDEVICE_TSM_UNBIND: Unbind a vDevice from TSM
+ */
+enum iommu_vdevice_tsm_op_type {
+	IOMMU_VDEVICE_TSM_BIND = 0x1,
+	IOMMU_VDEVICE_TSM_UNBIND,
+};
+
+/**
+ * struct iommu_vdevice_tsm_op - ioctl(IOMMU_VDEVICE_TSM_OP)
+ * @size: sizeof(struct iommu_vdevice_tsm_op)
+ * @type: Type of TSM operation. Must be defined in enum iommu_vdevice_tsm_op_type
+ * @flags: Must be 0
+ * @vdevice_id: Object handle for the vDevice. Returned from IOMMU_VDEVICE_ALLOC
+ */
+struct iommu_vdevice_tsm_op {
+	__u32 size;
+	__u32 type;
+	__u32 flags;
+	__u32 vdevice_id;
+};
+#define IOMMU_VDEVICE_TSM_OP _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_OP)
+
 /**
  * struct iommu_ioas_change_process - ioctl(VFIO_IOAS_CHANGE_PROCESS)
  * @size: sizeof(struct iommu_ioas_change_process)

---

## [6] Aneesh Kumar K.V (Arm) — 2026-05-25
*Subject: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

Add IOMMU_VDEVICE_TSM_REQUEST for issuing TSM guest request/response
transactions against an iommufd vdevice.

The ioctl takes a vdevice_id plus request/response user buffers and length
fields, and forwards the request through tsm_guest_req() to the PCI TSM
backend. This provides the host-side passthrough path used by CoCo guests
for TSM device attestation and acceptance flows after the device has been
bound to TSM.

Also add the supporting tsm_guest_req() helper and associated TSM core
interface definitions.

Based on changes from: Alexey Kardashevskiy <aik@amd.com>

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/iommufd_private.h |  6 ++
 drivers/iommu/iommufd/main.c            |  3 +
 drivers/iommu/iommufd/tsm.c             | 68 +++++++++++++++++++++
 drivers/virt/coco/tsm-core.c            | 39 ++++++++++++
 include/linux/pci-tsm.h                 |  9 +--
 include/linux/tsm.h                     | 25 ++++++++
 include/uapi/linux/iommufd.h            | 80 +++++++++++++++++++++++++
 7 files changed, 226 insertions(+), 4 deletions(-)

diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 8eea0c2c332b..0080895e9e92 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -701,11 +701,17 @@ int iommufd_hw_queue_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_hw_queue_destroy(struct iommufd_object *obj);
 #ifdef CONFIG_TSM
 int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd);
+int iommufd_vdevice_tsm_req_ioctl(struct iommufd_ucmd *ucmd);
 #else
 static inline int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
 {
 	return -EOPNOTSUPP;
 }
+
+static inline int iommufd_vdevice_tsm_req_ioctl(struct iommufd_ucmd *ucmd)
+{
+	return -EOPNOTSUPP;
+}
 #endif
 
 static inline struct iommufd_vdevice *
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index d73e6b391c6f..5f49b546ec92 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -433,6 +433,7 @@ union ucmd_buffer {
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
 	struct iommu_vdevice_tsm_op tsm_op;
+	struct iommu_vdevice_tsm_req tsm_req;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -496,6 +497,8 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 struct iommu_viommu_alloc, out_viommu_id),
 	IOCTL_OP(IOMMU_VDEVICE_TSM_OP, iommufd_vdevice_tsm_op_ioctl,
 		 struct iommu_vdevice_tsm_op, vdevice_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_REQ, iommufd_vdevice_tsm_req_ioctl,
+		 struct iommu_vdevice_tsm_req, resp_uptr),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/tsm.c b/drivers/iommu/iommufd/tsm.c
index 09ee668dbed9..342fbdb6a6b9 100644
--- a/drivers/iommu/iommufd/tsm.c
+++ b/drivers/iommu/iommufd/tsm.c
@@ -60,3 +60,71 @@ int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &vdev->obj);
 	return rc;
 }
+
+static bool iommufd_vdevice_tsm_req_scope_valid(u32 scope)
+{
+	if (scope > IOMMU_VDEVICE_TSM_REQ_SCOPE_PCI_LAST)
+		return false;
+
+	switch (scope) {
+	case IOMMU_VDEVICE_TSM_REQ_PCI_INFO:
+	case IOMMU_VDEVICE_TSM_REQ_PCI_STATE_CHANGE:
+	case IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_READ:
+	case IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_WRITE:
+		return true;
+	default:
+		return false;
+	}
+}
+
+/**
+ * iommufd_vdevice_tsm_req_ioctl - Forward TSM requests
+ * @ucmd: user command data for IOMMU_VDEVICE_TSM_REQ
+ *
+ * Resolve @iommu_vdevice_tsm_req::vdevice_id to a vdevice and pass the
+ * request/response buffers to the TSM core.
+ *
+ * Return:
+ *  -errno on error.
+ *  positive residue if response/request bytes were left unconsumed.
+ *    if response buffer is provided, residue indicates the number of bytes
+ *    not used in response buffer
+ *    if there is no response buffer, residue indicates the number of bytes
+ *    not consumed in req buffer
+ *  0 otherwise.
+ */
+int iommufd_vdevice_tsm_req_ioctl(struct iommufd_ucmd *ucmd)
+{
+	int rc;
+	struct iommufd_vdevice *vdev;
+	struct iommu_vdevice_tsm_req *cmd = ucmd->cmd;
+	struct tsm_guest_req_info info = {
+		.scope = cmd->scope,
+		.req   = {
+			.user = u64_to_user_ptr(cmd->req_uptr),
+			.is_kernel = false,
+		},
+		.req_len = cmd->req_len,
+		.resp    =  {
+			.user = u64_to_user_ptr(cmd->resp_uptr),
+			.is_kernel = false,
+		},
+		.resp_len = cmd->resp_len,
+	};
+
+	if (cmd->__reserved)
+		return -EOPNOTSUPP;
+
+	if (!iommufd_vdevice_tsm_req_scope_valid(cmd->scope))
+		return -EINVAL;
+
+	vdev = iommufd_get_vdevice(ucmd->ictx, cmd->vdevice_id);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	rc = tsm_guest_req(vdev->idev->dev, &info);
+
+	/* No inline response, hence we don't need to copy the response */
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 3870d08ffe0d..c24886851f9e 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -8,6 +8,7 @@
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/pci-tsm.h>
+#include <uapi/linux/iommufd.h>
 
 static void tsm_release(struct device *);
 static const struct class tsm_class = {
@@ -127,6 +128,44 @@ int tsm_unbind(struct device *dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unbind);
 
+static int tsm_pci_req_scope(u32 scope, enum pci_tsm_req_scope *pci_scope)
+{
+	switch (scope) {
+	case IOMMU_VDEVICE_TSM_REQ_PCI_INFO:
+		*pci_scope = PCI_TSM_REQ_INFO;
+		return 0;
+	case IOMMU_VDEVICE_TSM_REQ_PCI_STATE_CHANGE:
+		*pci_scope = PCI_TSM_REQ_STATE_CHANGE;
+		return 0;
+	case IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_READ:
+		*pci_scope = PCI_TSM_REQ_DEBUG_READ;
+		return 0;
+	case IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_WRITE:
+		*pci_scope = PCI_TSM_REQ_DEBUG_WRITE;
+		return 0;
+	default:
+		return -EINVAL;
+	}
+}
+
+ssize_t tsm_guest_req(struct device *dev, struct tsm_guest_req_info *info)
+{
+	int ret;
+	enum pci_tsm_req_scope pci_scope;
+
+	if (!dev_is_pci(dev))
+		return -EINVAL;
+
+	ret = tsm_pci_req_scope(info->scope, &pci_scope);
+	if (ret)
+		return ret;
+
+	return pci_tsm_guest_req(to_pci_dev(dev), pci_scope, info->req,
+				 info->req_len, info->resp, info->resp_len,
+				 NULL);
+}
+EXPORT_SYMBOL_GPL(tsm_guest_req);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index a6435aba03f9..ec2236a7a279 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -4,6 +4,7 @@
 #include <linux/mutex.h>
 #include <linux/pci.h>
 #include <linux/sockptr.h>
+#include <uapi/linux/iommufd.h>
 
 struct pci_tsm;
 struct tsm_dev;
@@ -173,7 +174,7 @@ enum pci_tsm_req_scope {
 	 * typical TDISP collateral information like Device Interface Reports.
 	 * No device secrets are permitted, and no device state is changed.
 	 */
-	PCI_TSM_REQ_INFO = 0,
+	PCI_TSM_REQ_INFO = IOMMU_VDEVICE_TSM_REQ_PCI_INFO,
 	/**
 	 * @PCI_TSM_REQ_STATE_CHANGE: Request to change the TDISP state from
 	 * UNLOCKED->LOCKED, LOCKED->RUN, or other architecture specific state
@@ -181,14 +182,14 @@ enum pci_tsm_req_scope {
 	 * to TDISP) device / host state, configuration, or data change is
 	 * permitted.
 	 */
-	PCI_TSM_REQ_STATE_CHANGE = 1,
+	PCI_TSM_REQ_STATE_CHANGE = IOMMU_VDEVICE_TSM_REQ_PCI_STATE_CHANGE,
 	/**
 	 * @PCI_TSM_REQ_DEBUG_READ: Read-only request for debug information
 	 *
 	 * A method to facilitate TVM information retrieval outside of typical
 	 * TDISP operational requirements. No device secrets are permitted.
 	 */
-	PCI_TSM_REQ_DEBUG_READ = 2,
+	PCI_TSM_REQ_DEBUG_READ = IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_READ,
 	/**
 	 * @PCI_TSM_REQ_DEBUG_WRITE: Device state changes for debug purposes
 	 *
@@ -196,7 +197,7 @@ enum pci_tsm_req_scope {
 	 * the TDISP operational model. If allowed, requires CAP_SYS_RAW_IO, and
 	 * will taint the kernel.
 	 */
-	PCI_TSM_REQ_DEBUG_WRITE = 3,
+	PCI_TSM_REQ_DEBUG_WRITE = IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_WRITE,
 };
 
 #ifdef CONFIG_PCI_TSM
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 7b6df827321b..6101a2a1db61 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -6,6 +6,7 @@
 #include <linux/types.h>
 #include <linux/uuid.h>
 #include <linux/device.h>
+#include <linux/sockptr.h>
 
 #define TSM_REPORT_INBLOB_MAX 64
 #define TSM_REPORT_OUTBLOB_MAX SZ_16M
@@ -128,6 +129,23 @@ struct kvm;
 #ifdef CONFIG_TSM
 int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id);
 int tsm_unbind(struct device *dev);
+
+/**
+ * struct tsm_guest_req_info - parameter for tsm_guest_req()
+ * @scope: iommufd allocated scope for tsm guest request
+ * @req: request data buffer filled by guest
+ * @req_len: the size of @req filled by guest
+ * @resp: response data buffer filled by host
+ * @resp_len: the size of @resp buffer filled by guest
+ */
+struct tsm_guest_req_info {
+	u32 scope;
+	sockptr_t req;
+	size_t req_len;
+	sockptr_t resp;
+	size_t resp_len;
+};
+ssize_t tsm_guest_req(struct device *dev, struct tsm_guest_req_info *info);
 #else
 static inline int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id)
 {
@@ -138,6 +156,13 @@ static inline int tsm_unbind(struct device *dev)
 {
 	return 0;
 }
+
+struct tsm_guest_req_info;
+static inline ssize_t tsm_guest_req(struct device *dev,
+		struct tsm_guest_req_info *info)
+{
+	return -EINVAL;
+}
 #endif
 
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 66398efa31d1..7953e99a9671 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -58,6 +58,7 @@ enum {
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
 	IOMMUFD_CMD_HW_QUEUE_ALLOC = 0x94,
 	IOMMUFD_CMD_VDEVICE_TSM_OP = 0x95,
+	IOMMUFD_CMD_VDEVICE_TSM_REQ = 0x96,
 };
 
 /**
@@ -1373,4 +1374,83 @@ struct iommu_hw_queue_alloc {
 	__aligned_u64 length;
 };
 #define IOMMU_HW_QUEUE_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_HW_QUEUE_ALLOC)
+
+/*
+ * TSM request scope values are allocated by iommufd. Each device-bus transport
+ * gets a range from this number space.
+ */
+#define IOMMU_VDEVICE_TSM_REQ_SCOPE_PCI_BASE	0
+
+enum iommu_vdevice_tsm_req_scope {
+	/*
+	 * Read-only, without side effects, request for typical TDISP
+	 * collateral information like Device Interface Reports. No device
+	 * secrets are permitted, and no device state is changed.
+	 */
+	IOMMU_VDEVICE_TSM_REQ_PCI_INFO =
+		IOMMU_VDEVICE_TSM_REQ_SCOPE_PCI_BASE,
+	/*
+	 * Request to change the TDISP state from UNLOCKED->LOCKED,
+	 * LOCKED->RUN, or other architecture specific state changes to
+	 * support those transitions for a TDI. No other device or host state,
+	 * configuration, or data change is permitted.
+	 */
+	IOMMU_VDEVICE_TSM_REQ_PCI_STATE_CHANGE =
+		IOMMU_VDEVICE_TSM_REQ_SCOPE_PCI_BASE + 1,
+	/*
+	 * Read-only request for debug information outside of typical TDISP
+	 * operational requirements. No device secrets are permitted.
+	 */
+	IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_READ =
+		IOMMU_VDEVICE_TSM_REQ_SCOPE_PCI_BASE + 2,
+	/*
+	 * Device state changes for debug purposes. The request may affect the
+	 * operational state of the device outside of the TDISP operational
+	 * model. If allowed, this requires CAP_SYS_RAW_IO and taints the
+	 * kernel.
+	 */
+	IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_WRITE =
+		IOMMU_VDEVICE_TSM_REQ_SCOPE_PCI_BASE + 3,
+	IOMMU_VDEVICE_TSM_REQ_SCOPE_PCI_LAST =
+		IOMMU_VDEVICE_TSM_REQ_PCI_DEBUG_WRITE,
+};
+
+/**
+ * struct iommu_vdevice_tsm_req - ioctl(IOMMU_VDEVICE_TSM_REQ)
+ * @size: sizeof(struct iommu_vdevice_tsm_req)
+ * @vdevice_id: vDevice ID the guest request is for
+ * @scope: One of enum iommu_vdevice_tsm_req_scope
+ * @req_len: Size in bytes of the input payload at @req_uptr
+ * @resp_len: Size in bytes of the output buffer at @resp_uptr
+ * @__reserved: Must be 0
+ * @req_uptr: Userspace pointer to the guest-provided request payload
+ * @resp_uptr: Userspace pointer to the guest response buffer
+ *
+ * Forward a TSM request to the TSM bound vDevice. This is intended for
+ * guest TSM/TDISP message transport where the host kernel only marshals
+ * bytes between userspace and the TSM implementation.
+ *
+ * Requests outside the iommufd allocated scope values are rejected. Lower
+ * layers may reject scope values that are valid in the global iommufd
+ * namespace, but not permitted for a specific bus.
+ *
+ * The request payload is read from @req_uptr/@req_len. If a response is
+ * expected, userspace provides @resp_uptr/@resp_len as writable storage for
+ * response bytes returned by the TSM path.
+ *
+ * The ioctl is only suitable for commands and results that the host kernel
+ * has no use, the host is only facilitating guest to TSM communication.
+ */
+struct iommu_vdevice_tsm_req {
+	__u32 size;
+	__u32 vdevice_id;
+	__u32 scope;
+	__u32 req_len;
+	__u32 resp_len;
+	__u32 __reserved;
+	__aligned_u64 req_uptr;
+	__aligned_u64 resp_uptr;
+};
+
+#define IOMMU_VDEVICE_TSM_REQ _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_REQ)
 #endif

---

## [7] Anthony Krowiak — 2026-05-26
*Subject: Re: [PATCH v5 1/5] vfio: cache KVM VM file references instead of raw
 struct kvm pointers*

On 5/25/26 11:48 AM, Aneesh Kumar K.V (Arm) wrote:
> VFIO currently records struct kvm pointers on vfio_group, vfio_device_file
> and the opened vfio_device. Switch VFIO to track the VM's struct file

Acked-by: Anthony Krowiak <akrowiak@linxux.ibm.com>

> ---
>   drivers/s390/crypto/vfio_ap_ops.c |  5 +-

---

## [8] Alexey Kardashevskiy — 2026-05-27
*Subject: Re: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

On 26/5/26 01:48, Aneesh Kumar K.V (Arm) wrote:
> Add IOMMU_VDEVICE_TSM_REQUEST for issuing TSM guest request/response
> transactions against an iommufd vdevice.

This scope thing still needs clarification.

I have 3 types of requests to fit here, all go via VM -> KVM -> QEMU -> IOMMUFD -> TSM.

1) bind/unbind TDI <- moves to CONFIG_LOCKED, this is "OP";
2) start/stop TDI <- moves to RUN, this is "GR"? Right now I route it via "OP";
3) enable/disable MMIO/DMA <- no TDI state change, this is "GR" but which scope is it here?

thanks,



> +		return true;
> +	default:

---

## [9] Dan Williams (nvidia) — 2026-05-26
*Subject: Re: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

Alexey Kardashevskiy wrote:
> 
> 
[..]
> > diff --git a/drivers/iommu/iommufd/tsm.c b/drivers/iommu/iommufd/tsm.c
> > index 09ee668dbed9..342fbdb6a6b9 100644

The scope parameter was meant to enumerate a security model for classes
of commands that are otherwise opaque to the kernel. However, none of
the commands we are targeting are opaque (private specification with
unknown effect). It now turns out there is no role for @scope for
security.

Now a command family that iommufd can validate seems useful. As it
stands this implementation aliases command codes across TSMs. Do we
proceed with creating an actual shared command uapi for the truly shared
commands:

TSM_REQ_TYPE_DEFAULT: Commands every arch needs
TSM_REQ_READ_OBJECT
TSM_REQ_REGEN_OBJECT
TSM_REQ_OBJECT_INFO
TSM_REQ_VALIDATE_MMIO
TSM_REQ_SET_TDI_STATE

TSM_REQ_TYPE_SEV: Commands only SEV needs
TSM_REQ_SEV_ENABLE_DMA
TSM_REQ_SEV_DISABLE_DMA

...or just observe that per CC arch commands are needed to setup the VM
so per CC arch commands are needed to marshal device assignment support
requests.

In that case pci_tsm_req_scope becomes tsm_req_type and is just:

TSM_REQ_TYPE_CCA
TSM_REQ_TYPE_SEV
TSM_REQ_TYPE_TDX

I am leaning towards the latter at this point.

---

## [10] Tian, Kevin — 2026-05-27
*Subject: RE: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

> From: Dan Williams (nvidia) <djbw@kernel.org>
> Sent: Wednesday, May 27, 2026 2:18 PM

yeah, I haven't succeeded on figuring out that role for now. It sounds an
unnecessary abstraction asking vendor specific code to translate its
command into opaque then in the end we go back to the vendor code
to decide the security scope of that opaque.

[...]
> ...or just observe that per CC arch commands are needed to setup the VM
> so per CC arch commands are needed to marshal device assignment support

+1

---

## [11] Jason Gunthorpe — 2026-05-27
*Subject: Re: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

On Tue, May 26, 2026 at 11:17:50PM -0700, Dan Williams (nvidia) wrote:

> In that case pci_tsm_req_scope becomes tsm_req_type and is just:
> 

Yeah, this sounds good. I would also include an common op field that
can be decoded by the TSM driver based on the TYPE above, and the
usual in/out message buffers.

Jason

---

## [12] Aneesh Kumar K.V — 2026-05-27
*Subject: Re: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

"Dan Williams (nvidia)" <djbw@kernel.org> writes:

> Alexey Kardashevskiy wrote:
>> 

But we already have struct pci_tsm_ops::guest_req, which is specific to
the underlying CC architecture. From the above, pci_tsm_req_scope also
appears to carry the same information. Is that useful?

-aneesh

---

## [13] Aneesh Kumar K.V — 2026-05-27
*Subject: Re: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> "Dan Williams (nvidia)" <djbw@kernel.org> writes:
>

......

>>> 
>>> I have 3 types of requests to fit here, all go via VM -> KVM -> QEMU -> IOMMUFD -> TSM.

I think there is value in having the VMM express the guest’s
confidential computing architecture, so that the TSM backend can
validate whether it should handle that guest request ?.

So it would not be the IOMMU validating the scope value, but rather
pci_tsm_ops::guest_req.

static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope scope,
		sockptr_t req, size_t req_len, sockptr_t resp,
		size_t resp_len, u64 *tsm_code)
{
	struct pci_dev *pdev = tdi->pdev;

	/* reject the guest request if VMM was using the link tsm wrongly. The guest
	 * was using a wrong CC archiecture with this link tsm
	 */
	if (scope != TSM_REQ_TYPE_CCA)
		return -EINVAL;


Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Tue, May 26, 2026 at 11:17:50PM -0700, Dan Williams (nvidia) wrote:
>

We already have iommufd_vdevice_tsm_op_ioctl() to handle common
operations. Right now, it handles IOMMU_VDEVICE_TSM_BIND and
IOMMU_VDEVICE_TSM_UNBIND. I guess we should move TSM_REQ_SET_TDI_STATE
operations to that as well?

-aneesh

---

## [14] Dan Williams (nvidia) — 2026-05-27
*Subject: Re: [PATCH v5 5/5] iommufd/vdevice: add TSM request ioctl*

Aneesh Kumar K.V wrote:
> >> I am leaning towards the latter at this point.
> >

Yes, that is the idea.

> So it would not be the IOMMU validating the scope value, but rather
> pci_tsm_ops::guest_req.

Right, iommufd is tunneling TSM requests. The tunnel should have an
envelope of TSM_REQ_TYPE_* and an @op field. The TSM driver gets those
from iommufd, validates the envelope and then processes @req.

This self-consistency and explicitness also buys some future-proofing.
It allows for alternate command sets within an arch, cross TSM
implementation shared commands, IOMMUFD-to-TSM requests outside of guest
requests.

> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

Per above, I believe this is about an @op value in a common location
that iommufd can forward to the backend for validation of guest
requests.

> Right now, it handles IOMMU_VDEVICE_TSM_BIND and
> IOMMU_VDEVICE_TSM_UNBIND. I guess we should move TSM_REQ_SET_TDI_STATE

I think we can wait to move it to its own IOMMU operation unless/until
there is a need to set RUN outside of an explicit guest request, right?

---
