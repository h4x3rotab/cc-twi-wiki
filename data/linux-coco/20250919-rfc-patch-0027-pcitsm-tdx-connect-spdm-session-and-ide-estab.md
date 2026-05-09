---
title: '[RFC PATCH 00/27] PCI/TSM: TDX Connect: SPDM Session and IDE Establishment'
date: 2025-09-19
last_reply: 2025-11-17
message_count: 59
participants: ['Dan Williams', 'Huang, Kai', 'Samuel Ortiz', 'Xu Yilun', 'Jonathan Cameron']
---

## [1] Dan Williams — 2025-09-19

Add a PCI/TSM low-level driver implemenation for TDX Connect (the TEE
I/O architecture for Intel platforms). Recall that PCI/TSM [1] is the
Linux PCI core subsystem for interfacing with platform Trusted Execution
Environment (TEE) Security Managers (TSMs). TSMs establish secure
sessions with PCIe devices (SPDM over Data Object Exchange (DOE)
mailboxes) and establish PCIe link Integrity and Data Encryption (IDE).

The motivation for sending this out as an RFC with open TODOs beyond
"release early, release often" is:

- Get out of the phase of PCI/TSM core updates being done with only
  samples/devsec/ testing, i.e. avoid regressions like [2]

- Enable better collaboration on follow on common infrastructure like
  address association setup

- Take another step closer to the "at least two vendor implementations
  in #staging" threshold in a potential first intercept of v6.19.

This SPDM and IDE facility is enabled with TDX via a new capability
called a TDX Module Extension. An extension, as might be expected, is a
family of new seamcalls. Unlike typical base module seamcalls, an
extension supports preemptible calls for long running flows like SPDM
session establishment. This extension capability was added in response
to Intel Linux team feedback and in support of reducing the complexity
of the Linux implementation. The result is sequences like the following:

        guard(mutex)(&tdx_ext_lock);
        do {
                r = tdh_spdm_connect(tlink->spdm_id, tlink->spdm_conf,
                                     tlink->in_msg, tlink->out_msg,
                                     dev_info, &out_msg_sz);
                ret = tdx_link_event_handler(tlink, r, out_msg_sz);
        } while (ret == -EAGAIN);

...where tdh_spdm_connect() is a seamcall that may return early if this
CPU takes a hardirq or if the module needs a DOE message marshalled to
the device. tdx_link_event_handler() marshals the message and the
extension is resumed to continue the flow. In this case the TDX Connect
extension supports 1 caller at a time, think of it like a queue-depth of
one device-firmware command queue, so concurrency is managed with
@tdx_ext_lock.

This series and its base commit are available in tsm.git#tdx [3]. The
base commit includes devsec-20250911 and two in progress proposals,
"always enable VMX", and "refactor TDX CPU enabling into tdx_enable()".
I am holding off on putting this series in #staging because that VMX
work also includes an untested proposed cleanup to AMD SVM. If someone
has cycles to test this commit on AMD it would be greatly appreciated:

9d5a519d61d3 x86/boot, KVM: SVM: Move enabling/disabling SVM to CPU startup/shutdown phase

Not posting those proposals for now to focus on the PCI/TSM aspects of
this and save the deeper KVM implications of "TDX Host Services", for a
later time.

[1]: PCI/TSM: Core infrastructure for PCI device security (TDISP)
     http://lore.kernel.org/20250911235647.3248419-1-dan.j.williams@intel.com
[2]: http://lore.kernel.org/eeca3820-01dd-4abc-a437-cf46dc718ab6@amd.com
[3]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=tdx

Chao Gao (1):
  coco/tdx-host: Introduce a "tdx_host" device

Dave Jiang (3):
  ACPICA: Add KEYP table definitions
  acpi: Add KEYP support to fw_table parsing
  acpi: Add KEYP Key Configuration Unit parsing

Lu Baolu (2):
  iommu/vt-d: Cache max domain ID to avoid redundant calculation
  iommu/vt-d: Reserve the MSB domain ID bit for the TDX module

Xu Yilun (16):
  x86/virt/tdx: Move bit definitions of TDX_FEATURES0 to public header
  coco/tdx-host: Support Link TSM for TDX host
  x86/virt/tdx: Move tdx_errno.h from KVM to public place
  x86/virt/tdx: Add tdx_page_array helpers for new TDX Module objects
  TODO: x86/virt/tdx: Read TDX global metadata for TDX Module Extensions
  x86/virt/tdx: Add tdx_enable_ext() to enable of TDX Module Extensions
  TODO: x86/virt/tdx: Read TDX Connect global metadata for TDX Connect
  x86/virt/tdx: Extend tdx_page_array to support IOMMU_MT
  iommu/vt-d: Export a helper to do function for each dmar_drhd_unit
  coco/tdx-host: Setup all trusted IOMMUs on TDX Connect init
  coco/tdx-host: Add connect()/disconnect() handlers prototype
  PCI: iov: Export pci_iov_virtfn_bus()
  PCI/IDE: Add helpers for RID/Addr Association Registers setup
  PCI/IDE: Export pci_ide_domain()
  x86/virt/tdx: Add SEAMCALL wrappers for IDE stream management
  coco/tdx-host: Implement IDE stream setup/teardown

Zhenzhong Duan (5):
  x86/virt/tdx: Add SEAMCALL wrappers for TDH.EXT.MEM.ADD and
    TDH.EXT.INIT
  x86/virt/tdx: Add SEAMCALL wrappers for trusted IOMMU setup and clear
  coco/tdx-host: Add a helper to exchange SPDM messages through DOE
  x86/virt/tdx: Add SEAMCALL wrappers for SPDM management
  coco/tdx-host: Implement SPDM session setup

 arch/x86/include/asm/tdx.h                    |  58 ++
 arch/x86/{kvm/vmx => include/asm}/tdx_errno.h |   8 +-
 arch/x86/include/asm/tdx_global_metadata.h    |  14 +
 arch/x86/kvm/vmx/tdx.h                        |   1 -
 arch/x86/virt/vmx/tdx/tdx.c                   | 731 +++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.h                   |  17 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  32 +
 drivers/acpi/Kconfig                          |  12 +
 drivers/acpi/Makefile                         |   2 +
 drivers/acpi/pci_root.c                       |   2 +
 drivers/acpi/tables.c                         |  14 +-
 drivers/acpi/x86/keyp.c                       | 118 +++
 drivers/iommu/intel/dmar.c                    |  44 +
 drivers/iommu/intel/iommu.c                   |  10 +-
 drivers/iommu/intel/iommu.h                   |   1 +
 drivers/pci/ide.c                             |   3 +-
 drivers/pci/iov.c                             |   1 +
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Kconfig            |  17 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 942 ++++++++++++++++++
 include/acpi/actbl3.h                         |  60 ++
 include/linux/acpi.h                          |  16 +
 include/linux/dmar.h                          |   2 +
 include/linux/fw_table.h                      |   1 +
 include/linux/gfp.h                           |   2 +
 include/linux/mm.h                            |   2 +
 include/linux/pci-ide.h                       |  15 +
 lib/fw_table.c                                |   9 +
 30 files changed, 2121 insertions(+), 17 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm}/tdx_errno.h (87%)
 create mode 100644 drivers/acpi/x86/keyp.c
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c


base-commit: 0d1fbc1f1b7a3c8b14a643303dd89bcc82d3fbd0

---

## [2] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 01/27] coco/tdx-host: Introduce a "tdx_host" device*

From: Chao Gao <chao.gao@intel.com>

TDX depends on a platform firmware module that is invoked via instructions
similar to vmenter (i.e. enter into a new privileged "root-mode" context to
manage private memory and private device mechanisms). It is a software
construct that depends on the CPU vmxon state to enable invocation of
TDX-module ABIs. Unlike other Trusted Execution Environment (TEE) platform
implementations that employ a firmware module running on a PCI device with
an MMIO mailbox for communication, TDX has no hardware device to point to
as the TEE Secure Manager (TSM).

Create a virtual device not only to align with other implementations but
also to make it easier to

 - expose metadata (e.g., TDX module version, seamldr version etc) to
   the userspace as device attributes

 - implement firmware uploader APIs which are tied to a device. This is
   needed to support TDX module runtime updates

 - enable TDX Connect which will share a common infrastructure with other
   platform implementations. In the TDX Connect context, every
   architecture has a TSM, represented by a PCIe or virtual device. The
   new "tdx_host" device will serve the TSM role.

A faux device is used as for TDX because the TDX module is singular within
the system and lacks associated platform resources. Using a faux device
eliminates the need to create a stub bus.

The call to tdx_enable() makes the new module independent of kvm_intel.ko.
For example, TDX Connect may be used to established to PCIe link encryption
even if a TVM is never launched.  For now, just create the common loading
infrastructure.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/Kconfig             |  2 ++
 drivers/virt/coco/Makefile            |  1 +
 drivers/virt/coco/tdx-host/Kconfig    | 10 ++++++
 drivers/virt/coco/tdx-host/Makefile   |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 52 +++++++++++++++++++++++++++
 5 files changed, 66 insertions(+)
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index bb0c6d6ddcc8..b9fb0760e917 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -15,5 +15,7 @@ source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
 
+source "drivers/virt/coco/tdx-host/Kconfig"
+
 config TSM
 	bool
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index cb52021912b3..b323b0ae4f82 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -6,6 +6,7 @@ obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
+obj-$(CONFIG_INTEL_TDX_HOST)	+= tdx-host/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
new file mode 100644
index 000000000000..bf6be0fc0879
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -0,0 +1,10 @@
+config TDX_HOST_SERVICES
+	tristate "TDX Host Services Driver"
+	depends on INTEL_TDX_HOST
+	default m if INTEL_TDX_HOST
+	help
+	  Enable access to TDX host services like module update and
+	  extensions (e.g. TDX Connect).
+
+	  Say y or m if enabling support for confidential virtual machine
+	  support (CONFIG_INTEL_TDX_HOST). The module is called tdx_host.ko
diff --git a/drivers/virt/coco/tdx-host/Makefile b/drivers/virt/coco/tdx-host/Makefile
new file mode 100644
index 000000000000..e61e749a8dff
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Makefile
@@ -0,0 +1 @@
+obj-$(CONFIG_TDX_HOST_SERVICES) += tdx-host.o
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
new file mode 100644
index 000000000000..49c205913ef6
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -0,0 +1,52 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * TDX host user interface driver
+ *
+ * Copyright (C) 2025 Intel Corporation
+ */
+
+#include <linux/kernel.h>
+#include <linux/module.h>
+#include <linux/mod_devicetable.h>
+#include <linux/sysfs.h>
+#include <linux/device/faux.h>
+#include <asm/cpu_device_id.h>
+#include <asm/tdx.h>
+#include <asm/tdx_global_metadata.h>
+
+static const struct x86_cpu_id tdx_host_ids[] = {
+	X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),
+	{}
+};
+MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
+
+static struct faux_device *fdev;
+
+static int __init tdx_host_init(void)
+{
+	int r;
+
+	if (!x86_match_cpu(tdx_host_ids))
+		return -ENODEV;
+
+	/* Enable the usage of SEAMCALLs */
+	r = tdx_enable();
+	if (r)
+		return r;
+
+	fdev = faux_device_create(KBUILD_MODNAME, NULL, NULL);
+	if (!fdev)
+		return -ENODEV;
+
+	return 0;
+}
+module_init(tdx_host_init);
+
+static void __exit tdx_host_exit(void)
+{
+	faux_device_destroy(fdev);
+}
+module_exit(tdx_host_exit);
+
+MODULE_DESCRIPTION("TDX Host Services");
+MODULE_LICENSE("GPL");

base-commit: 0d1fbc1f1b7a3c8b14a643303dd89bcc82d3fbd0

---

## [3] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 02/27] x86/virt/tdx: Move bit definitions of TDX_FEATURES0 to public header*

From: Xu Yilun <yilun.xu@linux.intel.com>

Move bit definitions of TDX_FEATURES0 to TDX core public header.

Kernel users get TDX_FEATURE0 bitmap via tdx_get_sysinfo(). It is
reasonable to also public the definitions of each bit. TDX Connect
will add new bits and check them in tdx-host module.

Take the oppotunity to change its type to BIT_ULL cause tdx_features0
is explicitly defined as 64 bit in both TDX Module Specification and
TDX core code.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  | 4 ++++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 2 files changed, 4 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index cbea169b5fa0..4ce3a302d9ba 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -124,6 +124,10 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 #define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
 int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
+
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 82bb82be8567..c641b4632826 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -84,9 +84,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [4] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 03/27] coco/tdx-host: Support Link TSM for TDX host*

From: Xu Yilun <yilun.xu@linux.intel.com>

Register a Link TSM instance to support host side TSM operations for
TDISP, when the TDX Connect support bit is set by TDX Module in
tdx_feature0.

This is the main purpose of an independent tdx-host module out of TDX
core. Recall that a TEE Security Manager (TSM) is a platform agent that
speaks the TEE Device Interface Security Protocol (TDISP) to PCIe
devices and manages private memory resources for the platform. An
independent tdx-host module allows for device-security enumeration and
initialization flows to be deferred from other TDX Module initialization
requirements. Crucially, when / if TDX Module init moves earlier in x86
initialization flow this driver is still guaranteed to run after IOMMU
and PCI init (i.e. subsys_initcall() vs device_initcall()).

The ability to unload the module, or unbind the driver is also useful
for debug and coarse grained transitioning between PCI TSM operation and
PCI CMA operation (native kernel PCI device authentication).

For now this is the basic boilerplate with operation flows to be added
later.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h            |   1 +
 drivers/virt/coco/tdx-host/Kconfig    |   6 ++
 drivers/virt/coco/tdx-host/tdx-host.c | 145 +++++++++++++++++++++++++-
 3 files changed, 151 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 4ce3a302d9ba..166795e34c8f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -126,6 +126,7 @@ int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TDXCONNECT	BIT_ULL(6)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void);
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index bf6be0fc0879..026b7d5ea4fa 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -8,3 +8,9 @@ config TDX_HOST_SERVICES
 
 	  Say y or m if enabling support for confidential virtual machine
 	  support (CONFIG_INTEL_TDX_HOST). The module is called tdx_host.ko
+
+config TDX_CONNECT
+	bool
+	depends on TDX_HOST_SERVICES
+	depends on PCI_TSM
+	default TDX_HOST_SERVICES
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 49c205913ef6..41813ba352d0 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -8,7 +8,10 @@
 #include <linux/kernel.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
 #include <linux/sysfs.h>
+#include <linux/tsm.h>
 #include <linux/device/faux.h>
 #include <asm/cpu_device_id.h>
 #include <asm/tdx.h>
@@ -20,6 +23,146 @@ static const struct x86_cpu_id tdx_host_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
 
+/*
+ * The scope of this pointer is for TDX Connect.
+ * Every feature should evaluate how to get tdx_sysinfo. TDX Connect expects no
+ * tdx_sysinfo change after TDX Module update so could cache it. TDX version
+ * sysfs expects change so should call tdx_get_sysinfo() every time.
+ *
+ * Maybe move TDX Connect to a separate file makes thing clearer.
+ */
+static const struct tdx_sys_info *tdx_sysinfo;
+
+struct tdx_link {
+	struct pci_tsm_pf0 pci;
+};
+
+static struct tdx_link *to_tdx_link(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct tdx_link, pci.base_tsm);
+}
+
+static int tdx_link_connect(struct pci_dev *pdev)
+{
+	return -ENXIO;
+}
+
+static void tdx_link_disconnect(struct pci_dev *pdev)
+{
+}
+
+static struct pci_tsm_ops tdx_link_ops;
+
+static struct pci_tsm *tdx_link_pf0_probe(struct tsm_dev *tsm_dev,
+					  struct pci_dev *pdev)
+{
+	int rc;
+
+	struct tdx_link *tlink __free(kfree) =
+		kzalloc(sizeof(*tlink), GFP_KERNEL);
+	if (!tlink)
+		return NULL;
+
+	rc = pci_tsm_pf0_constructor(pdev, &tlink->pci, tsm_dev->pci_ops);
+	if (rc)
+		return NULL;
+
+	return &no_free_ptr(tlink)->pci.base_tsm;
+}
+
+static void tdx_link_pf0_remove(struct pci_tsm *tsm)
+{
+	struct tdx_link *tlink = to_tdx_link(tsm);
+
+	pci_tsm_pf0_destructor(&tlink->pci);
+	kfree(tlink);
+}
+
+static struct pci_tsm *tdx_link_fn_probe(struct tsm_dev *tsm_dev,
+					 struct pci_dev *pdev)
+{
+	int rc;
+
+	struct pci_tsm *pci_tsm __free(kfree) =
+		kzalloc(sizeof(*pci_tsm), GFP_KERNEL);
+	if (!pci_tsm)
+		return NULL;
+
+	rc = pci_tsm_link_constructor(pdev, pci_tsm, tsm_dev->pci_ops);
+	if (rc)
+		return NULL;
+
+	return no_free_ptr(pci_tsm);
+}
+
+static struct pci_tsm *tdx_link_probe(struct tsm_dev *tsm_dev, struct pci_dev *pdev)
+{
+	if (is_pci_tsm_pf0(pdev))
+		return tdx_link_pf0_probe(tsm_dev, pdev);
+
+	return tdx_link_fn_probe(tsm_dev, pdev);
+}
+
+static void tdx_link_remove(struct pci_tsm *tsm)
+{
+	if (is_pci_tsm_pf0(tsm->pdev)) {
+		tdx_link_pf0_remove(tsm);
+		return;
+	}
+
+	/* for sub-functions */
+	kfree(tsm);
+}
+
+static struct pci_tsm_ops tdx_link_ops = {
+	.probe = tdx_link_probe,
+	.remove = tdx_link_remove,
+	.connect = tdx_link_connect,
+	.disconnect = tdx_link_disconnect,
+};
+
+static struct tsm_dev *link_dev;
+
+static void unregister_link_tsm(void *data)
+{
+	tsm_unregister(link_dev);
+}
+
+static int tdx_connect_init(struct device *dev)
+{
+	struct tsm_dev *link;
+
+	if (!IS_ENABLED(CONFIG_TDX_CONNECT))
+		return 0;
+
+	tdx_sysinfo = tdx_get_sysinfo();
+	if (!tdx_sysinfo)
+		return -ENXIO;
+
+	if (!(tdx_sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT))
+		return 0;
+
+	link = tsm_register(dev, &tdx_link_ops);
+	if (IS_ERR(link)) {
+		dev_err(dev, "failed to register TSM: (%pe)\n", link);
+		return PTR_ERR(link);
+	}
+
+	link_dev = link;
+
+	return devm_add_action_or_reset(dev, unregister_link_tsm, NULL);
+}
+
+static int tdx_host_probe(struct faux_device *fdev)
+{
+	/* Only support TDX Connect now. More TDX features could be added here. */
+	return tdx_connect_init(&fdev->dev);
+}
+
+static struct faux_device_ops tdx_host_ops = {
+	.probe = tdx_host_probe,
+};
+
 static struct faux_device *fdev;
 
 static int __init tdx_host_init(void)
@@ -34,7 +177,7 @@ static int __init tdx_host_init(void)
 	if (r)
 		return r;
 
-	fdev = faux_device_create(KBUILD_MODNAME, NULL, NULL);
+	fdev = faux_device_create(KBUILD_MODNAME, NULL, &tdx_host_ops);
 	if (!fdev)
 		return -ENODEV;

---

## [5] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 04/27] x86/virt/tdx: Move tdx_errno.h from KVM to public place*

From: Xu Yilun <yilun.xu@linux.intel.com>

Move these TDX Module defined error code from KVM to public place.

SEAMCALL helpers (defined in TDX core, tdh_*()) returns these error code
to kernel users. It is reasonable to also public the definitions of each
error code. TDX core itself will use these error code when enabling
optional features (e.g. TDX Module extensions). TDX Connect will also use
them in tdx-host module.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h                    | 1 +
 arch/x86/{kvm/vmx => include/asm}/tdx_errno.h | 6 +++---
 arch/x86/kvm/vmx/tdx.h                        | 1 -
 3 files changed, 4 insertions(+), 4 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm}/tdx_errno.h (93%)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 166795e34c8f..732e1e7fd556 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -10,6 +10,7 @@
 #include <asm/errno.h>
 #include <asm/ptrace.h>
 #include <asm/trapnr.h>
+#include <asm/tdx_errno.h>
 #include <asm/shared/tdx.h>
 
 /*
diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/include/asm/tdx_errno.h
similarity index 93%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/tdx_errno.h
index 6ff4672c4181..6a5f183cf119 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/tdx_errno.h
@@ -1,8 +1,8 @@
 /* SPDX-License-Identifier: GPL-2.0 */
 /* architectural status code for SEAMCALL */
 
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
+#ifndef __ASM_X86_TDX_ERRNO_H
+#define __ASM_X86_TDX_ERRNO_H
 
 #define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
 
@@ -37,4 +37,4 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#endif /* __ASM_X86_TDX_ERRNO_H */
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ca39a9391db1..f4e609a745ee 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -3,7 +3,6 @@
 #define __KVM_X86_VMX_TDX_H
 
 #include "tdx_arch.h"
-#include "tdx_errno.h"
 
 #ifdef CONFIG_KVM_INTEL_TDX
 #include "common.h"

---

## [6] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 05/27] x86/virt/tdx: Add tdx_page_array helpers for new TDX Module objects*

From: Xu Yilun <yilun.xu@linux.intel.com>

Add struct tdx_page_array definition for new TDX Module object
types - HPA_ARRAY_T and HPA_LIST_INFO. They are used as input/output
parameters in newly defined SEAMCALLs. Also define some helpers to
allocate, setup and free tdx_page_array.

HPA_ARRAY_T and HPA_LIST_INFO are similar in most aspects. They both
represent a list of pages for TDX Module accessing. There are several
use cases for these 2 structures:

 - As SEAMCALL inputs. They are claimed by TDX Module as control pages.
 - As SEAMCALL outputs. They were TDX Module control pages and now are
   released.
 - As SEAMCALL inputs. They are just medium for exchanging data blobs
   in one SEAMCALL. TDX Module will not hold them as control pages.

The 2 structures both need a 'root page' which contains a list of HPAs.
They compress the HPA of the root page and the number of valid HPAs into
a 64 bit raw value for SEAMCALL parameters. The root page is always a
medium for passing data pages, TDX Module never keeps the root page.

A main difference is HPA_ARRAY_T requires singleton mode when
containing just 1 functional page (page0). In this mode the root page is
not needed and the HPA field of the raw value directly points to the
page0.

Another small difference is HPA_LIST_INFO contains a 'first entry' field
which could be filled by TDX Module. This simplifies host by providing
the same structure when re-invoke the interrupted SEAMCALL. No need for
host to touch this field.

Typical usages of the tdx_page_array:

1. Add control pages:
 - struct tdx_page_array *array = tdx_page_array_create(nr_pages, ...);
 - seamcall(TDH_XXX_CREATE, array, ...);

2. Release control pages:
 - seamcall(TDX_XXX_DELETE, array, &nr_released, &released_hpa);
 - tdx_page_array_ctrl_release(array, nr_released, released_hpa);

3. Exchange data blobs:
 - struct tdx_page_array *array = tdx_page_array_create(nr_pages, ...);
 - seamcall(TDX_XXX, array, ...);
 - Read data from array.
 - tdx_page_array_free(array);

4. Note the root page contains 512 HPAs at most, if more pages are
   required, refilling the tdx_page_array is needed.

 - struct tdx_page_array *array = tdx_page_array_alloc(nr_pages, ...);
 - for each 512-page bulk
   - tdx_page_array_fill_root(array, offset);
   - seamcall(TDH_XXX_ADD, array, ...);

In case 2, SEAMCALLs output the released page array in the form of
HPA_ARRAY_T or PAGE_LIST_INFO. tdx_page_array_ctrl_release() is
responsible for checking if the output pages match the original input
pages. If failed to match, the safer way is to leak the control pages,
tdx_page_array_ctrl_leak() should be called.

The usage of tdx_page_array will be in following patches.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  |  18 +++
 arch/x86/virt/vmx/tdx/tdx.c | 221 ++++++++++++++++++++++++++++++++++++
 include/linux/gfp.h         |   2 +
 3 files changed, 241 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 732e1e7fd556..fbd50df216af 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -136,6 +136,24 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
+struct tdx_page_array {
+	unsigned int nr_pages;
+	struct page **pages;
+
+	unsigned int offset;
+	unsigned int nents;
+	struct page *root;
+};
+
+void tdx_page_array_free(struct tdx_page_array *array);
+DEFINE_FREE(tdx_page_array_free, struct tdx_page_array *, if (_T) tdx_page_array_free(_T))
+struct tdx_page_array *
+tdx_page_array_create(unsigned int nr_pages, bool allow_singleton);
+void tdx_page_array_ctrl_leak(struct tdx_page_array *array);
+int tdx_page_array_ctrl_release(struct tdx_page_array *array,
+				unsigned int nr_released,
+				u64 released_hpa);
+
 struct tdx_td {
 	/* TD root structure: */
 	struct page *tdr_page;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ada2fd4c2d54..bc5b8e288546 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -269,6 +269,227 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
+#define TDX_PAGE_ARRAY_MAX_NENTS	(PAGE_SIZE / sizeof(u64))
+
+static int tdx_page_array_fill_root(struct tdx_page_array *array,
+				    unsigned int offset)
+{
+	unsigned int i;
+	u64 *entries;
+
+	if (offset >= array->nr_pages)
+		return 0;
+
+	if (!array->root) {
+		array->nents = 1;
+		return array->nents;
+	}
+
+	array->offset = offset;
+	array->nents = umin(array->nr_pages - offset,
+			    TDX_PAGE_ARRAY_MAX_NENTS);
+
+	entries = (u64 *)page_address(array->root);
+	for (i = 0; i < array->nents; i++)
+		entries[i] = page_to_phys(array->pages[offset + i]);
+
+	return array->nents;
+}
+
+static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
+{
+	unsigned long i;
+
+	for (i = 0; i < nr_pages; i++)
+		__free_page(pages[i]);
+}
+
+static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages)
+{
+	unsigned int filled, done = 0;
+
+	do {
+		filled = alloc_pages_bulk(GFP_KERNEL, nr_pages - done,
+					  pages + done);
+		if (!filled) {
+			tdx_free_pages_bulk(done, pages);
+			return -ENOMEM;
+		}
+
+		done += filled;
+	} while (done != nr_pages);
+
+	return 0;
+}
+
+void tdx_page_array_free(struct tdx_page_array *array)
+{
+	if (!array)
+		return;
+
+	if (array->root)
+		__free_page(array->root);
+
+	tdx_free_pages_bulk(array->nr_pages, array->pages);
+	kfree(array->pages);
+	kfree(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_free);
+
+static struct tdx_page_array *
+tdx_page_array_alloc(unsigned int nr_pages, bool allow_singleton)
+{
+	int ret;
+
+	if (!nr_pages)
+		return NULL;
+
+	struct tdx_page_array *array __free(kfree) = kzalloc(sizeof(*array),
+							     GFP_KERNEL);
+	if (!array)
+		return NULL;
+
+	struct page *root __free(__free_page) = NULL;
+	if (!allow_singleton || nr_pages != 1) {
+		root = alloc_page(GFP_KERNEL | __GFP_ZERO);
+		if (!root)
+			return NULL;
+	}
+
+	struct page **pages __free(kfree) = kcalloc(nr_pages, sizeof(*pages),
+						    GFP_KERNEL);
+	if (!pages)
+		return NULL;
+
+	ret = tdx_alloc_pages_bulk(nr_pages, pages);
+	if (ret)
+		return NULL;
+
+	array->nr_pages = nr_pages;
+	array->pages = no_free_ptr(pages);
+	array->root = no_free_ptr(root);
+
+	return no_free_ptr(array);
+}
+
+/*
+ * For holding less than TDX_PAGE_ARRAY_MAX_NENTS (512) pages.
+ *
+ * If more pages are required, use tdx_page_array_alloc() and
+ * tdx_page_array_fill_root() to build tdx_page_array chunk by chunk.
+ */
+struct tdx_page_array *
+tdx_page_array_create(unsigned int nr_pages, bool allow_singleton)
+{
+	int filled;
+
+	if (nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
+		return NULL;
+
+	struct tdx_page_array *array __free(tdx_page_array_free) =
+		tdx_page_array_alloc(nr_pages, allow_singleton);
+	if (!array)
+		return NULL;
+
+	filled = tdx_page_array_fill_root(array, 0);
+	if (filled != nr_pages)
+		return NULL;
+
+	return no_free_ptr(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_create);
+
+/*
+ * Call this function when failed to reclaim the control pages. The root page
+ * and the holding structures can still be freed.
+ */
+void tdx_page_array_ctrl_leak(struct tdx_page_array *array)
+{
+	if (array->root)
+		__free_page(array->root);
+
+	kfree(array->pages);
+	kfree(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_leak);
+
+static bool tdx_page_array_ctrl_match(struct tdx_page_array *array,
+				      unsigned int offset,
+				      unsigned int nr_released,
+				      u64 released_hpa)
+{
+	unsigned int nents;
+	u64 *entries;
+	int i;
+
+	if (offset >= array->nr_pages)
+		return 0;
+
+	nents = umin(array->nr_pages - offset, TDX_PAGE_ARRAY_MAX_NENTS);
+
+	if (nents != nr_released) {
+		pr_err("%s nr_released [%d] doesn't match page array nents [%d]\n",
+		       __func__, nr_released, nents);
+		return false;
+	}
+
+	if (!array->root) {
+		if (page_to_phys(array->pages[0]) != released_hpa) {
+			pr_err("%s released_hpa [0x%llx] doesn't match page0 hpa [0x%llx]\n",
+			       __func__, released_hpa,
+			       page_to_phys(array->pages[0]));
+			return false;
+		}
+
+		return true;
+	}
+
+	if (page_to_phys(array->root) != released_hpa) {
+		pr_err("%s released_hpa [0x%llx] doesn't match root page hpa [0x%llx]\n",
+		       __func__, released_hpa, page_to_phys(array->root));
+		return 0;
+	}
+
+	entries = (u64 *)page_address(array->root);
+	for (i = 0; i < nents; i++) {
+		if (page_to_phys(array->pages[offset + i]) != entries[i]) {
+			pr_err("%s entry[%d] [0x%llx] doesn't match page hpa [0x%llx]\n",
+			       __func__, i, entries[i],
+			       page_to_phys(array->pages[offset + i]));
+			return false;
+		}
+	}
+
+	return true;
+}
+
+/* For releasing control pages which are created by tdx_page_array_create() */
+int tdx_page_array_ctrl_release(struct tdx_page_array *array,
+				unsigned int nr_released,
+				u64 released_hpa)
+{
+	int i;
+	u64 r;
+
+	if (WARN_ON(array->nr_pages > TDX_PAGE_ARRAY_MAX_NENTS))
+		return -EINVAL;
+
+	if (WARN_ON(!tdx_page_array_ctrl_match(array, 0, nr_released,
+					       released_hpa)))
+		return -EFAULT;
+
+	for (i = 0; i < array->nr_pages; i++) {
+		r = tdh_phymem_page_wbinvd_hkid(tdx_global_keyid,
+						array->pages[i]);
+		if (WARN_ON(r))
+			return -EFAULT;
+	}
+
+	tdx_page_array_free(array);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_release);
+
 static int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
diff --git a/include/linux/gfp.h b/include/linux/gfp.h
index 5ebf26fcdcfa..f0a651155872 100644
--- a/include/linux/gfp.h
+++ b/include/linux/gfp.h
@@ -385,6 +385,8 @@ extern void free_pages(unsigned long addr, unsigned int order);
 #define __free_page(page) __free_pages((page), 0)
 #define free_page(addr) free_pages((addr), 0)
 
+DEFINE_FREE(__free_page, struct page *, if (_T) __free_page(_T))
+
 void page_alloc_init_cpuhp(void);
 int decay_pcp_high(struct zone *zone, struct per_cpu_pages *pcp);
 void drain_zone_pages(struct zone *zone, struct per_cpu_pages *pcp);

---

## [7] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 06/27] x86/virt/tdx: Add SEAMCALL wrappers for TDH.EXT.MEM.ADD and TDH.EXT.INIT*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Add the two SEAMCALLs for TDX Module Extension initialization.

TDH.EXT.MEM.ADD add pages to a shared memory pool for extensions to
consume. The number of pages required is published in the
MEMORY_POOL_REQUIRED_PAGES field from TDH.SYS.RD. Then on TDX.EXT.INIT, the
extensions consume from the pool and initialize.

TDH.EXT.MEM.ADD is the first user of tdx_page_array. It provides pages
to TDX Module as control (private) pages. A tdx_clflush_page_array()
helper is introduced to flush shared cache before SEAMCALL, to avoid
shared cache write back damages these private pages.

TDH.EXT.MEM.ADD uses HPA_LIST_INFO as parameter so could leverage the
'first_entry' field to simplify the interrupted - retry flow. Include
the retry handling in the wrapper so users don't have to care about
partial page adding and 'first_entry'.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c | 49 +++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  2 ++
 3 files changed, 53 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index fbd50df216af..1f1bcae46bb3 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -217,6 +217,8 @@ u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u6
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_ext_mem_add(struct tdx_page_array *pg_arr);
+u64 tdh_ext_init(void);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_enable(void)  { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index bc5b8e288546..d47b2612c816 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2110,3 +2110,52 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+
+static void tdx_clflush_page_array(struct tdx_page_array *array)
+{
+	for (int i = 0; i < array->nents; i++)
+		tdx_clflush_page(array->pages[array->offset + i]);
+}
+
+union hpa_list_info {
+	struct {
+		u64 rsvd0:3;
+		u64 first_entry:9;
+		u64 hpa:40;
+		u64 rsvd1:3;
+		u64 last_entry:9;
+	};
+	u64 raw;
+};
+
+u64 tdh_ext_mem_add(struct tdx_page_array *pg_arr)
+{
+	union hpa_list_info info = { 0 };
+	struct tdx_module_args args = { 0 };
+	u64 r;
+	int i;
+
+	tdx_clflush_page_array(pg_arr);
+
+	info.raw = page_to_phys(pg_arr->root);
+	info.first_entry = 0;
+	info.last_entry = pg_arr->nents - 1;
+	args.rcx = info.raw;
+
+	for (i = TDX_SEAMCALL_RETRIES; i > 0; i--) {
+		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
+		if (r != TDX_INTERRUPTED_RESUMABLE)
+			break;
+	}
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_ext_mem_add);
+
+u64 tdh_ext_init(void)
+{
+	struct tdx_module_args args = {};
+
+	return seamcall(TDH_EXT_INIT, &args);
+}
+EXPORT_SYMBOL_GPL(tdh_ext_init);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index c641b4632826..e3b403846863 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,8 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_EXT_INIT			60
+#define TDH_EXT_MEM_ADD			61
 
 /*
  * SEAMCALL leaf:

---

## [8] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 07/27] TODO: x86/virt/tdx: Read TDX global metadata for TDX Module Extensions*

From: Xu Yilun <yilun.xu@linux.intel.com>

Add the global metadata for TDX core to enable extensions. They are:

 - "memory_pool_required_pages"
   Specify the required number of memory pool pages for the present
   extensions.

 - "ext_required"
   Specify if TDX.EXT.INIT is required.

Note for these 2 fields, a value of 0 doesn't mean extensions are not
supported.  It means no need to call TDX.EXT.MEM.ADD or TDX.EXT.INIT.

----
TODO: This patch should be auto-generated by script but for now the TDX
Connect part is not published in global_metadata.json so make the patch
manually. The correct way should be:

The code change is auto-generated by re-running the script in [1] after
uncommenting the "td_conf" and "td_ctrl" part to regenerate the
tdx_global_metadata.{hc} and update them to the existing ones in the
kernel.

  #python tdx.py global_metadata.json tdx_global_metadata.h \
        tdx_global_metadata.c

The 'global_metadata.json' can be fetched from [1].

Link: https://cdrdv2.intel.com/v1/dl/getContent/795381 [1]
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx_global_metadata.h  |  6 ++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 14 ++++++++++++++
 2 files changed, 20 insertions(+)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 060a2ad744bf..2aa741190b93 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -34,11 +34,17 @@ struct tdx_sys_info_td_conf {
 	u64 cpuid_config_values[128][2];
 };
 
+struct tdx_sys_info_ext {
+	u16 memory_pool_required_pages;
+	u8 ext_required;
+};
+
 struct tdx_sys_info {
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
 	struct tdx_sys_info_td_conf td_conf;
+	struct tdx_sys_info_ext ext;
 };
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..69be16c1e6ec 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -85,6 +85,19 @@ static int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf
 	return ret;
 }
 
+static int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x3100000100000000, &val)))
+		sysinfo_ext->memory_pool_required_pages = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3100000100000001, &val)))
+		sysinfo_ext->ext_required = val;
+
+	return ret;
+}
+
 static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -93,6 +106,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
+	ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
 
 	return ret;
 }

---

## [9] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 08/27] x86/virt/tdx: Add tdx_enable_ext() to enable of TDX Module Extensions*

From: Xu Yilun <yilun.xu@linux.intel.com>

tdx_enable() implements a simple state machine with @tdx_module_status to
determine if TDX is already enabled, or failed to enable. Add another state
to that enum (TDX_MODULE_INITIALIZED_EXT) to track if extensions have been enabled.

The extension initialization uses the new TDH.EXT.MEM.ADD and TDX.EXT.INIT
seamcalls.

Note that this extension initialization does not impact existing in-flight
SEAMCALLs that are not implemented by the extension. So only the first user
of an extension-seamcall needs invoke this helper.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h            |   3 +
 arch/x86/virt/vmx/tdx/tdx.c           | 152 ++++++++++++++++++++++++--
 arch/x86/virt/vmx/tdx/tdx.h           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c |   7 ++
 4 files changed, 155 insertions(+), 8 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 1f1bcae46bb3..d53260aadb0b 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -124,11 +124,13 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 #define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
 #define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
 int tdx_enable(void);
+int tdx_enable_ext(void);
 const char *tdx_dump_mce_info(struct mce *m);
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_TDXCONNECT	BIT_ULL(6)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_EXT		BIT_ULL(39)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
@@ -222,6 +224,7 @@ u64 tdh_ext_init(void);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_enable(void)  { return -ENODEV; }
+static inline int tdx_enable_ext(void) { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index d47b2612c816..9d4cebace054 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -122,9 +122,13 @@ static int try_init_module_global(void)
 	if (sysinit_done)
 		goto out;
 
-	/* RCX is module attributes and all bits are reserved */
-	args.rcx = 0;
+	/* TODO: Replace try/fail with new feature enumeration capability */
+	args.rcx = TDX_FEATURES0_TDXCONNECT | TDX_FEATURES0_EXT;
 	sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
+	if (sysinit_ret) {
+		args.rcx = 0;
+		sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
+	}
 
 	/*
 	 * The first SEAMCALL also detects the TDX module, thus
@@ -1443,6 +1447,7 @@ int tdx_enable(void)
 		ret = __tdx_enable();
 		break;
 	case TDX_MODULE_INITIALIZED:
+	case TDX_MODULE_INITIALIZED_EXT:
 		/* Already initialized, great, tell the caller. */
 		ret = 0;
 		break;
@@ -1456,6 +1461,139 @@ int tdx_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_enable);
 
+static int enable_tdx_ext(void)
+{
+	u64 r;
+
+	if (!tdx_sysinfo.ext.ext_required)
+		return 0;
+
+	do {
+		r = tdh_ext_init();
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
+static void tdx_ext_mempool_free(struct tdx_page_array *mempool)
+{
+	/*
+	 * Some pages may have been touched by the TDX module.
+	 * Flush cache before returning these pages to kernel.
+	 */
+	wbinvd_on_all_cpus();
+
+	tdx_page_array_free(mempool);
+}
+
+DEFINE_FREE(tdx_ext_mempool_free, struct tdx_page_array *, if (!IS_ERR_OR_NULL(_T)) tdx_ext_mempool_free(_T))
+
+static struct tdx_page_array *tdx_ext_mempool_setup(void)
+{
+	unsigned int nr_pages, nents, offset = 0;
+	u64 tdx_ret;
+
+	nr_pages = tdx_sysinfo.ext.memory_pool_required_pages;
+	if (!nr_pages)
+		return NULL;
+
+	struct tdx_page_array *mempool __free(tdx_page_array_free) =
+		tdx_page_array_alloc(nr_pages, false);
+	if (!mempool)
+		return ERR_PTR(-ENOMEM);
+
+	while (1) {
+		nents = tdx_page_array_fill_root(mempool, offset);
+		if (!nents)
+			break;
+
+		tdx_ret = tdh_ext_mem_add(mempool);
+		if (tdx_ret != TDX_SUCCESS)
+			return ERR_PTR(-EFAULT);
+
+		offset += nents;
+	}
+
+	return no_free_ptr(mempool);
+}
+
+static int init_tdx_ext(void)
+{
+	int ret;
+
+	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
+		return -EOPNOTSUPP;
+
+	struct tdx_page_array *mempool __free(tdx_ext_mempool_free) =
+		tdx_ext_mempool_setup();
+	/* Return NULL is OK, means no need to setup mempool */
+	if (IS_ERR(mempool))
+		return PTR_ERR(mempool);
+
+	ret = enable_tdx_ext();
+	if (ret)
+		return ret;
+
+	/* Extension memory is never reclaimed once assigned */
+	if (mempool)
+		tdx_page_array_ctrl_leak(no_free_ptr(mempool));
+
+	return 0;
+}
+
+static int __tdx_enable_ext(void)
+{
+	int ret;
+
+	ret = init_tdx_ext();
+	if (ret) {
+		pr_debug("module extension initialization failed (%d)\n", ret);
+		tdx_module_status = TDX_MODULE_ERROR;
+		return ret;
+	}
+
+	pr_debug("module extension initialized\n");
+	tdx_module_status = TDX_MODULE_INITIALIZED_EXT;
+
+	return 0;
+}
+
+/**
+ * tdx_enable_ext - Enable TDX module extensions.
+ *
+ * This function assumes the caller has done VMXON.
+ *
+ * This function can be called in parallel by multiple callers.
+ *
+ * Return 0 if TDX module extension is enabled successfully, otherwise error.
+ */
+int tdx_enable_ext(void)
+{
+	int ret;
+
+	mutex_lock(&tdx_module_lock);
+
+	switch (tdx_module_status) {
+	case TDX_MODULE_INITIALIZED:
+		ret = __tdx_enable_ext();
+		break;
+	case TDX_MODULE_INITIALIZED_EXT:
+		ret = 0;
+		break;
+	default:
+		ret = -EINVAL;
+		break;
+	}
+
+	mutex_unlock(&tdx_module_lock);
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tdx_enable_ext);
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
@@ -1709,7 +1847,8 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
 	/* Make sure all fields in @tdx_sysinfo have been populated */
 	mutex_lock(&tdx_module_lock);
-	if (tdx_module_status == TDX_MODULE_INITIALIZED)
+	if (tdx_module_status == TDX_MODULE_INITIALIZED ||
+	    tdx_module_status == TDX_MODULE_INITIALIZED_EXT)
 		p = (const struct tdx_sys_info *)&tdx_sysinfo;
 	mutex_unlock(&tdx_module_lock);
 
@@ -2133,7 +2272,6 @@ u64 tdh_ext_mem_add(struct tdx_page_array *pg_arr)
 	union hpa_list_info info = { 0 };
 	struct tdx_module_args args = { 0 };
 	u64 r;
-	int i;
 
 	tdx_clflush_page_array(pg_arr);
 
@@ -2142,11 +2280,9 @@ u64 tdh_ext_mem_add(struct tdx_page_array *pg_arr)
 	info.last_entry = pg_arr->nents - 1;
 	args.rcx = info.raw;
 
-	for (i = TDX_SEAMCALL_RETRIES; i > 0; i--) {
+	do {
 		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
-		if (r != TDX_INTERRUPTED_RESUMABLE)
-			break;
-	}
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
 
 	return r;
 }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index e3b403846863..f4bcfec7fb86 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -95,6 +95,7 @@ struct tdmr_info {
 enum tdx_module_status_t {
 	TDX_MODULE_UNINITIALIZED,
 	TDX_MODULE_INITIALIZED,
+	TDX_MODULE_INITIALIZED_EXT,
 	TDX_MODULE_ERROR
 };
 
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 41813ba352d0..2411c7d34b6b 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -131,6 +131,7 @@ static void unregister_link_tsm(void *data)
 static int tdx_connect_init(struct device *dev)
 {
 	struct tsm_dev *link;
+	int ret;
 
 	if (!IS_ENABLED(CONFIG_TDX_CONNECT))
 		return 0;
@@ -142,6 +143,12 @@ static int tdx_connect_init(struct device *dev)
 	if (!(tdx_sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT))
 		return 0;
 
+	ret = tdx_enable_ext();
+	if (ret) {
+		dev_dbg(dev, "Enable extension failed\n");
+		return ret;
+	}
+
 	link = tsm_register(dev, &tdx_link_ops);
 	if (IS_ERR(link)) {
 		dev_err(dev, "failed to register TSM: (%pe)\n", link);

---

## [10] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 09/27] ACPICA: Add KEYP table definitions*

From: Dave Jiang <dave.jiang@intel.com>

Add KEYP ACPI table definition defined by [1].

Software uses this table to discover the base address of the Key
Configuration Unit (KCU) register block associated with each IDE capable
host bridge. TDX host only gets the max IDE streams supported from KCU,
it doesn't access other parts since host won't directly touch the host
side IDE configuration, TDX Module does.

[1]: Root Complex IDE Key Configuration Unit Software Programming Guide
     https://cdrdv2.intel.com/v1/dl/getContent/732838

Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
[djbw: todo: do the proper ACPICA flow for this]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/acpi/actbl3.h | 60 +++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 60 insertions(+)

diff --git a/include/acpi/actbl3.h b/include/acpi/actbl3.h
index 79d3aa5a4bad..807135e115d0 100644
--- a/include/acpi/actbl3.h
+++ b/include/acpi/actbl3.h
@@ -24,6 +24,7 @@
  * file. Useful because they make it more difficult to inadvertently type in
  * the wrong signature.
  */
+#define ACPI_SIG_KEYP           "KEYP"  /* Key Programming Interface for IDE */
 #define ACPI_SIG_SLIC           "SLIC"	/* Software Licensing Description Table */
 #define ACPI_SIG_SLIT           "SLIT"	/* System Locality Distance Information Table */
 #define ACPI_SIG_SPCR           "SPCR"	/* Serial Port Console Redirection table */
@@ -794,6 +795,65 @@ struct acpi_table_xenv {
 	u8 event_flags;
 };
 
+/*******************************************************************************
+ *
+ * KEYP - Key Programming Interface for Root Complex Integrity and Data
+ *	  Encryption (IDE)
+ *        Version 1
+ *
+ * Conforms to "Key Programming Interface for Root Complex Integrity and Data
+ * Encryption (IDE)" document. See under ACPI-Related Documents.
+ *
+ ******************************************************************************/
+
+struct acpi_table_keyp {
+	struct acpi_table_header header;
+	u32 reserved;
+};
+
+/* KEYP common subtable header */
+
+struct acpi_keyp_common_header {
+	u8 type;
+	u8 reserved;
+	u16 length;
+};
+
+/* Values for Type field above */
+
+enum acpi_keyp_type {
+	ACPI_KEYP_TYPE_CONFIG_UNIT = 0,
+};
+
+/* Root Port Information Structure */
+
+struct acpi_keyp_rp_info {
+	u16 segment;
+	u8 bus;
+	u8 devfn;
+};
+
+/* Key Configuration Unit Structure */
+
+struct acpi_keyp_config_unit {
+	struct acpi_keyp_common_header header;
+	u8 protocol_type;
+	u8 version;
+	u8 root_port_count;
+	u8 flags;
+	u64 register_base_address;
+	struct acpi_keyp_rp_info rp_info[];
+};
+
+enum acpi_keyp_protocol_type {
+	ACPI_KEYP_PROTO_TYPE_INVALID = 0,
+	ACPI_KEYP_PROTO_TYPE_PCIE,
+	ACPI_KEYP_PROTO_TYPE_CXL,
+	ACPI_KEYP_PROTO_TYPE_RESERVED
+};
+
+#define ACPI_KEYP_F_TVM_USABLE		(1)
+
 /* Reset to default packing */
 
 #pragma pack()

---

## [11] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 10/27] acpi: Add KEYP support to fw_table parsing*

From: Dave Jiang <dave.jiang@intel.com>

KEYP ACPI table can be parsed using the common fw_table handlers. Add
additional support to detect and parse the table.

Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
[djbw: todo: drop config symbol for this]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/acpi/Kconfig     | 12 ++++++++++++
 drivers/acpi/tables.c    | 14 +++++++++++++-
 include/linux/acpi.h     | 13 +++++++++++++
 include/linux/fw_table.h |  1 +
 lib/fw_table.c           |  9 +++++++++
 5 files changed, 48 insertions(+), 1 deletion(-)

diff --git a/drivers/acpi/Kconfig b/drivers/acpi/Kconfig
index b594780a57d7..e9af80d69e02 100644
--- a/drivers/acpi/Kconfig
+++ b/drivers/acpi/Kconfig
@@ -600,6 +600,18 @@ config ACPI_PRMT
 	  substantially increase computational overhead related to the
 	  initialization of some server systems.
 
+config ACPI_KEYP
+	bool "ACPI KEYP Table Support for Integrity and Data Encryption (IDE)"
+	depends on X86_64
+	default y
+	help
+	  Platform KEYP table holds the KEY Configuration Unit (KCU) structures
+	  and the base address of the KCU register block associated with each
+	  IDE capable host bridge. Host parses this table to gets the max IDE
+	  streams supported by each host bridge.
+
+	  Say Y to enable KEYP table parsing for IDE stream creation.
+
 endif	# ACPI
 
 config X86_PM_TIMER
diff --git a/drivers/acpi/tables.c b/drivers/acpi/tables.c
index fa9bb8c8ce95..37c72d31eac8 100644
--- a/drivers/acpi/tables.c
+++ b/drivers/acpi/tables.c
@@ -299,6 +299,18 @@ acpi_table_parse_cedt(enum acpi_cedt_type id,
 }
 EXPORT_SYMBOL_ACPI_LIB(acpi_table_parse_cedt);
 
+#ifdef CONFIG_ACPI_KEYP
+int __init_or_acpilib
+acpi_table_parse_keyp(enum acpi_keyp_type id,
+		      acpi_tbl_entry_handler_arg handler_arg, void *arg)
+{
+	return __acpi_table_parse_entries(ACPI_SIG_KEYP,
+					  sizeof(struct acpi_table_keyp), id,
+					  NULL, handler_arg, arg, 0);
+}
+EXPORT_SYMBOL_ACPI_LIB(acpi_table_parse_keyp);
+#endif
+
 int __init acpi_table_parse_entries(char *id, unsigned long table_size,
 				    int entry_id,
 				    acpi_tbl_entry_handler handler,
@@ -408,7 +420,7 @@ static const char table_sigs[][ACPI_NAMESEG_SIZE] __nonstring_array __initconst
 	ACPI_SIG_PSDT, ACPI_SIG_RSDT, ACPI_SIG_XSDT, ACPI_SIG_SSDT,
 	ACPI_SIG_IORT, ACPI_SIG_NFIT, ACPI_SIG_HMAT, ACPI_SIG_PPTT,
 	ACPI_SIG_NHLT, ACPI_SIG_AEST, ACPI_SIG_CEDT, ACPI_SIG_AGDI,
-	ACPI_SIG_NBFT };
+	ACPI_SIG_NBFT, ACPI_SIG_KEYP };
 
 #define ACPI_HEADER_SIZE sizeof(struct acpi_table_header)
 
diff --git a/include/linux/acpi.h b/include/linux/acpi.h
index 1c5bb1e887cd..36662c1c7de4 100644
--- a/include/linux/acpi.h
+++ b/include/linux/acpi.h
@@ -235,6 +235,19 @@ int __init_or_acpilib
 acpi_table_parse_cedt(enum acpi_cedt_type id,
 		      acpi_tbl_entry_handler_arg handler_arg, void *arg);
 
+#ifdef CONFIG_ACPI_KEYP
+int __init_or_acpilib
+acpi_table_parse_keyp(enum acpi_keyp_type id,
+		      acpi_tbl_entry_handler_arg handler_arg, void *arg);
+#else
+static inline int acpi_table_parse_keyp(enum acpi_keyp_type id,
+					acpi_tbl_entry_handler_arg handler_arg,
+					void *arg)
+{
+	return -EOPNOTSUPP;
+}
+#endif
+
 int acpi_parse_mcfg (struct acpi_table_header *header);
 void acpi_table_print_madt_entry (struct acpi_subtable_header *madt);
 
diff --git a/include/linux/fw_table.h b/include/linux/fw_table.h
index 9bd605b87c4c..293252cb0b7e 100644
--- a/include/linux/fw_table.h
+++ b/include/linux/fw_table.h
@@ -36,6 +36,7 @@ union acpi_subtable_headers {
 	struct acpi_prmt_module_header prmt;
 	struct acpi_cedt_header cedt;
 	struct acpi_cdat_header cdat;
+	struct acpi_keyp_common_header keyp;
 };
 
 int acpi_parse_entries_array(char *id, unsigned long table_size,
diff --git a/lib/fw_table.c b/lib/fw_table.c
index 16291814450e..147e3895e94c 100644
--- a/lib/fw_table.c
+++ b/lib/fw_table.c
@@ -20,6 +20,7 @@ enum acpi_subtable_type {
 	ACPI_SUBTABLE_PRMT,
 	ACPI_SUBTABLE_CEDT,
 	CDAT_SUBTABLE,
+	ACPI_SUBTABLE_KEYP,
 };
 
 struct acpi_subtable_entry {
@@ -41,6 +42,8 @@ acpi_get_entry_type(struct acpi_subtable_entry *entry)
 		return entry->hdr->cedt.type;
 	case CDAT_SUBTABLE:
 		return entry->hdr->cdat.type;
+	case ACPI_SUBTABLE_KEYP:
+		return entry->hdr->keyp.type;
 	}
 	return 0;
 }
@@ -61,6 +64,8 @@ acpi_get_entry_length(struct acpi_subtable_entry *entry)
 		__le16 length = (__force __le16)entry->hdr->cdat.length;
 
 		return le16_to_cpu(length);
+	case ACPI_SUBTABLE_KEYP:
+		return entry->hdr->keyp.length;
 	}
 	}
 	return 0;
@@ -80,6 +85,8 @@ acpi_get_subtable_header_length(struct acpi_subtable_entry *entry)
 		return sizeof(entry->hdr->cedt);
 	case CDAT_SUBTABLE:
 		return sizeof(entry->hdr->cdat);
+	case ACPI_SUBTABLE_KEYP:
+		return sizeof(entry->hdr->keyp);
 	}
 	return 0;
 }
@@ -95,6 +102,8 @@ acpi_get_subtable_type(char *id)
 		return ACPI_SUBTABLE_CEDT;
 	if (strncmp(id, ACPI_SIG_CDAT, 4) == 0)
 		return CDAT_SUBTABLE;
+	if (strncmp(id, ACPI_SIG_KEYP, 4) == 0)
+		return ACPI_SUBTABLE_KEYP;
 	return ACPI_SUBTABLE_COMMON;
 }

---

## [12] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 11/27] acpi: Add KEYP Key Configuration Unit parsing*

From: Dave Jiang <dave.jiang@intel.com>

Parse the KEYP Key Configuration Units (KCU), to decide the max IDE
streams supported for each host bridge.

The KEYP table points to a number of KCU structures that each associates
with a list of root ports (RP) via segment, bus, and devfn. Sanity check
the KEYP table, ensure all RPs listed for each KCU are included in one
host bridge. Then extact the max IDE streams supported to
pci_host_bridge via pci_ide_init_nr_streams().

Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
[djbw: todo: find a better place for this than common host-bridge init]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/acpi/Makefile              |   2 +
 drivers/acpi/pci_root.c            |   2 +
 drivers/acpi/x86/keyp.c            | 118 +++++++++++++++++++++++++++++
 drivers/virt/coco/tdx-host/Kconfig |   1 +
 include/linux/acpi.h               |   3 +
 5 files changed, 126 insertions(+)
 create mode 100644 drivers/acpi/x86/keyp.c

diff --git a/drivers/acpi/Makefile b/drivers/acpi/Makefile
index d1b0affb844f..fdd68d402aa2 100644
--- a/drivers/acpi/Makefile
+++ b/drivers/acpi/Makefile
@@ -134,3 +134,5 @@ obj-$(CONFIG_ACPI_VIOT)		+= viot.o
 
 obj-$(CONFIG_RISCV)		+= riscv/
 obj-$(CONFIG_X86)		+= x86/
+
+obj-$(CONFIG_ACPI_KEYP)		+= x86/keyp.o
diff --git a/drivers/acpi/pci_root.c b/drivers/acpi/pci_root.c
index 74ade4160314..633e6a00c62d 100644
--- a/drivers/acpi/pci_root.c
+++ b/drivers/acpi/pci_root.c
@@ -757,6 +757,8 @@ static int acpi_pci_root_add(struct acpi_device *device,
 		acpi_ioapic_add(root->device->handle);
 	}
 
+	keyp_setup_nr_ide_stream(root->bus);
+
 	pci_lock_rescan_remove();
 	pci_bus_add_devices(root->bus);
 	pci_unlock_rescan_remove();
diff --git a/drivers/acpi/x86/keyp.c b/drivers/acpi/x86/keyp.c
new file mode 100644
index 000000000000..99680f1edff7
--- /dev/null
+++ b/drivers/acpi/x86/keyp.c
@@ -0,0 +1,118 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * KEYP ACPI table parsing
+ *
+ * Copyright (C) 2023 Intel Corporation
+ */
+
+#include <linux/acpi.h>
+#include <linux/bitfield.h>
+#include <linux/pci.h>
+
+#define KCU_STR_CAP_NUM_STREAMS		GENMASK(8, 0)
+
+/* The bus_end is inclusive */
+struct keyp_hb_info {
+	/* input */
+	u16 segment;
+	u8 bus_start;
+	u8 bus_end;
+	/* output */
+	u8 nr_ide_streams;
+};
+
+static bool keyp_info_match(struct acpi_keyp_rp_info *rp,
+			    struct keyp_hb_info *hb)
+{
+	if (rp->segment != hb->segment)
+		return false;
+
+	if (rp->bus >= hb->bus_start && rp->bus <= hb->bus_end)
+		return true;
+
+	return false;
+}
+
+static int keyp_config_unit_handler(union acpi_subtable_headers *header,
+				    void *arg, const unsigned long end)
+{
+	struct acpi_keyp_config_unit *acpi_cu =
+		(struct acpi_keyp_config_unit *)&header->keyp;
+	struct keyp_hb_info *hb_info = arg;
+	int rp_size, rp_count, i;
+	void __iomem *addr;
+	bool match = false;
+	u32 cap;
+
+	rp_size = acpi_cu->header.length - sizeof(*acpi_cu);
+	if (rp_size % sizeof(struct acpi_keyp_rp_info))
+		return -EINVAL;
+
+	rp_count = rp_size / sizeof(struct acpi_keyp_rp_info);
+	if (!rp_count || rp_count != acpi_cu->root_port_count)
+		return -EINVAL;
+
+	for (i = 0; i < rp_count; i++) {
+		struct acpi_keyp_rp_info *rp_info = &acpi_cu->rp_info[i];
+
+		if (i == 0) {
+			match = keyp_info_match(rp_info, hb_info);
+			/* The host bridge already matches another KCU */
+			if (match && hb_info->nr_ide_streams)
+				return -EINVAL;
+
+			continue;
+		}
+
+		if (match ^ keyp_info_match(rp_info, hb_info))
+			return -EINVAL;
+	}
+
+	if (!match)
+		return 0;
+
+	addr = ioremap(acpi_cu->register_base_address, sizeof(cap));
+	if (!addr)
+		return -ENOMEM;
+	cap = ioread32(addr);
+	iounmap(addr);
+
+	hb_info->nr_ide_streams = FIELD_GET(KCU_STR_CAP_NUM_STREAMS, cap) + 1;
+
+	return 0;
+}
+
+static u8 keyp_find_nr_ide_stream(u16 segment, u8 bus_start, u8 bus_end)
+{
+	struct keyp_hb_info hb_info = {
+		.segment = segment,
+		.bus_start = bus_start,
+		.bus_end = bus_end,
+	};
+	int rc;
+
+	rc = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
+				   keyp_config_unit_handler, &hb_info);
+	if (rc < 0)
+		return 0;
+
+	return hb_info.nr_ide_streams;
+}
+
+void keyp_setup_nr_ide_stream(struct pci_bus *bus)
+{
+	struct pci_host_bridge *hb = to_pci_host_bridge(bus->bridge);
+	u8 nr_ide_streams;
+
+	if (hb->nr_ide_streams > 0)
+		return;
+
+	nr_ide_streams = keyp_find_nr_ide_stream(pci_domain_nr(bus),
+						 bus->busn_res.start,
+						 bus->busn_res.end);
+	if (!nr_ide_streams)
+		return;
+
+	pci_ide_init_nr_streams(hb, nr_ide_streams);
+}
+EXPORT_SYMBOL_GPL(keyp_setup_nr_ide_stream);
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index 026b7d5ea4fa..c3f779c511e3 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -14,3 +14,4 @@ config TDX_CONNECT
 	depends on TDX_HOST_SERVICES
 	depends on PCI_TSM
 	default TDX_HOST_SERVICES
+	select ACPI_KEYP
diff --git a/include/linux/acpi.h b/include/linux/acpi.h
index 36662c1c7de4..0165f2209d91 100644
--- a/include/linux/acpi.h
+++ b/include/linux/acpi.h
@@ -239,6 +239,7 @@ acpi_table_parse_cedt(enum acpi_cedt_type id,
 int __init_or_acpilib
 acpi_table_parse_keyp(enum acpi_keyp_type id,
 		      acpi_tbl_entry_handler_arg handler_arg, void *arg);
+void __init_or_acpilib keyp_setup_nr_ide_stream(struct pci_bus *bus);
 #else
 static inline int acpi_table_parse_keyp(enum acpi_keyp_type id,
 					acpi_tbl_entry_handler_arg handler_arg,
@@ -246,6 +247,8 @@ static inline int acpi_table_parse_keyp(enum acpi_keyp_type id,
 {
 	return -EOPNOTSUPP;
 }
+
+static inline void keyp_setup_nr_ide_stream(struct pci_bus *bus) {}
 #endif
 
 int acpi_parse_mcfg (struct acpi_table_header *header);

---

## [13] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 12/27] iommu/vt-d: Cache max domain ID to avoid redundant calculation*

From: Lu Baolu <baolu.lu@linux.intel.com>

The cap_ndoms() helper calculates the maximum available domain ID from
the value of capability register, which can be inefficient if called
repeatedly. Cache the maximum supported domain ID in max_domain_id field
during initialization to avoid redundant calls to cap_ndoms() throughout
the IOMMU driver.

No functionality change.

Signed-off-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/iommu/intel/dmar.c  |  1 +
 drivers/iommu/intel/iommu.c | 10 +++++-----
 drivers/iommu/intel/iommu.h |  1 +
 3 files changed, 7 insertions(+), 5 deletions(-)

diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index ec975c73cfe6..a54934c0536f 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -1099,6 +1099,7 @@ static int alloc_iommu(struct dmar_drhd_unit *drhd)
 	spin_lock_init(&iommu->lock);
 	ida_init(&iommu->domain_ida);
 	mutex_init(&iommu->did_lock);
+	iommu->max_domain_id = cap_ndoms(iommu->cap);
 
 	ver = readl(iommu->reg + DMAR_VER_REG);
 	pr_info("%s: reg_base_addr %llx ver %d:%d cap %llx ecap %llx\n",
diff --git a/drivers/iommu/intel/iommu.c b/drivers/iommu/intel/iommu.c
index 9c3ab9d9f69a..9b02007ef831 100644
--- a/drivers/iommu/intel/iommu.c
+++ b/drivers/iommu/intel/iommu.c
@@ -1356,7 +1356,7 @@ int domain_attach_iommu(struct dmar_domain *domain, struct intel_iommu *iommu)
 	}
 
 	num = ida_alloc_range(&iommu->domain_ida, IDA_START_DID,
-			      cap_ndoms(iommu->cap) - 1, GFP_KERNEL);
+			      iommu->max_domain_id - 1, GFP_KERNEL);
 	if (num < 0) {
 		pr_err("%s: No free domain ids\n", iommu->name);
 		goto err_unlock;
@@ -1420,7 +1420,7 @@ static void copied_context_tear_down(struct intel_iommu *iommu,
 	did_old = context_domain_id(context);
 	context_clear_entry(context);
 
-	if (did_old < cap_ndoms(iommu->cap)) {
+	if (did_old < iommu->max_domain_id) {
 		iommu->flush.flush_context(iommu, did_old,
 					   PCI_DEVID(bus, devfn),
 					   DMA_CCMD_MASK_NOBIT,
@@ -1981,7 +1981,7 @@ static int copy_context_table(struct intel_iommu *iommu,
 			continue;
 
 		did = context_domain_id(&ce);
-		if (did >= 0 && did < cap_ndoms(iommu->cap))
+		if (did >= 0 && did < iommu->max_domain_id)
 			ida_alloc_range(&iommu->domain_ida, did, did, GFP_KERNEL);
 
 		set_context_copied(iommu, bus, devfn);
@@ -2897,7 +2897,7 @@ static ssize_t domains_supported_show(struct device *dev,
 				      struct device_attribute *attr, char *buf)
 {
 	struct intel_iommu *iommu = dev_to_intel_iommu(dev);
-	return sysfs_emit(buf, "%ld\n", cap_ndoms(iommu->cap));
+	return sysfs_emit(buf, "%ld\n", iommu->max_domain_id);
 }
 static DEVICE_ATTR_RO(domains_supported);
 
@@ -2908,7 +2908,7 @@ static ssize_t domains_used_show(struct device *dev,
 	unsigned int count = 0;
 	int id;
 
-	for (id = 0; id < cap_ndoms(iommu->cap); id++)
+	for (id = 0; id < iommu->max_domain_id; id++)
 		if (ida_exists(&iommu->domain_ida, id))
 			count++;
 
diff --git a/drivers/iommu/intel/iommu.h b/drivers/iommu/intel/iommu.h
index d09b92871659..d16b1a51c6d6 100644
--- a/drivers/iommu/intel/iommu.h
+++ b/drivers/iommu/intel/iommu.h
@@ -727,6 +727,7 @@ struct intel_iommu {
 	/* mutex to protect domain_ida */
 	struct mutex	did_lock;
 	struct ida	domain_ida; /* domain id allocator */
+	unsigned long	max_domain_id;
 	unsigned long	*copied_tables; /* bitmap of copied tables */
 	spinlock_t	lock; /* protect context, domain ids */
 	struct root_entry *root_entry; /* virtual address */

---

## [14] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 13/27] iommu/vt-d: Reserve the MSB domain ID bit for the TDX module*

From: Lu Baolu <baolu.lu@linux.intel.com>

The Intel TDX Connect Architecture Specification defines some enhancements
for the VT-d architecture to introduce IOMMU support for TEE-IO requests.
Section 2.2, 'Trusted DMA' states that:

I/O TLB and DID Isolation – When IOMMU is enabled to support TDX Connect,
the IOMMU restricts the VMM’s DID setting, reserving the MSB bit for the
TDX module. The TDX module always sets this reserved bit on the trusted
DMA table. IOMMU tags IOTLB, PASID cache, and context entries to indicate
whether they were created from TEE-IO transactions, ensuring isolation
between TEE and non-TEE requests in translation caches.

Reserve the MSB in the domain ID for the TDX module's use.

Signed-off-by: Lu Baolu <baolu.lu@linux.intel.com>
[djbw: todo: replace SOC table with ACPI table detect]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/iommu/intel/dmar.c | 29 ++++++++++++++++++++++++++++-
 1 file changed, 28 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index a54934c0536f..3ae177463774 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -29,6 +29,8 @@
 #include <linux/numa.h>
 #include <linux/limits.h>
 #include <asm/irq_remapping.h>
+#include <asm/cpu_device_id.h>
+#include <asm/intel-family.h>
 
 #include "iommu.h"
 #include "../irq_remapping.h"
@@ -1033,6 +1035,31 @@ static int map_iommu(struct intel_iommu *iommu, struct dmar_drhd_unit *drhd)
 	return err;
 }
 
+static bool platform_is_tdxc_enhanced(void)
+{
+	return (boot_cpu_data.x86_vfm == INTEL_GRANITERAPIDS_D ||
+		boot_cpu_data.x86_vfm == INTEL_GRANITERAPIDS_X);
+}
+
+static unsigned long iommu_calculate_max_domain_id(struct intel_iommu *iommu)
+{
+	unsigned long ndoms = cap_ndoms(iommu->cap);
+
+	/*
+	 * Intel TDX Connect Architecture Specification, Section 2.2 Trusted DMA
+	 *
+	 * When IOMMU is enabled to support TDX Connect, the IOMMU restricts
+	 * the VMM’s DID setting, reserving the MSB bit for the TDX module. The
+	 * TDX module always sets this reserved bit on the trusted DMA table.
+	 */
+	if (platform_is_tdxc_enhanced() && (iommu->ecap & BIT_ULL(50))) {
+		pr_info_once("Most Significant Bit of domain ID reserved.\n");
+		return ndoms >> 1;
+	}
+
+	return ndoms;
+}
+
 static int alloc_iommu(struct dmar_drhd_unit *drhd)
 {
 	struct intel_iommu *iommu;
@@ -1099,7 +1126,7 @@ static int alloc_iommu(struct dmar_drhd_unit *drhd)
 	spin_lock_init(&iommu->lock);
 	ida_init(&iommu->domain_ida);
 	mutex_init(&iommu->did_lock);
-	iommu->max_domain_id = cap_ndoms(iommu->cap);
+	iommu->max_domain_id = iommu_calculate_max_domain_id(iommu);
 
 	ver = readl(iommu->reg + DMAR_VER_REG);
 	pr_info("%s: reg_base_addr %llx ver %d:%d cap %llx ecap %llx\n",

---

## [15] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 14/27] TODO: x86/virt/tdx: Read TDX Connect global metadata for TDX Connect*

From: Xu Yilun <yilun.xu@linux.intel.com>

Add several global metadata fields for TDX Connect. These metadata field
specify the number of metadata pages needed for IOMMU/IDE/SPDM setup.

TODO:

This patch should be auto-generated by script but for now the TDX
Connect part is not published in global_metadata.json so make the patch
manually. The correct way should be:

The code change is auto-generated by re-running the script in [1] after
uncommenting the "td_conf" and "td_ctrl" part to regenerate the
tdx_global_metadata.{hc} and update them to the existing ones in the
kernel.

  #python tdx.py global_metadata.json tdx_global_metadata.h \
        tdx_global_metadata.c

The 'global_metadata.json' can be fetched from [1].

Link: https://cdrdv2.intel.com/v1/dl/getContent/795381 [1]
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx_global_metadata.h  |  8 ++++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 18 ++++++++++++++++++
 2 files changed, 26 insertions(+)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 2aa741190b93..e7948bca671a 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -39,12 +39,20 @@ struct tdx_sys_info_ext {
 	u8 ext_required;
 };
 
+struct tdx_sys_info_connect {
+	u16 ide_mt_page_count;
+	u16 spdm_mt_page_count;
+	u16 iommu_mt_page_count;
+	u16 spdm_max_dev_info_pages;
+};
+
 struct tdx_sys_info {
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
 	struct tdx_sys_info_td_conf td_conf;
 	struct tdx_sys_info_ext ext;
+	struct tdx_sys_info_connect connect;
 };
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 69be16c1e6ec..63e0a6e7bf29 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -98,6 +98,23 @@ static int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
 	return ret;
 }
 
+static int get_tdx_sys_info_connect(struct tdx_sys_info_connect *sysinfo_connect)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000001, &val)))
+		sysinfo_connect->ide_mt_page_count = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000002, &val)))
+		sysinfo_connect->spdm_mt_page_count = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000003, &val)))
+		sysinfo_connect->iommu_mt_page_count = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000007, &val)))
+		sysinfo_connect->spdm_max_dev_info_pages = val;
+
+	return ret;
+}
+
 static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -107,6 +124,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
 	ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
+	ret = ret ?: get_tdx_sys_info_connect(&sysinfo->connect);
 
 	return ret;
 }

---

## [16] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 15/27] x86/virt/tdx: Extend tdx_page_array to support IOMMU_MT*

From: Xu Yilun <yilun.xu@linux.intel.com>

IOMMU_MT is another TDX Module defined structure similar to HPA_ARRAY_T
and HPA_LIST_INFO. The difference is it supports multi-order contiguous
pages. It adds an additional NUM_PAGES field for every multi-order page
entry [1].

Add an dedicated allocation helper for IOMMU_MT. Maybe a general
allocation helper for multi-order is better but could postpond until
another user appears.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 +
 arch/x86/virt/vmx/tdx/tdx.c | 79 ++++++++++++++++++++++++++++++++++---
 include/linux/mm.h          |  2 +
 3 files changed, 77 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index d53260aadb0b..4aae56fa225f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -155,6 +155,8 @@ void tdx_page_array_ctrl_leak(struct tdx_page_array *array);
 int tdx_page_array_ctrl_release(struct tdx_page_array *array,
 				unsigned int nr_released,
 				u64 released_hpa);
+struct tdx_page_array *
+tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages);
 
 struct tdx_td {
 	/* TD root structure: */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9d4cebace054..1061adcc041f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -294,8 +294,15 @@ static int tdx_page_array_fill_root(struct tdx_page_array *array,
 			    TDX_PAGE_ARRAY_MAX_NENTS);
 
 	entries = (u64 *)page_address(array->root);
-	for (i = 0; i < array->nents; i++)
-		entries[i] = page_to_phys(array->pages[offset + i]);
+	for (i = 0; i < array->nents; i++) {
+		struct page *page = array->pages[offset + i];
+
+		entries[i] = page_to_phys(page);
+
+		/* Now only for iommu_mt */
+		if (compound_nr(page) > 1)
+			entries[i] |= compound_nr(page);
+	}
 
 	return array->nents;
 }
@@ -305,7 +312,7 @@ static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
 	unsigned long i;
 
 	for (i = 0; i < nr_pages; i++)
-		__free_page(pages[i]);
+		put_page(pages[i]);
 }
 
 static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages)
@@ -456,10 +463,16 @@ static bool tdx_page_array_ctrl_match(struct tdx_page_array *array,
 
 	entries = (u64 *)page_address(array->root);
 	for (i = 0; i < nents; i++) {
-		if (page_to_phys(array->pages[offset + i]) != entries[i]) {
+		struct page *page = array->pages[offset + i];
+		u64 val = page_to_phys(page);
+
+		/* Now only for iommu_mt */
+		if (compound_nr(page) > 1)
+			val |= compound_nr(page);
+
+		if (val != entries[i]) {
 			pr_err("%s entry[%d] [0x%llx] doesn't match page hpa [0x%llx]\n",
-			       __func__, i, entries[i],
-			       page_to_phys(array->pages[offset + i]));
+			       __func__, i, entries[i], val);
 			return false;
 		}
 	}
@@ -494,6 +507,60 @@ int tdx_page_array_ctrl_release(struct tdx_page_array *array,
 }
 EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_release);
 
+struct tdx_page_array *
+tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages)
+{
+	unsigned int nr_entries = 2 + nr_mt_pages;
+	int ret;
+
+	if (nr_entries > TDX_PAGE_ARRAY_MAX_NENTS)
+		return NULL;
+
+	struct tdx_page_array *array __free(kfree) = kzalloc(sizeof(*array),
+							     GFP_KERNEL);
+	if (!array)
+		return NULL;
+
+	struct page *root __free(__free_page) = alloc_page(GFP_KERNEL |
+							   __GFP_ZERO);
+	if (!root)
+		return NULL;
+
+	struct page **pages __free(kfree) = kcalloc(nr_entries, sizeof(*pages),
+						    GFP_KERNEL);
+	if (!pages)
+		return NULL;
+
+	/* TODO: folio_alloc_node() is preferred, but need numa info */
+	struct folio *t_iq __free(folio_put) = folio_alloc(GFP_KERNEL |
+							   __GFP_ZERO,
+							   iq_order);
+	if (!t_iq)
+		return NULL;
+
+	struct folio *t_ctxiq __free(folio_put) = folio_alloc(GFP_KERNEL |
+							      __GFP_ZERO,
+							      iq_order);
+	if (!t_ctxiq)
+		return NULL;
+
+	ret = tdx_alloc_pages_bulk(nr_mt_pages, pages + 2);
+	if (ret)
+		return NULL;
+
+	pages[0] = folio_page(no_free_ptr(t_iq), 0);
+	pages[1] = folio_page(no_free_ptr(t_ctxiq), 0);
+
+	array->nr_pages = nr_entries;
+	array->pages = no_free_ptr(pages);
+	array->root = no_free_ptr(root);
+
+	tdx_page_array_fill_root(array, 0);
+
+	return no_free_ptr(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_create_iommu_mt);
+
 static int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
diff --git a/include/linux/mm.h b/include/linux/mm.h
index 1ae97a0b8ec7..719cc479f9e7 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -1360,6 +1360,8 @@ static inline void folio_put(struct folio *folio)
 		__folio_put(folio);
 }
 
+DEFINE_FREE(folio_put, struct folio *, if (_T) folio_put(_T))
+
 /**
  * folio_put_refs - Reduce the reference count on a folio.
  * @folio: The folio.

---

## [17] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 16/27] x86/virt/tdx: Add SEAMCALL wrappers for trusted IOMMU setup and clear*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Add SEAMCALLs to setup/clear trusted IOMMU for TDX Connect.

Enable TEE I/O support for a target device requires to setup trusted IOMMU
for the related IOMMU device first, even only for enabling physical secure
links like SPDM/IDE.

TDH.IOMMU.SETUP takes the register base address (VTBAR) to position an
IOMMU device, and outputs an IOMMU_ID as the trusted IOMMU identifier.
TDH.IOMMU.CLEAR takes the IOMMU_ID to reverse the setup.

More information see Intel TDX Connect ABI Specification [1]
Section 3.2 TDX Connect Host-Side (SEAMCALL) Interface Functions.

[1]: https://cdrdv2.intel.com/v1/dl/getContent/858625

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c | 28 ++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  2 ++
 3 files changed, 32 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 4aae56fa225f..5f2bc970cf25 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -223,6 +223,8 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 u64 tdh_ext_mem_add(struct tdx_page_array *pg_arr);
 u64 tdh_ext_init(void);
+u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id);
+u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_enable(void)  { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 1061adcc041f..0f34009411fb 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2362,3 +2362,31 @@ u64 tdh_ext_init(void)
 	return seamcall(TDH_EXT_INIT, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_ext_init);
+
+u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id)
+{
+	struct tdx_module_args args = {
+		.rcx = vtbar,
+		.rdx = page_to_phys(iommu_mt->root),
+	};
+	u64 r;
+
+	tdx_clflush_page_array(iommu_mt);
+
+	r = seamcall_ret(TDH_IOMMU_SETUP, &args);
+
+	*iommu_id = args.rcx;
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_iommu_setup);
+
+u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
+{
+	struct tdx_module_args args = {
+		.rcx = iommu_id,
+		.rdx = page_to_phys(iommu_mt->root),
+	};
+
+	return seamcall_ret(TDH_IOMMU_CLEAR, &args);
+}
+EXPORT_SYMBOL_GPL(tdh_iommu_clear);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index f4bcfec7fb86..13d11c8ad33d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -48,6 +48,8 @@
 #define TDH_SYS_CONFIG			45
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
+#define TDH_IOMMU_SETUP			128
+#define TDH_IOMMU_CLEAR			129
 
 /*
  * SEAMCALL leaf:

---

## [18] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 17/27] iommu/vt-d: Export a helper to do function for each dmar_drhd_unit*

From: Xu Yilun <yilun.xu@linux.intel.com>

Enable the tdx-host module to get VTBAR address for every IOMMU device.
The VTBAR address is for TDX Module to identify the IOMMU device and
setup its trusted configuraion.

Suggested-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/iommu/intel/dmar.c | 16 ++++++++++++++++
 include/linux/dmar.h       |  2 ++
 2 files changed, 18 insertions(+)

diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index 3ae177463774..222d66bff80a 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -2429,3 +2429,19 @@ bool dmar_platform_optin(void)
 	return ret;
 }
 EXPORT_SYMBOL_GPL(dmar_platform_optin);
+
+int do_for_each_drhd_unit(int (*fn)(struct dmar_drhd_unit *))
+{
+	struct dmar_drhd_unit *drhd;
+	int ret;
+
+	guard(rwsem_read)(&dmar_global_lock);
+
+	for_each_drhd_unit(drhd) {
+		ret = fn(drhd);
+		if (ret)
+			return ret;
+	}
+	return 0;
+}
+EXPORT_SYMBOL_GPL(do_for_each_drhd_unit);
diff --git a/include/linux/dmar.h b/include/linux/dmar.h
index 692b2b445761..f4ca8e0c67e5 100644
--- a/include/linux/dmar.h
+++ b/include/linux/dmar.h
@@ -86,6 +86,8 @@ extern struct list_head dmar_drhd_units;
 				dmar_rcu_check())			\
 		if (i=drhd->iommu, 0) {} else 
 
+extern int do_for_each_drhd_unit(int (*fn)(struct dmar_drhd_unit *));
+
 static inline bool dmar_rcu_check(void)
 {
 	return rwsem_is_locked(&dmar_global_lock) ||

---

## [19] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 18/27] coco/tdx-host: Setup all trusted IOMMUs on TDX Connect init*

From: Xu Yilun <yilun.xu@linux.intel.com>

Setup all trusted IOMMUs on TDX Connect initialization and clear all on
TDX Connect removal.

Trusted IOMMU setup is the pre-condition for all following TDX Connect
operations such as SPDM/IDE setup. It is more of a platform
configuration than a standalone IOMMU configuration, so put the
implementation in tdx-host driver.

There is no dedicated way to enumerate which IOMMU devices support
trusted operations. The host has to call TDH.IOMMU.SETUP on all IOMMU
devices and tell their trusted capability by the return value.

Suggested-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 90 +++++++++++++++++++++++++++
 1 file changed, 90 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 2411c7d34b6b..cdd2a4670c96 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -5,6 +5,7 @@
  * Copyright (C) 2025 Intel Corporation
  */
 
+#include <linux/dmar.h>
 #include <linux/kernel.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
@@ -128,6 +129,85 @@ static void unregister_link_tsm(void *data)
 	tsm_unregister(link_dev);
 }
 
+static DEFINE_XARRAY(tlink_iommu_xa);
+
+static void tdx_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
+{
+	u64 r;
+
+	r = tdh_iommu_clear(iommu_id, iommu_mt);
+	if (r) {
+		pr_err("%s fail to clear tdx iommu\n", __func__);
+		goto leak;
+	}
+
+	if (tdx_page_array_ctrl_release(iommu_mt, iommu_mt->nr_pages,
+					page_to_phys(iommu_mt->root))) {
+		pr_err("%s fail to release metadata pages\n", __func__);
+		goto leak;
+	}
+
+	return;
+
+leak:
+	tdx_page_array_ctrl_leak(iommu_mt);
+}
+
+static int tdx_iommu_enable_one(struct dmar_drhd_unit *drhd)
+{
+	unsigned int nr_pages = tdx_sysinfo->connect.iommu_mt_page_count;
+	u64 r, iommu_id;
+	int ret;
+
+	struct tdx_page_array *iommu_mt __free(tdx_page_array_free) =
+		tdx_page_array_create_iommu_mt(1, nr_pages);
+	if (!iommu_mt)
+		return -ENOMEM;
+
+	do {
+		r = tdh_iommu_setup(drhd->reg_base_addr, iommu_mt, &iommu_id);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	/* This drhd doesn't support tdx mode, skip. */
+	if ((r & TDX_SEAMCALL_STATUS_MASK)  == TDX_OPERAND_INVALID)
+		return 0;
+
+	if (r) {
+		pr_err("fail to enable tdx mode for DRHD[0x%llx]\n",
+		       drhd->reg_base_addr);
+		return -EFAULT;
+	}
+
+	ret = xa_insert(&tlink_iommu_xa, (unsigned long)iommu_id,
+			no_free_ptr(iommu_mt), GFP_KERNEL);
+	if (ret) {
+		tdx_iommu_clear(iommu_id, iommu_mt);
+		return ret;
+	}
+
+	return 0;
+}
+
+static void tdx_iommu_disable_all(void *data)
+{
+	struct tdx_page_array *iommu_mt;
+	unsigned long iommu_id;
+
+	xa_for_each(&tlink_iommu_xa, iommu_id, iommu_mt)
+		tdx_iommu_clear(iommu_id, iommu_mt);
+}
+
+static int tdx_iommu_enable_all(void)
+{
+	int ret;
+
+	ret = do_for_each_drhd_unit(tdx_iommu_enable_one);
+	if (ret)
+		tdx_iommu_disable_all(NULL);
+
+	return ret;
+}
+
 static int tdx_connect_init(struct device *dev)
 {
 	struct tsm_dev *link;
@@ -149,6 +229,16 @@ static int tdx_connect_init(struct device *dev)
 		return ret;
 	}
 
+	ret = tdx_iommu_enable_all();
+	if (ret) {
+		dev_err(dev, "Enable tdx iommu failed\n");
+		return ret;
+	}
+
+	ret = devm_add_action_or_reset(dev, tdx_iommu_disable_all, NULL);
+	if (ret)
+		return ret;
+
 	link = tsm_register(dev, &tdx_link_ops);
 	if (IS_ERR(link)) {
 		dev_err(dev, "failed to register TSM: (%pe)\n", link);

---

## [20] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 19/27] coco/tdx-host: Add a helper to exchange SPDM messages through DOE*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

TDX host uses this function to exchange TDX Module encrypted data with
devices via SPDM. It is unfortunate that TDX passes raw DOE frames with
headers included and the PCI DOE core wants payloads separated from
headers.

This conversion code is about the same amount of work as teaching the PCI
DOE driver to support raw frames. Unless and until another raw frame use
case shows up, just do this conversion in the TDX TSM driver.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 61 +++++++++++++++++++++++++++
 1 file changed, 61 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index cdd2a4670c96..f5a869443b15 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -5,11 +5,13 @@
  * Copyright (C) 2025 Intel Corporation
  */
 
+#include <linux/bitfield.h>
 #include <linux/dmar.h>
 #include <linux/kernel.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
+#include <linux/pci-doe.h>
 #include <linux/pci-tsm.h>
 #include <linux/sysfs.h>
 #include <linux/tsm.h>
@@ -43,6 +45,65 @@ static struct tdx_link *to_tdx_link(struct pci_tsm *tsm)
 	return container_of(tsm, struct tdx_link, pci.base_tsm);
 }
 
+#define PCI_DOE_DATA_OBJECT_HEADER_1_OFFSET	0
+#define PCI_DOE_DATA_OBJECT_HEADER_2_OFFSET	4
+#define PCI_DOE_DATA_OBJECT_HEADER_SIZE		8
+#define PCI_DOE_DATA_OBJECT_PAYLOAD_OFFSET	PCI_DOE_DATA_OBJECT_HEADER_SIZE
+
+#define PCI_DOE_PROTOCOL_SECURE_SPDM		2
+
+static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_link *tlink,
+						void *request, size_t request_sz,
+						void *response, size_t response_sz)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	void *req_pl_addr, *resp_pl_addr;
+	size_t req_pl_sz, resp_pl_sz;
+	u32 data, len;
+	u16 vendor;
+	u8 type;
+	int ret;
+
+	/*
+	 * pci_doe() accept DOE PAYLOAD only but request carries DOE HEADER so
+	 * shift the buffers, skip DOE HEADER in request buffer, and fill DOE
+	 * HEADER in response buffer manually.
+	 */
+
+	data = le32_to_cpu(*(__le32 *)(request + PCI_DOE_DATA_OBJECT_HEADER_1_OFFSET));
+	vendor = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_VID, data);
+	type = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_TYPE, data);
+
+	data = le32_to_cpu(*(__le32 *)(request + PCI_DOE_DATA_OBJECT_HEADER_2_OFFSET));
+	len = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_2_LENGTH, data);
+
+	req_pl_sz = len * sizeof(__le32) - PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+	resp_pl_sz = response_sz - PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+	req_pl_addr = request + PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+	resp_pl_addr = response + PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+
+	ret = pci_doe(tlink->pci.doe_mb, PCI_VENDOR_ID_PCI_SIG, type,
+		      req_pl_addr, req_pl_sz, resp_pl_addr, resp_pl_sz);
+	if (ret < 0) {
+		pci_err(pdev, "spdm msg exchange fail %d\n", ret);
+		return ret;
+	}
+
+	data = FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_1_VID, vendor) |
+	       FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_1_TYPE, type);
+	*(__le32 *)(response + PCI_DOE_DATA_OBJECT_HEADER_1_OFFSET) = cpu_to_le32(data);
+
+	len = (ret + PCI_DOE_DATA_OBJECT_HEADER_SIZE) / sizeof(__le32);
+	data = FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_2_LENGTH, len);
+	*(__le32 *)(response + PCI_DOE_DATA_OBJECT_HEADER_2_OFFSET) = cpu_to_le32(data);
+
+	ret += PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+
+	pci_dbg(pdev, "%s complete: vendor 0x%x type 0x%x rsp_sz %d\n",
+		__func__, vendor, type, ret);
+	return ret;
+}
+
 static int tdx_link_connect(struct pci_dev *pdev)
 {
 	return -ENXIO;

---

## [21] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect() handlers prototype*

From: Xu Yilun <yilun.xu@linux.intel.com>

Add basic skeleton for connect()/disconnect() handlers. The major steps
are SPDM setup first and then IDE selective stream setup.

No detailed TDX Connect implementation.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 49 ++++++++++++++++++++++++++-
 1 file changed, 48 insertions(+), 1 deletion(-)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index f5a869443b15..0d052a1acf62 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -104,13 +104,60 @@ static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_link *tlink,
 	return ret;
 }
 
+static void tdx_spdm_session_teardown(struct tdx_link *tlink)
+{
+}
+
+static int tdx_spdm_session_setup(struct tdx_link *tlink)
+{
+	return -EOPNOTSUPP;
+}
+
+static void tdx_ide_stream_teardown(struct tdx_link *tlink)
+{
+}
+
+static int tdx_ide_stream_setup(struct tdx_link *tlink)
+{
+	return -EOPNOTSUPP;
+}
+
+static void __tdx_link_disconnect(struct tdx_link *tlink)
+{
+	tdx_ide_stream_teardown(tlink);
+	tdx_spdm_session_teardown(tlink);
+}
+
+DEFINE_FREE(__tdx_link_disconnect, struct tdx_link *, if (_T) __tdx_link_disconnect(_T))
+
 static int tdx_link_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct tdx_link *tlink = to_tdx_link(pdev->tsm);
+	int ret;
+
+	struct tdx_link *__tlink __free(__tdx_link_disconnect) = tlink;
+	ret = tdx_spdm_session_setup(tlink);
+	if (ret) {
+		pci_err(pdev, "fail to setup spdm session\n");
+		return ret;
+	}
+
+	ret = tdx_ide_stream_setup(tlink);
+	if (ret) {
+		pci_err(pdev, "fail to setup ide stream\n");
+		return ret;
+	}
+
+	tlink = no_free_ptr(__tlink);
+
+	return 0;
 }
 
 static void tdx_link_disconnect(struct pci_dev *pdev)
 {
+	struct tdx_link *tlink = to_tdx_link(pdev->tsm);
+
+	__tdx_link_disconnect(tlink);
 }
 
 static struct pci_tsm_ops tdx_link_ops;

---

## [22] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 21/27] x86/virt/tdx: Add SEAMCALL wrappers for SPDM management*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Add several SEAMCALL wrappers for SPDM management. TDX Module requires
HPA_ARRAY_T structure as input/output parameters for these SEAMCALLs.
So use tdx_page_array as for these wrappers.

- TDH.SPDM.CREATE creates SPDM session metadata buffers for TDX Module.
- TDH.SPDM.DELETE destroys SPDM session metadata and returns these
  buffers to host, after checking no reference attached to the metadata.
- TDH.SPDM.CONNECT establishes a new SPDM session with the device.
- TDH.SPDM.DISCONNECT tears down the SPDM session with the device.
- TDH.SPDM.MNG supports three SPDM runtime operations: HEARTBEAT,
  KEY_UPDATE and DEV_INFO_RECOLLECTION.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  |  11 +++
 arch/x86/virt/vmx/tdx/tdx.c | 133 ++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |   5 ++
 3 files changed, 149 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 5f2bc970cf25..97e0d7a1f38d 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -225,6 +225,17 @@ u64 tdh_ext_mem_add(struct tdx_page_array *pg_arr);
 u64 tdh_ext_init(void);
 u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id);
 u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt);
+u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id);
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
+		    unsigned int *nr_released, u64 *released_hpa);
+u64 tdh_spdm_connect(u64 spdm_id, struct page *spdm_conf,
+		     struct page *spdm_rsp, struct page *spdm_req,
+		     struct tdx_page_array *spdm_out, u64 *spdm_req_or_out_len);
+u64 tdh_spdm_disconnect(u64 spdm_id, struct page *spdm_rsp,
+			struct page *spdm_req, u64 *spdm_req_len);
+u64 tdh_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
+		 struct page *spdm_rsp, struct page *spdm_req,
+		 struct tdx_page_array *spdm_out, u64 *spdm_req_or_out_len);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_enable(void)  { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0f34009411fb..86dd855d7361 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2390,3 +2390,136 @@ u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
 	return seamcall_ret(TDH_IOMMU_CLEAR, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_iommu_clear);
+
+union hpa_array_t {
+	struct {
+		u64 rsvd0:12;
+		u64 pfn:40;
+		u64 rsvd1:3;
+		u64 array_size:9;
+	};
+	u64 raw;
+};
+
+static u64 hpa_array_t_assign_raw(struct tdx_page_array *array)
+{
+	union hpa_array_t hat;
+
+	if (array->root) {
+		hat.raw = page_to_phys(array->root);
+		hat.array_size = array->nents - 1;
+	} else {
+		hat.raw = page_to_phys(array->pages[0]);
+	}
+
+	return hat.raw;
+}
+
+static u64 hpa_array_t_release_raw(struct tdx_page_array *array)
+{
+	if (array->root)
+		return page_to_phys(array->root);
+
+	return 0;
+}
+
+u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id)
+{
+	struct tdx_module_args args = {
+		.rcx = func_id,
+		.rdx = hpa_array_t_assign_raw(spdm_mt)
+	};
+	u64 r;
+
+	tdx_clflush_page_array(spdm_mt);
+
+	r = seamcall_ret(TDH_SPDM_CREATE, &args);
+
+	*spdm_id = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_spdm_create);
+
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
+		    unsigned int *nr_released, u64 *released_hpa)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = hpa_array_t_release_raw(spdm_mt),
+	};
+	union hpa_array_t released;
+	u64 r;
+
+	r = seamcall_ret(TDH_SPDM_DELETE, &args);
+	if (r < 0)
+		return r;
+
+	released.raw = args.rcx;
+	*nr_released = released.array_size + 1;
+	*released_hpa = released.pfn << PAGE_SHIFT;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_spdm_delete);
+
+u64 tdh_spdm_connect(u64 spdm_id, struct page *spdm_conf,
+		     struct page *spdm_rsp, struct page *spdm_req,
+		     struct tdx_page_array *spdm_out, u64 *spdm_req_or_out_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = page_to_phys(spdm_conf),
+		.r8 = page_to_phys(spdm_rsp),
+		.r9 = page_to_phys(spdm_req),
+		.r10 = hpa_array_t_assign_raw(spdm_out),
+	};
+	u64 r;
+
+	r = seamcall_ret(TDH_SPDM_CONNECT, &args);
+
+	*spdm_req_or_out_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_spdm_connect);
+
+u64 tdh_spdm_disconnect(u64 spdm_id, struct page *spdm_rsp,
+			struct page *spdm_req, u64 *spdm_req_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = page_to_phys(spdm_rsp),
+		.r8 = page_to_phys(spdm_req),
+	};
+	u64 r;
+
+	r = seamcall_ret(TDH_SPDM_DISCONNECT, &args);
+
+	*spdm_req_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_spdm_disconnect);
+
+u64 tdh_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
+		 struct page *spdm_rsp, struct page *spdm_req,
+		 struct tdx_page_array *spdm_out, u64 *spdm_req_or_out_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = spdm_op,
+		.r8 = spdm_param ? page_to_phys(spdm_param) : -1,
+		.r9 = page_to_phys(spdm_rsp),
+		.r10 = page_to_phys(spdm_req),
+		.r11 = spdm_out ? hpa_array_t_assign_raw(spdm_out) : -1,
+	};
+	u64 r;
+
+	r = seamcall_ret(TDH_SPDM_MNG, &args);
+
+	*spdm_req_or_out_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_spdm_mng);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 13d11c8ad33d..eb67fd9d1f55 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -50,6 +50,11 @@
 #define TDH_EXT_MEM_ADD			61
 #define TDH_IOMMU_SETUP			128
 #define TDH_IOMMU_CLEAR			129
+#define TDH_SPDM_CREATE			130
+#define TDH_SPDM_DELETE			131
+#define TDH_SPDM_CONNECT		142
+#define TDH_SPDM_DISCONNECT		143
+#define TDH_SPDM_MNG			144
 
 /*
  * SEAMCALL leaf:

---

## [23] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 22/27] coco/tdx-host: Implement SPDM session setup*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Implementation for a most straightforward SPDM session setup, using all
default session options. Retrieve device info data from TDX Module which
contains the SPDM negotiation results.

TDH.SPDM.CONNECT/DISCONNECT are TDX Module Extension introduced
SEAMCALLs which can run for longer periods and interruptible. But there
is resource constraints that limit how many SEAMCALLs of this kind can
run simultaneously. The current situation is One SEAMCALL at a time. [*]
Otherwise TDX_OPERAND_BUSY is returned. To avoid "broken indefinite"
retry, a tdx_ext_lock is used to guard these SEAMCALLs.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx_errno.h      |   2 +
 drivers/virt/coco/tdx-host/tdx-host.c | 275 +++++++++++++++++++++++++-
 2 files changed, 276 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx_errno.h b/arch/x86/include/asm/tdx_errno.h
index 6a5f183cf119..86d011cb753e 100644
--- a/arch/x86/include/asm/tdx_errno.h
+++ b/arch/x86/include/asm/tdx_errno.h
@@ -27,6 +27,8 @@
 #define TDX_EPT_WALK_FAILED			0xC0000B0000000000ULL
 #define TDX_EPT_ENTRY_STATE_INCORRECT		0xC0000B0D00000000ULL
 #define TDX_METADATA_FIELD_NOT_READABLE		0xC0000C0200000000ULL
+#define TDX_SPDM_SESSION_KEY_REQUIRE_REFRESH	0xC0000F4500000000ULL
+#define TDX_SPDM_REQUEST			0xC0000F5700000000ULL
 
 /*
  * TDX module operand ID, appears in 31:0 part of error code as
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 0d052a1acf62..258539cf0cdf 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -16,6 +16,7 @@
 #include <linux/sysfs.h>
 #include <linux/tsm.h>
 #include <linux/device/faux.h>
+#include <linux/vmalloc.h>
 #include <asm/cpu_device_id.h>
 #include <asm/tdx.h>
 #include <asm/tdx_global_metadata.h>
@@ -36,8 +37,34 @@ MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
  */
 static const struct tdx_sys_info *tdx_sysinfo;
 
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
 struct tdx_link {
 	struct pci_tsm_pf0 pci;
+	u32 func_id;
+	struct page *in_msg;
+	struct page *out_msg;
+
+	u64 spdm_id;
+	struct page *spdm_conf;
+	struct tdx_page_array *spdm_mt;
+	unsigned int dev_info_size;
+	void *dev_info_data;
 };
 
 static struct tdx_link *to_tdx_link(struct pci_tsm *tsm)
@@ -104,13 +131,218 @@ static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_link *tlink,
 	return ret;
 }
 
+static int tdx_spdm_session_keyupdate(struct tdx_link *tlink);
+
+static int tdx_link_event_handler(struct tdx_link *tlink,
+				  u64 tdx_ret, u64 out_msg_sz)
+{
+	int ret;
+
+	if (tdx_ret == TDX_SUCCESS)
+		return 0;
+
+	if (tdx_ret == TDX_INTERRUPTED_RESUMABLE)
+		return -EAGAIN;
+
+	if (tdx_ret == TDX_SPDM_REQUEST) {
+		ret = tdx_spdm_msg_exchange(tlink,
+					    page_address(tlink->out_msg),
+					    out_msg_sz,
+					    page_address(tlink->in_msg),
+					    PAGE_SIZE);
+		if (ret < 0)
+			return ret;
+
+		return -EAGAIN;
+	}
+
+	if (tdx_ret == TDX_SPDM_SESSION_KEY_REQUIRE_REFRESH) {
+		/* keyupdate won't trigger this error again, no recursion risk */
+		ret = tdx_spdm_session_keyupdate(tlink);
+		if (ret)
+			return ret;
+
+		return -EAGAIN;
+	}
+
+	return -EFAULT;
+}
+
+/*
+ * Currently TDX Module extension introduced SEAMCALLs can't be executed in
+ * parallel and can fail with TDX_OPERAND_BUSY. Use a global mutex to serialize
+ * them.
+ */
+static DEFINE_MUTEX(tdx_ext_lock);
+
+enum tdx_spdm_mng_op {
+	TDX_SPDM_MNG_HEARTBEAT = 0,
+	TDX_SPDM_MNG_KEY_UPDATE = 1,
+	TDX_SPDM_MNG_RECOLLECT = 2,
+};
+
+static int tdx_spdm_session_mng(struct tdx_link *tlink,
+				enum tdx_spdm_mng_op op)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_spdm_mng(tlink->spdm_id, op, NULL, tlink->in_msg,
+				 tlink->out_msg, NULL, &out_msg_sz);
+		ret = tdx_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	return ret;
+}
+
+static int tdx_spdm_session_keyupdate(struct tdx_link *tlink)
+{
+	return tdx_spdm_session_mng(tlink, TDX_SPDM_MNG_KEY_UPDATE);
+}
+
+static void *tdx_dup_array_data(struct tdx_page_array *array,
+				unsigned int data_size)
+{
+	unsigned int npages = (data_size + PAGE_SIZE - 1) / PAGE_SIZE;
+	void *data, *dup_data;
+
+	if (npages > array->nr_pages)
+		return NULL;
+
+	data = vm_map_ram(array->pages, npages, -1);
+	if (!data)
+		return NULL;
+
+	dup_data = kmemdup(data, data_size, GFP_KERNEL);
+	vm_unmap_ram(data, npages);
+
+	return dup_data;
+}
+
+static int tdx_spdm_session_connect(struct tdx_link *tlink,
+				    struct tdx_page_array *dev_info)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_spdm_connect(tlink->spdm_id, tlink->spdm_conf,
+				     tlink->in_msg, tlink->out_msg,
+				     dev_info, &out_msg_sz);
+		ret = tdx_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	if (ret)
+		return ret;
+
+	tlink->dev_info_size = out_msg_sz;
+	return 0;
+}
+
+static void tdx_spdm_session_disconnect(struct tdx_link *tlink)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_spdm_disconnect(tlink->spdm_id, tlink->in_msg,
+					tlink->out_msg, &out_msg_sz);
+		ret = tdx_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	WARN_ON(ret);
+
+	tlink->dev_info_size = 0;
+}
+
+static int tdx_spdm_create(struct tdx_link *tlink)
+{
+	unsigned int nr_pages = tdx_sysinfo->connect.spdm_mt_page_count;
+	u64 spdm_id, r;
+
+	struct tdx_page_array *spdm_mt __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages, true);
+	if (!spdm_mt)
+		return -ENOMEM;
+
+	r = tdh_spdm_create(tlink->func_id, spdm_mt, &spdm_id);
+	if (r)
+		return -EFAULT;
+
+	tlink->spdm_id = spdm_id;
+	tlink->spdm_mt = no_free_ptr(spdm_mt);
+	return 0;
+}
+
+static void tdx_spdm_delete(struct tdx_link *tlink)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	unsigned int nr_released;
+	u64 released_hpa, r;
+
+	r = tdh_spdm_delete(tlink->spdm_id, tlink->spdm_mt, &nr_released, &released_hpa);
+	if (r) {
+		pci_err(pdev, "fail to delete spdm\n");
+		goto leak;
+	}
+
+	if (tdx_page_array_ctrl_release(tlink->spdm_mt, nr_released, released_hpa)) {
+		pci_err(pdev, "fail to release metadata pages\n");
+		goto leak;
+	}
+
+	goto out;
+
+leak:
+	tdx_page_array_ctrl_leak(tlink->spdm_mt);
+out:
+	tlink->spdm_mt = NULL;
+}
+
 static void tdx_spdm_session_teardown(struct tdx_link *tlink)
 {
+	kfree(tlink->dev_info_data);
+
+	if (tlink->dev_info_size)
+		tdx_spdm_session_disconnect(tlink);
+
+	if (tlink->spdm_mt)
+		tdx_spdm_delete(tlink);
 }
 
+DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_link *, if (_T) tdx_spdm_session_teardown(_T))
+
 static int tdx_spdm_session_setup(struct tdx_link *tlink)
 {
-	return -EOPNOTSUPP;
+	unsigned int nr_pages = tdx_sysinfo->connect.spdm_max_dev_info_pages;
+	int ret;
+
+	struct tdx_link *__tlink __free(tdx_spdm_session_teardown) = tlink;
+	ret = tdx_spdm_create(tlink);
+	if (ret)
+		return ret;
+
+	struct tdx_page_array *dev_info __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages, true);
+	if (!dev_info)
+		return -ENOMEM;
+
+	ret = tdx_spdm_session_connect(tlink, dev_info);
+	if (ret)
+		return ret;
+
+	tlink->dev_info_data = tdx_dup_array_data(dev_info,
+						  tlink->dev_info_size);
+	if (!tlink->dev_info_data)
+		return -ENOMEM;
+
+	tlink = no_free_ptr(__tlink);
+
+	return 0;
 }
 
 static void tdx_ide_stream_teardown(struct tdx_link *tlink)
@@ -160,11 +392,26 @@ static void tdx_link_disconnect(struct pci_dev *pdev)
 	__tdx_link_disconnect(tlink);
 }
 
+struct spdm_config_info_t {
+	u32 vmm_spdm_cap;
+#define SPDM_CAP_HBEAT          BIT(13)
+#define SPDM_CAP_KEY_UPD        BIT(14)
+	u8 spdm_session_policy;
+	u8 certificate_slot_mask;
+	u8 raw_bitstream_requested;
+	u8 reserved[];
+} __packed;
+
 static struct pci_tsm_ops tdx_link_ops;
 
 static struct pci_tsm *tdx_link_pf0_probe(struct tsm_dev *tsm_dev,
 					  struct pci_dev *pdev)
 {
+	const struct spdm_config_info_t spdm_config_info = {
+		/* use a default configuration, may require user input later */
+		.vmm_spdm_cap = SPDM_CAP_KEY_UPD,
+		.certificate_slot_mask = 0xff,
+	};
 	int rc;
 
 	struct tdx_link *tlink __free(kfree) =
@@ -176,6 +423,29 @@ static struct pci_tsm *tdx_link_pf0_probe(struct tsm_dev *tsm_dev,
 	if (rc)
 		return NULL;
 
+	tlink->func_id = tdisp_func_id(pdev);
+
+	struct page *in_msg_page __free(__free_page) =
+		alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!in_msg_page)
+		return NULL;
+
+	struct page *out_msg_page __free(__free_page) =
+		alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!out_msg_page)
+		return NULL;
+
+	struct page *spdm_conf __free(__free_page) =
+		alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!spdm_conf)
+		return NULL;
+
+	memcpy(page_address(spdm_conf), &spdm_config_info, sizeof(spdm_config_info));
+
+	tlink->in_msg = no_free_ptr(in_msg_page);
+	tlink->out_msg = no_free_ptr(out_msg_page);
+	tlink->spdm_conf = no_free_ptr(spdm_conf);
+
 	return &no_free_ptr(tlink)->pci.base_tsm;
 }
 
@@ -183,6 +453,9 @@ static void tdx_link_pf0_remove(struct pci_tsm *tsm)
 {
 	struct tdx_link *tlink = to_tdx_link(tsm);
 
+	__free_page(tlink->in_msg);
+	__free_page(tlink->out_msg);
+	__free_page(tlink->spdm_conf);
 	pci_tsm_pf0_destructor(&tlink->pci);
 	kfree(tlink);
 }

---

## [24] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 23/27] PCI: iov: Export pci_iov_virtfn_bus()*

From: Xu Yilun <yilun.xu@linux.intel.com>

Export pci_iov_virtfn_bus() for tdx-host module. Use it find all PCIe
VF devices associate to a PF0, then calculate the address ranges for IDE
Address Association Registers.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
[djbw: todo: drop this export and teach drivers/pci/ide.c to do this]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/iov.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/drivers/pci/iov.c b/drivers/pci/iov.c
index ac4375954c94..d1bd3419e606 100644
--- a/drivers/pci/iov.c
+++ b/drivers/pci/iov.c
@@ -28,6 +28,7 @@ int pci_iov_virtfn_bus(struct pci_dev *dev, int vf_id)
 	return dev->bus->number + ((dev->devfn + dev->sriov->offset +
 				    dev->sriov->stride * vf_id) >> 8);
 }
+EXPORT_SYMBOL_GPL(pci_iov_virtfn_bus);
 
 int pci_iov_virtfn_devfn(struct pci_dev *dev, int vf_id)
 {

---

## [25] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 24/27] PCI/IDE: Add helpers for RID/Addr Association Registers setup*

From: Xu Yilun <yilun.xu@linux.intel.com>

These Macros are mini helpers mainly for TSM drivers to setup root port
side IDE. TDX Connect will use the Macros in later patches.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
[djbw: todo: move and merge with Aneesh's address association in PCI/IDE core]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/pci-ide.h | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index a30f9460b04a..03e7561d4ad9 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -6,6 +6,20 @@
 #ifndef __PCI_IDE_H__
 #define __PCI_IDE_H__
 
+#define SEL_ADDR1_LOWER GENMASK(31, 20)
+#define SEL_ADDR_UPPER GENMASK_ULL(63, 32)
+#define PREP_PCI_IDE_SEL_ADDR1(base, limit)                    \
+	(FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |             \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW,          \
+		    FIELD_GET(SEL_ADDR1_LOWER, (base))) | \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW,         \
+		    FIELD_GET(SEL_ADDR1_LOWER, (limit))))
+
+#define PREP_PCI_IDE_SEL_RID_2(base, domain)               \
+	(FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |          \
+	 FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, (base)) | \
+	 FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, (domain)))
+
 enum pci_ide_partner_select {
 	PCI_IDE_EP,
 	PCI_IDE_RP,

---

## [26] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 25/27] PCI/IDE: Export pci_ide_domain()*

From: Xu Yilun <yilun.xu@linux.intel.com>

Export another mini helper for TSM drivers to setup root port side IDE.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
[djbw: todo: move this to drivers/pci/ide.c, skip export]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/ide.c       | 3 ++-
 include/linux/pci-ide.h | 1 +
 2 files changed, 3 insertions(+), 1 deletion(-)

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 851633b240e3..b56f1a3033a2 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -345,12 +345,13 @@ void pci_ide_stream_unregister(struct pci_ide *ide)
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_unregister);
 
-static int pci_ide_domain(struct pci_dev *pdev)
+int pci_ide_domain(struct pci_dev *pdev)
 {
 	if (pdev->fm_enabled)
 		return pci_domain_nr(pdev->bus);
 	return 0;
 }
+EXPORT_SYMBOL_GPL(pci_ide_domain);
 
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide)
 {
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 03e7561d4ad9..6a234ece405a 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -75,6 +75,7 @@ struct pci_ide {
 	struct tsm_dev *tsm_dev;
 };
 
+int pci_ide_domain(struct pci_dev *pdev);
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide);
 struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
 void pci_ide_stream_free(struct pci_ide *ide);

---

## [27] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 26/27] x86/virt/tdx: Add SEAMCALL wrappers for IDE stream management*

From: Xu Yilun <yilun.xu@linux.intel.com>

Add several SEAMCALL wrappers for IDE stream management.

- TDH.IDE.STREAM.CREATE creates IDE stream metadata buffers for TDX
  Module, and does root port side IDE configuration.
- TDH.IDE.STREAM.BLOCK clears the root port side IDE configuration.
- TDH.IDE.STREAM.DELETE releases the IDE stream metadata buffers.
- TDH.IDE.STREAM.KM deals with the IDE Key Management protocol (IDE-KM)

More information see Intel TDX Connect ABI Specification [1]
Section 3.2 TDX Connect Host-Side (SEAMCALL) Interface Functions.

[1]: https://cdrdv2.intel.com/v1/dl/getContent/858625

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  | 14 ++++++
 arch/x86/virt/vmx/tdx/tdx.c | 91 +++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  4 ++
 3 files changed, 109 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 97e0d7a1f38d..a10e6a08874c 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -236,6 +236,20 @@ u64 tdh_spdm_disconnect(u64 spdm_id, struct page *spdm_rsp,
 u64 tdh_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
 		 struct page *spdm_rsp, struct page *spdm_req,
 		 struct tdx_page_array *spdm_out, u64 *spdm_req_or_out_len);
+u64 tdh_ide_stream_create(u64 stream_info, u64 spdm_id,
+			  struct tdx_page_array *stream_mt, u64 stream_ctrl,
+			  u64 rid_assoc1, u64 rid_assoc2,
+			  u64 addr_assoc1, u64 addr_assoc2,
+			  u64 addr_assoc3,
+			  u64 *stream_id,
+			  u64 *rp_ide_id);
+u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id);
+u64 tdh_ide_stream_delete(u64 spdm_id, u64 stream_id,
+			  struct tdx_page_array *stream_mt,
+			  unsigned int *nr_released, u64 *released_hpa);
+u64 tdh_ide_stream_km(u64 spdm_id, u64 stream_id, u64 operation,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      u64 *spdm_req_len);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_enable(void)  { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 86dd855d7361..179c976eab01 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2523,3 +2523,94 @@ u64 tdh_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
 	return r;
 }
 EXPORT_SYMBOL_GPL(tdh_spdm_mng);
+
+u64 tdh_ide_stream_create(u64 stream_info, u64 spdm_id,
+			  struct tdx_page_array *stream_mt, u64 stream_ctrl,
+			  u64 rid_assoc1, u64 rid_assoc2,
+			  u64 addr_assoc1, u64 addr_assoc2,
+			  u64 addr_assoc3,
+			  u64 *stream_id,
+			  u64 *rp_ide_id)
+{
+	struct tdx_module_args args = {
+		.rcx = stream_info,
+		.rdx = spdm_id,
+		.r8 = hpa_array_t_assign_raw(stream_mt),
+		.r9 = stream_ctrl,
+		.r10 = rid_assoc1,
+		.r11 = rid_assoc2,
+		.r12 = addr_assoc1,
+		.r13 = addr_assoc2,
+		.r14 = addr_assoc3,
+	};
+	u64 r;
+
+	tdx_clflush_page_array(stream_mt);
+
+	r = seamcall_saved_ret(TDH_IDE_STREAM_CREATE, &args);
+
+	*stream_id = args.rcx;
+	*rp_ide_id = args.rdx;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_ide_stream_create);
+
+u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = stream_id,
+	};
+	u64 r;
+
+	r = seamcall(TDH_IDE_STREAM_BLOCK, &args);
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_ide_stream_block);
+
+u64 tdh_ide_stream_delete(u64 spdm_id, u64 stream_id,
+			  struct tdx_page_array *stream_mt,
+			  unsigned int *nr_released, u64 *released_hpa)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = stream_id,
+		.r8 = hpa_array_t_release_raw(stream_mt),
+	};
+	union hpa_array_t released;
+	u64 r;
+
+	r = seamcall_ret(TDH_IDE_STREAM_DELETE, &args);
+	if (r < 0)
+		return r;
+
+	released.raw = args.rcx;
+	*nr_released = released.array_size + 1;
+	*released_hpa = released.pfn << PAGE_SHIFT;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_ide_stream_delete);
+
+u64 tdh_ide_stream_km(u64 spdm_id, u64 stream_id, u64 operation,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      u64 *spdm_req_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = stream_id,
+		.r8 = operation,
+		.r9 = page_to_phys(spdm_rsp),
+		.r10 = page_to_phys(spdm_req),
+	};
+	u64 r;
+
+	r = seamcall_ret(TDH_IDE_STREAM_KM, &args);
+
+	*spdm_req_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_GPL(tdh_ide_stream_km);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index eb67fd9d1f55..3f73926aebec 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -52,6 +52,10 @@
 #define TDH_IOMMU_CLEAR			129
 #define TDH_SPDM_CREATE			130
 #define TDH_SPDM_DELETE			131
+#define TDH_IDE_STREAM_CREATE		132
+#define TDH_IDE_STREAM_BLOCK		133
+#define TDH_IDE_STREAM_DELETE		134
+#define TDH_IDE_STREAM_KM		135
 #define TDH_SPDM_CONNECT		142
 #define TDH_SPDM_DISCONNECT		143
 #define TDH_SPDM_MNG			144

---

## [28] Dan Williams — 2025-09-19
*Subject: [RFC PATCH 27/27] coco/tdx-host: Implement IDE stream setup/teardown*

From: Xu Yilun <yilun.xu@linux.intel.com>

Implementation for a most straightforward Selective IDE stream setup.
Hard code all parameters for Stream Control Register. And no IDE Key
Refresh support.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 271 +++++++++++++++++++++++++-
 1 file changed, 270 insertions(+), 1 deletion(-)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 258539cf0cdf..7f156d219cee 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -12,6 +12,7 @@
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
 #include <linux/pci-doe.h>
+#include <linux/pci-ide.h>
 #include <linux/pci-tsm.h>
 #include <linux/sysfs.h>
 #include <linux/tsm.h>
@@ -65,6 +66,10 @@ struct tdx_link {
 	struct tdx_page_array *spdm_mt;
 	unsigned int dev_info_size;
 	void *dev_info_data;
+
+	struct pci_ide *ide;
+	struct tdx_page_array *stream_mt;
+	unsigned int stream_id;
 };
 
 static struct tdx_link *to_tdx_link(struct pci_tsm *tsm)
@@ -345,13 +350,277 @@ static int tdx_spdm_session_setup(struct tdx_link *tlink)
 	return 0;
 }
 
+enum tdx_ide_stream_km_op {
+	TDX_IDE_STREAM_KM_SETUP = 0,
+	TDX_IDE_STREAM_KM_REFRESH = 1,
+	TDX_IDE_STREAM_KM_STOP = 2,
+};
+
+static int tdx_ide_stream_km(struct tdx_link *tlink,
+			     enum tdx_ide_stream_km_op op)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	do {
+		r = tdh_ide_stream_km(tlink->spdm_id, tlink->stream_id, op,
+				      tlink->in_msg, tlink->out_msg,
+				      &out_msg_sz);
+		ret = tdx_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	return ret;
+}
+
+static int tdx_ide_stream_key_program(struct tdx_link *tlink)
+{
+	return tdx_ide_stream_km(tlink, TDX_IDE_STREAM_KM_SETUP);
+}
+
+static void tdx_ide_stream_key_stop(struct tdx_link *tlink)
+{
+	tdx_ide_stream_km(tlink, TDX_IDE_STREAM_KM_STOP);
+}
+
+static void add_pdev_to_addr_range(struct pci_dev *pdev,
+				   resource_size_t *start, resource_size_t *end)
+{
+	resource_size_t s = ULLONG_MAX, e = 0;
+	int i;
+
+	for (i = 0; i < PCI_STD_NUM_BARS; i++) {
+		if (!(pci_resource_flags(pdev, i) & IORESOURCE_MEM))
+			continue;
+
+		/* Skip low MMIO BAR */
+		if (pci_resource_start(pdev, i) <= U32_MAX)
+			continue;
+
+		if (!pci_resource_len(pdev, i))
+			continue;
+
+		s = min_t(resource_size_t, s, pci_resource_start(pdev, i));
+		e = max_t(resource_size_t, e, pci_resource_end(pdev, i));
+	}
+
+	*start = min_t(resource_size_t, s, *start);
+	*end = max_t(resource_size_t, e, *end);
+}
+
+static int match_pci_dev_by_devid(struct device *dev, const void *data)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+
+	if (*(const unsigned int *)data == pci_dev_id(pdev))
+		return 1;
+
+	return 0;
+}
+
+/* OPEN: Should we add general address range support in pci/ide.c ? */
+static void setup_addr_range(struct pci_dev *pdev,
+			     resource_size_t *start, resource_size_t *end)
+{
+	struct device *dev;
+	u32 devid;
+	int i;
+
+	add_pdev_to_addr_range(pdev, start, end);
+
+	for (i = 0; i < pci_num_vf(pdev); i++) {
+		devid = PCI_DEVID(pci_iov_virtfn_bus(pdev, i),
+				  pci_iov_virtfn_devfn(pdev, i));
+
+		dev = bus_find_device(&pci_bus_type, NULL, &devid,
+				      match_pci_dev_by_devid);
+		if (dev) {
+			add_pdev_to_addr_range(to_pci_dev(dev), start, end);
+			put_device(dev);
+		}
+	}
+}
+
+static void sel_stream_block_setup(struct pci_dev *pdev, struct pci_ide *ide,
+				   u64 *rid_assoc1, u64 *rid_assoc2,
+				   u64 *addr_assoc1, u64 *addr_assoc2,
+				   u64 *addr_assoc3)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide_partner *setting = pci_ide_to_settings(rp, ide);
+	resource_size_t start = ULLONG_MAX, end = 0;
+
+	*rid_assoc1 = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, setting->rid_end);
+	*rid_assoc2 = PREP_PCI_IDE_SEL_RID_2(setting->rid_start, pci_ide_domain(pdev));
+
+	/* Only one address association register block */
+	setup_addr_range(pdev, &start, &end);
+
+	*addr_assoc1 = PREP_PCI_IDE_SEL_ADDR1(start, end);
+	*addr_assoc2 = FIELD_GET(SEL_ADDR_UPPER, end);
+	*addr_assoc3 = FIELD_GET(SEL_ADDR_UPPER, start);
+}
+
+#define STREAM_INFO_RP_DEVFN		GENMASK_ULL(7, 0)
+#define STREAM_INFO_TYPE		BIT_ULL(8)
+#define  STREAM_INFO_TYPE_LINK		0
+#define  STREAM_INFO_TYPE_SEL		1
+
+static int tdx_ide_stream_create(struct tdx_link *tlink, struct pci_ide *ide)
+{
+	u64 stream_info, stream_ctrl, rid_assoc1, rid_assoc2;
+	u64 addr_assoc1, addr_assoc2, addr_assoc3;
+	u64 stream_id, rp_ide_id;
+	unsigned int nr_pages = tdx_sysinfo->connect.ide_mt_page_count;
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	u64 r;
+
+	struct tdx_page_array *stream_mt __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages, true);
+	if (!stream_mt)
+		return -ENOMEM;
+
+	stream_info = FIELD_PREP(STREAM_INFO_RP_DEVFN, rp->devfn);
+	stream_info |= FIELD_PREP(STREAM_INFO_TYPE, STREAM_INFO_TYPE_SEL);
+
+	/*
+	 * For Selective IDE stream, below values must be 0:
+	 *   NPR_AGG/PR_AGG/CPL_AGG/CONF_REQ/ALGO/DEFAULT/STREAM_ID
+	 *
+	 * below values are configurable but now hardcode to 0:
+	 *   PCRC/TC
+	 */
+	stream_ctrl = FIELD_PREP(PCI_IDE_SEL_CTL_EN, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TX_AGGR_NPR, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TX_AGGR_PR, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TX_AGGR_CPL, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_PCRC_EN, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_ALG, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TC, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_ID, 0);
+
+	sel_stream_block_setup(pdev, ide, &rid_assoc1, &rid_assoc2,
+			       &addr_assoc1, &addr_assoc2, &addr_assoc3);
+
+	r = tdh_ide_stream_create(stream_info, tlink->spdm_id,
+				  stream_mt, stream_ctrl,
+				  rid_assoc1, rid_assoc2, addr_assoc1,
+				  addr_assoc2, addr_assoc3,
+				  &stream_id, &rp_ide_id);
+	if (r)
+		return -EFAULT;
+
+	tlink->stream_id = stream_id;
+	tlink->stream_mt = no_free_ptr(stream_mt);
+
+	pci_dbg(pdev, "%s stream id 0x%x rp ide_id 0x%llx\n", __func__,
+		tlink->stream_id, rp_ide_id);
+	return 0;
+}
+
+static void tdx_ide_stream_delete(struct tdx_link *tlink)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	unsigned int nr_released;
+	u64 released_hpa, r;
+
+	r = tdh_ide_stream_block(tlink->spdm_id, tlink->stream_id);
+	if (r) {
+		pci_err(pdev, "ide stream block fail %llx\n", r);
+		goto leak;
+	}
+
+	r = tdh_ide_stream_delete(tlink->spdm_id, tlink->stream_id,
+				  tlink->stream_mt, &nr_released,
+				  &released_hpa);
+	if (r) {
+		pci_err(pdev, "ide stream delete fail %llx\n", r);
+		goto leak;
+	}
+
+	if (tdx_page_array_ctrl_release(tlink->stream_mt, nr_released,
+					released_hpa)) {
+		pci_err(pdev, "fail to release IDE stream metadata pages\n");
+		goto leak;
+	}
+
+	goto out;
+
+leak:
+	tdx_page_array_ctrl_leak(tlink->stream_mt);
+out:
+	tlink->stream_mt = NULL;
+}
+
 static void tdx_ide_stream_teardown(struct tdx_link *tlink)
 {
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	struct pci_ide *ide = tlink->ide;
+
+	if (!ide)
+		return;
+
+	pci_ide_stream_disable(pdev, ide);
+	tsm_ide_stream_unregister(ide);
+	tdx_ide_stream_key_stop(tlink);
+	pci_ide_stream_teardown(pdev, ide);
+	pci_ide_stream_unregister(ide);
+	tdx_ide_stream_delete(tlink);
+	pci_ide_stream_free(tlink->ide);
+	tlink->ide = NULL;
 }
 
 static int tdx_ide_stream_setup(struct tdx_link *tlink)
 {
-	return -EOPNOTSUPP;
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	struct pci_ide *ide;
+	int ret;
+
+	ide = pci_ide_stream_alloc(pdev);
+	if (!ide)
+		return -ENOMEM;
+
+	/* Configure IDE capability for RP & get stream_id */
+	ret = tdx_ide_stream_create(tlink, ide);
+	if (ret)
+		goto stream_free;
+
+	ide->stream_id = tlink->stream_id;
+	ret = pci_ide_stream_register(ide);
+	if (ret)
+		goto tdx_stream_delete;
+
+	/* Configure IDE capability for target device */
+	pci_ide_stream_setup(pdev, ide);
+
+	/* Key Programming for RP & target device, enable IDE stream for RP */
+	ret = tdx_ide_stream_key_program(tlink);
+	if (ret)
+		goto stream_teardown;
+
+	ret = tsm_ide_stream_register(ide);
+	if (ret)
+		goto tdx_key_stop;
+
+	/* Enable IDE stream for target device */
+	pci_ide_stream_enable(pdev, ide);
+
+	tlink->ide = ide;
+
+	return 0;
+
+tdx_key_stop:
+	tdx_ide_stream_key_stop(tlink);
+stream_teardown:
+	pci_ide_stream_teardown(pdev, ide);
+	pci_ide_stream_unregister(ide);
+tdx_stream_delete:
+	tdx_ide_stream_delete(tlink);
+stream_free:
+	pci_ide_stream_free(tlink->ide);
+	tlink->ide = NULL;
+	return ret;
 }
 
 static void __tdx_link_disconnect(struct tdx_link *tlink)

---

## [29] Huang, Kai — 2025-09-22
*Subject: Re: [RFC PATCH 04/27] x86/virt/tdx: Move tdx_errno.h from KVM to
 public place*

On Fri, 2025-09-19 at 07:22 -0700, Dan Williams wrote:
> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

<asm/tdx.h> has below:

/*                                                                    
 * TDX module SEAMCALL leaf function error codes
 */
#define TDX_SUCCESS             0ULL                            
#define TDX_RND_NO_ENTROPY      0x8000020300000000ULL

Perhaps take this chance to move these two into <asm/tdx_errno.h> too?

Btw, Rick is trying to do similar thing in his dynamic PAMT series:

https://lore.kernel.org/kvm/20250918232224.2202592-2-rick.p.edgecombe@intel.com/

---

## [30] Samuel Ortiz — 2025-10-06
*Subject: Re: [RFC PATCH 09/27] ACPICA: Add KEYP table definitions*

Hi Dan, Dave,

On Fri, Sep 19, 2025 at 07:22:18AM -0700, Dan Williams wrote:
> From: Dave Jiang <dave.jiang@intel.com>
> 

Can you share more about how the TDX Module knows about where the KCU
register block is? Is the host VMM supposed to explicitly "donate" that
MMIO region to the TSM before TDH_IDE_STREAM_KM?

I'm asking that question to potentially align the RISC-V TEE-IO spec [1]
with a similar KEYP based implementation, as I think it is simpler.

Cheers,
Samuel.

[1] https://github.com/riscv-non-isa/riscv-ap-tee-io/blob/main/src/07-theory_operations.adoc#root-of-trust-spdm-session

---

## [31] Xu Yilun — 2025-10-10
*Subject: Re: [RFC PATCH 09/27] ACPICA: Add KEYP table definitions*

On Mon, Oct 06, 2025 at 04:41:46PM +0200, Samuel Ortiz wrote:
> Hi Dan, Dave,
> 

No, host VMM doesn't tell TSM about the KCU region. BIOS assigns the KCU
regions, it tells host where is the KCU by generating KEYP, it tells
TDX Module the same info by generating another info table.

Thanks,
Yilun

> 
> I'm asking that question to potentially align the RISC-V TEE-IO spec [1]

---

## [32] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 01/27] coco/tdx-host: Introduce a "tdx_host" device*

On Fri, 19 Sep 2025 07:22:10 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Chao Gao <chao.gao@intel.com>
> 

I'm only taking a look to see a second example of how the core
code is used as I care mostly about the ARM one.  Anyhow, a
few passing comments inline.

> diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
> new file mode 100644

There is general rework ongoing to stop including kernel.h except
where strictly necessary.  Please check exactly what you need and
see if one or more more specific headers is appropriate.

> +#include <linux/module.h>
> +#include <linux/mod_devicetable.h>

Bring headers in with the patch that first uses them. I'm not immediately
spotting anything from this one in this patch.  Doing that just makes
it easier to see if there are excess headers included at the end of
building up the driver across a series.

> +#include <linux/device/faux.h>
> +#include <asm/cpu_device_id.h>

What's the logic behind doing that here rather than in probe
for the faux device?  Perhaps add something to this comment.

> +	r = tdx_enable();
> +	if (r)

---

## [33] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 03/27] coco/tdx-host: Support Link TSM for TDX host*

On Fri, 19 Sep 2025 07:22:12 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

> diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
> index 49c205913ef6..41813ba352d0 100644

> +static struct pci_tsm_ops tdx_link_ops;
> +

Why is this needed?


> +static int tdx_connect_init(struct device *dev)
> +{

Might as well use
		return dev_err_probe(dev, PTR_ERR(link), "failed to register TSM\n");
as that will pretty print the error for you anyway and saves a few lines of code.

Thanks,

Jonathan

---

## [34] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 05/27] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Fri, 19 Sep 2025 07:22:14 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

One trivial thing + I think that introduction of a DEFINE_FREE() needs
to be more obvious to MM folk that it will be buried in here.

Looks fine but needs an Ack.

> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> index ada2fd4c2d54..bc5b8e288546 100644



> +static bool tdx_page_array_ctrl_match(struct tdx_page_array *array,
> +				      unsigned int offset,
return false

> +	}
> +

> diff --git a/include/linux/gfp.h b/include/linux/gfp.h
> index 5ebf26fcdcfa..f0a651155872 100644

This is at least more 'normal' than the CCA set one for free_page.
Burying it down here means getting an MM review. I'd be tempted to find
an alternative use somewhere else and post this stand alone to get that
review done.
 
> +
>  void page_alloc_init_cpuhp(void);

---

## [35] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 08/27] x86/virt/tdx: Add tdx_enable_ext() to enable
 of TDX Module Extensions*

On Fri, 19 Sep 2025 07:22:17 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

A few more trivial comments.

> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> index d47b2612c816..9d4cebace054 100644

> +
> +DEFINE_FREE(tdx_ext_mempool_free, struct tdx_page_array *, if (!IS_ERR_OR_NULL(_T)) tdx_ext_mempool_free(_T))
Very long line. Add a break somewhere!


> +/**
> + * tdx_enable_ext - Enable TDX module extensions.
guard() perhaps which would make early returns an option if nothing esle
gets added after the switch.

> +
> +	switch (tdx_module_status) {

---

## [36] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 11/27] acpi: Add KEYP Key Configuration Unit parsing*

On Fri, 19 Sep 2025 07:22:20 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Dave Jiang <dave.jiang@intel.com>
> 

Generally all this ACPI code looks fine (up to the TODOs Dan has called out)
One trivial thing below

> diff --git a/drivers/acpi/x86/keyp.c b/drivers/acpi/x86/keyp.c
> new file mode 100644

> +static bool keyp_info_match(struct acpi_keyp_rp_info *rp,
> +			    struct keyp_hb_info *hb)
If you are going to not use the simple pattern for matching that
would have this inverted so we only match if we pass all checks
might as well do
	return rp->bus >= hb->bus_start && rp->bus <= hb->bus_end;


> +
> +	return false;

---

## [37] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 15/27] x86/virt/tdx: Extend tdx_page_array to
 support IOMMU_MT*

On Fri, 19 Sep 2025 07:22:24 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

postponed

> another user appears.
> 


> diff --git a/include/linux/mm.h b/include/linux/mm.h
> index 1ae97a0b8ec7..719cc479f9e7 100644

Another case of buried mm stuff that maybe could go ahead of this series
so this doesn't stall on any controversy around that.

> +
>  /**

---

## [38] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 18/27] coco/tdx-host: Setup all trusted IOMMUs on
 TDX Connect init*

On Fri, 19 Sep 2025 07:22:27 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 
Trivial follows.

>  static int tdx_connect_init(struct device *dev)
>  {

Similar to earlier comment, might as well use return dev_err_probe()

> +		return ret;
> +	}

---

## [39] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 19/27] coco/tdx-host: Add a helper to exchange SPDM
 messages through DOE*

On Fri, 19 Sep 2025 07:22:28 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Zhenzhong Duan <zhenzhong.duan@intel.com>
> 

LGTM and finally a bit I know enough about for a tag to make sense :)
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [40] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

On Fri, 19 Sep 2025 07:22:29 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 
Feels like use of __free() in here is inappropriate to me.

> ---
>  drivers/virt/coco/tdx-host/tdx-host.c | 49 ++++++++++++++++++++++++++-

> +
> +static void __tdx_link_disconnect(struct tdx_link *tlink)
I'm not a fan on an ownership pass like this just for purposes of cleaning up.

I'd be a bit happier if you could make it
	struct tdx_link *tlink __free(__tdx_link_disconnect) = to_tdx_link(pdev->dsm);

but I still don't really like it.  I think I'd just not use __free and stick
to traditional cleanup in via a goto. 

> +	ret = tdx_spdm_session_setup(tlink);
> +	if (ret) {

If this fails we still call tdx_ide_stream_teardown().  Why does that make sense
given I'd expect this to have no side effects on failure?  Definitely needs
a comment. I also definitely don't think __free is appropriate here as it
is hiding this detail somewhat

> +		return ret;
> +	}

---

## [41] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 21/27] x86/virt/tdx: Add SEAMCALL wrappers for SPDM
 management*

On Fri, 19 Sep 2025 07:22:30 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Zhenzhong Duan <zhenzhong.duan@intel.com>
> 

> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> index 0f34009411fb..86dd855d7361 100644

This is confusing me. I'd be inclined to set hat.pfn with appropriate masks
shifts etc.  Or just do it with field masks and FIELD_PREP() etc


> +		hat.array_size = array->nents - 1;
> +	} else {

---

## [42] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 22/27] coco/tdx-host: Implement SPDM session setup*

On Fri, 19 Sep 2025 07:22:31 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Zhenzhong Duan <zhenzhong.duan@intel.com>
> 
Various minor things inline.

Thanks,

Jonathan
> ---
>  arch/x86/include/asm/tdx_errno.h      |   2 +

> +
> +static void tdx_spdm_delete(struct tdx_link *tlink)
I'd do a separate error handling block so
	}
	link->spdm_mt = NULL;
	return;

leak:
	tdx_page_array_ctrl_leak(tlink->spdm_mt);
	tlink->spdm_mt = NULL;
	
> +}

>  
> +DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_link *, if (_T) tdx_spdm_session_teardown(_T))

Similar comment as before.  To me using __free without a constructor is rather non intuitive.

> +	ret = tdx_spdm_create(tlink);
> +	if (ret)

If you drop the __free on above, factor out from here as a separate
helper and you can just do an if (ret) teardown after that call.

> +	struct tdx_page_array *dev_info __free(tdx_page_array_free) =
> +		tdx_page_array_create(nr_pages, true);
Given the only use in here that I can immediately spot is on the
stack with nothing in reserved (so zero size) + you then memcpy that into
another buffer, why bother having reserved in this declaration?
> +} __packed;
> +
Trivial but I'd prefer to see these freed in reverse order of allocation
of where they are set. Just makes reviewing a tiny bit easier as the code
evolves.

>  	pci_tsm_pf0_destructor(&tlink->pci);
>  	kfree(tlink);

---

## [43] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 26/27] x86/virt/tdx: Add SEAMCALL wrappers for IDE
 stream management*

On Fri, 19 Sep 2025 07:22:35 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> index 86dd855d7361..179c976eab01 100644

> +
> +u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id)

	return seamcall()

---

## [44] Jonathan Cameron — 2025-10-30
*Subject: Re: [RFC PATCH 27/27] coco/tdx-host: Implement IDE stream
 setup/teardown*

On Fri, 19 Sep 2025 07:22:36 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 
A few small things in here.

Jonathan

> ---
>  drivers/virt/coco/tdx-host/tdx-host.c | 271 +++++++++++++++++++++++++-


> +static void tdx_ide_stream_delete(struct tdx_link *tlink)
> +{

Similar to the other case below. I'd just duplicate this last line
in the interests of simpler code flow.

> +}
> +
Use ide local variable

> +	tlink->ide = NULL;
Can you do this earlier so it's reverse of ordering in the
setup function?
>  }
>  
(ide) I think because...
> +	tlink->ide = NULL;
How is this set in any path that gets here?  Looks
like it is only assigned right at the end after all error paths.

> +	return ret;
>  }

---

## [45] dan.j.williams@intel.com — 2025-11-03
*Subject: Re: [RFC PATCH 01/27] coco/tdx-host: Introduce a "tdx_host" device*

Jonathan Cameron wrote:
> On Fri, 19 Sep 2025 07:22:10 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Thanks for taking a look at a cross-arch RFC.

> 
> > diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c

Sure, easy enough to clean up.

> > +#include <linux/module.h>
> > +#include <linux/mod_devicetable.h>

For this specific case of tdx_enable() it will be obviated by the fact
that the new direction is to always enable TDX early [1].

[1]: http://lore.kernel.org/20251010220403.987927-1-seanjc@google.com

Otherwise there are cases where we might create the device without a
driver. E.g. sysfs ABI only for updates, vs also enabling PCI/TSM
services via a driver attached to this device.

---

## [46] dan.j.williams@intel.com — 2025-11-03
*Subject: Re: [RFC PATCH 03/27] coco/tdx-host: Support Link TSM for TDX host*

Jonathan Cameron wrote:
> On Fri, 19 Sep 2025 07:22:12 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

I think Yilun was staging some infrastructure early, will clean this and
other stuff up for the v1 posting.

> 
> 

Makes sense.

---

## [47] dan.j.williams@intel.com — 2025-11-03
*Subject: Re: [RFC PATCH 05/27] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

Jonathan Cameron wrote:
[..]
> > diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> > index ada2fd4c2d54..bc5b8e288546 100644
[..]
> > +	if (page_to_phys(array->root) != released_hpa) {
> > +		pr_err("%s released_hpa [0x%llx] doesn't match root page hpa [0x%llx]\n",

Good catch.

> > diff --git a/include/linux/gfp.h b/include/linux/gfp.h
> > index 5ebf26fcdcfa..f0a651155872 100644

Can break it out and front-load it in the series, but I am not expecting
controversy. The __free(kvfree) went upstream without MM comment for
example.

If you have a use case for it ahead of TDX Connect, go for it, but I am
otherwise in no rush.

---

## [48] dan.j.williams@intel.com — 2025-11-03
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

Jonathan Cameron wrote:
> On Fri, 19 Sep 2025 07:22:29 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Yeah this needs a rethink. The session and the stream are independent
resources. It can be a composite object that encapsulates both
resources, but not tlink directly.

...chalk this up to RFC expediency.

> I'd be a bit happier if you could make it
> 	struct tdx_link *tlink __free(__tdx_link_disconnect) = to_tdx_link(pdev->dsm);

I would not go that far, but certainly I can see that being preferable
than reusing the existing base 'struct tdx_link *' as the cleanup
variable.

---

## [49] dan.j.williams@intel.com — 2025-11-03
*Subject: Re: [RFC PATCH 21/27] x86/virt/tdx: Add SEAMCALL wrappers for SPDM
 management*

Jonathan Cameron wrote:
> On Fri, 19 Sep 2025 07:22:30 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Yeah, its a hardware-ish ABI should use bitfield.h macros not C
bitfields.

---

## [50] dan.j.williams@intel.com — 2025-11-03
*Subject: Re: [RFC PATCH 27/27] coco/tdx-host: Implement IDE stream
 setup/teardown*

Jonathan Cameron wrote:
> On Fri, 19 Sep 2025 07:22:36 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:
[..]

Ack to the comments here and previous ones.

> How is this set in any path that gets here?  Looks
> like it is only assigned right at the end after all error paths.

I think some of this gets cleaned up naturally by switching to an
__free(pci_ide_stream_release) scheme similar to the sample
devsec_link_tsm_connect() implementation.

...but yes revisting this function's organization was on my list of
things to do before v1.

---

## [51] Xu Yilun — 2025-11-05
*Subject: Re: [RFC PATCH 08/27] x86/virt/tdx: Add tdx_enable_ext() to enable
 of TDX Module Extensions*

On Thu, Oct 30, 2025 at 10:55:51AM +0000, Jonathan Cameron wrote:
> On Fri, 19 Sep 2025 07:22:17 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

Yes, will wrap.

> 
> 

Will do. New version will be based on Sean's VMXON changes [1] so has
some differences, but guard() is still a good idea.

[1] https://lore.kernel.org/linux-coco/20251010220403.987927-4-seanjc@google.com/

Thanks,
Yilun

---

## [52] Xu Yilun — 2025-11-05
*Subject: Re: [RFC PATCH 11/27] acpi: Add KEYP Key Configuration Unit parsing*

On Thu, Oct 30, 2025 at 11:02:51AM +0000, Jonathan Cameron wrote:
> On Fri, 19 Sep 2025 07:22:20 -0700
> Dan Williams <dan.j.williams@intel.com> wrote:

OK, let's use the pattern for all:

	return rp->segment == hb->segment && rp->bus >= hb->bus_start &&
	       rp->bus <= hb->bus_end;

> 
>

---

## [53] Xu Yilun — 2025-11-06
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

On Mon, Nov 03, 2025 at 03:34:15PM -0800, dan.j.williams@intel.com wrote:
> Jonathan Cameron wrote:
> > On Fri, 19 Sep 2025 07:22:29 -0700

The latest implementation internally is as follows. tlink_spdm &
tlink_ide represent independent resources though they point to the same
instance. I'm already comfortable about this code:

static int tdx_link_connect(struct pci_dev *pdev)
{
	struct tdx_link *tlink = to_tdx_link(pdev->tsm);

	struct tdx_link *tlink_spdm __free(tdx_spdm_session_teardown) =
		tdx_spdm_session_setup(tlink);
	if (IS_ERR(tlink_spdm)) {
		pci_err(pdev, "fail to setup spdm session\n");
		return PTR_ERR(tlink_spdm);
	}

	struct tdx_link *tlink_ide __free(tdx_ide_stream_teardown) =
		tdx_ide_stream_setup(tlink);
	if (IS_ERR(tlink_ide)) {
		pci_err(pdev, "fail to setup ide stream\n");
		return PTR_ERR(tlink_ide);
	}

	retain_and_null_ptr(tlink_spdm);
	retain_and_null_ptr(tlink_ide);

	return 0;
}

---

## [54] Xu Yilun — 2025-11-06
*Subject: Re: [RFC PATCH 22/27] coco/tdx-host: Implement SPDM session setup*

> > +struct spdm_config_info_t {
> > +	u32 vmm_spdm_cap;

I'll delete the reserved.

> > +} __packed;
> > +

Will do.

> 
> >  	pci_tsm_pf0_destructor(&tlink->pci);

---

## [55] Jonathan Cameron — 2025-11-10
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

On Thu, 6 Nov 2025 13:18:41 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> On Mon, Nov 03, 2025 at 03:34:15PM -0800, dan.j.williams@intel.com wrote:
> > Jonathan Cameron wrote:  
Nice. That looks good to me.

J

---

## [56] dan.j.williams@intel.com — 2025-11-10
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

Xu Yilun wrote:
> On Mon, Nov 03, 2025 at 03:34:15PM -0800, dan.j.williams@intel.com wrote:
> > Jonathan Cameron wrote:

The question I have is why does tdx_spdm_session_setup() return a
'struct tdx_link' instance and not a new 'struct tdx_spdm' object to
represent the new resources that were acquired? 'struct tdx_link' is
base infrastructure created by ->probe(). Perhaps 'struct tdx_spdm'
could be:

struct tdx_spdm {
       u64 spdm_id;
       struct page *spdm_conf;
       struct tdx_page_array *spdm_mt;
}

...and then tdx_link becomes:

struct tdx_link {
	...
	struct tdx_spdm spdm;
};

...and you can do:

       struct tdx_spdm *spdm __free(tdx_spdm_session_teardown) =
               tdx_spdm_session_setup(tlink);

tlink->spdm = *no_free_ptr(spdm);

...to assign it back to the preallocated space in @tlink, or make
it dynamically allocated.

struct tdx_link {
	...
	struct tdx_spdm *spdm;
};

tlink->spdm = no_free_ptr(spdm);

> 	if (IS_ERR(tlink_spdm)) {
> 		pci_err(pdev, "fail to setup spdm session\n");

No strict need for scope-based cleanup if this is the last resource
acquisition, but maybe there are other PCI/TSM core things to do that
are not shown.

---

## [57] Xu Yilun — 2025-11-13
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

On Mon, Nov 10, 2025 at 04:51:21PM -0800, dan.j.williams@intel.com wrote:
> Xu Yilun wrote:
> > On Mon, Nov 03, 2025 at 03:34:15PM -0800, dan.j.williams@intel.com wrote:

It works for sure. I have also thought about this solution, but dropped.
I don't wanna see the usage of auto-cleanup impose too much influences
to the code/structure design, even if it shows better modularity.

It is normal in kernel that a base structure contains several
sub-features and we just group them with blank lines. Some fields may be
used accoss 1-2 features and doesn't have a clear owner. If we ask for
strict structure/flow design for auto-cleanup, people may reluctant to
switch to auto-cleanup, thought is it over-engineering?

IOW, I like this current piece of code cause it is in perfect balance.
I don't have to change the mindset much for code design. I get the benifit
of auto-cleanup, and the local cleanup handlers (tlink_spdm, tlink_ide)
are cheap but clearly tell me what will happen if any step fails.

> 
> > 	if (IS_ERR(tlink_spdm)) {

So if we don't do auto-cleanup for the last one, do we still need a
structure for that? If not,

 struct tdx_link {
	struct tdx_spdm *spdm;
	
	int ide_stream_field1;
	int ide_stream_field2;
	...
 }

seems so wierd.

> but maybe there are other PCI/TSM core things to do that
> are not shown.

There is no following items for now but I think cleanup for the last one
is good. Otherwise we may face with the same problem as goto, that we
see unrelated changes (add cleanup for previous one) when we add a new
step.

Thanks,
Yilun

---

## [58] dan.j.williams@intel.com — 2025-11-14
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

Xu Yilun wrote:
[..]
> IOW, I like this current piece of code cause it is in perfect balance.
> I don't have to change the mindset much for code design. I get the benifit

I think in this case of conflicting minor preferences the tie goes to
the submitter. While I personally think the discipline of clearly
delineating objects and ownerships yields maintainability benefits, I
also do not hate the model of "extend existing object with scope based
setup".

So,

Acked-by: Dan Williams <dan.j.williams@intel.com>

> > > 	if (IS_ERR(tlink_spdm)) {
> > > 		pci_err(pdev, "fail to setup spdm session\n");

Yeah, a little clunky.

> > but maybe there are other PCI/TSM core things to do that
> > are not shown.

Again, this is a case of I still disagree with shipping the dead code,
but not enough to NAK your preference.

---

## [59] Xu Yilun — 2025-11-17
*Subject: Re: [RFC PATCH 20/27] coco/tdx-host: Add connect()/disconnect()
 handlers prototype*

On Fri, Nov 14, 2025 at 12:19:09PM -0800, dan.j.williams@intel.com wrote:
> Xu Yilun wrote:
> [..]

OK. Will delete the last scope-based cleanup

> but not enough to NAK your preference.

---
