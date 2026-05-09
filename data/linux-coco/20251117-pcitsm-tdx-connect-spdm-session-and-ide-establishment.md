---
title: 'PCI/TSM: TDX Connect: SPDM Session and IDE Establishment'
date: 2025-11-17
last_reply: 2026-02-17
message_count: 74
participants: ['Xu Yilun', 'Dave Hansen', 'dan.j.williams@intel.com', 'Jonathan Cameron', 'Tony Lindgren']
---

## [1] Xu Yilun — 2025-11-17

This is a new version of the RFC [1]. It is based on Dan's
"Link" TSM Core infrastructure [2][3] + Sean's VMXON RFC [4]. All
together they enable the SPDM Session and IDE Establishment for TDX
Connect. This series and its base commits are available in Dan's
tsm.git#staging [5].

Changes since public RFC:
- No tdx_enable() needed in tdx-host
- Simplify tdx_page_array kAPI, no singleton mode input
- Refactor the handling of TDX_INTERRUPTED_RESUMABLE
- Refine the usage of scope-based cleanup in tdx-host
- Set nr_stream_id in tdx-host, not in PCI ACPI initialization
- Use KEYP table + ECAP bit50 to decide Domain ID reservation
- Refactor IDE Address Association Register setup
- Remove prototype patches
- Refactor tdx_enable_ext() locking because of Sean's change
- Pick ACPICA KEYP patch from ACPICA repo
- Select TDX Connect feature for TDH.SYS.CONFIG, remove temporary
  solution for TDH.SYS.INIT
- Use Rick's tdx_errno.h movement patch [6]
- Factor out scope-based cleanup patches in mm
- Remove redunant header files, add header files only when first used
- Use dev_err_probe() when possible
- keyp_info_match() refactor
- Use bitfield.h macros for PAGE_LIST_INFO & HPA_ARRAY_T raw value
- Remove reserved fields for spdm_config_info_t
- Simplify return for tdh_ide_stream_block()
- Other small fixes for Jonathan's comments

[1]: https://lore.kernel.org/linux-coco/20250919142237.418648-1-dan.j.williams@intel.com/
[2]: https://lore.kernel.org/linux-coco/20251031212902.2256310-1-dan.j.williams@intel.com/
[3]: https://lore.kernel.org/linux-coco/20251105040055.2832866-1-dan.j.williams@intel.com/
[4]: https://lore.kernel.org/all/20251010220403.987927-1-seanjc@google.com/
[5]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging
[6]: https://lore.kernel.org/all/20250918232224.2202592-2-rick.p.edgecombe@intel.com/


Trimmed Original Cover letter:
-------------------------------

Add a PCI/TSM low-level driver implemenation for TDX Connect (the TEE
I/O architecture for Intel platforms). Recall that PCI/TSM is the
Linux PCI core subsystem for interfacing with platform Trusted Execution
Environment (TEE) Security Managers (TSMs). TSMs establish secure
sessions with PCIe devices (SPDM over Data Object Exchange (DOE)
mailboxes) and establish PCIe link Integrity and Data Encryption (IDE).

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


Chao Gao (1):
  coco/tdx-host: Introduce a "tdx_host" device

Dave Jiang (2):
  ACPICA: Add KEYP table definition
  acpi: Add KEYP support to fw_table parsing

Kirill A. Shutemov (1):
  x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>

Lu Baolu (2):
  iommu/vt-d: Cache max domain ID to avoid redundant calculation
  iommu/vt-d: Reserve the MSB domain ID bit for the TDX module

Xu Yilun (15):
  x86/virt/tdx: Move bit definitions of TDX_FEATURES0 to public header
  coco/tdx-host: Support Link TSM for TDX host
  mm: Add __free() support for __free_page()
  x86/virt/tdx: Add tdx_page_array helpers for new TDX Module objects
  x86/virt/tdx: Read TDX global metadata for TDX Module Extensions
  x86/virt/tdx: Read TDX Connect global metadata for TDX Connect
  mm: Add __free() support for folio_put()
  x86/virt/tdx: Extend tdx_page_array to support IOMMU_MT
  x86/virt/tdx: Add a helper to loop on TDX_INTERRUPTED_RESUMABLE
  iommu/vt-d: Export a helper to do function for each dmar_drhd_unit
  coco/tdx-host: Setup all trusted IOMMUs on TDX Connect init
  coco/tdx-host: Parse ACPI KEYP table to init IDE for PCI host bridges
  x86/virt/tdx: Add SEAMCALL wrappers for IDE stream management
  coco/tdx-host: Implement IDE stream setup/teardown
  coco/tdx-host: Finally enable SPDM session and IDE Establishment

Zhenzhong Duan (5):
  x86/virt/tdx: Add tdx_enable_ext() to enable of TDX Module Extensions
  x86/virt/tdx: Add SEAMCALL wrappers for trusted IOMMU setup and clear
  coco/tdx-host: Add a helper to exchange SPDM messages through DOE
  x86/virt/tdx: Add SEAMCALL wrappers for SPDM management
  coco/tdx-host: Implement SPDM session setup

 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/tdx-host/Kconfig            |  17 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 arch/x86/include/asm/shared/tdx.h             |   1 +
 .../vmx => include/asm/shared}/tdx_errno.h    |  29 +-
 arch/x86/include/asm/tdx.h                    |  76 +-
 arch/x86/include/asm/tdx_global_metadata.h    |  14 +
 arch/x86/kvm/vmx/tdx.h                        |   1 -
 arch/x86/virt/vmx/tdx/tdx.h                   |  16 +-
 drivers/iommu/intel/iommu.h                   |   2 +
 include/acpi/actbl2.h                         |  59 ++
 include/linux/acpi.h                          |   3 +
 include/linux/dmar.h                          |   2 +
 include/linux/fw_table.h                      |   1 +
 include/linux/gfp.h                           |   1 +
 include/linux/mm.h                            |   2 +
 include/linux/pci-ide.h                       |   2 +
 arch/x86/virt/vmx/tdx/tdx.c                   | 740 ++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  32 +
 drivers/acpi/tables.c                         |  12 +-
 drivers/iommu/intel/dmar.c                    |  67 ++
 drivers/iommu/intel/iommu.c                   |  10 +-
 drivers/pci/ide.c                             |   5 +-
 drivers/virt/coco/tdx-host/tdx-host.c         | 969 ++++++++++++++++++
 lib/fw_table.c                                |   9 +
 26 files changed, 2027 insertions(+), 47 deletions(-)
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (62%)
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

---

## [2] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 01/26] coco/tdx-host: Introduce a "tdx_host" device*

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

[ Yilun: Remove unnecessary head files ]
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/Kconfig             |  2 ++
 drivers/virt/coco/tdx-host/Kconfig    | 10 +++++++
 drivers/virt/coco/Makefile            |  1 +
 drivers/virt/coco/tdx-host/Makefile   |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 41 +++++++++++++++++++++++++++
 5 files changed, 55 insertions(+)
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
diff --git a/drivers/virt/coco/tdx-host/Makefile b/drivers/virt/coco/tdx-host/Makefile
new file mode 100644
index 000000000000..e61e749a8dff
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Makefile
@@ -0,0 +1 @@
+obj-$(CONFIG_TDX_HOST_SERVICES) += tdx-host.o
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
new file mode 100644
index 000000000000..ced1c980dc6f
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -0,0 +1,41 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * TDX host user interface driver
+ *
+ * Copyright (C) 2025 Intel Corporation
+ */
+
+#include <linux/module.h>
+#include <linux/mod_devicetable.h>
+#include <linux/device/faux.h>
+#include <asm/cpu_device_id.h>
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
+	if (!x86_match_cpu(tdx_host_ids))
+		return -ENODEV;
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

---

## [3] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 02/26] x86/virt/tdx: Move bit definitions of TDX_FEATURES0 to public header*

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
index a149740b24e8..b6961e137450 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -146,6 +146,10 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 #define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
 #define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
 const char *tdx_dump_mce_info(struct mce *m);
+
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index dde219c823b4..4370d3d177f6 100644
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

## [4] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 03/26] coco/tdx-host: Support Link TSM for TDX host*

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
 drivers/virt/coco/tdx-host/Kconfig    |   6 +
 arch/x86/include/asm/tdx.h            |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 154 +++++++++++++++++++++++++-
 3 files changed, 160 insertions(+), 1 deletion(-)

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
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index b6961e137450..ff77900f067b 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -148,6 +148,7 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 const char *tdx_dump_mce_info(struct mce *m);
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TDXCONNECT	BIT_ULL(6)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void);
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index ced1c980dc6f..6f21bb2dbeb9 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -7,8 +7,13 @@
 
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
+#include <linux/tsm.h>
 #include <linux/device/faux.h>
 #include <asm/cpu_device_id.h>
+#include <asm/tdx.h>
+#include <asm/tdx_global_metadata.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
 	X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),
@@ -16,6 +21,153 @@ static const struct x86_cpu_id tdx_host_ids[] = {
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
+	rc = pci_tsm_pf0_constructor(pdev, &tlink->pci, tsm_dev);
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
+	rc = pci_tsm_link_constructor(pdev, pci_tsm, tsm_dev);
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
+static void unregister_link_tsm(void *link)
+{
+	tsm_unregister(link);
+}
+
+static int __maybe_unused tdx_connect_init(struct device *dev)
+{
+	struct tsm_dev *link;
+
+	if (!IS_ENABLED(CONFIG_TDX_CONNECT))
+		return 0;
+
+	/*
+	 * With this errata, TDX should use movdir64b to clear private pages
+	 * when reclaiming them. See tdx_clear_page().
+	 *
+	 * Don't expect this errata on any TDX Connect supported platform. TDX
+	 * Connect will never call tdx_clear_page().
+	 */
+	if (boot_cpu_has_bug(X86_BUG_TDX_PW_MCE))
+		return -ENXIO;
+
+	tdx_sysinfo = tdx_get_sysinfo();
+	if (!tdx_sysinfo)
+		return -ENXIO;
+
+	if (!(tdx_sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT))
+		return 0;
+
+	link = tsm_register(dev, &tdx_link_ops);
+	if (IS_ERR(link))
+		return dev_err_probe(dev, PTR_ERR(link),
+				     "failed to register TSM\n");
+
+	return devm_add_action_or_reset(dev, unregister_link_tsm, link);
+}
+
+static int tdx_host_probe(struct faux_device *fdev)
+{
+	/*
+	 * Only support TDX Connect now. More TDX features could be added here.
+	 *
+	 * TODO: do tdx_connect_init() when it is fully implemented.
+	 */
+	return 0;
+}
+
+static struct faux_device_ops tdx_host_ops = {
+	.probe = tdx_host_probe,
+};
+
 static struct faux_device *fdev;
 
 static int __init tdx_host_init(void)
@@ -23,7 +175,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids))
 		return -ENODEV;
 
-	fdev = faux_device_create(KBUILD_MODNAME, NULL, NULL);
+	fdev = faux_device_create(KBUILD_MODNAME, NULL, &tdx_host_ops);
 	if (!fdev)
 		return -ENODEV;

---

## [5] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 04/26] x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Today there are two separate locations where TDX error codes are defined:
         arch/x86/include/asm/tdx.h
         arch/x86/kvm/vmx/tdx.h

They have some overlap that is already defined similarly. Reduce the
duplication and prepare to introduce some helpers for these error codes in
the central place by unifying them. Join them at:
        asm/shared/tdx_errno.h
...and update the headers that contained the duplicated definitions to
include the new unified header.

Opportunistically massage some comments. Also, adjust
_BITUL()->_BITULL() to address 32 bit build errors after the move.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/shared/tdx.h             |  1 +
 .../vmx => include/asm/shared}/tdx_errno.h    | 27 ++++++++++++++-----
 arch/x86/include/asm/tdx.h                    | 20 --------------
 arch/x86/kvm/vmx/tdx.h                        |  1 -
 4 files changed, 22 insertions(+), 27 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (66%)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 8bc074c8d7c6..6a1646fc2b2f 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -4,6 +4,7 @@
 
 #include <linux/bits.h>
 #include <linux/types.h>
+#include <asm/shared/tdx_errno.h>
 
 #define TDX_HYPERCALL_STANDARD  0
 
diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
similarity index 66%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/shared/tdx_errno.h
index 6ff4672c4181..f98924fe5198 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -1,14 +1,14 @@
 /* SPDX-License-Identifier: GPL-2.0 */
-/* architectural status code for SEAMCALL */
-
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
+#ifndef _X86_SHARED_TDX_ERRNO_H
+#define _X86_SHARED_TDX_ERRNO_H
 
+/* Upper 32 bit of the TDX error code encodes the status */
 #define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
 
 /*
- * TDX SEAMCALL Status Codes (returned in RAX)
+ * TDX SEAMCALL Status Codes
  */
+#define TDX_SUCCESS				0ULL
 #define TDX_NON_RECOVERABLE_VCPU		0x4000000100000000ULL
 #define TDX_NON_RECOVERABLE_TD			0x4000000200000000ULL
 #define TDX_NON_RECOVERABLE_TD_NON_ACCESSIBLE	0x6000000500000000ULL
@@ -17,6 +17,7 @@
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
+#define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
@@ -28,6 +29,20 @@
 #define TDX_EPT_ENTRY_STATE_INCORRECT		0xC0000B0D00000000ULL
 #define TDX_METADATA_FIELD_NOT_READABLE		0xC0000C0200000000ULL
 
+/*
+ * SW-defined error codes.
+ *
+ * Bits 47:40 == 0xFF indicate Reserved status code class that never used by
+ * TDX module.
+ */
+#define TDX_ERROR			_BITULL(63)
+#define TDX_NON_RECOVERABLE		_BITULL(62)
+#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
+#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _ULL(0xFFFF0000))
+
+#define TDX_SEAMCALL_GP			(TDX_SW_ERROR | X86_TRAP_GP)
+#define TDX_SEAMCALL_UD			(TDX_SW_ERROR | X86_TRAP_UD)
+
 /*
  * TDX module operand ID, appears in 31:0 part of error code as
  * detail information
@@ -37,4 +52,4 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#endif /* _X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index ff77900f067b..ad27b746522f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -12,26 +12,6 @@
 #include <asm/trapnr.h>
 #include <asm/shared/tdx.h>
 
-/*
- * SW-defined error codes.
- *
- * Bits 47:40 == 0xFF indicate Reserved status code class that never used by
- * TDX module.
- */
-#define TDX_ERROR			_BITUL(63)
-#define TDX_NON_RECOVERABLE		_BITUL(62)
-#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
-#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _UL(0xFFFF0000))
-
-#define TDX_SEAMCALL_GP			(TDX_SW_ERROR | X86_TRAP_GP)
-#define TDX_SEAMCALL_UD			(TDX_SW_ERROR | X86_TRAP_UD)
-
-/*
- * TDX module SEAMCALL leaf function error codes
- */
-#define TDX_SUCCESS		0ULL
-#define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
-
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
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

## [6] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 05/26] mm: Add __free() support for __free_page()*

Allow for the declaration of struct page * variables that trigger
__free_page() when they go out of scope.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/gfp.h | 1 +
 1 file changed, 1 insertion(+)

diff --git a/include/linux/gfp.h b/include/linux/gfp.h
index 0ceb4e09306c..dc61fa63a3b9 100644
--- a/include/linux/gfp.h
+++ b/include/linux/gfp.h
@@ -383,6 +383,7 @@ extern void free_pages_nolock(struct page *page, unsigned int order);
 extern void free_pages(unsigned long addr, unsigned int order);
 
 #define __free_page(page) __free_pages((page), 0)
+DEFINE_FREE(__free_page, struct page *, if (_T) __free_page(_T))
 #define free_page(addr) free_pages((addr), 0)
 
 void page_alloc_init_cpuhp(void);

---

## [7] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for new TDX Module objects*

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
 - As SEAMCALL inputs. They are just temporary buffers for exchanging
   data blobs in one SEAMCALL. TDX Module will not hold them as control
   pages.

The 2 structures both need a 'root page' which contains a list of HPAs.
They collapse the HPA of the root page and the number of valid HPAs
into a 64 bit raw value for SEAMCALL parameters. The root page is
always a medium for passing data pages, TDX Module never keeps the root
page.

A main difference is HPA_ARRAY_T requires singleton mode when
containing just 1 functional page (page0). In this mode the root page is
not needed and the HPA field of the raw value directly points to the
page0. But in this patch, root page is always allocated for user
friendly kAPIs.

Another small difference is HPA_LIST_INFO contains a 'first entry' field
which could be filled by TDX Module. This simplifies host by providing
the same structure when re-invoke the interrupted SEAMCALL. No need for
host to touch this field.

Typical usages of the tdx_page_array:

1. Add control pages:
 - struct tdx_page_array *array = tdx_page_array_create(nr_pages);
 - seamcall(TDH_XXX_CREATE, array, ...);

2. Release control pages:
 - seamcall(TDX_XXX_DELETE, array, &nr_released, &released_hpa);
 - tdx_page_array_ctrl_release(array, nr_released, released_hpa);

3. Exchange data blobs:
 - struct tdx_page_array *array = tdx_page_array_create(nr_pages);
 - seamcall(TDX_XXX, array, ...);
 - Read data from array.
 - tdx_page_array_free(array);

4. Note the root page contains 512 HPAs at most, if more pages are
   required, refilling the tdx_page_array is needed.

 - struct tdx_page_array *array = tdx_page_array_alloc(nr_pages);
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
 arch/x86/include/asm/tdx.h  |  17 +++
 arch/x86/virt/vmx/tdx/tdx.c | 252 ++++++++++++++++++++++++++++++++++++
 2 files changed, 269 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index ad27b746522f..3a3ea3fa04f2 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -139,6 +139,23 @@ void tdx_guest_keyid_free(unsigned int keyid);
 
 void tdx_quirk_reset_page(struct page *page);
 
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
+struct tdx_page_array *tdx_page_array_create(unsigned int nr_pages);
+void tdx_page_array_ctrl_leak(struct tdx_page_array *array);
+int tdx_page_array_ctrl_release(struct tdx_page_array *array,
+				unsigned int nr_released,
+				u64 released_hpa);
+
 struct tdx_td {
 	/* TD root structure: */
 	struct page *tdr_page;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 09c766e60962..9a5c32dc1767 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -30,6 +30,7 @@
 #include <linux/suspend.h>
 #include <linux/syscore_ops.h>
 #include <linux/idr.h>
+#include <linux/bitfield.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -296,6 +297,257 @@ static __init int build_tdx_memlist(struct list_head *tmb_list)
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
+	__free_page(array->root);
+	tdx_free_pages_bulk(array->nr_pages, array->pages);
+	kfree(array->pages);
+	kfree(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_free);
+
+static struct tdx_page_array *tdx_page_array_alloc(unsigned int nr_pages)
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
+	struct page *root __free(__free_page) = alloc_page(GFP_KERNEL |
+							   __GFP_ZERO);
+	if (!root)
+		return NULL;
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
+struct tdx_page_array *tdx_page_array_create(unsigned int nr_pages)
+{
+	int filled;
+
+	if (nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
+		return NULL;
+
+	struct tdx_page_array *array __free(tdx_page_array_free) =
+		tdx_page_array_alloc(nr_pages);
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
+	__free_page(array->root);
+	kfree(array->pages);
+	kfree(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_leak);
+
+static bool tdx_page_array_validate_release(struct tdx_page_array *array,
+					    unsigned int offset,
+					    unsigned int nr_released,
+					    u64 released_hpa)
+{
+	unsigned int nents;
+	u64 *entries;
+	int i;
+
+	if (offset >= array->nr_pages)
+		return false;
+
+	nents = umin(array->nr_pages - offset, TDX_PAGE_ARRAY_MAX_NENTS);
+
+	if (nents != nr_released) {
+		pr_err("%s nr_released [%d] doesn't match page array nents [%d]\n",
+		       __func__, nr_released, nents);
+		return false;
+	}
+
+	/*
+	 * Unfortunately TDX has multiple page allocation protocols, check the
+	 * "singleton" case required for HPA_ARRAY_T.
+	 */
+	if (page_to_phys(array->pages[0]) == released_hpa &&
+	    array->nr_pages == 1)
+		return true;
+
+	/* Then check the "non-singleton" case */
+	if (page_to_phys(array->root) == released_hpa) {
+		entries = (u64 *)page_address(array->root);
+		for (i = 0; i < nents; i++) {
+			struct page *page = array->pages[offset + i];
+			u64 val = page_to_phys(page);
+
+			if (val != entries[i]) {
+				pr_err("%s entry[%d] [0x%llx] doesn't match page hpa [0x%llx]\n",
+				       __func__, i, entries[i], val);
+				return false;
+			}
+		}
+
+		return true;
+	}
+
+	pr_err("%s failed to validate, released_hpa [0x%llx], root page hpa [0x%llx], page0 hpa [%#llx], number pages %u\n",
+	       __func__, released_hpa, page_to_phys(array->root),
+	       page_to_phys(array->pages[0]), array->nr_pages);
+
+	return false;
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
+	/*
+	 * The only case where ->nr_pages is allowed to be >
+	 * TDX_PAGE_ARRAY_MAX_NENTS is a case where those pages are never
+	 * expected to be released by this function.
+	 */
+	if (WARN_ON(array->nr_pages > TDX_PAGE_ARRAY_MAX_NENTS))
+		return -EINVAL;
+
+	if (WARN_ONCE(!tdx_page_array_validate_release(array, 0, nr_released,
+						       released_hpa),
+		      "page release protocol error, TDX Module needs replacement.\n"))
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
+#define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
+#define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
+#define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
+
+static u64 __maybe_unused hpa_list_info_assign_raw(struct tdx_page_array *array)
+{
+	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
+	       FIELD_PREP(HPA_LIST_INFO_PFN, page_to_pfn(array->root)) |
+	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, array->nents - 1);
+}
+
+#define HPA_ARRAY_T_PFN		GENMASK_U64(51, 12)
+#define HPA_ARRAY_T_SIZE	GENMASK_U64(63, 55)
+
+static u64 __maybe_unused hpa_array_t_assign_raw(struct tdx_page_array *array)
+{
+	struct page *page;
+
+	if (array->nents == 1)
+		page = array->pages[0];
+	else
+		page = array->root;
+
+	return FIELD_PREP(HPA_ARRAY_T_PFN, page_to_pfn(page)) |
+	       FIELD_PREP(HPA_ARRAY_T_SIZE, array->nents - 1);
+}
+
+static u64 __maybe_unused hpa_array_t_release_raw(struct tdx_page_array *array)
+{
+	if (array->nents == 1)
+		return 0;
+
+	return page_to_phys(array->root);
+}
+
 static __init int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};

---

## [8] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 07/26] x86/virt/tdx: Read TDX global metadata for TDX Module Extensions*

Add the global metadata for TDX core to enable extensions. They are:

 - "memory_pool_required_pages"
   Specify the required number of memory pool pages for the present
   extensions.

 - "ext_required"
   Specify if TDX.EXT.INIT is required.

Note for these 2 fields, a value of 0 doesn't mean extensions are not
supported.  It means no need to call TDX.EXT.MEM.ADD or TDX.EXT.INIT.

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
index 360963bc9328..c3b2e2748b3e 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -85,6 +85,19 @@ static __init int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_
 	return ret;
 }
 
+static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
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
 static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -93,6 +106,7 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
+	ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
 
 	return ret;
 }

---

## [9] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of TDX Module Extensions*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Add a kAPI tdx_enable_ext() for kernel to enable TDX Module Extensions
after basic TDX Module initialization.

The extension initialization uses the new TDH.EXT.MEM.ADD and
TDX.EXT.INIT seamcalls. TDH.EXT.MEM.ADD add pages to a shared memory
pool for extensions to consume. The number of pages required is
published in the MEMORY_POOL_REQUIRED_PAGES field from TDH.SYS.RD. Then
on TDX.EXT.INIT, the extensions consume from the pool and initialize.

TDH.EXT.MEM.ADD is the first user of tdx_page_array. It provides pages
to TDX Module as control (private) pages. A tdx_clflush_page_array()
helper is introduced to flush shared cache before SEAMCALL, to avoid
shared cache write back damages these private pages.

TDH.EXT.MEM.ADD uses HPA_LIST_INFO as parameter so could leverage the
'first_entry' field to simplify the interrupted - retry flow. Host
don't have to care about partial page adding and 'first_entry'.

Use a new version TDH.SYS.CONFIG for VMM to tell TDX Module which
optional features (e.g. TDX Connect, and selecting TDX Connect implies
selecting TDX Module Extensions) to use and let TDX Module update its
global metadata (e.g. memory_pool_required_pages for TDX Module
Extensions). So after calling this new version TDH.SYS.CONFIG, VMM
updates the cached tdx_sysinfo.

Note that this extension initialization does not impact existing
in-flight SEAMCALLs that are not implemented by the extension. So only
the first user of an extension-seamcall needs invoke this helper.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h            |   3 +
 arch/x86/virt/vmx/tdx/tdx.h           |   2 +
 arch/x86/virt/vmx/tdx/tdx.c           | 184 ++++++++++++++++++++++++--
 drivers/virt/coco/tdx-host/tdx-host.c |   5 +
 4 files changed, 181 insertions(+), 13 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 3a3ea3fa04f2..1eeb77a6790a 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -125,11 +125,13 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 #define seamcall(_fn, _args)		sc_retry(__seamcall, (_fn), (_args))
 #define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
 #define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
+int tdx_enable_ext(void);
 const char *tdx_dump_mce_info(struct mce *m);
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_TDXCONNECT	BIT_ULL(6)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_EXT		BIT_ULL(39)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
@@ -223,6 +225,7 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 #else
 static inline void tdx_init(void) { }
+static inline int tdx_enable_ext(void) { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 4370d3d177f6..b84678165d00 100644
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
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9a5c32dc1767..bbf93cad5bf2 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -59,6 +59,9 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
+static DEFINE_MUTEX(tdx_module_ext_lock);
+static bool tdx_module_ext_initialized;
+
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
@@ -517,7 +520,7 @@ EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_release);
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
 #define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
 
-static u64 __maybe_unused hpa_list_info_assign_raw(struct tdx_page_array *array)
+static u64 hpa_list_info_assign_raw(struct tdx_page_array *array)
 {
 	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
 	       FIELD_PREP(HPA_LIST_INFO_PFN, page_to_pfn(array->root)) |
@@ -1251,7 +1254,14 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
-	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
+
+	if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_TDXCONNECT) {
+		args.r9 |= TDX_FEATURES0_TDXCONNECT;
+		args.r11 = ktime_get_real_seconds();
+		ret = seamcall_prerr(TDH_SYS_CONFIG | (1ULL << TDX_VERSION_SHIFT), &args);
+	} else {
+		ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
+	}
 
 	/* Free the array as it is not required anymore. */
 	kfree(tdmr_pa_array);
@@ -1411,6 +1421,11 @@ static __init int init_tdx_module(void)
 	if (ret)
 		goto err_free_pamts;
 
+	/* configuration to tdx module may change tdx_sysinfo, update it */
+	ret = get_tdx_sys_info(&tdx_sysinfo);
+	if (ret)
+		goto err_reset_pamts;
+
 	/* Config the key of global KeyID on all packages */
 	ret = config_global_keyid();
 	if (ret)
@@ -1488,6 +1503,160 @@ static __init int tdx_enable(void)
 }
 subsys_initcall(tdx_enable);
 
+static int enable_tdx_ext(void)
+{
+	struct tdx_module_args args = {};
+	u64 r;
+
+	if (!tdx_sysinfo.ext.ext_required)
+		return 0;
+
+	do {
+		r = seamcall(TDH_EXT_INIT, &args);
+		cond_resched();
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
+	tdx_page_array_free(mempool);
+}
+
+DEFINE_FREE(tdx_ext_mempool_free, struct tdx_page_array *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_ext_mempool_free(_T))
+
+/*
+ * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
+ * a CLFLUSH of pages is required before handing them to the TDX module.
+ * Be conservative and make the code simpler by doing the CLFLUSH
+ * unconditionally.
+ */
+static void tdx_clflush_page(struct page *page)
+{
+	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
+}
+
+static void tdx_clflush_page_array(struct tdx_page_array *array)
+{
+	for (int i = 0; i < array->nents; i++)
+		tdx_clflush_page(array->pages[array->offset + i]);
+}
+
+static int tdx_ext_mem_add(struct tdx_page_array *mempool)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa_list_info_assign_raw(mempool),
+	};
+	u64 r;
+
+	tdx_clflush_page_array(mempool);
+
+	do {
+		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
+		cond_resched();
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
+static struct tdx_page_array *tdx_ext_mempool_setup(void)
+{
+	unsigned int nr_pages, nents, offset = 0;
+	int ret;
+
+	nr_pages = tdx_sysinfo.ext.memory_pool_required_pages;
+	if (!nr_pages)
+		return NULL;
+
+	struct tdx_page_array *mempool __free(tdx_page_array_free) =
+		tdx_page_array_alloc(nr_pages);
+	if (!mempool)
+		return ERR_PTR(-ENOMEM);
+
+	while (1) {
+		nents = tdx_page_array_fill_root(mempool, offset);
+		if (!nents)
+			break;
+
+		ret = tdx_ext_mem_add(mempool);
+		if (ret)
+			return ERR_PTR(ret);
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
+/**
+ * tdx_enable_ext - Enable TDX module extensions.
+ *
+ * This function can be called in parallel by multiple callers.
+ *
+ * Return 0 if TDX module extension is enabled successfully, otherwise error.
+ */
+int tdx_enable_ext(void)
+{
+	int ret;
+
+	if (!tdx_module_initialized)
+		return -ENOENT;
+
+	guard(mutex)(&tdx_module_ext_lock);
+
+	if (tdx_module_ext_initialized)
+		return 0;
+
+	ret = init_tdx_ext();
+	if (ret) {
+		pr_debug("module extension initialization failed (%d)\n", ret);
+		return ret;
+	}
+
+	pr_debug("module extension initialized\n");
+	tdx_module_ext_initialized = true;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tdx_enable_ext);
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
@@ -1769,17 +1938,6 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
-/*
- * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
- * a CLFLUSH of pages is required before handing them to the TDX module.
- * Be conservative and make the code simpler by doing the CLFLUSH
- * unconditionally.
- */
-static void tdx_clflush_page(struct page *page)
-{
-	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
-}
-
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 6f21bb2dbeb9..982c928fae86 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -125,6 +125,7 @@ static void unregister_link_tsm(void *link)
 static int __maybe_unused tdx_connect_init(struct device *dev)
 {
 	struct tsm_dev *link;
+	int ret;
 
 	if (!IS_ENABLED(CONFIG_TDX_CONNECT))
 		return 0;
@@ -146,6 +147,10 @@ static int __maybe_unused tdx_connect_init(struct device *dev)
 	if (!(tdx_sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT))
 		return 0;
 
+	ret = tdx_enable_ext();
+	if (ret)
+		return dev_err_probe(dev, ret, "Enable extension failed\n");
+
 	link = tsm_register(dev, &tdx_link_ops);
 	if (IS_ERR(link))
 		return dev_err_probe(dev, PTR_ERR(link),

---

## [10] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 09/26] ACPICA: Add KEYP table definition*

From: Dave Jiang <dave.jiang@intel.com>

ACPICA commit af970172e2dde62d1ab8ba1429c97339ef3c6c23

Software uses this table to discover the base address of the Key
Configuration Unit (KCU) register block associated with each IDE capable
host bridge.

[1]: Root Complex IDE Key Configuration Unit Software Programming Guide
     https://cdrdv2.intel.com/v1/dl/getContent/732838

Link: https://github.com/acpica/acpica/commit/af970172
Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/acpi/actbl2.h | 59 +++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 59 insertions(+)

diff --git a/include/acpi/actbl2.h b/include/acpi/actbl2.h
index f726bce3eb84..4040e4df051b 100644
--- a/include/acpi/actbl2.h
+++ b/include/acpi/actbl2.h
@@ -32,6 +32,7 @@
 #define ACPI_SIG_ERDT           "ERDT"	/* Enhanced Resource Director Technology */
 #define ACPI_SIG_IORT           "IORT"	/* IO Remapping Table */
 #define ACPI_SIG_IVRS           "IVRS"	/* I/O Virtualization Reporting Structure */
+#define ACPI_SIG_KEYP           "KEYP"	/* Key Programming Interface for IDE */
 #define ACPI_SIG_LPIT           "LPIT"	/* Low Power Idle Table */
 #define ACPI_SIG_MADT           "APIC"	/* Multiple APIC Description Table */
 #define ACPI_SIG_MCFG           "MCFG"	/* PCI Memory Mapped Configuration table */
@@ -1065,6 +1066,64 @@ struct acpi_ivrs_memory {
 	u64 memory_length;
 };
 
+/*******************************************************************************
+ *
+ * KEYP - Key Programming Interface for Root Complex Integrity and Data
+ *        Encryption (IDE)
+ *        Version 1
+ *
+ * Conforms to "Key Programming Interface for Root Complex Integrity and Data
+ * Encryption (IDE)" document. See under ACPI-Related Documents.
+ *
+ ******************************************************************************/
+struct acpi_table_keyp {
+	struct acpi_table_header header;	/* Common ACPI table header */
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
+#define ACPI_KEYP_F_TVM_USABLE      (1)
+
 /*******************************************************************************
  *
  * LPIT - Low Power Idle Table

---

## [11] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 10/26] acpi: Add KEYP support to fw_table parsing*

From: Dave Jiang <dave.jiang@intel.com>

KEYP ACPI table can be parsed using the common fw_table handlers. Add
additional support to detect and parse the table.

Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/acpi.h     |  3 +++
 include/linux/fw_table.h |  1 +
 drivers/acpi/tables.c    | 12 +++++++++++-
 lib/fw_table.c           |  9 +++++++++
 4 files changed, 24 insertions(+), 1 deletion(-)

diff --git a/include/linux/acpi.h b/include/linux/acpi.h
index 5ff5d99f6ead..3bfcd9c5d4e4 100644
--- a/include/linux/acpi.h
+++ b/include/linux/acpi.h
@@ -234,6 +234,9 @@ int acpi_table_parse_madt(enum acpi_madt_type id,
 int __init_or_acpilib
 acpi_table_parse_cedt(enum acpi_cedt_type id,
 		      acpi_tbl_entry_handler_arg handler_arg, void *arg);
+int __init_or_acpilib
+acpi_table_parse_keyp(enum acpi_keyp_type id,
+		      acpi_tbl_entry_handler_arg handler_arg, void *arg);
 
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
diff --git a/drivers/acpi/tables.c b/drivers/acpi/tables.c
index 57fc8bc56166..4162386d9672 100644
--- a/drivers/acpi/tables.c
+++ b/drivers/acpi/tables.c
@@ -299,6 +299,16 @@ acpi_table_parse_cedt(enum acpi_cedt_type id,
 }
 EXPORT_SYMBOL_ACPI_LIB(acpi_table_parse_cedt);
 
+int __init_or_acpilib
+acpi_table_parse_keyp(enum acpi_keyp_type id,
+		      acpi_tbl_entry_handler_arg handler_arg, void *arg)
+{
+	return __acpi_table_parse_entries(ACPI_SIG_KEYP,
+					  sizeof(struct acpi_table_keyp), id,
+					  NULL, handler_arg, arg, 0);
+}
+EXPORT_SYMBOL_ACPI_LIB(acpi_table_parse_keyp);
+
 int __init acpi_table_parse_entries(char *id, unsigned long table_size,
 				    int entry_id,
 				    acpi_tbl_entry_handler handler,
@@ -408,7 +418,7 @@ static const char table_sigs[][ACPI_NAMESEG_SIZE] __nonstring_array __initconst
 	ACPI_SIG_PSDT, ACPI_SIG_RSDT, ACPI_SIG_XSDT, ACPI_SIG_SSDT,
 	ACPI_SIG_IORT, ACPI_SIG_NFIT, ACPI_SIG_HMAT, ACPI_SIG_PPTT,
 	ACPI_SIG_NHLT, ACPI_SIG_AEST, ACPI_SIG_CEDT, ACPI_SIG_AGDI,
-	ACPI_SIG_NBFT, ACPI_SIG_SWFT};
+	ACPI_SIG_NBFT, ACPI_SIG_SWFT, ACPI_SIG_KEYP};
 
 #define ACPI_HEADER_SIZE sizeof(struct acpi_table_header)
 
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

## [12] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 11/26] iommu/vt-d: Cache max domain ID to avoid redundant calculation*

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
 drivers/iommu/intel/iommu.h |  1 +
 drivers/iommu/intel/dmar.c  |  1 +
 drivers/iommu/intel/iommu.c | 10 +++++-----
 3 files changed, 7 insertions(+), 5 deletions(-)

diff --git a/drivers/iommu/intel/iommu.h b/drivers/iommu/intel/iommu.h
index 3056583d7f56..66c3aa549fd4 100644
--- a/drivers/iommu/intel/iommu.h
+++ b/drivers/iommu/intel/iommu.h
@@ -724,6 +724,7 @@ struct intel_iommu {
 	/* mutex to protect domain_ida */
 	struct mutex	did_lock;
 	struct ida	domain_ida; /* domain id allocator */
+	unsigned long	max_domain_id;
 	unsigned long	*copied_tables; /* bitmap of copied tables */
 	spinlock_t	lock; /* protect context, domain ids */
 	struct root_entry *root_entry; /* virtual address */
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
index e236c7ec221f..848b300da63e 100644
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
@@ -1986,7 +1986,7 @@ static int copy_context_table(struct intel_iommu *iommu,
 			continue;
 
 		did = context_domain_id(&ce);
-		if (did >= 0 && did < cap_ndoms(iommu->cap))
+		if (did >= 0 && did < iommu->max_domain_id)
 			ida_alloc_range(&iommu->domain_ida, did, did, GFP_KERNEL);
 
 		set_context_copied(iommu, bus, devfn);
@@ -2902,7 +2902,7 @@ static ssize_t domains_supported_show(struct device *dev,
 				      struct device_attribute *attr, char *buf)
 {
 	struct intel_iommu *iommu = dev_to_intel_iommu(dev);
-	return sysfs_emit(buf, "%ld\n", cap_ndoms(iommu->cap));
+	return sysfs_emit(buf, "%ld\n", iommu->max_domain_id);
 }
 static DEVICE_ATTR_RO(domains_supported);
 
@@ -2913,7 +2913,7 @@ static ssize_t domains_used_show(struct device *dev,
 	unsigned int count = 0;
 	int id;
 
-	for (id = 0; id < cap_ndoms(iommu->cap); id++)
+	for (id = 0; id < iommu->max_domain_id; id++)
 		if (ida_exists(&iommu->domain_ida, id))
 			count++;

---

## [13] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 12/26] iommu/vt-d: Reserve the MSB domain ID bit for the TDX module*

From: Lu Baolu <baolu.lu@linux.intel.com>

The Intel TDX Connect Architecture Specification defines some enhancements
for the VT-d architecture to introduce IOMMU support for TEE-IO requests.
Section 2.2, 'Trusted DMA' states that:

"I/O TLB and DID Isolation – When IOMMU is enabled to support TDX
Connect, the IOMMU restricts the VMM’s DID setting, reserving the MSB bit
for the TDX module. The TDX module always sets this reserved bit on the
trusted DMA table. IOMMU tags IOTLB, PASID cache, and context entries to
indicate whether they were created from TEE-IO transactions, ensuring
isolation between TEE and non-TEE requests in translation caches."

Reserve the MSB in the domain ID for the TDX module's use if the
enhancement is required, which is detected if the ECAP.TDXCS bit in the
VT-d extended capability register is set and the TVM Usable field of the
ACPI KEYP table is set.

Signed-off-by: Lu Baolu <baolu.lu@linux.intel.com>
---
 drivers/iommu/intel/iommu.h |  1 +
 drivers/iommu/intel/dmar.c  | 52 ++++++++++++++++++++++++++++++++++++-
 2 files changed, 52 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/intel/iommu.h b/drivers/iommu/intel/iommu.h
index 66c3aa549fd4..836777d7645d 100644
--- a/drivers/iommu/intel/iommu.h
+++ b/drivers/iommu/intel/iommu.h
@@ -192,6 +192,7 @@
  */
 
 #define ecap_pms(e)		(((e) >> 51) & 0x1)
+#define ecap_tdxc(e)		(((e) >> 50) & 0x1)
 #define ecap_rps(e)		(((e) >> 49) & 0x1)
 #define ecap_smpwc(e)		(((e) >> 48) & 0x1)
 #define ecap_flts(e)		(((e) >> 47) & 0x1)
diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index a54934c0536f..e9d65b26ad64 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -1033,6 +1033,56 @@ static int map_iommu(struct intel_iommu *iommu, struct dmar_drhd_unit *drhd)
 	return err;
 }
 
+static int keyp_config_unit_tvm_usable(union acpi_subtable_headers *header,
+				       void *arg, const unsigned long end)
+{
+	struct acpi_keyp_config_unit *acpi_cu =
+		(struct acpi_keyp_config_unit *)&header->keyp;
+	int *tvm_usable = arg;
+
+	if (acpi_cu->flags & ACPI_KEYP_F_TVM_USABLE)
+		*tvm_usable = true;
+
+	return 0;
+}
+
+static bool platform_is_tdxc_enhanced(void)
+{
+	static int tvm_usable = -1;
+	int ret;
+
+	/* only need to parse once */
+	if (tvm_usable != -1)
+		return tvm_usable;
+
+	tvm_usable = false;
+	ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
+				    keyp_config_unit_tvm_usable, &tvm_usable);
+	if (ret < 0)
+		tvm_usable = false;
+
+	return tvm_usable;
+}
+
+static unsigned long iommu_max_domain_id(struct intel_iommu *iommu)
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
+	if (ecap_tdxc(iommu->ecap) && platform_is_tdxc_enhanced()) {
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
@@ -1099,7 +1149,7 @@ static int alloc_iommu(struct dmar_drhd_unit *drhd)
 	spin_lock_init(&iommu->lock);
 	ida_init(&iommu->domain_ida);
 	mutex_init(&iommu->did_lock);
-	iommu->max_domain_id = cap_ndoms(iommu->cap);
+	iommu->max_domain_id = iommu_max_domain_id(iommu);
 
 	ver = readl(iommu->reg + DMAR_VER_REG);
 	pr_info("%s: reg_base_addr %llx ver %d:%d cap %llx ecap %llx\n",

---

## [14] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 13/26] x86/virt/tdx: Read TDX Connect global metadata for TDX Connect*

Add several global metadata fields for TDX Connect. These metadata field
specify the number of metadata pages needed for IOMMU/IDE/SPDM setup.

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
index c3b2e2748b3e..b9029c3f9b32 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -98,6 +98,23 @@ static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
 	return ret;
 }
 
+static __init int get_tdx_sys_info_connect(struct tdx_sys_info_connect *sysinfo_connect)
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
 static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -107,6 +124,7 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
 	ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
+	ret = ret ?: get_tdx_sys_info_connect(&sysinfo->connect);
 
 	return ret;
 }

---

## [15] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 14/26] mm: Add __free() support for folio_put()*

Allow for the declaration of struct folio * variables that trigger
folio_put() when they go out of scope.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/mm.h | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/include/linux/mm.h b/include/linux/mm.h
index d16b33bacc32..2456bb775e27 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -1425,6 +1425,8 @@ static inline void folio_put(struct folio *folio)
 		__folio_put(folio);
 }
 
+DEFINE_FREE(folio_put, struct folio *, if (_T) folio_put(_T))
+
 /**
  * folio_put_refs - Reduce the reference count on a folio.
  * @folio: The folio.

---

## [16] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 15/26] x86/virt/tdx: Extend tdx_page_array to support IOMMU_MT*

IOMMU_MT is another TDX Module defined structure similar to HPA_ARRAY_T
and HPA_LIST_INFO. The difference is it supports multi-order contiguous
pages. It adds an additional NUM_PAGES field for every multi-order page
entry.

Add an dedicated allocation helper for IOMMU_MT. Maybe a general
allocation helper for multi-order is better but could postponed until
another user appears.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c | 71 +++++++++++++++++++++++++++++++++++--
 2 files changed, 70 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 1eeb77a6790a..4078fc497779 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -157,6 +157,8 @@ void tdx_page_array_ctrl_leak(struct tdx_page_array *array);
 int tdx_page_array_ctrl_release(struct tdx_page_array *array,
 				unsigned int nr_released,
 				u64 released_hpa);
+struct tdx_page_array *
+tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages);
 
 struct tdx_td {
 	/* TD root structure: */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index bbf93cad5bf2..46cdb5aaaf68 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -316,8 +316,15 @@ static int tdx_page_array_fill_root(struct tdx_page_array *array,
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
@@ -327,7 +334,7 @@ static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
 	unsigned long i;
 
 	for (i = 0; i < nr_pages; i++)
-		__free_page(pages[i]);
+		put_page(pages[i]);
 }
 
 static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages)
@@ -466,6 +473,10 @@ static bool tdx_page_array_validate_release(struct tdx_page_array *array,
 			struct page *page = array->pages[offset + i];
 			u64 val = page_to_phys(page);
 
+			/* Now only for iommu_mt */
+			if (compound_nr(page) > 1)
+				val |= compound_nr(page);
+
 			if (val != entries[i]) {
 				pr_err("%s entry[%d] [0x%llx] doesn't match page hpa [0x%llx]\n",
 				       __func__, i, entries[i], val);
@@ -516,6 +527,60 @@ int tdx_page_array_ctrl_release(struct tdx_page_array *array,
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
 #define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
 #define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)

---

## [17] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 16/26] x86/virt/tdx: Add a helper to loop on TDX_INTERRUPTED_RESUMABLE*

Add a helper to handle SEAMCALL return code TDX_INTERRUPTED_RESUMABLE.

SEAMCALL returns TDX_INTERRUPTED_RESUMABLE to avoid stalling host for
long time. After host has handled the interrupt, it calls the
interrupted SEAMCALL again and TDX Module continues to execute. TDX
Module made progress in this case and would eventually finish. An
infinite loop in host should be safe.

The helper is for SEAMCALL wrappers which output information by using
seamcall_ret() or seamcall_saved_ret(). The 2 functions overwrite input
arguments by outputs but much SEAMCALLs expect the same inputs to
resume.

The helper is not for special cases where the SEAMCALL expects modified
inputs to resume. The helper is also not for SEAMCALLs with no output,
do {...} while (r == TDX_INTERRUPTED_RESUMABLE) just works.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 23 +++++++++++++++++++++++
 1 file changed, 23 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 46cdb5aaaf68..7bc2c900a8a8 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2003,6 +2003,29 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
+static u64 __maybe_unused __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
+						struct tdx_module_args *args)
+{
+	struct tdx_module_args _args;
+	u64 r;
+
+	while (1) {
+		_args = *(args);
+		r = sc_retry(sc_func, fn, &_args);
+		if (r != TDX_INTERRUPTED_RESUMABLE)
+			break;
+
+		cond_resched();
+	}
+
+	*args = _args;
+
+	return r;
+}
+
+#define seamcall_ret_ir_resched(fn, args)	\
+	__seamcall_ir_resched(__seamcall_ret, fn, args)
+
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;

---

## [18] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 17/26] x86/virt/tdx: Add SEAMCALL wrappers for trusted IOMMU setup and clear*

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
 arch/x86/virt/vmx/tdx/tdx.h |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c | 32 ++++++++++++++++++++++++++++++--
 3 files changed, 34 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 4078fc497779..efc4200b9931 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -225,6 +225,8 @@ u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u6
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id);
+u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_enable_ext(void) { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index b84678165d00..7c653604271b 100644
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
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 7bc2c900a8a8..fe3b43c86314 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2003,8 +2003,8 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
-static u64 __maybe_unused __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
-						struct tdx_module_args *args)
+static u64 __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
+				 struct tdx_module_args *args)
 {
 	struct tdx_module_args _args;
 	u64 r;
@@ -2397,3 +2397,31 @@ void tdx_cpu_flush_cache_for_kexec(void)
 }
 EXPORT_SYMBOL_GPL(tdx_cpu_flush_cache_for_kexec);
 #endif
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
+	r = seamcall_ret_ir_resched(TDH_IOMMU_SETUP, &args);
+
+	*iommu_id = args.rcx;
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_iommu_setup, "tdx-host");
+
+u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
+{
+	struct tdx_module_args args = {
+		.rcx = iommu_id,
+		.rdx = page_to_phys(iommu_mt->root),
+	};
+
+	return seamcall_ret_ir_resched(TDH_IOMMU_CLEAR, &args);
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_iommu_clear, "tdx-host");

---

## [19] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 18/26] iommu/vt-d: Export a helper to do function for each dmar_drhd_unit*

Enable the tdx-host module to get VTBAR address for every IOMMU device.
The VTBAR address is for TDX Module to identify the IOMMU device and
setup its trusted configuraion.

Suggested-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/dmar.h       |  2 ++
 drivers/iommu/intel/dmar.c | 16 ++++++++++++++++
 2 files changed, 18 insertions(+)

diff --git a/include/linux/dmar.h b/include/linux/dmar.h
index 692b2b445761..cd8d9f440975 100644
--- a/include/linux/dmar.h
+++ b/include/linux/dmar.h
@@ -86,6 +86,8 @@ extern struct list_head dmar_drhd_units;
 				dmar_rcu_check())			\
 		if (i=drhd->iommu, 0) {} else 
 
+int do_for_each_drhd_unit(int (*fn)(struct dmar_drhd_unit *));
+
 static inline bool dmar_rcu_check(void)
 {
 	return rwsem_is_locked(&dmar_global_lock) ||
diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index e9d65b26ad64..645b72270967 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -2452,3 +2452,19 @@ bool dmar_platform_optin(void)
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

---

## [20] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 19/26] coco/tdx-host: Setup all trusted IOMMUs on TDX Connect init*

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
 drivers/virt/coco/tdx-host/tdx-host.c | 85 +++++++++++++++++++++++++++
 1 file changed, 85 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 982c928fae86..3cd19966a61b 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -5,6 +5,7 @@
  * Copyright (C) 2025 Intel Corporation
  */
 
+#include <linux/dmar.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
@@ -122,6 +123,82 @@ static void unregister_link_tsm(void *link)
 	tsm_unregister(link);
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
+	r = tdh_iommu_setup(drhd->reg_base_addr, iommu_mt, &iommu_id);
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
 static int __maybe_unused tdx_connect_init(struct device *dev)
 {
 	struct tsm_dev *link;
@@ -151,6 +228,14 @@ static int __maybe_unused tdx_connect_init(struct device *dev)
 	if (ret)
 		return dev_err_probe(dev, ret, "Enable extension failed\n");
 
+	ret = tdx_iommu_enable_all();
+	if (ret)
+		return dev_err_probe(dev, ret, "Enable tdx iommu failed\n");
+
+	ret = devm_add_action_or_reset(dev, tdx_iommu_disable_all, NULL);
+	if (ret)
+		return ret;
+
 	link = tsm_register(dev, &tdx_link_ops);
 	if (IS_ERR(link))
 		return dev_err_probe(dev, PTR_ERR(link),

---

## [21] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 20/26] coco/tdx-host: Add a helper to exchange SPDM messages through DOE*

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
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 61 +++++++++++++++++++++++++++
 1 file changed, 61 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 3cd19966a61b..f0151561e00e 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -5,10 +5,12 @@
  * Copyright (C) 2025 Intel Corporation
  */
 
+#include <linux/bitfield.h>
 #include <linux/dmar.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
+#include <linux/pci-doe.h>
 #include <linux/pci-tsm.h>
 #include <linux/tsm.h>
 #include <linux/device/faux.h>
@@ -41,6 +43,65 @@ static struct tdx_link *to_tdx_link(struct pci_tsm *tsm)
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
+	ret = pci_tsm_doe_transfer(pdev, type, req_pl_addr, req_pl_sz,
+				   resp_pl_addr, resp_pl_sz);
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

## [22] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 21/26] x86/virt/tdx: Add SEAMCALL wrappers for SPDM management*

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
 arch/x86/include/asm/tdx.h  |  13 ++++
 arch/x86/virt/vmx/tdx/tdx.h |   5 ++
 arch/x86/virt/vmx/tdx/tdx.c | 114 +++++++++++++++++++++++++++++++++++-
 3 files changed, 130 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index efc4200b9931..8e6da080f4e2 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -227,6 +227,19 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id);
 u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt);
+u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id);
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
+		    unsigned int *nr_released, u64 *released_hpa);
+u64 tdh_exec_spdm_connect(u64 spdm_id, struct page *spdm_conf,
+			  struct page *spdm_rsp, struct page *spdm_req,
+			  struct tdx_page_array *spdm_out,
+			  u64 *spdm_req_or_out_len);
+u64 tdh_exec_spdm_disconnect(u64 spdm_id, struct page *spdm_rsp,
+			     struct page *spdm_req, u64 *spdm_req_len);
+u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      struct tdx_page_array *spdm_out,
+		      u64 *spdm_req_or_out_len);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_enable_ext(void) { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 7c653604271b..f68b9d3abfe1 100644
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
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index fe3b43c86314..a0ba4d13e340 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -595,7 +595,7 @@ static u64 hpa_list_info_assign_raw(struct tdx_page_array *array)
 #define HPA_ARRAY_T_PFN		GENMASK_U64(51, 12)
 #define HPA_ARRAY_T_SIZE	GENMASK_U64(63, 55)
 
-static u64 __maybe_unused hpa_array_t_assign_raw(struct tdx_page_array *array)
+static u64 hpa_array_t_assign_raw(struct tdx_page_array *array)
 {
 	struct page *page;
 
@@ -608,7 +608,7 @@ static u64 __maybe_unused hpa_array_t_assign_raw(struct tdx_page_array *array)
 	       FIELD_PREP(HPA_ARRAY_T_SIZE, array->nents - 1);
 }
 
-static u64 __maybe_unused hpa_array_t_release_raw(struct tdx_page_array *array)
+static u64 hpa_array_t_release_raw(struct tdx_page_array *array)
 {
 	if (array->nents == 1)
 		return 0;
@@ -2026,6 +2026,15 @@ static u64 __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
 #define seamcall_ret_ir_resched(fn, args)	\
 	__seamcall_ir_resched(__seamcall_ret, fn, args)
 
+/*
+ * seamcall_ret_ir_exec() aliases seamcall_ret_ir_resched() for
+ * documentation purposes. It documents the TDX Module extension
+ * seamcalls that are long running / hard-irq preemptible flows that
+ * generate events. The calls using seamcall_ret_ir_resched() are long
+ * running flows, that periodically yield.
+ */
+#define seamcall_ret_ir_exec seamcall_ret_ir_resched
+
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;
@@ -2425,3 +2434,104 @@ u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
 	return seamcall_ret_ir_resched(TDH_IOMMU_CLEAR, &args);
 }
 EXPORT_SYMBOL_FOR_MODULES(tdh_iommu_clear, "tdx-host");
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
+EXPORT_SYMBOL_FOR_MODULES(tdh_spdm_create, "tdx-host");
+
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
+		    unsigned int *nr_released, u64 *released_hpa)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = hpa_array_t_release_raw(spdm_mt),
+	};
+	u64 r;
+
+	r = seamcall_ret(TDH_SPDM_DELETE, &args);
+	if (r < 0)
+		return r;
+
+	*nr_released = FIELD_GET(HPA_ARRAY_T_SIZE, args.rcx) + 1;
+	*released_hpa = FIELD_GET(HPA_ARRAY_T_PFN, args.rcx) << PAGE_SHIFT;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_spdm_delete, "tdx-host");
+
+u64 tdh_exec_spdm_connect(u64 spdm_id, struct page *spdm_conf,
+			  struct page *spdm_rsp, struct page *spdm_req,
+			  struct tdx_page_array *spdm_out,
+			  u64 *spdm_req_or_out_len)
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
+	r = seamcall_ret_ir_exec(TDH_SPDM_CONNECT, &args);
+
+	*spdm_req_or_out_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_connect, "tdx-host");
+
+u64 tdh_exec_spdm_disconnect(u64 spdm_id, struct page *spdm_rsp,
+			     struct page *spdm_req, u64 *spdm_req_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = page_to_phys(spdm_rsp),
+		.r8 = page_to_phys(spdm_req),
+	};
+	u64 r;
+
+	r = seamcall_ret_ir_exec(TDH_SPDM_DISCONNECT, &args);
+
+	*spdm_req_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_disconnect, "tdx-host");
+
+u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      struct tdx_page_array *spdm_out,
+		      u64 *spdm_req_or_out_len)
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
+	r = seamcall_ret_ir_exec(TDH_SPDM_MNG, &args);
+
+	*spdm_req_or_out_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_mng, "tdx-host");

---

## [23] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 22/26] coco/tdx-host: Implement SPDM session setup*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Implementation for a most straightforward SPDM session setup, using all
default session options. Retrieve device info data from TDX Module which
contains the SPDM negotiation results.

TDH.SPDM.CONNECT/DISCONNECT are TDX Module Extension introduced
SEAMCALLs which can run for longer periods and interruptible. But there
is resource constraints that limit how many SEAMCALLs of this kind can
run simultaneously. The current situation is One SEAMCALL at a time.
Otherwise TDX_OPERAND_BUSY is returned. To avoid "broken indefinite"
retry, a tdx_ext_lock is used to guard these SEAMCALLs.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/include/asm/shared/tdx_errno.h |   2 +
 drivers/virt/coco/tdx-host/tdx-host.c   | 301 +++++++++++++++++++++++-
 2 files changed, 299 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index f98924fe5198..7e87496a9603 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -28,6 +28,8 @@
 #define TDX_EPT_WALK_FAILED			0xC0000B0000000000ULL
 #define TDX_EPT_ENTRY_STATE_INCORRECT		0xC0000B0D00000000ULL
 #define TDX_METADATA_FIELD_NOT_READABLE		0xC0000C0200000000ULL
+#define TDX_SPDM_SESSION_KEY_REQUIRE_REFRESH	0xC0000F4500000000ULL
+#define TDX_SPDM_REQUEST			0xC0000F5700000000ULL
 
 /*
  * SW-defined error codes.
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index f0151561e00e..ede47ccb5821 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -14,6 +14,7 @@
 #include <linux/pci-tsm.h>
 #include <linux/tsm.h>
 #include <linux/device/faux.h>
+#include <linux/vmalloc.h>
 #include <asm/cpu_device_id.h>
 #include <asm/tdx.h>
 #include <asm/tdx_global_metadata.h>
@@ -34,8 +35,34 @@ MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
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
@@ -50,9 +77,9 @@ static struct tdx_link *to_tdx_link(struct pci_tsm *tsm)
 
 #define PCI_DOE_PROTOCOL_SECURE_SPDM		2
 
-static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_link *tlink,
-						void *request, size_t request_sz,
-						void *response, size_t response_sz)
+static int tdx_spdm_msg_exchange(struct tdx_link *tlink,
+				 void *request, size_t request_sz,
+				 void *response, size_t response_sz)
 {
 	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
 	void *req_pl_addr, *resp_pl_addr;
@@ -102,18 +129,258 @@ static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_link *tlink,
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
+ * TDX Module extension introduced SEAMCALLs work like a request queue.
+ * The caller is responsible for grabbing a queue slot before SEAMCALL,
+ * otherwise will fail with TDX_OPERAND_BUSY. Currently the queue depth is 1.
+ * So a mutex could work for simplicity.
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
+		r = tdh_exec_spdm_mng(tlink->spdm_id, op, NULL, tlink->in_msg,
+				      tlink->out_msg, NULL, &out_msg_sz);
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
+static struct tdx_link *tdx_spdm_session_connect(struct tdx_link *tlink,
+						 struct tdx_page_array *dev_info)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_exec_spdm_connect(tlink->spdm_id, tlink->spdm_conf,
+					  tlink->in_msg, tlink->out_msg,
+					  dev_info, &out_msg_sz);
+		ret = tdx_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	if (ret)
+		return ERR_PTR(ret);
+
+	tlink->dev_info_size = out_msg_sz;
+	return tlink;
+}
+
+static void tdx_spdm_session_disconnect(struct tdx_link *tlink)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_exec_spdm_disconnect(tlink->spdm_id, tlink->in_msg,
+					     tlink->out_msg, &out_msg_sz);
+		ret = tdx_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	WARN_ON(ret);
+}
+
+DEFINE_FREE(tdx_spdm_session_disconnect, struct tdx_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_spdm_session_disconnect(_T))
+
+static struct tdx_link *tdx_spdm_create(struct tdx_link *tlink)
+{
+	unsigned int nr_pages = tdx_sysinfo->connect.spdm_mt_page_count;
+	u64 spdm_id, r;
+
+	struct tdx_page_array *spdm_mt __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages);
+	if (!spdm_mt)
+		return ERR_PTR(-ENOMEM);
+
+	r = tdh_spdm_create(tlink->func_id, spdm_mt, &spdm_id);
+	if (r)
+		return ERR_PTR(-EFAULT);
+
+	tlink->spdm_id = spdm_id;
+	tlink->spdm_mt = no_free_ptr(spdm_mt);
+	return tlink;
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
+	return;
+
+leak:
+	tdx_page_array_ctrl_leak(tlink->spdm_mt);
+}
+
+DEFINE_FREE(tdx_spdm_delete, struct tdx_link *, if (!IS_ERR_OR_NULL(_T)) tdx_spdm_delete(_T))
+
+static struct tdx_link *tdx_spdm_session_setup(struct tdx_link *tlink)
+{
+	unsigned int nr_pages = tdx_sysinfo->connect.spdm_max_dev_info_pages;
+
+	struct tdx_link *tlink_create __free(tdx_spdm_delete) =
+		tdx_spdm_create(tlink);
+	if (IS_ERR(tlink_create))
+		return tlink_create;
+
+	struct tdx_page_array *dev_info __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages);
+	if (!dev_info)
+		return ERR_PTR(-ENOMEM);
+
+	struct tdx_link *tlink_connect __free(tdx_spdm_session_disconnect) =
+		tdx_spdm_session_connect(tlink, dev_info);
+	if (IS_ERR(tlink_connect))
+		return tlink_connect;
+
+	tlink->dev_info_data = tdx_dup_array_data(dev_info,
+						  tlink->dev_info_size);
+	if (!tlink->dev_info_data)
+		return ERR_PTR(-ENOMEM);
+
+	retain_and_null_ptr(tlink_create);
+	retain_and_null_ptr(tlink_connect);
+
+	return tlink;
+}
+
+static void tdx_spdm_session_teardown(struct tdx_link *tlink)
+{
+	kfree(tlink->dev_info_data);
+
+	tdx_spdm_session_disconnect(tlink);
+	tdx_spdm_delete(tlink);
+}
+
+DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_spdm_session_teardown(_T))
+
 static int tdx_link_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct tdx_link *tlink = to_tdx_link(pdev->tsm);
+
+	struct tdx_link *tlink_spdm __free(tdx_spdm_session_teardown) =
+		tdx_spdm_session_setup(tlink);
+	if (IS_ERR(tlink_spdm)) {
+		pci_err(pdev, "fail to setup spdm session\n");
+		return PTR_ERR(tlink_spdm);
+	}
+
+	retain_and_null_ptr(tlink_spdm);
+
+	return 0;
 }
 
 static void tdx_link_disconnect(struct pci_dev *pdev)
 {
+	struct tdx_link *tlink = to_tdx_link(pdev->tsm);
+
+	tdx_spdm_session_teardown(tlink);
 }
 
+struct spdm_config_info_t {
+	u32 vmm_spdm_cap;
+#define SPDM_CAP_HBEAT          BIT(13)
+#define SPDM_CAP_KEY_UPD        BIT(14)
+	u8 spdm_session_policy;
+	u8 certificate_slot_mask;
+	u8 raw_bitstream_requested;
+} __packed;
+
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
@@ -125,6 +392,29 @@ static struct pci_tsm *tdx_link_pf0_probe(struct tsm_dev *tsm_dev,
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
 
@@ -132,6 +422,9 @@ static void tdx_link_pf0_remove(struct pci_tsm *tsm)
 {
 	struct tdx_link *tlink = to_tdx_link(tsm);
 
+	__free_page(tlink->spdm_conf);
+	__free_page(tlink->out_msg);
+	__free_page(tlink->in_msg);
 	pci_tsm_pf0_destructor(&tlink->pci);
 	kfree(tlink);
 }

---

## [24] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 23/26] coco/tdx-host: Parse ACPI KEYP table to init IDE for PCI host bridges*

Parse the KEYP Key Configuration Units (KCU), to decide the max IDE
streams supported for each host bridge.

The KEYP table points to a number of KCU structures that each associates
with a list of root ports (RP) via segment, bus, and devfn. Sanity check
the KEYP table, ensure all RPs listed for each KCU are included in one
host bridge. Then extact the max IDE streams supported to
pci_host_bridge via pci_ide_set_nr_streams().

Co-developed-by: Dave Jiang <dave.jiang@intel.com>
Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/tdx-host/Kconfig    |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 111 ++++++++++++++++++++++++++
 2 files changed, 112 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index 026b7d5ea4fa..5444798fa160 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -13,4 +13,5 @@ config TDX_CONNECT
 	bool
 	depends on TDX_HOST_SERVICES
 	depends on PCI_TSM
+	depends on ACPI
 	default TDX_HOST_SERVICES
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index ede47ccb5821..986a75084747 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -5,12 +5,14 @@
  * Copyright (C) 2025 Intel Corporation
  */
 
+#include <linux/acpi.h>
 #include <linux/bitfield.h>
 #include <linux/dmar.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
 #include <linux/pci-doe.h>
+#include <linux/pci-ide.h>
 #include <linux/pci-tsm.h>
 #include <linux/tsm.h>
 #include <linux/device/faux.h>
@@ -477,6 +479,111 @@ static void unregister_link_tsm(void *link)
 	tsm_unregister(link);
 }
 
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
+	return rp->segment == hb->segment && rp->bus >= hb->bus_start &&
+	       rp->bus <= hb->bus_end;
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
+static void keyp_setup_nr_ide_stream(struct pci_bus *bus)
+{
+	struct pci_host_bridge *hb = pci_find_host_bridge(bus);
+	u8 nr_ide_streams;
+
+	nr_ide_streams = keyp_find_nr_ide_stream(pci_domain_nr(bus),
+						 bus->busn_res.start,
+						 bus->busn_res.end);
+
+	pci_ide_set_nr_streams(hb, nr_ide_streams);
+}
+
+static void tdx_setup_nr_ide_stream(void)
+{
+	struct pci_bus *bus = NULL;
+
+	while ((bus = pci_find_next_bus(bus)))
+		keyp_setup_nr_ide_stream(bus);
+}
+
 static DEFINE_XARRAY(tlink_iommu_xa);
 
 static void tdx_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
@@ -590,6 +697,8 @@ static int __maybe_unused tdx_connect_init(struct device *dev)
 	if (ret)
 		return ret;
 
+	tdx_setup_nr_ide_stream();
+
 	link = tsm_register(dev, &tdx_link_ops);
 	if (IS_ERR(link))
 		return dev_err_probe(dev, PTR_ERR(link),
@@ -633,5 +742,7 @@ static void __exit tdx_host_exit(void)
 }
 module_exit(tdx_host_exit);
 
+MODULE_IMPORT_NS("ACPI");
+MODULE_IMPORT_NS("PCI_IDE");
 MODULE_DESCRIPTION("TDX Host Services");
 MODULE_LICENSE("GPL");

---

## [25] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 24/26] x86/virt/tdx: Add SEAMCALL wrappers for IDE stream management*

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
 arch/x86/virt/vmx/tdx/tdx.h |  4 ++
 arch/x86/virt/vmx/tdx/tdx.c | 86 +++++++++++++++++++++++++++++++++++++
 3 files changed, 104 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 8e6da080f4e2..b5ad3818f222 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -240,6 +240,20 @@ u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
 		      struct page *spdm_rsp, struct page *spdm_req,
 		      struct tdx_page_array *spdm_out,
 		      u64 *spdm_req_or_out_len);
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
 static inline int tdx_enable_ext(void) { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index f68b9d3abfe1..9097cabce343 100644
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
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a0ba4d13e340..fd622445d3d6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2535,3 +2535,89 @@ u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
 	return r;
 }
 EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_mng, "tdx-host");
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
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_create, "tdx-host");
+
+u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = stream_id,
+	};
+
+	return seamcall(TDH_IDE_STREAM_BLOCK, &args);
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_block, "tdx-host");
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
+	u64 r;
+
+	r = seamcall_ret(TDH_IDE_STREAM_DELETE, &args);
+	if (r < 0)
+		return r;
+
+	*nr_released = FIELD_GET(HPA_ARRAY_T_SIZE, args.rcx) + 1;
+	*released_hpa = FIELD_GET(HPA_ARRAY_T_PFN, args.rcx) << PAGE_SHIFT;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_delete, "tdx-host");
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
+	r = seamcall_ret_ir_resched(TDH_IDE_STREAM_KM, &args);
+
+	*spdm_req_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_km, "tdx-host");

---

## [26] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 25/26] coco/tdx-host: Implement IDE stream setup/teardown*

Implementation for a most straightforward Selective IDE stream setup.
Hard code all parameters for Stream Control Register. And no IDE Key
Refresh support.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/pci-ide.h               |   2 +
 drivers/pci/ide.c                     |   5 +-
 drivers/virt/coco/tdx-host/tdx-host.c | 225 ++++++++++++++++++++++++++
 3 files changed, 230 insertions(+), 2 deletions(-)

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 37a1ad9501b0..2521a2914294 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -106,6 +106,8 @@ struct pci_ide {
 void pci_ide_set_nr_streams(struct pci_host_bridge *hb, u16 nr);
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev,
 					    struct pci_ide *ide);
+void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
+			    struct pci_ide_regs *regs);
 struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
 void pci_ide_stream_free(struct pci_ide *ide);
 int  pci_ide_stream_register(struct pci_ide *ide);
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index f0ef474e1a0d..58246349178e 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -556,8 +556,8 @@ static void mem_assoc_to_regs(struct pci_bus_region *region,
  * @ide: registered IDE settings descriptor
  * @regs: output register values
  */
-static void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
-				   struct pci_ide_regs *regs)
+void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
+			    struct pci_ide_regs *regs)
 {
 	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
 	int assoc_idx = 0;
@@ -586,6 +586,7 @@ static void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
 
 	regs->nr_addr = assoc_idx;
 }
+EXPORT_SYMBOL_GPL(pci_ide_stream_to_regs);
 
 /**
  * pci_ide_stream_setup() - program settings to Selective IDE Stream registers
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 986a75084747..7f3c00f17ec7 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -65,6 +65,10 @@ struct tdx_link {
 	struct tdx_page_array *spdm_mt;
 	unsigned int dev_info_size;
 	void *dev_info_data;
+
+	struct pci_ide *ide;
+	struct tdx_page_array *stream_mt;
+	unsigned int stream_id;
 };
 
 static struct tdx_link *to_tdx_link(struct pci_tsm *tsm)
@@ -343,6 +347,218 @@ static void tdx_spdm_session_teardown(struct tdx_link *tlink)
 DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_link *,
 	    if (!IS_ERR_OR_NULL(_T)) tdx_spdm_session_teardown(_T))
 
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
+static struct tdx_link *tdx_ide_stream_key_program(struct tdx_link *tlink)
+{
+	int ret;
+
+	ret = tdx_ide_stream_km(tlink, TDX_IDE_STREAM_KM_SETUP);
+	if (ret)
+		return ERR_PTR(ret);
+
+	return tlink;
+}
+
+static void tdx_ide_stream_key_stop(struct tdx_link *tlink)
+{
+	tdx_ide_stream_km(tlink, TDX_IDE_STREAM_KM_STOP);
+}
+
+DEFINE_FREE(tdx_ide_stream_key_stop, struct tdx_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_ide_stream_key_stop(_T))
+
+static void sel_stream_block_regs(struct pci_dev *pdev, struct pci_ide *ide,
+				  struct pci_ide_regs *regs)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide_partner *setting = pci_ide_to_settings(rp, ide);
+
+	/* only support address association for prefetchable memory */
+	setting->mem_assoc = (struct pci_bus_region) { 0, -1 };
+	pci_ide_stream_to_regs(rp, ide, regs);
+}
+
+#define STREAM_INFO_RP_DEVFN		GENMASK_ULL(7, 0)
+#define STREAM_INFO_TYPE		BIT_ULL(8)
+#define  STREAM_INFO_TYPE_LINK		0
+#define  STREAM_INFO_TYPE_SEL		1
+
+static struct tdx_link *tdx_ide_stream_create(struct tdx_link *tlink,
+					      struct pci_ide *ide)
+{
+	u64 stream_info, stream_ctrl;
+	u64 stream_id, rp_ide_id;
+	unsigned int nr_pages = tdx_sysinfo->connect.ide_mt_page_count;
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide_regs regs;
+	u64 r;
+
+	struct tdx_page_array *stream_mt __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages);
+	if (!stream_mt)
+		return ERR_PTR(-ENOMEM);
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
+	sel_stream_block_regs(pdev, ide, &regs);
+	if (regs.nr_addr != 1)
+		return ERR_PTR(-EFAULT);
+
+	r = tdh_ide_stream_create(stream_info, tlink->spdm_id,
+				  stream_mt, stream_ctrl,
+				  regs.rid1, regs.rid2, regs.addr[0].assoc1,
+				  regs.addr[0].assoc2, regs.addr[0].assoc3,
+				  &stream_id, &rp_ide_id);
+	if (r)
+		return ERR_PTR(-EFAULT);
+
+	tlink->stream_id = stream_id;
+	tlink->stream_mt = no_free_ptr(stream_mt);
+
+	pci_dbg(pdev, "%s stream id 0x%x rp ide_id 0x%llx\n", __func__,
+		tlink->stream_id, rp_ide_id);
+	return tlink;
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
+	return;
+
+leak:
+	tdx_page_array_ctrl_leak(tlink->stream_mt);
+}
+
+DEFINE_FREE(tdx_ide_stream_delete, struct tdx_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_ide_stream_delete(_T))
+
+static struct tdx_link *tdx_ide_stream_setup(struct tdx_link *tlink)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	int ret;
+
+	struct pci_ide *ide __free(pci_ide_stream_release) =
+		pci_ide_stream_alloc(pdev);
+	if (!ide)
+		return ERR_PTR(-ENOMEM);
+
+	/* Configure IDE capability for RP & get stream_id */
+	struct tdx_link *tlink_create __free(tdx_ide_stream_delete) =
+		tdx_ide_stream_create(tlink, ide);
+	if (IS_ERR(tlink_create))
+		return tlink_create;
+
+	ide->stream_id = tlink->stream_id;
+	ret = pci_ide_stream_register(ide);
+	if (ret)
+		return ERR_PTR(ret);
+
+	/*
+	 * Configure IDE capability for target device
+	 *
+	 * Some test devices work only with DEFAULT_STREAM enabled. For
+	 * simplicity, enable DEFAULT_STREAM for all devices. A future decent
+	 * solution may be to have a quirk table to specify which devices need
+	 * DEFAULT_STREAM.
+	 */
+	ide->partner[PCI_IDE_EP].default_stream = 1;
+	pci_ide_stream_setup(pdev, ide);
+
+	/* Key Programming for RP & target device, enable IDE stream for RP */
+	struct tdx_link *tlink_program __free(tdx_ide_stream_key_stop) =
+		tdx_ide_stream_key_program(tlink);
+	if (IS_ERR(tlink_program))
+		return tlink_program;
+
+	ret = tsm_ide_stream_register(ide);
+	if (ret)
+		return ERR_PTR(ret);
+
+	/* Enable IDE stream for target device */
+	ret = pci_ide_stream_enable(pdev, ide);
+	if (ret)
+		return ERR_PTR(ret);
+
+	retain_and_null_ptr(tlink_create);
+	retain_and_null_ptr(tlink_program);
+	tlink->ide = no_free_ptr(ide);
+
+	return tlink;
+}
+
+static void tdx_ide_stream_teardown(struct tdx_link *tlink)
+{
+	tdx_ide_stream_key_stop(tlink);
+	tdx_ide_stream_delete(tlink);
+	pci_ide_stream_release(tlink->ide);
+}
+
+DEFINE_FREE(tdx_ide_stream_teardown, struct tdx_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_ide_stream_teardown(_T))
+
 static int tdx_link_connect(struct pci_dev *pdev)
 {
 	struct tdx_link *tlink = to_tdx_link(pdev->tsm);
@@ -354,7 +570,15 @@ static int tdx_link_connect(struct pci_dev *pdev)
 		return PTR_ERR(tlink_spdm);
 	}
 
+	struct tdx_link *tlink_ide __free(tdx_ide_stream_teardown) =
+		tdx_ide_stream_setup(tlink);
+	if (IS_ERR(tlink_ide)) {
+		pci_err(pdev, "fail to setup ide stream\n");
+		return PTR_ERR(tlink_ide);
+	}
+
 	retain_and_null_ptr(tlink_spdm);
+	retain_and_null_ptr(tlink_ide);
 
 	return 0;
 }
@@ -363,6 +587,7 @@ static void tdx_link_disconnect(struct pci_dev *pdev)
 {
 	struct tdx_link *tlink = to_tdx_link(pdev->tsm);
 
+	tdx_ide_stream_teardown(tlink);
 	tdx_spdm_session_teardown(tlink);
 }

---

## [27] Xu Yilun — 2025-11-17
*Subject: [PATCH v1 26/26] coco/tdx-host: Finally enable SPDM session and IDE Establishment*

The basic SPDM session and IDE functionalities are all implemented,
enable them.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 10 +++-------
 1 file changed, 3 insertions(+), 7 deletions(-)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 7f3c00f17ec7..b809f8f77206 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -885,7 +885,7 @@ static int tdx_iommu_enable_all(void)
 	return ret;
 }
 
-static int __maybe_unused tdx_connect_init(struct device *dev)
+static int tdx_connect_init(struct device *dev)
 {
 	struct tsm_dev *link;
 	int ret;
@@ -934,12 +934,8 @@ static int __maybe_unused tdx_connect_init(struct device *dev)
 
 static int tdx_host_probe(struct faux_device *fdev)
 {
-	/*
-	 * Only support TDX Connect now. More TDX features could be added here.
-	 *
-	 * TODO: do tdx_connect_init() when it is fully implemented.
-	 */
-	return 0;
+	/* Only support TDX Connect now. More TDX features could be added here. */
+	return tdx_connect_init(&fdev->dev);
 }
 
 static struct faux_device_ops tdx_host_ops = {

---

## [28] Dave Hansen — 2025-11-17
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

On 11/16/25 18:22, Xu Yilun wrote:
> +	struct page *root __free(__free_page) = alloc_page(GFP_KERNEL |
> +							   __GFP_ZERO);

Why don't you just kcalloc() this like the rest of them?

Then you won't need "mm: Add __free() support for __free_page()" either,
right?

---

## [29] Dave Hansen — 2025-11-17
*Subject: Re: [PATCH v1 07/26] x86/virt/tdx: Read TDX global metadata for TDX
 Module Extensions*

On 11/16/25 18:22, Xu Yilun wrote:
> +static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
> +{

These were OK-ish when they were being generated by a script.

Now that they're being generated by and edited by humans, they
need to actually be readable.

Can we please get this down to something that looks more like:

	MACRO(&sysinfo_ext->memory_pool_required_pages, 0x3100000100000000);
	MACRO(&sysinfo_ext->ext_required,		0x3100000100000001);

You can generate code in that macro, or generate a struct like
this:

static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
{
	int ret = 0;
	struct tdx_metadata_init[] = {
		MACRO(&sysinfo_ext->memory_pool_required_pages, 0x3100000100000000),
		MACRO(&sysinfo_ext->ext_required,		0x3100000100000001),
		{},
	};

	return tdx_...(sysinfo_ext, tdx_metadata_init);
}

and have the helper parse the structure.

But, either way, the method that's being proposed here needs to go.

---

## [30] Dave Hansen — 2025-11-17
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

I really dislike subjects like this. I honestly don't need to know what
the function's name is. The _rest_ of the subject is just words that
don't tell me _anything_ about what this patch does.

In this case, I suspect it's because the patch is doing about 15
discrete things and it's impossible to write a subject that's anything
other than some form of:

	x86/virt/tdx: Implement $FOO by making miscellaneous changes

So it's a symptom of the real disease.

On 11/16/25 18:22, Xu Yilun wrote:
> From: Zhenzhong Duan <zhenzhong.duan@intel.com>
> 

"Shared memory" is an exceedingly unfortunate term to use here. They're
TDX private memory, right?

> The number of pages required is
> published in the MEMORY_POOL_REQUIRED_PAGES field from TDH.SYS.RD. Then

This all seems backwards to me. I don't need to read the ABI names in
the changelog. I *REALLY* don't need to read the TDX documentation names
for them. If *ANYTHING* these names should be trivialy mappable to the
patch that sits below this changelog. They're not.

This changelog _should_ begin:

	Currently, TDX module memory use is relatively static. But, some
	new features (called "TDX Module Extensions") need to use memory
	more dynamically.

How much memory does this consume?

> TDH.EXT.MEM.ADD is the first user of tdx_page_array. It provides pages
> to TDX Module as control (private) pages. A tdx_clflush_page_array()

First, this talks about "control pages". But I don't know what a control
page is.

Second, these all need to be in imperative voice. Not:

	It provides pages to TDX Module as control (private) pages.

Do this:

	Provide pages to TDX Module as control (private) pages.

> TDH.EXT.MEM.ADD uses HPA_LIST_INFO as parameter so could leverage the
> 'first_entry' field to simplify the interrupted - retry flow. Host

Ahh, so this is another bit of very useful information buried deep in
this changelog.

Extensions consume memory, but they're *optional*.

> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
> index 3a3ea3fa04f2..1eeb77a6790a 100644

I'm in the first actual hunk of code and I'm lost. I don't have any idea
what the "(1ULL << TDX_VERSION_SHIFT)" is doing.

Also, bifurcating code paths is discouraged. It's much better to not
copy and paste the code and instead name your variables and change
*them* in a single path:

    u64 module_function = TDH_SYS_CONFIG;
    u64 features = 0;
    u64 timestamp = 0;

    if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_TDXCONNECT) {
	features |= TDX_FEATURES0_TDXCONNECT;
	timestamp = ktime_get_real_seconds();
	module_function |= 1ULL << TDX_VERSION_SHIFT;
    }

    ret = seamcall_prerr(module_function, &args);

This would also provide a place to say what the heck is going on with
the whole "(1ULL << TDX_VERSION_SHIFT)" thing. Just hacking it in and
open-coding makes it actually harder to comment and describe it.

>  	/* Free the array as it is not required anymore. */
>  	kfree(tdmr_pa_array);

Comments, please. "ext" can mean too many things. What does this do and
why can it fail?

> +	struct tdx_module_args args = {};
> +	u64 r;

Is this an optimization or is it functionally required?

> +	do {
> +		r = seamcall(TDH_EXT_INIT, &args);

arch/x86/virt/vmx/tdx/tdx.c has:

static void tdx_clflush_page(struct page *page)
{
        clflush_cache_range(page_to_virt(page), PAGE_SIZE);
}

Seems odd to see this here.

> +static void tdx_clflush_page_array(struct tdx_page_array *array)
> +{

I just realized the 'mempool' has nothing to do with 'struct mempool',
which makes this a rather unfortunate naming choice.

> +	struct tdx_module_args args = {
> +		.rcx = hpa_list_info_assign_raw(mempool),

This is really difficult to understand. It's not really filling a
"root", it's populating an array. The structure of the loop is also
rather non-obvious. It's doing:

	while (1) {
		fill(&array);
		tell_tdx_module(&array);
	}

Why can't it be:

	while (1)
		fill(&array);
	while (1)
		tell_tdx_module(&array);

for example?

> +		if (!nents)
> +			break;

This patch is getting waaaaaaaaaaaaaaay too long. I'd say it needs to be
4 or 5 patches, just eyeballing it.

Call be old fashioned, but I suspect the use of __free() here is atually
hurting readability.

> +static int init_tdx_ext(void)
> +{

That's a somewhat odd comment to put above an if() that doesn't return NULL.

> +	ret = enable_tdx_ext();
> +	if (ret)



> +/**
> + * tdx_enable_ext - Enable TDX module extensions.

Ahh, here's the code move.

This should be in its own patch.

---

## [31] Dave Hansen — 2025-11-17
*Subject: Re: [PATCH v1 15/26] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On 11/16/25 18:22, Xu Yilun wrote:
> +struct tdx_page_array *
> +tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages)

Please endeavor to find another way to do this. This is virtually a
copy-and-paste of the earlier code. Please refactor it in way that you
don't need the copy-and-paste.

---

## [32] Dave Hansen — 2025-11-17
*Subject: Re: [PATCH v1 00/26] PCI/TSM: TDX Connect: SPDM Session and IDE
 Establishment*

On 11/16/25 18:22, Xu Yilun wrote:
> This is a new version of the RFC [1]. It is based on Dan's
> "Link" TSM Core infrastructure [2][3] + Sean's VMXON RFC [4]. All

What are your expectations from posting this series? You cc'd me on it.
What would you like me to do with it? Is it ready to be merged? Are you
looking for reviews?

Or, is it just kinda being thrown out here so we can see what you are up to?

---

## [33] Xu Yilun — 2025-11-18
*Subject: Re: [PATCH v1 00/26] PCI/TSM: TDX Connect: SPDM Session and IDE
 Establishment*

On Mon, Nov 17, 2025 at 03:05:50PM -0800, Dave Hansen wrote:
> On 11/16/25 18:22, Xu Yilun wrote:
> > This is a new version of the RFC [1]. It is based on Dan's

It is not ready to be merged cause we still have the vmxon dependency,
but I'm still looking for reviews from TDX side so that I can get better
prepared when the dependency solved.

Thanks,
Yilun

> 
> Or, is it just kinda being thrown out here so we can see what you are up to?

---

## [34] Xu Yilun — 2025-11-18
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Mon, Nov 17, 2025 at 08:41:37AM -0800, Dave Hansen wrote:
> On 11/16/25 18:22, Xu Yilun wrote:
> > +	struct page *root __free(__free_page) = alloc_page(GFP_KERNEL |

It's feasible for this patch, see the code below.

But when I'm trying to address the copy-and-paste concern in Patch #15,
I realize the common part is the allocation of the supporting structures
(struct tdx_page_array *, struct page **, the root page), and the
different part is the allocation of data pages that TDX module requires.
So I don't think I should allocate root page along with the data pages
here.

> 
> Then you won't need "mm: Add __free() support for __free_page()" either,

mm.. But I still need this scope-based cleanup in later patch:

  [PATCH v1 22/26] coco/tdx-host: Implement SPDM session setup


--------------8<------
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index b5ad3818f222..bb62f8639040 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -148,6 +148,7 @@ struct tdx_page_array {
        unsigned int offset;
        unsigned int nents;
        struct page *root;
+       struct page **raw;
 };

 void tdx_page_array_free(struct tdx_page_array *array);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index fd622445d3d6..c41af2260475 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -360,15 +360,16 @@ void tdx_page_array_free(struct tdx_page_array *array)
        if (!array)
                return;

-       __free_page(array->root);
-       tdx_free_pages_bulk(array->nr_pages, array->pages);
-       kfree(array->pages);
+       tdx_free_pages_bulk(array->nr_pages + 1, array->raw);
+       kfree(array->raw);
        kfree(array);
 }
 EXPORT_SYMBOL_GPL(tdx_page_array_free);

 static struct tdx_page_array *tdx_page_array_alloc(unsigned int nr_pages)
 {
+       /* Need an extra root page to hold the page array HPA list */
+       unsigned int nr_pages_alloc = nr_pages + 1;
        int ret;

        if (!nr_pages)
@@ -379,23 +380,19 @@ static struct tdx_page_array *tdx_page_array_alloc(unsigned int nr_pages)
        if (!array)
                return NULL;

-       struct page *root __free(__free_page) = alloc_page(GFP_KERNEL |
-                                                          __GFP_ZERO);
-       if (!root)
-               return NULL;
-
-       struct page **pages __free(kfree) = kcalloc(nr_pages, sizeof(*pages),
-                                                   GFP_KERNEL);
-       if (!pages)
+       struct page **raw __free(kfree) = kcalloc(nr_pages_alloc, sizeof(*raw),
+                                                 GFP_KERNEL);
+       if (!raw)
                return NULL;

-       ret = tdx_alloc_pages_bulk(nr_pages, pages);
+       ret = tdx_alloc_pages_bulk(nr_pages_alloc, raw);
        if (ret)
                return NULL;

+       array->root = raw[0];
+       array->pages = raw + 1;
        array->nr_pages = nr_pages;
-       array->pages = no_free_ptr(pages);
-       array->root = no_free_ptr(root);
+       array->raw = no_free_ptr(raw);

        return no_free_ptr(array);
 }

---

## [35] Xu Yilun — 2025-11-18
*Subject: Re: [PATCH v1 07/26] x86/virt/tdx: Read TDX global metadata for TDX
 Module Extensions*

On Mon, Nov 17, 2025 at 08:52:36AM -0800, Dave Hansen wrote:
> On 11/16/25 18:22, Xu Yilun wrote:
> > +static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)

I agree. Further more, let me figure out if we could require minimum
boilerplate code when a new field is added.

> 
> Can we please get this down to something that looks more like:

I'll try and may need a seperate refactoring patch for the existing
code.

---

## [36] Xu Yilun — 2025-11-19
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

On Mon, Nov 17, 2025 at 09:34:30AM -0800, Dave Hansen wrote:
> I really dislike subjects like this. I honestly don't need to know what
> the function's name is. The _rest_ of the subject is just words that

Yes, I'll try split the patch.

> 
> On 11/16/25 18:22, Xu Yilun wrote:

Sorry, they are indeed TDX private memory. Here 'shared' means the
memory in the pool will be consumed by multiple new features but this
is TDX Module internal details that I should not ramble, especially in
TDX context.

> 
> > The number of pages required is

12800 pages.

> 
> > TDH.EXT.MEM.ADD is the first user of tdx_page_array. It provides pages

It refers to pages provided to TDX Module to hold all kinds of control
structures or metadata. E.g. TDR, TDCS, TDVPR... With TDX Connect we
have more, SPDM metadata, IDE metadata...

> 
> Second, these all need to be in imperative voice. Not:

TDX Module defines the version field in its leaf to specify updated
parameter set. The existing user is:

u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
{
	struct tdx_module_args args = {
		.rcx = vp->tdvpr_pa,
		.rdx = initial_rcx,
		.r8 = x2apicid,
	};

	/* apicid requires version == 1. */
	return seamcall(TDH_VP_INIT | (1ULL << TDX_VERSION_SHIFT), &args);
}

> 
> Also, bifurcating code paths is discouraged. It's much better to not

and the following code would be:

	args.r9 = features;
	args.r11 = timestamp;

But the version0 leaf doesn't define these inputs. So I'm wondering
if bifurcating here explains the SPEC evolution better. But anyway
I'm also good to no bifurcation.

> 
>     ret = seamcall_prerr(module_function, &args);

Yes.

> What does this do and

I would probably say "Initialize the TDX Module extension". I assume no
need to deep dive into TDX Module internal details, and the SPEC doesn't
reveal them.

> why can it fail?

I would say "Fail when TDH.EXT.INIT is required but returns error on
execution." This is the only thing VMM can see, we don't (have to)
know what's inside.

> 
> > +	struct tdx_module_args args = {};

It is functionally required. When ext_required is 0, it means
no need TDH.EXT.INIT to enable TDX Module Extension, it is already
enabled.

> 
> > +	do {

Maybe tdx_ext_mem?

> 
> > +	struct tdx_module_args args = {

It is populating the root page with part (512 pages at most) of the array.
So is it better name the function tdx_page_array_populate_root()?

> rather non-obvious. It's doing:
> 

There is some explanation in Patch #6:

 4. Note the root page contains 512 HPAs at most, if more pages are
   required, refilling the tdx_page_array is needed.

 - struct tdx_page_array *array = tdx_page_array_alloc(nr_pages);
 - for each 512-page bulk
   - tdx_page_array_fill_root(array, offset);
   - seamcall(TDH_XXX_ADD, array, ...);

> 
> Why can't it be:

The consideration is, no need to create as much supporting
structures (struct tdx_page_array *, struct page ** and root page) for
each 512-page bulk. Use one and re-populate it in loop is efficient.

> 
> for example?

I agree.

> 
> Call be old fashioned, but I suspect the use of __free() here is atually

Ah.. Dan, could you help me here? :)   I'm infected by Dan and truly
start to love scope-based cleanup.

> 
> > +static int init_tdx_ext(void)

I meant to explain why using IS_ERR instead of IS_ERR_OR_NULL. I can
impove the comment.

> 
> > +	ret = enable_tdx_ext();

Yes.

> 
>

---

## [37] Dave Hansen — 2025-11-18
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

On 11/18/25 09:14, Xu Yilun wrote:
....>>> The extension initialization uses the new TDH.EXT.MEM.ADD and
>>> TDX.EXT.INIT seamcalls. TDH.EXT.MEM.ADD add pages to a shared memory
>>> pool for extensions to consume.
... and you'll find a better term in the next revision. Right?

...>> How much memory does this consume?
> 
> 12800 pages.

Oof. That's more than I expected and it's also getting up to the amount
that you don't want to just eat without saying seomthing about it.

Could you please at least dump a pr_info() out about how much memory
this consumes?

>>> TDH.EXT.MEM.ADD is the first user of tdx_page_array. It provides pages
>>> to TDX Module as control (private) pages. A tdx_clflush_page_array()

Please *say* that. Explain how existing TDX metadata consumes memory and
how this new mechanism is different.

BTW... Do you see how I'm trimming context as I reply? Could you please
endeavor to do the same?

>>> @@ -1251,7 +1254,14 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
>>>  	args.rcx = __pa(tdmr_pa_array);

OK, so there's a single existing user with this thing open coded.

You're adding a second user, so you just copied and pasted the existing
code. Is there a better way to do this? For instance, can we just pass
the version number to *ALL* seamcall()s?



...>> This is really difficult to understand. It's not really filling a
>> "root", it's populating an array. The structure of the loop is also
> 

That's getting a bit verbose.

>> rather non-obvious. It's doing:
>>

That doesn't really help me, or future reviewers.

>  4. Note the root page contains 512 HPAs at most, if more pages are
>    required, refilling the tdx_page_array is needed.

Great! That is useful information to have here, in the code.

>> Why can't it be:
>>

Huh? What is it efficient for? Are you saving a few pages of _temporary_
memory?

I'm not following at all.

>>> +static int init_tdx_ext(void)
>>> +{

I'd kinda rather the code was improved. Why cram everything into a
pointer if you don't need to. This would be just fine, no?

	ret = tdx_ext_mempool_setup(&mempool);
	if (ret)
		return ret;

---

## [38] Dave Hansen — 2025-11-18
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

On 11/16/25 18:22, Xu Yilun wrote:
...> +	struct tdx_page_array *array __free(kfree) = kzalloc(sizeof(*array),
> +							     GFP_KERNEL);
> +	if (!array)

I just reworked this to use normal goto's. It looks a billion times
better. Please remove all these __free()'s unless you have specific
evidence that they make the code better.

Maybe I'm old fashioned, but I don't see anything wrong with:

static struct tdx_pglist *tdx_pglist_alloc(unsigned int nr_pages)
{
        struct tdx_page_array *array = NULL;
        struct page **pages = NULL;
        struct page *root = NULL;
        int ret;

        if (!nr_pages)
                return NULL;

        array = kzalloc(sizeof(*array), GFP_KERNEL);
        if (!array)
                goto out_free;

        root = kzalloc(PAGE_SIZE, GFP_KERNEL);
        if (!root)
                goto out_free;

        pages = kcalloc(nr_pages, sizeof(*pages), GFP_KERNEL);
        if (!pages)
                goto out_free;

        ret = tdx_alloc_pages_bulk(nr_pages, pages);
        if (ret)
                goto out_free;

        array->nr_pages	= nr_pages;
        array->pages	= pages;
        array->root	= root;

        return array;

out_free:
        kfree(array);
        kfree(root);
        kfree(pages);

        return NULL;
}

---

## [39] Dave Hansen — 2025-11-19
*Subject: Re: [PATCH v1 00/26] PCI/TSM: TDX Connect: SPDM Session and IDE
 Establishment*

Any chance we could use english in subjects? Isn't this something more
along the lines of:

	PCI: Secure Device Passthrough For TDX, initial support

I mean, "TDX Connect" is a pure marketing term that doesn't tell us
much. Right?

I'll also say that even the beginning of the cover letter doesn't help a
lot. Plain, acronym-free language when possible would be much
appreciated there and across this series.

For instance, there's not even a problem statement to be seen. I asked
ChatGPT: "write me a short, three sentence plain language paragraph
about why TDX Connect is needed on top of regular TDX"

	Regular TDX keeps a guest’s memory safe but leaves the path to
	physical devices exposed to the host. That means the host could
	spoof a device, alter configuration, or watch DMA traffic. TDX
	Connect closes that gap by letting the guest verify real devices
	and encrypt the I/O link so the host can’t interfere.

That would be a great way to open a cover letter.

On 11/16/25 18:22, Xu Yilun wrote:
>  arch/x86/virt/vmx/tdx/tdx.c                   | 740 ++++++++++++-
>  arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  32 +

Let me know if anyone feels differently, but I really think the "TDX
Host Extensions" need to be reviewed as a different patch set. Sure,
they are a dependency for "TDX Connect". But, in the end, the host
extension enabling does not interact at *ALL* with the later stuff. It's
purely:

	* Ask the TDX module how much memory it wants
	* Feed it with that much memory

... and voila! The fancy new extension works. Right?

But can we break this up, please?

---

## [40] dan.j.williams@intel.com — 2025-11-19
*Subject: Re: [PATCH v1 00/26] PCI/TSM: TDX Connect: SPDM Session and IDE
 Establishment*

Dave Hansen wrote:
> Any chance we could use english in subjects? Isn't this something more
> along the lines of:

Note that I generated that subject for this series during the RFC.
Yilun, apologies for setting you up for this feedback.

In retrospect, a better subject would be:

"PCI/TSM: PCIe Link Encryption Establishment via TDX platform services"

Most of the plain English description of this topic has gone through
multiple rounds of review in the core series to introduce and
re-introduce these acronyms [1].

This TDX series is one of many low-level architecture specific drivers,
and no, this phase of the enablement does not touch passthrough. It only
implements initial link protection details which are this acronym soup
that the PCI community at least is slowly learning to speak. It is a
pre-requisite for passthrough work.

The ordering of the enabling staging is detailed here [2].

I will add more decoder ring to that. At some point the coarse English
breaks down as the need talk about fine details picks up, i.e.  specific
acronyms used by the specification need to be invoked. Granted, maybe
not in the subject.

[1]: http://lore.kernel.org/20251031212902.2256310-1-dan.j.williams@intel.com
[2]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/tree/Documentation/driver-api/pci/tsm.rst?h=staging

> I'll also say that even the beginning of the cover letter doesn't help a
> lot. Plain, acronym-free language when possible would be much

None of that is implemented in this series.

> That would be a great way to open a cover letter.

I think the break down is not reminding folks that this is a low-level
incremental implementation supporting core infrastructure that has
described the "first phase" problem on behalf of a class of these "TSM"
drivers that will follow. English is needed, yes, but I do not think we
need each submission to recreate an intro essay from the core
submission. Yes, we lost the link in this case, and that is my fault,
not Yilun's.

> On 11/16/25 18:22, Xu Yilun wrote:
> >  arch/x86/virt/vmx/tdx/tdx.c                   | 740 ++++++++++++-

I feel differently.

> 	* Ask the TDX module how much memory it wants
> 	* Feed it with that much memory

Right, minor implementation detail of new ABIs. What does a "TDX
Host Extensions" patch set do that does not introduce new ABI? Linux
should not merge a patch that gives resources to the TDX Module
independent of a intent to use the ABIs.

---

## [41] Dave Hansen — 2025-11-19
*Subject: Re: [PATCH v1 00/26] PCI/TSM: TDX Connect: SPDM Session and IDE
 Establishment*

On 11/19/25 07:50, dan.j.williams@intel.com wrote:
> "PCI/TSM: PCIe Link Encryption Establishment via TDX platform services"

That is, indeed, much better!

>> On 11/16/25 18:22, Xu Yilun wrote:
>>>  arch/x86/virt/vmx/tdx/tdx.c                   | 740 ++++++++++++-

I was looking at the "merge" and "review" as different steps of the
process. I totally agree we shouldn't send "TDX Host Extensions" to
Linus without an in-tree user ready to use it.

But I do think there's some value in breaking this series up into pieces
that are relatively unrelated, even if there is a functional dependency
between them. My gut says that would be best done with two or more
actually separate postings. But, I'd also be quite open to reworking
this series into two distinct, logical parts.

like:

	Patches   1-4: New mm support and cleanups
	Patches   5-9: TDX Module Extensions, including "gifted" memory
	Patches 10-12: tdx_host device support
	Patches 12-99: KVM and/or PCI gunk Dave can mostly ignore :)

But the important part is considering what the logical pieces are,
breaking up the series into those chapters, and telling the story of
this series be told by putting them in order.

---

## [42] dan.j.williams@intel.com — 2025-11-19
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

Dave Hansen wrote:
> On 11/16/25 18:22, Xu Yilun wrote:
> ...> +	struct tdx_page_array *array __free(kfree) = kzalloc(sizeof(*array),

I think this s/alloc_page/kcalloc/ is the bulk of the improvement, that
is a good change I missed. Otherwise, this version of the function is
longer, and I feel the use of gotos makes this function less
maintainable longer term. Future refactors or feature additions need to
be careful.

Please document that tip prefers that goto be used in cases where a
single goto target can be used.

---

## [43] Dave Hansen — 2025-11-19
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

On 11/19/25 08:20, dan.j.williams@intel.com wrote:
> Please document that tip prefers that goto be used in cases where a
> single goto target can be used.

I don't think it's that hard and fast of a rule. It's really just a more
general: use the best tool for the job. For instance, if your line of
code was already on the long side, the additional __free(foo) might be
the straw that breaks the camel's back.

So it all depends.

In this case, we have very linear code flow, very long lines, and quite
uniform allocator use (they can all be kfree()). That tips the scales
squarely in the direction of goto.

Dan, you were also concerned about the mental load of ensuring that the
error goto code frees objects in reverse allocation order. I certainly
understand that inclination.

But there's already code that takes that allocation order into account.
It's also going to be in this patch whether or not __free() is utilized:

> +void tdx_page_array_free(struct tdx_page_array *array)
> +{
Ideally, we'd be able to define the free ordering requirements in a
single bit of code and use it in both paths.

---

## [44] dan.j.williams@intel.com — 2025-11-19
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

Dave Hansen wrote:
> On 11/19/25 08:20, dan.j.williams@intel.com wrote:
> > Please document that tip prefers that goto be used in cases where a

In the absence of near term future use cases that will violate the
uniform allocator observation, yes, today's needs can rely on a single
error exit path.

For clarity for Yilun, be circumspect on scope-based-cleanup usage for
arch/x86/virt/, but for TSM driver bits in drivers/virt/, do feel free
to continue aggressive avoidance of goto.

> But there's already code that takes that allocation order into account.
> It's also going to be in this patch whether or not __free() is utilized:

__free() does not effect object destructors like this, only the
constructor early error exits. It would be nice to have uniformity, but
that is more something that devres offers rather than
scope-based-cleanup. Devres is not appropriate for this path.

So yes, some mental load needs to be spent on validating the order of
the destructor path.

---

## [45] Xu Yilun — 2025-11-20
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

On Tue, Nov 18, 2025 at 10:32:13AM -0800, Dave Hansen wrote:
> On 11/18/25 09:14, Xu Yilun wrote:
> ....>>> The extension initialization uses the new TDH.EXT.MEM.ADD and

Yes, I think just "memory pool" is enough.

> 
> ...>> How much memory does this consume?

Sure.

> 
> >>> TDH.EXT.MEM.ADD is the first user of tdx_page_array. It provides pages

Yes.

Existing ways to provide an array of metadata pages to TDX Module
varies:

 1. Assign each HPA for each SEAMCALL register.
 2. Call the same seamcall multiple times.
 3. Assign the PA of HPA-array in one register and the page number in
    another register.

TDX Module defines new interfaces trying to unify the page array
provision. It is similar to the 3rd method. The new objects HPA_ARRAY_T
and HPA_LIST_INFO need a 'root page' which contains a list of HPAs.
They collapse the HPA of the root page and the number of valid HPAs
into a 64 bit raw value for one SEAMCALL parameter.

I think these words should be in:

  x86/virt/tdx: Add tdx_page_array helpers for new TDX Module objects
> 
> BTW... Do you see how I'm trimming context as I reply? Could you please

Yes.

> 
> >>> @@ -1251,7 +1254,14 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,

I think it may be too heavy. We have a hundred SEAMCALLs and I expect
few needs version 1. I actually think v2 is nothing different from a new
leaf. How about something like:

--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD         41
 #define TDH_VP_WR                      43
 #define TDH_SYS_CONFIG                 45
+#define TDH_SYS_CONFIG_V1              (TDH_SYS_CONFIG | (1ULL << TDX_VERSION_SHIFT))

And if a SEAMCALL needs export, add new tdh_foobar() helper. Anyway
the parameter list should be different.

> 
> 

tdx_page_array_populate()

> 
> >> rather non-obvious. It's doing:

In this case yes, cause no way to reclaim TDX Module EXT required pages.
But when reclaimation is needed, will hold these supporting structures
long time.

Also I want the tdx_page_array object itself not been restricted by 512
pages, so tdx_page_array users don't have to manage an array of array.

> 
> I'm not following at all.

It's good.

The usage of pointer is still about __free(). In order to auto-free
something, we need an object handler for something. I think this is a
more controversial usage of __free() than pure allocation. We setup
something and want auto-undo something on failure.

Thanks,
Yilun

---

## [46] Xu Yilun — 2025-11-20
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Wed, Nov 19, 2025 at 08:20:15AM -0800, dan.j.williams@intel.com wrote:
> Dave Hansen wrote:
> > On 11/16/25 18:22, Xu Yilun wrote:

s/alloc_page/kzalloc, is it?

Yes, I agree. I almost missed the change here.

---

## [47] Xu Yilun — 2025-11-20
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

> For clarity for Yilun, be circumspect on scope-based-cleanup usage for
> arch/x86/virt/,

Yes. I think I should drop __free() here. But allow me to keep the kAPIs
definitions like:

 void tdx_page_array_free(struct tdx_page_array *array);
 DEFINE_FREE(tdx_page_array_free, struct tdx_page_array *, if (_T) tdx_page_array_free(_T))

So I can use __free() elsewhere.

> but for TSM driver bits in drivers/virt/, do feel free
> to continue aggressive avoidance of goto.

Yes.

---

## [48] Dave Hansen — 2025-11-20
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

On 11/19/25 22:09, Xu Yilun wrote:
> On Tue, Nov 18, 2025 at 10:32:13AM -0800, Dave Hansen wrote:
...
>> Please *say* that. Explain how existing TDX metadata consumes memory and
>> how this new mechanism is different.

That's not quite what I was hoping for.

I want an overview of how this new memory fits into the overall scheme.
I'd argue that these "control pages" are most similar to the PAMT:
There's some back-and-forth with the module about how much memory it
needs, the kernel allocates it, hands it over, and never gets it back.

That's the level that this needs to be presented at: a high-level
logical overview.

...> I think it may be too heavy. We have a hundred SEAMCALLs and I expect
> few needs version 1. I actually think v2 is nothing different from a new
> leaf. How about something like:

I'd need quite a bit of convincing that this is the right way.

What is the scenario where there's a:

	TDH_SYS_CONFIG_V1
and
	TDH_SYS_CONFIG_V2

in the tree at the same time?

Second, does it hurt to pass the version along with other calls, like
... (naming a random one) ... TDH_PHYMEM_PAGE_WBINVD ?

Even if we did this, we wouldn't copy and paste "(1ULL <<
TDX_VERSION_SHIFT)" all over the place, right? We'd create a more
concise, cleaner macro and then use it everywhere. Right?
	
>>>> rather non-obvious. It's doing:
>>>>

I asked in my last message, but perhaps it was missed: Could you please
start clearing irrelevant context in your replies. Like that hunk ^

>>>> Why can't it be:
>>>>

I suspect we're not really talking about the same thing here.

In any case, I'm not a super big fan of how tdx_ext_mempool_setup() is
written. Can you please take another pass at it and try to simplify it
and make it easier to follow?

This would be a great opportunity to bring in some of your colleagues to
take a look. You can solicit them for suggestions.

>>>>> +static int init_tdx_ext(void)
>>>>> +{
I'm not sure what you are trying to say here. By saying "It's good" are
you agreeing that my suggested structure is good and that you will use
it? Or are you saying that the original structure is good?

Second, what is an "object handler"? Are you talking about the function
that is pointed to by __free()?

Third, are you saying that the original code structure is somehow
connected to __free()? I thought that all of these were logically
equivalent:

	void *foo __free(foofree) = alloc_foo();

	void *foo __free(foofree) = NULL:
	foo = alloc_foo();

	void *foo __free(foofree) = NULL;
	populate_foo(&foo);

Is there something special about doing the variable assignment at the
variable declaration spot?

---

## [49] dan.j.williams@intel.com — 2025-11-20
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

Dave Hansen wrote:
[..]
> Third, are you saying that the original code structure is somehow
> connected to __free()? I thought that all of these were logically

On this topic I argue in cleanup.h that the:

   void *foo __free(foofree) = alloc_foo();

...form, should be preferred. The NULL initialization form potentially
destroys the first-in-last-out ordering of cleanup callbacks.

Linus mentions here [1] though that it is not a hard and fast rule. That
was part of the rationale for documenting the preference in cleanup.h,
but not in coding-style, nor in checkpatch.pl [2].

[1]: http://lore.kernel.org/CAHk-=whPZoi03ZwphxiW6cuWPtC3nyKYS8_BThgztCdgPWP1WA@mail.gmail.com
[2]: http://lore.kernel.org/769268a5035b5a711a375591c25d48d077b46faa.camel@perches.com

---

## [50] Xu Yilun — 2025-11-21
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

> I want an overview of how this new memory fits into the overall scheme.
> I'd argue that these "control pages" are most similar to the PAMT:

OK. I can split out a patch dedicate to the memory feeding, and put
the overview in changelog.


x86/virt/tdx: Add extra memory to TDX Module for Extentions

Currently, TDX module memory use is relatively static. But, some new
features (called "TDX Module Extensions") need to use memory more
dynamically. While 'static' here means the kernel provides necessary
amount of memory to TDX Module for its initialization, 'dynamic' means
extra memory be added after TDX Module initialization and before the
first optional usage of TDX Module Extension. So add a new memory
feeding process backed by a new SEAMCALL TDH.EXT.MEM.ADD.

The process is mostly the same as adding PAMT. The kernel queries TDX
Module how much memory needed, allocates it, hands it over and never
gets it back.

more details...

For now, TDX Module Extensions consume quite large amount of memory
(12800 pages), print this readout value on TDX Module Extentions
initialization.

> 
> ...> I think it may be too heavy. We have a hundred SEAMCALLs and I expect

Sorry for typo, there is no v2 yet.

> > leaf. How about something like:
> > 

I assume you mean TDH_SYS_CONFIG & TDH_SYS_CONFIG_V1.

If you want to enable optional features via this seamcall, you must use
v1, otherwise v0 & v1 are all good. Mm... I suddenly don't see usecase
they must co-exist. Unconditionally use v1 is fine. So does TDH_VP_INIT.

Does that mean we don't have to keep versions, always use the latest is
good? (Proper Macro to be used...)

 -#define TDH_SYS_CONFIG                 45
 +#define TDH_SYS_CONFIG                 (45 | (1ULL << TDX_VERSION_SHIFT))

> 
> Second, does it hurt to pass the version along with other calls, like

I see no runtime hurt, just an extra zero parameter passed around.

And version change always goes with more parameters, if we add version
parameter, it looks like:

 u64 tdh_phymem_page_wbinvd_tdr(int version, struct tdx_td *td, int new_param1, int new_param2);

For readability, I prefer the following, they provide clear definitions:

 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_tdr_1(struct tdx_td *td, int new_param1, int new_param2);


But I hope eventually we don't have to keep versions, then we don't have to choose:

 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td, int new_param1, int new_param2);


> 
> Even if we did this, we wouldn't copy and paste "(1ULL <<

Sure. Will do.

...

> >>>> 	while (1)
> >>>> 		fill(&array);

Sorry, I went through the history again and thought I got off track from
here. I was trying to explain why I choose to let struct tdx_page_array
not restricted by 512 pages. But that's not your question.

For your question why:

  while (1) {
        fill(&array);
        tell_tdx_module(&array);
  }

not:

  while (1)
        fill(&array);
  while (1)
        tell_tdx_module(&array);

The TDX Module can only accept one root page (i.e. 512 HPAs at most), while
struct tdx_page_array contains the whole EXT memory (12800 pages). So we
can't populate all pages into one root page then tell TDX Module. We need to
populate one batch, tell tdx module, then populate the next batch, tell
tdx module...

I assume when you said "Great! That is useful information to have here,
in the code." The concern was solved.

> I suspect we're not really talking about the same thing here.

Sorry I deviated from the question.

> 
> In any case, I'm not a super big fan of how tdx_ext_mempool_setup() is

Yes. I plan to remove the __free(). This gives the chance to re-organize
things from the start.

> 
> This would be a great opportunity to bring in some of your colleagues to

Yes.

...

> >> I'd kinda rather the code was improved. Why cram everything into a
> >> pointer if you don't need to. This would be just fine, no?

I mean your suggestion is good. I'll use it since I will remove
__free().

> 
> Second, what is an "object handler"? Are you talking about the function

Sorry, should be object handle, it refers to the pointer, the
struct tdx_page_array *mempool

> 
> Third, are you saying that the original code structure is somehow

Yes.

> I thought that all of these were logically
> equivalent:

Yes, Dan explained it.

---

## [51] Dave Hansen — 2025-11-21
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

On 11/21/25 04:54, Xu Yilun wrote:
...
> For now, TDX Module Extensions consume quite large amount of memory
> (12800 pages), print this readout value on TDX Module Extentions

Overall, the description is looking better, thanks!

A few more nits, though. Please don't talk about things in terms of
number of pages. Just give the usage in megabytes.


>>> --- a/arch/x86/virt/vmx/tdx/tdx.h
>>> +++ b/arch/x86/virt/vmx/tdx/tdx.h

Sure. But I wasn't being that literal about it. My point was whether we
need two macros for two simultaneous uses of the same seamcall.

> If you want to enable optional features via this seamcall, you must use
> v1, otherwise v0 & v1 are all good. Mm... I suddenly don't see usecase

That's my theory: we don't need to keep versions.

>> Second, does it hurt to pass the version along with other calls, like
>> ... (naming a random one) ... TDH_PHYMEM_PAGE_WBINVD ?

Sure, but that's not happening today. So for TDX_FEATURES0_TDXCONNECT at
least, config_tdx_module() doesn't change.

> The TDX Module can only accept one root page (i.e. 512 HPAs at most), while
> struct tdx_page_array contains the whole EXT memory (12800 pages). So we

That is, indeed, the information that I was looking for. Can you please
ensure that makes it into code comments?

---

## [52] Dave Hansen — 2025-11-21
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

On 11/21/25 07:15, Dave Hansen wrote:
> On 11/21/25 04:54, Xu Yilun wrote:
> ...

Oh, and please at least have a discussion with the memory management
folks about consuming this amount of memory forever. I think it's quite
possible they will prefer it be allocated in a way other than thousands
of plain old allocations.

For example, imagine memory was fragmented and those 12800 pages came
from 12,800 different 2M regions. Well, now you've got ~50GB of memory
that is _permanently_ fragmented and will never be able to satisfy a 2M
allocation.

You might get an answer that it's better to do a small number of
max-size buddy allocations than a large number of PAGE_SIZE allocations.

---

## [53] Xu Yilun — 2025-11-24
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

On Fri, Nov 21, 2025 at 07:38:03AM -0800, Dave Hansen wrote:
> On 11/21/25 07:15, Dave Hansen wrote:
> > On 11/21/25 04:54, Xu Yilun wrote:

Loop in mm folks.

Hi mm folks, for Intel TDX (Trust Domain Extensions) feature, there is
a requirement to donate quite a number of pages (12800 x 4K = 50MB for
now) to TDX firmware (known as TDX Module) for its initialization. These
pages will never be revoked cause the TDX Module initialization is a one
way path.

The TDX Module doesn't require these pages be physically contiguous, and
the patches [1][2] in this series [3] does PAGE_SIZE allocation. But as
mentioned by Dave, the donation may _permanently_ fragment regions, stop
them from 2M huge page allocation. In worst case, 12800 x 2MB = 25GB
memory region.

So is order based buddy allocation a better choice? I believe so.  And if
that fails, should we fall back to PAGE_SIZE allocation? Or PAGE_SIZE
allocation should be a hard no in this _permanent_ donation case?

[1]: https://lore.kernel.org/linux-coco/20251117022311.2443900-7-yilun.xu@linux.intel.com/
[2]: https://lore.kernel.org/linux-coco/20251117022311.2443900-9-yilun.xu@linux.intel.com/
[3]: https://lore.kernel.org/linux-coco/20251117022311.2443900-1-yilun.xu@linux.intel.com/

Thanks,
Yilun

---

## [54] Xu Yilun — 2025-11-24
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

> A few more nits, though. Please don't talk about things in terms of
> number of pages. Just give the usage in megabytes.

Yes.

...

> >  -#define TDH_SYS_CONFIG                 45
> >  +#define TDH_SYS_CONFIG                 (45 | (1ULL << TDX_VERSION_SHIFT))

Good to know.

...

> > The TDX Module can only accept one root page (i.e. 512 HPAs at most), while
> > struct tdx_page_array contains the whole EXT memory (12800 pages). So we

Yes.

---

## [55] Xu Yilun — 2025-12-08
*Subject: Re: [PATCH v1 08/26] x86/virt/tdx: Add tdx_enable_ext() to enable of
 TDX Module Extensions*

> >>> --- a/arch/x86/virt/vmx/tdx/tdx.h
> >>> +++ b/arch/x86/virt/vmx/tdx/tdx.h

Sorry, I found we have to keep versions for backward compatibility. The
old TDX Modules reject v1.

Here is my change, including TDH_SYS_CONFIG & TDH_VP_INIT. Will break
them down in formal patches.

-----8<-------

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 3b4d7cb25164..1e0a174dfb57 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1330,6 +1330,7 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
                                    u64 global_keyid)
 {
        struct tdx_module_args args = {};
+       u64 seamcall_fn = TDH_SYS_CONFIG;
        u64 *tdmr_pa_array;
        size_t array_sz;
        int i, ret;
@@ -1354,7 +1355,14 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
        args.rcx = __pa(tdmr_pa_array);
        args.rdx = tdmr_list->nr_consumed_tdmrs;
        args.r8 = global_keyid;
-       ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
+
+       if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_TDXCONNECT) {
+               args.r9 |= TDX_FEATURES0_TDXCONNECT;
+               args.r11 = ktime_get_real_seconds();
+               seamcall_fn = TDH_SYS_CONFIG_V1;
+       }
+
+       ret = seamcall_prerr(seamcall_fn, &args);

        /* Free the array as it is not required anymore. */
        kfree(tdmr_pa_array);
@@ -2153,7 +2166,7 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
        };

        /* apicid requires version == 1. */
-       return seamcall(TDH_VP_INIT | (1ULL << TDX_VERSION_SHIFT), &args);
+       return seamcall(TDH_VP_INIT_V1, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_vp_init);

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 4370d3d177f6..835ea2f08fe2 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -2,6 +2,7 @@
 #ifndef _X86_VIRT_TDX_H
 #define _X86_VIRT_TDX_H

+#include <linux/bitfield.h>
 #include <linux/bits.h>

 /*
@@ -11,6 +12,18 @@
  * architectural definitions come first.
  */

+/*
+ * SEAMCALL leaf:
+ *
+ * Bit 15:0    Leaf number
+ * Bit 23:16   Version number
+ */
+#define SEAMCALL_LEAF                  GENMASK(15, 0)
+#define SEAMCALL_VER                   GENMASK(23, 16)
+
+#define SEAMCALL_LEAF_VER(l, v)                (FIELD_PREP(SEAMCALL_LEAF, l) | \
+                                        FIELD_PREP(SEAMCALL_VER, v))
+
 /*
  * TDX module SEAMCALL leaf functions
  */
@@ -31,7 +44,7 @@
 #define TDH_VP_CREATE                  10
 #define TDH_MNG_KEY_FREEID             20
 #define TDH_MNG_INIT                   21
-#define TDH_VP_INIT                    22
+#define TDH_VP_INIT_V1                 SEAMCALL_LEAF_VER(22, 1)
 #define TDH_PHYMEM_PAGE_RDMD           24
 #define TDH_VP_RD                      26
 #define TDH_PHYMEM_PAGE_RECLAIM                28
@@ -46,14 +59,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD         41
 #define TDH_VP_WR                      43
 #define TDH_SYS_CONFIG                 45
-
-/*
- * SEAMCALL leaf:
- *
- * Bit 15:0    Leaf number
- * Bit 23:16   Version number
- */
-#define TDX_VERSION_SHIFT              16
+#define TDH_SYS_CONFIG_V1              SEAMCALL_LEAF_VER(TDH_SYS_CONFIG, 1)

 /* TDX page types */
 #define        PT_NDA          0x0

---

## [56] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 03/26] coco/tdx-host: Support Link TSM for TDX host*

On Mon, 17 Nov 2025 10:22:47 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> Register a Link TSM instance to support host side TSM operations for
> TDISP, when the TDX Connect support bit is set by TDX Module in
All very standard looking which is just what we want to see!

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [57] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 01/26] coco/tdx-host: Introduce a "tdx_host" device*

On Mon, 17 Nov 2025 10:22:45 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> From: Chao Gao <chao.gao@intel.com>
> 
LGTM
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [58] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 05/26] mm: Add __free() support for __free_page()*

On Mon, 17 Nov 2025 10:22:49 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> Allow for the declaration of struct page * variables that trigger
> __free_page() when they go out of scope.

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

> ---
>  include/linux/gfp.h | 1 +

---

## [59] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Mon, 17 Nov 2025 10:22:50 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> Add struct tdx_page_array definition for new TDX Module object
> types - HPA_ARRAY_T and HPA_LIST_INFO. They are used as input/output

One trivial comment below. I'm not going to look into tdx specifics
enough to do a detailed review of this patch.

> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> index 09c766e60962..9a5c32dc1767 100644

> +static bool tdx_page_array_validate_release(struct tdx_page_array *array,
> +					    unsigned int offset,

page_address() returns a void * so the cast here isn't needed and (to me
at least) doesn't add value from readability point of view.

I haven't checked later patches, but if this code doesn't change to use
entries outside this scope then,
		u64 *entries = page_address(array->root);
would be nice to restrict the scope and make the type here immediately
visible.

> +		for (i = 0; i < nents; i++) {
> +			struct page *page = array->pages[offset + i];

---

## [60] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 10/26] acpi: Add KEYP support to fw_table parsing*

On Mon, 17 Nov 2025 10:22:54 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> From: Dave Jiang <dave.jiang@intel.com>
> 

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [61] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 12/26] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

On Mon, 17 Nov 2025 10:22:56 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> From: Lu Baolu <baolu.lu@linux.intel.com>
> 
Hi,
One comment inline.

Thanks,

Jonathan

> diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
> index a54934c0536f..e9d65b26ad64 100644
As below. Be consistent on int vs bool as otherwise the subtle use of -1 is very confusing.
> +
> +	return 0;

This is flipping between an int and a bool which seems odd.
I'd stick to an integer then make it a bool only at return.

> +	ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
> +				    keyp_config_unit_tvm_usable, &tvm_usable);

---

## [62] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 12/26] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

On Mon, 17 Nov 2025 10:22:56 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> From: Lu Baolu <baolu.lu@linux.intel.com>
> 
Missing sign off of the person who 'handled' the patch by sending it to
the list in this series.  i.e. Xu Yilun.

One comment inline.

Thanks,

Jonathan

> diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
> index a54934c0536f..e9d65b26ad64 100644
As below. Be consistent on int vs bool as otherwise the subtle use of -1 is very confusing.
> +
> +	return 0;

This is flipping between an int and a bool which seems odd.
I'd stick to an integer then make it a bool only at return.

> +	ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
> +				    keyp_config_unit_tvm_usable, &tvm_usable);

---

## [63] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 11/26] iommu/vt-d: Cache max domain ID to avoid
 redundant calculation*

On Mon, 17 Nov 2025 10:22:55 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> From: Lu Baolu <baolu.lu@linux.intel.com>
> 
Missing sign off of the last person to handle the patch. Xu Yilun.
That makes this unmergeable :(

---

## [64] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 14/26] mm: Add __free() support for folio_put()*

On Mon, 17 Nov 2025 10:22:58 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> Allow for the declaration of struct folio * variables that trigger
> folio_put() when they go out of scope.

Seems like a reasonable addition to me.
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

> +
>  /**

---

## [65] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 23/26] coco/tdx-host: Parse ACPI KEYP table to init
 IDE for PCI host bridges*

On Mon, 17 Nov 2025 10:23:07 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> Parse the KEYP Key Configuration Units (KCU), to decide the max IDE
> streams supported for each host bridge.
LGTM
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [66] Jonathan Cameron — 2025-12-19
*Subject: Re: [PATCH v1 26/26] coco/tdx-host: Finally enable SPDM session and
 IDE Establishment*

On Mon, 17 Nov 2025 10:23:10 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> The basic SPDM session and IDE functionalities are all implemented,
> enable them.
Hard to disagree with this one :)
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [67] Xu Yilun — 2025-12-23
*Subject: Re: [PATCH v1 05/26] mm: Add __free() support for __free_page()*

On Fri, Dec 19, 2025 at 11:22:20AM +0000, Jonathan Cameron wrote:
> On Mon, 17 Nov 2025 10:22:49 +0800
> Xu Yilun <yilun.xu@linux.intel.com> wrote:

Sorry I will drop this patch on v2 cause I'll use

  kzalloc(PAGE_SIZE, ...) for all single page allocation in this series.

Thanks,
Yilun

---

## [68] Xu Yilun — 2025-12-23
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

> > +static bool tdx_page_array_validate_release(struct tdx_page_array *array,
> > +					    unsigned int offset,

These casts disappear during the refactoring from alloc_page() to
kzalloc(PAGE_SIZE, ...) for my v2.

> 
> I haven't checked later patches, but if this code doesn't change to use

Yes. Also for int i.

Thanks,
Yilun

> 
> > +		for (i = 0; i < nents; i++) {

---

## [69] Xu Yilun — 2025-12-23
*Subject: Re: [PATCH v1 11/26] iommu/vt-d: Cache max domain ID to avoid
 redundant calculation*

On Fri, Dec 19, 2025 at 11:53:09AM +0000, Jonathan Cameron wrote:
> On Mon, 17 Nov 2025 10:22:55 +0800
> Xu Yilun <yilun.xu@linux.intel.com> wrote:

Will add my Sign off in v2, thanks.

---

## [70] Xu Yilun — 2025-12-23
*Subject: Re: [PATCH v1 12/26] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

On Fri, Dec 19, 2025 at 11:51:15AM +0000, Jonathan Cameron wrote:
> On Mon, 17 Nov 2025 10:22:56 +0800
> Xu Yilun <yilun.xu@linux.intel.com> wrote:

I agree. My change below:

> 
> > +	ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,

-----------8<----------------------

diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index 645b72270967..fd14de8775b6 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -1041,7 +1041,7 @@ static int keyp_config_unit_tvm_usable(union acpi_subtable_headers *header,
        int *tvm_usable = arg;

        if (acpi_cu->flags & ACPI_KEYP_F_TVM_USABLE)
-               *tvm_usable = true;
+               *tvm_usable = 1;

        return 0;
 }
@@ -1053,15 +1053,15 @@ static bool platform_is_tdxc_enhanced(void)

        /* only need to parse once */
        if (tvm_usable != -1)
-               return tvm_usable;
+               return !!tvm_usable;

-       tvm_usable = false;
+       tvm_usable = 0;
        ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
                                    keyp_config_unit_tvm_usable, &tvm_usable);
        if (ret < 0)
-               tvm_usable = false;
+               tvm_usable = 0;

-       return tvm_usable;
+       return !!tvm_usable;
 }


> 
>

---

## [71] Xu Yilun — 2025-12-23
*Subject: Re: [PATCH v1 14/26] mm: Add __free() support for folio_put()*

On Fri, Dec 19, 2025 at 11:55:07AM +0000, Jonathan Cameron wrote:
> On Mon, 17 Nov 2025 10:22:58 +0800
> Xu Yilun <yilun.xu@linux.intel.com> wrote:

Sorry I'll also drop this one cause I'll drop __free() in tdx core.

> 
> > +

---

## [72] Xu Yilun — 2025-12-23
*Subject: Re: [PATCH v1 26/26] coco/tdx-host: Finally enable SPDM session and
 IDE Establishment*

On Fri, Dec 19, 2025 at 12:06:16PM +0000, Jonathan Cameron wrote:
> On Mon, 17 Nov 2025 10:23:10 +0800
> Xu Yilun <yilun.xu@linux.intel.com> wrote:

Thanks for all your review, tagged them in my v2.

---

## [73] dan.j.williams@intel.com — 2026-02-11
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

Dave Hansen wrote:
> On 11/16/25 18:22, Xu Yilun wrote:
> > +	struct page *root __free(__free_page) = alloc_page(GFP_KERNEL |

I saw a preview of what this comment does to the implementation and I am
not sure it is an improvement to avoid the __free() support for
alloc_page().

The seamcall prototype is:

u64 tdh_ide_stream_km(u64 spdm_id, u64 stream_id, u64 operation,
                      struct page *spdm_rsp, struct page *spdm_req,
                      u64 *spdm_req_len);

The interdiff of the effect of this review feedback is:

    @@ drivers/virt/coco/tdx-host/tdx-host.c: static void tdx_spdm_session_teardown(str
     +
     +  do {
     +          r = tdh_ide_stream_km(tlink->spdm_id, tlink->stream_id, op,
    -+                                tlink->in_msg, tlink->out_msg,
    ++                                virt_to_page(tlink->in_msg),
    ++                                virt_to_page(tlink->out_msg),
     +                                &out_msg_sz);
     +          ret = tdx_link_event_handler(tlink, r, out_msg_sz);
     +  } while (ret == -EAGAIN);

This is unfortunate because tdh_ide_stream_km() will just turn around
and call page_to_phys() on those arguments. It forfeits type safety and
inflicts the mental hurdle of "->in_msg and ->out_msg are direct-mapped
page-aligned virtual addresses, right, right!?".

So alloc_page() + __free_page() is more suitable than kzalloc(PAGE_SIZE,
...) as long as the seamcall requires 'struct page *' arguments. Another
path is the seamcall semantic is updated to handle virt_to_phys()
without alignment concerns, but it is a bit late to make that change. I
considered the concept of passing a "va page frame number" around, but
'struct page *' *is* the idiomatic expression for that concept.

---

## [74] Tony Lindgren — 2026-02-17
*Subject: Re: [PATCH v1 06/26] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Mon, Nov 17, 2025 at 10:22:50AM +0800, Xu Yilun wrote:
> @@ -296,6 +297,257 @@ static __init int build_tdx_memlist(struct list_head *tmb_list)
>  	return ret;
...

> +/*
> + * For holding less than TDX_PAGE_ARRAY_MAX_NENTS (512) pages.

The comment should be "For holding at most TDX_PAGE_ARRAY_MAX_NENTS.."

> + * If more pages are required, use tdx_page_array_alloc() and
> + * tdx_page_array_fill_root() to build tdx_page_array chunk by chunk.

To match this check.

> +	struct tdx_page_array *array __free(tdx_page_array_free) =
> +		tdx_page_array_alloc(nr_pages);

Regards,

Tony

---
