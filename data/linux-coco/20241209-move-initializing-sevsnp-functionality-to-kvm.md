---
title: 'Move initializing SEV/SNP functionality to KVM'
date: 2024-12-09
last_reply: 2024-12-10
message_count: 11
participants: ['Ashish Kalra', 'Dionna Amalie Glaze', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2024-12-09

From: Ashish Kalra <ashish.kalra@amd.com>

Remove initializing SEV/SNP functionality from PSP driver and instead add
support to KVM to explicitly initialize the PSP if KVM wants to use
SEV/SNP functionality.

This removes SEV/SNP initialization at PSP module probe time and does
on-demand SEV/SNP initialization when KVM really wants to use 
SEV/SNP functionality. This will allow running legacy non-confidential
VMs without initializating SEV functionality. 

This will assist in adding SNP CipherTextHiding support and SEV firmware
hotloading support in KVM without sharing SEV ASID management and SNP
guest context support between PSP driver and KVM and keeping all that
support only in KVM.

Ashish Kalra (7):
  crypto: ccp: Move dev_info/err messages for SEV/SNP initialization
  crypto: ccp: Fix implicit SEV/SNP init and shutdown in ioctls
  crypto: ccp: Reset TMR size at SNP Shutdown
  crypto: ccp: Register SNP panic notifier only if SNP is enabled
  crypto: ccp: Add new SEV/SNP platform shutdown API
  KVM: SVM: Add support to initialize SEV/SNP functionality in KVM
  crypto: ccp: Move SEV/SNP Platform initialization to KVM

 arch/x86/kvm/svm/sev.c       |  11 ++
 drivers/crypto/ccp/sev-dev.c | 227 ++++++++++++++++++++++++++---------
 include/linux/psp-sev.h      |   3 +
 3 files changed, 187 insertions(+), 54 deletions(-)

---

## [2] Ashish Kalra — 2024-12-09
*Subject: [PATCH 1/7] crypto: ccp: Move dev_info/err messages for SEV/SNP initialization*

From: Ashish Kalra <ashish.kalra@amd.com>

Remove dev_info and dev_err messages related to SEV/SNP initialization
from callers and instead move those inside __sev_platform_init_locked()
and __sev_snp_init_locked().

This allows both _sev_platform_init_locked() and various SEV/SNP ioctls
to call __sev_platform_init_locked() and __sev_snp_init_locked() for
implicit SEV/SNP initialization and shutdown without additionally
printing any errors/success messages.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 26 +++++++++++++++++++-------
 1 file changed, 19 insertions(+), 7 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index af018afd9cd7..a17796729725 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1177,19 +1177,27 @@ static int __sev_snp_init_locked(int *error)
 
 	rc = __sev_do_cmd_locked(cmd, arg, error);
 	if (rc)
-		return rc;
+		goto err;
 
 	/* Prepare for first SNP guest launch after INIT. */
 	wbinvd_on_all_cpus();
 	rc = __sev_do_cmd_locked(SEV_CMD_SNP_DF_FLUSH, NULL, error);
 	if (rc)
-		return rc;
+		goto err;
 
 	sev->snp_initialized = true;
 	dev_dbg(sev->dev, "SEV-SNP firmware initialized\n");
 
+	dev_info(sev->dev, "SEV-SNP API:%d.%d build:%d\n", sev->api_major,
+		 sev->api_minor, sev->build);
+
 	sev_es_tmr_size = SNP_TMR_SIZE;
 
+	return 0;
+
+err:
+	dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
+		rc, *error);
 	return rc;
 }
 
@@ -1268,7 +1276,7 @@ static int __sev_platform_init_locked(int *error)
 
 	rc = __sev_platform_init_handle_init_ex_path(sev);
 	if (rc)
-		return rc;
+		goto err;
 
 	rc = __sev_do_init_locked(&psp_ret);
 	if (rc && psp_ret == SEV_RET_SECURE_DATA_INVALID) {
@@ -1288,7 +1296,7 @@ static int __sev_platform_init_locked(int *error)
 		*error = psp_ret;
 
 	if (rc)
-		return rc;
+		goto err;
 
 	sev->state = SEV_STATE_INIT;
 
@@ -1296,7 +1304,7 @@ static int __sev_platform_init_locked(int *error)
 	wbinvd_on_all_cpus();
 	rc = __sev_do_cmd_locked(SEV_CMD_DF_FLUSH, NULL, error);
 	if (rc)
-		return rc;
+		goto err;
 
 	dev_dbg(sev->dev, "SEV firmware initialized\n");
 
@@ -1304,6 +1312,11 @@ static int __sev_platform_init_locked(int *error)
 		 sev->api_minor, sev->build);
 
 	return 0;
+
+err:
+	dev_err(sev->dev, "SEV: failed to INIT error %#x, rc %d\n",
+		psp_ret, rc);
+	return rc;
 }
 
 static int _sev_platform_init_locked(struct sev_platform_init_args *args)
@@ -1329,8 +1342,7 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 		 * Don't abort the probe if SNP INIT failed,
 		 * continue to initialize the legacy SEV firmware.
 		 */
-		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
-			rc, args->error);
+		dev_info(sev->dev, "SEV-SNP: failed, continue to INIT SEV firmware\n");
 	}
 
 	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */

---

## [3] Ashish Kalra — 2024-12-09
*Subject: [PATCH 2/7] crypto: ccp: Fix implicit SEV/SNP init and shutdown in ioctls*

From: Ashish Kalra <ashish.kalra@amd.com>

Modify the behavior of implicit SEV initialization in some of the
SEV ioctls to do both SEV initialization and shutdown and adds
implicit SNP initialization and shutdown to some of the SNP ioctls
so that the change of SEV/SNP platform initialization not being
done during PSP driver probe time does not break userspace tools
such as sevtool, etc.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 149 +++++++++++++++++++++++++++++------
 1 file changed, 125 insertions(+), 24 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index a17796729725..d8673d8836f1 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1453,7 +1453,8 @@ static int sev_ioctl_do_platform_status(struct sev_issue_cmd *argp)
 static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	int rc;
+	bool shutdown_required = false;
+	int rc, ret, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1462,19 +1463,30 @@ static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool wr
 		rc = __sev_platform_init_locked(&argp->error);
 		if (rc)
 			return rc;
+		shutdown_required = true;
+	}
+
+	rc = __sev_do_cmd_locked(cmd, NULL, &argp->error);
+
+	if (shutdown_required) {
+		ret = __sev_platform_shutdown_locked(&error);
+		if (ret)
+			dev_err(sev->dev, "SEV: failed to SHUTDOWN error %#x, rc %d\n",
+				error, ret);
 	}
 
-	return __sev_do_cmd_locked(cmd, NULL, &argp->error);
+	return rc;
 }
 
 static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_pek_csr input;
+	bool shutdown_required = false;
 	struct sev_data_pek_csr data;
 	void __user *input_address;
+	int ret, rc, error;
 	void *blob = NULL;
-	int ret;
 
 	if (!writable)
 		return -EPERM;
@@ -1505,6 +1517,7 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 		ret = __sev_platform_init_locked(&argp->error);
 		if (ret)
 			goto e_free_blob;
+		shutdown_required = true;
 	}
 
 	ret = __sev_do_cmd_locked(SEV_CMD_PEK_CSR, &data, &argp->error);
@@ -1523,6 +1536,13 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_blob:
+	if (shutdown_required) {
+		rc = __sev_platform_shutdown_locked(&error);
+		if (rc)
+			dev_err(sev->dev, "SEV: failed to SHUTDOWN error %#x, rc %d\n",
+				error, rc);
+	}
+
 	kfree(blob);
 	return ret;
 }
@@ -1738,8 +1758,9 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_pek_cert_import input;
 	struct sev_data_pek_cert_import data;
+	bool shutdown_required = false;
 	void *pek_blob, *oca_blob;
-	int ret;
+	int ret, rc, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1771,11 +1792,19 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 		ret = __sev_platform_init_locked(&argp->error);
 		if (ret)
 			goto e_free_oca;
+		shutdown_required = true;
 	}
 
 	ret = __sev_do_cmd_locked(SEV_CMD_PEK_CERT_IMPORT, &data, &argp->error);
 
 e_free_oca:
+	if (shutdown_required) {
+		rc = __sev_platform_shutdown_locked(&error);
+		if (rc)
+			dev_err(sev->dev, "SEV: failed to SHUTDOWN error %#x, rc %d\n",
+				error, rc);
+	}
+
 	kfree(oca_blob);
 e_free_pek:
 	kfree(pek_blob);
@@ -1892,17 +1921,8 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	struct sev_data_pdh_cert_export data;
 	void __user *input_cert_chain_address;
 	void __user *input_pdh_cert_address;
-	int ret;
-
-	/* If platform is not in INIT state then transition it to INIT. */
-	if (sev->state != SEV_STATE_INIT) {
-		if (!writable)
-			return -EPERM;
-
-		ret = __sev_platform_init_locked(&argp->error);
-		if (ret)
-			return ret;
-	}
+	bool shutdown_required = false;
+	int ret, rc, error;
 
 	if (copy_from_user(&input, (void __user *)argp->data, sizeof(input)))
 		return -EFAULT;
@@ -1943,6 +1963,16 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	data.cert_chain_len = input.cert_chain_len;
 
 cmd:
+	/* If platform is not in INIT state then transition it to INIT. */
+	if (sev->state != SEV_STATE_INIT) {
+		if (!writable)
+			return -EPERM;
+		ret = __sev_platform_init_locked(&argp->error);
+		if (ret)
+			goto e_free_cert;
+		shutdown_required = true;
+	}
+
 	ret = __sev_do_cmd_locked(SEV_CMD_PDH_CERT_EXPORT, &data, &argp->error);
 
 	/* If we query the length, FW responded with expected data. */
@@ -1969,6 +1999,13 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_cert:
+	if (shutdown_required) {
+		rc = __sev_platform_shutdown_locked(&error);
+		if (rc)
+			dev_err(sev->dev, "SEV: failed to SHUTDOWN error %#x, rc %d\n",
+				error, rc);
+	}
+
 	kfree(cert_blob);
 e_free_pdh:
 	kfree(pdh_blob);
@@ -1978,12 +2015,13 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 {
 	struct sev_device *sev = psp_master->sev_data;
+	bool shutdown_required = false;
 	struct sev_data_snp_addr buf;
 	struct page *status_page;
+	int ret, rc, error;
 	void *data;
-	int ret;
 
-	if (!sev->snp_initialized || !argp->data)
+	if (!argp->data)
 		return -EINVAL;
 
 	status_page = alloc_page(GFP_KERNEL_ACCOUNT);
@@ -1992,6 +2030,13 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 
 	data = page_address(status_page);
 
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&argp->error);
+		if (ret)
+			goto cleanup;
+		shutdown_required = true;
+	}
+
 	/*
 	 * Firmware expects status page to be in firmware-owned state, otherwise
 	 * it will report firmware error code INVALID_PAGE_STATE (0x1A).
@@ -2020,6 +2065,13 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 		ret = -EFAULT;
 
 cleanup:
+	if (shutdown_required) {
+		rc = __sev_snp_shutdown_locked(&error, false);
+		if (rc)
+			dev_err(sev->dev, "SEV-SNP: failed to SHUTDOWN error %#x, rc %d\n",
+				error, rc);
+	}
+
 	__free_pages(status_page, 0);
 	return ret;
 }
@@ -2028,21 +2080,38 @@ static int sev_ioctl_do_snp_commit(struct sev_issue_cmd *argp)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_data_snp_commit buf;
+	bool shutdown_required = false;
+	int ret, rc, error;
 
-	if (!sev->snp_initialized)
-		return -EINVAL;
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&argp->error);
+		if (ret)
+			return ret;
+		shutdown_required = true;
+	}
 
 	buf.len = sizeof(buf);
 
-	return __sev_do_cmd_locked(SEV_CMD_SNP_COMMIT, &buf, &argp->error);
+	ret = __sev_do_cmd_locked(SEV_CMD_SNP_COMMIT, &buf, &argp->error);
+
+	if (shutdown_required) {
+		rc = __sev_snp_shutdown_locked(&error, false);
+		if (rc)
+			dev_err(sev->dev, "SEV-SNP: failed to SHUTDOWN error %#x, rc %d\n",
+				error, rc);
+	}
+
+	return ret;
 }
 
 static int sev_ioctl_do_snp_set_config(struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_snp_config config;
+	bool shutdown_required = false;
+	int ret, rc, error;
 
-	if (!sev->snp_initialized || !argp->data)
+	if (!argp->data)
 		return -EINVAL;
 
 	if (!writable)
@@ -2051,17 +2120,34 @@ static int sev_ioctl_do_snp_set_config(struct sev_issue_cmd *argp, bool writable
 	if (copy_from_user(&config, (void __user *)argp->data, sizeof(config)))
 		return -EFAULT;
 
-	return __sev_do_cmd_locked(SEV_CMD_SNP_CONFIG, &config, &argp->error);
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&argp->error);
+		if (ret)
+			return ret;
+		shutdown_required = true;
+	}
+
+	ret = __sev_do_cmd_locked(SEV_CMD_SNP_CONFIG, &config, &argp->error);
+
+	if (shutdown_required) {
+		rc = __sev_snp_shutdown_locked(&error, false);
+		if (rc)
+			dev_err(sev->dev, "SEV-SNP: failed to SHUTDOWN error %#x, rc %d\n",
+				error, rc);
+	}
+
+	return ret;
 }
 
 static int sev_ioctl_do_snp_vlek_load(struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_snp_vlek_load input;
+	bool shutdown_required = false;
+	int ret, rc, error;
 	void *blob;
-	int ret;
 
-	if (!sev->snp_initialized || !argp->data)
+	if (!argp->data)
 		return -EINVAL;
 
 	if (!writable)
@@ -2080,8 +2166,23 @@ static int sev_ioctl_do_snp_vlek_load(struct sev_issue_cmd *argp, bool writable)
 
 	input.vlek_wrapped_address = __psp_pa(blob);
 
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&argp->error);
+		if (ret)
+			goto cleanup;
+		shutdown_required = true;
+	}
+
 	ret = __sev_do_cmd_locked(SEV_CMD_SNP_VLEK_LOAD, &input, &argp->error);
 
+	if (shutdown_required) {
+		rc = __sev_snp_shutdown_locked(&error, false);
+		if (rc)
+			dev_err(sev->dev, "SEV-SNP: failed to SHUTDOWN error %#x, rc %d\n",
+				error, rc);
+	}
+
+cleanup:
 	kfree(blob);
 
 	return ret;

---

## [4] Ashish Kalra — 2024-12-09
*Subject: [PATCH 3/7] crypto: ccp: Reset TMR size at SNP Shutdown*

From: Ashish Kalra <ashish.kalra@amd.com>

When SEV-SNP is enabled the TMR needs to be 2MB aligned and 2MB sized,
ensure that TMR size is reset back to default when SNP is shutdown.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 3 +++
 1 file changed, 3 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index d8673d8836f1..bc121ad9ec26 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1750,6 +1750,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	sev->snp_initialized = false;
 	dev_dbg(sev->dev, "SEV-SNP firmware shutdown\n");
 
+	/* Reset TMR size back to default */
+	sev_es_tmr_size = SEV_TMR_SIZE;
+
 	return ret;
 }

---

## [5] Ashish Kalra — 2024-12-09
*Subject: [PATCH 4/7] crypto: ccp: Register SNP panic notifier only if SNP is enabled*

From: Ashish Kalra <ashish.kalra@amd.com>

Register the SNP panic notifier if and only if SNP is actually
initialized and deregistering the notifier when shutting down
SNP in PSP driver when KVM module is unloaded.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 21 +++++++++++++--------
 1 file changed, 13 insertions(+), 8 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index bc121ad9ec26..21faf4c4c4ec 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -109,6 +109,13 @@ static void *sev_init_ex_buffer;
  */
 static struct sev_data_range_list *snp_range_list;
 
+static int snp_shutdown_on_panic(struct notifier_block *nb,
+				 unsigned long reason, void *arg);
+
+static struct notifier_block snp_panic_notifier = {
+	.notifier_call = snp_shutdown_on_panic,
+};
+
 static inline bool sev_version_greater_or_equal(u8 maj, u8 min)
 {
 	struct sev_device *sev = psp_master->sev_data;
@@ -1191,6 +1198,9 @@ static int __sev_snp_init_locked(int *error)
 	dev_info(sev->dev, "SEV-SNP API:%d.%d build:%d\n", sev->api_major,
 		 sev->api_minor, sev->build);
 
+	atomic_notifier_chain_register(&panic_notifier_list,
+				       &snp_panic_notifier);
+
 	sev_es_tmr_size = SNP_TMR_SIZE;
 
 	return 0;
@@ -1750,6 +1760,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	sev->snp_initialized = false;
 	dev_dbg(sev->dev, "SEV-SNP firmware shutdown\n");
 
+	atomic_notifier_chain_unregister(&panic_notifier_list,
+					 &snp_panic_notifier);
+
 	/* Reset TMR size back to default */
 	sev_es_tmr_size = SEV_TMR_SIZE;
 
@@ -2489,10 +2502,6 @@ static int snp_shutdown_on_panic(struct notifier_block *nb,
 	return NOTIFY_DONE;
 }
 
-static struct notifier_block snp_panic_notifier = {
-	.notifier_call = snp_shutdown_on_panic,
-};
-
 int sev_issue_cmd_external_user(struct file *filep, unsigned int cmd,
 				void *data, int *error)
 {
@@ -2541,8 +2550,6 @@ void sev_pci_init(void)
 	dev_info(sev->dev, "SEV%s API:%d.%d build:%d\n", sev->snp_initialized ?
 		"-SNP" : "", sev->api_major, sev->api_minor, sev->build);
 
-	atomic_notifier_chain_register(&panic_notifier_list,
-				       &snp_panic_notifier);
 	return;
 
 err:
@@ -2560,6 +2567,4 @@ void sev_pci_exit(void)
 
 	sev_firmware_shutdown(sev);
 
-	atomic_notifier_chain_unregister(&panic_notifier_list,
-					 &snp_panic_notifier);
 }

---

## [6] Ashish Kalra — 2024-12-09
*Subject: [PATCH 5/7] crypto: ccp: Add new SEV/SNP platform shutdown API*

From: Ashish Kalra <ashish.kalra@amd.com>

Add new API interface to do SEV/SNP platform shutdown when KVM module
is unloaded.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 13 +++++++++++++
 include/linux/psp-sev.h      |  3 +++
 2 files changed, 16 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 21faf4c4c4ec..b8938c96915b 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2468,6 +2468,19 @@ static void sev_firmware_shutdown(struct sev_device *sev)
 	mutex_unlock(&sev_cmd_mutex);
 }
 
+void sev_platform_shutdown(void)
+{
+	struct sev_device *sev;
+
+	if (!psp_master || !psp_master->sev_data)
+		return;
+
+	sev = psp_master->sev_data;
+
+	sev_firmware_shutdown(sev);
+}
+EXPORT_SYMBOL_GPL(sev_platform_shutdown);
+
 void sev_dev_destroy(struct psp_device *psp)
 {
 	struct sev_device *sev = psp->sev_data;
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 903ddfea8585..fea20fbe2a8a 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -945,6 +945,7 @@ int sev_do_cmd(int cmd, void *data, int *psp_ret);
 void *psp_copy_user_blob(u64 uaddr, u32 len);
 void *snp_alloc_firmware_page(gfp_t mask);
 void snp_free_firmware_page(void *addr);
+void sev_platform_shutdown(void);
 
 #else	/* !CONFIG_CRYPTO_DEV_SP_PSP */
 
@@ -979,6 +980,8 @@ static inline void *snp_alloc_firmware_page(gfp_t mask)
 
 static inline void snp_free_firmware_page(void *addr) { }
 
+static inline void sev_platform_shutdown(void) { }
+
 #endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
 
 #endif	/* __PSP_SEV_H__ */

---

## [7] Ashish Kalra — 2024-12-09
*Subject: [PATCH 6/7] KVM: SVM: Add support to initialize SEV/SNP functionality in KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

Remove platform initialization of SEV/SNP from PSP driver probe time and
move it to KVM module load time so that KVM can do SEV/SNP platform
initialization explicitly if it actually wants to use SEV/SNP
functionality.

With this patch, KVM will explicitly call into the PSP driver at load time
to initialize SEV/SNP by default but this behavior can be altered with KVM
module parameters to not do SEV/SNP platform initialization at module load
time if required. Additionally SEV/SNP platform shutdown is invoked during
KVM module unload time.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 72674b8825c4..ffb5c907c5bb 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2966,6 +2966,7 @@ void __init sev_set_cpu_caps(void)
 void __init sev_hardware_setup(void)
 {
 	unsigned int eax, ebx, ecx, edx, sev_asid_count, sev_es_asid_count;
+	struct sev_platform_init_args init_args = {0};
 	bool sev_snp_supported = false;
 	bool sev_es_supported = false;
 	bool sev_supported = false;
@@ -3082,6 +3083,13 @@ void __init sev_hardware_setup(void)
 	sev_supported_vmsa_features = 0;
 	if (sev_es_debug_swap_enabled)
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
+
+	if (!sev_enabled)
+		return;
+
+	/* Do SEV/SNP INIT */
+	init_args.probe = true;
+	sev_platform_init(&init_args);
 }
 
 void sev_hardware_unsetup(void)
@@ -3097,6 +3105,9 @@ void sev_hardware_unsetup(void)
 
 	misc_cg_set_capacity(MISC_CG_RES_SEV, 0);
 	misc_cg_set_capacity(MISC_CG_RES_SEV_ES, 0);
+
+	/* Do SEV/SNP Shutdown */
+	sev_platform_shutdown();
 }
 
 int sev_cpu_init(struct svm_cpu_data *sd)

---

## [8] Ashish Kalra — 2024-12-09
*Subject: [PATCH 7/7] crypto: ccp: Move SEV/SNP Platform initialization to KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

SNP initialization is forced during PSP driver probe purely because SNP
can't be initialized if VMs are running.  But the only in-tree user of
SEV/SNP functionality is KVM, and KVM depends on PSP driver for the same.
Forcing SEV/SNP initialization because a hypervisor could be running
legacy non-confidential VMs make no sense.

This patch removes SEV/SNP initialization from the PSP driver probe
time and moves the requirement to initialize SEV/SNP functionality
to KVM if it wants to use SEV/SNP.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 15 ---------------
 1 file changed, 15 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index b8938c96915b..52dce46745ba 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2528,9 +2528,7 @@ EXPORT_SYMBOL_GPL(sev_issue_cmd_external_user);
 void sev_pci_init(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	struct sev_platform_init_args args = {0};
 	u8 api_major, api_minor, build;
-	int rc;
 
 	if (!sev)
 		return;
@@ -2553,16 +2551,6 @@ void sev_pci_init(void)
 			 api_major, api_minor, build,
 			 sev->api_major, sev->api_minor, sev->build);
 
-	/* Initialize the platform */
-	args.probe = true;
-	rc = sev_platform_init(&args);
-	if (rc)
-		dev_err(sev->dev, "SEV: failed to INIT error %#x, rc %d\n",
-			args.error, rc);
-
-	dev_info(sev->dev, "SEV%s API:%d.%d build:%d\n", sev->snp_initialized ?
-		"-SNP" : "", sev->api_major, sev->api_minor, sev->build);
-
 	return;
 
 err:
@@ -2577,7 +2565,4 @@ void sev_pci_exit(void)
 
 	if (!sev)
 		return;
-
-	sev_firmware_shutdown(sev);
-
 }

---

## [9] Dionna Amalie Glaze — 2024-12-10
*Subject: Re: [PATCH 1/7] crypto: ccp: Move dev_info/err messages for SEV/SNP initialization*

>
>  static int _sev_platform_init_locked(struct sev_platform_init_args *args)

You don't necessarily continue to INIT SEV if args->probe &&
!psp_init_on_probe, so this may be misleading.

>         }
>

---

## [10] Tom Lendacky — 2024-12-10
*Subject: Re: [PATCH 3/7] crypto: ccp: Reset TMR size at SNP Shutdown*

On 12/9/24 17:25, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

I think a bit more info here about why this is (now) needed would be good.

Thanks,
Tom

> 
> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>

---

## [11] Tom Lendacky — 2024-12-10
*Subject: Re: [PATCH 4/7] crypto: ccp: Register SNP panic notifier only if SNP
 is enabled*

On 12/9/24 17:25, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Talk about why you are making the change.

Thanks,
Tom

> 
> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>

---
