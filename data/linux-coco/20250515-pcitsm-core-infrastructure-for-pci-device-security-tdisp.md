---
title: 'PCI/TSM: Core infrastructure for PCI device security (TDISP)'
date: 2025-05-15
last_reply: 2025-08-28
message_count: 173
participants: ['Dan Williams', 'Xu Yilun', 'kernel test robot', 'Alexey Kardashevskiy', 'Aneesh Kumar K.V', 'Suzuki K Poulose', 'Jason Gunthorpe', 'Jonathan Cameron']
---

## [1] Dan Williams — 2025-05-15

Changes since v2 [1]:
- drivers/virt/coco/guest rename merged to tsm.git#next
- Clarify usage and requirements for pci_ide_init_nr_streams() (Dionna)
- Misc fixups (Dionna)
- Fix sel_ide_offset() to incorporate ide_cap (Aneesh, Yilun)
- Allow at least 1 stream when enforcing uniform address association
  register layout (Yilun)
- Fix host-bridge-emulation for PCI_DOMAINS_GENERIC platform (Suzuki)
- Export pci_ide_to_settings() as a helper for TSM drivers (Yilun)
- Set Stream ID early, prior to IDE_KM (Alexey)
- Catch IDE_KM initial setup failures with pci_ide_stream_enable()
  errors (Yilun).
- Fix missing initialization of nr_link_ide (caught by
  samples/devsec/bus test)
- Add some reference documentation to the devsec_tsm_connect() sample
  operation to clarify implementation expectations (Zhi)
- Expand the possible Device Security Managers from only PF0 of a device
  hosting TDIs, to include Upstream Ports with downstream endpoints as
  TDIs
- Add bind, unbind, guest_req, and accept operations (Yilun)

[1]: http://lore.kernel.org/174107245357.1288555.10863541957822891561.stgit@dwillia2-xfh.jf.intel.com

Launch of tsm.git#staging [2]
-----------------------------
As mentioned on v2, tsm.git#staging is proposed as a neutral location to
collect device-security infrastructure from multiple vendors. I.e.
collect all the vendor trees to resolve conflicts, code or otherwise.
For now it does not contain kvm-coco-queue, but am open to merging that
if needed for some device-security-flows.

Yilun showed a potential flow for the end-to-end API changes here [1],
do review that and point out where it may not work for a different
architecture. A goal of mine is to catch sample/devsec/ up with that
diagram to prove out and unit test the end-to-end mechanism without
needing hardware. It has already found bugs while revising this new set.

[2]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging
[3]: http://lore.kernel.org/aCYsNSFQJZzHVOFI@yilunxu-OptiPlex-7050

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

The proposal is incrementally develop the shared infrastructure on top
of a sample TSM driver implementation to enable clean vendor agnostic
discussions about the commons. "samples/devsec/" is meant to be: just
enough emulation to exercise all the core infrastructure, a reference
implementation, and a simple unit test. The sample also enables
coordination with the native PCI device security effort [4].

[4]: http://lore.kernel.org/cover.1719771133.git.lukas@wunner.de

Dan Williams (11):
  coco/tsm: Introduce a core device for TEE Security Managers
  PCI/IDE: Enumerate Selective Stream IDE capabilities
  PCI/TSM: Authenticate devices via platform TSM
  PCI: Enable host-bridge emulation for PCI_DOMAINS_GENERIC platforms
  PCI: vmd: Switch to pci_bus_find_emul_domain_nr()
  samples/devsec: Introduce a PCI device-security bus + endpoint sample
  PCI: Add PCIe Device 3 Extended Capability enumeration
  PCI/IDE: Add IDE establishment helpers
  PCI/IDE: Report available IDE streams
  PCI/TSM: Report active IDE streams
  samples/devsec: Add sample IDE establishment

Xu Yilun (2):
  PCI/TSM: support TDI related operations for host TSM driver
  PCI/TSM: Add Guest TSM Support

 Documentation/ABI/testing/sysfs-bus-pci       |  45 +
 Documentation/ABI/testing/sysfs-class-tsm     |  20 +
 .../ABI/testing/sysfs-devices-pci-host-bridge |  51 ++
 MAINTAINERS                                   |   7 +-
 drivers/pci/Kconfig                           |  28 +
 drivers/pci/Makefile                          |   2 +
 drivers/pci/controller/pci-hyperv.c           |  53 +-
 drivers/pci/controller/vmd.c                  |  33 +-
 drivers/pci/ide.c                             | 525 ++++++++++++
 drivers/pci/pci-sysfs.c                       |   4 +
 drivers/pci/pci.c                             |  43 +-
 drivers/pci/pci.h                             |  19 +
 drivers/pci/probe.c                           |  34 +-
 drivers/pci/remove.c                          |   3 +
 drivers/pci/tsm.c                             | 782 ++++++++++++++++++
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/host/Kconfig                |   6 +
 drivers/virt/coco/host/Makefile               |   6 +
 drivers/virt/coco/host/tsm-core.c             | 144 ++++
 include/linux/pci-ide.h                       |  76 ++
 include/linux/pci-tsm.h                       | 211 +++++
 include/linux/pci.h                           |  29 +
 include/linux/tsm.h                           |  11 +
 include/uapi/linux/pci_regs.h                 |  91 +-
 samples/Kconfig                               |  16 +
 samples/Makefile                              |   1 +
 samples/devsec/Makefile                       |  10 +
 samples/devsec/bus.c                          | 711 ++++++++++++++++
 samples/devsec/common.c                       |  26 +
 samples/devsec/devsec.h                       |  40 +
 samples/devsec/tsm.c                          | 218 +++++
 32 files changed, 3170 insertions(+), 78 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 create mode 100644 drivers/pci/ide.c
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 drivers/virt/coco/host/Kconfig
 create mode 100644 drivers/virt/coco/host/Makefile
 create mode 100644 drivers/virt/coco/host/tsm-core.c
 create mode 100644 include/linux/pci-ide.h
 create mode 100644 include/linux/pci-tsm.h
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/tsm.c


base-commit: 7515f45c165269b72ee739e6fc26cc2ef928fc1b

---

## [2] Dan Williams — 2025-05-15
*Subject: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE Security Managers*

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
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm |  10 ++
 MAINTAINERS                               |   3 +-
 drivers/virt/coco/Kconfig                 |   2 +
 drivers/virt/coco/Makefile                |   1 +
 drivers/virt/coco/host/Kconfig            |   6 ++
 drivers/virt/coco/host/Makefile           |   6 ++
 drivers/virt/coco/host/tsm-core.c         | 112 ++++++++++++++++++++++
 include/linux/tsm.h                       |   5 +
 8 files changed, 144 insertions(+), 1 deletion(-)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 drivers/virt/coco/host/Kconfig
 create mode 100644 drivers/virt/coco/host/Makefile
 create mode 100644 drivers/virt/coco/host/tsm-core.c

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
new file mode 100644
index 000000000000..7503f04a9eb9
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -0,0 +1,10 @@
+What:		/sys/class/tsm/tsm0
+Date:		Dec, 2024
+Contact:	linux-coco@lists.linux.dev
+Description:
+		"tsm0" is a singleton device that represents the generic
+		attributes of a platform TEE Security Manager. It is a child of
+		the platform TSM device. /sys/class/tsm/tsm0/uevent
+		signals when the PCI layer is able to support establishment of
+		link encryption and other device-security features coordinated
+		through the platform tsm.
diff --git a/MAINTAINERS b/MAINTAINERS
index 0a1ca9233ccf..09bf7b45708b 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24555,12 +24555,13 @@ M:	David Lechner <dlechner@baylibre.com>
 S:	Maintained
 F:	Documentation/devicetree/bindings/trigger-source/pwm-trigger.yaml
 
-TRUSTED SECURITY MODULE (TSM) ATTESTATION REPORTS
+TRUSTED EXECUTION ENVIRONMENT SECURITY MANAGER (TSM)
 M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm-report
 F:	drivers/virt/coco/guest/
+F:	drivers/virt/coco/host/
 F:	include/linux/tsm.h
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 819a97e8ba99..14e7cf145d85 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -14,3 +14,5 @@ source "drivers/virt/coco/tdx-guest/Kconfig"
 source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
+
+source "drivers/virt/coco/host/Kconfig"
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 885c9ef4e9fc..73f1b7bc5b11 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -8,3 +8,4 @@ obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM_REPORTS)	+= guest/
+obj-y				+= host/
diff --git a/drivers/virt/coco/host/Kconfig b/drivers/virt/coco/host/Kconfig
new file mode 100644
index 000000000000..4fbc6ef34f12
--- /dev/null
+++ b/drivers/virt/coco/host/Kconfig
@@ -0,0 +1,6 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# TSM (TEE Security Manager) Common infrastructure and host drivers
+#
+config TSM
+	tristate
diff --git a/drivers/virt/coco/host/Makefile b/drivers/virt/coco/host/Makefile
new file mode 100644
index 000000000000..be0aba6007cd
--- /dev/null
+++ b/drivers/virt/coco/host/Makefile
@@ -0,0 +1,6 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# TSM (TEE Security Manager) Common infrastructure and host drivers
+
+obj-$(CONFIG_TSM) += tsm.o
+tsm-y := tsm-core.o
diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/host/tsm-core.c
new file mode 100644
index 000000000000..4f64af1a8967
--- /dev/null
+++ b/drivers/virt/coco/host/tsm-core.c
@@ -0,0 +1,112 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <linux/tsm.h>
+#include <linux/rwsem.h>
+#include <linux/device.h>
+#include <linux/module.h>
+#include <linux/cleanup.h>
+
+static DECLARE_RWSEM(tsm_core_rwsem);
+static struct class *tsm_class;
+static struct tsm_core_dev {
+	struct device dev;
+} *tsm_core;
+
+static struct tsm_core_dev *
+alloc_tsm_core(struct device *parent, const struct attribute_group **groups)
+{
+	struct tsm_core_dev *core = kzalloc(sizeof(*core), GFP_KERNEL);
+	struct device *dev;
+
+	if (!core)
+		return ERR_PTR(-ENOMEM);
+	dev = &core->dev;
+	dev->parent = parent;
+	dev->groups = groups;
+	dev->class = tsm_class;
+	device_initialize(dev);
+	return core;
+}
+
+static void put_tsm_core(struct tsm_core_dev *core)
+{
+	put_device(&core->dev);
+}
+
+DEFINE_FREE(put_tsm_core, struct tsm_core_dev *,
+	    if (!IS_ERR_OR_NULL(_T)) put_tsm_core(_T))
+struct tsm_core_dev *tsm_register(struct device *parent,
+				  const struct attribute_group **groups)
+{
+	struct device *dev;
+	int rc;
+
+	guard(rwsem_write)(&tsm_core_rwsem);
+	if (tsm_core) {
+		dev_warn(parent, "failed to register: %s already registered\n",
+			 dev_name(tsm_core->dev.parent));
+		return ERR_PTR(-EBUSY);
+	}
+
+	struct tsm_core_dev *core __free(put_tsm_core) =
+		alloc_tsm_core(parent, groups);
+	if (IS_ERR(core))
+		return core;
+
+	dev = &core->dev;
+	rc = dev_set_name(dev, "tsm0");
+	if (rc)
+		return ERR_PTR(rc);
+
+	rc = device_add(dev);
+	if (rc)
+		return ERR_PTR(rc);
+
+	tsm_core = no_free_ptr(core);
+
+	return tsm_core;
+}
+EXPORT_SYMBOL_GPL(tsm_register);
+
+void tsm_unregister(struct tsm_core_dev *core)
+{
+	guard(rwsem_write)(&tsm_core_rwsem);
+	if (!tsm_core || core != tsm_core) {
+		pr_warn("failed to unregister, not currently registered\n");
+		return;
+	}
+
+	device_unregister(&core->dev);
+	tsm_core = NULL;
+}
+EXPORT_SYMBOL_GPL(tsm_unregister);
+
+static void tsm_release(struct device *dev)
+{
+	struct tsm_core_dev *core = container_of(dev, typeof(*core), dev);
+
+	kfree(core);
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
+MODULE_DESCRIPTION("TEE Security Manager core");
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 431054810dca..9253b79b8582 100644
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
+struct tsm_core_dev;
+struct tsm_core_dev *tsm_register(struct device *parent,
+				  const struct attribute_group **groups);
+void tsm_unregister(struct tsm_core_dev *tsm_core);
 #endif /* __TSM_H */

---

## [3] Dan Williams — 2025-05-15
*Subject: [PATCH v3 02/13] PCI/IDE: Enumerate Selective Stream IDE capabilities*

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
 drivers/pci/Kconfig           |  14 +++++
 drivers/pci/Makefile          |   1 +
 drivers/pci/ide.c             | 100 ++++++++++++++++++++++++++++++++++
 drivers/pci/pci.h             |   6 ++
 drivers/pci/probe.c           |   1 +
 include/linux/pci.h           |   7 +++
 include/uapi/linux/pci_regs.h |  81 ++++++++++++++++++++++++++-
 7 files changed, 209 insertions(+), 1 deletion(-)
 create mode 100644 drivers/pci/ide.c

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index da28295b4aac..0c662f9813eb 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -121,6 +121,20 @@ config XEN_PCIDEV_FRONTEND
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
+	  Set a kernel limit for the number of streams. The expectation
+	  is that the platform limit is 4 to 8, so the kernel need not
+	  track the maximum possibility of 256 streams per host bridge
+	  in the typical case.
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
index 000000000000..98a51596e329
--- /dev/null
+++ b/drivers/pci/ide.c
@@ -0,0 +1,100 @@
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
+static int __sel_ide_offset(int ide_cap, int nr_link_ide, int stream_index,
+			    int nr_ide_mem)
+{
+	int offset;
+
+	offset = ide_cap + PCI_IDE_LINK_STREAM_0 + nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE;
+
+	/*
+	 * Assume a constant number of address association resources per
+	 * stream index
+	 */
+	if (stream_index > 0)
+		offset += stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);
+	return offset;
+}
+
+static int sel_ide_offset(struct pci_dev *pdev,
+			  struct pci_ide_partner *settings)
+{
+	return __sel_ide_offset(pdev->ide_cap, pdev->nr_link_ide,
+				settings->stream_index, pdev->nr_ide_mem);
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
+	for (int i = 0; i < nr_streams; i++) {
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
index b81e99cd4b62..10be2ce5e5d5 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -511,6 +511,12 @@ static inline void pci_doe_sysfs_init(struct pci_dev *pdev) { }
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
index 364fa2a514f8..1b597b6e946c 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2619,6 +2619,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
+	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 0e8e3fd77e96..14467b944da9 100644
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
index ba326710f9c8..90affa69edb0 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -750,7 +750,8 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
-#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_DOE
+#define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
+#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE
 
 #define PCI_EXT_CAP_DSN_SIZEOF	12
 #define PCI_EXT_CAP_MCAST_ENDPOINT_SIZEOF 40
@@ -1220,4 +1221,82 @@
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
+#define  PCI_IDE_CAP_SEL_CFG		0x80 /* Selective IDE for Config Cycles Support */
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
+/* IDE Address Association Register 3 is "Memory Base Upper" */
+#define  PCI_IDE_SEL_ADDR_2(x)		    (24 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+#define  PCI_IDE_SEL_ADDR_3(x)		    (28 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
+#define PCI_IDE_SEL_BLOCK_SIZE(nr_assoc)  (20 + PCI_IDE_SEL_ADDR_BLOCK_SIZE * (nr_assoc))
+
 #endif /* LINUX_PCI_REGS_H */

---

## [4] Dan Williams — 2025-05-15
*Subject: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

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
Userspace can watch for the arrival of the "TSM" core device,
/sys/class/tsm/tsm0/uevent, to know when the PCI core has initialized
TSM services.

The common verbs that the low-level TSM drivers implement are defined by
'struct pci_tsm_ops'. For now only 'connect' and 'disconnect' are
defined for secure session and IDE establishment. The 'probe' and
'remove' operations setup per-device context objects starting with
'struct pci_tsm_pf0', the device Physical Function 0 that mediates
communication to the device's Security Manager (DSM).

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
 Documentation/ABI/testing/sysfs-bus-pci |  45 +++
 MAINTAINERS                             |   2 +
 drivers/pci/Kconfig                     |  14 +
 drivers/pci/Makefile                    |   1 +
 drivers/pci/pci-sysfs.c                 |   4 +
 drivers/pci/pci.h                       |  10 +
 drivers/pci/probe.c                     |   1 +
 drivers/pci/remove.c                    |   3 +
 drivers/pci/tsm.c                       | 437 ++++++++++++++++++++++++
 drivers/virt/coco/host/tsm-core.c       |  19 +-
 include/linux/pci-tsm.h                 | 138 ++++++++
 include/linux/pci.h                     |   3 +
 include/linux/tsm.h                     |   4 +-
 include/uapi/linux/pci_regs.h           |   1 +
 14 files changed, 679 insertions(+), 3 deletions(-)
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 include/linux/pci-tsm.h

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 69f952fffec7..1d38e0d3a6be 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -612,3 +612,48 @@ Description:
 
 		  # ls doe_features
 		  0001:01        0001:02        doe_discovery
+
+What:		/sys/bus/pci/devices/.../tsm/
+Date:		July 2024
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
+Date:		July 2024
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) Writing "1" to this file triggers the platform TSM (TEE
+		Security Manager) to establish a connection with the device.
+		This typically includes an SPDM (DMTF Security Protocols and
+		Data Models) session over PCIe DOE (Data Object Exchange) and
+		may also include PCIe IDE (Integrity and Data Encryption)
+		establishment.
+
+What:		/sys/bus/pci/devices/.../authenticated
+Date:		July 2024
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
diff --git a/MAINTAINERS b/MAINTAINERS
index 09bf7b45708b..2f92623b4de5 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24560,8 +24560,10 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm-report
+F:	drivers/pci/tsm.c
 F:	drivers/virt/coco/guest/
 F:	drivers/virt/coco/host/
+F:	include/linux/pci-tsm.h
 F:	include/linux/tsm.h
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 0c662f9813eb..5c3f896ac9f4 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -135,6 +135,20 @@ config PCI_IDE_STREAM_MAX
 	  track the maximum possibility of 256 streams per host bridge
 	  in the typical case.
 
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
index c6cda56ca52c..6bd16a110916 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1811,6 +1811,10 @@ const struct attribute_group *pci_dev_attr_groups[] = {
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
index 10be2ce5e5d5..7f763441f658 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -517,6 +517,16 @@ void pci_ide_init(struct pci_dev *dev);
 static inline void pci_ide_init(struct pci_dev *dev) { }
 #endif
 
+#ifdef CONFIG_PCI_TSM
+void pci_tsm_init(struct pci_dev *pdev);
+void pci_tsm_destroy(struct pci_dev *pdev);
+extern const struct attribute_group pci_tsm_pf0_attr_group;
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
index 1b597b6e946c..c090289b70be 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2620,6 +2620,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_rebar_init(dev);		/* Resizable BAR */
 	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
+	pci_tsm_init(dev);		/* TEE Security Manager connection */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
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
index 000000000000..d00a8e471340
--- /dev/null
+++ b/drivers/pci/tsm.c
@@ -0,0 +1,437 @@
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
+static const struct pci_tsm_ops *tsm_ops;
+
+/* supplemental attributes to surface when pci_tsm_attr_group is active */
+static const struct attribute_group *pci_tsm_owner_attr_group;
+
+static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *pci_tsm)
+{
+	struct pci_dev *pdev = pci_tsm->pdev;
+
+	if (!is_pci_tsm_pf0(pdev) || pci_tsm->type != PCI_TSM_PF0) {
+		dev_WARN_ONCE(&pdev->dev, 1, "invalid context object\n");
+		return NULL;
+	}
+
+	return container_of(pci_tsm, struct pci_tsm_pf0, tsm);
+}
+
+/* TODO: switch to ACQUIRE() and ACQUIRE_ERR() */
+static struct mutex *tsm_ops_lock(struct pci_tsm_pf0 *tsm)
+{
+	lockdep_assert_held(&pci_tsm_rwsem);
+
+	if (mutex_lock_interruptible(&tsm->lock) != 0)
+		return NULL;
+	return &tsm->lock;
+}
+DEFINE_FREE(tsm_ops_unlock, struct mutex *, if (_T) mutex_unlock(_T))
+
+static int pci_tsm_disconnect(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
+
+	struct mutex *lock __free(tsm_ops_unlock) = tsm_ops_lock(tsm);
+	if (!lock)
+		return -EINTR;
+
+	if (tsm->state < PCI_TSM_INIT)
+		return -ENXIO;
+	if (tsm->state < PCI_TSM_CONNECT)
+		return 0;
+
+	tsm_ops->disconnect(pdev);
+	tsm->state = PCI_TSM_INIT;
+
+	return 0;
+}
+
+static int pci_tsm_connect(struct pci_dev *pdev)
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
+	if (tsm->state >= PCI_TSM_CONNECT)
+		return 0;
+
+	rc = tsm_ops->connect(pdev);
+	if (rc)
+		return rc;
+	tsm->state = PCI_TSM_CONNECT;
+	return 0;
+}
+
+/* TODO: switch to ACQUIRE() and ACQUIRE_ERR() */
+static struct rw_semaphore *tsm_read_lock(void)
+{
+	if (down_read_interruptible(&pci_tsm_rwsem))
+		return NULL;
+	return &pci_tsm_rwsem;
+}
+DEFINE_FREE(tsm_read_unlock, struct rw_semaphore *, if (_T) up_read(_T))
+
+static ssize_t connect_store(struct device *dev, struct device_attribute *attr,
+			     const char *buf, size_t len)
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
+		rc = pci_tsm_connect(pdev);
+	else
+		rc = pci_tsm_disconnect(pdev);
+	if (rc)
+		return rc;
+	return len;
+}
+
+static ssize_t connect_show(struct device *dev, struct device_attribute *attr,
+			    char *buf)
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
+	return sysfs_emit(buf, "%d\n", tsm->state >= PCI_TSM_CONNECT);
+}
+static DEVICE_ATTR_RW(connect);
+
+static bool pci_tsm_pf0_group_visible(struct kobject *kobj)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct pci_dev *pdev = to_pci_dev(dev);
+
+	if (pdev->tsm && is_pci_tsm_pf0(pdev))
+		return true;
+	return false;
+}
+DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm_pf0);
+
+static struct attribute *pci_tsm_pf0_attrs[] = {
+	&dev_attr_connect.attr,
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
+static bool is_pci_tsm_downstream(struct pci_dev *pdev)
+{
+	struct pci_dev *uport;
+
+	if (pci_pcie_type(pdev) != PCI_EXP_TYPE_ENDPOINT)
+		return false;
+
+	/* "grandparent" of an endpoint is an Upstream Port (or Root Port) */
+	if (!pdev->dev.parent)
+		return false;
+	if (!pdev->dev.parent->parent)
+		return false;
+
+	uport = to_pci_dev(pdev->dev.parent->parent);
+	if (pci_pcie_type(uport) != PCI_EXP_TYPE_UPSTREAM)
+		return false;
+
+	if (!uport->tsm)
+		return false;
+
+	/* Upstream Port has a 'tsm' context, probe downstream devices. */
+	return true;
+}
+
+static enum pci_tsm_type pci_tsm_type(struct pci_dev *pdev)
+{
+	if (is_pci_tsm_pf0(pdev))
+		return PCI_TSM_PF0;
+
+	struct pci_dev *pf0 __free(pci_dev_put) = pf0_dev_get(pdev);
+	if (!pf0)
+		return PCI_TSM_INVALID;
+
+	if (pf0->tsm && pf0->tsm->type == PCI_TSM_PF0) {
+		if (pdev->is_virtfn)
+			return PCI_TSM_VIRTFN;
+		else
+			return PCI_TSM_MFD;
+	}
+
+	/*
+	 * Allow for Device Security Managers (DSMs) at a Switch level
+	 * to host TDISP services for downstream devices
+	 */
+	if (is_pci_tsm_downstream(pdev))
+		return PCI_TSM_DOWNSTREAM;
+	return PCI_TSM_INVALID;
+}
+
+/**
+ * pci_tsm_initialize() - base 'struct pci_tsm' initialization
+ * @pdev: The PCI device
+ * @tsm: context to initialize
+ */
+void pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm)
+{
+	tsm->type = pci_tsm_type(pdev);
+	tsm->pdev = pdev;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_initialize);
+
+/**
+ * pci_tsm_pf0_initialize() - common 'struct pci_tsm_pf0' initialization
+ * @pdev: Physical Function 0 PCI device
+ * @tsm: context to initialize
+ */
+int pci_tsm_pf0_initialize(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm)
+{
+	mutex_init(&tsm->lock);
+	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					   PCI_DOE_PROTO_CMA);
+	if (!tsm->doe_mb) {
+		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
+		return -ENODEV;
+	}
+
+	tsm->state = PCI_TSM_INIT;
+	pci_tsm_initialize(pdev, &tsm->tsm);
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_pf0_initialize);
+
+static void __pci_tsm_pf0_destroy(struct pci_tsm_pf0 *tsm)
+{
+	mutex_destroy(&tsm->lock);
+}
+
+static void tsm_remove(struct pci_tsm *tsm)
+{
+	if (!tsm)
+		return;
+	tsm_ops->remove(tsm);
+}
+DEFINE_FREE(tsm_remove, struct pci_tsm *, if (_T) tsm_remove(_T))
+
+static void pci_tsm_pf0_init(struct pci_dev *pdev)
+{
+	bool tee_cap;
+
+	tee_cap = pdev->devcap & PCI_EXP_DEVCAP_TEE;
+
+	if (!(pdev->ide_cap || tee_cap))
+		return;
+
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+	if (!tsm_ops)
+		return;
+
+	/*
+	 * If a physical device has any security capabilities it may be
+	 * a candidate to connect with the platform TSM
+	 */
+	struct pci_tsm *pci_tsm __free(tsm_remove) = tsm_ops->probe(pdev);
+
+	pci_dbg(pdev, "Device security capabilities detected (%s%s ), TSM %s\n",
+		pdev->ide_cap ? " ide" : "", tee_cap ? " tee" : "",
+		pci_tsm ? "attach" : "skip");
+
+	if (!pci_tsm)
+		return;
+
+	pdev->tsm = no_free_ptr(pci_tsm);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_pf0_attr_group);
+	if (pci_tsm_owner_attr_group)
+		sysfs_merge_group(&pdev->dev.kobj, pci_tsm_owner_attr_group);
+}
+
+static void __pci_tsm_init(struct pci_dev *pdev)
+{
+	enum pci_tsm_type type = pci_tsm_type(pdev);
+
+	switch (type) {
+	case PCI_TSM_PF0:
+		pci_tsm_pf0_init(pdev);
+		break;
+	case PCI_TSM_VIRTFN:
+	case PCI_TSM_MFD:
+	case PCI_TSM_DOWNSTREAM:
+		pdev->tsm = tsm_ops->probe(pdev);
+		break;
+	case PCI_TSM_INVALID:
+	default:
+		break;
+	}
+}
+
+void pci_tsm_init(struct pci_dev *pdev)
+{
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	__pci_tsm_init(pdev);
+}
+
+int pci_tsm_core_register(const struct pci_tsm_ops *ops, const struct attribute_group *grp)
+{
+	struct pci_dev *pdev = NULL;
+
+	if (!ops)
+		return 0;
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	if (tsm_ops)
+		return -EBUSY;
+	tsm_ops = ops;
+	pci_tsm_owner_attr_group = grp;
+	for_each_pci_dev(pdev)
+		__pci_tsm_init(pdev);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_core_register);
+
+static void pci_tsm_pf0_destroy(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
+
+	if (tsm->state > PCI_TSM_INIT)
+		pci_tsm_disconnect(pdev);
+	pdev->tsm = NULL;
+	if (pci_tsm_owner_attr_group)
+		sysfs_unmerge_group(&pdev->dev.kobj, pci_tsm_owner_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_pf0_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	__pci_tsm_pf0_destroy(tsm);
+}
+
+static void __pci_tsm_destroy(struct pci_dev *pdev)
+{
+	struct pci_tsm *pci_tsm = pdev->tsm;
+
+	if (!pci_tsm)
+		return;
+
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+
+	if (is_pci_tsm_pf0(pdev))
+		pci_tsm_pf0_destroy(pdev);
+	tsm_ops->remove(pci_tsm);
+}
+
+void pci_tsm_destroy(struct pci_dev *pdev)
+{
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	__pci_tsm_destroy(pdev);
+}
+
+void pci_tsm_core_unregister(const struct pci_tsm_ops *ops)
+{
+	struct pci_dev *pdev = NULL;
+
+	if (!ops)
+		return;
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	if (ops != tsm_ops)
+		return;
+	for_each_pci_dev(pdev)
+		__pci_tsm_destroy(pdev);
+	tsm_ops = NULL;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_core_unregister);
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
diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/host/tsm-core.c
index 4f64af1a8967..51146f226a64 100644
--- a/drivers/virt/coco/host/tsm-core.c
+++ b/drivers/virt/coco/host/tsm-core.c
@@ -8,11 +8,13 @@
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
+#include <linux/pci-tsm.h>
 
 static DECLARE_RWSEM(tsm_core_rwsem);
 static struct class *tsm_class;
 static struct tsm_core_dev {
 	struct device dev;
+	const struct pci_tsm_ops *pci_ops;
 } *tsm_core;
 
 static struct tsm_core_dev *
@@ -39,7 +41,8 @@ static void put_tsm_core(struct tsm_core_dev *core)
 DEFINE_FREE(put_tsm_core, struct tsm_core_dev *,
 	    if (!IS_ERR_OR_NULL(_T)) put_tsm_core(_T))
 struct tsm_core_dev *tsm_register(struct device *parent,
-				  const struct attribute_group **groups)
+				  const struct attribute_group **groups,
+				  const struct pci_tsm_ops *pci_ops)
 {
 	struct device *dev;
 	int rc;
@@ -61,10 +64,20 @@ struct tsm_core_dev *tsm_register(struct device *parent,
 	if (rc)
 		return ERR_PTR(rc);
 
+	rc = pci_tsm_core_register(pci_ops, NULL);
+	if (rc) {
+		dev_err(parent, "PCI initialization failure: %pe\n",
+			ERR_PTR(rc));
+		return ERR_PTR(rc);
+	}
+
 	rc = device_add(dev);
-	if (rc)
+	if (rc) {
+		pci_tsm_core_unregister(pci_ops);
 		return ERR_PTR(rc);
+	}
 
+	core->pci_ops = pci_ops;
 	tsm_core = no_free_ptr(core);
 
 	return tsm_core;
@@ -79,7 +92,9 @@ void tsm_unregister(struct tsm_core_dev *core)
 		return;
 	}
 
+	pci_tsm_core_unregister(core->pci_ops);
 	device_unregister(&core->dev);
+
 	tsm_core = NULL;
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
new file mode 100644
index 000000000000..00fdae087069
--- /dev/null
+++ b/include/linux/pci-tsm.h
@@ -0,0 +1,138 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef __PCI_TSM_H
+#define __PCI_TSM_H
+#include <linux/mutex.h>
+#include <linux/pci.h>
+
+struct pci_dev;
+
+enum pci_tsm_state {
+	PCI_TSM_ERR = -1,
+	PCI_TSM_INIT,
+	PCI_TSM_CONNECT,
+};
+
+/**
+ * enum pci_tsm_type - 'struct pci_tsm' object types
+ * @PCI_TSM_PF0: function0 that hosts a DOE mailbox that comprehends an
+ *		 Interface ID per potential TDI
+ * @PCI_TSM_VIRTFN: physfn-0 of this device is "tsm_pf0"
+ * @PCI_TSM_MFD: function0 of this device is  "tsm_pf0"
+ * @PCI_TSM_DOWNSTREAM: immediate Upstream Port of this device is "tsm_pf0"
+ */
+enum pci_tsm_type {
+	PCI_TSM_INVALID,
+	PCI_TSM_PF0,
+	PCI_TSM_VIRTFN,
+	PCI_TSM_MFD,
+	PCI_TSM_DOWNSTREAM,
+};
+
+/**
+ * struct pci_tsm - Core TSM context for a given PCIe endpoint
+ * @pdev: indicates the type of pci_tsm object
+ * @type: pci_tsm object type to disambiguate PCI_TSM_DOWNSTREAM and PCI_TSM_PF0
+ *
+ * This structure is wrapped by a low level TSM driver and returned by
+ * tsm_ops.probe(), it is freed by tsm_ops.remove(). Depending on
+ * whether @pdev is physical function 0, another physical function, or a
+ * virtual function determines the pci_tsm object type. E.g. see 'struct
+ * pci_tsm_pf0'.
+ */
+struct pci_tsm {
+	struct pci_dev *pdev;
+	enum pci_tsm_type type;
+};
+
+/**
+ * struct pci_tsm_pf0 - Physical Function 0 TDISP context
+ * @state: reflect device initialized, connected, or bound
+ * @lock: protect @state vs pci_tsm_ops invocation
+ * @doe_mb: PCIe Data Object Exchange mailbox
+ */
+struct pci_tsm_pf0 {
+	struct pci_tsm tsm;
+	enum pci_tsm_state state;
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
+/**
+ * struct pci_tsm_ops - Low-level TSM-exported interface to the PCI core
+ * @probe: probe/accept device for tsm operation, setup DSM context
+ * @remove: destroy DSM context
+ * @connect: establish / validate a secure connection (e.g. IDE) with the device
+ * @disconnect: teardown the secure connection
+ *
+ * @probe and @remove run in pci_tsm_rwsem held for write context. All
+ * other ops run under the @pdev->tsm->lock mutex and pci_tsm_rwsem held
+ * for read.
+ */
+struct pci_tsm_ops {
+	struct pci_tsm *(*probe)(struct pci_dev *pdev);
+	void (*remove)(struct pci_tsm *tsm);
+	int (*connect)(struct pci_dev *pdev);
+	void (*disconnect)(struct pci_dev *pdev);
+};
+
+enum pci_doe_proto {
+	PCI_DOE_PROTO_CMA = 1,
+	PCI_DOE_PROTO_SSESSION = 2,
+};
+
+#ifdef CONFIG_PCI_TSM
+int pci_tsm_core_register(const struct pci_tsm_ops *ops,
+			  const struct attribute_group *grp);
+void pci_tsm_core_unregister(const struct pci_tsm_ops *ops);
+int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
+			 const void *req, size_t req_sz, void *resp,
+			 size_t resp_sz);
+void pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm);
+int pci_tsm_pf0_initialize(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm);
+#else
+static inline int pci_tsm_core_register(const struct pci_tsm_ops *ops,
+					const struct attribute_group *grp)
+{
+	return 0;
+}
+static inline void pci_tsm_core_unregister(const struct pci_tsm_ops *ops)
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
index 14467b944da9..72d07ad994fa 100644
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
index 9253b79b8582..59d3848404e1 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -111,7 +111,9 @@ struct tsm_report_ops {
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_core_dev;
+struct pci_tsm_ops;
 struct tsm_core_dev *tsm_register(struct device *parent,
-				  const struct attribute_group **groups);
+				  const struct attribute_group **groups,
+				  const struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_core_dev *tsm_core);
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 90affa69edb0..7e9a6a130711 100644
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

## [5] Dan Williams — 2025-05-15
*Subject: [PATCH v3 04/13] PCI: Enable host-bridge emulation for PCI_DOMAINS_GENERIC platforms*

The ability to emulate a host-bridge is useful not only for hardware PCI
controllers like CONFIG_VMD, or virtual PCI controllers like
CONFIG_PCI_HYPERV, but also for test and development scenarios like
CONFIG_SAMPLES_DEVSEC [1].

One stumbling block for defining CONFIG_SAMPLES_DEVSEC, a sample
implementation of a platform TSM for PCI Device Security, is the need to
accommodate PCI_DOMAINS_GENERIC architectures alongside x86 [2].

In support of supplementing the existing CONFIG_PCI_BRIDGE_EMUL
infrastructure for host bridges:

* Introduce pci_bus_find_emul_domain_nr() as a common way to find a free
  PCI domain number whether that is to reuse the existing dynamic
  allocation code in the !ACPI case, or to assign an unused domain above
  the last ACPI segment.

* Convert pci-hyperv to the new allocator so that the PCI core can
  unconditionally assume that bridge->domain_nr != PCI_DOMAIN_NR_NOT_SET
  is the dynamically allocated case.

A follow on patch can also convert vmd to the new scheme. Currently vmd
is limited to CONFIG_PCI_DOMAINS_GENERIC=n (x86) so, unlike pci-hyperv,
it does not immediately conflict with this new
pci_bus_find_emul_domain_nr() mechanism.

Link: http://lore.kernel.org/174107249038.1288555.12362100502109498455.stgit@dwillia2-xfh.jf.intel.com [1]
Reported-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Closes: http://lore.kernel.org/20250311144601.145736-3-suzuki.poulose@arm.com
Cc: Lorenzo Pieralisi <lpieralisi@kernel.org>
Cc: Manivannan Sadhasivam <manivannan.sadhasivam@linaro.org>
Cc: Rob Herring <robh@kernel.org>
Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: "K. Y. Srinivasan" <kys@microsoft.com>
Cc: Haiyang Zhang <haiyangz@microsoft.com>
Cc: Wei Liu <wei.liu@kernel.org>
Cc: Dexuan Cui <decui@microsoft.com>
Tested-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/controller/pci-hyperv.c | 53 ++---------------------------
 drivers/pci/pci.c                   | 43 ++++++++++++++++++++++-
 drivers/pci/probe.c                 |  8 ++++-
 include/linux/pci.h                 |  4 +++
 4 files changed, 56 insertions(+), 52 deletions(-)

diff --git a/drivers/pci/controller/pci-hyperv.c b/drivers/pci/controller/pci-hyperv.c
index ac27bda5ba26..8b624da2fdd7 100644
--- a/drivers/pci/controller/pci-hyperv.c
+++ b/drivers/pci/controller/pci-hyperv.c
@@ -3574,48 +3574,6 @@ static int hv_send_resources_released(struct hv_device *hdev)
 	return 0;
 }
 
-#define HVPCI_DOM_MAP_SIZE (64 * 1024)
-static DECLARE_BITMAP(hvpci_dom_map, HVPCI_DOM_MAP_SIZE);
-
-/*
- * PCI domain number 0 is used by emulated devices on Gen1 VMs, so define 0
- * as invalid for passthrough PCI devices of this driver.
- */
-#define HVPCI_DOM_INVALID 0
-
-/**
- * hv_get_dom_num() - Get a valid PCI domain number
- * Check if the PCI domain number is in use, and return another number if
- * it is in use.
- *
- * @dom: Requested domain number
- *
- * return: domain number on success, HVPCI_DOM_INVALID on failure
- */
-static u16 hv_get_dom_num(u16 dom)
-{
-	unsigned int i;
-
-	if (test_and_set_bit(dom, hvpci_dom_map) == 0)
-		return dom;
-
-	for_each_clear_bit(i, hvpci_dom_map, HVPCI_DOM_MAP_SIZE) {
-		if (test_and_set_bit(i, hvpci_dom_map) == 0)
-			return i;
-	}
-
-	return HVPCI_DOM_INVALID;
-}
-
-/**
- * hv_put_dom_num() - Mark the PCI domain number as free
- * @dom: Domain number to be freed
- */
-static void hv_put_dom_num(u16 dom)
-{
-	clear_bit(dom, hvpci_dom_map);
-}
-
 /**
  * hv_pci_probe() - New VMBus channel probe, for a root PCI bus
  * @hdev:	VMBus's tracking struct for this root PCI bus
@@ -3659,9 +3617,9 @@ static int hv_pci_probe(struct hv_device *hdev,
 	 * collisions) in the same VM.
 	 */
 	dom_req = hdev->dev_instance.b[5] << 8 | hdev->dev_instance.b[4];
-	dom = hv_get_dom_num(dom_req);
+	dom = pci_bus_find_emul_domain_nr(dom_req);
 
-	if (dom == HVPCI_DOM_INVALID) {
+	if (dom < 0) {
 		dev_err(&hdev->device,
 			"Unable to use dom# 0x%x or other numbers", dom_req);
 		ret = -EINVAL;
@@ -3795,7 +3753,7 @@ static int hv_pci_probe(struct hv_device *hdev,
 destroy_wq:
 	destroy_workqueue(hbus->wq);
 free_dom:
-	hv_put_dom_num(hbus->bridge->domain_nr);
+	pci_bus_release_emul_domain_nr(hbus->bridge->domain_nr);
 free_bus:
 	kfree(hbus);
 	return ret;
@@ -3919,8 +3877,6 @@ static void hv_pci_remove(struct hv_device *hdev)
 	irq_domain_remove(hbus->irq_domain);
 	irq_domain_free_fwnode(hbus->fwnode);
 
-	hv_put_dom_num(hbus->bridge->domain_nr);
-
 	kfree(hbus);
 }
 
@@ -4097,9 +4053,6 @@ static int __init init_hv_pci_drv(void)
 	if (ret)
 		return ret;
 
-	/* Set the invalid domain number's bit, so it will not be used */
-	set_bit(HVPCI_DOM_INVALID, hvpci_dom_map);
-
 	/* Initialize PCI block r/w interface */
 	hvpci_block_ops.read_block = hv_read_config_block;
 	hvpci_block_ops.write_block = hv_write_config_block;
diff --git a/drivers/pci/pci.c b/drivers/pci/pci.c
index 4d7c9f64ea24..aea6bf37a360 100644
--- a/drivers/pci/pci.c
+++ b/drivers/pci/pci.c
@@ -6713,9 +6713,50 @@ static void pci_no_domains(void)
 #endif
 }
 
+#ifdef CONFIG_PCI_DOMAINS
+static DEFINE_IDA(pci_domain_nr_dynamic_ida);
+
+/*
+ * Find a free domain_nr either allocated by pci_domain_nr_dynamic_ida or
+ * fallback to the first free domain number above the last ACPI segment number.
+ * Caller may have a specific domain number in mind, in which case try to
+ * reserve it.
+ *
+ * Note that this allocation is freed by pci_release_host_bridge_dev().
+ */
+int pci_bus_find_emul_domain_nr(int hint)
+{
+	if (hint >= 0) {
+		hint = ida_alloc_range(&pci_domain_nr_dynamic_ida, hint, hint,
+				       GFP_KERNEL);
+
+		if (hint >= 0)
+			return hint;
+	}
+
+	if (acpi_disabled)
+		return ida_alloc(&pci_domain_nr_dynamic_ida, GFP_KERNEL);
+
+	/*
+	 * Emulated domains start at 0x10000 to not clash with ACPI _SEG
+	 * domains.  Per ACPI r6.0, sec 6.5.6,  _SEG returns an integer, of
+	 * which the lower 16 bits are the PCI Segment Group (domain) number.
+	 * Other bits are currently reserved.
+	 */
+	return ida_alloc_range(&pci_domain_nr_dynamic_ida, 0x10000, INT_MAX,
+			       GFP_KERNEL);
+}
+EXPORT_SYMBOL_GPL(pci_bus_find_emul_domain_nr);
+
+void pci_bus_release_emul_domain_nr(int domain_nr)
+{
+	ida_free(&pci_domain_nr_dynamic_ida, domain_nr);
+}
+EXPORT_SYMBOL_GPL(pci_bus_release_emul_domain_nr);
+#endif
+
 #ifdef CONFIG_PCI_DOMAINS_GENERIC
 static DEFINE_IDA(pci_domain_nr_static_ida);
-static DEFINE_IDA(pci_domain_nr_dynamic_ida);
 
 static void of_pci_reserve_static_domain_nr(void)
 {
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index c090289b70be..e4a7bb8b415f 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -632,6 +632,11 @@ static void pci_release_host_bridge_dev(struct device *dev)
 
 	pci_free_resource_list(&bridge->windows);
 	pci_free_resource_list(&bridge->dma_ranges);
+
+	/* Host bridges only have domain_nr set in the emulation case */
+	if (bridge->domain_nr != PCI_DOMAIN_NR_NOT_SET)
+		pci_bus_release_emul_domain_nr(bridge->domain_nr);
+
 	kfree(bridge);
 }
 
@@ -1112,7 +1117,8 @@ static int pci_register_host_bridge(struct pci_host_bridge *bridge)
 	device_del(&bridge->dev);
 free:
 #ifdef CONFIG_PCI_DOMAINS_GENERIC
-	pci_bus_release_domain_nr(parent, bus->domain_nr);
+	if (bridge->domain_nr == PCI_DOMAIN_NR_NOT_SET)
+		pci_bus_release_domain_nr(parent, bus->domain_nr);
 #endif
 	if (bus_registered)
 		put_device(&bus->dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 72d07ad994fa..8962bf133316 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -1894,10 +1894,14 @@ DEFINE_GUARD(pci_dev, struct pci_dev *, pci_dev_lock(_T), pci_dev_unlock(_T))
  */
 #ifdef CONFIG_PCI_DOMAINS
 extern int pci_domains_supported;
+int pci_bus_find_emul_domain_nr(int hint);
+void pci_bus_release_emul_domain_nr(int domain_nr);
 #else
 enum { pci_domains_supported = 0 };
 static inline int pci_domain_nr(struct pci_bus *bus) { return 0; }
 static inline int pci_proc_domain(struct pci_bus *bus) { return 0; }
+static inline int pci_bus_find_emul_domain_nr(int hint) { return 0; }
+static inline void pci_bus_release_emul_domain_nr(int domain_nr) { }
 #endif /* CONFIG_PCI_DOMAINS */
 
 /*

---

## [6] Dan Williams — 2025-05-15
*Subject: [PATCH v3 05/13] PCI: vmd: Switch to pci_bus_find_emul_domain_nr()*

The new common domain number allocator can replace the custom allocator
in VMD.

Beyond some code reuse benefits it does close a potential race whereby
vmd_find_free_domain() collides with new PCI buses coming online with a
conflicting domain number. Such a race has not been observed in
practice, hence not tagging this change as a fix.

As VMD uses pci_create_root_bus() rather than pci_alloc_host_bridge() +
pci_scan_root_bus_bridge() it has no chance to set ->domain_nr in the
bridge so needs to manage freeing the domain number on its own.

Cc: Nirmal Patel <nirmal.patel@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/controller/vmd.c | 33 ++++++++++-----------------------
 1 file changed, 10 insertions(+), 23 deletions(-)

diff --git a/drivers/pci/controller/vmd.c b/drivers/pci/controller/vmd.c
index 8df064b62a2f..f60244ff9ef8 100644
--- a/drivers/pci/controller/vmd.c
+++ b/drivers/pci/controller/vmd.c
@@ -565,22 +565,6 @@ static void vmd_detach_resources(struct vmd_dev *vmd)
 	vmd->dev->resource[VMD_MEMBAR2].child = NULL;
 }
 
-/*
- * VMD domains start at 0x10000 to not clash with ACPI _SEG domains.
- * Per ACPI r6.0, sec 6.5.6,  _SEG returns an integer, of which the lower
- * 16 bits are the PCI Segment Group (domain) number.  Other bits are
- * currently reserved.
- */
-static int vmd_find_free_domain(void)
-{
-	int domain = 0xffff;
-	struct pci_bus *bus = NULL;
-
-	while ((bus = pci_find_next_bus(bus)) != NULL)
-		domain = max_t(int, domain, pci_domain_nr(bus));
-	return domain + 1;
-}
-
 static int vmd_get_phys_offsets(struct vmd_dev *vmd, bool native_hint,
 				resource_size_t *offset1,
 				resource_size_t *offset2)
@@ -865,13 +849,6 @@ static int vmd_enable_domain(struct vmd_dev *vmd, unsigned long features)
 		.parent = res,
 	};
 
-	sd->vmd_dev = vmd->dev;
-	sd->domain = vmd_find_free_domain();
-	if (sd->domain < 0)
-		return sd->domain;
-
-	sd->node = pcibus_to_node(vmd->dev->bus);
-
 	/*
 	 * Currently MSI remapping must be enabled in guest passthrough mode
 	 * due to some missing interrupt remapping plumbing. This is probably
@@ -903,9 +880,17 @@ static int vmd_enable_domain(struct vmd_dev *vmd, unsigned long features)
 	pci_add_resource_offset(&resources, &vmd->resources[1], offset[0]);
 	pci_add_resource_offset(&resources, &vmd->resources[2], offset[1]);
 
+	sd->vmd_dev = vmd->dev;
+	sd->domain = pci_bus_find_emul_domain_nr(PCI_DOMAIN_NR_NOT_SET);
+	if (sd->domain < 0)
+		return sd->domain;
+
+	sd->node = pcibus_to_node(vmd->dev->bus);
+
 	vmd->bus = pci_create_root_bus(&vmd->dev->dev, vmd->busn_start,
 				       &vmd_ops, sd, &resources);
 	if (!vmd->bus) {
+		pci_bus_release_emul_domain_nr(sd->domain);
 		pci_free_resource_list(&resources);
 		vmd_remove_irq_domain(vmd);
 		return -ENODEV;
@@ -998,6 +983,7 @@ static int vmd_probe(struct pci_dev *dev, const struct pci_device_id *id)
 		return -ENOMEM;
 
 	vmd->dev = dev;
+	vmd->sysdata.domain = PCI_DOMAIN_NR_NOT_SET;
 	vmd->instance = ida_alloc(&vmd_instance_ida, GFP_KERNEL);
 	if (vmd->instance < 0)
 		return vmd->instance;
@@ -1063,6 +1049,7 @@ static void vmd_remove(struct pci_dev *dev)
 	vmd_detach_resources(vmd);
 	vmd_remove_irq_domain(vmd);
 	ida_free(&vmd_instance_ida, vmd->instance);
+	pci_bus_release_emul_domain_nr(vmd->sysdata.domain);
 }
 
 static void vmd_shutdown(struct pci_dev *dev)

---

## [7] Dan Williams — 2025-05-15
*Subject: [PATCH v3 06/13] samples/devsec: Introduce a PCI device-security bus + endpoint sample*

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
 samples/devsec/tsm.c    | 143 ++++++++
 8 files changed, 945 insertions(+)
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/tsm.c

diff --git a/MAINTAINERS b/MAINTAINERS
index 2f92623b4de5..2fcbd29853a8 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24565,6 +24565,7 @@ F:	drivers/virt/coco/guest/
 F:	drivers/virt/coco/host/
 F:	include/linux/pci-tsm.h
 F:	include/linux/tsm.h
+F:	samples/devsec/
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index 09011be2391a..523a7129aed3 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -313,6 +313,22 @@ source "samples/rust/Kconfig"
 
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
index bf6e6fca5410..0f77b95c7941 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -43,3 +43,4 @@ obj-$(CONFIG_SAMPLES_RUST)		+= rust/
 obj-$(CONFIG_SAMPLE_DAMON_WSSE)		+= damon/
 obj-$(CONFIG_SAMPLE_DAMON_PRCL)		+= damon/
 obj-$(CONFIG_SAMPLE_HUNG_TASK)		+= hung_task/
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
index 000000000000..7a8d33dc54c6
--- /dev/null
+++ b/samples/devsec/tsm.c
@@ -0,0 +1,143 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved. */
+
+#define dev_fmt(fmt) "devsec: " fmt
+#include <linux/platform_device.h>
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
+static struct devsec_tsm_pf0 *to_devsec_tsm(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct devsec_tsm_pf0, pci.tsm);
+}
+
+static struct pci_tsm *devsec_tsm_pci_probe(struct pci_dev *pdev)
+{
+	int rc;
+
+	if (pdev->sysdata != devsec_sysdata)
+		return NULL;
+
+	if (!is_pci_tsm_pf0(pdev))
+		return NULL;
+
+	struct devsec_tsm_pf0 *devsec_tsm __free(kfree) =
+		kzalloc(sizeof(*devsec_tsm), GFP_KERNEL);
+	if (!devsec_tsm)
+		return NULL;
+
+	rc = pci_tsm_pf0_initialize(pdev, &devsec_tsm->pci);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "tsm enabled\n");
+	return &no_free_ptr(devsec_tsm)->pci.tsm;
+}
+
+static void devsec_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct devsec_tsm_pf0 *devsec_tsm = to_devsec_tsm(tsm);
+
+	pci_dbg(tsm->pdev, "tsm disabled\n");
+	kfree(devsec_tsm);
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
+static const struct pci_tsm_ops devsec_pci_ops = {
+	.probe = devsec_tsm_pci_probe,
+	.remove = devsec_tsm_pci_remove,
+	.connect = devsec_tsm_connect,
+	.disconnect = devsec_tsm_disconnect,
+};
+
+static void devsec_tsm_remove(void *tsm_core)
+{
+	tsm_unregister(tsm_core);
+}
+
+static int devsec_tsm_probe(struct platform_device *pdev)
+{
+	struct tsm_core_dev *tsm_core;
+
+	tsm_core = tsm_register(&pdev->dev, NULL, &devsec_pci_ops);
+	if (IS_ERR(tsm_core))
+		return PTR_ERR(tsm_core);
+
+	return devm_add_action_or_reset(&pdev->dev, devsec_tsm_remove,
+					tsm_core);
+}
+
+static struct platform_driver devsec_tsm_driver = {
+	.driver = {
+		.name = "devsec_tsm",
+	},
+};
+
+static struct platform_device *devsec_tsm;
+
+static int __init devsec_tsm_init(void)
+{
+	struct platform_device_info devsec_tsm_info = {
+		.name = "devsec_tsm",
+		.id = -1,
+	};
+	int rc;
+
+	devsec_tsm = platform_device_register_full(&devsec_tsm_info);
+	if (IS_ERR(devsec_tsm))
+		return PTR_ERR(devsec_tsm);
+
+	rc = platform_driver_probe(&devsec_tsm_driver, devsec_tsm_probe);
+	if (rc)
+		platform_device_unregister(devsec_tsm);
+	return rc;
+}
+module_init(devsec_tsm_init);
+
+static void __exit devsec_tsm_exit(void)
+{
+	platform_driver_unregister(&devsec_tsm_driver);
+	platform_device_unregister(devsec_tsm);
+}
+module_exit(devsec_tsm_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Platform TSM Driver");

---

## [8] Dan Williams — 2025-05-15
*Subject: [PATCH v3 07/13] PCI: Add PCIe Device 3 Extended Capability enumeration*

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
index e4a7bb8b415f..56704e851224 100644
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
 	pci_tsm_init(dev);		/* TEE Security Manager connection */
 
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 8962bf133316..d8dd315d8b4c 100644
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
index 7e9a6a130711..670314666fdd 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -751,6 +751,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_DEV3	0x2F	/* Device 3 Capability/Control/Status */
 #define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE
 
@@ -1217,6 +1218,12 @@
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

## [9] Dan Williams — 2025-05-15
*Subject: [PATCH v3 08/13] PCI/IDE: Add IDE establishment helpers*

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

    stream%d.%d.%d:%s

Where the tuple of integers reflects the allocated platform, Root Port,
and Endpoint stream index (Selective IDE Stream Register Block) values,
and the %s is the endpoint device name.

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
 .../ABI/testing/sysfs-devices-pci-host-bridge |  38 ++
 MAINTAINERS                                   |   1 +
 drivers/pci/ide.c                             | 366 ++++++++++++++++++
 include/linux/pci-ide.h                       |  76 ++++
 include/linux/pci.h                           |   6 +
 include/uapi/linux/pci_regs.h                 |   2 +
 6 files changed, 489 insertions(+)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 create mode 100644 include/linux/pci-ide.h

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
new file mode 100644
index 000000000000..d592b68c7333
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -0,0 +1,38 @@
+What:		/sys/devices/pciDDDD:BB
+		/sys/devices/.../pciDDDD:BB
+Date:		December, 2024
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
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) Symlink to the platform firmware device object "companion"
+		of the host bridge. For example, an ACPI device with an _HID of
+		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00). See
+		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
+		format.
+
+What:		pciDDDD:BB/streamH.R.E:DDDD:BB:DD:F
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a platform has established a secure connection, PCIe
+		IDE, between two Partner Ports, this symlink appears. The
+		primary function is to account the stream slot / resources
+		consumed in each of the (H)ost bridge, (R)oot Port and
+		(E)ndpoint that will be freed when invoking the tsm/disconnect
+		flow. The link points to the endpoint PCI device at domain:DDDD
+		bus:BB device:DD function:F. Where R and E represent the
+		assigned Selective IDE Stream Register Block in the Root Port
+		and Endpoint, and H represents a platform specific pool of
+		stream resources shared by the Root Ports in a host bridge.  See
+		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
+		format.
diff --git a/MAINTAINERS b/MAINTAINERS
index 2fcbd29853a8..e4c3da0b570b 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -18677,6 +18677,7 @@ Q:	https://patchwork.kernel.org/project/linux-pci/list/
 B:	https://bugzilla.kernel.org
 C:	irc://irc.oftc.net/linux-pci
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/pci/pci.git
+F:	Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 F:	Documentation/PCI/
 F:	Documentation/devicetree/bindings/pci/
 F:	arch/x86/kernel/early-quirks.c
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 98a51596e329..a529926647f4 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -5,6 +5,8 @@
 
 #define dev_fmt(fmt) "PCI/IDE: " fmt
 #include <linux/pci.h>
+#include <linux/sysfs.h>
+#include <linux/pci-ide.h>
 #include <linux/bitfield.h>
 #include "pci.h"
 
@@ -96,5 +98,369 @@ void pci_ide_init(struct pci_dev *pdev)
 
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
+	struct stream_index __stream[PCI_IDE_PARTNER_MAX + 1];
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
+	const char *name __free(kfree) = kasprintf(
+		GFP_KERNEL, "stream%d.%d.%d:%s", ide->host_bridge_stream,
+		rp_stream, ep_stream, dev_name(&pdev->dev));
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
+	val = PREP_PCI_IDE_SEL_RID_2(settings->rid_start, pci_ide_domain(pdev));
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
+
+	/*
+	 * Setup control register early for devices that expect
+	 * stream_id is set during key programming.
+	 */
+	set_ide_sel_ctl(pdev, ide, pos, false);
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
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_teardown);
+
+/**
+ * pci_ide_stream_enable() - after setup, enable the stream
+ * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
+ * @ide: registered and setup IDE settings descriptor
+ *
+ * Activate the stream by writing to the Selective IDE Stream Control Register.
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
+	    PCI_IDE_SEL_STS_STATE_SECURE)
+		return -ENXIO;
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_enable);
+
+/**
+ * pci_ide_stream_disable() - disable the given stream
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
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_disable);
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
new file mode 100644
index 000000000000..0753c3cd752a
--- /dev/null
+++ b/include/linux/pci-ide.h
@@ -0,0 +1,76 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+/* PCIe 6.2 section 6.33 Integrity & Data Encryption (IDE) */
+
+#ifndef __PCI_IDE_H__
+#define __PCI_IDE_H__
+
+#include <linux/range.h>
+
+#define SEL_ADDR1_LOWER_MASK GENMASK(31, 20)
+#define SEL_ADDR_UPPER_MASK GENMASK_ULL(63, 32)
+#define PREP_PCI_IDE_SEL_ADDR1(base, limit)                    \
+	(FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |             \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK,          \
+		    FIELD_GET(SEL_ADDR1_LOWER_MASK, (base))) | \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK,         \
+		    FIELD_GET(SEL_ADDR1_LOWER_MASK, (limit))))
+
+#define PREP_PCI_IDE_SEL_RID_2(base, domain)               \
+	(FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |          \
+	 FIELD_PREP(PCI_IDE_SEL_RID_2_BASE_MASK, (base)) | \
+	 FIELD_PREP(PCI_IDE_SEL_RID_2_SEG_MASK, (domain)))
+
+enum pci_ide_partner_select {
+	PCI_IDE_EP,
+	PCI_IDE_RP,
+	PCI_IDE_PARTNER_MAX,
+	/* pci_ide_stream_alloc() uses this for stream index allocation */
+	PCI_IDE_HB = PCI_IDE_PARTNER_MAX,
+};
+
+/**
+ * struct pci_ide_partner - Per port IDE Stream settings
+ * @rid_start: Partner Port Requester ID range start
+ * @rid_start: Partner Port Requester ID range end
+ * @stream_index: Selective IDE Stream Register Block selection
+ */
+struct pci_ide_partner {
+	u16 rid_start;
+	u16 rid_end;
+	u8 stream_index;
+};
+
+/**
+ * struct pci_ide - PCIe Selective IDE Stream descriptor
+ * @pdev: PCIe Endpoint for the stream
+ * @partner: settings for both partner ports in a stream
+ * @host_bridge_stream: track platform Stream index
+ * @stream_id: unique id (within Partner Port pairing) for the stream
+ * @name: name of the stream in sysfs
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
+DEFINE_FREE(pci_ide_stream_free, struct pci_ide *, if (_T) pci_ide_stream_free(_T))
+int  pci_ide_stream_register(struct pci_ide *ide);
+void pci_ide_stream_unregister(struct pci_ide *ide);
+void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide);
+int pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide);
+#endif /* __PCI_IDE_H__ */
diff --git a/include/linux/pci.h b/include/linux/pci.h
index d8dd315d8b4c..d1c901904ee4 100644
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
@@ -605,6 +607,10 @@ struct pci_host_bridge {
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
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 670314666fdd..0ae7e77313f8 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -1286,6 +1286,8 @@
 /* Selective IDE Stream Status Register */
 #define  PCI_IDE_SEL_STS		 8
 #define   PCI_IDE_SEL_STS_STATE_MASK	 __GENMASK(3, 0) /* Selective IDE Stream State */
+#define   PCI_IDE_SEL_STS_STATE_INSECURE 0
+#define   PCI_IDE_SEL_STS_STATE_SECURE   2
 #define   PCI_IDE_SEL_STS_RECVD_INTEGRITY_CHECK	0x80000000 /* Received Integrity Check Fail Msg */
 /* IDE RID Association Register 1 */
 #define  PCI_IDE_SEL_RID_1		 0xc

---

## [10] Dan Williams — 2025-05-15
*Subject: [PATCH v3 09/13] PCI/IDE: Report available IDE streams*

The limited number of link-encryption (IDE) streams that a given set of
host bridges supports is a platform specific detail. Provide
pci_ide_init_nr_streams() as a generic facility for either platform TSM
drivers, or PCI core native IDE, to report the number available streams.
After invoking pci_ide_init_nr_streams() an "available_secure_streams"
attribute appears in PCI host bridge sysfs to convey that count.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge | 13 ++++
 drivers/pci/ide.c                             | 59 +++++++++++++++++++
 drivers/pci/pci.h                             |  3 +
 drivers/pci/probe.c                           | 12 +++-
 include/linux/pci.h                           |  8 +++
 5 files changed, 94 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index d592b68c7333..382866a21703 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -36,3 +36,16 @@ Description:
 		stream resources shared by the Root Ports in a host bridge.  See
 		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
 		format.
+
+What:		pciDDDD:BB/available_secure_streams
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host bridge has Root Ports that support PCIe IDE
+		(link encryption and integrity protection) there may be a
+		limited number of streams that can be used for establishing new
+		secure links. This attribute decrements upon secure link setup,
+		and increments upon secure link teardown. The in-use stream
+		count is determined by counting stream symlinks.  See
+		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
+		format.
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index a529926647f4..b7561ac03405 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -464,3 +464,62 @@ void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide)
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
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
+	if (hb->nr_ide_streams < 0)
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
+	NULL,
+};
+
+static umode_t pci_ide_attr_visible(struct kobject *kobj, struct attribute *a, int n)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct pci_host_bridge *hb = to_pci_host_bridge(dev);
+
+	if (a == &dev_attr_available_secure_streams.attr)
+		if (hb->nr_ide_streams < 0)
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
+void pci_ide_init_nr_streams(struct pci_host_bridge *hb, int nr)
+{
+	hb->nr_ide_streams = nr;
+	sysfs_update_group(&hb->dev.kobj, &pci_ide_attr_group);
+}
+EXPORT_SYMBOL_NS_GPL(pci_ide_init_nr_streams, "PCI_IDE");
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 7f763441f658..3e556e4ad9b9 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -513,8 +513,11 @@ static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 
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
index 56704e851224..93be55321537 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -640,6 +640,16 @@ static void pci_release_host_bridge_dev(struct device *dev)
 	kfree(bridge);
 }
 
+static const struct attribute_group *pci_host_bridge_groups[] = {
+	PCI_IDE_ATTR_GROUP,
+	NULL,
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
index d1c901904ee4..5f37957da18f 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -662,6 +662,14 @@ void pci_set_host_bridge_release(struct pci_host_bridge *bridge,
 				 void (*release_fn)(struct pci_host_bridge *),
 				 void *release_data);
 
+#ifdef CONFIG_PCI_IDE
+void pci_ide_init_nr_streams(struct pci_host_bridge *hb, int nr);
+#else
+static inline void pci_ide_init_nr_streams(struct pci_host_bridge *hb, int nr)
+{
+}
+#endif
+
 int pcibios_root_bridge_prepare(struct pci_host_bridge *bridge);
 
 #define PCI_REGION_FLAG_MASK	0x0fU	/* These bits of resource flags tell us the PCI region flags */

---

## [11] Dan Williams — 2025-05-15
*Subject: [PATCH v3 10/13] PCI/TSM: Report active IDE streams*

Given that the platform TSM owns IDE Stream ID allocation, report the
active streams via the TSM class device. Establish a symlink from the
class device to the PCI endpoint device consuming the stream, named by
the Stream ID.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm | 10 ++++++++++
 drivers/virt/coco/host/tsm-core.c         | 17 +++++++++++++++++
 include/linux/tsm.h                       |  4 ++++
 3 files changed, 31 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 7503f04a9eb9..75ee2b9bc555 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -8,3 +8,13 @@ Description:
 		signals when the PCI layer is able to support establishment of
 		link encryption and other device-security features coordinated
 		through the platform tsm.
+
+What:		/sys/class/tsm/tsm0/streamN:DDDD:BB:DD:F
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host bridge has established a secure connection via
+		the platform TSM, symlink appears. The primary function of this
+		is have a system global review of TSM resource consumption
+		across host bridges. The link points to the endpoint PCI device
+		at domain:DDDD bus:BB device:DD function:F.
diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/host/tsm-core.c
index 51146f226a64..bd9e09b07412 100644
--- a/drivers/virt/coco/host/tsm-core.c
+++ b/drivers/virt/coco/host/tsm-core.c
@@ -2,13 +2,16 @@
 /* Copyright(c) 2024 Intel Corporation. All rights reserved. */
 
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+#define dev_fmt(fmt) KBUILD_MODNAME ": " fmt
 
 #include <linux/tsm.h>
+#include <linux/pci.h>
 #include <linux/rwsem.h>
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 
 static DECLARE_RWSEM(tsm_core_rwsem);
 static struct class *tsm_class;
@@ -99,6 +102,20 @@ void tsm_unregister(struct tsm_core_dev *core)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+/* must be invoked between tsm_register / tsm_unregister */
+int tsm_ide_stream_register(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	return sysfs_create_link(&tsm_core->dev.kobj, &pdev->dev.kobj,
+				 ide->name);
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_register);
+
+void tsm_ide_stream_unregister(struct pci_ide *ide)
+{
+	sysfs_remove_link(&tsm_core->dev.kobj, ide->name);
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_core_dev *core = container_of(dev, typeof(*core), dev);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 59d3848404e1..915c4c8b061b 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -116,4 +116,8 @@ struct tsm_core_dev *tsm_register(struct device *parent,
 				  const struct attribute_group **groups,
 				  const struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_core_dev *tsm_core);
+struct pci_dev;
+struct pci_ide;
+int tsm_ide_stream_register(struct pci_dev *pdev, struct pci_ide *ide);
+void tsm_ide_stream_unregister(struct pci_ide *ide);
 #endif /* __TSM_H */

---

## [12] Dan Williams — 2025-05-15
*Subject: [PATCH v3 11/13] samples/devsec: Add sample IDE establishment*

Exercise common setup and teardown flows for a sample platform TSM
driver that implements the TSM 'connect' and 'disconnect' flows.

This is both a template for platform specific implementations and a
simple integration test for the PCI core infrastructure + ABI.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 samples/devsec/bus.c |  3 ++
 samples/devsec/tsm.c | 77 +++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 79 insertions(+), 1 deletion(-)

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
index 7a8d33dc54c6..aa852ac1c16d 100644
--- a/samples/devsec/tsm.c
+++ b/samples/devsec/tsm.c
@@ -4,6 +4,7 @@
 #define dev_fmt(fmt) "devsec: " fmt
 #include <linux/platform_device.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 #include <linux/module.h>
 #include <linux/pci.h>
 #include <linux/tsm.h>
@@ -50,6 +51,10 @@ static void devsec_tsm_pci_remove(struct pci_tsm *tsm)
 	kfree(devsec_tsm);
 }
 
+/* protected by tsm_ops lock */
+static DECLARE_BITMAP(devsec_stream_ids, NR_TSM_STREAMS);
+static struct pci_ide *devsec_streams[NR_TSM_STREAMS];
+
 /*
  * Reference consumer for a TSM driver "connect" operation callback. The
  * low-level TSM driver understands details about the platform the PCI
@@ -74,11 +79,81 @@ static void devsec_tsm_pci_remove(struct pci_tsm *tsm)
  */
 static int devsec_tsm_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide *ide;
+	int rc, stream_id;
+
+	stream_id =
+		find_first_zero_bit(devsec_stream_ids, NR_TSM_STREAMS);
+	if (stream_id == NR_TSM_STREAMS)
+		return -EBUSY;
+	set_bit(stream_id, devsec_stream_ids);
+
+	ide = pci_ide_stream_alloc(pdev);
+	if (!ide) {
+		rc = -ENOMEM;
+		goto err_stream_alloc;
+	}
+
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
+	 * Model a TSM that handled enabling the stream at
+	 * tsm_ide_stream_register() time
+	 */
+	rc = pci_ide_stream_enable(pdev, ide);
+	if (rc)
+		goto err_enable;
+	devsec_streams[stream_id] = ide;
+
+	return 0;
+
+err_enable:
+	tsm_ide_stream_unregister(ide);
+err_tsm:
+	pci_ide_stream_teardown(rp, ide);
+	pci_ide_stream_teardown(pdev, ide);
+	pci_ide_stream_unregister(ide);
+err_stream:
+	pci_ide_stream_free(ide);
+err_stream_alloc:
+	clear_bit(stream_id, devsec_stream_ids);
+
+	return rc;
 }
 
 static void devsec_tsm_disconnect(struct pci_dev *pdev)
 {
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide *ide;
+	int i;
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
+	pci_ide_stream_disable(pdev, ide);
+	tsm_ide_stream_unregister(ide);
+	pci_ide_stream_teardown(rp, ide);
+	pci_ide_stream_teardown(pdev, ide);
+	pci_ide_stream_unregister(ide);
+	pci_ide_stream_free(ide);
+	clear_bit(i, devsec_stream_ids);
 }
 
 static const struct pci_tsm_ops devsec_pci_ops = {

---

## [13] Dan Williams — 2025-05-15
*Subject: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host TSM driver*

From: Xu Yilun <yilun.xu@linux.intel.com>

Add kAPIs pci_tsm_{bind,unbind,guest_req}() for PCI devices.

pci_tsm_bind/unbind() are supposed to be called by kernel components
which manages the virtual device. The verb 'bind' means VMM does extra
configurations to make the assigned device ready to be validated by
CoCo VM as TDI (TEE Device Interface). Usually these configurations
include assigning device ownership and MMIO ownership to CoCo VM, and
move the TDI to CONFIG_LOCKED TDISP state by LOCK_INTERFACE_REQUEST
TDISP message. The detailed operations are specific to platform TSM
firmware so need to be supported by vendor TSM drivers.

pci_tsm_guest_req() supports a channel for CoCo VM to directly talk
to TSM firmware about further TDI operations after TDI is bound, e.g.
get device interface report, certifications & measurements. So this kAPI
is supposed to be called from KVM vmexit handler.

A problem to solve here is the TDI operation lock. The TDI operations
involve TDISP message communication with devices, which is transferred
via PF0's DOE. When multiple VFs or MFDs are involved at the same time,
these messages are not intended to interleave with each other. So
serialize all TSM operations of one slot by holding the DSM device (PF0)
pci_tsm.lock.

Add a struct pci_tdi to represent the TDI context, which is common to
all PFs/VFs/MFDs so embedded it in struct pci_tsm. The appearing of the
tsm::tdi means the device is in BOUND state and vice versa. So no extra
enum pci_tsm_state value is added for bind. That also means the access
to tsm::tdi must with the DEM device (PF0) TSM lock.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/tsm.c       | 227 +++++++++++++++++++++++++++++++++++++++-
 include/linux/pci-tsm.h |  64 +++++++++++
 2 files changed, 290 insertions(+), 1 deletion(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index d00a8e471340..219e40c5d4e7 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -50,10 +50,65 @@ static struct mutex *tsm_ops_lock(struct pci_tsm_pf0 *tsm)
 }
 DEFINE_FREE(tsm_ops_unlock, struct mutex *, if (_T) mutex_unlock(_T))
 
+static int __pci_tsm_unbind(struct pci_dev *pdev);
+static void pci_tsm_unbind_all_vfs(struct pci_dev *pdev)
+{
+	struct pci_dev *virtfn;
+
+	for (int i = 0; i < pci_num_vf(pdev); i++) {
+		virtfn = pci_get_domain_bus_and_slot(pci_domain_nr(pdev->bus),
+						     pci_iov_virtfn_bus(pdev, i),
+						     pci_iov_virtfn_devfn(pdev, i));
+		if (virtfn) {
+			__pci_tsm_unbind(virtfn);
+			pci_dev_put(virtfn);
+		}
+	}
+}
+
+static void pci_tsm_unbind_all_mfds(struct pci_dev *pdev)
+{
+	struct pci_dev *phyfn;
+
+	for (int i = 0; i < 8; i++) {
+		phyfn = pci_get_slot(pdev->bus, PCI_DEVFN(PCI_SLOT(pdev->devfn), i));
+		if (phyfn) {
+			__pci_tsm_unbind(phyfn);
+			pci_dev_put(phyfn);
+		}
+	}
+}
+
+static int unbind_downstream(struct pci_dev *pdev, void *uport_subordinate)
+{
+	if (pdev->bus->parent != uport_subordinate)
+		return 0;
+
+	if (pdev->tsm && pdev->tsm->type == PCI_TSM_DOWNSTREAM)
+		__pci_tsm_unbind(pdev);
+
+	return 0;
+}
+
+static void pci_tsm_unbind_all_downstream(struct pci_dev *pdev)
+{
+	if (pci_pcie_type(pdev) != PCI_EXP_TYPE_UPSTREAM)
+		return;
+
+	if (!pdev->tsm)
+		return;
+
+	pci_walk_bus(pdev->subordinate, unbind_downstream, pdev->subordinate);
+}
+
 static int pci_tsm_disconnect(struct pci_dev *pdev)
 {
 	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
 
+	pci_tsm_unbind_all_downstream(pdev);
+	pci_tsm_unbind_all_vfs(pdev);
+	pci_tsm_unbind_all_mfds(pdev);
+
 	struct mutex *lock __free(tsm_ops_unlock) = tsm_ops_lock(tsm);
 	if (!lock)
 		return -EINTR;
@@ -392,8 +447,12 @@ static void __pci_tsm_destroy(struct pci_dev *pdev)
 
 	lockdep_assert_held_write(&pci_tsm_rwsem);
 
-	if (is_pci_tsm_pf0(pdev))
+	if (is_pci_tsm_pf0(pdev)) {
 		pci_tsm_pf0_destroy(pdev);
+	} else {
+		__pci_tsm_unbind(pdev);
+		pdev->tsm = NULL;
+	}
 	tsm_ops->remove(pci_tsm);
 }
 
@@ -435,3 +494,169 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 		       resp, resp_sz);
 }
 EXPORT_SYMBOL_GPL(pci_tsm_doe_transfer);
+
+/* lookup the 'DSM' pf0 for @pdev */
+static struct pci_dev *tsm_pf0_get(struct pci_dev *pdev)
+{
+	struct pci_dev *uport_pf0;
+
+	struct pci_dev *pf0 __free(pci_dev_put) = pf0_dev_get(pdev);
+	if (!pf0)
+		return NULL;
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
+/* Only implement non-interruptible lock for now */
+static struct mutex *tdi_ops_lock(struct pci_dev *pf0_dev)
+{
+	struct pci_tsm_pf0 *pf0_tsm;
+
+	lockdep_assert_held(&pci_tsm_rwsem);
+
+	if (!pf0_dev->tsm)
+		return ERR_PTR(-EINVAL);
+
+	pf0_tsm = to_pci_tsm_pf0(pf0_dev->tsm);
+	mutex_lock(&pf0_tsm->lock);
+
+	if (pf0_tsm->state < PCI_TSM_CONNECT) {
+		mutex_unlock(&pf0_tsm->lock);
+		return ERR_PTR(-EINVAL);
+	}
+
+	return &pf0_tsm->lock;
+}
+DEFINE_FREE(tdi_ops_unlock, struct mutex *, if (!IS_ERR(_T)) mutex_unlock(_T))
+
+int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
+{
+	struct pci_tdi *tdi;
+
+	if (!kvm)
+		return -EINVAL;
+
+	struct rw_semaphore *lock __free(tsm_read_unlock) = tsm_read_lock();
+	if (!lock)
+		return -EINTR;
+
+	if (!pdev->tsm)
+		return -EINVAL;
+
+	struct pci_dev *pf0_dev __free(pci_dev_put) = tsm_pf0_get(pdev);
+	if (!pf0_dev)
+		return -EINVAL;
+
+	struct mutex *ops_lock __free(tdi_ops_unlock) = tdi_ops_lock(pf0_dev);
+	if (IS_ERR(ops_lock))
+		return PTR_ERR(ops_lock);
+
+	if (pdev->tsm->tdi) {
+		if (pdev->tsm->tdi->kvm == kvm)
+			return 0;
+		else
+			return -EBUSY;
+	}
+
+	tdi = tsm_ops->bind(pdev, pf0_dev, kvm, tdi_id);
+	if (!tdi)
+		return -ENXIO;
+
+	pdev->tsm->tdi = tdi;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_bind);
+
+static int __pci_tsm_unbind(struct pci_dev *pdev)
+{
+	struct pci_tdi *tdi;
+
+	lockdep_assert_held(&pci_tsm_rwsem);
+
+	if (!pdev->tsm)
+		return -EINVAL;
+
+	struct pci_dev *pf0_dev __free(pci_dev_put) = tsm_pf0_get(pdev);
+	if (!pf0_dev)
+		return -EINVAL;
+
+	struct mutex *lock __free(tdi_ops_unlock) = tdi_ops_lock(pf0_dev);
+	if (IS_ERR(lock))
+		return PTR_ERR(lock);
+
+	tdi = pdev->tsm->tdi;
+	if (!tdi)
+		return 0;
+
+	tsm_ops->unbind(tdi);
+	pdev->tsm->tdi = NULL;
+
+	return 0;
+}
+
+int pci_tsm_unbind(struct pci_dev *pdev)
+{
+	struct rw_semaphore *lock __free(tsm_read_unlock) = tsm_read_lock();
+	if (!lock)
+		return -EINTR;
+
+	return __pci_tsm_unbind(pdev);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_unbind);
+
+/**
+ * pci_tsm_guest_req - VFIO/IOMMUFD helper to handle guest requests
+ * @pdev: @pdev representing a bound tdi
+ * @info: envelope for the request
+ *
+ * Expected flow is guest low-level TSM driver initiates a guest request
+ * like "transition TDISP state to RUN", "fetch report" via a
+ * technology specific guest-host-interface and KVM exit reason. KVM
+ * posts to userspace (e.g. QEMU) that holds the host-to-guest RID
+ * mapping.
+ */
+int pci_tsm_guest_req(struct pci_dev *pdev, struct pci_tsm_guest_req_info *info)
+{
+	struct pci_tdi *tdi;
+	int rc;
+
+	lockdep_assert_held_read(&pci_tsm_rwsem);
+
+	if (!pdev->tsm)
+		return -ENODEV;
+
+	struct pci_dev *pf0_dev __free(pci_dev_put) = tsm_pf0_get(pdev);
+	if (!pf0_dev)
+		return -EINVAL;
+
+	struct mutex *lock __free(tdi_ops_unlock) = tdi_ops_lock(pf0_dev);
+	if (IS_ERR(lock))
+		return -ENODEV;
+
+	tdi = pdev->tsm->tdi;
+	if (!tdi)
+		return -ENODEV;
+
+	rc = tsm_ops->guest_req(pdev, info);
+	if (rc)
+		return -EIO;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_guest_req);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 00fdae087069..2328037ae4d1 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -5,6 +5,7 @@
 #include <linux/pci.h>
 
 struct pci_dev;
+struct kvm;
 
 enum pci_tsm_state {
 	PCI_TSM_ERR = -1,
@@ -28,10 +29,23 @@ enum pci_tsm_type {
 	PCI_TSM_DOWNSTREAM,
 };
 
+/**
+ * struct pci_tdi - TDI context
+ * @pdev: host side representation of guest-side TDI
+ * @dsm: PF0 PCI device that can modify TDISP state for the TDI
+ * @kvm: TEE VM context of bound TDI
+ */
+struct pci_tdi {
+	struct pci_dev *pdev;
+	struct pci_dev *dsm;
+	struct kvm *kvm;
+};
+
 /**
  * struct pci_tsm - Core TSM context for a given PCIe endpoint
  * @pdev: indicates the type of pci_tsm object
  * @type: pci_tsm object type to disambiguate PCI_TSM_DOWNSTREAM and PCI_TSM_PF0
+ * @tdi: TDI context
  *
  * This structure is wrapped by a low level TSM driver and returned by
  * tsm_ops.probe(), it is freed by tsm_ops.remove(). Depending on
@@ -42,6 +56,7 @@ enum pci_tsm_type {
 struct pci_tsm {
 	struct pci_dev *pdev;
 	enum pci_tsm_type type;
+	struct pci_tdi *tdi;
 };
 
 /**
@@ -86,12 +101,40 @@ static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
 	return PCI_FUNC(pdev->devfn) == 0;
 }
 
+enum pci_tsm_guest_req_type {
+	PCI_TSM_GUEST_REQ_TDXC,
+};
+
+/**
+ * struct pci_tsm_guest_req_info - parameter for pci_tsm_ops.guest_req()
+ * @type: identify the format of the following blobs
+ * @type_info: extra input/output info, e.g. firmware error code
+ * @type_info_len: the size of @type_info
+ * @req: request data buffer filled by guest
+ * @req_len: the size of @req filled by guest
+ * @resp: response data buffer filled by host
+ * @resp_len: for input, the size of @resp buffer filled by guest
+ *	      for output, the size of actual response data filled by host
+ */
+struct pci_tsm_guest_req_info {
+	enum pci_tsm_guest_req_type type;
+	void *type_info;
+	size_t type_info_len;
+	void *req;
+	size_t req_len;
+	void *resp;
+	size_t resp_len;
+};
+
 /**
  * struct pci_tsm_ops - Low-level TSM-exported interface to the PCI core
  * @probe: probe/accept device for tsm operation, setup DSM context
  * @remove: destroy DSM context
  * @connect: establish / validate a secure connection (e.g. IDE) with the device
  * @disconnect: teardown the secure connection
+ * @bind: establish a secure binding with the TVM
+ * @unbind: teardown the secure binding
+ * @guest_req: handle the vendor specific requests from TVM when bound
  *
  * @probe and @remove run in pci_tsm_rwsem held for write context. All
  * other ops run under the @pdev->tsm->lock mutex and pci_tsm_rwsem held
@@ -102,6 +145,11 @@ struct pci_tsm_ops {
 	void (*remove)(struct pci_tsm *tsm);
 	int (*connect)(struct pci_dev *pdev);
 	void (*disconnect)(struct pci_dev *pdev);
+	struct pci_tdi *(*bind)(struct pci_dev *pdev, struct pci_dev *pf0_dev,
+				struct kvm *kvm, u64 tdi_id);
+	void (*unbind)(struct pci_tdi *tdi);
+	int (*guest_req)(struct pci_dev *pdev,
+			 struct pci_tsm_guest_req_info *info);
 };
 
 enum pci_doe_proto {
@@ -118,6 +166,9 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 			 size_t resp_sz);
 void pci_tsm_initialize(struct pci_dev *pdev, struct pci_tsm *tsm);
 int pci_tsm_pf0_initialize(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm);
+int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id);
+int pci_tsm_unbind(struct pci_dev *pdev);
+int pci_tsm_guest_req(struct pci_dev *pdev, struct pci_tsm_guest_req_info *info);
 #else
 static inline int pci_tsm_core_register(const struct pci_tsm_ops *ops,
 					const struct attribute_group *grp)
@@ -134,5 +185,18 @@ static inline int pci_tsm_doe_transfer(struct pci_dev *pdev,
 {
 	return -ENOENT;
 }
+static inline int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm,
+			       u64 tdi_id)
+{
+	return -ENOENT;
+}
+static inline int pci_tsm_unbind(struct pci_dev *pdev)
+{
+	return -ENOENT;
+}
+int pci_tsm_guest_req(struct pci_dev *pdev, struct pci_tsm_guest_req_info *info)
+{
+	return -ENOENT;
+}
 #endif
 #endif /*__PCI_TSM_H */

---

## [14] Dan Williams — 2025-05-15
*Subject: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

From: Xu Yilun <yilun.xu@linux.intel.com>

Enable PCI TSM/TSM core to support assigned device authentication in
CoCo VM. The main changes are:

 - Add an ->accept() operation which also flags whether the TSM driver is
   host or guest context.
 - Re-purpose the 'connect' sysfs attribute in guest to lock down the
   private configuration for the device.
 - Add the 'accept' sysfs attribute for guest to accept the private
   device into its TEE.
 - Skip DOE setup/transfer for guest TSM managed devices.

All private capable assigned PCI devices (TDI) start as shared. CoCo VM
should authenticate some of these devices and accept them in its TEE for
private memory access. TSM supports this authentication in 3 steps:
Connect, Attest and Accept.

On Connect, CoCo VM requires hypervisor to finish all private
configurations to the device and put the device in TDISP CONFIG_LOCKED
state. Please note this verb has different meaning from host context. On
host, Connect means establish secure physical link (e.g. PCI IDE).

On Attest, CoCo VM retrieves evidence from device and decide if the
device is good for accept. The CoCo VM kernel provides evidence,
userspace decides if the evidence is good based on its own strategy.

On Accept, userspace has acknowledged the evidence and requires CoCo VM
kernel to enable private MMIO & DMA access. Usually it ends up by put
the device in TDISP RUN state.

Currently only implement Connect & Accept to enable a minimum flow for
device shared <-> private conversion. There is no evidence retrieval
interfaces, only to assume the device evidences are always good without
attestation.

The shared -> private conversion:

  echo 1 > /sys/bus/pci/devices/<...>/tsm/connect
  echo 1 > /sys/bus/pci/devices/<...>/tsm/accept

The private -> shared conversion:

  echo 0 > /sys/bus/pci/devices/<...>/tsm/connect

Since the device's MMIO & DMA are all blocked after Connect & before
Accept, device drivers are not considered workable in this intermediate
state. The Connect and Accept transitions only proceed while the driver is
detached. Note this can be relaxed later with a callback to an enlightened
driver to coordinate the transition, but for now, require detachment.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/tsm.c       | 160 +++++++++++++++++++++++++++++++++++-----
 include/linux/pci-tsm.h |  15 +++-
 2 files changed, 152 insertions(+), 23 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 219e40c5d4e7..794de2f258c3 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -124,6 +124,29 @@ static int pci_tsm_disconnect(struct pci_dev *pdev)
 	return 0;
 }
 
+/*
+ * TDISP locked state temporarily makes the device inaccessible, do not
+ * surprise live attached drivers
+ */
+static int __driver_idle_connect(struct pci_dev *pdev)
+{
+	guard(device)(&pdev->dev);
+	if (pdev->dev.driver)
+		return -EBUSY;
+	return tsm_ops->connect(pdev);
+}
+
+/*
+ * When the registered ops support accept it indicates that this is a
+ * TVM-side (guest) TSM operations structure. In this mode ->connect()
+ * arranges for the TDI to enter TDISP LOCKED state, and ->accept()
+ * transitions the device to RUN state.
+ */
+static bool tvm_mode(void)
+{
+	return !!tsm_ops->accept;
+}
+
 static int pci_tsm_connect(struct pci_dev *pdev)
 {
 	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
@@ -138,13 +161,47 @@ static int pci_tsm_connect(struct pci_dev *pdev)
 	if (tsm->state >= PCI_TSM_CONNECT)
 		return 0;
 
-	rc = tsm_ops->connect(pdev);
+	if (tvm_mode())
+		rc = __driver_idle_connect(pdev);
+	else
+		rc = tsm_ops->connect(pdev);
 	if (rc)
 		return rc;
 	tsm->state = PCI_TSM_CONNECT;
 	return 0;
 }
 
+static int pci_tsm_accept(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
+	int rc;
+
+	struct mutex *lock __free(tsm_ops_unlock) = tsm_ops_lock(tsm);
+	if (!lock)
+		return -EINTR;
+
+	if (tsm->state < PCI_TSM_CONNECT)
+		return -ENXIO;
+	if (tsm->state >= PCI_TSM_ACCEPT)
+		return 0;
+
+	/*
+	 * "Accept" transitions a device to the run state, it is only suitable
+	 * to make that transition from a known DMA-idle (no active mappings)
+	 * state.  The "driver detached" state is a coarse way to assert that
+	 * requirement.
+	 */
+	guard(device)(&pdev->dev);
+	if (pdev->dev.driver)
+		return -EBUSY;
+
+	rc = tsm_ops->accept(pdev);
+	if (rc)
+		return rc;
+	tsm->state = PCI_TSM_ACCEPT;
+	return 0;
+}
+
 /* TODO: switch to ACQUIRE() and ACQUIRE_ERR() */
 static struct rw_semaphore *tsm_read_lock(void)
 {
@@ -196,6 +253,61 @@ static ssize_t connect_show(struct device *dev, struct device_attribute *attr,
 }
 static DEVICE_ATTR_RW(connect);
 
+static ssize_t accept_store(struct device *dev, struct device_attribute *attr,
+			    const char *buf, size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	bool accept;
+	int rc;
+
+	rc = kstrtobool(buf, &accept);
+	if (rc)
+		return rc;
+
+	if (!accept)
+		return -EINVAL;
+
+	struct rw_semaphore *lock __free(tsm_read_unlock) = tsm_read_lock();
+	if (!lock)
+		return -EINTR;
+
+	rc = pci_tsm_accept(pdev);
+	if (rc)
+		return rc;
+
+	return len;
+}
+
+static ssize_t accept_show(struct device *dev, struct device_attribute *attr,
+			   char *buf)
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
+	return sysfs_emit(buf, "%d\n", tsm->state >= PCI_TSM_ACCEPT);
+}
+static DEVICE_ATTR_RW(accept);
+
+static umode_t pci_tsm_pf0_attr_visible(struct kobject *kobj,
+					struct attribute *a, int n)
+{
+	if (!tvm_mode()) {
+		/* Host context, filter out guest only attributes */
+		if (a == &dev_attr_accept.attr)
+			return 0;
+	}
+
+	return a->mode;
+}
+
 static bool pci_tsm_pf0_group_visible(struct kobject *kobj)
 {
 	struct device *dev = kobj_to_dev(kobj);
@@ -205,10 +317,11 @@ static bool pci_tsm_pf0_group_visible(struct kobject *kobj)
 		return true;
 	return false;
 }
-DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm_pf0);
+DEFINE_SYSFS_GROUP_VISIBLE(pci_tsm_pf0);
 
 static struct attribute *pci_tsm_pf0_attrs[] = {
 	&dev_attr_connect.attr,
+	&dev_attr_accept.attr,
 	NULL
 };
 
@@ -322,11 +435,15 @@ EXPORT_SYMBOL_GPL(pci_tsm_initialize);
 int pci_tsm_pf0_initialize(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm)
 {
 	mutex_init(&tsm->lock);
-	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
-					   PCI_DOE_PROTO_CMA);
-	if (!tsm->doe_mb) {
-		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
-		return -ENODEV;
+
+	/* Assigned pci device in guest won't have IDE and DOE exposed. */
+	if (!tvm_mode()) {
+		tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+						   PCI_DOE_PROTO_CMA);
+		if (!tsm->doe_mb) {
+			pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
+			return -ENODEV;
+		}
 	}
 
 	tsm->state = PCI_TSM_INIT;
@@ -483,7 +600,7 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 {
 	struct pci_tsm_pf0 *tsm;
 
-	if (!pdev->tsm || !is_pci_tsm_pf0(pdev))
+	if (!pdev->tsm || !is_pci_tsm_pf0(pdev) || tvm_mode())
 		return -ENXIO;
 
 	tsm = to_pci_tsm_pf0(pdev->tsm);
@@ -495,8 +612,8 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 }
 EXPORT_SYMBOL_GPL(pci_tsm_doe_transfer);
 
-/* lookup the 'DSM' pf0 for @pdev */
-static struct pci_dev *tsm_pf0_get(struct pci_dev *pdev)
+/* lookup the Device Security Manager (DSM) pf0 for @pdev */
+static struct pci_dev *dsm_dev_get(struct pci_dev *pdev)
 {
 	struct pci_dev *uport_pf0;
 
@@ -558,11 +675,11 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
 	if (!pdev->tsm)
 		return -EINVAL;
 
-	struct pci_dev *pf0_dev __free(pci_dev_put) = tsm_pf0_get(pdev);
-	if (!pf0_dev)
+	struct pci_dev *dsm_dev __free(pci_dev_put) = dsm_dev_get(pdev);
+	if (!dsm_dev)
 		return -EINVAL;
 
-	struct mutex *ops_lock __free(tdi_ops_unlock) = tdi_ops_lock(pf0_dev);
+	struct mutex *ops_lock __free(tdi_ops_unlock) = tdi_ops_lock(dsm_dev);
 	if (IS_ERR(ops_lock))
 		return PTR_ERR(ops_lock);
 
@@ -573,10 +690,13 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
 			return -EBUSY;
 	}
 
-	tdi = tsm_ops->bind(pdev, pf0_dev, kvm, tdi_id);
+	tdi = tsm_ops->bind(pdev, dsm_dev, kvm, tdi_id);
 	if (!tdi)
 		return -ENXIO;
 
+	tdi->pdev = pdev;
+	tdi->dsm_dev = dsm_dev;
+	tdi->kvm = kvm;
 	pdev->tsm->tdi = tdi;
 
 	return 0;
@@ -592,11 +712,11 @@ static int __pci_tsm_unbind(struct pci_dev *pdev)
 	if (!pdev->tsm)
 		return -EINVAL;
 
-	struct pci_dev *pf0_dev __free(pci_dev_put) = tsm_pf0_get(pdev);
-	if (!pf0_dev)
+	struct pci_dev *dsm_dev __free(pci_dev_put) = dsm_dev_get(pdev);
+	if (!dsm_dev)
 		return -EINVAL;
 
-	struct mutex *lock __free(tdi_ops_unlock) = tdi_ops_lock(pf0_dev);
+	struct mutex *lock __free(tdi_ops_unlock) = tdi_ops_lock(dsm_dev);
 	if (IS_ERR(lock))
 		return PTR_ERR(lock);
 
@@ -641,11 +761,11 @@ int pci_tsm_guest_req(struct pci_dev *pdev, struct pci_tsm_guest_req_info *info)
 	if (!pdev->tsm)
 		return -ENODEV;
 
-	struct pci_dev *pf0_dev __free(pci_dev_put) = tsm_pf0_get(pdev);
-	if (!pf0_dev)
+	struct pci_dev *dsm_dev __free(pci_dev_put) = dsm_dev_get(pdev);
+	if (!dsm_dev)
 		return -EINVAL;
 
-	struct mutex *lock __free(tdi_ops_unlock) = tdi_ops_lock(pf0_dev);
+	struct mutex *lock __free(tdi_ops_unlock) = tdi_ops_lock(dsm_dev);
 	if (IS_ERR(lock))
 		return -ENODEV;
 
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 2328037ae4d1..1920ca591a42 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -11,6 +11,7 @@ enum pci_tsm_state {
 	PCI_TSM_ERR = -1,
 	PCI_TSM_INIT,
 	PCI_TSM_CONNECT,
+	PCI_TSM_ACCEPT,
 };
 
 /**
@@ -32,12 +33,12 @@ enum pci_tsm_type {
 /**
  * struct pci_tdi - TDI context
  * @pdev: host side representation of guest-side TDI
- * @dsm: PF0 PCI device that can modify TDISP state for the TDI
+ * @dsm_dev: PF0 PCI device that can modify TDISP state for the TDI
  * @kvm: TEE VM context of bound TDI
  */
 struct pci_tdi {
 	struct pci_dev *pdev;
-	struct pci_dev *dsm;
+	struct pci_dev *dsm_dev;
 	struct kvm *kvm;
 };
 
@@ -69,7 +70,12 @@ struct pci_tsm_pf0 {
 	struct pci_tsm tsm;
 	enum pci_tsm_state state;
 	struct mutex lock;
-	struct pci_doe_mb *doe_mb;
+	union {
+		struct {	/* host pf0 tsm */
+			struct pci_doe_mb *doe_mb;
+		};
+		/* To be added: guest tsm */
+	};
 };
 
 /* physical function0 and capable of 'connect' */
@@ -135,6 +141,8 @@ struct pci_tsm_guest_req_info {
  * @bind: establish a secure binding with the TVM
  * @unbind: teardown the secure binding
  * @guest_req: handle the vendor specific requests from TVM when bound
+ * @accept: TVM-only operation to confirm that system policy allows
+ *	    device to access private memory and be mapped with private mmio.
  *
  * @probe and @remove run in pci_tsm_rwsem held for write context. All
  * other ops run under the @pdev->tsm->lock mutex and pci_tsm_rwsem held
@@ -150,6 +158,7 @@ struct pci_tsm_ops {
 	void (*unbind)(struct pci_tdi *tdi);
 	int (*guest_req)(struct pci_dev *pdev,
 			 struct pci_tsm_guest_req_info *info);
+	int (*accept)(struct pci_dev *pdev);
 };
 
 enum pci_doe_proto {

---

## [15] Xu Yilun — 2025-05-16
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Thu, May 15, 2025 at 10:47:31PM -0700, Dan Williams wrote:
> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

To clarify, this commit message is staled. We are proposing existing to
QEMU, then pass to TSM through IOMMUFD VDEVICE.

Thanks,
Yilun

---

## [16] kernel test robot — 2025-05-18
*Subject: Re: [PATCH v3 09/13] PCI/IDE: Report available IDE streams*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 7515f45c165269b72ee739e6fc26cc2ef928fc1b]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/coco-tsm-Introduce-a-core-device-for-TEE-Security-Managers/20250516-135307
base:   7515f45c165269b72ee739e6fc26cc2ef928fc1b
patch link:    https://lore.kernel.org/r/20250516054732.2055093-10-dan.j.williams%40intel.com
patch subject: [PATCH v3 09/13] PCI/IDE: Report available IDE streams
config: i386-randconfig-r072-20250518 (https://download.01.org/0day-ci/archive/20250518/202505182032.CfUZnPyX-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14) 12.2.0

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202505182032.CfUZnPyX-lkp@intel.com/

smatch warnings:
drivers/pci/ide.c:475 available_secure_streams_show() warn: unsigned 'hb->nr_ide_streams' is never less than zero.
drivers/pci/ide.c:495 pci_ide_attr_visible() warn: unsigned 'hb->nr_ide_streams' is never less than zero.

vim +475 drivers/pci/ide.c

   467	
   468	static ssize_t available_secure_streams_show(struct device *dev,
   469						     struct device_attribute *attr,
   470						     char *buf)
   471	{
   472		struct pci_host_bridge *hb = to_pci_host_bridge(dev);
   473		int avail;
   474	
 > 475		if (hb->nr_ide_streams < 0)
   476			return -ENXIO;
   477	
   478		avail = hb->nr_ide_streams -
   479			bitmap_weight(hb->ide_stream_map, hb->nr_ide_streams);
   480		return sysfs_emit(buf, "%d\n", avail);
   481	}
   482	static DEVICE_ATTR_RO(available_secure_streams);
   483	
   484	static struct attribute *pci_ide_attrs[] = {
   485		&dev_attr_available_secure_streams.attr,
   486		NULL,
   487	};
   488	
   489	static umode_t pci_ide_attr_visible(struct kobject *kobj, struct attribute *a, int n)
   490	{
   491		struct device *dev = kobj_to_dev(kobj);
   492		struct pci_host_bridge *hb = to_pci_host_bridge(dev);
   493	
   494		if (a == &dev_attr_available_secure_streams.attr)
 > 495			if (hb->nr_ide_streams < 0)
   496				return 0;
   497	
   498		return a->mode;
   499	}
   500

---

## [17] Alexey Kardashevskiy — 2025-05-19
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 16/5/25 15:47, Dan Williams wrote:
> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

Does not belong here, if the caller failed to get the kvm pointer from an fd, then that caller should handle it.

> +
> +	struct rw_semaphore *lock __free(tsm_read_unlock) = tsm_read_lock();

Nothing checks for these errors.

> +
> +	struct pci_dev *pf0_dev __free(pci_dev_put) = tsm_pf0_get(pdev);

return rc.

> +
> +	return 0;

Will Intel ever need more types here?

> +};
> +

Call it "fw_ret"?

> + * @type_info_len: the size of @type_info
> + * @req: request data buffer filled by guest

pf0_dev is not needed here, we should be able to calculate it from pdev.

tdi_id is 32bit.

Should return an error code. Thanks,

> +	void (*unbind)(struct pci_tdi *tdi);
> +	int (*guest_req)(struct pci_dev *pdev,

---

## [18] Alexey Kardashevskiy — 2025-05-19
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

On 16/5/25 15:47, Dan Williams wrote:
> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

Do not need "__"...

> +{
> +	guard(device)(&pdev->dev);

> +	return tsm_ops->connect(pdev);
> +}

tsm_ops->accept != NULL


> +}
> +

... or just open code it here?

> +	else
> +		rc = tsm_ops->connect(pdev);

Add an empty line.

> +	if (!lock)
> +		return -EINTR;

And then the userspace will modprobe the driver, which will enable BME and MSE which in turn will render the ERROR state, what is the plan here?

> +	 */
> +	guard(device)(&pdev->dev);

A bunch of changes like this one belong to 12/13.

>   
> -	struct mutex *ops_lock __free(tdi_ops_unlock) = tdi_ops_lock(pf0_dev);


Should be in 12/13.

>   	struct kvm *kvm;
>   };


When I posted my v1, I got several comments to not put host and guest callbacks together which makes sense (as only really "connect" and "status" are shared, and I am not sure I like dual use of "connect") and so did I in v2 and yet you are pushing for one struct for all? Thanks,



>   };
>

---

## [19] Aneesh Kumar K.V — 2025-05-20
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Dan Williams <dan.j.williams@intel.com> writes:

> From: Xu Yilun <yilun.xu@linux.intel.com>
>

Now that we have guest kernel also susing tsm_register, should we have
patch [PATCH 01/13] coco/tsm: Introduce a core device for TEE Security
Managers add tsm-core.c to drivers/virt/coco/ ?

Something similar to https://git.gitlab.arm.com/linux-arm/linux-cca/-/commit/2e83f71b4b3a71ee56a77b45f5214b6223dda3b5

-aneesh

---

## [20] Aneesh Kumar K.V — 2025-05-20
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Thu, May 15, 2025 at 10:47:31PM -0700, Dan Williams wrote:
>> From: Xu Yilun <yilun.xu@linux.intel.com>

Can you share the POC code/git repo implementing that? I am looking for
pci_tsm_bind()/pci_tsm_unbind() example usage.

-aneesh

---

## [21] Aneesh Kumar K.V — 2025-05-20
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Dan Williams <dan.j.williams@intel.com> writes:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 
 .....

> @@ -558,11 +675,11 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
>  	if (!pdev->tsm)

Can we do the below?

modified   include/linux/pci-tsm.h
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

And update dsm_dev during ->probe(). That will avoid these get/put()
operations in these functions.


-aneesh

---

## [22] Aneesh Kumar K.V — 2025-05-20
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Dan Williams <dan.j.williams@intel.com> writes:

> From: Xu Yilun <yilun.xu@linux.intel.com>
...

> @@ -558,11 +675,11 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
>  	if (!pdev->tsm)

should that be no_free_ptr(dsm_dev)? Also unbind needs to drop that
device reference? 

modified   drivers/pci/tsm.c
@@ -697,7 +697,7 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
 		return -ENXIO;
 
 	tdi->pdev = pdev;
-	tdi->dsm_dev = dsm_dev;
+	tdi->dsm_dev = no_free_ptr(dsm_dev);
 	tdi->kvm = kvm;
 	pdev->tsm->tdi = tdi;
 
@@ -714,10 +714,6 @@ static int __pci_tsm_unbind(struct pci_dev *pdev)
 	if (!pdev->tsm)
 		return -EINVAL;
 
-	struct pci_dev *dsm_dev __free(pci_dev_put) = dsm_dev_get(pdev);
-	if (!dsm_dev)
-		return -EINVAL;
-
 	struct mutex *lock __free(tdi_ops_unlock) = tdi_ops_lock(dsm_dev);
 	if (IS_ERR(lock))
 		return PTR_ERR(lock);
@@ -726,6 +722,10 @@ static int __pci_tsm_unbind(struct pci_dev *pdev)
 	if (!tdi)
 		return 0;
 
+	struct pci_dev *dsm_dev __free(pci_dev_put) = tdi->dsm_dev;
+	if (!dsm_dev)
+		return -EINVAL;
+
 	tsm_ops->unbind(tdi);
 	pdev->tsm->tdi = NULL;
 


>  
>  	return 0;

...

-aneesh

---

## [23] Dan Williams — 2025-05-20
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy wrote:
[..]
> > +int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
> > +{

Sure.

[..]
> > +static int __pci_tsm_unbind(struct pci_dev *pdev)
> > +{

True this function signature should probably drop the error code
altogether and become a void helper. I.e. it should be impossible for a
bound device to not have a reference, or not be in the right state.

> 
> > +

Agree.

[..]
> > @@ -86,12 +101,40 @@ static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
> >   	return PCI_FUNC(pdev->devfn) == 0;

I doubt it as this is routing to a TDX vs TIO vs ... blob handler. It is
unfortunate that we need this indirection (i.e. missing
standardization), but it is in the same line-of-thought as
configfs-tsm-report providing a transport along with a
technology-specific "provider" identifier for parsing the blob.

> > + * struct pci_tsm_guest_req_info - parameter for pci_tsm_ops.guest_req()
> > + * @type: identify the format of the following blobs

Sure.

[..]
> > @@ -102,6 +145,11 @@ struct pci_tsm_ops {
> >   	void (*remove)(struct pci_tsm *tsm);

The pci_tsm core needs to hold the lock before calling this routine. At
that point might as well pass the already looked up device rather than
require the low-level TSM driver to repeat that work.

> tdi_id is 32bit.

@Yilun, I saw that you had it as 64-bit in one location, was that
unintentional.

Note that INTERFACE_ID is Reserved to be 12-bytes, but today FUNCTION_ID
is indeed only 4-bytes. I will fix this up unless some arch speaks up
and says they need to pass a larger id around.

> Should return an error code. Thanks,

Lets make it an ERR_PTR() because the low-level provider likely needs to
allocate more than just a 'struct pci_tdi' on bind.

---

## [24] Dan Williams — 2025-05-20
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Alexey Kardashevskiy wrote:
> 
> 

I am ok to drop. The thought was to make this nuance stand-out more, as
one more level of indirection than typically necessary, but no need to
push that preference.

> > +{
> > +	guard(device)(&pdev->dev);

Yeah, that is a bit more idiomatic.

> > +}
> > +

I will do with dropping the "__" and keeping the helper with the
comment to keep this function less busy.

> > +	else
> > +		rc = tsm_ops->connect(pdev);

I think we, as a community, are still figuring out the coding-style
around scope-based cleanup declarations, but I would argue, no empty
line required after mid-function variable declarations. Now, in this
case it is arguably not "mid-function", but all the other occurrences of
tsm_ops_lock() are checking the result on the immediate next line.

> > +	if (!lock)
> > +		return -EINTR;

Right, so the notifier proposal [1] gave me pause because of perceived
complexity and my general reluctance to rely on the magic of notifiers
when an explicit sequence is easier to read/maintain. The proposal is
that drivers switch to TDISP aware setup helpers that understand that
BME and MSE were handled at LOCK. Becauase it is not just
pci_enable_device() / pci_set_master() awareness that is needed but also
pci_disable_device() / pci_clear_master() flows that need consideration
for avoiding/handling the TDISP ERROR state.

I.e. support for TDISP-unaware drivers is not a goal.

There are still details to work out like supporting drivers that want to
stay loaded over the UNLOCKED->LOCKED->RUN transitions, and whether the
"accept" UAPI triggers entry into "RUN" or still requires a driver to
perform that.

[1]: http://lore.kernel.org/20250218111017.491719-20-aik@amd.com

[..]
> > @@ -558,11 +675,11 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
> >   	if (!pdev->tsm)

Whoops, yes, missed that before sending.

[..]
> > @@ -135,6 +141,8 @@ struct pci_tsm_guest_req_info {
> >    * @bind: establish a secure binding with the TVM

Frankly, I missed that feedback and was focused on how to simply extend
PCI to understand TSM semantics.

Part of the motivation is reduce the number of details that
drivers/pci/tsm.c needs to consider. I.e. there is only one ops object
to manage. Can you share the lore links for the comments that convinced
you to change course? Maybe those folks can chime in again here, but I
might have been too focused my tdi_dev object model concerns to notice
those previously.

As for repurposing "connect" that also comes back to question of whether
userspace needs to see or care about that nuance. In the end "connect"
is "prepare this device for follow-on TSM + TDISP security operations".
If the "accept" attribute is present userspace can infer that it has
more work to get the device operational in the TEE. So the interface can
indeed be more verbose... but to what end?

---

## [25] Dan Williams — 2025-05-20
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

Makes sense to me.

---

## [26] Dan Williams — 2025-05-20
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

That sounds reasonable at first glance to me, and might even kill the
need for pci_tsm_type because:

PCI_TSM_INVALID: !tsm || !dsm_dev
PCI_TSM_PF0: pdev == dsm_dev
PCI_TSM_VIRTFN: is_virtfn(pdev)
PCI_TSM_MFD: pdev != dsm_dev && PCI_SLOT(pdev) == PCI_SLOT(dsm_dev)
PCI_TSM_DOWNSTREAM: is_upstream_port(dsm_dev)

---

## [27] Dan Williams — 2025-05-20
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

Hmmm, are there any scenarios where @tdi can outlive @dsm_dev?

The end of life of @dsm_dev includes pci_tsm_destroy() which should
invalidate all outstanding @tdi contexts.

---

## [28] Xu Yilun — 2025-05-21
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Tue, May 20, 2025 at 01:12:12PM -0700, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]

This field is intended for out-of-blob values, like fw_ret. But fw_ret
is specified in GHCB and is vendor specific. Other vendors may also
have different values of this kind.

So I intend to gather these out-of-blob values in type_info, like:

enum pci_tsm_guest_req_type {
  PCI_TSM_GUEST_REQ_TDXC,
  PCI_TSM_GUEST_REQ_SEV_SNP,
};

/* SEV SNP guest request type info */
struct pci_tsm_guest_req_sev_snp {
	s32 fw_err;
};

Since IOMMUFD has the userspace entry, maybe these definitions should be
moved to include/uapi/linux/iommufd.h.

In pci-tsm.h, just define:

struct pci_tsm_guest_req_info {
	u32 type;
	void __user *type_info;
	size_t type_info_len;
	void __user *req;
	size_t req_len;
	void __user *resp;
	size_t resp_len;
};

BTW: TDX Connect has no out-of-blob value, so should set type_info_len = 0

> 
> [..]

Intel is also switching to gBDF as tdi_id, so yes 32bit is good.

> 
> Note that INTERFACE_ID is Reserved to be 12-bytes, but today FUNCTION_ID

Yes.

Thanks,
Yilun

> 
> > Should return an error code. Thanks,

---

## [29] Xu Yilun — 2025-05-21
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Tue, May 20, 2025 at 12:47:05PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

The usage of these kAPIs should be in IOMMUFD, that's what I'm doing for
Stage 2 patchset. I need to rebase this series, adopt suggestions from
Jason, and make TDX Connect work to verify, so need more time...

Thanks,
Yilun

> 
> -aneesh

---

## [30] Xu Yilun — 2025-05-21
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

> @@ -573,10 +690,13 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
>  			return -EBUSY;

I think it is still better that platform TSM drivers assign these
fields in ->bind(), just as pci_tsm_ops.probe() do.  It is
inconveniente that struct pci_tdi is not initialized, then these
parameters have to be passed again and again between functions.

Thanks,
Yilun

>  	pdev->tsm->tdi = tdi;

---

## [31] Aneesh Kumar K.V — 2025-05-21
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Dan Williams <dan.j.williams@intel.com> writes:

....

> +static void pci_tsm_pf0_init(struct pci_dev *pdev)
> +{

If we expect to use pci_tsm_pf0_init and is_pci_tsm_pf0() from the
guest, can we have the ide_cap and tee_cap check here? Will that be true
for all devices assigned to the guest?

> +
> +	lockdep_assert_held_write(&pci_tsm_rwsem);
....

> +/* physical function0 and capable of 'connect' */
> +static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)

here

> +	default:
> +		return false;


-aneesh

---

## [32] Alexey Kardashevskiy — 2025-05-22
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

On 21/5/25 07:11, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>>

Do not really care as much :)

> 
>>> +	if (!lock)

So your plan it to modify driver to switch to the secure mode on the go? (not arguing, just asking for now)

The alternative is - let TSM do the attestation and acceptance and then "modprobe tdispawaredriver tdisp=on" and change the driver to assume that BME and MSE are already enabled.



> There are still details to work out like supporting drivers that want to
> stay loaded over the UNLOCKED->LOCKED->RUN transitions, and whether the

That was literally you (and I think someone else mentioned it too) ;)

https://lore.kernel.org/all/66d7a10a4d621_3975294ac@dwillia2-xfh.jf.intel.com.notmuch/

"Lets not mix HV and VM hooks in the same ops without good reason" and I do not see a good reason here yet.

More to the point, the host and guest have very little in common to have one ops struct for both and then deal with questions "do we execute the code related to PF0 in the guest", etc.

My life definitely got easier with 2 separate structures and my split to virt/coco/...(tsm-host.c|tsm-guest.c|tsm.c) + pci/tsm.c.


> Part of the motivation is reduce the number of details that
> drivers/pci/tsm.c needs to consider. I.e. there is only one ops object

I see "connect" more like "set up ssh connection with some ports forwarded"

> If the "accept" attribute is present userspace can infer that it has
> more work to get the device operational in the TEE. So the interface can

... and these "accept" as connecting via ssh-forwarded ports. Not the same thing. But not really an issue here. Thanks,

---

## [33] Aneesh Kumar K.V — 2025-05-26
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Tue, May 20, 2025 at 12:47:05PM +0530, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

Since the bind/unbind operations are PCI-specific callbacks, and iommufd
doesn’t seem to have a PCI-specific abstraction layer (unlike vfio,
which uses vfio_pci.c), I’m wondering how iommufd intends to support
PCI-specific TSM binding. Will there be a new interface for this, or is
it expected to hook into something existing?

-aneesh

---

## [34] Alexey Kardashevskiy — 2025-05-26
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 26/5/25 15:05, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

Not really, it is PCI-specific in TSM (for DOE) but since IOMMUFD is not doing any of that, it can work with struct device (not pci_dev). Thanks,

> doesn’t seem to have a PCI-specific abstraction layer (unlike vfio,
> which uses vfio_pci.c), I’m wondering how iommufd intends to support

---

## [35] Alexey Kardashevskiy — 2025-05-26
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 21/5/25 19:28, Xu Yilun wrote:
> On Tue, May 20, 2025 at 01:12:12PM -0700, Dan Williams wrote:
>> Alexey Kardashevskiy wrote:


The pci_tsm_ops hooks already know what they are - SEV or TDX.


> /* SEV SNP guest request type info */
> struct pci_tsm_guest_req_sev_snp {


No TDX Connect fw error handling on the host OS whatsoever, always return to the guest? oookay, do not use it but the fw response is still a generic thing. Whatever is specific to AMD can be packed into req/resp and QEMU/guest will handle those.



>>
>> [..]

yeah, 4 or 12 bytes make sense but not 8. Thanks,


> 
> Thanks,

---

## [36] Aneesh Kumar K.V — 2025-05-26
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 26/5/25 15:05, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

Ok, something like this? and iommufd will call tsm_bind()?

int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id)
{
	if (!dev_is_pci(dev))
		return -EINVAL;

	return pci_tsm_bind(to_pci_dev(dev), kvm, tdi_id);
}
EXPORT_SYMBOL_GPL(tsm_bind);

int tsm_unbind(struct device *dev)
{
	if (!dev_is_pci(dev))
		return -EINVAL;

	return pci_tsm_unbind(to_pci_dev(dev));
}
EXPORT_SYMBOL_GPL(tsm_unbind);


-aneesh

---

## [37] Alexey Kardashevskiy — 2025-05-27
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 27/5/25 01:44, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

yeah, I guess, there is a couple of places like this

git grep pci_dev drivers/iommu/iommufd/

drivers/iommu/iommufd/device.c:                 struct pci_dev *pdev = to_pci_dev(idev->dev);
drivers/iommu/iommufd/eventq.c:         struct pci_dev *pdev = to_pci_dev(dev);

Although I do not see any compelling reason to have pci_dev in the TSM API, struct device should just work and not spill any PCI details to IOMMUFD but whatever... Thanks,

> 
> int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id)

---

## [38] Suzuki K Poulose — 2025-05-27
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 26/05/2025 16:44, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

Remember that there may be other devices, AMBA CHI based devices
being assigned. Not sure if they pretend to be PCI or not.

Cheers
Suzuki


> 
> int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id)

---

## [39] Aneesh Kumar K.V — 2025-05-27
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 27/5/25 01:44, Aneesh Kumar K.V wrote:
>> Alexey Kardashevskiy <aik@amd.com> writes:

Getting the kvm reference is tricky here. Also the locking while
updating vdevice->tsm_bound needs some solution. Here is what I am
improving. Are you also planning something similar?

 drivers/iommu/iommufd/device.c          |  4 +-
 drivers/iommu/iommufd/iommufd_private.h |  5 ++
 drivers/iommu/iommufd/main.c            |  5 ++
 drivers/iommu/iommufd/viommu.c          | 62 +++++++++++++++++++++++++
 drivers/vfio/iommufd.c                  |  2 +-
 include/linux/iommufd.h                 |  3 +-
 include/uapi/linux/iommufd.h            | 16 +++++++
 7 files changed, 94 insertions(+), 3 deletions(-)

diff --git a/drivers/iommu/iommufd/device.c b/drivers/iommu/iommufd/device.c
index 2111bad72c72..79d669064044 100644
--- a/drivers/iommu/iommufd/device.c
+++ b/drivers/iommu/iommufd/device.c
@@ -165,7 +165,7 @@ void iommufd_device_destroy(struct iommufd_object *obj)
  * The caller must undo this with iommufd_device_unbind()
  */
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
-					   struct device *dev, u32 *id)
+					   struct device *dev, struct kvm *kvm, u32 *id)
 {
 	struct iommufd_device *idev;
 	struct iommufd_group *igroup;
@@ -221,6 +221,7 @@ struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
 	refcount_inc(&idev->obj.users);
 	/* igroup refcount moves into iommufd_device */
 	idev->igroup = igroup;
+	idev->kvm = kvm;
 	mutex_init(&idev->iopf_lock);
 
 	/*
@@ -1009,6 +1010,7 @@ void iommufd_device_detach(struct iommufd_device *idev, ioasid_t pasid)
 	if (!hwpt)
 		return;
 	iommufd_hw_pagetable_put(idev->ictx, hwpt);
+	idev->kvm = NULL;
 	refcount_dec(&idev->obj.users);
 }
 EXPORT_SYMBOL_NS_GPL(iommufd_device_detach, "IOMMUFD");
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 80e8c76d25f2..dd1c87500a74 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -424,6 +424,7 @@ struct iommufd_device {
 	struct list_head group_item;
 	/* always the physical device */
 	struct device *dev;
+	struct kvm *kvm;
 	bool enforce_cache_coherency;
 	/* protect iopf_enabled counter */
 	struct mutex iopf_lock;
@@ -606,13 +607,17 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_viommu_destroy(struct iommufd_object *obj);
 int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_vdevice_destroy(struct iommufd_object *obj);
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd);
+int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd);
 
 struct iommufd_vdevice {
 	struct iommufd_object obj;
 	struct iommufd_ctx *ictx;
 	struct iommufd_viommu *viommu;
 	struct device *dev;
+	struct kvm *kvm;
 	u64 id; /* per-vIOMMU virtual ID */
+	bool tsm_bound;
 };
 
 #ifdef CONFIG_IOMMUFD_TEST
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 3df468f64e7d..9959436d0d42 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -320,6 +320,7 @@ union ucmd_buffer {
 	struct iommu_veventq_alloc veventq;
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
+	struct iommu_vdevice_id vdev_id;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -379,6 +380,10 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 __reserved),
 	IOCTL_OP(IOMMU_VIOMMU_ALLOC, iommufd_viommu_alloc_ioctl,
 		 struct iommu_viommu_alloc, out_viommu_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_BIND, iommufd_vdevice_tsm_bind_ioctl,
+		 struct iommu_vdevice_id, vdevice_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_UNBIND, iommufd_vdevice_tsm_unbind_ioctl,
+		 struct iommu_vdevice_id, vdevice_id),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 01df2b985f02..9182353f7069 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -2,6 +2,7 @@
 /* Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES
  */
 #include "iommufd_private.h"
+#include "linux/tsm.h"
 
 void iommufd_viommu_destroy(struct iommufd_object *obj)
 {
@@ -90,6 +91,9 @@ void iommufd_vdevice_destroy(struct iommufd_object *obj)
 		container_of(obj, struct iommufd_vdevice, obj);
 	struct iommufd_viommu *viommu = vdev->viommu;
 
+	if (vdev->tsm_bound)
+		tsm_unbind(vdev->dev);
+
 	/* xa_cmpxchg is okay to fail if alloc failed xa_cmpxchg previously */
 	xa_cmpxchg(&viommu->vdevs, vdev->id, vdev, NULL, GFP_KERNEL);
 	refcount_dec(&viommu->obj.users);
@@ -134,6 +138,8 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	vdev->dev = idev->dev;
 	get_device(idev->dev);
 	vdev->viommu = viommu;
+	vdev->kvm = idev->kvm;
+	pr_info("Assigning kvm 0x%lx\n", vdev->kvm);
 	refcount_inc(&viommu->obj.users);
 
 	curr = xa_cmpxchg(&viommu->vdevs, virt_id, NULL, vdev, GFP_KERNEL);
@@ -157,3 +163,59 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &viommu->obj);
 	return rc;
 }
+
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_id *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	int rc = 0;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	rc = tsm_bind(vdev->dev, vdev->kvm, vdev->id);
+	if (rc) {
+		rc = -ENODEV;
+		goto out_put_vdev;
+	}
+
+	/* locking? */
+	vdev->tsm_bound = true;
+	refcount_inc(&vdev->obj.users);
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
+
+int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_id *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	int rc = 0;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	rc = tsm_unbind(vdev->dev);
+	if (rc) {
+		rc = -ENODEV;
+		goto out_put_vdev;
+	}
+
+	refcount_dec(&vdev->obj.users);
+	/* locking ? */
+	vdev->tsm_bound = false;
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
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
index 34b6e6ca4bfa..79a9bb0a7a00 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -51,8 +51,9 @@ struct iommufd_object {
 	unsigned int id;
 };
 
+struct kvm;
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
-					   struct device *dev, u32 *id);
+					   struct device *dev, struct kvm *kvm, u32 *id);
 void iommufd_device_unbind(struct iommufd_device *idev);
 
 int iommufd_device_attach(struct iommufd_device *idev, ioasid_t pasid,
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index f29b6c44655e..abcdad90bfba 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -56,6 +56,8 @@ enum {
 	IOMMUFD_CMD_VDEVICE_ALLOC = 0x91,
 	IOMMUFD_CMD_IOAS_CHANGE_PROCESS = 0x92,
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
+	IOMMUFD_CMD_VDEVICE_TSM_BIND = 0x94,
+	IOMMUFD_CMD_VDEVICE_TSM_UNBIND = 0x95,
 };
 
 /**
@@ -1038,6 +1040,20 @@ enum iommu_veventq_flag {
 	IOMMU_VEVENTQ_FLAG_LOST_EVENTS = (1U << 0),
 };
 
+/**
+ * struct iommu_vdevice_tsm_unbind - ioctl(IOMMU_VDEVICE_TSM_UNBIND)
+ * @size: sizeof(struct iommu_vdevice_tsm_unbind)
+ * @vdevice_id:
+ *
+ */
+struct iommu_vdevice_id {
+	__u32 size;
+	__u32 vdevice_id;
+} __packed;
+#define IOMMU_VDEVICE_TSM_BIND _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_BIND)
+#define IOMMU_VDEVICE_TSM_UNBIND _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_UNBIND)
+
+
 /**
  * struct iommufd_vevent_header - Virtual Event Header for a vEVENTQ Status
  * @flags: Combination of enum iommu_veventq_flag

---

## [40] Jason Gunthorpe — 2025-05-27
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Tue, May 27, 2025 at 05:18:01PM +0530, Aneesh Kumar K.V wrote:
> > yeah, I guess, there is a couple of places like this
> >

The KVM will come from the viommu object, passed in by userspace that
is the plan at least.. If you are not presenting a viommu to the guest
then I imagine we would still have some kind of NOP viommu object..

We need an association between the viommu and vdevice to tell the TSM
world what it is when we tell the TSM to create the vPCI function..

There is a missing ioctl in this sequence, you have to register the
vdev with the viommu to create a vPCI function, and that may trigger a
TSM call too.

The registration should link the vdev to the viommu and then you can
get the viommu's kvm for a later bind.

> +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
> +{

This refcount isn't going to work, it will make an error close()
crash..

You need to auto-unbind on destruction I think.

Jason

---

## [41] Aneesh Kumar K.V — 2025-05-27
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Tue, May 27, 2025 at 05:18:01PM +0530, Aneesh Kumar K.V wrote:
>> > yeah, I guess, there is a couple of places like this

I assume you are not suggesting using IOMMU_VIOMMU_ALLOC? That would
break the ABI, which we need to maintain.

Instead, my approach uses VFIO_DEVICE_BIND_IOMMUFD to associate the KVM
context. The vfio device file descriptor had already been linked to the
KVM instance via KVM_DEV_VFIO_FILE_ADD.

Through VFIO_DEVICE_BIND_IOMMUFD, we inherit the necessary KVM details
and pass them along to iommufd_device, and subsequently to
iommufd_vdevice, using IOMMU_VDEVICE_ALLOC.

>
> We need an association between the viommu and vdevice to tell the TSM

Can you elaborate on that? if vdevice is tsm_bound,
iommufd_vdevice_destroy() do call tsm_unbind in the changes I shared.

-aneesh

---

## [42] Jason Gunthorpe — 2025-05-27
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Tue, May 27, 2025 at 07:56:09PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@nvidia.com> writes:
> 

Yes I am, what ABI are you talking about? CC is all new.

> Instead, my approach uses VFIO_DEVICE_BIND_IOMMUFD to associate the KVM
> context. The vfio device file descriptor had already been linked to the

It is not OK, we want this in the viommu not the device for a bunch of
other reasons. I don't want two copies of the KVM running around
inside iommfd..

> >> +	if (rc) {
> >> +		rc = -ENODEV;

You are driving it from the vfio side? Then you don't need the
refcount at all here because the vfio facing APIs already take one.

Jason

---

## [43] Aneesh Kumar K.V — 2025-05-28
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Tue, May 27, 2025 at 07:56:09PM +0530, Aneesh Kumar K.V wrote:
>> Jason Gunthorpe <jgg@nvidia.com> writes:

Ok, I updated the changes as below.

5 files changed, 161 insertions(+), 2 deletions(-)
drivers/iommu/iommufd/iommufd_private.h |   3 +
drivers/iommu/iommufd/main.c            |   5 ++
drivers/iommu/iommufd/viommu.c          | 134 +++++++++++++++++++++++++++++++-
include/linux/iommufd.h                 |   5 +-
include/uapi/linux/iommufd.h            |  16 ++++

modified   drivers/iommu/iommufd/iommufd_private.h
@@ -606,6 +606,8 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_viommu_destroy(struct iommufd_object *obj);
 int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_vdevice_destroy(struct iommufd_object *obj);
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd);
+int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd);
 
 struct iommufd_vdevice {
 	struct iommufd_object obj;
@@ -613,6 +615,7 @@ struct iommufd_vdevice {
 	struct iommufd_viommu *viommu;
 	struct device *dev;
 	u64 id; /* per-vIOMMU virtual ID */
+	bool tsm_bound;
 };
 
 #ifdef CONFIG_IOMMUFD_TEST
modified   drivers/iommu/iommufd/main.c
@@ -320,6 +320,7 @@ union ucmd_buffer {
 	struct iommu_veventq_alloc veventq;
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
+	struct iommu_vdevice_id vdev_id;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -379,6 +380,10 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 __reserved),
 	IOCTL_OP(IOMMU_VIOMMU_ALLOC, iommufd_viommu_alloc_ioctl,
 		 struct iommu_viommu_alloc, out_viommu_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_BIND, iommufd_vdevice_tsm_bind_ioctl,
+		 struct iommu_vdevice_id, vdevice_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_UNBIND, iommufd_vdevice_tsm_unbind_ioctl,
+		 struct iommu_vdevice_id, vdevice_id),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
modified   drivers/iommu/iommufd/viommu.c
@@ -2,6 +2,57 @@
 /* Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES
  */
 #include "iommufd_private.h"
+#include "linux/tsm.h"
+
+#if IS_ENABLED(CONFIG_KVM)
+#include <linux/kvm_host.h>
+
+static void viommu_get_kvm_safe(struct iommufd_viommu *viommu, struct kvm *kvm)
+{
+	void (*put_fn)(struct kvm *kvm);
+	bool (*get_fn)(struct kvm *kvm);
+	bool ret;
+
+	if (!kvm)
+		return;
+
+	put_fn = symbol_get(kvm_put_kvm);
+	if (WARN_ON(!put_fn))
+		return;
+
+	get_fn = symbol_get(kvm_get_kvm_safe);
+	if (WARN_ON(!get_fn)) {
+		symbol_put(kvm_put_kvm);
+		return;
+	}
+
+	ret = get_fn(kvm);
+	symbol_put(kvm_get_kvm_safe);
+	if (!ret) {
+		symbol_put(kvm_put_kvm);
+		return;
+	}
+
+	viommu->put_kvm = put_fn;
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
+#endif
 
 void iommufd_viommu_destroy(struct iommufd_object *obj)
 {
@@ -12,6 +63,8 @@ void iommufd_viommu_destroy(struct iommufd_object *obj)
 		viommu->ops->destroy(viommu);
 	refcount_dec(&viommu->hwpt->common.obj.users);
 	xa_destroy(&viommu->vdevs);
+
+	viommu_put_kvm(viommu);
 }
 
 int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
@@ -68,10 +121,32 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	 */
 	viommu->iommu_dev = __iommu_get_iommu_dev(idev->dev);
 
+	/* get the kvm details if specified. */
+	if (cmd->kvm_vm_fd) {
+		struct kvm *kvm;
+		struct fd f = fdget(cmd->kvm_vm_fd);
+
+		if (!fd_file(f)) {
+			rc = -EBADF;
+			goto out_abort;
+		}
+
+		if (!file_is_kvm(fd_file(f))) {
+			rc = -EBADF;
+			fdput(f);
+			goto out_abort;
+		}
+		kvm = fd_file(f)->private_data;
+		viommu_get_kvm_safe(viommu, kvm);
+		fdput(f);
+	}
+
 	cmd->out_viommu_id = viommu->obj.id;
 	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
-	if (rc)
+	if (rc) {
+		viommu_put_kvm(viommu);
 		goto out_abort;
+	}
 	iommufd_object_finalize(ucmd->ictx, &viommu->obj);
 	goto out_put_hwpt;
 
@@ -90,6 +165,9 @@ void iommufd_vdevice_destroy(struct iommufd_object *obj)
 		container_of(obj, struct iommufd_vdevice, obj);
 	struct iommufd_viommu *viommu = vdev->viommu;
 
+	if (vdev->tsm_bound)
+		tsm_unbind(vdev->dev);
+
 	/* xa_cmpxchg is okay to fail if alloc failed xa_cmpxchg previously */
 	xa_cmpxchg(&viommu->vdevs, vdev->id, vdev, NULL, GFP_KERNEL);
 	refcount_dec(&viommu->obj.users);
@@ -157,3 +235,57 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &viommu->obj);
 	return rc;
 }
+
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_id *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	int rc = 0;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	rc = tsm_bind(vdev->dev, vdev->viommu->kvm, vdev->id);
+	if (rc) {
+		rc = -ENODEV;
+		goto out_put_vdev;
+	}
+
+	/* locking? */
+	vdev->tsm_bound = true;
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
+
+int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_id *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	int rc = 0;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	rc = tsm_unbind(vdev->dev);
+	if (rc) {
+		rc = -ENODEV;
+		goto out_put_vdev;
+	}
+
+	/* locking ? */
+	vdev->tsm_bound = false;
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
modified   include/linux/iommufd.h
@@ -51,8 +51,9 @@ struct iommufd_object {
 	unsigned int id;
 };
 
+struct kvm;
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
-					   struct device *dev, u32 *id);
+					   struct device *dev, struct kvm *kvm, u32 *id);
 void iommufd_device_unbind(struct iommufd_device *idev);
 
 int iommufd_device_attach(struct iommufd_device *idev, ioasid_t pasid,
@@ -94,6 +95,8 @@ struct iommufd_viommu {
 	struct iommufd_ctx *ictx;
 	struct iommu_device *iommu_dev;
 	struct iommufd_hwpt_paging *hwpt;
+	struct kvm *kvm;
+	void (*put_kvm)(struct kvm *kvm);
 
 	const struct iommufd_viommu_ops *ops;
 
modified   include/uapi/linux/iommufd.h
@@ -56,6 +56,8 @@ enum {
 	IOMMUFD_CMD_VDEVICE_ALLOC = 0x91,
 	IOMMUFD_CMD_IOAS_CHANGE_PROCESS = 0x92,
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
+	IOMMUFD_CMD_VDEVICE_TSM_BIND = 0x94,
+	IOMMUFD_CMD_VDEVICE_TSM_UNBIND = 0x95,
 };
 
 /**
@@ -985,6 +987,7 @@ struct iommu_viommu_alloc {
 	__u32 dev_id;
 	__u32 hwpt_id;
 	__u32 out_viommu_id;
+	__u32 kvm_vm_fd;
 };
 #define IOMMU_VIOMMU_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VIOMMU_ALLOC)
 
@@ -1038,6 +1041,19 @@ enum iommu_veventq_flag {
 	IOMMU_VEVENTQ_FLAG_LOST_EVENTS = (1U << 0),
 };
 
+/**
+ * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)
+ * @size: sizeof(struct iommu_vdevice_id)
+ * @vdevice_id: Object handle for the vDevice. Returned from IOMMU_VDEVICE_ALLOC
+ */
+struct iommu_vdevice_id {
+	__u32 size;
+	__u32 vdevice_id;
+} __packed;
+#define IOMMU_VDEVICE_TSM_BIND _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_BIND)
+#define IOMMU_VDEVICE_TSM_UNBIND _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_UNBIND)
+
+
 /**
  * struct iommufd_vevent_header - Virtual Event Header for a vEVENTQ Status
  * @flags: Combination of enum iommu_veventq_flag



>
>> >> +	if (rc) {

I am using iommufd ioctl to bind/unbind. The goal was to call tsm_unbind
when we close the iommu file descriptor( So when a vdevice object is
destroyed).

-aneesh

---

## [44] Jason Gunthorpe — 2025-05-28
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Wed, May 28, 2025 at 05:47:19PM +0530, Aneesh Kumar K.V wrote:

> +#if IS_ENABLED(CONFIG_KVM)
> +#include <linux/kvm_host.h>

Shameer was working on something like this too

I would probably split just the viommu kvm stuff into one patch so you
two can share it.

> @@ -68,10 +121,32 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
>  	 */

Pedantically a 0 fd is still valid, you should add a flag to indicate
if the KVM is being supplied.

> +		struct kvm *kvm;
> +		struct fd f = fdget(cmd->kvm_vm_fd);

I mentioned this to Sean a while back, but can we just use the fdget
reference here and forget about kvm_get_kvm_safe()?

> +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
> +{

Yeah, that makes alot of sense now, you are passing in the KVM for the
VIOMMU and both the vBDF and pBDF to the TSM layer, that should be
enough for it to figure out what to do. The only other data would be
the TSM's VIOMMU handle..

> +int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd)
> +{

But there is no locking here so userspace could race tsm_unbind with
tsm_bind, which doesn't sound great. Shouldn't iommufd protect against
that?

You could abuse the device_lock(vdev->dev) ?

I think we still have an existing bug where the vdevice can outlive
the idevice, but that is not your issue, just FYI

Jason

---

## [45] Jason Gunthorpe — 2025-05-28
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Wed, May 28, 2025 at 01:42:25PM -0300, Jason Gunthorpe wrote:
> > +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
> > +{

Actually it should also check that the viommu type is compatible with
the TSM, somehow.

The way I imagine this working is userspace would create a 
IOMMU_VIOMMU_TYPE_TSM_VTD (for example) viommu object which will do a
TSM call to setup the secure vIOMMU

Then when you create a VDEVICE against the IOMMU_VIOMMU_TYPE_TSM_VTD
it will do a TSM call to create the secure vPCI function attached to
the vIOMMU and register the vBDF. [1]

And finally bind will switch to T=1 mode.

But if someone creates a VIOMMU with IOMMU_VIOMMU_TYPE_ARM_SMMUV3 then
the vdevice shouldn't be allowed to work in TSM mode at all.

Finally IOMMU_VIOMMU_TYPE_TSM_NO_VIOMMU would be a "NOP" viommu type
that enables TSM support but has no vIOMMU and works with all the
iommu drivers.

Not sure exactly how to wrangle this all, but it should be done
here..

1 - IMHO alot of the architectures I've seen have messed up the VIOMMU
design by having completely separate IOMMUs for T=1 and T=0 traffic. I
hope people will fix this and allow the secure VIOMMU to translate
both T=0 and T=1 traffic as walking page tables in secure memory and
then rejecting T=0 if the final physical is secure memory. Meaning
from an API perspective we want the vPCI to possibly have a working
secure vIOMMU before we reach bind.

Jason

---

## [46] Alexey Kardashevskiy — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 27/5/25 21:48, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 


At the moment I am planning getting/holding the KVM reference in the TSM:

https://lore.kernel.org/r/20250218111017.491719-15-aik@amd.com

but may push it even further to the AMD TSM (CCP, the firmware driver) as this where I actually need the kvm struct to get GCTX+ASID from kvm_svm; Intel folks have a similar intimate knowledge sharing between kvm_intel and TDX-connect. Thanks,


> 
>   drivers/iommu/iommufd/device.c          |  4 +-

---

## [47] Xu Yilun — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Wed, May 28, 2025 at 01:52:22PM -0300, Jason Gunthorpe wrote:
> On Wed, May 28, 2025 at 01:42:25PM -0300, Jason Gunthorpe wrote:
> > > +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)

Then we should have more verbose TSM APIs,
pci_tsm_tdi_create/bind/unbind/free(), which seems workable. Now
according to Dan's series, we only have bind() which creates secure
vPCI and switch to T=1, and unbind() which switch to T=0 and free secure
vPCI.

Thanks,
Yilun

> 
> And finally bind will switch to T=1 mode.

---

## [48] Aneesh Kumar K.V — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 27/5/25 21:48, Aneesh Kumar K.V wrote:
>> Alexey Kardashevskiy <aik@amd.com> writes:

So you won't be able to work with already available kvm reference in
viommu alloc? I will send the tsm_bind changes i have done so that we
can share the diff against that with explanation of why things can't
work that way?

-aneesh

---

## [49] Aneesh Kumar K.V (Arm) — 2025-05-29
*Subject: [RFC PATCH 1/3] coco: tsm: Add tsm_bind/unbind helpers*

This will be later used by iommufd bind a tdi to guest.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/tsm-core.c | 18 ++++++++++++++++++
 include/linux/tsm.h          |  3 +++
 2 files changed, 21 insertions(+)

diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index bd9e09b07412..0a7c9aa46c56 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
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

## [50] Aneesh Kumar K.V (Arm) — 2025-05-29
*Subject: [RFC PATCH 2/3] iommufd/viommu: Add support to associate viommu with kvm instance*

The associated kvm instance will be used in later patch by iommufd to
bind a tdi to kvm.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/viommu.c | 48 ++++++++++++++++++++++++++++++++--
 include/linux/iommufd.h        |  3 +++
 include/uapi/linux/iommufd.h   |  2 ++
 3 files changed, 51 insertions(+), 2 deletions(-)

diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 01df2b985f02..10d343871fb2 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -2,6 +2,37 @@
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
+	struct kvm *kvm;
+	struct fd f = fdget(kvm_vm_fd);
+
+	if (!fd_file(f) || !file_is_kvm(fd_file(f)))
+		goto err_out;
+
+	kvm = fd_file(f)->private_data;
+	if (!kvm)
+		goto err_out;
+
+	/* hold the kvm reference via file descriptor */
+	viommu->kvm_fd = f;
+	return rc;
+err_out:
+	fdput(f);
+	return rc;
+}
+
+static void viommu_put_kvm(struct iommufd_viommu *viommu)
+{
+	fdput(viommu->kvm_fd);
+}
+#endif
 
 void iommufd_viommu_destroy(struct iommufd_object *obj)
 {
@@ -12,6 +43,8 @@ void iommufd_viommu_destroy(struct iommufd_object *obj)
 		viommu->ops->destroy(viommu);
 	refcount_dec(&viommu->hwpt->common.obj.users);
 	xa_destroy(&viommu->vdevs);
+
+	viommu_put_kvm(viommu);
 }
 
 int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
@@ -23,7 +56,9 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	const struct iommu_ops *ops;
 	int rc;
 
-	if (cmd->flags || cmd->type == IOMMU_VIOMMU_TYPE_DEFAULT)
+	if (cmd->flags & ~IOMMU_VIOMMU_KVM_FD)
+		return -EOPNOTSUPP;
+	if (cmd->type == IOMMU_VIOMMU_TYPE_DEFAULT)
 		return -EOPNOTSUPP;
 
 	idev = iommufd_get_device(ucmd, cmd->dev_id);
@@ -68,10 +103,19 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	 */
 	viommu->iommu_dev = __iommu_get_iommu_dev(idev->dev);
 
+	/* get the kvm details if specified. */
+	if (cmd->flags & IOMMU_VIOMMU_KVM_FD) {
+		rc = viommu_get_kvm(viommu, cmd->kvm_vm_fd);
+		if (rc)
+			goto out_abort;
+	}
+
 	cmd->out_viommu_id = viommu->obj.id;
 	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
-	if (rc)
+	if (rc) {
+		viommu_put_kvm(viommu);
 		goto out_abort;
+	}
 	iommufd_object_finalize(ucmd->ictx, &viommu->obj);
 	goto out_put_hwpt;
 
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index 34b6e6ca4bfa..ed5c404f1b0b 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -12,6 +12,7 @@
 #include <linux/refcount.h>
 #include <linux/types.h>
 #include <linux/xarray.h>
+#include <linux/file.h>
 #include <uapi/linux/iommufd.h>
 
 struct device;
@@ -51,6 +52,7 @@ struct iommufd_object {
 	unsigned int id;
 };
 
+struct kvm;
 struct iommufd_device *iommufd_device_bind(struct iommufd_ctx *ictx,
 					   struct device *dev, u32 *id);
 void iommufd_device_unbind(struct iommufd_device *idev);
@@ -94,6 +96,7 @@ struct iommufd_viommu {
 	struct iommufd_ctx *ictx;
 	struct iommu_device *iommu_dev;
 	struct iommufd_hwpt_paging *hwpt;
+	struct fd kvm_fd;
 
 	const struct iommufd_viommu_ops *ops;
 
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index f29b6c44655e..b3b962d857c7 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -957,6 +957,7 @@ enum iommu_viommu_type {
 	IOMMU_VIOMMU_TYPE_ARM_SMMUV3 = 1,
 };
 
+#define IOMMU_VIOMMU_KVM_FD	BIT(0)
 /**
  * struct iommu_viommu_alloc - ioctl(IOMMU_VIOMMU_ALLOC)
  * @size: sizeof(struct iommu_viommu_alloc)
@@ -985,6 +986,7 @@ struct iommu_viommu_alloc {
 	__u32 dev_id;
 	__u32 hwpt_id;
 	__u32 out_viommu_id;
+	__u32 kvm_vm_fd;
 };
 #define IOMMU_VIOMMU_ALLOC _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VIOMMU_ALLOC)

---

## [51] Aneesh Kumar K.V (Arm) — 2025-05-29
*Subject: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/iommufd/iommufd_private.h |  3 +
 drivers/iommu/iommufd/main.c            |  5 ++
 drivers/iommu/iommufd/viommu.c          | 78 +++++++++++++++++++++++++
 include/uapi/linux/iommufd.h            | 15 +++++
 4 files changed, 101 insertions(+)

diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 80e8c76d25f2..a323e8b18125 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -606,6 +606,8 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_viommu_destroy(struct iommufd_object *obj);
 int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_vdevice_destroy(struct iommufd_object *obj);
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd);
+int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd);
 
 struct iommufd_vdevice {
 	struct iommufd_object obj;
@@ -613,6 +615,7 @@ struct iommufd_vdevice {
 	struct iommufd_viommu *viommu;
 	struct device *dev;
 	u64 id; /* per-vIOMMU virtual ID */
+	bool tsm_bound;
 };
 
 #ifdef CONFIG_IOMMUFD_TEST
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 3df468f64e7d..9959436d0d42 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -320,6 +320,7 @@ union ucmd_buffer {
 	struct iommu_veventq_alloc veventq;
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
+	struct iommu_vdevice_id vdev_id;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -379,6 +380,10 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 __reserved),
 	IOCTL_OP(IOMMU_VIOMMU_ALLOC, iommufd_viommu_alloc_ioctl,
 		 struct iommu_viommu_alloc, out_viommu_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_BIND, iommufd_vdevice_tsm_bind_ioctl,
+		 struct iommu_vdevice_id, vdevice_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_UNBIND, iommufd_vdevice_tsm_unbind_ioctl,
+		 struct iommu_vdevice_id, vdevice_id),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 10d343871fb2..841cbadfb259 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -134,6 +134,9 @@ void iommufd_vdevice_destroy(struct iommufd_object *obj)
 		container_of(obj, struct iommufd_vdevice, obj);
 	struct iommufd_viommu *viommu = vdev->viommu;
 
+	if (vdev->tsm_bound)
+		tsm_unbind(vdev->dev);
+
 	/* xa_cmpxchg is okay to fail if alloc failed xa_cmpxchg previously */
 	xa_cmpxchg(&viommu->vdevs, vdev->id, vdev, NULL, GFP_KERNEL);
 	refcount_dec(&viommu->obj.users);
@@ -201,3 +204,78 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &viommu->obj);
 	return rc;
 }
+
+static struct mutex *vdev_lock(struct iommufd_vdevice *vdev)
+{
+
+	if (device_lock_interruptible(vdev->dev) != 0)
+		return NULL;
+	return &vdev->dev->mutex;
+}
+DEFINE_FREE(vdev_unlock, struct mutex *, if (_T) mutex_unlock(_T))
+
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_id *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	int rc = 0;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+
+	struct mutex *lock __free(vdev_unlock) = vdev_lock(vdev);
+	if (!lock)
+		return -EINTR;
+
+	if (!vdev->tsm_bound) {
+		struct kvm *kvm;
+
+		kvm = fd_file(vdev->viommu->kvm_fd)->private_data;
+		rc = tsm_bind(vdev->dev, kvm, vdev->id);
+		if (rc) {
+			rc = -ENODEV;
+			goto out_put_vdev;
+		}
+		vdev->tsm_bound = true;
+	}
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
+
+int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_id *cmd = ucmd->cmd;
+	struct iommufd_vdevice *vdev;
+	int rc = 0;
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(vdev))
+		return PTR_ERR(vdev);
+
+	struct mutex *lock __free(vdev_unlock) = vdev_lock(vdev);
+	if (!lock)
+		return -EINTR;
+
+	if (vdev->tsm_bound) {
+		rc = tsm_unbind(vdev->dev);
+		if (rc) {
+			rc = -ENODEV;
+			goto out_put_vdev;
+		}
+		vdev->tsm_bound = false;
+	}
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+	return rc;
+}
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index b3b962d857c7..a080a64d7fda 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -56,6 +56,8 @@ enum {
 	IOMMUFD_CMD_VDEVICE_ALLOC = 0x91,
 	IOMMUFD_CMD_IOAS_CHANGE_PROCESS = 0x92,
 	IOMMUFD_CMD_VEVENTQ_ALLOC = 0x93,
+	IOMMUFD_CMD_VDEVICE_TSM_BIND = 0x94,
+	IOMMUFD_CMD_VDEVICE_TSM_UNBIND = 0x95,
 };
 
 /**
@@ -1040,6 +1042,19 @@ enum iommu_veventq_flag {
 	IOMMU_VEVENTQ_FLAG_LOST_EVENTS = (1U << 0),
 };
 
+/**
+ * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)
+ * @size: sizeof(struct iommu_vdevice_id)
+ * @vdevice_id: Object handle for the vDevice. Returned from IOMMU_VDEVICE_ALLOC
+ */
+struct iommu_vdevice_id {
+	__u32 size;
+	__u32 vdevice_id;
+} __packed;
+#define IOMMU_VDEVICE_TSM_BIND _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_BIND)
+#define IOMMU_VDEVICE_TSM_UNBIND _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_UNBIND)
+
+
 /**
  * struct iommufd_vevent_header - Virtual Event Header for a vEVENTQ Status
  * @flags: Combination of enum iommu_veventq_flag

---

## [52] Aneesh Kumar K.V — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Wed, May 28, 2025 at 01:42:25PM -0300, Jason Gunthorpe wrote:
>> > +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)

Don’t we create the vdevice before the guest starts? If I
understand correctly, we expect tsm_bind to be triggered by the guest’s
request—specifically, when it writes to /sys/bus/pci/devices/X/tsm/connect.

-aneesh

---

## [53] Xu Yilun — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Wed, May 28, 2025 at 01:42:25PM -0300, Jason Gunthorpe wrote:
> On Wed, May 28, 2025 at 05:47:19PM +0530, Aneesh Kumar K.V wrote:
> 

Did I miss something? Shameer's patch passed in struct kvm* through
iommufd_device_bind() then to viommu, and has your Reviewed-by. I'm a
little confused...

https://lore.kernel.org/all/20250319232848.GD126678@ziepe.ca/

Thanks,
Yilun

---

## [54] Jason Gunthorpe — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Thu, May 29, 2025 at 09:49:51PM +0800, Xu Yilun wrote:

> > > @@ -68,10 +121,32 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd)
> > >  	 */

He was doing something different, and IIRC posted it before viommu was merged

Jason

---

## [55] Jason Gunthorpe — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Thu, May 29, 2025 at 07:13:54PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@nvidia.com> writes:
> 

Yes, vdevice/vPCI creation is before the guest start.

> If I understand correctly, we expect tsm_bind to be triggered by the
> guest’s request—specifically, when it writes to

Yes, vdevice creation does not set the device to T=1.

If the device is T=1/0 mode is a dynamic choice controlled by the
guest.

vPCI device creation is controlled by the hypervisor and is done
before starting the VM. It just informs the TSM that a vPCI function
exists, should the TSM need to know that, which it usually will if
a secure vIOMMU is involved.

Jason

---

## [56] Jason Gunthorpe — 2025-05-29
*Subject: Re: [RFC PATCH 2/3] iommufd/viommu: Add support to associate viommu
 with kvm instance*

> +static int viommu_get_kvm(struct iommufd_viommu *viommu, int kvm_vm_fd)
> +{

Is this actually possible? Doesn't it suggest that the file refcount is
not sufficient? If not possible then remove it.

> +
> +	/* hold the kvm reference via file descriptor */

You can't store a 'struct fd', fdget is a special "fast" function that only
works within system calls. You must use the normal fget flow here.

> diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
> index f29b6c44655e..b3b962d857c7 100644

Needs a kdoc

Jason

---

## [57] Xu Yilun — 2025-05-29
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

> > > 
> > > > > + * struct pci_tsm_guest_req_info - parameter for pci_tsm_ops.guest_req()

I think this is for type safe check to some extend. The tsm driver hook
assumes the blobs are for its known format, but userspace may pass in
another format ...

> 
> 

Always return to guest. The fw error info (not raw fw error code) is
embedded in response blob.

For QEMU/IOMMUFD, Guest Request doesn't care blob data, so don't have
to judge fw_error either. Alway return to the guest and let the guest
decide what to do.

> oookay, do not use it but the fw response is still a generic thing. Whatever is specific to AMD can be packed into req/resp and QEMU/guest will handle those.

But for out-of-blob data, it is the same effort as packing into type_info.
At least we could have a clear idea, which blob is SW defined, which blob
is GHCI/GHCB defined.

Thanks,
Yilun

---

## [58] Jason Gunthorpe — 2025-05-29
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Thu, May 29, 2025 at 07:07:56PM +0530, Aneesh Kumar K.V (Arm) wrote:

> +static struct mutex *vdev_lock(struct iommufd_vdevice *vdev)
> +{

I know I suggested this, but maybe it would be happier to use a mutex
in the viommu?

What is the locking model you need for TSM calls here anyhow? Can you
concurrently call tsms for vommu creation with bind/unbind or so on?
> +/**
> + * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)

???
Why is it called vdevice_id?
Why is it packed?

The struct should be per-ioctl. Does anyone need a TSM specific argument
blob for bind?

Jason

---

## [59] Alexey Kardashevskiy — 2025-05-30
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 29/5/25 23:34, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

By "already" you mean 2/3 you posted in reply to this, do not you? :)

> I will send the tsm_bind changes i have done so that we
> can share the diff against that with explanation of why things can't

I am missing the point in having a kvm pointer in iommufd which does not do anything with the kvm struct, fget(kvm_fd) should be enough. Thanks,

> 
> -aneesh

---

## [60] Alexey Kardashevskiy — 2025-05-30
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 30/5/25 00:20, Xu Yilun wrote:
>>>>
>>>>>> + * struct pci_tsm_guest_req_info - parameter for pci_tsm_ops.guest_req()

The blobs are guest_request blobs, they enter the kernel via iommufd's viommu ioctl and viommu already has  iommu_viommu_type which is (in my tree):

enum iommu_viommu_type {
         IOMMU_VIOMMU_TYPE_DEFAULT = 0,
         IOMMU_VIOMMU_TYPE_ARM_SMMUV3 = 1,
        IOMMU_VIOMMU_TYPE_AMD_TSM = 2,
        IOMMU_VIOMMU_TYPE_AMD = 3,
  };


>>
>>

So whatever is inside such requests, the host is not told about it ever? How does DOE bouncing work on Intel then if the fw cannot ask the host to do DOE? Thanks,

>> oookay, do not use it but the fw response is still a generic thing. Whatever is specific to AMD can be packed into req/resp and QEMU/guest will handle those.
>

---

## [61] Alexey Kardashevskiy — 2025-05-30
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 30/5/25 00:09, Jason Gunthorpe wrote:
> On Thu, May 29, 2025 at 07:13:54PM +0530, Aneesh Kumar K.V wrote:
>> Jason Gunthorpe <jgg@nvidia.com> writes:

sorry but I still need clarification :)

vPCI == passed through PCI function (ethernet nic, etc), visible in guest's "lspci"

vdevice == slice (say, AMD's DTE/sDTE) of viommu device (say, AMD vIOMMU PCI device) to handle a specific vPCI


is that right?

> 
>> If I understand correctly, we expect tsm_bind to be triggered by the

I am asking (again) because with PCIe hotplug it is not done before starting the VM. Thanks,

> It just informs the TSM that a vPCI function
> exists, should the TSM need to know that, which it usually will if

---

## [62] Aneesh Kumar K.V — 2025-05-30
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Thu, May 29, 2025 at 07:07:56PM +0530, Aneesh Kumar K.V (Arm) wrote:
>

Thinking about this more, I guess we likely don’t need a lock here. I
initially added it to handle vdevice->tsm_bind, but concurrent TSM calls
are already serialized via tsm_ops_lock.

Additionally, if tsm_bind is invoked on an already bound TDI, the TSM
layer handles it gracefully. This suggests that maintaining
vdevice->tsm_bound is unnecessary.

Since we're not modifying any vdevice state here, it appears safe to
remove the vdev_lock() call?

>> +/**
>> + * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)

For both tsm_bind and tsm_unbind, we need the vdevice id. How do we pass
that?

---

## [63] Jason Gunthorpe — 2025-05-30
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Fri, May 30, 2025 at 01:00:41PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Yes

> vdevice == slice (say, AMD's DTE/sDTE) of viommu device (say, AMD vIOMMU PCI device) to handle a specific vPCI

Yes.. with general extensions of what "slice" means into the TSM
world.

vdevice is the hypervisor handle for the vPCI function the guest sees.

> > vPCI device creation is controlled by the hypervisor and is done
> > before starting the VM.

Sure, hotplug has to create the vPCI and VDEVICE before notifying the
guest of the hotplug.

Jason

---

## [64] Jason Gunthorpe — 2025-05-30
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Fri, May 30, 2025 at 02:03:00PM +0530, Aneesh Kumar K.V wrote:
> Jason Gunthorpe <jgg@nvidia.com> writes:
> 

Okay, that's a reasonable answer


> >> +struct iommu_vdevice_id {
> >> +	__u32 size;

You should have a struct attached to the ioctl, and not packed. Maybe
this is a sign you don't need two ioctls, or maybe you should have two
structs.

What you may really want is a TSM_OPERATION iommufd operation where
bind/unbind are just sub-ops there. It could unify the viommu and
vdevice related TSM ops that will be needed into one ioctl.

I think all the ops will have the same basic format of an id and a
blob of TSM specific information?

Jason

---

## [65] Xu Yilun — 2025-05-31
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Fri, May 30, 2025 at 12:54:44PM +1000, Alexey Kardashevskiy wrote:
> 
> 

That's a good point. So I think we don't have to use a 'type' field for
ioctl(IOMMUFD_VDEVICE_GUEST_REQUEST). But I didn't see these viommu_type
would be passed to TSM driver. So for this pci_tsm_guest_req kAPI, is it
still good we keep the 'type' for type safe check in TSM driver?

> 
> 

No, I just say QEMU/IOMMUFD don't care about the execution, so no need
an explicit fw_err return to them. Platform TSM driver should definitely
know about fw_err and handle it (to do DOE or anything else) internally,
but don't have to EXPLICITLY propagate these error code to up layers (TSM
core/QEMU/IOMMUFD).

Thanks,
Yilun

> > > oookay, do not use it but the fw response is still a generic thing. Whatever is specific to AMD can be packed into req/resp and QEMU/guest will handle those.
> >

---

## [66] Xu Yilun — 2025-06-01
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

> + * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)
> + * @size: sizeof(struct iommu_vdevice_id)

Hello, I see you are talking about the detailed implementation. But
could we firstly address the confusing whether this TSM Bind/Unbind
should be a VFIO uAPI or IOMMUFD uAPI?

In this thread [1], I was talking about TSM Bind/Unbind affects VFIO
behavior so they cannot be iommufd uAPIs which VFIO is not aware of.
At least TDX Connect cares about this problem now. And the conclusion
seems to be "have a VFIO_DEVICE_BIND(iommufd vdevice id), then have
VFIO reach into iommufd".

And some further findings [2] indicate this problem may also exist on
AMD when p2p is involved.

[1]: https://lore.kernel.org/all/20250515175658.GR382960@nvidia.com/
[2]: https://lore.kernel.org/all/aDnXxk46kwrOcl0i@yilunxu-OptiPlex-7050/

Thanks,
Yilun

> +
> +

---

## [67] Alexey Kardashevskiy — 2025-06-02
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 1/6/25 01:26, Xu Yilun wrote:
> On Fri, May 30, 2025 at 12:54:44PM +1000, Alexey Kardashevskiy wrote:
>>
This means that we somehow make it possible to create an Intel vdevice for the AMD TSM and now have to catch such situation  in runtime which seems wrong, we should not allow the mix in the first place. IOMMUFD is going to call the platform IOMMU code and that guy will just refuse creating a wrong viommu type.


>>
>>>>

On AMD, the host has to provide certain handles along with the guest request/response buffers and the host can get it wrong so the host may want to know if the host did a wrong call. Say, we are killing a guest and by the same time making a guest request - will the Intel fw still say "that's ok, forward the response to the guest", even if it knows it is not possible? Or SPDM session broke - the host OS won't be told until it specifically make a call other than guest request? Seems weird but okay. Thanks,


> Thanks,
> Yilun

---

## [68] Alexey Kardashevskiy — 2025-06-02
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On 1/6/25 02:25, Xu Yilun wrote:
>> + * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)
>> + * @size: sizeof(struct iommu_vdevice_id)


What will the host VFIO-PCI driver do differently? I only remember "stop mmaping to the userspace", is that all? Or, more to the point, what is that exact thing which cannot be done from QEMU? Thanks,


> At least TDX Connect cares about this problem now. And the conclusion
> seems to be "have a VFIO_DEVICE_BIND(iommufd vdevice id), then have

---

## [69] Aneesh Kumar K.V — 2025-06-02
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

Xu Yilun <yilun.xu@linux.intel.com> writes:

>> + * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)
>> + * @size: sizeof(struct iommu_vdevice_id)

Looking at your patch series, I understand the reason you need a vfio
ioctl is to call pci_request_regions_exclusive—is that correct?

In another thread, I asked whether this might be better handled by
pci_tsm instead of vfio. I'd be interested in your thoughts on that.

I also noticed you want to unbind the TDI before unmapping the BAR in
vfio. From what I understand, this should still be possible if we use an
iommufd ioctl. Either approach—a vfio or iommufd ioctl—works fine for my
needs. We can continue that discussion in your patch series thread.

-aneesh

---

## [70] Jason Gunthorpe — 2025-06-02
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Sun, Jun 01, 2025 at 12:25:15AM +0800, Xu Yilun wrote:
> > + * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)
> > + * @size: sizeof(struct iommu_vdevice_id)

I thought you guys had moved past that? VFIO doesn't have enough
information so iommufd would be a better place to make the call?

Jason

---

## [71] Jason Gunthorpe — 2025-06-02
*Subject: Re: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE
 Security Managers*

On Thu, May 15, 2025 at 10:47:20PM -0700, Dan Williams wrote:
> +static struct class *tsm_class;
> +static struct tsm_core_dev {

This is gross, do we really need to have a global?

Jason

---

## [72] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Mon, Jun 02, 2025 at 04:38:09PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

The immediate reason is to unbind the TDI before unmapping the BAR.

> 
> In another thread, I asked whether this might be better handled by

I'm not sure how is that possible.

> Either approach—a vfio or iommufd ioctl—works fine for my
> needs. We can continue that discussion in your patch series thread.

Yeah, let's discuss in that thread.

> 
> -aneesh

---

## [73] Jason Gunthorpe — 2025-06-02
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 12:25:21AM +0800, Xu Yilun wrote:

> > Looking at your patch series, I understand the reason you need a vfio
> > ioctl is to call pci_request_regions_exclusive—is that correct?

Maybe you should just do this directly, require the TSM layer to issue
an unbind if it gets any requests to change the secure EPT?

Jason

---

## [74] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Mon, Jun 02, 2025 at 02:52:52PM +1000, Alexey Kardashevskiy wrote:
> 
> 

And do unbind before zapping MMIO.

> Or, more to the point, what is that exact thing which cannot be done from QEMU? Thanks,

But kernel don't want incorrect userspace calls crash kernel, e.g. VFIO
zaps MMIO on TDI bound then KVM just crashes. So you need to check if
zapping MMIOs are allowed in VFIO, that means VFIO still needs to know
if device is bound.  Scatter BIND/UNBIND & other device controls in both
IOMMUFD & VFIO makes life harder.

Thanks,
Yilun

---

## [75] Xu Yilun — 2025-06-03
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

On Mon, Jun 02, 2025 at 02:51:53PM +1000, Alexey Kardashevskiy wrote:
> 
> 

That's good point, seems we should check if viommu type matches TSM ...
Need more investigations on it

> 
> 

For Intel, there is no 'guest_request' fw_call. Every GHCI call has
clear meaning to host (TSM driver) and host uses exact fw_calls to
complete each GHCI call.

Intel fw doesn't fill GHCI buffer, it just executes fw_call and
returns fw_err to host. Intel fw will not decide forwarding anything to
guest or not. It is the TSM driver's job to fill GHCI buffer according
to fw_call execution status.

That said, guest_request is just a QEMU selected set of GHCI commands.

For guest_request, a GHCI OK only means host has filled the response
buffer, host fills fw_err to the response buffer and guest should look
into the response buffer to see what really happened.

> Or SPDM session broke - the host OS won't be told until it specifically make a call other than guest request? Seems weird but okay. Thanks,
> 

The TDX TSM driver knows every detail of the execution of a fw_calls.

Thanks,
Yilun

> 
> > Thanks,

---

## [76] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Mon, Jun 02, 2025 at 09:47:18AM -0300, Jason Gunthorpe wrote:
> On Sun, Jun 01, 2025 at 12:25:15AM +0800, Xu Yilun wrote:
> > > + * struct iommu_vdevice_id - ioctl(IOMMU_VDEVICE_TSM_BIND/UNBIND)

Not yet.

> VFIO doesn't have enough
> information so iommufd would be a better place to make the call?

VFIO doesn't have enough information, but VFIO needs to know about
bound state. So comes the suggestion [1] that the VFIO uAPI, then VFIO
reach into iommufd for real bind.

And my implementation [2] is:

ioctl(vfio_cdev_fd, VFIO_DEVICE_TSM_BIND)
-> vfio_iommufd_tsm_bind()
   -> iommufd_device_tsm_bind()
      -> iommufd_vdevice_tsm_bind()
         -> pci_tsm_bind()

[2]: https://lore.kernel.org/all/20250529053513.1592088-1-yilun.xu@linux.intel.com/


> In this thread [1], I was talking about TSM Bind/Unbind affects VFIO
> behavior so they cannot be iommufd uAPIs which VFIO is not aware of.


> 
> Jason

---

## [77] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Mon, Jun 02, 2025 at 01:48:57PM -0300, Jason Gunthorpe wrote:
> On Tue, Jun 03, 2025 at 12:25:21AM +0800, Xu Yilun wrote:
> 

The TSM layer won't touch S-EPT, KVM manages S-EPT. 

Similarly IOMMUFD/IOMMU driver manages IOMMUPT. When p2p is
involved, still need to unbind the TDI first then unmap the BAR for
IOMMUPT.

Thanks,
Yilun

> 
> Jason

---

## [78] Aneesh Kumar K.V — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Mon, Jun 02, 2025 at 04:38:09PM +0530, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

IIUC, what you need is the below interface
int iommufd_device_tsm_unbind(struct iommufd_device *idev) so that vfio
can use vfio_iommufd_tsm_unbind() -> 	iommufd_device_tsm_unbind(vdev->iommufd_device);

The below iommufd changes can get that

static struct mutex *vdev_lock(struct iommufd_vdevice *vdev)
{
	if (mutex_lock_interruptible(&vdev->mutex) != 0)
		return NULL;
	return &vdev->mutex;
}
DEFINE_FREE(vdev_unlock, struct mutex *, if (_T) mutex_unlock(_T))

static struct mutex *idev_lock(struct iommufd_device *idev)
{
	if (mutex_lock_interruptible(&idev->igroup->lock) != 0)
		return NULL;
	return &idev->igroup->lock;
}
DEFINE_FREE(idev_unlock, struct mutex *, if (_T) mutex_unlock(_T))

int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
{
	struct iommu_vdevice_tsm_bind *cmd = ucmd->cmd;
	struct iommufd_vdevice *vdev;
	struct iommufd_device *idev;
	struct mutex *ilock __free(idev_unlock) = NULL;
	struct mutex *vlock __free(vdev_unlock) = NULL;
	struct kvm *kvm;
	int rc = 0;

	if (cmd->flags)
		return -EOPNOTSUPP;

	idev = iommufd_get_device(ucmd, cmd->dev_id);
	if (IS_ERR(idev))
		return PTR_ERR(idev);

	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
					       IOMMUFD_OBJ_VDEVICE),
			    struct iommufd_vdevice, obj);
	if (IS_ERR(vdev)) {
		rc = PTR_ERR(vdev);
		goto out_put_idev;
	}

	ilock = idev_lock(idev);
	if (!ilock) {
		rc = -EINTR;
		goto out_put_vdev;
	}

	if (idev->vdev) {
		/* if it is already bound */
		rc = -EINVAL;
		goto out_put_vdev;
	}

	vlock = vdev_lock(vdev);
	if (!vlock) {
		rc = -EINTR;
		goto out_put_vdev;
	}

	if (WARN_ON(vdev->idev)) {
		rc = -EINVAL;
		goto out_put_vdev;
	}

	kvm = vdev->viommu->kvm_filp->private_data;
	if (kvm) {
		/*
		 * tsm layer will make take care of parallel calls to tsm_bind/unbind
		 */
		rc = tsm_bind(vdev->dev, kvm, vdev->id);
		if (rc) {
			rc = -ENODEV;
			goto out_put_vdev;
		}
	} else {
		rc = -ENODEV;
		goto out_put_vdev;
	}
	idev->vdev = vdev;
	vdev->idev = idev;
	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));

out_put_idev:
	iommufd_put_object(ucmd->ictx, &idev->obj);
out_put_vdev:
	iommufd_put_object(ucmd->ictx, &vdev->obj);
	return rc;
}

static int iommufd_vdevice_tsm_unbind(struct iommufd_vdevice *vdev)
{
	int rc = -EINVAL;
	struct mutex *lock __free(vdev_unlock) = vdev_lock(vdev);
	if (!lock)
		return -EINTR;

	if (!vdev->idev) {
		tsm_unbind(vdev->dev);
		vdev->idev = NULL;
		rc = 0;
	}
	return rc;
}

/**
 * iommufd_device_tsm_unbind - Move a device out of TSM bind state
 * @idev: device to detach
 *
 * Undo iommufd_device_tsm_bind(). This removes all Confidential Computing
 * configurations, Once this completes the device is unlocked (TDISP
 * CONFIG_UNLOCKED).
 */
int iommufd_device_tsm_unbind(struct iommufd_device *idev)
{
	struct mutex *lock __free(idev_unlock) = idev_lock(idev);
	if (!lock)
		return -EINTR;

	if (!idev->vdev)
		return -EINVAL;

	iommufd_vdevice_tsm_unbind(idev->vdev);
	idev->vdev = NULL;
	return 0;
}
EXPORT_SYMBOL_NS_GPL(iommufd_device_tsm_unbind, "IOMMUFD");

int iommufd_vdevice_tsm_unbind_ioctl(struct iommufd_ucmd *ucmd)
{
	struct iommu_vdevice_tsm_unbind *cmd = ucmd->cmd;
	struct iommufd_vdevice *vdev;
	int rc = 0;

	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
					       IOMMUFD_OBJ_VDEVICE),
			    struct iommufd_vdevice, obj);
	if (IS_ERR(vdev))
		return PTR_ERR(vdev);

	rc = iommufd_device_tsm_unbind(vdev->idev);
	if (rc) {
		rc = -ENODEV;
		goto out_put_vdev;
	}
	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));

out_put_vdev:
	iommufd_put_object(ucmd->ictx, &vdev->obj);
	return rc;
}

---

## [79] Xu Yilun — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 10:30:30AM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

I see. But I'm not sure if it can be a better story than ioctl(VFIO_TSM_BIND).
You want VFIO unaware of TSM bind, e.g. try to hide pci_request/release_region(),
but make VFIO aware of TSM unbind, which seems odd ...

Thanks,
Yilun

> 
> The below iommufd changes can get that

---

## [80] Jason Gunthorpe — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 11:47:33AM +0800, Xu Yilun wrote:

> VFIO doesn't have enough information, but VFIO needs to know about
> bound state. So comes the suggestion [1] that the VFIO uAPI, then VFIO

This doesn't work, logically you are binding the vdevice, not the
idevice, the uapi should provide the vdevice id, which VFIO doesn't
have.

If you really need vfio involvement then you need callbacks, I think.

Jason

---

## [81] Jason Gunthorpe — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 12:05:42PM +0800, Xu Yilun wrote:
> On Mon, Jun 02, 2025 at 01:48:57PM -0300, Jason Gunthorpe wrote:
> > On Tue, Jun 03, 2025 at 12:25:21AM +0800, Xu Yilun wrote:

Why not? This cross layering mess has to live someplace.

If the actual issue is the KVM S-EPT interacting with TSM bind/unbind
only on Intel platforms then it would be better to address it there
and stop trying to dance around the problem in higher levels.

> Similarly IOMMUFD/IOMMU driver manages IOMMUPT. When p2p is
> involved, still need to unbind the TDI first then unmap the BAR for

Huh? I thought if the device is in T=1 mode then it's MMIO should not
be in the non-secure IOMMU page table at all for Intel? Only T=1 P2P
DMA should reach its MMIO and that goes through the TSM controlled
IOMMU which uses the S-EPT ???

Jason

---

## [82] Jason Gunthorpe — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 06:50:13PM +0800, Xu Yilun wrote:

> I see. But I'm not sure if it can be a better story than ioctl(VFIO_TSM_BIND).
> You want VFIO unaware of TSM bind, e.g. try to hide pci_request/release_region(),

request_region does not need to be done dynamically. It should be done
once when the VFIO cdev is opened. If you need some new ioctl to put
VFIO in a CC compatible mode then it should do all this stuff once. It
doesn't need to be dynamic.

I think all you want is to trigger VFIO to invalidate its MMIOs when
bind/unbind happens.

Jason

---

## [83] Jason Gunthorpe — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 10:30:30AM +0530, Aneesh Kumar K.V wrote:

> static struct mutex *vdev_lock(struct iommufd_vdevice *vdev)
> {

Dn't do things like this.

We already have scoped_cond_guard(mutex_intr) for this pattern and
there was a big debate about its design.

It doesn't make alot of sense to use that here, this is a place where
you should not use cleanup.h.

Jason

---

## [84] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Dan Williams wrote:
> Aneesh Kumar K.V wrote:
> > Dan Williams <dan.j.williams@intel.com> writes:

So with the move to add @dsm to 'struct pci_tsm' this mess goes away.
That said, it should indeed always be the case that a registered PCI
device always pins its Device Security Manager. In other words there
are no scenarios where the registered lifetime of a PCI device can
outlive the DSM because the DSM is always an ancestor.

---

## [85] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Xu Yilun wrote:
[..]
> This field is intended for out-of-blob values, like fw_ret. But fw_ret
> is specified in GHCB and is vendor specific. Other vendors may also

2 comments:

No, I do not think 'struct pci_tsm_guest_req_info' needs the
sophistication of a "type-info + type-info-len" scheme. Just make it a
64-bit @fw_ret property. The kernel has no need for that value, and
there is nothing to indicate it needs to be larger than 64-bit. Both
ends of the pipe understand what @fw_ret might contain.

Yes, this envelope definition belongs in a uapi header.

---

## [86] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Xu Yilun wrote:
> > @@ -573,10 +690,13 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
> >  			return -EBUSY;

Ok, I added pci_tdi_initialize() as a helper for low-level TSM driver
implementations of ->bind().

---

## [87] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

I do not expect this path to be taken for a guest device. IDE is not
relevant for TDIs in the guest and function0 is not a requirement guest
BDFs. I still need to add this to samples/devsec/, but the expectation
is that in "TVM mode" the presence of PCI_EXP_DEVCAP_TEE is sufficient
to route any PCI function to tsm_ops->probe().

---

## [88] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Alexey Kardashevskiy wrote:
[..]
> >>> +static int pci_tsm_accept(struct pci_dev *pdev)
> >>> +{

Hey, what's kernel development without little side-arguments about
whitespace? Will leave it alone for now.

> >>> +	if (!lock)
> >>> +		return -EINTR;

Effectively, yes. In the non-TDISP case the driver handles the MSE+BME
transition, in the TDISP case the driver also effectively handles the
same as BME+MSE are superseded by the LOCKED state.

So TVM userspace is responsible for marking the device "accepted" and the
driver checks that state before enabling the device (LOCKED -> RUN).

This also allows for kernel debug overrides of the acceptance policy,
because, in the end, the Linux kernel trusts drivers. If the TVM owner
loads a driver that ignores the "accepted" bit, that is the owner's
prerogative. If the TVM owner does not trust a driver there are multiple
knobs under the TVM's control to mitigate that mistrust.

> The alternative is - let TSM do the attestation and acceptance and
> then "modprobe tdispawaredriver tdisp=on" and change the driver to

My heartburn with that is that there is an indefinite amount of time
whereby a device is MSE + BME active without any driver to deal with the
consequences. For example, what if the device needs some form of reset /
re-initialization to quiet an engine or silence an interrupt that
immediately starts firing upon the LOCKED -> RUN transition. Userspace
is not in a good position to make judgements about the state of the
device outside of the Interface Report.

> > There are still details to work out like supporting drivers that want to
> > stay loaded over the UNLOCKED->LOCKED->RUN transitions, and whether the

Yes, I now think entry into "RUN" needs to be a driver triggered event
to maintain parity with the safety of the non-TDISP case.

[..]
> >>> @@ -135,6 +141,8 @@ struct pci_tsm_guest_req_info {
> >>>     * @bind: establish a secure binding with the TVM

Ugh, yes, it seems that joke: "debugging is a murder mystery where you
find out you were the killer the whole time." can also be true for patch
review.

> "Lets not mix HV and VM hooks in the same ops without good reason" and
> I do not see a good reason here yet.

Now that is a problem independent of the ops unification question. The
'struct pci_tsm_pf0' data-type should not be used for guest devices. I
will rework that to be a separate data-structure, but still keep
'pci_tsm_ops' unified since the signatures are identical.

> My life definitely got easier with 2 separate structures and my split
> to virt/coco/...(tsm-host.c|tsm-guest.c|tsm.c) + pci/tsm.c.

Here is the reason my thinking evolved from that comment. A primary goal
of drivers/pci/tsm.c is to give one "Device Security" lifetime model to
the PCI core. That means TSM driver discovery (host or guest) lights up
TEE I/O capabilities in the PCI topology. That supports "pci_tsm_ops +
mode flag" vs separate registration mechanisms for different ops.

I also am not perceiving the need for guest-specific ops beyond
->accept(), as part of what drove my reaction to that RFC proposal was
the quantity of proposed ops.

So today's "good reason" is the useful programming pattern of "push
complexity from core-to-leaf". Where the low-level TSM driver needs to
be "mode" aware for some operations.

---

## [89] Jason Gunthorpe — 2025-06-03
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

On Tue, Jun 03, 2025 at 03:26:47PM -0700, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]

I don't think places should be open coding "free" functions for
mutexes. We already have support for interruptable mutexes in
cleanup.h. The syntax is unfriendly and that seems to have been a
deliberate decision. Meaning if you can't stomache the syntax then
probably don't use cleanup.h, so don't open code it?

> My heartburn with that is that there is an indefinite amount of time
> whereby a device is MSE + BME active without any driver to deal with the

That sounds horrible, I'd expect a device to be largely reset and
quiet after entering T=1, otherwise I'd fear there is some way left
over junk from the non-secure state, programmed by the untrusted
hypervisor, could leak into the secure state.

Jason

---

## [90] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy wrote:
[..]
> >> The usage of these kAPIs should be in IOMMUFD, that's what I'm doing for
> >> Stage 2 patchset. I need to rebase this series, adopt suggestions from

Certainly the iommufd call signature will be in terms of iommufd_device,
but that call ultimately needs to be bus aware, because "Device
Security" is a bus specific protocol.

---

## [91] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Suzuki K Poulose wrote:
[..]
> > Ok, something like this? and iommufd will call tsm_bind()?
> 

I have been thinking about this especially with the relative ease of
creating samples/devsec/ given the existing Linux infrastructure
emulating PCI host bridges.

Why not require PCI emulation for non-PCI devices? The tipping point is
whether the relative maintenance burden of not needing to maintain
multi-bus Device Security infrastructure outweighs the complexity of
impedance matching those other buses to PCI.

Make "PCI" the lingua franca of Device Security.

---

## [92] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE
 Security Managers*

Jason Gunthorpe wrote:
> On Thu, May 15, 2025 at 10:47:20PM -0700, Dan Williams wrote:
> > +static struct class *tsm_class;

Let me restate the assumptions that led to this, because if we disagree
there then that is more interesting and may lead to a better solution.

* The "TSM" (TEE Security Manager) concept in the PCIe TDISP specification
  and, by implication, all the CC arch implementations, instantiate this
  platform object / agent as a singleton. There is one TDX Module in
  SEAM mode, one SEV-SNP CCP firmware context, one RISC-V COVE module
  etc...

* PCIe TDISP is the first of potentially a class of confidential
  computing platform capabilities that span across platforms.

* There are generally useful details that platform owners want to know,
  like number of available / in-use PCIe link encryption stream
  resources, that are suitable to publish in sysfs.

* Userspace is better served by a static /sys/class/tsm/tsm... path to those
  common attributes vs trawling through arch-specific sysfs paths. E.g.
  SEV-SNP device object for their "TSM" is on the PCI bus, the TDX
  Module device object lives on the "virtual" bus etc...

So, create a singleton tsm_core_dev to anchor attributes in that
"cross-TSM" class.

---

## [93] Dan Williams — 2025-06-03
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

Jason Gunthorpe wrote:
> On Tue, Jun 03, 2025 at 10:30:30AM +0530, Aneesh Kumar K.V wrote:
> 

The work in progress proposal to improve upon the ergonomics of
scoped_cond_guard() is the ACQUIRE() + ACQUIRE_ERR() proposal [1]. I
need to circle back with Peter about moving that forward:

https://lore.kernel.org/all/20250512185817.GA1808@noisy.programming.kicks-ass.net/

> It doesn't make alot of sense to use that here, this is a place where
> you should not use cleanup.h.

What are those situations in your mind? We can capture that in
include/linux/cleanup.h doc.

My main "don't use cleanup" is when the function still has goto for
other reasons. Make it all or nothing which is already documented that
header:

"I.e. for a given routine, convert all resources that need a "goto"
 cleanup to scope-based cleanup, or convert none of them."

---

## [94] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE
 Security Managers*

Dan Williams wrote:
> Jason Gunthorpe wrote:
> > On Thu, May 15, 2025 at 10:47:20PM -0700, Dan Williams wrote:

However, after spelling all that out it occurs to me that a class dev
already meets most of that requirement. The name of the class dev does
not matter much, and other paths can enforce that there is only one TSM
class dev registered at a time.

So userspace could lookup /sys/class/tsm/*/$attribute and as long that
is a single result, great. If that ever returns more than one instance
then we will have entered some advanced future where there are multiple
TSMs per platform.

---

## [95] Alexey Kardashevskiy — 2025-06-04
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 4/6/25 08:47, Dan Williams wrote:
> Suzuki K Poulose wrote:
> [..]

This is how virtio started, and now it has to behave like a proper PCI device, i.e. use DMA API. Or ivshmem which maps memory as "PCI" (which it is not PCI but the guest does not know it) and is deprecated now. Not the best idea to enforce PCI from day1 imho.

---

## [96] Alexey Kardashevskiy — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On 3/6/25 03:17, Xu Yilun wrote:
> On Mon, Jun 02, 2025 at 02:52:52PM +1000, Alexey Kardashevskiy wrote:
>>

>> Or, more to the point, what is that exact thing which cannot be done from QEMU? Thanks,
> 

I am confused. What is that userspace call, ioctl(VFIO_DEVICE_RESET)? The userspace (==QEMU) knows it is bound and can unbind first, no?

If it is the case of killing QEMU - then there is no usespace and then it is a matter of what fd is closed first - VFIO-PCI or IOMMUFD, we could teach IOMMUFD to hold an VFIO-PCI fd to guarantee the order. Thanks,



> 
> Thanks,

---

## [97] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy wrote:
> 
> 

VFIO is a Linux convention. PCIe TDISP is an industry standard protocol.
The goal here is not have platform leak "oh, but my bus is special"
details throughout the tree vs keep that limited to the PCIe bus adapter
drivers for these things that want to speak a TDISP-ish like language.

That said it is difficult to speak in the abstract and the proof needs
to be in demonstrating that "tipping point" I mention above has been reached.

As it is, we already have our hands full with the industry standard
mechanism for the foreseeable future.

---

## [98] Dan Williams — 2025-06-03
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> > 

Oh, sorry you said "virtio" not "vfio", but the point is still that we
have not even got one implementation of a bus Device Security protocol
upstream, let alone multiple.

---

## [99] Xu Yilun — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 11:47:14AM +1000, Alexey Kardashevskiy wrote:
> 
> 

Yes, this can be one.

> The userspace (==QEMU) knows it is bound and can unbind first, no?

The userspace can, this is the case of correct userspace call. There are
other cases of incorrect userspace call, e.g. QEMU doesn't unbind first
and just call ioctl(VFIO_DEVICE_RESET).

Thanks,
Yilun

> 
> If it is the case of killing QEMU - then there is no usespace and then it is a matter of what fd is closed first - VFIO-PCI or IOMMUFD, we could teach IOMMUFD to hold an VFIO-PCI fd to guarantee the order. Thanks,

---

## [100] Xu Yilun — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 09:14:56AM -0300, Jason Gunthorpe wrote:
> On Tue, Jun 03, 2025 at 06:50:13PM +0800, Xu Yilun wrote:
> 

But the unbind needs to be dynamic.

> 
> I think all you want is to trigger VFIO to invalidate its MMIOs when

Trigger VFIO to passively invalidate MMIOs during unbind is a TDX
specific requirement.


Another more general requirement is, VFIO needs to trigger unbind when
VFIO wants to actively invalidate MMIOs. e.g. before VFIO resets device.
That is the dynamic unbind thing.

The reason is the secure DMA silent drop issue.  Intel, and seems
AMD (Alexey please confirm) both implemented some policy in FW/HW to block
this issue. But the consequences are fatal to OS, so better we avoid
this.

[1]: https://lore.kernel.org/all/aDnXxk46kwrOcl0i@yilunxu-OptiPlex-7050/

Thanks,
Yilun

> 
> Jason

---

## [101] Xu Yilun — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 09:11:42AM -0300, Jason Gunthorpe wrote:
> On Tue, Jun 03, 2025 at 12:05:42PM +0800, Xu Yilun wrote:
> > On Mon, Jun 02, 2025 at 01:48:57PM -0300, Jason Gunthorpe wrote:

Correct.

But the p2p case may impact AMD, AMD have legacy IOMMUPT on its secure
DMA path. And if you invalidate MMIO (in turn unmaps IOMMUPT) when
bound, may trigger HW protection mechanism against DMA silent drop.

SEV-TIO Firmware Interface SPEC, Section 2.11

"If a bound TDI sends a request to the root complex, and the IOMMU detects a fault caused by host
configuration, the root complex fences the ASID from all further I/O to or from that guest. A host
fault is either a host page table fault or an RMP check violation. ASID fencing means that the
IOMMU blocks all further I/O from the root complex to the guest that the TDI was bound, and the
root complex blocks all MMIO accesses by the guest. When a guest writes to MMIO, the write is
silently dropped. When a guest reads from MMIO, the guest reads 1s."


BTW: What is ARM's secure DMA path, does it goes through independent
Secure IOPT? So for p2p when VFIO invalidates MMIO, how the Secure IOPT
react? How to avoid DMA slient drop?

Thanks,
Yilun

> 
> Jason

---

## [102] Xu Yilun — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 09:08:10AM -0300, Jason Gunthorpe wrote:
> On Tue, Jun 03, 2025 at 11:47:33AM +0800, Xu Yilun wrote:
> 

Yes. Sorry I just too lazy to provide the full API format.

The original suggestion [1] is to provide vdevice_id in VFIO uAPI.

[1] https://lore.kernel.org/all/20250515175658.GR382960@nvidia.com/

And here is a piece of the implementation in [2]:

+struct vfio_pci_tsm_bind {
+	__u32	argsz;
+	__u32	flags;
+	__u32	vdevice_id;
+	__u32	pad;
+};
+
+#define VFIO_DEVICE_TSM_BIND		_IO(VFIO_TYPE, VFIO_BASE + 22)

[2] https://lore.kernel.org/all/20250529053513.1592088-20-yilun.xu@linux.intel.com/

> 
> If you really need vfio involvement then you need callbacks, I think.

Only callback is not enough, there are cases that VFIO wants actively
invalidate MMIO, e.g. VFIO_DEVICE_RESET. In that case, VFIO needs
dynamic unbind then invalidate MMIO.

Thanks,
Yilun

> 
> Jason

---

## [103] Aneesh Kumar K.V — 2025-06-04
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Dan Williams <dan.j.williams@intel.com> writes:

> Aneesh Kumar K.V wrote:
>> Dan Williams <dan.j.williams@intel.com> writes:

We do that because we expose /sys/bus/pci/devices/<x>/tsm/connect to
guest and we have

static int pci_tsm_connect(struct pci_dev *pdev)
{
	struct pci_tsm_pf0 *tsm = to_pci_tsm_pf0(pdev->tsm);
	int rc;

        ....

      	if (tvm_mode())
		rc = __driver_idle_connect(pdev);
	else
		rc = tsm_ops->connect(pdev);



-aneesh

---

## [104] Jason Gunthorpe — 2025-06-04
*Subject: Re: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE
 Security Managers*

On Tue, Jun 03, 2025 at 05:42:05PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> > On Thu, May 15, 2025 at 10:47:20PM -0700, Dan Williams wrote:

We will be very sad if we need multiple TSMs or TSM flavours (like
PCI, CHI, whatever) down the road as single TSM was baked permanently
into the uapi.

It is far saner to have paths like /sys/class/tsm0/tsm/.. and remove
the global than take the risk that one and only one is the right
answer forever for everyone.

Jason

---

## [105] Jason Gunthorpe — 2025-06-04
*Subject: Re: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE
 Security Managers*

On Tue, Jun 03, 2025 at 06:15:00PM -0700, Dan Williams wrote:

> So userspace could lookup /sys/class/tsm/*/$attribute and as long that
> is a single result, great. If that ever returns more than one instance

Yes, exactly

Jason

---

## [106] Jason Gunthorpe — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 03, 2025 at 06:06:08PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> > On Tue, Jun 03, 2025 at 10:30:30AM +0530, Aneesh Kumar K.V wrote:

Yeah, maybe if you can get people to agree..

> > It doesn't make alot of sense to use that here, this is a place where
> > you should not use cleanup.h.

I wouldn't indent the whole function, for instance :)

And I think I saw some agreement you shouldn't do tricky things to the
holder variable, like nulling it or whatnot.. 

cleanup.h seems to be generally accepted for very simple direct
non-clever things.

Jason

---

## [107] Jason Gunthorpe — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 01:31:38PM +0800, Xu Yilun wrote:
> On Tue, Jun 03, 2025 at 09:14:56AM -0300, Jason Gunthorpe wrote:
> > On Tue, Jun 03, 2025 at 06:50:13PM +0800, Xu Yilun wrote:

That has nothing to do with request_region.

> > I think all you want is to trigger VFIO to invalidate its MMIOs when
> > bind/unbind happens.

I still think TDX is making this too hard, the S-EPT is controled by
the TSM right? Why doesn't it do the map/unmap of the MMIO as part of
the bind/unbind instead of this weird thing where the vPCI function
creation is split up between KVM and iommufd?

> Another more general requirement is, VFIO needs to trigger unbind when
> VFIO wants to actively invalidate MMIOs. e.g. before VFIO resets device.

Alexey is right here, this is a userspace problem. VFIO should block
FLR on an bound device. Userspace has to unbind as part of its FLR
flow.

Jason

---

## [108] Jason Gunthorpe — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 01:58:55PM +0800, Xu Yilun wrote:

> But the p2p case may impact AMD, AMD have legacy IOMMUPT on its secure
> DMA path. And if you invalidate MMIO (in turn unmaps IOMMUPT) when

As I understand AMD it sort of has a single translation and relies on
its RMP for security. So I think the MMIO remains mapped always in
the iommufd IOAS on AMD?

> SEV-TIO Firmware Interface SPEC, Section 2.11
> 

Sounds to me like the guest has to do things properly or the guest
gets itself killed. I wonder how feasible this really is..

> BTW: What is ARM's secure DMA path, does it goes through independent
> Secure IOPT? So for p2p when VFIO invalidates MMIO, how the Secure IOPT

On ARM T=1/0 traffic goes to two different iommu instances.

As I understand it the T=1 traffic will go through an TSM controlled
IOMMU that uses the ARM equivalent of the S-EPT for translation. Ie
the CPU and IOMMU translation are enforced to be identical.

T=0 traffic will go through an iommufd controlled iommu and it will
use the IOAS for translation.

I've also understood this is quite similar to Intel.

(IMHO this design is a mistake, but oh well)

Jason

---

## [109] Jason Gunthorpe — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 11:47:14AM +1000, Alexey Kardashevskiy wrote:

> If it is the case of killing QEMU - then there is no usespace and
> then it is a matter of what fd is closed first - VFIO-PCI or

It is the other way around VFIO holds the iommufd and it always
destroys first.

We are missing a bit where the vfio destruction of the idevice does
not clean up the vdevice too.

Jason

---

## [110] Jason Gunthorpe — 2025-06-04
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 02:39:19PM +0800, Xu Yilun wrote:
> On Tue, Jun 03, 2025 at 09:08:10AM -0300, Jason Gunthorpe wrote:
> > On Tue, Jun 03, 2025 at 11:47:33AM +0800, Xu Yilun wrote:

I don't want to pass iommufd IDs through vfio as much as possibile, it
makes no logical sense.

> > If you really need vfio involvement then you need callbacks, I think.
> 

We've already talked about reset, Alexeys solution is good it is not a
problem. Block FLR on bound devices.

Jason

---

## [111] Xu Yilun — 2025-06-05
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 09:39:00AM -0300, Jason Gunthorpe wrote:
> On Wed, Jun 04, 2025 at 02:39:19PM +0800, Xu Yilun wrote:
> > On Tue, Jun 03, 2025 at 09:08:10AM -0300, Jason Gunthorpe wrote:

OK.

Thanks,
Yilun

---

## [112] Xu Yilun — 2025-06-05
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 09:36:37AM -0300, Jason Gunthorpe wrote:
> On Wed, Jun 04, 2025 at 01:58:55PM +0800, Xu Yilun wrote:
> 

Depends on how IOMMUFD/IOMMU driver reacts to VFIO's MMIO invalidation
when bound. Legacy IOMMUPT is not controlled by firmware, but it's part
of AMD's secure DMA path, so we have to do something on VMM side.

In legacy case I assume IOMMUFD should unmap MMIO range in response to
MMIO invalidation (via DMABUF move notify), is it? Will do something
different when bound?

Anyway, seems we all agreed VFIO should ensure device unbound first,
or no MMIO invalidation. This blocks the issue from happening.

> 
> > SEV-TIO Firmware Interface SPEC, Section 2.11

I think both guest & host. If host unmaps some legacy IOMMUPT entry
delibrately or accidently, the issue happens.

> 
> > BTW: What is ARM's secure DMA path, does it goes through independent

We are on the same boat... I need to check how ARM operates on this
S-EPT equivalent, also in KVM?

Based on this I doubt ARM also has the immediate DMA silent drop issue.

Anyway, unbind the device first.

> 
> T=0 traffic will go through an iommufd controlled iommu and it will

---

## [113] Xu Yilun — 2025-06-05
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 09:31:18AM -0300, Jason Gunthorpe wrote:
> On Wed, Jun 04, 2025 at 01:31:38PM +0800, Xu Yilun wrote:
> > On Tue, Jun 03, 2025 at 09:14:56AM -0300, Jason Gunthorpe wrote:

That's good point, thanks. S-EPT is controlled by TSM, but the fact is,
unlike RMP it needs too much help from VMM side, and now KVM is the
helper. I will continue to investigate if TDX TSM driver could opt in to
become another helper and how to coordinate with KVM.

> 
> > Another more general requirement is, VFIO needs to trigger unbind when

That means VFIO should know the bound state. if VFIO cannot receive the
initial bind/unbind request from userspace, VFIO needs a callback from
IOMMUFD. I think that's what you recently suggest.

Thanks,
Yilun

> Userspace has to unbind as part of its FLR flow.
>

---

## [114] Alexey Kardashevskiy — 2025-06-05
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 4/6/25 11:54, Dan Williams wrote:
> Dan Williams wrote:
>> Alexey Kardashevskiy wrote:

"virtio" is just not a Linux convention, Windows (at least guests) uses it, and there were even punks developing physical devices implementing virtio, hence the recommendation of iommu_platform=on in QEMU command line for virtio devices.

> but the point is still that we
> have not even got one implementation of a bus Device Security protocol

And my point is that TSM does not actually do anything with PCI except SPDM/DOE which can happily live in a library or DOE (and called from CCP or TDX drivers) and the rest can be just "device", not "pci_dev". I wonder if+how nailing TSM to PCI makes your life somehow easier, it is not going to help my case. Thanks,

---

## [115] Jason Gunthorpe — 2025-06-05
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Thu, Jun 05, 2025 at 11:25:29AM +0800, Xu Yilun wrote:

> That's good point, thanks. S-EPT is controlled by TSM, but the fact is,
> unlike RMP it needs too much help from VMM side, and now KVM is the

I think it would be quite a simplification if the iommufd operation
would also cause the TSM to setup the secure MMIO directly from the
pPCI device and remove hypervisor access to it.

Then you don't need DMABUF to KVM at all.

The create vPCI call would have to specify the base virtual addresses
of all the BARs from userspace, which is probably OK as I suspose you
also cannot disable or relocate the MMIO BAR while in T=1 mode.

Jason

---

## [116] Alexey Kardashevskiy — 2025-06-06
*Subject: Re: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE
 Security Managers*

On 2/6/25 23:18, Jason Gunthorpe wrote:
> On Thu, May 15, 2025 at 10:47:20PM -0700, Dan Williams wrote:
>> +static struct class *tsm_class;

Sure we do not, such pointer happily lives in the CCP driver in my case.

---

## [117] Alexey Kardashevskiy — 2025-06-06
*Subject: Re: [PATCH v3 01/13] coco/tsm: Introduce a core device for TEE
 Security Managers*

On 4/6/25 22:14, Jason Gunthorpe wrote:
> On Tue, Jun 03, 2025 at 05:42:05PM -0700, Dan Williams wrote:
>> Jason Gunthorpe wrote:

In my tree I do just that, ccp (a5:00.5 is it) and sev-guest modules each register themselves in TSM:

aik@purico-ec3dhost ~> ls -la /sys/class/tsm/tsm0
lrwxrwxrwx 1 root root 0 Jun  6 03:29 /sys/class/tsm/tsm0 -> ../../devices/pci0000:a0/0000:a0:07.1/0000:a5:00.5/tsm/tsm0

aik@purico-ec3dhost ~> ssh tvm ls -la /sys/class/tsm/tsm0
lrwxrwxrwx 1 root root 0 Jun  6 13:29 /sys/class/tsm/tsm0 -> ../../devices/platform/sev-guest/tsm/tsm0

No globals anywhere.

---

## [118] Xu Yilun — 2025-06-06
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jun 04, 2025 at 09:37:47AM -0300, Jason Gunthorpe wrote:
> On Wed, Jun 04, 2025 at 11:47:14AM +1000, Alexey Kardashevskiy wrote:
> 

Seems there is still problem, the suggested flow is:

1. VFIO fops release
2. vfio_pci_core_close_device()
3. vfio_df_iommufd_unbind()
4.   iommufd_device_unbind()
5.     iommufd_device_destroy()
6.       iommufd_vdevice_destroy() (not implemented)
7.         iommufd_vdevice_tsm_unbind()

In step 2, vfio pci does all cleanup, including invalidate MMIO.
In step 7 vdevice does tsm unbind, this is not correct. TSM unbind
should be done before invalidating MMIO.

TSM unbind should always the first thing to do to release lockdown,
then cleanup physical device configuration.

Thanks,
Yilun

> 
> Jason

---

## [119] Jason Gunthorpe — 2025-06-06
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Fri, Jun 06, 2025 at 11:40:30PM +0800, Xu Yilun wrote:
> On Wed, Jun 04, 2025 at 09:37:47AM -0300, Jason Gunthorpe wrote:
> > On Wed, Jun 04, 2025 at 11:47:14AM +1000, Alexey Kardashevskiy wrote:

I think you'd have to re-order things so that vfio_df_iommufd_unbind()
happens before the mmio invalidate..

And if you can succeed in moving the MMIO mapping to bind/unbind then
the invalidate from vfio won't matter.

Jason

---

## [120] Dan Williams — 2025-06-06
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy wrote:
[..]
> > but the point is still that we
> > have not even got one implementation of a bus Device Security protocol

The goal is not to solve Alexey's case, the goal is to solve the TDISP
enabling problem in a way that all impacted subsystem owners (PCI,
Device core, DMA, IOMMU, VFIO/IOMMUFD, KVM, CPU arch/...), and all TSM
platform vendors are willing to accept.

"TSM" is literally a PCI-introduced term. It comes with a full
device-model and state machine for a protocol that we, OS practitioners,
have a chance to agree what it means. If another bus wants to do "Device
Security" ideally it would map as a strict subset of the TDISP model. If
/ when that happens it is easy enough for userspace to see "oh hey, bus
$foo now has tsm/connect and tsm/accept mechanisms too".

Just like the evolution of the "new_id / remove_id, and authorized" bus
attributes, other buses add workalike functionality as a matter of
course. Other buses can add "TSM" mechanisms to their device model,
"TSM" is not a device model unto itself. Similarly, nothing stops
'struct pci_dev' properties to be promoted to 'struct device' when
needed.

I note IOMMMUFD has the bulk of all the interesting cross-bus shared
work to do here and it already has a generic device object model for
that purpose. It is another example of "extend existing objects with
'Device Security' properties", not "add a new tdi_dev object to manage".

I am frustrated that we are still spinning in this philosophical debate.
In terms of progress towards the goal of "shared commons that all
impacted subsystem owners are willing to accept":

* Bjorn acked the PCI/TSM approach [1]
* Lukas is doing native CMA and SPDM work that may yield a shared
  transport for multiple use cases (SPDM/CMA and TDISP) [2]
* Greg gave a nod to the PCI/TSM staging approach [3].
* Aneesh and Suzuki are helping out with ideas [4], and fixes to move
  this forward [5]

This is not a competition, this is carrying a shared upstream burden by
consensus for the benefit of ecosystem use cases.

[1]: http://lore.kernel.org/20240419220729.GA307280@bhelgaas
[2]: https://github.com/l1k/linux/commits/doe
[3]: http://lore.kernel.org/2024120625-baggage-balancing-48c5@gregkh
[4]: http://lore.kernel.org/yq5att5f4osr.fsf@kernel.org
[5]: http://lore.kernel.org/20250311144601.145736-3-suzuki.poulose@arm.com

---

## [121] Xu Yilun — 2025-06-09
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Fri, Jun 06, 2025 at 01:34:55PM -0300, Jason Gunthorpe wrote:
> On Fri, Jun 06, 2025 at 11:40:30PM +0800, Xu Yilun wrote:
> > On Wed, Jun 04, 2025 at 09:37:47AM -0300, Jason Gunthorpe wrote:

That seems an easier solution.

> 
> And if you can succeed in moving the MMIO mapping to bind/unbind then

It still matters. If VFIO tries to invalidate MMIOs before Unbind, DMA
Silent Drop protection still triggers. Ensuring a correct bind/unbind
operation in IOMMUFD cannot make VFIO agnostic to bind/unbind.


BTW: Let me summarize what I've got about Bind-MMIO interaction.

1. All vendors need TSM Unbind first, then invalidate MMIOs, this is
   to avoid DMA Silent Drop protection which exists on all vendors.
2. TDX Connect additionally requires finer operation sequence during TSM
   Unbind, i.e. invalidate MMIOs after TDI stop and before TDI metadata
   free, this is for TDX firmware internal TDI management logic.

Thanks,
Yilun
> 
> Jason

---

## [122] Xu Yilun — 2025-06-09
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Thu, Jun 05, 2025 at 11:54:35AM -0300, Jason Gunthorpe wrote:
> On Thu, Jun 05, 2025 at 11:25:29AM +0800, Xu Yilun wrote:
> 

I thought about this for sometime. It may be possible to trigger KVM
to populate/zap the S-EPT but cannot let TSM direct setup/remove S-EPT.
RMP could be updated by a single instruction, but S-EPT update involves
generic KVM MMU flow like Page Table Page management, TLB invalidation,
even mirror EPT management (specific to x86 KVM MMU).

To make KVM populate S-EPT, we need KVM memory slots and in turn need
DMABUF.

Thanks,
Yilun

> 
> The create vPCI call would have to specify the base virtual addresses

---

## [123] Suzuki K Poulose — 2025-06-09
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On 09/06/2025 07:10, Xu Yilun wrote:
> On Thu, Jun 05, 2025 at 11:54:35AM -0300, Jason Gunthorpe wrote:
>> On Thu, Jun 05, 2025 at 11:25:29AM +0800, Xu Yilun wrote:

May be this is answered/discussed already, but why can't we use 
(vfio->fd, offset) similar to the gmem_fd for KVM memory slot ? VFIO 
could prevent mmap if the device is bound and also pervent bind, when 
there is a mapping ?

Suzuki


> 
> Thanks,

---

## [124] Jason Gunthorpe — 2025-06-09
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Mon, Jun 09, 2025 at 05:42:59PM +0100, Suzuki K Poulose wrote:

> May be this is answered/discussed already, but why can't we use (vfio->fd,
> offset) similar to the gmem_fd for KVM memory slot ? VFIO could prevent mmap

This creates a mess of circular dependencies where kvm and vfio are
both needing to hold references on each other's FDs.

Jason

---

## [125] Alexey Kardashevskiy — 2025-06-10
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On 3/6/25 14:05, Xu Yilun wrote:
> On Mon, Jun 02, 2025 at 01:48:57PM -0300, Jason Gunthorpe wrote:
>> On Tue, Jun 03, 2025 at 12:25:21AM +0800, Xu Yilun wrote:

Is not it the TDX fw which manages _S_-EPT? And the TDX host driver (what is it called btw? Intel's "CCP") registers itself as TSM in the TSM core so it is somewhere near S-EPT logic? Thanks,

> 
> Similarly IOMMUFD/IOMMU driver manages IOMMUPT. When p2p is

---

## [126] Alexey Kardashevskiy — 2025-06-10
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On 4/6/25 22:36, Jason Gunthorpe wrote:
> On Wed, Jun 04, 2025 at 01:58:55PM +0800, Xu Yilun wrote:
> 

Well, two levels with the first page table living in the guest memory + RMP for the second page table in the host memory.

> So I think the MMIO remains mapped always in
> the iommufd IOAS on AMD?

Yup.

> 
>> SEV-TIO Firmware Interface SPEC, Section 2.11

What does look especially worrying? So far the process has been pretty straightforward. Thanks,


>> BTW: What is ARM's secure DMA path, does it goes through independent
>> Secure IOPT? So for p2p when VFIO invalidates MMIO, how the Secure IOPT

---

## [127] Alexey Kardashevskiy — 2025-06-10
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On 4/6/25 15:31, Xu Yilun wrote:
> On Tue, Jun 03, 2025 at 09:14:56AM -0300, Jason Gunthorpe wrote:
>> On Tue, Jun 03, 2025 at 06:50:13PM +0800, Xu Yilun wrote:

Why does it have to be fatal to any OS? A device which suddenly stops working is not something unheard of, not a good reason to kill an OS. Blocking MMIO or DMA seems like an adequate response.


> [1]: https://lore.kernel.org/all/aDnXxk46kwrOcl0i@yilunxu-OptiPlex-7050/
>

---

## [128] Alexey Kardashevskiy — 2025-06-10
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

On 4/6/25 08:26, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]

:)

>>>>> +	if (!lock)
>>>>> +		return -EINTR;

(out of curiosity) AMD can block DMA until the guest decides it is ready and enabled IOMMU for the device, cannot TDX do the same?

And what is the consequence of MSE being enabled? It is in the guest's best interest to avoid touching MMIO before things are set up. p2p DMA?


> For example, what if the device needs some form of reset /
> re-initialization to quiet an engine or silence an interrupt that

The OS will have to ignore such interrupts, what is a problem with it?

> Userspace
> is not in a good position to make judgements about the state of the


But this is all the guest will ever need, why allow possibility of (not) dealing with IDE/DOE in the guest? We will end up with "host-connect" and "guest-connect" when talking about this, having 2 types of bind (VFIO bind and TDI bind) is already confusing people whom I tell about this TSM business. And a global pointer, why... :(

"tvm_mode == !!tsm_ops->accept" - this kind of knob should really be compile-time imho.

Is it going to be one TSM driver for TDX host and guest, sharing measurable amount of code? I am definitely missing a bigger picture here. Thanks,


> So today's "good reason" is the useful programming pattern of "push
> complexity from core-to-leaf". Where the low-level TSM driver needs to

---

## [129] Jason Gunthorpe — 2025-06-10
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 10, 2025 at 05:05:21PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Yes, 'level' is a bit unclear here.. Intel and ARM have four levels. 

 T=0 S2 lives in hypervisor memory
 T=1 S2 lives in TSM memory (S-EPT)
 T=0 S1 lives in guest shared memory
 T=1 S1 lives in guest private memory

So compared to AMD both the RMP equivalent and the secure S2 live in
TSM memory and provide protection..

I've forgotten exactly how AMD manages to secure the IOMMU S2 in
hypervisor memory, but it seemed unique to AMD.

> > > "If a bound TDI sends a request to the root complex, and the IOMMU detects a fault caused by host
> > > configuration, the root complex fences the ASID from all further I/O to or from that guest. A host

I think it makes debugging guest bugs hard if the guest explodes on an
errant DMA.

Jason

---

## [130] Jason Gunthorpe — 2025-06-10
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 10, 2025 at 02:47:32PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Yeah, I wonder the same things..

Jason

---

## [131] Alexey Kardashevskiy — 2025-06-11
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On 11/6/25 04:19, Jason Gunthorpe wrote:
> On Tue, Jun 10, 2025 at 05:05:21PM +1000, Alexey Kardashevskiy wrote:
>>

S2 lives in the host memory, unencrypted, same table can work for trusted and untrusted devices. But S2 lookup results are then checked against RMP, and this is unique to AMD.

> 
>>>> "If a bound TDI sends a request to the root complex, and the IOMMU detects a fault caused by host

Well, my machine prints IOMMU RMP event in the host's dmesg, the guest does not receive the write, the device driver barfs timeouts or errors, but nothing crashes.

> 
> Jason

---

## [132] Alexey Kardashevskiy — 2025-06-11
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for host
 TSM driver*

On 7/6/25 11:56, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]

Right, so I need to understand how this TSM makes your life easier. I did show my complete solution, still waiting to see yours or any other really. For example, DOE bouncing.


> "TSM" is literally a PCI-introduced term. It comes with a full
> device-model and state machine for a protocol that we, OS practitioners,

Quite a chunk of it is in the SPDM specs which have all sorts of bindings. No strict PCI.

VFIO started as PCI and look at it now with all these platform and mediated devices.

  > Just like the evolution of the "new_id / remove_id, and authorized" bus
> attributes, other buses add workalike functionality as a matter of
> course. Other buses can add "TSM" mechanisms to their device model,

That's because I did not do very good job explaining my TSM, my bad, I'll do better, it is too bloated now, and violates sysfs, and should integrate with Lukas'es work, my bad.

But having this all in a single built-in (1) with PCI nailed down (2), globals (3), one tsm_ops struct for both host and guest - this frustrates me.

(1) means annoyingly many reboots vs rmmod+modprobe
(2) TSM does not IDE (the platform calls the IDE library) and does not do DOE (the DOE library should, called by the platform)
(3) bites every time when there are development bugs
(4) leads to ugly "if (tvm_mode())" checks and bugs (when missed), been there, done that with my first TSM, did not like it.

1/2/3/5 are not necessary, do not really make anything simpler and most likely will requite untangling later.


Say, there are assumptions already made for IDE which I believe we do not have to make (like, same number association blocks in all streams) but it is internal IDE detail, can be changed later if needed, but the API is sane so I am ok with the limitations (thanks btw!). But the TSM just is not there yet imho. Hope it all makes sense. Trying now to move to v6.16-rc1 + dmabuf + this series as we speak so you'll hear from me soon :) Thanks,


> In terms of progress towards the goal of "shared commons that all
> impacted subsystem owners are willing to accept":

---

## [133] Xu Yilun — 2025-06-12
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 10, 2025 at 02:47:32PM +1000, Alexey Kardashevskiy wrote:
> 
> 

TDX fw writes the S-EPT entries, but to "manage" S-EPT, there are more
works for VMM.

The S-EPT related TDX fwcalls are verbose, it is not a fwcall like
"TDX_SEPT_MAP/UNMAP(gfn_range, pfn_range)" then the tree is there.

I wanna briefly describe the S-EPT fwcalls

 - A SEPT_ADD fwcall links a page-table page to a specifc S-EPT non-leaf entry.
 - A PAGE_AUG fwcall links a guest memory page to a specific leaf entry.
 - The MEM_TRACK fwcall tracks if VMM kicks all VCPUs out of guest mode, to
   ensure TLB for S-EPT are flushed/synced for every VCPU.
 - A PAGE_REMOVE fwcall clears a specific leaf entry, only when TLB
   flush are all done.

So it is KVM's job to orchestrate what a S-EPT tree should look like,
and request TDX fw to add/remove each S-EPT node one by one. TDX fw is
responsible for the security check for each adding/removing request, if
the check passed, TDX fw writes the actual S-EPT entry.

These TDX base implementations are already in linux-next.

> And the TDX host driver (what is it called btw? Intel's "CCP") registers itself as TSM in the TSM core so it is somewhere near S-EPT logic? Thanks,

Currently kvm_intel is near S-EPT for private memory, just as kvm_amd is
near RMP for private memory.

I see in AMD's solution, CCP TSM driver could directly operate RMP for
MMIO. I was trying to figure out if TDX TSM driver could also operate
MMIO part of S-EPT, but I didn't see the chance. Kicking VCPUs is not
what TSM driver could do.  Another thing is the existing KVM mirror
page table mechenism (allow me to keep simple).

Thanks,
Yilun

> 
> >

---

## [134] Xu Yilun — 2025-06-12
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jun 10, 2025 at 05:31:41PM +1000, Alexey Kardashevskiy wrote:
> 
> 

It is fatal before any recovery solution is already in the OS. There are
plenty of BUG_ON()s in kernel but from HW's POV they may not be the end
of world. If recovery is more complex than prevention from SW's POV,
let's prevent it and bail out if we failed to prevent.

AMD's ASID fence (and Intel & ARM's DMA Silent Drop protection) are the
ways to ensure security, but let's try best not to trigger them.

Thanks,
Yilun

> 
>

---

## [135] Dan Williams — 2025-06-12
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy wrote:
> 
> 

The goal is make other subsystem owner's lives easier.

I read Bjorn's ack as "oh hey, you added new PCI/TSM functionality in
the same way all other new PCI device capabilities get added with
lifetime bounded by pci_init_capabilities() and pci_destroy_dev(), and
the sysfs attributes follow normal PCI device rules too". I also expect
I have an implied ack from Lukas who also does the same lifetime for
native authentication.

Now, they are free to change their mind if new information makes them
rethink this, but I have been operating under the assumption this
question is settled. I read ARM folks as tentatively on board as well.
Greg did not balk yet either.

I expect other subsystem maintainers want to see vendor consensus before
weighing. "Ongoing debate" almost always == "wait".

> I did show my complete solution, still waiting to see yours or any
> other really.

This is a fair criticism and I hope to share more soon in the meantime
Yilun and I have been working on the skeleton pieces and samples/devsec/
to unit test the proposals.

> For example, DOE bouncing.

The tsm operations and bind have been taking up all of the focus. What
are the specific concerns around DOE bouncing proposal? The only
criteria I currently have in mind is:

* if there is common boilerplate lets make that a library helper
* a TDISP operation / state change should be atomic regardless of how
  many DOE messages are involved.

> > "TSM" is literally a PCI-introduced term. It comes with a full
> > device-model and state machine for a protocol that we, OS practitioners,

Agree, but most of the interesting potential for shared code there is
buried within the TSM implementations with TDISP we mostly sit behind
TSM calls.

I note that Lukas has spdm common code in lib/spdm/, but all of protocol
work there is not usable for TDISP since TSMs run that protocol.

> VFIO started as PCI and look at it now with all these platform and mediated devices.

Yes, and VFIO still has specific support for PCI semantics... but the
meat of your concern is below.

>   > Just like the evolution of the "new_id / remove_id, and authorized" bus
> > attributes, other buses add workalike functionality as a matter of

No need to apologize, this stuff is complicated and I needed significant
changes from v1 to v2, getting better for v3, but v4 still needed.

> But having this all in a single built-in (1) with PCI nailed down (2),
> globals (3), one tsm_ops struct for both host and guest - this

These are good review comments, and need to be addressed.

> (1) means annoyingly many reboots vs rmmod+modprobe

Once you buy the idea that a PCI device capability should have lifetime
bounded by pci_init_capabilities()/pci_destroy_dev() and attributes
defined by pci_dev_attr_groups() then the built-in design comes along
for the ride.

I do not agree that this near term developer ergonomics issue, for this
core infrastructure piece that will eventually settle and be slow moving
thereafter, should affect the long term design.

That was also another motivation for samples/devsec/, i.e. stand up an
environment that can quickly target different corners of the TSM stack
by restarting QEMU.

> (2) TSM does not IDE (the platform calls the IDE library) and does not
> do DOE (the DOE library should, called by the platform)

The rationale for this organization is that IDE is not required. TSM may
have knowledge that the link is secure by other means.

> (3) bites every time when there are development bugs

I take this as par for the course for PCI capability development. I also
expect the bulk of the development complexity to live in the low-level
TSM driver, not the TSM skeleton.

> (4) leads to ugly "if (tvm_mode())" checks and bugs (when missed), been there, done that with my first TSM, did not like it.

Fair enough. I will take a look at replacing tvm_mode() with guest
specific ops structure. It likely still ends up being the same ops
signature though.

> 1/2/3/5 are not necessary, do not really make anything simpler and
> most likely will requite untangling later.

Which dmabuf series are you trying to integrate? There is yours,
Yilun's, and Aneesh was looking to publish a third.

> so you'll hear from me soon :) Thanks,

Sounds good, the whole goal of this is get to the point where 2 vendors
agree and they can drag the 3rd vendor along.

---

## [136] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 02/13] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On Thu, 15 May 2025 22:47:21 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Link encryption is a new PCIe feature enumerated by "PCIe 6.2 section
> 7.9.26 IDE Extended Capability".

This has been sat in my to read list for too long. Sorry about that!

A few trivial things inline.

Jonathan

> ---
>  drivers/pci/Kconfig           |  14 +++++

Maybe suggest why a kernel might want to limit this?  Testing only?

> +
>  config PCI_DOE

> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> new file mode 100644

Is stream_index ever < 0?  Doesn't look like it.  So why not do this unconditionally
as it doesn't do anything if stream_index == 0?

Better yet, why not make all the parameters unsigned given I don' think any of
them can be < 0



> +	return offset;
> +}


> diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
> index ba326710f9c8..90affa69edb0 100644

Not sure we care but it's called Requests Support in the 6.2 spec at at least rather than
Cycles.


> +#define  PCI_IDE_CAP_ALG_MASK		__GENMASK(12, 8) /* Supported Algorithms */
> +#define  PCI_IDE_CAP_ALG_AES_GCM_256	0    /* AES-GCM 256 key size, 96b MAC */

If we are going to start using __GENMASK in here (which I'm in favour of) maybe we
could use _BIT()/ _BITUL() from uapi/linux/const.h as well.  Counting zeros is annoying given
the spec is all by bit number.

> +#define PCI_IDE_CTL			0x8
> +#define  PCI_IDE_CTL_FLOWTHROUGH_IDE	0x4  /* Flow-Through IDE Stream Enabled */

Why not move this comment down one line? Match where the def is.

> +#define  PCI_IDE_SEL_ADDR_2(x)		    (24 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)
> +#define  PCI_IDE_SEL_ADDR_3(x)		    (28 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)

---

## [137] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

On Thu, 15 May 2025 22:47:22 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This
Trivial stuff on this one. See inline.

Jonathan

> ---
>  Documentation/ABI/testing/sysfs-bus-pci |  45 +++

Guess the date for merge?

> +Contact:	linux-coco@lists.linux.dev
> +Description:

> diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> new file mode 100644

Not seeing an xa stuff yet.
Check the others are all needed or push them forwards to appropriate patch.

> +#include <linux/sysfs.h>
> +


> +static bool pci_tsm_pf0_group_visible(struct kobject *kobj)
> +{

Unless this is going to get more complex later

	return pdev->tsm && is_pci_tsm_pf0(pdev);

> +}
> +DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm_pf0);

> +
> +const struct attribute_group pci_tsm_auth_attr_group = {


> +static void pci_tsm_pf0_init(struct pci_dev *pdev)
> +{

Might as well put that on first line.

> +
> +	if (!(pdev->ide_cap || tee_cap))




> diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/host/tsm-core.c
> index 4f64af1a8967..51146f226a64 100644

Using device_initialize() and device_add() in probe but device_unregister()
in remove results in trivial ordering mess like this.  I'd split the
remove() path so we can take down in the reverse of setup with pci_tsm_core_unregister()
between device_del() and put_device()

This ordering thing is common enough though that maybe we can just 
not worry about it.

> +

Push whitespace change back to earlier patch.

>  	tsm_core = NULL;
>  }

Given you have linux/pci.h no need for the forwards def.


> +
> +enum pci_tsm_state {

Kernel-doc should warn on incomplete docs.  I'd add trivial comment for
INVALID to avoid that.

> + * @PCI_TSM_PF0: function0 that hosts a DOE mailbox that comprehends an
> + *		 Interface ID per potential TDI

Double space after "is" seems odd.

> + * @PCI_TSM_DOWNSTREAM: immediate Upstream Port of this device is "tsm_pf0"
> + */

How does a pci_dev indicate a type?  Maybe: Used to distinguish the type of pci_tsm object.
  
> + * @type: pci_tsm object type to disambiguate PCI_TSM_DOWNSTREAM and PCI_TSM_PF0
> + *

Missing tsm and kernel-doc warns if docs are complete.

> + * @state: reflect device initialized, connected, or bound
> + * @lock: protect @state vs pci_tsm_ops invocation

---

## [138] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 06/13] samples/devsec: Introduce a PCI
 device-security bus + endpoint sample*

On Thu, 15 May 2025 22:47:25 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Establish just enough emulated PCI infrastructure to register a sample
> TSM (platform security manager) driver and have it discover an IDE + TEE

Interesting bit of emulation.  Only real question I have
is whether you can switch from platform devices to faux bus?



> diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
> new file mode 100644

> +static const struct pci_tsm_ops devsec_pci_ops = {
> +	.probe = devsec_tsm_pci_probe,

Could this use the faux bus stuff or does it need to be a platform
device for some reason?  That support may well have crossed with this work.


> +	struct platform_device_info devsec_tsm_info = {
> +		.name = "devsec_tsm",

---

## [139] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 07/13] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Thu, 15 May 2025 22:47:26 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
> enumerates new link capabilities and status added for Gen 6 devices. One

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [140] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 08/13] PCI/IDE: Add IDE establishment helpers*

On Thu, 15 May 2025 22:47:27 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into
A few little comments inline.

Thanks,

Jonathan

> ---
>  .../ABI/testing/sysfs-devices-pci-host-bridge |  38 ++

No problem with this documentation but not I think related to this patch and
could go upstream before this?

> +
> +What:		pciDDDD:BB/streamH.R.E:DDDD:BB:DD:F

> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> index 98a51596e329..a529926647f4 100644

> +/**
> + * pci_ide_stream_enable() - after setup, enable the stream

Trivial but blank line here would I think help readability a tiny bit.

> +	return 0;
> +}

> diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
> new file mode 100644

Needed?  I'm guessing it was and isn't any more.

> +
> +#define SEL_ADDR1_LOWER_MASK GENMASK(31, 20)

ADDR_1 would be more consistent.

However, unless we are going to see a lot of these I'd personally prefer
to see this lot inline in the code.

> +	(FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |             \
> +	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK,          \

This is a case I'd just not use FIELD_PREP / GET for. Just ends up
confusing and needs definitions that make little sense on their own.
	lower_32_bits(base) & PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK
perhaps.

> +	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK,         \
> +		    FIELD_GET(SEL_ADDR1_LOWER_MASK, (limit))))

Maybe use upper_32_bits() for this one.

However it is an odd macro and I can't immediately find where it is used
so maybe just drop it?

> +
> +#define PREP_PCI_IDE_SEL_RID_2(base, domain)               \
This one I'd prefer to see inline.

> +/**
> + * struct pci_ide_partner - Per port IDE Stream settings

Why the capital S?  Seems a little inconsistent across different comments.


> + * @stream_id: unique id (within Partner Port pairing) for the stream
> + * @name: name of the stream in sysfs

---

## [141] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 09/13] PCI/IDE: Report available IDE streams*

On Thu, 15 May 2025 22:47:28 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> The limited number of link-encryption (IDE) streams that a given set of
> host bridges supports is a platform specific detail. Provide
Trivial stuff inline.

> ---
>  .../ABI/testing/sysfs-devices-pci-host-bridge | 13 ++++

Is this name specific enough given mix of link and selective streams, both of which are
limited?  Nice to use generic terms but this one feels too generic!

> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> index a529926647f4..b7561ac03405 100644

> +static struct attribute *pci_ide_attrs[] = {
> +	&dev_attr_available_secure_streams.attr,

As below. No trailing comma here.

> +};



> diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
> index 56704e851224..93be55321537 100644

One of my favourite comments :)  No comma on terminators. Let's
not make it easy to accidentally put something after them.

> +};
> +

I've no problem with this as a clean up but you could have just
used the bridge->dev.groups instead I think? If you are clearing
that out for some other use alter, mention that in the patch description.

> +};
> +

---

## [142] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 10/13] PCI/TSM: Report active IDE streams*

On Thu, 15 May 2025 22:47:29 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Given that the platform TSM owns IDE Stream ID allocation, report the
> active streams via the TSM class device. Establish a symlink from the

Do we need the name to link to include the sbdf?  Maybe just streamN
is enough. It's a little fiddly to get the spdf from where that goes, but not
that challenging.

For user ls -lf /sys/class/tsm/tsm0/* should work for instance.

I don't care strongly about this. Maybe one for Bjorn.

---

## [143] Jonathan Cameron — 2025-06-17
*Subject: Re: [PATCH v3 11/13] samples/devsec: Add sample IDE establishment*

On Thu, 15 May 2025 22:47:30 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Exercise common setup and teardown flows for a sample platform TSM
> driver that implements the TSM 'connect' and 'disconnect' flows.
Trivial comment inline.

> index 7a8d33dc54c6..aa852ac1c16d 100644
> --- a/samples/devsec/tsm.c

>  /*
>   * Reference consumer for a TSM driver "connect" operation callback. The

Ugly and it's under 80 chars on one line.


> +	if (stream_id == NR_TSM_STREAMS)
> +		return -EBUSY;

>  
>  static void devsec_tsm_disconnect(struct pci_dev *pdev)
== NR_TSM_STREAMS 
not that it really matters but it can never be greater.

> +		return;
> +

---

## [144] Alexey Kardashevskiy — 2025-07-03
*Subject: Re: [PATCH v3 08/13] PCI/IDE: Add IDE establishment helpers*

On 16/5/25 15:47, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into

The PCIe spec allows (but funnily "does not recommend") enabling the stream before the keys are programmed and one of my test devices insists on doing it this way (the other one is fine) so at least a different code should be used here? Thanks,



> +	return 0;
> +}

---

## [145] Aneesh Kumar K.V — 2025-07-07
*Subject: Re: [PATCH v3 12/13] PCI/TSM: support TDI related operations for
 host TSM driver*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 16/5/25 15:47, Dan Williams wrote:
>> From: Xu Yilun <yilun.xu@linux.intel.com>

ARM rmm spec have this as 64 bit.

-aneesh

---

## [146] dan.j.williams@intel.com — 2025-07-11
*Subject: Re: [PATCH v3 13/13] PCI/TSM: Add Guest TSM Support*

Alexey Kardashevskiy wrote:
> 
> 

Circling back to this as I go to refresh this series...

I am not worried about the host protecting itself, I am worried about
diverging from the model where the device is expected to not be active
while a driver is detached. If the device is enabled to, for example,
trigger platform errors (platform self protection from unauthorized DMA
/ interrupts), that is a difference from the non-CC case.

So this is more about symmetry of behavior with the typical non-CC case
where PCI devices are not issuing or accepting bus cycles while a driver
is detached.

> And what is the consequence of MSE being enabled?

I think the problem is reversed with MSE, you *want* errors to happen
when the driver is detached which is what happens in the non-CC case.

> It is in the guest's best interest to avoid touching MMIO before
> things are set up. p2p DMA?

Yes.

> > For example, what if the device needs some form of reset /
> > re-initialization to quiet an engine or silence an interrupt that

I don't know, but I do know that it would a bug to fix in the non-CC
case. I.e. it is a problem that need not be introduced by maintaining
"driver is in control of MSE+BME activation" (LOCKED->RUN transition).

> > Userspace
> > is not in a good position to make judgements about the state of the

FWIW between this and Aneesh's comments about the different ops needed
for guest vs host side I am going to separate them in the next version.

---

## [147] dan.j.williams@intel.com — 2025-07-12
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Jonathan Cameron wrote:
> On Thu, 15 May 2025 22:47:22 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

No, date authored / created, but the Date: tag in these ABI entries is
not generally useful, just going to drop it.

> > +Contact:	linux-coco@lists.linux.dev
> > +Description:

One line works for me.

> 
> > +}

Done.

> 
> > +

Turns out in the new version I came to the same conclusion.

> This ordering thing is common enough though that maybe we can just 
> not worry about it.

Lost that whitespace along the way...

> 
> >  	tsm_core = NULL;

Ack.

> 
> 

pci_tsm_type is gone in the new version per Aneesh's insight that it can
be derived from other data in the pci_tsm context.

> > + * @PCI_TSM_PF0: function0 that hosts a DOE mailbox that comprehends an
> > + *		 Interface ID per potential TDI

Changed to:

 @pdev: Back ref to device function, distinguishes type of pci_tsm context. 

>   
> > + * @type: pci_tsm object type to disambiguate PCI_TSM_DOWNSTREAM and PCI_TSM_PF0

Went ahead and added a simple Documentation/drivers-api/pci/tsm.rst that
includes pci-tsm.h and tsm.c. Yes, this warning was still there in the
latest version.

---

## [148] dan.j.williams@intel.com — 2025-07-12
*Subject: Re: [PATCH v3 02/13] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

Jonathan Cameron wrote:
> On Thu, 15 May 2025 22:47:21 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Yes, that is the only reason I can think of to mess with this value.
Updated the description to:

    Set a kernel max for the number of IDE streams the PCI core supports
    per device. While the PCI specification max is 256, the hardware
    platform capability for the foreseeable future is 4 to 8 streams. Bump
    this value up if you have an expert testing need.

> > +
> >  config PCI_DOE

Yeah, they are already all unsigned in the caller, done.

> 
> > +	return offset;

Yeah, that's my parallel-PCI upbringing showing. While the PCIe spec
still says "configuration cycle" in places "configuration request"
dominates. Fixed.

> 
> 

Sure.

> 
> > +#define  PCI_IDE_SEL_ADDR_2(x)		    (24 + (x) * PCI_IDE_SEL_ADDR_BLOCK_SIZE)

---

## [149] dan.j.williams@intel.com — 2025-07-12
*Subject: Re: [PATCH v3 06/13] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

Jonathan Cameron wrote:
> On Thu, 15 May 2025 22:47:25 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:
[..]
> 
> > +static struct platform_device *devsec_tsm;

Yes, this was conceived before that existed, but it is a perfect fit for
what I need here. Switched.

---

## [150] dan.j.williams@intel.com — 2025-07-14
*Subject: Re: [PATCH v3 08/13] PCI/IDE: Add IDE establishment helpers*

Jonathan Cameron wrote:
> On Thu, 15 May 2025 22:47:27 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Sure, given there are a few other things in this series that could go upstream
in advance of the TSM bits, I will pull this and those out.

> 
> > +

Ack.

> 
> > +	return 0;

Yup, good catch.

> > +
> > +#define SEL_ADDR1_LOWER_MASK GENMASK(31, 20)

It was in an earlier rev, but I dropped it for simplicity. For now,
there is no address limitations within the the stream.

> 
> > +

So this was deliberate, but does indeed look strange. Bjorn has asked,
and I agree with him, that specification terms be capitalized. So the
"Stream index" is the PCI defined number that gets programmed into
hardware registers for a Selective IDE Stream, and "stream" is the name
of the related Linux software collateral.

That is indeed too subtle. I think adding the full Selective IDE Stream
for those cases will help distinguish.

---

## [151] dan.j.williams@intel.com — 2025-07-14
*Subject: Re: [PATCH v3 09/13] PCI/IDE: Report available IDE streams*

Jonathan Cameron wrote:
> On Thu, 15 May 2025 22:47:28 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

I will update the description to call out that these are Selective IDE
Stream resources, but keep the generic name of the attribute.

If Linux ever grows Link IDE support that can come in with a different
name. Especially because the security properties of Link IDE are weaker
in the presence of switches. I.e. you need to trust a switch to
decrypt/re-crypt.

So if Link IDE support ever arrives it can call its related attribute
"available_local_secure_streams" or something similar as "Selective" and
"Link" are not saying much to an admin that has not ready the PCIe
specification.

> > diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> > index a529926647f4..b7561ac03405 100644

Fixed. ...might be worth a checkpatch update for this, my Perl-fu is
rusty though.

> 
> > +};

Sure, I will mention it.

---

## [152] dan.j.williams@intel.com — 2025-07-14
*Subject: Re: [PATCH v3 10/13] PCI/TSM: Report active IDE streams*

Jonathan Cameron wrote:
> On Thu, 15 May 2025 22:47:29 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

I had the target PCI device name in the link name before the rewrite to
name the stream with the tuple of {host_bridge_stream_id,
root_port_stream_id, endpoint_stream_id}. With that in place the stream
name is disambiguated and the PCI device name can be dropped.

> I don't care strongly about this. Maybe one for Bjorn.

The shorter name is less complicated.

---

## [153] dan.j.williams@intel.com — 2025-07-14
*Subject: Re: [PATCH v3 11/13] samples/devsec: Add sample IDE establishment*

Jonathan Cameron wrote:
> On Thu, 15 May 2025 22:47:30 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Just a missed clang-format, fixed.

> 
> 

I does not matter in practice but if the valid values are "< size" then
the invalid values are ">= size".

---

## [154] Xu Yilun — 2025-07-15
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Thu, May 29, 2025 at 07:07:56PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

Hello:

I recently have another concern about the vdevice tsm bind/unbind API.
And need your inputs.

According to this:
https://lore.kernel.org/all/aC9QPoEUw_nLHhV4@google.com/

Sean illustrates the memory in-place conversion, that the memory
owner - gmemfd should own & control the memory shareability) and
the conversion. I.e. For in-place conversion,
KVM_SET_MEMORY_ATTRIBUTES should be disabled.

Private/shared MMIO must be of in-place conversion, similarly it's
the MMIO owner should be responsible for MMIO shareability, maybe adding
some new ioctls like MMIO_CONVERT_SHARED/PRIVATE.

From previous discussion, VFIO is the MMIO owner (implement as dmabuf
exporter), so manages MMIO shareability. And IOMMUFD vdevice is the TDI
state owner for TSM bind/unbind. But MMIO shareability & TDI state are
actually correlated, do we really want to manage them in 2 components?

Thanks,
Yilun

---

## [155] Jason Gunthorpe — 2025-07-15
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jul 15, 2025 at 06:29:35PM +0800, Xu Yilun wrote:
> On Thu, May 29, 2025 at 07:07:56PM +0530, Aneesh Kumar K.V (Arm) wrote:
> > Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

Except it doesn't work like that for MMIO. Shared/private is a TDI
operation only and effects the whole device. We shouldn't split it
into two actions.

I also don't think it needs to be strictly 'in-place' as we expect the
VM to be idle on the MMIO during this change over. Faulting would be OK.

> From previous discussion, VFIO is the MMIO owner (implement as dmabuf
> exporter), so manages MMIO shareability. And IOMMUFD vdevice is the TDI

Yes, we've been over this. There are two components, we have to split
it somehow. It makes more sense for iommufd to lead the ioctls because
it has more information about the full system.

Any case where we need to get back to vfio for something needs to be
managed with a callback of some kind. We need to get a list of what
those things are.

What do all the arches need here?
 - ARM I suspect has the TDI locking operation install the MMIO in the
   secure S2, not KVM?
 - AMD just leaves the MMIO mapped all the time?
 - x86 presumably needs to carefully map/unmap to KVM and iommu in the
   right sequence or you get a MCE?

So what is the plan? You want to wrap this in DMABUF, but will there
be two DMABUFS, one for secure and one for non-secure? Is userspace
expected to map/unmap in the right sequence?

Something else?

Jason

---

## [156] Xu Yilun — 2025-07-16
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Tue, Jul 15, 2025 at 10:09:49AM -0300, Jason Gunthorpe wrote:
> On Tue, Jul 15, 2025 at 06:29:35PM +0800, Xu Yilun wrote:
> > On Thu, May 29, 2025 at 07:07:56PM +0530, Aneesh Kumar K.V (Arm) wrote:

OK. IIUC you want 1 uAPI, TSM Bind, to finish all secure configuration,
including MMIO sharebility. I think it is possible, the MMIO shareability
is fixed after TSM Bind. iommufd could fetch TDI report to get the
private/shared MMIO ranges and callback to VFIO.

> 
> I also don't think it needs to be strictly 'in-place' as we expect the

When I said "must be in-place", I mean the MMIO resource (hpa) for one gfn is
fixed, can't have 2 copies of backend as the current private/shared
memory does.

> VM to be idle on the MMIO during this change over. Faulting would be OK.

Sorry, I don't get your point about 'strictly in-place' here?

> 
> > From previous discussion, VFIO is the MMIO owner (implement as dmabuf

Yeah, for Intel TDX, basically 2 things, zap the mapping on opposite side
page table, mark the correct shareability for correct fault in.

> 
> So what is the plan? You want to wrap this in DMABUF, but will there

No I don't expect 2 dmabufs. I image shareability could be an physical
attribute of dmabuf and the callback to VFIO changes the shareability.
And VFIO, the dmabuf exporter, could notify KVM/iommufd about the
shareability change. Then KVM/iommufd unmaps their page tables.

Thanks,
Yilun

> expected to map/unmap in the right sequence?
>

---

## [157] Jason Gunthorpe — 2025-07-16
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jul 16, 2025 at 11:41:12PM +0800, Xu Yilun wrote:
> > Except it doesn't work like that for MMIO. Shared/private is a TDI
> > operation only and effects the whole device. We shouldn't split it

Am I wrong? Isn't this one action? Once you do bind you MUST have no
hypervisor mapping or x86 will explode. And once bind completes the
hypervisor mapping is unusable on all other arches.

That's one operation as far as I can tell??

> > I also don't think it needs to be strictly 'in-place' as we expect the
> 

Ok, I would not call that in place..

> > VM to be idle on the MMIO during this change over. Faulting would be OK.
> 

Here I mean the iommu page table would have to atomically change "in
place" from shared to private in a way that that is hitless to the
guest. We don't need this, IMHO.

> > Any case where we need to get back to vfio for something needs to be
> > managed with a callback of some kind. We need to get a list of what

I expect userspace to be doing this, which is why I asked about two DMABUFs..

> > So what is the plan? You want to wrap this in DMABUF, but will there
> > be two DMABUFS, one for secure and one for non-secure? Is userspace

How can this work exactly?

Does Intel put shared/private MMIO at the same guest address when it
changes around? I understand other arches do not do this.

Even if you do, the owning page table changes, right? In public mode
it has to be mapped into an ioas and in private mode there is no ioas
mapping?

Seems to me that two DMABUFs is easier than trying to teach DMABUf
about some new attribute..

Userpsace can unmap all the shared DMABUFs, do a TDI BIND, then map
private DMABUFs. DMABUFs do not change from private to shared on the
fly.

Invalidation is only an error case situation to revoke if userspace
didn't do the above sequence right.

Is that reasonable???

Jason

---

## [158] Xu Yilun — 2025-07-17
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Wed, Jul 16, 2025 at 01:31:34PM -0300, Jason Gunthorpe wrote:
> On Wed, Jul 16, 2025 at 11:41:12PM +0800, Xu Yilun wrote:
> > > Except it doesn't work like that for MMIO. Shared/private is a TDI

You are right and I'm good to this one operation.

> hypervisor mapping or x86 will explode. And once bind completes the
> hypervisor mapping is unusable on all other arches.

I agree.

> 
> > > Any case where we need to get back to vfio for something needs to be

No, The Shared bit is embedded in GPA, it toggles for shared/private
change.

> 
> Even if you do, the owning page table changes, right? In public mode

Yes.

> 
> Seems to me that two DMABUFs is easier than trying to teach DMABUf

But the shareability of each MMIO pfn should still be recorded at the
time of TDI BIND. Shareability is not only about hypervisor can map the
MMIO or not, it is mainly about Guest should access it in a shared or
private manner. According to this KVM map the pfn in EPT or S-EPT.

For MMIO, the shareability layout is the TDI's inherence which can be
get from TDI report. I.e. some MMIOs must still be accessed as shared by
guest even if the device is converted to private. So I think a private
DMABUF without sharebility layout can't support the TDI case.

The existing shareability layout for all guest memory space is recorded
in KVM via KVM_SET_MEMORY_ATTRIBUTES, but now Sean's suggestion is
giving it back to resource owners when in-place conversion makes
guest_memfd fully aware of the shareability layout.

Thanks,
Yilun

> 
> Invalidation is only an error case situation to revoke if userspace

---

## [159] Jason Gunthorpe — 2025-07-17
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Thu, Jul 17, 2025 at 04:28:15PM +0800, Xu Yilun wrote:
> > Seems to me that two DMABUFs is easier than trying to teach DMABUf
> > about some new attribute..

> Shareability is not only about hypervisor can map the
> MMIO or not, it is mainly about Guest should access it in a shared or

Yes, which is why having two dmabufs might be nice because you can
plug the public one into the EPT and the private one into the S-EPT
and SW can validate the right one is in the right place.

> For MMIO, the shareability layout is the TDI's inherence which can be
> get from TDI report. I.e. some MMIOs must still be accessed as shared by

IMHO this even more strongly says two DMABUFs. After binding you'd get
a new shared DMABUF that was limited to only the actual shared pages
while the private DMABUF would be limited to only the actual private
pages.

It is much simpler considering the current DMABUF APIs than trying to
convey per-pfn shared/private indication.

> The existing shareability layout for all guest memory space is recorded
> in KVM via KVM_SET_MEMORY_ATTRIBUTES, but now Sean's suggestion is

I would say this discussion is irrelevant to this case since we are
not doing any kind of in-place conversion.

1) At VM start the VMM gets the shared DMABUF and maps it to IOAS and
   EPT
2) Bind request comes in, VMM unmaps shared DMABUF from IOAS and EPT
   then closes it.
3) Bind is done
4) VMM opens a shared and private DMABUF FD and learns the valid
   ranges in both DMABUFs (ie what PFNS are private/shared)
5) VMM maps the shared DMABUF fragments to the EPT and IOAS
6) VMM maps the private DMABUF fragments to the S-EPT
7) Unbind request comes in, VMM unmaps both shared and private DMABUFS

For all error cases the kernel revokes all open DMABUFS and userspace
is expected to close & reopen them to recover.

From a KVM perspective when you tell it to map the DMABUF the VMM will
also tell it the shared/private, which is basically implied by the
GPA. There is no "conversion", userspace will destroy the memslot and
create new ones.

Isn't this pretty simple?

Jason

---

## [160] Xu Yilun — 2025-07-18
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Thu, Jul 17, 2025 at 09:43:33AM -0300, Jason Gunthorpe wrote:
> On Thu, Jul 17, 2025 at 04:28:15PM +0800, Xu Yilun wrote:
> > > Seems to me that two DMABUFs is easier than trying to teach DMABUf

I generally think the flow you describe is good for implementation.
But still some details, see below.

> 
> > The existing shareability layout for all guest memory space is recorded

Who decides the dmabuf be shared or private? I assume you mean
userspace, VFIO doesn't know about the shareability of each dmabuf?

> 5) VMM maps the shared DMABUF fragments to the EPT and IOAS

Userspace could set a shared only memory slot.

> 6) VMM maps the private DMABUF fragments to the S-EPT

Userspace could set a private only memory slot, but maybe the concern
is KVM can't trust userspace about the assertion of private. Like for
private memory, KVM now verifies the slot is backed by gmem before
allowing the slot to be private. This is some in-kernel contract.
Without the contract, userspace could assign arbitrary memory to KVM as
private and explode.  If VFIO is not aware of the shareability, KVM - VFIO
can't build the contract.

If VFIO should be aware of the shareability, IOMMUFD to VFIO callback is
needed after TSM bind.

> 7) Unbind request comes in, VMM unmaps both shared and private DMABUFS
> 

It is simpler on kernel side. FYR, may introduce some complexity in
userspace, this may result in 3+ dmabufs. There may be shared holes
in the BAR, and kvm slot can't be gfn sparse. This may not be a big
problem.

Thanks,
Yilun

> 
> Jason

---

## [161] Jason Gunthorpe — 2025-07-18
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Fri, Jul 18, 2025 at 05:15:42PM +0800, Xu Yilun wrote:
> > I would say this discussion is irrelevant to this case since we are
> > not doing any kind of in-place conversion.

I imagined userspace would put a flag in the ioctl to VFIO to get the
dmabuf kind it wants. VFIO would have to be told from iommufd what the
per-pfn shared/private layout is and can use that to manage the
dmabufs.

> > 5) VMM maps the shared DMABUF fragments to the EPT and IOAS
> 

I imagined kvm can query the dmabuf and learn it is all private from
VFIO. The whole dmabuf, not per-pfn. Same for #5 it can check it is
shared memory too.

I sort of imagine using the same mechanism for p2p where we can mark
memory in the dmabuf with a 'provider' indicating these details. We
will have to see.

> If VFIO should be aware of the shareability, IOMMUFD to VFIO callback is
> needed after TSM bind.

Yes, whever this list of per-PFN shared/private must be shared between
VFIO and the TSM.

> It is simpler on kernel side. FYR, may introduce some complexity in
> userspace, this may result in 3+ dmabufs. There may be shared holes

Userspace probably needs to create multiple slots for sparsity

Again this seems much better if userspace handles it and just uses
simple mostly existing KVM interfaces.

Why 3+ dmabufs? Isn't just one shared and one private per BAR?

Jason

---

## [162] Xu Yilun — 2025-07-20
*Subject: Re: [RFC PATCH 3/3] iommufd/tsm: Add tsm_bind/unbind iommufd ioctls*

On Fri, Jul 18, 2025 at 09:26:46AM -0300, Jason Gunthorpe wrote:
> On Fri, Jul 18, 2025 at 05:15:42PM +0800, Xu Yilun wrote:
> > > I would say this discussion is irrelevant to this case since we are

Yes.

On KVM side, userspace should firstly indicate the slot type in the
ioctl and KVM verifies. Nowadays, KVM accepts 'private slot', which can
be private or shared. And legacy slot, which can only be shared. We
need to introduce a new type 'private only slot', then KVM verifies
against dma-buf.  We will see how KVM folks think about it.

> 
> I sort of imagine using the same mechanism for p2p where we can mark

Yes.

> 
> > If VFIO should be aware of the shareability, IOMMUFD to VFIO callback is

Sorry, we must have 3+ KVM slots, but can have 2 dmabufs. We can map the
file offset to pfn ranges.

KVM slot can't be for sparse GFNs. If there is a shared hole inside
private space in the same bar, e.g.

0x10000000 - 0x10001fff    private
0x10002000 - 0x10002fff    shared
0x10003000 - 0x101fffff    private

We need 3 slots.

Thanks,
Yilun

> 
> Jason

---

## [163] Alexey Kardashevskiy — 2025-08-26
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

On 16/5/25 15:47, Dan Williams wrote:
> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This

Here it is: struct pci_tsm_pf0 *tsm  (it is really a "dsm")
In pci_tsm: struct pci_dev *dsm (alright)

May be we need some distinction between PF0's pci_dev and pci_tsm_pf0 but still these are DSMs.

In pci_tsm_pf0 it is: struct pci_tsm tsm, imho "base" is less confusing (I keep catching myself thinking it is a pointer to tsm_dev).

"tsm" would be what you call "tsm_dev" which is ok but seeing short "tsm" used as "dsm" or "TSM data for this pci_dev" is confusing.

s/pci_tsm/pci_tsm_ctx/ and s/tsm/tsm_ctx/ ? Thanks,

---

## [164] Alexey Kardashevskiy — 2025-08-26
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

On 16/5/25 15:47, Dan Williams wrote:
> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This


This does not belong here yet - no user.

But if you still want it - "enum pci_doe_proto" should go to pci-doe.h like this https://github.com/AMDESE/linux-kvm/commit/af12dec97ed98a9f365bbbb6925e76c556937d01

> +{
> +	struct pci_tsm_pf0 *tsm;

The wrapper does not seem to be very helpful - the platform driver (==TSM ==CCP) which is going to call it already knows it is a DSM and mailboxes are initialized (otherwise the DSM's pci_tsm_ops::probe() would've failed) so it can just call pci_doe() directly. Thanks,

---

## [165] Alexey Kardashevskiy — 2025-08-26
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

On 16/5/25 15:47, Dan Williams wrote:
> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This

select TSM

as otherwise:

|| ld: drivers/pci/ide.o: in function `pci_ide_stream_release':
drivers/pci/ide.c|276| (.text+0x620): undefined reference to `tsm_ide_stream_unregister'
|| ld: drivers/pci/tsm.o: in function `pci_tsm_pf0_destructor':
drivers/pci/tsm.c|434| (.text+0xa1): undefined reference to `tsm_pci_group'
ld: /home/aik/p/tsm/drivers/pci/tsm.c|435| (.text+0xae): undefined reference to `tsm_pci_group'
|| ld: drivers/pci/tsm.o: in function `connect_show':
drivers/pci/tsm.c|201| (.text+0x1a4): undefined reference to `tsm_name'
|| ld: drivers/pci/tsm.o: in function `pci_tsm_register':
drivers/pci/tsm.c|462| (.text+0x28e): undefined reference to `tsm_pci_ops'

etc.

but this is kinda wrong as it is quite bizarre to call drivers/virt/coco/tsm-core.c's tsm_ide_stream_unregister() from drivers/pci/ide.c's pci_ide_stream_release(), i.e. "virt" from "pci core". imho the caller of pci_ide_stream_release() should just call tsm_ide_stream_unregister() too, and so on. Thanks,

---

## [166] dan.j.williams@intel.com — 2025-08-26
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
[..]
[trim multiple pages of uncommented context, please trim your replies]

> > +/**
> > + * pci_tsm_pf0_initialize() - common 'struct pci_tsm_pf0' initialization

All of the context returned by the TSM driver is a "tsm" context, the
only time use "dsm" is in referring to the actual pci_dev that runs the
SPDM session.

> In pci_tsm: struct pci_dev *dsm (alright)
> 

Ok, I can change it to base.

> "tsm" would be what you call "tsm_dev" which is ok but seeing short "tsm" used as "dsm" or "TSM data for this pci_dev" is confusing.
> 

What is a tsm_ctx? The s/pci_tsm/pci_tsm_ctx/ rename is not adding more
clarity for me. If Aneesh or Yilun also find that rename clarifying I
will switch. For v5 I will stick with 'struct pci_tsm' as the PCI object
that wraps TSM driver produced objects.

The reason I do not think of "pci_tsm" as a "tsm_dev" is because PCI is
always a consumer of an outside of PCI TSM service provided, PCI does
not have a TSM concept internal to it.

---

## [167] dan.j.williams@intel.com — 2025-08-26
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
[..trim reply..]
> > +int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
> > +			 const void *req, size_t req_sz, void *resp,

I had been pulling things out without users, but Yilun and Aneesh ask
for them to be included for staging purposes. When this staging branch
goes upstream a user for all exported APIs is a requirement. However,
per your comment below this is worth deleting.

> 
> But if you still want it - "enum pci_doe_proto" should go to pci-doe.h like this https://github.com/AMDESE/linux-kvm/commit/af12dec97ed98a9f365bbbb6925e76c556937d01

Yeah, I will move it over there.

> > +{
> > +	struct pci_tsm_pf0 *tsm;

True, this is a weak helper the TSM driver already knows when and if it
should be using the already exported pci_doe().

---

## [168] dan.j.williams@intel.com — 2025-08-26
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
[..]
> > diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
> > index 0c662f9813eb..5c3f896ac9f4 100644

Yup, already in v5.

> etc.
> 

So I agree it is odd, and I orginally did not have this tie until the
DEFINE_FREE(pci_ide_stream_release, ...) proposal. With that I want to
allow for TSM drivers to teardown everything associated with IDE setup
with one scope-based-cleanup helper.

It is not a mid-layer because nothing requires a TSM driver to call
tsm_ide_stream_register(), but if they do register it then the PCI core
helper will handle cleaning it up on error along with the rest of the
resources.

---

## [169] Alexey Kardashevskiy — 2025-08-27
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

On 27/8/25 09:54, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..]

ah ok. Just seems a bit counterintuitive to use a short "tsm" acronym for something else than the actual TSM as defined in the PCI spec and in this case - it is the opposite to the spec's "TSM" - it is a DSM, the other end of trust chain. And if I wanted to reference the actual TSM in the same function - that would be "tsm_dev".⁠⁠⁠⁠⁠ And the actual DSM pci_dev is barely used, it is mostly "struct pci_tsm_pf0".


>> In pci_tsm: struct pci_dev *dsm (alright)
>>

TSM-related attributes of a PCI device. Not the best name, true.

> If Aneesh or Yilun also find that rename clarifying I
> will switch. For v5 I will stick with 'struct pci_tsm' as the PCI object
yeah, if it is just me, then never mind, I'll get used to it.

> The reason I do not think of "pci_tsm" as a "tsm_dev" is because PCI is
> always a consumer of an outside of PCI TSM service provided, PCI does
"struct pci_dev" describes a PCI device, "struct pci_ide" - a PCI IDE stream but "struct pci_tsm" does not describe PCI TSM... Hm. Thanks,

---

## [170] Alexey Kardashevskiy — 2025-08-27
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

On 27/8/25 10:15, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..]

I see but imho DEFINE_FREE() is weak justification for such cross-subsystem jumping, still. I was looking at the linker error as, like, "find a Wally". May be then drop EXPORT_SYMBOL_GPL() for tsm_ide_stream_unregister()? Thanks,

---

## [171] Alexey Kardashevskiy — 2025-08-27
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

On 27/8/25 09:58, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..trim reply..]


I did not mean to drop it just because of no users but it could stay in a separate patch as this one is quite big (679 insertions) and no-users stuff just adds unnecessary noise.

>>
>> But if you still want it - "enum pci_doe_proto" should go to pci-doe.h like this https://github.com/AMDESE/linux-kvm/commit/af12dec97ed98a9f365bbbb6925e76c556937d01

right, thanks,

---

## [172] dan.j.williams@intel.com — 2025-08-28
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
> 
> 

The "dsm" pci_dev is used for type-checking assignable subfunctions vs the
device that runs the SPDM session, and it is used as the device to lock
when running operations on any subfunction.

> >> In pci_tsm: struct pci_dev *dsm (alright)
> >>

How about keep ->tsm as the short name in 'struct pci_dev', but rename
the type 'struct pci_tsm_ctl'? It is a core control data structure for
TSM operations. It is not a "context" like device drvdata where the
owner can do whatever it wants, it is a core control structure that a
low-level TSM driver can wrap with its own control attributes.

---

## [173] dan.j.williams@intel.com — 2025-08-28
*Subject: Re: [PATCH v3 03/13] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
[..]
> >> but this is kinda wrong as it is quite bizarre to call
> >> drivers/virt/coco/tsm-core.c's tsm_ide_stream_unregister() from

Interesting, I do not see 'struct pci_ide' understanding that one of the
primary methods of establishing IDE (coordination through a TSM) as
cross-subsystem jumping. It is unlikely that Linux will ever understand
IDE establishment in any other form especially because, as far as I
understand, all but Intel platforms enforce IDE establishment through
TSM ABI calls.

> still. I was looking at the linker error as, like, "find a Wally".

not sure what that means...
 
>May be then drop EXPORT_SYMBOL_GPL() for tsm_ide_stream_unregister()?

True, that can be dropped now.

---
