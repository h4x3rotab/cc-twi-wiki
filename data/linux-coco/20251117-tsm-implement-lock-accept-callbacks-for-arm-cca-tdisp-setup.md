---
title: 'TSM: Implement ->lock()/->accept() callbacks for ARM CCA TDISP setup'
date: 2025-11-17
last_reply: 2026-01-08
message_count: 30
participants: ['Aneesh Kumar K.V (Arm)', 'Jonathan Cameron', 'Will Deacon']
---

## [1] Aneesh Kumar K.V (Arm) — 2025-11-17

This patch series implements the TSM ->lock(), ->unlock and ->accept() callbacks
required for the TDISP setup with ARM CCA described in the RMM ALP17 specification [1].

The series builds upon the TSM framework patches posted at [2] . A git repository
containing all the related changes is available at [3].

Testing / Usage

echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind

To Transition the device to TDISP LOCK state:
echo tsm0 > /sys/bus/pci/devices/${DEVICE}/tsm/lock

To Transition the device to TDISP RUN state:
echo 1 > /sys/bus/pci/devices/${DEVICE}/tsm/accept

echo ${DEVICE} > /sys/bus/pci/drivers_probe 

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp17.zip
[2] https://lore.kernel.org/all/20251024020418.1366664-1-dan.j.williams@intel.com/
[3] https://git.gitlab.arm.com/linux-arm/linux-cca.git cca/topics/cca-guest-setup-upstream-v2


Aneesh Kumar K.V (Arm) (11):
  coco: guest: arm64: Guest TSM callback and realm device lock support
  coco: guest: arm64: Add Realm Host Interface and guest DA helper
  coco: guest: arm64: Add support for guest initiated TDI bind/unbind
  coco: guest: arm64: Add support for updating interface reports from
    device
  coco: guest: arm64: Add support for updating measurements from device
  coco: guest: arm64: Add support for reading cached objects from host
  coco: guest: arm64: Validate Realm MMIO mappings from TDISP report
  coco: guest: arm64: Add support for fetching and verifying device info
  coco: guest: arm64: Wire Realm TDISP RUN/STOP transitions into guest
    driver
  coco: arm64: dma: Update force_dma_unencrypted for accepted devices
  coco: guest: arm64: Enable vdev DMA after attestation

 arch/arm64/include/asm/mem_encrypt.h      |   6 +-
 arch/arm64/include/asm/rhi.h              |  77 +++++
 arch/arm64/include/asm/rsi.h              |   3 +
 arch/arm64/include/asm/rsi_cmds.h         |  81 +++++
 arch/arm64/include/asm/rsi_smc.h          |  58 ++++
 arch/arm64/kernel/rsi.c                   |  11 +
 arch/arm64/mm/mem_encrypt.c               |  10 +
 drivers/virt/coco/Makefile                |   2 +-
 drivers/virt/coco/arm-cca-guest/Kconfig   |  10 +-
 drivers/virt/coco/arm-cca-guest/Makefile  |   3 +-
 drivers/virt/coco/arm-cca-guest/arm-cca.c |  95 +++++-
 drivers/virt/coco/arm-cca-guest/rhi-da.c  | 330 ++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h  |  18 ++
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 354 ++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  83 +++++
 include/linux/swiotlb.h                   |   5 +
 16 files changed, 1137 insertions(+), 9 deletions(-)
 create mode 100644 arch/arm64/include/asm/rhi.h
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.h
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.h

---

## [2] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 01/11] coco: guest: arm64: Guest TSM callback and realm device lock support*

Register the TSM callback when the DA feature is supported by RSI. The
build order is also adjusted so that the TSM class is created before the
arm-cca-guest driver is initialized.

In addition, add support for the TDISP lock sequence. Writing a TSM
(TEE Security Manager) device name from `/sys/class/tsm` into `tsm/lock`
triggers the realm device lock operation.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi.h              |  3 ++
 arch/arm64/include/asm/rsi_cmds.h         | 17 +++++++
 arch/arm64/include/asm/rsi_smc.h          |  1 +
 arch/arm64/kernel/rsi.c                   | 11 +++++
 drivers/virt/coco/Makefile                |  2 +-
 drivers/virt/coco/arm-cca-guest/Kconfig   |  8 ++-
 drivers/virt/coco/arm-cca-guest/Makefile  |  1 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 60 ++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-guest/rsi-da.h  | 32 ++++++++++++
 9 files changed, 132 insertions(+), 3 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.h

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index 2d2d363aaaee..12ccd1ed3dfa 100644
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
index 2c8763876dfb..6c2db7a24ef3 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -159,4 +159,21 @@ static inline unsigned long rsi_attestation_token_continue(phys_addr_t granule,
 	return res.a0;
 }
 
+/**
+ * rsi_features() - Read feature register
+ * @index: Feature register index
+ * @out: Feature register value is written to this pointer
+ *
+ * Return: RSI return code
+ */
+static inline unsigned long rsi_features(unsigned long index, unsigned long *out)
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
index 1b716d18b80e..2ec0f5dff02e 100644
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
+	return u64_get_bits(rsi_feat_reg0, RSI_FEATURE_REGISTER_0_DA);
+}
+EXPORT_SYMBOL_GPL(rsi_has_da_feature);
+
 bool cc_platform_has(enum cc_attr attr)
 {
 	switch (attr) {
@@ -146,6 +153,10 @@ void __init arm64_rsi_init(void)
 		return;
 	if (WARN_ON(rsi_get_realm_config(&config)))
 		return;
+
+	if (WARN_ON(rsi_features(0, &rsi_feat_reg0)))
+		return;
+
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index cb52021912b3..57556d7c1cec 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -6,6 +6,6 @@ obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
-obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
+obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index a42359a90558..66b2d9202b66 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -1,11 +1,17 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+
 config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
+	depends on PCI_TSM
 	select TSM_REPORTS
 	select AUXILIARY_BUS
+	select TSM
 	help
-	  The driver provides userspace interface to request and
+	  The driver provides userspace interface to request an
 	  attestation report from the Realm Management Monitor(RMM).
+	  If the DA feature is supported, it also register with TSM framework.
 
 	  If you choose 'M' here, this module will be called
 	  arm-cca-guest.
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 75a120e24fda..bc3b2be4019f 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -1,4 +1,5 @@
 # SPDX-License-Identifier: GPL-2.0-only
+#
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
 
 arm-cca-guest-y +=  arm-cca.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index dc96171791db..288fa53ad0af 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -1,6 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /*
- * Copyright (C) 2023 ARM Ltd.
+ * Copyright (C) 2025 ARM Ltd.
  */
 
 #include <linux/auxiliary_bus.h>
@@ -15,6 +15,8 @@
 
 #include <asm/rsi.h>
 
+#include "rsi-da.h"
+
 /**
  * struct arm_cca_token_info - a descriptor for the token buffer.
  * @challenge:		Pointer to the challenge data
@@ -192,6 +194,57 @@ static void unregister_cca_tsm_report(void *data)
 	tsm_report_unregister(&arm_cca_tsm_report_ops);
 }
 
+static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pdev)
+{
+	int ret;
+
+	struct cca_guest_dsc *cca_dsc __free(kfree) =
+		kzalloc(sizeof(*cca_dsc), GFP_KERNEL);
+	if (!cca_dsc)
+		return ERR_PTR(-ENOMEM);
+
+	ret = pci_tsm_devsec_constructor(pdev, &cca_dsc->pci, tsm_dev);
+	if (ret)
+		return ERR_PTR(ret);
+
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
+	int rc;
+
+	tsm_dev = tsm_register(&adev->dev, &cca_devsec_pci_ops);
+	if (IS_ERR(tsm_dev))
+		return PTR_ERR(tsm_dev);
+
+	rc = devm_add_action_or_reset(&adev->dev, cca_devsec_tsm_remove, tsm_dev);
+	if (rc) {
+		cca_devsec_tsm_remove(tsm_dev);
+		return rc;
+	}
+
+	return 0;
+}
+
 static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
 				const struct auxiliary_device_id *id)
 {
@@ -212,6 +265,10 @@ static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
 		return ret;
 	}
 
+	/* Allow tsm report even if tsm_register fails */
+	if (rsi_has_da_feature())
+		cca_devsec_tsm_register(adev);
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
index 000000000000..5ad3b740710e
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -0,0 +1,32 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2025 ARM Ltd.
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
+static inline int rsi_vdev_id(struct pci_dev *pdev)
+{
+	return (pci_domain_nr(pdev->bus) << 16) |
+	       PCI_DEVID(pdev->bus->number, pdev->devfn);
+}
+
+#endif

---

## [3] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 02/11] coco: guest: arm64: Add Realm Host Interface and guest DA helper*

- describe the Realm Host Interface SMC IDs and result codes in a new
  `asm/rhi.h` header
- expose `struct rsi_host_call` plus an `rsi_host_call()` helper so we can
  invoke `SMC_RSI_HOST_CALL` from C code
- build a guest-side `rhi-da` helper that drives the vdev TDI state machine
  via RHI host calls and translates the firmware status codes

This provides the basic RHI plumbing that later DA features rely on.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h              |  50 +++++++
 arch/arm64/include/asm/rsi_cmds.h         |   9 ++
 arch/arm64/include/asm/rsi_smc.h          |   7 +
 drivers/virt/coco/arm-cca-guest/Makefile  |   2 +-
 drivers/virt/coco/arm-cca-guest/arm-cca.c |   3 +-
 drivers/virt/coco/arm-cca-guest/rhi-da.c  | 158 ++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h  |  14 ++
 7 files changed, 241 insertions(+), 2 deletions(-)
 create mode 100644 arch/arm64/include/asm/rhi.h
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/rhi-da.h

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
new file mode 100644
index 000000000000..335930bbf059
--- /dev/null
+++ b/arch/arm64/include/asm/rhi.h
@@ -0,0 +1,50 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2024 ARM Ltd.
+ */
+
+#ifndef __ASM_RHI_H_
+#define __ASM_RHI_H_
+
+#include <linux/types.h>
+
+#define SMC_RHI_CALL(func)				\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
+			   ARM_SMCCC_SMC_64,		\
+			   ARM_SMCCC_OWNER_STANDARD_HYP,\
+			   (func))
+
+#define RHI_DA_SUCCESS				0x0
+#define RHI_DA_INCOMPLETE			0x1
+#define RHI_DA_ERROR_DATA_NOT_AVAILABLE		0x2
+#define RHI_DA_ERROR_INVALID_VDEV_ID		0x3
+#define RHI_DA_ERROR_INVALID_OBJECT		0x4
+#define RHI_DA_ERROR_INPUT			0x5
+#define RHI_DA_ERROR_DEVICE			0x6
+#define RHI_DA_ERROR_INVALID_OFFSET		0x7
+#define RHI_DA_ERROR_ACCESS_FAILED		0x8
+#define RHI_DA_ERROR_BUSY			0x9
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
+#define RHI_DA_TDI_CONFIG_UNLOCKED		0x0
+#define RHI_DA_TDI_CONFIG_LOCKED		0x1
+#define RHI_DA_TDI_CONFIG_RUN			0x2
+#define RHI_DA_VDEV_SET_TDI_STATE	SMC_RHI_CALL(0x0054)
+#define RHI_DA_VDEV_ABORT		SMC_RHI_CALL(0x0056)
+
+#endif
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 6c2db7a24ef3..18aa1b9efb9b 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -176,4 +176,13 @@ static inline unsigned long rsi_features(unsigned long index, unsigned long *out
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
index 8e486cdef9eb..4dbd87a27d9b 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -183,6 +183,13 @@ struct realm_config {
  */
 #define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
 
+struct rsi_host_call {
+	union {
+		u16 imm;
+		u64 padding0;
+	};
+	u64 gprs[31];
+} __aligned(0x100);
 /*
  * Make a Host call.
  *
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index bc3b2be4019f..04d26e398a1d 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -2,4 +2,4 @@
 #
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
 
-arm-cca-guest-y +=  arm-cca.o
+arm-cca-guest-y +=  arm-cca.o rhi-da.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 288fa53ad0af..26be2e8fe182 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -16,6 +16,7 @@
 #include <asm/rsi.h>
 
 #include "rsi-da.h"
+#include "rhi-da.h"
 
 /**
  * struct arm_cca_token_info - a descriptor for the token buffer.
@@ -266,7 +267,7 @@ static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
 	}
 
 	/* Allow tsm report even if tsm_register fails */
-	if (rsi_has_da_feature())
+	if (rsi_has_da_feature() && rhi_has_da_support())
 		cca_devsec_tsm_register(adev);
 
 	return 0;
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
new file mode 100644
index 000000000000..3430d8df4424
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -0,0 +1,158 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
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
+	case RHI_DA_INCOMPLETE:
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
+	if (ret != RSI_SUCCESS || rhicall->gprs[0] == SMCCC_RET_NOT_SUPPORTED)
+		return false;
+
+	/* For base DA to work we need these to be supported */
+	if ((rhicall->gprs[0] & RHI_DA_BASE_FEATURE) == RHI_DA_BASE_FEATURE)
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
+		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_CONTINUE;
+	rhi_call->gprs[1] = vdev_id;
+	rhi_call->gprs[2] = cookie;
+
+	ret = rsi_host_call(virt_to_phys(rhi_call));
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
+	ret = rsi_host_call(virt_to_phys(rhi_call));
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	return *da_error = rhi_call->gprs[0];
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
+				    unsigned long target_state,
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
+	ret = rsi_host_call(virt_to_phys(rhi_call));
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	*cookie = rhi_call->gprs[1];
+	return map_rhi_da_error(rhi_call->gprs[0]);
+}
+
+int rhi_vdev_set_tdi_state(struct pci_dev *pdev, unsigned long target_state)
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
index 000000000000..8dd77c7ed645
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -0,0 +1,14 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2024 ARM Ltd.
+ */
+
+#ifndef _VIRT_COCO_RHI_DA_H_
+#define _VIRT_COCO_RHI_DA_H_
+
+#include <asm/rhi.h>
+
+struct pci_dev;
+bool rhi_has_da_support(void);
+int rhi_vdev_set_tdi_state(struct pci_dev *pdev, unsigned long target_state);
+#endif

---

## [4] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 03/11] coco: guest: arm64: Add support for guest initiated TDI bind/unbind*

Add RHI for VDEV_SET_TDI_STATE

Note: This is not part of RHI spec. This is a POC implementation
and will be later converted to correct interface defined by RHI.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-guest/Makefile  |  2 +-
 drivers/virt/coco/arm-cca-guest/arm-cca.c |  8 ++++-
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 36 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  2 ++
 4 files changed, 46 insertions(+), 2 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-guest/rsi-da.c

diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 04d26e398a1d..146af69d0362 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -2,4 +2,4 @@
 #
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
 
-arm-cca-guest-y +=  arm-cca.o rhi-da.o
+arm-cca-guest-y +=  arm-cca.o rhi-da.o rsi-da.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 26be2e8fe182..f4c9e529c43e 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -208,13 +208,19 @@ static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pde
 	if (ret)
 		return ERR_PTR(ret);
 
-	return ERR_PTR(-EIO);
+	ret = cca_device_lock(pdev);
+	if (ret)
+		return ERR_PTR(-EIO);
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
index 000000000000..6770861629f2
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -0,0 +1,36 @@
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
+#define PCI_TDISP_MESSAGE_VERSION_10	0x10
+
+int cca_device_lock(struct pci_dev *pdev)
+{
+	int ret;
+
+	ret = rhi_vdev_set_tdi_state(pdev, RHI_DA_TDI_CONFIG_LOCKED);
+	if (ret) {
+		pci_err(pdev, "failed to lock the device (%u)\n", ret);
+		return -EIO;
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
+		pci_err(pdev, "failed to unlock the device (%u)\n", ret);
+		return -EIO;
+	}
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 5ad3b740710e..d1f4641a0fa1 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -29,4 +29,6 @@ static inline int rsi_vdev_id(struct pci_dev *pdev)
 	       PCI_DEVID(pdev->bus->number, pdev->devfn);
 }
 
+int cca_device_lock(struct pci_dev *pdev);
+int cca_device_unlock(struct pci_dev *pdev);
 #endif

---

## [5] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 04/11] coco: guest: arm64: Add support for updating interface reports from device*

Support collecting interface reports using RSI calls. The fetched
interface report will be cached in the host.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h              |  1 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c |  6 ++++
 drivers/virt/coco/arm-cca-guest/rhi-da.c  | 44 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h  |  1 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 13 +++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  |  2 ++
 6 files changed, 67 insertions(+)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 335930bbf059..5f140015afc3 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -40,6 +40,7 @@
 #define RHI_DA_FEATURES			SMC_RHI_CALL(0x004B)
 
 #define RHI_DA_VDEV_CONTINUE		SMC_RHI_CALL(0x0051)
+#define RHI_DA_VDEV_GET_INTERFACE_REPORT SMC_RHI_CALL(0x0052)
 
 #define RHI_DA_TDI_CONFIG_UNLOCKED		0x0
 #define RHI_DA_TDI_CONFIG_LOCKED		0x1
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index f4c9e529c43e..7988ff6d4b2e 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -212,6 +212,12 @@ static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pde
 	if (ret)
 		return ERR_PTR(-EIO);
 
+	ret = cca_update_device_object_cache(pdev, cca_dsc);
+	if (ret) {
+		cca_device_unlock(pdev);
+		return ERR_PTR(-EIO);
+	}
+
 	return &no_free_ptr(cca_dsc)->pci.base_tsm;
 }
 
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
index 3430d8df4424..f4fb8577e1b5 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -156,3 +156,47 @@ int rhi_vdev_set_tdi_state(struct pci_dev *pdev, unsigned long target_state)
 
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
+	ret = rsi_host_call(virt_to_phys(rhi_call));
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
index 8dd77c7ed645..d83e61359b35 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -11,4 +11,5 @@
 struct pci_dev;
 bool rhi_has_da_support(void);
 int rhi_vdev_set_tdi_state(struct pci_dev *pdev, unsigned long target_state);
+int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev);
 #endif
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index 6770861629f2..c8ba72e4be3e 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -34,3 +34,16 @@ int cca_device_unlock(struct pci_dev *pdev)
 	}
 	return 0;
 }
+
+int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *dsc)
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
index d1f4641a0fa1..fd4792a50daf 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -31,4 +31,6 @@ static inline int rsi_vdev_id(struct pci_dev *pdev)
 
 int cca_device_lock(struct pci_dev *pdev);
 int cca_device_unlock(struct pci_dev *pdev);
+int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *dsc);
+
 #endif

---

## [6] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 05/11] coco: guest: arm64: Add support for updating measurements from device*

Fetch device measurements using RSI_RDEV_GET_MEASUREMENTS. The fetched
device measurements will be cached in the host.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             | 19 ++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.c | 48 ++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h |  2 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 58 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h |  2 +
 5 files changed, 129 insertions(+)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 5f140015afc3..ce2ed8a440c3 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -42,6 +42,25 @@
 #define RHI_DA_VDEV_CONTINUE		SMC_RHI_CALL(0x0051)
 #define RHI_DA_VDEV_GET_INTERFACE_REPORT SMC_RHI_CALL(0x0052)
 
+#define RHI_VDEV_MEASURE_SIGNED		BIT(0)
+#define RHI_VDEV_MEASURE_RAW		BIT(1)
+#define RHI_VDEV_MEASURE_EXCHANGE	BIT(2)
+struct rhi_vdev_measurement_params {
+	union {
+		u64 flags;
+		u8 padding0[256];
+	};
+	union {
+		u8 indices[32];
+		u8 padding1[256];
+	};
+	union {
+		u8 nonce[32];
+		u8 padding2[256];
+	};
+};
+#define RHI_DA_VDEV_GET_MEASUREMENTS	SMC_RHI_CALL(0x0053)
+
 #define RHI_DA_TDI_CONFIG_UNLOCKED		0x0
 #define RHI_DA_TDI_CONFIG_LOCKED		0x1
 #define RHI_DA_TDI_CONFIG_RUN			0x2
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
index f4fb8577e1b5..aa17bb3ee562 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -200,3 +200,51 @@ int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev)
 
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
+		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhi_call)
+		return -ENOMEM;
+
+	rhi_call->imm = 0;
+	rhi_call->gprs[0] = RHI_DA_VDEV_GET_MEASUREMENTS;
+	rhi_call->gprs[1] = vdev_id;
+	rhi_call->gprs[2] = vdev_meas_phys;
+
+	ret = rsi_host_call(virt_to_phys(rhi_call));
+	if (ret != RSI_SUCCESS)
+		return -EIO;
+
+	*cookie = rhi_call->gprs[1];
+	return map_rhi_da_error(rhi_call->gprs[0]);
+}
+
+int rhi_update_vdev_measurements_cache(struct pci_dev *pdev,
+				       struct rhi_vdev_measurement_params *params)
+{
+	int ret;
+	unsigned long cookie;
+	int vdev_id = rsi_vdev_id(pdev);
+	phys_addr_t vdev_meas_phys = virt_to_phys(params);
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
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.h b/drivers/virt/coco/arm-cca-guest/rhi-da.h
index d83e61359b35..f90e0e715073 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -12,4 +12,6 @@ struct pci_dev;
 bool rhi_has_da_support(void);
 int rhi_vdev_set_tdi_state(struct pci_dev *pdev, unsigned long target_state);
 int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev);
+int rhi_update_vdev_measurements_cache(struct pci_dev *pdev,
+				       struct rhi_vdev_measurement_params *params);
 #endif
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index c8ba72e4be3e..aa6e13e4c0ea 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -4,6 +4,7 @@
  */
 
 #include <linux/pci.h>
+#include <linux/mem_encrypt.h>
 #include <asm/rsi_cmds.h>
 
 #include "rsi-da.h"
@@ -35,9 +36,50 @@ int cca_device_unlock(struct pci_dev *pdev)
 	return 0;
 }
 
+struct page *alloc_shared_pages(int nid, gfp_t gfp_mask, unsigned long min_size)
+{
+	int ret;
+	struct page *page;
+	/* We should normalize the size based on hypervisor page size */
+	int page_order = get_order(min_size);
+
+	/* Always request for zero filled pages */
+	page = alloc_pages_node(nid, gfp_mask | __GFP_ZERO, page_order);
+
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
+int free_shared_pages(struct page *page, unsigned long min_size)
+{
+	int ret;
+	/* We should normalize the size based on hypervisor page size */
+	int page_order = get_order(min_size);
+
+	ret = set_memory_encrypted((unsigned long)page_address(page), 1 << page_order);
+	/* If we fail to mark it encrypted don't free it back */
+	if (!ret)
+		__free_pages(page, page_order);
+	return ret;
+}
+
 int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *dsc)
 {
 	int ret;
+	struct page *shared_pages;
+	struct rhi_vdev_measurement_params *dev_meas;
 
 	ret = rhi_update_vdev_interface_report_cache(pdev);
 	if (ret) {
@@ -45,5 +87,21 @@ int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *d
 		return ret;
 	}
 
+	shared_pages = alloc_shared_pages(NUMA_NO_NODE, GFP_KERNEL, sizeof(struct rhi_vdev_measurement_params));
+	if (!shared_pages)
+		return -ENOMEM;
+
+	dev_meas = (struct rhi_vdev_measurement_params *)page_address(shared_pages);
+	/* request for signed full transcript */
+	dev_meas->flags = RHI_VDEV_MEASURE_SIGNED | RHI_VDEV_MEASURE_EXCHANGE;
+	/* request all measurement block. Set bit 254 */
+	dev_meas->indices[31] = 0x40;
+	ret = rhi_update_vdev_measurements_cache(pdev, dev_meas);
+
+	free_shared_pages(shared_pages, sizeof(struct rhi_vdev_measurement_params));
+	if (ret) {
+		pci_err(pdev, "failed to get device measurement (%d)\n", ret);
+		return ret;
+	}
 	return 0;
 }
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index fd4792a50daf..3b01182924bc 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -32,5 +32,7 @@ static inline int rsi_vdev_id(struct pci_dev *pdev)
 int cca_device_lock(struct pci_dev *pdev);
 int cca_device_unlock(struct pci_dev *pdev);
 int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *dsc);
+struct page *alloc_shared_pages(int nid, gfp_t gfp_mask, unsigned long min_size);
+int free_shared_pages(struct page *page, unsigned long min_size);
 
 #endif

---

## [7] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 06/11] coco: guest: arm64: Add support for reading cached objects from host*

Teach rsi_device_start() to pull the interface report and device
certificate from the host by querying size, sharing a decrypted buffer
for the read, copying the payload to private memory. Also track the
fetched blobs in struct cca_guest_dsc so later stages can hand them to
the attestation flow.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             |  7 +++
 drivers/virt/coco/arm-cca-guest/rhi-da.c | 80 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rhi-da.h |  1 +
 drivers/virt/coco/arm-cca-guest/rsi-da.h |  8 +++
 4 files changed, 96 insertions(+)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index ce2ed8a440c3..738470dfb869 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -39,6 +39,13 @@
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
 #define RHI_DA_VDEV_GET_INTERFACE_REPORT SMC_RHI_CALL(0x0052)
 
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
index aa17bb3ee562..d29aee0fca58 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.c
@@ -248,3 +248,83 @@ int rhi_update_vdev_measurements_cache(struct pci_dev *pdev,
 
 	return ret;
 }
+
+int rhi_read_cached_object(int vdev_id, int da_object_type, void **object, int *object_size)
+{
+	int ret;
+	int max_data_len;
+	struct page *shared_pages;
+	void *data_buf_shared, *data_buf_private;
+	struct rsi_host_call *rhicall;
+
+	rhicall = kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
+	if (!rhicall)
+		return -ENOMEM;
+
+	rhicall->imm = 0;
+	rhicall->gprs[0] = RHI_DA_OBJECT_SIZE;
+	rhicall->gprs[1] = vdev_id;
+	rhicall->gprs[2] = da_object_type;
+
+	ret = rsi_host_call(virt_to_phys(rhicall));
+	if (ret != RSI_SUCCESS) {
+		ret = -EIO;
+		goto err_return;
+	}
+
+	if (rhicall->gprs[0] != RHI_DA_SUCCESS) {
+		ret = -EIO;
+		goto err_return;
+	}
+
+	/* validate against the max cache object size used on host. */
+	max_data_len = rhicall->gprs[1];
+	if (max_data_len > MAX_CACHE_OBJ_SIZE || max_data_len == 0) {
+		ret = -EIO;
+		goto err_return;
+	}
+	*object_size = max_data_len;
+
+	data_buf_private = kmalloc(*object_size, GFP_KERNEL);
+	if (!data_buf_private) {
+		ret = -ENOMEM;
+		goto err_return;
+	}
+
+	shared_pages = alloc_shared_pages(NUMA_NO_NODE, GFP_KERNEL, max_data_len);
+	if (!shared_pages) {
+		ret = -ENOMEM;
+		goto err_shared_alloc;
+	}
+	data_buf_shared = page_address(shared_pages);
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
+		ret = -EIO;
+		goto err_rhi_call;
+	}
+
+	memcpy(data_buf_private, data_buf_shared, *object_size);
+	free_shared_pages(shared_pages, max_data_len);
+
+	*object = data_buf_private;
+	kfree(rhicall);
+	return 0;
+
+err_rhi_call:
+	free_shared_pages(shared_pages, max_data_len);
+err_shared_alloc:
+	kfree(data_buf_private);
+err_return:
+	*object = NULL;
+	*object_size = 0;
+	kfree(rhicall);
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.h b/drivers/virt/coco/arm-cca-guest/rhi-da.h
index f90e0e715073..303d19a80cd0 100644
--- a/drivers/virt/coco/arm-cca-guest/rhi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rhi-da.h
@@ -14,4 +14,5 @@ int rhi_vdev_set_tdi_state(struct pci_dev *pdev, unsigned long target_state);
 int rhi_update_vdev_interface_report_cache(struct pci_dev *pdev);
 int rhi_update_vdev_measurements_cache(struct pci_dev *pdev,
 				       struct rhi_vdev_measurement_params *params);
+int rhi_read_cached_object(int vdev_id, int da_object_type, void **object, int *object_size);
 #endif
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 3b01182924bc..fa9cc01095da 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -10,8 +10,16 @@
 #include <linux/pci-tsm.h>
 #include <asm/rsi_smc.h>
 
+#define MAX_CACHE_OBJ_SIZE	SZ_16M
+
 struct cca_guest_dsc {
 	struct pci_tsm_devsec pci;
+	void *interface_report;
+	int interface_report_size;
+	void *certificate;
+	int certificate_size;
+	void *measurements;
+	int measurements_size;
 };
 
 static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)

---

## [8] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 07/11] coco: guest: arm64: Validate Realm MMIO mappings from TDISP report*

Parse the TDISP device interface report and drive the RSI
RDEV_VALIDATE_MAPPING handshake for each Realm MMIO window. The new
helper walks the reported ranges, rejects malformed entries, and either
validates the IPA->PA mapping when the device transitions to RUN or tears
it down with RIPAS updates on unlock.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h         | 29 ++++++++
 arch/arm64/include/asm/rsi_smc.h          |  4 +
 drivers/virt/coco/arm-cca-guest/arm-cca.c |  9 +++
 drivers/virt/coco/arm-cca-guest/rsi-da.c  | 91 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.h  | 24 +++++-
 5 files changed, 156 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 18aa1b9efb9b..fe36dd2b96ac 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -185,4 +185,33 @@ static inline unsigned long rsi_host_call(phys_addr_t addr)
 	return res.a0;
 }
 
+static inline long
+rsi_vdev_validate_mapping(unsigned long vdev_id,
+			  phys_addr_t ipa_base, phys_addr_t ipa_top,
+			  phys_addr_t pa_base, phys_addr_t *next_ipa,
+			  unsigned long flags, unsigned long lock_nonce,
+			  unsigned long meas_nonce, unsigned report_nonce)
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
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 4dbd87a27d9b..26aaa97469e8 100644
--- a/arch/arm64/include/asm/rsi_smc.h
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -183,6 +183,10 @@ struct realm_config {
  */
 #define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
 
+#define RSI_DEV_MEM_COHERENT		BIT(0)
+#define RSI_DEV_MEM_LIMITED_ORDER	BIT(1)
+#define SMC_RSI_VDEV_VALIDATE_MAPPING		SMC_RSI_FID(0x19F)
+
 struct rsi_host_call {
 	union {
 		u16 imm;
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index 7988ff6d4b2e..e86c3ad355f8 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -223,10 +223,19 @@ static struct pci_tsm *cca_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pde
 
 static void cca_tsm_unlock(struct pci_tsm *tsm)
 {
+	long ret;
 	struct cca_guest_dsc *cca_dsc = to_cca_guest_dsc(tsm->pdev);
 
+	/* invalidate dev mapping based on interface report */
+	ret = cca_apply_interface_report_mappings(tsm->pdev, false);
+	if (ret) {
+		pci_err(tsm->pdev, "failed to invalidate the interface report\n");
+		goto err_out;
+	}
+
 	cca_device_unlock(tsm->pdev);
 
+err_out:
 	kfree(cca_dsc);
 }
 
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index aa6e13e4c0ea..c70fb7dd4838 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -105,3 +105,94 @@ int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *d
 	}
 	return 0;
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
+int cca_apply_interface_report_mappings(struct pci_dev *pdev, bool validate)
+{
+	int ret;
+	struct resource *r;
+	unsigned int range_id;
+	phys_addr_t mmio_start_phys;
+	struct pci_tdisp_mmio_range *mmio_range;
+	phys_addr_t ipa_start, ipa_end, bar_offset;
+	struct pci_tdisp_device_interface_report *interface_report;
+	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+
+	interface_report = (struct pci_tdisp_device_interface_report *)dsc->interface_report;
+	mmio_range = (struct pci_tdisp_mmio_range *)(interface_report + 1);
+
+
+	for (int i = 0; i < interface_report->mmio_range_count; i++, mmio_range++) {
+
+		range_id = FIELD_GET(TSM_INTF_REPORT_MMIO_RANGE_ID, mmio_range->range_attributes);
+
+		if (range_id >= PCI_NUM_RESOURCES) {
+			pci_warn(pdev, "Skipping broken range [%d] #%d %d\n",
+				 i, range_id, mmio_range->num_pages);
+			continue;
+		}
+
+		r = pci_resource_n(pdev, range_id);
+
+		if (r->end == r->start ||
+		    resource_size(r) & ~PAGE_MASK || !mmio_range->num_pages) {
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
+		/* units in 4K size*/
+		mmio_start_phys = mmio_range->first_page << 12;
+		bar_offset = mmio_start_phys & (pci_resource_len(pdev, range_id) - 1);
+		ipa_start = r->start + bar_offset;
+		ipa_end = ipa_start + (mmio_range->num_pages << 12);
+
+		if (!validate)
+			ret = rsi_invalidate_dev_mapping(ipa_start, ipa_end);
+		if (ret)
+			return ret;
+	}
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index fa9cc01095da..32cf90beb55e 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -12,6 +12,28 @@
 
 #define MAX_CACHE_OBJ_SIZE	SZ_16M
 
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
 	struct pci_tsm_devsec pci;
 	void *interface_report;
@@ -42,5 +64,5 @@ int cca_device_unlock(struct pci_dev *pdev);
 int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *dsc);
 struct page *alloc_shared_pages(int nid, gfp_t gfp_mask, unsigned long min_size);
 int free_shared_pages(struct page *page, unsigned long min_size);
-
+int cca_apply_interface_report_mappings(struct pci_dev *pdev, bool validate);
 #endif

---

## [9] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 08/11] coco: guest: arm64: Add support for fetching and verifying device info*

RSI_RDEV_GET_INFO returns different digest hash values, which can be
compared with host cached values to ensure the host didn't tamper with
the cached data.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h        |  11 ++
 arch/arm64/include/asm/rsi_smc.h         |  44 +++++++
 drivers/virt/coco/arm-cca-guest/Kconfig  |   2 +
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 139 ++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-guest/rsi-da.h |  15 +++
 5 files changed, 210 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index fe36dd2b96ac..e6d68760a729 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -214,4 +214,15 @@ rsi_vdev_validate_mapping(unsigned long vdev_id,
 	return res.a0;
 }
 
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
index 26aaa97469e8..49334d07dd55 100644
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
@@ -183,6 +186,47 @@ struct realm_config {
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
 #define RSI_DEV_MEM_COHERENT		BIT(0)
 #define RSI_DEV_MEM_LIMITED_ORDER	BIT(1)
 #define SMC_RSI_VDEV_VALIDATE_MAPPING		SMC_RSI_FID(0x19F)
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index 66b2d9202b66..7407b5a464e3 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -5,6 +5,8 @@ config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
 	depends on PCI_TSM
+	select CRYPTO_LIB_SHA256
+	select CRYPTO_LIB_SHA512
 	select TSM_REPORTS
 	select AUXILIARY_BUS
 	select TSM
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index c70fb7dd4838..c6b92f4ae9c5 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -6,6 +6,7 @@
 #include <linux/pci.h>
 #include <linux/mem_encrypt.h>
 #include <asm/rsi_cmds.h>
+#include <crypto/hash.h>
 
 #include "rsi-da.h"
 #include "rhi-da.h"
@@ -139,10 +140,12 @@ int cca_apply_interface_report_mappings(struct pci_dev *pdev, bool validate)
 	struct resource *r;
 	unsigned int range_id;
 	phys_addr_t mmio_start_phys;
+	unsigned long mmio_flags = 0; /* non coherent, not limited order */
 	struct pci_tdisp_mmio_range *mmio_range;
 	phys_addr_t ipa_start, ipa_end, bar_offset;
 	struct pci_tdisp_device_interface_report *interface_report;
 	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+	int vdev_id = rsi_vdev_id(pdev);
 
 	interface_report = (struct pci_tdisp_device_interface_report *)dsc->interface_report;
 	mmio_range = (struct pci_tdisp_mmio_range *)(interface_report + 1);
@@ -189,10 +192,144 @@ int cca_apply_interface_report_mappings(struct pci_dev *pdev, bool validate)
 		ipa_start = r->start + bar_offset;
 		ipa_end = ipa_start + (mmio_range->num_pages << 12);
 
-		if (!validate)
+		if (validate)
+			ret = rsi_validate_dev_mapping(vdev_id, ipa_start,
+						       ipa_end, mmio_start_phys,
+						       mmio_flags,
+						       dsc->dev_info.lock_nonce,
+						       dsc->dev_info.meas_nonce,
+						       dsc->dev_info.report_nonce);
+		else
 			ret = rsi_invalidate_dev_mapping(ipa_start, ipa_end);
 		if (ret)
 			return ret;
 	}
 	return 0;
 }
+
+static int verify_digests(struct cca_guest_dsc *dsc)
+{
+	u8 digest[SHA512_DIGEST_SIZE];
+	size_t digest_size;
+	void (*digest_func)(const u8 *data, size_t len, u8 *out);
+
+	struct pci_dev *pdev = dsc->pci.base_tsm.pdev;
+	struct {
+		uint8_t *report;
+		size_t size;
+		uint8_t *digest;
+	} reports[] = {
+		{
+			dsc->interface_report,
+			dsc->interface_report_size,
+			dsc->dev_info.report_digest
+		},
+		{
+			dsc->certificate,
+			dsc->certificate_size,
+			dsc->dev_info.cert_digest
+		},
+		{
+			dsc->measurements,
+			dsc->measurements_size,
+			dsc->dev_info.meas_digest
+		}
+	};
+
+	switch (dsc->dev_info.hash_algo) {
+	case RSI_HASH_SHA_256:
+		digest_func = sha256;
+		digest_size = SHA256_DIGEST_SIZE;
+		break;
+
+	case RSI_HASH_SHA_512:
+		digest_func = sha512;
+		digest_size = SHA512_DIGEST_SIZE;
+		break;
+	default:
+		pci_err(pdev, "Unknown realm hash algorithm!\n");
+		return -EINVAL;
+	}
+
+	for (int i = 0; i < ARRAY_SIZE(reports); i++) {
+
+		digest_func(reports[i].report, reports[i].size, digest);
+		if (memcmp(reports[i].digest, digest, digest_size)) {
+			pci_err(pdev, "Invalid digest\n");
+			return -EINVAL;
+		}
+	}
+
+	pci_dbg(pdev, "Successfully verified the digests\n");
+	return 0;
+}
+
+int cca_device_verify_and_accept(struct pci_dev *pdev)
+{
+	int ret;
+	int vdev_id = rsi_vdev_id(pdev);
+	struct rsi_vdevice_info *dev_info;
+	struct cca_guest_dsc *dsc = to_cca_guest_dsc(pdev);
+
+	/* Now make a host call to copy the interface report to guest. */
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_INTERFACE_REPORT,
+				     &dsc->interface_report, &dsc->interface_report_size);
+	if (ret) {
+		pci_err(pdev, "failed to get interface report from the host (%d)\n", ret);
+		return ret;
+	}
+
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_CERTIFICATE,
+				     &dsc->certificate, &dsc->certificate_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device certificate from the host (%d)\n", ret);
+		return ret;
+	}
+
+	ret = rhi_read_cached_object(vdev_id, RHI_DA_OBJECT_MEASUREMENT,
+				     &dsc->measurements, &dsc->measurements_size);
+	if (ret) {
+		pci_err(pdev, "failed to get device certificate from the host (%d)\n", ret);
+		return ret;
+	}
+
+	/* RMM expects sizeof(*dev_info) = 512 bytes aligned address */
+	BUILD_BUG_ON(sizeof(*dev_info) != 512);
+	dev_info = kmalloc(sizeof(*dev_info), GFP_KERNEL);
+	if (!dev_info)
+		return -ENOMEM;
+
+	if (rsi_vdev_get_info(vdev_id, virt_to_phys(dev_info))) {
+		pci_err(pdev, "failed to get device digests (%d)\n", ret);
+		kfree(dev_info);
+		return -EIO;
+	}
+
+	dsc->dev_info.cert_id       = dev_info->cert_id;
+	dsc->dev_info.hash_algo     = dev_info->hash_algo;
+	dsc->dev_info.lock_nonce    = dev_info->lock_nonce;
+	dsc->dev_info.meas_nonce    = dev_info->meas_nonce;
+	dsc->dev_info.report_nonce  = dev_info->report_nonce;
+	memcpy(dsc->dev_info.cert_digest, dev_info->cert_digest, SHA512_DIGEST_SIZE);
+	memcpy(dsc->dev_info.meas_digest, dev_info->meas_digest, SHA512_DIGEST_SIZE);
+	memcpy(dsc->dev_info.report_digest, dev_info->report_digest, SHA512_DIGEST_SIZE);
+
+	kfree(dev_info);
+	/*
+	 * Verify that the digests of the provided reports match with the
+	 * digests from RMM
+	 */
+	ret = verify_digests(dsc);
+	if (ret) {
+		pci_err(pdev, "device digest validation failed (%d)\n", ret);
+		return ret;
+	}
+
+	ret = cca_apply_interface_report_mappings(pdev, true);
+	if (ret) {
+		pci_err(pdev, "failed to validate the interface report\n");
+		return -EIO;
+	}
+
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
index 32cf90beb55e..73d3d095ade6 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.h
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.h
@@ -9,6 +9,7 @@
 #include <linux/pci.h>
 #include <linux/pci-tsm.h>
 #include <asm/rsi_smc.h>
+#include <crypto/sha2.h>
 
 #define MAX_CACHE_OBJ_SIZE	SZ_16M
 
@@ -34,6 +35,18 @@ struct pci_tdisp_mmio_range {
 #define TSM_INTF_REPORT_MMIO_RESERVED		GENMASK(15, 4)
 #define TSM_INTF_REPORT_MMIO_RANGE_ID		GENMASK(31, 16)
 
+struct dsm_device_info {
+	u64 flags;
+	u64 cert_id;
+	u64 hash_algo;
+	u64 lock_nonce;
+	u64 meas_nonce;
+	u64 report_nonce;
+	u8 cert_digest[SHA512_DIGEST_SIZE];
+	u8 meas_digest[SHA512_DIGEST_SIZE];
+	u8 report_digest[SHA512_DIGEST_SIZE];
+};
+
 struct cca_guest_dsc {
 	struct pci_tsm_devsec pci;
 	void *interface_report;
@@ -42,6 +55,7 @@ struct cca_guest_dsc {
 	int certificate_size;
 	void *measurements;
 	int measurements_size;
+	struct dsm_device_info dev_info;
 };
 
 static inline struct cca_guest_dsc *to_cca_guest_dsc(struct pci_dev *pdev)
@@ -65,4 +79,5 @@ int cca_update_device_object_cache(struct pci_dev *pdev, struct cca_guest_dsc *d
 struct page *alloc_shared_pages(int nid, gfp_t gfp_mask, unsigned long min_size);
 int free_shared_pages(struct page *page, unsigned long min_size);
 int cca_apply_interface_report_mappings(struct pci_dev *pdev, bool validate);
+int cca_device_verify_and_accept(struct pci_dev *pdev);
 #endif

---

## [10] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 09/11] coco: guest: arm64: Wire Realm TDISP RUN/STOP transitions into guest driver*

Teach the Arm CCA guest driver how to transition a Realm device between
RUN and STOP states. The new helpers issue the RSI START/STOP calls,
poll with CONTINUE until completion, and surface errors back to the TSM.
The PCI TSM accept/unlock paths now invoke these helpers so writing `1`
to `tsm/accept` correctly kicks off the TDISP RUN sequence and unlock
tears it back down.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-guest/arm-cca.c | 13 +++++++++++++
 drivers/virt/coco/arm-cca-guest/rsi-da.c  |  5 +++++
 2 files changed, 18 insertions(+)

diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
index e86c3ad355f8..46cc0fdefe34 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -239,9 +239,22 @@ static void cca_tsm_unlock(struct pci_tsm *tsm)
 	kfree(cca_dsc);
 }
 
+static int cca_tsm_accept(struct pci_dev *pdev)
+{
+	int ret;
+
+	ret = cca_device_verify_and_accept(pdev);
+	if (ret) {
+		pci_err(pdev, "failed to transition the device to run state (%d)\n", ret);
+		return -EIO;
+	}
+	return 0;
+}
+
 static struct pci_tsm_ops cca_devsec_pci_ops = {
 	.lock = cca_tsm_lock,
 	.unlock = cca_tsm_unlock,
+	.accept	 = cca_tsm_accept,
 };
 
 static void cca_devsec_tsm_remove(void *tsm_dev)
diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
index c6b92f4ae9c5..4852a03dd17d 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -331,5 +331,10 @@ int cca_device_verify_and_accept(struct pci_dev *pdev)
 		return -EIO;
 	}
 
+	ret = rhi_vdev_set_tdi_state(pdev, RHI_DA_TDI_CONFIG_RUN);
+	if (ret) {
+		pci_err(pdev, "failed to switch the device (%u) to RUN state\n", ret);
+		return -EIO;
+	}
 	return 0;
 }

---

## [11] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 10/11] coco: arm64: dma: Update force_dma_unencrypted for accepted devices*

This change updates the DMA behavior for accepted devices by assuming
they access only private memory. Currently, the DMA API does not provide
a mechanism for allocating shared memory that can be accessed by both
the secure realm and the non-secure host.

Accepted devices are therefore expected to operate entirely within the
private memory space. As of now, there is no API in the DMA layer that
allows such devices to explicitly request shared memory allocations for
coherent data exchange with the host.

If future use cases require accepted devices to interact with shared
memory— for example, for host-device communication, we will need to
extend the DMA interface to support such allocation semantics. This
commit lays the groundwork for that by clearly defining the current
assumption and isolating the enforcement to force_dma_unencrypted.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  6 +-----
 arch/arm64/mm/mem_encrypt.c          | 10 ++++++++++
 include/linux/swiotlb.h              |  5 +++++
 3 files changed, 16 insertions(+), 5 deletions(-)

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
index ee3c0ab04384..645c099fd551 100644
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
+	if (device_cc_accepted(dev))
+		return false;
+
+	return is_realm_world();
+}
+EXPORT_SYMBOL_GPL(force_dma_unencrypted);
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..b27de03f2466 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -173,6 +173,11 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+	if (device_cc_accepted(dev)) {
+		dev_warn_once(dev, "(TIO) Disable SWIOTLB");
+		return false;
+	}
+
 	return mem && mem->force_bounce;
 }

---

## [12] Aneesh Kumar K.V (Arm) — 2025-11-17
*Subject: [PATCH v2 11/11] coco: guest: arm64: Enable vdev DMA after attestation*

- define SMC_RSI_VDEV_DMA_ENABLE and add wrapper in rsi_cmds.h
- invoke the new helper from the guest accept path once the device
  passes attestation, rolling back to TDI_LOCKED on failure

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi_cmds.h        | 15 +++++++++++++++
 arch/arm64/include/asm/rsi_smc.h         |  2 ++
 drivers/virt/coco/arm-cca-guest/rsi-da.c | 14 ++++++++++++++
 3 files changed, 31 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index e6d68760a729..bce08778c799 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -225,4 +225,19 @@ static inline unsigned long rsi_vdev_get_info(unsigned long vdev_id,
 	return res.a0;
 }
 
+static inline unsigned long __rsi_vdev_dma_enable(unsigned long vdev_id,
+						  unsigned long non_ats_plane,
+						  unsigned long lock_nonce,
+						  unsigned long meas_nonce,
+						  unsigned long report_nonce)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_VDEV_DMA_ENABLE, vdev_id,
+			     non_ats_plane, lock_nonce,
+			     meas_nonce, report_nonce, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
index 49334d07dd55..7bfc8bc5c2ff 100644
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
index 4852a03dd17d..0b98f6271da6 100644
--- a/drivers/virt/coco/arm-cca-guest/rsi-da.c
+++ b/drivers/virt/coco/arm-cca-guest/rsi-da.c
@@ -264,6 +264,13 @@ static int verify_digests(struct cca_guest_dsc *dsc)
 	return 0;
 }
 
+static inline int rsi_vdev_enable_dma(int vdev_id, struct dsm_device_info *dev_info)
+{
+	return __rsi_vdev_dma_enable(vdev_id, 0, dev_info->lock_nonce,
+				     dev_info->meas_nonce, dev_info->report_nonce);
+
+}
+
 int cca_device_verify_and_accept(struct pci_dev *pdev)
 {
 	int ret;
@@ -336,5 +343,12 @@ int cca_device_verify_and_accept(struct pci_dev *pdev)
 		pci_err(pdev, "failed to switch the device (%u) to RUN state\n", ret);
 		return -EIO;
 	}
+
+	if (rsi_vdev_enable_dma(vdev_id, &dsc->dev_info)) {
+		rhi_vdev_set_tdi_state(pdev, RHI_DA_TDI_CONFIG_LOCKED);
+		pci_err(pdev, "failed to enable DMA from the device %d\n", ret);
+		return -EIO;
+	}
+
 	return 0;
 }

---

## [13] Jonathan Cameron — 2025-11-19
*Subject: Re: [PATCH v2 01/11] coco: guest: arm64: Guest TSM callback and
 realm device lock support*

On Mon, 17 Nov 2025 19:29:57 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Register the TSM callback when the DA feature is supported by RSI. The
> build order is also adjusted so that the TSM class is created before the
Hi Aneesh,

Some minor stuff in here.   One general comment is that there
are some fixlets for the CCA code surrounding what this patch
should focus on. Break those out as separate cleanup or base
this on top of the fixed up version of that code.

Thanks,

Jonathan

> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
> index 1b716d18b80e..2ec0f5dff02e 100644

I'm not keen on mixing explicit size of a u64 with the implicit
fact an unsigned long is effectively a u64.  Can we tidy up the types
to match?
 
> +}
> +EXPORT_SYMBOL_GPL(rsi_has_da_feature);

> diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
> index cb52021912b3..57556d7c1cec 100644

Check all patches for noise like this.  It may be a valid change but in this series
it's just adding confusion.

> diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
> index a42359a90558..66b2d9202b66 100644

Push this fixlet to the series adding this or a follow up if that isn't being respun.
Definitely shouldn't be in here.

>  	  attestation report from the Realm Management Monitor(RMM).
> +	  If the DA feature is supported, it also register with TSM framework.

Stray change.

>  obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
>  
Usually we just extend the date span rather than claiming everything is
2025. e.g.
 * Copyright (C) 2023-2025 ARM Ltd.

>   */

> @@ -192,6 +194,57 @@ static void unregister_cca_tsm_report(void *data)
>  	tsm_report_unregister(&arm_cca_tsm_report_ops);

Perhaps add a comment so you have something like

	return ERR_PTR(-EIO); /* For now always return an error */

Just makes it a tiny bit easier to review as no need to go check this
is removed in a later patch.

> +}
> +

Take a look at what the _or_reset() does in the devm_add_action_or_reset().
Short story, you should not need this call if the devm machinery has returned
an error.

> +		return rc;
> +	}

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
> new file mode 100644

> +static inline int rsi_vdev_id(struct pci_dev *pdev)
> +{

I'm struggling to find where this is actually defined in the various specs
so good to have a reference in a comment here.

> +}
> +

---

## [14] Jonathan Cameron — 2025-11-19
*Subject: Re: [PATCH v2 02/11] coco: guest: arm64: Add Realm Host Interface
 and guest DA helper*

On Mon, 17 Nov 2025 19:29:58 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> - describe the Realm Host Interface SMC IDs and result codes in a new
>   `asm/rhi.h` header
Hi Aneesh, minor comments follow.

> diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.c b/drivers/virt/coco/arm-cca-guest/rhi-da.c
> new file mode 100644
...

> +
> +bool rhi_has_da_support(void)

Doesn't look to be passed out anywhere, so not obvious why the lifetime
of this extends beyond this function.  Maybe I'm missing something.

> +	if (!rhicall)
> +		return -ENOMEM;

sizeof(*rhi_call)  Same for all other cases of this.

> +	if (!rhi_call)
> +		return -ENOMEM;

sizeof(*rhi_call) probably preferred.

> +	if (!rhi_call)
> +		return -ENOMEM;

?  Run builds after each patch and you may catch stuff like this.

> +}
> +

Maybe use an enum for target state? Can name it to align with the
RHIDAVDevTDIState used as the type for this in the RHI spec.


> +				    unsigned long *cookie)
> +{

> diff --git a/drivers/virt/coco/arm-cca-guest/rhi-da.h b/drivers/virt/coco/arm-cca-guest/rhi-da.h
> new file mode 100644

Possibly update if this has changed much this year.

> + */
> +

---

## [15] Jonathan Cameron — 2025-11-19
*Subject: Re: [PATCH v2 03/11] coco: guest: arm64: Add support for guest
 initiated TDI bind/unbind*

On Mon, 17 Nov 2025 19:29:59 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add RHI for VDEV_SET_TDI_STATE
> 

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> new file mode 100644

Not sure why this define is here.  It sounds generic
and looks ot be the TDISPVersion field content for first
byte of a TDISP message.  If so should be in a PCI header
not here.

> +
> +int cca_device_lock(struct pci_dev *pdev)
Why eat ret?  It might have a useful error value to the caller.
If there is a reason -EIO is special then add a comment here to explain
that.
> +	}
> +	return 0;
Same as above.
> +	}
> +	return 0;

---

## [16] Jonathan Cameron — 2025-11-19
*Subject: Re: [PATCH v2 04/11] coco: guest: arm64: Add support for updating
 interface reports from device*

On Mon, 17 Nov 2025 19:30:00 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Support collecting interface reports using RSI calls. The fetched
> interface report will be cached in the host.

> diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
> index f4c9e529c43e..7988ff6d4b2e 100644

Why not return ERR_PTR(ret);

> +	}
> +

Given every rsi_host_call I've seen in here is passed
output of virt_to_phys() maybe a wrapper that does that is worthwhile?

rsi_host_call_va() or something like that.

> +	if (ret != RSI_SUCCESS)
> +		return -EIO;


> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.h b/drivers/virt/coco/arm-cca-guest/rsi-da.h
> index d1f4641a0fa1..fd4792a50daf 100644

If the blank line makes sense, should have been in previous patch.

>  #endif

---

## [17] Jonathan Cameron — 2025-11-20
*Subject: Re: [PATCH v2 05/11] coco: guest: arm64: Add support for updating
 measurements from device*

On Mon, 17 Nov 2025 19:30:01 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Fetch device measurements using RSI_RDEV_GET_MEASUREMENTS. The fetched
> device measurements will be cached in the host.
Hi Aneesh

Minor stuff inline.

thanks

Jonathan

> ---
>  arch/arm64/include/asm/rhi.h             | 19 ++++++++
Whilst I appreciate the specs are still subject to minor changes, 
it would be very helpful if definitions like the ones above were
all accompanied by a spec reference.

Which is another way of saying I can't find these ones ;)

> +struct rhi_vdev_measurement_params {
> +	union {

sizeof(*rhi_call) slightly preferred.

> +	if (!rhi_call)
> +		return -ENOMEM;


> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index c8ba72e4be3e..aa6e13e4c0ea 100644

Not sure the comment is necessary given the visible flag.
If you were saying 'why' then a comment would be fine, but this is just
repeating what we can see in the code.

> +	page = alloc_pages_node(nid, gfp_mask | __GFP_ZERO, page_order);
> +
If failing to mark it encrypted is an error I'd find it easier to read this if it were
out of line.

	ret = set_memory...
	if (ret)
		return ret;

	__free_pages();

	return 0;

This is just a preference as someone who reads a lot of code.  Having error handling
as the out of line path is more common and so what my brain (and other reviewers)
has long been trained to expect.

> +}
> +

Perhaps sizeof(*dev_meas) would be both shorter and clearer.

> +	if (!shared_pages)
> +		return -ENOMEM;

It might be worth appropriate DEFINE_FREE() magic to to stash the size away
and simplify this a tiny bit. Kind of depends on whether this is a one off
or those helpers are going to get a reasonable amount of use.

> +	if (ret) {
> +		pci_err(pdev, "failed to get device measurement (%d)\n", ret);

---

## [18] Jonathan Cameron — 2025-11-20
*Subject: Re: [PATCH v2 06/11] coco: guest: arm64: Add support for reading
 cached objects from host*

On Mon, 17 Nov 2025 19:30:02 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Teach rsi_device_start() to pull the interface report and device
> certificate from the host by querying size, sharing a decrypted buffer

I raise this below, but not sure why this is set way before setting
*object.  Can set it later and use max_data_len which I think is
clearer naming anyway.

> +
> +	data_buf_private = kmalloc(*object_size, GFP_KERNEL);

Given data_buf_private() only seems useful if we aren't in an error
condition, why not move allocation to here and use kmemdup() ?

> +	free_shared_pages(shared_pages, max_data_len);
> +

Is it necessary to zero the passed in variable given this function never
touched it and is returning an error. If it is, can you do that unconditionally
at start of function and override only on success?

> +	*object_size = 0;

Likewise for the size - I'm not sure why you set that much earlier
than *object.

With those two gone, this feels like it would be well suited for
some __free magic to handle everything here.
You will need to deal with the free_shared_pages() though which will
require an extra structure definition and helpers to wrap up what
is allocated - similar to what tdx_page_array_alloc does (though without
the bulk aspects of that)

http://lore.kernel.org/all/20251117022311.2443900-7-yilun.xu@linux.intel.com/

Or given the shared page stuff is the inner most aspect anyway you could
just do a helper function from alloc_shared_pages to free_shared_pages
calls so that you can call that free_shared_pages unconditionally before
checking return value.

Note that if you do go with DEFINE_FREE() you 'could' pass in the storage.
I objected to that elsewhere but there is precedence.  So have a
struct shared_pages {
	struct page *page;
	size_t order;
}
define one on the stack and pass it in so that you avoid an extra allocation.
Not a pattern I particularly like though and this isn't expected to be
a particularly fast path so I'd just dynamically allocate a struct shared_pages
inside alloc_shared_pages.


> +	kfree(rhicall);
> +	return ret;

---

## [19] Jonathan Cameron — 2025-11-20
*Subject: Re: [PATCH v2 07/11] coco: guest: arm64: Validate Realm MMIO
 mappings from TDISP report*

On Mon, 17 Nov 2025 19:30:03 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Parse the TDISP device interface report and drive the RSI
> RDEV_VALIDATE_MAPPING handshake for each Realm MMIO window. The new

A few minor things in here.

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index aa6e13e4c0ea..c70fb7dd4838 100644

> +int cca_apply_interface_report_mappings(struct pci_dev *pdev, bool validate)
> +{

I would make scope of some of the variables used in here explicit by declaring them in the loop.
e.g. range_id.

> +		range_id = FIELD_GET(TSM_INTF_REPORT_MMIO_RANGE_ID, mmio_range->range_attributes);
> +
I would drop this blank line. Keep the variable set and error check tightly together.
> +		if (range_id >= PCI_NUM_RESOURCES) {
> +			pci_warn(pdev, "Skipping broken range [%d] #%d %d\n",

Likewise I would drop this blank line.

> +		if (r->end == r->start ||
> +		    resource_size(r) & ~PAGE_MASK || !mmio_range->num_pages) {
Seems like an odd wrap.
		if (r->end == r->start ||
		    resource_size(r) & ~PAGE_MASK ||
		    !mmio_range->num_pages) {

or
		if (r->end == r->start || resource_size(r) & ~PAGE_MASK ||
		    !mmio_range->num_pages) {

Only exception being if you are going to edit this in a patch soon after and this
is about avoiding churn in that patch  - if so ignore this comment.


> +			pci_warn(pdev, "Skipping broken range [%d] #%d %d pages, %llx..%llx\n",
> +				i, range_id, mmio_range->num_pages, r->start, r->end);

>  struct cca_guest_dsc {
>  	struct pci_tsm_devsec pci;

Check all patches for noise like this. Either that white space is good to have in which case
keep it. Or it's not in which case delete.

> +int cca_apply_interface_report_mappings(struct pci_dev *pdev, bool validate);
>  #endif

---

## [20] Jonathan Cameron — 2025-11-20
*Subject: Re: [PATCH v2 08/11] coco: guest: arm64: Add support for fetching
 and verifying device info*

On Mon, 17 Nov 2025 19:30:04 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> RSI_RDEV_GET_INFO returns different digest hash values, which can be
> compared with host cached values to ensure the host didn't tamper with

> diff --git a/drivers/virt/coco/arm-cca-guest/rsi-da.c b/drivers/virt/coco/arm-cca-guest/rsi-da.c
> index c70fb7dd4838..c6b92f4ae9c5 100644

> +
> +static int verify_digests(struct cca_guest_dsc *dsc)

I'd drop this blank line as it doesn't for me at least enhance readability
and I don't recall it being particularly common to have one here
in kernel code.

> +		digest_func(reports[i].report, reports[i].size, digest);
> +		if (memcmp(reports[i].digest, digest, digest_size)) {

Could use __free for that and not worry that we free it a little later than
last place we need it.

> +		return -EIO;
> +	}

So copy everything other than flags.  Any reason why not flags?
> +
> +	kfree(dev_info);

---

## [21] Jonathan Cameron — 2025-11-20
*Subject: Re: [PATCH v2 09/11] coco: guest: arm64: Wire Realm TDISP RUN/STOP
 transitions into guest driver*

On Mon, 17 Nov 2025 19:30:05 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Teach the Arm CCA guest driver how to transition a Realm device between
> RUN and STOP states. The new helpers issue the RSI START/STOP calls,
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [22] Jonathan Cameron — 2025-11-20
*Subject: Re: [PATCH v2 10/11] coco: arm64: dma: Update force_dma_unencrypted
 for accepted devices*

On Mon, 17 Nov 2025 19:30:06 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> This change updates the DMA behavior for accepted devices by assuming
> they access only private memory. Currently, the DMA API does not provide

Isn't this sentence a bit of a repeat of the one at the end of the
1st paragraph.

> 
> If future use cases require accepted devices to interact with shared

---

## [23] Jonathan Cameron — 2025-11-20
*Subject: Re: [PATCH v2 11/11] coco: guest: arm64: Enable vdev DMA after
 attestation*

On Mon, 17 Nov 2025 19:30:07 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> - define SMC_RSI_VDEV_DMA_ENABLE and add wrapper in rsi_cmds.h
> - invoke the new helper from the guest accept path once the device
LGTM
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [24] Aneesh Kumar K.V — 2025-11-24
*Subject: Re: [PATCH v2 01/11] coco: guest: arm64: Guest TSM callback and
 realm device lock support*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 17 Nov 2025 19:29:57 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

will switch rsi_feat_reg0 to static u64

>> +}
>> +EXPORT_SYMBOL_GPL(rsi_has_da_feature);

This is required for the patch to work as intended. This patch adds
registration with TSM, which depends on the TSM class being created
before the arm_cca_guest driver is initialized. The commit message
provides further details.

"Register the TSM callback when the DA feature is supported by RSI. The
build order is also adjusted so that the TSM class is created before the
arm-cca-guest driver is initialized.""


>
>> diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig

The vdev_id is provided by the host during the rmi_vdev_create
operation. In the Linux implementation, we use the guest_rid as the
vdev_id.

https://git.gitlab.arm.com/linux-arm/linux-cca/-/commit/3c55fc14480183f18c694e3d6054578830719d00#152a2139b6b88b07ff1e0f53e408a1d4158076a4_643_715


>> +}
>> +

-aneesh

---

## [25] Aneesh Kumar K.V — 2025-11-24
*Subject: Re: [PATCH v2 02/11] coco: guest: arm64: Add Realm Host Interface
 and guest DA helper*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 17 Nov 2025 19:29:58 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

This should be similar to other calls

	struct rsi_host_call *rhicall __free(kfree) =
		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);

I’ll update the code to reflect that. Thanks for pointing it out.

>
>> +	if (!rhicall)

how about enum rhi_tdi_state ?

>
>

-aneesh

---

## [26] Aneesh Kumar K.V — 2025-11-24
*Subject: Re: [PATCH v2 04/11] coco: guest: arm64: Add support for updating
 interface reports from device*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 17 Nov 2025 19:30:00 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

how about static inline unsigned long rsi_host_call(struct rsi_host_call *rhi_call)


>
>> +	if (ret != RSI_SUCCESS)

---

## [27] Aneesh Kumar K.V — 2025-11-24
*Subject: Re: [PATCH v2 05/11] coco: guest: arm64: Add support for updating
 measurements from device*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 17 Nov 2025 19:30:01 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

The RHI spec update is still pending. In the meantime, the relevant
details can be found in the RMI spec under section B4.4.69, which
describes the RmiVdevMeasureFlags type. I’ll update the cover letter to
reference the specific spec details that these patches are based on.

>
>> +struct rhi_vdev_measurement_params {

something like

static inline void vdev_meas_params_free(struct rhi_vdev_measurement_params *params)
{
	struct page *pages = virt_to_page(params);

	free_shared_pages(pages, sizeof(struct rhi_vdev_measurement_params));
}
DEFINE_FREE(vdev_meas_params_free, struct rhi_vdev_measurement_params *, if (_T) vdev_meas_params_free(_T))


>
>> +	if (ret) {

-aneesh

---

## [28] Aneesh Kumar K.V — 2025-11-24
*Subject: Re: [PATCH v2 06/11] coco: guest: arm64: Add support for reading
 cached objects from host*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 17 Nov 2025 19:30:02 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

I'm not sure we need a new struct here, since other shared pages do have
type like struct rhi_vdev_measurement_params. The read-cached object is
the only exception.

That said, I’ve updated the other allocation to use __free() as suggested.

int rhi_read_cached_object(int vdev_id, int da_object_type, void **object, int *object_size)
{
	int ret;
	int max_data_len;
	void *data_buf_shared;
	struct page *shared_pages;

	*object_size = 0;
	*object = NULL;

	struct rsi_host_call *rhicall __free(kfree) =
		kmalloc(sizeof(struct rsi_host_call), GFP_KERNEL);
	if (!rhicall)
		return -ENOMEM;

	rhicall->imm = 0;
	rhicall->gprs[0] = RHI_DA_OBJECT_SIZE;
	rhicall->gprs[1] = vdev_id;
	rhicall->gprs[2] = da_object_type;

	ret = rsi_host_call(virt_to_phys(rhicall));
	if (ret != RSI_SUCCESS)
		return -EIO;

	if (rhicall->gprs[0] != RHI_DA_SUCCESS)
		return -EIO;

	/* validate against the max cache object size used on host. */
	max_data_len = rhicall->gprs[1];
	if (max_data_len > MAX_CACHE_OBJ_SIZE || max_data_len == 0)
		return -EIO;

	shared_pages = alloc_shared_pages(NUMA_NO_NODE, GFP_KERNEL, max_data_len);
	if (!shared_pages)
		return -ENOMEM;

	data_buf_shared = page_address(shared_pages);

	rhicall->imm = 0;
	rhicall->gprs[0] = RHI_DA_OBJECT_READ;
	rhicall->gprs[1] = vdev_id;
	rhicall->gprs[2] = da_object_type;
	rhicall->gprs[3] = 0; /* offset within the data buffer */
	rhicall->gprs[4] = max_data_len;
	rhicall->gprs[5] = virt_to_phys(data_buf_shared);
	ret = rsi_host_call(virt_to_phys(rhicall));
	if (ret != RSI_SUCCESS || rhicall->gprs[0] != RHI_DA_SUCCESS) {
		free_shared_pages(shared_pages, max_data_len);
		return -EIO;
	}

	void *data_buf_private __free(kvfree) =
		kvmemdup(data_buf_shared, max_data_len, GFP_KERNEL);
	/* free the shared pages irrespective of error condition */
	free_shared_pages(shared_pages, max_data_len);
	if (!data_buf_private)
		return -ENOMEM;

	*object = data_buf_private;
	*object_size = max_data_len;
	return 0;
}

---

## [29] Aneesh Kumar K.V — 2025-11-24
*Subject: Re: [PATCH v2 08/11] coco: guest: arm64: Add support for fetching
 and verifying device info*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 17 Nov 2025 19:30:04 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

...

>
>> +		return -EIO;

The flags field currently carries p2p_enabled and p2p_bound, but these
aren’t used yet. I’ll drop flags from dsc->dev_info for now and
reintroduce it once there’s an actual user.

>> +
>> +	kfree(dev_info);

---

## [30] Will Deacon — 2026-01-08
*Subject: Re: [PATCH v2 03/11] coco: guest: arm64: Add support for guest
 initiated TDI bind/unbind*

On Mon, Nov 17, 2025 at 07:29:59PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add RHI for VDEV_SET_TDI_STATE
> 

Then maybe send this as an RFC given that it doesn't sound like something
we should be merging?

Will

---
