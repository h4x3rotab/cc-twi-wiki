---
title: 'PCI/TSM: Core infrastructure for PCI device security (TDISP)'
date: 2025-10-31
last_reply: 2025-11-10
message_count: 21
participants: ['Dan Williams', 'Jonathan Cameron', 'Xu Yilun']
---

## [1] Dan Williams — 2025-10-31

Changes since v7 [1]:
- Pick up Reviewed-by tags from Jonathan, Alexey, and Aneesh.
- Simplify put_tsm_dev() (Jonathan)
- Misc cleanups (Jonathan)
- Drop IDR usage (switched to class_find_device()) (Carlos)
- Keep local drivers/bus/pci.c style for pci_walk_bus_reverse() (Jonathan)
- Clarify commit message for "PCI/TSM: Establish Secure Sessions and
  Link Encryption" (Jonathan)
- Fixup up documentation for 'struct pci_tsm_ops' (Jonathan)
- Clarify DSM lifetime comment (Jonathan)
- Fix alloc_stream_index() when the host bridge supports 256 streams
  (Aneesh)
- Drop PCI_IDE_ATTR_GROUP in favor of ifdef in C (Jonathan)
- Mirror setup sequence at unwind in tsm_unregister() (Jonathan)

[1]: http://lore.kernel.org/20251024020418.1366664-1-dan.j.williams@intel.com

This set will be available on Monday at
https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging
(rebasing branch) or devsec-20251103 (immutable tag). That branch
additionally contains address association support, Stream ID uniqueness
compability quirk, updated samples/devsec/ (now with multifunction
device and simple bind support), and an updated preview of v2 of "[PATCH
0/7] PCI/TSM: TEE I/O infrastructure" (fixes x86 encrypted ioremap and
other changes) [2].

[2]: http://lore.kernel.org/20250827035259.1356758-1-dan.j.williams@intel.com

It passes an updated regression test using samples/devsec/. See this
commit on the staging branch for that test:

https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/commit/?id=44932bffdcc1

Status: sufficient review for linux-next
----------------------------------------
Thanks to the folks that gave this topic another review this past week.
At this point it feels ready for linux-next exposure especially after
seeing work-in-progress rebases for SEV-TIO, CCA, and TDX Connect.

Next steps:
-----------
- Push this series to linux-next

- Post the next rev of "PCI/TSM: TEE I/O infrastructure"

- See at least one vendor "connect" implementation queued in an arch
  tree, or pull one into tsm.git

Updated Cover letter:
---------------------

Trusted execution environment (TEE) Device Interface Security Protocol
(TDISP) is a chapter name in the PCI Express Base Specification (r7.0).
It describes an alphabet soup of mechanisms, SPDM, CMA, IDE, TSM/DSM,
that system software uses to establish trust in a device and assign it
to a confidential virtual machine (CVM). It is a protocol for
dynamically extending the Trusted Computing Boundary (TCB) of a CVM with
a PCI device interface enabled to issue DMA to CVM private memory.

The acronym soup problem is extended by each platform architecture
having distinct TEE Security Manager (TSM) API implementations /
capabilities, and each endpoint Device Security Manager (DSM) having its
own idiosyncratic behaviors and requirements around TDISP state
transitions.

Despite all that opportunity for differentiation, there is a significant
portion of the implementation that is cross-vendor common. The PCI/TSM
extension of the PCI core subsystem is a library for TSM drivers to
establish link encryption and enable device access to confidential
memory.

This foundational phase is focused on host-side link encryption, the
next phase focuses on guest-side locking and accepting devices, the
phase after that focuses on all the host-side setup for private DMA and
private MMIO. There are more phases beyond that, like device
attestation, but the goal is upstream manageable incremental steps that
provide tangible value to Linux at each step.

Dan Williams (9):
  coco/tsm: Introduce a core device for TEE Security Managers
  PCI/IDE: Enumerate Selective Stream IDE capabilities
  PCI: Introduce pci_walk_bus_reverse(), for_each_pci_dev_reverse()
  PCI/TSM: Establish Secure Sessions and Link Encryption
  PCI: Add PCIe Device 3 Extended Capability enumeration
  PCI: Establish document for PCI host bridge sysfs attributes
  PCI/IDE: Add IDE establishment helpers
  PCI/IDE: Report available IDE streams
  PCI/TSM: Report active IDE streams

 drivers/pci/Kconfig                           |  18 +
 drivers/virt/coco/Kconfig                     |   3 +
 drivers/pci/Makefile                          |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 Documentation/ABI/testing/sysfs-bus-pci       |  51 ++
 Documentation/ABI/testing/sysfs-class-tsm     |  19 +
 .../ABI/testing/sysfs-devices-pci-host-bridge |  45 ++
 Documentation/driver-api/pci/index.rst        |   1 +
 Documentation/driver-api/pci/tsm.rst          |  21 +
 drivers/pci/pci.h                             |  19 +
 include/linux/device/bus.h                    |   3 +
 include/linux/pci-doe.h                       |   4 +
 include/linux/pci-ide.h                       |  81 +++
 include/linux/pci-tsm.h                       | 157 +++++
 include/linux/pci.h                           |  28 +
 include/linux/tsm.h                           |  17 +
 include/uapi/linux/pci_regs.h                 |  89 +++
 drivers/base/bus.c                            |  38 ++
 drivers/pci/bus.c                             |  39 ++
 drivers/pci/doe.c                             |   2 -
 drivers/pci/ide.c                             | 587 ++++++++++++++++
 drivers/pci/pci-sysfs.c                       |   4 +
 drivers/pci/probe.c                           |  31 +-
 drivers/pci/remove.c                          |   6 +
 drivers/pci/search.c                          |  62 +-
 drivers/pci/tsm.c                             | 643 ++++++++++++++++++
 drivers/virt/coco/tsm-core.c                  | 163 +++++
 MAINTAINERS                                   |   7 +-
 28 files changed, 2128 insertions(+), 13 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 create mode 100644 Documentation/driver-api/pci/tsm.rst
 create mode 100644 include/linux/pci-ide.h
 create mode 100644 include/linux/pci-tsm.h
 create mode 100644 drivers/pci/ide.c
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 drivers/virt/coco/tsm-core.c


base-commit: 211ddde0823f1442e4ad052a2f30f050145ccada

---

## [2] Dan Williams — 2025-10-31
*Subject: [PATCH v8 1/9] coco/tsm: Introduce a core device for TEE Security Managers*

A "TSM" is a platform component that provides an API for securely
provisioning resources for a confidential guest (TVM) to consume. The
name originates from the PCI specification for platform agent that
carries out operations for PCIe TDISP (TEE Device Interface Security
Protocol).

Instances of this core device are parented by a device representing the
platform security function like CONFIG_CRYPTO_DEV_CCP or
CONFIG_INTEL_TDX_HOST.

This device interface is a frontend to the aspects of a TSM and TEE I/O
that are cross-architecture common. This includes mechanisms like
enumerating available platform TEE I/O capabilities and provisioning
connections between the platform TSM and device DSMs (Device Security
Manager (TDISP)).

For now this is just the scaffolding for registering a TSM device sysfs
interface.

Cc: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Co-developed-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/Kconfig                 |  3 +
 drivers/virt/coco/Makefile                |  1 +
 Documentation/ABI/testing/sysfs-class-tsm |  9 +++
 include/linux/tsm.h                       | 11 +++
 drivers/virt/coco/tsm-core.c              | 93 +++++++++++++++++++++++
 MAINTAINERS                               |  2 +-
 6 files changed, 118 insertions(+), 1 deletion(-)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 drivers/virt/coco/tsm-core.c

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 819a97e8ba99..bb0c6d6ddcc8 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -14,3 +14,6 @@ source "drivers/virt/coco/tdx-guest/Kconfig"
 source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
+
+config TSM
+	bool
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index f918bbb61737..cb52021912b3 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -7,4 +7,5 @@ obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
+obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
new file mode 100644
index 000000000000..2949468deaf7
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -0,0 +1,9 @@
+What:		/sys/class/tsm/tsmN
+Contact:	linux-coco@lists.linux.dev
+Description:
+		"tsmN" is a device that represents the generic attributes of a
+		platform TEE Security Manager.  It is typically a child of a
+		platform enumerated TSM device. /sys/class/tsm/tsmN/uevent
+		signals when the PCI layer is able to support establishment of
+		link encryption and other device-security features coordinated
+		through a platform tsm.
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 431054810dca..cd97c63ffa32 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,7 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <linux/device.h>
 
 #define TSM_REPORT_INBLOB_MAX 64
 #define TSM_REPORT_OUTBLOB_MAX SZ_32K
@@ -107,6 +108,16 @@ struct tsm_report_ops {
 	bool (*report_bin_attr_visible)(int n);
 };
 
+struct tsm_dev {
+	struct device dev;
+	int id;
+};
+
+DEFINE_FREE(put_tsm_dev, struct tsm_dev *,
+	    if (!IS_ERR_OR_NULL(_T)) put_device(&_T->dev))
+
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
+struct tsm_dev *tsm_register(struct device *parent);
+void tsm_unregister(struct tsm_dev *tsm_dev);
 #endif /* __TSM_H */
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
new file mode 100644
index 000000000000..347507cc5e3f
--- /dev/null
+++ b/drivers/virt/coco/tsm-core.c
@@ -0,0 +1,93 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024-2025 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <linux/tsm.h>
+#include <linux/rwsem.h>
+#include <linux/device.h>
+#include <linux/module.h>
+#include <linux/cleanup.h>
+
+static struct class *tsm_class;
+static DECLARE_RWSEM(tsm_rwsem);
+static DEFINE_IDA(tsm_ida);
+
+static struct tsm_dev *alloc_tsm_dev(struct device *parent)
+{
+	struct device *dev;
+	int id;
+
+	struct tsm_dev *tsm_dev __free(kfree) =
+		kzalloc(sizeof(*tsm_dev), GFP_KERNEL);
+	if (!tsm_dev)
+		return ERR_PTR(-ENOMEM);
+
+	id = ida_alloc(&tsm_ida, GFP_KERNEL);
+	if (id < 0)
+		return ERR_PTR(id);
+
+	tsm_dev->id = id;
+	dev = &tsm_dev->dev;
+	dev->parent = parent;
+	dev->class = tsm_class;
+	device_initialize(dev);
+
+	return no_free_ptr(tsm_dev);
+}
+
+struct tsm_dev *tsm_register(struct device *parent)
+{
+	struct tsm_dev *tsm_dev __free(put_tsm_dev) = alloc_tsm_dev(parent);
+	struct device *dev;
+	int rc;
+
+	if (IS_ERR(tsm_dev))
+		return tsm_dev;
+
+	dev = &tsm_dev->dev;
+	rc = dev_set_name(dev, "tsm%d", tsm_dev->id);
+	if (rc)
+		return ERR_PTR(rc);
+
+	rc = device_add(dev);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return no_free_ptr(tsm_dev);
+}
+EXPORT_SYMBOL_GPL(tsm_register);
+
+void tsm_unregister(struct tsm_dev *tsm_dev)
+{
+	device_unregister(&tsm_dev->dev);
+}
+EXPORT_SYMBOL_GPL(tsm_unregister);
+
+static void tsm_release(struct device *dev)
+{
+	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);
+
+	ida_free(&tsm_ida, tsm_dev->id);
+	kfree(tsm_dev);
+}
+
+static int __init tsm_init(void)
+{
+	tsm_class = class_create("tsm");
+	if (IS_ERR(tsm_class))
+		return PTR_ERR(tsm_class);
+
+	tsm_class->dev_release = tsm_release;
+	return 0;
+}
+module_init(tsm_init)
+
+static void __exit tsm_exit(void)
+{
+	class_destroy(tsm_class);
+}
+module_exit(tsm_exit)
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("TEE Security Manager Class Device");
diff --git a/MAINTAINERS b/MAINTAINERS
index 545a4776795e..06285f3a24df 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26097,7 +26097,7 @@ M:	David Lechner <dlechner@baylibre.com>
 S:	Maintained
 F:	Documentation/devicetree/bindings/trigger-source/*
 
-TRUSTED SECURITY MODULE (TSM) INFRASTRUCTURE
+TRUSTED EXECUTION ENVIRONMENT SECURITY MANAGER (TSM)
 M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained

---

## [3] Dan Williams — 2025-10-31
*Subject: [PATCH v8 2/9] PCI/IDE: Enumerate Selective Stream IDE capabilities*

Link encryption is a new PCIe feature enumerated by "PCIe r7.0 section
7.9.26 IDE Extended Capability".

It is both a standalone port + endpoint capability, and a building block
for the security protocol defined by "PCIe r7.0 section 11 TEE Device
Interface Security Protocol (TDISP)". That protocol coordinates device
security setup between a platform TSM (TEE Security Manager) and a
device DSM (Device Security Manager). While the platform TSM can
allocate resources like Stream ID and manage keys, it still requires
system software to manage the IDE capability register block.

Add register definitions and basic enumeration in preparation for
Selective IDE Stream establishment. A follow on change selects the new
CONFIG_PCI_IDE symbol. Note that while the IDE specification defines
both a point-to-point "Link Stream" and a Root Port to endpoint
"Selective Stream", only "Selective Stream" is considered for Linux as
that is the predominant mode expected by Trusted Execution Environment
Security Managers (TSMs), and it is the security model that limits the
number of PCI components within the TCB in a PCIe topology with
switches.

Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Reviewed-by: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Kconfig           |  3 ++
 drivers/pci/Makefile          |  1 +
 drivers/pci/pci.h             |  6 +++
 include/linux/pci.h           |  7 +++
 include/uapi/linux/pci_regs.h | 81 ++++++++++++++++++++++++++++++++
 drivers/pci/ide.c             | 88 +++++++++++++++++++++++++++++++++++
 drivers/pci/probe.c           |  1 +
 7 files changed, 187 insertions(+)
 create mode 100644 drivers/pci/ide.c

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index f94f5d384362..b28423e2057f 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -122,6 +122,9 @@ config XEN_PCIDEV_FRONTEND
 config PCI_ATS
 	bool
 
+config PCI_IDE
+	bool
+
 config PCI_DOE
 	bool "Enable PCI Data Object Exchange (DOE) support"
 	help
diff --git a/drivers/pci/Makefile b/drivers/pci/Makefile
index 67647f1880fb..6612256fd37d 100644
--- a/drivers/pci/Makefile
+++ b/drivers/pci/Makefile
@@ -34,6 +34,7 @@ obj-$(CONFIG_PCI_P2PDMA)	+= p2pdma.o
 obj-$(CONFIG_XEN_PCIDEV_FRONTEND) += xen-pcifront.o
 obj-$(CONFIG_VGA_ARB)		+= vgaarb.o
 obj-$(CONFIG_PCI_DOE)		+= doe.o
+obj-$(CONFIG_PCI_IDE)		+= ide.o
 obj-$(CONFIG_PCI_DYNAMIC_OF_NODES) += of_property.o
 obj-$(CONFIG_PCI_NPEM)		+= npem.o
 obj-$(CONFIG_PCIE_TPH)		+= tph.o
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 4492b809094b..86ef13e7cece 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -613,6 +613,12 @@ static inline void pci_doe_sysfs_init(struct pci_dev *pdev) { }
 static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 #endif
 
+#ifdef CONFIG_PCI_IDE
+void pci_ide_init(struct pci_dev *dev);
+#else
+static inline void pci_ide_init(struct pci_dev *dev) { }
+#endif
+
 /**
  * pci_dev_set_io_state - Set the new error state if possible.
  *
diff --git a/include/linux/pci.h b/include/linux/pci.h
index d1fdf81fbe1e..4402ca931124 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -539,6 +539,13 @@ struct pci_dev {
 #endif
 #ifdef CONFIG_PCI_NPEM
 	struct npem	*npem;		/* Native PCIe Enclosure Management */
+#endif
+#ifdef CONFIG_PCI_IDE
+	u16		ide_cap;	/* Link Integrity & Data Encryption */
+	u8		nr_ide_mem;	/* Address association resources for streams */
+	u8		nr_link_ide;	/* Link Stream count (Selective Stream offset) */
+	unsigned int	ide_cfg:1;	/* Config cycles over IDE */
+	unsigned int	ide_tee_limit:1; /* Disallow T=0 traffic over IDE */
 #endif
 	u16		acs_cap;	/* ACS Capability offset */
 	u8		supported_speeds; /* Supported Link Speeds Vector */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 07e06aafec50..05bd22d9e352 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -754,6 +754,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_PL_64GT	0x31	/* Physical Layer 64.0 GT/s */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_PL_64GT
 
@@ -1249,4 +1250,84 @@
 #define PCI_DVSEC_CXL_PORT_CTL				0x0c
 #define PCI_DVSEC_CXL_PORT_CTL_UNMASK_SBR		0x00000001
 
+/* Integrity and Data Encryption Extended Capability */
+#define PCI_IDE_CAP			0x04
+#define  PCI_IDE_CAP_LINK		0x1  /* Link IDE Stream Supported */
+#define  PCI_IDE_CAP_SELECTIVE		0x2  /* Selective IDE Streams Supported */
+#define  PCI_IDE_CAP_FLOWTHROUGH	0x4  /* Flow-Through IDE Stream Supported */
+#define  PCI_IDE_CAP_PARTIAL_HEADER_ENC 0x8  /* Partial Header Encryption Supported */
+#define  PCI_IDE_CAP_AGGREGATION	0x10 /* Aggregation Supported */
+#define  PCI_IDE_CAP_PCRC		0x20 /* PCRC Supported */
+#define  PCI_IDE_CAP_IDE_KM		0x40 /* IDE_KM Protocol Supported */
+#define  PCI_IDE_CAP_SEL_CFG		0x80 /* Selective IDE for Config Request Support */
+#define  PCI_IDE_CAP_ALG		__GENMASK(12, 8) /* Supported Algorithms */
+#define   PCI_IDE_CAP_ALG_AES_GCM_256	0    /* AES-GCM 256 key size, 96b MAC */
+#define  PCI_IDE_CAP_LINK_TC_NUM	__GENMASK(15, 13) /* Link IDE TCs */
+#define  PCI_IDE_CAP_SEL_NUM		__GENMASK(23, 16) /* Supported Selective IDE Streams */
+#define  PCI_IDE_CAP_TEE_LIMITED	0x1000000 /* TEE-Limited Stream Supported */
+#define PCI_IDE_CTL			0x08
+#define  PCI_IDE_CTL_FLOWTHROUGH_IDE	0x4  /* Flow-Through IDE Stream Enabled */
+
+#define PCI_IDE_LINK_STREAM_0		0xc  /* First Link Stream Register Block */
+#define  PCI_IDE_LINK_BLOCK_SIZE	8
+/* Link IDE Stream block, up to PCI_IDE_CAP_LINK_TC_NUM */
+#define PCI_IDE_LINK_CTL_0		0x00		  /* First Link Control Register Offset in block */
+#define  PCI_IDE_LINK_CTL_EN		0x1		  /* Link IDE Stream Enable */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_NPR	__GENMASK(3, 2)	  /* Tx Aggregation Mode NPR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_PR	__GENMASK(5, 4)	  /* Tx Aggregation Mode PR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_CPL	__GENMASK(7, 6)	  /* Tx Aggregation Mode CPL */
+#define  PCI_IDE_LINK_CTL_PCRC_EN	0x100		  /* PCRC Enable */
+#define  PCI_IDE_LINK_CTL_PART_ENC	__GENMASK(13, 10) /* Partial Header Encryption Mode */
+#define  PCI_IDE_LINK_CTL_ALG		__GENMASK(18, 14) /* Selection from PCI_IDE_CAP_ALG */
+#define  PCI_IDE_LINK_CTL_TC		__GENMASK(21, 19) /* Traffic Class */
+#define  PCI_IDE_LINK_CTL_ID		__GENMASK(31, 24) /* Stream ID */
+#define PCI_IDE_LINK_STS_0		0x4               /* First Link Status Register Offset in block */
+#define  PCI_IDE_LINK_STS_STATE		__GENMASK(3, 0)   /* Link IDE Stream State */
+#define  PCI_IDE_LINK_STS_IDE_FAIL	0x80000000	  /* IDE fail message received */
+
+/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */
+/* Selective IDE Stream Capability Register */
+#define  PCI_IDE_SEL_CAP		0x00
+#define   PCI_IDE_SEL_CAP_ASSOC_NUM	__GENMASK(3, 0)
+/* Selective IDE Stream Control Register */
+#define  PCI_IDE_SEL_CTL		0x04
+#define   PCI_IDE_SEL_CTL_EN		0x1		  /* Selective IDE Stream Enable */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_NPR	__GENMASK(3, 2)	  /* Tx Aggregation Mode NPR */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_PR	__GENMASK(5, 4)   /* Tx Aggregation Mode PR */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_CPL	__GENMASK(7, 6)	  /* Tx Aggregation Mode CPL */
+#define   PCI_IDE_SEL_CTL_PCRC_EN	0x100		  /* PCRC Enable */
+#define   PCI_IDE_SEL_CTL_CFG_EN	0x200		  /* Selective IDE for Configuration Requests */
+#define   PCI_IDE_SEL_CTL_PART_ENC	__GENMASK(13, 10) /* Partial Header Encryption Mode */
+#define   PCI_IDE_SEL_CTL_ALG		__GENMASK(18, 14) /* Selection from PCI_IDE_CAP_ALG */
+#define   PCI_IDE_SEL_CTL_TC		__GENMASK(21, 19) /* Traffic Class */
+#define   PCI_IDE_SEL_CTL_DEFAULT	0x400000	  /* Default Stream */
+#define   PCI_IDE_SEL_CTL_TEE_LIMITED	0x800000	  /* TEE-Limited Stream */
+#define   PCI_IDE_SEL_CTL_ID		__GENMASK(31, 24) /* Stream ID */
+#define   PCI_IDE_SEL_CTL_ID_MAX	255
+/* Selective IDE Stream Status Register */
+#define  PCI_IDE_SEL_STS		 0x08
+#define   PCI_IDE_SEL_STS_STATE		 __GENMASK(3, 0) /* Selective IDE Stream State */
+#define   PCI_IDE_SEL_STS_STATE_INSECURE 0
+#define   PCI_IDE_SEL_STS_STATE_SECURE	 2
+#define   PCI_IDE_SEL_STS_IDE_FAIL	 0x80000000	 /* IDE fail message received */
+/* IDE RID Association Register 1 */
+#define  PCI_IDE_SEL_RID_1		 0x0c
+#define   PCI_IDE_SEL_RID_1_LIMIT	 __GENMASK(23, 8)
+/* IDE RID Association Register 2 */
+#define  PCI_IDE_SEL_RID_2		0x10
+#define   PCI_IDE_SEL_RID_2_VALID	0x1
+#define   PCI_IDE_SEL_RID_2_BASE	__GENMASK(23, 8)
+#define   PCI_IDE_SEL_RID_2_SEG		__GENMASK(31, 24)
+/* Selective IDE Address Association Register Block, up to PCI_IDE_SEL_CAP_ASSOC_NUM */
+#define PCI_IDE_SEL_ADDR_BLOCK_SIZE	12
+#define  PCI_IDE_SEL_ADDR_1(x)		(20 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+#define   PCI_IDE_SEL_ADDR_1_VALID	0x1
+#define   PCI_IDE_SEL_ADDR_1_BASE_LOW	__GENMASK(19, 8)
+#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW	__GENMASK(31, 20)
+/* IDE Address Association Register 2 is "Memory Limit Upper" */
+#define  PCI_IDE_SEL_ADDR_2(x)		(24 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+/* IDE Address Association Register 3 is "Memory Base Upper" */
+#define  PCI_IDE_SEL_ADDR_3(x)		(28 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+#define PCI_IDE_SEL_BLOCK_SIZE(nr_assoc)  (20 + PCI_IDE_SEL_ADDR_BLOCK_SIZE * (nr_assoc))
+
 #endif /* LINUX_PCI_REGS_H */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
new file mode 100644
index 000000000000..26866edf91b4
--- /dev/null
+++ b/drivers/pci/ide.c
@@ -0,0 +1,88 @@
+// SPDX-License-Identifier: GPL-2.0
+/* Copyright(c) 2024-2025 Intel Corporation. All rights reserved. */
+
+/* PCIe r7.0 section 6.33 Integrity & Data Encryption (IDE) */
+
+#define dev_fmt(fmt) "PCI/IDE: " fmt
+#include <linux/bitfield.h>
+#include <linux/pci.h>
+#include <linux/pci_regs.h>
+
+#include "pci.h"
+
+static int __sel_ide_offset(u16 ide_cap, u8 nr_link_ide, u8 stream_index,
+			    u8 nr_ide_mem)
+{
+	u32 offset = ide_cap + PCI_IDE_LINK_STREAM_0 +
+		     nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE;
+
+	/*
+	 * Assume a constant number of address association resources per stream
+	 * index
+	 */
+	return offset + stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);
+}
+
+void pci_ide_init(struct pci_dev *pdev)
+{
+	u16 nr_link_ide, nr_ide_mem, nr_streams;
+	u16 ide_cap;
+	u32 val;
+
+	if (!pci_is_pcie(pdev))
+		return;
+
+	ide_cap = pci_find_ext_capability(pdev, PCI_EXT_CAP_ID_IDE);
+	if (!ide_cap)
+		return;
+
+	pci_read_config_dword(pdev, ide_cap + PCI_IDE_CAP, &val);
+	if ((val & PCI_IDE_CAP_SELECTIVE) == 0)
+		return;
+
+	/*
+	 * Require endpoint IDE capability to be paired with IDE Root Port IDE
+	 * capability.
+	 */
+	if (pci_pcie_type(pdev) == PCI_EXP_TYPE_ENDPOINT) {
+		struct pci_dev *rp = pcie_find_root_port(pdev);
+
+		if (!rp->ide_cap)
+			return;
+	}
+
+	pdev->ide_cfg = FIELD_GET(PCI_IDE_CAP_SEL_CFG, val);
+	pdev->ide_tee_limit = FIELD_GET(PCI_IDE_CAP_TEE_LIMITED, val);
+
+	if (val & PCI_IDE_CAP_LINK)
+		nr_link_ide = 1 + FIELD_GET(PCI_IDE_CAP_LINK_TC_NUM, val);
+	else
+		nr_link_ide = 0;
+
+	nr_ide_mem = 0;
+	nr_streams = 1 + FIELD_GET(PCI_IDE_CAP_SEL_NUM, val);
+	for (u16 i = 0; i < nr_streams; i++) {
+		int pos = __sel_ide_offset(ide_cap, nr_link_ide, i, nr_ide_mem);
+		int nr_assoc;
+		u32 val;
+
+		pci_read_config_dword(pdev, pos + PCI_IDE_SEL_CAP, &val);
+
+		/*
+		 * Let's not entertain streams that do not have a constant
+		 * number of address association blocks
+		 */
+		nr_assoc = FIELD_GET(PCI_IDE_SEL_CAP_ASSOC_NUM, val);
+		if (i && (nr_assoc != nr_ide_mem)) {
+			pci_info(pdev, "Unsupported Selective Stream %d capability, SKIP the rest\n", i);
+			nr_streams = i;
+			break;
+		}
+
+		nr_ide_mem = nr_assoc;
+	}
+
+	pdev->ide_cap = ide_cap;
+	pdev->nr_link_ide = nr_link_ide;
+	pdev->nr_ide_mem = nr_ide_mem;
+}
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 0ce98e18b5a8..4c55020f3ddf 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2667,6 +2667,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
+	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);

---

## [4] Dan Williams — 2025-10-31
*Subject: [PATCH v8 3/9] PCI: Introduce pci_walk_bus_reverse(), for_each_pci_dev_reverse()*

PCI/TSM, the PCI core functionality for the PCIe TEE Device Interface
Security Protocol (TDISP), has a need to walk all subordinate functions of
a Device Security Manager (DSM) to setup a device security context. A DSM
is physical function 0 of multi-function or SR-IOV device endpoint, or it
is an upstream switch port.

In error scenarios or when a TEE Security Manager (TSM) device is removed
it needs to unwind all established DSM contexts.

Introduce reverse versions of PCI device iteration helpers to mirror the
setup path and ensure that dependent children are handled before parents.

Cc: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/device/bus.h |  3 ++
 include/linux/pci.h        | 11 +++++++
 drivers/base/bus.c         | 38 +++++++++++++++++++++++
 drivers/pci/bus.c          | 39 ++++++++++++++++++++++++
 drivers/pci/search.c       | 62 +++++++++++++++++++++++++++++++++-----
 5 files changed, 145 insertions(+), 8 deletions(-)

diff --git a/include/linux/device/bus.h b/include/linux/device/bus.h
index f5a56efd2bd6..99b1002b3e31 100644
--- a/include/linux/device/bus.h
+++ b/include/linux/device/bus.h
@@ -150,6 +150,9 @@ int bus_for_each_dev(const struct bus_type *bus, struct device *start,
 		     void *data, device_iter_t fn);
 struct device *bus_find_device(const struct bus_type *bus, struct device *start,
 			       const void *data, device_match_t match);
+struct device *bus_find_device_reverse(const struct bus_type *bus,
+				       struct device *start, const void *data,
+				       device_match_t match);
 /**
  * bus_find_device_by_name - device iterator for locating a particular device
  * of a specific name.
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 4402ca931124..b6a12a82be12 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -582,6 +582,8 @@ struct pci_dev *pci_alloc_dev(struct pci_bus *bus);
 
 #define	to_pci_dev(n) container_of(n, struct pci_dev, dev)
 #define for_each_pci_dev(d) while ((d = pci_get_device(PCI_ANY_ID, PCI_ANY_ID, d)) != NULL)
+#define for_each_pci_dev_reverse(d) \
+	while ((d = pci_get_device_reverse(PCI_ANY_ID, PCI_ANY_ID, d)) != NULL)
 
 static inline int pci_channel_offline(struct pci_dev *pdev)
 {
@@ -1242,6 +1244,8 @@ u64 pci_get_dsn(struct pci_dev *dev);
 
 struct pci_dev *pci_get_device(unsigned int vendor, unsigned int device,
 			       struct pci_dev *from);
+struct pci_dev *pci_get_device_reverse(unsigned int vendor, unsigned int device,
+				       struct pci_dev *from);
 struct pci_dev *pci_get_subsys(unsigned int vendor, unsigned int device,
 			       unsigned int ss_vendor, unsigned int ss_device,
 			       struct pci_dev *from);
@@ -1661,6 +1665,8 @@ int pci_scan_bridge(struct pci_bus *bus, struct pci_dev *dev, int max,
 
 void pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void *),
 		  void *userdata);
+void pci_walk_bus_reverse(struct pci_bus *top,
+			  int (*cb)(struct pci_dev *, void *), void *userdata);
 int pci_cfg_space_size(struct pci_dev *dev);
 unsigned char pci_bus_max_busnr(struct pci_bus *bus);
 resource_size_t pcibios_window_alignment(struct pci_bus *bus,
@@ -2049,6 +2055,11 @@ static inline struct pci_dev *pci_get_device(unsigned int vendor,
 					     struct pci_dev *from)
 { return NULL; }
 
+static inline struct pci_dev *pci_get_device_reverse(unsigned int vendor,
+						     unsigned int device,
+						     struct pci_dev *from)
+{ return NULL; }
+
 static inline struct pci_dev *pci_get_subsys(unsigned int vendor,
 					     unsigned int device,
 					     unsigned int ss_vendor,
diff --git a/drivers/base/bus.c b/drivers/base/bus.c
index 5e75e1bce551..d19dae8f9d1b 100644
--- a/drivers/base/bus.c
+++ b/drivers/base/bus.c
@@ -334,6 +334,19 @@ static struct device *next_device(struct klist_iter *i)
 	return dev;
 }
 
+static struct device *prev_device(struct klist_iter *i)
+{
+	struct klist_node *n = klist_prev(i);
+	struct device *dev = NULL;
+	struct device_private *dev_prv;
+
+	if (n) {
+		dev_prv = to_device_private_bus(n);
+		dev = dev_prv->device;
+	}
+	return dev;
+}
+
 /**
  * bus_for_each_dev - device iterator.
  * @bus: bus type.
@@ -414,6 +427,31 @@ struct device *bus_find_device(const struct bus_type *bus,
 }
 EXPORT_SYMBOL_GPL(bus_find_device);
 
+struct device *bus_find_device_reverse(const struct bus_type *bus,
+				       struct device *start, const void *data,
+				       device_match_t match)
+{
+	struct subsys_private *sp = bus_to_subsys(bus);
+	struct klist_iter i;
+	struct device *dev;
+
+	if (!sp)
+		return NULL;
+
+	klist_iter_init_node(&sp->klist_devices, &i,
+			     (start ? &start->p->knode_bus : NULL));
+	while ((dev = prev_device(&i))) {
+		if (match(dev, data)) {
+			get_device(dev);
+			break;
+		}
+	}
+	klist_iter_exit(&i);
+	subsys_put(sp);
+	return dev;
+}
+EXPORT_SYMBOL_GPL(bus_find_device_reverse);
+
 static struct device_driver *next_driver(struct klist_iter *i)
 {
 	struct klist_node *n = klist_next(i);
diff --git a/drivers/pci/bus.c b/drivers/pci/bus.c
index f26aec6ff588..b8b17f825bc0 100644
--- a/drivers/pci/bus.c
+++ b/drivers/pci/bus.c
@@ -8,6 +8,7 @@
  */
 #include <linux/module.h>
 #include <linux/kernel.h>
+#include <linux/cleanup.h>
 #include <linux/pci.h>
 #include <linux/errno.h>
 #include <linux/ioport.h>
@@ -432,6 +433,27 @@ static int __pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void
 	return ret;
 }
 
+static int __pci_walk_bus_reverse(struct pci_bus *top,
+				  int (*cb)(struct pci_dev *, void *),
+				  void *userdata)
+{
+	struct pci_dev *dev;
+	int ret = 0;
+
+	list_for_each_entry_reverse(dev, &top->devices, bus_list) {
+		if (dev->subordinate) {
+			ret = __pci_walk_bus_reverse(dev->subordinate, cb,
+						     userdata);
+			if (ret)
+				break;
+		}
+		ret = cb(dev, userdata);
+		if (ret)
+			break;
+	}
+	return ret;
+}
+
 /**
  *  pci_walk_bus - walk devices on/under bus, calling callback.
  *  @top: bus whose devices should be walked
@@ -453,6 +475,23 @@ void pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void *), void
 }
 EXPORT_SYMBOL_GPL(pci_walk_bus);
 
+/**
+ * pci_walk_bus_reverse - walk devices on/under bus, calling callback.
+ * @top: bus whose devices should be walked
+ * @cb: callback to be called for each device found
+ * @userdata: arbitrary pointer to be passed to callback
+ *
+ * Same semantics as pci_walk_bus(), but walks the bus in reverse order.
+ */
+void pci_walk_bus_reverse(struct pci_bus *top,
+			  int (*cb)(struct pci_dev *, void *), void *userdata)
+{
+	down_read(&pci_bus_sem);
+	__pci_walk_bus_reverse(top, cb, userdata);
+	up_read(&pci_bus_sem);
+}
+EXPORT_SYMBOL_GPL(pci_walk_bus_reverse);
+
 void pci_walk_bus_locked(struct pci_bus *top, int (*cb)(struct pci_dev *, void *), void *userdata)
 {
 	lockdep_assert_held(&pci_bus_sem);
diff --git a/drivers/pci/search.c b/drivers/pci/search.c
index 53840634fbfc..e6e84dc62e82 100644
--- a/drivers/pci/search.c
+++ b/drivers/pci/search.c
@@ -282,6 +282,45 @@ static struct pci_dev *pci_get_dev_by_id(const struct pci_device_id *id,
 	return pdev;
 }
 
+static struct pci_dev *pci_get_dev_by_id_reverse(const struct pci_device_id *id,
+						 struct pci_dev *from)
+{
+	struct device *dev;
+	struct device *dev_start = NULL;
+	struct pci_dev *pdev = NULL;
+
+	if (from)
+		dev_start = &from->dev;
+	dev = bus_find_device_reverse(&pci_bus_type, dev_start, (void *)id,
+				      match_pci_dev_by_id);
+	if (dev)
+		pdev = to_pci_dev(dev);
+	pci_dev_put(from);
+	return pdev;
+}
+
+enum pci_search_direction {
+	PCI_SEARCH_FORWARD,
+	PCI_SEARCH_REVERSE,
+};
+
+static struct pci_dev *__pci_get_subsys(unsigned int vendor, unsigned int device,
+				 unsigned int ss_vendor, unsigned int ss_device,
+				 struct pci_dev *from, enum pci_search_direction dir)
+{
+	struct pci_device_id id = {
+		.vendor = vendor,
+		.device = device,
+		.subvendor = ss_vendor,
+		.subdevice = ss_device,
+	};
+
+	if (dir == PCI_SEARCH_FORWARD)
+		return pci_get_dev_by_id(&id, from);
+	else
+		return pci_get_dev_by_id_reverse(&id, from);
+}
+
 /**
  * pci_get_subsys - begin or continue searching for a PCI device by vendor/subvendor/device/subdevice id
  * @vendor: PCI vendor id to match, or %PCI_ANY_ID to match all vendor ids
@@ -302,14 +341,8 @@ struct pci_dev *pci_get_subsys(unsigned int vendor, unsigned int device,
 			       unsigned int ss_vendor, unsigned int ss_device,
 			       struct pci_dev *from)
 {
-	struct pci_device_id id = {
-		.vendor = vendor,
-		.device = device,
-		.subvendor = ss_vendor,
-		.subdevice = ss_device,
-	};
-
-	return pci_get_dev_by_id(&id, from);
+	return __pci_get_subsys(vendor, device, ss_vendor, ss_device, from,
+				PCI_SEARCH_FORWARD);
 }
 EXPORT_SYMBOL(pci_get_subsys);
 
@@ -334,6 +367,19 @@ struct pci_dev *pci_get_device(unsigned int vendor, unsigned int device,
 }
 EXPORT_SYMBOL(pci_get_device);
 
+/*
+ * Same semantics as pci_get_device(), except walks the PCI device list
+ * in reverse discovery order.
+ */
+struct pci_dev *pci_get_device_reverse(unsigned int vendor,
+				       unsigned int device,
+				       struct pci_dev *from)
+{
+	return __pci_get_subsys(vendor, device, PCI_ANY_ID, PCI_ANY_ID, from,
+				PCI_SEARCH_REVERSE);
+}
+EXPORT_SYMBOL(pci_get_device_reverse);
+
 /**
  * pci_get_class - begin or continue searching for a PCI device by class
  * @class: search for a PCI device with this class designation

---

## [5] Dan Williams — 2025-10-31
*Subject: [PATCH v8 4/9] PCI/TSM: Establish Secure Sessions and Link Encryption*

The PCIe 7.0 specification, section 11, defines the Trusted Execution
Environment (TEE) Device Interface Security Protocol (TDISP).  This
protocol definition builds upon Component Measurement and Authentication
(CMA), and link Integrity and Data Encryption (IDE). It adds support for
assigning devices (PCI physical or virtual function) to a confidential VM
such that the assigned device is enabled to access guest private memory
protected by technologies like Intel TDX, AMD SEV-SNP, RISCV COVE, or ARM
CCA.

The "TSM" (TEE Security Manager) is a concept in the TDISP specification
of an agent that mediates between a "DSM" (Device Security Manager) and
system software in both a VMM and a confidential VM. A VMM uses TSM ABIs
to setup link security and assign devices. A confidential VM uses TSM
ABIs to transition an assigned device into the TDISP "RUN" state and
validate its configuration. From a Linux perspective the TSM abstracts
many of the details of TDISP, IDE, and CMA. Some of those details leak
through at times, but for the most part TDISP is an internal
implementation detail of the TSM.

CONFIG_PCI_TSM adds an "authenticated" attribute and "tsm/" subdirectory
to pci-sysfs. Consider that the TSM driver may itself be a PCI driver.
Userspace can watch for the arrival of a "TSM" device,
/sys/class/tsm/tsm0/uevent KOBJ_CHANGE, to know when the PCI core has
initialized TSM services.

The operations that can be executed against a PCI device are split into
two mutually exclusive operation sets, "Link" and "Security" (struct
pci_tsm_{link,security}_ops). The "Link" operations manage physical link
security properties and communication with the device's Device Security
Manager firmware. These are the host side operations in TDISP. The
"Security" operations coordinate the security state of the assigned
virtual device (TDI). These are the guest side operations in TDISP.

Only "link" (Secure Session and physical Link Encryption) operations are
defined at this stage. There are placeholders for the device security
(Trusted Computing Base entry / exit) operations.

The locking allows for multiple devices to be executing commands
simultaneously, one outstanding command per-device and an rwsem
synchronizes the implementation relative to TSM registration/unregistration
events.

Thanks to Wu Hao for his work on an early draft of this support.

Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Kconfig                     |  15 +
 drivers/pci/Makefile                    |   1 +
 Documentation/ABI/testing/sysfs-bus-pci |  51 ++
 Documentation/driver-api/pci/index.rst  |   1 +
 Documentation/driver-api/pci/tsm.rst    |  21 +
 drivers/pci/pci.h                       |  10 +
 include/linux/pci-doe.h                 |   4 +
 include/linux/pci-tsm.h                 | 157 ++++++
 include/linux/pci.h                     |   3 +
 include/linux/tsm.h                     |   5 +-
 include/uapi/linux/pci_regs.h           |   1 +
 drivers/pci/doe.c                       |   2 -
 drivers/pci/pci-sysfs.c                 |   4 +
 drivers/pci/probe.c                     |   3 +
 drivers/pci/remove.c                    |   6 +
 drivers/pci/tsm.c                       | 643 ++++++++++++++++++++++++
 drivers/virt/coco/tsm-core.c            |  46 +-
 MAINTAINERS                             |   4 +-
 18 files changed, 971 insertions(+), 6 deletions(-)
 create mode 100644 Documentation/driver-api/pci/tsm.rst
 create mode 100644 include/linux/pci-tsm.h
 create mode 100644 drivers/pci/tsm.c

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index b28423e2057f..00b0210e1f1d 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -125,6 +125,21 @@ config PCI_ATS
 config PCI_IDE
 	bool
 
+config PCI_TSM
+	bool "PCI TSM: Device security protocol support"
+	select PCI_IDE
+	select PCI_DOE
+	select TSM
+	help
+	  The TEE (Trusted Execution Environment) Device Interface
+	  Security Protocol (TDISP) defines a "TSM" as a platform agent
+	  that manages device authentication, link encryption, link
+	  integrity protection, and assignment of PCI device functions
+	  (virtual or physical) to confidential computing VMs that can
+	  access (DMA) guest private memory.
+
+	  Enable a platform TSM driver to use this capability.
+
 config PCI_DOE
 	bool "Enable PCI Data Object Exchange (DOE) support"
 	help
diff --git a/drivers/pci/Makefile b/drivers/pci/Makefile
index 6612256fd37d..2c545f877062 100644
--- a/drivers/pci/Makefile
+++ b/drivers/pci/Makefile
@@ -35,6 +35,7 @@ obj-$(CONFIG_XEN_PCIDEV_FRONTEND) += xen-pcifront.o
 obj-$(CONFIG_VGA_ARB)		+= vgaarb.o
 obj-$(CONFIG_PCI_DOE)		+= doe.o
 obj-$(CONFIG_PCI_IDE)		+= ide.o
+obj-$(CONFIG_PCI_TSM)		+= tsm.o
 obj-$(CONFIG_PCI_DYNAMIC_OF_NODES) += of_property.o
 obj-$(CONFIG_PCI_NPEM)		+= npem.o
 obj-$(CONFIG_PCIE_TPH)		+= tph.o
diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 92debe879ffb..6ffe02f854d6 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -621,3 +621,54 @@ Description:
 		number extended capability. The file is read only and due to
 		the possible sensitivity of accessible serial numbers, admin
 		only.
+
+What:		/sys/bus/pci/devices/.../tsm/
+Contact:	linux-coco@lists.linux.dev
+Description:
+		This directory only appears if a physical device function
+		supports authentication (PCIe CMA-SPDM), interface security
+		(PCIe TDISP), and is accepted for secure operation by the
+		platform TSM driver. This attribute directory appears
+		dynamically after the platform TSM driver loads. So, only after
+		the /sys/class/tsm/tsm0 device arrives can tools assume that
+		devices without a tsm/ attribute directory will never have one;
+		before that, the security capabilities of the device relative to
+		the platform TSM are unknown. See
+		Documentation/ABI/testing/sysfs-class-tsm.
+
+What:		/sys/bus/pci/devices/.../tsm/connect
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) Write the name of a TSM (TEE Security Manager) device from
+		/sys/class/tsm to this file to establish a connection with the
+		device.  This typically includes an SPDM (DMTF Security
+		Protocols and Data Models) session over PCIe DOE (Data Object
+		Exchange) and may also include PCIe IDE (Integrity and Data
+		Encryption) establishment. Reads from this attribute return the
+		name of the connected TSM or the empty string if not
+		connected. A TSM device signals its readiness to accept PCI
+		connection via a KOBJ_CHANGE event.
+
+What:		/sys/bus/pci/devices/.../tsm/disconnect
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(WO) Write the name of the TSM device that was specified
+		to 'connect' to teardown the connection.
+
+What:		/sys/bus/pci/devices/.../authenticated
+Contact:	linux-pci@vger.kernel.org
+Description:
+		When the device's tsm/ directory is present device
+		authentication (PCIe CMA-SPDM) and link encryption (PCIe IDE)
+		are handled by the platform TSM (TEE Security Manager). When the
+		tsm/ directory is not present this attribute reflects only the
+		native CMA-SPDM authentication state with the kernel's
+		certificate store.
+
+		If the attribute is not present, it indicates that
+		authentication is unsupported by the device, or the TSM has no
+		available authentication methods for the device.
+
+		When present and the tsm/ attribute directory is present, the
+		authenticated attribute is an alias for the device 'connect'
+		state. See the 'tsm/connect' attribute for more details.
diff --git a/Documentation/driver-api/pci/index.rst b/Documentation/driver-api/pci/index.rst
index a38e475cdbe3..9e1b801d0f74 100644
--- a/Documentation/driver-api/pci/index.rst
+++ b/Documentation/driver-api/pci/index.rst
@@ -10,6 +10,7 @@ The Linux PCI driver implementer's API guide
 
    pci
    p2pdma
+   tsm
 
 .. only::  subproject and html
 
diff --git a/Documentation/driver-api/pci/tsm.rst b/Documentation/driver-api/pci/tsm.rst
new file mode 100644
index 000000000000..232b92bec93f
--- /dev/null
+++ b/Documentation/driver-api/pci/tsm.rst
@@ -0,0 +1,21 @@
+.. SPDX-License-Identifier: GPL-2.0
+.. include:: <isonum.txt>
+
+========================================================
+PCI Trusted Execution Environment Security Manager (TSM)
+========================================================
+
+Subsystem Interfaces
+====================
+
+.. kernel-doc:: include/linux/pci-ide.h
+   :internal:
+
+.. kernel-doc:: drivers/pci/ide.c
+   :export:
+
+.. kernel-doc:: include/linux/pci-tsm.h
+   :internal:
+
+.. kernel-doc:: drivers/pci/tsm.c
+   :export:
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 86ef13e7cece..6e4cc1c9aa58 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -619,6 +619,16 @@ void pci_ide_init(struct pci_dev *dev);
 static inline void pci_ide_init(struct pci_dev *dev) { }
 #endif
 
+#ifdef CONFIG_PCI_TSM
+void pci_tsm_init(struct pci_dev *pdev);
+void pci_tsm_destroy(struct pci_dev *pdev);
+extern const struct attribute_group pci_tsm_attr_group;
+extern const struct attribute_group pci_tsm_auth_attr_group;
+#else
+static inline void pci_tsm_init(struct pci_dev *pdev) { }
+static inline void pci_tsm_destroy(struct pci_dev *pdev) { }
+#endif
+
 /**
  * pci_dev_set_io_state - Set the new error state if possible.
  *
diff --git a/include/linux/pci-doe.h b/include/linux/pci-doe.h
index 1f14aed4354b..bd4346a7c4e7 100644
--- a/include/linux/pci-doe.h
+++ b/include/linux/pci-doe.h
@@ -15,6 +15,10 @@
 
 struct pci_doe_mb;
 
+#define PCI_DOE_FEATURE_DISCOVERY 0
+#define PCI_DOE_FEATURE_CMA 1
+#define PCI_DOE_FEATURE_SSESSION 2
+
 struct pci_doe_mb *pci_find_doe_mailbox(struct pci_dev *pdev, u16 vendor,
 					u8 type);
 
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
new file mode 100644
index 000000000000..e921d30f9b6c
--- /dev/null
+++ b/include/linux/pci-tsm.h
@@ -0,0 +1,157 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef __PCI_TSM_H
+#define __PCI_TSM_H
+#include <linux/mutex.h>
+#include <linux/pci.h>
+
+struct pci_tsm;
+struct tsm_dev;
+
+/*
+ * struct pci_tsm_ops - manage confidential links and security state
+ * @link_ops: Coordinate PCIe SPDM and IDE establishment via a platform TSM.
+ *	      Provide a secure session transport for TDISP state management
+ *	      (typically bare metal physical function operations).
+ * @devsec_ops: Lock, unlock, and interrogate the security state of the
+ *		function via the platform TSM (typically virtual function
+ *		operations).
+ *
+ * This operations are mutually exclusive either a tsm_dev instance
+ * manages physical link properties or it manages function security
+ * states like TDISP lock/unlock.
+ */
+struct pci_tsm_ops {
+	/*
+	 * struct pci_tsm_link_ops - Manage physical link and the TSM/DSM session
+	 * @probe: establish context with the TSM (allocate / wrap 'struct
+	 *	   pci_tsm') for follow-on link operations
+	 * @remove: destroy link operations context
+	 * @connect: establish / validate a secure connection (e.g. IDE)
+	 *	     with the device
+	 * @disconnect: teardown the secure link
+	 *
+	 * Context: @probe, @remove, @connect, and @disconnect run under
+	 * pci_tsm_rwsem held for write to sync with TSM unregistration and
+	 * mutual exclusion of @connect and @disconnect. @connect and
+	 * @disconnect additionally run under the DSM lock (struct
+	 * pci_tsm_pf0::lock) as well as @probe and @remove of the subfunctions.
+	 */
+	struct_group_tagged(pci_tsm_link_ops, link_ops,
+		struct pci_tsm *(*probe)(struct tsm_dev *tsm_dev,
+					 struct pci_dev *pdev);
+		void (*remove)(struct pci_tsm *tsm);
+		int (*connect)(struct pci_dev *pdev);
+		void (*disconnect)(struct pci_dev *pdev);
+	);
+
+	/*
+	 * struct pci_tsm_devsec_ops - Manage the security state of the function
+	 * @lock: establish context with the TSM (allocate / wrap 'struct
+	 *	  pci_tsm') for follow-on security state transitions from the
+	 *	  LOCKED state
+	 * @unlock: destroy TSM context and return device to UNLOCKED state
+	 *
+	 * Context: @lock and @unlock run under pci_tsm_rwsem held for write to
+	 * sync with TSM unregistration and each other
+	 */
+	struct_group_tagged(pci_tsm_devsec_ops, devsec_ops,
+		struct pci_tsm *(*lock)(struct tsm_dev *tsm_dev,
+					struct pci_dev *pdev);
+		void (*unlock)(struct pci_tsm *tsm);
+	);
+};
+
+/**
+ * struct pci_tsm - Core TSM context for a given PCIe endpoint
+ * @pdev: Back ref to device function, distinguishes type of pci_tsm context
+ * @dsm_dev: PCI Device Security Manager for link operations on @pdev
+ * @tsm_dev: PCI TEE Security Manager device for Link Confidentiality or Device
+ *	     Function Security operations
+ *
+ * This structure is wrapped by low level TSM driver data and returned by
+ * probe()/lock(), it is freed by the corresponding remove()/unlock().
+ *
+ * For link operations it serves to cache the association between a Device
+ * Security Manager (DSM) and the functions that manager can assign to a TVM.
+ * That can be "self", for assigning function0 of a TEE I/O device, a
+ * sub-function (SR-IOV virtual function, or non-function0
+ * multifunction-device), or a downstream endpoint (PCIe upstream switch-port as
+ * DSM).
+ */
+struct pci_tsm {
+	struct pci_dev *pdev;
+	struct pci_dev *dsm_dev;
+	struct tsm_dev *tsm_dev;
+};
+
+/**
+ * struct pci_tsm_pf0 - Physical Function 0 TDISP link context
+ * @base_tsm: generic core "tsm" context
+ * @lock: mutual exclustion for pci_tsm_ops invocation
+ * @doe_mb: PCIe Data Object Exchange mailbox
+ */
+struct pci_tsm_pf0 {
+	struct pci_tsm base_tsm;
+	struct mutex lock;
+	struct pci_doe_mb *doe_mb;
+};
+
+/* physical function0 and capable of 'connect' */
+static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
+{
+	if (!pdev)
+		return false;
+
+	if (!pci_is_pcie(pdev))
+		return false;
+
+	if (pdev->is_virtfn)
+		return false;
+
+	/*
+	 * Allow for a Device Security Manager (DSM) associated with function0
+	 * of an Endpoint to coordinate TDISP requests for other functions
+	 * (physical or virtual) of the device, or allow for an Upstream Port
+	 * DSM to accept TDISP requests for the Endpoints downstream of the
+	 * switch.
+	 */
+	switch (pci_pcie_type(pdev)) {
+	case PCI_EXP_TYPE_ENDPOINT:
+	case PCI_EXP_TYPE_UPSTREAM:
+	case PCI_EXP_TYPE_RC_END:
+		if (pdev->ide_cap || (pdev->devcap & PCI_EXP_DEVCAP_TEE))
+			break;
+		fallthrough;
+	default:
+		return false;
+	}
+
+	return PCI_FUNC(pdev->devfn) == 0;
+}
+
+#ifdef CONFIG_PCI_TSM
+int pci_tsm_register(struct tsm_dev *tsm_dev);
+void pci_tsm_unregister(struct tsm_dev *tsm_dev);
+int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
+			     struct tsm_dev *tsm_dev);
+int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
+			    struct tsm_dev *tsm_dev);
+void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
+int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,
+			 size_t req_sz, void *resp, size_t resp_sz);
+#else
+static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
+{
+	return 0;
+}
+static inline void pci_tsm_unregister(struct tsm_dev *tsm_dev)
+{
+}
+static inline int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type,
+				       const void *req, size_t req_sz,
+				       void *resp, size_t resp_sz)
+{
+	return -ENXIO;
+}
+#endif
+#endif /*__PCI_TSM_H */
diff --git a/include/linux/pci.h b/include/linux/pci.h
index b6a12a82be12..2f9c0cb6a50a 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -546,6 +546,9 @@ struct pci_dev {
 	u8		nr_link_ide;	/* Link Stream count (Selective Stream offset) */
 	unsigned int	ide_cfg:1;	/* Config cycles over IDE */
 	unsigned int	ide_tee_limit:1; /* Disallow T=0 traffic over IDE */
+#endif
+#ifdef CONFIG_PCI_TSM
+	struct pci_tsm *tsm;		/* TSM operation state */
 #endif
 	u16		acs_cap;	/* ACS Capability offset */
 	u8		supported_speeds; /* Supported Link Speeds Vector */
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index cd97c63ffa32..22e05b2aac69 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -108,9 +108,11 @@ struct tsm_report_ops {
 	bool (*report_bin_attr_visible)(int n);
 };
 
+struct pci_tsm_ops;
 struct tsm_dev {
 	struct device dev;
 	int id;
+	const struct pci_tsm_ops *pci_ops;
 };
 
 DEFINE_FREE(put_tsm_dev, struct tsm_dev *,
@@ -118,6 +120,7 @@ DEFINE_FREE(put_tsm_dev, struct tsm_dev *,
 
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
-struct tsm_dev *tsm_register(struct device *parent);
+struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
+struct tsm_dev *find_tsm_dev(int id);
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 05bd22d9e352..f2759c1097bc 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -503,6 +503,7 @@
 #define  PCI_EXP_DEVCAP_PWR_VAL	0x03fc0000 /* Slot Power Limit Value */
 #define  PCI_EXP_DEVCAP_PWR_SCL	0x0c000000 /* Slot Power Limit Scale */
 #define  PCI_EXP_DEVCAP_FLR     0x10000000 /* Function Level Reset */
+#define  PCI_EXP_DEVCAP_TEE     0x40000000 /* TEE I/O (TDISP) Support */
 #define PCI_EXP_DEVCTL		0x08	/* Device Control */
 #define  PCI_EXP_DEVCTL_CERE	0x0001	/* Correctable Error Reporting En. */
 #define  PCI_EXP_DEVCTL_NFERE	0x0002	/* Non-Fatal Error Reporting Enable */
diff --git a/drivers/pci/doe.c b/drivers/pci/doe.c
index aae9a8a00406..62be9c8dbc52 100644
--- a/drivers/pci/doe.c
+++ b/drivers/pci/doe.c
@@ -24,8 +24,6 @@
 
 #include "pci.h"
 
-#define PCI_DOE_FEATURE_DISCOVERY 0
-
 /* Timeout of 1 second from 6.30.2 Operation, PCI Spec r6.0 */
 #define PCI_DOE_TIMEOUT HZ
 #define PCI_DOE_POLL_INTERVAL	(PCI_DOE_TIMEOUT / 128)
diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
index 9d6f74bd95f8..7f9237a926c2 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1868,6 +1868,10 @@ const struct attribute_group *pci_dev_attr_groups[] = {
 #endif
 #ifdef CONFIG_PCI_DOE
 	&pci_doe_sysfs_group,
+#endif
+#ifdef CONFIG_PCI_TSM
+	&pci_tsm_auth_attr_group,
+	&pci_tsm_attr_group,
 #endif
 	NULL,
 };
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 4c55020f3ddf..d1467348c169 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2763,6 +2763,9 @@ void pci_device_add(struct pci_dev *dev, struct pci_bus *bus)
 	ret = device_add(&dev->dev);
 	WARN_ON(ret < 0);
 
+	/* Establish pdev->tsm for newly added (e.g. new SR-IOV VFs) */
+	pci_tsm_init(dev);
+
 	pci_npem_create(dev);
 
 	pci_doe_sysfs_init(dev);
diff --git a/drivers/pci/remove.c b/drivers/pci/remove.c
index ce5c25adef55..803391892c4a 100644
--- a/drivers/pci/remove.c
+++ b/drivers/pci/remove.c
@@ -57,6 +57,12 @@ static void pci_destroy_dev(struct pci_dev *dev)
 	pci_doe_sysfs_teardown(dev);
 	pci_npem_remove(dev);
 
+	/*
+	 * While device is in D0 drop the device from TSM link operations
+	 * including unbind and disconnect (IDE + SPDM teardown).
+	 */
+	pci_tsm_destroy(dev);
+
 	device_del(&dev->dev);
 
 	down_write(&pci_bus_sem);
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
new file mode 100644
index 000000000000..6a2849f77adc
--- /dev/null
+++ b/drivers/pci/tsm.c
@@ -0,0 +1,643 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Interface with platform TEE Security Manager (TSM) objects as defined by
+ * PCIe r7.0 section 11 TEE Device Interface Security Protocol (TDISP)
+ *
+ * Copyright(c) 2024-2025 Intel Corporation. All rights reserved.
+ */
+
+#define dev_fmt(fmt) "PCI/TSM: " fmt
+
+#include <linux/bitfield.h>
+#include <linux/pci.h>
+#include <linux/pci-doe.h>
+#include <linux/pci-tsm.h>
+#include <linux/sysfs.h>
+#include <linux/tsm.h>
+#include <linux/xarray.h>
+#include "pci.h"
+
+/*
+ * Provide a read/write lock against the init / exit of pdev tsm
+ * capabilities and arrival/departure of a TSM instance
+ */
+static DECLARE_RWSEM(pci_tsm_rwsem);
+
+/*
+ * Count of TSMs registered that support physical link operations vs device
+ * security state management.
+ */
+static int pci_tsm_link_count;
+static int pci_tsm_devsec_count;
+
+static const struct pci_tsm_ops *to_pci_tsm_ops(struct pci_tsm *tsm)
+{
+	return tsm->tsm_dev->pci_ops;
+}
+
+static inline bool is_dsm(struct pci_dev *pdev)
+{
+	return pdev->tsm && pdev->tsm->dsm_dev == pdev;
+}
+
+static inline bool has_tee(struct pci_dev *pdev)
+{
+	return pdev->devcap & PCI_EXP_DEVCAP_TEE;
+}
+
+/* 'struct pci_tsm_pf0' wraps 'struct pci_tsm' when ->dsm_dev == ->pdev (self) */
+static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *tsm)
+{
+	/*
+	 * All "link" TSM contexts reference the device that hosts the DSM
+	 * interface for a set of devices. Walk to the DSM device and cast its
+	 * ->tsm context to a 'struct pci_tsm_pf0 *'.
+	 */
+	struct pci_dev *pf0 = tsm->dsm_dev;
+
+	if (!is_pci_tsm_pf0(pf0) || !is_dsm(pf0)) {
+		pci_WARN_ONCE(tsm->pdev, 1, "invalid context object\n");
+		return NULL;
+	}
+
+	return container_of(pf0->tsm, struct pci_tsm_pf0, base_tsm);
+}
+
+static void tsm_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev;
+
+	if (!tsm)
+		return;
+
+	pdev = tsm->pdev;
+	to_pci_tsm_ops(tsm)->remove(tsm);
+	pdev->tsm = NULL;
+}
+DEFINE_FREE(tsm_remove, struct pci_tsm *, if (_T) tsm_remove(_T))
+
+static void pci_tsm_walk_fns(struct pci_dev *pdev,
+			     int (*cb)(struct pci_dev *pdev, void *data),
+			     void *data)
+{
+	/* Walk subordinate physical functions */
+	for (int i = 0; i < 8; i++) {
+		struct pci_dev *pf __free(pci_dev_put) = pci_get_slot(
+			pdev->bus, PCI_DEVFN(PCI_SLOT(pdev->devfn), i));
+
+		if (!pf)
+			continue;
+
+		/* on entry function 0 has already run @cb */
+		if (i > 0)
+			cb(pf, data);
+
+		/* walk virtual functions of each pf */
+		for (int j = 0; j < pci_num_vf(pf); j++) {
+			struct pci_dev *vf __free(pci_dev_put) =
+				pci_get_domain_bus_and_slot(
+					pci_domain_nr(pf->bus),
+					pci_iov_virtfn_bus(pf, j),
+					pci_iov_virtfn_devfn(pf, j));
+
+			if (!vf)
+				continue;
+
+			cb(vf, data);
+		}
+	}
+
+	/*
+	 * Walk downstream devices, assumes that an upstream DSM is
+	 * limited to downstream physical functions
+	 */
+	if (pci_pcie_type(pdev) == PCI_EXP_TYPE_UPSTREAM && is_dsm(pdev))
+		pci_walk_bus(pdev->subordinate, cb, data);
+}
+
+static void pci_tsm_walk_fns_reverse(struct pci_dev *pdev,
+				     int (*cb)(struct pci_dev *pdev,
+					       void *data),
+				     void *data)
+{
+	/* Reverse walk downstream devices */
+	if (pci_pcie_type(pdev) == PCI_EXP_TYPE_UPSTREAM && is_dsm(pdev))
+		pci_walk_bus_reverse(pdev->subordinate, cb, data);
+
+	/* Reverse walk subordinate physical functions */
+	for (int i = 7; i >= 0; i--) {
+		struct pci_dev *pf __free(pci_dev_put) = pci_get_slot(
+			pdev->bus, PCI_DEVFN(PCI_SLOT(pdev->devfn), i));
+
+		if (!pf)
+			continue;
+
+		/* reverse walk virtual functions */
+		for (int j = pci_num_vf(pf) - 1; j >= 0; j--) {
+			struct pci_dev *vf __free(pci_dev_put) =
+				pci_get_domain_bus_and_slot(
+					pci_domain_nr(pf->bus),
+					pci_iov_virtfn_bus(pf, j),
+					pci_iov_virtfn_devfn(pf, j));
+
+			if (!vf)
+				continue;
+			cb(vf, data);
+		}
+
+		/* on exit, caller will run @cb on function 0 */
+		if (i > 0)
+			cb(pf, data);
+	}
+}
+
+static int probe_fn(struct pci_dev *pdev, void *dsm)
+{
+	struct pci_dev *dsm_dev = dsm;
+	const struct pci_tsm_ops *ops = to_pci_tsm_ops(dsm_dev->tsm);
+
+	pdev->tsm = ops->probe(dsm_dev->tsm->tsm_dev, pdev);
+	pci_dbg(pdev, "setup TSM context: DSM: %s status: %s\n",
+		pci_name(dsm_dev), pdev->tsm ? "success" : "failed");
+	return 0;
+}
+
+static int pci_tsm_connect(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
+{
+	int rc;
+	struct pci_tsm_pf0 *tsm_pf0;
+	const struct pci_tsm_ops *ops = tsm_dev->pci_ops;
+	struct pci_tsm *pci_tsm __free(tsm_remove) = ops->probe(tsm_dev, pdev);
+
+	/* connect() mutually exclusive with subfunction pci_tsm_init() */
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+
+	if (!pci_tsm)
+		return -ENXIO;
+
+	pdev->tsm = pci_tsm;
+	tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+
+	/* mutex_intr assumes connect() is always sysfs/user driven */
+	ACQUIRE(mutex_intr, lock)(&tsm_pf0->lock);
+	if ((rc = ACQUIRE_ERR(mutex_intr, &lock)))
+		return rc;
+
+	rc = ops->connect(pdev);
+	if (rc)
+		return rc;
+
+	pdev->tsm = no_free_ptr(pci_tsm);
+
+	/*
+	 * Now that the DSM is established, probe() all the potential
+	 * dependent functions. Failure to probe a function is not fatal
+	 * to connect(), it just disables subsequent security operations
+	 * for that function.
+	 *
+	 * Note this is done unconditionally, without regard to finding
+	 * PCI_EXP_DEVCAP_TEE on the dependent function, for robustness. The DSM
+	 * is the ultimate arbiter of security state relative to a given
+	 * interface id, and if it says it can manage TDISP state of a function,
+	 * let it.
+	 */
+	if (has_tee(pdev))
+		pci_tsm_walk_fns(pdev, probe_fn, pdev);
+	return 0;
+}
+
+static ssize_t connect_show(struct device *dev, struct device_attribute *attr,
+			    char *buf)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct tsm_dev *tsm_dev;
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return sysfs_emit(buf, "\n");
+
+	tsm_dev = pdev->tsm->tsm_dev;
+	return sysfs_emit(buf, "%s\n", dev_name(&tsm_dev->dev));
+}
+
+/* Is @tsm_dev managing physical link / session properties... */
+static bool is_link_tsm(struct tsm_dev *tsm_dev)
+{
+	return tsm_dev && tsm_dev->pci_ops && tsm_dev->pci_ops->link_ops.probe;
+}
+
+/* ...or is @tsm_dev managing device security state ? */
+static bool is_devsec_tsm(struct tsm_dev *tsm_dev)
+{
+	return tsm_dev && tsm_dev->pci_ops && tsm_dev->pci_ops->devsec_ops.lock;
+}
+
+static ssize_t connect_store(struct device *dev, struct device_attribute *attr,
+			     const char *buf, size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	int rc, id;
+
+	rc = sscanf(buf, "tsm%d\n", &id);
+	if (rc != 1)
+		return -EINVAL;
+
+	ACQUIRE(rwsem_write_kill, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_write_kill, &lock)))
+		return rc;
+
+	if (pdev->tsm)
+		return -EBUSY;
+
+	struct tsm_dev *tsm_dev __free(put_tsm_dev) = find_tsm_dev(id);
+	if (!is_link_tsm(tsm_dev))
+		return -ENXIO;
+
+	rc = pci_tsm_connect(pdev, tsm_dev);
+	if (rc)
+		return rc;
+	return len;
+}
+static DEVICE_ATTR_RW(connect);
+
+static int remove_fn(struct pci_dev *pdev, void *data)
+{
+	tsm_remove(pdev->tsm);
+	return 0;
+}
+
+static void __pci_tsm_disconnect(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+	const struct pci_tsm_ops *ops = to_pci_tsm_ops(pdev->tsm);
+
+	/* disconnect() mutually exclusive with subfunction pci_tsm_init() */
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+
+	/*
+	 * disconnect() is uninterruptible as it may be called for device
+	 * teardown
+	 */
+	guard(mutex)(&tsm_pf0->lock);
+	pci_tsm_walk_fns_reverse(pdev, remove_fn, NULL);
+	ops->disconnect(pdev);
+}
+
+static void pci_tsm_disconnect(struct pci_dev *pdev)
+{
+	__pci_tsm_disconnect(pdev);
+	tsm_remove(pdev->tsm);
+}
+
+static ssize_t disconnect_store(struct device *dev,
+				struct device_attribute *attr, const char *buf,
+				size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct tsm_dev *tsm_dev;
+	int rc;
+
+	ACQUIRE(rwsem_write_kill, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_write_kill, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return -ENXIO;
+
+	tsm_dev = pdev->tsm->tsm_dev;
+	if (!sysfs_streq(buf, dev_name(&tsm_dev->dev)))
+		return -EINVAL;
+
+	pci_tsm_disconnect(pdev);
+	return len;
+}
+static DEVICE_ATTR_WO(disconnect);
+
+/* The 'authenticated' attribute is exclusive to the presence of a 'link' TSM */
+static bool pci_tsm_link_group_visible(struct kobject *kobj)
+{
+	struct pci_dev *pdev = to_pci_dev(kobj_to_dev(kobj));
+
+	return pci_tsm_link_count && is_pci_tsm_pf0(pdev);
+}
+DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm_link);
+
+/*
+ * 'link' and 'devsec' TSMs share the same 'tsm/' sysfs group, so the TSM type
+ * specific attributes need individual visibility checks.
+ */
+static umode_t pci_tsm_attr_visible(struct kobject *kobj,
+				    struct attribute *attr, int n)
+{
+	if (pci_tsm_link_group_visible(kobj)) {
+		if (attr == &dev_attr_connect.attr ||
+		    attr == &dev_attr_disconnect.attr)
+			return attr->mode;
+	}
+
+	return 0;
+}
+
+static bool pci_tsm_group_visible(struct kobject *kobj)
+{
+	return pci_tsm_link_group_visible(kobj);
+}
+DEFINE_SYSFS_GROUP_VISIBLE(pci_tsm);
+
+static struct attribute *pci_tsm_attrs[] = {
+	&dev_attr_connect.attr,
+	&dev_attr_disconnect.attr,
+	NULL
+};
+
+const struct attribute_group pci_tsm_attr_group = {
+	.name = "tsm",
+	.attrs = pci_tsm_attrs,
+	.is_visible = SYSFS_GROUP_VISIBLE(pci_tsm),
+};
+
+static ssize_t authenticated_show(struct device *dev,
+				  struct device_attribute *attr, char *buf)
+{
+	/*
+	 * When the SPDM session established via TSM the 'authenticated' state
+	 * of the device is identical to the connect state.
+	 */
+	return connect_show(dev, attr, buf);
+}
+static DEVICE_ATTR_RO(authenticated);
+
+static struct attribute *pci_tsm_auth_attrs[] = {
+	&dev_attr_authenticated.attr,
+	NULL
+};
+
+const struct attribute_group pci_tsm_auth_attr_group = {
+	.attrs = pci_tsm_auth_attrs,
+	.is_visible = SYSFS_GROUP_VISIBLE(pci_tsm_link),
+};
+
+/*
+ * Retrieve physical function0 device whether it has TEE capability or not
+ */
+static struct pci_dev *pf0_dev_get(struct pci_dev *pdev)
+{
+	struct pci_dev *pf_dev = pci_physfn(pdev);
+
+	if (PCI_FUNC(pf_dev->devfn) == 0)
+		return pci_dev_get(pf_dev);
+
+	return pci_get_slot(pf_dev->bus,
+			    pf_dev->devfn - PCI_FUNC(pf_dev->devfn));
+}
+
+/*
+ * Find the PCI Device instance that serves as the Device Security Manager (DSM)
+ * for @pdev. Note that no additional reference is held for the resulting device
+ * because that resulting object always has a registered lifetime
+ * greater-than-or-equal to that of the @pdev argument. This is by virtue of
+ * @pdev being a descendant of, or identical to, the returned DSM device.
+ */
+static struct pci_dev *find_dsm_dev(struct pci_dev *pdev)
+{
+	struct device *grandparent;
+	struct pci_dev *uport;
+
+	if (is_pci_tsm_pf0(pdev))
+		return pdev;
+
+	struct pci_dev *pf0 __free(pci_dev_put) = pf0_dev_get(pdev);
+	if (!pf0)
+		return NULL;
+
+	if (is_dsm(pf0))
+		return pf0;
+
+	/*
+	 * For cases where a switch may be hosting TDISP services on behalf of
+	 * downstream devices, check the first upstream port relative to this
+	 * endpoint.
+	 */
+	if (!pdev->dev.parent)
+		return NULL;
+	grandparent = pdev->dev.parent->parent;
+	if (!grandparent)
+		return NULL;
+	if (!dev_is_pci(grandparent))
+		return NULL;
+	uport = to_pci_dev(grandparent);
+	if (!pci_is_pcie(uport) ||
+	    pci_pcie_type(uport) != PCI_EXP_TYPE_UPSTREAM)
+		return NULL;
+
+	if (is_dsm(uport))
+		return uport;
+	return NULL;
+}
+
+/**
+ * pci_tsm_link_constructor() - base 'struct pci_tsm' initialization for link TSMs
+ * @pdev: The PCI device
+ * @tsm: context to initialize
+ * @tsm_dev: Platform TEE Security Manager, initiator of security operations
+ */
+int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
+			     struct tsm_dev *tsm_dev)
+{
+	if (!is_link_tsm(tsm_dev))
+		return -EINVAL;
+
+	tsm->dsm_dev = find_dsm_dev(pdev);
+	if (!tsm->dsm_dev) {
+		pci_warn(pdev, "failed to find Device Security Manager\n");
+		return -ENXIO;
+	}
+	tsm->pdev = pdev;
+	tsm->tsm_dev = tsm_dev;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_link_constructor);
+
+/**
+ * pci_tsm_pf0_constructor() - common 'struct pci_tsm_pf0' (DSM) initialization
+ * @pdev: Physical Function 0 PCI device (as indicated by is_pci_tsm_pf0())
+ * @tsm: context to initialize
+ * @tsm_dev: Platform TEE Security Manager, initiator of security operations
+ */
+int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
+			    struct tsm_dev *tsm_dev)
+{
+	mutex_init(&tsm->lock);
+	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					   PCI_DOE_FEATURE_CMA);
+	if (!tsm->doe_mb) {
+		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
+		return -ENODEV;
+	}
+
+	return pci_tsm_link_constructor(pdev, &tsm->base_tsm, tsm_dev);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_pf0_constructor);
+
+void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *pf0_tsm)
+{
+	mutex_destroy(&pf0_tsm->lock);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_pf0_destructor);
+
+static void pf0_sysfs_enable(struct pci_dev *pdev)
+{
+	bool tee = has_tee(pdev);
+
+	pci_dbg(pdev, "Device Security Manager detected (%s%s%s)\n",
+		pdev->ide_cap ? "IDE" : "", pdev->ide_cap && tee ? " " : "",
+		tee ? "TEE" : "");
+
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+}
+
+int pci_tsm_register(struct tsm_dev *tsm_dev)
+{
+	struct pci_dev *pdev = NULL;
+
+	if (!tsm_dev)
+		return -EINVAL;
+
+	/* The TSM device must only implement one of link_ops or devsec_ops */
+	if (!is_link_tsm(tsm_dev) && !is_devsec_tsm(tsm_dev))
+		return -EINVAL;
+
+	if (is_link_tsm(tsm_dev) && is_devsec_tsm(tsm_dev))
+		return -EINVAL;
+
+	guard(rwsem_write)(&pci_tsm_rwsem);
+
+	/* On first enable, update sysfs groups */
+	if (is_link_tsm(tsm_dev) && pci_tsm_link_count++ == 0) {
+		for_each_pci_dev(pdev)
+			if (is_pci_tsm_pf0(pdev))
+				pf0_sysfs_enable(pdev);
+	} else if (is_devsec_tsm(tsm_dev)) {
+		pci_tsm_devsec_count++;
+	}
+
+	return 0;
+}
+
+static void pci_tsm_fn_exit(struct pci_dev *pdev)
+{
+	/* TODO: unbind the fn */
+	tsm_remove(pdev->tsm);
+}
+
+/**
+ * __pci_tsm_destroy() - destroy the TSM context for @pdev
+ * @pdev: device to cleanup
+ * @tsm_dev: the TSM device being removed, or NULL if @pdev is being removed.
+ *
+ * At device removal or TSM unregistration all established context
+ * with the TSM is torn down. Additionally, if there are no more TSMs
+ * registered, the PCI tsm/ sysfs attributes are hidden.
+ */
+static void __pci_tsm_destroy(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+
+	/*
+	 * First, handle the TSM removal case to shutdown @pdev sysfs, this is
+	 * skipped if the device itself is being removed since sysfs goes away
+	 * naturally at that point
+	 */
+	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev) && !pci_tsm_link_count) {
+		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+	}
+
+	/* Nothing else to do if this device never attached to the departing TSM */
+	if (!tsm)
+		return;
+
+	/* Now lookup the tsm_dev to destroy TSM context */
+	if (!tsm_dev)
+		tsm_dev = tsm->tsm_dev;
+	else if (tsm_dev != tsm->tsm_dev)
+		return;
+
+	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev))
+		pci_tsm_disconnect(pdev);
+	else
+		pci_tsm_fn_exit(pdev);
+}
+
+void pci_tsm_destroy(struct pci_dev *pdev)
+{
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	__pci_tsm_destroy(pdev, NULL);
+}
+
+void pci_tsm_init(struct pci_dev *pdev)
+{
+	guard(rwsem_read)(&pci_tsm_rwsem);
+
+	/*
+	 * Subfunctions are either probed synchronous with connect() or later
+	 * when either the SR-IOV configuration is changed, or, unlikely,
+	 * connect() raced initial bus scanning.
+	 */
+	if (pdev->tsm)
+		return;
+
+	if (pci_tsm_link_count) {
+		struct pci_dev *dsm = find_dsm_dev(pdev);
+
+		if (!dsm)
+			return;
+
+		/*
+		 * The only path to init a Device Security Manager capable
+		 * device is via connect().
+		 */
+		if (!dsm->tsm)
+			return;
+
+		probe_fn(pdev, dsm);
+	}
+}
+
+void pci_tsm_unregister(struct tsm_dev *tsm_dev)
+{
+	struct pci_dev *pdev = NULL;
+
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	if (is_link_tsm(tsm_dev))
+		pci_tsm_link_count--;
+	if (is_devsec_tsm(tsm_dev))
+		pci_tsm_devsec_count--;
+	for_each_pci_dev_reverse(pdev)
+		__pci_tsm_destroy(pdev, tsm_dev);
+}
+
+int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,
+			 size_t req_sz, void *resp, size_t resp_sz)
+{
+	struct pci_tsm_pf0 *tsm;
+
+	if (!pdev->tsm || !is_pci_tsm_pf0(pdev))
+		return -ENXIO;
+
+	tsm = to_pci_tsm_pf0(pdev->tsm);
+	if (!tsm->doe_mb)
+		return -ENXIO;
+
+	return pci_doe(tsm->doe_mb, PCI_VENDOR_ID_PCI_SIG, type, req, req_sz,
+		       resp, resp_sz);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_doe_transfer);
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 347507cc5e3f..0e705f3067a1 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -8,11 +8,29 @@
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
+#include <linux/pci-tsm.h>
 
 static struct class *tsm_class;
 static DECLARE_RWSEM(tsm_rwsem);
 static DEFINE_IDA(tsm_ida);
 
+static int match_id(struct device *dev, const void *data)
+{
+	struct tsm_dev *tsm_dev = container_of(dev, struct tsm_dev, dev);
+	int id = *(const int *)data;
+
+	return tsm_dev->id == id;
+}
+
+struct tsm_dev *find_tsm_dev(int id)
+{
+	struct device *dev = class_find_device(tsm_class, NULL, &id, match_id);
+
+	if (!dev)
+		return NULL;
+	return container_of(dev, struct tsm_dev, dev);
+}
+
 static struct tsm_dev *alloc_tsm_dev(struct device *parent)
 {
 	struct device *dev;
@@ -36,7 +54,29 @@ static struct tsm_dev *alloc_tsm_dev(struct device *parent)
 	return no_free_ptr(tsm_dev);
 }
 
-struct tsm_dev *tsm_register(struct device *parent)
+static struct tsm_dev *tsm_register_pci_or_reset(struct tsm_dev *tsm_dev,
+						 struct pci_tsm_ops *pci_ops)
+{
+	int rc;
+
+	if (!pci_ops)
+		return tsm_dev;
+
+	tsm_dev->pci_ops = pci_ops;
+	rc = pci_tsm_register(tsm_dev);
+	if (rc) {
+		dev_err(tsm_dev->dev.parent,
+			"PCI/TSM registration failure: %d\n", rc);
+		device_unregister(&tsm_dev->dev);
+		return ERR_PTR(rc);
+	}
+
+	/* Notify TSM userspace that PCI/TSM operations are now possible */
+	kobject_uevent(&tsm_dev->dev.kobj, KOBJ_CHANGE);
+	return tsm_dev;
+}
+
+struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *pci_ops)
 {
 	struct tsm_dev *tsm_dev __free(put_tsm_dev) = alloc_tsm_dev(parent);
 	struct device *dev;
@@ -54,12 +94,14 @@ struct tsm_dev *tsm_register(struct device *parent)
 	if (rc)
 		return ERR_PTR(rc);
 
-	return no_free_ptr(tsm_dev);
+	return tsm_register_pci_or_reset(no_free_ptr(tsm_dev), pci_ops);
 }
 EXPORT_SYMBOL_GPL(tsm_register);
 
 void tsm_unregister(struct tsm_dev *tsm_dev)
 {
+	if (tsm_dev->pci_ops)
+		pci_tsm_unregister(tsm_dev);
 	device_unregister(&tsm_dev->dev);
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
diff --git a/MAINTAINERS b/MAINTAINERS
index 06285f3a24df..ebf6988666eb 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26103,8 +26103,10 @@ L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm-report
 F:	Documentation/driver-api/coco/
+F:	Documentation/driver-api/pci/tsm.rst
+F:	drivers/pci/tsm.c
 F:	drivers/virt/coco/guest/
-F:	include/linux/tsm*.h
+F:	include/linux/*tsm*.h
 F:	samples/tsm-mr/
 
 TRUSTED SERVICES TEE DRIVER

---

## [6] Dan Williams — 2025-10-31
*Subject: [PATCH v8 5/9] PCI: Add PCIe Device 3 Extended Capability enumeration*

PCIe r7.0 Section 7.7.9 Device 3 Extended Capability Structure, defines the
canonical location for determining the Flit Mode of a device. This status
is a dependency for PCIe IDE enabling. Add a new fm_enabled flag to 'struct
pci_dev'.

Cc: Lukas Wunner <lukas@wunner.de>
Cc: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/pci.h           |  1 +
 include/uapi/linux/pci_regs.h |  7 +++++++
 drivers/pci/probe.c           | 12 ++++++++++++
 3 files changed, 20 insertions(+)

diff --git a/include/linux/pci.h b/include/linux/pci.h
index 2f9c0cb6a50a..ea94799c81b0 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -450,6 +450,7 @@ struct pci_dev {
 	unsigned int	pasid_enabled:1;	/* Process Address Space ID */
 	unsigned int	pri_enabled:1;		/* Page Request Interface */
 	unsigned int	tph_enabled:1;		/* TLP Processing Hints */
+	unsigned int	fm_enabled:1;		/* Flit Mode (segment captured) */
 	unsigned int	is_managed:1;		/* Managed via devres */
 	unsigned int	is_msi_managed:1;	/* MSI release via devres installed */
 	unsigned int	needs_freset:1;		/* Requires fundamental reset */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index f2759c1097bc..3add74ae2594 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -755,6 +755,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_DEV3	0x2F	/* Device 3 Capability/Control/Status */
 #define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_PL_64GT	0x31	/* Physical Layer 64.0 GT/s */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_PL_64GT
@@ -1246,6 +1247,12 @@
 /* Deprecated old name, replaced with PCI_DOE_DATA_OBJECT_DISC_RSP_3_TYPE */
 #define PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL		PCI_DOE_DATA_OBJECT_DISC_RSP_3_TYPE
 
+/* Device 3 Extended Capability */
+#define PCI_DEV3_CAP		0x04	/* Device 3 Capabilities Register */
+#define PCI_DEV3_CTL		0x08	/* Device 3 Control Register */
+#define PCI_DEV3_STA		0x0c	/* Device 3 Status Register */
+#define  PCI_DEV3_STA_SEGMENT	0x8	/* Segment Captured (end-to-end flit-mode detected) */
+
 /* Compute Express Link (CXL r3.1, sec 8.1.5) */
 #define PCI_DVSEC_CXL_PORT				3
 #define PCI_DVSEC_CXL_PORT_CTL				0x0c
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index d1467348c169..3b54f1720be5 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2283,6 +2283,17 @@ int pci_configure_extended_tags(struct pci_dev *dev, void *ign)
 	return 0;
 }
 
+static void pci_dev3_init(struct pci_dev *pdev)
+{
+	u16 cap = pci_find_ext_capability(pdev, PCI_EXT_CAP_ID_DEV3);
+	u32 val = 0;
+
+	if (!cap)
+		return;
+	pci_read_config_dword(pdev, cap + PCI_DEV3_STA, &val);
+	pdev->fm_enabled = !!(val & PCI_DEV3_STA_SEGMENT);
+}
+
 /**
  * pcie_relaxed_ordering_enabled - Probe for PCIe relaxed ordering enable
  * @dev: PCI device to query
@@ -2667,6 +2678,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
+	pci_dev3_init(dev);		/* Device 3 capabilities */
 	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);

---

## [7] Dan Williams — 2025-10-31
*Subject: [PATCH v8 6/9] PCI: Establish document for PCI host bridge sysfs attributes*

In preparation for adding more host bridge sysfs attributes, document the
existing naming format and 'firmware_node' attribute.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge | 19 +++++++++++++++++++
 MAINTAINERS                                   |  1 +
 2 files changed, 20 insertions(+)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
new file mode 100644
index 000000000000..8c3a652799f1
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -0,0 +1,19 @@
+What:		/sys/devices/pciDDDD:BB
+		/sys/devices/.../pciDDDD:BB
+Contact:	linux-pci@vger.kernel.org
+Description:
+		A PCI host bridge device parents a PCI bus device topology. PCI
+		controllers may also parent host bridges. The DDDD:BB format
+		conveys the PCI domain (ACPI segment) number and root bus number
+		(in hexadecimal) of the host bridge. Note that the domain number
+		may be larger than the 16-bits that the "DDDD" format implies
+		for emulated host-bridges.
+
+What:		pciDDDD:BB/firmware_node
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) Symlink to the platform firmware device object "companion"
+		of the host bridge. For example, an ACPI device with an _HID of
+		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00). See
+		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
+		format.
diff --git a/MAINTAINERS b/MAINTAINERS
index ebf6988666eb..9b961fb11b09 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -19896,6 +19896,7 @@ Q:	https://patchwork.kernel.org/project/linux-pci/list/
 B:	https://bugzilla.kernel.org
 C:	irc://irc.oftc.net/linux-pci
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/pci/pci.git
+F:	Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 F:	Documentation/PCI/
 F:	Documentation/devicetree/bindings/pci/
 F:	arch/x86/kernel/early-quirks.c

---

## [8] Dan Williams — 2025-10-31
*Subject: [PATCH v8 7/9] PCI/IDE: Add IDE establishment helpers*

There are two components to establishing an encrypted link, provisioning
the stream in Partner Port config-space, and programming the keys into
the link layer via IDE_KM (IDE Key Management). This new library,
drivers/pci/ide.c, enables the former. IDE_KM, via a TSM low-level
driver, is saved for later.

With the platform TSM implementations of SEV-TIO and TDX Connect in mind
this library abstracts small differences in those implementations. For
example, TDX Connect handles Root Port register setup while SEV-TIO
expects System Software to update the Root Port registers. This is the
rationale for fine-grained 'setup' + 'enable' verbs.

The other design detail for TSM-coordinated IDE establishment is that
the TSM may manage allocation of Stream IDs, this is why the Stream ID
value is passed in to pci_ide_stream_setup().

The flow is:

pci_ide_stream_alloc():
    Allocate a Selective IDE Stream Register Block in each Partner Port
    (Endpoint + Root Port), and reserve a host bridge / platform stream
    slot. Gather Partner Port specific stream settings like Requester ID.

pci_ide_stream_register():
    Publish the stream in sysfs after allocating a Stream ID. In the TSM
    case the TSM allocates the Stream ID for the Partner Port pair.

pci_ide_stream_setup():
    Program the stream settings to a Partner Port. Caller is responsible
    for optionally calling this for the Root Port as well if the TSM
    implementation requires it.

pci_ide_stream_enable():
    Enable the stream after IDE_KM.

In support of system administrators auditing where platform, Root Port,
and Endpoint IDE stream resources are being spent, the allocated stream
is reflected as a symlink from the host bridge to the endpoint with the
name:

    stream%d.%d.%d

Where the tuple of integers reflects the allocated platform, Root Port,
and Endpoint stream index (Selective IDE Stream Register Block) values.

Thanks to Wu Hao for a draft implementation of this infrastructure.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge |  14 +
 drivers/pci/pci.h                             |   2 +
 include/linux/pci-ide.h                       |  78 ++++
 include/linux/pci.h                           |   6 +
 drivers/pci/ide.c                             | 428 ++++++++++++++++++
 drivers/pci/probe.c                           |   1 +
 6 files changed, 529 insertions(+)
 create mode 100644 include/linux/pci-ide.h

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index 8c3a652799f1..2c66e5bb2bf8 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -17,3 +17,17 @@ Description:
 		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00). See
 		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
 		format.
+
+What:		pciDDDD:BB/streamH.R.E
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a platform has established a secure connection, PCIe
+		IDE, between two Partner Ports, this symlink appears. A stream
+		consumes a Stream ID slot in each of the Host bridge (H), Root
+		Port (R) and Endpoint (E).  The link points to the Endpoint PCI
+		device in the Selective IDE Stream pairing. Specifically, "R"
+		and "E" represent the assigned Selective IDE Stream Register
+		Block in the Root Port and Endpoint, and "H" represents a
+		platform specific pool of stream resources shared by the Root
+		Ports in a host bridge. See /sys/devices/pciDDDD:BB entry for
+		details about the DDDD:BB format.
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 6e4cc1c9aa58..d3f16be40102 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -615,8 +615,10 @@ static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 
 #ifdef CONFIG_PCI_IDE
 void pci_ide_init(struct pci_dev *dev);
+void pci_ide_init_host_bridge(struct pci_host_bridge *hb);
 #else
 static inline void pci_ide_init(struct pci_dev *dev) { }
+static inline void pci_ide_init_host_bridge(struct pci_host_bridge *hb) { }
 #endif
 
 #ifdef CONFIG_PCI_TSM
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
new file mode 100644
index 000000000000..e638f9429bf9
--- /dev/null
+++ b/include/linux/pci-ide.h
@@ -0,0 +1,78 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Common helpers for drivers (e.g. low-level PCI/TSM drivers) implementing the
+ * IDE key management protocol (IDE_KM) as defined by:
+ * PCIe r7.0 section 6.33 Integrity & Data Encryption (IDE)
+ *
+ * Copyright(c) 2024-2025 Intel Corporation. All rights reserved.
+ */
+
+#ifndef __PCI_IDE_H__
+#define __PCI_IDE_H__
+
+enum pci_ide_partner_select {
+	PCI_IDE_EP,
+	PCI_IDE_RP,
+	PCI_IDE_PARTNER_MAX,
+	/*
+	 * In addition to the resources in each partner port the
+	 * platform / host-bridge additionally has a Stream ID pool that
+	 * it shares across root ports. Let pci_ide_stream_alloc() use
+	 * the alloc_stream_index() helper as endpoints and root ports.
+	 */
+	PCI_IDE_HB = PCI_IDE_PARTNER_MAX,
+};
+
+/**
+ * struct pci_ide_partner - Per port pair Selective IDE Stream settings
+ * @rid_start: Partner Port Requester ID range start
+ * @rid_end: Partner Port Requester ID range end
+ * @stream_index: Selective IDE Stream Register Block selection
+ * @default_stream: Endpoint uses this stream for all upstream TLPs regardless of
+ *		    address and RID association registers
+ * @setup: flag to track whether to run pci_ide_stream_teardown() for this
+ *	   partner slot
+ * @enable: flag whether to run pci_ide_stream_disable() for this partner slot
+ */
+struct pci_ide_partner {
+	u16 rid_start;
+	u16 rid_end;
+	u8 stream_index;
+	unsigned int default_stream:1;
+	unsigned int setup:1;
+	unsigned int enable:1;
+};
+
+/**
+ * struct pci_ide - PCIe Selective IDE Stream descriptor
+ * @pdev: PCIe Endpoint in the pci_ide_partner pair
+ * @partner: per-partner settings
+ * @host_bridge_stream: allocated from host bridge @ide_stream_ida pool
+ * @stream_id: unique Stream ID (within Partner Port pairing)
+ * @name: name of the established Selective IDE Stream in sysfs
+ *
+ * Negative @stream_id values indicate "uninitialized" on the
+ * expectation that with TSM established IDE the TSM owns the stream_id
+ * allocation.
+ */
+struct pci_ide {
+	struct pci_dev *pdev;
+	struct pci_ide_partner partner[PCI_IDE_PARTNER_MAX];
+	u8 host_bridge_stream;
+	int stream_id;
+	const char *name;
+};
+
+struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev,
+					    struct pci_ide *ide);
+struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
+void pci_ide_stream_free(struct pci_ide *ide);
+int  pci_ide_stream_register(struct pci_ide *ide);
+void pci_ide_stream_unregister(struct pci_ide *ide);
+void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide);
+int pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_release(struct pci_ide *ide);
+DEFINE_FREE(pci_ide_stream_release, struct pci_ide *, if (_T) pci_ide_stream_release(_T))
+#endif /* __PCI_IDE_H__ */
diff --git a/include/linux/pci.h b/include/linux/pci.h
index ea94799c81b0..2c8dbae4916c 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -545,6 +545,8 @@ struct pci_dev {
 	u16		ide_cap;	/* Link Integrity & Data Encryption */
 	u8		nr_ide_mem;	/* Address association resources for streams */
 	u8		nr_link_ide;	/* Link Stream count (Selective Stream offset) */
+	u16		nr_sel_ide;	/* Selective Stream count (register block allocator) */
+	struct ida	ide_stream_ida;
 	unsigned int	ide_cfg:1;	/* Config cycles over IDE */
 	unsigned int	ide_tee_limit:1; /* Disallow T=0 traffic over IDE */
 #endif
@@ -614,6 +616,10 @@ struct pci_host_bridge {
 	int		domain_nr;
 	struct list_head windows;	/* resource_entry */
 	struct list_head dma_ranges;	/* dma ranges resource list */
+#ifdef CONFIG_PCI_IDE
+	u16 nr_ide_streams; /* Max streams possibly active in @ide_stream_ida */
+	struct ida ide_stream_ida;
+#endif
 	u8 (*swizzle_irq)(struct pci_dev *, u8 *); /* Platform IRQ swizzler */
 	int (*map_irq)(const struct pci_dev *, u8, u8);
 	void (*release_fn)(struct pci_host_bridge *);
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 26866edf91b4..7643840738fe 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -5,8 +5,12 @@
 
 #define dev_fmt(fmt) "PCI/IDE: " fmt
 #include <linux/bitfield.h>
+#include <linux/bitops.h>
 #include <linux/pci.h>
+#include <linux/pci-ide.h>
 #include <linux/pci_regs.h>
+#include <linux/slab.h>
+#include <linux/sysfs.h>
 
 #include "pci.h"
 
@@ -23,12 +27,25 @@ static int __sel_ide_offset(u16 ide_cap, u8 nr_link_ide, u8 stream_index,
 	return offset + stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);
 }
 
+static int sel_ide_offset(struct pci_dev *pdev,
+			  struct pci_ide_partner *settings)
+{
+	return __sel_ide_offset(pdev->ide_cap, pdev->nr_link_ide,
+				settings->stream_index, pdev->nr_ide_mem);
+}
+
 void pci_ide_init(struct pci_dev *pdev)
 {
 	u16 nr_link_ide, nr_ide_mem, nr_streams;
 	u16 ide_cap;
 	u32 val;
 
+	/*
+	 * Unconditionally init so that ida idle state is consistent with
+	 * pdev->ide_cap.
+	 */
+	ida_init(&pdev->ide_stream_ida);
+
 	if (!pci_is_pcie(pdev))
 		return;
 
@@ -84,5 +101,416 @@ void pci_ide_init(struct pci_dev *pdev)
 
 	pdev->ide_cap = ide_cap;
 	pdev->nr_link_ide = nr_link_ide;
+	pdev->nr_sel_ide = nr_streams;
 	pdev->nr_ide_mem = nr_ide_mem;
 }
+
+struct stream_index {
+	struct ida *ida;
+	u8 stream_index;
+};
+
+static void free_stream_index(struct stream_index *stream)
+{
+	ida_free(stream->ida, stream->stream_index);
+}
+
+DEFINE_FREE(free_stream, struct stream_index *, if (_T) free_stream_index(_T))
+static struct stream_index *alloc_stream_index(struct ida *ida, u16 max,
+					       struct stream_index *stream)
+{
+	int id;
+
+	if (!max)
+		return NULL;
+
+	id = ida_alloc_max(ida, max - 1, GFP_KERNEL);
+	if (id < 0)
+		return NULL;
+
+	*stream = (struct stream_index) {
+		.ida = ida,
+		.stream_index = id,
+	};
+	return stream;
+}
+
+/**
+ * pci_ide_stream_alloc() - Reserve stream indices and probe for settings
+ * @pdev: IDE capable PCIe Endpoint Physical Function
+ *
+ * Retrieve the Requester ID range of @pdev for programming its Root
+ * Port IDE RID Association registers, and conversely retrieve the
+ * Requester ID of the Root Port for programming @pdev's IDE RID
+ * Association registers.
+ *
+ * Allocate a Selective IDE Stream Register Block instance per port.
+ *
+ * Allocate a platform stream resource from the associated host bridge.
+ * Retrieve stream association parameters for Requester ID range and
+ * address range restrictions for the stream.
+ */
+struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
+{
+	/* EP, RP, + HB Stream allocation */
+	struct stream_index __stream[PCI_IDE_HB + 1];
+	struct pci_host_bridge *hb;
+	struct pci_dev *rp;
+	int num_vf, rid_end;
+
+	if (!pci_is_pcie(pdev))
+		return NULL;
+
+	if (pci_pcie_type(pdev) != PCI_EXP_TYPE_ENDPOINT)
+		return NULL;
+
+	if (!pdev->ide_cap)
+		return NULL;
+
+	struct pci_ide *ide __free(kfree) = kzalloc(sizeof(*ide), GFP_KERNEL);
+	if (!ide)
+		return NULL;
+
+	hb = pci_find_host_bridge(pdev->bus);
+	struct stream_index *hb_stream __free(free_stream) = alloc_stream_index(
+		&hb->ide_stream_ida, hb->nr_ide_streams, &__stream[PCI_IDE_HB]);
+	if (!hb_stream)
+		return NULL;
+
+	rp = pcie_find_root_port(pdev);
+	struct stream_index *rp_stream __free(free_stream) = alloc_stream_index(
+		&rp->ide_stream_ida, rp->nr_sel_ide, &__stream[PCI_IDE_RP]);
+	if (!rp_stream)
+		return NULL;
+
+	struct stream_index *ep_stream __free(free_stream) = alloc_stream_index(
+		&pdev->ide_stream_ida, pdev->nr_sel_ide, &__stream[PCI_IDE_EP]);
+	if (!ep_stream)
+		return NULL;
+
+	/* for SR-IOV case, cover all VFs */
+	num_vf = pci_num_vf(pdev);
+	if (num_vf)
+		rid_end = PCI_DEVID(pci_iov_virtfn_bus(pdev, num_vf),
+				    pci_iov_virtfn_devfn(pdev, num_vf));
+	else
+		rid_end = pci_dev_id(pdev);
+
+	*ide = (struct pci_ide) {
+		.pdev = pdev,
+		.partner = {
+			[PCI_IDE_EP] = {
+				.rid_start = pci_dev_id(rp),
+				.rid_end = pci_dev_id(rp),
+				.stream_index = no_free_ptr(ep_stream)->stream_index,
+			},
+			[PCI_IDE_RP] = {
+				.rid_start = pci_dev_id(pdev),
+				.rid_end = rid_end,
+				.stream_index = no_free_ptr(rp_stream)->stream_index,
+			},
+		},
+		.host_bridge_stream = no_free_ptr(hb_stream)->stream_index,
+		.stream_id = -1,
+	};
+
+	return_ptr(ide);
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_alloc);
+
+/**
+ * pci_ide_stream_free() - unwind pci_ide_stream_alloc()
+ * @ide: idle IDE settings descriptor
+ *
+ * Free all of the stream index (register block) allocations acquired by
+ * pci_ide_stream_alloc(). The stream represented by @ide is assumed to
+ * be unregistered and not instantiated in any device.
+ */
+void pci_ide_stream_free(struct pci_ide *ide)
+{
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
+
+	ida_free(&pdev->ide_stream_ida, ide->partner[PCI_IDE_EP].stream_index);
+	ida_free(&rp->ide_stream_ida, ide->partner[PCI_IDE_RP].stream_index);
+	ida_free(&hb->ide_stream_ida, ide->host_bridge_stream);
+	kfree(ide);
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_free);
+
+/**
+ * pci_ide_stream_release() - unwind and release an @ide context
+ * @ide: partially or fully registered IDE settings descriptor
+ *
+ * In support of automatic cleanup of IDE setup routines perform IDE
+ * teardown in expected reverse order of setup and with respect to which
+ * aspects of IDE setup have successfully completed.
+ *
+ * Be careful that setup order mirrors this shutdown order. Otherwise,
+ * open code releasing the IDE context.
+ */
+void pci_ide_stream_release(struct pci_ide *ide)
+{
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+
+	if (ide->partner[PCI_IDE_RP].enable)
+		pci_ide_stream_disable(rp, ide);
+
+	if (ide->partner[PCI_IDE_EP].enable)
+		pci_ide_stream_disable(pdev, ide);
+
+	if (ide->partner[PCI_IDE_RP].setup)
+		pci_ide_stream_teardown(rp, ide);
+
+	if (ide->partner[PCI_IDE_EP].setup)
+		pci_ide_stream_teardown(pdev, ide);
+
+	if (ide->name)
+		pci_ide_stream_unregister(ide);
+
+	pci_ide_stream_free(ide);
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_release);
+
+/**
+ * pci_ide_stream_register() - Prepare to activate an IDE Stream
+ * @ide: IDE settings descriptor
+ *
+ * After a Stream ID has been acquired for @ide, record the presence of
+ * the stream in sysfs. The expectation is that @ide is immutable while
+ * registered.
+ */
+int pci_ide_stream_register(struct pci_ide *ide)
+{
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
+	u8 ep_stream, rp_stream;
+	int rc;
+
+	if (ide->stream_id < 0 || ide->stream_id > U8_MAX) {
+		pci_err(pdev, "Setup fail: Invalid Stream ID: %d\n", ide->stream_id);
+		return -ENXIO;
+	}
+
+	ep_stream = ide->partner[PCI_IDE_EP].stream_index;
+	rp_stream = ide->partner[PCI_IDE_RP].stream_index;
+	const char *name __free(kfree) = kasprintf(GFP_KERNEL, "stream%d.%d.%d",
+						   ide->host_bridge_stream,
+						   rp_stream, ep_stream);
+	if (!name)
+		return -ENOMEM;
+
+	rc = sysfs_create_link(&hb->dev.kobj, &pdev->dev.kobj, name);
+	if (rc)
+		return rc;
+
+	ide->name = no_free_ptr(name);
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_register);
+
+/**
+ * pci_ide_stream_unregister() - unwind pci_ide_stream_register()
+ * @ide: idle IDE settings descriptor
+ *
+ * In preparation for freeing @ide, remove sysfs enumeration for the
+ * stream.
+ */
+void pci_ide_stream_unregister(struct pci_ide *ide)
+{
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
+
+	sysfs_remove_link(&hb->dev.kobj, ide->name);
+	kfree(ide->name);
+	ide->name = NULL;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_unregister);
+
+static int pci_ide_domain(struct pci_dev *pdev)
+{
+	if (pdev->fm_enabled)
+		return pci_domain_nr(pdev->bus);
+	return 0;
+}
+
+struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	if (!pci_is_pcie(pdev)) {
+		pci_warn_once(pdev, "not a PCIe device\n");
+		return NULL;
+	}
+
+	switch (pci_pcie_type(pdev)) {
+	case PCI_EXP_TYPE_ENDPOINT:
+		if (pdev != ide->pdev) {
+			pci_warn_once(pdev, "setup expected Endpoint: %s\n", pci_name(ide->pdev));
+			return NULL;
+		}
+		return &ide->partner[PCI_IDE_EP];
+	case PCI_EXP_TYPE_ROOT_PORT: {
+		struct pci_dev *rp = pcie_find_root_port(ide->pdev);
+
+		if (pdev != rp) {
+			pci_warn_once(pdev, "setup expected Root Port: %s\n",
+				      pci_name(rp));
+			return NULL;
+		}
+		return &ide->partner[PCI_IDE_RP];
+	}
+	default:
+		pci_warn_once(pdev, "invalid device type\n");
+		return NULL;
+	}
+}
+EXPORT_SYMBOL_GPL(pci_ide_to_settings);
+
+static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide,
+			    struct pci_ide_partner *settings, int pos,
+			    bool enable)
+{
+	u32 val = FIELD_PREP(PCI_IDE_SEL_CTL_ID, ide->stream_id) |
+		  FIELD_PREP(PCI_IDE_SEL_CTL_DEFAULT, settings->default_stream) |
+		  FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, pdev->ide_cfg) |
+		  FIELD_PREP(PCI_IDE_SEL_CTL_TEE_LIMITED, pdev->ide_tee_limit) |
+		  FIELD_PREP(PCI_IDE_SEL_CTL_EN, enable);
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
+}
+
+/**
+ * pci_ide_stream_setup() - program settings to Selective IDE Stream registers
+ * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
+ * @ide: registered IDE settings descriptor
+ *
+ * When @pdev is a PCI_EXP_TYPE_ENDPOINT then the PCI_IDE_EP partner
+ * settings are written to @pdev's Selective IDE Stream register block,
+ * and when @pdev is a PCI_EXP_TYPE_ROOT_PORT, the PCI_IDE_RP settings
+ * are selected.
+ */
+void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	int pos;
+	u32 val;
+
+	if (!settings)
+		return;
+
+	pos = sel_ide_offset(pdev, settings);
+
+	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
+
+	val = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
+	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, settings->rid_start) |
+	      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, pci_ide_domain(pdev));
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
+
+	/*
+	 * Setup control register early for devices that expect
+	 * stream_id is set during key programming.
+	 */
+	set_ide_sel_ctl(pdev, ide, settings, pos, false);
+	settings->setup = 1;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_setup);
+
+/**
+ * pci_ide_stream_teardown() - disable the stream and clear all settings
+ * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
+ * @ide: registered IDE settings descriptor
+ *
+ * For stream destruction, zero all registers that may have been written
+ * by pci_ide_stream_setup(). Consider pci_ide_stream_disable() to leave
+ * settings in place while temporarily disabling the stream.
+ */
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	int pos;
+
+	if (!settings)
+		return;
+
+	pos = sel_ide_offset(pdev, settings);
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, 0);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, 0);
+	settings->setup = 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_teardown);
+
+/**
+ * pci_ide_stream_enable() - enable a Selective IDE Stream
+ * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
+ * @ide: registered and setup IDE settings descriptor
+ *
+ * Activate the stream by writing to the Selective IDE Stream Control
+ * Register.
+ *
+ * Return: 0 if the stream successfully entered the "secure" state, and -EINVAL
+ * if @ide is invalid, and -ENXIO if the stream fails to enter the secure state.
+ *
+ * Note that the state may go "insecure" at any point after returning 0, but
+ * those events are equivalent to a "link down" event and handled via
+ * asynchronous error reporting.
+ *
+ * Caller is responsible to clear the enable bit in the -ENXIO case.
+ */
+int pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	int pos;
+	u32 val;
+
+	if (!settings)
+		return -EINVAL;
+
+	pos = sel_ide_offset(pdev, settings);
+
+	set_ide_sel_ctl(pdev, ide, settings, pos, true);
+	settings->enable = 1;
+
+	pci_read_config_dword(pdev, pos + PCI_IDE_SEL_STS, &val);
+	if (FIELD_GET(PCI_IDE_SEL_STS_STATE, val) !=
+	    PCI_IDE_SEL_STS_STATE_SECURE)
+		return -ENXIO;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_enable);
+
+/**
+ * pci_ide_stream_disable() - disable a Selective IDE Stream
+ * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
+ * @ide: registered and setup IDE settings descriptor
+ *
+ * Clear the Selective IDE Stream Control Register, but leave all other
+ * registers untouched.
+ */
+void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	int pos;
+
+	if (!settings)
+		return;
+
+	pos = sel_ide_offset(pdev, settings);
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
+	settings->enable = 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_disable);
+
+void pci_ide_init_host_bridge(struct pci_host_bridge *hb)
+{
+	hb->nr_ide_streams = 256;
+	ida_init(&hb->ide_stream_ida);
+}
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 3b54f1720be5..93fa7ba8dfa6 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -672,6 +672,7 @@ static void pci_init_host_bridge(struct pci_host_bridge *bridge)
 	bridge->native_dpc = 1;
 	bridge->domain_nr = PCI_DOMAIN_NR_NOT_SET;
 	bridge->native_cxl_error = 1;
+	pci_ide_init_host_bridge(bridge);
 
 	device_initialize(&bridge->dev);
 }

---

## [9] Dan Williams — 2025-10-31
*Subject: [PATCH v8 8/9] PCI/IDE: Report available IDE streams*

The limited number of link-encryption (IDE) streams that a given set of
host bridges supports is a platform specific detail. Provide
pci_ide_init_nr_streams() as a generic facility for either platform TSM
drivers, or PCI core native IDE, to report the number available streams.
After invoking pci_ide_init_nr_streams() an "available_secure_streams"
attribute appears in PCI host bridge sysfs to convey that count.

Introduce a device-type, @pci_host_bridge_type, now that both a release
method and sysfs attribute groups are being specified for all 'struct
pci_host_bridge' instances.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge | 12 ++++
 drivers/pci/pci.h                             |  1 +
 include/linux/pci-ide.h                       |  1 +
 drivers/pci/ide.c                             | 67 +++++++++++++++++++
 drivers/pci/probe.c                           | 14 +++-
 5 files changed, 94 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index 2c66e5bb2bf8..b91ec3450811 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -31,3 +31,15 @@ Description:
 		platform specific pool of stream resources shared by the Root
 		Ports in a host bridge. See /sys/devices/pciDDDD:BB entry for
 		details about the DDDD:BB format.
+
+What:		pciDDDD:BB/available_secure_streams
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host bridge has Root Ports that support PCIe IDE
+		(link encryption and integrity protection) there may be a
+		limited number of Selective IDE Streams that can be used for
+		establishing new end-to-end secure links. This attribute
+		decrements upon secure link setup, and increments upon secure
+		link teardown. The in-use stream count is determined by counting
+		stream symlinks. See /sys/devices/pciDDDD:BB entry for details
+		about the DDDD:BB format.
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index d3f16be40102..f6ffe5ee4717 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -616,6 +616,7 @@ static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 #ifdef CONFIG_PCI_IDE
 void pci_ide_init(struct pci_dev *dev);
 void pci_ide_init_host_bridge(struct pci_host_bridge *hb);
+extern const struct attribute_group pci_ide_attr_group;
 #else
 static inline void pci_ide_init(struct pci_dev *dev) { }
 static inline void pci_ide_init_host_bridge(struct pci_host_bridge *hb) { }
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index e638f9429bf9..85645b0a8620 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -63,6 +63,7 @@ struct pci_ide {
 	const char *name;
 };
 
+void pci_ide_set_nr_streams(struct pci_host_bridge *hb, u16 nr);
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev,
 					    struct pci_ide *ide);
 struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 7643840738fe..4ae3872589fc 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -514,3 +514,70 @@ void pci_ide_init_host_bridge(struct pci_host_bridge *hb)
 	hb->nr_ide_streams = 256;
 	ida_init(&hb->ide_stream_ida);
 }
+
+static ssize_t available_secure_streams_show(struct device *dev,
+					     struct device_attribute *attr,
+					     char *buf)
+{
+	struct pci_host_bridge *hb = to_pci_host_bridge(dev);
+	int nr = READ_ONCE(hb->nr_ide_streams);
+	int avail = nr;
+
+	if (!nr)
+		return -ENXIO;
+
+	/*
+	 * Yes, this is inefficient and racy, but it is only for occasional
+	 * platform resource surveys. Worst case is bounded to 256 streams.
+	 */
+	for (int i = 0; i < nr; i++)
+		if (ida_exists(&hb->ide_stream_ida, i))
+			avail--;
+	return sysfs_emit(buf, "%d\n", avail);
+}
+static DEVICE_ATTR_RO(available_secure_streams);
+
+static struct attribute *pci_ide_attrs[] = {
+	&dev_attr_available_secure_streams.attr,
+	NULL
+};
+
+static umode_t pci_ide_attr_visible(struct kobject *kobj, struct attribute *a, int n)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct pci_host_bridge *hb = to_pci_host_bridge(dev);
+
+	if (a == &dev_attr_available_secure_streams.attr)
+		if (!hb->nr_ide_streams)
+			return 0;
+
+	return a->mode;
+}
+
+const struct attribute_group pci_ide_attr_group = {
+	.attrs = pci_ide_attrs,
+	.is_visible = pci_ide_attr_visible,
+};
+
+/**
+ * pci_ide_set_nr_streams() - sets size of the pool of IDE Stream resources
+ * @hb: host bridge boundary for the stream pool
+ * @nr: number of streams
+ *
+ * Platform PCI init and/or expert test module use only. Limit IDE
+ * Stream establishment by setting the number of stream resources
+ * available at the host bridge. Platform init code must set this before
+ * the first pci_ide_stream_alloc() call if the platform has less than the
+ * default of 256 streams per host-bridge.
+ *
+ * The "PCI_IDE" symbol namespace is required because this is typically
+ * a detail that is settled in early PCI init. I.e. this export is not
+ * for endpoint drivers.
+ */
+void pci_ide_set_nr_streams(struct pci_host_bridge *hb, u16 nr)
+{
+	hb->nr_ide_streams = min(nr, 256);
+	WARN_ON_ONCE(!ida_is_empty(&hb->ide_stream_ida));
+	sysfs_update_group(&hb->dev.kobj, &pci_ide_attr_group);
+}
+EXPORT_SYMBOL_NS_GPL(pci_ide_set_nr_streams, "PCI_IDE");
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 93fa7ba8dfa6..cfacf5bcd073 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -653,6 +653,18 @@ static void pci_release_host_bridge_dev(struct device *dev)
 	kfree(bridge);
 }
 
+static const struct attribute_group *pci_host_bridge_groups[] = {
+#ifdef CONFIG_PCI_IDE
+	&pci_ide_attr_group,
+#endif
+	NULL
+};
+
+static const struct device_type pci_host_bridge_type = {
+	.groups = pci_host_bridge_groups,
+	.release = pci_release_host_bridge_dev,
+};
+
 static void pci_init_host_bridge(struct pci_host_bridge *bridge)
 {
 	INIT_LIST_HEAD(&bridge->windows);
@@ -672,6 +684,7 @@ static void pci_init_host_bridge(struct pci_host_bridge *bridge)
 	bridge->native_dpc = 1;
 	bridge->domain_nr = PCI_DOMAIN_NR_NOT_SET;
 	bridge->native_cxl_error = 1;
+	bridge->dev.type = &pci_host_bridge_type;
 	pci_ide_init_host_bridge(bridge);
 
 	device_initialize(&bridge->dev);
@@ -686,7 +699,6 @@ struct pci_host_bridge *pci_alloc_host_bridge(size_t priv)
 		return NULL;
 
 	pci_init_host_bridge(bridge);
-	bridge->dev.release = pci_release_host_bridge_dev;
 
 	return bridge;
 }

---

## [10] Dan Williams — 2025-10-31
*Subject: [PATCH v8 9/9] PCI/TSM: Report active IDE streams*

Given that the platform TSM owns IDE Stream ID allocation, report the
active streams via the TSM class device. Establish a symlink from the
class device to the PCI endpoint device consuming the stream, named by
the Stream ID.

Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm | 10 ++++++++
 include/linux/pci-ide.h                   |  2 ++
 include/linux/tsm.h                       |  3 +++
 drivers/pci/ide.c                         |  4 ++++
 drivers/virt/coco/tsm-core.c              | 28 +++++++++++++++++++++++
 5 files changed, 47 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 2949468deaf7..6fc1a5ac6da1 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -7,3 +7,13 @@ Description:
 		signals when the PCI layer is able to support establishment of
 		link encryption and other device-security features coordinated
 		through a platform tsm.
+
+What:		/sys/class/tsm/tsmN/streamH.R.E
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host bridge has established a secure connection via
+		the platform TSM, symlink appears. The primary function of this
+		is have a system global review of TSM resource consumption
+		across host bridges. The link points to the endpoint PCI device
+		and matches the same link published by the host bridge. See
+		Documentation/ABI/testing/sysfs-devices-pci-host-bridge.
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 85645b0a8620..d0f10f3c89fc 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -50,6 +50,7 @@ struct pci_ide_partner {
  * @host_bridge_stream: allocated from host bridge @ide_stream_ida pool
  * @stream_id: unique Stream ID (within Partner Port pairing)
  * @name: name of the established Selective IDE Stream in sysfs
+ * @tsm_dev: For TSM established IDE, the TSM device context
  *
  * Negative @stream_id values indicate "uninitialized" on the
  * expectation that with TSM established IDE the TSM owns the stream_id
@@ -61,6 +62,7 @@ struct pci_ide {
 	u8 host_bridge_stream;
 	int stream_id;
 	const char *name;
+	struct tsm_dev *tsm_dev;
 };
 
 void pci_ide_set_nr_streams(struct pci_host_bridge *hb, u16 nr);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 22e05b2aac69..a3b7ab668eff 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -123,4 +123,7 @@ int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
+struct pci_ide;
+int tsm_ide_stream_register(struct pci_ide *ide);
+void tsm_ide_stream_unregister(struct pci_ide *ide);
 #endif /* __TSM_H */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 4ae3872589fc..da5b1acccbb4 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -11,6 +11,7 @@
 #include <linux/pci_regs.h>
 #include <linux/slab.h>
 #include <linux/sysfs.h>
+#include <linux/tsm.h>
 
 #include "pci.h"
 
@@ -261,6 +262,9 @@ void pci_ide_stream_release(struct pci_ide *ide)
 	if (ide->partner[PCI_IDE_EP].enable)
 		pci_ide_stream_disable(pdev, ide);
 
+	if (ide->tsm_dev)
+		tsm_ide_stream_unregister(ide);
+
 	if (ide->partner[PCI_IDE_RP].setup)
 		pci_ide_stream_teardown(rp, ide);
 
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 0e705f3067a1..f027876a2f19 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -4,11 +4,13 @@
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
 
 #include <linux/tsm.h>
+#include <linux/pci.h>
 #include <linux/rwsem.h>
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 
 static struct class *tsm_class;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -106,6 +108,32 @@ void tsm_unregister(struct tsm_dev *tsm_dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+/* must be invoked between tsm_register / tsm_unregister */
+int tsm_ide_stream_register(struct pci_ide *ide)
+{
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct tsm_dev *tsm_dev = tsm->tsm_dev;
+	int rc;
+
+	rc = sysfs_create_link(&tsm_dev->dev.kobj, &pdev->dev.kobj, ide->name);
+	if (rc)
+		return rc;
+
+	ide->tsm_dev = tsm_dev;
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_register);
+
+void tsm_ide_stream_unregister(struct pci_ide *ide)
+{
+	struct tsm_dev *tsm_dev = ide->tsm_dev;
+
+	ide->tsm_dev = NULL;
+	sysfs_remove_link(&tsm_dev->dev.kobj, ide->name);
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);

---

## [11] Jonathan Cameron — 2025-11-03
*Subject: Re: [PATCH v8 7/9] PCI/IDE: Add IDE establishment helpers*

On Fri, 31 Oct 2025 14:28:59 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [12] Xu Yilun — 2025-11-08
*Subject: Re: [PATCH v8 1/9] coco/tsm: Introduce a core device for TEE
 Security Managers*

On Fri, Oct 31, 2025 at 02:28:53PM -0700, Dan Williams wrote:
> A "TSM" is a platform component that provides an API for securely
> provisioning resources for a confidential guest (TVM) to consume. The

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> Signed-off-by: Dan Williams <dan.j.williams@intel.com>

---

## [13] Xu Yilun — 2025-11-09
*Subject: Re: [PATCH v8 2/9] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Fri, Oct 31, 2025 at 02:28:54PM -0700, Dan Williams wrote:
> Link encryption is a new PCIe feature enumerated by "PCIe r7.0 section
> 7.9.26 IDE Extended Capability".

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> Signed-off-by: Dan Williams <dan.j.williams@intel.com>

---

## [14] Xu Yilun — 2025-11-10
*Subject: Re: [PATCH v8 4/9] PCI/TSM: Establish Secure Sessions and Link
 Encryption*

> +#ifdef CONFIG_PCI_TSM
> +int pci_tsm_register(struct tsm_dev *tsm_dev);

Any concern to keep the stub without PCI_TSM?
pci_tsm_pf0_constructor/destructor() don't do this.

> +{
> +	return -ENXIO;

[...]

> diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> new file mode 100644

No need the bitfield.h

> +#include <linux/pci.h>
> +#include <linux/pci-doe.h>

No need the xarray.h

Anyway, they are all minor and cause no impact, I don't expect a new
version.

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [15] Xu Yilun — 2025-11-10
*Subject: Re: [PATCH v8 5/9] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Fri, Oct 31, 2025 at 02:28:57PM -0700, Dan Williams wrote:
> PCIe r7.0 Section 7.7.9 Device 3 Extended Capability Structure, defines the
> canonical location for determining the Flit Mode of a device. This status

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> Signed-off-by: Dan Williams <dan.j.williams@intel.com>

---

## [16] Xu Yilun — 2025-11-10
*Subject: Re: [PATCH v8 7/9] PCI/IDE: Add IDE establishment helpers*

> +{
> +	if (!pci_is_pcie(pdev)) {

No need the braces

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> +		struct pci_dev *rp = pcie_find_root_port(ide->pdev);
> +

---

## [17] Xu Yilun — 2025-11-10
*Subject: Re: [PATCH v8 8/9] PCI/IDE: Report available IDE streams*

On Fri, Oct 31, 2025 at 02:29:00PM -0700, Dan Williams wrote:
> The limited number of link-encryption (IDE) streams that a given set of
> host bridges supports is a platform specific detail. Provide

Should be updated to pci_ide_set_nr_streams().

> drivers, or PCI core native IDE, to report the number available streams.
> After invoking pci_ide_init_nr_streams() an "available_secure_streams"

I suppose should also be pci_ide_set_nr_streams() here.

> attribute appears in PCI host bridge sysfs to convey that count.

I don't see how it appears later. 

> +static umode_t pci_ide_attr_visible(struct kobject *kobj, struct attribute *a, int n)
> +{

The previous patch unconditionally initializes nr_ide_streams to 256, so
this check is not functional for "appear later". Maybe remove it.

> +
> +	return a->mode;

Also no need to update group, is it?


Should be easy to address these concerns. I believe I can also:

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> +}

---

## [18] Xu Yilun — 2025-11-10
*Subject: Re: [PATCH v8 9/9] PCI/TSM: Report active IDE streams*

On Fri, Oct 31, 2025 at 02:29:01PM -0700, Dan Williams wrote:
> Given that the platform TSM owns IDE Stream ID allocation, report the
> active streams via the TSM class device. Establish a symlink from the

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> Signed-off-by: Dan Williams <dan.j.williams@intel.com>

---

## [19] dan.j.williams@intel.com — 2025-11-10
*Subject: Re: [PATCH v8 4/9] PCI/TSM: Establish Secure Sessions and Link
 Encryption*

Xu Yilun wrote:
> > +#ifdef CONFIG_PCI_TSM
> > +int pci_tsm_register(struct tsm_dev *tsm_dev);

True. There should be no callers of this when CONFIG_PCI_TSM=n. Will
append a cleanup for this.

> 
> > +{

Ah yes, holdovers from early versions, will append your reviewed-by in
the pull request.

> 
> Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [20] dan.j.williams@intel.com — 2025-11-10
*Subject: Re: [PATCH v8 7/9] PCI/IDE: Add IDE establishment helpers*

Xu Yilun wrote:
> > +{
> > +	if (!pci_is_pcie(pdev)) {

Some older ARM compilers apparently still care:

http://lore.kernel.org/032cd284-1b0e-4d52-94d8-e37fc9a759fc@arm.com

...so, leaving this for now.

---

## [21] dan.j.williams@intel.com — 2025-11-10
*Subject: Re: [PATCH v8 8/9] PCI/IDE: Report available IDE streams*

Xu Yilun wrote:
> On Fri, Oct 31, 2025 at 02:29:00PM -0700, Dan Williams wrote:
> > The limited number of link-encryption (IDE) streams that a given set of

Ah true, after this switched to the new model of initializing to max by
default, failed to come back and fixup the changelog.

> > attribute appears in PCI host bridge sysfs to convey that count.
> 

It still holds true that the attribute appears after registering the TSM
driver.

> > +static umode_t pci_ide_attr_visible(struct kobject *kobj, struct attribute *a, int n)
> > +{

It is still valid for cases where pci_ide_set_nr_streams() is called at
runtime to make the attribute disappear. Not that we have those cases
yet, but the mechanism is that this attribute dynamically appears and
disappears as the IDE configuration changes.

> 
> > +

Unless zero is forbidden as an argument to pci_ide_set_nr_streams().
That base expectation of "available_secure_streams may disappear
dynamically" is something that userspace needs to contend.

---
