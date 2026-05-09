---
title: 'configfs-tsm-report: TCB Stability'
date: 2024-09-12
last_reply: 2024-10-07
message_count: 15
participants: ['Dan Williams', 'Kirill A. Shutemov', 'Alexander Graf', 'Dave Hansen', 'Dionna Amalie Glaze']
---

## [1] Dan Williams — 2024-09-12

As detailed in patch4, the TDX Module update capability has raised the
question  "what is the kernel's responsibility for mitigating 'surprise'
updates to a confidential VM's launch attestation?".

The approach taken in this patch set is to move it from an implicit
policy of the platform technology and hosting provider to an explicit
policy selected by the confidential VM kernel. Specifically, add
enumeration and choice so that the problem can be discussed in terms of
a TCB stability policy.

See patch4 for more details. Patches 1-3 are preparatory work for
building new guest-side "tsm" functionality.

This is untested for now, the initial focus for review is arriving at a
cross-vendor consensus view of the "surprise update" problem. Then
follow-up with finalizing the low-level details.

Note this is v6.13 material at the earliest, i.e. not for the imminent
merge window.

---

Dan Williams (4):
      configfs-tsm: Namespace TSM report symbols
      coco/guest: Move shared guest CC infrastructure to drivers/virt/coco/guest/
      x86/tdx: Introduce guest global metadata retrieval infrastructure
      configfs-tsm-report: Introduce TCB stability enumeration and watchdog


 Documentation/ABI/testing/configfs-tsm-report |   41 +++++++++
 MAINTAINERS                                   |    4 -
 arch/x86/coco/tdx/tdx.c                       |   39 ++++++++
 arch/x86/include/asm/shared/tdx.h             |    9 ++
 drivers/virt/coco/Kconfig                     |    6 -
 drivers/virt/coco/Makefile                    |    2 
 drivers/virt/coco/guest/Kconfig               |   72 ++++++++++++++++
 drivers/virt/coco/guest/Makefile              |    4 +
 drivers/virt/coco/guest/report.c              |  115 ++++++++++++++++++++++---
 drivers/virt/coco/guest/watchdog.c            |   59 +++++++++++++
 drivers/virt/coco/guest/watchdog.h            |   40 +++++++++
 drivers/virt/coco/sev-guest/sev-guest.c       |   12 +--
 drivers/virt/coco/tdx-guest/tdx-guest.c       |   15 ++-
 include/linux/tsm.h                           |   29 ++++--
 14 files changed, 403 insertions(+), 44 deletions(-)
 rename Documentation/ABI/testing/{configfs-tsm => configfs-tsm-report} (75%)
 create mode 100644 drivers/virt/coco/guest/Kconfig
 create mode 100644 drivers/virt/coco/guest/Makefile
 rename drivers/virt/coco/{tsm.c => guest/report.c} (79%)
 create mode 100644 drivers/virt/coco/guest/watchdog.c
 create mode 100644 drivers/virt/coco/guest/watchdog.h

base-commit: 5be63fc19fcaa4c236b307420483578a56986a37

---

## [2] Dan Williams — 2024-09-12
*Subject: [PATCH 1/4] configfs-tsm: Namespace TSM report symbols*

In preparation for new + common TSM (TEE Security Manager)
infrastructure, namespace the TSM report symbols in tsm.h with an
_REPORT suffix to differentiate them from other incoming tsm work.

Cc: Wu Hao <hao.wu@intel.com>
Cc: Yilun Xu <yilun.xu@intel.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/configfs-tsm-report |    0 
 MAINTAINERS                                   |    2 +-
 drivers/virt/coco/sev-guest/sev-guest.c       |   12 +++++----
 drivers/virt/coco/tdx-guest/tdx-guest.c       |    8 +++---
 drivers/virt/coco/tsm.c                       |   32 +++++++++++++------------
 include/linux/tsm.h                           |   22 +++++++++--------
 6 files changed, 38 insertions(+), 38 deletions(-)
 rename Documentation/ABI/testing/{configfs-tsm => configfs-tsm-report} (100%)

diff --git a/Documentation/ABI/testing/configfs-tsm b/Documentation/ABI/testing/configfs-tsm-report
similarity index 100%
rename from Documentation/ABI/testing/configfs-tsm
rename to Documentation/ABI/testing/configfs-tsm-report
diff --git a/MAINTAINERS b/MAINTAINERS
index 878dcd23b331..d2bf72c7ac55 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23263,7 +23263,7 @@ TRUSTED SECURITY MODULE (TSM) ATTESTATION REPORTS
 M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
-F:	Documentation/ABI/testing/configfs-tsm
+F:	Documentation/ABI/testing/configfs-tsm-report
 F:	drivers/virt/coco/tsm.c
 F:	include/linux/tsm.h
 
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 6fc7884ea0a1..2fc818c7ece0 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -794,7 +794,7 @@ struct snp_msg_cert_entry {
 static int sev_svsm_report_new(struct tsm_report *report, void *data)
 {
 	unsigned int rep_len, man_len, certs_len;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	struct svsm_attest_call ac = {};
 	unsigned int retry_count;
 	void *rep, *man, *certs;
@@ -931,7 +931,7 @@ static int sev_svsm_report_new(struct tsm_report *report, void *data)
 static int sev_report_new(struct tsm_report *report, void *data)
 {
 	struct snp_msg_cert_entry *cert_table;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	struct snp_guest_dev *snp_dev = data;
 	struct snp_msg_report_resp_hdr hdr;
 	const u32 report_size = SZ_4K;
@@ -1068,7 +1068,7 @@ static bool sev_report_bin_attr_visible(int n)
 	return false;
 }
 
-static struct tsm_ops sev_tsm_ops = {
+static struct tsm_report_ops sev_tsm_report_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = sev_report_new,
 	.report_attr_visible = sev_report_attr_visible,
@@ -1077,7 +1077,7 @@ static struct tsm_ops sev_tsm_ops = {
 
 static void unregister_sev_tsm(void *data)
 {
-	tsm_unregister(&sev_tsm_ops);
+	tsm_report_unregister(&sev_tsm_report_ops);
 }
 
 static int __init sev_guest_probe(struct platform_device *pdev)
@@ -1158,9 +1158,9 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	snp_dev->input.data_gpa = __pa(snp_dev->certs_data);
 
 	/* Set the privlevel_floor attribute based on the vmpck_id */
-	sev_tsm_ops.privlevel_floor = vmpck_id;
+	sev_tsm_report_ops.privlevel_floor = vmpck_id;
 
-	ret = tsm_register(&sev_tsm_ops, snp_dev);
+	ret = tsm_report_register(&sev_tsm_report_ops, snp_dev);
 	if (ret)
 		goto e_free_cert_data;
 
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 2acba56ad42e..a74b9a509658 100644
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
 
@@ -300,7 +300,7 @@ static const struct x86_cpu_id tdx_guest_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_guest_ids);
 
-static const struct tsm_ops tdx_tsm_ops = {
+static const struct tsm_report_ops tdx_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = tdx_report_new,
 	.report_attr_visible = tdx_report_attr_visible,
@@ -325,7 +325,7 @@ static int __init tdx_guest_init(void)
 		goto free_misc;
 	}
 
-	ret = tsm_register(&tdx_tsm_ops, NULL);
+	ret = tsm_report_register(&tdx_tsm_ops, NULL);
 	if (ret)
 		goto free_quote;
 
@@ -342,7 +342,7 @@ module_init(tdx_guest_init);
 
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

## [3] Dan Williams — 2024-09-12
*Subject: [PATCH 2/4] coco/guest: Move shared guest CC infrastructure to
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
index d2bf72c7ac55..837d7e6323f0 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23264,7 +23264,7 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm-report
-F:	drivers/virt/coco/tsm.c
+F:	drivers/virt/coco/guest/
 F:	include/linux/tsm.h
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 87d142c1f932..7c41e0abd423 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -3,12 +3,10 @@
 # Confidential computing related collateral
 #
 
-config TSM_REPORTS
-	select CONFIGFS_FS
-	tristate
-
 source "drivers/virt/coco/efi_secret/Kconfig"
 
 source "drivers/virt/coco/sev-guest/Kconfig"
 
 source "drivers/virt/coco/tdx-guest/Kconfig"
+
+source "drivers/virt/coco/guest/Kconfig"
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 18c1aba5edb7..621111811a76 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -2,7 +2,7 @@
 #
 # Confidential computing related collateral
 #
-obj-$(CONFIG_TSM_REPORTS)	+= tsm.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
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

## [4] Dan Williams — 2024-09-12
*Subject: [PATCH 3/4] x86/tdx: Introduce guest global metadata retrieval
 infrastructure*

Similar to the host side [1], build some macro helpers for retrieving
global metadata fields.

This infrastructure is overkill if the guest only ends up consuming a
few fields of metadata. Some of the overhead reduced later by
refactoring the TDH_SYS_RD (host side) infrastructure to optionally
support TDG_SYS_RD (guest side) as an alternate low-level transport.

If this moves forward, expect that it is rebased on the host side
metadata patches to share infrastructure.

Link: http://lore.kernel.org/cover.1724741926.git.kai.huang@intel.com [1]
Cc: Kai Huang <kai.huang@intel.com>
Cc: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: x86@kernel.org
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/coco/tdx/tdx.c           |   39 +++++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h |    9 +++++++++
 2 files changed, 48 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..270da751eb24 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -922,6 +922,42 @@ static void tdx_kexec_finish(void)
 	}
 }
 
+static void tdg_sys_rd(u64 field_id, u64 *data)
+{
+	struct tdx_module_args args = {};
+
+	/*
+	 * TDG.SYS.RD -- reads one global metadata field
+	 *  - RDX (in): the field to read
+	 *  - R8 (out): the field data
+	 */
+	args.rdx = field_id;
+	tdcall(TDG_SYS_RD, &args);
+	*data = args.r8;
+}
+
+#define build_tdg_sys_rd(size)                                          \
+	static __init void tdg_sys_rd##size(u64 field_id, u##size *val) \
+	{                                                               \
+		u64 tmp;                                                \
+									\
+		tdg_sys_rd(field_id, &tmp);                             \
+		*val = tmp;                                             \
+	}
+
+build_tdg_sys_rd(64);
+build_tdg_sys_rd(8);
+
+/* TODO: move these to a shared host/guest location */
+#define MD_FIELD_ID_NUM_TDX_FEATURES 0x0A00000000000001ULL
+#define MD_FIELD_ID_TDX_FEATURES0 0x0A00000300000008ULL
+
+struct tdg_sys_info_features tdg_sys_info_features __ro_after_init;
+EXPORT_SYMBOL(tdg_sys_info_features);
+
+#define READ_SYS_INFO_FEATURES(_id, _member, _size) \
+	tdg_sys_rd##_size(MD_FIELD_ID_##_id, &tdg_sys_info_features._member)
+
 void __init tdx_early_init(void)
 {
 	struct tdx_module_args args = {
@@ -995,5 +1031,8 @@ void __init tdx_early_init(void)
 	 */
 	x86_cpuinit.parallel_bringup = false;
 
+	READ_SYS_INFO_FEATURES(NUM_TDX_FEATURES, num_tdx_features, 8);
+	READ_SYS_INFO_FEATURES(TDX_FEATURES0, features0, 64);
+
 	pr_info("Guest detected\n");
 }
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index fdfd41511b02..0b7e408104d3 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -17,6 +17,7 @@
 #define TDG_MR_REPORT			4
 #define TDG_MEM_PAGE_ACCEPT		6
 #define TDG_VM_WR			8
+#define TDG_SYS_RD			11
 
 /* TDCS fields. To be used by TDG.VM.WR and TDG.VM.RD module calls */
 #define TDCS_NOTIFY_ENABLES		0x9100000000000010
@@ -121,6 +122,14 @@ void __noreturn __tdx_hypercall_failed(void);
 
 bool tdx_accept_memory(phys_addr_t start, phys_addr_t end);
 
+extern struct tdg_sys_info_features {
+	u8 num_tdx_features;
+	u64 features0;
+} tdg_sys_info_features;
+
+#define TDX_FEATURE_TD_PRESERVING_BIT 1
+#define TDX_FEATURE_TD_PRESERVING BIT(TDX_FEATURE_TD_PRESERVING_BIT)
+
 /*
  * The TDG.VP.VMCALL-Instruction-execution sub-functions are defined
  * independently from but are currently matched 1:1 with VMX EXIT_REASONs.

---

## [5] Dan Williams — 2024-09-12
*Subject: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

One of the points of contention for enabling runtime updates of the TDX
Module has been what to do about the fact that it results in
confidential VMs seeing surprise updates to their TCB. The general
concern is that there is a non-zero confidentiality regression risk for
updating measured TCB components. Not only the TDX Module, but
microcode, SEV-SNP PSP firmware, RISCV and ARM equivalents etc. The
degree to which the TCB is or is not compromised by an unexpected update
is unknowable by the kernel, but it should at least try to be
transparent about what it knows about TCB stability.

Ironically, microcode and PSP firmware update flows predated this
launch-state attestation era of confidential computing and resulted in a
"permissive" by default policy. So while TDX Module update is a new
concern that triggers fresh questions, the resolution of that question
reads on more than just the TDX Module.

The proposal is: update the cross-vendor TSM Reports mechanism to have a
unified response to this question in the form of a "TCB Stability"
build-time configuration stance.

Likely hosting providers expect tenants to be permissive of updates at
all times in which case they can just mandate
CONFIG_TSM_REPORTS_TCB_STABILITY_PERMISSIVE in tenant Linux kernel
configs, and no need to read the rest of this changelog.

Outside of that case though the kernel has a responsibility to be
transparent about what it knows about the stability of launch
attestation reports, and it has the ability to supplement the lack of
proactive notification of pending updates with an after-the-fact
watchdog.

The expectation is that userspace that depends on remote attestation
(the common ecosystem expectation for confidential computing
deployments) already has everything it needs to periodically revalidate
the TCB. However, similar to how the typical watchdog backstops
unexpected lockup scenarios to limit downtime, the
CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED policy backstops unexpected
remote attestation connectivity losses in a common way.

Lastly, CONFIG_TSM_REPORTS_TCB_STABILITY_STRICT, for completeness,
allows the kernel to be toxic to even the possibility of runtime
updates. The inclusion of this option is mainly for the communication
value it provides to later survey how many Linux distributions, cloud
hosting providers and confidential computing host platforms offer
compatibility with a "no runtime TCB component update" policy. The
maintenance burden of this option is low compared to that communication
value.

The enforcement of "Relaxed" or "Strict" violations is expected to adopt
the kernel's "panic_on_warn" policy. I.e. a violation is only a WARN()
in either configuration.

For now, only tdx-guest is updated to convey when runtime updates are
disbaled. sev-guest always asserts that runtime updates are enabled.

Cc: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Cc: "Borislav Petkov (AMD)" <bp@alien8.de>
Cc: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Cc: Thomas Gleixner <tglx@linutronix.de>
Cc: Michael Roth <michael.roth@amd.com>
Cc: x86@kernel.org
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/configfs-tsm-report |   41 ++++++++++++
 drivers/virt/coco/guest/Kconfig               |   65 +++++++++++++++++++
 drivers/virt/coco/guest/Makefile              |    1 
 drivers/virt/coco/guest/report.c              |   85 +++++++++++++++++++++++++
 drivers/virt/coco/guest/watchdog.c            |   59 +++++++++++++++++
 drivers/virt/coco/guest/watchdog.h            |   40 ++++++++++++
 drivers/virt/coco/sev-guest/sev-guest.c       |    2 -
 drivers/virt/coco/tdx-guest/tdx-guest.c       |    9 ++-
 include/linux/tsm.h                           |    9 ++-
 9 files changed, 307 insertions(+), 4 deletions(-)
 create mode 100644 drivers/virt/coco/guest/watchdog.c
 create mode 100644 drivers/virt/coco/guest/watchdog.h

diff --git a/Documentation/ABI/testing/configfs-tsm-report b/Documentation/ABI/testing/configfs-tsm-report
index 534408bc1408..28c89afc265b 100644
--- a/Documentation/ABI/testing/configfs-tsm-report
+++ b/Documentation/ABI/testing/configfs-tsm-report
@@ -143,3 +143,44 @@ Description:
 
 		See 'service_provider' for information on the format of the
 		service manifest version.
+
+What:		/sys/kernel/config/tsm/report/$name/tcb_static
+Date:		September, 2024
+KernelVersion:	v6.13
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) Reports 1 if low level TCB component versions are subject to
+		change at runtime, reports 0 otherwise.  Note that TSM provider
+		implementations may draw the line on what can be updated at
+		runtime differently. For example, only small security fixes are
+		suitable for runtime update while major feature versions require
+		VM shutdown. Consult with the platform provider on what component
+		updates are included in runtime updates.
+
+What:		/sys/kernel/config/tsm/report/$name/watchdog
+Date:		September, 2024
+KernelVersion:	v6.13
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(WO) Attribute is visible if the kernel is built with
+		CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED=y and @tcb_static reports
+		"0". Userspace is required to write "1" to this file at least once
+		every @watchdog_timeout period to assert that the TCB has not
+		changed and that userspace connectivity with remote attestation
+		services is still alive. The watchdog starts upon the first read
+		from @outblob.
+
+What:		/sys/kernel/config/tsm/report/$name/watchdog_timeout
+Date:		September, 2024
+KernelVersion:	v6.13
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) Attribute is visible if the kernel is built with
+		CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED=y and @tcb_static reports
+		"0". It reports the current timeout value in seconds when read.
+		Writing an integer value establishes the next timeout for the
+		period initiated with a write to @watchdog, or retrieval of a new
+		report from @outblob. A write of "0" disables the watchdog. Also
+		consider building the kernel with
+		CONFIG_TSM_REPORTS_TCB_STABILITY_PERMISSIVE=y if there is no
+		intent to use the watchdog.
diff --git a/drivers/virt/coco/guest/Kconfig b/drivers/virt/coco/guest/Kconfig
index ed9bafbdd854..d59cb237b1e0 100644
--- a/drivers/virt/coco/guest/Kconfig
+++ b/drivers/virt/coco/guest/Kconfig
@@ -5,3 +5,68 @@
 config TSM_REPORTS
 	select CONFIGFS_FS
 	tristate
+
+choice
+	prompt "TSM Reports: TCB Stability Policy"
+	depends on TSM_REPORTS
+	help
+	  Confidential Computing Launch attestation includes the version of
+	  components like the TSM firmware and CPU microcode.
+
+	  While updates to those components are designed to maintain or improve
+	  confidentiality and integrity, there is a non-zero chance for
+	  regressions. Select one of "Strict", "Relaxed", or "Permissive" to
+	  determine the kernel's default policy with respect to runtime updates.
+	  Select "Relaxed" if unsure, the historical default is "Permissive",
+	  but otherwise, consult with your VM host provider and/or attestation
+	  service provider for the recommended policy.
+
+config TSM_REPORTS_TCB_STABILITY_PERMISSIVE
+	bool "Permissive"
+	help
+	  If the VM running this kernel trusts or is contractually obligated to
+	  accept runtime updates, set this option. It assumes that the
+	  regression risk of updates is lower than the risk of continuing with
+	  an older TCB, or the hosting provider has an operational deployment
+	  requirement to mandate runtime updates. Set this option to disable
+	  kernel diligence around asserting that the TCB is not being mutated in
+	  unexpected ways.
+
+config TSM_REPORTS_TCB_STABILITY_RELAXED
+	bool "Relaxed"
+	help
+	  There are legitimate reasons for runtime updates of TCB components.
+	  The kernel is not in a position to pre-approve exposure to updated
+	  TCBs, or to parse a myriad of vendor specific report formats across
+	  platforms. It is, however, in a position to trigger self protection of
+	  confidentiality and integrity when TCB update surprises occur and go
+	  unhandled. This option requires userspace to positively assert that
+	  each new attestation report it receives has not modified the TCB in a
+	  way that userspace does not expect. It is a watchdog to set a kernel
+	  enforced maximum amount of time that the VM is exposed to new TCB
+	  components without validation.  See "watchdog" in
+	  Documentation/ABI/testing/configfs-tsm-report.
+
+config TSM_REPORTS_TCB_STABILITY_STRICT
+	bool "Strict"
+	help
+	  For maximum paranoia, trigger a warning immediately upon userspace
+	  retrieving an attestation report that is subject to potential surprise
+	  updates of any of the measured components, or if the kernel cannot
+	  determine that such updates are disabled. The system "panic_on_warn"
+	  policy can be deployed to escalate this notification to terminating
+	  the kernel to prevent exposure to updated TCBs that may not yet be
+	  approved by a verifier. Contact the VMM host provider to determine if
+	  disabling exposure to dynamic TCBs is possible.
+endchoice
+
+config TSM_REPORTS_WATCHDOG_TIMEOUT
+	int "TSM Reports: TCB Stability Watchdog Timeout"
+	depends on TSM_REPORTS_TCB_STABILITY_RELAXED
+	range 1 300
+	default 60
+	help
+	  Set a timeout, in seconds, for userspace to assert that newly
+	  retrieved attestation reports have not modified a measured component
+	  version outside of expectations, and require revalidation of the TCB
+	  on this period.
diff --git a/drivers/virt/coco/guest/Makefile b/drivers/virt/coco/guest/Makefile
index b3b217af77cf..341009357400 100644
--- a/drivers/virt/coco/guest/Makefile
+++ b/drivers/virt/coco/guest/Makefile
@@ -1,3 +1,4 @@
 # SPDX-License-Identifier: GPL-2.0
 obj-$(CONFIG_TSM_REPORTS)	+= tsm_report.o
 tsm_report-y := report.o
+tsm_report-$(CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED) += watchdog.o
diff --git a/drivers/virt/coco/guest/report.c b/drivers/virt/coco/guest/report.c
index bcb515b50c68..6e33804702e7 100644
--- a/drivers/virt/coco/guest/report.c
+++ b/drivers/virt/coco/guest/report.c
@@ -12,8 +12,11 @@
 #include <linux/cleanup.h>
 #include <linux/configfs.h>
 
+#include "watchdog.h"
+
 static struct tsm_provider {
 	const struct tsm_report_ops *ops;
+	unsigned long flags;
 	void *data;
 } provider;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -42,6 +45,7 @@ struct tsm_report_state {
 	unsigned long write_generation;
 	unsigned long read_generation;
 	struct config_item cfg;
+	struct tcb_stability_state tcb;
 };
 
 enum tsm_data_select {
@@ -221,6 +225,66 @@ static ssize_t tsm_report_provider_show(struct config_item *cfg, char *buf)
 }
 CONFIGFS_ATTR_RO(tsm_report_, provider);
 
+static ssize_t tsm_report_tcb_static_show(struct config_item *cfg, char *buf)
+{
+	guard(rwsem_read)(&tsm_rwsem);
+	return sysfs_emit(buf, "%d\n",
+			  !!(provider.flags & TSM_REPORT_TCB_STATIC));
+}
+CONFIGFS_ATTR_RO(tsm_report_, tcb_static);
+
+static ssize_t tsm_report_watchdog_timeout_store(struct config_item *cfg,
+						 const char *buf, size_t len)
+{
+	struct tsm_report *report = to_tsm_report(cfg);
+	struct tsm_report_state *state = to_state(report);
+	int rc;
+
+	rc = kstrtoul(buf, 0, &state->tcb.tmo);
+	if (rc)
+		return rc;
+	return len;
+}
+
+static ssize_t tsm_report_watchdog_timeout_show(struct config_item *cfg,
+						char *buf)
+{
+	struct tsm_report *report = to_tsm_report(cfg);
+	struct tsm_report_state *state = to_state(report);
+
+	return sysfs_emit(buf, "%ld\n", state->tcb.tmo);
+}
+CONFIGFS_ATTR(tsm_report_, watchdog_timeout);
+
+static ssize_t tsm_report_watchdog_store(struct config_item *cfg,
+					 const char *buf, size_t len)
+{
+	struct tsm_report *report = to_tsm_report(cfg);
+	struct tsm_report_state *state = to_state(report);
+
+	return __tsm_report_watchdog_store(&state->tcb, buf, len);
+}
+CONFIGFS_ATTR_WO(tsm_report_, watchdog);
+
+static void check_tcb_stability(struct tsm_report_state *state)
+{
+	if (provider.flags & TSM_REPORT_TCB_STATIC || state->tcb.report)
+		return;
+
+	if (IS_ENABLED(CONFIG_TSM_REPORTS_TCB_STABILITY_PERMISSIVE)) {
+		pr_info("%s: TCB is subject to dynamic low level component updates\n",
+			state->tcb.name);
+		state->tcb.report = true;
+	} else if (IS_ENABLED(CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED))
+		tcb_watchdog_trigger(&state->tcb);
+	else if (IS_ENABLED(CONFIG_TSM_REPORTS_TCB_STABILITY_STRICT)) {
+		WARN(1,
+		     pr_fmt("%s: TCB is subject to dynamic low level component updates\n"),
+		     state->tcb.name);
+		state->tcb.report = true;
+	}
+}
+
 static ssize_t __read_report(struct tsm_report *report, void *buf, size_t count,
 			     enum tsm_data_select select)
 {
@@ -303,6 +367,7 @@ static ssize_t tsm_report_read(struct tsm_report *report, void *buf,
 	if (rc < 0)
 		return rc;
 	state->read_generation = state->write_generation;
+	check_tcb_stability(state);
 out:
 	return __read_report(report, buf, count, select);
 }
@@ -342,6 +407,9 @@ static struct configfs_attribute *tsm_report_attrs[] = {
 	[TSM_REPORT_SERVICE_PROVIDER] = &tsm_report_attr_service_provider,
 	[TSM_REPORT_SERVICE_GUID] = &tsm_report_attr_service_guid,
 	[TSM_REPORT_SERVICE_MANIFEST_VER] = &tsm_report_attr_service_manifest_version,
+	[TSM_REPORT_TCB_STATIC] = &tsm_report_attr_tcb_static,
+	[TSM_REPORT_TCB_WATCHDOG] = &tsm_report_attr_watchdog,
+	[TSM_REPORT_TCB_WATCHDOG_TIMEOUT] = &tsm_report_attr_watchdog_timeout,
 	NULL,
 };
 
@@ -358,6 +426,7 @@ static void tsm_report_item_release(struct config_item *cfg)
 	struct tsm_report *report = to_tsm_report(cfg);
 	struct tsm_report_state *state = to_state(report);
 
+	tcb_watchdog_shutdown(&state->tcb);
 	kvfree(report->manifestblob);
 	kvfree(report->auxblob);
 	kvfree(report->outblob);
@@ -376,6 +445,16 @@ static bool tsm_report_is_visible(struct config_item *item,
 	if (!provider.ops)
 		return false;
 
+	if (attr == &tsm_report_attr_tcb_static)
+		return true;
+
+	if (attr == &tsm_report_attr_watchdog ||
+	    attr == &tsm_report_attr_watchdog_timeout) {
+		if (IS_ENABLED(CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED))
+			return true;
+		return false;
+	}
+
 	if (!provider.ops->report_attr_visible)
 		return true;
 
@@ -421,6 +500,7 @@ static struct config_item *tsm_report_make_item(struct config_group *group,
 	if (!state)
 		return ERR_PTR(-ENOMEM);
 
+	tcb_watchdog_init(&state->tcb, name);
 	config_item_init_type_name(&state->cfg, name, &tsm_report_type);
 	return &state->cfg;
 }
@@ -448,7 +528,8 @@ static struct configfs_subsystem tsm_configfs = {
 	.su_mutex = __MUTEX_INITIALIZER(tsm_configfs.su_mutex),
 };
 
-int tsm_report_register(const struct tsm_report_ops *ops, void *priv)
+int tsm_report_register(const struct tsm_report_ops *ops, unsigned long flags,
+			void *priv)
 {
 	const struct tsm_report_ops *conflict;
 
@@ -461,6 +542,7 @@ int tsm_report_register(const struct tsm_report_ops *ops, void *priv)
 
 	provider.ops = ops;
 	provider.data = priv;
+	provider.flags = flags;
 	return 0;
 }
 EXPORT_SYMBOL_GPL(tsm_report_register);
@@ -472,6 +554,7 @@ int tsm_report_unregister(const struct tsm_report_ops *ops)
 		return -EBUSY;
 	provider.ops = NULL;
 	provider.data = NULL;
+	provider.flags = 0;
 	return 0;
 }
 EXPORT_SYMBOL_GPL(tsm_report_unregister);
diff --git a/drivers/virt/coco/guest/watchdog.c b/drivers/virt/coco/guest/watchdog.c
new file mode 100644
index 000000000000..58577a286a13
--- /dev/null
+++ b/drivers/virt/coco/guest/watchdog.c
@@ -0,0 +1,59 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <linux/workqueue.h>
+#include "watchdog.h"
+
+/*
+ * a new report has been retrieved, require userspace to assert that
+ * connectivity with and approval from remote attestation is still
+ * intact, and remains intact on an ongoing basis
+ */
+void tcb_watchdog_trigger(struct tcb_stability_state *tcb)
+{
+	unsigned long tmo = READ_ONCE(tcb->tmo);
+
+	if (!tmo)
+		return;
+
+	schedule_delayed_work(&tcb->watchdog_work, msecs_to_jiffies(tmo * 1000));
+}
+
+static void tcb_watchdog_work(struct work_struct *work)
+{
+	struct tcb_stability_state *tcb = container_of(
+		work, struct tcb_stability_state, watchdog_work.work);
+
+	WARN(1, pr_fmt("%s: Timeout awaiting TCB stability validation\n"), tcb->name);
+	tcb->report = true;
+}
+
+void tcb_watchdog_init(struct tcb_stability_state *tcb, const char *name)
+{
+	INIT_DELAYED_WORK(&tcb->watchdog_work, tcb_watchdog_work);
+	tcb->tmo = CONFIG_TSM_REPORTS_WATCHDOG_TIMEOUT;
+	tcb->name = name;
+}
+
+ssize_t __tsm_report_watchdog_store(struct tcb_stability_state *tcb, const char *buf,
+				    size_t len)
+{
+	unsigned long tmo = READ_ONCE(tcb->tmo);
+	bool cancel;
+	int rc;
+
+	rc = kstrtobool(buf, &cancel);
+	if (rc)
+		return rc;
+	if (!cancel)
+		return len;
+	if (!tmo) {
+		cancel_delayed_work(&tcb->watchdog_work);
+		return len;
+	}
+
+	schedule_delayed_work(&tcb->watchdog_work, msecs_to_jiffies(tmo * 1000));
+	return len;
+}
diff --git a/drivers/virt/coco/guest/watchdog.h b/drivers/virt/coco/guest/watchdog.h
new file mode 100644
index 000000000000..c29a0d8e3833
--- /dev/null
+++ b/drivers/virt/coco/guest/watchdog.h
@@ -0,0 +1,40 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef __TCB_WATCHDOG_H
+#define __TCB_WATCHDOG_H
+#include <linux/workqueue.h>
+
+struct tcb_stability_state {
+	const char *name;
+	bool report;
+	unsigned long tmo;
+	struct delayed_work watchdog_work;
+};
+
+#ifdef CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED
+void tcb_watchdog_trigger(struct tcb_stability_state *tcb);
+ssize_t __tsm_report_watchdog_store(struct tcb_stability_state *tcb,
+				    const char *buf, size_t len);
+void tcb_watchdog_init(struct tcb_stability_state *tcb, const char *name);
+static inline void tcb_watchdog_shutdown(struct tcb_stability_state *tcb)
+{
+	cancel_delayed_work_sync(&tcb->watchdog_work);
+}
+#else
+static inline void tcb_watchdog_init(struct tcb_stability_state *tcb,
+				     const char *name)
+{
+}
+static inline void tcb_watchdog_shutdown(struct tcb_stability_state *tcb)
+{
+}
+static inline void tcb_watchdog_trigger(struct tcb_stability_state *tcb)
+{
+}
+static inline ssize_t
+__tsm_report_watchdog_store(struct tcb_stability_state *tcb, const char *buf,
+			    size_t len)
+{
+	return -ENXIO;
+}
+#endif /* CONFIG_TSM_REPORTS_TCB_STABILITY_RELAXED */
+#endif /* __TCB_WATCHDOG_H */
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 2fc818c7ece0..89b160ae719d 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -1160,7 +1160,7 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	/* Set the privlevel_floor attribute based on the vmpck_id */
 	sev_tsm_report_ops.privlevel_floor = vmpck_id;
 
-	ret = tsm_report_register(&sev_tsm_report_ops, snp_dev);
+	ret = tsm_report_register(&sev_tsm_report_ops, 0, snp_dev);
 	if (ret)
 		goto e_free_cert_data;
 
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index a74b9a509658..122a10a8dd2b 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -309,6 +309,7 @@ static const struct tsm_report_ops tdx_tsm_ops = {
 
 static int __init tdx_guest_init(void)
 {
+	unsigned long flags;
 	int ret;
 
 	if (!x86_match_cpu(tdx_guest_ids))
@@ -325,7 +326,13 @@ static int __init tdx_guest_init(void)
 		goto free_misc;
 	}
 
-	ret = tsm_report_register(&tdx_tsm_ops, NULL);
+	flags = TSM_REPORT_TCB_STATIC;
+	if (tdg_sys_info_features.num_tdx_features >
+		    TDX_FEATURE_TD_PRESERVING_BIT &&
+	    tdg_sys_info_features.features0 & TDX_FEATURE_TD_PRESERVING)
+		flags = 0;
+
+	ret = tsm_report_register(&tdx_tsm_ops, flags, NULL);
 	if (ret)
 		goto free_quote;
 
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 431054810dca..e53c237620f2 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -62,6 +62,8 @@ struct tsm_report {
  * @TSM_REPORT_SERVICE_PROVIDER: index of the service provider identifier attribute
  * @TSM_REPORT_SERVICE_GUID: index of the service GUID attribute
  * @TSM_REPORT_SERVICE_MANIFEST_VER: index of the service manifest version attribute
+ * @TSM_REPORT_TCB_WATCHDOG: TCB stability monitor
+ * @TSM_REPORT_TCB_WATCHDOG_TIMEOUT: TCB stability timeout value (seconds)
  */
 enum tsm_attr_index {
 	TSM_REPORT_GENERATION,
@@ -71,6 +73,8 @@ enum tsm_attr_index {
 	TSM_REPORT_SERVICE_PROVIDER,
 	TSM_REPORT_SERVICE_GUID,
 	TSM_REPORT_SERVICE_MANIFEST_VER,
+	TSM_REPORT_TCB_WATCHDOG,
+	TSM_REPORT_TCB_WATCHDOG_TIMEOUT,
 };
 
 /**
@@ -107,6 +111,9 @@ struct tsm_report_ops {
 	bool (*report_bin_attr_visible)(int n);
 };
 
-int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
+#define TSM_REPORT_TCB_STATIC BIT(0)
+
+int tsm_report_register(const struct tsm_report_ops *ops, unsigned long flags,
+			void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
 #endif /* __TSM_H */

---

## [6] Kirill A. Shutemov — 2024-09-16
*Subject: Re: [PATCH 3/4] x86/tdx: Introduce guest global metadata retrieval
 infrastructure*

On Thu, Sep 12, 2024 at 05:26:18PM -0700, Dan Williams wrote:
> Similar to the host side [1], build some macro helpers for retrieving
> global metadata fields.

This patchset already introduces helper for TDG_VM_RD. The same can be
done for TDG_SYS_RD.

https://lore.kernel.org/all/20240828093505.2359947-1-kirill.shutemov@linux.intel.com/

---

## [7] Kirill A. Shutemov — 2024-09-16
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

On Thu, Sep 12, 2024 at 05:26:26PM -0700, Dan Williams wrote:
> One of the points of contention for enabling runtime updates of the TDX
> Module has been what to do about the fact that it results in

I am not convinced it brings any value in TDX case.

Whether TDX module supports TD_PRESERVING depends on what TDX module it
is. And TDX module is already attested, so attestation server can just
fail attestation if it is not okay with it. It seems to be functionally
equivalent to what you are proposing.

---

## [8] Dan Williams — 2024-09-30
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

Kirill A. Shutemov wrote:
> On Thu, Sep 12, 2024 at 05:26:26PM -0700, Dan Williams wrote:
> > One of the points of contention for enabling runtime updates of the TDX

...and, do not forget, what the tenant is willing to accept. If a
sufficiently motivated tenant wanted a module that asserted no updates I
have little reason to doubt they could request to run with such a
module.

> And TDX module is already attested, so attestation server can just
> fail attestation if it is not okay with it. It seems to be functionally

I address this in the cover letter. There is a measure of value for
requiring the connectivity with the attestation server to remain in
effect. That is the value of watchdog's in general, the kernel can set a
ceiling for exposure to an unattested TCB.

The cost of this mechanism in terms of complexity is negligible when
considering that small (userspace can always do this on its own) value.

Recall that the motivation for this mechanism is to allow forward
progress on update enabling while mitigating the impact to
theoretical hyper-vigilant tenants, and to survey the prevalance of
hyper-vigilant tenants who may not make themselves known until this
technology is more baked and widely avaialable.

---

## [9] Dan Williams — 2024-10-01
*Subject: Re: [PATCH 3/4] x86/tdx: Introduce guest global metadata retrieval
 infrastructure*

Kirill A. Shutemov wrote:
> On Thu, Sep 12, 2024 at 05:26:18PM -0700, Dan Williams wrote:
> > Similar to the host side [1], build some macro helpers for retrieving

Shouldn't this be reworked to use the same metadata reading
infrastructure as Kai is introducing for the host side?

http://lore.kernel.org/1b14e28b-972e-4277-898f-8e2dcb77e144@intel.com

---

## [10] Alexander Graf — 2024-10-01
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

On 13.09.24 02:26, Dan Williams wrote:
> One of the points of contention for enabling runtime updates of the TDX
> Module has been what to do about the fact that it results in


IMHO this looks at the problem the wrong way around. The typical flow 
for firmware updates is:

1) Researchers find an issue
2) Intel fixes it, ideally in TDX Module. Releases TDX Module update.
3) Infrastructure providers update TDX Module to resolve issue
4) Embargo lifts

If an issue impacts your confidentiality promises according to your 
threat model, you are already affected by it after 1). You are able to 
assess whether that is the case after 4). This patch tells you about it 
during 3).

If your threat model really really considers hosting infrastructure as 
malicious, you did not gain any benefits from learning about 3). You 
know that something was patched. You do not know what. You do not know 
whether anyone malicious was already aware of the issue. If you were 
strict, you would need to consider all data past 1) in such a VM as 
compromised. Given SEV-SNP's patch track record, I would expect security 
relevant patches multiple times per year. If you are really paranoid 
enough to care, notifications at point 3 will not tell you anything. 
Instead, your conclusion would probably be "I could get compromised at 
any point in time, so let me not expose data in the first place" which 
means you can not run in the Cloud at all. In most risk assessments, 
customers will typically be ok with a temporary, limited risk between 1) 
and 3). And that means you want to optimize to shift 3) left as much as 
possible to fix security issues as quickly as possible.

Instead, what we do by creating FUD around the patching process is to 
create a false assumption with customers that "unpatched" == "secure" 
while it's the exact opposite. We also encourage a shift of 3) from left 
to right: If I only patch you after embargo lift, you can assess, so 
it's safer, right? Not really, because you prolong the time an 
environment is unpatched.

The crux of the problem is that - by definition - a VM can not 
autonomously determine step 1) because what really happens here is that 
the world around it changed. We need to ask the world. So if Intel is 
really concerned about the update flow and notifying customers that the 
environment they are running in is potentially insecure, Intel should 
provide an attestation mechanism to notify them as early as reasonable; 
probably around 3). That way, customers get the chance to learn first 
hand that they should be running on a newer revision of TDX Module code 
and should no longer trust the one with known vulnerabilities.

The in-VM logic suggested in this patch such as "I'll die if you patch 
my host" or "I tell my owner that you patched me, but my owner won't be 
able to tell anything from that info" is not going to help anyone for 
TDX Module security patching situations.

Instead, let's start the conversation from how Intel can provide a 
mechanism to customers to evaluate whether their system is fully 
patched, work towards closing the gap between 1) and 3) and then build 
whatever interfaces in Linux we need to enable customers to make use of 
the evaluation mechanism.


Thanks,

Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [11] Dan Williams — 2024-10-04
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

Alexander Graf wrote:
> On 13.09.24 02:26, Dan Williams wrote:
> > One of the points of contention for enabling runtime updates of the TDX

Lets set aside "malicious host", because as you allude, why cloud host
at all in that case? Instead lets focus on "theoretical paranoid tenant"
that wants to trust but verify the TCB in the presence of updates.

More below, but I readily admit that "theoretical tenant" already raises
the "no practical benefit" objection to the proposal.

> you did not gain any benefits from learning about 3). You 
> know that something was patched. You do not know what. You do not know 

I quote the above in its entirety because, "no lies detected". However,
reframe it in the perspective of paranoid  / vigilant tenant. It is
always going to be the case that a vigilant tenant can see updates
whether the kernel is polling for them or not. Also, it will almost
always be the case that the platform vendor release schedule for updates
will come at some inopportune time for the tenant, or that the CSP
update somehow races to the tenant before the notification from platform
vendor that a new update is available.

At the discovery of an issue impacting TCB1, that is potentially fixed
by TCB2, I think it is reasonable to support a tenant that wants to
pause TCB1 operations until a TCB2 audit is complete and then resume
operations. If that is reasonable then the question becomes how to
ensure periodic renewal in confidence of TCB1 and non-surprise update to
TCB2. A kernel watchdog protects against userspace hangs or exceptions
that block periodic renewal of TCB1, or otherwise confirms that an
update to TCB2 is expected and welcome.

---

## [12] Alexander Graf — 2024-10-07
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

Hi Dan,

On 04.10.24 23:36, Dan Williams wrote:
> Alexander Graf wrote:
>> On 13.09.24 02:26, Dan Williams wrote:


I can follow your rationale, but I don't see many (economically viable) 
alternatives to "trust newer TCB until audit is complete":

Let's assume a TCB refresh once per month. In the scenario you outline 
above, we need to assume that the audit of TCB-next only follows with a 
delay to the deployment of TCB-next. If that delay is 2 weeks (which is 
pretty fast for audits!), then you would be effectively offline for 2 
weeks every month: half of the time. I don't see how you could 
realistically put your workload into the cloud with such a model.

However, if you were to

   1) "blindly" trust Intel that any TCB is valid or
   2) Intel provides you with an attestation mechanism that includes 
pre-released TCBs or
   3) you can live with a swing period of "up to X weeks" where you 
don't know if you trusted a TCB yet, but you faithfully believe you do 
and only retrospectively consider systems compromised if your audit did 
not succeed within that time frame

then you can make things work without ever declaring the cloud option as 
non-viable.

I don't think a solution that says "Now I no longer trust my cloud 
infrastructure, so I stop running there" will work. The only conclusion 
you will reach from that is that you need to keep an in-house stack of 
the same size as today as fallback net, but still pay cloud costs when 
you run there. And that in turn means you're only increasing costs. We 
need to provide a way to always make the cloud solution a viable target 
to run in to be economically attractive to customers.

Whatever you're playing through mentally, play it through with monthly 
TCB updates to give them a reality check for viability. Customers may be 
willing to switch to an alternative, reduced-capacity solution for a 
week every 10 years as emergency measure. They won't do it monthly.

In other words: The "theoretical tenant" above that wants to pause 
operations won't exist. If it did, they'd be bankrupt by now :).


Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [13] Dave Hansen — 2024-10-07
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

I figured I'd just write down what I think is the contract that we're
trending towards:

 1. Attestation includes a snapshot of the TCB, which includes the TDX
    module and microcode versions.
 2. There is a record made of each attestation which includes those
    versions.
 3. The machine owner is in control of the components of the TCB and may
    upgrade the components to a later version at any time but can not
    downgrade them.
 4. If there is a security regression in a TCB component (say microcode
    version $V), any TD that ever attested with microcode version $V or
    any earlier version should be considered exposed to the regression.
 5. The attestation record is the sole means of limiting the scope of
    the impact from the regression.

The subtle part of that is that the attestation really isn't for a
single version.  It's fundamentally for that version or any later future
version of the machine owner's choosing.

Note the "or any earlier version" wording in #4.  That's there because
even if $V-1 was not affected, an attacker could silently and
unilaterally upgrade to $V at any time.

It's probably also worth noting that the TDX module can't be runtime
updated today.  Microcode _can_, but I think it's entirely orthogonal to
TDX and they currently don't have any interaction with each other.

I assume it's the same in the AMD or other CoCo worlds.  I just don't
know what the PSP update model is on AMD.

---

## [14] Dan Williams — 2024-10-07
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

Dave Hansen wrote:
> I figured I'd just write down what I think is the contract that we're
> trending towards:

So, in summary per Alex's last note: "there is no operationally viable
way to be a confidential computing tenant in the cloud and distrust
updates from the platform vendor deployed at will by the cloud
operator".

---

## [15] Dionna Amalie Glaze — 2024-10-07
*Subject: Re: [PATCH 4/4] configfs-tsm-report: Introduce TCB stability
 enumeration and watchdog*

On Mon, Oct 7, 2024 at 11:59 AM Dan Williams <dan.j.williams@intel.com> wrote:
>
> Dave Hansen wrote:

Yes. This is also the AMD trust model.

The TCB_VERSION is tracked and included in the key derivation function
for the attestation key. The REPORTED_TCB is what is used to derive
the attestation key, and it can only be UP TO the committed TCB
version. You can be artificially held back to an old VCEK but still
see what your current and committed TCB versions are.
On TDX you can update your microcode and I'm not clear if CPUSVN is
changed subsequently or if you have to run EUPDATESVN first, but there
is a similar delay between updates to TCB and updates to attestation
keys (and certificates).

The microcode, PSP bootloader, TEE component, and SP firmware all have
their own individual security patch level (security version number)
that may not be rolled back by any of the component hotloading
features.
The SEV_CMD_DOWNLOAD_FIRMWARE_EX command will fail if the SP firmware
svn is lower than the committed firmware's svn.
The amd-ucode loading MSR_AMD64_PATCH_LOADER can only add patches. It
cannot remove them. I haven't inspected the other components' late
loading abilities.

The current, committed, reported, and launch TCB_VERSION values are
included in the attestation report to show TCB version change status.

If you want to know about updates before they're rolled out, you can
get on the AMD DevHub provided you have an AMD contact to grant
access. I don't imagine that CSPs can execute on full qualification
and rollout of a new firmware patch within 2 weeks either.

---
