---
title: 'PCI/TSM: Core infrastructure for PCI device\n security (TDISP)'
date: 2025-03-03
last_reply: 2025-05-07
message_count: 43
participants: ['Dan Williams', 'kernel test robot', 'Dionna Amalie Glaze', 'Steven Price', 'Sathyanarayanan Kuppuswamy', 'Huang, Kai', 'Aneesh Kumar K.V', 'Alexey Kardashevskiy', 'Suzuki K Poulose', 'Xu Yilun', 'Zhi Wang']
---

## [1] Dan Williams — 2025-03-03

Changes since v1 [1]:
 - [configfs-tsm: Namespace TSM report symbols]
   - collect tags
 - [coco/guest: Move shared guest CC infrastructure to drivers/virt/coco/guest/]
   - collect tags
 - [coco/tsm: Introduce a core device for TEE Security Managers]
   - Rename 'tsm_subsys' => 'tsm_core_dev' (Jonathan)
 - [PCI/IDE: Enumerate Selective Stream IDE capabilities]
   - Fix the reference PCIe 6.2 specification chapter to 7.9.26 (Bjoen)
   - Treat all specification terms as proper nouns, like "Stream ID" (Bjorn)
   - Rename PCI_IDE_LINK_STREAM to PCI_IDE_LINK_STREAM_0 to indicate
     first of a series (Jonathan)
   - Stop saving sel_ide_cap in pci_dev as it is not a capability block
     (Jonathan)
   - Add support for the "Configuration cycles over Selective Stream"
     mechanism (Alexey, Jonathan)
   - Cache the number of Link Stream register blocks in pci_dev to save
     IDE capability re-reads
   - Clarify 'from Endpoint to Root Port' comment in pci_ide_init()
     (Jonathan)
   - Fix "Number of Selective IDE Streams Supported" 1-based field
     interpretation (Aneesh, Yilun, Jonathan)
   - Switch all register mask definitions to use __GENMASK() to fix
     bugs, cleanup readability, and support usage of FIELD_{PREP,GET}()
     in ide.c (Alexey, Jonathan, Yilun, Aneesh)
 - [PCI/TSM: Authenticate devices via platform TSM]
   - Line wrap documentation, and fixup fidelity to specification
     terminology (Bjorn)
   - Prepare for calling tsm_ops->probe() for Physical Functions beyond
     0 and Virtual Functions, introduce 'struct pci_tsm_pf0' as the
     object to wrap 'struct pci_tsm' in the Physical Function 0 case.
     Call tsm_ops->probe() and tsm_ops->remove() for all functions on a
     device if Physical Function 0 sets pdev->tsm. (Yilun, Aneesh)
   - Drop the complicated 'struct pci_dsm' scheme (Alexey)
   - Fix tsm->state validation, 'init before connect' (Yilun)
   - Move on from if_not_guard(), but not onto the whitespace column
     pressure of scoped_cond_guard() (Jonathan)
   - Rename pci_tsm_register() pci_tsm_core_register() to disambiguate
     from device init in pci_tsm_init() (Jonathan)
 - [samples/devsec: Introduce a PCI device-security bus + endpoint sample]
   - Fix CONFIG_VIRT_DRIVERS=n compilation dependency (0day Kbuild Robot)
   - Switch from a single devm action to remove emulated devices and
     ports to a per-device / per-port scheme (Jonathan)
   - Fix "Number of Selective IDE Streams Supported"
   - Use devm_gen_pool_create() (Jonathan)
 - [PCI: Add PCIe Device 3 Extended Capability enumeration]
 - [PCI/IDE: Add IDE establishment helpers]
   - Drop PCI_IDE_SETUP_ROOT_PORT and its related complications. Push
     Root Port programming responsibility to leaf drivers. (Alexey,
     Jonathan, Bjorn)
   - Clarify that some TSM technologies do not allow system-software to
     allocate the Stream ID (Aneesh)
   - Fundamentally rework the API to stop tying the Stream ID to the
     Endpoint register block index, the Root Port register block index,
     and the platform stream slot. Add pci_ide_strem_alloc() to grab
     those resources and clarify that Stream IDs only need to be unique
     within a Partner Port pairing. The 'struct pci_ide' object is
     updated accordingly to carry all the Partner Port details. (Alexey,
     Jonathan, Aneesh)
   - Add kernel-doc commentary for all exported APIs (Bjorn)
   - Miscellaneous specific terminology fixups and pci.h comment
     cleanups (Bjorn)
   - Drop address association setup for now given the questions around
     its value (Alexey, Yilun)
   - Switch from "devid" to "RID" to match specification language, add a
     comment to address the discrepancy in Linux terms vs PCIe spec
     terms (Bjorn)
   - Setup RID association registers relative to which RIDs are seen at
     either Partner Port (Yilun, Alexey)
 - [PCI/IDE: Report available IDE streams]
   - Rename pci_set_nr_ide_streams() to pci_ide_init_nr_streams() to
     clarify why this one symbols is in the "PCI_IDE" symbol namespace
     since PCI init code is typically built-in. (Alexey)
   - Fix missing quotes in usage of EXPORT_SYMBOL_NS_GPL() and
     MODULE_IMPORT() (Alexey)
 - [PCI/TSM: Report active IDE streams]
   - Documentation fixups (Bjorn)
   - Rename tsm_register_ide_stream() to tsm_ide_stream_register() for
     naming consistency
   - Reflect that the format of the stream link changed from:
     pciDDDD:BB/streamN:DDDD:BB:DD:F
     ...to:
     pciDDDD:BB/streamH.R.E:DDDD:BB:DD:F
 - [samples/devsec: Add sample IDE establishment]
   - Mirror the devsec_tsm_disconnect() sequence in the
     devsec_tsm_connect() error unwind path (Jonathan)
   - Other miscellaneous symmetry on error unwind fixups (Jonathan)

[1]: http://lore.kernel.org/173343739517.1074769.13134786548545925484.stgit@dwillia2-xfh.jf.intel.com

---
Towards devsec-next:

As evidenced by a full page of change notes from v1 to v2 there is
multi-party interest in this core infrastructure, and more importantly,
many small details to negotiate. That number of details to negotiate
only increases with the follow-on "device bind" flows and the
interactions across VFIO, IOMMUFD and KVM.

I expect it will continue to be the case that the mainline ingestion
rate of all this infrastructure results in several more cycles before
mainline ships a complete solution for one or more vendors. In the
meantime, I am looking to run a devsec-next integration tree for kernel
and QEMU. That is, a supplemental staging tree to enable end-to-end
testing while proposals make their way upstream. For now, consider
sending a branch and I will aim to do periodic octopus merges of
submitted branches on top of a kvm-coco-queue + devsec-core baseline.

The main motivation for a "devsec-next" tree, as I mentioned to some in
the hallway track at Plumbers, is to wrangle private hacks and
workarounds in vendor trees to coalesce if not mature.  An example of
multiple vendors solving the same problem in different ways in their
vendor trees is: [2] vs [3]. Note that devsec-next is not intended to
replace vendor trees, and instead reflect the snapshot state of
cross-vendor consensus before topics are ready for linux-next /
mainline.

I will send out more details as a follow up.

[2]: https://github.com/aik/qemu/commit/5256c41f
[3]: http://lore.kernel.org/20250217081833.21568-1-chenyi.qiang@intel.com

---
Original Cover letter:

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
   
The devsec_tsm driver already yielding benefits as it drove many of
the fixes and enhancements of this patch-kit relative to the last RFC
[1]. Future development would either reuse established devsec_tsm paths,
or extend the sample alongside the vendor-specific implementation.
     
This first batch is just enough infrastructure for IDE (link Integrity
and Data Encryption) establishment via TSM APIs. It is based on a review
and curation of the IDE establishment flows from the SEV-TIO RFC [5] and
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

The full series is available via devsec/tsm.git [6].

[4]: http://lore.kernel.org/cover.1719771133.git.lukas@wunner.de
[5]: http://lore.kernel.org/20240823132137.336874-1-aik@amd.com
[6]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=devsec-20250303

---

Dan Williams (11):
      configfs-tsm: Namespace TSM report symbols
      coco/guest: Move shared guest CC infrastructure to drivers/virt/coco/guest/
      coco/tsm: Introduce a core device for TEE Security Managers
      PCI/IDE: Enumerate Selective Stream IDE capabilities
      PCI/TSM: Authenticate devices via platform TSM
      samples/devsec: Introduce a PCI device-security bus + endpoint sample
      PCI: Add PCIe Device 3 Extended Capability enumeration
      PCI/IDE: Add IDE establishment helpers
      PCI/IDE: Report available IDE streams
      PCI/TSM: Report active IDE streams
      samples/devsec: Add sample IDE establishment


 Documentation/ABI/testing/configfs-tsm-report      |    0 
 Documentation/ABI/testing/sysfs-bus-pci            |   45 +
 Documentation/ABI/testing/sysfs-class-tsm          |   20 +
 .../ABI/testing/sysfs-devices-pci-host-bridge      |   44 +
 MAINTAINERS                                        |   10 
 drivers/pci/Kconfig                                |   37 +
 drivers/pci/Makefile                               |    2 
 drivers/pci/ide.c                                  |  499 ++++++++++++++
 drivers/pci/pci-sysfs.c                            |    4 
 drivers/pci/pci.h                                  |   19 +
 drivers/pci/probe.c                                |   26 +
 drivers/pci/remove.c                               |    3 
 drivers/pci/tsm.c                                  |  377 +++++++++++
 drivers/virt/coco/Kconfig                          |    8 
 drivers/virt/coco/Makefile                         |    3 
 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c    |    8 
 drivers/virt/coco/guest/Kconfig                    |    7 
 drivers/virt/coco/guest/Makefile                   |    3 
 drivers/virt/coco/guest/report.c                   |   32 -
 drivers/virt/coco/host/Kconfig                     |    6 
 drivers/virt/coco/host/Makefile                    |    6 
 drivers/virt/coco/host/tsm-core.c                  |  144 ++++
 drivers/virt/coco/sev-guest/sev-guest.c            |   12 
 drivers/virt/coco/tdx-guest/tdx-guest.c            |    8 
 include/linux/pci-ide.h                            |   60 ++
 include/linux/pci-tsm.h                            |  135 ++++
 include/linux/pci.h                                |   25 +
 include/linux/tsm.h                                |   33 +
 include/uapi/linux/pci_regs.h                      |   89 +++
 samples/Kconfig                                    |   16 
 samples/Makefile                                   |    1 
 samples/devsec/Makefile                            |   10 
 samples/devsec/bus.c                               |  698 ++++++++++++++++++++
 samples/devsec/common.c                            |   26 +
 samples/devsec/devsec.h                            |    7 
 samples/devsec/tsm.c                               |  192 ++++++
 36 files changed, 2564 insertions(+), 51 deletions(-)
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

base-commit: 7eb172143d5508b4da468ed59ee857c6e5e01da6

---

## [2] Dan Williams — 2025-03-03
*Subject: [PATCH v2 01/11] configfs-tsm: Namespace TSM report symbols*

In preparation for new + common TSM (TEE Security Manager)
infrastructure, namespace the TSM report symbols in tsm.h with an
_REPORT suffix to differentiate them from other incoming tsm work.

Cc: Yilun Xu <yilun.xu@intel.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Steven Price <steven.price@arm.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
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
index 8e0736dc2ee0..38bcf530c2ae 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24115,7 +24115,7 @@ TRUSTED SECURITY MODULE (TSM) ATTESTATION REPORTS
 M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
-F:	Documentation/ABI/testing/configfs-tsm
+F:	Documentation/ABI/testing/configfs-tsm-report
 F:	drivers/virt/coco/tsm.c
 F:	include/linux/tsm.h
 
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
index 87f162736b2e..0c9ea24a200c 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
@@ -96,7 +96,7 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
 	struct arm_cca_token_info info;
 	void *buf;
 	u8 *token __free(kvfree) = NULL;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 
 	if (desc->inblob_len < 32 || desc->inblob_len > 64)
 		return -EINVAL;
@@ -181,7 +181,7 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
 	return ret;
 }
 
-static const struct tsm_ops arm_cca_tsm_ops = {
+static const struct tsm_report_ops arm_cca_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = arm_cca_report_new,
 };
@@ -202,7 +202,7 @@ static int __init arm_cca_guest_init(void)
 	if (!is_realm_world())
 		return -ENODEV;
 
-	ret = tsm_register(&arm_cca_tsm_ops, NULL);
+	ret = tsm_report_register(&arm_cca_tsm_ops, NULL);
 	if (ret < 0)
 		pr_err("Error %d registering with TSM\n", ret);
 
@@ -216,7 +216,7 @@ module_init(arm_cca_guest_init);
  */
 static void __exit arm_cca_guest_exit(void)
 {
-	tsm_unregister(&arm_cca_tsm_ops);
+	tsm_report_unregister(&arm_cca_tsm_ops);
 }
 module_exit(arm_cca_guest_exit);
 
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 264b6523fe52..964ac8ed8fde 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -317,7 +317,7 @@ struct snp_msg_cert_entry {
 static int sev_svsm_report_new(struct tsm_report *report, void *data)
 {
 	unsigned int rep_len, man_len, certs_len;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	struct svsm_attest_call ac = {};
 	unsigned int retry_count;
 	void *rep, *man, *certs;
@@ -452,7 +452,7 @@ static int sev_svsm_report_new(struct tsm_report *report, void *data)
 static int sev_report_new(struct tsm_report *report, void *data)
 {
 	struct snp_msg_cert_entry *cert_table;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	struct snp_guest_dev *snp_dev = data;
 	struct snp_msg_report_resp_hdr hdr;
 	const u32 report_size = SZ_4K;
@@ -581,7 +581,7 @@ static bool sev_report_bin_attr_visible(int n)
 	return false;
 }
 
-static struct tsm_ops sev_tsm_ops = {
+static struct tsm_report_ops sev_tsm_report_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = sev_report_new,
 	.report_attr_visible = sev_report_attr_visible,
@@ -590,7 +590,7 @@ static struct tsm_ops sev_tsm_ops = {
 
 static void unregister_sev_tsm(void *data)
 {
-	tsm_unregister(&sev_tsm_ops);
+	tsm_report_unregister(&sev_tsm_report_ops);
 }
 
 static int __init sev_guest_probe(struct platform_device *pdev)
@@ -627,9 +627,9 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	misc->fops = &snp_guest_fops;
 
 	/* Set the privlevel_floor attribute based on the vmpck_id */
-	sev_tsm_ops.privlevel_floor = mdesc->vmpck_id;
+	sev_tsm_report_ops.privlevel_floor = mdesc->vmpck_id;
 
-	ret = tsm_register(&sev_tsm_ops, snp_dev);
+	ret = tsm_report_register(&sev_tsm_report_ops, snp_dev);
 	if (ret)
 		goto e_msg_init;
 
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 224e7dde9cde..bd043838ab2e 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -161,7 +161,7 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 {
 	u8 *buf, *reportdata = NULL, *tdreport = NULL;
 	struct tdx_quote_buf *quote_buf = quote_data;
-	struct tsm_desc *desc = &report->desc;
+	struct tsm_report_desc *desc = &report->desc;
 	int ret;
 	u64 err;
 
@@ -297,7 +297,7 @@ static const struct x86_cpu_id tdx_guest_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_guest_ids);
 
-static const struct tsm_ops tdx_tsm_ops = {
+static const struct tsm_report_ops tdx_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = tdx_report_new,
 	.report_attr_visible = tdx_report_attr_visible,
@@ -322,7 +322,7 @@ static int __init tdx_guest_init(void)
 		goto free_misc;
 	}
 
-	ret = tsm_register(&tdx_tsm_ops, NULL);
+	ret = tsm_report_register(&tdx_tsm_ops, NULL);
 	if (ret)
 		goto free_quote;
 
@@ -339,7 +339,7 @@ module_init(tdx_guest_init);
 
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

## [3] Dan Williams — 2025-03-03
*Subject: [PATCH v2 02/11] coco/guest: Move shared guest CC infrastructure to
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
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
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
index 38bcf530c2ae..6a1d705c8eac 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24116,7 +24116,7 @@ M:	Dan Williams <dan.j.williams@intel.com>
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

## [4] Dan Williams — 2025-03-03
*Subject: [PATCH v2 03/11] coco/tsm: Introduce a core device for TEE Security
 Managers*

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
 Documentation/ABI/testing/sysfs-class-tsm |   10 +++
 MAINTAINERS                               |    3 +
 drivers/virt/coco/Kconfig                 |    2 +
 drivers/virt/coco/Makefile                |    1 
 drivers/virt/coco/host/Kconfig            |    6 ++
 drivers/virt/coco/host/Makefile           |    6 ++
 drivers/virt/coco/host/tsm-core.c         |  112 +++++++++++++++++++++++++++++
 include/linux/tsm.h                       |    5 +
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
index 6a1d705c8eac..352f982f435e 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24111,12 +24111,13 @@ W:	https://github.com/srcres258/linux-doc
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

## [5] Dan Williams — 2025-03-03
*Subject: [PATCH v2 04/11] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

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
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Kconfig           |   14 ++++++
 drivers/pci/Makefile          |    1 
 drivers/pci/ide.c             |   89 +++++++++++++++++++++++++++++++++++++++++
 drivers/pci/pci.h             |    6 +++
 drivers/pci/probe.c           |    1 
 include/linux/pci.h           |    7 +++
 include/uapi/linux/pci_regs.h |   81 +++++++++++++++++++++++++++++++++++++
 7 files changed, 198 insertions(+), 1 deletion(-)
 create mode 100644 drivers/pci/ide.c

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 2fbd379923fd..5fb6dd113b0d 100644
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
index 000000000000..193380763812
--- /dev/null
+++ b/drivers/pci/ide.c
@@ -0,0 +1,89 @@
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
+static int sel_ide_offset(int nr_link_ide, int stream_index, int nr_ide_mem)
+{
+	int offset;
+
+	offset = PCI_IDE_LINK_STREAM_0 + nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE;
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
+
+	nr_ide_mem = 0;
+	nr_streams = min(1 + FIELD_GET(PCI_IDE_CAP_SEL_NUM_MASK, val),
+			 CONFIG_PCI_IDE_STREAM_MAX);
+	for (int i = 0; i < nr_streams; i++) {
+		int offset = sel_ide_offset(nr_link_ide, i, nr_ide_mem);
+		int nr_assoc;
+		u32 val;
+
+		pci_read_config_dword(pdev, ide_cap + offset, &val);
+
+		/*
+		 * Let's not entertain devices that do not have a
+		 * constant number of address association blocks
+		 */
+		nr_assoc = FIELD_GET(PCI_IDE_SEL_CAP_ASSOC_NUM_MASK, val);
+		if (i && (nr_assoc != nr_ide_mem)) {
+			pci_info(pdev, "Unsupported Selective Stream %d capability\n", i);
+			return;
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
index 01e51db8d285..6927028ab695 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -456,6 +456,12 @@ static inline void pci_npem_create(struct pci_dev *dev) { }
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
index 246744d8d268..6114d199c1d5 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2565,6 +2565,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_rcec_init(dev);		/* Root Complex Event Collector */
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
+	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 47b31ad724fa..628f9f5fdac9 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -530,6 +530,13 @@ struct pci_dev {
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
index 3445c4970e4d..000258cd93c8 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -749,7 +749,8 @@
 #define PCI_EXT_CAP_ID_NPEM	0x29	/* Native PCIe Enclosure Management */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
-#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_DOE
+#define PCI_EXT_CAP_ID_IDE	0x30    /* Integrity and Data Encryption */
+#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE
 
 #define PCI_EXT_CAP_DSN_SIZEOF	12
 #define PCI_EXT_CAP_MCAST_ENDPOINT_SIZEOF 40
@@ -1213,4 +1214,82 @@
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

## [6] Dan Williams — 2025-03-03
*Subject: [PATCH v2 05/11] PCI/TSM: Authenticate devices via platform TSM*

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
 Documentation/ABI/testing/sysfs-bus-pci |   45 ++++
 MAINTAINERS                             |    2 
 drivers/pci/Kconfig                     |   23 ++
 drivers/pci/Makefile                    |    1 
 drivers/pci/pci-sysfs.c                 |    4 
 drivers/pci/pci.h                       |   10 +
 drivers/pci/probe.c                     |    1 
 drivers/pci/remove.c                    |    3 
 drivers/pci/tsm.c                       |  377 +++++++++++++++++++++++++++++++
 drivers/virt/coco/host/tsm-core.c       |   19 +-
 include/linux/pci-tsm.h                 |  135 +++++++++++
 include/linux/pci.h                     |    3 
 include/linux/tsm.h                     |    4 
 include/uapi/linux/pci_regs.h           |    1 
 14 files changed, 625 insertions(+), 3 deletions(-)
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 include/linux/pci-tsm.h

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 5da6a14dc326..816a342695b3 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -583,3 +583,48 @@ Description:
 		enclosure-specific indications "specific0" to "specific7",
 		hence the corresponding led class devices are unavailable if
 		the DSM interface is used.
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
index 352f982f435e..80a5951bfa04 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24116,8 +24116,10 @@ M:	Dan Williams <dan.j.williams@intel.com>
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
index 5fb6dd113b0d..f9e0e517aaed 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -135,6 +135,29 @@ config PCI_IDE_STREAM_MAX
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
+config PCI_TSM_DEBUG
+	bool "PCI TSM: Debug"
+	depends on PCI_TSM
+	help
+	  Enable runtime sanity checks and assertions for the pci_tsm
+	  object model. For example, validate that a low-level TSM
+	  driver use the expected initialization helpers for newly
+	  created objects.
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
index b46ce1a2c554..b595cbaed8c0 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1804,6 +1804,10 @@ const struct attribute_group *pci_dev_attr_groups[] = {
 #endif
 #ifdef CONFIG_PCIEASPM
 	&aspm_ctrl_attr_group,
+#endif
+#ifdef CONFIG_PCI_TSM
+	&pci_tsm_auth_attr_group,
+	&pci_tsm_pf0_attr_group,
 #endif
 	NULL,
 };
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 6927028ab695..b38bdd91e742 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -462,6 +462,16 @@ void pci_ide_init(struct pci_dev *dev);
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
index 6114d199c1d5..1d1d7de642da 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2566,6 +2566,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
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
index 000000000000..e5ea9f306672
--- /dev/null
+++ b/drivers/pci/tsm.c
@@ -0,0 +1,377 @@
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
+	if (!is_pci_tsm_pf0(pdev) || !pci_tsm_check_type(pci_tsm, PCI_TSM_PF0)) {
+		dev_WARN_ONCE(&pdev->dev, 1, "invalid context object\n");
+		return NULL;
+	}
+
+	return container_of(pci_tsm, struct pci_tsm_pf0, tsm);
+}
+
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
+/* registration read lock */
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
+	pci_tsm_set_type(&tsm->tsm, PCI_TSM_PF0);
+	tsm->tsm.pdev = pdev;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_pf0_initialize);
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
+static void pci_tsm_virtfn_init(struct pci_dev *pdev)
+{
+	if (!pci_physfn(pdev)->tsm)
+		return;
+
+	struct pci_tsm *pci_tsm __free(tsm_remove) = tsm_ops->probe(pdev);
+	if (!pci_tsm)
+		return;
+
+	pdev->tsm = no_free_ptr(pci_tsm);
+}
+
+static void pci_tsm_mfd_init(struct pci_dev *pdev)
+{
+	struct pci_dev *pf0_dev __free(pci_dev_put) =
+		pci_get_slot(pdev->bus, pdev->devfn - PCI_FUNC(pdev->devfn));
+
+	if (!pf0_dev)
+		return;
+
+	if (!pf0_dev->tsm)
+		return;
+
+	struct pci_tsm *pci_tsm __free(tsm_remove) = tsm_ops->probe(pdev);
+	if (!pci_tsm)
+		return;
+
+	pdev->tsm = no_free_ptr(pci_tsm);
+}
+
+static void __pci_tsm_init(struct pci_dev *pdev)
+{
+	if (is_pci_tsm_pf0(pdev))
+		pci_tsm_pf0_init(pdev);
+	else if (pdev->is_virtfn)
+		pci_tsm_virtfn_init(pdev);
+	else
+		pci_tsm_mfd_init(pdev);
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
index 000000000000..17657b7ef66c
--- /dev/null
+++ b/include/linux/pci-tsm.h
@@ -0,0 +1,135 @@
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
+enum pci_tsm_type {
+	PCI_TSM_INVALID,
+	PCI_TSM_PF0,
+	PCI_TSM_VIRTFN,
+	PCI_TSM_MFD,
+};
+
+/**
+ * struct pci_tsm - Core TSM context for a given PCIe endpoint
+ * @pdev: indicates the type of pci_tsm object
+ * @type: debug validation of the pci_tsm object type inferred by @pdev
+ *
+ * This structure is wrapped by a low level TSM driver and returned by
+ * tsm_ops.probe(), it is freed by tsm_ops.remove(). Depending on
+ * whether @pdev is physical function 0, another physical function, or a
+ * virtual function determines the pci_tsm object type. E.g. see 'struct
+ * pci_tsm_pf0'.
+ */
+struct pci_tsm {
+	struct pci_dev *pdev;
+#ifdef CONFIG_PCI_TSM_DEBUG
+	enum pci_tsm_type type;
+#endif
+};
+
+#ifdef CONFIG_PCI_TSM_DEBUG
+static inline void pci_tsm_set_type(struct pci_tsm *pci_tsm, enum pci_tsm_type type)
+{
+	pci_tsm->type = type;
+}
+static inline bool pci_tsm_check_type(struct pci_tsm *pci_tsm, enum pci_tsm_type type)
+{
+	return pci_tsm->type == type;
+}
+#else
+static inline void pci_tsm_set_type(struct pci_tsm *pci_tsm, enum pci_tsm_type type)
+{
+}
+
+static inline bool pci_tsm_check_type(struct pci_tsm *pci_tsm, enum pci_tsm_type type)
+{
+	return true;
+}
+#endif
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
+static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
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
index 628f9f5fdac9..57cfa0e3f2bd 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -537,6 +537,9 @@ struct pci_dev {
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
index 000258cd93c8..713588a29813 100644
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

## [7] Dan Williams — 2025-03-03
*Subject: [PATCH v2 06/11] samples/devsec: Introduce a PCI device-security
 bus + endpoint sample*

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
 samples/Kconfig         |   16 +
 samples/Makefile        |    1 
 samples/devsec/Makefile |   10 +
 samples/devsec/bus.c    |  692 +++++++++++++++++++++++++++++++++++++++++++++++
 samples/devsec/common.c |   26 ++
 samples/devsec/devsec.h |    7 
 samples/devsec/tsm.c    |  121 ++++++++
 8 files changed, 874 insertions(+)
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/tsm.c

diff --git a/MAINTAINERS b/MAINTAINERS
index 80a5951bfa04..69d74790f2ff 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24121,6 +24121,7 @@ F:	drivers/virt/coco/guest/
 F:	drivers/virt/coco/host/
 F:	include/linux/pci-tsm.h
 F:	include/linux/tsm.h
+F:	samples/devsec/
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index 820e00b2ed68..6bd64fc54ac1 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -304,6 +304,22 @@ source "samples/rust/Kconfig"
 
 source "samples/damon/Kconfig"
 
+config SAMPLE_DEVSEC
+	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
+	depends on PCI
+	depends on VIRT_DRIVERS
+	depends on X86 # TODO: PCI_DOMAINS_GENERIC support
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
index f24cd0d72dd0..e4d8820e878f 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -42,3 +42,4 @@ obj-$(CONFIG_SAMPLE_FPROBE)		+= fprobe/
 obj-$(CONFIG_SAMPLES_RUST)		+= rust/
 obj-$(CONFIG_SAMPLE_DAMON_WSSE)		+= damon/
 obj-$(CONFIG_SAMPLE_DAMON_PRCL)		+= damon/
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
index 000000000000..69117db10897
--- /dev/null
+++ b/samples/devsec/bus.c
@@ -0,0 +1,692 @@
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
+#define NR_PORT_STREAMS 1
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
+static void destroy_bus(void *data)
+{
+	struct devsec *devsec = data;
+
+	pci_stop_root_bus(devsec->bus);
+	pci_remove_root_bus(devsec->bus);
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
index 000000000000..7698df2b4e29
--- /dev/null
+++ b/samples/devsec/tsm.c
@@ -0,0 +1,121 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
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

## [8] Dan Williams — 2025-03-03
*Subject: [PATCH v2 07/11] PCI: Add PCIe Device 3 Extended Capability
 enumeration*

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
 drivers/pci/probe.c           |   12 ++++++++++++
 include/linux/pci.h           |    1 +
 include/uapi/linux/pci_regs.h |    7 +++++++
 3 files changed, 20 insertions(+)

diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 1d1d7de642da..e1c915629864 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2251,6 +2251,17 @@ int pci_configure_extended_tags(struct pci_dev *dev, void *ign)
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
@@ -2565,6 +2576,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_rcec_init(dev);		/* Root Complex Event Collector */
 	pci_doe_init(dev);		/* Data Object Exchange */
 	pci_tph_init(dev);		/* TLP Processing Hints */
+	pci_dev3_init(dev);		/* Device 3 capabilities */
 	pci_ide_init(dev);		/* Link Integrity and Data Encryption */
 	pci_tsm_init(dev);		/* TEE Security Manager connection */
 
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 57cfa0e3f2bd..b5ea9869c2b1 100644
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
index 713588a29813..d17579592027 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -750,6 +750,7 @@
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

## [9] Dan Williams — 2025-03-03
*Subject: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

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
  Run the stream after IDE_KM.

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
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 .../ABI/testing/sysfs-devices-pci-host-bridge      |   32 ++
 drivers/pci/ide.c                                  |  352 ++++++++++++++++++++
 include/linux/pci-ide.h                            |   60 +++
 include/linux/pci.h                                |    6 
 4 files changed, 450 insertions(+)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 create mode 100644 include/linux/pci-ide.h

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
new file mode 100644
index 000000000000..51dc9eed9353
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -0,0 +1,32 @@
+What:		/sys/devices/pciDDDD:BB
+		/sys/devices/.../pciDDDD:BB
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		A PCI host bridge device parents a PCI bus device topology. PCI
+		controllers may also parent host bridges. The DDDD:BB format
+		conveys the PCI domain number and root bus number of the
+		host bridge.
+
+What:		pciDDDD:BB/firmware_node
+Date:		December, 2024
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) Symlink to the platform firmware device object "companion"
+		of the host bridge. For example, an ACPI device with an _HID of
+		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00).
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
+		stream resources shared by the Root Ports in a host bridge.
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 193380763812..b2091f6260e6 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -5,6 +5,8 @@
 
 #define dev_fmt(fmt) "PCI/IDE: " fmt
 #include <linux/pci.h>
+#include <linux/sysfs.h>
+#include <linux/pci-ide.h>
 #include <linux/bitfield.h>
 #include "pci.h"
 
@@ -85,5 +87,355 @@ void pci_ide_init(struct pci_dev *pdev)
 
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
+	struct pci_ide *ide __free(kfree) = kzalloc(sizeof(*ide), GFP_KERNEL);
+	if (!ide)
+		return NULL;
+
+	hb = pci_find_host_bridge(pdev->bus);
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
+static int ide_domain(struct pci_dev *pdev)
+{
+	if (pdev->fm_enabled)
+		return pci_domain_nr(pdev->bus);
+	return 0;
+}
+
+static struct pci_ide_partner *to_settings(struct pci_dev *pdev, struct pci_ide *ide)
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
+	case PCI_EXP_TYPE_ROOT_PORT:
+		struct pci_dev *rp = pcie_find_root_port(ide->pdev);
+
+		if (pdev != pcie_find_root_port(ide->pdev)) {
+			pci_warn_once(pdev, "setup expected Root Port: %s\n",
+				      pci_name(rp));
+			return NULL;
+		}
+		return &ide->partner[PCI_IDE_RP];
+	default:
+		pci_warn_once(pdev, "invalid device type\n");
+		return NULL;
+	}
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
+	struct pci_ide_partner *settings = to_settings(pdev, ide);
+	int pos;
+	u32 val;
+
+	if (!settings)
+		return;
+
+	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+			     pdev->nr_ide_mem);
+
+	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT_MASK, settings->rid_end);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
+
+	val = PREP_PCI_IDE_SEL_RID_2(settings->rid_start, ide_domain(pdev));
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
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
+	struct pci_ide_partner *settings = to_settings(pdev, ide);
+	int pos;
+
+	if (!settings)
+		return;
+
+	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+			     pdev->nr_ide_mem);
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
+void pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	struct pci_ide_partner *settings = to_settings(pdev, ide);
+	int pos;
+	u32 val;
+
+	if (!settings)
+		return;
+
+	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+			     pdev->nr_ide_mem);
+
+	val = FIELD_PREP(PCI_IDE_SEL_CTL_ID_MASK, ide->stream_id) |
+	      FIELD_PREP(PCI_IDE_SEL_CTL_DEFAULT, 1) |
+	      FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, pdev->ide_cfg) |
+	      FIELD_PREP(PCI_IDE_SEL_CTL_TEE_LIMITED, pdev->ide_tee_limit) |
+	      FIELD_PREP(PCI_IDE_SEL_CTL_EN, 1);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
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
+	struct pci_ide_partner *settings = to_settings(pdev, ide);
+	int pos;
+
+	if (!settings)
+		return;
+
+	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+			     pdev->nr_ide_mem);
+
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_disable);
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
new file mode 100644
index 000000000000..7a3f72915ee2
--- /dev/null
+++ b/include/linux/pci-ide.h
@@ -0,0 +1,60 @@
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
+struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
+void pci_ide_stream_free(struct pci_ide *ide);
+DEFINE_FREE(pci_ide_stream_free, struct pci_ide *, if (_T) pci_ide_stream_free(_T))
+int  pci_ide_stream_register(struct pci_ide *ide);
+void pci_ide_stream_unregister(struct pci_ide *ide);
+void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide);
+void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide);
+#endif /* __PCI_IDE_H__ */
diff --git a/include/linux/pci.h b/include/linux/pci.h
index b5ea9869c2b1..0f9d6aece346 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -536,6 +536,8 @@ struct pci_dev {
 	u16		ide_cap;	/* Link Integrity & Data Encryption */
 	u8		nr_ide_mem;	/* Address association resources for streams */
 	u8		nr_link_ide;	/* Link Stream count (Selective Stream offset) */
+	u8		nr_sel_ide;	/* Selective Stream count (register block allocator) */
+	DECLARE_BITMAP(ide_stream_map, CONFIG_PCI_IDE_STREAM_MAX);
 	unsigned int	ide_cfg:1;	/* Config cycles over IDE */
 	unsigned int	ide_tee_limit:1; /* Disallow T=0 traffic over IDE */
 #endif
@@ -603,6 +605,10 @@ struct pci_host_bridge {
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

## [10] Dan Williams — 2025-03-03
*Subject: [PATCH v2 09/11] PCI/IDE: Report available IDE streams*

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
 .../ABI/testing/sysfs-devices-pci-host-bridge      |   12 ++++
 drivers/pci/ide.c                                  |   58 ++++++++++++++++++++
 drivers/pci/pci.h                                  |    3 +
 drivers/pci/probe.c                                |   12 ++++
 include/linux/pci.h                                |    8 +++
 5 files changed, 92 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index 51dc9eed9353..4624469e56d4 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -20,6 +20,7 @@ What:		pciDDDD:BB/streamH.R.E:DDDD:BB:DD:F
 Date:		December, 2024
 Contact:	linux-pci@vger.kernel.org
 Description:
+<<<<<<< current
 		(RO) When a platform has established a secure connection, PCIe
 		IDE, between two Partner Ports, this symlink appears. The
 		primary function is to account the stream slot / resources
@@ -30,3 +31,14 @@ Description:
 		assigned Selective IDE Stream Register Block in the Root Port
 		and Endpoint, and H represents a platform specific pool of
 		stream resources shared by the Root Ports in a host bridge.
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
+		count is determined by counting stream symlinks.
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index b2091f6260e6..0c72985e6a65 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -439,3 +439,61 @@ void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide)
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
+ * pci_init_nr_ide_streams() - size the pool of IDE Stream resources
+ * @hb: host bridge boundary for the stream pool
+ * @nr: number of streams
+ *
+ * Enable IDE Stream establishment by setting the number of stream
+ * resources available at the host bridge. Platform init code must set
+ * this before the first pci_ide_stream_alloc() call.
+ *
+ * The "PCI_IDE" symbol namespace is required because this is typically
+ * a detail that is settled in early PCI init, i.e. only an expert or
+ * test module should consume this export.
+ */
+void pci_ide_init_nr_streams(struct pci_host_bridge *hb, int nr)
+{
+	hb->nr_ide_streams = nr;
+	sysfs_update_group(&hb->dev.kobj, &pci_ide_attr_group);
+}
+EXPORT_SYMBOL_NS_GPL(pci_ide_init_nr_streams, "PCI_IDE");
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index b38bdd91e742..6c050eb9a91b 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -458,8 +458,11 @@ static inline void pci_npem_remove(struct pci_dev *dev) { }
 
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
index e1c915629864..a383cc32c84b 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -633,6 +633,16 @@ static void pci_release_host_bridge_dev(struct device *dev)
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
@@ -652,6 +662,7 @@ static void pci_init_host_bridge(struct pci_host_bridge *bridge)
 	bridge->native_dpc = 1;
 	bridge->domain_nr = PCI_DOMAIN_NR_NOT_SET;
 	bridge->native_cxl_error = 1;
+	bridge->dev.type = &pci_host_bridge_type;
 
 	device_initialize(&bridge->dev);
 }
@@ -665,7 +676,6 @@ struct pci_host_bridge *pci_alloc_host_bridge(size_t priv)
 		return NULL;
 
 	pci_init_host_bridge(bridge);
-	bridge->dev.release = pci_release_host_bridge_dev;
 
 	return bridge;
 }
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 0f9d6aece346..c2f18f31f7a7 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -660,6 +660,14 @@ void pci_set_host_bridge_release(struct pci_host_bridge *bridge,
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

## [11] Dan Williams — 2025-03-03
*Subject: [PATCH v2 10/11] PCI/TSM: Report active IDE streams*

Given that the platform TSM owns IDE Stream ID allocation, report the
active streams via the TSM class device. Establish a symlink from the
class device to the PCI endpoint device consuming the stream, named by
the Stream ID.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm |   10 ++++++++++
 drivers/virt/coco/host/tsm-core.c         |   17 +++++++++++++++++
 include/linux/tsm.h                       |    4 ++++
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

## [12] Dan Williams — 2025-03-03
*Subject: [PATCH v2 11/11] samples/devsec: Add sample IDE establishment*

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
 samples/devsec/bus.c |    6 ++++
 samples/devsec/tsm.c |   73 +++++++++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 78 insertions(+), 1 deletion(-)

diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
index 69117db10897..b78c04b21eb9 100644
--- a/samples/devsec/bus.c
+++ b/samples/devsec/bus.c
@@ -15,6 +15,7 @@
 
 #define NR_DEVSEC_BUSES 1
 #define NR_DEVSEC_ROOT_PORTS 1
+#define NR_PLATFORM_STREAMS 4
 #define NR_PORT_STREAMS 1
 #define NR_ADDR_ASSOC 1
 #define NR_DEVSEC_DEVS 1
@@ -589,6 +590,7 @@ static int __init devsec_bus_probe(struct platform_device *pdev)
 	struct devsec *devsec;
 	struct pci_sysdata *sd;
 	u64 mmio_size = SZ_64G;
+	struct pci_host_bridge *hb;
 	struct device *dev = &pdev->dev;
 	u64 mmio_start = iomem_resource.end + 1 - SZ_64G;
 
@@ -649,6 +651,9 @@ static int __init devsec_bus_probe(struct platform_device *pdev)
 	if (rc)
 		return rc;
 
+	hb = pci_find_host_bridge(devsec->bus);
+	pci_ide_init_nr_streams(hb, NR_PLATFORM_STREAMS);
+
 	pci_scan_child_bus(devsec->bus);
 
 	return 0;
@@ -688,5 +693,6 @@ static void __exit devsec_bus_exit(void)
 }
 module_exit(devsec_bus_exit);
 
+MODULE_IMPORT_NS("PCI_IDE");
 MODULE_LICENSE("GPL");
 MODULE_DESCRIPTION("Device Security Sample Infrastructure: TDISP Device Emulation");
diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
index 7698df2b4e29..9c033662c1b4 100644
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
@@ -50,13 +51,83 @@ static void devsec_tsm_pci_remove(struct pci_tsm *tsm)
 	kfree(devsec_tsm);
 }
 
+/* protected by tsm_ops lock */
+static DECLARE_BITMAP(devsec_stream_ids, NR_TSM_STREAMS);
+static struct pci_ide *devsec_streams[NR_TSM_STREAMS];
+
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
+	pci_ide_stream_enable(pdev, ide);
+	devsec_streams[stream_id] = ide;
+
+	return 0;
+
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

## [13] kernel test robot — 2025-03-04
*Subject: Re: [PATCH v2 09/11] PCI/IDE: Report available IDE streams*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 7eb172143d5508b4da468ed59ee857c6e5e01da6]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/configfs-tsm-Namespace-TSM-report-symbols/20250304-152958
base:   7eb172143d5508b4da468ed59ee857c6e5e01da6
patch link:    https://lore.kernel.org/r/174107250696.1288555.15924775074966673629.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH v2 09/11] PCI/IDE: Report available IDE streams
config: s390-allyesconfig (https://download.01.org/0day-ci/archive/20250304/202503042126.FUEGx8dD-lkp@intel.com/config)
compiler: s390-linux-gcc (GCC) 14.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250304/202503042126.FUEGx8dD-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202503042126.FUEGx8dD-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> drivers/pci/ide.c:495: warning: expecting prototype for pci_init_nr_ide_streams(). Prototype was for pci_ide_init_nr_streams() instead


vim +495 drivers/pci/ide.c

   480	
   481	/**
   482	 * pci_init_nr_ide_streams() - size the pool of IDE Stream resources
   483	 * @hb: host bridge boundary for the stream pool
   484	 * @nr: number of streams
   485	 *
   486	 * Enable IDE Stream establishment by setting the number of stream
   487	 * resources available at the host bridge. Platform init code must set
   488	 * this before the first pci_ide_stream_alloc() call.
   489	 *
   490	 * The "PCI_IDE" symbol namespace is required because this is typically
   491	 * a detail that is settled in early PCI init, i.e. only an expert or
   492	 * test module should consume this export.
   493	 */
   494	void pci_ide_init_nr_streams(struct pci_host_bridge *hb, int nr)
 > 495	{

---

## [14] Dionna Amalie Glaze — 2025-03-04
*Subject: Re: [PATCH v2 09/11] PCI/IDE: Report available IDE streams*

On Mon, Mar 3, 2025 at 11:20 PM Dan Williams <dan.j.williams@intel.com> wrote:
>
> The limited number of link-encryption (IDE) streams that a given set of

Drop?

>                 (RO) When a platform has established a secure connection, PCIe
>                 IDE, between two Partner Ports, this symlink appears. The

Please describe the expected form metavariables DDDD and BB will take.

> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> index b2091f6260e6..0c72985e6a65 100644

/size/sets the size of/

> + * @hb: host bridge boundary for the stream pool
> + * @nr: number of streams

Is failing to call this a caught error by pci_ide_stream_alloc?

> + *
> + * The "PCI_IDE" symbol namespace is required because this is typically

Perhaps start with "Expert use only"?

> + */
> +void pci_ide_init_nr_streams(struct pci_host_bridge *hb, int nr)

---

## [15] kernel test robot — 2025-03-05
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 7eb172143d5508b4da468ed59ee857c6e5e01da6]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/configfs-tsm-Namespace-TSM-report-symbols/20250304-152958
base:   7eb172143d5508b4da468ed59ee857c6e5e01da6
patch link:    https://lore.kernel.org/r/174107250147.1288555.16948528371146013276.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers
config: s390-allmodconfig (https://download.01.org/0day-ci/archive/20250305/202503050439.9Ubeq0dP-lkp@intel.com/config)
compiler: clang version 19.1.7 (https://github.com/llvm/llvm-project cd708029e0b2869e80abe31ddb175f7c35361f90)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250305/202503050439.9Ubeq0dP-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202503050439.9Ubeq0dP-lkp@intel.com/

All warnings (new ones prefixed by >>):

   In file included from drivers/pci/ide.c:7:
   In file included from include/linux/pci.h:37:
   In file included from include/linux/device.h:32:
   In file included from include/linux/device/driver.h:21:
   In file included from include/linux/module.h:19:
   In file included from include/linux/elf.h:6:
   In file included from arch/s390/include/asm/elf.h:181:
   In file included from arch/s390/include/asm/mmu_context.h:11:
   In file included from arch/s390/include/asm/pgalloc.h:18:
   In file included from include/linux/mm.h:2224:
   include/linux/vmstat.h:504:43: warning: arithmetic between different enumeration types ('enum zone_stat_item' and 'enum numa_stat_item') [-Wenum-enum-conversion]
     504 |         return vmstat_text[NR_VM_ZONE_STAT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~ ^
     505 |                            item];
         |                            ~~~~
   include/linux/vmstat.h:511:43: warning: arithmetic between different enumeration types ('enum zone_stat_item' and 'enum numa_stat_item') [-Wenum-enum-conversion]
     511 |         return vmstat_text[NR_VM_ZONE_STAT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~ ^
     512 |                            NR_VM_NUMA_EVENT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~~
   include/linux/vmstat.h:524:43: warning: arithmetic between different enumeration types ('enum zone_stat_item' and 'enum numa_stat_item') [-Wenum-enum-conversion]
     524 |         return vmstat_text[NR_VM_ZONE_STAT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~ ^
     525 |                            NR_VM_NUMA_EVENT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~~
>> drivers/pci/ide.c:322:3: warning: label followed by a declaration is a C23 extension [-Wc23-extensions]
     322 |                 struct pci_dev *rp = pcie_find_root_port(ide->pdev);
         |                 ^
   4 warnings generated.


vim +322 drivers/pci/ide.c

   306	
   307	static struct pci_ide_partner *to_settings(struct pci_dev *pdev, struct pci_ide *ide)
   308	{
   309		if (!pci_is_pcie(pdev)) {
   310			pci_warn_once(pdev, "not a PCIe device\n");
   311			return NULL;
   312		}
   313	
   314		switch (pci_pcie_type(pdev)) {
   315		case PCI_EXP_TYPE_ENDPOINT:
   316			if (pdev != ide->pdev) {
   317				pci_warn_once(pdev, "setup expected Endpoint: %s\n", pci_name(ide->pdev));
   318				return NULL;
   319			}
   320			return &ide->partner[PCI_IDE_EP];
   321		case PCI_EXP_TYPE_ROOT_PORT:
 > 322			struct pci_dev *rp = pcie_find_root_port(ide->pdev);
   323	
   324			if (pdev != pcie_find_root_port(ide->pdev)) {
   325				pci_warn_once(pdev, "setup expected Root Port: %s\n",
   326					      pci_name(rp));
   327				return NULL;
   328			}
   329			return &ide->partner[PCI_IDE_RP];
   330		default:
   331			pci_warn_once(pdev, "invalid device type\n");
   332			return NULL;
   333		}
   334	}
   335

---

## [16] Steven Price — 2025-03-05
*Subject: Re: [PATCH v2 01/11] configfs-tsm: Namespace TSM report symbols*

On 04/03/2025 07:14, Dan Williams wrote:
> In preparation for new + common TSM (TEE Security Manager)
> infrastructure, namespace the TSM report symbols in tsm.h with an

Reviewed-by: Steven Price <steven.price@arm.com>

> ---
>  Documentation/ABI/testing/configfs-tsm-report   |    0

---

## [17] kernel test robot — 2025-03-05
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Hi Dan,

kernel test robot noticed the following build errors:

[auto build test ERROR on 7eb172143d5508b4da468ed59ee857c6e5e01da6]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/configfs-tsm-Namespace-TSM-report-symbols/20250304-152958
base:   7eb172143d5508b4da468ed59ee857c6e5e01da6
patch link:    https://lore.kernel.org/r/174107250147.1288555.16948528371146013276.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers
config: powerpc-allyesconfig (https://download.01.org/0day-ci/archive/20250305/202503052042.Clxxh3ZH-lkp@intel.com/config)
compiler: clang version 16.0.6 (https://github.com/llvm/llvm-project 7cbf1a2591520c2491aa35339f227775f4d3adf6)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250305/202503052042.Clxxh3ZH-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202503052042.Clxxh3ZH-lkp@intel.com/

All errors (new ones prefixed by >>):

>> drivers/pci/ide.c:322:3: error: expected expression
                   struct pci_dev *rp = pcie_find_root_port(ide->pdev);
                   ^
>> drivers/pci/ide.c:326:20: error: use of undeclared identifier 'rp'
                                         pci_name(rp));
                                                  ^
   2 errors generated.


vim +322 drivers/pci/ide.c

   306	
   307	static struct pci_ide_partner *to_settings(struct pci_dev *pdev, struct pci_ide *ide)
   308	{
   309		if (!pci_is_pcie(pdev)) {
   310			pci_warn_once(pdev, "not a PCIe device\n");
   311			return NULL;
   312		}
   313	
   314		switch (pci_pcie_type(pdev)) {
   315		case PCI_EXP_TYPE_ENDPOINT:
   316			if (pdev != ide->pdev) {
   317				pci_warn_once(pdev, "setup expected Endpoint: %s\n", pci_name(ide->pdev));
   318				return NULL;
   319			}
   320			return &ide->partner[PCI_IDE_EP];
   321		case PCI_EXP_TYPE_ROOT_PORT:
 > 322			struct pci_dev *rp = pcie_find_root_port(ide->pdev);
   323	
   324			if (pdev != pcie_find_root_port(ide->pdev)) {
   325				pci_warn_once(pdev, "setup expected Root Port: %s\n",
 > 326					      pci_name(rp));
   327				return NULL;
   328			}
   329			return &ide->partner[PCI_IDE_RP];
   330		default:
   331			pci_warn_once(pdev, "invalid device type\n");
   332			return NULL;
   333		}
   334	}
   335

---

## [18] Sathyanarayanan Kuppuswamy — 2025-03-10
*Subject: Re: [PATCH v2 01/11] configfs-tsm: Namespace TSM report symbols*

On 3/3/25 11:14 PM, Dan Williams wrote:
> In preparation for new + common TSM (TEE Security Manager)
> infrastructure, namespace the TSM report symbols in tsm.h with an

Reviewed-by: Kuppuswamy Sathyanarayanan 
<sathyanarayanan.kuppuswamy@linux.intel.com>

>   Documentation/ABI/testing/configfs-tsm-report   |    0
>   MAINTAINERS                                     |    2 +

---

## [19] Sathyanarayanan Kuppuswamy — 2025-03-10
*Subject: Re: [PATCH v2 02/11] coco/guest: Move shared guest CC infrastructure
 to drivers/virt/coco/guest/*

On 3/3/25 11:14 PM, Dan Williams wrote:
> In preparation for creating a new drivers/virt/coco/host/ directory to
> house shared host driver infrastructure for confidential computing, move

Reviewed-by: Kuppuswamy Sathyanarayanan 
<sathyanarayanan.kuppuswamy@linux.intel.com>

>   MAINTAINERS                      |    2 +-
>   drivers/virt/coco/Kconfig        |    6 ++----

---

## [20] Huang, Kai — 2025-03-10
*Subject: Re: [PATCH v2 01/11] configfs-tsm: Namespace TSM report symbols*

On Mon, 2025-03-03 at 23:14 -0800, Dan Williams wrote:
> In preparation for new + common TSM (TEE Security Manager)
> infrastructure, namespace the TSM report symbols in tsm.h with an

Reviewed-by: Kai Huang <kai.huang@intel.com>

[...]

> -static const struct tsm_ops arm_cca_tsm_ops = {
> +static const struct tsm_report_ops arm_cca_tsm_ops = {
[...]

> -static struct tsm_ops sev_tsm_ops = {
> +static struct tsm_report_ops sev_tsm_report_ops = {
[...]

> -static const struct tsm_ops tdx_tsm_ops = {
> +static const struct tsm_report_ops tdx_tsm_ops = {
[...]

Nit:

Seems we can simplify 'sev_tsm_report_ops' to 'sev_tsm_ops' to make it
consistent with arm cca and TDX?  But I think it is out-of-scope of this patch
anyway.

---

## [21] Huang, Kai — 2025-03-10
*Subject: Re: [PATCH v2 02/11] coco/guest: Move shared guest CC infrastructure
 to drivers/virt/coco/guest/*

On Mon, 2025-03-03 at 23:14 -0800, Dan Williams wrote:
> In preparation for creating a new drivers/virt/coco/host/ directory to
> house shared host driver infrastructure for confidential computing, move

[...]

> diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
> index c3d07cfc087e..885c9ef4e9fc 100644

Would it make more sense to also move 'pkvm-guest', 'sev-guset', 'tdx-guest' and
'arm-cca-guest' under the new 'guest/'?

---

## [22] Aneesh Kumar K.V — 2025-03-11
*Subject: Re: [PATCH v2 04/11] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

Dan Williams <dan.j.williams@intel.com> writes:

.....

> +void pci_ide_init(struct pci_dev *pdev)
> +{

What is the purpose of the loop? Should it use the minimum value to
ensure we select the lowest supported value for all selective IDE
stream? I assume that, in practice, the number of address association
register blocks will be the same for all selective streams?

                 nr_ide_mem = min(nr_ide_mem, nr_assoc);

> +	}
> +


-aneesh

---

## [23] Alexey Kardashevskiy — 2025-03-11
*Subject: Re: [PATCH v2 04/11] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

On 11/3/25 16:46, Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

It is to be able to implement sel_ide_offset() as simple as:

offset = PCI_IDE_LINK_STREAM_0 + nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE +
stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);

as each stream can potentially have different "Number of Address 
Association Register Blocks" (which we do not want for some reason).

> Should it use the minimum value to
> ensure we select the lowest supported value for all selective IDE

This is what we are going to support now. Since this "Number of Address 
Association Register Blocks" thing is to be programmed on the rootport, 
it is probably a reasonable thing to expect from SOCs anyway. Thanks,


>                   nr_ide_mem = min(nr_ide_mem, nr_assoc);
>

---

## [24] Suzuki K Poulose — 2025-03-11
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Hi Dan

On 04/03/2025 07:15, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into

...

> +
> +static struct pci_ide_partner *to_settings(struct pci_dev *pdev, struct pci_ide *ide)

My (relatively old) compiler complains about this:

drivers/pci/ide.c: In function ‘to_settings’:
drivers/pci/ide.c:322:3: error: a label can only be part of a statement 
and a declaration is not a statement
   322 |   struct pci_dev *rp = pcie_find_root_port(ide->pdev);
       |   ^~~~~~

$ gcc -v
...
Target: aarch64-none-linux-gnu
...
gcc version 10.3.1 20210621 (GNU Toolchain for the A-profile 
Architecture 10.3-2021.07 (arm-10.29))

Works fine on a later version of the GCC (version 12.2)

The following hunk fixes the build for me.

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 0c72985e6a65..f6f4cb71307d 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -318,15 +318,16 @@ static struct pci_ide_partner *to_settings(struct 
pci_dev *pdev, struct pci_ide
                         return NULL;
                 }
                 return &ide->partner[PCI_IDE_EP];
-       case PCI_EXP_TYPE_ROOT_PORT:
+       case PCI_EXP_TYPE_ROOT_PORT: {
                 struct pci_dev *rp = pcie_find_root_port(ide->pdev);

-               if (pdev != pcie_find_root_port(ide->pdev)) {
+               if (pdev != rp) {
                         pci_warn_once(pdev, "setup expected Root Port: 
%s\n",
                                       pci_name(rp));
                         return NULL;
                 }
                 return &ide->partner[PCI_IDE_RP];
+       }


Suzuki

---

## [25] Suzuki K Poulose — 2025-03-11
*Subject: Re: [PATCH v2 06/11] samples/devsec: Introduce a PCI device-security*

Hi Dan,

I have been playing with this, and these changes kind of makes it work on arm64
and hopefully for others with CONFIG_PCI_DOMAINS_GENERIC.

The first patch is a build failure fix for my toolchain.

[RFC PATCH 0/3] samples: devsec: Add support for PCI_DOMAINS_GENERIC

# insmod devsec_common.ko
# insmod devsec_bus.ko
# insmod devsec_tsm.ko
# dmesg
[ 7817.297135] devsec_bus devsec_bus: PCI host bridge to bus 0001:00
[ 7817.297251] pci_bus 0001:00: root bus resource [bus 00-01]
[ 7817.297374] pci_bus 0001:00: root bus resource [mem 0xfffffff000000000-0xffffffffffffffff 64bit]
[ 7817.297653] pci 0001:00:00.0: [8086:7075] type 01 class 0x060400 PCIe Root Port
[ 7817.297856] pci 0001:00:00.0: PCI bridge to [bus 00]
[ 7817.297986] pci 0001:00:00.0:   bridge window [io  0x0000-0x0fff]
[ 7817.298115] pci 0001:00:00.0:   bridge window [mem 0x00000000-0x000fffff]
[ 7817.298267] pci 0001:00:00.0:   bridge window [mem 0x00000000-0x000fffff 64bit pref]
[ 7817.304866] pci 0001:00:00.0: bridge configuration invalid ([bus 00-00]), reconfiguring
[ 7817.305464] pci 0001:01:00.0: [8086:ffff] type 00 class 0x000000 PCIe Endpoint
[ 7817.305664] pci 0001:01:00.0: BAR 0 [mem 0x00000000-0x001fffff]
[ 7817.312503] pci 0001:01:00.0: disabling ASPM on pre-1.1 PCIe device.  You can enable it with 'pcie_aspm=force'
[ 7817.312714] pci_bus 0001:01: busn_res: [bus 01] end is updated to 01
# cd /sys/bus/pci/devices/0001\:01\:00.0/
# cat tsm/connect
0
# echo 1 > tsm/connect
# cat authenticated
1
# echo 0 > tsm/connect
# cat authenticated
0



Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: linux-pci@vger.kernel.org
Cc: linux-coco@lists.linux.dev

Suzuki K Poulose (3):
  pci: ide: Fix build failure
  pci: generic-domains: Add helpers to alloc/free dynamic bus numbers
  samples: devsec: Add support for PCI_DOMAINS_GENERIC

 drivers/pci/ide.c       |  5 +++--
 drivers/pci/pci.c       | 16 ++++++++++++++--
 include/linux/pci.h     |  3 +++
 samples/Kconfig         |  1 -
 samples/devsec/bus.c    | 32 +++++++++++++++++++++-----------
 samples/devsec/common.c |  2 +-
 samples/devsec/devsec.h |  2 +-
 7 files changed, 43 insertions(+), 18 deletions(-)

---

## [26] Suzuki K Poulose — 2025-03-11
*Subject: [RESEND RFC PATCH 1/3] pci: ide: Fix build failure*

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 drivers/pci/ide.c | 5 +++--
 1 file changed, 3 insertions(+), 2 deletions(-)

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 0c72985e6a65..f6f4cb71307d 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -318,15 +318,16 @@ static struct pci_ide_partner *to_settings(struct pci_dev *pdev, struct pci_ide
 			return NULL;
 		}
 		return &ide->partner[PCI_IDE_EP];
-	case PCI_EXP_TYPE_ROOT_PORT:
+	case PCI_EXP_TYPE_ROOT_PORT: {
 		struct pci_dev *rp = pcie_find_root_port(ide->pdev);
 
-		if (pdev != pcie_find_root_port(ide->pdev)) {
+		if (pdev != rp) {
 			pci_warn_once(pdev, "setup expected Root Port: %s\n",
 				      pci_name(rp));
 			return NULL;
 		}
 		return &ide->partner[PCI_IDE_RP];
+	}
 	default:
 		pci_warn_once(pdev, "invalid device type\n");
 		return NULL;

---

## [27] Suzuki K Poulose — 2025-03-11
*Subject: [RESEND RFC PATCH 2/3] pci: generic-domains: Add helpers to alloc/free dynamic bus numbers*

Add helpers to allocate/free useable PCI domain numbers at runtime.
This will be later used by sample devsec code.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 drivers/pci/pci.c   | 16 ++++++++++++++--
 include/linux/pci.h |  3 +++
 2 files changed, 17 insertions(+), 2 deletions(-)

diff --git a/drivers/pci/pci.c b/drivers/pci/pci.c
index 869d204a70a3..729bc57e025b 100644
--- a/drivers/pci/pci.c
+++ b/drivers/pci/pci.c
@@ -6685,6 +6685,18 @@ static void pci_no_domains(void)
 static DEFINE_IDA(pci_domain_nr_static_ida);
 static DEFINE_IDA(pci_domain_nr_dynamic_ida);
 
+int pci_alloc_dynamic_domain(void)
+{
+	return ida_alloc(&pci_domain_nr_dynamic_ida, GFP_KERNEL);
+}
+EXPORT_SYMBOL_GPL(pci_alloc_dynamic_domain);
+
+void pci_free_dynamic_domain(int domain)
+{
+	ida_free(&pci_domain_nr_dynamic_ida, domain);
+}
+EXPORT_SYMBOL_GPL(pci_free_dynamic_domain);
+
 static void of_pci_reserve_static_domain_nr(void)
 {
 	struct device_node *np;
@@ -6733,7 +6745,7 @@ static int of_pci_bus_find_domain_nr(struct device *parent)
 	 * dynamic allocations to prevent assigning them to other DT nodes
 	 * without static domain.
 	 */
-	return ida_alloc(&pci_domain_nr_dynamic_ida, GFP_KERNEL);
+	return pci_alloc_dynamic_domain();
 }
 
 static void of_pci_bus_release_domain_nr(struct device *parent, int domain_nr)
@@ -6745,7 +6757,7 @@ static void of_pci_bus_release_domain_nr(struct device *parent, int domain_nr)
 	if (of_get_pci_domain_nr(parent->of_node) == domain_nr)
 		ida_free(&pci_domain_nr_static_ida, domain_nr);
 	else
-		ida_free(&pci_domain_nr_dynamic_ida, domain_nr);
+		pci_free_dynamic_domain(domain_nr);
 }
 
 int pci_bus_find_domain_nr(struct pci_bus *bus, struct device *parent)
diff --git a/include/linux/pci.h b/include/linux/pci.h
index c2f18f31f7a7..c040c1d49632 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -1934,6 +1934,9 @@ static inline int acpi_pci_bus_find_domain_nr(struct pci_bus *bus)
 #endif
 int pci_bus_find_domain_nr(struct pci_bus *bus, struct device *parent);
 void pci_bus_release_domain_nr(struct device *parent, int domain_nr);
+int pci_alloc_dynamic_domain(void);
+void pci_free_dynamic_domain(int domain);
+
 #endif
 
 /* Some architectures require additional setup to direct VGA traffic */

---

## [28] Suzuki K Poulose — 2025-03-11
*Subject: [RESEND RFC PATCH 3/3] samples: devsec: Add support for PCI_DOMAINS_GENERIC*

Allocate/free a domain at runtime for the sample devsec TSM.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 samples/Kconfig         |  1 -
 samples/devsec/bus.c    | 32 +++++++++++++++++++++-----------
 samples/devsec/common.c |  2 +-
 samples/devsec/devsec.h |  2 +-
 4 files changed, 23 insertions(+), 14 deletions(-)

diff --git a/samples/Kconfig b/samples/Kconfig
index 6bd64fc54ac1..f23be5088b9e 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -308,7 +308,6 @@ config SAMPLE_DEVSEC
 	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
 	depends on PCI
 	depends on VIRT_DRIVERS
-	depends on X86 # TODO: PCI_DOMAINS_GENERIC support
 	select PCI_BRIDGE_EMUL
 	select PCI_TSM
 	select TSM
diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
index b78c04b21eb9..8ec04b3549f0 100644
--- a/samples/devsec/bus.c
+++ b/samples/devsec/bus.c
@@ -21,7 +21,7 @@
 #define NR_DEVSEC_DEVS 1
 
 struct devsec {
-	struct pci_sysdata sysdata;
+	int domain;
 	struct gen_pool *iomem_pool;
 	struct resource resource[2];
 	struct pci_bus *bus;
@@ -70,7 +70,7 @@ struct devsec {
 
 static struct devsec *bus_to_devsec(struct pci_bus *bus)
 {
-	return container_of(bus->sysdata, struct devsec, sysdata);
+	return container_of(bus->sysdata, struct devsec, domain);
 }
 
 static int devsec_dev_config_read(struct devsec *devsec, struct pci_bus *bus,
@@ -309,6 +309,17 @@ static struct pci_ops devsec_ops = {
 };
 
 /* borrowed from vmd_find_free_domain() */
+#ifdef CONFIG_PCI_GENERIC_DOMAINS
+static int find_free_domain(void)
+{
+	return pci_alloc_dynamic_domain();
+}
+
+static int release_domain(int domain)
+{
+	pci_free_dynamic_domain(domain);
+}
+#else
 static int find_free_domain(void)
 {
 	int domain = 0xffff;
@@ -318,13 +329,15 @@ static int find_free_domain(void)
 		domain = max_t(int, domain, pci_domain_nr(bus));
 	return domain + 1;
 }
-
+static void release_domain(int domain) {}
+#endif
 static void destroy_bus(void *data)
 {
 	struct devsec *devsec = data;
 
 	pci_stop_root_bus(devsec->bus);
 	pci_remove_root_bus(devsec->bus);
+	release_domain(devsec->domain);
 }
 
 static u32 build_ext_cap_header(u32 id, u32 ver, u32 next)
@@ -588,7 +601,6 @@ static int __init devsec_bus_probe(struct platform_device *pdev)
 	int rc;
 	LIST_HEAD(resources);
 	struct devsec *devsec;
-	struct pci_sysdata *sd;
 	u64 mmio_size = SZ_64G;
 	struct pci_host_bridge *hb;
 	struct device *dev = &pdev->dev;
@@ -633,15 +645,13 @@ static int __init devsec_bus_probe(struct platform_device *pdev)
 	};
 	pci_add_resource(&resources, &devsec->resource[1]);
 
-	sd = &devsec->sysdata;
-	devsec_sysdata = sd;
-	sd->domain = find_free_domain();
-	if (sd->domain < 0)
-		return sd->domain;
-
+	devsec_sysdata = &devsec->domain;
+	devsec->domain = find_free_domain();
+	if (devsec->domain < 0)
+		return devsec->domain;
 
 	devsec->bus = pci_create_root_bus(dev, 0, &devsec_ops,
-					  &devsec->sysdata, &resources);
+					  &devsec->domain, &resources);
 	if (!devsec->bus) {
 		pci_free_resource_list(&resources);
 		return -ENOMEM;
diff --git a/samples/devsec/common.c b/samples/devsec/common.c
index 9b6f4022f241..4da85b53b6a9 100644
--- a/samples/devsec/common.c
+++ b/samples/devsec/common.c
@@ -8,7 +8,7 @@
  * devsec_bus and devsec_tsm need a common location for this data to
  * avoid depending on each other. Enables load order testing
  */
-struct pci_sysdata *devsec_sysdata;
+void *devsec_sysdata;
 EXPORT_SYMBOL_GPL(devsec_sysdata);
 
 static int __init common_init(void)
diff --git a/samples/devsec/devsec.h b/samples/devsec/devsec.h
index 794a9898ee2d..496020c9cb6d 100644
--- a/samples/devsec/devsec.h
+++ b/samples/devsec/devsec.h
@@ -3,5 +3,5 @@
 
 #ifndef __DEVSEC_H__
 #define __DEVSEC_H__
-extern struct pci_sysdata *devsec_sysdata;
+extern void *devsec_sysdata;
 #endif /* __DEVSEC_H__ */

---

## [29] Alexey Kardashevskiy — 2025-03-18
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

On 4/3/25 18:15, Dan Williams wrote:
> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into


PCIe 6.1-1.0 provides an example at "Figure 6-62 IDE_KM Example":
===
Host and Device are configured with credentials for authentication.
System Firmware/Software programs, in both Ports, the IDE Extended 
Capability for the Stream to be established.
...
SPDM VENDOR_DEFINED_REQUEST (IDE_KM K_SET_GO(Tx))
SPDM VENDOR_DEFINED_RESPONSE (IDE_KM K_GOSTOP_ACK) 3 times
...
System Software / Firmware sets the Enable bit and IDE is established
===

1. write to the IDE stream cap everything except "enabled".
2. program the keys into the device.
3. write "enable" to the IDE stream cap.

Doing it in one go as you suggest works with one of my devices but not 
the other.

And to make things "clear", the spec also says:
===
It is strongly recommended to complete key programming for a Stream 
before Setting the Enable bit in the IDE Extended Capability entry for 
that Stream.
◦ It is permitted, but strongly not recommended, to Set the Enable bit 
in the IDE Extended Capability entry for a Stream prior to the 
completion of key programming for that Stream
====

So are we going to do "permitted" or not "not recommended" (== 
recommended)? Thanks,


> +
> +/**

---

## [30] Aneesh Kumar K.V — 2025-04-16
*Subject: Re: [PATCH v2 05/11] PCI/TSM: Authenticate devices via platform TSM*

Dan Williams <dan.j.williams@intel.com> writes:

....

> diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
> new file mode 100644

While working with a multifunction device, I found that adding lock and
state to struct pci_tsm simplified the code considerably.

In multifunction setups, it’s possible that multiple functions may
expose DOE capabilities. In this case, when sending SPDM messages for a
TDI, should we always use the DOE mailbox of function 0, or should we
address the mailbox of the specific function involved?

If the latter is preferred, would it make sense to rename the current
structure—currently representing the base pci_tsm plus the DOE
mailbox—to something more generic? because it is not more tied to
physical function 0

> +
> +static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)

---

## [31] Dan Williams — 2025-04-18
*Subject: Re: [PATCH v2 02/11] coco/guest: Move shared guest CC infrastructure
 to drivers/virt/coco/guest/*

Huang, Kai wrote:
> On Mon, 2025-03-03 at 23:14 -0800, Dan Williams wrote:
> > In preparation for creating a new drivers/virt/coco/host/ directory to

If folks want that. The main motivation is that common infrastructure
for the host side should live in a separate directory from common
infrastructure for the guest side, but for now I will live the
vendor-specific guest directories alone.

---

## [32] Dan Williams — 2025-04-19
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Suzuki K Poulose wrote:
[..]
> My (relatively old) compiler complains about this:
> 

Looks good to me, I have folded this in.

---

## [33] Dan Williams — 2025-04-20
*Subject: Re: [RESEND RFC PATCH 3/3] samples: devsec: Add support for
 PCI_DOMAINS_GENERIC*

Suzuki K Poulose wrote:
> Allocate/free a domain at runtime for the sample devsec TSM.
> 

The config symbol name is PCI_DOMAINS_GENERIC, so the only way I can see
this patch working is if you have ACPI=n in your build? See below.

> +static int find_free_domain(void)
> +{

See pci_register_host_bridge()... I don't think this works unless you
have CONFIG_ACPI=n to avoid trying to lookup the non-existent ACPI
device associated with this fake bridge.

I think the path here is to make emulated host bridges a first-class
citizen of the PCI core.

The below seems to work. It adds a new pci_bus_find_emul_domain_nr() to
unify a few cases where PCI domain host-bridges are being emulated, and
it allows to the emulated domain_nr to be established between
pci_alloc_host_bridge() and pci_register_host_bridge(). It still needs
to play pci_sysdata hiding games for now:

-- 8< --
diff --git a/drivers/pci/controller/vmd.c b/drivers/pci/controller/vmd.c
index 8df064b62a2f..efef329c359a 100644
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
@@ -866,7 +850,7 @@ static int vmd_enable_domain(struct vmd_dev *vmd, unsigned long features)
 	};
 
 	sd->vmd_dev = vmd->dev;
-	sd->domain = vmd_find_free_domain();
+	sd->domain = pci_bus_find_emul_domain_nr();
 	if (sd->domain < 0)
 		return sd->domain;
 
diff --git a/drivers/pci/pci.c b/drivers/pci/pci.c
index 4d7c9f64ea24..0d5a08583197 100644
--- a/drivers/pci/pci.c
+++ b/drivers/pci/pci.c
@@ -6774,7 +6774,7 @@ static void of_pci_bus_release_domain_nr(struct device *parent, int domain_nr)
 		return;
 
 	/* Release domain from IDA where it was allocated. */
-	if (of_get_pci_domain_nr(parent->of_node) == domain_nr)
+	if (parent && of_get_pci_domain_nr(parent->of_node) == domain_nr)
 		ida_free(&pci_domain_nr_static_ida, domain_nr);
 	else
 		ida_free(&pci_domain_nr_dynamic_ida, domain_nr);
@@ -6794,6 +6794,42 @@ void pci_bus_release_domain_nr(struct device *parent, int domain_nr)
 }
 #endif
 
+/*
+ * Find a free domain_nr either allocated by of_pci_bus_find_domain_nr()
+ * or fallback to the first free domain number above the last ACPI
+ * segment number, do not ask acpi_pci_bus_find_domain_nr() it has no
+ * information about emulated host bridges
+ */
+int pci_bus_find_emul_domain_nr(void)
+{
+	/*
+	 * Emulated domains start at 0x10000 to not clash with ACPI _SEG
+	 * domains.  Per ACPI r6.0, sec 6.5.6,  _SEG returns an integer, of
+	 * which the lower 16 bits are the PCI Segment Group (domain) number.
+	 * Other bits are currently reserved.
+	 */
+	int domain = 0xffff;
+	struct pci_bus *bus = NULL;
+
+#ifdef CONFIG_PCI_DOMAINS_GENERIC
+	if (acpi_disabled)
+		return of_pci_bus_find_domain_nr(NULL);
+#endif
+
+	while ((bus = pci_find_next_bus(bus)) != NULL)
+		domain = max_t(int, domain, pci_domain_nr(bus));
+	return domain + 1;
+}
+EXPORT_SYMBOL_GPL(pci_bus_find_emul_domain_nr);
+
+void pci_bus_release_emul_domain_nr(int domain_nr)
+{
+#ifdef CONFIG_PCI_DOMAINS_GENERIC
+	/* Note that in the in the ACPI emulation case this is a nop */
+	pci_bus_release_domain_nr(NULL, domain_nr);
+#endif
+}
+
 /**
  * pci_ext_cfg_avail - can we access extended PCI config space?
  *
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index c090289b70be..1e65692efc0a 100644
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
 
@@ -949,7 +954,7 @@ static bool pci_preserve_config(struct pci_host_bridge *host_bridge)
 	return false;
 }
 
-static int pci_register_host_bridge(struct pci_host_bridge *bridge)
+int pci_register_host_bridge(struct pci_host_bridge *bridge)
 {
 	struct device *parent = bridge->dev.parent;
 	struct resource_entry *window, *next, *n;
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
@@ -1121,6 +1127,7 @@ static int pci_register_host_bridge(struct pci_host_bridge *bridge)
 
 	return err;
 }
+EXPORT_SYMBOL_GPL(pci_register_host_bridge);
 
 static bool pci_bridge_child_ext_cfg_accessible(struct pci_dev *bridge)
 {
@@ -3176,6 +3183,22 @@ void __weak pcibios_remove_bus(struct pci_bus *bus)
 {
 }
 
+void pci_setup_host_bridge(struct pci_host_bridge *bridge,
+			   struct device *parent, int bus, struct pci_ops *ops,
+			   void *sysdata, struct list_head *resources,
+			   int domain_nr)
+{
+	WARN_ON(device_is_registered(&bridge->dev));
+	bridge->dev.parent = parent;
+
+	list_splice_init(resources, &bridge->windows);
+	bridge->sysdata = sysdata;
+	bridge->busnr = bus;
+	bridge->ops = ops;
+	bridge->domain_nr = domain_nr;
+}
+EXPORT_SYMBOL_GPL(pci_setup_host_bridge);
+
 struct pci_bus *pci_create_root_bus(struct device *parent, int bus,
 		struct pci_ops *ops, void *sysdata, struct list_head *resources)
 {
@@ -3186,12 +3209,8 @@ struct pci_bus *pci_create_root_bus(struct device *parent, int bus,
 	if (!bridge)
 		return NULL;
 
-	bridge->dev.parent = parent;
-
-	list_splice_init(resources, &bridge->windows);
-	bridge->sysdata = sysdata;
-	bridge->busnr = bus;
-	bridge->ops = ops;
+	pci_setup_host_bridge(bridge, parent, bus, ops, sysdata, resources,
+			      PCI_DOMAIN_NR_NOT_SET);
 
 	error = pci_register_host_bridge(bridge);
 	if (error < 0)
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 72d07ad994fa..f3bed5462279 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -1165,6 +1165,11 @@ struct pci_bus *pci_scan_bus(int bus, struct pci_ops *ops, void *sysdata);
 struct pci_bus *pci_create_root_bus(struct device *parent, int bus,
 				    struct pci_ops *ops, void *sysdata,
 				    struct list_head *resources);
+void pci_setup_host_bridge(struct pci_host_bridge *bridge,
+			   struct device *parent, int bus, struct pci_ops *ops,
+			   void *sysdata, struct list_head *resources,
+			   int domain_nr);
+int pci_register_host_bridge(struct pci_host_bridge *bridge);
 int pci_host_probe(struct pci_host_bridge *bridge);
 int pci_bus_insert_busn_res(struct pci_bus *b, int bus, int busmax);
 int pci_bus_update_busn_res_end(struct pci_bus *b, int busmax);
@@ -1919,6 +1924,8 @@ static inline int acpi_pci_bus_find_domain_nr(struct pci_bus *bus)
 int pci_bus_find_domain_nr(struct pci_bus *bus, struct device *parent);
 void pci_bus_release_domain_nr(struct device *parent, int domain_nr);
 #endif
+int pci_bus_find_emul_domain_nr(void);
+void pci_bus_release_emul_domain_nr(int domain_nr);
 
 /* Some architectures require additional setup to direct VGA traffic */
 typedef int (*arch_set_vga_state_t)(struct pci_dev *pdev, bool decode,
diff --git a/samples/Kconfig b/samples/Kconfig
index 6d6aeb736c8f..523a7129aed3 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -317,7 +317,7 @@ config SAMPLE_DEVSEC
 	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
 	depends on PCI
 	depends on VIRT_DRIVERS
-	depends on X86 # TODO: PCI_DOMAINS_GENERIC support
+	depends on PCI_DOMAINS_GENERIC || X86
 	select PCI_BRIDGE_EMUL
 	select PCI_TSM
 	select TSM
diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
index 69117db10897..0ca8acaf2204 100644
--- a/samples/devsec/bus.c
+++ b/samples/devsec/bus.c
@@ -20,7 +20,7 @@
 #define NR_DEVSEC_DEVS 1
 
 struct devsec {
-	struct pci_sysdata sysdata;
+	struct devsec_sysdata sysdata;
 	struct gen_pool *iomem_pool;
 	struct resource resource[2];
 	struct pci_bus *bus;
@@ -307,17 +307,6 @@ static struct pci_ops devsec_ops = {
 	.write = devsec_pci_write,
 };
 
-/* borrowed from vmd_find_free_domain() */
-static int find_free_domain(void)
-{
-	int domain = 0xffff;
-	struct pci_bus *bus = NULL;
-
-	while ((bus = pci_find_next_bus(bus)) != NULL)
-		domain = max_t(int, domain, pci_domain_nr(bus));
-	return domain + 1;
-}
-
 static void destroy_bus(void *data)
 {
 	struct devsec *devsec = data;
@@ -582,12 +571,60 @@ static int alloc_ports(struct devsec *devsec)
 	return 0;
 }
 
+static struct list_head *devsec_add_resources(struct devsec *devsec,
+					      struct list_head *resources,
+					      u64 mmio_start, u64 mmio_size)
+{
+	devsec->resource[0] = (struct resource) {
+		.name = "DEVSEC BUSES",
+		.start = 0,
+		.end = NR_DEVSEC_BUSES + NR_DEVSEC_ROOT_PORTS - 1,
+		.flags = IORESOURCE_BUS | IORESOURCE_PCI_FIXED,
+	};
+	pci_add_resource(resources, &devsec->resource[0]);
+
+	devsec->resource[1] = (struct resource) {
+		.name = "DEVSEC MMIO",
+		.start = mmio_start,
+		.end = mmio_start + mmio_size - 1,
+		.flags = IORESOURCE_MEM | IORESOURCE_MEM_64,
+	};
+	pci_add_resource(resources, &devsec->resource[1]);
+
+	return resources;
+}
+
+static int devsec_autofree_bus(struct devsec *devsec, struct pci_bus *bus,
+			       struct list_head *resources)
+{
+	devsec->bus = bus;
+	return devm_add_action_or_reset(devsec->dev, destroy_bus, devsec);
+}
+
+static int *devsec_alloc_domain_nr(int *domain_nr)
+{
+	*domain_nr = pci_bus_find_emul_domain_nr();
+	if (*domain_nr < 0)
+		return NULL;
+	return domain_nr;
+}
+
+static void devsec_free_domain_nr(int *domain_nr)
+{
+	if (domain_nr)
+		pci_bus_release_emul_domain_nr(*domain_nr);
+}
+
+DEFINE_FREE(free_resource_list, struct list_head *, if (_T) pci_free_resource_list(_T))
+DEFINE_FREE(free_bridge, struct pci_host_bridge *, if (_T) put_device(&_T->dev));
+DEFINE_FREE(free_domain_nr, int *, if (_T) devsec_free_domain_nr(_T))
+
 static int __init devsec_bus_probe(struct platform_device *pdev)
 {
-	int rc;
-	LIST_HEAD(resources);
+	int rc, __domain_nr;
+	LIST_HEAD(__resources);
 	struct devsec *devsec;
-	struct pci_sysdata *sd;
+	struct devsec_sysdata *sd;
 	u64 mmio_size = SZ_64G;
 	struct device *dev = &pdev->dev;
 	u64 mmio_start = iomem_resource.end + 1 - SZ_64G;
@@ -615,37 +652,34 @@ static int __init devsec_bus_probe(struct platform_device *pdev)
 	if (rc)
 		return rc;
 
-	devsec->resource[0] = (struct resource) {
-		.name = "DEVSEC BUSES",
-		.start = 0,
-		.end = NR_DEVSEC_BUSES + NR_DEVSEC_ROOT_PORTS - 1,
-		.flags = IORESOURCE_BUS | IORESOURCE_PCI_FIXED,
-	};
-	pci_add_resource(&resources, &devsec->resource[0]);
+	struct list_head *resources __free(free_resource_list) =
+		devsec_add_resources(devsec, &__resources, mmio_start,
+				     mmio_size);
 
-	devsec->resource[1] = (struct resource) {
-		.name = "DEVSEC MMIO",
-		.start = mmio_start,
-		.end = mmio_start + mmio_size - 1,
-		.flags = IORESOURCE_MEM | IORESOURCE_MEM_64,
-	};
-	pci_add_resource(&resources, &devsec->resource[1]);
+	struct pci_host_bridge *hb __free(free_bridge) = pci_alloc_host_bridge(0);
+	if (!hb)
+		return -ENOMEM;
 
 	sd = &devsec->sysdata;
 	devsec_sysdata = sd;
-	sd->domain = find_free_domain();
-	if (sd->domain < 0)
-		return sd->domain;
-
-
-	devsec->bus = pci_create_root_bus(dev, 0, &devsec_ops,
-					  &devsec->sysdata, &resources);
-	if (!devsec->bus) {
-		pci_free_resource_list(&resources);
-		return -ENOMEM;
-	}
+	int *domain_nr __free(free_domain_nr) = devsec_alloc_domain_nr(&__domain_nr);
+	if (!domain_nr)
+		return __domain_nr;
+
+	/*
+	 * Note, domain_nr is set in devsec_sysdata for
+	 * !CONFIG_PCI_DOMAINS_GENERIC platforms
+	 */
+	devsec_set_domain_nr(sd, *no_free_ptr(domain_nr));
+	pci_setup_host_bridge(hb, dev, 0, &devsec_ops, &devsec->sysdata,
+			      resources, devsec_get_domain_nr(sd));
+
+	rc = pci_register_host_bridge(hb);
+	if (rc)
+		return rc;
 
-	rc = devm_add_action_or_reset(dev, destroy_bus, devsec);
+	rc = devsec_autofree_bus(devsec, no_free_ptr(hb)->bus,
+				 no_free_ptr(resources));
 	if (rc)
 		return rc;
 
diff --git a/samples/devsec/devsec.h b/samples/devsec/devsec.h
index 794a9898ee2d..64e35731325b 100644
--- a/samples/devsec/devsec.h
+++ b/samples/devsec/devsec.h
@@ -3,5 +3,38 @@
 
 #ifndef __DEVSEC_H__
 #define __DEVSEC_H__
-extern struct pci_sysdata *devsec_sysdata;
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
 #endif /* __DEVSEC_H__ */

---

## [34] Aneesh Kumar K.V — 2025-04-21
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Dan Williams <dan.j.williams@intel.com> writes:

> There are two components to establishing an encrypted link, provisioning
> the stream in Partner Port config-space, and programming the keys into
....

> +/**
> + * pci_ide_stream_setup() - program settings to Selective IDE Stream registers

This and the similar offset caclulation below needs the EXT_CAP_ID_IDE offset 

modified   drivers/pci/ide.c
@@ -10,11 +10,13 @@
 #include <linux/bitfield.h>
 #include "pci.h"
 
-static int sel_ide_offset(int nr_link_ide, int stream_index, int nr_ide_mem)
+static int sel_ide_offset(struct pci_dev *pdev, int nr_link_ide,
+			  int stream_index, int nr_ide_mem)
 {
 	int offset;
 
-	offset = PCI_IDE_LINK_STREAM_0 + nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE;
+	offset = pci_find_ext_capability(pdev, PCI_EXT_CAP_ID_IDE);
+	offset += PCI_IDE_LINK_STREAM_0 + nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE;
 
 	/*
 	 * Assume a constant number of address association resources per
@@ -66,7 +68,7 @@ void pci_ide_init(struct pci_dev *pdev)
 	nr_streams = min(1 + FIELD_GET(PCI_IDE_CAP_SEL_NUM_MASK, val),
 			 CONFIG_PCI_IDE_STREAM_MAX);
 	for (int i = 0; i < nr_streams; i++) {
-		int offset = sel_ide_offset(nr_link_ide, i, nr_ide_mem);
+		int offset = sel_ide_offset(pdev, nr_link_ide, i, nr_ide_mem);
 		int nr_assoc;
 		u32 val;
 
@@ -352,8 +354,7 @@ void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 
 	if (!settings)
 		return;
-
-	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+	pos = sel_ide_offset(pdev, pdev->nr_link_ide, settings->stream_index,
 			     pdev->nr_ide_mem);
 
 	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT_MASK, settings->rid_end);
@@ -381,7 +382,7 @@ void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
 	if (!settings)
 		return;
 
-	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+	pos = sel_ide_offset(pdev, pdev->nr_link_ide, settings->stream_index,
 			     pdev->nr_ide_mem);
 
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
@@ -406,7 +407,7 @@ void pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide)
 	if (!settings)
 		return;
 
-	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+	pos = sel_ide_offset(pdev, pdev->nr_link_ide, settings->stream_index,
 			     pdev->nr_ide_mem);
 
 	val = FIELD_PREP(PCI_IDE_SEL_CTL_ID_MASK, ide->stream_id) |
@@ -434,7 +435,7 @@ void pci_ide_stream_disable(struct pci_dev *pdev, struct pci_ide *ide)
 	if (!settings)
 		return;
 
-	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
+	pos = sel_ide_offset(pdev, pdev->nr_link_ide, settings->stream_index,
 			     pdev->nr_ide_mem);
 
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);



> +
> +	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT_MASK, settings->rid_end);

....

> +/**
> + * pci_ide_stream_enable() - after setup, enable the stream

Does enabling pdev->ide_tee_limit here will prevent a device from operating 
as expected before we get to TDISP RUN state? 

TEE-Limited Stream – When Set, requires that, for Requests, only those that have the T bit Set are
permitted to be associated with this Stream


> +	      FIELD_PREP(PCI_IDE_SEL_CTL_EN, 1);
> +	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);

here

> +
> +	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);


-aneesh

---

## [35] Suzuki K Poulose — 2025-04-22
*Subject: Re: [RESEND RFC PATCH 3/3] samples: devsec: Add support for
 PCI_DOMAINS_GENERIC*

Hi Dan

On 20/04/2025 19:29, Dan Williams wrote:
> Suzuki K Poulose wrote:
>> Allocate/free a domain at runtime for the sample devsec TSM.

You're right. But I did have ACPI=y, but built it for only arm64 (but 
only booted with DT).

>> @@ -633,15 +645,13 @@ static int __init devsec_bus_probe(struct platform_device *pdev)
>>   	};

I have tested this on arm64 (Juno board) with ACPI and DT and it works*

I have spotted a crash with an unrelated bug in the GICv2M driver, with
ACPI. I will send out a fix for that.

Thanks for reworking the patch !

FWIW:

Tested-by: Suzuki K Poulose <suzuki.poulose@arm.com> # on Arm64

Suzuki


> 
> -- 8< --

---

## [36] Xu Yilun — 2025-04-26
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

On Mon, Apr 21, 2025 at 11:43:58AM +0530, Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

ide_cap, nr_link_ide, nr_ide_mem are all cached in pci_dev structure at
the end of pci_ide_init().

So either use all cached value in pdev (not for pci_ide_init()):

  static int sel_ide_offset(struct pci_dev *pdev, int stream_index)

or don't use any cached value:

  static int sel_ide_offset(u16 dev_cap, int nr_link_ide, int stream_index, int nr_ide_mem)

or keep sel_ide_offset() unchanged, alway do:

  ide_cap + sel_ide_offset()

>  
>  	/*

With your change, the next line will be broken:

-		pci_read_config_dword(pdev, ide_cap + offset, &val);
+		pci_read_config_dword(pdev, offset, &val);

Thanks,
Yilun

---

## [37] Dan Williams — 2025-04-25
*Subject: Re: [PATCH v2 09/11] PCI/IDE: Report available IDE streams*

Dionna Amalie Glaze wrote:
> On Mon, Mar 3, 2025 at 11:20 PM Dan Williams <dan.j.williams@intel.com> wrote:
> >

Whoops, surprised checkpatch did not flag that.

> 
> >                 (RO) When a platform has established a secure connection, PCIe

I went ahead and folded the below into the preceding patch, and will add
another "See /sys/devices/pciDDDD:BB entry..." note.

diff --git a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
index 51dc9eed9353..8ea48b7aa996 100644
--- a/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
+++ b/Documentation/ABI/testing/sysfs-devices-pci-host-bridge
@@ -5,8 +5,10 @@ Contact:	linux-pci@vger.kernel.org
 Description:
 		A PCI host bridge device parents a PCI bus device topology. PCI
 		controllers may also parent host bridges. The DDDD:BB format
-		conveys the PCI domain number and root bus number of the
-		host bridge.
+		conveys the PCI domain number and root bus number (in
+		hexadecimal) of the host bridge. Note that the domain number may
+		be larger than the 16-bits that the "DDDD" format implies for
+		emulated host-bridges.
 
 What:		pciDDDD:BB/firmware_node
 Date:		December, 2024
@@ -14,7 +16,9 @@ Contact:	linux-pci@vger.kernel.org
 Description:
 		(RO) Symlink to the platform firmware device object "companion"
 		of the host bridge. For example, an ACPI device with an _HID of
-		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00).
+		PNP0A08 (/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00). See
+		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
+		format.
 
 What:		pciDDDD:BB/streamH.R.E:DDDD:BB:DD:F
 Date:		December, 2024
@@ -29,4 +33,6 @@ Description:
 		bus:BB device:DD function:F. Where R and E represent the
 		assigned Selective IDE Stream Register Block in the Root Port
 		and Endpoint, and H represents a platform specific pool of
-		stream resources shared by the Root Ports in a host bridge.
+		stream resources shared by the Root Ports in a host bridge.  See
+		/sys/devices/pciDDDD:BB entry for details about the DDDD:BB
+		format.

> > diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> > index b2091f6260e6..0c72985e6a65 100644

Fixed.

> > + * @hb: host bridge boundary for the stream pool
> > + * @nr: number of streams

Good point, it should.

> > + *
> > + * The "PCI_IDE" symbol namespace is required because this is typically

Updated it to:

@@ -480,17 +490,18 @@ struct attribute_group pci_ide_attr_group = {
 };
 
 /**
- * pci_ide_init_nr_streams() - size the pool of IDE Stream resources
+ * pci_ide_init_nr_streams() - sets size of the pool of IDE Stream resources
  * @hb: host bridge boundary for the stream pool
  * @nr: number of streams
  *
- * Enable IDE Stream establishment by setting the number of stream
- * resources available at the host bridge. Platform init code must set
- * this before the first pci_ide_stream_alloc() call.
+ * Platform PCI init and/or expert test module use only. Enable IDE
+ * Stream establishment by setting the number of stream resources
+ * available at the host bridge. Platform init code must set this before
+ * the first pci_ide_stream_alloc() call.
  *
  * The "PCI_IDE" symbol namespace is required because this is typically
- * a detail that is settled in early PCI init, i.e. only an expert or
- * test module should consume this export.
+ * a detail that is settled in early PCI init. I.e. this export is not
+ * for endpoint drivers.
  */

Thanks for the fixup suggestions.

---

## [38] Dan Williams — 2025-04-25
*Subject: Re: [PATCH v2 04/11] PCI/IDE: Enumerate Selective Stream IDE
 capabilities*

Alexey Kardashevskiy wrote:
> On 11/3/25 16:46, Aneesh Kumar K.V wrote:
> > Dan Williams <dan.j.williams@intel.com> writes:
[..]
> >> +		nr_ide_mem = nr_assoc;
> >>

The cost to spec writers of allowing more degrees of freedom is zero.
The cost of supporting it in system-software is non-zero.

It is useful to test that implementations have a practical need to
maximize their complexity. That testing serves 2 purposes, it either
stops the complexity from being realized, or otherwise puts the burden
on the vendor who thinks they need that to come back and fixup the
implementation.

Meanwhile we get the relief of living in a slightly less complicated
world, if only for a moment.

---

## [39] Dan Williams — 2025-04-25
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Alexey Kardashevskiy wrote:
[..]
> Doing it in one go as you suggest works with one of my devices but not 
> the other.

So the spec is only talking about the key programming not the control
register, but if a device wants the control register to have everything
but "enable" set, that seems reasonable to me. Does this work for that
device?

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 2b5295615a3a..4657138d3a7a 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -344,6 +344,18 @@ static struct pci_ide_partner *to_settings(struct pci_dev *pdev, struct pci_ide
 	}
 }
 
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
 /**
  * pci_ide_stream_setup() - program settings to Selective IDE Stream registers
  * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
@@ -371,6 +383,12 @@ void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 
 	val = PREP_PCI_IDE_SEL_RID_2(settings->rid_start, ide_domain(pdev));
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
+
+	/*
+	 * Setup control register early for devices that expect
+	 * stream_id is set during key programming.
+	 */
+	set_ide_sel_ctl(pdev, ide, pos, false);
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_setup);
 
@@ -411,7 +429,6 @@ void pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide)
 {
 	struct pci_ide_partner *settings = to_settings(pdev, ide);
 	int pos;
-	u32 val;
 
 	if (!settings)
 		return;
@@ -419,12 +436,7 @@ void pci_ide_stream_enable(struct pci_dev *pdev, struct pci_ide *ide)
 	pos = sel_ide_offset(pdev->nr_link_ide, settings->stream_index,
 			     pdev->nr_ide_mem);
 
-	val = FIELD_PREP(PCI_IDE_SEL_CTL_ID_MASK, ide->stream_id) |
-	      FIELD_PREP(PCI_IDE_SEL_CTL_DEFAULT, 1) |
-	      FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, pdev->ide_cfg) |
-	      FIELD_PREP(PCI_IDE_SEL_CTL_TEE_LIMITED, pdev->ide_tee_limit) |
-	      FIELD_PREP(PCI_IDE_SEL_CTL_EN, 1);
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
+	set_ide_sel_ctl(pdev, ide, pos, true);
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_enable);

---

## [40] Dan Williams — 2025-04-25
*Subject: Re: [PATCH v2 05/11] PCI/TSM: Authenticate devices via platform TSM*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
[..]
> > +/**
> > + * struct pci_tsm_pf0 - Physical Function 0 TDISP context

Just wanted to circle back on list for this discussion we had off-list.
Specifically, that even for a multi-function device the SPDM session and
IDE setup belongs with physical-function-0 (per PCIe 6.2 11.2.2). So is
it really the case that Linux needs to contend with non-0 functions for
IDE_KM and TDISP?

---

## [41] Dan Williams — 2025-04-25
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

*facepalm*

So it seems no one is trying to build on top of this framework yet.

> 
> modified   drivers/pci/ide.c

Will fix this up to the following since ide_cap is already cached:

static int __sel_ide_offset(int ide_cap, int nr_link_ide, int stream_index,
                            int nr_ide_mem)
{
        int offset;
        
        offset = ide_cap + PCI_IDE_LINK_STREAM_0 + nr_link_ide * PCI_IDE_LINK_BLOCK_SIZE;
        
        /*
         * Assume a constant number of address association resources per
         * stream index
         */
        if (stream_index > 0)
                offset += stream_index * PCI_IDE_SEL_BLOCK_SIZE(nr_ide_mem);
        return offset;
}

static int sel_ide_offset(struct pci_dev *pdev,
                          struct pci_ide_partner *settings)
{
        return sel_ide_offset(pdev->ide_cap, pdev->nr_link_ide,
                              settings->stream_index, pdev->nr_ide_mem);
}

[..]
> > +/**
> > + * pci_ide_stream_enable() - after setup, enable the stream

My expectation is that non-IDE TLPs can always be sent. I.e. a TDISP
device outside the RUN state should still be operational without needing
to send T=0 traffic over the IDE stream.

---

## [42] Aneesh Kumar K.V — 2025-04-27
*Subject: Re: [PATCH v2 08/11] PCI/IDE: Add IDE establishment helpers*

Dan Williams <dan.j.williams@intel.com> writes:

> Aneesh Kumar K.V wrote:
>> Dan Williams <dan.j.williams@intel.com> writes:

You can find my POC work with this framework at
https://gitlab.arm.com/linux-arm/linux-cca/-/tree/cca-1.1/da/proto/rmm-1.1-alp12/v1
. I'm still reworking the patches, so I haven't posted them to the
mailing list yet.

-aneesh

---

## [43] Zhi Wang — 2025-05-07
*Subject: Re: [PATCH v2 00/11] PCI/TSM: Core infrastructure for PCI device
 security (TDISP)*

On Mon, 03 Mar 2025 23:14:14 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

Hi Dan,

Thanks for the patches!

I tested this patch series along with the example devices you provided,
and it works well. The current design and interface reflect the outcomes
of our numerous discussions during kernel SIG meetings with Gobi and
our brainstorm sessions at tech summits.

From my perspective, it should fit most modern TDISP devices, such as
GPUs and other accelerators, although the TDI bind interfaces are
still under discussion.

It's great to see this patch series progressing from the early RFC stage
to a formal merge request, definitely a significant step for bringing
TDISP support is in the mainline and benefits end-users.

It would be helpful if a minimal (my gut feeling would be it could be
very much basically functional, e.g. support one device and one IDE
stream, no advanced features) Intel TSM driver could be added later. So
that we can validate this framework basically on the Intel platform, and
confidently gives an Acked-by:

Z.

> Changes since v1 [1]:
>  - [configfs-tsm: Namespace TSM report symbols]

---
