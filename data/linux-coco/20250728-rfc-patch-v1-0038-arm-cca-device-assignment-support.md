---
title: '[RFC PATCH v1 00/38] ARM CCA Device Assignment support'
date: 2025-07-28
last_reply: 2025-10-15
message_count: 188
participants: ['Aneesh Kumar K.V (Arm)', 'Jason Gunthorpe', 'Jonathan Cameron', 'Xu Yilun', 'Suzuki K Poulose', 'Greg KH', 'Arto Merilainen', 'dan.j.williams@intel.com', 'Alexey Kardashevskiy', 'Bjorn Helgaas', 'Eric Biggers', 'Mostafa Saleh', 'Jeremy Linton', 'James Bottomley']
---

## [1] Aneesh Kumar K.V (Arm) — 2025-07-28

This patch series implements support for Device Assignment in the ARM CCA
architecture. The code changes are based on Alp12 specification published here
[1].

The code builds on the TSM framework patches posted at [2]. We add extension to
that framework so that TSM is now used in both the host and the guest.

A DA workflow can be summarized as below:

Host:
step 1.
echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind
echo vfio-pci > /sys/bus/pci/devices/${DEVICE}/driver_override
echo ${DEVICE} > /sys/bus/pci/drivers_probe

step 2.
echo 1 > /sys/bus/pci/devices/$DEVICE/tsm/connect

Now in the guest we follow the below steps

step 1:
echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind

step 2: Move the device to TDISP LOCK state
echo 1 > /sys/bus/pci/devices/${DEVICE}/tsm/lock

step 3: Moves the device to TDISP RUN state
echo 1 > /sys/bus/pci/devices/${DEVICE}/tsm/accept

step 4: Load the driver again.
echo ${DEVICE} > /sys/bus/pci/drivers_probe

I'm currently working against TSM v3, as TSM v4 lacks the necessary
callbacks—bind, unbind, and guest_req—required for guest interactions.

The implementation also makes use of RHI interfaces that fall outside the
current RHI specification [5]. Once the spec is finalized, the code will be aligned
accordingly.

For now, I’ve retained validate_mmio and vdev_req exit handling within KVM. This
will transition to a guest_req-based mechanism once the specification is
updated.

At that point, all device assignment (DA)-specific VM exits will exit directly
to the VMM, and will use the guest_req ioctl to handle exit reasons. As part of
this change, the handlers realm_exit_vdev_req_handler,
realm_exit_vdev_comm_handler, and realm_exit_dev_mem_map_handler will be
removed.

Full patchset for the kernel and kvmtool can be found at [3] and [4]

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp12.zip

[2] https://lore.kernel.org/all/20250516054732.2055093-1-dan.j.williams@intel.com

[3] https://git.gitlab.arm.com/linux-arm/linux-cca.git cca/tdisp-upstream-post-v1
[4] https://git.gitlab.arm.com/linux-arm/kvmtool-cca.git cca/tdisp-upstream-post-v1
[5] https://developer.arm.com/documentation/den0148/latest/


Aneesh Kumar K.V (Arm) (35):
  tsm: Add tsm_bind/unbind helpers
  tsm: Move tsm core outside the host directory
  tsm: Move dsm_dev from pci_tdi to pci_tsm
  tsm: Support DMA Allocation from private memory
  tsm: Don't overload connect
  iommufd: Add and option to request for bar mapping with
    IORESOURCE_EXCLUSIVE
  iommufd/viommu: Add support to associate viommu with kvm instance
  iommufd/tsm: Add tsm_op iommufd ioctls
  iommufd/vdevice: Add TSM Guest request uAPI
  iommufd/vdevice: Add TSM map ioctl
  KVM: arm64: CCA: register host tsm platform device
  coco: host: arm64: CCA host platform device driver
  coco: host: arm64: Create a PDEV with rmm
  coco: host: arm64: Device communication support
  coco: host: arm64: Stop and destroy the physical device
  coco: host: arm64: set_pubkey support
  coco: host: arm64: Add support for creating a virtual device
  coco: host: arm64: Add support for virtual device communication
  coco: host: arm64: Stop and destroy virtual device
  coco: guest: arm64: Update arm CCA guest driver
  arm64: CCA: Register guest tsm callback
  cca: guest: arm64: Realm device lock support
  KVM: arm64: Add exit handler related to device assignment
  coco: host: arm64: add RSI_RDEV_GET_INSTANCE_ID related exit handler
  coco: host: arm64: Add support for device communication exit handler
  coco: guest: arm64: Add support for collecting interface reports
  coco: host: arm64: Add support for realm host interface (RHI)
  coco: guest: arm64: Add support for fetching interface report and
    certificate chain from host
  coco: guest: arm64: Add support for guest initiated TDI bind/unbind
  KVM: arm64: CCA: handle dev mem map/unmap
  coco: guest: arm64: Validate mmio range found in the interface report
  coco: guest: arm64: Add Realm device start and stop support
  KVM: arm64: CCA: enable DA in realm create parameters
  coco: guest: arm64: Add support for fetching device measurements
  coco: guest: arm64: Add support for fetching device info

Lukas Wunner (3):
  X.509: Make certificate parser public
  X.509: Parse Subject Alternative Name in certificates
  X.509: Move certificate length retrieval into new helper

 arch/arm64/include/asm/kvm_rme.h              |   3 +
 arch/arm64/include/asm/mem_encrypt.h          |   6 +-
 arch/arm64/include/asm/rhi.h                  |  39 +
 arch/arm64/include/asm/rmi_cmds.h             | 173 ++++
 arch/arm64/include/asm/rmi_smc.h              | 210 ++++-
 arch/arm64/include/asm/rsi.h                  |   5 +-
 arch/arm64/include/asm/rsi_cmds.h             | 129 +++
 arch/arm64/include/asm/rsi_smc.h              |  60 ++
 arch/arm64/kernel/Makefile                    |   2 +-
 arch/arm64/kernel/rhi.c                       |  35 +
 arch/arm64/kernel/rsi.c                       |  26 +-
 arch/arm64/kvm/mmu.c                          |  45 +
 arch/arm64/kvm/rme-exit.c                     |  87 ++
 arch/arm64/kvm/rme.c                          | 208 ++++-
 arch/arm64/mm/mem_encrypt.c                   |  10 +
 crypto/asymmetric_keys/x509_cert_parser.c     |   9 +
 crypto/asymmetric_keys/x509_loader.c          |  38 +-
 crypto/asymmetric_keys/x509_parser.h          |  40 +-
 drivers/iommu/iommufd/device.c                |  54 ++
 drivers/iommu/iommufd/iommufd_private.h       |   7 +
 drivers/iommu/iommufd/main.c                  |  13 +
 drivers/iommu/iommufd/viommu.c                | 178 +++-
 drivers/pci/tsm.c                             | 229 ++++-
 drivers/vfio/pci/vfio_pci_core.c              |  20 +-
 drivers/virt/coco/Kconfig                     |   5 +-
 drivers/virt/coco/Makefile                    |   7 +-
 drivers/virt/coco/arm-cca-guest/Kconfig       |  10 +-
 drivers/virt/coco/arm-cca-guest/Makefile      |   3 +
 .../{arm-cca-guest.c => arm-cca.c}            | 175 +++-
 drivers/virt/coco/arm-cca-guest/rsi-da.c      | 576 ++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h      |  73 ++
 drivers/virt/coco/arm-cca-host/Kconfig        |  17 +
 drivers/virt/coco/arm-cca-host/Makefile       |   5 +
 drivers/virt/coco/arm-cca-host/arm-cca.c      | 384 ++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.c       | 857 ++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h       | 108 +++
 drivers/virt/coco/host/Kconfig                |   6 -
 drivers/virt/coco/host/Makefile               |   6 -
 drivers/virt/coco/{host => }/tsm-core.c       |  27 +
 include/keys/asymmetric-type.h                |   2 +
 include/keys/x509-parser.h                    |  55 ++
 include/linux/device.h                        |   1 +
 include/linux/iommufd.h                       |   4 +
 include/linux/kvm_host.h                      |   1 +
 include/linux/pci-tsm.h                       |  37 +-
 include/linux/swiotlb.h                       |   4 +
 include/linux/tsm.h                           |  29 +
 include/uapi/linux/iommufd.h                  |  69 ++
 48 files changed, 3887 insertions(+), 200 deletions(-)
 create mode 100644 arch/arm64/include/asm/rhi.h
 create mode 100644 arch/arm64/kernel/rhi.c
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (62%)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.h
 create mode 100644 drivers/virt/coco/arm-cca-host/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-host/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-host/arm-cca.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmm-da.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmm-da.h
 delete mode 100644 drivers/virt/coco/host/Kconfig
 delete mode 100644 drivers/virt/coco/host/Makefile
 rename drivers/virt/coco/{host => }/tsm-core.c (85%)
 create mode 100644 include/keys/x509-parser.h

---

## [2] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 01/38] tsm: Add tsm_bind/unbind helpers*

This will be later used by iommufd to bind a tdi to guest.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/host/tsm-core.c | 18 ++++++++++++++++++
 include/linux/tsm.h               |  3 +++
 2 files changed, 21 insertions(+)

diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/host/tsm-core.c
index bd9e09b07412..0a7c9aa46c56 100644
--- a/drivers/virt/coco/host/tsm-core.c
+++ b/drivers/virt/coco/host/tsm-core.c
@@ -116,6 +116,24 @@ void tsm_ide_stream_unregister(struct pci_ide *ide)
 }
 EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
 
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
+	return pci_tsm_unbind(to_pci_dev(dev));
+}
+EXPORT_SYMBOL_GPL(tsm_unbind);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_core_dev *core = container_of(dev, typeof(*core), dev);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 915c4c8b061b..0aab8d037e71 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -118,6 +118,9 @@ struct tsm_core_dev *tsm_register(struct device *parent,
 void tsm_unregister(struct tsm_core_dev *tsm_core);
 struct pci_dev;
 struct pci_ide;
+struct kvm;
 int tsm_ide_stream_register(struct pci_dev *pdev, struct pci_ide *ide);
 void tsm_ide_stream_unregister(struct pci_ide *ide);
+int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id);
+int tsm_unbind(struct device *dev);
 #endif /* __TSM_H */

---

## [3] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 02/38] tsm: Move tsm core outside the host directory*

A later patch will add guest changes that will also use the same
infrastructure.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/Kconfig               | 3 ++-
 drivers/virt/coco/Makefile              | 6 ++++--
 drivers/virt/coco/host/Kconfig          | 6 ------
 drivers/virt/coco/host/Makefile         | 6 ------
 drivers/virt/coco/{host => }/tsm-core.c | 0
 5 files changed, 6 insertions(+), 15 deletions(-)
 delete mode 100644 drivers/virt/coco/host/Kconfig
 delete mode 100644 drivers/virt/coco/host/Makefile
 rename drivers/virt/coco/{host => }/tsm-core.c (100%)

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 14e7cf145d85..57248b088545 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -15,4 +15,5 @@ source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
 
-source "drivers/virt/coco/host/Kconfig"
+config TSM
+	tristate
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 73f1b7bc5b11..04e124b2d7cf 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -2,10 +2,12 @@
 #
 # Confidential computing related collateral
 #
+
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
-obj-$(CONFIG_TSM_REPORTS)	+= guest/
-obj-y				+= host/
+
+obj-$(CONFIG_TSM) 		+= tsm-core.o
+obj-y				+= guest/
diff --git a/drivers/virt/coco/host/Kconfig b/drivers/virt/coco/host/Kconfig
deleted file mode 100644
index 4fbc6ef34f12..000000000000
--- a/drivers/virt/coco/host/Kconfig
+++ /dev/null
@@ -1,6 +0,0 @@
-# SPDX-License-Identifier: GPL-2.0-only
-#
-# TSM (TEE Security Manager) Common infrastructure and host drivers
-#
-config TSM
-	tristate
diff --git a/drivers/virt/coco/host/Makefile b/drivers/virt/coco/host/Makefile
deleted file mode 100644
index be0aba6007cd..000000000000
--- a/drivers/virt/coco/host/Makefile
+++ /dev/null
@@ -1,6 +0,0 @@
-# SPDX-License-Identifier: GPL-2.0-only
-#
-# TSM (TEE Security Manager) Common infrastructure and host drivers
-
-obj-$(CONFIG_TSM) += tsm.o
-tsm-y := tsm-core.o
diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/tsm-core.c
similarity index 100%
rename from drivers/virt/coco/host/tsm-core.c
rename to drivers/virt/coco/tsm-core.c

---

## [4] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 03/38] tsm: Move dsm_dev from pci_tdi to pci_tsm*

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/tsm.c       | 72 ++++++++++++++++++++++++-----------------
 include/linux/pci-tsm.h |  4 +--
 2 files changed, 45 insertions(+), 31 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 794de2f258c3..e4a3b5b37939 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -415,15 +415,55 @@ static enum pci_tsm_type pci_tsm_type(struct pci_dev *pdev)
 	return PCI_TSM_INVALID;
 }
 
+/* lookup the Device Security Manager (DSM) pf0 for @pdev */
+static struct pci_dev *dsm_dev_get(struct pci_dev *pdev)
+{
+	struct pci_dev *uport_pf0;
+
+	struct pci_dev *pf0 __free(pci_dev_put) = pf0_dev_get(pdev);
+	if (!pf0)
+		return NULL;
+
+	if (pf0 == pdev)
+		return no_free_ptr(pf0);
+
+	/* Check that @pf0 was not initialized as PCI_TSM_DOWNSTREAM */
+	if (pf0->tsm && pf0->tsm->type == PCI_TSM_PF0)
+		return no_free_ptr(pf0);
+
+	/*
+	 * For cases where a switch may be hosting TDISP services on
+	 * behalf of downstream devices, check the first usptream port
+	 * relative to this endpoint.
+	 */
+	if (!pdev->dev.parent || !pdev->dev.parent->parent)
+		return NULL;
+
+	uport_pf0 = to_pci_dev(pdev->dev.parent->parent);
+	if (!uport_pf0->tsm)
+		return NULL;
+	return pci_dev_get(uport_pf0);
+}
+
 /**
  * pci_tsm_initialize() - base 'struct pci_tsm' initialization
  * @pdev: The PCI device
  * @tsm: context to initialize
  */
-void pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm)
+int pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm)
 {
+	struct pci_dev *dsm_dev __free(pci_dev_put) = dsm_dev_get(pdev);
+	if (!dsm_dev)
+		return -EINVAL;
+
 	tsm->type = pci_tsm_type(pdev);
 	tsm->pdev = pdev;
+	/*
+	 * No reference needed because when we destroy
+	 * dsm_dev all the tdis get destroyed before that.
+	 */
+	tsm->dsm_dev = dsm_dev;
+	return 0;
 }
 EXPORT_SYMBOL_GPL(pci_tsm_initialize);
 
@@ -447,7 +487,8 @@ int pci_tsm_pf0_initialize(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm)
 	}
 
 	tsm->state = PCI_TSM_INIT;
-	pci_tsm_initialize(pdev, &tsm->tsm);
+	if (pci_tsm_initialize(pdev, &tsm->tsm))
+		return -ENODEV;
 
 	return 0;
 }
@@ -612,32 +653,6 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 }
 EXPORT_SYMBOL_GPL(pci_tsm_doe_transfer);
 
-/* lookup the Device Security Manager (DSM) pf0 for @pdev */
-static struct pci_dev *dsm_dev_get(struct pci_dev *pdev)
-{
-	struct pci_dev *uport_pf0;
-
-	struct pci_dev *pf0 __free(pci_dev_put) = pf0_dev_get(pdev);
-	if (!pf0)
-		return NULL;
-
-	/* Check that @pf0 was not initialized as PCI_TSM_DOWNSTREAM */
-	if (pf0->tsm && pf0->tsm->type == PCI_TSM_PF0)
-		return no_free_ptr(pf0);
-
-	/*
-	 * For cases where a switch may be hosting TDISP services on
-	 * behalf of downstream devices, check the first usptream port
-	 * relative to this endpoint.
-	 */
-	if (!pdev->dev.parent || !pdev->dev.parent->parent)
-		return NULL;
-
-	uport_pf0 = to_pci_dev(pdev->dev.parent->parent);
-	if (!uport_pf0->tsm)
-		return NULL;
-	return pci_dev_get(uport_pf0);
-}
 
 /* Only implement non-interruptible lock for now */
 static struct mutex *tdi_ops_lock(struct pci_dev *pf0_dev)
@@ -695,7 +710,6 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
 		return -ENXIO;
 
 	tdi->pdev = pdev;
-	tdi->dsm_dev = dsm_dev;
 	tdi->kvm = kvm;
 	pdev->tsm->tdi = tdi;
 
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 1920ca591a42..0d4303726b25 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -38,7 +38,6 @@ enum pci_tsm_type {
  */
 struct pci_tdi {
 	struct pci_dev *pdev;
-	struct pci_dev *dsm_dev;
 	struct kvm *kvm;
 };
 
@@ -56,6 +55,7 @@ struct pci_tdi {
  */
 struct pci_tsm {
 	struct pci_dev *pdev;
+	struct pci_dev *dsm_dev;
 	enum pci_tsm_type type;
 	struct pci_tdi *tdi;
 };
@@ -173,7 +173,7 @@ void pci_tsm_core_unregister(const struct pci_tsm_ops *ops);
 int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 			 const void *req, size_t req_sz, void *resp,
 			 size_t resp_sz);
-void pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm);
+int pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm);
 int pci_tsm_pf0_initialize(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm);
 int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id);
 int pci_tsm_unbind(struct pci_dev *pdev);

---

## [5] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private memory*

Currently, we enforce the use of bounce buffers to ensure that memory
accessed by non-secure devices is explicitly shared with the host [1].
However, for secure devices, this approach must be avoided.

To achieve this, we introduce a device flag that controls whether a
bounce buffer allocation is required for the device. Additionally, this flag is
used to manage the top IPA bit assignment for setting up
protected/unprotected IPA aliases.

[1] commit fbf979a01375 ("arm64: Enforce bounce buffers for realm DMA")

based on changes from Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  6 +-----
 arch/arm64/mm/mem_encrypt.c          | 10 ++++++++++
 drivers/pci/tsm.c                    |  6 ++++++
 include/linux/device.h               |  1 +
 include/linux/swiotlb.h              |  4 ++++
 5 files changed, 22 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index 314b2b52025f..d77c10cd5b79 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -15,14 +15,10 @@ int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops);
 
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
+bool force_dma_unencrypted(struct device *dev);
 
 int realm_register_memory_enc_ops(void);
 
-static inline bool force_dma_unencrypted(struct device *dev)
-{
-	return is_realm_world();
-}
-
 /*
  * For Arm CCA guests, canonical addresses are "encrypted", so no changes
  * required for dma_addr_encrypted().
diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
index ee3c0ab04384..279696a8af3f 100644
--- a/arch/arm64/mm/mem_encrypt.c
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -17,6 +17,7 @@
 #include <linux/compiler.h>
 #include <linux/err.h>
 #include <linux/mm.h>
+#include <linux/device.h>
 
 #include <asm/mem_encrypt.h>
 
@@ -48,3 +49,12 @@ int set_memory_decrypted(unsigned long addr, int numpages)
 	return crypt_ops->decrypt(addr, numpages);
 }
 EXPORT_SYMBOL_GPL(set_memory_decrypted);
+
+bool force_dma_unencrypted(struct device *dev)
+{
+	if (dev->tdi_enabled)
+		return false;
+
+	return is_realm_world();
+}
+EXPORT_SYMBOL_GPL(force_dma_unencrypted);
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index e4a3b5b37939..60f50d57a725 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -120,6 +120,7 @@ static int pci_tsm_disconnect(struct pci_dev *pdev)
 
 	tsm_ops->disconnect(pdev);
 	tsm->state = PCI_TSM_INIT;
+	pdev->dev.tdi_enabled = false;
 
 	return 0;
 }
@@ -199,6 +200,8 @@ static int pci_tsm_accept(struct pci_dev *pdev)
 	if (rc)
 		return rc;
 	tsm->state = PCI_TSM_ACCEPT;
+	pdev->dev.tdi_enabled = true;
+
 	return 0;
 }
 
@@ -557,6 +560,9 @@ static void __pci_tsm_init(struct pci_dev *pdev)
 	default:
 		break;
 	}
+
+	/* FIXME!! should this be default true and switch to false for TEE capable device */
+	pdev->dev.tdi_enabled = false;
 }
 
 void pci_tsm_init(struct pci_dev *pdev)
diff --git a/include/linux/device.h b/include/linux/device.h
index 4940db137fff..d62e0dd9d8ee 100644
--- a/include/linux/device.h
+++ b/include/linux/device.h
@@ -688,6 +688,7 @@ struct device {
 #ifdef CONFIG_IOMMU_DMA
 	bool			dma_iommu:1;
 #endif
+	bool			tdi_enabled:1;
 };
 
 /**
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..61e7cff7768b 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -173,6 +173,10 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+	if (dev->tdi_enabled) {
+		dev_warn_once(dev, "(TIO) Disable SWIOTLB");
+		return false;
+	}
 	return mem && mem->force_bounce;
 }

---

## [6] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 05/38] tsm: Don't overload connect*

We need separate handling in the guest while destroying the device.
Hence switch to new callback lock and unlock. Hide the connect sysfs
file in guest.

guest sysfs will now looks like
ls -al  /sys/bus/pci/devices/0000:02:00.0/tsm/
total 0
drwxr-xr-x    2 root     root             0 Jan  1 00:00 .
drwxr-xr-x    7 root     root             0 Jan  1 00:00 ..
-rw-r--r--    1 root     root          4096 Jan  1 00:00 accept
-rw-r--r--    1 root     root          4096 Jan  1 00:00 lock

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/tsm.c       | 136 ++++++++++++++++++++++++++++++++++------
 include/linux/pci-tsm.h |   3 +
 2 files changed, 121 insertions(+), 18 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 60f50d57a725..80607082b7f0 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -125,18 +125,6 @@ static int pci_tsm_disconnect(struct pci_dev *pdev)
 	return 0;
 }
 
-/*
- * TDISP locked state temporarily makes the device inaccessible, do not
- * surprise live attached drivers
- */
-static int __driver_idle_connect(struct pci_dev *pdev)
-{
-	guard(device)(&pdev->dev);
-	if (pdev->dev.driver)
-		return -EBUSY;
-	return tsm_ops->connect(pdev);
-}
-
 /*
  * When the registered ops support accept it indicates that this is a
  * TVM-side (guest) TSM operations structure. In this mode ->connect()
@@ -162,10 +150,7 @@ static int pci_tsm_connect(struct pci_dev *pdev)
 	if (tsm->state >= PCI_TSM_CONNECT)
 		return 0;
 
-	if (tvm_mode())
-		rc = __driver_idle_connect(pdev);
-	else
-		rc = tsm_ops->connect(pdev);
+	rc = tsm_ops->connect(pdev);
 	if (rc)
 		return rc;
 	tsm->state = PCI_TSM_CONNECT;
@@ -299,6 +284,99 @@ static ssize_t accept_show(struct device *dev, struct device_attribute *attr,
 }
 static DEVICE_ATTR_RW(accept);
 
+static int pci_tsm_unlock(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
+
+	struct mutex *lock __free(tsm_ops_unlock) = tsm_ops_lock(tsm);
+	if (!lock)
+		return -EINTR;
+
+	if (tsm->state < PCI_TSM_INIT)
+		return -ENXIO;
+	if (tsm->state < PCI_TSM_LOCK)
+		return 0;
+
+	tsm_ops->unlock(pdev);
+	tsm->state = PCI_TSM_INIT;
+	pdev->dev.tdi_enabled = false;
+
+	return 0;
+}
+
+/*
+ * TDISP locked state temporarily makes the device inaccessible, do not
+ * surprise live attached drivers
+ */
+static int __driver_idle_lock(struct pci_dev *pdev)
+{
+	guard(device)(&pdev->dev);
+	if (pdev->dev.driver)
+		return -EBUSY;
+	return tsm_ops->lock(pdev);
+}
+
+static int pci_tsm_lock(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
+	int rc;
+
+	struct mutex *lock __free(tsm_ops_unlock) = tsm_ops_lock(tsm);
+	if (!lock)
+		return -EINTR;
+
+	if (tsm->state < PCI_TSM_INIT)
+		return -ENXIO;
+
+	rc = __driver_idle_lock(pdev);
+	if (rc)
+		return rc;
+	tsm->state = PCI_TSM_CONNECT;
+	return 0;
+}
+
+static ssize_t lock_store(struct device *dev, struct device_attribute *attr,
+			  const char *buf, size_t len)
+{
+	int rc;
+	bool connect;
+	struct pci_dev *pdev = to_pci_dev(dev);
+
+	rc = kstrtobool(buf, &connect);
+	if (rc)
+		return rc;
+
+	struct rw_semaphore *lock __free(tsm_read_unlock) = tsm_read_lock();
+	if (!lock)
+		return -EINTR;
+
+	if (connect)
+		rc = pci_tsm_lock(pdev);
+	else
+		rc = pci_tsm_unlock(pdev);
+	if (rc)
+		return rc;
+	return len;
+}
+
+static ssize_t lock_show(struct device *dev, struct device_attribute *attr,
+			 char *buf)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct pci_tsm_pf0 *tsm;
+
+	struct rw_semaphore *lock __free(tsm_read_unlock) = tsm_read_lock();
+	if (!lock)
+		return -EINTR;
+
+	if (!pdev->tsm)
+		return -ENXIO;
+
+	tsm = to_pci_tsm_pf0(pdev->tsm);
+	return sysfs_emit(buf, "%d\n", tsm->state >= PCI_TSM_LOCK);
+}
+static DEVICE_ATTR_RW(lock);
+
 static umode_t pci_tsm_pf0_attr_visible(struct kobject *kobj,
 					struct attribute *a, int n)
 {
@@ -306,6 +384,11 @@ static umode_t pci_tsm_pf0_attr_visible(struct kobject *kobj,
 		/* Host context, filter out guest only attributes */
 		if (a == &dev_attr_accept.attr)
 			return 0;
+		if (a == &dev_attr_lock.attr)
+			return 0;
+	} else {
+		if (a == &dev_attr_connect.attr)
+			return 0;
 	}
 
 	return a->mode;
@@ -325,6 +408,7 @@ DEFINE_SYSFS_GROUP_VISIBLE(pci_tsm_pf0);
 static struct attribute *pci_tsm_pf0_attrs[] = {
 	&dev_attr_connect.attr,
 	&dev_attr_accept.attr,
+	&dev_attr_lock.attr,
 	NULL
 };
 
@@ -537,7 +621,8 @@ static void pci_tsm_pf0_init(struct pci_dev *pdev)
 		return;
 
 	pdev->tsm = no_free_ptr(pci_tsm);
-	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	if (!tvm_mode())
+		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
 	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_pf0_attr_group);
 	if (pci_tsm_owner_attr_group)
 		sysfs_merge_group(&pdev->dev.kobj, pci_tsm_owner_attr_group);
@@ -602,6 +687,19 @@ static void pci_tsm_pf0_destroy(struct pci_dev *pdev)
 	__pci_tsm_pf0_destroy(tsm);
 }
 
+static void pci_tsm_guest_destroy(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
+
+	if (tsm->state > PCI_TSM_INIT)
+		pci_tsm_unlock(pdev);
+	pdev->tsm = NULL;
+	if (pci_tsm_owner_attr_group)
+		sysfs_unmerge_group(&pdev->dev.kobj, pci_tsm_owner_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_pf0_attr_group);
+	__pci_tsm_pf0_destroy(tsm);
+}
+
 static void __pci_tsm_destroy(struct pci_dev *pdev)
 {
 	struct pci_tsm *pci_tsm = pdev->tsm;
@@ -611,7 +709,9 @@ static void __pci_tsm_destroy(struct pci_dev *pdev)
 
 	lockdep_assert_held_write(&pci_tsm_rwsem);
 
-	if (is_pci_tsm_pf0(pdev)) {
+	if (tvm_mode()) {
+		pci_tsm_guest_destroy(pdev);
+	} else if (is_pci_tsm_pf0(pdev)) {
 		pci_tsm_pf0_destroy(pdev);
 	} else {
 		__pci_tsm_unbind(pdev);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 0d4303726b25..7639e7963681 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -11,6 +11,7 @@ enum pci_tsm_state {
 	PCI_TSM_ERR = -1,
 	PCI_TSM_INIT,
 	PCI_TSM_CONNECT,
+	PCI_TSM_LOCK,
 	PCI_TSM_ACCEPT,
 };
 
@@ -153,6 +154,8 @@ struct pci_tsm_ops {
 	void (*remove)(struct pci_tsm *tsm);
 	int (*connect)(struct pci_dev *pdev);
 	void (*disconnect)(struct pci_dev *pdev);
+	int (*lock)(struct pci_dev *pdev);
+	void (*unlock)(struct pci_dev *pdev);
 	struct pci_tdi *(*bind)(struct pci_dev *pdev, struct pci_dev *pf0_dev,
 				struct kvm *kvm, u64 tdi_id);
 	void (*unbind)(struct pci_tdi *tdi);

---

## [7] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar mapping with IORESOURCE_EXCLUSIVE*

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/device.c          | 54 +++++++++++++++++++++++++
 drivers/iommu/iommufd/iommufd_private.h |  4 ++
 drivers/iommu/iommufd/main.c            |  3 ++
 drivers/vfio/pci/vfio_pci_core.c        |  9 ++++-
 include/linux/iommufd.h                 |  1 +
 include/uapi/linux/iommufd.h            |  1 +
 6 files changed, 71 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/iommufd/device.c b/drivers/iommu/iommufd/device.c
index 65fbd098f9e9..3bd6972836a1 100644
--- a/drivers/iommu/iommufd/device.c
+++ b/drivers/iommu/iommufd/device.c
@@ -1660,3 +1660,57 @@ int iommufd_get_hw_info(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &idev->obj);
 	return rc;
 }
+
+static int iommufd_device_option_exclusive_ranges(struct iommu_option *cmd,
+					  struct iommufd_device *idev)
+{
+	if (cmd->op == IOMMU_OPTION_OP_GET) {
+		cmd->val64 = idev->flags & IOMMUFD_DEVICE_EXCLUSIVE_RANGE;
+		return 0;
+	}
+
+	if (cmd->op == IOMMU_OPTION_OP_SET) {
+		if (cmd->val64 == 0) {
+			idev->flags &= ~IOMMUFD_DEVICE_EXCLUSIVE_RANGE;
+			return 0;
+		} else if (cmd->val64 & IOMMUFD_DEVICE_EXCLUSIVE_RANGE) {
+			idev->flags |= IOMMUFD_DEVICE_EXCLUSIVE_RANGE;
+			return 0;
+		}
+		return -EINVAL;
+	}
+	return -EOPNOTSUPP;
+}
+bool iommufd_device_need_exclusive_range(struct iommufd_device *idev)
+{
+	return !!(idev->flags & IOMMUFD_DEVICE_EXCLUSIVE_RANGE);
+}
+
+int iommufd_device_option(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_option *cmd = ucmd->cmd;
+	struct iommufd_device *idev;
+	int rc = 0;
+
+	if (cmd->__reserved)
+		return -EOPNOTSUPP;
+
+	idev = iommufd_get_device(ucmd, cmd->object_id);
+	if (IS_ERR(idev))
+		return PTR_ERR(idev);
+
+	mutex_lock(&idev->igroup->lock);
+
+
+	switch (cmd->option_id) {
+	case IOMMU_OPTION_EXCLUSIVE_RANGES:
+		rc = iommufd_device_option_exclusive_ranges(cmd, idev);
+		break;
+	default:
+		rc = -EOPNOTSUPP;
+	}
+
+	mutex_unlock(&idev->igroup->lock);
+	iommufd_put_object(ucmd->ictx, &idev->obj);
+	return rc;
+}
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 0da2a81eedfa..fce68714c80f 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -346,6 +346,7 @@ int iommufd_ioas_change_process(struct iommufd_ucmd *ucmd);
 int iommufd_ioas_copy(struct iommufd_ucmd *ucmd);
 int iommufd_ioas_unmap(struct iommufd_ucmd *ucmd);
 int iommufd_ioas_option(struct iommufd_ucmd *ucmd);
+int iommufd_device_option(struct iommufd_ucmd *ucmd);
 int iommufd_option_rlimit_mode(struct iommu_option *cmd,
 			       struct iommufd_ctx *ictx);
 
@@ -489,10 +490,13 @@ struct iommufd_device {
 	/* always the physical device */
 	struct device *dev;
 	bool enforce_cache_coherency;
+	unsigned long flags;
 	struct iommufd_vdevice *vdev;
 	bool destroying;
 };
 
+#define IOMMUFD_DEVICE_EXCLUSIVE_RANGE		BIT(0)
+
 static inline struct iommufd_device *
 iommufd_get_device(struct iommufd_ucmd *ucmd, u32 id)
 {
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 15af7ced0501..89830da8b418 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -376,6 +376,9 @@ static int iommufd_option(struct iommufd_ucmd *ucmd)
 	case IOMMU_OPTION_HUGE_PAGES:
 		rc = iommufd_ioas_option(ucmd);
 		break;
+	case IOMMU_OPTION_EXCLUSIVE_RANGES:
+		rc = iommufd_device_option(ucmd);
+		break;
 	default:
 		return -EOPNOTSUPP;
 	}
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index 6328c3a05bcd..bee3cf3226e9 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -1753,8 +1753,15 @@ int vfio_pci_core_mmap(struct vfio_device *core_vdev, struct vm_area_struct *vma
 	 * we need to request the region and the barmap tracks that.
 	 */
 	if (!vdev->barmap[index]) {
-		ret = pci_request_selected_regions(pdev,
+
+		if (core_vdev->iommufd_device &&
+		    iommufd_device_need_exclusive_range(core_vdev->iommufd_device))
+			ret = pci_request_selected_regions_exclusive(pdev,
+							1 << index, "vfio-pci");
+		else
+			ret = pci_request_selected_regions(pdev,
 						   1 << index, "vfio-pci");
+
 		if (ret)
 			return ret;
 
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 6e7efe83bc5d..55ae02581f9b 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -70,6 +70,7 @@ void iommufd_device_detach(struct iommufd_device *idev, ioasid_t pasid);
 
 struct iommufd_ctx *iommufd_device_to_ictx(struct iommufd_device *idev);
 u32 iommufd_device_to_id(struct iommufd_device *idev);
+bool iommufd_device_need_exclusive_range(struct iommufd_device *idev);
 
 struct iommufd_access_ops {
 	u8 needs_pin_pages : 1;
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index c218c89e0e2e..548d4b5afcd4 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -310,6 +310,7 @@ struct iommu_ioas_unmap {
 enum iommufd_option {
 	IOMMU_OPTION_RLIMIT_MODE = 0,
 	IOMMU_OPTION_HUGE_PAGES = 1,
+	IOMMU_OPTION_EXCLUSIVE_RANGES = 2,
 };
 
 /**

---

## [8] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 07/38] iommufd/viommu: Add support to associate viommu with kvm instance*

The associated kvm instance will be used in later patch by iommufd to
bind a tdi to kvm.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/viommu.c | 45 +++++++++++++++++++++++++++++++++-
 include/linux/iommufd.h        |  3 +++
 include/uapi/linux/iommufd.h   | 12 +++++++++
 3 files changed, 59 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 2ca5809b238b..59f1e1176f7f 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -2,6 +2,36 @@
 /* Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES
  */
 #include "iommufd_private.h"
+#include "linux/tsm.h"
+
+#if IS_ENABLED(CONFIG_KVM)
+#include <linux/kvm_host.h>
+
+static int viommu_get_kvm(struct iommufd_viommu *viommu, int kvm_vm_fd)
+{
+	int rc = -EBADF;
+	struct file *filp;
+
+	filp = fget(kvm_vm_fd);
+
+	if (!file_is_kvm(filp))
+		goto err_out;
+
+	/* hold the kvm reference via file descriptor */
+	viommu->kvm_filp = filp;
+	return 0;
+err_out:
+	viommu->kvm_filp = NULL;
+	fput(filp);
+	return rc;
+}
+
+static void viommu_put_kvm(struct iommufd_viommu *viommu)
+{
+	fput(viommu->kvm_filp);
+	viommu->kvm_filp = NULL;
+}
+#endif
 
 void iommufd_viommu_destroy(struct iommufd_object *obj)
 {
@@ -12,6 +42,8 @@ void iommufd_viommu_destroy(struct iommufd_object *obj)
 		viommu->ops->destroy(viommu);
 	refcount_dec(&viommu->hwpt->common.obj.users);
 	xa_destroy(&viommu->vdevs);
+
+	viommu_put_kvm(viommu);
 }
 
 int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
@@ -29,7 +61,9 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	size_t viommu_size;
 	int rc;
 
-	if (cmd->flags || cmd->type == IOMMU_VIOMMU_TYPE_DEFAULT)
+	if (cmd->flags & ~IOMMU_VIOMMU_KVM_FD)
+		return -EOPNOTSUPP;
+	if (cmd->type == IOMMU_VIOMMU_TYPE_DEFAULT)
 		return -EOPNOTSUPP;
 
 	idev = iommufd_get_device(ucmd, cmd->dev_id);
@@ -100,8 +134,17 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 		goto out_put_hwpt;
 	}
 
+	/* get the kvm details if specified. */
+	if (cmd->flags & IOMMU_VIOMMU_KVM_FD) {
+		rc = viommu_get_kvm(viommu, cmd->kvm_vm_fd);
+		if (rc)
+			goto out_put_hwpt;
+	}
+
 	cmd->out_viommu_id = viommu->obj.id;
 	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+	if (rc)
+		viommu_put_kvm(viommu);
 
 out_put_hwpt:
 	iommufd_put_object(ucmd->ictx, &hwpt_paging->common.obj);
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 55ae02581f9b..b7617ba7a536 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -12,6 +12,7 @@
 #include <linux/refcount.h>
 #include <linux/types.h>
 #include <linux/xarray.h>
+#include <linux/file.h>
 #include <uapi/linux/iommufd.h>
 
 struct device;
@@ -58,6 +59,7 @@ struct iommufd_object {
 	unsigned int id;
 };
 
+struct kvm;
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
 					   struct device *dev, u32 *id);
 void iommufd_device_unbind(struct iommufd_device *idev);
@@ -102,6 +104,7 @@ struct iommufd_viommu {
 	struct iommufd_ctx *ictx;
 	struct iommu_device *iommu_dev;
 	struct iommufd_hwpt_paging *hwpt;
+	struct file *kvm_filp;
 
 	const struct iommufd_viommu_ops *ops;
 
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 548d4b5afcd4..9014c61a97d4 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -1023,6 +1023,17 @@ struct iommu_viommu_tegra241_cmdqv {
 	__aligned_u64 out_vintf_mmap_length;
 };
 
+/**
+ * define IOMMU_VIOMMU_KVM_FD - Flag indicating a valid KVM VM file descriptor
+ *
+ * This flag must be set when allocating a viommu instance that will be
+ * associated with a specific KVM VM. When allocating a viommu instance for a
+ * KVM VM, this flag must be set to inform the initialization logic that
+ * @iommu_viommu_alloc::kvm_vm_fd is properly initialized. If this flag is not
+ * provided but @iommu_viommu_alloc::kvm_vm_fd field will be ignored.
+ */
+#define IOMMU_VIOMMU_KVM_FD	BIT(0)
+
 /**
  * struct iommu_viommu_alloc - ioctl(IOMMU_VIOMMU_ALLOC)
  * @size: sizeof(struct iommu_viommu_alloc)
@@ -1057,6 +1068,7 @@ struct iommu_viommu_alloc {
 	__u32 data_len;
 	__u32 __reserved;
 	__aligned_u64 data_uptr;
+	__u32 kvm_vm_fd;
 };
 #define IOMMU_VIOMMU_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VIOMMU_ALLOC)

---

## [9] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 08/38] iommufd/tsm: Add tsm_op iommufd ioctls*

Add operations bind and unbind used to bind a TDI to the secure guest.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/iommufd_private.h |  1 +
 drivers/iommu/iommufd/main.c            |  3 ++
 drivers/iommu/iommufd/viommu.c          | 50 +++++++++++++++++++++++++
 drivers/vfio/pci/vfio_pci_core.c        | 10 +++++
 include/uapi/linux/iommufd.h            | 18 +++++++++
 5 files changed, 82 insertions(+)

diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index fce68714c80f..e08186f1d102 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -697,6 +697,7 @@ void iommufd_vdevice_destroy(struct iommufd_object *obj);
 void iommufd_vdevice_abort(struct iommufd_object *obj);
 int iommufd_hw_queue_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_hw_queue_destroy(struct iommufd_object *obj);
+int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd);
 
 static inline struct iommufd_vdevice *
 iommufd_get_vdevice(struct iommufd_ctx *ictx, u32 id)
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 89830da8b418..4f2a1995bd1f 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -410,6 +410,7 @@ union ucmd_buffer {
 	struct iommu_veventq_alloc veventq;
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
+	struct iommu_vdevice_tsm_op tsm_op;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -471,6 +472,8 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 __reserved),
 	IOCTL_OP(IOMMU_VIOMMU_ALLOC, iommufd_viommu_alloc_ioctl,
 		 struct iommu_viommu_alloc, out_viommu_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_OP, iommufd_vdevice_tsm_op_ioctl,
+		 struct iommu_vdevice_tsm_op, vdevice_id),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 59f1e1176f7f..c934312e5397 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -162,6 +162,9 @@ void iommufd_vdevice_abort(struct iommufd_object *obj)
 
 	lockdep_assert_held(&idev->igroup->lock);
 
+#ifdef CONFIG_TSM
+	tsm_unbind(idev->dev);
+#endif
 	if (vdev->destroy)
 		vdev->destroy(vdev);
 	/* xa_cmpxchg is okay to fail if alloc failed xa_cmpxchg previously */
@@ -471,3 +474,50 @@ int iommufd_hw_queue_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &viommu->obj);
 	return rc;
 }
+
+#ifdef CONFIG_TSM
+int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_tsm_op *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	struct kvm *kvm;
+	int rc = -ENODEV;
+
+	if (cmd->flags)
+		return -EOPNOTSUPP;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	kvm = vdev->viommu->kvm_filp->private_data;
+	if (kvm) {
+		/*
+		 * tsm layer will make take care of parallel calls to tsm_bind/unbind
+		 */
+		if (cmd->op == IOMMU_VDEICE_TSM_BIND)
+			rc = tsm_bind(vdev->idev->dev, kvm, vdev->virt_id);
+		else if (cmd->op == IOMMU_VDEICE_TSM_UNBIND)
+			rc = tsm_unbind(vdev->idev->dev);
+
+		if (rc) {
+			rc = -ENODEV;
+			goto out_put_vdev;
+		}
+	} else {
+		goto out_put_vdev;
+	}
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
+#else /* !CONFIG_TSM */
+int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
+{
+	return -ENODEV;
+}
+#endif
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index bee3cf3226e9..afdb39c6aefd 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -694,6 +694,16 @@ void vfio_pci_core_close_device(struct vfio_device *core_vdev)
 #if IS_ENABLED(CONFIG_EEH)
 	eeh_dev_release(vdev->pdev);
 #endif
+
+#if 0
+	/*
+	 * destroy vdevice which involves tsm unbind before we disable pci disable
+	 * A MSE/BME clear will transition the device to error state.
+	 */
+	if (core_vdev->iommufd_device)
+		iommufd_device_tombstone_vdevice(core_vdev->iommufd_device);
+#endif
+
 	vfio_pci_core_disable(vdev);
 
 	mutex_lock(&vdev->igate);
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 9014c61a97d4..8b1fbf1ef25c 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -57,6 +57,7 @@ enum {
 	IOMMUFD_CMD_IOAS_CHANGE_PROCESS = 0x92,
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
 	IOMMUFD_CMD_HW_QUEUE_ALLOC = 0x94,
+	IOMMUFD_CMD_VDEVICE_TSM_OP = 0x95,
 };
 
 /**
@@ -1127,6 +1128,23 @@ enum iommu_veventq_flag {
 	IOMMU_VEVENTQ_FLAG_LOST_EVENTS = (1U << 0),
 };
 
+/**
+ * struct iommu_vdevice_tsm_OP - ioctl(IOMMU_VDEVICE_TSM_OP)
+ * @size: sizeof(struct iommu_vdevice_tsm_OP)
+ * @op: Either TSM_BIND or TSM_UNBIMD
+ * @flags: Must be 0
+ * @vdevice_id: Object handle for the vDevice. Returned from IOMMU_VDEVICE_ALLOC
+ */
+struct iommu_vdevice_tsm_op {
+	__u32 size;
+	__u32 op;
+	__u32 flags;
+	__u32 vdevice_id;
+};
+#define IOMMU_VDEVICE_TSM_OP	_IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_OP)
+#define IOMMU_VDEICE_TSM_BIND		0x1
+#define IOMMU_VDEICE_TSM_UNBIND		0x2
+
 /**
  * struct iommufd_vevent_header - Virtual Event Header for a vEVENTQ Status
  * @flags: Combination of enum iommu_veventq_flag

---

## [10] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 09/38] iommufd/vdevice: Add TSM Guest request uAPI*

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

Based on changes from: Alexey Kardashevskiy <aik@amd.com>

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/iommufd_private.h |  1 +
 drivers/iommu/iommufd/main.c            |  3 ++
 drivers/iommu/iommufd/viommu.c          | 40 +++++++++++++++++++++++++
 drivers/pci/tsm.c                       | 15 ++++++++--
 drivers/virt/coco/tsm-core.c            |  9 ++++++
 include/linux/pci-tsm.h                 | 30 ++-----------------
 include/linux/tsm.h                     | 23 ++++++++++++++
 include/uapi/linux/iommufd.h            | 28 +++++++++++++++++
 8 files changed, 120 insertions(+), 29 deletions(-)

diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index e08186f1d102..0c0d96135432 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -698,6 +698,7 @@ void iommufd_vdevice_abort(struct iommufd_object *obj);
 int iommufd_hw_queue_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_hw_queue_destroy(struct iommufd_object *obj);
 int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd);
+int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd);
 
 static inline struct iommufd_vdevice *
 iommufd_get_vdevice(struct iommufd_ctx *ictx, u32 id)
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 4f2a1995bd1f..65e60da9caef 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -411,6 +411,7 @@ union ucmd_buffer {
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
 	struct iommu_vdevice_tsm_op tsm_op;
+	struct iommu_vdevice_tsm_guest_request gr;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -474,6 +475,8 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 struct iommu_viommu_alloc, out_viommu_id),
 	IOCTL_OP(IOMMU_VDEVICE_TSM_OP, iommufd_vdevice_tsm_op_ioctl,
 		 struct iommu_vdevice_tsm_op, vdevice_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_GUEST_REQUEST, iommufd_vdevice_tsm_guest_request_ioctl,
+		 struct iommu_vdevice_tsm_guest_request, resp_uptr),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index c934312e5397..9f4d4d69b82b 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -515,9 +515,49 @@ int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &vdev->obj);
 	return rc;
 }
+
+int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_tsm_guest_request *cmd = ucmd->cmd;
+	struct tsm_guest_req_info info = {
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
+	rc = tsm_guest_req(vdev->idev->dev, &info);
+	if (rc)
+		goto err_out;
+
+	cmd->resp_len = info.resp_len;
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+err_out:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
+
 #else /* !CONFIG_TSM */
+
 int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
 {
 	return -ENODEV;
 }
+
+int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd)
+{
+	return -ENODEV;
+}
+
 #endif
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 80607082b7f0..896ef0f5fbe7 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -861,7 +861,7 @@ int pci_tsm_unbind(struct pci_dev *pdev)
 EXPORT_SYMBOL_GPL(pci_tsm_unbind);
 
 /**
- * pci_tsm_guest_req - VFIO/IOMMUFD helper to handle guest requests
+ * pci_tsm_guest_req - IOMMUFD helper to handle guest requests
  * @pdev: @pdev representing a bound tdi
  * @info: envelope for the request
  *
@@ -871,11 +871,12 @@ EXPORT_SYMBOL_GPL(pci_tsm_unbind);
  * posts to userspace (e.g. QEMU) that holds the host-to-guest RID
  * mapping.
  */
-int pci_tsm_guest_req(struct pci_dev *pdev, struct pci_tsm_guest_req_info *info)
+static int __pci_tsm_guest_req(struct pci_dev *pdev, struct tsm_guest_req_info *info)
 {
 	struct pci_tdi *tdi;
 	int rc;
 
+
 	lockdep_assert_held_read(&pci_tsm_rwsem);
 
 	if (!pdev->tsm)
@@ -899,4 +900,14 @@ int pci_tsm_guest_req(struct pci_dev *pdev, struct pci_tsm_guest_req_info *info)
 
 	return 0;
 }
+
+int pci_tsm_guest_req(struct pci_dev *pdev, struct tsm_guest_req_info *info)
+{
+	struct rw_semaphore *lock __free(tsm_read_unlock) = tsm_read_lock();
+	if (!lock)
+		return -EINTR;
+
+	return __pci_tsm_guest_req(pdev, info);
+}
+
 EXPORT_SYMBOL_GPL(pci_tsm_guest_req);
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 0a7c9aa46c56..32b1235518b4 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -134,6 +134,15 @@ int tsm_unbind(struct device *dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unbind);
 
+int tsm_guest_req(struct device *dev, struct tsm_guest_req_info *info)
+{
+	if (!dev_is_pci(dev))
+		return -EINVAL;
+
+	return pci_tsm_guest_req(to_pci_dev(dev), info);
+}
+EXPORT_SYMBOL_GPL(tsm_guest_req);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_core_dev *core = container_of(dev, typeof(*core), dev);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 7639e7963681..530f8b3093f8 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -108,31 +108,7 @@ static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
 	return PCI_FUNC(pdev->devfn) == 0;
 }
 
-enum pci_tsm_guest_req_type {
-	PCI_TSM_GUEST_REQ_TDXC,
-};
-
-/**
- * struct pci_tsm_guest_req_info - parameter for pci_tsm_ops.guest_req()
- * @type: identify the format of the following blobs
- * @type_info: extra input/output info, e.g. firmware error code
- * @type_info_len: the size of @type_info
- * @req: request data buffer filled by guest
- * @req_len: the size of @req filled by guest
- * @resp: response data buffer filled by host
- * @resp_len: for input, the size of @resp buffer filled by guest
- *	      for output, the size of actual response data filled by host
- */
-struct pci_tsm_guest_req_info {
-	enum pci_tsm_guest_req_type type;
-	void *type_info;
-	size_t type_info_len;
-	void *req;
-	size_t req_len;
-	void *resp;
-	size_t resp_len;
-};
-
+struct tsm_guest_req_info;
 /**
  * struct pci_tsm_ops - Low-level TSM-exported interface to the PCI core
  * @probe: probe/accept device for tsm operation, setup DSM context
@@ -160,7 +136,7 @@ struct pci_tsm_ops {
 				struct kvm *kvm, u64 tdi_id);
 	void (*unbind)(struct pci_tdi *tdi);
 	int (*guest_req)(struct pci_dev *pdev,
-			 struct pci_tsm_guest_req_info *info);
+			 struct tsm_guest_req_info *info);
 	int (*accept)(struct pci_dev *pdev);
 };
 
@@ -180,7 +156,7 @@ int pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm);
 int pci_tsm_pf0_initialize(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm);
 int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id);
 int pci_tsm_unbind(struct pci_dev *pdev);
-int pci_tsm_guest_req(struct pci_dev *pdev, struct pci_tsm_guest_req_info *info);
+int pci_tsm_guest_req(struct pci_dev *pdev, struct tsm_guest_req_info *info);
 #else
 static inline int pci_tsm_core_register(const struct pci_tsm_ops *ops,
 					const struct attribute_group *grp)
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 0aab8d037e71..497a3b4df5a0 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -123,4 +123,27 @@ int tsm_ide_stream_register(struct pci_dev *pdev, struct pci_ide *ide);
 void tsm_ide_stream_unregister(struct pci_ide *ide);
 int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id);
 int tsm_unbind(struct device *dev);
+
+/**
+ * struct tsm_guest_req_info - parameter for pci_tsm_ops.guest_req()
+ * @type: identify the format of the following blobs
+ * @type_info: extra input/output info, e.g. firmware error code
+ * @type_info_len: the size of @type_info
+ * @req: request data buffer filled by guest
+ * @req_len: the size of @req filled by guest
+ * @resp: response data buffer filled by host
+ * @resp_len: for input, the size of @resp buffer filled by guest
+ *	      for output, the size of actual response data filled by host
+ */
+struct tsm_guest_req_info {
+	u32 type;
+	void __user *type_info;
+	size_t type_info_len;
+	void __user *req;
+	size_t req_len;
+	void __user *resp;
+	size_t resp_len;
+};
+
+int tsm_guest_req(struct device *dev, struct tsm_guest_req_info *info);
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 8b1fbf1ef25c..56542cfcfa38 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -58,6 +58,7 @@ enum {
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
 	IOMMUFD_CMD_HW_QUEUE_ALLOC = 0x94,
 	IOMMUFD_CMD_VDEVICE_TSM_OP = 0x95,
+	IOMMUFD_CMD_VDEVICE_TSM_GUEST_REQUEST = 0x96,
 };
 
 /**
@@ -1320,4 +1321,31 @@ struct iommu_hw_queue_alloc {
 	__aligned_u64 length;
 };
 #define IOMMU_HW_QUEUE_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_HW_QUEUE_ALLOC)
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

## [11] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

With passthrough devices, we need to make sure private memory is
allocated and assigned to the secure guest before we can issue the DMA.
For ARM RMM, we only need to map and the secure SMMU management is
internal to RMM. For shared IPA, vfio/iommufd DMA MAP/UNMAP interface
does the equivalent

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/kvm/mmu.c                    | 45 +++++++++++++++++++++++++
 drivers/iommu/iommufd/iommufd_private.h |  1 +
 drivers/iommu/iommufd/main.c            |  4 +++
 drivers/iommu/iommufd/viommu.c          | 43 +++++++++++++++++++++++
 include/linux/kvm_host.h                |  1 +
 include/uapi/linux/iommufd.h            | 10 ++++++
 6 files changed, 104 insertions(+)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index c866891fd8f9..8788d24095d6 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1530,6 +1530,51 @@ static int realm_map_ipa(struct kvm *kvm, phys_addr_t ipa,
 	return realm_map_protected(realm, ipa, pfn, map_size, memcache);
 }
 
+int kvm_map_private_memory(struct kvm *kvm, phys_addr_t start_gpa,
+			   phys_addr_t end_gpa)
+{
+	struct kvm_mmu_memory_cache cache = { .gfp_zero = __GFP_ZERO };
+	struct kvm_s2_mmu *mmu = &kvm->arch.mmu;
+	struct kvm_memory_slot *memslot;
+	phys_addr_t addr;
+	struct page *page;
+	kvm_pfn_t pfn;
+	int ret = 0, idx;
+	gfn_t gfn;
+
+	idx = srcu_read_lock(&kvm->srcu);
+	for (addr = start_gpa; addr < end_gpa; addr += PAGE_SIZE) {
+
+		ret = kvm_mmu_topup_memory_cache(&cache,
+						 kvm_mmu_cache_min_pages(mmu));
+		if (ret)
+			break;
+
+		gfn = addr >> PAGE_SHIFT;
+
+		memslot = gfn_to_memslot(kvm, gfn);
+		if (!kvm_slot_can_be_private(memslot)) {
+			ret = -EINVAL;
+			break;
+		}
+		/* should we check if kvm_mem_is_private()? */
+		ret = kvm_gmem_get_pfn(kvm, memslot, gfn, &pfn, &page, NULL);
+		if (ret)
+			break;
+
+		/* should we hold kvm_fault_lock()? */
+		ret = realm_map_ipa(kvm, addr, pfn, PAGE_SIZE, KVM_PGTABLE_PROT_W,
+				    &cache);
+		if (ret) {
+			put_page(page);
+			break;
+		}
+	}
+	kvm_mmu_free_memory_cache(&cache);
+	srcu_read_unlock(&kvm->srcu, idx);
+	return ret;
+}
+
 static int private_memslot_fault(struct kvm_vcpu *vcpu,
 				 phys_addr_t fault_ipa,
 				 struct kvm_memory_slot *memslot)
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 0c0d96135432..34f3ae0e0cd1 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -698,6 +698,7 @@ void iommufd_vdevice_abort(struct iommufd_object *obj);
 int iommufd_hw_queue_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_hw_queue_destroy(struct iommufd_object *obj);
 int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd);
+int iommufd_vdevice_tsm_map_ioctl(struct iommufd_ucmd *ucmd);
 int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd);
 
 static inline struct iommufd_vdevice *
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 65e60da9caef..388d11334994 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -411,6 +411,7 @@ union ucmd_buffer {
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
 	struct iommu_vdevice_tsm_op tsm_op;
+	struct iommu_vdevice_tsm_map tsm_map;
 	struct iommu_vdevice_tsm_guest_request gr;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
@@ -475,6 +476,9 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 struct iommu_viommu_alloc, out_viommu_id),
 	IOCTL_OP(IOMMU_VDEVICE_TSM_OP, iommufd_vdevice_tsm_op_ioctl,
 		 struct iommu_vdevice_tsm_op, vdevice_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_MAP, iommufd_vdevice_tsm_map_ioctl,
+		 struct iommu_vdevice_tsm_map, vdevice_id),
+
 	IOCTL_OP(IOMMU_VDEVICE_TSM_GUEST_REQUEST, iommufd_vdevice_tsm_guest_request_ioctl,
 		 struct iommu_vdevice_tsm_guest_request, resp_uptr),
 #ifdef CONFIG_IOMMUFD_TEST
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 9f4d4d69b82b..1ffc996caa3e 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -516,6 +516,44 @@ int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
 	return rc;
 }
 
+int __weak kvm_map_private_memory(struct kvm *kvm, phys_addr_t start_gpa,
+				  phys_addr_t end_gpa)
+{
+	return -EINVAL;
+}
+
+int iommufd_vdevice_tsm_map_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_tsm_map *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	struct kvm *kvm;
+	int rc = -ENODEV;
+
+	if (cmd->flags)
+		return -EOPNOTSUPP;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	kvm = vdev->viommu->kvm_filp->private_data;
+	if (kvm) {
+		rc = kvm_map_private_memory(kvm, cmd->start_gpa, cmd->end_gpa);
+		if (rc)
+			goto out_put_vdev;
+
+	} else {
+		goto out_put_vdev;
+	}
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
+
 int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd)
 {
 	struct iommu_vdevice_tsm_guest_request *cmd = ucmd->cmd;
@@ -555,6 +593,11 @@ int iommufd_vdevice_tsm_op_ioctl(struct iommufd_ucmd *ucmd)
 	return -ENODEV;
 }
 
+int iommufd_vdevice_tsm_map_ioctl(struct iommufd_ucmd *ucmd)
+{
+	return -ENODEV;
+}
+
 int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd)
 {
 	return -ENODEV;
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 3bde4fb5c6aa..bfdfb4f32d28 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2602,4 +2602,5 @@ static inline int kvm_enable_virtualization(void) { return 0; }
 static inline void kvm_disable_virtualization(void) { }
 #endif
 
+int kvm_map_private_memory(struct kvm *kvm, phys_addr_t start_gpa, phys_addr_t end_gpa);
 #endif
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 56542cfcfa38..75056d1f141d 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -59,6 +59,7 @@ enum {
 	IOMMUFD_CMD_HW_QUEUE_ALLOC = 0x94,
 	IOMMUFD_CMD_VDEVICE_TSM_OP = 0x95,
 	IOMMUFD_CMD_VDEVICE_TSM_GUEST_REQUEST = 0x96,
+	IOMMUFD_CMD_VDEVICE_TSM_MAP = 0x97,
 };
 
 /**
@@ -1146,6 +1147,15 @@ struct iommu_vdevice_tsm_op {
 #define IOMMU_VDEICE_TSM_BIND		0x1
 #define IOMMU_VDEICE_TSM_UNBIND		0x2
 
+struct iommu_vdevice_tsm_map {
+	__u32 size;
+	__u32 flags;
+	__u64 start_gpa;
+	__u64 end_gpa;
+	__u32 vdevice_id;
+};
+#define IOMMU_VDEVICE_TSM_MAP	_IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_MAP)
+
 /**
  * struct iommufd_vevent_header - Virtual Event Header for a vEVENTQ Status
  * @flags: Combination of enum iommu_veventq_flag

---

## [12] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform device*

Register a platform device if the CCA DA feature is supported.
A driver for this platform device will further drive the CCA DA workflow.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h |  3 +++
 arch/arm64/kvm/rme.c             | 16 ++++++++++++++++
 2 files changed, 19 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 504009a42035..42708d500048 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -12,6 +12,8 @@
 
 #include <linux/arm-smccc.h>
 
+#define RMI_DEV_NAME "arm-rmi-dev"
+
 #define SMC_RMI_CALL(func)				\
 	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
 			   ARM_SMCCC_SMC_64,		\
@@ -87,6 +89,7 @@ enum rmi_ripas {
 #define RMI_FEATURE_REGISTER_0_GICV3_NUM_LRS	GENMASK(37, 34)
 #define RMI_FEATURE_REGISTER_0_MAX_RECS_ORDER	GENMASK(41, 38)
 #define RMI_FEATURE_REGISTER_0_Reserved		GENMASK(63, 42)
+#define RMI_FEATURE_REGISTER_0_DA		BIT(42)
 
 #define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
 #define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index ec8093ec2da3..d1c147aba2ed 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -4,6 +4,7 @@
  */
 
 #include <linux/kvm_host.h>
+#include <linux/platform_device.h>
 
 #include <asm/kvm_emulate.h>
 #include <asm/kvm_mmu.h>
@@ -1724,6 +1725,18 @@ int kvm_init_realm_vm(struct kvm *kvm)
 	return 0;
 }
 
+static struct platform_device cca_host_dev = {
+	.name = RMI_DEV_NAME,
+	.id = PLATFORM_DEVID_NONE
+};
+
+static void rmm_tsm_init(void)
+{
+	if (!platform_device_register(&cca_host_dev))
+		pr_info("CCA host DA platform device initialized.\n");
+
+}
+
 void kvm_init_rme(void)
 {
 	if (PAGE_SIZE != SZ_4K)
@@ -1737,6 +1750,9 @@ void kvm_init_rme(void)
 	if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))
 		return;
 
+	if (rme_has_feature(RMI_FEATURE_REGISTER_0_DA))
+		rmm_tsm_init();
+
 	if (rme_vmid_init())
 		return;

---

## [13] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 12/38] coco: host: arm64: CCA host platform device driver*

This driver registers the pci_tsm_ops with tsm subsystem.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/Kconfig                |   2 +
 drivers/virt/coco/Makefile               |   1 +
 drivers/virt/coco/arm-cca-host/Kconfig   |  12 ++
 drivers/virt/coco/arm-cca-host/Makefile  |   5 +
 drivers/virt/coco/arm-cca-host/arm-cca.c | 209 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  |  29 ++++
 6 files changed, 258 insertions(+)
 create mode 100644 drivers/virt/coco/arm-cca-host/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-host/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-host/arm-cca.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmm-da.h

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 57248b088545..43e9508301bf 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -15,5 +15,7 @@ source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
 
+source "drivers/virt/coco/arm-cca-host/Kconfig"
+
 config TSM
 	tristate
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 04e124b2d7cf..d0a859dd9eaf 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -11,3 +11,4 @@ obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-y				+= guest/
+obj-$(CONFIG_ARM_CCA_HOST)	+= arm-cca-host/
diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
new file mode 100644
index 000000000000..0f19fbf47613
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/Kconfig
@@ -0,0 +1,12 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# TSM (TEE Security Manager) host drivers
+#
+config ARM_CCA_HOST
+	tristate "Arm CCA Host driver"
+	depends on ARM64
+	depends on PCI_TSM
+	select TSM
+
+	help
+	  The driver provides TSM backend for ARM CCA
diff --git a/drivers/virt/coco/arm-cca-host/Makefile b/drivers/virt/coco/arm-cca-host/Makefile
new file mode 100644
index 000000000000..ad353b07e95a
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/Makefile
@@ -0,0 +1,5 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+obj-$(CONFIG_ARM_CCA_HOST) += arm-cca-host.o
+
+arm-cca-host-$(CONFIG_TSM) +=  arm-cca.o
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
new file mode 100644
index 000000000000..c8b0e6db1f47
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -0,0 +1,209 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <linux/platform_device.h>
+#include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include <linux/vmalloc.h>
+
+#include "rmm-da.h"
+
+/* Number of streams that we can support at the hostbridge level */
+#define CCA_HB_PLATFORM_STREAMS 4
+
+/* Total number of stream id supported at root port level */
+#define MAX_STREAM_ID	256
+
+DEFINE_FREE(vfree, void *, if (!IS_ERR_OR_NULL(_T)) vfree(_T))
+static struct pci_tsm *cca_tsm_pci_probe(struct pci_dev *pdev)
+{
+	int rc;
+	struct pci_host_bridge *hb;
+	struct cca_host_dsc_pf0 *dsc_pf0 __free(vfree) = NULL;
+
+	if (pdev->is_virtfn)
+		return NULL;
+
+	if (!is_pci_tsm_pf0(pdev)) {
+		struct pci_tsm *tsm = kzalloc(sizeof(*tsm), GFP_KERNEL);
+
+		if (!tsm)
+			goto err_out;
+
+		pci_tsm_initialize(pdev, tsm);
+		return tsm;
+	}
+
+	if (!pdev->ide_cap)
+		goto err_out;
+
+	dsc_pf0 = vcalloc(sizeof(*dsc_pf0), GFP_KERNEL);
+	if (!dsc_pf0)
+		goto err_out;
+
+	rc = pci_tsm_pf0_initialize(pdev, &dsc_pf0->pci);
+	if (rc)
+		return NULL;
+	/*
+	 * FIXME!!
+	 * update the hostbridge details. This should go into
+	 * some host bridge probe/init routine.
+	 * than the selective index supported by the endpoint
+	 */
+	hb = pci_find_host_bridge(pdev->bus);
+	pci_ide_init_nr_streams(hb, CCA_HB_PLATFORM_STREAMS);
+
+	pci_info(pdev, "tsm enabled\n");
+	return &no_free_ptr(dsc_pf0)->pci.tsm;
+
+err_out:
+	return NULL;
+}
+
+static void cca_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+
+	if (WARN_ON(pdev->is_virtfn))
+		return;
+
+	if (!is_pci_tsm_pf0(pdev)) {
+
+		pci_dbg(tsm->pdev, "tsm disabled\n");
+		kfree(pdev->tsm);
+		return;
+	}
+
+	dsc_pf0 = to_cca_dsc_pf0(pdev);
+	pci_dbg(tsm->pdev, "tsm disabled\n");
+	vfree(dsc_pf0);
+}
+
+/* per root port unique with multiple restrictions. For now global */
+static DECLARE_BITMAP(cca_stream_ids, MAX_STREAM_ID);
+
+static int cca_tsm_connect(struct pci_dev *pdev)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	struct pci_ide *ide;
+	int rc, stream_id;
+
+	/* Only function 0 supports connect in host */
+	if (WARN_ON(!is_pci_tsm_pf0(pdev)))
+		return -EIO;
+
+	dsc_pf0 = to_cca_dsc_pf0(pdev);
+	/* Allocate stream id */
+	stream_id = find_first_zero_bit(cca_stream_ids, MAX_STREAM_ID);
+	if (stream_id == MAX_STREAM_ID)
+		return -EBUSY;
+	set_bit(stream_id, cca_stream_ids);
+
+	ide = pci_ide_stream_alloc(pdev);
+	if (!ide) {
+		rc = -ENOMEM;
+		goto err_stream_alloc;
+	}
+
+	dsc_pf0->sel_stream = ide;
+	ide->stream_id = stream_id;
+	rc = pci_ide_stream_register(ide);
+	if (rc)
+		goto err_stream;
+
+	pci_ide_stream_setup(pdev, ide);
+	pci_ide_stream_setup(rp, ide);
+
+	rc = tsm_ide_stream_register(pdev, ide);
+	if (rc)
+		goto err_tsm;
+
+	/*
+	 * Once ide is setup enable the stream at endpoint
+	 * Root port will be done by RMM
+	 */
+	pci_ide_stream_enable(pdev, ide);
+	return 0;
+
+err_tsm:
+	pci_ide_stream_teardown(rp, ide);
+	pci_ide_stream_teardown(pdev, ide);
+	pci_ide_stream_unregister(ide);
+err_stream:
+	pci_ide_stream_free(ide);
+err_stream_alloc:
+	clear_bit(stream_id, cca_stream_ids);
+
+	return rc;
+}
+
+static void cca_tsm_disconnect(struct pci_dev *pdev)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	struct pci_ide *ide;
+
+	if (WARN_ON(!is_pci_tsm_pf0(pdev)))
+		return;
+
+	dsc_pf0 = to_cca_dsc_pf0(pdev);
+	ide = dsc_pf0->sel_stream;
+	dsc_pf0->sel_stream = NULL;
+	pci_ide_stream_disable(pdev, ide);
+	tsm_ide_stream_unregister(ide);
+	pci_ide_stream_teardown(rp, ide);
+	pci_ide_stream_teardown(pdev, ide);
+	pci_ide_stream_unregister(ide);
+	clear_bit(ide->stream_id, cca_stream_ids);
+	pci_ide_stream_free(ide);
+}
+
+static const struct pci_tsm_ops cca_pci_ops = {
+	.probe = cca_tsm_pci_probe,
+	.remove = cca_tsm_pci_remove,
+	.connect = cca_tsm_connect,
+	.disconnect = cca_tsm_disconnect,
+};
+
+static void cca_tsm_remove(void *tsm_core)
+{
+	tsm_unregister(tsm_core);
+}
+
+static int cca_tsm_probe(struct platform_device *pdev)
+{
+	struct tsm_core_dev *tsm_core;
+
+	tsm_core = tsm_register(&pdev->dev, NULL, &cca_pci_ops);
+	if (IS_ERR(tsm_core))
+		return PTR_ERR(tsm_core);
+
+	return devm_add_action_or_reset(&pdev->dev, cca_tsm_remove, tsm_core);
+}
+
+static const struct platform_device_id arm_cca_host_id_table[] = {
+	{ RMI_DEV_NAME, 0},
+	{ }
+};
+MODULE_DEVICE_TABLE(platform, arm_cca_host_id_table);
+
+
+static struct platform_driver cca_tsm_platform_driver = {
+	.probe = cca_tsm_probe,
+	.id_table = arm_cca_host_id_table,
+	.driver = {
+		.name = "cca_tsm",
+	},
+};
+
+MODULE_IMPORT_NS("PCI_IDE");
+module_platform_driver(cca_tsm_platform_driver);
+MODULE_DESCRIPTION("ARM CCA Host TSM driver");
+MODULE_LICENSE("GPL");
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
new file mode 100644
index 000000000000..840cb584acdd
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -0,0 +1,29 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2024 ARM Ltd.
+ */
+
+#ifndef RMM_DA_H_
+#define RMM_DA_H_
+
+#include <linux/pci.h>
+#include <linux/pci-ide.h>
+#include <linux/pci-tsm.h>
+#include <asm/rmi_smc.h>
+
+struct cca_host_dsc_pf0 {
+	struct pci_tsm_pf0 pci;
+	struct pci_ide *sel_stream;
+};
+
+static inline struct cca_host_dsc_pf0 *to_cca_dsc_pf0(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm || pdev->is_virtfn || !is_pci_tsm_pf0(pdev))
+		return NULL;
+
+	return container_of(tsm, struct cca_host_dsc_pf0, pci.tsm);
+}
+
+#endif

---

## [14] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 13/38] coco: host: arm64: Create a PDEV with rmm*

Create the realm physical device with RMM.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  31 +++++
 arch/arm64/include/asm/rmi_smc.h         |  72 ++++++++++-
 drivers/virt/coco/arm-cca-host/Makefile  |   2 +-
 drivers/virt/coco/arm-cca-host/arm-cca.c |  10 +-
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 150 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  |   5 +
 6 files changed, 267 insertions(+), 3 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-host/rmm-da.c

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index ef53147c1984..f0817bd3bab4 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -505,4 +505,35 @@ static inline int rmi_rtt_unmap_unprotected(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_aux_count(unsigned long flags, u64 *aux_count)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_AUX_COUNT, flags, &res);
+
+	*aux_count = res.a1;
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_create(unsigned long pdev_phys,
+					    unsigned long pdev_params_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_CREATE,
+			     pdev_phys, pdev_params_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_get_state(unsigned long pdev_phys, unsigned long *state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_GET_STATE, pdev_phys, &res);
+
+	*state = res.a1;
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 42708d500048..a84ed61e5001 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -26,7 +26,7 @@
 #define SMC_RMI_DATA_CREATE		SMC_RMI_CALL(0x0153)
 #define SMC_RMI_DATA_CREATE_UNKNOWN	SMC_RMI_CALL(0x0154)
 #define SMC_RMI_DATA_DESTROY		SMC_RMI_CALL(0x0155)
-
+#define SMC_RMI_PDEV_AUX_COUNT		SMC_RMI_CALL(0x0156)
 #define SMC_RMI_REALM_ACTIVATE		SMC_RMI_CALL(0x0157)
 #define SMC_RMI_REALM_CREATE		SMC_RMI_CALL(0x0158)
 #define SMC_RMI_REALM_DESTROY		SMC_RMI_CALL(0x0159)
@@ -47,6 +47,9 @@
 #define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
 
+#define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
+#define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
+
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
 
@@ -268,4 +271,71 @@ struct rec_run {
 	struct rec_exit exit;
 };
 
+enum rmi_pdev_state {
+	RMI_PDEV_NEW,
+	RMI_PDEV_NEEDS_KEY,
+	RMI_PDEV_HAS_KEY,
+	RMI_PDEV_READY,
+	RMI_PDEV_COMMUNICATING,
+	RMI_PDEV_STOPPING,
+	RMI_PDEV_STOPPED,
+	RMI_PDEV_ERROR,
+};
+
+#define MAX_PDEV_AUX_GRANULES	32
+#define MAX_IOCOH_ADDR_RANGE	16
+#define MAX_FCOH_ADDR_RANGE	4
+
+#define RMI_PDEV_SPDM_TRUE	BIT(0)
+#define RMI_PDEV_IDE_TRUE	BIT(1)
+#define RMI_PDEV_FOCOH		BIT(2)
+#define RMI_PDEV_P2P_STREAM	BIT(3)
+
+#define RMI_HASH_SHA_256	0
+#define RMI_HASH_SHA_512	1
+
+struct rmi_pdev_addr_range {
+	unsigned long base;
+	unsigned long top;
+};
+
+struct rmi_pdev_params {
+	union {
+		struct {
+			u64 flags;
+			u64 pdev_id;
+			u64 segment_id;
+			u64 ecam_addr;
+			u64 root_id;
+			u64 cert_id;
+			u64 rid_base;
+			u64 rid_top;
+			u64 hash_algo;
+			u64 num_aux;
+			u64 ide_sid;
+			u64 ncoh_num_addr_range;
+			u64 coh_num_addr_range;
+		};
+		u8 padding1[0x100];
+	};
+
+	union { /* 0x100 */
+		u64 aux_granule[MAX_PDEV_AUX_GRANULES];
+		u8 padding2[0x100];
+	};
+
+	union { /* 0x200 */
+		struct {
+			struct rmi_pdev_addr_range ncoh_addr_range[MAX_IOCOH_ADDR_RANGE];
+		};
+		u8 padding3[0x100];
+	};
+	union { /* 0x300 */
+		struct {
+			struct rmi_pdev_addr_range coh_addr_range[MAX_FCOH_ADDR_RANGE];
+		};
+		u8 padding4[0x100];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/Makefile b/drivers/virt/coco/arm-cca-host/Makefile
index ad353b07e95a..8409220a6510 100644
--- a/drivers/virt/coco/arm-cca-host/Makefile
+++ b/drivers/virt/coco/arm-cca-host/Makefile
@@ -2,4 +2,4 @@
 #
 obj-$(CONFIG_ARM_CCA_HOST) += arm-cca-host.o
 
-arm-cca-host-$(CONFIG_TSM) +=  arm-cca.o
+arm-cca-host-$(CONFIG_TSM) +=  arm-cca.o rmm-da.o
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index c8b0e6db1f47..84d97dd41191 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -124,7 +124,15 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 	rc = tsm_ide_stream_register(pdev, ide);
 	if (rc)
 		goto err_tsm;
-
+	/*
+	 * Take a module reference so that we won't call unregister
+	 * without rme_unasign_device
+	 */
+	if (!try_module_get(THIS_MODULE)) {
+		rc = -ENXIO;
+		goto err_tsm;
+	}
+	rme_asign_device(pdev);
 	/*
 	 * Once ide is setup enable the stream at endpoint
 	 * Root port will be done by RMM
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
new file mode 100644
index 000000000000..426e530ac182
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -0,0 +1,150 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <linux/pci.h>
+#include <linux/pci-ecam.h>
+#include <asm/rmi_cmds.h>
+
+#include "rmm-da.h"
+
+static int pci_res_to_pdev_addr(struct rmi_pdev_addr_range *pdev_addr,
+				unsigned int naddr, struct resource *res,
+				unsigned int nres)
+{
+	int i, j;
+
+	for (i = 0, j = 0; i < naddr && j < nres; j++) {
+		if (res[j].flags & IORESOURCE_MEM) {
+			pdev_addr[i].base = res[j].start;
+			pdev_addr[i].top  = res[j].end;
+			i++;
+		}
+	}
+	return i;
+}
+
+static void free_aux_pages(int cnt, void *aux[])
+{
+	int ret;
+
+	while (cnt--) {
+		ret = rmi_granule_undelegate(virt_to_phys(aux[cnt]));
+		if (!ret)
+			free_page((unsigned long)aux[cnt]);
+	}
+}
+
+static int init_pdev_params(struct pci_dev *pdev, struct rmi_pdev_params *params)
+{
+	void *aux;
+	int rid, ret, i;
+	phys_addr_t aux_phys;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_config_window *cfg = pdev->bus->sysdata;
+
+	dsc_pf0 = to_cca_dsc_pf0(pdev);
+	/* assign the ep device with RMM */
+	rid = pci_dev_id(pdev);
+	params->pdev_id = rid;
+	/* slot number for certificate chain */
+	params->cert_id = 0;
+	/* io coherent spdm/ide and non p2p */
+	params->flags = RMI_PDEV_SPDM_TRUE | RMI_PDEV_IDE_TRUE;
+	params->ide_sid = dsc_pf0->sel_stream->stream_id;
+	params->hash_algo = RMI_HASH_SHA_256;
+	/* use the rid and MMIO resources of the epdev */
+	params->rid_top = params->rid_base = rid;
+	params->ecam_addr = cfg->res.start;
+	params->root_id = pci_dev_id(rp);
+
+	params->ncoh_num_addr_range = pci_res_to_pdev_addr(params->ncoh_addr_range,
+							    ARRAY_SIZE(params->ncoh_addr_range),
+							    pdev->resource,
+							    DEVICE_COUNT_RESOURCE);
+
+	rmi_pdev_aux_count(params->flags, &params->num_aux);
+	pr_debug("%s using %ld pdev aux granules\n", __func__, (unsigned long)params->num_aux);
+	dsc_pf0->num_aux = params->num_aux;
+	for (i = 0; i < params->num_aux; i++) {
+		aux = (void *)__get_free_page(GFP_KERNEL);
+		if (!aux) {
+			ret = -ENOMEM;
+			goto err_free_aux;
+		}
+
+		aux_phys = virt_to_phys(aux);
+		if (rmi_granule_delegate(aux_phys)) {
+			ret = -ENXIO;
+			free_page((unsigned long)aux);
+			goto err_free_aux;
+		}
+		params->aux_granule[i] = aux_phys;
+		dsc_pf0->aux[i] = aux;
+	}
+	return 0;
+
+err_free_aux:
+	free_aux_pages(i, dsc_pf0->aux[i]);
+	return -ENOMEM;
+}
+
+
+int rme_asign_device(struct pci_dev *pci_dev)
+{
+	int ret;
+	void *rmm_pdev;
+	unsigned long state;
+	phys_addr_t rmm_pdev_phys;
+	struct rmi_pdev_params *params;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+
+	dsc_pf0 = to_cca_dsc_pf0(pci_dev);
+	rmm_pdev = (void *)get_zeroed_page(GFP_KERNEL);
+	if (!rmm_pdev) {
+		ret = -ENOMEM;
+		goto err_out;
+	}
+
+	rmm_pdev_phys = virt_to_phys(rmm_pdev);
+	if (rmi_granule_delegate(rmm_pdev_phys)) {
+		ret = -ENXIO;
+		goto err_free_pdev;
+	}
+
+	params = (struct rmi_pdev_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params) {
+		ret = -ENOMEM;
+		goto err_granule_undelegate;
+	}
+
+	ret = init_pdev_params(pci_dev, params);
+	if (ret)
+		goto err_free_params;
+
+	ret = rmi_pdev_create(rmm_pdev_phys, virt_to_phys(params));
+	pr_info("rmi_pdev_create(0x%llx, 0x%llx): %d\n", rmm_pdev_phys, virt_to_phys(params), ret);
+	if (ret)
+		goto err_free_aux;
+
+	rmi_pdev_get_state(rmm_pdev_phys, &state);
+	if (state != RMI_PDEV_NEW)
+		goto err_free_aux;
+
+	dsc_pf0->rmm_pdev = rmm_pdev;
+	free_page((unsigned long)params);
+	return 0;
+
+err_free_aux:
+	free_aux_pages(dsc_pf0->num_aux, dsc_pf0->aux);
+err_free_params:
+	free_page((unsigned long)params);
+err_granule_undelegate:
+	rmi_granule_undelegate(rmm_pdev_phys);
+err_free_pdev:
+	free_page((unsigned long)rmm_pdev);
+err_out:
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index 840cb584acdd..179ba68f2430 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -14,6 +14,10 @@
 struct cca_host_dsc_pf0 {
 	struct pci_tsm_pf0 pci;
 	struct pci_ide *sel_stream;
+
+	void *rmm_pdev;
+	int num_aux;
+	void *aux[MAX_PDEV_AUX_GRANULES];
 };
 
 static inline struct cca_host_dsc_pf0 *to_cca_dsc_pf0(struct pci_dev *pdev)
@@ -26,4 +30,5 @@ static inline struct cca_host_dsc_pf0 *to_cca_dsc_pf0(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_host_dsc_pf0, pci.tsm);
 }
 
+int rme_asign_device(struct pci_dev *pdev);
 #endif

---

## [15] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 14/38] coco: host: arm64: Device communication support*

Add helpers for device communication from RMM

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  11 ++
 arch/arm64/include/asm/rmi_smc.h         |  49 ++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  45 ++++++
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 198 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  |  41 +++++
 5 files changed, 344 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index f0817bd3bab4..eb0034a675bb 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -536,4 +536,15 @@ static inline unsigned long rmi_pdev_get_state(unsigned long pdev_phys, unsigned
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_communicate(unsigned long pdev_phys,
+						 unsigned long pdev_comm_data_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_COMMUNICATE,
+			     pdev_phys, pdev_comm_data_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index a84ed61e5001..8bece465b670 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -47,6 +47,7 @@
 #define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
 
+#define SMC_RMI_PDEV_COMMUNICATE        SMC_RMI_CALL(0x0175)
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
 
@@ -338,4 +339,52 @@ struct rmi_pdev_params {
 	};
 };
 
+#define RMI_DEV_COMM_EXIT_CACHE_REQ	BIT(0)
+#define RMI_DEV_COMM_EXIT_CACHE_RSP	BIT(1)
+#define RMI_DEV_COMM_EXIT_SEND		BIT(2)
+#define RMI_DEV_COMM_EXIT_WAIT		BIT(3)
+#define RMI_DEV_COMM_EXIT_MULTI		BIT(4)
+
+#define RMI_DEV_COMM_NONE	0
+#define RMI_DEV_COMM_RESPONSE	1
+#define RMI_DEV_COMM_ERROR	2
+
+#define RMI_PROTOCOL_SPDM		0
+#define RMI_PROTOCOL_SECURE_SPDM	1
+
+#define RMI_DEV_VCA			0
+#define RMI_DEV_CERTIFICATE		1
+#define RMI_DEV_MEASUREMENTS		2
+#define RMI_DEV_INTERFACE_REPORT	3
+
+struct rmi_dev_comm_enter {
+	u64 status;
+	u64 req_addr;
+	u64 resp_addr;
+	u64 resp_len;
+};
+
+struct rmi_dev_comm_exit {
+	u64 flags;
+	u64 cache_req_offset;
+	u64 cache_req_len;
+	u64 cache_rsp_offset;
+	u64 cache_rsp_len;
+	u64 cache_obj_id;
+	u64 protocol;
+	u64 req_len;
+	u64 timeout;
+};
+
+struct rmi_dev_comm_data {
+	union { /* 0x0 */
+		struct rmi_dev_comm_enter enter;
+		u8 padding_1[0x800];
+	};
+	union { /* 0x800 */
+		struct rmi_dev_comm_exit exit;
+		u8 padding_2[0x800];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 84d97dd41191..294a6ef60d5f 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -85,6 +85,45 @@ static void cca_tsm_pci_remove(struct pci_tsm *tsm)
 	vfree(dsc_pf0);
 }
 
+static int init_dev_communication_buffers(struct cca_host_comm_data *comm_data)
+{
+	int ret = -ENOMEM;
+
+	comm_data->io_params = (struct rmi_dev_comm_data *)get_zeroed_page(GFP_KERNEL);
+	if (!comm_data->io_params)
+		goto err_out;
+
+	comm_data->resp_buff = (void *)__get_free_page(GFP_KERNEL);
+	if (!comm_data->resp_buff)
+		goto err_res_buff;
+
+	comm_data->req_buff = (void *)__get_free_page(GFP_KERNEL);
+	if (!comm_data->req_buff)
+		goto err_req_buff;
+
+
+	comm_data->io_params->enter.status = RMI_DEV_COMM_NONE;
+	comm_data->io_params->enter.resp_addr = virt_to_phys(comm_data->resp_buff);
+	comm_data->io_params->enter.req_addr  = virt_to_phys((void *)comm_data->req_buff);
+	comm_data->io_params->enter.resp_len = 0;
+
+	return 0;
+
+err_req_buff:
+	free_page((unsigned long)comm_data->resp_buff);
+err_res_buff:
+	free_page((unsigned long)comm_data->io_params);
+err_out:
+	return ret;
+}
+
+static inline void free_dev_communication_buffers(struct cca_host_comm_data *comm_data)
+{
+	free_page((unsigned long)comm_data->req_buff);
+	free_page((unsigned long)comm_data->resp_buff);
+	free_page((unsigned long)comm_data->io_params);
+}
+
 /* per root port unique with multiple restrictions. For now global */
 static DECLARE_BITMAP(cca_stream_ids, MAX_STREAM_ID);
 
@@ -124,6 +163,7 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 	rc = tsm_ide_stream_register(pdev, ide);
 	if (rc)
 		goto err_tsm;
+	init_dev_communication_buffers(&dsc_pf0->comm_data);
 	/*
 	 * Take a module reference so that we won't call unregister
 	 * without rme_unasign_device
@@ -133,6 +173,11 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 		goto err_tsm;
 	}
 	rme_asign_device(pdev);
+	/*
+	 * Schedule a work to fetch device certificate and setup IDE
+	 */
+	schedule_rme_ide_setup(pdev);
+
 	/*
 	 * Once ide is setup enable the stream at endpoint
 	 * Root port will be done by RMM
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index 426e530ac182..d123940ce82e 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -148,3 +148,201 @@ int rme_asign_device(struct pci_dev *pci_dev)
 err_out:
 	return ret;
 }
+
+static int doe_send_req_resp(struct pci_tsm *tsm)
+{
+	u8 protocol;
+	int ret, data_obj_type;
+	struct cca_host_comm_data *comm_data;
+	struct rmi_dev_comm_exit *io_exit;
+
+	comm_data = to_cca_comm_data(tsm->pdev);
+
+	io_exit = &comm_data->io_params->exit;
+	protocol = io_exit->protocol;
+
+	pr_debug("doe_req size:%lld doe_io_type=%d\n", io_exit->req_len, (int)protocol);
+
+	if (protocol == RMI_PROTOCOL_SPDM)
+		data_obj_type = PCI_DOE_PROTO_CMA;
+	else if (protocol == RMI_PROTOCOL_SECURE_SPDM)
+		data_obj_type = PCI_DOE_PROTO_SSESSION;
+	else
+		return -EINVAL;
+
+	ret = pci_tsm_doe_transfer(tsm->dsm_dev, data_obj_type,
+				   comm_data->req_buff, io_exit->req_len,
+				   comm_data->resp_buff, PAGE_SIZE);
+	pr_debug("doe returned:%d\n", ret);
+	return ret;
+}
+
+/* Parallel update for cca_dsc contents FIXME!! */
+static int __do_dev_communicate(int type, struct pci_tsm *tsm)
+{
+	int ret;
+	bool is_multi;
+	u8 *cache_buf;
+	int *cache_offset;
+	int nbytes, cache_remaining;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	struct rmi_dev_comm_exit *io_exit;
+	struct rmi_dev_comm_enter *io_enter;
+	struct cca_host_comm_data *comm_data;
+
+
+	comm_data = to_cca_comm_data(tsm->pdev);
+	io_enter = &comm_data->io_params->enter;
+	io_exit = &comm_data->io_params->exit;
+
+	dsc_pf0 = to_cca_dsc_pf0(tsm->dsm_dev);
+redo_communicate:
+	is_multi = false;
+
+	if (type == PDEV_COMMUNICATE)
+		ret = rmi_pdev_communicate(virt_to_phys(dsc_pf0->rmm_pdev),
+					   virt_to_phys(comm_data->io_params));
+	else
+		ret = RMI_ERROR_INPUT;
+	if (ret != RMI_SUCCESS) {
+		pr_err("pdev communicate error\n");
+		return ret;
+	}
+
+	/* caching request from RMM */
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_RSP) {
+		switch (io_exit->cache_obj_id) {
+		case RMI_DEV_VCA:
+			cache_buf = dsc_pf0->vca.buf;
+			cache_offset = &dsc_pf0->vca.size;
+			cache_remaining = sizeof(dsc_pf0->vca.buf) - *cache_offset;
+			break;
+		case RMI_DEV_CERTIFICATE:
+			cache_buf = dsc_pf0->cert_chain.cache.buf;
+			cache_offset = &dsc_pf0->cert_chain.cache.size;
+			cache_remaining = sizeof(dsc_pf0->cert_chain.cache.buf) - *cache_offset;
+			break;
+		default:
+			/* FIXME!! depending on the DevComms status,
+			 * it might require to ABORT the communcation.
+			 */
+			return -EINVAL;
+		}
+
+		if (io_exit->cache_rsp_len > cache_remaining)
+			return -EINVAL;
+
+		memcpy(cache_buf + *cache_offset,
+		       (comm_data->resp_buff + io_exit->cache_rsp_offset), io_exit->cache_rsp_len);
+		*cache_offset += io_exit->cache_rsp_len;
+	}
+
+	/*
+	 * wait for last packet request from RMM.
+	 * We should not find this because our device communication in synchronous
+	 */
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_WAIT)
+		return -ENXIO;
+
+	is_multi = !!(io_exit->flags & RMI_DEV_COMM_EXIT_MULTI);
+
+	/* next packet to send */
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_SEND) {
+		nbytes = doe_send_req_resp(tsm);
+		if (nbytes < 0) {
+			/* report error back to RMM */
+			io_enter->status = RMI_DEV_COMM_ERROR;
+		} else {
+			/* send response back to RMM */
+			io_enter->resp_len = nbytes;
+			io_enter->status = RMI_DEV_COMM_RESPONSE;
+		}
+	} else {
+		/* no data transmitted => no data received */
+		io_enter->resp_len = 0;
+	}
+
+	/* The call need to do multiple request/respnse */
+	if (is_multi)
+		goto redo_communicate;
+
+	return 0;
+}
+
+static int do_dev_communicate(int type, struct pci_tsm *tsm, int target_state)
+{
+	int ret;
+	unsigned long state;
+	unsigned long error_state;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	struct rmi_dev_comm_enter *io_enter;
+
+	dsc_pf0 = to_cca_dsc_pf0(tsm->dsm_dev);
+	io_enter = &dsc_pf0->comm_data.io_params->enter;
+	io_enter->resp_len = 0;
+	io_enter->status = RMI_DEV_COMM_NONE;
+
+	state = -1;
+	do {
+		ret = __do_dev_communicate(type, tsm);
+		if (ret != 0) {
+			pr_err("dev communication error\n");
+			break;
+		}
+
+		if (type == PDEV_COMMUNICATE) {
+			ret = rmi_pdev_get_state(virt_to_phys(dsc_pf0->rmm_pdev),
+						 &state);
+			error_state = RMI_PDEV_ERROR;
+		}
+		if (ret != 0) {
+			pr_err("Get dev state error\n");
+			break;
+		}
+	} while (state != target_state && state != error_state);
+
+	pr_info("dev_io_complete: status: %d state:%ld\n", ret, state);
+
+	return state;
+}
+
+static int do_pdev_communicate(struct pci_tsm *tsm, int target_state)
+{
+	return do_dev_communicate(PDEV_COMMUNICATE, tsm, target_state);
+}
+
+struct dev_comm_work {
+	struct pci_tsm *tsm;
+	struct work_struct work;
+	struct completion complete;
+};
+
+static void pdev_ide_setup_work(struct work_struct *work)
+{
+	unsigned long state;
+	struct pci_tsm *tsm;
+	struct dev_comm_work *setup_work;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+
+	state = do_pdev_communicate(tsm, RMI_PDEV_NEEDS_KEY);
+	WARN_ON(state != RMI_PDEV_NEEDS_KEY);
+
+	complete(&setup_work->complete);
+}
+
+int schedule_rme_ide_setup(struct pci_dev *pdev)
+{
+	struct dev_comm_work setup_work = {
+		.tsm = pdev->tsm,
+	};
+
+	INIT_WORK_ONSTACK(&setup_work.work, pdev_ide_setup_work);
+	init_completion(&setup_work.complete);
+	schedule_work(&setup_work.work);
+	wait_for_completion(&setup_work.complete);
+	destroy_work_on_stack(&setup_work.work);
+
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index 179ba68f2430..b9ddc4d9112b 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -11,15 +11,40 @@
 #include <linux/pci-tsm.h>
 #include <asm/rmi_smc.h>
 
+#define MAX_CACHE_OBJ_SIZE	4096
+struct cache_object {
+	u8 buf[MAX_CACHE_OBJ_SIZE];
+	int size;
+};
+
+/* dsc = device security context */
+struct cca_host_comm_data {
+	void *resp_buff;
+	void *req_buff;
+	struct rmi_dev_comm_data *io_params;
+};
+
 struct cca_host_dsc_pf0 {
+	struct cca_host_comm_data comm_data;
 	struct pci_tsm_pf0 pci;
 	struct pci_ide *sel_stream;
 
 	void *rmm_pdev;
 	int num_aux;
 	void *aux[MAX_PDEV_AUX_GRANULES];
+
+	struct {
+		struct cache_object cache;
+
+		void *public_key;
+		size_t public_key_size;
+
+		bool valid;
+	} cert_chain;
+	struct cache_object vca;
 };
 
+#define PDEV_COMMUNICATE	0x1
 static inline struct cca_host_dsc_pf0 *to_cca_dsc_pf0(struct pci_dev *pdev)
 {
 	struct pci_tsm *tsm = pdev->tsm;
@@ -30,5 +55,21 @@ static inline struct cca_host_dsc_pf0 *to_cca_dsc_pf0(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_host_dsc_pf0, pci.tsm);
 }
 
+static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
+{
+	struct cca_host_dsc_pf0 *dsc_pf0;
+
+	dsc_pf0 = to_cca_dsc_pf0(pdev);
+	if (dsc_pf0)
+		return &dsc_pf0->comm_data;
+
+	dsc_pf0 = to_cca_dsc_pf0(pdev->tsm->dsm_dev);
+	if (dsc_pf0)
+		return &dsc_pf0->comm_data;
+
+	return NULL;
+}
+
 int rme_asign_device(struct pci_dev *pdev);
+int schedule_rme_ide_setup(struct pci_dev *pdev);
 #endif

---

## [16] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 15/38] coco: host: arm64: Stop and destroy the physical device*

Add support for stopping and destroying physical devices.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 18 ++++++++++++++++++
 arch/arm64/include/asm/rmi_smc.h         |  2 ++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  3 +++
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 21 +++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  |  1 +
 5 files changed, 45 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index eb0034a675bb..d4ea9f8363f5 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -547,4 +547,22 @@ static inline unsigned long rmi_pdev_communicate(unsigned long pdev_phys,
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_stop(unsigned long pdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STOP, pdev_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_destroy(unsigned long pdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_DESTROY, pdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 8bece465b670..9f25a876238e 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -49,7 +49,9 @@
 
 #define SMC_RMI_PDEV_COMMUNICATE        SMC_RMI_CALL(0x0175)
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
+#define SMC_RMI_PDEV_DESTROY		SMC_RMI_CALL(0x0177)
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
+#define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
 
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 294a6ef60d5f..c65b81f0706f 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -210,12 +210,15 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	ide = dsc_pf0->sel_stream;
 	dsc_pf0->sel_stream = NULL;
 	pci_ide_stream_disable(pdev, ide);
+	rme_unassign_device(pdev);
+	module_put(THIS_MODULE);
 	tsm_ide_stream_unregister(ide);
 	pci_ide_stream_teardown(rp, ide);
 	pci_ide_stream_teardown(pdev, ide);
 	pci_ide_stream_unregister(ide);
 	clear_bit(ide->stream_id, cca_stream_ids);
 	pci_ide_stream_free(ide);
+	free_dev_communication_buffers(&dsc_pf0->comm_data);
 }
 
 static const struct pci_tsm_ops cca_pci_ops = {
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index d123940ce82e..ec8c5bfcee35 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -346,3 +346,24 @@ int schedule_rme_ide_setup(struct pci_dev *pdev)
 
 	return 0;
 }
+
+void rme_unassign_device(struct pci_dev *pdev)
+{
+	unsigned long ret;
+	unsigned long state;
+	phys_addr_t rmm_pdev_phys;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+
+	dsc_pf0 = to_cca_dsc_pf0(pdev);
+	rmm_pdev_phys = virt_to_phys(dsc_pf0->rmm_pdev);
+	ret = rmi_pdev_stop(rmm_pdev_phys);
+	if (WARN_ON(ret != RMI_SUCCESS))
+		return;
+
+	state = do_pdev_communicate(pdev->tsm, RMI_PDEV_STOPPED);
+	/* ignore the error state and destroy the device */
+	WARN_ON(state != RMI_PDEV_STOPPED);
+	ret = rmi_pdev_destroy(rmm_pdev_phys);
+	if (WARN_ON(ret != RMI_SUCCESS))
+		return;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index b9ddc4d9112b..c401be55d770 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -71,5 +71,6 @@ static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
 }
 
 int rme_asign_device(struct pci_dev *pdev);
+void rme_unassign_device(struct pci_dev *pdev);
 int schedule_rme_ide_setup(struct pci_dev *pdev);
 #endif

---

## [17] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 16/38] X.509: Make certificate parser public*

From: Lukas Wunner <lukas@wunner.de>

The upcoming support for PCI device authentication with CMA-SPDM
(PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name
in X.509 certificates.

High-level functions for X.509 parsing such as key_create_or_update()
throw away the internal, low-level struct x509_certificate after
extracting the struct public_key and public_key_signature from it.
The Subject Alternative Name is thus inaccessible when using those
functions.

Afford CMA-SPDM access to the Subject Alternative Name by making struct
x509_certificate public, together with the functions for parsing an
X.509 certificate into such a struct and freeing such a struct.

The private header file x509_parser.h previously included <linux/time.h>
for the definition of time64_t.  That definition was since moved to
<linux/time64.h> by commit 361a3bf00582 ("time64: Add time64.h header
and define struct timespec64"), so adjust the #include directive as part
of the move to the new public header file <keys/x509-parser.h>.

No functional change intended.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/asymmetric_keys/x509_parser.h | 40 +--------------------
 include/keys/x509-parser.h           | 53 ++++++++++++++++++++++++++++
 2 files changed, 54 insertions(+), 39 deletions(-)
 create mode 100644 include/keys/x509-parser.h

diff --git a/crypto/asymmetric_keys/x509_parser.h b/crypto/asymmetric_keys/x509_parser.h
index 0688c222806b..39f1521b773d 100644
--- a/crypto/asymmetric_keys/x509_parser.h
+++ b/crypto/asymmetric_keys/x509_parser.h
@@ -5,49 +5,11 @@
  * Written by David Howells (dhowells@redhat.com)
  */
 
-#include <linux/cleanup.h>
-#include <linux/time.h>
-#include <crypto/public_key.h>
-#include <keys/asymmetric-type.h>
-
-struct x509_certificate {
-	struct x509_certificate *next;
-	struct x509_certificate *signer;	/* Certificate that signed this one */
-	struct public_key *pub;			/* Public key details */
-	struct public_key_signature *sig;	/* Signature parameters */
-	char		*issuer;		/* Name of certificate issuer */
-	char		*subject;		/* Name of certificate subject */
-	struct asymmetric_key_id *id;		/* Issuer + Serial number */
-	struct asymmetric_key_id *skid;		/* Subject + subjectKeyId (optional) */
-	time64_t	valid_from;
-	time64_t	valid_to;
-	const void	*tbs;			/* Signed data */
-	unsigned	tbs_size;		/* Size of signed data */
-	unsigned	raw_sig_size;		/* Size of signature */
-	const void	*raw_sig;		/* Signature data */
-	const void	*raw_serial;		/* Raw serial number in ASN.1 */
-	unsigned	raw_serial_size;
-	unsigned	raw_issuer_size;
-	const void	*raw_issuer;		/* Raw issuer name in ASN.1 */
-	const void	*raw_subject;		/* Raw subject name in ASN.1 */
-	unsigned	raw_subject_size;
-	unsigned	raw_skid_size;
-	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
-	unsigned	index;
-	bool		seen;			/* Infinite recursion prevention */
-	bool		verified;
-	bool		self_signed;		/* T if self-signed (check unsupported_sig too) */
-	bool		unsupported_sig;	/* T if signature uses unsupported crypto */
-	bool		blacklisted;
-};
+#include <keys/x509-parser.h>
 
 /*
  * x509_cert_parser.c
  */
-extern void x509_free_certificate(struct x509_certificate *cert);
-DEFINE_FREE(x509_free_certificate, struct x509_certificate *,
-	    if (!IS_ERR(_T)) x509_free_certificate(_T))
-extern struct x509_certificate *x509_cert_parse(const void *data, size_t datalen);
 extern int x509_decode_time(time64_t *_t,  size_t hdrlen,
 			    unsigned char tag,
 			    const unsigned char *value, size_t vlen);
diff --git a/include/keys/x509-parser.h b/include/keys/x509-parser.h
new file mode 100644
index 000000000000..37436a5c7526
--- /dev/null
+++ b/include/keys/x509-parser.h
@@ -0,0 +1,53 @@
+/* SPDX-License-Identifier: GPL-2.0-or-later */
+/* X.509 certificate parser
+ *
+ * Copyright (C) 2012 Red Hat, Inc. All Rights Reserved.
+ * Written by David Howells (dhowells@redhat.com)
+ */
+
+#ifndef _KEYS_X509_PARSER_H
+#define _KEYS_X509_PARSER_H
+
+#include <crypto/public_key.h>
+#include <keys/asymmetric-type.h>
+#include <linux/cleanup.h>
+#include <linux/time64.h>
+
+struct x509_certificate {
+	struct x509_certificate *next;
+	struct x509_certificate *signer;	/* Certificate that signed this one */
+	struct public_key *pub;			/* Public key details */
+	struct public_key_signature *sig;	/* Signature parameters */
+	char		*issuer;		/* Name of certificate issuer */
+	char		*subject;		/* Name of certificate subject */
+	struct asymmetric_key_id *id;		/* Issuer + Serial number */
+	struct asymmetric_key_id *skid;		/* Subject + subjectKeyId (optional) */
+	time64_t	valid_from;
+	time64_t	valid_to;
+	const void	*tbs;			/* Signed data */
+	unsigned	tbs_size;		/* Size of signed data */
+	unsigned	raw_sig_size;		/* Size of signature */
+	const void	*raw_sig;		/* Signature data */
+	const void	*raw_serial;		/* Raw serial number in ASN.1 */
+	unsigned	raw_serial_size;
+	unsigned	raw_issuer_size;
+	const void	*raw_issuer;		/* Raw issuer name in ASN.1 */
+	const void	*raw_subject;		/* Raw subject name in ASN.1 */
+	unsigned	raw_subject_size;
+	unsigned	raw_skid_size;
+	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
+	unsigned	index;
+	bool		seen;			/* Infinite recursion prevention */
+	bool		verified;
+	bool		self_signed;		/* T if self-signed (check unsupported_sig too) */
+	bool		unsupported_sig;	/* T if signature uses unsupported crypto */
+	bool		blacklisted;
+};
+
+struct x509_certificate *x509_cert_parse(const void *data, size_t datalen);
+void x509_free_certificate(struct x509_certificate *cert);
+
+DEFINE_FREE(x509_free_certificate, struct x509_certificate *,
+	    if (!IS_ERR(_T)) x509_free_certificate(_T))
+
+#endif /* _KEYS_X509_PARSER_H */

---

## [18] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 17/38] X.509: Parse Subject Alternative Name in certificates*

From: Lukas Wunner <lukas@wunner.de>

The upcoming support for PCI device authentication with CMA-SPDM
(PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name
in X.509 certificates.

Store a pointer to the Subject Alternative Name upon parsing for
consumption by CMA-SPDM.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Wilfred Mallawa <wilfred.mallawa@wdc.com>
Reviewed-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Acked-by: Dan Williams <dan.j.williams@intel.com>
---
 crypto/asymmetric_keys/x509_cert_parser.c | 9 +++++++++
 include/keys/x509-parser.h                | 2 ++
 2 files changed, 11 insertions(+)

diff --git a/crypto/asymmetric_keys/x509_cert_parser.c b/crypto/asymmetric_keys/x509_cert_parser.c
index 2ffe4ae90bea..ac8a01c2b9fc 100644
--- a/crypto/asymmetric_keys/x509_cert_parser.c
+++ b/crypto/asymmetric_keys/x509_cert_parser.c
@@ -571,6 +571,15 @@ int x509_process_extension(void *context, size_t hdrlen,
 		return 0;
 	}
 
+	if (ctx->last_oid == OID_subjectAltName) {
+		if (ctx->cert->raw_san)
+			return -EBADMSG;
+
+		ctx->cert->raw_san = v;
+		ctx->cert->raw_san_size = vlen;
+		return 0;
+	}
+
 	if (ctx->last_oid == OID_keyUsage) {
 		/*
 		 * Get hold of the keyUsage bit string
diff --git a/include/keys/x509-parser.h b/include/keys/x509-parser.h
index 37436a5c7526..8e450befe3b9 100644
--- a/include/keys/x509-parser.h
+++ b/include/keys/x509-parser.h
@@ -36,6 +36,8 @@ struct x509_certificate {
 	unsigned	raw_subject_size;
 	unsigned	raw_skid_size;
 	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
+	const void	*raw_san;		/* Raw subjectAltName in ASN.1 */
+	unsigned	raw_san_size;
 	unsigned	index;
 	bool		seen;			/* Infinite recursion prevention */
 	bool		verified;

---

## [19] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 18/38] X.509: Move certificate length retrieval into new helper*

From: Lukas Wunner <lukas@wunner.de>

The upcoming in-kernel SPDM library (Security Protocol and Data Model,
https://www.dmtf.org/dsp/DSP0274) needs to retrieve the length from
ASN.1 DER-encoded X.509 certificates.

Such code already exists in x509_load_certificate_list(), so move it
into a new helper for reuse by SPDM.

Export the helper so that SPDM can be tristate.  (Some upcoming users of
the SPDM libray may be modular, such as SCSI and ATA.)

No functional change intended.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/asymmetric_keys/x509_loader.c | 38 +++++++++++++++++++---------
 include/keys/asymmetric-type.h       |  2 ++
 2 files changed, 28 insertions(+), 12 deletions(-)

diff --git a/crypto/asymmetric_keys/x509_loader.c b/crypto/asymmetric_keys/x509_loader.c
index a41741326998..25ff027fad1d 100644
--- a/crypto/asymmetric_keys/x509_loader.c
+++ b/crypto/asymmetric_keys/x509_loader.c
@@ -4,28 +4,42 @@
 #include <linux/key.h>
 #include <keys/asymmetric-type.h>
 
+ssize_t x509_get_certificate_length(const u8 *p, unsigned long buflen)
+{
+	ssize_t plen;
+
+	/* Each cert begins with an ASN.1 SEQUENCE tag and must be more
+	 * than 256 bytes in size.
+	 */
+	if (buflen < 4)
+		return -EINVAL;
+
+	if (p[0] != 0x30 &&
+	    p[1] != 0x82)
+		return -EINVAL;
+
+	plen = (p[2] << 8) | p[3];
+	plen += 4;
+	if (plen > buflen)
+		return -EINVAL;
+
+	return plen;
+}
+EXPORT_SYMBOL_GPL(x509_get_certificate_length);
+
 int x509_load_certificate_list(const u8 cert_list[],
 			       const unsigned long list_size,
 			       const struct key *keyring)
 {
 	key_ref_t key;
 	const u8 *p, *end;
-	size_t plen;
+	ssize_t plen;
 
 	p = cert_list;
 	end = p + list_size;
 	while (p < end) {
-		/* Each cert begins with an ASN.1 SEQUENCE tag and must be more
-		 * than 256 bytes in size.
-		 */
-		if (end - p < 4)
-			goto dodgy_cert;
-		if (p[0] != 0x30 &&
-		    p[1] != 0x82)
-			goto dodgy_cert;
-		plen = (p[2] << 8) | p[3];
-		plen += 4;
-		if (plen > end - p)
+		plen = x509_get_certificate_length(p, end - p);
+		if (plen < 0)
 			goto dodgy_cert;
 
 		key = key_create_or_update(make_key_ref(keyring, 1),
diff --git a/include/keys/asymmetric-type.h b/include/keys/asymmetric-type.h
index 69a13e1e5b2e..e2af07fec3c6 100644
--- a/include/keys/asymmetric-type.h
+++ b/include/keys/asymmetric-type.h
@@ -84,6 +84,8 @@ extern struct key *find_asymmetric_key(struct key *keyring,
 				       const struct asymmetric_key_id *id_2,
 				       bool partial);
 
+ssize_t x509_get_certificate_length(const u8 *p, unsigned long buflen);
+
 int x509_load_certificate_list(const u8 cert_list[], const unsigned long list_size,
 			       const struct key *keyring);

---

## [20] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 19/38] coco: host: arm64: set_pubkey support*

Add changes to share the device's public key with the RMM.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       |   9 ++
 arch/arm64/include/asm/rmi_smc.h        |  18 +++
 drivers/virt/coco/arm-cca-host/Kconfig  |   4 +
 drivers/virt/coco/arm-cca-host/rmm-da.c | 150 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h |   1 +
 5 files changed, 182 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index d4ea9f8363f5..aef0b0ee062e 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -565,4 +565,13 @@ static inline unsigned long rmi_pdev_destroy(unsigned long pdev_phys)
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_set_pubkey(unsigned long pdev_phys, unsigned long key_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_SET_PUBKEY, pdev_phys, key_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 9f25a876238e..4a5ba98c1c0d 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -51,6 +51,7 @@
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
 #define SMC_RMI_PDEV_DESTROY		SMC_RMI_CALL(0x0177)
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
+#define SMC_RMI_PDEV_SET_PUBKEY		SMC_RMI_CALL(0x017b)
 #define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
 
 #define RMI_ABI_MAJOR_VERSION	1
@@ -389,4 +390,21 @@ struct rmi_dev_comm_data {
 	};
 };
 
+#define RMI_SIG_RSASSA_3072	0
+#define RMI_SIG_ECDSA_P256	1
+#define RMI_SIG_ECDSA_P384	2
+
+struct rmi_public_key_params {
+	union {
+		struct {
+			u8 public_key[1024];
+			u8 metadata[1024];
+			u64 public_key_len;
+			u64 metadata_len;
+			u8 rmi_signature_algorithm;
+		} __packed;
+		u8 padding[0x1000];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
index 0f19fbf47613..a5b777f0d50e 100644
--- a/drivers/virt/coco/arm-cca-host/Kconfig
+++ b/drivers/virt/coco/arm-cca-host/Kconfig
@@ -6,7 +6,11 @@ config ARM_CCA_HOST
 	tristate "Arm CCA Host driver"
 	depends on ARM64
 	depends on PCI_TSM
+	select KEYS
+	select X509_CERTIFICATE_PARSER
 	select TSM
+	select CRYPTO_ECDSA
+	select CRYPTO_RSA
 
 	help
 	  The driver provides TSM backend for ARM CCA
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index ec8c5bfcee35..3715e6d58c83 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -6,6 +6,9 @@
 #include <linux/pci.h>
 #include <linux/pci-ecam.h>
 #include <asm/rmi_cmds.h>
+#include <crypto/internal/rsa.h>
+#include <keys/asymmetric-type.h>
+#include <keys/x509-parser.h>
 
 #include "rmm-da.h"
 
@@ -311,6 +314,136 @@ static int do_pdev_communicate(struct pci_tsm *tsm, int target_state)
 	return do_dev_communicate(PDEV_COMMUNICATE, tsm, target_state);
 }
 
+static int parse_certificate_chain(struct pci_tsm *tsm)
+{
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	unsigned int chain_size;
+	unsigned int offset = 0;
+	u8 *chain_data;
+	int ret = 0;
+
+	dsc_pf0 = to_cca_dsc_pf0(tsm->pdev);
+	chain_size = dsc_pf0->cert_chain.cache.size;
+	chain_data = dsc_pf0->cert_chain.cache.buf;
+
+	while (offset < chain_size) {
+		unsigned int cert_len =
+			x509_get_certificate_length(chain_data + offset,
+						    chain_size - offset);
+		struct x509_certificate *cert =
+			x509_cert_parse(chain_data + offset, cert_len);
+
+		if (IS_ERR(cert)) {
+			pr_warn("%s(): parsing of certificate chain not successful\n", __func__);
+			ret = PTR_ERR(cert);
+			break;
+		}
+
+		if (offset + cert_len == chain_size) {
+			dsc_pf0->cert_chain.public_key = kzalloc(cert->pub->keylen, GFP_KERNEL);
+			if (!dsc_pf0->cert_chain.public_key) {
+				ret = -ENOMEM;
+				x509_free_certificate(cert);
+				break;
+			}
+
+			if (!strcmp("ecdsa-nist-p256", cert->pub->pkey_algo)) {
+				dsc_pf0->rmi_signature_algorithm = RMI_SIG_ECDSA_P256;
+			} else if (!strcmp("ecdsa-nist-p384", cert->pub->pkey_algo)) {
+				dsc_pf0->rmi_signature_algorithm = RMI_SIG_ECDSA_P384;
+			} else if (!strcmp("rsa", cert->pub->pkey_algo)) {
+				dsc_pf0->rmi_signature_algorithm = RMI_SIG_RSASSA_3072;
+			} else {
+				ret = -ENXIO;
+				x509_free_certificate(cert);
+				break;
+			}
+			memcpy(dsc_pf0->cert_chain.public_key, cert->pub->key, cert->pub->keylen);
+			dsc_pf0->cert_chain.public_key_size = cert->pub->keylen;
+		}
+
+		x509_free_certificate(cert);
+
+		offset += cert_len;
+	}
+
+	if (ret == 0)
+		dsc_pf0->cert_chain.valid = true;
+
+	return ret;
+}
+
+static int pdev_set_public_key(struct pci_tsm *tsm)
+{
+	struct rmi_public_key_params *key_shared;
+	unsigned long expected_key_len = 0;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	int ret;
+
+	dsc_pf0 = to_cca_dsc_pf0(tsm->pdev);
+	/* Check that all the necessary information was captured from communication */
+	if (!dsc_pf0->cert_chain.valid)
+		return -EINVAL;
+
+	key_shared = (struct rmi_public_key_params *)get_zeroed_page(GFP_KERNEL);
+	if (!key_shared)
+		return -ENOMEM;
+
+	key_shared->rmi_signature_algorithm = dsc_pf0->rmi_signature_algorithm;
+
+	switch (key_shared->rmi_signature_algorithm) {
+	case RMI_SIG_ECDSA_P384:
+		expected_key_len = 97;
+
+		if (dsc_pf0->cert_chain.public_key_size != expected_key_len)
+			return -EINVAL;
+		key_shared->public_key_len = dsc_pf0->cert_chain.public_key_size;
+		memcpy(key_shared->public_key,
+		       dsc_pf0->cert_chain.public_key,
+		       dsc_pf0->cert_chain.public_key_size);
+		key_shared->metadata_len = 0;
+		break;
+	case RMI_SIG_ECDSA_P256:
+		expected_key_len = 65;
+
+		if (dsc_pf0->cert_chain.public_key_size != expected_key_len)
+			return -EINVAL;
+		key_shared->public_key_len = dsc_pf0->cert_chain.public_key_size;
+		memcpy(key_shared->public_key,
+		       dsc_pf0->cert_chain.public_key,
+		       dsc_pf0->cert_chain.public_key_size);
+		key_shared->metadata_len = 0;
+		break;
+	case RMI_SIG_RSASSA_3072:
+		expected_key_len = 385;
+		struct rsa_key rsa_key = {0};
+		int ret_rsa_parse = rsa_parse_pub_key(&rsa_key,
+						      dsc_pf0->cert_chain.public_key,
+						      dsc_pf0->cert_chain.public_key_size);
+		/* This also checks the key_len */
+		if (ret_rsa_parse)
+			return ret_rsa_parse;
+		/*
+		 * exponent is usally 65537 (size = 24bits) but in rare cases
+		 * it size can be as large as the modulus
+		 */
+		if (rsa_key.e_sz > expected_key_len)
+			return -EINVAL;
+		key_shared->public_key_len = rsa_key.n_sz;
+		key_shared->metadata_len = rsa_key.e_sz;
+		memcpy(key_shared->public_key, (unsigned char *)rsa_key.n, rsa_key.n_sz);
+		memcpy(key_shared->metadata, (unsigned char *)rsa_key.e, rsa_key.e_sz);
+		break;
+	default:
+		return -EINVAL;
+	}
+
+	ret = rmi_pdev_set_pubkey(virt_to_phys(dsc_pf0->rmm_pdev),
+				  virt_to_phys(key_shared));
+	free_page((unsigned long)key_shared);
+	return ret;
+}
+
 struct dev_comm_work {
 	struct pci_tsm *tsm;
 	struct work_struct work;
@@ -319,6 +452,7 @@ struct dev_comm_work {
 
 static void pdev_ide_setup_work(struct work_struct *work)
 {
+	int ret;
 	unsigned long state;
 	struct pci_tsm *tsm;
 	struct dev_comm_work *setup_work;
@@ -329,6 +463,22 @@ static void pdev_ide_setup_work(struct work_struct *work)
 	state = do_pdev_communicate(tsm, RMI_PDEV_NEEDS_KEY);
 	WARN_ON(state != RMI_PDEV_NEEDS_KEY);
 
+	/*
+	 * we now have certificate chain in dsm->cert_chain. Parse
+	 * that and set the pubkey.
+	 */
+	ret = parse_certificate_chain(tsm);
+	if (ret)
+		goto err_out;
+
+	ret = pdev_set_public_key(tsm);
+	if (ret)
+		goto err_out;
+
+	state = do_pdev_communicate(tsm, RMI_PDEV_READY);
+	WARN_ON(state != RMI_PDEV_READY);
+
+err_out:
 	complete(&setup_work->complete);
 }
 
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index c401be55d770..03c3149b8a98 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -33,6 +33,7 @@ struct cca_host_dsc_pf0 {
 	int num_aux;
 	void *aux[MAX_PDEV_AUX_GRANULES];
 
+	uint8_t rmi_signature_algorithm;
 	struct {
 		struct cache_object cache;

---

## [21] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 20/38] coco: host: arm64: Add support for creating a virtual device*

Changes to support the creation of virtual device objects with RMM.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 13 +++++
 arch/arm64/include/asm/rmi_smc.h         | 30 +++++++++++
 drivers/virt/coco/arm-cca-host/Kconfig   |  1 +
 drivers/virt/coco/arm-cca-host/arm-cca.c | 30 +++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 67 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  | 17 ++++++
 6 files changed, 158 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index aef0b0ee062e..7d91f847069b 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -574,4 +574,17 @@ static inline unsigned long rmi_pdev_set_pubkey(unsigned long pdev_phys, unsigne
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_create(unsigned long rd,
+					    unsigned long pdev_phys,
+					    unsigned long vdev_phys,
+					    unsigned long vdev_params_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_CREATE, rd, pdev_phys,
+			     vdev_phys, vdev_params_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 4a5ba98c1c0d..e5238b271493 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -53,6 +53,8 @@
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
 #define SMC_RMI_PDEV_SET_PUBKEY		SMC_RMI_CALL(0x017b)
 #define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
+#define SMC_RMI_VDEV_CREATE		SMC_RMI_CALL(0x0187)
+
 
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
@@ -407,4 +409,32 @@ struct rmi_public_key_params {
 	};
 };
 
+enum rmi_vdev_state {
+	RMI_VDEV_READY,
+	RMI_VDEV_COMMUNICATING,
+	RMI_VDEV_STOPPING,
+	RMI_VDEV_STOPPED,
+	RMI_VDEV_ERROR,
+};
+
+#define MAX_VDEV_AUX_GRANULES	32
+
+struct rmi_vdev_params {
+	union {
+		struct {
+			u64 flags;
+			u64 vdev_id;
+			u64 tdi_id;
+			u64 num_aux;
+		};
+		u8 padding1[0x100];
+	};
+	union {	/* 0x100 */
+		struct {
+			unsigned long aux[MAX_VDEV_AUX_GRANULES];
+		};
+		u8 padding2[0x900];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
index a5b777f0d50e..52ed1cd5f06a 100644
--- a/drivers/virt/coco/arm-cca-host/Kconfig
+++ b/drivers/virt/coco/arm-cca-host/Kconfig
@@ -6,6 +6,7 @@ config ARM_CCA_HOST
 	tristate "Arm CCA Host driver"
 	depends on ARM64
 	depends on PCI_TSM
+	depends on KVM
 	select KEYS
 	select X509_CERTIFICATE_PARSER
 	select TSM
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index c65b81f0706f..2da513f45974 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -10,6 +10,8 @@
 #include <linux/pci.h>
 #include <linux/tsm.h>
 #include <linux/vmalloc.h>
+#include <linux/kvm_host.h>
+#include <linux/pci.h>
 
 #include "rmm-da.h"
 
@@ -221,11 +223,39 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	free_dev_communication_buffers(&dsc_pf0->comm_data);
 }
 
+static struct pci_tdi *cca_tsm_bind(struct pci_dev *pdev, struct pci_dev *pf0_dev,
+				    struct kvm *kvm, u64 tdi_id)
+{
+	void *rmm_vdev;
+	struct cca_host_tdi *host_tdi __free(kfree) = NULL;
+	struct realm *realm = &kvm->arch.realm;
+
+	if (pdev->is_virtfn)
+		return ERR_PTR(-ENXIO);
+
+	if (!try_module_get(THIS_MODULE))
+		return ERR_PTR(-ENXIO);
+
+	host_tdi = kmalloc(sizeof(struct cca_host_tdi), GFP_KERNEL);
+	if (!host_tdi)
+		return ERR_PTR(-ENOMEM);
+
+	rmm_vdev = rme_create_vdev(realm, pdev, pf0_dev, tdi_id);
+	if (!IS_ERR_OR_NULL(rmm_vdev)) {
+		host_tdi->rmm_vdev = rmm_vdev;
+		return &no_free_ptr(host_tdi)->tdi;
+	}
+
+	module_put(THIS_MODULE);
+	return rmm_vdev;
+}
+
 static const struct pci_tsm_ops cca_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
 	.connect = cca_tsm_connect,
 	.disconnect = cca_tsm_disconnect,
+	.bind	= cca_tsm_bind,
 };
 
 static void cca_tsm_remove(void *tsm_core)
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index 3715e6d58c83..41314db1d568 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -9,6 +9,8 @@
 #include <crypto/internal/rsa.h>
 #include <keys/asymmetric-type.h>
 #include <keys/x509-parser.h>
+#include <linux/kvm_types.h>
+#include <asm/kvm_rme.h>
 
 #include "rmm-da.h"
 
@@ -517,3 +519,68 @@ void rme_unassign_device(struct pci_dev *pdev)
 	if (WARN_ON(ret != RMI_SUCCESS))
 		return;
 }
+
+static unsigned long pci_get_tdi_id(struct pci_dev *pdev)
+{
+	/* requester segment is marked reserved. */
+	return pci_dev_id(pdev);
+
+}
+
+void *rme_create_vdev(struct realm *realm, struct pci_dev *pdev,
+		      struct pci_dev *pf0_dev, u32 guest_rid)
+{
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	struct rmi_vdev_params *params = NULL;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	void *rmm_vdev;
+	int ret;
+
+	dsc_pf0 = to_cca_dsc_pf0(pf0_dev);
+	if (!dsc_pf0->rmm_pdev) {
+		ret = -EINVAL;
+		goto err_out;
+	}
+
+	rmm_vdev = (void *)get_zeroed_page(GFP_KERNEL);
+	if (!rmm_vdev) {
+		ret =  -ENOMEM;
+		goto err_out;
+	}
+
+	rmm_vdev_phys = virt_to_phys(rmm_vdev);
+	if (rmi_granule_delegate(rmm_vdev_phys)) {
+		ret = -ENXIO;
+		goto err_free_vdev;
+	}
+
+	params = (struct rmi_vdev_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params) {
+		ret = -ENOMEM;
+		goto err_granule_undelegate;
+	}
+
+	params->flags = 0;
+	params->vdev_id = guest_rid;
+	params->tdi_id = pci_get_tdi_id(pdev);
+	params->num_aux = 0;
+
+	rmm_pdev_phys = virt_to_phys(dsc_pf0->rmm_pdev);
+	ret = rmi_vdev_create(rd_phys, rmm_pdev_phys,
+			      rmm_vdev_phys, virt_to_phys(params));
+	if (ret)
+		goto err_granule_undelegate;
+
+	free_page((unsigned long)params);
+	return rmm_vdev;
+
+err_granule_undelegate:
+	rmi_granule_undelegate(rmm_vdev_phys);
+err_free_vdev:
+	free_page((unsigned long)rmm_vdev);
+	free_page((unsigned long)params);
+err_out:
+	return ERR_PTR(ret);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index 03c3149b8a98..6d612ea3b87f 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -45,6 +45,11 @@ struct cca_host_dsc_pf0 {
 	struct cache_object vca;
 };
 
+struct cca_host_tdi {
+	struct pci_tdi tdi;
+	void *rmm_vdev;
+};
+
 #define PDEV_COMMUNICATE	0x1
 static inline struct cca_host_dsc_pf0 *to_cca_dsc_pf0(struct pci_dev *pdev)
 {
@@ -71,7 +76,19 @@ static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
 	return NULL;
 }
 
+static inline struct cca_host_tdi *to_cca_host_tdi(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm || !tsm->tdi)
+		return NULL;
+
+	return container_of(tsm->tdi, struct cca_host_tdi, tdi);
+}
+
 int rme_asign_device(struct pci_dev *pdev);
 void rme_unassign_device(struct pci_dev *pdev);
 int schedule_rme_ide_setup(struct pci_dev *pdev);
+void *rme_create_vdev(struct realm *realm, struct pci_dev *pdev,
+		      struct pci_dev *pf0_dev, u32 guest_rid);
 #endif

---

## [22] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 21/38] coco: host: arm64: Add support for virtual device communication*

Add support for vdev_communicate with RMM.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       | 22 ++++++++++++++++++++++
 arch/arm64/include/asm/rmi_smc.h        |  2 ++
 drivers/virt/coco/arm-cca-host/rmm-da.c | 21 +++++++++++++++++++--
 drivers/virt/coco/arm-cca-host/rmm-da.h |  2 ++
 4 files changed, 45 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 7d91f847069b..25197f47a0a9 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -587,4 +587,26 @@ static inline unsigned long rmi_vdev_create(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_communicate(unsigned long pdev_phys,
+						 unsigned long vdev_phys,
+						 unsigned long vdev_comm_data_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_COMMUNICATE,
+			     pdev_phys, vdev_phys, vdev_comm_data_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_get_state(unsigned long vdev_phys, unsigned long *state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_STATE, vdev_phys, &res);
+
+	*state = res.a1;
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index e5238b271493..127dd0938604 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -53,7 +53,9 @@
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
 #define SMC_RMI_PDEV_SET_PUBKEY		SMC_RMI_CALL(0x017b)
 #define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
+#define SMC_RMI_VDEV_COMMUNICATE	SMC_RMI_CALL(0x0186)
 #define SMC_RMI_VDEV_CREATE		SMC_RMI_CALL(0x0187)
+#define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
 
 
 #define RMI_ABI_MAJOR_VERSION	1
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index 41314db1d568..8635f361bbe8 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -207,8 +207,14 @@ static int __do_dev_communicate(int type, struct pci_tsm *tsm)
 	if (type == PDEV_COMMUNICATE)
 		ret = rmi_pdev_communicate(virt_to_phys(dsc_pf0->rmm_pdev),
 					   virt_to_phys(comm_data->io_params));
-	else
-		ret = RMI_ERROR_INPUT;
+	else {
+		struct cca_host_tdi *host_tdi = container_of(tsm->tdi, struct cca_host_tdi, tdi);
+
+		ret = rmi_vdev_communicate(virt_to_phys(dsc_pf0->rmm_pdev),
+					   virt_to_phys(host_tdi->rmm_vdev),
+					   virt_to_phys(comm_data->io_params));
+	}
+
 	if (ret != RMI_SUCCESS) {
 		pr_err("pdev communicate error\n");
 		return ret;
@@ -299,6 +305,12 @@ static int do_dev_communicate(int type, struct pci_tsm *tsm, int target_state)
 			ret = rmi_pdev_get_state(virt_to_phys(dsc_pf0->rmm_pdev),
 						 &state);
 			error_state = RMI_PDEV_ERROR;
+		} else {
+			struct cca_host_tdi *host_tdi = container_of(tsm->tdi, struct cca_host_tdi, tdi);
+
+			ret = rmi_vdev_get_state(virt_to_phys(host_tdi->rmm_vdev),
+						 &state);
+			error_state = RMI_VDEV_ERROR;
 		}
 		if (ret != 0) {
 			pr_err("Get dev state error\n");
@@ -584,3 +596,8 @@ void *rme_create_vdev(struct realm *realm, struct pci_dev *pdev,
 err_out:
 	return ERR_PTR(ret);
 }
+
+static int __maybe_unused do_vdev_communicate(struct pci_tsm *tsm, int target_state)
+{
+	return do_dev_communicate(VDEV_COMMUNICATE, tsm, target_state);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index 6d612ea3b87f..37a8f4dce68e 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -51,6 +51,8 @@ struct cca_host_tdi {
 };
 
 #define PDEV_COMMUNICATE	0x1
+#define VDEV_COMMUNICATE	0x2
+
 static inline struct cca_host_dsc_pf0 *to_cca_dsc_pf0(struct pci_dev *pdev)
 {
 	struct pci_tsm *tsm = pdev->tsm;

---

## [23] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 22/38] coco: host: arm64: Stop and destroy virtual device*

Add support for vdev_stop and vdev_destroy.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 21 ++++++++
 arch/arm64/include/asm/rmi_smc.h         |  3 +-
 drivers/virt/coco/arm-cca-host/arm-cca.c | 10 ++++
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 61 +++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmm-da.h  |  2 +
 5 files changed, 95 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 25197f47a0a9..eb4f67eb6b01 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -609,4 +609,25 @@ static inline unsigned long rmi_vdev_get_state(unsigned long vdev_phys, unsigned
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_stop(unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_STOP, vdev_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_destroy(unsigned long rd,
+					     unsigned long pdev_phys,
+					     unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_DESTROY, rd, pdev_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 127dd0938604..c6e16ab608e1 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -55,8 +55,9 @@
 #define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
 #define SMC_RMI_VDEV_COMMUNICATE	SMC_RMI_CALL(0x0186)
 #define SMC_RMI_VDEV_CREATE		SMC_RMI_CALL(0x0187)
+#define SMC_RMI_VDEV_DESTROY		SMC_RMI_CALL(0x0188)
 #define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
-
+#define SMC_RMI_VDEV_STOP		SMC_RMI_CALL(0x018A)
 
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 2da513f45974..3792d7b5cb99 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -250,12 +250,22 @@ static struct pci_tdi *cca_tsm_bind(struct pci_dev *pdev, struct pci_dev *pf0_de
 	return rmm_vdev;
 }
 
+static void cca_tsm_unbind(struct pci_tdi *tdi)
+{
+	struct realm *realm = &tdi->kvm->arch.realm;
+
+	rme_unbind_vdev(realm, tdi->pdev, tdi->pdev->tsm->dsm_dev);
+
+	module_put(THIS_MODULE);
+}
+
 static const struct pci_tsm_ops cca_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
 	.connect = cca_tsm_connect,
 	.disconnect = cca_tsm_disconnect,
 	.bind	= cca_tsm_bind,
+	.unbind = cca_tsm_unbind,
 };
 
 static void cca_tsm_remove(void *tsm_core)
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index 8635f361bbe8..53072610fa67 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -597,7 +597,66 @@ void *rme_create_vdev(struct realm *realm, struct pci_dev *pdev,
 	return ERR_PTR(ret);
 }
 
-static int __maybe_unused do_vdev_communicate(struct pci_tsm *tsm, int target_state)
+static int do_vdev_communicate(struct pci_tsm *tsm, int target_state)
 {
 	return do_dev_communicate(VDEV_COMMUNICATE, tsm, target_state);
 }
+
+static void vdev_stop_work(struct work_struct *work)
+{
+	struct dev_comm_work *stop_work;
+	struct pci_tsm *tsm;
+	unsigned long state;
+
+	stop_work = container_of(work, struct dev_comm_work, work);
+	tsm = stop_work->tsm;
+
+	state = do_vdev_communicate(tsm, RMI_VDEV_STOPPED);
+	WARN_ON(state != RMI_VDEV_STOPPED);
+
+	complete(&stop_work->complete);
+}
+
+static int schedule_vdev_unbind(struct pci_dev *pdev)
+{
+	struct dev_comm_work unbind_work = {
+		.tsm = pdev->tsm,
+	};
+
+	INIT_WORK_ONSTACK(&unbind_work.work, vdev_stop_work);
+	init_completion(&unbind_work.complete);
+	schedule_work(&unbind_work.work);
+	wait_for_completion(&unbind_work.complete);
+	destroy_work_on_stack(&unbind_work.work);
+
+	return 0;
+}
+
+void rme_unbind_vdev(struct realm *realm, struct pci_dev *pdev, struct pci_dev *pf0_dev)
+{
+	int ret;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	struct cca_host_tdi *host_tdi;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+
+	host_tdi = container_of(pdev->tsm->tdi, struct cca_host_tdi, tdi);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+
+	dsc_pf0 = to_cca_dsc_pf0(pf0_dev);
+	rmm_pdev_phys = virt_to_phys(dsc_pf0->rmm_pdev);
+	/* Request stopping the VDEV */
+	ret = rmi_vdev_stop(rmm_vdev_phys);
+	if (ret) {
+		pr_err("failed to stop vdev (%d)\n", ret);
+		return;
+	}
+
+	schedule_vdev_unbind(pdev);
+	ret = rmi_vdev_destroy(rd_phys, rmm_pdev_phys, rmm_vdev_phys);
+	if (ret) {
+		pr_err("failed to destroy vdev (%d)\n", ret);
+		return;
+	}
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index 37a8f4dce68e..6361f7403f95 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -93,4 +93,6 @@ void rme_unassign_device(struct pci_dev *pdev);
 int schedule_rme_ide_setup(struct pci_dev *pdev);
 void *rme_create_vdev(struct realm *realm, struct pci_dev *pdev,
 		      struct pci_dev *pf0_dev, u32 guest_rid);
+void rme_unbind_vdev(struct realm *realm, struct pci_dev *pdev,
+		     struct pci_dev *pf0_dev);
 #endif

---

## [24] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 23/38] coco: guest: arm64: Update arm CCA guest driver*

This patch includes renaming changes to simplify the registration of a
TSM backend in the next patch. There are no functional changes in this
update.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi.h                  |  2 +-
 arch/arm64/kernel/rsi.c                       |  2 +-
 drivers/virt/coco/arm-cca-guest/Makefile      |  3 ++
 .../{arm-cca-guest.c => arm-cca.c}            | 52 +++++++++----------
 4 files changed, 29 insertions(+), 30 deletions(-)
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (86%)

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index b42aeac05340..26ef6143562b 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -10,7 +10,7 @@
 #include <linux/jump_label.h>
 #include <asm/rsi_cmds.h>
 
-#define RSI_PDEV_NAME "arm-cca-dev"
+#define RSI_DEV_NAME "arm-rsi-dev"
 
 DECLARE_STATIC_KEY_FALSE(rsi_present);
 
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index ce4778141ec7..bf9ea99e2aa1 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -142,7 +142,7 @@ void __init arm64_rsi_init(void)
 }
 
 static struct platform_device rsi_dev = {
-	.name = RSI_PDEV_NAME,
+	.name = RSI_DEV_NAME,
 	.id = PLATFORM_DEVID_NONE
 };
 
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 69eeba08e98a..609462ea9438 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -1,2 +1,5 @@
 # SPDX-License-Identifier: GPL-2.0-only
+#
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
+
+arm-cca-guest-$(CONFIG_TSM) +=  arm-cca.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
similarity index 86%
rename from drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
rename to drivers/virt/coco/arm-cca-guest/arm-cca.c
index 0c9ea24a200c..547fc2c79f7d 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -11,6 +11,7 @@
 #include <linux/smp.h>
 #include <linux/tsm.h>
 #include <linux/types.h>
+#include <linux/platform_device.h>
 
 #include <asm/rsi.h>
 
@@ -181,52 +182,47 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
 	return ret;
 }
 
-static const struct tsm_report_ops arm_cca_tsm_ops = {
+static const struct tsm_report_ops arm_cca_tsm_report_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = arm_cca_report_new,
 };
 
-/**
- * arm_cca_guest_init - Register with the Trusted Security Module (TSM)
- * interface.
- *
- * Return:
- * * %0        - Registered successfully with the TSM interface.
- * * %-ENODEV  - The execution context is not an Arm Realm.
- * * %-EBUSY   - Already registered.
- */
-static int __init arm_cca_guest_init(void)
+static void unregister_cca_tsm_report(void *data)
+{
+	tsm_report_unregister(&arm_cca_tsm_report_ops);
+}
+
+static int cca_guest_probe(struct platform_device *pdev)
 {
 	int ret;
 
 	if (!is_realm_world())
 		return -ENODEV;
 
-	ret = tsm_report_register(&arm_cca_tsm_ops, NULL);
+	ret = tsm_report_register(&arm_cca_tsm_report_ops, NULL);
 	if (ret < 0)
 		pr_err("Error %d registering with TSM\n", ret);
 
-	return ret;
-}
-module_init(arm_cca_guest_init);
+	ret = devm_add_action_or_reset(&pdev->dev, unregister_cca_tsm_report, NULL);
 
-/**
- * arm_cca_guest_exit - unregister with the Trusted Security Module (TSM)
- * interface.
- */
-static void __exit arm_cca_guest_exit(void)
-{
-	tsm_report_unregister(&arm_cca_tsm_ops);
+	return ret;
 }
-module_exit(arm_cca_guest_exit);
 
 /* modalias, so userspace can autoload this module when RSI is available */
-static const struct platform_device_id arm_cca_match[] __maybe_unused = {
-	{ RSI_PDEV_NAME, 0},
+static const struct platform_device_id arm_cca_guest_id_table[] = {
+	{ RSI_DEV_NAME, 0},
 	{ }
 };
-
-MODULE_DEVICE_TABLE(platform, arm_cca_match);
+MODULE_DEVICE_TABLE(platform, arm_cca_guest_id_table);
+
+static struct platform_driver cca_guest_platform_driver = {
+	.probe = cca_guest_probe,
+	.id_table = arm_cca_guest_id_table,
+	.driver = {
+		.name = "arm-cca-guest",
+	},
+};
+module_platform_driver(cca_guest_platform_driver);
 MODULE_AUTHOR("Sami Mujawar <sami.mujawar@arm.com>");
-MODULE_DESCRIPTION("Arm CCA Guest TSM Driver");
+MODULE_DESCRIPTION("Arm CCA Guest TSM driver");
 MODULE_LICENSE("GPL");

---

## [25] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 24/38] arm64: CCA: Register guest tsm callback*

Register the TSM callback if the DA feature is supported by RSI.

Additionally, adjust the build order so that the TSM class is created
before the arm-cca-guest driver initialization.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi.h              |  3 +
 arch/arm64/include/asm/rsi_cmds.h         | 18 ++++++
 arch/arm64/include/asm/rsi_smc.h          |  1 +
 arch/arm64/kernel/rsi.c                   | 24 ++++++--
 drivers/virt/coco/Makefile                |  2 +-
 drivers/virt/coco/arm-cca-guest/Kconfig   |  8 ++-
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 71 ++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-guest/rsi-da.h  | 27 +++++++++
 8 files changed, 144 insertions(+), 10 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.h

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index 26ef6143562b..35dfbba4767b 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -67,4 +67,7 @@ static inline int rsi_set_memory_range_shared(phys_addr_t start,
 	return rsi_set_memory_range(start, end, RSI_RIPAS_EMPTY,
 				    RSI_CHANGE_DESTROYED);
 }
+
+bool rsi_has_da_feature(void);
+
 #endif /* __ASM_RSI_H_ */
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 2c8763876dfb..d4834baeef1b 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -159,4 +159,22 @@ static inline unsigned long rsi_attestation_token_continue(phys_addr_t granule,
 	return res.a0;
 }
 
+/**
+ * rsi_features() - Read feature register
+ * @index: Feature register index
+ * @out: Feature register value is written to this pointer
+ *
+ * Return: RSI return code
+ */
+static inline int rsi_features(unsigned long index, unsigned long *out)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_FEATURES, index, &res);
+
+	if (out)
+		*out = res.a1;
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 6cb070eca9e9..8e486cdef9eb 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -53,6 +53,7 @@
  */
 #define SMC_RSI_ABI_VERSION	SMC_RSI_FID(0x190)
 
+#define RSI_FEATURE_REGISTER_0_DA		BIT(0)
 /*
  * Read feature register.
  *
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index bf9ea99e2aa1..ef06c083990a 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -15,6 +15,7 @@
 #include <asm/rsi.h>
 
 static struct realm_config config;
+static unsigned long rsi_feat_reg0;
 
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
@@ -22,6 +23,12 @@ EXPORT_SYMBOL(prot_ns_shared);
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
+bool rsi_has_da_feature(void)
+{
+	return !!u64_get_bits(rsi_feat_reg0, RSI_FEATURE_REGISTER_0_DA);
+}
+EXPORT_SYMBOL_GPL(rsi_has_da_feature);
+
 bool cc_platform_has(enum cc_attr attr)
 {
 	switch (attr) {
@@ -128,6 +135,10 @@ void __init arm64_rsi_init(void)
 		return;
 	if (WARN_ON(rsi_get_realm_config(&config)))
 		return;
+
+	if (WARN_ON(rsi_features(0, &rsi_feat_reg0)))
+		return;
+
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
@@ -141,17 +152,18 @@ void __init arm64_rsi_init(void)
 	static_branch_enable(&rsi_present);
 }
 
-static struct platform_device rsi_dev = {
+static struct platform_device cca_guest_dev = {
 	.name = RSI_DEV_NAME,
 	.id = PLATFORM_DEVID_NONE
 };
 
-static int __init arm64_create_dummy_rsi_dev(void)
+static int __init arm64_create_cca_guest_dev(void)
 {
-	if (is_realm_world() &&
-	    platform_device_register(&rsi_dev))
-		pr_err("failed to register rsi platform device\n");
+	if (is_realm_world()) {
+		if (!platform_device_register(&cca_guest_dev))
+			pr_info("CCA guest platform device registered.\n");
+	}
 	return 0;
 }
 
-arch_initcall(arm64_create_dummy_rsi_dev)
+device_initcall(arm64_create_cca_guest_dev)
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index d0a859dd9eaf..4264ee367b3b 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -7,8 +7,8 @@ obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
-obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-y				+= guest/
+obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_ARM_CCA_HOST)	+= arm-cca-host/
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index 3f0f013f03f1..410d9c3fb2b3 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -1,10 +1,16 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+
 config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
+	depends on PCI_TSM
 	select TSM_REPORTS
+	select TSM
 	help
-	  The driver provides userspace interface to request and
+	  The driver provides userspace interface to request an
 	  attestation report from the Realm Management Monitor(RMM).
+	  If the DA feature is supported, it also register with TSM framework.
 
 	  If you choose 'M' here, this module will be called
 	  arm-cca-guest.
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 547fc2c79f7d..3adbbd67e06e 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -1,6 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /*
- * Copyright (C) 2023 ARM Ltd.
+ * Copyright (C) 2025 ARM Ltd.
  */
 
 #include <linux/arm-smccc.h>
@@ -15,6 +15,8 @@
 
 #include <asm/rsi.h>
 
+#include "rsi-da.h"
+
 /**
  * struct arm_cca_token_info - a descriptor for the token buffer.
  * @challenge:		Pointer to the challenge data
@@ -192,6 +194,60 @@ static void unregister_cca_tsm_report(void *data)
 	tsm_report_unregister(&arm_cca_tsm_report_ops);
 }
 
+static struct pci_tsm *cca_tsm_pci_probe(struct pci_dev *pdev)
+{
+	struct cca_guest_dsc *cca_dsc __free(kfree);
+
+	if (!is_pci_tsm_pf0(pdev))
+		return NULL;
+
+	cca_dsc = kzalloc(sizeof(*cca_dsc), GFP_KERNEL);
+	if (!cca_dsc)
+		return NULL;
+
+	if (pci_tsm_pf0_initialize(pdev, &cca_dsc->pci))
+		return NULL;
+
+	pci_info(pdev, "Guest tsm enabled\n");
+	return &no_free_ptr(cca_dsc)->pci.tsm;
+}
+
+static void cca_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct cca_guest_dsc *cca_dsc = to_cca_guest_dsc(tsm->pdev);
+
+	pci_dbg(tsm->pdev, "tsm disabled\n");
+	kfree(cca_dsc);
+}
+
+static const struct pci_tsm_ops cca_pci_ops = {
+	.probe = cca_tsm_pci_probe,
+	.remove = cca_tsm_pci_remove,
+};
+
+static void cca_tsm_unregister(void *tsm)
+{
+	tsm_unregister(tsm);
+}
+
+static int cca_tsm_register(struct platform_device *pdev)
+{
+	struct tsm_core_dev *tsm_core;
+	int rc;
+
+	tsm_core = tsm_register(&pdev->dev, NULL, &cca_pci_ops);
+	if (IS_ERR(tsm_core))
+		return PTR_ERR(tsm_core);
+
+	rc = devm_add_action_or_reset(&pdev->dev, cca_tsm_unregister, tsm_core);
+	if (rc) {
+		cca_tsm_unregister(tsm_core);
+		return rc;
+	}
+
+	return 0;
+}
+
 static int cca_guest_probe(struct platform_device *pdev)
 {
 	int ret;
@@ -200,11 +256,22 @@ static int cca_guest_probe(struct platform_device *pdev)
 		return -ENODEV;
 
 	ret = tsm_report_register(&arm_cca_tsm_report_ops, NULL);
-	if (ret < 0)
+	if (ret < 0) {
 		pr_err("Error %d registering with TSM\n", ret);
+		goto err_out;
+	}
 
 	ret = devm_add_action_or_reset(&pdev->dev, unregister_cca_tsm_report, NULL);
+	if (ret < 0) {
+		pr_err("Error %d registering devm action\n", ret);
+		unregister_cca_tsm_report(NULL);
+		goto err_out;
+	}
+
+	if (rsi_has_da_feature())
+		ret = cca_tsm_register(pdev);
 
+err_out:
 	return ret;
 }
 
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
new file mode 100644
index 000000000000..8a4d5f1b0263
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -0,0 +1,27 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#ifndef RSI_DA_H_
+#define RSI_DA_H_
+
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
+#include <asm/rsi_smc.h>
+
+
+struct cca_guest_dsc {
+	struct pci_tsm_pf0 pci;
+};
+
+static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm)
+		return NULL;
+	return container_of(tsm, struct cca_guest_dsc, pci.tsm);
+}
+
+#endif

---

## [26] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 25/38] cca: guest: arm64: Realm device lock support*

Writing 1 to 'tsm/lock' will initiate the TDISP lock sequence.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h         | 32 +++++++++++++-
 arch/arm64/include/asm/rsi_smc.h          |  5 +++
 drivers/virt/coco/arm-cca-guest/Makefile  |  2 +-
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 18 ++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 52 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  3 +-
 6 files changed, 108 insertions(+), 4 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.c

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index d4834baeef1b..b9c4b8ff5631 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -172,8 +172,36 @@ static inline int rsi_features(unsigned long index, unsigned long *out)
 
 	arm_smccc_1_1_invoke(SMC_RSI_FEATURES, index, &res);
 
-	if (out)
-		*out = res.a1;
+	*out = res.a1;
+	return res.a0;
+}
+
+static inline unsigned long rsi_rdev_get_instance_id(unsigned long vdev_id, unsigned long *inst_id)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_GET_INSTANCE_ID, vdev_id, &res);
+
+	*inst_id = res.a1;
+	return res.a0;
+}
+
+static inline unsigned long __rsi_rdev_lock(unsigned long vdev_id, unsigned long inst_id)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_LOCK, vdev_id, inst_id, &res);
+
+	return res.a0;
+}
+
+
+static inline unsigned long rsi_rdev_continue(unsigned long vdev_id, unsigned long inst_id)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_CONTINUE, vdev_id, inst_id, &res);
+
 	return res.a0;
 }
 
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 8e486cdef9eb..44b583ab6d67 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -191,4 +191,9 @@ struct realm_config {
  */
 #define SMC_RSI_HOST_CALL			SMC_RSI_FID(0x199)
 
+#define SMC_RSI_RDEV_GET_INSTANCE_ID		SMC_RSI_FID(0x19c)
+#define SMC_RSI_RDEV_CONTINUE			SMC_RSI_FID(0x1a4)
+
+#define SMC_RSI_RDEV_LOCK			SMC_RSI_FID(0x1a9)
+
 #endif /* __ASM_RSI_SMC_H_ */
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 609462ea9438..341c7b37d610 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -2,4 +2,4 @@
 #
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
 
-arm-cca-guest-$(CONFIG_TSM) +=  arm-cca.o
+arm-cca-guest-$(CONFIG_TSM) +=  arm-cca.o rsi-da.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 3adbbd67e06e..2c0190bcb2a9 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -220,9 +220,27 @@ static void cca_tsm_pci_remove(struct pci_tsm *tsm)
 	kfree(cca_dsc);
 }
 
+static int cca_tsm_lock(struct pci_dev *pdev)
+{
+	unsigned long ret;
+
+	ret = rsi_device_lock(pdev);
+	if (ret) {
+		pci_err(pdev, "failed to lock the device (%lu)\n", ret);
+		return -EIO;
+	}
+	return 0;
+}
+
+static void cca_tsm_unlock(struct pci_dev *pdev)
+{
+}
+
 static const struct pci_tsm_ops cca_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
+	.lock = cca_tsm_lock,
+	.unlock = cca_tsm_unlock,
 };
 
 static void cca_tsm_unregister(void *tsm)
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
new file mode 100644
index 000000000000..097cf52ee199
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -0,0 +1,52 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <linux/pci.h>
+#include <asm/rsi_cmds.h>
+
+#include "rsi-da.h"
+
+#define PCI_TDISP_MESSAGE_VERSION_10	0x10
+
+static inline unsigned long rsi_rdev_lock(struct pci_dev *pdev,
+					  unsigned long vdev_id, unsigned long inst_id)
+{
+	unsigned long ret;
+
+	ret = __rsi_rdev_lock(vdev_id, inst_id);
+	if (ret != RSI_SUCCESS)
+		return ret;
+
+	do {
+		ret = rsi_rdev_continue(vdev_id, inst_id);
+	} while (ret == RSI_INCOMPLETE);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to communicate with the device (%lu)\n", ret);
+		return ret;
+	}
+	return RSI_SUCCESS;
+}
+
+int rsi_device_lock(struct pci_dev *pdev)
+{
+	unsigned long ret;
+	struct cca_guest_dsc *dsm = to_cca_guest_dsc(pdev);
+	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
+		PCI_DEVID(pdev->bus->number, pdev->devfn);
+
+	ret = rsi_rdev_get_instance_id(vdev_id, &dsm->instance_id);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to get the device instance id (%lu)\n", ret);
+		return -EIO;
+	}
+
+	ret = rsi_rdev_lock(pdev, vdev_id, dsm->instance_id);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to lock the device (%lu)\n", ret);
+		return -EIO;
+	}
+
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 8a4d5f1b0263..f12430c7d792 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -10,9 +10,9 @@
 #include <linux/pci-tsm.h>
 #include <asm/rsi_smc.h>
 
-
 struct cca_guest_dsc {
 	struct pci_tsm_pf0 pci;
+	unsigned long instance_id;
 };
 
 static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
@@ -24,4 +24,5 @@ static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_guest_dsc, pci.tsm);
 }
 
+int rsi_device_lock(struct pci_dev *pdev);
 #endif

---

## [27] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 26/38] KVM: arm64: Add exit handler related to device assignment*

Different RSI calls related to DA result in REC exits. Add a facility to
register handlers for handling these REC exits.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/kvm_rme.h |  3 ++
 arch/arm64/include/asm/rmi_smc.h | 14 +++++++-
 arch/arm64/kvm/rme-exit.c        | 60 ++++++++++++++++++++++++++++++++
 3 files changed, 76 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index e954bb95dc86..370d056222e8 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -136,4 +136,7 @@ static inline bool kvm_realm_is_private_address(struct realm *realm,
 	return !(addr & BIT(realm->ia_bits - 1));
 }
 
+extern int (*realm_exit_vdev_req_handler)(struct realm_rec *rec);
+extern int (*realm_exit_vdev_comm_handler)(struct realm_rec *rec);
+extern int (*realm_exit_dev_mem_map_handler)(struct realm_rec *rec);
 #endif /* __ASM_KVM_RME_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index c6e16ab608e1..a5ef68b62bc0 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -219,6 +219,9 @@ struct rec_enter {
 #define RMI_EXIT_RIPAS_CHANGE		0x04
 #define RMI_EXIT_HOST_CALL		0x05
 #define RMI_EXIT_SERROR			0x06
+#define RMI_EXIT_VDEV_REQUEST		0x08
+#define RMI_EXIT_VDEV_COMM		0x09
+#define RMI_EXIT_DEV_MEM_MAP		0x0a
 
 struct rec_exit {
 	union { /* 0x000 */
@@ -264,7 +267,16 @@ struct rec_exit {
 		u8 padding5[0x100];
 	};
 	union { /* 0x600 */
-		u16 imm;
+		struct {
+			u16 imm;
+			u8 padding[6];
+			u64 plane;
+			u64 vdev;
+			u64 vdev_action;
+			u64 dev_mem_base;
+			u64 dev_mem_top;
+			u64 dev_mem_pa;
+		};
 		u8 padding6[0x100];
 	};
 	union { /* 0x700 */
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index 1a8ca7526863..25948207fc5b 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
@@ -129,6 +129,60 @@ static int rec_exit_host_call(struct kvm_vcpu *vcpu)
 	return kvm_smccc_call_handler(vcpu);
 }
 
+int (*realm_exit_vdev_req_handler)(struct realm_rec *rec);
+EXPORT_SYMBOL_GPL(realm_exit_vdev_req_handler);
+static int rec_exit_vdev_request(struct kvm_vcpu *vcpu)
+{
+	int ret;
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	if (realm_exit_vdev_req_handler) {
+		ret = (*realm_exit_vdev_req_handler)(rec);
+	} else {
+		kvm_pr_unimpl("Unsupported exit reason: %u\n",
+			      rec->run->exit.exit_reason);
+		vcpu->run->exit_reason = KVM_EXIT_INTERNAL_ERROR;
+		ret = 0;
+	}
+	return ret;
+}
+
+int (*realm_exit_vdev_comm_handler)(struct realm_rec *rec);
+EXPORT_SYMBOL_GPL(realm_exit_vdev_comm_handler);
+static int rec_exit_vdev_communication(struct kvm_vcpu *vcpu)
+{
+	int ret;
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	if (realm_exit_vdev_comm_handler) {
+		ret = (*realm_exit_vdev_comm_handler)(rec);
+	} else {
+		kvm_pr_unimpl("Unsupported exit reason: %u\n",
+			      rec->run->exit.exit_reason);
+		vcpu->run->exit_reason = KVM_EXIT_INTERNAL_ERROR;
+		ret = 0;
+	}
+	return ret;
+}
+
+int (*realm_exit_dev_mem_map_handler)(struct realm_rec *rec);
+EXPORT_SYMBOL_GPL(realm_exit_dev_mem_map_handler);
+static int rec_exit_dev_mem_map(struct kvm_vcpu *vcpu)
+{
+	int ret;
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	if (realm_exit_dev_mem_map_handler) {
+		ret = (*realm_exit_dev_mem_map_handler)(rec);
+	} else {
+		kvm_pr_unimpl("Unsupported exit reason: %u\n",
+			      rec->run->exit.exit_reason);
+		vcpu->run->exit_reason = KVM_EXIT_INTERNAL_ERROR;
+		ret = 0;
+	}
+	return ret;
+}
+
 static void update_arch_timer_irq_lines(struct kvm_vcpu *vcpu)
 {
 	struct realm_rec *rec = &vcpu->arch.rec;
@@ -198,6 +252,12 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_ripas_change(vcpu);
 	case RMI_EXIT_HOST_CALL:
 		return rec_exit_host_call(vcpu);
+	case RMI_EXIT_VDEV_REQUEST:
+		return rec_exit_vdev_request(vcpu);
+	case RMI_EXIT_VDEV_COMM:
+		return rec_exit_vdev_communication(vcpu);
+	case RMI_EXIT_DEV_MEM_MAP:
+		return rec_exit_dev_mem_map(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",

---

## [28] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 27/38] coco: host: arm64: add RSI_RDEV_GET_INSTANCE_ID related exit handler*

Mapping the VDEV object that matches a specified virtual device ID
results in a REC exit, which is handled by the VDEV request exit
handler.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  8 +++++
 arch/arm64/include/asm/rmi_smc.h         |  9 ++++--
 drivers/virt/coco/arm-cca-host/arm-cca.c |  8 ++++-
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 39 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  |  2 ++
 5 files changed, 63 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index eb4f67eb6b01..fcf6b319e953 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -629,5 +629,13 @@ static inline unsigned long rmi_vdev_destroy(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_complete(unsigned long rec_phys, unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_COMPLETE, rec_phys, vdev_phys, &res);
+
+	return res.a0;
+}
 
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index a5ef68b62bc0..6b23afa070d1 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -57,7 +57,8 @@
 #define SMC_RMI_VDEV_CREATE		SMC_RMI_CALL(0x0187)
 #define SMC_RMI_VDEV_DESTROY		SMC_RMI_CALL(0x0188)
 #define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
-#define SMC_RMI_VDEV_STOP		SMC_RMI_CALL(0x018A)
+#define SMC_RMI_VDEV_STOP		SMC_RMI_CALL(0x018a)
+#define SMC_RMI_VDEV_COMPLETE		SMC_RMI_CALL(0x018e)
 
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
@@ -262,7 +263,11 @@ struct rec_exit {
 		struct {
 			u64 ripas_base;
 			u64 ripas_top;
-			u64 ripas_value;
+			u8 ripas_value;
+			u8 padding8[15];
+			u64 s2ap_base;
+			u64 s2ap_top;
+			u64 vdev_id;
 		};
 		u8 padding5[0x100];
 	};
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 3792d7b5cb99..837bd10ccd47 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -275,13 +275,19 @@ static void cca_tsm_remove(void *tsm_core)
 
 static int cca_tsm_probe(struct platform_device *pdev)
 {
+	int rc;
 	struct tsm_core_dev *tsm_core;
 
 	tsm_core = tsm_register(&pdev->dev, NULL, &cca_pci_ops);
 	if (IS_ERR(tsm_core))
 		return PTR_ERR(tsm_core);
 
-	return devm_add_action_or_reset(&pdev->dev, cca_tsm_remove, tsm_core);
+	rc = devm_add_action_or_reset(&pdev->dev, cca_tsm_remove, tsm_core);
+	if (rc)
+		return rc;
+
+	rme_register_exit_handlers();
+	return 0;
 }
 
 static const struct platform_device_id arm_cca_host_id_table[] = {
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index 53072610fa67..d4f1da590b90 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -660,3 +660,42 @@ void rme_unbind_vdev(struct realm *realm, struct pci_dev *pdev, struct pci_dev *
 		return;
 	}
 }
+
+static struct pci_tsm *find_pci_tsm_from_vdev_id(unsigned long vdev_id)
+{
+	struct pci_dev *pdev = NULL;
+	struct cca_host_tdi *host_tdi;
+
+	for_each_pci_dev(pdev) {
+		host_tdi = to_cca_host_tdi(pdev);
+		if (!host_tdi)
+			continue;
+		if (host_tdi->vdev_id == vdev_id)
+			return pdev->tsm;
+	}
+	return NULL;
+}
+
+static int rme_exit_vdev_req_handler(struct realm_rec *rec)
+{
+	struct cca_host_tdi *host_tdi = NULL;
+	unsigned long vdev_id = rec->run->exit.vdev_id;
+	struct pci_tsm *tsm = find_pci_tsm_from_vdev_id(vdev_id);
+	phys_addr_t rec_phys = virt_to_phys(rec->rec_page);
+
+	if (tsm)
+		host_tdi = to_cca_host_tdi(tsm->pdev);
+
+	if (host_tdi)
+		rmi_vdev_complete(rec_phys, virt_to_phys(host_tdi->rmm_vdev));
+	/*
+	 * Return back to the guest without calling vdev complete.
+	 * The Realm will treat that as an error.
+	 */
+	return 1;
+}
+
+void rme_register_exit_handlers(void)
+{
+	realm_exit_vdev_req_handler = rme_exit_vdev_req_handler;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index 6361f7403f95..7f51b611467b 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -48,6 +48,7 @@ struct cca_host_dsc_pf0 {
 struct cca_host_tdi {
 	struct pci_tdi tdi;
 	void *rmm_vdev;
+	unsigned long vdev_id;
 };
 
 #define PDEV_COMMUNICATE	0x1
@@ -95,4 +96,5 @@ void *rme_create_vdev(struct realm *realm, struct pci_dev *pdev,
 		      struct pci_dev *pf0_dev, u32 guest_rid);
 void rme_unbind_vdev(struct realm *realm, struct pci_dev *pdev,
 		     struct pci_dev *pf0_dev);
+void rme_register_exit_handlers(void);
 #endif

---

## [29] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 28/38] coco: host: arm64: Add support for device communication exit handler*

Different RSI calls that require device communication result in a REC
exit, which is handled by the device communication exit handler.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h         |  6 ++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  1 +
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 75 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  |  4 ++
 4 files changed, 86 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 6b23afa070d1..7073eccaec5f 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -457,4 +457,10 @@ struct rmi_vdev_params {
 	};
 };
 
+#define RMI_VDEV_ACTION_GET_INTERFACE_REPORT	0x0
+#define RMI_VDEV_ACTION_GET_MEASUREMENTS	0x1
+#define RMI_VDEV_ACTION_LOCK			0x2
+#define RMI_VDEV_ACTION_START			0x3
+#define RMI_VDEV_ACTION_STOP			0x4
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 837bd10ccd47..be1296fb1bf2 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -243,6 +243,7 @@ static struct pci_tdi *cca_tsm_bind(struct pci_dev *pdev, struct pci_dev *pf0_de
 	rmm_vdev = rme_create_vdev(realm, pdev, pf0_dev, tdi_id);
 	if (!IS_ERR_OR_NULL(rmm_vdev)) {
 		host_tdi->rmm_vdev = rmm_vdev;
+		host_tdi->vdev_id = tdi_id;
 		return &no_free_ptr(host_tdi)->tdi;
 	}
 
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index d4f1da590b90..bef33e618fd3 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -233,6 +233,16 @@ static int __do_dev_communicate(int type, struct pci_tsm *tsm)
 			cache_offset = &dsc_pf0->cert_chain.cache.size;
 			cache_remaining = sizeof(dsc_pf0->cert_chain.cache.buf) - *cache_offset;
 			break;
+		case RMI_DEV_INTERFACE_REPORT:
+			cache_buf = dsc_pf0->interface_report.buf;
+			cache_offset = &dsc_pf0->interface_report.size;
+			cache_remaining = sizeof(dsc_pf0->interface_report.buf) - *cache_offset;
+			break;
+		case RMI_DEV_MEASUREMENTS:
+			cache_buf = dsc_pf0->measurements.buf;
+			cache_offset = &dsc_pf0->measurements.size;
+			cache_remaining = sizeof(dsc_pf0->measurements.buf) - *cache_offset;
+			break;
 		default:
 			/* FIXME!! depending on the DevComms status,
 			 * it might require to ABORT the communcation.
@@ -661,6 +671,21 @@ void rme_unbind_vdev(struct realm *realm, struct pci_dev *pdev, struct pci_dev *
 	}
 }
 
+static struct pci_tsm *find_pci_tsm_from_vdev(phys_addr_t vdev_phys)
+{
+	struct pci_dev *pdev = NULL;
+	struct cca_host_tdi *host_tdi;
+
+	for_each_pci_dev(pdev) {
+		host_tdi = to_cca_host_tdi(pdev);
+		if (!host_tdi)
+			continue;
+		if (virt_to_phys(host_tdi->rmm_vdev) == vdev_phys)
+			return pdev->tsm;
+	}
+	return NULL;
+}
+
 static struct pci_tsm *find_pci_tsm_from_vdev_id(unsigned long vdev_id)
 {
 	struct pci_dev *pdev = NULL;
@@ -676,6 +701,55 @@ static struct pci_tsm *find_pci_tsm_from_vdev_id(unsigned long vdev_id)
 	return NULL;
 }
 
+static int rme_exit_vdev_comm_handler(struct realm_rec *rec)
+{
+	int ret;
+	unsigned long state;
+	struct cca_host_tdi *host_tdi;
+	struct cca_host_comm_data *comm_data;
+	phys_addr_t vdev_phys = rec->run->exit.vdev;
+	struct pci_tsm *tsm = find_pci_tsm_from_vdev(vdev_phys);
+
+	if (!tsm)
+		goto err_out;
+
+	host_tdi = to_cca_host_tdi(tsm->pdev);
+	if (!host_tdi)
+		goto err_out;
+
+	comm_data = to_cca_comm_data(tsm->pdev);
+	if (!comm_data->vdev_comm_active) {
+		struct rmi_dev_comm_enter *io_enter;
+
+		io_enter = &comm_data->io_params->enter;
+		io_enter->resp_len = 0;
+		io_enter->status = RMI_DEV_COMM_NONE;
+		comm_data->vdev_comm_active = true;
+	}
+
+	/* FIXME!! Should this be a work? */
+	ret = __do_dev_communicate(VDEV_COMMUNICATE, tsm);
+	if (ret)
+		goto err_out;
+
+	ret = rmi_vdev_get_state(virt_to_phys(host_tdi->rmm_vdev), &state);
+	if (ret)
+		goto err_out;
+	/*
+	 * If vdev is done communicating, the next update should
+	 * reinitialize the cache
+	 */
+	if (state != RMI_VDEV_COMMUNICATING)
+		comm_data->vdev_comm_active = false;
+
+err_out:
+	/*
+	 * Return back to the guest without calling DEV communicate.
+	 * The Realm will treat that as an error.
+	 */
+	return 1;
+}
+
 static int rme_exit_vdev_req_handler(struct realm_rec *rec)
 {
 	struct cca_host_tdi *host_tdi = NULL;
@@ -697,5 +771,6 @@ static int rme_exit_vdev_req_handler(struct realm_rec *rec)
 
 void rme_register_exit_handlers(void)
 {
+	realm_exit_vdev_comm_handler = rme_exit_vdev_comm_handler;
 	realm_exit_vdev_req_handler = rme_exit_vdev_req_handler;
 }
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index 7f51b611467b..cebddab8464d 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -22,6 +22,8 @@ struct cca_host_comm_data {
 	void *resp_buff;
 	void *req_buff;
 	struct rmi_dev_comm_data *io_params;
+
+	bool vdev_comm_active;
 };
 
 struct cca_host_dsc_pf0 {
@@ -43,6 +45,8 @@ struct cca_host_dsc_pf0 {
 		bool valid;
 	} cert_chain;
 	struct cache_object vca;
+	struct cache_object interface_report;
+	struct cache_object measurements;
 };
 
 struct cca_host_tdi {

---

## [30] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 29/38] coco: guest: arm64: Add support for collecting interface reports*

Support collecting interface reports using RSI calls.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h        | 14 ++++++++++
 arch/arm64/include/asm/rsi_smc.h         |  2 ++
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 34 ++++++++++++++++++++++++
 3 files changed, 50 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index b9c4b8ff5631..1d76f7d37cb6 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -205,4 +205,18 @@ static inline unsigned long rsi_rdev_continue(unsigned long vdev_id, unsigned lo
 	return res.a0;
 }
 
+static inline unsigned long __rsi_rdev_get_interface_report(unsigned long vdev_id,
+							  unsigned long inst_id,
+							  unsigned long version_max,
+							  unsigned long *version)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_GET_INTERFACE_REPORT,
+			     vdev_id, inst_id, version_max, &res);
+
+	*version = res.a1;
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 44b583ab6d67..6afcccee2ae7 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -194,6 +194,8 @@ struct realm_config {
 #define SMC_RSI_RDEV_GET_INSTANCE_ID		SMC_RSI_FID(0x19c)
 #define SMC_RSI_RDEV_CONTINUE			SMC_RSI_FID(0x1a4)
 
+#define SMC_RSI_RDEV_GET_INTERFACE_REPORT	SMC_RSI_FID(0x1a6)
+
 #define SMC_RSI_RDEV_LOCK			SMC_RSI_FID(0x1a9)
 
 #endif /* __ASM_RSI_SMC_H_ */
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 097cf52ee199..28ec946df1e2 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -29,9 +29,31 @@ static inline unsigned long rsi_rdev_lock(struct pci_dev *pdev,
 	return RSI_SUCCESS;
 }
 
+static inline unsigned long
+rsi_rdev_get_interface_report(struct pci_dev *pdev, unsigned long vdev_id,
+			      unsigned long inst_id, unsigned long version_max,
+			      unsigned long *version)
+{
+	unsigned long ret;
+
+	ret = __rsi_rdev_get_interface_report(vdev_id, inst_id, version_max, version);
+	if (ret != RSI_SUCCESS)
+		return ret;
+
+	do {
+		ret = rsi_rdev_continue(vdev_id, inst_id);
+	} while (ret == RSI_INCOMPLETE);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to communicate with the device (%lu)\n", ret);
+		return ret;
+	}
+	return RSI_SUCCESS;
+}
+
 int rsi_device_lock(struct pci_dev *pdev)
 {
 	unsigned long ret;
+	unsigned long tdisp_version;
 	struct cca_guest_dsc *dsm = to_cca_guest_dsc(pdev);
 	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
 		PCI_DEVID(pdev->bus->number, pdev->devfn);
@@ -48,5 +70,17 @@ int rsi_device_lock(struct pci_dev *pdev)
 		return -EIO;
 	}
 
+	ret = rsi_rdev_get_interface_report(pdev, vdev_id, dsm->instance_id,
+					   PCI_TDISP_MESSAGE_VERSION_10, &tdisp_version);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to get interface report (%lu)\n", ret);
+		return -EIO;
+	}
+
+	if (tdisp_version != PCI_TDISP_MESSAGE_VERSION_10) {
+		pci_err(pdev, "unknown TDISP version (%lu)\n", tdisp_version);
+		return -EOPNOTSUPP;
+	}
+
 	return ret;
 }

---

## [31] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 30/38] coco: host: arm64: Add support for realm host interface (RHI)*

Device assignment-related RHI calls result in a REC exit, which is
handled by the tsm guest_request callback.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             | 32 ++++++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 68 ++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.c  | 81 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmm-da.h  |  4 ++
 include/linux/tsm.h                      |  3 +
 5 files changed, 188 insertions(+)
 create mode 100644 arch/arm64/include/asm/rhi.h

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
new file mode 100644
index 000000000000..d3c22e582678
--- /dev/null
+++ b/arch/arm64/include/asm/rhi.h
@@ -0,0 +1,32 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2024 ARM Ltd.
+ */
+
+#ifndef __ASM_RHI_H_
+#define __ASM_RHI_H_
+
+#define SMC_RHI_CALL(func)				\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
+			   ARM_SMCCC_SMC_64,		\
+			   ARM_SMCCC_OWNER_STANDARD_HYP,\
+			   (func))
+
+
+#define RHI_DA_FEATURES			SMC_RHI_CALL(0x004d)
+#define RHI_DA_OBJECT_SIZE		SMC_RHI_CALL(0x004e)
+#define RHI_DA_OBJECT_READ		SMC_RHI_CALL(0x004f)
+
+#define RHI_DA_OBJECT_CERTIFICATE		0x1
+#define RHI_DA_OBJECT_MEASUREMENT		0x2
+#define RHI_DA_OBJECT_INTERFACE_REPORT		0x3
+#define RHI_DA_OBJECT_VCA			0x4
+
+
+#define RHI_DA_SUCCESS				0x1
+#define RHI_ERROR_INVALID_VDEV_ID		0x2
+#define RHI_ERROR_INVALID_DA_OBJECT_TYPE	0x3
+#define RHI_ERROR_DATA_NOT_AVAILABLE		0x4
+#define RHI_ERROR_INVALID_OFFSET		0x5
+#define RHI_ERROR_INVALID_ADDR			0x6
+#endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index be1296fb1bf2..0807fcf8d222 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -260,6 +260,73 @@ static void cca_tsm_unbind(struct pci_tdi *tdi)
 	module_put(THIS_MODULE);
 }
 
+struct da_object_size_req {
+	int object_type;
+};
+
+struct da_object_read_req {
+	int object_type;
+	unsigned long offset;
+};
+
+static int cca_tsm_guest_req(struct pci_dev *pdev, struct tsm_guest_req_info *info)
+{
+	int ret;
+
+	switch (info->type) {
+	case ARM_CCA_DA_OBJECT_SIZE:
+	{
+		int object_size;
+		struct da_object_size_req req;
+
+		if (sizeof(req) != info->req_len)
+			return -EINVAL;
+
+		if (copy_from_user(&req, info->req, info->req_len))
+			return -EFAULT;
+
+		object_size = rme_get_da_object_size(pdev, req.object_type);
+		if (object_size > 0) {
+			if (info->resp_len < sizeof(object_size))
+				return -EINVAL;
+			if (copy_to_user(info->resp, &object_size, sizeof(object_size)))
+				return -EFAULT;
+			info->resp_len = sizeof(object_size);
+			ret = 0;
+		} else
+			/* error */
+			ret = object_size;
+		break;
+	}
+	case ARM_CCA_DA_OBJECT_READ:
+	{
+		int resp_len;
+		struct da_object_read_req req;
+
+		if (sizeof(req) != info->req_len)
+			return -EINVAL;
+
+		if (copy_from_user(&req, info->req, info->req_len))
+			return -EFAULT;
+
+		resp_len = rme_da_object_read(pdev, req.object_type, req.offset,
+					      info->resp_len,
+					      info->resp);
+		if (resp_len > 0) {
+			info->resp_len = resp_len;
+			ret = 0;
+		} else
+			/* error */
+			ret = resp_len;
+		break;
+	}
+	default:
+		ret = -EINVAL;
+		break;
+	}
+	return ret;
+}
+
 static const struct pci_tsm_ops cca_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
@@ -267,6 +334,7 @@ static const struct pci_tsm_ops cca_pci_ops = {
 	.disconnect = cca_tsm_disconnect,
 	.bind	= cca_tsm_bind,
 	.unbind = cca_tsm_unbind,
+	.guest_req = cca_tsm_guest_req,
 };
 
 static void cca_tsm_remove(void *tsm_core)
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
index bef33e618fd3..c7da9d12f258 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
@@ -10,7 +10,9 @@
 #include <keys/asymmetric-type.h>
 #include <keys/x509-parser.h>
 #include <linux/kvm_types.h>
+#include <linux/kvm_host.h>
 #include <asm/kvm_rme.h>
+#include <asm/kvm_emulate.h>
 
 #include "rmm-da.h"
 
@@ -769,6 +771,85 @@ static int rme_exit_vdev_req_handler(struct realm_rec *rec)
 	return 1;
 }
 
+int rme_get_da_object_size(struct pci_dev *pdev, int type)
+{
+	int ret = 0;
+	unsigned long len;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+
+	if (!tsm)
+		return -EINVAL;
+
+	dsc_pf0 = to_cca_dsc_pf0(tsm->dsm_dev);
+
+	/* Determine the buffer that should be used */
+	if (type == RHI_DA_OBJECT_INTERFACE_REPORT) {
+		len = dsc_pf0->interface_report.size;
+	} else if (type == RHI_DA_OBJECT_MEASUREMENT) {
+		len = dsc_pf0->measurements.size;
+	} else if (type == RHI_DA_OBJECT_CERTIFICATE) {
+		len = dsc_pf0->cert_chain.cache.size;
+	} else if (type == RHI_DA_OBJECT_VCA) {
+		len = dsc_pf0->vca.size;
+	} else {
+		ret = -EINVAL;
+		goto err_out;
+	}
+
+	return len;
+err_out:
+	return ret;
+}
+
+int rme_da_object_read(struct pci_dev *pdev, int type, unsigned long offset,
+		       unsigned long max_len, void __user *user_buf)
+{
+	void *buf;
+	int ret = 0;
+	unsigned long len;
+	struct cca_host_dsc_pf0 *dsc_pf0;
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm)
+		return -EINVAL;
+
+	dsc_pf0 = to_cca_dsc_pf0(tsm->dsm_dev);
+
+	/* Determine the buffer that should be used */
+	if (type == RHI_DA_OBJECT_INTERFACE_REPORT) {
+		len = dsc_pf0->interface_report.size;
+		buf = dsc_pf0->interface_report.buf;
+	} else if (type == RHI_DA_OBJECT_MEASUREMENT) {
+		len = dsc_pf0->measurements.size;
+		buf = dsc_pf0->measurements.buf;
+	} else if (type == RHI_DA_OBJECT_CERTIFICATE) {
+		len = dsc_pf0->cert_chain.cache.size;
+		buf = dsc_pf0->cert_chain.cache.buf;
+	} else if (type == RHI_DA_OBJECT_VCA) {
+		len = dsc_pf0->vca.size;
+		buf = dsc_pf0->vca.buf;
+	} else {
+		ret = -EINVAL;
+		goto err_out;
+	}
+
+	/* Assume that the buffer is large enough for the whole report */
+	if ((max_len - offset) < len) {
+		/* FIXME!! the error code */
+		ret = -ENOMEM;
+		goto err_out;
+	}
+
+	if (copy_to_user(user_buf + offset, buf, len)) {
+		ret = -EIO;
+		goto err_out;
+	}
+	ret = len;
+err_out:
+	return ret;
+}
+
 void rme_register_exit_handlers(void)
 {
 	realm_exit_vdev_comm_handler = rme_exit_vdev_comm_handler;
diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.h b/drivers/virt/coco/arm-cca-host/rmm-da.h
index cebddab8464d..457660ff3b69 100644
--- a/drivers/virt/coco/arm-cca-host/rmm-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmm-da.h
@@ -10,6 +10,7 @@
 #include <linux/pci-ide.h>
 #include <linux/pci-tsm.h>
 #include <asm/rmi_smc.h>
+#include <asm/rhi.h>
 
 #define MAX_CACHE_OBJ_SIZE	4096
 struct cache_object {
@@ -101,4 +102,7 @@ void *rme_create_vdev(struct realm *realm, struct pci_dev *pdev,
 void rme_unbind_vdev(struct realm *realm, struct pci_dev *pdev,
 		     struct pci_dev *pf0_dev);
 void rme_register_exit_handlers(void);
+int rme_get_da_object_size(struct pci_dev *pdev, int type);
+int rme_da_object_read(struct pci_dev *pdev, int type, unsigned long offset,
+		       unsigned long max_len, void __user *user_buf);
 #endif
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 497a3b4df5a0..e82046b0c7fa 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -145,5 +145,8 @@ struct tsm_guest_req_info {
 	size_t resp_len;
 };
 
+#define ARM_CCA_DA_OBJECT_SIZE 0x1
+#define ARM_CCA_DA_OBJECT_READ 0x2
+
 int tsm_guest_req(struct device *dev, struct tsm_guest_req_info *info);
 #endif /* __TSM_H */

---

## [32] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 31/38] coco: guest: arm64: Add support for fetching interface report and certificate chain from host*

Fetch interface report and certificate chain from the host using RHI calls.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h        |   9 ++
 arch/arm64/include/asm/rsi_smc.h         |   6 ++
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 131 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h |   5 +
 4 files changed, 151 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 1d76f7d37cb6..18fc4e1ce577 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -219,4 +219,13 @@ static inline unsigned long __rsi_rdev_get_interface_report(unsigned long vdev_i
 	return res.a0;
 }
 
+static inline unsigned long rsi_host_call(phys_addr_t addr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_HOST_CALL, addr, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 6afcccee2ae7..1d762fe3777b 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -183,6 +183,12 @@ struct realm_config {
  */
 #define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
 
+struct rsi_host_call {
+	u16 imm;
+	u8 padding[6];
+	u64 gprs[31];
+};
+
 /*
  * Make a Host call.
  *
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 28ec946df1e2..47b379318e7c 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -4,6 +4,7 @@
  */
 
 #include <linux/pci.h>
+#include <linux/mem_encrypt.h>
 #include <asm/rsi_cmds.h>
 
 #include "rsi-da.h"
@@ -50,6 +51,121 @@ rsi_rdev_get_interface_report(struct pci_dev *pdev, unsigned long vdev_id,
 	return RSI_SUCCESS;
 }
 
+static long rhi_get_report(int vdev_id, int da_object_type, void **report, int *report_size)
+{
+	int ret, enc_ret = 0;
+	int nr_pages;
+	int max_data_len;
+	void *data_buf_shared, *data_buf_private;
+	struct rsi_host_call *rhicall;
+
+	rhicall = kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhicall)
+		return -ENOMEM;
+
+	rhicall->imm = 0;
+	rhicall->gprs[0] = RHI_DA_FEATURES;
+
+	ret = rsi_host_call(virt_to_phys(rhicall));
+	if (ret != RSI_SUCCESS) {
+		ret =  -EIO;
+		goto err_out;
+	}
+
+	if (rhicall->gprs[0] != 0x3) {
+		ret =  -EIO;
+		goto err_out;
+	}
+
+	rhicall->imm = 0;
+	rhicall->gprs[0] = RHI_DA_OBJECT_SIZE;
+	rhicall->gprs[1] = vdev_id;
+	rhicall->gprs[2] = da_object_type;
+
+	ret = rsi_host_call(virt_to_phys(rhicall));
+	if (ret != RSI_SUCCESS) {
+		ret =  -EIO;
+		goto err_out;
+	}
+	if (rhicall->gprs[0] != RHI_DA_SUCCESS) {
+		ret =  -EIO;
+		goto err_out;
+	}
+	max_data_len = rhicall->gprs[1];
+	*report_size = max_data_len;
+
+	/*
+	 * We need to share this memory with hypervisor.
+	 * So it should be multiple of sharing unit.
+	 */
+	max_data_len = ALIGN(max_data_len, PAGE_SIZE);
+	nr_pages = max_data_len >> PAGE_SHIFT;
+
+	if (!max_data_len || nr_pages > MAX_ORDER_NR_PAGES) {
+		ret = -ENOMEM;
+		goto err_out;
+	}
+
+	/*
+	 * We need to share this memory with hypervisor.
+	 * So it should be multiple of sharing unit.
+	 */
+	data_buf_shared = (void *)__get_free_pages(GFP_KERNEL, get_order(max_data_len));
+	if (!data_buf_shared) {
+		ret =  -ENOMEM;
+		goto err_out;
+	}
+
+	data_buf_private = kmalloc(*report_size, GFP_KERNEL);
+	if (!data_buf_private) {
+		ret =  -ENOMEM;
+		goto err_private_alloc;
+	}
+
+	ret = set_memory_decrypted((unsigned long)data_buf_shared, nr_pages);
+	if (ret) {
+		ret =  -EIO;
+		goto err_decrypt;
+	}
+
+	rhicall->imm = 0;
+	rhicall->gprs[0] = RHI_DA_OBJECT_READ;
+	rhicall->gprs[1] = vdev_id;
+	rhicall->gprs[2] = da_object_type;
+	rhicall->gprs[3] = 0; /* offset within the data buffer */
+	rhicall->gprs[4] = max_data_len;
+	rhicall->gprs[5] = virt_to_phys(data_buf_shared);
+	ret = rsi_host_call(virt_to_phys(rhicall));
+	if (ret != RSI_SUCCESS || rhicall->gprs[0] != RHI_DA_SUCCESS) {
+		ret =  -EIO;
+		goto err_rhi_call;
+	}
+
+	memcpy(data_buf_private, data_buf_shared, *report_size);
+	enc_ret = set_memory_encrypted((unsigned long)data_buf_shared, nr_pages);
+	if (!enc_ret)
+		/* If we fail to mark it encrypted don't free it back */
+		free_pages((unsigned long)data_buf_shared, get_order(max_data_len));
+
+	*report = data_buf_private;
+	kfree(rhicall);
+	return 0;
+
+err_rhi_call:
+	enc_ret = set_memory_encrypted((unsigned long)data_buf_shared, nr_pages);
+err_decrypt:
+	kfree(data_buf_private);
+err_private_alloc:
+	if (!enc_ret)
+		/* If we fail to mark it encrypted don't free it back */
+		free_pages((unsigned long)data_buf_shared, get_order(max_data_len));
+err_out:
+	*report = NULL;
+	*report_size = 0;
+	kfree(rhicall);
+	return ret;
+}
+
 int rsi_device_lock(struct pci_dev *pdev)
 {
 	unsigned long ret;
@@ -82,5 +198,20 @@ int rsi_device_lock(struct pci_dev *pdev)
 		return -EOPNOTSUPP;
 	}
 
+	/* Now make a host call to copy the interface report to guest. */
+	ret = rhi_get_report(vdev_id, RHI_DA_OBJECT_INTERFACE_REPORT,
+			     &dsm->interface_report, &dsm->interface_report_size);
+	if (ret) {
+		pci_err(pdev, "failed to get interface report from the host (%lu)\n", ret);
+		return -EIO;
+	}
+
+	ret = rhi_get_report(vdev_id, RHI_DA_OBJECT_CERTIFICATE,
+			     &dsm->certificate, &dsm->certificate_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device certificate from the host (%lu)\n", ret);
+		return -EIO;
+	}
+
 	return ret;
 }
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index f12430c7d792..bd565785ff4b 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -9,10 +9,15 @@
 #include <linux/pci.h>
 #include <linux/pci-tsm.h>
 #include <asm/rsi_smc.h>
+#include <asm/rhi.h>
 
 struct cca_guest_dsc {
 	struct pci_tsm_pf0 pci;
 	unsigned long instance_id;
+	void *interface_report;
+	int interface_report_size;
+	void *certificate;
+	int certificate_size;
 };
 
 static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)

---

## [33] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 32/38] coco: guest: arm64: Add support for guest initiated TDI bind/unbind*

Add RHI for VDEV_SET_TDI_STATE

Note: This is not part of RHI spec. This is a POC implementation
and will be later switced to correct interface defined by RHI.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h              |  7 +++++
 arch/arm64/kernel/Makefile                |  2 +-
 arch/arm64/kernel/rhi.c                   | 35 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 22 ++++++++++++--
 drivers/virt/coco/arm-cca-host/arm-cca.c  |  8 ++++--
 5 files changed, 69 insertions(+), 5 deletions(-)
 create mode 100644 arch/arm64/kernel/rhi.c

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index d3c22e582678..993b4b15b057 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -16,6 +16,7 @@
 #define RHI_DA_FEATURES			SMC_RHI_CALL(0x004d)
 #define RHI_DA_OBJECT_SIZE		SMC_RHI_CALL(0x004e)
 #define RHI_DA_OBJECT_READ		SMC_RHI_CALL(0x004f)
+#define RHI_DA_VDEV_SET_TDI_STATE	SMC_RHI_CALL(0x0052)
 
 #define RHI_DA_OBJECT_CERTIFICATE		0x1
 #define RHI_DA_OBJECT_MEASUREMENT		0x2
@@ -29,4 +30,10 @@
 #define RHI_ERROR_DATA_NOT_AVAILABLE		0x4
 #define RHI_ERROR_INVALID_OFFSET		0x5
 #define RHI_ERROR_INVALID_ADDR			0x6
+
+#define RHI_DA_TDI_CONFIG_UNLOCKED		0x0
+#define RHI_DA_TDI_CONFIG_LOCKED		0x1
+#define RHI_DA_TDI_CONFIG_RUN			0x2
+long rhi_da_vdev_set_tdi_state(unsigned long vdev_id, unsigned long target_state);
+
 #endif
diff --git a/arch/arm64/kernel/Makefile b/arch/arm64/kernel/Makefile
index a2faf0049dab..dde8fa78852c 100644
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
index 000000000000..3685b50c2e94
--- /dev/null
+++ b/arch/arm64/kernel/rhi.c
@@ -0,0 +1,35 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <asm/memory.h>
+#include <asm/string.h>
+#include <asm/rsi.h>
+#include <asm/rhi.h>
+
+#include <linux/slab.h>
+
+long rhi_da_vdev_set_tdi_state(unsigned long guest_rid, unsigned long target_state)
+{
+	long ret;
+	struct rsi_host_call *rhi_call;
+
+	rhi_call = kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_SET_TDI_STATE;
+	rhi_call->gprs[1] = guest_rid;
+	rhi_call->gprs[2] = target_state;
+
+	ret = rsi_host_call(virt_to_phys(rhi_call));
+	if (ret != RSI_SUCCESS)
+		ret =  -EIO;
+	else
+		ret = rhi_call->gprs[0];
+
+	kfree(rhi_call);
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 2c0190bcb2a9..de70fba09e92 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -222,11 +222,20 @@ static void cca_tsm_pci_remove(struct pci_tsm *tsm)
 
 static int cca_tsm_lock(struct pci_dev *pdev)
 {
-	unsigned long ret;
+	long ret;
+	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
+		PCI_DEVID(pdev->bus->number, pdev->devfn);
 
+	ret = rhi_da_vdev_set_tdi_state(vdev_id, RHI_DA_TDI_CONFIG_LOCKED);
+	if (ret) {
+		pci_err(pdev, "failed to TSM bind the device (%ld)\n", ret);
+		return -EIO;
+	}
+
+	/* This will be done by above rhi in later spec */
 	ret = rsi_device_lock(pdev);
 	if (ret) {
-		pci_err(pdev, "failed to lock the device (%lu)\n", ret);
+		pci_err(pdev, "failed to lock the device (%ld)\n", ret);
 		return -EIO;
 	}
 	return 0;
@@ -234,6 +243,15 @@ static int cca_tsm_lock(struct pci_dev *pdev)
 
 static void cca_tsm_unlock(struct pci_dev *pdev)
 {
+	long ret;
+	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
+		PCI_DEVID(pdev->bus->number, pdev->devfn);
+
+	ret = rhi_da_vdev_set_tdi_state(vdev_id, RHI_DA_TDI_CONFIG_UNLOCKED);
+	if (ret) {
+		pci_err(pdev, "failed to TSM unbind the device (%ld)\n", ret);
+		return;
+	}
 }
 
 static const struct pci_tsm_ops cca_pci_ops = {
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 0807fcf8d222..18d0a627baa4 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -254,9 +254,13 @@ static struct pci_tdi *cca_tsm_bind(struct pci_dev *pdev, struct pci_dev *pf0_de
 static void cca_tsm_unbind(struct pci_tdi *tdi)
 {
 	struct realm *realm = &tdi->kvm->arch.realm;
-
+	/*
+	 * FIXME!!
+	 * All the related DEV RIPAS regions should be unmapped by now.
+	 * For now we handle them during stage2 teardown. There is no
+	 * bound IPA address available here. Possibly dmabuf can help
+	 */
 	rme_unbind_vdev(realm, tdi->pdev, tdi->pdev->tsm->dsm_dev);
-
 	module_put(THIS_MODULE);
 }

---

## [34] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 33/38] KVM: arm64: CCA: handle dev mem map/unmap*

Handle VM exit on DEV_MEM_MAP

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h |  40 +++++++
 arch/arm64/include/asm/rmi_smc.h  |   5 +
 arch/arm64/kvm/rme-exit.c         |  39 +++++-
 arch/arm64/kvm/rme.c              | 190 ++++++++++++++++++++++++++++--
 drivers/vfio/pci/vfio_pci_core.c  |   1 +
 5 files changed, 262 insertions(+), 13 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index fcf6b319e953..900e35dae740 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -638,4 +638,44 @@ static inline unsigned long rmi_vdev_complete(unsigned long rec_phys, unsigned l
 	return res.a0;
 }
 
+static inline int rmi_rtt_dev_mem_validate(unsigned long rd, unsigned long rec,
+					   unsigned long base, unsigned long top,
+					   unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_DEV_MEM_VALIDATE, rd, rec, base, top, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+static inline int rmi_dev_mem_map(unsigned long rd, unsigned long ipa,
+				  unsigned long level, unsigned long pa)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_DEV_MEM_MAP, rd, ipa, level, pa, &res);
+
+	return res.a0;
+}
+
+static inline int rmi_dev_mem_unmap(unsigned long rd, unsigned long ipa,
+				    unsigned long level, unsigned long *out_pa,
+				    unsigned long *out_ipa)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_DEV_MEM_UNMAP, rd, ipa, level, &res);
+
+	if (out_pa)
+		*out_pa = res.a1;
+	if (out_ipa)
+		*out_ipa = res.a2;
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 7073eccaec5f..ab169b375198 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -39,6 +39,7 @@
 
 #define SMC_RMI_RTT_READ_ENTRY		SMC_RMI_CALL(0x0161)
 #define SMC_RMI_RTT_UNMAP_UNPROTECTED	SMC_RMI_CALL(0x0162)
+#define SMC_RMI_RTT_DEV_MEM_VALIDATE	SMC_RMI_CALL(0x0163)
 
 #define SMC_RMI_PSCI_COMPLETE		SMC_RMI_CALL(0x0164)
 #define SMC_RMI_FEATURES		SMC_RMI_CALL(0x0165)
@@ -47,6 +48,9 @@
 #define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
 
+#define SMC_RMI_DEV_MEM_MAP		SMC_RMI_CALL(0x0172)
+#define SMC_RMI_DEV_MEM_UNMAP		SMC_RMI_CALL(0x0173)
+
 #define SMC_RMI_PDEV_COMMUNICATE        SMC_RMI_CALL(0x0175)
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
 #define SMC_RMI_PDEV_DESTROY		SMC_RMI_CALL(0x0177)
@@ -84,6 +88,7 @@ enum rmi_ripas {
 	RMI_EMPTY = 0,
 	RMI_RAM = 1,
 	RMI_DESTROYED = 2,
+	RMI_DEV = 3,
 };
 
 #define RMI_NO_MEASURE_CONTENT	0
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index 25948207fc5b..77829491805b 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
@@ -170,17 +170,44 @@ EXPORT_SYMBOL_GPL(realm_exit_dev_mem_map_handler);
 static int rec_exit_dev_mem_map(struct kvm_vcpu *vcpu)
 {
 	int ret;
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
 	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long base = rec->run->exit.dev_mem_base;
+	unsigned long top = rec->run->exit.dev_mem_top;
+
+	if (!kvm_realm_is_private_address(realm, base) ||
+	    !kvm_realm_is_private_address(realm, top - 1)) {
+		vcpu_err(vcpu, "Invalid DEV_MEM_VALIDATE for %#lx - %#lx\n", base, top);
+		return -EINVAL;
+	}
 
+	/* See if coco driver want to look at the dev mem_map request */
 	if (realm_exit_dev_mem_map_handler) {
 		ret = (*realm_exit_dev_mem_map_handler)(rec);
-	} else {
-		kvm_pr_unimpl("Unsupported exit reason: %u\n",
-			      rec->run->exit.exit_reason);
-		vcpu->run->exit_reason = KVM_EXIT_INTERNAL_ERROR;
-		ret = 0;
+		if (ret)
+			return ret;
 	}
-	return ret;
+
+#if 0
+	/* we don't need a memory fault exit for device mapping.
+	 * 1. On enter to rec, we map the device memory using dev_mem_map
+	   2. There is no fallocate, and we are not tracking this via memory attributes.
+	   If we need a fault exit, we need to differentiate it in VMM so that we don't
+	   map the private memory via tsm map ioctl.
+	 */
+	/*
+	 * Exit to VMM so that VMM can deny the validation, the actual
+	 * validation response is done on next entry
+	 */
+	kvm_prepare_memory_fault_exit(vcpu, base, top - base, false, false,
+				      true);
+
+	/* exit to hypervisor */
+	return -EFAULT;
+#else
+	return 1;
+#endif
 }
 
 static void update_arch_timer_irq_lines(struct kvm_vcpu *vcpu)
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index d1c147aba2ed..11c8d47e3e9b 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -445,18 +445,27 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
 	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
 }
 
-static int realm_destroy_private_granule(struct realm *realm,
-					 unsigned long ipa,
+static int realm_destroy_private_granule(struct realm *realm, unsigned long ipa,
 					 unsigned long *next_addr,
-					 phys_addr_t *out_rtt)
+					 phys_addr_t *out_rtt,
+					 int *ripas)
 {
 	unsigned long rd = virt_to_phys(realm->rd);
 	unsigned long rtt_addr;
+	struct rtt_entry rtt_entry;
 	phys_addr_t rtt;
 	int ret;
 
+	ret = rmi_rtt_read_entry(rd, ipa, RMM_RTT_MAX_LEVEL, &rtt_entry);
+	if (ret != RMI_SUCCESS)
+		return -ENXIO;
+
 retry:
-	ret = rmi_data_destroy(rd, ipa, &rtt_addr, next_addr);
+	if (rtt_entry.ripas == RMI_DEV)
+		ret = rmi_dev_mem_unmap(rd, ipa, RMM_RTT_MAX_LEVEL, &rtt_addr, next_addr);
+	else
+		ret = rmi_data_destroy(rd, ipa, &rtt_addr, next_addr);
+
 	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
 		if (*next_addr > ipa)
 			return 0; /* UNASSIGNED */
@@ -484,6 +493,7 @@ static int realm_destroy_private_granule(struct realm *realm,
 		return -ENXIO;
 
 	*out_rtt = rtt_addr;
+	*ripas = rtt_entry.ripas;
 
 	return 0;
 }
@@ -495,16 +505,16 @@ static int realm_unmap_private_page(struct realm *realm,
 	unsigned long end = ALIGN(ipa + 1, PAGE_SIZE);
 	unsigned long addr;
 	phys_addr_t out_rtt = PHYS_ADDR_MAX;
-	int ret;
+	int ret, ripas;
 
 	for (addr = ipa; addr < end; addr = *next_addr) {
 		ret = realm_destroy_private_granule(realm, addr, next_addr,
-						    &out_rtt);
+						    &out_rtt, &ripas);
 		if (ret)
 			return ret;
 	}
 
-	if (out_rtt != PHYS_ADDR_MAX) {
+	if (out_rtt != PHYS_ADDR_MAX && ripas != RMI_DEV) {
 		out_rtt = ALIGN_DOWN(out_rtt, PAGE_SIZE);
 		free_page((unsigned long)phys_to_virt(out_rtt));
 	}
@@ -1222,8 +1232,17 @@ static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
 	struct kvm *kvm = vcpu->kvm;
 	int ret = ripas_change(kvm, vcpu, start, end, RIPAS_SET, top_ipa);
 
+#if 0
+	/*
+	 * We don't need to do this because a ripas change will take a memory
+	 * fault exit That results in stage2 invalidate which will take care of
+	 * unmap of both private and shared ipa.. IF we need to do this, we
+	 * should do it before ripas change, we look at ripas when unmapping the
+	 * private range.
+	 */
 	if (ripas == RMI_EMPTY && *top_ipa != start)
 		realm_unmap_private_range(kvm, start, *top_ipa, false);
+#endif
 
 	return ret;
 }
@@ -1492,6 +1511,159 @@ static void kvm_complete_ripas_change(struct kvm_vcpu *vcpu)
 	rec->run->exit.ripas_base = base;
 }
 
+/*
+ * Even though we can map larger block, since we need to delegate each granule.
+ * We map granule size and fold
+ */
+static int realm_dev_mem_map(struct kvm_vcpu *vcpu, unsigned long start_ipa,
+			     unsigned long end_ipa, phys_addr_t phys)
+{
+	int ret = 0;
+	unsigned long ipa;
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	struct kvm_mmu_memory_cache *memcache = &vcpu->arch.mmu_page_cache;
+
+	for (ipa = start_ipa ; ipa < end_ipa; ipa += PAGE_SIZE) {
+
+		if (rmi_granule_delegate(phys))
+			return -EINVAL;
+
+		ret = rmi_dev_mem_map(rd, ipa, RMM_RTT_MAX_LEVEL, phys);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(ret);
+
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      RMM_RTT_MAX_LEVEL,
+						      memcache);
+			WARN_ON(ret);
+			if (ret)
+				goto err_undelegate;
+
+			ret = rmi_dev_mem_map(rd, ipa, RMM_RTT_MAX_LEVEL, phys);
+		}
+		WARN_ON(ret);
+
+		if (ret)
+			goto err_undelegate;
+
+		phys += PAGE_SIZE;
+	}
+
+	/* : ipa = ALIGN(start_ipa, RMM_L2_BLOCK_SIZE) to be safer ?  */
+	for (ipa = start_ipa; ((ipa + RMM_L2_BLOCK_SIZE) < end_ipa); ipa += RMM_L2_BLOCK_SIZE)
+		fold_rtt(realm, ipa, RMM_RTT_BLOCK_LEVEL);
+
+	return 0;
+
+err_undelegate:
+	WARN_ON(rmi_granule_undelegate(phys));
+
+	while (ipa > start_ipa) {
+		unsigned long out_pa;
+
+		phys -= PAGE_SIZE;
+		ipa -= PAGE_SIZE;
+
+		WARN_ON(rmi_dev_mem_unmap(rd, ipa, RMM_RTT_MAX_LEVEL, &out_pa, NULL));
+
+		WARN_ON(phys != out_pa);
+		WARN_ON(rmi_granule_undelegate(out_pa));
+	}
+	return -ENXIO;
+}
+
+static int realm_dev_mem_validate(struct kvm_vcpu *vcpu,
+				  unsigned long start, unsigned long end,
+				  unsigned long *top_ipa)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	phys_addr_t rec_phys = virt_to_phys(rec->rec_page);
+	struct kvm_mmu_memory_cache *memcache = &vcpu->arch.mmu_page_cache;
+	unsigned long ipa = start;
+	int ret = 0;
+
+	while (ipa < end) {
+		unsigned long next;
+
+		ret = rmi_rtt_dev_mem_validate(rd_phys, rec_phys, ipa, end, &next);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			/*
+			 * FIXME!! We can't find the RTT error here, because
+			 * things are already setup by dev_mem_map before
+			 */
+			int walk_level = RMI_RETURN_INDEX(ret);
+			int level = find_map_level(realm, ipa, end);
+
+			/*
+			 * If the RMM walk ended early then more tables are
+			 * needed to reach the required depth to set the RIPAS.
+			 */
+			if (walk_level < level) {
+				ret = realm_create_rtt_levels(realm, ipa,
+							      walk_level,
+							      level,
+							      memcache);
+				/* Retry with RTTs created */
+				if (!ret)
+					continue;
+			} else {
+				ret = -EINVAL;
+			}
+
+			break;
+		} else if (RMI_RETURN_STATUS(ret) != RMI_SUCCESS) {
+			WARN(1, "Unexpected error in %s: %#x\n", __func__,
+			     ret);
+			ret = -EINVAL;
+			break;
+		}
+		ipa = next;
+	}
+
+	*top_ipa = ipa;
+
+	return ret;
+}
+
+static void kvm_complete_dev_mem_change(struct kvm_vcpu *vcpu)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long base = rec->run->exit.dev_mem_base;
+	unsigned long top = rec->run->exit.dev_mem_top;
+	unsigned long pa = rec->run->exit.dev_mem_pa;
+	unsigned long top_ipa;
+	int ret;
+
+	do {
+		kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_page_cache,
+					   kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));
+		write_lock(&kvm->mmu_lock);
+		/*
+		 * FIXME!! we need validate these values. Also PA need to be tied to the life cycle
+		 * of vfio device/file descriptor.
+		 */
+		ret = realm_dev_mem_map(vcpu, base, top, pa);
+		if (!ret)
+			ret = realm_dev_mem_validate(vcpu, base, top, &top_ipa);
+		write_unlock(&kvm->mmu_lock);
+		if (ret)
+			break;
+
+		base = top_ipa;
+	} while (top_ipa < top);
+
+	WARN(ret, "Unable to satisfy DEV_MEM_CHANGE for %#lx - %#lx\n", base, top);
+}
+
 /*
  * kvm_rec_pre_enter - Complete operations before entering a REC
  *
@@ -1520,6 +1692,10 @@ int kvm_rec_pre_enter(struct kvm_vcpu *vcpu)
 	case RMI_EXIT_RIPAS_CHANGE:
 		kvm_complete_ripas_change(vcpu);
 		break;
+	case RMI_EXIT_DEV_MEM_MAP:
+		kvm_complete_dev_mem_change(vcpu);
+		break;
+
 	}
 
 	return 1;
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index afdb39c6aefd..264ee84d7ecd 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -1718,6 +1718,7 @@ static const struct vm_operations_struct vfio_pci_mmap_ops = {
 #endif
 };
 
+/* FIXME!! don't allow mmap once the device is TDISP locked and we did dev mem_map. */
 int vfio_pci_core_mmap(struct vfio_device *core_vdev, struct vm_area_struct *vma)
 {
 	struct vfio_pci_core_device *vdev =

---

## [35] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range found in the interface report*

This starts the sequence to transition the realm device to the TDISP RUN
state by writing 1 to 'tsm/accept'.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h         |  18 +++
 arch/arm64/include/asm/rsi_smc.h          |   4 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c |   3 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 132 ++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  25 ++++
 5 files changed, 182 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 18fc4e1ce577..1cc00d404e53 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -228,4 +228,22 @@ static inline unsigned long rsi_host_call(phys_addr_t addr)
 	return res.a0;
 }
 
+static inline unsigned long
+rsi_rdev_validate_mapping(unsigned long vdev_id, unsigned long inst_id,
+			  phys_addr_t start_ipa, phys_addr_t end_ipa,
+			  phys_addr_t io_pa, phys_addr_t *next_ipa, unsigned long flags)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_VALIDATE_MAPPING, vdev_id,
+			     inst_id, start_ipa, end_ipa, io_pa, flags, &res);
+	*next_ipa = res.a1;
+
+	if (res.a2 != RSI_ACCEPT)
+		return -EPERM;
+
+	if (res.a0 != RSI_SUCCESS)
+		return -EINVAL;
+	return 0;
+}
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 1d762fe3777b..a28b41cf01ca 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -204,4 +204,8 @@ struct rsi_host_call {
 
 #define SMC_RSI_RDEV_LOCK			SMC_RSI_FID(0x1a9)
 
+#define RSI_DEV_MEM_COHERENT		BIT(0)
+#define RSI_DEV_MEM_LIMITED_ORDER	BIT(1)
+#define SMC_RSI_RDEV_VALIDATE_MAPPING		SMC_RSI_FID(0x1ac)
+
 #endif /* __ASM_RSI_SMC_H_ */
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index de70fba09e92..c1cefb983ac7 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -247,6 +247,9 @@ static void cca_tsm_unlock(struct pci_dev *pdev)
 	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
 		PCI_DEVID(pdev->bus->number, pdev->devfn);
 
+	/* invalidate dev mapping based on interface report */
+	rsi_update_interface_report(pdev, false);
+
 	ret = rhi_da_vdev_set_tdi_state(vdev_id, RHI_DA_TDI_CONFIG_UNLOCKED);
 	if (ret) {
 		pci_err(pdev, "failed to TSM unbind the device (%ld)\n", ret);
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 47b379318e7c..936f844880de 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -215,3 +215,135 @@ int rsi_device_lock(struct pci_dev *pdev)
 
 	return ret;
 }
+
+static inline unsigned long
+rsi_validate_dev_mapping(unsigned long vdev_id, unsigned long inst_id,
+			 phys_addr_t start_ipa, phys_addr_t end_ipa,
+			 phys_addr_t io_pa, unsigned long flags)
+{
+	unsigned long ret;
+	phys_addr_t next_ipa;
+
+	while (start_ipa < end_ipa) {
+		ret = rsi_rdev_validate_mapping(vdev_id, inst_id,
+						start_ipa, end_ipa,
+						io_pa, &next_ipa, flags);
+		if (ret || next_ipa < start_ipa || next_ipa > end_ipa)
+			return -EINVAL;
+		io_pa += next_ipa - start_ipa;
+		start_ipa = next_ipa;
+	}
+	return 0;
+}
+
+static int rsi_invalidate_dev_mapping(phys_addr_t start_ipa, phys_addr_t end_ipa)
+{
+	return rsi_set_memory_range(start_ipa, end_ipa, RSI_RIPAS_EMPTY,
+				    RSI_CHANGE_DESTROYED);
+}
+
+static int get_msix_bar(struct pci_dev *pdev, int cap)
+{
+	int bar;
+	u32 table_offset;
+	unsigned long flags;
+
+	pci_read_config_dword(pdev, pdev->msix_cap + cap, &table_offset);
+	bar = (u8)(table_offset & PCI_MSIX_TABLE_BIR);
+	flags = pci_resource_flags(pdev, bar);
+	if (!flags || (flags & IORESOURCE_UNSET))
+		return -1;
+
+	return bar;
+}
+
+int rsi_update_interface_report(struct pci_dev *pdev, bool validate)
+{
+	int ret;
+	struct resource *r;
+	int msix_tbl_bar, msix_pba_bar;
+	unsigned int range_id;
+	unsigned long mmio_start_phys;
+	unsigned long mmio_flags = 0; /* non coherent, not limited order */
+	struct pci_tdisp_mmio_range *mmio_range;
+	struct pci_tdisp_device_interface_report *interface_report;
+	struct cca_guest_dsc *dsm = to_cca_guest_dsc(pdev);
+	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
+		PCI_DEVID(pdev->bus->number, pdev->devfn);
+
+
+	interface_report = (struct pci_tdisp_device_interface_report *)dsm->interface_report;
+	mmio_range = (struct pci_tdisp_mmio_range *)(interface_report + 1);
+
+
+	msix_tbl_bar = get_msix_bar(pdev, PCI_MSIX_TABLE);
+	msix_pba_bar = get_msix_bar(pdev, PCI_MSIX_PBA);
+
+	for (int i = 0; i < interface_report->mmio_range_count; i++, mmio_range++) {
+
+		/*FIXME!! units in 4K size*/
+		range_id = FIELD_GET(TSM_INTF_REPORT_MMIO_RANGE_ID, mmio_range->range_attributes);
+
+		/* no secure interrupts */
+		if (msix_tbl_bar != -1 && range_id == msix_tbl_bar) {
+			pr_info("Skipping misx table\n");
+			continue;
+		}
+
+		if (msix_pba_bar != -1 && range_id == msix_pba_bar) {
+			pr_info("Skipping misx pba\n");
+			continue;
+		}
+
+		r = pci_resource_n(pdev, range_id);
+
+		if (r->end == r->start ||
+		    ((r->end - r->start + 1) & ~PAGE_MASK) || !mmio_range->num_pages) {
+			pci_warn(pdev, "Skipping broken range [%d] #%d %d pages, %llx..%llx\n",
+				i, range_id, mmio_range->num_pages, r->start, r->end);
+			continue;
+		}
+
+		if (FIELD_GET(TSM_INTF_REPORT_MMIO_IS_NON_TEE, mmio_range->range_attributes)) {
+			pci_info(pdev, "Skipping non-TEE range [%d] #%d %d pages, %llx..%llx\n",
+				 i, range_id, mmio_range->num_pages, r->start, r->end);
+			continue;
+		}
+
+		/* No secure interrupts, we should not find this set, ignore for now. */
+		if (FIELD_GET(TSM_INTF_REPORT_MMIO_MSIX_TABLE, mmio_range->range_attributes) ||
+		    FIELD_GET(TSM_INTF_REPORT_MMIO_PBA, mmio_range->range_attributes)) {
+			pci_info(pdev, "Skipping MSIX (%ld/%ld) range [%d] #%d %d pages, %llx..%llx\n",
+				 FIELD_GET(TSM_INTF_REPORT_MMIO_MSIX_TABLE, mmio_range->range_attributes),
+				 FIELD_GET(TSM_INTF_REPORT_MMIO_PBA, mmio_range->range_attributes),
+				 i, range_id, mmio_range->num_pages, r->start, r->end);
+			continue;
+		}
+
+		mmio_start_phys = mmio_range->first_page;
+		if (validate)
+			ret = rsi_validate_dev_mapping(vdev_id, dsm->instance_id,
+						       r->start, r->end + 1,
+						       mmio_start_phys << 12, mmio_flags);
+		else
+			ret = rsi_invalidate_dev_mapping(r->start, r->end + 1);
+		if (ret) {
+			pci_err(pdev, "failed to set protection attributes for the address range\n");
+			return -EIO;
+		}
+	}
+	return 0;
+}
+
+int rsi_device_start(struct pci_dev *pdev)
+{
+	int ret;
+
+	ret = rsi_update_interface_report(pdev, true);
+	if (ret) {
+		pci_err(pdev, "failed validate the interface report\n");
+		return -EIO;
+	}
+
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index bd565785ff4b..0d6e1c0ada4a 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -11,6 +11,28 @@
 #include <asm/rsi_smc.h>
 #include <asm/rhi.h>
 
+struct pci_tdisp_device_interface_report {
+	u16 interface_info;
+	u16 reserved;
+	u16 msi_x_message_control;
+	u16 lnr_control;
+	u32 tph_control;
+	u32 mmio_range_count;
+} __packed;
+
+struct pci_tdisp_mmio_range {
+	u64 first_page;
+	u32 num_pages;
+	u32 range_attributes;
+} __packed;
+
+#define TSM_INTF_REPORT_MMIO_MSIX_TABLE		BIT(0)
+#define TSM_INTF_REPORT_MMIO_PBA		BIT(1)
+#define TSM_INTF_REPORT_MMIO_IS_NON_TEE		BIT(2)
+#define TSM_INTF_REPORT_MMIO_IS_UPDATABLE	BIT(3)
+#define TSM_INTF_REPORT_MMIO_RESERVED		GENMASK(15, 4)
+#define TSM_INTF_REPORT_MMIO_RANGE_ID		GENMASK(31, 16)
+
 struct cca_guest_dsc {
 	struct pci_tsm_pf0 pci;
 	unsigned long instance_id;
@@ -29,5 +51,8 @@ static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_guest_dsc, pci.tsm);
 }
 
+int rsi_update_interface_report(struct pci_dev *pdev, bool validate);
 int rsi_device_lock(struct pci_dev *pdev);
+int rsi_device_start(struct pci_dev *pdev);
+
 #endif

---

## [36] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 35/38] coco: guest: arm64: Add Realm device start and stop support*

Writing 1 to 'tsm/acceept' will initiate the TDISP RUN sequence.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h         | 19 +++++++
 arch/arm64/include/asm/rsi_smc.h          |  2 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 15 ++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 60 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  2 +-
 5 files changed, 97 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 1cc00d404e53..3463d571d7db 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -246,4 +246,23 @@ rsi_rdev_validate_mapping(unsigned long vdev_id, unsigned long inst_id,
 		return -EINVAL;
 	return 0;
 }
+
+static inline unsigned long __rsi_rdev_start(unsigned long vdev_id, unsigned long inst_id)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_START, vdev_id, inst_id, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long __rsi_rdev_stop(unsigned long vdev_id, unsigned long inst_id)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_STOP, vdev_id, inst_id, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index a28b41cf01ca..f6aa647239c0 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -203,6 +203,8 @@ struct rsi_host_call {
 #define SMC_RSI_RDEV_GET_INTERFACE_REPORT	SMC_RSI_FID(0x1a6)
 
 #define SMC_RSI_RDEV_LOCK			SMC_RSI_FID(0x1a9)
+#define SMC_RSI_RDEV_START			SMC_RSI_FID(0x1aa)
+#define SMC_RSI_RDEV_STOP			SMC_RSI_FID(0x1ab)
 
 #define RSI_DEV_MEM_COHERENT		BIT(0)
 #define RSI_DEV_MEM_LIMITED_ORDER	BIT(1)
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index c1cefb983ac7..7eeb9732d20a 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -250,6 +250,8 @@ static void cca_tsm_unlock(struct pci_dev *pdev)
 	/* invalidate dev mapping based on interface report */
 	rsi_update_interface_report(pdev, false);
 
+	rsi_device_stop(pdev);
+
 	ret = rhi_da_vdev_set_tdi_state(vdev_id, RHI_DA_TDI_CONFIG_UNLOCKED);
 	if (ret) {
 		pci_err(pdev, "failed to TSM unbind the device (%ld)\n", ret);
@@ -257,11 +259,24 @@ static void cca_tsm_unlock(struct pci_dev *pdev)
 	}
 }
 
+static int cca_tsm_accept(struct pci_dev *pdev)
+{
+	int ret;
+
+	ret = rsi_device_start(pdev);
+	if (ret) {
+		pci_err(pdev, "failed to transition the device to run state (%d)\n", ret);
+		return -EIO;
+	}
+	return 0;
+}
+
 static const struct pci_tsm_ops cca_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
 	.lock = cca_tsm_lock,
 	.unlock = cca_tsm_unlock,
+	.accept	 = cca_tsm_accept,
 };
 
 static void cca_tsm_unregister(void *tsm)
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 936f844880de..64034d220e02 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -215,6 +215,24 @@ int rsi_device_lock(struct pci_dev *pdev)
 
 	return ret;
 }
+static inline unsigned long rsi_rdev_start(struct pci_dev *pdev,
+					   unsigned long vdev_id, unsigned long inst_id)
+{
+	unsigned long ret;
+
+	ret = __rsi_rdev_start(vdev_id, inst_id);
+	if (ret != RSI_SUCCESS)
+		return ret;
+
+	do {
+		ret = rsi_rdev_continue(vdev_id, inst_id);
+	} while (ret == RSI_INCOMPLETE);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to communicate with the device (%lu)\n", ret);
+		return ret;
+	}
+	return RSI_SUCCESS;
+}
 
 static inline unsigned long
 rsi_validate_dev_mapping(unsigned long vdev_id, unsigned long inst_id,
@@ -338,6 +356,9 @@ int rsi_update_interface_report(struct pci_dev *pdev, bool validate)
 int rsi_device_start(struct pci_dev *pdev)
 {
 	int ret;
+	struct cca_guest_dsc *dsm = to_cca_guest_dsc(pdev);
+	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
+		PCI_DEVID(pdev->bus->number, pdev->devfn);
 
 	ret = rsi_update_interface_report(pdev, true);
 	if (ret) {
@@ -345,5 +366,44 @@ int rsi_device_start(struct pci_dev *pdev)
 		return -EIO;
 	}
 
+	ret = rsi_rdev_start(pdev, vdev_id, dsm->instance_id);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to start the device (%u)\n", ret);
+		return -EIO;
+	}
+	return 0;
+}
+
+static inline unsigned long rsi_rdev_stop(struct pci_dev *pdev,
+					  unsigned long vdev_id, unsigned long inst_id)
+{
+	unsigned long ret;
+
+	ret = __rsi_rdev_stop(vdev_id, inst_id);
+	if (ret != RSI_SUCCESS)
+		return ret;
+
+	do {
+		ret = rsi_rdev_continue(vdev_id, inst_id);
+	} while (ret == RSI_INCOMPLETE);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to communicate with the device (%lu)\n", ret);
+		return ret;
+	}
+	return RSI_SUCCESS;
+}
+
+int rsi_device_stop(struct pci_dev *pdev)
+{
+	int ret;
+	struct cca_guest_dsc *dsm = to_cca_guest_dsc(pdev);
+	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
+		PCI_DEVID(pdev->bus->number, pdev->devfn);
+
+	ret = rsi_rdev_stop(pdev, vdev_id, dsm->instance_id);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to stop the device (%u)\n", ret);
+		return -EIO;
+	}
 	return 0;
 }
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 0d6e1c0ada4a..71ee1edb832e 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -54,5 +54,5 @@ static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
 int rsi_update_interface_report(struct pci_dev *pdev, bool validate);
 int rsi_device_lock(struct pci_dev *pdev);
 int rsi_device_start(struct pci_dev *pdev);
-
+int rsi_device_stop(struct pci_dev *pdev);
 #endif

---

## [37] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 36/38] KVM: arm64: CCA: enable DA in realm create parameters*

Now that we have all the required steps for DA in-place, enable
DA while creating ralm.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h | 1 +
 arch/arm64/kvm/rme.c             | 2 ++
 2 files changed, 3 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index ab169b375198..f664954a2a91 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -112,6 +112,7 @@ enum rmi_ripas {
 #define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
 #define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
 #define RMI_REALM_PARAM_FLAG_PMU		BIT(2)
+#define RMI_REALM_PARAM_FLAG_DA			BIT(3)
 
 /*
  * Note many of these fields are smaller than u64 but all fields have u64
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 11c8d47e3e9b..394d1534e6c2 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -695,6 +695,8 @@ static int realm_create_rd(struct kvm *kvm)
 	if (r)
 		goto out_undelegate_tables;
 
+	/* For now default enable DA */
+	params->flags = RMI_REALM_PARAM_FLAG_DA;
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---

## [38] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 37/38] coco: guest: arm64: Add support for fetching device measurements*

Fetch device measurements using RSI_RDEV_GET_MEASUREMENTS.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h        | 11 +++++++
 arch/arm64/include/asm/rsi_smc.h         | 16 ++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 39 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h |  2 ++
 4 files changed, 68 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 3463d571d7db..42b998f44a0e 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -265,4 +265,15 @@ static inline unsigned long __rsi_rdev_stop(unsigned long vdev_id, unsigned long
 	return res.a0;
 }
 
+static inline unsigned long __rsi_rdev_get_measurements(unsigned long vdev_id,
+						       unsigned long inst_id,
+						       phys_addr_t meas)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_GET_MEASUREMENTS, vdev_id, inst_id, meas, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index f6aa647239c0..f051db54cdc3 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -202,6 +202,22 @@ struct rsi_host_call {
 
 #define SMC_RSI_RDEV_GET_INTERFACE_REPORT	SMC_RSI_FID(0x1a6)
 
+#define RSI_DEV_MEASURE_ALL		BIT(0)
+#define RSI_DEV_MEASURE_SIGNED		BIT(1)
+#define RSI_DEV_MEASURE_RAW		BIT(2)
+
+struct rsi_device_measurements_params {
+	union {
+		struct {
+			u64 flags;
+			u8 indices[32];
+			u8 nounce[32];
+		};
+		u8 padding[0x100];
+	};
+};
+
+#define SMC_RSI_RDEV_GET_MEASUREMENTS		SMC_RSI_FID(0x1a7)
 #define SMC_RSI_RDEV_LOCK			SMC_RSI_FID(0x1a9)
 #define SMC_RSI_RDEV_START			SMC_RSI_FID(0x1aa)
 #define SMC_RSI_RDEV_STOP			SMC_RSI_FID(0x1ab)
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 64034d220e02..6222b10964ee 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -166,10 +166,31 @@ static long rhi_get_report(int vdev_id, int da_object_type, void **report, int *
 	return ret;
 }
 
+static inline unsigned long
+rsi_rdev_get_measurements(struct pci_dev *pdev, unsigned long vdev_id,
+			  unsigned long inst_id, phys_addr_t meas)
+{
+	unsigned long ret;
+
+	ret = __rsi_rdev_get_measurements(vdev_id, inst_id, meas);
+	if (ret != RSI_SUCCESS)
+		return ret;
+
+	do {
+		ret = rsi_rdev_continue(vdev_id, inst_id);
+	} while (ret == RSI_INCOMPLETE);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to communicate with the device (%lu)\n", ret);
+		return ret;
+	}
+	return RSI_SUCCESS;
+}
+
 int rsi_device_lock(struct pci_dev *pdev)
 {
 	unsigned long ret;
 	unsigned long tdisp_version;
+	struct rsi_device_measurements_params *rsi_dev_meas;
 	struct cca_guest_dsc *dsm = to_cca_guest_dsc(pdev);
 	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
 		PCI_DEVID(pdev->bus->number, pdev->devfn);
@@ -198,6 +219,17 @@ int rsi_device_lock(struct pci_dev *pdev)
 		return -EOPNOTSUPP;
 	}
 
+	rsi_dev_meas = (struct rsi_device_measurements_params *)__get_free_page(GFP_KERNEL);
+	rsi_dev_meas->flags = RSI_DEV_MEASURE_ALL;
+	ret = rsi_rdev_get_measurements(pdev, vdev_id, dsm->instance_id,
+					virt_to_phys(rsi_dev_meas));
+
+	free_page((unsigned long)rsi_dev_meas);
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to get device measurement (%lu)\n", ret);
+		return -EIO;
+	}
+
 	/* Now make a host call to copy the interface report to guest. */
 	ret = rhi_get_report(vdev_id, RHI_DA_OBJECT_INTERFACE_REPORT,
 			     &dsm->interface_report, &dsm->interface_report_size);
@@ -213,6 +245,13 @@ int rsi_device_lock(struct pci_dev *pdev)
 		return -EIO;
 	}
 
+	ret = rhi_get_report(vdev_id, RHI_DA_OBJECT_MEASUREMENT,
+			     &dsm->measurements, &dsm->measurements_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device certificate from the host (%lu)\n", ret);
+		return -EIO;
+	}
+
 	return ret;
 }
 static inline unsigned long rsi_rdev_start(struct pci_dev *pdev,
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 71ee1edb832e..f26156d9be81 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -40,6 +40,8 @@ struct cca_guest_dsc {
 	int interface_report_size;
 	void *certificate;
 	int certificate_size;
+	void *measurements;
+	int measurements_size;
 };
 
 static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)

---

## [39] Aneesh Kumar K.V (Arm) — 2025-07-28
*Subject: [RFC PATCH v1 38/38] coco: guest: arm64: Add support for fetching device info*

RSI_RDEV_GET_INFO returns different digest hash values, which can be
compared with host cached values to ensure the host didn't tamper with
the cached data.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h        |  12 +++
 arch/arm64/include/asm/rsi_smc.h         |  24 +++++
 drivers/virt/coco/arm-cca-guest/Kconfig  |   2 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 128 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h |  13 +++
 5 files changed, 179 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 42b998f44a0e..6b90a6cdd7fb 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -276,4 +276,16 @@ static inline unsigned long __rsi_rdev_get_measurements(unsigned long vdev_id,
 	return res.a0;
 }
 
+static inline unsigned long rsi_rdev_get_info(unsigned long vdev_id,
+					      unsigned long inst_id,
+					      unsigned long digest_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_RDEV_GET_INFO,
+			     vdev_id, inst_id, digest_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index f051db54cdc3..e2b51cf58bd4 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -125,6 +125,9 @@
 
 #ifndef __ASSEMBLY__
 
+#define RSI_HASH_SHA_256 0
+#define RSI_HASH_SHA_512 1
+
 struct realm_config {
 	union {
 		struct {
@@ -200,6 +203,27 @@ struct rsi_host_call {
 #define SMC_RSI_RDEV_GET_INSTANCE_ID		SMC_RSI_FID(0x19c)
 #define SMC_RSI_RDEV_CONTINUE			SMC_RSI_FID(0x1a4)
 
+struct rsi_device_info {
+	union {
+		struct {
+			u64 flags;
+			u64 attest_type;
+			u64 cert_id;
+			u8 hash_algo;
+		};
+		u8 padding[0x40];
+	};
+	union { /* 0x40  */
+		struct {
+			u8 cert_digest[0x40];
+			u8 meas_digest[0x40];
+			u8 report_digest[0x40];
+		};
+		u8 padding2[0x200 - 0x40];
+	};
+};
+
+#define SMC_RSI_RDEV_GET_INFO			SMC_RSI_FID(0x1a5)
 #define SMC_RSI_RDEV_GET_INTERFACE_REPORT	SMC_RSI_FID(0x1a6)
 
 #define RSI_DEV_MEASURE_ALL		BIT(0)
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index 410d9c3fb2b3..6fc86c1f3900 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -5,6 +5,8 @@ config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
 	depends on PCI_TSM
+	select CRYPTO_SHA256
+	select CRYPTO_SHA512
 	select TSM_REPORTS
 	select TSM
 	help
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 6222b10964ee..a1bb225adb4c 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -6,6 +6,7 @@
 #include <linux/pci.h>
 #include <linux/mem_encrypt.h>
 #include <asm/rsi_cmds.h>
+#include <crypto/hash.h>
 
 #include "rsi-da.h"
 
@@ -186,11 +187,102 @@ rsi_rdev_get_measurements(struct pci_dev *pdev, unsigned long vdev_id,
 	return RSI_SUCCESS;
 }
 
+static int verify_digests(struct cca_guest_dsc *dsm)
+{
+	int i;
+	int ret;
+	u8 digest[SHA512_DIGEST_SIZE];
+	int sdesc_size;
+	size_t digest_size;
+	char *hash_alg_name;
+	struct shash_desc *shash;
+	struct crypto_shash *alg;
+	struct pci_dev *pdev = dsm->pci.tsm.pdev;
+	struct {
+		uint8_t *report;
+		size_t size;
+		uint8_t *digest;
+	} reports[] = {
+		{
+			dsm->interface_report,
+			dsm->interface_report_size,
+			dsm->dev_info.report_digest
+		},
+		{
+			dsm->certificate,
+			dsm->certificate_size,
+			dsm->dev_info.cert_digest
+		},
+		{
+			dsm->measurements,
+			dsm->measurements_size,
+			dsm->dev_info.meas_digest
+		}
+	};
+
+
+	if (dsm->dev_info.hash_algo == RSI_HASH_SHA_256) {
+		hash_alg_name = "sha256";
+		digest_size = SHA256_DIGEST_SIZE;
+	} else if (dsm->dev_info.hash_algo == RSI_HASH_SHA_512) {
+		hash_alg_name = "sha512";
+		digest_size = SHA512_DIGEST_SIZE;
+	} else {
+		pci_err(pdev, "unknown realm hash algorithm!\n");
+		ret = -EINVAL;
+		goto err_out;
+	}
+
+	alg = crypto_alloc_shash(hash_alg_name, 0, 0);
+	if (IS_ERR(alg)) {
+		pci_err(pdev, "cannot allocate %s\n", hash_alg_name);
+		return PTR_ERR(alg);
+	}
+
+	sdesc_size = sizeof(struct shash_desc) + crypto_shash_descsize(alg);
+	shash = kzalloc(sdesc_size, GFP_KERNEL);
+	if (!shash) {
+		pci_err(pdev, "cannot allocate sdesc\n");
+		ret = -ENOMEM;
+		goto err_free_shash;
+	}
+	shash->tfm = alg;
+
+	for (i = 0; i < ARRAY_SIZE(reports); i++) {
+		ret = crypto_shash_digest(shash, reports[i].report,
+					  reports[i].size, digest);
+		if (ret) {
+			pci_err(pdev, "failed to compute digest, %d\n", ret);
+			goto err_free_sdesc;
+		}
+
+		if (memcmp(reports[i].digest, digest, digest_size)) {
+			pci_err(pdev, "invalid digest\n");
+			ret = -EINVAL;
+			goto err_free_sdesc;
+		}
+	}
+
+	kfree(shash);
+	crypto_free_shash(alg);
+
+	pci_info(pdev, "Successfully verified the digests\n");
+	return 0;
+
+err_free_sdesc:
+	kfree(shash);
+err_free_shash:
+	crypto_free_shash(alg);
+err_out:
+	return ret;
+}
+
 int rsi_device_lock(struct pci_dev *pdev)
 {
 	unsigned long ret;
 	unsigned long tdisp_version;
 	struct rsi_device_measurements_params *rsi_dev_meas;
+	struct rsi_device_info *dev_info;
 	struct cca_guest_dsc *dsm = to_cca_guest_dsc(pdev);
 	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
 		PCI_DEVID(pdev->bus->number, pdev->devfn);
@@ -252,8 +344,44 @@ int rsi_device_lock(struct pci_dev *pdev)
 		return -EIO;
 	}
 
+	/* RMM expects sizeof(dev_info) (512 bytes) aligned address */
+	dev_info = kmalloc(sizeof(*dev_info), GFP_KERNEL);
+	if (!dev_info) {
+		ret = -ENOMEM;
+		goto err_out;
+	}
+
+	ret = rsi_rdev_get_info(vdev_id, dsm->instance_id, virt_to_phys(dev_info));
+	if (ret != RSI_SUCCESS) {
+		pci_err(pdev, "failed to get device digests (%lu)\n", ret);
+		ret = -EIO;
+		kfree(dev_info);
+		goto err_out;
+	}
+
+	dsm->dev_info.attest_type   = dev_info->attest_type;
+	dsm->dev_info.cert_id       = dev_info->cert_id;
+	dsm->dev_info.hash_algo     = dev_info->hash_algo;
+	memcpy(dsm->dev_info.cert_digest, dev_info->cert_digest, SHA512_DIGEST_SIZE);
+	memcpy(dsm->dev_info.meas_digest, dev_info->meas_digest, SHA512_DIGEST_SIZE);
+	memcpy(dsm->dev_info.report_digest, dev_info->report_digest, SHA512_DIGEST_SIZE);
+
+	kfree(dev_info);
+	/*
+	 * Verify that the digests of the provided reports match with the
+	 * digests from RMM
+	 */
+	ret = verify_digests(dsm);
+	if (ret) {
+		pci_err(pdev, "device digest validation failed (%ld)\n", ret);
+		return ret;
+	}
+
+	return 0;
+err_out:
 	return ret;
 }
+
 static inline unsigned long rsi_rdev_start(struct pci_dev *pdev,
 					   unsigned long vdev_id, unsigned long inst_id)
 {
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index f26156d9be81..e8953b8e85a3 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -10,6 +10,7 @@
 #include <linux/pci-tsm.h>
 #include <asm/rsi_smc.h>
 #include <asm/rhi.h>
+#include <crypto/sha2.h>
 
 struct pci_tdisp_device_interface_report {
 	u16 interface_info;
@@ -33,6 +34,17 @@ struct pci_tdisp_mmio_range {
 #define TSM_INTF_REPORT_MMIO_RESERVED		GENMASK(15, 4)
 #define TSM_INTF_REPORT_MMIO_RANGE_ID		GENMASK(31, 16)
 
+struct dsm_device_info {
+	u64 flags;
+	u64 attest_type;
+	u64 cert_id;
+	u64 hash_algo;
+	u8 cert_digest[SHA512_DIGEST_SIZE];
+	u8 meas_digest[SHA512_DIGEST_SIZE];
+	u8 report_digest[SHA512_DIGEST_SIZE];
+};
+
+
 struct cca_guest_dsc {
 	struct pci_tsm_pf0 pci;
 	unsigned long instance_id;
@@ -42,6 +54,7 @@ struct cca_guest_dsc {
 	int certificate_size;
 	void *measurements;
 	int measurements_size;
+	struct dsm_device_info dev_info;
 };
 
 static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)

---

## [40] Jason Gunthorpe — 2025-07-28
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

On Mon, Jul 28, 2025 at 07:21:43PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

Why would we need this?

I can sort of understand why Intel would need it due to their issues
with MCE, but ARM shouldn't care either way, should it?

But also why is it an iommufd option? That doesn't seem right..

Jason

---

## [41] Jason Gunthorpe — 2025-07-28
*Subject: Re: [RFC PATCH v1 07/38] iommufd/viommu: Add support to associate
 viommu with kvm instance*

On Mon, Jul 28, 2025 at 07:21:44PM +0530, Aneesh Kumar K.V (Arm) wrote:

> +#if IS_ENABLED(CONFIG_KVM)
> +#include <linux/kvm_host.h>

Missing stub functions for !CONFIG_KVM?

Looks like an OK design otherwise

> @@ -1057,6 +1068,7 @@ struct iommu_viommu_alloc {
>  	__u32 data_len;

fds are __s32, they are signed numbers.

Jason

---

## [42] Jason Gunthorpe — 2025-07-28
*Subject: Re: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

On Mon, Jul 28, 2025 at 07:21:47PM +0530, Aneesh Kumar K.V (Arm) wrote:
> With passthrough devices, we need to make sure private memory is
> allocated and assigned to the secure guest before we can issue the DMA.

I'm not really sure what this is about? It is about getting KVM to pin
all the memory and commit it to the RMM so it can be used for DMA?

But it looks really strange to have an iommufd ioctl that just calls a
KVM function. Feeling this should be a KVM function, or a guestmfd
behavior??

I was kind of thinking it would be nice to have a guestmemfd mode that
was "pinned", meaning the memory is allocated and remains almost
always mapped into the TSM's page tables automatically. VFIO using
guests would set things this way.

Jason

---

## [43] Jason Gunthorpe — 2025-07-28
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Mon, Jul 28, 2025 at 07:21:41PM +0530, Aneesh Kumar K.V (Arm) wrote:
> @@ -48,3 +49,12 @@ int set_memory_decrypted(unsigned long addr, int numpages)
>  	return crypt_ops->decrypt(addr, numpages);

Is this OK? I see code like this:

static inline dma_addr_t phys_to_dma_direct(struct device *dev,
		phys_addr_t phys)
{
	if (force_dma_unencrypted(dev))
		return phys_to_dma_unencrypted(dev, phys);
	return phys_to_dma(dev, phys);

What are the ARM rules for generating dma addreses?

1) Device is T=0, memory is unencrypted, call dma_addr_unencrypted()
   and do "top bit IBA set"

2) Device is T=1, memory is encrypted, use the phys_to_dma() normally

3) Device it T=1, memory is uncrypted, use the phys_to_dma()
   normally??? Seems odd, I would have guessed the DMA address sould
   be the same as case #1?

Can you document this in a comment?

> diff --git a/include/linux/device.h b/include/linux/device.h
> index 4940db137fff..d62e0dd9d8ee 100644

I would give the dev->tdi_enabled a clearer name, maybe
dev->encrypted_dma_supported ?

Also need to think carefully of a bitfield is OK here, we can't
locklessly change a bitfield so need to audit that all members are set
under, probably, the device lock or some other single threaded hand
waving. It seems believable it is like that but should be checked out,
and add a lockdep if it relies on the device lock.

Jason

---

## [44] Aneesh Kumar K.V — 2025-07-29
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Mon, Jul 28, 2025 at 07:21:41PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> @@ -48,3 +49,12 @@ int set_memory_decrypted(unsigned long addr, int numpages)

If a device is operating in secure mode (T=1), it is currently assumed
that only access to private (encrypted) memory is supported. It is
unclear whether devices would need to perform DMA to shared
(unencrypted) memory while operating in this mode, as TLPs with T=1 are
generally expected to target private memory.

Based on this assumption, T=1 devices will always access
private/encrypted memory, while T=0 devices will be restricted to
shared/unencrypted memory.

>
>> diff --git a/include/linux/device.h b/include/linux/device.h

Will check and update the patch.

-aneesh

---

## [45] Aneesh Kumar K.V — 2025-07-29
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Mon, Jul 28, 2025 at 07:21:43PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

This is based on our previous discussion https://lore.kernel.org/all/20250606120919.GH19710@nvidia.com

IIUC, we intend to request the resource in exclusive mode for secure
guests—regardless of whether the platform is Intel or ARM. Could you
help clarify the MCE issue observed on Intel platforms in this context?

-aneesh

---

## [46] Aneesh Kumar K.V — 2025-07-29
*Subject: Re: [RFC PATCH v1 07/38] iommufd/viommu: Add support to associate
 viommu with kvm instance*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Mon, Jul 28, 2025 at 07:21:44PM +0530, Aneesh Kumar K.V (Arm) wrote:
>

Thanks for the review comments. I’ll update the patch with the suggested changes.

-aneesh

---

## [47] Aneesh Kumar K.V — 2025-07-29
*Subject: Re: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Mon, Jul 28, 2025 at 07:21:47PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> With passthrough devices, we need to make sure private memory is

That is correct.

>
> But it looks really strange to have an iommufd ioctl that just calls a
This functionality is equivalent to `IOMMU_IOAS_MAP`, but in the
presence of firmware like RMM, we also need to supply the realm
descriptor associated with the KVM instance.

Initially, I attempted to handle this within the `map_pages` callback in
`iommu_domain_ops`, but that path lacks any awareness of the associated
KVM context, making it unsuitable for this purpose.


> I was kind of thinking it would be nice to have a guestmemfd mode that
> was "pinned", meaning the memory is allocated and remains almost

We need to allocate and free these pages dynamically as they are
converted between private and shared states.

-aneesh

---

## [48] Jason Gunthorpe — 2025-07-29
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

On Tue, Jul 29, 2025 at 01:58:54PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

I suggested a global option, this is a per-device option, and that
especially seems wrong for iommufd. If it is per-device that is vfio,
if it is global then vfio can pick it up during the early phases of
opening the device.

> IIUC, we intend to request the resource in exclusive mode for secure
> guests—regardless of whether the platform is Intel or ARM. Could you

As I understand it Intel MCEs if the non-secure side ever reads from
secure'd address space. So there is alot of emphasis there to ensure
there are no CPU mappings.

Jason

---

## [49] Jason Gunthorpe — 2025-07-29
*Subject: Re: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

On Tue, Jul 29, 2025 at 02:07:55PM +0530, Aneesh Kumar K.V wrote:
> > But it looks really strange to have an iommufd ioctl that just calls a
> > KVM function. Feeling this should be a KVM function, or a guestmfd

There is no IOAS here because the secure world is using the KVM page
table. Since KVM owns this I don't see why iommufd should be invovled
in any way.

You need KVM to push the guestmemfd to the RMM and pin all the memory.

> > I was kind of thinking it would be nice to have a guestmemfd mode that
> > was "pinned", meaning the memory is allocated and remains almost

That's still within guestmemfd's area of concern and it can
immediately pin on state changes.

Jason

---

## [50] Jason Gunthorpe — 2025-07-29
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Tue, Jul 29, 2025 at 01:53:10PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

No, this is no how the PCI specs were written as far as I
understand. The XT bit thing is supposed to add more fine grained
device side control over what memory the DMA can target. T alone does
not do that.

> It is unclear whether devices would need to perform DMA to shared
> (unencrypted) memory while operating in this mode, as TLPs with T=1

PCI SIG supports it, kernel should support it.

Jason

---

## [51] Jonathan Cameron — 2025-07-29
*Subject: Re: [RFC PATCH v1 07/38] iommufd/viommu: Add support to associate
 viommu with kvm instance*

On Mon, 28 Jul 2025 19:21:44 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> The associated kvm instance will be used in later patch by iommufd to
> bind a tdi to kvm.

Is this to undo side effects from this function on error?

kvm_filp is only set after all error paths so maybe this isn't
needed?

If this isn't needed then use __free(fput) and no_free_ptr() to
deal with filp more simply and in teh erorr path can just return -EBADF
directly rather than the goto.

Or are we avoiding that stuff in iommufd?

> +	fput(filp);
> +	return rc;

---

## [52] Jonathan Cameron — 2025-07-29
*Subject: Re: [RFC PATCH v1 08/38] iommufd/tsm: Add tsm_op iommufd ioctls*

On Mon, 28 Jul 2025 19:21:45 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add operations bind and unbind used to bind a TDI to the secure guest.
> 

Hi Aneesh,

I'm mostly reading this to get head around it rather than fully review
at this point.

A few things inline though that I noticed whilst doing so.

Jonathan

> ---
>  drivers/iommu/iommufd/iommufd_private.h |  1 +

> diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
> index 59f1e1176f7f..c934312e5397 100644
Can we use stubs for some of this stuff so we don't need ifdefs in as many
places.

> +	tsm_unbind(idev->dev);
> +#endif

Might want to split this out to a separate c file and use stubs in a header to
keep the code clean here.

> +{
> +	struct iommu_vdevice_tsm_op *cmd = ucmd->cmd;

Wrap comment to say under 80 chars. Or if file goes higher, use a single line
comment.

		  tsm layer will take care ...

(stray 'make')

> +		 */
> +		if (cmd->op == IOMMU_VDEICE_TSM_BIND)

If we want to eat an error code coming from elsewhere, maybe a comment on why?

> +			goto out_put_vdev;
> +		}

If this always skips the next line, does that imply that line should
have been under if (kvm)?  Maybe this makes more sense in
later patches - if so ignore this comment.

> +	}
> +	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));

If you really need to do this, add a comment on why if 0

> +	/*
> +	 * destroy vdevice which involves tsm unbind before we disable pci disable

>  /**
> @@ -1127,6 +1128,23 @@ enum iommu_veventq_flag {

_op I guess?

> + * @op: Either TSM_BIND or TSM_UNBIMD
> + * @flags: Must be 0

---

## [53] Jonathan Cameron — 2025-07-29
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

On Mon, 28 Jul 2025 19:21:48 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Register a platform device if the CCA DA feature is supported.
> A driver for this platform device will further drive the CCA DA workflow.
Few trivial things

> diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
> index ec8093ec2da3..d1c147aba2ed 100644
Hmm. Greg is getting increasingly (and correctly in my view) grumpy with
platform devices being registered with no underlying resources etc as glue
layers.  Maybe some of that will come later. 
> +	.name = RMI_DEV_NAME,
> +	.id = PLATFORM_DEVID_NONE

Add trailing comma. More than possible something else will be added after this.

> +};
> +

Noisy as we should be able to tell that in a bunch of other ways.

> +
Excess blank line.
> +}

---

## [54] Jonathan Cameron — 2025-07-29
*Subject: Re: [RFC PATCH v1 12/38] coco: host: arm64: CCA host platform
 device driver*

On Mon, 28 Jul 2025 19:21:49 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> This driver registers the pci_tsm_ops with tsm subsystem.
> 

Hi Aneesh,

For this main comment is around use of __free..  Dan wrote up guidance and
added to cleanup.h after many email threads kept running into same issues
and Linus added his requirements for that stuff to be acceptable.

Anyhow, easy to fix - comments inline.

> diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
> new file mode 100644

That's going to make for grumpy checkpatch!   More help.


> diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
> new file mode 100644
cleanup.h and maybe others missing.  Basically follow include what you use principles
(flexed a little for headers that are front ends to others).

> +
> +#include "rmm-da.h"

Read the stuff in cleanup.h and work out why this needs
changing to be inline below and not use this NULL pattern here
(unless you like grumpy Linus ;)

Note that with the err_out, even if you do that you'll still be
breaking with the guidance doc (and actually causing undefined
behavior :)  Get rid of those gotos if you want to use __free()


> +
> +	if (pdev->is_virtfn)

Ok. RFC I guess.  Still pci_dbg()

> +	return &no_free_ptr(dsc_pf0)->pci.tsm;
> +

Why? Random mix of direct returns of NULL above and goto here.

> +	return NULL;
> +}

> +
> +static void cca_tsm_disconnect(struct pci_dev *pdev)

Ordering subtly different from error path above.
If there is a reason for that add a comment.

> +}

> +static void cca_tsm_remove(void *tsm_core)
> +{

So this makes two with the one in Dan's test code. 
devm_tsm_register() seems to be a useful generic thing to add (implementation
being exactly what you have here.

> +}
> +
Space before } and don't provide data until there is a use for it.
	{ RMI_DEV_NAME }

> +	{ }
> +};
Consistency on spacing.  I'd go for just 1 blank line for separation
of things.
> +
> +static struct platform_driver cca_tsm_platform_driver = {

---

## [55] Jason Gunthorpe — 2025-07-29
*Subject: Re: [RFC PATCH v1 07/38] iommufd/viommu: Add support to associate
 viommu with kvm instance*

On Tue, Jul 29, 2025 at 05:26:21PM +0100, Jonathan Cameron wrote:
> On Mon, 28 Jul 2025 19:21:44 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

Looks like you are right to me

> If this isn't needed then use __free(fput) and no_free_ptr() to
> deal with filp more simply and in teh erorr path can just return -EBADF

Nope, gentle obvious use is fine :)

Jason

---

## [56] Jason Gunthorpe — 2025-07-29
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Tue, Jul 29, 2025 at 06:10:45PM +0100, Jonathan Cameron wrote:

> > +static struct platform_device cca_host_dev = {
> Hmm. Greg is getting increasingly (and correctly in my view) grumpy with

Is faux_device a better choice? I admit to not knowing entirely what
it is for..

But alternatively, why do we need a dummy "hw" struct device at all?
Typically a subsystem like TSM should be structured to create its own
struct devices..

I would expect this to just call 'register tsm' ?

Jason

---

## [57] Jason Gunthorpe — 2025-07-29
*Subject: Re: [RFC PATCH v1 12/38] coco: host: arm64: CCA host platform device
 driver*

On Tue, Jul 29, 2025 at 06:22:44PM +0100, Jonathan Cameron wrote:
> > +}
> 

Pelase no, this is insane, you have a probed driver with a
probe/remove function pairing already. Why on earth would you use devm
just to call a remove function :(

Just put tsm_unregister() in the normal driver remove like it is
supposed to be done and use the drvdata to pass the tsm_core_dev
pointer. It is easy and normal, look at fwctl for a very simple
example.

devm is useful to solve complex things, these trivial things should be
done normally..

Jason

---

## [58] Xu Yilun — 2025-07-30
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

> diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
> index 6328c3a05bcd..bee3cf3226e9 100644

I did't get the idea.

The purpose of my original patch [1] is not to make VFIO choose between
pci_request_regions_exclusive() or pci_request_regions(). It is mainly
to prevent userspace mmap/read/write against a vfio_cdev FD. For
example:

  If pci_request_selected_regions() is succesfully executed on mmap(),
  later TSM Bind would fail on its pci_request_regions_exclusive(). It
  means userspace should not mmap otherwise you can't do private
  assignment. Vice versa, if you've done TSM Bind, you cannot mmap
  anymore.

The _exclusive is just a bonus that further prevents "/dev/mem and the
sysfs MMIO access"

[1]: https://lore.kernel.org/all/20250529053513.1592088-20-yilun.xu@linux.intel.com/

Thanks,
Yilun

---

## [59] Xu Yilun — 2025-07-30
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

On Tue, Jul 29, 2025 at 11:29:17AM -0300, Jason Gunthorpe wrote:
> On Tue, Jul 29, 2025 at 01:58:54PM +0530, Aneesh Kumar K.V wrote:
> > Jason Gunthorpe <jgg@ziepe.ca> writes:

I think this should be per-device. The original purpose of this
pci_region_request_*() is to prevent further mmap/read/write against
a vfio_cdev FD which would be used for private assignment. You shouldn't
prevent all other devices from working with userspace APPs (e.g. DPDK)
if there is one private assignment in system.

> if it is global then vfio can pick it up during the early phases of
> opening the device.

Yeah, Intel TDX doesn't have a lower access control table for CC. So if
host reads, the TLP sends and MCE happens.

Thanks,
Yilun

> there are no CPU mappings.
>

---

## [60] Aneesh Kumar K.V — 2025-07-30
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Tue, Jul 29, 2025 at 06:10:45PM +0100, Jonathan Cameron wrote:
>

The goal is to have tsm class device to be parented by the platform
device.

# ls -al
total 0
drwxr-xr-x    2 root     root             0 Jan 13 06:07 .
drwxr-xr-x   23 root     root             0 Jan  1 00:00 ..
lrwxrwxrwx    1 root     root             0 Jan 13 06:07 tsm0 -> ../../devices/platform/arm-rmi-dev/tsm/tsm0
# pwd
/sys/class/tsm

-aneesh

---

## [61] Aneesh Kumar K.V — 2025-07-30
*Subject: Re: [RFC PATCH v1 12/38] coco: host: arm64: CCA host platform
 device driver*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:21:49 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

...

>> +
>> +#include "rmm-da.h"

I’ve already fixed up similar cases by removing the goto based on cleanup.h
docs in other functions.I must have missed this one.

By the way, isn't using the `NULL` pattern acceptable when there are
no additional lock variables involved (ie, unwind order doesn't matter)?
Or should we always follow the pattern below regardless?

	struct cca_host_dsc_pf0 *dsc_pf0 __free(vfree) =
		vcalloc(sizeof(*dsc_pf0), GFP_KERNEL);

-aneesh

---

## [62] Suzuki K Poulose — 2025-07-30
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On 29/07/2025 15:33, Jason Gunthorpe wrote:
> On Tue, Jul 29, 2025 at 01:53:10PM +0530, Aneesh Kumar K.V wrote:
>> Jason Gunthorpe <jgg@ziepe.ca> writes:

ACK. On Arm CCA, the device can access shared IPA, with T=1 transaction
as long as the mapping is active in the Stage2 managed by RMM.

Rather than mapping the entire memory from the host, it would be ideal
if the Coco vms have some sort of a callback to "make sure the DMA
wouldn't fault for a device". e.g, it could be as simple as touching
the page in Arm CCA (GFP_ZERO could do the trick, well one byte
per Granule is good). or an ACCEPT a given page.

Is this a problem for AMDE SNP / Intel TDX ?

Suzuki




> 
> Jason

---

## [63] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 12/38] coco: host: arm64: CCA host platform
 device driver*

On Wed, 30 Jul 2025 14:28:55 +0530
Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

> Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:
> 

Always do this.  It's not really about what happens today but
more what we might break by failing to notice a future patch causes
problems.  Keeping the unwind ordering tightly couple with setup
means we basically can't get it wrong (famous last words ;)

Jonathan


> 
> -aneesh

---

## [64] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 12/38] coco: host: arm64: CCA host platform
 device driver*

On Tue, 29 Jul 2025 20:22:43 -0300
Jason Gunthorpe <jgg@ziepe.ca> wrote:

> On Tue, Jul 29, 2025 at 06:22:44PM +0100, Jonathan Cameron wrote:
> > > +}  

Sure, that would be fine for now.  If we end up with a large complex flow that
happens to have a tsm_register() in amongst various managed resources
we can revisit.  If they all end up looking like this then a manual call
in remove is fine.

> 
> Jason

---

## [65] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

On Wed, 30 Jul 2025 14:12:26 +0530
"Aneesh Kumar K.V" <aneesh.kumar@kernel.org> wrote:

> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

I'll go with a cautious yes to faux_device. This case of a glue device
with no resources and no reason to be on a particular bus was definitely
the intent but I'm not 100% sure without trying it that we don't run
into any problems.

Not that many examples yet, but cpuidle-psci.c looks like a vaguely similar
case to this one.  

All it really does is move the location of the device and
smash together the device registration with probe/remove.
That means the device disappears if probe() fails, which is cleaner
in many ways than leaving a pointless stub behind.

Maybe it isn't appropriate it if is actually useful to rmmod/modprobe the
driver. 

+CC Greg on basis I may have wrong end of the stick ;)

> >
> > But alternatively, why do we need a dummy "hw" struct device at all?

> 
> # ls -al

---

## [66] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

On Wed, 30 Jul 2025 11:38:27 +0100
Jonathan Cameron <Jonathan.Cameron@huawei.com> wrote:

> On Wed, 30 Jul 2025 14:12:26 +0530
> "Aneesh Kumar K.V" <aneesh.kumar@kernel.org> wrote:
This time with at least one less typo in Greg's email address.

> 
> > >

---

## [67] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 13/38] coco: host: arm64: Create a PDEV with rmm*

On Mon, 28 Jul 2025 19:21:50 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Create the realm physical device with RMM.
> 
Hi Aneesh,

Various small things inline.

Jonathan

> ---
>  arch/arm64/include/asm/rmi_cmds.h        |  31 +++++

I'd use the enum for the state type and range check in here.


> +{
> +	struct arm_smccc_res res;

Probably keep

> +#define SMC_RMI_PDEV_AUX_COUNT		SMC_RMI_CALL(0x0156)

and add one here as different groups.

>  #define SMC_RMI_REALM_ACTIVATE		SMC_RMI_CALL(0x0157)
>  #define SMC_RMI_REALM_CREATE		SMC_RMI_CALL(0x0158)
Type never used, but I think it should be. See above.

> +	RMI_PDEV_NEW,
> +	RMI_PDEV_NEEDS_KEY,
Seems someone put another state in here, but I guess you'll update
when the rest of the stack catches up.
	RMI_PDEV_IDE_RESETTING,

Maybe throw a comment here for now.

> +	RMI_PDEV_COMMUNICATING,
> +	RMI_PDEV_STOPPING,

I'd stick flags in the name (assuming this is
RmiPDevFlags? I'm not sure as the spec I could
find has different usages other after BIT(!))


> +
> +#define RMI_HASH_SHA_256	0

Whilst we only care about platforms where this is u64, maybe
just make that explicit so we can trivially see this
matches the spec?

> +};
> +

Reference? Looks like B4.4.25 RmiPdevParams type
in alp15.  Though as there are some fields missing
I guess this chagned.

> +	union {
> +		struct {

Called ncoh_ide_side in the alpha 15.  Maybe match that unless
it is changing name in future version.

> +			u64 ncoh_num_addr_range;
> +			u64 coh_num_addr_range;

Maybe pad out the rest?  Mostly so we can see here that it is 4k.

> +};
> +

> diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
> index c8b0e6db1f47..84d97dd41191 100644

Tidy up.  I'd leave it.

> +	/*
> +	 * Take a module reference so that we won't call unregister


> +
> +static int init_pdev_params(struct pci_dev *pdev, struct rmi_pdev_params *params)

Probably makes sense to reduce scope of aux to within the loop.

> +	int rid, ret, i;
> +	phys_addr_t aux_phys;
Only used in one place for now anyway.  Probably better
to move it down there.

> +	struct pci_config_window *cfg = pdev->bus->sysdata;
> +

I'd do that at declaration.  Seems little advantage in doing it
down here.

> +	/* assign the ep device with RMM */
> +	rid = pci_dev_id(pdev);

Spell out epdev or associate it with the pdev here more clearly.

> +	params->rid_top = params->rid_base = rid;
> +	params->ecam_addr = cfg->res.start;

	params->root_id = pci_dev_id(pcie_find_root_port(pdev));
to me acts as better documentation fo what is going on than using
the local variable rp.

> +
> +	params->ncoh_num_addr_range = pci_res_to_pdev_addr(params->ncoh_addr_range,

		void *aux = (void *)__get_free_page(GFP_KERNEL);

> +		aux = (void *)__get_free_page(GFP_KERNEL);
> +		if (!aux) {

I think you want
	free_aux_pages(i, dsc_pf0->aux);
Assuming this is supposed to unwind the loop above.

> +	return -ENOMEM;
> +}
Trivial: Single line probably fine here.
> +
> +int rme_asign_device(struct pci_dev *pci_dev)

Might as well save a line with

	struct cca_host_dsc_pf0 *dsc_pf0 = to_cca_dsc_pf0(pci_dev);

> +	rmm_pdev = (void *)get_zeroed_page(GFP_KERNEL);
> +	if (!rmm_pdev) {

return -ENOMEM;

> +		goto err_out;
> +	}

RFC, but even so I'd demote to debug and use dynamic debug stuff to enable
them for your testing.

> +	if (ret)
> +		goto err_free_aux;

Nothing to unwind in rmi_pdev_create()?  We've told the
RMM about it then we blow away it's resources. Seems unwise!
Maybe this is cleaned up elsewhere but if so a comment is
probably good.

> +
> +	dsc_pf0->rmm_pdev = rmm_pdev;

One of my favourite nitpicks. Why not just return if nothing to do?
That tends to save a reviewer a bit of scrolling when checking
error paths do correct unwinding.

> +	return ret;
> +}

---

## [68] Greg KH — 2025-07-30
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Jul 30, 2025 at 01:23:33PM +0100, Jonathan Cameron wrote:
> On Wed, 30 Jul 2025 11:38:27 +0100
> Jonathan Cameron <Jonathan.Cameron@huawei.com> wrote:

Yes, use faux_device if you need/want a struct device to represent
something in the tree and it does NOT have any real platform resources
behind it.  That's explicitly what it was designed for.

thanks,

greg k-h

---

## [69] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 14/38] coco: host: arm64: Device communication
 support*

On Mon, 28 Jul 2025 19:21:51 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add helpers for device communication from RMM
> 

>  #endif /* __ASM_RMI_CMDS_H */
> diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h

>  
> +#define RMI_DEV_COMM_EXIT_CACHE_REQ	BIT(0)
In latest spec called rsp_timeout.
Not sure we care that much but if no strong reason otherwise, should
aim to match the spec text. (Maybe this got renamed?)
> +};

> diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
> index 84d97dd41191..294a6ef60d5f 100644

Hmm. There isn't a DEFINE_FREE() yet for free_page().  Maybe time to add one.
If we did then we'd use local variables until all allocations succeed then
assign with no_free_ptr()


> +	if (!comm_data->io_params)
> +		goto err_out;
I think it's already a a void * and even if it were some other pointer type
no cast would be necessary.

> +	comm_data->io_params->enter.resp_len = 0;
> +

> +
>  /* per root port unique with multiple restrictions. For now global */
	rme_assign_device() - I obviously missed this earlier!

> +	/*
> +	 * Schedule a work to fetch device certificate and setup IDE
Single line comment probably fine here.  Though it perhaps doesn't add
much over the function name.
> +	 */
> +	schedule_rme_ide_setup(pdev);

For all these I'd combine with the declarations.

> +
> +	pr_debug("doe_req size:%lld doe_io_type=%d\n", io_exit->req_len, (int)protocol);

Might as well set these local variables as the declaration point
above.  None of them will be very long lines.

> +
> +	dsc_pf0 = to_cca_dsc_pf0(tsm->dsm_dev);

I'd split this case out and return here farther than using the match below
as it feels like the error message auto to be more specific. Something
about type not matching.

> +	if (ret != RMI_SUCCESS) {
> +		pr_err("pdev communicate error\n");

!! doesn't add anything here that I can see over

	is_multi = io_exit->flags & RMI_DEV_COMM_EXIT_MULTI;


> +
> +	/* next packet to send */
		if (ret)

> +			pr_err("dev communication error\n");
> +			break;

I'd just return in error cases.

> +		}
> +

---

## [70] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 15/38] coco: host: arm64: Stop and destroy the
 physical device*

On Mon, 28 Jul 2025 19:21:52 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add support for stopping and destroying physical devices.

I think it's an odd mix to not do create and destroy in a single patch.
Same with start and stop.
Leaves reviewers thinking perhaps you weren't cleaning up properly
an any error paths are much less obvious.

> 
> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

As with previous patches, I'd set as many of these are seems reasonable at the
variable declations.

> +	ret = rmi_pdev_stop(rmm_pdev_phys);
> +	if (WARN_ON(ret != RMI_SUCCESS))
WARN_ON is rather heavy if you want to ignore it.

> +	WARN_ON(state != RMI_PDEV_STOPPED);
> +	ret = rmi_pdev_destroy(rmm_pdev_phys);

---

## [71] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 19/38] coco: host: arm64: set_pubkey support*

On Mon, 28 Jul 2025 19:21:56 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add changes to share the device's public key with the RMM.
> 

A few minor comments inline.

> diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
> index ec8c5bfcee35..3715e6d58c83 100644

Direct return looks fine here.  Maybe add a DEFINE_FREE(x509_cert,...)
as then can use direct returns throughout.


> +			break;
> +		}
	if (ret)
		return ret;

	dsc_pf0->cert_chain.valid = true;

	return 0;

would be my preference for style here but others may disagree.
> +
> +	return ret;

Don't set this. It's only used in places where it is explicitly set and
if it is used anywhere else we want the compiler to tell us.

> +	struct cca_host_dsc_pf0 *dsc_pf0;
> +	int ret;

Shouldn't define this inline.  Maybe move up a line and add some {}
to set the scope to this case statement.

> +		int ret_rsa_parse = rsa_parse_pub_key(&rsa_key,
> +						      dsc_pf0->cert_chain.public_key,

Why is the cast needed?


> +		memcpy(key_shared->metadata, (unsigned char *)rsa_key.e, rsa_key.e_sz);
> +		break;

---

## [72] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 20/38] coco: host: arm64: Add support for
 creating a virtual device*

On Mon, 28 Jul 2025 19:21:57 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Changes to support the creation of virtual device objects with RMM.
> 
Hi Aneesh,

Really trivial stuff in this one.

> diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
> index 4a5ba98c1c0d..e5238b271493 100644

One blankl line probably enough.

>  
>  #define RMI_ABI_MAJOR_VERSION	1

t/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
> index c65b81f0706f..2da513f45974 100644
> --- a/drivers/virt/coco/arm-cca-host/arm-cca.c

Move declaration and registration of destructor down to where it's
constructed. (Follow guidance in cleanup.h.

> +	struct realm *realm = &kvm->arch.realm;
> +
Odd spacing.  Seems just bind is using a tab.

>  };

---

## [73] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 21/38] coco: host: arm64: Add support for virtual
 device communication*

On Mon, 28 Jul 2025 19:21:58 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add support for vdev_communicate with RMM.
> 

One minor comment.

> diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
> index 41314db1d568..8635f361bbe8 100644

Can type parameter be an enum so we can see all cases are covered?

>  	if (type == PDEV_COMMUNICATE)
>  		ret = rmi_pdev_communicate(virt_to_phys(dsc_pf0->rmm_pdev),

---

## [74] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 22/38] coco: host: arm64: Stop and destroy
 virtual device*

On Mon, 28 Jul 2025 19:21:59 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add support for vdev_stop and vdev_destroy.
> 
Really trivial comments.

> ---
>  arch/arm64/include/asm/rmi_cmds.h        | 21 ++++++++
One is enough.

> +
>  #endif /* __ASM_RMI_CMDS_H */

There have been a few of these. Check v2 carefully to make sure
no more sneak in.

> +#define SMC_RMI_VDEV_STOP		SMC_RMI_CALL(0x018A)
>  

>  static void cca_tsm_remove(void *tsm_core)
> diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c

> +void rme_unbind_vdev(struct realm *realm, struct pci_dev *pdev, struct pci_dev *pf0_dev)
> +{

No point in returning here.  Maybe fine to keep this if more code
is coming after this in future patches.

> +	}
> +}

---

## [75] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 23/38] coco: guest: arm64: Update arm CCA guest
 driver*

On Mon, 28 Jul 2025 19:22:00 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> This patch includes renaming changes to simplify the registration of a
> TSM backend in the next patch. There are no functional changes in this

> index 0c9ea24a200c..547fc2c79f7d 100644
> --- a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c

> +static int cca_guest_probe(struct platform_device *pdev)
...
> +	ret = devm_add_action_or_reset(&pdev->dev, unregister_cca_tsm_report, NULL);
>  

	return devm_add_action_or_reset()

Mind you, Jason probably won't like this ;)
>  }


>  MODULE_AUTHOR("Sami Mujawar <sami.mujawar@arm.com>");
> -MODULE_DESCRIPTION("Arm CCA Guest TSM Driver");

Is this D/d worth the noise?

>  MODULE_LICENSE("GPL");

---

## [76] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 24/38] arm64: CCA: Register guest tsm callback*

On Mon, 28 Jul 2025 19:22:01 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Register the TSM callback if the DA feature is supported by RSI.
> 
See below.

> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
> index bf9ea99e2aa1..ef06c083990a 100644

!! not needed.

> +}
> +EXPORT_SYMBOL_GPL(rsi_has_da_feature);


> diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
> index 547fc2c79f7d..3adbbd67e06e 100644

>  static int cca_guest_probe(struct platform_device *pdev)
>  {
Why do we not need to call unregister_cca_tsm_report()
if this fails?

>  
> +err_out:
I'd just return above.

>  	return ret;
>  }
One blank line probably enough.
> +
> +struct cca_guest_dsc {

---

## [77] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 25/38] cca: guest: arm64: Realm device lock
 support*

On Mon, 28 Jul 2025 19:22:02 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Writing 1 to 'tsm/lock' will initiate the TDISP lock sequence.
> 

Seems unrelated change. 

> +}
> +

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> new file mode 100644

> +int rsi_device_lock(struct pci_dev *pdev)
> +{
return 0? 

You carefully overwrite other error codes. I assume RSI_SUCCESS == 0 but
even better to just return 0 directly in the good path.

> +}
> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h

Push back to earlier patch where I comment on this.

>  struct cca_guest_dsc {
>  	struct pci_tsm_pf0 pci;

---

## [78] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 26/38] KVM: arm64: Add exit handler related to
 device assignment*

On Mon, 28 Jul 2025 19:22:03 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Different RSI calls related to DA result in REC exits. Add a facility to
> register handlers for handling these REC exits.


> diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
> index c6e16ab608e1..a5ef68b62bc0 100644

> diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
> index 1a8ca7526863..25948207fc5b 100644


> +static int rec_exit_dev_mem_map(struct kvm_vcpu *vcpu)
> +{

I guess maybe this gets more complex later, but right now
		return 0;

And maybe return in the if branch as well.
Same for other similar code in this patch.

> +	}
> +	return ret;

---

## [79] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 30/38] coco: host: arm64: Add support for realm
 host interface (RHI)*

On Mon, 28 Jul 2025 19:22:07 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Device assignment-related RHI calls result in a REC exit, which is
> handled by the tsm guest_request callback.

Comments below.

> ---
>  arch/arm64/include/asm/rhi.h             | 32 ++++++++++

> diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
> index be1296fb1bf2..0807fcf8d222 100644

> +static int cca_tsm_guest_req(struct pci_dev *pdev, struct tsm_guest_req_info *info)
> +{
			return 0;
then else isn't needed.

> +		} else

#Style is {} on all legs if any need it.

> +			/* error */
> +			ret = object_size;
			return object_size;

> +		break;
> +	}
Similar to above.
> +		} else
> +			/* error */
As you've probably figured out, I love an early return.  This sort
of function shows why as it reduced indent etc in lots of places.
Here you mix and match. Maybe it will make sense later in the series though!

> +}

> diff --git a/drivers/virt/coco/arm-cca-host/rmm-da.c b/drivers/virt/coco/arm-cca-host/rmm-da.c
> index bef33e618fd3..c7da9d12f258 100644

Similar to below. This pattern just makes things more complex.
If we need to introduce a label, do it in the patch where you add
code to do something on error.

> +	return ret;
> +}

Definitely makes sense to just return directly in the error paths above and
just return len here


> +	return ret;
> +}

---

## [80] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 31/38] coco: guest: arm64: Add support for
 fetching interface report and certificate chain from host*

On Mon, 28 Jul 2025 19:22:08 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Fetch interface report and certificate chain from the host using RHI calls.
> 

Comments inline

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index 28ec946df1e2..47b379318e7c 100644

Extra space.

> +		goto err_out;
> +	}

extra space.  All of these seem to have one.  Not seeing a reason for it
though.


> +		goto err_out;
> +	}
I'd expect there to be nothing to do except return under an err_out label
So rename it.

> +	*report = NULL;
> +	*report_size = 0;

>  	return ret;
return 0;

>  }

---

## [81] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 32/38] coco: guest: arm64: Add support for guest
 initiated TDI bind/unbind*

On Mon, 28 Jul 2025 19:22:09 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add RHI for VDEV_SET_TDI_STATE
> 

A few minor comments. 

Maybe we need some discussion of how this is used.

> diff --git a/arch/arm64/kernel/rhi.c b/arch/arm64/kernel/rhi.c
> new file mode 100644
	struct rsi_host_call *rhi_call __free(kfree) =
		kmalloc(sizeof(*rhi_call), GFP_KERNEL);

then direct returns on errors.

> +	if (!rhi_call)
> +		return -ENOMEM;

Push this earlier. It doesn't do any harm that I can see and will reduce churn

> +	int vdev_id = (pci_domain_nr(pdev->bus) << 16) |
> +		PCI_DEVID(pdev->bus->number, pdev->devfn);

>  
>  static const struct pci_tsm_ops cca_pci_ops = {

Tidy up these whitespace changes.  Just adds noise.

>  	module_put(THIS_MODULE);
>  }

---

## [82] Jonathan Cameron — 2025-07-30
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On Mon, 28 Jul 2025 19:22:11 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> This starts the sequence to transition the realm device to the TDISP RUN
> state by writing 1 to 'tsm/accept'.
Just some trivial stuff.


> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index 47b379318e7c..936f844880de 100644

> +
> +int rsi_update_interface_report(struct pci_dev *pdev, bool validate)
Single line.
> +	interface_report = (struct pci_tdisp_device_interface_report *)dsm->interface_report;
> +	mmio_range = (struct pci_tdisp_mmio_range *)(interface_report + 1);
Single line

> +	msix_tbl_bar = get_msix_bar(pdev, PCI_MSIX_TABLE);
> +	msix_pba_bar = get_msix_bar(pdev, PCI_MSIX_PBA);

That first condition can get hiked out of the loop.

> +			pr_info("Skipping misx table\n");
> +			continue;

Likewise.

> +			pr_info("Skipping misx pba\n");
> +			continue;
resource_size() 
> +			pci_warn(pdev, "Skipping broken range [%d] #%d %d pages, %llx..%llx\n",
> +				i, range_id, mmio_range->num_pages, r->start, r->end);

---

## [83] Jason Gunthorpe — 2025-07-30
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

On Mon, Jul 28, 2025 at 07:21:37PM +0530, Aneesh Kumar K.V (Arm) wrote:
> This patch series implements support for Device Assignment in the ARM CCA
> architecture. The code changes are based on Alp12 specification published here

Robin and I were talking about CCA and DMA here:

https://lore.kernel.org/r/6c5fb9f0-c608-4e19-8c60-5d8cef3efbdf@arm.com

What do you think about pulling some of this out and trying to
independently push a series getting the DMA API layers ready for
device assignment?

I think there will be some discussion on these points, it would be
good to get started.

Jason

---

## [84] Jonathan Cameron — 2025-07-31
*Subject: Re: [RFC PATCH v1 37/38] coco: guest: arm64: Add support for
 fetching device measurements*

On Mon, 28 Jul 2025 19:22:14 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Fetch device measurements using RSI_RDEV_GET_MEASUREMENTS.
> 
One completely trivial comment.

J
> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index 64034d220e02..6222b10964ee 100644

> @@ -213,6 +245,13 @@ int rsi_device_lock(struct pci_dev *pdev)
>  		return -EIO;

return 0;  Always good to make it explicit when it can't take any other values.
Looks like that belong sin an earlier patch though based on this snippet.


>  }

---

## [85] Jonathan Cameron — 2025-07-31
*Subject: Re: [RFC PATCH v1 38/38] coco: guest: arm64: Add support for
 fetching device info*

On Mon, 28 Jul 2025 19:22:15 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> RSI_RDEV_GET_INFO returns different digest hash values, which can be
> compared with host cached values to ensure the host didn't tamper with
Hi Aneesh

A few comments on this one

Jonathan

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index 6222b10964ee..a1bb225adb4c 100644

This to me smells like a place that will need switch sooner or
later, maybe just do it now.

> +		hash_alg_name = "sha256";
> +		digest_size = SHA256_DIGEST_SIZE;

return -EINVAL;

> +		goto err_out;
> +	}
As below - I'd spin a DEFINE_FREE() for this to simplify error
paths in here and remove the labels that had me confused briefly.

> +	if (IS_ERR(alg)) {
> +		pci_err(pdev, "cannot allocate %s\n", hash_alg_name);

Not common in crypto so perhaps just leave this as you have it.

	sdesc_size = struct_size(struct shash_dec, __ctx, crypto_shash_desc_size(alg));

is more informative on what is going on here.


> +	shash = kzalloc(sdesc_size, GFP_KERNEL);
> +	if (!shash) {

To me a bit marginal on whether this loop and the structures above
are beneficial over straight line code.

> +		if (ret) {
> +			pci_err(pdev, "failed to compute digest, %d\n", ret);

debug.

> +	return 0;
> +
I'd tweak these labels if you keep them. This isn't freeing the sdesc.

> +	kfree(shash);
Looks perfect for some __free() magic dust.
> +err_free_shash:
> +	crypto_free_shash(alg);

DEFINE_FREE() needed for this but looks pretty uncontroversial.

> +err_out:
As below. I'd not do this.

> +	return ret;
> +}

Use a __free(kfree) here (and direct returns on errors) given it's freed
in all paths and we don't care if it is freed before or after verifying the digests.

I'm being slow today, but what in that enforces the alignment?  I guess
it's that the structure happens to be big enough that it happens naturally?

I'd allocate max(512, sizeof(*dev_info)) to make it explicitly the case.

> +	if (!dev_info) {
> +		ret = -ENOMEM;

Can't you memcpy the whole thing in one go?

> +	kfree(dev_info);
> +	/*
I'll always grumble about these.  To me it always makes the code
less readable. Some others disagree though ;( 
>  	return ret;
>  }

Looks like this should have been in an earlier patch.

>  static inline unsigned long rsi_rdev_start(struct pci_dev *pdev,
>  					   unsigned long vdev_id, unsigned long inst_id)

One probably enough.

> +
>  struct cca_guest_dsc {

---

## [86] Jonathan Cameron — 2025-07-31
*Subject: Re: [RFC PATCH v1 35/38] coco: guest: arm64: Add Realm device start
 and stop support*

On Mon, 28 Jul 2025 19:22:12 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Writing 1 to 'tsm/acceept' will initiate the TDISP RUN sequence.
> 

A few more trivial things on this first read through.

Jonathan

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index 936f844880de..64034d220e02 100644

> +int rsi_device_stop(struct pci_dev *pdev)
> +{

Feels like this occurs so often we should add a helper.
Can't be completely generic as pci_domain_nr can have more bits
than I guess we are assuming here, but we can have something for
use in the rsi code.


> +
> +	ret = rsi_rdev_stop(pdev, vdev_id, dsm->instance_id);

Tidy this up.

> +int rsi_device_stop(struct pci_dev *pdev);
>  #endif

---

## [87] Arto Merilainen — 2025-07-31
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On 28.7.2025 16.52, Aneesh Kumar K.V (Arm) wrote:

> +	for (int i = 0; i < interface_report->mmio_range_count; i++, mmio_range++) {
> +


MSI-X and PBA can be placed to a BAR that has other registers as well. 
While the PCIe specification recommends BAR-level isolation for MSI-X 
structures, it is not mandated. It is enough to have sufficient 
isolation within the BAR. Therefore, skipping the MSI-X and PBA BARs 
altogether may leave registers unintentionally mapped via unprotected 
IPA when they should have been mapped via protected IPA.

Instead of skipping the whole BAR, would it make sense to determine
where the MSI-X related regions reside, and skip validation only from 
these regions?

- R2

---

## [88] Arto Merilainen — 2025-07-31
*Subject: Re: [RFC PATCH v1 13/38] coco: host: arm64: Create a PDEV with rmm*

On 28.7.2025 16.51, Aneesh Kumar K.V (Arm) wrote:

> +static int pci_res_to_pdev_addr(struct rmi_pdev_addr_range *pdev_addr,
> +				unsigned int naddr, struct resource *res,

I think there is an off-by-one bug in res[j].end. As per the RMM 
specification the base address is inclusive and the top address is 
exclusive. Both res[j].start and res[j].end are inclusive, and hence
res[j].end seems wrong.

> +	/* use the rid and MMIO resources of the epdev */
> +	params->rid_top = params->rid_base = rid;

Similar issue here. As per the specification the rid_base is inclusive 
and the rid_top exclusive.

- R2

---

## [89] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Jul 30, 2025 at 11:38:27AM +0100, Jonathan Cameron wrote:
> On Wed, 30 Jul 2025 14:12:26 +0530
> "Aneesh Kumar K.V" <aneesh.kumar@kernel.org> wrote:

Yeah, exactly. Can a TSM driver even be modular? If it has to be built
in then there is no reason to do this:

> > The goal is to have tsm class device to be parented by the platform
> > device.

IMHO the only real point of that is to trigger module autoloading.

Otherwise the tsm core should accept NULL as the parent pointer during
registration, it probably already does..

Jason

---

## [90] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Wed, Jul 30, 2025 at 11:09:35AM +0100, Suzuki K Poulose wrote:
> > > It is unclear whether devices would need to perform DMA to shared
> > > (unencrypted) memory while operating in this mode, as TLPs with T=1

Right, I expect that the T=0 SMMU S2 translation is a perfect subset of
the T=1 S2 rmm translation. At most pages that are not available to
T=0 should be removed when making the subset.

I'm not sure what the plan is here on ARM though, do you expect to
pre-load the entire T=0 SMMU S2 with the shared IPA aliases and rely
on the GPT for protection or will the hypervisor dynamically change
the T=0 SMMU S2 after each shared/private change? Same question for
the RMM S2?

The first option sounds fairly appealing, IMHO

> Rather than mapping the entire memory from the host, it would be ideal
> if the Coco vms have some sort of a callback to "make sure the DMA

Isn't that a different topic? For right now we expect that all pages
are pinned and loaded into both S2s. Upon any private/shared
conversion the pages should be reloaded into the appropriate S2s if
required. The VM never needs to tell the hypervisor that it wants to
do DMA.

There are all sorts of options here to relax this but exploring them
it an entirely different project that CCA, IMHO.

Jason

---

## [91] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

On Wed, Jul 30, 2025 at 02:55:02PM +0800, Xu Yilun wrote:
> On Tue, Jul 29, 2025 at 11:29:17AM -0300, Jason Gunthorpe wrote:
> > On Tue, Jul 29, 2025 at 01:58:54PM +0530, Aneesh Kumar K.V wrote:

IMHO there is no use case for that, it should arguably be global to
the whole kernel.

> The original purpose of this pci_region_request_*() is to prevent
> further mmap/read/write against a vfio_cdev FD which would be used

No way, the VFIO internal mmap should be controled by VFIO not by
request region. If you want to block that it should be blocked by
iommufd telling VFIO that the device is bound which revokes the
mmaps/dmabufs/etc and prevents opening new ones.

The only thing request region should do is prevent /sys/../resource,
/dev/mem users and so on, which is why it can and should be
global. Arguably VFIO should always block those things but
historically hasn't..

There should only be one request region call in VFIO, it should
ideally happen when the VFIO driver probes the device.

Jason

---

## [92] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 12/38] coco: host: arm64: CCA host platform device
 driver*

On Wed, Jul 30, 2025 at 11:28:04AM +0100, Jonathan Cameron wrote:
> > devm is useful to solve complex things, these trivial things should be
> > done normally..

IMHO just don't use devm, it is so easy to use devm wrong and get out
of order clean up. It works well for extremely simple case where 100%
of cleanup is in devm (but then it is questionable if the overhead is
worthwehile), and it is necessary for extremely hard cases where
writing a manual unwind is too hard. But the middle ground it tends to
just make ordering bugs and not provide alot of value, IMHO.

Jason

---

## [93] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 14/38] coco: host: arm64: Device communication
 support*

On Wed, Jul 30, 2025 at 02:52:48PM +0100, Jonathan Cameron wrote:
> > +static int init_dev_communication_buffers(struct cca_host_comm_data *comm_data)
> > +{

Maybe think carefully if you really need a "page".

What would prevent just using kzalloc(PAGE_SIZE)? Under the covers it
is almost the same thing.

Jason

---

## [94] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 23/38] coco: guest: arm64: Update arm CCA guest
 driver*

On Wed, Jul 30, 2025 at 03:22:04PM +0100, Jonathan Cameron wrote:
> > -static void __exit arm_cca_guest_exit(void)
> > -{

devm in a module __exit function? How ?

Jason

---

## [95] Jonathan Cameron — 2025-07-31
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

On Thu, 31 Jul 2025 09:11:33 -0300
Jason Gunthorpe <jgg@ziepe.ca> wrote:

> On Wed, Jul 30, 2025 at 11:38:27AM +0100, Jonathan Cameron wrote:
> > On Wed, 30 Jul 2025 14:12:26 +0530

If you mean create a class device with no parent, that's also something
we are slowly trying to fix.  Reminds me that fixing up more perf devices
is still on my todo list.

Should be a child of something, so maybe that is a good reason for a
faux_device here if there is nothing else to use.

Jonathan

> 
> Jason

---

## [96] Suzuki K Poulose — 2025-07-31
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On 31/07/2025 13:17, Jason Gunthorpe wrote:
> On Wed, Jul 30, 2025 at 11:09:35AM +0100, Suzuki K Poulose wrote:
>>>> It is unclear whether devices would need to perform DMA to shared

Yes, this is what the VMM is supposed to do today, see [0] & [1].

> 
> I'm not sure what the plan is here on ARM though, do you expect to

Yes, share/private transitions do go all the way back to VMM and it
is supposed to make the necessary changes to the SMMU S2 (as in [1]).

> the RMM S2?
> 

As for the RMM S2, the current plan is to re-use the CPU S2 managed
by RMM.

> The first option sounds fairly appealing, IMHO
> 

Actually it is. But might solve the problem for confidential VMs,
where the S2 mapping is kind of pinned.

Population of S2 is a bit tricky for CVMs, as there are restrictions
due to :
   1) Pre-boot measurements
   2) Restrictions on modifying the S2 (at least on CCA).

Thus, "the preload S2 and pin" must be done, after the "Initial images 
are loaded". And that becomes tricky from the Hypervisor (thinking of 
this, the VMM may be able to do this properly, as long as it remembers
which areas where loaded).

Filling in the S2, with already populated S2 is complicated for CCA
(costly, but not impossible). But the easier way is for the Realm to
fault in the pages before they are used for DMA (and S2 mappings can be
pinned by the hyp as default). Hence that suggestion.

Suzuki

[0] https://gitlab.arm.com/linux-arm/kvmtool-cca/-/commit/7c34972ddc
[1] https://gitlab.arm.com/linux-arm/kvmtool-cca/-/commit/ab4e654c4

> conversion the pages should be reloaded into the appropriate S2s if
> required. The VM never needs to tell the hypervisor that it wants to

> 
> There are all sorts of options here to relax this but exploring them

---

## [97] Jonathan Cameron — 2025-07-31
*Subject: Re: [RFC PATCH v1 23/38] coco: guest: arm64: Update arm CCA guest
 driver*

On Thu, 31 Jul 2025 09:29:48 -0300
Jason Gunthorpe <jgg@ziepe.ca> wrote:

> On Wed, Jul 30, 2025 at 03:22:04PM +0100, Jonathan Cameron wrote:
> > > -static void __exit arm_cca_guest_exit(void)
More coffee time... 

> 
> Jason

---

## [98] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Thu, Jul 31, 2025 at 02:48:23PM +0100, Suzuki K Poulose wrote:
> On 31/07/2025 13:17, Jason Gunthorpe wrote:
> > On Wed, Jul 30, 2025 at 11:09:35AM +0100, Suzuki K Poulose wrote:

Okay great!

> > I'm not sure what the plan is here on ARM though, do you expect to
> > pre-load the entire T=0 SMMU S2 with the shared IPA aliases and rely

Okay, it works, but also why?

From a hypervisor perspective when using VFIO I'd like the guestmemfd
to fix all the physical memory immediately, so the entire physical map
is fixed and known. Backed by 1G huge pages most likely.

Is there a reason not to just dump that into the T=0 SMMU using 1G
huge pages and never touch it again? The GPT provides protection?

Sure sounds appealing..

> As for the RMM S2, the current plan is to re-use the CPU S2 managed
> by RMM.

Yes, but my question is if the CPU will be prepopulated
 
> Actually it is. But might solve the problem for confidential VMs,
> where the S2 mapping is kind of pinned.

Not kind of pinned, it is pinned in the hypervisor..
 
> Population of S2 is a bit tricky for CVMs, as there are restrictions
> due to :

I haven't dug into any of this, but I'd challenge you to try to make
it run fast if the guestmemfd has a full fixed address map in 1G pages
and could just dump them into the RMM efficiently once during boot.

Perhaps there are ways to optimize the measurements for huge amounts
of zero'd memory.

> Filling in the S2, with already populated S2 is complicated for CCA
> (costly, but not impossible). But the easier way is for the Realm to

I guess, but it's weird, kinda slow, and the RMM can never unfault them..

How will you reconstruct the 1G huge pages in the S2 if you are only
populating on faults? Can you really fault the entire 1G page? If so
why can't it be prepopulated?

Jason

---

## [99] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Thu, Jul 31, 2025 at 02:22:50PM +0100, Jonathan Cameron wrote:

> If you mean create a class device with no parent, that's also something
> we are slowly trying to fix.  Reminds me that fixing up more perf devices

IIRC if you create a class device with no parent it gets placed on the
virtual bus...

Do you mean we should not do that?

> Should be a child of something, so maybe that is a good reason for a
> faux_device here if there is nothing else to use.

Don't see such a big difference to have it be the child of a faux
device on the faux bus than to just be directly on the virtual bus?

Jason

---

## [100] Jason Gunthorpe — 2025-07-31
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On Thu, Jul 31, 2025 at 02:39:09PM +0300, Arto Merilainen wrote:
> On 28.7.2025 16.52, Aneesh Kumar K.V (Arm) wrote:
> 

Right, there are not enough BARs in most devices to give MSI its own
BAR.

>  It is enough to have sufficient isolation within the
> BAR. Therefore, skipping the MSI-X and PBA BARs altogether may leave

Right, this sounds bad.

> Instead of skipping the whole BAR, would it make sense to determine
> where the MSI-X related regions reside, and skip validation only from these

IMHO this is a mess. The virtualization must end up putting a shared
page(s) covering the MSI space in the middle of the MMIO region.

I think this should be done by fragmenting the layout in the IPA where
the private MMIO is within the protected IPA space with an unmapped
hole covering the MSIX registers. The acceptance process should
validate this.

The MSIX registers would then be located in the shared IPA space.

A normal driver mmaping it's BAR will then crash if it tries to access
the MSIX registers. This is good, we want to catch these non-secure
configurations and block them.

The MSI code will have to know to compute the shared IPA alias and use
that.

Jason

---

## [101] dan.j.williams@intel.com — 2025-07-31
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

Aneesh Kumar K.V (Arm) wrote:
> This patch series implements support for Device Assignment in the ARM CCA
> architecture. The code changes are based on Alp12 specification published here

Just for my own understanding... presumably there is no ordering
constraint for ARM CCA between step1 and step2, right? I.e. The connect
state is independent of the bind state.

In the v4 PCI/TSM scheme the connect command is now:

echo $tsm_dev > /sys/bus/pci/devices/$DEVICE/tsm/connect

> Now in the guest we follow the below steps

I assume a signifcant amount of kvmtool magic happens here to get the
TDI into a "bind capable" state, can you share that command?

I had been assuming that everyone was prototyping with QEMU. Not a
problem per se, but the memory management for shared device assignment /
bounce buffering has had a quite of bit of work on the QEMU side, so
just curious about the difference in approach here. Like, does kvmtool
support operating the device in shared mode with bounce buffering and
page conversion (shared <=> private) support? In any event, happy to see
mutiple simultaneous consumers of this new kernel infrastructure.

> step 1:
> echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind

Ok, so my stance has recently picked up some nuance here. As Jason
mentions here:

http://lore.kernel.org/20250410235008.GC63245@ziepe.ca

"However it works, it should be done before the driver is probed and
remain stable for the duration of the driver attachment. From the
iommu side the correct iommu domain, on the correct IOMMU instance to
handle the expected traffic should be setup as the DMA API's iommu
domain."

I agree with that up until the point where the implication is userspace
control of the UNLOCKED->LOCKED transition. That transition requires
enabling bus-mastering (BME), configuring the device into an expected
state, and *then* locking the device. That means userspace is blindly
hoping that the device is in a state where it will remain quiet on the
bus between BME and LOCKED, and that the previous unbind left the device
in a state where it is prepared to be locked again.

The BME concern may be overblown given major PCI drivers blindly set BME
without validating the device is in a quiesced state, but the "device is
prepped for locking" problem seems harder.

2 potential ways to solve this, but open to other ideas:

- Userspace only picks the iommu domain context for the device not the
  lock state. Something like:

  private > /sys/bus/pci/devices/${DEVICE}/tsm/domain

  ...where the default is "shared" and from that point the device can
  not issue DMA until a driver attaches.  Driver controls
  UNLOCKED->LOCKED->RUN.

- Userspace is not involved in this transition and the dma mapping API
  is updated to allow a driver to switch the iommu domain at runtime,
  but only if the device has no outstanding mappings and the transition
  can only happen from ->probe() context. Driver controls joining
  secure-world-DMA and UNLOCKED->LOCKED->RUN.

Clearly the first option is less work in the kernel, but in both options
the driver is in control of when BME is set relative to being ready for
the LOCKED transition.
  
> step 3: Moves the device to TDISP RUN state
> echo 1 > /sys/bus/pci/devices/${DEVICE}/tsm/accept

This has the same concern from me about userspace being in control of
BME. It feels like a departure from typical expectations.  At least in
the case of a driver setting BME the driver's probe routine is going to
get the device in order shortly and otherwise have error handlers at the
ready to effect any needed recovery.

Userspace just leaves the device enabled indefinitely and hopes.

Now, the nice thing about the scheme as proposed in this set is that
userspace has all the time in the world between "lock" and "accept" to
talk to a verifier.

With the driver in control there would need to be something like a
usermodehelper to notify userspace that the device is in the locked
state and to go ahead and run the attestation while the driver waits*.

* or driver could decide to not wait, especially useful for debug and
  development

> step 4: Load the driver again.
> echo ${DEVICE} > /sys/bus/pci/drivers_probe

TIL drivers_probe

Maybe want to recommend:

echo ${DEVICE} > /sys/bus/pci/drivers/${DRIVER}/bind

...to users just in case there are multiple drivers loaded for the
device for the "shared" vs "private" case?

> I'm currently working against TSM v3, as TSM v4 lacks the necessary
> callbacks—bind, unbind, and guest_req—required for guest interactions.

For staging purposes I wanted to put the "connect" flow to bed before
moving on to the guest side.

> The implementation also makes use of RHI interfaces that fall outside the
> current RHI specification [5]. Once the spec is finalized, the code will be aligned

Thanks for this and the help reviewing PCI/TSM so far! I want to get
this into tsm.git#staging so we can start to make hard claims ("look at
the shared tree!") of hardware vendor consensus.

---

## [102] Greg KH — 2025-08-01
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Thu, Jul 31, 2025 at 01:46:03PM -0300, Jason Gunthorpe wrote:
> On Thu, Jul 31, 2025 at 02:22:50PM +0100, Jonathan Cameron wrote:
> 

Either is fine, but just never use a platform device for a
non-platform-resource-backed device please.

thanks,

greg k-h

---

## [103] Suzuki K Poulose — 2025-08-01
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On 31/07/2025 17:44, Jason Gunthorpe wrote:
> On Thu, Jul 31, 2025 at 02:48:23PM +0100, Suzuki K Poulose wrote:
>> On 31/07/2025 13:17, Jason Gunthorpe wrote:

That is possible, once we get guest_memfd mmap support merged upstream.
GPT does provide protection. The only caveat is, does the guest_memfd
support this at all ? i.e., shared->private transitions with a shared
mapping in place (Though this is in SMMU only, not the Host CPU
pagetables)


> 
> Sure sounds appealing..

There is. We (VMM) can choose not to "measure" the zero'd pages.


>> Filling in the S2, with already populated S2 is complicated for CCA
>> (costly, but not impossible). But the easier way is for the Realm to

It is tricky to prepopulate the 1G page, as parts of the pages may be
"populated" with contents. We can recreate the 1G block mapping by
"FOLD" ing the leaf level tables, all the way upto 1G, after the
mappings are created. We have to do that anyway for CCA.

I think we can go ahead with VMM pre-populating the entire DRAM
and keeping it pinned for DA. Rather than doing this from the
vfio kernel, it could be done by the VMM as it has better knowledge
of the populated contents and map the rest as "unmeasured" 0s.

Suzuki

---

## [104] Jason Gunthorpe — 2025-08-01
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Fri, Aug 01, 2025 at 10:30:35AM +0100, Suzuki K Poulose wrote:
> > Is there a reason not to just dump that into the T=0 SMMU using 1G
> > huge pages and never touch it again? The GPT provides protection?

I don't know, we haven't got to the guestmemfd/IOMMU integration yet,
which is why I ask the questions.

I think AMD and ARM would both be interested in guestmemfd <-> iommu
working this way, at least.

> I think we can go ahead with VMM pre-populating the entire DRAM
> and keeping it pinned for DA. Rather than doing this from the

Yes, if done it should be done by the VMM and run through
guestmemfd/kvm however that is agreed to.

Jason

---

## [105] Jason Gunthorpe — 2025-08-01
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

On Thu, Jul 31, 2025 at 07:07:17PM -0700, dan.j.williams@intel.com wrote:
> Aneesh Kumar K.V (Arm) wrote:
> > Host:

What does this do on the host? It seems to somehow prep it for VM
assignment? Seems pretty strange this is here in sysfs and not part of
creating the vPCI function in the VM through VFIO and iommufd?

Frankly, I'm nervous about making any uAPI whatsoever for the
hypervisor side at this point. I don't think we have enough of the
solution even in draft format. I'd really like your first merged TSM
series to only have uAPI for the guest side where things are hopefully
closer to complete..

> > step 1:
> > echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind

I think it is not just the dma api, but also the MMIO registers may
move location (form shared to protected IPA space for
example). Meaning any attached driver is completely wrecked.

> I agree with that up until the point where the implication is userspace
> control of the UNLOCKED->LOCKED transition. That transition requires

Why? That's sad. BME should be controlled by the VM driver not the
TSM, and it should be set only when a VM driver is probed to the RUN
state device?

> and *then* locking the device. That means userspace is blindly
> hoping that the device is in a state where it will remain quiet on the

Yes, but we broadly assume this already in Linux. Drivers assume their
devices are quiet when they are bound the first time, we expect on
unbinding a driver quiets the device before removing.

So broadly I think you can assume that a device with no driver is
quiet regardless of BME.

> 2 potential ways to solve this, but open to other ideas:
> 

What? Gross, no way can we let userspace control such intimate details
of the kernel. The kernel must auto set based on what T=x mode the
device driver binds into.

> - Userspace is not involved in this transition and the dma mapping API
>   is updated to allow a driver to switch the iommu domain at runtime,

I don't see why it is so complicated. The driver is unbound before it
reaches T=1 so we expect the device to be quiet (bigger problems if
not).  When the PCI core reaches T=1 it tells the DMA API to
reconfigure things for the unbound struct device. Then we bind a
driver as normal.

Driver controls nothing. All existing T=0 drivers "just work" with no
source changes in T=1 mode. DMA API magically hides the bounce
buffering. Surely this should be the baseline target functionality
from a Linux perspective?

So we should not have "driver controls" statements at all. Userspace
prepares the PCI device, driver probes onto a T=1 environment and just
works.

> > step 3: Moves the device to TDISP RUN state
> > echo 1 > /sys/bus/pci/devices/${DEVICE}/tsm/accept

It is, it is architecturally broken for BME to be controlled by the
TSM. BME is controlled by the guest OS driver only.

IMHO if this is a real worry (and I don't think it is) then the right
answer is for physical BME to be set on during locking, but VIRTUAL
BME is left off. Virtual BME is created by the hypervisor/tsm by
telling the IOMMU to block DMA.

The Guest OS should not participate in this broken design, the
hypervisor can set pBME automatically when the lock request comes in,
and the quality of vBME emulation is left up to the implementation,
but the implementation must provide at least a NOP vBME once locked.

> Now, the nice thing about the scheme as proposed in this set is that
> userspace has all the time in the world between "lock" and "accept" to

Seems right to me. There should be NO trusted kernel driver bound
until the verifier accepts the attestation. Anything else allows un
accepted devices to attack the kernel drivers. Few kernel drivers
today distrust their HW interfaces as hostile actors and security
defend against them. Therefore we should be very reluctant to bind
drivers to anything..

Arguably a CC secure kernel should have an allow list of audited
secure drivers that can autoprobe and all other drivers must be
approved by userspace in some way, either through T=1 and attestation
or some customer-aware risk assumption.

From that principal the kernel should NOT auto probe drivers to T=0
devices that can be made T=1. Userspace should handle attaching HW to
such devices, and userspace can sequence whatever is required,
including the attestation and verifying.

Otherwise, if you say, have a TDISP capable mlx5 device and boot up
the cVM in a comporomised host the host can probably completely hack
your cVM by exploiting the mlx5 drivers's total trust in the HW
interface while running in T=0 mode.

You must attest it and switch to T=1 before binding any driver if you
care about mitigating this risk.

> With the driver in control there would need to be something like a
> usermodehelper to notify userspace that the device is in the locked

It doesn't make sense to require modification to all existing drivers
in Linux! The starting point must have the core code do this sequence
for every driver. Once that is working we can talk about if other
flows are needed.

> > step 4: Load the driver again.
> > echo ${DEVICE} > /sys/bus/pci/drivers_probe

Generic userspace will have a hard time to know what the driver names
are..

The driver_probe option looks good to me as the default.

I'm not sure how generic code can handle "multiple drivers".. Most
devices will be able to work just fine with T=0 mode with bounce
buffers so we should generally not encourage people to make completely
different drivers for T=0/T=1 mode.

I think what is needed is some way for userspace to trigger the
"locking configuration" you mentioned, that may need a special driver,
but ONLY if the userspace is sequencing the device to T=1 mode. Not
sure how to make that generic, but I think so long as userspace is
explicitly controlling driver binding we can punt on that solution to
the userspace project :)

The real nastyness is RAS - what do you do when the device falls out
of RUN, the kernel driver should pretty much explode. But lots of
people would like the kernel driver to stay alive and somehow we FLR,
re-attest and "resume" the kernel driver without allowing any T=0
risks. For instance you can keep your netdev and just see a lot of
lost packets while the driver thrashes.

But I think we can start with the idea that such RAS failures have to
reload the driver too and work on improvements. Realistically few
drivers have the sort of RAS features to consume this anyhow and maybe
we introduce some "enhanced" driver mode to opt-into down the road.

Jason

---

## [106] dan.j.williams@intel.com — 2025-08-01
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

Jason Gunthorpe wrote:
> On Thu, Jul 31, 2025 at 07:07:17PM -0700, dan.j.williams@intel.com wrote:
> > Aneesh Kumar K.V (Arm) wrote:

vPCI is out of the picture at this phase.

On the host this establishes an SPDM session and sets up link encryption
(IDE) with the physical device. Leave VMs out of the picture, this
capability in isolation is a useful property. It addresses the similar
threat model that Intel Total Memory Encryption (TME) or AMD Secure
Memory Encryption (SME) go after, i.e. interposer on a physical link
capturing data in flight. 

With that established then one can go futher to do the full TDISP dance.

> Frankly, I'm nervous about making any uAPI whatsoever for the
> hypervisor side at this point. I don't think we have enough of the

Aligned. I am not comfortable merging any of this until we have that end
to end reliably stable for a kernel cycle or 2. The proposal is soak all
the vendor solutions together in tsm.git#staging.

Now, if the guest side graduates out of that staging before the host
side, I am ok with that.

> > > step 1:
> > > echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind

True.

> > I agree with that up until the point where the implication is userspace
> > control of the UNLOCKED->LOCKED transition. That transition requires

To me it is an unfortunate PCI specification wrinkle that writing to the
command register drops the device from RUN to ERROR. So you can LOCK
without setting BME, but then no DMA.

> > and *then* locking the device. That means userspace is blindly
> > hoping that the device is in a state where it will remain quiet on the

Flummoxed. Any way this gets sliced, userspace is asking for "private
world attach" because it alone knows that this device is acceptable, and
devices need to arrive in "shared world attach" mode.

> > - Userspace is not involved in this transition and the dma mapping API
> >   is updated to allow a driver to switch the iommu domain at runtime,

I started this project with "all existing T=0 drivers 'just work'" as a
goal and a virtue. I have been begrudgingly pulled away from it from the
slow drip of complexity it appears to push into the PCI core.

Now, I suspect the number of devices that are willing to spend gates and
firmware on TDISP capabilities in the near term is small. The "just
works" case is saved for either an L1 VMM to hide all this from an L2
guest, or a simplified TDISP specification that actually allows an OS
PCI core to handle these details in a standard way.

> So we should not have "driver controls" statements at all. Userspace
> prepares the PCI device, driver probes onto a T=1 environment and just

The concern is neither userspace nor the PCI core have everything it
needs to get the device to T=1. PCI core knows that the device is T=1
capable, but does not know how to preconfigure the device-specific lock
state, needs to wait for attestation. Userpace knows how to
attest/verify the device but really has no business running the device
outside of binding a driver, and can not rely on the PCI core to have
prepped the device's device-specific lock state.

Userspace might be able to bind a new driver that leaves the device in a
lockable state on unbind, but that is not "just works" that is,
"introduce a new concept of skinny TDISP setup drivers that leave
devices in LOCKED state on driver unbind, so that userspace can do the
work to verify the device and move it to RUN before loading the main
driver that expects the device arrives already running. Also, that main
driver needs to be careful not to trigger typically benign actions like
touch the command register to trip the device into ERROR state, or any
device-specific actions that trip ERROR state but would otherwise be
benign outside of TDISP."

If locking the device was just a toggle it would be possible. As far as
I can see it is a "prep+toggle" where "prep" needs a driver.

> > > step 3: Moves the device to TDISP RUN state
> > > echo 1 > /sys/bus/pci/devices/${DEVICE}/tsm/accept

Agree. That "accept" attribute does not belong with TSM. That is where
Aneesh has it in this RFC. "Accept" as an action is the combination of
device entered the LOCKED state in a configuration the verifier is
willing to accept and the mechanics of triggering the LOCKED->RUN
transition.

> IMHO if this is a real worry (and I don't think it is) then the right
> answer is for physical BME to be set on during locking, but VIRTUAL

I can let go of the "BME without driver" worry, but that does nothing to
solve the "device specific configuration required before lock" problem.

> > Now, the nice thing about the scheme as proposed in this set is that
> > userspace has all the time in the world between "lock" and "accept" to

Yes, today, where nothing is T=1 capable for an L1 guest*, the onus is
100% on the distribution, not the kernel. I.e. trim kernel config and
set modprobe policy to prevent unwanted drivers.

* For L2 there are proposals like this, where if you already trust your
  paravisor also pre-trust all the devices it tells you to trust.
[1]: http://lore.kernel.org/20250714221545.5615-1-romank@linux.microsoft.com

> From that principal the kernel should NOT auto probe drivers to T=0
> devices that can be made T=1. Userspace should handle attaching HW to

Agree, for PCI it would be simple to set a no-auto-probe policy for T=1
capable devices.

> Otherwise, if you say, have a TDISP capable mlx5 device and boot up
> the cVM in a comporomised host the host can probably completely hack

Yes, userspace must have a chance to say "no" before a driver attempts
to launch DMA to private memory after secrets have been deployed to the
TVM.

> > With the driver in control there would need to be something like a
> > usermodehelper to notify userspace that the device is in the locked

I do not want to burden the PCI core with TDISP compatibility hacks and
workarounds if it turns out only a small handful of devices ever deploy
a first generation TDISP Device Security Manager (DSM). L1 aiding L2, or
TDISP simplicity improvements to allow the PCI core to handle this in a
non-broken way, are what I expect if secure device assignment takes off.

> The starting point must have the core code do this sequence
> for every driver. Once that is working we can talk about if other

Do you agree that "device-specific-prep+lock" is the problem to solve?

> > > step 4: Load the driver again.
> > > echo ${DEVICE} > /sys/bus/pci/drivers_probe

Ideally the RUN->ERROR->UNLOCKED->LOCKED->RUN recovery can fit into the
existing 'struct pci_error_handlers' regime in some farther out future.

It was a "fun" discovery to see that virtual AER injection does not
exist in QEMU (at least last time I checked) and assigned devices that
throw physical AER events just kill the VM.

> But I think we can start with the idea that such RAS failures have to
> reload the driver too and work on improvements. Realistically few

Hmm, having trouble not reading that back supporting my argument above:

Realistically few devices support TDISP lets require enhanced drivers to
opt-into TDISP for the time being.

---

## [107] dan.j.williams@intel.com — 2025-08-01
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

Jason Gunthorpe wrote:
> On Wed, Jul 30, 2025 at 11:38:27AM +0100, Jonathan Cameron wrote:
> > On Wed, 30 Jul 2025 14:12:26 +0530

For example, CRYPTO_DEV_CCP_DD, the AMD PCI device driver that will call
tsm_register(), is already modular.

> > > The goal is to have tsm class device to be parented by the platform
> > > device.

Right. For TDX, and I expect CCA as well, the arch code that knows that
PCI/TSM functionality is available and can register a device, may be
running too early to attach a driver to that device.

I.e. I would like to just use faux_device, but without the ability to do
EPROBE_DEFER, for example to await the plaform IOMMU driver. It needs to
move to its own bus so the attach event can be handled at a better time.

> Otherwise the tsm core should accept NULL as the parent pointer during
> registration, it probably already does..

Yes, NULL @parent "just works" with tsm_register().

However, I expect all tsm_register() callers to be from modular drivers.

---

## [108] Aneesh Kumar K.V — 2025-08-02
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Tue, Jul 29, 2025 at 01:53:10PM +0530, Aneesh Kumar K.V wrote:
>> Jason Gunthorpe <jgg@ziepe.ca> writes:

Would we also need a separate DMA allocation API for allocating
addresses intended to be shared with the non-secure hypervisor?

Are there any existing drivers in the kernel that already require such
shared allocations, which I could use as a reference?

-aneesh

---

## [109] Aneesh Kumar K.V — 2025-08-02
*Subject: Re: [RFC PATCH v1 08/38] iommufd/tsm: Add tsm_op iommufd ioctls*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:21:45 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

This is something I’d like to get feedback on. According to the TSM
specification, we’re required to unlock before clearing MSE/BME via 
calling `vfio_pci_core_disable(vdev)`.

However, in the current `iommufd` branch, we seem to call
`vdevice_destroy` a bit too late in the sequence to meet this
requirement.


>>  	mutex_lock(&vdev->igate);
>> diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h


Thanks for the review comments. I'll update the patch with the suggested changes.


-aneesh

---

## [110] Aneesh Kumar K.V — 2025-08-02
*Subject: Re: [RFC PATCH v1 13/38] coco: host: arm64: Create a PDEV with rmm*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:21:50 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

This patch series is currently based on the ALP12 specification, available here:
https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp12.zip

The next revision of the series will be updated to align with the ALP15 specification.

>
>> +	union {

ok

>
>> +};

`pdev_create` is expected to set the device state to `RMI_PDEV_NEW`, so
the subsequent check is redundant if `rmi_pdev_create` returns success.
I will drop that.

>
>> +

Thanks for the review comments. I'll update the patch with the suggested changes.

-aneesh

---

## [111] Aneesh Kumar K.V — 2025-08-02
*Subject: Re: [RFC PATCH v1 13/38] coco: host: arm64: Create a PDEV with rmm*

Arto Merilainen <amerilainen@nvidia.com> writes:

> On 28.7.2025 16.51, Aneesh Kumar K.V (Arm) wrote:
>

Thanks for the review comments. I'll update the patch with the suggested changes.

-aneesh

---

## [112] Jason Gunthorpe — 2025-08-02
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Sat, Aug 02, 2025 at 02:14:20PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

The most likely case in the near term is PCI P2P to shared MMIO.

I don't know any way to allocate shared memory in a driver??

At the bare minimum this patch should be documenting the correct
architecture and outlining any gaps in the current implementation.

I also don't really understand what the above code is even
doing.. Isn't the design on ARM that the IPA always encodes the
shared/private in the top bit?

How do we get a shared page that does not already have a phys_addr_t
in the shared IPA? Shouldn't the kernel have switched to the shared
IPA alias when it returned the swiotlb buffer? eg why do we need to do:

#define dma_addr_unencrypted(x)		((x) | PROT_NS_SHARED)

At all?

Suzuki ?

Jason

---

## [113] Jason Gunthorpe — 2025-08-02
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

On Fri, Aug 01, 2025 at 02:19:54PM -0700, dan.j.williams@intel.com wrote:

> On the host this establishes an SPDM session and sets up link encryption
> (IDE) with the physical device. Leave VMs out of the picture, this

Okay, maybe connect is not an intuitive name for opening IDE
sessions..

> I started this project with "all existing T=0 drivers 'just work'" as a
> goal and a virtue. I have been begrudgingly pulled away from it from the

Do you have some examples? I don't really see what complexity there is
if the solution it simply not auto bind any drivers to TDISP capable
devices and userspace is responsible to manually bind a driver once it
has reached T=1.

This seems like the minimum possible simplicitly for the kernel as
simply everything is managed by userspace, and there is really no
special kernel behavior beyond switching the DMA API of an unbound
driver on the T=0/1 change.

> The concern is neither userspace nor the PCI core have everything it
> needs to get the device to T=1. 

Disagree, I think userspace can have everything. It may need some
per-device userspace support in difficult cases, but userspace can
deal with it..

> PCI core knows that the device is T=1 capable, but does not know how
> to preconfigure the device-specific lock state,

Userspace can do this. Can we define exactly what is needed to do this
"pre-configure the device specific lock state"? At the very worst, for
the most poorly designed device, userspace would have to bind a T=0
driver and then unbind it.

Again, I am trying to make something simple for the kernel that gets
us to a working solution before we jump ahead to far more complex in
the kernel models, like aware drivers that can toggle themselves
between T=0/1.

> Userspace might be able to bind a new driver that leaves the device in a
> lockable state on unbind, but that is not "just works" that is,

I wouldn't have the kernel leave the device in the locked state. That
should always be userspace. The special driver may do whatever special
setup is needed, then unbind and leave a normal unlocked device
"prepped" for userspace locking without doing a FLR or
something. Realistically I expect this to be a very rare requirement,
I think this coming up just reflects the HW immaturity of some early
TDISP devices.

Sensible mature devices should have no need of a pre-locking step. I
think we should design toward that goal as the stable future and only
try to enable a hacky work around for the problematic early devices. I
certainly am not keen on seeing significant permanent kernel
complexity to support this device design defect.

> driver that expects the device arrives already running. Also, that main
> driver needs to be careful not to trigger typically benign actions like

As I said below, I disagree with this. You can't touch the *physical*
command register but the cVM can certainly touch the *virtualized*
command register. It up to the VMM To ensure this doesn't cause the
device to fall out of RUN as part of virtualization.

I'd also say that the VMM should be responsible to set pBME=1 even if
vBME=0? Shouldn't it? That simplifies even more things for the guest.

> > From that principal the kernel should NOT auto probe drivers to T=0
> > devices that can be made T=1. Userspace should handle attaching HW to

So then it is just a question of what does a userspace component need
to do.

> I do not want to burden the PCI core with TDISP compatibility hacks and
> workarounds if it turns out only a small handful of devices ever deploy

Same feeling about pre-configuration :)

> > The starting point must have the core code do this sequence
> > for every driver. Once that is working we can talk about if other

Not "the" problem, but an design issue we need to accommodate but not
endorse.

> > But I think we can start with the idea that such RAS failures have to
> > reload the driver too and work on improvements. Realistically few

I would be comfortable if hitless RAS recovery for TDISP devices
requires some kernel opt-in. But also I'm not sure how this should
work from a security perspective. Should userspace also have to
re-attest before allowing back to RUN? Clearly this is complicated.

Also, I would be comfortable to support this only for devices that do
not require pre-configuration.

Jason

---

## [114] dan.j.williams@intel.com — 2025-08-02
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

Jason Gunthorpe wrote:
> On Fri, Aug 01, 2025 at 02:19:54PM -0700, dan.j.williams@intel.com wrote:
> 

Part of the rationale for a generic name is the TSM is free to assert
that the link is secure without IDE. Think integrated devices where
there is no expectation the link can be observed.

The host and guest side TSM operations are split into link/transport
security and device/state security (private MMIO/DMA) concerns
respectively. So maybe "secure_link" would be a better name for this
host-side-only operation.

> > I started this project with "all existing T=0 drivers 'just work'" as a
> > goal and a virtue. I have been begrudgingly pulled away from it from the

The example I have front of mind (confirmed by 2 vendors) is deferring
the loading of guest-side device/state security capable firmware to the
guest driver when the full device is assigned. In that scenario default
device power-on firmware is capable of link/transport security, enough
to get the device assigned. Guest needs to get the device/state security
firmware loaded before TDISP state transitions are possible.

I do think RAS recovery needs it too, but like you say below that should
come with conditions.

> This seems like the minimum possible simplicitly for the kernel as
> simply everything is managed by userspace, and there is really no

I do think userspace can / must deal with it. Let me come back with
actual patches and a sample test case. I see a potential path to support
the above "prep" scenario without the mess of TDISP setup drivers, or
the ugly complexity of driver toggles or a usermodehelper.

> > PCI core knows that the device is T=1 capable, but does not know how
> > to preconfigure the device-specific lock state,

Agree. When I talked about wishing for the simple TDISP case that is
userspace can always "just lock" and "driver bind" without needing to
worry about "prep", i.e any "prep" is always implied by "lock". That
should be the baseline.

> > Userspace might be able to bind a new driver that leaves the device in a
> > lockable state on unbind, but that is not "just works" that is,

Yeah, that is the nightmare I had last night. I completed the thought
exercise about driver toggle and said, "whoops, nope, Jason is right, we
can't design for that without leaving a permanent mess to cleanup".
The end goal needs to look like straight line typical driver probe path
for TDISP capable devices.

> > driver that expects the device arrives already running. Also, that main
> > driver needs to be careful not to trigger typically benign actions like

True. Although, now I am going back on my PCI core burden concern to
wonder if *it* should handle a vBME on behalf of the driver if only
because it may want to force the device out of the RUN state on driver
unbind to meet typical pci_disable_device() expectations.

Alexey had this, I thought it was burdensome, now coming around.

> > > From that principal the kernel should NOT auto probe drivers to T=0
> > > devices that can be made T=1. Userspace should handle attaching HW to

I hear you, let me walk back from the cliff with patches.

> 
> > > But I think we can start with the idea that such RAS failures have to

That seems reasonable. You want hitless RAS? Give us hitless init.

---

## [115] Jason Gunthorpe — 2025-08-03
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

On Sat, Aug 02, 2025 at 04:50:50PM -0700, dan.j.williams@intel.com wrote:
> > Do you have some examples? I don't really see what complexity there is
> > if the solution it simply not auto bind any drivers to TDISP capable

Yeah, those are the only cases I know of too, and IMHO, they are just
early devices. Clearly the clean answer is to put enough boot FW on
the device's flash to get to T=1 mode, then have the trusted OS driver
load the operating firmware from the trusted OS filesystem though the
trusted bootloader T=1 device.

You effectively attest the bootloader, and then if you trust the
bootloader you know that when the device gets to T=1 it can be trusted
to properly run the FW the trusted driver provides.

Think about this more broadly, does the prep FW load idea make sense
for something like SRIOV? No, it really doesn't. The hypervisor loaded
FW that is running the PF should definately be strong enough to get to
T=1 on the VM/VF side as well.

The non-SRIOV cases are quite often whole machine assignment
scenarios. But I'm sensing alot of that space is moving toward bare
metal machines instead of VMs.

I wonder if you can use all the CC machinery to attest and secure a
bare metal host?

> I do think RAS recovery needs it too, but like you say below that should
> come with conditions.

Especially RAS becomes simple because it basically follows the normal
flows that existed prior to TDISP, with the exception of needing some
attestation step.

I don't know alot about CC attestation, but maybe we can have
userspace provide the kernel with the accepted measurement and then
for RAS the kernel can FLR, remeasure and if the measurement is
exactly the same go back into T=1 automatically as part of the PCI
core FLR logic.

> I do think userspace can / must deal with it. Let me come back with
> actual patches and a sample test case. I see a potential path to support

I don't see how, something nasty has to be done in the kernel to allow
an attached driver to switch between T=1 and T=0 "views" of the device
and lockstep those changes with userspace. This is not so simple and
it really basically exactly the same as driver binding.

I don't think we should be afraid of T=0 prep drivers in these early
days.

Something more complex could come later if it is really warranted and
people really insist on continuing this unclean device design
strategy.

> Yeah, that is the nightmare I had last night. I completed the thought
> exercise about driver toggle and said, "whoops, nope, Jason is right, we

Yeah, maybe it is worthwhile to someday try to figure out an
alternative - keep in mind that critically this requires someone to
also come with an intree driver that will use all these new APIs and
capabilities!!!

So lets get walking first and then someone can come with some
proposal, complete with a driver implementing it, and it can be
judged. This project is already so big, and I'm pretty sure if you
start to also need entirely new operating modes for drivers the basics
will just get bogged down in that discussion, and very likely killed
anyhow due to a lack of user.

Even if we decide that is prefered it is better to separate it and
discuss it after the basics are merged. At least where I sit getting
basic guest support is a big priority so I strongly want to strip it
down to minimal as possible to make consistent progress steps.

> True. Although, now I am going back on my PCI core burden concern to
> wonder if *it* should handle a vBME on behalf of the driver if only

Hiding some vBME in the PCI core might make sense if we can't get the
VMM owners to agree to do it on the hypervisor side. It works better
on the VMM side because there is always an IOMMU and the VMM can
emulate BME by blocking DMA with the IOMMU.

But I would not allow/expect kernel device drivers to have anything to
do with the TDISP states. Getting into RUN is fully sequenced by
userspace, getting out of run should also be sequenced only by
userspace.

Removing a driver does not change the trust state of the PCI device,
so it shouldn't drop out of RUN. If userspace wishes to FLR the device
after userspace asked to unbind it can, there are already sysfs
controls for this IIRC.

Basically, all this says that Linux drivers that want to be used with
T=1 should be well behaved, fully quite all their DMA on remove, and
have no *functional* need for BME to do anyhting. We pretty much
already expect this of drivers today, so I don't see an issue with
strongly requiring it for T=1.

Keep in mind the flip side, almost no drivers are structured properly
to forcibly quiet any DMA before pci_enable_device(). Some HW, like
mlx5, can't do this at all without either using DMA to send a reset
command or through FLR.

> > I would be comfortable if hitless RAS recovery for TDISP devices
> > requires some kernel opt-in. But also I'm not sure how this should

Yeah.. Realistically there are few drivers that can even do this
today, mlx5 for example has such code (and it is hard!).

There is alot of investment required in the driver's core subsystem to
make this work. netdev and RDMA can support a 'rebirth' sort of flow
where the driver can disconnect the SW APIs, FLR the device, then
reconnect in some way. However, for example, I recently had a
discussion with DRM guys about RAS and they are not even doing the
basic locking/etc to be able to do this. :\

Jason

---

## [116] Alexey Kardashevskiy — 2025-08-04
*Subject: Re: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

On 28/7/25 19:47, Jason Gunthorpe wrote:
> On Mon, Jul 28, 2025 at 07:21:47PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> With passthrough devices, we need to make sure private memory is


I ended up exporting the guestmemfd's kvm_gmem_get_folio() for gfn->pfn and its fd a bit differently in iommufd - "no extra referencing":
https://github.com/AMDESE/linux-kvm/commit/f1ebd358327f026f413f8d3d64d46decfd6ab7f6

It is a new iommufd->kvm dependency though.

> I was kind of thinking it would be nice to have a guestmemfd mode that
> was "pinned", meaning the memory is allocated and remains almost

Yeah while doing the above, I was wondering if I want to pass the fd type when DMA-mapping from an fd or "detect" it as I do in the above commit or have some iommufd_fdmap_ops in this fd saying "(no) pinning needed" (or make this a flag of IOMMU_IOAS_MAP_FILE).

The "detection" is (mapping_inaccessible(mapping) && mapping_unevictable(mapping)), works for now.

btw in the AMD case, here it does not matter as much if it is private or shared, I map everything and let RMP and the VM deal with the permissions. Thanks,


> 
> Jason

---

## [117] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 14/38] coco: host: arm64: Device communication
 support*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:21:51 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

This get updated in the follow up patch as below.

	if (type == PDEV_COMMUNICATE)
		ret = rmi_pdev_communicate(virt_to_phys(dsc_pf0->rmm_pdev),
					   virt_to_phys(comm_data->io_params));
	else {
		struct cca_host_tdi *host_tdi = container_of(tsm->tdi, struct cca_host_tdi, tdi);

		ret = rmi_vdev_communicate(virt_to_phys(dsc_pf0->rmm_pdev),
					   virt_to_phys(host_tdi->rmm_vdev),
					   virt_to_phys(comm_data->io_params));
	}


>
>> +	if (ret != RMI_SUCCESS) {

Thanks for the review comments. I'll update the patch with the suggested changes.

-aneesh

---

## [118] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 15/38] coco: host: arm64: Stop and destroy the
 physical device*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:21:52 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

I’ll fold this into the patch that adds the `pdev_create` functionality.

-aneesh

---

## [119] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 19/38] coco: host: arm64: set_pubkey support*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:21:56 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

Thanks for the review comments. I'll update the patch with the suggested changes.

-aneesh

---

## [120] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 21/38] coco: host: arm64: Add support for virtual
 device communication*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:21:58 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

Sure, will update the patch

>
>>  	if (type == PDEV_COMMUNICATE)

-aneesh

---

## [121] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 24/38] arm64: CCA: Register guest tsm callback*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:22:01 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

`tsm_report` and DA are independent functionalities. I’ll update the
guest probe to return success so that `tsm_report` remains available
even if the DA tsm registration fails.

-aneesh

---

## [122] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

Arto Merilainen <amerilainen@nvidia.com> writes:

> On 28.7.2025 16.52, Aneesh Kumar K.V (Arm) wrote:
>

Yes, that was added because at one point the FVP model was including the
MSI-X table and PBA regions in the interface report.

If I understand correctly, we shouldn't expect to see those regions in
the report unless secure interrupts are supported. The BAR-based
skipping was added as a workaround to handle the FVP issue.

I believe we can drop that workaround now—if those regions are
incorrectly present, the below validation logic should catch and
reject them appropriately. Does that sound reasonable?

		/* No secure interrupts, we should not find this set, ignore for now. */
		if (FIELD_GET(TSM_INTF_REPORT_MMIO_MSIX_TABLE, mmio_range->range_attributes) ||
		    FIELD_GET(TSM_INTF_REPORT_MMIO_PBA, mmio_range->range_attributes)) {
			pci_info(pdev, "Skipping MSIX (%ld/%ld) range [%d] #%d %d pages, %llx..%llx\n",
				 FIELD_GET(TSM_INTF_REPORT_MMIO_MSIX_TABLE, mmio_range->range_attributes),
				 FIELD_GET(TSM_INTF_REPORT_MMIO_PBA, mmio_range->range_attributes),
				 i, range_id, mmio_range->num_pages, r->start, r->end);
			continue;
		}


-aneesh

---

## [123] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 38/38] coco: guest: arm64: Add support for
 fetching device info*

Jonathan Cameron <Jonathan.Cameron@huawei.com> writes:

> On Mon, 28 Jul 2025 19:22:15 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

...

>> +	return ret;
>> +}

yes, struct rsi_device_info is 512 bytes.

>
>> +	if (!dev_info) {

yes. But won't that be confusing? Is there a difference?
Also struct dsm_device_info is not same as struct rsi_device_info. We
don't need to keep all that padding in dsm_device_info.

>
>> +	kfree(dev_info);

-aneesh

---

## [124] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Sat, Aug 02, 2025 at 02:14:20PM +0530, Aneesh Kumar K.V wrote:
>> Jason Gunthorpe <jgg@ziepe.ca> writes:

swiotlb virt addr is updated in the direct map page table such that we
have the correct attribute set. For ex: swiotlb_update_mem_attributes
uses set_memory_decrypted() to mark the memory as shared.

	set_memory_decrypted((unsigned long)mem->vaddr, bytes >> PAGE_SHIFT);

However, when mapping swiotlb regions to obtain a `dma_addr_t`, we still
need to explicitly convert the physical address:

swiotlb_map()
	swiotlb_addr = swiotlb_tbl_map_single(dev, paddr, size, 0, dir, attrs);
        ...

	/* Ensure that the address returned is DMA'ble */
	dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);

Note that we don’t update the phys_addr_t to set the top
bit. For reference:

	tlb_addr = slot_addr(pool->start, index) + offset;

-aneesh

---

## [125] Arto Merilainen — 2025-08-04
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On 4.8.2025 9.37, Aneesh Kumar K.V wrote:
> Arto Merilainen <amerilainen@nvidia.com> writes:
> 

The issue I am raising is a different one. The MSI-X table and PBA may 
reside in the middle of a BAR range, and the BAR range may contain 
registers which should be accessible only via protected IPA. In this 
case I would expect the pages before and after the MSI-X table (and PBA) 
to be validated while the pages related to MSI-X structures would be 
left unprotected.

Given that the MSI-X table or PBA regions shouldn't be present in the 
interface report, the code needs to first find out where the MSI-X 
structures reside, and use this information to determine which 
"sub-ranges" should be skipped over during validation.
> If I understand correctly, we shouldn't expect to see those regions in
> the report unless secure interrupts are supported. The BAR-based

Correct. Assuming that RMM doesn't lock the MSI-X table, I'd expect 
these regions to be omitted in the interface report.

> I believe we can drop that workaround now—if those regions are
> incorrectly present, the below validation logic should catch and

First, I think this is skipping over the whole range => if there are 
registers outside of the MSI-X structures (but within the same BAR), 
they won't be validated.

Second, if the MSI-X regions are present in the interface report, 
wouldn't it - in the common case - mean that the device expects the 
ranges to be accessed with T=1? If this happens unexpectedly, it sounds 
that MSI-X wouldn't be usable. I wonder if the code should simply return 
an error instead if informing the user via pci_info()...

- R2

---

## [126] Aneesh Kumar K.V — 2025-08-04
*Subject: Re: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 28/7/25 19:47, Jason Gunthorpe wrote:
>> On Mon, Jul 28, 2025 at 07:21:47PM +0530, Aneesh Kumar K.V (Arm) wrote:

Was the motivation for that design choice the fact that in case of AMD
VFIO/IOMMUFD manages both private memory allocation and updates to the
IOMMU page tables?

On the ARM side, the requirement is to ensure that pages are present in
the stage-2 page table, which is managed by the firmware (RMM). Because
of this, we need an interface that VFIO/IOMMUFD can use to trigger
stage-2 mappings within KVM.

Alternatively, we could introduce a dedicated KVM ioctl for this
purpose, avoiding the need to rely on IOMMUFD.

For reference, TDX uses a similar ioctl—`KVM_TDX_INIT_MEM_REGION`—to
initialize guest memory. However, that interface isn’t well-suited for
dynamic updates to stage-2 mappings during shared-to-private or
private-to-shared transitions.


>
>> I was kind of thinking it would be nice to have a guestmemfd mode that

-aneesh

---

## [127] Jonathan Cameron — 2025-08-04
*Subject: Re: [RFC PATCH v1 38/38] coco: guest: arm64: Add support for
 fetching device info*

> >  
> >> +	if (!dev_info) {
Ah. I misread and thought they were the same structure.  No problem copying
only relevant fields then!

Jonathan

---

## [128] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 03/38] tsm: Move dsm_dev from pci_tdi to pci_tsm*

On Mon, Jul 28, 2025 at 07:21:40PM +0530, Aneesh Kumar K.V (Arm) wrote:

Subject line should include "PCI" prefix.

Needs a commit log, even if it repeats what's in the subject.  Would
also be good to know *why* this is desirable.

> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

s/lookup/Look up/ (it's a verb here)
 
> +static struct pci_dev *dsm_dev_get(struct pci_dev *pdev)
> +{

Remove this blank line ...

> +	struct pci_dev *pf0 __free(pci_dev_put) = pf0_dev_get(pdev);

and add one here.

> +	if (!pf0)
> +		return NULL;

s/usptream/upstream/

> +	 */
> +	if (!pdev->dev.parent || !pdev->dev.parent->parent)

Add blank line before comment.

> +	/*
> +	 * No reference needed because when we destroy

"tdi" looks like an initialism, which would normally be capitalized.

> +	 */
> +	tsm->dsm_dev = dsm_dev;

This code move looks like it could be a separate patch that only moves
(and fixes the typos I mentioned).

Then a second patch could do what the subject claims (moving dsm_dev
from pci_tdi to pci_tsm) so it's not buried in the simple move.

>  /* Only implement non-interruptible lock for now */
>  static struct mutex *tdi_ops_lock(struct pci_dev *pf0_dev)

---

## [129] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Mon, Jul 28, 2025 at 07:21:41PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Currently, we enforce the use of bounce buffers to ensure that memory
> accessed by non-secure devices is explicitly shared with the host [1].

> @@ -557,6 +560,9 @@ static void __pci_tsm_init(struct pci_dev *pdev)
>  	default:

Fix whatever this is, or make it a real sentence and wrap to fit in 80
columns.

> +	pdev->dev.tdi_enabled = false;
>  }

---

## [130] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 05/38] tsm: Don't overload connect*

Only touches drivers/pci, so needs a "PCI" prefix of some flavor.

On Mon, Jul 28, 2025 at 07:21:42PM +0530, Aneesh Kumar K.V (Arm) wrote:
> We need separate handling in the guest while destroying the device.
> Hence switch to new callback lock and unlock. Hide the connect sysfs

s/guest/Guest/
s/will now looks/will now look/

> ls -al  /sys/bus/pci/devices/0000:02:00.0/tsm/
> total 0

Indent quoted material a couple spaces.

I don't know about TSM, so this commit log doesn't quite tell me why
we need this.

It appears this also adds a sysfs file that could be documented
somehow.

> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

Drop this blank line ...

> +	struct mutex *lock __free(tsm_ops_unlock) = tsm_ops_lock(tsm);

add one here.  I'm seeing a new pattern; maybe the trend is to put
declarations of __free() things outside the usual local variable list?

> +	if (!lock)
> +		return -EINTR;

---

## [131] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 09/38] iommufd/vdevice: Add TSM Guest request uAPI*

On Mon, Jul 28, 2025 at 07:21:46PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add TSM Guest request uAPI against iommufd_vdevice to forward various
> TSM attestation & acceptance requests from guest to TSM driver/secure

s/illustates/illustrates/

> +++ b/drivers/pci/tsm.c
> @@ -861,7 +861,7 @@ int pci_tsm_unbind(struct pci_dev *pdev)

I dunno where this got added (not this patch), but "TDI" might be an
initialism that should be capitalized?

>   * @info: envelope for the request
>   *

Spurious diff.

>  	lockdep_assert_held_read(&pci_tsm_rwsem);
>

---

## [132] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 08/38] iommufd/tsm: Add tsm_op iommufd ioctls*

On Mon, Jul 28, 2025 at 07:21:45PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add operations bind and unbind used to bind a TDI to the secure guest.

> +++ b/include/uapi/linux/iommufd.h

> +#define IOMMU_VDEVICE_TSM_OP	_IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_OP)
> +#define IOMMU_VDEICE_TSM_BIND		0x1

s/VDEICE/VDEVICE/

---

## [133] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 19/38] coco: host: arm64: set_pubkey support*

On Mon, Jul 28, 2025 at 07:21:56PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add changes to share the device's public key with the RMM.

> +++ b/drivers/virt/coco/arm-cca-host/rmm-da.c

> +static int pdev_set_public_key(struct pci_tsm *tsm)
> +{

> +		/*
> +		 * exponent is usally 65537 (size = 24bits) but in rare cases

s/it size/size/ or s/it size/its size/ ?
s/usally/usually/

---

## [134] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 37/38] coco: guest: arm64: Add support for
 fetching device measurements*

On Mon, Jul 28, 2025 at 07:22:14PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Fetch device measurements using RSI_RDEV_GET_MEASUREMENTS.

> +++ b/arch/arm64/include/asm/rsi_smc.h

> +struct rsi_device_measurements_params {
> +	union {

s/nounce/nonce/ ?

---

## [135] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 35/38] coco: guest: arm64: Add Realm device start
 and stop support*

On Mon, Jul 28, 2025 at 07:22:12PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Writing 1 to 'tsm/acceept' will initiate the TDISP RUN sequence.

s/acceept/accept/

---

## [136] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 18/38] X.509: Move certificate length retrieval
 into new helper*

On Mon, Jul 28, 2025 at 07:21:55PM +0530, Aneesh Kumar K.V (Arm) wrote:
> From: Lukas Wunner <lukas@wunner.de>
> 

s/libray/library/

---

## [137] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 13/38] coco: host: arm64: Create a PDEV with rmm*

On Mon, Jul 28, 2025 at 07:21:50PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Create the realm physical device with RMM.

> +++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
> @@ -124,7 +124,15 @@ static int cca_tsm_connect(struct pci_dev *pdev)

s/rme_unasign_device/rme_unassign/

> +	 */
> +	if (!try_module_get(THIS_MODULE)) {

s/rme_asign_device/rme_assign_device/

---

## [138] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 32/38] coco: guest: arm64: Add support for guest
 initiated TDI bind/unbind*

On Mon, Jul 28, 2025 at 07:22:09PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add RHI for VDEV_SET_TDI_STATE
> 

s/switced/switched/ (or maybe "converted")

---

## [139] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 14/38] coco: host: arm64: Device communication
 support*

On Mon, Jul 28, 2025 at 07:21:51PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add helpers for device communication from RMM

> +++ b/drivers/virt/coco/arm-cca-host/rmm-da.c
> +static int __do_dev_communicate(int type, struct pci_tsm *tsm)

> +			/* FIXME!! depending on the DevComms status,
> +			 * it might require to ABORT the communcation.

s/communcation/communication/

Even better, fix the FIXME :)

> +			 */
> +			return -EINVAL;

s/communication in/communication is/

> +	 */
> +	if (io_exit->flags & RMI_DEV_COMM_EXIT_WAIT)

s/respnse/response/

> +	if (is_multi)
> +		goto redo_communicate;

---

## [140] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On Mon, Jul 28, 2025 at 07:22:11PM +0530, Aneesh Kumar K.V (Arm) wrote:
> This starts the sequence to transition the realm device to the TDISP RUN
> state by writing 1 to 'tsm/accept'.

> +++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c

> +int rsi_update_interface_report(struct pci_dev *pdev, bool validate)
> +{

I guess you intend to fix this?

> +		/* no secure interrupts */
> +		if (msix_tbl_bar != -1 && range_id == msix_tbl_bar) {

s/misx/MSI-X/ (twice)
s/pba/PBA/

---

## [141] Bjorn Helgaas — 2025-08-04
*Subject: Re: [RFC PATCH v1 36/38] KVM: arm64: CCA: enable DA in realm create
 parameters*

On Mon, Jul 28, 2025 at 07:22:13PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Now that we have all the required steps for DA in-place, enable
> DA while creating ralm.

s/ralm/realm/ ?

---

## [142] Alexey Kardashevskiy — 2025-08-05
*Subject: Re: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

On 4/8/25 13:58, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

IOMMUFD maps pages for DMA in the IOMMU pagetable, let it do just that.


> On the ARM side, the requirement is to ensure that pages are present in
> the stage-2 page table, which is managed by the firmware (RMM). Because

Right, if there is a requirement like this, and QEMU can do just another ioctl() - then I just do that, helps to untangle all these kernel module references. It is the firmware which makes sure that page tables are in sync so no much point teaching KVM about it imho, DMA map requests cannot go past QEMU anyway. Thanks,


> 
> For reference, TDX uses a similar ioctl—`KVM_TDX_INIT_MEM_REGION`—to

---

## [143] Xu Yilun — 2025-08-05
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

On Thu, Jul 31, 2025 at 09:22:17AM -0300, Jason Gunthorpe wrote:
> On Wed, Jul 30, 2025 at 02:55:02PM +0800, Xu Yilun wrote:
> > On Tue, Jul 29, 2025 at 11:29:17AM -0300, Jason Gunthorpe wrote:

I think there are 2 topics here:

1. Prevent VFIO mmap
2. Prevent /sys/../resource, /dev/mem users

I assume you are refering to the 2nd, then I agree.

> 
> > The original purpose of this pci_region_request_*() is to prevent

I assume your point is never to use more than one request region in the
same driver to achieve some mutual exclusion. I'm good to it. We could
switch to some bound flag.

> request region. If you want to block that it should be blocked by
> iommufd telling VFIO that the device is bound which revokes the

Agree.

> 
> The only thing request region should do is prevent /sys/../resource,

Agree. So seems no need a global option?

Thanks,
Yilun

> 
> There should only be one request region call in VFIO, it should

---

## [144] Aneesh Kumar K.V — 2025-08-05
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

<dan.j.williams@intel.com> writes:

> Aneesh Kumar K.V (Arm) wrote:
>> This patch series implements support for Device Assignment in the ARM CCA

lkvm run --realm -c 2 -m 256 -k /kselftest/Image  -p  "$KERNEL_PARAMS" -d ./rootfs-guest.ext2 --iommufd-vdevice --vfio-pci $DEVICE1 --vfio-pci $DEVICE2

> I had been assuming that everyone was prototyping with QEMU. Not a
> problem per se, but the memory management for shared device assignment /

-aneesh

---

## [145] Aneesh Kumar K.V — 2025-08-05
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

<dan.j.williams@intel.com> writes:

> Jason Gunthorpe wrote:
>> On Thu, Jul 31, 2025 at 07:07:17PM -0700, dan.j.williams@intel.com wrote:

This is only w.r.t clearing BME isn't ?

According to section 11.2.6 DSM Tracking and Handling of Locked TDI Configurations

Clearing any of the following bits causes the TDI hosted
by the Function to transition to ERROR:

• Memory Space Enable
• Bus Master Enable


Which implies the flow described in the cover-letter where driver enable the BME works?
However clearing BME may be problematic? I did have a FIXME!!/comment in [1]

vfio_pci_core_close_device():

#if 0
	/*
	 * destroy vdevice which involves tsm unbind before we disable pci disable
	 * A MSE/BME clear will transition the device to error state.
	 */
	if (core_vdev->iommufd_device)
		iommufd_device_tombstone_vdevice(core_vdev->iommufd_device);
#endif

	vfio_pci_core_disable(vdev);


Currently, we destroy (TSM unbind) the vdevice after calling
vfio_pci_core_disable(), which means BME is cleared before unbinding,
and the TDI transitions to the ERROR state.

[1] https://lore.kernel.org/all/20250728135216.48084-9-aneesh.kumar@kernel.org/

-aneesh

---

## [146] Aneesh Kumar K.V — 2025-08-05
*Subject: Re: [RFC PATCH v1 03/38] tsm: Move dsm_dev from pci_tdi to pci_tsm*

Bjorn Helgaas <helgaas@kernel.org> writes:

> On Mon, Jul 28, 2025 at 07:21:40PM +0530, Aneesh Kumar K.V (Arm) wrote:
>

Thanks for the review comments. I'll update the patch with the suggested changes.

-aneesh

---

## [147] Alexey Kardashevskiy — 2025-08-05
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On 28/7/25 20:03, Jason Gunthorpe wrote:
> On Mon, Jul 28, 2025 at 07:21:41PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> @@ -48,3 +49,12 @@ int set_memory_decrypted(unsigned long addr, int numpages)

I did write this in the first place so I'll comment :)

> 
> What are the ARM rules for generating dma addreses?


On AMD, T=1 only encrypts the PCIe trafic, when a DMA request hits the IOMMU, the IOMMU decrypts it and then decides whether to encrypt it with a memory key: if there is secure vIOMMU - it will do what Cbit says in the guest IOMMU table (this is in the works) oooor just always set Cbit without guest vIOMMU (which is a big knob per a device and this is what my patches do now).

And with vIOMMU, I'd expect phys_to_dma_direct() not to be called as this one is in a direct map path.

> 
>> diff --git a/include/linux/device.h b/include/linux/device.h


May be but "_enabled", not "_supported". And, ideally, with vIOMMU, at least AMD won't be needing it.

> 
> Also need to think carefully of a bitfield is OK here, we can't

True.

> 
> Jason

---

## [148] Jason Gunthorpe — 2025-08-05
*Subject: Re: [RFC PATCH v1 10/38] iommufd/vdevice: Add TSM map ioctl*

On Mon, Aug 04, 2025 at 08:02:23AM +0530, Alexey Kardashevskiy wrote:
> I ended up exporting the guestmemfd's kvm_gmem_get_folio() for gfn->pfn and its fd a bit differently in iommufd - "no extra referencing":
> https://github.com/AMDESE/linux-kvm/commit/f1ebd358327f026f413f8d3d64d46decfd6ab7f6

This patch needs to explain how the lifecylce works and why the IOMMU
can't UAF the memory. I think it cannot really work as shown without
more things like an invalidation callback.

IOW you need to define for how long the return result of
guest_memfd_get_pfn() is valid for.

> > I was kind of thinking it would be nice to have a guestmemfd mode that
> > was "pinned", meaning the memory is allocated and remains almost

It should be autodetected.

Since this is unique behavior for guestmemfd it is fine to start
there..

> btw in the AMD case, here it does not matter as much if it is
> private or shared, I map everything and let RMP and the VM deal with

I think ARM would like to do this as well.

Hence my suggestion that guestmemfd could just have unchanging 1G PFNs
and all shared/private changes have no impact on iommufd.

If so likely all this needs is an invalidation callback from
guestmemfd to iommufd to revoke on ftruncate.

Jason

---

## [149] Jason Gunthorpe — 2025-08-05
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Mon, Aug 04, 2025 at 12:28:33PM +0530, Aneesh Kumar K.V wrote:
> Note that we don’t update the phys_addr_t to set the top
> bit. For reference:

This seems unfortunate.

So you end up with the private IPA space having shared pages in it,
so *sometimes* you have to force the unencrypted bit?

Seems to me we should insist the phys_addr is cannonised before
reaching the dma API. Ie that the swiotlb/etc code will set the right
IPA bit.

Jason

---

## [150] Jason Gunthorpe — 2025-08-05
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Tue, Aug 05, 2025 at 08:22:10PM +1000, Alexey Kardashevskiy wrote:

>> static inline dma_addr_t phys_to_dma_direct(struct device *dev,
>>               phys_addr_t phys)

On AMD what is the force_dma_unencrypted() for?

I thought AMD had only one IOMMU and effectively one S2 mapping. Why
does it need to change the phys depending on it being shared or private?

> On AMD, T=1 only encrypts the PCIe trafic, when a DMA request hits
> the IOMMU, the IOMMU decrypts it and then decides whether to encrypt

AMD doesn't have the split IOMMU design that something like ARM has,
so it is bit different..

On ARM the T=1 IOMMU should map the entire CPU address space, so any
IOVA with any address should just work. So I'd expect AMD and ARM to
be the same here.

For the T=0 iommu ARM (I think) will only map the shared pages to the
shared IPA alias, so the guest VM has to ensure the shared physical
alias is used. Then it sounds like the CPU will sometimes accept the
private physical alias, and linus will sometimes prefer the physical
alias, for the shared memory too so Linux gets things muddled.

IMHO ARM probably should fix this much higher up the stack when it has
more information to tell if the phys_addr is actualy the private alias
a shared page.

> > > +	bool			tdi_enabled:1;
> > >   };

Yes

Jason

---

## [151] Jason Gunthorpe — 2025-08-05
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

On Tue, Aug 05, 2025 at 10:26:06AM +0800, Xu Yilun wrote:
> > IMHO there is no use case for that, it should arguably be global to
> > the whole kernel.

Yes, the region stuff is only about #2.

> > 
> > > The original purpose of this pci_region_request_*() is to prevent

Yes and yes

> > The only thing request region should do is prevent /sys/../resource,
> > /dev/mem users and so on, which is why it can and should be

I'd ask Alex if he is OK with a global behavior change to make vfio
exclusive, after any required fixing to make vfio only request the
regions once at driver probe time..

Jason

---

## [152] Jason Gunthorpe — 2025-08-05
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

On Tue, Aug 05, 2025 at 10:37:01AM +0530, Aneesh Kumar K.V wrote:
> > To me it is an unfortunate PCI specification wrinkle that writing to the
> > command register drops the device from RUN to ERROR. So you can LOCK

Oh that's nice, yeah!

> Which implies the flow described in the cover-letter where driver enable the BME works?
> However clearing BME may be problematic? I did have a FIXME!!/comment in [1]

Here is where I feel the VMM should be trapping this and NOPing it, or
failing that the guest PCI Core should NOP it.

With the ideal version being the TSM and VMM would be able to block
the iommu as a functional stand in for BME.

> Currently, we destroy (TSM unbind) the vdevice after calling
> vfio_pci_core_disable(), which means BME is cleared before unbinding,

I don't think this ordering is deliberate, we can destroy the vdevice
much earlier??

Jason

---

## [153] dan.j.williams@intel.com — 2025-08-05
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

Jason Gunthorpe wrote:
> On Tue, Aug 05, 2025 at 10:37:01AM +0530, Aneesh Kumar K.V wrote:
> > > To me it is an unfortunate PCI specification wrinkle that writing to the

That is useful, but an unmodified PCI driver is going to make separate
calls to pci_set_master() and pci_enable_device() so it should still be
the case that those need to be trapped out of the concern that
writing back zero for a read-modify-write also trips the error state on
some device that fails the Robustness Principle.

I guess we could wait to solve that problem until the encountering the
first device that trips ERROR when writing zero to an already zeroed
bit.

> > Which implies the flow described in the cover-letter where driver enable the BME works?
> > However clearing BME may be problematic? I did have a FIXME!!/comment in [1]

At this point (vfio shutdown path) the VMM is committed stopping guest
operations with the device. So ok not to not NOP in this specific path,
right?

> With the ideal version being the TSM and VMM would be able to block
> the iommu as a functional stand in for BME.

The TSM block for BME is the LOCKED or ERROR state. That would be in
conflict with the proposal that the device stays in the RUN state on
guest driver unbind.

I feel like either the device stays in RUN state and BME leaks, or the
device is returned to LOCKED on driver unbind. Otherwise a functional
stand-in for BME that also keeps the device in RUN state feels like a
TSM feature request for a "RUN but BLOCKED" state.

---

## [154] Jason Gunthorpe — 2025-08-05
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

On Tue, Aug 05, 2025 at 11:27:36AM -0700, dan.j.williams@intel.com wrote:
> > > Clearing any of the following bits causes the TDI hosted
> > > by the Function to transition to ERROR:

I hope we don't RMW BME and MSE in some weird way like that :(
 
> > Here is where I feel the VMM should be trapping this and NOPing it, or
> > failing that the guest PCI Core should NOP it.

What I said in my other mail was the the T=1 state should have nothing
to do with driver binding. So unbinding vfio should leave the device
in the RUN state just fine.

> > With the ideal version being the TSM and VMM would be able to block
> > the iommu as a functional stand in for BME.

This is a different thing. Leaving RUN says the OS (especially
userspace) does not trust the device.

Disabling DMA, on explict trusted request from the cVM, is entirely
fine to do inside the T=1 state. PCI made it so the only way to do
this is with the IOMMU, oh well, so be it.

> I feel like either the device stays in RUN state and BME leaks, or the
> device is returned to LOCKED on driver unbind. 

Stay in RUN is my vote. I can't really defend the other choice from a
linux driver model perspective.

> Otherwise a functional stand-in for BME that also keeps the device
> in RUN state feels like a TSM feature request for a "RUN but

Yes, and probably not necessary, more of a defence against bugs in
depth kind of request. For Linux we would like it if the device can be
in RUN and have DMA blocked off during all times when no driver is
attached.

Jason

---

## [155] dan.j.williams@intel.com — 2025-08-05
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

Jason Gunthorpe wrote:
> On Tue, Aug 05, 2025 at 11:27:36AM -0700, dan.j.williams@intel.com wrote:
> > > > Clearing any of the following bits causes the TDI hosted

Yeah, I would like to say, "device, you get to keep the pieces if you
transition to ERROR state on re-writing on already zeroed-bit."

> > > Here is where I feel the VMM should be trapping this and NOPing it, or
> > > failing that the guest PCI Core should NOP it.

Guest driver unbind, agree.

> So unbinding vfio should leave the device in the RUN state just fine.

Perhaps my vfio inexperience is showing, but at the point where the VMM
is unbinding vfio it is committed to destroying the guest's assigned
device context, no? So should that not be the point where continuing to
maintain the RUN state ends?

> > > With the ideal version being the TSM and VMM would be able to block
> > > the iommu as a functional stand in for BME.

Ok, defense in depth, but in the meantime rely on unbound driver == DMA
unmapped and device should be quiescent. Combine that with the fact that
userspace PCI drivers should be disabled in cVMs should mean that guest
can expect that an unbound TDI in the RUN state will remain quiet.

---

## [156] Jason Gunthorpe — 2025-08-05
*Subject: Re: [RFC PATCH v1 00/38] ARM CCA Device Assignment support*

On Tue, Aug 05, 2025 at 12:06:11PM -0700, dan.j.williams@intel.com wrote:

> > So unbinding vfio should leave the device in the RUN state just fine.
> 

Oh, sorry it gets so confusing..

VFIO *in the guest* should behave as above, like any other driver
unbind leaves it in RUN.

VFIO *in the host* should leave the RUN state at the soonest of:

 - cVM's KVM is destroyed
 - iommufd vdevice is destroyed
 - vfio device is closed

And maybe more cases I didn't think of.. BME should happen strictly
after all of the above and should not be the trigger that drops it out
of RUN.

> > Yes, and probably not necessary, more of a defence against bugs in
> > depth kind of request. For Linux we would like it if the device can be

"userspace PCI drivers" is VFIO in the guest which means you get
FLRs to fence the DMA.

If we end up where I suggested earlier for RAS that a FLR can check
the attestation and if exactly matching reaccept it automatically then
it would maintain the 'once accepted we stay in T=1 RUN state' idea.

Jason

---

## [157] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [RFC PATCH v1 06/38] iommufd: Add and option to request for bar
 mapping with IORESOURCE_EXCLUSIVE*

Aneesh Kumar K.V (Arm) wrote:
> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

I think we simply make the rule be something like this:

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 700addee8f62..d84158aacabf 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -138,6 +138,7 @@ config PCI_IDE_STREAM_MAX
 
 config PCI_TSM
 	bool "PCI TSM: Device security protocol support"
+	depends on IO_STRICT_DEVMEM
 	select PCI_IDE
 	select PCI_DOE
 	help

...i.e. the base expectation is there is only ever one owner of
potentially private MMIO space.

---

## [158] Eric Biggers — 2025-08-08
*Subject: Re: [RFC PATCH v1 38/38] coco: guest: arm64: Add support for
 fetching device info*

On Mon, Jul 28, 2025 at 07:22:15PM +0530, Aneesh Kumar K.V (Arm) wrote:
> @@ -5,6 +5,8 @@ config ARM_CCA_GUEST
>  	tristate "Arm CCA Guest driver"

CRYPTO_LIB_SHA256 and CRYPTO_LIB_SHA512

> +	if (dsm->dev_info.hash_algo == RSI_HASH_SHA_256) {
> +		hash_alg_name = "sha256";

Use sha256() and sha512().

- Eric

---

## [159] Arto Merilainen — 2025-09-10
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On 31.7.2025 14.39, Arto Merilainen wrote:
> On 28.7.2025 16.52, Aneesh Kumar K.V (Arm) wrote:
> 

I re-reviewed my suggestion, and what I proposed here seems wrong. 
However, I think there is a different more generic problem related to 
the MSI-X table, PBA and non-TEE ranges.

If a BAR is sparse (e.g., it has TEE pages and the MSI-X table, PBA or 
non-TEE areas), the TDISP interface report may contain multiple ranges 
with the same range_id (/BAR id). In case a BAR contains some registers 
in low addresses, the MSI-X table and other registers after the MSI-X 
table, the interface report is expected to have two ranges for the same 
BAR with different "first 4k page" and "size" fields.

This creates a tricky problem given that RSI_VDEV_VALIDATE_MAPPING 
requires both the ipa_base and pa_base which should correspond to the 
same location. In above scenario, the PA of the first range would 
correspond to the BAR base whereas the second range would correspond to 
a location residing after the MSI-X table.

Assuming that the report contains obfuscated (but linear) physical 
addresses, it would be possible to create heuristics for this case. 
However, the fundamental problem is that none of the "first 4k page" 
fields in the ranges is guaranteed to correspond to the base of any BAR: 
Consider a case where the MSI-X table is in the beginning of a BAR and 
it is followed by a single TEE range. If the MSI-X is not locked, the 
"first 4k page" field will not correspond to the beginning of the BAR. 
If the realm naiviely reads the ipa_base using pci_resouce_n() and 
corresponding pa_base from the interface report, the addresses won't 
match and the validation will fail.

It seems that interpreting the interface report cannot be done without 
knowledge of the device's register layout. Therefore, I don't think the 
ranges can be validated/remapped automatically without involving the 
device driver, but there should be APIs for reading the interface 
report, and for requesting making specific ranges protected.

- R2

---

## [160] Jason Gunthorpe — 2025-09-10
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On Wed, Sep 10, 2025 at 08:47:43AM +0300, Arto Merilainen wrote:
> This creates a tricky problem given that RSI_VDEV_VALIDATE_MAPPING requires
> both the ipa_base and pa_base which should correspond to the same location.

This seems like a defect in the RSI_VDEV_VALIDATE_MAPPING - it should
be able to consume the same format of data that the tdisp report emits
to validate it.

From a kernel side we also should be careful that the driver isn't
tricked into mapping MMIO that is not secure when it should
be. Presumably all the default io access functions should demand
secure memory in T=1 mode, and special ones like the MSI-X code would
have some special version to accept either?

Jason

---

## [161] Aneesh Kumar K.V — 2025-09-11
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

Arto Merilainen <amerilainen@nvidia.com> writes:

> On 31.7.2025 14.39, Arto Merilainen wrote:
>> On 28.7.2025 16.52, Aneesh Kumar K.V (Arm) wrote:

But we need to validate the interface report before accepting the device,
and the device driver is only loaded after the device has been accepted.

Can we assume that only the MSI-X table and PBA ranges may be missing
from the interface report, while all other non-secure regions are
reported as NON-TEE ranges?

If so, we could retrieve the MSI-X guest real address details from
config space and map the beginning of the BAR correctly.

Dan / Yilun — how is this handled in Intel TDX?

From what I can see, the AMD patches appear to encounter the same issue.

-aneesh

---

## [162] Alexey Kardashevskiy — 2025-09-11
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On 11/9/25 15:33, Aneesh Kumar K.V wrote:
> Arto Merilainen <amerilainen@nvidia.com> writes:
> 

In case of the "some registers"+MSIX+"some more registers" BAR#X, I'd rather expect 3 ranges in the report and not just 2, for each subrange, sorted, with/without NonTEE bit set, as the PCIe spec suggests (sort of, I struggle parsing it):

===
When reporting the MMIO range for a TDI, the MMIO ranges must be reported in the logical order in which the TDI MMIO
range is configured such that the first range reported corresponds to first range of pages in the TDI and so on
===

And if the number of pages in the report differs from the BAR size, then we should fail validation. Otherwise it is impossible to tell from the report's MMIO addresses what part of a BAR needs to be validated (==TEE) and if the guest device driver has to know it - then reports are just useless (which is hardly true).


> If so, we could retrieve the MSI-X guest real address details from
> config space and map the beginning of the BAR correctly.

I am skipping MSIX BAR because T=1 is tied to C=1 so after such validation, the BAR belongs to the guest and the hw will reject VFIO-PCI (==HV) attempts to write to MSIX BAR. Probably too straight forward though and I can try assigning it to the host (and add Cbit in those PTEs), and see how the PSP handles it (not). Thanks,


> 
> -aneesh

---

## [163] Jason Gunthorpe — 2025-09-11
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

On Thu, Sep 11, 2025 at 11:03:50AM +0530, Aneesh Kumar K.V wrote:

> But we need to validate the interface report before accepting the device,
> and the device driver is only loaded after the device has been accepted.

+1

This must work from the generic OS code.

So I'd say add a new TSM op:
 int validate_pci_bar_range(struct pci_dev *pdev,
                            unsigned int bar_index, u64 tdisp_pa,
			    u64 size,phys_addr_t *bar_offset_out);

TSM has broadly two options to compute bar_offset_out:

1) Require the TDISP MMIO Offset is aligned to the BAR size and use
   something like:

    *bar_offset_out = (tdisp_pa) % pci_resource_len(pdev, bar_index);
    ipa = pci_resource_start(pdev, bar_index) + *bar_offset_out;
    if (size + *bar_offset_out > pci_resource_len(pdev, bar_index))
        return -EINVAL;
    tsm_call_to_validate(pdev, ipa, pa, size)

2) Require the TSM to convert the offest'd PA to the IPA:

    tsm_call_to_convert(pdev, pa, size, &ipa);

    if (ipa < pci_resource_start(pdev, bar_index) ||
        ipa >= pci_resource_end(pdev, bar_index) ||
        (ipa + size) > pci_resource_end(pdev, bar_index))
	return -EINVAL;

    *bar_offset_out = ipa -  pci_resource_start(pdev, bar_index);

Then the generic code builds a map of what parts of the BAR are secure
and what are not.

If it can't do either the TSM is unusable by Linux.

Jason

---

## [164] dan.j.williams@intel.com — 2025-09-11
*Subject: Re: [RFC PATCH v1 34/38] coco: guest: arm64: Validate mmio range
 found in the interface report*

Aneesh Kumar K.V wrote:
> Arto Merilainen <amerilainen@nvidia.com> writes:
> 

Same issue exists for TDX. In the near term this solidifies that the
PCI/TSM core should not be assumining anything with respect to marking
MMIO ranges as private, and leave that all the to low-level TSM driver.

...but then yes I expect we need to build some common infrastructure for
special casing MSIX.

---

## [165] Mostafa Saleh — 2025-09-15
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

Hi Aneesh,

On Mon, Jul 28, 2025 at 07:21:41PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Currently, we enforce the use of bounce buffers to ensure that memory
> accessed by non-secure devices is explicitly shared with the host [1].


Sorry this might be a basic question, I just started looking into this.
I see that “force_dma_unencrypted” and “is_swiotlb_force_bounce” are only
used from DMA-direct, but it seems in your case it involves an IOMMU.
How does it influence bouncing in that case?

Thanks,
Mostafa

> 
> To achieve this, we introduce a device flag that controls whether a

---

## [166] Aneesh Kumar K.V — 2025-09-16
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

Mostafa Saleh <smostafa@google.com> writes:

> Hi Aneesh,
>

With the current patchset, the guest does not have an assigned IOMMU (no
Stage1 SMMU), so guest DMA operations use DMA-direct.

For non-secure devices:
 - Streaming DMA uses swiotlb, which is a shared pool with the hypervisor.
 - Non-streaming DMA uses DMA-direct, and the attributes of the allocated
   memory are updated with dma_set_decrypted().

For secure devices, neither of these mechanisms is needed.

-aneesh

---

## [167] Mostafa Saleh — 2025-09-16
*Subject: Re: [RFC PATCH v1 04/38] tsm: Support DMA Allocation from private
 memory*

On Tue, Sep 16, 2025 at 09:45:18AM +0530, Aneesh Kumar K.V wrote:
> Mostafa Saleh <smostafa@google.com> writes:
> 

I see, thanks for the explanation!

Thanks,
Mostafa

> 
> -aneesh

---

## [168] Aneesh Kumar K.V — 2025-10-09
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

<dan.j.williams@intel.com> writes:

> Jason Gunthorpe wrote:
>> On Wed, Jul 30, 2025 at 11:38:27AM +0100, Jonathan Cameron wrote:

One of the issues I’ve run into after switching to the faux_device model
is determining how to automatically load the guest and host TSM drivers
based on the availability of the device assignment feature.

The platform device previously provided a clean abstraction for this
behavior, which made autoloading straightforward

>
>> Otherwise the tsm core should accept NULL as the parent pointer during

-aneesh

---

## [169] Jeremy Linton — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

Hi,


On 7/30/25 8:07 AM, Greg KH wrote:
> On Wed, Jul 30, 2025 at 01:23:33PM +0100, Jonathan Cameron wrote:
>> On Wed, 30 Jul 2025 11:38:27 +0100

Right, but this code is intended to trigger the kmod/userspace module 
loader.

AFAIK, the faux device is currently missing a faux_device_id in 
mod_devicetable, alias matching logic in file2alias, and probably a few 
other things which keeps it from performing this function.

thanks,

---

## [170] Greg KH — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Fri, Oct 10, 2025 at 07:10:58AM -0500, Jeremy Linton wrote:
> Hi,
> 

Why?

> AFAIK, the faux device is currently missing a faux_device_id in
> mod_devicetable, alias matching logic in file2alias, and probably a few

How would a faux device ever expect to get auto-loaded?  That's not what
is supposed to be happening here at all.

If you have real hardware backing something, then use the real driver
type.  that is NOT a faux driver, which is, as the name says, for "fake"
devices that you wish to add to the device/driver tree.

thanks,

greg k-h

---

## [171] Jason Gunthorpe — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Fri, Oct 10, 2025 at 07:10:58AM -0500, Jeremy Linton wrote:
> > Yes, use faux_device if you need/want a struct device to represent
> > something in the tree and it does NOT have any real platform resources

Faux devices are not intended to be bound, it says so right on the label:

 * A "simple" faux bus that allows devices to be created and added
 * automatically to it.  This is to be used whenever you need to create a
 * device that is not associated with any "real" system resources, and do
 * not want to have to deal with a bus/driver binding logic.  It is
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^
 * intended to be very simple, with only a create and a destroy function
 * available.

auxiliary_device is quite similar to faux except it is intended to be
bound to drivers, supports module autoloading and so on.

What you have here is the platform firmware provides the ARM SMC
(Secure Monitor Call Calling Convention) interface which is a generic
function call multiplexer between the OS and ARM firmware.

Then we have things like the TSM subsystem that want to load a driver
to use calls over SMC if the underlying platform firmware supports the
RSI group of SMC APIs. You'd have a TSM subsystem driver that uses the
RSI call group over SMC that autobinds when the RSI call group is
detected when the SMC is first discovered.

So you could use auxiliary_device, you'd consider SMC itself to be the
shared HW block and all the auxiliary drivers are per-subsystem
aspects of that shared SMC interface. It is not a terrible fit for
what it was intended for at least.

Jason

---

## [172] Jeremy Linton — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

Hi,

On 10/10/25 7:38 AM, Greg KH wrote:
> On Fri, Oct 10, 2025 at 07:10:58AM -0500, Jeremy Linton wrote:
>> Hi,

Originally it was because without the tsm drivers loaded there wasn't 
any way for a CCA guest to know it is running in a confidential compute 
environment. That is a bit of a problem for generic distro kernels which 
don't want to load a bunch of functionality on devices that don't 
support it. So, this triggers the tsm module load, which in turn 
provides enough metadata for userspace to start attestation/whatever it 
needs. (Ex: systemd-detect-virt --cvm).

I think Jason clarifies whats going on too.




> 
>> AFAIK, the faux device is currently missing a faux_device_id in

---

## [173] Jeremy Linton — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

Hi,

On 10/10/25 8:59 AM, Jason Gunthorpe wrote:
> On Fri, Oct 10, 2025 at 07:10:58AM -0500, Jeremy Linton wrote:
>>> Yes, use faux_device if you need/want a struct device to represent

Turns out that changing any of this, will at the moment break systemd's 
confidential vm detection, because they wanted the earliest indicator 
the guest was capable and that turned out to be this platform device.

---

## [174] Jason Gunthorpe — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Fri, Oct 10, 2025 at 10:28:36AM -0500, Jeremy Linton wrote:

> > So you could use auxiliary_device, you'd consider SMC itself to be the
> > shared HW block and all the auxiliary drivers are per-subsystem

Having systemd detect a software created platform device sounds
compltely crazy, don't do that. Make a proper sysfs uapi for such a
general idea please.

Jason

---

## [175] Greg KH — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Fri, Oct 10, 2025 at 12:30:46PM -0300, Jason Gunthorpe wrote:
> On Fri, Oct 10, 2025 at 10:28:36AM -0500, Jeremy Linton wrote:
> 

Agreed.  Please do NOT abuse platform devices for this, as this is NOT a
platform device.  It is a random virtual device that you are wanting to
create out of thin air based on something else.

Trigger off of that "something else" please.

thanks,

greg k-h

---

## [176] Jeremy Linton — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On 10/10/25 10:30 AM, Jason Gunthorpe wrote:
> On Fri, Oct 10, 2025 at 10:28:36AM -0500, Jeremy Linton wrote:
> 

Yes, I agree, its just at the time the statment was around what is the 
most reliable early indicator, and since there isn't a hwcap or anything 
that ended up being the choice, as disgusting as it is.

Presumably once all this works out the sysfs/api surface will be more 
'defined'


> 
> Jason

---

## [177] dan.j.williams@intel.com — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

Jeremy Linton wrote:
> On 10/10/25 10:30 AM, Jason Gunthorpe wrote:
> > On Fri, Oct 10, 2025 at 10:28:36AM -0500, Jeremy Linton wrote:

It has definition today.

All guest-side TSM drivers currently call tsm_report_register(), that
establishes /sys/kernel/config/tsm/report which is the common cross-arch
transport for retrieving CVM launch attestation reports.

In the TEE I/O patches [1] a /sys/class/tsm/tsmX device will be created
by all platforms that support TEE I/O. However, systemd would need to be
careful to differentiate host-side TSMs vs guest-side, and that is only
possible when the TSM supports TEE I/O.

I would be open to adding a simple attribute to that class device for
this common "am I a CVM" question for systemd. Would just need to update
all the CVM guest drivers to register that class device in the non TEE
I/O case.

[1]: http://lore.kernel.org/20250911235647.3248419-2-dan.j.williams@intel.com

---

## [178] Jason Gunthorpe — 2025-10-10
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Fri, Oct 10, 2025 at 11:44:04AM -0700, dan.j.williams@intel.com wrote:
> Jeremy Linton wrote:
> > On 10/10/25 10:30 AM, Jason Gunthorpe wrote:

I suspect this ins't a TSM question but an existing question if any of
the underlying CC frameworks are enabled. 

It is this stuff:

https://github.com/systemd/systemd/blob/main/src/basic/confidential-virt.c
https://github.com/systemd/systemd/commit/2572bf6a39b6c548acef07fd25f461c5a88560af

  Like the s390 detection logic, the sysfs path being checked is not labeled
  as ABI, and may change in the future. It was chosen because its
  directly tied to the kernel's detection of the realm service interface
  rather to the Trusted Security Module (TSM) which is what is being
  triggered by the device entry.

Maybe a /sys/firmware/smc/rsi file might be appropriate?

Given how small a deployed fooprint ARM CCA has right now (ie none) it
would be good to fix this ASAP so it doesn't become entrenched.

Jason

---

## [179] Jeremy Linton — 2025-10-13
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

Hi,

On 10/10/25 5:34 PM, Jason Gunthorpe wrote:
> On Fri, Oct 10, 2025 at 11:44:04AM -0700, dan.j.williams@intel.com wrote:
>> Jeremy Linton wrote:

Except that you can see from the code that this problem is being solved 
in a hw platform dependent way for 4+ platforms now.

Ideally the sysfs node would be common across all those hw platforms and 
reflect the vm capabilities so the code doesn't' need #ifdef's. Meaning 
it shouldn't have the smc/rsi arm'ism in the name, and maybe shouldn't 
be in /sys/firmware


Thanks,

> 
> Given how small a deployed fooprint ARM CCA has right now (ie none) it

---

## [180] Aneesh Kumar K.V — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Fri, Oct 10, 2025 at 07:10:58AM -0500, Jeremy Linton wrote:
>> > Yes, use faux_device if you need/want a struct device to represent

IIUC, auxiliary_device needs a parent device, and the documentation
explains that it’s intended for cases where a large driver is split into
multiple dependent smaller ones.

If we want to use auxiliary_device for this case, what would serve as
the parent device?

-aneesh

---

## [181] Greg KH — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Oct 15, 2025 at 03:22:28PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@ziepe.ca> writes:
> 

The real device that has the resources you wish to share access to.  Are
there physical resources here you are sharing?  If so, that device is
the parent.  If there is no such thing, then just make a bunch of faux
devices and be done with it :)

thanks,

greg k-h

---

## [182] Jason Gunthorpe — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Oct 15, 2025 at 11:58:25AM +0200, Greg KH wrote:
> On Wed, Oct 15, 2025 at 03:22:28PM +0530, Aneesh Kumar K.V wrote:
> > Jason Gunthorpe <jgg@ziepe.ca> writes:

Which is the case here, you have a SMC interface that you want to
fracture into multiple subsystems.

> > If we want to use auxiliary_device for this case, what would serve as
> > the parent device?

You probably need to make a platform device for the discovered PSCI
interface from the firmware. Looks like DT will already have one, ACPI
could invent one..
 
> The real device that has the resources you wish to share access to.  Are
> there physical resources here you are sharing?  If so, that device is

At the very bottom of the stack it looks like the PSCI interface is
discovered first through DT/ACPI. The PSCI interface has RPCs that are
then used to discover if SMC/etc/etc are present and along the way it
makes platform devices to plug in subsystems to it based on what it
can discover.

It is just not sharing "resources" in the traditional sense, PSCI has
no registers or interrupts, yet it is a service provided by the
platform firmare.

Again faux devices don't serve the need here to load modules and do
driver binding.

Jason

---

## [183] Greg KH — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Oct 15, 2025 at 08:50:44AM -0300, Jason Gunthorpe wrote:
> On Wed, Oct 15, 2025 at 11:58:25AM +0200, Greg KH wrote:
> > On Wed, Oct 15, 2025 at 03:22:28PM +0530, Aneesh Kumar K.V wrote:

Great, so you have a real platform device down there at the "root" of
all of this, that is doleing out resources to other "child" drivers.

> It is just not sharing "resources" in the traditional sense, PSCI has
> no registers or interrupts, yet it is a service provided by the

Great, so it's a real firmware device, use that as a platform device and
use the resources available there.

> Again faux devices don't serve the need here to load modules and do
> driver binding.

If this really is a firmware thing, and you have a firmware device, then
I am confused why this was even brought up at all?  Use a real platform
device, with the resources that are needed to talk to this platform
device and you should be fine.

BUT, if you are making child devices that are NOT actually talking to
the firmware, then make it a faux device and deal with the fact that you
can't load modules because it's a fake device that no hardware
definition is there for :)

Does that make sense?

thanks,

greg k-h

---

## [184] Jason Gunthorpe — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Oct 15, 2025 at 01:57:38PM +0200, Greg KH wrote:

> If this really is a firmware thing, and you have a firmware device, then
> I am confused why this was even brought up at all?  Use a real platform

I think the issue today is the PSCI does not always get a
platform_device, fixing that seems straightforward then all the
downstream things can switch from using more platform devices to using
an aux device with the PSCI as the parent..

> BUT, if you are making child devices that are NOT actually talking to
> the firmware,

This thread is about how to bind various subsystems to this shared
firmware interface.

Jason

---

## [185] Greg KH — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Oct 15, 2025 at 09:15:33AM -0300, Jason Gunthorpe wrote:
> On Wed, Oct 15, 2025 at 01:57:38PM +0200, Greg KH wrote:
> 

Great, fix that up and it should get much easier.

> > BUT, if you are making child devices that are NOT actually talking to
> > the firmware,

Great, use the platform device that the firmware created for you!

thanks,

greg k-h

---

## [186] James Bottomley — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm
 platform device*

On Wed, 2025-10-15 at 08:50 -0300, Jason Gunthorpe wrote:
> On Wed, Oct 15, 2025 at 11:58:25AM +0200, Greg KH wrote:
[...]
> > The real device that has the resources you wish to share access
> > to.  Are there physical resources here you are sharing?  If so,

This came up for the SVSM as well: we want to expose things that can be
virtual devices or other resources that the guest discovers.  Our
conclusion was we either needed to share one of the virtual busses
(like virtio) or do our own svsm bus.  The agreement was to implement
our own bus, but we still haven't got around to it.

Regards,

James

---

## [187] Greg KH — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Oct 15, 2025 at 11:19:41AM -0400, James Bottomley wrote:
> On Wed, 2025-10-15 at 08:50 -0300, Jason Gunthorpe wrote:
> > On Wed, Oct 15, 2025 at 11:58:25AM +0200, Greg KH wrote:

I think it might be time to get around to it and not abuse other busses
:)

As an example, take the faux bus code as a base if you want a tiny
example.

thanks,

greg k-h

---

## [188] Jason Gunthorpe — 2025-10-15
*Subject: Re: [RFC PATCH v1 11/38] KVM: arm64: CCA: register host tsm platform
 device*

On Wed, Oct 15, 2025 at 11:19:41AM -0400, James Bottomley wrote:
> This came up for the SVSM as well: we want to expose things that can be
> virtual devices or other resources that the guest discovers.  Our

I think your own bus only makes sense if there is a structured
general discovery mechanism that can be used to automatically
enumerate the devices to create.

If you are open coding all the discovery via C tests in Linux then aux
bus is probably appropriate..

Jason

---
