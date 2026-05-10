---
title: 'PCI/TSM: Core infrastructure for PCI device security (TDISP)'
date: 2025-07-17
last_reply: 2025-09-25
message_count: 74
participants: ['Dan Williams', 'Aneesh Kumar K.V', 'Jonathan Cameron', 'Xu Yilun', 'Bjorn Helgaas', 'Arto Merilainen', 'Gerd Hoffmann', 'Alexey Kardashevskiy']
---

## [1] Dan Williams — 2025-07-17

Changes since v3 [1]:
- Move the TSM core out of the host/ subdirectory since it is shared
  with the guest (Aneesh)
- Support multiple simultaneous TSM providers (Jason, Alexey)
- Do not reuse the "connect" operation for both Link and Security state
  management (Aneesh, Alexey)
- Derive the pci_tsm instance type from details in the @pdev or @dsm
  properties (Aneesh)
- Delay TSM association until ->connect(), results in removing the need
  for the @state attribute
- Introduce reverse iterators for all PCI bus and function walking.
- Move all per-device context setup/teardown to
  pci_tsm_(constructor,destructor)
- Add pci_ide_stream_release() for scope-based cleanup of IDE setup
- Shorten the name of the "stream" sysfs link (Jonathan)
- misc fixups (Jonathan)
- Note creation of pci_host_bridge_type in changelog (Jonathan)
- Drop now unused PREP_PCI_IDE_SEL_ADDR1() and related macros (Jonathan)
- Open code PREP_PCI_IDE_SEL_RID_2 in its only caller (Jonathan)
- Clarify the specification Stream term from a Linux "stream" object
  (Jonathan)
- Convert samples/devsec/ to faux device (Jonathan)
- Drop Date: from ABI entries
- Add basic driver-api documentation to build kdoc
- Switch to ACQUIRE()
- Add an explicit 'disconnect' attribute
- Clarify the PCI_IDE_STREAM_MAX Kconfig help (Jonathan)
- Use unsigned variables from sel_ide_offset (Jonathan)

[1]: http://lore.kernel.org/20250516054732.2055093-1-dan.j.williams@intel.com

This set is available at tsm.git#staging (rebasing branch) or
tsm.git#devsec-20250717 (immutable tag). It passes a basic that
exercises load/unload of the samples/devsec/ modules and
connect/disconnect of the emulated device.

Status (complexity reductions):
-------------------------------

Between the support for multiple TSMs, the split of "Link" and
"Security" operations and inferring the type of 'struct pci_tsm' context
from its properties, the implementation shed complexity.

Now, ->probe() is only called in the sysfs::connect_store() path which
means that there is no need to track the PCI_TSM_INIT and
PCI_TSM_CONNECT states. Simply, when a Device Security Manager (DSM) is
connected, at that point all potential TDIs (assignable functions where
the DSM can manage its security state) are probed.

Now, initial determination of when the "tsm/" sysfs group appears
follows typical expectations. If at least one TSM device has been
registered prior to a DSM device being scanned, its "tsm/" attribute
group will appear. No more need for a pci_tsm_init() call via
pci_init_capabilities().

The pci_tsm_destroy() path is now simply arranging for
pci_tsm_disconnect() of all DSMs after all TDIs have gone through
->remove() callback. This is accomplished with new "reverse" iterators
for all PCI bus walks.

Next steps:
-----------
The campaign to graduate this out of tsm.git#staging and into mainline
starts in earnest when samples/devsec/ + 1 vendor implementation, or 2
vendor implementations can demonstrate the end-to-end flow (minus
attestation). That is the "consensus" event horizon where prior to that
it seems reasonable for impacted subsystem maintainers to opt-out of
reviewing all the fine details under debate. Suffice to say there are a
lot of fine details flying around.

To that end I expect it would help to have a tracking document in
tsm.git#staging that catalogs the open debates and the current leanings
of the staging tree. That is next in the hopper.

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
PCI device security effort [2].

[2]: http://lore.kernel.org/cover.1719771133.git.lukas@wunner.de

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
 .../ABI/testing/sysfs-devices-pci-host-bridge |  29 +
 Documentation/driver-api/pci/index.rst        |   1 +
 Documentation/driver-api/pci/tsm.rst          |  12 +
 MAINTAINERS                                   |   7 +-
 drivers/base/bus.c                            |  38 +
 drivers/pci/Kconfig                           |  28 +
 drivers/pci/Makefile                          |   2 +
 drivers/pci/bus.c                             |  37 +
 drivers/pci/ide.c                             | 578 ++++++++++++++
 drivers/pci/pci-sysfs.c                       |   4 +
 drivers/pci/pci.h                             |  17 +
 drivers/pci/probe.c                           |  25 +-
 drivers/pci/remove.c                          |   3 +
 drivers/pci/search.c                          |  63 +-
 drivers/pci/tsm.c                             | 554 ++++++++++++++
 drivers/virt/coco/Kconfig                     |   3 +
 drivers/virt/coco/Makefile                    |   2 +
 drivers/virt/coco/tsm-core.c                  | 198 +++++
 include/linux/device/bus.h                    |   3 +
 include/linux/pci-ide.h                       |  72 ++
 include/linux/pci-tsm.h                       | 158 ++++
 include/linux/pci.h                           |  36 +
 include/linux/tsm.h                           |  15 +
 include/uapi/linux/pci_regs.h                 |  89 +++
 samples/Kconfig                               |  16 +
 samples/Makefile                              |   1 +
 samples/devsec/Makefile                       |  10 +
 samples/devsec/bus.c                          | 711 ++++++++++++++++++
 samples/devsec/common.c                       |  26 +
 samples/devsec/devsec.h                       |  40 +
 samples/devsec/tsm.c                          | 241 ++++++
 33 files changed, 3078 insertions(+), 11 deletions(-)
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
 create mode 100644 samples/devsec/tsm.c


base-commit: df877487cac3509cbae2625181e7ad6748afed24

---

## [2] Dan Williams — 2025-07-17
*Subject: [PATCH v4 01/10] coco/tsm: Introduce a core device for TEE Security Managers*

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

Cc: Xiaoyao Li <xiaoyao.li@intel.com>
Cc: Isaku Yamahata <isaku.yamahata@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Yilun Xu <yilun.xu@intel.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Cc: John Allen <john.allen@amd.com>
Co-developed-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm |   9 ++
 MAINTAINERS                               |   2 +-
 drivers/virt/coco/Kconfig                 |   3 +
 drivers/virt/coco/Makefile                |   2 +
 drivers/virt/coco/tsm-core.c              | 113 ++++++++++++++++++++++
 include/linux/tsm.h                       |   5 +
 6 files changed, 133 insertions(+), 1 deletion(-)
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
index b6219e19a749..cfa3fb8772d2 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -25241,7 +25241,7 @@ M:	David Lechner <dlechner@baylibre.com>
 S:	Maintained
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
index f918bbb61737..c0c3733be165 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -2,9 +2,11 @@
 #
 # Confidential computing related collateral
 #
+
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
+obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
new file mode 100644
index 000000000000..1f53b9049e2d
--- /dev/null
+++ b/drivers/virt/coco/tsm-core.c
@@ -0,0 +1,113 @@
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
+static struct tsm_dev *alloc_tsm_dev(struct device *parent,
+				     const struct attribute_group **groups)
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
+	dev->groups = groups;
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
+struct tsm_dev *tsm_register(struct device *parent,
+			     const struct attribute_group **groups)
+{
+	struct tsm_dev *tsm_dev __free(put_tsm_dev) =
+		alloc_tsm_dev(parent, groups);
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
index 431054810dca..a90b40b1b13c 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,7 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <linux/device.h>
 
 #define TSM_REPORT_INBLOB_MAX 64
 #define TSM_REPORT_OUTBLOB_MAX SZ_32K
@@ -109,4 +110,8 @@ struct tsm_report_ops {
 
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
+struct tsm_dev;
+struct tsm_dev *tsm_register(struct device *parent,
+			     const struct attribute_group **groups);
+void tsm_unregister(struct tsm_dev *tsm_dev);
 #endif /* __TSM_H */

---

## [3] Dan Williams — 2025-07-17
*Subject: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE capabilities*

Link encryption is a new PCIe feature enumerated by "PCIe 6.2 section
7.9.26 IDE Extended Capability".

It is both a standalone port + endpoint capability, and a building block
for the security protocol defined by "PCIe 6.2 section 11 TEE Device
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

Cc: Yilun Xu <yilun.xu@intel.com>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Yilun Xu <yilun.xu@intel.com>
Signed-off-by: Yilun Xu <yilun.xu@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Kconfig           | 14 ++++++
 drivers/pci/Makefile          |  1 +
 drivers/pci/ide.c             | 93 +++++++++++++++++++++++++++++++++++
 drivers/pci/pci.h             |  6 +++
 drivers/pci/probe.c           |  1 +
 include/linux/pci.h           |  7 +++
 include/uapi/linux/pci_regs.h | 81 ++++++++++++++++++++++++++++++
 7 files changed, 203 insertions(+)
 create mode 100644 drivers/pci/ide.c

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 9c0e4aaf4e8c..4bd75d8b9b86 100644
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
index 000000000000..e15937cdb2a4
--- /dev/null
+++ b/drivers/pci/ide.c
@@ -0,0 +1,93 @@
+// SPDX-License-Identifier: GPL-2.0
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+/* PCIe 6.2 section 6.33 Integrity & Data Encryption (IDE) */
+
+#define dev_fmt(fmt) "PCI/IDE: " fmt
+#include <linux/pci.h>
+#include <linux/bitfield.h>
+#include "pci.h"
+
+static int __sel_ide_offset(u16 ide_cap, u8 nr_link_ide, u8 stream_index,
+			    u8 nr_ide_mem)
+{
+	u32 offset;
+
+	offset = ide_cap + PCI_IDE_LINK_STREAM_0 +
+		 nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE;
+
+	/*
+	 * Assume a constant number of address association resources per
+	 * stream index
+	 */
+	offset += stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);
+	return offset;
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
+		nr_link_ide = 1 + FIELD_GET(PCI_IDE_CAP_LINK_TC_NUM_MASK, val);
+	else
+		nr_link_ide = 0;
+
+	nr_ide_mem = 0;
+	nr_streams = min(1 + FIELD_GET(PCI_IDE_CAP_SEL_NUM_MASK, val),
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
+		nr_assoc = FIELD_GET(PCI_IDE_SEL_CAP_ASSOC_NUM_MASK, val);
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
index 12215ee72afb..1c223c79634f 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -515,6 +515,12 @@ static inline void pci_doe_sysfs_init(struct pci_dev *pdev) { }
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
index e94978c3be3d..e19e7a926423 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2625,6 +2625,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
+	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index f6a713da5c49..3fac811376b5 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -532,6 +532,13 @@ struct pci_dev {
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
index a3a3e942dedf..ab4ebf0f8a46 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -750,6 +750,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_PL_64GT	0x31	/* Physical Layer 64.0 GT/s */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_PL_64GT
 
@@ -1230,4 +1231,84 @@
 #define PCI_DVSEC_CXL_PORT_CTL				0x0c
 #define PCI_DVSEC_CXL_PORT_CTL_UNMASK_SBR		0x00000001
 
+/* Integrity and Data Encryption Extended Capability */
+#define PCI_IDE_CAP			0x4
+#define  PCI_IDE_CAP_LINK		0x1  /* Link IDE Stream Supported */
+#define  PCI_IDE_CAP_SELECTIVE		0x2  /* Selective IDE Streams Supported */
+#define  PCI_IDE_CAP_FLOWTHROUGH	0x4  /* Flow-Through IDE Stream Supported */
+#define  PCI_IDE_CAP_PARTIAL_HEADER_ENC 0x8  /* Partial Header Encryption Supported */
+#define  PCI_IDE_CAP_AGGREGATION	0x10 /* Aggregation Supported */
+#define  PCI_IDE_CAP_PCRC		0x20 /* PCRC Supported */
+#define  PCI_IDE_CAP_IDE_KM		0x40 /* IDE_KM Protocol Supported */
+#define  PCI_IDE_CAP_SEL_CFG		0x80 /* Selective IDE for Config Request Support */
+#define  PCI_IDE_CAP_ALG_MASK		__GENMASK(12, 8) /* Supported Algorithms */
+#define  PCI_IDE_CAP_ALG_AES_GCM_256	0    /* AES-GCM 256 key size, 96b MAC */
+#define  PCI_IDE_CAP_LINK_TC_NUM_MASK	__GENMASK(15, 13) /* Link IDE TCs */
+#define  PCI_IDE_CAP_SEL_NUM_MASK	__GENMASK(23, 16)/* Supported Selective IDE Streams */
+#define  PCI_IDE_CAP_TEE_LIMITED	0x1000000 /* TEE-Limited Stream Supported */
+#define PCI_IDE_CTL			0x8
+#define  PCI_IDE_CTL_FLOWTHROUGH_IDE	0x4  /* Flow-Through IDE Stream Enabled */
+
+#define PCI_IDE_LINK_STREAM_0		0xc  /* First Link Stream Register Block */
+#define  PCI_IDE_LINK_BLOCK_SIZE	8
+/* Link IDE Stream block, up to PCI_IDE_CAP_LINK_TC_NUM */
+#define PCI_IDE_LINK_CTL_0		   0x0               /* First Link Control Register Offset in block */
+#define  PCI_IDE_LINK_CTL_EN		   0x1               /* Link IDE Stream Enable */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_NPR_MASK __GENMASK(3, 2)   /* Tx Aggregation Mode NPR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_PR_MASK  __GENMASK(5, 4)   /* Tx Aggregation Mode PR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_CPL_MASK __GENMASK(7, 6)   /* Tx Aggregation Mode CPL */
+#define  PCI_IDE_LINK_CTL_PCRC_EN	   0x100	     /* PCRC Enable */
+#define  PCI_IDE_LINK_CTL_PART_ENC_MASK	   __GENMASK(13, 10) /* Partial Header Encryption Mode */
+#define  PCI_IDE_LINK_CTL_ALG_MASK	   __GENMASK(18, 14) /* Selection from PCI_IDE_CAP_ALG */
+#define  PCI_IDE_LINK_CTL_TC_MASK	   __GENMASK(21, 19) /* Traffic Class */
+#define  PCI_IDE_LINK_CTL_ID_MASK	   __GENMASK(31, 24) /* Stream ID */
+#define PCI_IDE_LINK_STS_0		   0x4               /* First Link Status Register Offset in block */
+#define  PCI_IDE_LINK_STS_STATE		   __GENMASK(3, 0)   /* Link IDE Stream State */
+#define  PCI_IDE_LINK_STS_RECVD_INTEGRITY_CHECK	0x80000000   /* Received Integrity Check Fail Msg */
+
+/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */
+/* Selective IDE Stream Capability Register */
+#define  PCI_IDE_SEL_CAP		 0
+#define  PCI_IDE_SEL_CAP_ASSOC_NUM_MASK	 __GENMASK(3, 0)
+/* Selective IDE Stream Control Register */
+#define  PCI_IDE_SEL_CTL		 4
+#define   PCI_IDE_SEL_CTL_EN		 0x1	/* Selective IDE Stream Enable */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_NPR_MASK __GENMASK(3, 2) /* Tx Aggregation Mode NPR */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_PR_MASK  __GENMASK(5, 4) /* Tx Aggregation Mode PR */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_CPL_MASK __GENMASK(7, 6) /* Tx Aggregation Mode CPL */
+#define   PCI_IDE_SEL_CTL_PCRC_EN	 0x100	/* PCRC Enable */
+#define   PCI_IDE_SEL_CTL_CFG_EN	 0x200	/* Selective IDE for Configuration Requests */
+#define   PCI_IDE_SEL_CTL_PART_ENC_MASK	 __GENMASK(13, 10) /* Partial Header Encryption Mode */
+#define   PCI_IDE_SEL_CTL_ALG_MASK	 __GENMASK(18, 14) /* Selection from PCI_IDE_CAP_ALG */
+#define   PCI_IDE_SEL_CTL_TC_MASK	 __GENMASK(21, 19) /* Traffic Class */
+#define   PCI_IDE_SEL_CTL_DEFAULT	 0x400000 /* Default Stream */
+#define   PCI_IDE_SEL_CTL_TEE_LIMITED	 0x800000 /* TEE-Limited Stream */
+#define   PCI_IDE_SEL_CTL_ID_MASK	 __GENMASK(31, 24) /* Stream ID */
+#define   PCI_IDE_SEL_CTL_ID_MAX	 255
+/* Selective IDE Stream Status Register */
+#define  PCI_IDE_SEL_STS		 8
+#define   PCI_IDE_SEL_STS_STATE_MASK	 __GENMASK(3, 0) /* Selective IDE Stream State */
+#define   PCI_IDE_SEL_STS_STATE_INSECURE 0
+#define   PCI_IDE_SEL_STS_STATE_SECURE   2
+#define   PCI_IDE_SEL_STS_RECVD_INTEGRITY_CHECK	0x80000000 /* Received Integrity Check Fail Msg */
+/* IDE RID Association Register 1 */
+#define  PCI_IDE_SEL_RID_1		 0xc
+#define   PCI_IDE_SEL_RID_1_LIMIT_MASK	 __GENMASK(23, 8)
+/* IDE RID Association Register 2 */
+#define  PCI_IDE_SEL_RID_2		 0x10
+#define   PCI_IDE_SEL_RID_2_VALID	 0x1
+#define   PCI_IDE_SEL_RID_2_BASE_MASK	 __GENMASK(23, 8)
+#define   PCI_IDE_SEL_RID_2_SEG_MASK	 __GENMASK(31, 24)
+/* Selective IDE Address Association Register Block, up to PCI_IDE_SEL_CAP_ASSOC_NUM */
+#define PCI_IDE_SEL_ADDR_BLOCK_SIZE	    12
+#define  PCI_IDE_SEL_ADDR_1(x)		    (20 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+#define   PCI_IDE_SEL_ADDR_1_VALID	    0x1
+#define   PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK  __GENMASK(19, 8)
+#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK __GENMASK(31, 20)
+/* IDE Address Association Register 2 is "Memory Limit Upper" */
+#define  PCI_IDE_SEL_ADDR_2(x)		    (24 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+/* IDE Address Association Register 3 is "Memory Base Upper" */
+#define  PCI_IDE_SEL_ADDR_3(x)		    (28 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+#define PCI_IDE_SEL_BLOCK_SIZE(nr_assoc)  (20 + PCI_IDE_SEL_ADDR_BLOCK_SIZE * (nr_assoc))
+
 #endif /* LINUX_PCI_REGS_H */

---

## [4] Dan Williams — 2025-07-17
*Subject: [PATCH v4 03/10] PCI: Introduce pci_walk_bus_reverse(), for_each_pci_dev_reverse()*

PCI/TSM, the PCI core functionality for the PCIe TEE Device Interface
Security Protocol (TDISP), has a need to walk all subordinate functions of
a Device Security Manager (DSM) to setup a device security context. A DSM
is physical function 0 of multi-function or SRIOV device endpoint, or it is
an upstream switch port.

In error scenarios or when a TEE Security Manager (TSM) device is removed
it needs to unwind all established DSM contexts.

Introduce reverse versions of PCI device iteration helpers to mirror the
setup path and ensure that dependent children are handled before parents.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/base/bus.c         | 38 +++++++++++++++++++++++
 drivers/pci/bus.c          | 37 ++++++++++++++++++++++
 drivers/pci/search.c       | 63 +++++++++++++++++++++++++++++++++-----
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
index 69048869ef1c..d894c87ce1fd 100644
--- a/drivers/pci/bus.c
+++ b/drivers/pci/bus.c
@@ -428,6 +428,27 @@ static int __pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void
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
@@ -449,6 +470,22 @@ void pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void *), void
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
index 53840634fbfc..7a4623f65256 100644
--- a/drivers/pci/search.c
+++ b/drivers/pci/search.c
@@ -282,6 +282,46 @@ static struct pci_dev *pci_get_dev_by_id(const struct pci_device_id *id,
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
+
 /**
  * pci_get_subsys - begin or continue searching for a PCI device by vendor/subvendor/device/subdevice id
  * @vendor: PCI vendor id to match, or %PCI_ANY_ID to match all vendor ids
@@ -302,14 +342,8 @@ struct pci_dev *pci_get_subsys(unsigned int vendor, unsigned int device,
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
 
@@ -334,6 +368,19 @@ struct pci_dev *pci_get_device(unsigned int vendor, unsigned int device,
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
index 3fac811376b5..b8bca0711967 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -575,6 +575,8 @@ struct pci_dev *pci_alloc_dev(struct pci_bus *bus);
 
 #define	to_pci_dev(n) container_of(n, struct pci_dev, dev)
 #define for_each_pci_dev(d) while ((d = pci_get_device(PCI_ANY_ID, PCI_ANY_ID, d)) != NULL)
+#define for_each_pci_dev_reverse(d) \
+	while ((d = pci_get_device_reverse(PCI_ANY_ID, PCI_ANY_ID, d)) != NULL)
 
 static inline int pci_channel_offline(struct pci_dev *pdev)
 {
@@ -1220,6 +1222,8 @@ u64 pci_get_dsn(struct pci_dev *dev);
 
 struct pci_dev *pci_get_device(unsigned int vendor, unsigned int device,
 			       struct pci_dev *from);
+struct pci_dev *pci_get_device_reverse(unsigned int vendor, unsigned int device,
+				       struct pci_dev *from);
 struct pci_dev *pci_get_subsys(unsigned int vendor, unsigned int device,
 			       unsigned int ss_vendor, unsigned int ss_device,
 			       struct pci_dev *from);
@@ -1639,6 +1643,8 @@ int pci_scan_bridge(struct pci_bus *bus, struct pci_dev *dev, int max,
 
 void pci_walk_bus(struct pci_bus *top, int (*cb)(struct pci_dev *, void *),
 		  void *userdata);
+void pci_walk_bus_reverse(struct pci_bus *top,
+			  int (*cb)(struct pci_dev *, void *), void *userdata);
 int pci_cfg_space_size(struct pci_dev *dev);
 unsigned char pci_bus_max_busnr(struct pci_bus *bus);
 resource_size_t pcibios_window_alignment(struct pci_bus *bus,
@@ -2031,6 +2037,11 @@ static inline struct pci_dev *pci_get_device(unsigned int vendor,
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

## [5] Dan Williams — 2025-07-17
*Subject: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

The PCIe 6.1 specification, section 11, introduces the Trusted Execution
Environment (TEE) Device Interface Security Protocol (TDISP).  This
protocol definition builds upon Component Measurement and Authentication
(CMA), and link Integrity and Data Encryption (IDE). It adds support for
assigning devices (PCI physical or virtual function) to a confidential
VM such that the assigned device is enabled to access guest private
memory protected by technologies like Intel TDX, AMD SEV-SNP, RISCV
COVE, or ARM CCA.

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
2 mutually exclusive operation sets, "Link" and "Security" (struct
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
 Documentation/ABI/testing/sysfs-bus-pci |  51 +++
 Documentation/driver-api/pci/index.rst  |   1 +
 Documentation/driver-api/pci/tsm.rst    |  12 +
 MAINTAINERS                             |   4 +-
 drivers/pci/Kconfig                     |  14 +
 drivers/pci/Makefile                    |   1 +
 drivers/pci/pci-sysfs.c                 |   4 +
 drivers/pci/pci.h                       |   8 +
 drivers/pci/remove.c                    |   3 +
 drivers/pci/tsm.c                       | 554 ++++++++++++++++++++++++
 drivers/virt/coco/tsm-core.c            |  61 ++-
 include/linux/pci-tsm.h                 | 158 +++++++
 include/linux/pci.h                     |   3 +
 include/linux/tsm.h                     |   8 +-
 include/uapi/linux/pci_regs.h           |   1 +
 15 files changed, 879 insertions(+), 4 deletions(-)
 create mode 100644 Documentation/driver-api/pci/tsm.rst
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 include/linux/pci-tsm.h

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 69f952fffec7..99315fbfbe10 100644
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
+		devices without a tsm/ attribute directory will never have one,
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
+		(WO) Write '1' or 'true' to this attribute to disconnect it from
+		a previous TSM connection.
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
index cfa3fb8772d2..8cb7ee9270d2 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -25247,8 +25247,10 @@ L:	linux-coco@lists.linux.dev
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
index 4bd75d8b9b86..700addee8f62 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -136,6 +136,20 @@ config PCI_IDE_STREAM_MAX
 	  platform capability for the foreseeable future is 4 to 8 streams. Bump
 	  this value up if you have an expert testing need.
 
+config PCI_TSM
+	bool "PCI TSM: Device security protocol support"
+	select PCI_IDE
+	select PCI_DOE
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
diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
index 268c69daa4d5..23cbf6c8796a 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1815,6 +1815,10 @@ const struct attribute_group *pci_dev_attr_groups[] = {
 #endif
 #ifdef CONFIG_PCI_DOE
 	&pci_doe_sysfs_group,
+#endif
+#ifdef CONFIG_PCI_TSM
+	&pci_tsm_auth_attr_group,
+	&pci_tsm_pf0_attr_group,
 #endif
 	NULL,
 };
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 1c223c79634f..3b282c24dde8 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -521,6 +521,14 @@ void pci_ide_init(struct pci_dev *dev);
 static inline void pci_ide_init(struct pci_dev *dev) { }
 #endif
 
+#ifdef CONFIG_PCI_TSM
+void pci_tsm_destroy(struct pci_dev *pdev);
+extern const struct attribute_group pci_tsm_pf0_attr_group;
+extern const struct attribute_group pci_tsm_auth_attr_group;
+#else
+static inline void pci_tsm_destroy(struct pci_dev *pdev) { }
+#endif
+
 /**
  * pci_dev_set_io_state - Set the new error state if possible.
  *
diff --git a/drivers/pci/remove.c b/drivers/pci/remove.c
index 445afdfa6498..21851c13becd 100644
--- a/drivers/pci/remove.c
+++ b/drivers/pci/remove.c
@@ -55,6 +55,9 @@ static void pci_destroy_dev(struct pci_dev *dev)
 	pci_doe_sysfs_teardown(dev);
 	pci_npem_remove(dev);
 
+	/* before device_del() to keep config cycle access */
+	pci_tsm_destroy(dev);
+
 	device_del(&dev->dev);
 
 	down_write(&pci_bus_sem);
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
new file mode 100644
index 000000000000..0784cc436dd3
--- /dev/null
+++ b/drivers/pci/tsm.c
@@ -0,0 +1,554 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * TEE Security Manager for the TEE Device Interface Security Protocol
+ * (TDISP, PCIe r6.1 sec 11)
+ *
+ * Copyright(c) 2024 Intel Corporation. All rights reserved.
+ */
+
+#define dev_fmt(fmt) "TSM: " fmt
+
+#include <linux/bitfield.h>
+#include <linux/xarray.h>
+#include <linux/sysfs.h>
+
+#include <linux/tsm.h>
+#include <linux/pci.h>
+#include <linux/pci-doe.h>
+#include <linux/pci-tsm.h>
+#include "pci.h"
+
+/*
+ * Provide a read/write lock against the init / exit of pdev tsm
+ * capabilities and arrival/departure of a tsm instance
+ */
+static DECLARE_RWSEM(pci_tsm_rwsem);
+static int pci_tsm_count;
+
+static inline bool is_dsm(struct pci_dev *pdev)
+{
+	return pdev->tsm && pdev->tsm->dsm == pdev;
+}
+
+static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *pci_tsm)
+{
+	struct pci_dev *pdev = pci_tsm->pdev;
+
+	if (!is_pci_tsm_pf0(pdev) || !is_dsm(pdev)) {
+		dev_WARN_ONCE(&pdev->dev, 1, "invalid context object\n");
+		return NULL;
+	}
+
+	return container_of(pci_tsm, struct pci_tsm_pf0, tsm);
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
+static int call_cb_put(struct pci_dev *pdev, void *data,
+		       int (*cb)(struct pci_dev *pdev, void *data))
+{
+	int rc;
+
+	if (!pdev)
+		return 0;
+	rc = cb(pdev, data);
+	pci_dev_put(pdev);
+	return rc;
+}
+
+static void pci_tsm_walk_fns(struct pci_dev *pdev,
+			     int (*cb)(struct pci_dev *pdev, void *data),
+			     void *data)
+{
+	struct pci_dev *fn;
+	int i;
+
+	/* walk virtual functions */
+        for (i = 0; i < pci_num_vf(pdev); i++) {
+		fn = pci_get_domain_bus_and_slot(pci_domain_nr(pdev->bus),
+						 pci_iov_virtfn_bus(pdev, i),
+						 pci_iov_virtfn_devfn(pdev, i));
+		if (call_cb_put(fn, data, cb))
+			return;
+        }
+
+	/* walk subordinate physical functions */
+	for (i = 1; i < 8; i++) {
+		fn = pci_get_slot(pdev->bus,
+				  PCI_DEVFN(PCI_SLOT(pdev->devfn), i));
+		if (call_cb_put(fn, data, cb))
+			return;
+	}
+
+	/* walk downstream devices */
+        if (pci_pcie_type(pdev) != PCI_EXP_TYPE_UPSTREAM)
+                return;
+
+        if (!is_dsm(pdev))
+                return;
+
+        pci_walk_bus(pdev->subordinate, cb, data);
+}
+
+static void pci_tsm_walk_fns_reverse(struct pci_dev *pdev,
+				     int (*cb)(struct pci_dev *pdev,
+					       void *data),
+				     void *data)
+{
+	struct pci_dev *fn;
+	int i;
+
+	/* reverse walk virtual functions */
+	for (i = pci_num_vf(pdev) - 1; i >= 0; i--) {
+		fn = pci_get_domain_bus_and_slot(pci_domain_nr(pdev->bus),
+						 pci_iov_virtfn_bus(pdev, i),
+						 pci_iov_virtfn_devfn(pdev, i));
+		if (call_cb_put(fn, data, cb))
+			return;
+	}
+
+	/* reverse walk subordinate physical functions */
+	for (i = 7; i >= 1; i--) {
+		fn = pci_get_slot(pdev->bus,
+				  PCI_DEVFN(PCI_SLOT(pdev->devfn), i));
+		if (call_cb_put(fn, data, cb))
+			return;
+	}
+
+	/* reverse walk downstream devices */
+	if (pci_pcie_type(pdev) != PCI_EXP_TYPE_UPSTREAM)
+		return;
+
+	if (!is_dsm(pdev))
+		return;
+
+	pci_walk_bus_reverse(pdev->subordinate, cb, data);
+}
+
+static int probe_fn(struct pci_dev *pdev, void *dsm)
+{
+	struct pci_dev *dsm_dev = dsm;
+	const struct pci_tsm_ops *ops = dsm_dev->tsm->ops;
+
+	pdev->tsm = ops->probe(pdev);
+	pci_dbg(pdev, "setup tsm context: dsm: %s status: %s\n",
+		pci_name(dsm_dev), pdev->tsm ? "success" : "failed");
+	return 0;
+}
+
+static void pci_tsm_probe_fns(struct pci_dev *dsm)
+{
+	pci_tsm_walk_fns(dsm, probe_fn, dsm);
+}
+
+static int pci_tsm_connect(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
+{
+	int rc;
+	struct pci_tsm_pf0 *tsm_pf0;
+	const struct pci_tsm_ops *ops = tsm_pci_ops(tsm_dev);
+	struct pci_tsm *pci_tsm __free(tsm_remove) = ops->probe(pdev);
+
+	if (!pci_tsm)
+		return -ENXIO;
+
+	pdev->tsm = pci_tsm;
+	tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+
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
+	 */
+	pci_tsm_probe_fns(pdev);
+	return 0;
+}
+
+static ssize_t connect_show(struct device *dev, struct device_attribute *attr,
+			    char *buf)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return sysfs_emit(buf, "\n");
+
+	return sysfs_emit(buf, "%s\n", tsm_name(pdev->tsm->ops->owner));
+}
+
+static ssize_t connect_store(struct device *dev, struct device_attribute *attr,
+			     const char *buf, size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	const struct pci_tsm_ops *ops;
+	struct tsm_dev *tsm_dev;
+	int rc, id;
+
+	rc = sscanf(buf, "tsm%d\n", &id);
+	if (rc != 1)
+		return -EINVAL;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (pdev->tsm)
+		return -EBUSY;
+
+	tsm_dev = find_tsm_dev(id);
+	if (!tsm_dev)
+		return -ENXIO;
+
+	ops = tsm_pci_ops(tsm_dev);
+	if (!ops || !ops->connect || !ops->probe)
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
+static void pci_tsm_remove_fns(struct pci_dev *dsm)
+{
+	pci_tsm_walk_fns_reverse(dsm, remove_fn, NULL);
+}
+
+static void __pci_tsm_disconnect(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+	const struct pci_tsm_ops *ops = pdev->tsm->ops;
+
+	/* disconnect is not interruptible */
+	guard(mutex)(&tsm_pf0->lock);
+	pci_tsm_remove_fns(pdev);
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
+	bool disconnect;
+	int rc;
+
+	rc = kstrtobool(buf, &disconnect);
+	if (rc)
+		return rc;
+	if (!disconnect)
+		return -EINVAL;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return -ENXIO;
+
+	pci_tsm_disconnect(pdev);
+	return len;
+}
+static DEVICE_ATTR_WO(disconnect);
+
+static bool pci_tsm_pf0_group_visible(struct kobject *kobj)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct pci_dev *pdev = to_pci_dev(dev);
+
+	return pci_tsm_count && is_pci_tsm_pf0(pdev);
+}
+DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm_pf0);
+
+static struct attribute *pci_tsm_pf0_attrs[] = {
+	&dev_attr_connect.attr,
+	&dev_attr_disconnect.attr,
+	NULL
+};
+
+const struct attribute_group pci_tsm_pf0_attr_group = {
+	.name = "tsm",
+	.attrs = pci_tsm_pf0_attrs,
+	.is_visible = SYSFS_GROUP_VISIBLE(pci_tsm_pf0),
+};
+
+static ssize_t authenticated_show(struct device *dev,
+				  struct device_attribute *attr, char *buf)
+{
+	/*
+	 * When device authentication is TSM owned, 'authenticated' is
+	 * identical to the connect state.
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
+	.is_visible = SYSFS_GROUP_VISIBLE(pci_tsm_pf0),
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
+ * Find the PCI Device instance that serves as the Device Security
+ * Manger (DSM) for @pdev. Note that no additional reference is held for
+ * the resulting device because @pdev always has a longer registered
+ * lifetime than its DSM by virtue of being a child of or identical to
+ * its DSM.
+ */
+static struct pci_dev *find_dsm_dev(struct pci_dev *pdev)
+{
+	struct pci_dev *uport_pf0;
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
+	 * For cases where a switch may be hosting TDISP services on
+	 * behalf of downstream devices, check the first usptream port
+	 * relative to this endpoint.
+         */
+	if (!pdev->dev.parent || !pdev->dev.parent->parent)
+		return NULL;
+
+	uport_pf0 = to_pci_dev(pdev->dev.parent->parent);
+	if (is_dsm(uport_pf0))
+		return uport_pf0;
+	return NULL;
+}
+
+/**
+ * pci_tsm_constructor() - base 'struct pci_tsm' initialization
+ * @pdev: The PCI device
+ * @tsm: context to initialize
+ * @ops: PCI operations provided by the TSM
+ */
+int pci_tsm_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
+			const struct pci_tsm_ops *ops)
+{
+	tsm->pdev = pdev;
+	tsm->ops = ops;
+	tsm->dsm = find_dsm_dev(pdev);
+	if (!tsm->dsm) {
+		pci_warn(pdev, "failed to find Device Security Manager\n");
+		return -ENXIO;
+	}
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_constructor);
+
+/**
+ * pci_tsm_pf0_constructor() - common 'struct pci_tsm_pf0' initialization
+ * @pdev: Physical Function 0 PCI device (as indicated by is_pci_tsm_pf0())
+ * @tsm: context to initialize
+ */
+int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
+			    const struct pci_tsm_ops *ops)
+{
+	struct tsm_dev *tsm_dev = ops->owner;
+
+	mutex_init(&tsm->lock);
+	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					   PCI_DOE_PROTO_CMA);
+	if (!tsm->doe_mb) {
+		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
+		return -ENODEV;
+	}
+
+	if (tsm_pci_group(tsm_dev))
+		sysfs_merge_group(&pdev->dev.kobj, tsm_pci_group(tsm_dev));
+
+	return pci_tsm_constructor(pdev, &tsm->tsm, ops);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_pf0_constructor);
+
+void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *pf0_tsm)
+{
+	struct pci_tsm *tsm = &pf0_tsm->tsm;
+	struct pci_dev *pdev = tsm->pdev;
+	struct tsm_dev *tsm_dev = tsm->ops->owner;
+
+	if (tsm_pci_group(tsm_dev))
+		sysfs_unmerge_group(&pdev->dev.kobj, tsm_pci_group(tsm_dev));
+	mutex_destroy(&pf0_tsm->lock);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_pf0_destructor);
+
+static void pf0_sysfs_enable(struct pci_dev *pdev)
+{
+	pci_dbg(pdev, "Device Security Manager detected (%s%s )\n",
+		pdev->ide_cap ? " ide" : "",
+		pdev->devcap & PCI_EXP_DEVCAP_TEE ? " tee" : "");
+
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_pf0_attr_group);
+}
+
+int pci_tsm_register(struct tsm_dev *tsm_dev)
+{
+	const struct pci_tsm_ops *ops;
+	struct pci_dev *pdev = NULL;
+
+	if (!tsm_dev)
+		return -EINVAL;
+
+	/*
+	 * The TSM device must have pci_ops, and only implement one of link_ops
+	 * or sec_ops.
+	 */
+	ops = tsm_pci_ops(tsm_dev);
+	if (!ops)
+		return -EINVAL;
+
+	if (!ops->probe && !ops->sec_probe)
+		return -EINVAL;
+
+	if (ops->probe && ops->sec_probe)
+		return -EINVAL;
+
+	guard(rwsem_write)(&pci_tsm_rwsem);
+
+	pci_tsm_count++;
+
+	/* PCI/TSM sysfs already enabled? */
+	if (pci_tsm_count > 1)
+		return 0;
+
+	for_each_pci_dev(pdev)
+		if (is_pci_tsm_pf0(pdev))
+			pf0_sysfs_enable(pdev);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_register);
+
+/**
+ * __pci_tsm_destroy() - destroy the TSM context for @pdev
+ * @pdev: device to cleanup
+ * @tsm_dev: TSM context if a TSM device is being removed, NULL if
+ * 	     @pdev is being removed.
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
+	if (tsm_dev && is_pci_tsm_pf0(pdev) && !pci_tsm_count) {
+		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_pf0_attr_group);
+	}
+
+	if (!tsm)
+		return;
+
+	if (!tsm_dev)
+		tsm_dev = tsm->ops->owner;
+	else if (tsm_dev != tsm->ops->owner)
+		return;
+
+	if (is_pci_tsm_pf0(pdev))
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
+void pci_tsm_unregister(struct tsm_dev *tsm_dev)
+{
+	struct pci_dev *pdev = NULL;
+
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	pci_tsm_count--;
+	for_each_pci_dev_reverse(pdev)
+		__pci_tsm_destroy(pdev, tsm_dev);
+}
+
+int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
+			 const void *req, size_t req_sz, void *resp,
+			 size_t resp_sz)
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
index 1f53b9049e2d..093824dc68dd 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -9,6 +9,7 @@
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
+#include <linux/pci-tsm.h>
 
 static struct class *tsm_class;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -17,8 +18,39 @@ static DEFINE_IDR(tsm_idr);
 struct tsm_dev {
 	struct device dev;
 	int id;
+	const struct pci_tsm_ops *pci_ops;
+	const struct attribute_group *group;
 };
 
+const char *tsm_name(const struct tsm_dev *tsm_dev)
+{
+	return dev_name(&tsm_dev->dev);
+}
+
+/*
+ * Caller responsible for ensuring it does not race tsm_dev
+ * unregistration.
+ */
+struct tsm_dev *find_tsm_dev(int id)
+{
+	guard(rcu)();
+	return idr_find(&tsm_idr, id);
+}
+
+const struct pci_tsm_ops *tsm_pci_ops(const struct tsm_dev *tsm_dev)
+{
+	if (!tsm_dev)
+		return NULL;
+	return tsm_dev->pci_ops;
+}
+
+const struct attribute_group *tsm_pci_group(const struct tsm_dev *tsm_dev)
+{
+	if (!tsm_dev)
+		return NULL;
+	return tsm_dev->group;
+}
+
 static struct tsm_dev *alloc_tsm_dev(struct device *parent,
 				     const struct attribute_group **groups)
 {
@@ -44,6 +76,29 @@ static struct tsm_dev *alloc_tsm_dev(struct device *parent,
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
@@ -54,7 +109,8 @@ DEFINE_FREE(put_tsm_dev, struct tsm_dev *,
 	    if (!IS_ERR_OR_NULL(_T)) put_tsm_dev(_T))
 
 struct tsm_dev *tsm_register(struct device *parent,
-			     const struct attribute_group **groups)
+			     const struct attribute_group **groups,
+			     struct pci_tsm_ops *pci_ops)
 {
 	struct tsm_dev *tsm_dev __free(put_tsm_dev) =
 		alloc_tsm_dev(parent, groups);
@@ -73,12 +129,13 @@ struct tsm_dev *tsm_register(struct device *parent,
 	if (rc)
 		return ERR_PTR(rc);
 
-	return no_free_ptr(tsm_dev);
+	return tsm_register_pci_or_reset(no_free_ptr(tsm_dev), pci_ops);
 }
 EXPORT_SYMBOL_GPL(tsm_register);
 
 void tsm_unregister(struct tsm_dev *tsm_dev)
 {
+	pci_tsm_unregister(tsm_dev);
 	device_unregister(&tsm_dev->dev);
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
new file mode 100644
index 000000000000..f370c022fac4
--- /dev/null
+++ b/include/linux/pci-tsm.h
@@ -0,0 +1,158 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef __PCI_TSM_H
+#define __PCI_TSM_H
+#include <linux/mutex.h>
+#include <linux/pci.h>
+
+struct pci_tsm;
+
+/*
+ * struct pci_tsm_ops - manage confidential links and security state
+ * @link_ops: Coordinate PCIe SPDM and IDE establishment via a platform TSM.
+ * 	      Provide a secure session transport for TDISP state management
+ * 	      (typically bare metal physical function operations).
+ * @sec_ops: Lock, unlock, and interrogate the security state of the
+ *	     function via the platform TSM (typically virtual function
+ *	     operations).
+ * @owner: Back reference to the TSM device that owns this instance.
+ *
+ * This operations are mutually exclusive either a tsm_dev instance
+ * manages phyiscal link properties or it manages function security
+ * states like TDISP lock/unlock.
+ */
+struct pci_tsm_ops {
+	/*
+	 * struct pci_tsm_link_ops - Manage physical link and the TSM/DSM session
+	 * @probe: probe device for tsm link operation readiness, setup
+	 *	   DSM context
+	 * @remove: destroy DSM context
+	 * @connect: establish / validate a secure connection (e.g. IDE)
+	 *	     with the device
+	 * @disconnect: teardown the secure link
+	 *
+	 * @probe and @remove run in pci_tsm_rwsem held for write context. All
+	 * other ops run under the @pdev->tsm->lock mutex and pci_tsm_rwsem held
+	 * for read.
+	 */
+	struct_group_tagged(pci_tsm_link_ops, link_ops,
+		struct pci_tsm *(*probe)(struct pci_dev *pdev);
+		void (*remove)(struct pci_tsm *tsm);
+		int (*connect)(struct pci_dev *pdev);
+		void (*disconnect)(struct pci_dev *pdev);
+	);
+
+	/*
+	 * struct pci_tsm_security_ops - Manage the security state of the function
+	 * @sec_probe: probe device for tsm security operation
+	 *	       readiness, setup security context
+	 * @sec_remove: destroy security context
+	 *
+	 * @sec_probe and @sec_remove run in pci_tsm_rwsem held for
+	 * write context. All other ops run under the @pdev->tsm->lock
+	 * mutex and pci_tsm_rwsem held for read.
+	 */
+	struct_group_tagged(pci_tsm_security_ops, ops,
+		struct pci_tsm *(*sec_probe)(struct pci_dev *pdev);
+		void (*sec_remove)(struct pci_tsm *tsm);
+	);
+	struct tsm_dev *owner;
+};
+
+/**
+ * struct pci_tsm - Core TSM context for a given PCIe endpoint
+ * @pdev: Back ref to device function, distinguishes type of pci_tsm context
+ * @dsm: PCI Device Security Manager for link operations on @pdev.
+ * @ops: Link Confidentiality or Device Function Security operations
+ *
+ * This structure is wrapped by low level TSM driver data and returned
+ * by probe()/sec_probe(), it is freed by the corresponding
+ * remove()/sec_remove().
+ *
+ * For link operations it serves to cache the association between a
+ * Device Security Manager (DSM) and the functions that manager can
+ * assign to a TVM.  That can be "self", for assigning function0 of a
+ * TEE I/O device, a sub-function (SR-IOV virtual function, or
+ * non-function0 multifunction-device), or a downstream endpoint (PCIe
+ * upstream switch-port as DSM).
+ */
+struct pci_tsm {
+	struct pci_dev *pdev;
+	struct pci_dev *dsm;
+	const struct pci_tsm_ops *ops;
+};
+
+/**
+ * struct pci_tsm_pf0 - Physical Function 0 TDISP link context
+ * @tsm: generic core "tsm" context
+ * @lock: protect @state vs pci_tsm_ops invocation
+ * @doe_mb: PCIe Data Object Exchange mailbox
+ */
+struct pci_tsm_pf0 {
+	struct pci_tsm tsm;
+	struct mutex lock;
+	struct pci_doe_mb *doe_mb;
+};
+
+/* physical function0 and capable of 'connect' */
+static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
+{
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
+	 * DSM to accept TDISP requests for switch Downstream Endpoints.
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
+enum pci_doe_proto {
+	PCI_DOE_PROTO_CMA = 1,
+	PCI_DOE_PROTO_SSESSION = 2,
+};
+
+#ifdef CONFIG_PCI_TSM
+struct tsm_dev;
+int pci_tsm_register(struct tsm_dev *tsm_dev);
+void pci_tsm_unregister(struct tsm_dev *tsm_dev);
+int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
+			 const void *req, size_t req_sz, void *resp,
+			 size_t resp_sz);
+int pci_tsm_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
+			const struct pci_tsm_ops *ops);
+int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
+			    const struct pci_tsm_ops *ops);
+void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
+#else
+static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
+{
+	return 0;
+}
+static inline void pci_tsm_unregister(struct tsm_dev *tsm_dev)
+{
+}
+static inline int pci_tsm_doe_transfer(struct pci_dev *pdev,
+				       enum pci_doe_proto type, const void *req,
+				       size_t req_sz, void *resp,
+				       size_t resp_sz)
+{
+	return -ENOENT;
+}
+#endif
+#endif /*__PCI_TSM_H */
diff --git a/include/linux/pci.h b/include/linux/pci.h
index b8bca0711967..0e5703fad0f6 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -539,6 +539,9 @@ struct pci_dev {
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
index a90b40b1b13c..ce95589a5d5b 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -111,7 +111,13 @@ struct tsm_report_ops {
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_dev;
+struct pci_tsm_ops;
 struct tsm_dev *tsm_register(struct device *parent,
-			     const struct attribute_group **groups);
+			     const struct attribute_group **groups,
+			     struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
+const char *tsm_name(const struct tsm_dev *tsm_dev);
+struct tsm_dev *find_tsm_dev(int id);
+const struct pci_tsm_ops *tsm_pci_ops(const struct tsm_dev *tsm_dev);
+const struct attribute_group *tsm_pci_group(const struct tsm_dev *tsm_dev);
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index ab4ebf0f8a46..1b991a88c19c 100644
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

## [6] Dan Williams — 2025-07-17
*Subject: [PATCH v4 05/10] samples/devsec: Introduce a PCI device-security bus + endpoint sample*

Establish just enough emulated PCI infrastructure to register a sample
TSM (platform security manager) driver and have it discover an IDE + TEE
(link encryption + device-interface security protocol (TDISP)) capable
device.

Use the existing a CONFIG_PCI_BRIDGE_EMUL to emulate an IDE capable root
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
 # modprobe devsec_tsm
    devsec_tsm_pci_probe: pci 10000:01:00.0: devsec: tsm enabled
    __pci_tsm_init: pci 10000:01:00.0: TSM: Device security capabilities detected ( ide tee ), TSM attach

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 MAINTAINERS             |   1 +
 samples/Kconfig         |  16 +
 samples/Makefile        |   1 +
 samples/devsec/Makefile |  10 +
 samples/devsec/bus.c    | 708 ++++++++++++++++++++++++++++++++++++++++
 samples/devsec/common.c |  26 ++
 samples/devsec/devsec.h |  40 +++
 samples/devsec/tsm.c    | 173 ++++++++++
 8 files changed, 975 insertions(+)
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/tsm.c

diff --git a/MAINTAINERS b/MAINTAINERS
index 8cb7ee9270d2..97494511da0c 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -25251,6 +25251,7 @@ F:	Documentation/driver-api/pci/tsm.rst
 F:	drivers/pci/tsm.c
 F:	drivers/virt/coco/guest/
 F:	include/linux/*tsm*.h
+F:	samples/devsec/
 F:	samples/tsm-mr/
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/samples/Kconfig b/samples/Kconfig
index ffef99950206..8441593fb654 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -325,6 +325,22 @@ source "samples/rust/Kconfig"
 
 source "samples/damon/Kconfig"
 
+config SAMPLE_DEVSEC
+	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
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
index 000000000000..c8cb5c0cceb8
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
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_tsm.o
+devsec_tsm-y := tsm.o
diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
new file mode 100644
index 000000000000..675e185fcf79
--- /dev/null
+++ b/samples/devsec/bus.c
@@ -0,0 +1,708 @@
+// SPDX-License-Identifier: GPL-2.0-only
+// Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved.
+
+#include <linux/platform_device.h>
+#include <linux/genalloc.h>
+#include <linux/bitfield.h>
+#include <linux/cleanup.h>
+#include <linux/module.h>
+#include <linux/range.h>
+#include <uapi/linux/pci_regs.h>
+#include <linux/pci.h>
+
+#include "../../drivers/pci/pci-bridge-emul.h"
+#include "devsec.h"
+
+#define NR_DEVSEC_BUSES 1
+#define NR_DEVSEC_ROOT_PORTS 1
+#define NR_PORT_STREAMS 1
+#define NR_ADDR_ASSOC 1
+#define NR_DEVSEC_DEVS 1
+
+struct devsec {
+	struct pci_host_bridge hb;
+	struct devsec_sysdata sysdata;
+	struct gen_pool *iomem_pool;
+	struct resource resource[2];
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
+	} *devsec_ports[NR_DEVSEC_ROOT_PORTS];
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
+	} *devsec_devs[NR_DEVSEC_DEVS];
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
+			stream->status &= ~PCI_IDE_SEL_STS_STATE_MASK;
+			if (val & PCI_IDE_SEL_CTL_EN)
+				stream->status |= FIELD_PREP(
+					PCI_IDE_SEL_STS_STATE_MASK,
+					PCI_IDE_SEL_STS_STATE_SECURE);
+			else
+				stream->status |= FIELD_PREP(
+					PCI_IDE_SEL_STS_STATE_MASK,
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
+		   FIELD_PREP(PCI_IDE_CAP_SEL_NUM_MASK, NR_PORT_STREAMS - 1);
+
+	for (int i = 0; i < NR_PORT_STREAMS; i++)
+		ide->stream[i].cap =
+			FIELD_PREP(PCI_IDE_SEL_CAP_ASSOC_NUM_MASK, NR_ADDR_ASSOC);
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
+
+static void destroy_devsec_dev(void *data)
+{
+	struct devsec_dev *devsec_dev = data;
+	struct devsec *devsec = devsec_dev->devsec;
+
+	gen_pool_free(devsec->iomem_pool, devsec_dev->mmio_range.start,
+		      range_len(&devsec_dev->mmio_range));
+	kfree(devsec_dev);
+}
+
+static struct devsec_dev *devsec_dev_alloc(struct devsec *devsec)
+{
+	struct devsec_dev *devsec_dev __free(kfree) =
+		kzalloc(sizeof(*devsec_dev), GFP_KERNEL);
+	struct genpool_data_align data = {
+		.align = MMIO_SIZE,
+	};
+	u64 phys;
+
+	if (!devsec_dev)
+		return ERR_PTR(-ENOMEM);
+
+	phys = gen_pool_alloc_algo(devsec->iomem_pool, MMIO_SIZE,
+				   gen_pool_first_fit_align, &data);
+	if (!phys)
+		return ERR_PTR(-ENOMEM);
+
+	*devsec_dev = (struct devsec_dev) {
+		.mmio_range = {
+			.start = phys,
+			.end = phys + MMIO_SIZE - 1,
+		},
+		.devsec = devsec,
+	};
+	init_dev_cfg(devsec_dev);
+
+	return_ptr(devsec_dev);
+}
+
+static int alloc_devs(struct devsec *devsec)
+{
+	struct device *dev = devsec->dev;
+
+	for (int i = 0; i < ARRAY_SIZE(devsec->devsec_devs); i++) {
+		struct devsec_dev *devsec_dev = devsec_dev_alloc(devsec);
+		int rc;
+
+		if (IS_ERR(devsec_dev))
+			return PTR_ERR(devsec_dev);
+		rc = devm_add_action_or_reset(dev, destroy_devsec_dev,
+					      devsec_dev);
+		if (rc)
+			return rc;
+		devsec->devsec_devs[i] = devsec_dev;
+	}
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
+static int init_port(struct devsec_port *devsec_port)
+{
+	struct pci_bridge_emul *bridge = &devsec_port->bridge;
+
+	*bridge = (struct pci_bridge_emul) {
+		.conf = {
+			.vendor = cpu_to_le16(0x8086),
+			.device = cpu_to_le16(0x7075),
+			.class_revision = cpu_to_le32(0x1),
+			.pref_mem_base = cpu_to_le16(PCI_PREF_RANGE_TYPE_64),
+			.pref_mem_limit = cpu_to_le16(PCI_PREF_RANGE_TYPE_64),
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
+	return pci_bridge_emul_init(bridge, 0);
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
+static struct devsec_port *devsec_port_alloc(void)
+{
+	int rc;
+
+	struct devsec_port *devsec_port __free(kfree) =
+		kzalloc(sizeof(*devsec_port), GFP_KERNEL);
+
+	if (!devsec_port)
+		return ERR_PTR(-ENOMEM);
+
+	rc = init_port(devsec_port);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return_ptr(devsec_port);
+}
+
+static int alloc_ports(struct devsec *devsec)
+{
+	struct device *dev = devsec->dev;
+
+	for (int i = 0; i < ARRAY_SIZE(devsec->devsec_ports); i++) {
+		struct devsec_port *devsec_port = devsec_port_alloc();
+		int rc;
+
+		if (IS_ERR(devsec_port))
+			return PTR_ERR(devsec_port);
+		rc = devm_add_action_or_reset(dev, destroy_port, devsec_port);
+		if (rc)
+			return rc;
+		devsec->devsec_ports[i] = devsec_port;
+	}
+
+	return 0;
+}
+
+static int __init devsec_bus_probe(struct platform_device *pdev)
+{
+	int rc;
+	struct devsec *devsec;
+	u64 mmio_size = SZ_64G;
+	struct devsec_sysdata *sd;
+	struct pci_host_bridge *hb;
+	struct device *dev = &pdev->dev;
+	u64 mmio_start = iomem_resource.end + 1 - SZ_64G;
+
+	hb = devm_pci_alloc_host_bridge(
+		dev, sizeof(*devsec) - sizeof(struct pci_host_bridge));
+	if (!hb)
+		return -ENOMEM;
+
+	devsec = container_of(hb, struct devsec, hb);
+	devsec->dev = dev;
+	devsec->iomem_pool = devm_gen_pool_create(dev, ilog2(SZ_2M),
+						  NUMA_NO_NODE, "devsec iomem");
+	if (!devsec->iomem_pool)
+		return -ENOMEM;
+
+	rc = gen_pool_add(devsec->iomem_pool, mmio_start, mmio_size,
+			  NUMA_NO_NODE);
+	if (rc)
+		return rc;
+
+	rc = alloc_ports(devsec);
+	if (rc)
+		return rc;
+
+	rc = alloc_devs(devsec);
+	if (rc)
+		return rc;
+
+	devsec->resource[0] = (struct resource) {
+		.name = "DEVSEC BUSES",
+		.start = 0,
+		.end = NR_DEVSEC_BUSES + NR_DEVSEC_ROOT_PORTS - 1,
+		.flags = IORESOURCE_BUS | IORESOURCE_PCI_FIXED,
+	};
+	pci_add_resource(&hb->windows, &devsec->resource[0]);
+
+	devsec->resource[1] = (struct resource) {
+		.name = "DEVSEC MMIO",
+		.start = mmio_start,
+		.end = mmio_start + mmio_size - 1,
+		.flags = IORESOURCE_MEM | IORESOURCE_MEM_64,
+	};
+	pci_add_resource(&hb->windows, &devsec->resource[1]);
+
+	sd = &devsec->sysdata;
+	devsec_sysdata = sd;
+	hb->domain_nr = pci_bus_find_emul_domain_nr(PCI_DOMAIN_NR_NOT_SET);
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
+	return devm_add_action_or_reset(dev, destroy_bus, no_free_ptr(hb));
+}
+
+static struct platform_driver devsec_bus_driver = {
+	.driver = {
+		.name = "devsec_bus",
+	},
+};
+
+static struct platform_device *devsec_bus;
+
+static int __init devsec_bus_init(void)
+{
+	struct platform_device_info devsec_bus_info = {
+		.name = "devsec_bus",
+		.id = -1,
+	};
+	int rc;
+
+	devsec_bus = platform_device_register_full(&devsec_bus_info);
+	if (IS_ERR(devsec_bus))
+		return PTR_ERR(devsec_bus);
+
+	rc = platform_driver_probe(&devsec_bus_driver, devsec_bus_probe);
+	if (rc)
+		platform_device_unregister(devsec_bus);
+	return 0;
+}
+module_init(devsec_bus_init);
+
+static void __exit devsec_bus_exit(void)
+{
+	platform_driver_unregister(&devsec_bus_driver);
+	platform_device_unregister(devsec_bus);
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
diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
new file mode 100644
index 000000000000..a4705212a7e4
--- /dev/null
+++ b/samples/devsec/tsm.c
@@ -0,0 +1,173 @@
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
+	return container_of(tsm, struct devsec_tsm_pf0, pci.tsm);
+}
+
+static struct devsec_tsm_fn *to_devsec_tsm_fn(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct devsec_tsm_fn, pci);
+}
+
+static const struct pci_tsm_ops *__devsec_pci_ops;
+
+static struct pci_tsm *devsec_tsm_pf0_probe(struct pci_dev *pdev)
+{
+	int rc;
+
+	struct devsec_tsm_pf0 *devsec_tsm __free(kfree) =
+		kzalloc(sizeof(*devsec_tsm), GFP_KERNEL);
+	if (!devsec_tsm)
+		return NULL;
+
+	rc = pci_tsm_pf0_constructor(pdev, &devsec_tsm->pci, __devsec_pci_ops);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "tsm enabled\n");
+	return &no_free_ptr(devsec_tsm)->pci.tsm;
+}
+
+static struct pci_tsm *devsec_tsm_fn_probe(struct pci_dev *pdev)
+{
+	int rc;
+
+	struct devsec_tsm_fn *devsec_tsm __free(kfree) =
+		kzalloc(sizeof(*devsec_tsm), GFP_KERNEL);
+	if (!devsec_tsm)
+		return NULL;
+
+	rc = pci_tsm_constructor(pdev, &devsec_tsm->pci, __devsec_pci_ops);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "tsm (sub-function) enabled\n");
+	return &no_free_ptr(devsec_tsm)->pci;
+}
+
+static struct pci_tsm *devsec_tsm_pci_probe(struct pci_dev *pdev)
+{
+	if (pdev->sysdata != devsec_sysdata)
+		return NULL;
+
+	if (is_pci_tsm_pf0(pdev))
+		return devsec_tsm_pf0_probe(pdev);
+	return devsec_tsm_fn_probe(pdev);
+}
+
+static void devsec_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+
+	pci_dbg(pdev, "tsm disabled\n");
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
+static int devsec_tsm_connect(struct pci_dev *pdev)
+{
+	return -ENXIO;
+}
+
+static void devsec_tsm_disconnect(struct pci_dev *pdev)
+{
+}
+
+static struct pci_tsm_ops devsec_pci_ops = {
+	.probe = devsec_tsm_pci_probe,
+	.remove = devsec_tsm_pci_remove,
+	.connect = devsec_tsm_connect,
+	.disconnect = devsec_tsm_disconnect,
+};
+
+static void devsec_tsm_remove(void *tsm_dev)
+{
+	tsm_unregister(tsm_dev);
+}
+
+static int devsec_tsm_probe(struct faux_device *fdev)
+{
+	struct tsm_dev *tsm_dev;
+
+	tsm_dev = tsm_register(&fdev->dev, NULL, &devsec_pci_ops);
+	if (IS_ERR(tsm_dev))
+		return PTR_ERR(tsm_dev);
+
+	return devm_add_action_or_reset(&fdev->dev, devsec_tsm_remove,
+					tsm_dev);
+}
+
+static struct faux_device *devsec_tsm;
+
+static const struct faux_device_ops devsec_device_ops = {
+	.probe = devsec_tsm_probe,
+};
+
+static int __init devsec_tsm_init(void)
+{
+	__devsec_pci_ops = &devsec_pci_ops;
+	devsec_tsm = faux_device_create("devsec_tsm", NULL, &devsec_device_ops);
+	if (!devsec_tsm)
+		return -ENOMEM;
+	return 0;
+}
+module_init(devsec_tsm_init);
+
+static void __exit devsec_tsm_exit(void)
+{
+	faux_device_destroy(devsec_tsm);
+}
+module_exit(devsec_tsm_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Platform TSM Driver");

---

## [7] Dan Williams — 2025-07-17
*Subject: [PATCH v4 06/10] PCI: Add PCIe Device 3 Extended Capability enumeration*

PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
enumerates new link capabilities and status added for Gen 6 devices. One
of the link details enumerated in that register block is the "Segment
Captured" status in the Device Status 3 register. That status is
relevant for enabling IDE (Integrity & Data Encryption) whereby
Selective IDE streams can be limited to a given Requester ID range
within a given segment.

If a device has captured its Segment value then it knows that PCIe Flit
Mode is enabled via all links in the path that a configuration write
traversed. IDE establishment requires that "Segment Base" in
IDE RID Association Register 2 (PCIe 6.2 Section 7.9.26.5.4.2) be
programmed if the RID association mechanism is in effect.

When / if IDE + Flit Mode capable devices arrive, the PCI core needs to
setup the segment base when using the RID association facility, but no
known deployments today depend on this.

Cc: Lukas Wunner <lukas@wunner.de>
Cc: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/probe.c           | 12 ++++++++++++
 include/linux/pci.h           |  1 +
 include/uapi/linux/pci_regs.h |  7 +++++++
 3 files changed, 20 insertions(+)

diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index e19e7a926423..9ed25035a06d 100644
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
@@ -2625,6 +2636,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
+	pci_dev3_init(dev);		/* Device 3 capabilities */
 	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 0e5703fad0f6..a7353df51fea 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -444,6 +444,7 @@ struct pci_dev {
 	unsigned int	pasid_enabled:1;	/* Process Address Space ID */
 	unsigned int	pri_enabled:1;		/* Page Request Interface */
 	unsigned int	tph_enabled:1;		/* TLP Processing Hints */
+	unsigned int	fm_enabled:1;		/* Flit Mode (segment captured) */
 	unsigned int	is_managed:1;		/* Managed via devres */
 	unsigned int	is_msi_managed:1;	/* MSI release via devres installed */
 	unsigned int	needs_freset:1;		/* Requires fundamental reset */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 1b991a88c19c..2d49a4786a9f 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -751,6 +751,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_DEV3	0x2F	/* Device 3 Capability/Control/Status */
 #define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_PL_64GT	0x31	/* Physical Layer 64.0 GT/s */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_PL_64GT
@@ -1227,6 +1228,12 @@
 /* Deprecated old name, replaced with PCI_DOE_DATA_OBJECT_DISC_RSP_3_TYPE */
 #define PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL		PCI_DOE_DATA_OBJECT_DISC_RSP_3_TYPE
 
+/* Device 3 Extended Capability */
+#define PCI_DEV3_CAP		0x4	/* Device 3 Capabilities Register */
+#define PCI_DEV3_CTL		0x8	/* Device 3 Control Register */
+#define PCI_DEV3_STA		0xc	/* Device 3 Status Register */
+#define  PCI_DEV3_STA_SEGMENT	0x8	/* Segment Captured (end-to-end flit-mode detected) */
+
 /* Compute Express Link (CXL r3.1, sec 8.1.5) */
 #define PCI_DVSEC_CXL_PORT				3
 #define PCI_DVSEC_CXL_PORT_CTL				0x0c

---

## [8] Dan Williams — 2025-07-17
*Subject: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

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

pci_ide_stream_alloc()
  Allocate a Selective IDE Stream Register Block in each Partner Port
  (Endpoint + Root Port), and reserve a host bridge / platform stream
  slot. Gather Partner Port specific stream settings like Requester ID.
pci_ide_stream_register()
  Publish the stream in sysfs after allocating a Stream ID. In the TSM
  case the TSM allocates the Stream ID for the Partner Port pair.
pci_ide_stream_setup()
  Program the stream settings to a Partner Port. Caller is responsible
  for optionally calling this for the Root Port as well if the TSM
  implementation requires it.
pci_ide_stream_enable()
  Try to run the stream after IDE_KM.

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
Co-developed-by: Yilun Xu <yilun.xu@linux.intel.com>
Signed-off-by: Yilun Xu <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge |  16 +
 drivers/pci/ide.c                             | 422 ++++++++++++++++++
 include/linux/pci-ide.h                       |  70 +++
 include/linux/pci.h                           |   6 +
 4 files changed, 514 insertions(+)
 create mode 100644 include/linux/pci-ide.h

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index 8c3a652799f1..c67d7c30efa0 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -17,3 +17,19 @@ Description:
 		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00). See
 		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
 		format.
+
+What:		pciDDDD:BB/streamH.R.E
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a platform has established a secure connection, PCIe
+		IDE, between two Partner Ports, this symlink appears. The
+		primary function is to account the stream slot / resources
+		consumed in each of the (H)ost bridge, (R)oot Port and
+		(E)ndpoint that will be freed when invoking the tsm/disconnect
+		flow. The link points to the endpoint PCI device in the
+		Selective IDE Stream. "R" and "E" represent the assigned
+		Selective IDE Stream Register Block in the Root Port and
+		Endpoint, and "H" represents a platform specific pool of stream
+		resources shared by the Root Ports in a host bridge. See
+		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
+		format.
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index e15937cdb2a4..cdc773a8b381 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -5,6 +5,8 @@
 
 #define dev_fmt(fmt) "PCI/IDE: " fmt
 #include <linux/pci.h>
+#include <linux/sysfs.h>
+#include <linux/pci-ide.h>
 #include <linux/bitfield.h>
 #include "pci.h"
 
@@ -24,6 +26,13 @@ static int __sel_ide_offset(u16 ide_cap, u8 nr_link_ide, u8 stream_index,
 	return offset;
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
@@ -89,5 +98,418 @@ void pci_ide_init(struct pci_dev *pdev)
 
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
+int pci_ide_domain(struct pci_dev *pdev)
+{
+	if (pdev->fm_enabled)
+		return pci_domain_nr(pdev->bus);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_domain);
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
+static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide, int pos,
+			    bool enable)
+{
+	u32 val = FIELD_PREP(PCI_IDE_SEL_CTL_ID_MASK, ide->stream_id) |
+		  FIELD_PREP(PCI_IDE_SEL_CTL_DEFAULT, 1) |
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
+	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT_MASK, settings->rid_end);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
+
+	val = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
+	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE_MASK, settings->rid_start) |
+	      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG_MASK, pci_ide_domain(pdev));
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
+
+	/*
+	 * Setup control register early for devices that expect
+	 * stream_id is set during key programming.
+	 */
+	set_ide_sel_ctl(pdev, ide, pos, false);
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
+ * pci_ide_stream_enable() - try to enable a Selective IDE Stream
+ * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
+ * @ide: registered and setup IDE settings descriptor
+ *
+ * Activate the stream by writing to the Selective IDE Stream Control
+ * Register, report whether the state successfully transitioned to
+ * secure mode. Note that the state may go "insecure" at any point after
+ * this check, but that is handled via asynchronous error reporting.
+ */
+int pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	int pos;
+	u32 val;
+
+	if (!settings)
+		return -ENXIO;
+
+	pos = sel_ide_offset(pdev, settings);
+
+	set_ide_sel_ctl(pdev, ide, pos, true);
+
+	pci_read_config_dword(pdev, pos + PCI_IDE_SEL_STS, &val);
+	if (FIELD_GET(PCI_IDE_SEL_STS_STATE_MASK, val) !=
+	    PCI_IDE_SEL_STS_STATE_SECURE) {
+		set_ide_sel_ctl(pdev, ide, pos, false);
+		return -ENXIO;
+	}
+
+	settings->enable = 1;
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
index 000000000000..89c1ef0de841
--- /dev/null
+++ b/include/linux/pci-ide.h
@@ -0,0 +1,70 @@
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
+ * @setup: flag to track whether to run pci_ide_stream_teardown for this parnter slot
+ * @enable: flag whether to run pci_ide_stream_disable for this parnter slot
+ */
+struct pci_ide_partner {
+	u16 rid_start;
+	u16 rid_end;
+	u8 stream_index;
+	unsigned int setup:1;
+	unsigned int enable:1;
+};
+
+/**
+ * struct pci_ide - PCIe Selective IDE Stream descriptor
+ * @pdev: PCIe Endpoint in the pci_ide_partner pair
+ * @partner: Per-partner settings
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
+int pci_ide_domain(struct pci_dev *pdev);
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
index a7353df51fea..cc83ae274601 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -538,6 +538,8 @@ struct pci_dev {
 	u16		ide_cap;	/* Link Integrity & Data Encryption */
 	u8		nr_ide_mem;	/* Address association resources for streams */
 	u8		nr_link_ide;	/* Link Stream count (Selective Stream offset) */
+	u8		nr_sel_ide;	/* Selective Stream count (register block allocator) */
+	DECLARE_BITMAP(ide_stream_map, CONFIG_PCI_IDE_STREAM_MAX);
 	unsigned int	ide_cfg:1;	/* Config cycles over IDE */
 	unsigned int	ide_tee_limit:1; /* Disallow T=0 traffic over IDE */
 #endif
@@ -607,6 +609,10 @@ struct pci_host_bridge {
 	int		domain_nr;
 	struct list_head windows;	/* resource_entry */
 	struct list_head dma_ranges;	/* dma ranges resource list */
+#ifdef CONFIG_PCI_IDE
+	u8 nr_ide_streams;		/* Track available vs in-use streams */
+	DECLARE_BITMAP(ide_stream_map, CONFIG_PCI_IDE_STREAM_MAX);
+#endif
 	u8 (*swizzle_irq)(struct pci_dev *, u8 *); /* Platform IRQ swizzler */
 	int (*map_irq)(const struct pci_dev *, u8, u8);
 	void (*release_fn)(struct pci_host_bridge *);

---

## [9] Dan Williams — 2025-07-17
*Subject: [PATCH v4 08/10] PCI/IDE: Report available IDE streams*

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
Cc: Xu Yi lun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge | 13 ++++
 drivers/pci/ide.c                             | 59 +++++++++++++++++++
 drivers/pci/pci.h                             |  3 +
 drivers/pci/probe.c                           | 12 +++-
 include/linux/pci.h                           |  8 +++
 5 files changed, 94 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index c67d7c30efa0..067d0879e353 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -33,3 +33,16 @@ Description:
 		resources shared by the Root Ports in a host bridge. See
 		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
 		format.
+
+What:		pciDDDD:BB/available_secure_streams
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host bridge has Root Ports that support PCIe IDE
+		(link encryption and integrity protection) there may be a
+		limited number of Selective IDE Streams that can be used for
+		establishing new end-to-end secure links. This attribute
+		decrements upon secure link setup, and increments upon secure
+		link teardown. The in-use stream count is determined by counting
+		stream symlinks.  See /sys/devices/pciDDDD:BB entry for details
+		about the DDDD:BB format.
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index cdc773a8b381..cafbc740a9da 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -513,3 +513,62 @@ void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide)
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
index 3b282c24dde8..8154f829d303 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -517,8 +517,11 @@ static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 
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
index 9ed25035a06d..a84aaad462ca 100644
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
index cc83ae274601..ae5f32539a91 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -664,6 +664,14 @@ void pci_set_host_bridge_release(struct pci_host_bridge *bridge,
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

## [10] Dan Williams — 2025-07-17
*Subject: [PATCH v4 09/10] PCI/TSM: Report active IDE streams*

Given that the platform TSM owns IDE Stream ID allocation, report the
active streams via the TSM class device. Establish a symlink from the
class device to the PCI endpoint device consuming the stream, named by
the Stream ID.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm | 10 ++++++++
 drivers/pci/ide.c                         |  4 ++++
 drivers/virt/coco/tsm-core.c              | 28 +++++++++++++++++++++++
 include/linux/pci-ide.h                   |  2 ++
 include/linux/tsm.h                       |  4 ++++
 5 files changed, 48 insertions(+)

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
index cafbc740a9da..923b0db4803c 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -5,6 +5,7 @@
 
 #define dev_fmt(fmt) "PCI/IDE: " fmt
 #include <linux/pci.h>
+#include <linux/tsm.h>
 #include <linux/sysfs.h>
 #include <linux/pci-ide.h>
 #include <linux/bitfield.h>
@@ -271,6 +272,9 @@ void pci_ide_stream_release(struct pci_ide *ide)
 	if (ide->partner[PCI_IDE_EP].enable)
 		pci_ide_stream_disable(pdev, ide);
 
+	if (ide->tsm_dev)
+		tsm_ide_stream_unregister(ide);
+
 	if (ide->partner[PCI_IDE_RP].setup)
 		pci_ide_stream_teardown(rp, ide);
 
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 093824dc68dd..b0ef9089e0f2 100644
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
@@ -140,6 +143,31 @@ void tsm_unregister(struct tsm_dev *tsm_dev)
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
+	rc = sysfs_create_link(&tsm_dev->dev.kobj, &pdev->dev.kobj,
+				 ide->name);
+	if (rc == 0)
+		ide->tsm_dev = tsm_dev;
+	return rc;
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
index 89c1ef0de841..36290bdaf51f 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -42,6 +42,7 @@ struct pci_ide_partner {
  * @host_bridge_stream: track platform Stream ID
  * @stream_id: unique Stream ID (within Partner Port pairing)
  * @name: name of the established Selective IDE Stream in sysfs
+ * @tsm_dev: For TSM established IDE, the TSM device context
  *
  * Negative @stream_id values indicate "uninitialized" on the
  * expectation that with TSM established IDE the TSM owns the stream_id
@@ -53,6 +54,7 @@ struct pci_ide {
 	u8 host_bridge_stream;
 	int stream_id;
 	const char *name;
+	struct tsm_dev *tsm_dev;
 };
 
 int pci_ide_domain(struct pci_dev *pdev);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index ce95589a5d5b..4eba45a754ec 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -120,4 +120,8 @@ const char *tsm_name(const struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
 const struct pci_tsm_ops *tsm_pci_ops(const struct tsm_dev *tsm_dev);
 const struct attribute_group *tsm_pci_group(const struct tsm_dev *tsm_dev);
+struct pci_dev;
+struct pci_ide;
+int tsm_ide_stream_register(struct pci_ide *ide);
+void tsm_ide_stream_unregister(struct pci_ide *ide);
 #endif /* __TSM_H */

---

## [11] Dan Williams — 2025-07-17
*Subject: [PATCH v4 10/10] samples/devsec: Add sample IDE establishment*

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
 samples/devsec/bus.c |  3 ++
 samples/devsec/tsm.c | 70 +++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 72 insertions(+), 1 deletion(-)

diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
index 675e185fcf79..efd7a650b20d 100644
--- a/samples/devsec/bus.c
+++ b/samples/devsec/bus.c
@@ -15,6 +15,7 @@
 
 #define NR_DEVSEC_BUSES 1
 #define NR_DEVSEC_ROOT_PORTS 1
+#define NR_PLATFORM_STREAMS 4
 #define NR_PORT_STREAMS 1
 #define NR_ADDR_ASSOC 1
 #define NR_DEVSEC_DEVS 1
@@ -662,6 +663,7 @@ static int __init devsec_bus_probe(struct platform_device *pdev)
 	hb->dev.parent = dev;
 	hb->sysdata = sd;
 	hb->ops = &devsec_ops;
+	pci_ide_init_nr_streams(hb, NR_PLATFORM_STREAMS);
 
 	rc = pci_scan_root_bus_bridge(hb);
 	if (rc)
@@ -704,5 +706,6 @@ static void __exit devsec_bus_exit(void)
 }
 module_exit(devsec_bus_exit);
 
+MODULE_IMPORT_NS("PCI_IDE");
 MODULE_LICENSE("GPL");
 MODULE_DESCRIPTION("Device Security Sample Infrastructure: TDISP Device Emulation");
diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
index a4705212a7e4..b93396ca0c92 100644
--- a/samples/devsec/tsm.c
+++ b/samples/devsec/tsm.c
@@ -4,6 +4,7 @@
 #define dev_fmt(fmt) "devsec: " fmt
 #include <linux/device/faux.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 #include <linux/module.h>
 #include <linux/pci.h>
 #include <linux/tsm.h>
@@ -92,6 +93,23 @@ static void devsec_tsm_pci_remove(struct pci_tsm *tsm)
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
@@ -116,11 +134,61 @@ static void devsec_tsm_pci_remove(struct pci_tsm *tsm)
  */
 static int devsec_tsm_connect(struct pci_dev *pdev)
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
 
 static void devsec_tsm_disconnect(struct pci_dev *pdev)
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
 
 static struct pci_tsm_ops devsec_pci_ops = {

---

## [12] Aneesh Kumar K.V — 2025-07-18
*Subject: Re: [PATCH v4 00/10] PCI/TSM: Core infrastructure for PCI device
 security (TDISP)*

Dan Williams <dan.j.williams@intel.com> writes:

> Changes since v3 [1]:
> - Move the TSM core out of the host/ subdirectory since it is shared

This series currently doesn’t include the TDI bind equivalent.
Incorporating some of the changes from patch [1] would help lay the
groundwork for submitting the remaining POC patches.

Also, could you clarify the purpose of sec_probe and sec_remove? How are
they being used?

[1] https://lore.kernel.org/all/20250516054732.2055093-13-dan.j.williams@intel.com

-aneesh

---

## [13] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 01/10] coco/tsm: Introduce a core device for TEE
 Security Managers*

On Thu, 17 Jul 2025 11:33:49 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> A "TSM" is a platform component that provides an API for securely
> provisioning resources for a confidential guest (TVM) to consume. The

Nice. One trivial comment inline.

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

> diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
> index f918bbb61737..c0c3733be165 100644

Unrelated change.

>  obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
>  obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/

---

## [14] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Thu, 17 Jul 2025 11:33:50 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Link encryption is a new PCIe feature enumerated by "PCIe 6.2 section
> 7.9.26 IDE Extended Capability".

Seems that one field has changed naming and gained broader meaning
between 6.0 and 6.2 (which I was checking against).
I guess resolving that will require some digging into whether it
was an errata an intentional change.  Definitely wants a comment
though.

Other than that and a few trivial things LGTM.

> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> new file mode 100644

> +static int __sel_ide_offset(u16 ide_cap, u8 nr_link_ide, u8 stream_index,
> +			    u8 nr_ide_mem)

	return offset + stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);

is perhaps a little bit neater?

> +}

> diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
> index a3a3e942dedf..ab4ebf0f8a46 100644

Spec uses two digits. Things are a bit inconsistent in this file but
0x04 looks like the most common syntax if hex.  Curiously some are
not in hex.  Anyhow, I'd go with 0x04 etc for all register offsets
unless Bjorn or someone else shouts otherwise!


> +#define  PCI_IDE_CAP_LINK		0x1  /* Link IDE Stream Supported */
> +#define  PCI_IDE_CAP_SELECTIVE		0x2  /* Selective IDE Streams Supported */
Looking at the rest of this file I think this should be.
#define  PCI_IDE_CAP_ALG_MASK		__GENMASK(12, 8) /* Supported Algorithms */
#define   PCI_IDE_CAP_ALG_AES_GCM_256	0    /* AES-GCM 256 key size, 96b MAC */

So indent one more space. Example being PCI_LPH_LOC_NONE

> +#define  PCI_IDE_CAP_LINK_TC_NUM_MASK	__GENMASK(15, 13) /* Link IDE TCs */
> +#define  PCI_IDE_CAP_SEL_NUM_MASK	__GENMASK(23, 16)/* Supported Selective IDE Streams */

Space before comment missing?

> +#define  PCI_IDE_CAP_TEE_LIMITED	0x1000000 /* TEE-Limited Stream Supported */
> +#define PCI_IDE_CTL			0x8
As above 0x08 more consistent with rest of the file.  Same for remaining cases.
> +#define  PCI_IDE_CTL_FLOWTHROUGH_IDE	0x4  /* Flow-Through IDE Stream Enabled */
> +

Event this I think should be 0x01 for consistency

> +#define  PCI_IDE_LINK_CTL_EN		   0x1               /* Link IDE Stream Enable */
> +#define  PCI_IDE_LINK_CTL_TX_AGGR_NPR_MASK __GENMASK(3, 2)   /* Tx Aggregation Mode NPR */
Naming here is drawing on stuff not in the Status register description (in 6.2 anyway which is what I'm
checking against).  That just calls this Received IDE Fail Message.
The text else where calls it out 'Upon transition from Secure to Insecure for any reason, other than
corresponding Link/Selective IDE Stream Enable bit is Cleared, for a given Stream, the Port must transmit an
IDE Fail Message indicating the Stream ID to the Partner port'

To me the integrity check naming doesn't really cover that.

I did some minimal digging. Your text matches 6.0. 


> +
> +/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */

0x00

> +#define  PCI_IDE_SEL_CAP_ASSOC_NUM_MASK	 __GENMASK(3, 0)
> +/* Selective IDE Stream Control Register */

Same thing.

> +/* IDE RID Association Register 1 */
> +#define  PCI_IDE_SEL_RID_1		 0xc

---

## [15] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 03/10] PCI: Introduce pci_walk_bus_reverse(),
 for_each_pci_dev_reverse()*

On Thu, 17 Jul 2025 11:33:51 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> PCI/TSM, the PCI core functionality for the PCIe TEE Device Interface
> Security Protocol (TDISP), has a need to walk all subordinate functions of

A couple of trivial comments.

Probably want to +CC Greg KH on next version given bits in drivers/base

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

> diff --git a/drivers/pci/bus.c b/drivers/pci/bus.c
> index 69048869ef1c..d894c87ce1fd 100644

include cleanup.h perhaps for access to guard()?


> diff --git a/drivers/pci/search.c b/drivers/pci/search.c
> index 53840634fbfc..7a4623f65256 100644

I don't really care, but given there are only two sane directions maybe
a bool reverse as a parameter to __pci_get_subsys() would be sufficient? 

> +static struct pci_dev *__pci_get_subsys(unsigned int vendor, unsigned int device,
> +				 unsigned int ss_vendor, unsigned int ss_device,
This file seems to use 1 blank line only between functions.
> +
>  /**

---

## [16] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

On Thu, 17 Jul 2025 11:33:52 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This
Various things inline.

> diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> new file mode 100644

> +static void tsm_remove(struct pci_tsm *tsm)
> +{

You protect against this in the DEFINE_FREE() so probably safe
to assume it is always set if we get here.

> +		return;
> +

Is this combination worth while?  I don't like the 'and' aspect of it
and it only saves a few lines...

vs
	if (pdev) {
		rc = cb(pdev, data);
		pci_dev_put(pdev);
		if (rc)
			return;
	}

> +		       int (*cb)(struct pci_dev *pdev, void *data))
> +{

spaces rather than tabs...


> +                return;
> +
While it probably doesn't matter can we make this strict reverse by doing
the physical functions first?  I prefer not to think about whether it matters.


> +	/* reverse walk subordinate physical functions */
> +	for (i = 7; i >= 1; i--) {

Likewise, can we do this before the rest.

> +}

> +/*
> + * Find the PCI Device instance that serves as the Device Security


Unusual for a find command to not hold the device reference on the device
it returns.  Maybe just call that out in the comment.

> +
> +	/*
Odd alignment. Space rather than tab.


> +	if (!pdev->dev.parent || !pdev->dev.parent->parent)
> +		return NULL;


> +/**
> + * pci_tsm_pf0_constructor() - common 'struct pci_tsm_pf0' initialization

ops missing.  Run kernel-doc or do W=1 build to catch these.

> + */
> +int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
Might as well do devm_mutex_init()

> +	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
> +					   PCI_DOE_PROTO_CMA);

> diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
> index 1f53b9049e2d..093824dc68dd 100644

> +/*
> + * Caller responsible for ensuring it does not race tsm_dev
Wrap is a bit early. unregistration fits on the line above.
> + */
> +struct tsm_dev *find_tsm_dev(int id)

> @@ -44,6 +76,29 @@ static struct tsm_dev *alloc_tsm_dev(struct device *parent,
>  	return no_free_ptr(tsm_dev);

As below. I'm fairly sure this device_unregister is nothing to do with
what this function is doing, so having it buried in here is less easy
to follow than pushing it up a layer.

> +		return ERR_PTR(rc);
> +	}

Having a function call that either succeeds or cleans up something it
never did on error is odd.  The or_reset hints at that oddity but
to me is not enough. If you want to use __free magic in here
maybe hand off the tsm_dev on succesful device registration.

	struct tsm_dev *registered_tsm_dev __free(unregister_tsm_dev) =
		no_free_ptr(tsm_dev);

	rc = tsm_register_pci(registered_tsm_dev, pci_ops);
	//change return type as no need for another tsm_dev
	if (rc)
		return ERR_PTR(rc);

	return no_free_ptr(registered_tsm_dev);
	

>  }
>  EXPORT_SYMBOL_GPL(tsm_register);

/**

Or was this intentional? Feels like it should be kernel-doc. 

> + * struct pci_tsm_ops - manage confidential links and security state
> + * @link_ops: Coordinate PCIe SPDM and IDE establishment via a platform TSM.
Likewise though I'm not sure if kernel-doc deals with struct groups.

> +	 * struct pci_tsm_link_ops - Manage physical link and the TSM/DSM session
> +	 * @probe: probe device for tsm link operation readiness, setup

> +
> +/**

What is @state referring to? 

> + * @doe_mb: PCIe Data Object Exchange mailbox
> + */

---

## [17] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI
 device-security bus + endpoint sample*

On Thu, 17 Jul 2025 11:33:53 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Establish just enough emulated PCI infrastructure to register a sample
> TSM (platform security manager) driver and have it discover an IDE + TEE

A fairly superficial review.  Too much staring at code today
to check the emulation was right and have any chance of spotting bugs!

> diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
> new file mode 100644

> +static int alloc_devs(struct devsec *devsec)
> +{

Similar to below.  Maybe use it inline.

> +
> +	for (int i = 0; i < ARRAY_SIZE(devsec->devsec_devs); i++) {


> +static int init_port(struct devsec_port *devsec_port)
> +{

Emulating something real?  If not maybe we should get an ID from another space
(or reserve this one ;)

> +			.class_revision = cpu_to_le32(0x1),
> +			.pref_mem_base = cpu_to_le16(PCI_PREF_RANGE_TYPE_64),


> +{
> +	struct device *dev = devsec->dev;

Only used once. I'd move it down there.

> +
> +	for (int i = 0; i < ARRAY_SIZE(devsec->devsec_ports); i++) {

I'd move dev up a line.

> +	if (!hb)
> +		return -ENOMEM;



> diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
> new file mode 100644

> +
> +static const struct pci_tsm_ops *__devsec_pci_ops;

As below. I'm not seeing why we can't use &devsec_pci_ops directly here.

> +	if (rc)
> +		return NULL;

here as well.

> +	if (rc)
> +		return NULL;

> +static struct pci_tsm_ops devsec_pci_ops = {
> +	.probe = devsec_tsm_pci_probe,

I'm not immediately grasping why this global is needed.
You never check if it's set, so why not just move definition of devsec_pci_ops
early enough that can be directly used everywhere.


> +	devsec_tsm = faux_device_create("devsec_tsm", NULL, &devsec_device_ops);
> +	if (!devsec_tsm)

---

## [18] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 06/10] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Thu, 17 Jul 2025 11:33:54 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
> enumerates new link capabilities and status added for Gen 6 devices. One

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>


> diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
> index 1b991a88c19c..2d49a4786a9f 100644

Similar to earlier cases I'd make these 0x04 etc just to copy local style + match spec.


> +#define PCI_DEV3_CTL		0x8	/* Device 3 Control Register */
> +#define PCI_DEV3_STA		0xc	/* Device 3 Status Register */

---

## [19] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

On Thu, 17 Jul 2025 11:33:55 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into

A few minor things inline.

> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> index e15937cdb2a4..cdc773a8b381 100644


> +/**
> + * pci_ide_stream_enable() - try to enable a Selective IDE Stream
and report

> ... Note that the state may go "insecure" at any point after
> + * this check, but that is handled via asynchronous error reporting.

> diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
> new file mode 100644
...

> +/**
> + * struct pci_ide_partner - Per port pair Selective IDE Stream settings

partner.

> + * @enable: flag whether to run pci_ide_stream_disable for this parnter slot

same again.

> + */
> +struct pci_ide_partner {
per-partner maybe?  Capitalization seems a little random
as mostly you have used them for spec terms, but Per-partner probably
isn't one?

> + * @host_bridge_stream: track platform Stream ID
> + * @stream_id: unique Stream ID (within Partner Port pairing)

> diff --git a/include/linux/pci.h b/include/linux/pci.h
> index a7353df51fea..cc83ae274601 100644

Which does it do?  Confusing comment.

> +	DECLARE_BITMAP(ide_stream_map, CONFIG_PCI_IDE_STREAM_MAX);
> +#endif

---

## [20] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 08/10] PCI/IDE: Report available IDE streams*

On Thu, 17 Jul 2025 11:33:56 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> The limited number of link-encryption (IDE) streams that a given set of
> host bridges supports is a platform specific detail. Provide
LGTM

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [21] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 09/10] PCI/TSM: Report active IDE streams*

On Thu, 17 Jul 2025 11:33:57 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Given that the platform TSM owns IDE Stream ID allocation, report the
> active streams via the TSM class device. Establish a symlink from the
Trivial stuff only
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

> ---
>  Documentation/ABI/testing/sysfs-class-tsm | 10 ++++++++

> diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
> index 093824dc68dd..b0ef9089e0f2 100644

> +/* must be invoked between tsm_register / tsm_unregister */
> +int tsm_ide_stream_register(struct pci_ide *ide)

Fits on one line under 80 chars (just)

> +	if (rc == 0)
> +		ide->tsm_dev = tsm_dev;

I'd prefer 

	if (rc)
		return rc;

	ide->tsm_dev = tsm_dev;

	return 0;

but don't care that much.

> +	return rc;
> +}

> diff --git a/include/linux/tsm.h b/include/linux/tsm.h
> index ce95589a5d5b..4eba45a754ec 100644

Not used.

> +struct pci_ide;
> +int tsm_ide_stream_register(struct pci_ide *ide);

---

## [22] Jonathan Cameron — 2025-07-29
*Subject: Re: [PATCH v4 10/10] samples/devsec: Add sample IDE establishment*

On Thu, 17 Jul 2025 11:33:58 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Exercise common setup and teardown flows for a sample platform TSM
> driver that implements the TSM 'connect' and 'disconnect' flows.
One really trivial comment inline.

> diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
> index a4705212a7e4..b93396ca0c92 100644


>  
>  static void devsec_tsm_disconnect(struct pci_dev *pdev)

pet irritation - why imply cases that can't occur.

	if (i == NR_TSM_STREAMS)

> +		return;
> +

---

## [23] Xu Yilun — 2025-08-05
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

> +static int pci_tsm_connect(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
> +{

[...]

> +static void pf0_sysfs_enable(struct pci_dev *pdev)
> +{

[...]

> +	for_each_pci_dev(pdev)
> +		if (is_pci_tsm_pf0(pdev))

Now the tsm attributes are exposed to user before ops->probe(), from
user's POV, tsm link operation for this device is already ready ...

> +	return 0;
> +}

[...]

> +struct pci_tsm_ops {
> +	/*

So I think the probe callback is losing the meaning of readiness check.
Users see the 'connect/disconnect', they write 'connect' and found
errors no matter ->probe() fails or ->connect() fails.

Maybe just remove the responsibility of readiness check from ->probe(),
I found it simplifies code when implementing tdx-tsm driver.

Thanks,
Yilun

> +	 *	   DSM context
> +	 * @remove: destroy DSM context

---

## [24] dan.j.williams@intel.com — 2025-08-05
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

Jonathan Cameron wrote:
[..]
> > diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> > new file mode 100644

Sure.

> 
> > +}

While I'm here, might as well.

> > +#define  PCI_IDE_CAP_LINK		0x1  /* Link IDE Stream Supported */
> > +#define  PCI_IDE_CAP_SELECTIVE		0x2  /* Selective IDE Streams Supported */

ok.

> 
> > +#define  PCI_IDE_CAP_LINK_TC_NUM_MASK	__GENMASK(15, 13) /* Link IDE TCs */

Got it.

> 
> > +#define  PCI_IDE_CAP_TEE_LIMITED	0x1000000 /* TEE-Limited Stream Supported */

You mean 0x00, right?

> 
> > +#define  PCI_IDE_LINK_CTL_EN		   0x1               /* Link IDE Stream Enable */

Will update to:

#define  PCI_IDE_LINK_STS_IDE_FAIL         0x80000000        /* IDE fail message received */

...and same for selective.

[ snip the other occurences of 0-padding register offsets ]

---

## [25] dan.j.williams@intel.com — 2025-08-05
*Subject: Re: [PATCH v4 03/10] PCI: Introduce pci_walk_bus_reverse(),
 for_each_pci_dev_reverse()*

Jonathan Cameron wrote:
> On Thu, 17 Jul 2025 11:33:51 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Oh, true. On last revision I copied him on whole series. Missed that this
time.

> 
> Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

Sure.

> > diff --git a/drivers/pci/search.c b/drivers/pci/search.c
> > index 53840634fbfc..7a4623f65256 100644

I dislike reading:

   return __pci_get_subsys(vendor, device, ss_vendor, ss_device, from, false);

...in isolation where I must walk the symbol to the function to figure
out what that parameter means vs:

   return __pci_get_subsys(vendor, device, ss_vendor, ss_device, from,
                           PCI_SEARCH_FORWARD);

...which is immediately clear.

> 
> > +static struct pci_dev *__pci_get_subsys(unsigned int vendor, unsigned int device,

ok.

---

## [26] dan.j.williams@intel.com — 2025-08-05
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

Jonathan Cameron wrote:
> On Thu, 17 Jul 2025 11:33:52 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

It is safe, but I would rather not require reading other code to
understand the expectation that some callers may unconditionally call
this routine.

> > +		return;
> > +

I think it is worth it, but an even better option is to just let
scope-based cleanup handle it by moving the variable inside the loop
declaration.

> 
> > +		       int (*cb)(struct pci_dev *pdev, void *data))

Fixed.

> > +                return;
> > +

Actually, me too, and in that case I also want the downstream devices to
be done in strict reverse order. So, I do not have a use in mind where
this matters, but changed the order to physical->virtual->downstream and
downstream->virtual->physical for the reverse case.

Oh, this is missing the potential case of SR-IOV on multiple physical
functions of the device, so added that too.

> 
> > +	/* reverse walk subordinate physical functions */

Fixed.

> 
> > +}

It is, "Note that no additional reference..."

> > +
> > +	/*

Hmm, clang-format does not fixup tabs vs spaces in block comments,
fixed.


> 
> 

TIL I do not need need to create a Documentation file to reference this
file to get kdoc build warnings.

Fixed.

> 
> > + */

Hmm, no, this is running out of the driver bind lifetime of @pdev.

> > +	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
> > +					   PCI_DOE_PROTO_CMA);

True, fixed up editor settings to automate this.

> > + */
> > +struct tsm_dev *find_tsm_dev(int id)

I prefer a short function with an early exit and no scope based unwind
for this.

> > +		return ERR_PTR(rc);
> > +	}

devm_add_action_or_reset() is the same pattern. Do the action, or
otherwise take care of cleaning up. The action in this case is
pci_tsm_register() and the reset is cleaning up the device_add().


> The or_reset hints at that oddity but to me is not enough. If you want
> to use __free magic in here maybe hand off the tsm_dev on succesful

That does not look like an improvement to me.

The moment device_add() succeeds the cleanup shifts from put_device() to
device_unregister(). I considered wrapping device_add(), but I think it
is awkard to redeclare the same variable again vs being able to walk all
instances of @tsm_dev in the function.

[..]
> > + * struct pci_tsm_ops - manage confidential links and security state
> > + * @link_ops: Coordinate PCIe SPDM and IDE establishment via a platform TSM.

It does not.

> > +/**
> > + * struct pci_tsm_pf0 - Physical Function 0 TDISP link context

@state was removed with v4 of the PCI/TSM series.

The kernel-doc for 'struct pci_tsm_pf0' is now:


/**
 * struct pci_tsm_pf0 - Physical Function 0 TDISP link context
 * @tsm: generic core "tsm" context
 * @lock: mutual exclustion for pci_tsm_ops invocation
 * @doe_mb: PCIe Data Object Exchange mailbox
 */
struct pci_tsm_pf0 {
        struct pci_tsm tsm;
        struct mutex lock;
        struct pci_doe_mb *doe_mb;
};

---

## [27] dan.j.williams@intel.com — 2025-08-05
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

Jonathan Cameron wrote:
> On Thu, 17 Jul 2025 11:33:53 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

ok.

> > +	for (int i = 0; i < ARRAY_SIZE(devsec->devsec_devs); i++) {
> > +		struct devsec_dev *devsec_dev = devsec_dev_alloc(devsec);

I am happy to switch to something else, but no, I do not have time to
chase this through PCI SIG. I do not expect this id to cause conflicts,
but no guarantees.

> > +			.class_revision = cpu_to_le32(0x1),
> > +			.pref_mem_base = cpu_to_le16(PCI_PREF_RANGE_TYPE_64),

ok.

> 
> > +

clang-format disagrees and I prefer just letting a tool do my formatting.

[..]
> > +static int __init devsec_tsm_init(void)
> > +{

Because devsec_pci_ops is used inside the ops it declares. So either
forward declare all those ops, or do this pointer assigment dance. I
opted for the latter as it is smaller.

---

## [28] Jonathan Cameron — 2025-08-06
*Subject: Re: [PATCH v4 03/10] PCI: Introduce pci_walk_bus_reverse(),
 for_each_pci_dev_reverse()*

> > > +enum pci_search_direction {
> > > +	PCI_SEARCH_FORWARD,
Fair enough.

> 
> >

---

## [29] Jonathan Cameron — 2025-08-06
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

> >   
> > > diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c

I think a function like remove being called on 'nothing' should
pretty much always be a bug, but meh, up to you.

> 
> > > +		return;
I don't follow that lat bit, but will look at next version to see
what you mean!

> 

> > > +                return;
> > > +

Good point :)

> > > diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
> > > index 1f53b9049e2d..093824dc68dd 100644

> > > +static struct tsm_dev *tsm_register_pci_or_reset(struct tsm_dev *tsm_dev,
> > > +						 struct pci_tsm_ops *pci_ops)

It's a pretty obscure pattern but I agree there is that precedence.
In my head that one case gets to be 'special' because it is always
calling the callback, just a question of now or later (in remove).
Here thing callback happens in remove but it's explicit and nothing
to do with this function (unlikely the devm version)

Anyhow, not a thing I'm going to bother pushing back that hard on.
> 
> 

I agree it's a slightly odd construction and so might cause confusion.
So whilst I think I prefer it to the or_reset() pattern I guess I'll just
try and remember why this is odd (should I ever read this again after it's
merged!) :)

> 
> [..]

Hmm. Given they are getting common maybe that's one to address, but
obviously not in this series.

Jonathan

---

## [30] Jonathan Cameron — 2025-08-06
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI
 device-security bus + endpoint sample*

+CC Gerd, of off chance we can use a Redhat PCI device ID for kernel
emulation similar to those they let Qemu use.

> 
> > > +	for (int i = 0; i < ARRAY_SIZE(devsec->devsec_devs); i++) {

Nothing to do with the SIG - you definitely don't want to try talking them
into giving a Vendor ID for the kernel.  That's an Intel ID so you need to find
the owner of whatever tracker Intel uses for these.  Or maybe we can ask for
one of the Redhat ones (maintained by Gerd).

> 
> > > +			.class_revision = cpu_to_le32(0x1),

...
> > > +static int __init devsec_tsm_init(void)
> > > +{
Ok. I guess in emulation that's a reasonable compromise.  Maybe leave
a comment somewhere to avoid repeat of this feedback.

Jonathan

>

---

## [31] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

Jonathan Cameron wrote:
> 
> +CC Gerd, of off chance we can use a Redhat PCI device ID for kernel
[..]
> > > Emulating something real?  If not maybe we should get an ID from another space
> > > (or reserve this one ;)  

About the same level of difficulty...

> Or maybe we can ask for one of the Redhat ones (maintained by Gerd).

In the meantime I added this to the Kconfig because I also received a
report of an AMD platform being confused about this extra PCI domain.
This protects against allyesconfig builds autoloading this thing which
should only be used with unit tests.

diff --git a/samples/Kconfig b/samples/Kconfig
index 8441593fb654..9ad822d4e808 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -327,6 +327,7 @@ source "samples/damon/Kconfig"
 
 config SAMPLE_DEVSEC
 	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
+	depends on m
 	depends on PCI
 	depends on VIRT_DRIVERS
 	depends on PCI_DOMAINS_GENERIC || X86
@@ -339,7 +340,11 @@ config SAMPLE_DEVSEC
 	  devsec_bus and devsec_tsm, exercise device-security enumeration, PCI
 	  subsystem use ABIs, device security flows. For example, exercise IDE
 	  (link encryption) establishment and TDISP state transitions via a
-	  Device Security Manager (DSM).
+	  Device Security Manager (DSM). Note the emulation uses a device-id
+	  (vendor: 0x8086 device: 0x7075) that is *assumed* unused and some
+	  architectures may be confused by this emulated PCI domain.
+
+	  If unsure, say N
 
 endif # SAMPLES
 
> 
> > 

I expect all the low-level tsm drivers will struggle with this, so
expect to see this pattern repeat outside of emulation.

---

## [32] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 06/10] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Jonathan Cameron wrote:
> On Thu, 17 Jul 2025 11:33:54 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Done.

---

## [33] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 06/10] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Jonathan Cameron wrote:
[..]
> > index 1b991a88c19c..2d49a4786a9f 100644
> > --- a/include/uapi/linux/pci_regs.h

Done.

---

## [34] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

Jonathan Cameron wrote:
[..]
> A few minor things inline.
[..]
> > +/**
> > + * pci_ide_stream_enable() - try to enable a Selective IDE Stream

ack.

[..]
> > diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
> > new file mode 100644

yes.

> > +/**
> > + * struct pci_ide - PCIe Selective IDE Stream descriptor

true.

> > + * @host_bridge_stream: track platform Stream ID
> > + * @stream_id: unique Stream ID (within Partner Port pairing)

Oh, true, I was going for a combo comment for nr_ide_streams and
ide_stream_map, but missed on the clarity. Make that relationship
clearer:

-       u8 nr_ide_streams;              /* Track available vs in-use streams */
+       u8 nr_ide_streams; /* Max streams possibly active in @ide_stream_map */

---

## [35] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 09/10] PCI/TSM: Report active IDE streams*

Jonathan Cameron wrote:
> On Thu, 17 Jul 2025 11:33:57 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:
[..]
> > diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
> > index 093824dc68dd..b0ef9089e0f2 100644

clang-format agrees.

> > +	if (rc == 0)
> > +		ide->tsm_dev = tsm_dev;

Switched to that.

> 
> > +	return rc;

Good catch, missed cleaning that up during development.

---

## [36] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

Xu Yilun wrote:
[..]
> > +	for_each_pci_dev(pdev)
> > +		if (is_pci_tsm_pf0(pdev))

Oh true, that comment is now stale with this new organization as probe
is only about setting up any context to allow future operations. Any
"readiness" is determined in those follow-on operations, not probe.
Updated the comment to:

        /*
         * struct pci_tsm_link_ops - Manage physical link and the TSM/DSM session
         * @probe: allocate context (wrap 'struct pci_tsm') for follow-on link
         *         operations
         * @remove: destroy link operations context

---

## [37] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

Jonathan Cameron wrote:
> > > You protect against this in the DEFINE_FREE() so probably safe
> > > to assume it is always set if we get here.  

...inspired by kfree(NULL). Potentially saves "if (tsm) tsm_remove(tsm)"
checks down the road, but yes, all of those are obviated by the
DEFINE_FREE() at present.

> > > > +	pdev = tsm->pdev;
> > > > +	tsm->ops->remove(tsm);

Here is new approach (only compile tested) after understanding that loop
declared variables do trigger cleanup on each iteration.

static void pci_tsm_walk_fns(struct pci_dev *pdev,
			     int (*cb)(struct pci_dev *pdev, void *data),
			     void *data)
{
	/* Walk subordinate physical functions */
	for (int i = 0; i < 8; i++) {
		struct pci_dev *pf __free(pci_dev_put) = pci_get_slot(
			pdev->bus, PCI_DEVFN(PCI_SLOT(pdev->devfn), i));

		if (!pf)
			continue;

		/* on entry function 0 has already run @cb */
		if (i > 0)
			cb(pf, data);

		/* walk virtual functions of each pf */
		for (int j = 0; j < pci_num_vf(pf); j++) {
			struct pci_dev *vf __free(pci_dev_put) =
				pci_get_domain_bus_and_slot(
					pci_domain_nr(pf->bus),
					pci_iov_virtfn_bus(pf, j),
					pci_iov_virtfn_devfn(pf, j));

			if (!vf)
				continue;

			cb(vf, data);
		}
	}

	/*
	 * Walk downstream devices, assumes that an upstream DSM is
	 * limited to downstream physical functions
	 */
	if (pci_pcie_type(pdev) == PCI_EXP_TYPE_UPSTREAM && is_dsm(pdev))
		pci_walk_bus(pdev->subordinate, cb, data);
}

static void pci_tsm_walk_fns_reverse(struct pci_dev *pdev,
				     int (*cb)(struct pci_dev *pdev,
					       void *data),
				     void *data)
{
	/* Reverse walk downstream devices */
	if (pci_pcie_type(pdev) == PCI_EXP_TYPE_UPSTREAM && is_dsm(pdev))
		pci_walk_bus_reverse(pdev->subordinate, cb, data);

	/* Reverse walk subordinate physical functions */
	for (int i = 7; i >= 0; i--) {
		struct pci_dev *pf __free(pci_dev_put) = pci_get_slot(
			pdev->bus, PCI_DEVFN(PCI_SLOT(pdev->devfn), i));

		if (!pf)
			continue;

		/* reverse walk virtual functions */
		for (int j = pci_num_vf(pf) - 1; j >= 0; j--) {
			struct pci_dev *vf __free(pci_dev_put) =
				pci_get_domain_bus_and_slot(
					pci_domain_nr(pf->bus),
					pci_iov_virtfn_bus(pf, j),
					pci_iov_virtfn_devfn(pf, j));

			if (!vf)
				continue;
			cb(vf, data);
		}

		/* on exit, caller will run @cb on function 0 */
		if (i > 0)
			cb(pf, data);
	}
}

[..]
> I agree it's a slightly odd construction and so might cause confusion.
> So whilst I think I prefer it to the or_reset() pattern I guess I'll just

However, I am interested in these "the trouble with cleanup.h" style
discussions.

I recently suggested this [1] in another thread which indeed uses
multiple local variables of the same object to represent the different
phases of the setup. It was easier there because the code was
straigtforward to convert to an ERR_PTR() organization.

If there was already an alternative device_add() like this:

struct device *device_add_or_reset(struct device *dev)

That handled the put_device() then you could write:

struct device *devreg __free(device_unregister) = device_add_or_reset(no_free_ptr(dev))

...and help that common pattern of 'struct device' setup transitions
from put_device() to device_unregister() at device_add() time.

[1]: http://lore.kernel.org/688bcf40215c3_48e5100d6@dwillia2-xfh.jf.intel.com.notmuch

[..]
> > > > + * struct pci_tsm_ops - manage confidential links and security state
> > > > + * @link_ops: Coordinate PCIe SPDM and IDE establishment via a platform TSM.

CXL could use it too...

---

## [38] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

Jonathan Cameron wrote:
[..]
> > > > diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> > > > new file mode 100644

I should have noted earlier that tsm_probe() on subfunctions might fail
without failing the 'connect' operation and unwinding the subfunctions
that did probe successfully. tsm_probe() should rarely fail, it is just
subject to kmalloc(GFP_KERNEL) failure in most cases.

So at shutdown time tsm_remove() will opportunistically cleanup just the
subfunctions that probed.

---

## [39] Jonathan Cameron — 2025-08-07
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

> > > > > +	pdev = tsm->pdev;
> > > > > +	tsm->ops->remove(tsm);

Looks good.


> 
> [..]

That's definitely interesting (in a fairly good way) as anything to stop people
introducing bugs around the device_add() stuff would be welcome.  It'll take a bit
of getting used to though.  Maybe make it more explicit device_add_or_put()?

Naming hard as normal..
> 
Jonathan

---

## [40] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Thu, Jul 17, 2025 at 11:33:50AM -0700, Dan Williams wrote:
> Link encryption is a new PCIe feature enumerated by "PCIe 6.2 section
> 7.9.26 IDE Extended Capability".

> +++ b/drivers/pci/ide.c
> @@ -0,0 +1,93 @@

Trend is to alphabetize these.  And I think there should be more
#includes here instead of using other things pulled in indirectly:

  https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/process/submit-checklist.rst?id=v6.16#n17

> +++ b/include/uapi/linux/pci_regs.h

> +#define  PCI_IDE_CAP_ALG_MASK		__GENMASK(12, 8) /* Supported Algorithms */
> +#define  PCI_IDE_CAP_ALG_AES_GCM_256	0    /* AES-GCM 256 key size, 96b MAC */

I'm totally OK with dropping the "_MASK" suffix since I think uses are
completely readable without it, especially with __GENMASK()/FIELD_GET()/
FIELD_PREP().

---

## [41] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 03/10] PCI: Introduce pci_walk_bus_reverse(),
 for_each_pci_dev_reverse()*

On Thu, Jul 17, 2025 at 11:33:51AM -0700, Dan Williams wrote:
> PCI/TSM, the PCI core functionality for the PCIe TEE Device Interface
> Security Protocol (TDISP), has a need to walk all subordinate functions of

s/SRIOV/SR-IOV/

> In error scenarios or when a TEE Security Manager (TSM) device is removed
> it needs to unwind all established DSM contexts.

I really don't like these search and iterator interfaces.  I wish we
didn't need them like this because code that uses them becomes a
one-time thing that doesn't handle hotplug and has potential locking
and race issues.  But I assume you really do need these.

> +++ b/drivers/base/bus.c
> +static struct device *prev_device(struct klist_iter *i)

I think this would be simpler as:

  if (!n)
    return NULL;

  dev_prv = to_device_private_bus(n);
  return dev_prv->device;

> +++ b/drivers/pci/bus.c
> +static int __pci_walk_bus_reverse(struct pci_bus *top,

Why not:

  list_for_each_entry_reverse(...) {
    ...
    if (ret)
      return ret;
  }
  return 0;

---

## [42] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

On Thu, Jul 17, 2025 at 11:33:52AM -0700, Dan Williams wrote:
> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This

Previous patches reference PCIe r6.2.  Personally I would change them
all the citations to r7.0, since that's out now and (I assume)
includes everything.  I guess you said "introduced in r6.1," which is
not the same as "introduced in r7.0," but I'm not sure how relevant it
is to know that very first revision.

> The operations that can be executed against a PCI device are split into
> 2 mutually exclusive operation sets, "Link" and "Security" (struct

s/2/two/  Old skool, but you obviously pay attention to details like
that :)

> +++ b/Documentation/ABI/testing/sysfs-bus-pci
> +What:		/sys/bus/pci/devices/.../tsm/

s/never have one,/never have one;/

> +++ b/drivers/pci/tsm.c
> +#define dev_fmt(fmt) "TSM: " fmt

Include "PCI" for context?

> + * Provide a read/write lock against the init / exit of pdev tsm
> + * capabilities and arrival/departure of a tsm instance

s/tsm/TSM/ in comments.

> +static void pci_tsm_walk_fns(struct pci_dev *pdev,
> +			     int (*cb)(struct pci_dev *pdev, void *data),

What's the difference between all this and just pci_walk_bus() of
pdev->subordinate?  Are VFs not included in that walk?  Maybe a
hint here would be useful.

> +static int pci_tsm_connect(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
> +{

Makes me wonder what happens if a device is hot-added in the
hierarchy.  I guess nothing.  Is that what we want?  What would be the
flow if we *did* want to do something?  I guess disconnect and connect
again?

> + * Find the PCI Device instance that serves as the Device Security
> + * Manger (DSM) for @pdev. Note that no additional reference is held for

s/Manger/Manager/

> +	 * For cases where a switch may be hosting TDISP services on
> +	 * behalf of downstream devices, check the first usptream port

s/usptream/upstream/

> +++ b/include/linux/pci-tsm.h
> + * struct pci_tsm_ops - manage confidential links and security state

s/phyiscal/physical/

> +struct pci_tsm_ops {
> +	/*

s/tsm link/TSM link/

> +	 * struct pci_tsm_security_ops - Manage the security state of the function
> +	 * @sec_probe: probe device for tsm security operation

s/for tsm/for TSM/

> + * struct pci_tsm - Core TSM context for a given PCIe endpoint
> + * @pdev: Back ref to device function, distinguishes type of pci_tsm context

Extra period at end, unlike others.

> + * @ops: Link Confidentiality or Device Function Security operations

> +static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
> +{

What exactly is a "switch Downstream Endpoint"?  Do you mean a "Switch
Downstream Port"?  Or an Endpoint that is downstream of a Switch?

Bjorn

---

## [43] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

On Thu, Jul 17, 2025 at 11:33:53AM -0700, Dan Williams wrote:
> Establish just enough emulated PCI infrastructure to register a sample
> TSM (platform security manager) driver and have it discover an IDE + TEE

s/existing a/existing/

> The devsec_tsm driver responds to the PCI core TSM operations as if it
> successfully exercised the given interface security protocol message.

Most of these messages don't seem relevant to DSM/TDISP/etc.  It
*would* be useful to have a hint about what specifically makes this an
IDE + TEE device.  Capability visible via lspci?  Are devices at both
ends required, e.g., a Root Port and an Endpoint?

Oooh, I see (finally).  This hierarchy is all totally fabricated, no
actual hardware involved at all.  You did say that above; it just took
a while to sink in.

>  # modprobe devsec_tsm
>     devsec_tsm_pci_probe: pci 10000:01:00.0: devsec: tsm enabled

s/tsm/TSM/ in the message
s/ide/IDE/
s/tee/TEE/

Looks like spurious spaces inside parens?

> + * The expectation is the helpers referenceed are convenience "library"

s/referenceed/referenced/

---

## [44] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 06/10] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Thu, Jul 17, 2025 at 11:33:54AM -0700, Dan Williams wrote:
> PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
> enumerates new link capabilities and status added for Gen 6 devices. One

s/ added for Gen 6 devices//

I know the "Gen 6 device" terminology is pervasive, but the spec
suggests avoiding it because it's so ambiguous.

> of the link details enumerated in that register block is the "Segment
> Captured" status in the Device Status 3 register. That status is

So far this mentions a lot of facts, but only the subject hints at
what it does.  I guess it just captures the Flit Mode status, inferred
by Segment Captured?

I'm OK with basically just saying *that*, and moving some of the
implications to places where we depend on them.

> Cc: Lukas Wunner <lukas@wunner.de>
> Cc: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>

---

## [45] dan.j.williams@intel.com — 2025-08-07
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

Bjorn Helgaas wrote:
> On Thu, Jul 17, 2025 at 11:33:50AM -0700, Dan Williams wrote:
> > Link encryption is a new PCIe feature enumerated by "PCIe 6.2 section

In this case I think it was only missing a:

#include <linux/pci_regs.h>

...but more includes are needed in follow-on patches. Added those and
alphabetized.

> 
> > +++ b/include/uapi/linux/pci_regs.h

Sounds good, and helps with the column width pressure. There might be
isolated cases of "mask vs value" confusion, but I think proximity to
FIELD_PREP()/FIELD_GET(), like you say, makes this clear.

---

## [46] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

On Thu, Jul 17, 2025 at 11:33:55AM -0700, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into

IIUC this patch doesn't actually add this as a "flow"; it adds these
interfaces, and I guess it's up to callers to use them in a way that
establishes this flow.

Maybe indent a couple spaces and add blank lines between them?

> In support of system administrators auditing where platform, Root Port,
> and Endpoint IDE stream resources are being spent, the allocated stream

> +++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
> +What:		pciDDDD:BB/streamH.R.E

s/tsm/TSM/
s/endpoint/Endpoint/

For "(H)ost bridge", "(R)oot Port",

  - Could use "Host bridge (H)", etc, which makes spell checkers work
    better (trivial, I know)

  - What's the format of these parts?  From the patch (and the commit
    log), it looks like they're decimal stream index values?  (I don't
    know enough to know what stream index values are, but presumably
    users will.)

> +++ b/drivers/pci/ide.c
> +int pci_ide_domain(struct pci_dev *pdev)

Not mentioned in commit log.  Maybe it doesn't need to be.  The only
call I see is in this file, so it looks like it could even be static.

> +/**
> + * pci_ide_stream_enable() - try to enable a Selective IDE Stream

Do or do not.  There is no try.

> + * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
> + * @ide: registered and setup IDE settings descriptor

Maybe recast this as "Return:" instead of "report whether ..."  At
least, I assume this reporting is done via the return value.

> + */
> +int pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide)

> +++ b/include/linux/pci-ide.h
> + * struct pci_ide_partner - Per port pair Selective IDE Stream settings

Wrap to fit in 80 columns like the rest of the file.  Add "()" after
function name (below too).  Jonathan mentioned the "parnter".

> + * @enable: flag whether to run pci_ide_stream_disable for this parnter slot

---

## [47] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Thu, Jul 17, 2025 at 11:33:50AM -0700, Dan Williams wrote:
> Link encryption is a new PCIe feature enumerated by "PCIe 6.2 section
> 7.9.26 IDE Extended Capability".

Acked-by: Bjorn Helgaas <bhelgaas@google.com>

> +++ b/drivers/pci/Kconfig
> @@ -122,6 +122,20 @@ config XEN_PCIDEV_FRONTEND

Maybe worth expanding IDE once as we did for DOE:

> +
>  config PCI_DOE

---

## [48] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 06/10] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Thu, Jul 17, 2025 at 11:33:54AM -0700, Dan Williams wrote:
> PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
> enumerates new link capabilities and status added for Gen 6 devices. One

Acked-by: Bjorn Helgaas <bhelgaas@google.com>

> ---
>  drivers/pci/probe.c           | 12 ++++++++++++

---

## [49] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

On Thu, Jul 17, 2025 at 11:33:55AM -0700, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into

Acked-by: Bjorn Helgaas <bhelgaas@google.com>

> ---
>  .../ABI/testing/sysfs-devices-pci-host-bridge |  16 +

---

## [50] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 08/10] PCI/IDE: Report available IDE streams*

On Thu, Jul 17, 2025 at 11:33:56AM -0700, Dan Williams wrote:
> The limited number of link-encryption (IDE) streams that a given set of
> host bridges supports is a platform specific detail. Provide

Acked-by: Bjorn Helgaas <bhelgaas@google.com>

> ---
>  .../ABI/testing/sysfs-devices-pci-host-bridge | 13 ++++

---

## [51] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 09/10] PCI/TSM: Report active IDE streams*

On Thu, Jul 17, 2025 at 11:33:57AM -0700, Dan Williams wrote:
> Given that the platform TSM owns IDE Stream ID allocation, report the
> active streams via the TSM class device. Establish a symlink from the

Acked-by: Bjorn Helgaas <bhelgaas@google.com>

> ---
>  Documentation/ABI/testing/sysfs-class-tsm | 10 ++++++++

---

## [52] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Thu, Aug 07, 2025 at 03:37:36PM -0700, dan.j.williams@intel.com wrote:
> Bjorn Helgaas wrote:
> > On Thu, Jul 17, 2025 at 11:33:50AM -0700, Dan Williams wrote:

I assumed dev_fmt was used by dev_printk(), but didn't go back to
look.

---

## [53] dan.j.williams@intel.com — 2025-08-07
*Subject: Re: [PATCH v4 03/10] PCI: Introduce pci_walk_bus_reverse(),
 for_each_pci_dev_reverse()*

Bjorn Helgaas wrote:
> On Thu, Jul 17, 2025 at 11:33:51AM -0700, Dan Williams wrote:
> > PCI/TSM, the PCI core functionality for the PCIe TEE Device Interface

ack

> > In error scenarios or when a TEE Security Manager (TSM) device is removed
> > it needs to unwind all established DSM contexts.

The underlying assumption is that the first generation of TDISP capable
devices will have a Device Security Manager (DSM) for all the SR-IOV
virtual functions of the device, or the card will have an embedded PCIe
switch where the Upstream Switch Port has a Device Security Manager for
integrated Dowstream Endpoint functions in the card.

The expectation is that physical hotplug for these cases never happens
*within* a security domain. The entire physical function is removed and
by implication all the functions the DSM watches over.

However, this does highlight a miss for logical hotplug of VFs. This
enabling wants to have sriov_init() check if the PF is connected to a
TSM and if so perform a late pdev->tsm->ops->probe() to setup any
context needed to allow the VF to go through secure-device-assignment. I
will add that for the next version.

The reverse is already there... any TSM context for to-be-removed VFs is
cleaned up.

> 
> > +++ b/drivers/base/bus.c

Agree, in isolation, but next to next_device() the style looks odd. So,
go back and style-fix code from 2008, or make 2025 code look like 2008
code is the choice.

> 
> > +++ b/drivers/pci/bus.c

Again, for conformance to existing style of __pci_walk_bus(). Want a
lead-in cleanup for that?

---

## [54] Bjorn Helgaas — 2025-08-07
*Subject: Re: [PATCH v4 03/10] PCI: Introduce pci_walk_bus_reverse(),
 for_each_pci_dev_reverse()*

On Thu, Aug 07, 2025 at 04:17:54PM -0700, dan.j.williams@intel.com wrote:
> Bjorn Helgaas wrote:
> > On Thu, Jul 17, 2025 at 11:33:51AM -0700, Dan Williams wrote:

> > > +++ b/drivers/base/bus.c
> > > +static struct device *prev_device(struct klist_iter *i)

Good point, I didn't look around at that code.  Following the existing
style seems right to me.

> > > +++ b/drivers/pci/bus.c
> > > +static int __pci_walk_bus_reverse(struct pci_bus *top,

Don't bother.  Maybe some janitor will show up and do it eventually.

Bjorn

---

## [55] dan.j.williams@intel.com — 2025-08-07
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

Bjorn Helgaas wrote:
> On Thu, Aug 07, 2025 at 03:37:36PM -0700, dan.j.williams@intel.com wrote:
> > Bjorn Helgaas wrote:

Yes, but it is interesting from a "include what you use" perspective.
This file is only using pci_info() defined in pci.h. It just so happens
that pci_info() is a wrapper for dev_info(). So it is a bit of a
layering violation to know that dev_fmt can be used to prefix
pci_<level> messages and must be defined before any include.

I could add a pci_fmt, but it would need to accommodate these too:

drivers/pci/pcie/aer.c:15:#define pr_fmt(fmt) "AER: " fmt
drivers/pci/pcie/aer.c:16:#define dev_fmt pr_fmt
drivers/pci/pcie/dpc.c:9:#define dev_fmt(fmt) "DPC: " fmt
drivers/pci/pcie/edr.c:9:#define dev_fmt(fmt) "EDR: " fmt
drivers/pci/pcie/err.c:13:#define dev_fmt(fmt) "AER: " fmt
drivers/pci/pcie/pme.c:10:#define dev_fmt(fmt) "PME: " fmt

---

## [56] Arto Merilainen — 2025-08-08
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

On 17.7.2025 21.33, Dan Williams wrote:
> +static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide, int pos,
> +			    bool enable)

If I recall correctly, setting the DEFAULT bit is allowed only for one 
SEL_SID instance at a time. If we consider the root port, wouldn't this 
prevent having multiple IDE capable devices under the same RP?

> +		  FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, pdev->ide_cfg) |
> +		  FIELD_PREP(PCI_IDE_SEL_CTL_TEE_LIMITED, pdev->ide_tee_limit) |

The first revision of this patch had address association register 
programming but it has since been removed. Could you comment if there is 
a reason for this change?

Some background: This might be problematic for ARM CCA. I recall seeing 
a comment stating that the address association register programming can 
be skipped on some architectures (e.g., apparently AMD uses a separate 
table that contains the StreamID) but on ARM CCA the StreamID 
association AFAIK happens through these registers.

- R2

---

## [57] Bjorn Helgaas — 2025-08-08
*Subject: Re: [PATCH v4 02/10] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Thu, Aug 07, 2025 at 07:17:11PM -0700, dan.j.williams@intel.com wrote:
> Bjorn Helgaas wrote:
> > On Thu, Aug 07, 2025 at 03:37:36PM -0700, dan.j.williams@intel.com wrote:

Seems like too much.  You used pci_info(), which is supplied by
<linux/pci.h>, so I think that's enough.  I would say it's pci.h's
responsibility to include things *it* depends on.  I didn't realize
how little was actually in ide.c at this point.

Bjorn

---

## [58] dan.j.williams@intel.com — 2025-08-08
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

Arto Merilainen wrote:
> On 17.7.2025 21.33, Dan Williams wrote:
> > +static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide, int pos,

True, I'll drop this from the next version. We can circle back to this
when ATS is considered, but that is not in scope for initial enabling.

> > +		  FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, pdev->ide_cfg) |
> > +		  FIELD_PREP(PCI_IDE_SEL_CTL_TEE_LIMITED, pdev->ide_tee_limit) |

We chatted about it around this point in the original review thread [1].
tl;dr SEV-TIO and TDX Connect did not see a strict need for it. However,
the expectation was always to circle back and revive it if it turned out
later to be required.

[1]: http://lore.kernel.org/67bcf19bd1c7a_1c530f29449@dwillia2-xfh.jf.intel.com.notmuch

> Some background: This might be problematic for ARM CCA. I recall seeing 
> a comment stating that the address association register programming can 

Can you confirm and perhaps work with Aneesh to propose an incremental
patch to add that support back? It might be something that we let the
low level TSM driver control. Like an additional address association
object that can be attached to 'struct pci_ide' by the low level TSM
driver.

The messy part is sparse device MMIO layout vs limited association
blocks and this is where SEV-TIO and TDX Connect have other mechanisms
to do that stream-id association.

---

## [59] dan.j.williams@intel.com — 2025-08-08
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

Bjorn Helgaas wrote:
> On Thu, Jul 17, 2025 at 11:33:52AM -0700, Dan Williams wrote:
> > The PCIe 6.1 specification, section 11, introduces the Trusted Execution

Ack, looks like the section numbers have not changed which makes it easier.

> > The operations that can be executed against a PCI device are split into
> > 2 mutually exclusive operation sets, "Link" and "Security" (struct

I only recently gave up the fight against 2^H^H two spaces after a
period, fixed.

> > +++ b/Documentation/ABI/testing/sysfs-bus-pci
> > +What:		/sys/bus/pci/devices/.../tsm/

yes.

> 
> > +++ b/drivers/pci/tsm.c

Sure.

> 
> > + * Provide a read/write lock against the init / exit of pdev tsm

Got it.

> > +static void pci_tsm_walk_fns(struct pci_dev *pdev,
> > +			     int (*cb)(struct pci_dev *pdev, void *data),

Right, ->subordinate is only managed for actual bridge devices. PFs do
use one or more 'struct pci_bus *' instances for their VFs, but do not
set ->subordinate I assume becuase of that "or more" case. See the NULL
@bridge parameter to pci_add_new_bus() in virtfn_add_bus(). With that
there is no clean way I see to walk all the virtfn buses of a PF, so
fall back to a pci_get_domain_bus_and_slot() walk.

I will add a note to this effect as I had to do some digging here to be
sure.

> > +static int pci_tsm_connect(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
> > +{

If a subfunction is found after the 'connect' event, like late enable of
SR-IOV capability, then the resulting pci_device_add() for that should
lookup and perform the ->probe() at that time.

> > + * Find the PCI Device instance that serves as the Device Security
> > + * Manger (DSM) for @pdev. Note that no additional reference is held for

...could have swore I ran checkpatch, but indeed it flags this.

Fixed, along with the others.
 
> > +struct pci_tsm_ops {
> > +	/*

Fixed the above.

> 
> > + * @ops: Link Confidentiality or Device Function Security operations

Endpoint that is downstream of a Switch. I will clarify the comment.

---

## [60] dan.j.williams@intel.com — 2025-08-08
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

Bjorn Helgaas wrote:
> On Thu, Jul 17, 2025 at 11:33:53AM -0700, Dan Williams wrote:
> > Establish just enough emulated PCI infrastructure to register a sample

Fixed.

> 
> > The devsec_tsm driver responds to the PCI core TSM operations as if it

Yeah, there are so many moving parts to this that I do not feel
comfortable leaving 100% of the testing to hardware. This is faster to
prototype than teaching QEMU to emulate all the pieces here.

> 
> >  # modprobe devsec_tsm

Fixed.

> 
> Looks like spurious spaces inside parens?

Yeah just to avoid extra code to elide the separator, but easy enough to
fixup.

> > + * The expectation is the helpers referenceed are convenience "library"
> 

Got it, checkpatch misses this one.

---

## [61] dan.j.williams@intel.com — 2025-08-08
*Subject: Re: [PATCH v4 06/10] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Bjorn Helgaas wrote:
> On Thu, Jul 17, 2025 at 11:33:54AM -0700, Dan Williams wrote:
> > PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,

Ok.

> 
> > of the link details enumerated in that register block is the "Segment

Agree, too wordy. Trimmed to:

PCIe r7.0 Section 7.7.9 Device 3 Extended Capability Structure, defines the
canonical location for determining the Flit Mode of a device. This status
is a dependency for PCIe IDE enabling. Add a new fm_enabled flag to 'struct
pci_dev'.

---

## [62] dan.j.williams@intel.com — 2025-08-08
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

Bjorn Helgaas wrote:
> On Thu, Jul 17, 2025 at 11:33:55AM -0700, Dan Williams wrote:
> > There are two components to establishing an encrypted link, provisioning

Right, common helpers for low-level TSM drivers to use with an example
of such a driver (without all the arch specific complexities) in
samples/devsec/.

> Maybe indent a couple spaces and add blank lines between them?

Ok.

> 
> > In support of system administrators auditing where platform, Root Port,

I clarified that a bit:

"A stream consumes a Stream ID slot in each of the Host bridge (H), Root
Port (R) and Endpoint (E)"

Presumably users that are debugging why they are unable to establish any
more streams can use this to discover, for example, "oh, I have resources available
in my Host Bridge and Endpoint, but the Root Port is out of Stream
slots".

> 
> > +++ b/drivers/pci/ide.c

True, not sure why I thought this would be consumed by TSM drivers.
Fixed.

> 
> > +/**

Ha! It does always enable, it just may immediately transition to the
error state if one of the partners is upset about something.

> > + * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
> > + * @ide: registered and setup IDE settings descriptor

Yup, that is better.

> 
> > + */

Done.

---

## [63] Arto Merilainen — 2025-08-11
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

On 8.8.2025 20.26, dan.j.williams@intel.com wrote:
> Arto Merilainen wrote:
>> The first revision of this patch had address association register

Thank you for the reference. I suppose it is ok to rely on the default 
streams on the first iteration, and add a follow-up patch in the ARM CCA 
device assignment support series in case it is the only architecture 
that depends on them.

> 
>> Some background: This might be problematic for ARM CCA. I recall seeing

Aneesh, could you perhaps extend the IDE driver by adding the RP address 
association register programming in the next revision of the DA support 
series?

I think the EP side programming won't be relevant until we get to the 
P2P use-cases.

> 
> The messy part is sparse device MMIO layout vs limited association

Despite the potential sparsity, I think there needs to be only three 
address association register blocks per SEL_IDE block: The routing is 
based on the type-1 configuration space header which defines only three 
ranges (32bit BAR, 64bit BAR, IO). When enabling IDE between an RP and 
an EP, the SEL_IDE address association registers in the RP can be 
programmed with the same ranges used in the type-1 header in the switch 
upstream from the EP.

That said, if the RP implements less than three address association 
registers per SEL_SID, this scheme won't work.

(I vaguely recall that the PCIe spec might forbid IORd/IOWr TLPs when 
selective IDE streams are used so the limit might in fact be two instead 
three...)

- R2

---

## [64] Gerd Hoffmann — 2025-08-11
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

On Wed, Aug 06, 2025 at 11:33:18AM -0700, dan.j.williams@intel.com wrote:
> Jonathan Cameron wrote:
> > 

Well, they are meant for virtual devices emulated by qemu (and the
registry is docs/specs/pci-ids.rst in the qemu repo).

We made exceptions to that rule before (linux/samples/vfio-mdev/mdpy.c
got one for example).  So feel free to try sending a patch with an
update to qemu-devel.  There should be a /good/ explanation why you want
go that route, and "I'm to lazy to get one from my employer" is not what
I'd consider "good".  Also it's qemu release freeze and vacation season
right now, so don't expect this process to be fast.

take care,
  Gerd

---

## [65] dan.j.williams@intel.com — 2025-08-11
*Subject: Re: [PATCH v4 05/10] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

Gerd Hoffmann wrote:
> On Wed, Aug 06, 2025 at 11:33:18AM -0700, dan.j.williams@intel.com wrote:
> > Jonathan Cameron wrote:

Thanks for the details Gerd. IIUC that samples/vfio-mdev/ example is for
a functional use case. samples/devsec/ is not a functional use case. It
does not need an exclusive id to enable some limited unit testing. If
samples/devsec/ ever causes real world conflict the resolution is turn
it off / refrain from loading it.

---

## [66] Alexey Kardashevskiy — 2025-08-13
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

On 18/7/25 04:33, Dan Williams wrote:
> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This

Why is id needed here? Are there going to be multiple DSMs per a PCI device?

I am missing the point of tsm_dev. It does not have sysfs nodes (the pci_dev parent does), tsm_register() takes attribute_group but what would posibbly go there? certificates/meas/report blobs? The pci_dev struct itself has *tsm now so this child device is not that. Hm.


> +	if (rc != 1)
> +		return -EINVAL;

When PCI TSM loads, all it does is add "connect" nodes. And when write to "connect" happens, this find_tsm_dev() is expected to find a tsm_dev but what is going to add those in the real PCI? devsec_tsm_probe() does not really explain.

> +	if (!tsm_dev)
> +		return -ENXIO;

imho "echo 0 > connect" is more descriptive than "echo 1 > disconnect", and one less sysfs node.


> +
> +static bool pci_tsm_pf0_group_visible(struct kobject *kobj)

These should go down, right before "return 0". Thanks,


> +	tsm->dsm = find_dsm_dev(pdev);
> +	if (!tsm->dsm) {

---

## [67] dan.j.williams@intel.com — 2025-08-13
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
> On 18/7/25 04:33, Dan Williams wrote:
[..]
> > diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> > new file mode 100644
[..]
> > +static ssize_t connect_store(struct device *dev, struct device_attribute *attr,
> > +			     const char *buf, size_t len)

The implementation allows for multiple TSMs per platform [1], and you
acknowledged this earlier [2] (at least the "no globals" bit).

[1]: http://lore.kernel.org/683f9e141f1b1_1626e1009@dwillia2-xfh.jf.intel.com.notmuch

[2]: http://lore.kernel.org/b281b714-5097-4b3a-9809-7bdcb9e004dc@amd.com

One of the nice properties of multiple tsm_devs is the ability to unit test
host and guest side TSM flows in the same kernel image.

> I am missing the point of tsm_dev. It does not have sysfs nodes (the
> pci_dev parent does)

The resource accounting symlinks for each each IDE stream point to the
tsm_dev, see tsm_ide_stream_register().

> tsm_register() takes attribute_group but what would posibbly go there?

Any vendor specific implementation of commonly named attributes.
Contrast that with vendor specific attributes with vendor specific names
that the vendor specific device publishes.

> certificates/meas/report blobs?

Perhaps. For now, I want to just focus on the mechanics of the getting a
TDI into the run state. The attestation flow is a separate design debate
one there is consensus on getting the TDI up and running.

> The pci_dev struct itself has *tsm now so this child device is not
> that. Hm.

This tsm_dev is not a child device it is the common class representation
of a platform capability that can establish SPDM and optionally IDE.

> > +	if (rc != 1)
> > +		return -EINVAL;

sev_tsm_init() calls tsm_register(). Userspace catches the tsm_dev
KOBJECT_ADD event to run:

echo $TSM_DEV > /sys/bus/pci/devices/$PDEV/tsm/connect

[..]
> imho "echo 0 > connect" is more descriptive than "echo 1 > disconnect", and one less sysfs node.

That makes it a bit too ambiguous for my taste as connect is "connect to
a tsm of the following identifier", so, for example, "is '0' a shorthand
for 'tsm0'?"

...and as I say that I realize disconnect as the same problem.  I will
update disconnect to take the tsm device name just like connect for
symmetry, this ambiguity concern, and in case multiple TSM connections
per device might ever happen way down the road.

[..]
> > +/**
> > + * pci_tsm_constructor() - base 'struct pci_tsm' initialization

Sure, makes sense.

In practice @tsm will be unwound, but might as well not make it a
valid object while it is awaiting to be freed.

---

## [68] Alexey Kardashevskiy — 2025-08-15
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

On 14/8/25 11:40, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>> On 18/7/25 04:33, Dan Williams wrote:

Right but I'd think that devices (or, more precisely, PCIe slots) are statically assigned to TSMs. A bit hard to imagine 2 TSMs in a system and ability to connect some PCI device to either of those. It is not impossible but not exactly "painfully simple".


> [2]: http://lore.kernel.org/b281b714-5097-4b3a-9809-7bdcb9e004dc@amd.com
> 

Hm. Those groups are per a TSM so no device's certificates/meas/report blobs there, right?

> For now, I want to just focus on the mechanics of the getting a
> TDI into the run state. The attestation flow is a separate design debate

Yeah, I realized that soon after I hit "send".


>>> +	if (rc != 1)
>>> +		return -EINVAL;

Nah, ignore my "imho" then. Thanks,


> ...and as I say that I realize disconnect as the same problem.  I will
> update disconnect to take the tsm device name just like connect for

---

## [69] dan.j.williams@intel.com — 2025-08-18
*Subject: Re: [PATCH v4 04/10] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
> 
> 

The simple case is the typical case, single TSM. If a platform invents
multiple TSMs then it needs to define a protocol for userspace to figure
out the rules, like "match TSMs to devices by PCIe Segment Number", or
something similar. "Painfully simple" also means not pre-constraining
the ABI just to mitigate future userspace complexity. In the end the
kernel is allowed to not need / have an opinion about this detail.

> > [2]: http://lore.kernel.org/b281b714-5097-4b3a-9809-7bdcb9e004dc@amd.com
> > 

True, I was thinking of a per-device TSM driver supplied attributes
similar to 'struct device_driver'::dev_groups. Both that, and this
@groups parameter to tsm_register() can wait until a solid use case
arrives.

---

## [70] Aneesh Kumar K.V — 2025-08-28
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

Arto Merilainen <amerilainen@nvidia.com> writes:

> On 8.8.2025 20.26, dan.j.williams@intel.com wrote:
>> Arto Merilainen wrote:

Sure, I can add that change as part of next update. 

>
> I think the EP side programming won't be relevant until we get to the

---

## [71] Aneesh Kumar K.V — 2025-09-11
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> Arto Merilainen <amerilainen@nvidia.com> writes:
>

This is the change I am adding

 drivers/pci/ide.c                        | 128 ++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/arm-cca.c |  13 +++
 include/linux/pci-ide.h                  |   7 ++
 3 files changed, 147 insertions(+), 1 deletion(-)

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 3f772979eacb..23d1712ba97a 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -101,7 +101,7 @@ void pci_ide_init(struct pci_dev *pdev)
 	pdev->ide_cap = ide_cap;
 	pdev->nr_link_ide = nr_link_ide;
 	pdev->nr_sel_ide = nr_streams;
-	pdev->nr_ide_mem = nr_ide_mem;
+	pdev->nr_ide_mem = min(nr_ide_mem, PCI_IDE_AASOC_REG_MAX);
 }
 
 struct stream_index {
@@ -213,11 +213,13 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 				.rid_start = pci_dev_id(rp),
 				.rid_end = pci_dev_id(rp),
 				.stream_index = no_free_ptr(ep_stream)->stream_index,
+				.nr_mem = 0,
 			},
 			[PCI_IDE_RP] = {
 				.rid_start = pci_dev_id(pdev),
 				.rid_end = rid_end,
 				.stream_index = no_free_ptr(rp_stream)->stream_index,
+				.nr_mem = 0,
 			},
 		},
 		.host_bridge_stream = no_free_ptr(hb_stream)->stream_index,
@@ -228,6 +230,109 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_alloc);
 
+static int add_range_merge_overlap(struct range *range, int az, int nr_range,
+				   u64 start, u64 end)
+{
+	int i;
+
+	if (start >= end)
+		return nr_range;
+
+	/* get new start/end: */
+	for (i = 0; i < nr_range; i++) {
+
+		if (!range[i].end)
+			continue;
+
+		/* Try to add to the end */
+		if (range[i].end + 1 == start) {
+			range[i].end = end;
+			return nr_range;
+		}
+
+		/* Try to add to the start */
+		if (range[i].start == end + 1) {
+			range[i].start = start;
+			return nr_range;
+		}
+	}
+
+	/* Need to add it: */
+	return add_range(range, az, nr_range, start, end);
+}
+
+int pci_ide_add_address_assoc_block(struct pci_dev *pdev,
+				    struct pci_ide *ide,
+				    u64 start, u64 end)
+{
+	struct pci_ide_partner *partner;
+
+	if (!pci_is_pcie(pdev)) {
+		pci_warn_once(pdev, "not a PCIe device\n");
+		return -EINVAL;
+	}
+
+	switch (pci_pcie_type(pdev)) {
+	case PCI_EXP_TYPE_ENDPOINT:
+
+		if (pdev != ide->pdev)
+			return -EINVAL;
+		partner = &ide->partner[PCI_IDE_RP];
+		break;
+	default:
+		pci_warn_once(pdev, "invalid device type\n");
+		return -EINVAL;
+	}
+
+	if (partner->nr_mem >= pdev->nr_ide_mem)
+		return -ENOMEM;
+
+	partner->nr_mem = add_range_merge_overlap(partner->mem,
+					   PCI_IDE_AASOC_REG_MAX, partner->nr_mem,
+					   start, end);
+	return 0;
+}
+
+
+int pci_ide_merge_address_assoc_block(struct pci_dev *pdev,
+				      struct pci_ide *ide, u64 start, u64 end)
+{
+	struct pci_ide_partner *partner;
+
+	if (!pci_is_pcie(pdev)) {
+		pci_warn_once(pdev, "not a PCIe device\n");
+		return -EINVAL;
+	}
+
+	switch (pci_pcie_type(pdev)) {
+	case PCI_EXP_TYPE_ENDPOINT:
+
+		if (pdev != ide->pdev)
+			return -EINVAL;
+		partner = &ide->partner[PCI_IDE_RP];
+		break;
+	default:
+		pci_warn_once(pdev, "invalid device type\n");
+		return -EINVAL;
+	}
+
+	for (int i = 0; i < PCI_IDE_AASOC_REG_MAX; i++) {
+		struct range *r = &partner->mem[i];
+
+		if (r->start < start)
+			start = r->start;
+		if (r->end > end)
+			end = r->end;
+		r->start = 0;
+		r->end = 0;
+	}
+	partner->mem[0].start = start;
+	partner->mem[0].end = end;
+	partner->nr_mem = 1;
+
+	return 0;
+}
+
 /**
  * pci_ide_stream_free() - unwind pci_ide_stream_alloc()
  * @ide: idle IDE settings descriptor
@@ -424,6 +529,21 @@ void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
 
+	for (int i = 0; i < settings->nr_mem; i++) {
+		val = FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |
+			FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW,
+				   lower_32_bits(settings->mem[i].start)) |
+			FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW,
+				   lower_32_bits(settings->mem[i].end));
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), val);
+
+		val = upper_32_bits(settings->mem[i].end);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), val);
+
+		val = upper_32_bits(settings->mem[i].start);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), val);
+	}
+
 	/*
 	 * Setup control register early for devices that expect
 	 * stream_id is set during key programming.
@@ -453,6 +573,12 @@ void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
 	pos = sel_ide_offset(pdev, settings);
 
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
+	for (int i = settings->nr_mem - 1; i >= 0; i--) {
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), 0);
+	}
+
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, 0);
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, 0);
 	settings->setup = 0;
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index c9717698af56..28993f9277e4 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -137,6 +137,7 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 {
 	struct pci_dev *rp = pcie_find_root_port(pdev);
 	struct cca_host_pf0_dsc *dsc_pf0;
+	struct resource *res;
 	struct pci_ide *ide;
 	int rc, stream_id;
 
@@ -163,9 +164,21 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 	if (rc)
 		goto err_stream;
 
+	/*
+	 * Try to use the available address assoc register blocks.
+	 * If we fail with ENOMEM, create one block covering the entire
+	 * address range. (Should work for arm64)
+	 */
+	pci_dev_for_each_resource(pdev, res) {
+		rc = pci_ide_add_address_assoc_block(pdev, ide, res->start, res->end);
+		if (rc == -ENOMEM)
+			pci_ide_merge_address_assoc_block(pdev, ide, res->start, res->end);
+	}
+
 	pci_ide_stream_setup(pdev, ide);
 	pci_ide_stream_setup(rp, ide);
 
+
 	rc = tsm_ide_stream_register(ide);
 	if (rc)
 		goto err_tsm;
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index c3838d11af88..3d4f7f462a8d 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -19,6 +19,7 @@ enum pci_ide_partner_select {
 	PCI_IDE_HB = PCI_IDE_PARTNER_MAX,
 };
 
+#define PCI_IDE_AASOC_REG_MAX	6
 /**
  * struct pci_ide_partner - Per port pair Selective IDE Stream settings
  * @rid_start: Partner Port Requester ID range start
@@ -34,6 +35,8 @@ struct pci_ide_partner {
 	u8 stream_index;
 	unsigned int setup:1;
 	unsigned int enable:1;
+	int nr_mem;
+	struct range mem[PCI_IDE_AASOC_REG_MAX];
 };
 
 /**
@@ -60,6 +63,10 @@ struct pci_ide {
 
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide);
 struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
+int pci_ide_add_address_assoc_block(struct pci_dev *pdev,
+				    struct pci_ide *ide, u64 start, u64 end);
+int pci_ide_merge_address_assoc_block(struct pci_dev *pdev,
+				      struct pci_ide *ide, u64 start, u64 end);
 void pci_ide_stream_free(struct pci_ide *ide);
 int  pci_ide_stream_register(struct pci_ide *ide);
 void pci_ide_stream_unregister(struct pci_ide *ide);

---

## [72] dan.j.williams@intel.com — 2025-09-11
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V wrote:
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:
[..]
> >> Aneesh, could you perhaps extend the IDE driver by adding the RP address 
> >> association register programming in the next revision of the DA support 

Just thinking out loud...

I assume we will soon get to the point where at least one of the vendors
is ready to have their implementation pulled into tsm.git.

For truly vendor-specific bits that can be a pull request that I just
blindly pull. For core update proposals like this I expect it would be
best to cherry-pick those into the base at the next staging tree update.
This would be in support of prepping tsm.git (at least the base
infrastructure) for inclusion in linux-next.

As always, open to ideas on how to coordinate this.

In the meantime the tsm.git plan is to continue to rebase the base
infrastrcture branch until the review comments subside and all new
changes can be handled as incremental updates.

>  drivers/pci/ide.c                        | 128 ++++++++++++++++++++++-
>  drivers/virt/coco/arm-cca-host/arm-cca.c |  13 +++

Designated initializers already zero by default.

>  			},
>  			[PCI_IDE_RP] = {

How about:

pci_ide_associate_address()?

...because the result is not always a new block.

> +{
> +	struct pci_ide_partner *partner;

Is this really "merge", or "expand_to_fit" similar to
insert_resource_expand_to_fit()?

pci_ide_associate_address_force()? ...or am I reading it wrong?

[..]
> diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
> index c9717698af56..28993f9277e4 100644

How does this play with the "shared MSI-X MMIO" problem? Does this also
need to align with interface report expectations?

> +	}
> +

Where does 6 come from?

---
7.9.26.5.1 Selective IDE Stream Capability Register

The number of Selective IDE Address Association register blocks for a
given IDE Stream is hardware implementation specific, and is permitted
to be any number between 0 and 15.
---

Also, I would put this max in include/uapi/linux/pci_regs.h and match
the local naming.

---

## [73] Xu Yilun — 2025-09-25
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

> This is the change I am adding
> 

Can add_range_with_merge() serve your purpose?

> +
> +int pci_ide_add_address_assoc_block(struct pci_dev *pdev,

IIUC, you want to program the RP is it? So is it better we input the to
be programmed device (RP), not the target device (EP) with the range.

> +	default:
> +		pci_warn_once(pdev, "invalid device type\n");

I don't get why the desired number blocks for RP is related to the
supported number blocks for EP.

Apart from this, I don't see the necessary to input the EP device.

> +
> +	partner->nr_mem = add_range_merge_overlap(partner->mem,

IIUC, this function will merge previously added ranges, and the newly
input range, into one, which is wield to me as a kAPI.

> +
> +	return 0;

I noticed Arto has a good idea that there needs at most 2 blocks no
matter how the mmio layout is for PF/VF/MFD..., one for 32 bit, one for
64 bit. And the direct connected upstream bridge to the DSM device has
already aggregated the 2 ranges on enumeration. [1] That greatly reduces
the complexity. No need for callers to iterate the devices/resources to
collect the ranges again.

For TDX, the firmware enforces to setup only one addr block for RP, no
matter how many supported blocks the RP actually has. That means TDX
could only support 64 bit IDE ranges. I'd like to require an input
parameter like "max_nr_mem_rp" for this purpose.

Based on the above, I've found the only input from the caller is the
max_nr_mem_rp, how about we just add it in pci_ide_stream_alloc(),
input 0 if you don't need the addr block setup.

[...]

>  
> @@ -163,9 +164,21 @@ static int cca_tsm_connect(struct pci_dev *pdev)

You just input the addr of PF0, not VF/MFD... any limitation? If we
switch to get ranges from direct upstream bridge, are you still OK?

Thanks,
Yilun

---

## [74] Arto Merilainen — 2025-09-25
*Subject: Re: [PATCH v4 07/10] PCI/IDE: Add IDE establishment helpers*

On 25.9.2025 13.18, Xu Yilun wrote:
>> This is the change I am adding
>>

Should we use bus addresses while programming the ranges? The 32-bit 
ranges may be remapped (i.e. the range address doesn't match with the 
bus address).

> 
> I noticed Arto has a good idea that there needs at most 2 blocks no

I agree that the implementation feels unnecessarily complex given that 
the aggregated ranges are already available.

For reference, I am using a routine like this for collecting the ranges 
before programming the address association registers:

static int pci_res_to_ide_addr(struct pci_dev *pdev,
                                struct ide_addr_range *ide_addr)
{
         struct pci_dev *bridge = pci_upstream_bridge(pdev);
         struct pci_bus_region region;
         struct resource *res;
         int naddr = 0;

         res = &bridge->resource[PCI_BRIDGE_MEM_WINDOW];
         if (res->flags & IORESOURCE_MEM) {
                 pcibios_resource_to_bus(bridge->bus, &region, res);
                 ide_addr[naddr].start = region.start;
                 ide_addr[naddr].end = region.end;
                 naddr++;
         }

         res = &bridge->resource[PCI_BRIDGE_PREF_MEM_WINDOW];
         if (res->flags & IORESOURCE_PREFETCH) {
                 pcibios_resource_to_bus(bridge->bus, &region, res);
                 ide_addr[naddr].start = region.start;
                 ide_addr[naddr].end = region.end;
                 naddr++;
         }

         return naddr;
}

> For TDX, the firmware enforces to setup only one addr block for RP, no
> matter how many supported blocks the RP actually has. That means TDX

I do not think having only a limited number of addr blocks is unique to 
TDX. Given that the SW needs only a couple of addr blocks when 
programmed using the information in the type-1 header of the upstream 
bridge, I would expect hardware implementations to not have more blocks 
than necessary.

- R2

---
