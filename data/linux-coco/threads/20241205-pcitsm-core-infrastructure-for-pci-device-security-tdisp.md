---
title: 'PCI/TSM: Core infrastructure for PCI device security\n (TDISP)'
date: 2024-12-05
last_reply: 2025-03-07
message_count: 125
participants: ['Dan Williams', 'kernel test robot', 'Greg KH', 'Ilpo Järvinen', 'Aneesh Kumar K.V', 'Alexey Kardashevskiy', 'Bjorn Helgaas', 'Suzuki K Poulose', 'Xu Yilun', 'Jonathan Cameron']
---

## [1] Dan Williams — 2024-12-05

Changes since the RFC [1]:
- Wording changes and cleanups in "PCI/TSM: Authenticate devices via
  platform TSM" (Bjorn)
- Document /sys/class/tsm/tsm0 (Bjorn)
- Replace the single ->exec(@op_code) operation with named operations
  (Alexey, Yilun)
- Locking fixup in drivers/pci/tsm.c (Yilun)
- Drop pci_tsm_devs xarray (Alexey, Yilun)
- Finish the host bridge stream id allocator implementation (Alexey)
- Clarify pci_tsm_init() relative to IDE && !TEE devices (Alexey)
- Add the IDE core helpers
- Add devsec_tsm and devsec_bus sample driver and emulation

[1]: http://lore.kernel.org/171291190324.3532867.13480405752065082171.stgit@dwillia2-xfh.jf.intel.com

---

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
coordination with the native PCI device security effort [2].

The devsec_tsm driver is already yielding benefits as it drove many of
the fixes and enhancements of this patch-kit relative to the last RFC
[1]. Future development would either reuse established devsec_tsm paths,
or extend the sample alongside the vendor-specific implementation.

This first batch is just enough infrastructure for IDE (link Integrity
and Data Encryption) establishment via TSM APIs. It is based on a review
and curation of the IDE establishment flows from the SEV-TIO RFC [3] and
a work-in-progress TDX Connect RFC (see the Co-developed-by and thanks
yous in the changelogs for where code was copied).

It deliberately avoids SPDM details and does not touch upon the "bind"
flows, or guest-side flows, simply to allow for upstream digestion of
all the assumptions and tradeoffs for the "simple" IDE establishment
baseline.

Note that devsec_tsm is for near term staging of vendor TSM
implementations. The expectation is that every piece of new core
infrastructure that devsec_tsm consumes must also have a vendor TSM
driver consumer within 1 to 2 kernel development cycles.

The full series is available via devsec/tsm.git [4].

[2]: http://lore.kernel.org/cover.1719771133.git.lukas@wunner.de
[3]: http://lore.kernel.org/20240823132137.336874-1-aik@amd.com
[4]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=devsec-20241205

---

Dan Williams (11):
      configfs-tsm: Namespace TSM report symbols
      coco/guest: Move shared guest CC infrastructure to drivers/virt/coco/guest/
      coco/tsm: Introduce a class device for TEE Security Managers
      PCI/IDE: Selective Stream IDE enumeration
      PCI/TSM: Authenticate devices via platform TSM
      samples/devsec: PCI device-security bus / endpoint sample
      PCI: Add PCIe Device 3 Extended Capability enumeration
      PCI/IDE: Add IDE establishment helpers
      PCI/IDE: Report available IDE streams
      PCI/TSM: Report active IDE streams
      samples/devsec: Add sample IDE establishment


 Documentation/ABI/testing/configfs-tsm-report      |    0 
 Documentation/ABI/testing/sysfs-bus-pci            |   42 +
 Documentation/ABI/testing/sysfs-class-tsm          |   20 +
 .../ABI/testing/sysfs-devices-pci-host-bridge      |   39 +
 MAINTAINERS                                        |   10 
 drivers/pci/Kconfig                                |   16 
 drivers/pci/Makefile                               |    2 
 drivers/pci/ide.c                                  |  311 +++++++++
 drivers/pci/pci-sysfs.c                            |    4 
 drivers/pci/pci.h                                  |   34 +
 drivers/pci/probe.c                                |   15 
 drivers/pci/remove.c                               |    3 
 drivers/pci/tsm.c                                  |  293 ++++++++
 drivers/virt/coco/Kconfig                          |    8 
 drivers/virt/coco/Makefile                         |    3 
 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c    |    8 
 drivers/virt/coco/guest/Kconfig                    |    7 
 drivers/virt/coco/guest/Makefile                   |    3 
 drivers/virt/coco/guest/report.c                   |   32 -
 drivers/virt/coco/host/Kconfig                     |    6 
 drivers/virt/coco/host/Makefile                    |    6 
 drivers/virt/coco/host/tsm-core.c                  |  145 ++++
 drivers/virt/coco/sev-guest/sev-guest.c            |   12 
 drivers/virt/coco/tdx-guest/tdx-guest.c            |    8 
 include/linux/pci-ide.h                            |   33 +
 include/linux/pci-tsm.h                            |   83 ++
 include/linux/pci.h                                |   22 +
 include/linux/tsm.h                                |   33 +
 include/uapi/linux/pci_regs.h                      |   92 +++
 samples/Kconfig                                    |   15 
 samples/Makefile                                   |    1 
 samples/devsec/Makefile                            |   10 
 samples/devsec/bus.c                               |  695 ++++++++++++++++++++
 samples/devsec/common.c                            |   26 +
 samples/devsec/devsec.h                            |    7 
 samples/devsec/tsm.c                               |  192 ++++++
 36 files changed, 2185 insertions(+), 51 deletions(-)
 rename Documentation/ABI/testing/{configfs-tsm => configfs-tsm-report} (100%)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 create mode 100644 drivers/pci/ide.c
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 drivers/virt/coco/guest/Kconfig
 create mode 100644 drivers/virt/coco/guest/Makefile
 rename drivers/virt/coco/{tsm.c => guest/report.c} (93%)
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

base-commit: 40384c840ea1944d7c5a392e8975ed088ecf0b37

---

## [2] Dan Williams — 2024-12-05
*Subject: [PATCH 01/11] configfs-tsm: Namespace TSM report symbols*

In preparation for new + common TSM (TEE Security Manager)
infrastructure, namespace the TSM report symbols in tsm.h with an
_REPORT suffix to differentiate them from other incoming tsm work.

Cc: Yilun Xu <yilun.xu@intel.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/configfs-tsm-report   |    0 
 MAINTAINERS                                     |    2 +
 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c |    8 +++---
 drivers/virt/coco/sev-guest/sev-guest.c         |   12 ++++-----
 drivers/virt/coco/tdx-guest/tdx-guest.c         |    8 +++---
 drivers/virt/coco/tsm.c                         |   32 ++++++++++++-----------
 include/linux/tsm.h                             |   22 ++++++++--------
 7 files changed, 42 insertions(+), 42 deletions(-)
 rename Documentation/ABI/testing/{configfs-tsm => configfs-tsm-report} (100%)

diff --git a/Documentation/ABI/testing/configfs-tsm b/Documentation/ABI/testing/configfs-tsm-report
similarity index 100%
rename from Documentation/ABI/testing/configfs-tsm
rename to Documentation/ABI/testing/configfs-tsm-report
diff --git a/MAINTAINERS b/MAINTAINERS
index 1e930c7a58b1..53f04c499705 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23842,7 +23842,7 @@ TRUSTED SECURITY MODULE (TSM) ATTESTATION REPORTS
 M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
-F:	Documentation/ABI/testing/configfs-tsm
+F:	Documentation/ABI/testing/configfs-tsm-report
 F:	drivers/virt/coco/tsm.c
 F:	include/linux/tsm.h
 
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
index 488153879ec9..63b9fdb843fa 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
@@ -95,7 +95,7 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
 	struct arm_cca_token_info info;
 	void *buf;
 	u8 *token __free(kvfree) = NULL;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 
 	if (desc->inblob_len < 32 || desc->inblob_len > 64)
 		return -EINVAL;
@@ -180,7 +180,7 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
 	return ret;
 }
 
-static const struct tsm_ops arm_cca_tsm_ops = {
+static const struct tsm_report_ops arm_cca_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = arm_cca_report_new,
 };
@@ -201,7 +201,7 @@ static int __init arm_cca_guest_init(void)
 	if (!is_realm_world())
 		return -ENODEV;
 
-	ret = tsm_register(&arm_cca_tsm_ops, NULL);
+	ret = tsm_report_register(&arm_cca_tsm_ops, NULL);
 	if (ret < 0)
 		pr_err("Error %d registering with TSM\n", ret);
 
@@ -215,7 +215,7 @@ module_init(arm_cca_guest_init);
  */
 static void __exit arm_cca_guest_exit(void)
 {
-	tsm_unregister(&arm_cca_tsm_ops);
+	tsm_report_unregister(&arm_cca_tsm_ops);
 }
 module_exit(arm_cca_guest_exit);
 
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index fca5c45ed5cd..7eedde61589c 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -701,7 +701,7 @@ struct snp_msg_cert_entry {
 static int sev_svsm_report_new(struct tsm_report *report, void *data)
 {
 	unsigned int rep_len, man_len, certs_len;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	struct svsm_attest_call ac = {};
 	unsigned int retry_count;
 	void *rep, *man, *certs;
@@ -836,7 +836,7 @@ static int sev_svsm_report_new(struct tsm_report *report, void *data)
 static int sev_report_new(struct tsm_report *report, void *data)
 {
 	struct snp_msg_cert_entry *cert_table;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	struct snp_guest_dev *snp_dev = data;
 	struct snp_msg_report_resp_hdr hdr;
 	const u32 report_size = SZ_4K;
@@ -965,7 +965,7 @@ static bool sev_report_bin_attr_visible(int n)
 	return false;
 }
 
-static struct tsm_ops sev_tsm_ops = {
+static struct tsm_report_ops sev_tsm_report_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = sev_report_new,
 	.report_attr_visible = sev_report_attr_visible,
@@ -974,7 +974,7 @@ static struct tsm_ops sev_tsm_ops = {
 
 static void unregister_sev_tsm(void *data)
 {
-	tsm_unregister(&sev_tsm_ops);
+	tsm_report_unregister(&sev_tsm_report_ops);
 }
 
 static int __init sev_guest_probe(struct platform_device *pdev)
@@ -1062,9 +1062,9 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	mdesc->input.data_gpa = __pa(mdesc->certs_data);
 
 	/* Set the privlevel_floor attribute based on the vmpck_id */
-	sev_tsm_ops.privlevel_floor = vmpck_id;
+	sev_tsm_report_ops.privlevel_floor = vmpck_id;
 
-	ret = tsm_register(&sev_tsm_ops, snp_dev);
+	ret = tsm_report_register(&sev_tsm_report_ops, snp_dev);
 	if (ret)
 		goto e_free_cert_data;
 
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index d7db6c824e13..66ea09207a7c 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -163,7 +163,7 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 {
 	u8 *buf, *reportdata = NULL, *tdreport = NULL;
 	struct tdx_quote_buf *quote_buf = quote_data;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	int ret;
 	u64 err;
 
@@ -299,7 +299,7 @@ static const struct x86_cpu_id tdx_guest_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_guest_ids);
 
-static const struct tsm_ops tdx_tsm_ops = {
+static const struct tsm_report_ops tdx_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = tdx_report_new,
 	.report_attr_visible = tdx_report_attr_visible,
@@ -324,7 +324,7 @@ static int __init tdx_guest_init(void)
 		goto free_misc;
 	}
 
-	ret = tsm_register(&tdx_tsm_ops, NULL);
+	ret = tsm_report_register(&tdx_tsm_ops, NULL);
 	if (ret)
 		goto free_quote;
 
@@ -341,7 +341,7 @@ module_init(tdx_guest_init);
 
 static void __exit tdx_guest_exit(void)
 {
-	tsm_unregister(&tdx_tsm_ops);
+	tsm_report_unregister(&tdx_tsm_ops);
 	free_quote_buf(quote_data);
 	misc_deregister(&tdx_misc_dev);
 }
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index 9432d4e303f1..bcb515b50c68 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -13,7 +13,7 @@
 #include <linux/configfs.h>
 
 static struct tsm_provider {
-	const struct tsm_ops *ops;
+	const struct tsm_report_ops *ops;
 	void *data;
 } provider;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -98,7 +98,7 @@ static ssize_t tsm_report_privlevel_store(struct config_item *cfg,
 	 * SEV-SNP GHCB) and a minimum of a TSM selected floor value no less
 	 * than 0.
 	 */
-	if (provider.ops->privlevel_floor > val || val > TSM_PRIVLEVEL_MAX)
+	if (provider.ops->privlevel_floor > val || val > TSM_REPORT_PRIVLEVEL_MAX)
 		return -EINVAL;
 
 	guard(rwsem_write)(&tsm_rwsem);
@@ -202,7 +202,7 @@ static ssize_t tsm_report_inblob_write(struct config_item *cfg,
 	memcpy(report->desc.inblob, buf, count);
 	return count;
 }
-CONFIGFS_BIN_ATTR_WO(tsm_report_, inblob, NULL, TSM_INBLOB_MAX);
+CONFIGFS_BIN_ATTR_WO(tsm_report_, inblob, NULL, TSM_REPORT_INBLOB_MAX);
 
 static ssize_t tsm_report_generation_show(struct config_item *cfg, char *buf)
 {
@@ -272,7 +272,7 @@ static ssize_t tsm_report_read(struct tsm_report *report, void *buf,
 			       size_t count, enum tsm_data_select select)
 {
 	struct tsm_report_state *state = to_state(report);
-	const struct tsm_ops *ops;
+	const struct tsm_report_ops *ops;
 	ssize_t rc;
 
 	/* try to read from the existing report if present and valid... */
@@ -314,7 +314,7 @@ static ssize_t tsm_report_outblob_read(struct config_item *cfg, void *buf,
 
 	return tsm_report_read(report, buf, count, TSM_REPORT);
 }
-CONFIGFS_BIN_ATTR_RO(tsm_report_, outblob, NULL, TSM_OUTBLOB_MAX);
+CONFIGFS_BIN_ATTR_RO(tsm_report_, outblob, NULL, TSM_REPORT_OUTBLOB_MAX);
 
 static ssize_t tsm_report_auxblob_read(struct config_item *cfg, void *buf,
 				       size_t count)
@@ -323,7 +323,7 @@ static ssize_t tsm_report_auxblob_read(struct config_item *cfg, void *buf,
 
 	return tsm_report_read(report, buf, count, TSM_CERTS);
 }
-CONFIGFS_BIN_ATTR_RO(tsm_report_, auxblob, NULL, TSM_OUTBLOB_MAX);
+CONFIGFS_BIN_ATTR_RO(tsm_report_, auxblob, NULL, TSM_REPORT_OUTBLOB_MAX);
 
 static ssize_t tsm_report_manifestblob_read(struct config_item *cfg, void *buf,
 					    size_t count)
@@ -332,7 +332,7 @@ static ssize_t tsm_report_manifestblob_read(struct config_item *cfg, void *buf,
 
 	return tsm_report_read(report, buf, count, TSM_MANIFEST);
 }
-CONFIGFS_BIN_ATTR_RO(tsm_report_, manifestblob, NULL, TSM_OUTBLOB_MAX);
+CONFIGFS_BIN_ATTR_RO(tsm_report_, manifestblob, NULL, TSM_REPORT_OUTBLOB_MAX);
 
 static struct configfs_attribute *tsm_report_attrs[] = {
 	[TSM_REPORT_GENERATION] = &tsm_report_attr_generation,
@@ -448,9 +448,9 @@ static struct configfs_subsystem tsm_configfs = {
 	.su_mutex = __MUTEX_INITIALIZER(tsm_configfs.su_mutex),
 };
 
-int tsm_register(const struct tsm_ops *ops, void *priv)
+int tsm_report_register(const struct tsm_report_ops *ops, void *priv)
 {
-	const struct tsm_ops *conflict;
+	const struct tsm_report_ops *conflict;
 
 	guard(rwsem_write)(&tsm_rwsem);
 	conflict = provider.ops;
@@ -463,9 +463,9 @@ int tsm_register(const struct tsm_ops *ops, void *priv)
 	provider.data = priv;
 	return 0;
 }
-EXPORT_SYMBOL_GPL(tsm_register);
+EXPORT_SYMBOL_GPL(tsm_report_register);
 
-int tsm_unregister(const struct tsm_ops *ops)
+int tsm_report_unregister(const struct tsm_report_ops *ops)
 {
 	guard(rwsem_write)(&tsm_rwsem);
 	if (ops != provider.ops)
@@ -474,11 +474,11 @@ int tsm_unregister(const struct tsm_ops *ops)
 	provider.data = NULL;
 	return 0;
 }
-EXPORT_SYMBOL_GPL(tsm_unregister);
+EXPORT_SYMBOL_GPL(tsm_report_unregister);
 
 static struct config_group *tsm_report_group;
 
-static int __init tsm_init(void)
+static int __init tsm_report_init(void)
 {
 	struct config_group *root = &tsm_configfs.su_group;
 	struct config_group *tsm;
@@ -499,14 +499,14 @@ static int __init tsm_init(void)
 
 	return 0;
 }
-module_init(tsm_init);
+module_init(tsm_report_init);
 
-static void __exit tsm_exit(void)
+static void __exit tsm_report_exit(void)
 {
 	configfs_unregister_default_group(tsm_report_group);
 	configfs_unregister_subsystem(&tsm_configfs);
 }
-module_exit(tsm_exit);
+module_exit(tsm_report_exit);
 
 MODULE_LICENSE("GPL");
 MODULE_DESCRIPTION("Provide Trusted Security Module attestation reports via configfs");
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 11b0c525be30..431054810dca 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -6,17 +6,17 @@
 #include <linux/types.h>
 #include <linux/uuid.h>
 
-#define TSM_INBLOB_MAX 64
-#define TSM_OUTBLOB_MAX SZ_32K
+#define TSM_REPORT_INBLOB_MAX 64
+#define TSM_REPORT_OUTBLOB_MAX SZ_32K
 
 /*
  * Privilege level is a nested permission concept to allow confidential
  * guests to partition address space, 4-levels are supported.
  */
-#define TSM_PRIVLEVEL_MAX 3
+#define TSM_REPORT_PRIVLEVEL_MAX 3
 
 /**
- * struct tsm_desc - option descriptor for generating tsm report blobs
+ * struct tsm_report_desc - option descriptor for generating tsm report blobs
  * @privlevel: optional privilege level to associate with @outblob
  * @inblob_len: sizeof @inblob
  * @inblob: arbitrary input data
@@ -24,10 +24,10 @@
  * @service_guid: optional service-provider service guid to attest
  * @service_manifest_version: optional service-provider service manifest version requested
  */
-struct tsm_desc {
+struct tsm_report_desc {
 	unsigned int privlevel;
 	size_t inblob_len;
-	u8 inblob[TSM_INBLOB_MAX];
+	u8 inblob[TSM_REPORT_INBLOB_MAX];
 	char *service_provider;
 	guid_t service_guid;
 	unsigned int service_manifest_version;
@@ -44,7 +44,7 @@ struct tsm_desc {
  * @manifestblob: (optional) manifest data associated with the report
  */
 struct tsm_report {
-	struct tsm_desc desc;
+	struct tsm_report_desc desc;
 	size_t outblob_len;
 	u8 *outblob;
 	size_t auxblob_len;
@@ -88,7 +88,7 @@ enum tsm_bin_attr_index {
 };
 
 /**
- * struct tsm_ops - attributes and operations for tsm instances
+ * struct tsm_report_ops - attributes and operations for tsm_report instances
  * @name: tsm id reflected in /sys/kernel/config/tsm/report/$report/provider
  * @privlevel_floor: convey base privlevel for nested scenarios
  * @report_new: Populate @report with the report blob and auxblob
@@ -99,7 +99,7 @@ enum tsm_bin_attr_index {
  * Implementation specific ops, only one is expected to be registered at
  * a time i.e. only one of "sev-guest", "tdx-guest", etc.
  */
-struct tsm_ops {
+struct tsm_report_ops {
 	const char *name;
 	unsigned int privlevel_floor;
 	int (*report_new)(struct tsm_report *report, void *data);
@@ -107,6 +107,6 @@ struct tsm_ops {
 	bool (*report_bin_attr_visible)(int n);
 };
 
-int tsm_register(const struct tsm_ops *ops, void *priv);
-int tsm_unregister(const struct tsm_ops *ops);
+int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
+int tsm_report_unregister(const struct tsm_report_ops *ops);
 #endif /* __TSM_H */

---

## [3] Dan Williams — 2024-12-05
*Subject: [PATCH 02/11] coco/guest: Move shared guest CC infrastructure to
 drivers/virt/coco/guest/*

In preparation for creating a new drivers/virt/coco/host/ directory to
house shared host driver infrastructure for confidential computing, move
configfs-tsm to a guest/ sub-directory. The tsm.ko module is renamed to
tsm_reports.ko. The old tsm.ko module was only ever demand loaded by
kernel internal dependencies, so it should not affect existing userspace
module install scripts.

The new drivers/virt/coco/guest/ is also a preparatory landing spot for
new / optional TSM Report mechanics like a TCB stability enumeration /
watchdog mechanism. To be added later.

Cc: Wu Hao <hao.wu@intel.com>
Cc: Yilun Xu <yilun.xu@intel.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 MAINTAINERS                      |    2 +-
 drivers/virt/coco/Kconfig        |    6 ++----
 drivers/virt/coco/Makefile       |    2 +-
 drivers/virt/coco/guest/Kconfig  |    7 +++++++
 drivers/virt/coco/guest/Makefile |    3 +++
 drivers/virt/coco/guest/report.c |    0 
 6 files changed, 14 insertions(+), 6 deletions(-)
 create mode 100644 drivers/virt/coco/guest/Kconfig
 create mode 100644 drivers/virt/coco/guest/Makefile
 rename drivers/virt/coco/{tsm.c => guest/report.c} (100%)

diff --git a/MAINTAINERS b/MAINTAINERS
index 53f04c499705..0c8f61662836 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23843,7 +23843,7 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm-report
-F:	drivers/virt/coco/tsm.c
+F:	drivers/virt/coco/guest/
 F:	include/linux/tsm.h
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index ff869d883d95..819a97e8ba99 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -3,10 +3,6 @@
 # Confidential computing related collateral
 #
 
-config TSM_REPORTS
-	select CONFIGFS_FS
-	tristate
-
 source "drivers/virt/coco/efi_secret/Kconfig"
 
 source "drivers/virt/coco/pkvm-guest/Kconfig"
@@ -16,3 +12,5 @@ source "drivers/virt/coco/sev-guest/Kconfig"
 source "drivers/virt/coco/tdx-guest/Kconfig"
 
 source "drivers/virt/coco/arm-cca-guest/Kconfig"
+
+source "drivers/virt/coco/guest/Kconfig"
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index c3d07cfc087e..885c9ef4e9fc 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -2,9 +2,9 @@
 #
 # Confidential computing related collateral
 #
-obj-$(CONFIG_TSM_REPORTS)	+= tsm.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
+obj-$(CONFIG_TSM_REPORTS)	+= guest/
diff --git a/drivers/virt/coco/guest/Kconfig b/drivers/virt/coco/guest/Kconfig
new file mode 100644
index 000000000000..ed9bafbdd854
--- /dev/null
+++ b/drivers/virt/coco/guest/Kconfig
@@ -0,0 +1,7 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# Confidential computing shared guest collateral
+#
+config TSM_REPORTS
+	select CONFIGFS_FS
+	tristate
diff --git a/drivers/virt/coco/guest/Makefile b/drivers/virt/coco/guest/Makefile
new file mode 100644
index 000000000000..b3b217af77cf
--- /dev/null
+++ b/drivers/virt/coco/guest/Makefile
@@ -0,0 +1,3 @@
+# SPDX-License-Identifier: GPL-2.0
+obj-$(CONFIG_TSM_REPORTS)	+= tsm_report.o
+tsm_report-y := report.o
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/guest/report.c
similarity index 100%
rename from drivers/virt/coco/tsm.c
rename to drivers/virt/coco/guest/report.c

---

## [4] Dan Williams — 2024-12-05
*Subject: [PATCH 03/11] coco/tsm: Introduce a class device for TEE Security
 Managers*

A "TSM" is a platform component that provides an API for securely
provisioning resources for a confidential guest (TVM) to consume. The
name originates from the PCI specification for platform agent that
carries out operations for PCIe TDISP (TEE Device Interface Security
Protocol).

Instances of this class device are parented by a device representing the
platform security capability like CONFIG_CRYPTO_DEV_CCP or
CONFIG_INTEL_TDX_HOST.

This class device interface is a frontend to the aspects of a TSM and
TEE I/O that are cross-architecture common. This includes mechanisms
like enumerating available platform TEE I/O capabilities and
provisioning connections between the platform TSM and device DSMs
(Device Security Manager (TDISP)).

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
 Documentation/ABI/testing/sysfs-class-tsm |   10 +++
 MAINTAINERS                               |    3 +
 drivers/virt/coco/Kconfig                 |    2 +
 drivers/virt/coco/Makefile                |    1 
 drivers/virt/coco/host/Kconfig            |    6 ++
 drivers/virt/coco/host/Makefile           |    6 ++
 drivers/virt/coco/host/tsm-core.c         |  113 +++++++++++++++++++++++++++++
 include/linux/tsm.h                       |    5 +
 8 files changed, 145 insertions(+), 1 deletion(-)
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
index 0c8f61662836..abaabbc39134 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23838,12 +23838,13 @@ W:	https://github.com/srcres258/linux-doc
 T:	git git://github.com/srcres258/linux-doc.git doc-zh-tw
 F:	Documentation/translations/zh_TW/
 
-TRUSTED SECURITY MODULE (TSM) ATTESTATION REPORTS
+TRUSTED (TEE) SECURITY MANAGER (TSM)
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
index 000000000000..0ee738fc40ed
--- /dev/null
+++ b/drivers/virt/coco/host/tsm-core.c
@@ -0,0 +1,113 @@
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
+static struct tsm_subsys {
+	struct device dev;
+} *tsm_subsys;
+
+static struct tsm_subsys *
+alloc_tsm_subsys(struct device *parent, const struct attribute_group **groups)
+{
+	struct tsm_subsys *subsys = kzalloc(sizeof(*subsys), GFP_KERNEL);
+	struct device *dev;
+
+	if (!subsys)
+		return ERR_PTR(-ENOMEM);
+	dev = &subsys->dev;
+	dev->parent = parent;
+	dev->groups = groups;
+	dev->class = tsm_class;
+	device_initialize(dev);
+	return subsys;
+}
+
+static void put_tsm_subsys(struct tsm_subsys *subsys)
+{
+	if (!IS_ERR_OR_NULL(subsys))
+		put_device(&subsys->dev);
+}
+
+DEFINE_FREE(put_tsm_subsys, struct tsm_subsys *,
+	    if (!IS_ERR_OR_NULL(_T)) put_tsm_subsys(_T))
+struct tsm_subsys *tsm_register(struct device *parent,
+				const struct attribute_group **groups)
+{
+	struct device *dev;
+	int rc;
+
+	guard(rwsem_write)(&tsm_core_rwsem);
+	if (tsm_subsys) {
+		dev_warn(parent, "failed to register: %s already registered\n",
+			 dev_name(tsm_subsys->dev.parent));
+		return ERR_PTR(-EBUSY);
+	}
+
+	struct tsm_subsys *subsys __free(put_tsm_subsys) =
+		alloc_tsm_subsys(parent, groups);
+	if (IS_ERR(subsys))
+		return subsys;
+
+	dev = &subsys->dev;
+	rc = dev_set_name(dev, "tsm0");
+	if (rc)
+		return ERR_PTR(rc);
+
+	rc = device_add(dev);
+	if (rc)
+		return ERR_PTR(rc);
+
+	tsm_subsys = no_free_ptr(subsys);
+
+	return tsm_subsys;
+}
+EXPORT_SYMBOL_GPL(tsm_register);
+
+void tsm_unregister(struct tsm_subsys *subsys)
+{
+	guard(rwsem_write)(&tsm_core_rwsem);
+	if (!tsm_subsys || subsys != tsm_subsys) {
+		pr_warn("failed to unregister, not currently registered\n");
+		return;
+	}
+
+	device_unregister(&subsys->dev);
+	tsm_subsys = NULL;
+}
+EXPORT_SYMBOL_GPL(tsm_unregister);
+
+static void tsm_release(struct device *dev)
+{
+	struct tsm_subsys *subsys = container_of(dev, typeof(*subsys), dev);
+
+	kfree(subsys);
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
index 431054810dca..1a97459fc23e 100644
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
+struct tsm_subsys;
+struct tsm_subsys *tsm_register(struct device *parent,
+				const struct attribute_group **groups);
+void tsm_unregister(struct tsm_subsys *subsys);
 #endif /* __TSM_H */

---

## [5] Dan Williams — 2024-12-05
*Subject: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Link encryption is a new PCIe capability defined by "PCIe 6.2 section
6.33 Integrity & Data Encryption (IDE)". While it is a standalone port
and endpoint capability, it is also a building block for device security
defined by "PCIe 6.2 section 11 TEE Device Interface Security Protocol
(TDISP)". That protocol coordinates device security setup between the
platform TSM (TEE Security Manager) and device DSM (Device Security
Manager). While the platform TSM can allocate resources like stream-ids
and manage keys, it still requires system software to manage the IDE
capability register block.

Add register definitions and basic enumeration for a "selective-stream"
IDE capability, a follow on change will select the new CONFIG_PCI_IDE
symbol. Note that while the IDE specifications defines both a
point-to-point "Link" stream and a root-port-to-endpoint "Selective"
stream, only "Selective" is considered for now for platform TSM
coordination.

Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Kconfig           |    3 +
 drivers/pci/Makefile          |    1 
 drivers/pci/ide.c             |   73 ++++++++++++++++++++++++++++++++++++
 drivers/pci/pci.h             |    6 +++
 drivers/pci/probe.c           |    1 
 include/linux/pci.h           |    5 ++
 include/uapi/linux/pci_regs.h |   84 +++++++++++++++++++++++++++++++++++++++++
 7 files changed, 172 insertions(+), 1 deletion(-)
 create mode 100644 drivers/pci/ide.c

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 2fbd379923fd..4e5236c456f5 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -121,6 +121,9 @@ config XEN_PCIDEV_FRONTEND
 config PCI_ATS
 	bool
 
+config PCI_IDE
+	bool
+
 config PCI_DOE
 	bool
 
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
index 000000000000..a0c09d9e0b75
--- /dev/null
+++ b/drivers/pci/ide.c
@@ -0,0 +1,73 @@
+// SPDX-License-Identifier: GPL-2.0
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+/* PCIe 6.2 section 6.33 Integrity & Data Encryption (IDE) */
+
+#define dev_fmt(fmt) "PCI/IDE: " fmt
+#include <linux/pci.h>
+#include "pci.h"
+
+static int sel_ide_offset(u16 cap, int stream_id, int nr_ide_mem)
+{
+	return cap + stream_id * PCI_IDE_SELECTIVE_BLOCK_SIZE(nr_ide_mem);
+}
+
+void pci_ide_init(struct pci_dev *pdev)
+{
+	u16 ide_cap, sel_ide_cap;
+	int nr_ide_mem = 0;
+	u32 val = 0;
+
+	if (!pci_is_pcie(pdev))
+		return;
+
+	ide_cap = pci_find_ext_capability(pdev, PCI_EXT_CAP_ID_IDE);
+	if (!ide_cap)
+		return;
+
+	/*
+	 * Check for selective stream capability from endpoint to root-port, and
+	 * require consistent number of address association blocks
+	 */
+	pci_read_config_dword(pdev, ide_cap + PCI_IDE_CAP, &val);
+	if ((val & PCI_IDE_CAP_SELECTIVE) == 0)
+		return;
+
+	if (pci_pcie_type(pdev) == PCI_EXP_TYPE_ENDPOINT) {
+		struct pci_dev *rp = pcie_find_root_port(pdev);
+
+		if (!rp->ide_cap)
+			return;
+	}
+
+	if (val & PCI_IDE_CAP_LINK)
+		sel_ide_cap = ide_cap + PCI_IDE_LINK_STREAM +
+			      (PCI_IDE_CAP_LINK_TC_NUM(val) + 1) *
+				      PCI_IDE_LINK_BLOCK_SIZE;
+	else
+		sel_ide_cap = ide_cap + PCI_IDE_LINK_STREAM;
+
+	for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val); i++) {
+		if (i == 0) {
+			pci_read_config_dword(pdev, sel_ide_cap, &val);
+			nr_ide_mem = PCI_IDE_SEL_CAP_ASSOC_NUM(val);
+		} else {
+			int offset = sel_ide_offset(sel_ide_cap, i, nr_ide_mem);
+
+			pci_read_config_dword(pdev, offset, &val);
+
+			/*
+			 * lets not entertain devices that do not have a
+			 * constant number of address association blocks
+			 */
+			if (PCI_IDE_SEL_CAP_ASSOC_NUM(val) != nr_ide_mem) {
+				pci_info(pdev, "Unsupported Selective Stream %d capability\n", i);
+				return;
+			}
+		}
+	}
+
+	pdev->ide_cap = ide_cap;
+	pdev->sel_ide_cap = sel_ide_cap;
+	pdev->nr_ide_mem = nr_ide_mem;
+}
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 2e40fc63ba31..0305f497b28a 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -452,6 +452,12 @@ static inline void pci_npem_create(struct pci_dev *dev) { }
 static inline void pci_npem_remove(struct pci_dev *dev) { }
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
index 2e81ab0f5a25..e22f515a8da9 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2517,6 +2517,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_rcec_init(dev);		/* Root Complex Event Collector */
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
+	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index db9b47ce3eef..50811b7655dd 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -530,6 +530,11 @@ struct pci_dev {
 #endif
 #ifdef CONFIG_PCI_NPEM
 	struct npem	*npem;		/* Native PCIe Enclosure Management */
+#endif
+#ifdef CONFIG_PCI_IDE
+	u16		ide_cap;	/* Link Integrity & Data Encryption */
+	u16		sel_ide_cap;	/* - Selective Stream register block */
+	int		nr_ide_mem;	/* - Address range limits for streams */
 #endif
 	u16		acs_cap;	/* ACS Capability offset */
 	u8		supported_speeds; /* Supported Link Speeds Vector */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 1601c7ed5fab..9635b27d2485 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -748,7 +748,8 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
-#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_DOE
+#define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
+#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE
 
 #define PCI_EXT_CAP_DSN_SIZEOF	12
 #define PCI_EXT_CAP_MCAST_ENDPOINT_SIZEOF 40
@@ -1213,4 +1214,85 @@
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
+#define  PCI_IDE_CAP_ALG(x)		(((x) >> 8) & 0x1f) /* Supported Algorithms */
+#define  PCI_IDE_CAP_ALG_AES_GCM_256	0    /* AES-GCM 256 key size, 96b MAC */
+#define  PCI_IDE_CAP_LINK_TC_NUM(x)	(((x) >> 13) & 0x7) /* Link IDE TCs */
+#define  PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(x)	(((x) >> 16) & 0xff) /* Selective IDE Streams */
+#define  PCI_IDE_CAP_SELECTIVE_STREAMS_MASK	0xff0000
+#define  PCI_IDE_CAP_TEE_LIMITED	0x1000000 /* TEE-Limited Stream Supported */
+#define PCI_IDE_CTL			0x8
+#define  PCI_IDE_CTL_FLOWTHROUGH_IDE	0x4	/* Flow-Through IDE Stream Enabled */
+#define PCI_IDE_LINK_STREAM		0xc
+#define PCI_IDE_LINK_BLOCK_SIZE		8
+/* Link IDE Stream block, up to PCI_IDE_CAP_LINK_TC_NUM */
+/* Link IDE Stream Control Register */
+#define  PCI_IDE_LINK_CTL_EN		 0x1	/* Link IDE Stream Enable */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_NPR(x) (((x) >> 2) & 0x3) /* Tx Aggregation Mode NPR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_PR(x)	 (((x) >> 4) & 0x3) /* Tx Aggregation Mode PR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_CPL(x) (((x) >> 6) & 0x3) /* Tx Aggregation Mode CPL */
+#define  PCI_IDE_LINK_CTL_PCRC_EN	 0x100	/* PCRC Enable */
+#define  PCI_IDE_LINK_CTL_PART_ENC(x)	 (((x) >> 10) & 0xf)  /* Partial Header Encryption Mode */
+#define  PCI_IDE_LINK_CTL_ALG(x)	 (((x) >> 14) & 0x1f) /* Selected Algorithm */
+#define  PCI_IDE_LINK_CTL_TC(x)		 (((x) >> 19) & 0x7)  /* Traffic Class */
+#define  PCI_IDE_LINK_CTL_ID(x)		 (((x) >> 24) & 0xff) /* Stream ID */
+#define  PCI_IDE_LINK_CTL_ID_MASK	 0xff000000
+
+
+/* Link IDE Stream Status Register */
+#define  PCI_IDE_LINK_STS_STATUS(x)	((x) & 0xf) /* Link IDE Stream State */
+#define  PCI_IDE_LINK_STS_RECVD_INTEGRITY_CHECK	0x80000000 /* Received Integrity Check Fail Msg */
+/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */
+#define PCI_IDE_SELECTIVE_BLOCK_SIZE(x)  (20 + 12 * (x))
+/* Selective IDE Stream Capability Register */
+#define  PCI_IDE_SEL_CAP		 0
+#define  PCI_IDE_SEL_CAP_ASSOC_NUM(x)	 ((x) & 0xf) /* Address Association Register Blocks Number */
+#define  PCI_IDE_SEL_CAP_ASSOC_MASK	 0xf
+/* Selective IDE Stream Control Register */
+#define  PCI_IDE_SEL_CTL		 4
+#define   PCI_IDE_SEL_CTL_EN		 0x1	/* Selective IDE Stream Enable */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_NPR(x) (((x) >> 2) & 0x3) /* Tx Aggregation Mode NPR */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_PR(x)	 (((x) >> 4) & 0x3) /* Tx Aggregation Mode PR */
+#define   PCI_IDE_SEL_CTL_TX_AGGR_CPL(x) (((x) >> 6) & 0x3) /* Tx Aggregation Mode CPL */
+#define   PCI_IDE_SEL_CTL_PCRC_EN	 0x100	/* PCRC Enable */
+#define   PCI_IDE_SEL_CTL_CFG_EN	 0x200	/* Selective IDE for Configuration Requests */
+#define   PCI_IDE_SEL_CTL_PART_ENC(x)	 (((x) >> 10) & 0xf)  /* Partial Header Encryption Mode */
+#define   PCI_IDE_SEL_CTL_ALG(x)	 (((x) >> 14) & 0x1f) /* Selected Algorithm */
+#define   PCI_IDE_SEL_CTL_TC(x)		 (((x) >> 19) & 0x7)  /* Traffic Class */
+#define   PCI_IDE_SEL_CTL_DEFAULT	 0x400000 /* Default Stream */
+#define   PCI_IDE_SEL_CTL_TEE_LIMITED	 (1 << 23) /* TEE-Limited Stream */
+#define   PCI_IDE_SEL_CTL_ID_MASK	 0xff000000
+#define   PCI_IDE_SEL_CTL_ID_MAX	 255
+/* Selective IDE Stream Status Register */
+#define  PCI_IDE_SEL_STS		 8
+#define   PCI_IDE_SEL_STS_STATUS(x)	((x) & 0xf) /* Selective IDE Stream State */
+#define   PCI_IDE_SEL_STS_RECVD_INTEGRITY_CHECK	0x80000000 /* Received Integrity Check Fail Msg */
+/* IDE RID Association Register 1 */
+#define  PCI_IDE_SEL_RID_1		 12
+#define   PCI_IDE_SEL_RID_1_LIMIT_MASK	 0xffff00
+/* IDE RID Association Register 2 */
+#define  PCI_IDE_SEL_RID_2		 16
+#define   PCI_IDE_SEL_RID_2_VALID	 0x1
+#define   PCI_IDE_SEL_RID_2_BASE_MASK	 0x00ffff00
+#define   PCI_IDE_SEL_RID_2_SEG_MASK	 0xff000000
+/* Selective IDE Address Association Register Block, up to PCI_IDE_SEL_CAP_ASSOC_NUM */
+#define  PCI_IDE_SEL_ADDR_1(x)		     (20 + (x) * 12)
+#define   PCI_IDE_SEL_ADDR_1_VALID	     0x1
+#define   PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK   0x000fff0
+#define   PCI_IDE_SEL_ADDR_1_BASE_LOW_SHIFT  20
+#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK  0xfff0000
+#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_SHIFT 20
+/* IDE Address Association Register 2 is "Memory Limit Upper" */
+/* IDE Address Association Register 3 is "Memory Base Upper" */
+#define  PCI_IDE_SEL_ADDR_2(x)		(24 + (x) * 12)
+#define  PCI_IDE_SEL_ADDR_3(x)		(28 + (x) * 12)
+
 #endif /* LINUX_PCI_REGS_H */

---

## [6] Dan Williams — 2024-12-05
*Subject: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

The PCIe 6.1 specification, section 11, introduces the Trusted Execution
Environment (TEE) Device Interface Security Protocol (TDISP).  This
interface definition builds upon Component Measurement and
Authentication (CMA), and link Integrity and Data Encryption (IDE). It
adds support for assigning devices (PCI physical or virtual function) to
a confidential VM such that the assigned device is enabled to access
guest private memory protected by technologies like Intel TDX, AMD
SEV-SNP, RISCV COVE, or ARM CCA.

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
to pci-sysfs. The work in progress CONFIG_PCI_CMA (software
kernel-native PCI authentication) that can depend on a local to the PCI
core implementation, CONFIG_PCI_TSM needs to be prepared for late
loading of the platform TSM driver. Consider that the TSM driver may
itself be a PCI driver. Userspace can watch /sys/class/tsm/tsm0/uevent
to know when the PCI core has TSM services enabled.

The common verbs that the low-level TSM drivers implement are defined by
'struct pci_tsm_ops'. For now only 'connect' and 'disconnect' are
defined for secure session and IDE establishment. The 'probe' and
'remove' operations setup per-device context representing the device's
security manager (DSM). Note that there is only one DSM expected per
physical PCI function, and that coordinates a variable number of
assignable interfaces to CVMs.

The locking allows for multiple devices to be executing commands
simultaneously, one outstanding command per-device and an rwsem flushes
all in-flight commands when a TSM low-level driver/device is removed.

Thanks to Wu Hao for his work on an early draft of this support.

Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Acked-by: Bjorn Helgaas <bhelgaas@google.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-bus-pci |   42 ++++
 MAINTAINERS                             |    2 
 drivers/pci/Kconfig                     |   13 +
 drivers/pci/Makefile                    |    1 
 drivers/pci/pci-sysfs.c                 |    4 
 drivers/pci/pci.h                       |   10 +
 drivers/pci/probe.c                     |    1 
 drivers/pci/remove.c                    |    3 
 drivers/pci/tsm.c                       |  293 +++++++++++++++++++++++++++++++
 drivers/virt/coco/host/tsm-core.c       |   19 ++
 include/linux/pci-tsm.h                 |   83 +++++++++
 include/linux/pci.h                     |    3 
 include/linux/tsm.h                     |    4 
 include/uapi/linux/pci_regs.h           |    1 
 14 files changed, 476 insertions(+), 3 deletions(-)
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 include/linux/pci-tsm.h

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 5da6a14dc326..0d742ef41aa7 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -583,3 +583,45 @@ Description:
 		enclosure-specific indications "specific0" to "specific7",
 		hence the corresponding led class devices are unavailable if
 		the DSM interface is used.
+
+What:		/sys/bus/pci/devices/.../tsm/
+Date:		July 2024
+Contact:	linux-coco@lists.linux.dev
+Description:
+		This directory only appears if a physical device function supports
+		authentication (PCIe CMA-SPDM), interface security (PCIe TDISP), and is
+		accepted for secure operation by the platform TSM driver. This attribute
+		directory appears dynamically after the platform TSM driver loads. So,
+		only after the /sys/class/tsm/tsm0 device arrives can tools assume that
+		devices without a tsm/ attribute directory will never have one, before
+		that, the security capabilities of the device relative to the platform
+		TSM are unknown. See Documentation/ABI/testing/sysfs-class-tsm.
+
+What:		/sys/bus/pci/devices/.../tsm/connect
+Date:		July 2024
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) Writing "1" to this file triggers the platform TSM (TEE Security
+		Manager) to establish a connection with the device.  This typically
+		includes an SPDM (DMTF Security Protocols and Data Models) session over
+		PCIe DOE (Data Object Exchange) and may also include PCIe IDE (Integrity
+		and Data Encryption) establishment.
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
index abaabbc39134..8f28a2d9bbc6 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23843,8 +23843,10 @@ M:	Dan Williams <dan.j.williams@intel.com>
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
index 4e5236c456f5..8dab60dadb7d 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -124,6 +124,19 @@ config PCI_ATS
 config PCI_IDE
 	bool
 
+config PCI_TSM
+	bool "TEE Security Manager for PCI Device Security"
+	select PCI_IDE
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
 	bool
 
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
index 7679d75d71e5..7e1ed3440a50 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1696,6 +1696,10 @@ const struct attribute_group *pci_dev_attr_groups[] = {
 #endif
 #ifdef CONFIG_PCIEASPM
 	&aspm_ctrl_attr_group,
+#endif
+#ifdef CONFIG_PCI_TSM
+	&pci_tsm_auth_attr_group,
+	&pci_tsm_attr_group,
 #endif
 	NULL,
 };
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 0305f497b28a..0537fc72d5be 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -458,6 +458,16 @@ void pci_ide_init(struct pci_dev *dev);
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
index e22f515a8da9..7cddde3cb0ed 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2518,6 +2518,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
 	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
+	pci_tsm_init(dev);		/* TEE Security Manager connection */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
diff --git a/drivers/pci/remove.c b/drivers/pci/remove.c
index efc37fcb73e2..fd4ccafed067 100644
--- a/drivers/pci/remove.c
+++ b/drivers/pci/remove.c
@@ -55,6 +55,9 @@ static void pci_destroy_dev(struct pci_dev *dev)
 
 	pci_npem_remove(dev);
 
+	/* before device_del() to keep config cycle access */
+	pci_tsm_destroy(dev);
+
 	device_del(&dev->dev);
 
 	down_write(&pci_bus_sem);
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
new file mode 100644
index 000000000000..04e9257a6e41
--- /dev/null
+++ b/drivers/pci/tsm.c
@@ -0,0 +1,293 @@
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
+#include <linux/pci.h>
+#include <linux/pci-doe.h>
+#include <linux/sysfs.h>
+#include <linux/xarray.h>
+#include <linux/pci-tsm.h>
+#include <linux/bitfield.h>
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
+static int pci_tsm_disconnect(struct pci_dev *pdev)
+{
+	struct pci_tsm *pci_tsm = pdev->tsm;
+
+	lockdep_assert_held(&pci_tsm_rwsem);
+	if_not_guard(mutex_intr, &pci_tsm->lock)
+		return -EINTR;
+
+	if (pci_tsm->state < PCI_TSM_CONNECT)
+		return 0;
+	if (pci_tsm->state < PCI_TSM_INIT)
+		return -ENXIO;
+
+	tsm_ops->disconnect(pdev);
+	pci_tsm->state = PCI_TSM_INIT;
+
+	return 0;
+}
+
+static int pci_tsm_connect(struct pci_dev *pdev)
+{
+	struct pci_tsm *pci_tsm = pdev->tsm;
+	int rc;
+
+	lockdep_assert_held(&pci_tsm_rwsem);
+	if_not_guard(mutex_intr, &pci_tsm->lock)
+		return -EINTR;
+
+	if (pci_tsm->state >= PCI_TSM_CONNECT)
+		return 0;
+	if (pci_tsm->state < PCI_TSM_INIT)
+		return -ENXIO;
+
+	rc = tsm_ops->connect(pdev);
+	if (rc)
+		return rc;
+	pci_tsm->state = PCI_TSM_CONNECT;
+	return 0;
+}
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
+	if_not_guard(rwsem_read_intr, &pci_tsm_rwsem)
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
+
+	if_not_guard(rwsem_read_intr, &pci_tsm_rwsem)
+		return -EINTR;
+	if (!pdev->tsm)
+		return -ENXIO;
+	return sysfs_emit(buf, "%d\n", pdev->tsm->state >= PCI_TSM_CONNECT);
+}
+static DEVICE_ATTR_RW(connect);
+
+static bool pci_tsm_group_visible(struct kobject *kobj)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct pci_dev *pdev = to_pci_dev(dev);
+
+	if (pdev->tsm)
+		return true;
+	return false;
+}
+DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm);
+
+static struct attribute *pci_tsm_attrs[] = {
+	&dev_attr_connect.attr,
+	NULL,
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
+	 * When device authentication is TSM owned, 'authenticated' is
+	 * identical to the connect state.
+	 */
+	return connect_show(dev, attr, buf);
+}
+static DEVICE_ATTR_RO(authenticated);
+
+static struct attribute *pci_tsm_auth_attrs[] = {
+	&dev_attr_authenticated.attr,
+	NULL,
+};
+
+const struct attribute_group pci_tsm_auth_attr_group = {
+	.attrs = pci_tsm_auth_attrs,
+	.is_visible = SYSFS_GROUP_VISIBLE(pci_tsm),
+};
+
+static void dsm_remove(struct pci_dsm *dsm)
+{
+	if (!dsm)
+		return;
+	tsm_ops->remove(dsm);
+}
+DEFINE_FREE(dsm_remove, struct pci_dsm *, if (_T) dsm_remove(_T))
+
+static bool is_physical_endpoint(struct pci_dev *pdev)
+{
+	if (!pci_is_pcie(pdev))
+		return false;
+
+	if (pdev->is_virtfn)
+		return false;
+
+	if (pci_pcie_type(pdev) != PCI_EXP_TYPE_ENDPOINT)
+		return false;
+
+	return true;
+}
+
+static void __pci_tsm_init(struct pci_dev *pdev)
+{
+	bool tee_cap;
+
+	if (!is_physical_endpoint(pdev))
+		return;
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
+	struct pci_tsm *pci_tsm __free(kfree) = kzalloc(sizeof(*pci_tsm), GFP_KERNEL);
+	if (!pci_tsm)
+		return;
+
+	/*
+	 * If a physical device has any security capabilities it may be
+	 * a candidate to connect with the platform TSM
+	 */
+	struct pci_dsm *dsm __free(dsm_remove) = tsm_ops->probe(pdev);
+
+	pci_dbg(pdev, "Device security capabilities detected (%s%s ), TSM %s\n",
+		pdev->ide_cap ? " ide" : "", tee_cap ? " tee" : "",
+		dsm ? "attach" : "skip");
+
+	if (!dsm)
+		return;
+
+	mutex_init(&pci_tsm->lock);
+	pci_tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					       PCI_DOE_PROTO_CMA);
+	if (!pci_tsm->doe_mb) {
+		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
+		return;
+	}
+
+	pci_tsm->state = PCI_TSM_INIT;
+	pci_tsm->dsm = no_free_ptr(dsm);
+	pdev->tsm = no_free_ptr(pci_tsm);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+	if (pci_tsm_owner_attr_group)
+		sysfs_merge_group(&pdev->dev.kobj, pci_tsm_owner_attr_group);
+}
+
+void pci_tsm_init(struct pci_dev *pdev)
+{
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	__pci_tsm_init(pdev);
+}
+
+int pci_tsm_register(const struct pci_tsm_ops *ops, const struct attribute_group *grp)
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
+EXPORT_SYMBOL_GPL(pci_tsm_register);
+
+static void __pci_tsm_destroy(struct pci_dev *pdev)
+{
+	struct pci_tsm *pci_tsm = pdev->tsm;
+
+	if (!pci_tsm)
+		return;
+
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+	if (pci_tsm->state > PCI_TSM_INIT)
+		pci_tsm_disconnect(pdev);
+	tsm_ops->remove(pci_tsm->dsm);
+	pdev->tsm = NULL;
+	if (pci_tsm_owner_attr_group)
+		sysfs_unmerge_group(&pdev->dev.kobj, pci_tsm_owner_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	kfree(pci_tsm);
+}
+
+void pci_tsm_destroy(struct pci_dev *pdev)
+{
+	guard(rwsem_write)(&pci_tsm_rwsem);
+	__pci_tsm_destroy(pdev);
+}
+
+void pci_tsm_unregister(const struct pci_tsm_ops *ops)
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
+EXPORT_SYMBOL_GPL(pci_tsm_unregister);
+
+int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
+			 const void *req, size_t req_sz, void *resp,
+			 size_t resp_sz)
+{
+	if (!pdev->tsm || !pdev->tsm->doe_mb)
+		return -ENXIO;
+
+	return pci_doe(pdev->tsm->doe_mb, PCI_VENDOR_ID_PCI_SIG, type, req,
+		       req_sz, resp, resp_sz);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_doe_transfer);
diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/host/tsm-core.c
index 0ee738fc40ed..21270210b03f 100644
--- a/drivers/virt/coco/host/tsm-core.c
+++ b/drivers/virt/coco/host/tsm-core.c
@@ -8,11 +8,13 @@
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
+#include <linux/pci-tsm.h>
 
 static DECLARE_RWSEM(tsm_core_rwsem);
 static struct class *tsm_class;
 static struct tsm_subsys {
 	struct device dev;
+	const struct pci_tsm_ops *pci_ops;
 } *tsm_subsys;
 
 static struct tsm_subsys *
@@ -40,7 +42,8 @@ static void put_tsm_subsys(struct tsm_subsys *subsys)
 DEFINE_FREE(put_tsm_subsys, struct tsm_subsys *,
 	    if (!IS_ERR_OR_NULL(_T)) put_tsm_subsys(_T))
 struct tsm_subsys *tsm_register(struct device *parent,
-				const struct attribute_group **groups)
+				const struct attribute_group **groups,
+				const struct pci_tsm_ops *pci_ops)
 {
 	struct device *dev;
 	int rc;
@@ -62,10 +65,20 @@ struct tsm_subsys *tsm_register(struct device *parent,
 	if (rc)
 		return ERR_PTR(rc);
 
+	rc = pci_tsm_register(pci_ops, NULL);
+	if (rc) {
+		dev_err(parent, "PCI initialization failure: %pe\n",
+			ERR_PTR(rc));
+		return ERR_PTR(rc);
+	}
+
 	rc = device_add(dev);
-	if (rc)
+	if (rc) {
+		pci_tsm_unregister(pci_ops);
 		return ERR_PTR(rc);
+	}
 
+	subsys->pci_ops = pci_ops;
 	tsm_subsys = no_free_ptr(subsys);
 
 	return tsm_subsys;
@@ -80,7 +93,9 @@ void tsm_unregister(struct tsm_subsys *subsys)
 		return;
 	}
 
+	pci_tsm_unregister(subsys->pci_ops);
 	device_unregister(&subsys->dev);
+
 	tsm_subsys = NULL;
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
new file mode 100644
index 000000000000..beb0d68129bc
--- /dev/null
+++ b/include/linux/pci-tsm.h
@@ -0,0 +1,83 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef __PCI_TSM_H
+#define __PCI_TSM_H
+#include <linux/mutex.h>
+
+struct pci_dev;
+
+/**
+ * struct pci_dsm - Device Security Manager context
+ * @pdev: physical device back pointer
+ */
+struct pci_dsm {
+	struct pci_dev *pdev;
+};
+
+enum pci_tsm_state {
+	PCI_TSM_ERR = -1,
+	PCI_TSM_INIT,
+	PCI_TSM_CONNECT,
+};
+
+/**
+ * struct pci_tsm - Platform TSM transport context
+ * @state: reflect device initialized, connected, or bound
+ * @lock: protect @state vs pci_tsm_ops invocation
+ * @doe_mb: PCIe Data Object Exchange mailbox
+ * @dsm: TSM driver device context established by pci_tsm_ops.probe
+ */
+struct pci_tsm {
+	enum pci_tsm_state state;
+	struct mutex lock;
+	struct pci_doe_mb *doe_mb;
+	struct pci_dsm *dsm;
+};
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
+	struct pci_dsm *(*probe)(struct pci_dev *pdev);
+	void (*remove)(struct pci_dsm *dsm);
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
+int pci_tsm_register(const struct pci_tsm_ops *ops,
+		     const struct attribute_group *grp);
+void pci_tsm_unregister(const struct pci_tsm_ops *ops);
+int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
+			 const void *req, size_t req_sz, void *resp,
+			 size_t resp_sz);
+#else
+static inline int pci_tsm_register(const struct pci_tsm_ops *ops,
+				   const struct attribute_group *grp)
+{
+	return 0;
+}
+static inline void pci_tsm_unregister(const struct pci_tsm_ops *ops)
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
index 50811b7655dd..a0900e7d2012 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -535,6 +535,9 @@ struct pci_dev {
 	u16		ide_cap;	/* Link Integrity & Data Encryption */
 	u16		sel_ide_cap;	/* - Selective Stream register block */
 	int		nr_ide_mem;	/* - Address range limits for streams */
+#endif
+#ifdef CONFIG_PCI_TSM
+	struct pci_tsm *tsm;		/* TSM operation state */
 #endif
 	u16		acs_cap;	/* ACS Capability offset */
 	u8		supported_speeds; /* Supported Link Speeds Vector */
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 1a97459fc23e..46b9a0c6ea4e 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -111,7 +111,9 @@ struct tsm_report_ops {
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_subsys;
+struct pci_tsm_ops;
 struct tsm_subsys *tsm_register(struct device *parent,
-				const struct attribute_group **groups);
+				const struct attribute_group **groups,
+				const struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_subsys *subsys);
 #endif /* __TSM_H */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 9635b27d2485..19bba65a262c 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -499,6 +499,7 @@
 #define  PCI_EXP_DEVCAP_PWR_VAL	0x03fc0000 /* Slot Power Limit Value */
 #define  PCI_EXP_DEVCAP_PWR_SCL	0x0c000000 /* Slot Power Limit Scale */
 #define  PCI_EXP_DEVCAP_FLR     0x10000000 /* Function Level Reset */
+#define  PCI_EXP_DEVCAP_TEE     0x40000000 /* TEE I/O (TDISP) Support */
 #define PCI_EXP_DEVCTL		0x08	/* Device Control */
 #define  PCI_EXP_DEVCTL_CERE	0x0001	/* Correctable Error Reporting En. */
 #define  PCI_EXP_DEVCTL_NFERE	0x0002	/* Non-Fatal Error Reporting Enable */

---

## [7] Dan Williams — 2024-12-05
*Subject: [PATCH 06/11] samples/devsec: PCI device-security bus / endpoint
 sample*

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
 MAINTAINERS             |    1 
 samples/Kconfig         |   15 +
 samples/Makefile        |    1 
 samples/devsec/Makefile |   10 +
 samples/devsec/bus.c    |  695 +++++++++++++++++++++++++++++++++++++++++++++++
 samples/devsec/common.c |   26 ++
 samples/devsec/devsec.h |    7 
 samples/devsec/tsm.c    |  113 ++++++++
 8 files changed, 868 insertions(+)
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/tsm.c

diff --git a/MAINTAINERS b/MAINTAINERS
index 8f28a2d9bbc6..9dba89d42af6 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23848,6 +23848,7 @@ F:	drivers/virt/coco/guest/
 F:	drivers/virt/coco/host/
 F:	include/linux/pci-tsm.h
 F:	include/linux/tsm.h
+F:	samples/devsec/
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index b288d9991d27..9581757bfa67 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -293,6 +293,21 @@ config SAMPLE_CGROUP
 
 source "samples/rust/Kconfig"
 
+config SAMPLE_DEVSEC
+	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
+	depends on PCI
+	depends on X86 # missing PCI_DOMAINS_GENERIC support
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
index b85fa64390c5..da1829049249 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -39,3 +39,4 @@ obj-$(CONFIG_SAMPLE_KMEMLEAK)		+= kmemleak/
 obj-$(CONFIG_SAMPLE_CORESIGHT_SYSCFG)	+= coresight/
 obj-$(CONFIG_SAMPLE_FPROBE)		+= fprobe/
 obj-$(CONFIG_SAMPLES_RUST)		+= rust/
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
index 000000000000..47dbe4e1b648
--- /dev/null
+++ b/samples/devsec/bus.c
@@ -0,0 +1,695 @@
+// SPDX-License-Identifier: GPL-2.0-only
+// Copyright(c) 2024 Intel Corporation. All rights reserved.
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
+#define NR_STREAMS 1
+#define NR_ADDR_ASSOC 1
+#define NR_DEVSEC_DEVS 1
+
+struct devsec {
+	struct pci_sysdata sysdata;
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
+				} stream[NR_STREAMS];
+			} ide __packed;
+			char ide_regs[sizeof(struct devsec_ide)];
+		};
+		struct pci_bridge_emul bridge;
+	} *devsec_ports[NR_DEVSEC_ROOT_PORTS];
+	struct devsec_dev {
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
+	if (bus == devsec->bus)
+		return devsec_port_config_read(devsec, devfn, pos, size, val);
+	else if (bus->parent == devsec->bus)
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
+	u8 type, index;
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
+	index = FIELD_GET(PCI_DOE_DATA_OBJECT_DISC_REQ_3_INDEX, doe->req[2]);
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
+	if (bus == devsec->bus)
+		return devsec_port_config_write(devsec, bus, devfn, pos, size,
+						val);
+	else if (bus->parent == devsec->bus)
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
+/* borrowed from vmd_find_free_domain() */
+static int find_free_domain(void)
+{
+	int domain = 0xffff;
+	struct pci_bus *bus = NULL;
+
+	while ((bus = pci_find_next_bus(bus)) != NULL)
+		domain = max_t(int, domain, pci_domain_nr(bus));
+	return domain + 1;
+}
+
+static void destroy_iomem_pool(void *data)
+{
+	struct devsec *devsec = data;
+
+	gen_pool_destroy(devsec->iomem_pool);
+}
+
+static void destroy_bus(void *data)
+{
+	struct devsec *devsec = data;
+
+	pci_stop_root_bus(devsec->bus);
+	pci_remove_root_bus(devsec->bus);
+}
+
+static void destroy_devs(void *data)
+{
+	struct devsec *devsec = data;
+	int i;
+
+	for (i = ARRAY_SIZE(devsec->devsec_devs) - 1; i >= 0; i--) {
+		struct devsec_dev *devsec_dev = devsec->devsec_devs[i];
+
+		if (!devsec_dev)
+			continue;
+		gen_pool_free(devsec->iomem_pool, devsec_dev->mmio_range.start,
+			      range_len(&devsec_dev->mmio_range));
+		kfree(devsec_dev);
+		devsec->devsec_devs[i] = NULL;
+	}
+}
+
+static unsigned build_ext_cap_header(u32 id, u32 ver, u32 next)
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
+		   FIELD_PREP(PCI_IDE_CAP_SELECTIVE_STREAMS_MASK, NR_STREAMS);
+
+	for (int i = 0; i < NR_STREAMS; i++)
+		ide->stream[i].cap =
+			FIELD_PREP(PCI_IDE_SEL_CAP_ASSOC_MASK, NR_ADDR_ASSOC);
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
+static int alloc_devs(struct devsec *devsec)
+{
+	struct device *dev = devsec->dev;
+	int i, rc;
+
+	rc = devm_add_action_or_reset(dev, destroy_devs, devsec);
+	if (rc)
+		return rc;
+
+	for (i = 0; i < ARRAY_SIZE(devsec->devsec_devs); i++) {
+		struct devsec_dev *devsec_dev __free(kfree) =
+			kzalloc(sizeof(*devsec_dev), GFP_KERNEL);
+		struct genpool_data_align data = {
+			.align = MMIO_SIZE,
+		};
+		u64 phys;
+
+		if (!devsec_dev)
+			return -ENOMEM;
+
+		phys = gen_pool_alloc_algo(devsec->iomem_pool, MMIO_SIZE,
+					   gen_pool_first_fit_align, &data);
+		if (!phys)
+			return -ENOMEM;
+
+		devsec_dev->mmio_range = (struct range) {
+			.start = phys,
+			.end = phys + MMIO_SIZE - 1,
+		};
+		init_dev_cfg(devsec_dev);
+		devsec->devsec_devs[i] = no_free_ptr(devsec_dev);
+	}
+
+	return 0;
+}
+
+static void destroy_ports(void *data)
+{
+	struct devsec *devsec = data;
+	int i;
+
+	for (i = ARRAY_SIZE(devsec->devsec_ports) - 1; i >= 0; i--) {
+		struct devsec_port *devsec_port = devsec->devsec_ports[i];
+
+		if (!devsec_port)
+			continue;
+		pci_bridge_emul_cleanup(&devsec_port->bridge);
+		kfree(devsec_port);
+		devsec->devsec_ports[i] = NULL;
+	}
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
+	int rc;
+
+	bridge->conf.vendor = cpu_to_le16(0x8086);
+	bridge->conf.device = cpu_to_le16(0x7075);
+	bridge->subsystem_vendor_id = cpu_to_le16(0x8086);
+	bridge->conf.class_revision = cpu_to_le32(0x1);
+
+	bridge->conf.pref_mem_base = cpu_to_le16(PCI_PREF_RANGE_TYPE_64);
+	bridge->conf.pref_mem_limit = cpu_to_le16(PCI_PREF_RANGE_TYPE_64);
+
+	bridge->has_pcie = true;
+	bridge->pcie_conf.devcap = cpu_to_le16(PCI_EXP_DEVCAP_FLR);
+	bridge->pcie_conf.lnksta = cpu_to_le16(PCI_EXP_LNKSTA_CLS_2_5GB);
+
+	bridge->data = devsec_port;
+	bridge->ops = &devsec_bridge_ops;
+
+	init_ide(&devsec_port->ide);
+
+	rc = pci_bridge_emul_init(bridge, 0);
+	if (rc)
+		return rc;
+
+	return 0;
+}
+
+static int alloc_ports(struct devsec *devsec)
+{
+	struct device *dev = devsec->dev;
+	int i, rc;
+
+	rc = devm_add_action_or_reset(dev, destroy_ports, devsec);
+	if (rc)
+		return rc;
+
+	for (i = 0; i < ARRAY_SIZE(devsec->devsec_ports); i++) {
+		struct devsec_port *devsec_port __free(kfree) =
+			kzalloc(sizeof(*devsec_port), GFP_KERNEL);
+
+		if (!devsec_port)
+			return -ENOMEM;
+
+		rc = init_port(devsec_port);
+		if (rc)
+			return rc;
+		devsec->devsec_ports[i] = no_free_ptr(devsec_port);
+	}
+
+	return 0;
+}
+
+static int __init devsec_bus_probe(struct platform_device *pdev)
+{
+	int rc;
+	LIST_HEAD(resources);
+	struct devsec *devsec;
+	struct pci_sysdata *sd;
+	u64 mmio_size = SZ_64G;
+	struct device *dev = &pdev->dev;
+	u64 mmio_start = iomem_resource.end + 1 - SZ_64G;
+
+	devsec = devm_kzalloc(dev, sizeof(*devsec), GFP_KERNEL);
+	if (!devsec)
+		return -ENOMEM;
+
+	devsec->dev = dev;
+	devsec->iomem_pool = gen_pool_create(ilog2(SZ_2M), NUMA_NO_NODE);
+	if (!devsec->iomem_pool)
+		return -ENOMEM;
+
+	rc = devm_add_action_or_reset(dev, destroy_iomem_pool, devsec);
+	if (rc)
+		return rc;
+
+	rc = gen_pool_add(devsec->iomem_pool, mmio_start, mmio_size,
+			  NUMA_NO_NODE);
+	if (rc)
+		return rc;
+
+	devsec->resource[0] = (struct resource) {
+		.name = "DEVSEC BUSES",
+		.start = 0,
+		.end = NR_DEVSEC_BUSES + NR_DEVSEC_ROOT_PORTS - 1,
+		.flags = IORESOURCE_BUS | IORESOURCE_PCI_FIXED,
+	};
+	pci_add_resource(&resources, &devsec->resource[0]);
+
+	devsec->resource[1] = (struct resource) {
+		.name = "DEVSEC MMIO",
+		.start = mmio_start,
+		.end = mmio_start + mmio_size - 1,
+		.flags = IORESOURCE_MEM | IORESOURCE_MEM_64,
+	};
+	pci_add_resource(&resources, &devsec->resource[1]);
+
+	sd = &devsec->sysdata;
+	devsec_sysdata = sd;
+	sd->domain = find_free_domain();
+	if (sd->domain < 0)
+		return sd->domain;
+
+	devsec->bus = pci_create_root_bus(dev, 0, &devsec_ops,
+					  &devsec->sysdata, &resources);
+	if (!devsec->bus) {
+		pci_free_resource_list(&resources);
+		return -ENOMEM;
+	}
+
+	rc = devm_add_action_or_reset(dev, destroy_bus, devsec);
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
+	pci_scan_child_bus(devsec->bus);
+
+	return 0;
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
index 000000000000..9b6f4022f241
--- /dev/null
+++ b/samples/devsec/common.c
@@ -0,0 +1,26 @@
+// SPDX-License-Identifier: GPL-2.0-only
+// Copyright(c) 2024 Intel Corporation. All rights reserved.
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
index 000000000000..794a9898ee2d
--- /dev/null
+++ b/samples/devsec/devsec.h
@@ -0,0 +1,7 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+// Copyright(c) 2024 Intel Corporation. All rights reserved.
+
+#ifndef __DEVSEC_H__
+#define __DEVSEC_H__
+extern struct pci_sysdata *devsec_sysdata;
+#endif /* __DEVSEC_H__ */
diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
new file mode 100644
index 000000000000..d446ab8879d8
--- /dev/null
+++ b/samples/devsec/tsm.c
@@ -0,0 +1,113 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+// Copyright(c) 2024 Intel Corporation. All rights reserved.
+
+#define dev_fmt(fmt) "devsec: " fmt
+#include <linux/platform_device.h>
+#include <linux/pci-tsm.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include "devsec.h"
+
+struct devsec_dsm {
+	struct pci_dsm pci;
+};
+
+static struct devsec_dsm *to_devsec_dsm(struct pci_dsm *dsm)
+{
+	return container_of(dsm, struct devsec_dsm, pci);
+}
+
+static struct pci_dsm *devsec_tsm_pci_probe(struct pci_dev *pdev)
+{
+	struct devsec_dsm *devsec_dsm;
+
+	if (pdev->sysdata != devsec_sysdata)
+		return NULL;
+
+	devsec_dsm = kzalloc(sizeof(*devsec_dsm), GFP_KERNEL);
+	if (!devsec_dsm)
+		return NULL;
+
+	devsec_dsm->pci.pdev = pdev;
+	pci_dbg(pdev, "tsm enabled\n");
+	return &devsec_dsm->pci;
+}
+
+static void devsec_tsm_pci_remove(struct pci_dsm *dsm)
+{
+	struct devsec_dsm *devsec_dsm = to_devsec_dsm(dsm);
+
+	pci_dbg(dsm->pdev, "tsm disabled\n");
+	kfree(devsec_dsm);
+}
+
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
+static void devsec_tsm_remove(void *tsm)
+{
+	tsm_unregister(tsm);
+}
+
+static int devsec_tsm_probe(struct platform_device *pdev)
+{
+	struct tsm_subsys *tsm;
+
+	tsm = tsm_register(&pdev->dev, NULL, &devsec_pci_ops);
+	if (IS_ERR(tsm))
+		return PTR_ERR(tsm);
+
+	return devm_add_action_or_reset(&pdev->dev, devsec_tsm_remove,
+					tsm);
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

## [8] Dan Williams — 2024-12-05
*Subject: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability enumeration*

PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
enumerates new link capabilities and status added for Gen 6 devices. One
of the link details enumerated in that register block is the "Segment
Captured" status in the Device Status 3 register. That status is
relevant for enabling IDE (Integrity & Data Encryption) whereby
Selective IDE streams can be limited to a given requester id range
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
 drivers/pci/pci.h             |   11 +++++++++++
 drivers/pci/probe.c           |    1 +
 include/linux/pci.h           |    1 +
 include/uapi/linux/pci_regs.h |    7 +++++++
 4 files changed, 20 insertions(+)

diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 0537fc72d5be..6565eb72ded2 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -444,6 +444,17 @@ static inline void pci_doe_destroy(struct pci_dev *pdev) { }
 static inline void pci_doe_disconnected(struct pci_dev *pdev) { }
 #endif
 
+static inline void pci_dev3_init(struct pci_dev *pdev)
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
 #ifdef CONFIG_PCI_NPEM
 void pci_npem_create(struct pci_dev *dev);
 void pci_npem_remove(struct pci_dev *dev);
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 7cddde3cb0ed..6c1fe6354d26 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2517,6 +2517,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_rcec_init(dev);		/* Root Complex Event Collector */
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
+	pci_dev3_init(dev);		/* Device 3 capabilities */
 	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 	pci_tsm_init(dev);		/* TEE Security Manager connection */
 
diff --git a/include/linux/pci.h b/include/linux/pci.h
index a0900e7d2012..10d035395a43 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -443,6 +443,7 @@ struct pci_dev {
 	unsigned int	pasid_enabled:1;	/* Process Address Space ID */
 	unsigned int	pri_enabled:1;		/* Page Request Interface */
 	unsigned int	tph_enabled:1;		/* TLP Processing Hints */
+	unsigned int	fm_enabled:1;		/* Flit Mode (segment captured) */
 	unsigned int	is_managed:1;		/* Managed via devres */
 	unsigned int	is_msi_managed:1;	/* MSI release via devres installed */
 	unsigned int	needs_freset:1;		/* Requires fundamental reset */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 19bba65a262c..c61231861b51 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -749,6 +749,7 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
+#define PCI_EXT_CAP_ID_DEV3	0x2F	/* Device 3 Capability/Control/Status */
 #define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
 #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE
 
@@ -1210,6 +1211,12 @@
 #define PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL		0x00ff0000
 #define PCI_DOE_DATA_OBJECT_DISC_RSP_3_NEXT_INDEX	0xff000000
 
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

## [9] Dan Williams — 2024-12-05
*Subject: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

There are two components to establishing an encrypted link, provisioning
the stream in config-space, and programming the keys into the link layer
via the IDE_KM (key management) protocol. These helpers enable the
former, and are in support of TSM coordinated IDE_KM. When / if native
IDE establishment arrives it will share this same config-space
provisioning flow, but for now IDE_KM, in any form, is saved for a
follow-on change.

With the TSM implementations of SEV-TIO and TDX Connect in mind this
abstracts small differences in those implementations. For example, TDX
Connect handles Root Port registers updates while SEV-TIO expects System
Software to update the Root Port registers. This is the rationale for
the PCI_IDE_SETUP_ROOT_PORT flag.

The other design detail for TSM-coordinated IDE establishment is that
the TSM manages allocation of stream-ids, this is why the stream_id is
passed in to pci_ide_stream_setup().

The flow is:

pci_ide_stream_probe()
  Gather stream settings (devid and address filters)
pci_ide_stream_setup()
  Program the stream settings into the endpoint, and optionally Root Port)
pci_ide_enable_stream()
  Run the stream after IDE_KM

In support of system administrators auditing where platform IDE stream
resources are being spent, the allocated stream is reflected as a
symlink from the host-bridge to the endpoint.

Thanks to Wu Hao for a draft implementation of this infrastructure.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge      |   28 +++
 drivers/pci/ide.c                                  |  192 ++++++++++++++++++++
 drivers/pci/pci.h                                  |    4 
 drivers/pci/probe.c                                |    1 
 include/linux/pci-ide.h                            |   33 +++
 include/linux/pci.h                                |    4 
 6 files changed, 262 insertions(+)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 create mode 100644 include/linux/pci-ide.h

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
new file mode 100644
index 000000000000..15dafb46b176
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -0,0 +1,28 @@
+What:		/sys/devices/pciDDDDD:BB
+		/sys/devices/.../pciDDDDD:BB
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		A PCI host bridge device parents a PCI bus device topology. PCI
+		controllers may also parent host bridges. The DDDDD:BB format
+		convey the PCI domain number and the bus number for root ports
+		of the host bridge.
+
+What:		pciDDDDD:BB/firmware_node
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) Symlink to the platform firmware device object "companion"
+		of the host bridge. For example, an ACPI device with an _HID of
+		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00).
+
+What:		pciDDDDD:BB/streamN:DDDDD:BB:DD:F
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host-bridge has established a secure connection,
+		typically PCIe IDE, between a host-bridge an endpoint, this
+		symlink appears. The primary function is to account how many
+		streams can be returned to the available secure streams pool by
+		invoking the tsm/disconnect flow. The link points to the
+		endpoint PCI device at domain:DDDDD bus:BB device:DD function:F.
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index a0c09d9e0b75..c37f35f0d2c0 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -5,6 +5,9 @@
 
 #define dev_fmt(fmt) "PCI/IDE: " fmt
 #include <linux/pci.h>
+#include <linux/sysfs.h>
+#include <linux/pci-ide.h>
+#include <linux/bitfield.h>
 #include "pci.h"
 
 static int sel_ide_offset(u16 cap, int stream_id, int nr_ide_mem)
@@ -71,3 +74,192 @@ void pci_ide_init(struct pci_dev *pdev)
 	pdev->sel_ide_cap = sel_ide_cap;
 	pdev->nr_ide_mem = nr_ide_mem;
 }
+
+void pci_init_host_bridge_ide(struct pci_host_bridge *hb)
+{
+	hb->ide_stream_res =
+		DEFINE_RES_MEM_NAMED(0, 0, "IDE Address Association");
+}
+
+/*
+ * Retrieve stream association parameters for devid (RID) and resources
+ * (device address ranges)
+ */
+void pci_ide_stream_probe(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	int num_vf = pci_num_vf(pdev);
+
+	*ide = (struct pci_ide) { .stream_id = -1 };
+
+	if (pdev->fm_enabled)
+		ide->domain = pci_domain_nr(pdev->bus);
+	ide->devid_start = pci_dev_id(pdev);
+
+	/* for SR-IOV case, cover all VFs */
+	if (num_vf)
+		ide->devid_end = PCI_DEVID(pci_iov_virtfn_bus(pdev, num_vf),
+					   pci_iov_virtfn_devfn(pdev, num_vf));
+	else
+		ide->devid_end = ide->devid_start;
+
+	/* TODO: address association probing... */
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_probe);
+
+static void __pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	int pos;
+
+	pos = sel_ide_offset(pdev->sel_ide_cap, ide->stream_id,
+			     pdev->nr_ide_mem);
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
+	for (int i = ide->nr_mem - 1; i >= 0; i--) {
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), 0);
+	}
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, 0);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, 0);
+}
+
+static void __pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	int pos;
+	u32 val;
+
+	pos = sel_ide_offset(pdev->sel_ide_cap, ide->stream_id,
+			     pdev->nr_ide_mem);
+
+	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT_MASK, ide->devid_end);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
+
+	val = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
+	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE_MASK, ide->devid_start) |
+	      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG_MASK, ide->domain);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
+
+	for (int i = 0; i < ide->nr_mem; i++) {
+		val = FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |
+		      FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK,
+				 lower_32_bits(ide->mem[i].start) >>
+					 PCI_IDE_SEL_ADDR_1_BASE_LOW_SHIFT) |
+		      FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK,
+				 lower_32_bits(ide->mem[i].end) >>
+					 PCI_IDE_SEL_ADDR_1_LIMIT_LOW_SHIFT);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), val);
+
+		val = upper_32_bits(ide->mem[i].end);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), val);
+
+		val = upper_32_bits(ide->mem[i].start);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), val);
+	}
+}
+
+/*
+ * Establish IDE stream parameters in @pdev and, optionally, its root port
+ */
+int pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide,
+			 enum pci_ide_flags flags)
+{
+	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	int mem = 0, rc;
+
+	if (ide->stream_id < 0 || ide->stream_id > U8_MAX) {
+		pci_err(pdev, "Setup fail: Invalid stream id: %d\n", ide->stream_id);
+		return -ENXIO;
+	}
+
+	if (test_and_set_bit_lock(ide->stream_id, hb->ide_stream_ids)) {
+		pci_err(pdev, "Setup fail: Busy stream id: %d\n",
+			ide->stream_id);
+		return -EBUSY;
+	}
+
+	ide->name = kasprintf(GFP_KERNEL, "stream%d:%s", ide->stream_id,
+			      dev_name(&pdev->dev));
+	if (!ide->name) {
+		rc = -ENOMEM;
+		goto err_name;
+	}
+
+	rc = sysfs_create_link(&hb->dev.kobj, &pdev->dev.kobj, ide->name);
+	if (rc)
+		goto err_link;
+
+	for (mem = 0; mem < ide->nr_mem; mem++)
+		if (!__request_region(&hb->ide_stream_res, ide->mem[mem].start,
+				      range_len(&ide->mem[mem]), ide->name,
+				      0)) {
+			pci_err(pdev,
+				"Setup fail: stream%d: address association conflict [%#llx-%#llx]\n",
+				ide->stream_id, ide->mem[mem].start,
+				ide->mem[mem].end);
+
+			rc = -EBUSY;
+			goto err;
+		}
+
+	__pci_ide_stream_setup(pdev, ide);
+	if (flags & PCI_IDE_SETUP_ROOT_PORT)
+		__pci_ide_stream_setup(rp, ide);
+
+	return 0;
+err:
+	for (; mem >= 0; mem--)
+		__release_region(&hb->ide_stream_res, ide->mem[mem].start,
+				 range_len(&ide->mem[mem]));
+	sysfs_remove_link(&hb->dev.kobj, ide->name);
+err_link:
+	kfree(ide->name);
+err_name:
+	clear_bit_unlock(ide->stream_id, hb->ide_stream_ids);
+	return rc;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_setup);
+
+void pci_ide_enable_stream(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	int pos;
+	u32 val;
+
+	pos = sel_ide_offset(pdev->sel_ide_cap, ide->stream_id,
+			     pdev->nr_ide_mem);
+
+	val = FIELD_PREP(PCI_IDE_SEL_CTL_ID_MASK, ide->stream_id) |
+	      FIELD_PREP(PCI_IDE_SEL_CTL_DEFAULT, 1);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
+}
+EXPORT_SYMBOL_GPL(pci_ide_enable_stream);
+
+void pci_ide_disable_stream(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	int pos;
+
+	pos = sel_ide_offset(pdev->sel_ide_cap, ide->stream_id,
+			     pdev->nr_ide_mem);
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
+}
+EXPORT_SYMBOL_GPL(pci_ide_disable_stream);
+
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide,
+			     enum pci_ide_flags flags)
+{
+	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+
+	__pci_ide_stream_teardown(pdev, ide);
+	if (flags & PCI_IDE_SETUP_ROOT_PORT)
+		__pci_ide_stream_teardown(rp, ide);
+
+	for (int i = ide->nr_mem - 1; i >= 0; i--)
+		__release_region(&hb->ide_stream_res, ide->mem[i].start,
+				 range_len(&ide->mem[i]));
+	sysfs_remove_link(&hb->dev.kobj, ide->name);
+	kfree(ide->name);
+	clear_bit_unlock(ide->stream_id, hb->ide_stream_ids);
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_teardown);
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 6565eb72ded2..b267fabfd542 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -465,8 +465,12 @@ static inline void pci_npem_remove(struct pci_dev *dev) { }
 
 #ifdef CONFIG_PCI_IDE
 void pci_ide_init(struct pci_dev *dev);
+void pci_init_host_bridge_ide(struct pci_host_bridge *bridge);
 #else
 static inline void pci_ide_init(struct pci_dev *dev) { }
+static inline void pci_init_host_bridge_ide(struct pci_host_bridge *bridge)
+{
+}
 #endif
 
 #ifdef CONFIG_PCI_TSM
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 6c1fe6354d26..667faa18ced2 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -608,6 +608,7 @@ static void pci_init_host_bridge(struct pci_host_bridge *bridge)
 	bridge->native_dpc = 1;
 	bridge->domain_nr = PCI_DOMAIN_NR_NOT_SET;
 	bridge->native_cxl_error = 1;
+	pci_init_host_bridge_ide(bridge);
 
 	device_initialize(&bridge->dev);
 }
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
new file mode 100644
index 000000000000..24e08a413645
--- /dev/null
+++ b/include/linux/pci-ide.h
@@ -0,0 +1,33 @@
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
+struct pci_ide {
+	int domain;
+	u16 devid_start;
+	u16 devid_end;
+	int stream_id;
+	const char *name;
+	int nr_mem;
+	struct range mem[16];
+};
+
+void pci_ide_stream_probe(struct pci_dev *pdev, struct pci_ide *ide);
+
+enum pci_ide_flags {
+	PCI_IDE_SETUP_ROOT_PORT = BIT(0),
+};
+
+int pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide,
+			 enum pci_ide_flags flags);
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide,
+			     enum pci_ide_flags flags);
+void pci_ide_enable_stream(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_disable_stream(struct pci_dev *pdev, struct pci_ide *ide);
+#endif /* __PCI_IDE_H__ */
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 10d035395a43..5d9fc498bc70 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -601,6 +601,10 @@ struct pci_host_bridge {
 	int		domain_nr;
 	struct list_head windows;	/* resource_entry */
 	struct list_head dma_ranges;	/* dma ranges resource list */
+#ifdef CONFIG_PCI_IDE			/* track IDE stream id allocation */
+	DECLARE_BITMAP(ide_stream_ids, PCI_IDE_SEL_CTL_ID_MAX + 1);
+	struct resource ide_stream_res; /* track ide stream address association */
+#endif
 	u8 (*swizzle_irq)(struct pci_dev *, u8 *); /* Platform IRQ swizzler */
 	int (*map_irq)(const struct pci_dev *, u8, u8);
 	void (*release_fn)(struct pci_host_bridge *);

---

## [10] Dan Williams — 2024-12-05
*Subject: [PATCH 09/11] PCI/IDE: Report available IDE streams*

The limited number of link-encryption (IDE) streams that a given set of
host-bridges supports is a platform specific detail. Provide
pci_set_nr_ide_streams() as a generic facility for either platform TSM
drivers, or in the future PCI core native IDE, to report the number
available streams. After invoking pci_set_nr_ide_streams() an
"available_secure_streams" attribute appears in PCI Host Bridge sysfs to
convey how many streams are available for IDE establishment.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge      |   11 +++++
 drivers/pci/ide.c                                  |   46 ++++++++++++++++++++
 drivers/pci/pci.h                                  |    3 +
 drivers/pci/probe.c                                |   11 ++++-
 include/linux/pci.h                                |    9 ++++
 5 files changed, 79 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index 15dafb46b176..1a3249f20e48 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -26,3 +26,14 @@ Description:
 		streams can be returned to the available secure streams pool by
 		invoking the tsm/disconnect flow. The link points to the
 		endpoint PCI device at domain:DDDDD bus:BB device:DD function:F.
+
+What:		pciDDDDD:BB/available_secure_streams
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host-bridge has root ports that support PCIe IDE
+		(link encryption and integrity protection) there may be a
+		limited number of streams that can be used for establishing new
+		secure links. This attribute decrements upon secure link setup,
+		and increments upon secure link teardown. The in-use stream
+		count is determined by counting stream symlinks.
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index c37f35f0d2c0..0abc19b341ab 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -75,8 +75,54 @@ void pci_ide_init(struct pci_dev *pdev)
 	pdev->nr_ide_mem = nr_ide_mem;
 }
 
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
+		bitmap_weight(hb->ide_stream_ids, PCI_IDE_SEL_CTL_ID_MAX + 1);
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
+void pci_set_nr_ide_streams(struct pci_host_bridge *hb, int nr)
+{
+	hb->nr_ide_streams = nr;
+	sysfs_update_group(&hb->dev.kobj, &pci_ide_attr_group);
+}
+EXPORT_SYMBOL_NS_GPL(pci_set_nr_ide_streams, PCI_IDE);
+
 void pci_init_host_bridge_ide(struct pci_host_bridge *hb)
 {
+	hb->nr_ide_streams = -1;
 	hb->ide_stream_res =
 		DEFINE_RES_MEM_NAMED(0, 0, "IDE Address Association");
 }
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index b267fabfd542..76f18b07e081 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -466,11 +466,14 @@ static inline void pci_npem_remove(struct pci_dev *dev) { }
 #ifdef CONFIG_PCI_IDE
 void pci_ide_init(struct pci_dev *dev);
 void pci_init_host_bridge_ide(struct pci_host_bridge *bridge);
+extern struct attribute_group pci_ide_attr_group;
+#define PCI_IDE_ATTR_GROUP (&pci_ide_attr_group)
 #else
 static inline void pci_ide_init(struct pci_dev *dev) { }
 static inline void pci_init_host_bridge_ide(struct pci_host_bridge *bridge)
 {
 }
+#define PCI_IDE_ATTR_GROUP NULL
 #endif
 
 #ifdef CONFIG_PCI_TSM
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 667faa18ced2..a85ad3b28028 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -589,6 +589,16 @@ static void pci_release_host_bridge_dev(struct device *dev)
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
@@ -622,7 +632,6 @@ struct pci_host_bridge *pci_alloc_host_bridge(size_t priv)
 		return NULL;
 
 	pci_init_host_bridge(bridge);
-	bridge->dev.release = pci_release_host_bridge_dev;
 
 	return bridge;
 }
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 5d9fc498bc70..eae3d11710db 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -604,6 +604,7 @@ struct pci_host_bridge {
 #ifdef CONFIG_PCI_IDE			/* track IDE stream id allocation */
 	DECLARE_BITMAP(ide_stream_ids, PCI_IDE_SEL_CTL_ID_MAX + 1);
 	struct resource ide_stream_res; /* track ide stream address association */
+	int nr_ide_streams;
 #endif
 	u8 (*swizzle_irq)(struct pci_dev *, u8 *); /* Platform IRQ swizzler */
 	int (*map_irq)(const struct pci_dev *, u8, u8);
@@ -654,6 +655,14 @@ void pci_set_host_bridge_release(struct pci_host_bridge *bridge,
 				 void (*release_fn)(struct pci_host_bridge *),
 				 void *release_data);
 
+#ifdef CONFIG_PCI_IDE
+void pci_set_nr_ide_streams(struct pci_host_bridge *hb, int nr);
+#else
+static inline void pci_set_nr_ide_streams(struct pci_host_bridge *hb, int nr)
+{
+}
+#endif
+
 int pcibios_root_bridge_prepare(struct pci_host_bridge *bridge);
 
 #define PCI_REGION_FLAG_MASK	0x0fU	/* These bits of resource flags tell us the PCI region flags */

---

## [11] Dan Williams — 2024-12-05
*Subject: [PATCH 10/11] PCI/TSM: Report active IDE streams*

Given that the platform TSM owns IDE stream id allocation, report the
active streams via the TSM class device. Establish a symlink from the
class device to the PCI endpoint device consuming the stream, named by
the stream id.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm |   10 ++++++++++
 drivers/virt/coco/host/tsm-core.c         |   17 +++++++++++++++++
 include/linux/tsm.h                       |    4 ++++
 3 files changed, 31 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 7503f04a9eb9..d6830f5f8628 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -8,3 +8,13 @@ Description:
 		signals when the PCI layer is able to support establishment of
 		link encryption and other device-security features coordinated
 		through the platform tsm.
+
+What:		/sys/class/tsm/tsm0/streamN:DDDDD:BB:DD:F
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a host-bridge has established a secure connection via
+		the platform TSM, symlink appears. The primary function of this
+		is have a system global review of TSM resource consumption
+		across host bridges. The link points to the endpoint PCI device
+		at domain:DDDDD bus:BB device:DD function:F.
diff --git a/drivers/virt/coco/host/tsm-core.c b/drivers/virt/coco/host/tsm-core.c
index 21270210b03f..d78a9faf507d 100644
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
@@ -100,6 +103,20 @@ void tsm_unregister(struct tsm_subsys *subsys)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+/* must be invoked between tsm_register / tsm_unregister */
+int tsm_register_ide_stream(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	return sysfs_create_link(&tsm_subsys->dev.kobj, &pdev->dev.kobj,
+				 ide->name);
+}
+EXPORT_SYMBOL_GPL(tsm_register_ide_stream);
+
+void tsm_unregister_ide_stream(struct pci_ide *ide)
+{
+	sysfs_remove_link(&tsm_subsys->dev.kobj, ide->name);
+}
+EXPORT_SYMBOL_GPL(tsm_unregister_ide_stream);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_subsys *subsys = container_of(dev, typeof(*subsys), dev);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 46b9a0c6ea4e..ce95e9130436 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -116,4 +116,8 @@ struct tsm_subsys *tsm_register(struct device *parent,
 				const struct attribute_group **groups,
 				const struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_subsys *subsys);
+struct pci_dev;
+struct pci_ide;
+int tsm_register_ide_stream(struct pci_dev *pdev, struct pci_ide *ide);
+void tsm_unregister_ide_stream(struct pci_ide *ide);
 #endif /* __TSM_H */

---

## [12] Dan Williams — 2024-12-05
*Subject: [PATCH 11/11] samples/devsec: Add sample IDE establishment*

Exercise common setup and teardown flows for a sample platform TSM
driver that implements the TSM 'connect' and 'disconnect' flows.

This is both a template for platform specific implementations and a test
case for the shared infrastructure.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 samples/devsec/tsm.c |   85 ++++++++++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 82 insertions(+), 3 deletions(-)

diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
index d446ab8879d8..a8894d08f323 100644
--- a/samples/devsec/tsm.c
+++ b/samples/devsec/tsm.c
@@ -4,11 +4,14 @@
 #define dev_fmt(fmt) "devsec: " fmt
 #include <linux/platform_device.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 #include <linux/module.h>
 #include <linux/pci.h>
 #include <linux/tsm.h>
 #include "devsec.h"
 
+#define DEVSEC_NR_IDE_STREAMS 4
+
 struct devsec_dsm {
 	struct pci_dsm pci;
 };
@@ -42,13 +45,60 @@ static void devsec_tsm_pci_remove(struct pci_dsm *dsm)
 	kfree(devsec_dsm);
 }
 
+/* protected by tsm_ops lock */
+static DECLARE_BITMAP(devsec_stream_ids, DEVSEC_NR_IDE_STREAMS);
+static struct devsec_stream_info {
+	struct pci_dev *pdev;
+	struct pci_ide ide;
+} devsec_streams[DEVSEC_NR_IDE_STREAMS];
+
 static int devsec_tsm_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct pci_ide *ide;
+	int rc, stream_id;
+
+	stream_id =
+		find_first_zero_bit(devsec_stream_ids, DEVSEC_NR_IDE_STREAMS);
+	if (stream_id == DEVSEC_NR_IDE_STREAMS)
+		return -EBUSY;
+	set_bit(stream_id, devsec_stream_ids);
+	ide = &devsec_streams[stream_id].ide;
+	pci_ide_stream_probe(pdev, ide);
+
+	ide->stream_id = stream_id;
+	rc = pci_ide_stream_setup(pdev, ide, PCI_IDE_SETUP_ROOT_PORT);
+	if (rc)
+		return rc;
+	rc = tsm_register_ide_stream(pdev, ide);
+	if (rc)
+		goto err;
+
+	devsec_streams[stream_id].pdev = pdev;
+	pci_ide_enable_stream(pdev, ide);
+	return 0;
+err:
+	pci_ide_stream_teardown(pdev, ide, PCI_IDE_SETUP_ROOT_PORT);
+	return rc;
 }
 
 static void devsec_tsm_disconnect(struct pci_dev *pdev)
 {
+	struct pci_ide *ide;
+	int i;
+
+	for_each_set_bit(i, devsec_stream_ids, DEVSEC_NR_IDE_STREAMS)
+		if (devsec_streams[i].pdev == pdev)
+			break;
+
+	if (i >= DEVSEC_NR_IDE_STREAMS)
+		return;
+
+	ide = &devsec_streams[i].ide;
+	pci_ide_disable_stream(pdev, ide);
+	tsm_unregister_ide_stream(ide);
+	pci_ide_stream_teardown(pdev, ide, PCI_IDE_SETUP_ROOT_PORT);
+	devsec_streams[i].pdev = NULL;
+	clear_bit(i, devsec_stream_ids);
 }
 
 static const struct pci_tsm_ops devsec_pci_ops = {
@@ -63,16 +113,44 @@ static void devsec_tsm_remove(void *tsm)
 	tsm_unregister(tsm);
 }
 
+static void set_nr_ide_streams(int nr)
+{
+	struct pci_dev *pdev = NULL;
+
+	for_each_pci_dev(pdev) {
+		struct pci_host_bridge *hb;
+
+		if (pdev->sysdata != devsec_sysdata)
+			continue;
+		hb = pci_find_host_bridge(pdev->bus);
+		if (hb->nr_ide_streams >= 0)
+			continue;
+		pci_set_nr_ide_streams(hb, nr);
+	}
+}
+
+static void devsec_tsm_ide_teardown(void *data)
+{
+	set_nr_ide_streams(-1);
+}
+
 static int devsec_tsm_probe(struct platform_device *pdev)
 {
 	struct tsm_subsys *tsm;
+	int rc;
 
 	tsm = tsm_register(&pdev->dev, NULL, &devsec_pci_ops);
 	if (IS_ERR(tsm))
 		return PTR_ERR(tsm);
 
-	return devm_add_action_or_reset(&pdev->dev, devsec_tsm_remove,
-					tsm);
+	rc = devm_add_action_or_reset(&pdev->dev, devsec_tsm_remove, tsm);
+	if (rc)
+		return rc;
+
+	set_nr_ide_streams(DEVSEC_NR_IDE_STREAMS);
+
+	return devm_add_action_or_reset(&pdev->dev, devsec_tsm_ide_teardown,
+					NULL);
 }
 
 static struct platform_driver devsec_tsm_driver = {
@@ -109,5 +187,6 @@ static void __exit devsec_tsm_exit(void)
 }
 module_exit(devsec_tsm_exit);
 
+MODULE_IMPORT_NS(PCI_IDE);
 MODULE_LICENSE("GPL");
 MODULE_DESCRIPTION("Device Security Sample Infrastructure: Platform TSM Driver");

---

## [13] kernel test robot — 2024-12-06
*Subject: Re: [PATCH 09/11] PCI/IDE: Report available IDE streams*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 40384c840ea1944d7c5a392e8975ed088ecf0b37]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/configfs-tsm-Namespace-TSM-report-symbols/20241206-064224
base:   40384c840ea1944d7c5a392e8975ed088ecf0b37
patch link:    https://lore.kernel.org/r/173343744869.1074769.12345445223792172558.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH 09/11] PCI/IDE: Report available IDE streams
config: mips-mtx1_defconfig (https://download.01.org/0day-ci/archive/20241206/202412060733.L2zUE7gx-lkp@intel.com/config)
compiler: clang version 16.0.6 (https://github.com/llvm/llvm-project 7cbf1a2591520c2491aa35339f227775f4d3adf6)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20241206/202412060733.L2zUE7gx-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202412060733.L2zUE7gx-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> drivers/pci/probe.c:597:33: warning: unused variable 'pci_host_bridge_type' [-Wunused-const-variable]
   static const struct device_type pci_host_bridge_type = {
                                   ^
   1 warning generated.


vim +/pci_host_bridge_type +597 drivers/pci/probe.c

   596	
 > 597	static const struct device_type pci_host_bridge_type = {
   598		.groups = pci_host_bridge_groups,
   599		.release = pci_release_host_bridge_dev,
   600	};
   601

---

## [14] kernel test robot — 2024-12-06
*Subject: Re: [PATCH 09/11] PCI/IDE: Report available IDE streams*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 40384c840ea1944d7c5a392e8975ed088ecf0b37]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/configfs-tsm-Namespace-TSM-report-symbols/20241206-064224
base:   40384c840ea1944d7c5a392e8975ed088ecf0b37
patch link:    https://lore.kernel.org/r/173343744869.1074769.12345445223792172558.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH 09/11] PCI/IDE: Report available IDE streams
config: i386-buildonly-randconfig-006 (https://download.01.org/0day-ci/archive/20241206/202412060857.Kn0HyAFH-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20241206/202412060857.Kn0HyAFH-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202412060857.Kn0HyAFH-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> drivers/pci/probe.c:597:33: warning: 'pci_host_bridge_type' defined but not used [-Wunused-const-variable=]
     597 | static const struct device_type pci_host_bridge_type = {
         |                                 ^~~~~~~~~~~~~~~~~~~~


vim +/pci_host_bridge_type +597 drivers/pci/probe.c

   596	
 > 597	static const struct device_type pci_host_bridge_type = {
   598		.groups = pci_host_bridge_groups,
   599		.release = pci_release_host_bridge_dev,
   600	};
   601

---

## [15] kernel test robot — 2024-12-06
*Subject: Re: [PATCH 06/11] samples/devsec: PCI device-security bus / endpoint
 sample*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 40384c840ea1944d7c5a392e8975ed088ecf0b37]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/configfs-tsm-Namespace-TSM-report-symbols/20241206-064224
base:   40384c840ea1944d7c5a392e8975ed088ecf0b37
patch link:    https://lore.kernel.org/r/173343743095.1074769.17985181033044298157.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH 06/11] samples/devsec: PCI device-security bus / endpoint sample
config: i386-kismet-CONFIG_TSM-CONFIG_SAMPLE_DEVSEC-0-0 (https://download.01.org/0day-ci/archive/20241206/202412061214.KMe4sOrh-lkp@intel.com/config)
reproduce: (https://download.01.org/0day-ci/archive/20241206/202412061214.KMe4sOrh-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202412061214.KMe4sOrh-lkp@intel.com/

kismet warnings: (new ones prefixed by >>)
>> kismet: WARNING: unmet direct dependencies detected for TSM when selected by SAMPLE_DEVSEC
   WARNING: unmet direct dependencies detected for TSM
     Depends on [n]: VIRT_DRIVERS [=n]
     Selected by [y]:
     - SAMPLE_DEVSEC [=y] && SAMPLES [=y] && PCI [=y] && X86 [=y]

---

## [16] Greg KH — 2024-12-06
*Subject: Re: [PATCH 00/11] PCI/TSM: Core infrastructure for PCI device
 security (TDISP)*

On Thu, Dec 05, 2024 at 02:23:15PM -0800, Dan Williams wrote:
> Changes since the RFC [1]:
> - Wording changes and cleanups in "PCI/TSM: Authenticate devices via

Wow, you aren't kidding about the acronym soup problem, this is a mess.
And does any of this relate to the existing drivers/tee/ subsystem in
any way?

Anyhow, this patch series looks sane, nice work.

> Note that devsec_tsm is for near term staging of vendor TSM
> implementations. The expectation is that every piece of new core

How are you going to enforce this?  By removing infrastructure?
Normally we can't add infrastructure unless there's a real user, and
when you add a real user then you see all the things that need to be
chagned.

So are you ok with the apis and interfaces moving around over time here?
I think I only see sysfs files being exported so hopefully this
shouldn't be that big of a deal for userspace to deal with, but I don't
know what userspace is supposed to do with any of this, is there
external tools to talk to / set up, these devices?

thanks,

greg k-h

---

## [17] Dan Williams — 2024-12-06
*Subject: Re: [PATCH 00/11] PCI/TSM: Core infrastructure for PCI device
 security (TDISP)*

Greg KH wrote:
> On Thu, Dec 05, 2024 at 02:23:15PM -0800, Dan Williams wrote:
> > Changes since the RFC [1]:

No relation to the subsystem, but if I understand correctly the modern
AMD security co-processor that runs SEV-SNP firmware is a descendant, at
least conceptually, of the 'amdtee' device.

Meanwhile Intel, RISC-V and ARM implemented new CPU execution modes to
run their platform security software.

> Anyhow, this patch series looks sane, nice work.
> 

Mainly by moving slowly and carefully.

> By removing infrastructure?

If necessary.

> Normally we can't add infrastructure unless there's a real user, and
> when you add a real user then you see all the things that need to be

What you see here is only 1/3 of the solution, and it has taken quite a
while to get to this point. Meanwhile there are several "hardware
validation" / RFC quality stacks floating around with the end-to-end
flow supported (3/3 solution).

So, there is a wealth of RFCs to draw from and have near constant line
of sight on the next topic to build an upstream consensus solution.
There is low risk that upstream carries something that does not have 2-3
vendor implementations in mind or needs more than a couple kernel cycles
to follow in behind the sample implementation.

I hope to corral all those vendor staging trees into a unified staging
tree where upstream-ready infra can bubble out of that cauldron, similar
to Paolo's kvm-coco-queue.

> So are you ok with the apis and interfaces moving around over time here?
> I think I only see sysfs files being exported so hopefully this

For this first 1/3 of the effort I expect just a simple udev policy to
say "for the 4 potential PCIe links that can be encrypted on this host,
these are the 4 endpoint devices that get those resources, echo 1 to
'connect' when you see them".

For the 2nd 1/3 of the effort the ABI changes will be augmenting VFIO,
GUEST_MEM_FD, and IOMMUFD ABI to coordinate secure device assignment to
confidential VMs.

The last 1/3 of the ABI will be guest side to fetch and validate device
certificates and security measurements. Here I expect work-in-progress
efforts like the TDM effort [1] to be the consumer of a new netlink ABI
to pull this security collateral. At least, that was the consensus ABI
discussed at Plumbers in this year's PCI device authentication BoF.

So I expect to still be enjoying a large bowl of acronym soup well into
next year.

[1]: https://github.com/confidential-containers/guest-components/pull/290
     (Samuel, is there a newer version of this somewhere?)

---

## [18] kernel test robot — 2024-12-09
*Subject: Re: [PATCH 06/11] samples/devsec: PCI device-security bus / endpoint
 sample*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 40384c840ea1944d7c5a392e8975ed088ecf0b37]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/configfs-tsm-Namespace-TSM-report-symbols/20241206-064224
base:   40384c840ea1944d7c5a392e8975ed088ecf0b37
patch link:    https://lore.kernel.org/r/173343743095.1074769.17985181033044298157.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH 06/11] samples/devsec: PCI device-security bus / endpoint sample
config: i386-randconfig-r123-20241206 (https://download.01.org/0day-ci/archive/20241207/202412070726.Au4TQYYS-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20241207/202412070726.Au4TQYYS-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202412070726.Au4TQYYS-lkp@intel.com/

All warnings (new ones prefixed by >>):

   samples/devsec/bus.c: In function 'doe_process':
>> samples/devsec/bus.c:172:18: warning: variable 'index' set but not used [-Wunused-but-set-variable]
     172 |         u8 type, index;
         |                  ^~~~~

Kconfig warnings: (for reference only)
   WARNING: unmet direct dependencies detected for TSM
   Depends on [n]: VIRT_DRIVERS [=n]
   Selected by [y]:
   - SAMPLE_DEVSEC [=y] && SAMPLES [=y] && PCI [=y] && X86 [=y]

sparse warnings: (new ones prefixed by >>)
>> samples/devsec/bus.c:539:37: sparse: sparse: incorrect type in assignment (different base types) @@     expected unsigned short [usertype] subsystem_vendor_id @@     got restricted __le16 [usertype] @@
   samples/devsec/bus.c:539:37: sparse:     expected unsigned short [usertype] subsystem_vendor_id
   samples/devsec/bus.c:539:37: sparse:     got restricted __le16 [usertype]
>> samples/devsec/bus.c:546:34: sparse: sparse: incorrect type in assignment (different base types) @@     expected restricted __le32 [usertype] devcap @@     got restricted __le16 [usertype] @@
   samples/devsec/bus.c:546:34: sparse:     expected restricted __le32 [usertype] devcap
   samples/devsec/bus.c:546:34: sparse:     got restricted __le16 [usertype]
>> samples/devsec/bus.c:609:59: sparse: sparse: cast truncates bits from constant value (1000000000 becomes 0)

vim +/index +172 samples/devsec/bus.c

   168	
   169	/* just indicate support for CMA */
   170	static void doe_process(struct devsec_dev_doe *doe)
   171	{
 > 172		u8 type, index;
   173		u16 vid;
   174	
   175		vid = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_VID, doe->req[0]);
   176		type = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_TYPE, doe->req[0]);
   177	
   178		if (vid != PCI_VENDOR_ID_PCI_SIG) {
   179			doe->read_ttl = -1;
   180			return;
   181		}
   182	
   183		if (type != PCI_DOE_PROTOCOL_DISCOVERY) {
   184			doe->read_ttl = -1;
   185			return;
   186		}
   187	
   188		index = FIELD_GET(PCI_DOE_DATA_OBJECT_DISC_REQ_3_INDEX, doe->req[2]);
   189	
   190		doe->rsp[0] = doe->req[0];
   191		doe->rsp[1] = FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_2_LENGTH, 3);
   192		doe->read_ttl = 3;
   193		doe->rsp[2] = FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_VID,
   194					 PCI_VENDOR_ID_PCI_SIG) |
   195			      FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL,
   196					 PCI_DOE_FEATURE_CMA) |
   197			      FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_NEXT_INDEX, 0);
   198	}
   199

---

## [19] Ilpo Järvinen — 2024-12-09
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Thu, 5 Dec 2024, Dan Williams wrote:

> PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
> enumerates new link capabilities and status added for Gen 6 devices. One

Should save/restore too be added for DEV3_CTL?

---

## [20] Aneesh Kumar K.V — 2024-12-10
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Hi Dan,

> +#define  PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(x)	(((x) >> 16) & 0xff) /* Selective IDE Streams */

Should this be

#define  PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(x)	((((x) >> 16) & 0xff) + 1) /* Selective IDE Streams */

We do loop as below in ide.c

	for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val); i++) {
		if (i == 0) {
			pci_read_config_dword(pdev, sel_ide_cap, &val);
			nr_ide_mem = PCI_IDE_SEL_CAP_ASSOC_NUM(val);

-aneesh

---

## [21] Aneesh Kumar K.V — 2024-12-10
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Hi Dan,

Dan Williams <dan.j.williams@intel.com> writes:
> +int pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide,
> +			 enum pci_ide_flags flags)

Considering we are using the hostbridge ide_stream_ids bitmap, why is
the stream_id allocation not generic? ie, any reason why a stream id alloc
like below will not work?

static int pcie_ide_sel_streamid_alloc(struct pci_dev *pdev)
{
	int stream_id;
	struct pci_host_bridge *hb;

	hb = pci_find_host_bridge(pdev->bus);

	stream_id = find_first_zero_bit(hb->ide_stream_ids, hb->nr_ide_streams);
	if (stream_id >= hb->nr_ide_streams)
		return -EBUSY;

	return stream_id;
}

-aneesh

---

## [22] Aneesh Kumar K.V — 2024-12-10
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> Hi Dan,
>

Also wondering should the stream id be unique at the rootport level? ie
for a config like below

# pwd
/sys/devices/platform/40000000.pci/pci0000:00
# ls
0000:00:01.0              available_secure_streams  power
0000:00:02.0              pci_bus                   uevent
# lspci
00:01.0 PCI bridge: ARM Device 0def
00:02.0 PCI bridge: ARM Device 0def
01:00.0 Unassigned class [ff00]: ARM Device ff80
02:00.0 SATA controller: Device 0abc:aced (rev 01)
# 
# lspci -t
-[0000:00]-+-01.0-[01]----00.0
           \-02.0-[02]----00.0
# 


I should be able to use the same stream id to program both the rootports?

-aneesh

---

## [23] Alexey Kardashevskiy — 2024-12-10
*Subject: Re: [PATCH 01/11] configfs-tsm: Namespace TSM report symbols*

On 6/12/24 09:23, Dan Williams wrote:
> In preparation for new + common TSM (TEE Security Manager)
> infrastructure, namespace the TSM report symbols in tsm.h with an

Reviewed-by: Alexey Kardashevskiy <aik@amd.com>


> ---
>   Documentation/ABI/testing/configfs-tsm-report   |    0

---

## [24] Alexey Kardashevskiy — 2024-12-10
*Subject: Re: [PATCH 02/11] coco/guest: Move shared guest CC infrastructure to
 drivers/virt/coco/guest/*

On 6/12/24 09:23, Dan Williams wrote:
> In preparation for creating a new drivers/virt/coco/host/ directory to
> house shared host driver infrastructure for confidential computing, move

Reviewed-by: Alexey Kardashevskiy <aik@amd.com>

> ---
>   MAINTAINERS                      |    2 +-

---

## [25] Alexey Kardashevskiy — 2024-12-10
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

On 6/12/24 09:23, Dan Williams wrote:
> Link encryption is a new PCIe capability defined by "PCIe 6.2 section
> 6.33 Integrity & Data Encryption (IDE)". While it is a standalone port

But why? It is quite easy to support those. Yeah, won't be able to cache 
nr_ide_mem and will have to read more configspace but a specific 
selected stream offset can live in pci_ide from 8/11. Thanks,

> +			 */
> +			if (PCI_IDE_SEL_CAP_ASSOC_NUM(val) != nr_ide_mem) {

---

## [26] Alexey Kardashevskiy — 2024-12-10
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

On 6/12/24 09:23, Dan Williams wrote:
> Link encryption is a new PCIe capability defined by "PCIe 6.2 section
> 6.33 Integrity & Data Encryption (IDE)". While it is a standalone port

0x000fff00 (missing a zero)

> +#define   PCI_IDE_SEL_ADDR_1_BASE_LOW_SHIFT  20
> +#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK  0xfff0000


0xfff00000

31:20 Memory Limit Lower – Corresponds to Address bits [31:20]. Address 
bits [19:0] are implicitly F_FFFFh. RW
19:8 Memory Base Lower – Corresponds to Address bits [31:20]. 
Address[19:0] bits are implicitly 0_0000h.


> +#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_SHIFT 20

I like mine better :) Shows in one place how addr_1 is made:

#define  PCI_IDE_SEL_ADDR_1(v, base, limit) \
	((FIELD_GET(0xfff00000, (limit))  << 20) | \
	(FIELD_GET(0xfff00000, (base)) << 8) | \
	((v) ? 1 : 0))

Also, when something uses "SHIFT", I expect left shift (like, 
PAGE_SHIFT), but this is right shift.

Otherwise, looks good. Thanks,

> +/* IDE Address Association Register 2 is "Memory Limit Upper" */
> +/* IDE Address Association Register 3 is "Memory Base Upper" */

---

## [27] Alexey Kardashevskiy — 2024-12-10
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 6/12/24 09:24, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in config-space, and programming the keys into the link layer

out of curiosity - should it be DEFINE_RES_MEM_NAMED(0, UINT_MAX, "IDE 
Address Association");?


> +}
> +


FIELD_PREP(PCI_IDE_SEL_CTL_EN) is missing here.

And no PCI_IDE_SETUP_ROOT_PORT here, is the platform expected to enable 
it explicitely? If yes, then we do not need PCI_IDE_SETUP_ROOT_PORT 
really. If no, then this needs to enable the stream on the rootport.

Also, my test device wants PCI_IDE_SEL_CTL_TEE_LIMITED to work, I wonder 
how to showel it in here, add a "unsigned dev_sel_ctl" to pci_ide?
And the same comment for PCI_IDE_SEL_CTL_CFG_EN on the rootport. 
"unsigned rootport_sel_ctl"?



> +	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
> +}

Not much point in caching this, real easy to calculate in that one spot.
Thanks,

ps. I'll probably be commenting more on the same things as I try using 
all this :)


> +	u16 devid_start;
> +	u16 devid_end;

---

## [28] Alexey Kardashevskiy — 2024-12-10
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On 6/12/24 09:23, Dan Williams wrote:
> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This

It is sooo small, make me wonder why we need it at all...

>   include/linux/pci-tsm.h                 |   83 +++++++++
>   include/linux/pci.h                     |    3

I thought ages ago it was suggested that DOE/SPDM loop happens in a 
common place and not in the platform driver implementing 
tsm_ops->connect() (but I may have missed the point then).


> +	if (rc)
> +		return rc;

doe_mb and state look are device's attribures so will look more 
appropriate in pci_dsm ("d" from "dsm" is "device"), and pci_tsm would 
be some intimate knowledge of the ccp.ko (==PSP) about PCI PFs ("t" == 
"TEE" == TCB == PSP). Or I got it all wrong?

> +
> +/**


I am trying to wrap my head around your tsm. here is what I got in my tree:
https://github.com/aik/linux/blob/tsm/include/linux/tsm.h

Shortly:

drivers/virt/coco/tsm.ko does sysfs (including "connect" and "bind" to 
control and "certs"/"report" to attest) and implements tsm_dev/tsm_tdi, 
it does not know pci_dev;

drivers/pci/tsm-pci.ko creates/destroys tsm_dev/tsm_dev using tsm.ko;

drivers/crypto/ccp/ccp.ko (the PSP guy) registers:
- tsm_subsys in tsm.ko (which does "connect" and "bind" and
- tsm_bus_subsys in tsm-pci.ko (which does "spdm_forward")
ccp.ko knows about pci_dev and whatever else comes in the future, and 
ccp.ko's "connect" implementation calls the IDE library (I am adopting 
yours now, with some tweaks).

tsm-dev and tsm-tdi embed struct dev each and are added as children to 
PCI devices: no hide/show attrs, no additional TSM pointer in struct 
device or pci_dev, looks like:

aik@sc ~> ls  /sys/bus/pci/devices/0000:e1:04.0/tsm-tdi/tdi:0000:e1:04.0/
device  power  subsystem  tsm_report  tsm_report_user  tsm_tdi_bind 
tsm_tdi_status  tsm_tdi_status_user  uevent

aik@sc ~> ls  /sys/bus/pci/devices/0000:e1:04.0/tsm_dev/
device  power  subsystem  tsm_certs  tsm_cert_slot  tsm_certs_user 
tsm_dev_connect  tsm_dev_status  tsm_meas  tsm_meas_user  uevent

aik@sc ~> ls /sys/class/tsm/tsm0/
device  power  stream0:0000:e1:00.0  subsystem  uevent

aik@sc ~> ls /sys/class/tsm-dev/
tdev:0000:c0:01.1  tdev:0000:e0:01.1  tdev:0000:e1:00.0

aik@sc ~> ls /sys/class/tsm-tdi/
tdi:0000:c0:01.1  tdi:0000:e0:01.1  tdi:0000:e1:00.0  tdi:0000:e1:04.0 
tdi:0000:e1:04.1  tdi:0000:e1:04.2  tdi:0000:e1:04.3


SPDM forwarding seems a bus-agnostic concept, "connect" is a PCI thing 
but pci_dev is only needed for DOE/IDE.

Or is separating struct pci_dev from struct device not worth it and most 
of it should go to tsm-pci.ko? Then what is left for tsm.ko? Thanks,

---

## [29] Bjorn Helgaas — 2024-12-10
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On Thu, Dec 05, 2024 at 02:24:02PM -0800, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in config-space, and programming the keys into the link layer

s/stream-ids/Stream IDs/ to match spec usage (also several other
places)

> The flow is:
> 

Not sure what "devid" is.  Requester ID?  I suppose it's from
PCI_DEVID(), which does turn out to be the PCIe Requester ID.  I don't
think the spec uses a "devid" term, so I'd prefer the term used in the
spec.

> In support of system administrators auditing where platform IDE stream
> resources are being spent, the allocated stream is reflected as a

s/host-bridge/host bridge/ to match typical usage (also elsewhere)

> +++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
> @@ -0,0 +1,28 @@

"Root ports" doesn't seem quite right here; BB is the root bus number,
and makes sense even for conventional PCI.

I know IDE etc is PCIe-specific, but I think saying "the PCI domain
number and root bus number of the host bridge" would be more accurate
since there can be things other than Root Ports on the root bus, e.g.,
conventional PCI devices, RCiEPs, RCECs, etc.

Typical formatting of domain is %04x.

> +What:		pciDDDDD:BB/streamN:DDDDD:BB:DD:F
> +Date:		December, 2024

s/host-bridge an endpoint/host bridge and an endpoint/

> + * Retrieve stream association parameters for devid (RID) and resources
> + * (device address ranges)

This and other exported functions probably should have kernel-doc.
Document only the implemented parts.

> +void pci_ide_stream_probe(struct pci_dev *pdev, struct pci_ide *ide)

> +void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide,
> +			     enum pci_ide_flags flags)

Looks like this relies on the caller to supply the same flags as they
previously supplied to pci_ide_stream_setup()?  Could/should we
remember the flags to remove the possibility of leaking the RP setup
or trying to teardown RP setup that wasn't done?

> +++ b/include/linux/pci.h
> @@ -601,6 +601,10 @@ struct pci_host_bridge {

Seems like overkill to repeat this.  Probably remove the comment on
the #ifdef and s/ide/IDE/ here.

---

## [30] Bjorn Helgaas — 2024-12-10
*Subject: Re: [PATCH 10/11] PCI/TSM: Report active IDE streams*

On Thu, Dec 05, 2024 at 02:24:14PM -0800, Dan Williams wrote:
> Given that the platform TSM owns IDE stream id allocation, report the
> active streams via the TSM class device. Establish a symlink from the

s/stream id/Stream ID/ to match spec usage as a proper noun

> +++ b/Documentation/ABI/testing/sysfs-class-tsm
> @@ -8,3 +8,13 @@ Description:

Typical formatting of domain is %04x, including in existing sysfs
docs.

---

## [31] Bjorn Helgaas — 2024-12-10
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On Thu, Dec 05, 2024 at 02:23:45PM -0800, Dan Williams wrote:
> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This

> +++ b/Documentation/ABI/testing/sysfs-bus-pci
> @@ -583,3 +583,45 @@ Description:

Wrap to fit in 80 columns like the rest of the file.

> +
> +What:		/sys/bus/pci/devices/.../tsm/connect

---

## [32] Bjorn Helgaas — 2024-12-10
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Thu, Dec 05, 2024 at 02:23:56PM -0800, Dan Williams wrote:
> PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,
> enumerates new link capabilities and status added for Gen 6 devices. One

s/requester id/Requester ID/ to match spec usage

> +++ b/include/uapi/linux/pci_regs.h
> @@ -749,6 +749,7 @@

It doesn't look like lspci knows about this; is there something in
progress to add that?

https://git.kernel.org/pub/scm/utils/pciutils/pciutils.git/tree/lib/header.h?id=v3.13.0#n257

>  #define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
>  #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE

---

## [33] Bjorn Helgaas — 2024-12-10
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

I try to make the first word of the subject a verb that says something
about what the patch does, maybe "Enumerate" in this case?

On Thu, Dec 05, 2024 at 02:23:39PM -0800, Dan Williams wrote:
> Link encryption is a new PCIe capability defined by "PCIe 6.2 section
> 6.33 Integrity & Data Encryption (IDE)". While it is a standalone port

Since sec 6.33 doesn't cover the "IDE Extended Capability" (sec
7.9.26), I would word this as "a new PCIe feature" here.

> and endpoint capability, it is also a building block for device security
> defined by "PCIe 6.2 section 11 TEE Device Interface Security Protocol

s/stream-ids/Stream IDs/ to match spec usage

> Add register definitions and basic enumeration for a "selective-stream"
> IDE capability, a follow on change will select the new CONFIG_PCI_IDE

s/root-port/Root Port/ to match spec usage, also below

> +void pci_ide_init(struct pci_dev *pdev)
> +{

> +			 * lets not entertain devices that do not have a
> +			 * constant number of address association blocks

s/lets/Let's/

---

## [34] Ilpo Järvinen — 2024-12-11
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Tue, 10 Dec 2024, Bjorn Helgaas wrote:

> On Thu, Dec 05, 2024 at 02:23:56PM -0800, Dan Williams wrote:
> > PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,

Hi,

I've two patches lying around that add a few Flit mode related fields 
and Dev3 into lspci, although the latter patch doesn't exactly have all 
the fields from Dev3 but at least it would be a good start for many 
things.

I think I'll just post them as is and see where it goes.

> >  #define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
> >  #define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE

---

## [35] Suzuki K Poulose — 2024-12-11
*Subject: Re: [PATCH 01/11] configfs-tsm: Namespace TSM report symbols*

On 05/12/2024 22:23, Dan Williams wrote:
> In preparation for new + common TSM (TEE Security Manager)
> infrastructure, namespace the TSM report symbols in tsm.h with an

> ---
>   Documentation/ABI/testing/configfs-tsm-report   |    0

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [36] Xu Yilun — 2024-12-12
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

> > +/* Selective IDE Stream Capability Register */
> > +#define  PCI_IDE_SEL_CAP		 0

PCI_IDE_SEL_CAP_ASSOC_NUM_MASK is better?

> > +/* Selective IDE Stream Control Register */
> > +#define  PCI_IDE_SEL_CTL		 4

These fields are more likely to be written to the register than read
out, so may need other definitions.

I think generally _XXX(x) Macros are less useful than _MASK because of
FIELD_PREP/GET(), so maybe by default we define _MASK Macros and on
demand define _XXX(x) Macros for all registers.

> > +#define   PCI_IDE_SEL_CTL_PCRC_EN	 0x100	/* PCRC Enable */
> > +#define   PCI_IDE_SEL_CTL_CFG_EN	 0x200	/* Selective IDE for Configuration Requests */

I don't think _SHIFT MACRO is needed, also because of FIELD_PREP/GET().

> 
> I like mine better :) Shows in one place how addr_1 is made:

This Macro is useful for SEL_ADDR_1 but not generally useful for other
registers like SEL_CTRL, which has far more fields to input. So I'd
rather have only _MASK Macros here to make things simpler. This
specific Macro for SEL_ADDR_1 could be put in like pci-ide.h if really
needed.

Thanks,
Yilun

> 
> Also, when something uses "SHIFT", I expect left shift (like, PAGE_SHIFT),

---

## [37] Xu Yilun — 2024-12-12
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

On Tue, Dec 10, 2024 at 08:38:57AM +0530, Aneesh Kumar K.V wrote:
> 
> Hi Dan,

Is it better keep the literal SPEC definition here in pci_reg.h? And ...

> 
> We do loop as below in ide.c

for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val) + 1; i++) {

Thanks,
Yilun

> 		if (i == 0) {
> 			pci_read_config_dword(pdev, sel_ide_cap, &val);

---

## [38] Xu Yilun — 2024-12-12
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

> +static int pci_tsm_disconnect(struct pci_dev *pdev)
> +{

Check PCI_TSM_INIT first, or this condition will never hit.

  if (pci_tsm->state < PCI_TSM_INIT)
	return -ENXIO;
  if (pci_tsm->state < PCI_TSM_CONNECT)
	return 0;

I suggest the same sequence for pci_tsm_connect().

> +
> +	tsm_ops->disconnect(pdev);

[...]

> +
> +static void __pci_tsm_init(struct pci_dev *pdev)

This Filters out virtual functions, just because not ready for support,
is it?

> +
> +	tee_cap = pdev->devcap & PCI_EXP_DEVCAP_TEE;

IIUC, pdev->tsm should be for every pci function (physical or virtual),
pdev->tsm->dsm should be only for physical functions, is it?

> +
> +	pci_dbg(pdev, "Device security capabilities detected (%s%s ), TSM %s\n",

---

## [39] Xu Yilun — 2024-12-12
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

> +static void __pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
> +{

Oh, I missunderstood the _LOW_SHIFT Macros. But still think if they
could be moved out of pci_reg.h. Placing in pci_reg.h makes me think
they are some register field offsets.

Thanks,
Yilun

---

## [40] Alexey Kardashevskiy — 2024-12-18
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

On 12/12/24 17:06, Xu Yilun wrote:
>>> +/* Selective IDE Stream Capability Register */
>>> +#define  PCI_IDE_SEL_CAP		 0

(I saw your comment, just to clarify this bikeshedding :) )

PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK applies to the source (which is 
"base") and PCI_IDE_SEL_ADDR_1_LIMIT_LOW_SHIFT applies to the result 
(which is "addr1").

May be
s/PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK/PCI_IDE_SEL_LIMIT_LOW_MASK_FOR_ADDR_1/

or just to PCI_IDE_SEL_LIMIT_LOW_MASK

Thanks,


>>
>> I like mine better :) Shows in one place how addr_1 is made:

> 
> Thanks,

---

## [41] Alexey Kardashevskiy — 2024-12-19
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 6/12/24 09:24, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in config-space, and programming the keys into the link layer


This needs to test that (pdev->nr_ide_mem >= ide->nr_mem), easy to miss 
especially when PCI_IDE_SETUP_ROOT_PORT. Thanks,



> +		val = FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |
> +		      FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK,

---

## [42] Alexey Kardashevskiy — 2024-12-19
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 19/12/24 18:25, Alexey Kardashevskiy wrote:
> 
> 

Oh, when we do this, the root port gets the same devid_start/end as the 
device which is not correct, what should be there, the rootport bdfn? 
Need to dig that but PCI_IDE_SETUP_ROOT_PORT should detect that it is a 
root port. Thanks,


>> +
>> +    return 0;

---

## [43] Xu Yilun — 2025-01-08
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

> > > +static void __pci_ide_stream_setup(struct pci_dev *pdev, struct
> > > pci_ide *ide)

Yes, but nr_ide_mem is limited HW resource and may easily smaller than
device memory region number. In this case, maybe we have to merge the
memory regions into one big range.

> > 
> > 

"Indicates the lowest/highest value RID in the range
associated with this Stream ID at the IDE *Partner* Port"

My understanding is that device should fill the RP bdfn, and the RP
should fill the device bdfn for RID association registers. Same for Addr
association registers.

Thanks,
Yilun

> to dig that but PCI_IDE_SETUP_ROOT_PORT should detect that it is a root
> port. Thanks,

---

## [44] Xu Yilun — 2025-01-08
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On Tue, Dec 10, 2024 at 08:49:40AM +0530, Aneesh Kumar K.V wrote:
> 
> Hi Dan,

Should be illustrating in commit log.

"The other design detail for TSM-coordinated IDE establishment is that
the TSM manages allocation of stream-ids, this is why the stream_id is
passed in to pci_ide_stream_setup()."

This is true for Intel TDX.

Thanks,
Yilun

> 
> static int pcie_ide_sel_streamid_alloc(struct pci_dev *pdev)



> 
> -aneesh

---

## [45] Alexey Kardashevskiy — 2025-01-09
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 8/1/25 07:00, Xu Yilun wrote:
>>>> +static void __pci_ide_stream_setup(struct pci_dev *pdev, struct
>>>> pci_ide *ide)

My rootport does not have any range (instead, it relies on C-bit in MMIO 
access to set T-bit). The device got just one (which is no use here as I 
understand).


> In this case, maybe we have to merge the
> memory regions into one big range.

>>>
>>>

Oh. Yeah, this sounds right. So most of the setup needs to be done on 
the root port and not on the device (which only needs to enable the 
stream), which is not what the patch does. Or I got it wrong? Thanks,

> 
> Thanks,

---

## [46] Xu Yilun — 2025-01-10
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On Thu, Jan 09, 2025 at 01:35:58PM +1100, Alexey Kardashevskiy wrote:
> 
> 

It seems strange, then how the RP decide which stream id to use.

> access to set T-bit). The device got just one (which is no use here as I
> understand).

I also have no idea from SPEC how to use the IDE register blocks on EP,
except stream ENABLE bit.

And no matter how I program the RID/ADDR association registers, it
always work...

Call for help.

> 
> 

I don't get you. This patch does IDE setup for 2 partners:

__pci_ide_stream_setup(pdev, ide);  This is the setup on RP
__pci_ide_stream_setup(rp, ide);    This is the setup on device

unless AMD setup IDE by firmware, and didn't set the PCI_IDE_SETUP_ROOT_PORT flag.

Thanks,
Yilun

> 
> >

---

## [47] Aneesh Kumar K.V — 2025-01-10
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Tue, Dec 10, 2024 at 08:49:40AM +0530, Aneesh Kumar K.V wrote:
>> 

IIUC ide->stream_id is going to be set by SVE or TDX backend. But then
we also expect the below.

	if (test_and_set_bit_lock(ide->stream_id, hb->ide_stream_ids)) {
		pci_err(pdev, "Setup fail: Busy stream id: %d\n",


Hence the confusion why the stream-id cannot be allocated by the generic
TSM module as below

>> 
>> static int pcie_ide_sel_streamid_alloc(struct pci_dev *pdev)

-aneesh

---

## [48] Alexey Kardashevskiy — 2025-01-15
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 10/1/25 08:28, Xu Yilun wrote:
> On Thu, Jan 09, 2025 at 01:35:58PM +1100, Alexey Kardashevskiy wrote:
>>

The RMP table (an AMD thing for secure memory) has streamid.


>> access to set T-bit). The device got just one (which is no use here as I
>> understand).

Well, there is another problem.

My other test device has 1 link stream and 1 selective stream, both have 
streamid=0 and enable=0 after reset. I only configure 1 selective stream 
(write streamid + enable) and do not touch the link stream.

But the device assumes 2 streams have the same streamid=0 and when it 
receives KEY_PROG, it semi-randomly assigns the key to the link stream 
in my case so things do not work. The argument for it is: every stream 
needs to have an unique id, regardless its enabled state as "enable" can 
come before or after key programming (and I wonder if somebody else 
interprets it the same way).

This patch assumes that the selective streamid is the same as its index 
in the IDE cap's list of selective streams. And it just leaves link 
streams unconfigured. So I have to work around my device by writing 
unique numbers to all streams (link + selective) I am not using. Meh.

And then what are we doing to do when we start adding link streams? I 
suggest decoupling pci_ide::stream_id from stream_id in sel_ide_offset() 
(which is more like selective_stream_index) from the start.


> And no matter how I program the RID/ADDR association registers, it
> always work...

Nope, the opposite, rp=pcie_find_root_port(pdev) so the first one writes 
to the @pdev's IDE cap and the second one (optionally) writes to the 
@rp's IDE cap.


> unless AMD setup IDE by firmware, and didn't set the PCI_IDE_SETUP_ROOT_PORT flag.

The AMD firmware only programs keys to the rootport and uses the host OS 
for everything else - IDE_KM over DOE to program keys into the device 
and the IDE capability programming on both ends. Thanks,


> 
> Thanks,

---

## [49] Jonathan Cameron — 2025-01-28
*Subject: Re: [PATCH 03/11] coco/tsm: Introduce a class device for TEE
 Security Managers*

On Thu, 05 Dec 2024 14:23:33 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> A "TSM" is a platform component that provides an API for securely
> provisioning resources for a confidential guest (TVM) to consume. The

A couple of generic comments inline.

> diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
> index 819a97e8ba99..14e7cf145d85 100644

This naming seems a bit confusing. To me tsm_sybsys could be:
a) The subsystem itself.  So something we'd expect to remove only alongside
class destroy.
b) A subsystem of a tsm (confusing here in a subsystem for tsms). Expectation
   being that a given tsm would register more than one of these.
c) What I think it is which is, which is the device added to register with
   the tsm subsystem.  

Mind you I'm not immediately sure what a better naming is.
tsm_class_dev maybe?  Though that sounds like it should be a struct device.


> +
> +static struct tsm_subsys *

If you are calling this with it as an error or null then
that smells like a bad bug we shouldn't paper over.
The only case I can think of is the define free you have
below which correctly has the same check.

> +		put_device(&subsys->dev);
> +}

---

## [50] Jonathan Cameron — 2025-01-30
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

On Thu, 05 Dec 2024 14:23:39 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> Link encryption is a new PCIe capability defined by "PCIe 6.2 section
> 6.33 Integrity & Data Encryption (IDE)". While it is a standalone port
Some overlap in here with other reviews probably...

Jonathan

> ---
>  drivers/pci/Kconfig           |    3 +

I'd be tempted to have a define to go from base of the IDE extended cap
directly to the sel_ide_offset rather than this use of a block based
offset.  Maybe it ends up too complex though.

> +}
> +

on the EP.
(for avoidance of confusion).

Also, from here just seems to mean at the RP and the EP.  Not seting a bus
walk here to check anything else.  Note I'm not sure we need to but this
comment is implying a 'from/to' aspect that this code doesn't seem to check.

> +	 */
> +	pci_read_config_dword(pdev, ide_cap + PCI_IDE_CAP, &val);
Maybe cleaner as
	int link_tc_count = 0;
	if (val & PCI_IDE_CAP_LINK)
		//see suggestion in header to make macro include +1.
		link_tc_count = PCI_IDE_CAP_LINK_TC_NUM(val) + 1;

	sel_ide_cap = ide_cap + PCI_IDE_LINK_STREAM +
		      link_tc_count * PCI_IDE_LINK_BLOCK_SIZE;
I'm not that bothered either way. Just didn't like that
ide_cap + PIC_IDE_LINK_STREAM is in both legs.

Or have a macro that always gets you to the selective part without
using a zero length PCI_IDE_LINK_STREAM block.


> +
> +	for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val); i++) {

Yank out and index from 1 for the loop?
Note though that PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val) of 1
means 2 streams so you want <= or just +1 in the macro so the PCI
header gets to deal with that!


> +		} else {
> +			int offset = sel_ide_offset(sel_ide_cap, i, nr_ide_mem);



> diff --git a/include/linux/pci.h b/include/linux/pci.h
> index db9b47ce3eef..50811b7655dd 100644

I'd not call it cap as people will go looking for a selective IDE extended capability.
I'm a little dubious about it being necessary vs a helper function that grabs
the necessary count info directly from the device.

> +	int		nr_ide_mem;	/* - Address range limits for streams */
>  #endif

Looks like 3.2 has a bit 7 defined as well.  Selective IDE for configuration requests supported.
Probably worth adding that.

> +#define  PCI_IDE_CAP_ALG(x)		(((x) >> 8) & 0x1f) /* Supported Algorithms */
> +#define  PCI_IDE_CAP_ALG_AES_GCM_256	0    /* AES-GCM 256 key size, 96b MAC */
Maybe add 1 here as the macro name kind of implies it is returning the number of link IDE TCs
rather than 1 less that that. It is a little tricky given the spec calls this field "Number of"

> +#define  PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(x)	(((x) >> 16) & 0xff) /* Selective IDE Streams */

Similar here. I'm not sure what precedence we have int his file. I can't immediately see any
either way. 

> +#define  PCI_IDE_CAP_SELECTIVE_STREAMS_MASK	0xff0000
Why have the mask if you are providing the macro above to get the value?

> +#define  PCI_IDE_CAP_TEE_LIMITED	0x1000000 /* TEE-Limited Stream Supported */
> +#define PCI_IDE_CTL			0x8
I couldn't find specific precedence for this but my gut would say add a _0 postfix
to indicate it's the first of a number of these.
All the similar cases seem to explicitly enumerate _0, _1 etc which makes little
sense here.

> +#define PCI_IDE_LINK_BLOCK_SIZE		8
> +/* Link IDE Stream block, up to PCI_IDE_CAP_LINK_TC_NUM */
I'd expect a _0 define for the first ctrl and one for the first status.

Then index each register via
PCI_IDE_LINK_CTL_0 + i * PCIE_IDE_LINK_BLOCK_SIZE
PCI_IDE_LINK_STS_0 + i * PCIE_IDE_LINK_BLOCK_SIZE

Again, not immediately seeing precedence, but having register field defines without
a register address define (even a constructed one as will be relevant
for the selective IDE stream blocks) seems odd to me.

> +#define  PCI_IDE_LINK_CTL_EN		 0x1	/* Link IDE Stream Enable */
> +#define  PCI_IDE_LINK_CTL_TX_AGGR_NPR(x) (((x) >> 2) & 0x3) /* Tx Aggregation Mode NPR */
Perhaps nice to throw in a reference to the supported algs list above.

> +#define  PCI_IDE_LINK_CTL_TC(x)		 (((x) >> 19) & 0x7)  /* Traffic Class */
> +#define  PCI_IDE_LINK_CTL_ID(x)		 (((x) >> 24) & 0xff) /* Stream ID */


I'd put some white space here.

> +/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */
> +#define PCI_IDE_SELECTIVE_BLOCK_SIZE(x)  (20 + 12 * (x))

Probably want a better name than 'x' for that parameter as it's not
immediately obvious what it is. (number of IDE address association
register blocks).
Also that 12 probably wants a define. It's used a few times.

> +/* Selective IDE Stream Capability Register */
> +#define  PCI_IDE_SEL_CAP		 0

If the mask make sense to keep at all would be good to build
the macro above using it.

> +/* Selective IDE Stream Control Register */
> +#define  PCI_IDE_SEL_CTL		 4
This is a control register. Seems likely we'll mostly be writing these.
So how useful is it to provide just a read macro?
Maybe I'm missing something!
> +#define   PCI_IDE_SEL_CTL_ALG(x)	 (((x) >> 14) & 0x1f) /* Selected Algorithm */
> +#define   PCI_IDE_SEL_CTL_TC(x)		 (((x) >> 19) & 0x7)  /* Traffic Class */

Why this one as a shift and all the rest as explicit hex values?

> +#define   PCI_IDE_SEL_CTL_ID_MASK	 0xff000000
> +#define   PCI_IDE_SEL_CTL_ID_MAX	 255

Why leading zeros on this one?

> +#define   PCI_IDE_SEL_RID_2_SEG_MASK	 0xff000000
> +/* Selective IDE Address Association Register Block, up to PCI_IDE_SEL_CAP_ASSOC_NUM */

more leading zeros which doesn't seem consistent. Also, as Alexey
pointed out value is wrong as that's 4 bits in not 8.


> +#define   PCI_IDE_SEL_ADDR_1_BASE_LOW_SHIFT  20
8?

> +#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK  0xfff0000
> +#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_SHIFT 20
Also missing a zero (Alexey got this one as well I see)

> +/* IDE Address Association Register 2 is "Memory Limit Upper" */
> +/* IDE Address Association Register 3 is "Memory Base Upper" */

---

## [51] Jonathan Cameron — 2025-01-30
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On Thu, 05 Dec 2024 14:23:45 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> The PCIe 6.1 specification, section 11, introduces the Trusted Execution
> Environment (TEE) Device Interface Security Protocol (TDISP).  This

I don't follow the previous sentence. Perhaps consider a rewrite?

> Consider that the TSM driver may
> itself be a PCI driver. Userspace can watch /sys/class/tsm/tsm0/uevent
A few minor things inline.

Jonathan

> ---
>  Documentation/ABI/testing/sysfs-bus-pci |   42 ++++



> diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> new file mode 100644

Odd header ordering.  Anything consistent is fine by me but
this just feels random.


> +#include "pci.h"
> +

Sadly that got dropped.

> +		return -EINTR;
> +

> +static struct attribute *pci_tsm_attrs[] = {
> +	&dev_attr_connect.attr,

Trivia but no comma given it's a terminator and nothing will
ever come after it.


> +};
> +
no comma

> +};


> +void pci_tsm_destroy(struct pci_dev *pdev)
> +{

I'd try to name things so it is clearer when a function
is about the TSM coming and going vs a particular PCI
device coming and going after the TSM is loaded.

At least that's what I'm assuming is the difference between
pci_tsm_unregister() tsm going vs
pci_tsm_destroy() particular PCI device driver being unbound
(which I don't think gets called, so maybe drop for now?)

> +{
> +	struct pci_dev *pdev = NULL;

>

---

## [52] Jonathan Cameron — 2025-01-30
*Subject: Re: [PATCH 06/11] samples/devsec: PCI device-security bus /
 endpoint sample*

On Thu, 05 Dec 2024 14:23:51 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> Establish just enough emulated PCI infrastructure to register a sample
> TSM (platform security manager) driver and have it discover an IDE + TEE
Hi Dan,

A few minor comments as I was reading this. Mostly just trying
to get my head around it hence they are all fairly superficial things.

Jonathan

> diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
> new file mode 100644


> +static void destroy_iomem_pool(void *data)

There is a devm_gen_pool_create you can probably use.

> +{
> +	struct devsec *devsec = data;

> +#define MMIO_SIZE SZ_2M
> +

Similar to the case below. I'd rather see a per dev devm_ cleanup
than relying on unified cleanup and that array having null entrees.
Should end up easier to follow.  Might require devsec dev to have
a reference back to the pool though.


> +	}
> +

Is this necessary? If so it wrecks suggestion to do per port devres cleanup.
I don't think it is necessary though as we really should be touching that
array after this function is done.


> +	}
> +}


> +static int init_port(struct devsec_port *devsec_port)
> +{
Maybe 
	*bridge = (struct pci_bridge_emul) {
	};
appropriate here. 	
> +
> +	init_ide(&devsec_port->ide);

return pci_bridge_emul_init() unless a later patch is going to add more here.

> +	if (rc)
> +		return rc;

I'd prefer to see a per port devm cleanup registered so that you don't
have to register that before anything has happened leaving it only
loosely associated with what it is doing.


> +		devsec->devsec_ports[i] = no_free_ptr(devsec_port);
> +	}

---

## [53] Jonathan Cameron — 2025-01-30
*Subject: Re: [PATCH 11/11] samples/devsec: Add sample IDE establishment*

On Thu, 05 Dec 2024 14:24:19 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> Exercise common setup and teardown flows for a sample platform TSM
> driver that implements the TSM 'connect' and 'disconnect' flows.
Trivial comments inline.

>  static int devsec_tsm_connect(struct pci_dev *pdev)
>  {

I'd kind of expect to see more of what we have in disconnect here.
Like clearing the bit.

> +	return rc;
>  }
If this setting to NULL needs to be out of order wrt to what happens
in probe, add a comment.  If not move it to after pci_ide_disable_steram()

> +	clear_bit(i, devsec_stream_ids);
>  }

---

## [54] Alexey Kardashevskiy — 2025-02-11
*Subject: Re: [PATCH 09/11] PCI/IDE: Report available IDE streams*

On 6/12/24 09:24, Dan Williams wrote:
> The limited number of link-encryption (IDE) streams that a given set of
> host-bridges supports is a platform specific detail. Provide


PCI_IDE needs quotes but somehow it was compiling for months until I 
rebased onto v6.14. Hm. Also probably all exports should be PCI_IDE NS, 
or none. Thanks,


> +
>   void pci_init_host_bridge_ide(struct pci_host_bridge *hb)

---

## [55] Dan Williams — 2025-02-19
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Ilpo J�rvinen wrote:
> On Thu, 5 Dec 2024, Dan Williams wrote:
> 
[..]
> > @@ -1210,6 +1211,12 @@
> >  #define PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL		0x00ff0000

Good point, yes it should.

---

## [56] Dan Williams — 2025-02-19
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Dan Williams wrote:
> Ilpo J�rvinen wrote:
> > On Thu, 5 Dec 2024, Dan Williams wrote:

...although only when the kernel adds a use case to write to DEV3_CTL,
for now the use case is read-only for DEV3_CAP.

---

## [57] Dan Williams — 2025-02-19
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Aneesh Kumar K.V wrote:
> 
> Hi Dan,

Yes, good eye, and excuse the delay while I worked my way back to this
patch set.

---

## [58] Dan Williams — 2025-02-19
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V wrote:
> 
> Hi Dan,

So recall that this design is meant to support both native and TSM
initiated IDE establishment. While in the native IDE case the kernel
could just pick a free id, in the TSM case the kernel is told the id
that the TSM picked during its IDE establishment flow.

My expectation is that if Linux ever supports native IDE then
establishment that would be modeled as just another TSM that just
happens to be a kernel software backend rather than a TSM provided by
the platform.

For now this function just sanity checks that the TSM is not handing out
duplicate ids, and to record which of a limited pool of ids is in use.

---

## [59] Dan Williams — 2025-02-19
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V wrote:
[..]
> 
> Also wondering should the stream id be unique at the rootport level? ie

For all the IDE capable platforms I know of the stream id allocation
pool is segmented per host-bridge. Do you have a use case where root
ports that share a host-bridge each have access to a distinct pool of
IDE stream ids?

---

## [60] Dan Williams — 2025-02-19
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Alexey Kardashevskiy wrote:
> On 6/12/24 09:23, Dan Williams wrote:
> > Link encryption is a new PCIe capability defined by "PCIe 6.2 section
[..]
> > +void pci_ide_init(struct pci_dev *pdev)
> > +{

Specifications often add flexibility without concern for the system
software complexity it implies. I am happy to change it as soon as there
is the first sign of evidence someone might build such a thing, but
otherwise it makes walking this register space simpler. It is not clear
to me that there is an economic reason to build a device with variable
amount of address association per stream block.

Also, apologies for letting this patch set so long, I have finally
cleared some other backlog.

---

## [61] Alexey Kardashevskiy — 2025-02-20
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 10/1/25 08:28, Xu Yilun wrote:
> On Thu, Jan 09, 2025 at 01:35:58PM +1100, Alexey Kardashevskiy wrote:
>>

Oh I thought I replied :-/ The RP gets the stream id from an RMP entry 
corresponding to the MMIO page.


> 
>> access to set T-bit). The device got just one (which is no use here as I

+1.


>>
>>

Nah, it is the oppositve.

> 
> unless AMD setup IDE by firmware, and didn't set the PCI_IDE_SETUP_ROOT_PORT flag.

The AMD firmware does not access the config space at all, relies on the 
host os instead. Thanks,


> 
> Thanks,

---

## [62] Dan Williams — 2025-02-20
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Alexey Kardashevskiy wrote:
> On 6/12/24 09:23, Dan Williams wrote:
> > Link encryption is a new PCIe capability defined by "PCIe 6.2 section

Whoops, was moving too fast, fixed.

> 
> 31:20 Memory Limit Lower – Corresponds to Address bits [31:20]. Address 

I too would have liked to use the bitfield macros, but I notice that
this would be the first bitfield macro usage in pci_regs.h and that
bitfield.h is not a uapi header. In fact, there is no bitfield.h usage
in all of include/uapi/.

How about a compromise, I will add your macro to include/linux/pci-ide.h
based on offset and mask defines from include/uapi/pci_regs.h.

---

## [63] Dan Williams — 2025-02-20
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
> On 6/12/24 09:24, Dan Williams wrote:
> > There are two components to establishing an encrypted link, provisioning
[..]
> > @@ -71,3 +74,192 @@ void pci_ide_init(struct pci_dev *pdev)
> >   	pdev->sel_ide_cap = sel_ide_cap;

Hmm, yes, an empty resource only makes sense if there is going to be a
later point in the init flow where it is adjusted to map the real
platform probed boundaries, and I do not have that in this code.

The platform iomem_resource boundaries should be settled before the
host-bridge is initialized, so no need to find a later point than this
to set the bounds. Will fold in this incremental change:

@@ -77,8 +77,13 @@ void pci_ide_init(struct pci_dev *pdev)
 
 void pci_init_host_bridge_ide(struct pci_host_bridge *hb)
 {
-       hb->ide_stream_res =
-               DEFINE_RES_MEM_NAMED(0, 0, "IDE Address Association");
+       /*
+        * Match platform iomem resource boundaries for IDE address
+        * association.
+        */
+       hb->ide_stream_res = DEFINE_RES_MEM_NAMED(
+               iomem_resource.start, resource_size(&iomem_resource),
+               "IDE Address Association");
 }
 
 /*


[..]
> > +void pci_ide_enable_stream(struct pci_dev *pdev, struct pci_ide *ide)
> > +{

Added.

> And no PCI_IDE_SETUP_ROOT_PORT here, is the platform expected to enable 
> it explicitely? If yes, then we do not need PCI_IDE_SETUP_ROOT_PORT 

Hmm, yes, looking at this now, PCI_IDE_SETUP_ROOT_PORT is giving off
"mid-layer" smells and this responsibility should be pushed to the low
level driver.

It is still the case that there is a part of the stream setup that can
fail, like registering the presence of the stream in sysfs, but the
piece that can not fail, __pci_ide_stream_setup(), should be left to the
platform TSM driver to optionally be called for the root-port.

I will rename the parts of the stream setup that needs alloc / free as
"pci_ide_stream_{register,unregister}()", export
__pci_ide_stream_setup() as a standalone helper renamed to just
pci_ide_stream_setup(), and drop the PCI_IDE_SETUP_ROOT_PORT flag
concept.

> Also, my test device wants PCI_IDE_SEL_CTL_TEE_LIMITED to work, I wonder 
> how to showel it in here, add a "unsigned dev_sel_ctl" to pci_ide?

I will add that. If the device supports limited stream I see no reason
that Linux would want to not require it (outside of device quirks). So,
the default will be to enable it if supported, but the low-level TSM
driver can always clear that support flag in the pdev (endpoint or root)
if the need arises.

[..]
> > diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
> > new file mode 100644

Agree, added an ide_domain_nr() helper to meet the requirement that
software must write 0 if the device has not captured its segment base.

> Thanks,
> 

Hey, yes please! The whole point of this effort is to find a path to
mutual acceptance on all these concerns.

---

## [64] Alexey Kardashevskiy — 2025-02-21
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

On 21/2/25 05:07, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> On 6/12/24 09:23, Dan Williams wrote:

just double checking - fixed 0x000fff00 too, right?


> 
>>

oh I did not notice that. Makes sense now.


> How about a compromise, I will add your macro to include/linux/pci-ide.h
> based on offset and mask defines from include/uapi/pci_regs.h.

That works. tbh I would not even comment on these if I did not have to 
check these after finding 0x000fff0 and 0xfff0000 :) Thanks,

---

## [65] Aneesh Kumar K.V — 2025-02-21
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy <aik@amd.com> writes:

....

>
> I am trying to wrap my head around your tsm. here is what I got in my tree:

For the Arm CCA DA, I have structured the flow as follows. I am
currently refining my changes to prepare them for posting. I am using
tsm-core in both the host and guest. There is no bind interface at the
sysfs level; instead, it is managed via the KVM ioctl

Host:
step 1.
echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind
echo vfio-pci > /sys/bus/pci/devices/${DEVICE}/driver_override
echo ${DEVICE} > /sys/bus/pci/drivers_probe

step 2.
echo 1 > /sys/bus/pci/devices/$DEVICE/tsm/connect

step 3.
using VMM to make the new KVM_SET_DEVICE_ATTR ioctl

+		dev_num = vfio_devices[i].dev_hdr.dev_num;
+		/* kvmtool only do 0 domain, 0 bus and 0 function devices. */
+		guest_bdf = (0ULL << 32) | (0 << 16) | dev_num << 11 | (0 << 8);
+
+		struct kvm_vfio_tsm_bind param = {
+			.guest_rid = guest_bdf,
+			.devfd = vfio_devices[i].fd,
+		};
+		struct kvm_device_attr attr = {
+			.group = KVM_DEV_VFIO_DEVICE,
+			.attr = KVM_DEV_VFIO_DEVICE_TDI_BIND,
+			.addr = (__u64)&param,
+		};
+
+		if (ioctl(kvm_vfio_device, KVM_SET_DEVICE_ATTR, &attr)) {
+			pr_err("Failed KVM_SET_DEVICE_ATTR for KVM_DEV_VFIO_DEVICE");
+			return -ENODEV;
+		}
+

Now in the guest we follow the below steps

step 1:
echo ${DEVICE} > /sys/bus/pci/devices/${DEVICE}/driver/unbind

step 2: Move the device to TDISP LOCK state
echo 1 > /sys/bus/pci/devices/0000:00:00.0/tsm/connect
echo 3 > /sys/bus/pci/devices/0000:00:00.0/tsm/connect

step 3: Moves the device to TDISP RUN state
echo 4 > /sys/bus/pci/devices/0000:00:00.0/tsm/connect

step 4: Load the driver again.
echo ${DEVICE} > /sys/bus/pci/drivers_probe

---

## [66] Aneesh Kumar K.V — 2025-02-21
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Dan Williams <dan.j.williams@intel.com> writes:

> Aneesh Kumar K.V wrote:
> [..]

I am using FVP simulator for my development. Hence no real device. The spec states:
"
All IDE TLPs must be associated with an IDE Stream, identified via an IDE Stream ID.
◦ Software must assign IDE Stream IDs such that two Partner Ports use the same value for a given IDE
Stream.
◦ Software must assign IDE Stream IDs such that every enabled IDE Stream associated with a given
terminal Port is assigned a unique Stream ID value at that Port
◦ It is permitted for a platform to further restrict the assignment of Stream IDs.
"

If I understand correctly, the stream ID allocation pool per host bridge
qualifies as an additional platform restriction? If so, why is Linux
enforcing it? Wouldn’t it be more appropriate for the platform code to
handle this instead?

-aneesh

---

## [67] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
> On 6/12/24 09:23, Dan Williams wrote:
> > The PCIe 6.1 specification, section 11, introduces the Trusted Execution

I expect it to grow as more common cross-vendor host TSM functionality
is added.

> > +static int pci_tsm_connect(struct pci_dev *pdev)
> > +{

That's still the plan, but I would expect that to be a common helper
that TSM drivers can use and does not need to be enforced as a midlayer
detail in pci/tsm.c. We can add that to pci/doe.c or somewhere more
appropriate for SPDM transport helpers.

[..]
> > diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
> > new file mode 100644

I typed up a long reply only to realize I think this can be made simpler
by only having one common context and drop this subtle 'struct pci_dsm'
distinction.

So, 'struct pci_tsm' is just the common core context / handle for
drivers/pci/tsm.c to communicate with low level TSM driver
implementation. It is allocated by pci_tsm_ops->probe() and freed by
pci_tsm_ops->remove().

A low-level TSM driver can optionally wrap that core context with its
own data, i.e. enforce a container_of() relationship between the core
context and the low level context.

[..]
> > diff --git a/include/linux/pci.h b/include/linux/pci.h
> > index 50811b7655dd..a0900e7d2012 100644

The motivation for building awareness of device-security properties
natively into 'struct pci_dev' is the recognition that TSM-based
security is not the only model that Linux needs to contend. The TSM
flow is a superset of PCI-CMA and maybe PCI-IDE in the future (although
Intel seems to be the only architecture that has a concept of allowing
IDE establishment without a TSM).

I understand your motivations to make all of TSM functionality bolted
onto the side of the PCI core. It has some nice properties. However, I
think that is a SEV-TIO centric view of the world. PCI device security
attributes are PCI device attributes and have reason to exist with and
without a TSM. In other words, certificates and measurements should not
be placed behind a TSM ABI because certificates and measurements are
expected to have a native PCI-CMA ABI.

It would be a useful property if software written to retrieve
measurement and certificate chains did that relative to the PCI dev
independent of TSM presence.

> aik@sc ~> ls  /sys/bus/pci/devices/0000:e1:04.0/tsm-tdi/tdi:0000:e1:04.0/
> device  power  subsystem  tsm_report  tsm_report_user  tsm_tdi_bind 

Right, so I remain unconvinced that Linux needs to contend with new "tsm"
class devs vs PCI device objects with security properties especially
when those security properties have a "TSM" and non-"TSM" flavor.

---

## [68] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Bjorn Helgaas wrote:
> On Thu, Dec 05, 2024 at 02:24:02PM -0800, Dan Williams wrote:
> > There are two components to establishing an encrypted link, provisioning

Sure. Fixed up this one, the print statements that were using "stream
id", the code comments, and all the other patches in this set using
lowercase "stream id".

> > The flow is:
> > 

Indeed my thought process, was "well, Linux has long called Requester ID
'DEVID' so just pick 'DEVID' to keep with that momentum". I am fine to
use "Requester ID" in all comments etc.

I'll also switch any usage of "devid" to "rid" for variable names and
just note somewhere that PCI_DEVID() is the "rid" as far as IDE and TSM
code paths are concerned.

> > In support of system administrators auditing where platform IDE stream
> > resources are being spent, the allocated stream is reflected as a

Fixed here, found an additional one code comments, and the documentation
file

> 
> > +++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge

Makes sense, adopted your wording.

> 
> Typical formatting of domain is %04x.

Oh, whoops, fixed that by doing:

    s/DDDDD/DDDD/

...throughout the set.

> 
> > +What:		pciDDDDD:BB/streamN:DDDDD:BB:DD:F

Fixed.

> > + * Retrieve stream association parameters for devid (RID) and resources
> > + * (device address ranges)

I addressed this by decomposing this function into a "register" step and
a "setup" step according to Alexey's feedback. That removes the
responsibility of the core to remember the flags and puts the onus on
the leaf driver to remember to program the RP if its TSM implementation
requires that (some do not).

In other words the leak risk is contained to pairing "stream register"
with "stream unregister" calls, and that is independent of this now
deleted PCI_IDE_SETUP_ROOT_PORT detail.

> > +++ b/include/linux/pci.h
> > @@ -601,6 +601,10 @@ struct pci_host_bridge {

Done.

---

## [69] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 10/11] PCI/TSM: Report active IDE streams*

Bjorn Helgaas wrote:
> On Thu, Dec 05, 2024 at 02:24:14PM -0800, Dan Williams wrote:
> > Given that the platform TSM owns IDE stream id allocation, report the

Yup, got both of these fixed per comments on the last patch.

---

## [70] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Bjorn Helgaas wrote:
> On Thu, Dec 05, 2024 at 02:23:45PM -0800, Dan Williams wrote:
> > The PCIe 6.1 specification, section 11, introduces the Trusted Execution

Good catch, done.

---

## [71] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Bjorn Helgaas wrote:
> On Thu, Dec 05, 2024 at 02:23:56PM -0800, Dan Williams wrote:
> > PCIe 6.2 Section 7.7.9 Device 3 Extended Capability Structure,

Fixed.

> > +++ b/include/uapi/linux/pci_regs.h
> > @@ -749,6 +749,7 @@

Alexey, do you have plans to follow up your IDE addition to pcituils
with this DEV3 support given the "Flit Mode" detection requirements of
"IDE RID Association Register 2"?

---

## [72] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Bjorn Helgaas wrote:
> I try to make the first word of the subject a verb that says something
> about what the patch does, maybe "Enumerate" in this case?

I usually do that as well, "Enumerate" works for me.

> On Thu, Dec 05, 2024 at 02:23:39PM -0800, Dan Williams wrote:
> > Link encryption is a new PCIe capability defined by "PCIe 6.2 section

Updated to:

"Link encryption is a new PCIe feature enumerated by PCIe 6.2 section
 7.9.26 IDE Extended Capability."

> > and endpoint capability, it is also a building block for device security
> > defined by "PCIe 6.2 section 11 TEE Device Interface Security Protocol

Got it.

> 
> > Add register definitions and basic enumeration for a "selective-stream"

I also went ahead and updated occurrences of "selective stream" to
"Selective IDE Stream" given that is also how it appears in the spec.

> 
> > +void pci_ide_init(struct pci_dev *pdev)

Got it.

---

## [73] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Ilpo J�rvinen wrote:
> On Tue, 10 Dec 2024, Bjorn Helgaas wrote:
> 

Oh, good to hear (the dangers of replying to patch feedback in response
order unfortunately means I missed this in my earlier reply). Please
copy me on those patches so I can keep track of that discussion.

---

## [74] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Xu Yilun wrote:
> > > +/* Selective IDE Stream Capability Register */
> > > +#define  PCI_IDE_SEL_CAP		 0

Agree, updated.

> 
> > > +/* Selective IDE Stream Control Register */

I also agree with this. I had copied these from Alexey, but for the ones
that actually got used in the code I ended up using mask defines with
FIELD_PREP/GET(). I think I will just delete them for now, and we can
add them back as masks later.

[..]
> > > +#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_SHIFT 20
> 

Agree, I ended up with this definition inline in ide.c:

#define SEL_ADDR1_LOWER_MASK GENMASK(31, 20)
#define PREP_PCI_IDE_SEL_ADDR1(base, limit)                   \
        FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |             \
        FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK,          \
                   FIELD_GET(SEL_ADDR1_LOWER_MASK, (base))) | \
        FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK,         \
                   FIELD_GET(SEL_ADDR1_LOWER_MASK, (limit)))

---

## [75] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Xu Yilun wrote:
> On Tue, Dec 10, 2024 at 08:38:57AM +0530, Aneesh Kumar K.V wrote:
> > 

I think we should follow what you said in the last patch and just define
the mask that gets to the raw field and then put the fixup code in ide.c

Folded in this:

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 6667a61ba01a..eea126ce7ae0 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -14,8 +14,8 @@ static int sel_ide_offset(u16 cap, int stream_id, int nr_ide_mem)
 
 void pci_ide_init(struct pci_dev *pdev)
 {
+       int nr_ide_mem = 0, nr_streams;
        u16 ide_cap, sel_ide_cap;
-       int nr_ide_mem = 0;
        u32 val = 0;
 
        if (!pci_is_pcie(pdev))
@@ -47,7 +47,8 @@ void pci_ide_init(struct pci_dev *pdev)
        else
                sel_ide_cap = ide_cap + PCI_IDE_LINK_STREAM;
 
-       for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val); i++) {
+       nr_streams = FIELD_GET(PCI_IDE_CAP_SELECTIVE_STREAMS_NUM_MASK, val) + 1;
+       for (int i = 0; i < nr_streams; i++) {
                if (i == 0) {
                        pci_read_config_dword(pdev, sel_ide_cap, &val);
                        nr_ide_mem = PCI_IDE_SEL_CAP_ASSOC_NUM(val);
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 7b8ef694a9ef..17aef7646b8d 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -1226,8 +1226,7 @@
 #define  PCI_IDE_CAP_ALG(x)            (((x) >> 8) & 0x1f) /* Supported Algorithms */
 #define  PCI_IDE_CAP_ALG_AES_GCM_256   0    /* AES-GCM 256 key size, 96b MAC */
 #define  PCI_IDE_CAP_LINK_TC_NUM(x)    (((x) >> 13) & 0x7) /* Link IDE TCs */
-#define  PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(x) ((((x) >> 16) & 0xff) + 1) /* Selective IDE Streams */
-#define  PCI_IDE_CAP_SELECTIVE_STREAMS_MASK    0xff0000
+#define  PCI_IDE_CAP_SELECTIVE_STREAMS_NUM_MASK        0xff0000 /* Supported Selective IDE Streams */
 #define  PCI_IDE_CAP_TEE_LIMITED       0x1000000 /* TEE-Limited Stream Supported */
 #define PCI_IDE_CTL                    0x8
 #define  PCI_IDE_CTL_FLOWTHROUGH_IDE   0x4     /* Flow-Through IDE Stream Enabled */

---

## [76] Dan Williams — 2025-02-21
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Xu Yilun wrote:
> > +static int pci_tsm_disconnect(struct pci_dev *pdev)
> > +{

Good catch, fixed.

[..]
> > +
> > +static void __pci_tsm_init(struct pci_dev *pdev)

Do you see a need for PCI core to notify the TSM driver about the
arrival of VF devices?

My expectation is that a VF TDI communicates with the TSM driver
relative to its PF.

> > +
> > +	tee_cap = pdev->devcap & PCI_EXP_DEVCAP_TEE;

Per above I was only expecting physical function, but the bind flow
might introduce the need for per function (phyiscal or virtual) TDI
context. I expect that is separate from the PF pdev->tsm context.

---

## [77] Xu Yilun — 2025-02-24
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On Fri, Feb 21, 2025 at 05:15:24PM -0800, Dan Williams wrote:
> Xu Yilun wrote:
> > > +static int pci_tsm_disconnect(struct pci_dev *pdev)

I think yes.

> 
> My expectation is that a VF TDI communicates with the TSM driver

It is possible, but the PF TSM still need to manage the TDI context for
all it's VFs, like:

struct pci_tdi;

struct pci_tsm {
	...
	struct pci_dsm *dsm;
	struct xarray tdi_xa; // struct pci_tdi array
};


An alternative is we allow VFs has their own pci_tsm, and store their
own tdi contexts in it.

struct pci_tsm {
	...
	struct pci_dsm *dsm; // point to PF's dsm.
	struct pci_tdi *tdi;
};

I perfer the later cause we don't have to seach for TDI context
everytime we have a pdev for VF and do tsm operations on it.

> 
> > > +

Could we embed TDI context in PF's pdev->tsm AND VF's pdev->tsm? From
TDISP spec, TSM covers TDI management so I think it is proper
struct pci_tsm contains TDI context.

Thanks,
Yilun

---

## [78] Ilpo Järvinen — 2025-02-24
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On Fri, 21 Feb 2025, Dan Williams wrote:
> Ilpo J�rvinen wrote:
> > On Tue, 10 Dec 2024, Bjorn Helgaas wrote:

Hi Dan,

I've seemingly Cc'ed you back then:

https://lore.kernel.org/linux-pci/20241211134840.3375-1-ilpo.jarvinen@linux.intel.com/

(Np of not noticing, we do get way too much email to pick up everything.)

...There has been no discussion about it though.

---

## [79] Dan Williams — 2025-02-24
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
> 
> 
[..]
> > diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> > index a0c09d9e0b75..c37f35f0d2c0 100644
[..]
> > +static void __pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
> > +{

Good catch.

I think the more appropriate place to enforce this is in
pci_ide_stream_probe() with something like the below... unless I am
mistaken and address association settings do not need to be identical
between endpoint and Root Port?

@@ -99,9 +99,13 @@ void pci_init_host_bridge_ide(struct pci_host_bridge *hb)
  */
 void pci_ide_stream_probe(struct pci_dev *pdev, struct pci_ide *ide)
 {
+       struct pci_dev *rp = pcie_find_root_port(pdev);
        int num_vf = pci_num_vf(pdev);
 
-       *ide = (struct pci_ide) { .stream_id = -1 };
+       *ide = (struct pci_ide) {
+               .stream_id = -1,
+               .nr_mem = min(pdev->nr_ide_mem, rp->nr_ide_mem),
+       };
 
        /* PCIe Requester ID == Linux "devid" */
        ide->rid_start = pci_dev_id(pdev);

---

## [80] Dan Williams — 2025-02-24
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
> 
> 
[..]
> >> +��� __pci_ide_stream_setup(pdev, ide);
> >> +��� if (flags & PCI_IDE_SETUP_ROOT_PORT)

Why would the values be different? The Stream is associated with a set
of RIDs, I expect the PF and the Root Port to agree on that set?

Regardless, the PCI_IDE_SETUP_ROOT_PORT concept is dead so this could
support distinct settings per Root Port vs endpoint, but I am missing
where / why those would diverge.

---

## [81] Dan Williams — 2025-02-24
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Xu Yilun wrote:
[..]
> > 
> > Oh, when we do this, the root port gets the same devid_start/end as the

So you expect that the endpoint programs RPs and Peer-to-Peer RIDs in
its association register? That makes sense, although I feel like once
Peer-to-Peer operation is considered the RID association loses
effectiveness because it is difficult to capture a constrained range in
that case.

We can start with that for RID as our best current understanding and
circle back later if it causes problems. As for address association I am
not sure Linux needs to worry about it in the first implementation. The
mechanism is too coarse to keep up with IOMMU entries for the device. If
it already needs to be overspecified might as well disable it.

---

## [82] Dan Williams — 2025-02-24
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

This is an after-the-fact "trust but verify" sanity check. It is making
sure that the Linux-view and TSM-view of the Stream ID space stays in
sync. 

> Hence the confusion why the stream-id cannot be allocated by the generic
> TSM module as below

...again, because Linux has no way to convey which Stream ID to use to
the TSM.

---

## [83] Dan Williams — 2025-02-24
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
[..]
> >> access to set T-bit). The device got just one (which is no use here as I
> >> understand).

Oh, true that should be separated, and perhaps that is the concern that
Aneesh has been raising as well?
 
> And it just leaves link streams unconfigured. So I have to work around
> my device by writing unique numbers to all streams (link + selective)

This sounds like a device-quirk where it is not waiting for an enable
event to associate the key with a given stream index. One could imagine
this is either a pervasive problem and TSMs will start considering
Stream ID 0 as burned for compatibilitiy reasons. Or, this device is
just exhibiting a pre-production quirk that Linux does not need to
react, yet.

Can you say whether this problem is going to escape your test bench into
something mainline Linux needs to worry about?

> And then what are we doing to do when we start adding link streams? I 
> suggest decoupling pci_ide::stream_id from stream_id in sel_ide_offset() 

Setting aside that I agree with you that Stream index be separated from
from Stream ID, what would motivate Linux to consider setting up Link
Stream IDE?

One of the operational criticisms of Link IDE is that it requires adding
more points of failure into the TCB where a compromised switch can snoop
traffic. It also adds more Keys and their associated maintainenace
overhead. So, before we start planning ahead for Link IDE and Selective
Stream IDE to co-exist in the implementation, I think we need a clear
use case that demonstrates Link IDE is going to graduate from the
specification into practical deployments.

We can always cross that sophistication bridge later.

---

## [84] Dan Williams — 2025-02-24
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

Ah, ok, yes, the Stream ID itself only needs to be unique within a given
port pair so it is reasonable for 2 root ports to alias Stream IDs.

It turns out I was overloading "Stream ID" and in practice there are
three separate resources to consider:

- Stream ID: 256 Stream IDs within a port pair (can alias across Root
             Ports): TSM allocated

- Stream instance: Up to 16 Selective Streams Per port: Linux allocated

- Stream resource: Platform specific number of supported streams, likely
                   per-host bridge: Linux allocation constraint

That last one may be a small number like 4 given the relative expense of
link encryption hardware.

The motivation for registering streams as a sysfs object is mainly for
an administrator to manage that last number as the tightest constrained
resource. However Linux can also keep the TSM honest that it is not
violating allocation expectations within a port pair.

---

## [85] Alexey Kardashevskiy — 2025-02-25
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

On 22/2/25 10:34, Dan Williams wrote:
> Bjorn Helgaas wrote:
>> On Thu, Dec 05, 2024 at 02:23:56PM -0800, Dan Williams wrote:

No sorry I do not, I do not have any device with this capability to try 
lspci on. When/if I get one - then, sure. Do you have such device btw? 
Thanks,

---

## [86] Alexey Kardashevskiy — 2025-02-25
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 25/2/25 09:31, Dan Williams wrote:
> Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

The AMD PSP fw allows the OS to choose streamids (have not tested 
anything but "0" but all the API is there) and the OS programs these to 
both ends of PCIe link via the IDE cap. Is it different elsewhere? Thanks,

---

## [87] Xu Yilun — 2025-02-25
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On Mon, Feb 24, 2025 at 02:24:27PM -0800, Dan Williams wrote:
> Xu Yilun wrote:
> [..]

Yes.

> Peer-to-Peer operation is considered the RID association loses
> effectiveness because it is difficult to capture a constrained range in

That's OK.

> not sure Linux needs to worry about it in the first implementation. The

For Intel, yes on RP side. Intel TDX Module requires OS to input ONE
address association range on IDE stream create to setup RP.

Thanks,
Yilun

> mechanism is too coarse to keep up with IOMMU entries for the device. If
> it already needs to be overspecified might as well disable it.

---

## [88] Alexey Kardashevskiy — 2025-02-25
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 25/2/25 11:06, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]

The hw people call it "the device needs to have an errata" (for which we 
will later have a quirk?).

> Can you say whether this problem is going to escape your test bench into
> something mainline Linux needs to worry about?

Likely going to escape, unless the PCIe spec says specifically that this 
is a bug. Hence 
https://github.com/aik/linux/commit/745ee4e151bcc8e3b6db8281af445ab498e87a70


> 
>> And then what are we doing to do when we start adding link streams? I

Probably for things like CXL which connect directly to the soc? I do not 
really know, I only touch link streams because of that only device which 
is like to see the light of the day though.

> We can always cross that sophistication bridge later.

Today SEV-TIO does not do link streams at all so I am with you :) Thanks,

---

## [89] Alexey Kardashevskiy — 2025-02-25
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On 22/2/25 07:42, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> On 6/12/24 09:23, Dan Williams wrote:

My sketch evolved much since I wrote this comment :) I've put the low 
level TSM bits into CCP.


> [..]
>>> diff --git a/include/linux/pci.h b/include/linux/pci.h

Very true.

> PCI device security
> attributes are PCI device attributes and have reason to exist with and

The Lukas'es CMA ABI should just work on AMD, without any TSM. I am not 
sure if anyone wants CMA bits from the PSP when can be obtained from the 
device directly.


> It would be a useful property if software written to retrieve
> measurement and certificate chains did that relative to the PCI dev

One of the thoughts was - when we start adding this TDISP to CXL (which 
is but also is not PCI), this may be handy, may be. Or, I dunno, 
USB-TDISP. The security objects are described in the PCIe spec now but 
the concept is generic really. Thanks,

---

## [90] Xu Yilun — 2025-02-25
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On Mon, Feb 24, 2025 at 12:24:20PM -0800, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> > 

No, addr associations don't have to be identical.

Now we should fill EP's mem ranges to RP's addr association registers,
so Aik's idea is to check if RP's pdev->nr_ide_mem >= EP's nr_mem.

EP's nr_mem calculation is complicated,

	ep_nr_mem = pci_resource_number(PF_pdev, IORESOURCE_MEM) +
		    pci_resource_number(VF1_pdev, IORESOURCE_MEM) +
		    pci_resource_number(VF2_pdev, IORESOURCE_MEM) +
		    ...;

It is easily rp->nr_ide_mem < ep_mr_mem, so I don't think check and
fail is a good way, we have to merge ranges. Maybe merging to 1 range
is a simplest solution:

	if (rp->nr_ide_mem < ep_nr_mem) {
		ide->nr_mem = 1;
		/* merge ep ranges and fill ide->mem[0] */

	} else {
		ide->nr_mem = ep_nr_mem;
		/* copy ep ranges to ide->mem[] */
	}

A further requirement is, firmware may not agree to use all RP's address
asociation blocks, e.g. Intel TDX Module just use one block. So maybe
add an input parameter:

void pci_ide_stream_probe(struct pci_dev *pdev, int max_ide_nr_mem, struct pci_ide *ide)
{
	int nr_ide_mem = min(rp->nr_ide_mem, max_ide_nr_mem);

	int ep_nr_mem = calc_ep_nr_mem(pdev);

	if (nr_ide_mem < ep_nr_mem) {
		ide->nr_mem = 1;
		/* merge ep ranges and fill ide->mem[0] */
        } else {
		ide->nr_mem = ep_nr_mem;
		/* copy ep ranges to ide->mem[] */
        }
}


BTW: I'm not sure how to fill EP's addr association register, for now I
just skip it and works. Maybe my device doesn't care about them at all.

Thanks,
Yilun

> +       };
>

---

## [91] Xu Yilun — 2025-02-25
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On Fri, Feb 21, 2025 at 01:43:28PM +0530, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

I think bind (which brings device to a LOCKED state, no MMIO, no DMA)
cannot be a driver agnostic behavior. So I think it should be a VFIO
ioctl.

> 
> Now in the guest we follow the below steps

Reuse the 'connect' interface? I think it conceptually brings chaos. Is
it better we create a new interface?

> 
> step 3: Moves the device to TDISP RUN state

Could you elaborate what '1'/'3'/'4' stand for?

Thanks,
Yilun

> 
> step 4: Load the driver again.

---

## [92] Dan Williams — 2025-02-25
*Subject: Re: [PATCH 03/11] coco/tsm: Introduce a class device for TEE
 Security Managers*

Jonathan Cameron wrote:
> On Thu, 05 Dec 2024 14:23:33 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

Yeah, subsys is awkward because even though this device is a singleton,
it is not a 'bus'. I will switch to 'struct tsm_core_dev' unless someone
comes up with a better name.

> 
> 

So, I do not think it matters in the end because there is no expectation
that anything but __free() invokes this call, and @subsys will be NULL
after no_free_ptr(). In general I expect that __free() callbacks should
mirror the "skip free()" condition in their DEFINE_FREE()
implementation. In this case though, the usage is so small and obvious
that we can pre-elide that code and just drop the duplicate check.

Going forward though I think this is something that deserves
clarification in cleanup.h documentation and I would argue that
DEFINE_FREE() and the __free handler duplicate the "skip free()"
condition check.

...or otherwise clarify the complication introduced by mixing ERR_PTR()
with no_free_ptr().

---

## [93] Dan Williams — 2025-02-25
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Jonathan Cameron wrote:
> On Thu, 05 Dec 2024 14:23:39 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:
[..]
> > diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> > new file mode 100644

Considering other feedback below, I will make this change.


> > +}
> > +

The from/to aspect is that the ide_cap of endpoints is ignored if the
device's root-port does not have IDE capability.

I will move the comment next to the "if (!rp->ide_cap)" check to make
this clearer.

> > +	 */
> > +	pci_read_config_dword(pdev, ide_cap + PCI_IDE_CAP, &val);

Makes sense, fixed.

> Or have a macro that always gets you to the selective part without
> using a zero length PCI_IDE_LINK_STREAM block.

Unless it gets multiple use I would open code it in ide.c.

> > +
> > +	for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val); i++) {

In other review feedback the discussion settled on only shipping offset + masks
in include/uapi/linux/pci_regs.h [1], and put any other logic related to
bitfield.h in ide.c.

[1]: http://lore.kernel.org/67b91d86a48aa_1c530f29431@dwillia2-xfh.jf.intel.com.notmuch


[..]
> > diff --git a/include/linux/pci.h b/include/linux/pci.h
> > index db9b47ce3eef..50811b7655dd 100644

I was trying to avoid extra config cycles in the common case, but there
is no precedent for caching extra offsets in 'struct pci_dev'.

I am ok to drop sel_ide_cap.

> 
> > +	int		nr_ide_mem;	/* - Address range limits for streams */

Might as well.

> 
> > +#define  PCI_IDE_CAP_ALG(x)		(((x) >> 8) & 0x1f) /* Supported Algorithms */

A mix of copying from the SEV-TIO vs TDX Connect RFCs. Per other
feedback, I have now resolved to only defines masks and offsets and drop
the decorated helpers that are open coding bitmask.h.

It turns out that __GENMASK is available in uapi/linux/bits.h, so I will
switch to that.

> > +#define  PCI_IDE_CAP_TEE_LIMITED	0x1000000 /* TEE-Limited Stream Supported */
> > +#define PCI_IDE_CTL			0x8

I will add the _0, but skip the rest for now. There is no precedence I
can see for the amount of degrees of freedom in this IDE register block for
the location of the selective registers, and Linux does not currently
have a use case for Link IDE. I imagine any Link Register Block walking
will live in ide.c. I.e. given Selective Stream block offset calculation
lives in ide.c might as well do the same for Link IDE when/if needed.

> 
> > +#define  PCI_IDE_LINK_CTL_EN		 0x1	/* Link IDE Stream Enable */

Ok

> 
> > +#define  PCI_IDE_LINK_CTL_TC(x)		 (((x) >> 19) & 0x7)  /* Traffic Class */

Ok

> 
> > +/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */

Ok

> 
> > +/* Selective IDE Stream Capability Register */

Dropped the macro, kept the mask.

> 
> > +/* Selective IDE Stream Control Register */

I agree and this matches other feedback prompting the "masks only"
stance.


> > +#define   PCI_IDE_SEL_CTL_ALG(x)	 (((x) >> 14) & 0x1f) /* Selected Algorithm */
> > +#define   PCI_IDE_SEL_CTL_TC(x)		 (((x) >> 19) & 0x7)  /* Traffic Class */

Fixed.

> 
> > +#define   PCI_IDE_SEL_CTL_ID_MASK	 0xff000000

Fixed.

> 
> > +#define   PCI_IDE_SEL_RID_2_SEG_MASK	 0xff000000

This was defining how much to shift the lower 32-bits of an address to
feed this value. Moved all that detail to ide.c

> 
> > +#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK  0xfff0000

Got it, thanks for going through all that!

---

## [94] Dan Williams — 2025-02-25
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Jonathan Cameron wrote:
> On Thu, 05 Dec 2024 14:23:45 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

I will just drop it for now as the entanglements with native PCI CMA are
not relevant in this changelog especially as is not clear which series
will land first.

The rewrite would have been:

--
CONFIG_PCI_TSM adds an "authenticated" attribute and "tsm/" subdirectory
to pci-sysfs. If native authentication is enabled then the existing
"authenticated" attribute is replaced. The presence of the "tsm/"
directory indicates what device authentication method is in effect.
--

> 
> > Consider that the TSM driver may
[..]
> > diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> > new file mode 100644

Grouped the PCI ones together and X-mas-treed it.

> > +#include "pci.h"
> > +

RIP.

> 
> > +		return -EINTR;

Ok.

> 
> 

Ok.

> 
> > +};

I will add "core" to the ones that are registering ops from the TSM core
to the PCI core.

> At least that's what I'm assuming is the difference between
> pci_tsm_unregister() tsm going vs

pci_destroy_dev() calls it.

---

## [95] Alexey Kardashevskiy — 2025-02-26
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 25/2/25 07:28, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>>

My current understanding of this the RIDs range is a firewall rule and 
not to tag PCIe trafic with a specific streamid, so:
the PF's RIDs should be just 1 RID of the RP;
the RP's RIDs should be the whole range of RIDs of that PF + all its VFs.

Or I am missing the point of it, am I? Thanks,

> Regardless, the PCI_IDE_SETUP_ROOT_PORT concept is dead so this could
> support distinct settings per Root Port vs endpoint, but I am missing

---

## [96] Dan Williams — 2025-02-25
*Subject: Re: [PATCH 06/11] samples/devsec: PCI device-security bus / endpoint
 sample*

Jonathan Cameron wrote:
> On Thu, 05 Dec 2024 14:23:51 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

Indeed there is, thanks.

[..]
> Similar to the case below. I'd rather see a per dev devm_ cleanup
> than relying on unified cleanup and that array having null entrees.

Done for ports and devs.

The arrays are used during PCI bus operations. This made me realize that
I should be putting the device and port allocation *before* the PCI bus
creation to make sure those arrays are dead and idle before the they are
invalidated by the port and dev devres actions.

[..]
> > +static int init_port(struct devsec_port *devsec_port)
> > +{

Sure.

> > +
> > +	init_ide(&devsec_port->ide);

Ok.

---

## [97] Aneesh Kumar K.V — 2025-02-26
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Fri, Feb 21, 2025 at 01:43:28PM +0530, Aneesh Kumar K.V wrote:
>> Alexey Kardashevskiy <aik@amd.com> writes:

For the current CCA implementation bind is equivalent to VDEV_CREATE
which doesn't mark the device LOCKED. Marking the device LOCKED is
driven by the guest as shown in the steps below.


>> 
>> Now in the guest we follow the below steps

I was looking at converting these numbers to strings.
"1" -> connect
"2" -> lock
"3" -> run


>
>> 

As mentioned above, them move the device to different TDISP state.

I will reply to this patch with my early RFC chnages for tsm framework.
I am not yet ready to share the CCA backend changes. But I assume having
the tsm framework changes alone can be useful?

-aneesh

---

## [98] Aneesh Kumar K.V (Arm) — 2025-02-26
*Subject: [RFC PATCH 1/7] tsm: Select PCI_DOE which is required for PCI_TSM*

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/Kconfig | 1 +
 1 file changed, 1 insertion(+)

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 8dab60dadb7d..f16d0e99a109 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -127,6 +127,7 @@ config PCI_IDE
 config PCI_TSM
 	bool "TEE Security Manager for PCI Device Security"
 	select PCI_IDE
+	select PCI_DOE
 	help
 	  The TEE (Trusted Execution Environment) Device Interface
 	  Security Protocol (TDISP) defines a "TSM" as a platform agent

---

## [99] Aneesh Kumar K.V (Arm) — 2025-02-26
*Subject: [RFC PATCH 2/7] tsm: Move tsm core outside the host directory*

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

## [100] Aneesh Kumar K.V (Arm) — 2025-02-26
*Subject: [RFC PATCH 3/7] tsm: vfio: Add tsm bind/unbind support*

This will be used to bind a TDI to the VM instance.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/tsm.c           |  48 +++++++++++++++
 drivers/vfio/pci/vfio_pci.c |  13 ++++
 drivers/vfio/vfio_main.c    |  31 ++++++++++
 include/linux/pci-tsm.h     |  17 ++++++
 include/linux/vfio.h        |   6 ++
 include/uapi/linux/kvm.h    |  17 ++++++
 virt/kvm/vfio.c             | 116 ++++++++++++++++++++++++++++++++++++
 7 files changed, 248 insertions(+)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 720b54d422b7..1a071130dea3 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -292,3 +292,51 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 		       req_sz, resp, resp_sz);
 }
 EXPORT_SYMBOL_GPL(pci_tsm_doe_transfer);
+
+static int __pci_tsm_bind(struct vfio_device *vfio_dev, u32 guest_rid)
+{
+	int rc;
+	struct pci_dev *pdev = to_pci_dev(vfio_dev->dev);
+	struct pci_tsm *pci_tsm = pdev->tsm;
+
+	scoped_cond_guard(mutex_intr, return -EINTR, &pci_tsm->lock) {
+		if (pci_tsm->state != PCI_TSM_CONNECT)
+			return -ENXIO;
+
+		/* This should hold a reference to the module providing tsm_ops */
+		rc = tsm_ops->bind(vfio_dev, guest_rid);
+		if (rc)
+			return rc;
+	}
+	return 0;
+}
+
+int pci_tsm_bind(struct vfio_device *vfio_dev, u32 guest_rid)
+{
+	int ret = -ENXIO;
+
+	scoped_cond_guard(rwsem_read_intr, return -EINTR, &pci_tsm_rwsem) {
+		if (tsm_ops)
+			ret = __pci_tsm_bind(vfio_dev, guest_rid);
+	}
+	return ret;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_bind);
+
+/*
+ * pci_tsm_ops can't be NULL since we hold a module reference during bind.
+ * Hence No pci_tsm_rwsem locking needed.
+ */
+void pci_tsm_unbind(struct vfio_device *vfio_dev)
+{
+	struct pci_dev *pdev = to_pci_dev(vfio_dev->dev);
+	struct pci_tsm *pci_tsm = pdev->tsm;
+
+	scoped_cond_guard(mutex_intr, return, &pci_tsm->lock) {
+		if (pci_tsm->state != PCI_TSM_BOUND)
+			return;
+
+		tsm_ops->unbind(vfio_dev);
+	}
+}
+EXPORT_SYMBOL_GPL(pci_tsm_unbind);
diff --git a/drivers/vfio/pci/vfio_pci.c b/drivers/vfio/pci/vfio_pci.c
index e727941f589d..a1e1eb4c26db 100644
--- a/drivers/vfio/pci/vfio_pci.c
+++ b/drivers/vfio/pci/vfio_pci.c
@@ -24,6 +24,7 @@
 #include <linux/slab.h>
 #include <linux/types.h>
 #include <linux/uaccess.h>
+#include <linux/pci-tsm.h>
 
 #include "vfio_pci_priv.h"
 
@@ -127,6 +128,16 @@ static int vfio_pci_open_device(struct vfio_device *core_vdev)
 	return 0;
 }
 
+static int vfio_pci_tsm_bind(struct vfio_device *core_vdev, u32 guest_rid)
+{
+	return pci_tsm_bind(core_vdev, guest_rid);
+}
+
+static void vfio_pci_tsm_unbind(struct vfio_device *core_vdev)
+{
+	return pci_tsm_unbind(core_vdev);
+}
+
 static const struct vfio_device_ops vfio_pci_ops = {
 	.name		= "vfio-pci",
 	.init		= vfio_pci_core_init_dev,
@@ -144,6 +155,8 @@ static const struct vfio_device_ops vfio_pci_ops = {
 	.unbind_iommufd	= vfio_iommufd_physical_unbind,
 	.attach_ioas	= vfio_iommufd_physical_attach_ioas,
 	.detach_ioas	= vfio_iommufd_physical_detach_ioas,
+	.tsm_bind	= vfio_pci_tsm_bind,
+	.tsm_unbind	= vfio_pci_tsm_unbind,
 };
 
 static int vfio_pci_probe(struct pci_dev *pdev, const struct pci_device_id *id)
diff --git a/drivers/vfio/vfio_main.c b/drivers/vfio/vfio_main.c
index 1fd261efc582..b24644c9c841 100644
--- a/drivers/vfio/vfio_main.c
+++ b/drivers/vfio/vfio_main.c
@@ -462,6 +462,21 @@ void vfio_device_get_kvm_safe(struct vfio_device *device, struct kvm *kvm)
 	device->kvm = kvm;
 }
 
+int vfio_tsm_bind(struct kvm *kvm, struct vfio_device *vdev, u32 guest_rid)
+{
+	if (vdev->ops->tsm_bind)
+		return vdev->ops->tsm_bind(vdev, guest_rid);
+	return -EINVAL;
+}
+EXPORT_SYMBOL_GPL(vfio_tsm_bind);
+
+void vfio_tsm_unbind(struct kvm *kvm, struct vfio_device *vdev)
+{
+	if (vdev->ops->tsm_bind)
+		return vdev->ops->tsm_unbind(vdev);
+}
+EXPORT_SYMBOL_GPL(vfio_tsm_unbind);
+
 void vfio_device_put_kvm(struct vfio_device *device)
 {
 	lockdep_assert_held(&device->dev_set->lock);
@@ -472,6 +487,11 @@ void vfio_device_put_kvm(struct vfio_device *device)
 	if (WARN_ON(!device->put_kvm))
 		goto clear;
 
+	/* Unbind TDI here */
+	vfio_tsm_unbind(device->kvm, device);
+	/* drop the reference held in kvm_dev_tsm_bind */
+	vfio_put_device(device);
+
 	device->put_kvm(device->kvm);
 	device->put_kvm = NULL;
 	symbol_put(kvm_put_kvm);
@@ -1447,6 +1467,17 @@ void vfio_file_set_kvm(struct file *file, struct kvm *kvm)
 }
 EXPORT_SYMBOL_GPL(vfio_file_set_kvm);
 
+struct vfio_device *vfio_file_device(struct file *filep)
+{
+	struct vfio_device_file *df = filep->private_data;
+
+	if (filep->f_op != &vfio_device_fops)
+		return NULL;
+
+	return df->device;
+}
+EXPORT_SYMBOL_GPL(vfio_file_device);
+
 /*
  * Sub-module support
  */
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index beb0d68129bc..774496d7b37e 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -2,6 +2,7 @@
 #ifndef __PCI_TSM_H
 #define __PCI_TSM_H
 #include <linux/mutex.h>
+#include <linux/vfio_pci_core.h>
 
 struct pci_dev;
 
@@ -17,6 +18,7 @@ enum pci_tsm_state {
 	PCI_TSM_ERR = -1,
 	PCI_TSM_INIT,
 	PCI_TSM_CONNECT,
+	PCI_TSM_BOUND,
 };
 
 /**
@@ -49,6 +51,8 @@ struct pci_tsm_ops {
 	void (*remove)(struct pci_dsm *dsm);
 	int (*connect)(struct pci_dev *pdev);
 	void (*disconnect)(struct pci_dev *pdev);
+	int (*bind)(struct vfio_device *vfio_dev, u32 guest_rid);
+	void (*unbind)(struct vfio_device *vfio_dev);
 };
 
 enum pci_doe_proto {
@@ -63,6 +67,9 @@ void pci_tsm_unregister(const struct pci_tsm_ops *ops);
 int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 			 const void *req, size_t req_sz, void *resp,
 			 size_t resp_sz);
+int pci_tsm_bind(struct vfio_device *vfio_dev, u32 guest_rid);
+void pci_tsm_unbind(struct vfio_device *vfio_dev);
+
 #else
 static inline int pci_tsm_register(const struct pci_tsm_ops *ops,
 				   const struct attribute_group *grp)
@@ -79,5 +86,15 @@ static inline int pci_tsm_doe_transfer(struct pci_dev *pdev,
 {
 	return -ENOENT;
 }
+
+static inline int pci_tsm_bind(struct vfio_device *vifo_dev, u32 guest_rid);
+{
+	return -EINVAL;
+}
+
+static inline void pci_tsm_unbind(struct vfio_device *vfio_dev)
+{
+	return -EINVAL;
+}
 #endif
 #endif /*__PCI_TSM_H */
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index 000a6cab2d31..a177dcade4aa 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -129,6 +129,8 @@ struct vfio_device_ops {
 	void	(*dma_unmap)(struct vfio_device *vdev, u64 iova, u64 length);
 	int	(*device_feature)(struct vfio_device *device, u32 flags,
 				  void __user *arg, size_t argsz);
+	int	(*tsm_bind)(struct vfio_device *vdev, u32 guest_rid);
+	void	(*tsm_unbind)(struct vfio_device *vdev);
 };
 
 #if IS_ENABLED(CONFIG_IOMMUFD)
@@ -316,6 +318,10 @@ static inline bool vfio_file_has_dev(struct file *file, struct vfio_device *devi
 bool vfio_file_is_valid(struct file *file);
 bool vfio_file_enforced_coherent(struct file *file);
 void vfio_file_set_kvm(struct file *file, struct kvm *kvm);
+struct vfio_device *vfio_file_device(struct file *file);
+void vfio_tsm_unbind(struct kvm *kvm, struct vfio_device *vdev);
+int vfio_tsm_bind(struct kvm *kvm, struct vfio_device *vdev, u32 guest_rid);
+
 
 #define VFIO_PIN_PAGES_MAX_ENTRIES	(PAGE_SIZE/sizeof(unsigned long))
 
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 9cabf9b6a9b4..6c251f04c5dd 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -1604,4 +1604,21 @@ struct kvm_arm_rmm_psci_complete {
 /* FIXME: Update nr (0xd2) when merging */
 #define KVM_ARM_VCPU_RMM_PSCI_COMPLETE	_IOW(KVMIO, 0xd2, struct kvm_arm_rmm_psci_complete)
 
+#define  KVM_DEV_VFIO_DEVICE			2
+#define  KVM_DEV_VFIO_DEVICE_TDI_BIND		1
+#define  KVM_DEV_VFIO_DEVICE_TDI_UNBIND		2
+
+/*
+ * struct kvm_vfio_tsm_bind
+ *
+ * @guest_rid: Hypervisor provided identifier used by the guest to identify
+ *             the TDI in guest messages
+ * @devfd: a fd of VFIO device
+ */
+struct kvm_vfio_tsm_bind {
+	__u32 guest_rid;
+	__s32 devfd;
+} __packed;
+
+
 #endif /* __LINUX_KVM_H */
diff --git a/virt/kvm/vfio.c b/virt/kvm/vfio.c
index 196a102e34fb..525aeccfaf2b 100644
--- a/virt/kvm/vfio.c
+++ b/virt/kvm/vfio.c
@@ -15,6 +15,7 @@
 #include <linux/slab.h>
 #include <linux/uaccess.h>
 #include <linux/vfio.h>
+#include <linux/tsm.h>
 #include "vfio.h"
 
 #ifdef CONFIG_SPAPR_TCE_IOMMU
@@ -80,6 +81,23 @@ static bool kvm_vfio_file_is_valid(struct file *file)
 	return ret;
 }
 
+static struct vfio_device *kvm_vfio_file_device(struct file *file)
+{
+	struct vfio_device *(*fn)(struct file *file);
+	struct vfio_device *ret;
+
+	fn = symbol_get(vfio_file_device);
+	if (!fn)
+		return NULL;
+
+	ret = fn(file);
+
+	symbol_put(vfio_file_device);
+
+	return ret;
+}
+
+
 #ifdef CONFIG_SPAPR_TCE_IOMMU
 static struct iommu_group *kvm_vfio_file_iommu_group(struct file *file)
 {
@@ -291,6 +309,94 @@ static int kvm_vfio_set_file(struct kvm_device *dev, long attr,
 	return -ENXIO;
 }
 
+static int kvm_dev_tsm_bind(struct kvm_device *dev, void __user *arg)
+{
+	int (*tsm_bind)(struct kvm *kvm, struct vfio_device *vdev, u32 guest_rid);
+	struct kvm_vfio *kv = dev->private;
+	struct kvm_vfio_tsm_bind tb;
+	struct vfio_device *vdev;
+	struct file *filp;
+	int ret;
+
+	if (copy_from_user(&tb, arg, sizeof(tb)))
+		return -EFAULT;
+
+	filp = fget(tb.devfd);
+	if (!filp)
+		return -EBADF;
+
+	ret = -ENOENT;
+
+	tsm_bind = symbol_get(vfio_tsm_bind);
+	if (!tsm_bind)
+		goto err_out;
+
+	mutex_lock(&kv->lock);
+	vdev = kvm_vfio_file_device(filp);
+	if (vdev) {
+		/* hold the reference to the vfio device file when we bind. */
+		get_device(&vdev->device);
+		ret = (*tsm_bind)(dev->kvm, vdev, tb.guest_rid);
+		if (ret)
+			vfio_put_device(vdev);
+	}
+	mutex_unlock(&kv->lock);
+	symbol_put(vfio_tsm_bind);
+err_out:
+	fput(filp);
+	return ret;
+}
+
+static int kvm_dev_tsm_unbind(struct kvm_device *dev, void __user *arg)
+{
+	void (*tsm_unbind)(struct kvm *kvm, struct vfio_device *vdev);
+	struct kvm_vfio *kv = dev->private;
+	struct kvm_vfio_tsm_bind tb;
+	struct vfio_device *vdev;
+	struct file *filp;
+	int ret;
+
+	if (copy_from_user(&tb, arg, sizeof(tb)))
+		return -EFAULT;
+
+	filp = fget(tb.devfd);
+	if (!filp)
+		return -EBADF;
+
+	ret = -ENOENT;
+
+	tsm_unbind = symbol_get(vfio_tsm_unbind);
+	if (!tsm_unbind)
+		goto err_out;
+
+	mutex_lock(&kv->lock);
+	vdev = kvm_vfio_file_device(filp);
+	if (vdev) {
+		(*tsm_unbind)(dev->kvm, vdev);
+		/* drop the reference held in kvm_dev_tsm_bind */
+		vfio_put_device(vdev);
+		ret = 0;
+	}
+	mutex_unlock(&kv->lock);
+	symbol_put(vfio_tsm_unbind);
+err_out:
+	fput(filp);
+	return ret;
+}
+
+static int kvm_vfio_set_device(struct kvm_device *dev, long attr,
+			       void __user *arg)
+{
+	switch (attr) {
+	case KVM_DEV_VFIO_DEVICE_TDI_BIND:
+		return kvm_dev_tsm_bind(dev, arg);
+	case KVM_DEV_VFIO_DEVICE_TDI_UNBIND:
+		return kvm_dev_tsm_unbind(dev, arg);
+	}
+
+	return -ENXIO;
+}
+
 static int kvm_vfio_set_attr(struct kvm_device *dev,
 			     struct kvm_device_attr *attr)
 {
@@ -298,6 +404,9 @@ static int kvm_vfio_set_attr(struct kvm_device *dev,
 	case KVM_DEV_VFIO_FILE:
 		return kvm_vfio_set_file(dev, attr->attr,
 					 u64_to_user_ptr(attr->addr));
+	case KVM_DEV_VFIO_DEVICE:
+		return kvm_vfio_set_device(dev, attr->attr,
+					   u64_to_user_ptr(attr->addr));
 	}
 
 	return -ENXIO;
@@ -317,6 +426,13 @@ static int kvm_vfio_has_attr(struct kvm_device *dev,
 			return 0;
 		}
 
+		break;
+	case KVM_DEV_VFIO_DEVICE:
+		switch (attr->attr) {
+		case KVM_DEV_VFIO_DEVICE_TDI_BIND:
+		case KVM_DEV_VFIO_DEVICE_TDI_UNBIND:
+			return 0;
+		}
 		break;
 	}

---

## [101] Aneesh Kumar K.V (Arm) — 2025-02-26
*Subject: [RFC PATCH 4/7] tsm: Allow tsm ops function to be called for multi-function devices*

IDE spec says "For Endpoints, including Functions of a Multi-Function
Device, associated with an Upstream Port, only Function 0 must implement
the IDE Extended Capability." So we expect ide_cap to be present only
for function 0. Allow tsm probe ops to be called for all PCI devices

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/tsm.c | 3 +--
 1 file changed, 1 insertion(+), 2 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 1a071130dea3..e798d9bf3da4 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -176,8 +176,7 @@ static void __pci_tsm_init(struct pci_dev *pdev)
 		return;
 
 	tee_cap = pdev->devcap & PCI_EXP_DEVCAP_TEE;
-
-	if (!(pdev->ide_cap || tee_cap))
+	if (!tee_cap)
 		return;
 
 	lockdep_assert_held_write(&pci_tsm_rwsem);

---

## [102] Aneesh Kumar K.V (Arm) — 2025-02-26
*Subject: [RFC PATCH 5/7] tsm: Don't error out for doe mailbox failure*

Only function 0 is expected to support the DOE mailbox.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/tsm.c | 13 ++++---------
 1 file changed, 4 insertions(+), 9 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index e798d9bf3da4..a0deddac6767 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -192,21 +192,16 @@ static void __pci_tsm_init(struct pci_dev *pdev)
 	 * a candidate to connect with the platform TSM
 	 */
 	struct pci_dsm *dsm __free(dsm_remove) = tsm_ops->probe(pdev);
-
-	pci_dbg(pdev, "Device security capabilities detected (%s%s ), TSM %s\n",
-		pdev->ide_cap ? " ide" : "", tee_cap ? " tee" : "",
-		dsm ? "attach" : "skip");
-
 	if (!dsm)
 		return;
 
 	mutex_init(&pci_tsm->lock);
 	pci_tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
 					       PCI_DOE_PROTO_CMA);
-	if (!pci_tsm->doe_mb) {
-		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
-		return;
-	}
+	pci_info(pdev, "Device security capabilities detected (%s%s%s)\n",
+		 pdev->ide_cap ? " ide" : "",
+		 tee_cap ? " tee" : "",
+		 pci_tsm->doe_mb ? " doe" : "");
 
 	pci_tsm->state = PCI_TSM_INIT;
 	pci_tsm->dsm = no_free_ptr(dsm);

---

## [103] Aneesh Kumar K.V (Arm) — 2025-02-26
*Subject: [RFC PATCH 6/7] tsm: Allow tsm connect ops to be used for multiple operations*

The connect sysfs file will be used in the guest for TDISP locking and
transitioning the device to the run state.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/tsm.c       | 16 +++++++---------
 include/linux/pci-tsm.h |  4 +++-
 2 files changed, 10 insertions(+), 10 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index a0deddac6767..3251dc5eeef8 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -45,7 +45,7 @@ static int pci_tsm_disconnect(struct pci_dev *pdev)
 	return 0;
 }
 
-static int pci_tsm_connect(struct pci_dev *pdev)
+static int pci_tsm_connect(struct pci_dev *pdev, int new_state)
 {
 	struct pci_tsm *pci_tsm = pdev->tsm;
 	int rc;
@@ -53,15 +53,13 @@ static int pci_tsm_connect(struct pci_dev *pdev)
 	lockdep_assert_held(&pci_tsm_rwsem);
 
 	scoped_cond_guard(mutex_intr, return -EINTR, &pci_tsm->lock) {
-		if (pci_tsm->state >= PCI_TSM_CONNECT)
-			return 0;
+
 		if (pci_tsm->state < PCI_TSM_INIT)
 			return -ENXIO;
 
-		rc = tsm_ops->connect(pdev);
+		rc = tsm_ops->connect(pdev, new_state);
 		if (rc)
 			return rc;
-		pci_tsm->state = PCI_TSM_CONNECT;
 	}
 	return 0;
 }
@@ -70,16 +68,16 @@ static ssize_t connect_store(struct device *dev, struct device_attribute *attr,
 			     const char *buf, size_t len)
 {
 	int rc;
-	bool connect;
+	int connect;
 	struct pci_dev *pdev = to_pci_dev(dev);
 
-	rc = kstrtobool(buf, &connect);
+	rc = kstrtoint(buf, 0, &connect);
 	if (rc)
 		return rc;
 
 	scoped_cond_guard(rwsem_read_intr, return -EINTR, &pci_tsm_rwsem) {
 		if (connect)
-			rc = pci_tsm_connect(pdev);
+			rc = pci_tsm_connect(pdev, connect);
 		else
 			rc = pci_tsm_disconnect(pdev);
 		if (rc)
@@ -97,7 +95,7 @@ static ssize_t connect_show(struct device *dev, struct device_attribute *attr,
 	scoped_cond_guard(rwsem_read_intr, return -EINTR, &pci_tsm_rwsem) {
 		if (!pdev->tsm)
 			return -ENXIO;
-		connect_status = pdev->tsm->state >= PCI_TSM_CONNECT;
+		connect_status = pdev->tsm->state;
 	}
 	return sysfs_emit(buf, "%d\n", connect_status);
 }
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 774496d7b37e..6ad2081a329d 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -19,6 +19,8 @@ enum pci_tsm_state {
 	PCI_TSM_INIT,
 	PCI_TSM_CONNECT,
 	PCI_TSM_BOUND,
+	PCI_TSM_LOCKED,
+	PCI_TSM_RUN,
 };
 
 /**
@@ -49,7 +51,7 @@ struct pci_tsm {
 struct pci_tsm_ops {
 	struct pci_dsm *(*probe)(struct pci_dev *pdev);
 	void (*remove)(struct pci_dsm *dsm);
-	int (*connect)(struct pci_dev *pdev);
+	int (*connect)(struct pci_dev *pdev, int new_state);
 	void (*disconnect)(struct pci_dev *pdev);
 	int (*bind)(struct vfio_device *vfio_dev, u32 guest_rid);
 	void (*unbind)(struct vfio_device *vfio_dev);

---

## [104] Aneesh Kumar K.V (Arm) — 2025-02-26
*Subject: [RFC PATCH 7/7] tsm: Add secure SPDM support*

Add secure doe mailbox support

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/pci/tsm.c       | 24 +++++++++++++++++++-----
 include/linux/pci-tsm.h |  1 +
 2 files changed, 20 insertions(+), 5 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 3251dc5eeef8..cb251497ca68 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -194,12 +194,16 @@ static void __pci_tsm_init(struct pci_dev *pdev)
 		return;
 
 	mutex_init(&pci_tsm->lock);
-	pci_tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+	pci_tsm->doe_mb 	= pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
 					       PCI_DOE_PROTO_CMA);
-	pci_info(pdev, "Device security capabilities detected (%s%s%s)\n",
+	pci_tsm->doe_secure_mb 	= pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					       PCI_DOE_PROTO_SSESSION);
+
+	pci_info(pdev, "Device security capabilities detected (%s%s%s%s)\n",
 		 pdev->ide_cap ? " ide" : "",
 		 tee_cap ? " tee" : "",
-		 pci_tsm->doe_mb ? " doe" : "");
+		 pci_tsm->doe_mb ? " doe" : "",
+		 pci_tsm->doe_secure_mb ? " secure-doe" : "");
 
 	pci_tsm->state = PCI_TSM_INIT;
 	pci_tsm->dsm = no_free_ptr(dsm);
@@ -277,10 +281,20 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, enum pci_doe_proto type,
 			 const void *req, size_t req_sz, void *resp,
 			 size_t resp_sz)
 {
-	if (!pdev->tsm || !pdev->tsm->doe_mb)
+	struct pci_doe_mb *mb = NULL;
+
+	if (!pdev->tsm)
+		return -ENXIO;
+
+	if (type == PCI_DOE_PROTO_CMA)
+		mb = pdev->tsm->doe_mb;
+	else if (type == PCI_DOE_PROTO_SSESSION)
+		mb = pdev->tsm->doe_secure_mb;
+
+	if (!mb)
 		return -ENXIO;
 
-	return pci_doe(pdev->tsm->doe_mb, PCI_VENDOR_ID_PCI_SIG, type, req,
+	return pci_doe(mb, PCI_VENDOR_ID_PCI_SIG, type, req,
 		       req_sz, resp, resp_sz);
 }
 EXPORT_SYMBOL_GPL(pci_tsm_doe_transfer);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 6ad2081a329d..815da9c3fc50 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -34,6 +34,7 @@ struct pci_tsm {
 	enum pci_tsm_state state;
 	struct mutex lock;
 	struct pci_doe_mb *doe_mb;
+	struct pci_doe_mb *doe_secure_mb;
 	struct pci_dsm *dsm;
 };

---

## [105] Xu Yilun — 2025-02-27
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On Wed, Feb 26, 2025 at 05:40:02PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

Could you elaborate why vdev create & LOCK can't be done at the same
time, when guest requests "lock"? Intel TDX also requires firmware calls
like tdi_create(alloc metadata) & tdi_bind(do LOCK), but I don't see
there is need to break them out in different phases.

> 
> 

What does "connect" do in guest?

Thanks,
Yilun

> "2" -> lock
> "3" -> run

---

## [106] Xu Yilun — 2025-02-27
*Subject: Re: [RFC PATCH 7/7] tsm: Add secure SPDM support*

On Wed, Feb 26, 2025 at 05:43:23PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Add secure doe mailbox support
> 

Do you have 2 doe mb instances on PCI cap? And one only support CMA,
another only support SSESSION?

If it is not the case, pci_tsm->doe_mb & pci_tsm->doe_secure_mb are
likely the same one.

Thanks,
Yilun

> +
> +	pci_info(pdev, "Device security capabilities detected (%s%s%s%s)\n",

---

## [107] Aneesh Kumar K.V — 2025-02-27
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Wed, Feb 26, 2025 at 05:40:02PM +0530, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

Yes, that is possible and might be what I will end up doing. Right now
I have kept the interface flexible enough as I am writing these changes.
Device can possibly be presented in locked state to the guest.

>
>> 

Nothing much for now. I added that to keep it consistent with host
workflow. That is device transition from PCI_TSM_INIT -> PCI_TSM_CONNECT
-> PCI_TSM_BOUND -> PCI_TSM_LOCK -> PCI_TSM_RUN.

Relevant part of the TSM backend in guest

static int cca_tsm_connect(struct pci_dev *pdev, int new_state)
{
	unsigned long ret;
	int connect_state;
	struct pci_tsm *pci_tsm = pdev->tsm;

	connect_state = pci_tsm->state;
	switch (new_state) {
	case PCI_TSM_CONNECT:
		pci_tsm->state = PCI_TSM_CONNECT;
		break;
	case PCI_TSM_LOCKED:
		if (connect_state != PCI_TSM_CONNECT)
			return -EINVAL;

		ret = rsi_device_lock(pdev);
		if (ret) {
			pci_err(pdev, "failed to lock the device (%lu)\n", ret);
			return -EIO;
		}
		pci_tsm->state = PCI_TSM_LOCKED;
		break;


-aneesh

---

## [108] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

I plan to switch focus to the bind flow after we achieve consensus on
the base TSM framework pieces, but my initial reaction is that
separating "bind" from "lock" is a finer grained state transition than
has been discussed previously. There are end use cases that justify
exposing LOCKED vs RUN in the ABI, but could point to the use case for
separating the BOUND vs LOCKED states?

> >> Now in the guest we follow the below steps
> >> 

I have been modeling Host-side "connect" as IDE establishment on the PF
while Guest-side "connect" arranges for "bind+lock" on an assigned
function / TDI. Do we really need to expose "lock" as an explicit state
vs interpret what "connect" means in the different contexts?

> "3" -> run
> 

Yes. There are so many moving pieces and multiple vendors that the only
way to make progress here is to wrestle the common pieces into a form
that all vendors can agree. Feel free to extend the samples/devsec/
implementation to demonstrate flows that CCA needs. The idea is that
sample implementation serves as both a reference implementation and a
simple smoke test for all the common core pieces.

---

## [109] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 11/11] samples/devsec: Add sample IDE establishment*

Jonathan Cameron wrote:
> On Thu, 05 Dec 2024 14:24:19 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

Yeah, that was a leak, now fixed and symmetric.

> > +	return rc;
> >  }

Also fixed with the same symmetry as the connect unwind case.

---

## [110] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 09/11] PCI/IDE: Report available IDE streams*

Alexey Kardashevskiy wrote:
> On 6/12/24 09:24, Dan Williams wrote:
> > The limited number of link-encryption (IDE) streams that a given set of

Oh, interesting, will fix that up when sending v2 based on v6.14-rc.


> Hm. Also probably all exports should be PCI_IDE NS, 
> or none. Thanks,

I will add a comment for why this one is namespaced and the others are
not. I am also renaming it to pci_ide_init_nr_streams() to reflect this
detail:

/**
 * pci_init_nr_ide_streams() - size the pool of IDE Stream resources
 * @hb: host bridge boundary for the stream pool
 * @nr: number of streams
 *
 * Enable IDE Stream establishment by setting the number of stream
 * resources available at the host bridge. Platform init code must set
 * this before the first pci_ide_stream_alloc() call.
 *
 * The "PCI_IDE" symbol namespace is required because this is typically
 * a detail that is settled in early PCI init, i.e. only an expert or
 * test module should consume this export.
 */

---

## [111] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 04/11] PCI/IDE: Selective Stream IDE enumeration*

Alexey Kardashevskiy wrote:
> On 21/2/25 05:07, Dan Williams wrote:
> > Alexey Kardashevskiy wrote:
[..]
> > 
> > Whoops, was moving too fast, fixed.

In fact I have dropped error prone mask definitions and "getter" macros
altogether after other comments from Yilun and Jonathan.

I noticed that back in v6.9 Paolo had the good sense to do this:

    3c7a8e190bc5 uapi: introduce uapi-friendly macros for GENMASK

...so now all the IDE defines that need a mask are using __GENMASK in
v2.

---

## [112] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Xu Yilun wrote:
> On Fri, Feb 21, 2025 at 05:15:24PM -0800, Dan Williams wrote:
> > Xu Yilun wrote:

I do think it makes sense to have one ->tsm pointer from a PCI device to
represent any possible TSM context, but I do not think it makes sense
for that context to always contain members that are only relevant to PF
Function 0. So, here is an updated proposal:

/**
 * struct pci_tsm - Core TSM context for a given PCIe endpoint
 * @pdev: indicates the type of pci_tsm object
 *
 * This structure is wrapped by a low level TSM driver and returned by
 * tsm_ops.probe(), it is freed by tsm_ops.remove(). Depending on
 * whether @pdev is physical function 0, another physical function, or a
 * virtual function determines the pci_tsm object type. E.g. see 'struct
 * pci_tsm_pf0'.
 */
struct pci_tsm {
        struct pci_dev *pdev;
};

/**
 * struct pci_tsm_pf0 - Physical Function 0 TDISP context
 * @state: reflect device initialized, connected, or bound
 * @lock: protect @state vs pci_tsm_ops invocation
 * @doe_mb: PCIe Data Object Exchange mailbox
 */
struct pci_tsm_pf0 {
        enum pci_tsm_state state;
        struct mutex lock;
        struct pci_doe_mb *doe_mb;
        struct pci_tsm tsm;
};

This arrangement lets the core 'struct pci_tsm' object hold
common-to-all device-type details like a 'struct pci_tdi' pointer. For
physical function0 devices the core does:

   container_of(pdev->tsm, struct pci_tsm_pf0, tsm)

...to get to those exclusive details.

> > > > +
> > > > +	tee_cap = pdev->devcap & PCI_EXP_DEVCAP_TEE;

Yes, makes sense. I will work on moving the physical function0 data
out-of-line from the core 'struct pci_tsm' definition.

So, 'struct pci_tdi' is common to 'struct pci_tsm' since any PCI
function can become a TDI. If VFs or non-function0 functions need
addtional context we could create a 'struct pci_tsm_vf' or similar for
that data.

---

## [113] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

Ilpo J�rvinen wrote:
> > Oh, good to hear (the dangers of replying to patch feedback in response
> > order unfortunately means I missed this in my earlier reply). Please

Oh, I indeed missed it.

> ...There has been no discussion about it though.

Might just need to bump it with Martin with the new information that the
kernel is going to start caring about it soon.

---

## [114] Xu Yilun — 2025-02-28
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On Thu, Feb 27, 2025 at 07:27:22PM +0530, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 

Good to know that, thanks.

> Device can possibly be presented in locked state to the guest.

This is also what I did before. But finally I dropped (or pending) this
"early binding" support. There are several reset operations during VM
setup and booting, especially the ones in bios. They breaks LOCK state
and I have to make VFIO suppress the reset, or reset & recover, but that
seems not worth the effort.

May wanna know how you see this problem.

Thanks,
Yilun

---

## [115] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
[..]
> >> And it just leaves link streams unconfigured. So I have to work around
> >> my device by writing unique numbers to all streams (link + selective)

It would be great if by the time this device hit production that problem
could be fixed, but hey, errata happens.

> > Can you say whether this problem is going to escape your test bench into
> > something mainline Linux needs to worry about?

Linux has a role to play here in influencing what is acceptable in
advance of the specification catching up to provide an implementation
clarification.

> https://github.com/aik/linux/commit/745ee4e151bcc8e3b6db8281af445ab498e87a70

I would not expect the core to have a "Some devices insist on streamid
to be unique even for not enabled streams" path that gets inflicted on
everything unless it is clear that this bug is not not limited to this
one device.

Also, I expect the workaround needs to be re-applied at every Stream
establishment event especially to support TSM implementations that
allocate the Stream ID. I.e. it is presumptuous for the core to assume
that it can pick Stream IDs at pci_ide_init() time.

It would be great if Linux could just say "the maximum number of
potential Stream IDs is 255 (instead of 256). All TSM implementations
must allocate starting at 1". Then this conflict never exists for the
default Stream ID 0 case. That is, if this problem is widespread.

Otherwise, at pci_ide_stream_setup() time I expect that the core would
need to do something gross like check the incoming Stream ID and walk
all idle streams to make sure they are not aliasing that ID.

> >> And then what are we doing to do when we start adding link streams? I
> >> suggest decoupling pci_ide::stream_id from stream_id in sel_ide_offset()

CXL TSP is a wholly separate operation model and it expects that CXL
devices, and more specifically CXL memory, are inside the TCB before the
OS boots. So there is no current need for Linux to consider Link IDE for
CXL.

> > We can always cross that sophistication bridge later.
> 

Sounds good.

---

## [116] Dan Williams — 2025-02-27
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Alexey Kardashevskiy wrote:
[..]
> >> aik@sc ~> ls /sys/class/tsm-tdi/
> >> tdi:0000:c0:01.1  tdi:0000:e0:01.1  tdi:0000:e1:00.0  tdi:0000:e1:04.0

I understand the temptation to consider "what if", but we have more than
enough complication and details to settle without the additional burden
of "maybe another bus will need this one day, so lets commit to a more
sophisticated (more device objects) ABI just in case".

For the specific case of CXL there is already the TSP specification. CXL
TSP does not call for any OS support beyond the existing memory
acceptance flow. I.e. CXL TSP pulls CXL.mem into the TCB just like DDR
does not need any enabling beyond asking the TSM if the physical address
supports shared-to-private memory conversion.

If another bus shows up tomorrow wanting to reuse the concepts there is
nothing stopping them from adding "authenticated", "tsm/connect", etc
attributes to their devices. So the proposed ABI is not tied to PCI.

The simple model of "device has security attributes" is scalable in a
way that "tdi child devices" is not. The statement, "the concept is
generic really", goes both ways. It implies not only "TDISP on other
buses", but also "device-security that is not TDISP". Unlike theoretical
"TDISP on other buses", "device-security that is not TDISP" is a
practical concern. It already has patches on the list.

---

## [117] Xu Yilun — 2025-02-28
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On Thu, Feb 27, 2025 at 04:15:26PM -0800, Dan Williams wrote:
> Xu Yilun wrote:
> > On Fri, Feb 21, 2025 at 05:15:24PM -0800, Dan Williams wrote:

I think the scope of the lock should expand to pci_tsm_ops::bind(), we
need to ensure the TDI bind won't race with its PF0's (dis)connect.

  struct pci_tsm {
	struct pci_dev *pdev;
	struct pci_tdi *tdi;
  };

  struct pci_tdi {
	struct pci_tsm_pf0 *tsm_pf0;
	...
  };

  int pci_tdi_lock(struct pci_tdi *tdi)
  {
	mutex_lock(&tdi->tsm_pf0->lock);
  }

Thanks,
Yilun

>         struct pci_doe_mb *doe_mb;
>         struct pci_tsm tsm;

---

## [118] Aneesh Kumar K.V — 2025-02-28
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Xu Yilun <yilun.xu@linux.intel.com> writes:

> On Thu, Feb 27, 2025 at 07:27:22PM +0530, Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

Currently, my approach involves a split vdev_create and a TDISP lock, which is
why I haven't encountered the issue mentioned above. The current changes
implement vdev_create via the VMM, while the guest makes an RSI call to
switch the device to the locked state.

I chose to separate vdev_create and TDISP lock into two distinct steps
to simplify the process and better align it with the RMM spec [1].

I noticed that SEV-TIO performs a KVM_EXIT_VMGEXIT, which carries out a
similar operation unless it has already been handled during VM startup.
From your reply above, I understand there was a proposal to combine
VDEV_CREATE and TDISP_LOCK. However, you also mentioned that if we
present the device in a locked state to a VM early in the boot process,
we might unintentionally break the TDISP lock state.

I will look up the previous discussions to better understand the
rationale behind combining vdev_create and lock.

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp12.zip

-aneesh

---

## [119] Aneesh Kumar K.V — 2025-02-28
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

Dan Williams <dan.j.williams@intel.com> writes:

> Aneesh Kumar K.V wrote:
>> Xu Yilun <yilun.xu@linux.intel.com> writes:

Can you share the link or reference to the previous discussion? I wasn’t
aware of it.

I chose to implement vdev_create and TDISP lock as two separate steps to
better align with the RMM spec[1]. Additionally, there is a possibility
that the guest might need to perform certain operations that either
cannot be executed in the TDISP locked state or would cause the device
to transition to an unlocked state.

In such cases, wouldn’t we need a guest interface to move the device
back to the locked state? I understand that this process might trigger a
device reset, which could even require a full restart of the device
assignment workflow

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp12.zip

>
>> >> Now in the guest we follow the below steps

One possible use case I was considering is a guest needing to perform
certain operations before the device transitions to the locked state.

>> "3" -> run
>> 

I haven't looked at samples/devsec yet because it has an x86 PCI
dependency, and it was easier to get the ARM RME backend working.
However, I will try to update devsec to work with ARM RME as well

-aneesh

---

## [120] Xu Yilun — 2025-03-01
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

> >> >> For the current CCA implementation bind is equivalent to VDEV_CREATE
> >> >> which doesn't mark the device LOCKED. Marking the device LOCKED is

That doesn't break the proposal to combine VDEV CREATE & LOCK. We end up
make VMM do nothing about Secure at VM boot, just normal shared passthrough.
VMM does VDEV create & LOCK in a batch when guest asks for bind (or lock
or connect, or whatever verb).

I think if any device specific thing must be done *between* VDEV CREATE
and LOCK, then they must be separated. But I haven't found yet.

Thanks,
Yilun

> 
> I will look up the previous discussions to better understand the

---

## [121] Alexey Kardashevskiy — 2025-03-04
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 28/2/25 13:26, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]

Unlikely though.

>>> Can you say whether this problem is going to escape your test bench into
>>> something mainline Linux needs to worry about?

True.

> It would be great if Linux could just say "the maximum number of
> potential Stream IDs is 255 (instead of 256). All TSM implementations

Better if the PCIe spec said that but yeah, this would do.

> Otherwise, at pci_ide_stream_setup() time I expect that the core would
> need to do something gross like check the incoming Stream ID and walk

This is what PCIe spec suggests doing now imho.


>>>> And then what are we doing to do when we start adding link streams? I
>>>> suggest decoupling pci_ide::stream_id from stream_id in sel_ide_offset()

Link IDE or any IDE? I know very little about CXL but some of those 
device types are not just simple fast memory but also do read/write 
from/to that memory so they cannot rely on CPU memory encryption and IDE 
makes sense for those (especially Link IDE as there are no bridges, or 
are there?). Thanks,


>>> We can always cross that sophistication bridge later.
>>

---

## [122] Dan Williams — 2025-03-03
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
[..]
> > Otherwise, at pci_ide_stream_setup() time I expect that the core would
> > need to do something gross like check the incoming Stream ID and walk

Ok, I am about to send out v2, let's follow on to that with an
implementation that simply sets all idle stream indexes to Stream ID
255. Then, catch cases where the low-level TSM driver tries to use ID
255. This is on the assumption that most implementations will allocate
starting from zero.

> >>>> And then what are we doing to do when we start adding link streams? I
> >>>> suggest decoupling pci_ide::stream_id from stream_id in sel_ide_offset()

So there are 2 use cases CXL.cache and CXL.mem, and of CXL.mem there is
general memory expansion and accelerator memory. Most of the devices in
the market and the sole focus of the CXL TSP (TEE Security Protocol)
specification is how to get CXL.mem from general memory expansion
devices (Type-3) into the TCB. From the spec:

    "This CXL security content scope focuses on features that are needed for
     confidential computing utilizing CXL Type 3 memory expander devices"

The TSP definition specifies that CXL.mem memory is brought into the TCB
by pre-OS software.

It goes on to say, "Transport security is optional for TSP", i.e. IDE is
optional. If you have initiator based memory encryption then you do not
also need encryption on the transport.

So, IDE is optional and any optional IDE establishment will be by pre-OS
software. There is nothing I can see from CXL-land threatening to make
the Linux IDE implementation care about Link IDE.

---

## [123] Alexey Kardashevskiy — 2025-03-04
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

On 4/3/25 11:57, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]


(self educating now)
So CXL.io is not a thing, or not going to support TSP?
Wiki mentions IO registers and DMA, not relevant here why? Thanks,


> 
>      "This CXL security content scope focuses on features that are needed for

---

## [124] Dan Williams — 2025-03-04
*Subject: Re: [PATCH 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
[..]
> (self educating now)
> So CXL.io is not a thing, or not going to support TSP?

CXL.io is outside of TSP.

CXL.io IDE is a nearly identical programming model to PCIe IDE (some
edge constraints are different). So unless and until there is a solid
use case to cause the kernel to consider PCIe Link Stream IDE, then
CXL.io IDE can also live in a "Selective IDE Stream only, for now"
world.

---

## [125] Alexey Kardashevskiy — 2025-03-07
*Subject: Re: [PATCH 05/11] PCI/TSM: Authenticate devices via platform TSM*

On 28/2/25 20:48, Aneesh Kumar K.V wrote:
> Xu Yilun <yilun.xu@linux.intel.com> writes:
> 


Linux will break it (or/and my device are buggy?), I have this in my stash:

https://github.com/aik/linux/commit/805d6763d349be173a93a4411912c4763ab44c60
"RFC: PCI: Avoid needless touching of Command register"


> I will look up the previous discussions to better understand the
> rationale behind combining vdev_create and lock.

It is the opposite, there is no obvious reason to separate these so we 
are trying to make things simpler for now.


> [1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp12.zip

ah this is the spec. "Realm Management Monitor" is not very obvious 
name when searching for TDISP (but I did not try hard :) ) Thanks,


> 
> -aneesh

---
