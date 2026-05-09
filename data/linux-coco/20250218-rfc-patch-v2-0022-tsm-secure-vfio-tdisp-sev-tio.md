---
title: '[RFC PATCH v2 00/22] TSM: Secure VFIO, TDISP, SEV TIO'
date: 2025-02-18
last_reply: 2025-04-24
message_count: 92
participants: ['Alexey Kardashevskiy', 'Jason Gunthorpe', 'Michael Roth', 'Xu Yilun', 'Borislav Petkov', 'Suzuki K Poulose', 'Dan Williams', 'Francesco Lavra', 'Aneesh Kumar K.V', 'Tian, Kevin', 'Bjorn Helgaas']
---

## [1] Alexey Kardashevskiy — 2025-02-18

Here are some patches to enable SEV-TIO on AMD Turin. It's been a while
and got quiet and I kept fixing my tree and wondering if I am going in
the right direction.

SEV-TIO allow a guest to establish trust in a device that supports TEE
Device Interface Security Protocol (TDISP, defined in PCIe r6.0+) and
then interact with the device via private memory.

These include both guest and host support. QEMU also requires changes.
This is more to show what it takes on AMD EPYC to pass through TDISP
devices, hence "RFC".

Components affected:
KVM
IOMMUFD
CCP (AMD)
SEV-GUEST (AMD)

New components:
PCI IDE
PCI TSM
VIRT CoCo TSM
VIRT CoCo TSM-HOST
VIRT CoCo TSM-GUEST


This is based on a merge of Lukas'es CMA and 1 week old upstream + some of Dan's patches:

https://github.com/aik/linux/tree/tsm
https://github.com/aik/qemu/tree/tsm

Not using "[PATCH 03/11] coco/tsm: Introduce a class device for TEE Security Managers"
yet as may be (may be) my approach makes sense too. Tried to stick to the terminology.
I have done some changes on top of that, these are on github, not posting here as
I expect those to be addressed in that thread:
https://lore.kernel.org/linux-coco/173343739517.1074769.13134786548545925484.stgit@dwillia2-xfh.jf.intel.com/T/


SEV TIO spec:
https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58271_0_70.pdf
Whitepaper:
https://www.amd.com/content/dam/amd/en/documents/epyc-business-docs/white-papers/sev-tio-whitepaper.pdf


Acronyms:

TEE - Trusted Execution Environments, a concept of managing trust between the host
	and devices
TSM - TEE Security Manager (TSM), an entity which ensures security on the host
PSP - AMD platform secure processor (also "ASP", "AMD-SP"), acts as TSM on AMD.
SEV TIO - the TIO protocol implemented by the PSP and used by the host
GHCB - guest/host communication block - a protocol for guest-to-host communication
	via a shared page
TDISP - TEE Device Interface Security Protocol (PCIe).


Flow:

- Boot host OS, load CCP and PCI TSM (they will load TSM-HOST too)
- PCI TSM creates sysfs nodes in "coco/tsm: Add tsm and tsm-host modules" for all TDISP-capable devices
- Enable IDE via "echo 0 > /sys/bus/pci/devices/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_dev_connect"
- Examine certificates/measurements/status via sysfs

- run an SNP VM _without_ VFIO PCI device, wait till it is booted
- hotplug a TDISP-capable PCI function, IOMMUFD must be used (not a VFIO container)
- QEMU pins all guest memory via IOMMUFD map-from-fd ioctl()
- the VM detects a TDISP-capable device, creates sysfs nodes in "coco/tsm: Add tsm-guest module"
- the VM loads the device driver which goes as usual till enabling bus master (for convinience)
- TSM-GUEST modules listens for bus master event (hacked in "pci: Add BUS_NOTIFY_PCI_BUS_MASTER event")
- TSM-GUEST requests TDI ("trusted PCI VF") info, traps into QEMU
- QEMU binds the VF to the Coco VM in the secure fw (AMD PSP) via IOMMUFD ioctl
- QEMU reads certificates/measurements/interface report from the hosts sysfs and writes to the guest memory
- the guest receives all the data, examines it (not in this series though)
- the guest enables secure DMA and MMIO by calling GHCB which traps into QEMU
- QEMU calls IOMMUFD ioctl to enable secure DMA and MMIO
- the guest can now stop sharing memory for DMA (and expect DMA to encrypted memory to work) and
start accessing validated MMIO with Cbit set.



Assumptions

This requires hotpligging into the VM vs passing the device via the command line as
VFIO maps all guest memory as the device init step which is too soon as
SNP LAUNCH UPDATE happens later and will fail if VFIO maps private memory before that.

This requires the BME hack as MMIO and BusMaster enable bits cannot be 0 after MMIO
validation is done and there are moments in the guest OS booting process when this
appens.

SVSM could help addressing these (not implemented).

QEMU advertises TEE-IO capability to the VM. An additional x-tio flag is added to
vfio-pci.

Trying to avoid the device driver modification as much as possible at
the moment as my test devices already exist in non-TDISP form and need to work without
modification. Arguably this may not be always the case.


TODOs

Deal with PCI reset. Hot unplug+plug? Power states too.
Actually collaborate with CMA.
Other tons of things.


The previous conversation is here:
https://lore.kernel.org/r/20240823132137.336874-1-aik@amd.com


Changes:
v2:
* redid the whole thing pretty much
* RMPUPDATE API for QEMU
* switched to IOMMUFD
* mapping guest memory via IOMMUFD map-from-fd
* marking resouces as validated
* more modules
* moved tons to the userspace (QEMU), such as TDI bind and GHCB guest requests


Sean, get_maintainer.pl produced more than 100 emails for the entire
patchset, should I have posted them all anyway?

Please comment. Thanks.



Alexey Kardashevskiy (22):
  pci/doe: Define protocol types and make those public
  PCI/IDE: Fixes to make it work on AMD SNP-SEV
  PCI/IDE: Init IDs on all IDE streams beforehand
  iommu/amd: Report SEV-TIO support
  crypto: ccp: Enable SEV-TIO feature in the PSP when supported
  KVM: X86: Define tsm_get_vmid
  coco/tsm: Add tsm and tsm-host modules
  pci/tsm: Add PCI driver for TSM
  crypto/ccp: Implement SEV TIO firmware interface
  KVM: SVM: Add uAPI to change RMP for MMIO
  KVM: SEV: Add TIO VMGEXIT
  iommufd: Allow mapping from guest_memfd
  iommufd: amd-iommu: Add vdevice support
  iommufd: Add TIO calls
  KVM: X86: Handle private MMIO as shared
  coco/tsm: Add tsm-guest module
  resource: Mark encrypted MMIO resource on validation
  coco/sev-guest: Implement the guest support for SEV TIO
  RFC: pci: Add BUS_NOTIFY_PCI_BUS_MASTER event
  sev-guest: Stop changing encrypted page state for TDISP devices
  pci: Allow encrypted MMIO mapping via sysfs
  pci: Define pci_iomap_range_encrypted

 drivers/crypto/ccp/Makefile                 |   13 +
 drivers/pci/Makefile                        |    3 +
 drivers/virt/coco/Makefile                  |    2 +
 drivers/virt/coco/guest/Makefile            |    3 +
 drivers/virt/coco/host/Makefile             |    6 +
 drivers/virt/coco/sev-guest/Makefile        |    2 +-
 arch/x86/include/asm/kvm-x86-ops.h          |    1 +
 arch/x86/include/asm/kvm_host.h             |    2 +
 arch/x86/include/asm/sev.h                  |   31 +
 arch/x86/include/uapi/asm/kvm.h             |   11 +
 arch/x86/include/uapi/asm/svm.h             |    2 +
 drivers/crypto/ccp/sev-dev-tio.h            |  111 ++
 drivers/crypto/ccp/sev-dev.h                |   19 +
 drivers/iommu/amd/amd_iommu_types.h         |    3 +
 drivers/iommu/iommufd/iommufd_private.h     |    3 +
 include/asm-generic/pci_iomap.h             |    4 +
 include/linux/amd-iommu.h                   |    2 +
 include/linux/device.h                      |    4 +
 include/linux/device/bus.h                  |    3 +
 include/linux/dma-direct.h                  |    8 +
 include/linux/ioport.h                      |    2 +
 include/linux/kvm_host.h                    |    2 +
 include/linux/pci-doe.h                     |    4 +
 include/linux/pci-ide.h                     |   19 +-
 include/linux/pci.h                         |    2 +-
 include/linux/psp-sev.h                     |   61 +-
 include/linux/swiotlb.h                     |    8 +
 include/linux/tsm.h                         |  315 ++++
 include/uapi/linux/iommufd.h                |   26 +
 include/uapi/linux/kvm.h                    |   24 +
 include/uapi/linux/pci_regs.h               |    5 +-
 include/uapi/linux/psp-sev.h                |    6 +-
 include/uapi/linux/sev-guest.h              |   39 +
 arch/x86/coco/sev/core.c                    |   19 +-
 arch/x86/kvm/mmu/mmu.c                      |    6 +-
 arch/x86/kvm/svm/sev.c                      |  205 +++
 arch/x86/kvm/svm/svm.c                      |   12 +
 arch/x86/mm/ioremap.c                       |    2 +
 arch/x86/mm/mem_encrypt.c                   |    6 +
 arch/x86/virt/svm/sev.c                     |   34 +-
 drivers/crypto/ccp/sev-dev-tio.c            | 1664 ++++++++++++++++++++
 drivers/crypto/ccp/sev-dev-tsm.c            |  709 +++++++++
 drivers/crypto/ccp/sev-dev.c                |   94 +-
 drivers/iommu/amd/init.c                    |    9 +
 drivers/iommu/amd/iommu.c                   |   60 +-
 drivers/iommu/iommufd/main.c                |    6 +
 drivers/iommu/iommufd/pages.c               |   88 +-
 drivers/iommu/iommufd/viommu.c              |  112 ++
 drivers/pci/doe.c                           |    2 -
 drivers/pci/ide.c                           |  103 +-
 drivers/pci/iomap.c                         |   24 +
 drivers/pci/mmap.c                          |   11 +-
 drivers/pci/pci-sysfs.c                     |   27 +-
 drivers/pci/pci.c                           |    3 +
 drivers/pci/proc.c                          |    2 +-
 drivers/pci/tsm.c                           |  233 +++
 drivers/virt/coco/guest/tsm-guest.c         |  326 ++++
 drivers/virt/coco/host/tsm-host.c           |  551 +++++++
 drivers/virt/coco/sev-guest/sev_guest.c     |   10 +
 drivers/virt/coco/sev-guest/sev_guest_tio.c |  738 +++++++++
 drivers/virt/coco/tsm.c                     |  638 ++++++++
 kernel/resource.c                           |   48 +
 virt/kvm/kvm_main.c                         |    6 +
 Documentation/virt/coco/tsm.rst             |  132 ++
 drivers/crypto/ccp/Kconfig                  |    2 +
 drivers/pci/Kconfig                         |   15 +
 drivers/virt/coco/Kconfig                   |   14 +
 drivers/virt/coco/guest/Kconfig             |    3 +
 drivers/virt/coco/host/Kconfig              |    6 +
 drivers/virt/coco/sev-guest/Kconfig         |    1 +
 70 files changed, 6614 insertions(+), 53 deletions(-)
 create mode 100644 drivers/virt/coco/host/Makefile
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.h
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.c
 create mode 100644 drivers/crypto/ccp/sev-dev-tsm.c
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 drivers/virt/coco/guest/tsm-guest.c
 create mode 100644 drivers/virt/coco/host/tsm-host.c
 create mode 100644 drivers/virt/coco/sev-guest/sev_guest_tio.c
 create mode 100644 drivers/virt/coco/tsm.c
 create mode 100644 Documentation/virt/coco/tsm.rst
 create mode 100644 drivers/virt/coco/host/Kconfig

---

## [2] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 01/22] pci/doe: Define protocol types and make those public*

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
index e4b609f613da..98fd86fae8d8 100644
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

## [3] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 02/22] PCI/IDE: Fixes to make it work on AMD SNP-SEV*

The IDE proposed patches do setup of endpoints while they should focus
on root port.

These are workarounds better be discussed in
"[PATCH 00/11] PCI/TSM: Core infrastructure for PCI device security
(TDISP)"

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/pci-ide.h       | 19 +++--
 include/uapi/linux/pci_regs.h |  4 +-
 drivers/pci/ide.c             | 76 ++++++++++++++++----
 3 files changed, 78 insertions(+), 21 deletions(-)

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 24e08a413645..f784fb16cc88 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -8,26 +8,33 @@
 
 #include <linux/range.h>
 
+enum pci_ide_flags {
+	PCI_IDE_SETUP_ROOT_PORT = BIT(0),
+	PCI_IDE_SETUP_ROOT_PORT_MEM = BIT(1),
+};
+
 struct pci_ide {
 	int domain;
 	u16 devid_start;
 	u16 devid_end;
+	u16 rpid_start;
+	u16 rpid_end;
 	int stream_id;
 	const char *name;
 	int nr_mem;
 	struct range mem[16];
+	unsigned int dev_sel_ctl;
+	unsigned int rootport_sel_ctl;
+	enum pci_ide_flags flags;
 };
 
 void pci_ide_stream_probe(struct pci_dev *pdev, struct pci_ide *ide);
 
-enum pci_ide_flags {
-	PCI_IDE_SETUP_ROOT_PORT = BIT(0),
-};
-
 int pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide,
 			 enum pci_ide_flags flags);
-void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide,
-			     enum pci_ide_flags flags);
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide);
 void pci_ide_enable_stream(struct pci_dev *pdev, struct pci_ide *ide);
 void pci_ide_disable_stream(struct pci_dev *pdev, struct pci_ide *ide);
+int pci_ide_stream_state(struct pci_dev *pdev, struct pci_ide *ide, u32 *status, u32 *rpstatus);
+
 #endif /* __PCI_IDE_H__ */
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 498c6b298186..15bd8e2b3cf5 100644
--- a/include/uapi/linux/pci_regs.h
+++ b/include/uapi/linux/pci_regs.h
@@ -1293,9 +1293,9 @@
 /* Selective IDE Address Association Register Block, up to PCI_IDE_SEL_CAP_ASSOC_NUM */
 #define  PCI_IDE_SEL_ADDR_1(x)			(20 + (x) * 12)
 #define   PCI_IDE_SEL_ADDR_1_VALID		0x1
-#define   PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK	0x000fff0
+#define   PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK	0x000fff00
 #define   PCI_IDE_SEL_ADDR_1_BASE_LOW_SHIFT	20
-#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK 	0xfff0000
+#define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_MASK	0xfff00000
 #define   PCI_IDE_SEL_ADDR_1_LIMIT_LOW_SHIFT	20
 /* IDE Address Association Register 2 is "Memory Limit Upper" */
 /* IDE Address Association Register 3 is "Memory Base Upper" */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 500b63e149cf..3c53b27f8447 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -50,10 +50,10 @@ void pci_ide_init(struct pci_dev *pdev)
 	else
 		sel_ide_cap = ide_cap + PCI_IDE_LINK_STREAM;
 
-	for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val); i++) {
+	for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val) + 1; i++) {
 		if (i == 0) {
 			pci_read_config_dword(pdev, sel_ide_cap, &val);
-			nr_ide_mem = PCI_IDE_SEL_CAP_ASSOC_NUM(val);
+			nr_ide_mem = PCI_IDE_SEL_CAP_ASSOC_NUM(val) + 1;
 		} else {
 			int offset = sel_ide_offset(sel_ide_cap, i, nr_ide_mem);
 
@@ -118,7 +118,7 @@ void pci_set_nr_ide_streams(struct pci_host_bridge *hb, int nr)
 	hb->nr_ide_streams = nr;
 	sysfs_update_group(&hb->dev.kobj, &pci_ide_attr_group);
 }
-EXPORT_SYMBOL_NS_GPL(pci_set_nr_ide_streams, PCI_IDE);
+EXPORT_SYMBOL_NS_GPL(pci_set_nr_ide_streams, "PCI_IDE");
 
 void pci_init_host_bridge_ide(struct pci_host_bridge *hb)
 {
@@ -148,6 +148,10 @@ void pci_ide_stream_probe(struct pci_dev *pdev, struct pci_ide *ide)
 	else
 		ide->devid_end = ide->devid_start;
 
+	/* Enable everything into the rootport by default */
+	ide->rpid_start = 0;
+	ide->rpid_end = 0xffff;
+
 	/* TODO: address association probing... */
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_probe);
@@ -160,7 +164,7 @@ static void __pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
 			     pdev->nr_ide_mem);
 
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
-	for (int i = ide->nr_mem - 1; i >= 0; i--) {
+	for (int i = min(ide->nr_mem, pdev->nr_ide_mem) - 1; i >= 0; i--) {
 		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), 0);
 		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), 0);
 		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), 0);
@@ -169,7 +173,7 @@ static void __pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
         pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, 0);
 }
 
-static void __pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
+static int __pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide, bool mem, bool rp)
 {
 	int pos;
 	u32 val;
@@ -177,14 +181,20 @@ static void __pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 	pos = sel_ide_offset(pdev->sel_ide_cap, ide->stream_id,
 			     pdev->nr_ide_mem);
 
-	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT_MASK, ide->devid_end);
+	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT_MASK, rp ? ide->rpid_end : ide->devid_end);
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
 
 	val = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
-	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE_MASK, ide->devid_start) |
+	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE_MASK, rp ? ide->rpid_start : ide->devid_start) |
 	      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG_MASK, ide->domain);
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
 
+	if (!mem)
+		return 0;
+
+	if (ide->nr_mem > pdev->nr_ide_mem)
+		return -EINVAL;
+
 	for (int i = 0; i < ide->nr_mem; i++) {
 		val = FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |
 		      FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW_MASK,
@@ -201,6 +211,8 @@ static void __pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 		val = upper_32_bits(ide->mem[i].start);
 		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), val);
 	}
+
+	return 0;
 }
 
 /*
@@ -248,10 +260,14 @@ int pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide,
 			goto err;
 		}
 
-	__pci_ide_stream_setup(pdev, ide);
-	if (flags & PCI_IDE_SETUP_ROOT_PORT)
-		__pci_ide_stream_setup(rp, ide);
+	rc = __pci_ide_stream_setup(pdev, ide, true, false);
+	if (!rc && (flags & PCI_IDE_SETUP_ROOT_PORT))
+		rc = __pci_ide_stream_setup(rp, ide, !!(flags & PCI_IDE_SETUP_ROOT_PORT_MEM), true);
+
+	if (rc)
+		goto err;
 
+	ide->flags = flags;
 	return 0;
 err:
 	for (; mem >= 0; mem--)
@@ -268,6 +284,7 @@ EXPORT_SYMBOL_GPL(pci_ide_stream_setup);
 
 void pci_ide_enable_stream(struct pci_dev *pdev, struct pci_ide *ide)
 {
+	struct pci_dev *rp = pcie_find_root_port(pdev);
 	int pos;
 	u32 val;
 
@@ -276,14 +293,27 @@ void pci_ide_enable_stream(struct pci_dev *pdev, struct pci_ide *ide)
 
 	val = FIELD_PREP(PCI_IDE_SEL_CTL_ID_MASK, ide->stream_id) |
 	      FIELD_PREP(PCI_IDE_SEL_CTL_DEFAULT, 1);
+	val |= FIELD_PREP(PCI_IDE_SEL_CTL_EN, 1);
+	/* there is rootport and pdev is not it */
+	if (rp && rp != pdev)
+		val |= ide->dev_sel_ctl;
+	else
+		val |= ide->rootport_sel_ctl;
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
+
+	if (ide->flags & PCI_IDE_SETUP_ROOT_PORT && rp && rp != pdev)
+		pci_ide_enable_stream(rp, ide);
 }
 EXPORT_SYMBOL_GPL(pci_ide_enable_stream);
 
 void pci_ide_disable_stream(struct pci_dev *pdev, struct pci_ide *ide)
 {
+	struct pci_dev *rp = pcie_find_root_port(pdev);
 	int pos;
 
+	if (ide->flags & PCI_IDE_SETUP_ROOT_PORT && rp && rp != pdev)
+		pci_ide_disable_stream(rp, ide);
+
 	pos = sel_ide_offset(pdev->sel_ide_cap, ide->stream_id,
 			     pdev->nr_ide_mem);
 
@@ -291,14 +321,13 @@ void pci_ide_disable_stream(struct pci_dev *pdev, struct pci_ide *ide)
 }
 EXPORT_SYMBOL_GPL(pci_ide_disable_stream);
 
-void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide,
-			     enum pci_ide_flags flags)
+void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
 {
 	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
 	struct pci_dev *rp = pcie_find_root_port(pdev);
 
 	__pci_ide_stream_teardown(pdev, ide);
-	if (flags & PCI_IDE_SETUP_ROOT_PORT)
+	if (ide->flags & PCI_IDE_SETUP_ROOT_PORT)
 		__pci_ide_stream_teardown(rp, ide);
 
 	for (int i = ide->nr_mem - 1; i >= 0; i--)
@@ -309,3 +338,24 @@ void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide,
 	clear_bit_unlock(ide->stream_id, hb->ide_stream_ids);
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_teardown);
+
+static int __pci_ide_stream_state(struct pci_dev *pdev, struct pci_ide *ide, u32 *status)
+{
+	int pos = sel_ide_offset(pdev->sel_ide_cap, ide->stream_id,
+				 pdev->nr_ide_mem);
+
+	return pci_read_config_dword(pdev, pos + PCI_IDE_SEL_STS, status);
+}
+
+int pci_ide_stream_state(struct pci_dev *pdev, struct pci_ide *ide, u32 *status, u32 *rpstatus)
+{
+	int ret = __pci_ide_stream_state(pdev, ide, status);
+
+	if (!ret && ide->flags & PCI_IDE_SETUP_ROOT_PORT) {
+		struct pci_dev *rp = pcie_find_root_port(pdev);
+
+		ret = __pci_ide_stream_state(rp, ide, rpstatus);
+	}
+	return ret;
+}
+EXPORT_SYMBOL_GPL(pci_ide_stream_state);

---

## [4] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 03/22] PCI/IDE: Init IDs on all IDE streams beforehand*

The PCIe spec defines two types of streams - selective and link.
Each stream has an ID from the same bucket so a stream ID does not
tell the type.
The spec defines an "enable" bit for every stream and required
stream IDs to be unique among all enabled stream but there is no such
requirement for disabled streams.

However, when IDE_KM is programming keys, an IDE-capable device needs
to know the type of stream being programmed to write it directly to
the hardware as keys are relatively large, possibly many of them and
devices often struggle with keeping around rather big data not being
used.

Walk through all streams on a device and initialize the IDs to some
unique number, both link and selective.

Probably should be a quirk if it turns out not to be a common issue.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/pci/ide.c | 29 ++++++++++++++++++--
 1 file changed, 26 insertions(+), 3 deletions(-)

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 3c53b27f8447..5f1d5385d3a8 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -18,7 +18,7 @@ static int sel_ide_offset(u16 cap, int stream_id, int nr_ide_mem)
 void pci_ide_init(struct pci_dev *pdev)
 {
 	u16 ide_cap, sel_ide_cap;
-	int nr_ide_mem = 0;
+	int nr_ide_mem = 0, i, link_num, sel_num, offset;
 	u32 val = 0;
 
 	if (!pci_is_pcie(pdev))
@@ -33,6 +33,7 @@ void pci_ide_init(struct pci_dev *pdev)
 	 * require consistent number of address association blocks
 	 */
 	pci_read_config_dword(pdev, ide_cap + PCI_IDE_CAP, &val);
+
 	if ((val & PCI_IDE_CAP_SELECTIVE) == 0)
 		return;
 
@@ -43,6 +44,9 @@ void pci_ide_init(struct pci_dev *pdev)
 			return;
 	}
 
+	link_num = PCI_IDE_CAP_LINK_TC_NUM(val) + 1;
+	sel_num = PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val) + 1;
+
 	if (val & PCI_IDE_CAP_LINK)
 		sel_ide_cap = ide_cap + PCI_IDE_LINK_STREAM +
 			      (PCI_IDE_CAP_LINK_TC_NUM(val) + 1) *
@@ -50,12 +54,13 @@ void pci_ide_init(struct pci_dev *pdev)
 	else
 		sel_ide_cap = ide_cap + PCI_IDE_LINK_STREAM;
 
-	for (int i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val) + 1; i++) {
+	for (i = 0; i < PCI_IDE_CAP_SELECTIVE_STREAMS_NUM(val) + 1; i++) {
 		if (i == 0) {
+			offset = 0;
 			pci_read_config_dword(pdev, sel_ide_cap, &val);
 			nr_ide_mem = PCI_IDE_SEL_CAP_ASSOC_NUM(val) + 1;
 		} else {
-			int offset = sel_ide_offset(sel_ide_cap, i, nr_ide_mem);
+			offset = sel_ide_offset(sel_ide_cap, i, nr_ide_mem);
 
 			pci_read_config_dword(pdev, offset, &val);
 
@@ -68,6 +73,24 @@ void pci_ide_init(struct pci_dev *pdev)
 				return;
 			}
 		}
+
+		/* Some devices insist on streamid to be unique even for not enabled streams */
+		val &= ~PCI_IDE_SEL_CTL_ID_MASK;
+		val |= FIELD_PREP(PCI_IDE_SEL_CTL_ID_MASK, i);
+		pci_write_config_dword(pdev, offset + PCI_IDE_SEL_CTL, val);
+	}
+
+	if (val & PCI_IDE_CAP_LINK) {
+		/* Some devices insist on streamid to be unique even for not enabled streams */
+		for (i = 0; i < link_num; ++i) {
+			offset = ide_cap + PCI_IDE_LINK_STREAM + i * PCI_IDE_LINK_BLOCK_SIZE;
+
+			pci_read_config_dword(pdev, offset, &val);
+			val &= ~PCI_IDE_LINK_CTL_ID_MASK;
+			val |= FIELD_PREP(PCI_IDE_LINK_CTL_ID_MASK, i + sel_num);
+
+			pci_write_config_dword(pdev, offset, val);
+		}
 	}
 
 	pdev->ide_cap = ide_cap;

---

## [5] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 04/22] iommu/amd: Report SEV-TIO support*

The AMD BIOS'es "SEV-TIO" switch is reported to the OS via IOMMU
Extended Feature 2 register (EFR2), bit 1.

Add helper to parse the bit and report the feature presense.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/iommu/amd/amd_iommu_types.h | 1 +
 include/linux/amd-iommu.h           | 2 ++
 drivers/iommu/amd/init.c            | 9 +++++++++
 3 files changed, 12 insertions(+)

diff --git a/drivers/iommu/amd/amd_iommu_types.h b/drivers/iommu/amd/amd_iommu_types.h
index 0bbda60d3cdc..b086fb632990 100644
--- a/drivers/iommu/amd/amd_iommu_types.h
+++ b/drivers/iommu/amd/amd_iommu_types.h
@@ -108,6 +108,7 @@
 
 
 /* Extended Feature 2 Bits */
+#define FEATURE_SEVSNPIO_SUP	BIT_ULL(1)
 #define FEATURE_SNPAVICSUP	GENMASK_ULL(7, 5)
 #define FEATURE_SNPAVICSUP_GAM(x) \
 	(FIELD_GET(FEATURE_SNPAVICSUP, x) == 0x1)
diff --git a/include/linux/amd-iommu.h b/include/linux/amd-iommu.h
index 062fbd4c9b77..cb1b94fdb63c 100644
--- a/include/linux/amd-iommu.h
+++ b/include/linux/amd-iommu.h
@@ -32,10 +32,12 @@ struct task_struct;
 struct pci_dev;
 
 extern void amd_iommu_detect(void);
+extern bool amd_iommu_sev_tio_supported(void);
 
 #else /* CONFIG_AMD_IOMMU */
 
 static inline void amd_iommu_detect(void) { }
+static inline bool amd_iommu_sev_tio_supported(void) { return false; }
 
 #endif /* CONFIG_AMD_IOMMU */
 
diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index c5cd92edada0..9f2756d3bd73 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -2156,6 +2156,9 @@ static void print_iommu_info(void)
 		if (check_feature(FEATURE_SNP))
 			pr_cont(" SNP");
 
+		if (check_feature2(FEATURE_SEVSNPIO_SUP))
+			pr_cont(" SEV-TIO");
+
 		pr_cont("\n");
 	}
 
@@ -3856,4 +3859,10 @@ int amd_iommu_snp_disable(void)
 	return 0;
 }
 EXPORT_SYMBOL_GPL(amd_iommu_snp_disable);
+
+bool amd_iommu_sev_tio_supported(void)
+{
+	return check_feature2(FEATURE_SEVSNPIO_SUP);
+}
+EXPORT_SYMBOL_GPL(amd_iommu_sev_tio_supported);
 #endif

---

## [6] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 05/22] crypto: ccp: Enable SEV-TIO feature in the PSP when supported*

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
 drivers/crypto/ccp/sev-dev.h |  1 +
 include/linux/psp-sev.h      | 32 +++++++-
 include/uapi/linux/psp-sev.h |  4 +-
 drivers/crypto/ccp/sev-dev.c | 84 +++++++++++++++++++-
 4 files changed, 115 insertions(+), 6 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index d382a265350b..c87a312f7da6 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -71,6 +71,7 @@ struct sev_device {
 	struct fw_upload *fwl;
 	bool fw_cancel;
 #endif /* CONFIG_FW_UPLOAD */
+	bool tio_en;
 };
 
 bool sev_version_greater_or_equal(u8 maj, u8 min);
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 788505d46d25..103d9c161f41 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -107,6 +107,7 @@ enum sev_cmd {
 	SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX = 0x0CA,
 	SEV_CMD_SNP_COMMIT		= 0x0CB,
 	SEV_CMD_SNP_VLEK_LOAD		= 0x0CD,
+	SEV_CMD_SNP_FEATURE_INFO	= 0x0CE,
 
 	SEV_CMD_MAX,
 };
@@ -146,6 +147,7 @@ struct sev_data_init_ex {
 } __packed;
 
 #define SEV_INIT_FLAGS_SEV_ES	0x01
+#define SEV_INIT_FLAGS_SEV_TIO_EN	BIT(2)
 
 /**
  * struct sev_data_pek_csr - PEK_CSR command parameters
@@ -601,6 +603,25 @@ struct sev_data_snp_addr {
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
@@ -762,10 +783,14 @@ struct sev_data_snp_guest_request {
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
@@ -804,7 +829,8 @@ struct sev_data_range_list {
 struct sev_data_snp_shutdown_ex {
 	u32 len;
 	u32 iommu_snp_shutdown:1;
-	u32 rsvd1:31;
+	u32 x86_snp_shutdown:1;
+	u32 rsvd1:30;
 } __packed;
 
 /**
diff --git a/include/uapi/linux/psp-sev.h b/include/uapi/linux/psp-sev.h
index b508b355a72e..affa65dcebd4 100644
--- a/include/uapi/linux/psp-sev.h
+++ b/include/uapi/linux/psp-sev.h
@@ -189,6 +189,7 @@ struct sev_user_data_get_id2 {
  * @mask_chip_id: whether chip id is present in attestation reports or not
  * @mask_chip_key: whether attestation reports are signed or not
  * @vlek_en: VLEK (Version Loaded Endorsement Key) hashstick is loaded
+ * @feature_info: Indicates that the SNP_FEATURE_INFO command is available
  * @rsvd1: reserved
  * @guest_count: the number of guest currently managed by the firmware
  * @current_tcb_version: current TCB version
@@ -204,7 +205,8 @@ struct sev_user_data_snp_status {
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
index 7c9e6ca33bd2..b01e5f913727 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -74,6 +74,10 @@ static bool psp_init_on_probe = true;
 module_param(psp_init_on_probe, bool, 0444);
 MODULE_PARM_DESC(psp_init_on_probe, "  if true, the PSP will be initialized on module init. Else the PSP will be initialized on the first command requiring it");
 
+/* enable/disable SEV-TIO support */
+static bool sev_tio_enabled = true;
+module_param_named(sev_tio, sev_tio_enabled, bool, 0444);
+
 MODULE_FIRMWARE("amd/amd_sev_fam17h_model0xh.sbin"); /* 1st gen EPYC */
 MODULE_FIRMWARE("amd/amd_sev_fam17h_model3xh.sbin"); /* 2nd gen EPYC */
 MODULE_FIRMWARE("amd/amd_sev_fam19h_model0xh.sbin"); /* 3rd gen EPYC */
@@ -228,6 +232,7 @@ static int sev_cmd_buffer_len(int cmd)
 	case SEV_CMD_SNP_GUEST_REQUEST:		return sizeof(struct sev_data_snp_guest_request);
 	case SEV_CMD_SNP_CONFIG:		return sizeof(struct sev_user_data_snp_config);
 	case SEV_CMD_SNP_COMMIT:		return sizeof(struct sev_data_snp_commit);
+	case SEV_CMD_SNP_FEATURE_INFO:		return sizeof(struct sev_data_snp_feature_info);
 	case SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX:	return sizeof(struct sev_data_download_firmware_ex);
 	default:				return 0;
 	}
@@ -1055,7 +1060,7 @@ static int __sev_init_ex_locked(int *error)
 		 */
 		data.tmr_address = __pa(sev_es_tmr);
 
-		data.flags |= SEV_INIT_FLAGS_SEV_ES;
+		data.flags |= SEV_INIT_FLAGS_SEV_ES | SEV_INIT_FLAGS_SEV_TIO_EN;
 		data.tmr_len = sev_es_tmr_size;
 	}
 
@@ -1226,6 +1231,77 @@ int sev_snp_guest_decommission(int asid, int *psp_ret)
 }
 EXPORT_SYMBOL_GPL(sev_snp_guest_decommission);
 
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
@@ -1290,6 +1366,8 @@ static int __sev_snp_init_locked(int *error)
 		data.init_rmp = 1;
 		data.list_paddr_en = 1;
 		data.list_paddr = __psp_pa(snp_range_list);
+		data.tio_en = sev_tio_enabled && sev_tio_present(sev) &&
+			amd_iommu_sev_tio_supported();
 		cmd = SEV_CMD_SNP_INIT_EX;
 	} else {
 		cmd = SEV_CMD_SNP_INIT;
@@ -1319,7 +1397,9 @@ static int __sev_snp_init_locked(int *error)
 		return rc;
 
 	sev->snp_initialized = true;
-	dev_dbg(sev->dev, "SEV-SNP firmware initialized\n");
+	sev->tio_en = data.tio_en;
+	dev_dbg(sev->dev, "SEV-SNP firmware initialized, SEV-TIO is %s\n",
+		sev->tio_en ? "enabled" : "disabled");
 
 	sev_es_tmr_size = SNP_TMR_SIZE;

---

## [7] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 06/22] KVM: X86: Define tsm_get_vmid*

In order to add a PCI VF into a secure VM, the TSM module needs to
perform a "TDI bind" operation. The secure module ("PSP" for AMD)
reuqires a VM id to associate with a VM and KVM has it. Since
KVM cannot directly bind a TDI (as it does not have all necesessary
data such as host/guest PCI BDFn). QEMU and IOMMUFD do know the BDFns
but they do not have a VM id recognisable by the PSP.

Add get_vmid() hook to KVM. Implement it for AMD SEV to return a sum
of GCTX (a private page describing secure VM context) and ASID
(required on unbind for IOMMU unfencing, when needed).

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  1 +
 arch/x86/include/asm/kvm_host.h    |  2 ++
 include/linux/kvm_host.h           |  2 ++
 arch/x86/kvm/svm/svm.c             | 12 ++++++++++++
 virt/kvm/kvm_main.c                |  6 ++++++
 5 files changed, 23 insertions(+)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index c35550581da0..63102a224cd7 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -144,6 +144,7 @@ KVM_X86_OP_OPTIONAL(alloc_apic_backing_page)
 KVM_X86_OP_OPTIONAL_RET0(gmem_prepare)
 KVM_X86_OP_OPTIONAL_RET0(private_max_mapping_level)
 KVM_X86_OP_OPTIONAL(gmem_invalidate)
+KVM_X86_OP_OPTIONAL(tsm_get_vmid)
 
 #undef KVM_X86_OP
 #undef KVM_X86_OP_OPTIONAL
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index b15cde0a9b5c..9330e8d4d29d 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1875,6 +1875,8 @@ struct kvm_x86_ops {
 	int (*gmem_prepare)(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 	void (*gmem_invalidate)(kvm_pfn_t start, kvm_pfn_t end);
 	int (*private_max_mapping_level)(struct kvm *kvm, kvm_pfn_t pfn);
+
+	u64 (*tsm_get_vmid)(struct kvm *kvm);
 };
 
 struct kvm_x86_nested_ops {
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index f34f4cfaa513..6cd351edb956 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2571,4 +2571,6 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 				    struct kvm_pre_fault_memory *range);
 #endif
 
+u64 kvm_arch_tsm_get_vmid(struct kvm *kvm);
+
 #endif
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 7640a84e554a..0276d60c61d6 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4998,6 +4998,16 @@ static void *svm_alloc_apic_backing_page(struct kvm_vcpu *vcpu)
 	return page_address(page);
 }
 
+static u64 svm_tsm_get_vmid(struct kvm *kvm)
+{
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
+
+	if (!sev->es_active)
+		return 0;
+
+	return ((u64) sev->snp_context) | sev->asid;
+}
+
 static struct kvm_x86_ops svm_x86_ops __initdata = {
 	.name = KBUILD_MODNAME,
 
@@ -5137,6 +5147,8 @@ static struct kvm_x86_ops svm_x86_ops __initdata = {
 	.gmem_prepare = sev_gmem_prepare,
 	.gmem_invalidate = sev_gmem_invalidate,
 	.private_max_mapping_level = sev_private_max_mapping_level,
+
+	.tsm_get_vmid = svm_tsm_get_vmid,
 };
 
 /*
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index ba0327e2d0d3..90c3ff7c5c02 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6464,3 +6464,9 @@ void kvm_exit(void)
 	kvm_irqfd_exit();
 }
 EXPORT_SYMBOL_GPL(kvm_exit);
+
+u64 kvm_arch_tsm_get_vmid(struct kvm *kvm)
+{
+	return static_call(kvm_x86_tsm_get_vmid)(kvm);
+}
+EXPORT_SYMBOL_GPL(kvm_arch_tsm_get_vmid);

---

## [8] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 07/22] coco/tsm: Add tsm and tsm-host modules*

The TSM module is a library to create sysfs nodes common for hypervisors
and VMs. It also provides helpers to parse interface reports (required
by VMs, visible to HVs). It registers 3 device classes:
- tsm: one per platform,
- tsm-dev: for physical functions, ("TDEV");
- tdm-tdi: for PCI functions being assigned to VMs ("TDI").

The library adds a child device of "tsm-dev" or/and "tsm-tdi" class
for every capable PCI device. Note that the module is made bus-agnostic.

New device nodes provide sysfs interface for fetching device certificates
and measurements and TDI interface reports.
Nodes with the "_user" suffix provide human-readable information, without
that suffix it is raw binary data to be copied to a guest.

The TSM-HOST module adds hypervisor-only functionality on top. At the
moment it is:
- "connect" to enable/disable IDE (a PCI link encryption);
- "TDI bind" to manage a PCI function passed through to a secure VM.

A platform is expected to register itself in TSM-HOST and provide
necessary callbacks. No platform is added here, AMD SEV is coming in the
next patches.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/Makefile        |   2 +
 drivers/virt/coco/host/Makefile   |   6 +
 include/linux/tsm.h               | 295 +++++++++
 drivers/virt/coco/host/tsm-host.c | 552 +++++++++++++++++
 drivers/virt/coco/tsm.c           | 636 ++++++++++++++++++++
 Documentation/virt/coco/tsm.rst   |  99 +++
 drivers/virt/coco/Kconfig         |  14 +
 drivers/virt/coco/host/Kconfig    |   6 +
 8 files changed, 1610 insertions(+)

diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 885c9ef4e9fc..670f77c564e8 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -2,9 +2,11 @@
 #
 # Confidential computing related collateral
 #
+obj-$(CONFIG_TSM)		+= tsm.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM_REPORTS)	+= guest/
+obj-$(CONFIG_TSM_HOST)          += host/
diff --git a/drivers/virt/coco/host/Makefile b/drivers/virt/coco/host/Makefile
new file mode 100644
index 000000000000..c5e216b6cb1c
--- /dev/null
+++ b/drivers/virt/coco/host/Makefile
@@ -0,0 +1,6 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# TSM (TEE Security Manager) Common infrastructure and host drivers
+
+obj-$(CONFIG_TSM_HOST) += tsm_host.o
+tsm_host-y += tsm-host.o
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 431054810dca..486e386d90fc 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,11 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <linux/device.h>
+#include <linux/slab.h>
+#include <linux/mutex.h>
+#include <linux/device.h>
+#include <linux/bitfield.h>
 
 #define TSM_REPORT_INBLOB_MAX 64
 #define TSM_REPORT_OUTBLOB_MAX SZ_32K
@@ -109,4 +114,294 @@ struct tsm_report_ops {
 
 int tsm_report_register(const struct tsm_report_ops *ops, void *priv);
 int tsm_report_unregister(const struct tsm_report_ops *ops);
+
+/* SPDM control structure for DOE */
+struct tsm_spdm {
+	unsigned long req_len;
+	void *req;
+	unsigned long rsp_len;
+	void *rsp;
+};
+
+/* Data object for measurements/certificates/attestationreport */
+struct tsm_blob {
+	void *data;
+	size_t len;
+};
+
+struct tsm_blob *tsm_blob_new(void *data, size_t len);
+static inline void tsm_blob_free(struct tsm_blob *b)
+{
+	kfree(b);
+}
+
+/**
+ * struct tdisp_interface_id - TDISP INTERFACE_ID Definition
+ *
+ * @function_id: Identifies the function of the device hosting the TDI
+ *   15:0: @rid: Requester ID
+ *   23:16: @rseg: Requester Segment (Reserved if Requester Segment Valid is Clear)
+ *   24: @rseg_valid: Requester Segment Valid
+ *   31:25 – Reserved
+ * 8B - Reserved
+ */
+struct tdisp_interface_id {
+	u32 function_id; /* TSM_TDISP_IID_xxxx */
+	u8 reserved[8];
+} __packed;
+
+#define TSM_TDISP_IID_REQUESTER_ID	GENMASK(15, 0)
+#define TSM_TDISP_IID_RSEG		GENMASK(23, 16)
+#define TSM_TDISP_IID_RSEG_VALID	BIT(24)
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
+	u16 interface_info; /* TSM_TDI_REPORT_xxx */
+	u16 reserved2;
+	u16 msi_x_message_control;
+	u16 lnr_control;
+	u32 tph_control;
+	u32 mmio_range_count;
+} __packed;
+
+#define _BITSH(x)	(1 << (x))
+#define TSM_TDI_REPORT_NO_FW_UPDATE	_BITSH(0)  /* not updates in CONFIG_LOCKED or RUN */
+#define TSM_TDI_REPORT_DMA_NO_PASID	_BITSH(1)  /* TDI generates DMA requests without PASID */
+#define TSM_TDI_REPORT_DMA_PASID	_BITSH(2)  /* TDI generates DMA requests with PASID */
+#define TSM_TDI_REPORT_ATS		_BITSH(3)  /* ATS supported and enabled for the TDI */
+#define TSM_TDI_REPORT_PRS		_BITSH(4)  /* PRS supported and enabled for the TDI */
+
+/*
+ * Each MMIO Range of the TDI is reported with the MMIO reporting offset added.
+ * Base and size in units of 4K pages
+ */
+struct tdi_report_mmio_range {
+	u64 first_page; /* First 4K page with offset added */
+	u32 num;	/* Number of 4K pages in this range */
+	u32 range_attributes; /* TSM_TDI_REPORT_MMIO_xxx */
+} __packed;
+
+#define TSM_TDI_REPORT_MMIO_MSIX_TABLE		BIT(0)
+#define TSM_TDI_REPORT_MMIO_PBA			BIT(1)
+#define TSM_TDI_REPORT_MMIO_IS_NON_TEE		BIT(2)
+#define TSM_TDI_REPORT_MMIO_IS_UPDATABLE	BIT(3)
+#define TSM_TDI_REPORT_MMIO_RESERVED		GENMASK(15, 4)
+#define TSM_TDI_REPORT_MMIO_RANGE_ID		GENMASK(31, 16)
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
+struct tsm_bus_ops;
+
+/* Physical device descriptor responsible for IDE/TDISP setup */
+struct tsm_dev {
+	const struct attribute_group *ag;
+	struct device *physdev; /* Physical PCI function #0 */
+	struct device dev; /* A child device of PCI function #0 */
+	struct tsm_spdm spdm;
+	struct mutex spdm_mutex;
+
+	u8 cert_slot;
+	u8 connected;
+	unsigned int bound;
+
+	struct tsm_blob *meas;
+	struct tsm_blob *certs;
+#define TSM_MAX_NONCE_LEN	64
+	u8 nonce[TSM_MAX_NONCE_LEN];
+	size_t nonce_len;
+
+	void *data; /* Platform specific data */
+
+	struct tsm_subsys *tsm;
+	struct tsm_bus_subsys *tsm_bus;
+	/* Bus specific data follow this struct, see tsm_dev_to_bdata */
+};
+
+#define tsm_dev_to_bdata(tdev)	((tdev)?((void *)&(tdev)[1]):NULL)
+
+/* PCI function for passing through, can be the same as tsm_dev::pdev */
+struct tsm_tdi {
+	const struct attribute_group *ag;
+	struct device dev; /* A child device of PCI VF */
+	struct list_head node;
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
+	struct kvm *kvm;
+	u16 guest_rid; /* BDFn of PCI Fn in the VM (when PCI TDISP) */
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
+	TSM_SPDM_ALGOS_DHE_SECP256R1,
+	TSM_SPDM_ALGOS_DHE_SECP384R1,
+	TSM_SPDM_ALGOS_AEAD_AES_128_GCM,
+	TSM_SPDM_ALGOS_AEAD_AES_256_GCM,
+	TSM_SPDM_ALGOS_ASYM_TPM_ALG_RSASSA_3072,
+	TSM_SPDM_ALGOS_ASYM_TPM_ALG_ECDSA_ECC_NIST_P256,
+	TSM_SPDM_ALGOS_ASYM_TPM_ALG_ECDSA_ECC_NIST_P384,
+	TSM_SPDM_ALGOS_HASH_TPM_ALG_SHA_256,
+	TSM_SPDM_ALGOS_HASH_TPM_ALG_SHA_384,
+	TSM_SPDM_ALGOS_KEY_SCHED_SPDM_KEY_SCHEDULE,
+};
+
+enum tsm_tdisp_state {
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
+	u64 spdm_algos; /* Bitmask of TSM_SPDM_ALGOS */
+	u8 certs_digest[48];
+	u8 meas_digest[48];
+	u8 interface_report_digest[48];
+	u64 intf_report_counter;
+	struct tdisp_interface_id id;
+	enum tsm_tdisp_state state;
+};
+
+struct tsm_bus_ops {
+	int (*spdm_forward)(struct tsm_spdm *spdm, u8 type);
+};
+
+struct tsm_bus_subsys {
+	struct tsm_bus_ops *ops;
+	struct notifier_block notifier;
+	struct tsm_subsys *tsm;
+};
+
+struct tsm_bus_subsys *pci_tsm_register(struct tsm_subsys *tsm_subsys);
+void pci_tsm_unregister(struct tsm_bus_subsys *subsys);
+
+/* tsm_hv_ops return codes for SPDM bouncing, when requested by the TSM */
+#define TSM_PROTO_CMA_SPDM		1
+#define TSM_PROTO_SECURED_CMA_SPDM	2
+
+struct tsm_hv_ops {
+	int (*dev_connect)(struct tsm_dev *tdev, void *private_data);
+	int (*dev_disconnect)(struct tsm_dev *tdev);
+	int (*dev_status)(struct tsm_dev *tdev, struct tsm_dev_status *s);
+	int (*dev_measurements)(struct tsm_dev *tdev);
+	int (*tdi_bind)(struct tsm_tdi *tdi, u32 bdfn, u64 vmid);
+	int (*tdi_unbind)(struct tsm_tdi *tdi);
+	int (*guest_request)(struct tsm_tdi *tdi, u8 __user *req, size_t reqlen,
+			     u8 __user *rsp, size_t rsplen, int *fw_err);
+	int (*tdi_status)(struct tsm_tdi *tdi, struct tsm_tdi_status *ts);
+};
+
+struct tsm_subsys {
+	struct device dev;
+	struct list_head tdi_head;
+	struct mutex lock;
+	const struct attribute_group *tdev_groups[3]; /* Common, host/guest, NULL */
+	const struct attribute_group *tdi_groups[3]; /* Common, host/guest, NULL */
+	int (*update_measurements)(struct tsm_dev *tdev);
+};
+
+struct tsm_subsys *tsm_register(struct device *parent, size_t extra,
+				const struct attribute_group *tdev_ag,
+				const struct attribute_group *tdi_ag,
+				int (*update_measurements)(struct tsm_dev *tdev));
+void tsm_unregister(struct tsm_subsys *subsys);
+
+struct tsm_host_subsys;
+struct tsm_host_subsys *tsm_host_register(struct device *parent,
+					  struct tsm_hv_ops *hvops,
+					  void *private_data);
+struct tsm_dev *tsm_dev_get(struct device *dev);
+void tsm_dev_put(struct tsm_dev *tdev);
+struct tsm_tdi *tsm_tdi_get(struct device *dev);
+void tsm_tdi_put(struct tsm_tdi *tdi);
+
+struct pci_dev;
+int pci_dev_tdi_validate(struct pci_dev *pdev, bool invalidate);
+int pci_dev_tdi_mmio_config(struct pci_dev *pdev, u32 range_id, bool tee);
+
+int tsm_dev_init(struct tsm_bus_subsys *tsm_bus, struct device *parent,
+		 size_t busdatalen, struct tsm_dev **ptdev);
+void tsm_dev_free(struct tsm_dev *tdev);
+int tsm_tdi_init(struct tsm_dev *tdev, struct device *dev);
+void tsm_tdi_free(struct tsm_tdi *tdi);
+
+/* IOMMUFD vIOMMU helpers */
+int tsm_tdi_bind(struct tsm_tdi *tdi, u32 guest_rid, int kvmfd);
+void tsm_tdi_unbind(struct tsm_tdi *tdi);
+int tsm_guest_request(struct tsm_tdi *tdi, u8 __user *req, size_t reqlen,
+		      u8 __user *res, size_t reslen, int *fw_err);
+
+/* Debug */
+ssize_t tsm_report_gen(struct tsm_blob *report, char *b, size_t len);
+
+/* IDE */
+int tsm_create_link(struct tsm_subsys *tsm, struct device *dev, const char *name);
+void tsm_remove_link(struct tsm_subsys *tsm, const char *name);
+#define tsm_register_ide_stream(tdev, ide) \
+	tsm_create_link((tdev)->tsm, &(tdev)->dev, (ide)->name)
+#define tsm_unregister_ide_stream(tdev, ide) \
+	tsm_remove_link((tdev)->tsm, (ide)->name)
+
 #endif /* __TSM_H */
diff --git a/drivers/virt/coco/host/tsm-host.c b/drivers/virt/coco/host/tsm-host.c
new file mode 100644
index 000000000000..80f3315fb195
--- /dev/null
+++ b/drivers/virt/coco/host/tsm-host.c
@@ -0,0 +1,552 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include <linux/module.h>
+#include <linux/tsm.h>
+#include <linux/file.h>
+#include <linux/kvm_host.h>
+
+#define DRIVER_VERSION	"0.1"
+#define DRIVER_AUTHOR	"aik@amd.com"
+#define DRIVER_DESC	"TSM host library"
+
+struct tsm_host_subsys {
+	struct tsm_subsys base;
+	struct tsm_hv_ops *ops;
+	void *private_data;
+};
+
+static int tsm_dev_connect(struct tsm_dev *tdev)
+{
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	int ret;
+
+	if (WARN_ON(!hsubsys->ops->dev_connect))
+		return -EPERM;
+
+	if (WARN_ON(!tdev->tsm_bus))
+		return -EPERM;
+
+	mutex_lock(&tdev->spdm_mutex);
+	while (1) {
+		ret = hsubsys->ops->dev_connect(tdev, hsubsys->private_data);
+		if (ret <= 0)
+			break;
+
+		ret = tdev->tsm_bus->ops->spdm_forward(&tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	tdev->connected = (ret == 0);
+
+	return ret;
+}
+
+static int tsm_dev_reclaim(struct tsm_dev *tdev)
+{
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	int ret;
+
+	if (WARN_ON(!hsubsys->ops->dev_disconnect))
+		return -EPERM;
+
+	/* Do not disconnect with active TDIs */
+	if (tdev->bound)
+		return -EBUSY;
+
+	mutex_lock(&tdev->spdm_mutex);
+	while (1) {
+		ret = hsubsys->ops->dev_disconnect(tdev);
+		if (ret <= 0)
+			break;
+
+		ret = tdev->tsm_bus->ops->spdm_forward(&tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	if (!ret)
+		tdev->connected = false;
+
+	return ret;
+}
+
+static int tsm_dev_status(struct tsm_dev *tdev, struct tsm_dev_status *s)
+{
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+
+	if (WARN_ON(!hsubsys->ops->dev_status))
+		return -EPERM;
+
+	return hsubsys->ops->dev_status(tdev, s);
+}
+
+static int tsm_tdi_measurements_locked(struct tsm_dev *tdev)
+{
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	int ret;
+
+	while (1) {
+		ret = hsubsys->ops->dev_measurements(tdev);
+		if (ret <= 0)
+			break;
+
+		ret = tdev->tsm_bus->ops->spdm_forward(&tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+
+	return ret;
+}
+
+static void tsm_tdi_reclaim(struct tsm_tdi *tdi)
+{
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	int ret;
+
+	if (WARN_ON(!hsubsys->ops->tdi_unbind))
+		return;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = hsubsys->ops->tdi_unbind(tdi);
+		if (ret <= 0)
+			break;
+
+		ret = tdi->tdev->tsm_bus->ops->spdm_forward(&tdi->tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+}
+
+static int tsm_tdi_status(struct tsm_tdi *tdi, void *private_data, struct tsm_tdi_status *ts)
+{
+	struct tsm_tdi_status tstmp = { 0 };
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	int ret;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = hsubsys->ops->tdi_status(tdi, &tstmp);
+		if (ret <= 0)
+			break;
+
+		ret = tdi->tdev->tsm_bus->ops->spdm_forward(&tdi->tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	if (!ret)
+		*ts = tstmp;
+
+	return ret;
+}
+
+static ssize_t tsm_cert_slot_store(struct device *dev, struct device_attribute *attr,
+				   const char *buf, size_t count)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	ssize_t ret = count;
+	unsigned long val;
+
+	if (kstrtoul(buf, 0, &val) < 0)
+		ret = -EINVAL;
+	else
+		tdev->cert_slot = val;
+
+	return ret;
+}
+
+static ssize_t tsm_cert_slot_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	ssize_t ret = sysfs_emit(buf, "%u\n", tdev->cert_slot);
+
+	return ret;
+}
+
+static DEVICE_ATTR_RW(tsm_cert_slot);
+
+static ssize_t tsm_dev_connect_store(struct device *dev, struct device_attribute *attr,
+				     const char *buf, size_t count)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	unsigned long val;
+	ssize_t ret = -EIO;
+
+	if (kstrtoul(buf, 0, &val) < 0)
+		ret = -EINVAL;
+	else if (val && !tdev->connected)
+		ret = tsm_dev_connect(tdev);
+	else if (!val && tdev->connected)
+		ret = tsm_dev_reclaim(tdev);
+
+	if (!ret)
+		ret = count;
+
+	return ret;
+}
+
+static ssize_t tsm_dev_connect_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	ssize_t ret = sysfs_emit(buf, "%u\n", tdev->connected);
+
+	return ret;
+}
+
+static DEVICE_ATTR_RW(tsm_dev_connect);
+
+static ssize_t tsm_dev_status_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	struct tsm_dev_status s = { 0 };
+	int ret = tsm_dev_status(tdev, &s);
+	ssize_t ret1;
+
+	ret1 = sysfs_emit(buf, "ret=%d\n"
+			  "ctx_state=%x\n"
+			  "tc_mask=%x\n"
+			  "certs_slot=%x\n"
+			  "device_id=%x:%x.%d\n"
+			  "segment_id=%x\n"
+			  "no_fw_update=%x\n",
+			  ret,
+			  s.ctx_state,
+			  s.tc_mask,
+			  s.certs_slot,
+			  (s.device_id >> 8) & 0xff,
+			  (s.device_id >> 3) & 0x1f,
+			  s.device_id & 0x07,
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
+	&dev_attr_tsm_dev_connect.attr,
+	&dev_attr_tsm_dev_status.attr,
+	NULL,
+};
+static const struct attribute_group host_dev_group = {
+	.attrs = host_dev_attrs,
+};
+
+static ssize_t tsm_tdi_bind_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+
+	if (!tdi->kvm)
+		return sysfs_emit(buf, "not bound\n");
+
+	return sysfs_emit(buf, "VM=%p BDFn=%x:%x.%d\n",
+			  tdi->kvm,
+			  (tdi->guest_rid >> 8) & 0xff,
+			  (tdi->guest_rid >> 3) & 0x1f,
+			  tdi->guest_rid & 0x07);
+}
+
+static DEVICE_ATTR_RO(tsm_tdi_bind);
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
+static ssize_t tsm_tdi_status_user_show(struct device *dev,
+					struct device_attribute *attr,
+					char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	struct tsm_tdi_status ts = { 0 };
+	char algos[256] = "";
+	unsigned int n, m;
+	int ret;
+
+	ret = tsm_tdi_status(tdi, hsubsys->private_data, &ts);
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
+		     "report_counter=%lld\n"
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
+		     ts.spdm_algos, spdm_algos_to_str(ts.spdm_algos, algos, sizeof(algos) - 1),
+		     ts.intf_report_counter);
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
+static DEVICE_ATTR_RO(tsm_tdi_status_user);
+
+static ssize_t tsm_tdi_status_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	struct tsm_tdi_status ts = { 0 };
+	u8 state;
+	int ret;
+
+	ret = tsm_tdi_status(tdi, hsubsys->private_data, &ts);
+	if (ret)
+		return ret;
+
+	state = ts.state;
+	memcpy(buf, &state, sizeof(state));
+
+	return sizeof(state);
+}
+
+static DEVICE_ATTR_RO(tsm_tdi_status);
+
+static struct attribute *host_tdi_attrs[] = {
+	&dev_attr_tsm_tdi_bind.attr,
+	&dev_attr_tsm_tdi_status_user.attr,
+	&dev_attr_tsm_tdi_status.attr,
+	NULL,
+};
+
+static const struct attribute_group host_tdi_group = {
+	.attrs = host_tdi_attrs,
+};
+
+int tsm_tdi_bind(struct tsm_tdi *tdi, u32 guest_rid, int kvmfd)
+{
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	struct fd f = fdget(kvmfd);
+	struct kvm *kvm;
+	u64 vmid;
+	int ret;
+
+	if (!fd_file(f))
+		return -EBADF;
+
+	if (!file_is_kvm(fd_file(f))) {
+		ret = -EBADF;
+		goto out_fput;
+	}
+
+	kvm = fd_file(f)->private_data;
+	if (!kvm || !kvm_get_kvm_safe(kvm)) {
+		ret = -EFAULT;
+		goto out_fput;
+	}
+
+	vmid = kvm_arch_tsm_get_vmid(kvm);
+	if (!vmid) {
+		ret = -EFAULT;
+		goto out_kvm_put;
+	}
+
+	if (WARN_ON(!hsubsys->ops->tdi_bind)) {
+		ret = -EPERM;
+		goto out_kvm_put;
+	}
+
+	if (!tdev->connected) {
+		ret = -EIO;
+		goto out_kvm_put;
+	}
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = hsubsys->ops->tdi_bind(tdi, guest_rid, vmid);
+		if (ret < 0)
+			break;
+
+		if (!ret)
+			break;
+
+		ret = tdi->tdev->tsm_bus->ops->spdm_forward(&tdi->tdev->spdm, ret);
+		if (ret < 0)
+			break;
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	if (ret) {
+		tsm_tdi_unbind(tdi);
+		goto out_kvm_put;
+	}
+
+	tdi->guest_rid = guest_rid;
+	tdi->kvm = kvm;
+	++tdi->tdev->bound;
+	goto out_fput;
+
+out_kvm_put:
+	kvm_put_kvm(kvm);
+out_fput:
+	fdput(f);
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_bind);
+
+void tsm_tdi_unbind(struct tsm_tdi *tdi)
+{
+	if (tdi->kvm) {
+		tsm_tdi_reclaim(tdi);
+		--tdi->tdev->bound;
+		kvm_put_kvm(tdi->kvm);
+		tdi->kvm = NULL;
+	}
+
+	tdi->guest_rid = 0;
+	tdi->dev.parent->tdi_enabled = false;
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_unbind);
+
+int tsm_guest_request(struct tsm_tdi *tdi, u8 __user *req, size_t reqlen,
+		      u8 __user *res, size_t reslen, int *fw_err)
+{
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_host_subsys *hsubsys = (struct tsm_host_subsys *) tdev->tsm;
+	int ret;
+
+	if (!hsubsys->ops->guest_request)
+		return -EPERM;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	while (1) {
+		ret = hsubsys->ops->guest_request(tdi, req, reqlen,
+						  res, reslen, fw_err);
+		if (ret <= 0)
+			break;
+
+		ret = tdi->tdev->tsm_bus->ops->spdm_forward(&tdi->tdev->spdm,
+							    ret);
+		if (ret < 0)
+			break;
+	}
+
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tsm_guest_request);
+
+struct tsm_host_subsys *tsm_host_register(struct device *parent,
+					  struct tsm_hv_ops *hvops,
+					  void *private_data)
+{
+	struct tsm_subsys *subsys = tsm_register(parent, sizeof(struct tsm_host_subsys),
+						 &host_dev_group, &host_tdi_group,
+						 tsm_tdi_measurements_locked);
+	struct tsm_host_subsys *hsubsys;
+
+	hsubsys = (struct tsm_host_subsys *) subsys;
+
+	if (IS_ERR(hsubsys))
+		return hsubsys;
+
+	hsubsys->ops = hvops;
+	hsubsys->private_data = private_data;
+
+	return hsubsys;
+}
+EXPORT_SYMBOL_GPL(tsm_host_register);
+
+static int __init tsm_init(void)
+{
+	int ret = 0;
+
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION "\n");
+
+	return ret;
+}
+
+static void __exit tsm_exit(void)
+{
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION " shutdown\n");
+}
+
+module_init(tsm_init);
+module_exit(tsm_exit);
+
+MODULE_VERSION(DRIVER_VERSION);
+MODULE_LICENSE("GPL");
+MODULE_AUTHOR(DRIVER_AUTHOR);
+MODULE_DESCRIPTION(DRIVER_DESC);
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
new file mode 100644
index 000000000000..b6235d1210ca
--- /dev/null
+++ b/drivers/virt/coco/tsm.c
@@ -0,0 +1,636 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include <linux/module.h>
+#include <linux/tsm.h>
+
+#define DRIVER_VERSION	"0.1"
+#define DRIVER_AUTHOR	"aik@amd.com"
+#define DRIVER_DESC	"TSM library"
+
+static struct class *tsm_class, *tdev_class, *tdi_class;
+
+/* snprintf does not check for the size, hence this wrapper */
+static int tsmprint(char *buf, size_t size, const char *fmt, ...)
+{
+	va_list args;
+	size_t i;
+
+	if (!size)
+		return 0;
+
+	va_start(args, fmt);
+	i = vsnprintf(buf, size, fmt, args);
+	va_end(args);
+
+	return min(i, size);
+}
+
+struct tsm_blob *tsm_blob_new(void *data, size_t len)
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
+	memcpy(b->data, data, len);
+
+	return b;
+}
+EXPORT_SYMBOL_GPL(tsm_blob_new);
+
+static int match_class(struct device *dev, const void *data)
+{
+	return dev->class == data;
+}
+
+struct tsm_dev *tsm_dev_get(struct device *parent)
+{
+	struct device *dev = device_find_child(parent, tdev_class, match_class);
+
+	if (!dev) {
+		dev = device_find_child(parent, tdi_class, match_class);
+		if (dev) {
+			struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+
+			dev = &tdi->tdev->dev;
+		}
+	}
+
+	if (!dev)
+		return NULL;
+
+	/* device_find_child() does get_device() */
+	return container_of(dev, struct tsm_dev, dev);
+}
+EXPORT_SYMBOL_GPL(tsm_dev_get);
+
+void tsm_dev_put(struct tsm_dev *tdev)
+{
+	put_device(&tdev->dev);
+}
+EXPORT_SYMBOL_GPL(tsm_dev_put);
+
+struct tsm_tdi *tsm_tdi_get(struct device *parent)
+{
+	struct device *dev = device_find_child(parent, tdi_class, match_class);
+
+	if (!dev)
+		return NULL;
+
+	/* device_find_child() does get_device() */
+	return container_of(dev, struct tsm_tdi, dev);
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_get);
+
+void tsm_tdi_put(struct tsm_tdi *tdi)
+{
+	put_device(&tdi->dev);
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_put);
+
+static ssize_t blob_show(struct tsm_blob *blob, char *buf)
+{
+	unsigned int n, m;
+	size_t sz = PAGE_SIZE - 1;
+
+	if (!blob)
+		return sysfs_emit(buf, "none\n");
+
+	n = tsmprint(buf, sz, "%lu %u\n", blob->len);
+	m = hex_dump_to_buffer(blob->data, blob->len, 32, 1,
+			       buf + n, sz - n, false);
+	n += min(sz - n, m);
+	n += tsmprint(buf + n, sz - n, "...\n");
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
+		n += tsmprint(buf + n, len - n, "[%d] len=%d:\n", i, h->length);
+
+		for (o2 = 0, p = (u8 *)&h[1]; o2 < h->length; o2 += 32) {
+			m = hex_dump_to_buffer(p + o2, h->length - o2, 32, 1,
+					       buf + n, len - n, true);
+			n += min(len - n, m);
+			n += tsmprint(buf + n, len - n, "\n");
+		}
+
+		off += h->length; /* Includes the header */
+	}
+
+	return n;
+}
+
+static ssize_t tsm_certs_user_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	ssize_t n;
+
+	mutex_lock(&tdev->spdm_mutex);
+	if (!tdev->certs) {
+		n = sysfs_emit(buf, "none\n");
+	} else {
+		n = tsm_certs_gen(tdev->certs, buf, PAGE_SIZE - 1);
+		if (!n)
+			n = blob_show(tdev->certs, buf);
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_certs_user);
+
+static ssize_t tsm_certs_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	ssize_t n = 0;
+
+	mutex_lock(&tdev->spdm_mutex);
+	if (tdev->certs) {
+		n = min(PAGE_SIZE, tdev->certs->len);
+		memcpy(buf, tdev->certs->data, n);
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
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
+	unsigned int n, m, off, what;
+	bool dmtf;
+
+	n = tsmprint(buf, len, "Len=%d\n", meas->len);
+	for (off = 0; off < meas->len; ) {
+		mb = (struct spdm_measurement_block_header *)(((u8 *) meas->data) + off);
+		dmtf = mb->spec & 1;
+
+		n += tsmprint(buf + n, len - n, "#%d (%d) ", mb->index, mb->size);
+		if (dmtf) {
+			h = (void *) &mb[1];
+
+			if (WARN_ON_ONCE(mb->size != (sizeof(*h) + h->size)))
+				return -EINVAL;
+
+			what = h->type & 0x7F;
+			n += tsmprint(buf + n, len - n, "%x=[%s %s]: ",
+				h->type,
+				h->type & 0x80 ? "digest" : "raw",
+				what < ARRAY_SIZE(whats) ? whats[what] : "reserved");
+
+			if (what == 5) {
+				dm = (struct dmtf_measurement_block_device_mode *) &h[1];
+				n += tsmprint(buf + n, len - n, " %x %x %x %x",
+					      dm->opmode_cap, dm->opmode_sta,
+					      dm->devmode_cap, dm->devmode_sta);
+			} else {
+				m = hex_dump_to_buffer(&h[1], h->size, 32, 1,
+						       buf + n, len - n, false);
+				n += min(len - n, m);
+			}
+		} else {
+			n += tsmprint(buf + n, len - n, "spec=%x: ", mb->spec);
+			m = hex_dump_to_buffer(&mb[1], min(len - off, mb->size),
+					       32, 1, buf + n, len - n, false);
+			n += min(len - n, m);
+		}
+
+		off += sizeof(*mb) + mb->size;
+		n += tsmprint(buf + n, len - n, "...\n");
+	}
+
+	return n;
+}
+
+static ssize_t tsm_meas_user_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	ssize_t n;
+
+	mutex_lock(&tdev->spdm_mutex);
+	n = tdev->tsm->update_measurements(tdev);
+
+	if (!tdev->meas || n) {
+		n = sysfs_emit(buf, "none\n");
+	} else {
+		n = tsm_meas_gen(tdev->meas, buf, PAGE_SIZE);
+		if (!n)
+			n = blob_show(tdev->meas, buf);
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_meas_user);
+
+static ssize_t tsm_meas_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = container_of(dev, struct tsm_dev, dev);
+	ssize_t n = 0;
+
+	mutex_lock(&tdev->spdm_mutex);
+	n = tdev->tsm->update_measurements(tdev);
+	if (!n && tdev->meas) {
+		n = MIN(PAGE_SIZE, tdev->meas->len);
+		memcpy(buf, tdev->meas->data, n);
+	}
+	mutex_unlock(&tdev->spdm_mutex);
+
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_meas);
+
+static ssize_t tsm_nonce_store(struct device *dev, struct device_attribute *attr,
+			       const char *buf, size_t count)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+
+	if (!tdev)
+		return -EFAULT;
+
+	tdev->nonce_len = min(count, sizeof(tdev->nonce));
+	mutex_lock(&tdev->spdm_mutex);
+	memcpy(tdev->nonce, buf, tdev->nonce_len);
+	mutex_unlock(&tdev->spdm_mutex);
+	tsm_dev_put(tdev);
+
+	return tdev->nonce_len;
+}
+
+static ssize_t tsm_nonce_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_dev *tdev = tsm_dev_get(dev);
+
+	if (!tdev)
+		return -EFAULT;
+
+	mutex_lock(&tdev->spdm_mutex);
+	memcpy(buf, tdev->nonce, tdev->nonce_len);
+	mutex_unlock(&tdev->spdm_mutex);
+	tsm_dev_put(tdev);
+
+	return tdev->nonce_len;
+}
+
+static DEVICE_ATTR_RW(tsm_nonce);
+
+static struct attribute *dev_attrs[] = {
+	&dev_attr_tsm_certs_user.attr,
+	&dev_attr_tsm_meas_user.attr,
+	&dev_attr_tsm_certs.attr,
+	&dev_attr_tsm_meas.attr,
+	&dev_attr_tsm_nonce.attr,
+	NULL,
+};
+static const struct attribute_group dev_group = {
+	.attrs = dev_attrs,
+};
+
+
+ssize_t tsm_report_gen(struct tsm_blob *report, char *buf, size_t len)
+{
+	struct tdi_report_header *h = TDI_REPORT_HDR(report);
+	struct tdi_report_mmio_range *mr = TDI_REPORT_MR_OFF(report);
+	struct tdi_report_footer *f = TDI_REPORT_FTR(report);
+	unsigned int n, m, i;
+
+	n = tsmprint(buf, len,
+		     "no_fw_update=%u\ndma_no_pasid=%u\ndma_pasid=%u\nats=%u\nprs=%u\n",
+		     FIELD_GET(TSM_TDI_REPORT_NO_FW_UPDATE, h->interface_info),
+		     FIELD_GET(TSM_TDI_REPORT_DMA_NO_PASID, h->interface_info),
+		     FIELD_GET(TSM_TDI_REPORT_DMA_PASID, h->interface_info),
+		     FIELD_GET(TSM_TDI_REPORT_ATS,  h->interface_info),
+		     FIELD_GET(TSM_TDI_REPORT_PRS, h->interface_info));
+	n += tsmprint(buf + n, len - n,
+		      "msi_x_message_control=%#04x\nlnr_control=%#04x\n",
+		      h->msi_x_message_control, h->lnr_control);
+	n += tsmprint(buf + n, len - n, "tph_control=%#08x\n", h->tph_control);
+
+	for (i = 0; i < h->mmio_range_count; ++i) {
+#define FIELD_CH(m, r) (FIELD_GET((m), (r)) ? '+':'-')
+		n += tsmprint(buf + n, len - n,
+			      "[%i] #%lu %#016llx +%#lx MSIX%c PBA%c NonTEE%c Upd%c\n",
+			      i,
+			      FIELD_GET(TSM_TDI_REPORT_MMIO_RANGE_ID, mr[i].range_attributes),
+			      mr[i].first_page << PAGE_SHIFT,
+			      (unsigned long) mr[i].num << PAGE_SHIFT,
+			      FIELD_CH(TSM_TDI_REPORT_MMIO_MSIX_TABLE, mr[i].range_attributes),
+			      FIELD_CH(TSM_TDI_REPORT_MMIO_PBA, mr[i].range_attributes),
+			      FIELD_CH(TSM_TDI_REPORT_MMIO_IS_NON_TEE, mr[i].range_attributes),
+			      FIELD_CH(TSM_TDI_REPORT_MMIO_IS_UPDATABLE, mr[i].range_attributes));
+
+		if (FIELD_GET(TSM_TDI_REPORT_MMIO_RESERVED, mr[i].range_attributes))
+			n += tsmprint(buf + n, len - n,
+				      "[%i] WARN: reserved=%#x\n", i, mr[i].range_attributes);
+	}
+
+	if (f->device_specific_info_len) {
+		unsigned int num = report->len - ((u8 *)f->device_specific_info - (u8 *)h);
+
+		num = min(num, f->device_specific_info_len);
+		n += tsmprint(buf + n, len - n, "DevSp len=%d%s",
+			f->device_specific_info_len, num ? ": " : "");
+		m = hex_dump_to_buffer(f->device_specific_info, num, 32, 1,
+				       buf + n, len - n, false);
+		n += min(len - n, m);
+		n += tsmprint(buf + n, len - n, m ? "\n" : "...\n");
+	}
+
+	return n;
+}
+EXPORT_SYMBOL_GPL(tsm_report_gen);
+
+static ssize_t tsm_report_user_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+	ssize_t n;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	if (!tdi->report) {
+		n = sysfs_emit(buf, "none\n");
+	} else {
+		n = tsm_report_gen(tdi->report, buf, PAGE_SIZE - 1);
+		if (!n)
+			n = blob_show(tdi->report, buf);
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	return n;
+}
+
+static DEVICE_ATTR_RO(tsm_report_user);
+
+static ssize_t tsm_report_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+	ssize_t n = 0;
+
+	mutex_lock(&tdi->tdev->spdm_mutex);
+	if (tdi->report) {
+		n = min(PAGE_SIZE, tdi->report->len);
+		memcpy(buf, tdi->report->data, n);
+	}
+	mutex_unlock(&tdi->tdev->spdm_mutex);
+
+	return n;
+}
+static DEVICE_ATTR_RO(tsm_report);
+
+static struct attribute *tdi_attrs[] = {
+	&dev_attr_tsm_report_user.attr,
+	&dev_attr_tsm_report.attr,
+	NULL,
+};
+
+static const struct attribute_group tdi_group = {
+	.attrs = tdi_attrs,
+};
+
+int tsm_tdi_init(struct tsm_dev *tdev, struct device *parent)
+{
+	struct tsm_tdi *tdi;
+	struct device *dev;
+	int ret = 0;
+
+	dev_info(parent, "Initializing tdi\n");
+	if (!tdev)
+		return -ENODEV;
+
+	tdi = kzalloc(sizeof(*tdi), GFP_KERNEL);
+	if (!tdi)
+		return -ENOMEM;
+
+	dev = &tdi->dev;
+	dev->groups = tdev->tsm->tdi_groups;
+	dev->parent = parent;
+	dev->class = tdi_class;
+	dev_set_name(dev, "tdi:%s", dev_name(parent));
+	device_initialize(dev);
+	ret = device_add(dev);
+	if (ret)
+		return ret;
+
+	ret = sysfs_create_link(&parent->kobj, &tdev->dev.kobj, "tsm_dev");
+	if (ret)
+		goto free_exit;
+
+	tdi->tdev = tdev;
+
+	return 0;
+
+free_exit:
+	kfree(tdi);
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_init);
+
+void tsm_tdi_free(struct tsm_tdi *tdi)
+{
+	struct device *parent = tdi->dev.parent;
+
+	dev_notice(&tdi->dev, "Freeing tdi\n");
+	sysfs_remove_link(&parent->kobj, "tsm_dev");
+	device_unregister(&tdi->dev);
+}
+EXPORT_SYMBOL_GPL(tsm_tdi_free);
+
+int tsm_dev_init(struct tsm_bus_subsys *tsm_bus, struct device *parent,
+		 size_t busdatalen, struct tsm_dev **ptdev)
+{
+	struct tsm_dev *tdev;
+	struct device *dev;
+	int ret = 0;
+
+	dev_info(parent, "Initializing tdev\n");
+	tdev = kzalloc(sizeof(*tdev) + busdatalen, GFP_KERNEL);
+	if (!tdev)
+		return -ENOMEM;
+
+	tdev->physdev = get_device(parent);
+	mutex_init(&tdev->spdm_mutex);
+
+	tdev->tsm = tsm_bus->tsm;
+	tdev->tsm_bus = tsm_bus;
+
+	dev = &tdev->dev;
+	dev->groups = tdev->tsm->tdev_groups;
+	dev->parent = parent;
+	dev->class = tdev_class;
+	dev_set_name(dev, "tdev:%s", dev_name(parent));
+	device_initialize(dev);
+	ret = device_add(dev);
+
+	get_device(dev);
+	*ptdev = tdev;
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_dev_init);
+
+void tsm_dev_free(struct tsm_dev *tdev)
+{
+	dev_notice(&tdev->dev, "Freeing tdevice\n");
+	device_unregister(&tdev->dev);
+}
+EXPORT_SYMBOL_GPL(tsm_dev_free);
+
+int tsm_create_link(struct tsm_subsys *tsm, struct device *dev, const char *name)
+{
+	return sysfs_create_link(&tsm->dev.kobj, &dev->kobj, name);
+}
+EXPORT_SYMBOL_GPL(tsm_create_link);
+
+void tsm_remove_link(struct tsm_subsys *tsm, const char *name)
+{
+	sysfs_remove_link(&tsm->dev.kobj, name);
+}
+EXPORT_SYMBOL_GPL(tsm_remove_link);
+
+static struct tsm_subsys *alloc_tsm_subsys(struct device *parent, size_t size)
+{
+	struct tsm_subsys *subsys;
+	struct device *dev;
+
+	if (WARN_ON_ONCE(size < sizeof(*subsys)))
+		return ERR_PTR(-EINVAL);
+
+	subsys = kzalloc(size, GFP_KERNEL);
+	if (!subsys)
+		return ERR_PTR(-ENOMEM);
+
+	dev = &subsys->dev;
+	dev->parent = parent;
+	dev->class = tsm_class;
+	device_initialize(dev);
+	return subsys;
+}
+
+struct tsm_subsys *tsm_register(struct device *parent, size_t size,
+				const struct attribute_group *tdev_ag,
+				const struct attribute_group *tdi_ag,
+				int (*update_measurements)(struct tsm_dev *tdev))
+{
+	struct tsm_subsys *subsys = alloc_tsm_subsys(parent, size);
+	struct device *dev;
+	int rc;
+
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
+	subsys->tdev_groups[0] = &dev_group;
+	subsys->tdev_groups[1] = tdev_ag;
+	subsys->tdi_groups[0] = &tdi_group;
+	subsys->tdi_groups[1] = tdi_ag;
+	subsys->update_measurements = update_measurements;
+
+	return subsys;
+}
+EXPORT_SYMBOL_GPL(tsm_register);
+
+void tsm_unregister(struct tsm_subsys *subsys)
+{
+	device_unregister(&subsys->dev);
+}
+EXPORT_SYMBOL_GPL(tsm_unregister);
+
+static void tsm_release(struct device *dev)
+{
+	struct tsm_subsys *tsm = container_of(dev, typeof(*tsm), dev);
+
+	dev_info(&tsm->dev, "Releasing TSM\n");
+	kfree(tsm);
+}
+
+static void tdev_release(struct device *dev)
+{
+	struct tsm_dev *tdev = container_of(dev, typeof(*tdev), dev);
+
+	dev_info(&tdev->dev, "Releasing %s TDEV\n",
+		 tdev->connected ? "connected":"disconnected");
+	kfree(tdev);
+}
+
+static void tdi_release(struct device *dev)
+{
+	struct tsm_tdi *tdi = container_of(dev, typeof(*tdi), dev);
+
+	dev_info(&tdi->dev, "Releasing %s TDI\n", tdi->kvm ? "bound" : "unbound");
+	sysfs_remove_link(&tdi->dev.parent->kobj, "tsm_dev");
+	kfree(tdi);
+}
+
+static int __init tsm_init(void)
+{
+	int ret = 0;
+
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION "\n");
+
+	tsm_class = class_create("tsm");
+	if (IS_ERR(tsm_class))
+		return PTR_ERR(tsm_class);
+	tsm_class->dev_release = tsm_release;
+
+	tdev_class = class_create("tsm-dev");
+	if (IS_ERR(tdev_class))
+		return PTR_ERR(tdev_class);
+	tdev_class->dev_release = tdev_release;
+
+	tdi_class = class_create("tsm-tdi");
+	if (IS_ERR(tdi_class))
+		return PTR_ERR(tdi_class);
+	tdi_class->dev_release = tdi_release;
+
+	return ret;
+}
+
+static void __exit tsm_exit(void)
+{
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION " shutdown\n");
+	class_destroy(tdi_class);
+	class_destroy(tdev_class);
+	class_destroy(tsm_class);
+}
+
+module_init(tsm_init);
+module_exit(tsm_exit);
+
+MODULE_VERSION(DRIVER_VERSION);
+MODULE_LICENSE("GPL");
+MODULE_AUTHOR(DRIVER_AUTHOR);
+MODULE_DESCRIPTION(DRIVER_DESC);
diff --git a/Documentation/virt/coco/tsm.rst b/Documentation/virt/coco/tsm.rst
new file mode 100644
index 000000000000..7cb5f1862492
--- /dev/null
+++ b/Documentation/virt/coco/tsm.rst
@@ -0,0 +1,99 @@
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
+TSM modules
+===========
+
+TSM is a library, shared among hosts and guests.
+
+TSM-HOST contains host-specific bits, controls IDE and TDISP bindings.
+
+TSM-GUEST contains guest-specific bits, controls enablement of encrypted DMA and
+MMIO.
+
+TSM-PCI is PCI binding for TSM, calls the above libraries for setting up
+sysfs nodes and corresponding data structures.
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
+The sysfs example from a host with a TDISP capable device:
+
+~> find /sys -iname "*tsm*"
+/sys/class/tsm-tdi
+/sys/class/tsm
+/sys/class/tsm/tsm0
+/sys/class/tsm-dev
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.1/tsm_dev
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.1/tsm-tdi
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.1/tsm-tdi/tdi:0000:e1:00.1/tsm_tdi_bind
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.1/tsm-tdi/tdi:0000:e1:00.1/tsm_tdi_status
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.1/tsm-tdi/tdi:0000:e1:00.1/tsm_tdi_status_user
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.1/tsm-tdi/tdi:0000:e1:00.1/tsm_report_user
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.1/tsm-tdi/tdi:0000:e1:00.1/tsm_report
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm_dev
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-tdi
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-tdi/tdi:0000:e1:00.0/tsm_tdi_bind
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-tdi/tdi:0000:e1:00.0/tsm_tdi_status
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-tdi/tdi:0000:e1:00.0/tsm_tdi_status_user
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-tdi/tdi:0000:e1:00.0/tsm_report_user
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-tdi/tdi:0000:e1:00.0/tsm_report
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_certs
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_nonce
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_meas_user
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_certs_user
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_dev_status
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_cert_slot
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_dev_connect
+/sys/devices/pci0000:e0/0000:e0:01.1/0000:e1:00.0/tsm-dev/tdev:0000:e1:00.0/tsm_meas
+/sys/devices/pci0000:a0/0000:a0:07.1/0000:a9:00.5/tsm
+/sys/devices/pci0000:a0/0000:a0:07.1/0000:a9:00.5/tsm/tsm0
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
index 819a97e8ba99..e4385247440b 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -3,6 +3,18 @@
 # Confidential computing related collateral
 #
 
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
+	  This is prerequisite for host and guest support.
+
 source "drivers/virt/coco/efi_secret/Kconfig"
 
 source "drivers/virt/coco/pkvm-guest/Kconfig"
@@ -14,3 +26,5 @@ source "drivers/virt/coco/tdx-guest/Kconfig"
 source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
+
+source "drivers/virt/coco/host/Kconfig"
diff --git a/drivers/virt/coco/host/Kconfig b/drivers/virt/coco/host/Kconfig
new file mode 100644
index 000000000000..3bde38b91fd4
--- /dev/null
+++ b/drivers/virt/coco/host/Kconfig
@@ -0,0 +1,6 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# TSM (TEE Security Manager) Common infrastructure and host drivers
+#
+config TSM_HOST
+	tristate

---

## [9] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 08/22] pci/tsm: Add PCI driver for TSM*

The PCI TSM module scans the PCI bus to initialize a TSM context for
physical ("TDEV") and virtual ("TDI") functions. It also implements
bus operations which at the moment is just an SPDM bouncer which talks
to the PF's DOE mailboxes.

The purpose of this module is to keep drivers/virt/coco/(guest|host)
unaware of PCI as much as possible (which is not always the case).

This module does not add new sysfs interfaces.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/pci/Makefile          |   3 +
 include/uapi/linux/pci_regs.h |   1 +
 drivers/pci/tsm.c             | 233 ++++++++++++++++++++
 drivers/pci/Kconfig           |  15 ++
 4 files changed, 252 insertions(+)

diff --git a/drivers/pci/Makefile b/drivers/pci/Makefile
index 8050b04cc350..59d774bf9c32 100644
--- a/drivers/pci/Makefile
+++ b/drivers/pci/Makefile
@@ -43,6 +43,9 @@ obj-$(CONFIG_PCI_CMA)		+= cma.o cma.asn1.o
 $(obj)/cma.o:			$(obj)/cma.asn1.h
 $(obj)/cma.asn1.o:		$(obj)/cma.asn1.c $(obj)/cma.asn1.h
 
+tsm_pci-y			:= tsm.o
+obj-$(CONFIG_PCI_TSM)		+= tsm_pci.o
+
 # Endpoint library must be initialized before its users
 obj-$(CONFIG_PCI_ENDPOINT)	+= endpoint/
 
diff --git a/include/uapi/linux/pci_regs.h b/include/uapi/linux/pci_regs.h
index 15bd8e2b3cf5..9c4a1995da8c 100644
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
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
new file mode 100644
index 000000000000..1539db584887
--- /dev/null
+++ b/drivers/pci/tsm.c
@@ -0,0 +1,233 @@
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
+#include <linux/module.h>
+#include <linux/pci-ide.h>
+#include <linux/tsm.h>
+
+#define DRIVER_VERSION	"0.1"
+#define DRIVER_AUTHOR	"aik@amd.com"
+#define DRIVER_DESC	"TSM TDISP library"
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
+static bool is_endpoint(struct pci_dev *pdev)
+{
+	if (!pci_is_pcie(pdev))
+		return false;
+
+	if (pci_pcie_type(pdev) != PCI_EXP_TYPE_ENDPOINT)
+		return false;
+
+	return true;
+}
+
+struct tsm_pci_dev_data {
+	struct pci_doe_mb *doe_mb;
+	struct pci_doe_mb *doe_mb_sec;
+};
+
+#define tsm_dev_to_pcidata(tdev) ((struct tsm_pci_dev_data *)tsm_dev_to_bdata(tdev))
+
+static int tsm_pci_dev_spdm_forward(struct tsm_spdm *spdm, u8 type)
+{
+	struct tsm_dev *tdev = container_of(spdm, struct tsm_dev, spdm);
+	struct tsm_pci_dev_data *tdata = tsm_dev_to_pcidata(tdev);
+	struct pci_doe_mb *doe_mb;
+	int rc;
+
+	if (type == TSM_PROTO_SECURED_CMA_SPDM)
+		doe_mb = tdata->doe_mb_sec;
+	else if (type == TSM_PROTO_CMA_SPDM)
+		doe_mb = tdata->doe_mb;
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
+static struct tsm_bus_ops tsm_pci_ops = {
+	.spdm_forward = tsm_pci_dev_spdm_forward,
+};
+
+static int tsm_pci_dev_init(struct tsm_bus_subsys *tsm_bus,
+			    struct pci_dev *pdev,
+			    struct tsm_dev **ptdev)
+{
+	struct tsm_pci_dev_data *tdata;
+	int ret = tsm_dev_init(tsm_bus, &pdev->dev, sizeof(*tdata), ptdev);
+
+	if (ret)
+		return ret;
+
+	tdata = tsm_dev_to_bdata(*ptdev);
+
+	tdata->doe_mb = pci_find_doe_mailbox(pdev,
+					     PCI_VENDOR_ID_PCI_SIG,
+					     PCI_DOE_PROTOCOL_CMA_SPDM);
+	tdata->doe_mb_sec = pci_find_doe_mailbox(pdev,
+						 PCI_VENDOR_ID_PCI_SIG,
+						 PCI_DOE_PROTOCOL_SECURED_CMA_SPDM);
+
+	if (tdata->doe_mb || tdata->doe_mb_sec)
+		pci_notice(pdev, "DOE SPDM=%s SecuredSPDM=%s\n",
+			   tdata->doe_mb ? "yes":"no", tdata->doe_mb_sec ? "yes":"no");
+
+	return ret;
+}
+
+static int tsm_pci_alloc_device(struct tsm_bus_subsys *tsm_bus,
+				struct pci_dev *pdev)
+{
+	int ret = 0;
+
+	/* Set up TDIs for HV (physical functions) and VM (all functions) */
+	if ((pdev->devcap & PCI_EXP_DEVCAP_TEE) &&
+	    (((pdev->is_physfn && (PCI_FUNC(pdev->devfn) == 0)) ||
+	      (!pdev->is_physfn && !pdev->is_virtfn)))) {
+
+		struct tsm_dev *tdev = NULL;
+
+		if (!is_physical_endpoint(pdev))
+			return 0;
+
+		ret = tsm_pci_dev_init(tsm_bus, pdev, &tdev);
+		if (ret)
+			return ret;
+
+		ret = tsm_tdi_init(tdev, &pdev->dev);
+		tsm_dev_put(tdev);
+		return ret;
+	}
+
+	/* Set up TDIs for HV (virtual functions), should do nothing in VMs */
+	if (pdev->is_virtfn) {
+		struct pci_dev *pf0 = pci_get_slot(pdev->physfn->bus,
+						   pdev->physfn->devfn & ~7);
+
+		if (pf0 && (pf0->devcap & PCI_EXP_DEVCAP_TEE)) {
+			struct tsm_dev *tdev = tsm_dev_get(&pf0->dev);
+
+			if (!is_endpoint(pdev))
+				return 0;
+
+			ret = tsm_tdi_init(tdev, &pdev->dev);
+			tsm_dev_put(tdev);
+			return ret;
+		}
+	}
+
+	return 0;
+}
+
+static void tsm_pci_dev_free(struct pci_dev *pdev)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(&pdev->dev);
+
+	if (tdi) {
+		tsm_tdi_put(tdi);
+		tsm_tdi_free(tdi);
+	}
+
+	struct tsm_dev *tdev = tsm_dev_get(&pdev->dev);
+
+	if (tdev) {
+		tsm_dev_put(tdev);
+		tsm_dev_free(tdev);
+	}
+
+	WARN_ON(!tdi && tdev);
+}
+
+static int tsm_pci_bus_notifier(struct notifier_block *nb, unsigned long action, void *data)
+{
+	struct tsm_bus_subsys *tsm_bus = container_of(nb, struct tsm_bus_subsys, notifier);
+
+	switch (action) {
+	case BUS_NOTIFY_ADD_DEVICE:
+		tsm_pci_alloc_device(tsm_bus, to_pci_dev(data));
+		break;
+	case BUS_NOTIFY_DEL_DEVICE:
+		tsm_pci_dev_free(to_pci_dev(data));
+		break;
+	}
+
+	return NOTIFY_OK;
+}
+
+struct tsm_bus_subsys *pci_tsm_register(struct tsm_subsys *tsm)
+{
+	struct tsm_bus_subsys *tsm_bus = kzalloc(sizeof(*tsm_bus), GFP_KERNEL);
+	struct pci_dev *pdev = NULL;
+
+	pr_info("Scan TSM PCI\n");
+	tsm_bus->ops = &tsm_pci_ops;
+	tsm_bus->tsm = tsm;
+	tsm_bus->notifier.notifier_call = tsm_pci_bus_notifier;
+	for_each_pci_dev(pdev)
+		tsm_pci_alloc_device(tsm_bus, pdev);
+	bus_register_notifier(&pci_bus_type, &tsm_bus->notifier);
+	return tsm_bus;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_register);
+
+void pci_tsm_unregister(struct tsm_bus_subsys *subsys)
+{
+	struct pci_dev *pdev = NULL;
+
+	pr_info("Shut down TSM PCI\n");
+	bus_unregister_notifier(&pci_bus_type, &subsys->notifier);
+	for_each_pci_dev(pdev)
+		tsm_pci_dev_free(pdev);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_unregister);
+
+static int __init tsm_pci_init(void)
+{
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION "\n");
+	return 0;
+}
+
+static void __exit tsm_pci_cleanup(void)
+{
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION " unload\n");
+}
+
+module_init(tsm_pci_init);
+module_exit(tsm_pci_cleanup);
+
+MODULE_VERSION(DRIVER_VERSION);
+MODULE_LICENSE("GPL");
+MODULE_AUTHOR(DRIVER_AUTHOR);
+MODULE_DESCRIPTION(DRIVER_DESC);
diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 9212c0decdc5..9285e7511860 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -137,6 +137,21 @@ config PCI_CMA
 config PCI_IDE
 	bool
 
+config PCI_TSM
+	tristate "TEE Security Manager for PCI Device Security"
+	select PCI_IDE
+	depends on TSM
+	default m
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

---

## [10] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 09/22] crypto/ccp: Implement SEV TIO firmware interface*

On AND SEV, the AMD PSP firmware acts as TSM (manages the
security/trust). The CCP driver provides the interface to it
and registers itself in the TSM-HOST subsystem.

Implement SEV TIO PSP command wrappers in sev-dev-tio.c, these make
SPDM calls and store the data in the SEV-TIO-specific structs.

Implement TSM-HOST hooks in sev-dev-tsm.c.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/Makefile       |   13 +
 arch/x86/include/asm/sev.h        |   20 +
 drivers/crypto/ccp/sev-dev-tio.h  |  111 ++
 drivers/crypto/ccp/sev-dev.h      |   18 +
 include/linux/psp-sev.h           |   27 +
 include/uapi/linux/psp-sev.h      |    2 +
 drivers/crypto/ccp/sev-dev-tio.c  | 1664 ++++++++++++++++++++
 drivers/crypto/ccp/sev-dev-tsm.c  |  709 +++++++++
 drivers/crypto/ccp/sev-dev.c      |   10 +-
 drivers/virt/coco/host/tsm-host.c |    4 +-
 drivers/crypto/ccp/Kconfig        |    2 +
 11 files changed, 2576 insertions(+), 4 deletions(-)

diff --git a/drivers/crypto/ccp/Makefile b/drivers/crypto/ccp/Makefile
index 5ce69134ec48..8868896f3fd5 100644
--- a/drivers/crypto/ccp/Makefile
+++ b/drivers/crypto/ccp/Makefile
@@ -14,6 +14,19 @@ ccp-$(CONFIG_CRYPTO_DEV_SP_PSP) += psp-dev.o \
                                    platform-access.o \
                                    dbc.o \
                                    hsti.o
+
+ifeq ($(CONFIG_CRYPTO_DEV_SP_PSP)$(CONFIG_PCI_TSM),yy)
+ccp-y += sev-dev-tsm.o sev-dev-tio.o
+endif
+
+ifeq ($(CONFIG_CRYPTO_DEV_SP_PSP)$(CONFIG_PCI_TSM),ym)
+ccp-m += sev-dev-tsm.o sev-dev-tio.o
+endif
+
+ifeq ($(CONFIG_CRYPTO_DEV_SP_PSP)$(CONFIG_PCI_TSM),mm)
+ccp-m += sev-dev-tsm.o sev-dev-tio.o
+endif
+
 ccp-$(CONFIG_CRYPTO_DEV_SP_PSP_FW_UPLOAD) += sev-fw.o
 
 obj-$(CONFIG_CRYPTO_DEV_CCP_CRYPTO) += ccp-crypto.o
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 46a7e5d45275..c5e9455df0dc 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -146,6 +146,14 @@ enum msg_type {
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
 
 	SNP_MSG_TSC_INFO_REQ = 17,
 	SNP_MSG_TSC_INFO_RSP,
@@ -209,6 +217,18 @@ struct snp_guest_req {
 	void *data;
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
index 000000000000..98d6797fea5e
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tio.h
@@ -0,0 +1,111 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef __PSP_SEV_TIO_H__
+#define __PSP_SEV_TIO_H__
+
+#include <linux/tsm.h>
+#include <linux/pci-ide.h>
+#include <uapi/linux/psp-sev.h>
+
+#if defined(CONFIG_CRYPTO_DEV_SP_PSP) || defined(CONFIG_CRYPTO_DEV_SP_PSP_MODULE)
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
+	size_t output_len;
+	size_t scratch_len;
+	struct sla_buffer_hdr *reqbuf; /* vmap'ed @req for DOE */
+	struct sla_buffer_hdr *respbuf; /* vmap'ed @resp for DOE */
+
+	int cmd;
+	int psp_ret;
+	u8 cmd_data[SEV_TIO_MAX_COMMAND_LENGTH];
+	u8 *data_pg; /* Data page for SPDM-aware commands returning some data */
+
+	struct sev_tio_status *tio_status;
+	void *guest_req_buf;    /* Bounce buffer for TIO Guest Request input */
+	void *guest_resp_buf;   /* Bounce buffer for TIO Guest Request output */
+
+	struct pci_ide ide;
+};
+
+/* struct tsm_tdi::data */
+struct tsm_tdi_tio {
+	struct sla_addr_t tdi_ctx;
+	u64 gctx_paddr;
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
+void sev_tio_cleanup(struct sev_device *sev);
+
+void tio_save_output(struct tsm_blob **blob, struct sla_addr_t sla, u32 dobjid);
+
+int sev_tio_status(struct sev_device *sev);
+int sev_tio_continue(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+
+int sev_tio_dev_measurements(struct tsm_dev_tio *dev_data, void *nonce, size_t nonce_len,
+			     struct tsm_spdm *spdm);
+int sev_tio_dev_certificates(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+int sev_tio_dev_create(struct tsm_dev_tio *dev_data, u16 device_id, u16 root_port_id,
+		       u8 segment_id);
+int sev_tio_dev_connect(struct tsm_dev_tio *dev_data, u8 tc_mask, u8 ids[8], u8 cert_slot,
+			struct tsm_spdm *spdm);
+int sev_tio_dev_disconnect(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+int sev_tio_dev_reclaim(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+int sev_tio_dev_status(struct tsm_dev_tio *dev_data, struct tsm_dev_status *status);
+int sev_tio_ide_refresh(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm);
+
+int sev_tio_tdi_create(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data, u16 dev_id,
+		       u8 rseg, u8 rseg_valid);
+void sev_tio_tdi_reclaim(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data);
+int sev_tio_guest_request(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+			  void *req, void *res, struct tsm_spdm *spdm);
+
+int sev_tio_tdi_bind(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		     u32 guest_rid, u64 gctx_paddr, u32 asid, bool force_run,
+		     struct tsm_spdm *spdm);
+int sev_tio_tdi_unbind(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm);
+int sev_tio_tdi_report(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm);
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
index c87a312f7da6..342fcd42fa7c 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -43,6 +43,8 @@ struct sev_misc_dev {
 	struct miscdevice misc;
 };
 
+struct sev_tio_status;
+
 struct sev_device {
 	struct device *dev;
 	struct psp_device *psp;
@@ -71,7 +73,13 @@ struct sev_device {
 	struct fw_upload *fwl;
 	bool fw_cancel;
 #endif /* CONFIG_FW_UPLOAD */
+
 	bool tio_en;
+#if defined(CONFIG_PCI_TSM) || defined(CONFIG_PCI_TSM_MODULE)
+	struct tsm_host_subsys *tsm;
+	struct tsm_bus_subsys *tsm_bus;
+	struct sev_tio_status *tio_status;
+#endif
 };
 
 bool sev_version_greater_or_equal(u8 maj, u8 min);
@@ -102,4 +110,14 @@ static inline void sev_snp_destroy_firmware_upload(struct sev_device *sev) { }
 static inline int sev_snp_synthetic_error(struct sev_device *sev, int *psp_ret) { return 0; }
 #endif /* CONFIG_CRYPTO_DEV_SP_PSP_FW_UPLOAD */
 
+#if defined(CONFIG_PCI_TSM) || defined(CONFIG_PCI_TSM_MODULE)
+void sev_tsm_init(struct sev_device *sev);
+void sev_tsm_uninit(struct sev_device *sev);
+int sev_tio_cmd_buffer_len(int cmd);
+#else
+static inline void sev_tsm_init(struct sev_device *sev) {}
+static inline void sev_tsm_uninit(struct sev_device *sev) {}
+static inline int sev_tio_cmd_buffer_len(int cmd) { return 0; }
+#endif
+
 #endif /* __SEV_DEV_H */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 103d9c161f41..5d276e2c2112 100644
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
 
@@ -770,6 +792,11 @@ struct sev_data_snp_guest_request {
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
diff --git a/include/uapi/linux/psp-sev.h b/include/uapi/linux/psp-sev.h
index affa65dcebd4..a2fbc20c5db6 100644
--- a/include/uapi/linux/psp-sev.h
+++ b/include/uapi/linux/psp-sev.h
@@ -88,6 +88,8 @@ typedef enum {
 	SEV_RET_RMP_INITIALIZATION_FAILED  = 0x0026,
 	SEV_RET_INVALID_KEY                = 0x0027,
 	SEV_RET_SHUTDOWN_INCOMPLETE        = 0x0028,
+	SEV_RET_INCORRECT_BUFFER_LENGTH	   = 0x0030,
+	SEV_RET_EXPAND_BUFFER_LENGTH_REQUEST = 0x0031,
 	SEV_RET_SPDM_REQUEST               = 0x0032,
 	SEV_RET_SPDM_ERROR                 = 0x0033,
 	SEV_RET_IN_USE                     = 0x003A,
diff --git a/drivers/crypto/ccp/sev-dev-tio.c b/drivers/crypto/ccp/sev-dev-tio.c
new file mode 100644
index 000000000000..bd55ad6c5fb3
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tio.c
@@ -0,0 +1,1664 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+// Interface to PSP for CCP/SEV-TIO/SNP-VM
+
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include <linux/psp.h>
+#include <linux/file.h>
+#include <linux/vmalloc.h>
+
+#include <asm/sev-common.h>
+#include <asm/sev.h>
+#include <asm/page.h>
+
+#include "psp-dev.h"
+#include "sev-dev.h"
+#include "sev-dev-tio.h"
+
+static void *__prep_data_pg(struct tsm_dev_tio *dev_data, size_t len)
+{
+	void *r = dev_data->data_pg;
+
+	if (snp_reclaim_pages(virt_to_phys(r), 1, false))
+		return NULL;
+
+	memset(r, 0, len);
+
+	if (rmp_make_private(page_to_pfn(virt_to_page(r)), 0, PG_LEVEL_4K, 0, true))
+		return NULL;
+
+	return r;
+}
+
+#define prep_data_pg(type, tdev) ((type *) __prep_data_pg((tdev), sizeof(type)))
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
+	u32 length; /* Length of the data object, INCLUDING THIS HEADER */
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
+void sev_tio_cleanup(struct sev_device *sev)
+{
+	kfree(sev->tio_status);
+	sev->tio_status = NULL;
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
+	u8 meas_nonce[32];
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
+	u8 ide_stream_id[8];
+	u8 reserved4[8];
+	u8 certs_digest[48];
+	u8 meas_digest[48];
+	u32 tdi_count;
+	u32 bound_tdi_count;
+	u8 reserved5[8];
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
+	u16 run:1;
+	u16 reserved2:15;
+	u8 reserved3[2];
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
+		struct sla_addr_t *scatter = __va((u64)sla.pfn << PAGE_SHIFT);
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
+		struct sla_addr_t *scatter = __va((u64)sla.pfn << PAGE_SHIFT);
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
+			scatter = __va((u64)sla.pfn << PAGE_SHIFT);
+
+			for (i = 0; i < npages; ++i) {
+				if (IS_SLA_EOL(scatter[i]))
+					break;
+
+				ret = snp_reclaim_pages(
+					(u64)scatter[i].pfn << PAGE_SHIFT,
+					1, false);
+				if (ret)
+					break;
+			}
+		} else {
+			pr_err("Reclaiming %llx\n", (u64)sla.pfn << PAGE_SHIFT);
+			ret = snp_reclaim_pages((u64)sla.pfn << PAGE_SHIFT, 1, false);
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
+			free_page((unsigned long)__va((u64)scatter[i].pfn << PAGE_SHIFT));
+		}
+	}
+
+	free_page((unsigned long)__va((u64)sla.pfn << PAGE_SHIFT));
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
+/* Expands a buffer, only firmware owned buffers allowed for now */
+static int sla_expand(struct sla_addr_t *sla, size_t *len)
+{
+	struct sla_buffer_hdr *oldbuf = sla_buffer_map(*sla), *newbuf;
+	struct sla_addr_t oldsla = *sla, newsla;
+	size_t oldlen = *len, newlen;
+
+	if (!oldbuf)
+		return -EFAULT;
+
+	newlen = oldbuf->capacity_sz;
+	if (oldbuf->capacity_sz == oldlen) {
+		/* This buffer does not require expansion, must be another buffer */
+		sla_buffer_unmap(oldsla, oldbuf);
+		return 1;
+	}
+
+	pr_notice("Expanding BUFFER from %ld to %ld bytes\n", oldlen, newlen);
+
+	newsla = sla_alloc(newlen, true);
+	if (IS_SLA_NULL(newsla))
+		return -ENOMEM;
+
+	newbuf = sla_buffer_map(newsla);
+	if (!newbuf) {
+		sla_free(newsla, newlen, true);
+		return -EFAULT;
+	}
+
+	memcpy(newbuf, oldbuf, oldlen);
+
+	sla_buffer_unmap(newsla, newbuf);
+	sla_free(oldsla, oldlen, true);
+	*sla = newsla;
+	*len = newlen;
+
+	return 0;
+}
+
+void tio_save_output(struct tsm_blob **blob, struct sla_addr_t sla, u32 check_dobjid)
+{
+	struct sla_buffer_hdr *buf;
+	struct spdm_dobj_hdr *hdr;
+
+	tsm_blob_free(*blob);
+	*blob = NULL;
+
+	buf = sla_buffer_map(sla);
+	if (!buf)
+		return;
+
+	hdr = sla_to_dobj_hdr_check(buf, check_dobjid);
+	if (hdr)
+		*blob = tsm_blob_new(SPDM_DOBJ_DATA(hdr), hdr->length);
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
+	if (rc == 0 && *psp_ret == SEV_RET_EXPAND_BUFFER_LENGTH_REQUEST) {
+		int rc1, rc2;
+
+		rc1 = sla_expand(&dev_data->output, &dev_data->output_len);
+		if (rc1 < 0)
+			return rc1;
+
+		rc2 = sla_expand(&dev_data->scratch, &dev_data->scratch_len);
+		if (rc2 < 0)
+			return rc2;
+
+		if (!rc1 && !rc2)
+			/* Neither buffer requires expansion, this is wrong */
+			return -EFAULT;
+
+		*psp_ret = 0;
+		rc = sev_do_cmd(cmd, data, psp_ret);
+	}
+
+	if (spdm && (rc == 0 || rc == -EIO) && *psp_ret == SEV_RET_SPDM_REQUEST) {
+		struct spdm_dobj_hdr_resp *resp_hdr;
+		struct spdm_dobj_hdr_req *req_hdr;
+		size_t resp_len = dev_data->tio_status->spdm_req_size_max -
+			(sla_dobj_id_to_size(SPDM_DOBJ_ID_RESP) + sizeof(struct sla_buffer_hdr));
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
+			rc = TSM_PROTO_CMA_SPDM;
+			break;
+		case DOBJ_DATA_TYPE_SECURE_SPDM:
+			rc = TSM_PROTO_SECURED_CMA_SPDM;
+			break;
+		default:
+			rc = -EINVAL;
+			return rc;
+		}
+		resp_hdr->data_type = req_hdr->data_type;
+		spdm->req_len = req_hdr->hdr.length;
+		spdm->rsp_len = resp_len;
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
+	ret = sev_tio_do_cmd(dev_data->cmd, dev_data->cmd_data, 0,
+			     &dev_data->psp_ret, dev_data, spdm);
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
+	size_t len = dev_data->tio_status->spdm_req_size_max -
+		(sla_dobj_id_to_size(SPDM_DOBJ_ID_RESP) +
+		 sizeof(struct sla_buffer_hdr));
+
+	sla_buffer_unmap(dev_data->resp, dev_data->respbuf);
+	sla_buffer_unmap(dev_data->req, dev_data->reqbuf);
+	spdm->rsp = NULL;
+	spdm->req = NULL;
+	sla_free(dev_data->req, len, true);
+	sla_free(dev_data->resp, len, false);
+	sla_free(dev_data->scratch, dev_data->tio_status->spdm_scratch_size_max, true);
+
+	dev_data->req.sla = 0;
+	dev_data->resp.sla = 0;
+	dev_data->scratch.sla = 0;
+	dev_data->respbuf = NULL;
+	dev_data->reqbuf = NULL;
+	sla_free(dev_data->output, dev_data->tio_status->spdm_out_size_max, true);
+}
+
+static int spdm_ctrl_alloc(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_tio_status *tio_status = dev_data->tio_status;
+	int ret;
+
+	dev_data->req = sla_alloc(tio_status->spdm_req_size_max, true);
+	dev_data->resp = sla_alloc(tio_status->spdm_req_size_max, false);
+	dev_data->scratch_len = tio_status->spdm_scratch_size_max;
+	dev_data->scratch = sla_alloc(dev_data->scratch_len, true);
+	dev_data->output_len = tio_status->spdm_out_size_max;
+	dev_data->output = sla_alloc(dev_data->output_len, true);
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
+int sev_tio_status(struct sev_device *sev)
+{
+	struct sev_data_tio_status data_status = {
+		.length = sizeof(data_status),
+	};
+	struct sev_tio_status *tio_status;
+	int ret = 0, psp_ret = 0;
+
+	if (!sev_version_greater_or_equal(1, 55))
+		return -EPERM;
+
+	WARN_ON(tio_status);
+
+	tio_status = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+	if (!tio_status)
+		return -ENOMEM;
+
+	data_status.status_paddr = __psp_pa(tio_status);
+	ret = sev_do_cmd(SEV_CMD_TIO_STATUS, &data_status, &psp_ret);
+	if (ret)
+		goto err_msg_exit;
+
+	if (tio_status->flags & 0xFFFFFF00) {
+		ret = -EFAULT;
+		goto err_msg_exit;
+	}
+
+	if (!tio_status->tio_en && !tio_status->tio_init_done) {
+		ret = -ENOENT;
+		goto err_msg_exit;
+	}
+
+	if (tio_status->tio_en && !tio_status->tio_init_done) {
+		struct sev_data_tio_init ti = { .length = sizeof(ti) };
+
+		ret = sev_do_cmd(SEV_CMD_TIO_INIT, &ti, &psp_ret);
+		if (ret)
+			goto err_msg_exit;
+
+		ret = sev_do_cmd(SEV_CMD_TIO_STATUS, &data_status, &psp_ret);
+		if (ret)
+			goto err_msg_exit;
+
+		print_hex_dump(KERN_INFO, "TIO_ST ", DUMP_PREFIX_OFFSET, 16, 1, tio_status,
+			       sizeof(*tio_status), false);
+	}
+
+	sev->tio_status = kmemdup(tio_status, sizeof(*tio_status), GFP_KERNEL);
+	if (!sev->tio_status) {
+		ret = -ENOMEM;
+		goto err_msg_exit;
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
+	goto free_exit;
+
+err_msg_exit:
+	pr_err("Failed to enable SEV-TIO: ret=%d en=%d initdone=%d SEV=%d\n",
+	       ret, tio_status->tio_en, tio_status->tio_init_done,
+	       boot_cpu_has(X86_FEATURE_SEV));
+	pr_err("Check BIOS for: SMEE, SEV Control, SEV-ES ASID Space Limit=99,\n"
+	       "SNP Memory (RMP Table) Coverage, RMP Coverage for 64Bit MMIO Ranges\n"
+	       "SEV-SNP Support, SEV-TIO Support, PCIE IDE Capability\n");
+	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+		pr_err("mem_encrypt=on is currently broken\n");
+
+free_exit:
+	snp_free_firmware_page(tio_status);
+	return ret;
+}
+
+int sev_tio_dev_create(struct tsm_dev_tio *dev_data, u16 device_id,
+		       u16 root_port_id, u8 segment_id)
+{
+	struct sev_tio_status *tio_status = dev_data->tio_status;
+	struct sev_data_tio_dev_create create = {
+		.length = sizeof(create),
+		.device_id = device_id,
+		.root_port_id = root_port_id,
+		.segment_id = segment_id,
+	};
+	void *data_pg;
+	int ret;
+
+	dev_data->dev_ctx = sla_alloc(tio_status->devctx_size, true);
+	if (IS_SLA_NULL(dev_data->dev_ctx))
+		return -ENOMEM;
+
+	/* Alloc data page for TDI_STATUS, TDI_INFO, the PSP or prep_data_pg() will zero it */
+	data_pg = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT);
+	if (!data_pg) {
+		ret = -ENOMEM;
+		goto free_ctx_exit;
+	}
+
+	create.dev_ctx_sla = dev_data->dev_ctx;
+	ret = sev_tio_do_cmd(SEV_CMD_TIO_DEV_CREATE, &create, sizeof(create),
+			     &dev_data->psp_ret, dev_data, NULL);
+	if (ret)
+		goto free_data_pg_exit;
+
+	dev_data->data_pg = data_pg;
+
+	return ret;
+
+free_data_pg_exit:
+	snp_free_firmware_page(data_pg);
+free_ctx_exit:
+	sla_free(create.dev_ctx_sla, tio_status->devctx_size, true);
+	return ret;
+}
+
+int sev_tio_dev_reclaim(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_tio_status *tio_status = dev_data->tio_status;
+	struct sev_data_tio_dev_reclaim r = {
+		.length = sizeof(r),
+		.dev_ctx_sla = dev_data->dev_ctx,
+	};
+	int ret;
+
+	if (dev_data->data_pg) {
+		snp_free_firmware_page(dev_data->data_pg);
+		dev_data->data_pg = NULL;
+	}
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
+int sev_tio_dev_connect(struct tsm_dev_tio *dev_data, u8 tc_mask, u8 ids[8], u8 cert_slot,
+			struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_connect connect = {
+		.length = sizeof(connect),
+		.tc_mask = tc_mask,
+		.cert_slot = cert_slot,
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.ide_stream_id = {
+			ids[0], ids[1], ids[2], ids[3],
+			ids[4], ids[5], ids[6], ids[7]
+		},
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
+int sev_tio_dev_measurements(struct tsm_dev_tio *dev_data, void *nonce, size_t nonce_len,
+			     struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_meas meas = {
+		.length = sizeof(meas),
+		.raw_bitstream = 1,
+	};
+
+	if (nonce_len > sizeof(meas.meas_nonce))
+		return -EINVAL;
+
+	if (WARN_ON(IS_SLA_NULL(dev_data->dev_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &meas.spdm_ctrl, dev_data);
+	meas.dev_ctx_sla = dev_data->dev_ctx;
+	memcpy(meas.meas_nonce, nonce, nonce_len);
+
+	return sev_tio_do_cmd(SEV_CMD_TIO_DEV_MEASUREMENTS, &meas, sizeof(meas),
+			      &dev_data->psp_ret, dev_data, spdm);
+}
+
+int sev_tio_dev_certificates(struct tsm_dev_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_dev_certs c = {
+		.length = sizeof(c),
+	};
+
+	if (WARN_ON(IS_SLA_NULL(dev_data->dev_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &c.spdm_ctrl, dev_data);
+	c.dev_ctx_sla = dev_data->dev_ctx;
+
+	return sev_tio_do_cmd(SEV_CMD_TIO_DEV_CERTIFICATES, &c, sizeof(c),
+			      &dev_data->psp_ret, dev_data, spdm);
+}
+
+int sev_tio_dev_status(struct tsm_dev_tio *dev_data, struct tsm_dev_status *s)
+{
+	struct sev_tio_dev_status *status =
+		prep_data_pg(struct sev_tio_dev_status, dev_data);
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
+	struct sev_tio_status *tio_status = dev_data->tio_status;
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
+	c.interface_id.function_id =
+		FIELD_PREP(TSM_TDISP_IID_REQUESTER_ID, dev_id) |
+		FIELD_PREP(TSM_TDISP_IID_RSEG, rseg) |
+		FIELD_PREP(TSM_TDISP_IID_RSEG_VALID, rseg_valid);
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
+	struct sev_tio_status *tio_status = dev_data->tio_status;
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
+		     u32 guest_rid, u64 gctx_paddr, u32 asid, bool force_run,
+		     struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_tdi_bind b = {
+		.length = sizeof(b),
+	};
+
+	if (WARN_ON_ONCE(IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &b.spdm_ctrl, dev_data);
+	b.dev_ctx_sla = dev_data->dev_ctx;
+	b.tdi_ctx_sla = tdi_data->tdi_ctx;
+	b.guest_device_id = guest_rid;
+	b.gctx_paddr = gctx_paddr;
+	b.run = force_run;
+
+	tdi_data->gctx_paddr = gctx_paddr;
+	tdi_data->asid = asid;
+
+	return sev_tio_do_cmd(SEV_CMD_TIO_TDI_BIND, &b, sizeof(b),
+			      &dev_data->psp_ret, dev_data, spdm);
+}
+
+int sev_tio_tdi_unbind(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_tdi_unbind ub = {
+		.length = sizeof(ub),
+	};
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
+	return sev_tio_do_cmd(SEV_CMD_TIO_TDI_UNBIND, &ub, sizeof(ub),
+			      &dev_data->psp_ret, dev_data, spdm);
+}
+
+int sev_tio_tdi_report(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		       struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_tdi_report r = {
+		.length = sizeof(r),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+		.gctx_paddr = tdi_data->gctx_paddr,
+	};
+
+	if (WARN_ON_ONCE(IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx)))
+		return -EFAULT;
+
+	spdm_ctrl_init(spdm, &r.spdm_ctrl, dev_data);
+
+	return sev_tio_do_cmd(SEV_CMD_TIO_TDI_REPORT, &r, sizeof(r),
+			      &dev_data->psp_ret, dev_data, spdm);
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
+
+	return sev_do_cmd(SEV_CMD_TIO_ASID_FENCE_CLEAR, &c, psp_ret);
+}
+
+int sev_tio_asid_fence_status(struct tsm_dev_tio *dev_data, u16 device_id, u8 segment_id,
+			      u32 asid, bool *fenced)
+{
+	u64 *status = prep_data_pg(u64, dev_data);
+	struct sev_data_tio_asid_fence_status s = {
+		.length = sizeof(s),
+		.asid = asid,
+		.status_pa = __psp_pa(status),
+		.device_id = device_id,
+		.segment_id = segment_id,
+	};
+	int ret;
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
+int sev_tio_guest_request(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+			  void *req, void *res, struct tsm_spdm *spdm)
+{
+	struct sev_data_tio_guest_request gr = {
+		.length = sizeof(gr),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+		.gctx_paddr = tdi_data->gctx_paddr,
+		.req_paddr = __psp_pa(req),
+		.res_paddr = __psp_pa(res),
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
+			u32 tdi_status:2; /* 0: TDI_UNBOUND 1: TDI_BIND_LOCKED 2: TDI_BIND_RUN */
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
+	u64 intf_report_counter;
+	u32 asid; /* ASID of the guest that this device is assigned to. Valid if CTX_STATE=1 */
+	u8 reserved2[4];
+} __packed;
+
+struct sev_data_tio_tdi_info {
+	u32 length;
+	u32 reserved1;
+	struct sla_addr_t dev_ctx_sla;
+	struct sla_addr_t tdi_ctx_sla;
+	u64 status_paddr;
+	u8 reserved2[16];
+} __packed;
+
+int sev_tio_tdi_info(struct tsm_dev_tio *dev_data, struct tsm_tdi_tio *tdi_data,
+		     struct tsm_tdi_status *ts)
+{
+	struct sev_tio_tdi_info_data *data =
+		prep_data_pg(struct sev_tio_tdi_info_data, dev_data);
+	struct sev_data_tio_tdi_info info = {
+		.length = sizeof(info),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+		.status_paddr = __psp_pa(data),
+	};
+	int ret;
+
+	if (IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx))
+		return -ENXIO;
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
+	((((x) & (0xFFULL << (n))) == TIO_SPDM_ALGOS_##y) ? \
+	 (1ULL << TSM_SPDM_ALGOS_##y) : 0)
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
+	ts->intf_report_counter = data->intf_report_counter;
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
+	struct sev_tio_tdi_status_data *data =
+		prep_data_pg(struct sev_tio_tdi_status_data, dev_data);
+	struct sev_data_tio_tdi_status status = {
+		.length = sizeof(status),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.tdi_ctx_sla = tdi_data->tdi_ctx,
+		.status_paddr = __psp_pa(data),
+	};
+
+	if (IS_SLA_NULL(dev_data->dev_ctx) || IS_SLA_NULL(tdi_data->tdi_ctx))
+		return -ENXIO;
+
+	spdm_ctrl_init(spdm, &status.spdm_ctrl, dev_data);
+
+	return sev_tio_do_cmd(SEV_CMD_TIO_TDI_STATUS, &status, sizeof(status),
+			      &dev_data->psp_ret, dev_data, spdm);
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
+	struct sev_tio_tdi_status_data *data = (struct sev_tio_tdi_status_data *) dev_data->data_pg;
+
+	switch (data->tdisp_state) {
+#define __TDISP_STATE(y) case TIO_TDISP_STATE_##y: *state = TDISP_STATE_##y; break
+	__TDISP_STATE(CONFIG_UNLOCKED);
+	__TDISP_STATE(CONFIG_LOCKED);
+	__TDISP_STATE(RUN);
+	__TDISP_STATE(ERROR);
+#undef __TDISP_STATE
+	}
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
index 000000000000..db34fce3126b
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -0,0 +1,709 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+// Interface to CCP/SEV-TIO for generic PCIe TDISP module
+
+#include <linux/pci.h>
+#include <linux/device.h>
+#include <linux/tsm.h>
+
+#include <asm/sev-common.h>
+#include <asm/sev.h>
+
+#include "psp-dev.h"
+#include "sev-dev.h"
+#include "sev-dev-tio.h"
+
+#define tdi_to_pci_dev(tdi) (to_pci_dev(tdi->dev.parent))
+
+static void pr_ide_state(struct pci_dev *pdev, struct pci_ide *ide)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	u32 devst = 0xffffffff, rcst = 0xffffffff;
+	int ret = pci_ide_stream_state(pdev, ide, &devst, &rcst);
+
+	pci_notice(pdev, "%x%s <-> %s: %x%s ret=%d",
+		   devst,
+		   PCI_IDE_SEL_STS_STATUS(devst) == 2 ? "=SECURE" : "",
+		   pci_name(rp),
+		   rcst,
+		   PCI_IDE_SEL_STS_STATUS(rcst) == 2 ? "=SECURE" : "",
+		   ret);
+}
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
+static int ide_refresh(struct tsm_dev *tdev)
+{
+	struct tsm_dev_tio *dev_data = tdev->data;
+	int ret;
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_ide_refresh(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_ROLL_KEY) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+	}
+
+	return ret;
+}
+
+static int dev_create(struct tsm_dev *tdev, void *private_data)
+{
+	struct pci_dev *pdev = to_pci_dev(tdev->physdev);
+	u8 segment_id = pdev->bus ? pci_domain_nr(pdev->bus) : 0;
+	struct pci_dev *rootport = pdev->bus->self;
+	struct sev_device *sev = private_data;
+	u16 device_id = pci_dev_id(pdev);
+	struct tsm_dev_tio *dev_data;
+	struct page *req_page;
+	u16 root_port_id;
+	u32 lnkcap = 0;
+	int ret;
+
+	if (pci_read_config_dword(rootport, pci_pcie_cap(rootport) + PCI_EXP_LNKCAP,
+				  &lnkcap))
+		return -ENODEV;
+
+	root_port_id = FIELD_GET(PCI_EXP_LNKCAP_PN, lnkcap);
+
+	dev_data = kzalloc(sizeof(*dev_data), GFP_KERNEL);
+	if (!dev_data)
+		return -ENOMEM;
+
+	dev_data->tio_status = sev->tio_status;
+
+	req_page = alloc_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+	if (!req_page) {
+		ret = -ENOMEM;
+		goto free_dev_data_exit;
+	}
+	dev_data->guest_req_buf = page_address(req_page);
+
+	dev_data->guest_resp_buf = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+	if (!dev_data->guest_resp_buf) {
+		ret = -EIO;
+		goto free_req_exit;
+	}
+
+	ret = sev_tio_dev_create(dev_data, device_id, root_port_id, segment_id);
+	if (ret)
+		goto free_resp_exit;
+
+	tdev->data = dev_data;
+
+	return 0;
+
+free_resp_exit:
+	snp_free_firmware_page(dev_data->guest_resp_buf);
+free_req_exit:
+	__free_page(req_page);
+free_dev_data_exit:
+	kfree(dev_data);
+	return ret;
+}
+
+static int dev_connect(struct tsm_dev *tdev, void *private_data)
+{
+	struct pci_dev *pdev = to_pci_dev(tdev->physdev);
+	struct tsm_dev_tio *dev_data = tdev->data;
+	u8 tc_mask = 1, ids[8] = { 0 };
+	int ret;
+
+	if (tdev->connected)
+		return ide_refresh(tdev);
+
+	if (!dev_data) {
+		struct pci_ide ide1 = { 0 };
+		struct pci_ide *ide = &ide1;
+
+		pci_ide_stream_probe(pdev, ide);
+		ide->stream_id = ids[0];
+		ide->nr_mem = 1;
+		ide->mem[0] = (struct range) { 0, 0xFFFFFFFFFFF00000ULL };
+		ide->dev_sel_ctl = FIELD_PREP(PCI_IDE_SEL_CTL_TEE_LIMITED, 1);
+		ide->rootport_sel_ctl = FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, 1);
+		ide->devid_start = 0;
+		ide->devid_end = 0xffff;
+		ide->rpid_start = 0;
+		ide->rpid_end = 0xffff;
+
+		ret = pci_ide_stream_setup(pdev, ide, PCI_IDE_SETUP_ROOT_PORT);
+		if (ret)
+			return ret;
+
+		pci_ide_enable_stream(pdev, ide);
+		pr_ide_state(pdev, ide);
+
+		ret = dev_create(tdev, private_data);
+		if (ret)
+			return ret;
+
+		dev_data = tdev->data;
+		dev_data->ide = *ide;
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_connect(dev_data, tc_mask, ids, tdev->cert_slot, &tdev->spdm);
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
+		if (ret > 0)
+			return ret;
+		if (ret < 0)
+			goto free_exit;
+
+		tio_save_output(&tdev->certs, dev_data->output, SPDM_DOBJ_ID_CERTIFICATE);
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_measurements(dev_data, tdev->nonce, tdev->nonce_len, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		if (ret < 0) {
+			pci_warn(pdev, "Reading measurements failed ret=%d\n", ret);
+			ret = 0;
+		} else {
+			tio_save_output(&tdev->meas, dev_data->output, SPDM_DOBJ_ID_MEASUREMENT);
+		}
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_DEV_MEASUREMENTS) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		if (ret < 0) {
+			pci_warn(pdev, "Reading measurements failed ret=%d\n", ret);
+			ret = 0;
+		} else {
+			tio_save_output(&tdev->meas, dev_data->output, SPDM_DOBJ_ID_MEASUREMENT);
+		}
+	}
+#if 0
+	/* Uncomment to verify SEV_CMD_TIO_DEV_CERTIFICATES work */
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_certificates(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		if (ret < 0)
+			goto free_exit;
+
+		tio_save_output(&tdev->certs, dev_data->output, SPDM_DOBJ_ID_CERTIFICATE);
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_DEV_CERTIFICATES) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		if (ret < 0)
+			goto free_exit;
+
+		tio_save_output(&tdev->certs, dev_data->output, SPDM_DOBJ_ID_CERTIFICATE);
+	}
+#endif
+	ret = tsm_register_ide_stream(tdev, &dev_data->ide);
+	if (ret)
+		goto free_exit;
+
+	try_module_get(THIS_MODULE);
+	pr_ide_state(pdev, &dev_data->ide);
+	return 0;
+
+free_exit:
+	sev_tio_dev_reclaim(dev_data, &tdev->spdm);
+	kfree(dev_data);
+	tdev->data = NULL;
+	if (ret > 0)
+		ret = -EFAULT;
+
+	return ret;
+}
+
+static int dev_disconnect(struct tsm_dev *tdev)
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
+		dev_err(&tdev->dev, "Wrong state, cmd 0x%x in flight\n",
+			dev_data->cmd);
+	}
+
+	ret = sev_tio_dev_reclaim(dev_data, &tdev->spdm);
+	ret = mkret(ret, dev_data);
+
+	tsm_blob_free(tdev->meas);
+	tdev->meas = NULL;
+	tsm_blob_free(tdev->certs);
+	tdev->certs = NULL;
+	kfree(tdev->data);
+	tdev->data = NULL;
+
+	if (dev_data->guest_resp_buf)
+		snp_free_firmware_page(dev_data->guest_resp_buf);
+
+	if (dev_data->guest_req_buf)
+		__free_page(virt_to_page(dev_data->guest_req_buf));
+
+	dev_data->guest_req_buf = NULL;
+	dev_data->guest_resp_buf = NULL;
+
+	struct pci_dev *pdev = to_pci_dev(tdev->physdev);
+	struct pci_ide *ide = &dev_data->ide;
+
+	pr_ide_state(pdev, &dev_data->ide);
+	pci_ide_disable_stream(pdev, ide);
+	tsm_unregister_ide_stream(tdev, ide);
+	pci_ide_stream_teardown(pdev, ide);
+	pr_ide_state(pdev, &dev_data->ide);
+
+	module_put(THIS_MODULE);
+
+	return ret;
+}
+
+static int dev_status(struct tsm_dev *tdev, struct tsm_dev_status *s)
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
+		WARN_ON(s->device_id != pci_dev_id(to_pci_dev(tdev->physdev)));
+
+	return ret;
+}
+
+static int dev_measurements(struct tsm_dev *tdev)
+{
+	struct tsm_dev_tio *dev_data = tdev->data;
+	int ret;
+
+	if (!dev_data)
+		return -ENODEV;
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_dev_measurements(dev_data, tdev->nonce, tdev->nonce_len, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		if (ret < 0)
+			return ret;
+
+		tio_save_output(&tdev->meas, dev_data->output, SPDM_DOBJ_ID_MEASUREMENT);
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_DEV_MEASUREMENTS) {
+		ret = sev_tio_continue(dev_data, &tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		if (ret < 0)
+			return ret;
+
+		tio_save_output(&tdev->meas, dev_data->output, SPDM_DOBJ_ID_MEASUREMENT);
+	}
+
+	return 0;
+}
+
+static void tdi_share_mmio(struct pci_dev *pdev);
+
+static int tdi_unbind(struct tsm_tdi *tdi)
+{
+	struct tsm_dev_tio *dev_data;
+	int ret;
+
+	if (!tdi->data)
+		return -ENODEV;
+
+	dev_data = tdi->tdev->data;
+	if (tdi->kvm) {
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
+	/* The hunk to verify transitioning to CONFIG_UNLOCKED */
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_tdi_status(tdi->tdev->data, tdi->data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+
+	} else if (dev_data->cmd == SEV_CMD_TIO_TDI_STATUS) {
+		enum tsm_tdisp_state state = TDISP_STATE_CONFIG_UNLOCKED;
+		static const char * const sstate[] = {
+			"CONFIG_UNLOCKED", "CONFIG_LOCKED", "RUN", "ERROR"};
+
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+
+		if (ret) {
+			dev_err(&tdi->dev, "TDI status failed to read, ret=%d\n", ret);
+		} else {
+			ret = sev_tio_tdi_status_fin(tdi->tdev->data, tdi->data, &state);
+			dev_notice(&tdi->dev, "TDI status %d=\"%s\"\n",
+				   state, state < ARRAY_SIZE(sstate) ? sstate[state] : sstate[0]);
+		}
+	}
+
+	/* Reclaim TDI if DEV is connected */
+	if (tdi->tdev->data) {
+		struct tsm_tdi_tio *tdi_data = tdi->data;
+		struct tsm_dev *tdev = tdi->tdev;
+		struct pci_dev *pdev = to_pci_dev(tdev->physdev);
+		struct pci_dev *rootport = pdev->bus->self;
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
+						tdi_data->gctx_paddr, &dev_data->psp_ret);
+				pci_notice(rootport, "Unfenced VM=%llx ASID=%d ret=%d %d",
+					   tdi_data->gctx_paddr, tdi_data->asid, ret,
+					   dev_data->psp_ret);
+			}
+		}
+
+		tsm_blob_free(tdi->report);
+		tdi->report = NULL;
+	}
+
+	pr_ide_state(to_pci_dev(tdi->tdev->physdev), &dev_data->ide);
+	kfree(tdi->data);
+	tdi->data = NULL;
+
+	tdi_share_mmio(tdi_to_pci_dev(tdi));
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
+	ret = sev_tio_tdi_create(tdi->tdev->data, tdi_data, pci_dev_id(tdi_to_pci_dev(tdi)),
+				 tdi->rseg, tdi->rseg_valid);
+	if (ret)
+		kfree(tdi_data);
+	else
+		tdi->data = tdi_data;
+
+	return ret;
+}
+
+static int tdi_bind(struct tsm_tdi *tdi, u32 bdfn, u64 vmid)
+{
+	enum tsm_tdisp_state state = TDISP_STATE_CONFIG_UNLOCKED;
+	struct tsm_dev_tio *dev_data = tdi->tdev->data;
+	u64 gctx = __psp_pa(vmid & PAGE_MASK); /* see SVM's sev_tio_vmid() */
+	u32 asid = vmid & ~PAGE_MASK;
+	int ret = 0;
+
+	if (dev_data->cmd == SEV_CMD_TIO_TDI_UNBIND) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		return mkret(ret, dev_data);
+	}
+
+	if (!tdi->data) {
+		ret = tdi_create(tdi);
+		if (ret)
+			return ret;
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_tdi_bind(dev_data, tdi->data, bdfn, gctx, asid,
+				       false, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret < 0) {
+			ret = sev_tio_tdi_bind(dev_data, tdi->data, bdfn, gctx, asid,
+					       true, &tdi->tdev->spdm);
+			ret = mkret(ret, dev_data);
+		}
+		if (ret < 0)
+			goto error_exit;
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdi->report, dev_data->output, SPDM_DOBJ_ID_REPORT);
+	}
+
+	if (dev_data->cmd == SEV_CMD_TIO_TDI_BIND) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret < 0)
+			goto error_exit;
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdi->report, dev_data->output, SPDM_DOBJ_ID_REPORT);
+	}
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_tdi_status(tdi->tdev->data, tdi->data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		ret = sev_tio_tdi_status_fin(tdi->tdev->data, tdi->data, &state);
+	} else if (dev_data->cmd == SEV_CMD_TIO_TDI_STATUS) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+
+		ret = sev_tio_tdi_status_fin(tdi->tdev->data, tdi->data, &state);
+	}
+
+	if (ret < 0)
+		goto error_exit;
+	if (ret)
+		return ret;
+
+	if (dev_data->cmd == 0 && state == TDISP_STATE_CONFIG_LOCKED) {
+		ret = sev_tio_tdi_bind(dev_data, tdi->data, bdfn, gctx, asid,
+				       true, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret < 0)
+			goto error_exit;
+		if (ret)
+			return ret;
+
+		tio_save_output(&tdi->report, dev_data->output, SPDM_DOBJ_ID_REPORT);
+	}
+
+	pr_ide_state(to_pci_dev(tdi->tdev->physdev), &dev_data->ide);
+
+	return ret;
+
+error_exit:
+	return sev_tio_tdi_unbind(tdi->tdev->data, tdi->data, &tdi->tdev->spdm);
+}
+
+static int guest_request(struct tsm_tdi *tdi, u8 __user *req, size_t reqlen,
+			 u8 __user *rsp, size_t rsplen, int *fw_err)
+{
+	struct tsm_dev_tio *dev_data = tdi->tdev->data;
+	int ret;
+
+	if (!tdi->data)
+		return -EFAULT;
+
+	if (dev_data->cmd == 0) {
+		ret = copy_from_user(dev_data->guest_req_buf, req, reqlen);
+		if (ret)
+			return ret;
+
+		ret = sev_tio_guest_request(dev_data, tdi->data, dev_data->guest_req_buf,
+					    dev_data->guest_resp_buf, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		*fw_err = dev_data->psp_ret;
+		ret = copy_to_user(rsp, dev_data->guest_resp_buf, rsplen);
+
+	} else if (dev_data->cmd == SEV_CMD_TIO_GUEST_REQUEST) {
+		ret = sev_tio_continue(dev_data, &tdi->tdev->spdm);
+		ret = mkret(ret, dev_data);
+		if (ret > 0)
+			return ret;
+		*fw_err = dev_data->psp_ret;
+		ret = copy_to_user(rsp, dev_data->guest_resp_buf, rsplen);
+	}
+
+	return ret;
+}
+
+static int tdi_status(struct tsm_tdi *tdi, struct tsm_tdi_status *ts)
+{
+	struct tsm_dev_tio *dev_data = tdi->tdev->data;
+	int ret;
+
+	if (!tdi->data)
+		return -ENODEV;
+
+	if (dev_data->cmd == 0) {
+		ret = sev_tio_tdi_info(tdi->tdev->data, tdi->data, ts);
+		ret = mkret(ret, dev_data);
+		if (ret)
+			return ret;
+	}
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
+		dev_err(tdi->dev.parent, "Wrong state, cmd 0x%x in flight\n",
+			dev_data->cmd);
+	}
+
+	return ret;
+}
+
+struct tsm_hv_ops sev_tsm_ops = {
+	.dev_connect = dev_connect,
+	.dev_disconnect = dev_disconnect,
+	.dev_status = dev_status,
+	.dev_measurements = dev_measurements,
+	.tdi_bind = tdi_bind,
+	.tdi_unbind = tdi_unbind,
+	.guest_request = guest_request,
+	.tdi_status = tdi_status,
+};
+
+void sev_tsm_init(struct sev_device *sev)
+{
+	int ret;
+
+	if (!sev->tio_en)
+		return;
+
+	ret = sev_tio_status(sev);
+	if (ret) {
+		pr_warn("SEV-TIO STATUS failed with %d\n", ret);
+		return;
+	}
+
+	sev->tsm = tsm_host_register(sev->dev, &sev_tsm_ops, sev);
+	sev->tsm_bus = pci_tsm_register((struct tsm_subsys *) sev->tsm);
+}
+
+void sev_tsm_uninit(struct sev_device *sev)
+{
+	if (!sev->tio_en)
+		return;
+	if (sev->tsm_bus)
+		pci_tsm_unregister(sev->tsm_bus);
+	if (sev->tsm)
+		tsm_unregister((struct tsm_subsys *) sev->tsm);
+	sev->tsm_bus = NULL;
+	sev->tsm = NULL;
+	sev_tio_cleanup(sev);
+	sev->tio_en = false;
+}
+
+
+static int rmpupdate(u64 pfn, struct rmp_state *state)
+{
+	unsigned long paddr = pfn << PAGE_SHIFT;
+	int ret, level;
+
+	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+		return -ENODEV;
+
+	level = RMP_TO_PG_LEVEL(state->pagesize);
+
+	do {
+		/* Binutils version 2.36 supports the RMPUPDATE mnemonic. */
+		asm volatile(".byte 0xF2, 0x0F, 0x01, 0xFE"
+			     : "=a" (ret)
+			     : "a" (paddr), "c" ((unsigned long)state)
+			     : "memory", "cc");
+	} while (ret == RMPUPDATE_FAIL_OVERLAP);
+
+	if (ret) {
+		pr_err("MMIO RMPUPDATE failed for PFN %llx, pg_level: %d, ret: %d\n",
+		       pfn, level, ret);
+		return -EFAULT;
+	}
+
+	return 0;
+}
+
+static void tdi_share_mmio(struct pci_dev *pdev)
+{
+	struct resource *res;
+
+	pci_dev_for_each_resource(pdev, res) {
+		if (!res)
+			continue;
+
+		pr_err("___K___ %s %u: Sharing %s %llx..%llx\n", __func__, __LINE__,
+			res->name ? res->name : "(null)", res->start, res->end);
+		for (resource_size_t off = res->start; off < res->end; off += PAGE_SIZE) {
+			struct rmp_state state = {};
+
+			state.pagesize = PG_LEVEL_TO_RMP(PG_LEVEL_4K);
+			rmpupdate(off >> PAGE_SHIFT, &state);
+		}
+	}
+}
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index b01e5f913727..d59d74d3aaca 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -37,6 +37,7 @@
 
 #include "psp-dev.h"
 #include "sev-dev.h"
+#include "sev-dev-tio.h"
 
 #define DEVICE_NAME		"sev"
 #define SEV_FW_FILE		"amd/sev.fw"
@@ -234,7 +235,7 @@ static int sev_cmd_buffer_len(int cmd)
 	case SEV_CMD_SNP_COMMIT:		return sizeof(struct sev_data_snp_commit);
 	case SEV_CMD_SNP_FEATURE_INFO:		return sizeof(struct sev_data_snp_feature_info);
 	case SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX:	return sizeof(struct sev_data_download_firmware_ex);
-	default:				return 0;
+	default:				return sev_tio_cmd_buffer_len(cmd);
 	}
 
 	return 0;
@@ -2631,6 +2632,8 @@ void sev_pci_init(void)
 
 	atomic_notifier_chain_register(&panic_notifier_list,
 				       &snp_panic_notifier);
+	sev_tsm_init(sev);
+
 	return;
 
 err:
@@ -2647,6 +2650,11 @@ void sev_pci_exit(void)
 		return;
 
 	sev_firmware_shutdown(sev);
+	/*
+	 * sev_tsm_uninit needs to clear tio_en after sev_firmware_shutdown to let it
+	 * do proper cleanup.
+	 */
+	sev_tsm_uninit(sev);
 
 	atomic_notifier_chain_unregister(&panic_notifier_list,
 					 &snp_panic_notifier);
diff --git a/drivers/virt/coco/host/tsm-host.c b/drivers/virt/coco/host/tsm-host.c
index 80f3315fb195..5d23a3871009 100644
--- a/drivers/virt/coco/host/tsm-host.c
+++ b/drivers/virt/coco/host/tsm-host.c
@@ -265,7 +265,7 @@ static char *spdm_algos_to_str(u64 algos, char *buf, size_t len)
 
 	buf[0] = 0;
 #define __ALGO(x) do {								\
-		if ((n < len) && (algos & (1ULL << (TSM_TDI_SPDM_ALGOS_##x))))	\
+		if ((n < len) && (algos & (1ULL << (TSM_SPDM_ALGOS_##x))))	\
 			n += snprintf(buf + n, len - n, #x" ");			\
 	} while (0)
 
@@ -287,7 +287,6 @@ static const char *tdisp_state_to_str(enum tsm_tdisp_state state)
 {
 	switch (state) {
 #define __ST(x) case TDISP_STATE_##x: return #x
-	case TDISP_STATE_UNAVAIL: return "TDISP state unavailable";
 	__ST(CONFIG_UNLOCKED);
 	__ST(CONFIG_LOCKED);
 	__ST(RUN);
@@ -475,7 +474,6 @@ void tsm_tdi_unbind(struct tsm_tdi *tdi)
 	}
 
 	tdi->guest_rid = 0;
-	tdi->dev.parent->tdi_enabled = false;
 }
 EXPORT_SYMBOL_GPL(tsm_tdi_unbind);
 
diff --git a/drivers/crypto/ccp/Kconfig b/drivers/crypto/ccp/Kconfig
index 40be991f15d2..459bc339e651 100644
--- a/drivers/crypto/ccp/Kconfig
+++ b/drivers/crypto/ccp/Kconfig
@@ -25,6 +25,7 @@ config CRYPTO_DEV_CCP_CRYPTO
 	default m
 	depends on CRYPTO_DEV_CCP_DD
 	depends on CRYPTO_DEV_SP_CCP
+	depends on PCI_TSM
 	select CRYPTO_HASH
 	select CRYPTO_SKCIPHER
 	select CRYPTO_AUTHENC
@@ -39,6 +40,7 @@ config CRYPTO_DEV_SP_PSP
 	bool "Platform Security Processor (PSP) device"
 	default y
 	depends on CRYPTO_DEV_CCP_DD && X86_64 && AMD_IOMMU
+	select TSM_HOST
 	help
 	 Provide support for the AMD Platform Security Processor (PSP).
 	 The PSP is a dedicated processor that provides support for key

---

## [11] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 10/22] KVM: SVM: Add uAPI to change RMP for MMIO*

The TDI bind operation moves the TDI into "RUN" state which means that
TEE resources are now to be used as encrypted, or the device will
refuse to operate. This requires RMP setup for MMIO BARs which is done
in 2 steps:
- RMPUPDATE on the host to assign host's MMIO ranges to GPA (like RAM);
- validate the RMP entry which is done via TIO GUEST REQUEST GHCB message
(unlike RAM for which the VM could just call PVALIDATE) but TDI bind must
complete first to ensure the TDI is in the LOCKED state so the location
of MMIO is fixed.

The bind happens on the first TIO GUEST REQUEST from the guest.
At this point KVM does not have host TDI BDFn so it exits to QEMU which
calls VFIO-IOMMUFD to bind the TDI.

Now, RMPUPDATE need to be done, in some place on the way back to the guest.
Possible places are:
a) the VFIO-IOMMUFD bind handler (does not know GPAs);
b) QEMU (can mmapp MMIO and knows GPA);
c) the KVM handler which received the first TIO GUEST REQUEST (does not
know host MMIO ranges or host BDFn).

The b) approach is taken. Add an KVM ioctl() to update RMP table for
a given MMIO range. Lots of cut-n-paste.

The validation happens later on explicit guest requests.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 arch/x86/include/asm/sev.h      |   2 +
 arch/x86/include/uapi/asm/kvm.h |  11 ++
 arch/x86/kvm/svm/sev.c          | 135 ++++++++++++++++++++
 arch/x86/virt/svm/sev.c         |  34 ++++-
 4 files changed, 178 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index c5e9455df0dc..2cae72b618d0 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -573,7 +573,9 @@ int snp_lookup_rmpentry(u64 pfn, bool *assigned, int *level);
 void snp_dump_hva_rmpentry(unsigned long address);
 int psmash(u64 pfn);
 int rmp_make_private(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immutable);
+int rmp_make_private_mmio(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immutable);
 int rmp_make_shared(u64 pfn, enum pg_level level);
+int rmp_make_shared_mmio(u64 pfn, enum pg_level level);
 void snp_leak_pages(u64 pfn, unsigned int npages);
 void kdump_sev_callback(void);
 void snp_fixup_e820_tables(void);
diff --git a/arch/x86/include/uapi/asm/kvm.h b/arch/x86/include/uapi/asm/kvm.h
index 9e75da97bce0..1681bd8c5d33 100644
--- a/arch/x86/include/uapi/asm/kvm.h
+++ b/arch/x86/include/uapi/asm/kvm.h
@@ -704,6 +704,7 @@ enum sev_cmd_id {
 	KVM_SEV_SNP_LAUNCH_START = 100,
 	KVM_SEV_SNP_LAUNCH_UPDATE,
 	KVM_SEV_SNP_LAUNCH_FINISH,
+	KVM_SEV_SNP_MMIO_RMP_UPDATE,
 
 	KVM_SEV_NR_MAX,
 };
@@ -874,6 +875,16 @@ struct kvm_sev_snp_launch_finish {
 	__u64 pad1[4];
 };
 
+#define KVM_SEV_SNP_RMP_FLAG_PRIVATE		BIT(0)
+
+struct kvm_sev_snp_rmp_update {
+	__u32 flags; /* KVM_SEV_SNP_RMP_FLAG_xxxx */
+	__u32 pad0;
+	__u64 useraddr;
+	__u64 gpa;
+	__u64 size;
+};
+
 #define KVM_X2APIC_API_USE_32BIT_IDS            (1ULL << 0)
 #define KVM_X2APIC_API_DISABLE_BROADCAST_QUIRK  (1ULL << 1)
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 23705ea03381..4916b916c20a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2541,6 +2541,8 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return ret;
 }
 
+static int snp_mmio_rmp_update(struct kvm *kvm, struct kvm_sev_cmd *argp);
+
 int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 {
 	struct kvm_sev_cmd sev_cmd;
@@ -2646,6 +2648,9 @@ int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 	case KVM_SEV_SNP_LAUNCH_FINISH:
 		r = snp_launch_finish(kvm, &sev_cmd);
 		break;
+	case KVM_SEV_SNP_MMIO_RMP_UPDATE:
+		r = snp_mmio_rmp_update(kvm, &sev_cmd);
+		break;
 	default:
 		r = -EINVAL;
 		goto out;
@@ -4115,6 +4120,136 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 	return 1; /* resume guest */
 }
 
+static int hva_to_pfn_remapped(struct vm_area_struct *vma,
+			       unsigned long addr, bool write_fault,
+			       bool *writable, kvm_pfn_t *p_pfn)
+{
+	struct follow_pfnmap_args args = { .vma = vma, .address = addr };
+	kvm_pfn_t pfn;
+	int r;
+
+	r = follow_pfnmap_start(&args);
+	if (r) {
+		/*
+		 * get_user_pages fails for VM_IO and VM_PFNMAP vmas and does
+		 * not call the fault handler, so do it here.
+		 */
+		bool unlocked = false;
+
+		r = fixup_user_fault(current->mm, addr,
+				     (write_fault ? FAULT_FLAG_WRITE : 0),
+				     &unlocked);
+		if (unlocked)
+			return -EAGAIN;
+		if (r)
+			return r;
+
+		r = follow_pfnmap_start(&args);
+		if (r)
+			return r;
+	}
+
+	if (write_fault && !args.writable) {
+		pfn = KVM_PFN_ERR_RO_FAULT;
+		goto out;
+	}
+
+	if (writable)
+		*writable = args.writable;
+	pfn = args.pfn;
+out:
+	follow_pfnmap_end(&args);
+	*p_pfn = pfn;
+
+	return r;
+}
+
+static bool vma_is_valid(struct vm_area_struct *vma, bool write_fault)
+{
+	if (unlikely(!(vma->vm_flags & VM_READ)))
+		return false;
+
+	if (write_fault && (unlikely(!(vma->vm_flags & VM_WRITE))))
+		return false;
+
+	return true;
+}
+
+static inline int check_user_page_hwpoison(unsigned long addr)
+{
+	int rc, flags = FOLL_HWPOISON | FOLL_WRITE;
+
+	rc = get_user_pages(addr, 1, flags, NULL);
+	return rc == -EHWPOISON;
+}
+
+static kvm_pfn_t hva_to_pfn(unsigned long addr, bool atomic, bool interruptible,
+		     bool *async, bool write_fault, bool *writable)
+{
+	struct vm_area_struct *vma;
+	kvm_pfn_t pfn;
+	int r;
+
+	mmap_read_lock(current->mm);
+retry:
+	vma = vma_lookup(current->mm, addr);
+
+	if (vma == NULL)
+		pfn = KVM_PFN_ERR_FAULT;
+	else if (vma->vm_flags & (VM_IO | VM_PFNMAP)) {
+		// Here we only expect MMIO for validation
+		r = hva_to_pfn_remapped(vma, addr, write_fault, writable, &pfn);
+		if (r == -EAGAIN)
+			goto retry;
+		if (r < 0)
+			pfn = KVM_PFN_ERR_FAULT;
+	} else {
+		if (async && vma_is_valid(vma, write_fault))
+			*async = true;
+		pfn = KVM_PFN_ERR_FAULT;
+	}
+
+	mmap_read_unlock(current->mm);
+	return pfn;
+}
+
+
+static int snp_mmio_rmp_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
+{
+	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
+	struct kvm_sev_snp_rmp_update params;
+	bool async = false, writable = false;
+	int ret;
+
+	if (!sev_snp_guest(kvm))
+		return -ENOTTY;
+
+	if (!sev->snp_context)
+		return -EINVAL;
+
+	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
+		return -EFAULT;
+
+	for (phys_addr_t off = 0; off < params.size; off += PAGE_SIZE) {
+		kvm_pfn_t pfn = hva_to_pfn(params.useraddr + off, false,
+					   false /*interruptible*/,
+					   &async, false, &writable);
+
+		if (is_error_pfn(pfn))
+			return -EINVAL;
+
+		if (params.flags & KVM_SEV_SNP_RMP_FLAG_PRIVATE)
+			ret = rmp_make_private_mmio(pfn, params.gpa + off, PG_LEVEL_4K,
+						    sev->asid, false/*Immutable*/);
+		else
+			ret = rmp_make_shared_mmio(pfn, PG_LEVEL_4K);
+		if (ret)
+			break;
+	}
+
+	return ret;
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 1dcc027ec77e..6e6bd3c2f7ec 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -978,7 +978,7 @@ static int adjust_direct_map(u64 pfn, int rmp_level)
  * The optimal solution would be range locking to avoid locking disjoint
  * regions unnecessarily but there's no support for that yet.
  */
-static int rmpupdate(u64 pfn, struct rmp_state *state)
+static int rmpupdate(u64 pfn, struct rmp_state *state, bool mmio)
 {
 	unsigned long paddr = pfn << PAGE_SHIFT;
 	int ret, level;
@@ -988,7 +988,7 @@ static int rmpupdate(u64 pfn, struct rmp_state *state)
 
 	level = RMP_TO_PG_LEVEL(state->pagesize);
 
-	if (adjust_direct_map(pfn, level))
+	if (!mmio && adjust_direct_map(pfn, level))
 		return -EFAULT;
 
 	do {
@@ -1022,10 +1022,25 @@ int rmp_make_private(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immut
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
@@ -1034,10 +1049,21 @@ int rmp_make_shared(u64 pfn, enum pg_level level)
 	memset(&state, 0, sizeof(state));
 	state.pagesize = PG_LEVEL_TO_RMP(level);
 
-	return rmpupdate(pfn, &state);
+	return rmpupdate(pfn, &state, false);
 }
 EXPORT_SYMBOL_GPL(rmp_make_shared);
 
+int rmp_make_shared_mmio(u64 pfn, enum pg_level level)
+{
+	struct rmp_state state;
+
+	memset(&state, 0, sizeof(state));
+	state.pagesize = PG_LEVEL_TO_RMP(level);
+
+	return rmpupdate(pfn, &state, true);
+}
+EXPORT_SYMBOL_GPL(rmp_make_shared_mmio);
+
 void snp_leak_pages(u64 pfn, unsigned int npages)
 {
 	struct page *page = pfn_to_page(pfn);

---

## [12] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 11/22] KVM: SEV: Add TIO VMGEXIT*

The SEV TIO spec defines a new TIO_GUEST_MESSAGE message to provide
a secure communication channel between a SNP VM and the PSP, very
similar to the GHCB GUEST MESSAGE. However the new call requires
additional information about the host and guest PCI BDFn and
the VM id (which is GCTX==guest context page). Since KVM does not
know PCI, it exits to QEMU which has all the pieces to make the call
to the PSP. This relies on necessary additional ioctl() are
implemented separately, such as:
- IOMMUFD "TDI bind" to bind a secure VF to a CoCo VM;
- IOMMUFD "Guest Request" to manage secure DMA and MMIO;
- SEV KVM ioctl() to call RMPUPDATE on MMIO ranges.

Define new VMGEXIT code - SEV_TIO_GUEST_REQUEST. Define its
parameters in kvm_run::kvm_user_vmgexit. These include:
- guest BDFn,
- GHCB request/response buffers (encrypted guest pages),
- space for certificate/measurements/interface repors
(non encrypted guest pages).

Some numeric values are out of order because numbers in between
have been used at different stages of KVM SEV-SNP upstreaming process.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 arch/x86/include/uapi/asm/svm.h |  2 +
 include/uapi/linux/kvm.h        | 24 +++++++
 arch/x86/kvm/svm/sev.c          | 70 ++++++++++++++++++++
 3 files changed, 96 insertions(+)

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
 
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 45e6d8fca9b9..cb3bc5b9c1e0 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -135,6 +135,28 @@ struct kvm_xen_exit {
 	} u;
 };
 
+struct kvm_user_vmgexit {
+#define KVM_USER_VMGEXIT_TIO_REQ	4
+	__u32 type; /* KVM_USER_VMGEXIT_* type */
+	union {
+		struct {
+			__u32 guest_rid;	/* in */
+			__u16 ret;		/* out */
+#define KVM_USER_VMGEXIT_TIO_REQ_FLAG_STATUS		BIT(0)
+#define KVM_USER_VMGEXIT_TIO_REQ_FLAG_MMIO_VALIDATE	BIT(1)
+#define KVM_USER_VMGEXIT_TIO_REQ_FLAG_MMIO_CONFIG	BIT(2)
+			__u8  flags;		/* in */
+			__u8  tdi_status;	/* out */
+			__u64 data_gpa;		/* in */
+			__u64 data_npages;	/* in/out */
+			__u64 req_spa;		/* in */
+			__u64 rsp_spa;		/* in */
+			__u64 mmio_gpa;		/* in */
+			__s32 fw_err;		/* out */
+		} tio_req;
+	};
+} __packed;
+
 #define KVM_S390_GET_SKEYS_NONE   1
 #define KVM_S390_SKEYS_MAX        1048576
 
@@ -178,6 +200,7 @@ struct kvm_xen_exit {
 #define KVM_EXIT_NOTIFY           37
 #define KVM_EXIT_LOONGARCH_IOCSR  38
 #define KVM_EXIT_MEMORY_FAULT     39
+#define KVM_EXIT_VMGEXIT          40
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -446,6 +469,7 @@ struct kvm_run {
 			__u64 gpa;
 			__u64 size;
 		} memory_fault;
+		struct kvm_user_vmgexit vmgexit;
 		/* Fix the size of the union. */
 		char padding[256];
 	};
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 4916b916c20a..ea1cf33191b5 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3390,6 +3390,8 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 		    control->exit_info_1 == control->exit_info_2)
 			goto vmgexit_err;
 		break;
+	case SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST:
+		break;
 	default:
 		reason = GHCB_ERR_INVALID_EVENT;
 		goto vmgexit_err;
@@ -4250,6 +4252,71 @@ static int snp_mmio_rmp_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return ret;
 }
 
+static int snp_complete_sev_tio_guest_request(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_svm *svm = to_svm(vcpu);
+	struct vmcb_control_area *control = &svm->vmcb->control;
+	gpa_t req_gpa = control->exit_info_1;
+	struct kvm *kvm = vcpu->kvm;
+	struct kvm_sev_info *sev;
+	u8 msg_type = 0;
+
+	if (!sev_snp_guest(kvm))
+		return -EINVAL;
+
+	sev = &to_kvm_svm(kvm)->sev_info;
+
+	if (kvm_read_guest(kvm, req_gpa + offsetof(struct snp_guest_msg_hdr, msg_type),
+			   &msg_type, 1))
+		return -EIO;
+
+	if (msg_type == TIO_MSG_TDI_INFO_REQ)
+		vcpu->arch.regs[VCPU_REGS_RDX] = vcpu->run->vmgexit.tio_req.tdi_status;
+
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+				SNP_GUEST_ERR(0, vcpu->run->vmgexit.tio_req.fw_err));
+
+	return 1; /* Resume guest */
+}
+
+static int snp_sev_tio_guest_request(struct kvm_vcpu *vcpu, gpa_t req_gpa, gpa_t resp_gpa)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct kvm_sev_info *sev;
+	u8 msg_type;
+
+	if (!sev_snp_guest(kvm))
+		return SEV_RET_INVALID_GUEST;
+
+	sev = &to_kvm_svm(kvm)->sev_info;
+
+	if (kvm_read_guest(kvm, req_gpa + offsetof(struct snp_guest_msg_hdr, msg_type),
+			   &msg_type, 1))
+		return -EIO;
+
+	vcpu->run->exit_reason = KVM_EXIT_VMGEXIT;
+	vcpu->run->vmgexit.type = KVM_USER_VMGEXIT_TIO_REQ;
+	vcpu->run->vmgexit.tio_req.guest_rid = vcpu->arch.regs[VCPU_REGS_RCX];
+	vcpu->run->vmgexit.tio_req.flags = 0;
+	if (msg_type == TIO_MSG_TDI_INFO_REQ)
+		vcpu->run->vmgexit.tio_req.flags |= KVM_USER_VMGEXIT_TIO_REQ_FLAG_STATUS;
+	if (msg_type == TIO_MSG_MMIO_VALIDATE_REQ) {
+		vcpu->run->vmgexit.tio_req.flags |= KVM_USER_VMGEXIT_TIO_REQ_FLAG_MMIO_VALIDATE;
+		vcpu->run->vmgexit.tio_req.mmio_gpa = vcpu->arch.regs[VCPU_REGS_RDX];
+	}
+	if (msg_type == TIO_MSG_MMIO_CONFIG_REQ) {
+		vcpu->run->vmgexit.tio_req.flags |= KVM_USER_VMGEXIT_TIO_REQ_FLAG_MMIO_CONFIG;
+		vcpu->run->vmgexit.tio_req.mmio_gpa = vcpu->arch.regs[VCPU_REGS_RDX];
+	}
+	vcpu->run->vmgexit.tio_req.data_gpa = vcpu->arch.regs[VCPU_REGS_RAX];
+	vcpu->run->vmgexit.tio_req.data_npages = vcpu->arch.regs[VCPU_REGS_RBX];
+	vcpu->run->vmgexit.tio_req.req_spa = req_gpa;
+	vcpu->run->vmgexit.tio_req.rsp_spa = resp_gpa;
+	vcpu->arch.complete_userspace_io = snp_complete_sev_tio_guest_request;
+
+	return 0; /* Exit KVM */
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4530,6 +4597,9 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 	case SVM_VMGEXIT_EXT_GUEST_REQUEST:
 		ret = snp_handle_ext_guest_req(svm, control->exit_info_1, control->exit_info_2);
 		break;
+	case SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST:
+		ret = snp_sev_tio_guest_request(vcpu, control->exit_info_1, control->exit_info_2);
+		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
 		vcpu_unimpl(vcpu,
 			    "vmgexit: unsupported event - exit_info_1=%#llx, exit_info_2=%#llx\n",

---

## [13] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

CoCo VMs get their private memory allocated from guest_memfd
("gmemfd") which is a KVM facility similar to memfd.
At the moment gmemfds cannot mmap() so the usual GUP API does
not work on these as expected.

Use the existing IOMMU_IOAS_MAP_FILE API to allow mapping from
fd + offset. Detect the gmemfd case in pfn_reader_user_pin() and
simplified mapping.

The long term plan is to ditch this workaround and follow
the usual memfd path.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/iommu/iommufd/pages.c | 88 +++++++++++++++++++-
 1 file changed, 87 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/iommufd/pages.c b/drivers/iommu/iommufd/pages.c
index 3427749bc5ce..457d8eaacd2c 100644
--- a/drivers/iommu/iommufd/pages.c
+++ b/drivers/iommu/iommufd/pages.c
@@ -53,6 +53,7 @@
 #include <linux/overflow.h>
 #include <linux/slab.h>
 #include <linux/sched/mm.h>
+#include <linux/pagemap.h>
 
 #include "double_span.h"
 #include "io_pagetable.h"
@@ -850,6 +851,88 @@ static long pin_memfd_pages(struct pfn_reader_user *user, unsigned long start,
 	return npages_out;
 }
 
+static bool is_guest_memfd(struct file *file)
+{
+	struct address_space *mapping = file_inode(file)->i_mapping;
+
+	return mapping_inaccessible(mapping) && mapping_unevictable(mapping);
+}
+
+static struct folio *guest_memfd_get_pfn(struct file *file, unsigned long index,
+					 unsigned long *pfn, int *max_order)
+{
+	struct folio *folio;
+	int ret = 0;
+
+	folio = filemap_grab_folio(file_inode(file)->i_mapping, index);
+
+	if (IS_ERR(folio))
+		return folio;
+
+	if (folio_test_hwpoison(folio)) {
+		folio_unlock(folio);
+		folio_put(folio);
+		return ERR_PTR(-EHWPOISON);
+	}
+
+	*pfn = folio_pfn(folio) + (index & (folio_nr_pages(folio) - 1));
+	if (!max_order)
+		goto unlock_exit;
+
+	/* Refs for unpin_user_page_range_dirty_lock->gup_put_folio(FOLL_PIN) */
+	ret = folio_add_pins(folio, 1);
+	folio_put(folio); /* Drop ref from filemap_grab_folio */
+
+unlock_exit:
+	folio_unlock(folio);
+	if (ret)
+		folio = ERR_PTR(ret);
+
+	return folio;
+}
+
+static long pin_guest_memfd_pages(struct pfn_reader_user *user, loff_t start, unsigned long npages,
+			       struct iopt_pages *pages)
+{
+	unsigned long offset = 0;
+	loff_t uptr = start;
+	long rc = 0;
+
+	for (unsigned long i = 0; i < npages; ++i, uptr += PAGE_SIZE) {
+		unsigned long gfn = 0, pfn = 0;
+		int max_order = 0;
+		struct folio *folio;
+
+		folio = guest_memfd_get_pfn(user->file, uptr >> PAGE_SHIFT, &pfn, &max_order);
+		if (IS_ERR(folio))
+			rc = PTR_ERR(folio);
+
+		if (rc == -EINVAL && i == 0) {
+			pr_err_once("Must be vfio mmio at gfn=%lx pfn=%lx, skipping\n", gfn, pfn);
+			return rc;
+		}
+
+		if (rc) {
+			pr_err("%s: %ld %ld %lx -> %lx\n", __func__,
+			       rc, i, (unsigned long) uptr, (unsigned long) pfn);
+			break;
+		}
+
+		if (i == 0)
+			offset = offset_in_folio(folio, start);
+
+		user->ufolios[i] = folio;
+	}
+
+	if (!rc) {
+		rc = npages;
+		user->ufolios_next = user->ufolios;
+		user->ufolios_offset = offset;
+	}
+
+	return rc;
+}
+
 static int pfn_reader_user_pin(struct pfn_reader_user *user,
 			       struct iopt_pages *pages,
 			       unsigned long start_index,
@@ -903,7 +986,10 @@ static int pfn_reader_user_pin(struct pfn_reader_user *user,
 
 	if (user->file) {
 		start = pages->start + (start_index * PAGE_SIZE);
-		rc = pin_memfd_pages(user, start, npages);
+		if (is_guest_memfd(user->file))
+			rc = pin_guest_memfd_pages(user, start, npages, pages);
+		else
+			rc = pin_memfd_pages(user, start, npages);
 	} else if (!remote_mm) {
 		uptr = (uintptr_t)(pages->uptr + start_index * PAGE_SIZE);
 		rc = pin_user_pages_fast(uptr, npages, user->gup_flags,

---

## [14] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 13/22] iommufd: amd-iommu: Add vdevice support*

The new AMD SEV-TIO feature allows DMA to/from encrypted memory and
encrypted MMIO for use in CoCo VMs (SEV-SNP). The secure part of IOMMU
is called sDTE ("Secure DTE") which resides in private memory and
controlled by the PSP. sDTEs of passed through devices are in the TCB
of CoCo VMs and inaccessible by the host OS.

Implement vdevice in the AMD IOMMU host OS to represent the host instance
of a secure IOMMU which is visible to the guest. This will be used for
GHCB TIO GUEST REQUEST to manage secure sDTE and MMIO.

Most parts of insecure DTE move to sDTE so DTEs need to be adjusted.
At the moment this includes "domain_id" (moves to sDTE) and
"IOTLB enable" (should stay in sync with sDTE).

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/iommu/amd/amd_iommu_types.h |  2 +
 include/uapi/linux/iommufd.h        |  1 +
 drivers/iommu/amd/iommu.c           | 60 +++++++++++++++++++-
 3 files changed, 61 insertions(+), 2 deletions(-)

diff --git a/drivers/iommu/amd/amd_iommu_types.h b/drivers/iommu/amd/amd_iommu_types.h
index b086fb632990..b5513bf05b27 100644
--- a/drivers/iommu/amd/amd_iommu_types.h
+++ b/drivers/iommu/amd/amd_iommu_types.h
@@ -593,6 +593,8 @@ struct protection_domain {
 
 	struct mmu_notifier mn;	/* mmu notifier for the SVA domain */
 	struct list_head dev_data_list; /* List of pdom_dev_data */
+
+	struct amd_viommu *aviommu;
 };
 
 /*
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 78747b24bd0f..b346fa11955c 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -939,6 +939,7 @@ struct iommu_fault_alloc {
 enum iommu_viommu_type {
 	IOMMU_VIOMMU_TYPE_DEFAULT = 0,
 	IOMMU_VIOMMU_TYPE_ARM_SMMUV3 = 1,
+	IOMMU_VIOMMU_TYPE_TSM = 2,
 };
 
 /**
diff --git a/drivers/iommu/amd/iommu.c b/drivers/iommu/amd/iommu.c
index b48a72bd7b23..076c58d61d5e 100644
--- a/drivers/iommu/amd/iommu.c
+++ b/drivers/iommu/amd/iommu.c
@@ -30,6 +30,7 @@
 #include <linux/percpu.h>
 #include <linux/io-pgtable.h>
 #include <linux/cc_platform.h>
+#include <linux/iommufd.h>
 #include <asm/irq_remapping.h>
 #include <asm/io_apic.h>
 #include <asm/apic.h>
@@ -2068,7 +2069,18 @@ static void set_dte_entry(struct amd_iommu *iommu,
 		new.data[1] |= DTE_FLAG_IOTLB;
 
 	old_domid = READ_ONCE(dte->data[1]) & DEV_DOMID_MASK;
-	new.data[1] |= domid;
+
+	if (domain->aviommu) {
+		/*
+		 * This runs when VFIO is bound to a device but TDI is not yet.
+		 * Ideally TSM should change DTE only when TDI is bound.
+		 */
+		dev_info(dev_data->dev, "Skip DomainID=%x and set bit96\n", domid);
+		new.data[1] |= 1ULL << (96 - 64);
+	} else {
+		dev_info(dev_data->dev, "Not skip DomainID=%x and not set bit96\n", domid);
+		new.data[1] |= domid;
+	}
 
 	/*
 	 * Restore cached persistent DTE bits, which can be set by information
@@ -2549,12 +2561,15 @@ amd_iommu_domain_alloc_paging_flags(struct device *dev, u32 flags,
 {
 	struct amd_iommu *iommu = get_amd_iommu_from_dev(dev);
 	const u32 supported_flags = IOMMU_HWPT_ALLOC_DIRTY_TRACKING |
+						IOMMU_HWPT_ALLOC_PASID |
+						IOMMU_HWPT_ALLOC_NEST_PARENT;
+	const u32 supported_flags2 = IOMMU_HWPT_ALLOC_DIRTY_TRACKING |
 						IOMMU_HWPT_ALLOC_PASID;
 
 	if ((flags & ~supported_flags) || user_data)
 		return ERR_PTR(-EOPNOTSUPP);
 
-	switch (flags & supported_flags) {
+	switch (flags & supported_flags2) {
 	case IOMMU_HWPT_ALLOC_DIRTY_TRACKING:
 		/* Allocate domain with v1 page table for dirty tracking */
 		if (!amd_iommu_hd_support(iommu))
@@ -3015,6 +3030,46 @@ static int amd_iommu_dev_disable_feature(struct device *dev,
 	return ret;
 }
 
+struct amd_viommu {
+	struct iommufd_viommu core;
+	struct protection_domain *domain;
+};
+
+static void amd_viommu_destroy(struct iommufd_viommu *viommu)
+{
+	struct amd_viommu *aviommu = container_of(viommu, struct amd_viommu, core);
+
+	if (!aviommu->domain)
+		return;
+	aviommu->domain->aviommu = NULL;
+}
+
+
+static const struct iommufd_viommu_ops amd_viommu_ops = {
+	.destroy = amd_viommu_destroy,
+};
+
+static struct iommufd_viommu *amd_viommu_alloc(struct device *dev,
+					       struct iommu_domain *parent,
+					       struct iommufd_ctx *ictx,
+					       unsigned int viommu_type)
+{
+	struct amd_viommu *aviommu;
+	struct protection_domain *domain = to_pdomain(parent);
+
+	if (viommu_type != IOMMU_VIOMMU_TYPE_TSM)
+		return ERR_PTR(-EOPNOTSUPP);
+
+	aviommu = iommufd_viommu_alloc(ictx, struct amd_viommu, core, &amd_viommu_ops);
+	if (IS_ERR(aviommu))
+		return ERR_CAST(aviommu);
+
+	aviommu->domain = domain;
+	domain->aviommu = aviommu;
+
+	return &aviommu->core;
+}
+
 const struct iommu_ops amd_iommu_ops = {
 	.capable = amd_iommu_capable,
 	.blocked_domain = &blocked_domain,
@@ -3031,6 +3086,7 @@ const struct iommu_ops amd_iommu_ops = {
 	.dev_enable_feat = amd_iommu_dev_enable_feature,
 	.dev_disable_feat = amd_iommu_dev_disable_feature,
 	.page_response = amd_iommu_page_response,
+	.viommu_alloc = amd_viommu_alloc,
 	.default_domain_ops = &(const struct iommu_domain_ops) {
 		.attach_dev	= amd_iommu_attach_device,
 		.map_pages	= amd_iommu_map_pages,

---

## [15] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

When a TDISP-capable device is passed through, it is configured as
a shared device to begin with. Later on when a VM probes the device,
detects its TDISP capability (reported via the PCIe ExtCap bit
called "TEE-IO"), performs the device attestation and transitions it
to a secure state when the device can run encrypted DMA and respond
to encrypted MMIO accesses.

Since KVM is out of the TCB, secure enablement is done in the secure
firmware. The API requires PCI host/guest BDFns, a KVM id hence such
calls are routed via IOMMUFD, primarily because allowing secure DMA
is the major performance bottleneck and it is a function of IOMMU.

Add TDI bind to do the initial binding of a passed through PCI
function to a VM. Add a forwarder for TIO GUEST REQUEST. These two
call into the TSM which forwards the calls to the PSP.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

Both enabling secure DMA (== "SDTE Write") and secure MMIO (== "MMIO
validate") are TIO GUEST REQUEST messages. These are encrypted and
the HV (==IOMMUFD or KVM or VFIO) cannot see them unless the guest
shares some via kvm_run::kvm_user_vmgexit (and then QEMU passes those
via ioctls).

This RFC routes all TIO GUEST REQUESTs via IOMMUFD which arguably should
only do so only for "SDTE Write" and leave "MMIO validate" for VFIO.
---
 drivers/iommu/iommufd/iommufd_private.h |   3 +
 include/uapi/linux/iommufd.h            |  25 +++++
 drivers/iommu/iommufd/main.c            |   6 ++
 drivers/iommu/iommufd/viommu.c          | 112 ++++++++++++++++++++
 4 files changed, 146 insertions(+)

diff --git a/drivers/iommu/iommufd/iommufd_private.h b/drivers/iommu/iommufd/iommufd_private.h
index 0b1bafc7fd99..47a6fb5da253 100644
--- a/drivers/iommu/iommufd/iommufd_private.h
+++ b/drivers/iommu/iommufd/iommufd_private.h
@@ -546,6 +546,8 @@ int iommufd_viommu_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_viommu_destroy(struct iommufd_object *obj);
 int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd);
 void iommufd_vdevice_destroy(struct iommufd_object *obj);
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd);
+int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd);
 
 struct iommufd_vdevice {
 	struct iommufd_object obj;
@@ -553,6 +555,7 @@ struct iommufd_vdevice {
 	struct iommufd_viommu *viommu;
 	struct device *dev;
 	u64 id; /* per-vIOMMU virtual ID */
+	bool tsm_bound;
 };
 
 #ifdef CONFIG_IOMMUFD_TEST
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index b346fa11955c..0af15dcabd23 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -55,6 +55,8 @@ enum {
 	IOMMUFD_CMD_VIOMMU_ALLOC = 0x90,
 	IOMMUFD_CMD_VDEVICE_ALLOC = 0x91,
 	IOMMUFD_CMD_IOAS_CHANGE_PROCESS = 0x92,
+	IOMMUFD_CMD_VDEVICE_TSM_BIND = 0x93,
+	IOMMUFD_CMD_VDEVICE_TSM_GUEST_REQUEST = 0x94,
 };
 
 /**
@@ -1015,4 +1017,27 @@ struct iommu_ioas_change_process {
 #define IOMMU_IOAS_CHANGE_PROCESS \
 	_IO(IOMMUFD_TYPE, IOMMUFD_CMD_IOAS_CHANGE_PROCESS)
 
+struct iommu_vdevice_tsm_bind {
+	__u32 size;
+	__u32 viommu_id;
+	__u32 dev_id;
+	__u32 vdevice_id;
+	__s32 kvmfd;
+	__u32 pad;
+} __packed;
+#define IOMMU_VDEVICE_TSM_BIND _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_BIND)
+
+struct iommu_vdevice_tsm_guest_request {
+	__u32 size;
+	__u32 viommu_id;
+	__u32 dev_id;
+	__u32 vdevice_id;
+	__u8 *req;
+	__u8 *rsp;
+	__u32 rsp_len;
+	__u32 req_len;
+	__s32 fw_err;
+} __packed;
+#define IOMMU_VDEVICE_TSM_GUEST_REQUEST _IO(IOMMUFD_TYPE, IOMMUFD_CMD_VDEVICE_TSM_GUEST_REQUEST)
+
 #endif
diff --git a/drivers/iommu/iommufd/main.c b/drivers/iommu/iommufd/main.c
index ccf616462a1c..c9152ef3dcab 100644
--- a/drivers/iommu/iommufd/main.c
+++ b/drivers/iommu/iommufd/main.c
@@ -310,6 +310,8 @@ union ucmd_buffer {
 	struct iommu_vdevice_alloc vdev;
 	struct iommu_vfio_ioas vfio_ioas;
 	struct iommu_viommu_alloc viommu;
+	struct iommu_vdevice_tsm_bind bind;
+	struct iommu_vdevice_tsm_guest_request gr;
 #ifdef CONFIG_IOMMUFD_TEST
 	struct iommu_test_cmd test;
 #endif
@@ -367,6 +369,10 @@ static const struct iommufd_ioctl_op iommufd_ioctl_ops[] = {
 		 __reserved),
 	IOCTL_OP(IOMMU_VIOMMU_ALLOC, iommufd_viommu_alloc_ioctl,
 		 struct iommu_viommu_alloc, out_viommu_id),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_BIND, iommufd_vdevice_tsm_bind_ioctl,
+		 struct iommu_vdevice_tsm_bind, pad),
+	IOCTL_OP(IOMMU_VDEVICE_TSM_GUEST_REQUEST, iommufd_vdevice_tsm_guest_request_ioctl,
+		 struct iommu_vdevice_tsm_guest_request, fw_err),
 #ifdef CONFIG_IOMMUFD_TEST
 	IOCTL_OP(IOMMU_TEST_CMD, iommufd_test, struct iommu_test_cmd, last),
 #endif
diff --git a/drivers/iommu/iommufd/viommu.c b/drivers/iommu/iommufd/viommu.c
index 69b88e8c7c26..936d8a71a3ef 100644
--- a/drivers/iommu/iommufd/viommu.c
+++ b/drivers/iommu/iommufd/viommu.c
@@ -2,6 +2,7 @@
 /* Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES
  */
 #include "iommufd_private.h"
+#include "linux/tsm.h"
 
 void iommufd_viommu_destroy(struct iommufd_object *obj)
 {
@@ -88,6 +89,15 @@ void iommufd_vdevice_destroy(struct iommufd_object *obj)
 		container_of(obj, struct iommufd_vdevice, obj);
 	struct iommufd_viommu *viommu = vdev->viommu;
 
+	if (vdev->tsm_bound) {
+		struct tsm_tdi *tdi = tsm_tdi_get(vdev->dev);
+
+		if (tdi) {
+			tsm_tdi_unbind(tdi);
+			tsm_tdi_put(tdi);
+		}
+	}
+
 	/* xa_cmpxchg is okay to fail if alloc failed xa_cmpxchg previously */
 	xa_cmpxchg(&viommu->vdevs, vdev->id, vdev, NULL, GFP_KERNEL);
 	refcount_dec(&viommu->obj.users);
@@ -155,3 +165,105 @@ int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
 	iommufd_put_object(ucmd->ictx, &viommu->obj);
 	return rc;
 }
+
+int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_tsm_bind *cmd = ucmd->cmd;
+	struct iommufd_viommu *viommu;
+	struct iommufd_vdevice *vdev;
+	struct iommufd_device *idev;
+	struct tsm_tdi *tdi;
+	int rc = 0;
+
+	viommu = iommufd_get_viommu(ucmd, cmd->viommu_id);
+	if (IS_ERR(viommu))
+		return PTR_ERR(viommu);
+
+	idev = iommufd_get_device(ucmd, cmd->dev_id);
+	if (IS_ERR(idev)) {
+		rc = PTR_ERR(idev);
+		goto out_put_viommu;
+	}
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(idev)) {
+		rc = PTR_ERR(idev);
+		goto out_put_dev;
+	}
+
+	tdi = tsm_tdi_get(idev->dev);
+	if (!tdi) {
+		rc = -ENODEV;
+		goto out_put_vdev;
+	}
+
+	rc = tsm_tdi_bind(tdi, vdev->id, cmd->kvmfd);
+	if (rc)
+		goto out_put_tdi;
+
+	vdev->tsm_bound = true;
+
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+out_put_tdi:
+	tsm_tdi_put(tdi);
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+out_put_dev:
+	iommufd_put_object(ucmd->ictx, &idev->obj);
+out_put_viommu:
+	iommufd_put_object(ucmd->ictx, &viommu->obj);
+	return rc;
+}
+
+int iommufd_vdevice_tsm_guest_request_ioctl(struct iommufd_ucmd *ucmd)
+{
+	struct iommu_vdevice_tsm_guest_request *cmd = ucmd->cmd;
+	struct iommufd_viommu *viommu;
+	struct iommufd_vdevice *vdev;
+	struct iommufd_device *idev;
+	struct tsm_tdi *tdi;
+	int rc = 0, fw_err = 0;
+
+	viommu = iommufd_get_viommu(ucmd, cmd->viommu_id);
+	if (IS_ERR(viommu))
+		return PTR_ERR(viommu);
+
+	idev = iommufd_get_device(ucmd, cmd->dev_id);
+	if (IS_ERR(idev)) {
+		rc = PTR_ERR(idev);
+		goto out_put_viommu;
+	}
+
+	vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+					       IOMMUFD_OBJ_VDEVICE),
+			    struct iommufd_vdevice, obj);
+	if (IS_ERR(idev)) {
+		rc = PTR_ERR(idev);
+		goto out_put_dev;
+	}
+
+	tdi = tsm_tdi_get(idev->dev);
+	if (!tdi) {
+		rc = -ENODEV;
+		goto out_put_vdev;
+	}
+
+	rc = tsm_guest_request(tdi, cmd->req, cmd->req_len, cmd->rsp, cmd->rsp_len, &fw_err);
+	if (rc)
+		goto out_put_tdi;
+
+	cmd->fw_err = fw_err;
+	rc = iommufd_ucmd_respond(ucmd, sizeof(*cmd));
+
+out_put_tdi:
+	tsm_tdi_put(tdi);
+out_put_vdev:
+	iommufd_put_object(ucmd->ictx, &vdev->obj);
+out_put_dev:
+	iommufd_put_object(ucmd->ictx, &idev->obj);
+out_put_viommu:
+	iommufd_put_object(ucmd->ictx, &viommu->obj);
+	return rc;
+}

---

## [16] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 15/22] KVM: X86: Handle private MMIO as shared*

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
index 74c20dbb92da..32e27080b1c7 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4347,7 +4347,11 @@ static int __kvm_mmu_faultin_pfn(struct kvm_vcpu *vcpu,
 {
 	unsigned int foll = fault->write ? FOLL_WRITE : 0;
 
-	if (fault->is_private)
+	if (fault->slot && fault->is_private && !kvm_slot_can_be_private(fault->slot) &&
+	    (vcpu->kvm->arch.vm_type == KVM_X86_SNP_VM))
+		pr_warn("%s: private SEV TIO MMIO fault for fault->gfn=%llx\n",
+			__func__, fault->gfn);
+	else if (fault->is_private)
 		return kvm_mmu_faultin_pfn_private(vcpu, fault);
 
 	foll |= FOLL_NOWAIT;

---

## [17] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 16/22] coco/tsm: Add tsm-guest module*

The "coco/tsm: Add tsm and tsm-host modules" added a common TSM library
and the host module which initialises contexts for secure devices on
the host.

Guests use some of the host sysfs interface and define their own, hence
a new module - TSM GUEST.

Note that the module is made bus-agnostic, like TSM-HOST.

New device nodes provide sysfs interface for fetching device certificates
and measurements and TDI interface reports.

A platform is expected to register itself in TSM-GUEST and provide
necessary callbacks. No platform is added here, AMD SEV is coming in the
next patches.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/guest/Makefile    |   3 +
 include/linux/device.h              |   4 +
 include/linux/tsm.h                 |  20 ++
 drivers/virt/coco/guest/tsm-guest.c | 291 ++++++++++++++++++++
 drivers/virt/coco/host/tsm-host.c   |   1 +
 drivers/virt/coco/tsm.c             |   2 +
 Documentation/virt/coco/tsm.rst     |  33 +++
 drivers/virt/coco/guest/Kconfig     |   3 +
 drivers/virt/coco/sev-guest/Kconfig |   1 +
 9 files changed, 358 insertions(+)

diff --git a/drivers/virt/coco/guest/Makefile b/drivers/virt/coco/guest/Makefile
index b3b217af77cf..60b688ab816a 100644
--- a/drivers/virt/coco/guest/Makefile
+++ b/drivers/virt/coco/guest/Makefile
@@ -1,3 +1,6 @@
 # SPDX-License-Identifier: GPL-2.0
 obj-$(CONFIG_TSM_REPORTS)	+= tsm_report.o
 tsm_report-y := report.o
+
+obj-$(CONFIG_TSM_GUEST) += tsm_guest.o
+tsm_guest-y := tsm-guest.o
diff --git a/include/linux/device.h b/include/linux/device.h
index 80a5b3268986..e813575b848b 100644
--- a/include/linux/device.h
+++ b/include/linux/device.h
@@ -843,6 +843,10 @@ struct device {
 #ifdef CONFIG_IOMMU_DMA
 	bool			dma_iommu:1;
 #endif
+#if defined(CONFIG_TSM_GUEST) || defined(CONFIG_TSM_GUEST_MODULE)
+	bool			tdi_enabled:1;
+	bool			tdi_validated:1;
+#endif
 };
 
 /**
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 486e386d90fc..9e25b1a99c19 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -353,6 +353,20 @@ struct tsm_hv_ops {
 	int (*tdi_status)(struct tsm_tdi *tdi, struct tsm_tdi_status *ts);
 };
 
+/* featuremask for tdi_validate */
+/* TODO: use it */
+#define TDI_VALIDATE_DMA	BIT(0)
+#define TDI_VALIDATE_MMIO	BIT(1)
+
+struct tsm_vm_ops {
+	int (*tdi_validate)(struct tsm_tdi *tdi, unsigned int featuremask,
+			    bool invalidate, void *private_data);
+	int (*tdi_mmio_config)(struct tsm_tdi *tdi, u64 start, u64 size,
+			       bool tee, void *private_data);
+	int (*tdi_status)(struct tsm_tdi *tdi, void *private_data,
+			  struct tsm_tdi_status *ts);
+};
+
 struct tsm_subsys {
 	struct device dev;
 	struct list_head tdi_head;
@@ -372,6 +386,12 @@ struct tsm_host_subsys;
 struct tsm_host_subsys *tsm_host_register(struct device *parent,
 					  struct tsm_hv_ops *hvops,
 					  void *private_data);
+struct tsm_guest_subsys;
+struct tsm_guest_subsys *tsm_guest_register(struct device *parent,
+					    struct tsm_vm_ops *vmops,
+					    void *private_data);
+void tsm_guest_unregister(struct tsm_guest_subsys *gsubsys);
+
 struct tsm_dev *tsm_dev_get(struct device *dev);
 void tsm_dev_put(struct tsm_dev *tdev);
 struct tsm_tdi *tsm_tdi_get(struct device *dev);
diff --git a/drivers/virt/coco/guest/tsm-guest.c b/drivers/virt/coco/guest/tsm-guest.c
new file mode 100644
index 000000000000..d3be089308e0
--- /dev/null
+++ b/drivers/virt/coco/guest/tsm-guest.c
@@ -0,0 +1,291 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include <linux/module.h>
+#include <linux/tsm.h>
+
+#define DRIVER_VERSION	"0.1"
+#define DRIVER_AUTHOR	"aik@amd.com"
+#define DRIVER_DESC	"TSM guest library"
+
+struct tsm_guest_subsys {
+	struct tsm_subsys base;
+	struct tsm_vm_ops *ops;
+	void *private_data;
+	struct notifier_block notifier;
+};
+
+static int tsm_tdi_measurements_locked(struct tsm_dev *tdev)
+{
+	struct tsm_guest_subsys *gsubsys = (struct tsm_guest_subsys *) tdev->tsm;
+	struct tsm_tdi_status tstmp = { 0 };
+	struct tsm_tdi *tdi = tsm_tdi_get(tdev->physdev);
+
+	if (!tdi)
+		return -EFAULT;
+
+	return gsubsys->ops->tdi_status(tdi, gsubsys->private_data, &tstmp);
+}
+
+static int tsm_tdi_validate(struct tsm_tdi *tdi, unsigned int featuremask, bool invalidate)
+{
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_guest_subsys *gsubsys = (struct tsm_guest_subsys *) tdev->tsm;
+	int ret;
+
+	if (!tdi || !gsubsys->ops->tdi_validate)
+		return -EPERM;
+
+	ret = gsubsys->ops->tdi_validate(tdi, featuremask, invalidate, gsubsys->private_data);
+	if (ret) {
+		tdi->dev.parent->tdi_validated = false;
+		dev_err(tdi->dev.parent, "TDI is not validated, ret=%d\n", ret);
+	} else {
+		tdi->dev.parent->tdi_validated = true;
+		dev_info(tdi->dev.parent, "TDI validated\n");
+	}
+
+	return ret;
+}
+
+//int tsm_tdi_mmio_config(struct tsm_tdi *tdi, u64 start, u64 end, bool tee)
+//{
+//	struct tsm_dev *tdev = tdi->tdev;
+//	struct tsm_guest_subsys *gsubsys = (struct tsm_guest_subsys *) tdev->tsm;
+//	int ret;
+//
+//	if (!tdi || !gsubsys->ops->tdi_mmio_config)
+//		return -EPERM;
+//
+//	ret = gsubsys->ops->tdi_mmio_config(tdi, start, end, tee, gsubsys->private_data);
+//
+//	return ret;
+//}
+//EXPORT_SYMBOL_GPL(tsm_tdi_mmio_config);
+
+static int tsm_tdi_status(struct tsm_tdi *tdi, void *private_data, struct tsm_tdi_status *ts)
+{
+	struct tsm_tdi_status tstmp = { 0 };
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_guest_subsys *gsubsys = (struct tsm_guest_subsys *) tdev->tsm;
+	int ret;
+
+	ret = gsubsys->ops->tdi_status(tdi, private_data, &tstmp);
+	if (!ret)
+		*ts = tstmp;
+
+	return ret;
+}
+
+static ssize_t tsm_tdi_validate_store(struct device *dev, struct device_attribute *attr,
+				      const char *buf, size_t count)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+	unsigned long val;
+	ssize_t ret;
+
+	if (kstrtoul(buf, 0, &val) < 0)
+		return -EINVAL;
+
+	if (val) {
+		ret = tsm_tdi_validate(tdi, TDI_VALIDATE_DMA | TDI_VALIDATE_MMIO, false);
+		if (ret)
+			return ret;
+	} else {
+		tsm_tdi_validate(tdi, TDI_VALIDATE_DMA | TDI_VALIDATE_MMIO, true);
+	}
+
+	tdi->validated = val;
+
+	return count;
+}
+
+static ssize_t tsm_tdi_validate_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+
+	return sysfs_emit(buf, "%u\n", tdi->validated);
+}
+
+static DEVICE_ATTR_RW(tsm_tdi_validate);
+
+static char *spdm_algos_to_str(u64 algos, char *buf, size_t len)
+{
+	size_t n = 0;
+
+	buf[0] = 0;
+#define __ALGO(x) do {								\
+		if ((n < len) && (algos & (1ULL << (TSM_SPDM_ALGOS_##x))))	\
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
+	__ST(CONFIG_UNLOCKED);
+	__ST(CONFIG_LOCKED);
+	__ST(RUN);
+	__ST(ERROR);
+#undef __ST
+	default: return "unknown";
+	}
+}
+
+static ssize_t tsm_tdi_status_user_show(struct device *dev,
+					struct device_attribute *attr,
+					char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_guest_subsys *gsubsys = (struct tsm_guest_subsys *) tdev->tsm;
+	struct tsm_tdi_status ts = { 0 };
+	char algos[256] = "";
+	unsigned int n, m;
+	int ret;
+
+	ret = tsm_tdi_status(tdi, gsubsys->private_data, &ts);
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
+		     "report_counter=%lld\n"
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
+		     ts.spdm_algos, spdm_algos_to_str(ts.spdm_algos, algos, sizeof(algos) - 1),
+		     ts.intf_report_counter);
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
+static DEVICE_ATTR_RO(tsm_tdi_status_user);
+
+static ssize_t tsm_tdi_status_show(struct device *dev, struct device_attribute *attr, char *buf)
+{
+	struct tsm_tdi *tdi = container_of(dev, struct tsm_tdi, dev);
+	struct tsm_dev *tdev = tdi->tdev;
+	struct tsm_guest_subsys *gsubsys = (struct tsm_guest_subsys *) tdev->tsm;
+	struct tsm_tdi_status ts = { 0 };
+	u8 state;
+	int ret;
+
+	ret = tsm_tdi_status(tdi, gsubsys->private_data, &ts);
+	if (ret)
+		return ret;
+
+	state = ts.state;
+	memcpy(buf, &state, sizeof(state));
+
+	return sizeof(state);
+}
+
+static DEVICE_ATTR_RO(tsm_tdi_status);
+
+static struct attribute *tdi_attrs[] = {
+	&dev_attr_tsm_tdi_validate.attr,
+	&dev_attr_tsm_tdi_status_user.attr,
+	&dev_attr_tsm_tdi_status.attr,
+	NULL,
+};
+
+static const struct attribute_group tdi_group = {
+	.attrs = tdi_attrs,
+};
+
+struct tsm_guest_subsys *tsm_guest_register(struct device *parent,
+					    struct tsm_vm_ops *vmops,
+					    void *private_data)
+{
+	struct tsm_subsys *subsys = tsm_register(parent, sizeof(struct tsm_guest_subsys),
+						 NULL, &tdi_group,
+						 tsm_tdi_measurements_locked);
+	struct tsm_guest_subsys *gsubsys;
+
+	gsubsys = (struct tsm_guest_subsys *) subsys;
+
+	if (IS_ERR(gsubsys))
+		return gsubsys;
+
+	gsubsys->ops = vmops;
+	gsubsys->private_data = private_data;
+
+	return gsubsys;
+}
+EXPORT_SYMBOL_GPL(tsm_guest_register);
+
+void tsm_guest_unregister(struct tsm_guest_subsys *gsubsys)
+{
+	tsm_unregister(&gsubsys->base);
+}
+EXPORT_SYMBOL_GPL(tsm_guest_unregister);
+
+static int __init tsm_init(void)
+{
+	int ret = 0;
+
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION "\n");
+
+	return ret;
+}
+
+static void __exit tsm_exit(void)
+{
+	pr_info(DRIVER_DESC " version: " DRIVER_VERSION " shutdown\n");
+}
+
+module_init(tsm_init);
+module_exit(tsm_exit);
+
+MODULE_VERSION(DRIVER_VERSION);
+MODULE_LICENSE("GPL");
+MODULE_AUTHOR(DRIVER_AUTHOR);
+MODULE_DESCRIPTION(DRIVER_DESC);
diff --git a/drivers/virt/coco/host/tsm-host.c b/drivers/virt/coco/host/tsm-host.c
index 5d23a3871009..7a37327fded8 100644
--- a/drivers/virt/coco/host/tsm-host.c
+++ b/drivers/virt/coco/host/tsm-host.c
@@ -474,6 +474,7 @@ void tsm_tdi_unbind(struct tsm_tdi *tdi)
 	}
 
 	tdi->guest_rid = 0;
+	tdi->dev.parent->tdi_enabled = false;
 }
 EXPORT_SYMBOL_GPL(tsm_tdi_unbind);
 
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index b6235d1210ca..a6979d51f029 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -442,6 +442,8 @@ int tsm_tdi_init(struct tsm_dev *tdev, struct device *parent)
 		goto free_exit;
 
 	tdi->tdev = tdev;
+	tdi->dev.parent->tdi_enabled = true;
+	tdi->dev.parent->tdi_validated = false;
 
 	return 0;
 
diff --git a/Documentation/virt/coco/tsm.rst b/Documentation/virt/coco/tsm.rst
index 7cb5f1862492..203cc9c8411d 100644
--- a/Documentation/virt/coco/tsm.rst
+++ b/Documentation/virt/coco/tsm.rst
@@ -90,6 +90,39 @@ The sysfs example from a host with a TDISP capable device:
 /sys/devices/pci0000:a0/0000:a0:07.1/0000:a9:00.5/tsm/tsm0
 
 
+The sysfs example from a guest with a TDISP capable device:
+
+~> find /sys -iname "*tsm*"
+/sys/kernel/config/tsm
+/sys/class/tsm-tdi
+/sys/class/tsm
+/sys/class/tsm/tsm0
+/sys/class/tsm-dev
+/sys/devices/platform/sev-guest/tsm
+/sys/devices/platform/sev-guest/tsm/tsm0
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm_dev
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-tdi
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-tdi/tdi:0000:01:00.0/tsm_tdi_status
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-tdi/tdi:0000:01:00.0/tsm_tdi_validate
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-tdi/tdi:0000:01:00.0/tsm_tdi_status_user
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-tdi/tdi:0000:01:00.0/tsm_report_user
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-tdi/tdi:0000:01:00.0/tsm_report
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-dev
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-dev/tdev:0000:01:00.0/tsm_certs
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-dev/tdev:0000:01:00.0/tsm_nonce
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-dev/tdev:0000:01:00.0/tsm_meas_user
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-dev/tdev:0000:01:00.0/tsm_certs_user
+/sys/devices/pci0000:00/0000:00:02.0/0000:01:00.0/tsm-dev/tdev:0000:01:00.0/tsm_meas
+/sys/module/tsm_pci
+/sys/module/sev_guest/parameters/tsm_vtom
+/sys/module/sev_guest/parameters/tsm_enable
+/sys/module/tsm_report
+/sys/module/tsm
+/sys/module/tsm/holders/tsm_pci
+/sys/module/tsm/holders/tsm_guest
+/sys/module/tsm_guest
+
+
 References
 ==========
 
diff --git a/drivers/virt/coco/guest/Kconfig b/drivers/virt/coco/guest/Kconfig
index ed9bafbdd854..30f0235f0113 100644
--- a/drivers/virt/coco/guest/Kconfig
+++ b/drivers/virt/coco/guest/Kconfig
@@ -5,3 +5,6 @@
 config TSM_REPORTS
 	select CONFIGFS_FS
 	tristate
+
+config TSM_GUEST
+	tristate
diff --git a/drivers/virt/coco/sev-guest/Kconfig b/drivers/virt/coco/sev-guest/Kconfig
index a6405ab6c2c3..148af36772ff 100644
--- a/drivers/virt/coco/sev-guest/Kconfig
+++ b/drivers/virt/coco/sev-guest/Kconfig
@@ -3,6 +3,7 @@ config SEV_GUEST
 	default m
 	depends on AMD_MEM_ENCRYPT
 	select TSM_REPORTS
+	select TSM_GUEST
 	help
 	  SEV-SNP firmware provides the guest a mechanism to communicate with
 	  the PSP without risk from a malicious hypervisor who wishes to read,

---

## [18] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 17/22] resource: Mark encrypted MMIO resource on validation*

In order to allow encrypted MMIO, a TDISP device needs to have it set up
as "TEE" (means "trusted") and the platform needs to allow accessing it
as encrypted (which is "pvalidate"'ed in AMD terms).

Once TDISP MMIO validation succeeded, a resource needs to be mapped as
encrypted or the device will reject it.

Add encrypt_resource() which marks the resource as "validated".
The TSM module is going to call this API.

Modify __ioremap_check_encrypted() to look for the new flag to allow
ioremap() correctly map encrypted resources.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

Should it also be IORESOURCE_BUSY?
---
 include/linux/ioport.h |  2 +
 arch/x86/mm/ioremap.c  |  2 +
 kernel/resource.c      | 48 ++++++++++++++++++++
 3 files changed, 52 insertions(+)

diff --git a/include/linux/ioport.h b/include/linux/ioport.h
index 5385349f0b8a..f2e0b9f02373 100644
--- a/include/linux/ioport.h
+++ b/include/linux/ioport.h
@@ -55,6 +55,7 @@ struct resource {
 #define IORESOURCE_MEM_64	0x00100000
 #define IORESOURCE_WINDOW	0x00200000	/* forwarded by bridge */
 #define IORESOURCE_MUXED	0x00400000	/* Resource is software muxed */
+#define IORESOURCE_VALIDATED	0x00800000	/* TDISP validated */
 
 #define IORESOURCE_EXT_TYPE_BITS 0x01000000	/* Resource extended types */
 #define IORESOURCE_SYSRAM	0x01000000	/* System RAM (modifier) */
@@ -248,6 +249,7 @@ extern int allocate_resource(struct resource *root, struct resource *new,
 struct resource *lookup_resource(struct resource *root, resource_size_t start);
 int adjust_resource(struct resource *res, resource_size_t start,
 		    resource_size_t size);
+int encrypt_resource(struct resource *res, unsigned int flags);
 resource_size_t resource_alignment(struct resource *res);
 
 /**
diff --git a/arch/x86/mm/ioremap.c b/arch/x86/mm/ioremap.c
index 38ff7791a9c7..748f39af127a 100644
--- a/arch/x86/mm/ioremap.c
+++ b/arch/x86/mm/ioremap.c
@@ -100,6 +100,8 @@ static unsigned int __ioremap_check_encrypted(struct resource *res)
 	switch (res->desc) {
 	case IORES_DESC_NONE:
 	case IORES_DESC_RESERVED:
+		if (res->flags & IORESOURCE_VALIDATED)
+			return IORES_MAP_ENCRYPTED;
 		break;
 	default:
 		return IORES_MAP_ENCRYPTED;
diff --git a/kernel/resource.c b/kernel/resource.c
index 12004452d999..c5a80da58033 100644
--- a/kernel/resource.c
+++ b/kernel/resource.c
@@ -503,6 +503,13 @@ int walk_mem_res(u64 start, u64 end, void *arg,
 {
 	unsigned long flags = IORESOURCE_MEM | IORESOURCE_BUSY;
 
+	int ret =  __walk_iomem_res_desc(start, end, flags, IORES_DESC_NONE, arg,
+				     func);
+	if (ret < 0)
+		return ret;
+
+	flags = IORESOURCE_MEM | IORESOURCE_VALIDATED;
+
 	return __walk_iomem_res_desc(start, end, flags, IORES_DESC_NONE, arg,
 				     func);
 }
@@ -1085,6 +1092,47 @@ int adjust_resource(struct resource *res, resource_size_t start,
 }
 EXPORT_SYMBOL(adjust_resource);
 
+int encrypt_resource(struct resource *res, unsigned int flags)
+{
+	struct resource *p;
+	int result = 0;
+
+	if (!res)
+		return -EINVAL;
+
+	write_lock(&resource_lock);
+
+	for_each_resource(&iomem_resource, p, false) {
+		/* If we passed the resource we are looking for, stop */
+		if (p->start > res->end) {
+			p = NULL;
+			break;
+		}
+
+		/* Skip until we find a range that matches what we look for */
+		if (p->end < res->start)
+			continue;
+
+		if (p->start == res->start && p->end == res->end) {
+			if ((p->flags & res->flags) != res->flags)
+				p = NULL;
+			break;
+		}
+	}
+
+	if (p) {
+		p->flags = (p->flags & ~(IORESOURCE_VALIDATED)) | flags;
+		res->flags = (res->flags & ~(IORESOURCE_VALIDATED)) | flags;
+	} else {
+		result = -EINVAL;
+	}
+
+	write_unlock(&resource_lock);
+
+	return result;
+}
+EXPORT_SYMBOL(encrypt_resource);
+
 static void __init
 __reserve_region_with_split(struct resource *root, resource_size_t start,
 			    resource_size_t end, const char *name)

---

## [19] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 18/22] coco/sev-guest: Implement the guest support for SEV TIO*

Define tsm_ops for the guest and forward the ops calls to the HV via
SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST.
Do the attestation report examination and enable MMIO.

In this RFC exercise, encrypted DMA supported for Coco VMs. Secure DMA
is allowed to all memory below "vTOM" (set now to the possible maximum
so all DMA is encrypted) after the VM performs "validation" via GHCB
TIO GUEST REQUEST "sDTE write" call to the secure fw.

Encrypted MMIO is possible to TEE regions in the VF (==TDI) interface
report and requires accepting MMIO ranges into the guest TCB which is
done in 2 steps:
- the HV RMPUPDATEs the ranges;
- the guest accepts them via GHCB TIO GUEST REQUEST "MMIO validate"
call to the secure fw (which is AMD's "pvalidate" for MMIO).

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/sev-guest/Makefile        |   2 +-
 arch/x86/include/asm/sev.h                  |   9 +
 include/uapi/linux/sev-guest.h              |  39 ++
 arch/x86/coco/sev/core.c                    |  19 +-
 drivers/virt/coco/sev-guest/sev_guest.c     |  10 +
 drivers/virt/coco/sev-guest/sev_guest_tio.c | 738 ++++++++++++++++++++
 6 files changed, 815 insertions(+), 2 deletions(-)

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
index 2cae72b618d0..a396dbcdee68 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -119,6 +119,8 @@ struct snp_req_data {
 	unsigned long resp_gpa;
 	unsigned long data_gpa;
 	unsigned int data_npages;
+	unsigned int guest_rid;
+	unsigned long param;
 };
 
 #define MAX_AUTHTAG_LEN		32
@@ -306,6 +308,11 @@ struct snp_guest_dev {
 		struct snp_derived_key_req derived_key;
 		struct snp_ext_report_req ext_report;
 	} req;
+
+#if defined(CONFIG_PCI_TSM) || defined(CONFIG_PCI_TSM_MODULE)
+	struct tsm_guest_subsys *tsm;
+	struct tsm_bus_subsys *tsm_bus;
+#endif
 };
 
 /*
@@ -516,6 +523,8 @@ void *snp_alloc_shared_pages(size_t sz);
 void snp_free_shared_pages(void *buf, size_t sz);
 int snp_send_guest_request(struct snp_msg_desc *mdesc, struct snp_guest_req *req,
 			   u64 *exitinfo2);
+struct snp_guest_dev;
+void sev_guest_tsm_set_ops(bool set, struct snp_guest_dev *snp_dev);
 
 void __init snp_secure_tsc_prepare(void);
 void __init snp_secure_tsc_init(void);
diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
index fcdfea767fca..48b6df3d3298 100644
--- a/include/uapi/linux/sev-guest.h
+++ b/include/uapi/linux/sev-guest.h
@@ -13,6 +13,7 @@
 #define __UAPI_LINUX_SEV_GUEST_H_
 
 #include <linux/types.h>
+#include <linux/uuid.h>
 
 #define SNP_REPORT_USER_DATA_SIZE 64
 
@@ -96,4 +97,42 @@ struct snp_ext_report_req {
 #define SNP_GUEST_VMM_ERR_INVALID_LEN	1
 #define SNP_GUEST_VMM_ERR_BUSY		2
 
+/*
+ * TIO_GUEST_REQUEST's TIO_MSG_MMIO_VALIDATE_REQ
+ * encoding for MMIO in RDX:
+ *
+ * ........ ....GGGG GGGGGGGG GGGGGGGG GGGGGGGG GGGGGGGG GGGGOOOO OOOOTrrr
+ * Where:
+ *	G - guest physical address
+ *	O - order of 4K pages
+ *	T - TEE (valid for TIO_MSG_MMIO_CONFIG_REQ)
+ *	r - range id == BAR
+ */
+#define MMIO_VALIDATE_GPA(r)      ((r) & 0x000FFFFFFFFFF000ULL)
+#define MMIO_VALIDATE_LEN(r)      (1ULL << (12 + (((r) >> 4) & 0xFF)))
+#define MMIO_VALIDATE_RANGEID(r)  ((r) & 0x7)
+#define MMIO_VALIDATE_RESERVED(r) ((r) & 0xFFF0000000000000ULL)
+#define MMIO_CONFIG_TEE		  BIT(3)
+
+#define MMIO_MK_VALIDATE(start, size, range_id, tee) \
+	(MMIO_VALIDATE_GPA(start) | (get_order(size >> 12) << 4) | \
+	((range_id) & 0xFF) | ((tee)?MMIO_CONFIG_TEE:0))
+
+/* Optional Certificates/measurements/report data from TIO_GUEST_REQUEST */
+struct tio_blob_table_entry {
+	guid_t guid;
+	__u32 offset;
+	__u32 length;
+} __packed;
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
 #endif /* __UAPI_LINUX_SEV_GUEST_H_ */
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index c680057c13fa..c78a5db0feb5 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2592,6 +2592,11 @@ static int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input,
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
@@ -2601,6 +2606,8 @@ static int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input,
 	*exitinfo2 = ghcb->save.sw_exit_info_2;
 	switch (*exitinfo2) {
 	case 0:
+		if (exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST)
+			input->param = ghcb_get_rdx(ghcb);
 		break;
 
 	case SNP_GUEST_VMM_ERR(SNP_GUEST_VMM_ERR_BUSY):
@@ -2613,6 +2620,10 @@ static int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input,
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
@@ -2974,7 +2985,8 @@ static int verify_and_dec_payload(struct snp_msg_desc *mdesc, struct snp_guest_r
 		return -EBADMSG;
 
 	/* Verify response message type and version number. */
-	if (resp_msg_hdr->msg_type != (req_msg_hdr->msg_type + 1) ||
+	if ((resp_msg_hdr->msg_type != (req_msg_hdr->msg_type + 1) &&
+	     (resp_msg_hdr->msg_type != (req_msg_hdr->msg_type - 0x80))) ||
 	    resp_msg_hdr->msg_version != req_msg_hdr->msg_version)
 		return -EBADMSG;
 
@@ -3047,6 +3059,11 @@ static int __handle_guest_request(struct snp_msg_desc *mdesc, u64 exit_code,
 	rc = snp_issue_guest_request(exit_code, input, exitinfo2);
 	switch (rc) {
 	case -ENOSPC:
+		if (exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST) {
+			pr_warn("SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST => -ENOSPC");
+			break;
+		}
+
 		/*
 		 * If the extended guest request fails due to having too
 		 * small of a certificate data buffer, retry the same
diff --git a/drivers/virt/coco/sev-guest/sev_guest.c b/drivers/virt/coco/sev-guest/sev_guest.c
index 4e79da7cb0d2..f8d5261595b9 100644
--- a/drivers/virt/coco/sev-guest/sev_guest.c
+++ b/drivers/virt/coco/sev-guest/sev_guest.c
@@ -43,6 +43,10 @@ static int vmpck_id = -1;
 module_param(vmpck_id, int, 0444);
 MODULE_PARM_DESC(vmpck_id, "The VMPCK ID to use when communicating with the PSP.");
 
+static bool tsm_enable = true;
+module_param(tsm_enable, bool, 0644);
+MODULE_PARM_DESC(tsm_enable, "Enable SEV TIO");
+
 static inline struct snp_guest_dev *to_snp_dev(struct file *file)
 {
 	struct miscdevice *dev = file->private_data;
@@ -635,6 +639,10 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	snp_dev->msg_desc = mdesc;
 	dev_info(dev, "Initialized SEV guest driver (using VMPCK%d communication key)\n",
 		 mdesc->vmpck_id);
+
+	if (tsm_enable)
+		sev_guest_tsm_set_ops(true, snp_dev);
+
 	return 0;
 
 e_msg_init:
@@ -648,6 +656,8 @@ static void __exit sev_guest_remove(struct platform_device *pdev)
 	struct snp_guest_dev *snp_dev = platform_get_drvdata(pdev);
 
 	snp_msg_free(snp_dev->msg_desc);
+	if (tsm_enable)
+		sev_guest_tsm_set_ops(false, snp_dev);
 	misc_deregister(&snp_dev->misc);
 }
 
diff --git a/drivers/virt/coco/sev-guest/sev_guest_tio.c b/drivers/virt/coco/sev-guest/sev_guest_tio.c
new file mode 100644
index 000000000000..7faa810a2823
--- /dev/null
+++ b/drivers/virt/coco/sev-guest/sev_guest_tio.c
@@ -0,0 +1,738 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include <linux/bitfield.h>
+#include <linux/pci.h>
+#include <linux/psp-sev.h>
+#include <linux/tsm.h>
+#include <crypto/gcm.h>
+#include <uapi/linux/sev-guest.h>
+
+#include <asm/svm.h>
+#include <asm/sev.h>
+
+#define TIO_MESSAGE_VERSION	1
+
+ulong tsm_vtom = 0x7fffffff;
+module_param(tsm_vtom, ulong, 0644);
+MODULE_PARM_DESC(tsm_vtom, "SEV TIO vTOM value");
+
+#define tdi_to_pci_dev(tdi) (to_pci_dev(tdi->dev.parent))
+
+/*
+ * Status codes from TIO_MSG_SDTE_WRITE_RSP
+ */
+enum sdte_write_status {
+	SDTE_WRITE_SUCCESS = 0,
+	SDTE_WRITE_INVALID_TDI = 1,
+	SDTE_WRITE_TDI_NOT_BOUND = 2,
+	SDTE_WRITE_RESERVED = 3,
+};
+
+/*
+ * Status codes from TIO_MSG_MMIO_VALIDATE_REQ
+ */
+enum mmio_validate_status {
+	MMIO_VALIDATE_SUCCESS = 0,
+	MMIO_VALIDATE_INVALID_TDI = 1,
+	MMIO_VALIDATE_TDI_UNBOUND = 2,
+	/* At least one page is not assigned to the guest */
+	MMIO_VALIDATE_NOT_ASSIGNED = 3,
+	/* The Validated bit is not uniformly set for the MMIO subrange */
+	MMIO_VALIDATE_NOT_UNIFORM = 4,
+	/* At least one page does not have immutable bit set when validated bit is clear */
+	MMIO_VALIDATE_NOT_IMMUTABLE = 5,
+	/* At least one page is not mapped to the expected GPA */
+	MMIO_VALIDATE_NOT_MAPPED = 6,
+	/* The provided MMIO range ID is not reported in the interface report */
+	MMIO_VALIDATE_NOT_REPORTED = 7,
+	/* The subrange is out the MMIO range in the interface report */
+	MMIO_VALIDATE_OUT_OF_RANGE = 8,
+};
+
+/*
+ * Status codes from TIO_MSG_MMIO_CONFIG_REQ
+ */
+enum mmio_config_status {
+	MMIO_CONFIG_SUCCESS = 0,
+	MMIO_CONFIG_INVALID_TDI = 1,
+	MMIO_CONFIG_TDI_UNBOUND = 2,
+	 /* The provided MMIO range ID is not reported in the interface report */
+	MMIO_CONFIG_NOT_REPORTED = 3,
+	/* One or more attributes could not be changed */
+	MMIO_CONFIG_COULD_NOT_CHANGE = 4,
+};
+
+static int handle_tio_guest_request(struct snp_guest_dev *snp_dev, u8 type,
+				   void *req_buf, size_t req_sz, void *resp_buf, u32 resp_sz,
+				   void *pt, u64 *npages, u64 *bdfn, u64 *param, u64 *fw_err)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	struct snp_guest_req req = {
+		.msg_version = TIO_MESSAGE_VERSION,
+	};
+	u64 exitinfo2 = 0;
+	int ret;
+
+	req.msg_type = type;
+	req.vmpck_id = mdesc->vmpck_id;
+	req.req_buf = req_buf;
+	req.req_sz = req_sz;
+	req.resp_buf = resp_buf;
+	req.resp_sz = resp_sz;
+	req.exit_code = SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST;
+
+	req.input.guest_rid = 0;
+	req.input.param = 0;
+
+	if (pt && npages) {
+		req.data = pt;
+		req.input.data_npages = *npages;
+	}
+	if (bdfn)
+		req.input.guest_rid = *bdfn;
+	if (param)
+		req.input.param = *param;
+
+	ret = snp_send_guest_request(mdesc, &req, &exitinfo2);
+
+	if (param)
+		*param = req.input.param;
+
+	*fw_err = exitinfo2;
+
+	return ret;
+}
+
+static int guest_request_tio_data(struct snp_guest_dev *snp_dev, u8 type,
+				   void *req_buf, size_t req_sz, void *resp_buf, u32 resp_sz,
+				   u64 bdfn, enum tsm_tdisp_state *state,
+				   struct tsm_blob **certs, struct tsm_blob **meas,
+				   struct tsm_blob **report, u64 *fw_err)
+{
+	u64 npages = SZ_32K >> PAGE_SHIFT, c1, param = 0;
+	struct tio_blob_table_entry *pt;
+	int rc;
+
+	pt = snp_alloc_shared_pages(npages << PAGE_SHIFT);
+	if (!pt)
+		return -ENOMEM;
+
+	c1 = npages;
+	rc = handle_tio_guest_request(snp_dev, type, req_buf, req_sz, resp_buf, resp_sz,
+				      pt, &c1, &bdfn, state ? &param : NULL, fw_err);
+
+	if (c1 > SZ_32K) {
+		snp_free_shared_pages(pt, npages);
+		npages = c1;
+		pt = snp_alloc_shared_pages(npages << PAGE_SHIFT);
+		if (!pt)
+			return -ENOMEM;
+
+		rc = handle_tio_guest_request(snp_dev, type, req_buf, req_sz, resp_buf, resp_sz,
+					      pt, &c1, &bdfn, state ? &param : NULL, fw_err);
+	}
+	if (rc)
+		return rc;
+
+	tsm_blob_free(*meas);
+	tsm_blob_free(*certs);
+	tsm_blob_free(*report);
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
+		b = tsm_blob_new(ptr, len);
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
+	snp_free_shared_pages(pt, npages);
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
+	__u64 tdi_report_count;
+	__u64 reserved2;
+} __packed;
+
+static int tio_tdi_status(struct tsm_tdi *tdi, struct snp_guest_dev *snp_dev,
+			  struct tsm_tdi_status *ts)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_tdi_info_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_tdi_info_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_tdi_info_req req = {
+		.guest_device_id = pci_dev_id(tdi_to_pci_dev(tdi)),
+	};
+	u64 fw_err = 0;
+	int rc;
+	enum tsm_tdisp_state state = 0;
+
+	dev_notice(&tdi->dev, "TDI info");
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = guest_request_tio_data(snp_dev, TIO_MSG_TDI_INFO_REQ, &req,
+				     sizeof(req), rsp, resp_len,
+				     pci_dev_id(tdi_to_pci_dev(tdi)), &state,
+				     &tdi->tdev->certs, &tdi->tdev->meas,
+				     &tdi->report, &fw_err);
+	if (rc)
+		goto free_exit;
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
+	 (1ULL << TSM_SPDM_ALGOS_##y) : 0)
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
+	ts->intf_report_counter = rsp->tdi_report_count;
+
+	ts->valid = true;
+	ts->state = state;
+	/* The response buffer contains the sensitive data, explicitly clear it. */
+free_exit:
+	memzero_explicit(&rsp, sizeof(resp_len));
+	kfree(rsp);
+	return rc;
+}
+
+struct tio_msg_mmio_validate_req {
+	__u16 guest_device_id;
+	__u16 reserved1;
+	__u8 reserved2[12];
+	__u64 subrange_base;
+	__u32 subrange_page_count;
+	__u32 range_offset;
+	union {
+		__u16 flags;
+		struct {
+			__u16 validated:1; /* Desired value to set RMP.Validated for the range */
+			/*
+			 * Force validated:
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
+			/* Validated bit has changed due to this operation */
+			__u16 changed:1;
+		};
+	};
+	__u16 range_id;
+	__u8 reserved2[12];
+} __packed;
+
+static int mmio_validate_range(struct snp_guest_dev *snp_dev, struct pci_dev *pdev,
+			       unsigned int range_id, resource_size_t start, resource_size_t size,
+			       bool invalidate, u64 *fw_err, u16 *status)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_mmio_validate_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_mmio_validate_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_mmio_validate_req req = { 0 };
+	u64 bdfn = pci_dev_id(pdev);
+	u64 mmio_val = MMIO_MK_VALIDATE(start, size, range_id, !invalidate);
+	int rc;
+
+	if (!rsp)
+		return -ENOMEM;
+
+	if (!invalidate)
+		req = (struct tio_msg_mmio_validate_req) {
+			.guest_device_id = pci_dev_id(pdev),
+			.subrange_base = start,
+			.subrange_page_count = size >> PAGE_SHIFT,
+			.range_offset = 0,
+			.validated = 1, /* Desired value to set RMP.Validated for the range */
+			.force_validated = 0,
+			.range_id = range_id,
+		};
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_MMIO_VALIDATE_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, &mmio_val, fw_err);
+	if (rc)
+		goto free_exit;
+
+	*status = rsp->status;
+
+free_exit:
+	/* The response buffer contains the sensitive data, explicitly clear it. */
+	memzero_explicit(&rsp, sizeof(resp_len));
+	kfree(rsp);
+	return rc;
+}
+
+struct tio_msg_mmio_config_req {
+	__u16 guest_device_id;
+	__u16 reserved1;
+	struct {
+		__u32 reserved2:2;
+		__u32 is_non_tee_mem:1;
+		__u32 reserved3:13;
+		__u32 range_id:16;
+	};
+	struct {
+		__u32 write:1; /* 0: read; 1: Write configuration of range */
+		__u32 reserved4:31;
+	};
+	__u8 reserved5[4];
+} __packed;
+
+struct tio_msg_mmio_config_rsp {
+	__u16 guest_device_id;
+	__u16 status; /* mmio_config_status */
+	struct {
+		__u32 msix_table:1;
+		__u32 msix_pba:1;
+		__u32 is_non_tee_mem:1;
+		__u32 is_mem_attr_updateable:1;
+		__u32 reserved1:12;
+		__u32 range_id:16;
+	};
+	struct {
+		__u32 write:1; /* 0: read; 1: Write configuration of range */
+		__u32 reserved2:31;
+	};
+	__u8 reserved3[4];
+} __packed;
+
+static int mmio_config_get(struct snp_guest_dev *snp_dev, struct pci_dev *pdev,
+			   unsigned int range_id, bool *updateable, bool *is_non_tee,
+			   u64 *fw_err, u16 *status)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_mmio_config_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_mmio_config_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_mmio_config_req req = {
+		.guest_device_id = pci_dev_id(pdev),
+		.is_non_tee_mem = 0,
+		.range_id = range_id,
+		.write = 0,
+	};
+	u64 bdfn = pci_dev_id(pdev);
+	int rc;
+
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_MMIO_CONFIG_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, NULL, fw_err);
+	if (rc)
+		goto free_exit;
+
+	*status = rsp->status;
+	*updateable = rsp->is_mem_attr_updateable;
+	*is_non_tee = rsp->is_non_tee_mem;
+
+free_exit:
+	/* The response buffer contains the sensitive data, explicitly clear it. */
+	memzero_explicit(&rsp, sizeof(resp_len));
+	kfree(rsp);
+	return rc;
+}
+
+static int mmio_config_range(struct snp_guest_dev *snp_dev, struct pci_dev *pdev,
+			     unsigned int range_id, resource_size_t start, resource_size_t size,
+			     bool tee, u64 *fw_err, u16 *status)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_mmio_config_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_mmio_config_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_mmio_config_req req = {
+		.guest_device_id = pci_dev_id(pdev),
+//		We kinda want these but the spec does not define them (yet?)
+//		.subrange_base = start,
+//		.subrange_page_count = size >> PAGE_SHIFT,
+//		.range_offset = 0,
+		.is_non_tee_mem = !tee,
+		.range_id = range_id,
+		.write = 1,
+	};
+	u64 bdfn = pci_dev_id(pdev);
+	u64 mmio_val = MMIO_MK_VALIDATE(start, size, range_id, tee);
+	int rc;
+
+	if (!rsp)
+		return -ENOMEM;
+
+	if (tee)
+		mmio_val |= MMIO_CONFIG_TEE;
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_MMIO_CONFIG_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, &mmio_val, fw_err);
+	if (rc)
+		goto free_exit;
+
+	*status = rsp->status;
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
+	struct pci_dev *pdev = tdi_to_pci_dev(tdi);
+	struct tdi_report_mmio_range mr;
+	unsigned int range_id;
+	struct resource *r;
+	u16 mmio_status;
+	u64 fw_err = 0;
+	int i = 0, rc;
+
+	pci_notice(pdev, "MMIO validate");
+
+	if (WARN_ON_ONCE(!tdi->report || !tdi->report->data))
+		return -EFAULT;
+
+	for (i = 0; i < TDI_REPORT_MR_NUM(tdi->report); ++i) {
+		mr = TDI_REPORT_MR(tdi->report, i);
+		range_id = FIELD_GET(TSM_TDI_REPORT_MMIO_RANGE_ID, mr.range_attributes);
+		r = pci_resource_n(pdev, range_id);
+
+		if (r->end == r->start || ((r->end - r->start + 1) & ~PAGE_MASK) || !mr.num) {
+			pci_warn(pdev, "Skipping broken range [%d] #%d %d pages, %llx..%llx\n",
+				i, range_id, mr.num, r->start, r->end);
+			continue;
+		}
+
+		if (FIELD_GET(TSM_TDI_REPORT_MMIO_IS_NON_TEE, mr.range_attributes)) {
+			pci_info(pdev, "Skipping non-TEE range [%d] #%d %d pages, %llx..%llx\n",
+				 i, range_id, mr.num, r->start, r->end);
+			continue;
+		}
+
+		/* Currently not supported */
+		if (FIELD_GET(TSM_TDI_REPORT_MMIO_MSIX_TABLE, mr.range_attributes) ||
+		    FIELD_GET(TSM_TDI_REPORT_MMIO_PBA, mr.range_attributes)) {
+			pci_info(pdev, "Skipping MSIX (%ld/%ld) range [%d] #%d %d pages, %llx..%llx\n",
+				 FIELD_GET(TSM_TDI_REPORT_MMIO_MSIX_TABLE, mr.range_attributes),
+				 FIELD_GET(TSM_TDI_REPORT_MMIO_PBA, mr.range_attributes),
+				 i, range_id, mr.num, r->start, r->end);
+			continue;
+		}
+
+		mmio_status = 0;
+		rc = mmio_validate_range(snp_dev, pdev, range_id,
+					 r->start, r->end - r->start + 1, invalidate, &fw_err,
+					 &mmio_status);
+		if (rc || fw_err != SEV_RET_SUCCESS || mmio_status != MMIO_VALIDATE_SUCCESS) {
+			pci_err(pdev, "MMIO #%d %llx..%llx validation failed 0x%llx %d\n",
+				range_id, r->start, r->end, fw_err, mmio_status);
+			continue;
+		}
+
+		rc = encrypt_resource(pci_resource_n(pdev, range_id),
+				      invalidate ? 0 : IORESOURCE_VALIDATED);
+		if (rc) {
+			pci_err(pdev, "MMIO #%d %llx..%llx failed to reserve\n",
+				range_id, r->start, r->end);
+			continue;
+		}
+
+		/* Try to make MMIO shared */
+		if (invalidate) {
+			bool updateable = false, is_non_tee = false;
+			u16 status = 0;
+
+			rc = mmio_config_get(snp_dev, pdev, range_id, &updateable,
+					     &is_non_tee, &fw_err, &status);
+			if (rc || fw_err) {
+				pci_err(pdev, "MMIO #%d %llx..%llx failed to get config\n",
+					range_id, r->start, r->end);
+				continue;
+			}
+
+			pci_notice(pdev, "[%d] #%d: updateable=%d is_non_tee=%d\n",
+				   i, range_id, updateable, is_non_tee);
+
+			if (!updateable || is_non_tee)
+				continue;
+
+			rc = mmio_config_range(snp_dev, pdev, range_id,
+					       r->start, r->end - r->start + 1,
+					       false, &fw_err, &status);
+			if (rc) {
+				pci_err(pdev, "MMIO #%d %llx..%llx failed to set config\n",
+					range_id, r->start, r->end);
+				continue;
+			}
+
+			pci_notice(pdev, "[%d] #%d: setting config rc=%d status=%d\n",
+				   i, range_id, rc, status);
+		}
+
+		pci_notice(pdev, "MMIO #%d %llx..%llx %s\n",  range_id, r->start, r->end,
+			   invalidate ? "invalidated" : "validated");
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
+struct tio_msg_sdte_write_rsp {
+	__u16 guest_device_id;
+	__u16 status; /* SDTE_WRITE_xxx */
+	__u8 reserved[12];
+} __packed;
+
+static int tio_tdi_sdte_write(struct tsm_tdi *tdi, struct snp_guest_dev *snp_dev, bool invalidate)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_sdte_write_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_sdte_write_rsp *rsp = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_sdte_write_req req;
+	u64 fw_err = 0;
+	u64 bdfn = pci_dev_id(tdi_to_pci_dev(tdi));
+	int rc;
+
+	BUILD_BUG_ON(sizeof(struct sdte) * 8 != 512);
+
+	if (!invalidate)
+		req = (struct tio_msg_sdte_write_req) {
+			.guest_device_id = pci_dev_id(tdi_to_pci_dev(tdi)),
+			.sdte.vmpl = 0,
+			.sdte.vtom = tsm_vtom,
+			.sdte.vtom_en = 1,
+			.sdte.iw = 1,
+			.sdte.ir = 1,
+			.sdte.v = 1,
+		};
+	else
+		req = (struct tio_msg_sdte_write_req) {
+			.guest_device_id = pci_dev_id(tdi_to_pci_dev(tdi)),
+		};
+
+	dev_notice(&tdi->dev, "SDTE write vTOM=%lx", (unsigned long) req.sdte.vtom << 21);
+
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_SDTE_WRITE_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, NULL, &fw_err);
+	if (rc) {
+		dev_err(&tdi->dev, "SDTE write failed with 0x%llx\n", fw_err);
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
+static int sev_guest_tdi_status(struct tsm_tdi *tdi, void *private_data,
+				struct tsm_tdi_status *ts)
+{
+	struct snp_guest_dev *snp_dev = private_data;
+
+	return tio_tdi_status(tdi, snp_dev, ts);
+}
+
+static int sev_guest_tdi_validate(struct tsm_tdi *tdi, unsigned int featuremask,
+				  bool invalidate, void *private_data)
+{
+	struct snp_guest_dev *snp_dev = private_data;
+	struct tsm_tdi_status ts = { 0 };
+	int ret;
+
+	if (!tdi->report) {
+		ret = tio_tdi_status(tdi, snp_dev, &ts);
+
+		if (ret || !tdi->report) {
+			dev_err(&tdi->dev, "No report available, ret=%d", ret);
+			if (!ret && tdi->report)
+				ret = -EIO;
+			return ret;
+		}
+
+		if (ts.state != TDISP_STATE_RUN) {
+			dev_err(&tdi->dev, "Not in RUN state, state=%d instead", ts.state);
+			return -EIO;
+		}
+	}
+
+	ret = tio_tdi_sdte_write(tdi, snp_dev, invalidate);
+	if (ret)
+		return ret;
+
+	/* MMIO validation result is stored as IORESOURCE_VALIDATED */
+	tio_tdi_mmio_validate(tdi, snp_dev, invalidate);
+
+	return 0;
+}
+
+struct tsm_vm_ops sev_guest_tsm_ops = {
+	.tdi_validate = sev_guest_tdi_validate,
+	.tdi_status = sev_guest_tdi_status,
+};
+
+void sev_guest_tsm_set_ops(bool set, struct snp_guest_dev *snp_dev)
+{
+#if defined(CONFIG_PCI_TSM) || defined(CONFIG_PCI_TSM_MODULE)
+	if (set) {
+		snp_dev->tsm = tsm_guest_register(snp_dev->dev, &sev_guest_tsm_ops, snp_dev);
+		snp_dev->tsm_bus = pci_tsm_register((struct tsm_subsys *) snp_dev->tsm);
+	} else {
+		if (snp_dev->tsm_bus)
+			pci_tsm_unregister(snp_dev->tsm_bus);
+		if (snp_dev->tsm)
+			tsm_unregister((struct tsm_subsys *) snp_dev->tsm);
+		snp_dev->tsm_bus = NULL;
+		snp_dev->tsm = NULL;
+	}
+#endif
+}

---

## [20] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 19/22] RFC: pci: Add BUS_NOTIFY_PCI_BUS_MASTER event*

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
 include/linux/device/bus.h          |  3 ++
 drivers/pci/pci.c                   |  3 ++
 drivers/virt/coco/guest/tsm-guest.c | 35 ++++++++++++++++++++
 3 files changed, 41 insertions(+)

diff --git a/include/linux/device/bus.h b/include/linux/device/bus.h
index f5a56efd2bd6..12f46ca69239 100644
--- a/include/linux/device/bus.h
+++ b/include/linux/device/bus.h
@@ -278,8 +278,11 @@ enum bus_notifier_event {
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
index b462bab597f7..3aeaa583cd92 100644
--- a/drivers/pci/pci.c
+++ b/drivers/pci/pci.c
@@ -4294,6 +4294,9 @@ static void __pci_set_master(struct pci_dev *dev, bool enable)
 		pci_write_config_word(dev, PCI_COMMAND, cmd);
 	}
 	dev->is_busmaster = enable;
+
+	if (enable)
+		bus_notify(&dev->dev, BUS_NOTIFY_PCI_BUS_MASTER);
 }
 
 /**
diff --git a/drivers/virt/coco/guest/tsm-guest.c b/drivers/virt/coco/guest/tsm-guest.c
index d3be089308e0..d30e49c154e0 100644
--- a/drivers/virt/coco/guest/tsm-guest.c
+++ b/drivers/virt/coco/guest/tsm-guest.c
@@ -2,6 +2,7 @@
 
 #include <linux/module.h>
 #include <linux/tsm.h>
+#include <linux/pci.h>
 
 #define DRIVER_VERSION	"0.1"
 #define DRIVER_AUTHOR	"aik@amd.com"
@@ -241,6 +242,36 @@ static const struct attribute_group tdi_group = {
 	.attrs = tdi_attrs,
 };
 
+/* In case BUS_NOTIFY_PCI_BUS_MASTER is no good, a driver can call pci_dev_tdi_validate() */
+int pci_dev_tdi_validate(struct pci_dev *pdev, bool invalidate)
+{
+	struct tsm_tdi *tdi = tsm_tdi_get(&pdev->dev);
+	int ret;
+
+	if (!tdi)
+		return -EFAULT;
+
+	ret = tsm_tdi_validate(tdi, TDI_VALIDATE_DMA | TDI_VALIDATE_MMIO, invalidate);
+
+	tsm_tdi_put(tdi);
+	return ret;
+}
+EXPORT_SYMBOL_GPL(pci_dev_tdi_validate);
+
+static int tsm_guest_pci_bus_notifier(struct notifier_block *nb, unsigned long action, void *data)
+{
+	switch (action) {
+	case BUS_NOTIFY_UNBOUND_DRIVER:
+		pci_dev_tdi_validate(to_pci_dev(data), true);
+		break;
+	case BUS_NOTIFY_PCI_BUS_MASTER:
+		pci_dev_tdi_validate(to_pci_dev(data), false);
+		break;
+	}
+
+	return NOTIFY_OK;
+}
+
 struct tsm_guest_subsys *tsm_guest_register(struct device *parent,
 					    struct tsm_vm_ops *vmops,
 					    void *private_data)
@@ -258,12 +289,16 @@ struct tsm_guest_subsys *tsm_guest_register(struct device *parent,
 	gsubsys->ops = vmops;
 	gsubsys->private_data = private_data;
 
+	gsubsys->notifier.notifier_call = tsm_guest_pci_bus_notifier;
+	bus_register_notifier(&pci_bus_type, &gsubsys->notifier);
+
 	return gsubsys;
 }
 EXPORT_SYMBOL_GPL(tsm_guest_register);
 
 void tsm_guest_unregister(struct tsm_guest_subsys *gsubsys)
 {
+	bus_unregister_notifier(&pci_bus_type, &gsubsys->notifier);
 	tsm_unregister(&gsubsys->base);
 }
 EXPORT_SYMBOL_GPL(tsm_guest_unregister);

---

## [21] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 20/22] sev-guest: Stop changing encrypted page state for TDISP devices*

At the moment DMA is assumes insecure and either private memory is
converted into shared for the duration of DMA, or SWIOTLB is used.
With secure DMA enabled, neither is required.

Stop enforcing unencrypted DMA and SWIOTLB if the device is marked as
TDI enabled.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/dma-direct.h | 8 ++++++++
 include/linux/swiotlb.h    | 8 ++++++++
 arch/x86/mm/mem_encrypt.c  | 6 ++++++
 3 files changed, 22 insertions(+)

diff --git a/include/linux/dma-direct.h b/include/linux/dma-direct.h
index d7e30d4f7503..3bd533d2e65d 100644
--- a/include/linux/dma-direct.h
+++ b/include/linux/dma-direct.h
@@ -94,6 +94,14 @@ static inline dma_addr_t phys_to_dma_unencrypted(struct device *dev,
  */
 static inline dma_addr_t phys_to_dma(struct device *dev, phys_addr_t paddr)
 {
+#if defined(CONFIG_TSM_GUEST) || defined(CONFIG_TSM_GUEST_MODULE)
+	if (dev->tdi_enabled) {
+		dev_warn_once(dev, "(TIO) Disable SME");
+		if (!dev->tdi_validated)
+			dev_warn(dev, "TDI is not validated, DMA @%llx will fail", paddr);
+		return phys_to_dma_unencrypted(dev, paddr);
+	}
+#endif
 	return __sme_set(phys_to_dma_unencrypted(dev, paddr));
 }
 
diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..67bea31fa42a 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -173,6 +173,14 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+#if defined(CONFIG_TSM_GUEST) || defined(CONFIG_TSM_GUEST_MODULE)
+	if (dev->tdi_enabled) {
+		dev_warn_once(dev, "(TIO) Disable SWIOTLB");
+		if (!dev->tdi_validated)
+			dev_warn(dev, "TDI is not validated");
+		return false;
+	}
+#endif
 	return mem && mem->force_bounce;
 }
 
diff --git a/arch/x86/mm/mem_encrypt.c b/arch/x86/mm/mem_encrypt.c
index 95bae74fdab2..c9c99154bec9 100644
--- a/arch/x86/mm/mem_encrypt.c
+++ b/arch/x86/mm/mem_encrypt.c
@@ -19,6 +19,12 @@
 /* Override for DMA direct allocation check - ARCH_HAS_FORCE_DMA_UNENCRYPTED */
 bool force_dma_unencrypted(struct device *dev)
 {
+#if defined(CONFIG_TSM_GUEST) || defined(CONFIG_TSM_GUEST_MODULE)
+	if (dev->tdi_enabled) {
+		dev_warn_once(dev, "(TIO) Disable decryption");
+		return false;
+	}
+#endif
 	/*
 	 * For SEV, all DMA must be to unencrypted addresses.
 	 */

---

## [22] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 21/22] pci: Allow encrypted MMIO mapping via sysfs*

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
index 073f8f3aece8..862f63ef9bf9 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -2129,7 +2129,7 @@ pci_alloc_irq_vectors(struct pci_dev *dev, unsigned int min_vecs,
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
index 4136889011c9..7b03daa13879 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1062,7 +1062,7 @@ void pci_remove_legacy_files(struct pci_bus *b)
  * Use the regular PCI mapping routines to map a PCI resource into userspace.
  */
 static int pci_mmap_resource(struct kobject *kobj, const struct bin_attribute *attr,
-			     struct vm_area_struct *vma, int write_combine)
+			     struct vm_area_struct *vma, int write_combine, int enc)
 {
 	struct pci_dev *pdev = to_pci_dev(kobj_to_dev(kobj));
 	int bar = (unsigned long)attr->private;
@@ -1082,21 +1082,28 @@ static int pci_mmap_resource(struct kobject *kobj, const struct bin_attribute *a
 
 	mmap_type = res->flags & IORESOURCE_MEM ? pci_mmap_mem : pci_mmap_io;
 
-	return pci_mmap_resource_range(pdev, bar, vma, mmap_type, write_combine);
+	return pci_mmap_resource_range(pdev, bar, vma, mmap_type, write_combine, enc);
 }
 
 static int pci_mmap_resource_uc(struct file *filp, struct kobject *kobj,
 				const struct bin_attribute *attr,
 				struct vm_area_struct *vma)
 {
-	return pci_mmap_resource(kobj, attr, vma, 0);
+	return pci_mmap_resource(kobj, attr, vma, 0, 0);
 }
 
 static int pci_mmap_resource_wc(struct file *filp, struct kobject *kobj,
 				const struct bin_attribute *attr,
 				struct vm_area_struct *vma)
 {
-	return pci_mmap_resource(kobj, attr, vma, 1);
+	return pci_mmap_resource(kobj, attr, vma, 1, 0);
+}
+
+static int pci_mmap_resource_enc(struct file *filp, struct kobject *kobj,
+				 const struct bin_attribute *attr,
+				 struct vm_area_struct *vma)
+{
+	return pci_mmap_resource(kobj, attr, vma, 0, 1);
 }
 
 static ssize_t pci_resource_io(struct file *filp, struct kobject *kobj,
@@ -1190,7 +1197,7 @@ static void pci_remove_resource_files(struct pci_dev *pdev)
 	}
 }
 
-static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine)
+static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine, int enc)
 {
 	/* allocate attribute structure, piggyback attribute name */
 	int name_len = write_combine ? 13 : 10;
@@ -1208,6 +1215,9 @@ static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine)
 	if (write_combine) {
 		sprintf(res_attr_name, "resource%d_wc", num);
 		res_attr->mmap = pci_mmap_resource_wc;
+	} else if (enc) {
+		sprintf(res_attr_name, "resource%d_enc", num);
+		res_attr->mmap = pci_mmap_resource_enc;
 	} else {
 		sprintf(res_attr_name, "resource%d", num);
 		if (pci_resource_flags(pdev, num) & IORESOURCE_IO) {
@@ -1264,11 +1274,14 @@ static int pci_create_resource_files(struct pci_dev *pdev)
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

## [23] Alexey Kardashevskiy — 2025-02-18
*Subject: [RFC PATCH v2 22/22] pci: Define pci_iomap_range_encrypted*

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
index 9fb7cacc15cd..97bada477336 100644
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
+	if ((flags & IORESOURCE_MEM) && (flags & IORESOURCE_VALIDATED))
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

## [24] Jason Gunthorpe — 2025-02-18
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Tue, Feb 18, 2025 at 10:09:59PM +1100, Alexey Kardashevskiy wrote:
> CoCo VMs get their private memory allocated from guest_memfd
> ("gmemfd") which is a KVM facility similar to memfd.

How is that possible though?

> +static struct folio *guest_memfd_get_pfn(struct file *file, unsigned long index,
> +					 unsigned long *pfn, int *max_order)

Connecting iommufd to guestmemfd through the FD is broadly the right
idea, but I'm not sure this matches the design of guestmemfd regarding
pinnability. IIRC they were adamant that the pages would not be
pinned..

folio_add_pins() just prevents the folio from being freed, it doesn't
prevent the guestmemfd code from messing with the filemap.

You should separate this from the rest of the series and discuss it
directly with the guestmemfd maintainers.
 
As I understood it the requirement here is to have some kind of
invalidation callback so that iommufd can drop mappings, but I don't
really know and AFAIK AMD is special in wanting private pages mapped
to the hypervisor iommu..

Jason

---

## [25] Alexey Kardashevskiy — 2025-02-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On 19/2/25 01:16, Jason Gunthorpe wrote:
> On Tue, Feb 18, 2025 at 10:09:59PM +1100, Alexey Kardashevskiy wrote:
>> CoCo VMs get their private memory allocated from guest_memfd

dunno, things evolve over years and converge somehow :)

>> +static struct folio *guest_memfd_get_pfn(struct file *file, unsigned long index,
>> +					 unsigned long *pfn, int *max_order)

uff I thought it was about "not mapped" rather than "non pinned".

> folio_add_pins() just prevents the folio from being freed, it doesn't
> prevent the guestmemfd code from messing with the filemap.

Alright, thanks for the suggestion.

> As I understood it the requirement here is to have some kind of
> invalidation callback so that iommufd can drop mappings,

Since shared<->private conversion is an ioctl() (kvm/gmemfd) so it is 
ioctl() for iommufd then too. Oh well.

> but I don't
> really know and AFAIK AMD is special in wanting private pages mapped

With in-place conversion, we could map the entire guest once in the HV 
IOMMU and control the Cbit via the guest's IOMMU table (when available). 
Thanks,

---

## [26] Jason Gunthorpe — 2025-02-18
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Wed, Feb 19, 2025 at 10:35:28AM +1100, Alexey Kardashevskiy wrote:

> With in-place conversion, we could map the entire guest once in the HV IOMMU
> and control the Cbit via the guest's IOMMU table (when available). Thanks,

Isn't it more complicated than that? I understood you need to have a
IOPTE boundary in the hypervisor at any point where the guest Cbit
changes - so you can't just dump 1G hypervisor pages to cover the
whole VM, you have to actively resize ioptes?

This was the whole motivation to adding the page size override kernel
command line.

Jason

---

## [27] Alexey Kardashevskiy — 2025-02-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On 19/2/25 10:51, Jason Gunthorpe wrote:
> On Wed, Feb 19, 2025 at 10:35:28AM +1100, Alexey Kardashevskiy wrote:
> 

When the guest Cbit changes, only AMD RMP table requires update but not 
necessaryly NPT or IOPTEs.
(I may have misunderstood the question, what meaning does "dump 1G 
pages" have?).


> This was the whole motivation to adding the page size override kernel
> command line.

---

## [28] Jason Gunthorpe — 2025-02-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Wed, Feb 19, 2025 at 11:43:46AM +1100, Alexey Kardashevskiy wrote:
> On 19/2/25 10:51, Jason Gunthorpe wrote:
> > On Wed, Feb 19, 2025 at 10:35:28AM +1100, Alexey Kardashevskiy wrote:

AFAIK that is not true, if there are mismatches in page size, ie the
RMP is 2M and the IOPTE is 1G then things do not work properly.

It is why we had to do this:

> > This was the whole motivation to adding the page size override kernel
> > command line.

commit f0295913c4b4f377c454e06f50c1a04f2f80d9df
Author: Joerg Roedel <jroedel@suse.de>
Date:   Thu Sep 5 09:22:40 2024 +0200

    iommu/amd: Add kernel parameters to limit V1 page-sizes
    
    Add two new kernel command line parameters to limit the page-sizes
    used for v1 page-tables:
    
            nohugepages     - Limits page-sizes to 4KiB
    
            v2_pgsizes_only - Limits page-sizes to 4Kib/2Mib/1GiB; The
                              same as the sizes used with v2 page-tables
    
    This is needed for multiple scenarios. When assigning devices to
    SEV-SNP guests the IOMMU page-sizes need to match the sizes in the RMP
    table, otherwise the device will not be able to access all shared
    memory.
    
    Also, some ATS devices do not work properly with arbitrary IO
    page-sizes as supported by AMD-Vi, so limiting the sizes used by the
    driver is a suitable workaround.
    
    All-in-all, these parameters are only workarounds until the IOMMU core
    and related APIs gather the ability to negotiate the page-sizes in a
    better way.
    
    Signed-off-by: Joerg Roedel <jroedel@suse.de>
    Reviewed-by: Vasant Hegde <vasant.hegde@amd.com>
    Link: https://lore.kernel.org/r/20240905072240.253313-1-joro@8bytes.org

Jason

---

## [29] Michael Roth — 2025-02-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Wed, Feb 19, 2025 at 09:35:16AM -0400, Jason Gunthorpe wrote:
> On Wed, Feb 19, 2025 at 11:43:46AM +1100, Alexey Kardashevskiy wrote:
> > On 19/2/25 10:51, Jason Gunthorpe wrote:

Just for clarity: at least for normal/nested page table (but I'm
assuming the same applies to IOMMU mappings), 1G mappings are
handled similarly as 2MB mappings as far as RMP table checks are
concerned: each 2MB range is checked individually as if it were
a separate 2MB mapping:

AMD Architecture Programmer's Manual Volume 2, 15.36.10,
"RMP and VMPL Access Checks":

  "Accesses to 1GB pages only install 2MB TLB entries when SEV-SNP is
  enabled, therefore this check treats 1GB accesses as 2MB accesses for
  purposes of this check."

So a 1GB mapping doesn't really impose more restrictions than a 2MB
mapping (unless there's something different about how RMP checks are
done for IOMMU).

But the point still stands for 4K RMP entries and 2MB mappings: a 2MB
mapping either requires private page RMP entries to be 2MB, or in the
case of 2MB mapping of shared pages, every page in the range must be
shared according to the corresponding RMP entries.

> 
> It is why we had to do this:

I think, for the non-SEV-TIO use-case, it had more to do with inability
to unmap a 4K range once a particular 4K page has been converted
from shared to private if it was originally installed via a 2MB IOPTE,
since the guest could actively be DMA'ing to other shared pages in the
2M range (but we can be assured it is not DMA'ing to a particular 4K
page it has converted to private), and the IOMMU doesn't (AFAIK) have
a way to atomically split an existing 2MB IOPTE to avoid this. So
forcing everything to 4K ends up being necessary since we don't know
in advance what ranges might contain 4K pages that will get converted
to private in the future by the guest.

SEV-TIO might relax this restriction by making use of TMPM and the
PSMASH_IO command to split/"smash" RMP entries and IOMMU mappings to 4K
after-the-fact, but I'm not too familiar with the architecture/plans so
Alexey can correct me on that.

-Mike

> 
> > > This was the whole motivation to adding the page size override kernel

---

## [30] Jason Gunthorpe — 2025-02-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Wed, Feb 19, 2025 at 02:23:24PM -0600, Michael Roth wrote:
> Just for clarity: at least for normal/nested page table (but I'm
> assuming the same applies to IOMMU mappings), 1G mappings are

Well, IIRC we are dealing with the AMDv1 IO page table here which
supports more sizes than 1G and we likely start to see things like 4M
mappings and the like. So maybe there is some issue if the above
special case really only applies to 1G and only 1G.

> But the point still stands for 4K RMP entries and 2MB mappings: a 2MB
> mapping either requires private page RMP entries to be 2MB, or in the

 Is 4k RMP what people are running?

> I think, for the non-SEV-TIO use-case, it had more to do with inability
> to unmap a 4K range once a particular 4K page has been converted

Yes, we don't support unmap or resize. The entire theory of operation
has the IOPTEs cover the guest memory and remain static at VM boot
time. The RMP alone controls access and handles the static/private.

Assuming the host used 2M pages the IOPTEs in an AMDv1 table will be
sized around 2M,4M,8M just based around random luck.

So it sounds like you can get to a situation with a >=2M mapping in
the IOPTE but the guest has split it into private/shared at lower
granularity and the HW cannot handle this?

> from shared to private if it was originally installed via a 2MB IOPTE,
> since the guest could actively be DMA'ing to other shared pages in

The iommu can split it (with SW help), I'm working on that
infrastructure right now..

So you will get a notification that the guest has made a
private/public split and the iommu page table can be atomically
restructured to put an IOPTE boundary at the split.

Then the HW will not see IOPTEs that exceed the shared/private
granularity of the VM.

Jason

---

## [31] Michael Roth — 2025-02-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Wed, Feb 19, 2025 at 04:37:08PM -0400, Jason Gunthorpe wrote:
> On Wed, Feb 19, 2025 at 02:23:24PM -0600, Michael Roth wrote:
> > Just for clarity: at least for normal/nested page table (but I'm

I think the documentation only mentioned 1G specifically since that's
the next level up in host/nested page table mappings, and that more
generally anything mapping at a higher granularity than 2MB would be
broken down into individual checks on each 2MB range within. But it's
quite possible things are handled differently for IOMMU so definitely
worth confirming.

> 
> > But the point still stands for 4K RMP entries and 2MB mappings: a 2MB

Unfortunately yes, but that's mainly due to guest_memfd only handling
4K currently. Hopefully that will change soon, but in the meantime
there's only experimental support for larger private page sizes that
make use of 2MB RMP entries (via THP).

But regardless, we'll still end up dealing with 4K RMP entries since
we'll need to split 2MB RMP entries in response to private->conversions
that aren't 2MB aligned/sized.

> 
> > I think, for the non-SEV-TIO use-case, it had more to do with inability

Remembering more details: the situation is a bit more specific to
guest_memfd. In general, for non-SEV-TIO, everything in the IOMMU will
be always be for shared pages, and because of that the RMP checks don't
impose any additional restrictions on mapping size (a shared page can
be mapped 2MB even if the RMP entry is 4K (the RMP page-size bit only
really applies for private pages)).

The issue with guest_memfd is that it is only used for private pages
(at least until in-place conversion is supported), so when we "convert"
shared pages to private we are essentially discarding those pages and
re-allocating them via guest_memfd, so the mappings for those discarded
pages become stale and need to be removed. But since this can happen
at 4K granularities, we need to map as 4K because we don't have a way
to split them later on (at least, not currently...).

The other approach is to not discard these shared pages after conversion
and just not free them back, which ends up using more host memory, but
allows for larger IOMMU mappings.

> 
> > from shared to private if it was originally installed via a 2MB IOPTE,

That sounds very interesting. It would allow us to use larger IOMMU
mappings even for guest_memfd as it exists today, while still supporting
shared memory discard and avoiding the additional host memory usage
mentioned above. Are there patches available publicly?

Thanks,

Mike

> 
> Jason

---

## [32] Jason Gunthorpe — 2025-02-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Wed, Feb 19, 2025 at 03:30:37PM -0600, Michael Roth wrote:
> I think the documentation only mentioned 1G specifically since that's
> the next level up in host/nested page table mappings, and that more

Hmm, well, I'd very much like it if we are all on the same page as to
why the new kernel parameters were needed. Joerg was definitely seeing
testing failures without them.

IMHO we should not require parameters like that, I expect the kernel
to fix this stuff on its own.

> But regardless, we'll still end up dealing with 4K RMP entries since
> we'll need to split 2MB RMP entries in response to private->conversions

:( What is the point of even allowing < 2MP private/shared conversion?

> > Then the HW will not see IOPTEs that exceed the shared/private
> > granularity of the VM.

https://patch.msgid.link/r/0-v1-01fa10580981+1d-iommu_pt_jgg@nvidia.com

I'm getting quite close to having something non-RFC that just does AMD
and the bare minimum. I will add you two to the CC

Jason

---

## [33] Alexey Kardashevskiy — 2025-02-20
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On 20/2/25 00:35, Jason Gunthorpe wrote:
> On Wed, Feb 19, 2025 at 11:43:46AM +1100, Alexey Kardashevskiy wrote:
>> On 19/2/25 10:51, Jason Gunthorpe wrote:


Right, so I misunderstood. When I first replied, I assumed the current 
situation of 4K pages everywhere. IOPTEs larger than RMP entries are 
likely to cause failed RMP checks (confirming now, surprises sometime 
happen). Thanks,


> It is why we had to do this:
>

---

## [34] Xu Yilun — 2025-02-25
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Tue, Feb 18, 2025 at 10:10:01PM +1100, Alexey Kardashevskiy wrote:
> When a TDISP-capable device is passed through, it is configured as
> a shared device to begin with. Later on when a VM probes the device,

I still have concern about the vdevice interface for bind. Bind put the
device to LOCKED state, so is more of a device configuration rather
than an iommu configuration. So seems more reasonable put the API in VFIO?

> 
> Add TDI bind to do the initial binding of a passed through PCI

The fact is HV cannot see the guest requests, even I think HV never have
to care about the guest requests. HV cares until bind, then no HV side
MMIO & DMA access is possible, any operation/state after bind won't
affect HV more. And HV could always unbind to rollback guest side thing.

That said guest requests are nothing to do with any host side component,
iommu or vfio. It is just the message posting between VM & firmware. I
suppose KVM could directly do it by calling TSM driver API.

Thanks,
Yilun

---

## [35] Alexey Kardashevskiy — 2025-02-26
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 25/2/25 20:00, Xu Yilun wrote:
> On Tue, Feb 18, 2025 at 10:10:01PM +1100, Alexey Kardashevskiy wrote:
>> When a TDISP-capable device is passed through, it is configured as

IOMMUFD means pretty much VFIO (in the same way "VFIO means KVM" as 95+% 
of VFIO users use it from KVM, although VFIO works fine without KVM) so 
not much difference where to put this API and can be done either way. 
VFIO is reasonable, the immediate problem is that IOMMUFD's vIOMMU knows 
the guest BDFn (well, for AMD) and VFIO PCI does not.


>> Add TDI bind to do the initial binding of a passed through PCI
>> function to a VM. Add a forwarder for TIO GUEST REQUEST. These two

No, it could not as the HV needs to add the host BDFn to the guest's 
request before calling the firmware and KVM does not have that knowledge.

These guest requests are only partly encrypted as the guest needs 
cooperation from the HV. The guest BDFn comes unencrypted from the VM to 
let the HV find the host BDFn and do the bind.

Also, say, in order to enable MMIO range, the host needs to "rmpupdate" 
MMIOs first (and then the firmware does "pvalidate") so it needs to know 
the range which is in unencrypted part of guest request.

Here is a rough idea: https://github.com/aik/qemu/commit/f804b65aff5b

A TIO Guest request is made of:
- guest page with unencrypted header (msg type is essential) and 
encrypted body for consumption by the firmware;
- a couple of 64bit bit fields and RAX/RBX/... in shared GHCB page.

Thanks,

> Thanks,
> Yilun

---

## [36] Xu Yilun — 2025-02-26
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Wed, Feb 26, 2025 at 11:12:32AM +1100, Alexey Kardashevskiy wrote:
> 
> 

Er... I cannot agree. There are clear responsibilities for
VFIO/IOMMUFD/KVM each. They don't overlap each other. So I don't think
either way is OK. VFIO still controls the overall device behavior
and it is VFIO's decision to hand over user DMA setup to IOMMUFD. IIUC
that's why VFIO_DEVICE_ATTACH_IOMMUFD_PT should be a VFIO API.

E.g. I don't think VFIO driver would expect its MMIO access suddenly
failed without knowing what happened.

> reasonable, the immediate problem is that IOMMUFD's vIOMMU knows the guest
> BDFn (well, for AMD) and VFIO PCI does not.

For Intel, it is host BDF. But I think this is TSM architecture
difference that could be hidden in TSM framework. From TSM caller's POV,
it could just be a magic number identifying the TDI.

Back to your concern, I don't think it is a problem. From your patch,
vIOMMU doesn't know the guest BDFn by nature, it is just the user
stores the id in vdevice via iommufd_vdevice_alloc_ioctl(). A proper
VFIO API could also do this work.

I'm suggesting a VFIO API:

/*
 * @tdi_id: A TSM recognizable TDI identifier
 *	    On input, user suggests the TDI identifier number for TSM.
 *	    On output, TSM's decision of the TDI identifier number.
 */
struct vfio_pci_tsm_bind {
	__u32 argsz;
	__u32 flags;
	__u32 tdi_id;
	__u32 pad;
};

#define VFIO_DEVICE_TSM_BIND		_IO(VFIO_TYPE, VFIO_BASE + 22)

I need the tdi_id as output cause I don't want any outside TSM user and
Guest to assume what the TDI id should be.

static int vfio_pci_ioctl_tsm_bind(struct vfio_pci_core_device *vdev,
				   void __user *arg)
{
	unsigned long minsz = offsetofend(struct vfio_pci_tsm_bind, tdi_id);
	struct pci_dev *pdev = vdev->pdev;
	struct kvm *kvm = vdev->vdev.kvm;
	struct vfio_pci_tsm_bind bind;

	if (copy_from_user(&bind, arg, minsz))
		return -EFAULT;

	ret = pci_tsm_dev_bind(pdev, kvm, &bind.tdi_id);

}

A call to TSM makes TSM driver know the tdi_id and could find the real
device inside TSM via tdi_id. Following TSM call could directly use
tdi_id as parameter.

The implementation is basically no difference from:

+       vdev = container_of(iommufd_get_object(ucmd->ictx, cmd->vdevice_id,
+                                              IOMMUFD_OBJ_VDEVICE),

The real concern is the device owner, VFIO, should initiate the bind.

> 
> 

I think if TSM has knowledge about tdi_id, KVM doesn't have to know host BDFn.
Just let TSM handle the vendor difference. Not sure if this solves all
the problem.

> 
> These guest requests are only partly encrypted as the guest needs

It is not about HV never touch any message content. It is about HV
doesn't (and shouldn't, since some info is encrypted) influence any host
behavior by executing guest request, so no need to route to any other
component.

Thanks,
Yilun

> 
> Also, say, in order to enable MMIO range, the host needs to "rmpupdate"

---

## [37] Jason Gunthorpe — 2025-02-26
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Wed, Feb 26, 2025 at 11:12:32AM +1100, Alexey Kardashevskiy wrote:
> > I still have concern about the vdevice interface for bind. Bind put the
> > device to LOCKED state, so is more of a device configuration rather

I would re-enforce what I said before, VFIO & iommufd alone should be
able to operate a TDISP device and get device encrpytion without
requiring KVM.

It makes sense that if the secure firmware object handles (like the
viommu, vdevice, vBDF) are accessed through iommufd then iommufd will
relay operations against those handles.

Jason

---

## [38] Jason Gunthorpe — 2025-02-26
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Wed, Feb 26, 2025 at 06:49:18PM +0800, Xu Yilun wrote:

> E.g. I don't think VFIO driver would expect its MMIO access suddenly
> failed without knowing what happened.

What do people expect to happen here anyhow? Do you still intend to
mmap any of the MMIO into the hypervisor? No, right? It is all locked
down?

So perhaps the answer is that the VFIO side has to put the device into
CC mode which disables MMAP/etc, then the viommu/vdevice iommufd
object can control it.

> Back to your concern, I don't think it is a problem. From your patch,
> vIOMMU doesn't know the guest BDFn by nature, it is just the user

We don't want duplication though. If the viommu/vdevice/vbdf are owned
and lifecycle controlled by iommufd then the operations against them
must go through iommufd and through it's locking regime.
> 
> The implementation is basically no difference from:

There is a big different, the above has correct locking, the other
does not :)

Jason

---

## [39] Alexey Kardashevskiy — 2025-02-27
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 27/2/25 00:12, Jason Gunthorpe wrote:
> On Wed, Feb 26, 2025 at 06:49:18PM +0800, Xu Yilun wrote:
> 

This patchset expects it to be mmap'able as this is how MMIO gets mapped 
in the NPT and SEV-SNP still works with that (and updates the RMPs on 
top), the host os is not expected to access these though. TDX will 
handle this somehow different. Thanks,

> 
> So perhaps the answer is that the VFIO side has to put the device into

---

## [40] Xu Yilun — 2025-02-27
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Wed, Feb 26, 2025 at 09:12:02AM -0400, Jason Gunthorpe wrote:
> On Wed, Feb 26, 2025 at 06:49:18PM +0800, Xu Yilun wrote:
> 

Not expecting mmap the MMIO, but I switched to another way. VFIO doesn't
disallow mmap until bind, and if there is mmap on bind, bind failed.
That's my understanding of your comments.

https://lore.kernel.org/kvm/Z4Hp9jvJbhW0cqWY@yilunxu-OptiPlex-7050/#t


Another concern is about dma-buf importer (e.g. KVM) mapping the MMIO.
Recall we are working on the VFIO dma-buf solution, on bind/unbind the
MMIO accessibility is being changed and importers should be notified to
remove their mapping beforehand, and rebuild later if possible.
An immediate requirement for Intel TDX is, KVM should remove secure EPT
mapping for MMIO before unbind.

So I think device is all locked down into CC mode AFTER bind and BEFORE
unbind. It doesn't seems viommu/vdevice could control bind/unbind.

There are other bus error handling cases, like AER when TDISP/SPDM/IDE
state broken, that I don't have a clear solution now. But I cannot
imagine they could be correctly handled without pci_driver support.

> down?
> 

Could you elaborate more on that? Any locking problem if we implement
bind/unbind outside iommufd. Thanks in advance.

Thanks,
Yilun

> 
> Jason

---

## [41] Borislav Petkov — 2025-02-27
*Subject: Re: [RFC PATCH v2 00/22] TSM: Secure VFIO, TDISP, SEV TIO*

FWIW,

I really appreciate this mail which explains to unenlightened people like me
what this is all about.

Especially the Acronyms, Flow, Specs pointers etc. I wish I could see this
type of writeups in all patchsets' 0th messages, leading in the reader into
the topic while not expecting the latter to actually *know* all those things
because, d0h, it is obvious. You can read my mind, right? :-)

So thanks for taking the time - it is very helpful!

On Tue, Feb 18, 2025 at 10:09:47PM +1100, Alexey Kardashevskiy wrote:
> Here are some patches to enable SEV-TIO on AMD Turin. It's been a while
> and got quiet and I kept fixing my tree and wondering if I am going in

---

## [42] Borislav Petkov — 2025-02-27
*Subject: Re: [RFC PATCH v2 20/22] sev-guest: Stop changing encrypted page
 state for TDISP devices*

On Tue, Feb 18, 2025 at 10:10:07PM +1100, Alexey Kardashevskiy wrote:
> diff --git a/include/linux/dma-direct.h b/include/linux/dma-direct.h
> index d7e30d4f7503..3bd533d2e65d 100644

Duplicated code with ugly ifdeffery. Perhaps do a helper which you call
everywhere instead?

---

## [43] Jason Gunthorpe — 2025-02-28
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Thu, Feb 27, 2025 at 11:33:31AM +1100, Alexey Kardashevskiy wrote:
> 
> 

I'm expecting you'll wrap that in a FD, since iommufd will not be
accessing MMIO through mmaps.

Jason

---

## [44] Jason Gunthorpe — 2025-02-28
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Thu, Feb 27, 2025 at 11:59:18AM +0800, Xu Yilun wrote:
> On Wed, Feb 26, 2025 at 09:12:02AM -0400, Jason Gunthorpe wrote:
> > On Wed, Feb 26, 2025 at 06:49:18PM +0800, Xu Yilun wrote:

That seems reasonable

> Another concern is about dma-buf importer (e.g. KVM) mapping the MMIO.
> Recall we are working on the VFIO dma-buf solution, on bind/unbind the

dmabuf can do that..

> > > The implementation is basically no difference from:
> > > 

You will be unable to access any information iommufd has in the viommu
and vdevice objects. So you will not be able to pass a viommu ID or
vBDF to the secure world unless you enter through an iommufd path, and
use iommufd_get_object() to obtain the required locks.
 
I don't know what the API signatures are for all three platforms to
tell if this is a problem or not.

Jason

---

## [45] Xu Yilun — 2025-03-03
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Fri, Feb 28, 2025 at 08:37:11PM -0400, Jason Gunthorpe wrote:
> On Thu, Feb 27, 2025 at 11:59:18AM +0800, Xu Yilun wrote:
> > On Wed, Feb 26, 2025 at 09:12:02AM -0400, Jason Gunthorpe wrote:

Yes, dmabuf can do that via notify. dmabuf is implemented in VFIO,
so iommufd/vdevice couldn't operate on dmabuf and send the notify.

> 
> > > > The implementation is basically no difference from:

Seems not a problem for Intel TDX. Basically secure DMA settings for TDX
is just to build the secure IOMMUPT, only need host BDF. Also secure
device setting needs no secure DMA info.

All these settings cannot really take function until guest verifies them
and does TDISP start. Guest verification does not (should not) need host
awareness.

Our solution is, separate the secure DMA setting and secure device setting
in different components, iommufd & vfio.

Guest require bind:
  - ioctl(iommufd, IOMMU_VIOMMU_ALLOC, {.type = IOMMU_VIOMMU_TYPE_KVM_VALID,
					.kvm_fd = kvm_fd,
					.out_viommu_id = &viommu_id});
  - ioctl(iommufd, IOMMU_HWPT_ALLOC, {.flag = IOMMU_HWPT_ALLOC_TRUSTED,
				      .pt_id = viommu_id,
				      .out_hwpt_id = &hwpt_id});
  - ioctl(vfio_fd, VFIO_DEVICE_ATTACH_IOMMUFD_PT, {.pt_id = hwpt_id})
    - do secure DMA setting in Intel iommu driver.

  - ioctl(vfio_fd, VFIO_DEVICE_TSM_BIND, ...)
    - do bind in Intel TSM driver.

Thanks,
Yilun

> 
> Jason

---

## [46] Alexey Kardashevskiy — 2025-03-05
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 1/3/25 11:32, Jason Gunthorpe wrote:
> On Thu, Feb 27, 2025 at 11:33:31AM +1100, Alexey Kardashevskiy wrote:
>>

A KVM memslot from VFIO's fd similar to gmemfd's fd, and skip VMA? 
Doable but 1) creates a KVM->VFIO dependency to do gpa->hpa translation 
2) is not necessary in the AMD case (although host-mmap of 
guest-assigned private BAR is way too easy way of shooting yourself in 
the foot).

 > since iommufd will not be accessing MMIO through mmaps.

here I do not follow, why would iommufd care about MMIO? or it is about 
p2p DMA? Thanks,

> 
> Jason

---

## [47] Jason Gunthorpe — 2025-03-05
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Wed, Mar 05, 2025 at 02:09:09PM +1100, Alexey Kardashevskiy wrote:
> 
> 

But since it is necessary in other cases, the code will be there and
everyone should just use it..

> > since iommufd will not be accessing MMIO through mmaps.
> 

Yes, p2p dma

Jason

---

## [48] Jason Gunthorpe — 2025-03-05
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Mon, Mar 03, 2025 at 01:32:47PM +0800, Xu Yilun wrote:
> All these settings cannot really take function until guest verifies them
> and does TDISP start. Guest verification does not (should not) need host

Except what do command do you issue to the secure world for TSM_BIND
and what are it's argument? Again you can't include the vBDF or vIOMMU
ID here.

vfio also can't validate that the hwpt is in the right state when it
executes this function.

You could also issue the TSM bind against the idev on the iommufd
side..

Part of my problem here is I don't see anyone who seems to have read
all three specs and is trying to mush them together. Everyone is
focused on their own spec. I know there are subtle differences :\

Jason

---

## [49] Xu Yilun — 2025-03-06
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Wed, Mar 05, 2025 at 03:28:42PM -0400, Jason Gunthorpe wrote:
> On Mon, Mar 03, 2025 at 01:32:47PM +0800, Xu Yilun wrote:
> > All these settings cannot really take function until guest verifies them

Bind for TDX doesn't require vBDF or vIOMMU ID. The seamcall is like:

u64 tdh_devif_create(u64 stream_id,     // IDE stream ID, PF0 stuff
                     u64 devif_id,      // TDI ID, it is the host BDF
                     u64 tdr_pa,        // TDX VM core metadate page, TDX Connect uses it as CoCo-VM ID
                     u64 devifcs_pa)    // metadate page provide to firmware

While for AMD:
        ...
        b.guest_device_id = guest_rid;  //TDI ID, it is the vBDF
        b.gctx_paddr = gctx_paddr;      //AMDs CoCo-VM ID

        ret = sev_tio_do_cmd(SEV_CMD_TIO_TDI_BIND, &b, ...


Neither of them use vIOMMU ID or any IOMMU info, so the only concern is
vBDF.

Basically from host POV the two interfaces does the same thing, connect
the CoCo-VM ID with the TDI ID, for which Intel uses host BDF while AMD
uses vBDF. But AMD firmware cannot know anything meaningful about the
vBDF, it is just a magic number to index TDI metadata.

So I don't think we have to introduce vBDF concept in kernel. AMD uses
QEMU created vBDF as TDI ID, that's fine, QEMU should ensure the
validity of the vBDF.

> 
> vfio also can't validate that the hwpt is in the right state when it

Not sure if VFIO has to validate, or is there a requirement that
secure DMA should be in right state before bind. TDX doesn't require
this, and I didn't see the requirement in SEV-TIO spec. I.e. the
bind firmware calls don't check DMA state.

In my opinion, TDI bind means put device in LOCKED state and related
metadate management in firmware. After bind the DMA cannot work. It
is the guest's resposibility to validate everything (including DMA)
is in the right state, then issues RUN, then DMA works. I.e. guest tsm
calls check DMA state.  That's why I think Secure DMA configuration
on host could be in a separated flow from bind.

> 
> You could also issue the TSM bind against the idev on the iommufd

But I cannot figure out how idev could ensure no mmap on VFIO, and how
idev could call dma_buf_move_notify.

Thanks,
Yilun

> 
> Part of my problem here is I don't see anyone who seems to have read

---

## [50] Jason Gunthorpe — 2025-03-06
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Thu, Mar 06, 2025 at 02:47:23PM +0800, Xu Yilun wrote:

> While for AMD:
>         ...

I think that is enough, we should not be putting this in VFIO if it
cannot execute it for AMD :\

> > You could also issue the TSM bind against the idev on the iommufd
> > side..

I suggest you start out this way from the VFIO. Put the device in a CC
mode which bans the mmap entirely and pass that CC capable as a flag
into iommufd when creating the idev.

If it really needs to be dyanmic a VFIO feature could change the CC
mode and that could call back to iommufd to synchronize if that is
allowed.

Jason

---

## [51] Alexey Kardashevskiy — 2025-03-07
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 6/3/25 17:47, Xu Yilun wrote:
> On Wed, Mar 05, 2025 at 03:28:42PM -0400, Jason Gunthorpe wrote:
>> On Mon, Mar 03, 2025 at 01:32:47PM +0800, Xu Yilun wrote:


(offtopic) is there a public spec with this command defined?

> 
> While for AMD:

One is SEV TIO (earlier version published), another one TDX Connect 
(which I do not have and asked above) and what is the third one here? Or 
is it 4 as ARM and RiscV both doing this now? Thanks,

---

## [52] Xu Yilun — 2025-03-07
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Thu, Mar 06, 2025 at 02:26:14PM -0400, Jason Gunthorpe wrote:
> On Thu, Mar 06, 2025 at 02:47:23PM +0800, Xu Yilun wrote:
> 

OK. With these discussion, my understanding is it can execute for AMD
but we don't duplicate the effort for vdevice->id.

We can swtich to vdevice and try to solve the rest problems.

> 
> > > You could also issue the TSM bind against the idev on the iommufd

IIUC, it basically switches back to my previous implementation for mmap.

https://lore.kernel.org/kvm/20250107142719.179636-9-yilun.xu@linux.intel.com/

I can do that.

Thanks,
yilun

> 
> If it really needs to be dyanmic a VFIO feature could change the CC

---

## [53] Jason Gunthorpe — 2025-03-07
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Fri, Mar 07, 2025 at 01:19:11PM +1100, Alexey Kardashevskiy wrote:
> > > Part of my problem here is I don't see anyone who seems to have read
> > > all three specs and is trying to mush them together. Everyone is

ARM will come with a spec someday, I don't know about RISCV. Maybe it
is 4..

Jason

---

## [54] Xu Yilun — 2025-03-12
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Fri, Mar 07, 2025 at 01:19:11PM +1100, Alexey Kardashevskiy wrote:
> 
> 

Sorry, there is no public TDX Connect SPEC yet.

Thanks,
Yilun

---

## [55] Suzuki K Poulose — 2025-03-12
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 07/03/2025 15:17, Jason Gunthorpe wrote:
> On Fri, Mar 07, 2025 at 01:19:11PM +1100, Alexey Kardashevskiy wrote:
>>>> Part of my problem here is I don't see anyone who seems to have read

The Arm CCA DA (Device Assignment, as we call it) specs are available in 
Alpha stage here, under "Future version" section.

https://developer.arm.com/documentation/den0137/latest/

Cheers
Suzuki


> 
> Jason

---

## [56] Dan Williams — 2025-03-12
*Subject: Re: [RFC PATCH v2 06/22] KVM: X86: Define tsm_get_vmid*

Alexey Kardashevskiy wrote:
> In order to add a PCI VF into a secure VM, the TSM module needs to
> perform a "TDI bind" operation. The secure module ("PSP" for AMD)

Curious why KVM needs to be bothered by a new kvm_arch_tsm_get_vmid()
and a vendor specific cookie "vmid" concept. In other words KVM never
calls kvm_arch_tsm_get_vmid(), like other kvm_arch_*() support calls.

Is this due to a restriction that something like tsm_tdi_bind() is
disallowed from doing to_kvm_svm() on an opaque @kvm pointer? Or
otherwise asking an arch/x86/kvm/svm/svm.c to do the same?

Effectively low level TSM drivers are extensions of arch code that
routinely performs "container_of(kvm, struct kvm_$arch, kvm)".

---

## [57] Alexey Kardashevskiy — 2025-03-13
*Subject: Re: [RFC PATCH v2 06/22] KVM: X86: Define tsm_get_vmid*

On 13/3/25 12:51, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> In order to add a PCI VF into a secure VM, the TSM module needs to

I saw someone already doing some sort of VMID thing and thought it is a 
good way of not spilling KVM details outside KVM.

> Effectively low level TSM drivers are extensions of arch code that
> routinely performs "container_of(kvm, struct kvm_$arch, kvm)".

The arch code is CCP and so far it avoided touching KVM, KVM calls CCP 
when it needs but not vice versa. Thanks,

---

## [58] Alexey Kardashevskiy — 2025-03-13
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On 20/2/25 07:37, Jason Gunthorpe wrote:
> On Wed, Feb 19, 2025 at 02:23:24PM -0600, Michael Roth wrote:
>> Just for clarity: at least for normal/nested page table (but I'm

About this atomical restructure - I looked at yours iommu-pt branch on 
github but  __cut_mapping()->pt_table_install64() only atomically swaps 
the PDE but it does not do IOMMU TLB invalidate, have I missed it? And 
if it did so, that would not be atomic but it won't matter as long as we 
do not destroy the old PDE before invalidating IOMMU TLB, is this the 
idea? Thanks,

> 
> Then the HW will not see IOPTEs that exceed the shared/private

---

## [59] Xu Yilun — 2025-03-13
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

> +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
> +{

Why need user to input viommu_id? And why get viommu here?
The viommu is always available after vdevice is allocated, is it?

int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
{
	...

	vdev->viommu = viommu;
	refcount_inc(&viommu->obj.users);
	...
}

> +	if (IS_ERR(viommu))
> +		return PTR_ERR(viommu);
                   ^
vdev?

> +		rc = PTR_ERR(idev);
> +		goto out_put_dev;

And do we still need dev_id for the struct device *? vdevice also has
this info.

int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
{
        ...
	vdev->dev = idev->dev;
	get_device(idev->dev);
        ...
}


> +	if (!tdi) {
> +		rc = -ENODEV;

Another concern is do we need an unbind ioctl? We don't bind on vdevice
create so it seems not symmetrical we only unbind on vdevice destroy.

Thanks,
Yilun

---

## [60] Dan Williams — 2025-03-13
*Subject: Re: [RFC PATCH v2 06/22] KVM: X86: Define tsm_get_vmid*

Alexey Kardashevskiy wrote:
> 
> 

Reference?

> and thought it is a good way of not spilling KVM details outside KVM.

...but it is not a KVM detail. It is an arch specific TSM cookie derived
from arch specific data that wraps 'struct kvm'. Now if the rationale is
some least privelege concern about what code can have a container_of()
relationship with an opaque 'struct kvm *' pointer, let's have that
discussion.  As it stands nothing in KVM cares about
kvm_arch_tsm_get_vmid(), and I expect 'vmid' does not cover all the ways
in which modular TSM drivers may interact with arch/.../kvm/ code.

For example TDX Connect needs to share some data from 'struct kvm_tdx',
and it does that with an export from arch/x86/kvm/vmx/tdx.c, not an
indirection through virt/kvm/kvm_main.c.

> > Effectively low level TSM drivers are extensions of arch code that
> > routinely performs "container_of(kvm, struct kvm_$arch, kvm)".

Right, and the observation is that you don't need to touch
virt/kvm/kvm_main.c at all to meet this data sharing requirement.

---

## [61] Dan Williams — 2025-03-13
*Subject: Re: [RFC PATCH v2 07/22] coco/tsm: Add tsm and tsm-host modules*

Alexey Kardashevskiy wrote:
> The TSM module is a library to create sysfs nodes common for hypervisors
> and VMs. It also provides helpers to parse interface reports (required

There was some discussion on the merits of "TDEV" and "TDI" objects in
the PCI/TSM thread [1], I will summarize the main objections here:

 * PCI device security is a PCI device property. That security property is
   not strictly limited to the platform TEE Security Manager (TSM) case.
   The PCI device authentication enabling, mentioned as "Lukas's CMA" in
   the cover letter, adds a TSM-independent authentication and device
   measurement collection ABI. The PCI/TSM proposal simply aims to reuse
   that ABI and existing PCI device object lifecycle expectations.

 * PCI device security is a PCI specification [2]. The acronym soup of PCI
   device security (TDISP, IDE, CMA, SPDM, DOE) is deeply entangled with
   PCI specifics. If other buses grow the ability to add devices to a
   confidential VM's TCB that future enabling need not be encumbered by
   premature adherence to the TDEV+TDI object model, the bus can do what
   makes sense for its specific mechanisms. The kernel can abstract common
   attributes and ABI without the burden of a new object model.

[1]: http://lore.kernel.org/67b8e5328fd41_2d2c294e5@dwillia2-xfh.jf.intel.com.notmuch
[2]: http://lore.kernel.org/67c128dcb5c21_1a7729454@dwillia2-xfh.jf.intel.com.notmuch

> New device nodes provide sysfs interface for fetching device certificates
> and measurements and TDI interface reports.
[..]
> diff --git a/drivers/virt/coco/host/tsm-host.c b/drivers/virt/coco/host/tsm-host.c
> new file mode 100644
[..]
> +static ssize_t tsm_dev_status_show(struct device *dev, struct device_attribute *attr, char *buf)
> +{

I know this is just an RFC, but...

> +
> +	ret1 = sysfs_emit(buf, "ret=%d\n"

What does "ret" mean to userspace?

> +			  "ctx_state=%x\n"

This violates the one property per file sysfs expectation.

> +			  "tc_mask=%x\n"

Is this the Link IDE traffic class?

> +			  "certs_slot=%x\n"
> +			  "device_id=%x:%x.%d\n"

These last 2 lines are all redundant information relative to the PCI
device name, right?

> +			  "no_fw_update=%x\n",
> +			  ret,

I would not expect sysfs to need to manage device references. If the
device is registered sysfs is live and the reference is already
elevated. If the device is unregistered, sysfs is disabled and attribute
handlers are no longer executing.

[..]
> +static ssize_t tsm_tdi_status_user_show(struct device *dev,
> +					struct device_attribute *attr,

More sysfs expectation violations...

Let's start working on what the Plumbers feedback to Lukas on his
attempt to export PCI CMA device evidence through sysfs means for the
TSM side. I do not expect it will all be strictly reusable but the
transport and some record formats should be unified. Specifically I want
to start the discussion about collaboration and differences among
PCI-CMA-netlink and PCI-TSM-netlink. For example, device measurements
are ostensibly common, but interface reports are unique to the TSM flow.

---

## [62] Alexey Kardashevskiy — 2025-03-14
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 13/3/25 22:01, Xu Yilun wrote:
>> +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
>> +{


I thought it may be a good idea to hold a reference while doing 
tsm_tdi_bind(), likely not needed.

> int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
> {

yes.

> 
>> +		rc = PTR_ERR(idev);

Oh, likely no. Probably leftover from multiple rebases, or me not fully 
following what nature these IDs are of (some are just numbers, some are 
guest bdfn).


> int iommufd_vdevice_alloc_ioctl(struct iommufd_ucmd *ucmd)
> {

I'll add it as we progress. Just for now I have no flow to exercise it - 
I accept the device into my SNP VM and that's it but if something in the 
VM is unhappy about the device report, then we'll need to unbind and 
continue using the device as untrusted. Thanks,

(sorry for late response, still going through all comments here and in 
Dan's threads)

> 
> Thanks,

---

## [63] Alexey Kardashevskiy — 2025-03-14
*Subject: Re: [RFC PATCH v2 06/22] KVM: X86: Define tsm_get_vmid*

On 14/3/25 06:09, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>>

Cannot find it now, RiscV and ARM have this concept but internally and 
it probably should stay this way.

>> and thought it is a good way of not spilling KVM details outside KVM.
> 

a) KVM-AMD uses CCP's exports now, and if I add exports to KVM-AMD for 
CCP - it is cross-reference so I'll need what, KVM-AMD-TIO module, to 
untangle this?

b) I could include arch/x86/kvm/svm/svm.h in drivers/crypto/ccp/ which 
is... meh?

c) Or move parts of struct kvm_sev_info/kvm_svm from 
arch/x86/kvm/svm/svm.h to arch/x86/include/asm/svm.h and do some trick 
to get kvm_sev_info from struct kvm.

d) In my RFC v1, I simply called tsm_tdi_bind() from KVM-AMD with this 
cookie but that assumed KVM knowledge of PCI which I dropped in this RFC 
so the bind request travels via QEMU between the guest and the PSP.

All doable though.

>>> Effectively low level TSM drivers are extensions of arch code that
>>> routinely performs "container_of(kvm, struct kvm_$arch, kvm)".

These are all valid points. I like neither of a)..d) in particular and I 
am AMD-centric (as you correctly noticed :) ) and for this exercise I 
only needed kvmfd->guest_context_page, hence this proposal. Thanks,

---

## [64] Dan Williams — 2025-03-14
*Subject: Re: [RFC PATCH v2 10/22] KVM: SVM: Add uAPI to change RMP for MMIO*

Alexey Kardashevskiy wrote:
> The TDI bind operation moves the TDI into "RUN" state which means that
> TEE resources are now to be used as encrypted, or the device will

Given the guest_memfd momentum to keep private memory unmapped from the
host side do you expect to align with the DMABUF effort [1] to teach KVM
about convertible MMIO where the expectation is that convertible MMIO
need never be mmapped on the host side?

[1]: http://lore.kernel.org/20250123160827.GS5556@nvidia.com

---

## [65] Dan Williams — 2025-03-14
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

Jason Gunthorpe wrote:
> On Wed, Feb 26, 2025 at 11:12:32AM +1100, Alexey Kardashevskiy wrote:
> > > I still have concern about the vdevice interface for bind. Bind put the

Without requiring KVM, but still requiring a TVM context per TDISP
expectations?

I.e. I am still trying to figure out if you are talking about
device-authentication and encryption without KVM, TDISP without a
TVM (not sure what that is), or TDISP state management relative to a
shared concept of a "TVM context" that KVM also references.

> It makes sense that if the secure firmware object handles (like the
> viommu, vdevice, vBDF) are accessed through iommufd then iommufd will

Yes, that tracks.

---

## [66] Alexey Kardashevskiy — 2025-03-17
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 15/3/25 12:11, Dan Williams wrote:
> Jason Gunthorpe wrote:
>> On Wed, Feb 26, 2025 at 11:12:32AM +1100, Alexey Kardashevskiy wrote:

It is about accessing MMIO with Cbit set, and running DMA to/from 
private memory, in DPDK. On AMD, if we want the PCI's Tbit in MMIO, the 
Cbit needs to be set in some page table. "TVM" in this case is a few 
private pages (+ bunch of PSP calls to bring to the right state) 
pretending to be a CVM which does not need to run. Thanks,


> or TDISP state management relative to a
> shared concept of a "TVM context" that KVM also references.

>> It makes sense that if the secure firmware object handles (like the
>> viommu, vdevice, vBDF) are accessed through iommufd then iommufd will

---

## [67] Jason Gunthorpe — 2025-03-19
*Subject: Re: [RFC PATCH v2 12/22] iommufd: Allow mapping from guest_memfd*

On Thu, Mar 13, 2025 at 03:51:13PM +1100, Alexey Kardashevskiy wrote:

> About this atomical restructure - I looked at yours iommu-pt branch on
> github but  __cut_mapping()->pt_table_install64() only atomically swaps the

That branch doesn't have the invalidation wired in, there is another
branch that has invalidation but not cut yet.. It is a journey

> And if it did so, that would not be atomic but it won't matter as
> long as we do not destroy the old PDE before invalidating IOMMU TLB,

When splitting the change in the PDE->PTE doesn't change the
translation in effect.

So if the IOTLB has cached the PDE, the SW will update it to an array
of PTEs of same address, any concurrent DMA will continue to hit the
same address, then when we invalidate the IOTLB the PDE will get
dropped from cache and the next DMA will load PTEs.

When I say atomic I mean from the perspective of the DMA initator
there is no visible alteration. Perhaps I should say hitless.

Jason

---

## [68] Francesco Lavra — 2025-03-22
*Subject: Re: [RFC PATCH v2 05/22] crypto: ccp: Enable SEV-TIO feature in the
 PSP when supported*

On 2025-02-18 at 11:09, Alexey Kardashevskiy wrote:
> @@ -601,6 +603,25 @@ struct sev_data_snp_addr {
>  	u64 address;				/* In/Out */

According to the SNP firmware ABI spec, support for SEV TIO commands is
indicated by bit 1 (bit 0 is for SEV legacy commands).

> +static int snp_get_feature_info(struct sev_device *sev, u32 ecx,
> struct sev_snp_feature_info *fi)

s/ret/psp_ret/

> +		return -EFAULT;
> +	if (!status.feature_info)

Same here

---

## [69] Francesco Lavra — 2025-03-23
*Subject: Re: [RFC PATCH v2 09/22] crypto/ccp: Implement SEV TIO firmware
 interface*

On 2025-02-18 at 11:09, Alexey Kardashevskiy wrote:
> diff --git a/drivers/crypto/ccp/sev-dev-tio.c
> b/drivers/crypto/ccp/sev-dev-tio.c

We have virt_to_pfn().

> +static struct sla_addr_t sla_alloc(size_t len, bool firmware_state)
> +{

This should be (npages + 1 > (...)), because we need to fit `npages`
SLAs plus the final SLA_EOL.

> +/* Expands a buffer, only firmware owned buffers allowed for now */
> +static int sla_expand(struct sla_addr_t *sla, size_t *len)

Return values are inconsistent with how this function is used in
sev_tio_do_cmd(): a zero value should indicate that expansion is not
required.

---

## [70] Alexey Kardashevskiy — 2025-03-26
*Subject: Re: [RFC PATCH v2 05/22] crypto: ccp: Enable SEV-TIO feature in the
 PSP when supported*

On 22/3/25 22:50, Francesco Lavra wrote:
> On 2025-02-18 at 11:09, Alexey Kardashevskiy wrote:
>> @@ -601,6 +603,25 @@ struct sev_data_snp_addr {

well, I wanted a bit number (which is 1) but this is wrong nevertheless:

present = (fi.ebx & SNP_FEATURE_FN8000_0024_EBX_X00_SEVTIO) != 0;

should be:

present = (fi.ebx & BIT(SNP_FEATURE_FN8000_0024_EBX_X00_SEVTIO)) != 0;

good spotting!

> 
>> +static int snp_get_feature_info(struct sev_device *sev, u32 ecx,

yeah I noticed this after posting. Thanks,

> 
>> +		return -EFAULT;

---

## [71] Alexey Kardashevskiy — 2025-03-27
*Subject: Re: [RFC PATCH v2 10/22] KVM: SVM: Add uAPI to change RMP for MMIO*

On 15/3/25 11:08, Dan Williams wrote:
> Alexey Kardashevskiy wrote:
>> The TDI bind operation moves the TDI into "RUN" state which means that


Well, I need to do better than the horrendous "[RFC PATCH v2 15/22] KVM: 
X86: Handle private MMIO as shared" and this one fits the purpose so 
yes. Thanks,

> 
> [1]: http://lore.kernel.org/20250123160827.GS5556@nvidia.com

---

## [72] Aneesh Kumar K.V — 2025-03-28
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

Alexey Kardashevskiy <aik@amd.com> writes:

....

> +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
> +{

Would this require an IOMMU_HWPT_ALLOC_NEST_PARENT page table
allocation? How would this work in cases where there's no need to set up
Stage 1 IOMMU tables?

Alternatively, should we allocate an IOMMU_HWPT_ALLOC_NEST_PARENT with a
Stage 1 disabled translation config? (In the ARM case, this could mean
marking STE entries as Stage 1 bypass and Stage 2 translate.)

Also, if a particular setup doesn't require creating IOMMU
entries because the entire guest RAM is identity-mapped in the IOMMU, do
we still need to make tsm_tdi_bind use this abstraction in iommufd?


> +
> +	idev = iommufd_get_device(ucmd, cmd->dev_id);

-aneesh

---

## [73] Jason Gunthorpe — 2025-04-01
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Mon, Mar 17, 2025 at 01:32:31PM +1100, Alexey Kardashevskiy wrote:

> It is about accessing MMIO with Cbit set, and running DMA to/from private
> memory, in DPDK. On AMD, if we want the PCI's Tbit in MMIO, the Cbit needs

Yeah, though that may be infeasible on other platforms. I'm pretty
sure ARM and Intel route the Tbit packets directly to their secure
worlds so there is no possibility for VFIO to use them without also
using the secure world to create a VM.

Maybe AMD is different, IDK.

Jason

---

## [74] Jason Gunthorpe — 2025-04-01
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Fri, Mar 28, 2025 at 10:57:18AM +0530, Aneesh Kumar K.V wrote:
> > +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)
> > +{

Probably. That flag is what forces a S2 page table.

> How would this work in cases where there's no need to set up Stage 1
> IOMMU tables?

Either attach the raw HWPT of the IOMMU_HWPT_ALLOC_NEST_PARENT or:

> Alternatively, should we allocate an IOMMU_HWPT_ALLOC_NEST_PARENT with a
> Stage 1 disabled translation config? (In the ARM case, this could mean

For arm you mean IOMMU_HWPT_DATA_ARM_SMMUV3.. But yes, this can work
too and is mandatory if you want the various viommu linked features to
work.

> Also, if a particular setup doesn't require creating IOMMU
> entries because the entire guest RAM is identity-mapped in the IOMMU, do

Even if the viommu will not be exposed to the guest I'm expecting that
iommufd will have a viommu object, just not use various features. We
are using viommu as the handle for the KVM, vmid and other things that
are likely important here.

Jason

---

## [75] Jason Gunthorpe — 2025-04-01
*Subject: Re: [RFC PATCH v2 13/22] iommufd: amd-iommu: Add vdevice support*

On Tue, Feb 18, 2025 at 10:10:00PM +1100, Alexey Kardashevskiy wrote:
> @@ -939,6 +939,7 @@ struct iommu_fault_alloc {
>  enum iommu_viommu_type {

This should probably be some kind of AMD_TSM and the driver data blob
should carry any additional data needed to create the vIOMMU that is
visible to the guest.

> @@ -2068,7 +2069,18 @@ static void set_dte_entry(struct amd_iommu *iommu,
>  		new.data[1] |= DTE_FLAG_IOTLB;

AMD should be implementing viommu natively without CC as well, try to
structure things so it fits together better. This should only trigger
for the CC viommu type..

> +		/*
> +		 * This runs when VFIO is bound to a device but TDI is not yet.

Just ignore NEST_PARENT? That seems wrong, it should force a V1 page
table??

> +static struct iommufd_viommu *amd_viommu_alloc(struct device *dev,
> +					       struct iommu_domain *parent,

This is not OK, the parent domain of the viommu can be used with
multiple viommu objects, it can't just have a naked back reference
like this.

You can get 1:1 domain objects linked to the viommu by creating the
'S1' type domains, maybe that is what you want here. A special domain
type that is TSM that has a special DTE.

Though I'd really rather see the domain attach logic and DTE formation
in the AMD driver be fixed up before we made it more complex :\

It would be nice to see normal nesting and viommu support first too :\

Jason

---

## [76] Jason Gunthorpe — 2025-04-01
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Tue, Feb 18, 2025 at 10:10:01PM +1100, Alexey Kardashevskiy wrote:
> When a TDISP-capable device is passed through, it is configured as
> a shared device to begin with. Later on when a VM probes the device,

Can you list here what the basic flow of iommufd calls is to create a
CC VM, with no vIOMMU, and a CC capable vPCI device?

I'd like the other arches to review this list and see how their arches
fit

Thanks
Jason

---

## [77] Alexey Kardashevskiy — 2025-04-03
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On 2/4/25 03:12, Jason Gunthorpe wrote:
> On Tue, Feb 18, 2025 at 10:10:01PM +1100, Alexey Kardashevskiy wrote:
>> When a TDISP-capable device is passed through, it is configured as

I do this in QEMU in additional to the usual VFIO setup:

iommufd_cdev_autodomains_get() [1]:

1. iommufd_backend_alloc_viommu
2. iommufd_backend_alloc_vdev


kvm_handle_vmgexit_tio_req() in KVM [2]:

1. (IOMMUFD) tio_bind(pdev, kvm_vmfd(kvm_state))
2. (KVM) kvm_set_memory_attributes_private(mmio region)
3. (SEV) sev_ioctl(/dev/sev, KVM_SEV_SNP_MMIO_RMP_UPDATE)
4. (IOMMUFD) tio_guest_request() /* enable DMA/MMIO in secure world */

> I'd like the other arches to review this list and see how their arches
> fit

Well, I have it all here: https://github.com/aik/qemu/tree/tsm
Raw stuff so I did not post it even as RFC but may be it'd help if I 
did? Thanks,

[1] 
https://github.com/aik/qemu/commit/da86ba11e71f10d48dd40a8d71a2ff595f04bb2d
[2] 
https://github.com/aik/qemu/commit/f804b65aff5b28f6f0430a5abca07cbac73f70bc

---

## [78] Francesco Lavra — 2025-04-05
*Subject: Re: [RFC PATCH v2 16/22] coco/tsm: Add tsm-guest module*

On 2025-02-18 at 11:10, Alexey Kardashevskiy wrote:
> diff --git a/drivers/virt/coco/guest/tsm-guest.c
> b/drivers/virt/coco/guest/tsm-guest.c

Missing call to tsm_tdi_put().

---

## [79] Francesco Lavra — 2025-04-05
*Subject: Re: [RFC PATCH v2 17/22] resource: Mark encrypted MMIO resource on
 validation*

On 2025-02-18 at 11:10, Alexey Kardashevskiy wrote:
> diff --git a/include/linux/ioport.h b/include/linux/ioport.h
> index 5385349f0b8a..f2e0b9f02373 100644

You may want to remove the reference to TDISP, as this flag could be
reused for non-PCI devices in the future.

> @@ -1085,6 +1092,47 @@ int adjust_resource(struct resource *res,
> resource_size_t start,

I don't think this function should walk the iomem_resource list, it can
simply modify res->flags, which is consistent with what is done by the
other *_resource() functions that take a pointer to a resource that is
expected to be in the list.
Also, the name of this function is unrelated to the name of the
affected flag, you may want to make these names more consistent.

---

## [80] Francesco Lavra — 2025-04-07
*Subject: Re: [RFC PATCH v2 18/22] coco/sev-guest: Implement the guest
 support for SEV TIO*

On 2025-02-18 at 11:10, Alexey Kardashevskiy wrote:
> 
> +static int handle_tio_guest_request(struct snp_guest_dev *snp_dev,

The logic to update *npages is missing.

> 
> +}

c1 is supposed to be a number of pages, not a number of bytes.

> +static int tio_tdi_status(struct tsm_tdi *tdi, struct snp_guest_dev
> *snp_dev,

The first argument should be rsp, not &rsp. This issue is also present
in the other memzero_explicit() calls in this patch.

> +static int sev_guest_tdi_validate(struct tsm_tdi *tdi, unsigned int
> featuremask,

This cannot happen, I think you meant (!ret && !tdi->report)
>

---

## [81] Aneesh Kumar K.V — 2025-04-07
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Fri, Mar 28, 2025 at 10:57:18AM +0530, Aneesh Kumar K.V wrote:
>> > +int iommufd_vdevice_tsm_bind_ioctl(struct iommufd_ucmd *ucmd)

I was trying to prototype this using kvmtool and I have run into some
issues. First i needed the below change for vIOMMU alloc to work

modified   drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
@@ -4405,6 +4405,8 @@ static int arm_smmu_device_hw_probe(struct arm_smmu_device *smmu)
 	reg = readl_relaxed(smmu->base + ARM_SMMU_IDR3);
 	if (FIELD_GET(IDR3_RIL, reg))
 		smmu->features |= ARM_SMMU_FEAT_RANGE_INV;
+	if (FIELD_GET(IDR3_FWB, reg))
+		smmu->features |= ARM_SMMU_FEAT_S2FWB;
 
 	/* IDR5 */
 	reg = readl_relaxed(smmu->base + ARM_SMMU_IDR5);



Also current code don't allow a Stage 1 bypass, Stage2 translation when
allocating HWPT.

arm_vsmmu_alloc_domain_nested -> arm_smmu_validate_vste -> 

	cfg = FIELD_GET(STRTAB_STE_0_CFG, le64_to_cpu(arg->ste[0]));
	if (cfg != STRTAB_STE_0_CFG_ABORT && cfg != STRTAB_STE_0_CFG_BYPASS &&
	    cfg != STRTAB_STE_0_CFG_S1_TRANS)
		return -EIO;


This only allow a abort or bypass or stage1 translate/stage2 bypass config

Also if we don't need stage1 table, what will
iommufd_viommu_alloc_hwpt_nested() return?

>
>> Also, if a particular setup doesn't require creating IOMMU

-aneesh

---

## [82] Jason Gunthorpe — 2025-04-07
*Subject: Re: [RFC PATCH v2 14/22] iommufd: Add TIO calls*

On Mon, Apr 07, 2025 at 05:10:29PM +0530, Aneesh Kumar K.V wrote:
> I was trying to prototype this using kvmtool and I have run into some
> issues. First i needed the below change for vIOMMU alloc to work

Oh wow, I don't know what happened there that the IDR3 got dropped
maybe a rebase mistake? It was in earlier versions of the patch at
least :\ Please send a formal patch!!

> Also current code don't allow a Stage 1 bypass, Stage2 translation when
> allocating HWPT.

The above is for the vSTE, the cfg is not copied as is to the host
STE. See how arm_smmu_make_nested_domain_ste() transforms it.

STRTAB_STE_0_CFG_ABORT blocks all DMA
STRTAB_STE_0_CFG_BYPASS "bypass" for the VM is S2 translation only
STRTAB_STE_0_CFG_S1_TRANS "s1 only" for the VM is S1 & S1 translation

> Also if we don't need stage1 table, what will
> iommufd_viommu_alloc_hwpt_nested() return?

A wrapper around whatever STE configuration that userspace requested
logically linked to the viommu.

Jason

---

## [83] Alexey Kardashevskiy — 2025-04-10
*Subject: Re: [RFC PATCH v2 13/22] iommufd: amd-iommu: Add vdevice support*

On 2/4/25 03:11, Jason Gunthorpe wrote:
> On Tue, Feb 18, 2025 at 10:10:00PM +1100, Alexey Kardashevskiy wrote:
>> @@ -939,6 +939,7 @@ struct iommu_fault_alloc {


Ahhh... This is because I still have troubles with what 
IOMMU_DOMAIN_NESTED means (and iommufd.rst does not help me). There is 
one device, one IOMMU table buuut 2 domains? Uh.


> 
>> +static struct iommufd_viommu *amd_viommu_alloc(struct device *dev,

Should not IOMMU_DOMAIN_NESTED be that "S1" domain? And what does "S1" 
mean here? Currently the domain in the hunk above is __IOMMU_DOMAIN_PAGING.

> Though I'd really rather see the domain attach logic and DTE formation
> in the AMD driver be fixed up before we made it more complex :\

It is in the works too. Thanks,

---

## [84] Tian, Kevin — 2025-04-10
*Subject: RE: [RFC PATCH v2 13/22] iommufd: amd-iommu: Add vdevice support*

> From: Alexey Kardashevskiy <aik@amd.com>
> Sent: Thursday, April 10, 2025 2:40 PM

(not yet catch up with the whole thread. so just for basics)

one device can be attached to only one domain. When the attached domain
is NESTED, the output from that domain will be further translated by another
domain (PARENT). so yes, 2 domains could be involved and two IOMMU
page tables chained in translation.

In that configuration, the NESTED domain is also called stage-1/s1 and its
parent domain is called stage-2/s2.

Typically seen in a setup where the guest sees a vIOMMU and manages its
own I/O page tables (translating guest IOVA to GPA). Then the GPA is
further translated by a host-managed I/O paging table (PAGING domain,
GPA->HPA).

a special case of s1 is 1:1 identity mapping (or passthrough), with which 
effectively only one domain (s2) manages translation but the concept of
nested translation still holds.

---

## [85] Jason Gunthorpe — 2025-04-10
*Subject: Re: [RFC PATCH v2 13/22] iommufd: amd-iommu: Add vdevice support*

On Thu, Apr 10, 2025 at 04:39:39PM +1000, Alexey Kardashevskiy wrote:
> > > @@ -2549,12 +2561,15 @@ amd_iommu_domain_alloc_paging_flags(struct device *dev, u32 flags,
> > >   {

It means whatever you want it to mean, so long as it holds a reference
to a NEST_PARENT :)

> > You can get 1:1 domain objects linked to the viommu by creating the
> > 'S1' type domains, maybe that is what you want here. A special domain

Yes that is how ARM is doing it.

Minimally IOMMU_DOMAIN_NESTED on AMD should refere to a partial DTE
fragment that sets the GCR3 information and other guest controlled
bits from the vDTE. It should hold a reference to the viommu and the
S2 NEST_PARENT.

From that basis then you'd try to fit in the CC stuff.

> > Though I'd really rather see the domain attach logic and DTE formation
> > in the AMD driver be fixed up before we made it more complex :\

I think your work will be easier to understand when viewed on top of
working basic nesting support as it is just a special case of that

Jason

---

## [86] Alexey Kardashevskiy — 2025-04-14
*Subject: Re: [RFC PATCH v2 13/22] iommufd: amd-iommu: Add vdevice support*

On 10/4/25 23:05, Jason Gunthorpe wrote:
> On Thu, Apr 10, 2025 at 04:39:39PM +1000, Alexey Kardashevskiy wrote:
>>>> @@ -2549,12 +2561,15 @@ amd_iommu_domain_alloc_paging_flags(struct device *dev, u32 flags,

ahhhh ;)

>>> You can get 1:1 domain objects linked to the viommu by creating the
>>> 'S1' type domains, maybe that is what you want here. A special domain

Really not sure about that "easier" thing :)

GCR3 is orthogonal to what I am doing here right now - this exercise does not use any additional guest table, instead it tells the host IOMMU (yeah, via the PSP) how to treat all IOVAs - private or shared (a bar called "vTOM" == virtual top of memory, below that bar everything is private, above - shared, I set it to the maximum). So even when we get vIOMMU in SNP VMs, unenlightened VM will be still using vTOM (SVSM == privileged VM FW which will talk to the PSP about vTOM).

This vTOM is very limited vIOMMU really (communicated just an address limit), not what people usually think when read "vIOMMU" with guest tables and 2 level translation.

---

## [87] Bjorn Helgaas — 2025-04-15
*Subject: Re: [RFC PATCH v2 01/22] pci/doe: Define protocol types and make
 those public*

Match capitalization of subject from previous history.

On Tue, Feb 18, 2025 at 10:09:48PM +1100, Alexey Kardashevskiy wrote:
> Already public pci_doe() takes a protocol type argument.
> PCIe 6.0 defines three, define them in a header for use with pci_doe().

Add section number to spec reference, rewrap paragraph to fill 75
columns.

Bjorn

---

## [88] Bjorn Helgaas — 2025-04-15
*Subject: Re: [RFC PATCH v2 08/22] pci/tsm: Add PCI driver for TSM*

Match subject capitalization style of history.

Drop second "PCI", mostly redundant.

On Tue, Feb 18, 2025 at 10:09:55PM +1100, Alexey Kardashevskiy wrote:
> The PCI TSM module scans the PCI bus to initialize a TSM context for
> physical ("TDEV") and virtual ("TDI") functions. It also implements

Expand "TSM" once here and maybe in the subject.

> + * Copyright(c) 2024 Intel Corporation. All rights reserved.

2025 now.

> +static int tsm_pci_dev_init(struct tsm_bus_subsys *tsm_bus,
> +			    struct pci_dev *pdev,

Move the tsm_dev_init() out of the automatic variable list.  Doing it
in the list is OK for trivial things, but this is kind of the meat of
the function.

> +	if (ret)
> +		return ret;

> +
> +static int tsm_pci_alloc_device(struct tsm_bus_subsys *tsm_bus,

Unnecessary initialization.

> +	/* Set up TDIs for HV (physical functions) and VM (all functions) */
> +	if ((pdev->devcap & PCI_EXP_DEVCAP_TEE) &&

> +
> +static void tsm_pci_dev_free(struct pci_dev *pdev)

Move at least the declaration to automatic list at entry.

> +	if (tdev) {
> +		tsm_dev_put(tdev);

Wrap to fit in 80 columns like the rest of drivers/pci/

> +{
> +	struct tsm_bus_subsys *tsm_bus = container_of(nb, struct tsm_bus_subsys, notifier);

Looks racy that we iterate through PCI devs before registering the
notifier.

> +	return tsm_bus;
> +}

> +static int __init tsm_pci_init(void)
> +{

Both init and cleanup messages are OK for debug, but probably not for
upstream.

> +config PCI_TSM
> +	tristate "TEE Security Manager for PCI Device Security"

Expand "TSM" here.  From menu line above, I guess it's "TEE Security
Manager"?

> +	  that manages device authentication, link encryption, link
> +	  integrity protection, and assignment of PCI device functions

---

## [89] Bjorn Helgaas — 2025-04-15
*Subject: Re: [RFC PATCH v2 19/22] RFC: pci: Add BUS_NOTIFY_PCI_BUS_MASTER
 event*

Match subject capitalization style.

On Tue, Feb 18, 2025 at 10:10:06PM +1100, Alexey Kardashevskiy wrote:
> TDISP allows secure MMIO access to a validated MMIO range.
> The validation is done in the TSM and after that point changing

Wrap all to fill 75 columns.

---

## [90] Bjorn Helgaas — 2025-04-15
*Subject: Re: [RFC PATCH v2 21/22] pci: Allow encrypted MMIO mapping via sysfs*

On Tue, Feb 18, 2025 at 10:10:08PM +1100, Alexey Kardashevskiy wrote:
> Add another resource#d_enc to allow mapping MMIO as
> an encrypted/private region.

I guess this means a sysfs file.  Document alongside the others.

> Unlike resourceN_wc, the node is added always as ability to
> map MMIO as private depends on negotiation with the TSM which

Match capitalization (subject) and wrap to fill 75 columns.

> +++ b/include/linux/pci.h
> @@ -2129,7 +2129,7 @@ pci_alloc_irq_vectors(struct pci_dev *dev, unsigned int min_vecs,

Wrap to fit in 80 columns.

>  
>  #ifndef arch_can_pci_mmap_wc

Ditto.

>  {
>  	unsigned long size;

s/Calling/Call/

> +	 */
> +	if (enc)

---

## [91] Bjorn Helgaas — 2025-04-15
*Subject: Re: [RFC PATCH v2 22/22] pci: Define pci_iomap_range_encrypted*

On Tue, Feb 18, 2025 at 10:10:09PM +1100, Alexey Kardashevskiy wrote:
> So far PCI BARs could not be mapped as encrypted so there was no
> need in API supporting encrypted mappings. TDISP is adding such

Match subject capitalization, rewrap.

> +void __iomem *pci_iomap_range_encrypted(struct pci_dev *dev,
> +					int bar,

"What?" indeed.  This could be removed or made to say something
intelligible.

> +	return NULL;
> +}

---

## [92] Alexey Kardashevskiy — 2025-04-24
*Subject: Re: [RFC PATCH v2 06/22] KVM: X86: Define tsm_get_vmid*

On 14/3/25 14:28, Alexey Kardashevskiy wrote:
> 
> 

> 
> c) Or move parts of struct kvm_sev_info/kvm_svm from arch/x86/kvm/svm/svm.h to arch/x86/include/asm/svm.h and do some trick to get kvm_sev_info from struct kvm.


Thanks for the suggestion, I ended up doing this and ditched the whole tsm_get_vmid() thing, looks semi-acceptable (at least contained to the AMD code) to keep going. Thanks,



> 
> d) In my RFC v1, I simply called tsm_tdi_bind() from KVM-AMD with this cookie but that assumed KVM knowledge of PCI which I dropped in this RFC so the bind request travels via QEMU between the guest and the PSP.

---
