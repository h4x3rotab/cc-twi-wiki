---
title: '[RFC PATCH v4 00/14] coco/TSM: Host-side Arm CCA IDE setup via connect/disconnect callbacks'
date: 2026-04-27
last_reply: 2026-05-27
message_count: 20
participants: ['Aneesh Kumar K.V (Arm)', 'Will Deacon', 'Suzuki K Poulose', 'Dan Williams (nvidia)']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-04-27

This patch series implements the TSM ->connect() and ->disconnect() callbacks
required for the Arm CCA IDE setup as per the RMM 2.0bet1 specification [1].

This patchset includes the host-side flow needed by connect/disconnect,
including:
- DA feature detection helpers
- host TSM callback wiring and IDE stream allocation support
- creation/registration of RMM pdev descriptors
- RMM pdev communication helpers
- pdev stop and teardown helpers for disconnect
- pdev instantiation from the connect path
- public key registration with RMM

To support public-key handling from the device certificate chain, the series
also includes the required X.509 parser updates.

The series builds upon the TSM framework patches posted at [2] and depends on
the KVM CCA patchset [3]. A git repository containing all the related changes is
available at [4].

Testing / Usage

To initiate the IDE setup:
	echo tsm0 > /sys/bus/pci/devices/$DEVICE/tsm/connect

To disconnect:
	echo tsm0 > /sys/bus/pci/devices/$DEVICE/tsm/disconnect

Changes from v3:
https://lore.kernel.org/all/20260312080129.3483585-1-aneesh.kumar@kernel.org
* updated the patches to follow the RMM 2.0bet1 specification
* reworked the host-side pdev lifecycle to better match the RMM 2.0bet1 flow,
  including common pdev state, root-port pdev support, and non-coherent stream
  setup and teardown
* split PF0 setup into identity collection and conditional public-key
  installation, and gate DA enablement on RMI_FEATURE_REGISTER_2_DA
* added coordinated handling for RMI_DEV_COMM_EXIT_STREAM_WAIT, along with
  stream connect/disconnect and stream key refresh/purge support during vdev
  teardown

Changes from v2:
rfc-v2 https://lore.kernel.org/all/20251027095602.1154418-1-aneesh.kumar@kernel.org
* rebase to latest kernel and core TSM changes
* Address review feedback.

v1:
rfc-v1 https://lore.kernel.org/all/20250728135216.48084-1-aneesh.kumar@kernel.org

[1] https://developer.arm.com/documentation/den0137/2-0bet1/
[2] https://lore.kernel.org/all/20260303000207.1836586-1-dan.j.williams@intel.com
[3] https://lore.kernel.org/all/20260318155413.793430-1-steven.price@arm.com
[4] https://gitlab.arm.com/linux-arm/linux-cca.git cca/topics/cca-tdisp-upstream-rfc-v4

Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Jonathan Cameron <jic23@kernel.org>
Cc: Marc Zyngier <maz@kernel.org>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Xu Yilun <yilun.xu@linux.intel.com>

Aneesh Kumar K.V (Arm) (11):
  coco: host: arm64: Add host TSM callback and IDE stream allocation
    support
  coco: host: arm64: Create RMM pdev objects for PCI endpoints
  coco: host: arm64: Add RMM device communication helpers
  coco: host: arm64: Add helper to stop and tear down an RMM pdev
  coco: host: arm64: Register device public key with RMM
  coco: host: arm64: Initialize RMM pdev state for TDISP IDE connect
  coco: host: arm64: Coordinate peer stream waits during pdev
    communication
  coco: host: arm64: Connect RMM pdev streams for IDE devices
  coco: host: arm64: Refcount root-port pdevs used by IDE streams
  PCI/TSM: Move CMA DOE mailbox discovery out of
    pci_tsm_pf0_constructor()
  coco: host: arm64: Add NCOH_SYS stream support for RC endpoints

Lukas Wunner (3):
  X.509: Make certificate parser public
  X.509: Parse Subject Alternative Name in certificates
  X.509: Move certificate length retrieval into new helper

 arch/arm64/include/asm/rmi_cmds.h         |  85 +++
 arch/arm64/include/asm/rmi_smc.h          | 168 +++++
 crypto/asymmetric_keys/x509_cert_parser.c |   9 +
 crypto/asymmetric_keys/x509_loader.c      |  38 +-
 crypto/asymmetric_keys/x509_parser.h      |  42 +-
 drivers/crypto/ccp/sev-dev-tsm.c          |  13 +
 drivers/firmware/smccc/rmm.c              |  12 +
 drivers/firmware/smccc/rmm.h              |   8 +
 drivers/firmware/smccc/smccc.c            |   1 +
 drivers/pci/tsm/core.c                    |  14 +-
 drivers/virt/coco/Kconfig                 |   2 +
 drivers/virt/coco/Makefile                |   1 +
 drivers/virt/coco/arm-cca-host/Kconfig    |  23 +
 drivers/virt/coco/arm-cca-host/Makefile   |   5 +
 drivers/virt/coco/arm-cca-host/arm-cca.c  | 494 ++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c   | 867 ++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h   | 217 ++++++
 drivers/virt/coco/tdx-host/tdx-host.c     |  13 +
 include/keys/asymmetric-type.h            |   2 +
 include/keys/x509-parser.h                |  57 ++
 20 files changed, 2012 insertions(+), 59 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-host/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-host/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-host/arm-cca.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.h
 create mode 100644 include/keys/x509-parser.h

---

## [2] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 01/14] coco: host: arm64: Add host TSM callback and IDE stream allocation support*

Register the TSM callback when the DA feature is supported by KVM.

This driver handles IDE stream setup for both the root port and PCIe
endpoints. Root port IDE stream enablement itself is managed by RMM.

In addition, the driver registers pci_tsm_ops with the TSM subsystem.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h         |   2 +
 drivers/firmware/smccc/rmm.c             |  12 ++
 drivers/firmware/smccc/rmm.h             |   8 +
 drivers/firmware/smccc/smccc.c           |   1 +
 drivers/virt/coco/Kconfig                |   2 +
 drivers/virt/coco/Makefile               |   1 +
 drivers/virt/coco/arm-cca-host/Kconfig   |  19 ++
 drivers/virt/coco/arm-cca-host/Makefile  |   5 +
 drivers/virt/coco/arm-cca-host/arm-cca.c | 225 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  46 +++++
 10 files changed, 321 insertions(+)
 create mode 100644 drivers/virt/coco/arm-cca-host/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-host/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-host/arm-cca.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.h

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index fa23818e1b4c..109d6cc6ef37 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -12,6 +12,8 @@
 
 #include <linux/arm-smccc.h>
 
+#define RMI_DEV_NAME "arm-rmi-dev"
+
 #define SMC_RMI_CALL(func)				\
 	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
 			   ARM_SMCCC_SMC_64,		\
diff --git a/drivers/firmware/smccc/rmm.c b/drivers/firmware/smccc/rmm.c
index 2a6187df3285..7444cc3a588c 100644
--- a/drivers/firmware/smccc/rmm.c
+++ b/drivers/firmware/smccc/rmm.c
@@ -21,3 +21,15 @@ void __init register_rsi_device(struct platform_device *pdev)
 	__devm_auxiliary_device_create(&pdev->dev,
 				       "arm_cca_guest", RSI_DEV_NAME, NULL, 0);
 }
+
+void __init register_rmi_device(struct platform_device *pdev)
+{
+	struct arm_smccc_res res;
+	unsigned long host_version = RMI_ABI_VERSION(RMI_ABI_MAJOR_VERSION,
+						     RMI_ABI_MINOR_VERSION);
+
+	arm_smccc_1_1_invoke(SMC_RMI_VERSION, host_version, &res);
+	if (res.a0 == RMI_SUCCESS)
+		__devm_auxiliary_device_create(&pdev->dev,
+					"arm_cca_host", RMI_DEV_NAME, NULL, 0);
+}
diff --git a/drivers/firmware/smccc/rmm.h b/drivers/firmware/smccc/rmm.h
index a47a650d4f51..37d0d95a099e 100644
--- a/drivers/firmware/smccc/rmm.h
+++ b/drivers/firmware/smccc/rmm.h
@@ -6,12 +6,20 @@
 
 #ifdef CONFIG_ARM64
 #include <asm/rsi_cmds.h>
+#include <asm/rmi_smc.h>
+
 void __init register_rsi_device(struct platform_device *pdev);
+void __init register_rmi_device(struct platform_device *pdev);
 #else
 
 static void __init register_rsi_device(struct platform_device *pdev)
 {
 
+}
+
+static void __init register_rmi_device(struct platform_device *pdev)
+{
+
 }
 #endif
 #endif
diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index fc9b44b7c687..2bf2d59e686d 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -97,6 +97,7 @@ static int __init smccc_devices_init(void)
 		 * the required SMCCC function IDs at a supported revision.
 		 */
 		register_rsi_device(pdev);
+		register_rmi_device(pdev);
 	}
 
 	if (smccc_trng_available) {
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index f7691f64fbe3..1cbc2134f9ea 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -19,5 +19,7 @@ endif
 
 source "drivers/virt/coco/tdx-host/Kconfig"
 
+source "drivers/virt/coco/arm-cca-host/Kconfig"
+
 config TSM
 	bool
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index b323b0ae4f82..f2310c34daf9 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -10,3 +10,4 @@ obj-$(CONFIG_INTEL_TDX_HOST)	+= tdx-host/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
+obj-$(CONFIG_ARM_CCA_HOST)	+= arm-cca-host/
diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
new file mode 100644
index 000000000000..efe40d61d5d8
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/Kconfig
@@ -0,0 +1,19 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# TSM (TEE Security Manager) host drivers
+#
+config ARM_CCA_HOST
+	tristate "Arm CCA Host driver"
+	depends on ARM64
+	depends on PCI
+	depends on KVM
+	select PCI_TSM
+	select AUXILIARY_BUS
+
+	help
+	  ARM CCA RMM firmware is the trusted runtime that enforces memory
+	  isolation and security for confidential computing on ARM. This driver
+	  provides the interface for communicating with RMM to support secure
+	  device assignment.
+
+	  If you choose 'M' here, this module will be called arm-cca-host.
diff --git a/drivers/virt/coco/arm-cca-host/Makefile b/drivers/virt/coco/arm-cca-host/Makefile
new file mode 100644
index 000000000000..c236827f002c
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/Makefile
@@ -0,0 +1,5 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+obj-$(CONFIG_ARM_CCA_HOST) += arm-cca-host.o
+
+arm-cca-host-y	+=  arm-cca.o
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
new file mode 100644
index 000000000000..67f7e80106e8
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -0,0 +1,225 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#include <linux/auxiliary_bus.h>
+#include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include <linux/vmalloc.h>
+#include <linux/cleanup.h>
+
+#include "rmi-da.h"
+
+/* Total number of stream id supported at root port level */
+#define MAX_STREAM_ID	256
+
+static struct pci_tsm *cca_tsm_pci_probe(struct tsm_dev *tsm_dev, struct pci_dev *pdev)
+{
+	int ret;
+
+	if (!is_pci_tsm_pf0(pdev)) {
+		struct cca_host_fn_dsc *fn_dsc __free(kfree) =
+			kzalloc(sizeof(*fn_dsc), GFP_KERNEL);
+
+		if (!fn_dsc)
+			return NULL;
+
+		ret = pci_tsm_link_constructor(pdev, &fn_dsc->pci, tsm_dev);
+		if (ret)
+			return NULL;
+
+		return &no_free_ptr(fn_dsc)->pci;
+	}
+
+	if (!pdev->ide_cap)
+		return NULL;
+
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc __free(kfree) =
+		kzalloc(sizeof(*pf0_ep_dsc), GFP_KERNEL);
+	if (!pf0_ep_dsc)
+		return NULL;
+
+	ret = pci_tsm_pf0_constructor(pdev, &pf0_ep_dsc->pci, tsm_dev);
+	if (ret)
+		return NULL;
+
+	pci_dbg(pdev, "tsm enabled\n");
+	return &no_free_ptr(pf0_ep_dsc)->pci.base_tsm;
+}
+
+static void cca_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+
+	if (is_pci_tsm_pf0(pdev)) {
+		struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+
+		pci_tsm_pf0_destructor(&pf0_ep_dsc->pci);
+		kfree(pf0_ep_dsc);
+	} else {
+		kfree(to_cca_fn_dsc(pdev));
+	}
+}
+
+/* For now global for simplicity. Protected by pci_tsm_rwsem */
+static DECLARE_BITMAP(cca_stream_ids, MAX_STREAM_ID);
+static int alloc_stream_id(struct pci_host_bridge *hb)
+{
+	int stream_id;
+
+redo_alloc:
+	stream_id = find_first_zero_bit(cca_stream_ids, MAX_STREAM_ID);
+	if (stream_id == MAX_STREAM_ID)
+		return stream_id;
+
+	if (ida_exists(&hb->ide_stream_ids_ida, stream_id)) {
+		/* mark the stream allocated in the global bitmap. */
+		set_bit(stream_id, cca_stream_ids);
+		goto redo_alloc;
+	}
+	return stream_id;
+}
+
+static inline bool cca_pdev_need_sel_ide_streams(struct pci_dev *pdev)
+{
+	return pci_pcie_type(pdev) == PCI_EXP_TYPE_ENDPOINT;
+}
+
+static int cca_tsm_connect(struct pci_dev *pdev)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+	struct pci_ide *ide;
+	int ret, stream_id = 0;
+
+	/* Only function 0 supports connect in host */
+	if (WARN_ON(!is_pci_tsm_pf0(pdev)))
+		return -EIO;
+
+	pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+	if (cca_pdev_need_sel_ide_streams(pdev)) {
+		/* Allocate stream id */
+		stream_id = alloc_stream_id(pci_find_host_bridge(pdev->bus));
+		if (stream_id == MAX_STREAM_ID)
+			return -EBUSY;
+		set_bit(stream_id, cca_stream_ids);
+
+		ide = pci_ide_stream_alloc(pdev);
+		if (!ide) {
+			ret = -ENOMEM;
+			goto err_stream_alloc;
+		}
+
+		pf0_ep_dsc->sel_stream = ide;
+		ide->stream_id = stream_id;
+		ret = pci_ide_stream_register(ide);
+		if (ret)
+			goto err_stream;
+		/*
+		 * Configure IDE capability for target device
+		 *
+		 * Some test devices work only with DEFAULT_STREAM enabled.
+		 * For simplicity, enable DEFAULT_STREAM for all devices. A
+		 * future decent solution may be to have a quirk table to
+		 * specify which devices need DEFAULT_STREAM.
+		 */
+		ide->partner[PCI_IDE_EP].default_stream = 1;
+		pci_ide_stream_setup(pdev, ide);
+		pci_ide_stream_setup(rp, ide);
+
+		ret = tsm_ide_stream_register(ide);
+		if (ret)
+			goto err_tsm;
+
+		/*
+		 * Once ide is setup, enable the stream at the endpoint
+		 * Root port will be done by RMM
+		 */
+		pci_ide_stream_enable(pdev, ide);
+	}
+	return 0;
+
+err_tsm:
+	if (cca_pdev_need_sel_ide_streams(pdev)) {
+		pci_ide_stream_teardown(rp, ide);
+		pci_ide_stream_teardown(pdev, ide);
+		pci_ide_stream_unregister(ide);
+	}
+err_stream:
+	if (cca_pdev_need_sel_ide_streams(pdev))
+		pci_ide_stream_free(ide);
+	pf0_ep_dsc->sel_stream = NULL;
+err_stream_alloc:
+	clear_bit(stream_id, cca_stream_ids);
+
+	return ret;
+}
+
+static void cca_tsm_disconnect(struct pci_dev *pdev)
+{
+	int stream_id;
+	struct pci_ide *ide;
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+
+	pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+	if (!pf0_ep_dsc)
+		return;
+
+	if (cca_pdev_need_sel_ide_streams(pdev)) {
+		ide = pf0_ep_dsc->sel_stream;
+		stream_id = ide->stream_id;
+
+		pci_ide_stream_release(ide);
+		pf0_ep_dsc->sel_stream = NULL;
+		clear_bit(stream_id, cca_stream_ids);
+	}
+
+}
+
+static struct pci_tsm_ops cca_link_pci_ops = {
+	.probe = cca_tsm_pci_probe,
+	.remove = cca_tsm_pci_remove,
+	.connect = cca_tsm_connect,
+	.disconnect = cca_tsm_disconnect,
+};
+
+static void cca_link_tsm_remove(void *tsm_dev)
+{
+	tsm_unregister(tsm_dev);
+}
+
+static int cca_link_tsm_probe(struct auxiliary_device *adev,
+		const struct auxiliary_device_id *id)
+{
+	struct tsm_dev *tsm_dev;
+
+	if (!rmm_has_reg2_feature(RMI_FEATURE_REGISTER_2_DA))
+		return -ENODEV;
+
+	tsm_dev = tsm_register(&adev->dev, &cca_link_pci_ops);
+	if (IS_ERR(tsm_dev))
+		return PTR_ERR(tsm_dev);
+
+	return devm_add_action_or_reset(&adev->dev, cca_link_tsm_remove,
+					tsm_dev);
+}
+
+static const struct auxiliary_device_id cca_link_tsm_id_table[] = {
+	{ .name =  KBUILD_MODNAME "." RMI_DEV_NAME },
+	{}
+};
+MODULE_DEVICE_TABLE(auxiliary, cca_link_tsm_id_table);
+
+static struct auxiliary_driver cca_link_tsm_driver = {
+	.probe = cca_link_tsm_probe,
+	.id_table = cca_link_tsm_id_table,
+};
+module_auxiliary_driver(cca_link_tsm_driver);
+MODULE_IMPORT_NS("PCI_IDE");
+MODULE_AUTHOR("Aneesh Kumar <aneesh.kumar@kernel.org>");
+MODULE_DESCRIPTION("ARM CCA Host TSM driver");
+MODULE_LICENSE("GPL");
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
new file mode 100644
index 000000000000..4abc7ad159e5
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -0,0 +1,46 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#ifndef _VIRT_COCO_RMM_DA_H_
+#define _VIRT_COCO_RMM_DA_H_
+
+#include <linux/pci.h>
+#include <linux/pci-ide.h>
+#include <linux/pci-tsm.h>
+#include <asm/rmi_cmds.h>
+#include <asm/rmi_smc.h>
+
+/**
+ * struct cca_host_pf0_ep_dsc - PF0 endpoint device security context.
+ * @pci: Physical Function 0 TDISP link context
+ * @sel_stream: Selective IDE Stream descriptor
+ */
+struct cca_host_pf0_ep_dsc {
+	struct pci_tsm_pf0 pci;
+	struct pci_ide *sel_stream;
+};
+
+struct cca_host_fn_dsc {
+	struct pci_tsm pci;
+};
+
+static inline struct cca_host_pf0_ep_dsc *to_cca_pf0_ep_dsc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm || !is_pci_tsm_pf0(pdev))
+		return NULL;
+
+	return container_of(tsm, struct cca_host_pf0_ep_dsc, pci.base_tsm);
+}
+
+static inline struct cca_host_fn_dsc *to_cca_fn_dsc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	return container_of(tsm, struct cca_host_fn_dsc, pci);
+}
+
+#endif

---

## [3] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 02/14] coco: host: arm64: Create RMM pdev objects for PCI endpoints*

Add the RMI definitions needed for pdev management, including the pdev
state enum, parameter layout, and helpers for RMI_PDEV_CREATE and
RMI_PDEV_GET_STATE.

Introduce a host-side pdev descriptor and cca_pdev_create() to
allocate and delegate the backing granule, populate the pdev parameters
from the PCI endpoint, and issue RMI_PDEV_CREATE to the RMM.

The new helper stores the created RMM pdev handle in the PF0 endpoint
descriptor preparing the device for later IDE/TDISP setup.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       |  10 ++
 arch/arm64/include/asm/rmi_smc.h        |  49 ++++++++
 drivers/virt/coco/arm-cca-host/Makefile |   2 +-
 drivers/virt/coco/arm-cca-host/rmi-da.c | 151 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h |  26 ++++
 5 files changed, 237 insertions(+), 1 deletion(-)
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.c

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 2901fc84d245..d23a0590c7ee 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -726,4 +726,14 @@ static inline int rmi_rtt_unmap_unprotected(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_get_state(unsigned long pdev_phys, enum rmi_pdev_state *state)
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
index 109d6cc6ef37..94bcaf3e7e68 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -429,4 +429,53 @@ struct rec_run {
 	struct rec_exit exit;
 };
 
+enum rmi_pdev_state {
+	RMI_PDEV_NEW,
+	RMI_PDEV_NEEDS_KEY,
+	RMI_PDEV_HAS_KEY,
+	RMI_PDEV_READY,
+	RMI_PDEV_STOPPED,
+	RMI_PDEV_ERROR,
+};
+
+#define RMI_PDEV_FLAGS_SPDM		BIT(0)
+#define RMI_PDEV_FLAGS_CATEGORY_MASK	GENMASK(2, 1)
+#define RMI_PDEV_FLAGS_CATEGORY_SHIFT	1
+#define RMI_PDEV_FLAGS_P2P		BIT(3)
+
+#define RMI_PDEV_FLAGS_CATEGORY_ROOT_PORT	0x0
+#define RMI_PDEV_FLAGS_CATEGORY_OFF_CHIP_EP	0x1
+#define RMI_PDEV_FLAGS_CATEGORY_ON_CHIP_EP	0x2
+#define RMI_PDEV_FLAGS_CATEGORY_CMEM		0x3
+
+#define RMI_HASH_SHA_256	0x0
+#define RMI_HASH_SHA_512	0x1
+#define RMI_HASH_SHA_384	0x2
+
+struct rmi_pdev_params {
+	union {
+		struct {
+			u64 flags;
+			u64 pdev_id;
+			//u64 rc_id;
+			u64 routing_id;
+			u64 id_index;
+			union {
+				u16 rid_base;
+				u8 padding1[8];
+			};
+			union {
+				u16 rid_top;
+				u8 padding2[8];
+			};
+			union {
+				u8 hash_algo;
+				u8 padding3[8];
+			};
+			u64 max_vdevs_order;
+		};
+		u8 padding5[0x1000];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/Makefile b/drivers/virt/coco/arm-cca-host/Makefile
index c236827f002c..d48e8940af46 100644
--- a/drivers/virt/coco/arm-cca-host/Makefile
+++ b/drivers/virt/coco/arm-cca-host/Makefile
@@ -2,4 +2,4 @@
 #
 obj-$(CONFIG_ARM_CCA_HOST) += arm-cca-host.o
 
-arm-cca-host-y	+=  arm-cca.o
+arm-cca-host-y	+=  arm-cca.o rmi-da.o
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
new file mode 100644
index 000000000000..8fb5d286fd82
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -0,0 +1,151 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#include <linux/pci.h>
+#include <linux/pci-ecam.h>
+#include <asm/rmi_cmds.h>
+
+#include "rmi-da.h"
+
+static int pci_ide_segment(struct pci_dev *pdev)
+{
+	if (pdev->fm_enabled)
+		return pci_domain_nr(pdev->bus);
+	return 0;
+}
+
+static unsigned int pci_get_max_rid(struct pci_dev *pdev)
+{
+	int fn;
+	int max_rid;
+	int slot = PCI_SLOT(pdev->devfn);
+
+	for (fn = 0; fn < 8; fn++) {
+		struct pci_dev *fn_dev;
+
+		fn_dev = pci_get_slot(pdev->bus, PCI_DEVFN(slot, fn));
+		if (!fn_dev)
+			continue;
+
+		max_rid = PCI_DEVFN(slot, fn);
+		pci_dev_put(fn_dev);
+	}
+	return max_rid;
+}
+
+static int init_pdev_params(struct pci_dev *pdev, struct rmi_pdev_params *params)
+{
+	int rid;
+	unsigned long category;
+	struct pci_config_window *cfg = pdev->bus->sysdata;
+
+	/* check we are ECAM compliant */
+	if (!pdev->bus->ops->map_bus)
+		return -EINVAL;
+
+	switch (pci_pcie_type(pdev)) {
+	case PCI_EXP_TYPE_ENDPOINT: {
+		struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+
+		/* Endpoint needs DOE mailbox */
+		if (!pf0_ep_dsc->pci.doe_mb)
+			return -EINVAL;
+
+		params->flags = RMI_PDEV_FLAGS_SPDM;
+		category = RMI_PDEV_FLAGS_CATEGORY_OFF_CHIP_EP;
+		break;
+	}
+	default:
+		return -EINVAL;
+	}
+
+	params->flags |= (category << RMI_PDEV_FLAGS_CATEGORY_SHIFT);
+	/* assign the ep device with RMM */
+	rid = pci_dev_id(pdev);
+	params->pdev_id = cfg->res.start | rid;
+	// ecam window base FIXME!!
+	//params->pdev_id = rid;
+	//params->rc_id = cfg->res.start;
+	params->routing_id = pci_ide_segment(pdev);
+	/* slot number for certificate chain default to zero */
+	params->id_index = 0;
+	params->hash_algo = RMI_HASH_SHA_256;
+	/* no multi function device here. */
+	params->rid_base = rid;
+	params->rid_top = pci_get_max_rid(pdev) + 1;
+	// FIXME!! what is this?
+	params->max_vdevs_order = 10;
+	return 0;
+}
+
+static inline int rmi_pdev_create(unsigned long pdev_phys,
+		unsigned long pdev_params_phys, unsigned long *rmi_ret)
+{
+
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_PDEV_CREATE, pdev_phys, pdev_params_phys);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+
+	return 0;
+}
+
+int cca_pdev_create(struct pci_dev *pci_dev)
+{
+	int ret;
+	void *rmm_pdev;
+	bool should_free = true;
+	phys_addr_t rmm_pdev_phys;
+	struct rmi_pdev_params *params;
+	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(pci_dev);
+
+	rmm_pdev = (void *)get_zeroed_page(GFP_KERNEL);
+	if (!rmm_pdev)
+		return -ENOMEM;
+
+	rmm_pdev_phys = virt_to_phys(rmm_pdev);
+	if (rmi_delegate_page(rmm_pdev_phys)) {
+		ret = -EIO;
+		goto err_granule_delegate;
+	}
+
+	params = (struct rmi_pdev_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params) {
+		ret = -ENOMEM;
+		goto err_param_alloc;
+	}
+
+	ret = init_pdev_params(pci_dev, params);
+	if (ret)
+		goto err_init_pdev_params;
+
+	{
+		unsigned long rmi_ret;
+
+		ret = rmi_pdev_create(rmm_pdev_phys, virt_to_phys(params),
+				      &rmi_ret);
+		if (ret || rmi_ret) {
+			if (!ret)
+				ret = -EIO;
+			goto err_init_pdev_params;
+		}
+	}
+
+	pdev_dsc->rmm_pdev = rmm_pdev;
+	free_page((unsigned long)params);
+	return 0;
+
+err_init_pdev_params:
+	free_page((unsigned long)params);
+err_param_alloc:
+	if (rmi_undelegate_page(rmm_pdev_phys))
+		should_free = false;
+err_granule_delegate:
+	if (should_free)
+		free_page((unsigned long)rmm_pdev);
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 4abc7ad159e5..de67f10ce20e 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -12,13 +12,26 @@
 #include <asm/rmi_cmds.h>
 #include <asm/rmi_smc.h>
 
+/**
+ * struct cca_host_pdev_dsc - Common RMM pdev context
+ * @rmm_pdev: Delegated page backing the RMM pdev object
+ * @object_lock: Serializes access to the RMM pdev object and PF0/TDI caches
+ */
+struct cca_host_pdev_dsc {
+	void *rmm_pdev;
+	/* lock kept here to simplify the generic lock/unlock paths. */
+	struct mutex object_lock;
+};
+
 /**
  * struct cca_host_pf0_ep_dsc - PF0 endpoint device security context.
  * @pci: Physical Function 0 TDISP link context
+ * @pdev: pdev communication context
  * @sel_stream: Selective IDE Stream descriptor
  */
 struct cca_host_pf0_ep_dsc {
 	struct pci_tsm_pf0 pci;
+	struct cca_host_pdev_dsc pdev;
 	struct pci_ide *sel_stream;
 };
 
@@ -43,4 +56,17 @@ static inline struct cca_host_fn_dsc *to_cca_fn_dsc(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_host_fn_dsc, pci);
 }
 
+static inline struct cca_host_pdev_dsc *to_cca_pdev_dsc(struct pci_dev *pdev)
+{
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+
+	pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+	if (pf0_ep_dsc)
+		return &pf0_ep_dsc->pdev;
+
+	return NULL;
+}
+
+int cca_pdev_create(struct pci_dev *pdev);
+
 #endif

---

## [4] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 03/14] coco: host: arm64: Add RMM device communication helpers*

- add SMCCC IDs/wrappers for RMI_PDEV_COMMUNICATE/RMI_PDEV_ABORT
- describe the RMM device-communication ABI (struct rmi_dev_comm_*,
  cache flags, protocol/object IDs, busy error code)
- track per-PF0 communication state (buffers, workqueue, cache metadata) and
  serialize access behind object_lock
- plumb a DOE/SPDM worker plus shared helpers that submit the SMCCC call,
  cache multi-part responses, and handle retries/abort

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  20 ++
 arch/arm64/include/asm/rmi_smc.h         |  60 +++++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  50 ++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 276 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  65 ++++++
 5 files changed, 471 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index d23a0590c7ee..6664c439173f 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -736,4 +736,24 @@ static inline unsigned long rmi_pdev_get_state(unsigned long pdev_phys, enum rmi
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
+static inline unsigned long rmi_pdev_abort(unsigned long pdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_ABORT, pdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 94bcaf3e7e68..9056a7639667 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -478,4 +478,64 @@ struct rmi_pdev_params {
 	};
 };
 
+#define RMI_DEV_COMM_EXIT_CACHE_REQ	BIT(0)
+#define RMI_DEV_COMM_EXIT_CACHE_RSP	BIT(1)
+#define RMI_DEV_COMM_EXIT_SEND		BIT(2)
+#define RMI_DEV_COMM_EXIT_WAIT		BIT(3)
+#define RMI_DEV_COMM_EXIT_RSP_RESET	BIT(4)
+#define RMI_DEV_COMM_EXIT_MULTI		BIT(5)
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
+	union {
+		u8 status;
+		u64 padding0;
+	};
+	u64 req_addr;
+	u64 resp_addr;
+	u64 resp_len;
+};
+
+struct rmi_dev_comm_exit {
+	u64 flags;
+	u64 req_cache_offset;
+	u64 req_cache_len;
+	u64 rsp_cache_offset;
+	u64 rsp_cache_len;
+	union {
+		u8 cache_obj_id;
+		u64 padding0;
+	};
+
+	union {
+		u8 protocol;
+		u64 padding1;
+	};
+	u64 req_delay;
+	u64 req_len;
+	u64 rsp_timeout;
+};
+
+struct rmi_dev_comm_data {
+	union { /* 0x0 */
+		struct rmi_dev_comm_enter enter;
+		u8 padding0[0x800];
+	};
+	union { /* 0x800 */
+		struct rmi_dev_comm_exit exit;
+		u8 padding1[0x800];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 67f7e80106e8..3c854aab95cc 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -46,6 +46,7 @@ static struct pci_tsm *cca_tsm_pci_probe(struct tsm_dev *tsm_dev, struct pci_dev
 	ret = pci_tsm_pf0_constructor(pdev, &pf0_ep_dsc->pci, tsm_dev);
 	if (ret)
 		return NULL;
+	mutex_init(&pf0_ep_dsc->pdev.object_lock);
 
 	pci_dbg(pdev, "tsm enabled\n");
 	return &no_free_ptr(pf0_ep_dsc)->pci.base_tsm;
@@ -65,6 +66,55 @@ static void cca_tsm_pci_remove(struct pci_tsm *tsm)
 	}
 }
 
+static __maybe_unused int init_dev_communication_buffers(struct pci_dev *pdev,
+		struct cca_host_comm_data *comm_data)
+{
+	int ret = -ENOMEM;
+
+	comm_data->io_params = (struct rmi_dev_comm_data *)get_zeroed_page(GFP_KERNEL);
+	if (!comm_data->io_params)
+		goto err_out;
+
+	comm_data->rsp_buff = (void *)__get_free_page(GFP_KERNEL);
+	if (!comm_data->rsp_buff)
+		goto err_res_buff;
+
+	comm_data->req_buff = (void *)__get_free_page(GFP_KERNEL);
+	if (!comm_data->req_buff)
+		goto err_req_buff;
+
+	comm_data->work_queue = alloc_ordered_workqueue("%s %s DEV_COMM", 0,
+						dev_bus_name(&pdev->dev),
+						pci_name(pdev));
+	if (!comm_data->work_queue)
+		goto err_work_queue;
+
+	comm_data->io_params->enter.status = RMI_DEV_COMM_NONE;
+	comm_data->io_params->enter.resp_addr = virt_to_phys(comm_data->rsp_buff);
+	comm_data->io_params->enter.req_addr  = virt_to_phys(comm_data->req_buff);
+	comm_data->io_params->enter.resp_len = 0;
+
+	return 0;
+
+err_work_queue:
+	free_page((unsigned long)comm_data->req_buff);
+err_req_buff:
+	free_page((unsigned long)comm_data->rsp_buff);
+err_res_buff:
+	free_page((unsigned long)comm_data->io_params);
+err_out:
+	return ret;
+}
+
+static inline void free_dev_communication_buffers(struct cca_host_comm_data *comm_data)
+{
+	destroy_workqueue(comm_data->work_queue);
+
+	free_page((unsigned long)comm_data->req_buff);
+	free_page((unsigned long)comm_data->rsp_buff);
+	free_page((unsigned long)comm_data->io_params);
+}
+
 /* For now global for simplicity. Protected by pci_tsm_rwsem */
 static DECLARE_BITMAP(cca_stream_ids, MAX_STREAM_ID);
 static int alloc_stream_id(struct pci_host_bridge *hb)
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 8fb5d286fd82..dc159d9f2c24 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -5,6 +5,8 @@
 
 #include <linux/pci.h>
 #include <linux/pci-ecam.h>
+#include <linux/pci-doe.h>
+#include <linux/delay.h>
 #include <asm/rmi_cmds.h>
 
 #include "rmi-da.h"
@@ -149,3 +151,277 @@ int cca_pdev_create(struct pci_dev *pci_dev)
 		free_page((unsigned long)rmm_pdev);
 	return ret;
 }
+
+static int doe_send_req_resp(struct pci_tsm *tsm)
+{
+	int data_obj_type;
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(tsm->pdev);
+	struct rmi_dev_comm_exit *io_exit = &comm_data->io_params->exit;
+	u8 protocol = io_exit->protocol;
+
+	if (protocol == RMI_PROTOCOL_SPDM)
+		data_obj_type = PCI_DOE_FEATURE_CMA;
+	else if (protocol == RMI_PROTOCOL_SECURE_SPDM)
+		data_obj_type = PCI_DOE_FEATURE_SSESSION;
+	else
+		return -EINVAL;
+
+	/* delay the send */
+	if (io_exit->req_delay)
+		fsleep(io_exit->req_delay);
+
+	return pci_tsm_doe_transfer(tsm->dsm_dev, data_obj_type,
+				    comm_data->req_buff, io_exit->req_len,
+				    comm_data->rsp_buff, PAGE_SIZE);
+}
+
+static inline bool pending_dev_communicate(struct rmi_dev_comm_exit *io_exit)
+{
+	bool pending = io_exit->flags & (RMI_DEV_COMM_EXIT_CACHE_REQ |
+					 RMI_DEV_COMM_EXIT_CACHE_RSP |
+					 RMI_DEV_COMM_EXIT_SEND |
+					 RMI_DEV_COMM_EXIT_WAIT |
+					 RMI_DEV_COMM_EXIT_MULTI);
+	return pending;
+}
+
+static inline gfp_t cache_obj_id_to_gfp_flags(u8 cache_obj_id)
+{
+	/* These two cache objects are system objects. */
+	if (cache_obj_id == RMI_DEV_VCA || cache_obj_id == RMI_DEV_CERTIFICATE)
+		return GFP_KERNEL;
+	/* rest are per TDI which is associated to a VM */
+	return GFP_KERNEL_ACCOUNT;
+}
+
+static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
+{
+	unsigned long rmi_ret;
+	gfp_t cache_alloc_flags;
+	int nbytes, cp_len;
+	struct cache_object **cache_objp, *cache_obj;
+	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(tsm->pdev);
+	struct rmi_dev_comm_enter *io_enter = &comm_data->io_params->enter;
+	struct rmi_dev_comm_exit *io_exit = &comm_data->io_params->exit;
+
+redo_communicate:
+
+	if (type == PDEV_COMMUNICATE)
+		rmi_ret = rmi_pdev_communicate(virt_to_phys(pdev_dsc->rmm_pdev),
+					       virt_to_phys(comm_data->io_params));
+	else
+		rmi_ret = RMI_ERROR_INPUT;
+	if (rmi_ret != RMI_SUCCESS) {
+		if (rmi_ret == RMI_BUSY)
+			return -EBUSY;
+		return -EIO;
+	}
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_REQ ||
+	    io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_RSP) {
+		struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(tsm->dsm_dev);
+
+		if (!pf0_ep_dsc) {
+			WARN(1,
+			     "Device communication got cache request on wrong device\n");
+			return -EINVAL;
+		}
+
+		switch (io_exit->cache_obj_id) {
+		case RMI_DEV_VCA:
+			cache_objp = &pf0_ep_dsc->vca;
+			break;
+		case RMI_DEV_CERTIFICATE:
+			cache_objp = &pf0_ep_dsc->cert_chain.cache;
+			break;
+		default:
+			return -EINVAL;
+		}
+		cache_obj = *cache_objp;
+		cache_alloc_flags = cache_obj_id_to_gfp_flags(io_exit->cache_obj_id);
+		int cache_remaining;
+
+		if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_REQ)
+			cp_len = io_exit->req_cache_len;
+		else
+			cp_len = io_exit->rsp_cache_len;
+
+		/* response and request len should be <= SZ_4k */
+		if (cp_len > CACHE_CHUNK_SIZE)
+			return -EINVAL;
+
+		/* new allocation */
+		if (!cache_obj) {
+			int obj_size = struct_size(cache_obj, buf,
+						   CACHE_CHUNK_SIZE);
+
+			cache_obj = kvmalloc(obj_size, cache_alloc_flags);
+			if (!cache_obj)
+				return -ENOMEM;
+
+			cache_obj->size = CACHE_CHUNK_SIZE;
+			cache_obj->offset = 0;
+			*cache_objp = cache_obj;
+		}
+
+		cache_remaining = cache_obj->size - cache_obj->offset;
+		if (cp_len > cache_remaining) {
+			struct cache_object *new_obj;
+			int new_size = struct_size(cache_obj, buf,
+						   cache_obj->size +
+						   CACHE_CHUNK_SIZE);
+
+			if (cache_obj->size + CACHE_CHUNK_SIZE > MAX_CACHE_OBJ_SIZE)
+				return -EINVAL;
+
+			new_obj = kvrealloc(cache_obj, new_size, cache_alloc_flags);
+			if (!new_obj)
+				return -ENOMEM;
+			new_obj->size = cache_obj->size + CACHE_CHUNK_SIZE;
+			*cache_objp = new_obj;
+		}
+
+		/* cache object can change above. */
+		cache_obj = *cache_objp;
+	}
+
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_REQ) {
+		memcpy(cache_obj->buf + cache_obj->offset,
+		       (comm_data->req_buff + io_exit->req_cache_offset), io_exit->req_cache_len);
+		cache_obj->offset += io_exit->req_cache_len;
+	}
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_RSP) {
+		memcpy(cache_obj->buf + cache_obj->offset,
+		       (comm_data->rsp_buff + io_exit->rsp_cache_offset), io_exit->rsp_cache_len);
+		cache_obj->offset += io_exit->rsp_cache_len;
+	}
+
+	/*
+	 * wait for last packet request from RMM.
+	 * We should not find this because our device communication is synchronous
+	 */
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_WAIT)
+		return -EIO;
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
+		io_enter->status = RMI_DEV_COMM_NONE;
+	}
+
+	if (pending_dev_communicate(io_exit))
+		goto redo_communicate;
+
+	return 0;
+}
+
+static int do_dev_communicate(enum dev_comm_type type,
+		struct pci_tsm *tsm, unsigned long error_state)
+{
+	int ret, state = error_state;
+	struct rmi_dev_comm_enter *io_enter;
+	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+
+	io_enter = &pdev_dsc->comm_data.io_params->enter;
+	io_enter->resp_len = 0;
+	io_enter->status = RMI_DEV_COMM_NONE;
+
+	ret = _do_dev_communicate(type, tsm);
+	if (ret) {
+		if (type == PDEV_COMMUNICATE)
+			rmi_pdev_abort(virt_to_phys(pdev_dsc->rmm_pdev));
+	} else {
+		/*
+		 * Some device communication error will transition the
+		 * device to error state. Report that.
+		 */
+		if (type == PDEV_COMMUNICATE) {
+			if (rmi_pdev_get_state(virt_to_phys(pdev_dsc->rmm_pdev),
+					       (enum rmi_pdev_state *)&state))
+				state = error_state;
+		}
+	}
+
+	if (state == error_state)
+		pci_err(tsm->pdev, "device communication error\n");
+
+	return state;
+}
+
+static int wait_for_dev_state(enum dev_comm_type type, struct pci_tsm *tsm,
+		unsigned long target_state, unsigned long error_state)
+{
+	int state;
+
+	do {
+		state = do_dev_communicate(type, tsm, error_state);
+
+		if (state == target_state || state == error_state)
+			return state;
+	} while (1);
+
+	/* can't reach */
+	return error_state;
+}
+
+static int wait_for_pdev_state(struct pci_tsm *tsm, enum rmi_pdev_state target_state)
+{
+	return wait_for_dev_state(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
+}
+
+static void pdev_state_transition_workfn(struct work_struct *work)
+{
+	unsigned long state;
+	struct pci_tsm *tsm;
+	struct dev_comm_work *setup_work;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+	pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+
+	guard(mutex)(&pdev_dsc->object_lock);
+	state = wait_for_pdev_state(tsm, setup_work->target_state);
+	WARN_ON(state != setup_work->target_state);
+}
+
+static int __maybe_unused submit_pdev_state_transition_work(struct pci_dev *pdev,
+		enum rmi_pdev_state target_state)
+{
+	enum rmi_pdev_state state;
+	struct dev_comm_work comm_work;
+	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(pdev);
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
+
+	INIT_WORK_ONSTACK(&comm_work.work, pdev_state_transition_workfn);
+	comm_work.tsm = pdev->tsm;
+	comm_work.target_state = target_state;
+
+	queue_work(comm_data->work_queue, &comm_work.work);
+
+	flush_work(&comm_work.work);
+	destroy_work_on_stack(&comm_work.work);
+
+	/* check if we reached target state */
+	if (rmi_pdev_get_state(virt_to_phys(pdev_dsc->rmm_pdev), &state))
+		return -EIO;
+
+	if (state != target_state)
+		/* no specific error for this */
+		return -1;
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index de67f10ce20e..9f72ff8f28bf 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -9,15 +9,46 @@
 #include <linux/pci.h>
 #include <linux/pci-ide.h>
 #include <linux/pci-tsm.h>
+#include <linux/sizes.h>
 #include <asm/rmi_cmds.h>
 #include <asm/rmi_smc.h>
 
+#define MAX_CACHE_OBJ_SIZE	SZ_16M
+#define CACHE_CHUNK_SIZE	SZ_4K
+struct cache_object {
+	int size;
+	int offset;
+	u8 buf[] __counted_by(size);
+};
+
+struct dev_comm_work {
+	struct pci_tsm *tsm;
+	int target_state;
+	struct work_struct work;
+};
+
+struct cca_host_comm_data {
+	void *rsp_buff;
+	void *req_buff;
+	struct rmi_dev_comm_data *io_params;
+	/*
+	 * Only one device communication request can be active at
+	 * a time. This limitation comes from using the DOE mailbox
+	 * at the pdev level. Requests such as get_measurements may
+	 * span multiple mailbox messages, which must not be
+	 * interleaved with other SPDM requests.
+	 */
+	struct workqueue_struct *work_queue;
+};
+
 /**
  * struct cca_host_pdev_dsc - Common RMM pdev context
+ * @comm_data: Shared device communication state for the DSM-owned pdev
  * @rmm_pdev: Delegated page backing the RMM pdev object
  * @object_lock: Serializes access to the RMM pdev object and PF0/TDI caches
  */
 struct cca_host_pdev_dsc {
+	struct cca_host_comm_data comm_data;
 	void *rmm_pdev;
 	/* lock kept here to simplify the generic lock/unlock paths. */
 	struct mutex object_lock;
@@ -28,17 +59,33 @@ struct cca_host_pdev_dsc {
  * @pci: Physical Function 0 TDISP link context
  * @pdev: pdev communication context
  * @sel_stream: Selective IDE Stream descriptor
+ * @cert_chain: cetrificate chain
+ * @vca: SPDM's Version-Capabilities-Algorithms cache object
  */
 struct cca_host_pf0_ep_dsc {
 	struct pci_tsm_pf0 pci;
 	struct cca_host_pdev_dsc pdev;
 	struct pci_ide *sel_stream;
+
+	struct {
+		struct cache_object *cache;
+
+		void *public_key;
+		size_t public_key_size;
+
+		bool valid;
+	} cert_chain;
+	struct cache_object *vca;
 };
 
 struct cca_host_fn_dsc {
 	struct pci_tsm pci;
 };
 
+enum dev_comm_type {
+	PDEV_COMMUNICATE = 0x1,
+};
+
 static inline struct cca_host_pf0_ep_dsc *to_cca_pf0_ep_dsc(struct pci_dev *pdev)
 {
 	struct pci_tsm *tsm = pdev->tsm;
@@ -67,6 +114,24 @@ static inline struct cca_host_pdev_dsc *to_cca_pdev_dsc(struct pci_dev *pdev)
 	return NULL;
 }
 
+static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
+{
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	pdev_dsc = to_cca_pdev_dsc(pdev);
+	if (pdev_dsc)
+		return &pdev_dsc->comm_data;
+
+	if (!pdev->tsm || !pdev->tsm->dsm_dev)
+		return NULL;
+
+	pdev_dsc = to_cca_pdev_dsc(pdev->tsm->dsm_dev);
+	if (pdev_dsc)
+		return &pdev_dsc->comm_data;
+
+	return NULL;
+}
+
 int cca_pdev_create(struct pci_dev *pdev);
 
 #endif

---

## [5] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 04/14] coco: host: arm64: Add helper to stop and tear down an RMM pdev*

Add helper to stop and tear down an RMM pdev
- describe the RMI_PDEV_STOP/RMI_PDEV_DESTROY SMC IDs and provide
  wrappers in rmi_cmds.h
- implement pdev_stop_and_destroy() so the host driver stops the pdev,
  waits for it to reach RMI_PDEV_STOPPED and destroys it

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       |  9 +++++
 drivers/virt/coco/arm-cca-host/rmi-da.c | 47 ++++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h |  1 +
 3 files changed, 56 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 6664c439173f..8024e9d89e55 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -756,4 +756,13 @@ static inline unsigned long rmi_pdev_abort(unsigned long pdev_phys)
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
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index dc159d9f2c24..8a43a1f1c036 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -399,7 +399,7 @@ static void pdev_state_transition_workfn(struct work_struct *work)
 	WARN_ON(state != setup_work->target_state);
 }
 
-static int __maybe_unused submit_pdev_state_transition_work(struct pci_dev *pdev,
+static int submit_pdev_state_transition_work(struct pci_dev *pdev,
 		enum rmi_pdev_state target_state)
 {
 	enum rmi_pdev_state state;
@@ -425,3 +425,48 @@ static int __maybe_unused submit_pdev_state_transition_work(struct pci_dev *pdev
 		return -1;
 	return 0;
 }
+
+static inline int rmi_pdev_destroy(unsigned long pdev_phys,
+			   unsigned long *rmi_ret)
+{
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_PDEV_DESTROY, pdev_phys);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+
+	return 0;
+}
+
+void cca_pdev_stop_and_destroy(struct pci_dev *pdev)
+{
+	int ret;
+	unsigned long rmi_ret;
+	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(pdev);
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+	phys_addr_t rmm_pdev_phys = virt_to_phys(pdev_dsc->rmm_pdev);
+
+	if (WARN_ON(rmi_pdev_stop(rmm_pdev_phys)))
+		return;
+
+	ret = submit_pdev_state_transition_work(pdev, RMI_PDEV_STOPPED);
+	if (ret)
+		return;
+
+	ret = rmi_pdev_destroy(rmm_pdev_phys, &rmi_ret);
+	if (WARN_ON(ret || rmi_ret))
+		return;
+
+	if (pf0_ep_dsc) {
+		kfree(pf0_ep_dsc->cert_chain.public_key);
+		kvfree(pf0_ep_dsc->cert_chain.cache);
+		kvfree(pf0_ep_dsc->vca);
+		pf0_ep_dsc->cert_chain.cache = NULL;
+		pf0_ep_dsc->vca = NULL;
+	}
+
+	if (!rmi_undelegate_page(rmm_pdev_phys))
+		free_page((unsigned long)pdev_dsc->rmm_pdev);
+	pdev_dsc->rmm_pdev = NULL;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 9f72ff8f28bf..784eb1fff95d 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -133,5 +133,6 @@ static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
 }
 
 int cca_pdev_create(struct pci_dev *pdev);
+void cca_pdev_stop_and_destroy(struct pci_dev *pdev);
 
 #endif

---

## [6] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 05/14] X.509: Make certificate parser public*

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
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 crypto/asymmetric_keys/x509_parser.h | 42 +--------------------
 include/keys/x509-parser.h           | 55 ++++++++++++++++++++++++++++
 2 files changed, 56 insertions(+), 41 deletions(-)
 create mode 100644 include/keys/x509-parser.h

diff --git a/crypto/asymmetric_keys/x509_parser.h b/crypto/asymmetric_keys/x509_parser.h
index b7aeebdddb36..39f1521b773d 100644
--- a/crypto/asymmetric_keys/x509_parser.h
+++ b/crypto/asymmetric_keys/x509_parser.h
@@ -5,51 +5,11 @@
  * Written by David Howells (dhowells@redhat.com)
  */
 
-#include <linux/cleanup.h>
-#include <linux/time.h>
-#include <crypto/public_key.h>
-#include <keys/asymmetric-type.h>
-#include <crypto/sha2.h>
-
-struct x509_certificate {
-	struct x509_certificate *next;
-	struct x509_certificate *signer;	/* Certificate that signed this one */
-	struct public_key *pub;			/* Public key details */
-	struct public_key_signature *sig;	/* Signature parameters */
-	u8		sha256[SHA256_DIGEST_SIZE]; /* Hash for blacklist purposes */
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
index 000000000000..8b68e720693a
--- /dev/null
+++ b/include/keys/x509-parser.h
@@ -0,0 +1,55 @@
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
+#include <linux/cleanup.h>
+#include <linux/time.h>
+#include <crypto/public_key.h>
+#include <keys/asymmetric-type.h>
+#include <crypto/sha2.h>
+
+struct x509_certificate {
+	struct x509_certificate *next;
+	struct x509_certificate *signer;	/* Certificate that signed this one */
+	struct public_key *pub;			/* Public key details */
+	struct public_key_signature *sig;	/* Signature parameters */
+	u8		sha256[SHA256_DIGEST_SIZE]; /* Hash for blacklist purposes */
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

## [7] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 06/14] X.509: Parse Subject Alternative Name in certificates*

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
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 crypto/asymmetric_keys/x509_cert_parser.c | 9 +++++++++
 include/keys/x509-parser.h                | 2 ++
 2 files changed, 11 insertions(+)

diff --git a/crypto/asymmetric_keys/x509_cert_parser.c b/crypto/asymmetric_keys/x509_cert_parser.c
index 37e4fb9da106..d81b7de4236c 100644
--- a/crypto/asymmetric_keys/x509_cert_parser.c
+++ b/crypto/asymmetric_keys/x509_cert_parser.c
@@ -596,6 +596,15 @@ int x509_process_extension(void *context, size_t hdrlen,
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
index 8b68e720693a..4e6a05a8c7a6 100644
--- a/include/keys/x509-parser.h
+++ b/include/keys/x509-parser.h
@@ -38,6 +38,8 @@ struct x509_certificate {
 	unsigned	raw_subject_size;
 	unsigned	raw_skid_size;
 	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
+	const void	*raw_san;		/* Raw subjectAltName in ASN.1 */
+	unsigned	raw_san_size;
 	unsigned	index;
 	bool		seen;			/* Infinite recursion prevention */
 	bool		verified;

---

## [8] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 07/14] X.509: Move certificate length retrieval into new helper*

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
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
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
index 1b91c8f98688..301efa952e26 100644
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

## [9] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 08/14] coco: host: arm64: Register device public key with RMM*

- Introduce the SMC_RMI_PDEV_SET_PUBKEY helper and the associated struct
rmi_public_key_params so the host can hand the device’s public key to
the RMM.

- Parse the certificate chain cached during SPDM session setup, extract the
final certificate’s public key, and recognise RSA-3072, ECDSA-P256, and
ECDSA-P384 keys before calling into the RMM.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       |   9 ++
 arch/arm64/include/asm/rmi_smc.h        |  17 +++
 drivers/virt/coco/arm-cca-host/Kconfig  |   4 +
 drivers/virt/coco/arm-cca-host/rmi-da.c | 155 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h |   2 +
 5 files changed, 187 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 8024e9d89e55..00e0a08e17a6 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -765,4 +765,13 @@ static inline unsigned long rmi_pdev_stop(unsigned long pdev_phys)
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
index 9056a7639667..7a5d57a8be7a 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -538,4 +538,21 @@ struct rmi_dev_comm_data {
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
+		};
+		u8 padding[0x1000];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
index efe40d61d5d8..c5076e2b4eb5 100644
--- a/drivers/virt/coco/arm-cca-host/Kconfig
+++ b/drivers/virt/coco/arm-cca-host/Kconfig
@@ -8,7 +8,11 @@ config ARM_CCA_HOST
 	depends on PCI
 	depends on KVM
 	select PCI_TSM
+	select KEYS
+	select X509_CERTIFICATE_PARSER
 	select AUXILIARY_BUS
+	select CRYPTO_ECDSA
+	select CRYPTO_RSA
 
 	help
 	  ARM CCA RMM firmware is the trusted runtime that enforces memory
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 8a43a1f1c036..996979dba709 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -8,6 +8,9 @@
 #include <linux/pci-doe.h>
 #include <linux/delay.h>
 #include <asm/rmi_cmds.h>
+#include <crypto/internal/rsa.h>
+#include <keys/asymmetric-type.h>
+#include <keys/x509-parser.h>
 
 #include "rmi-da.h"
 
@@ -383,6 +386,158 @@ static int wait_for_pdev_state(struct pci_tsm *tsm, enum rmi_pdev_state target_s
 	return wait_for_dev_state(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
 }
 
+static int __maybe_unused parse_certificate_chain(struct pci_tsm *tsm)
+{
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+	unsigned int chain_size;
+	unsigned int offset = 0;
+	u8 *chain_data;
+
+	pf0_ep_dsc = to_cca_pf0_ep_dsc(tsm->pdev);
+
+	/* If device communication didn't results in certificate caching. */
+	if (!pf0_ep_dsc->cert_chain.cache || !pf0_ep_dsc->cert_chain.cache->offset)
+		return -EINVAL;
+
+	chain_size = pf0_ep_dsc->cert_chain.cache->offset;
+	chain_data = pf0_ep_dsc->cert_chain.cache->buf;
+
+	while (offset < chain_size) {
+		ssize_t cert_len =
+			x509_get_certificate_length(chain_data + offset,
+						    chain_size - offset);
+		if (cert_len < 0)
+			return cert_len;
+
+		struct x509_certificate *cert __free(x509_free_certificate) =
+			x509_cert_parse(chain_data + offset, cert_len);
+
+		if (IS_ERR(cert)) {
+			pci_warn(tsm->pdev, "parsing of certificate chain not successful\n");
+			return PTR_ERR(cert);
+		}
+
+		/* The key in the last cert in the chain is used */
+		if (offset + cert_len == chain_size) {
+			void *public_key __free(kfree) =
+				kzalloc(cert->pub->keylen, GFP_KERNEL);
+
+			if (!public_key)
+				return -ENOMEM;
+
+			if (!strcmp("ecdsa-nist-p256", cert->pub->pkey_algo)) {
+				pf0_ep_dsc->rmi_signature_algorithm = RMI_SIG_ECDSA_P256;
+			} else if (!strcmp("ecdsa-nist-p384", cert->pub->pkey_algo)) {
+				pf0_ep_dsc->rmi_signature_algorithm = RMI_SIG_ECDSA_P384;
+			} else if (!strcmp("rsa", cert->pub->pkey_algo)) {
+				struct rsa_key rsa_key = {0};
+				size_t skip = 0;
+				int ret;
+
+				ret = rsa_parse_pub_key(&rsa_key, cert->pub->key,
+							cert->pub->keylen);
+				if (ret)
+					return ret;
+
+				while (skip < rsa_key.n_sz && !rsa_key.n[skip])
+					skip++;
+
+				/* check we have 3072 bits len */
+				if ((rsa_key.n_sz - skip) != (3072 >> 3))
+					return -EINVAL;
+
+				pf0_ep_dsc->rmi_signature_algorithm = RMI_SIG_RSASSA_3072;
+			} else {
+				return -EINVAL;
+			}
+
+			memcpy(public_key, cert->pub->key, cert->pub->keylen);
+			pf0_ep_dsc->cert_chain.public_key = no_free_ptr(public_key);
+			pf0_ep_dsc->cert_chain.public_key_size = cert->pub->keylen;
+			pf0_ep_dsc->cert_chain.valid = true;
+			return 0;
+		}
+
+		offset += cert_len;
+	}
+
+	/* something wrong with chain size and parsing. */
+	return -EINVAL;
+}
+
+static inline void key_param_free(struct rmi_public_key_params *param)
+{
+	return free_page((unsigned long)param);
+}
+
+static inline int copy_key_part(u8 *buf, const u8 *key_buf, size_t sz)
+{
+	int skip;
+
+	/* skip leading zero in asn.1 */
+	for (skip = 0; skip < sz; skip++)
+		if (key_buf[skip])
+			break;
+
+	memcpy(buf, key_buf + skip, sz - skip);
+	return sz - skip;
+}
+
+DEFINE_FREE(key_param_free, struct rmi_public_key_params *, if (_T) key_param_free(_T))
+static int __maybe_unused pdev_set_public_key(struct pci_tsm *tsm)
+{
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+
+	pf0_ep_dsc = to_cca_pf0_ep_dsc(tsm->pdev);
+	/* Check that all the necessary information was captured from communication */
+	if (!pf0_ep_dsc->cert_chain.valid)
+		return -EINVAL;
+
+	struct rmi_public_key_params *key_params __free(key_param_free) =
+		(struct rmi_public_key_params *)get_zeroed_page(GFP_KERNEL);
+	if (!key_params)
+		return -ENOMEM;
+
+	key_params->rmi_signature_algorithm = pf0_ep_dsc->rmi_signature_algorithm;
+
+	switch (key_params->rmi_signature_algorithm) {
+	case RMI_SIG_ECDSA_P384:
+	case RMI_SIG_ECDSA_P256:
+	{
+		key_params->public_key_len = pf0_ep_dsc->cert_chain.public_key_size;
+		memcpy(key_params->public_key,
+		       pf0_ep_dsc->cert_chain.public_key,
+		       pf0_ep_dsc->cert_chain.public_key_size);
+		key_params->metadata_len = 0;
+		break;
+	}
+	case RMI_SIG_RSASSA_3072:
+	{
+		int ret;
+		struct rsa_key rsa_key = {0};
+
+		ret = rsa_parse_pub_key(&rsa_key,
+					pf0_ep_dsc->cert_chain.public_key,
+					pf0_ep_dsc->cert_chain.public_key_size);
+		if (ret)
+			return ret;
+
+		key_params->public_key_len = copy_key_part(key_params->public_key,
+							   rsa_key.n, rsa_key.n_sz);
+		key_params->metadata_len = copy_key_part(key_params->metadata,
+							 rsa_key.e, rsa_key.e_sz);
+		break;
+	}
+	default:
+		return -EINVAL;
+	}
+
+	if (rmi_pdev_set_pubkey(virt_to_phys(pf0_ep_dsc->pdev.rmm_pdev),
+				virt_to_phys(key_params)))
+		return -ENXIO;
+	return 0;
+}
+
 static void pdev_state_transition_workfn(struct work_struct *work)
 {
 	unsigned long state;
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 784eb1fff95d..7d38e548b659 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -59,6 +59,7 @@ struct cca_host_pdev_dsc {
  * @pci: Physical Function 0 TDISP link context
  * @pdev: pdev communication context
  * @sel_stream: Selective IDE Stream descriptor
+ * @rmi_signature_algorithm: Signature algorithm used for public key
  * @cert_chain: cetrificate chain
  * @vca: SPDM's Version-Capabilities-Algorithms cache object
  */
@@ -67,6 +68,7 @@ struct cca_host_pf0_ep_dsc {
 	struct cca_host_pdev_dsc pdev;
 	struct pci_ide *sel_stream;
 
+	uint8_t rmi_signature_algorithm;
 	struct {
 		struct cache_object *cache;

---

## [10] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 09/14] coco: host: arm64: Initialize RMM pdev state for TDISP IDE connect*

Update connect() to:
- allocate device-communication buffers,
- create the RMM pdev object,
- perform initial device communication to collect identity, and
- set the device public key when the pdev enters NEEDS_KEY.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-host/arm-cca.c | 43 +++++++++--
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 92 +++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  3 +
 3 files changed, 128 insertions(+), 10 deletions(-)

diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 3c854aab95cc..f0aa4e46e96c 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -66,7 +66,7 @@ static void cca_tsm_pci_remove(struct pci_tsm *tsm)
 	}
 }
 
-static __maybe_unused int init_dev_communication_buffers(struct pci_dev *pdev,
+static int init_dev_communication_buffers(struct pci_dev *pdev,
 		struct cca_host_comm_data *comm_data)
 {
 	int ret = -ENOMEM;
@@ -184,15 +184,40 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 		ret = tsm_ide_stream_register(ide);
 		if (ret)
 			goto err_tsm;
+	}
 
-		/*
-		 * Once ide is setup, enable the stream at the endpoint
-		 * Root port will be done by RMM
-		 */
-		pci_ide_stream_enable(pdev, ide);
+	ret = init_dev_communication_buffers(pdev, &pf0_ep_dsc->pdev.comm_data);
+	if (ret)
+		goto err_comm_buff;
+	ret = cca_pdev_create(pdev);
+	if (ret)
+		goto err_pdev_create;
+
+	ret = cca_pdev_collect_identity(pdev);
+	if (ret)
+		goto pdev_destroy;
+
+	if (cca_pdev_needs_key(pdev)) {
+		ret = cca_pdev_set_public_key(pdev);
+		if (ret)
+			goto pdev_destroy;
 	}
+	/*
+	 * Once ide is setup, enable the stream at the endpoint
+	 * Root port will be done by RMM
+	 */
+	if (cca_pdev_need_sel_ide_streams(pdev))
+		pci_ide_stream_enable(pdev, ide);
+
 	return 0;
 
+pdev_destroy:
+	cca_pdev_stop_and_destroy(pdev);
+err_pdev_create:
+	free_dev_communication_buffers(&pf0_ep_dsc->pdev.comm_data);
+err_comm_buff:
+	if (cca_pdev_need_sel_ide_streams(pdev))
+		tsm_ide_stream_unregister(ide);
 err_tsm:
 	if (cca_pdev_need_sel_ide_streams(pdev)) {
 		pci_ide_stream_teardown(rp, ide);
@@ -222,12 +247,16 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	if (cca_pdev_need_sel_ide_streams(pdev)) {
 		ide = pf0_ep_dsc->sel_stream;
 		stream_id = ide->stream_id;
+	}
+
+	cca_pdev_stop_and_destroy(pdev);
+	free_dev_communication_buffers(&pf0_ep_dsc->pdev.comm_data);
 
+	if (cca_pdev_need_sel_ide_streams(pdev)) {
 		pci_ide_stream_release(ide);
 		pf0_ep_dsc->sel_stream = NULL;
 		clear_bit(stream_id, cca_stream_ids);
 	}
-
 }
 
 static struct pci_tsm_ops cca_link_pci_ops = {
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 996979dba709..cb654d1b2eb3 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -386,7 +386,7 @@ static int wait_for_pdev_state(struct pci_tsm *tsm, enum rmi_pdev_state target_s
 	return wait_for_dev_state(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
 }
 
-static int __maybe_unused parse_certificate_chain(struct pci_tsm *tsm)
+static int parse_certificate_chain(struct pci_tsm *tsm)
 {
 	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
 	unsigned int chain_size;
@@ -484,7 +484,7 @@ static inline int copy_key_part(u8 *buf, const u8 *key_buf, size_t sz)
 }
 
 DEFINE_FREE(key_param_free, struct rmi_public_key_params *, if (_T) key_param_free(_T))
-static int __maybe_unused pdev_set_public_key(struct pci_tsm *tsm)
+static int pdev_set_public_key(struct pci_tsm *tsm)
 {
 	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
 
@@ -581,8 +581,94 @@ static int submit_pdev_state_transition_work(struct pci_dev *pdev,
 	return 0;
 }
 
+static void pdev_collect_identity_workfn(struct work_struct *work)
+{
+	struct pci_tsm *tsm;
+	struct dev_comm_work *setup_work;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+	pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+
+	guard(mutex)(&pdev_dsc->object_lock);
+
+	do_dev_communicate(PDEV_COMMUNICATE, tsm, RMI_PDEV_ERROR);
+
+	/*
+	 * Don't worry about communication error. The caller will look at
+	 * device state to find more about error
+	 */
+}
+
+int cca_pdev_collect_identity(struct pci_dev *pdev)
+{
+	enum rmi_pdev_state state;
+	struct dev_comm_work comm_work;
+	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(pdev);
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
+
+	/*
+	 * Device identity is collected by doing a device communication
+	 * after a pdev_create
+	 */
+	INIT_WORK_ONSTACK(&comm_work.work, pdev_collect_identity_workfn);
+	comm_work.tsm = pdev->tsm;
+
+	queue_work(comm_data->work_queue, &comm_work.work);
+
+	flush_work(&comm_work.work);
+	destroy_work_on_stack(&comm_work.work);
+
+	/* check for device communication error*/
+	if (rmi_pdev_get_state(virt_to_phys(pdev_dsc->rmm_pdev), &state))
+		return -EIO;
+
+	if (state == RMI_PDEV_ERROR)
+		return -EPROTO;
+
+	return 0;
+}
+
+bool cca_pdev_needs_key(struct pci_dev *pdev)
+{
+	enum rmi_pdev_state state;
+	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(pdev);
+
+	/*
+	 * Consider pdev_get_state failure as need key transition
+	 * and that will result in device communication failure, which
+	 * will handle this error.
+	 */
+	if (rmi_pdev_get_state(virt_to_phys(pdev_dsc->rmm_pdev), &state))
+		return true;
+
+	if (state == RMI_PDEV_NEEDS_KEY)
+		return true;
+	return false;
+}
+
+int cca_pdev_set_public_key(struct pci_dev *pdev)
+{
+	int ret;
+
+	/*
+	 * we now have certificate chain in dsm->cert_chain. Parse that and set
+	 * the pubkey.
+	 */
+	ret = parse_certificate_chain(pdev->tsm);
+	if (ret)
+		return ret;
+
+	ret = pdev_set_public_key(pdev->tsm);
+	if (ret)
+		return ret;
+
+	return submit_pdev_state_transition_work(pdev, RMI_PDEV_READY);
+}
+
 static inline int rmi_pdev_destroy(unsigned long pdev_phys,
-			   unsigned long *rmi_ret)
+		unsigned long *rmi_ret)
 {
 	struct rmi_sro_state *sro __free(sro) =
 		rmi_sro_init(SMC_RMI_PDEV_DESTROY, pdev_phys);
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 7d38e548b659..240b2993ae53 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -135,6 +135,9 @@ static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
 }
 
 int cca_pdev_create(struct pci_dev *pdev);
+int cca_pdev_collect_identity(struct pci_dev *pdev);
+bool cca_pdev_needs_key(struct pci_dev *pdev);
+int cca_pdev_set_public_key(struct pci_dev *pdev);
 void cca_pdev_stop_and_destroy(struct pci_dev *pdev);
 
 #endif

---

## [11] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 10/14] coco: host: arm64: Coordinate peer stream waits during pdev communication*

RMM stream operations can return RMI_DEV_COMM_EXIT_STREAM_WAIT while
one side waits for the peer stream to reach the matching point in the
protocol.

Teach arm-cca host device communication to detect STREAM_WAIT and add
a helper that runs pdev communication for both sides in parallel until
each side has made enough progress, then issue rmi_pdev_stream_complete().

This provides the synchronization needed for stream connect,
disconnect, key refresh, and key purge operations.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h        |   1 +
 drivers/virt/coco/arm-cca-host/rmi-da.c | 116 +++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h |  13 +++
 3 files changed, 125 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 7a5d57a8be7a..e9437d56996a 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -484,6 +484,7 @@ struct rmi_pdev_params {
 #define RMI_DEV_COMM_EXIT_WAIT		BIT(3)
 #define RMI_DEV_COMM_EXIT_RSP_RESET	BIT(4)
 #define RMI_DEV_COMM_EXIT_MULTI		BIT(5)
+#define RMI_DEV_COMM_EXIT_STREAM_WAIT	BIT(6)
 
 #define RMI_DEV_COMM_NONE	0
 #define RMI_DEV_COMM_RESPONSE	1
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index cb654d1b2eb3..28f450e2db27 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -197,7 +197,7 @@ static inline gfp_t cache_obj_id_to_gfp_flags(u8 cache_obj_id)
 	return GFP_KERNEL_ACCOUNT;
 }
 
-static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
+static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm, int *stream_wait)
 {
 	unsigned long rmi_ret;
 	gfp_t cache_alloc_flags;
@@ -329,11 +329,17 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 	if (pending_dev_communicate(io_exit))
 		goto redo_communicate;
 
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_STREAM_WAIT) {
+		if (stream_wait)
+			*stream_wait = 1;
+		else
+			WARN(1, "Unexpected Stream wait status\n");
+	}
 	return 0;
 }
 
 static int do_dev_communicate(enum dev_comm_type type,
-		struct pci_tsm *tsm, unsigned long error_state)
+		struct pci_tsm *tsm, unsigned long error_state, int *stream_wait)
 {
 	int ret, state = error_state;
 	struct rmi_dev_comm_enter *io_enter;
@@ -342,8 +348,10 @@ static int do_dev_communicate(enum dev_comm_type type,
 	io_enter = &pdev_dsc->comm_data.io_params->enter;
 	io_enter->resp_len = 0;
 	io_enter->status = RMI_DEV_COMM_NONE;
+	if (stream_wait)
+		*stream_wait = 0;
 
-	ret = _do_dev_communicate(type, tsm);
+	ret = _do_dev_communicate(type, tsm, stream_wait);
 	if (ret) {
 		if (type == PDEV_COMMUNICATE)
 			rmi_pdev_abort(virt_to_phys(pdev_dsc->rmm_pdev));
@@ -371,7 +379,7 @@ static int wait_for_dev_state(enum dev_comm_type type, struct pci_tsm *tsm,
 	int state;
 
 	do {
-		state = do_dev_communicate(type, tsm, error_state);
+		state = do_dev_communicate(type, tsm, error_state, NULL);
 
 		if (state == target_state || state == error_state)
 			return state;
@@ -593,7 +601,7 @@ static void pdev_collect_identity_workfn(struct work_struct *work)
 
 	guard(mutex)(&pdev_dsc->object_lock);
 
-	do_dev_communicate(PDEV_COMMUNICATE, tsm, RMI_PDEV_ERROR);
+	do_dev_communicate(PDEV_COMMUNICATE, tsm, RMI_PDEV_ERROR, NULL);
 
 	/*
 	 * Don't worry about communication error. The caller will look at
@@ -711,3 +719,101 @@ void cca_pdev_stop_and_destroy(struct pci_dev *pdev)
 		free_page((unsigned long)pdev_dsc->rmm_pdev);
 	pdev_dsc->rmm_pdev = NULL;
 }
+
+static void stream_connect_workfn(struct work_struct *work)
+{
+	int state;
+	int peer_wait = 0;
+	struct pci_tsm *tsm;
+	int my_index, peer_index, target;
+	struct stream_connect_work *stream_work;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	stream_work = container_of(work, struct stream_connect_work, work);
+	tsm = stream_work->tsm;
+	pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+
+	my_index = stream_work->my_index;
+	peer_index = my_index ^ 0x1;
+
+redo_communicate:
+	mutex_lock(&pdev_dsc->object_lock);
+
+	state = do_dev_communicate(PDEV_COMMUNICATE, tsm, RMI_PDEV_ERROR, &peer_wait);
+	if (state != RMI_PDEV_ERROR && peer_wait) {
+
+		if (!stream_work->has_peer) {
+			WARN(1, "Unexpected STREAM_WAIT without peer stream\n");
+			mutex_unlock(&pdev_dsc->object_lock);
+			return;
+		}
+		/*
+		 * Record a fresh target val for this side, then wait until
+		 * peer reaches at least the same target.
+		 */
+		target = atomic_inc_return(&stream_work->sync->val[my_index]);
+
+		wake_up_all(&stream_work->sync->wq);
+
+		mutex_unlock(&pdev_dsc->object_lock);
+
+		/* Wait for peer to make matching progress */
+		wait_event(stream_work->sync->wq,
+			   atomic_read(&stream_work->sync->val[peer_index]) >= target);
+		goto redo_communicate;
+	}
+
+	/* Signal peer if it is waiting on me */
+	atomic_inc_return(&stream_work->sync->val[my_index]);
+	wake_up_all(&stream_work->sync->wq);
+
+	mutex_unlock(&pdev_dsc->object_lock);
+}
+
+static int __maybe_unused submit_stream_work(struct pci_dev *pdev1, struct pci_dev *pdev2,
+		unsigned long stream_handle)
+{
+	phys_addr_t rmm_pdev1_phys, rmm_pdev2_phys = 0;
+	struct cca_host_comm_data *comm_data_pdev1, *comm_data_pdev2;
+	struct cca_host_pdev_dsc *pdev_dsc1, *pdev_dsc2 = NULL;
+	struct stream_sync sync;
+	struct stream_connect_work stream_work_pdev1, stream_work_pdev2;
+
+	comm_data_pdev1 = to_cca_comm_data(pdev1);
+	init_waitqueue_head(&sync.wq);
+	atomic_set(&sync.val[0], 0);
+	atomic_set(&sync.val[1], 0);
+
+	pdev_dsc1 = to_cca_pdev_dsc(pdev1);
+	INIT_WORK_ONSTACK(&stream_work_pdev1.work, stream_connect_workfn);
+	stream_work_pdev1.tsm = pdev1->tsm;
+	stream_work_pdev1.sync = &sync;
+	stream_work_pdev1.my_index = 0;
+	stream_work_pdev1.has_peer = !!pdev2;
+	queue_work(comm_data_pdev1->work_queue, &stream_work_pdev1.work);
+
+	if (pdev2) {
+		comm_data_pdev2 = to_cca_comm_data(pdev2);
+		pdev_dsc2 = to_cca_pdev_dsc(pdev2);
+		INIT_WORK_ONSTACK(&stream_work_pdev2.work, stream_connect_workfn);
+		stream_work_pdev2.tsm = pdev2->tsm;
+		stream_work_pdev2.sync = &sync;
+		stream_work_pdev2.my_index = 1;
+		stream_work_pdev2.has_peer = true;
+		queue_work(comm_data_pdev2->work_queue, &stream_work_pdev2.work);
+	}
+
+	flush_work(&stream_work_pdev1.work);
+	if (pdev2) {
+		flush_work(&stream_work_pdev2.work);
+		destroy_work_on_stack(&stream_work_pdev2.work);
+	}
+
+	destroy_work_on_stack(&stream_work_pdev1.work);
+
+	rmm_pdev1_phys = virt_to_phys(pdev_dsc1->rmm_pdev);
+	if (pdev2)
+		rmm_pdev2_phys = virt_to_phys(pdev_dsc2->rmm_pdev);
+
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 240b2993ae53..5b0f43493485 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -27,6 +27,19 @@ struct dev_comm_work {
 	struct work_struct work;
 };
 
+struct stream_sync {
+	wait_queue_head_t wq;
+	atomic_t val[2];
+};
+
+struct stream_connect_work {
+	struct pci_tsm *tsm;
+	struct work_struct work;
+	struct stream_sync *sync;
+	u8 my_index;
+	bool has_peer;
+};
+
 struct cca_host_comm_data {
 	void *rsp_buff;
 	void *req_buff;

---

## [12] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 11/14] coco: host: arm64: Connect RMM pdev streams for IDE devices*

Add the RMI definitions for pdev stream management, including the stream
parameter layout and helpers for RMI_PDEV_STREAM_CONNECT,
RMI_PDEV_STREAM_COMPLETE, and RMI_PDEV_STREAM_DISCONNECT.

Create an RMM pdev for the endpoint's root port when needed, build the
non-coherent stream parameters from the endpoint/root-port pdevs, IDE
stream ID, and bridge address windows, and issue the RMM stream connect
before enabling IDE on the endpoint.

Store the returned stream handle in the PF0 descriptor

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  37 +++++++
 arch/arm64/include/asm/rmi_smc.h         |  39 +++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 127 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  |  40 ++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  57 ++++++++++
 5 files changed, 299 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 00e0a08e17a6..c82d4d9cbc06 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -774,4 +774,41 @@ static inline unsigned long rmi_pdev_set_pubkey(unsigned long pdev_phys, unsigne
 	return res.a0;
 }
 
+
+static inline unsigned long rmi_pdev_stream_connect(unsigned long stream_params_phys,
+		unsigned long *stream_handle)
+{
+
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STREAM_CONNECT, stream_params_phys, &res);
+
+	*stream_handle = res.a1;
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_stream_complete(unsigned long pdev1_phys,
+		unsigned long pdev2_phys, unsigned long stream_handle)
+{
+
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STREAM_COMPLETE, pdev1_phys,
+			     pdev2_phys, stream_handle, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_stream_disconnect(unsigned long pdev1_phys,
+		unsigned long pdev2_phys, unsigned long stream_handle)
+{
+
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STREAM_DISCONNECT, pdev1_phys,
+			     pdev2_phys, stream_handle, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index e9437d56996a..7b16f1540a0e 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -556,4 +556,43 @@ struct rmi_public_key_params {
 	};
 };
 
+#define MAX_STREAM_ADDR_RANGE	16
+
+enum rmi_pdev_stream_type {
+	RMI_PDEV_STREAM_NON_TEE,
+	RMI_PDEV_STREAM_NCOH,
+	RMI_PDEV_STREAM_COH,
+	RMI_PDEV_STREAM_NCOH_SYS,
+	RMI_PDEV_STREAM_COH_SYS,
+	RMI_PDEV_STREAM_NCOH_P2P,
+	RMI_PDEV_STREAM_COH_CMEM,
+};
+
+struct rmi_addr_range {
+	u64 base; /* inclusive */
+	u64 top;  /* exclusive */
+};
+
+struct rmi_pdev_stream_params {
+	union {
+		struct {
+			u64 flags;
+			union {
+				u8 type;
+				u8 padding1[8];
+			};
+			u64 pdev_1;
+			u64 pdev_2;
+			u64 ide_sid;
+			u64 num_addr_range;
+		};
+		u8 padding2[0x100];
+	};
+
+	union { /* 0x100 */
+		struct rmi_addr_range addr_range[MAX_STREAM_ADDR_RANGE];
+		u8 padding3[0xF00];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index f0aa4e46e96c..de7a2e156549 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -134,6 +134,126 @@ static int alloc_stream_id(struct pci_host_bridge *hb)
 	return stream_id;
 }
 
+static int cca_root_port_pdev_create(struct pci_dev *rp, struct tsm_dev *tsm_dev)
+{
+	int ret;
+	struct cca_host_rp_dsc *rp_dsc;
+
+	/* We are under pci_tsm_rwsem. */
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+
+	rp_dsc = kzalloc_obj(*rp_dsc);
+	if (!rp_dsc)
+		return -ENOMEM;
+
+	/* we expect this to be asigned early */
+	rp->tsm = &rp_dsc->pci;
+	rp->tsm->dsm_dev = rp;
+	rp->tsm->pdev = rp;
+	rp->tsm->tsm_dev = tsm_dev;
+	mutex_init(&rp_dsc->pdev.object_lock);
+
+	ret = init_dev_communication_buffers(rp, &rp_dsc->pdev.comm_data);
+	if (ret)
+		goto err_comm_buff;
+
+	ret = cca_pdev_create(rp);
+	if (ret)
+		goto err_pdev_create;
+
+	/*
+	 * device communication is still required even though
+	 * there is not identity collection
+	 */
+	ret = cca_pdev_collect_identity(rp);
+	if (ret)
+		goto pdev_destroy;
+
+	return 0;
+
+pdev_destroy:
+	cca_pdev_stop_and_destroy(rp);
+err_pdev_create:
+	free_dev_communication_buffers(&rp_dsc->pdev.comm_data);
+err_comm_buff:
+	kfree(rp_dsc);
+	rp->tsm = NULL;
+	return ret;
+}
+
+static int pci_dev_addr_range(struct pci_dev *pdev, struct rmi_addr_range *pdev_addr)
+{
+	int naddr = 0;
+	struct pci_dev *br;
+	struct resource *mem, *pref;
+
+	br = pci_upstream_bridge(pdev);
+	if (!br)
+		return 0;
+
+	mem = pci_resource_n(br, PCI_BRIDGE_MEM_WINDOW);
+	pref = pci_resource_n(br, PCI_BRIDGE_PREF_MEM_WINDOW);
+	if (resource_assigned(mem))
+		naddr = insert_addr_range_sorted(pdev_addr, naddr,
+						 mem->start, mem->end + 1);
+	if (resource_assigned(pref))
+		naddr = insert_addr_range_sorted(pdev_addr, naddr,
+						 pref->start, pref->end + 1);
+
+	return naddr;
+}
+
+static int cca_pdev_create_ncoh_stream(struct pci_dev *pdev, unsigned long stream_id)
+{
+	int ret;
+	long stream_handle;
+	struct cca_host_rp_dsc *rp_dsc;
+	struct rmi_pdev_stream_params *params;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+
+	if (!rp->tsm) {
+		ret = cca_root_port_pdev_create(rp, pf0_ep_dsc->pci.base_tsm.tsm_dev);
+		if (ret)
+			return ret;
+		rp_dsc = to_cca_rp_dsc(rp);
+	} else {
+		rp_dsc = to_cca_rp_dsc(rp);
+		/* Make sure they use the same TSM */
+		if (rp->tsm->tsm_dev != pf0_ep_dsc->pci.base_tsm.tsm_dev)
+			return -EINVAL;
+	}
+
+
+	params = (struct rmi_pdev_stream_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params)
+		return -ENOMEM;
+
+	params->flags = 0;
+	params->type = RMI_PDEV_STREAM_NCOH;
+	params->pdev_1 = virt_to_phys(pf0_ep_dsc->pdev.rmm_pdev);
+	params->pdev_2 = virt_to_phys(rp_dsc->pdev.rmm_pdev);
+	params->ide_sid = stream_id;
+	params->num_addr_range = pci_dev_addr_range(pdev, params->addr_range);
+
+	ret = cca_pdev_stream_connect(pdev, rp, params, &stream_handle);
+	if (!ret)
+		pf0_ep_dsc->stream_handle = stream_handle;
+
+	free_page((unsigned long)params);
+	return ret;
+}
+
+static int cca_pdev_create_streams(struct pci_dev *pdev, unsigned long stream_id)
+{
+	switch (pci_pcie_type(pdev)) {
+	case PCI_EXP_TYPE_ENDPOINT:
+		return cca_pdev_create_ncoh_stream(pdev, stream_id);
+	default:
+		return -EINVAL;
+	}
+}
+
 static inline bool cca_pdev_need_sel_ide_streams(struct pci_dev *pdev)
 {
 	return pci_pcie_type(pdev) == PCI_EXP_TYPE_ENDPOINT;
@@ -202,6 +322,10 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 		if (ret)
 			goto pdev_destroy;
 	}
+	/* Create IDE streams */
+	ret = cca_pdev_create_streams(pdev, stream_id);
+	if (ret)
+		goto pdev_destroy;
 	/*
 	 * Once ide is setup, enable the stream at the endpoint
 	 * Root port will be done by RMM
@@ -239,6 +363,7 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	int stream_id;
 	struct pci_ide *ide;
 	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
 
 	pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
 	if (!pf0_ep_dsc)
@@ -249,6 +374,8 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 		stream_id = ide->stream_id;
 	}
 
+	cca_pdev_disconnect_stream(pdev, rp, pf0_ep_dsc->stream_handle);
+
 	cca_pdev_stop_and_destroy(pdev);
 	free_dev_communication_buffers(&pf0_ep_dsc->pdev.comm_data);
 
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 28f450e2db27..a10ac6ff03d1 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -62,6 +62,10 @@ static int init_pdev_params(struct pci_dev *pdev, struct rmi_pdev_params *params
 		category = RMI_PDEV_FLAGS_CATEGORY_OFF_CHIP_EP;
 		break;
 	}
+	case PCI_EXP_TYPE_ROOT_PORT: {
+		category = RMI_PDEV_FLAGS_CATEGORY_ROOT_PORT;
+		break;
+	}
 	default:
 		return -EINVAL;
 	}
@@ -770,7 +774,7 @@ static void stream_connect_workfn(struct work_struct *work)
 	mutex_unlock(&pdev_dsc->object_lock);
 }
 
-static int __maybe_unused submit_stream_work(struct pci_dev *pdev1, struct pci_dev *pdev2,
+static int submit_stream_work(struct pci_dev *pdev1, struct pci_dev *pdev2,
 		unsigned long stream_handle)
 {
 	phys_addr_t rmm_pdev1_phys, rmm_pdev2_phys = 0;
@@ -814,6 +818,40 @@ static int __maybe_unused submit_stream_work(struct pci_dev *pdev1, struct pci_d
 	rmm_pdev1_phys = virt_to_phys(pdev_dsc1->rmm_pdev);
 	if (pdev2)
 		rmm_pdev2_phys = virt_to_phys(pdev_dsc2->rmm_pdev);
+	/*
+	 * If we had device communication error, this will error out.
+	 */
+	if (rmi_pdev_stream_complete(rmm_pdev1_phys, rmm_pdev2_phys, stream_handle))
+		return -EIO;
 
 	return 0;
 }
+
+int cca_pdev_stream_connect(struct pci_dev *pdev1, struct pci_dev *pdev2,
+		struct rmi_pdev_stream_params *stream_params,
+		unsigned long *stream_handle)
+{
+	phys_addr_t stream_params_phys = virt_to_phys(stream_params);
+
+	if (rmi_pdev_stream_connect(stream_params_phys, stream_handle))
+		return -EIO;
+
+	return submit_stream_work(pdev1, pdev2, *stream_handle);
+}
+
+int cca_pdev_disconnect_stream(struct pci_dev *pdev1,
+		struct pci_dev *pdev2, unsigned long stream_handle)
+{
+
+	phys_addr_t rmm_pdev2_phys = 0;
+	struct cca_host_pdev_dsc *pdev_dsc1 = to_cca_pdev_dsc(pdev1);
+
+	if (pdev2)
+		rmm_pdev2_phys = virt_to_phys(to_cca_pdev_dsc(pdev2)->rmm_pdev);
+
+	if (rmi_pdev_stream_disconnect(virt_to_phys(pdev_dsc1->rmm_pdev),
+				       rmm_pdev2_phys, stream_handle))
+		return -EIO;
+
+	return submit_stream_work(pdev1, pdev2, stream_handle);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 5b0f43493485..ea5f7df3541f 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -72,6 +72,7 @@ struct cca_host_pdev_dsc {
  * @pci: Physical Function 0 TDISP link context
  * @pdev: pdev communication context
  * @sel_stream: Selective IDE Stream descriptor
+ * @stream_handle: Stream handle returned by stream connect
  * @rmi_signature_algorithm: Signature algorithm used for public key
  * @cert_chain: cetrificate chain
  * @vca: SPDM's Version-Capabilities-Algorithms cache object
@@ -80,6 +81,7 @@ struct cca_host_pf0_ep_dsc {
 	struct pci_tsm_pf0 pci;
 	struct cca_host_pdev_dsc pdev;
 	struct pci_ide *sel_stream;
+	unsigned long stream_handle;
 
 	uint8_t rmi_signature_algorithm;
 	struct {
@@ -93,6 +95,17 @@ struct cca_host_pf0_ep_dsc {
 	struct cache_object *vca;
 };
 
+/**
+ * struct cca_host_rp_dsc - Root-port pdev context for stream coordination.
+ * @pci: Root-port TSM link context
+ * @pdev: Common pdev communication context
+ * @tsm_ref: Reference count held by connected endpoint streams
+ */
+struct cca_host_rp_dsc {
+	struct pci_tsm pci;
+	struct cca_host_pdev_dsc pdev;
+};
+
 struct cca_host_fn_dsc {
 	struct pci_tsm pci;
 };
@@ -101,6 +114,30 @@ enum dev_comm_type {
 	PDEV_COMMUNICATE = 0x1,
 };
 
+static inline int insert_addr_range_sorted(struct rmi_addr_range *addr_range,
+		int nr_addr_range, resource_size_t start, resource_size_t top)
+{
+	int index = nr_addr_range;
+
+	while (index > 0) {
+		struct rmi_addr_range *prev = &addr_range[index - 1];
+
+		if (prev->base < start)
+			break;
+
+		if (prev->base == start && prev->top <= top)
+			break;
+
+		addr_range[index] = *prev;
+		index--;
+	}
+
+	addr_range[index].base = start;
+	addr_range[index].top = top;
+
+	return nr_addr_range + 1;
+}
+
 static inline struct cca_host_pf0_ep_dsc *to_cca_pf0_ep_dsc(struct pci_dev *pdev)
 {
 	struct pci_tsm *tsm = pdev->tsm;
@@ -118,14 +155,29 @@ static inline struct cca_host_fn_dsc *to_cca_fn_dsc(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_host_fn_dsc, pci);
 }
 
+static inline struct cca_host_rp_dsc *to_cca_rp_dsc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm || pci_pcie_type(pdev) != PCI_EXP_TYPE_ROOT_PORT)
+		return NULL;
+
+	return container_of(tsm, struct cca_host_rp_dsc, pci);
+}
+
 static inline struct cca_host_pdev_dsc *to_cca_pdev_dsc(struct pci_dev *pdev)
 {
 	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+	struct cca_host_rp_dsc *rp_dsc;
 
 	pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
 	if (pf0_ep_dsc)
 		return &pf0_ep_dsc->pdev;
 
+	rp_dsc = to_cca_rp_dsc(pdev);
+	if (rp_dsc)
+		return &rp_dsc->pdev;
+
 	return NULL;
 }
 
@@ -152,5 +204,10 @@ int cca_pdev_collect_identity(struct pci_dev *pdev);
 bool cca_pdev_needs_key(struct pci_dev *pdev);
 int cca_pdev_set_public_key(struct pci_dev *pdev);
 void cca_pdev_stop_and_destroy(struct pci_dev *pdev);
+int cca_pdev_stream_connect(struct pci_dev *pdev1, struct pci_dev *pdev2,
+		struct rmi_pdev_stream_params *stream_params,
+		unsigned long *stream_handle);
+int cca_pdev_disconnect_stream(struct pci_dev *pdev1,
+		struct pci_dev *pdev2, unsigned long stream_handle);
 
 #endif

---

## [13] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 12/14] coco: host: arm64: Refcount root-port pdevs used by IDE streams*

Keep the root-port RMM pdev alive while endpoint IDE streams are attached
to it.

Add a kref to the root-port descriptor, take a reference when reusing an
existing root-port pdev for stream setup, and drop it when the endpoint
disconnects. Release the root-port pdev once the final reference is
dropped, tearing down the RMM object and its communication buffers at that
point.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-host/arm-cca.c | 31 +++++++++++++++++++++---
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  4 +++
 2 files changed, 32 insertions(+), 3 deletions(-)

diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index de7a2e156549..0b1200f591ab 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -134,6 +134,23 @@ static int alloc_stream_id(struct pci_host_bridge *hb)
 	return stream_id;
 }
 
+static void cca_root_port_pdev_release(struct kref *kref)
+{
+	struct cca_host_rp_dsc *rp_dsc = container_of(kref, struct cca_host_rp_dsc,
+						      tsm_ref);
+	struct pci_dev *rp = rp_dsc->pci.pdev;
+
+	cca_pdev_stop_and_destroy(rp);
+	free_dev_communication_buffers(&rp_dsc->pdev.comm_data);
+	rp->tsm = NULL;
+	kfree(rp_dsc);
+}
+
+static inline void cca_root_port_pdev_put(struct cca_host_rp_dsc *rp_dsc)
+{
+	kref_put(&rp_dsc->tsm_ref, cca_root_port_pdev_release);
+}
+
 static int cca_root_port_pdev_create(struct pci_dev *rp, struct tsm_dev *tsm_dev)
 {
 	int ret;
@@ -151,6 +168,7 @@ static int cca_root_port_pdev_create(struct pci_dev *rp, struct tsm_dev *tsm_dev
 	rp->tsm->dsm_dev = rp;
 	rp->tsm->pdev = rp;
 	rp->tsm->tsm_dev = tsm_dev;
+	kref_init(&rp_dsc->tsm_ref);
 	mutex_init(&rp_dsc->pdev.object_lock);
 
 	ret = init_dev_communication_buffers(rp, &rp_dsc->pdev.comm_data);
@@ -222,12 +240,15 @@ static int cca_pdev_create_ncoh_stream(struct pci_dev *pdev, unsigned long strea
 		/* Make sure they use the same TSM */
 		if (rp->tsm->tsm_dev != pf0_ep_dsc->pci.base_tsm.tsm_dev)
 			return -EINVAL;
-	}
 
+		kref_get(&rp_dsc->tsm_ref);
+	}
 
 	params = (struct rmi_pdev_stream_params *)get_zeroed_page(GFP_KERNEL);
-	if (!params)
+	if (!params) {
+		cca_root_port_pdev_put(rp_dsc);
 		return -ENOMEM;
+	}
 
 	params->flags = 0;
 	params->type = RMI_PDEV_STREAM_NCOH;
@@ -237,7 +258,9 @@ static int cca_pdev_create_ncoh_stream(struct pci_dev *pdev, unsigned long strea
 	params->num_addr_range = pci_dev_addr_range(pdev, params->addr_range);
 
 	ret = cca_pdev_stream_connect(pdev, rp, params, &stream_handle);
-	if (!ret)
+	if (ret)
+		cca_root_port_pdev_put(rp_dsc);
+	else
 		pf0_ep_dsc->stream_handle = stream_handle;
 
 	free_page((unsigned long)params);
@@ -375,6 +398,8 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	}
 
 	cca_pdev_disconnect_stream(pdev, rp, pf0_ep_dsc->stream_handle);
+	if (rp)
+		cca_root_port_pdev_put(to_cca_rp_dsc(rp));
 
 	cca_pdev_stop_and_destroy(pdev);
 	free_dev_communication_buffers(&pf0_ep_dsc->pdev.comm_data);
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index ea5f7df3541f..798a8ed7505f 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -10,6 +10,9 @@
 #include <linux/pci-ide.h>
 #include <linux/pci-tsm.h>
 #include <linux/sizes.h>
+#include <linux/atomic.h>
+#include <linux/kref.h>
+#include <linux/wait.h>
 #include <asm/rmi_cmds.h>
 #include <asm/rmi_smc.h>
 
@@ -104,6 +107,7 @@ struct cca_host_pf0_ep_dsc {
 struct cca_host_rp_dsc {
 	struct pci_tsm pci;
 	struct cca_host_pdev_dsc pdev;
+	struct kref tsm_ref;
 };
 
 struct cca_host_fn_dsc {

---

## [14] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 13/14] PCI/TSM: Move CMA DOE mailbox discovery out of pci_tsm_pf0_constructor()*

pci_tsm_pf0_constructor() currently looks up a CMA DOE mailbox and
fails PF0 initialization when one is not present. That is too strict
for all link TSM drivers.

Move CMA DOE mailbox discovery into the low-level PF0 probe callbacks
so each driver can decide whether a mailbox is mandatory.

Keep SEV-TIO and TDX requiring a CMA mailbox, while allowing the
arm-cca host path to proceed on PF0 devices that do not support IDE
and therefore have no DOE-based SPDM path.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/crypto/ccp/sev-dev-tsm.c         | 13 +++++++++++++
 drivers/pci/tsm/core.c                   | 14 ++++++++------
 drivers/virt/coco/arm-cca-host/arm-cca.c | 16 +++++++++++++---
 drivers/virt/coco/tdx-host/tdx-host.c    | 13 +++++++++++++
 4 files changed, 47 insertions(+), 9 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
index b07ae529b591..a7506cbbe392 100644
--- a/drivers/crypto/ccp/sev-dev-tsm.c
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -217,6 +217,19 @@ static struct pci_tsm *tio_pf0_probe(struct pci_dev *pdev, struct sev_device *se
 	if (rc)
 		return NULL;
 
+	/* if device have ide cap, setup doe mailbox */
+	if (pdev->ide_cap) {
+		struct pci_doe_mb *doe_mb;
+
+		doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					      PCI_DOE_FEATURE_CMA);
+		if (!doe_mb)
+			return NULL;
+		dsm->tsm.doe_mb = doe_mb;
+	} else {
+		return NULL;
+	}
+
 	pci_dbg(pdev, "TSM enabled\n");
 	dsm->sev = sev;
 	return &no_free_ptr(dsm)->tsm.base_tsm;
diff --git a/drivers/pci/tsm/core.c b/drivers/pci/tsm/core.c
index bb440135b8f7..900306a43161 100644
--- a/drivers/pci/tsm/core.c
+++ b/drivers/pci/tsm/core.c
@@ -1236,12 +1236,14 @@ int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 			    struct tsm_dev *tsm_dev)
 {
 	mutex_init(&tsm->lock);
-	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
-					   PCI_DOE_FEATURE_CMA);
-	if (!tsm->doe_mb) {
-		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
-		return -ENODEV;
-	}
+
+	/*
+	 * Note, low-level TSM driver responsible for determining if it wants to
+	 * proceed with a device that has no DOE mailbox. TSM may have an
+	 * alternate method for coordinating TDISP.
+	 */
+	if (!tsm->doe_mb)
+		pci_dbg(pdev, "no CMA mailbox\n");
 
 	return pci_tsm_link_constructor(pdev, &tsm->base_tsm, tsm_dev);
 }
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 0b1200f591ab..265aa0cb612a 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -11,6 +11,8 @@
 #include <linux/tsm.h>
 #include <linux/vmalloc.h>
 #include <linux/cleanup.h>
+#include <linux/pci-doe.h>
+
 
 #include "rmi-da.h"
 
@@ -35,14 +37,22 @@ static struct pci_tsm *cca_tsm_pci_probe(struct tsm_dev *tsm_dev, struct pci_dev
 		return &no_free_ptr(fn_dsc)->pci;
 	}
 
-	if (!pdev->ide_cap)
-		return NULL;
-
 	struct cca_host_pf0_ep_dsc *pf0_ep_dsc __free(kfree) =
 		kzalloc(sizeof(*pf0_ep_dsc), GFP_KERNEL);
 	if (!pf0_ep_dsc)
 		return NULL;
 
+	/* if device have ide cap, setup doe mailbox */
+	if (pdev->ide_cap) {
+		struct pci_doe_mb *doe_mb;
+
+		doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					      PCI_DOE_FEATURE_CMA);
+		if (!doe_mb)
+			return NULL;
+		pf0_ep_dsc->pci.doe_mb = doe_mb;
+	}
+
 	ret = pci_tsm_pf0_constructor(pdev, &pf0_ep_dsc->pci, tsm_dev);
 	if (ret)
 		return NULL;
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index ea7c2167660f..4947b9bc2359 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -634,6 +634,19 @@ static struct pci_tsm *tdx_link_pf0_probe(struct tsm_dev *tsm_dev,
 	spdm_conf->vmm_spdm_cap = SPDM_CAP_KEY_UPD;
 	spdm_conf->certificate_slot_mask = 0xff;
 
+	/* if device have ide cap, setup doe mailbox */
+	if (pdev->ide_cap) {
+		struct pci_doe_mb *doe_mb;
+
+		doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					      PCI_DOE_FEATURE_CMA);
+		if (!doe_mb)
+			return NULL;
+		tlink->pci.doe_mb = doe_mb;
+	} else {
+		return NULL;
+	}
+
 	tlink->in_msg = no_free_ptr(in_msg);
 	tlink->out_msg = no_free_ptr(out_msg);
 	tlink->spdm_conf = no_free_ptr(spdm_conf);

---

## [15] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 14/14] coco: host: arm64: Add NCOH_SYS stream support for RC endpoints*

Teach the host CCA pdev setup to handle PCI_EXP_TYPE_RC_END devices.

Classify RC integrated endpoints as RMI_PDEV_FLAGS_CATEGORY_ON_CHIP_EP when
building the RMM pdev parameters, and only advertise SPDM support when a
DOE mailbox is present.

Also add the stream setup path for these devices by creating an
RMI_PDEV_STREAM_NCOH_SYS stream using the endpoint pdev and its bridge
address windows. This allows RC endpoints to participate in the TDISP flow
without requiring a separate root-port pdev.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-host/arm-cca.c | 28 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 10 +++++++++
 2 files changed, 38 insertions(+)

diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 265aa0cb612a..8b1182620872 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -277,11 +277,39 @@ static int cca_pdev_create_ncoh_stream(struct pci_dev *pdev, unsigned long strea
 	return ret;
 }
 
+static int cca_pdev_create_ncoh_sys_stream(struct pci_dev *pdev)
+{
+	int ret;
+	long stream_handle;
+	struct rmi_pdev_stream_params *params;
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+
+	params = (struct rmi_pdev_stream_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params)
+		return -ENOMEM;
+
+	params->flags = 0;
+	params->type = RMI_PDEV_STREAM_NCOH_SYS;
+	params->pdev_1 = virt_to_phys(pf0_ep_dsc->pdev.rmm_pdev);
+	params->pdev_2 = 0; /* ignored */
+	params->ide_sid = 0; /* ignored */
+	params->num_addr_range = pci_dev_addr_range(pdev, params->addr_range);
+
+	ret = cca_pdev_stream_connect(pdev, NULL, params, &stream_handle);
+	if (!ret)
+		pf0_ep_dsc->stream_handle = stream_handle;
+
+	free_page((unsigned long)params);
+	return ret;
+}
+
 static int cca_pdev_create_streams(struct pci_dev *pdev, unsigned long stream_id)
 {
 	switch (pci_pcie_type(pdev)) {
 	case PCI_EXP_TYPE_ENDPOINT:
 		return cca_pdev_create_ncoh_stream(pdev, stream_id);
+	case PCI_EXP_TYPE_RC_END:
+		return cca_pdev_create_ncoh_sys_stream(pdev);
 	default:
 		return -EINVAL;
 	}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index a10ac6ff03d1..33a2551fd09f 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -66,6 +66,16 @@ static int init_pdev_params(struct pci_dev *pdev, struct rmi_pdev_params *params
 		category = RMI_PDEV_FLAGS_CATEGORY_ROOT_PORT;
 		break;
 	}
+	case PCI_EXP_TYPE_RC_END: {
+		struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(pdev);
+
+		/* Use SPDM if present */
+		if (pf0_ep_dsc->pci.doe_mb)
+			params->flags = RMI_PDEV_FLAGS_SPDM;
+
+		category = RMI_PDEV_FLAGS_CATEGORY_ON_CHIP_EP;
+		break;
+	}
 	default:
 		return -EINVAL;
 	}

---

## [16] Will Deacon — 2026-05-18
*Subject: Re: [RFC PATCH v4 00/14] coco/TSM: Host-side Arm CCA IDE setup via
 connect/disconnect callbacks*

On Mon, Apr 27, 2026 at 12:21:07PM +0530, Aneesh Kumar K.V (Arm) wrote:
>  arch/arm64/include/asm/rmi_cmds.h         |  85 +++
>  arch/arm64/include/asm/rmi_smc.h          | 168 +++++

Curious, but why does this stuff have to live in the arch code? Wouldn't
it be better off somewhere like drivers/firmware/ or
include/linux/arm-rmi.h?

Will

---

## [17] Aneesh Kumar K.V — 2026-05-18
*Subject: Re: [RFC PATCH v4 00/14] coco/TSM: Host-side Arm CCA IDE setup via
 connect/disconnect callbacks*

Will Deacon <will@kernel.org> writes:

> On Mon, Apr 27, 2026 at 12:21:07PM +0530, Aneesh Kumar K.V (Arm) wrote:
>>  arch/arm64/include/asm/rmi_cmds.h         |  85 +++

Those headers are used to collect all RMI-related helpers and #defines.
They were introduced by the Realm KVM/host support patch series, and I
am continuing to use the same headers to add more helpers.

We can consider moving the RMI helpers used by virt/coco/arm-caa-guest/,
virt/coco/arm-cca-host/, and
drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c into a more generic
header such as include/linux/arm-rmi.h. However, that would either
require moving all the helpers currently used by KVM there as well,
otherwise we would end up with two separate headers carrying RMI
helpers.

Additionally, there are also arch/arm64/include/asm/rsi_cmds.h and
arch/arm64/include/asm/rsi_smc.h to consider.

-aneesh

---

## [18] Suzuki K Poulose — 2026-05-19
*Subject: Re: [RFC PATCH v4 00/14] coco/TSM: Host-side Arm CCA IDE setup via
 connect/disconnect callbacks*

On 18/05/2026 13:59, Will Deacon wrote:
> On Mon, Apr 27, 2026 at 12:21:07PM +0530, Aneesh Kumar K.V (Arm) wrote:
>>   arch/arm64/include/asm/rmi_cmds.h         |  85 +++

Good point. RMI interface is only available for arm64 (not in Arm32). 
That said, it is indeed a firmware ! ;-) interface. The APIs are closely
integrated with the KVM Realm management. If the general consensus is
to move them under drivers/firmware (like PSCI), we could take that
approach.

Suzuki

> 
> Will

---

## [19] Will Deacon — 2026-05-19
*Subject: Re: [RFC PATCH v4 00/14] coco/TSM: Host-side Arm CCA IDE setup via
 connect/disconnect callbacks*

On Tue, May 19, 2026 at 09:24:07AM +0100, Suzuki K Poulose wrote:
> On 18/05/2026 13:59, Will Deacon wrote:
> > On Mon, Apr 27, 2026 at 12:21:07PM +0530, Aneesh Kumar K.V (Arm) wrote:

I'd certainly prefer that as it means it's co-located with other firmware
interface code and also means that the arch maintainers don't need to
worry about changes to driver code :p

Will

---

## [20] Dan Williams (nvidia) — 2026-05-27
*Subject: Re: [RFC PATCH v4 01/14] coco: host: arm64: Add host TSM callback and
 IDE stream allocation support*

Aneesh Kumar K.V (Arm) wrote:
> Register the TSM callback when the DA feature is supported by KVM.
> 

Do you want to call out that this is an infrastructure / scaffolding
patch that only handles the PCI-TSM skeleton. The CCA meat comes later,
in particular IDE key management. Tell a bit more of the story 

Otherwise, mostly looks good.

Minor comments below...

> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---
[..]
> diff --git a/drivers/firmware/smccc/rmm.c b/drivers/firmware/smccc/rmm.c
> index 2a6187df3285..7444cc3a588c 100644
[..]
> diff --git a/drivers/firmware/smccc/rmm.h b/drivers/firmware/smccc/rmm.h
> index a47a650d4f51..37d0d95a099e 100644
[..]
> diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
> index fc9b44b7c687..2bf2d59e686d 100644

Would splitting the above three hunks make this series stand on its own
relative to the base CCA series? I assume likely not as soon as we get
to patch2.

Otherwise, just curious what your intended merge strategy is for this,
tsm.git or arm.git, and what help this needs?

[..]
snip code that looks good.

> diff --git a/drivers/virt/coco/arm-cca-host/Makefile b/drivers/virt/coco/arm-cca-host/Makefile
> new file mode 100644

kzalloc_obj(*fn_dsc)

> +
> +		if (!fn_dsc)

Bailing early?

Maybe the RMM knows something about this device not needing IDE? I have
a similar question in patch2 around trusted sources for whether a device
is internal or not. 

> +
> +	struct cca_host_pf0_ep_dsc *pf0_ep_dsc __free(kfree) =

Is 256 total an RMM limit, and/or does it require globally unique
stream-ids? If not you could do what SEV-TIO does and just set stream-id
== stream-index.

> +}
> +

The end point of these patches follows the spec recommendation of
delaying enable until after key programming.

> +	}
> +	return 0;

Should this be making security claims to userspace without taking any
action for non-endpoint devices that happen to be passed in?

Thinking about a bisection case this should either fail here, print a
message that is removed in the final enabling patch, or do the
__maybe_unused arrangement to land all the CCA bits first and then do
this hookup. Up to you.

---
