---
title: 'PCI/TSM: Enabling core infrastructure on AMD SEV TIO'
date: 2025-11-11
last_reply: 2025-11-21
message_count: 14
participants: ['Alexey Kardashevskiy', 'Jonathan Cameron', 'dan.j.williams@intel.com']
---

## [1] Alexey Kardashevskiy — 2025-11-11

Here are some patches to begin enabling SEV-TIO on AMD.

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

This is phase1 == IDE only.

SEV TIO spec:
https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58271.pdf

Acronyms:
TEE - Trusted Execution Environments, a concept of managing trust between the host and devices
TSM - TEE Security Manager (TSM), an entity which ensures security on the host
PSP - AMD platform secure processor (also "ASP", "AMD-SP"), acts as TSM on AMD.
SEV TIO - the TIO protocol implemented by the PSP and used by the host
GHCB - guest/host communication block - a protocol for guest-to-host communication via a shared page
TDISP - TEE Device Interface Security Protocol (PCIe).


Flow:
- Boot host OS, load CCP which registers itself as a TSM
- PCI TSM creates sysfs nodes under "tsm" subdirectory in for all TDISP-capable devices
- Enable IDE via "echo tsm0 > /sys/bus/pci/devices/0000:e1:00.0/tsm/connect"
- observe "secure" in stream states in "lspci" for the rootport and endpoint


This is pushed out to
https://github.com/AMDESE/linux-kvm/commits/tsm-staging


The previous conversation is here:
https://lore.kernel.org/r/20250218111017.491719-1-aik@amd.com

This is based on sha1
6fdb0d839738 Dan Williams "PCI/TSM: Documentation: Add Maturity Map".

Please comment. Thanks.



Alexey Kardashevskiy (6):
  PCI/TSM: Add secure SPDM DOE mailbox
  ccp: Make snp_reclaim_pages and __sev_do_cmd_locked public
  psp-sev: Assign numbers to all status codes and add new
  iommu/amd: Report SEV-TIO support
  crypto: ccp: Enable SEV-TIO feature in the PSP when supported
  crypto/ccp: Implement SEV-TIO PCIe IDE (phase1)

 drivers/crypto/ccp/Kconfig          |   1 +
 drivers/crypto/ccp/Makefile         |   8 +
 drivers/crypto/ccp/sev-dev-tio.h    | 141 +++
 drivers/crypto/ccp/sev-dev.h        |   8 +
 drivers/iommu/amd/amd_iommu_types.h |   1 +
 include/linux/amd-iommu.h           |   2 +
 include/linux/pci-tsm.h             |  14 +
 include/linux/psp-sev.h             |  22 +-
 include/uapi/linux/psp-sev.h        |  66 +-
 drivers/crypto/ccp/sev-dev-tio.c    | 989 ++++++++++++++++++++
 drivers/crypto/ccp/sev-dev-tsm.c    | 435 +++++++++
 drivers/crypto/ccp/sev-dev.c        |  69 +-
 drivers/iommu/amd/init.c            |   9 +
 drivers/pci/tsm.c                   |   4 +
 14 files changed, 1733 insertions(+), 36 deletions(-)
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.h
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.c
 create mode 100644 drivers/crypto/ccp/sev-dev-tsm.c

---

## [2] Alexey Kardashevskiy — 2025-11-11
*Subject: [PATCH kernel 1/6] PCI/TSM: Add secure SPDM DOE mailbox*

The IDE key programming happens via Secure SPDM channel, initialise it
at the PF0 probing.

Add the SPDM certificate slot (up to 8 are allowed by SPDM), the platform
is expected to select one.

While at this, add a common struct for SPDM request/response as these
are going to needed by every platform.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

(!tsm->doe_mb_sec) is definitely an error on AMD SEV-TIO, is not it on other platforms?
---
 include/linux/pci-tsm.h | 14 ++++++++++++++
 drivers/pci/tsm.c       |  4 ++++
 2 files changed, 18 insertions(+)

diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 40c5e4c31a3f..b6866f7c14b4 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -10,6 +10,14 @@ struct tsm_dev;
 struct kvm;
 enum pci_tsm_req_scope;
 
+/* SPDM control structure for DOE */
+struct tsm_spdm {
+	unsigned long req_len;
+	void *req;
+	unsigned long rsp_len;
+	void *rsp;
+};
+
 /*
  * struct pci_tsm_ops - manage confidential links and security state
  * @link_ops: Coordinate PCIe SPDM and IDE establishment via a platform TSM.
@@ -130,11 +138,17 @@ struct pci_tsm {
  * @base_tsm: generic core "tsm" context
  * @lock: mutual exclustion for pci_tsm_ops invocation
  * @doe_mb: PCIe Data Object Exchange mailbox
+ * @doe_mb_sec: DOE mailbox used when secured SPDM is requested
+ * @spdm: cached SPDM request/response buffers for the link
+ * @cert_slot: SPDM certificate slot
  */
 struct pci_tsm_pf0 {
 	struct pci_tsm base_tsm;
 	struct mutex lock;
 	struct pci_doe_mb *doe_mb;
+	struct pci_doe_mb *doe_mb_sec;
+	struct tsm_spdm spdm;
+	u8 cert_slot;
 };
 
 struct pci_tsm_mmio {
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index ed8a280a2cf4..378748b15825 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -1067,6 +1067,10 @@ int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
 		return -ENODEV;
 	}
+	tsm->doe_mb_sec = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+					       PCI_DOE_FEATURE_SSESSION);
+	if (!tsm->doe_mb_sec)
+		pci_warn(pdev, "TSM init failed to init SSESSION mailbox\n");
 
 	return pci_tsm_link_constructor(pdev, &tsm->base_tsm, tsm_dev);
 }

---

## [3] Alexey Kardashevskiy — 2025-11-11
*Subject: [PATCH kernel 2/6] ccp: Make snp_reclaim_pages and __sev_do_cmd_locked public*

The snp_reclaim_pages() helper reclaims pages in the FW state. SEV-TIO
and the TMPM driver (a hardware engine which smashes IOMMU PDEs among
other things) will use to reclaim memory when cleaning up.

Share and export snp_reclaim_pages().

Most of the SEV-TIO code uses sev_do_cmd() which locks the sev_cmd_mutex
and already exported. But the SNP init code (which also sets up SEV-TIO)
executes under the sev_cmd_mutex lock so the SEV-TIO code has to use
the __sev_do_cmd_locked() helper. This one though does not need to be
exported/shared globally as SEV-TIO is a part of the CCP driver still.

Share __sev_do_cmd_locked() via the CCP internal header.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/sev-dev.h |  1 +
 include/linux/psp-sev.h      |  6 ++++++
 drivers/crypto/ccp/sev-dev.c | 11 +++--------
 3 files changed, 10 insertions(+), 8 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index ac03bd0848f7..5cc08661b5b6 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -71,5 +71,6 @@ void sev_pci_exit(void);
 
 struct page *snp_alloc_hv_fixed_pages(unsigned int num_2mb_pages);
 void snp_free_hv_fixed_pages(struct page *page);
+int __sev_do_cmd_locked(int cmd, void *data, int *psp_ret);
 
 #endif /* __SEV_DEV_H */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index e0dbcb4b4fd9..e3db92e9c687 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -995,6 +995,7 @@ void *snp_alloc_firmware_page(gfp_t mask);
 void snp_free_firmware_page(void *addr);
 void sev_platform_shutdown(void);
 bool sev_is_snp_ciphertext_hiding_supported(void);
+int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool locked);
 
 #else	/* !CONFIG_CRYPTO_DEV_SP_PSP */
 
@@ -1033,6 +1034,11 @@ static inline void sev_platform_shutdown(void) { }
 
 static inline bool sev_is_snp_ciphertext_hiding_supported(void) { return false; }
 
+static inline int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool locked)
+{
+	return -ENODEV;
+}
+
 #endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
 
 #endif	/* __PSP_SEV_H__ */
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 0d13d47c164b..9e0c16b36f9c 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -387,13 +387,7 @@ static int sev_write_init_ex_file_if_required(int cmd_id)
 	return sev_write_init_ex_file();
 }
 
-/*
- * snp_reclaim_pages() needs __sev_do_cmd_locked(), and __sev_do_cmd_locked()
- * needs snp_reclaim_pages(), so a forward declaration is needed.
- */
-static int __sev_do_cmd_locked(int cmd, void *data, int *psp_ret);
-
-static int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool locked)
+int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool locked)
 {
 	int ret, err, i;
 
@@ -427,6 +421,7 @@ static int snp_reclaim_pages(unsigned long paddr, unsigned int npages, bool lock
 	snp_leak_pages(__phys_to_pfn(paddr), npages - i);
 	return ret;
 }
+EXPORT_SYMBOL_GPL(snp_reclaim_pages);
 
 static int rmp_mark_pages_firmware(unsigned long paddr, unsigned int npages, bool locked)
 {
@@ -857,7 +852,7 @@ static int snp_reclaim_cmd_buf(int cmd, void *cmd_buf)
 	return 0;
 }
 
-static int __sev_do_cmd_locked(int cmd, void *data, int *psp_ret)
+int __sev_do_cmd_locked(int cmd, void *data, int *psp_ret)
 {
 	struct cmd_buf_desc desc_list[CMD_BUF_DESC_MAX] = {0};
 	struct psp_device *psp = psp_master;

---

## [4] Alexey Kardashevskiy — 2025-11-11
*Subject: [PATCH kernel 3/6] psp-sev: Assign numbers to all status codes and add new*

Make the definitions explicit. Add some more new codes.

The following patches will be using SPDM_REQUEST and
EXPAND_BUFFER_LENGTH_REQUEST, others are useful for the PSP FW
diagnostics.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/uapi/linux/psp-sev.h | 66 ++++++++++++--------
 1 file changed, 41 insertions(+), 25 deletions(-)

diff --git a/include/uapi/linux/psp-sev.h b/include/uapi/linux/psp-sev.h
index c2fd324623c4..2b5b042eb73b 100644
--- a/include/uapi/linux/psp-sev.h
+++ b/include/uapi/linux/psp-sev.h
@@ -47,32 +47,32 @@ typedef enum {
 	 * with possible values from the specification.
 	 */
 	SEV_RET_NO_FW_CALL = -1,
-	SEV_RET_SUCCESS = 0,
-	SEV_RET_INVALID_PLATFORM_STATE,
-	SEV_RET_INVALID_GUEST_STATE,
-	SEV_RET_INAVLID_CONFIG,
+	SEV_RET_SUCCESS                    = 0,
+	SEV_RET_INVALID_PLATFORM_STATE     = 0x0001,
+	SEV_RET_INVALID_GUEST_STATE        = 0x0002,
+	SEV_RET_INAVLID_CONFIG             = 0x0003,
 	SEV_RET_INVALID_CONFIG = SEV_RET_INAVLID_CONFIG,
-	SEV_RET_INVALID_LEN,
-	SEV_RET_ALREADY_OWNED,
-	SEV_RET_INVALID_CERTIFICATE,
-	SEV_RET_POLICY_FAILURE,
-	SEV_RET_INACTIVE,
-	SEV_RET_INVALID_ADDRESS,
-	SEV_RET_BAD_SIGNATURE,
-	SEV_RET_BAD_MEASUREMENT,
-	SEV_RET_ASID_OWNED,
-	SEV_RET_INVALID_ASID,
-	SEV_RET_WBINVD_REQUIRED,
-	SEV_RET_DFFLUSH_REQUIRED,
-	SEV_RET_INVALID_GUEST,
-	SEV_RET_INVALID_COMMAND,
-	SEV_RET_ACTIVE,
-	SEV_RET_HWSEV_RET_PLATFORM,
-	SEV_RET_HWSEV_RET_UNSAFE,
-	SEV_RET_UNSUPPORTED,
-	SEV_RET_INVALID_PARAM,
-	SEV_RET_RESOURCE_LIMIT,
-	SEV_RET_SECURE_DATA_INVALID,
+	SEV_RET_INVALID_LEN                = 0x0004,
+	SEV_RET_ALREADY_OWNED              = 0x0005,
+	SEV_RET_INVALID_CERTIFICATE        = 0x0006,
+	SEV_RET_POLICY_FAILURE             = 0x0007,
+	SEV_RET_INACTIVE                   = 0x0008,
+	SEV_RET_INVALID_ADDRESS            = 0x0009,
+	SEV_RET_BAD_SIGNATURE              = 0x000A,
+	SEV_RET_BAD_MEASUREMENT            = 0x000B,
+	SEV_RET_ASID_OWNED                 = 0x000C,
+	SEV_RET_INVALID_ASID               = 0x000D,
+	SEV_RET_WBINVD_REQUIRED            = 0x000E,
+	SEV_RET_DFFLUSH_REQUIRED           = 0x000F,
+	SEV_RET_INVALID_GUEST              = 0x0010,
+	SEV_RET_INVALID_COMMAND            = 0x0011,
+	SEV_RET_ACTIVE                     = 0x0012,
+	SEV_RET_HWSEV_RET_PLATFORM         = 0x0013,
+	SEV_RET_HWSEV_RET_UNSAFE           = 0x0014,
+	SEV_RET_UNSUPPORTED                = 0x0015,
+	SEV_RET_INVALID_PARAM              = 0x0016,
+	SEV_RET_RESOURCE_LIMIT             = 0x0017,
+	SEV_RET_SECURE_DATA_INVALID        = 0x0018,
 	SEV_RET_INVALID_PAGE_SIZE          = 0x0019,
 	SEV_RET_INVALID_PAGE_STATE         = 0x001A,
 	SEV_RET_INVALID_MDATA_ENTRY        = 0x001B,
@@ -87,6 +87,22 @@ typedef enum {
 	SEV_RET_RESTORE_REQUIRED           = 0x0025,
 	SEV_RET_RMP_INITIALIZATION_FAILED  = 0x0026,
 	SEV_RET_INVALID_KEY                = 0x0027,
+	SEV_RET_SHUTDOWN_INCOMPLETE        = 0x0028,
+	SEV_RET_INCORRECT_BUFFER_LENGTH	   = 0x0030,
+	SEV_RET_EXPAND_BUFFER_LENGTH_REQUEST = 0x0031,
+	SEV_RET_SPDM_REQUEST               = 0x0032,
+	SEV_RET_SPDM_ERROR                 = 0x0033,
+	SEV_RET_SEV_STATUS_ERR_IN_DEV_CONN = 0x0035,
+	SEV_RET_SEV_STATUS_INVALID_DEV_CTX = 0x0036,
+	SEV_RET_SEV_STATUS_INVALID_TDI_CTX = 0x0037,
+	SEV_RET_SEV_STATUS_INVALID_TDI     = 0x0038,
+	SEV_RET_SEV_STATUS_RECLAIM_REQUIRED = 0x0039,
+	SEV_RET_IN_USE                     = 0x003A,
+	SEV_RET_SEV_STATUS_INVALID_DEV_STATE = 0x003B,
+	SEV_RET_SEV_STATUS_INVALID_TDI_STATE = 0x003C,
+	SEV_RET_SEV_STATUS_DEV_CERT_CHANGED = 0x003D,
+	SEV_RET_SEV_STATUS_RESYNC_REQ      = 0x003E,
+	SEV_RET_SEV_STATUS_RESPONSE_TOO_LARGE = 0x003F,
 	SEV_RET_MAX,
 } sev_ret_code;

---

## [5] Alexey Kardashevskiy — 2025-11-11
*Subject: [PATCH kernel 4/6] iommu/amd: Report SEV-TIO support*

The SEV-TIO switch in the AMD BIOS is reported to the OS via
the IOMMU Extended Feature 2 register (EFR2), bit 1.

Add helper to parse the bit and report the feature presence.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/iommu/amd/amd_iommu_types.h | 1 +
 include/linux/amd-iommu.h           | 2 ++
 drivers/iommu/amd/init.c            | 9 +++++++++
 3 files changed, 12 insertions(+)

diff --git a/drivers/iommu/amd/amd_iommu_types.h b/drivers/iommu/amd/amd_iommu_types.h
index a698a2e7ce2a..a2f72c53d3cc 100644
--- a/drivers/iommu/amd/amd_iommu_types.h
+++ b/drivers/iommu/amd/amd_iommu_types.h
@@ -107,6 +107,7 @@
 
 
 /* Extended Feature 2 Bits */
+#define FEATURE_SEVSNPIO_SUP	BIT_ULL(1)
 #define FEATURE_SNPAVICSUP	GENMASK_ULL(7, 5)
 #define FEATURE_SNPAVICSUP_GAM(x) \
 	(FIELD_GET(FEATURE_SNPAVICSUP, x) == 0x1)
diff --git a/include/linux/amd-iommu.h b/include/linux/amd-iommu.h
index 8cced632ecd0..0f64f09d1f34 100644
--- a/include/linux/amd-iommu.h
+++ b/include/linux/amd-iommu.h
@@ -18,10 +18,12 @@ struct task_struct;
 struct pci_dev;
 
 extern void amd_iommu_detect(void);
+extern bool amd_iommu_sev_tio_supported(void);
 
 #else /* CONFIG_AMD_IOMMU */
 
 static inline void amd_iommu_detect(void) { }
+static inline bool amd_iommu_sev_tio_supported(void) { return false; }
 
 #endif /* CONFIG_AMD_IOMMU */
 
diff --git a/drivers/iommu/amd/init.c b/drivers/iommu/amd/init.c
index f2991c11867c..ba95467ba492 100644
--- a/drivers/iommu/amd/init.c
+++ b/drivers/iommu/amd/init.c
@@ -2252,6 +2252,9 @@ static void print_iommu_info(void)
 		if (check_feature(FEATURE_SNP))
 			pr_cont(" SNP");
 
+		if (check_feature2(FEATURE_SEVSNPIO_SUP))
+			pr_cont(" SEV-TIO");
+
 		pr_cont("\n");
 	}
 
@@ -4015,4 +4018,10 @@ int amd_iommu_snp_disable(void)
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

## [6] Alexey Kardashevskiy — 2025-11-11
*Subject: [PATCH kernel 5/6] crypto: ccp: Enable SEV-TIO feature in the PSP when supported*

The PSP advertises the SEV-TIO support via the FEATURE_INFO command
advertised via SNP_PLATFORM_STATUS.

The BIOS advertises the SEV-TIO enablement via the IOMMU EFR2 register
(added in an earlier patch).

Enable SEV-TIO during the SNP_INIT_EX call if both the PSP and the BIOS
advertise support for it.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 include/linux/psp-sev.h      |  4 +++-
 drivers/crypto/ccp/sev-dev.c | 10 +++++++++-
 2 files changed, 12 insertions(+), 2 deletions(-)

diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index e3db92e9c687..6162cf5dccde 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -750,7 +750,8 @@ struct sev_data_snp_init_ex {
 	u32 list_paddr_en:1;
 	u32 rapl_dis:1;
 	u32 ciphertext_hiding_en:1;
-	u32 rsvd:28;
+	u32 tio_en:1;
+	u32 rsvd:27;
 	u32 rsvd1;
 	u64 list_paddr;
 	u16 max_snp_asid;
@@ -850,6 +851,7 @@ struct snp_feature_info {
 } __packed;
 
 #define SNP_CIPHER_TEXT_HIDING_SUPPORTED	BIT(3)
+#define SNP_SEV_TIO_SUPPORTED			BIT(1) /* EBX */
 
 #ifdef CONFIG_CRYPTO_DEV_SP_PSP
 
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 9e0c16b36f9c..2f1c9614d359 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1358,6 +1358,11 @@ static int snp_filter_reserved_mem_regions(struct resource *rs, void *arg)
 	return 0;
 }
 
+static bool sev_tio_present(struct sev_device *sev)
+{
+	return (sev->snp_feat_info_0.ebx & SNP_SEV_TIO_SUPPORTED) != 0;
+}
+
 static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 {
 	struct psp_device *psp = psp_master;
@@ -1434,6 +1439,8 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 		data.init_rmp = 1;
 		data.list_paddr_en = 1;
 		data.list_paddr = __psp_pa(snp_range_list);
+		data.tio_en = sev_tio_present(sev) &&
+			amd_iommu_sev_tio_supported();
 		cmd = SEV_CMD_SNP_INIT_EX;
 	} else {
 		cmd = SEV_CMD_SNP_INIT;
@@ -1471,7 +1478,8 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 
 	snp_hv_fixed_pages_state_update(sev, HV_FIXED);
 	sev->snp_initialized = true;
-	dev_dbg(sev->dev, "SEV-SNP firmware initialized\n");
+	dev_dbg(sev->dev, "SEV-SNP firmware initialized, SEV-TIO is %s\n",
+		data.tio_en ? "enabled" : "disabled");
 
 	dev_info(sev->dev, "SEV-SNP API:%d.%d build:%d\n", sev->api_major,
 		 sev->api_minor, sev->build);

---

## [7] Alexey Kardashevskiy — 2025-11-11
*Subject: [PATCH kernel 6/6] crypto/ccp: Implement SEV-TIO PCIe IDE (phase1)*

Implement the SEV-TIO (Trusted I/O) firmware interface for PCIe TDISP
(Trust Domain In-Socket Protocol). This enables secure communication
between trusted domains and PCIe devices through the PSP (Platform
Security Processor).

The implementation includes:
- Device Security Manager (DSM) operations for establishing secure links
- SPDM (Security Protocol and Data Model) over DOE (Data Object Exchange)
- IDE (Integrity Data Encryption) stream management for secure PCIe

This module bridges the SEV firmware stack with the generic PCIe TSM
framework.

This is phase1 as described in Documentation/driver-api/pci/tsm.rst.

On AMD SEV, the AMD PSP firmware acts as TSM (manages the security/trust).
The CCP driver provides the interface to it and registers in the TSM
subsystem.

Implement SEV TIO PSP command wrappers in sev-dev-tio.c and store
the data in the SEV-TIO-specific structs.

Implement TSM hooks and IDE setup in sev-dev-tsm.c.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/Kconfig       |   1 +
 drivers/crypto/ccp/Makefile      |   8 +
 drivers/crypto/ccp/sev-dev-tio.h | 141 +++
 drivers/crypto/ccp/sev-dev.h     |   7 +
 include/linux/psp-sev.h          |  12 +
 drivers/crypto/ccp/sev-dev-tio.c | 989 ++++++++++++++++++++
 drivers/crypto/ccp/sev-dev-tsm.c | 435 +++++++++
 drivers/crypto/ccp/sev-dev.c     |  48 +-
 8 files changed, 1640 insertions(+), 1 deletion(-)

diff --git a/drivers/crypto/ccp/Kconfig b/drivers/crypto/ccp/Kconfig
index f394e45e11ab..3e737d3e21c8 100644
--- a/drivers/crypto/ccp/Kconfig
+++ b/drivers/crypto/ccp/Kconfig
@@ -25,6 +25,7 @@ config CRYPTO_DEV_CCP_CRYPTO
 	default m
 	depends on CRYPTO_DEV_CCP_DD
 	depends on CRYPTO_DEV_SP_CCP
+	select PCI_TSM
 	select CRYPTO_HASH
 	select CRYPTO_SKCIPHER
 	select CRYPTO_AUTHENC
diff --git a/drivers/crypto/ccp/Makefile b/drivers/crypto/ccp/Makefile
index a9626b30044a..839df68b70ff 100644
--- a/drivers/crypto/ccp/Makefile
+++ b/drivers/crypto/ccp/Makefile
@@ -16,6 +16,14 @@ ccp-$(CONFIG_CRYPTO_DEV_SP_PSP) += psp-dev.o \
                                    hsti.o \
                                    sfs.o
 
+ifeq ($(CONFIG_CRYPTO_DEV_SP_PSP)$(CONFIG_PCI_TSM),yy)
+ccp-y += sev-dev-tsm.o sev-dev-tio.o
+endif
+
+ifeq ($(CONFIG_CRYPTO_DEV_SP_PSP)$(CONFIG_PCI_TSM),my)
+ccp-m += sev-dev-tsm.o sev-dev-tio.o
+endif
+
 obj-$(CONFIG_CRYPTO_DEV_CCP_CRYPTO) += ccp-crypto.o
 ccp-crypto-objs := ccp-crypto-main.o \
 		   ccp-crypto-aes.o \
diff --git a/drivers/crypto/ccp/sev-dev-tio.h b/drivers/crypto/ccp/sev-dev-tio.h
new file mode 100644
index 000000000000..c72ac38d4351
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tio.h
@@ -0,0 +1,141 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef __PSP_SEV_TIO_H__
+#define __PSP_SEV_TIO_H__
+
+#include <linux/pci-tsm.h>
+#include <linux/tsm.h>
+#include <linux/pci-ide.h>
+#include <uapi/linux/psp-sev.h>
+
+#if defined(CONFIG_CRYPTO_DEV_SP_PSP)
+
+/* Return codes from SEV-TIO helpers to request DOE MB transaction */
+#define TSM_PROTO_CMA_SPDM              1
+#define TSM_PROTO_SECURED_CMA_SPDM      2
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
+
+/* Describes TIO device */
+struct tsm_dsm_tio {
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
+	void *data_pg; /* Data page for DEV_STATUS/TDI_STATUS/TDI_INFO/ASID_FENCE */
+
+#define TIO_IDE_MAX_TC	8
+	struct pci_ide *ide[TIO_IDE_MAX_TC];
+};
+
+/* Described TSM structure for PF0 pointed by pci_dev->tsm */
+struct tio_dsm {
+	struct pci_tsm_pf0 tsm;
+	struct tsm_dsm_tio data;
+	struct sev_device *sev;
+};
+
+/* Data object IDs */
+#define SPDM_DOBJ_ID_NONE		0
+#define SPDM_DOBJ_ID_REQ		1
+#define SPDM_DOBJ_ID_RESP		2
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
+/**
+ * struct sev_tio_status - TIO_STATUS command's info_paddr buffer
+ *
+ * @length: Length of this structure in bytes
+ * @tio_en: Indicates that SNP_INIT_EX initialized the RMP for SEV-TIO
+ * @tio_init_done: Indicates TIO_INIT has been invoked
+ * @spdm_req_size_min: Minimum SPDM request buffer size in bytes
+ * @spdm_req_size_max: Maximum SPDM request buffer size in bytes
+ * @spdm_scratch_size_min: Minimum SPDM scratch buffer size in bytes
+ * @spdm_scratch_size_max: Maximum SPDM scratch buffer size in bytes
+ * @spdm_out_size_min: Minimum SPDM output buffer size in bytes
+ * @spdm_out_size_max: Maximum for the SPDM output buffer size in bytes
+ * @spdm_rsp_size_min: Minimum SPDM response buffer size in bytes
+ * @spdm_rsp_size_max: Maximum SPDM response buffer size in bytes
+ * @devctx_size: Size of a device context buffer in bytes
+ * @tdictx_size: Size of a TDI context buffer in bytes
+ * @tio_crypto_alg: TIO crypto algorithms supported
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
+	u32 tio_crypto_alg;
+	u8 reserved[12];
+} __packed;
+
+int sev_tio_init_locked(void *tio_status_page);
+int sev_tio_continue(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm);
+
+int sev_tio_dev_create(struct tsm_dsm_tio *dev_data, u16 device_id, u16 root_port_id,
+		       u8 segment_id);
+int sev_tio_dev_connect(struct tsm_dsm_tio *dev_data, u8 tc_mask, u8 ids[8], u8 cert_slot,
+			struct tsm_spdm *spdm);
+int sev_tio_dev_disconnect(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm, bool force);
+int sev_tio_dev_reclaim(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm);
+
+int sev_tio_asid_fence_clear(struct sla_addr_t dev_ctx, u64 gctx_paddr, int *psp_ret);
+int sev_tio_asid_fence_status(struct tsm_dsm_tio *dev_data, u16 device_id, u8 segment_id,
+			      u32 asid, bool *fenced);
+
+#endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
+
+#if defined(CONFIG_PCI_TSM)
+void sev_tsm_init_locked(struct sev_device *sev, void *tio_status_page);
+void sev_tsm_uninit(struct sev_device *sev);
+int sev_tio_cmd_buffer_len(int cmd);
+#else
+static inline int sev_tio_cmd_buffer_len(int cmd) { return 0; }
+#endif
+
+#endif	/* __PSP_SEV_TIO_H__ */
diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index 5cc08661b5b6..754353becc9c 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -34,6 +34,8 @@ struct sev_misc_dev {
 	struct miscdevice misc;
 };
 
+struct sev_tio_status;
+
 struct sev_device {
 	struct device *dev;
 	struct psp_device *psp;
@@ -61,6 +63,11 @@ struct sev_device {
 
 	struct sev_user_data_snp_status snp_plat_status;
 	struct snp_feature_info snp_feat_info_0;
+
+#if defined(CONFIG_PCI_TSM)
+	struct tsm_dev *tsmdev;
+	struct sev_tio_status *tio_status;
+#endif
 };
 
 int sev_dev_init(struct psp_device *psp);
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 6162cf5dccde..14263b6f6e32 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -109,6 +109,18 @@ enum sev_cmd {
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
+	SEV_CMD_TIO_ASID_FENCE_CLEAR	= 0x0E1,
+	SEV_CMD_TIO_ASID_FENCE_STATUS	= 0x0E2,
 	SEV_CMD_MAX,
 };
 
diff --git a/drivers/crypto/ccp/sev-dev-tio.c b/drivers/crypto/ccp/sev-dev-tio.c
new file mode 100644
index 000000000000..ca0db6e64839
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tio.c
@@ -0,0 +1,989 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+// Interface to PSP for CCP/SEV-TIO/SNP-VM
+
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include <linux/psp.h>
+#include <linux/vmalloc.h>
+#include <linux/bitfield.h>
+#include <asm/sev-common.h>
+#include <asm/sev.h>
+#include <asm/page.h>
+#include "sev-dev.h"
+#include "sev-dev-tio.h"
+
+#define to_tio_status(dev_data)	\
+		(container_of((dev_data), struct tio_dsm, data)->sev->tio_status)
+
+static void *__prep_data_pg(struct tsm_dsm_tio *dev_data, size_t len)
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
+#define SLA_EOL			((struct sla_addr_t) { .pfn = ((1UL << 40) - 1) })
+#define SLA_NULL		((struct sla_addr_t) { 0 })
+#define IS_SLA_NULL(s)		((s).sla == SLA_NULL.sla)
+#define IS_SLA_EOL(s)		((s).sla == SLA_EOL.sla)
+
+static phys_addr_t sla_to_pa(struct sla_addr_t sla)
+{
+	u64 pfn = sla.pfn;
+	u64 pa = pfn << PAGE_SHIFT;
+
+	return pa;
+}
+
+static void *sla_to_va(struct sla_addr_t sla)
+{
+	void *va = __va(__sme_clr(sla_to_pa(sla)));
+
+	return va;
+}
+
+#define sla_to_pfn(sla)		(__pa(sla_to_va(sla)) >> PAGE_SHIFT)
+#define sla_to_page(sla)	virt_to_page(sla_to_va(sla))
+
+static struct sla_addr_t make_sla(struct page *pg, bool stp)
+{
+	u64 pa = __sme_set(page_to_phys(pg));
+	struct sla_addr_t ret = {
+		.pfn = pa >> PAGE_SHIFT,
+		.page_size = SLA_PAGE_SIZE_4K, /* Do not do SLA_PAGE_SIZE_2M ATM */
+		.page_type = stp ? SLA_PAGE_TYPE_SCATTER : SLA_PAGE_TYPE_DATA
+	};
+
+	return ret;
+}
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
+/* Defined in sev-dev-tio.h so sev-dev-tsm.c can read types of blobs */
+struct spdm_dobj_hdr_cert;
+struct spdm_dobj_hdr_meas;
+struct spdm_dobj_hdr_report;
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
+	if (WARN_ON_ONCE(!hdr))
+		return NULL;
+
+	if (hdr->id != check_dobjid) {
+		pr_err("! ERROR: expected %d, found %d\n", check_dobjid, hdr->id);
+		return NULL;
+	}
+
+	return hdr;
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
+ * struct sev_data_tio_asid_fence_clear - TIO_ASID_FENCE_CLEAR command
+ *
+ * @length: Length in bytes of this command buffer
+ * @dev_ctx_paddr: Scatter list address of device context
+ * @gctx_paddr: System physical address of guest context page
+ *
+ * This command clears the ASID fence for a TDI.
+ */
+struct sev_data_tio_asid_fence_clear {
+	u32 length;				/* In */
+	u32 reserved1;
+	struct sla_addr_t dev_ctx_paddr;	/* In */
+	u64 gctx_paddr;			/* In */
+	u8 reserved2[8];
+} __packed;
+
+/**
+ * struct sev_data_tio_asid_fence_status - TIO_ASID_FENCE_STATUS command
+ *
+ * @length: Length in bytes of this command buffer
+ * @dev_ctx_paddr: Scatter list address of device context
+ * @asid: Address Space Identifier to query
+ * @status_pa: System physical address where fence status will be written
+ *
+ * This command queries the fence status for a specific ASID.
+ */
+struct sev_data_tio_asid_fence_status {
+	u32 length;				/* In */
+	u8 reserved1[4];
+	struct sla_addr_t dev_ctx_paddr;	/* In */
+	u32 asid;				/* In */
+	u64 status_pa;
+	u8 reserved2[4];
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
+		struct sla_addr_t *scatter = sla_to_va(sla);
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
+			pp[i] = sla_to_page(scatter[i]);
+
+		buf = vm_map_ram(pp, npages, 0);
+		kfree(pp);
+	} else {
+		struct page *pg = sla_to_page(sla);
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
+		struct sla_addr_t *scatter = sla_to_va(sla);
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
+			scatter = sla_to_va(sla);
+
+			for (i = 0; i < npages; ++i) {
+				if (IS_SLA_EOL(scatter[i]))
+					break;
+
+				ret = snp_reclaim_pages(sla_to_pa(scatter[i]), 1, false);
+				if (ret)
+					break;
+			}
+		} else {
+			ret = snp_reclaim_pages(sla_to_pa(sla), 1, false);
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
+			free_page((unsigned long)sla_to_va(scatter[i]));
+		}
+	}
+
+	free_page((unsigned long)sla_to_va(sla));
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
+		ret = make_sla(pg, true);
+		scatter = page_to_virt(pg);
+		for (i = 0; i < npages; ++i) {
+			pg = alloc_page(GFP_KERNEL | __GFP_ZERO);
+			if (!pg)
+				goto no_reclaim_exit;
+
+			scatter[i] = make_sla(pg, false);
+		}
+		scatter[i] = SLA_EOL;
+	} else {
+		pg = alloc_page(GFP_KERNEL | __GFP_ZERO);
+		if (!pg)
+			return SLA_NULL;
+
+		ret = make_sla(pg, false);
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
+				if (rmp_make_private(sla_to_pfn(scatter[i]), 0,
+						     PG_LEVEL_4K, 0, true))
+					goto free_exit;
+			}
+		} else {
+			if (rmp_make_private(sla_to_pfn(ret), 0, PG_LEVEL_4K, 0, true))
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
+static int sev_tio_do_cmd(int cmd, void *data, size_t data_len, int *psp_ret,
+			  struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm)
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
+		struct sev_tio_status *tio_status = to_tio_status(dev_data);
+		size_t resp_len = tio_status->spdm_req_size_max -
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
+		spdm->req_len = req_hdr->hdr.length - sla_dobj_id_to_size(SPDM_DOBJ_ID_REQ);
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
+int sev_tio_continue(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm)
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
+	if (!ret && (dev_data->psp_ret != SEV_RET_SUCCESS))
+		return -EINVAL;
+
+	return ret;
+}
+
+static int spdm_ctrl_init(struct tsm_spdm *spdm, struct spdm_ctrl *ctrl,
+			  struct tsm_dsm_tio *dev_data)
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
+static void spdm_ctrl_free(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_tio_status *tio_status = to_tio_status(dev_data);
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
+static int spdm_ctrl_alloc(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_tio_status *tio_status = to_tio_status(dev_data);
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
+int sev_tio_init_locked(void *tio_status_page)
+{
+	struct sev_tio_status *tio_status = tio_status_page;
+	struct sev_data_tio_status data_status = {
+		.length = sizeof(data_status),
+	};
+	int ret = 0, psp_ret = 0;
+
+	data_status.status_paddr = __psp_pa(tio_status_page);
+	ret = __sev_do_cmd_locked(SEV_CMD_TIO_STATUS, &data_status, &psp_ret);
+	if (ret)
+		return ret;
+
+	if (tio_status->length < offsetofend(struct sev_tio_status, tdictx_size) ||
+	    tio_status->flags & 0xFFFFFF00)
+		return -EFAULT;
+
+	if (!tio_status->tio_en && !tio_status->tio_init_done)
+		return -ENOENT;
+
+	if (tio_status->tio_init_done)
+		return -EBUSY;
+
+	struct sev_data_tio_init ti = { .length = sizeof(ti) };
+
+	ret = __sev_do_cmd_locked(SEV_CMD_TIO_INIT, &ti, &psp_ret);
+	if (ret)
+		return ret;
+
+	ret = __sev_do_cmd_locked(SEV_CMD_TIO_STATUS, &data_status, &psp_ret);
+	if (ret)
+		return ret;
+
+	return 0;
+}
+
+int sev_tio_dev_create(struct tsm_dsm_tio *dev_data, u16 device_id,
+		       u16 root_port_id, u8 segment_id)
+{
+	struct sev_tio_status *tio_status = to_tio_status(dev_data);
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
+int sev_tio_dev_reclaim(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm)
+{
+	struct sev_tio_status *tio_status = to_tio_status(dev_data);
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
+int sev_tio_dev_connect(struct tsm_dsm_tio *dev_data, u8 tc_mask, u8 ids[8], u8 cert_slot,
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
+int sev_tio_dev_disconnect(struct tsm_dsm_tio *dev_data, struct tsm_spdm *spdm, bool force)
+{
+	struct sev_data_tio_dev_disconnect dc = {
+		.length = sizeof(dc),
+		.dev_ctx_sla = dev_data->dev_ctx,
+		.force = force,
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
+int sev_tio_asid_fence_clear(struct sla_addr_t dev_ctx, u64 gctx_paddr, int *psp_ret)
+{
+	struct sev_data_tio_asid_fence_clear c = {
+		.length = sizeof(c),
+		.dev_ctx_paddr = dev_ctx,
+		.gctx_paddr = gctx_paddr,
+	};
+
+	return sev_do_cmd(SEV_CMD_TIO_ASID_FENCE_CLEAR, &c, psp_ret);
+}
+
+int sev_tio_asid_fence_status(struct tsm_dsm_tio *dev_data, u16 device_id, u8 segment_id,
+			      u32 asid, bool *fenced)
+{
+	u64 *status = prep_data_pg(u64, dev_data);
+	struct sev_data_tio_asid_fence_status s = {
+		.length = sizeof(s),
+		.dev_ctx_paddr = dev_data->dev_ctx,
+		.asid = asid,
+		.status_pa = __psp_pa(status),
+	};
+	int ret;
+
+	ret = sev_do_cmd(SEV_CMD_TIO_ASID_FENCE_STATUS, &s, &dev_data->psp_ret);
+
+	if (ret == SEV_RET_SUCCESS) {
+		u8 dma_status = *status & 0x3;
+		u8 mmio_status = (*status >> 2) & 0x3;
+
+		switch (dma_status) {
+		case 0:
+			*fenced = false;
+			break;
+		case 1:
+		case 3:
+			*fenced = true;
+			break;
+		default:
+			pr_err("%04x:%x:%x.%d: undefined DMA fence state %#llx\n",
+			       segment_id, PCI_BUS_NUM(device_id),
+			       PCI_SLOT(device_id), PCI_FUNC(device_id), *status);
+			*fenced = true;
+			break;
+		}
+
+		switch (mmio_status) {
+		case 0:
+			*fenced = false;
+			break;
+		case 3:
+			*fenced = true;
+			break;
+		default:
+			pr_err("%04x:%x:%x.%d: undefined MMIO fence state %#llx\n",
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
+int sev_tio_cmd_buffer_len(int cmd)
+{
+	switch (cmd) {
+	case SEV_CMD_TIO_STATUS:		return sizeof(struct sev_data_tio_status);
+	case SEV_CMD_TIO_INIT:			return sizeof(struct sev_data_tio_init);
+	case SEV_CMD_TIO_DEV_CREATE:		return sizeof(struct sev_data_tio_dev_create);
+	case SEV_CMD_TIO_DEV_RECLAIM:		return sizeof(struct sev_data_tio_dev_reclaim);
+	case SEV_CMD_TIO_DEV_CONNECT:		return sizeof(struct sev_data_tio_dev_connect);
+	case SEV_CMD_TIO_DEV_DISCONNECT:	return sizeof(struct sev_data_tio_dev_disconnect);
+	case SEV_CMD_TIO_ASID_FENCE_CLEAR:	return sizeof(struct sev_data_tio_asid_fence_clear);
+	case SEV_CMD_TIO_ASID_FENCE_STATUS: return sizeof(struct sev_data_tio_asid_fence_status);
+	default:				return 0;
+	}
+}
diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
new file mode 100644
index 000000000000..4702139185a2
--- /dev/null
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -0,0 +1,435 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+// Interface to CCP/SEV-TIO for generic PCIe TDISP module
+
+#include <linux/pci.h>
+#include <linux/device.h>
+#include <linux/tsm.h>
+#include <linux/iommu.h>
+#include <linux/pci-doe.h>
+#include <linux/bitfield.h>
+#include <linux/module.h>
+
+#include <asm/sev-common.h>
+#include <asm/sev.h>
+
+#include "psp-dev.h"
+#include "sev-dev.h"
+#include "sev-dev-tio.h"
+
+MODULE_IMPORT_NS("PCI_IDE");
+
+#define TIO_DEFAULT_NR_IDE_STREAMS	1
+
+static uint nr_ide_streams = TIO_DEFAULT_NR_IDE_STREAMS;
+module_param_named(ide_nr, nr_ide_streams, uint, 0644);
+MODULE_PARM_DESC(ide_nr, "Set the maximum number of IDE streams per PHB");
+
+#define dev_to_sp(dev)		((struct sp_device *)dev_get_drvdata(dev))
+#define dev_to_psp(dev)		((struct psp_device *)(dev_to_sp(dev)->psp_data))
+#define dev_to_sev(dev)		((struct sev_device *)(dev_to_psp(dev)->sev_data))
+#define tsm_dev_to_sev(tsmdev)	dev_to_sev((tsmdev)->dev.parent)
+#define tsm_pf0_to_sev(t)	tsm_dev_to_sev((t)->base.owner)
+
+/*to_pci_tsm_pf0((pdev)->tsm)*/
+#define pdev_to_tsm_pf0(pdev)	(((pdev)->tsm && (pdev)->tsm->dsm_dev) ? \
+				((struct pci_tsm_pf0 *)((pdev)->tsm->dsm_dev->tsm)) : \
+				NULL)
+
+#define tsm_pf0_to_data(t)	(&(container_of((t), struct tio_dsm, tsm)->data))
+
+static int sev_tio_spdm_cmd(struct pci_tsm_pf0 *dsm, int ret)
+{
+	struct tsm_dsm_tio *dev_data = tsm_pf0_to_data(dsm);
+	struct tsm_spdm *spdm = &dsm->spdm;
+	struct pci_doe_mb *doe_mb;
+
+	/* Check the main command handler response before entering the loop */
+	if (ret == 0 && dev_data->psp_ret != SEV_RET_SUCCESS)
+		return -EINVAL;
+	else if (ret <= 0)
+		return ret;
+
+	/* ret > 0 means "SPDM requested" */
+	while (ret > 0) {
+		/* The proto can change at any point */
+		if (ret == TSM_PROTO_CMA_SPDM) {
+			doe_mb = dsm->doe_mb;
+		} else if (ret == TSM_PROTO_SECURED_CMA_SPDM) {
+			doe_mb = dsm->doe_mb_sec;
+		} else {
+			ret = -EFAULT;
+			break;
+		}
+
+		ret = pci_doe(doe_mb, PCI_VENDOR_ID_PCI_SIG, ret,
+			      spdm->req, spdm->req_len, spdm->rsp, spdm->rsp_len);
+		if (ret < 0)
+			break;
+
+		WARN_ON_ONCE(ret == 0); /* The response should never be empty */
+		spdm->rsp_len = ret;
+		ret = sev_tio_continue(dev_data, &dsm->spdm);
+	}
+
+	return ret;
+}
+
+static int stream_enable(struct pci_ide *ide)
+{
+	struct pci_dev *rp = pcie_find_root_port(ide->pdev);
+	int ret;
+
+	ret = pci_ide_stream_enable(rp, ide);
+	if (!ret)
+		ret = pci_ide_stream_enable(ide->pdev, ide);
+
+	if (ret)
+		pci_ide_stream_disable(rp, ide);
+
+	return ret;
+}
+
+static int streams_enable(struct pci_ide **ide)
+{
+	int ret = 0;
+
+	for (int i = 0; i < TIO_IDE_MAX_TC; ++i) {
+		if (ide[i]) {
+			ret = stream_enable(ide[i]);
+			if (ret)
+				break;
+		}
+	}
+
+	return ret;
+}
+
+static void stream_disable(struct pci_ide *ide)
+{
+	pci_ide_stream_disable(ide->pdev, ide);
+	pci_ide_stream_disable(pcie_find_root_port(ide->pdev), ide);
+}
+
+static void streams_disable(struct pci_ide **ide)
+{
+	for (int i = 0; i < TIO_IDE_MAX_TC; ++i)
+		if (ide[i])
+			stream_disable(ide[i]);
+}
+
+static void stream_setup(struct pci_ide *ide)
+{
+	struct pci_dev *rp = pcie_find_root_port(ide->pdev);
+
+	ide->partner[PCI_IDE_EP].rid_start = 0;
+	ide->partner[PCI_IDE_EP].rid_end = 0xffff;
+	ide->partner[PCI_IDE_RP].rid_start = 0;
+	ide->partner[PCI_IDE_RP].rid_end = 0xffff;
+
+	ide->pdev->ide_cfg = 0;
+	ide->pdev->ide_tee_limit = 1;
+	rp->ide_cfg = 1;
+	rp->ide_tee_limit = 0;
+
+	pci_warn(ide->pdev, "Forcing CFG/TEE for %s", pci_name(rp));
+	pci_ide_stream_setup(ide->pdev, ide);
+	pci_ide_stream_setup(rp, ide);
+}
+
+static u8 streams_setup(struct pci_ide **ide, u8 *ids)
+{
+	bool def = false;
+	u8 tc_mask = 0;
+	int i;
+
+	for (i = 0; i < TIO_IDE_MAX_TC; ++i) {
+		if (!ide[i]) {
+			ids[i] = 0xFF;
+			continue;
+		}
+
+		tc_mask |= 1 << i;
+		ids[i] = ide[i]->stream_id;
+
+		if (!def) {
+			struct pci_ide_partner *settings;
+
+			settings = pci_ide_to_settings(ide[i]->pdev, ide[i]);
+			settings->default_stream = 1;
+			def = true;
+		}
+
+		stream_setup(ide[i]);
+	}
+
+	return tc_mask;
+}
+
+static int streams_register(struct pci_ide **ide)
+{
+	int ret = 0, i;
+
+	for (i = 0; i < TIO_IDE_MAX_TC; ++i) {
+		if (!ide[i])
+			continue;
+
+		ret = pci_ide_stream_register(ide[i]);
+		if (ret)
+			break;
+	}
+
+	return ret;
+}
+
+static void streams_unregister(struct pci_ide **ide)
+{
+	for (int i = 0; i < TIO_IDE_MAX_TC; ++i)
+		if (ide[i])
+			pci_ide_stream_unregister(ide[i]);
+}
+
+static void stream_teardown(struct pci_ide *ide)
+{
+	pci_ide_stream_teardown(ide->pdev, ide);
+	pci_ide_stream_teardown(pcie_find_root_port(ide->pdev), ide);
+}
+
+static void streams_teardown(struct pci_ide **ide)
+{
+	for (int i = 0; i < TIO_IDE_MAX_TC; ++i) {
+		if (ide[i]) {
+			stream_teardown(ide[i]);
+			pci_ide_stream_free(ide[i]);
+			ide[i] = NULL;
+		}
+	}
+}
+
+static int stream_alloc(struct pci_dev *pdev, struct tsm_dsm_tio *dev_data,
+			unsigned int tc)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide *ide;
+
+	if (dev_data->ide[tc]) {
+		pci_err(pdev, "Stream for class=%d already registered", tc);
+		return -EBUSY;
+	}
+
+	/* FIXME: find a better way */
+	if (nr_ide_streams != TIO_DEFAULT_NR_IDE_STREAMS)
+		pci_notice(pdev, "Enable non-default %d streams", nr_ide_streams);
+	pci_ide_set_nr_streams(to_pci_host_bridge(rp->bus->bridge), nr_ide_streams);
+
+	ide = pci_ide_stream_alloc(pdev);
+	if (!ide)
+		return -EFAULT;
+
+	/* Blindly assign streamid=0 to TC=0, and so on */
+	ide->stream_id = tc;
+
+	dev_data->ide[tc] = ide;
+
+	return 0;
+}
+
+static struct pci_tsm *tio_pf0_probe(struct pci_dev *pdev, struct sev_device *sev)
+{
+	struct tio_dsm *dsm __free(kfree) = kzalloc(sizeof(*dsm), GFP_KERNEL);
+	int rc;
+
+	if (!dsm)
+		return NULL;
+
+	rc = pci_tsm_pf0_constructor(pdev, &dsm->tsm, sev->tsmdev);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "TSM enabled\n");
+	dsm->sev = sev;
+	return &no_free_ptr(dsm)->tsm.base_tsm;
+}
+
+static struct pci_tsm *dsm_probe(struct tsm_dev *tsmdev, struct pci_dev *pdev)
+{
+	struct sev_device *sev = tsm_dev_to_sev(tsmdev);
+
+	if (is_pci_tsm_pf0(pdev))
+		return tio_pf0_probe(pdev, sev);
+	return 0;
+}
+
+static void dsm_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+
+	pci_dbg(pdev, "TSM disabled\n");
+
+	if (is_pci_tsm_pf0(pdev)) {
+		struct tio_dsm *dsm = container_of(tsm, struct tio_dsm, tsm.base_tsm);
+
+		pci_tsm_pf0_destructor(&dsm->tsm);
+		kfree(dsm);
+	}
+}
+
+static int dsm_create(struct pci_tsm_pf0 *dsm)
+{
+	struct pci_dev *pdev = dsm->base_tsm.pdev;
+	u8 segment_id = pdev->bus ? pci_domain_nr(pdev->bus) : 0;
+	struct pci_dev *rootport = pcie_find_root_port(pdev);
+	u16 device_id = pci_dev_id(pdev);
+	struct tsm_dsm_tio *dev_data = tsm_pf0_to_data(dsm);
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
+	req_page = alloc_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+	if (!req_page)
+		return -ENOMEM;
+
+	ret = sev_tio_dev_create(dev_data, device_id, root_port_id, segment_id);
+	if (ret)
+		goto free_resp_exit;
+
+	return 0;
+
+free_resp_exit:
+	__free_page(req_page);
+	return ret;
+}
+
+static int dsm_connect(struct pci_dev *pdev)
+{
+	struct pci_tsm_pf0 *dsm = pdev_to_tsm_pf0(pdev);
+	struct tsm_dsm_tio *dev_data = tsm_pf0_to_data(dsm);
+	u8 ids[TIO_IDE_MAX_TC];
+	u8 tc_mask;
+	int ret;
+
+	ret = stream_alloc(pdev, dev_data, 0);
+	if (ret)
+		return ret;
+
+	ret = dsm_create(dsm);
+	if (ret)
+		goto ide_free_exit;
+
+	tc_mask = streams_setup(dev_data->ide, ids);
+
+	ret = sev_tio_dev_connect(dev_data, tc_mask, ids, dsm->cert_slot, &dsm->spdm);
+	ret = sev_tio_spdm_cmd(dsm, ret);
+	if (ret)
+		goto free_exit;
+
+	streams_enable(dev_data->ide);
+
+	ret = streams_register(dev_data->ide);
+	if (ret)
+		goto free_exit;
+
+	return 0;
+
+free_exit:
+	sev_tio_dev_reclaim(dev_data, &dsm->spdm);
+
+	streams_disable(dev_data->ide);
+ide_free_exit:
+
+	streams_teardown(dev_data->ide);
+
+	if (ret > 0)
+		ret = -EFAULT;
+	return ret;
+}
+
+static void dsm_disconnect(struct pci_dev *pdev)
+{
+	bool force = SYSTEM_HALT <= system_state && system_state <= SYSTEM_RESTART;
+	struct pci_tsm_pf0 *dsm = pdev_to_tsm_pf0(pdev);
+	struct tsm_dsm_tio *dev_data = tsm_pf0_to_data(dsm);
+	int ret;
+
+	ret = sev_tio_dev_disconnect(dev_data, &dsm->spdm, force);
+	ret = sev_tio_spdm_cmd(dsm, ret);
+	if (ret && !force) {
+		ret = sev_tio_dev_disconnect(dev_data, &dsm->spdm, true);
+		sev_tio_spdm_cmd(dsm, ret);
+	}
+
+	sev_tio_dev_reclaim(dev_data, &dsm->spdm);
+
+	streams_disable(dev_data->ide);
+	streams_unregister(dev_data->ide);
+	streams_teardown(dev_data->ide);
+}
+
+static struct pci_tsm_ops sev_tsm_ops = {
+	.probe = dsm_probe,
+	.remove = dsm_remove,
+	.connect = dsm_connect,
+	.disconnect = dsm_disconnect,
+};
+
+void sev_tsm_init_locked(struct sev_device *sev, void *tio_status_page)
+{
+	struct sev_tio_status *t __free(kfree) = kzalloc(sizeof(*t), GFP_KERNEL);
+	struct tsm_dev *tsmdev;
+	int ret;
+
+	WARN_ON(sev->tio_status);
+
+	if (!t)
+		return;
+
+	ret = sev_tio_init_locked(tio_status_page);
+	if (ret) {
+		pr_warn("SEV-TIO STATUS failed with %d\n", ret);
+		goto error_exit;
+	}
+
+	tsmdev = tsm_register(sev->dev, &sev_tsm_ops);
+	if (IS_ERR(tsmdev))
+		goto error_exit;
+
+	memcpy(t, tio_status_page, sizeof(*t));
+
+	pr_notice("SEV-TIO status: EN=%d INIT_DONE=%d rq=%d..%d rs=%d..%d "
+		  "scr=%d..%d out=%d..%d dev=%d tdi=%d algos=%x\n",
+		  t->tio_en, t->tio_init_done,
+		  t->spdm_req_size_min, t->spdm_req_size_max,
+		  t->spdm_rsp_size_min, t->spdm_rsp_size_max,
+		  t->spdm_scratch_size_min, t->spdm_scratch_size_max,
+		  t->spdm_out_size_min, t->spdm_out_size_max,
+		  t->devctx_size, t->tdictx_size,
+		  t->tio_crypto_alg);
+
+	sev->tsmdev = tsmdev;
+	sev->tio_status = no_free_ptr(t);
+
+	return;
+
+error_exit:
+	pr_err("Failed to enable SEV-TIO: ret=%d en=%d initdone=%d SEV=%d\n",
+	       ret, t->tio_en, t->tio_init_done,
+	       boot_cpu_has(X86_FEATURE_SEV));
+	pr_err("Check BIOS for: SMEE, SEV Control, SEV-ES ASID Space Limit=99,\n"
+	       "SNP Memory (RMP Table) Coverage, RMP Coverage for 64Bit MMIO Ranges\n"
+	       "SEV-SNP Support, SEV-TIO Support, PCIE IDE Capability\n");
+}
+
+void sev_tsm_uninit(struct sev_device *sev)
+{
+	if (sev->tsmdev)
+		tsm_unregister(sev->tsmdev);
+
+	sev->tsmdev = NULL;
+}
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 2f1c9614d359..365867f381e9 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -38,6 +38,7 @@
 
 #include "psp-dev.h"
 #include "sev-dev.h"
+#include "sev-dev-tio.h"
 
 #define DEVICE_NAME		"sev"
 #define SEV_FW_FILE		"amd/sev.fw"
@@ -75,6 +76,12 @@ static bool psp_init_on_probe = true;
 module_param(psp_init_on_probe, bool, 0444);
 MODULE_PARM_DESC(psp_init_on_probe, "  if true, the PSP will be initialized on module init. Else the PSP will be initialized on the first command requiring it");
 
+#if defined(CONFIG_PCI_TSM)
+static bool sev_tio_enabled = true;
+module_param_named(tio, sev_tio_enabled, bool, 0444);
+MODULE_PARM_DESC(tio, "Enables TIO in SNP_INIT_EX");
+#endif
+
 MODULE_FIRMWARE("amd/amd_sev_fam17h_model0xh.sbin"); /* 1st gen EPYC */
 MODULE_FIRMWARE("amd/amd_sev_fam17h_model3xh.sbin"); /* 2nd gen EPYC */
 MODULE_FIRMWARE("amd/amd_sev_fam19h_model0xh.sbin"); /* 3rd gen EPYC */
@@ -251,7 +258,7 @@ static int sev_cmd_buffer_len(int cmd)
 	case SEV_CMD_SNP_COMMIT:		return sizeof(struct sev_data_snp_commit);
 	case SEV_CMD_SNP_FEATURE_INFO:		return sizeof(struct sev_data_snp_feature_info);
 	case SEV_CMD_SNP_VLEK_LOAD:		return sizeof(struct sev_user_data_snp_vlek_load);
-	default:				return 0;
+	default:				return sev_tio_cmd_buffer_len(cmd);
 	}
 
 	return 0;
@@ -1439,8 +1446,14 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 		data.init_rmp = 1;
 		data.list_paddr_en = 1;
 		data.list_paddr = __psp_pa(snp_range_list);
+
+#if defined(CONFIG_PCI_TSM)
 		data.tio_en = sev_tio_present(sev) &&
+			sev_tio_enabled && psp_init_on_probe &&
 			amd_iommu_sev_tio_supported();
+		if (sev_tio_present(sev) && !psp_init_on_probe)
+			dev_warn(sev->dev, "SEV-TIO as incompatible with psp_init_on_probe=0\n");
+#endif
 		cmd = SEV_CMD_SNP_INIT_EX;
 	} else {
 		cmd = SEV_CMD_SNP_INIT;
@@ -1487,6 +1500,24 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 	atomic_notifier_chain_register(&panic_notifier_list,
 				       &snp_panic_notifier);
 
+#if defined(CONFIG_PCI_TSM)
+	if (data.tio_en) {
+		/*
+		 * This executes with the sev_cmd_mutex held so down the stack
+		 * snp_reclaim_pages(locked=false) might be needed (which is extremely
+		 * unlikely) but will cause a deadlock.
+		 * Instead of exporting __snp_alloc_firmware_pages(), allocate a page
+		 * for this one call here.
+		 */
+		void *tio_status = page_address(__snp_alloc_firmware_pages(
+			GFP_KERNEL_ACCOUNT | __GFP_ZERO, 0, true));
+
+		if (tio_status) {
+			sev_tsm_init_locked(sev, tio_status);
+			__snp_free_firmware_pages(virt_to_page(tio_status), 0, true);
+		}
+	}
+#endif
 	sev_es_tmr_size = SNP_TMR_SIZE;
 
 	return 0;
@@ -2766,7 +2797,22 @@ static void __sev_firmware_shutdown(struct sev_device *sev, bool panic)
 
 static void sev_firmware_shutdown(struct sev_device *sev)
 {
+#if defined(CONFIG_PCI_TSM)
+	/*
+	 * Calling without sev_cmd_mutex held as TSM will likely try disconnecting
+	 * IDE and this ends up calling sev_do_cmd() which locks sev_cmd_mutex.
+	 */
+	if (sev->tio_status)
+		sev_tsm_uninit(sev);
+#endif
+
 	mutex_lock(&sev_cmd_mutex);
+
+#if defined(CONFIG_PCI_TSM)
+	kfree(sev->tio_status);
+	sev->tio_status = NULL;
+#endif
+
 	__sev_firmware_shutdown(sev, false);
 	mutex_unlock(&sev_cmd_mutex);
 }

---

## [8] Jonathan Cameron — 2025-11-11
*Subject: Re: [PATCH kernel 6/6] crypto/ccp: Implement SEV-TIO PCIe IDE
 (phase1)*

On Tue, 11 Nov 2025 17:38:18 +1100
Alexey Kardashevskiy <aik@amd.com> wrote:

> Implement the SEV-TIO (Trusted I/O) firmware interface for PCIe TDISP
> (Trust Domain In-Socket Protocol). This enables secure communication
Hi Alexey,

Various minor comments inline.

Thanks,

Jonathan

> diff --git a/drivers/crypto/ccp/sev-dev-tio.h b/drivers/crypto/ccp/sev-dev-tio.h
> new file mode 100644

> diff --git a/drivers/crypto/ccp/sev-dev-tio.c b/drivers/crypto/ccp/sev-dev-tio.c
> new file mode 100644

> +static size_t sla_dobj_id_to_size(u8 id)
> +{

Maybe just returning above would be simpler and remove need for local variables
etc.

> +}
>

A few of these aren't present in the structure so out of date docs I think

> + * @segment_id: The PCIe Segment Identifier of the device to connect to.
> + * @dev_ctx_sla: Scatter list address of the device context buffer.

flags need documentation as well.
Generally I'd avoid bitfields and rely on defines so we don't hit
the weird stuff the c spec allows to be done with bitfields.

> + * @raw_bitstream: 0: Requests the digest form of the attestation report
> + *                 1: Requests the raw bitstream form of the attestation report

> +/**
> + * struct sev_data_tio_dev_reclaim - TIO_DEV_RECLAIM command
Why a u32 for this reserved, but u8[] arrays for some of thos in
other structures like sev_data_tio_asid_fence_status.
I'd aim for consistency on that. I don't really mind which option!
> +	struct sla_addr_t dev_ctx_sla;
> +} __packed;

As below wrt to complete docs.

> + *
> + * This command clears the ASID fence for a TDI.
Kernel-doc complains about undocument structure elements, so you probably have
to add a trivial comment for the two reserved ones to keep it happy.

> + * @dev_ctx_paddr: Scatter list address of device context
> + * @asid: Address Space Identifier to query

Could use a __free to avoid needing to manually clean this up.

> +		if (!pp)
> +			return NULL;

> +
> +/* Expands a buffer, only firmware owned buffers allowed for now */

Is this check correct?  I think you return 1 on no need to expand.

> +			return -EFAULT;
> +

			return -EINVAL;

> +		}
> +		resp_hdr->data_type = req_hdr->data_type;

> +static int spdm_ctrl_init(struct tsm_spdm *spdm, struct spdm_ctrl *ctrl,
> +			  struct tsm_dsm_tio *dev_data)

This seems like a slightly odd function as it is initializing two different
things.  To me I'd read this as only initializing the spdm_ctrl structure.
Perhaps split, or rename?

> +{
> +	ctrl->req = dev_data->req;

> +
> +int sev_tio_init_locked(void *tio_status_page)

ret always set before use so don't initialize.

> +
> +	data_status.status_paddr = __psp_pa(tio_status_page);
	return __sev_do_cmd_locked() perhaps.

> +}
> +

return 0;  Might as well make it clear this is always a good path.

> +
> +free_data_pg_exit:

> +
> +int sev_tio_dev_connect(struct tsm_dsm_tio *dev_data, u8 tc_mask, u8 ids[8], u8 cert_slot,

return sev_tio_do_cmd...

> +}
> +

return sev_tio..

> +}
> +
The meaning of return codes in these functions is a mix of errno and SEV specific.
Perhaps some documentation to make that clear, or even a typedef for the SEV ones?
> +{
> +	u64 *status = prep_data_pg(u64, dev_data);

I guess this gets more complex in future series to mean that checking
the opposite isn't the way to go?
	if (ret != SEV_RET_SUCCESS)
		return ret;

If not I'd do that to reduce indent and have a nice quick exit
for errors.

> +		u8 dma_status = *status & 0x3;
> +		u8 mmio_status = (*status >> 2) & 0x3;
These feel like magic numbers that could perhaps have defines to give
them pretty names?
> +			*fenced = false;
> +			break;
Same as above, names might be nice.
> +			*fenced = false;
> +			break;

> diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
> new file mode 100644

> +
> +static uint nr_ide_streams = TIO_DEFAULT_NR_IDE_STREAMS;

Left over of something?

> +#define pdev_to_tsm_pf0(pdev)	(((pdev)->tsm && (pdev)->tsm->dsm_dev) ? \
> +				((struct pci_tsm_pf0 *)((pdev)->tsm->dsm_dev->tsm)) : \

	if (ret <= 0)
		return ret;

as returned already in the if path.

> +
> +	/* ret > 0 means "SPDM requested" */
I'd be tempted to do
		else 
			return -EFAULT;
here and similar if the other error path below.
> +		}
> +

I would suggest using a goto for the cleanup to avoid having
an unusual code flow, but more interesting to me is why pci_ide_stream_enable()
has side effects on failure that means we have to call pci_ide_stream_disable().

Looking at Dan's patch I can see that we might have programmed things
but then the hardware failed to set them up.   Perhaps we should push
cleanup into that function or at least add something to docs to point
out that we must cleanup whether or not that function succeeds?

> +	if (!ret)
> +		ret = pci_ide_stream_enable(ide->pdev, ide);
Personal taste thing so up to you but I'd do return ret;
here and return 0 at the end. 
> +				break;
> +		}

> +static u8 streams_setup(struct pci_ide **ide, u8 *ids)
> +{

Kind of obvious either way but perhaps a slight preference for
		tc_mask |= BIT(i);

> +		ids[i] = ide[i]->stream_id;
> +
Worth doing if the line is long or there is more to do here.  Maybe there
is in some follow up series, but fo rnow
		if (ide[i]) {
			ret = pci_ide_stream_register(ide[i]);
			if (ret)
				return ret;
		}
Seems cleaner to me.

> +
> +		ret = pci_ide_stream_register(ide[i]);

> +static void stream_teardown(struct pci_ide *ide)
> +{

Seems unbalanced to have stream_alloc take
the struct tsm_dsm_tio * pointer to just access dev_data->ide
but the teardown passes that directly.

I'm be happier if they were both passed the same thing (either struct pci_ide **ide
or struct tsm_dsm_tio *dev_data).
Slight preference for struct pci_ide **ide in stream_alloc as well.

> +{
> +	for (int i = 0; i < TIO_IDE_MAX_TC; ++i) {


> +
> +static int dsm_create(struct pci_tsm_pf0 *dsm)

Allocate then leak a page?  req_page isn't used.

> +	if (!req_page)
> +		return -ENOMEM;

As above. I'd use dev_data->ide instead of dev_data as the parameter here
to match the other cases later.  I'm guessing this parameter choice
was something that underwent evolution and perhaps ended up less
than ideal.

> +	if (ret)
> +		return ret;

My gut feeling would be that this manipulation of positive
return codes should be pushed to where it is more obvious why it is happening.
Either inside the functions or int the if (ret) blocks above.
It's sufficiently unusual I'd like it to be more obvious.

> +	return ret;
> +}
Whilst it is fine here, general advice is don't mix gotos and cleanup.h magic
in a given function (see the comments in the header).  

> +	struct tsm_dev *tsmdev;
> +	int ret;

If it weren't for the goto then this could be

	struct sev_tio_status *t __free(kfree) =
		kmemdup(tio_status_page, sizeof(*t), GFP_KERNEL;
	if (!t)
		return;


> +
> +	pr_notice("SEV-TIO status: EN=%d INIT_DONE=%d rq=%d..%d rs=%d..%d "

Superficially feels to me that some of this set of helpful messages is only relevant
to some error paths - maybe just print the most relevant parts where those problems
are detected?

> +}
> +

---

## [9] Alexey Kardashevskiy — 2025-11-12
*Subject: Re: [PATCH kernel 6/6] crypto/ccp: Implement SEV-TIO PCIe IDE
 (phase1)*

On 11/11/25 22:47, Jonathan Cameron wrote:
> On Tue, 11 Nov 2025 17:38:18 +1100
> Alexey Kardashevskiy <aik@amd.com> wrote:

Agrh. I asked the Cursor's AI to fix them all and yet it missed a bunch :)

> Generally I'd avoid bitfields and rely on defines so we don't hit
> the weird stuff the c spec allows to be done with bitfields.

imho bitfields are okay until different endianness but here is always LE.

>> + * @raw_bitstream: 0: Requests the digest form of the attestation report
>> + *                 1: Requests the raw bitstream form of the attestation report

I am just repeating the SEV TIO spec (which is getting polished now so I'll sync up with that).

> I'd aim for consistency on that. I don't really mind which option!
>> +	struct sla_addr_t dev_ctx_sla;


Well, if the PSP said "need expansion" but did not say "of what", then I'd thinkg it is screwed and I do not really want to continue. May return 0 but make it WARN_ON_ONCE(!rc1 && !rc2) if it is better.

> 
>> +			return -EFAULT;


pci_ide_stream_enable() is called on the rootport and then the endpoint and the revert is done on the rootport, cannot push the cleanup to pci_ide_stream_enable().



> 
>> +	if (!ret)
Well, really only "SNP Memory (RMP Table) Coverage" will make SNP_INIT_EX fail (and it is off by default) but for SEV-TIO to work - all these need to be enabled so I mention them all here. I guess I'll remove the whole "Check BIOS" thing, the defaults have changed now.

Thanks for the review, I'll fix what I have not commented on.

>> +}
>> +

---

## [10] dan.j.williams@intel.com — 2025-11-13
*Subject: Re: [PATCH kernel 1/6] PCI/TSM: Add secure SPDM DOE mailbox*

Alexey Kardashevskiy wrote:
> The IDE key programming happens via Secure SPDM channel, initialise it
> at the PF0 probing.

I think you just happen to have a multi-DOE test device, or a device
that has a PCI_DOE_FEATURE_SSESSION DOE and not a PCI_DOE_FEATURE_CMA
DOE.

> ---
>  include/linux/pci-tsm.h | 14 ++++++++++++++

I would only add things to the core that the core needs, or all
implementations can unify. You can see that tdx_spdm_msg_exchange() can
not use this common definition for example.

> +
>  /*

See below, pci_tsm_pf0 should only ever need one doe_mb instance.

> +	struct tsm_spdm spdm;

Per above, just move @tsm_spdm into the TIO object that wraps
pci_tsm_pf0.

> +	u8 cert_slot;
>  };

So it is surprising to find that a device supports PCI_DOE_FEATURE_CMA,
but requires the TSM to also use the PCI_DOE_FEATURE_SSESSION mailbox?
A PCI_DOE_FEATURE_CMA mailbox is capable of supporting secure sessions
and IDE.

When a device supports multiple DOE, the VMM does need to pick one, but the
hope was that "first CMA DOE" would work, but apparently you have a
device that wants to violate this simple heuristic?

What happens on this device if you use the CMA mailbox for IDE
establishment and secure sessions?

---

## [11] Alexey Kardashevskiy — 2025-11-17
*Subject: Re: [PATCH kernel 6/6] crypto/ccp: Implement SEV-TIO PCIe IDE
 (phase1)*

On 11/11/25 22:47, Jonathan Cameron wrote:
> On Tue, 11 Nov 2025 17:38:18 +1100
> Alexey Kardashevskiy <aik@amd.com> wrote:

Actually not, to_pci_tsm_pf0() is a static helper in drivers/pci/tsm.c and pdev_to_tsm_pf0() (below) is the same thing defined for drivers/crypto/ccp/sev-dev-tsm.c and I wonder if to_pci_tsm_pf0() is better be exported. pdev_to_tsm_pf0() does not need all the checks as if we are that far past the initial setup, we can skip on some checks which to_pci_tsm_pf0() performs so I have not exported to_pci_tsm_pf0() but left the comment. Thanks,

> 
>> +#define pdev_to_tsm_pf0(pdev)	(((pdev)->tsm && (pdev)->tsm->dsm_dev) ? \

---

## [12] Alexey Kardashevskiy — 2025-11-17
*Subject: Re: [PATCH kernel 1/6] PCI/TSM: Add secure SPDM DOE mailbox*

On 14/11/25 12:51, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>> The IDE key programming happens via Secure SPDM channel, initialise it


Oh I missed that we have tdx_spdm_msg_exchange() now, cool :)

>> +
>>   /*

Sure, can do that.

>> +	u8 cert_slot;
>>   };

What does guarantee that CMA supports SSESSION?

> When a device supports multiple DOE, the VMM does need to pick one, but the
> hope was that "first CMA DOE" would work, but apparently you have a

Nah, my devices have one DOE cap with 3 protocols supported, I just did not see any good reason to limit ourselves to one DOE MB. We will either have to BUG_ON on DOE MB which does CMA but does not do SSESSION, or just have 2 struct doe_mb pointers. Thanks,

---

## [13] dan.j.williams@intel.com — 2025-11-20
*Subject: Re: [PATCH kernel 6/6] crypto/ccp: Implement SEV-TIO PCIe IDE
 (phase1)*

Alexey Kardashevskiy wrote:
[..]
> >> +/*to_pci_tsm_pf0((pdev)->tsm)*/
> > 

Why does the low-level TSM driver need to_pci_tsm_pf0() when it
allocated the container for @tsm in the first place?

For example, samples/devsec/ does this:

static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
{
        struct pci_dev *pdev = tsm->pdev;

        dev_dbg(pci_tsm_host(pdev), "%s\n", pci_name(pdev));

        if (is_pci_tsm_pf0(pdev)) {
                struct devsec_tsm_pf0 *devsec_tsm = to_devsec_tsm_pf0(tsm);

                pci_tsm_pf0_destructor(&devsec_tsm->pci);
                kfree(devsec_tsm);
        } else {
                struct devsec_tsm_fn *devsec_tsm = to_devsec_tsm_fn(tsm);

                kfree(devsec_tsm);
        }
}

...where that to_devsec_tsm_pf0() is:

static struct devsec_tsm_pf0 *to_devsec_tsm_pf0(struct pci_tsm *tsm)
{
        return container_of(tsm, struct devsec_tsm_pf0, pci.base_tsm);
}

---

## [14] Alexey Kardashevskiy — 2025-11-21
*Subject: Re: [PATCH kernel 6/6] crypto/ccp: Implement SEV-TIO PCIe IDE
 (phase1)*

On 21/11/25 08:28, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..]


If the question "can I skip pci_tsm_pf0 and cast straight to tsm_dsm_tio" - yes I can and probably will, so so many leftovers are still there :)

If the question why I need pf0 in the TSM driver - for things like tdi_bind/unbind which take VFs pdev and I'll need PF0 for DOE.

Thanks,


> For example, samples/devsec/ does this:
>

---
