---
title: 'crypto/ccp: Fix no-TSM build in SEV-TIO PCIe IDE'
date: 2025-12-01
last_reply: 2025-12-01
message_count: 2
participants: ['Alexey Kardashevskiy', 'Aithal, Srikanth']
---

## [1] Alexey Kardashevskiy — 2025-12-01

Here are some cleanups for disable TSM+IDE.

Fixes: 3532f6154971 ("crypto/ccp: Implement SEV-TIO PCIe IDE (phase1)")
Reported-by: Srikanth Aithal <Srikanth.Aithal@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

Better be just squashed into 3532f6154971 while it is in the next.
---
 drivers/crypto/ccp/sev-dev-tio.h | 12 ------------
 drivers/crypto/ccp/sev-dev.h     |  8 ++++++++
 drivers/crypto/ccp/sev-dev.c     | 12 ++++--------
 3 files changed, 12 insertions(+), 20 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev-tio.h b/drivers/crypto/ccp/sev-dev-tio.h
index 7c42351210ef..71f232a2b08b 100644
--- a/drivers/crypto/ccp/sev-dev-tio.h
+++ b/drivers/crypto/ccp/sev-dev-tio.h
@@ -7,8 +7,6 @@
 #include <linux/pci-ide.h>
 #include <uapi/linux/psp-sev.h>
 
-#if defined(CONFIG_CRYPTO_DEV_SP_PSP)
-
 struct sla_addr_t {
 	union {
 		u64 sla;
@@ -129,14 +127,4 @@ int sev_tio_dev_connect(struct tsm_dsm_tio *dev_data, u8 tc_mask, u8 ids[8], u8
 int sev_tio_dev_disconnect(struct tsm_dsm_tio *dev_data, bool force);
 int sev_tio_dev_reclaim(struct tsm_dsm_tio *dev_data);
 
-#endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
-
-#if defined(CONFIG_PCI_TSM)
-void sev_tsm_init_locked(struct sev_device *sev, void *tio_status_page);
-void sev_tsm_uninit(struct sev_device *sev);
-int sev_tio_cmd_buffer_len(int cmd);
-#else
-static inline int sev_tio_cmd_buffer_len(int cmd) { return 0; }
-#endif
-
 #endif	/* __PSP_SEV_TIO_H__ */
diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index dced4a8e9f01..d3e506206dbd 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -81,4 +81,12 @@ void sev_pci_exit(void);
 struct page *snp_alloc_hv_fixed_pages(unsigned int num_2mb_pages);
 void snp_free_hv_fixed_pages(struct page *page);
 
+#if defined(CONFIG_PCI_TSM)
+void sev_tsm_init_locked(struct sev_device *sev, void *tio_status_page);
+void sev_tsm_uninit(struct sev_device *sev);
+int sev_tio_cmd_buffer_len(int cmd);
+#else
+static inline int sev_tio_cmd_buffer_len(int cmd) { return 0; }
+#endif
+
 #endif /* __SEV_DEV_H */
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 365867f381e9..67ea9b30159a 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -38,7 +38,6 @@
 
 #include "psp-dev.h"
 #include "sev-dev.h"
-#include "sev-dev-tio.h"
 
 #define DEVICE_NAME		"sev"
 #define SEV_FW_FILE		"amd/sev.fw"
@@ -1365,11 +1364,6 @@ static int snp_filter_reserved_mem_regions(struct resource *rs, void *arg)
 	return 0;
 }
 
-static bool sev_tio_present(struct sev_device *sev)
-{
-	return (sev->snp_feat_info_0.ebx & SNP_SEV_TIO_SUPPORTED) != 0;
-}
-
 static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 {
 	struct psp_device *psp = psp_master;
@@ -1448,10 +1442,12 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 		data.list_paddr = __psp_pa(snp_range_list);
 
 #if defined(CONFIG_PCI_TSM)
-		data.tio_en = sev_tio_present(sev) &&
+		bool tio_supp = !!(sev->snp_feat_info_0.ebx & SNP_SEV_TIO_SUPPORTED);
+
+		data.tio_en = tio_supp &&
 			sev_tio_enabled && psp_init_on_probe &&
 			amd_iommu_sev_tio_supported();
-		if (sev_tio_present(sev) && !psp_init_on_probe)
+		if (tio_supp && !psp_init_on_probe)
 			dev_warn(sev->dev, "SEV-TIO as incompatible with psp_init_on_probe=0\n");
 #endif
 		cmd = SEV_CMD_SNP_INIT_EX;

---

## [2] Aithal, Srikanth — 2025-12-01
*Subject: Re: [PATCH kernel] crypto/ccp: Fix no-TSM build in SEV-TIO PCIe IDE*

On 12/1/2025 1:22 PM, Alexey Kardashevskiy wrote:
> Here are some cleanups for disable TSM+IDE.
> 

This fixes the issue. Thank you.
Tested-by: Srikanth Aithal <Srikanth.Aithal@amd.com>

---
