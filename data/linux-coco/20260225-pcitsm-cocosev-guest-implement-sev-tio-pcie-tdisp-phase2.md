---
title: 'PCI/TSM: coco/sev-guest: Implement SEV-TIO PCIe TDISP (phase2)'
date: 2026-02-25
last_reply: 2026-04-30
message_count: 56
participants: ['Alexey Kardashevskiy', 'Borislav Petkov', 'dan.j.williams@intel.com', 'Arnd Bergmann', 'Robin Murphy', 'Bjorn Helgaas', 'Jason Gunthorpe', 'Aneesh Kumar K.V', 'Jason Gunthorpe']
---

## [1] Alexey Kardashevskiy — 2026-02-25

Here are some patches to continue enabling SEV-TIO on AMD.

SEV-TIO allows guests to establish trust in a device that supports TEE
Device Interface Security Protocol (TDISP, defined in PCIe r6.0+) and
then interact with the device via private memory.

In order to streamline upstreaming process, a common TSM infrastructure
is being developed in collaboration with Intel+ARM+RiscV. There is
Documentation/driver-api/pci/tsm.rst with proposed phases:
1. IDE: encrypt PCI, host only
2. TDISP: lock + accept flow, host and guest, interface report
3. Enable secure MMIO + DMA: IOMMUFD, KVM changes
4. Device attestation: certificates, measurements

This is phase2 == basic guest support allowing TDISP CONFIG_LOCKED and RUN states, and unlocking as well.

Acronyms:
TEE - Trusted Execution Environments, a concept of managing trust between the host and devices
TSM - TEE Security Manager (TSM), an entity which ensures security on the host
PSP - AMD platform secure processor (also "ASP", "AMD-SP"), acts as TSM on AMD.
SEV TIO - the TIO protocol implemented by the PSP and used by the host, extension to SEV-SNP
GHCB - guest/host communication block - a protocol for guest-to-host communication via a shared page
TDISP - TEE Device Interface Security Protocol (PCIe).



Flow:
- Boot guest OS, load sev-guest.ko which registers itself as a TSM
- PCI TSM creates sysfs nodes under "tsm" subdirectory in for all
  TDISP-capable devices
  - lock the device via:
  	echo tsm0 > "/sys/bus/pci/devices/0000:01:00.0/tsm/lock"
  - accept the device via:
  	echo 1 > "/sys/bus/pci/devices/0000:01:00.0/tsm/accept"
  - load the device driver:
  	- DMA to encrypted memory should work right away
	- MMIO regions reported in TDISP interface report will be mapped as encrypted


Since one of my test devices does not use private MMIO for the main function,
there is 9/9 which allows https://github.com/billfarrow/pcimem.git mapping MMIO as private.


The previous conversation is here:
https://lore.kernel.org/r/20250218111017.491719-1-aik@amd.com 

This is based on sha1
4fe8662d1a9c Dan Williams PCI/TSM: Documentation: Add Maturity Map
from
https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging
and 3 cherrypicks on top, please find the exact tree at:
https://github.com/AMDESE/linux-kvm/commits/tsm-staging

The host support is pushed here:
https://github.com/AMDESE/linux-kvm/commits/tsm

The SEV TIO spec:
https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58271.pdf

Individual patches have extra "---" comments (could have been "RFC"?)

Please comment. Thanks.

ps: quite a cc list from get_maintainers.pl.



Alexey Kardashevskiy (9):
  pci/tsm: Add TDISP report blob and helpers to parse it
  pci/tsm: Add tsm_tdi_status
  coco/sev-guest: Allow multiple source files in the driver
  dma/swiotlb: Stop forcing SWIOTLB for TDISP devices
  x86/mm: Stop forcing decrypted page state for TDISP devices
  x86/dma-direct: Stop changing encrypted page state for TDISP devices
  coco/sev-guest: Implement the guest support for SEV TIO (phase2)
  RFC: PCI: Avoid needless touching of Command register
  pci: Allow encrypted MMIO mapping via sysfs

 arch/x86/Kconfig                        |   1 +
 drivers/virt/coco/sev-guest/Kconfig     |   1 +
 drivers/virt/coco/sev-guest/Makefile    |   6 +-
 arch/x86/include/asm/dma-direct.h       |  39 ++
 arch/x86/include/asm/sev-common.h       |   1 +
 arch/x86/include/asm/sev.h              |  13 +
 arch/x86/include/uapi/asm/svm.h         |  13 +
 drivers/virt/coco/sev-guest/sev-guest.h |  20 +
 include/linux/pci-tsm.h                 | 110 +++
 include/linux/pci.h                     |   2 +-
 include/linux/psp-sev.h                 |  31 +
 include/linux/swiotlb.h                 |   9 +
 include/uapi/linux/sev-guest.h          |  43 ++
 arch/x86/coco/sev/core.c                |  53 ++
 arch/x86/mm/mem_encrypt.c               |   5 +-
 drivers/pci/mmap.c                      |  11 +-
 drivers/pci/pci-sysfs.c                 |  27 +-
 drivers/pci/probe.c                     |   5 +
 drivers/pci/proc.c                      |   2 +-
 drivers/pci/quirks.c                    |   9 +
 drivers/virt/coco/sev-guest/sev-guest.c |  23 +-
 drivers/virt/coco/sev-guest/tio.c       | 707 ++++++++++++++++++++
 drivers/virt/coco/tsm-core.c            |  19 +
 23 files changed, 1129 insertions(+), 21 deletions(-)
 create mode 100644 arch/x86/include/asm/dma-direct.h
 create mode 100644 drivers/virt/coco/sev-guest/sev-guest.h
 create mode 100644 drivers/virt/coco/sev-guest/tio.c

---

## [2] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 1/9] pci/tsm: Add TDISP report blob and helpers to parse it*

The TDI interface report is defined in PCIe r7.0,
chapter "11.3.11 DEVICE_INTERFACE_REPORT". The report enumerates
MMIO resources and their properties which will take effect upon
transitioning to the RUN state.

Store the report in pci_tsm.

Define macros and helpers to parse the binary blob.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

Probably pci_tsm::report could be struct tdi_report_header*?
---
 include/linux/pci-tsm.h      | 84 ++++++++++++++++++++
 drivers/virt/coco/tsm-core.c | 19 +++++
 2 files changed, 103 insertions(+)

diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index b984711fa91f..7987ede76914 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -10,6 +10,18 @@ struct tsm_dev;
 struct kvm;
 enum pci_tsm_req_scope;
 
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
 /*
  * struct pci_tsm_ops - manage confidential links and security state
  * @link_ops: Coordinate PCIe SPDM and IDE establishment via a platform TSM.
@@ -123,6 +135,7 @@ struct pci_tsm {
 	struct pci_dev *dsm_dev;
 	struct tsm_dev *tsm_dev;
 	struct pci_tdi *tdi;
+	struct tsm_blob *report;
 };
 
 /**
@@ -271,4 +284,75 @@ static inline ssize_t pci_tsm_guest_req(struct pci_dev *pdev,
 	return -ENXIO;
 }
 #endif
+
+/*
+ * struct tdisp_interface_id - TDISP INTERFACE_ID Definition
+ *
+ * @function_id: Identifies the function of the device hosting the TDI
+ *   15:0: @rid: Requester ID
+ *   23:16: @rseg: Requester Segment (Reserved if Requester Segment Valid is Clear)
+ *   24: @rseg_valid: Requester Segment Valid
+ *   31:25 – Reserved
+ * 8B - Reserved
+ */
+#define TSM_TDISP_IID_REQUESTER_ID	GENMASK(15, 0)
+#define TSM_TDISP_IID_RSEG		GENMASK(23, 16)
+#define TSM_TDISP_IID_RSEG_VALID	BIT(24)
+
+struct tdisp_interface_id {
+	__u32 function_id; /* TSM_TDISP_IID_xxxx */
+	__u8 reserved[8];
+} __packed;
+
+#define SPDM_MEASUREMENTS_NONCE_LEN	32
+typedef __u8 spdm_measurements_nonce_t[SPDM_MEASUREMENTS_NONCE_LEN];
+
+/*
+ * TDI Report Structure as defined in TDISP.
+ */
+#define _BITSH(x)	(1 << (x))
+#define TSM_TDI_REPORT_NO_FW_UPDATE	_BITSH(0)  /* not updates in CONFIG_LOCKED or RUN */
+#define TSM_TDI_REPORT_DMA_NO_PASID	_BITSH(1)  /* TDI generates DMA requests without PASID */
+#define TSM_TDI_REPORT_DMA_PASID	_BITSH(2)  /* TDI generates DMA requests with PASID */
+#define TSM_TDI_REPORT_ATS		_BITSH(3)  /* ATS supported and enabled for the TDI */
+#define TSM_TDI_REPORT_PRS		_BITSH(4)  /* PRS supported and enabled for the TDI */
+
+struct tdi_report_header {
+	__u16 interface_info; /* TSM_TDI_REPORT_xxx */
+	__u16 reserved2;
+	__u16 msi_x_message_control;
+	__u16 lnr_control;
+	__u32 tph_control;
+	__u32 mmio_range_count;
+} __packed;
+
+/*
+ * Each MMIO Range of the TDI is reported with the MMIO reporting offset added.
+ * Base and size in units of 4K pages
+ */
+#define TSM_TDI_REPORT_MMIO_MSIX_TABLE		BIT(0)
+#define TSM_TDI_REPORT_MMIO_PBA			BIT(1)
+#define TSM_TDI_REPORT_MMIO_IS_NON_TEE		BIT(2)
+#define TSM_TDI_REPORT_MMIO_IS_UPDATABLE	BIT(3)
+#define TSM_TDI_REPORT_MMIO_RESERVED		GENMASK(15, 4)
+#define TSM_TDI_REPORT_MMIO_RANGE_ID		GENMASK(31, 16)
+
+struct tdi_report_mmio_range {
+	__u64 first_page;		/* First 4K page with offset added */
+	__u32 num;			/* Number of 4K pages in this range */
+	__u32 range_attributes;		/* TSM_TDI_REPORT_MMIO_xxx */
+} __packed;
+
+struct tdi_report_footer {
+	__u32 device_specific_info_len;
+	__u8 device_specific_info[];
+} __packed;
+
+#define TDI_REPORT_HDR(rep)		((struct tdi_report_header *) ((rep)->data))
+#define TDI_REPORT_MR_NUM(rep)		(TDI_REPORT_HDR(rep)->mmio_range_count)
+#define TDI_REPORT_MR_OFF(rep)		((struct tdi_report_mmio_range *) (TDI_REPORT_HDR(rep) + 1))
+#define TDI_REPORT_MR(rep, rangeid)	TDI_REPORT_MR_OFF(rep)[rangeid]
+#define TDI_REPORT_FTR(rep)		((struct tdi_report_footer *) &TDI_REPORT_MR((rep), \
+					TDI_REPORT_MR_NUM(rep)))
+
 #endif /*__PCI_TSM_H */
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index e65ab3461d14..3929176b8d3b 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -16,6 +16,25 @@ static struct class *tsm_class;
 static DECLARE_RWSEM(tsm_rwsem);
 static DEFINE_IDA(tsm_ida);
 
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
 static int match_id(struct device *dev, const void *data)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, struct tsm_dev, dev);

---

## [3] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 2/9] pci/tsm: Add tsm_tdi_status*

Define a structure with all info about a TDI such as TDISP status,
bind state, used START_INTERFACE options and the report digest.

This will be extended and shared to the userspace.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

Make it uapi? We might want a sysfs node per a field so probably not.
For now its only user is AMD SEV TIO with a plan to expose this struct
as a whole via sysfs.
---
 include/linux/pci-tsm.h | 26 ++++++++++++++++++++
 1 file changed, 26 insertions(+)

diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 7987ede76914..8086f358c51b 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -355,4 +355,30 @@ struct tdi_report_footer {
 #define TDI_REPORT_FTR(rep)		((struct tdi_report_footer *) &TDI_REPORT_MR((rep), \
 					TDI_REPORT_MR_NUM(rep)))
 
+enum tsm_tdisp_state {
+	TDISP_STATE_CONFIG_UNLOCKED = 0,
+	TDISP_STATE_CONFIG_LOCKED = 1,
+	TDISP_STATE_RUN = 2,
+	TDISP_STATE_ERROR = 3,
+};
+
+enum tsm_tdisp_status {
+	TDISP_STATE_BOUND = 0,
+	TDISP_STATE_INVALID = 1,
+	TDISP_STATE_UNBOUND = 2,
+};
+
+struct tsm_tdi_status {
+	__u8 status; /* enum tsm_tdisp_status */
+	__u8 state; /* enum tsm_tdisp_state */
+	__u8 all_request_redirect;
+	__u8 bind_p2p;
+	__u8 lock_msix;
+	__u8 no_fw_update;
+	__u16 cache_line_size;
+	__u8 interface_report_digest[48];
+	__u64 intf_report_counter;
+	struct tdisp_interface_id id;
+} __packed;
+
 #endif /*__PCI_TSM_H */

---

## [4] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 3/9] coco/sev-guest: Allow multiple source files in the driver*

Prepare for SEV-TIO support as it is going to equal or bigger
than the existing sev_guest.c which is already 700 lines and
keeps growing.

No behavioural change expected.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/sev-guest/Makefile    |  3 ++-
 drivers/virt/coco/sev-guest/sev-guest.h | 16 ++++++++++++++++
 drivers/virt/coco/sev-guest/sev-guest.c | 10 ++--------
 3 files changed, 20 insertions(+), 9 deletions(-)

diff --git a/drivers/virt/coco/sev-guest/Makefile b/drivers/virt/coco/sev-guest/Makefile
index 63d67c27723a..9604792e0095 100644
--- a/drivers/virt/coco/sev-guest/Makefile
+++ b/drivers/virt/coco/sev-guest/Makefile
@@ -1,2 +1,3 @@
 # SPDX-License-Identifier: GPL-2.0-only
-obj-$(CONFIG_SEV_GUEST) += sev-guest.o
+obj-$(CONFIG_SEV_GUEST) += sev_guest.o
+sev_guest-y += sev-guest.o
diff --git a/drivers/virt/coco/sev-guest/sev-guest.h b/drivers/virt/coco/sev-guest/sev-guest.h
new file mode 100644
index 000000000000..b2a97778e635
--- /dev/null
+++ b/drivers/virt/coco/sev-guest/sev-guest.h
@@ -0,0 +1,16 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+
+#ifndef __SEV_GUEST_H__
+#define __SEV_GUEST_H__
+
+#include <linux/miscdevice.h>
+#include <asm/sev.h>
+
+struct snp_guest_dev {
+	struct device *dev;
+	struct miscdevice misc;
+
+	struct snp_msg_desc *msg_desc;
+};
+
+#endif /* __SEV_GUEST_H__ */
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index b01ec99106cd..e1ceeab54a21 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -28,19 +28,13 @@
 #include <uapi/linux/psp-sev.h>
 
 #include <asm/svm.h>
-#include <asm/sev.h>
+
+#include "sev-guest.h"
 
 #define DEVICE_NAME	"sev-guest"
 
 #define SVSM_MAX_RETRIES		3
 
-struct snp_guest_dev {
-	struct device *dev;
-	struct miscdevice misc;
-
-	struct snp_msg_desc *msg_desc;
-};
-
 /*
  * The VMPCK ID represents the key used by the SNP guest to communicate with the
  * SEV firmware in the AMD Secure Processor (ASP, aka PSP). By default, the key

---

## [5] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP devices*

SWIOTLB is enforced when encrypted guest memory is detected
in pci_swiotlb_detect() which is required for legacy devices.

Skip SWIOTLB for TDISP devices.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/swiotlb.h | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..119c25d639a7 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -173,6 +173,15 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+	/*
+	 * CC_ATTR_GUEST_MEM_ENCRYPT enforces SWIOTLB_FORCE in
+	 * swiotlb_init_remap() to allow legacy devices access arbitrary
+	 * VM encrypted memory.
+	 * Skip it for TDISP devices capable of DMA-ing the encrypted memory.
+	 */
+	if (device_cc_accepted(dev))
+		return false;
+
 	return mem && mem->force_bounce;
 }

---

## [6] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 5/9] x86/mm: Stop forcing decrypted page state for TDISP devices*

The DMA subsystem does is forcing private-to-shared
page conversion in force_dma_unencrypted().

Return false from force_dma_unencrypted() for TDISP devices.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 arch/x86/mm/mem_encrypt.c | 5 +++--
 1 file changed, 3 insertions(+), 2 deletions(-)

diff --git a/arch/x86/mm/mem_encrypt.c b/arch/x86/mm/mem_encrypt.c
index 95bae74fdab2..8daa6482b080 100644
--- a/arch/x86/mm/mem_encrypt.c
+++ b/arch/x86/mm/mem_encrypt.c
@@ -20,10 +20,11 @@
 bool force_dma_unencrypted(struct device *dev)
 {
 	/*
-	 * For SEV, all DMA must be to unencrypted addresses.
+	 * dma_direct_alloc() forces page state change if private memory is
+	 * allocated for DMA. Skip conversion if the TDISP device is accepted.
 	 */
 	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
-		return true;
+		return !device_cc_accepted(dev);
 
 	/*
 	 * For SME, all DMA must be to unencrypted addresses if the

---

## [7] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page state for TDISP devices*

TDISP devices operate in CoCo VMs only and capable of accessing
encrypted guest memory.

Currently when SME is on, the DMA subsystem forces the SME mask in
DMA handles in phys_to_dma() which assumes IOMMU pass through
which is never the case with CoCoVM running with a TDISP device.

Define X86's version of phys_to_dma() to skip leaking SME mask to
the device.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

Doing this in the generic version breaks ARM which uses
the SME mask in DMA handles, hence ARCH_HAS_PHYS_TO_DMA.

pci_device_add() enforces the FFFF_FFFF coherent DMA mask so
dma_alloc_coherent() fails when SME=on, this is how I ended up fixing
phys_to_dma() and not quite sure it is the right fix.
---
 arch/x86/Kconfig                  |  1 +
 arch/x86/include/asm/dma-direct.h | 39 ++++++++++++++++++++
 2 files changed, 40 insertions(+)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index fa3b616af03a..c46283064518 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -112,6 +112,7 @@ config X86
 	select ARCH_HAS_UBSAN
 	select ARCH_HAS_DEBUG_WX
 	select ARCH_HAS_ZONE_DMA_SET if EXPERT
+	select ARCH_HAS_PHYS_TO_DMA
 	select ARCH_HAVE_NMI_SAFE_CMPXCHG
 	select ARCH_HAVE_EXTRA_ELF_NOTES
 	select ARCH_MHP_MEMMAP_ON_MEMORY_ENABLE
diff --git a/arch/x86/include/asm/dma-direct.h b/arch/x86/include/asm/dma-direct.h
new file mode 100644
index 000000000000..f50e03d643c1
--- /dev/null
+++ b/arch/x86/include/asm/dma-direct.h
@@ -0,0 +1,39 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef ASM_X86_DMA_DIRECT_H
+#define ASM_X86_DMA_DIRECT_H 1
+
+static inline dma_addr_t __phys_to_dma(struct device *dev, phys_addr_t paddr)
+{
+	if (dev->dma_range_map)
+		return translate_phys_to_dma(dev, paddr);
+	return paddr;
+}
+
+static inline dma_addr_t phys_to_dma(struct device *dev, phys_addr_t paddr)
+{
+	/*
+	 * TDISP devices only work in CoCoVMs and rely on IOMMU to
+	 * decide on the memory encryption.
+	 * Stop leaking the SME mask in DMA handles and return
+	 * the real address.
+	 */
+	if (device_cc_accepted(dev))
+		return dma_addr_unencrypted(__phys_to_dma(dev, paddr));
+
+	return dma_addr_encrypted(__phys_to_dma(dev, paddr));
+}
+
+static inline phys_addr_t dma_to_phys(struct device *dev, dma_addr_t daddr)
+{
+	return daddr;
+}
+
+static inline dma_addr_t phys_to_dma_unencrypted(struct device *dev,
+						 phys_addr_t paddr)
+{
+	return dma_addr_unencrypted(__phys_to_dma(dev, paddr));
+}
+
+#define phys_to_dma_unencrypted phys_to_dma_unencrypted
+
+#endif /* ASM_X86_DMA_DIRECT_H */

---

## [8] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 7/9] coco/sev-guest: Implement the guest support for SEV TIO (phase2)*

Implement the SEV-TIO (Trusted I/O) support in for AMD SEV-SNP guests.

The implementation includes Device Security Manager (DSM) operations
for:
- binding a PCI function (GHCB extension) to a VM and locking
the device configuration;
- receiving TDI report and configuring MMIO and DMA/sDTE;
- accepting the device into the guest TCB.

Detect the SEV-TIO support (reported via GHCB HV features) and install
the SEV-TIO TSM ops.

Implement lock/accept/unlock TSM ops.

Define 2 new VMGEXIT codes for GHCB:
- TIO Guest Request to provide secure communication between a VM and
the FW (for configuring MMIO and DMA);
- TIO Op for requesting the HV to bind a TDI to the VM and for
starting/stopping a TDI.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/virt/coco/sev-guest/Kconfig     |   1 +
 drivers/virt/coco/sev-guest/Makefile    |   3 +
 arch/x86/include/asm/sev-common.h       |   1 +
 arch/x86/include/asm/sev.h              |  13 +
 arch/x86/include/uapi/asm/svm.h         |  13 +
 drivers/virt/coco/sev-guest/sev-guest.h |   4 +
 include/linux/psp-sev.h                 |  31 +
 include/uapi/linux/sev-guest.h          |  43 ++
 arch/x86/coco/sev/core.c                |  53 ++
 drivers/virt/coco/sev-guest/sev-guest.c |  13 +
 drivers/virt/coco/sev-guest/tio.c       | 707 ++++++++++++++++++++
 11 files changed, 882 insertions(+)

diff --git a/drivers/virt/coco/sev-guest/Kconfig b/drivers/virt/coco/sev-guest/Kconfig
index a6405ab6c2c3..4255072dfa1a 100644
--- a/drivers/virt/coco/sev-guest/Kconfig
+++ b/drivers/virt/coco/sev-guest/Kconfig
@@ -3,6 +3,7 @@ config SEV_GUEST
 	default m
 	depends on AMD_MEM_ENCRYPT
 	select TSM_REPORTS
+	select PCI_TSM if PCI
 	help
 	  SEV-SNP firmware provides the guest a mechanism to communicate with
 	  the PSP without risk from a malicious hypervisor who wishes to read,
diff --git a/drivers/virt/coco/sev-guest/Makefile b/drivers/virt/coco/sev-guest/Makefile
index 9604792e0095..b4766289c85f 100644
--- a/drivers/virt/coco/sev-guest/Makefile
+++ b/drivers/virt/coco/sev-guest/Makefile
@@ -1,3 +1,6 @@
 # SPDX-License-Identifier: GPL-2.0-only
 obj-$(CONFIG_SEV_GUEST) += sev_guest.o
 sev_guest-y += sev-guest.o
+ifeq ($(CONFIG_PCI_TSM),y)
+sev_guest-y += tio.o
+endif
diff --git a/arch/x86/include/asm/sev-common.h b/arch/x86/include/asm/sev-common.h
index 01a6e4dbe423..ff763c3c5d63 100644
--- a/arch/x86/include/asm/sev-common.h
+++ b/arch/x86/include/asm/sev-common.h
@@ -137,6 +137,7 @@ enum psc_op {
 #define GHCB_HV_FT_SNP			BIT_ULL(0)
 #define GHCB_HV_FT_SNP_AP_CREATION	BIT_ULL(1)
 #define GHCB_HV_FT_SNP_MULTI_VMPL	BIT_ULL(5)
+#define GHCB_HV_FT_SNP_SEV_TIO		BIT_ULL(7)
 
 /*
  * SNP Page State Change NAE event
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 0e6c0940100f..f6e1a2f96d47 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -149,6 +149,8 @@ struct snp_req_data {
 	unsigned long resp_gpa;
 	unsigned long data_gpa;
 	unsigned int data_npages;
+	unsigned int guest_rid;
+	unsigned long param;
 };
 
 #define MAX_AUTHTAG_LEN		32
@@ -179,6 +181,14 @@ enum msg_type {
 
 	SNP_MSG_TSC_INFO_REQ = 17,
 	SNP_MSG_TSC_INFO_RSP,
+	TIO_MSG_TDI_INFO_REQ = 19,
+	TIO_MSG_TDI_INFO_RSP = 20,
+	TIO_MSG_MMIO_VALIDATE_REQ = 21,
+	TIO_MSG_MMIO_VALIDATE_RSP = 22,
+	TIO_MSG_MMIO_CONFIG_REQ = 23,
+	TIO_MSG_MMIO_CONFIG_RSP = 24,
+	TIO_MSG_SDTE_WRITE_REQ = 25,
+	TIO_MSG_SDTE_WRITE_RSP = 26,
 
 	SNP_MSG_TYPE_MAX
 };
@@ -597,6 +607,9 @@ static inline void sev_evict_cache(void *va, int npages)
 	}
 }
 
+bool sev_tio_ghcb_supported(void);
+int sev_tio_op(u32 guest_rid, unsigned int op, u64 *fw_err, u64 *tdi_id);
+
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
 #define snp_vmpl 0
diff --git a/arch/x86/include/uapi/asm/svm.h b/arch/x86/include/uapi/asm/svm.h
index 650e3256ea7d..c4b735d0aa1e 100644
--- a/arch/x86/include/uapi/asm/svm.h
+++ b/arch/x86/include/uapi/asm/svm.h
@@ -122,6 +122,17 @@
 #define SVM_VMGEXIT_SAVIC_REGISTER_GPA		0
 #define SVM_VMGEXIT_SAVIC_UNREGISTER_GPA	1
 #define SVM_VMGEXIT_SAVIC_SELF_GPA		~0ULL
+#define SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST	0x80000020
+#define SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST_PARAM_STATE	BIT(0)
+#define SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST_PARAM_REPORT	BIT(3)
+#define SVM_VMGEXIT_SEV_TIO_OP			0x80000021
+#define SVM_VMGEXIT_SEV_TIO_OP_PARAM(guest_id, action)	((u64)(action)<<32|(guest_id))
+#define SVM_VMGEXIT_SEV_TIO_OP_ACTION(exitinfo1)	((exitinfo1)>>32)
+#define SVM_VMGEXIT_SEV_TIO_OP_GUEST_ID(exitinfo1)	((exitinfo1) & 0xFFFFFFFF)
+#define SVM_VMGEXIT_SEV_TIO_OP_BIND	0
+#define SVM_VMGEXIT_SEV_TIO_OP_UNBIND	1
+#define SVM_VMGEXIT_SEV_TIO_OP_RUN	2
+#define SVM_VMGEXIT_SEV_TIO_OP_STOP	3
 #define SVM_VMGEXIT_HV_FEATURES			0x8000fffd
 #define SVM_VMGEXIT_TERM_REQUEST		0x8000fffe
 #define SVM_VMGEXIT_TERM_REASON(reason_set, reason_code)	\
@@ -245,6 +256,8 @@
 	{ SVM_VMGEXIT_GUEST_REQUEST,	"vmgexit_guest_request" }, \
 	{ SVM_VMGEXIT_EXT_GUEST_REQUEST, "vmgexit_ext_guest_request" }, \
 	{ SVM_VMGEXIT_AP_CREATION,	"vmgexit_ap_creation" }, \
+	{ SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST, "vmgexit_sev_tio_guest_request" }, \
+	{ SVM_VMGEXIT_SEV_TIO_OP,	"vmgexit_sev_tio_op" }, \
 	{ SVM_VMGEXIT_HV_FEATURES,	"vmgexit_hypervisor_feature" }, \
 	{ SVM_EXIT_ERR,         "invalid_guest_state" }
 
diff --git a/drivers/virt/coco/sev-guest/sev-guest.h b/drivers/virt/coco/sev-guest/sev-guest.h
index b2a97778e635..c823a782739f 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.h
+++ b/drivers/virt/coco/sev-guest/sev-guest.h
@@ -11,6 +11,10 @@ struct snp_guest_dev {
 	struct miscdevice misc;
 
 	struct snp_msg_desc *msg_desc;
+
+	struct tsm_dev *tsmdev;
 };
 
+void sev_guest_tsm_set_ops(bool set, struct snp_guest_dev *snp_dev);
+
 #endif /* __SEV_GUEST_H__ */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index cce864dbf281..dc2932953abc 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -1050,4 +1050,35 @@ static inline bool sev_is_snp_ciphertext_hiding_supported(void) { return false;
 
 #endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
 
+/*
+ * Status codes from TIO_MSG_MMIO_VALIDATE_REQ
+ */
+enum mmio_validate_status {
+	MMIO_VALIDATE_SUCCESS = 0,
+	MMIO_VALIDATE_INVALID_TDI = 1,
+	MMIO_VALIDATE_TDI_UNBOUND = 2,
+	MMIO_VALIDATE_NOT_ASSIGNED = 3,
+	MMIO_VALIDATE_NOT_IO = 4,
+	MMIO_VALIDATE_NOT_UNIFORM = 5,  /* The Validated bit is not uniformly set for
+					   the MMIO subrange */
+	MMIO_VALIDATE_NOT_IMMUTABLE = 6,/* At least one page does not have immutable bit set
+					   when validated bit is clear */
+	MMIO_VALIDATE_NOT_MAPPED = 7,   /* At least one page is not mapped to the expected GPA */
+	MMIO_VALIDATE_NOT_REPORTED = 8, /* The provided MMIO range ID is not reported in
+					   the interface report */
+	MMIO_VALIDATE_OUT_OF_RANGE = 9, /* The subrange is out the MMIO range in
+					   the interface report */
+	MMIO_VALIDATE_NOT_4K = 10,	/* At least one page is not 4K page size */
+};
+
+/*
+ * Status codes from TIO_MSG_SDTE_WRITE_REQ
+ */
+enum sdte_write_status {
+	SDTE_WRITE_SUCCESS = 0,
+	SDTE_WRITE_INVALID_TDI = 1,
+	SDTE_WRITE_TDI_NOT_BOUND = 2,
+	SDTE_WRITE_RESERVED = 3,
+};
+
 #endif	/* __PSP_SEV_H__ */
diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
index fcdfea767fca..5015160254f4 100644
--- a/include/uapi/linux/sev-guest.h
+++ b/include/uapi/linux/sev-guest.h
@@ -13,6 +13,7 @@
 #define __UAPI_LINUX_SEV_GUEST_H_
 
 #include <linux/types.h>
+#include <linux/uuid.h>
 
 #define SNP_REPORT_USER_DATA_SIZE 64
 
@@ -96,4 +97,46 @@ struct snp_ext_report_req {
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
+#define MMIO_VALIDATE_PRIVATE(r)  (!!((r) & BIT(3)))
+
+#define MMIO_MK_VALIDATE(start, size, range_id, private) \
+	(MMIO_VALIDATE_GPA(start) | \
+	(get_order(size) << 4) | \
+	((private) ? BIT(3) : 0) | \
+	((range_id) & 7) )
+
+#define SDTE_VALIDATE		1
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
index 9ae3b11754e6..1f2e34367772 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -136,6 +136,43 @@ static unsigned long snp_tsc_freq_khz __ro_after_init;
 DEFINE_PER_CPU(struct sev_es_runtime_data*, runtime_data);
 DEFINE_PER_CPU(struct sev_es_save_area *, sev_vmsa);
 
+bool sev_tio_ghcb_supported(void)
+{
+	return !!(sev_hv_features & GHCB_HV_FT_SNP_SEV_TIO);
+}
+EXPORT_SYMBOL_GPL(sev_tio_ghcb_supported);
+
+int sev_tio_op(u32 guest_rid, unsigned int op, u64 *fw_err, u64 *tdi_id)
+{
+	struct ghcb_state state;
+	struct es_em_ctxt ctxt;
+	struct ghcb *ghcb;
+	int ret;
+
+	/* __sev_get_ghcb() needs IRQs disabled because it uses per-CPU GHCB. */
+	guard(irqsave)();
+
+	ghcb = __sev_get_ghcb(&state);
+	if (!ghcb)
+		return -EIO;
+
+	vc_ghcb_invalidate(ghcb);
+	ret = sev_es_ghcb_hv_call(ghcb, &ctxt, SVM_VMGEXIT_SEV_TIO_OP,
+				  SVM_VMGEXIT_SEV_TIO_OP_PARAM(guest_rid, op), 0);
+
+	*fw_err = ghcb->save.sw_exit_info_2;
+	if (*fw_err)
+		ret = -EIO;
+
+	if (!ret && op == SVM_VMGEXIT_SEV_TIO_OP_BIND && tdi_id)
+		*tdi_id = ghcb_get_rcx(ghcb);
+
+	__sev_put_ghcb(&state);
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(sev_tio_op);
+
 /*
  * SVSM related information:
  *   When running under an SVSM, the VMPL that Linux is executing at must be
@@ -1666,6 +1703,11 @@ static int snp_issue_guest_request(struct snp_guest_req *req)
 	if (req->exit_code == SVM_VMGEXIT_EXT_GUEST_REQUEST) {
 		ghcb_set_rax(ghcb, input->data_gpa);
 		ghcb_set_rbx(ghcb, input->data_npages);
+	} else if (req->exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST) {
+		ghcb_set_rax(ghcb, input->data_gpa);
+		ghcb_set_rbx(ghcb, input->data_npages);
+		ghcb_set_rcx(ghcb, input->guest_rid);
+		ghcb_set_rdx(ghcb, input->param);
 	}
 
 	ret = sev_es_ghcb_hv_call(ghcb, &ctxt, req->exit_code, input->req_gpa, input->resp_gpa);
@@ -1675,6 +1717,8 @@ static int snp_issue_guest_request(struct snp_guest_req *req)
 	req->exitinfo2 = ghcb->save.sw_exit_info_2;
 	switch (req->exitinfo2) {
 	case 0:
+		if (req->exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST)
+			input->param = ghcb_get_rdx(ghcb);
 		break;
 
 	case SNP_GUEST_VMM_ERR(SNP_GUEST_VMM_ERR_BUSY):
@@ -1687,6 +1731,10 @@ static int snp_issue_guest_request(struct snp_guest_req *req)
 			input->data_npages = ghcb_get_rbx(ghcb);
 			ret = -ENOSPC;
 			break;
+		} else if (req->exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST) {
+			input->data_npages = ghcb_get_rbx(ghcb);
+			ret = -ENOSPC;
+			break;
 		}
 		fallthrough;
 	default:
@@ -2176,6 +2224,11 @@ static int __handle_guest_request(struct snp_msg_desc *mdesc, struct snp_guest_r
 	rc = snp_issue_guest_request(req);
 	switch (rc) {
 	case -ENOSPC:
+		if (req->exit_code == SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST) {
+			pr_warn("SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST => -ENOSPC");
+			break;
+		}
+
 		/*
 		 * If the extended guest request fails due to having too
 		 * small of a certificate data buffer, retry the same
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index e1ceeab54a21..41072ece79a8 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -46,6 +46,10 @@ static int vmpck_id = -1;
 module_param(vmpck_id, int, 0444);
 MODULE_PARM_DESC(vmpck_id, "The VMPCK ID to use when communicating with the PSP.");
 
+static bool tsm_enable = true;
+module_param(tsm_enable, bool, 0644);
+MODULE_PARM_DESC(tsm_enable, "Enable SEV TIO");
+
 static inline struct snp_guest_dev *to_snp_dev(struct file *file)
 {
 	struct miscdevice *dev = file->private_data;
@@ -667,6 +671,13 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	snp_dev->msg_desc = mdesc;
 	dev_info(dev, "Initialized SEV guest driver (using VMPCK%d communication key)\n",
 		 mdesc->vmpck_id);
+
+	if (!sev_tio_ghcb_supported())
+		tsm_enable = false;
+
+	if (tsm_enable)
+		sev_guest_tsm_set_ops(true, snp_dev);
+
 	return 0;
 
 e_msg_init:
@@ -680,6 +691,8 @@ static void __exit sev_guest_remove(struct platform_device *pdev)
 	struct snp_guest_dev *snp_dev = platform_get_drvdata(pdev);
 
 	snp_msg_free(snp_dev->msg_desc);
+	if (tsm_enable)
+		sev_guest_tsm_set_ops(false, snp_dev);
 	misc_deregister(&snp_dev->misc);
 }
 
diff --git a/drivers/virt/coco/sev-guest/tio.c b/drivers/virt/coco/sev-guest/tio.c
new file mode 100644
index 000000000000..6739b1f49e0e
--- /dev/null
+++ b/drivers/virt/coco/sev-guest/tio.c
@@ -0,0 +1,707 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include <linux/bitfield.h>
+#include <linux/bitops.h>
+#include <linux/pci.h>
+#include <linux/psp-sev.h>
+#include <linux/tsm.h>
+#include <linux/pci-tsm.h>
+#include <crypto/gcm.h>
+#include <uapi/linux/sev-guest.h>
+
+#include <asm/svm.h>
+#include <asm/sev.h>
+#include <asm/sev-internal.h>
+
+#include "sev-guest.h"
+
+#define TIO_MESSAGE_VERSION	1
+
+ulong tsm_vtom = 0x7fffffff;
+module_param(tsm_vtom, ulong, 0644);
+MODULE_PARM_DESC(tsm_vtom, "SEV TIO vTOM value");
+
+#define tsm_dev_to_snp_dev(t)	((struct snp_guest_dev *)dev_get_drvdata((t)->dev.parent))
+#define pdev_to_tdi(p)		container_of((p)->tsm, struct tio_guest_tdi, ds.base_tsm)
+
+struct tio_guest_tdi {
+	struct pci_tsm_devsec ds;
+	struct snp_guest_dev *snp_dev;
+	u64 tdi_id; /* Runtime FW generated TDI id */
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
+	req.req_buf = kmemdup(req_buf, req_sz, GFP_KERNEL);
+	req.req_sz = req_sz;
+	req.resp_buf = kmalloc(resp_sz, GFP_KERNEL);
+	req.resp_sz = resp_sz;
+	req.exit_code = SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST;
+
+	req.input.guest_rid = 0;
+	req.input.param = 0;
+
+	if (pt && npages) {
+		req.certs_data = pt;
+		req.input.data_npages = *npages;
+	}
+	if (bdfn)
+		req.input.guest_rid = *bdfn;
+	req.input.param = *param;
+
+	ret = snp_send_guest_request(mdesc, &req);
+
+	memcpy(resp_buf, req.resp_buf, resp_sz);
+
+	*param = req.input.param;
+
+	*fw_err = exitinfo2;
+
+	kfree(req.resp_buf);
+	kfree(req.req_buf);
+
+	return ret;
+}
+
+static void free_shared_pages(void *buf, size_t sz)
+{
+	unsigned int npages = PAGE_ALIGN(sz) >> PAGE_SHIFT;
+	int ret;
+
+	if (!buf)
+		return;
+
+	ret = set_memory_encrypted((unsigned long)buf, npages);
+	if (ret) {
+		WARN_ONCE(ret, "failed to restore encryption mask (leak it)\n");
+		return;
+	}
+
+	__free_pages(virt_to_page(buf), get_order(sz));
+}
+
+static void *alloc_shared_pages(size_t sz)
+{
+	unsigned int npages = PAGE_ALIGN(sz) >> PAGE_SHIFT;
+	struct page *page;
+	int ret;
+
+	page = alloc_pages(GFP_KERNEL_ACCOUNT, get_order(sz));
+	if (!page)
+		return NULL;
+
+	ret = set_memory_decrypted((unsigned long)page_address(page), npages);
+	if (ret) {
+		pr_err("failed to mark page shared, ret=%d\n", ret);
+		__free_pages(page, get_order(sz));
+		return NULL;
+	}
+
+	return page_address(page);
+}
+
+static int guest_request_tio_data(struct snp_guest_dev *snp_dev, u8 type,
+				  void *req_buf, size_t req_sz, void *resp_buf, u32 resp_sz,
+				  u64 bdfn, enum tsm_tdisp_state *state,
+				  struct tsm_blob **report, u64 *fw_err)
+{
+#define TIO_DATA_PAGES	(SZ_32K >> PAGE_SHIFT)
+	u64 npages = TIO_DATA_PAGES, param = 0;
+	struct tio_blob_table_entry *pt;
+	int rc;
+
+	pt = alloc_shared_pages(TIO_DATA_PAGES << PAGE_SHIFT);
+	if (!pt)
+		return -ENOMEM;
+
+	if (state)
+		param |= SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST_PARAM_STATE;
+	if (report)
+		param |= SVM_VMGEXIT_SEV_TIO_GUEST_REQUEST_PARAM_REPORT;
+
+	rc = handle_tio_guest_request(snp_dev, type, req_buf, req_sz, resp_buf, resp_sz,
+				      pt, &npages, &bdfn, &param, fw_err);
+	if (npages > TIO_DATA_PAGES) {
+		free_shared_pages(pt, TIO_DATA_PAGES << PAGE_SHIFT);
+		pt = alloc_shared_pages(npages << PAGE_SHIFT);
+		if (!pt)
+			return -ENOMEM;
+
+		rc = handle_tio_guest_request(snp_dev, type, req_buf, req_sz, resp_buf, resp_sz,
+					      pt, &npages, &bdfn, &param, fw_err);
+	}
+	if (rc)
+		return rc;
+
+	if (report) {
+		tsm_blob_free(*report);
+		*report = NULL;
+	}
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
+		if (guid_equal(&pt[i].guid, &TIO_GUID_REPORT) && report)
+			*report = b;
+	}
+	free_shared_pages(pt, npages);
+
+	if (state)
+		*state = param;
+
+	return 0;
+}
+
+struct tio_msg_tdi_info_req {
+	u16 guest_device_id;
+	u8 reserved[14];
+} __packed;
+
+enum {
+	TIO_MSG_TDI_INFO_RSP_STATUS_BOUND = 0,
+	TIO_MSG_TDI_INFO_RSP_STATUS_INVALID = 1,
+	TIO_MSG_TDI_INFO_RSP_STATUS_UNBOUND = 2,
+};
+
+struct tio_msg_tdi_info_rsp {
+	u16 guest_device_id;
+	u16 status; /* TIO_MSG_TDI_INFO_RSP_STATUS_xxx */
+	u8 reserved1[12];
+
+	u32 meas_digest_valid:1;
+	u32 meas_digest_fresh:1;
+	u32 reserved2:30;
+
+	/* These are TDISP's LOCK_INTERFACE_REQUEST flags */
+	u32 no_fw_update:1;
+	u32 cache_line_size:1;
+	u32 lock_msix:1;
+	u32 bind_p2p:1;
+	u32 all_request_redirect:1;
+	u32 reserved3:27;
+
+	u64 spdm_algos;
+	u8 certs_digest[48];
+	u8 meas_digest[48];
+	u8 interface_report_digest[48];
+	u64 tdi_report_count;
+	u64 reserved4;
+} __packed;
+
+/* Passing pci_tsm explicitly as it may not be set in pci_dev just yet */
+static int tio_tdi_status(struct pci_dev *pdev, struct snp_guest_dev *snp_dev,
+			  struct tsm_tdi_status *ts, struct tsm_blob **report)
+{
+	enum tsm_tdisp_state state = TDISP_STATE_CONFIG_UNLOCKED;
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_tdi_info_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_tdi_info_rsp *rsp __free(kfree_sensitive) = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_tdi_info_req req = {
+		.guest_device_id = pci_dev_id(pdev),
+	};
+	u64 fw_err = 0;
+	int rc;
+
+	pci_notice(pdev, "TDI info");
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = guest_request_tio_data(snp_dev, TIO_MSG_TDI_INFO_REQ, &req,
+				    sizeof(req), rsp, resp_len,
+				    req.guest_device_id, &state,
+				    report, &fw_err);
+	if (rc)
+		return rc;
+
+	ts->no_fw_update = rsp->no_fw_update;
+	ts->cache_line_size = rsp->cache_line_size == 0 ? 64 : 128;
+	ts->lock_msix = rsp->lock_msix;
+	ts->bind_p2p = rsp->bind_p2p;
+	ts->all_request_redirect = rsp->all_request_redirect;
+	memcpy(ts->interface_report_digest, rsp->interface_report_digest,
+	       sizeof(ts->interface_report_digest));
+	ts->intf_report_counter = rsp->tdi_report_count;
+
+	switch (rsp->status) {
+	case TIO_MSG_TDI_INFO_RSP_STATUS_BOUND:
+		ts->status = TDISP_STATE_BOUND;
+		break;
+	case TIO_MSG_TDI_INFO_RSP_STATUS_UNBOUND:
+		ts->status = TDISP_STATE_UNBOUND;
+		break;
+	default:
+		ts->status = TDISP_STATE_INVALID;
+		break;
+	}
+	ts->state = state;
+
+	return 0;
+}
+
+struct tio_msg_mmio_validate_req {
+	u16 guest_device_id;
+	u16 reserved1;
+	u8 reserved2[12];
+	u64 subrange_base;
+	u32 subrange_page_count;
+	u32 range_offset;
+
+	u16 validated:1; /* Desired value to set RMP.Validated for the range */
+	/*
+	 * Force validated:
+	 * 0: If subrange does not have RMP.Validated set uniformly, fail.
+	 * 1: If subrange does not have RMP.Validated set uniformly, force
+	 *    to requested value
+	 */
+	u16 force_validated:1;
+	u16 reserved3:14;
+
+	u16 range_id;
+	u8 reserved4[12];
+} __packed;
+
+struct tio_msg_mmio_validate_rsp {
+	u16 guest_interface_id;
+	u16 status; /* MMIO_VALIDATE_xxx */
+	u8 reserved1[12];
+	u64 subrange_base;
+	u32 subrange_page_count;
+	u32 range_offset;
+
+	u16 changed:1; /* Validated bit has changed due to this operation */
+	u16 reserved2:15;
+
+	u16 range_id;
+	u8 reserved3[12];
+} __packed;
+
+static int mmio_validate_range(struct snp_guest_dev *snp_dev, struct pci_dev *pdev,
+			       unsigned int range_id,
+			       resource_size_t start, resource_size_t size,
+			       bool invalidate, u64 *fw_err, u16 *status)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_mmio_validate_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_mmio_validate_rsp *rsp __free(kfree_sensitive) = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_mmio_validate_req req = {
+		.guest_device_id = pci_dev_id(pdev),
+		.subrange_base = start,
+		.subrange_page_count = size >> PAGE_SHIFT,
+		.range_offset = 0,
+		.validated = !invalidate, /* Desired value to set RMP.Validated for the range */
+		.force_validated = 0,
+		.range_id = range_id,
+	};
+	u64 bdfn = pci_dev_id(pdev);
+	u64 mmio_val = MMIO_MK_VALIDATE(start, size, range_id, !invalidate);
+	int rc;
+
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_MMIO_VALIDATE_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, &mmio_val, fw_err);
+	if (rc)
+		return rc;
+
+	*status = rsp->status;
+
+	return 0;
+}
+
+static bool get_range(struct pci_dev *pdev, struct tsm_blob *report, unsigned int index,
+		      unsigned int *range_id, resource_size_t *start, resource_size_t *size)
+{
+	struct tdi_report_mmio_range mr = TDI_REPORT_MR(report, index);
+	unsigned int rangeid = FIELD_GET(TSM_TDI_REPORT_MMIO_RANGE_ID, mr.range_attributes);
+	struct resource *r = pci_resource_n(pdev, rangeid);
+	u64 first, offset;
+	unsigned int i;
+
+	if (FIELD_GET(TSM_TDI_REPORT_MMIO_IS_NON_TEE, mr.range_attributes)) {
+		pci_info(pdev, "Skipping non-TEE range [%d] #%d %d pages, %llx..%llx\n",
+			 index, rangeid, mr.num, r->start, r->end);
+		return false;
+	}
+
+	/* Currently not supported */
+	if (FIELD_GET(TSM_TDI_REPORT_MMIO_MSIX_TABLE, mr.range_attributes) ||
+	    FIELD_GET(TSM_TDI_REPORT_MMIO_PBA, mr.range_attributes)) {
+		pci_info(pdev, "Skipping MSIX (%ld/%ld) range [%d] #%d %d pages, %llx..%llx\n",
+			 FIELD_GET(TSM_TDI_REPORT_MMIO_MSIX_TABLE, mr.range_attributes),
+			 FIELD_GET(TSM_TDI_REPORT_MMIO_PBA, mr.range_attributes),
+			 index, rangeid, mr.num, r->start, r->end);
+		return false;
+	}
+
+	/*
+	 * First the first subregion of BAR, i.e. with the smallest .first_page.
+	 * This assumes that the same MMIO_REPORTING_OFFSET is applied to all regions.
+	 * */
+	for (i = 0, first = mr.first_page; i < TDI_REPORT_MR_NUM(report); ++i) {
+		struct tdi_report_mmio_range mrtmp = TDI_REPORT_MR(report, i);
+
+		if (rangeid != FIELD_GET(TSM_TDI_REPORT_MMIO_RANGE_ID, mrtmp.range_attributes))
+			continue;
+
+		first = min(mrtmp.first_page, first);
+	}
+
+	offset = mr.first_page - first;
+	if (((offset + mr.num) << PAGE_SHIFT) > (r->end - r->start + 1)) {
+		pci_warn(pdev, "Skipping broken range [%d] BAR%d off=%llx %d pages, %llx..%llx %llx %llx\n",
+			 index, rangeid, offset, mr.num, r->start, r->end, mr.first_page, first);
+		return false;
+	}
+
+	*range_id = rangeid;
+	*start = r->start + offset;
+	*size = mr.num << PAGE_SHIFT;
+
+	return true;
+}
+
+static int tio_tdi_mmio_validate(struct pci_dev *pdev, struct snp_guest_dev *snp_dev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+	u16 mmio_status;
+	u64 fw_err = 0;
+	int i = 0, rc = 0;
+	struct pci_tsm_mmio *mmio __free(kfree) =
+		kzalloc(struct_size(mmio, res, PCI_NUM_RESOURCES), GFP_KERNEL);
+
+	if (!mmio)
+		return -ENOMEM;
+
+	if (WARN_ON_ONCE(!tsm || !tsm->report))
+		return -ENODEV;
+
+	pci_notice(pdev, "MMIO validate");
+
+	for (i = 0; i < TDI_REPORT_MR_NUM(tsm->report); ++i) {
+		unsigned int range_id;
+		resource_size_t start = 0, size = 0, end;
+
+		if (!get_range(pdev, tsm->report, i, &range_id, &start, &size))
+			continue;
+
+		end = start + size - 1;
+		mmio_status = 0;
+		rc = mmio_validate_range(snp_dev, pdev, range_id, start, size,
+					 false, &fw_err,
+					 &mmio_status);
+		if (rc || fw_err != SEV_RET_SUCCESS || mmio_status != MMIO_VALIDATE_SUCCESS) {
+			pci_err(pdev, "MMIO #%d %llx..%llx validation failed 0x%llx %d\n",
+				range_id, start, end, fw_err, mmio_status);
+			continue;
+		}
+
+		mmio->res[mmio->nr] = DEFINE_RES_NAMED_DESC(start, size, "PCI MMIO Encrypted",
+				pci_resource_flags(pdev, range_id), IORES_DESC_ENCRYPTED);
+		++mmio->nr;
+
+		pci_notice(pdev, "MMIO #%d %llx..%llx validated\n",range_id, start, end);
+	}
+
+	if (!rc) {
+		rc = pci_tsm_mmio_setup(pdev, mmio);
+		if (!rc) {
+			struct pci_tsm_devsec *devsec_tsm = to_pci_tsm_devsec(tsm);
+
+			devsec_tsm->mmio = no_free_ptr(mmio);
+		}
+	}
+
+	return rc;
+}
+
+static void tio_tdi_mmio_invalidate(struct pci_dev *pdev, struct snp_guest_dev *snp_dev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+	u16 mmio_status;
+	u64 fw_err = 0;
+	int i = 0, rc = 0;
+	struct pci_tsm_devsec *devsec_tsm = to_pci_tsm_devsec(tsm);
+	struct pci_tsm_mmio *mmio = devsec_tsm->mmio;
+
+	if (!mmio)
+		return;
+
+	pci_notice(pdev, "MMIO invalidate");
+
+	for (i = 0; i < TDI_REPORT_MR_NUM(tsm->report); ++i) {
+		unsigned int range_id;
+		resource_size_t start = 0, size = 0, end;
+
+		if (!get_range(pdev, tsm->report, i, &range_id, &start, &size))
+			continue;
+
+		end = start + size - 1;
+		mmio_status = 0;
+		rc = mmio_validate_range(snp_dev, pdev, range_id,
+					 start, size, true, &fw_err,
+					 &mmio_status);
+		if (rc || fw_err != SEV_RET_SUCCESS || mmio_status != MMIO_VALIDATE_SUCCESS) {
+			pci_err(pdev, "MMIO #%d %llx..%llx validation failed 0x%llx %d\n",
+				range_id, start, end, fw_err, mmio_status);
+			continue;
+		}
+
+		pci_notice(pdev, "MMIO #%d %llx..%llx invalidated\n",  range_id, start, end);
+	}
+
+	pci_tsm_mmio_teardown(devsec_tsm->mmio);
+	kfree(devsec_tsm->mmio);
+	devsec_tsm->mmio = NULL;
+}
+
+struct sdte {
+	u64 v                  : 1;
+	u64 reserved           : 3;
+	u64 cxlio              : 3;
+	u64 reserved1          : 45;
+	u64 ppr                : 1;
+	u64 reserved2          : 1;
+	u64 giov               : 1;
+	u64 gv                 : 1;
+	u64 glx                : 2;
+	u64 gcr3_tbl_rp0       : 3;
+	u64 ir                 : 1;
+	u64 iw                 : 1;
+	u64 reserved3          : 1;
+	u16 domain_id;
+	u16 gcr3_tbl_rp1;
+	u32 interrupt          : 1;
+	u32 reserved4          : 5;
+	u32 ex                 : 1;
+	u32 sd                 : 1;
+	u32 reserved5          : 2;
+	u32 sats               : 1;
+	u32 gcr3_tbl_rp2       : 21;
+	u64 giv                : 1;
+	u64 gint_tbl_len       : 4;
+	u64 reserved6          : 1;
+	u64 gint_tbl           : 46;
+	u64 reserved7          : 2;
+	u64 gpm                : 2;
+	u64 reserved8          : 3;
+	u64 hpt_mode           : 1;
+	u64 reserved9          : 4;
+	u32 asid               : 12;
+	u32 reserved10         : 3;
+	u32 viommu_en          : 1;
+	u32 guest_device_id    : 16;
+	u32 guest_id           : 15;
+	u32 guest_id_mbo       : 1;
+	u32 reserved11         : 1;
+	u32 vmpl               : 2;
+	u32 reserved12         : 3;
+	u32 attrv              : 1;
+	u32 reserved13         : 1;
+	u32 sa                 : 8;
+	u8 ide_stream_id[8];
+	u32 vtom_en            : 1;
+	u32 vtom               : 31;
+	u32 rp_id              : 5;
+	u32 reserved14         : 27;
+	u8  reserved15[0x40-0x30];
+} __packed;
+
+struct tio_msg_sdte_write_req {
+	u16 guest_device_id;
+	u8 reserved[14];
+	struct sdte sdte;
+} __packed;
+
+struct tio_msg_sdte_write_rsp {
+	u16 guest_device_id;
+	u16 status; /* SDTE_WRITE_xxx */
+	u8 reserved[12];
+} __packed;
+
+static int tio_tdi_sdte_write(struct pci_dev *pdev, struct snp_guest_dev *snp_dev, bool invalidate)
+{
+	struct snp_msg_desc *mdesc = snp_dev->msg_desc;
+	size_t resp_len = sizeof(struct tio_msg_sdte_write_rsp) + mdesc->ctx->authsize;
+	struct tio_msg_sdte_write_rsp *rsp __free(kfree_sensitive) = kzalloc(resp_len, GFP_KERNEL);
+	struct tio_msg_sdte_write_req req;
+	u64 fw_err = 0;
+	u64 bdfn = pci_dev_id(pdev);
+	u64 flags = invalidate ? 0 : SDTE_VALIDATE;
+	int rc;
+
+	BUILD_BUG_ON(sizeof(struct sdte) * 8 != 512);
+
+	if (!invalidate)
+		req = (struct tio_msg_sdte_write_req) {
+			.guest_device_id = bdfn,
+			.sdte.vmpl = 0,
+			.sdte.vtom = tsm_vtom,
+			.sdte.vtom_en = 1,
+			.sdte.iw = 1,
+			.sdte.ir = 1,
+			.sdte.v = 1,
+		};
+	else
+		req = (struct tio_msg_sdte_write_req) {
+			.guest_device_id = bdfn,
+		};
+
+	pci_notice(pdev, "SDTE write vTOM=%lx", (unsigned long) req.sdte.vtom << 21);
+
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = handle_tio_guest_request(snp_dev, TIO_MSG_SDTE_WRITE_REQ,
+			       &req, sizeof(req), rsp, resp_len,
+			       NULL, NULL, &bdfn, &flags, &fw_err);
+	if (rc) {
+		pci_err(pdev, "SDTE write failed with 0x%llx\n", fw_err);
+		return rc;
+	}
+
+	return 0;
+}
+
+static struct pci_tsm *sev_guest_lock(struct tsm_dev *tsmdev, struct pci_dev *pdev)
+{
+	struct tio_guest_tdi *gtdi __free(kfree) = kzalloc(sizeof(*gtdi), GFP_KERNEL);
+	struct tsm_blob *report = NULL;
+	struct tsm_tdi_status ts = {};
+	u64 fw_err = 0, tdi_id = 0;
+	int rc;
+
+	if (!gtdi)
+		return ERR_PTR(-ENOMEM);
+
+	/* Enabling device tells the HV to register MMIO as memory slots */
+	rc = pci_enable_device_mem(pdev);
+	if (rc)
+		return ERR_PTR(rc);
+
+	rc = pci_tsm_devsec_constructor(pdev, &gtdi->ds, tsmdev);
+	if (rc)
+		return ERR_PTR(rc);
+
+	pci_dbg(pdev, "TSM enabled\n");
+
+	gtdi->snp_dev = tsm_dev_to_snp_dev(tsmdev);
+
+	rc = sev_tio_op(pci_dev_id(pdev), SVM_VMGEXIT_SEV_TIO_OP_BIND, &fw_err, &tdi_id);
+	if (rc) {
+		pci_err(pdev, "TDI bind CONFIG_LOCKED failed rc=%d fw=0x%llx\n",
+			rc, fw_err);
+		return ERR_PTR(rc);
+	}
+	pci_dbg(pdev, "New TDI ID=%llx\n", tdi_id);
+
+	rc = tio_tdi_status(pdev, gtdi->snp_dev, &ts, &report);
+	if (rc)
+		return ERR_PTR(rc);
+	if (!report)
+		return ERR_PTR(-ENODEV);
+
+	gtdi->tdi_id = tdi_id;
+	gtdi->ds.base_tsm.report = report;
+
+	return &no_free_ptr(gtdi)->ds.base_tsm;
+}
+
+static void sev_guest_unlock(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+	struct tio_guest_tdi *gtdi = pdev_to_tdi(pdev);
+	struct snp_guest_dev *snp_dev = gtdi->snp_dev;
+	u64 fw_err = 0;
+	int rc;
+
+	/* Quiesce DMA */
+	sev_tio_op(pci_dev_id(pdev), SVM_VMGEXIT_SEV_TIO_OP_STOP, &fw_err, NULL);
+
+	/* Disable encrypted DMA but the HV is unable to restart it as MMIO is still blocked for HV */
+	rc = tio_tdi_sdte_write(pdev, snp_dev, true);
+	if (rc || fw_err)
+		pr_err("SDTE_WRITE did not go through, ret=%d fw=0x%llx\n", rc, fw_err);
+
+	tio_tdi_mmio_invalidate(pdev, snp_dev);
+
+	sev_tio_op(pci_dev_id(pdev), SVM_VMGEXIT_SEV_TIO_OP_UNBIND, &fw_err, NULL);
+
+	tsm->pdev->tsm = NULL;
+	kvfree(tsm);
+}
+
+static int sev_guest_accept(struct pci_dev *pdev)
+{
+	struct tio_guest_tdi *gtdi = pdev_to_tdi(pdev);
+	struct snp_guest_dev *snp_dev = gtdi->snp_dev;
+	struct pci_tsm *tsm = pdev->tsm;
+	u64 fw_err = 0;
+	int ret;
+
+	if (!tsm->report) {
+		pci_warn_once(pdev, "Cannot accept without the report");
+		return -ENODEV;
+	}
+
+	ret = sev_tio_op(pci_dev_id(pdev), SVM_VMGEXIT_SEV_TIO_OP_RUN, &fw_err, NULL);
+	if (ret)
+		return ret;
+
+	ret = tio_tdi_sdte_write(pdev, snp_dev, false);
+	if (ret)
+		return ret;
+
+	ret = tio_tdi_mmio_validate(pdev, snp_dev);
+
+	return ret;
+}
+
+struct pci_tsm_ops sev_guest_tsm_ops = {
+	.lock = sev_guest_lock,
+	.unlock = sev_guest_unlock,
+	.accept = sev_guest_accept,
+};
+
+void sev_guest_tsm_set_ops(bool set, struct snp_guest_dev *snp_dev)
+{
+	if (set) {
+		struct tsm_dev *tsmdev;
+
+		tsmdev = tsm_register(snp_dev->dev, &sev_guest_tsm_ops);
+		if (IS_ERR(tsmdev))
+			return;
+
+		snp_dev->tsmdev = tsmdev;
+		return;
+	}
+
+	if (snp_dev->tsmdev) {
+		tsm_unregister(snp_dev->tsmdev);
+		snp_dev->tsmdev = NULL;
+	}
+}

---

## [9] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 8/9] RFC: PCI: Avoid needless touching of Command register*

Once locked, a TDI's MSE and BME are not allowed to be cleared.

Skip INTx test as TEE-capable PCI functions are most likely IOV VFs
anyway and those do not support INTx at all.

Add a quirk preventing the probing code from disabling MSE when
updating 64bit BAR (which cannot be done atomically).

Note that normally this happens too early and likely not really
needed for the device attestation happening long after PCI probing.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

This is also handled in QEMU - it will block clearing BME and MSE
(normally happening on modprobe/rmmod) as long as the TDI is
CONFIG_LOCKED or RUN.

This only patch is not enough but reduces the number of unwanted
writes to MSE/BME.

Also, SRIOV cannot have INTx so pci_intx_mask_broken() could skip
VFs too, should it?
---
 drivers/pci/probe.c  | 5 +++++
 drivers/pci/quirks.c | 9 +++++++++
 2 files changed, 14 insertions(+)

diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 4c3aec1fd53e..cc0613e7c905 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -1930,6 +1930,11 @@ static int pci_intx_mask_broken(struct pci_dev *dev)
 {
 	u16 orig, toggle, new;
 
+	if (dev->devcap & PCI_EXP_DEVCAP_TEE) {
+		pci_warn_once(dev, "(TIO) Disable check for broken INTX");
+		return 1;
+	}
+
 	pci_read_config_word(dev, PCI_COMMAND, &orig);
 	toggle = orig ^ PCI_COMMAND_INTX_DISABLE;
 	pci_write_config_word(dev, PCI_COMMAND, toggle);
diff --git a/drivers/pci/quirks.c b/drivers/pci/quirks.c
index 214ed060ca1b..b875859699ba 100644
--- a/drivers/pci/quirks.c
+++ b/drivers/pci/quirks.c
@@ -316,6 +316,15 @@ static void quirk_mmio_always_on(struct pci_dev *dev)
 DECLARE_PCI_FIXUP_CLASS_EARLY(PCI_ANY_ID, PCI_ANY_ID,
 				PCI_CLASS_BRIDGE_HOST, 8, quirk_mmio_always_on);
 
+static void quirk_mmio_tio_always_on(struct pci_dev *dev)
+{
+	if (dev->devcap & PCI_EXP_DEVCAP_TEE) {
+		pci_info(dev, "(TIO) quirk: MMIO always On");
+		dev->mmio_always_on = 1;
+	}
+}
+DECLARE_PCI_FIXUP_EARLY(PCI_ANY_ID, PCI_ANY_ID, quirk_mmio_tio_always_on);
+
 /*
  * The Mellanox Tavor device gives false positive parity errors.  Disable
  * parity error reporting.

---

## [10] Alexey Kardashevskiy — 2026-02-25
*Subject: [PATCH kernel 9/9] pci: Allow encrypted MMIO mapping via sysfs*

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
index 1a31353dc109..6e258b793278 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -2217,7 +2217,7 @@ pci_alloc_irq_vectors(struct pci_dev *dev, unsigned int min_vecs,
  */
 int pci_mmap_resource_range(struct pci_dev *dev, int bar,
 			    struct vm_area_struct *vma,
-			    enum pci_mmap_state mmap_state, int write_combine);
+			    enum pci_mmap_state mmap_state, int write_combine, int enc);
 
 #ifndef arch_can_pci_mmap_wc
 #define arch_can_pci_mmap_wc()		0
diff --git a/drivers/pci/mmap.c b/drivers/pci/mmap.c
index 8da3347a95c4..90a8ab4753b8 100644
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
+				       pgprot_encrypted(vma->vm_page_prot));
+
 	return io_remap_pfn_range(vma, vma->vm_start, vma->vm_pgoff,
 				  vma->vm_end - vma->vm_start,
 				  vma->vm_page_prot);
diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
index 7f9237a926c2..715407eb8b15 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1104,7 +1104,7 @@ void pci_remove_legacy_files(struct pci_bus *b)
  * Use the regular PCI mapping routines to map a PCI resource into userspace.
  */
 static int pci_mmap_resource(struct kobject *kobj, const struct bin_attribute *attr,
-			     struct vm_area_struct *vma, int write_combine)
+			     struct vm_area_struct *vma, int write_combine, int enc)
 {
 	struct pci_dev *pdev = to_pci_dev(kobj_to_dev(kobj));
 	int bar = (unsigned long)attr->private;
@@ -1124,21 +1124,28 @@ static int pci_mmap_resource(struct kobject *kobj, const struct bin_attribute *a
 
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
@@ -1232,7 +1239,7 @@ static void pci_remove_resource_files(struct pci_dev *pdev)
 	}
 }
 
-static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine)
+static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine, int enc)
 {
 	/* allocate attribute structure, piggyback attribute name */
 	int name_len = write_combine ? 13 : 10;
@@ -1250,6 +1257,9 @@ static int pci_create_attr(struct pci_dev *pdev, int num, int write_combine)
 	if (write_combine) {
 		sprintf(res_attr_name, "resource%d_wc", num);
 		res_attr->mmap = pci_mmap_resource_wc;
+	} else if (enc) {
+		sprintf(res_attr_name, "resource%d_enc", num);
+		res_attr->mmap = pci_mmap_resource_enc;
 	} else {
 		sprintf(res_attr_name, "resource%d", num);
 		if (pci_resource_flags(pdev, num) & IORESOURCE_IO) {
@@ -1310,11 +1320,14 @@ static int pci_create_resource_files(struct pci_dev *pdev)
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
index 9348a0fb8084..e0c0ece7f3f5 100644
--- a/drivers/pci/proc.c
+++ b/drivers/pci/proc.c
@@ -288,7 +288,7 @@ static int proc_bus_pci_mmap(struct file *file, struct vm_area_struct *vma)
 	/* Adjust vm_pgoff to be the offset within the resource */
 	vma->vm_pgoff -= start >> PAGE_SHIFT;
 	ret = pci_mmap_resource_range(dev, i, vma,
-				  fpriv->mmap_state, write_combine);
+				  fpriv->mmap_state, write_combine, 0);
 	if (ret < 0)
 		return ret;

---

## [11] Borislav Petkov — 2026-02-25
*Subject: Re: [PATCH kernel 7/9] coco/sev-guest: Implement the guest support for SEV TIO (phase2)*

On February 25, 2026 5:37:50 AM UTC, Alexey Kardashevskiy <aik@amd.com> wrote:
>Implement the SEV-TIO (Trusted I/O) support in for AMD SEV-SNP guests.
>

Just from staring at that huuuge diff, those bullets and things above are basically begging to be separate patches...

---

## [12] dan.j.williams@intel.com — 2026-02-24
*Subject: Re: [PATCH kernel 1/9] pci/tsm: Add TDISP report blob and helpers to
 parse it*

Alexey Kardashevskiy wrote:
> The TDI interface report is defined in PCIe r7.0,
> chapter "11.3.11 DEVICE_INTERFACE_REPORT". The report enumerates
[..]
> +struct tdi_report_header {
> +	__u16 interface_info; /* TSM_TDI_REPORT_xxx */

Those should be __le64 and le32, right? But see below for another
option...

> +} __packed;
> +

So we all have a version of a patch like this and the general style
suggestion I have is to just parse this layout with typical
offsets+bitfield definitions.

This follows the precedent, admittedly tiny, of the DOE definitions in
pci_regs.h. See:

	/* DOE Data Object - note not actually registers */

I have a patch that parses the TDISP report with these defines:

/*
 * PCIe ECN TEE Device Interface Security Protocol (TDISP)
 *
 * Device Interface Report data object layout as defined by PCIe r7.0 section
 * 11.3.11
 */
#define PCI_TSM_DEVIF_REPORT_INFO 0
#define PCI_TSM_DEVIF_REPORT_MSIX 4
#define PCI_TSM_DEVIF_REPORT_LNR 6
#define PCI_TSM_DEVIF_REPORT_TPH 8
#define PCI_TSM_DEVIF_REPORT_MMIO_COUNT 12
#define  PCI_TSM_DEVIF_REPORT_MMIO_PFN 0 /* An interface report 'pfn' is 4K in size */
#define  PCI_TSM_DEVIF_REPORT_MMIO_NR_PFNS 8
#define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR 12
#define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_TABLE BIT(0)
#define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_PBA BIT(1)
#define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_IS_NON_TEE BIT(2)
#define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_IS_UPDATABLE BIT(3)
#define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_RANGE_ID GENMASK(31, 16)
#define  PCI_TSM_DEVIF_REPORT_MMIO_SIZE (16)
#define PCI_TSM_DEVIF_REPORT_BASE_SIZE(nr_mmio) (16 + nr_mmio * PCI_TSM_DEVIF_REPORT_MMIO_SIZE)

Any strong feelings one way or the other? I have a mild preference for
this offset+bitfields approach.

---

## [13] dan.j.williams@intel.com — 2026-02-24
*Subject: Re: [PATCH kernel 2/9] pci/tsm: Add tsm_tdi_status*

Alexey Kardashevskiy wrote:
> Define a structure with all info about a TDI such as TDISP status,
> bind state, used START_INTERFACE options and the report digest.

Say more about what this uapi when sysfs already has lock+accept
indications?

Or are you just talking about exporting the TDISP report as a binary
blob?

I think the kernel probably wants a generic abstraction for asserting
that the tsm layer believes the report remains valid between fetch and
run. In other words I am not sure arch features like intf_report_counter
ever show up anywhere in uapi outside of debugfs.

---

## [14] Arnd Bergmann — 2026-02-25
*Subject: Re: [PATCH kernel 1/9] pci/tsm: Add TDISP report blob and helpers to parse it*

On Wed, Feb 25, 2026, at 07:16, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..]

If these come from DMA transfers from a device, yes.

>> +} __packed;

The structure appears to be allocated with kzalloc, so it is always
aligned to __alignof__(u64) or higher, and it's better to drop the
__packed annotation.

>
> /*

I assume by bitfield you mean the macros above, not the C structure
syntax with ':', right? The macros seem fine to me, while C bitfields
again would make the code nonportable due to architecture specific
bitfield positioning.

       Arnd

---

## [15] dan.j.williams@intel.com — 2026-02-25
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

Alexey Kardashevskiy wrote:
> SWIOTLB is enforced when encrypted guest memory is detected
> in pci_swiotlb_detect() which is required for legacy devices.

I worry this further muddies the meaning of the swiotlb force option.
What if you want to force swiotlb operation on accepted devices?

For example:

@@ -173,7 +176,13 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
        struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
-       return mem && mem->force_bounce;
+       if (!mem)
+               return false;
+       if (mem->force_bounce)
+               return true;
+       if (mem->bounce_unaccepted && !device_cc_accepted(dev))
+               return true;
+       return false;
 }
 
 void swiotlb_init(bool addressing_limited, unsigned int flags);

---

## [16] Robin Murphy — 2026-02-25
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 2026-02-25 5:37 am, Alexey Kardashevskiy wrote:
> SWIOTLB is enforced when encrypted guest memory is detected
> in pci_swiotlb_detect() which is required for legacy devices.

This seems backwards - how does it make sense for arch code to force 
SWIOTLB globally on the grounds that all DMA must be to shared memory, 
but then generic code override that because it claims to know better?

I'd expect to see something more like:

	if (is_cc_platform && !device_cc_accepted)
		return true;

here, and then get rid of the rest of the (ab)use of SWIOTLB_FORCE for 
this purpose entirely.

However there is the fiddly aspect that it's not necessarily strictly 
enough to just un-force SWIOTLB; we really want to actively ensure that 
no private memory can *ever* end up getting bounced through a shared 
SWIOTLB buffer. The private/shared state is really a property of the 
individual DMA mappings, though, rather than an overall property of the 
device itself (since a device that's trusted to access private memory 
isn't necessarily prohibited from still also accessing shared memory as 
well), hmmm...

Thanks,
Robin.

> +
>   	return mem && mem->force_bounce;

---

## [17] dan.j.williams@intel.com — 2026-02-25
*Subject: Re: [PATCH kernel 5/9] x86/mm: Stop forcing decrypted page state for
 TDISP devices*

Alexey Kardashevskiy wrote:
> The DMA subsystem does is forcing private-to-shared
> page conversion in force_dma_unencrypted().

Looks ok, but I would not reference "TDISP" here. TDISP is the PCI
"accept" protocol. Other buses might accept devices via other
bus-specific protocols.

---

## [18] Robin Murphy — 2026-02-25
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On 2026-02-25 5:37 am, Alexey Kardashevskiy wrote:
> TDISP devices operate in CoCo VMs only and capable of accessing
> encrypted guest memory.

That smells a bit off... In CCA we should be in the same boat, wherein a 
trusted device can access memory at a DMA address based on its "normal" 
(private) GPA, rather than having to be redirected to the shared alias 
(it's really not an "SME mask" in that sense at all).

I guess this comes back to the point I just raised on the previous patch 
- the current assumption is that devices cannot access private memory at 
all, and thus phys_to_dma() is implicitly only dealing with the 
mechanics of how the given device accesses shared memory. Once that no 
longer holds, I don't see how we can find the right answer without also 
consulting the relevant state of paddr itself, and that really *should* 
be able to be commonly abstracted across CoCo environments. And if in 
the process of that we could untangle the "implicit vs. explicit SME 
mask for shared memory or non-CoCo SME" case from common code and punt 
*that* into an x86-specific special case, all the better :)

Thanks,
Robin.

> pci_device_add() enforces the FFFF_FFFF coherent DMA mask so
> dma_alloc_coherent() fails when SME=on, this is how I ended up fixing

---

## [19] Robin Murphy — 2026-02-25
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 2026-02-25 4:30 pm, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>> SWIOTLB is enforced when encrypted guest memory is detected

For that we'd need a whole other private SWIOTLB plus the logic to 
decide which one to use in the first place. And if you really wanted an 
option to forcibly expose all DMA through shared memory regardless of 
TDISP and friends, that would logically want to be a higher-level CoCo 
option rather than belonging to SWIOTLB itself ;)

Thanks,
Robin.

> For example:
>

---

## [20] dan.j.williams@intel.com — 2026-02-25
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

Robin Murphy wrote:
> On 2026-02-25 4:30 pm, dan.j.williams@intel.com wrote:
> > Alexey Kardashevskiy wrote:

In this case I was still considering that swiotlb is still implicitly
only shared address bouncining. Indeed, a whole other "private_swiotlb"
mechanism would be needed for private bouncing. Not clear there is a
need for that at present.

Even for this swiotlb=force for "accepted" devices I only see a
potential kernel development use case, not a deployment use case.

> option to forcibly expose all DMA through shared memory regardless of 
> TDISP and friends, that would logically want to be a higher-level CoCo 

As I have it below, yes, CoCo opts into this bounce_unaccepted mechanism.

As to your other question:

> (since a device that's trusted to access private memory
> isn't necessarily prohibited from still also accessing shared memory as

The specification allows it, but Linux DMA mapping core is not yet ready
for it. So the expectation to start is that the device loses access to
its original shared IOMMU mappings when converted to private operation.

So on ARM where shared addresses are high, it is future work to figure
out how an accepted device might also access shared mappings outside the
device's dma_mask.

> > For example:
> >

---

## [21] dan.j.williams@intel.com — 2026-02-25
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

Robin Murphy wrote:
> On 2026-02-25 5:37 am, Alexey Kardashevskiy wrote:
> > TDISP devices operate in CoCo VMs only and capable of accessing

Not quite, no, CCA *is* in the same boat as TDX, not SEV-SNP. Only
SEV-SNP has this concept that the DMA handle for private memory is the
dma_addr_unencrypted() conversion (C-bit masked) of the CPU physical
address. For CCA and TDX the typical expectation of dma_addr_encrypted()
for accepted devices holds. It just so happens that dma_addr_encrypted()
does not munge the address on  is a nop conversion for CCA and TDX.

---

## [22] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [PATCH kernel 2/9] pci/tsm: Add tsm_tdi_status*

On 25/2/26 17:33, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>> Define a structure with all info about a TDI such as TDISP status,

I mean that between lock and accept the guest userspace wants to read certs/measurements/report to do the attestation. And it will want to know these blobs digests. And probably the TDI state. Although successful write to lock() is an indication of CONFIG_LOCKED, and accept == RUN.

We do not do real attestation in phase2 but the report is required anyway to enable private MMIO so I started shuffling with this structure.

> I think the kernel probably wants a generic abstraction for asserting
> that the tsm layer believes the report remains valid between fetch and

True, this is a shorter (not shorter enough :) ) version of SEV-TIO's TDI_INFO. Thanks,

---

## [23] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [PATCH kernel 1/9] pci/tsm: Add TDISP report blob and helpers to
 parse it*

On 25/2/26 17:16, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>> The TDI interface report is defined in PCIe r7.0,

Oh yes.

> But see below for another
> option...


I cannot easily see from these what the sizes are. And how many of each.

> #define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_TABLE BIT(0)
> #define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_PBA BIT(1)


My variant is just like this (may be need to put it in the comment):

tdi_report_header
tdi_report_mmio_range[]
tdi_report_footer

imho easier on eyes. I can live with either if the majority votes for it. Thanks.

---

## [24] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 26/2/26 03:48, Robin Murphy wrote:
> On 2026-02-25 5:37 am, Alexey Kardashevskiy wrote:
>> SWIOTLB is enforced when encrypted guest memory is detected

True. I have the itch to remove SWIOTLB_FORCE from pci_swiotlb_detect(), this may be the other way to go.

> I'd expect to see something more like:
> 

device_cc_accepted() implies is_cc_platform.

>          return true;
> 
At the moment it is a property of the device though, for AMD, at least.

> (since a device that's trusted to access private memory isn't necessarily prohibited from still also accessing shared memory as well), hmmm...

True. With vTOM ("everything above TopOfMemory is shared", not using it now) or secure vIOMMU all sorts of accesses is possible. Thanks,

> 
> Thanks,

---

## [25] Bjorn Helgaas — 2026-02-25
*Subject: Re: [PATCH kernel 8/9] RFC: PCI: Avoid needless touching of Command
 register*

On Wed, Feb 25, 2026 at 04:37:51PM +1100, Alexey Kardashevskiy wrote:
> Once locked, a TDI's MSE and BME are not allowed to be cleared.

Disallowed by hardware, by spec, by convention?  Spec reference would
be helpful.

> Skip INTx test as TEE-capable PCI functions are most likely IOV VFs
> anyway and those do not support INTx at all.

"Most likely" doesn't sound like a convincing argument for skipping
something.

> Add a quirk preventing the probing code from disabling MSE when
> updating 64bit BAR (which cannot be done atomically).

Say more about this please.  If there's something special about this
device, I'd like to know exactly what that is.

> Note that normally this happens too early and likely not really
> needed for the device attestation happening long after PCI probing.

I don't follow this either.  Please make it meaningful for
non-TEE/TDI/whatever experts.  And mention that context in the subject
line.

> @@ -1930,6 +1930,11 @@ static int pci_intx_mask_broken(struct pci_dev *dev)
>  {

s/INTX/INTx/

Why do users need to know this?  Why as a warning?  What can they do
about it?  "TIO"?

---

## [26] dan.j.williams@intel.com — 2026-02-25
*Subject: Re: [PATCH kernel 8/9] RFC: PCI: Avoid needless touching of Command
 register*

Alexey Kardashevskiy wrote:
> Once locked, a TDI's MSE and BME are not allowed to be cleared.
> 

Locked command register management is handled by QEMU. This patch needs
quite a bit more explanation about what use case it is trying to solve.

---

## [27] dan.j.williams@intel.com — 2026-02-25
*Subject: Re: [PATCH kernel 1/9] pci/tsm: Add TDISP report blob and helpers to
 parse it*

Alexey Kardashevskiy wrote:
[..]
> I cannot easily see from these what the sizes are. And how many of each.

Same as any other offset+bitmask code, the size is encoded in the accessor.

Arnd caught that I misspoke when I said offset+bitfield.

> > #define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_TABLE BIT(0)
> > #define  PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_PBA BIT(1)

Does the kernel have any use for the footer besides conveying it to
userspace?

> imho easier on eyes. I can live with either if the majority votes for it. Thanks.

Aneesh also already has 'structs+bitmask', I will switch to that.

---

## [28] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [PATCH kernel 7/9] coco/sev-guest: Implement the guest support
 for SEV TIO (phase2)*

On 25/2/26 17:00, Borislav Petkov wrote:
> On February 25, 2026 5:37:50 AM UTC, Alexey Kardashevskiy <aik@amd.com> wrote:
>> Implement the SEV-TIO (Trusted I/O) support in for AMD SEV-SNP guests.

I struggle to separate these more without making individual patches useless for any purpose, even splitting between maintainership area. People often define things in separate patches and then use them and I dislike such approach for reviewing purposes - hard to follow. I can ditch more stuff (like TIO_GUID_CERTIFICATES - just noticed) but it is not much :-/

---

## [29] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [PATCH kernel 1/9] pci/tsm: Add TDISP report blob and helpers to
 parse it*

On 26/2/26 13:34, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..]

PCIe says:

Example of such device specific information include:
• A network device may include receive-side scaling (RSS) related information such as the RSS hash and
mappings to the virtual station interface (VSI) queues, etc.
• A NVMe device may include information about the associated name spaces, mapping of name space to
command queue-pair mappings, etc.
• Accelerators may report capabilities such as algorithms supported, queue depths, etc


Sounds to me like something the device driver would be interested in.

> 
>> imho easier on eyes. I can live with either if the majority votes for it. Thanks.

oh I just found it, more or less my version :) I can add pci_tdisp_ prefixes, should I? Thanks,

---

## [30] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [PATCH kernel 8/9] RFC: PCI: Avoid needless touching of Command
 register*

On 26/2/26 11:24, Bjorn Helgaas wrote:
> On Wed, Feb 25, 2026 at 04:37:51PM +1100, Alexey Kardashevskiy wrote:
>> Once locked, a TDI's MSE and BME are not allowed to be cleared.

By the PCIe spec, the TDISP part. Once the device in CONFIG_LOCKED or RUN, clearing MSE or BME will destroy this state == will go to the ERROR state. PCIe r7, "Figure 11-5 TDISP State Machine".

Then, if it was CONFIG_LOCKED - the device won't be able to go to the RUN state which allows DMA to/from encrypted memory and encrypted MMIO. If it was RUN - the device will lose those encrypted DMA/MMIO abilities.

>> Skip INTx test as TEE-capable PCI functions are most likely IOV VFs
>> anyway and those do not support INTx at all.

Well, frankly, I have this patch for ages and originally QEMU did not intercept zeroing of BME/MSE and just by having this patch, I could get my prototype working without that QEMU hack.

Then, even though the QEMU hack works, it is kind of muddy as when a device driver wants to clear BME to, say, stop DMA - and in reality it won't stop. So I suspect the QEMU hack won't always be enough and we will have to teach the PCI subsystem to not clear BME/MSE in some cases.

Hence the patch, to highlight rather unexpected writes to the PCI command register which are not that harmless anymore.

I'll drop it if it is no use to anyone even with the above.

>> @@ -1930,6 +1930,11 @@ static int pci_intx_mask_broken(struct pci_dev *dev)
>>   {

ah, sorry, a leftover. Thanks,

---

## [31] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On 26/2/26 08:35, dan.j.williams@intel.com wrote:
> Robin Murphy wrote:
>> On 2026-02-25 5:37 am, Alexey Kardashevskiy wrote:

OTOH TDX and SNP do not leak SME mask to DMA handles, and ARM does.

Sounds like what, we need sme_dma_me_mask in addition to sme_me_mask? Scary.

---

## [32] Borislav Petkov — 2026-02-26
*Subject: Re: [PATCH kernel 7/9] coco/sev-guest: Implement the guest support for SEV TIO (phase2)*

On February 26, 2026 3:39:37 AM UTC, Alexey Kardashevskiy <aik@amd.com> wrote:
>I struggle to separate these more without making individual patches useless for any purpose

You sound like someone who hasn't been reviewing patches and scratching his head how to approach such a conglomerate as yours which does many things at once...

The rule is very simple actually: a patch should do one logical thing only. And no more. It doesn't matter whether the patch is "useless" by itself. It matters only whether it is reviewable and one can to a certain degree see that the transformation it contains is relatively bugfree.

And I'm very sure that when you start reviewing patches, you'll be pretty much asking people sending conglomerates like yours, to split them.

Thx.

---

## [33] dan.j.williams@intel.com — 2026-02-26
*Subject: Re: [PATCH kernel 1/9] pci/tsm: Add TDISP report blob and helpers to
 parse it*

Alexey Kardashevskiy wrote:
[..]
> > Does the kernel have any use for the footer besides conveying it to
> > userspace?

That is not the concern. The concern is how does Linux maintain a
convention around these use case so that common semantics converge on a
common implementation expectations.

> >> imho easier on eyes. I can live with either if the majority votes for it. Thanks.
> > 

I have a patch brewing that moves interface report consumption into
encrypted resource population for ioremap() to consider. I will send
that out shortly.

---

## [34] Jason Gunthorpe — 2026-02-27
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On Wed, Feb 25, 2026 at 05:08:37PM +0000, Robin Murphy wrote:

> I guess this comes back to the point I just raised on the previous patch -
> the current assumption is that devices cannot access private memory at all,

Definately, I think building on this is a good place to start

https://lore.kernel.org/all/20260223095136.225277-2-jiri@resnulli.us/

Probably this series needs to take DMA_ATTR_CC_DECRYPTED and push it
down into the phys_to_dma() and make the swiotlb shared allocation
code force set it.

But what value is stored in the phys_addr_t for shared pages on the
three arches? Does ARM and Intel set the high GPA/IPA bit in the
phys_addr or do they set it through the pgprot? What does AMD do?

ie can we test a bit in the phys_addr_t to reliably determine if it is
shared or private?

> > pci_device_add() enforces the FFFF_FFFF coherent DMA mask so
> > dma_alloc_coherent() fails when SME=on, this is how I ended up fixing

Does AMD have the shared/private GPA split like ARM and Intel do? Ie
shared is always at a high GPA? What is the SME mask?

Jason

---

## [35] Jason Gunthorpe — 2026-02-27
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On Wed, Feb 25, 2026 at 12:57:01PM -0800, dan.j.williams@intel.com wrote:
> > (since a device that's trusted to access private memory
> > isn't necessarily prohibited from still also accessing shared memory as

Yes, the underlying translation changes, but no, it doesn't loose DMA
access to any shared pages, it just goes through the T=1 IOMMU now.

The T=1 IOMMU will still have them mapped on all three platforms
AFAIK. On TDX/CCA the CPU and IOMMU S2 tables are identical, so of
course the shared pages are mapped. On AMD there is only one IOMMU so
the page must also be mapped or non-TDISP is broken.

When this TDISP awareness is put in the DMA API it needs to be done in
a way that allows DMA_ATTR_CC_DECRYPTED to keep working for TDISP
devices.

This is important because we are expecting these sorts of things to
work as part of integrating non-TDISP RDMA devices into CC guests. We
can't loose access to the shared pages that are shared with the
non-TDISP devices...

> So on ARM where shared addresses are high, it is future work to figure
> out how an accepted device might also access shared mappings outside the

ARM has a "solution" right now. The location of the high bit is
controlled by the VMM and the VMM cannot create a CC VM where the IPA
space exceeds the dma_mask of any assigned device.

Thus the VMM must limit the total available DRAM to fit within the HW
restrictions.

Hopefully TDX can do the same.

Jason

---

## [36] Alexey Kardashevskiy — 2026-03-02
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On 28/2/26 11:06, Jason Gunthorpe wrote:
> On Wed, Feb 25, 2026 at 05:08:37PM +0000, Robin Murphy wrote:
> 

cool, thanks for the pointer.

> Probably this series needs to take DMA_ATTR_CC_DECRYPTED and push it
> down into the phys_to_dma() and make the swiotlb shared allocation

Without secure vIOMMU, no Cbit in the S2 table (==host) for any VM. SDTE (==IOMMU) decides on shared/private for the device, i.e. (device_cc_accepted()?private:shared).

With secure vIOMMU, PTEs in VM will or won't have the SME mask.

>>> pci_device_add() enforces the FFFF_FFFF coherent DMA mask so
>>> dma_alloc_coherent() fails when SME=on, this is how I ended up fixing

sorry but I do not follow this entirely.

In general, GPA != DMA handle. Cbit (bit51) is not an address bit in a GPA but it is a DMA handle so I mask it there.

With one exception - 1) host 2) mem_encrypt=on 3) iommu=pt, but we default to IOMMU in the case of host+mem_encrypt=on and don't have Cbit in host's DMA handles.

For CoCoVM, I could map everything again at the 1<<51 offset in the same S2 table to leak Cbit to the bus (useless though).

There is vTOM in SDTE which is "every phys_addr_t above vTOM is no Cbit, below - with Cbit" (and there is the same thing for the CPU side in SEV) but this not it, right?

AMD's SME mask for shared is 0, for private - 1<<51.

Thanks,

---

## [37] Jason Gunthorpe — 2026-03-01
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On Mon, Mar 02, 2026 at 11:01:24AM +1100, Alexey Kardashevskiy wrote:
> 
> 

Is this "Cbit" part of the CPU S2 page table address space or is it
actually some PTE bit that says it is "encrypted" ?

It is confusing when you say it would start working with a vIOMMU.

If 1<<51 is a valid IOPTE, and it is an actually address, then it
should be mapped into the IOMMU S2, shouldn't it? If it is in the
IOMMU S2 then shouldn't it work as a dma_addr_t?

If the HW is treating 1<<51 special in some way and not reflecting it
into a S2 lookup then it isn't an address bit but an IOPTE flag.
IMHO is really dangerous to intermix PTE flags into phys_addr_t, I
hope that is not what is happening.

> > Does AMD have the shared/private GPA split like ARM and Intel do? Ie
> > shared is always at a high GPA? What is the SME mask?

Double map is what ARM does at least. I don't know it is a good
choice, but it means that phys_addr_t can have a shared/private bit
(eg your Cbit at 51) and both the CPU and IOMMU S2 have legitimate
mappings. ie it is a *true* address bit.

Given AMD has only a single IOMMO for T=0 and 1 it would make sense to
me if AMD always remove the C bit and there is always a uniform IOVA
mapping from 0 -> vTOM.

But in this case I would expect the vIOMMU to also use the same GPA
space starting from 0 and also remove the C bit, as the S2 shouldn't
have mappings starting at 1<<51.

> There is vTOM in SDTE which is "every phys_addr_t above vTOM is no
> Cbit, below - with Cbit" (and there is the same thing for the CPU

That seems like the IOMMU HW is specially handling the address bits in
some way? At least ARM doesn't have anything like that, address bits
are address bits, they don't get overloaded with secondary mechanisms.

> AMD's SME mask for shared is 0, for private - 1<<51.

ARM is the inverse of this (private is at 0), but the same idea.

Jason

---

## [38] Alexey Kardashevskiy — 2026-03-02
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On 2/3/26 11:35, Jason Gunthorpe wrote:
> On Mon, Mar 02, 2026 at 11:01:24AM +1100, Alexey Kardashevskiy wrote:
>>

When I mention vIOMMU, I mean the S1 table which is guest owned and which has Cbit in PTEs.

> If 1<<51 is a valid IOPTE, and it is an actually address, then it
> should be mapped into the IOMMU S2, shouldn't it? If it is in the

It should (and checked with the HW folks), I just have not tried it  as, like, whyyy.

> If the HW is treating 1<<51 special in some way and not reflecting it
> into a S2 lookup then it isn't an address bit but an IOPTE flag.
Sounds like what you hope for is how it works now.

>>> Does AMD have the shared/private GPA split like ARM and Intel do? Ie
>>> shared is always at a high GPA? What is the SME mask?

How would then IOMMU know if DMA targets private or shared memory? The Cbit does not participate in the S2 translation as an address bit but IOMMU still knows what it is.

>> There is vTOM in SDTE which is "every phys_addr_t above vTOM is no
>> Cbit, below - with Cbit" (and there is the same thing for the CPU

Yeah there is this capability. Except everything below vTOM is private and every above is shared so SME mask for it would be reverse than the CPU SME mask :) Not using this thing though (not sure why we have it). Thanks,

> At least ARM doesn't have anything like that, address bits
> are address bits, they don't get overloaded with secondary mechanisms.

---

## [39] Aneesh Kumar K.V — 2026-03-02
*Subject: Re: [PATCH kernel 2/9] pci/tsm: Add tsm_tdi_status*

<dan.j.williams@intel.com> writes:

> Alexey Kardashevskiy wrote:
>> Define a structure with all info about a TDI such as TDISP status,

Agreed. For CCA, we use rsi_vdev_info, but we need a generic mechanism
to associate this with the report that the guest has attested.

In CCA, we call rsi_vdev_get_info(vdev_id, dev_info) and later use that
information in rsi_vdev_enable_dma(vdev_id, dev_info).

Perhaps we could add a generation number (or meas_nonce) to the TSM
netlink response and use it when accepting the device, so we can
reliably bind the device measurement to the attested one?

-aneesh

---

## [40] Aneesh Kumar K.V — 2026-03-02
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

Alexey Kardashevskiy <aik@amd.com> writes:

> SWIOTLB is enforced when encrypted guest memory is detected
> in pci_swiotlb_detect() which is required for legacy devices.


I’m wondering whether we need more than that. Perhaps we could start
with a simpler assumption: a TDISP-capable device will never require
SWIOTLB bouncing. That would significantly simplify the DMA allocation
path for T=1.

Without this assumption, we might need to implement a private
io_tlb_mem.

We should also avoid supporting TDISP mode on devices that require
things like restricted-memory SWIOTLB pool.

Something like:

modified   arch/arm64/mm/mem_encrypt.c
@@ -18,6 +18,7 @@
 #include <linux/err.h>
 #include <linux/mm.h>
 #include <linux/mem_encrypt.h>
+#include <linux/device.h>
 
 static const struct arm64_mem_crypt_ops *crypt_ops;
 
@@ -53,3 +54,12 @@ int set_memory_decrypted(unsigned long addr, int numpages)
 	return crypt_ops->decrypt(addr, numpages);
 }
 EXPORT_SYMBOL_GPL(set_memory_decrypted);
+
+bool force_dma_unencrypted(struct device *dev)
+{
+	if (device_cc_accepted(dev))
+		return false;
+
+	return is_realm_world();
+}
+EXPORT_SYMBOL_GPL(force_dma_unencrypted);
modified   include/linux/swiotlb.h
@@ -173,6 +173,11 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+	if (device_cc_accepted(dev)) {
+		dev_warn_once(dev, "(TIO) Disable SWIOTLB");
+		return false;
+	}
+
 	return mem && mem->force_bounce;
 }
 
@@ -287,6 +292,9 @@ bool swiotlb_free(struct device *dev, struct page *page, size_t size);
 
 static inline bool is_swiotlb_for_alloc(struct device *dev)
 {
+	if (device_cc_accepted(dev))
+		return false;
+
 	return dev->dma_io_tlb_mem->for_alloc;
 }
 #else
modified   kernel/dma/direct.c
@@ -159,6 +159,14 @@ static struct page *__dma_direct_alloc_pages(struct device *dev, size_t size,
  */
 static bool dma_direct_use_pool(struct device *dev, gfp_t gfp)
 {
+	/*
+	 * Atomic pools are marked decrypted and are used if we require require
+	 * updation of pfn mem encryption attributes or for DMA non-coherent
+	 * device allocation. Both is not true for trusted device.
+	 */
+	if (device_cc_accepted(dev))
+		return false;
+
 	return !gfpflags_allow_blocking(gfp) && !is_swiotlb_for_alloc(dev);
 }
 
modified   kernel/dma/swiotlb.c
@@ -1643,6 +1643,9 @@ bool is_swiotlb_active(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
+	if (device_cc_accepted(dev))
+		return false;
+
 	return mem && mem->nslabs;
 }

---

## [41] Aneesh Kumar K.V — 2026-03-02
*Subject: Re: [PATCH kernel 9/9] pci: Allow encrypted MMIO mapping via sysfs*

Alexey Kardashevskiy <aik@amd.com> writes:

> Add another resource#d_enc to allow mapping MMIO as
> an encrypted/private region.

Why is this needed? Is this for a specific tool?

-aneesh

---

## [42] Alexey Kardashevskiy — 2026-03-02
*Subject: Re: [PATCH kernel 9/9] pci: Allow encrypted MMIO mapping via sysfs*

On 2/3/26 19:20, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 


It is not _needed_ but (as the cover letter says) since one of my test devices does not use private MMIO for the main function, here it is to allow https://github.com/billfarrow/pcimem.git to map MMIO as private and do simple reads/writes. Useful for validation, can stop in gdb and inspect tables and whatever. Thanks,


> 
> -aneesh

---

## [43] Jason Gunthorpe — 2026-03-02
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On Mon, Mar 02, 2026 at 04:26:58PM +1100, Alexey Kardashevskiy wrote:

> > > Without secure vIOMMU, no Cbit in the S2 table (==host) for any
> > > VM. SDTE (==IOMMU) decides on shared/private for the device,

Yes, I understand this.

It seems from your email that the CPU S2 has the Cbit as part of the
address and the S1 feeds it through to the S2, so it is genuinely has
two addres spaces?

While the IOMMU S1 does not and instead needs a PTE bit which is
emphatically not an address bit because it does not feed through the
S2?

> > If 1<<51 is a valid IOPTE, and it is an actually address, then it
> > should be mapped into the IOMMU S2, shouldn't it? If it is in the

Well, I think things work more sensibly if you don't have to mangle
the address..

> > But in this case I would expect the vIOMMU to also use the same GPA
> > space starting from 0 and also remove the C bit, as the S2 shouldn't

Same way it knows if there is no S1? Why does the S1 change anything?

> > > There is vTOM in SDTE which is "every phys_addr_t above vTOM is no
> > > Cbit, below - with Cbit" (and there is the same thing for the CPU

Weird!!

Jason

---

## [44] dan.j.williams@intel.com — 2026-03-02
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

Jason Gunthorpe wrote:
> On Wed, Feb 25, 2026 at 12:57:01PM -0800, dan.j.williams@intel.com wrote:
> > > (since a device that's trusted to access private memory

Yes, what I meant to say is that Linux may need to be prepared for
implementations that do not copy over the shared mappings. At least for
early staging / minimum viable implementation for first merge.

> The T=1 IOMMU will still have them mapped on all three platforms
> AFAIK.

Oh, I thought SEV-TIO had trouble with this, if this is indeed the case,
great, ignore my first comment.

> On TDX/CCA the CPU and IOMMU S2 tables are identical, so of
> course the shared pages are mapped. On AMD there is only one IOMMU so

Ok, I need to go look at this DMA_ATTR_CC_DECRYPTED proposal...

I have a v2 of a TEE I/O set going out shortly and sounds like it will
need a rethink for this attribute proposal for v3. I think it still helps to
have combo sets at this stage so the whole lifecycle is visible in one
set, but it is nearly at the point of being too big a set to consider in
one sitting.

> > So on ARM where shared addresses are high, it is future work to figure
> > out how an accepted device might also access shared mappings outside the

TDX does not have the same problem, but the ARM "solution" seems
reasonable for now.

---

## [45] Jason Gunthorpe — 2026-03-02
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On Mon, Mar 02, 2026 at 03:53:13PM -0800, dan.j.williams@intel.com wrote:
> > > The specification allows it, but Linux DMA mapping core is not yet ready
> > > for it. So the expectation to start is that the device loses access to

Alexey?

I think it is really important that shared mappings continue to be
reachable by TDISP device.

> I have a v2 of a TEE I/O set going out shortly and sounds like it will
> need a rethink for this attribute proposal for v3. I think it still helps to

My problem is I can't get in one place an actually correct picture of
how the IOVA translation works in all the arches and how the
phys_addr_t works.

So it is hard to make sense of all these proposals. What I would love
to see is one series that deals with this:

  [PATCH v2 11/19] x86, dma: Allow accepted devices to map private memory

For *all* the arches, along with a description for each of:
 * how their phys_addr_t is constructed
 * how their S2 IOMMU mapping works
 * how a vIOMMU S1 would change any of the above.

Then maybe we can see if we are actually doing it properly or not.

> > ARM has a "solution" right now. The location of the high bit is
> > controlled by the VMM and the VMM cannot create a CC VM where the IPA

I'm surprised because Xu said:

 This is same as Intel TDX, the GPA shared bit are used by IOMMU to
 target shared/private. You can imagine for T=1, there are 2 IOPTs, or
 1 IOPT with all private at lower address & all shared at higher address.

 https://lore.kernel.org/all/aaF6HD2gfe%2Fudl%2Fx@yilunxu-OptiPlex-7050/

So how come that not have exactly the same problem as ARM?

Jason

---

## [46] dan.j.williams@intel.com — 2026-03-02
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

Jason Gunthorpe wrote:
[..]
> > I have a v2 of a TEE I/O set going out shortly and sounds like it will
> > need a rethink for this attribute proposal for v3. I think it still helps to

Yes, this is my struggle as well. I will put this on the agenda for the
next CCC call.

[..]
> 
> I'm surprised because Xu said:

Sorry, yes TDX has same behavior as ARM, excuse the noise.

---

## [47] Alexey Kardashevskiy — 2026-03-03
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On 3/3/26 00:35, Jason Gunthorpe wrote:
> On Mon, Mar 02, 2026 at 04:26:58PM +1100, Alexey Kardashevskiy wrote:
> 

"no Cbit" here was "there is Cbit in PTe and it is 0", rather than "Cbit is an address bit".

>>> Is this "Cbit" part of the CPU S2 page table address space or is it
>>> actually some PTE bit that says it is "encrypted" ?

afaik it is always (while SNP is enabled) a PTE bit that says "encrypted".

>>> It is confusing when you say it would start working with a vIOMMU.
>>

S1/S2 PTEs have Cbit. Addresses to look up those PTEs - do not.

(both are "addresses" - one in the PTE and another one - to look up the PTE)

> While the IOMMU S1 does not and instead needs a PTE bit which is
> emphatically not an address bit because it does not feed through the

afaik IOMMU works the same.

>>> If 1<<51 is a valid IOPTE, and it is an actually address, then it
>>> should be mapped into the IOMMU S2, shouldn't it? If it is in the

If no S1 - then sDTE decides on Cbit for the entire ASID (with the help of vTOM).

> Why does the S1 change anything?

S1 will have Cbit in individual PTEs, allowing per page control.
>>>> There is vTOM in SDTE which is "every phys_addr_t above vTOM is no
>>>> Cbit, below - with Cbit" (and there is the same thing for the CPU

:)

I understand I am often confusing, trying to unconfuse (including myself)... Thanks,

---

## [48] Jason Gunthorpe — 2026-03-03
*Subject: Re: [PATCH kernel 6/9] x86/dma-direct: Stop changing encrypted page
 state for TDISP devices*

On Tue, Mar 03, 2026 at 07:19:36PM +1100, Alexey Kardashevskiy wrote:

> > It seems from your email that the CPU S2 has the Cbit as part of the
> > address and the S1 feeds it through to the S2, so it is genuinely has

So we are back to what I was saying before: using phys_addr_t to
encode a PTE bit is probably a very confusing idea - especially when
contrasted with the other arches that have a legitimate address bit.

> > Same way it knows if there is no S1?
> 

Sounds like the intention was the IOMMU shared/private space would be
controlled with vTOM which actually does a create a legitimate address
bit in the phys_addr_t.

A sDTE global control is OK for non-TDISP devices, or even devices
that haven't entered RUN yet, but it is not OK for a TDISP device that
must still be able to access shared memory.

> I understand I am often confusing, trying to unconfuse (including myself)... Thanks,

It seems to me the AMD architecture itself is pretty confusing. :\

Jason

---

## [49] Jason Gunthorpe — 2026-03-03
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On Mon, Mar 02, 2026 at 08:19:11PM -0400, Jason Gunthorpe wrote:
> > Oh, I thought SEV-TIO had trouble with this, if this is indeed the case,
> > great, ignore my first comment.

I think Alexey has clarified this in the other thread, and probably
AMD has some work to do here.

The issue is AMD does not have seperate address spaces for
shared/private like ARM does, instead it relies on a C bit in the *PTE*
to determine shared/private.

The S2 IOMMU page table *does* have the full mapping of all shared &
private pages but the HW requires a matching C bit to permit access.

If there is a S1 IOMMU then the IOPTEs of the VM can provide the C
bit, so no problem.

If there is no S1 then the sDTE of the hypervisor controls the C bit,
and it sounds like currently AMD sets this globally which effectively
locks TDISP RUN devices to *only* access private memory.

I suspect AMD needs to use their vTOM feature to allow shared memory
to remain available to TDISP RUN with a high/low address split.

Alexey, did I capture this properly?

Jason

---

## [50] Alexey Kardashevskiy — 2026-03-04
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 3/3/26 23:43, Jason Gunthorpe wrote:
> On Mon, Mar 02, 2026 at 08:19:11PM -0400, Jason Gunthorpe wrote:
>>> Oh, I thought SEV-TIO had trouble with this, if this is indeed the case,

sDTE is controlled by the FW (not the HV) on the VM behalf - the VM chooses whether to enable sDTE and therefore vTOM.

> and it sounds like currently AMD sets this globally which effectively
> locks TDISP RUN devices to *only* access private memory.

Right. The assumption is that if the guest wants finer control - there is secure vIOMMU (in the works).

> I suspect AMD needs to use their vTOM feature to allow shared memory
> to remain available to TDISP RUN with a high/low address split.
I could probably do something about it bit I wonder what is the real live use case which requires leaking SME mask, have a live example which I could try recreating?

> Alexey, did I capture this properly?

Yes, with the correction about sDTE above. Thanks,


> 
> Jason

---

## [51] Jason Gunthorpe — 2026-03-04
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On Wed, Mar 04, 2026 at 05:45:31PM +1100, Alexey Kardashevskiy wrote:

> > I suspect AMD needs to use their vTOM feature to allow shared memory
> > to remain available to TDISP RUN with a high/low address split.

We need shared memory allocated through a DMABUF heap:

https://lore.kernel.org/all/20260223095136.225277-1-jiri@resnulli.us/

To work with all PCI devices in the system, TDISP or not.

Without this the ability for a TDISP device to ingest (encrypted) data
requires all kinds of memcpy..

So the DMA API should see the DMA_ATTR_CC_DECRYPTED and setup the
correct dma_dddr_t either by choosing the shared alias for the TDISP
device's vTOM, or setting the C bit in a vIOMMU S1.

Jason

---

## [52] Alexey Kardashevskiy — 2026-03-25
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 04/03/2026 23:43, Jason Gunthorpe wrote:
> On Wed, Mar 04, 2026 at 05:45:31PM +1100, Alexey Kardashevskiy wrote:
> 


I can make this work by using some high enough bit as "Sbit" in vTOM to mark shared pages but I'll have to decouple dma_addr_encrypted/dma_addr_canonical (not many uses but still scary) from sme_me_mask and I wonder if anyone has recently attempted this so I won't have to reinvent?

(a reminder: below vTOM address == private, above vTOM == shared)

Thanks,

---

## [53] Alexey Kardashevskiy — 2026-04-03
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 4/3/26 23:43, Jason Gunthorpe wrote:
> On Wed, Mar 04, 2026 at 05:45:31PM +1100, Alexey Kardashevskiy wrote:
> 

Something like that?

https://github.com/AMDESE/linux-kvm/commit/266a41a1ea746557eb63debce886ce2c98820667

With some little hacks I can make this tree do TDISP DMA to private or shared (swiotlb) memory by steering via this vTOM thing. Thanks,



> 
> Jason

---

## [54] Alexey Kardashevskiy — 2026-04-15
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 3/4/26 23:40, Alexey Kardashevskiy wrote:
> 
> 


Ping? Thanks,


> 
>

---

## [55] Jason Gunthorpe — 2026-04-20
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On Wed, Apr 15, 2026 at 04:32:14PM +1000, Alexey Kardashevskiy wrote:
> > > So the DMA API should see the DMA_ATTR_CC_DECRYPTED and setup the
> > > correct dma_dddr_t either by choosing the shared alias for the TDISP

That seems approx right, it is broadl similar to what ARM is
doing.. But the address map changes when switching to T=1 for AMD?

Jason

---

## [56] Alexey Kardashevskiy — 2026-04-30
*Subject: Re: [PATCH kernel 4/9] dma/swiotlb: Stop forcing SWIOTLB for TDISP
 devices*

On 21/4/26 09:50, Jason Gunthorpe wrote:
> On Wed, Apr 15, 2026 at 04:32:14PM +1000, Alexey Kardashevskiy wrote:
>>>> So the DMA API should see the DMA_ATTR_CC_DECRYPTED and setup the

Well, at the moment, in my WIP tree, I map the guest memory in the host IOMMU twice -

1) from 0 offset (and this is shared when T=0 and private when T=1) and
2) from vTOM offset (say, 1TB) - and this half of the mapping is always shared.

Thanks,

---
