---
title: '[RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO'
date: 2024-08-23
last_reply: 2024-09-25
message_count: 128
participants: ['Alexey Kardashevskiy', 'Bjorn Helgaas', 'Tian, Kevin', 'Jason Gunthorpe', 'Jason Gunthorpe', 'Jonathan Cameron', 'Dan Williams', 'Xu Yilun', 'Aneesh Kumar K.V', 'Sean Christopherson', 'Zhi Wang', 'Zhi Wang', 'Vishal Annapurve']
---

## [1] Alexey Kardashevskiy — 2024-08-23

Hi everyone,

Here are some patches to enable SEV-TIO (aka TDISP, aka secure VFIO)
on AMD Turin.

The basic idea is to allow DMA to/from encrypted memory of SNP VMs and
secure MMIO in SNP VMs (i.e. with Cbit set) as well.

These include both guest and host support. QEMU also requires
some patches, links below.

The patches are organized as:
01..06 - preparing the host OS;
07 - new TSM module;
08 - add PSP SEV TIO ABI (IDE should start working at this point);
09..14 - add KVM support (TDI binding, MMIO faulting, etc);
15..19 - guest changes (the rest of SEV TIO ABI, DMA, secure MMIO).
20, 21 - some helpers for guest OS to use encrypted MMIO

This is based on a merge of
ee3248f9f8d6 Lukas Wunner spdm: Allow control of next requester nonce
through sysfs
85ef1ac03941 (AMDESE/snp-host-latest) 4 days ago Michael Roth [TEMP] KVM: guest_memfd: Update gmem_prep are hook to handle partially-allocated folios


Please comment. Thanks.

Thanks,


SEV TIO tree prototype
======================

Goal
----

Support secure PCI devices pass through to confidential VMs.
The support is defined by PCIe 6, SPDM, TDISP (not AMD) and SEV TIO
specification (by AMD).

SEV TIO spec:
https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58271_0_70.pdf
Whitepaper:
https://www.amd.com/content/dam/amd/en/documents/epyc-business-docs/white-papers/sev-tio-whitepaper.pdf
GHCB spec update is coming.

The changeset adds:
- a generic TSM.ko module;
makes necessary changes to:
- ccp (interface to AMD secure platform processor, "PSP", works on the
host),
- sev-guest (interace to PSP for confidential SNP guest),
- kvm_amd,
- memfd,
- vfio kvm device,
- kvm-x86.

Acronyms
--------

TEE - Trusted Execution Environments, a concept of managing trust
between the host
and devices
TSM - TEE Security Manager (TSM), an entity which ensures
security on the host
PSP - AMD platform secure processor (also "ASP", "AMD-SP"), acts
as TSM on AMD.
SEV TIO - the TIO protocol implemented by the PSP and used by
the host
GHCB - guest/host communication block - a protocol for
guest-to-host communication
via a shared page

CMA, IDE, TDISP,
TVM, DSM, SPDM, DOE

Code
----

Written with AMD SEV SNP in mind, TSM is the PSP and
therefore no much of IDE/TDISP
is left for the host or guest OS.

Add a common module to expose various data objects in
the same way in host and
guest OS.

Provide a know on the host to enable IDE encryption.

Add another version of Guest Request for secure
guest<->PSP communication.

Enable secure DMA by:
- configuring vTOM in a secure DTE via the PSP to cover
the entire guest RAM;
- mapping all private memory pages in IOMMU just like
as they were shared
(requires hacking iommufd);
- skipping various enforcements of non-SME or
SWIOTLB in the guest;

No mixed share+private DMA supported within the
same IOMMU.

Enable secure MMIO by:
- configuring RMP entries via the PSP;
- adding necessary helpers for mapping MMIO with
the Cbit set;
- hacking the KVM #PF handler to allow private
MMIO failts.

Based on the latest upstream KVM (at the
moment it is kvm-coco-queue).


Workflow
--------

1. Boot host OS.
2. "Connect" the physical device.
3. Bind a VF to VFIO-PCI.
4. Run QEMU _without_ the device yet.
5. Hotplug the VF to the VM.
6. (if not already) Load the device driver.
7. Right after the BusMaster is enabled,
tsm.ko performs secure DMA and MMIO setup.
8. Run tests, for example:
sudo ./pcimem/pcimem
/sys/bus/pci/devices/0000\:01\:00.0/resource4_enc
0 w*4 0xabcd


Assumptions
-----------

This requires hotpligging into the VM vs
passing the device via the command line as
VFIO maps all guest memory as the device init
step which is too soon as
SNP LAUNCH UPDATE happens later and will fail
if VFIO maps private memory before that.

This requires the BME hack as MMIO and
BusMaster enable bits cannot be 0 after MMIO
validation is done and there are moments in
the guest OS booting process when this
appens.

SVSM could help addressing these (not
implemented at the moment).

QEMU advertises TEE-IO capability to the VM.
An additional x-tio flag is added to
vfio-pci.


TODOs
-----

Deal with PCI reset. Hot unplug+plug? Power
states too.

Do better generalization, the current code
heavily uses SEV TIO defined
structures in supposedly generic code.

Fix the documentation comments of SEV TIO structures.


Git trees
---------

https://github.com/AMDESE/linux-kvm/tree/tio
https://github.com/AMDESE/qemu/tree/tio




Alexey Kardashevskiy (21):
  tsm-report: Rename module to reflect what it does
  pci/doe: Define protocol types and make those public
  pci: Define TEE-IO bit in PCIe device capabilities
  PCI/IDE: Define Integrity and Data Encryption (IDE) extended
    capability
  crypto/ccp: Make some SEV helpers public
  crypto: ccp: Enable SEV-TIO feature in the PSP when supported
  pci/tdisp: Introduce tsm module
  crypto/ccp: Implement SEV TIO firmware interface
  kvm: Export kvm_vm_set_mem_attributes
  vfio: Export helper to get vfio_device from fd
  KVM: SEV: Add TIO VMGEXIT and bind TDI
  KVM: IOMMUFD: MEMFD: Map private pages
  KVM: X86: Handle private MMIO as shared
  RFC: iommu/iommufd/amd: Add IOMMU_HWPT_TRUSTED flag, tweak DTE's
    DomainID, IOTLB
  coco/sev-guest: Allow multiple source files in the driver
  coco/sev-guest: Make SEV-to-PSP request helpers public
  coco/sev-guest: Implement the guest side of things
  RFC: pci: Add BUS_NOTIFY_PCI_BUS_MASTER event
  sev-guest: Stop changing encrypted page state for TDISP devices
  pci: Allow encrypted MMIO mapping via sysfs
  pci: Define pci_iomap_range_encrypted

 drivers/crypto/ccp/Makefile                              |    2 +
 drivers/pci/Makefile                                     |    1 +
 drivers/virt/coco/Makefile                               |    3 +-
 drivers/virt/coco/sev-guest/Makefile                     |    1 +
 arch/x86/include/asm/kvm-x86-ops.h                       |    2 +
 arch/x86/include/asm/kvm_host.h                          |    2 +
 arch/x86/include/asm/sev.h                               |   23 +
 arch/x86/include/uapi/asm/svm.h                          |    2 +
 arch/x86/kvm/svm/svm.h                                   |    2 +
 drivers/crypto/ccp/sev-dev-tio.h                         |  105 ++
 drivers/crypto/ccp/sev-dev.h                             |    4 +
 drivers/iommu/amd/amd_iommu_types.h                      |    2 +
 drivers/iommu/iommufd/io_pagetable.h                     |    3 +
 drivers/iommu/iommufd/iommufd_private.h                  |    4 +
 drivers/virt/coco/sev-guest/sev-guest.h                  |   56 +
 include/asm-generic/pci_iomap.h                          |    4 +
 include/linux/device.h                                   |    5 +
 include/linux/device/bus.h                               |    3 +
 include/linux/dma-direct.h                               |    4 +
 include/linux/iommufd.h                                  |    6 +
 include/linux/kvm_host.h                                 |   70 +
 include/linux/pci-doe.h                                  |    4 +
 include/linux/pci-ide.h                                  |   18 +
 include/linux/pci.h                                      |    2 +-
 include/linux/psp-sev.h                                  |  116 +-
 include/linux/swiotlb.h                                  |    4 +
 include/linux/tsm-report.h                               |  113 ++
 include/linux/tsm.h                                      |  337 +++--
 include/linux/vfio.h                                     |    1 +
 include/uapi/linux/iommufd.h                             |    1 +
 include/uapi/linux/kvm.h                                 |   29 +
 include/uapi/linux/pci_regs.h                            |   77 +-
 include/uapi/linux/psp-sev.h                             |    4 +-
 arch/x86/coco/sev/core.c                                 |   11 +
 arch/x86/kvm/mmu/mmu.c                                   |    6 +-
 arch/x86/kvm/svm/sev.c                                   |  217 +++
 arch/x86/kvm/svm/svm.c                                   |    3 +
 arch/x86/kvm/x86.c                                       |   12 +
 arch/x86/mm/mem_encrypt.c                                |    5 +
 arch/x86/virt/svm/sev.c                                  |   23 +-
 drivers/crypto/ccp/sev-dev-tio.c                         | 1565 ++++++++++++++++++++
 drivers/crypto/ccp/sev-dev-tsm.c                         |  397 +++++
 drivers/crypto/ccp/sev-dev.c                             |   87 +-
 drivers/iommu/amd/iommu.c                                |   20 +-
 drivers/iommu/iommufd/hw_pagetable.c                     |    4 +
 drivers/iommu/iommufd/io_pagetable.c                     |    2 +
 drivers/iommu/iommufd/main.c                             |   21 +
 drivers/iommu/iommufd/pages.c                            |   94 +-
 drivers/pci/doe.c                                        |    2 -
 drivers/pci/ide.c                                        |  186 +++
 drivers/pci/iomap.c                                      |   24 +
 drivers/pci/mmap.c                                       |   11 +-
 drivers/pci/pci-sysfs.c                                  |   27 +-
 drivers/pci/pci.c                                        |    3 +
 drivers/pci/proc.c                                       |    2 +-
 drivers/vfio/vfio_main.c                                 |   13 +
 drivers/virt/coco/sev-guest/{sev-guest.c => sev_guest.c} |   68 +-
 drivers/virt/coco/sev-guest/sev_guest_tio.c              |  513 +++++++
 drivers/virt/coco/tdx-guest/tdx-guest.c                  |    8 +-
 drivers/virt/coco/tsm-report.c                           |  512 +++++++
 drivers/virt/coco/tsm.c                                  | 1542 ++++++++++++++-----
 virt/kvm/guest_memfd.c                                   |   40 +
 virt/kvm/kvm_main.c                                      |    4 +-
 virt/kvm/vfio.c                                          |  197 ++-
 Documentation/virt/coco/tsm.rst                          |   62 +
 MAINTAINERS                                              |    4 +-
 arch/x86/kvm/Kconfig                                     |    1 +
 drivers/pci/Kconfig                                      |    4 +
 drivers/virt/coco/Kconfig                                |   11 +
 69 files changed, 6163 insertions(+), 548 deletions(-)
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.h
 create mode 100644 drivers/virt/coco/sev-guest/sev-guest.h
 create mode 100644 include/linux/pci-ide.h
 create mode 100644 include/linux/tsm-report.h
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.c
 create mode 100644 drivers/crypto/ccp/sev-dev-tsm.c
 create mode 100644 drivers/pci/ide.c
 rename drivers/virt/coco/sev-guest/{sev-guest.c => sev_guest.c} (96%)
 create mode 100644 drivers/virt/coco/sev-guest/sev_guest_tio.c
 create mode 100644 drivers/virt/coco/tsm-report.c
 create mode 100644 Documentation/virt/coco/tsm.rst

---

## [2] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 01/21] tsm-report: Rename module to reflect what it does*

And release the name for TSM to be used for TDISP-associated code.

Suggested-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/Makefile                |  2 +-
 include/linux/{tsm.h => tsm-report.h}     | 15 ++++++++-------
 drivers/virt/coco/sev-guest/sev-guest.c   | 10 +++++-----
 drivers/virt/coco/tdx-guest/tdx-guest.c   |  8 ++++----
 drivers/virt/coco/{tsm.c => tsm-report.c} | 12 ++++++------
 MAINTAINERS                               |  4 ++--
 6 files changed, 26 insertions(+), 25 deletions(-)

diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 18c1aba5edb7..75defec514f8 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -2,7 +2,7 @@
 #
 # Confidential computing related collateral
 #
-obj-$(CONFIG_TSM_REPORTS)	+= tsm.o
+obj-$(CONFIG_TSM_REPORTS)	+= tsm-report.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
diff --git a/include/linux/tsm.h b/include/linux/tsm-report.h
similarity index 92%
rename from include/linux/tsm.h
rename to include/linux/tsm-report.h
index 11b0c525be30..4d815358790b 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm-report.h
@@ -1,6 +1,6 @@
 /* SPDX-License-Identifier: GPL-2.0 */
-#ifndef __TSM_H
-#define __TSM_H
+#ifndef __TSM_REPORT_H
+#define __TSM_REPORT_H
 
 #include <linux/sizes.h>
 #include <linux/types.h>
@@ -88,7 +88,7 @@ enum tsm_bin_attr_index {
 };
 
 /**
- * struct tsm_ops - attributes and operations for tsm instances
+ * struct tsm_report_ops - attributes and operations for tsm instances
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
@@ -107,6 +107,7 @@ struct tsm_ops {
 	bool (*report_bin_attr_visible)(int n);
 };
 
-int tsm_register(const struct tsm_ops *ops, void *priv);
-int tsm_unregister(const struct tsm_ops *ops);
-#endif /* __TSM_H */
+int tsm_register(const struct tsm_report_ops *ops, void *priv);
+int tsm_unregister(const struct tsm_report_ops *ops);
+#endif /* __TSM_REPORT_H */
+
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 6fc7884ea0a1..ecc6176633be 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -16,7 +16,7 @@
 #include <linux/miscdevice.h>
 #include <linux/set_memory.h>
 #include <linux/fs.h>
-#include <linux/tsm.h>
+#include <linux/tsm-report.h>
 #include <crypto/aead.h>
 #include <linux/scatterlist.h>
 #include <linux/psp-sev.h>
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
+	tsm_unregister(&sev_tsm_report_ops);
 }
 
 static int __init sev_guest_probe(struct platform_device *pdev)
@@ -1158,9 +1158,9 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	snp_dev->input.data_gpa = __pa(snp_dev->certs_data);
 
 	/* Set the privlevel_floor attribute based on the vmpck_id */
-	sev_tsm_ops.privlevel_floor = vmpck_id;
+	sev_tsm_report_ops.privlevel_floor = vmpck_id;
 
-	ret = tsm_register(&sev_tsm_ops, snp_dev);
+	ret = tsm_register(&sev_tsm_report_ops, snp_dev);
 	if (ret)
 		goto e_free_cert_data;
 
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 2acba56ad42e..221d8b074301 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -15,7 +15,7 @@
 #include <linux/set_memory.h>
 #include <linux/io.h>
 #include <linux/delay.h>
-#include <linux/tsm.h>
+#include <linux/tsm-report.h>
 #include <linux/sizes.h>
 
 #include <uapi/linux/tdx-guest.h>
@@ -300,7 +300,7 @@ static const struct x86_cpu_id tdx_guest_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_guest_ids);
 
-static const struct tsm_ops tdx_tsm_ops = {
+static const struct tsm_report_ops tdx_tsm_report_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = tdx_report_new,
 	.report_attr_visible = tdx_report_attr_visible,
@@ -325,7 +325,7 @@ static int __init tdx_guest_init(void)
 		goto free_misc;
 	}
 
-	ret = tsm_register(&tdx_tsm_ops, NULL);
+	ret = tsm_register(&tdx_tsm_report_ops, NULL);
 	if (ret)
 		goto free_quote;
 
@@ -342,7 +342,7 @@ module_init(tdx_guest_init);
 
 static void __exit tdx_guest_exit(void)
 {
-	tsm_unregister(&tdx_tsm_ops);
+	tsm_unregister(&tdx_tsm_report_ops);
 	free_quote_buf(quote_data);
 	misc_deregister(&tdx_misc_dev);
 }
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm-report.c
similarity index 98%
rename from drivers/virt/coco/tsm.c
rename to drivers/virt/coco/tsm-report.c
index 9432d4e303f1..753ba2477f52 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm-report.c
@@ -3,7 +3,7 @@
 
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
 
-#include <linux/tsm.h>
+#include <linux/tsm-report.h>
 #include <linux/err.h>
 #include <linux/slab.h>
 #include <linux/rwsem.h>
@@ -13,7 +13,7 @@
 #include <linux/configfs.h>
 
 static struct tsm_provider {
-	const struct tsm_ops *ops;
+	const struct tsm_report_ops *ops;
 	void *data;
 } provider;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -272,7 +272,7 @@ static ssize_t tsm_report_read(struct tsm_report *report, void *buf,
 			       size_t count, enum tsm_data_select select)
 {
 	struct tsm_report_state *state = to_state(report);
-	const struct tsm_ops *ops;
+	const struct tsm_report_ops *ops;
 	ssize_t rc;
 
 	/* try to read from the existing report if present and valid... */
@@ -448,9 +448,9 @@ static struct configfs_subsystem tsm_configfs = {
 	.su_mutex = __MUTEX_INITIALIZER(tsm_configfs.su_mutex),
 };
 
-int tsm_register(const struct tsm_ops *ops, void *priv)
+int tsm_register(const struct tsm_report_ops *ops, void *priv)
 {
-	const struct tsm_ops *conflict;
+	const struct tsm_report_ops *conflict;
 
 	guard(rwsem_write)(&tsm_rwsem);
 	conflict = provider.ops;
@@ -465,7 +465,7 @@ int tsm_register(const struct tsm_ops *ops, void *priv)
 }
 EXPORT_SYMBOL_GPL(tsm_register);
 
-int tsm_unregister(const struct tsm_ops *ops)
+int tsm_unregister(const struct tsm_report_ops *ops)
 {
 	guard(rwsem_write)(&tsm_rwsem);
 	if (ops != provider.ops)
diff --git a/MAINTAINERS b/MAINTAINERS
index fcd91e4c5665..5169b13b2e55 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23256,8 +23256,8 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
-F:	drivers/virt/coco/tsm.c
-F:	include/linux/tsm.h
+F:	drivers/virt/coco/tsm-report.c
+F:	include/linux/tsm-report.h
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>

---

## [3] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 02/21] pci/doe: Define protocol types and make those public*

Already public pci_doe() takes a protocol type argument.
PCIe 6.0 defines three, define them in a header for use with pci_doe().

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/pci-doe.h | 4 ++++
 drivers/pci/doe.c       | 2 --
 2 files changed, 4 insertions(+), 2 deletions(-)

diff --git a/include/linux/pci-doe.h b/include/linux/pci-doe.h
index 0d3d7656c456..82e393ba5465 100644
--- a/include/linux/pci-doe.h
+++ b/include/linux/pci-doe.h
@@ -13,6 +13,10 @@
 #ifndef LINUX_PCI_DOE_H
 #define LINUX_PCI_DOE_H
 
+#define PCI_DOE_PROTOCOL_DISCOVERY		0
+#define PCI_DOE_PROTOCOL_CMA_SPDM		1
+#define PCI_DOE_PROTOCOL_SECURED_CMA_SPDM	2
+
 struct pci_doe_mb;
 
 /* Max data object length is 2^18 dwords (including 2 dwords for header) */
diff --git a/drivers/pci/doe.c b/drivers/pci/doe.c
index 0f94c4ed719e..30ba91f49b81 100644
--- a/drivers/pci/doe.c
+++ b/drivers/pci/doe.c
@@ -22,8 +22,6 @@
 
 #include "pci.h"
 
-#define PCI_DOE_PROTOCOL_DISCOVERY 0
-
 /* Timeout of 1 second from 6.30.2 Operation, PCI Spec r6.0 */
 #define PCI_DOE_TIMEOUT HZ
 #define PCI_DOE_POLL_INTERVAL	(PCI_DOE_TIMEOUT / 128)

---

## [4] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 03/21] pci: Define TEE-IO bit in PCIe device capabilities*

A new bit #30 from the PCI Express Device Capabilities Register is defined
in PCIe 6.1 as "TEE Device Interface Security Protocol (TDISP)".

Define the macro.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/uapi/linux/pci_regs.h | 1 +
 1 file changed, 1 insertion(+)

diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 94c00996e633..0011a301b8c5 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -498,6 +498,7 @@
 #define  PCI_EXP_DEVCAP_PWR_VAL	0x03fc0000 /* Slot Power Limit Value */
 #define  PCI_EXP_DEVCAP_PWR_SCL	0x0c000000 /* Slot Power Limit Scale */
 #define  PCI_EXP_DEVCAP_FLR     0x10000000 /* Function Level Reset */
+#define  PCI_EXP_DEVCAP_TEE_IO  0x40000000 /* TEE-IO Supported (TDISP) */
 #define PCI_EXP_DEVCTL		0x08	/* Device Control */
 #define  PCI_EXP_DEVCTL_CERE	0x0001	/* Correctable Error Reporting En. */
 #define  PCI_EXP_DEVCTL_NFERE	0x0002	/* Non-Fatal Error Reporting Enable */

---

## [5] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 04/21] PCI/IDE: Define Integrity and Data Encryption (IDE) extended capability*

PCIe 6.0 introduces the "Integrity & Data Encryption (IDE)" feature which
adds a new capability with id=0x30.

Add the new id to the list of capabilities. Add new flags from pciutils.
Add a module with a helper to control selective IDE capability.

TODO: get rid of lots of magic numbers. It is one annoying flexible
capability to deal with.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/pci/Makefile          |   1 +
 include/linux/pci-ide.h       |  18 ++
 include/uapi/linux/pci_regs.h |  76 +++++++-
 drivers/pci/ide.c             | 186 ++++++++++++++++++++
 drivers/pci/Kconfig           |   4 +
 5 files changed, 284 insertions(+), 1 deletion(-)

diff --git a/drivers/pci/Makefile b/drivers/pci/Makefile
index 1452e4ba7f00..034f17f9297a 100644
--- a/drivers/pci/Makefile
+++ b/drivers/pci/Makefile
@@ -34,6 +34,7 @@ obj-$(CONFIG_PCI_P2PDMA)	+= p2pdma.o
 obj-$(CONFIG_XEN_PCIDEV_FRONTEND) += xen-pcifront.o
 obj-$(CONFIG_VGA_ARB)		+= vgaarb.o
 obj-$(CONFIG_PCI_DOE)		+= doe.o
+obj-$(CONFIG_PCI_IDE)		+= ide.o
 obj-$(CONFIG_PCI_DYNAMIC_OF_NODES) += of_property.o
 
 obj-$(CONFIG_PCI_CMA)		+= cma.o cma.asn1.o
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
new file mode 100644
index 000000000000..983a8daf1199
--- /dev/null
+++ b/include/linux/pci-ide.h
@@ -0,0 +1,18 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Integrity & Data Encryption (IDE)
+ *	PCIe r6.0, sec 6.33 DOE
+ */
+
+#ifndef LINUX_PCI_IDE_H
+#define LINUX_PCI_IDE_H
+
+int pci_ide_set_sel(struct pci_dev *pdev, unsigned int sel_index, unsigned int streamid,
+		    bool enable, bool def, bool tee_limited, bool ide_cfg);
+int pci_ide_set_sel_rid_assoc(struct pci_dev *pdev, unsigned int sel_index,
+			      bool valid, u8 seg_base, u16 rid_base, u16 rid_limit);
+int pci_ide_set_sel_addr_assoc(struct pci_dev *pdev, unsigned int sel_index, unsigned int blocknum,
+			       bool valid, u64 base, u64 limit);
+int pci_ide_get_sel_sta(struct pci_dev *pdev, unsigned int sel_index, u32 *status);
+
+#endif
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 0011a301b8c5..80962b07719a 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -743,7 +743,8 @@
 #define PCI_EXT_CAP_ID_PL_16GT	0x26	/* Physical Layer 16.0 GT/s */
 #define PCI_EXT_CAP_ID_PL_32GT  0x2A    /* Physical Layer 32.0 GT/s */
 #define PCI_EXT_CAP_ID_DOE	0x2E	/* Data Object Exchange */
-#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_DOE
+#define PCI_EXT_CAP_ID_IDE	0x30	/* Integrity and Data Encryption (IDE) */
+#define PCI_EXT_CAP_ID_MAX	PCI_EXT_CAP_ID_IDE
 
 #define PCI_EXT_CAP_DSN_SIZEOF	12
 #define PCI_EXT_CAP_MCAST_ENDPOINT_SIZEOF 40
@@ -1150,9 +1151,82 @@
 #define PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL		0x00ff0000
 #define PCI_DOE_DATA_OBJECT_DISC_RSP_3_NEXT_INDEX	0xff000000
 
+
 /* Compute Express Link (CXL r3.1, sec 8.1.5) */
 #define PCI_DVSEC_CXL_PORT				3
 #define PCI_DVSEC_CXL_PORT_CTL				0x0c
 #define PCI_DVSEC_CXL_PORT_CTL_UNMASK_SBR		0x00000001
 
+/* Integrity and Data Encryption Extended Capability */
+#define PCI_IDE_CAP		0x4
+#define  PCI_IDE_CAP_LINK_IDE_SUPP	0x1	/* Link IDE Stream Supported */
+#define  PCI_IDE_CAP_SELECTIVE_IDE_SUPP 0x2	/* Selective IDE Streams Supported */
+#define  PCI_IDE_CAP_FLOWTHROUGH_IDE_SUPP 0x4	/* Flow-Through IDE Stream Supported */
+#define  PCI_IDE_CAP_PARTIAL_HEADER_ENC_SUPP 0x8 /* Partial Header Encryption Supported */
+#define  PCI_IDE_CAP_AGGREGATION_SUPP	0x10	/* Aggregation Supported */
+#define  PCI_IDE_CAP_PCRC_SUPP		0x20	/* PCRC Supported */
+#define  PCI_IDE_CAP_IDE_KM_SUPP	0x40	/* IDE_KM Protocol Supported */
+#define  PCI_IDE_CAP_ALG(x)	(((x) >> 8) & 0x1f) /* Supported Algorithms */
+#define  PCI_IDE_CAP_ALG_AES_GCM_256	0	/* AES-GCM 256 key size, 96b MAC */
+#define  PCI_IDE_CAP_LINK_TC_NUM(x)		(((x) >> 13) & 0x7) /* Link IDE TCs */
+#define  PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(x)	(((x) >> 16) & 0xff) /* Selective IDE Streams */
+#define  PCI_IDE_CAP_TEE_LIMITED_SUPP   0x1000000 /* TEE-Limited Stream Supported */
+#define PCI_IDE_CTL		0x8
+#define  PCI_IDE_CTL_FLOWTHROUGH_IDE	0x4	/* Flow-Through IDE Stream Enabled */
+#define PCI_IDE_LINK_STREAM		0xC
+/* Link IDE Stream block, up to PCI_IDE_CAP_LINK_TC_NUM */
+/* Link IDE Stream Control Register */
+#define  PCI_IDE_LINK_CTL_EN		0x1	/* Link IDE Stream Enable */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_NPR(x)(((x) >> 2) & 0x3) /* Tx Aggregation Mode NPR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_PR(x)	(((x) >> 4) & 0x3) /* Tx Aggregation Mode PR */
+#define  PCI_IDE_LINK_CTL_TX_AGGR_CPL(x)(((x) >> 6) & 0x3) /* Tx Aggregation Mode CPL */
+#define  PCI_IDE_LINK_CTL_PCRC_EN	0x100	/* PCRC Enable */
+#define  PCI_IDE_LINK_CTL_PART_ENC(x)	(((x) >> 10) & 0xf)  /* Partial Header Encryption Mode */
+#define  PCI_IDE_LINK_CTL_ALG(x)	(((x) >> 14) & 0x1f) /* Selected Algorithm */
+#define  PCI_IDE_LINK_CTL_TC(x)		(((x) >> 19) & 0x7)  /* Traffic Class */
+#define  PCI_IDE_LINK_CTL_ID(x)		(((x) >> 24) & 0xff) /* Stream ID */
+#define  PCI_IDE_LINK_CTL_ID_MASK	0xff000000
+
+/* Link IDE Stream Status Register */
+#define  PCI_IDE_LINK_STS_STATUS(x)	((x) & 0xf) /* Link IDE Stream State */
+#define  PCI_IDE_LINK_STS_RECVD_INTEGRITY_CHECK	0x80000000 /* Received Integrity Check Fail Msg */
+/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */
+/* Selective IDE Stream Capability Register */
+#define  PCI_IDE_SEL_CAP_BLOCKS_NUM(x)	((x) & 0xf) /*Address Association Register Blocks Number */
+/* Selective IDE Stream Control Register */
+#define  PCI_IDE_SEL_CTL_EN		0x1	/* Selective IDE Stream Enable */
+#define  PCI_IDE_SEL_CTL_TX_AGGR_NPR(x)	(((x) >> 2) & 0x3) /* Tx Aggregation Mode NPR */
+#define  PCI_IDE_SEL_CTL_TX_AGGR_PR(x)	(((x) >> 4) & 0x3) /* Tx Aggregation Mode PR */
+#define  PCI_IDE_SEL_CTL_TX_AGGR_CPL(x)	(((x) >> 6) & 0x3) /* Tx Aggregation Mode CPL */
+#define  PCI_IDE_SEL_CTL_PCRC_EN	0x100	/* PCRC Enable */
+#define  PCI_IDE_SEL_CTL_CFG_EN		0x200	/* Selective IDE for Configuration Requests */
+#define  PCI_IDE_SEL_CTL_PART_ENC(x)	(((x) >> 10) & 0xf)  /* Partial Header Encryption Mode */
+#define  PCI_IDE_SEL_CTL_ALG(x)		(((x) >> 14) & 0x1f) /* Selected Algorithm */
+#define  PCI_IDE_SEL_CTL_TC(x)		(((x) >> 19) & 0x7)  /* Traffic Class */
+#define  PCI_IDE_SEL_CTL_DEFAULT	0x400000 /* Default Stream */
+#define  PCI_IDE_SEL_CTL_TEE_LIMITED	(1 << 23) /* TEE-Limited Stream */
+#define  PCI_IDE_SEL_CTL_ID(x)		(((x) >> 24) & 0xff) /* Stream ID */
+/* Selective IDE Stream Status Register */
+#define  PCI_IDE_SEL_STS_STATUS(x)	((x) & 0xf) /* Selective IDE Stream State */
+#define  PCI_IDE_SEL_STS_RECVD_INTEGRITY_CHECK	0x80000000 /* Received Integrity Check Fail Msg */
+/* IDE RID Association Register 1 */
+#define  PCI_IDE_SEL_RID_1_LIMIT(x)	(((x) >> 8) & 0xffff) /* RID Limit */
+#define  PCI_IDE_SEL_RID_1(rid_limit)	(((rid_limit) & 0xffff) << 8)
+/* IDE RID Association Register 2 */
+#define  PCI_IDE_SEL_RID_2_VALID	0x1	/* Valid */
+#define  PCI_IDE_SEL_RID_2_BASE(x)	(((x) >> 8) & 0xffff) /* RID Base */
+#define  PCI_IDE_SEL_RID_2_SEG_BASE(x)	(((x) >> 24) & 0xff) /* Segmeng Base */
+#define  PCI_IDE_SEL_RID_2(v, rid_base, seg_base) ((((seg_base) & 0xff) << 24) | \
+						   (((rid_base) & 0xffff) << 8) | ((v) ? 1 : 0))
+/* Selective IDE Address Association Register Block, up to PCI_IDE_SEL_CAP_BLOCKS_NUM */
+#define  PCI_IDE_SEL_ADDR_1_VALID	0x1	/* Valid */
+#define  PCI_IDE_SEL_ADDR_1_BASE_LOW(x)	(((x) >> 8) & 0xfff) /* Memory Base Lower */
+#define  PCI_IDE_SEL_ADDR_1_LIMIT_LOW(x)(((x) >> 20) & 0xfff) /* Memory Limit Lower */
+/* IDE Address Association Register 2 is "Memory Limit Upper" */
+/* IDE Address Association Register 3 is "Memory Base Upper" */
+#define  PCI_IDE_SEL_ADDR_1(v, base, limit) ((FIELD_GET(0xfff00000, (limit))  << 20) | \
+					     (FIELD_GET(0xfff00000, (base)) << 8) | ((v) ? 1 : 0))
+#define  PCI_IDE_SEL_ADDR_2(limit)	((limit) >> 32)
+#define  PCI_IDE_SEL_ADDR_3(base)	((base) >> 32)
+
 #endif /* LINUX_PCI_REGS_H */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
new file mode 100644
index 000000000000..dc0632e836e7
--- /dev/null
+++ b/drivers/pci/ide.c
@@ -0,0 +1,186 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Integrity & Data Encryption (IDE)
+ *	PCIe r6.0, sec 6.33 DOE
+ */
+
+#define dev_fmt(fmt) "IDE: " fmt
+
+#include <linux/pci.h>
+#include <linux/pci-ide.h>
+#include <linux/bitfield.h>
+#include <linux/module.h>
+
+#define DRIVER_VERSION	"0.1"
+#define DRIVER_AUTHOR	"aik@amd.com"
+#define DRIVER_DESC	"Integrity and Data Encryption driver"
+
+/* Returns an offset of the specific IDE stream block */
+static u16 sel_off(struct pci_dev *pdev, unsigned int sel_index)
+{
+	u16 offset = pci_find_next_ext_capability(pdev, 0, PCI_EXT_CAP_ID_IDE);
+	unsigned int linknum = 0, selnum = 0, i;
+	u16 seloff;
+	u32 cap = 0;
+
+	if (!offset)
+		return 0;
+
+	pci_read_config_dword(pdev, offset + PCI_IDE_CAP, &cap);
+	if (cap & PCI_IDE_CAP_SELECTIVE_IDE_SUPP)
+		selnum = PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(cap) + 1;
+
+	if (!selnum || sel_index >= selnum)
+		return 0;
+
+	if (cap & PCI_IDE_CAP_LINK_IDE_SUPP)
+		linknum = PCI_IDE_CAP_LINK_TC_NUM(cap) + 1;
+
+	seloff = offset + PCI_IDE_LINK_STREAM + linknum * 2 * 4;
+	for (i = 0; i < sel_index; ++i) {
+		u32 selcap = 0;
+
+		pci_read_config_dword(pdev, seloff, &selcap);
+
+		/* Selective Cap+Ctrl+Sta + Addr#*8 */
+		seloff += 3 * 4 + PCI_IDE_SEL_CAP_BLOCKS_NUM(selcap) * 2 * 4;
+	}
+
+	return seloff;
+}
+
+static u16 sel_off_addr_block(struct pci_dev *pdev, u16 offset, unsigned int blocknum)
+{
+	unsigned int blocks;
+	u32 selcap = 0;
+
+	pci_read_config_dword(pdev, offset, &selcap);
+
+	blocks = PCI_IDE_SEL_CAP_BLOCKS_NUM(selcap);
+	if (!blocks)
+		return 0;
+
+	return offset + 3 * 4 + // Skip Cap, Ctl, Sta
+		2 * 4 + // RID Association Register 1 and 2
+		blocknum * 3 * 4; // Each block is Address Association Register 1, 2, 3
+}
+
+static int set_sel(struct pci_dev *pdev, unsigned int sel_index, u32 value)
+{
+	u16 offset = sel_off(pdev, sel_index);
+	u32 status = 0;
+
+	if (!offset)
+		return -EINVAL;
+
+	pci_read_config_dword(pdev, offset + 8, &status);
+	if (status & PCI_IDE_SEL_STS_RECVD_INTEGRITY_CHECK) {
+		pci_warn(pdev, "[%x] Clearing \"Received integrity check\"\n", offset + 4);
+		pci_write_config_dword(pdev, offset + 8,
+				       status & ~PCI_IDE_SEL_STS_RECVD_INTEGRITY_CHECK);
+	}
+
+	/* Selective IDE Stream Control Register */
+	pci_write_config_dword(pdev, offset + 4, value);
+	return 0;
+}
+
+int pci_ide_set_sel(struct pci_dev *pdev, unsigned int sel_index, unsigned int streamid,
+		    bool enable, bool def, bool tee_limited, bool ide_cfg)
+{
+	return set_sel(pdev, sel_index,
+		       FIELD_PREP(PCI_IDE_LINK_CTL_ID_MASK, streamid) |
+		       (def ? PCI_IDE_SEL_CTL_DEFAULT : 0) |
+		       (enable ? PCI_IDE_SEL_CTL_EN : 0) |
+		       (tee_limited ? PCI_IDE_SEL_CTL_TEE_LIMITED : 0) |
+		       (ide_cfg ? PCI_IDE_SEL_CTL_CFG_EN : 0)
+		      );
+}
+EXPORT_SYMBOL_GPL(pci_ide_set_sel);
+
+int pci_ide_set_sel_rid_assoc(struct pci_dev *pdev, unsigned int sel_index,
+			      bool valid, u8 seg_base, u16 rid_base, u16 rid_limit)
+{
+	u16 offset = sel_off(pdev, sel_index);
+	u32 rid1 = PCI_IDE_SEL_RID_1(rid_limit);
+	u32 rid2 = PCI_IDE_SEL_RID_2(valid, rid_base, seg_base);
+	u32 ctl = 0;
+
+	if (!offset)
+		return -EINVAL;
+
+	pci_read_config_dword(pdev, offset + 4, &ctl);
+	if (ctl & PCI_IDE_SEL_CTL_EN)
+		pci_warn(pdev, "Setting RID when En=off triggers Integrity Check Fail Message");
+
+	/* IDE RID Association Register 1 */
+	pci_write_config_dword(pdev, offset + 0xC, rid1);
+	/* IDE RID Association Register 2 */
+	pci_write_config_dword(pdev, offset + 0x10, rid2);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_set_sel_rid_assoc);
+
+int pci_ide_set_sel_addr_assoc(struct pci_dev *pdev, unsigned int sel_index, unsigned int blocknum,
+			       bool valid, u64 base, u64 limit)
+{
+	u16 offset = sel_off(pdev, sel_index), offset_ab;
+	u32 a1 = PCI_IDE_SEL_ADDR_1(1, base, limit);
+	u32 a2 = PCI_IDE_SEL_ADDR_2(limit);
+	u32 a3 = PCI_IDE_SEL_ADDR_3(base);
+
+	if (!offset)
+		return -EINVAL;
+
+	offset_ab = sel_off_addr_block(pdev, offset, blocknum);
+	if (!offset_ab || offset_ab <= offset)
+		return -EINVAL;
+
+	/* IDE Address Association Register 1 */
+	pci_write_config_dword(pdev, offset_ab, a1);
+	/* IDE Address Association Register 2 */
+	pci_write_config_dword(pdev, offset_ab + 4, a2);
+	/* IDE Address Association Register 1 */
+	pci_write_config_dword(pdev, offset_ab + 8, a3);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_set_sel_addr_assoc);
+
+int pci_ide_get_sel_sta(struct pci_dev *pdev, unsigned int sel_index, u32 *status)
+{
+	u16 offset = sel_off(pdev, sel_index);
+	u32 s = 0;
+	int ret;
+
+	if (!offset)
+		return -EINVAL;
+
+
+	ret = pci_read_config_dword(pdev, offset + 8, &s);
+	if (ret)
+		return ret;
+
+	*status = s;
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_ide_get_sel_sta);
+
+static int __init ide_init(void)
+{
+	int ret = 0;
+
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION "\n");
+	return ret;
+}
+
+static void __exit ide_cleanup(void)
+{
+}
+
+module_init(ide_init);
+module_exit(ide_cleanup);
+
+MODULE_VERSION(DRIVER_VERSION);
+MODULE_LICENSE("GPL");
+MODULE_AUTHOR(DRIVER_AUTHOR);
+MODULE_DESCRIPTION(DRIVER_DESC);
diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index b0b14468ba5d..8e908d684c77 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -137,6 +137,10 @@ config PCI_CMA
 config PCI_DOE
 	bool
 
+config PCI_IDE
+	tristate
+	default m
+
 config PCI_ECAM
 	bool

---

## [6] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 05/21] crypto/ccp: Make some SEV helpers public*

For SEV TIO.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/sev-dev.h | 2 ++
 include/linux/psp-sev.h      | 1 +
 drivers/crypto/ccp/sev-dev.c | 4 ++--
 3 files changed, 5 insertions(+), 2 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index 3e4e5574e88a..59842157e9d1 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -65,4 +65,6 @@ void sev_dev_destroy(struct psp_device *psp);
 void sev_pci_init(void);
 void sev_pci_exit(void);
 
+bool sev_version_greater_or_equal(u8 maj, u8 min);
+
 #endif /* __SEV_DEV_H */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 903ddfea8585..52d5ee101d3a 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -945,6 +945,7 @@ int sev_do_cmd(int cmd, void *data, int *psp_ret);
 void *psp_copy_user_blob(u64 uaddr, u32 len);
 void *snp_alloc_firmware_page(gfp_t mask);
 void snp_free_firmware_page(void *addr);
+int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool locked);
 
 #else	/* !CONFIG_CRYPTO_DEV_SP_PSP */
 
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 82549ff1d4a9..f6eafde584d9 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -109,7 +109,7 @@ static void *sev_init_ex_buffer;
  */
 static struct sev_data_range_list *snp_range_list;
 
-static inline bool sev_version_greater_or_equal(u8 maj, u8 min)
+bool sev_version_greater_or_equal(u8 maj, u8 min)
 {
 	struct sev_device *sev = psp_master->sev_data;
 
@@ -365,7 +365,7 @@ static int sev_write_init_ex_file_if_required(int cmd_id)
  */
 static int __sev_do_cmd_locked(int cmd, void *data, int *psp_ret);
 
-static int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool locked)
+int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool locked)
 {
 	int ret, err, i;

---

## [7] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 06/21] crypto: ccp: Enable SEV-TIO feature in the PSP when supported*

The PSP advertises the SEV-TIO support via the FEATURE_INFO command
support of which is advertised via SNP_PLATFORM_STATUS.

Add FEATURE_INFO and use it to detect the TIO support in the PSP.
If present, enable TIO in the SNP_INIT_EX call.

While at this, add new bits to sev_data_snp_init_ex() from SEV-SNP 1.55.

Note that this tests the PSP firmware support but not if the feature
is enabled in the BIOS.

While at this, add new sev_data_snp_shutdown_ex::x86_snp_shutdown

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/psp-sev.h      | 31 ++++++++-
 include/uapi/linux/psp-sev.h |  4 +-
 drivers/crypto/ccp/sev-dev.c | 73 ++++++++++++++++++++
 3 files changed, 104 insertions(+), 4 deletions(-)

diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 52d5ee101d3a..1d63044f66be 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -107,6 +107,7 @@ enum sev_cmd {
 	SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX = 0x0CA,
 	SEV_CMD_SNP_COMMIT		= 0x0CB,
 	SEV_CMD_SNP_VLEK_LOAD		= 0x0CD,
+	SEV_CMD_SNP_FEATURE_INFO	= 0x0CE,
 
 	SEV_CMD_MAX,
 };
@@ -584,6 +585,25 @@ struct sev_data_snp_addr {
 	u64 address;				/* In/Out */
 } __packed;
 
+/**
+ * struct sev_data_snp_feature_info - SEV_CMD_SNP_FEATURE_INFO command params
+ *
+ * @len: length of this struct
+ * @ecx_in: subfunction index of CPUID Fn8000_0024
+ * @feature_info_paddr: physical address of a page with sev_snp_feature_info
+ */
+#define SNP_FEATURE_FN8000_0024_EBX_X00_SEVTIO	1
+
+struct sev_snp_feature_info {
+	u32 eax, ebx, ecx, edx;			/* Out */
+} __packed;
+
+struct sev_data_snp_feature_info {
+	u32 length;				/* In */
+	u32 ecx_in;				/* In */
+	u64 feature_info_paddr;			/* In */
+} __packed;
+
 /**
  * struct sev_data_snp_launch_start - SNP_LAUNCH_START command params
  *
@@ -745,10 +765,14 @@ struct sev_data_snp_guest_request {
 struct sev_data_snp_init_ex {
 	u32 init_rmp:1;
 	u32 list_paddr_en:1;
-	u32 rsvd:30;
+	u32 rapl_dis:1;
+	u32 ciphertext_hiding_en:1;
+	u32 tio_en:1;
+	u32 rsvd:27;
 	u32 rsvd1;
 	u64 list_paddr;
-	u8  rsvd2[48];
+	u16 max_snp_asid;
+	u8  rsvd2[46];
 } __packed;
 
 /**
@@ -787,7 +811,8 @@ struct sev_data_range_list {
 struct sev_data_snp_shutdown_ex {
 	u32 len;
 	u32 iommu_snp_shutdown:1;
-	u32 rsvd1:31;
+	u32 x86_snp_shutdown:1;
+	u32 rsvd1:30;
 } __packed;
 
 /**
diff --git a/include/uapi/linux/psp-sev.h b/include/uapi/linux/psp-sev.h
index 7d2e10e3cdd5..28ee2a03c2b9 100644
--- a/include/uapi/linux/psp-sev.h
+++ b/include/uapi/linux/psp-sev.h
@@ -214,6 +214,7 @@ struct sev_user_data_get_id2 {
  * @mask_chip_id: whether chip id is present in attestation reports or not
  * @mask_chip_key: whether attestation reports are signed or not
  * @vlek_en: VLEK (Version Loaded Endorsement Key) hashstick is loaded
+ * @feature_info: Indicates that the SNP_FEATURE_INFO command is available
  * @rsvd1: reserved
  * @guest_count: the number of guest currently managed by the firmware
  * @current_tcb_version: current TCB version
@@ -229,7 +230,8 @@ struct sev_user_data_snp_status {
 	__u32 mask_chip_id:1;		/* Out */
 	__u32 mask_chip_key:1;		/* Out */
 	__u32 vlek_en:1;		/* Out */
-	__u32 rsvd1:29;
+	__u32 feature_info:1;		/* Out */
+	__u32 rsvd1:28;
 	__u32 guest_count;		/* Out */
 	__u64 current_tcb_version;	/* Out */
 	__u64 reported_tcb_version;	/* Out */
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index f6eafde584d9..a49fe54b8dd8 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -223,6 +223,7 @@ static int sev_cmd_buffer_len(int cmd)
 	case SEV_CMD_SNP_GUEST_REQUEST:		return sizeof(struct sev_data_snp_guest_request);
 	case SEV_CMD_SNP_CONFIG:		return sizeof(struct sev_user_data_snp_config);
 	case SEV_CMD_SNP_COMMIT:		return sizeof(struct sev_data_snp_commit);
+	case SEV_CMD_SNP_FEATURE_INFO:		return sizeof(struct sev_data_snp_feature_info);
 	default:				return 0;
 	}
 
@@ -1125,6 +1126,77 @@ static int snp_platform_status_locked(struct sev_device *sev,
 	return ret;
 }
 
+static int snp_feature_info_locked(struct sev_device *sev, u32 ecx,
+				   struct sev_snp_feature_info *fi, int *psp_ret)
+{
+	struct sev_data_snp_feature_info buf = {
+		.length = sizeof(buf),
+		.ecx_in = ecx,
+	};
+	struct page *status_page;
+	void *data;
+	int ret;
+
+	status_page = alloc_page(GFP_KERNEL_ACCOUNT);
+	if (!status_page)
+		return -ENOMEM;
+
+	data = page_address(status_page);
+
+	if (sev->snp_initialized && rmp_mark_pages_firmware(__pa(data), 1, true)) {
+		ret = -EFAULT;
+		goto cleanup;
+	}
+
+	buf.feature_info_paddr = __psp_pa(data);
+	ret = __sev_do_cmd_locked(SEV_CMD_SNP_FEATURE_INFO, &buf, psp_ret);
+
+	if (sev->snp_initialized && snp_reclaim_pages(__pa(data), 1, true))
+		ret = -EFAULT;
+
+	if (!ret)
+		memcpy(fi, data, sizeof(*fi));
+
+cleanup:
+	__free_pages(status_page, 0);
+	return ret;
+}
+
+static int snp_get_feature_info(struct sev_device *sev, u32 ecx, struct sev_snp_feature_info *fi)
+{
+	struct sev_user_data_snp_status status = { 0 };
+	int psp_ret = 0, ret;
+
+	ret = snp_platform_status_locked(sev, &status, &psp_ret);
+	if (ret)
+		return ret;
+	if (ret != SEV_RET_SUCCESS)
+		return -EFAULT;
+	if (!status.feature_info)
+		return -ENOENT;
+
+	ret = snp_feature_info_locked(sev, ecx, fi, &psp_ret);
+	if (ret)
+		return ret;
+	if (ret != SEV_RET_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
+static bool sev_tio_present(struct sev_device *sev)
+{
+	struct sev_snp_feature_info fi = { 0 };
+	bool present;
+
+	if (snp_get_feature_info(sev, 0, &fi))
+		return false;
+
+	present = (fi.ebx & SNP_FEATURE_FN8000_0024_EBX_X00_SEVTIO) != 0;
+	dev_info(sev->dev, "SEV-TIO support is %s\n", present ? "present" : "not present");
+	return present;
+}
+
 static int __sev_snp_init_locked(int *error)
 {
 	struct psp_device *psp = psp_master;
@@ -1189,6 +1261,7 @@ static int __sev_snp_init_locked(int *error)
 		data.init_rmp = 1;
 		data.list_paddr_en = 1;
 		data.list_paddr = __psp_pa(snp_range_list);
+		data.tio_en = sev_tio_present(sev);
 		cmd = SEV_CMD_SNP_INIT_EX;
 	} else {
 		cmd = SEV_CMD_SNP_INIT;

---

## [8] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

The module responsibilities are:
1. detect TEE support in a device and create nodes in the device's sysfs
entry;
2. allow binding a PCI device to a VM for passing it through in a trusted
manner;
3. store measurements/certificates/reports and provide access to those for
the userspace via sysfs.

This relies on the platform to register a set of callbacks,
for both host and guest.

And tdi_enabled in the device struct.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/Makefile      |    1 +
 include/linux/device.h          |    5 +
 include/linux/tsm.h             |  263 ++++
 drivers/virt/coco/tsm.c         | 1336 ++++++++++++++++++++
 Documentation/virt/coco/tsm.rst |   62 +
 drivers/virt/coco/Kconfig       |   11 +
 6 files changed, 1678 insertions(+)

diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 75defec514f8..5d1aefb62714 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -3,6 +3,7 @@
 # Confidential computing related collateral
 #
 obj-$(CONFIG_TSM_REPORTS)	+= tsm-report.o
+obj-$(CONFIG_TSM)		+= tsm.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
diff --git a/include/linux/device.h b/include/linux/device.h
index 34eb20f5966f..bb58ed1fb8da 100644
--- a/include/linux/device.h
+++ b/include/linux/device.h
@@ -45,6 +45,7 @@ struct fwnode_handle;
 struct iommu_group;
 struct dev_pin_info;
 struct dev_iommu;
+struct tsm_tdi;
 struct msi_device_data;
 
 /**
@@ -801,6 +802,7 @@ struct device {
 	void	(*release)(struct device *dev);
 	struct iommu_group	*iommu_group;
 	struct dev_iommu	*iommu;
+	struct tsm_tdi		*tdi;
 
 	struct device_physical_location *physical_location;
 
@@ -822,6 +824,9 @@ struct device {
 #ifdef CONFIG_DMA_NEED_SYNC
 	bool			dma_skip_sync:1;
 #endif
+#if defined(CONFIG_TSM) || defined(CONFIG_TSM_MODULE)
+	bool			tdi_enabled:1;
+#endif
 };
 
 /**
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
new file mode 100644
index 000000000000..d48eceaf5bc0
--- /dev/null
+++ b/include/linux/tsm.h
@@ -0,0 +1,263 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+
+#ifndef LINUX_TSM_H
+#define LINUX_TSM_H
+
+#include <linux/cdev.h>
+
+/* SPDM control structure for DOE */
+struct tsm_spdm {
+	unsigned long req_len;
+	void *req;
+	unsigned long rsp_len;
+	void *rsp;
+
+	struct pci_doe_mb *doe_mb;
+	struct pci_doe_mb *doe_mb_secured;
+};
+
+/* Data object for measurements/certificates/attestationreport */
+struct tsm_blob {
+	void *data;
+	size_t len;
+	struct kref kref;
+	void (*release)(struct tsm_blob *b);
+};
+
+struct tsm_blob *tsm_blob_new(void *data, size_t len, void (*release)(struct tsm_blob *b));
+struct tsm_blob *tsm_blob_get(struct tsm_blob *b);
+void tsm_blob_put(struct tsm_blob *b);
+
+/**
+ * struct tdisp_interface_id - TDISP INTERFACE_ID Definition
+ *
+ * @function_id: Identifies the function of the device hosting the TDI
+ * 15:0: @rid: Requester ID
+ * 23:16: @rseg: Requester Segment (Reserved if Requester Segment Valid is Clear)
+ * 24: @rseg_valid: Requester Segment Valid
+ * 31:25 – Reserved
+ * 8B - Reserved
+ */
+struct tdisp_interface_id {
+	union {
+		struct {
+			u32 function_id;
+			u8 reserved[8];
+		};
+		struct {
+			u16 rid;
+			u8 rseg;
+			u8 rseg_valid:1;
+		};
+	};
+} __packed;
+
+/*
+ * Measurement block as defined in SPDM DSP0274.
+ */
+struct spdm_measurement_block_header {
+	u8 index;
+	u8 spec; /* MeasurementSpecification */
+	u16 size;
+} __packed;
+
+struct dmtf_measurement_block_header {
+	u8 type;  /* DMTFSpecMeasurementValueType */
+	u16 size; /* DMTFSpecMeasurementValueSize */
+} __packed;
+
+struct dmtf_measurement_block_device_mode {
+	u32 opmode_cap;	 /* OperationalModeCapabilties */
+	u32 opmode_sta;  /* OperationalModeState */
+	u32 devmode_cap; /* DeviceModeCapabilties */
+	u32 devmode_sta; /* DeviceModeState */
+} __packed;
+
+struct spdm_certchain_block_header {
+	u16 length;
+	u16 reserved;
+} __packed;
+
+/*
+ * TDI Report Structure as defined in TDISP.
+ */
+struct tdi_report_header {
+	union {
+		u16 interface_info;
+		struct {
+			u16 no_fw_update:1; /* fw updates not permitted in CONFIG_LOCKED or RUN */
+			u16 dma_no_pasid:1; /* TDI generates DMA requests without PASID */
+			u16 dma_pasid:1; /* TDI generates DMA requests with PASID */
+			u16 ats:1; /*  ATS supported and enabled for the TDI */
+			u16 prs:1; /*  PRS supported and enabled for the TDI */
+			u16 reserved1:11;
+		};
+	};
+	u16 reserved2;
+	u16 msi_x_message_control;
+	u16 lnr_control;
+	u32 tph_control;
+	u32 mmio_range_count;
+} __packed;
+
+/*
+ * Each MMIO Range of the TDI is reported with the MMIO reporting offset added.
+ * Base and size in units of 4K pages
+ */
+struct tdi_report_mmio_range {
+	u64 first_page; /* First 4K page with offset added */
+	u32 num; 	/* Number of 4K pages in this range */
+	union {
+		u32 range_attributes;
+		struct {
+			u32 msix_table:1;
+			u32 msix_pba:1;
+			u32 is_non_tee_mem:1;
+			u32 is_mem_attr_updatable:1;
+			u32 reserved:12;
+			u32 range_id:16;
+		};
+	};
+} __packed;
+
+struct tdi_report_footer {
+	u32 device_specific_info_len;
+	u8 device_specific_info[];
+} __packed;
+
+#define TDI_REPORT_HDR(rep)		((struct tdi_report_header *) ((rep)->data))
+#define TDI_REPORT_MR_NUM(rep)		(TDI_REPORT_HDR(rep)->mmio_range_count)
+#define TDI_REPORT_MR_OFF(rep)		((struct tdi_report_mmio_range *) (TDI_REPORT_HDR(rep) + 1))
+#define TDI_REPORT_MR(rep, rangeid)	TDI_REPORT_MR_OFF(rep)[rangeid]
+#define TDI_REPORT_FTR(rep)		((struct tdi_report_footer *) &TDI_REPORT_MR((rep), \
+					TDI_REPORT_MR_NUM(rep)))
+
+/* Physical device descriptor responsible for IDE/TDISP setup */
+struct tsm_dev {
+	struct kref kref;
+	const struct attribute_group *ag;
+	struct pci_dev *pdev; /* Physical PCI function #0 */
+	struct tsm_spdm spdm;
+	struct mutex spdm_mutex;
+
+	u8 tc_mask;
+	u8 cert_slot;
+	u8 connected;
+	struct {
+		u8 enabled:1;
+		u8 enable:1;
+		u8 def:1;
+		u8 dev_ide_cfg:1;
+		u8 dev_tee_limited:1;
+		u8 rootport_ide_cfg:1;
+		u8 rootport_tee_limited:1;
+		u8 id;
+	} selective_ide[256];
+	bool ide_pre;
+
+	struct tsm_blob *meas;
+	struct tsm_blob *certs;
+
+	void *data; /* Platform specific data */
+};
+
+/* PCI function for passing through, can be the same as tsm_dev::pdev */
+struct tsm_tdi {
+	const struct attribute_group *ag;
+	struct pci_dev *pdev;
+	struct tsm_dev *tdev;
+
+	u8 rseg;
+	u8 rseg_valid;
+	bool validated;
+
+	struct tsm_blob *report;
+
+	void *data; /* Platform specific data */
+
+	u64 vmid;
+	u32 asid;
+	u16 guest_rid; /* BDFn of PCI Fn in the VM */
+};
+
+struct tsm_dev_status {
+	u8 ctx_state;
+	u8 tc_mask;
+	u8 certs_slot;
+	u16 device_id;
+	u16 segment_id;
+	u8 no_fw_update;
+	u16 ide_stream_id[8];
+};
+
+enum tsm_spdm_algos {
+	TSM_TDI_SPDM_ALGOS_DHE_SECP256R1,
+	TSM_TDI_SPDM_ALGOS_DHE_SECP384R1,
+	TSM_TDI_SPDM_ALGOS_AEAD_AES_128_GCM,
+	TSM_TDI_SPDM_ALGOS_AEAD_AES_256_GCM,
+	TSM_TDI_SPDM_ALGOS_ASYM_TPM_ALG_RSASSA_3072,
+	TSM_TDI_SPDM_ALGOS_ASYM_TPM_ALG_ECDSA_ECC_NIST_P256,
+	TSM_TDI_SPDM_ALGOS_ASYM_TPM_ALG_ECDSA_ECC_NIST_P384,
+	TSM_TDI_SPDM_ALGOS_HASH_TPM_ALG_SHA_256,
+	TSM_TDI_SPDM_ALGOS_HASH_TPM_ALG_SHA_384,
+	TSM_TDI_SPDM_ALGOS_KEY_SCHED_SPDM_KEY_SCHEDULE,
+};
+
+enum tsm_tdisp_state {
+	TDISP_STATE_UNAVAIL,
+	TDISP_STATE_CONFIG_UNLOCKED,
+	TDISP_STATE_CONFIG_LOCKED,
+	TDISP_STATE_RUN,
+	TDISP_STATE_ERROR,
+};
+
+struct tsm_tdi_status {
+	bool valid;
+	u8 meas_digest_fresh:1;
+	u8 meas_digest_valid:1;
+	u8 all_request_redirect:1;
+	u8 bind_p2p:1;
+	u8 lock_msix:1;
+	u8 no_fw_update:1;
+	u16 cache_line_size;
+	u64 spdm_algos; /* Bitmask of tsm_spdm_algos */
+	u8 certs_digest[48];
+	u8 meas_digest[48];
+	u8 interface_report_digest[48];
+
+	/* HV only */
+	struct tdisp_interface_id id;
+	u8 guest_report_id[16];
+	enum tsm_tdisp_state state;
+};
+
+struct tsm_ops {
+	/* HV hooks */
+	int (*dev_connect)(struct tsm_dev *tdev, void *private_data);
+	int (*dev_reclaim)(struct tsm_dev *tdev, void *private_data);
+	int (*dev_status)(struct tsm_dev *tdev, void *private_data, struct tsm_dev_status *s);
+	int (*ide_refresh)(struct tsm_dev *tdev, void *private_data);
+	int (*tdi_bind)(struct tsm_tdi *tdi, u32 bdfn, u64 vmid, u32 asid, void *private_data);
+	int (*tdi_reclaim)(struct tsm_tdi *tdi, void *private_data);
+
+	int (*guest_request)(struct tsm_tdi *tdi, u32 guest_rid, u64 vmid, void *req_data,
+			     enum tsm_tdisp_state *state, void *private_data);
+
+	/* VM hooks */
+	int (*tdi_validate)(struct tsm_tdi *tdi, bool invalidate, void *private_data);
+
+	/* HV and VM hooks */
+	int (*tdi_status)(struct tsm_tdi *tdi, void *private_data, struct tsm_tdi_status *ts);
+};
+
+void tsm_set_ops(struct tsm_ops *ops, void *private_data);
+struct tsm_tdi *tsm_tdi_get(struct device *dev);
+int tsm_tdi_bind(struct tsm_tdi *tdi, u32 guest_rid, u64 vmid, u32 asid);
+void tsm_tdi_unbind(struct tsm_tdi *tdi);
+int tsm_guest_request(struct tsm_tdi *tdi, enum tsm_tdisp_state *state, void *req_data);
+struct tsm_tdi *tsm_tdi_find(u32 guest_rid, u64 vmid);
+
+int pci_dev_tdi_validate(struct pci_dev *pdev);
+ssize_t tsm_report_gen(struct tsm_blob *report, char *b, size_t len);
+
+#endif /* LINUX_TSM_H */
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
new file mode 100644
index 000000000000..e90455a0267f
--- /dev/null
+++ b/drivers/virt/coco/tsm.c
@@ -0,0 +1,1336 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/pci-doe.h>
+#include <linux/pci-ide.h>
+#include <linux/file.h>
+#include <linux/fdtable.h>
+#include <linux/tsm.h>
+#include <linux/kvm_host.h>
+
+#define DRIVER_VERSION	"0.1"
+#define DRIVER_AUTHOR	"aik@amd.com"
+#define DRIVER_DESC	"TSM TDISP driver"
+
+static struct {
+	struct tsm_ops *ops;
+	void *private_data;
+
+	uint tc_mask;
+	uint cert_slot;
+	bool physfn;
+} tsm;
+
+module_param_named(tc_mask, tsm.tc_mask, uint, 0644);
+MODULE_PARM_DESC(tc_mask, "Mask of traffic classes enabled in the device");
+
+module_param_named(cert_slot, tsm.cert_slot, uint, 0644);
+MODULE_PARM_DESC(cert_slot, "Slot number of the certificate requested for constructing the SPDM session");
+
+module_param_named(physfn, tsm.physfn, bool, 0644);
+MODULE_PARM_DESC(physfn, "Allow TDI on SR IOV of a physical function");
+
+struct tsm_blob *tsm_blob_new(void *data, size_t len, void (*release)(struct tsm_blob *b))
+{
+	struct tsm_blob *b;
+
+	if (!len || !data)
+		return NULL;
+
+	b = kzalloc(sizeof(*b) + len, GFP_KERNEL);
+	if (!b)
+		return NULL;
+
+	b->data = (void *)b + sizeof(*b);
+	b->len = len;
+	b->release = release;
+	memcpy(b->data, data, len);
+	kref_init(&b->kref);
+
+	return b;
+}
+EXPORT_SYMBOL_GPL(tsm_blob_new);
+
+static void tsm_blob_release(struct kref *kref)
+{
+	struct tsm_blob *b = container_of(kref, struct tsm_blob, kref);
+
+	b->release(b);
+	kfree(b);
+}
+
+struct tsm_blob *tsm_blob_get(struct tsm_blob *b)
+{
+	if (!b)
+		return NULL;
+
+	if (!kref_get_unless_zero(&b->kref))
+		return NULL;
+
+	return b;
+}
+EXPORT_SYMBOL_GPL(tsm_blob_get);
+
+void tsm_blob_put(struct tsm_blob *b)
+{
+	if (!b)
+		return;
+
+	kref_put(&b->kref, tsm_blob_release);
+}
+EXPORT_SYMBOL_GPL(tsm_blob_put);
+
+static struct tsm_dev *tsm_dev_get(struct device *dev)
+{
+	struct tsm_tdi *tdi = dev->tdi;
+
+	if (!tdi || !tdi->tdev || !kref_get_unless_zero(&tdi->tdev->kref))
+		return NULL;
+
+	return tdi->tdev;
+}
+
+static void tsm_dev_free(struct kref *kref);
+static void tsm_dev_put(struct tsm_dev *tdev)
+{
+	kref_put(&tdev->kref, tsm_dev_free);
+}
+
+struct tsm_tdi *tsm_tdi_get(struct device *dev)
+{
+	struct tsm_tdi *tdi = dev->tdi;
+
+	return tdi;
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_get);
+
+static int spdm_forward(struct tsm_spdm *spdm, u8 type)
+{
+	struct pci_doe_mb *doe_mb;
+	int rc;
+
+	if (type == PCI_DOE_PROTOCOL_SECURED_CMA_SPDM)
+		doe_mb = spdm->doe_mb_secured;
+	else if (type == PCI_DOE_PROTOCOL_CMA_SPDM)
+		doe_mb = spdm->doe_mb;
+	else
+		return -EINVAL;
+
+	if (!doe_mb)
+		return -EFAULT;
+
+	rc = pci_doe(doe_mb, PCI_VENDOR_ID_PCI_SIG, type,
+		     spdm->req, spdm->req_len, spdm->rsp, spdm->rsp_len);
+	if (rc >= 0)
+		spdm->rsp_len = rc;
+
+	return rc;
+}
+
+/*
+ * Enables IDE between the RC and the device.
+ * TEE Limited, IDE Cfg space and other bits are hardcoded
+ * as this is a sketch.
+ */
+static int tsm_set_sel_ide(struct tsm_dev *tdev)
+{
+	struct pci_dev *rootport;
+	bool printed = false;
+	unsigned int i;
+	int ret = 0;
+
+	rootport = tdev->pdev->bus->self;
+	for (i = 0; i < ARRAY_SIZE(tdev->selective_ide); ++i) {
+		if (!tdev->selective_ide[i].enable)
+			continue;
+
+		if (!printed) {
+			pci_info(rootport, "Configuring IDE with %s\n",
+				 pci_name(tdev->pdev));
+			printed = true;
+		}
+		WARN_ON_ONCE(tdev->selective_ide[i].enabled);
+
+		ret = pci_ide_set_sel_rid_assoc(tdev->pdev, i, true, 0, 0, 0xFFFF);
+		if (ret)
+			pci_warn(tdev->pdev,
+				 "Failed configuring SelectiveIDE#%d rid1 with %d\n",
+				 i, ret);
+		ret = pci_ide_set_sel_addr_assoc(tdev->pdev, i, 0/* RID# */, true,
+						 0, 0xFFFFFFFFFFF00000ULL);
+		if (ret)
+			pci_warn(tdev->pdev,
+				 "Failed configuring SelectiveIDE#%d RID#0 with %d\n",
+				 i, ret);
+
+		ret = pci_ide_set_sel(tdev->pdev, i,
+				      tdev->selective_ide[i].id,
+				      tdev->selective_ide[i].enable,
+				      tdev->selective_ide[i].def,
+				      tdev->selective_ide[i].dev_tee_limited,
+				      tdev->selective_ide[i].dev_ide_cfg);
+		if (ret) {
+			pci_warn(tdev->pdev,
+				 "Failed configuring SelectiveIDE#%d with %d\n",
+				 i, ret);
+			break;
+		}
+
+		ret = pci_ide_set_sel_rid_assoc(rootport, i, true, 0, 0, 0xFFFF);
+		if (ret)
+			pci_warn(rootport,
+				 "Failed configuring SelectiveIDE#%d rid1 with %d\n",
+				 i, ret);
+
+		ret = pci_ide_set_sel(rootport, i,
+				      tdev->selective_ide[i].id,
+				      tdev->selective_ide[i].enable,
+				      tdev->selective_ide[i].def,
+				      tdev->selective_ide[i].rootport_tee_limited,
+				      tdev->selective_ide[i].rootport_ide_cfg);
+		if (ret)
+			pci_warn(rootport,
+				 "Failed configuring SelectiveIDE#%d with %d\n",
+				 i, ret);
+
+		tdev->selective_ide[i].enabled = 1;
+	}
+
+	return ret;
+}
+
+static void tsm_unset_sel_ide(struct tsm_dev *tdev)
+{
+	struct pci_dev *rootport = tdev->pdev->bus->self;
+	bool printed = false;
+
+	for (unsigned int i = 0; i < ARRAY_SIZE(tdev->selective_ide); ++i) {
+		if (!tdev->selective_ide[i].enabled)
+			continue;
+
+		if (!printed) {
+			pci_info(rootport, "Deconfiguring IDE with %s\n", pci_name(tdev->pdev));
+			printed = true;
+		}
+
+		pci_ide_set_sel(rootport, i, 0, 0, 0, false, false);
+		pci_ide_set_sel(tdev->pdev, i, 0, 0, 0, false, false);
+		tdev->selective_ide[i].enabled = 0;
+	}
+}
+
+static int tsm_dev_connect(struct tsm_dev *tdev, void *private_data, unsigned int val)
+{
+	int ret;
+
+	if (WARN_ON(!tsm.ops->dev_connect))
+		return -EPERM;
+
+	tdev->ide_pre = val == 2;
+	if (tdev->ide_pre)
+		tsm_set_sel_ide(tdev);
+
+	mutex_lock(&tdev->spdm_mutex);
+	while (1) {
+		ret = tsm.ops->dev_connect(tdev, tsm.private_data);
+		if (ret <= 0)
+			break;
+
+		ret = spdm_forward(&tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	if (!tdev->ide_pre)
+		ret = tsm_set_sel_ide(tdev);
+
+	tdev->connected = (ret == 0);
+
+	return ret;
+}
+
+static int tsm_dev_reclaim(struct tsm_dev *tdev, void *private_data)
+{
+	struct pci_dev *pdev = NULL;
+	int ret;
+
+	if (WARN_ON(!tsm.ops->dev_reclaim))
+		return -EPERM;
+
+	/* Do not disconnect with active TDIs */
+	for_each_pci_dev(pdev) {
+		struct tsm_tdi *tdi = tsm_tdi_get(&pdev->dev);
+
+		if (tdi && tdi->tdev == tdev && tdi->data)
+			return -EBUSY;
+	}
+
+	if (!tdev->ide_pre)
+		tsm_unset_sel_ide(tdev);
+
+	mutex_lock(&tdev->spdm_mutex);
+	while (1) {
+		ret = tsm.ops->dev_reclaim(tdev, private_data);
+		if (ret <= 0)
+			break;
+
+		ret = spdm_forward(&tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	if (tdev->ide_pre)
+		tsm_unset_sel_ide(tdev);
+
+	if (!ret)
+		tdev->connected = false;
+
+	return ret;
+}
+
+static int tsm_dev_status(struct tsm_dev *tdev, void *private_data, struct tsm_dev_status *s)
+{
+	if (WARN_ON(!tsm.ops->dev_status))
+		return -EPERM;
+
+	return tsm.ops->dev_status(tdev, private_data, s);
+}
+
+static int tsm_ide_refresh(struct tsm_dev *tdev, void *private_data)
+{
+	int ret;
+
+	if (!tsm.ops->ide_refresh)
+		return -EPERM;
+
+	mutex_lock(&tdev->spdm_mutex);
+	while (1) {
+		ret = tsm.ops->ide_refresh(tdev, private_data);
+		if (ret <= 0)
+			break;
+
+		ret = spdm_forward(&tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	return ret;
+}
+
+static void tsm_tdi_reclaim(struct tsm_tdi *tdi, void *private_data)
+{
+	int ret;
+
+	if (WARN_ON(!tsm.ops->tdi_reclaim))
+		return;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = tsm.ops->tdi_reclaim(tdi, private_data);
+		if (ret <= 0)
+			break;
+
+		ret = spdm_forward(&tdi->tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+}
+
+static int tsm_tdi_validate(struct tsm_tdi *tdi, bool invalidate, void *private_data)
+{
+	int ret;
+
+	if (!tdi || !tsm.ops->tdi_validate)
+		return -EPERM;
+
+	ret = tsm.ops->tdi_validate(tdi, invalidate, private_data);
+	if (ret) {
+		pci_err(tdi->pdev, "Validation failed, ret=%d", ret);
+		tdi->pdev->dev.tdi_enabled = false;
+	}
+
+	return ret;
+}
+
+/* In case BUS_NOTIFY_PCI_BUS_MASTER is no good, a driver can call pci_dev_tdi_validate() */
+int pci_dev_tdi_validate(struct pci_dev *pdev)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(&pdev->dev);
+
+	return tsm_tdi_validate(tdi, false, tsm.private_data);
+}
+EXPORT_SYMBOL_GPL(pci_dev_tdi_validate);
+
+static int tsm_tdi_status(struct tsm_tdi *tdi, void *private_data, struct tsm_tdi_status *ts)
+{
+	struct tsm_tdi_status tstmp = { 0 };
+	int ret;
+
+	if (WARN_ON(!tsm.ops->tdi_status))
+		return -EPERM;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = tsm.ops->tdi_status(tdi, private_data, &tstmp);
+		if (ret <= 0)
+			break;
+
+		ret = spdm_forward(&tdi->tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	*ts = tstmp;
+
+	return ret;
+}
+
+static ssize_t tsm_cert_slot_store(struct device *dev, struct device_attribute *attr,
+				   const char *buf, size_t count)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	ssize_t ret = count;
+	unsigned long val;
+
+	if (kstrtoul(buf, 0, &val) < 0)
+		ret = -EINVAL;
+	else
+		tdev->cert_slot = val;
+
+	tsm_dev_put(tdev);
+
+	return ret;
+}
+
+static ssize_t tsm_cert_slot_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	ssize_t ret = sysfs_emit(buf, "%u\n", tdev->cert_slot);
+
+	tsm_dev_put(tdev);
+	return ret;
+}
+
+static DEVICE_ATTR_RW(tsm_cert_slot);
+
+static ssize_t tsm_tc_mask_store(struct device *dev, struct device_attribute *attr,
+				 const char *buf, size_t count)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	ssize_t ret = count;
+	unsigned long val;
+
+	if (kstrtoul(buf, 0, &val) < 0)
+		ret = -EINVAL;
+	else
+		tdev->tc_mask = val;
+	tsm_dev_put(tdev);
+
+	return ret;
+}
+
+static ssize_t tsm_tc_mask_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	ssize_t ret = sysfs_emit(buf, "%#x\n", tdev->tc_mask);
+
+	tsm_dev_put(tdev);
+	return ret;
+}
+
+static DEVICE_ATTR_RW(tsm_tc_mask);
+
+static ssize_t tsm_dev_connect_store(struct device *dev, struct device_attribute *attr,
+				     const char *buf, size_t count)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	unsigned long val;
+	ssize_t ret = -EIO;
+
+	if (kstrtoul(buf, 0, &val) < 0)
+		ret = -EINVAL;
+	else if (val && !tdev->connected)
+		ret = tsm_dev_connect(tdev, tsm.private_data, val);
+	else if (!val && tdev->connected)
+		ret = tsm_dev_reclaim(tdev, tsm.private_data);
+
+	if (!ret)
+		ret = count;
+
+	tsm_dev_put(tdev);
+
+	return ret;
+}
+
+static ssize_t tsm_dev_connect_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	ssize_t ret = sysfs_emit(buf, "%u\n", tdev->connected);
+
+	tsm_dev_put(tdev);
+	return ret;
+}
+
+static DEVICE_ATTR_RW(tsm_dev_connect);
+
+static ssize_t tsm_sel_stream_store(struct device *dev, struct device_attribute *attr,
+				    const char *buf, size_t count)
+{
+	unsigned int ide_dev = false, tee_dev = true, ide_rp = true, tee_rp = false;
+	unsigned int sel_index, id, def, en;
+	struct tsm_dev *tdev;
+
+	if (sscanf(buf, "%u %u %u %u %u %u %u %u", &sel_index, &id, &def, &en,
+		   &ide_dev, &tee_dev, &ide_rp, &tee_rp) != 8) {
+		if (sscanf(buf, "%u %u %u %u", &sel_index, &id, &def, &en) != 4)
+			return -EINVAL;
+	}
+
+	if (sel_index >= ARRAY_SIZE(tdev->selective_ide) || id > 0x100)
+		return -EINVAL;
+
+	tdev = tsm_dev_get(dev);
+	if (en) {
+		tdev->selective_ide[sel_index].id = id;
+		tdev->selective_ide[sel_index].def = def;
+		tdev->selective_ide[sel_index].enable = 1;
+		tdev->selective_ide[sel_index].enabled = 0;
+		tdev->selective_ide[sel_index].dev_ide_cfg = ide_dev;
+		tdev->selective_ide[sel_index].dev_tee_limited = tee_dev;
+		tdev->selective_ide[sel_index].rootport_ide_cfg = ide_rp;
+		tdev->selective_ide[sel_index].rootport_tee_limited = tee_rp;
+	} else {
+		memset(&tdev->selective_ide[sel_index], 0, sizeof(tdev->selective_ide[0]));
+	}
+
+	tsm_dev_put(tdev);
+	return count;
+}
+
+static ssize_t tsm_sel_stream_show(struct device *dev, struct device_attribute *attr,
+				   char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	struct pci_dev *rootport = tdev->pdev->bus->self;
+	unsigned int i;
+	char *buf1;
+	ssize_t ret = 0, sz = PAGE_SIZE;
+
+	buf1 = kmalloc(sz, GFP_KERNEL);
+	if (!buf1)
+		return -ENOMEM;
+
+	buf1[0] = 0;
+	for (i = 0; i < ARRAY_SIZE(tdev->selective_ide); ++i) {
+		if (!tdev->selective_ide[i].enable)
+			continue;
+
+		ret += snprintf(buf1 + ret, sz - ret - 1, "%u: %d%s",
+				i,
+				tdev->selective_ide[i].id,
+				tdev->selective_ide[i].def ? " DEF" : "");
+		if (tdev->selective_ide[i].enabled) {
+			u32 devst = 0, rcst = 0;
+
+			pci_ide_get_sel_sta(tdev->pdev, i, &devst);
+			pci_ide_get_sel_sta(rootport, i, &rcst);
+			ret += snprintf(buf1 + ret, sz - ret - 1,
+				" %x%s %s%s<-> %x%s %s%s rootport:%s",
+				devst,
+				PCI_IDE_SEL_STS_STATUS(devst) == 2 ? "=SECURE" : "",
+				tdev->selective_ide[i].dev_ide_cfg ? "IDECfg " : "",
+				tdev->selective_ide[i].dev_tee_limited ? "TeeLim " : "",
+				rcst,
+				PCI_IDE_SEL_STS_STATUS(rcst) == 2 ? "=SECURE" : "",
+				tdev->selective_ide[i].rootport_ide_cfg ? "IDECfg " : "",
+				tdev->selective_ide[i].rootport_tee_limited ? "TeeLim " : "",
+				pci_name(rootport)
+			       );
+		}
+		ret += snprintf(buf1 + ret, sz - ret - 1, "\n");
+	}
+	tsm_dev_put(tdev);
+
+	ret = sysfs_emit(buf, buf1);
+	kfree(buf1);
+
+	return ret;
+}
+
+static DEVICE_ATTR_RW(tsm_sel_stream);
+
+static ssize_t tsm_ide_refresh_store(struct device *dev, struct device_attribute *attr,
+				     const char *buf, size_t count)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	int ret;
+
+	ret = tsm_ide_refresh(tdev, tsm.private_data);
+	tsm_dev_put(tdev);
+	if (ret)
+		return ret;
+
+	return count;
+}
+
+static DEVICE_ATTR_WO(tsm_ide_refresh);
+
+static ssize_t blob_show(struct tsm_blob *blob, char *buf)
+{
+	unsigned int n, m;
+
+	if (!blob)
+		return sysfs_emit(buf, "none\n");
+
+	n = snprintf(buf, PAGE_SIZE, "%lu %u\n", blob->len,
+		     kref_read(&blob->kref));
+	m = hex_dump_to_buffer(blob->data, blob->len, 32, 1,
+			       buf + n, PAGE_SIZE - n, false);
+	n += min(PAGE_SIZE - n, m);
+	n += snprintf(buf + n, PAGE_SIZE - n, "...\n");
+	return n;
+}
+
+static ssize_t tsm_certs_gen(struct tsm_blob *certs, char *buf, size_t len)
+{
+	struct spdm_certchain_block_header *h;
+	unsigned int n = 0, m, i, off, o2;
+	u8 *p;
+
+	for (i = 0, off = 0; off < certs->len; ++i) {
+		h = (struct spdm_certchain_block_header *) ((u8 *)certs->data + off);
+		if (WARN_ON_ONCE(h->length > certs->len - off))
+			return 0;
+
+		n += snprintf(buf + n, len - n, "[%d] len=%d:\n", i, h->length);
+
+		for (o2 = 0, p = (u8 *)&h[1]; o2 < h->length; o2 += 32) {
+			m = hex_dump_to_buffer(p + o2, h->length - o2, 32, 1,
+					       buf + n, len - n, true);
+			n += min(len - n, m);
+			n += snprintf(buf + n, len - n, "\n");
+		}
+
+		off += h->length; /* Includes the header */
+	}
+
+	return n;
+}
+
+static ssize_t tsm_certs_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	ssize_t n = 0;
+
+	if (!tdev->certs) {
+		n = sysfs_emit(buf, "none\n");
+	} else {
+		n = tsm_certs_gen(tdev->certs, buf, PAGE_SIZE);
+		if (!n)
+			n = blob_show(tdev->certs, buf);
+	}
+
+	tsm_dev_put(tdev);
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_certs);
+
+static ssize_t tsm_meas_gen(struct tsm_blob *meas, char *buf, size_t len)
+{
+	static const char * const whats[] = {
+		"ImmuROM", "MutFW", "HWCfg", "FWCfg",
+		"MeasMft", "DevDbg", "MutFWVer", "MutFWVerSec"
+	};
+	struct dmtf_measurement_block_device_mode *dm;
+	struct spdm_measurement_block_header *mb;
+	struct dmtf_measurement_block_header *h;
+	unsigned int n = 0, m, off, what;
+	bool dmtf;
+
+	for (off = 0; off < meas->len; ) {
+		mb = (struct spdm_measurement_block_header *)(((u8 *) meas->data) + off);
+		dmtf = mb->spec & 1;
+
+		n += snprintf(buf + n, len - n, "#%d (%d) ", mb->index, mb->size);
+		if (dmtf) {
+			h = (void *) &mb[1];
+
+			if (WARN_ON_ONCE(mb->size != (sizeof(*h) + h->size)))
+				return -EINVAL;
+
+			what = h->type & 0x7F;
+			n += snprintf(buf + n, len - n, "%x=[%s %s]: ",
+				h->type,
+				h->type & 0x80 ? "digest" : "raw",
+				what < ARRAY_SIZE(whats) ? whats[what] : "reserved");
+
+			if (what == 5) {
+				dm = (struct dmtf_measurement_block_device_mode *) &h[1];
+				n += snprintf(buf + n, len - n, " %x %x %x %x",
+					      dm->opmode_cap, dm->opmode_sta,
+					      dm->devmode_cap, dm->devmode_sta);
+			} else {
+				m = hex_dump_to_buffer(&h[1], h->size, 32, 1,
+						       buf + n, len - n, false);
+				n += min(PAGE_SIZE - n, m);
+			}
+		} else {
+			n += snprintf(buf + n, len - n, "spec=%x: ", mb->spec);
+			m = hex_dump_to_buffer(&mb[1], min(len - off, mb->size),
+					       32, 1, buf + n, len - n, false);
+			n += min(PAGE_SIZE - n, m);
+		}
+
+		off += sizeof(*mb) + mb->size;
+		n += snprintf(buf + n, PAGE_SIZE - n, "...\n");
+	}
+
+	return n;
+}
+
+static ssize_t tsm_meas_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	ssize_t n = 0;
+
+	if (!tdev->meas) {
+		n = sysfs_emit(buf, "none\n");
+	} else {
+		if (!n)
+			n = tsm_meas_gen(tdev->meas, buf, PAGE_SIZE);
+		if (!n)
+			n = blob_show(tdev->meas, buf);
+	}
+
+	tsm_dev_put(tdev);
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_meas);
+
+static ssize_t tsm_dev_status_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+	struct tsm_dev_status s = { 0 };
+	int ret = tsm_dev_status(tdev, tsm.private_data, &s);
+	ssize_t ret1;
+
+	ret1 = sysfs_emit(buf, "ret=%d\n"
+			  "ctx_state=%x\n"
+			  "tc_mask=%x\n"
+			  "certs_slot=%x\n"
+			  "device_id=%x\n"
+			  "segment_id=%x\n"
+			  "no_fw_update=%x\n",
+			  ret,
+			  s.ctx_state,
+			  s.tc_mask,
+			  s.certs_slot,
+			  s.device_id,
+			  s.segment_id,
+			  s.no_fw_update);
+
+	tsm_dev_put(tdev);
+	return ret1;
+}
+
+static DEVICE_ATTR_RO(tsm_dev_status);
+
+static struct attribute *host_dev_attrs[] = {
+	&dev_attr_tsm_cert_slot.attr,
+	&dev_attr_tsm_tc_mask.attr,
+	&dev_attr_tsm_dev_connect.attr,
+	&dev_attr_tsm_sel_stream.attr,
+	&dev_attr_tsm_ide_refresh.attr,
+	&dev_attr_tsm_certs.attr,
+	&dev_attr_tsm_meas.attr,
+	&dev_attr_tsm_dev_status.attr,
+	NULL,
+};
+static const struct attribute_group host_dev_group = {
+	.attrs = host_dev_attrs,
+};
+
+static struct attribute *guest_dev_attrs[] = {
+	&dev_attr_tsm_certs.attr,
+	&dev_attr_tsm_meas.attr,
+	NULL,
+};
+static const struct attribute_group guest_dev_group = {
+	.attrs = guest_dev_attrs,
+};
+
+static ssize_t tsm_tdi_bind_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+
+	if (!tdi->vmid)
+		return sysfs_emit(buf, "not bound\n");
+
+	return sysfs_emit(buf, "VM=%#llx ASID=%d BDFn=%x:%x.%d\n",
+			  tdi->vmid, tdi->asid,
+			  PCI_BUS_NUM(tdi->guest_rid), PCI_SLOT(tdi->guest_rid),
+			  PCI_FUNC(tdi->guest_rid));
+}
+
+static DEVICE_ATTR_RO(tsm_tdi_bind);
+
+static ssize_t tsm_tdi_validate_store(struct device *dev, struct device_attribute *attr,
+				      const char *buf, size_t count)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+	unsigned long val;
+	ssize_t ret;
+
+	if (kstrtoul(buf, 0, &val) < 0)
+		return -EINVAL;
+
+	if (val) {
+		ret = tsm_tdi_validate(tdi, false, tsm.private_data);
+		if (ret)
+			return ret;
+	} else {
+		tsm_tdi_validate(tdi, true, tsm.private_data);
+	}
+
+	tdi->validated = val;
+
+	return count;
+}
+
+static ssize_t tsm_tdi_validate_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+
+	return sysfs_emit(buf, "%u\n", tdi->validated);
+}
+
+static DEVICE_ATTR_RW(tsm_tdi_validate);
+
+ssize_t tsm_report_gen(struct tsm_blob *report, char *buf, size_t len)
+{
+	struct tdi_report_header *h = TDI_REPORT_HDR(report);
+	struct tdi_report_mmio_range *mr = TDI_REPORT_MR_OFF(report);
+	struct tdi_report_footer *f = TDI_REPORT_FTR(report);
+	unsigned int n, m, i;
+
+	n = snprintf(buf, len,
+		     "no_fw_update=%u\ndma_no_pasid=%u\ndma_pasid=%u\nats=%u\nprs=%u\n",
+		     h->no_fw_update, h->dma_no_pasid, h->dma_pasid, h->ats, h->prs);
+	n += snprintf(buf + n, len - n,
+		      "msi_x_message_control=%#04x\nlnr_control=%#04x\n",
+		      h->msi_x_message_control, h->lnr_control);
+	n += snprintf(buf + n, len - n, "tph_control=%#08x\n", h->tph_control);
+
+	for (i = 0; i < h->mmio_range_count; ++i) {
+		n += snprintf(buf + n, len - n,
+			      "[%i] #%u %#016llx +%#lx MSIX%c PBA%c NonTEE%c Upd%c\n",
+			      i, mr[i].range_id, mr[i].first_page << PAGE_SHIFT,
+			      (unsigned long) mr[i].num << PAGE_SHIFT,
+			      mr[i].msix_table ? '+':'-',
+			      mr[i].msix_pba ? '+':'-',
+			      mr[i].is_non_tee_mem ? '+':'-',
+			      mr[i].is_mem_attr_updatable ? '+':'-');
+		if (mr[i].reserved)
+			n += snprintf(buf + n, len - n,
+			      "[%i] WARN: reserved=%#x\n", i, mr[i].range_attributes);
+	}
+
+	if (f->device_specific_info_len) {
+		unsigned int num = report->len - ((u8 *)f->device_specific_info - (u8 *)h);
+
+		num = min(num, f->device_specific_info_len);
+		n += snprintf(buf + n, len - n, "DevSp len=%d%s",
+			f->device_specific_info_len, num ? ": " : "");
+		m = hex_dump_to_buffer(f->device_specific_info, num, 32, 1,
+				       buf + n, len - n, false);
+		n += min(len - n, m);
+		n += snprintf(buf + n, len - n, m ? "\n" : "...\n");
+	}
+
+	return n;
+}
+EXPORT_SYMBOL_GPL(tsm_report_gen);
+
+static ssize_t tsm_report_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+	ssize_t n = 0;
+
+	if (!tdi->report) {
+		n = sysfs_emit(buf, "none\n");
+	} else {
+		if (!n)
+			n = tsm_report_gen(tdi->report, buf, PAGE_SIZE);
+		if (!n)
+			n = blob_show(tdi->report, buf);
+	}
+
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_report);
+
+static char *spdm_algos_to_str(u64 algos, char *buf, size_t len)
+{
+	size_t n = 0;
+
+	buf[0] = 0;
+#define __ALGO(x) do {								\
+		if ((n < len) && (algos & (1ULL << (TSM_TDI_SPDM_ALGOS_##x))))	\
+			n += snprintf(buf + n, len - n, #x" ");			\
+	} while (0)
+
+	__ALGO(DHE_SECP256R1);
+	__ALGO(DHE_SECP384R1);
+	__ALGO(AEAD_AES_128_GCM);
+	__ALGO(AEAD_AES_256_GCM);
+	__ALGO(ASYM_TPM_ALG_RSASSA_3072);
+	__ALGO(ASYM_TPM_ALG_ECDSA_ECC_NIST_P256);
+	__ALGO(ASYM_TPM_ALG_ECDSA_ECC_NIST_P384);
+	__ALGO(HASH_TPM_ALG_SHA_256);
+	__ALGO(HASH_TPM_ALG_SHA_384);
+	__ALGO(KEY_SCHED_SPDM_KEY_SCHEDULE);
+#undef __ALGO
+	return buf;
+}
+
+static const char *tdisp_state_to_str(enum tsm_tdisp_state state)
+{
+	switch (state) {
+#define __ST(x) case TDISP_STATE_##x: return #x
+	case TDISP_STATE_UNAVAIL: return "TDISP state unavailable";
+	__ST(CONFIG_UNLOCKED);
+	__ST(CONFIG_LOCKED);
+	__ST(RUN);
+	__ST(ERROR);
+#undef __ST
+	default: return "unknown";
+	}
+}
+
+static ssize_t tsm_tdi_status_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+	struct tsm_tdi_status ts = { 0 };
+	char algos[256] = "";
+	unsigned int n, m;
+	int ret;
+
+	ret = tsm_tdi_status(tdi, tsm.private_data, &ts);
+	if (ret < 0)
+		return sysfs_emit(buf, "ret=%d\n\n", ret);
+
+	if (!ts.valid)
+		return sysfs_emit(buf, "ret=%d\nstate=%d:%s\n",
+				  ret, ts.state, tdisp_state_to_str(ts.state));
+
+	n = snprintf(buf, PAGE_SIZE,
+		     "ret=%d\n"
+		     "state=%d:%s\n"
+		     "meas_digest_fresh=%x\n"
+		     "meas_digest_valid=%x\n"
+		     "all_request_redirect=%x\n"
+		     "bind_p2p=%x\n"
+		     "lock_msix=%x\n"
+		     "no_fw_update=%x\n"
+		     "cache_line_size=%d\n"
+		     "algos=%#llx:%s\n"
+		     ,
+		     ret,
+		     ts.state, tdisp_state_to_str(ts.state),
+		     ts.meas_digest_fresh,
+		     ts.meas_digest_valid,
+		     ts.all_request_redirect,
+		     ts.bind_p2p,
+		     ts.lock_msix,
+		     ts.no_fw_update,
+		     ts.cache_line_size,
+		     ts.spdm_algos, spdm_algos_to_str(ts.spdm_algos, algos, sizeof(algos) - 1));
+
+	n += snprintf(buf + n, PAGE_SIZE - n, "Certs digest: ");
+	m = hex_dump_to_buffer(ts.certs_digest, sizeof(ts.certs_digest), 32, 1,
+			       buf + n, PAGE_SIZE - n, false);
+	n += min(PAGE_SIZE - n, m);
+	n += snprintf(buf + n, PAGE_SIZE - n, "...\nMeasurements digest: ");
+	m = hex_dump_to_buffer(ts.meas_digest, sizeof(ts.meas_digest), 32, 1,
+			       buf + n, PAGE_SIZE - n, false);
+	n += min(PAGE_SIZE - n, m);
+	n += snprintf(buf + n, PAGE_SIZE - n, "...\nInterface report digest: ");
+	m = hex_dump_to_buffer(ts.interface_report_digest, sizeof(ts.interface_report_digest),
+			       32, 1, buf + n, PAGE_SIZE - n, false);
+	n += min(PAGE_SIZE - n, m);
+	n += snprintf(buf + n, PAGE_SIZE - n, "...\n");
+
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_tdi_status);
+
+static struct attribute *host_tdi_attrs[] = {
+	&dev_attr_tsm_tdi_bind.attr,
+	&dev_attr_tsm_report.attr,
+	&dev_attr_tsm_tdi_status.attr,
+	NULL,
+};
+
+static const struct attribute_group host_tdi_group = {
+	.attrs = host_tdi_attrs,
+};
+
+static struct attribute *guest_tdi_attrs[] = {
+	&dev_attr_tsm_tdi_validate.attr,
+	&dev_attr_tsm_report.attr,
+	&dev_attr_tsm_tdi_status.attr,
+	NULL,
+};
+
+static const struct attribute_group guest_tdi_group = {
+	.attrs = guest_tdi_attrs,
+};
+
+static int tsm_tdi_init(struct tsm_dev *tdev, struct pci_dev *pdev)
+{
+	struct tsm_tdi *tdi;
+	int ret = 0;
+
+	dev_info(&pdev->dev, "Initializing tdi\n");
+	if (!tdev)
+		return -ENODEV;
+
+	tdi = kzalloc(sizeof(*tdi), GFP_KERNEL);
+	if (!tdi)
+		return -ENOMEM;
+
+	/* tsm_dev_get() requires pdev->dev.tdi which is set later */
+	if (!kref_get_unless_zero(&tdev->kref)) {
+		ret = -EPERM;
+		goto free_exit;
+	}
+
+	if (tsm.ops->dev_connect)
+		tdi->ag = &host_tdi_group;
+	else
+		tdi->ag = &guest_tdi_group;
+
+	ret = sysfs_create_link(&pdev->dev.kobj, &tdev->pdev->dev.kobj, "tsm_dev");
+	if (ret)
+		goto free_exit;
+
+	ret = device_add_group(&pdev->dev, tdi->ag);
+	if (ret)
+		goto sysfs_unlink_exit;
+
+	tdi->tdev = tdev;
+	tdi->pdev = pci_dev_get(pdev);
+
+	pdev->dev.tdi_enabled = !pdev->is_physfn || tsm.physfn;
+	pdev->dev.tdi = tdi;
+	pci_info(pdev, "TDI enabled=%d\n", pdev->dev.tdi_enabled);
+
+	return 0;
+
+sysfs_unlink_exit:
+	sysfs_remove_link(&pdev->dev.kobj, "tsm_dev");
+free_exit:
+	kfree(tdi);
+
+	return ret;
+}
+
+static void tsm_tdi_free(struct tsm_tdi *tdi)
+{
+	tsm_dev_put(tdi->tdev);
+
+	pci_dev_put(tdi->pdev);
+
+	device_remove_group(&tdi->pdev->dev, tdi->ag);
+	sysfs_remove_link(&tdi->pdev->dev.kobj, "tsm_dev");
+	tdi->pdev->dev.tdi = NULL;
+	tdi->pdev->dev.tdi_enabled = false;
+	kfree(tdi);
+}
+
+static int tsm_dev_init(struct pci_dev *pdev, struct tsm_dev **ptdev)
+{
+	struct tsm_dev *tdev;
+	int ret = 0;
+
+	dev_info(&pdev->dev, "Initializing tdev\n");
+	tdev = kzalloc(sizeof(*tdev), GFP_KERNEL);
+	if (!tdev)
+		return -ENOMEM;
+
+	kref_init(&tdev->kref);
+	tdev->tc_mask = tsm.tc_mask;
+	tdev->cert_slot = tsm.cert_slot;
+	tdev->pdev = pci_dev_get(pdev);
+	mutex_init(&tdev->spdm_mutex);
+
+	if (tsm.ops->dev_connect)
+		tdev->ag = &host_dev_group;
+	else
+		tdev->ag = &guest_dev_group;
+
+	ret = device_add_group(&pdev->dev, tdev->ag);
+	if (ret)
+		goto free_exit;
+
+	if (tsm.ops->dev_connect) {
+		ret = -EPERM;
+		tdev->pdev = pci_dev_get(pdev);
+		tdev->spdm.doe_mb = pci_find_doe_mailbox(tdev->pdev,
+							 PCI_VENDOR_ID_PCI_SIG,
+							 PCI_DOE_PROTOCOL_CMA_SPDM);
+		if (!tdev->spdm.doe_mb)
+			goto pci_dev_put_exit;
+
+		tdev->spdm.doe_mb_secured = pci_find_doe_mailbox(tdev->pdev,
+								 PCI_VENDOR_ID_PCI_SIG,
+								 PCI_DOE_PROTOCOL_SECURED_CMA_SPDM);
+		if (!tdev->spdm.doe_mb_secured)
+			goto pci_dev_put_exit;
+	}
+
+	*ptdev = tdev;
+	return 0;
+
+pci_dev_put_exit:
+	pci_dev_put(pdev);
+free_exit:
+	kfree(tdev);
+
+	return ret;
+}
+
+static void tsm_dev_free(struct kref *kref)
+{
+	struct tsm_dev *tdev = container_of(kref, struct tsm_dev, kref);
+
+	device_remove_group(&tdev->pdev->dev, tdev->ag);
+
+	if (tdev->connected)
+		tsm_dev_reclaim(tdev, tsm.private_data);
+
+	dev_info(&tdev->pdev->dev, "Freeing TDEV\n");
+	pci_dev_put(tdev->pdev);
+	kfree(tdev);
+}
+
+static int tsm_alloc_device(struct pci_dev *pdev)
+{
+	int ret = 0;
+
+	/* It is guest VM == TVM */
+	if (!tsm.ops->dev_connect) {
+		if (pdev->devcap & PCI_EXP_DEVCAP_TEE_IO) {
+			struct tsm_dev *tdev = NULL;
+
+			ret = tsm_dev_init(pdev, &tdev);
+			if (ret)
+				return ret;
+
+			ret = tsm_tdi_init(tdev, pdev);
+			tsm_dev_put(tdev);
+			return ret;
+		}
+		return 0;
+	}
+
+	if (pdev->is_physfn && (PCI_FUNC(pdev->devfn) == 0) &&
+	    (pdev->devcap & PCI_EXP_DEVCAP_TEE_IO)) {
+		struct tsm_dev *tdev = NULL;
+
+
+		ret = tsm_dev_init(pdev, &tdev);
+		if (ret)
+			return ret;
+
+		ret = tsm_tdi_init(tdev, pdev);
+		tsm_dev_put(tdev);
+		return ret;
+	}
+
+	if (pdev->is_virtfn) {
+		struct pci_dev *pf0 = pci_get_slot(pdev->physfn->bus,
+						   pdev->physfn->devfn & ~7);
+
+		if (pf0 && (pf0->devcap & PCI_EXP_DEVCAP_TEE_IO)) {
+			struct tsm_dev *tdev = tsm_dev_get(&pf0->dev);
+
+			ret = tsm_tdi_init(tdev, pdev);
+			tsm_dev_put(tdev);
+			return ret;
+		}
+	}
+
+	return 0;
+}
+
+static void tsm_dev_freeice(struct device *dev)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+
+	if (!tdi)
+		return;
+
+	tsm_tdi_free(tdi);
+}
+
+static int tsm_pci_bus_notifier(struct notifier_block *nb, unsigned long action, void *data)
+{
+	switch (action) {
+	case BUS_NOTIFY_ADD_DEVICE:
+		tsm_alloc_device(to_pci_dev(data));
+		break;
+	case BUS_NOTIFY_DEL_DEVICE:
+		tsm_dev_freeice(data);
+		break;
+	case BUS_NOTIFY_UNBOUND_DRIVER:
+		tsm_tdi_validate(tsm_tdi_get(data), true, tsm.private_data);
+		break;
+	}
+
+	return NOTIFY_OK;
+}
+
+static struct notifier_block tsm_pci_bus_nb = {
+	.notifier_call = tsm_pci_bus_notifier,
+};
+
+static int __init tsm_init(void)
+{
+	int ret = 0;
+
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION "\n");
+	return ret;
+}
+
+static void __exit tsm_cleanup(void)
+{
+}
+
+void tsm_set_ops(struct tsm_ops *ops, void *private_data)
+{
+	struct pci_dev *pdev = NULL;
+	int ret;
+
+	if (!tsm.ops && ops) {
+		tsm.ops = ops;
+		tsm.private_data = private_data;
+
+		for_each_pci_dev(pdev) {
+			ret = tsm_alloc_device(pdev);
+			if (ret)
+				break;
+		}
+		bus_register_notifier(&pci_bus_type, &tsm_pci_bus_nb);
+	} else {
+		bus_unregister_notifier(&pci_bus_type, &tsm_pci_bus_nb);
+		for_each_pci_dev(pdev)
+			tsm_dev_freeice(&pdev->dev);
+		tsm.ops = ops;
+	}
+}
+EXPORT_SYMBOL_GPL(tsm_set_ops);
+
+int tsm_tdi_bind(struct tsm_tdi *tdi, u32 guest_rid, u64 vmid, u32 asid)
+{
+	int ret;
+
+	if (WARN_ON(!tsm.ops->tdi_bind))
+		return -EPERM;
+
+	tdi->guest_rid = guest_rid;
+	tdi->vmid = vmid;
+	tdi->asid = asid;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = tsm.ops->tdi_bind(tdi, guest_rid, vmid, asid, tsm.private_data);
+		if (ret < 0)
+			break;
+
+		if (!ret)
+			break;
+
+		ret = spdm_forward(&tdi->tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	if (ret) {
+		tsm_tdi_unbind(tdi);
+		return ret;
+	}
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_bind);
+
+void tsm_tdi_unbind(struct tsm_tdi *tdi)
+{
+	tsm_tdi_reclaim(tdi, tsm.private_data);
+	tdi->vmid = 0;
+	tdi->asid = 0;
+	tdi->guest_rid = 0;
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_unbind);
+
+int tsm_guest_request(struct tsm_tdi *tdi, enum tsm_tdisp_state *state, void *req_data)
+{
+	int ret;
+
+	if (!tsm.ops->guest_request)
+		return -EPERM;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = tsm.ops->guest_request(tdi, tdi->guest_rid, tdi->vmid, req_data,
+					     state, tsm.private_data);
+		if (ret <= 0)
+			break;
+
+		ret = spdm_forward(&tdi->tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tsm_guest_request);
+
+struct tsm_tdi *tsm_tdi_find(u32 guest_rid, u64 vmid)
+{
+	struct pci_dev *pdev = NULL;
+	struct tsm_tdi *tdi;
+
+	for_each_pci_dev(pdev) {
+		tdi = tsm_tdi_get(&pdev->dev);
+		if (!tdi)
+			continue;
+
+		if (tdi->vmid == vmid && tdi->guest_rid == guest_rid)
+			return tdi;
+	}
+
+	return NULL;
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_find);
+
+module_init(tsm_init);
+module_exit(tsm_cleanup);
+
+MODULE_VERSION(DRIVER_VERSION);
+MODULE_LICENSE("GPL");
+MODULE_AUTHOR(DRIVER_AUTHOR);
+MODULE_DESCRIPTION(DRIVER_DESC);
diff --git a/Documentation/virt/coco/tsm.rst b/Documentation/virt/coco/tsm.rst
new file mode 100644
index 000000000000..3be6e8491e42
--- /dev/null
+++ b/Documentation/virt/coco/tsm.rst
@@ -0,0 +1,62 @@
+.. SPDX-License-Identifier: GPL-2.0
+
+What it is
+==========
+
+This is for PCI passthrough in confidential computing (CoCo: SEV-SNP, TDX, CoVE).
+Currently passing through PCI devices to a CoCo VM uses SWIOTLB to pre-shared
+memory buffers.
+
+PCIe IDE (Integrity and Data Encryption) and TDISP (TEE Device Interface Security
+Protocol) are protocols to enable encryption over PCIe link and DMA to encrypted
+memory. This doc is focused to DMAing to encrypted VM, the encrypted host memory is
+out of scope.
+
+
+Protocols
+=========
+
+PCIe r6 DOE is a mailbox protocol to read/write object from/to device.
+Objects are of plain SPDM or secure SPDM type. SPDM is responsible for authenticating
+devices, creating a secure link between a device and TSM.
+IDE_KM manages PCIe link encryption keys, it works on top of secure SPDM.
+TDISP manages a passed through PCI function state, also works on top on secure SPDM.
+Additionally, PCIe defines IDE capability which provides the host OS a way
+to enable streams on the PCIe link.
+
+
+TSM module
+==========
+
+This is common place to trigger device authentication and keys management.
+It exposes certificates/measurenets/reports/status via sysfs and provides control
+over the link (limited though by the TSM capabilities).
+A platform is expected to register a specific set of hooks. The same module works
+in host and guest OS, the set of requires platform hooks is quite different.
+
+
+Flow
+====
+
+At the boot time the tsm.ko scans the PCI bus to find and setup TDISP-cabable
+devices; it also listens to hotplug events. If setup was successful, tsm-prefixed
+nodes will appear in sysfs.
+
+Then, the user enables IDE by writing to /sys/bus/pci/devices/0000:e1:00.0/tsm_dev_connect
+and this is how PCIe encryption is enabled.
+
+To pass the device through, a modifined VMM is required.
+
+In the VM, the same tsm.ko loads. In addition to the host's setup, the VM wants
+to receive the report and enable secure DMA or/and secure MMIO, via some VM<->HV
+protocol (such as AMD GHCB). Once this is done, a VM can access validated MMIO
+with the Cbit set and the device can DMA to encrypted memory.
+
+
+References
+==========
+
+[1] TEE Device Interface Security Protocol - TDISP - v2022-07-27
+https://members.pcisig.com/wg/PCI-SIG/document/18268?downloadRevision=21500
+[2] Security Protocol and Data Model (SPDM)
+https://www.dmtf.org/sites/default/files/standards/documents/DSP0274_1.2.1.pdf
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 87d142c1f932..67a9c9daf96d 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -7,6 +7,17 @@ config TSM_REPORTS
 	select CONFIGFS_FS
 	tristate
 
+config TSM
+	tristate "Platform support for TEE Device Interface Security Protocol (TDISP)"
+	default m
+	depends on AMD_MEM_ENCRYPT
+	select PCI_DOE
+	select PCI_IDE
+	help
+	  Add a common place for user visible platform support for PCIe TDISP.
+	  TEE Device Interface Security Protocol (TDISP) from PCI-SIG,
+	  https://pcisig.com/tee-device-interface-security-protocol-tdisp
+
 source "drivers/virt/coco/efi_secret/Kconfig"
 
 source "drivers/virt/coco/sev-guest/Kconfig"

---

## [9] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 08/21] crypto/ccp: Implement SEV TIO firmware interface*

Implement SEV TIO PSP command wrappers in sev-dev-tio.c, these make
SPDM calls and store the data in the SEV-TIO-specific structs.

Implement tsm_ops for the hypervisor, the TSM module will call these
when loaded on the host and its tsm_set_ops() is called. The HV ops
are implemented in sev-dev-tsm.c.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/Makefile      |    2 +
 arch/x86/include/asm/sev.h       |   20 +
 drivers/crypto/ccp/sev-dev-tio.h |  105 ++
 drivers/crypto/ccp/sev-dev.h     |    2 +
 include/linux/psp-sev.h          |   60 +
 drivers/crypto/ccp/sev-dev-tio.c | 1565 ++++++++++++++++++++
 drivers/crypto/ccp/sev-dev-tsm.c |  397 +++++
 drivers/crypto/ccp/sev-dev.c     |   10 +-
 8 files changed, 2159 insertions(+), 2 deletions(-)

diff --git a/drivers/crypto/ccp/Makefile b/drivers/crypto/ccp/Makefile
index 394484929dae..d9871465dd08 100644
--- a/drivers/crypto/ccp/Makefile
+++ b/drivers/crypto/ccp/Makefile
@@ -11,6 +11,8 @@ ccp-$(CONFIG_PCI) += sp-pci.o
 ccp-$(CONFIG_CRYPTO_DEV_SP_PSP) += psp-dev.o \
                                    sev-dev.o \
                                    tee-dev.o \
+				   sev-dev-tio.o \
+				   sev-dev-tsm.o \
                                    platform-access.o \
                                    dbc.o \
                                    hsti.o
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 79bbe2be900e..80d9aa16fe61 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -138,6 +138,14 @@ enum msg_type {
 	SNP_MSG_ABSORB_RSP,
 	SNP_MSG_VMRK_REQ,
 	SNP_MSG_VMRK_RSP,
+	TIO_MSG_TDI_INFO_REQ        = 0x81,
+	TIO_MSG_TDI_INFO_RSP        = 0x01,
+	TIO_MSG_MMIO_VALIDATE_REQ   = 0x82,
+	TIO_MSG_MMIO_VALIDATE_RSP   = 0x02,
+	TIO_MSG_MMIO_CONFIG_REQ     = 0x83,
+	TIO_MSG_MMIO_CONFIG_RSP     = 0x03,
+	TIO_MSG_SDTE_WRITE_REQ      = 0x84,
+	TIO_MSG_SDTE_WRITE_RSP      = 0x04,
 
 	SNP_MSG_TYPE_MAX
 };
@@ -171,6 +179,18 @@ struct sev_guest_platform_data {
 	u64 secrets_gpa;
 };
 
+/* SPDM algorithms used for TDISP, used in TIO_MSG_TDI_INFO_REQ */
+#define TIO_SPDM_ALGOS_DHE_SECP256R1			0
+#define TIO_SPDM_ALGOS_DHE_SECP384R1			1
+#define TIO_SPDM_ALGOS_AEAD_AES_128_GCM			(0<<8)
+#define TIO_SPDM_ALGOS_AEAD_AES_256_GCM			(1<<8)
+#define TIO_SPDM_ALGOS_ASYM_TPM_ALG_RSASSA_3072		(0<<16)
+#define TIO_SPDM_ALGOS_ASYM_TPM_ALG_ECDSA_ECC_NIST_P256	(1<<16)
+#define TIO_SPDM_ALGOS_ASYM_TPM_ALG_ECDSA_ECC_NIST_P384	(2<<16)
+#define TIO_SPDM_ALGOS_HASH_TPM_ALG_SHA_256		(0<<24)
+#define TIO_SPDM_ALGOS_HASH_TPM_ALG_SHA_384		(1<<24)
+#define TIO_SPDM_ALGOS_KEY_SCHED_SPDM_KEY_SCHEDULE	(0ULL<<32)
+
 /*
  * The secrets page contains 96-bytes of reserved field that can be used by
  * the guest OS. The guest OS uses the area to save the message sequence
diff --git a/drivers/crypto/ccp/sev-dev-tio.h b/drivers/crypto/ccp/sev-dev-tio.h
new file mode 100644
index 000000000000..761cc88699c4
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tio.h
@@ -0,0 +1,105 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef __PSP_SEV_TIO_H__
+#define __PSP_SEV_TIO_H__
+
+#include <linux/tsm.h>
+#include <uapi/linux/psp-sev.h>
+
+#if defined(CONFIG_CRYPTO_DEV_SP_PSP) || defined(CONFIG_CRYPTO_DEV_SP_PSP_MODULE)
+
+int sev_tio_cmd_buffer_len(int cmd);
+
+struct sla_addr_t {
+	union {
+		u64 sla;
+		struct {
+			u64 page_type:1;
+			u64 page_size:1;
+			u64 reserved1:10;
+			u64 pfn:40;
+			u64 reserved2:12;
+		};
+	};
+} __packed;
+
+#define SEV_TIO_MAX_COMMAND_LENGTH	128
+#define SEV_TIO_MAX_DATA_LENGTH		256
+
+/* struct tsm_dev::data */
+struct tsm_dev_tio {
+	struct sla_addr_t dev_ctx;
+	struct sla_addr_t req;
+	struct sla_addr_t resp;
+	struct sla_addr_t scratch;
+	struct sla_addr_t output;
+	struct sla_buffer_hdr *reqbuf; /* vmap'ed @req for DOE */
+	struct sla_buffer_hdr *respbuf; /* vmap'ed @resp for DOE */
+
+	int cmd;
+	int psp_ret;
+	u8 cmd_data[SEV_TIO_MAX_COMMAND_LENGTH];
+	u8 data[SEV_TIO_MAX_DATA_LENGTH]; /* Data page for SPDM-aware commands returning some data */
+};
+
+/* struct tsm_tdi::data */
+struct tsm_tdi_tio {
+	struct sla_addr_t tdi_ctx;
+	u64 gctx_paddr;
+
+	u64 vmid;
+	u32 asid;
+};
+
+#define SPDM_DOBJ_ID_NONE		0
+#define SPDM_DOBJ_ID_REQ		1
+#define SPDM_DOBJ_ID_RESP		2
+#define SPDM_DOBJ_ID_CERTIFICATE	4
+#define SPDM_DOBJ_ID_MEASUREMENT	5
+#define SPDM_DOBJ_ID_REPORT		6
+
+void sev_tio_cleanup(void);
+
+void tio_save_output(struct tsm_blob **blob, struct sla_addr_t sla, u32 dobjid);
+
+int sev_tio_status(void);
+int sev_tio_continue(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+
+int sev_tio_dev_measurements(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+int sev_tio_dev_certificates(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+int sev_tio_dev_create(struct tsm_dev_tio *dev_data, u16 device_id, u16 root_port_id,
+		       u8 segment_id);
+int sev_tio_dev_connect(struct tsm_dev_tio *dev_data, u8 tc_mask, u8 cert_slot,
+			struct tsm_spdm *spdm);
+int sev_tio_dev_disconnect(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+int sev_tio_dev_reclaim(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+int sev_tio_dev_status(struct tsm_dev_tio *dev_data, struct tsm_dev_status *status);
+int sev_tio_ide_refresh(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+
+int sev_tio_tdi_create(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data, u16 dev_id,
+		       u8 rseg, u8 rseg_valid);
+void sev_tio_tdi_reclaim(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data);
+int sev_tio_guest_request(void *data, u32 guest_rid, u64 gctx_paddr,
+			  struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+			  struct tsm_spdm *spdm);
+
+int sev_tio_tdi_bind(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		     __u32 guest_rid, u64 gctx_paddr, struct tsm_spdm *spdm);
+int sev_tio_tdi_unbind(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm);
+int sev_tio_tdi_report(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       u64 gctx_paddr, struct tsm_spdm *spdm);
+
+int sev_tio_asid_fence_clear(u16 device_id, u8 segment_id, u64 gctx_paddr, int *psp_ret);
+int sev_tio_asid_fence_status(struct tsm_dev_tio *dev_data, u16 device_id, u8 segment_id,
+			      u32 asid, bool *fenced);
+
+int sev_tio_tdi_info(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		     struct tsm_tdi_status *ts);
+int sev_tio_tdi_status(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm);
+int sev_tio_tdi_status_fin(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+			   enum tsm_tdisp_state *state);
+
+#endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
+
+#endif	/* __PSP_SEV_TIO_H__ */
diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index 59842157e9d1..a74698a1e433 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -67,4 +67,6 @@ void sev_pci_exit(void);
 
 bool sev_version_greater_or_equal(u8 maj, u8 min);
 
+void sev_tsm_set_ops(bool set);
+
 #endif /* __SEV_DEV_H */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 1d63044f66be..adf40e0316dc 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -12,6 +12,7 @@
 #ifndef __PSP_SEV_H__
 #define __PSP_SEV_H__
 
+#include <linux/tsm.h>
 #include <uapi/linux/psp-sev.h>
 
 #define SEV_FW_BLOB_MAX_SIZE	0x4000	/* 16KB */
@@ -109,6 +110,27 @@ enum sev_cmd {
 	SEV_CMD_SNP_VLEK_LOAD		= 0x0CD,
 	SEV_CMD_SNP_FEATURE_INFO	= 0x0CE,
 
+	/* SEV-TIO commands */
+	SEV_CMD_TIO_STATUS		= 0x0D0,
+	SEV_CMD_TIO_INIT		= 0x0D1,
+	SEV_CMD_TIO_DEV_CREATE		= 0x0D2,
+	SEV_CMD_TIO_DEV_RECLAIM		= 0x0D3,
+	SEV_CMD_TIO_DEV_CONNECT		= 0x0D4,
+	SEV_CMD_TIO_DEV_DISCONNECT	= 0x0D5,
+	SEV_CMD_TIO_DEV_STATUS		= 0x0D6,
+	SEV_CMD_TIO_DEV_MEASUREMENTS	= 0x0D7,
+	SEV_CMD_TIO_DEV_CERTIFICATES	= 0x0D8,
+	SEV_CMD_TIO_TDI_CREATE		= 0x0DA,
+	SEV_CMD_TIO_TDI_RECLAIM		= 0x0DB,
+	SEV_CMD_TIO_TDI_BIND		= 0x0DC,
+	SEV_CMD_TIO_TDI_UNBIND		= 0x0DD,
+	SEV_CMD_TIO_TDI_REPORT		= 0x0DE,
+	SEV_CMD_TIO_TDI_STATUS		= 0x0DF,
+	SEV_CMD_TIO_GUEST_REQUEST	= 0x0E0,
+	SEV_CMD_TIO_ASID_FENCE_CLEAR	= 0x0E1,
+	SEV_CMD_TIO_ASID_FENCE_STATUS	= 0x0E2,
+	SEV_CMD_TIO_TDI_INFO		= 0x0E3,
+	SEV_CMD_TIO_ROLL_KEY		= 0x0E4,
 	SEV_CMD_MAX,
 };
 
@@ -147,6 +169,7 @@ struct sev_data_init_ex {
 } __packed;
 
 #define SEV_INIT_FLAGS_SEV_ES	0x01
+#define SEV_INIT_FLAGS_SEV_TIO_EN	BIT(2)
 
 /**
  * struct sev_data_pek_csr - PEK_CSR command parameters
@@ -752,6 +775,11 @@ struct sev_data_snp_guest_request {
 	u64 res_paddr;				/* In */
 } __packed;
 
+struct tio_guest_request {
+	struct sev_data_snp_guest_request data;
+	int fw_err;
+};
+
 /**
  * struct sev_data_snp_init_ex - SNP_INIT_EX structure
  *
@@ -1007,4 +1035,36 @@ static inline void snp_free_firmware_page(void *addr) { }
 
 #endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
 
+/*
+ * TIO_GUEST_REQUEST's TIO_MSG_MMIO_VALIDATE_REQ
+ * encoding for MMIO in RDX:
+ *
+ * ........ ....GGGG GGGGGGGG GGGGGGGG GGGGGGGG GGGGGGGG GGGGOOOO OOOO.rrr
+ * Where:
+ *	G - guest physical address
+ *	O - order of 4K pages
+ *	r - range id == BAR
+ */
+#define MMIO_VALIDATE_GPA(r)      ((r) & 0x000FFFFFFFFFF000ULL)
+#define MMIO_VALIDATE_LEN(r)      (1ULL << (12 + (((r) >> 4) & 0xFF)))
+#define MMIO_VALIDATE_RANGEID(r)  ((r) & 0x7)
+#define MMIO_VALIDATE_RESERVED(r) ((r) & 0xFFF0000000000008ULL)
+
+/* Optional Certificates/measurements/report data from TIO_GUEST_REQUEST */
+struct tio_blob_table_entry {
+	guid_t guid;
+	u32 offset;
+	u32 length;
+};
+
+/* Measurement’s blob: 5caa80c6-12ef-401a-b364-ec59a93abe3f */
+#define TIO_GUID_MEASUREMENTS \
+	GUID_INIT(0x5caa80c6, 0x12ef, 0x401a, 0xb3, 0x64, 0xec, 0x59, 0xa9, 0x3a, 0xbe, 0x3f)
+/* Certificates blob: 078ccb75-2644-49e8-afe7-5686c5cf72f1 */
+#define TIO_GUID_CERTIFICATES \
+	GUID_INIT(0x078ccb75, 0x2644, 0x49e8, 0xaf, 0xe7, 0x56, 0x86, 0xc5, 0xcf, 0x72, 0xf1)
+/* Attestation report: 70dc5b0e-0cc0-4cd5-97bb-ff0ba25bf320 */
+#define TIO_GUID_REPORT \
+	GUID_INIT(0x70dc5b0e, 0x0cc0, 0x4cd5, 0x97, 0xbb, 0xff, 0x0b, 0xa2, 0x5b, 0xf3, 0x20)
+
 #endif	/* __PSP_SEV_H__ */
diff --git a/drivers/crypto/ccp/sev-dev-tio.c b/drivers/crypto/ccp/sev-dev-tio.c
new file mode 100644
index 000000000000..42741b17c747
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tio.c
@@ -0,0 +1,1565 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+// Interface to PSP for CCP/SEV-TIO/SNP-VM
+
+#include <linux/pci.h>
+#include <linux/pci-doe.h>
+#include <linux/tsm.h>
+#include <linux/psp.h>
+#include <linux/file.h>
+#include <linux/vmalloc.h>
+#include <linux/smp.h>
+
+#include <asm/sev-common.h>
+#include <asm/sev.h>
+#include <asm/page.h>
+
+#include "psp-dev.h"
+#include "sev-dev.h"
+#include "sev-dev-tio.h"
+
+#define SLA_PAGE_TYPE_DATA	0
+#define SLA_PAGE_TYPE_SCATTER	1
+#define SLA_PAGE_SIZE_4K	0
+#define SLA_PAGE_SIZE_2M	1
+#define SLA_SZ(s)		((s).page_size == SLA_PAGE_SIZE_2M ? SZ_2M : SZ_4K)
+#define SLA_SCATTER_LEN(s)	(SLA_SZ(s) / sizeof(struct sla_addr_t))
+#define SLA_EOL			((struct sla_addr_t) { .pfn = 0xFFFFFFFFFFUL })
+#define SLA_NULL		((struct sla_addr_t) { 0 })
+#define IS_SLA_NULL(s)		((s).sla == SLA_NULL.sla)
+#define IS_SLA_EOL(s)		((s).sla == SLA_EOL.sla)
+
+/* the BUFFER Structure */
+struct sla_buffer_hdr {
+	u32 capacity_sz;
+	u32 payload_sz; /* The size of BUFFER_PAYLOAD in bytes. Must be multiple of 32B */
+	union {
+		u32 flags;
+		struct {
+			u32 encryption:1;
+		};
+	};
+	u32 reserved1;
+	u8 iv[16];	/* IV used for the encryption of this buffer */
+	u8 authtag[16]; /* Authentication tag for this buffer */
+	u8 reserved2[16];
+} __packed;
+
+struct spdm_dobj_hdr {
+	u32 id;     /* Data object type identifier */
+	u32 length; /* Length of the data object, INCLUDING THIS HEADER. Must be a multiple of 32B */
+	union {
+		u16 ver; /* Version of the data object structure */
+		struct {
+			u8 minor;
+			u8 major;
+		} version;
+	};
+} __packed;
+
+enum spdm_data_type_t {
+	DOBJ_DATA_TYPE_SPDM = 0x1,
+	DOBJ_DATA_TYPE_SECURE_SPDM = 0x2,
+};
+
+struct spdm_dobj_hdr_req {
+	struct spdm_dobj_hdr hdr; /* hdr.id == SPDM_DOBJ_ID_REQ */
+	u8 data_type; /* spdm_data_type_t */
+	u8 reserved2[5];
+} __packed;
+
+struct spdm_dobj_hdr_resp {
+	struct spdm_dobj_hdr hdr; /* hdr.id == SPDM_DOBJ_ID_RESP */
+	u8 data_type; /* spdm_data_type_t */
+	u8 reserved2[5];
+} __packed;
+
+struct spdm_dobj_hdr_cert {
+	struct spdm_dobj_hdr hdr; /* hdr.id == SPDM_DOBJ_ID_CERTIFICATE */
+	u8 reserved1[6];
+	u16 device_id;
+	u8 segment_id;
+	u8 type; /* 1h: SPDM certificate. 0h, 2h–FFh: Reserved. */
+	u8 reserved2[12];
+} __packed;
+
+struct spdm_dobj_hdr_meas {
+	struct spdm_dobj_hdr hdr; /* hdr.id == SPDM_DOBJ_ID_MEASUREMENT */
+	u8 reserved1[6];
+	u16 device_id;
+	u8 segment_id;
+	u8 type; /* 1h: SPDM measurement. 0h, 2h–FFh: Reserved. */
+	u8 reserved2[12];
+} __packed;
+
+struct spdm_dobj_hdr_report {
+	struct spdm_dobj_hdr hdr; /* hdr.id == SPDM_DOBJ_ID_REPORT */
+	u8 reserved1[6];
+	u16 device_id;
+	u8 segment_id;
+	u8 type; /* 1h: TDISP interface report. 0h, 2h–FFh: Reserved */
+	u8 reserved2[12];
+} __packed;
+
+/* Used in all SPDM-aware TIO commands */
+struct spdm_ctrl {
+	struct sla_addr_t req;
+	struct sla_addr_t resp;
+	struct sla_addr_t scratch;
+	struct sla_addr_t output;
+} __packed;
+
+static size_t sla_dobj_id_to_size(u8 id)
+{
+	size_t n;
+
+	BUILD_BUG_ON(sizeof(struct spdm_dobj_hdr_resp) != 0x10);
+	switch (id) {
+	case SPDM_DOBJ_ID_REQ:
+		n = sizeof(struct spdm_dobj_hdr_req);
+		break;
+	case SPDM_DOBJ_ID_RESP:
+		n = sizeof(struct spdm_dobj_hdr_resp);
+		break;
+	case SPDM_DOBJ_ID_CERTIFICATE:
+		n = sizeof(struct spdm_dobj_hdr_cert);
+		break;
+	case SPDM_DOBJ_ID_MEASUREMENT:
+		n = sizeof(struct spdm_dobj_hdr_meas);
+		break;
+	case SPDM_DOBJ_ID_REPORT:
+		n = sizeof(struct spdm_dobj_hdr_report);
+		break;
+	default:
+		WARN_ON(1);
+		n = 0;
+		break;
+	}
+
+	return n;
+}
+
+#define SPDM_DOBJ_HDR_SIZE(hdr)		sla_dobj_id_to_size((hdr)->id)
+#define SPDM_DOBJ_DATA(hdr)		((u8 *)(hdr) + SPDM_DOBJ_HDR_SIZE(hdr))
+#define SPDM_DOBJ_LEN(hdr)		((hdr)->length - SPDM_DOBJ_HDR_SIZE(hdr))
+
+#define sla_to_dobj_resp_hdr(buf)	((struct spdm_dobj_hdr_resp *) \
+					sla_to_dobj_hdr_check((buf), SPDM_DOBJ_ID_RESP))
+#define sla_to_dobj_req_hdr(buf)	((struct spdm_dobj_hdr_req *) \
+					sla_to_dobj_hdr_check((buf), SPDM_DOBJ_ID_REQ))
+
+static struct spdm_dobj_hdr *sla_to_dobj_hdr(struct sla_buffer_hdr *buf)
+{
+	if (!buf)
+		return NULL;
+
+	return (struct spdm_dobj_hdr *) &buf[1];
+}
+
+static struct spdm_dobj_hdr *sla_to_dobj_hdr_check(struct sla_buffer_hdr *buf, u32 check_dobjid)
+{
+	struct spdm_dobj_hdr *hdr = sla_to_dobj_hdr(buf);
+
+	if (hdr && hdr->id == check_dobjid)
+		return hdr;
+
+	pr_err("! ERROR: expected %d, found %d\n", check_dobjid, hdr->id);
+	return NULL;
+}
+
+static void *sla_to_data(struct sla_buffer_hdr *buf, u32 dobjid)
+{
+	struct spdm_dobj_hdr *hdr = sla_to_dobj_hdr(buf);
+
+	if (WARN_ON_ONCE(dobjid != SPDM_DOBJ_ID_REQ && dobjid != SPDM_DOBJ_ID_RESP))
+		return NULL;
+
+	if (!hdr)
+		return NULL;
+
+	return (u8 *) hdr + sla_dobj_id_to_size(dobjid);
+}
+
+/**
+ * struct sev_tio_status - TIO_STATUS command's info_paddr buffer
+ *
+ * @length: Length of this structure in bytes.
+ * @tio_init_done: Indicates TIO_INIT has been invoked
+ * @tio_en: Indicates that SNP_INIT_EX initialized the RMP for SEV-TIO.
+ * @spdm_req_size_min: Minimum SPDM request buffer size in bytes.
+ * @spdm_req_size_max: Maximum SPDM request buffer size in bytes.
+ * @spdm_scratch_size_min: Minimum  SPDM scratch buffer size in bytes.
+ * @spdm_scratch_size_max: Maximum SPDM scratch buffer size in bytes.
+ * @spdm_out_size_min: Minimum SPDM output buffer size in bytes
+ * @spdm_out_size_max: Maximum for the SPDM output buffer size in bytes.
+ * @spdm_rsp_size_min: Minimum SPDM response buffer size in bytes.
+ * @spdm_rsp_size_max: Maximum SPDM response buffer size in bytes.
+ * @devctx_size: Size of a device context buffer in bytes.
+ * @tdictx_size: Size of a TDI context buffer in bytes.
+ */
+struct sev_tio_status {
+	u32 length;
+	union {
+		u32 flags;
+		struct {
+			u32 tio_en:1;
+			u32 tio_init_done:1;
+		};
+	};
+	u32 spdm_req_size_min;
+	u32 spdm_req_size_max;
+	u32 spdm_scratch_size_min;
+	u32 spdm_scratch_size_max;
+	u32 spdm_out_size_min;
+	u32 spdm_out_size_max;
+	u32 spdm_rsp_size_min;
+	u32 spdm_rsp_size_max;
+	u32 devctx_size;
+	u32 tdictx_size;
+};
+
+/**
+ * struct sev_data_tio_status - SEV_CMD_TIO_STATUS command
+ *
+ * @length: Length of this command buffer in bytes
+ * @status_paddr: SPA of the TIO_STATUS structure
+ */
+struct sev_data_tio_status {
+	u32 length;
+	u32 reserved;
+	u64 status_paddr;
+} __packed;
+
+/* TIO_INIT */
+struct sev_data_tio_init {
+	u32 length;
+	u32 reserved[3];
+} __packed;
+
+static struct sev_tio_status *tio_status;
+
+void sev_tio_cleanup(void)
+{
+	kfree(tio_status);
+	tio_status = NULL;
+}
+
+/**
+ * struct sev_data_tio_dev_create - TIO_DEV_CREATE command
+ *
+ * @length: Length in bytes of this command buffer.
+ * @dev_ctx_sla: A scatter list address pointing to a buffer to be used as a device context buffer.
+ * @device_id: The PCIe Routing Identifier of the device to connect to.
+ * @root_port_id: FiXME: The PCIe Routing Identifier of the root port of the device.
+ * @segment_id: The PCIe Segment Identifier of the device to connect to.
+ */
+struct sev_data_tio_dev_create {
+	u32 length;
+	u32 reserved1;
+	struct sla_addr_t dev_ctx_sla;
+	u16 device_id;
+	u16 root_port_id;
+	u8 segment_id;
+	u8 reserved2[11];
+} __packed;
+
+/**
+ * struct sev_data_tio_dev_connect - TIO_DEV_CONNECT
+ *
+ * @length: Length in bytes of this command buffer.
+ * @spdm_ctrl: SPDM control structure defined in Section 5.1.
+ * @device_id: The PCIe Routing Identifier of the device to connect to.
+ * @root_port_id: The PCIe Routing Identifier of the root port of the device.
+ * @segment_id: The PCIe Segment Identifier of the device to connect to.
+ * @dev_ctx_sla: Scatter list address of the device context buffer.
+ * @tc_mask: Bitmask of the traffic classes to initialize for SEV-TIO usage.
+ *           Setting the kth bit of the TC_MASK to 1 indicates that the traffic
+ *           class k will be initialized.
+ * @cert_slot: Slot number of the certificate requested for constructing the SPDM session.
+ * @ide_stream_id: IDE stream IDs to be associated with this device.
+ *                 Valid only if corresponding bit in TC_MASK is set.
+ */
+struct sev_data_tio_dev_connect {
+	u32 length;
+	u32 reserved1;
+	struct spdm_ctrl spdm_ctrl;
+	u8 reserved2[8];
+	struct sla_addr_t dev_ctx_sla;
+	u8 tc_mask;
+	u8 cert_slot;
+	u8 reserved3[6];
+	u8 ide_stream_id[8];
+	u8 reserved4[8];
+} __packed;
+
+/**
+ * struct sev_data_tio_dev_disconnect - TIO_DEV_DISCONNECT
+ *
+ * @length: Length in bytes of this command buffer.
+ * @force: Force device disconnect without SPDM traffic.
+ * @spdm_ctrl: SPDM control structure defined in Section 5.1.
+ * @dev_ctx_sla: Scatter list address of the device context buffer.
+ */
+struct sev_data_tio_dev_disconnect {
+	u32 length;
+	union {
+		u32 flags;
+		struct {
+			u32 force:1;
+		};
+	};
+	struct spdm_ctrl spdm_ctrl;
+	struct sla_addr_t dev_ctx_sla;
+} __packed;
+
+/**
+ * struct sev_data_tio_dev_meas - TIO_DEV_MEASUREMENTS
+ *
+ * @length: Length in bytes of this command buffer
+ * @raw_bitstream: 0: Requests the digest form of the attestation report
+ *                 1: Requests the raw bitstream form of the attestation report
+ * @spdm_ctrl: SPDM control structure defined in Section 5.1.
+ * @dev_ctx_sla: Scatter list address of the device context buffer.
+ */
+struct sev_data_tio_dev_meas {
+	u32 length;
+	union {
+		u32 flags;
+		struct {
+			u32 raw_bitstream:1;
+		};
+	};
+	struct spdm_ctrl spdm_ctrl;
+	struct sla_addr_t dev_ctx_sla;
+} __packed;
+
+/**
+ * struct sev_data_tio_dev_certs - TIO_DEV_CERTIFICATES
+ *
+ * @length: Length in bytes of this command buffer
+ * @spdm_ctrl: SPDM control structure defined in Section 5.1.
+ * @dev_ctx_sla: Scatter list address of the device context buffer.
+ */
+struct sev_data_tio_dev_certs {
+	u32 length;
+	u32 reserved;
+	struct spdm_ctrl spdm_ctrl;
+	struct sla_addr_t dev_ctx_sla;
+} __packed;
+
+/**
+ * struct sev_data_tio_dev_reclaim - TIO_DEV_RECLAIM command
+ *
+ * @length: Length in bytes of this command buffer
+ * @dev_ctx_paddr: SPA of page donated by hypervisor
+ */
+struct sev_data_tio_dev_reclaim {
+	u32 length;
+	u32 reserved;
+	struct sla_addr_t dev_ctx_sla;
+} __packed;
+
+/**
+ * struct sev_tio_dev_status - sev_data_tio_dev_status::status_paddr of
+ * TIO_DEV_STATUS command
+ *
+ */
+struct sev_tio_dev_status {
+	u32 length;
+	u8 ctx_state;
+	u8 reserved1;
+	union {
+		u8 p1;
+		struct {
+			u8 request_pending:1;
+			u8 request_pending_tdi:1;
+		};
+	};
+	u8 certs_slot;
+	u16 device_id;
+	u8 segment_id;
+	u8 tc_mask;
+	u16 request_pending_command;
+	u16 reserved2;
+	struct tdisp_interface_id request_pending_interface_id;
+	union {
+		u8 p2;
+		struct {
+			u8 meas_digest_valid:1;
+			u8 no_fw_update:1;
+		};
+	};
+	u8 reserved3[3];
+	u16 ide_stream_id[8];
+	u8 reserved4[8];
+	u8 certs_digest[48];
+	u8 meas_digest[48];
+} __packed;
+
+/**
+ * struct sev_data_tio_dev_status - TIO_DEV_STATUS command
+ *
+ * @length: Length in bytes of this command buffer
+ * @dev_ctx_paddr: SPA of a device context page
+ * @status_length: Length in bytes of the sev_tio_dev_status buffer
+ * @status_paddr: SPA of the status buffer. See Table 16
+ */
+struct sev_data_tio_dev_status {
+	u32 length;				/* In */
+	u32 reserved;
+	struct sla_addr_t dev_ctx_paddr;		/* In */
+	u32 status_length;			/* In */
+	u64 status_paddr;			/* In */
+} __packed;
+
+/**
+ * struct sev_data_tio_tdi_create - TIO_TDI_CREATE command
+ *
+ * @length: Length in bytes of this command buffer
+ * @spdm_ctrl: SPDM control structure
+ * @dev_ctx_paddr: SPA of a device context page
+ * @tdi_ctx_paddr: SPA of page donated by hypervisor
+ * @interface_id: Interface ID of the TDI as defined by TDISP (host PCIID)
+ */
+struct sev_data_tio_tdi_create {
+	u32 length;				/* In */
+	u32 reserved;
+	struct sla_addr_t dev_ctx_sla;			/* In */
+	struct sla_addr_t tdi_ctx_sla;			/* In */
+	struct tdisp_interface_id interface_id;	/* In */
+	u8 reserved2[12];
+} __packed;
+
+struct sev_data_tio_tdi_reclaim {
+	u32 length;				/* In */
+	u32 reserved;
+	struct sla_addr_t dev_ctx_sla;			/* In */
+	struct sla_addr_t tdi_ctx_sla;			/* In */
+	u64 reserved2;
+} __packed;
+
+/*
+ * struct sev_data_tio_tdi_bind - TIO_TDI_BIND command
+ *
+ * @length: Length in bytes of this command buffer
+ * @spdm_ctrl: SPDM control structure defined in Chapter 2.
+ * @tdi_ctx_paddr: SPA of page donated by hypervisor
+ * @guest_ctx_paddr: SPA of guest context page
+ * @flags:
+ *  4 ALL_REQUEST_REDIRECT Requires ATS translated requests to route through
+ *                         the root complex. Must be 1.
+ *  3 BIND_P2P Enables direct P2P. Must be 0
+ *  2 LOCK_MSIX Lock the MSI-X table and PBA.
+ *  1 CACHE_LINE_SIZE Indicates the cache line size. 0 indicates 64B. 1 indicates 128B.
+ *                    Must be 0.
+ *  0 NO_FW_UPDATE Indicates that no firmware updates are allowed while the interface
+ *                 is locked.
+ * @mmio_reporting_offset: Offset added to the MMIO range addresses in the interface
+ *                         report.
+ * @guest_interface_id: Hypervisor provided identifier used by the guest to identify
+ *                      the TDI in guest messages
+ */
+struct sev_data_tio_tdi_bind {
+	u32 length;				/* In */
+	u32 reserved;
+	struct spdm_ctrl spdm_ctrl;		/* In */
+	struct sla_addr_t dev_ctx_sla;
+	struct sla_addr_t tdi_ctx_sla;
+	u64 gctx_paddr;
+	u16 guest_device_id;
+	union {
+		u16 flags;
+		/* These are TDISP's LOCK_INTERFACE_REQUEST flags */
+		struct {
+			u16 no_fw_update:1;
+			u16 reservedf1:1;
+			u16 lock_msix:1;
+			u16 bind_p2p:1;
+			u16 all_request_redirect:1;
+		};
+	} tdisp_lock_if;
+	u16 reserved2;
+} __packed;
+
+/*
+ * struct sev_data_tio_tdi_unbind - TIO_TDI_UNBIND command
+ *
+ * @length: Length in bytes of this command buffer
+ * @spdm_ctrl: SPDM control structure defined in Chapter 2.
+ * @tdi_ctx_paddr: SPA of page donated by hypervisor
+ */
+struct sev_data_tio_tdi_unbind {
+	u32 length;				/* In */
+	u32 reserved;
+	struct spdm_ctrl spdm_ctrl;		/* In */
+	struct sla_addr_t dev_ctx_sla;
+	struct sla_addr_t tdi_ctx_sla;
+	u64 gctx_paddr;			/* In */
+} __packed;
+
+/*
+ * struct sev_data_tio_tdi_report - TIO_TDI_REPORT command
+ *
+ * @length: Length in bytes of this command buffer
+ * @spdm_ctrl: SPDM control structure defined in Chapter 2.
+ * @dev_ctx_sla: Scatter list address of the device context buffer
+ * @tdi_ctx_paddr: Scatter list address of a TDI context buffer
+ * @guest_ctx_paddr: System physical address of a guest context page
+ */
+struct sev_data_tio_tdi_report {
+	u32 length;
+	u32 reserved;
+	struct spdm_ctrl spdm_ctrl;
+	struct sla_addr_t dev_ctx_sla;
+	struct sla_addr_t tdi_ctx_sla;
+	u64 gctx_paddr;
+} __packed;
+
+struct sev_data_tio_asid_fence_clear {
+	u32 length;				/* In */
+	u32 reserved1;
+	u64 gctx_paddr;			/* In */
+	u16 device_id;
+	u8 segment_id;
+	u8 reserved[13];
+} __packed;
+
+struct sev_data_tio_asid_fence_status {
+	u32 length;				/* In */
+	u32 asid;				/* In */
+	u64 status_pa;
+	u16 device_id;
+	u8 segment_id;
+	u8 reserved[13];
+} __packed;
+
+/**
+ * struct sev_data_tio_guest_request - TIO_GUEST_REQUEST command
+ *
+ * @length: Length in bytes of this command buffer
+ * @spdm_ctrl: SPDM control structure defined in Chapter 2.
+ * @gctx_paddr: system physical address of guest context page
+ * @tdi_ctx_paddr: SPA of page donated by hypervisor
+ * @req_paddr: system physical address of request page
+ * @res_paddr: system physical address of response page
+ */
+struct sev_data_tio_guest_request {
+	u32 length;				/* In */
+	u32 reserved;
+	struct spdm_ctrl spdm_ctrl;		/* In */
+	struct sla_addr_t dev_ctx_sla;
+	struct sla_addr_t tdi_ctx_sla;
+	u64 gctx_paddr;
+	u64 req_paddr;				/* In */
+	u64 res_paddr;				/* In */
+} __packed;
+
+struct sev_data_tio_roll_key {
+	u32 length;				/* In */
+	u32 reserved;
+	struct spdm_ctrl spdm_ctrl;		/* In */
+	struct sla_addr_t dev_ctx_sla;			/* In */
+} __packed;
+
+static struct sla_buffer_hdr *sla_buffer_map(struct sla_addr_t sla)
+{
+	struct sla_buffer_hdr *buf;
+
+	BUILD_BUG_ON(sizeof(struct sla_buffer_hdr) != 0x40);
+	if (IS_SLA_NULL(sla))
+		return NULL;
+
+	if (sla.page_type == SLA_PAGE_TYPE_SCATTER) {
+		struct sla_addr_t *scatter = __va(sla.pfn << PAGE_SHIFT);
+		unsigned int i, npages = 0;
+		struct page **pp;
+
+		for (i = 0; i < SLA_SCATTER_LEN(sla); ++i) {
+			if (WARN_ON_ONCE(SLA_SZ(scatter[i]) > SZ_4K))
+				return NULL;
+
+			if (WARN_ON_ONCE(scatter[i].page_type == SLA_PAGE_TYPE_SCATTER))
+				return NULL;
+
+			if (IS_SLA_EOL(scatter[i])) {
+				npages = i;
+				break;
+			}
+		}
+		if (WARN_ON_ONCE(!npages))
+			return NULL;
+
+		pp = kmalloc_array(npages, sizeof(pp[0]), GFP_KERNEL);
+		if (!pp)
+			return NULL;
+
+		for (i = 0; i < npages; ++i)
+			pp[i] = pfn_to_page(scatter[i].pfn);
+
+		buf = vm_map_ram(pp, npages, 0);
+		kfree(pp);
+	} else {
+		struct page *pg = pfn_to_page(sla.pfn);
+
+		buf = vm_map_ram(&pg, 1, 0);
+	}
+
+	return buf;
+}
+
+static void sla_buffer_unmap(struct sla_addr_t sla, struct sla_buffer_hdr *buf)
+{
+	if (!buf)
+		return;
+
+	if (sla.page_type == SLA_PAGE_TYPE_SCATTER) {
+		struct sla_addr_t *scatter = __va(sla.pfn << PAGE_SHIFT);
+		unsigned int i, npages = 0;
+
+		for (i = 0; i < SLA_SCATTER_LEN(sla); ++i) {
+			if (IS_SLA_EOL(scatter[i])) {
+				npages = i;
+				break;
+			}
+		}
+		if (!npages)
+			return;
+
+		vm_unmap_ram(buf, npages);
+	} else {
+		vm_unmap_ram(buf, 1);
+	}
+}
+
+static void dobj_response_init(struct sla_buffer_hdr *buf)
+{
+	struct spdm_dobj_hdr *dobj = sla_to_dobj_hdr(buf);
+
+	dobj->id = SPDM_DOBJ_ID_RESP;
+	dobj->version.major = 0x1;
+	dobj->version.minor = 0;
+	dobj->length = 0;
+	buf->payload_sz = sla_dobj_id_to_size(dobj->id) + dobj->length;
+}
+
+static void sla_free(struct sla_addr_t sla, size_t len, bool firmware_state)
+{
+	unsigned int npages = PAGE_ALIGN(len) >> PAGE_SHIFT;
+	struct sla_addr_t *scatter = NULL;
+	int ret = 0, i;
+
+	if (IS_SLA_NULL(sla))
+		return;
+
+	if (firmware_state) {
+		if (sla.page_type == SLA_PAGE_TYPE_SCATTER) {
+			scatter = __va(sla.pfn << PAGE_SHIFT);
+
+			for (i = 0; i < npages; ++i) {
+				if (IS_SLA_EOL(scatter[i]))
+					break;
+
+				ret = snp_reclaim_pages(scatter[i].pfn << PAGE_SHIFT, 1, false);
+				if (ret)
+					break;
+			}
+		} else {
+			pr_err("Reclaiming %llx\n", (u64)sla.pfn << PAGE_SHIFT);
+			ret = snp_reclaim_pages(sla.pfn << PAGE_SHIFT, 1, false);
+		}
+	}
+
+	if (WARN_ON(ret))
+		return;
+
+	if (scatter) {
+		for (i = 0; i < npages; ++i) {
+			if (IS_SLA_EOL(scatter[i]))
+				break;
+			free_page((unsigned long)__va(scatter[i].pfn << PAGE_SHIFT));
+		}
+	}
+
+	free_page((unsigned long)__va(sla.pfn << PAGE_SHIFT));
+}
+
+static struct sla_addr_t sla_alloc(size_t len, bool firmware_state)
+{
+	unsigned long i, npages = PAGE_ALIGN(len) >> PAGE_SHIFT;
+	struct sla_addr_t *scatter = NULL;
+	struct sla_addr_t ret = SLA_NULL;
+	struct sla_buffer_hdr *buf;
+	struct page *pg;
+
+	if (npages == 0)
+		return ret;
+
+	if (WARN_ON_ONCE(npages > ((PAGE_SIZE / sizeof(struct sla_addr_t)) + 1)))
+		return ret;
+
+	BUILD_BUG_ON(PAGE_SIZE < SZ_4K);
+
+	if (npages > 1) {
+		pg = alloc_page(GFP_KERNEL | __GFP_ZERO);
+		if (!pg)
+			return SLA_NULL;
+
+		ret.pfn = page_to_pfn(pg);
+		ret.page_size = SLA_PAGE_SIZE_4K;
+		ret.page_type = SLA_PAGE_TYPE_SCATTER;
+
+		scatter = page_to_virt(pg);
+		for (i = 0; i < npages; ++i) {
+			pg = alloc_page(GFP_KERNEL | __GFP_ZERO);
+			if (!pg)
+				goto no_reclaim_exit;
+
+			scatter[i].pfn = page_to_pfn(pg);
+			scatter[i].page_type = SLA_PAGE_TYPE_DATA;
+			scatter[i].page_size = SLA_PAGE_SIZE_4K;
+		}
+		scatter[i] = SLA_EOL;
+	} else {
+		pg = alloc_page(GFP_KERNEL | __GFP_ZERO);
+		if (!pg)
+			return SLA_NULL;
+
+		ret.pfn = page_to_pfn(pg);
+		ret.page_size = SLA_PAGE_SIZE_4K;
+		ret.page_type = SLA_PAGE_TYPE_DATA;
+	}
+
+	buf = sla_buffer_map(ret);
+	if (!buf)
+		goto no_reclaim_exit;
+
+	buf->capacity_sz = (npages << PAGE_SHIFT);
+	sla_buffer_unmap(ret, buf);
+
+	if (firmware_state) {
+		if (scatter) {
+			for (i = 0; i < npages; ++i) {
+				if (rmp_make_private(scatter[i].pfn, 0, PG_LEVEL_4K, 0, true))
+					goto free_exit;
+			}
+		} else {
+			if (rmp_make_private(ret.pfn, 0, PG_LEVEL_4K, 0, true))
+				goto no_reclaim_exit;
+		}
+	}
+
+	return ret;
+
+no_reclaim_exit:
+	firmware_state = false;
+free_exit:
+	sla_free(ret, len, firmware_state);
+	return SLA_NULL;
+}
+
+static void tio_blob_release(struct tsm_blob *b)
+{
+	memset(b->data, 0, b->len);
+}
+
+void tio_save_output(struct tsm_blob **blob, struct sla_addr_t sla, u32 check_dobjid)
+{
+	struct sla_buffer_hdr *buf;
+	struct spdm_dobj_hdr *hdr;
+
+	tsm_blob_put(*blob);
+	*blob = NULL;
+
+	buf = sla_buffer_map(sla);
+	if (!buf)
+		return;
+
+	hdr = sla_to_dobj_hdr_check(buf, check_dobjid);
+	if (hdr)
+		*blob = tsm_blob_new(SPDM_DOBJ_DATA(hdr), hdr->length, tio_blob_release);
+
+	sla_buffer_unmap(sla, buf);
+}
+
+static int sev_tio_do_cmd(int cmd, void *data, size_t data_len, int *psp_ret,
+			  struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	int rc;
+
+	*psp_ret = 0;
+	rc = sev_do_cmd(cmd, data, psp_ret);
+
+	if (WARN_ON(!spdm && !rc && *psp_ret == SEV_RET_SPDM_REQUEST))
+		return -EIO;
+
+	if (spdm && (rc == 0 || rc == -EIO) && *psp_ret == SEV_RET_SPDM_REQUEST) {
+		struct spdm_dobj_hdr_resp *resp_hdr;
+		struct spdm_dobj_hdr_req *req_hdr;
+
+		if (!dev_data->cmd) {
+			if (WARN_ON_ONCE(!data_len || (data_len != *(u32 *) data)))
+				return -EINVAL;
+			if (WARN_ON(data_len > sizeof(dev_data->cmd_data)))
+				return -EFAULT;
+			memcpy(dev_data->cmd_data, data, data_len);
+			memset(&dev_data->cmd_data[data_len], 0xFF,
+			       sizeof(dev_data->cmd_data) - data_len);
+			dev_data->cmd = cmd;
+		}
+
+		req_hdr = sla_to_dobj_req_hdr(dev_data->reqbuf);
+		resp_hdr = sla_to_dobj_resp_hdr(dev_data->respbuf);
+		switch (req_hdr->data_type) {
+		case DOBJ_DATA_TYPE_SPDM:
+			rc = PCI_DOE_PROTOCOL_CMA_SPDM;
+			break;
+		case DOBJ_DATA_TYPE_SECURE_SPDM:
+			rc = PCI_DOE_PROTOCOL_SECURED_CMA_SPDM;
+			break;
+		default:
+			rc = -EINVAL;
+			return rc;
+		}
+		resp_hdr->data_type = req_hdr->data_type;
+		spdm->req_len = req_hdr->hdr.length;
+		spdm->rsp_len = tio_status->spdm_req_size_max -
+			(sla_dobj_id_to_size(SPDM_DOBJ_ID_RESP) + sizeof(struct sla_buffer_hdr));
+	} else if (dev_data && dev_data->cmd) {
+		/* For either error or success just stop the bouncing */
+		memset(dev_data->cmd_data, 0, sizeof(dev_data->cmd_data));
+		dev_data->cmd = 0;
+	}
+
+	return rc;
+}
+
+int sev_tio_continue(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct spdm_dobj_hdr_resp *resp_hdr;
+	int ret;
+
+	if (!dev_data || !dev_data->cmd)
+		return -EINVAL;
+
+	resp_hdr = sla_to_dobj_resp_hdr(dev_data->respbuf);
+	resp_hdr->hdr.length = ALIGN(sla_dobj_id_to_size(SPDM_DOBJ_ID_RESP) + spdm->rsp_len, 32);
+	dev_data->respbuf->payload_sz = resp_hdr->hdr.length;
+
+	ret = sev_tio_do_cmd(dev_data->cmd, dev_data->cmd_data, 0, &dev_data->psp_ret,
+			     dev_data, spdm);
+
+	return ret;
+}
+
+static int spdm_ctrl_init(struct tsm_spdm *spdm, struct spdm_ctrl *ctrl,
+			  struct tsm_dev_tio *dev_data)
+{
+	ctrl->req = dev_data->req;
+	ctrl->resp = dev_data->resp;
+	ctrl->scratch = dev_data->scratch;
+	ctrl->output = dev_data->output;
+
+	spdm->req = sla_to_data(dev_data->reqbuf, SPDM_DOBJ_ID_REQ);
+	spdm->rsp = sla_to_data(dev_data->respbuf, SPDM_DOBJ_ID_RESP);
+	if (!spdm->req || !spdm->rsp)
+		return -EFAULT;
+
+	return 0;
+}
+
+static void spdm_ctrl_free(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	size_t len = tio_status->spdm_req_size_max -
+		(sla_dobj_id_to_size(SPDM_DOBJ_ID_RESP) +
+		 sizeof(struct sla_buffer_hdr));
+
+	sla_buffer_unmap(dev_data->resp, dev_data->respbuf);
+	sla_buffer_unmap(dev_data->req, dev_data->reqbuf);
+	spdm->rsp = NULL;
+	spdm->req = NULL;
+	sla_free(dev_data->req, len, true);
+	sla_free(dev_data->resp, len, false);
+	sla_free(dev_data->scratch, tio_status->spdm_scratch_size_max, true);
+
+	dev_data->req.sla = 0;
+	dev_data->resp.sla = 0;
+	dev_data->scratch.sla = 0;
+	dev_data->respbuf = NULL;
+	dev_data->reqbuf = NULL;
+	sla_free(dev_data->output, tio_status->spdm_out_size_max, true);
+}
+
+static int spdm_ctrl_alloc(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	int ret;
+
+	dev_data->req = sla_alloc(tio_status->spdm_req_size_max, true);
+	dev_data->resp = sla_alloc(tio_status->spdm_req_size_max, false);
+	dev_data->scratch = sla_alloc(tio_status->spdm_scratch_size_max, true);
+	dev_data->output = sla_alloc(tio_status->spdm_out_size_max, true);
+
+	if (IS_SLA_NULL(dev_data->req) || IS_SLA_NULL(dev_data->resp) ||
+	    IS_SLA_NULL(dev_data->scratch) || IS_SLA_NULL(dev_data->dev_ctx)) {
+		ret = -ENOMEM;
+		goto free_spdm_exit;
+	}
+
+	dev_data->reqbuf = sla_buffer_map(dev_data->req);
+	dev_data->respbuf = sla_buffer_map(dev_data->resp);
+	if (!dev_data->reqbuf || !dev_data->respbuf) {
+		ret = -EFAULT;
+		goto free_spdm_exit;
+	}
+
+	dobj_response_init(dev_data->respbuf);
+
+	return 0;
+
+free_spdm_exit:
+	spdm_ctrl_free(dev_data, spdm);
+	return ret;
+}
+
+int sev_tio_status(void)
+{
+	struct sev_data_tio_status data_status = {
+		.length = sizeof(data_status),
+	};
+	int ret = 0, psp_ret = 0;
+
+	if (!sev_version_greater_or_equal(1, 55))
+		return -EPERM;
+
+	WARN_ON(tio_status);
+
+	tio_status = kzalloc(sizeof(*tio_status), GFP_KERNEL);
+	// "8-byte aligned, and does not cross a page boundary"
+	// BUG_ON(tio_status & ~PAGE_MASK > PAGE_SIZE - sizeof(*tio_status));
+
+	if (!tio_status)
+		return -ENOMEM;
+
+	tio_status->length = sizeof(*tio_status);
+	data_status.status_paddr = __psp_pa(tio_status);
+
+	ret = sev_do_cmd(SEV_CMD_TIO_STATUS, &data_status, &psp_ret);
+	if (ret)
+		goto free_exit;
+
+	if (tio_status->flags & 0xFFFFFF00) {
+		ret = -EFAULT;
+		goto free_exit;
+	}
+
+	if (!tio_status->tio_en && !tio_status->tio_init_done) {
+		ret = -ENOENT;
+		goto free_exit;
+	}
+
+	if (tio_status->tio_en && !tio_status->tio_init_done) {
+		struct sev_data_tio_init ti = { .length = sizeof(ti) };
+
+		ret = sev_do_cmd(SEV_CMD_TIO_INIT, &ti, &psp_ret);
+		if (ret)
+			goto free_exit;
+
+		ret = sev_do_cmd(SEV_CMD_TIO_STATUS, &data_status, &psp_ret);
+		if (ret)
+			goto free_exit;
+	}
+
+	pr_notice("SEV-TIO status: EN=%d INIT_DONE=%d rq=%d..%d rs=%d..%d scr=%d..%d out=%d..%d dev=%d tdi=%d\n",
+		  tio_status->tio_en, tio_status->tio_init_done,
+		  tio_status->spdm_req_size_min, tio_status->spdm_req_size_max,
+		  tio_status->spdm_rsp_size_min, tio_status->spdm_rsp_size_max,
+		  tio_status->spdm_scratch_size_min, tio_status->spdm_scratch_size_max,
+		  tio_status->spdm_out_size_min, tio_status->spdm_out_size_max,
+		  tio_status->devctx_size, tio_status->tdictx_size);
+
+	return 0;
+
+free_exit:
+	pr_err("Failed to enable SEV-TIO: ret=%d en=%d initdone=%d SEV=%d\n",
+	       ret, tio_status->tio_en, tio_status->tio_init_done,
+	       boot_cpu_has(X86_FEATURE_SEV));
+	pr_err("Check BIOS for: SMEE, SEV Control, SEV-ES ASID Space Limit=99,\n"
+	       "SNP Memory (RMP Table) Coverage, RMP Coverage for 64Bit MMIO Ranges\n"
+	       "SEV-SNP Support, SEV-TIO Support, PCIE IDE Capability\n");
+	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+		pr_err("mem_encrypt=on is currently broken\n");
+
+	kfree(tio_status);
+	return ret;
+}
+
+int sev_tio_dev_create(struct tsm_dev_tio *dev_data, u16 device_id,
+		       u16 root_port_id, u8 segment_id)
+{
+	struct sev_data_tio_dev_create create = {
+		.length = sizeof(create),
+		.device_id = device_id,
+		.root_port_id = root_port_id,
+		.segment_id = segment_id,
+	};
+
+	dev_data->dev_ctx = sla_alloc(tio_status->devctx_size, true);
+	if (IS_SLA_NULL(dev_data->dev_ctx))
+		return -ENOMEM;
+
+	create.dev_ctx_sla = dev_data->dev_ctx;
+	return sev_tio_do_cmd(SEV_CMD_TIO_DEV_CREATE, &create, sizeof(create),
+			      &dev_data->psp_ret, dev_data, NULL);
+}
+
+int sev_tio_dev_reclaim(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_reclaim r = {
+		.length = sizeof(r),
+		.dev_ctx_sla = dev_data->dev_ctx,
+	};
+	int ret;
+
+	if (IS_SLA_NULL(dev_data->dev_ctx))
+		return 0;
+
+	ret = sev_do_cmd(SEV_CMD_TIO_DEV_RECLAIM, &r, &dev_data->psp_ret);
+
+	sla_free(dev_data->dev_ctx, tio_status->devctx_size, true);
+	dev_data->dev_ctx = SLA_NULL;
+
+	spdm_ctrl_free(dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_dev_connect(struct tsm_dev_tio *dev_data, u8 tc_mask, u8 cert_slot,
+			struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_connect connect = {
+		.length = sizeof(connect),
+		.tc_mask = tc_mask,
+		.cert_slot = cert_slot,
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.ide_stream_id = { 0 },
+	};
+	int ret;
+
+	if (WARN_ON(IS_SLA_NULL(dev_data->dev_ctx)))
+		return -EFAULT;
+	if (!(tc_mask & 1))
+		return -EINVAL;
+
+	ret = spdm_ctrl_alloc(dev_data, spdm);
+	if (ret)
+		return ret;
+	ret = spdm_ctrl_init(spdm, &connect.spdm_ctrl, dev_data);
+	if (ret)
+		return ret;
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_DEV_CONNECT, &connect, sizeof(connect),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_dev_disconnect(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_disconnect dc = {
+		.length = sizeof(dc),
+		.dev_ctx_sla = dev_data->dev_ctx,
+	};
+	int ret;
+
+	if (WARN_ON_ONCE(IS_SLA_NULL(dev_data->dev_ctx)))
+		return -EFAULT;
+
+	ret = spdm_ctrl_init(spdm, &dc.spdm_ctrl, dev_data);
+	if (ret)
+		return ret;
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_DEV_DISCONNECT, &dc, sizeof(dc),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_dev_measurements(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_meas meas = {
+		.length = sizeof(meas),
+		.raw_bitstream = 1,
+	};
+	int ret;
+
+	if (WARN_ON(IS_SLA_NULL(dev_data->dev_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &meas.spdm_ctrl, dev_data);
+	meas.dev_ctx_sla = dev_data->dev_ctx;
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_DEV_MEASUREMENTS, &meas, sizeof(meas),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_dev_certificates(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_certs c = {
+		.length = sizeof(c),
+	};
+	int ret;
+
+	if (WARN_ON(IS_SLA_NULL(dev_data->dev_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &c.spdm_ctrl, dev_data);
+	c.dev_ctx_sla = dev_data->dev_ctx;
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_DEV_CERTIFICATES, &c, sizeof(c),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_dev_status(struct tsm_dev_tio *dev_data, struct tsm_dev_status *s)
+{
+	struct sev_tio_dev_status *status = (struct sev_tio_dev_status *) dev_data->data;
+	struct sev_data_tio_dev_status data_status = {
+		.length = sizeof(data_status),
+		.dev_ctx_paddr = dev_data->dev_ctx,
+		.status_length = sizeof(*status),
+		.status_paddr = __psp_pa(status),
+	};
+	int ret;
+
+	if (!dev_data)
+		return -ENODEV;
+
+	if (IS_SLA_NULL(dev_data->dev_ctx))
+		return -ENXIO;
+
+	memset(status, 0, sizeof(*status));
+
+	ret = sev_do_cmd(SEV_CMD_TIO_DEV_STATUS, &data_status, &dev_data->psp_ret);
+	if (ret)
+		return ret;
+
+	s->ctx_state = status->ctx_state;
+	s->device_id = status->device_id;
+	s->tc_mask = status->tc_mask;
+	memcpy(s->ide_stream_id, status->ide_stream_id, sizeof(status->ide_stream_id));
+	s->certs_slot = status->certs_slot;
+	s->no_fw_update = status->no_fw_update;
+
+	return 0;
+}
+
+int sev_tio_ide_refresh(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_roll_key rk = {
+		.length = sizeof(rk),
+		.dev_ctx_sla = dev_data->dev_ctx,
+	};
+	int ret;
+
+	if (WARN_ON(IS_SLA_NULL(dev_data->dev_ctx)))
+		return -EFAULT;
+
+	ret = spdm_ctrl_init(spdm, &rk.spdm_ctrl, dev_data);
+	if (ret)
+		return ret;
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_ROLL_KEY, &rk, sizeof(rk),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_tdi_create(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data, u16 dev_id,
+		       u8 rseg, u8 rseg_valid)
+{
+	struct sev_data_tio_tdi_create c = {
+		.length = sizeof(c),
+	};
+	int ret;
+
+	if (!dev_data || !tdi_data) /* Device is not "connected" */
+		return -EPERM;
+
+	if (WARN_ON_ONCE(IS_SLA_NULL(dev_data->dev_ctx) || !IS_SLA_NULL(tdi_data->tdi_ctx)))
+		return -EFAULT;
+
+	tdi_data->tdi_ctx = sla_alloc(tio_status->tdictx_size, true);
+	if (IS_SLA_NULL(tdi_data->tdi_ctx))
+		return -ENOMEM;
+
+	c.dev_ctx_sla = dev_data->dev_ctx;
+	c.tdi_ctx_sla = tdi_data->tdi_ctx;
+	c.interface_id.rid = dev_id;
+	c.interface_id.rseg = rseg;
+	c.interface_id.rseg_valid = rseg_valid;
+
+	ret = sev_do_cmd(SEV_CMD_TIO_TDI_CREATE, &c, &dev_data->psp_ret);
+	if (ret)
+		goto free_exit;
+
+	return 0;
+
+free_exit:
+	sla_free(tdi_data->tdi_ctx, tio_status->tdictx_size, true);
+	tdi_data->tdi_ctx = SLA_NULL;
+	return ret;
+}
+
+void sev_tio_tdi_reclaim(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data)
+{
+	struct sev_data_tio_tdi_reclaim r = {
+		.length = sizeof(r),
+	};
+
+	if (WARN_ON(!dev_data || !tdi_data))
+		return;
+	if (IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx))
+		return;
+
+	r.dev_ctx_sla = dev_data->dev_ctx;
+	r.tdi_ctx_sla = tdi_data->tdi_ctx;
+
+	sev_do_cmd(SEV_CMD_TIO_TDI_RECLAIM, &r, &dev_data->psp_ret);
+
+	sla_free(tdi_data->tdi_ctx, tio_status->tdictx_size, true);
+	tdi_data->tdi_ctx = SLA_NULL;
+}
+
+int sev_tio_tdi_bind(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		     __u32 guest_rid, u64 gctx_paddr, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_tdi_bind b = {
+		.length = sizeof(b),
+	};
+	int ret;
+
+	if (WARN_ON_ONCE(IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &b.spdm_ctrl, dev_data);
+	b.dev_ctx_sla = dev_data->dev_ctx;
+	b.tdi_ctx_sla = tdi_data->tdi_ctx;
+	b.guest_device_id = guest_rid;
+	b.gctx_paddr = gctx_paddr;
+
+	tdi_data->gctx_paddr = gctx_paddr;
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_TDI_BIND, &b, sizeof(b),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_tdi_unbind(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_tdi_unbind ub = {
+		.length = sizeof(ub),
+	};
+	int ret;
+
+	if (WARN_ON(!tdi_data || !dev_data))
+		return 0;
+
+	if (WARN_ON(!tdi_data->gctx_paddr))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &ub.spdm_ctrl, dev_data);
+	ub.dev_ctx_sla = dev_data->dev_ctx;
+	ub.tdi_ctx_sla = tdi_data->tdi_ctx;
+	ub.gctx_paddr = tdi_data->gctx_paddr;
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_TDI_UNBIND, &ub, sizeof(ub),
+			     &dev_data->psp_ret, dev_data, spdm);
+	return ret;
+}
+
+int sev_tio_tdi_report(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       u64 gctx_paddr, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_tdi_report r = {
+		.length = sizeof(r),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+		.gctx_paddr = gctx_paddr,
+	};
+	int ret;
+
+	if (WARN_ON_ONCE(IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &r.spdm_ctrl, dev_data);
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_TDI_REPORT, &r, sizeof(r),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+int sev_tio_asid_fence_clear(u16 device_id, u8 segment_id, u64 gctx_paddr, int *psp_ret)
+{
+	struct sev_data_tio_asid_fence_clear c = {
+		.length = sizeof(c),
+		.gctx_paddr = gctx_paddr,
+		.device_id = device_id,
+		.segment_id = segment_id,
+	};
+	int ret;
+
+	ret = sev_do_cmd(SEV_CMD_TIO_ASID_FENCE_CLEAR, &c, psp_ret);
+
+	return ret;
+}
+
+int sev_tio_asid_fence_status(struct tsm_dev_tio *dev_data, u16 device_id, u8 segment_id,
+			      u32 asid, bool *fenced)
+{
+	u64 *status = (u64 *) dev_data->data;
+	struct sev_data_tio_asid_fence_status s = {
+		.length = sizeof(s),
+		.asid = asid,
+		.status_pa = __psp_pa(status),
+		.device_id = device_id,
+		.segment_id = segment_id,
+	};
+	int ret;
+
+	*status = 0;
+
+	ret = sev_do_cmd(SEV_CMD_TIO_ASID_FENCE_STATUS, &s, &dev_data->psp_ret);
+
+	if (ret == SEV_RET_SUCCESS) {
+		switch (*status) {
+		case 0:
+			*fenced = false;
+			break;
+		case 1:
+			*fenced = true;
+			break;
+		default:
+			pr_err("%04x:%x:%x.%d: undefined fence state %#llx\n",
+			       segment_id, PCI_BUS_NUM(device_id),
+			       PCI_SLOT(device_id), PCI_FUNC(device_id), *status);
+			*fenced = true;
+			break;
+		}
+	}
+
+	return ret;
+}
+
+int sev_tio_guest_request(void *data, u32 guest_rid, u64 gctx_paddr,
+			  struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+			  struct tsm_spdm *spdm)
+{
+	struct tio_guest_request *tgr = data;
+	struct sev_data_tio_guest_request gr = {
+		.length = sizeof(gr),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+		.gctx_paddr = tgr->data.gctx_paddr,
+		.req_paddr = tgr->data.req_paddr,
+		.res_paddr = tgr->data.res_paddr,
+	};
+	int ret;
+
+	if (WARN_ON(!tdi_data || !dev_data))
+		return -EINVAL;
+
+	spdm_ctrl_init(spdm, &gr.spdm_ctrl, dev_data);
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_GUEST_REQUEST, &gr, sizeof(gr),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+struct sev_tio_tdi_info_data {
+	u32 length;
+	struct tdisp_interface_id interface_id;
+	union {
+		u32 p1;
+		struct {
+			u32 meas_digest_valid:1;
+			u32 meas_digest_fresh:1;
+		};
+	};
+	union {
+		u32 p2;
+		struct {
+			u32 no_fw_update:1;
+			u32 cache_line_size:1;
+			u32 lock_msix:1;
+			u32 bind_p2p:1;
+			u32 all_request_redirect:1;
+		};
+	};
+	u64 spdm_algos;
+	u8 certs_digest[48];
+	u8 meas_digest[48];
+	u8 interface_report_digest[48];
+	u8 guest_report_id[16];
+} __packed;
+
+struct sev_data_tio_tdi_info {
+	u32 length;
+	u32 reserved1;
+	struct sla_addr_t dev_ctx_sla;
+	struct sla_addr_t tdi_ctx_sla;
+	u32 status_length;
+	u32 reserved2;
+	u64 status_paddr;
+} __packed;
+
+int sev_tio_tdi_info(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		     struct tsm_tdi_status *ts)
+{
+	struct sev_tio_tdi_info_data *data = (struct sev_tio_tdi_info_data *) dev_data->data;
+	struct sev_data_tio_tdi_info info = {
+		.length = sizeof(info),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+		.status_length = sizeof(*data),
+		.status_paddr = __psp_pa(data),
+	};
+	int ret;
+
+	if (IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx))
+		return -ENXIO;
+
+	memset(data, 0, sizeof(*data));
+
+	ret = sev_do_cmd(SEV_CMD_TIO_TDI_INFO, &info, &dev_data->psp_ret);
+	if (ret)
+		return ret;
+
+	ts->id = data->interface_id;
+	ts->meas_digest_valid = data->meas_digest_valid;
+	ts->meas_digest_fresh = data->meas_digest_fresh;
+	ts->no_fw_update = data->no_fw_update;
+	ts->cache_line_size = data->cache_line_size == 0 ? 64 : 128;
+	ts->lock_msix = data->lock_msix;
+	ts->bind_p2p = data->bind_p2p;
+	ts->all_request_redirect = data->all_request_redirect;
+
+#define __ALGO(x, n, y) \
+	((((x) & (0xFFUL << (n))) == TIO_SPDM_ALGOS_##y) ? \
+	 (1ULL << TSM_TDI_SPDM_ALGOS_##y) : 0)
+	ts->spdm_algos =
+		__ALGO(data->spdm_algos, 0, DHE_SECP256R1) |
+		__ALGO(data->spdm_algos, 0, DHE_SECP384R1) |
+		__ALGO(data->spdm_algos, 8, AEAD_AES_128_GCM) |
+		__ALGO(data->spdm_algos, 8, AEAD_AES_256_GCM) |
+		__ALGO(data->spdm_algos, 16, ASYM_TPM_ALG_RSASSA_3072) |
+		__ALGO(data->spdm_algos, 16, ASYM_TPM_ALG_ECDSA_ECC_NIST_P256) |
+		__ALGO(data->spdm_algos, 16, ASYM_TPM_ALG_ECDSA_ECC_NIST_P384) |
+		__ALGO(data->spdm_algos, 24, HASH_TPM_ALG_SHA_256) |
+		__ALGO(data->spdm_algos, 24, HASH_TPM_ALG_SHA_384) |
+		__ALGO(data->spdm_algos, 32, KEY_SCHED_SPDM_KEY_SCHEDULE);
+#undef __ALGO
+	memcpy(ts->certs_digest, data->certs_digest, sizeof(ts->certs_digest));
+	memcpy(ts->meas_digest, data->meas_digest, sizeof(ts->meas_digest));
+	memcpy(ts->interface_report_digest, data->interface_report_digest,
+	       sizeof(ts->interface_report_digest));
+	memcpy(ts->guest_report_id, data->guest_report_id, sizeof(ts->guest_report_id));
+	ts->valid = true;
+
+	return 0;
+}
+
+struct sev_tio_tdi_status_data {
+	u32 length;
+	u8 tdisp_state;
+	u8 reserved1[3];
+} __packed;
+
+struct sev_data_tio_tdi_status {
+	u32 length;
+	u32 reserved1;
+	struct spdm_ctrl spdm_ctrl;
+	struct sla_addr_t dev_ctx_sla;
+	struct sla_addr_t tdi_ctx_sla;
+	u64 status_paddr;
+} __packed;
+
+int sev_tio_tdi_status(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm)
+{
+	struct sev_tio_tdi_status_data *data = (struct sev_tio_tdi_status_data *) dev_data->data;
+	struct sev_data_tio_tdi_status status = {
+		.length = sizeof(status),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+	};
+	int ret;
+
+	if (IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx))
+		return -ENXIO;
+
+	memset(data, 0, sizeof(*data));
+
+	spdm_ctrl_init(spdm, &status.spdm_ctrl, dev_data);
+	status.status_paddr = __psp_pa(data);
+
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_TDI_STATUS, &status, sizeof(status),
+			     &dev_data->psp_ret, dev_data, spdm);
+
+	return ret;
+}
+
+#define TIO_TDISP_STATE_CONFIG_UNLOCKED	0
+#define TIO_TDISP_STATE_CONFIG_LOCKED	1
+#define TIO_TDISP_STATE_RUN		2
+#define TIO_TDISP_STATE_ERROR		3
+
+int sev_tio_tdi_status_fin(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+			   enum tsm_tdisp_state *state)
+{
+	struct sev_tio_tdi_status_data *data = (struct sev_tio_tdi_status_data *) dev_data->data;
+
+	switch (data->tdisp_state) {
+#define __TDISP_STATE(y) case TIO_TDISP_STATE_##y: *state = TDISP_STATE_##y; break
+	__TDISP_STATE(CONFIG_UNLOCKED);
+	__TDISP_STATE(CONFIG_LOCKED);
+	__TDISP_STATE(RUN);
+	__TDISP_STATE(ERROR);
+#undef __TDISP_STATE
+	}
+	memset(dev_data->data, 0, sizeof(dev_data->data));
+
+	return 0;
+}
+
+int sev_tio_cmd_buffer_len(int cmd)
+{
+	switch (cmd) {
+	case SEV_CMD_TIO_STATUS:		return sizeof(struct sev_data_tio_status);
+	case SEV_CMD_TIO_INIT:			return sizeof(struct sev_data_tio_init);
+	case SEV_CMD_TIO_DEV_CREATE:		return sizeof(struct sev_data_tio_dev_create);
+	case SEV_CMD_TIO_DEV_RECLAIM:		return sizeof(struct sev_data_tio_dev_reclaim);
+	case SEV_CMD_TIO_DEV_CONNECT:		return sizeof(struct sev_data_tio_dev_connect);
+	case SEV_CMD_TIO_DEV_DISCONNECT:	return sizeof(struct sev_data_tio_dev_disconnect);
+	case SEV_CMD_TIO_DEV_STATUS:		return sizeof(struct sev_data_tio_dev_status);
+	case SEV_CMD_TIO_DEV_MEASUREMENTS:	return sizeof(struct sev_data_tio_dev_meas);
+	case SEV_CMD_TIO_DEV_CERTIFICATES:	return sizeof(struct sev_data_tio_dev_certs);
+	case SEV_CMD_TIO_TDI_CREATE:		return sizeof(struct sev_data_tio_tdi_create);
+	case SEV_CMD_TIO_TDI_RECLAIM:		return sizeof(struct sev_data_tio_tdi_reclaim);
+	case SEV_CMD_TIO_TDI_BIND:		return sizeof(struct sev_data_tio_tdi_bind);
+	case SEV_CMD_TIO_TDI_UNBIND:		return sizeof(struct sev_data_tio_tdi_unbind);
+	case SEV_CMD_TIO_TDI_REPORT:		return sizeof(struct sev_data_tio_tdi_report);
+	case SEV_CMD_TIO_TDI_STATUS:		return sizeof(struct sev_data_tio_tdi_status);
+	case SEV_CMD_TIO_GUEST_REQUEST:		return sizeof(struct sev_data_tio_guest_request);
+	case SEV_CMD_TIO_ASID_FENCE_CLEAR:	return sizeof(struct sev_data_tio_asid_fence_clear);
+	case SEV_CMD_TIO_ASID_FENCE_STATUS: return sizeof(struct sev_data_tio_asid_fence_status);
+	case SEV_CMD_TIO_TDI_INFO:		return sizeof(struct sev_data_tio_tdi_info);
+	case SEV_CMD_TIO_ROLL_KEY:		return sizeof(struct sev_data_tio_roll_key);
+	default:				return 0;
+	}
+}
diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
new file mode 100644
index 000000000000..a11dea482d4b
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -0,0 +1,397 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+// Interface to CCP/SEV-TIO for generic PCIe TDISP module
+
+#include <linux/pci.h>
+#include <linux/pci-doe.h>
+#include <linux/tsm.h>
+
+#include <linux/smp.h>
+#include <asm/sev-common.h>
+
+#include "psp-dev.h"
+#include "sev-dev.h"
+#include "sev-dev-tio.h"
+
+static int mkret(int ret, struct tsm_dev_tio *dev_data)
+{
+	if (ret)
+		return ret;
+
+	if (dev_data->psp_ret == SEV_RET_SUCCESS)
+		return 0;
+
+	pr_err("PSP returned an error %d\n", dev_data->psp_ret);
+	return -EINVAL;
+}
+
+static int dev_connect(struct tsm_dev *tdev, void *private_data)
+{
+	u16 device_id = pci_dev_id(tdev->pdev);
+	u16 root_port_id = 0; // FIXME: this is NOT PCI id, need to figure out how to calculate this
+	u8 segment_id = tdev->pdev->bus ? pci_domain_nr(tdev->pdev->bus) : 0;
+	struct tsm_dev_tio *dev_data = tdev->data;
+	int ret;
+
+	if (!dev_data) {
+		dev_data = kzalloc(sizeof(*dev_data), GFP_KERNEL);
+		if (!dev_data)
+			return -ENOMEM;
+
+		ret = sev_tio_dev_create(dev_data, device_id, root_port_id, segment_id);
+		if (ret)
+			goto free_exit;
+
+		tdev->data = dev_data;
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_connect(dev_data, tdev->tc_mask, tdev->cert_slot, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		if (ret < 0)
+			goto free_exit;
+
+		tio_save_output(&tdev->certs, dev_data->output, SPDM_DOBJ_ID_CERTIFICATE);
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_DEV_CONNECT) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdev->certs, dev_data->output, SPDM_DOBJ_ID_CERTIFICATE);
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_measurements(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdev->meas, dev_data->output, SPDM_DOBJ_ID_MEASUREMENT);
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_DEV_MEASUREMENTS) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdev->meas, dev_data->output, SPDM_DOBJ_ID_MEASUREMENT);
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_certificates(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdev->certs, dev_data->output, SPDM_DOBJ_ID_CERTIFICATE);
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_DEV_CERTIFICATES) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdev->certs, dev_data->output, SPDM_DOBJ_ID_CERTIFICATE);
+	}
+
+	return 0;
+
+free_exit:
+	sev_tio_dev_reclaim(dev_data, &tdev->spdm);
+	kfree(dev_data);
+
+	return ret;
+}
+
+static int dev_reclaim(struct tsm_dev *tdev, void *private_data)
+{
+	struct tsm_dev_tio *dev_data = tdev->data;
+	int ret;
+
+	if (!dev_data)
+		return -ENODEV;
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_disconnect(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+	} else if (dev_data->cmd == SEV_CMD_TIO_DEV_DISCONNECT) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+	} else {
+		dev_err(&tdev->pdev->dev, "Wrong state, cmd 0x%x in flight\n",
+			dev_data->cmd);
+	}
+
+	ret = sev_tio_dev_reclaim(dev_data, &tdev->spdm);
+	ret = mkret(ret, dev_data);
+
+	tsm_blob_put(tdev->meas);
+	tdev->meas = NULL;
+	tsm_blob_put(tdev->certs);
+	tdev->certs = NULL;
+	kfree(tdev->data);
+	tdev->data = NULL;
+
+	return ret;
+}
+
+static int dev_status(struct tsm_dev *tdev, void *private_data, struct tsm_dev_status *s)
+{
+	struct tsm_dev_tio *dev_data = tdev->data;
+	int ret;
+
+	if (!dev_data)
+		return -ENODEV;
+
+	ret = sev_tio_dev_status(dev_data, s);
+	ret = mkret(ret, dev_data);
+	if (!ret)
+		WARN_ON(s->device_id != pci_dev_id(tdev->pdev));
+
+	return ret;
+}
+
+static int ide_refresh(struct tsm_dev *tdev, void *private_data)
+{
+	struct tsm_dev_tio *dev_data = tdev->data;
+	int ret;
+
+	if (!dev_data)
+		return -ENODEV;
+
+	ret = sev_tio_ide_refresh(dev_data, &tdev->spdm);
+
+	return ret;
+}
+
+static int tdi_reclaim(struct tsm_tdi *tdi, void *private_data)
+{
+	struct tsm_dev_tio *dev_data;
+	int ret;
+
+	if (!tdi->data)
+		return -ENODEV;
+
+	dev_data = tdi->tdev->data;
+	if (tdi->vmid) {
+		if (dev_data->cmd == 0) {
+			ret = sev_tio_tdi_unbind(tdi->tdev->data, tdi->data, &tdi->tdev->spdm);
+			ret = mkret(ret, dev_data);
+			if (ret)
+				return ret;
+		} else if (dev_data->cmd == SEV_CMD_TIO_TDI_UNBIND) {
+			ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+			ret = mkret(ret, dev_data);
+			if (ret)
+				return ret;
+		}
+	}
+
+	/* Reclaim TDI if DEV is connected */
+	if (tdi->tdev->data) {
+		struct tsm_tdi_tio *tdi_data = tdi->data;
+		struct tsm_dev *tdev = tdi->tdev;
+		struct pci_dev *rootport = tdev->pdev->bus->self;
+		u8 segment_id = pci_domain_nr(rootport->bus);
+		u16 device_id = pci_dev_id(rootport);
+		bool fenced = false;
+
+		sev_tio_tdi_reclaim(tdi->tdev->data, tdi->data);
+
+		if (!sev_tio_asid_fence_status(dev_data, device_id, segment_id,
+					       tdi_data->asid, &fenced)) {
+			if (fenced) {
+				ret = sev_tio_asid_fence_clear(device_id, segment_id,
+							       tdi_data->vmid, &dev_data->psp_ret);
+				pci_notice(rootport, "Unfenced VM=%llx ASID=%d ret=%d %d",
+					   tdi_data->vmid, tdi_data->asid, ret,
+					   dev_data->psp_ret);
+			}
+		}
+
+		tsm_blob_put(tdi->report);
+		tdi->report = NULL;
+	}
+
+	kfree(tdi->data);
+	tdi->data = NULL;
+
+	return 0;
+}
+
+static int tdi_create(struct tsm_tdi *tdi)
+{
+	struct tsm_tdi_tio *tdi_data = tdi->data;
+	int ret;
+
+	if (tdi_data)
+		return -EBUSY;
+
+	tdi_data = kzalloc(sizeof(*tdi_data), GFP_KERNEL);
+	if (!tdi_data)
+		return -ENOMEM;
+
+	ret = sev_tio_tdi_create(tdi->tdev->data, tdi_data, pci_dev_id(tdi->pdev),
+				 tdi->rseg, tdi->rseg_valid);
+	if (ret)
+		kfree(tdi_data);
+	else
+		tdi->data = tdi_data;
+
+	return ret;
+}
+
+static int tdi_bind(struct tsm_tdi *tdi, u32 bdfn, u64 vmid, u32 asid, void *private_data)
+{
+	struct tsm_dev_tio *dev_data = tdi->tdev->data;
+	struct tsm_tdi_tio *tdi_data;
+
+	int ret;
+
+	if (!tdi->data) {
+		ret = tdi_create(tdi);
+		if (ret)
+			return ret;
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_tdi_bind(dev_data, tdi->data, bdfn, vmid, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdi->report, dev_data->output, SPDM_DOBJ_ID_REPORT);
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_TDI_BIND) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdi->report, dev_data->output, SPDM_DOBJ_ID_REPORT);
+	}
+
+	tdi_data = tdi->data;
+	tdi_data->vmid = vmid;
+	tdi_data->asid = asid;
+
+	return 0;
+}
+
+static int guest_request(struct tsm_tdi *tdi, u32 guest_rid, u64 kvmid, void *req_data,
+			 enum tsm_tdisp_state *state, void *private_data)
+{
+	struct tsm_dev_tio *dev_data = tdi->tdev->data;
+	struct tio_guest_request *req = req_data;
+	int ret;
+
+	if (!tdi->data)
+		return -EFAULT;
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_guest_request(&req->data, guest_rid, kvmid,
+					    dev_data, tdi->data, &tdi->tdev->spdm);
+		req->fw_err = dev_data->psp_ret;
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+	} else if (dev_data->cmd == SEV_CMD_TIO_GUEST_REQUEST) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+	}
+
+	if (dev_data->cmd == 0 && state) {
+		ret = sev_tio_tdi_status(tdi->tdev->data, tdi->data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+	} else if (dev_data->cmd == SEV_CMD_TIO_TDI_STATUS) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+
+		ret = sev_tio_tdi_status_fin(tdi->tdev->data, tdi->data, state);
+	}
+
+	return ret;
+}
+
+static int tdi_status(struct tsm_tdi *tdi, void *private_data, struct tsm_tdi_status *ts)
+{
+	struct tsm_dev_tio *dev_data = tdi->tdev->data;
+	int ret;
+
+	if (!tdi->data)
+		return -ENODEV;
+
+#if 0 /* Not implemented yet */
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_tdi_info(tdi->tdev->data, tdi->data, ts);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+	}
+#endif
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_tdi_status(tdi->tdev->data, tdi->data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		ret = sev_tio_tdi_status_fin(tdi->tdev->data, tdi->data, &ts->state);
+	} else if (dev_data->cmd == SEV_CMD_TIO_TDI_STATUS) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		ret = sev_tio_tdi_status_fin(tdi->tdev->data, tdi->data, &ts->state);
+	} else {
+		pci_err(tdi->pdev, "Wrong state, cmd 0x%x in flight\n",
+			dev_data->cmd);
+	}
+
+	return ret;
+}
+
+struct tsm_ops sev_tsm_ops = {
+	.dev_connect = dev_connect,
+	.dev_reclaim = dev_reclaim,
+	.dev_status = dev_status,
+	.ide_refresh = ide_refresh,
+	.tdi_bind = tdi_bind,
+	.tdi_reclaim = tdi_reclaim,
+	.guest_request = guest_request,
+	.tdi_status = tdi_status,
+};
+
+void sev_tsm_set_ops(bool set)
+{
+	if (set) {
+		int ret = sev_tio_status();
+
+		if (ret)
+			pr_warn("SEV-TIO STATUS failed with %d\n", ret);
+		else
+			tsm_set_ops(&sev_tsm_ops, NULL);
+	} else {
+		tsm_set_ops(NULL, NULL);
+		sev_tio_cleanup();
+	}
+}
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index a49fe54b8dd8..ce6f327304e0 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -36,6 +36,7 @@
 
 #include "psp-dev.h"
 #include "sev-dev.h"
+#include "sev-dev-tio.h"
 
 #define DEVICE_NAME		"sev"
 #define SEV_FW_FILE		"amd/sev.fw"
@@ -224,7 +225,7 @@ static int sev_cmd_buffer_len(int cmd)
 	case SEV_CMD_SNP_CONFIG:		return sizeof(struct sev_user_data_snp_config);
 	case SEV_CMD_SNP_COMMIT:		return sizeof(struct sev_data_snp_commit);
 	case SEV_CMD_SNP_FEATURE_INFO:		return sizeof(struct sev_data_snp_feature_info);
-	default:				return 0;
+	default:				return sev_tio_cmd_buffer_len(cmd);
 	}
 
 	return 0;
@@ -1033,7 +1034,7 @@ static int __sev_init_ex_locked(int *error)
 		 */
 		data.tmr_address = __pa(sev_es_tmr);
 
-		data.flags |= SEV_INIT_FLAGS_SEV_ES;
+		data.flags |= SEV_INIT_FLAGS_SEV_ES | SEV_INIT_FLAGS_SEV_TIO_EN;
 		data.tmr_len = sev_es_tmr_size;
 	}
 
@@ -2493,6 +2494,10 @@ void sev_pci_init(void)
 
 	atomic_notifier_chain_register(&panic_notifier_list,
 				       &snp_panic_notifier);
+
+	if (cpu_feature_enabled(X86_FEATURE_SEV_SNP))
+		sev_tsm_set_ops(true);
+
 	return;
 
 err:
@@ -2506,6 +2511,7 @@ void sev_pci_exit(void)
 	if (!sev)
 		return;
 
+	sev_tsm_set_ops(false);
 	sev_firmware_shutdown(sev);
 
 	atomic_notifier_chain_unregister(&panic_notifier_list,

---

## [10] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 09/21] kvm: Export kvm_vm_set_mem_attributes*

SEV TIO can enable the private flag in an MMIO region in
runtime when validating MMIO upon the guest's request, this
requires updating the KVM memory attributes information.

Export helper to do so.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/kvm_host.h | 2 ++
 virt/kvm/kvm_main.c      | 4 +++-
 2 files changed, 5 insertions(+), 1 deletion(-)

diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 7ca32dbde575..d004d96c2ace 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2429,6 +2429,8 @@ bool kvm_arch_pre_set_memory_attributes(struct kvm *kvm,
 bool kvm_arch_post_set_memory_attributes(struct kvm *kvm,
 					 struct kvm_gfn_range *range);
 
+int kvm_vm_set_mem_attributes(struct kvm *kvm, gfn_t start, gfn_t end,
+			      unsigned long attributes);
 static inline bool kvm_mem_is_private(struct kvm *kvm, gfn_t gfn)
 {
 	return IS_ENABLED(CONFIG_KVM_PRIVATE_MEM) &&
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 975b287474a8..53a993607651 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -2508,7 +2508,7 @@ static bool kvm_pre_set_memory_attributes(struct kvm *kvm,
 }
 
 /* Set @attributes for the gfn range [@start, @end). */
-static int kvm_vm_set_mem_attributes(struct kvm *kvm, gfn_t start, gfn_t end,
+int kvm_vm_set_mem_attributes(struct kvm *kvm, gfn_t start, gfn_t end,
 				     unsigned long attributes)
 {
 	struct kvm_mmu_notifier_range pre_set_range = {
@@ -2564,6 +2564,8 @@ static int kvm_vm_set_mem_attributes(struct kvm *kvm, gfn_t start, gfn_t end,
 
 	return r;
 }
+EXPORT_SYMBOL_GPL(kvm_vm_set_mem_attributes);
+
 static int kvm_vm_ioctl_set_mem_attributes(struct kvm *kvm,
 					   struct kvm_memory_attributes *attrs)
 {

---

## [11] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 10/21] vfio: Export helper to get vfio_device from fd*

The SEV TIO Bind operation is going to be handled in the KVM
and requires the BDFn of the device being bound, and the only
supplied information is VFIO device fd.

Add helper to convert vfio devfd to a device.

Note that vfio_put_device() is already public (it is "static
inline" wrapper for put_device()).

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/vfio.h     |  1 +
 drivers/vfio/vfio_main.c | 13 +++++++++++++
 2 files changed, 14 insertions(+)

diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index 000a6cab2d31..91fd376ad13e 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -293,6 +293,7 @@ int vfio_mig_get_next_state(struct vfio_device *device,
 
 void vfio_combine_iova_ranges(struct rb_root_cached *root, u32 cur_nodes,
 			      u32 req_nodes);
+struct vfio_device *vfio_file_device(struct file *file);
 
 /*
  * External user API
diff --git a/drivers/vfio/vfio_main.c b/drivers/vfio/vfio_main.c
index a5a62d9d963f..5aa804ff918b 100644
--- a/drivers/vfio/vfio_main.c
+++ b/drivers/vfio/vfio_main.c
@@ -1447,6 +1447,19 @@ void vfio_file_set_kvm(struct file *file, struct kvm *kvm)
 }
 EXPORT_SYMBOL_GPL(vfio_file_set_kvm);
 
+struct vfio_device *vfio_file_device(struct file *filep)
+{
+	struct vfio_device_file *df = filep->private_data;
+
+	if (filep->f_op != &vfio_device_fops)
+		return NULL;
+
+	get_device(&df->device->device);
+
+	return df->device;
+}
+EXPORT_SYMBOL_GPL(vfio_file_device);
+
 /*
  * Sub-module support
  */

---

## [12] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

The SEV TIO spec defines a new TIO_GUEST_MESSAGE message to
provide a secure communication channel between a SNP VM and
the PSP.

The defined messages provide way to read TDI info and do secure
MMIO/DMA setup.

On top of this, GHCB defines an extension to return certificates/
measurements/report and TDI run status to the VM.

The TIO_GUEST_MESSAGE handler also checks if a specific TDI bound
to the VM and exits the KVM to allow the userspace to bind it.

Skip adjust_direct_map() in rmpupdate() for now as it fails on MMIO.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |   2 +
 arch/x86/include/asm/kvm_host.h    |   2 +
 arch/x86/include/asm/sev.h         |   1 +
 arch/x86/include/uapi/asm/svm.h    |   2 +
 arch/x86/kvm/svm/svm.h             |   2 +
 include/linux/kvm_host.h           |   2 +
 include/uapi/linux/kvm.h           |  29 +++
 arch/x86/kvm/svm/sev.c             | 217 ++++++++++++++++++++
 arch/x86/kvm/svm/svm.c             |   3 +
 arch/x86/kvm/x86.c                 |  12 ++
 arch/x86/virt/svm/sev.c            |  23 ++-
 virt/kvm/vfio.c                    | 139 +++++++++++++
 arch/x86/kvm/Kconfig               |   1 +
 13 files changed, 431 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 68ad4f923664..80e8176a4ea0 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -139,6 +139,8 @@ KVM_X86_OP_OPTIONAL(alloc_apic_backing_page)
 KVM_X86_OP_OPTIONAL_RET0(gmem_prepare)
 KVM_X86_OP_OPTIONAL_RET0(private_max_mapping_level)
 KVM_X86_OP_OPTIONAL(gmem_invalidate)
+KVM_X86_OP_OPTIONAL(tsm_bind)
+KVM_X86_OP_OPTIONAL(tsm_unbind)
 
 #undef KVM_X86_OP
 #undef KVM_X86_OP_OPTIONAL
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 4a68cb3eba78..80bdac4e47ac 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1830,6 +1830,8 @@ struct kvm_x86_ops {
 	int (*gmem_prepare)(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 	void (*gmem_invalidate)(kvm_pfn_t start, kvm_pfn_t end);
 	int (*private_max_mapping_level)(struct kvm *kvm, kvm_pfn_t pfn);
+	int (*tsm_bind)(struct kvm *kvm, struct device *dev, u32 guest_rid);
+	void (*tsm_unbind)(struct kvm *kvm, struct device *dev);
 };
 
 struct kvm_x86_nested_ops {
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 80d9aa16fe61..8edd7bccabf2 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -464,6 +464,7 @@ int snp_lookup_rmpentry(u64 pfn, bool *assigned, int *level);
 void snp_dump_hva_rmpentry(unsigned long address);
 int psmash(u64 pfn);
 int rmp_make_private(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immutable);
+int rmp_make_private_mmio(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immutable);
 int rmp_make_shared(u64 pfn, enum pg_level level);
 void snp_leak_pages(u64 pfn, unsigned int npages);
 void kdump_sev_callback(void);
diff --git a/arch/x86/include/uapi/asm/svm.h b/arch/x86/include/uapi/asm/svm.h
index 1814b413fd57..ac90a69e6327 100644
--- a/arch/x86/include/uapi/asm/svm.h
+++ b/arch/x86/include/uapi/asm/svm.h
@@ -116,6 +116,7 @@
 #define SVM_VMGEXIT_AP_CREATE			1
 #define SVM_VMGEXIT_AP_DESTROY			2
 #define SVM_VMGEXIT_SNP_RUN_VMPL		0x80000018
+#define SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST	0x80000020
 #define SVM_VMGEXIT_HV_FEATURES			0x8000fffd
 #define SVM_VMGEXIT_TERM_REQUEST		0x8000fffe
 #define SVM_VMGEXIT_TERM_REASON(reason_set, reason_code)	\
@@ -237,6 +238,7 @@
 	{ SVM_VMGEXIT_GUEST_REQUEST,	"vmgexit_guest_request" }, \
 	{ SVM_VMGEXIT_EXT_GUEST_REQUEST, "vmgexit_ext_guest_request" }, \
 	{ SVM_VMGEXIT_AP_CREATION,	"vmgexit_ap_creation" }, \
+	{ SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST, "vmgexit_sev_tio_guest_request" }, \
 	{ SVM_VMGEXIT_HV_FEATURES,	"vmgexit_hypervisor_feature" }, \
 	{ SVM_EXIT_ERR,         "invalid_guest_state" }
 
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 76107c7d0595..d04d583c1741 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -749,6 +749,8 @@ void sev_snp_init_protected_guest_state(struct kvm_vcpu *vcpu);
 int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 void sev_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn);
+int sev_tsm_bind(struct kvm *kvm, struct device *dev, u32 guest_rid);
+void sev_tsm_unbind(struct kvm *kvm, struct device *dev);
 #else
 static inline struct page *snp_safe_alloc_page_node(int node, gfp_t gfp)
 {
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index d004d96c2ace..fdb331b3e0d3 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2497,5 +2497,7 @@ void kvm_arch_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 				    struct kvm_pre_fault_memory *range);
 #endif
+int kvm_arch_tsm_bind(struct kvm *kvm, struct device *dev, u32 guest_rid);
+void kvm_arch_tsm_unbind(struct kvm *kvm, struct device *dev);
 
 #endif
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 637efc055145..37f76bbdfa9b 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -135,6 +135,17 @@ struct kvm_xen_exit {
 	} u;
 };
 
+struct kvm_user_vmgexit {
+#define KVM_USER_VMGEXIT_TIO_REQ	4
+	__u32 type; /* KVM_USER_VMGEXIT_* type */
+	union {
+		struct {
+			__u32 guest_rid;
+			__u32 ret;
+		} tio_req;
+	};
+} __packed;
+
 #define KVM_S390_GET_SKEYS_NONE   1
 #define KVM_S390_SKEYS_MAX        1048576
 
@@ -178,6 +189,7 @@ struct kvm_xen_exit {
 #define KVM_EXIT_NOTIFY           37
 #define KVM_EXIT_LOONGARCH_IOCSR  38
 #define KVM_EXIT_MEMORY_FAULT     39
+#define KVM_EXIT_VMGEXIT          40
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -446,6 +458,7 @@ struct kvm_run {
 			__u64 gpa;
 			__u64 size;
 		} memory_fault;
+		struct kvm_user_vmgexit vmgexit;
 		/* Fix the size of the union. */
 		char padding[256];
 	};
@@ -1166,6 +1179,22 @@ struct kvm_vfio_spapr_tce {
 	__s32	tablefd;
 };
 
+#define  KVM_DEV_VFIO_DEVICE			2
+#define   KVM_DEV_VFIO_DEVICE_TDI_BIND			1
+#define   KVM_DEV_VFIO_DEVICE_TDI_UNBIND		2
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
 /*
  * KVM_CREATE_VCPU receives as a parameter the vcpu slot, and returns
  * a vcpu fd.
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 9badf4fa7e1d..e36b93b9cc2b 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -20,6 +20,8 @@
 #include <linux/processor.h>
 #include <linux/trace_events.h>
 #include <uapi/linux/sev-guest.h>
+#include <linux/tsm.h>
+#include <linux/pci.h>
 
 #include <asm/pkru.h>
 #include <asm/trapnr.h>
@@ -3413,6 +3415,8 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 		    control->exit_info_1 == control->exit_info_2)
 			goto vmgexit_err;
 		break;
+	case SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST:
+		break;
 	default:
 		reason = GHCB_ERR_INVALID_EVENT;
 		goto vmgexit_err;
@@ -4128,6 +4132,182 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 	return 1; /* resume guest */
 }
 
+static int tio_make_mmio_private(struct vcpu_svm *svm, struct pci_dev *pdev,
+				 phys_addr_t mmio_gpa, phys_addr_t mmio_size,
+				 unsigned int rangeid)
+{
+	int ret = 0;
+
+	if (!mmio_gpa || !mmio_size || mmio_size != pci_resource_len(pdev, rangeid)) {
+		pci_err(pdev, "Invalid MMIO #%d gpa=%llx..%llx\n",
+			rangeid, mmio_gpa, mmio_gpa + mmio_size);
+		return SEV_RET_INVALID_PARAM;
+	}
+
+	/* Could as well exit to the userspace and ioctl(KVM_MEMORY_ATTRIBUTE_PRIVATE) */
+	ret = kvm_vm_set_mem_attributes(svm->vcpu.kvm, mmio_gpa >> PAGE_SHIFT,
+					(mmio_gpa + mmio_size) >> PAGE_SHIFT,
+					KVM_MEMORY_ATTRIBUTE_PRIVATE);
+	if (ret)
+		pci_err(pdev, "Failed to mark MMIO #%d gpa=%llx..%llx as private, ret=%d\n",
+			rangeid, mmio_gpa, mmio_gpa + mmio_size, ret);
+	else
+		pci_notice(pdev, "Marked MMIO#%d gpa=%llx..%llx as private\n",
+			   rangeid, mmio_gpa, mmio_gpa + mmio_size);
+
+	for (phys_addr_t off = 0; off < mmio_size; off += PAGE_SIZE) {
+		ret = rmp_make_private_mmio((pci_resource_start(pdev, rangeid) + off) >> PAGE_SHIFT,
+					    (mmio_gpa + off), PG_LEVEL_4K, svm->asid,
+					    false/*Immutable*/);
+		if (ret)
+			pci_err(pdev, "Failed to map TIO #%d %pR +%llx %llx -> gpa=%llx ret=%d\n",
+				rangeid, pci_resource_n(pdev, rangeid), off, mmio_size,
+				mmio_gpa + off, ret);
+	}
+
+	return SEV_RET_SUCCESS;
+}
+
+static int snp_complete_sev_tio_guest_request(struct kvm_vcpu *vcpu, struct tsm_tdi *tdi)
+{
+	struct vcpu_svm *svm = to_svm(vcpu);
+	struct vmcb_control_area *control = &svm->vmcb->control;
+	struct kvm *kvm = vcpu->kvm;
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
+	enum tsm_tdisp_state state = TDISP_STATE_UNAVAIL;
+	unsigned long exitcode = 0, data_npages;
+	struct tio_guest_request tioreq = { 0 };
+	struct snp_guest_msg_hdr *req_hdr;
+	gpa_t req_gpa, resp_gpa;
+	struct fd sevfd;
+	u64 data_gpa;
+	int ret;
+
+	if (!sev_snp_guest(kvm))
+		return -EINVAL;
+
+	mutex_lock(&sev->guest_req_mutex);
+
+	req_gpa = control->exit_info_1;
+	resp_gpa = control->exit_info_2;
+
+	ret = kvm_read_guest(kvm, req_gpa, sev->guest_req_buf, PAGE_SIZE);
+	if (ret)
+		goto out_unlock;
+
+	tioreq.data.gctx_paddr = __psp_pa(sev->snp_context);
+	tioreq.data.req_paddr = __psp_pa(sev->guest_req_buf);
+	tioreq.data.res_paddr = __psp_pa(sev->guest_resp_buf);
+
+	sevfd = fdget(sev->fd);
+	if (!sevfd.file)
+		goto out_unlock;
+
+	req_hdr = sev->guest_req_buf;
+	if (req_hdr->msg_type == TIO_MSG_MMIO_VALIDATE_REQ) {
+		const u64 raw_gpa = vcpu->arch.regs[VCPU_REGS_RDX];
+
+		ret = tio_make_mmio_private(svm, tdi->pdev,
+					    MMIO_VALIDATE_GPA(raw_gpa),
+					    MMIO_VALIDATE_LEN(raw_gpa),
+					    MMIO_VALIDATE_RANGEID(raw_gpa));
+		if (ret != SEV_RET_SUCCESS)
+			goto put_unlock;
+	}
+
+	ret = tsm_guest_request(tdi,
+				(req_hdr->msg_type == TIO_MSG_TDI_INFO_REQ) ? &state : NULL,
+				&tioreq);
+	if (ret)
+		goto put_unlock;
+
+	struct tio_blob_table_entry t[4] = {
+		{ .guid = TIO_GUID_MEASUREMENTS,
+		  .offset = sizeof(t),
+		  .length = tdi->tdev->meas ? tdi->tdev->meas->len : 0 },
+		{ .guid = TIO_GUID_CERTIFICATES,
+		  .offset = sizeof(t) + t[0].length,
+		  .length = tdi->tdev->certs ? tdi->tdev->certs->len : 0 },
+		{ .guid = TIO_GUID_REPORT,
+		  .offset = sizeof(t) + t[0].length + t[1].length,
+		  .length = tdi->report ? tdi->report->len : 0 },
+		{ .guid.b = { 0 } }
+	};
+	void *tp[4] = {
+		tdi->tdev->meas ? tdi->tdev->meas->data : NULL,
+		tdi->tdev->certs ? tdi->tdev->certs->data  : NULL,
+		tdi->report ? tdi->report->data : NULL
+	};
+
+	data_gpa = vcpu->arch.regs[VCPU_REGS_RAX];
+	data_npages = vcpu->arch.regs[VCPU_REGS_RBX];
+	vcpu->arch.regs[VCPU_REGS_RBX] = PAGE_ALIGN(t[0].length + t[1].length +
+						    t[2].length + sizeof(t)) >> PAGE_SHIFT;
+	if (data_gpa && ((data_npages << PAGE_SHIFT) >= vcpu->arch.regs[VCPU_REGS_RBX])) {
+		if (kvm_write_guest(kvm, data_gpa + 0, &t, sizeof(t)) ||
+		    kvm_write_guest(kvm, data_gpa + t[0].offset, tp[0], t[0].length) ||
+		    kvm_write_guest(kvm, data_gpa + t[1].offset, tp[1], t[1].length) ||
+		    kvm_write_guest(kvm, data_gpa + t[2].offset, tp[2], t[2].length))
+			exitcode = SEV_RET_INVALID_ADDRESS;
+	}
+
+	if (req_hdr->msg_type == TIO_MSG_TDI_INFO_REQ)
+		vcpu->arch.regs[VCPU_REGS_RDX] = state;
+
+	ret = kvm_write_guest(kvm, resp_gpa, sev->guest_resp_buf, PAGE_SIZE);
+	if (ret)
+		goto put_unlock;
+
+	ret = 1; /* Resume guest */
+
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(0, tioreq.fw_err));
+
+put_unlock:
+	fdput(sevfd);
+out_unlock:
+	mutex_unlock(&sev->guest_req_mutex);
+
+	return ret;
+}
+
+static int snp_try_complete_sev_tio_guest_request(struct kvm_vcpu *vcpu)
+{
+	struct kvm_sev_info *sev = &to_kvm_svm(vcpu->kvm)->sev_info;
+	u32 guest_rid = vcpu->arch.regs[VCPU_REGS_RCX];
+	struct tsm_tdi *tdi = tsm_tdi_find(guest_rid, (u64) __psp_pa(sev->snp_context));
+
+	if (!tdi) {
+		pr_err("TDI is not bound to %x:%02x.%d\n",
+		       PCI_BUS_NUM(guest_rid), PCI_SLOT(guest_rid), PCI_FUNC(guest_rid));
+		return 1; /* Resume guest */
+	}
+
+	return snp_complete_sev_tio_guest_request(vcpu, tdi);
+}
+
+static int snp_sev_tio_guest_request(struct kvm_vcpu *vcpu)
+{
+	u32 guest_rid = vcpu->arch.regs[VCPU_REGS_RCX];
+	struct kvm *kvm = vcpu->kvm;
+	struct kvm_sev_info *sev;
+	struct tsm_tdi *tdi;
+
+	if (!sev_snp_guest(kvm))
+		return SEV_RET_INVALID_GUEST;
+
+	sev = &to_kvm_svm(kvm)->sev_info;
+	tdi = tsm_tdi_find(guest_rid, (u64) __psp_pa(sev->snp_context));
+	if (!tdi) {
+		vcpu->run->exit_reason = KVM_EXIT_VMGEXIT;
+		vcpu->run->vmgexit.type = KVM_USER_VMGEXIT_TIO_REQ;
+		vcpu->run->vmgexit.tio_req.guest_rid = guest_rid;
+		vcpu->arch.complete_userspace_io = snp_try_complete_sev_tio_guest_request;
+		return 0; /* Exit KVM */
+	}
+
+	return snp_complete_sev_tio_guest_request(vcpu, tdi);
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4408,6 +4588,9 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 	case SVM_VMGEXIT_EXT_GUEST_REQUEST:
 		ret = snp_handle_ext_guest_req(svm, control->exit_info_1, control->exit_info_2);
 		break;
+	case SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST:
+		ret = snp_sev_tio_guest_request(vcpu);
+		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
 		vcpu_unimpl(vcpu,
 			    "vmgexit: unsupported event - exit_info_1=%#llx, exit_info_2=%#llx\n",
@@ -5000,3 +5183,37 @@ int sev_private_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn)
 
 	return level;
 }
+
+int sev_tsm_bind(struct kvm *kvm, struct device *dev, u32 guest_rid)
+{
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+	struct fd sevfd;
+	int ret;
+
+	if (!tdi)
+		return -ENODEV;
+
+	sevfd = fdget(sev->fd);
+	if (!sevfd.file)
+		return -EPERM;
+
+	dev_info(dev, "Binding guest=%x:%02x.%d\n",
+		 PCI_BUS_NUM(guest_rid), PCI_SLOT(guest_rid), PCI_FUNC(guest_rid));
+	ret = tsm_tdi_bind(tdi, guest_rid, (u64) __psp_pa(sev->snp_context), sev->asid);
+	fdput(sevfd);
+
+	return ret;
+}
+
+void sev_tsm_unbind(struct kvm *kvm, struct device *dev)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(dev);
+
+	if (!tdi)
+		return;
+
+	dev_notice(dev, "Unbinding guest=%x:%02x.%d\n",
+		   PCI_BUS_NUM(tdi->guest_rid), PCI_SLOT(tdi->guest_rid), PCI_FUNC(tdi->guest_rid));
+	tsm_tdi_unbind(tdi);
+}
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index d6f252555ab3..ab6e41eed697 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -5093,6 +5093,9 @@ static struct kvm_x86_ops svm_x86_ops __initdata = {
 
 	.vm_copy_enc_context_from = sev_vm_copy_enc_context_from,
 	.vm_move_enc_context_from = sev_vm_move_enc_context_from,
+
+	.tsm_bind = sev_tsm_bind,
+	.tsm_unbind = sev_tsm_unbind,
 #endif
 	.check_emulate_instruction = svm_check_emulate_instruction,
 
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 70219e406987..97261cffa9ad 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -14055,3 +14055,15 @@ static void __exit kvm_x86_exit(void)
 	WARN_ON_ONCE(static_branch_unlikely(&kvm_has_noapic_vcpu));
 }
 module_exit(kvm_x86_exit);
+
+int kvm_arch_tsm_bind(struct kvm *kvm, struct device *dev, u32 guest_rid)
+{
+	return static_call(kvm_x86_tsm_bind)(kvm, dev, guest_rid);
+}
+EXPORT_SYMBOL_GPL(kvm_arch_tsm_bind);
+
+void kvm_arch_tsm_unbind(struct kvm *kvm, struct device *dev)
+{
+	static_call(kvm_x86_tsm_unbind)(kvm, dev);
+}
+EXPORT_SYMBOL_GPL(kvm_arch_tsm_unbind);
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 44e7609c9bd6..91f5729dfcad 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -945,7 +945,7 @@ static int adjust_direct_map(u64 pfn, int rmp_level)
  * The optimal solution would be range locking to avoid locking disjoint
  * regions unnecessarily but there's no support for that yet.
  */
-static int rmpupdate(u64 pfn, struct rmp_state *state)
+static int rmpupdate(u64 pfn, struct rmp_state *state, bool mmio)
 {
 	unsigned long paddr = pfn << PAGE_SHIFT;
 	int ret, level;
@@ -955,7 +955,7 @@ static int rmpupdate(u64 pfn, struct rmp_state *state)
 
 	level = RMP_TO_PG_LEVEL(state->pagesize);
 
-	if (adjust_direct_map(pfn, level))
+	if (!mmio && adjust_direct_map(pfn, level))
 		return -EFAULT;
 
 	do {
@@ -989,10 +989,25 @@ int rmp_make_private(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immut
 	state.gpa = gpa;
 	state.pagesize = PG_LEVEL_TO_RMP(level);
 
-	return rmpupdate(pfn, &state);
+	return rmpupdate(pfn, &state, false);
 }
 EXPORT_SYMBOL_GPL(rmp_make_private);
 
+int rmp_make_private_mmio(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immutable)
+{
+	struct rmp_state state;
+
+	memset(&state, 0, sizeof(state));
+	state.assigned = 1;
+	state.asid = asid;
+	state.immutable = immutable;
+	state.gpa = gpa;
+	state.pagesize = PG_LEVEL_TO_RMP(level);
+
+	return rmpupdate(pfn, &state, true);
+}
+EXPORT_SYMBOL_GPL(rmp_make_private_mmio);
+
 /* Transition a page to hypervisor-owned/shared state in the RMP table. */
 int rmp_make_shared(u64 pfn, enum pg_level level)
 {
@@ -1001,7 +1016,7 @@ int rmp_make_shared(u64 pfn, enum pg_level level)
 	memset(&state, 0, sizeof(state));
 	state.pagesize = PG_LEVEL_TO_RMP(level);
 
-	return rmpupdate(pfn, &state);
+	return rmpupdate(pfn, &state, false);
 }
 EXPORT_SYMBOL_GPL(rmp_make_shared);
 
diff --git a/virt/kvm/vfio.c b/virt/kvm/vfio.c
index 76b7f6085dcd..a4e9db212adc 100644
--- a/virt/kvm/vfio.c
+++ b/virt/kvm/vfio.c
@@ -15,6 +15,7 @@
 #include <linux/slab.h>
 #include <linux/uaccess.h>
 #include <linux/vfio.h>
+#include <linux/tsm.h>
 #include "vfio.h"
 
 #ifdef CONFIG_SPAPR_TCE_IOMMU
@@ -29,8 +30,14 @@ struct kvm_vfio_file {
 #endif
 };
 
+struct kvm_vfio_tdi {
+	struct list_head node;
+	struct vfio_device *vdev;
+};
+
 struct kvm_vfio {
 	struct list_head file_list;
+	struct list_head tdi_list;
 	struct mutex lock;
 	bool noncoherent;
 };
@@ -80,6 +87,22 @@ static bool kvm_vfio_file_is_valid(struct file *file)
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
 #ifdef CONFIG_SPAPR_TCE_IOMMU
 static struct iommu_group *kvm_vfio_file_iommu_group(struct file *file)
 {
@@ -297,6 +320,103 @@ static int kvm_vfio_set_file(struct kvm_device *dev, long attr,
 	return -ENXIO;
 }
 
+static int kvm_dev_tsm_bind(struct kvm_device *dev, void __user *arg)
+{
+	struct kvm_vfio *kv = dev->private;
+	struct kvm_vfio_tsm_bind tb;
+	struct kvm_vfio_tdi *ktdi;
+	struct vfio_device *vdev;
+	struct fd fdev;
+	int ret;
+
+	if (copy_from_user(&tb, arg, sizeof(tb)))
+		return -EFAULT;
+
+	ktdi = kzalloc(sizeof(*ktdi), GFP_KERNEL_ACCOUNT);
+	if (!ktdi)
+		return -ENOMEM;
+
+	fdev = fdget(tb.devfd);
+	if (!fdev.file)
+		return -EBADF;
+
+	ret = -ENOENT;
+
+	mutex_lock(&kv->lock);
+
+	vdev = kvm_vfio_file_device(fdev.file);
+	if (vdev) {
+		ret = kvm_arch_tsm_bind(dev->kvm, vdev->dev, tb.guest_rid);
+		if (!ret) {
+			ktdi->vdev = vdev;
+			list_add_tail(&ktdi->node, &kv->tdi_list);
+		} else {
+			vfio_put_device(vdev);
+		}
+	}
+
+	fdput(fdev);
+	mutex_unlock(&kv->lock);
+	if (ret)
+		kfree(ktdi);
+
+	return ret;
+}
+
+static int kvm_dev_tsm_unbind(struct kvm_device *dev, void __user *arg)
+{
+	struct kvm_vfio *kv = dev->private;
+	struct kvm_vfio_tsm_bind tb;
+	struct kvm_vfio_tdi *ktdi;
+	struct vfio_device *vdev;
+	struct fd fdev;
+	int ret;
+
+	if (copy_from_user(&tb, arg, sizeof(tb)))
+		return -EFAULT;
+
+	fdev = fdget(tb.devfd);
+	if (!fdev.file)
+		return -EBADF;
+
+	ret = -ENOENT;
+
+	mutex_lock(&kv->lock);
+
+	vdev = kvm_vfio_file_device(fdev.file);
+	if (vdev) {
+		list_for_each_entry(ktdi, &kv->tdi_list, node) {
+			if (ktdi->vdev != vdev)
+				continue;
+
+			kvm_arch_tsm_unbind(dev->kvm, vdev->dev);
+			list_del(&ktdi->node);
+			kfree(ktdi);
+			vfio_put_device(vdev);
+			ret = 0;
+			break;
+		}
+		vfio_put_device(vdev);
+	}
+
+	fdput(fdev);
+	mutex_unlock(&kv->lock);
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
@@ -304,6 +424,9 @@ static int kvm_vfio_set_attr(struct kvm_device *dev,
 	case KVM_DEV_VFIO_FILE:
 		return kvm_vfio_set_file(dev, attr->attr,
 					 u64_to_user_ptr(attr->addr));
+	case KVM_DEV_VFIO_DEVICE:
+		return kvm_vfio_set_device(dev, attr->attr,
+					   u64_to_user_ptr(attr->addr));
 	}
 
 	return -ENXIO;
@@ -323,6 +446,13 @@ static int kvm_vfio_has_attr(struct kvm_device *dev,
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
 
@@ -332,8 +462,16 @@ static int kvm_vfio_has_attr(struct kvm_device *dev,
 static void kvm_vfio_release(struct kvm_device *dev)
 {
 	struct kvm_vfio *kv = dev->private;
+	struct kvm_vfio_tdi *ktdi, *tmp2;
 	struct kvm_vfio_file *kvf, *tmp;
 
+	list_for_each_entry_safe(ktdi, tmp2, &kv->tdi_list, node) {
+		kvm_arch_tsm_unbind(dev->kvm, ktdi->vdev->dev);
+		list_del(&ktdi->node);
+		vfio_put_device(ktdi->vdev);
+		kfree(ktdi);
+	}
+
 	list_for_each_entry_safe(kvf, tmp, &kv->file_list, node) {
 #ifdef CONFIG_SPAPR_TCE_IOMMU
 		kvm_spapr_tce_release_vfio_group(dev->kvm, kvf);
@@ -379,6 +517,7 @@ static int kvm_vfio_create(struct kvm_device *dev, u32 type)
 
 	INIT_LIST_HEAD(&kv->file_list);
 	mutex_init(&kv->lock);
+	INIT_LIST_HEAD(&kv->tdi_list);
 
 	dev->private = kv;
 
diff --git a/arch/x86/kvm/Kconfig b/arch/x86/kvm/Kconfig
index 472a1537b7a9..5e07a1fddb67 100644
--- a/arch/x86/kvm/Kconfig
+++ b/arch/x86/kvm/Kconfig
@@ -143,6 +143,7 @@ config KVM_AMD_SEV
 	select KVM_GENERIC_PRIVATE_MEM
 	select HAVE_KVM_ARCH_GMEM_PREPARE
 	select HAVE_KVM_ARCH_GMEM_INVALIDATE
+	select KVM_VFIO
 	help
 	  Provides support for launching Encrypted VMs (SEV) and Encrypted VMs
 	  with Encrypted State (SEV-ES) on AMD processors.

---

## [13] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

IOMMUFD calls get_user_pages() for every mapping which will allocate
shared memory instead of using private memory managed by the KVM and
MEMFD.

Add support for IOMMUFD fd to the VFIO KVM device's KVM_DEV_VFIO_FILE API
similar to already existing VFIO device and VFIO group fds.
This addition registers the KVM in IOMMUFD with a callback to get a pfn
for guest private memory for mapping it later in the IOMMU.
No callback for free as it is generic folio_put() for now.

The aforementioned callback uses uptr to calculate the offset into
the KVM memory slot and find private backing pfn, copies
kvm_gmem_get_pfn() pretty much.

This relies on private pages to be pinned beforehand.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/iommu/iommufd/io_pagetable.h    |  3 +
 drivers/iommu/iommufd/iommufd_private.h |  4 +
 include/linux/iommufd.h                 |  6 ++
 include/linux/kvm_host.h                | 66 ++++++++++++++
 drivers/iommu/iommufd/io_pagetable.c    |  2 +
 drivers/iommu/iommufd/main.c            | 21 +++++
 drivers/iommu/iommufd/pages.c           | 94 +++++++++++++++++---
 virt/kvm/guest_memfd.c                  | 40 +++++++++
 virt/kvm/vfio.c                         | 58 ++++++++++--
 9 files changed, 275 insertions(+), 19 deletions(-)

diff --git a/drivers/iommu/iommufd/io_pagetable.h b/drivers/iommu/iommufd/io_pagetable.h
index 0ec3509b7e33..fc9239fc94c0 100644
--- a/drivers/iommu/iommufd/io_pagetable.h
+++ b/drivers/iommu/iommufd/io_pagetable.h
@@ -204,6 +204,9 @@ struct iopt_pages {
 	struct rb_root_cached access_itree;
 	/* Of iopt_area::pages_node */
 	struct rb_root_cached domains_itree;
+
+	struct kvm *kvm;
+	gmem_pin_t gmem_pin;
 };
 
 struct iopt_pages *iopt_alloc_pages(void __user *uptr, unsigned long length,
diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 92efe30a8f0d..bd5573ddcd9c 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -10,6 +10,7 @@
 #include <linux/uaccess.h>
 #include <linux/iommu.h>
 #include <linux/iova_bitmap.h>
+#include <linux/iommufd.h>
 #include <uapi/linux/iommufd.h>
 #include "../iommu-priv.h"
 
@@ -28,6 +29,9 @@ struct iommufd_ctx {
 	/* Compatibility with VFIO no iommu */
 	u8 no_iommu_mode;
 	struct iommufd_ioas *vfio_ioas;
+
+	struct kvm *kvm;
+	gmem_pin_t gmem_pin;
 };
 
 /*
diff --git a/include/linux/iommufd.h b/include/linux/iommufd.h
index ffc3a949f837..a990f604c044 100644
--- a/include/linux/iommufd.h
+++ b/include/linux/iommufd.h
@@ -9,6 +9,7 @@
 #include <linux/types.h>
 #include <linux/errno.h>
 #include <linux/err.h>
+#include <linux/kvm_types.h>
 
 struct device;
 struct iommufd_device;
@@ -57,6 +58,11 @@ void iommufd_ctx_get(struct iommufd_ctx *ictx);
 #if IS_ENABLED(CONFIG_IOMMUFD)
 struct iommufd_ctx *iommufd_ctx_from_file(struct file *file);
 struct iommufd_ctx *iommufd_ctx_from_fd(int fd);
+bool iommufd_file_is_valid(struct file *file);
+typedef int (*gmem_pin_t)(struct kvm *kvm, void __user *uptr, gfn_t *gfn,
+			  kvm_pfn_t *pfn, int *max_order);
+void iommufd_file_set_kvm(struct file *file, struct kvm *kvm,
+			  gmem_pin_t gmem_pin);
 void iommufd_ctx_put(struct iommufd_ctx *ictx);
 bool iommufd_ctx_has_group(struct iommufd_ctx *ictx, struct iommu_group *group);
 
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index fdb331b3e0d3..a09a346ba3ca 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -1297,6 +1297,7 @@ int kvm_gfn_to_hva_cache_init(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 
 int kvm_clear_guest(struct kvm *kvm, gpa_t gpa, unsigned long len);
 struct kvm_memory_slot *gfn_to_memslot(struct kvm *kvm, gfn_t gfn);
+struct kvm_memory_slot *uptr_to_memslot(struct kvm *kvm, void __user *uptr);
 bool kvm_is_visible_gfn(struct kvm *kvm, gfn_t gfn);
 bool kvm_vcpu_is_visible_gfn(struct kvm_vcpu *vcpu, gfn_t gfn);
 unsigned long kvm_host_page_size(struct kvm_vcpu *vcpu, gfn_t gfn);
@@ -1713,6 +1714,22 @@ try_get_memslot(struct kvm_memory_slot *slot, gfn_t gfn)
 		return NULL;
 }
 
+static inline struct kvm_memory_slot *
+try_get_memslot_uptr(struct kvm_memory_slot *slot, void __user *uptr)
+{
+	unsigned long base_upn;
+	unsigned long upn = (unsigned long) uptr >> PAGE_SHIFT;
+
+	if (!slot)
+		return NULL;
+
+	base_upn = slot->userspace_addr >> PAGE_SHIFT;
+	if (upn >= base_upn && upn < base_upn + slot->npages)
+		return slot;
+	else
+		return NULL;
+}
+
 /*
  * Returns a pointer to the memslot that contains gfn. Otherwise returns NULL.
  *
@@ -1741,6 +1758,22 @@ search_memslots(struct kvm_memslots *slots, gfn_t gfn, bool approx)
 	return approx ? slot : NULL;
 }
 
+static inline struct kvm_memory_slot *
+search_memslots_uptr(struct kvm_memslots *slots, void __user *uptr)
+{
+	unsigned long upn = (unsigned long) uptr >> PAGE_SHIFT;
+	struct kvm_memslot_iter iter;
+
+	kvm_for_each_memslot_in_gfn_range(&iter, slots, 0, 512ULL * SZ_1T) {
+		struct kvm_memory_slot *slot = iter.slot;
+		unsigned long base_upn = slot->userspace_addr >> PAGE_SHIFT;
+
+		if (upn >= base_upn && upn < base_upn + slot->npages)
+			return slot;
+	}
+	return NULL;
+}
+
 static inline struct kvm_memory_slot *
 ____gfn_to_memslot(struct kvm_memslots *slots, gfn_t gfn, bool approx)
 {
@@ -1760,6 +1793,25 @@ ____gfn_to_memslot(struct kvm_memslots *slots, gfn_t gfn, bool approx)
 	return NULL;
 }
 
+static inline struct kvm_memory_slot *
+____uptr_to_memslot(struct kvm_memslots *slots, void __user *uptr)
+{
+	struct kvm_memory_slot *slot;
+
+	slot = (struct kvm_memory_slot *)atomic_long_read(&slots->last_used_slot);
+	slot = try_get_memslot_uptr(slot, uptr);
+	if (slot)
+		return slot;
+
+	slot = search_memslots_uptr(slots, uptr);
+	if (slot) {
+		atomic_long_set(&slots->last_used_slot, (unsigned long)slot);
+		return slot;
+	}
+
+	return NULL;
+}
+
 /*
  * __gfn_to_memslot() and its descendants are here to allow arch code to inline
  * the lookups in hot paths.  gfn_to_memslot() itself isn't here as an inline
@@ -1771,6 +1823,12 @@ __gfn_to_memslot(struct kvm_memslots *slots, gfn_t gfn)
 	return ____gfn_to_memslot(slots, gfn, false);
 }
 
+static inline struct kvm_memory_slot *
+__uptr_to_memslot(struct kvm_memslots *slots, void __user *uptr)
+{
+	return ____uptr_to_memslot(slots, uptr);
+}
+
 static inline unsigned long
 __gfn_to_hva_memslot(const struct kvm_memory_slot *slot, gfn_t gfn)
 {
@@ -2446,6 +2504,8 @@ static inline bool kvm_mem_is_private(struct kvm *kvm, gfn_t gfn)
 #ifdef CONFIG_KVM_PRIVATE_MEM
 int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 		     gfn_t gfn, kvm_pfn_t *pfn, int *max_order);
+int kvm_gmem_uptr_to_pfn(struct kvm *kvm, void __user *uptr, gfn_t *gfn,
+			 kvm_pfn_t *pfn, int *max_order);
 #else
 static inline int kvm_gmem_get_pfn(struct kvm *kvm,
 				   struct kvm_memory_slot *slot, gfn_t gfn,
@@ -2454,6 +2514,12 @@ static inline int kvm_gmem_get_pfn(struct kvm *kvm,
 	KVM_BUG_ON(1, kvm);
 	return -EIO;
 }
+static inline int kvm_gmem_uptr_to_pfn(struct kvm *kvm, void __user *uptr, gfn_t *gfn,
+				       kvm_pfn_t *pfn, int *max_order)
+{
+	KVM_BUG_ON(1, kvm);
+	return -EIO;
+}
 #endif /* CONFIG_KVM_PRIVATE_MEM */
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_PREPARE
diff --git a/drivers/iommu/iommufd/io_pagetable.c b/drivers/iommu/iommufd/io_pagetable.c
index 05fd9d3abf1b..aa7584d4a2b8 100644
--- a/drivers/iommu/iommufd/io_pagetable.c
+++ b/drivers/iommu/iommufd/io_pagetable.c
@@ -412,6 +412,8 @@ int iopt_map_user_pages(struct iommufd_ctx *ictx, struct io_pagetable *iopt,
 		elm.pages->account_mode = IOPT_PAGES_ACCOUNT_MM;
 	elm.start_byte = uptr - elm.pages->uptr;
 	elm.length = length;
+	elm.pages->kvm = ictx->kvm;
+	elm.pages->gmem_pin = ictx->gmem_pin;
 	list_add(&elm.next, &pages_list);
 
 	rc = iopt_map_pages(iopt, &pages_list, length, iova, iommu_prot, flags);
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index 83bbd7c5d160..b6039f7c1cce 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -17,6 +17,7 @@
 #include <linux/bug.h>
 #include <uapi/linux/iommufd.h>
 #include <linux/iommufd.h>
+#include <linux/kvm_host.h>
 
 #include "io_pagetable.h"
 #include "iommufd_private.h"
@@ -488,6 +489,26 @@ struct iommufd_ctx *iommufd_ctx_from_fd(int fd)
 }
 EXPORT_SYMBOL_NS_GPL(iommufd_ctx_from_fd, IOMMUFD);
 
+bool iommufd_file_is_valid(struct file *file)
+{
+	return file->f_op == &iommufd_fops;
+}
+EXPORT_SYMBOL_NS_GPL(iommufd_file_is_valid, IOMMUFD);
+
+void iommufd_file_set_kvm(struct file *file, struct kvm *kvm, gmem_pin_t gmem_pin)
+{
+	struct iommufd_ctx *ictx = iommufd_ctx_from_file(file);
+
+	if (WARN_ON(!ictx))
+		return;
+
+	ictx->kvm = kvm;
+	ictx->gmem_pin = gmem_pin;
+
+	iommufd_ctx_put(ictx);
+}
+EXPORT_SYMBOL_NS_GPL(iommufd_file_set_kvm, IOMMUFD);
+
 /**
  * iommufd_ctx_put - Put back a reference
  * @ictx: Context to put back
diff --git a/drivers/iommu/iommufd/pages.c b/drivers/iommu/iommufd/pages.c
index 117f644a0c5b..d85b6969d9ea 100644
--- a/drivers/iommu/iommufd/pages.c
+++ b/drivers/iommu/iommufd/pages.c
@@ -52,6 +52,8 @@
 #include <linux/highmem.h>
 #include <linux/kthread.h>
 #include <linux/iommufd.h>
+#include <linux/kvm_host.h>
+#include <linux/pagemap.h>
 
 #include "io_pagetable.h"
 #include "double_span.h"
@@ -622,6 +624,33 @@ static void batch_from_pages(struct pfn_batch *batch, struct page **pages,
 			break;
 }
 
+static void memfd_unpin_user_page_range_dirty_lock(struct page *page,
+						   unsigned long npages,
+						   bool make_dirty)
+{
+	unsigned long i, nr;
+
+	for (i = 0; i < npages; i += nr) {
+		struct page *next = nth_page(page, i);
+		struct folio *folio = page_folio(next);
+
+		if (folio_test_large(folio))
+			nr = min_t(unsigned int, npages - i,
+				   folio_nr_pages(folio) -
+				   folio_page_idx(folio, next));
+		else
+			nr = 1;
+
+		if (make_dirty && !folio_test_dirty(folio)) {
+			// FIXME: do we need this? private memory does not swap
+			folio_lock(folio);
+			folio_mark_dirty(folio);
+			folio_unlock(folio);
+		}
+		folio_put(folio);
+	}
+}
+
 static void batch_unpin(struct pfn_batch *batch, struct iopt_pages *pages,
 			unsigned int first_page_off, size_t npages)
 {
@@ -638,9 +667,14 @@ static void batch_unpin(struct pfn_batch *batch, struct iopt_pages *pages,
 		size_t to_unpin = min_t(size_t, npages,
 					batch->npfns[cur] - first_page_off);
 
-		unpin_user_page_range_dirty_lock(
-			pfn_to_page(batch->pfns[cur] + first_page_off),
-			to_unpin, pages->writable);
+		if (pages->kvm)
+			memfd_unpin_user_page_range_dirty_lock(
+				pfn_to_page(batch->pfns[cur] + first_page_off),
+				to_unpin, pages->writable);
+		else
+			unpin_user_page_range_dirty_lock(
+				pfn_to_page(batch->pfns[cur] + first_page_off),
+				to_unpin, pages->writable);
 		iopt_pages_sub_npinned(pages, to_unpin);
 		cur++;
 		first_page_off = 0;
@@ -777,17 +811,51 @@ static int pfn_reader_user_pin(struct pfn_reader_user *user,
 		return -EFAULT;
 
 	uptr = (uintptr_t)(pages->uptr + start_index * PAGE_SIZE);
-	if (!remote_mm)
-		rc = pin_user_pages_fast(uptr, npages, user->gup_flags,
-					 user->upages);
-	else {
-		if (!user->locked) {
-			mmap_read_lock(pages->source_mm);
-			user->locked = 1;
+
+	if (pages->kvm) {
+		if (WARN_ON(!pages->gmem_pin))
+			return -EFAULT;
+
+		rc = 0;
+		for (unsigned long i = 0; i < npages; ++i, uptr += PAGE_SIZE) {
+			gfn_t gfn = 0;
+			kvm_pfn_t pfn = 0;
+			int max_order = 0, rc1;
+
+			rc1 = pages->gmem_pin(pages->kvm, (void *) uptr,
+					      &gfn, &pfn, &max_order);
+			if (rc1 == -EINVAL && i == 0) {
+				pr_err_once("Must be vfio mmio at gfn=%llx pfn=%llx, skipping\n",
+					    gfn, pfn);
+				goto the_usual;
+			}
+
+			if (rc1) {
+				pr_err("%s: %d %ld %lx -> %lx\n", __func__,
+				       rc1, i, (unsigned long) uptr, (unsigned long) pfn);
+				rc = rc1;
+				break;
+			}
+
+			user->upages[i] = pfn_to_page(pfn);
+		}
+
+		if (!rc)
+			rc = npages;
+	} else {
+the_usual:
+		if (!remote_mm) {
+			rc = pin_user_pages_fast(uptr, npages, user->gup_flags,
+						 user->upages);
+		} else {
+			if (!user->locked) {
+				mmap_read_lock(pages->source_mm);
+				user->locked = 1;
+			}
+			rc = pin_user_pages_remote(pages->source_mm, uptr, npages,
+						   user->gup_flags, user->upages,
+						   &user->locked);
 		}
-		rc = pin_user_pages_remote(pages->source_mm, uptr, npages,
-					   user->gup_flags, user->upages,
-					   &user->locked);
 	}
 	if (rc <= 0) {
 		if (WARN_ON(!rc))
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index e930014b4bdc..07ff561208fd 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -659,6 +659,46 @@ __kvm_gmem_get_pfn(struct file *file, struct kvm_memory_slot *slot,
 	return folio;
 }
 
+int kvm_gmem_uptr_to_pfn(struct kvm *kvm, void __user *uptr, gfn_t *gfn,
+			 kvm_pfn_t *pfn, int *max_order)
+{
+	struct kvm_memory_slot *slot = __uptr_to_memslot(kvm_memslots(kvm),
+							 uptr);
+	bool is_prepared = false;
+	unsigned long upn_off;
+	struct folio *folio;
+	struct file *file;
+	int r;
+
+	if (!slot)
+		return -EFAULT;
+
+	file = kvm_gmem_get_file(slot);
+	if (!file)
+		return -EFAULT;
+
+	upn_off = ((unsigned long) uptr - slot->userspace_addr) >> PAGE_SHIFT;
+	*gfn = slot->base_gfn + upn_off;
+
+	folio = __kvm_gmem_get_pfn(file, slot, *gfn, pfn, &is_prepared, max_order, true);
+	if (IS_ERR(folio)) {
+		r = PTR_ERR(folio);
+		goto out;
+	}
+
+	if (!is_prepared)
+		r = kvm_gmem_prepare_folio(kvm, slot, *gfn, folio);
+
+	folio_unlock(folio);
+	if (r < 0)
+		folio_put(folio);
+
+out:
+	fput(file);
+	return r;
+}
+EXPORT_SYMBOL_GPL(kvm_gmem_uptr_to_pfn);
+
 int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 		     gfn_t gfn, kvm_pfn_t *pfn, int *max_order)
 {
diff --git a/virt/kvm/vfio.c b/virt/kvm/vfio.c
index a4e9db212adc..7c1d859a58e8 100644
--- a/virt/kvm/vfio.c
+++ b/virt/kvm/vfio.c
@@ -16,6 +16,7 @@
 #include <linux/uaccess.h>
 #include <linux/vfio.h>
 #include <linux/tsm.h>
+#include <linux/iommufd.h>
 #include "vfio.h"
 
 #ifdef CONFIG_SPAPR_TCE_IOMMU
@@ -25,6 +26,7 @@
 struct kvm_vfio_file {
 	struct list_head node;
 	struct file *file;
+	bool is_iommufd;
 #ifdef CONFIG_SPAPR_TCE_IOMMU
 	struct iommu_group *iommu_group;
 #endif
@@ -87,6 +89,36 @@ static bool kvm_vfio_file_is_valid(struct file *file)
 	return ret;
 }
 
+static bool kvm_iommufd_file_is_valid(struct file *file)
+{
+	bool (*fn)(struct file *file);
+	bool ret;
+
+	fn = symbol_get(iommufd_file_is_valid);
+	if (!fn)
+		return false;
+
+	ret = fn(file);
+
+	symbol_put(iommufd_file_is_valid);
+
+	return ret;
+}
+
+static void kvm_iommufd_file_set_kvm(struct file *file, struct kvm *kvm,
+				     gmem_pin_t gmem_pin)
+{
+	void (*fn)(struct file *file, struct kvm *kvm, gmem_pin_t gmem_pin);
+
+	fn = symbol_get(iommufd_file_set_kvm);
+	if (!fn)
+		return;
+
+	fn(file, kvm, gmem_pin);
+
+	symbol_put(iommufd_file_set_kvm);
+}
+
 static struct vfio_device *kvm_vfio_file_device(struct file *file)
 {
 	struct vfio_device *(*fn)(struct file *file);
@@ -167,7 +199,7 @@ static int kvm_vfio_file_add(struct kvm_device *dev, unsigned int fd)
 {
 	struct kvm_vfio *kv = dev->private;
 	struct kvm_vfio_file *kvf;
-	struct file *filp;
+	struct file *filp = NULL;
 	int ret = 0;
 
 	filp = fget(fd);
@@ -175,7 +207,7 @@ static int kvm_vfio_file_add(struct kvm_device *dev, unsigned int fd)
 		return -EBADF;
 
 	/* Ensure the FD is a vfio FD. */
-	if (!kvm_vfio_file_is_valid(filp)) {
+	if (!kvm_vfio_file_is_valid(filp) && !kvm_iommufd_file_is_valid(filp)) {
 		ret = -EINVAL;
 		goto out_fput;
 	}
@@ -196,11 +228,18 @@ static int kvm_vfio_file_add(struct kvm_device *dev, unsigned int fd)
 	}
 
 	kvf->file = get_file(filp);
+
 	list_add_tail(&kvf->node, &kv->file_list);
 
 	kvm_arch_start_assignment(dev->kvm);
-	kvm_vfio_file_set_kvm(kvf->file, dev->kvm);
-	kvm_vfio_update_coherency(dev);
+	kvf->is_iommufd = kvm_iommufd_file_is_valid(filp);
+
+	if (kvf->is_iommufd) {
+		kvm_iommufd_file_set_kvm(kvf->file, dev->kvm, kvm_gmem_uptr_to_pfn);
+	} else {
+		kvm_vfio_file_set_kvm(kvf->file, dev->kvm);
+		kvm_vfio_update_coherency(dev);
+	}
 
 out_unlock:
 	mutex_unlock(&kv->lock);
@@ -233,7 +272,11 @@ static int kvm_vfio_file_del(struct kvm_device *dev, unsigned int fd)
 #ifdef CONFIG_SPAPR_TCE_IOMMU
 		kvm_spapr_tce_release_vfio_group(dev->kvm, kvf);
 #endif
-		kvm_vfio_file_set_kvm(kvf->file, NULL);
+		if (kvf->is_iommufd)
+			kvm_iommufd_file_set_kvm(kvf->file, NULL, NULL);
+		else
+			kvm_vfio_file_set_kvm(kvf->file, NULL);
+
 		fput(kvf->file);
 		kfree(kvf);
 		ret = 0;
@@ -476,7 +519,10 @@ static void kvm_vfio_release(struct kvm_device *dev)
 #ifdef CONFIG_SPAPR_TCE_IOMMU
 		kvm_spapr_tce_release_vfio_group(dev->kvm, kvf);
 #endif
-		kvm_vfio_file_set_kvm(kvf->file, NULL);
+		if (kvf->is_iommufd)
+			kvm_iommufd_file_set_kvm(kvf->file, NULL, NULL);
+		else
+			kvm_vfio_file_set_kvm(kvf->file, NULL);
 		fput(kvf->file);
 		list_del(&kvf->node);
 		kfree(kvf);

---

## [14] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 13/21] KVM: X86: Handle private MMIO as shared*

Currently private MMIO nested page faults are not expected so when such
fault occurs, KVM tries moving the faulted page from private to shared
which is not going to work as private MMIO is not backed by memfd.

Handle private MMIO as shared: skip page state change and memfd
page state tracking.

The MMIO KVM memory slot is still marked as shared as the guest can
access it as private or shared so marking the MMIO slot as private
is not going to help.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 arch/x86/kvm/mmu/mmu.c | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 928cf84778b0..e74f5c3d0821 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4366,7 +4366,11 @@ static int __kvm_faultin_pfn(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault
 {
 	bool async;
 
-	if (fault->is_private)
+	if (fault->slot && fault->is_private && !kvm_slot_can_be_private(fault->slot) &&
+	    (vcpu->kvm->arch.vm_type == KVM_X86_SNP_VM))
+		pr_warn("%s: private SEV TIO MMIO fault for fault->gfn=%llx\n",
+			__func__, fault->gfn);
+	else if (fault->is_private)
 		return kvm_faultin_pfn_private(vcpu, fault);
 
 	async = false;

---

## [15] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 14/21] RFC: iommu/iommufd/amd: Add IOMMU_HWPT_TRUSTED flag, tweak DTE's DomainID, IOTLB*

AMD IOMMUs use a device table where one entry (DTE) describes IOMMU
setup per a PCI BDFn. DMA accesses via these DTEs are always
unencrypted.

In order to allow DMA to/from private memory, AMD IOMMUs use another
memory structure called "secure device table" which entries (sDTEs)
are similar to DTE and contain configuration for private DMA operations.
The sDTE table is in the private memory and is managed by the PSP on
behalf of a SNP VM. So the host OS does not have access to it and
does not need to manage it.

However if sDTE is enabled, some fields of a DTE are now marked as
reserved in a DTE and managed by an sDTE instead (such as DomainID),
other fields need to stay in sync (IR/IW).

Mark IOMMU HW page table with a flag saying that the memory is
backed by KVM (effectively MEMFD).

Skip setting the DomainID in DTE. Enable IOTLB enable (bit 96) to
match what the PSP writes to sDTE.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/iommu/amd/amd_iommu_types.h  |  2 ++
 include/uapi/linux/iommufd.h         |  1 +
 drivers/iommu/amd/iommu.c            | 20 ++++++++++++++++++--
 drivers/iommu/iommufd/hw_pagetable.c |  4 ++++
 4 files changed, 25 insertions(+), 2 deletions(-)

diff --git a/drivers/iommu/amd/amd_iommu_types.h b/drivers/iommu/amd/amd_iommu_types.h
index 2b76b5dedc1d..cf435c1f2839 100644
--- a/drivers/iommu/amd/amd_iommu_types.h
+++ b/drivers/iommu/amd/amd_iommu_types.h
@@ -588,6 +588,8 @@ struct protection_domain {
 
 	struct mmu_notifier mn;	/* mmu notifier for the SVA domain */
 	struct list_head dev_data_list; /* List of pdom_dev_data */
+
+	u32 flags;
 };
 
 /*
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 4dde745cfb7e..c5536686b0b1 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -364,6 +364,7 @@ enum iommufd_hwpt_alloc_flags {
 	IOMMU_HWPT_ALLOC_NEST_PARENT = 1 << 0,
 	IOMMU_HWPT_ALLOC_DIRTY_TRACKING = 1 << 1,
 	IOMMU_HWPT_FAULT_ID_VALID = 1 << 2,
+	IOMMU_HWPT_TRUSTED = 1 << 3,
 };
 
 /**
diff --git a/drivers/iommu/amd/iommu.c b/drivers/iommu/amd/iommu.c
index b19e8c0f48fa..e2f8fb79ee53 100644
--- a/drivers/iommu/amd/iommu.c
+++ b/drivers/iommu/amd/iommu.c
@@ -1930,7 +1930,20 @@ static void set_dte_entry(struct amd_iommu *iommu,
 	}
 
 	flags &= ~DEV_DOMID_MASK;
-	flags |= domid;
+
+	if (dev_data->dev->tdi_enabled && (domain->flags & IOMMU_HWPT_TRUSTED)) {
+		/*
+		 * Do hack for VFIO with TSM enabled.
+		 * This runs when VFIO is being bound to a device and before TDI is bound.
+		 * Ideally TSM should change DTE only when TDI is bound.
+		 * Probably better test for (domain->domain.type & __IOMMU_DOMAIN_DMA_API)
+		 */
+		dev_info(dev_data->dev, "Skip DomainID=%x and set bit96\n", domid);
+		flags |= 1ULL << (96 - 64);
+	} else {
+		//dev_info(dev_data->dev, "Not skip DomainID=%x and not set bit96\n", domid);
+		flags |= domid;
+	}
 
 	old_domid = dev_table[devid].data[1] & DEV_DOMID_MASK;
 	dev_table[devid].data[1]  = flags;
@@ -2413,6 +2426,8 @@ static struct iommu_domain *do_iommu_domain_alloc(unsigned int type,
 
 		if (dirty_tracking)
 			domain->domain.dirty_ops = &amd_dirty_ops;
+
+		domain->flags = flags;
 	}
 
 	return &domain->domain;
@@ -2437,7 +2452,8 @@ amd_iommu_domain_alloc_user(struct device *dev, u32 flags,
 {
 	unsigned int type = IOMMU_DOMAIN_UNMANAGED;
 
-	if ((flags & ~IOMMU_HWPT_ALLOC_DIRTY_TRACKING) || parent || user_data)
+	if ((flags & ~(IOMMU_HWPT_ALLOC_DIRTY_TRACKING | IOMMU_HWPT_TRUSTED)) ||
+	    parent || user_data)
 		return ERR_PTR(-EOPNOTSUPP);
 
 	return do_iommu_domain_alloc(type, dev, flags);
diff --git a/drivers/iommu/iommufd/hw_pagetable.c b/drivers/iommu/iommufd/hw_pagetable.c
index aefde4443671..23ae95fc95ee 100644
--- a/drivers/iommu/iommufd/hw_pagetable.c
+++ b/drivers/iommu/iommufd/hw_pagetable.c
@@ -136,6 +136,10 @@ iommufd_hwpt_paging_alloc(struct iommufd_ctx *ictx, struct iommufd_ioas *ioas,
 	hwpt_paging->nest_parent = flags & IOMMU_HWPT_ALLOC_NEST_PARENT;
 
 	if (ops->domain_alloc_user) {
+		if (ictx->kvm) {
+			pr_info("Trusted domain");
+			flags |= IOMMU_HWPT_TRUSTED;
+		}
 		hwpt->domain = ops->domain_alloc_user(idev->dev, flags, NULL,
 						      user_data);
 		if (IS_ERR(hwpt->domain)) {

---

## [16] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 15/21] coco/sev-guest: Allow multiple source files in the driver*

No behavioural change expected.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/sev-guest/Makefile                     | 1 +
 drivers/virt/coco/sev-guest/{sev-guest.c => sev_guest.c} | 0
 2 files changed, 1 insertion(+)

diff --git a/drivers/virt/coco/sev-guest/Makefile b/drivers/virt/coco/sev-guest/Makefile
index 63d67c27723a..2d7dffed7b2f 100644
--- a/drivers/virt/coco/sev-guest/Makefile
+++ b/drivers/virt/coco/sev-guest/Makefile
@@ -1,2 +1,3 @@
 # SPDX-License-Identifier: GPL-2.0-only
 obj-$(CONFIG_SEV_GUEST) += sev-guest.o
+sev-guest-y += sev_guest.o
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev_guest.c
similarity index 100%
rename from drivers/virt/coco/sev-guest/sev-guest.c
rename to drivers/virt/coco/sev-guest/sev_guest.c

---

## [17] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 16/21] coco/sev-guest: Make SEV-to-PSP request helpers public*

SEV TIO is going to a separate file, these helpers will be reused.

No functional change intended.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/sev-guest/sev-guest.h | 54 ++++++++++++++++++++
 drivers/virt/coco/sev-guest/sev_guest.c | 42 +++------------
 2 files changed, 60 insertions(+), 36 deletions(-)

diff --git a/drivers/virt/coco/sev-guest/sev-guest.h b/drivers/virt/coco/sev-guest/sev-guest.h
new file mode 100644
index 000000000000..765f42ff55aa
--- /dev/null
+++ b/drivers/virt/coco/sev-guest/sev-guest.h
@@ -0,0 +1,54 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2024 Advanced Micro Devices, Inc.
+ */
+
+#ifndef __VIRT_SEVGUEST_H__
+#define __VIRT_SEVGUEST_H__
+
+#include <linux/miscdevice.h>
+#include <linux/types.h>
+
+struct snp_guest_crypto {
+	struct crypto_aead *tfm;
+	u8 *iv, *authtag;
+	int iv_len, a_len;
+};
+
+struct snp_guest_dev {
+	struct device *dev;
+	struct miscdevice misc;
+
+	void *certs_data;
+	struct snp_guest_crypto *crypto;
+	/* request and response are in unencrypted memory */
+	struct snp_guest_msg *request, *response;
+
+	/*
+	 * Avoid information leakage by double-buffering shared messages
+	 * in fields that are in regular encrypted memory.
+	 */
+	struct snp_guest_msg secret_request, secret_response;
+
+	struct snp_secrets_page *secrets;
+	struct snp_req_data input;
+	union {
+		struct snp_report_req report;
+		struct snp_derived_key_req derived_key;
+		struct snp_ext_report_req ext_report;
+	} req;
+	u32 *os_area_msg_seqno;
+	u8 *vmpck;
+};
+
+extern struct mutex snp_cmd_mutex;
+
+int handle_guest_request(struct snp_guest_dev *snp_dev, u64 exit_code,
+				struct snp_guest_request_ioctl *rio, u8 type,
+				void *req_buf, size_t req_sz, void *resp_buf,
+				u32 resp_sz);
+
+void *alloc_shared_pages(struct device *dev, size_t sz);
+void free_shared_pages(void *buf, size_t sz);
+
+#endif /* __VIRT_SEVGUEST_H__ */
diff --git a/drivers/virt/coco/sev-guest/sev_guest.c b/drivers/virt/coco/sev-guest/sev_guest.c
index ecc6176633be..d04d270f359e 100644
--- a/drivers/virt/coco/sev-guest/sev_guest.c
+++ b/drivers/virt/coco/sev-guest/sev_guest.c
@@ -30,6 +30,8 @@
 #include <asm/svm.h>
 #include <asm/sev.h>
 
+#include "sev-guest.h"
+
 #define DEVICE_NAME	"sev-guest"
 #define AAD_LEN		48
 #define MSG_HDR_VER	1
@@ -39,38 +41,6 @@
 
 #define SVSM_MAX_RETRIES		3
 
-struct snp_guest_crypto {
-	struct crypto_aead *tfm;
-	u8 *iv, *authtag;
-	int iv_len, a_len;
-};
-
-struct snp_guest_dev {
-	struct device *dev;
-	struct miscdevice misc;
-
-	void *certs_data;
-	struct snp_guest_crypto *crypto;
-	/* request and response are in unencrypted memory */
-	struct snp_guest_msg *request, *response;
-
-	/*
-	 * Avoid information leakage by double-buffering shared messages
-	 * in fields that are in regular encrypted memory.
-	 */
-	struct snp_guest_msg secret_request, secret_response;
-
-	struct snp_secrets_page *secrets;
-	struct snp_req_data input;
-	union {
-		struct snp_report_req report;
-		struct snp_derived_key_req derived_key;
-		struct snp_ext_report_req ext_report;
-	} req;
-	u32 *os_area_msg_seqno;
-	u8 *vmpck;
-};
-
 /*
  * The VMPCK ID represents the key used by the SNP guest to communicate with the
  * SEV firmware in the AMD Secure Processor (ASP, aka PSP). By default, the key
@@ -83,7 +53,7 @@ module_param(vmpck_id, int, 0444);
 MODULE_PARM_DESC(vmpck_id, "The VMPCK ID to use when communicating with the PSP.");
 
 /* Mutex to serialize the shared buffer access and command handling. */
-static DEFINE_MUTEX(snp_cmd_mutex);
+DEFINE_MUTEX(snp_cmd_mutex);
 
 static bool is_vmpck_empty(struct snp_guest_dev *snp_dev)
 {
@@ -435,7 +405,7 @@ static int __handle_guest_request(struct snp_guest_dev *snp_dev, u64 exit_code,
 	return rc;
 }
 
-static int handle_guest_request(struct snp_guest_dev *snp_dev, u64 exit_code,
+int handle_guest_request(struct snp_guest_dev *snp_dev, u64 exit_code,
 				struct snp_guest_request_ioctl *rio, u8 type,
 				void *req_buf, size_t req_sz, void *resp_buf,
 				u32 resp_sz)
@@ -709,7 +679,7 @@ static long snp_guest_ioctl(struct file *file, unsigned int ioctl, unsigned long
 	return ret;
 }
 
-static void free_shared_pages(void *buf, size_t sz)
+void free_shared_pages(void *buf, size_t sz)
 {
 	unsigned int npages = PAGE_ALIGN(sz) >> PAGE_SHIFT;
 	int ret;
@@ -726,7 +696,7 @@ static void free_shared_pages(void *buf, size_t sz)
 	__free_pages(virt_to_page(buf), get_order(sz));
 }
 
-static void *alloc_shared_pages(struct device *dev, size_t sz)
+void *alloc_shared_pages(struct device *dev, size_t sz)
 {
 	unsigned int npages = PAGE_ALIGN(sz) >> PAGE_SHIFT;
 	struct page *page;

---

## [18] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 17/21] coco/sev-guest: Implement the guest side of things*

Define tsm_ops for the guest and forward the ops calls to the HV via
SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST.
Do the attestation report examination and enable MMIO.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/sev-guest/Makefile        |   2 +-
 arch/x86/include/asm/sev.h                  |   2 +
 drivers/virt/coco/sev-guest/sev-guest.h     |   2 +
 include/linux/psp-sev.h                     |  22 +
 arch/x86/coco/sev/core.c                    |  11 +
 drivers/virt/coco/sev-guest/sev_guest.c     |  16 +-
 drivers/virt/coco/sev-guest/sev_guest_tio.c | 513 ++++++++++++++++++++
 7 files changed, 566 insertions(+), 2 deletions(-)

diff --git a/drivers/virt/coco/sev-guest/Makefile b/drivers/virt/coco/sev-guest/Makefile
index 2d7dffed7b2f..34ea9fab698b 100644
--- a/drivers/virt/coco/sev-guest/Makefile
+++ b/drivers/virt/coco/sev-guest/Makefile
@@ -1,3 +1,3 @@
 # SPDX-License-Identifier: GPL-2.0-only
 obj-$(CONFIG_SEV_GUEST) += sev-guest.o
-sev-guest-y += sev_guest.o
+sev-guest-y += sev_guest.o sev_guest_tio.o
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 8edd7bccabf2..431c12bbd337 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -117,6 +117,8 @@ struct snp_req_data {
 	unsigned long resp_gpa;
 	unsigned long data_gpa;
 	unsigned int data_npages;
+	unsigned int guest_rid;
+	unsigned long param;
 };
 
 #define MAX_AUTHTAG_LEN		32
diff --git a/drivers/virt/coco/sev-guest/sev-guest.h b/drivers/virt/coco/sev-guest/sev-guest.h
index 765f42ff55aa..d1254148c83b 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.h
+++ b/drivers/virt/coco/sev-guest/sev-guest.h
@@ -51,4 +51,6 @@ int handle_guest_request(struct snp_guest_dev *snp_dev, u64 exit_code,
 void *alloc_shared_pages(struct device *dev, size_t sz);
 void free_shared_pages(void *buf, size_t sz);
 
+void sev_guest_tsm_set_ops(bool set, struct snp_guest_dev *snp_dev);
+
 #endif /* __VIRT_SEVGUEST_H__ */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index adf40e0316dc..bff7396d18de 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -1050,6 +1050,9 @@ static inline void snp_free_firmware_page(void *addr) { }
 #define MMIO_VALIDATE_RANGEID(r)  ((r) & 0x7)
 #define MMIO_VALIDATE_RESERVED(r) ((r) & 0xFFF0000000000008ULL)
 
+#define MMIO_MK_VALIDATE(start, size, range_id) \
+	(MMIO_VALIDATE_GPA(start) | (get_order(size >> 12) << 4) | ((range_id) & 0xFF))
+
 /* Optional Certificates/measurements/report data from TIO_GUEST_REQUEST */
 struct tio_blob_table_entry {
 	guid_t guid;
@@ -1067,4 +1070,23 @@ struct tio_blob_table_entry {
 #define TIO_GUID_REPORT \
 	GUID_INIT(0x70dc5b0e, 0x0cc0, 0x4cd5, 0x97, 0xbb, 0xff, 0x0b, 0xa2, 0x5b, 0xf3, 0x20)
 
+/*
+ * Status codes from TIO_MSG_MMIO_VALIDATE_REQ
+ */
+enum mmio_validate_status {
+	MMIO_VALIDATE_SUCCESS = 0,
+	MMIO_VALIDATE_INVALID_TDI = 1,
+	MMIO_VALIDATE_TDI_UNBOUND = 2,
+	MMIO_VALIDATE_NOT_ASSIGNED = 3, /* At least one page is not assigned to the guest */
+	MMIO_VALIDATE_NOT_UNIFORM = 4,  /* The Validated bit is not uniformly set for
+					   the MMIO subrange */
+	MMIO_VALIDATE_NOT_IMMUTABLE = 5,/* At least one page does not have immutable bit set
+					   when validated bit is clear */
+	MMIO_VALIDATE_NOT_MAPPED = 6,   /* At least one page is not mapped to the expected GPA */
+	MMIO_VALIDATE_NOT_REPORTED = 7, /* The provided MMIO range ID is not reported in
+					   the interface report */
+	MMIO_VALIDATE_OUT_OF_RANGE = 8, /* The subrange is out the MMIO range in
+					   the interface report */
+};
+
 #endif	/* __PSP_SEV_H__ */
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index de1df0cb45da..d05a97421ffc 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2468,6 +2468,11 @@ int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input, struct sn
 	if (exit_code == SVM_VMGEXIT_EXT_GUEST_REQUEST) {
 		ghcb_set_rax(ghcb, input->data_gpa);
 		ghcb_set_rbx(ghcb, input->data_npages);
+	} else if (exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST) {
+		ghcb_set_rax(ghcb, input->data_gpa);
+		ghcb_set_rbx(ghcb, input->data_npages);
+		ghcb_set_rcx(ghcb, input->guest_rid);
+		ghcb_set_rdx(ghcb, input->param);
 	}
 
 	ret = sev_es_ghcb_hv_call(ghcb, &ctxt, exit_code, input->req_gpa, input->resp_gpa);
@@ -2477,6 +2482,8 @@ int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input, struct sn
 	rio->exitinfo2 = ghcb->save.sw_exit_info_2;
 	switch (rio->exitinfo2) {
 	case 0:
+		if (exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST)
+			input->param = ghcb_get_rdx(ghcb);
 		break;
 
 	case SNP_GUEST_VMM_ERR(SNP_GUEST_VMM_ERR_BUSY):
@@ -2489,6 +2496,10 @@ int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input, struct sn
 			input->data_npages = ghcb_get_rbx(ghcb);
 			ret = -ENOSPC;
 			break;
+		} else if (exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST) {
+			input->data_npages = ghcb_get_rbx(ghcb);
+			ret = -ENOSPC;
+			break;
 		}
 		fallthrough;
 	default:
diff --git a/drivers/virt/coco/sev-guest/sev_guest.c b/drivers/virt/coco/sev-guest/sev_guest.c
index d04d270f359e..571faade5690 100644
--- a/drivers/virt/coco/sev-guest/sev_guest.c
+++ b/drivers/virt/coco/sev-guest/sev_guest.c
@@ -52,6 +52,10 @@ static int vmpck_id = -1;
 module_param(vmpck_id, int, 0444);
 MODULE_PARM_DESC(vmpck_id, "The VMPCK ID to use when communicating with the PSP.");
 
+static bool tsm_enable = true;
+module_param(tsm_enable, bool, 0644);
+MODULE_PARM_DESC(tsm_enable, "Enable SEV TIO");
+
 /* Mutex to serialize the shared buffer access and command handling. */
 DEFINE_MUTEX(snp_cmd_mutex);
 
@@ -277,7 +281,8 @@ static int verify_and_dec_payload(struct snp_guest_dev *snp_dev, void *payload,
 		return -EBADMSG;
 
 	/* Verify response message type and version number. */
-	if (resp_hdr->msg_type != (req_hdr->msg_type + 1) ||
+	if ((resp_hdr->msg_type != (req_hdr->msg_type + 1) &&
+	     (resp_hdr->msg_type != (req_hdr->msg_type - 0x80))) ||
 	    resp_hdr->msg_version != req_hdr->msg_version)
 		return -EBADMSG;
 
@@ -337,6 +342,10 @@ static int __handle_guest_request(struct snp_guest_dev *snp_dev, u64 exit_code,
 	rc = snp_issue_guest_request(exit_code, &snp_dev->input, rio);
 	switch (rc) {
 	case -ENOSPC:
+		if (exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST) {
+			pr_warn("SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST => -ENOSPC");
+			break;
+		}
 		/*
 		 * If the extended guest request fails due to having too
 		 * small of a certificate data buffer, retry the same
@@ -1142,6 +1151,9 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	if (ret)
 		goto e_free_cert_data;
 
+	if (tsm_enable)
+		sev_guest_tsm_set_ops(true, snp_dev);
+
 	dev_info(dev, "Initialized SEV guest driver (using vmpck_id %d)\n", vmpck_id);
 	return 0;
 
@@ -1160,6 +1172,8 @@ static void __exit sev_guest_remove(struct platform_device *pdev)
 {
 	struct snp_guest_dev *snp_dev = platform_get_drvdata(pdev);
 
+	if (tsm_enable)
+		sev_guest_tsm_set_ops(false, snp_dev);
 	free_shared_pages(snp_dev->certs_data, SEV_FW_BLOB_MAX_SIZE);
 	free_shared_pages(snp_dev->response, sizeof(struct snp_guest_msg));
 	free_shared_pages(snp_dev->request, sizeof(struct snp_guest_msg));
diff --git a/drivers/virt/coco/sev-guest/sev_guest_tio.c b/drivers/virt/coco/sev-guest/sev_guest_tio.c
new file mode 100644
index 000000000000..33a082e7f039
--- /dev/null
+++ b/drivers/virt/coco/sev-guest/sev_guest_tio.c
@@ -0,0 +1,513 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include <linux/pci.h>
+#include <linux/psp-sev.h>
+#include <linux/tsm.h>
+
+#include <asm/svm.h>
+#include <asm/sev.h>
+
+#include "sev-guest.h"
+
+#define TIO_MESSAGE_VERSION	1
+
+ulong tsm_vtom = 0x7fffffff;
+module_param(tsm_vtom, ulong, 0644);
+MODULE_PARM_DESC(tsm_vtom, "SEV TIO vTOM value");
+
+static void tio_guest_blob_free(struct tsm_blob *b)
+{
+	memset(b->data, 0, b->len);
+}
+
+static int handle_tio_guest_request(struct snp_guest_dev *snp_dev, u8 type,
+				   void *req_buf, size_t req_sz, void *resp_buf, u32 resp_sz,
+				   u64 *pt_pa, u64 *npages, u64 *bdfn, u64 *param, u64 *fw_err)
+{
+	struct snp_guest_request_ioctl rio = {
+		.msg_version = TIO_MESSAGE_VERSION,
+		.exitinfo2 = 0,
+	};
+	int ret;
+
+	snp_dev->input.data_gpa = 0;
+	snp_dev->input.data_npages = 0;
+	snp_dev->input.guest_rid = 0;
+	snp_dev->input.param = 0;
+
+	if (pt_pa && npages) {
+		snp_dev->input.data_gpa = *pt_pa;
+		snp_dev->input.data_npages = *npages;
+	}
+	if (bdfn)
+		snp_dev->input.guest_rid = *bdfn;
+	if (param)
+		snp_dev->input.param = *param;
+
+	mutex_lock(&snp_cmd_mutex);
+	ret = handle_guest_request(snp_dev, SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST,
+				   &rio, type, req_buf, req_sz, resp_buf, resp_sz);
+	mutex_unlock(&snp_cmd_mutex);
+
+	if (param)
+		*param = snp_dev->input.param;
+
+	*fw_err = rio.exitinfo2;
+
+	return ret;
+}
+
+static int guest_request_tio_certs(struct snp_guest_dev *snp_dev, u8 type,
+				   void *req_buf, size_t req_sz, void *resp_buf, u32 resp_sz,
+				   u64 bdfn, enum tsm_tdisp_state *state,
+				   struct tsm_blob **certs, struct tsm_blob **meas,
+				   struct tsm_blob **report, u64 *fw_err)
+{
+	u64 certs_size = SZ_32K, c1 = 0, pt_pa, param = 0;
+	struct tio_blob_table_entry *pt;
+	int rc;
+
+	pt = alloc_shared_pages(snp_dev->dev, certs_size);
+	if (!pt)
+		return -ENOMEM;
+
+	pt_pa = __pa(pt);
+	c1 = certs_size;
+	rc = handle_tio_guest_request(snp_dev, type, req_buf, req_sz, resp_buf, resp_sz,
+				      &pt_pa, &c1, &bdfn, state ? &param : NULL, fw_err);
+
+	if (c1 > SZ_32K) {
+		free_shared_pages(pt, certs_size);
+		certs_size = c1;
+		pt = alloc_shared_pages(snp_dev->dev, certs_size);
+		if (!pt)
+			return -ENOMEM;
+
+		pt_pa = __pa(pt);
+		rc = handle_tio_guest_request(snp_dev, type, req_buf, req_sz, resp_buf, resp_sz,
+					      &pt_pa, &c1, &bdfn, state ? &param : NULL, fw_err);
+	}
+
+	if (rc)
+		return rc;
+
+	tsm_blob_put(*meas);
+	tsm_blob_put(*certs);
+	tsm_blob_put(*report);
+	*meas = NULL;
+	*certs = NULL;
+	*report = NULL;
+
+	for (unsigned int i = 0; i < 3; ++i) {
+		u8 *ptr = ((u8 *) pt) + pt[i].offset;
+		size_t len = pt[i].length;
+		struct tsm_blob *b;
+
+		if (guid_is_null(&pt[i].guid))
+			break;
+
+		if (!len)
+			continue;
+
+		b = tsm_blob_new(ptr, len, tio_guest_blob_free);
+		if (!b)
+			break;
+
+		if (guid_equal(&pt[i].guid, &TIO_GUID_MEASUREMENTS))
+			*meas = b;
+		else if (guid_equal(&pt[i].guid, &TIO_GUID_CERTIFICATES))
+			*certs = b;
+		else if (guid_equal(&pt[i].guid, &TIO_GUID_REPORT))
+			*report = b;
+	}
+	free_shared_pages(pt, certs_size);
+
+	if (state)
+		*state = param;
+
+	return 0;
+}
+
+struct tio_msg_tdi_info_req {
+	__u16 guest_device_id;
+	__u8 reserved[14];
+} __packed;
+
+struct tio_msg_tdi_info_rsp {
+	__u16 guest_device_id;
+	__u16 status;
+	__u8 reserved1[12];
+	union {
+		u32 meas_flags;
+		struct {
+			u32 meas_digest_valid : 1;
+			u32 meas_digest_fresh : 1;
+		};
+	};
+	union {
+		u32 tdisp_lock_flags;
+		/* These are TDISP's LOCK_INTERFACE_REQUEST flags */
+		struct {
+			u32 no_fw_update : 1;
+			u32 cache_line_size : 1;
+			u32 lock_msix : 1;
+			u32 bind_p2p : 1;
+			u32 all_request_redirect : 1;
+		};
+	};
+	__u64 spdm_algos;
+	__u8 certs_digest[48];
+	__u8 meas_digest[48];
+	__u8 interface_report_digest[48];
+} __packed;
+
+static int tio_tdi_status(struct tsm_tdi *tdi, struct snp_guest_dev *snp_dev,
+			  struct tsm_tdi_status *ts)
+{
+	struct snp_guest_crypto *crypto = snp_dev->crypto;
+	size_t resp_len = sizeof(struct tio_msg_tdi_info_rsp) + crypto->a_len;
+	struct tio_msg_tdi_info_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_tdi_info_req req = {
+		.guest_device_id = pci_dev_id(tdi->pdev),
+	};
+	u64 fw_err = 0;
+	int rc;
+	enum tsm_tdisp_state state = 0;
+
+	pci_notice(tdi->pdev, "TDI info");
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = guest_request_tio_certs(snp_dev, TIO_MSG_TDI_INFO_REQ, &req,
+				     sizeof(req), rsp, resp_len,
+				     pci_dev_id(tdi->pdev), &state,
+				     &tdi->tdev->certs, &tdi->tdev->meas,
+				     &tdi->report, &fw_err);
+
+	ts->meas_digest_valid = rsp->meas_digest_valid;
+	ts->meas_digest_fresh = rsp->meas_digest_fresh;
+	ts->no_fw_update = rsp->no_fw_update;
+	ts->cache_line_size = rsp->cache_line_size == 0 ? 64 : 128;
+	ts->lock_msix = rsp->lock_msix;
+	ts->bind_p2p = rsp->bind_p2p;
+	ts->all_request_redirect = rsp->all_request_redirect;
+#define __ALGO(x, n, y) \
+	((((x) & (0xFFUL << (n))) == TIO_SPDM_ALGOS_##y) ? \
+	 (1ULL << TSM_TDI_SPDM_ALGOS_##y) : 0)
+	ts->spdm_algos =
+		__ALGO(rsp->spdm_algos, 0, DHE_SECP256R1) |
+		__ALGO(rsp->spdm_algos, 0, DHE_SECP384R1) |
+		__ALGO(rsp->spdm_algos, 8, AEAD_AES_128_GCM) |
+		__ALGO(rsp->spdm_algos, 8, AEAD_AES_256_GCM) |
+		__ALGO(rsp->spdm_algos, 16, ASYM_TPM_ALG_RSASSA_3072) |
+		__ALGO(rsp->spdm_algos, 16, ASYM_TPM_ALG_ECDSA_ECC_NIST_P256) |
+		__ALGO(rsp->spdm_algos, 16, ASYM_TPM_ALG_ECDSA_ECC_NIST_P384) |
+		__ALGO(rsp->spdm_algos, 24, HASH_TPM_ALG_SHA_256) |
+		__ALGO(rsp->spdm_algos, 24, HASH_TPM_ALG_SHA_384) |
+		__ALGO(rsp->spdm_algos, 32, KEY_SCHED_SPDM_KEY_SCHEDULE);
+#undef __ALGO
+	memcpy(ts->certs_digest, rsp->certs_digest, sizeof(ts->certs_digest));
+	memcpy(ts->meas_digest, rsp->meas_digest, sizeof(ts->meas_digest));
+	memcpy(ts->interface_report_digest, rsp->interface_report_digest,
+	       sizeof(ts->interface_report_digest));
+
+	ts->valid = true;
+	ts->state = state;
+	/* The response buffer contains the sensitive data, explicitly clear it. */
+	memzero_explicit(&rsp, sizeof(resp_len));
+	kfree(rsp);
+	return rc;
+}
+
+struct tio_msg_mmio_validate_req {
+	__u16 guest_device_id; /* Hypervisor provided identifier used by the guest
+				  to identify the TDI in guest messages */
+	__u16 reserved1;
+	__u8 reserved2[12];
+	__u64 subrange_base;
+	__u32 subrange_page_count;
+	__u32 range_offset;
+	union {
+		__u16 flags;
+		struct {
+			__u16 validated:1; /* Desired value to set RMP.Validated for the range */
+			/* Force validated:
+			 * 0: If subrange does not have RMP.Validated set uniformly, fail.
+			 * 1: If subrange does not have RMP.Validated set uniformly, force
+			 *    to requested value
+			 */
+			__u16 force_validated:1;
+		};
+	};
+	__u16 range_id;
+	__u8 reserved3[12];
+} __packed;
+
+struct tio_msg_mmio_validate_rsp {
+	__u16 guest_interface_id;
+	__u16 status; /* MMIO_VALIDATE_xxx */
+	__u8 reserved1[12];
+	__u64 subrange_base;
+	__u32 subrange_page_count;
+	__u32 range_offset;
+	union {
+		__u16 flags;
+		struct {
+			__u16 changed:1; /* Indicates that the Validated bit has changed
+					    due to this operation */
+		};
+	};
+	__u16 range_id;
+	__u8 reserved2[12];
+} __packed;
+
+static int mmio_validate_range(struct snp_guest_dev *snp_dev, struct pci_dev *pdev,
+			       unsigned int range_id, resource_size_t start, resource_size_t size,
+			       bool invalidate, u64 *fw_err)
+{
+	struct snp_guest_crypto *crypto = snp_dev->crypto;
+	size_t resp_len = sizeof(struct tio_msg_mmio_validate_rsp) + crypto->a_len;
+	struct tio_msg_mmio_validate_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_mmio_validate_req req = {
+		.guest_device_id = pci_dev_id(pdev),
+		.subrange_base = start,
+		.subrange_page_count = size >> PAGE_SHIFT,
+		.range_offset = 0,
+		.validated = 1, /* Desired value to set RMP.Validated for the range */
+		.force_validated = 0,
+		.range_id = range_id,
+	};
+	u64 bdfn = pci_dev_id(pdev);
+	u64 mmio_val = MMIO_MK_VALIDATE(start, size, range_id);
+	int rc;
+
+	if (!rsp)
+		return -ENOMEM;
+
+	if (invalidate)
+		memset(&req, 0, sizeof(req));
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_MMIO_VALIDATE_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, &mmio_val, fw_err);
+	if (rc)
+		goto free_exit;
+
+	if (rsp->status)
+		rc = -EBADR;
+
+free_exit:
+	/* The response buffer contains the sensitive data, explicitly clear it. */
+	memzero_explicit(&rsp, sizeof(resp_len));
+	kfree(rsp);
+	return rc;
+}
+
+static int tio_tdi_mmio_validate(struct tsm_tdi *tdi, struct snp_guest_dev *snp_dev,
+				 bool invalidate)
+{
+	struct pci_dev *pdev = tdi->pdev;
+	struct tdi_report_mmio_range mr;
+	struct resource *r;
+	u64 fw_err = 0;
+	int i = 0, rc;
+
+	pci_notice(tdi->pdev, "MMIO validate");
+
+	if (WARN_ON_ONCE(!tdi->report || !tdi->report->data))
+		return -EFAULT;
+
+	for (i = 0; i < TDI_REPORT_MR_NUM(tdi->report); ++i) {
+		mr = TDI_REPORT_MR(tdi->report, i);
+		r = pci_resource_n(tdi->pdev, mr.range_id);
+
+		if (r->end == r->start || ((r->end - r->start + 1) & ~PAGE_MASK) || !mr.num) {
+			pci_warn(tdi->pdev, "Skipping broken range [%d] #%d %d pages, %llx..%llx\n",
+				i, mr.range_id, mr.num, r->start, r->end);
+			continue;
+		}
+
+		if (mr.is_non_tee_mem) {
+			pci_info(tdi->pdev, "Skipping non-TEE range [%d] #%d %d pages, %llx..%llx\n",
+				 i, mr.range_id, mr.num, r->start, r->end);
+			continue;
+		}
+
+		rc = mmio_validate_range(snp_dev, pdev, mr.range_id,
+					 r->start, r->end - r->start + 1, invalidate, &fw_err);
+		if (rc) {
+			pci_err(pdev, "MMIO #%d %llx..%llx validation failed 0x%llx\n",
+				mr.range_id, r->start, r->end, fw_err);
+			continue;
+		}
+
+		pci_notice(pdev, "MMIO #%d %llx..%llx validated\n",  mr.range_id, r->start, r->end);
+	}
+
+	return rc;
+}
+
+struct sdte {
+	__u64 v                  : 1;
+	__u64 reserved           : 3;
+	__u64 cxlio              : 3;
+	__u64 reserved1          : 45;
+	__u64 ppr                : 1;
+	__u64 reserved2          : 1;
+	__u64 giov               : 1;
+	__u64 gv                 : 1;
+	__u64 glx                : 2;
+	__u64 gcr3_tbl_rp0       : 3;
+	__u64 ir                 : 1;
+	__u64 iw                 : 1;
+	__u64 reserved3          : 1;
+	__u16 domain_id;
+	__u16 gcr3_tbl_rp1;
+	__u32 interrupt          : 1;
+	__u32 reserved4          : 5;
+	__u32 ex                 : 1;
+	__u32 sd                 : 1;
+	__u32 reserved5          : 2;
+	__u32 sats               : 1;
+	__u32 gcr3_tbl_rp2       : 21;
+	__u64 giv                : 1;
+	__u64 gint_tbl_len       : 4;
+	__u64 reserved6          : 1;
+	__u64 gint_tbl           : 46;
+	__u64 reserved7          : 2;
+	__u64 gpm                : 2;
+	__u64 reserved8          : 3;
+	__u64 hpt_mode           : 1;
+	__u64 reserved9          : 4;
+	__u32 asid               : 12;
+	__u32 reserved10         : 3;
+	__u32 viommu_en          : 1;
+	__u32 guest_device_id    : 16;
+	__u32 guest_id           : 15;
+	__u32 guest_id_mbo       : 1;
+	__u32 reserved11         : 1;
+	__u32 vmpl               : 2;
+	__u32 reserved12         : 3;
+	__u32 attrv              : 1;
+	__u32 reserved13         : 1;
+	__u32 sa                 : 8;
+	__u8 ide_stream_id[8];
+	__u32 vtom_en            : 1;
+	__u32 vtom               : 31;
+	__u32 rp_id              : 5;
+	__u32 reserved14         : 27;
+	__u8  reserved15[0x40-0x30];
+} __packed;
+
+struct tio_msg_sdte_write_req {
+	__u16 guest_device_id;
+	__u8 reserved[14];
+	struct sdte sdte;
+} __packed;
+
+#define SDTE_WRITE_SUCCESS		0
+#define SDTE_WRITE_INVALID_TDI		1
+#define SDTE_WRITE_TDI_NOT_BOUND	2
+#define SDTE_WRITE_RESERVED		3
+
+struct tio_msg_sdte_write_rsp {
+	__u16 guest_device_id;
+	__u16 status; /* SDTE_WRITE_xxx */
+	__u8 reserved[12];
+} __packed;
+
+static int tio_tdi_sdte_write(struct tsm_tdi *tdi, struct snp_guest_dev *snp_dev, bool invalidate)
+{
+	struct snp_guest_crypto *crypto = snp_dev->crypto;
+	size_t resp_len = sizeof(struct tio_msg_sdte_write_rsp) + crypto->a_len;
+	struct tio_msg_sdte_write_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_sdte_write_req req = {
+		.guest_device_id = pci_dev_id(tdi->pdev),
+		.sdte.vmpl = 0,
+		.sdte.vtom = tsm_vtom,
+		.sdte.vtom_en = 1,
+		.sdte.iw = 1,
+		.sdte.ir = 1,
+		.sdte.v = 1,
+	};
+	u64 fw_err = 0;
+	u64 bdfn = pci_dev_id(tdi->pdev);
+	int rc;
+
+	BUILD_BUG_ON(sizeof(struct sdte) * 8 != 512);
+
+	if (invalidate)
+		memset(&req, 0, sizeof(req));
+
+	pci_notice(tdi->pdev, "SDTE write vTOM=%lx", (unsigned long) req.sdte.vtom << 21);
+
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_SDTE_WRITE_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, NULL, &fw_err);
+	if (rc) {
+		pci_err(tdi->pdev, "SDTE write failed with 0x%llx\n", fw_err);
+		goto free_exit;
+	}
+
+free_exit:
+	/* The response buffer contains the sensitive data, explicitly clear it. */
+	memzero_explicit(&rsp, sizeof(resp_len));
+	kfree(rsp);
+	return rc;
+}
+
+static int sev_guest_tdi_status(struct tsm_tdi *tdi, void *private_data, struct tsm_tdi_status *ts)
+{
+	struct snp_guest_dev *snp_dev = private_data;
+
+	return tio_tdi_status(tdi, snp_dev, ts);
+}
+
+static int sev_guest_tdi_validate(struct tsm_tdi *tdi, bool invalidate, void *private_data)
+{
+	struct snp_guest_dev *snp_dev = private_data;
+	struct tsm_tdi_status ts = { 0 };
+	int ret;
+
+	if (!tdi->report) {
+		ret = tio_tdi_status(tdi, snp_dev, &ts);
+
+		if (ret || !tdi->report) {
+			pci_err(tdi->pdev, "No report available, ret=%d", ret);
+			if (!ret && tdi->report)
+				ret = -EIO;
+			return ret;
+		}
+
+		if (ts.state != TDISP_STATE_RUN) {
+			pci_err(tdi->pdev, "Not in RUN state, state=%d instead", ts.state);
+			return -EIO;
+		}
+	}
+
+	ret = tio_tdi_sdte_write(tdi, snp_dev, invalidate);
+	if (ret)
+		return ret;
+
+	ret = tio_tdi_mmio_validate(tdi, snp_dev, invalidate);
+	if (ret)
+		return ret;
+
+	return 0;
+}
+
+struct tsm_ops sev_guest_tsm_ops = {
+	.tdi_validate = sev_guest_tdi_validate,
+	.tdi_status = sev_guest_tdi_status,
+};
+
+void sev_guest_tsm_set_ops(bool set, struct snp_guest_dev *snp_dev)
+{
+	if (set)
+		tsm_set_ops(&sev_guest_tsm_ops, snp_dev);
+	else
+		tsm_set_ops(NULL, NULL);
+}

---

## [19] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 18/21] RFC: pci: Add BUS_NOTIFY_PCI_BUS_MASTER event*

TDISP allows secure MMIO access to a validated MMIO range.
The validation is done in the TSM and after that point changing
the device's Memory Space enable (MSE) or Bus Master enable (BME)
transitions the device into the error state.

For PCI device drivers which enable MSE, then BME, and then
start using the device, enabling BME is a logical point to perform
the MMIO range validation in the TSM.

Define new event for a bus. TSM is going to listen to it in the TVM
and do the validation for TEE ranges.

This does not switch MMIO to private by default though as this is
for the driver to decide (at least, for now).

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/device/bus.h | 3 +++
 drivers/pci/pci.c          | 3 +++
 drivers/virt/coco/tsm.c    | 4 ++++
 3 files changed, 10 insertions(+)

diff --git a/include/linux/device/bus.h b/include/linux/device/bus.h
index 807831d6bf0f..314349149cd3 100644
--- a/include/linux/device/bus.h
+++ b/include/linux/device/bus.h
@@ -269,8 +269,11 @@ enum bus_notifier_event {
 	BUS_NOTIFY_UNBIND_DRIVER,
 	BUS_NOTIFY_UNBOUND_DRIVER,
 	BUS_NOTIFY_DRIVER_NOT_BOUND,
+	BUS_NOTIFY_PCI_BUS_MASTER,
 };
 
+void bus_notify(struct device *dev, enum bus_notifier_event value);
+
 struct kset *bus_get_kset(const struct bus_type *bus);
 struct device *bus_get_dev_root(const struct bus_type *bus);
 
diff --git a/drivers/pci/pci.c b/drivers/pci/pci.c
index 15c0bb86ab01..b8bb322d1659 100644
--- a/drivers/pci/pci.c
+++ b/drivers/pci/pci.c
@@ -4271,6 +4271,9 @@ static void __pci_set_master(struct pci_dev *dev, bool enable)
 		pci_write_config_word(dev, PCI_COMMAND, cmd);
 	}
 	dev->is_busmaster = enable;
+
+	if (enable && dev->dev.tdi_enabled)
+		bus_notify(&dev->dev, BUS_NOTIFY_PCI_BUS_MASTER);
 }
 
 /**
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index e90455a0267f..b16b5d33c80f 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -1193,6 +1193,10 @@ static int tsm_pci_bus_notifier(struct notifier_block *nb, unsigned long action,
 	case BUS_NOTIFY_DEL_DEVICE:
 		tsm_dev_freeice(data);
 		break;
+	case BUS_NOTIFY_PCI_BUS_MASTER:
+		/* Validating before the driver or after the driver just does not work so don't! */
+		tsm_tdi_validate(tsm_tdi_get(data), false, tsm.private_data);
+		break;
 	case BUS_NOTIFY_UNBOUND_DRIVER:
 		tsm_tdi_validate(tsm_tdi_get(data), true, tsm.private_data);
 		break;

---

## [20] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 19/21] sev-guest: Stop changing encrypted page state for TDISP devices*

And "sev-guest: Disable SWIOTLB for TIO device's dma_map".

And other things to make secure DMA work.
Like, clear C-bit.
And set GFP_DMA, which does not seem to matter though as down
the stack it gets cleared anyway.

CONFIG_ZONE_DMA must be off too.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/dma-direct.h | 4 ++++
 include/linux/swiotlb.h    | 4 ++++
 arch/x86/mm/mem_encrypt.c  | 5 +++++
 3 files changed, 13 insertions(+)

diff --git a/include/linux/dma-direct.h b/include/linux/dma-direct.h
index edbe13d00776..f6ed954b05a2 100644
--- a/include/linux/dma-direct.h
+++ b/include/linux/dma-direct.h
@@ -94,6 +94,10 @@ static inline dma_addr_t phys_to_dma_unencrypted(struct device *dev,
  */
 static inline dma_addr_t phys_to_dma(struct device *dev, phys_addr_t paddr)
 {
+	if (dev->tdi_enabled) {
+		dev_warn_once(dev, "(TIO) Disable SME");
+		return phys_to_dma_unencrypted(dev, paddr);
+	}
 	return __sme_set(phys_to_dma_unencrypted(dev, paddr));
 }
 
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..61e7cff7768b 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -173,6 +173,10 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+	if (dev->tdi_enabled) {
+		dev_warn_once(dev, "(TIO) Disable SWIOTLB");
+		return false;
+	}
 	return mem && mem->force_bounce;
 }
 
diff --git a/arch/x86/mm/mem_encrypt.c b/arch/x86/mm/mem_encrypt.c
index 0a120d85d7bb..e288e628ef88 100644
--- a/arch/x86/mm/mem_encrypt.c
+++ b/arch/x86/mm/mem_encrypt.c
@@ -19,6 +19,11 @@
 /* Override for DMA direct allocation check - ARCH_HAS_FORCE_DMA_UNENCRYPTED */
 bool force_dma_unencrypted(struct device *dev)
 {
+	if (dev->tdi_enabled) {
+		dev_warn_once(dev, "(TIO) Disable decryption");
+		return false;
+	}
+
 	/*
 	 * For SEV, all DMA must be to unencrypted addresses.
 	 */

---

## [21] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 20/21] pci: Allow encrypted MMIO mapping via sysfs*

Add another resource#d_enc to allow mapping MMIO as
an encrypted/private region.

Unlike resourceN_wc, the node is added always as ability to
map MMIO as private depends on negotiation with the TSM which
happens quite late.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/pci.h     |  2 +-
 drivers/pci/mmap.c      | 11 +++++++-
 drivers/pci/pci-sysfs.c | 27 +++++++++++++++-----
 drivers/pci/proc.c      |  2 +-
 4 files changed, 32 insertions(+), 10 deletions(-)

diff --git a/include/linux/pci.h b/include/linux/pci.h
index 053b7c506818..3c44542f66df 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -2085,7 +2085,7 @@ pci_alloc_irq_vectors(struct pci_dev *dev, unsigned int min_vecs,
  */
 int pci_mmap_resource_range(struct pci_dev *dev, int bar,
 			    struct vm_area_struct *vma,
-			    enum pci_mmap_state mmap_state, int write_combine);
+			    enum pci_mmap_state mmap_state, int write_combine, int enc);
 
 #ifndef arch_can_pci_mmap_wc
 #define arch_can_pci_mmap_wc()		0
diff --git a/drivers/pci/mmap.c b/drivers/pci/mmap.c
index 8da3347a95c4..4fd522aeb767 100644
--- a/drivers/pci/mmap.c
+++ b/drivers/pci/mmap.c
@@ -23,7 +23,7 @@ static const struct vm_operations_struct pci_phys_vm_ops = {
 
 int pci_mmap_resource_range(struct pci_dev *pdev, int bar,
 			    struct vm_area_struct *vma,
-			    enum pci_mmap_state mmap_state, int write_combine)
+			    enum pci_mmap_state mmap_state, int write_combine, int enc)
 {
 	unsigned long size;
 	int ret;
@@ -46,6 +46,15 @@ int pci_mmap_resource_range(struct pci_dev *pdev, int bar,
 
 	vma->vm_ops = &pci_phys_vm_ops;
 
+	/*
+	 * Calling remap_pfn_range() directly as io_remap_pfn_range()
+	 * enforces shared mapping.
+	 */
+	if (enc)
+		return remap_pfn_range(vma, vma->vm_start, vma->vm_pgoff,
+				       vma->vm_end - vma->vm_start,
+				       vma->vm_page_prot);
+
 	return io_remap_pfn_range(vma, vma->vm_start, vma->vm_pgoff,
 				  vma->vm_end - vma->vm_start,
 				  vma->vm_page_prot);
diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
index bf019371ef9a..1b0eca1751c2 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1032,7 +1032,7 @@ void pci_remove_legacy_files(struct pci_bus *b)
  * Use the regular PCI mapping routines to map a PCI resource into userspace.
  */
 static int pci_mmap_resource(struct kobject *kobj, struct bin_attribute *attr,
-			     struct vm_area_struct *vma, int write_combine)
+			     struct vm_area_struct *vma, int write_combine, int enc)
 {
 	struct pci_dev *pdev = to_pci_dev(kobj_to_dev(kobj));
 	int bar = (unsigned long)attr->private;
@@ -1052,21 +1052,28 @@ static int pci_mmap_resource(struct kobject *kobj, struct bin_attribute *attr,
 
 	mmap_type = res->flags & IORESOURCE_MEM ? pci_mmap_mem : pci_mmap_io;
 
-	return pci_mmap_resource_range(pdev, bar, vma, mmap_type, write_combine);
+	return pci_mmap_resource_range(pdev, bar, vma, mmap_type, write_combine, enc);
 }
 
 static int pci_mmap_resource_uc(struct file *filp, struct kobject *kobj,
 				struct bin_attribute *attr,
 				struct vm_area_struct *vma)
 {
-	return pci_mmap_resource(kobj, attr, vma, 0);
+	return pci_mmap_resource(kobj, attr, vma, 0, 0);
 }
 
 static int pci_mmap_resource_wc(struct file *filp, struct kobject *kobj,
 				struct bin_attribute *attr,
 				struct vm_area_struct *vma)
 {
-	return pci_mmap_resource(kobj, attr, vma, 1);
+	return pci_mmap_resource(kobj, attr, vma, 1, 0);
+}
+
+static int pci_mmap_resource_enc(struct file *filp, struct kobject *kobj,
+				 struct bin_attribute *attr,
+				 struct vm_area_struct *vma)
+{
+	return pci_mmap_resource(kobj, attr, vma, 0, 1);
 }
 
 static ssize_t pci_resource_io(struct file *filp, struct kobject *kobj,
@@ -1160,7 +1167,7 @@ static void pci_remove_resource_files(struct pci_dev *pdev)
 	}
 }
 
-static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine)
+static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine, int enc)
 {
 	/* allocate attribute structure, piggyback attribute name */
 	int name_len = write_combine ? 13 : 10;
@@ -1178,6 +1185,9 @@ static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine)
 	if (write_combine) {
 		sprintf(res_attr_name, "resource%d_wc", num);
 		res_attr->mmap = pci_mmap_resource_wc;
+	} else if (enc) {
+		sprintf(res_attr_name, "resource%d_enc", num);
+		res_attr->mmap = pci_mmap_resource_enc;
 	} else {
 		sprintf(res_attr_name, "resource%d", num);
 		if (pci_resource_flags(pdev, num) & IORESOURCE_IO) {
@@ -1234,11 +1244,14 @@ static int pci_create_resource_files(struct pci_dev *pdev)
 		if (!pci_resource_len(pdev, i))
 			continue;
 
-		retval = pci_create_attr(pdev, i, 0);
+		retval = pci_create_attr(pdev, i, 0, 0);
 		/* for prefetchable resources, create a WC mappable file */
 		if (!retval && arch_can_pci_mmap_wc() &&
 		    pdev->resource[i].flags & IORESOURCE_PREFETCH)
-			retval = pci_create_attr(pdev, i, 1);
+			retval = pci_create_attr(pdev, i, 1, 0);
+		/* Add node for private MMIO mapping */
+		if (!retval)
+			retval = pci_create_attr(pdev, i, 0, 1);
 		if (retval) {
 			pci_remove_resource_files(pdev);
 			return retval;
diff --git a/drivers/pci/proc.c b/drivers/pci/proc.c
index f967709082d6..62992c8234f1 100644
--- a/drivers/pci/proc.c
+++ b/drivers/pci/proc.c
@@ -284,7 +284,7 @@ static int proc_bus_pci_mmap(struct file *file, struct vm_area_struct *vma)
 	/* Adjust vm_pgoff to be the offset within the resource */
 	vma->vm_pgoff -= start >> PAGE_SHIFT;
 	ret = pci_mmap_resource_range(dev, i, vma,
-				  fpriv->mmap_state, write_combine);
+				  fpriv->mmap_state, write_combine, 0);
 	if (ret < 0)
 		return ret;

---

## [22] Alexey Kardashevskiy — 2024-08-23
*Subject: [RFC PATCH 21/21] pci: Define pci_iomap_range_encrypted*

So far PCI BARs could not be mapped as encrypted so there was no
need in API supporting encrypted mappings. TDISP is adding such
support so add pci_iomap_range_encrypted() to allow PCI drivers
do the encrypted mapping when needed.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/asm-generic/pci_iomap.h |  4 ++++
 drivers/pci/iomap.c             | 24 ++++++++++++++++++++
 2 files changed, 28 insertions(+)

diff --git a/include/asm-generic/pci_iomap.h b/include/asm-generic/pci_iomap.h
index 8fbb0a55545d..d7b922c5ab86 100644
--- a/include/asm-generic/pci_iomap.h
+++ b/include/asm-generic/pci_iomap.h
@@ -15,6 +15,10 @@ extern void __iomem *pci_iomap_wc(struct pci_dev *dev, int bar, unsigned long ma
 extern void __iomem *pci_iomap_range(struct pci_dev *dev, int bar,
 				     unsigned long offset,
 				     unsigned long maxlen);
+extern void __iomem *pci_iomap_range_encrypted(struct pci_dev *dev,
+					       int bar,
+					       unsigned long offset,
+					       unsigned long maxlen);
 extern void __iomem *pci_iomap_wc_range(struct pci_dev *dev, int bar,
 					unsigned long offset,
 					unsigned long maxlen);
diff --git a/drivers/pci/iomap.c b/drivers/pci/iomap.c
index a715a4803c95..2bf8ef4f672b 100644
--- a/drivers/pci/iomap.c
+++ b/drivers/pci/iomap.c
@@ -52,6 +52,30 @@ void __iomem *pci_iomap_range(struct pci_dev *dev,
 }
 EXPORT_SYMBOL(pci_iomap_range);
 
+void __iomem *pci_iomap_range_encrypted(struct pci_dev *dev,
+					int bar,
+					unsigned long offset,
+					unsigned long maxlen)
+{
+	resource_size_t start = pci_resource_start(dev, bar);
+	resource_size_t len = pci_resource_len(dev, bar);
+	unsigned long flags = pci_resource_flags(dev, bar);
+
+	if (len <= offset || !start)
+		return NULL;
+	len -= offset;
+	start += offset;
+	if (maxlen && len > maxlen)
+		len = maxlen;
+	if (flags & IORESOURCE_IO)
+		return NULL;
+	if (flags & IORESOURCE_MEM)
+		return ioremap_encrypted(start, len);
+	/* What? */
+	return NULL;
+}
+EXPORT_SYMBOL(pci_iomap_range_encrypted);
+
 /**
  * pci_iomap_wc_range - create a virtual WC mapping cookie for a PCI BAR
  * @dev: PCI device that owns the BAR

---

## [23] Bjorn Helgaas — 2024-08-23
*Subject: Re: [RFC PATCH 01/21] tsm-report: Rename module to reflect what it
 does*

On Fri, Aug 23, 2024 at 11:21:15PM +1000, Alexey Kardashevskiy wrote:

Include the text from the title here so the commit log is
self-contained.

> And release the name for TSM to be used for TDISP-associated code.

---

## [24] Bjorn Helgaas — 2024-08-23
*Subject: Re: [RFC PATCH 02/21] pci/doe: Define protocol types and make those
 public*

Run "git log --oneline" and follow the drivers/pci capitalization
convention.

On Fri, Aug 23, 2024 at 11:21:16PM +1000, Alexey Kardashevskiy wrote:
> Already public pci_doe() takes a protocol type argument.
> PCIe 6.0 defines three, define them in a header for use with pci_doe().

Include section number, e.g., PCIe r6.0, sec xxx.

Rewrap to fill 75 columns (or add a blank line if you intend two
paragraphs).

---

## [25] Bjorn Helgaas — 2024-08-23
*Subject: Re: [RFC PATCH 03/21] pci: Define TEE-IO bit in PCIe device
 capabilities*

On Fri, Aug 23, 2024 at 11:21:17PM +1000, Alexey Kardashevskiy wrote:
> A new bit #30 from the PCI Express Device Capabilities Register is defined
> in PCIe 6.1 as "TEE Device Interface Security Protocol (TDISP)".

Include spec section number.

---

## [26] Bjorn Helgaas — 2024-08-23
*Subject: Re: [RFC PATCH 04/21] PCI/IDE: Define Integrity and Data Encryption
 (IDE) extended capability*

On Fri, Aug 23, 2024 at 11:21:18PM +1000, Alexey Kardashevskiy wrote:
> PCIe 6.0 introduces the "Integrity & Data Encryption (IDE)" feature which
> adds a new capability with id=0x30.

Include section number.

> Add the new id to the list of capabilities. Add new flags from pciutils.
> Add a module with a helper to control selective IDE capability.

s/id/ID/  Maybe even include the name of the #define.

What's the "new flags from pciutils" about?  I don't think we need to
add #defines until they're used in Linux.

No comments on the code except to notice that 95%+ fits in 80 columns,
but some function prototypes are needlessly 90-100.

---

## [27] Bjorn Helgaas — 2024-08-23
*Subject: Re: [RFC PATCH 20/21] pci: Allow encrypted MMIO mapping via sysfs*

On Fri, Aug 23, 2024 at 11:21:34PM +1000, Alexey Kardashevskiy wrote:
> Add another resource#d_enc to allow mapping MMIO as
> an encrypted/private region.

Capitalize subject prefix.

Wrap to fill 75 columns.

> +++ b/include/linux/pci.h
> @@ -2085,7 +2085,7 @@ pci_alloc_irq_vectors(struct pci_dev *dev, unsigned int min_vecs,

This interface is only used in drivers/pci and look like it should be
moved to drivers/pci/pci.h.

> @@ -46,6 +46,15 @@ int pci_mmap_resource_range(struct pci_dev *pdev, int bar,
>  

s/Calling/Call/

Needs some additional context about why io_remap_pfn_range() can't be
used here.

> +	 */
> +	if (enc)

---

## [28] Tian, Kevin — 2024-08-26
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

+Jason/David

> From: Alexey Kardashevskiy <aik@amd.com>
> Sent: Friday, August 23, 2024 9:21 PM

There was a related discussion [1] which leans toward the conclusion
that the IOMMU page table for private memory will be managed by
the secure world i.e. the KVM path.

Obviously the work here confirms that it doesn't hold for SEV-TIO
which still expects the host to manage the IOMMU page table.

btw going down this path it's clearer to extend the MAP_DMA
uAPI to accept {gmemfd, offset} than adding a callback to KVM.

---

## [29] Jason Gunthorpe — 2024-08-26
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Mon, Aug 26, 2024 at 08:39:25AM +0000, Tian, Kevin wrote:
> > IOMMUFD calls get_user_pages() for every mapping which will allocate
> > shared memory instead of using private memory managed by the KVM and

It is still effectively true, AMD's design has duplication, the RMP
table has the mappings to validate GPA and that is all managed in the
secure world.

They just want another copy of that information in the unsecure world
in the form of page tables :\

> btw going down this path it's clearer to extend the MAP_DMA
> uAPI to accept {gmemfd, offset} than adding a callback to KVM.

Yes, we want a DMA MAP from memfd sort of API in general. So it should
go directly to guest memfd with no kvm entanglement.

Jason

---

## [30] Alexey Kardashevskiy — 2024-08-27
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On 26/8/24 18:39, Tian, Kevin wrote:
> +Jason/David
> 

Forgot [1]?

> that the IOMMU page table for private memory will be managed by
> the secure world i.e. the KVM path.

Thanks for the comment, makes sense, this should make the interface 
cleaner. It was just a bit messy (but doable nevertheless) at the time 
to push this new mapping flag/type all the way down to pfn_reader_user_pin:

iommufd_ioas_map -> iopt_map_user_pages -> iopt_map_pages -> 
iopt_fill_domains_pages -> iopt_area_fill_domains -> pfn_reader_first -> 
pfn_reader_next -> pfn_reader_fill_span -> pfn_reader_user_pin


Thanks,

---

## [31] Tian, Kevin — 2024-08-27
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Alexey Kardashevskiy <aik@amd.com>
> Sent: Tuesday, August 27, 2024 10:28 AM

[1] https://lore.kernel.org/kvm/20240620143406.GJ2494510@nvidia.com/

> 
> > that the IOMMU page table for private memory will be managed by

---

## [32] Jason Gunthorpe — 2024-08-27
*Subject: Re: [RFC PATCH 14/21] RFC: iommu/iommufd/amd: Add IOMMU_HWPT_TRUSTED
 flag, tweak DTE's DomainID, IOTLB*

On Fri, Aug 23, 2024 at 11:21:28PM +1000, Alexey Kardashevskiy wrote:
> AMD IOMMUs use a device table where one entry (DTE) describes IOMMU
> setup per a PCI BDFn. DMA accesses via these DTEs are always

This looks so extremely specialized to AMD I think you should put this
in an AMD specific struct.

> diff --git a/drivers/iommu/amd/iommu.c b/drivers/iommu/amd/iommu.c
> index b19e8c0f48fa..e2f8fb79ee53 100644

No, that wouldn't be better.

This seems sketchy, shouldn't the iommu driver be confirming that the
PSP has enabled the vDTE before making these assumptions?

> diff --git a/drivers/iommu/iommufd/hw_pagetable.c b/drivers/iommu/iommufd/hw_pagetable.c
> index aefde4443671..23ae95fc95ee 100644

Huh?

Jason

---

## [33] Jason Gunthorpe — 2024-08-27
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On Fri, Aug 23, 2024 at 11:21:21PM +1000, Alexey Kardashevskiy wrote:
> The module responsibilities are:
> 1. detect TEE support in a device and create nodes in the device's sysfs

Binding devices to VMs and managing their lifecycle is the purvue of
VFIO and iommufd, it should not be exposed via weird sysfs calls like
this. You can't build the right security model without being inside
the VFIO context.

As I said in the other email, it seems like the PSP and the iommu
driver need to coordinate to ensure the two DTEs are consistent, and
solve the other sequencing problems you seem to have.

I'm not convinced this should be in some side module - it seems like
this is possibly more logically integrated as part of the iommu..

> +static ssize_t tsm_dev_connect_store(struct device *dev, struct device_attribute *attr,
> +				     const char *buf, size_t count)

Please do a much better job explaining the uAPIS you are trying to
build in all the commit messages and how you expect them to be used.

Picking this stuff out of a 6k loc series is a bit tricky

Jason

---

## [34] Alexey Kardashevskiy — 2024-08-28
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On 27/8/24 22:32, Jason Gunthorpe wrote:
> On Fri, Aug 23, 2024 at 11:21:21PM +1000, Alexey Kardashevskiy wrote:
>> The module responsibilities are:

Is "extend the MAP_DMA uAPI to accept {gmemfd, offset}" enough for the 
VFIO context, or there is more and I am missing it?

> As I said in the other email, it seems like the PSP and the iommu
> driver need to coordinate to ensure the two DTEs are consistent, and

Correct. That DTE/sDTE hack is rather for showing the bare minimum 
needed to get IDE+TDISP going, we will definitely address this better.

> I'm not convinced this should be in some side module - it seems like
> this is possibly more logically integrated as part of the iommu..

There are two things which the module's sysfs interface tries dealing with:

1) device authentication (by the PSP, contrary to Lukas'es host-based 
CMA) and PCIe link encryption (PCIe IDE keys only programmable via the PSP);

2) VFIO + Coco VM.

The first part does not touch VFIO or IOMMU, and the sysfs interface 
provides API mostly for 1).

The proposed sysfs interface does not do VFIO or IOMMUFD binding though 
as it is weird indeed, even for test/bringup purposes, the only somewhat 
useful sysfs bit here is the interface report (a PCI/TDISP thing, comes 
from a device).

Besides sysfs, the module provides common "verbs" to be defined by the 
platform (which is right now a reduced set of the AMD PSP operations but 
the hope is it can be generalized); and the module also does PCIe DOE 
bouncing (which is also not uncommon). Part of this exercise is trying 
to find some common ground (if it is possible), hence routing everything 
via this module.


>> +static ssize_t tsm_dev_connect_store(struct device *dev, struct device_attribute *attr,
>> +				     const char *buf, size_t count)

True and sorry about that, will do better...

> Picking this stuff out of a 6k loc series is a bit tricky

Thanks for the comments!

> 
> Jason

---

## [35] Jonathan Cameron — 2024-08-28
*Subject: Re: [RFC PATCH 01/21] tsm-report: Rename module to reflect what it
 does*

On Fri, 23 Aug 2024 23:21:15 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> And release the name for TSM to be used for TDISP-associated code.
> 
Mention that it's not a simple file rename.
Some structure renames etc as well.

Maybe consider renaming the bits of the exported API as
well?


> Suggested-by: Dan Williams <dan.j.williams@intel.com>
> Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Perhaps makes sense to make thiese
tsm_report_register() etc.

> +#endif /* __TSM_REPORT_H */
> +

---

## [36] Jonathan Cameron — 2024-08-28
*Subject: Re: [RFC PATCH 03/21] pci: Define TEE-IO bit in PCIe device
 capabilities*

On Fri, 23 Aug 2024 23:21:17 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> A new bit #30 from the PCI Express Device Capabilities Register is defined
> in PCIe 6.1 as "TEE Device Interface Security Protocol (TDISP)".
No it isn't.

TEE-IO supported - When Set, this bit indicates the Function implements the TEE-IO
functionality as described by ....

So it is defined as TEE-IO not TDISP even though that definition is in the
TDISP section fo the spec.

As Bjorn said, spec reference.

Jonathan

> 
> Define the macro.

---

## [37] Jonathan Cameron — 2024-08-28
*Subject: Re: [RFC PATCH 04/21] PCI/IDE: Define Integrity and Data Encryption
 (IDE) extended capability*

On Fri, 23 Aug 2024 23:21:18 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> PCIe 6.0 introduces the "Integrity & Data Encryption (IDE)" feature which
> adds a new capability with id=0x30.

Ah. I should read the patch description before reviewing.
It is indeed horrible.

> 
> Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Hi Alexey,

Some comments inline.

> ---
>  drivers/pci/Makefile          |   1 +
Check for accidental white space changes. They distract from real content
so get rid of them before posting - even for an RFC.

>  /* Compute Express Link (CXL r3.1, sec 8.1.5) */
>  #define PCI_DVSEC_CXL_PORT				3

> +/* Link IDE Stream block, up to PCI_IDE_CAP_LINK_TC_NUM */
These are in a fixed location, so you can define an offset macro to get to each
register.

> +/* Link IDE Stream Control Register */
...

> +/* Link IDE Stream Status Register */


> +/* Selective IDE Stream block, up to PCI_IDE_CAP_SELECTIVE_STREAMS_NUM */
> +/* Selective IDE Stream Capability Register */
Space after /*


>  #endif /* LINUX_PCI_REGS_H */
> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
Prefix functions with something to indicate they are local.

ide_ or something like that.

Not obvious what sel_index parameter is. So documentation probably
needed for this function.

Also return an error, not 0 to mean error as it will be easier to read.



> +{
> +	u16 offset = pci_find_next_ext_capability(pdev, 0, PCI_EXT_CAP_ID_IDE);

I'd avoid mixing cases where the value is set and where it isn't.
Better to have
	unsigned int linknum = 0, selnum = 0;
	unsigned int i;

Though i might as well be int.


> +	u16 seloff;
> +	u32 cap = 0;
Not an error? That probably needs a comment.
> +
> +	pci_read_config_dword(pdev, offset + PCI_IDE_CAP, &cap);
	if (!(cap & PCI_IDE_CAP_SELECTIVE_IDE_SUPP))
		return -EINVAL; or whatever makes more sense.

	sel_num = PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(cap) + 1;
	if (selnum < sel_index)
		return -E...


> +
> +	if (!selnum || sel_index >= selnum)

2 and 4 have meaning. What are they? Use differences in addresses
of registers defined in header.


> +	for (i = 0; i < sel_index; ++i) {
> +		u32 selcap = 0;

Same here. All these offsets are in terms of real register differences,
use those and you won't need comments to explain.

> +	}
> +
Defines should exist for the registers, use the differences between them to
get these offsets.
It gets a little trickier for these as there is a variable size
field before them, but still good to do if possible.

> +		blocknum * 3 * 4; // Each block is Address Association Register 1, 2, 3
> +}
	int offset = ide_sel_off(pdev, sel_inxed);
> +	u32 status = 0;
> +
Return an error for sel_off not 0 on failure. Then pass that error on here.
	if (offset < 0)
		return -EINVAL;	
> +
> +	pci_read_config_dword(pdev, offset + 8, &status);

> +
> +int pci_ide_set_sel_addr_assoc(struct pci_dev *pdev, unsigned int sel_index, unsigned int blocknum,

How would you get the second condition?   Also, better to return
errors from these than 0 to indicate a problem.


> +		return -EINVAL;
> +

Check for error error returns consistently.


> +	/* IDE Address Association Register 2 */
> +	pci_write_config_dword(pdev, offset_ab + 4, a2);
With changes suggested above return the error code form sel_off.

> +
> +

Linux hasn't cared about driver versions for a long time
which is why relatively few drivers bother with them.
Why do we care here?

Also too noisy.

> +	return ret;
> +}

You don't have to have this until it has something in it.

> +}
> +

With the print above gone away, just use strings here.

> diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
> index b0b14468ba5d..8e908d684c77 100644
Don't set default.  Everything defaults to off and distro's
get to turn them on.

> +
>  config PCI_ECAM

---

## [38] Jonathan Cameron — 2024-08-28
*Subject: Re: [RFC PATCH 06/21] crypto: ccp: Enable SEV-TIO feature in the
 PSP when supported*

On Fri, 23 Aug 2024 23:21:20 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> The PSP advertises the SEV-TIO support via the FEATURE_INFO command
> support of which is advertised via SNP_PLATFORM_STATUS.
I was curious so had a read.
Some minor comments inline.

Jonathan

> ---
>  include/linux/psp-sev.h      | 31 ++++++++-

Comment seems to have drifted away from the structure.

> +#define SNP_FEATURE_FN8000_0024_EBX_X00_SEVTIO	1
> +

>  /**
> @@ -787,7 +811,8 @@ struct sev_data_range_list {

Has docs that want updating I think.

> +	u32 rsvd1:30;
>  } __packed;

> diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
> index f6eafde584d9..a49fe54b8dd8 100644

> +static int snp_feature_info_locked(struct sev_device *sev, u32 ecx,
> +				   struct sev_snp_feature_info *fi, int *psp_ret)
		goto cleanup
	}

	memcpy(fi, data, sizeof(*fi));

> +
> +	if (!ret)

rather than this is more consistent and hence easier to review.

> +
> +cleanup:

	free_page(status_page);

Maybe worth a DEFINE_FREE() to let you do early returns and make this
even nicer to read.



> +	return ret;
> +}

	won't get here as ret definitely == 0
given you checked it was just above.

> +		return -EFAULT;
> +	if (!status.feature_info)
and another.

	return snp_feature_info_locked(...


> +
> +	return 0;

Probably too noisy for final driver but fine for RFC I guess.

> +	return present;
> +}

---

## [39] Jonathan Cameron — 2024-08-28
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On Fri, 23 Aug 2024 23:21:21 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> The module responsibilities are:
> 1. detect TEE support in a device and create nodes in the device's sysfs



Main thing missing here is a sysfs ABI doc.

Otherwise, some random comments as I get my head around it.

Jonathan


> diff --git a/include/linux/tsm.h b/include/linux/tsm.h
> new file mode 100644
...


> +/* Physical device descriptor responsible for IDE/TDISP setup */
> +struct tsm_dev {

Kind of obvious, but still good to document what data this is protecting.

> +
> +	u8 tc_mask;

> diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
> new file mode 100644
...

>
> +struct tsm_tdi *tsm_tdi_get(struct device *dev)
	return dev->tdi;
seems fine to me.

> +}
> +EXPORT_SYMBOL_GPL(tsm_tdi_get);
	if (rc < 0)
		return rc;

	spdm->rsp_len = rc;
	
	return 0;

> +		spdm->rsp_len = rc;
> +

> +
> +static int tsm_ide_refresh(struct tsm_dev *tdev, void *private_data)
guard() and early returns.

> +	while (1) {
> +		ret = tsm.ops->ide_refresh(tdev, private_data);
guard() and early returns.

> +	while (1) {
> +		ret = tsm.ops->tdi_reclaim(tdi, private_data);


> +static int tsm_tdi_status(struct tsm_tdi *tdi, void *private_data, struct tsm_tdi_status *ts)
> +{
Perhaps scoped_guard() if it doesn't make sense to set *ts on error
(see below).
> +	while (1) {
> +		ret = tsm.ops->tdi_status(tdi, private_data, &tstmp);
Want to set this even on error?
> +
> +	return ret;


> +static ssize_t tsm_meas_show(struct device *dev, struct device_attribute *attr, char *buf)
> +{
Always true.

> +			n = tsm_meas_gen(tdev->meas, buf, PAGE_SIZE);
> +		if (!n)

> +
> +static struct attribute *host_dev_attrs[] = {
That final comma not needed as we'll never add anything after
this.

> +};
> +static const struct attribute_group host_dev_group = {


> +
> +static ssize_t tsm_report_show(struct device *dev, struct device_attribute *attr, char *buf)

Always true.

> +			n = tsm_report_gen(tdi->report, buf, PAGE_SIZE);
> +		if (!n)

in all cases this is only set once and if set nothing else
happens. Just return directly at those.

> +}

> +static char *spdm_algos_to_str(u64 algos, char *buf, size_t len)
> +{

Odd wrapping. I'd push the do { onto the next line and it will all look more normal.

> +
> +	__ALGO(DHE_SECP256R1);

> +
> +static ssize_t tsm_tdi_status_show(struct device *dev, struct device_attribute *attr, char *buf)
wrap
> +{

> +
> +static int tsm_tdi_init(struct tsm_dev *tdev, struct pci_dev *pdev)
set in all paths that use it.

> +
> +	dev_info(&pdev->dev, "Initializing tdi\n");
Is this defense needed?  Seems overkill given we just
got the tdev in all paths that lead here.

> +
> +	tdi = kzalloc(sizeof(*tdi), GFP_KERNEL);

As below, __free() + pointer steal will be neater here.

> +	pci_info(pdev, "TDI enabled=%d\n", pdev->dev.tdi_enabled);
> +

> +static int tsm_dev_init(struct pci_dev *pdev, struct tsm_dev **ptdev)
> +{

dev_dbg() for non RFC versions.

> +	tdev = kzalloc(sizeof(*tdev), GFP_KERNEL);
> +	if (!tdev)
Group not released
> +
> +		tdev->spdm.doe_mb_secured = pci_find_doe_mailbox(tdev->pdev,
Long lines.  I'd wrap after =

> +		if (!tdev->spdm.doe_mb_secured)
> +			goto pci_dev_put_exit;
nor here.

> +	}
> +

Could use __free() magic for tdev and steal the ptr here.
Maybe not worth the effort though given you need the error block anyway.


> +	return 0;
> +

dev_dbg() eventually but fine for RFC.

> +	pci_dev_put(tdev->pdev);
> +	kfree(tdev);
Trivial but... One blank line 
> +
> +		ret = tsm_dev_init(pdev, &tdev);

> +
> +static struct notifier_block tsm_pci_bus_nb = {

These aren't needed. If it's a library module it will have
nothing to do on init / exit which is fine.
And we don't care about versions! If we do then the discoverability
of features etc is totally broken.


> +
> +void tsm_set_ops(struct tsm_ops *ops, void *private_data)

scoped_guard() may help here and in the good path at least
allow a direct return.

> +	while (1) {
> +		ret = tsm.ops->tdi_bind(tdi, guest_rid, vmid, asid, tsm.private_data);

I'd have separate err_unlock label and error handling path.
This pattern is somewhat harder to read.

> +		tsm_tdi_unbind(tdi);
> +		return ret;
guard(mutex)(&tdi->tdev->spmd_mutex);

Then you can do returns on error or finish instead of breaking out
just to unlock.



> +	while (1) {
> +		ret = tsm.ops->guest_request(tdi, tdi->guest_rid, tdi->vmid, req_data,

> +
> +module_init(tsm_init);
Put these next to the relevant functions - or put the functions next to these.
> +module_exit(tsm_cleanup);
> +

I'd break this out as a separate patch - mostly to shout "DOCS here - read them"
as otherwise they end up at the end of a long email no one scrolls through.

> @@ -0,0 +1,62 @@
> +.. SPDX-License-Identifier: GPL-2.0

measurements 

> +over the link (limited though by the TSM capabilities).
> +A platform is expected to register a specific set of hooks. The same module works

No defaulting to m.  People get grumpy when this stuff turns up on their embedded
distros with no hardware support.

> +	depends on AMD_MEM_ENCRYPT
> +	select PCI_DOE

---

## [40] Jonathan Cameron — 2024-08-28
*Subject: Re: [RFC PATCH 08/21] crypto/ccp: Implement SEV TIO firmware
 interface*

On Fri, 23 Aug 2024 23:21:22 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> Implement SEV TIO PSP command wrappers in sev-dev-tio.c, these make
> SPDM calls and store the data in the SEV-TIO-specific structs.
Superficial comments online inline.

Jonathan

> ---
>  drivers/crypto/ccp/Makefile      |    2 +
spaces vs tabs. I guess go for consistency.

>                                     platform-access.o \
>                                     dbc.o \

> diff --git a/drivers/crypto/ccp/sev-dev-tio.c b/drivers/crypto/ccp/sev-dev-tio.c
> new file mode 100644

> +static size_t sla_dobj_id_to_size(u8 id)
> +{

Early returns will make this more readable.

> +}


> +/**
> + * struct sev_data_tio_dev_connect - TIO_DEV_CONNECT

Doesn't seem to be there.

> + * @dev_ctx_sla: Scatter list address of the device context buffer.
> + * @tc_mask: Bitmask of the traffic classes to initialize for SEV-TIO usage.


> +/**
> + * struct sev_data_tio_guest_request - TIO_GUEST_REQUEST command

Some more fields that aren't documented.  They all should be for
kernel-doc or the scripts will moan. 
I'd just run the script and fixup all the warnings and errors.


> + * @gctx_paddr: system physical address of guest context page
> + * @tdi_ctx_paddr: SPA of page donated by hypervisor



> +int sev_tio_tdi_status(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
> +		       struct tsm_spdm *spdm)

return sev_tio_do_cmd()

Same in other similar cases.

> +}


> diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
> new file mode 100644
I'm not totally convinced this is worth while vs simply checking
at call sites.

> +	return -EINVAL;
> +}
...

> +
> +free_exit:

Correct to free even if not allocated here?
Perhaps a comment if so.

> +
> +	return ret;


> +static int ide_refresh(struct tsm_dev *tdev, void *private_data)
> +{

	return sev_tio_ide_refresh()

> +}

> +
> +static int tdi_create(struct tsm_tdi *tdi)
	if (ret) {
		kfree(tdi_data);
		return ret;
	}

	tid->data = tdi_data;

	return 0;

is slightly longer but a more standard form so easier to review.

> +	else
> +		tdi->data = tdi_data;

> +
> +static int guest_request(struct tsm_tdi *tdi, u32 guest_rid, u64 kvmid, void *req_data,

Probably wrap nearer 80 chars.

> +			 enum tsm_tdisp_state *state, void *private_data)
> +{

If the above returned an error is psp_ret always set? I think not.
So maybe separate if (ret) condition, then set this and finally call
the code below.

> +		ret = mkret(ret, dev_data);
> +		if (ret > 0)

Given code as it stands. Might as well return here.

> +	} else if (dev_data->cmd == SEV_CMD_TIO_TDI_STATUS) {
Making this just an if.

> +		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
> +		ret = mkret(ret, dev_data);
and here.

> +	} else {

Making this the inline code as no need for else.

> +		pci_err(tdi->pdev, "Wrong state, cmd 0x%x in flight\n",
> +			dev_data->cmd);

---

## [41] Jonathan Cameron — 2024-08-28
*Subject: Re: [RFC PATCH 17/21] coco/sev-guest: Implement the guest side of
 things*

On Fri, 23 Aug 2024 23:21:31 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> Define tsm_ops for the guest and forward the ops calls to the HV via
> SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST.
More trivial stuff.

> diff --git a/drivers/virt/coco/sev-guest/sev_guest_tio.c b/drivers/virt/coco/sev-guest/sev_guest_tio.c
> new file mode 100644



> +static int tio_tdi_sdte_write(struct tsm_tdi *tdi, struct snp_guest_dev *snp_dev, bool invalidate)
> +{

Little odd to fill it then zero it.  Maybe just fill it
if !invalidate

> +
> +	pci_notice(tdi->pdev, "SDTE write vTOM=%lx", (unsigned long) req.sdte.vtom << 21);

I'd allocate rsp down here as then obvious what is going on.

> +		return -ENOMEM;
> +

kfree_sensitive() perhaps?

> +	return rc;
> +}

> +static int sev_guest_tdi_validate(struct tsm_tdi *tdi, bool invalidate, void *private_data)
> +{
I'd split the error paths to simplify the logic.
		if (ret) {
			pci_err(tdi->pdev, "No report available, ret=%d", ret);
			return ret;
		}
		if (!tdi->report) {
			pci_err(... some more meaningful message)
			return -EIO;
> +		}
> +

return tio_tdi_mmio_validate();

> +	if (ret)
> +		return ret;

---

## [42] Dan Williams — 2024-08-28
*Subject: Re: [RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO*

Alexey Kardashevskiy wrote:
> Hi everyone,
> 

This cover letter is something I can read after having been in and
around this space for a while, but I wonder how much of it makes sense
to casual reviewers?

> 
> Thanks,
[..]
> Code
> ----

What kind of hack are we talking about here? An upstream suitable
change, or something that needs quite a bit more work to be done
properly?

I jumped ahead to read Jason's reaction but please do at least provide a
map the controversy in the cover letter, something like "see patch 12 for
details".

> - skipping various enforcements of non-SME or
> SWIOTLB in the guest;

Is this based on some concept of private vs shared mode devices?

> No mixed share+private DMA supported within the
> same IOMMU.

What does this mean? A device may not have mixed mappings (makes sense),
or an IOMMU can not host devices that do not all agree on whether DMA is
private or shared?

> Enable secure MMIO by:
> - configuring RMP entries via the PSP;

Here is where I lament that kvm-coco-queue is not run like akpm/mm where
it is possible to try out "yesterday's mm". Perhaps this is an area to
collaborate on kvm-coco-queue snapshots to help with testing.

> Workflow
> --------

Would the device not just launch in "shared" mode until it is later
converted to private? I am missing the detail of why passing the device
on the command line requires that private memory be mapped early.

That said, the implication that private device assignment requires
hotplug events is a useful property. This matches nicely with initial
thoughts that device conversion events are violent and might as well be
unplug/replug events to match all the assumptions around what needs to
be updated.

> This requires the BME hack as MMIO and

Not sure what the "BME hack" is, I guess this is foreshadowing for later
in this story.

> BusMaster enable bits cannot be 0 after MMIO
> validation is done

It would be useful to call out what is a TDISP requirement, vs
device-specific DSM vs host-specific TSM requirement. In this case I
assume you are referring to PCI 6.2 11.2.6 where it notes that TDIs must
enter the TDISP ERROR state if BME is cleared after the device is
locked?

...but this begs the question of whether it needs to be avoided outright
or handled as an error recovery case dependending on policy.

> the guest OS booting process when this
> appens.

At first though avoiding SVSM entanglements where the kernel can be
enlightened shoud be the policy. I would only expect SVSM hacks to cover
for legacy OSes that will never be TDISP enlightened, but in that case
we are likely talking about fully unaware L2. Lets assume fully
enlightened L1 for now.

> QEMU advertises TEE-IO capability to the VM.
> An additional x-tio flag is added to

Hey, it's a start. I appreciate the "release early" aspect of this
posting.

> Git trees
> ---------
[..]
> 
>

---

## [43] Jason Gunthorpe — 2024-08-28
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On Wed, Aug 28, 2024 at 01:00:46PM +1000, Alexey Kardashevskiy wrote:
> 
> 

No, you need to have all the virtual PCI device creation stuff linked
to a VFIO cdev to prove you have rights to do things to the physical
device.
 
> > I'm not convinced this should be in some side module - it seems like
> > this is possibly more logically integrated as part of the iommu..

So when I look at the spec I think that probably TIO_DEV_* should be
connected to VFIO, somewhere as vfio/kvm/iommufd ioctls. This needs to
be coordinated with everyone else because everyone has *some kind* of
"trusted world create for me a vPCI device in the secure VM" set of
verbs.

TIO_TDI is presumably the device authentication stuff?

This is why I picked on tsm_dev_connect_store()..

> Besides sysfs, the module provides common "verbs" to be defined by the
> platform (which is right now a reduced set of the AMD PSP operations but the

I think there is a seperation between how the internal stuff in the
kernel works and how/what the uAPIs are.

General stuff like authenticate/accept/authorize a PCI device needs
to be pretty cross platform.

Stuff like creating vPCIs needs to be ioctls linked to KVM/VFIO
somehow and can have more platform specific components.

I would try to split your topics up more along those lines..

Jason

---

## [44] Dan Williams — 2024-08-28
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

Jason Gunthorpe wrote:
[..]
> So when I look at the spec I think that probably TIO_DEV_* should be
> connected to VFIO, somewhere as vfio/kvm/iommufd ioctls. This needs to

I would expect no, because device authentication is purely a
physical-device concept, and a TDI is some subset of that device (up to
and including full physical-function passthrough) that becomes VM
private-world assignable.

> This is why I picked on tsm_dev_connect_store()..
> 

I agree with this. There is a definite PCI only / VFIO-independent
portion of this that is before any consideration of TDISP LOCKED and RUN
states. It only deals with PCI device-authentication, link encryption
management, and is independent of any confidential VM. Then there is the
whole "assignable device" piece that is squarely KVM/VFIO territory.

Theoretically one could stop at link encryption setup and never proceed
with the rest. That is, assuming the platform allows for IDE protected
traffic to flow in the "T=0" (shared world device) case.

---

## [45] Jason Gunthorpe — 2024-08-28
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On Wed, Aug 28, 2024 at 05:00:57PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> [..]

So I got it backwards then? The TDI is the vPCI and DEV is the way to
operate TDISP/IDE/SPDM/etc? Spec says:

 To use a TDISP capable device with SEV-TIO, host software must first
 arrange for the SEV firmware to establish a connection with the device
 by invoking the TIO_DEV_CONNECT
 command. The TIO_DEV_CONNECT command performs the following:

 * Establishes a secure SPDM session using Secured Messages for SPDM.
 * Constructs IDE selective streams between the root complex and the device.
 * Checks the TDISP capabilities of the device.

Too many TLAs :O

> I agree with this. There is a definite PCI only / VFIO-independent
> portion of this that is before any consideration of TDISP LOCKED and RUN

Yes
 
> Theoretically one could stop at link encryption setup and never proceed
> with the rest. That is, assuming the platform allows for IDE protected

Yes. I keep hearing PCI people talking about interesting use cases for
IDE streams independent of any of the confidential compute stuff. I
think they should not be tied together.

Jason

---

## [46] Dan Williams — 2024-08-28
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

Jason Gunthorpe wrote:
> On Wed, Aug 28, 2024 at 05:00:57PM -0700, Dan Williams wrote:
> > Jason Gunthorpe wrote:

Right.

> 
>  To use a TDISP capable device with SEV-TIO, host software must first

My favorite is that the spec calls the device capability "TEE I/O" but
when you are speaking it no one can tell if you are talking about "TEE
I/O" the generic PCI thing, or "TIO", the AMD-specific seasoning on top
of TDISP.

> > I agree with this. There is a definite PCI only / VFIO-independent
> > portion of this that is before any consideration of TDISP LOCKED and RUN

I encourage those folks need to read the actual hardware specs, not just
the PCI spec. As far as I know there is only one host platform
implementation that allows IDE establishment and traffic flow for T=0
cases. So it is not yet trending to be a common thing that the PCI core
can rely upon.

---

## [47] Alexey Kardashevskiy — 2024-08-29
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On 29/8/24 09:42, Jason Gunthorpe wrote:
> On Wed, Aug 28, 2024 at 01:00:46PM +1000, Alexey Kardashevskiy wrote:
>>

The VM-to-VFIOdevice binding is already in the KVM VFIO device, the rest 
is the same old VFIO.

>>> I'm not convinced this should be in some side module - it seems like
>>> this is possibly more logically integrated as part of the iommu..

Not really. In practice:
- TDI is usually a SRIOV VF (and intended for passing through to a VM);
- DEV is always PF#0 of a (possibly multifunction) physical device which 
controls physical link encryption and authentication.

> This is why I picked on tsm_dev_connect_store()..
> >> Besides sysfs, the module provides common "verbs" to be defined by the

So those TIO_DEV_*** are for the PCI layer and nothing there is for 
virtualization and this is what is exposed via sysfs.

TIO_TDI_*** commands are for virtualization and, say, the user cannot 
attach a TDI to a VM by using the sysfs interface (new ioctls are for 
this), the user can only read some shared info about a TDI (interface 
report, status).

> Stuff like creating vPCIs needs to be ioctls linked to KVM/VFIO
> somehow and can have more platform specific components.

Right, I am adding ioctls to the KVM VFIO device.

> I would try to split your topics up more along those lines..

Fair point, my bad. I'll start with a PF-only module and then add TDI 
stuff to it separately.

I wonder if there is enough value to try keeping the TIO_DEV_* and 
TIO_TDI_* API together or having TIO_DEV_* in some PCI module and 
TIO_TDI_* in KVM is a non-confusing way to proceed with this. Adding 
things to the PCI's sysfs from more places bothers me more than this 
frankenmodule. Thanks,

---

## [48] Xu Yilun — 2024-08-29
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Mon, Aug 26, 2024 at 09:30:24AM -0300, Jason Gunthorpe wrote:
> On Mon, Aug 26, 2024 at 08:39:25AM +0000, Tian, Kevin wrote:
> > > IOMMUFD calls get_user_pages() for every mapping which will allocate

A uAPI like ioctl(MAP_DMA, gmemfd, offset, iova) still means userspace
takes control of the IOMMU mapping in the unsecure world. But as
mentioned, the unsecure world mapping is just a "copy" and has no
generic meaning without the CoCo-VM context. Seems no need for userspace
to repeat the "copy" for IOMMU.

Maybe userspace could just find a way to link the KVM context to IOMMU
at the first place, then let KVM & IOMMU directly negotiate the mapping
at runtime.

Thanks,
Yilun

> 
> Jason

---

## [49] Xu Yilun — 2024-08-29
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

> diff --git a/virt/kvm/vfio.c b/virt/kvm/vfio.c
> index 76b7f6085dcd..a4e9db212adc 100644

I think the TDI bind operation should be under the control of the device
owner (i.e. VFIO driver), rather than in this bridge driver. The TDI bind
means TDI would be transitioned to CONFIG_LOCKED state, and a bunch of
device configurations breaks the state (TDISP spec 11.4.5/8/9). So the
VFIO driver should be fully aware of the TDI bind and manage unwanted
breakage.

Thanks,
Yilun

---

## [50] Jason Gunthorpe — 2024-08-29
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On Wed, Aug 28, 2024 at 05:20:16PM -0700, Dan Williams wrote:

> I encourage those folks need to read the actual hardware specs, not just
> the PCI spec. As far as I know there is only one host platform

I think their perspective is this is the only path to do certain
things in PCI land (from a packet on the wire perspective) so they
would expect the platforms to align eventually if the standards go
that way..

Jason

---

## [51] Jason Gunthorpe — 2024-08-29
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On Thu, Aug 29, 2024 at 02:57:34PM +1000, Alexey Kardashevskiy wrote:

> > > Is "extend the MAP_DMA uAPI to accept {gmemfd, offset}" enough for the VFIO
> > > context, or there is more and I am missing it?

Frankly, I'd rather not add any more VFIO stuff to KVM. Today KVM has
no idea of a VFIO on most platforms.

Given you already have an issue with iommu driver synchronization this
looks like it might be a poor choice anyhow..

> I wonder if there is enough value to try keeping the TIO_DEV_* and TIO_TDI_*
> API together or having TIO_DEV_* in some PCI module and TIO_TDI_* in KVM is

I wouldn't mix them up, they are very different. Just because they are
RPCs to the same bit of FW doesn't really mean they should be together
in the same interfaces or ops structures.

Jason

---

## [52] Jason Gunthorpe — 2024-08-29
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Thu, Aug 29, 2024 at 05:34:52PM +0800, Xu Yilun wrote:
> On Mon, Aug 26, 2024 at 09:30:24AM -0300, Jason Gunthorpe wrote:
> > On Mon, Aug 26, 2024 at 08:39:25AM +0000, Tian, Kevin wrote:

Yes, such is how it seems to work.

It doesn't actually have much control, it has to build a mapping that
matches the RMP table exactly but still has to build it..

> But as mentioned, the unsecure world mapping is just a "copy" and
> has no generic meaning without the CoCo-VM context. Seems no need

Well, here I say copy from the information already in the PSP secure
world in the form fo their RMP, but in a different format.

There is another copy in KVM in it's stage 2 translation but..

> Maybe userspace could just find a way to link the KVM context to IOMMU
> at the first place, then let KVM & IOMMU directly negotiate the mapping

I think the KVM folks have said no to sharing the KVM stage 2 directly
with the iommu. They do too many operations that are incompatible with
the iommu requirements for the stage 2.

If that is true for the confidential compute, I don't know.

Still, continuing to duplicate the two mappings as we have always done
seems like a reasonable place to start and we want a memfd map anyhow
for other reasons:

https://lore.kernel.org/linux-iommu/20240806125602.GJ478300@nvidia.com/

Jason

---

## [53] Alexey Kardashevskiy — 2024-08-30
*Subject: Re: [RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO*

On 29/8/24 06:43, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> Hi everyone,

Right now it is hacking IOMMUFD to go to the KVM for 
private_gfn->host_pfn. As I am being told in this thread, VFIO DMA 
map/unmap needs to be taught to accept {memfd, offset}.


> I jumped ahead to read Jason's reaction but please do at least provide a
> map the controversy in the cover letter, something like "see patch 12 for

Yeah, noticed that, thanks, appreciated!

>> - skipping various enforcements of non-SME or
>> SWIOTLB in the guest;

Currently devices do not have an idea about private host memory (but it 
is being worked on afaik).

> or an IOMMU can not host devices that do not all agree on whether DMA is
> private or shared?

The hardware allows that via hardware-assisted vIOMMU and I/O page 
tables in the guest with C-bit takes into accound by the IOMMU but the 
software support is missing right now. So for this initial drop, vTOM is 
used for DMA - this thing says "everything below <addr> is private, 
above <addr> - shared" so nothing needs to bother with the C-bit, and in 
my exercise I set the <addr> to the allowed maximum.

So each IOMMUFD instance in the VM is either "all private mappings" or 
"all shared". Could be half/half by moving that <addr> :)


>> Enable secure MMIO by:
>> - configuring RMP entries via the PSP;

Yeah this more an idea of what it is based on, I normally push a tested 
branch somewhere on github, just to eliminate uncertainty.

> 
>> Workflow

A sequencing problem.

QEMU "realizes" a VFIO device, it creates an iommufd instance which 
creates a domain and writes to a DTE (a IOMMU descriptor for PCI BDFn). 
And DTE is not updated after than. For secure stuff, DTE needs to be 
slightly different. So right then I tell IOMMUFD that it will handle 
private memory.

Then, the same VFIO "realize" handler maps the guest memory in iommufd. 
I use the same flag (well, pointer to kvm) in the iommufd pinning code, 
private memory is pinned and mapped (and related page state change 
happens as the guest memory is made guest-owned in RMP).

QEMU goes to machine_reset() and calls "SNP LAUNCH UPDATE" (the actual 
place changed recenly, huh) and the latter will measure the guest and 
try making all guest memory private but it already happened => error.

I think I have to decouple the pinning and the IOMMU/DTE setting.

> That said, the implication that private device assignment requires
> hotplug events is a useful property. This matches nicely with initial

For the initial drop, I tell QEMU via "-device vfio-pci,x-tio=true" that 
it is going to be private so there should be no massive conversion.

> 
>> This requires the BME hack as MMIO and
 >
>> BusMaster enable bits cannot be 0 after MMIO
>> validation is done

Oh there is 6.2 already.

> enter the TDISP ERROR state if BME is cleared after the device is
> locked?

Well, besides a couple of avoidable places (like testing INTx support 
which we know is not going to work on VFs anyway), a standard driver 
enables MSE first (and the value for the command register does not have 
1 for BME) and only then BME. TBH I do not think writing BME=0 when 
BME=0 already is "clearing" but my test device disagrees.

> or handled as an error recovery case dependending on policy.

Avoding seems more straight forward unless we actually want enlightened 
device drivers which want to examine the interface report before 
enabling the device. Not sure.

>> the guest OS booting process when this
>> appens.

Well, I could also tweak OVMF to make necessary calls to the PSP and 
hack QEMU to postpone the command register updates to get this going, 
just a matter of ugliness.

>> QEMU advertises TEE-IO capability to the VM.
>> An additional x-tio flag is added to

:)

Thanks,


>> Git trees
>> ---------

---

## [54] Dan Williams — 2024-08-29
*Subject: Re: [RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO*

Alexey Kardashevskiy wrote:
[..]
> >> - skipping various enforcements of non-SME or
> >> SWIOTLB in the guest;

Worked on where? You mean the PCI core indicating that a device is
private or not? Is that not indicated by guest-side TSM connection
state?

> > or an IOMMU can not host devices that do not all agree on whether DMA is
> > private or shared?

I thought existing use cases assume that the CC-VM can trigger page
conversions at will without regard to a vTOM concept? It would be nice
to have that address-map separation arrangement, has not that ship
already sailed?

[..]
> > Would the device not just launch in "shared" mode until it is later
> > converted to private? I am missing the detail of why passing the device

That's a SEV-TIO RFC-specific hack, or a proposal?

An approach that aligns more closely with the VFIO operational model,
where it maps and waits for guest faults / usages, is that QEMU would be
told that the device is "bind capable", because the host is not in a
position to assume how the guest will use the device. A "bind capable"
device operates in shared mode unless and until the guest triggers
private conversion.

> >> This requires the BME hack as MMIO and
> > 

...but we should not be creating kernel policy around test devices. What
matters is real devices. Now, if it is likely that real / production
devices will go into the TDISP ERROR state by not coalescing MSE + BME
updates then we need a solution.

Given it is unlikely that TDISP support will be widespread any time soon
it is likely tenable to assume TDISP compatible drivers call a new:

   pci_enable(pdev, PCI_ENABLE_TARGET | PCI_ENABLE_INITIATOR);

...or something like that to coalesce command register writes.

Otherwise if that retrofit ends up being too much work or confusion then
the ROI of teaching the PCI core to recover this scenario needs to be
evaluated.

> > or handled as an error recovery case dependending on policy.
> 

If TDISP capable devices trends towards a handful of devices in the near
term then some driver fixups seems reasonable. Otherwise if every PCI
device driver Linux has ever seens needs to be ready for that device to
have a TDISP capable flavor then mitigating this in the PCI core makes
more sense than playing driver whack-a-mole.

> >> the guest OS booting process when this
> >> appens.

Per above, the tradeoff should be in ROI, not ugliness. I don't see how
OVMF helps when devices might be being virtually hotplugged or reset.

---

## [55] Dan Williams — 2024-08-29
*Subject: Re: [RFC PATCH 01/21] tsm-report: Rename module to reflect what it
 does*

Alexey Kardashevskiy wrote:
> And release the name for TSM to be used for TDISP-associated code.

I had a more comprehensive rename in mind so that grepping is a bit more
reliable between tsm_report_ and tsm_ symbol names. I am still looking
to send that series out, but for now here is that rename commit:

https://git.kernel.org/pub/scm/linux/kernel/git/djbw/linux.git/commit/?id=5174e044d64f

...and here is an additional fixup to prep for drivers/virt/coco/
containing both host and guest common code:

https://git.kernel.org/pub/scm/linux/kernel/git/djbw/linux.git/commit/?id=68fb296b36f2

---

## [56] Dan Williams — 2024-08-29
*Subject: Re: [RFC PATCH 02/21] pci/doe: Define protocol types and make those
 public*

Alexey Kardashevskiy wrote:
> Already public pci_doe() takes a protocol type argument.
> PCIe 6.0 defines three, define them in a header for use with pci_doe().

Why does discovery need to be global?

> +#define PCI_DOE_PROTOCOL_CMA_SPDM		1
> +#define PCI_DOE_PROTOCOL_SECURED_CMA_SPDM	2

Would be useful to have a brief idea of the consumer of these new global
definitions in the changelog.

Also you said this is based on Lukas's patches which already define
PCI_DOE_FEATURE_CMA, so lets unify that.

---

## [57] Dan Williams — 2024-08-29
*Subject: Re: [RFC PATCH 03/21] pci: Define TEE-IO bit in PCIe device
 capabilities*

Alexey Kardashevskiy wrote:
> A new bit #30 from the PCI Express Device Capabilities Register is defined
> in PCIe 6.1 as "TEE Device Interface Security Protocol (TDISP)".

Not sure this is justified as a standalone patch, lets fold it in with
its user.

---

## [58] Dan Williams — 2024-08-29
*Subject: Re: [RFC PATCH 04/21] PCI/IDE: Define Integrity and Data Encryption
 (IDE) extended capability*

Alexey Kardashevskiy wrote:
> PCIe 6.0 introduces the "Integrity & Data Encryption (IDE)" feature which
> adds a new capability with id=0x30.

This changelog needs a theory of operation to explain how it is used and
to give some chance of reviewing whether this is implementing more than
is required to get the job done.

> Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
> ---
[..]
> diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
> new file mode 100644
[..]
> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> new file mode 100644

This is not a driver. It is a helper library for the TSM core and maybe
native PCI IDE establishment in the future.

I am not what purpose AUTHOR, VERSION and DESC, serve as I do not see
how this can get away with being a module when the TSM core is built-in
to be initialized via pci_init_capabilities().

[..]

Difficult to review the implementation without a clear idea of the user,
and the exports are not necessary if the only consumer is the PCI core.

> +
> +static int __init ide_init(void)

Setting aside the tristate, no new kernel code should unconditionally
enable itself by default.

---

## [59] Dan Williams — 2024-08-29
*Subject: Re: [RFC PATCH 05/21] crypto/ccp: Make some SEV helpers public*

Alexey Kardashevskiy wrote:
> For SEV TIO.

I would exepct even an RFC to have reasonable change logs.

---

## [60] Alexey Kardashevskiy — 2024-08-30
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On 29/8/24 22:15, Jason Gunthorpe wrote:
> On Thu, Aug 29, 2024 at 05:34:52PM +0800, Xu Yilun wrote:
>> On Mon, Aug 26, 2024 at 09:30:24AM -0300, Jason Gunthorpe wrote:


Sorry, I am missing the point here. IOMMU maps bus addresses (IOVAs) to 
host physical, if we skip IOMMU, then how RMP (maps host pfns to guest 
pfns) will help to map IOVA (in fact, guest pfn) to host pfn? Thanks,

---

## [61] Alexey Kardashevskiy — 2024-08-30
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

On 29/8/24 20:08, Xu Yilun wrote:
>> diff --git a/virt/kvm/vfio.c b/virt/kvm/vfio.c
>> index 76b7f6085dcd..a4e9db212adc 100644

This is a valid point, although this means teaching VFIO about the KVM 
lifetime (and KVM already holds references to VFIO groups) and guest 
BDFns (which have no meaning for VFIO in the host kernel).

> The TDI bind
> means TDI would be transitioned to CONFIG_LOCKED state, and a bunch of

VFIO has no control over TDI any way, cannot even know what state it is 
in without talking to the firmware. When TDI goes into ERROR, this needs 
to be propagated to the VM. At the moment (afaik) it does not tell the 
userspace/guest about IOMMU errors and it probably should but the 
existing mechanism should be able to do so. Thanks,


> 
> Thanks,

---

## [62] Alexey Kardashevskiy — 2024-08-30
*Subject: Re: [RFC PATCH 03/21] pci: Define TEE-IO bit in PCIe device
 capabilities*

On 30/8/24 12:21, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> A new bit #30 from the PCI Express Device Capabilities Register is defined

not sure either but this one is already defined in the PCIe spec for 
some time and lspci knows it but it is going quite some time before "its 
user" makes it to the upstream linux.

---

## [63] Alexey Kardashevskiy — 2024-08-30
*Subject: Re: [RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO*

On 30/8/24 09:41, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
> [..]
DMA is
>>> private or shared?
>>

Mmm. I am either confusing you too much or not following you :) Any page 
can be converted, the proposed arrangement would require that 
convertion-candidate-pages are allocated from a specific pool?

There are two vTOMs - one in IOMMU to decide on Cbit for DMA trafic (I 
use this one), one in VMSA ("VIRTUAL_TOM") for guest memory (this 
exercise is not using it). Which one do you mean?

> 
> [..]

Not sure at the moment :)

> An approach that aligns more closely with the VFIO operational model,
> where it maps and waits for guest faults / usages, is that QEMU would be

True. I just started this exercise without QEMU DiscardManager. Now I 
rely on it but it either needs to allow dynamic flip from 
discarded==private to discarded==shared (should do for now) or  allow 3 
states for guest pages.

>>>> This requires the BME hack as MMIO and
>>>

True but I do not even know who to ask this question :)

> Given it is unlikely that TDISP support will be widespread any time soon
> it is likely tenable to assume TDISP compatible drivers call a new:

Agree.

>>> or handled as an error recovery case dependending on policy.
>>
 >
>>>> the guest OS booting process when this
>>>> appens.

I have no clue how exactly hotplug works on x86, is not BIOS playing 
role in it? Thanks,

---

## [64] Xu Yilun — 2024-08-30
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Thu, Aug 29, 2024 at 09:15:49AM -0300, Jason Gunthorpe wrote:
> On Thu, Aug 29, 2024 at 05:34:52PM +0800, Xu Yilun wrote:
> > On Mon, Aug 26, 2024 at 09:30:24AM -0300, Jason Gunthorpe wrote:

I kind of agree.

I'm not considering the page table sharing for AMD's case. I was just
thinking about the way we sync up the secure mapping for KVM & IOMMU,
when Page attribute conversion happens, still via userspace or KVM
directly notifies IOMMU.

> 
> If that is true for the confidential compute, I don't know.

For Intel TDX TEE-IO, there may be a different story.

Architechturely the secure IOMMU page table has to share with KVM secure
stage 2 (SEPT). The SEPT is managed by firmware (TDX Module), TDX Module
ensures the SEPT operations good for secure IOMMU, so there is no much
trick to play for SEPT.

> 
> Still, continuing to duplicate the two mappings as we have always done

---

## [65] Xu Yilun — 2024-08-30
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

On Fri, Aug 30, 2024 at 02:00:30PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Not sure if I understand, VFIO already knows KVM lifetime via
vfio_device_get_kvm_safe(), is it?

> guest BDFns (which have no meaning for VFIO in the host kernel).

KVM is not aware of the guest BDF today.

I think we need to pass a firmware recognizable TDI identifier, which
is actually a magic number and specific to vendors. For TDX, it is the
FUNCTION_ID. So I didn't think too much to whom the identifier is
meaningful.

> 
> > The TDI bind

I think VFIO could talk to the firmware, that's part of the reason we are
working on the TSM module independent to KVM.

> When TDI goes into ERROR, this needs to be
> propagated to the VM. At the moment (afaik) it does not tell the

I assume when TDISP ERROR happens, an interrupt (e.g. AER) would be sent
to OS and VFIO driver is the one who handles it in the first place. So
maybe there has to be some TDI stuff in VFIO?

Thanks,
Yilun

> userspace/guest about IOMMU errors and it probably should but the existing
> mechanism should be able to do so. Thanks,

---

## [66] Jason Gunthorpe — 2024-08-30
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Fri, Aug 30, 2024 at 01:47:40PM +1000, Alexey Kardashevskiy wrote:
> > > > Yes, we want a DMA MAP from memfd sort of API in general. So it should
> > > > go directly to guest memfd with no kvm entanglement.

It is the explanation for why this is safe.

For CC the translation of IOVA to physical must not be controlled by
the hypervisor, for security. This can result in translation based
attacks.

AMD is weird because it puts the IOMMU page table in untrusted
hypervisor memory, everyone else seems to put it in the trusted
world's memory.

This works for AMD because they have two copies of this translation,
in two different formats, one in the RMP which is in trusted memory
and one in the IO page table which is not trusted. Yes you can't use
the RMP to do an IOVA lookup, but it does encode exactly the same
information.

Both must agree on the IOVA to physical mapping otherwise the HW
rejects it. Meaning the IOMMU configuration must perfectly match the
RMP configuration.

Jason

---

## [67] Jason Gunthorpe — 2024-08-30
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Fri, Aug 30, 2024 at 01:20:12PM +0800, Xu Yilun wrote:

> > If that is true for the confidential compute, I don't know.
> 

Yes, I think ARM will do the same as well.

From a uAPI perspective we need some way to create a secure vPCI
function linked to a KVM and some IOMMUs will implicitly get a
translation from the secure world and some IOMMUs will need to manage
it in untrusted hypervisor memory.

Jason

---

## [68] Xu Yilun — 2024-08-31
*Subject: Re: [RFC PATCH 13/21] KVM: X86: Handle private MMIO as shared*

On Fri, Aug 23, 2024 at 11:21:27PM +1000, Alexey Kardashevskiy wrote:
> Currently private MMIO nested page faults are not expected so when such
> fault occurs, KVM tries moving the faulted page from private to shared

This means host keeps the mapping for private MMIO, which is different
from private memory. Not sure if it is expected, and I want to get
some directions here.

From HW perspective, private MMIO is not intended to be accessed by
host, but the consequence may varies. According to TDISP spec 11.2,
my understanding is private device (known as TDI) should reject the
TLP and transition to TDISP ERROR state. But no further error
reporting or logging is mandated. So the impact to the host system
is specific to each device. In my test environment, an AER
NonFatalErr is reported and nothing more, much better than host
accessing private memory.

On SW side, my concern is how to deal with mmu_notifier. In theory, if
we get pfn from hva we should follow the userspace mapping change. But
that makes no sense. Especially for TDX TEE-IO, private MMIO mapping
in SEPT cannot be changed or invalidated as long as TDI is running.

Another concern may be specific for TDX TEE-IO. Allowing both userspace
mapping and SEPT mapping may be safe for private MMIO, but on
KVM_SET_USER_MEMORY_REGION2,  KVM cannot actually tell if a userspace
addr is really for private MMIO. I.e. user could provide shared memory
addr to KVM but declare it is for private MMIO. The shared memory then
could be mapped in SEPT and cause problem.

So personally I prefer no host mapping for private MMIO.

Thanks,
Yilun

> page state tracking.
>

---

## [69] Dan Williams — 2024-08-30
*Subject: Re: [RFC PATCH 03/21] pci: Define TEE-IO bit in PCIe device
 capabilities*

Alexey Kardashevskiy wrote:
> On 30/8/24 12:21, Dan Williams wrote:
> > Alexey Kardashevskiy wrote:

So, wait. I.e. if the answer to the question "what does Linux lose by
not merging a patch?" is "nothing", then there is no urgency to merge
it.

---

## [70] Dan Williams — 2024-08-30
*Subject: Re: [RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO*

Alexey Kardashevskiy wrote:
[..]
> > I thought existing use cases assume that the CC-VM can trigger page
> > conversions at will without regard to a vTOM concept? It would be nice

Dunno, you introduced the vTOM term. Suffice to say if any page can be
converted in this model then I was confused.

> > [..]
> >>> Would the device not just launch in "shared" mode until it is later

Ok, without more information it looks like a SEV-TIO shortcut.

> > An approach that aligns more closely with the VFIO operational model,
> > where it maps and waits for guest faults / usages, is that QEMU would be

As we talked about on the KernelSIG call there is a potentially a
guestmemfd proposal to handle in place conversion without a
DiscardManager:

https://lore.kernel.org/kvm/20240712232937.2861788-1-ackerleytng@google.com/

[..]
> > Per above, the tradeoff should be in ROI, not ugliness. I don't see how
> > OVMF helps when devices might be being virtually hotplugged or reset.

The hotplug controller can either be native PCIe or firmware managed.
Likely we would pick the path of least of resistance for QEMU to
facilitate device conversion.

---

## [71] Alexey Kardashevskiy — 2024-09-02
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On 29/8/24 22:07, Jason Gunthorpe wrote:
> On Thu, Aug 29, 2024 at 02:57:34PM +1000, Alexey Kardashevskiy wrote:
> 
TIO_TDI_*
>> API together or having TIO_DEV_* in some PCI module and TIO_TDI_* in KVM is
>> a non-confusing way to proceed with this. Adding things to the PCI's sysfs

Both DEV_* and TDI_* use the same SecureSPDM channel (on top of the 
PF#0's PCIe DOE cap) for IDE_KM (for DEV_*) and TDISP (for TDI_*) so 
there is some common ground. Thanks,

---

## [72] Alexey Kardashevskiy — 2024-09-02
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On 30/8/24 22:35, Jason Gunthorpe wrote:
> On Fri, Aug 30, 2024 at 01:47:40PM +1000, Alexey Kardashevskiy wrote:
>>>>> Yes, we want a DMA MAP from memfd sort of API in general. So it should

It is exactly the same because today VFIO does 1:1 IOVA->guest mapping 
on x86 (and some/most other architectures) but it is not for when guests 
get hardware-assisted vIOMMU support. Thanks,

> Both must agree on the IOVA to physical mapping otherwise the HW
> rejects it. Meaning the IOMMU configuration must perfectly match the

---

## [73] Alexey Kardashevskiy — 2024-09-02
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

On 30/8/24 17:02, Xu Yilun wrote:
> On Fri, Aug 30, 2024 at 02:00:30PM +1000, Alexey Kardashevskiy wrote:
>>

Yeah you're right.

>> guest BDFns (which have no meaning for VFIO in the host kernel).
> 

It needs to be the same id for "bind" operation (bind a TDI to a VM, the 
op performed by QEMU) and GUEST_REQUEST (VMGEXIT from the VM so the id 
comes from the guest). The host kernel is not going to parse it but just 
pass to the firmware so I guess it can be just an u32.


>>> The TDI bind
>>> means TDI would be transitioned to CONFIG_LOCKED state, and a bunch of

Sounds reasonable, my test device just does not do this so I have not 
poked at the error handling much :) Thanks,


> Thanks,
> Yilun

---

## [74] Alexey Kardashevskiy — 2024-09-02
*Subject: Re: [RFC PATCH 01/21] tsm-report: Rename module to reflect what it
 does*

On 30/8/24 10:13, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> And release the name for TSM to be used for TDISP-associated code.

I am happy to use what you have in your queue and drop mine. I also 
suspect that my TSM will be no more soon, DEV_* bits will go to ide.ko 
and TDI_* will go to a new tdisp.ko and we won't have a tsm.ko vs 
tsm-report.ko problem after all. Thanks,

---

## [75] Alexey Kardashevskiy — 2024-09-02
*Subject: Re: [RFC PATCH 13/21] KVM: X86: Handle private MMIO as shared*

On 31/8/24 02:57, Xu Yilun wrote:
> On Fri, Aug 23, 2024 at 11:21:27PM +1000, Alexey Kardashevskiy wrote:
>> Currently private MMIO nested page faults are not expected so when such

There is no other translation table on AMD though, the same NPT. The 
security is enforced by the RMP table. A device says "bar#x is private" 
so the host + firmware ensure the each corresponding RMP entry is 
"assigned" + "validated" and has a correct IDE stream ID and ASID, and 
the VM's kernel maps it with the Cbit set.

>  From HW perspective, private MMIO is not intended to be accessed by
> host, but the consequence may varies. According to TDISP spec 11.2,

afair I get an non-fatal RMP fault so the device does not even notice.

> On SW side, my concern is how to deal with mmu_notifier. In theory, if
> we get pfn from hva we should follow the userspace mapping change. But

> Another concern may be specific for TDX TEE-IO. Allowing both userspace
> mapping and SEPT mapping may be safe for private MMIO, but on

I am missing lots of context here. When you are starting a guest with a 
passed through device, until the TDISP machinery transitions the TDI 
into RUN, this TDI's MMIO is shared and mapped everywhere. And after 
transitioning to RUN you move mappings from EPT to SEPT?

> So personally I prefer no host mapping for private MMIO.

Nah, cannot skip this step on AMD. Thanks,


> 
> Thanks,

---

## [76] Aneesh Kumar K.V — 2024-09-02
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

...

> +static int tsm_dev_connect(struct tsm_dev *tdev, void *private_data, unsigned int val)
> +{

I was expecting the DEV_CONNECT to happen in tsm_dev_init in
tsm_alloc_device(). Can you describe how the sysfs file is going to be
used? I didn't find details regarding that in the cover letter 
workflow section. 

-aneesh

---

## [77] Alexey Kardashevskiy — 2024-09-02
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On 2/9/24 16:50, Aneesh Kumar K.V wrote:
> 
> ...

Until I figure out the cooperation with the host-based CMA from Lukas, I 
do not automatically enable IDE. Instead, the operator needs to enable 
IDE manually:

sudo bash -c 'echo 2 > /sys/bus/pci/devices/0000:e1:00.0/tsm_dev_connect'

where e1:00.0 is physical function 0 of the device; or "echo 0" to 
disable the IDE encryption. Why "2" is different from "1" - this is a 
leftover from debugging. Thanks,


> 
> -aneesh

---

## [78] Alexey Kardashevskiy — 2024-09-02
*Subject: Re: [RFC PATCH 20/21] pci: Allow encrypted MMIO mapping via sysfs*

On 24/8/24 08:37, Bjorn Helgaas wrote:
> On Fri, Aug 23, 2024 at 11:21:34PM +1000, Alexey Kardashevskiy wrote:
>> Add another resource#d_enc to allow mapping MMIO as

https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=f8f6ae5d077a9bdaf5cbf2ac960a5d1a04b47482 
added this.

"IO devices do not understand encryption, so this memory must always be 
decrypted" it says.

But devices do understand encryption so forcing decryption is not 
wanted. What additional context is missing here, that "shared" means 
"non-encrypted"? Thanks,



> 
>> +	 */

---

## [79] Jason Gunthorpe — 2024-09-02
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Mon, Sep 02, 2024 at 11:09:49AM +1000, Alexey Kardashevskiy wrote:
> On 30/8/24 22:35, Jason Gunthorpe wrote:
> > On Fri, Aug 30, 2024 at 01:47:40PM +1000, Alexey Kardashevskiy wrote:

Yes, you are forced into a nesting IOMMU architecture with CC guests.

Jason

---

## [80] Alexey Kardashevskiy — 2024-09-03
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On 3/9/24 09:52, Jason Gunthorpe wrote:
> On Mon, Sep 02, 2024 at 11:09:49AM +1000, Alexey Kardashevskiy wrote:
>> On 30/8/24 22:35, Jason Gunthorpe wrote:

Up to two I/O page tables and the RMP table allow both 1:1 and vIOMMU, 
what am I forced into, and by what? Thanks,


> 
> Jason

---

## [81] Jason Gunthorpe — 2024-09-02
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Tue, Sep 03, 2024 at 10:03:53AM +1000, Alexey Kardashevskiy wrote:
> 
> 

A key point of CC security is that the hypervisor cannot control the
IOVA translation.

AMD is securing non-viommu by using the RMP to limit the IOVA
translation to 1:1

But, viommu models require a secured non 1:1 mapping.

How do you intend to secure this other than using actual iommu
nesting? Presumably relying on the PSP to program the secure DTE's
GCR3 pointer.

Jason

---

## [82] Xu Yilun — 2024-09-03
*Subject: Re: [RFC PATCH 13/21] KVM: X86: Handle private MMIO as shared*

On Mon, Sep 02, 2024 at 12:22:56PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Sorry for not being clear, when I say "host mapping" I mean host
userspace mapping (host CR3 mapping). By using guest_memfd, there is no
host CR3 mapping for private memory. I'm wondering if we could keep host
CR3 mapping for private MMIO.

> security is enforced by the RMP table. A device says "bar#x is private" so
> the host + firmware ensure the each corresponding RMP entry is "assigned" +

Yes, that's the situation nowadays. I think if we need to eliminate
host CR3 mapping for private MMIO, a simple way is we don't allow host
CR3 mapping at the first place, even for shared pass through. It is
doable cause:

 1. IIUC, host CR3 mapping for assigned MMIO is only used for pfn
    finding, i.e. host doesn't really (or shouldn't?) access them.
 2. The hint from guest_memfd shows KVM doesn't have to rely on host
    CR3 mapping to find pfn.

> transitioning to RUN you move mappings from EPT to SEPT?

Mostly correct, TDX move mapping from EPT to SEPT after LOCKED and
right before RUN.

> 
> > So personally I prefer no host mapping for private MMIO.

Not sure if we are on the same page. I assume from HW perspective, host
CR3 mapping is not necessary for NPT/RMP build?

Thanks,
Yilun

> 
>

---

## [83] Sean Christopherson — 2024-09-03
*Subject: Re: [RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO*

On Fri, Aug 23, 2024, Alexey Kardashevskiy wrote:
> Hi everyone,
> 

1. Use scripts/get_maintainer.pl
2. Fix your MUA to wrap closer to 80 chars
3. Explain the core design, e.g. roles and responsibilities, coordination between
   KVM, VFIO/IOMMUFD, userspace, etc.

---

## [84] Dan Williams — 2024-09-03
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

Jason Gunthorpe wrote:
> On Fri, Aug 30, 2024 at 01:20:12PM +0800, Xu Yilun wrote:
> 

Yes. This matches the line of though I had for the PCI TSM core
interface. It allows establishing the connection to the device's
security manager and facilitates linking that to a KVM context. So part
of the uAPI is charged with managing device-security independent of a
VM, and binding a vPCI device involves a rendezvous of the
secure-world IOMMU setup with secure-world PCI via IOMMU and PCI-TSM
coordination.

---

## [85] Dan Williams — 2024-09-03
*Subject: Re: [RFC PATCH 06/21] crypto: ccp: Enable SEV-TIO feature in the PSP
 when supported*

Alexey Kardashevskiy wrote:
> The PSP advertises the SEV-TIO support via the FEATURE_INFO command
> support of which is advertised via SNP_PLATFORM_STATUS.

Taking a peek to familiarize myself with that is required for TIO
enabling in the PSP driver...

> 
> diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h

Why use CPU register names in C structures? I would hope the spec
renames these parameters to something meaninful?

> +
>  /**

Would be nice to have direct pointer to the spec and spec chapter
documented for these command structure fields.

>  struct sev_data_snp_init_ex {
>  	u32 init_rmp:1;
[..]
> diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
> index f6eafde584d9..a49fe54b8dd8 100644

Jonathan already mentioned this, but "goto cleanup" is so 2022.

> +	}
> +

Why not make this bool...

> +{
> +	struct sev_user_data_snp_status status = { 0 };

...since the caller does not care?

> +		return false;
> +

Where does this get saved for follow-on code to consume that TIO is
active?

---

## [86] Bjorn Helgaas — 2024-09-03
*Subject: Re: [RFC PATCH 20/21] pci: Allow encrypted MMIO mapping via sysfs*

On Mon, Sep 02, 2024 at 06:22:00PM +1000, Alexey Kardashevskiy wrote:
> On 24/8/24 08:37, Bjorn Helgaas wrote:
> > On Fri, Aug 23, 2024 at 11:21:34PM +1000, Alexey Kardashevskiy wrote:

> > > @@ -46,6 +46,15 @@ int pci_mmap_resource_range(struct pci_dev *pdev, int bar,
> > >   	vma->vm_ops = &pci_phys_vm_ops;

Thanks for the pointer.  Given that hint, the pgprot_decrypted()
inside io_remap_pfn_range() is ... at least *there*, if not obvious.
io_remap_pfn_range() probably could benefit from a simple comment to
highlight that.

> But devices do understand encryption so forcing decryption is not wanted.
> What additional context is missing here, that "shared" means

If "shared" means "non-encrypted", that would be useful.  That wasn't
obvious to me.

IIUC, in the "enc" case, you *want* the mapping to remain encrypted?
In that case, it would be helpful to say something like
"io_remap_pfn_range() always produces decrypted mappings, so use
remap_pfn_range() directly to avoid the decryption".

Renaming "enc" to "encrypted" would also be a nice hint.

> > > +	 */
> > > +	if (enc)

---

## [87] Dan Williams — 2024-09-03
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

Alexey Kardashevskiy wrote:
> The module responsibilities are:
> 1. detect TEE support in a device and create nodes in the device's sysfs

I had been holding out hope that when I got this patch the changelog
would give some justification for what folks had been whispering to me
in recent days: "hey Dan, looks like Alexey is completely ignoring the
PCI/TSM approach?".

Bjorn acked that approach here:

http://lore.kernel.org/20240419220729.GA307280@bhelgaas

It is in need of a refresh, preview here:

https://git.kernel.org/pub/scm/linux/kernel/git/djbw/linux.git/commit/?id=5807465b92ac

At best, I am disappointed that this RFC ignored it. More comments
below, but please do clarify if we are working together on a Bjorn-acked
direction, or not.

> Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
> ---

The expectation is that something like drivers/virt/coco/tsm.c would be
the class driver for cross-vendor generic TSM uAPI. The PCI specific
bits go in drivers/pci/tsm.c.

>  obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
>  obj-$(CONFIG_SEV_GUEST)		+= sev-guest/

No. The only known device model for TDIs is PCI devices, i.e. TDISP is a
PCI protocol. Even SPDM which is cross device-type generic did not touch
'struct device'.

>  	struct device_physical_location *physical_location;
>  

Hard to judge the suitability of these without documentation. Skeptical
that these TDISP evidence blobs need to have a lifetime distinct from
the device's TSM context.

> +};
> +

Linux typically avoids C-bitfields in hardware interfaces in favor of
bitfield.h macros.

> +		};
> +	};

Does this need to be "packed"? Looks naturally aligned to pahole.

> +
> +/*

This one might need to be packed.

> +
> +struct dmtf_measurement_block_device_mode {

These last 2 struct do not seem to need it.

> +
> +/*

Same C-bitfield comment, as before, and what about big endian hosts?

> +	};
> +	u16 reserved2;

Another kref that begs the question why would a tsm_dev need its own
lifetime? This also goes back to the organization in the PCI/TSM
proposal that all TSM objects are at max bound to the lifetime of
whatever is shorter, the registration of the low-level TSM driver or the
PCI device itself.

> +	const struct attribute_group *ag;

PCI device attribute groups are already conveyed in a well known
(lifetime and user visibility) manner. What is motivating this
"re-imagining"?

> +	struct pci_dev *pdev; /* Physical PCI function #0 */
> +	struct tsm_spdm spdm;

Is an spdm lock sufficient? I expect the device needs to serialize all
TSM communications, not just spdm? Documentation of the locking would
help.

> +
> +	u8 tc_mask;

Compare these to the blobs that Lukas that maintains for CMA. To my
knoweldge no new kref lifetime rules independent of the authenticated
lifetime.

> +
> +	void *data; /* Platform specific data */

The lack of documentation for these ops makes review difficult.

> +	/* HV hooks */
> +	int (*dev_connect)(struct tsm_dev *tdev, void *private_data);

Lets not abandon type-safety this early. Is it really the case that all
of these helpers need anonymous globs passed to them?

> +	int (*dev_reclaim)(struct tsm_dev *tdev, void *private_data);
> +	int (*dev_status)(struct tsm_dev *tdev, void *private_data, struct tsm_dev_status *s);

IDE Key Refresh seems an enhancement worth breaking out of the base
enabling.

> +	int (*tdi_bind)(struct tsm_tdi *tdi, u32 bdfn, u64 vmid, u32 asid, void *private_data);
> +	int (*tdi_reclaim)(struct tsm_tdi *tdi, void *private_data);

Lets not mix HV and VM hooks in the same ops without good reason.

> +};
> +

No. Lets build proper uAPI for these. These TSM global parameters are
what I envisioned hanging off of the global TSM class device.

[..]
> +/*
> + * Enables IDE between the RC and the device.

It would help to know how in depth to review the pieces if there were
more pointers of "this is serious proposal", and "this is a sketch".

> + */
> +static int tsm_set_sel_ide(struct tsm_dev *tdev)

I find the "sel" abbreviation too short to be useful. Perhaps lets just
call "Selective IDE" "ide" and "Link IDE" "link_ide". Since "Selective"
is the common case.

> +{
> +	struct pci_dev *rootport;

Does this assume no intervening IDE switches?

> +	for (i = 0; i < ARRAY_SIZE(tdev->selective_ide); ++i) {
> +		if (!tdev->selective_ide[i].enable)

Why so chatty? Just make if pci_dbg() and be done.

> +		}
> +		WARN_ON_ONCE(tdev->selective_ide[i].enabled);

Crash the kernel if IDE is already enabled??

> +
> +		ret = pci_ide_set_sel_rid_assoc(tdev->pdev, i, true, 0, 0, 0xFFFF);

This feels kludgy. IDE is a fundamental mechanism of a PCI device why
would a PCI core helper not know how to extract the settings from a
pdev?

Something like:

pci_ide_setup_stream(pdev, i)

> +		if (ret) {
> +			pci_warn(tdev->pdev,

Perhaps:

pci_ide_host_setup_stream(pdev, i)

...I expect the helper should be able to figure out the rootport and RID
association.

> +				      tdev->selective_ide[i].id,
> +				      tdev->selective_ide[i].enable,

These calls are unreadable, how about:

pci_ide_host_destroy_stream(pdev, i)
pci_ide_destroy_stream(pdev, i)


> +static int tsm_dev_connect(struct tsm_dev *tdev, void *private_data, unsigned int val)
> +{

How does a device get this far into the flow with a TSM that does not
define the "connect" verb?

> +
> +	tdev->ide_pre = val == 2;

Similar comment about how this could happen and why crashing the kernel
is ok.

> +
> +	/* Do not disconnect with active TDIs */

I would expect that removing things out of order causes violence, not
blocking it.

For example you can remove disk drivers while filesystems are still
mounted. What is the administrator's recourse if they *do* want to
shutdown the TSM layer all at once?

> +	}
> +

What is the "reclaim" verb? Is this just a destructor? Does "disconnect"
not sufficiently clean up the device context?

> +
> +		ret = spdm_forward(&tdev->spdm, ret);

This is asking for better defined semantics.

> +}
> +

Why is refresh not "connect"? I.e. connecting an already connected
device refreshes the connection.

> +
> +		ret = spdm_forward(&tdev->spdm, ret);

What is involved in tdi "reclaim" separately from "unbind"?
"dev_reclaim" and "tdi_reclaim" seem less precise than "disconnect" and
"unbind".

> +
> +		ret = spdm_forward(&tdi->tdev->spdm, ret);

No. TDISP is a fundamental re-imagining of the PCI device security
model. It deserves first class support in the PCI core, not bolted on
support via bus notifiers.

[..]

I hesitate to keep commenting because this is so far off of the lifetime
and code organization expectations I thought we were negotiating with
the PCI/TSM series. So I will stop here for now.

---

## [88] Jason Gunthorpe — 2024-09-03
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Tue, Sep 03, 2024 at 01:34:29PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> > On Fri, Aug 30, 2024 at 01:20:12PM +0800, Xu Yilun wrote:

Okay, but I don't think you should ever be binding any PCI stuff to
KVM without involving VFIO in some way.

VFIO is the security proof that userspace is even permitted to touch
that PCI Device at all.

> It allows establishing the connection to the device's
> security manager and facilitates linking that to a KVM context. So part

Yes, the PCI core should have stuff for managing device-secuirty for
any bound driver, especially assuming an operational standard kernel
driver only.

> and binding a vPCI device involves a rendezvous of the secure-world
> IOMMU setup with secure-world PCI via IOMMU and PCI-TSM

And this stuff needs to start with VFIO and we can figure out of it is
in the iommufd subcomponent or not.

I'd really like to see a clearly written proposal for what the uAPI
would look like for vPCI function lifecycle and binding that at least
one of the platforms is happy with :)

It would be a good starting point for other platforms to pick at. Try
iommufd first (I'm guessing this is correct) and if it doesn't work
explain why.

Jason

---

## [89] Dan Williams — 2024-09-03
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

Jason Gunthorpe wrote:
> On Tue, Sep 03, 2024 at 01:34:29PM -0700, Dan Williams wrote:
> > Jason Gunthorpe wrote:

Right, I think VFIO grows a uAPI to make a vPCI device "bind capable"
which ties together the PCI/TSM security context, the assignable device
context and the KVM context.

> > It allows establishing the connection to the device's
> > security manager and facilitates linking that to a KVM context. So part

Yes, makes sense. Will take a look at that also to prevent more
disconnects on what this PCI device-security community is actually
building.

---

## [90] Alexey Kardashevskiy — 2024-09-04
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

On 4/9/24 09:51, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> The module responsibilities are:

Together.

My problem with that patchset is that it only does connect/disconnect 
and no TDISP business (and I need both for my exercise) and I was hoping 
to see some TDISP-aware git tree but this has not happened yet so I 
postponed rebasing onto it, due to the lack of time and also apparent 
difference between yours and mine TSMs (and I had mine working before I 
saw yours and focused on making things work for the starter). Sorry, I 
should have spoken louder. Or listen better to that whispering. Or 
rebase earlier.


> 
>> Signed-off-by: Alexey Kardashevskiy <aik@amd.com>

TDISP is PCI but DMA is not. This is for:
[RFC PATCH 19/21] sev-guest: Stop changing encrypted page state for 
TDISP devices

DMA layer deals with struct device and tries hard to avoid indirect _ops 
calls so I was looking for a place for "tdi_enabled" (a bad name, 
perhaps, may be call it "dma_encrypted", a few lines below). So I keep 
the flag and the pointer together for the RFC. I am hoping for a better 
solution for 19/21, then I am absolutely moving tdi* to pci_dev (well, 
drop these and just use yours).


>>   	struct device_physical_location *physical_location;
>>   

You are right.

>> +};
>> +

"__packed" is also a way to say it is a binary interface, I want to be 
precise about this.


>> +
>> +/*

Right, I'll get rid of c-bitfields in the common parts.

Although I am curious what big-endian platform is going to actually 
support this.


>> +	};
>> +	u16 reserved2;


That proposal deals with PFs for now and skips TDIs. Since TDI needs its 
place in pci_dev too, and I wanted to add the bare minimum to struct 
device or pci_dev, I only add TDIs and each of them references a DEV. 
Enough to get me going.


>> +	const struct attribute_group *ag;
> 

What other communication do you mean here?


>> +
>> +	u8 tc_mask;

Largely the latter, remember to keep appreciating the "release early" 
aspect of it :)

It is a sketch which has been tested on the hardware with both KVM and 
SNP VM which (I thought) has some value if posted before the LPC. I 
should have made it clearer though.


>> + */
>> +static int tsm_set_sel_ide(struct tsm_dev *tdev)


It is unclear to me how we go about what stream(s) need(s) enabling and 
what flags to set. Who decides - a driver? a daemon/user?

> 
>> +		if (ret) {

Where will the helper get the properties from?


>> +				      tdev->selective_ide[i].id,
>> +				      tdev->selective_ide[i].enable,

In this exercise, connect/reclaim are triggered via sysfs so this can 
happen in my practice.

And it is WARN_ON, not BUG_ON, is it still called "crashing" (vs. 
"panic", I never closely thought about it)?


> 
>> +

"rmmod tsm"

>> +	}
>> +
 >
>> +
>> +		ret = spdm_forward(&tdev->spdm, ret);

Really not sure about that. Either way I am ditching it for now.

>> +
>> +		ret = spdm_forward(&tdev->spdm, ret);

The firmware operates at the finer granularity so there are 
create+connect+disconnect+reclaim (for DEV and TDI). My verbs dictionary 
evolved from having all of them in the tsm_ops to this subset which 
tells the state the verb leaves the device at. This needs correction, yes.


>> +
>> +		ret = spdm_forward(&tdi->tdev->spdm, ret);

This one is about sequencing. For example, writing a zero to BME breaks 
a TDI after it moved to CONFIG_LOCKED. So, we either:
1) prevent zeroing BME or
2) delay this "validation" step (which also needs a better name).

If 1), then I can call "validate" from the PCI core before the driver's 
probe.
If 2), it is either a driver modification to call "validate" explicitly 
or have a notifier like this. Or guest's sysfs - as a VM might want to 
boot with a "shared" device, get to the userspace where some daemon 
inspects the certificates/etc and "validates" the device only if it is 
happy with the result. There may be even some vendor-specific device 
configuration happening before the validation step.

> 
> [..]

Good call, sorry for the mess. Thanks for the review!


ps: I'll just fix the things I did not comment on but I'm not ignoring them.

---

## [91] Dan Williams — 2024-09-04
*Subject: Re: [RFC PATCH 07/21] pci/tdisp: Introduce tsm module*

Alexey Kardashevskiy wrote:
> 
> 

Ok, this makes sense. This is definitely changelog material to clarify
assumptions, tradeoffs, and direction. The fact that the changelog said
nothing about those was, at a minimum, cause for concern.

[..]
> >> @@ -801,6 +802,7 @@ struct device {
> >>   	void	(*release)(struct device *dev);

The name and the fact that it exposes all of the TSM interfaces to the
driver core made it unclear if this oversharing was on purpose, or for
convenience / expediency?

I agree that 'struct device' should carry DMA mapping details, but the
full TDI context is so much more than that which makes it difficult to
understand the organizing principle of this data sharing.

> the flag and the pointer together for the RFC. I am hoping for a better 
> solution for 19/21, then I am absolutely moving tdi* to pci_dev (well, 

Ok, so what patches are in the category of "temporary hacks to get
something going and a plan to replace them", and which are "firm
proposals looking for review feedback"?

[..]
> >> +/**
> >> + * struct tdisp_interface_id - TDISP INTERFACE_ID Definition

It's also a way to tell the compiler to turn off useful optimizations.

Don't these also need to be __le32 and __le16 for the multi-byte fields?

[..]
> > Same C-bitfield comment, as before, and what about big endian hosts?
> 

The PCI DOE and CMA code is cross-CPU generic with endian annotations
where needed. Why would PCI TSM code get away with kicking that analysis
down the road?

[..]
> >> +/* Physical device descriptor responsible for IDE/TDISP setup */
> >> +struct tsm_dev {

Fine for an RFC, but again please be upfront about what is firmer for
deeper scrutiny and what is softer to get the RFC standing.

> >> +	const struct attribute_group *ag;
> > 

For example, a lock protecting entry into tsm_ops->connect(...), if that
operation is locked does there need to be a lower level spdm locking
context?

[..]
> >> +/*
> >> + * Enables IDE between the RC and the device.

It is definitely useful for getting the conversation started, but maybe
we need a SubmittingPatches style document that clarifies that RFC's
need to be explicit about if and where reviewers spend their time.

[..]
> > This feels kludgy. IDE is a fundamental mechanism of a PCI device why
> > would a PCI core helper not know how to extract the settings from a

That is a good topic for the design document that Jason wanted. I had
been expecting that since stream IDs are a limited resource the kernel
needs to depend on userspace to handle allocation conflicts. Most of the
other settings would seem to be PCI core defaults unless and until
someone can point to a use case for a driver or userspace to have a
different opinion about those settings.

> >> +		if (ret) {
> >> +			pci_warn(tdev->pdev,

I expect it can retrieve it out of @pdev since the IDE settings belong
in 'struct pci_dev'.

[..]
> >> +static int tsm_dev_reclaim(struct tsm_dev *tdev, void *private_data)
> >> +{

You will see folks like Greg raise the concern that many users run with
"panic_on_warn" enabled. I expect a confidential VM is well advised to
enable that.

If it is a "can't ever happen outside of a kernel developer mistake"
then maybe WARN_ON() is ok, and you will see folks like Christoph assert
that WARN_ON() is good for that, but it should be reserved for cases
where rebooting might be a good idea if it fires.

> >> +
> >> +	/* Do not disconnect with active TDIs */

Is tsm_dev_reclaim() triggered by "rmmod tsm"? The concern is how to
reclaim when tsm_dev_reclaim() is sometimes returning EBUSY. Similar to
how the driver core enforces that driver unbind must succeed so should
TSM shutdown.

Also, the proposal Bjorn acked, because it comports with PCI sysfs
lifetime and visibility expectations, is that the TSM core is part of
the PCI core, just like DOE and CMA. The proposed way to shutdown TSM
operations is to unbind the low level TSM driver (TIO, TDX-Connect,
etc...) and that will forcefully destruct all TDI contexts with no
dangling -EBUSY cases.

Maybe tsm_dev_reclaim() is not triggered by TSM shutdown, but TSM
shutdown, like 'struct device_driver'.remove() should return 'void'.
Note, I know that 'struct device_driver' is not quite there yet on
->remove() returning 'void' instead of 'int', but that is the direction.

[..]
> > Why is refresh not "connect"? I.e. connecting an already connected
> > device refreshes the connection.

Yeah, lets aggressively defer incremental features.

> >> +		ret = spdm_forward(&tdev->spdm, ret);
> >> +		if (ret < 0)

I like the simplicity of the TIO verbs, but that does not preclude the
Linux verbs from having even coarser semantics.

[..]
> >> +/* In case BUS_NOTIFY_PCI_BUS_MASTER is no good, a driver can call pci_dev_tdi_validate() */
> > 

Right, the guest might need to operate the device in shared mode to get
it ready for validation. At that point locking and validating the device
needs to be triggered by userspace talking to the PCI core before
reloading the driver to operate the device in private mode. That
conversion is probably best modeled as a hotplug event to leave the
shared world and enter the secured world.

That likely means that the userspace operation to transtion the device
to LOCKED also needs to take care of enabling BME and MSE independent of
any driver just based on the interface report. Then, loading the driver
can take the device from LOCKED to RUN when ready.

Yes, that implies an enlightened driver, for simplicity. We could later 
think about auto-validating devices by pre-loading golden measurements
into the kernel, but I expect the common case is that userspace needs to
do a bunch of work with the device-evidence and the verifier to get
itself comfortable with allowing the device to transition to the RUN
state.

> > I hesitate to keep commenting because this is so far off of the lifetime
> > and code organization expectations I thought we were negotiating with

No harm done. The code is useful and the disconnect on the communication
/ documentation is now understood.

> ps: I'll just fix the things I did not comment on but I'm not ignoring them.

Sounds good.

---

## [92] Alexey Kardashevskiy — 2024-09-05
*Subject: Re: [RFC PATCH 06/21] crypto: ccp: Enable SEV-TIO feature in the PSP
 when supported*

On 4/9/24 07:27, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> The PSP advertises the SEV-TIO support via the FEATURE_INFO command

This mimics the CPUID instruction and (my guess) x86 people are used to 
"CPUID's ECX" == "Subfunction index". The spec (the one I mention below) 
calls it precisely "ECX_IN".


>> +
>>   /**

For every command? Seems overkill. Any good example?

Although the file could have mentioned in the header that SNP_xxx are 
from "SEV Secure Nested Paging Firmware ABI Specification" which google 
easily finds, and search on that pdf for "SNP_INIT_EX" finds the 
structure layout. Using the exact chapter numbers/titles means they 
cannot change, or someone has to track the changes.

> 
>>   struct sev_data_snp_init_ex {

This requires DEFINE_FREE() which yet another place to look at. When I 
Then, no_free_ptr() just hurts to read (cold breath of c++). It is not 
needed here but unavoidably will be in other places when I start using 
__free(kfree). But alright, I'll switch.

> 
>> +	}


sev_tio_present() does not but other users of snp_get_feature_info() 
(one is coming sooner that TIO) might, WIP.


>> +		return false;
>> +

Oh. It is not saved, whether TIO is actually active is determined by the 
result of calling PSP's TIO_STATUS (which I should skip if tio_en == 
false in the first place). Thanks,

---

## [93] Tian, Kevin — 2024-09-05
*Subject: RE: [RFC PATCH 00/21] Secure VFIO, TDISP, SEV TIO*

> From: Alexey Kardashevskiy <aik@amd.com>
> Sent: Thursday, August 29, 2024 10:14 PM

Assume there will be a new hwpt type which hints for special DTE
setting at attach time and connects to a guest memfd. It'd make
sense to defer mapping guest memory to a point after "SNP
LAUNCH UPDATE" is completed for devices attached to such hwpt,
as long as we document such restriction clearly for that new type. 😊

---

## [94] Tian, Kevin — 2024-09-05
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Williams, Dan J <dan.j.williams@intel.com>
> Sent: Wednesday, September 4, 2024 9:00 AM

Could you elaborate why the new uAPI is for making vPCI "bind capable"
instead of doing the actual binding to KVM?

---

## [95] Jason Gunthorpe — 2024-09-05
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Tue, Sep 03, 2024 at 05:59:38PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> > On Tue, Sep 03, 2024 at 01:34:29PM -0700, Dan Williams wrote:

I think it is more than just "bind capable", I understand various
situations are going to require information passed from the VMM to the
secure world to specify details about what vPCI function will appear
in the VM.

AMD probably needs very little here, but others will need more.

> > It would be a good starting point for other platforms to pick at. Try
> > iommufd first (I'm guessing this is correct) and if it doesn't work

We are already adding a VIOMMU object and that is going to be the
linkage to the KVM side

So we could have new actions:
 - Create a CC VIOMMU with XYZ parameters
 - Create a CC vPCI function on the vIOMMU with XYZ parameters
 - Query stuff?
 - ???
 - Destroy a vPCI function

Jason

---

## [96] Jason Gunthorpe — 2024-09-05
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Thu, Sep 05, 2024 at 08:29:16AM +0000, Tian, Kevin wrote:

> Could you elaborate why the new uAPI is for making vPCI "bind capable"
> instead of doing the actual binding to KVM? 

I don't see why you'd do any of this in KVM, I mean you could, but you
also don't have to and KVM people don't really know about all the VFIO
parts anyhow.

It is like a bunch of our other viommu stuff, KVM has to share some of
the HW and interfaces with the iommu driver. In this case it would be
the secure VM context and the handles to talk to the trusted world

Jason

---

## [97] Tian, Kevin — 2024-09-05
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Jason Gunthorpe <jgg@nvidia.com>
> Sent: Thursday, September 5, 2024 8:02 PM

that's not my point. I was asking why this VFIO uAPI is not for linking/
binding a vPCI device to KVM (not do it in KVM) while making it just 'bind
capable'. 😊

---

## [98] Tian, Kevin — 2024-09-05
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Jason Gunthorpe <jgg@nvidia.com>
> Sent: Thursday, September 5, 2024 8:01 PM

I'll look at the vIOMMU series soon. Just double confirm here.

the so-called vIOMMU object here is the uAPI between iommufd
and userspace. Not exactly suggesting a vIOMMU visible to guest.
otherwise this solution will be tied to implementations supporting
trusted vIOMMU.

Then you expect to build CC/vPCI stuff around the vIOMMU
object given it already connects to KVM?

---

## [99] Jason Gunthorpe — 2024-09-05
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Thu, Sep 05, 2024 at 12:17:14PM +0000, Tian, Kevin wrote:
> > From: Jason Gunthorpe <jgg@nvidia.com>
> > Sent: Thursday, September 5, 2024 8:01 PM

Right, the viommu object today just wraps elements of HW that are
connected to the VM in some way. It is sort of a security container.

If the VMM goes on to expose a vIOMMU to the guest or not should be
orthogonal.

I expect people will explicitly request a secure vIOMMU if they intend
to expose the vIOMMU to the CC VM. This can trigger any actions in the
trusted world that are required to support a secure vIOMMU.

For instance any secure vIOMMU will require some way for the guest to
issue secure invalidations, and that will require some level of
trusted world involvement. At the minimum the trusted world has to
attest the validity of the vIOMMU to the guest.

> Then you expect to build CC/vPCI stuff around the vIOMMU
> object given it already connects to KVM?

Yes, it is my thought

We alreay have a binding of devices to the viommu, increasing that to
also include creating vPCI objects in the trusted world is a small
step.

Jason

---

## [100] Dan Williams — 2024-09-05
*Subject: Re: [RFC PATCH 06/21] crypto: ccp: Enable SEV-TIO feature in the PSP
 when supported*

Alexey Kardashevskiy wrote:
> 
> 
[..]
> > Why use CPU register names in C structures? I would hope the spec
> > renames these parameters to something meaninful?

Oh, I never would have guessed that "snp feature info" mimicked CPUID,
but then again, no one has ever accused me of being an "x86 people".

> >>   /**
> >>    * struct sev_data_snp_launch_start - SNP_LAUNCH_START command params

No need to go overboard, but you can grep for:
    "PCIe\ r\[0-9\]"
...or:
    "CXL\ \[12\]" 

...for some examples. Yes, these references can bit rot, but that can
also be good information "the last time this definition was touched was
in vN and vN+1 introduced some changes."

[..]
> >> +static int snp_get_feature_info(struct sev_device *sev, u32 ecx, struct sev_snp_feature_info *fi)
> > 

...not a huge deal, but it definitely looked odd to see so much care to
return distinct error codes only to throw away the distinction.

---

## [101] Dan Williams — 2024-09-05
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

Jason Gunthorpe wrote:
> On Thu, Sep 05, 2024 at 12:17:14PM +0000, Tian, Kevin wrote:
> > > From: Jason Gunthorpe <jgg@nvidia.com>

Sounds reasonable to me.

To answer Kevin's question about what "bind capable" means I need to
clarify this oversubscribed "bind" term means. "Bind" in the TDISP sense
is transitioning the device to the LOCKED state so that its
configuration is static and ready for the VM to run attestation without
worrying about TOCTOU races.

The VMM is not in a good position to know when the assigned device can
be locked. There are updates, configuration changes, and reset/recovery
scenarios the VM may want to perform before transitioning the device to
the LOCKED state. So, the "bind capable" concept is: pre-condition VFIO
with the context that "this vPCI device is known to VFIO as a device
that can attach to the secure world, all the linkage between VFIO and
the secure world is prepared for a VM to trigger entry into the LOCKED
state, and later the RUN state".

As mentioned in another thread this entry into the LOCKED state is
likely nearly as violent as hotplug event since the DMA layer currently
has no concept of a device having a foot in the secure world and the
shared world at the same time.

---

## [102] Jason Gunthorpe — 2024-09-05
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Thu, Sep 05, 2024 at 01:53:27PM -0700, Dan Williams wrote:

> As mentioned in another thread this entry into the LOCKED state is
> likely nearly as violent as hotplug event since the DMA layer currently

There is also something of a complicated situation where the VM also
must validate that it has received the complete and correct device
before it can lock it. Ie that the MMIO ranges belong to the device,
the DMA goes to the right place (the vRID:pRID is trusted), and so on.

Further, the vIOMMU, and it's parameters, in the VM must also be
validated and trusted before the VM can lock the device. The VM and
the trusted world must verify they have the exclusive control over the
translation.

This is where AMDs model of having the hypervisor control things get a
little bit confusing for me. I suppose there will be some way that the
confidential VM asks the trusted world to control the secure DTE such
that it can select between GCR3, BLOCKED and IDENTITY.

Regardless, I think everyone will need some metadata from the vIOMMU
world into the trusted world to do all of this.

Jason

---

## [103] Tian, Kevin — 2024-09-06
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Williams, Dan J <dan.j.williams@intel.com>
> Sent: Friday, September 6, 2024 4:53 AM

Okay this makes sense. So the point is that the TDI state machine is
fully managed by the TSM driver so here 'bind capable' is a necessary
preparation step for that state machine to enter the LOCKED state.

> 
> As mentioned in another thread this entry into the LOCKED state is

Is the DMA layer relevant in this context? Here we are talking about
VFIO/IOMMUFD which can be hinted by VMM for whatever side
effect caused by the entry into the LOCKED state...

---

## [104] Tian, Kevin — 2024-09-06
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Jason Gunthorpe <jgg@nvidia.com>
> Sent: Friday, September 6, 2024 7:07 AM

Looking at the TDISP spec it's the host to lock the device (as Dan
described the entry into the LOCKED state) while the VM is allowed
to put the device into the RUN state after validation.

I guess you actually meant the entry into RUN here? otherwise 
there might be some disconnect here.

> 
> This is where AMDs model of having the hypervisor control things get a

this matches what I read from the SEV-TIO spec.

> 
> Regardless, I think everyone will need some metadata from the vIOMMU

Agree.

---

## [105] Alexey Kardashevskiy — 2024-09-06
*Subject: Re: [RFC PATCH 13/21] KVM: X86: Handle private MMIO as shared*

On 3/9/24 15:13, Xu Yilun wrote:
> On Mon, Sep 02, 2024 at 12:22:56PM +1000, Alexey Kardashevskiy wrote:
>>
private" so
>> the host + firmware ensure the each corresponding RMP entry is "assigned" +
>> "validated" and has a correct IDE stream ID and ASID, and the VM's kernel

Well, the host userspace might also want to access MMIO via mmap'ed 
region if it is, say, DPDK.

>   2. The hint from guest_memfd shows KVM doesn't have to rely on host
>      CR3 mapping to find pfn.

True.

>> transitioning to RUN you move mappings from EPT to SEPT?
> 

With the above explanation, we are.

> I assume from HW perspective, host
> CR3 mapping is not necessary for NPT/RMP build?

Yeah, the hw does not require that afaik. But the existing code 
continues working for AMD, and I am guessing it is still true for your 
case too, right? Unless the host userspace tries accessing the private 
MMIO and some horrible stuff happens? Thanks,


> Thanks,
> Yilun

---

## [106] Jason Gunthorpe — 2024-09-06
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Fri, Sep 06, 2024 at 02:46:24AM +0000, Tian, Kevin wrote:
> > Further, the vIOMMU, and it's parameters, in the VM must also be
> > validated and trusted before the VM can lock the device. The VM and

Yeah

Jason

---

## [107] Xu Yilun — 2024-09-09
*Subject: Re: [RFC PATCH 13/21] KVM: X86: Handle private MMIO as shared*

On Fri, Sep 06, 2024 at 01:31:48PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Yes for DPDK. But I mean for virtualization cases, host doesn't access
assigned MMIO.

I'm not suggesting we remove the entire mmap functionality in VFIO, but
may have a user-optional no-mmap mode for private capable device.

> 
> >   2. The hint from guest_memfd shows KVM doesn't have to rely on host

It works for TDX with some minor changes similar as this patch does. But
still see some concerns on my side, E.g. mmu_notifier. Unlike SEV-SNP,
TDX firmware controls private MMIO accessing by building private S2 page
table. If I still follow the HVA based page fault routine, then I should
also follow the mmu_notifier, i.e. change private S2 mapping when HVA
mapping changes. But private MMIO accessing is part of the private dev
configuration and enforced (by firmware) not to be changed when TDI is
RUNning. My effort for this issue is that, don't use HVA based page
fault routine, switch to do like guest_memfd does.

I see SEV-SNP prebuilds RMP to control private MMIO accessing, S2 page
table modification is allowed at anytime. mmu_notifier only makes
private access dis-functional. I assume that could also be nice to
avoid.

> right? Unless the host userspace tries accessing the private MMIO and some
> horrible stuff happens? Thanks,

The common part for all vendors is, the private device will be
disturbed and enter TDISP ERROR state. I'm not sure if this is OK or can
also be nice to avoid.

Thanks,
Yilun

---

## [108] Alexey Kardashevskiy — 2024-09-10
*Subject: Re: [RFC PATCH 13/21] KVM: X86: Handle private MMIO as shared*

On 9/9/24 20:07, Xu Yilun wrote:
> On Fri, Sep 06, 2024 at 01:31:48PM +1000, Alexey Kardashevskiy wrote:
>>
 >
>>
>>>    2. The hint from guest_memfd shows KVM doesn't have to rely on host

ah I see, thanks.

> I see SEV-SNP prebuilds RMP to control private MMIO accessing, S2 page
> table modification is allowed at anytime. mmu_notifier only makes

For this instance, on AMD, I expect an RMP fault and no device 
disturbance, no TDISP ERROR. Thanks,


> 
> Thanks,

---

## [109] Zhi Wang — 2024-09-13
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

On Fri, 23 Aug 2024 23:21:25 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> The SEV TIO spec defines a new TIO_GUEST_MESSAGE message to
> provide a secure communication channel between a SNP VM and

Out of curiosity, do we have to handle the TDI bind/unbind in the kernel
space? It seems we are get the relationship between modules more
complicated. What is the design concern that letting QEMU to handle the
TDI bind/unbind message, because QEMU can talk to VFIO/KVM and also TSM.

> Skip adjust_direct_map() in rmpupdate() for now as it fails on MMIO.
>

---

## [110] Dan Williams — 2024-09-13
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

Zhi Wang wrote:
> On Fri, 23 Aug 2024 23:21:25 +1000
> Alexey Kardashevskiy <aik@amd.com> wrote:

Hmm, the flow I have in mind is:

Guest GHCx(BIND) => KVM => TSM GHCx handler => VFIO state update + TSM low-level BIND

vs this: (if I undertand your question correctly?)

Guest GHCx(BIND) => KVM => TSM GHCx handler => QEMU => VFIO => TSM low-level BIND

Why exit to QEMU only to turn around and call back into the kernel? VFIO
should already have the context from establishing the vPCI device as
"bind-capable" at setup time.

Maybe I misunderstood your complication concern?

---

## [111] Tian, Kevin — 2024-09-14
*Subject: RE: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

> From: Dan Williams <dan.j.williams@intel.com>
> Sent: Saturday, September 14, 2024 6:09 AM

Reading this patch appears that it's implemented this way except QEMU
calls a KVM_DEV uAPI instead of going through VFIO (as Yilun suggested).

> 
> Why exit to QEMU only to turn around and call back into the kernel? VFIO

The general practice in VFIO is to design things around userspace driver
control over the device w/o assuming the existence of KVM. When VMM
comes to the picture the interaction with KVM is minimized unless
for functional or perf reasons.

e.g. KVM needs to know whether an assigned device allows non-coherent
DMA for proper cache control, or mdev/new vIOMMU object needs
a reference to struct kvm, etc. 

sometimes frequent trap-emulates is too costly then KVM/VFIO may
enable in-kernel acceleration to skip Qemu via eventfd, but in 
this case the slow-path via Qemu has been firstly implemented.

Ideally BIND/UNBIND is not a frequent operation, so falling back to
Qemu in a longer path is not a real problem. If no specific
functionality or security reason for doing it in-kernel, I'm inclined
to agree with Zhi here (though not about complexity).

---

## [112] Zhi Wang — 2024-09-14
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

On Sat, 14 Sep 2024 02:47:27 +0000
"Tian, Kevin" <kevin.tian@intel.com> wrote:

> > From: Dan Williams <dan.j.williams@intel.com>
> > Sent: Saturday, September 14, 2024 6:09 AM

Exactly what I was thinking. Folks had been spending quite some efforts
on keeping VFIO and KVM independent. The existing shortcut calling
between two modules is there because there is no other better way to do
it.

TSM BIND/UNBIND should not be a performance critical path. Thus falling
back to QEMU would be fine. Besides, not sure about others' opinion, I
don't think adding tsm_{bind, unbind} in kvm_x86_ops is a good idea.

If we have to stick to the current approach, I think we need more
justifications.

---

## [113] Zhi Wang — 2024-09-14
*Subject: Re: [RFC PATCH 17/21] coco/sev-guest: Implement the guest side of
 things*

On Fri, 23 Aug 2024 23:21:31 +1000
Alexey Kardashevskiy <aik@amd.com> wrote:

> Define tsm_ops for the guest and forward the ops calls to the HV via
> SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST.

It seems in both guest side (this patch) and host side
(PATCH 7 tsm_report_show()), if the SW wants to reach the latest TDI
report, they have to call get TDI status verb first.

As this is about UABI, if this is expected, it would nice that we can
explicitly document this requirement. Or we just get the fresh report
from the device all the time?

Thanks,
Zhi.


> Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
> ---

---

## [114] Jason Gunthorpe — 2024-09-15
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Fri, Aug 23, 2024 at 11:21:26PM +1000, Alexey Kardashevskiy wrote:
> IOMMUFD calls get_user_pages() for every mapping which will allocate
> shared memory instead of using private memory managed by the KVM and

Please check this series, it is much more how I would expect this to
work. Use the guest memfd directly and forget about kvm in the iommufd code:

https://lore.kernel.org/r/1726319158-283074-1-git-send-email-steven.sistare@oracle.com

I would imagine you'd detect the guest memfd when accepting the FD and
then having some different path in the pinning logic to pin and get
the physical ranges out.

Probably we would also need some CAP interaction with the iommu driver
to understand if it can accept private pages to even allow this in the
first place.

Thanks,
Jason

---

## [115] Alexey Kardashevskiy — 2024-09-16
*Subject: Re: [RFC PATCH 17/21] coco/sev-guest: Implement the guest side of
 things*

On 14/9/24 17:19, Zhi Wang wrote:
> On Fri, 23 Aug 2024 23:21:31 +1000
> Alexey Kardashevskiy <aik@amd.com> wrote:

We do need to document the UABI.

> Or we just get the fresh report from the device all the time?

I'd do just that (and it should not really change as long as the TDI 
stays is in LOCKED/RUN) but since you are asking - I suspect there is a 
caveat, is not there? Thanks,

---

## [116] Xu Yilun — 2024-09-18
*Subject: Re: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

On Sat, Sep 14, 2024 at 08:19:46AM +0300, Zhi Wang wrote:
> On Sat, 14 Sep 2024 02:47:27 +0000
> "Tian, Kevin" <kevin.tian@intel.com> wrote:

Previously we tried to do host side "bind-capable" setup (TDI context
creation required by firmware but no LOCK) at setup time. But didn't
see enough value, only to make the error recovery flow more complex. So
now I actually didn't see much work to do for "bind-capable", just to
mark the device as can-be-private. I.e. the context from establishing
the vPCI device are moved to GHCx BIND phase.

> > > 
> > 

I agree GHCx BIND/UNBIND been routed to QEMU, cause there are host side
cross module managements for BIND/UNBIND. E.g. IOMMUFD page table
switching, VFIO side settings that builds host side TDI context & LOCK
TDI.

But I do support other GHCx calls between BIND/UNBIND been directly
route to TSM low-level. E.g. get device interface report, get device
certification/measurement, TDISP RUN. It is because these communications
are purely for CoCo-VM, firmware and TDI. Host is totally out of its
business and worth nothing to pass these requirements to QEMU/VFIO and
still back into TSM low-level.

Thanks,
Yilun

> > 
> >

---

## [117] Tian, Kevin — 2024-09-20
*Subject: RE: [RFC PATCH 11/21] KVM: SEV: Add TIO VMGEXIT and bind TDI*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Wednesday, September 18, 2024 6:45 PM

sure. If VFIO is conceptually irrelevant to an operation it's certainly
right to skip it.

---

## [118] Vishal Annapurve — 2024-09-20
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Sun, Sep 15, 2024 at 11:08 PM Jason Gunthorpe <jgg@nvidia.com> wrote:
>
> On Fri, Aug 23, 2024 at 11:21:26PM +1000, Alexey Kardashevskiy wrote:

According to the discussion at KVM microconference around hugepage
support for guest_memfd [1], it's imperative that guest private memory
is not long term pinned. Ideal way to implement this integration would
be to support a notifier that can be invoked by guest_memfd when
memory ranges get truncated so that IOMMU can unmap the corresponding
ranges. Such a notifier should also get called during memory
conversion, it would be interesting to discuss how conversion flow
would work in this case.

[1] https://lpc.events/event/18/contributions/1764/ (checkout the
slide 12 from attached presentation)

>
> Probably we would also need some CAP interaction with the iommu driver

---

## [119] Tian, Kevin — 2024-09-23
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Vishal Annapurve <vannapurve@google.com>
> Sent: Saturday, September 21, 2024 5:11 AM

Most devices don't support I/O page fault hence can only DMA to long
term pinned buffers. The notifier might be helpful for in-kernel conversion
but as a basic requirement there needs a way for IOMMUFD to call into
guest memfd to request long term pinning for a given range. That is
how I interpreted "different path" in Jason's comment.

---

## [120] Vishal Annapurve — 2024-09-23
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Mon, Sep 23, 2024 at 7:36 AM Tian, Kevin <kevin.tian@intel.com> wrote:
>
> > From: Vishal Annapurve <vannapurve@google.com>

Policy that is being aimed here:
1) guest_memfd will pin the pages backing guest memory for all users.
2) kvm_gmem_get_pfn users will get a locked folio with elevated
refcount when asking for the pfn/page from guest_memfd. Users will
drop the refcount and release the folio lock when they are done
using/installing (e.g. in KVM EPT/IOMMU PT entries) it. This folio
lock is supposed to be held for short durations.
3) Users can assume the pfn is around until they are notified by
guest_memfd on truncation or memory conversion.

Step 3 above is already followed by KVM EPT setup logic for CoCo VMs.
TDX VMs especially need to have secure EPT entries always mapped (once
faulted-in) while the guest memory ranges are private.

---

## [121] Tian, Kevin — 2024-09-23
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Vishal Annapurve <vannapurve@google.com>
> Sent: Monday, September 23, 2024 2:34 PM

'faulted-in' doesn't work for device DMAs (w/o IOPF).

and above is based on the assumption that CoCo VM will always
map/pin the private memory pages until a conversion happens.

Conversion is initiated by the guest so ideally the guest is responsible 
for not leaving any in-fly DMAs to the page which is being converted.
From this angle it is fine for IOMMUFD to receive a notification from
guest memfd when such a conversion happens.

But I'm not sure whether the TDX way is architectural or just an
implementation choice which could be changed later, or whether it
applies to other arch.

If that behavior cannot be guaranteed, then we may still need a way
for IOMMUFD to request long term pin.

---

## [122] Jason Gunthorpe — 2024-09-23
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Mon, Sep 23, 2024 at 08:24:40AM +0000, Tian, Kevin wrote:
> > From: Vishal Annapurve <vannapurve@google.com>
> > Sent: Monday, September 23, 2024 2:34 PM

Right, I think the expectation is if a guest has active DMA on a page
it is changing between shared/private there is no expectation that the
DMA will succeed. So we don't need page fault, we just need to allow
it to safely fail.

IMHO we should try to do as best we can here, and the ideal interface
would be a notifier to switch the shared/private pages in some portion
of the guestmemfd. With the idea that iommufd could perhaps do it
atomically.

When the notifier returns then the old pages are fenced off at the
HW.  

But this would have to be a sleepable notifier that can do memory
allocation.

It is actually pretty complicated and we will need a reliable cut
operation to make this work on AMD v1.

Jason

---

## [123] Vishal Annapurve — 2024-09-23
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Mon, Sep 23, 2024, 10:24 AM Tian, Kevin <kevin.tian@intel.com> wrote:
>
> > From: Vishal Annapurve <vannapurve@google.com>

faulted-in can be replaced with mapped-in for the context of IOMMU operations.

>
> and above is based on the assumption that CoCo VM will always

Host physical memory is pinned by the host software stack. If you are
talking about arch specific logic in KVM, then the expectation again
is that guest_memfd will give pinned memory to it's users.

>
> Conversion is initiated by the guest so ideally the guest is responsible

All private memory accesses from TDX VMs go via Secure EPT. If host
removes secure EPT entries without guest intervention then linux guest
has a logic to generate a panic when it encounters EPT violation on
private memory accesses [1].

>
> If that behavior cannot be guaranteed, then we may still need a way

[1] https://elixir.bootlin.com/linux/v6.11/source/arch/x86/coco/tdx/tdx.c#L677

---

## [124] Tian, Kevin — 2024-09-23
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Jason Gunthorpe <jgg@nvidia.com>
> Sent: Tuesday, September 24, 2024 12:03 AM

yes atomic replacement is necessary here, as there might be in-fly
DMAs to pages adjacent to the one being converted in the same
1G hunk. Unmap/remap could potentially break it.

---

## [125] Tian, Kevin — 2024-09-23
*Subject: RE: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

> From: Vishal Annapurve <vannapurve@google.com>
> Sent: Tuesday, September 24, 2024 4:54 AM

sorry it's a typo. I meant the host does it for CoCo VM.

> 
> >

Yeah, that sounds good.

> 
> >

---

## [126] Jason Gunthorpe — 2024-09-24
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Mon, Sep 23, 2024 at 11:52:19PM +0000, Tian, Kevin wrote:
> > IMHO we should try to do as best we can here, and the ideal interface
> > would be a notifier to switch the shared/private pages in some portion

Yeah.. This integration is going to be much more complicated than I
originally thought about. It will need the generic pt stuff as the
hitless page table manipulations we are contemplating here are pretty
complex.

Jason

---

## [127] Vishal Annapurve — 2024-09-25
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Tue, Sep 24, 2024 at 2:07 PM Jason Gunthorpe <jgg@nvidia.com> wrote:
>
> On Mon, Sep 23, 2024 at 11:52:19PM +0000, Tian, Kevin wrote:

 To ensure that I understand your concern properly, the complexity of
handling hitless page manipulations is because guests can convert
memory at smaller granularity than the physical page size used by the
host software. Complexity remains the same irrespective of whether
kvm/guest_memfd is notifying iommu driver to unmap converted ranges or
if its userspace notifying iommu driver.

---

## [128] Jason Gunthorpe — 2024-09-25
*Subject: Re: [RFC PATCH 12/21] KVM: IOMMUFD: MEMFD: Map private pages*

On Wed, Sep 25, 2024 at 10:44:12AM +0200, Vishal Annapurve wrote:
> On Tue, Sep 24, 2024 at 2:07 PM Jason Gunthorpe <jgg@nvidia.com> wrote:
> >

Yes

You want to, say, break up a 1G private page into 2M chunks and then
hitlessly replace a 2M chunk with a shared one. Unlike the MM side you
don't really want to just non-present the whole thing and fault it
back in. So it is more complex.

We already plan to build the 1G -> 2M transformation for dirty
tracking, the atomic replace will be a further operation.

In the short term you could experiment on this using unmap/remap, but
that isn't really going to work well as a solution. You really can't
unmap an entire 1G page just to poke a 2M hole into it without
disrupting the guest DMA.

Fortunately the work needed to resolve this is well in progress, I had
not realized there was a guest memfd connection, but this is good to
know. It means more people will be intersted in helping :) :)

> Complexity remains the same irrespective of whether kvm/guest_memfd
> is notifying iommu driver to unmap converted ranges or if its

You don't want to use the verb 'unmap'.

What you want is a verb more like 'refresh' which can only make sense
in the kernel. 'refresh' would cause the iommu copy of the physical
addresses to update to match the current data in the guestmemfd.

So the private/shared sequence would be like:

1) Guest asks for private -> shared
2) Guestmemfd figures out what the new physicals should be for the
   shared
3) Guestmemfd does 'refresh' on all of its notifiers. This will pick
   up the new shared physical and remove the old private physical from
   the iommus
4) Guestmemfd can be sure nothing in iommu is touching the old memory.

There are some other small considerations that increase complexity,
like AMD needs an IOPTE boundary at any transition between
shared/private. This is a current active bug in the AMD stuff, fixing
it automatically and preserving huge pages via special guestmemfd
support sounds very appealing to me.

Jason

---
