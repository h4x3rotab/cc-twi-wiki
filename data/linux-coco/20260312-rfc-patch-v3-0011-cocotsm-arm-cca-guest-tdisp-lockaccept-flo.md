---
title: '[RFC PATCH v3 00/11] coco/TSM: Arm CCA guest TDISP lock/accept flow with verification and DMA enable'
date: 2026-03-12
last_reply: 2026-03-12
message_count: 12
participants: ['Aneesh Kumar K.V (Arm)']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-03-12

This patch series implements the TSM ->lock(), ->unlock(), and ->accept()
callbacks required for the TDISP setup with Arm CCA as per the RMM ALP17
specification [1].

The series adds the guest-side DA plumbing needed to transition a device
through TDI LOCK and RUN states, verify host-provided evidence against
RMM-provided digests, validate interface-report MMIO mappings, and enable
DMA only after attestation succeeds.

At a high level, the series includes:
- guest TSM callback registration and lock/unlock/accept hooks
- RHI DA helper support for TDI state transitions and object refresh
- host-cached DA object fetch APIs in guest
- RSI_VDEV_GET_INFO digest verification of certificate/VCA/report/measurement
- mapping validation for interface-report ranges and teardown on unlock
- DMA behavior updates for accepted devices (including swiotlb restrictions)
- vdev DMA enable after successful attestation

The series builds upon the TSM framework patches posted at [2]. A git repository
containing all the related changes is available at [3].

Testing / Usage

echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind

To transition the device to TDISP LOCK state:
echo tsm0 > /sys/bus/pci/devices/${DEVICE}/tsm/lock

To transition the device to TDISP RUN state:
echo 1 > /sys/bus/pci/devices/${DEVICE}/tsm/accept

echo ${DEVICE} > /sys/bus/pci/drivers_probe

Previous posting:
rfc-v1: https://lore.kernel.org/all/20250728135216.48084-1-aneesh.kumar@kernel.org
rfc-v2: https://lore.kernel.org/all/20251117140007.122062-1-aneesh.kumar@kernel.org

Changes from v2:
* rebase to latest kernel and core TSM changes
* Address review feedback.
* Interface report is now collected using core TSM framework
* swiotlb is now considered shared-memory pool and is not allowed to be used by accepted devices.

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp17.zip
[2] https://lore.kernel.org/all/20260303000207.1836586-1-dan.j.williams@intel.com
[3] https://gitlab.arm.com/linux-arm/linux-cca.git cca/topics/cca-tdisp-upstream-rfc-v3

Aneesh Kumar K.V (Arm) (11):
  coco: guest: arm64: Guest TSM callback and realm device lock support
  coco: guest: arm64: Fix a typo in the ARM_CCA_GUEST Kconfig help
    string ("and" -> "an").
  coco: guest: arm64: Add Realm Host Interface and guest DA helper
  coco: guest: arm64: Support guest-initiated TDI lock/unlock
    transitions
  coco: guest: arm64: Refresh interface-report cache during device lock
  coco: guest: arm64: Add measurement refresh via
    RHI_DA_VDEV_GET_MEASUREMENTS
  coco: guest: arm64: Add guest APIs to read host-cached DA objects
  coco: guest: arm64: Verify DA evidence with RSI_VDEV_GET_INFO digests
  coco: guest: arm64: Hook TSM accept to Realm TDISP RUN transition
  coco: arm64: dma: Update force_dma_unencrypted for accepted devices
  coco: guest: arm64: Enable vdev DMA after attestation

 arch/arm64/include/asm/mem_encrypt.h      |   6 +-
 arch/arm64/include/asm/rhi.h              |  58 ++++
 arch/arm64/include/asm/rsi.h              |   1 +
 arch/arm64/include/asm/rsi_cmds.h         |  73 +++++
 arch/arm64/include/asm/rsi_smc.h          |  51 +++
 arch/arm64/kernel/rsi.c                   |  10 +
 arch/arm64/mm/mem_encrypt.c               |  10 +
 drivers/virt/coco/Makefile                |   2 +-
 drivers/virt/coco/arm-cca-guest/Kconfig   |   9 +-
 drivers/virt/coco/arm-cca-guest/Makefile  |   1 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 358 +++++++++++++++++++++-
 drivers/virt/coco/arm-cca-guest/rhi-da.c  | 345 +++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h  |  17 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 289 +++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  65 ++++
 include/linux/swiotlb.h                   |   3 +
 kernel/dma/direct.c                       |   8 +
 kernel/dma/swiotlb.c                      |   3 +
 18 files changed, 1301 insertions(+), 8 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.h
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.h

---

## [2] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 01/11] coco: guest: arm64: Guest TSM callback and realm device lock support*

Register the TSM callback when the DA feature is supported by RSI. The
build order is also adjusted so that the TSM class is created before the
arm-cca-guest driver is initialized.

In addition, add support for the TDISP lock sequence. Writing a TSM
(TEE Security Manager) device name from `/sys/class/tsm` into `tsm/lock`
triggers the realm device lock operation.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi.h              |  1 +
 arch/arm64/include/asm/rsi_cmds.h         | 17 +++++++
 arch/arm64/include/asm/rsi_smc.h          |  1 +
 arch/arm64/kernel/rsi.c                   | 10 ++++
 drivers/virt/coco/Makefile                |  2 +-
 drivers/virt/coco/arm-cca-guest/Kconfig   |  5 ++
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 60 ++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-guest/rsi-da.h  | 35 +++++++++++++
 8 files changed, 129 insertions(+), 2 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.h

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index 34c8f649fe48..f5288551ae77 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -68,5 +68,6 @@ static inline int rsi_set_memory_range_shared(phys_addr_t start,
 				    RSI_CHANGE_DESTROYED);
 }
 
+bool rsi_has_da_feature(void);
 unsigned long realm_get_hyp_pagesize(void);
 #endif /* __ASM_RSI_H_ */
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index a341ce0eeda1..596bdc356f1a 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -169,4 +169,21 @@ static inline unsigned long rsi_host_call(struct rsi_host_call *rhi_call)
 	return res.a0;
 }
 
+/**
+ * rsi_features() - Read feature register
+ * @index: Feature register index
+ * @out: Feature register value is written to this pointer
+ *
+ * Return: RSI return code
+ */
+static inline unsigned long rsi_features(unsigned long index, u64 *out)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_FEATURES, index, &res);
+
+	*out = res.a1;
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 9ee8b5c7612e..4af4638fdd49 100644
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
index 29d3c20ce011..2816f31d0dc6 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -16,6 +16,7 @@
 #include <asm/rhi.h>
 
 static struct realm_config config;
+static u64 rsi_feat_reg0;
 static unsigned long ipa_change_alignment = PAGE_SIZE;
 
 unsigned long prot_ns_shared;
@@ -24,6 +25,12 @@ EXPORT_SYMBOL(prot_ns_shared);
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
+bool rsi_has_da_feature(void)
+{
+	return u64_get_bits(rsi_feat_reg0, RSI_FEATURE_REGISTER_0_DA);
+}
+EXPORT_SYMBOL_GPL(rsi_has_da_feature);
+
 bool cc_platform_has(enum cc_attr attr)
 {
 	switch (attr) {
@@ -159,6 +166,9 @@ void __init arm64_rsi_init(void)
 	if (!ipa_change_alignment)
 		return;
 
+	if (WARN_ON(rsi_features(0, &rsi_feat_reg0)))
+		return;
+
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index b323b0ae4f82..4f7e30f5aeb8 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -7,6 +7,6 @@ obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_INTEL_TDX_HOST)	+= tdx-host/
-obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
+obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index a42359a90558..5f7f284dae1a 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -1,11 +1,16 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+
 config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
+	select PCI_TSM if PCI
 	select TSM_REPORTS
 	select AUXILIARY_BUS
 	help
 	  The driver provides userspace interface to request and
 	  attestation report from the Realm Management Monitor(RMM).
+	  If the DA feature is supported, it also register with TSM framework.
 
 	  If you choose 'M' here, this module will be called
 	  arm-cca-guest.
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 3d5c0fe75500..1d78727702be 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -1,6 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /*
- * Copyright (C) 2023 ARM Ltd.
+ * Copyright (C) 2023-2025 ARM Ltd.
  */
 
 #include <linux/auxiliary_bus.h>
@@ -15,6 +15,10 @@
 
 #include <asm/rsi.h>
 
+#ifdef CONFIG_PCI_TSM
+#include "rsi-da.h"
+#endif
+
 /**
  * struct arm_cca_token_info - a descriptor for the token buffer.
  * @challenge:		Pointer to the challenge data
@@ -192,6 +196,53 @@ static void unregister_cca_tsm_report(void *data)
 	tsm_report_unregister(&arm_cca_tsm_report_ops);
 }
 
+#ifdef CONFIG_PCI_TSM
+static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pdev)
+{
+	int ret;
+
+	struct cca_guest_dsc *cca_dsc __free(kfree) =
+		kzalloc_obj(struct cca_guest_dsc);
+	if (!cca_dsc)
+		return ERR_PTR(-ENOMEM);
+
+	ret = pci_tsm_devsec_constructor(pdev, &cca_dsc->pci, tsm_dev);
+	if (ret)
+		return ERR_PTR(ret);
+
+	/* For now always return an error */
+	return ERR_PTR(-EIO);
+}
+
+static void cca_tsm_unlock(struct pci_tsm *tsm)
+{
+	struct cca_guest_dsc *cca_dsc = to_cca_guest_dsc(tsm->pdev);
+
+	kfree(cca_dsc);
+}
+
+static struct pci_tsm_ops cca_devsec_pci_ops = {
+	.lock = cca_tsm_lock,
+	.unlock = cca_tsm_unlock,
+};
+
+static void cca_devsec_tsm_remove(void *tsm_dev)
+{
+	tsm_unregister(tsm_dev);
+}
+
+static int cca_devsec_tsm_register(struct auxiliary_device *adev)
+{
+	struct tsm_dev *tsm_dev;
+
+	tsm_dev = tsm_register(&adev->dev, &cca_devsec_pci_ops);
+	if (IS_ERR(tsm_dev))
+		return PTR_ERR(tsm_dev);
+
+	return devm_add_action_or_reset(&adev->dev, cca_devsec_tsm_remove, tsm_dev);
+}
+#endif /* CONFIG_PCI_TSM */
+
 static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
 				const struct auxiliary_device_id *id)
 {
@@ -212,6 +263,12 @@ static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
 		return ret;
 	}
 
+#ifdef CONFIG_PCI_TSM
+	/* Allow tsm report even if tsm_register fails */
+	if (rsi_has_da_feature())
+		cca_devsec_tsm_register(adev);
+#endif
+
 	return 0;
 }
 
@@ -227,5 +284,6 @@ static struct auxiliary_driver cca_devsec_tsm_driver = {
 };
 module_auxiliary_driver(cca_devsec_tsm_driver);
 MODULE_AUTHOR("Sami Mujawar <sami.mujawar@arm.com>");
+MODULE_AUTHOR("Aneesh Kumar <aneesh.kumar@kernel.org>");
 MODULE_DESCRIPTION("Arm CCA Guest TSM Driver");
 MODULE_LICENSE("GPL");
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
new file mode 100644
index 000000000000..858bfdaf59c9
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -0,0 +1,35 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#ifndef _VIRT_COCO_RSI_DA_H_
+#define _VIRT_COCO_RSI_DA_H_
+
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
+#include <asm/rsi_smc.h>
+
+struct cca_guest_dsc {
+	struct pci_tsm_devsec pci;
+};
+
+static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm)
+		return NULL;
+	return container_of(tsm, struct cca_guest_dsc, pci.base_tsm);
+}
+
+/*
+ * Linux use device requester id as the vdev id.
+ */
+static inline int rsi_vdev_id(struct pci_dev *pdev)
+{
+	return (pci_domain_nr(pdev->bus) << 16) |
+	       PCI_DEVID(pdev->bus->number, pdev->devfn);
+}
+
+#endif

---

## [3] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 02/11] coco: guest: arm64: Fix a typo in the ARM_CCA_GUEST Kconfig help string ("and" -> "an").*

Fix a typo in Kconfig file.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-guest/Kconfig | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index 5f7f284dae1a..d295146bd92a 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -8,7 +8,7 @@ config ARM_CCA_GUEST
 	select TSM_REPORTS
 	select AUXILIARY_BUS
 	help
-	  The driver provides userspace interface to request and
+	  The driver provides userspace interface to request an
 	  attestation report from the Realm Management Monitor(RMM).
 	  If the DA feature is supported, it also register with TSM framework.

---

## [4] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 03/11] coco: guest: arm64: Add Realm Host Interface and guest DA helper*

- Add  guest-side `rhi-da` helper that drives the vdev TDI state machine
  via RHI host calls and translates the firmware status codes

This provides the basic RHI plumbing that later DA features rely on.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h              |  37 +++++
 drivers/virt/coco/arm-cca-guest/Makefile  |   1 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c |   3 +-
 drivers/virt/coco/arm-cca-guest/rhi-da.c  | 158 ++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h  |  14 ++
 5 files changed, 212 insertions(+), 1 deletion(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.h

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 0895dd92ea1d..029ccd77cfbf 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -21,4 +21,41 @@ unsigned long rhi_get_ipa_change_alignment(void);
 #define __RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT BIT(0)
 #define RHI_HOSTCONF_FEATURES		SMC_RHI_CALL(0x004F)
 #define RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT	SMC_RHI_CALL(0x0050)
+
+#define RHI_DA_SUCCESS				0x0
+#define RHI_DA_ERROR_INCOMPLETE			0x1
+#define RHI_DA_ERROR_DATA_NOT_AVAILABLE		0x2
+#define RHI_DA_ERROR_INVALID_VDEV_ID		0x3
+#define RHI_DA_ERROR_INVALID_OBJECT		0x4
+#define RHI_DA_ERROR_INPUT			0x5
+#define RHI_DA_ERROR_DEVICE			0x6
+#define RHI_DA_ERROR_INVALID_OFFSET		0x7
+#define RHI_DA_ERROR_ACCESS_FAILED		0x8
+#define RHI_DA_ERROR_BUSY			0x9
+#define RHI_DA_ABORTED_OPERATION_HAD_COMPLETED	0xA
+
+#define RHI_DA_FEATURE_OBJECT_SIZE		BIT(0)
+#define RHI_DA_FEATURE_OBJECT_READ		BIT(1)
+#define RHI_DA_FEATURE_VDEV_CONTINUE		BIT(2)
+#define RHI_DA_FEATURE_VDEV_GET_MEASUREMENT	BIT(3)
+#define RHI_DA_FEATURE_VDEV_GET_INTF_REPORT	BIT(4)
+#define RHI_DA_FEATURE_VDEV_SET_TDI_STATE	BIT(5)
+
+#define RHI_DA_BASE_FEATURE	(RHI_DA_FEATURE_OBJECT_SIZE |		\
+				 RHI_DA_FEATURE_OBJECT_READ |		\
+				 RHI_DA_FEATURE_VDEV_GET_INTF_REPORT |	\
+				 RHI_DA_FEATURE_VDEV_GET_MEASUREMENT |	\
+				 RHI_DA_FEATURE_VDEV_SET_TDI_STATE)
+#define RHI_DA_FEATURES			SMC_RHI_CALL(0x004B)
+
+#define RHI_DA_VDEV_CONTINUE		SMC_RHI_CALL(0x0051)
+
+enum rhi_tdi_state {
+	RHI_DA_TDI_CONFIG_UNLOCKED,
+	RHI_DA_TDI_CONFIG_LOCKED,
+	RHI_DA_TDI_CONFIG_RUN,
+};
+#define RHI_DA_VDEV_SET_TDI_STATE	SMC_RHI_CALL(0x0054)
+#define RHI_DA_VDEV_ABORT		SMC_RHI_CALL(0x0056)
+
 #endif
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 75a120e24fda..65c4cc52c154 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -2,3 +2,4 @@
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
 
 arm-cca-guest-y +=  arm-cca.o
+arm-cca-guest-$(CONFIG_PCI_TSM) +=  rhi-da.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 1d78727702be..07f74f67d22c 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -17,6 +17,7 @@
 
 #ifdef CONFIG_PCI_TSM
 #include "rsi-da.h"
+#include "rhi-da.h"
 #endif
 
 /**
@@ -265,7 +266,7 @@ static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
 
 #ifdef CONFIG_PCI_TSM
 	/* Allow tsm report even if tsm_register fails */
-	if (rsi_has_da_feature())
+	if (rsi_has_da_feature() && rhi_has_da_support())
 		cca_devsec_tsm_register(adev);
 #endif
 
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
new file mode 100644
index 000000000000..0a04c0ec9320
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -0,0 +1,158 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#include "rsi-da.h"
+#include "rhi-da.h"
+
+/* return value to indicate the need to call rhi_vdev_continue*/
+#define E_INCOMPLETE	1
+static inline int map_rhi_da_error(unsigned long rhi_da_error)
+{
+	switch (rhi_da_error) {
+	case RHI_DA_SUCCESS:
+		return 0;
+	case RHI_DA_ERROR_INCOMPLETE:
+		return E_INCOMPLETE;
+	case RHI_DA_ERROR_BUSY:
+		return -EBUSY;
+	case RHI_DA_ERROR_INPUT:
+	case RHI_DA_ERROR_INVALID_VDEV_ID:
+		return -EINVAL;
+	case RHI_DA_ERROR_ACCESS_FAILED:
+		return -EFAULT;
+	case RHI_DA_ERROR_DEVICE:
+		return -EIO;
+	case RHI_DA_ERROR_INVALID_OBJECT:
+		return -EINVAL;
+	default:
+		return -EIO;
+	}
+}
+
+bool rhi_has_da_support(void)
+{
+	int ret;
+
+	struct rsi_host_call *rhi_call __free(kfree) =
+		kmalloc(sizeof(*rhi_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_FEATURES;
+
+	ret = rsi_host_call(rhi_call);
+	if (ret != RSI_SUCCESS || rhi_call->gprs[0] == SMCCC_RET_NOT_SUPPORTED)
+		return false;
+
+	/* For base DA to work we need these to be supported */
+	if ((rhi_call->gprs[0] & RHI_DA_BASE_FEATURE) == RHI_DA_BASE_FEATURE)
+		return true;
+
+	return false;
+}
+
+static inline int rhi_vdev_continue(unsigned long vdev_id, unsigned long cookie)
+{
+	unsigned long ret;
+
+	struct rsi_host_call *rhi_call __free(kfree) =
+		kmalloc(sizeof(*rhi_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_CONTINUE;
+	rhi_call->gprs[1] = vdev_id;
+	rhi_call->gprs[2] = cookie;
+
+	ret = rsi_host_call(rhi_call);
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	return map_rhi_da_error(rhi_call->gprs[0]);
+}
+
+static int __rhi_vdev_abort(unsigned long vdev_id, unsigned long *da_error)
+{
+	unsigned long ret;
+	struct rsi_host_call *rhi_call __free(kfree) =
+		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_ABORT;
+	rhi_call->gprs[1] = vdev_id;
+
+	ret = rsi_host_call(rhi_call);
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	*da_error = rhi_call->gprs[0];
+	return 0;
+}
+
+static bool should_abort_rhi_call_loop(unsigned long vdev_id)
+{
+	int ret;
+
+	cond_resched();
+	if (signal_pending(current)) {
+		unsigned long da_error;
+
+		ret = __rhi_vdev_abort(vdev_id, &da_error);
+		/* consider all kind of error as not aborted */
+		if (!ret && (da_error == RHI_DA_SUCCESS))
+			return true;
+	}
+	return false;
+}
+
+static int __rhi_vdev_set_tdi_state(unsigned long vdev_id,
+				    enum rhi_tdi_state target_state,
+				    unsigned long *cookie)
+{
+	unsigned long ret;
+
+	struct rsi_host_call *rhi_call __free(kfree) =
+		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_SET_TDI_STATE;
+	rhi_call->gprs[1] = vdev_id;
+	rhi_call->gprs[2] = target_state;
+
+	ret = rsi_host_call(rhi_call);
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	*cookie = rhi_call->gprs[1];
+	return map_rhi_da_error(rhi_call->gprs[0]);
+}
+
+int rhi_vdev_set_tdi_state(struct pci_dev *pdev, enum rhi_tdi_state target_state)
+{
+	int ret;
+	unsigned long cookie;
+	int vdev_id = rsi_vdev_id(pdev);
+
+	for (;;) {
+		ret = __rhi_vdev_set_tdi_state(vdev_id, target_state, &cookie);
+		if (ret != -EBUSY)
+			break;
+		cond_resched();
+	}
+
+	while (ret == E_INCOMPLETE) {
+		if (should_abort_rhi_call_loop(vdev_id))
+			return -EINTR;
+		ret = rhi_vdev_continue(vdev_id, cookie);
+	}
+
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.h b/drivers/virt/coco/arm-cca-guest/rhi-da.h
new file mode 100644
index 000000000000..43c1cda8738d
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -0,0 +1,14 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#ifndef _VIRT_COCO_RHI_DA_H_
+#define _VIRT_COCO_RHI_DA_H_
+
+#include <asm/rhi.h>
+
+struct pci_dev;
+bool rhi_has_da_support(void);
+int rhi_vdev_set_tdi_state(struct pci_dev *pdev, enum rhi_tdi_state target_state);
+#endif

---

## [5] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 04/11] coco: guest: arm64: Support guest-initiated TDI lock/unlock transitions*

Add guest helpers to drive TDI state transitions through RHI:
- cca_device_lock() -> RHI_DA_TDI_CONFIG_LOCKED
- cca_device_unlock() -> RHI_DA_TDI_CONFIG_UNLOCKED

Use these helpers in the PCI TSM lock/unlock callbacks so a successful
lock path returns a live pci_tsm handle and unlock transitions the device
back to unlocked state.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-guest/Makefile  |  2 +-
 drivers/virt/coco/arm-cca-guest/arm-cca.c |  9 ++++--
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 34 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  2 ++
 4 files changed, 44 insertions(+), 3 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.c

diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 65c4cc52c154..11db7af095c9 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -2,4 +2,4 @@
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
 
 arm-cca-guest-y +=  arm-cca.o
-arm-cca-guest-$(CONFIG_PCI_TSM) +=  rhi-da.o
+arm-cca-guest-$(CONFIG_PCI_TSM) +=  rhi-da.o rsi-da.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 07f74f67d22c..5e3a66315c70 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -211,14 +211,19 @@ static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pde
 	if (ret)
 		return ERR_PTR(ret);
 
-	/* For now always return an error */
-	return ERR_PTR(-EIO);
+	ret = cca_device_lock(pdev);
+	if (ret)
+		return ERR_PTR(ret);
+
+	return &no_free_ptr(cca_dsc)->pci.base_tsm;
 }
 
 static void cca_tsm_unlock(struct pci_tsm *tsm)
 {
 	struct cca_guest_dsc *cca_dsc = to_cca_guest_dsc(tsm->pdev);
 
+	cca_device_unlock(tsm->pdev);
+
 	kfree(cca_dsc);
 }
 
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
new file mode 100644
index 000000000000..2c3017933fb0
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -0,0 +1,34 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <linux/pci.h>
+#include <asm/rsi_cmds.h>
+
+#include "rsi-da.h"
+#include "rhi-da.h"
+
+int cca_device_lock(struct pci_dev *pdev)
+{
+	int ret;
+
+	ret = rhi_vdev_set_tdi_state(pdev, RHI_DA_TDI_CONFIG_LOCKED);
+	if (ret) {
+		pci_err(pdev, "failed to lock the device (%d)\n", ret);
+		return ret;
+	}
+	return 0;
+}
+
+int cca_device_unlock(struct pci_dev *pdev)
+{
+	int ret;
+
+	ret = rhi_vdev_set_tdi_state(pdev, RHI_DA_TDI_CONFIG_UNLOCKED);
+	if (ret) {
+		pci_err(pdev, "failed to unlock the device (%d)\n", ret);
+		return ret;
+	}
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 858bfdaf59c9..3619a75e160e 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -32,4 +32,6 @@ static inline int rsi_vdev_id(struct pci_dev *pdev)
 	       PCI_DEVID(pdev->bus->number, pdev->devfn);
 }
 
+int cca_device_lock(struct pci_dev *pdev);
+int cca_device_unlock(struct pci_dev *pdev);
 #endif

---

## [6] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 05/11] coco: guest: arm64: Refresh interface-report cache during device lock*

Add support for RHI_DA_VDEV_GET_INTERFACE_REPORT and use it to refresh the
host-side cached interface report when a device is locked.

Implement rhi_update_vdev_interface_report_cache() with busy retry and
cookie-based CONTINUE handling for incomplete operations. Surface the flow
through cca_update_device_object_cache(), and call it from the lock path so
the interface report is fetched before lock succeeds.

On refresh failure, unwind by unlocking the device and returning the error.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h              |  1 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c |  6 ++++
 drivers/virt/coco/arm-cca-guest/rhi-da.c  | 44 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h  |  1 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 13 +++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  1 +
 6 files changed, 66 insertions(+)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 029ccd77cfbf..076aecbce1c5 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -49,6 +49,7 @@ unsigned long rhi_get_ipa_change_alignment(void);
 #define RHI_DA_FEATURES			SMC_RHI_CALL(0x004B)
 
 #define RHI_DA_VDEV_CONTINUE		SMC_RHI_CALL(0x0051)
+#define RHI_DA_VDEV_GET_INTERFACE_REPORT SMC_RHI_CALL(0x0053)
 
 enum rhi_tdi_state {
 	RHI_DA_TDI_CONFIG_UNLOCKED,
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 5e3a66315c70..cb9f389be8b8 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -215,6 +215,12 @@ static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pde
 	if (ret)
 		return ERR_PTR(ret);
 
+	ret = cca_update_device_object_cache(pdev, NULL);
+	if (ret) {
+		cca_device_unlock(pdev);
+		return ERR_PTR(ret);
+	}
+
 	return &no_free_ptr(cca_dsc)->pci.base_tsm;
 }
 
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
index 0a04c0ec9320..4597fb87044e 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -156,3 +156,47 @@ int rhi_vdev_set_tdi_state(struct pci_dev *pdev, enum rhi_tdi_state target_state
 
 	return ret;
 }
+
+static inline int rhi_vdev_get_interface_report(unsigned long vdev_id,
+						unsigned long *cookie)
+{
+	unsigned long ret;
+
+	struct rsi_host_call *rhi_call __free(kfree) =
+		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_GET_INTERFACE_REPORT;
+	rhi_call->gprs[1] = vdev_id;
+
+	ret = rsi_host_call(rhi_call);
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	*cookie = rhi_call->gprs[1];
+	return map_rhi_da_error(rhi_call->gprs[0]);
+}
+
+int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev)
+{
+	int ret;
+	unsigned long cookie;
+	int vdev_id = rsi_vdev_id(pdev);
+
+	for (;;) {
+		ret = rhi_vdev_get_interface_report(vdev_id, &cookie);
+		if (ret != -EBUSY)
+			break;
+		cond_resched();
+	}
+
+	while (ret == E_INCOMPLETE) {
+		if (should_abort_rhi_call_loop(vdev_id))
+			return -EINTR;
+		ret = rhi_vdev_continue(vdev_id, cookie);
+	}
+
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.h b/drivers/virt/coco/arm-cca-guest/rhi-da.h
index 43c1cda8738d..8b7faf4d1c8a 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -11,4 +11,5 @@
 struct pci_dev;
 bool rhi_has_da_support(void);
 int rhi_vdev_set_tdi_state(struct pci_dev *pdev, enum rhi_tdi_state target_state);
+int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev);
 #endif
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 2c3017933fb0..6c78f0e2f3a1 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -32,3 +32,16 @@ int cca_device_unlock(struct pci_dev *pdev)
 	}
 	return 0;
 }
+
+int cca_update_device_object_cache(struct pci_dev *pdev, const u8 *nonce)
+{
+	int ret;
+
+	ret = rhi_update_vdev_interface_report_cache(pdev);
+	if (ret) {
+		pci_err(pdev, "failed to get interface report (%d)\n", ret);
+		return ret;
+	}
+
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 3619a75e160e..9ab3408d6354 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -34,4 +34,5 @@ static inline int rsi_vdev_id(struct pci_dev *pdev)
 
 int cca_device_lock(struct pci_dev *pdev);
 int cca_device_unlock(struct pci_dev *pdev);
+int cca_update_device_object_cache(struct pci_dev *pdev, const u8 *nonce);
 #endif

---

## [7] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 06/11] coco: guest: arm64: Add measurement refresh via RHI_DA_VDEV_GET_MEASUREMENTS*

Add guest support to request fresh device measurements using
RHI_DA_VDEV_GET_MEASUREMENTS.

Define measurement request parameters (flags + nonce), request RAW
measurements, and implement cookie-based continuation for incomplete DA
operations. Extend cca_update_device_object_cache() to refresh both
interface report and measurements.

Because RHI buffers are shared with the host, add shared-page allocation
helpers that convert pages to decrypted/shared memory before use and restore
them to encrypted/private state on free.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h              | 13 ++++
 drivers/virt/coco/arm-cca-guest/arm-cca.c |  1 +
 drivers/virt/coco/arm-cca-guest/rhi-da.c  | 79 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h  |  1 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 42 +++++++++++-
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  2 +
 6 files changed, 137 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 076aecbce1c5..d4759f410a17 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -49,6 +49,19 @@ unsigned long rhi_get_ipa_change_alignment(void);
 #define RHI_DA_FEATURES			SMC_RHI_CALL(0x004B)
 
 #define RHI_DA_VDEV_CONTINUE		SMC_RHI_CALL(0x0051)
+#define RHI_VDEV_MEASURE_HASH	0x0
+#define RHI_VDEV_MEASURE_RAW	0x1
+struct rhi_vdev_measurement_params {
+	union {
+		u64 flags;
+		u8 padding0[256];
+	};
+	union {
+		u8 nonce[32];
+		u8 padding1[256];
+	};
+};
+#define RHI_DA_VDEV_GET_MEASUREMENTS	SMC_RHI_CALL(0x0052)
 #define RHI_DA_VDEV_GET_INTERFACE_REPORT SMC_RHI_CALL(0x0053)
 
 enum rhi_tdi_state {
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index cb9f389be8b8..435645e97ab4 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -215,6 +215,7 @@ static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pde
 	if (ret)
 		return ERR_PTR(ret);
 
+	/* collect evidence without nonce */
 	ret = cca_update_device_object_cache(pdev, NULL);
 	if (ret) {
 		cca_device_unlock(pdev);
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
index 4597fb87044e..5130d4911f3a 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -200,3 +200,82 @@ int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev)
 
 	return ret;
 }
+
+static inline int rhi_vdev_get_measurements(unsigned long vdev_id,
+					    phys_addr_t vdev_meas_phys,
+					    unsigned long *cookie)
+{
+	unsigned long ret;
+
+	struct rsi_host_call *rhi_call __free(kfree) =
+		kmalloc(sizeof(*rhi_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_GET_MEASUREMENTS;
+	rhi_call->gprs[1] = vdev_id;
+	rhi_call->gprs[2] = vdev_meas_phys;
+
+	ret = rsi_host_call(rhi_call);
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	*cookie = rhi_call->gprs[1];
+	return map_rhi_da_error(rhi_call->gprs[0]);
+}
+
+static inline struct rhi_vdev_measurement_params *alloc_vdev_meas_params(void)
+{
+	struct page *pages;
+
+	pages = alloc_shared_pages(NUMA_NO_NODE, GFP_KERNEL, sizeof(struct rhi_vdev_measurement_params));
+	if (!pages)
+		return NULL;
+	return page_address(pages);
+}
+
+static inline void vdev_meas_params_free(struct rhi_vdev_measurement_params *params)
+{
+	struct page *pages = virt_to_page(params);
+
+	free_shared_pages(pages, sizeof(struct rhi_vdev_measurement_params));
+}
+
+DEFINE_FREE(vdev_meas_params_free, struct rhi_vdev_measurement_params *, if (_T) vdev_meas_params_free(_T))
+int rhi_update_vdev_measurements_cache(struct pci_dev *pdev, const u8 *nonce)
+{
+	int ret;
+	unsigned long cookie;
+	int vdev_id = rsi_vdev_id(pdev);
+	phys_addr_t vdev_meas_phys;
+
+	struct rhi_vdev_measurement_params *dev_meas __free(vdev_meas_params_free) =
+		alloc_vdev_meas_params();
+	if (!dev_meas)
+		return -ENOMEM;
+
+	vdev_meas_phys = virt_to_phys(dev_meas);
+	/* request for raw bitstream */
+	dev_meas->flags = RHI_VDEV_MEASURE_RAW;
+	if (nonce)
+		memcpy(dev_meas->nonce, nonce, 32);
+
+	for (;;) {
+		ret = rhi_vdev_get_measurements(vdev_id, vdev_meas_phys, &cookie);
+		if (ret != -EBUSY)
+			break;
+		cond_resched();
+	}
+
+	while (ret == E_INCOMPLETE) {
+		if (should_abort_rhi_call_loop(vdev_id))
+			return -EINTR;
+		ret = rhi_vdev_continue(vdev_id, cookie);
+	}
+
+	if (ret)
+		pci_err(pdev, "failed to get device measurement (%d)\n", ret);
+	return ret;
+}
+
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.h b/drivers/virt/coco/arm-cca-guest/rhi-da.h
index 8b7faf4d1c8a..d32ccc48c0d0 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -12,4 +12,5 @@ struct pci_dev;
 bool rhi_has_da_support(void);
 int rhi_vdev_set_tdi_state(struct pci_dev *pdev, enum rhi_tdi_state target_state);
 int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev);
+int rhi_update_vdev_measurements_cache(struct pci_dev *pdev, const u8 *nonce);
 #endif
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 6c78f0e2f3a1..9f9e54174813 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -4,6 +4,7 @@
  */
 
 #include <linux/pci.h>
+#include <linux/mem_encrypt.h>
 #include <asm/rsi_cmds.h>
 
 #include "rsi-da.h"
@@ -33,6 +34,45 @@ int cca_device_unlock(struct pci_dev *pdev)
 	return 0;
 }
 
+struct page *alloc_shared_pages(int nid, gfp_t gfp_mask, unsigned long min_size)
+{
+	int ret;
+	struct page *page;
+	/* We should normalize the size based on hypervisor page size */
+	int page_order = get_order(min_size);
+
+	page = alloc_pages_node(nid, gfp_mask | __GFP_ZERO, page_order);
+	if (!page)
+		return NULL;
+
+	ret = set_memory_decrypted((unsigned long)page_address(page),
+				   1 << page_order);
+	/*
+	 * If set_memory_decrypted() fails then we don't know what state the
+	 * page is in, so we can't free it. Instead we leak it.
+	 * set_memory_decrypted() will already have WARNed.
+	 */
+	if (ret)
+		return NULL;
+
+	return page;
+}
+
+int free_shared_pages(struct page *page, unsigned long size)
+{
+	int ret;
+	/* We should normalize the size based on hypervisor page size */
+	int page_order = get_order(size);
+
+	ret = set_memory_encrypted((unsigned long)page_address(page), 1 << page_order);
+	/* If we fail to mark it encrypted don't free it back */
+	if (ret)
+		return ret;
+
+	__free_pages(page, page_order);
+	return 0;
+}
+
 int cca_update_device_object_cache(struct pci_dev *pdev, const u8 *nonce)
 {
 	int ret;
@@ -43,5 +83,5 @@ int cca_update_device_object_cache(struct pci_dev *pdev, const u8 *nonce)
 		return ret;
 	}
 
-	return 0;
+	return rhi_update_vdev_measurements_cache(pdev, nonce);
 }
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 9ab3408d6354..2e3440f7c849 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -35,4 +35,6 @@ static inline int rsi_vdev_id(struct pci_dev *pdev)
 int cca_device_lock(struct pci_dev *pdev);
 int cca_device_unlock(struct pci_dev *pdev);
 int cca_update_device_object_cache(struct pci_dev *pdev, const u8 *nonce);
+struct page *alloc_shared_pages(int nid, gfp_t gfp_mask, unsigned long min_size);
+int free_shared_pages(struct page *page, unsigned long min_size);
 #endif

---

## [8] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 07/11] coco: guest: arm64: Add guest APIs to read host-cached DA objects*

Introduce guest-side helpers to read host-cached DA objects
(certificate, VCA, interface report, and measurements).

Add RHI_DA_OBJECT_SIZE and RHI_DA_OBJECT_READ definitions, then implement
rhi_read_cached_object() that:
- queries object size from host
- validates size against MAX_CACHE_OBJ_SIZE
- allocates a shared buffer
- issues OBJECT_READ into shared memory
- copies data into private memory and frees shared pages

Export the helper for later evidence-collection and verification code.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             |  7 +++
 drivers/virt/coco/arm-cca-guest/rhi-da.c | 64 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h |  1 +
 drivers/virt/coco/arm-cca-guest/rsi-da.h |  2 +
 4 files changed, 74 insertions(+)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index d4759f410a17..8f9ea4a4bb7c 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -48,6 +48,13 @@ unsigned long rhi_get_ipa_change_alignment(void);
 				 RHI_DA_FEATURE_VDEV_SET_TDI_STATE)
 #define RHI_DA_FEATURES			SMC_RHI_CALL(0x004B)
 
+#define RHI_DA_OBJECT_CERTIFICATE		0x1
+#define RHI_DA_OBJECT_MEASUREMENT		0x2
+#define RHI_DA_OBJECT_INTERFACE_REPORT		0x3
+#define RHI_DA_OBJECT_VCA			0x4
+#define RHI_DA_OBJECT_SIZE		SMC_RHI_CALL(0x004C)
+#define RHI_DA_OBJECT_READ		SMC_RHI_CALL(0x004D)
+
 #define RHI_DA_VDEV_CONTINUE		SMC_RHI_CALL(0x0051)
 #define RHI_VDEV_MEASURE_HASH	0x0
 #define RHI_VDEV_MEASURE_RAW	0x1
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
index 5130d4911f3a..c9b05fddccb9 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -3,6 +3,8 @@
  * Copyright (C) 2026 ARM Ltd.
  */
 
+#include <linux/string.h>
+
 #include "rsi-da.h"
 #include "rhi-da.h"
 
@@ -279,3 +281,65 @@ int rhi_update_vdev_measurements_cache(struct pci_dev *pdev, const u8 *nonce)
 	return ret;
 }
 
+int rhi_read_cached_object(int vdev_id, int da_object_type, void **object, int *object_size)
+{
+	int ret;
+	int max_data_len;
+	void *data_buf_shared;
+	struct page *shared_pages;
+
+	*object_size = 0;
+	*object = NULL;
+
+	struct rsi_host_call *rhicall __free(kfree) =
+		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhicall)
+		return -ENOMEM;
+
+	rhicall->imm = 0;
+	rhicall->gprs[0] = RHI_DA_OBJECT_SIZE;
+	rhicall->gprs[1] = vdev_id;
+	rhicall->gprs[2] = da_object_type;
+
+	ret = rsi_host_call(rhicall);
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	if (rhicall->gprs[0] != RHI_DA_SUCCESS)
+		return -EIO;
+
+	/* validate against the max cache object size used on host. */
+	max_data_len = rhicall->gprs[1];
+	if (max_data_len > MAX_CACHE_OBJ_SIZE || max_data_len == 0)
+		return -EIO;
+
+	shared_pages = alloc_shared_pages(NUMA_NO_NODE, GFP_KERNEL, max_data_len);
+	if (!shared_pages)
+		return -ENOMEM;
+
+	data_buf_shared = page_address(shared_pages);
+
+	rhicall->imm = 0;
+	rhicall->gprs[0] = RHI_DA_OBJECT_READ;
+	rhicall->gprs[1] = vdev_id;
+	rhicall->gprs[2] = da_object_type;
+	rhicall->gprs[3] = virt_to_phys(data_buf_shared);
+	rhicall->gprs[4] = max_data_len;
+	rhicall->gprs[5] = 0; /* offset within the data buffer */
+	ret = rsi_host_call(rhicall);
+	if (ret != RSI_SUCCESS || rhicall->gprs[0] != RHI_DA_SUCCESS) {
+		free_shared_pages(shared_pages, max_data_len);
+		return -EIO;
+	}
+
+	void *data_buf_private = kvmemdup(data_buf_shared,
+					  max_data_len, GFP_KERNEL);
+	/* free the shared pages irrespective of error condition */
+	free_shared_pages(shared_pages, max_data_len);
+	if (!data_buf_private)
+		return -ENOMEM;
+
+	*object = data_buf_private;
+	*object_size = max_data_len;
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.h b/drivers/virt/coco/arm-cca-guest/rhi-da.h
index d32ccc48c0d0..f7655d7ecf18 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -13,4 +13,5 @@ bool rhi_has_da_support(void);
 int rhi_vdev_set_tdi_state(struct pci_dev *pdev, enum rhi_tdi_state target_state);
 int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev);
 int rhi_update_vdev_measurements_cache(struct pci_dev *pdev, const u8 *nonce);
+int rhi_read_cached_object(int vdev_id, int da_object_type, void **object, int *object_size);
 #endif
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 2e3440f7c849..f28dc44b5cd2 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -10,6 +10,8 @@
 #include <linux/pci-tsm.h>
 #include <asm/rsi_smc.h>
 
+#define MAX_CACHE_OBJ_SIZE	SZ_16M
+
 struct cca_guest_dsc {
 	struct pci_tsm_devsec pci;
 };

---

## [9] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 08/11] coco: guest: arm64: Verify DA evidence with RSI_VDEV_GET_INFO digests*

Add guest-side evidence verification based on RSI_VDEV_GET_INFO and use the
verified TDISP interface report to validate Realm MMIO mappings.

During lock:
- refresh host caches from device
- read certificate/VCA/interface-report/measurement objects from host cache
- fetch trusted digest metadata from RSI_VDEV_GET_INFO
- verify host-provided objects against RSI digests
- initialize and populate PCI TSM evidence objects
- preserve lock/meas/report nonces and digests in guest state

Add mapping helpers to walk MMIO entries from the TDISP report and perform
RSI_VDEV_VALIDATE_MAPPING on map, or RIPAS destroy on unmap. Reject malformed
range progress while validating.

During unlock:
- invalidate mappings derived from the evidence report
- unlock the device and tear down MMIO bookkeeping

This ensures host-cached DA objects are cryptographically verified before
being trusted for mapping and attestation state transitions.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h         |  40 +++
 arch/arm64/include/asm/rsi_smc.h          |  48 ++++
 drivers/virt/coco/arm-cca-guest/Kconfig   |   2 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 287 +++++++++++++++++++++-
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 145 +++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  22 ++
 6 files changed, 533 insertions(+), 11 deletions(-)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 596bdc356f1a..f72d8e0cd422 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -186,4 +186,44 @@ static inline unsigned long rsi_features(unsigned long index, u64 *out)
 	return res.a0;
 }
 
+static inline long
+rsi_vdev_validate_mapping(unsigned long vdev_id,
+			  phys_addr_t ipa_base, phys_addr_t ipa_top,
+			  phys_addr_t pa_base, phys_addr_t *next_ipa,
+			  unsigned long flags, unsigned long lock_nonce,
+			  unsigned long meas_nonce, unsigned long report_nonce)
+{
+	struct arm_smccc_1_2_regs res;
+	struct arm_smccc_1_2_regs regs = {
+		.a0 = SMC_RSI_VDEV_VALIDATE_MAPPING,
+		.a1 = vdev_id,
+		.a2 = ipa_base,
+		.a3 = ipa_top,
+		.a4 = pa_base,
+		.a5 = flags,
+		.a6 = lock_nonce,
+		.a7 = meas_nonce,
+		.a8 = report_nonce,
+	};
+
+	arm_smccc_1_2_invoke(&regs, &res);
+	*next_ipa = res.a1;
+
+	if (res.a2 != RSI_ACCEPT)
+		return -EPERM;
+
+	return res.a0;
+}
+
+static inline unsigned long rsi_vdev_get_info(unsigned long vdev_id,
+					      unsigned long digest_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_VDEV_GET_INFO,
+			     vdev_id, digest_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 4af4638fdd49..5f1837282237 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -125,6 +125,9 @@
 
 #ifndef __ASSEMBLER__
 
+#define RSI_HASH_SHA_256 0
+#define RSI_HASH_SHA_512 1
+
 struct realm_config {
 	union {
 		struct {
@@ -183,6 +186,51 @@ struct realm_config {
  */
 #define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
 
+struct rsi_vdevice_info {
+	union {
+		struct {
+			u64 flags;
+			u64 cert_id;
+			union {
+				u8 hash_algo;
+				u64 padding0;
+			};
+			u64 lock_nonce;
+			u64 meas_nonce;
+			u64 report_nonce;
+			u64 tdisp_version;
+			union {
+				u8 state;
+				u64 padding1;
+			};
+
+		};
+		u8 padding2[0x40];
+	};
+	union { /* 0x40  */
+		struct {
+			u8 vca_digest[0x40];
+			u8 cert_digest[0x40];
+			u8 pubkey_digest[0x40];
+			u8 meas_digest[0x40];
+			u8 report_digest[0x40];
+		};
+		u8 padding3[0x200 - 0x40];
+	};
+};
+
+/*
+ * Get information for a device.
+ * arg1 == Realm device identifier (vdev id)
+ * arg2 == IPA to which configuration data will be written
+ * ret0 == Status / error
+ */
+#define SMC_RSI_VDEV_GET_INFO			SMC_RSI_FID(0x19D)
+
+#define RSI_DEV_MEM_COHERENT		BIT(0)
+#define RSI_DEV_MEM_LIMITED_ORDER	BIT(1)
+#define SMC_RSI_VDEV_VALIDATE_MAPPING		SMC_RSI_FID(0x19F)
+
 struct rsi_host_call {
 	union {
 		u16 imm;
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index d295146bd92a..8ed4b95df5e4 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -5,6 +5,8 @@ config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
 	select PCI_TSM if PCI
+	select CRYPTO_LIB_SHA256
+	select CRYPTO_LIB_SHA512
 	select TSM_REPORTS
 	select AUXILIARY_BUS
 	help
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 435645e97ab4..80ee20c8a7a6 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -198,39 +198,304 @@ static void unregister_cca_tsm_report(void *data)
 }
 
 #ifdef CONFIG_PCI_TSM
+
+static int __maybe_unused
+cca_update_dev_measurements(struct pci_dev *pdev, const u8 *nonce)
+{
+	int ret;
+	void *measurements;
+	int measurements_size;
+	int vdev_id = rsi_vdev_id(pdev);
+	struct pci_tsm_evidence *evidence;
+	struct rsi_vdevice_info *dev_info;
+	struct pci_tsm_evidence_object *obj;
+	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+
+	/* Regenerate the measurement from the device */
+	ret = rhi_update_vdev_measurements_cache(pdev, nonce);
+	if (ret) {
+		pci_err(pdev, "failed to update device measurements from device (%d)\n", ret);
+		return ret;
+	}
+
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_MEASUREMENT,
+				     &measurements, &measurements_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device measurements from the host (%d)\n", ret);
+		return ret;
+	}
+
+	dev_info = kmalloc(sizeof(*dev_info), GFP_KERNEL);
+	if (!dev_info) {
+		ret = -ENOMEM;
+		goto free_measurements;
+	}
+
+	if (rsi_vdev_get_info(vdev_id, virt_to_phys(dev_info))) {
+		pci_err(pdev, "failed to get device digests (%d)\n", ret);
+		ret = -EIO;
+		goto free_dev_info;
+	}
+
+	/* Make sure no unexpected lock/unlock operation happened from guest */
+	if (dsc->dev_info.lock_nonce != dev_info->lock_nonce) {
+		pci_err(pdev, "Unexpected lock/unlock operation from host (%d)\n", ret);
+		ret = -EIO;
+		goto free_dev_info;
+	}
+
+	/*
+	 * Verify that the digests of the provided reports match with the
+	 * digests from RMM
+	 */
+	ret = cca_verify_digest(dev_info->hash_algo, measurements,
+				measurements_size, dev_info->meas_digest);
+	if (ret) {
+		pci_err(pdev, "RMM provided digest mismatch (%d)\n", ret);
+		goto free_dev_info;
+	}
+
+	/* fill evidence details */
+	evidence = &dsc->pci.base_tsm.evidence;
+
+	/* Now update the evidence under lock. */
+	down_write(&evidence->lock);
+	evidence->generation = dev_info->meas_nonce;
+
+	obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_MEASUREMENTS];
+	if (obj->data)
+		kvfree(obj->data);
+	obj->data = measurements;
+	obj->len = measurements_size;
+
+	dsc->dev_info.meas_nonce    = dev_info->meas_nonce;
+	memcpy(dsc->dev_info.meas_digest, dev_info->meas_digest, SHA512_DIGEST_SIZE);
+	up_write(&evidence->lock);
+
+	kfree(dev_info);
+	return 0;
+
+free_dev_info:
+	kfree(dev_info);
+free_measurements:
+	kvfree(measurements);
+	return ret;
+}
+
+static int cca_collect_dev_evidence(struct pci_dev *pdev, struct cca_guest_dsc *dsc)
+{
+	int ret;
+	int vdev_id = rsi_vdev_id(pdev);
+	struct pci_tsm_evidence *evidence;
+	struct rsi_vdevice_info *dev_info;
+	struct pci_tsm_evidence_object *obj;
+	void *certificate, *vca, *interface_report, *measurements;
+	int certificate_size, vca_size, interface_report_size, measurements_size;
+
+	/* Regenerate interface report and measurement from the device */
+	ret = cca_update_device_object_cache(pdev, NULL);
+	if (ret) {
+		pci_err(pdev, "failed to update device objects from device (%d)\n", ret);
+		return ret;
+	}
+
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_CERTIFICATE,
+				     &certificate, &certificate_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device certificate from the host (%d)\n", ret);
+		return ret;
+	}
+
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_VCA, &vca, &vca_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device VCA from the host (%d)\n", ret);
+		goto free_certificate;
+	}
+
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_INTERFACE_REPORT,
+				     &interface_report, &interface_report_size);
+	if (ret) {
+		pci_err(pdev, "failed to get interface report from the host (%d)\n", ret);
+		goto free_vca;
+	}
+
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_MEASUREMENT,
+				     &measurements, &measurements_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device certificate from the host (%d)\n", ret);
+		goto free_interface_report;
+	}
+
+	dev_info = kmalloc(sizeof(*dev_info), GFP_KERNEL);
+	if (!dev_info) {
+		ret = -ENOMEM;
+		goto free_measurements;
+	}
+
+	if (rsi_vdev_get_info(vdev_id, virt_to_phys(dev_info))) {
+		pci_err(pdev, "failed to get device digests (%d)\n", ret);
+		ret = -EIO;
+		goto free_dev_info;
+	}
+
+	/* Make sure no unexpected lock/unlock operation happened from guest */
+	if (dsc->dev_info.lock_nonce != dev_info->lock_nonce) {
+		pci_err(pdev, "Unexpected lock/unlock operation from host (%d)\n", ret);
+		ret = -EIO;
+		goto free_dev_info;
+	}
+
+	/*
+	 * Verify that the digests of the provided reports match with the
+	 * digests from RMM
+	 */
+	ret = cca_verify_digests(dev_info->hash_algo, certificate,
+				 certificate_size, vca, vca_size,
+				 interface_report, interface_report_size,
+				 measurements, measurements_size, dev_info);
+	if (ret) {
+		pci_err(pdev, "RMM provided digest mismatch (%d)\n", ret);
+		goto free_dev_info;
+	}
+
+	/* fill evidence details */
+	evidence = &dsc->pci.base_tsm.evidence;
+
+	/* Now update the evidence under lock. */
+	down_write(&evidence->lock);
+	evidence->generation = dev_info->meas_nonce;
+
+	/* we default to slot 0 in pdev_create */
+	obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_CERT0];
+	WARN_ON(obj->data);
+	obj->data = certificate;
+	obj->len = certificate_size;
+
+	obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_VCA];
+	WARN_ON(obj->data);
+	obj->data = vca;
+	obj->len = vca_size;
+
+	obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_REPORT];
+	WARN_ON(obj->data);
+	obj->data = interface_report;
+	obj->len = interface_report_size;
+
+	obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_MEASUREMENTS];
+	WARN_ON(obj->data);
+	obj->data = measurements;
+	obj->len = measurements_size;
+
+	dsc->dev_info.meas_nonce    = dev_info->meas_nonce;
+	dsc->dev_info.report_nonce  = dev_info->report_nonce;
+	memcpy(dsc->dev_info.cert_digest, dev_info->cert_digest, SHA512_DIGEST_SIZE);
+	memcpy(dsc->dev_info.vca_digest, dev_info->vca_digest, SHA512_DIGEST_SIZE);
+	memcpy(dsc->dev_info.meas_digest, dev_info->meas_digest, SHA512_DIGEST_SIZE);
+	memcpy(dsc->dev_info.report_digest, dev_info->report_digest, SHA512_DIGEST_SIZE);
+	up_write(&evidence->lock);
+
+	kfree(dev_info);
+	return 0;
+
+free_dev_info:
+	kfree(dev_info);
+free_measurements:
+	kvfree(measurements);
+free_interface_report:
+	kvfree(interface_report);
+free_vca:
+	kvfree(vca);
+free_certificate:
+	kvfree(certificate);
+	return ret;
+}
+
 static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pdev)
 {
 	int ret;
+	enum hash_algo digest_algo;
+	struct cca_guest_dsc *cca_dsc;
+	int vdev_id = rsi_vdev_id(pdev);
+	struct rsi_vdevice_info *dev_info;
 
-	struct cca_guest_dsc *cca_dsc __free(kfree) =
-		kzalloc_obj(struct cca_guest_dsc);
+	cca_dsc = kzalloc_obj(struct cca_guest_dsc);
 	if (!cca_dsc)
 		return ERR_PTR(-ENOMEM);
 
 	ret = pci_tsm_devsec_constructor(pdev, &cca_dsc->pci, tsm_dev);
 	if (ret)
-		return ERR_PTR(ret);
+		goto free_cca_dsc;
 
 	ret = cca_device_lock(pdev);
 	if (ret)
-		return ERR_PTR(ret);
+		goto free_cca_dsc;
 
-	/* collect evidence without nonce */
-	ret = cca_update_device_object_cache(pdev, NULL);
-	if (ret) {
-		cca_device_unlock(pdev);
-		return ERR_PTR(ret);
+	dev_info = kmalloc_obj(struct rsi_vdevice_info);
+	if (!dev_info) {
+		ret = -ENOMEM;
+		goto dev_unlock;
+	}
+
+	if (rsi_vdev_get_info(vdev_id, virt_to_phys(dev_info))) {
+		ret = -EIO;
+		goto free_dev_info;
+	}
+
+	/* collect the lock nonce */
+	cca_dsc->dev_info.lock_nonce = dev_info->lock_nonce;
+
+	switch (dev_info->hash_algo) {
+	case RSI_HASH_SHA_256:
+		digest_algo = HASH_ALGO_SHA256;
+		break;
+	case RSI_HASH_SHA_512:
+		digest_algo = HASH_ALGO_SHA512;
+		break;
+	default:
+		ret = -EIO;
+		goto free_dev_info;
 	}
+	pci_tsm_init_evidence(&cca_dsc->pci.base_tsm.evidence,
+			      dev_info->cert_id, digest_algo);
 
-	return &no_free_ptr(cca_dsc)->pci.base_tsm;
+	/* collect evidence without nonce */
+	ret = cca_collect_dev_evidence(pdev, cca_dsc);
+	if (ret)
+		goto free_dev_info;
+
+	kfree(dev_info);
+	return &cca_dsc->pci.base_tsm;
+
+free_dev_info:
+	kfree(dev_info);
+dev_unlock:
+	cca_device_unlock(pdev);
+free_cca_dsc:
+	kfree(cca_dsc);
+	return ERR_PTR(ret);
 }
 
 static void cca_tsm_unlock(struct pci_tsm *tsm)
 {
-	struct cca_guest_dsc *cca_dsc = to_cca_guest_dsc(tsm->pdev);
+	long ret;
+	struct pci_dev *pdev = tsm->pdev;
+	struct cca_guest_dsc *cca_dsc = to_cca_guest_dsc(pdev);
+
+	/* invalidate dev mapping based on interface report */
+	ret = cca_unmap_evidence_report_range(tsm->pdev);
+	if (ret) {
+		pci_err(tsm->pdev, "failed to invalidate the interface report\n");
+		goto err_out;
+	}
 
 	cca_device_unlock(tsm->pdev);
+	pci_tsm_mmio_teardown(cca_dsc->pci.mmio);
 
+err_out:
+	/*
+	 * No error handling from this function. Leave the device locked
+	 */
+	pci_tsm_mmio_free(tsm->pdev, cca_dsc->pci.mmio);
 	kfree(cca_dsc);
 }
 
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 9f9e54174813..6f40329ac2f9 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -6,6 +6,7 @@
 #include <linux/pci.h>
 #include <linux/mem_encrypt.h>
 #include <asm/rsi_cmds.h>
+#include <crypto/hash.h>
 
 #include "rsi-da.h"
 #include "rhi-da.h"
@@ -85,3 +86,147 @@ int cca_update_device_object_cache(struct pci_dev *pdev, const u8 *nonce)
 
 	return rhi_update_vdev_measurements_cache(pdev, nonce);
 }
+
+static inline int
+rsi_validate_dev_mapping(unsigned long vdev_id, phys_addr_t start_ipa,
+			 phys_addr_t end_ipa, phys_addr_t io_pa,
+			 unsigned long flags, unsigned long lock_nonce,
+			 unsigned long meas_nonce, unsigned long report_nonce)
+{
+	unsigned long ret;
+	phys_addr_t next_ipa;
+
+	while (start_ipa < end_ipa) {
+		ret = rsi_vdev_validate_mapping(vdev_id, start_ipa, end_ipa,
+						io_pa, &next_ipa, flags,
+						lock_nonce, meas_nonce, report_nonce);
+		if (ret || next_ipa <= start_ipa || next_ipa > end_ipa)
+			return -EINVAL;
+		io_pa += next_ipa - start_ipa;
+		start_ipa = next_ipa;
+	}
+	return 0;
+}
+
+static inline int rsi_invalidate_dev_mapping(phys_addr_t start_ipa, phys_addr_t end_ipa)
+{
+	return rsi_set_memory_range(start_ipa, end_ipa, RSI_RIPAS_EMPTY,
+				    RSI_CHANGE_DESTROYED);
+}
+
+static int cca_apply_evidence_report_range(struct pci_dev *pdev,
+					   struct pci_tsm_mmio *mmio, bool map)
+{
+	int i, ret;
+	struct resource *res;
+	unsigned long mmio_flags = 0; /* non coherent, not limited order */
+	int vdev_id = rsi_vdev_id(pdev);
+	struct pci_tsm_mmio_entry *entry;
+	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+
+	for (i = 0; i < mmio->nr; i++) {
+		entry = pci_tsm_mmio_entry(mmio, i);
+		res = &entry->res;
+
+		if (res->desc != IORES_DESC_ENCRYPTED)
+			continue;
+
+		if (map)
+			ret = rsi_validate_dev_mapping(vdev_id, res->start,
+						       res->end + 1, entry->tsm_offset,
+						       mmio_flags,
+						       dsc->dev_info.lock_nonce,
+						       dsc->dev_info.meas_nonce,
+						       dsc->dev_info.report_nonce);
+		else
+			ret = rsi_invalidate_dev_mapping(res->start, res->end + 1);
+		if (ret)
+			return ret;
+	}
+	return 0;
+}
+
+int cca_map_evidence_report_range(struct pci_dev *pdev, struct pci_tsm_mmio *mmio)
+{
+	return cca_apply_evidence_report_range(pdev, mmio, true);
+}
+
+int cca_unmap_evidence_report_range(struct pci_dev *pdev)
+{
+	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+	struct pci_tsm_mmio *tsm_mmio = dsc->pci.mmio;
+
+	return cca_apply_evidence_report_range(pdev, tsm_mmio, false);
+}
+
+int cca_verify_digest(u64 hash_algo, uint8_t *report,
+		      size_t report_size, uint8_t *report_digest)
+{
+	u8 digest[SHA512_DIGEST_SIZE];
+	size_t digest_size;
+	void (*digest_func)(const u8 *data, size_t len, u8 *out);
+
+	switch (hash_algo) {
+	case RSI_HASH_SHA_256:
+		digest_func = sha256;
+		digest_size = SHA256_DIGEST_SIZE;
+		break;
+	case RSI_HASH_SHA_512:
+		digest_func = sha512;
+		digest_size = SHA512_DIGEST_SIZE;
+		break;
+	default:
+		return -EINVAL;
+	}
+
+	digest_func(report, report_size, digest);
+	if (memcmp(report_digest, digest, digest_size))
+		return -EINVAL;
+
+	return 0;
+}
+
+int cca_verify_digests(u64 hash_algo,
+		       uint8_t *certificate, size_t certificate_size,
+		       uint8_t *vca, size_t vca_size,
+		       uint8_t *interface_report, size_t interface_report_size,
+		       uint8_t *measurements, size_t measurements_size,
+		       struct rsi_vdevice_info *dev_info)
+{
+	int ret;
+	struct {
+		uint8_t *report;
+		size_t size;
+		uint8_t *digest;
+	} reports[] = {
+		{
+			certificate,
+			certificate_size,
+			dev_info->cert_digest
+		},
+		{
+			vca,
+			vca_size,
+			dev_info->vca_digest
+		},
+		{
+			interface_report,
+			interface_report_size,
+			dev_info->report_digest
+		},
+		{
+			measurements,
+			measurements_size,
+			dev_info->meas_digest
+		}
+
+	};
+
+	for (int i = 0; i < ARRAY_SIZE(reports); i++) {
+		ret = cca_verify_digest(hash_algo, reports[i].report,
+					reports[i].size, reports[i].digest);
+		if (ret)
+			return ret;
+	}
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index f28dc44b5cd2..4903a770412e 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -9,11 +9,23 @@
 #include <linux/pci.h>
 #include <linux/pci-tsm.h>
 #include <asm/rsi_smc.h>
+#include <crypto/sha2.h>
 
 #define MAX_CACHE_OBJ_SIZE	SZ_16M
 
+struct dsm_device_info {
+	u64 lock_nonce;
+	u64 meas_nonce;
+	u64 report_nonce;
+	u8 cert_digest[SHA512_DIGEST_SIZE];
+	u8 vca_digest[SHA512_DIGEST_SIZE];
+	u8 meas_digest[SHA512_DIGEST_SIZE];
+	u8 report_digest[SHA512_DIGEST_SIZE];
+};
+
 struct cca_guest_dsc {
 	struct pci_tsm_devsec pci;
+	struct dsm_device_info dev_info;
 };
 
 static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
@@ -39,4 +51,14 @@ int cca_device_unlock(struct pci_dev *pdev);
 int cca_update_device_object_cache(struct pci_dev *pdev, const u8 *nonce);
 struct page *alloc_shared_pages(int nid, gfp_t gfp_mask, unsigned long min_size);
 int free_shared_pages(struct page *page, unsigned long min_size);
+int cca_map_evidence_report_range(struct pci_dev *pdev, struct pci_tsm_mmio *mmio);
+int cca_unmap_evidence_report_range(struct pci_dev *pdev);
+int cca_verify_digest(u64 hash_algo, uint8_t *report,
+		      size_t report_size, uint8_t *report_digest);
+int cca_verify_digests(u64 hash_algo,
+		       uint8_t *certificate, size_t certificate_size,
+		       uint8_t *vca, size_t vca_size,
+		       uint8_t *interface_report, size_t interface_report_size,
+		       uint8_t *measurements, size_t measurements_size,
+		       struct rsi_vdevice_info *dev_info);
 #endif

---

## [10] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 09/11] coco: guest: arm64: Hook TSM accept to Realm TDISP RUN transition*

Add an accept callback in pci_tsm_ops and implement cca_device_accept() to:
- verify evidence generation (lock_nonce)
- allocate and register protected MMIO ranges
- transition TDI state to RUN

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 20 +++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 43 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  1 +
 3 files changed, 64 insertions(+)

diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 80ee20c8a7a6..84152f505b10 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -499,9 +499,29 @@ static void cca_tsm_unlock(struct pci_tsm *tsm)
 	kfree(cca_dsc);
 }
 
+static int __cca_tsm_accept(struct pci_dev *pdev, unsigned long lock_nonce)
+{
+	int ret;
+
+	ret = cca_device_accept(pdev, lock_nonce);
+	if (ret) {
+		pci_err(pdev, "failed to transition the device to run state (%d)\n", ret);
+		return ret;
+	}
+	return 0;
+}
+
+static int cca_tsm_accept(struct pci_dev *pdev)
+{
+	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+
+	return __cca_tsm_accept(pdev, dsc->dev_info.lock_nonce);
+}
+
 static struct pci_tsm_ops cca_devsec_pci_ops = {
 	.lock = cca_tsm_lock,
 	.unlock = cca_tsm_unlock,
+	.accept	 = cca_tsm_accept,
 };
 
 static void cca_devsec_tsm_remove(void *tsm_dev)
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 6f40329ac2f9..4030fa213ff4 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -230,3 +230,46 @@ int cca_verify_digests(u64 hash_algo,
 	}
 	return 0;
 }
+
+int cca_device_accept(struct pci_dev *pdev, unsigned long lock_nonce)
+{
+	int ret;
+	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+
+	if (lock_nonce != dsc->dev_info.lock_nonce) {
+		pci_err(pdev, "Device evidence generation mismatch\n");
+		return -EIO;
+	}
+
+	/* Allocation private mmio range based on interface report. */
+	struct pci_tsm_mmio *tsm_mmio __free(kfree) = pci_tsm_mmio_alloc(pdev);
+	if (!tsm_mmio) {
+		pci_err(pdev, "Protected mmio range allocation failure\n");
+		return -ENOMEM;
+	}
+
+	/*
+	 * Present the private mmio range in the resource hierarchy.
+	 * We don't use this for ioremap, ioremap check the RIPAS value.
+	 */
+	ret = pci_tsm_mmio_setup(pdev, tsm_mmio);
+	if (ret) {
+		pci_err(pdev, "Protected mmio setup failure\n");
+		return ret;
+	}
+
+	ret = cca_map_evidence_report_range(pdev, tsm_mmio);
+	if (ret) {
+		pci_err(pdev, "failed to validate the interface report\n");
+		return ret;
+	}
+
+	ret = rhi_vdev_set_tdi_state(pdev, RHI_DA_TDI_CONFIG_RUN);
+	if (ret) {
+		pci_err(pdev, "failed to switch the device (%u) to RUN state\n", ret);
+		return ret;
+	}
+
+	dsc->pci.mmio = no_free_ptr(tsm_mmio);
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 4903a770412e..c550926145a0 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -61,4 +61,5 @@ int cca_verify_digests(u64 hash_algo,
 		       uint8_t *interface_report, size_t interface_report_size,
 		       uint8_t *measurements, size_t measurements_size,
 		       struct rsi_vdevice_info *dev_info);
+int cca_device_accept(struct pci_dev *pdev, unsigned long lock_nonce);
 #endif

---

## [11] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 10/11] coco: arm64: dma: Update force_dma_unencrypted for accepted devices*

This change updates the DMA behavior for accepted devices by assuming
they access only private memory. Currently, the DMA API does not provide
a mechanism for allocating shared memory that can be accessed by both
the secure realm and the non-secure host. Accepted devices are therefore
expected to operate entirely within the private memory space.

If future use cases require accepted devices to interact with shared
memory— for example, for host-device communication, we will need to
extend the DMA interface to support such allocation semantics. This
commit lays the groundwork for that by clearly defining the current
assumption and isolating the enforcement to force_dma_unencrypted.

Treat swiotlb and decrypted DMA pools as shared-memory paths and avoid them
for accepted devices by:
- returning false from is_swiotlb_for_alloc() for accepted devices
- returning false from is_swiotlb_active() for accepted devices
- bypassing dma-direct atomic pool usage for accepted devices

This is based on the current assumption that accepted devices operate on private
Realm memory only, and prevents accidental fallback to shared/decrypted DMA
backends.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  6 +-----
 arch/arm64/mm/mem_encrypt.c          | 10 ++++++++++
 include/linux/swiotlb.h              |  3 +++
 kernel/dma/direct.c                  |  8 ++++++++
 kernel/dma/swiotlb.c                 |  3 +++
 5 files changed, 25 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index 5541911eb028..ae0b0cac0900 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -15,17 +15,13 @@ int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops);
 
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
+bool force_dma_unencrypted(struct device *dev);
 
 #define mem_decrypt_granule_size mem_decrypt_granule_size
 size_t mem_decrypt_granule_size(void);
 
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
index f5d64bc29c20..18dea5d879b8 100644
--- a/arch/arm64/mm/mem_encrypt.c
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -18,6 +18,7 @@
 #include <linux/err.h>
 #include <linux/mm.h>
 #include <linux/mem_encrypt.h>
+#include <linux/device.h>
 
 static const struct arm64_mem_crypt_ops *crypt_ops;
 
@@ -67,3 +68,12 @@ size_t mem_decrypt_granule_size(void)
 	return PAGE_SIZE;
 }
 EXPORT_SYMBOL_GPL(mem_decrypt_granule_size);
+
+bool force_dma_unencrypted(struct device *dev)
+{
+	if (device_cc_accepted(dev))
+		return false;
+
+	return is_realm_world();
+}
+EXPORT_SYMBOL_GPL(force_dma_unencrypted);
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 0efb9b8e5dd0..224dcec6a58f 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -296,6 +296,9 @@ bool swiotlb_free(struct device *dev, struct page *page, size_t size);
 
 static inline bool is_swiotlb_for_alloc(struct device *dev)
 {
+	if (device_cc_accepted(dev))
+		return false;
+
 	return dev->dma_io_tlb_mem->for_alloc;
 }
 #else
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 34eccd047e9b..a7a9984db342 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -158,6 +158,14 @@ static struct page *__dma_direct_alloc_pages(struct device *dev, size_t size,
  */
 static bool dma_direct_use_pool(struct device *dev, gfp_t gfp)
 {
+	/*
+	 * Atomic pools are marked decrypted and are used if we require
+	 * updation of pfn mem encryption attributes or for DMA non-coherent
+	 * device allocation. Both is not true for trusted device.
+	 */
+	if (device_cc_accepted(dev))
+		return false;
+
 	return !gfpflags_allow_blocking(gfp) && !is_swiotlb_for_alloc(dev);
 }
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index 309a8b398a7d..339147d1d42f 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -1634,6 +1634,9 @@ bool is_swiotlb_active(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+	if (device_cc_accepted(dev))
+		return false;
+
 	return mem && mem->nslabs;
 }

---

## [12] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 11/11] coco: guest: arm64: Enable vdev DMA after attestation*

- define SMC_RSI_VDEV_DMA_ENABLE and add wrapper in rsi_cmds.h
- invoke the new helper from the guest accept path once the device
  passes attestation, rolling back to TDI_LOCKED on failure

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h        | 16 ++++++++++++++++
 arch/arm64/include/asm/rsi_smc.h         |  2 ++
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 14 ++++++++++++++
 3 files changed, 32 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index f72d8e0cd422..1e0d1cd8841a 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -226,4 +226,20 @@ static inline unsigned long rsi_vdev_get_info(unsigned long vdev_id,
 	return res.a0;
 }
 
+static inline unsigned long __rsi_vdev_dma_enable(unsigned long vdev_id,
+						  unsigned long flags,
+						  unsigned long non_ats_plane,
+						  unsigned long lock_nonce,
+						  unsigned long meas_nonce,
+						  unsigned long report_nonce)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_VDEV_DMA_ENABLE, vdev_id, flags,
+			     non_ats_plane, lock_nonce,
+			     meas_nonce, report_nonce, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 5f1837282237..d2ea3656ea8f 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -186,6 +186,8 @@ struct realm_config {
  */
 #define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
 
+#define SMC_RSI_VDEV_DMA_ENABLE			SMC_RSI_FID(0x19C)
+
 struct rsi_vdevice_info {
 	union {
 		struct {
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 4030fa213ff4..74594066f46c 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -231,9 +231,17 @@ int cca_verify_digests(u64 hash_algo,
 	return 0;
 }
 
+static inline int rsi_vdev_enable_dma(int vdev_id, struct dsm_device_info *dev_info)
+{
+	/* No ATS support */
+	return __rsi_vdev_dma_enable(vdev_id, 0, 0, dev_info->lock_nonce,
+				     dev_info->meas_nonce, dev_info->report_nonce);
+}
+
 int cca_device_accept(struct pci_dev *pdev, unsigned long lock_nonce)
 {
 	int ret;
+	int vdev_id = rsi_vdev_id(pdev);
 	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
 
 	if (lock_nonce != dsc->dev_info.lock_nonce) {
@@ -270,6 +278,12 @@ int cca_device_accept(struct pci_dev *pdev, unsigned long lock_nonce)
 		return ret;
 	}
 
+	if (rsi_vdev_enable_dma(vdev_id, &dsc->dev_info)) {
+		rhi_vdev_set_tdi_state(pdev, RHI_DA_TDI_CONFIG_LOCKED);
+		pci_err(pdev, "failed to enable DMA from the device\n");
+		return -EIO;
+	}
+
 	dsc->pci.mmio = no_free_ptr(tsm_mmio);
 	return 0;
 }

---
