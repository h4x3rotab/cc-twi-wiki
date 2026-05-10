---
title: 'PCI/TSM: Core infrastructure for PCI device security (TDISP)'
date: 2025-09-11
last_reply: 2025-09-26
message_count: 24
participants: ['Dan Williams', 'Alexey Kardashevskiy', 'Jonathan Cameron', 'Aneesh Kumar K.V', 'Jason Gunthorpe']
---

## [1] Dan Williams — 2025-09-11

[apologies for the duplicates, I flubbed my mailing list aliases]

Changes since v5 [1]:
- Add @tsm_dev parameter to 'struct pci_tsm_link_ops::probe()' (Alexey)
- Fix to_pci_tsm_pf0() to walk to the DSM device (Alexey)
- Fix IDE establishment "default stream" setting regression (Alexey)
- Fix pci_ide_stream_enable() in the presence of devices that delay the
  "secure" transition to K_SET_GO (Alexey)
- Make sure pci_ide_stream_enable() has a unique error code for the
  "failed to go to secure state" case. (Alexey)
- Clarify that pci_tsm_connect() unconditionally probes all potential
  TDIs (Alexey)
- Rename 'struct pci_tsm_security_ops' to 'struct pci_tsm_devsec_ops'
  (Alexey)
- Add @tsm_dev parameter to 'struct pci_tsm_devsec_ops::lock()' (Alexey)
- Pass 'struct pci_tsm *' to 'struct pci_tsm_devsec_ops::unlock()' (Alexey)
- Rename 'struct pci_tsm::dsm' 'struct pci_tsm::dsm_dev' (Aneesh)
- Rename 'struct pci_tsm_pf0::base' to 'struct pci_tsm_pf0::base_tsm'
  (Aneesh)
- Make definition of 'struct tsm_dev' public, drop tsm_name() and
  tsm_pci_ops() helpers.
- Drop __devsec_pci_ops (delayed cleanup now possible with 'struct
  tsm_dev' public) (Jonathan)
- Revive pci_tsm_doe_transfer() (Aneesh)
- Fix tsm_unregister() to not assume that all TSMs implement PCI
  operations

[1]: http://lore.kernel.org/20250827035126.1356683-1-dan.j.williams@intel.com

This set is available at
https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging
(rebasing branch) or devsec-20250911 (immutable tag). It passes a basic
smoke test that exercises load/unload of the samples/devsec/ modules and
connect/disconnect of the emulated device. Note that tag also has a
preview of changes that will be included in v2 of "[PATCH 0/7] PCI/TSM:
TEE I/O infrastructure" [2].

[2]: http://lore.kernel.org/20250827035259.1356758-1-dan.j.williams@intel.com

Status: ->connect() flow is nearly settled
------------------------------------------
The review feedback continues to slow. Various folks have had their
naming and organization preferences adopted so I feel comfortable
calling this a consensus branch. Let us leave any further requests for
naming changes to Bjorn.

This version seems suitable for proceeding to linux-next inclusion. That
inclusion depends on the guest side TEE I/O infrastructure also
settling. That guest set definitely needs at least a v2 [2]. In short,
PCI core infrastructure for TEE I/O (both host and guest) targeting
linux-next inclusion post v6.18-rc1.

Next steps:
-----------
- Stage at least one vendor ->connect() implementation on top of a
  tsm.git#staging snapshot.

- Find an arrangement to supplement samples/devsec/ regression testing
  with IDE establishment / "connect()" flow regression testing.

Original Cover letter:
----------------------

Trusted execution environment (TEE) Device Interface Security Protocol
(TDISP) is a chapter name in the PCI specification. It describes an
alphabet soup of mechanisms, SPDM, CMA, IDE, TSM/DSM, that system
software uses to establish trust in a device and assign it to a
confidential virtual machine (CVM). It is protocol for dynamically
extending the trusted computing boundary (TCB) of a CVM with a PCI
device interface that can issue DMA to CVM private memory.

The acronym soup problem is enhanced by every major platform vendor
having distinct TEE Security Manager (TSM) API implementations /
capabilities, and to a lesser extent, every potential endpoint Device
Security Manager (DSM) having its own idiosyncratic behaviors around
TDISP state transitions.

Despite all that opportunity for differentiation, there is a significant
portion of the implementation that is cross-vendor common. However, it
is difficult to develop, debate, test and settle all those pieces absent
a low level TSM driver implementation to pull it all together.

The proposal, of which this set is the first phase, is incrementally
develop the shared infrastructure on top of a sample TSM driver
implementation to enable clean vendor agnostic discussions about the
commons. "samples/devsec/" is meant to be: just enough emulation to
exercise all the core infrastructure, a reference implementation, and a
simple unit test. The sample also enables coordination with the native
PCI device security effort [3].

[3]: http://lore.kernel.org/cover.1719771133.git.lukas@wunner.de

Dan Williams (10):
  coco/tsm: Introduce a core device for TEE Security Managers
  PCI/IDE: Enumerate Selective Stream IDE capabilities
  PCI: Introduce pci_walk_bus_reverse(), for_each_pci_dev_reverse()
  PCI/TSM: Authenticate devices via platform TSM
  samples/devsec: Introduce a PCI device-security bus + endpoint sample
  PCI: Add PCIe Device 3 Extended Capability enumeration
  PCI/IDE: Add IDE establishment helpers
  PCI/IDE: Report available IDE streams
  PCI/TSM: Report active IDE streams
  samples/devsec: Add sample IDE establishment

 Documentation/ABI/testing/sysfs-bus-pci       |  51 ++
 Documentation/ABI/testing/sysfs-class-tsm     |  19 +
 .../ABI/testing/sysfs-devices-pci-host-bridge |  26 +
 Documentation/driver-api/pci/index.rst        |   1 +
 Documentation/driver-api/pci/tsm.rst          |  12 +
 MAINTAINERS                                   |   7 +-
 drivers/base/bus.c                            |  38 +
 drivers/pci/Kconfig                           |  29 +
 drivers/pci/Makefile                          |   2 +
 drivers/pci/bus.c                             |  38 +
 drivers/pci/doe.c                             |   2 -
 drivers/pci/ide.c                             | 584 ++++++++++++++
 drivers/pci/pci-sysfs.c                       |   4 +
 drivers/pci/pci.h                             |  19 +
 drivers/pci/probe.c                           |  28 +-
 drivers/pci/remove.c                          |   6 +
 drivers/pci/search.c                          |  62 +-
 drivers/pci/tsm.c                             | 627 +++++++++++++++
 drivers/virt/coco/Kconfig                     |   3 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tsm-core.c                  | 166 ++++
 include/linux/device/bus.h                    |   3 +
 include/linux/pci-doe.h                       |   4 +
 include/linux/pci-ide.h                       |  75 ++
 include/linux/pci-tsm.h                       | 159 ++++
 include/linux/pci.h                           |  36 +
 include/linux/tsm.h                           |  14 +
 include/uapi/linux/pci_regs.h                 |  89 +++
 samples/Kconfig                               |  19 +
 samples/Makefile                              |   1 +
 samples/devsec/Makefile                       |  10 +
 samples/devsec/bus.c                          | 737 ++++++++++++++++++
 samples/devsec/common.c                       |  26 +
 samples/devsec/devsec.h                       |  40 +
 samples/devsec/link_tsm.c                     | 242 ++++++
 35 files changed, 3167 insertions(+), 13 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 Documentation/driver-api/pci/tsm.rst
 create mode 100644 drivers/pci/ide.c
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 drivers/virt/coco/tsm-core.c
 create mode 100644 include/linux/pci-ide.h
 create mode 100644 include/linux/pci-tsm.h
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/link_tsm.c


base-commit: 650d64cdd69122cc60d309f2f5fd72bbc080dbd7

---

## [2] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 01/10] coco/tsm: Introduce a core device for TEE Security Managers*

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

Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Co-developed-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm |   9 ++
 MAINTAINERS                               |   2 +-
 drivers/virt/coco/Kconfig                 |   3 +
 drivers/virt/coco/Makefile                |   1 +
 drivers/virt/coco/tsm-core.c              | 109 ++++++++++++++++++++++
 include/linux/tsm.h                       |   4 +
 6 files changed, 127 insertions(+), 1 deletion(-)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 drivers/virt/coco/tsm-core.c

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
diff --git a/MAINTAINERS b/MAINTAINERS
index b65289db4822..024b18244c65 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -25613,7 +25613,7 @@ S:	Maintained
 F:	Documentation/devicetree/bindings/trigger-source/gpio-trigger.yaml
 F:	Documentation/devicetree/bindings/trigger-source/pwm-trigger.yaml
 
-TRUSTED SECURITY MODULE (TSM) INFRASTRUCTURE
+TRUSTED EXECUTION ENVIRONMENT SECURITY MANAGER (TSM)
 M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
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
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
new file mode 100644
index 000000000000..a64b776642cf
--- /dev/null
+++ b/drivers/virt/coco/tsm-core.c
@@ -0,0 +1,109 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <linux/tsm.h>
+#include <linux/idr.h>
+#include <linux/rwsem.h>
+#include <linux/device.h>
+#include <linux/module.h>
+#include <linux/cleanup.h>
+
+static struct class *tsm_class;
+static DECLARE_RWSEM(tsm_rwsem);
+static DEFINE_IDR(tsm_idr);
+
+struct tsm_dev {
+	struct device dev;
+	int id;
+};
+
+static struct tsm_dev *alloc_tsm_dev(struct device *parent)
+{
+	struct tsm_dev *tsm_dev __free(kfree) =
+		kzalloc(sizeof(*tsm_dev), GFP_KERNEL);
+	struct device *dev;
+	int id;
+
+	if (!tsm_dev)
+		return ERR_PTR(-ENOMEM);
+
+	guard(rwsem_write)(&tsm_rwsem);
+	id = idr_alloc(&tsm_idr, tsm_dev, 0, INT_MAX, GFP_KERNEL);
+	if (id < 0)
+		return ERR_PTR(id);
+
+	tsm_dev->id = id;
+	dev = &tsm_dev->dev;
+	dev->parent = parent;
+	dev->class = tsm_class;
+	device_initialize(dev);
+	return no_free_ptr(tsm_dev);
+}
+
+static void put_tsm_dev(struct tsm_dev *tsm_dev)
+{
+	if (!IS_ERR_OR_NULL(tsm_dev))
+		put_device(&tsm_dev->dev);
+}
+
+DEFINE_FREE(put_tsm_dev, struct tsm_dev *,
+	    if (!IS_ERR_OR_NULL(_T)) put_tsm_dev(_T))
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
+	guard(rwsem_write)(&tsm_rwsem);
+	idr_remove(&tsm_idr, tsm_dev->id);
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
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 431054810dca..aa906eb67360 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,7 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <linux/device.h>
 
 #define TSM_REPORT_INBLOB_MAX 64
 #define TSM_REPORT_OUTBLOB_MAX SZ_32K
@@ -109,4 +110,7 @@ struct tsm_report_ops {
 
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
+struct tsm_dev;
+struct tsm_dev *tsm_register(struct device *parent);
+void tsm_unregister(struct tsm_dev *tsm_dev);
 #endif /* __TSM_H */

base-commit: 650d64cdd69122cc60d309f2f5fd72bbc080dbd7

---

## [3] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 02/10] PCI/IDE: Enumerate Selective Stream IDE capabilities*

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

Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Kconfig           | 14 ++++++
 drivers/pci/Makefile          |  1 +
 drivers/pci/ide.c             | 92 +++++++++++++++++++++++++++++++++++
 drivers/pci/pci.h             |  6 +++
 drivers/pci/probe.c           |  1 +
 include/linux/pci.h           |  7 +++
 include/uapi/linux/pci_regs.h | 81 ++++++++++++++++++++++++++++++
 7 files changed, 202 insertions(+)
 create mode 100644 drivers/pci/ide.c

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 9a249c65aedc..105b72b93613 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -122,6 +122,20 @@ config XEN_PCIDEV_FRONTEND
 config PCI_ATS
 	bool
 
+config PCI_IDE
+	bool
+
+config PCI_IDE_STREAM_MAX
+	int "Maximum number of Selective IDE Streams supported per host bridge" if EXPERT
+	depends on PCI_IDE
+	range 1 256
+	default 64
+	help
+	  Set a kernel max for the number of IDE streams the PCI core supports
+	  per device. While the PCI specification max is 256, the hardware
+	  platform capability for the foreseeable future is 4 to 8 streams. Bump
+	  this value up if you have an expert testing need.
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
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
new file mode 100644
index 000000000000..05ab8c18b768
--- /dev/null
+++ b/drivers/pci/ide.c
@@ -0,0 +1,92 @@
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
+	 * Assume a constant number of address association resources per
+	 * stream index
+	 */
+	return offset + stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);
+}
+
+void pci_ide_init(struct pci_dev *pdev)
+{
+	u8 nr_link_ide, nr_ide_mem, nr_streams;
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
+	 * Require endpoint IDE capability to be paired with IDE Root
+	 * Port IDE capability.
+	 */
+	if (pci_pcie_type(pdev) == PCI_EXP_TYPE_ENDPOINT) {
+		struct pci_dev *rp = pcie_find_root_port(pdev);
+
+		if (!rp->ide_cap)
+			return;
+	}
+
+	if (val & PCI_IDE_CAP_SEL_CFG)
+		pdev->ide_cfg = 1;
+
+	if (val & PCI_IDE_CAP_TEE_LIMITED)
+		pdev->ide_tee_limit = 1;
+
+	if (val & PCI_IDE_CAP_LINK)
+		nr_link_ide = 1 + FIELD_GET(PCI_IDE_CAP_LINK_TC_NUM, val);
+	else
+		nr_link_ide = 0;
+
+	nr_ide_mem = 0;
+	nr_streams = min(1 + FIELD_GET(PCI_IDE_CAP_SEL_NUM, val),
+			 CONFIG_PCI_IDE_STREAM_MAX);
+	for (u8 i = 0; i < nr_streams; i++) {
+		int pos = __sel_ide_offset(ide_cap, nr_link_ide, i, nr_ide_mem);
+		int nr_assoc;
+		u32 val;
+
+		pci_read_config_dword(pdev, pos, &val);
+
+		/*
+		 * Let's not entertain streams that do not have a
+		 * constant number of address association blocks
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
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 34f65d69662e..56851e73439b 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -519,6 +519,12 @@ static inline void pci_doe_sysfs_init(struct pci_dev *pdev) { }
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
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 1de6e3be6375..4fd6942ea6a8 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2642,6 +2642,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
+	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 9b2c753aa192..7b9c11a582e9 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -538,6 +538,13 @@ struct pci_dev {
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
index f5b17745de60..051f9e7a20ce 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -751,6 +751,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_PL_64GT	0x31	/* Physical Layer 64.0 GT/s */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_PL_64GT
 
@@ -1239,4 +1240,84 @@
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
+#define  PCI_IDE_SEL_CAP_ASSOC_NUM	__GENMASK(3, 0)
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

---

## [4] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 03/10] PCI: Introduce pci_walk_bus_reverse(), for_each_pci_dev_reverse()*

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
 drivers/base/bus.c         | 38 +++++++++++++++++++++++
 drivers/pci/bus.c          | 38 +++++++++++++++++++++++
 drivers/pci/search.c       | 62 +++++++++++++++++++++++++++++++++-----
 include/linux/device/bus.h |  3 ++
 include/linux/pci.h        | 11 +++++++
 5 files changed, 144 insertions(+), 8 deletions(-)

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
index b77fd30bbfd9..1a090da18e59 100644
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
@@ -425,6 +426,27 @@ static int __pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void
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
@@ -446,6 +468,22 @@ void pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void *), void
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
+	guard(rwsem_read)(&pci_bus_sem);
+	__pci_walk_bus_reverse(top, cb, userdata);
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
index 7b9c11a582e9..6fb0e8a95078 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -581,6 +581,8 @@ struct pci_dev *pci_alloc_dev(struct pci_bus *bus);
 
 #define	to_pci_dev(n) container_of(n, struct pci_dev, dev)
 #define for_each_pci_dev(d) while ((d = pci_get_device(PCI_ANY_ID, PCI_ANY_ID, d)) != NULL)
+#define for_each_pci_dev_reverse(d) \
+	while ((d = pci_get_device_reverse(PCI_ANY_ID, PCI_ANY_ID, d)) != NULL)
 
 static inline int pci_channel_offline(struct pci_dev *pdev)
 {
@@ -1241,6 +1243,8 @@ u64 pci_get_dsn(struct pci_dev *dev);
 
 struct pci_dev *pci_get_device(unsigned int vendor, unsigned int device,
 			       struct pci_dev *from);
+struct pci_dev *pci_get_device_reverse(unsigned int vendor, unsigned int device,
+				       struct pci_dev *from);
 struct pci_dev *pci_get_subsys(unsigned int vendor, unsigned int device,
 			       unsigned int ss_vendor, unsigned int ss_device,
 			       struct pci_dev *from);
@@ -1660,6 +1664,8 @@ int pci_scan_bridge(struct pci_bus *bus, struct pci_dev *dev, int max,
 
 void pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void *),
 		  void *userdata);
+void pci_walk_bus_reverse(struct pci_bus *top,
+			  int (*cb)(struct pci_dev *, void *), void *userdata);
 int pci_cfg_space_size(struct pci_dev *dev);
 unsigned char pci_bus_max_busnr(struct pci_bus *bus);
 resource_size_t pcibios_window_alignment(struct pci_bus *bus,
@@ -2055,6 +2061,11 @@ static inline struct pci_dev *pci_get_device(unsigned int vendor,
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

---

## [5] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via platform TSM*

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
virtual device (TDI). These are the guest side operations in TDISP. Only
link management operations are defined at this stage and placeholders
provided for the security operations.

The locking allows for multiple devices to be executing commands
simultaneously, one outstanding command per-device and an rwsem
synchronizes the implementation relative to TSM
registration/unregistration events.

Thanks to Wu Hao for his work on an early draft of this support.

Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-bus-pci |  51 ++
 Documentation/driver-api/pci/index.rst  |   1 +
 Documentation/driver-api/pci/tsm.rst    |  12 +
 MAINTAINERS                             |   4 +-
 drivers/pci/Kconfig                     |  15 +
 drivers/pci/Makefile                    |   1 +
 drivers/pci/doe.c                       |   2 -
 drivers/pci/pci-sysfs.c                 |   4 +
 drivers/pci/pci.h                       |  10 +
 drivers/pci/probe.c                     |   3 +
 drivers/pci/remove.c                    |   6 +
 drivers/pci/tsm.c                       | 627 ++++++++++++++++++++++++
 drivers/virt/coco/tsm-core.c            |  40 +-
 include/linux/pci-doe.h                 |   4 +
 include/linux/pci-tsm.h                 | 159 ++++++
 include/linux/pci.h                     |   3 +
 include/linux/tsm.h                     |  11 +-
 include/uapi/linux/pci_regs.h           |   1 +
 18 files changed, 943 insertions(+), 11 deletions(-)
 create mode 100644 Documentation/driver-api/pci/tsm.rst
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 include/linux/pci-tsm.h

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 69f952fffec7..e0c8dad8d889 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -612,3 +612,54 @@ Description:
 
 		  # ls doe_features
 		  0001:01        0001:02        doe_discovery
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
index 000000000000..59b94d79a4f2
--- /dev/null
+++ b/Documentation/driver-api/pci/tsm.rst
@@ -0,0 +1,12 @@
+.. SPDX-License-Identifier: GPL-2.0
+.. include:: <isonum.txt>
+
+========================================================
+PCI Trusted Execution Environment Security Manager (TSM)
+========================================================
+
+.. kernel-doc:: include/linux/pci-tsm.h
+   :internal:
+
+.. kernel-doc:: drivers/pci/tsm.c
+   :export:
diff --git a/MAINTAINERS b/MAINTAINERS
index 024b18244c65..f1aabab88c79 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -25619,8 +25619,10 @@ L:	linux-coco@lists.linux.dev
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
diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 105b72b93613..0183ca6f6954 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -136,6 +136,21 @@ config PCI_IDE_STREAM_MAX
 	  platform capability for the foreseeable future is 4 to 8 streams. Bump
 	  this value up if you have an expert testing need.
 
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
index 5eea14c1f7f5..367ca1bc5470 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1815,6 +1815,10 @@ const struct attribute_group *pci_dev_attr_groups[] = {
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
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 56851e73439b..0e24262aa4ba 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -525,6 +525,16 @@ void pci_ide_init(struct pci_dev *dev);
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
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 4fd6942ea6a8..7207f9a76a3e 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2738,6 +2738,9 @@ void pci_device_add(struct pci_dev *dev, struct pci_bus *bus)
 	ret = device_add(&dev->dev);
 	WARN_ON(ret < 0);
 
+	/* Establish pdev->tsm for newly added (e.g. new SR-IOV VFs) */
+	pci_tsm_init(dev);
+
 	pci_npem_create(dev);
 
 	pci_doe_sysfs_init(dev);
diff --git a/drivers/pci/remove.c b/drivers/pci/remove.c
index 445afdfa6498..4b9ad199389b 100644
--- a/drivers/pci/remove.c
+++ b/drivers/pci/remove.c
@@ -55,6 +55,12 @@ static void pci_destroy_dev(struct pci_dev *dev)
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
index 000000000000..724a58e3ccf1
--- /dev/null
+++ b/drivers/pci/tsm.c
@@ -0,0 +1,627 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * TEE Security Manager for the TEE Device Interface Security Protocol
+ * (TDISP, PCIe r6.1 sec 11)
+ *
+ * Copyright(c) 2024 Intel Corporation. All rights reserved.
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
+static inline bool is_dsm(struct pci_dev *pdev)
+{
+	return pdev->tsm && pdev->tsm->dsm_dev == pdev;
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
+	struct pci_dev *pdev = tsm->dsm_dev;
+
+	if (!is_pci_tsm_pf0(pdev) || !is_dsm(pdev)) {
+		pci_WARN_ONCE(tsm->pdev, 1, "invalid context object\n");
+		return NULL;
+	}
+
+	return container_of(tsm, struct pci_tsm_pf0, base_tsm);
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
+	tsm->ops->remove(tsm);
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
+	const struct pci_tsm_ops *ops = dsm_dev->tsm->ops;
+
+	pdev->tsm = ops->probe(ops->owner, pdev);
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
+	struct pci_tsm *pci_tsm __free(tsm_remove) =
+		ops->probe(ops->owner, pdev);
+
+	/* connect()  mutually exclusive with subfunction pci_tsm_init() */
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
+	pci_tsm_walk_fns(pdev, probe_fn, pdev);
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
+	tsm_dev = pdev->tsm->ops->owner;
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
+	struct tsm_dev *tsm_dev;
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
+	tsm_dev = find_tsm_dev(id);
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
+	const struct pci_tsm_ops *ops = pdev->tsm->ops;
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
+	tsm_dev = pdev->tsm->ops->owner;
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
+ * because @pdev always has a longer registered lifetime than its DSM by virtue
+ * of being a child of, or identical to, its DSM.
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
+ * @ops: PCI link operations provided by the TSM
+ */
+int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
+			     const struct pci_tsm_ops *ops)
+{
+	if (!is_link_tsm(ops->owner))
+		return -EINVAL;
+
+	tsm->dsm_dev = find_dsm_dev(pdev);
+	if (!tsm->dsm_dev) {
+		pci_warn(pdev, "failed to find Device Security Manager\n");
+		return -ENXIO;
+	}
+	tsm->pdev = pdev;
+	tsm->ops = ops;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_link_constructor);
+
+/**
+ * pci_tsm_pf0_constructor() - common 'struct pci_tsm_pf0' (DSM) initialization
+ * @pdev: Physical Function 0 PCI device (as indicated by is_pci_tsm_pf0())
+ * @tsm: context to initialize
+ * @ops: PCI link operations provided by the TSM
+ */
+int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
+			    const struct pci_tsm_ops *ops)
+{
+	mutex_init(&tsm->lock);
+	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					   PCI_DOE_PROTO_CMA);
+	if (!tsm->doe_mb) {
+		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
+		return -ENODEV;
+	}
+
+	return pci_tsm_link_constructor(pdev, &tsm->base_tsm, ops);
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
+	bool tee = pdev->devcap & PCI_EXP_DEVCAP_TEE;
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
+		tsm_dev = tsm->ops->owner;
+	else if (tsm_dev != tsm->ops->owner)
+		return;
+
+	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev))
+		pci_tsm_disconnect(pdev);
+	else
+		tsm_remove(pdev->tsm);
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
index a64b776642cf..f0bb580563c9 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -9,15 +9,18 @@
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
+#include <linux/pci-tsm.h>
 
 static struct class *tsm_class;
 static DECLARE_RWSEM(tsm_rwsem);
 static DEFINE_IDR(tsm_idr);
 
-struct tsm_dev {
-	struct device dev;
-	int id;
-};
+/* Caller responsible for ensuring it does not race tsm_dev unregistration */
+struct tsm_dev *find_tsm_dev(int id)
+{
+	guard(rcu)();
+	return idr_find(&tsm_idr, id);
+}
 
 static struct tsm_dev *alloc_tsm_dev(struct device *parent)
 {
@@ -42,6 +45,29 @@ static struct tsm_dev *alloc_tsm_dev(struct device *parent)
 	return no_free_ptr(tsm_dev);
 }
 
+static struct tsm_dev *tsm_register_pci_or_reset(struct tsm_dev *tsm_dev,
+						 struct pci_tsm_ops *pci_ops)
+{
+	int rc;
+
+	if (!pci_ops)
+		return tsm_dev;
+
+	pci_ops->owner = tsm_dev;
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
 static void put_tsm_dev(struct tsm_dev *tsm_dev)
 {
 	if (!IS_ERR_OR_NULL(tsm_dev))
@@ -51,7 +77,7 @@ static void put_tsm_dev(struct tsm_dev *tsm_dev)
 DEFINE_FREE(put_tsm_dev, struct tsm_dev *,
 	    if (!IS_ERR_OR_NULL(_T)) put_tsm_dev(_T))
 
-struct tsm_dev *tsm_register(struct device *parent)
+struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *pci_ops)
 {
 	struct tsm_dev *tsm_dev __free(put_tsm_dev) = alloc_tsm_dev(parent);
 	struct device *dev;
@@ -69,12 +95,14 @@ struct tsm_dev *tsm_register(struct device *parent)
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
diff --git a/include/linux/pci-doe.h b/include/linux/pci-doe.h
index 1f14aed4354b..7d839f4a6340 100644
--- a/include/linux/pci-doe.h
+++ b/include/linux/pci-doe.h
@@ -15,6 +15,10 @@
 
 struct pci_doe_mb;
 
+#define PCI_DOE_FEATURE_DISCOVERY 0
+#define PCI_DOE_PROTO_CMA 1
+#define PCI_DOE_PROTO_SSESSION 2
+
 struct pci_doe_mb *pci_find_doe_mailbox(struct pci_dev *pdev, u16 vendor,
 					u8 type);
 
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
new file mode 100644
index 000000000000..572aea6da27d
--- /dev/null
+++ b/include/linux/pci-tsm.h
@@ -0,0 +1,159 @@
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
+ * @sec_ops: Lock, unlock, and interrogate the security state of the
+ *	     function via the platform TSM (typically virtual function
+ *	     operations).
+ * @owner: Back reference to the TSM device that owns this instance.
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
+	struct tsm_dev *owner;
+};
+
+/**
+ * struct pci_tsm - Core TSM context for a given PCIe endpoint
+ * @pdev: Back ref to device function, distinguishes type of pci_tsm context
+ * @dsm: PCI Device Security Manager for link operations on @pdev
+ * @ops: Link Confidentiality or Device Function Security operations
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
+	const struct pci_tsm_ops *ops;
+};
+
+/**
+ * struct pci_tsm_pf0 - Physical Function 0 TDISP link context
+ * @base: generic core "tsm" context
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
+struct tsm_dev;
+int pci_tsm_register(struct tsm_dev *tsm_dev);
+void pci_tsm_unregister(struct tsm_dev *tsm_dev);
+int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
+			     const struct pci_tsm_ops *ops);
+int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
+			    const struct pci_tsm_ops *ops);
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
index 6fb0e8a95078..78c1e208d441 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -545,6 +545,9 @@ struct pci_dev {
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
index aa906eb67360..ee9a54ae3d3c 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -108,9 +108,16 @@ struct tsm_report_ops {
 	bool (*report_bin_attr_visible)(int n);
 };
 
+struct pci_tsm_ops;
+struct tsm_dev {
+	struct device dev;
+	int id;
+	const struct pci_tsm_ops *pci_ops;
+};
+
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
-struct tsm_dev;
-struct tsm_dev *tsm_register(struct device *parent);
+struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
+struct tsm_dev *find_tsm_dev(int id);
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 051f9e7a20ce..9d30307a3499 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -500,6 +500,7 @@
 #define  PCI_EXP_DEVCAP_PWR_VAL	0x03fc0000 /* Slot Power Limit Value */
 #define  PCI_EXP_DEVCAP_PWR_SCL	0x0c000000 /* Slot Power Limit Scale */
 #define  PCI_EXP_DEVCAP_FLR     0x10000000 /* Function Level Reset */
+#define  PCI_EXP_DEVCAP_TEE     0x40000000 /* TEE I/O (TDISP) Support */
 #define PCI_EXP_DEVCTL		0x08	/* Device Control */
 #define  PCI_EXP_DEVCTL_CERE	0x0001	/* Correctable Error Reporting En. */
 #define  PCI_EXP_DEVCTL_NFERE	0x0002	/* Non-Fatal Error Reporting Enable */

---

## [6] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 05/10] samples/devsec: Introduce a PCI device-security bus + endpoint sample*

Establish just enough emulated PCI infrastructure to register a sample
TSM (platform security manager) driver and have it discover an IDE + TEE
(link encryption + device-interface security protocol (TDISP)) capable
device.

Use the existing CONFIG_PCI_BRIDGE_EMUL to emulate an IDE capable root
port, and open code the emulation of an endpoint device via simulated
configuration cycle responses.

The devsec_tsm driver responds to the PCI core TSM operations as if it
successfully exercised the given interface security protocol message.

The devsec_bus and devsec_tsm drivers can be loaded in either order to
reflect cases like SEV-TIO where the TSM is PCI-device firmware, and
cases like TDX Connect where the TSM is a software agent running on the
host CPU.

Follow-on patches add common code for TSM managed IDE establishment. For
now, just successfully complete setup and teardown of the DSM (device
security manager) context as a building block for management of TDI
(trusted device interface) instances.

 # modprobe devsec_bus
    devsec_bus devsec_bus: PCI host bridge to bus 10000:00
    pci_bus 10000:00: root bus resource [bus 00-01]
    pci_bus 10000:00: root bus resource [mem 0xf000000000-0xffffffffff 64bit]
    pci 10000:00:00.0: [8086:7075] type 01 class 0x060400 PCIe Root Port
    pci 10000:00:00.0: PCI bridge to [bus 00]
    pci 10000:00:00.0:   bridge window [io  0x0000-0x0fff]
    pci 10000:00:00.0:   bridge window [mem 0x00000000-0x000fffff]
    pci 10000:00:00.0:   bridge window [mem 0x00000000-0x000fffff 64bit pref]
    pci 10000:00:00.0: bridge configuration invalid ([bus 00-00]), reconfiguring
    pci 10000:01:00.0: [8086:ffff] type 00 class 0x000000 PCIe Endpoint
    pci 10000:01:00.0: BAR 0 [mem 0xf000000000-0xf0001fffff 64bit pref]
    pci_doe_abort: pci 10000:01:00.0: DOE: [100] Issuing Abort
    pci_doe_cache_protocols: pci 10000:01:00.0: DOE: [100] Found protocol 0 vid: 1 prot: 1
    pci 10000:01:00.0: disabling ASPM on pre-1.1 PCIe device.  You can enable it with 'pcie_aspm=force'
    pci 10000:00:00.0: PCI bridge to [bus 01]
    pci_bus 10000:01: busn_res: [bus 01] end is updated to 01

 # modprobe devsec_link_tsm
    pf0_sysfs_enable: pci 10000:01:00.0: PCI/TSM: Device Security Manager detected (IDE TEE)

 # echo tsm0 > /sys/bus/pci/devices/10000:01:00.0/tsm/connect
    devsec_tsm_pf0_probe: pci 10000:01:00.0: devsec: TSM enabled

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 MAINTAINERS               |   1 +
 samples/Kconfig           |  19 +
 samples/Makefile          |   1 +
 samples/devsec/Makefile   |  10 +
 samples/devsec/bus.c      | 734 ++++++++++++++++++++++++++++++++++++++
 samples/devsec/common.c   |  26 ++
 samples/devsec/devsec.h   |  40 +++
 samples/devsec/link_tsm.c | 174 +++++++++
 8 files changed, 1005 insertions(+)
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/link_tsm.c

diff --git a/MAINTAINERS b/MAINTAINERS
index f1aabab88c79..c1ad1294560c 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -25623,6 +25623,7 @@ F:	Documentation/driver-api/pci/tsm.rst
 F:	drivers/pci/tsm.c
 F:	drivers/virt/coco/guest/
 F:	include/linux/*tsm*.h
+F:	samples/devsec/
 F:	samples/tsm-mr/
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/samples/Kconfig b/samples/Kconfig
index 6e072a5f1ed8..8a52fd08031a 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -324,6 +324,25 @@ source "samples/rust/Kconfig"
 
 source "samples/damon/Kconfig"
 
+config SAMPLE_DEVSEC
+	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
+	depends on m
+	depends on PCI
+	depends on VIRT_DRIVERS
+	depends on PCI_DOMAINS_GENERIC || X86
+	select PCI_BRIDGE_EMUL
+	select PCI_TSM
+	select TSM
+	help
+	  Build a sample platform TEE Security Manager (TSM) driver with a
+	  corresponding emulated PCIe topology. The resulting sample modules,
+	  devsec_bus and devsec_tsm, exercise device-security enumeration, PCI
+	  subsystem use ABIs, device security flows. For example, exercise IDE
+	  (link encryption) establishment and TDISP state transitions via a
+	  Device Security Manager (DSM).
+
+	  If unsure, say N
+
 endif # SAMPLES
 
 config HAVE_SAMPLE_FTRACE_DIRECT
diff --git a/samples/Makefile b/samples/Makefile
index 07641e177bd8..59b510ace9b2 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -45,3 +45,4 @@ obj-$(CONFIG_SAMPLE_DAMON_PRCL)		+= damon/
 obj-$(CONFIG_SAMPLE_DAMON_MTIER)	+= damon/
 obj-$(CONFIG_SAMPLE_HUNG_TASK)		+= hung_task/
 obj-$(CONFIG_SAMPLE_TSM_MR)		+= tsm-mr/
+obj-y					+= devsec/
diff --git a/samples/devsec/Makefile b/samples/devsec/Makefile
new file mode 100644
index 000000000000..da122eb8d23d
--- /dev/null
+++ b/samples/devsec/Makefile
@@ -0,0 +1,10 @@
+# SPDX-License-Identifier: GPL-2.0
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_common.o
+devsec_common-y := common.o
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_bus.o
+devsec_bus-y := bus.o
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_link_tsm.o
+devsec_link_tsm-y := link_tsm.o
diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
new file mode 100644
index 000000000000..07cf4ce82ceb
--- /dev/null
+++ b/samples/devsec/bus.c
@@ -0,0 +1,734 @@
+// SPDX-License-Identifier: GPL-2.0-only
+// Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved.
+
+#include <linux/bitfield.h>
+#include <linux/cleanup.h>
+#include <linux/device/faux.h>
+#include <linux/module.h>
+#include <linux/range.h>
+#include <uapi/linux/pci_regs.h>
+#include <linux/pci.h>
+
+#include "../../drivers/pci/pci-bridge-emul.h"
+#include "devsec.h"
+
+#define NR_DEVSEC_BUSES 1
+#define NR_PORT_STREAMS 1
+#define NR_ADDR_ASSOC 1
+
+struct devsec {
+	struct pci_host_bridge hb;
+	struct devsec_sysdata sysdata;
+	struct resource busnr_res;
+	struct resource mmio_res;
+	struct resource prefetch_res;
+	struct pci_bus *bus;
+	struct device *dev;
+	struct devsec_port {
+		union {
+			struct devsec_ide {
+				u32 cap;
+				u32 ctl;
+				struct devsec_stream {
+					u32 cap;
+					u32 ctl;
+					u32 status;
+					u32 rid1;
+					u32 rid2;
+					struct devsec_addr_assoc {
+						u32 assoc1;
+						u32 assoc2;
+						u32 assoc3;
+					} assoc[NR_ADDR_ASSOC];
+				} stream[NR_PORT_STREAMS];
+			} ide __packed;
+			char ide_regs[sizeof(struct devsec_ide)];
+		};
+		struct pci_bridge_emul bridge;
+	} *devsec_ports[NR_DEVSEC_BUSES];
+	struct devsec_dev {
+		struct devsec *devsec;
+		struct range mmio_range;
+		u8 __cfg[SZ_4K];
+		struct devsec_dev_doe {
+			int cap;
+			u32 req[SZ_4K / sizeof(u32)];
+			u32 rsp[SZ_4K / sizeof(u32)];
+			int write, read, read_ttl;
+		} doe;
+		u16 ide_pos;
+		union {
+			struct devsec_ide ide __packed;
+			char ide_regs[sizeof(struct devsec_ide)];
+		};
+	} *devsec_devs[NR_DEVSEC_BUSES];
+};
+
+#define devsec_base(x) ((void __force __iomem *) &(x)->__cfg[0])
+
+static struct devsec *bus_to_devsec(struct pci_bus *bus)
+{
+	return container_of(bus->sysdata, struct devsec, sysdata);
+}
+
+static int devsec_dev_config_read(struct devsec *devsec, struct pci_bus *bus,
+				  unsigned int devfn, int pos, int size,
+				  u32 *val)
+{
+	struct devsec_dev *devsec_dev;
+	struct devsec_dev_doe *doe;
+	void __iomem *base;
+
+	if (PCI_FUNC(devfn) != 0 ||
+	    PCI_SLOT(devfn) >= ARRAY_SIZE(devsec->devsec_devs))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_dev = devsec->devsec_devs[PCI_SLOT(devfn)];
+	base = devsec_base(devsec_dev);
+	doe = &devsec_dev->doe;
+
+	if (pos == doe->cap + PCI_DOE_READ) {
+		if (doe->read_ttl > 0) {
+			*val = doe->rsp[doe->read];
+			dev_dbg(&bus->dev, "devfn: %#x doe read[%d]\n", devfn,
+				doe->read);
+		} else {
+			*val = 0;
+			dev_dbg(&bus->dev, "devfn: %#x doe no data\n", devfn);
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (pos == doe->cap + PCI_DOE_STATUS) {
+		if (doe->read_ttl > 0) {
+			*val = PCI_DOE_STATUS_DATA_OBJECT_READY;
+			dev_dbg(&bus->dev, "devfn: %#x object ready\n", devfn);
+		} else if (doe->read_ttl < 0) {
+			*val = PCI_DOE_STATUS_ERROR;
+			dev_dbg(&bus->dev, "devfn: %#x error\n", devfn);
+		} else {
+			*val = 0;
+			dev_dbg(&bus->dev, "devfn: %#x idle\n", devfn);
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (pos >= devsec_dev->ide_pos &&
+		   pos < devsec_dev->ide_pos + sizeof(struct devsec_ide)) {
+		*val = *(u32 *) &devsec_dev->ide_regs[pos - devsec_dev->ide_pos];
+		return PCIBIOS_SUCCESSFUL;
+	}
+
+	switch (size) {
+	case 1:
+		*val = readb(base + pos);
+		break;
+	case 2:
+		*val = readw(base + pos);
+		break;
+	case 4:
+		*val = readl(base + pos);
+		break;
+	default:
+		PCI_SET_ERROR_RESPONSE(val);
+		return PCIBIOS_BAD_REGISTER_NUMBER;
+	}
+	return PCIBIOS_SUCCESSFUL;
+}
+
+static int devsec_port_config_read(struct devsec *devsec, unsigned int devfn,
+				   int pos, int size, u32 *val)
+{
+	struct devsec_port *devsec_port;
+
+	if (PCI_FUNC(devfn) != 0 ||
+	    PCI_SLOT(devfn) >= ARRAY_SIZE(devsec->devsec_ports))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_port = devsec->devsec_ports[PCI_SLOT(devfn)];
+	return pci_bridge_emul_conf_read(&devsec_port->bridge, pos, size, val);
+}
+
+static int devsec_pci_read(struct pci_bus *bus, unsigned int devfn, int pos,
+			   int size, u32 *val)
+{
+	struct devsec *devsec = bus_to_devsec(bus);
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (bus == devsec->hb.bus)
+		return devsec_port_config_read(devsec, devfn, pos, size, val);
+	else if (bus->parent == devsec->hb.bus)
+		return devsec_dev_config_read(devsec, bus, devfn, pos, size,
+					      val);
+
+	return PCIBIOS_DEVICE_NOT_FOUND;
+}
+
+#ifndef PCI_DOE_PROTOCOL_DISCOVERY
+#define PCI_DOE_PROTOCOL_DISCOVERY 0
+#define PCI_DOE_FEATURE_CMA 1
+#endif
+
+/* just indicate support for CMA */
+static void doe_process(struct devsec_dev_doe *doe)
+{
+	u8 type;
+	u16 vid;
+
+	vid = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_VID, doe->req[0]);
+	type = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_TYPE, doe->req[0]);
+
+	if (vid != PCI_VENDOR_ID_PCI_SIG) {
+		doe->read_ttl = -1;
+		return;
+	}
+
+	if (type != PCI_DOE_PROTOCOL_DISCOVERY) {
+		doe->read_ttl = -1;
+		return;
+	}
+
+	doe->rsp[0] = doe->req[0];
+	doe->rsp[1] = FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_2_LENGTH, 3);
+	doe->read_ttl = 3;
+	doe->rsp[2] = FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_VID,
+				 PCI_VENDOR_ID_PCI_SIG) |
+		      FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL,
+				 PCI_DOE_FEATURE_CMA) |
+		      FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_NEXT_INDEX, 0);
+}
+
+static int devsec_dev_config_write(struct devsec *devsec, struct pci_bus *bus,
+				   unsigned int devfn, int pos, int size,
+				   u32 val)
+{
+	struct devsec_dev *devsec_dev;
+	struct devsec_dev_doe *doe;
+	struct devsec_ide *ide;
+	void __iomem *base;
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (PCI_FUNC(devfn) != 0 ||
+	    PCI_SLOT(devfn) >= ARRAY_SIZE(devsec->devsec_devs))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_dev = devsec->devsec_devs[PCI_SLOT(devfn)];
+	base = devsec_base(devsec_dev);
+	doe = &devsec_dev->doe;
+	ide = &devsec_dev->ide;
+
+	if (pos >= PCI_BASE_ADDRESS_0 && pos <= PCI_BASE_ADDRESS_5) {
+		if (size != 4)
+			return PCIBIOS_BAD_REGISTER_NUMBER;
+		/* only one 64-bit mmio bar emulated for now */
+		if (pos == PCI_BASE_ADDRESS_0)
+			val &= ~lower_32_bits(range_len(&devsec_dev->mmio_range) - 1);
+		else if (pos == PCI_BASE_ADDRESS_1)
+			val &= ~upper_32_bits(range_len(&devsec_dev->mmio_range) - 1);
+		else
+			val = 0;
+	} else if (pos == PCI_ROM_ADDRESS) {
+		val = 0;
+	} else if (pos == doe->cap + PCI_DOE_CTRL) {
+		if (val & PCI_DOE_CTRL_GO) {
+			dev_dbg(&bus->dev, "devfn: %#x doe go\n", devfn);
+			doe_process(doe);
+		}
+		if (val & PCI_DOE_CTRL_ABORT) {
+			dev_dbg(&bus->dev, "devfn: %#x doe abort\n", devfn);
+			doe->write = 0;
+			doe->read = 0;
+			doe->read_ttl = 0;
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (pos == doe->cap + PCI_DOE_WRITE) {
+		if (doe->write < ARRAY_SIZE(doe->req))
+			doe->req[doe->write++] = val;
+		dev_dbg(&bus->dev, "devfn: %#x doe write[%d]\n", devfn,
+			doe->write - 1);
+		return PCIBIOS_SUCCESSFUL;
+	} else if (pos == doe->cap + PCI_DOE_READ) {
+		if (doe->read_ttl > 0) {
+			doe->read_ttl--;
+			doe->read++;
+			dev_dbg(&bus->dev, "devfn: %#x doe ack[%d]\n", devfn,
+				doe->read - 1);
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (pos >= devsec_dev->ide_pos &&
+		   pos < devsec_dev->ide_pos + sizeof(struct devsec_ide)) {
+		u16 ide_off = pos - devsec_dev->ide_pos;
+
+		for (int i = 0; i < NR_PORT_STREAMS; i++) {
+			struct devsec_stream *stream = &ide->stream[i];
+
+			if (ide_off != offsetof(typeof(*ide), stream[i].ctl))
+				continue;
+
+			stream->ctl = val;
+			stream->status &= ~PCI_IDE_SEL_STS_STATE;
+			if (val & PCI_IDE_SEL_CTL_EN)
+				stream->status |= FIELD_PREP(
+					PCI_IDE_SEL_STS_STATE,
+					PCI_IDE_SEL_STS_STATE_SECURE);
+			else
+				stream->status |= FIELD_PREP(
+					PCI_IDE_SEL_STS_STATE,
+					PCI_IDE_SEL_STS_STATE_INSECURE);
+			return PCIBIOS_SUCCESSFUL;
+		}
+	}
+
+	switch (size) {
+	case 1:
+		writeb(val, base + pos);
+		break;
+	case 2:
+		writew(val, base + pos);
+		break;
+	case 4:
+		writel(val, base + pos);
+		break;
+	default:
+		return PCIBIOS_BAD_REGISTER_NUMBER;
+	}
+	return PCIBIOS_SUCCESSFUL;
+}
+
+static int devsec_port_config_write(struct devsec *devsec, struct pci_bus *bus,
+				    unsigned int devfn, int pos, int size,
+				    u32 val)
+{
+	struct devsec_port *devsec_port;
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (PCI_FUNC(devfn) != 0 ||
+	    PCI_SLOT(devfn) >= ARRAY_SIZE(devsec->devsec_ports))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_port = devsec->devsec_ports[PCI_SLOT(devfn)];
+	return pci_bridge_emul_conf_write(&devsec_port->bridge, pos, size, val);
+}
+
+static int devsec_pci_write(struct pci_bus *bus, unsigned int devfn, int pos,
+			    int size, u32 val)
+{
+	struct devsec *devsec = bus_to_devsec(bus);
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (bus == devsec->hb.bus)
+		return devsec_port_config_write(devsec, bus, devfn, pos, size,
+						val);
+	else if (bus->parent == devsec->hb.bus)
+		return devsec_dev_config_write(devsec, bus, devfn, pos, size,
+					       val);
+	return PCIBIOS_DEVICE_NOT_FOUND;
+}
+
+static struct pci_ops devsec_ops = {
+	.read = devsec_pci_read,
+	.write = devsec_pci_write,
+};
+
+static void destroy_bus(void *data)
+{
+	struct pci_host_bridge *hb = data;
+
+	pci_stop_root_bus(hb->bus);
+	pci_remove_root_bus(hb->bus);
+}
+
+static u32 build_ext_cap_header(u32 id, u32 ver, u32 next)
+{
+	return FIELD_PREP(GENMASK(15, 0), id) |
+	       FIELD_PREP(GENMASK(19, 16), ver) |
+	       FIELD_PREP(GENMASK(31, 20), next);
+}
+
+static void init_ide(struct devsec_ide *ide)
+{
+	ide->cap = PCI_IDE_CAP_SELECTIVE | PCI_IDE_CAP_IDE_KM |
+		   PCI_IDE_CAP_TEE_LIMITED |
+		   FIELD_PREP(PCI_IDE_CAP_SEL_NUM, NR_PORT_STREAMS - 1);
+
+	for (int i = 0; i < NR_PORT_STREAMS; i++)
+		ide->stream[i].cap =
+			FIELD_PREP(PCI_IDE_SEL_CAP_ASSOC_NUM, NR_ADDR_ASSOC);
+}
+
+static void init_dev_cfg(struct devsec_dev *devsec_dev)
+{
+	void __iomem *base = devsec_base(devsec_dev), *cap_base;
+	int pos, next;
+
+	/* BAR space */
+	writew(0x8086, base + PCI_VENDOR_ID);
+	writew(0xffff, base + PCI_DEVICE_ID);
+	writew(PCI_CLASS_ACCELERATOR_PROCESSING, base + PCI_CLASS_DEVICE);
+	writel(lower_32_bits(devsec_dev->mmio_range.start) |
+		       PCI_BASE_ADDRESS_MEM_TYPE_64 |
+		       PCI_BASE_ADDRESS_MEM_PREFETCH,
+	       base + PCI_BASE_ADDRESS_0);
+	writel(upper_32_bits(devsec_dev->mmio_range.start),
+	       base + PCI_BASE_ADDRESS_1);
+
+	/* Capability init */
+	writeb(PCI_HEADER_TYPE_NORMAL, base + PCI_HEADER_TYPE);
+	writew(PCI_STATUS_CAP_LIST, base + PCI_STATUS);
+	pos = 0x40;
+	writew(pos, base + PCI_CAPABILITY_LIST);
+
+	/* PCI-E Capability */
+	cap_base = base + pos;
+	writeb(PCI_CAP_ID_EXP, cap_base);
+	writew(PCI_EXP_TYPE_ENDPOINT, cap_base + PCI_EXP_FLAGS);
+	writew(PCI_EXP_LNKSTA_CLS_2_5GB | PCI_EXP_LNKSTA_NLW_X1, cap_base + PCI_EXP_LNKSTA);
+	writel(PCI_EXP_DEVCAP_FLR | PCI_EXP_DEVCAP_TEE, cap_base + PCI_EXP_DEVCAP);
+
+	/* DOE Extended Capability */
+	pos = PCI_CFG_SPACE_SIZE;
+	next = pos + PCI_DOE_CAP_SIZEOF;
+	cap_base = base + pos;
+	devsec_dev->doe.cap = pos;
+	writel(build_ext_cap_header(PCI_EXT_CAP_ID_DOE, 2, next), cap_base);
+
+	/* IDE Extended Capability */
+	pos = next;
+	cap_base = base + pos;
+	writel(build_ext_cap_header(PCI_EXT_CAP_ID_IDE, 1, 0), cap_base);
+	devsec_dev->ide_pos = pos + 4;
+	init_ide(&devsec_dev->ide);
+}
+
+#define MMIO_SIZE SZ_2M
+#define PREFETCH_SIZE SZ_2M
+
+static void destroy_devsec_dev(void *devsec_dev)
+{
+	kfree(devsec_dev);
+}
+
+static struct devsec_dev *devsec_dev_alloc(struct devsec *devsec, int hb)
+{
+	struct devsec_dev *devsec_dev __free(kfree) =
+		kzalloc(sizeof(*devsec_dev), GFP_KERNEL);
+	u64 start = devsec->prefetch_res.start + hb * PREFETCH_SIZE;
+
+	if (!devsec_dev)
+		return ERR_PTR(-ENOMEM);
+
+	*devsec_dev = (struct devsec_dev) {
+		.mmio_range = {
+			.start = start,
+			.end = start + PREFETCH_SIZE - 1,
+		},
+		.devsec = devsec,
+	};
+	init_dev_cfg(devsec_dev);
+
+	return_ptr(devsec_dev);
+}
+
+static int alloc_dev(struct devsec *devsec, int hb)
+{
+	struct devsec_dev *devsec_dev = devsec_dev_alloc(devsec, hb);
+	int rc;
+
+	if (IS_ERR(devsec_dev))
+		return PTR_ERR(devsec_dev);
+	rc = devm_add_action_or_reset(devsec->dev, destroy_devsec_dev,
+				      devsec_dev);
+	if (rc)
+		return rc;
+	devsec->devsec_devs[hb] = devsec_dev;
+
+	return 0;
+}
+
+static pci_bridge_emul_read_status_t
+devsec_bridge_read_base(struct pci_bridge_emul *bridge, int pos, u32 *val)
+{
+	return PCI_BRIDGE_EMUL_NOT_HANDLED;
+}
+
+static pci_bridge_emul_read_status_t
+devsec_bridge_read_pcie(struct pci_bridge_emul *bridge, int pos, u32 *val)
+{
+	return PCI_BRIDGE_EMUL_NOT_HANDLED;
+}
+
+static pci_bridge_emul_read_status_t
+devsec_bridge_read_ext(struct pci_bridge_emul *bridge, int pos, u32 *val)
+{
+	struct devsec_port *devsec_port = bridge->data;
+
+	/* only one extended capability, IDE... */
+	if (pos == 0) {
+		*val = build_ext_cap_header(PCI_EXT_CAP_ID_IDE, 1, 0);
+		return PCI_BRIDGE_EMUL_HANDLED;
+	}
+
+	if (pos < 4)
+		return PCI_BRIDGE_EMUL_NOT_HANDLED;
+
+	pos -= 4;
+	if (pos < sizeof(struct devsec_ide)) {
+		*val = *(u32 *)(&devsec_port->ide_regs[pos]);
+		return PCI_BRIDGE_EMUL_HANDLED;
+	}
+
+	return PCI_BRIDGE_EMUL_NOT_HANDLED;
+}
+
+static void devsec_bridge_write_base(struct pci_bridge_emul *bridge, int pos,
+				     u32 old, u32 new, u32 mask)
+{
+}
+
+static void devsec_bridge_write_pcie(struct pci_bridge_emul *bridge, int pos,
+				     u32 old, u32 new, u32 mask)
+{
+}
+
+static void devsec_bridge_write_ext(struct pci_bridge_emul *bridge, int pos,
+				    u32 old, u32 new, u32 mask)
+{
+	struct devsec_port *devsec_port = bridge->data;
+
+	if (pos < sizeof(struct devsec_ide))
+		*(u32 *)(&devsec_port->ide_regs[pos]) = new;
+}
+
+static const struct pci_bridge_emul_ops devsec_bridge_ops = {
+	.read_base = devsec_bridge_read_base,
+	.write_base = devsec_bridge_write_base,
+	.read_pcie = devsec_bridge_read_pcie,
+	.write_pcie = devsec_bridge_write_pcie,
+	.read_ext = devsec_bridge_read_ext,
+	.write_ext = devsec_bridge_write_ext,
+};
+
+static int init_port(struct devsec *devsec, struct devsec_port *devsec_port,
+		     int hb)
+{
+	const struct resource *mres = &devsec->mmio_res;
+	const struct resource *pres = &devsec->prefetch_res;
+	struct pci_bridge_emul *bridge = &devsec_port->bridge;
+	u16 membase = cpu_to_le16(upper_16_bits(mres->start + MMIO_SIZE * hb) &
+				  0xfff0);
+	u16 memlimit =
+		cpu_to_le16(upper_16_bits(mres->end + MMIO_SIZE * hb) & 0xfff0);
+	u16 pref_mem_base =
+		cpu_to_le16((upper_16_bits(lower_32_bits(pres->start +
+							 PREFETCH_SIZE * hb)) &
+			     0xfff0) |
+			    PCI_PREF_RANGE_TYPE_64);
+	u16 pref_mem_limit = cpu_to_le16(
+		(upper_16_bits(lower_32_bits(pres->end + PREFETCH_SIZE * hb)) &
+		 0xfff0) |
+		PCI_PREF_RANGE_TYPE_64);
+	u32 prefbaseupper =
+		cpu_to_le32(upper_32_bits(pres->start + PREFETCH_SIZE * hb));
+	u32 preflimitupper =
+		cpu_to_le32(upper_32_bits(pres->end + PREFETCH_SIZE * hb));
+
+	*bridge = (struct pci_bridge_emul) {
+		.conf = {
+			.vendor = cpu_to_le16(0x8086),
+			.device = cpu_to_le16(0xffff),
+			.class_revision = cpu_to_le32(0x1),
+			.primary_bus = 0,
+			.secondary_bus = hb + 1,
+			.subordinate_bus = hb + 1,
+			.membase = membase,
+			.memlimit = memlimit,
+			.pref_mem_base = pref_mem_base,
+			.pref_mem_limit = pref_mem_limit,
+			.prefbaseupper = prefbaseupper,
+			.preflimitupper = preflimitupper,
+		},
+		.pcie_conf = {
+			.devcap = cpu_to_le16(PCI_EXP_DEVCAP_FLR),
+			.lnksta = cpu_to_le16(PCI_EXP_LNKSTA_CLS_2_5GB),
+		},
+		.subsystem_vendor_id = cpu_to_le16(0x8086),
+		.has_pcie = true,
+		.data = devsec_port,
+		.ops = &devsec_bridge_ops,
+	};
+
+	init_ide(&devsec_port->ide);
+
+	return pci_bridge_emul_init(bridge, PCI_BRIDGE_EMUL_NO_IO_FORWARD);
+}
+
+static void destroy_port(void *data)
+{
+	struct devsec_port *devsec_port = data;
+
+	pci_bridge_emul_cleanup(&devsec_port->bridge);
+	kfree(devsec_port);
+}
+
+static struct devsec_port *devsec_port_alloc(struct devsec *devsec, int hb)
+{
+	int rc;
+
+	struct devsec_port *devsec_port __free(kfree) =
+		kzalloc(sizeof(*devsec_port), GFP_KERNEL);
+
+	if (!devsec_port)
+		return ERR_PTR(-ENOMEM);
+
+	rc = init_port(devsec, devsec_port, hb);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return_ptr(devsec_port);
+}
+
+static int alloc_port(struct devsec *devsec, int hb)
+{
+	struct devsec_port *devsec_port = devsec_port_alloc(devsec, hb);
+	int rc;
+
+	if (IS_ERR(devsec_port))
+		return PTR_ERR(devsec_port);
+	rc = devm_add_action_or_reset(devsec->dev, destroy_port, devsec_port);
+	if (rc)
+		return rc;
+	devsec->devsec_ports[hb] = devsec_port;
+
+	return 0;
+}
+
+static void release_mmio_region(void *res)
+{
+	remove_resource(res);
+}
+
+static void release_prefetch_region(void *res)
+{
+	remove_resource(res);
+}
+
+static int __init devsec_bus_probe(struct faux_device *fdev)
+{
+	int rc;
+	struct pci_bus *bus;
+	struct devsec *devsec;
+	struct devsec_sysdata *sd;
+	struct pci_host_bridge *hb;
+	struct device *dev = &fdev->dev;
+
+	hb = devm_pci_alloc_host_bridge(
+		dev, sizeof(*devsec) - sizeof(struct pci_host_bridge));
+	if (!hb)
+		return -ENOMEM;
+
+	devsec = container_of(hb, struct devsec, hb);
+	devsec->dev = dev;
+
+	devsec->mmio_res.name = "DEVSEC MMIO";
+	devsec->mmio_res.flags = IORESOURCE_MEM;
+	rc = allocate_resource(&iomem_resource, &devsec->mmio_res,
+			       MMIO_SIZE * NR_DEVSEC_BUSES, 0, SZ_4G, MMIO_SIZE,
+			       NULL, NULL);
+	if (rc)
+		return rc;
+
+	rc = devm_add_action_or_reset(dev, release_mmio_region,
+				      &devsec->mmio_res);
+	if (rc)
+		return rc;
+
+	devsec->prefetch_res.name = "DEVSEC PREFETCH";
+	devsec->prefetch_res.flags = IORESOURCE_MEM | IORESOURCE_MEM_64 |
+				     IORESOURCE_PREFETCH;
+	rc = allocate_resource(&iomem_resource, &devsec->prefetch_res,
+			       PREFETCH_SIZE * NR_DEVSEC_BUSES, SZ_4G, U64_MAX,
+			       PREFETCH_SIZE, NULL, NULL);
+	if (rc)
+		return rc;
+
+	rc = devm_add_action_or_reset(dev, release_prefetch_region,
+				      &devsec->prefetch_res);
+	if (rc)
+		return rc;
+
+	for (int i = 0; i < NR_DEVSEC_BUSES; i++) {
+		rc = alloc_port(devsec, i);
+		if (rc)
+			return rc;
+
+		rc = alloc_dev(devsec, i);
+		if (rc)
+			return rc;
+	}
+
+	devsec->busnr_res = (struct resource) {
+		.name = "DEVSEC BUSES",
+		.start = 0,
+		.end = NR_DEVSEC_BUSES + 1 - 1, /* 1 RP per HB */
+		.flags = IORESOURCE_BUS | IORESOURCE_PCI_FIXED,
+	};
+	pci_add_resource(&hb->windows, &devsec->busnr_res);
+	pci_add_resource(&hb->windows, &devsec->mmio_res);
+	pci_add_resource(&hb->windows, &devsec->prefetch_res);
+
+	sd = &devsec->sysdata;
+	devsec_sysdata = sd;
+
+	/* Start devsec_bus emulation above the last ACPI segment */
+	hb->domain_nr = pci_bus_find_emul_domain_nr(0, 0x10000, INT_MAX);
+	if (hb->domain_nr < 0)
+		return hb->domain_nr;
+
+	/*
+	 * Note, domain_nr is set in devsec_sysdata for
+	 * !CONFIG_PCI_DOMAINS_GENERIC platforms
+	 */
+	devsec_set_domain_nr(sd, hb->domain_nr);
+
+	hb->dev.parent = dev;
+	hb->sysdata = sd;
+	hb->ops = &devsec_ops;
+
+	rc = pci_scan_root_bus_bridge(hb);
+	if (rc)
+		return rc;
+
+	bus = hb->bus;
+	rc = devm_add_action_or_reset(dev, destroy_bus, no_free_ptr(hb));
+	if (rc)
+		return rc;
+
+	pci_assign_unassigned_bus_resources(bus);
+	pci_bus_add_devices(bus);
+
+	return 0;
+}
+
+static struct faux_device *devsec_bus;
+
+static struct faux_device_ops devsec_bus_ops = {
+	.probe = devsec_bus_probe,
+};
+
+static int __init devsec_bus_init(void)
+{
+	devsec_bus = faux_device_create("devsec_bus", NULL, &devsec_bus_ops);
+	if (!devsec_bus)
+		return -ENODEV;
+	return 0;
+}
+module_init(devsec_bus_init);
+
+static void __exit devsec_bus_exit(void)
+{
+	faux_device_destroy(devsec_bus);
+}
+module_exit(devsec_bus_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: TDISP Device Emulation");
diff --git a/samples/devsec/common.c b/samples/devsec/common.c
new file mode 100644
index 000000000000..de0078e4d614
--- /dev/null
+++ b/samples/devsec/common.c
@@ -0,0 +1,26 @@
+// SPDX-License-Identifier: GPL-2.0-only
+// Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved.
+
+#include <linux/pci.h>
+#include <linux/export.h>
+
+/*
+ * devsec_bus and devsec_tsm need a common location for this data to
+ * avoid depending on each other. Enables load order testing
+ */
+struct pci_sysdata *devsec_sysdata;
+EXPORT_SYMBOL_GPL(devsec_sysdata);
+
+static int __init common_init(void)
+{
+	return 0;
+}
+module_init(common_init);
+
+static void __exit common_exit(void)
+{
+}
+module_exit(common_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Shared data");
diff --git a/samples/devsec/devsec.h b/samples/devsec/devsec.h
new file mode 100644
index 000000000000..ae4274c86244
--- /dev/null
+++ b/samples/devsec/devsec.h
@@ -0,0 +1,40 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+// Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved.
+
+#ifndef __DEVSEC_H__
+#define __DEVSEC_H__
+struct devsec_sysdata {
+#ifdef CONFIG_X86
+	/*
+	 * Must be first member to that x86::pci_domain_nr() can type
+	 * pun devsec_sysdata and pci_sysdata.
+	 */
+	struct pci_sysdata sd;
+#else
+	int domain_nr;
+#endif
+};
+
+#ifdef CONFIG_X86
+static inline void devsec_set_domain_nr(struct devsec_sysdata *sd,
+					int domain_nr)
+{
+	sd->sd.domain = domain_nr;
+}
+static inline int devsec_get_domain_nr(struct devsec_sysdata *sd)
+{
+	return sd->sd.domain;
+}
+#else
+static inline void devsec_set_domain_nr(struct devsec_sysdata *sd,
+					int domain_nr)
+{
+	sd->domain_nr = domain_nr;
+}
+static inline int devsec_get_domain_nr(struct devsec_sysdata *sd)
+{
+	return sd->domain_nr;
+}
+#endif
+extern struct devsec_sysdata *devsec_sysdata;
+#endif /* __DEVSEC_H__ */
diff --git a/samples/devsec/link_tsm.c b/samples/devsec/link_tsm.c
new file mode 100644
index 000000000000..2faee8b41ede
--- /dev/null
+++ b/samples/devsec/link_tsm.c
@@ -0,0 +1,174 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved. */
+
+#define dev_fmt(fmt) "devsec: " fmt
+#include <linux/device/faux.h>
+#include <linux/pci-tsm.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include "devsec.h"
+
+struct devsec_tsm_pf0 {
+	struct pci_tsm_pf0 pci;
+#define NR_TSM_STREAMS 4
+};
+
+struct devsec_tsm_fn {
+	struct pci_tsm pci;
+};
+
+static struct devsec_tsm_pf0 *to_devsec_tsm_pf0(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct devsec_tsm_pf0, pci.base_tsm);
+}
+
+static struct devsec_tsm_fn *to_devsec_tsm_fn(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct devsec_tsm_fn, pci);
+}
+
+static struct pci_tsm *devsec_tsm_pf0_probe(struct tsm_dev *tsm_dev,
+					    struct pci_dev *pdev)
+{
+	int rc;
+
+	struct devsec_tsm_pf0 *devsec_tsm __free(kfree) =
+		kzalloc(sizeof(*devsec_tsm), GFP_KERNEL);
+	if (!devsec_tsm)
+		return NULL;
+
+	rc = pci_tsm_pf0_constructor(pdev, &devsec_tsm->pci, tsm_dev->pci_ops);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "TSM enabled\n");
+	return &no_free_ptr(devsec_tsm)->pci.base_tsm;
+}
+
+static struct pci_tsm *devsec_link_tsm_fn_probe(struct tsm_dev *tsm_dev,
+						struct pci_dev *pdev)
+{
+	int rc;
+
+	struct devsec_tsm_fn *devsec_tsm __free(kfree) =
+		kzalloc(sizeof(*devsec_tsm), GFP_KERNEL);
+	if (!devsec_tsm)
+		return NULL;
+
+	rc = pci_tsm_link_constructor(pdev, &devsec_tsm->pci, tsm_dev->pci_ops);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "TSM (sub-function) enabled\n");
+	return &no_free_ptr(devsec_tsm)->pci;
+}
+
+static struct pci_tsm *devsec_link_tsm_pci_probe(struct tsm_dev *tsm_dev,
+						 struct pci_dev *pdev)
+{
+	if (pdev->sysdata != devsec_sysdata)
+		return NULL;
+
+	if (is_pci_tsm_pf0(pdev))
+		return devsec_tsm_pf0_probe(tsm_dev, pdev);
+	return devsec_link_tsm_fn_probe(tsm_dev, pdev);
+}
+
+static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+
+	pci_dbg(pdev, "TSM disabled\n");
+
+	if (is_pci_tsm_pf0(pdev)) {
+		struct devsec_tsm_pf0 *devsec_tsm = to_devsec_tsm_pf0(tsm);
+
+		pci_tsm_pf0_destructor(&devsec_tsm->pci);
+		kfree(devsec_tsm);
+	} else {
+		struct devsec_tsm_fn *devsec_tsm = to_devsec_tsm_fn(tsm);
+
+		kfree(devsec_tsm);
+	}
+}
+
+/*
+ * Reference consumer for a TSM driver "connect" operation callback. The
+ * low-level TSM driver understands details about the platform the PCI
+ * core does not, like number of available streams that can be
+ * established per host bridge. The expected flow is:
+ *
+ * 1/ Allocate platform specific Stream resource (TSM specific)
+ * 2/ Allocate Stream Ids in the endpoint and Root Port (PCI TSM helper)
+ * 3/ Register Stream Ids for the consumed resources from the last 2
+ *    steps to be accountable (via sysfs) to the admin (PCI TSM helper)
+ * 4/ Register the Stream with the TSM core so that either PCI sysfs or
+ *    TSM core sysfs can list the in-use resources (TSM core helper)
+ * 5/ Configure IDE settings in the endpoint and Root Port (PCI TSM helper)
+ * 6/ RPC call to TSM to perform IDE_KM and optionally enable the stream
+ * (TSM Specific)
+ * 7/ Enable the stream in the endpoint, and root port if TSM call did
+ *    not already handle that (PCI TSM helper)
+ *
+ * The expectation is the helpers referenceed are convenience "library"
+ * APIs for common operations, not a "midlayer" that enforces a specific
+ * or use model sequencing.
+ */
+static int devsec_link_tsm_connect(struct pci_dev *pdev)
+{
+	return -ENXIO;
+}
+
+static void devsec_link_tsm_disconnect(struct pci_dev *pdev)
+{
+}
+
+static struct pci_tsm_ops devsec_link_pci_ops = {
+	.probe = devsec_link_tsm_pci_probe,
+	.remove = devsec_link_tsm_pci_remove,
+	.connect = devsec_link_tsm_connect,
+	.disconnect = devsec_link_tsm_disconnect,
+};
+
+static void devsec_link_tsm_remove(void *tsm_dev)
+{
+	tsm_unregister(tsm_dev);
+}
+
+static int devsec_link_tsm_probe(struct faux_device *fdev)
+{
+	struct tsm_dev *tsm_dev;
+
+	tsm_dev = tsm_register(&fdev->dev, &devsec_link_pci_ops);
+	if (IS_ERR(tsm_dev))
+		return PTR_ERR(tsm_dev);
+
+	return devm_add_action_or_reset(&fdev->dev, devsec_link_tsm_remove,
+					tsm_dev);
+}
+
+static struct faux_device *devsec_link_tsm;
+
+static const struct faux_device_ops devsec_link_device_ops = {
+	.probe = devsec_link_tsm_probe,
+};
+
+static int __init devsec_link_tsm_init(void)
+{
+	devsec_link_tsm = faux_device_create("devsec_link_tsm", NULL,
+					     &devsec_link_device_ops);
+	if (!devsec_link_tsm)
+		return -ENOMEM;
+	return 0;
+}
+module_init(devsec_link_tsm_init);
+
+static void __exit devsec_link_tsm_exit(void)
+{
+	faux_device_destroy(devsec_link_tsm);
+}
+module_exit(devsec_link_tsm_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Platform Link-TSM Driver");

---

## [7] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 06/10] PCI: Add PCIe Device 3 Extended Capability enumeration*

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
 drivers/pci/probe.c           | 12 ++++++++++++
 include/linux/pci.h           |  1 +
 include/uapi/linux/pci_regs.h |  7 +++++++
 3 files changed, 20 insertions(+)

diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 7207f9a76a3e..6e308199001c 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2271,6 +2271,17 @@ int pci_configure_extended_tags(struct pci_dev *dev, void *ign)
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
@@ -2642,6 +2653,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
+	pci_dev3_init(dev);		/* Device 3 capabilities */
 	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 78c1e208d441..d3880a4f175e 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -449,6 +449,7 @@ struct pci_dev {
 	unsigned int	pasid_enabled:1;	/* Process Address Space ID */
 	unsigned int	pri_enabled:1;		/* Page Request Interface */
 	unsigned int	tph_enabled:1;		/* TLP Processing Hints */
+	unsigned int	fm_enabled:1;		/* Flit Mode (segment captured) */
 	unsigned int	is_managed:1;		/* Managed via devres */
 	unsigned int	is_msi_managed:1;	/* MSI release via devres installed */
 	unsigned int	needs_freset:1;		/* Requires fundamental reset */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 9d30307a3499..b6ea1ffbf489 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -752,6 +752,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_DEV3	0x2F	/* Device 3 Capability/Control/Status */
 #define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_PL_64GT	0x31	/* Physical Layer 64.0 GT/s */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_PL_64GT
@@ -1236,6 +1237,12 @@
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

---

## [8] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 07/10] PCI/IDE: Add IDE establishment helpers*

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
 drivers/pci/ide.c                             | 429 ++++++++++++++++++
 include/linux/pci-ide.h                       |  73 +++
 include/linux/pci.h                           |   6 +
 4 files changed, 522 insertions(+)
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
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 05ab8c18b768..608ce79d830f 100644
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
 
@@ -23,6 +27,13 @@ static int __sel_ide_offset(u16 ide_cap, u8 nr_link_ide, u8 stream_index,
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
 	u8 nr_link_ide, nr_ide_mem, nr_streams;
@@ -88,5 +99,423 @@ void pci_ide_init(struct pci_dev *pdev)
 
 	pdev->ide_cap = ide_cap;
 	pdev->nr_link_ide = nr_link_ide;
+	pdev->nr_sel_ide = nr_streams;
 	pdev->nr_ide_mem = nr_ide_mem;
 }
+
+struct stream_index {
+	unsigned long *map;
+	u8 max, stream_index;
+};
+
+static void free_stream_index(struct stream_index *stream)
+{
+	clear_bit_unlock(stream->stream_index, stream->map);
+}
+
+DEFINE_FREE(free_stream, struct stream_index *, if (_T) free_stream_index(_T))
+static struct stream_index *alloc_stream_index(unsigned long *map, u8 max,
+					       struct stream_index *stream)
+{
+	if (!max)
+		return NULL;
+
+	do {
+		u8 stream_index = find_first_zero_bit(map, max);
+
+		if (stream_index == max)
+			return NULL;
+		if (!test_and_set_bit_lock(stream_index, map)) {
+			*stream = (struct stream_index) {
+				.map = map,
+				.max = max,
+				.stream_index = stream_index,
+			};
+			return stream;
+		}
+		/* collided with another stream acquisition */
+	} while (1);
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
+	/*
+	 * Catch buggy PCI platform initialization (missing
+	 * pci_ide_init_nr_streams())
+	 */
+	hb = pci_find_host_bridge(pdev->bus);
+	if (WARN_ON_ONCE(!hb->nr_ide_streams))
+		return NULL;
+
+	struct pci_ide *ide __free(kfree) = kzalloc(sizeof(*ide), GFP_KERNEL);
+	if (!ide)
+		return NULL;
+
+	struct stream_index *hb_stream __free(free_stream) = alloc_stream_index(
+		hb->ide_stream_map, hb->nr_ide_streams, &__stream[PCI_IDE_HB]);
+	if (!hb_stream)
+		return NULL;
+
+	rp = pcie_find_root_port(pdev);
+	struct stream_index *rp_stream __free(free_stream) = alloc_stream_index(
+		rp->ide_stream_map, rp->nr_sel_ide, &__stream[PCI_IDE_RP]);
+	if (!rp_stream)
+		return NULL;
+
+	struct stream_index *ep_stream __free(free_stream) = alloc_stream_index(
+		pdev->ide_stream_map, pdev->nr_sel_ide, &__stream[PCI_IDE_EP]);
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
+	clear_bit_unlock(ide->partner[PCI_IDE_EP].stream_index,
+			 pdev->ide_stream_map);
+	clear_bit_unlock(ide->partner[PCI_IDE_RP].stream_index,
+			 rp->ide_stream_map);
+	clear_bit_unlock(ide->host_bridge_stream, hb->ide_stream_map);
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
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
new file mode 100644
index 000000000000..5a7ffb1d826f
--- /dev/null
+++ b/include/linux/pci-ide.h
@@ -0,0 +1,73 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+/* PCIe 6.2 section 6.33 Integrity & Data Encryption (IDE) */
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
+ * @rid_start: Partner Port Requester ID range end
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
+ * @host_bridge_stream: track platform Stream ID
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
+struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide);
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
index d3880a4f175e..45360ba87538 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -544,6 +544,8 @@ struct pci_dev {
 	u16		ide_cap;	/* Link Integrity & Data Encryption */
 	u8		nr_ide_mem;	/* Address association resources for streams */
 	u8		nr_link_ide;	/* Link Stream count (Selective Stream offset) */
+	u8		nr_sel_ide;	/* Selective Stream count (register block allocator) */
+	DECLARE_BITMAP(ide_stream_map, CONFIG_PCI_IDE_STREAM_MAX);
 	unsigned int	ide_cfg:1;	/* Config cycles over IDE */
 	unsigned int	ide_tee_limit:1; /* Disallow T=0 traffic over IDE */
 #endif
@@ -613,6 +615,10 @@ struct pci_host_bridge {
 	int		domain_nr;
 	struct list_head windows;	/* resource_entry */
 	struct list_head dma_ranges;	/* dma ranges resource list */
+#ifdef CONFIG_PCI_IDE
+	u8 nr_ide_streams; /* Max streams possibly active in @ide_stream_map */
+	DECLARE_BITMAP(ide_stream_map, CONFIG_PCI_IDE_STREAM_MAX);
+#endif
 	u8 (*swizzle_irq)(struct pci_dev *, u8 *); /* Platform IRQ swizzler */
 	int (*map_irq)(const struct pci_dev *, u8, u8);
 	void (*release_fn)(struct pci_host_bridge *);

---

## [9] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 08/10] PCI/IDE: Report available IDE streams*

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
 drivers/pci/ide.c                             | 59 +++++++++++++++++++
 drivers/pci/pci.h                             |  3 +
 drivers/pci/probe.c                           | 12 +++-
 include/linux/pci.h                           |  8 +++
 5 files changed, 93 insertions(+), 1 deletion(-)

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
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 608ce79d830f..eb6e146e6fb5 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -519,3 +519,62 @@ void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide)
 	settings->enable = 0;
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_disable);
+
+static ssize_t available_secure_streams_show(struct device *dev,
+					     struct device_attribute *attr,
+					     char *buf)
+{
+	struct pci_host_bridge *hb = to_pci_host_bridge(dev);
+	int avail;
+
+	if (!hb->nr_ide_streams)
+		return -ENXIO;
+
+	avail = hb->nr_ide_streams -
+		bitmap_weight(hb->ide_stream_map, hb->nr_ide_streams);
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
+struct attribute_group pci_ide_attr_group = {
+	.attrs = pci_ide_attrs,
+	.is_visible = pci_ide_attr_visible,
+};
+
+/**
+ * pci_ide_init_nr_streams() - sets size of the pool of IDE Stream resources
+ * @hb: host bridge boundary for the stream pool
+ * @nr: number of streams
+ *
+ * Platform PCI init and/or expert test module use only. Enable IDE
+ * Stream establishment by setting the number of stream resources
+ * available at the host bridge. Platform init code must set this before
+ * the first pci_ide_stream_alloc() call.
+ *
+ * The "PCI_IDE" symbol namespace is required because this is typically
+ * a detail that is settled in early PCI init. I.e. this export is not
+ * for endpoint drivers.
+ */
+void pci_ide_init_nr_streams(struct pci_host_bridge *hb, u8 nr)
+{
+	hb->nr_ide_streams = nr;
+	sysfs_update_group(&hb->dev.kobj, &pci_ide_attr_group);
+}
+EXPORT_SYMBOL_NS_GPL(pci_ide_init_nr_streams, "PCI_IDE");
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 0e24262aa4ba..22e0256a10ba 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -521,8 +521,11 @@ static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 
 #ifdef CONFIG_PCI_IDE
 void pci_ide_init(struct pci_dev *dev);
+extern struct attribute_group pci_ide_attr_group;
+#define PCI_IDE_ATTR_GROUP (&pci_ide_attr_group)
 #else
 static inline void pci_ide_init(struct pci_dev *dev) { }
+#define PCI_IDE_ATTR_GROUP NULL
 #endif
 
 #ifdef CONFIG_PCI_TSM
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 6e308199001c..cc77020aa021 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -640,6 +640,16 @@ static void pci_release_host_bridge_dev(struct device *dev)
 	kfree(bridge);
 }
 
+static const struct attribute_group *pci_host_bridge_groups[] = {
+	PCI_IDE_ATTR_GROUP,
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
@@ -659,6 +669,7 @@ static void pci_init_host_bridge(struct pci_host_bridge *bridge)
 	bridge->native_dpc = 1;
 	bridge->domain_nr = PCI_DOMAIN_NR_NOT_SET;
 	bridge->native_cxl_error = 1;
+	bridge->dev.type = &pci_host_bridge_type;
 
 	device_initialize(&bridge->dev);
 }
@@ -672,7 +683,6 @@ struct pci_host_bridge *pci_alloc_host_bridge(size_t priv)
 		return NULL;
 
 	pci_init_host_bridge(bridge);
-	bridge->dev.release = pci_release_host_bridge_dev;
 
 	return bridge;
 }
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 45360ba87538..3a71f30211a5 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -670,6 +670,14 @@ void pci_set_host_bridge_release(struct pci_host_bridge *bridge,
 				 void (*release_fn)(struct pci_host_bridge *),
 				 void *release_data);
 
+#ifdef CONFIG_PCI_IDE
+void pci_ide_init_nr_streams(struct pci_host_bridge *hb, u8 nr);
+#else
+static inline void pci_ide_init_nr_streams(struct pci_host_bridge *hb, u8 nr)
+{
+}
+#endif
+
 int pcibios_root_bridge_prepare(struct pci_host_bridge *bridge);
 
 #define PCI_REGION_FLAG_MASK	0x0fU	/* These bits of resource flags tell us the PCI region flags */

---

## [10] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 09/10] PCI/TSM: Report active IDE streams*

Given that the platform TSM owns IDE Stream ID allocation, report the
active streams via the TSM class device. Establish a symlink from the
class device to the PCI endpoint device consuming the stream, named by
the Stream ID.

Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm | 10 ++++++++
 drivers/pci/ide.c                         |  6 ++++-
 drivers/pci/pci.h                         |  2 +-
 drivers/virt/coco/tsm-core.c              | 29 +++++++++++++++++++++++
 include/linux/pci-ide.h                   |  2 ++
 include/linux/tsm.h                       |  3 +++
 6 files changed, 50 insertions(+), 2 deletions(-)

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
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index eb6e146e6fb5..851633b240e3 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -11,6 +11,7 @@
 #include <linux/pci_regs.h>
 #include <linux/slab.h>
 #include <linux/sysfs.h>
+#include <linux/tsm.h>
 
 #include "pci.h"
 
@@ -272,6 +273,9 @@ void pci_ide_stream_release(struct pci_ide *ide)
 	if (ide->partner[PCI_IDE_EP].enable)
 		pci_ide_stream_disable(pdev, ide);
 
+	if (ide->tsm_dev)
+		tsm_ide_stream_unregister(ide);
+
 	if (ide->partner[PCI_IDE_RP].setup)
 		pci_ide_stream_teardown(rp, ide);
 
@@ -553,7 +557,7 @@ static umode_t pci_ide_attr_visible(struct kobject *kobj, struct attribute *a, i
 	return a->mode;
 }
 
-struct attribute_group pci_ide_attr_group = {
+const struct attribute_group pci_ide_attr_group = {
 	.attrs = pci_ide_attrs,
 	.is_visible = pci_ide_attr_visible,
 };
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 22e0256a10ba..716eb7fecb16 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -521,7 +521,7 @@ static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 
 #ifdef CONFIG_PCI_IDE
 void pci_ide_init(struct pci_dev *dev);
-extern struct attribute_group pci_ide_attr_group;
+extern const struct attribute_group pci_ide_attr_group;
 #define PCI_IDE_ATTR_GROUP (&pci_ide_attr_group)
 #else
 static inline void pci_ide_init(struct pci_dev *dev) { }
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index f0bb580563c9..d223cb6fa972 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -2,14 +2,17 @@
 /* Copyright(c) 2024 Intel Corporation. All rights reserved. */
 
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+#define dev_fmt(fmt) KBUILD_MODNAME ": " fmt
 
 #include <linux/tsm.h>
 #include <linux/idr.h>
+#include <linux/pci.h>
 #include <linux/rwsem.h>
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 
 static struct class *tsm_class;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -107,6 +110,32 @@ void tsm_unregister(struct tsm_dev *tsm_dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+/* must be invoked between tsm_register / tsm_unregister */
+int tsm_ide_stream_register(struct pci_ide *ide)
+{
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct tsm_dev *tsm_dev = tsm->ops->owner;
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
+	sysfs_remove_link(&tsm_dev->dev.kobj, ide->name);
+	ide->tsm_dev = NULL;
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 5a7ffb1d826f..a30f9460b04a 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -46,6 +46,7 @@ struct pci_ide_partner {
  * @host_bridge_stream: track platform Stream ID
  * @stream_id: unique Stream ID (within Partner Port pairing)
  * @name: name of the established Selective IDE Stream in sysfs
+ * @tsm_dev: For TSM established IDE, the TSM device context
  *
  * Negative @stream_id values indicate "uninitialized" on the
  * expectation that with TSM established IDE the TSM owns the stream_id
@@ -57,6 +58,7 @@ struct pci_ide {
 	u8 host_bridge_stream;
 	int stream_id;
 	const char *name;
+	struct tsm_dev *tsm_dev;
 };
 
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index ee9a54ae3d3c..376139585797 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -120,4 +120,7 @@ int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
+struct pci_ide;
+int tsm_ide_stream_register(struct pci_ide *ide);
+void tsm_ide_stream_unregister(struct pci_ide *ide);
 #endif /* __TSM_H */

---

## [11] Dan Williams — 2025-09-11
*Subject: [PATCH resend v6 10/10] samples/devsec: Add sample IDE establishment*

Exercise common setup and teardown flows for a sample platform TSM
driver that implements the TSM 'connect' and 'disconnect' flows.

This is both a template for platform specific implementations and a
simple integration test for the PCI core infrastructure + ABI.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Cc: "Aneesh Kumar K.V" <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 samples/devsec/bus.c      |  3 ++
 samples/devsec/link_tsm.c | 70 ++++++++++++++++++++++++++++++++++++++-
 2 files changed, 72 insertions(+), 1 deletion(-)

diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
index 07cf4ce82ceb..37a62c1cbba4 100644
--- a/samples/devsec/bus.c
+++ b/samples/devsec/bus.c
@@ -13,6 +13,7 @@
 #include "devsec.h"
 
 #define NR_DEVSEC_BUSES 1
+#define NR_PLATFORM_STREAMS 4
 #define NR_PORT_STREAMS 1
 #define NR_ADDR_ASSOC 1
 
@@ -693,6 +694,7 @@ static int __init devsec_bus_probe(struct faux_device *fdev)
 	hb->dev.parent = dev;
 	hb->sysdata = sd;
 	hb->ops = &devsec_ops;
+	pci_ide_init_nr_streams(hb, NR_PLATFORM_STREAMS);
 
 	rc = pci_scan_root_bus_bridge(hb);
 	if (rc)
@@ -730,5 +732,6 @@ static void __exit devsec_bus_exit(void)
 }
 module_exit(devsec_bus_exit);
 
+MODULE_IMPORT_NS("PCI_IDE");
 MODULE_LICENSE("GPL");
 MODULE_DESCRIPTION("Device Security Sample Infrastructure: TDISP Device Emulation");
diff --git a/samples/devsec/link_tsm.c b/samples/devsec/link_tsm.c
index 2faee8b41ede..c7a62e52f387 100644
--- a/samples/devsec/link_tsm.c
+++ b/samples/devsec/link_tsm.c
@@ -4,6 +4,7 @@
 #define dev_fmt(fmt) "devsec: " fmt
 #include <linux/device/faux.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 #include <linux/module.h>
 #include <linux/pci.h>
 #include <linux/tsm.h>
@@ -93,6 +94,23 @@ static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
 	}
 }
 
+/* protected by tsm_ops lock */
+static DECLARE_BITMAP(devsec_stream_ids, NR_TSM_STREAMS);
+static struct pci_ide *devsec_streams[NR_TSM_STREAMS];
+
+static unsigned long *alloc_devsec_stream_id(unsigned long *stream_id)
+{
+	unsigned long id;
+
+	id = find_first_zero_bit(devsec_stream_ids, NR_TSM_STREAMS);
+	if (id == NR_TSM_STREAMS)
+		return NULL;
+	set_bit(id, devsec_stream_ids);
+	*stream_id = id;
+	return stream_id;
+}
+DEFINE_FREE(free_devsec_stream, unsigned long *, if (_T) clear_bit(*_T, devsec_stream_ids))
+
 /*
  * Reference consumer for a TSM driver "connect" operation callback. The
  * low-level TSM driver understands details about the platform the PCI
@@ -117,11 +135,61 @@ static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
  */
 static int devsec_link_tsm_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	unsigned long __stream_id;
+	int rc;
+
+	unsigned long *stream_id __free(free_devsec_stream) =
+		alloc_devsec_stream_id(&__stream_id);
+	if (!stream_id)
+		return -EBUSY;
+
+	struct pci_ide *ide __free(pci_ide_stream_release) =
+		pci_ide_stream_alloc(pdev);
+	if (!ide)
+		return -ENOMEM;
+
+	ide->stream_id = *stream_id;
+	rc = pci_ide_stream_register(ide);
+	if (rc)
+		return rc;
+
+	pci_ide_stream_setup(pdev, ide);
+	pci_ide_stream_setup(rp, ide);
+
+	rc = tsm_ide_stream_register(ide);
+	if (rc)
+		return rc;
+
+	/*
+	 * Model a TSM that handled enabling the stream at
+	 * tsm_ide_stream_register() time
+	 */
+	rc = pci_ide_stream_enable(pdev, ide);
+	if (rc)
+		return rc;
+
+	devsec_streams[*no_free_ptr(stream_id)] = no_free_ptr(ide);
+
+	return 0;
 }
 
 static void devsec_link_tsm_disconnect(struct pci_dev *pdev)
 {
+	struct pci_ide *ide;
+	unsigned long i;
+
+	for_each_set_bit(i, devsec_stream_ids, NR_TSM_STREAMS)
+		if (devsec_streams[i]->pdev == pdev)
+			break;
+
+	if (i >= NR_TSM_STREAMS)
+		return;
+
+	ide = devsec_streams[i];
+	devsec_streams[i] = NULL;
+	pci_ide_stream_release(ide);
+	clear_bit(i, devsec_stream_ids);
 }
 
 static struct pci_tsm_ops devsec_link_pci_ops = {

---

## [12] Alexey Kardashevskiy — 2025-09-15
*Subject: Re: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via
 platform TSM*

On 12/9/25 09:56, Dan Williams wrote:
> The PCIe 7.0 specification, section 11, defines the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This


A suggestion: "git format-patch -O ~/orderfile ..." produces nicer-to-review order of files especially where there are new interfaces being added.

===
*.txt
configure
Kconfig*
*Makefile*
*.json
*.h
*.c
===


>   18 files changed, 943 insertions(+), 11 deletions(-)
>   create mode 100644 Documentation/driver-api/pci/tsm.rst


It is still a rather global thing. May I suggest this?

===
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index e8d9d19732f6..77b6ed52a872 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -77,7 +77,6 @@ struct pci_tsm_ops {
                 void (*unlock)(struct pci_tsm *tsm);
                 int (*accept)(struct pci_dev *pdev);
         );
-       struct tsm_dev *owner;
  };

  /**
@@ -119,6 +118,7 @@ struct pci_tsm {
         struct pci_dev *dsm_dev;
         struct pci_tdi *tdi;
         const struct pci_tsm_ops *ops;
+       struct tsm_dev *owner;
  };
@@ -221,10 +221,13 @@ struct tsm_dev;
  int pci_tsm_register(struct tsm_dev *tsm_dev);
  void pci_tsm_unregister(struct tsm_dev *tsm_dev);
  int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
+                            struct tsm_dev *tsmdev,
                              const struct pci_tsm_ops *ops);
  int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
+                           struct tsm_dev *tsmdev,
                             const struct pci_tsm_ops *ops);
  int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
+                              struct tsm_dev *tsmdev,
                                const struct pci_tsm_ops *ops);
===

+ what is needed to compile all this. Otherwise LGTM. Thanks,

---

## [13] Alexey Kardashevskiy — 2025-09-15
*Subject: Re: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via
 platform TSM*

On 12/9/25 09:56, Dan Williams wrote:

[...]

> --- a/include/linux/pci-doe.h
> +++ b/include/linux/pci-doe.h

These are "features" now:

https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=b4db6be0ceec490f639d2e47449ffe3dd6db7679

---

## [14] Jonathan Cameron — 2025-09-15
*Subject: Re: [PATCH resend v6 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Thu, 11 Sep 2025 16:56:39 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Link encryption is a new PCIe feature enumerated by "PCIe r7.0 section
> 7.9.26 IDE Extended Capability".
Oops. I missed v6 and replied to 5.   Anyhow, comments stand so
please take a look back at that. As does
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [15] Alexey Kardashevskiy — 2025-09-16
*Subject: Re: [PATCH resend v6 07/10] PCI/IDE: Add IDE establishment helpers*

On 12/9/25 09:56, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into

This still stands true, just a few comments below, since I am commenting on other patches.

> Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
> Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>

Compiles without it.

>   #include <linux/pci.h>
> +#include <linux/pci-ide.h>

Compiles without it.

> +#include <linux/sysfs.h>
>   

The big beautiful comment before the function kinda covers this one :)

> +	struct stream_index __stream[PCI_IDE_HB + 1];
> +	struct pci_host_bridge *hb;

A nit: may be refer to the version where it appeared first (r6.1).

> +
> +#ifndef __PCI_IDE_H__


#include <linux/pci.h>


> +
> +enum pci_ide_partner_select {

---

## [16] Aneesh Kumar K.V — 2025-09-16
*Subject: Re: [PATCH resend v6 00/10] PCI/TSM: Core infrastructure for PCI
 device security (TDISP)*

Dan Williams <dan.j.williams@intel.com> writes:

> [apologies for the duplicates, I flubbed my mailing list aliases]
>

The corresponding Arm CCA changes based on this version of the TSM core
infrastructure can be found at:

 https://git.gitlab.arm.com/linux-arm/linux-cca.git cca/tdisp-upstream-post-v1.2
 https://git.gitlab.arm.com/linux-arm/kvmtool-cca.git cca/tdisp-upstream-post-v1.2

These changes are still based on the ALP12 specification. I am not
reposting the series yet, as I plan to rebase the v2 patchset against
the ALP16 version of the spec. Those changes are not ready at this point.

-aneesh

---

## [17] Alexey Kardashevskiy — 2025-09-19
*Subject: Re: [PATCH resend v6 00/10] PCI/TSM: Core infrastructure for PCI
 device security (TDISP)*

On 16/9/25 22:18, Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

Here are my trees:
https://github.com/AMDESE/linux-kvm/tree/tsm
https://github.com/AMDESE/qemu/tree/tsm

I'll repost after I adopt "x86/ioremap, resource: Introduce IORES_DESC_ENCRYPTED for encrypted PCI MMIO" (hopefully soon).

Thanks,

---

## [18] Jason Gunthorpe — 2025-09-19
*Subject: Re: [PATCH resend v6 00/10] PCI/TSM: Core infrastructure for PCI
 device security (TDISP)*

On Fri, Sep 19, 2025 at 02:17:23PM +1000, Alexey Kardashevskiy wrote:
> > The corresponding Arm CCA changes based on this version of the TSM core
> > infrastructure can be found at:

Guys these all need to be broken up. We need to see arch code to
implement only the ops and features in this series so Dan can bundle
it all together for merging.

Think small steps not giant trees with a giant mess of
everything.

Please cut them down and post something mergable.

Jason

---

## [19] dan.j.williams@intel.com — 2025-09-19
*Subject: Re: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via
 platform TSM*

Alexey Kardashevskiy wrote:
> 
> 

Not the first time I have heard this recommendation, finally
implementing in my flow.

> ===
> *.txt

Went with this ordering instead:

Kconfig
*/Kconfig
*/Kconfig.*
Makefile
*/Makefile
*/Makefile.*
scripts/*
Documentation/*
*.h
*.S
*.c
tools/testing/*

...stolen from Kees:

https://github.com/kees/kernel-tools/commit/909db155

[ .. scrolls past pages of uncommented context .. ]

> It is still a rather global thing. May I suggest this?

I am not too keen on this.

Yes, it is global, but less often used compared to @ops, and I do not
want both @ops and @tsm_dev in @pci_tsm. So the options are lookup @ops
from @tsm_dev or lookup @tsm_dev from @ops. Given @ops is used more
often that is how I came up with the current arrangement.

---

## [20] dan.j.williams@intel.com — 2025-09-19
*Subject: Re: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via
 platform TSM*

Alexey Kardashevskiy wrote:
> 
> 

Ah, thanks for the heads up. I will just append this fixup for v2 of the
TEE I/O series rather than resend patch4 again... unless something
bigger comes up requiring a respin.

-- 8< --
Subject: PCI/TSM: Rename new DOE defines from "protocol" to "feature"

From: Dan Williams <dan.j.williams@intel.com>

Follow the lead of:

b4db6be0ceec ("PCI/DOE: Rename DOE protocol to feature")

...and move the new PCI/TSM definitions to "feature".

Reported-by: Alexey Kardashevskiy <aik@amd.com>
Closes: http://lore.kernel.org/9ca082b6-ff38-4401-860e-e40d4437c3a3@amd.com
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/tsm.c       |    2 +-
 include/linux/pci-doe.h |    4 ++--
 2 files changed, 3 insertions(+), 3 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 724a58e3ccf1..f0202e52ce2d 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -464,7 +464,7 @@ int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 {
 	mutex_init(&tsm->lock);
 	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
-					   PCI_DOE_PROTO_CMA);
+					   PCI_DOE_FEATURE_CMA);
 	if (!tsm->doe_mb) {
 		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
 		return -ENODEV;
diff --git a/include/linux/pci-doe.h b/include/linux/pci-doe.h
index 7d839f4a6340..bd4346a7c4e7 100644
--- a/include/linux/pci-doe.h
+++ b/include/linux/pci-doe.h
@@ -16,8 +16,8 @@
 struct pci_doe_mb;
 
 #define PCI_DOE_FEATURE_DISCOVERY 0
-#define PCI_DOE_PROTO_CMA 1
-#define PCI_DOE_PROTO_SSESSION 2
+#define PCI_DOE_FEATURE_CMA 1
+#define PCI_DOE_FEATURE_SSESSION 2
 
 struct pci_doe_mb *pci_find_doe_mailbox(struct pci_dev *pdev, u16 vendor,
 					u8 type);

---

## [21] Alexey Kardashevskiy — 2025-09-22
*Subject: Re: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via
 platform TSM*

On 20/9/25 06:15, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>>
L>>>    MAINTAINERS                             |   4 +-
>>>    drivers/pci/Kconfig                     |  15 +
>>>    drivers/pci/Makefile                    |   1 +

oh this is better, I was so sure I don't need paths. TIL.

  
> [ .. scrolls past pages of uncommented context .. ]
> 

Why exactly?

> So the options are lookup @ops
> from @tsm_dev or lookup @tsm_dev from @ops. Given @ops is used more

I am looking at:
https://github.com/AMDESE/linux-kvm/commit/9e3caf921ad6ddd6bd860ec307b986649322a618
and not really sure "more often" applies here.

And do we have to check now if tsm_dev passed in probe() is the same as the owner? I struggle to find any other _ops doing the same owner caching easily. Or merge struct pci_tsm_ops into struct tsm_dev to stop pretending that pci_tsm_ops is an interface, and then we won't even need that @owner. Dunno. Aneesh? :)

Thanks,

---

## [22] dan.j.williams@intel.com — 2025-09-25
*Subject: Re: [PATCH resend v6 07/10] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
[..]
> > diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> > index 05ab8c18b768..608ce79d830f 100644

As Bjorn pointed out in his review, the recommendation is include what
you use:

https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/process/submit-checklist.rst?id=v6.17-rc7#n17

> > diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
> > new file mode 100644

Bjorn asked that I move all the specification references forward [1], and in
this case I missed moving this one to r7.

[1]: http://lore.kernel.org/20250807212716.GA62016@bhelgaas

---

## [23] dan.j.williams@intel.com — 2025-09-25
*Subject: Re: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via
 platform TSM*

Alexey Kardashevskiy wrote:
[..]
> >> It is still a rather global thing. May I suggest this?
> > 

...because it complicates the data structure merely for code convenience
which is often the wrong tradeoff.

Here are the current options:

1/ Current:
struct pci_tsm {
        struct pci_dev *pdev;
        struct pci_dev *dsm_dev;
        const struct pci_tsm_ops *ops;
};

2/ Alternative:
struct pci_tsm {
        struct pci_dev *pdev;
        struct pci_dev *dsm_dev;
        struct tsm_dev *tsm_dev;
};

2/ Proposed:
struct pci_tsm {
        struct pci_dev *pdev;
        struct pci_dev *dsm_dev;
        struct tsm_dev *tsm_dev;
        const struct pci_tsm_ops *ops;
};

I rank 3 last because it implies that @tsm_dev and @ops may have
different lifetimes or otherwise may not be related to the same object
until you read the code.

I rank 2 after 1 because most of 'struct pci_tsm_ops' do not need the
tsm_dev parameter.

Now, I would maybe go with 2 if 'struct tsm_dev' could be defined as:

diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 376139585797..3619ffa8f8c1 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -112,7 +112,7 @@ struct pci_tsm_ops;
 struct tsm_dev {
        struct device dev;
        int id;
-       const struct pci_tsm_ops *pci_ops;
+       const struct pci_tsm_ops pci_ops;
 };
 
...i.e. a container_of() relationship, but that makes pci_ops mandatory.
It is already the case that TDX has as a few host-services in mind that
may end up sharing common infrastructure at a TSM device level, so 1
remains the preference.

> > So the options are lookup @ops
> > from @tsm_dev or lookup @tsm_dev from @ops. Given @ops is used more

@ops are not passed passed back in probe so ->probe() can not verify.
Also ->probe() sets the operations to use via pci_tsm_link_constructor()
so at that point it does not matter how ->probe() got invoked the result
is still the TSM driver returning the ops associated with @tsm_dev.

> I struggle to find any other _ops doing the same owner
> caching easily.

struct file_operations::owner looks like one example.

> Or merge struct pci_tsm_ops into struct tsm_dev to stop pretending
> that pci_tsm_ops is an interface, and then we won't even need that

Not sure what you mean by "pretending that pci_tsm_ops is an interface"?

---

## [24] Alexey Kardashevskiy — 2025-09-26
*Subject: Re: [PATCH resend v6 04/10] PCI/TSM: Authenticate devices via
 platform TSM*

On 26/9/25 09:00, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..]

Either variant of 2 (with "*pci_ops" or "pci_ops") is fine by me.


>   };
>   

Do you need to be able to resolve tsm_dev from pci_ops pointer?


> It is already the case that TDX has as a few host-services in mind that
> may end up sharing common infrastructure at a TSM device level, so 1


Any pci_tsm_ops::probe implementation can be called with any tsm_dev. So every probe() should verify that BUG_ON(tsm_dev::pci_ops::probe != itself). Although it is not possible right now. And I do not see a better way. So I do not insist really. But my head explodes at this point :)


>> I struggle to find any other _ops doing the same owner
>> caching easily.

Not exactly the same - struct module does not have back reference to file_operations. And the file_operations::owner is an ELF with some code but tsm_dev is just some memory from kmalloc(). I guess "dev" implies "module" though.

> 
>> Or merge struct pci_tsm_ops into struct tsm_dev to stop pretending

Most of these _ops are stateless (so no "owner") set of hooks, often "static" (and should be "const", and live in .ro sections, not sure if they do). And this _ops could follow the pattern. Thanks,

---
