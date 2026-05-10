---
title: 'Move initializing SEV/SNP functionality to KVM'
date: 2025-01-03
last_reply: 2025-01-15
message_count: 31
participants: ['Ashish Kalra', 'Dionna Amalie Glaze', 'Alexey Kardashevskiy', 'Tom Lendacky', 'Sean Christopherson']
---

## [1] Ashish Kalra — 2025-01-03

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

To support SEV firmware hotloading, SEV Shutdown will be done explicitly
prior to DOWNLOAD_FIRMWARE_EX and SEV INIT post it to work with the
requirement of SEV to be in UNINIT state for DOWNLOAD_FIRMWARE_EX.
NOTE: SEV firmware hotloading will only be supported if there are no
active SEV/SEV-ES guests. 

v3:
- Move back to do both SNP and SEV platform initialization at KVM module
load time instead of SEV initialization on demand at SEV/SEV-ES VM launch
to prevent breaking QEMU which has a check for SEV to be initialized 
prior to launching SEV/SEV-ES VMs. 
- As both SNP and SEV platform initialization and shutdown is now done at
KVM module load and unload time remove patches for separate SEV and SNP
platform initialization and shutdown.

v2:
- Added support for separate SEV and SNP platform initalization, while
SNP platform initialization is done at KVM module load time, SEV 
platform initialization is done on demand at SEV/SEV-ES VM launch.
- Added support for separate SEV and SNP platform shutdown, both 
SEV and SNP shutdown done at KVM module unload time, only SEV
shutdown down when all SEV/SEV-ES VMs have been destroyed, this
allows SEV firmware hotloading support anytime during system lifetime.
- Updated commit messages for couple of patches in the series with
reference to the feedback received on v1 patches.

Ashish Kalra (7):
  crypto: ccp: Move dev_info/err messages for SEV/SNP initialization
  crypto: ccp: Fix implicit SEV/SNP init and shutdown in ioctls
  crypto: ccp: Reset TMR size at SNP Shutdown
  crypto: ccp: Register SNP panic notifier only if SNP is enabled
  crypto: ccp: Add new SEV/SNP platform shutdown API
  KVM: SVM: Add support to initialize SEV/SNP functionality in KVM
  crypto: ccp: Move SEV/SNP Platform initialization to KVM

 arch/x86/kvm/svm/sev.c       |  15 ++-
 drivers/crypto/ccp/sev-dev.c | 239 +++++++++++++++++++++++++----------
 include/linux/psp-sev.h      |   7 +-
 3 files changed, 190 insertions(+), 71 deletions(-)

---

## [2] Ashish Kalra — 2025-01-03
*Subject: [PATCH v3 1/7] crypto: ccp: Move dev_info/err messages for SEV/SNP initialization*

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
 drivers/crypto/ccp/sev-dev.c | 23 ++++++++++++++++++-----
 1 file changed, 18 insertions(+), 5 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index af018afd9cd7..1c1c33d3ed9a 100644
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

---

## [3] Ashish Kalra — 2025-01-03
*Subject: [PATCH v3 2/7] crypto: ccp: Fix implicit SEV/SNP init and shutdown in ioctls*

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
index 1c1c33d3ed9a..0ec2e8191583 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1454,7 +1454,8 @@ static int sev_ioctl_do_platform_status(struct sev_issue_cmd *argp)
 static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	int rc;
+	bool shutdown_required = false;
+	int rc, ret, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1463,19 +1464,30 @@ static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool wr
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
@@ -1506,6 +1518,7 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 		ret = __sev_platform_init_locked(&argp->error);
 		if (ret)
 			goto e_free_blob;
+		shutdown_required = true;
 	}
 
 	ret = __sev_do_cmd_locked(SEV_CMD_PEK_CSR, &data, &argp->error);
@@ -1524,6 +1537,13 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
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
@@ -1739,8 +1759,9 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_pek_cert_import input;
 	struct sev_data_pek_cert_import data;
+	bool shutdown_required = false;
 	void *pek_blob, *oca_blob;
-	int ret;
+	int ret, rc, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1772,11 +1793,19 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
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
@@ -1893,17 +1922,8 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
@@ -1944,6 +1964,16 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
@@ -1970,6 +2000,13 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
@@ -1979,12 +2016,13 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
@@ -1993,6 +2031,13 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 
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
@@ -2021,6 +2066,13 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
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
@@ -2029,21 +2081,38 @@ static int sev_ioctl_do_snp_commit(struct sev_issue_cmd *argp)
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
@@ -2052,17 +2121,34 @@ static int sev_ioctl_do_snp_set_config(struct sev_issue_cmd *argp, bool writable
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
@@ -2081,8 +2167,23 @@ static int sev_ioctl_do_snp_vlek_load(struct sev_issue_cmd *argp, bool writable)
 
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

## [4] Ashish Kalra — 2025-01-03
*Subject: [PATCH v3 3/7] crypto: ccp: Reset TMR size at SNP Shutdown*

From: Ashish Kalra <ashish.kalra@amd.com>

When SEV-SNP is enabled the TMR needs to be 2MB aligned and 2MB sized,
ensure that TMR size is reset back to default when SNP is shutdown as
SNP initialization and shutdown as part of some SNP ioctls may leave
TMR size modified and cause subsequent SEV only initialization to fail.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 3 +++
 1 file changed, 3 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 0ec2e8191583..9632a9a5c92e 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1751,6 +1751,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	sev->snp_initialized = false;
 	dev_dbg(sev->dev, "SEV-SNP firmware shutdown\n");
 
+	/* Reset TMR size back to default */
+	sev_es_tmr_size = SEV_TMR_SIZE;
+
 	return ret;
 }

---

## [5] Ashish Kalra — 2025-01-03
*Subject: [PATCH v3 4/7] crypto: ccp: Register SNP panic notifier only if SNP is enabled*

From: Ashish Kalra <ashish.kalra@amd.com>

Register the SNP panic notifier if and only if SNP is actually
initialized and deregistering the notifier when shutting down
SNP in PSP driver when KVM module is unloaded.

Currently the SNP panic notifier is being registered
irrespective of SNP being enabled/initialized and with this
change the SNP panic notifier is registered only if SNP
support is enabled and initialized.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 21 +++++++++++++--------
 1 file changed, 13 insertions(+), 8 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 9632a9a5c92e..7c15dec55f58 100644
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
@@ -1751,6 +1761,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	sev->snp_initialized = false;
 	dev_dbg(sev->dev, "SEV-SNP firmware shutdown\n");
 
+	atomic_notifier_chain_unregister(&panic_notifier_list,
+					 &snp_panic_notifier);
+
 	/* Reset TMR size back to default */
 	sev_es_tmr_size = SEV_TMR_SIZE;
 
@@ -2490,10 +2503,6 @@ static int snp_shutdown_on_panic(struct notifier_block *nb,
 	return NOTIFY_DONE;
 }
 
-static struct notifier_block snp_panic_notifier = {
-	.notifier_call = snp_shutdown_on_panic,
-};
-
 int sev_issue_cmd_external_user(struct file *filep, unsigned int cmd,
 				void *data, int *error)
 {
@@ -2542,8 +2551,6 @@ void sev_pci_init(void)
 	dev_info(sev->dev, "SEV%s API:%d.%d build:%d\n", sev->snp_initialized ?
 		"-SNP" : "", sev->api_major, sev->api_minor, sev->build);
 
-	atomic_notifier_chain_register(&panic_notifier_list,
-				       &snp_panic_notifier);
 	return;
 
 err:
@@ -2561,6 +2568,4 @@ void sev_pci_exit(void)
 
 	sev_firmware_shutdown(sev);
 
-	atomic_notifier_chain_unregister(&panic_notifier_list,
-					 &snp_panic_notifier);
 }

---

## [6] Ashish Kalra — 2025-01-03
*Subject: [PATCH v3 5/7] crypto: ccp: Add new SEV/SNP platform shutdown API*

From: Ashish Kalra <ashish.kalra@amd.com>

Add new API interface to do SEV/SNP platform shutdown when KVM module
is unloaded.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 13 +++++++++++++
 include/linux/psp-sev.h      |  3 +++
 2 files changed, 16 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 7c15dec55f58..1ad66c3451fb 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2469,6 +2469,19 @@ static void sev_firmware_shutdown(struct sev_device *sev)
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

## [7] Ashish Kalra — 2025-01-03
*Subject: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP functionality in KVM*

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
 arch/x86/kvm/svm/sev.c | 15 ++++++++++++++-
 1 file changed, 14 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 943bd074a5d3..0dc8294582c6 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -444,7 +444,6 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	if (ret)
 		goto e_no_asid;
 
-	init_args.probe = false;
 	ret = sev_platform_init(&init_args);
 	if (ret)
 		goto e_free;
@@ -2953,6 +2952,7 @@ void __init sev_set_cpu_caps(void)
 void __init sev_hardware_setup(void)
 {
 	unsigned int eax, ebx, ecx, edx, sev_asid_count, sev_es_asid_count;
+	struct sev_platform_init_args init_args = {0};
 	bool sev_snp_supported = false;
 	bool sev_es_supported = false;
 	bool sev_supported = false;
@@ -3069,6 +3069,16 @@ void __init sev_hardware_setup(void)
 	sev_supported_vmsa_features = 0;
 	if (sev_es_debug_swap_enabled)
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
+
+	if (!sev_enabled)
+		return;
+
+	/*
+	 * NOTE: Always do SNP INIT regardless of sev_snp_supported
+	 * as SNP INIT has to be done to launch legacy SEV/SEV-ES
+	 * VMs in case SNP is enabled system-wide.
+	 */
+	sev_platform_init(&init_args);
 }
 
 void sev_hardware_unsetup(void)
@@ -3084,6 +3094,9 @@ void sev_hardware_unsetup(void)
 
 	misc_cg_set_capacity(MISC_CG_RES_SEV, 0);
 	misc_cg_set_capacity(MISC_CG_RES_SEV_ES, 0);
+
+	/* Do SEV and SNP Shutdown */
+	sev_platform_shutdown();
 }
 
 int sev_cpu_init(struct svm_cpu_data *sd)

---

## [8] Ashish Kalra — 2025-01-03
*Subject: [PATCH v3 7/7] crypto: ccp: Move SEV/SNP Platform initialization to KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

SNP initialization is forced during PSP driver probe purely because SNP
can't be initialized if VMs are running.  But the only in-tree user of
SEV/SNP functionality is KVM, and KVM depends on PSP driver for the same.
Forcing SEV/SNP initialization because a hypervisor could be running
legacy non-confidential VMs make no sense.

This patch removes SEV/SNP initialization from the PSP driver probe
time and moves the requirement to initialize SEV/SNP functionality
to KVM if it wants to use SEV/SNP.

Remove the psp_init_on_probe parameter as it not used anymore.
Remove the probe field from struct sev_platform_init_args as it is
not used anymore.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 30 +-----------------------------
 include/linux/psp-sev.h      |  4 ----
 2 files changed, 1 insertion(+), 33 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 1ad66c3451fb..55a8dd762b67 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -69,10 +69,6 @@ static char *init_ex_path;
 module_param(init_ex_path, charp, 0444);
 MODULE_PARM_DESC(init_ex_path, " Path for INIT_EX data; if set try INIT_EX");
 
-static bool psp_init_on_probe = true;
-module_param(psp_init_on_probe, bool, 0444);
-MODULE_PARM_DESC(psp_init_on_probe, "  if true, the PSP will be initialized on module init. Else the PSP will be initialized on the first command requiring it");
-
 MODULE_FIRMWARE("amd/amd_sev_fam17h_model0xh.sbin"); /* 1st gen EPYC */
 MODULE_FIRMWARE("amd/amd_sev_fam17h_model3xh.sbin"); /* 2nd gen EPYC */
 MODULE_FIRMWARE("amd/amd_sev_fam19h_model0xh.sbin"); /* 3rd gen EPYC */
@@ -1342,24 +1338,15 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	if (sev->state == SEV_STATE_INIT)
 		return 0;
 
-	/*
-	 * Legacy guests cannot be running while SNP_INIT(_EX) is executing,
-	 * so perform SEV-SNP initialization at probe time.
-	 */
 	rc = __sev_snp_init_locked(&args->error);
 	if (rc && rc != -ENODEV) {
 		/*
 		 * Don't abort the probe if SNP INIT failed,
 		 * continue to initialize the legacy SEV firmware.
 		 */
-		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
-			rc, args->error);
+		dev_err(sev->dev, "SEV-SNP: failed to INIT, continue SEV INIT\n");
 	}
 
-	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */
-	if (args->probe && !psp_init_on_probe)
-		return 0;
-
 	return __sev_platform_init_locked(&args->error);
 }
 
@@ -2529,9 +2516,7 @@ EXPORT_SYMBOL_GPL(sev_issue_cmd_external_user);
 void sev_pci_init(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	struct sev_platform_init_args args = {0};
 	u8 api_major, api_minor, build;
-	int rc;
 
 	if (!sev)
 		return;
@@ -2554,16 +2539,6 @@ void sev_pci_init(void)
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
@@ -2578,7 +2553,4 @@ void sev_pci_exit(void)
 
 	if (!sev)
 		return;
-
-	sev_firmware_shutdown(sev);
-
 }
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index fea20fbe2a8a..b0884dbe7d33 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -794,13 +794,9 @@ struct sev_data_snp_shutdown_ex {
  * struct sev_platform_init_args
  *
  * @error: SEV firmware error code
- * @probe: True if this is being called as part of CCP module probe, which
- *  will defer SEV_INIT/SEV_INIT_EX firmware initialization until needed
- *  unless psp_init_on_probe module param is set
  */
 struct sev_platform_init_args {
 	int error;
-	bool probe;
 };
 
 /**

---

## [9] Dionna Amalie Glaze — 2025-01-06
*Subject: Re: [PATCH v3 1/7] crypto: ccp: Move dev_info/err messages for
 SEV/SNP initialization*

On Fri, Jan 3, 2025 at 11:59 AM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>

I don't see any "remove" code in this patch.

---

## [10] Dionna Amalie Glaze — 2025-01-06
*Subject: Re: [PATCH v3 2/7] crypto: ccp: Fix implicit SEV/SNP init and
 shutdown in ioctls*

On Fri, Jan 3, 2025 at 12:00 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>

The subject includes "Fix" but has no "Fixes" tag in the commit message.

> Modify the behavior of implicit SEV initialization in some of the
> SEV ioctls to do both SEV initialization and shutdown and adds

It would be helpful to update the description with the state machine
you're trying to maintain implicitly.
I think that this changes the uapi contract as well, so I think you
need to update the documentation.

You have SEV shutdown on error for platform maintenance ioctls here,
which already have implicit init.
pdh_export gets an init if not in the init state, which wasn't already
implicit because there's a wrinkle WRT the writability permission.

snp_platform_status, snp_config, vlek_load, snp_commit now should be
callable any time, not just when KVM has initialized SNP? If there's a
caveat to the platform status, the docs need to reflect it.
I don't know how SNP_COMMIT makes sense as having an implicit
init/shutdown unless you're using it as SET_CONFIG, but I suppose it
doesn't hurt?

> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
> ---


--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [11] Dionna Amalie Glaze — 2025-01-06
*Subject: Re: [PATCH v3 4/7] crypto: ccp: Register SNP panic notifier only if
 SNP is enabled*

On Fri, Jan 3, 2025 at 12:01 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>

---

## [12] Dionna Amalie Glaze — 2025-01-06
*Subject: Re: [PATCH v3 5/7] crypto: ccp: Add new SEV/SNP platform shutdown API*

On Fri, Jan 3, 2025 at 12:01 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Dionna Glaze <dionnaglaze@google.com>

---

## [13] Kalra, Ashish — 2025-01-06
*Subject: Re: [PATCH v3 1/7] crypto: ccp: Move dev_info/err messages for
 SEV/SNP initialization*

On 1/6/2025 11:17 AM, Dionna Amalie Glaze wrote:
> On Fri, Jan 3, 2025 at 11:59 AM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>>

Actually, the removal code is in the final patch after the platform initialization
stuff has been moved to KVM, and this is more of a pre-patch to move dev_info/dev_err
messages related to SEV/SNP initialization inside __sev_platform_init_locked()
and __sev_snp_init_locked(), so i will drop the remove" from commit message and 
keep only the move description as part of the commit message.

Thanks,
Ashish

---

## [14] Kalra, Ashish — 2025-01-06
*Subject: Re: [PATCH v3 2/7] crypto: ccp: Fix implicit SEV/SNP init and
 shutdown in ioctls*

On 1/6/2025 12:01 PM, Dionna Amalie Glaze wrote:
> On Fri, Jan 3, 2025 at 12:00 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>>

I will change the commit message to be more appropriate, it is not really
a fix but a change to either add a SEV shutdown to some SEV ioctls and
add SNP init and shutdown to some SNP ioctls.
 
>> Modify the behavior of implicit SEV initialization in some of the
>> SEV ioctls to do both SEV initialization and shutdown and adds
How does this change the uapi contract, as the SEV init and shutdown
is going to happen as a sequence and the platform state is going to 
be consistent before and after the ioctl, the next ioctl if required
will reissue SEV init.

> You have SEV shutdown on error for platform maintenance ioctls here,
> which already have implicit init.

This patch only adds SEV shutdown to already implied init code as part
of some of these SEV ioctls. 

If you see the behavior prior to this patch, SEV has always been initialized
before these ioctls as SEV initialization is done as part of PSP module
load, but now with SEV initialization being moved to KVM module load instead
of PSP driver load, the implied SEV INIT actually makes sense and gets used
and additionally we need to maintain SEV platform state consistency
before and after the ioctl which needs the SEV shutdown to be done after
the firmware call.
 
> snp_platform_status, snp_config, vlek_load, snp_commit now should be
> callable any time, not just when KVM has initialized SNP? If there's a

Yes, and that is what this code is allowing, to call snp_platform_status,
snp_config, vlek_load and snp_commit without KVM having initialized SNP.

If you see the behavior prior to this patch, SNP has always been initialized
before these ioctls as SNP initialization is done as part of PSP module
load, therefore, to keep a consistent behavior, SNP init is being done here 
implicitly as part of these ioctls and then SNP shutdown before returning
from the ioctl to maintain the consistent platform state before and
after the ioctl. 

Additionally looking at the SNP firmware API specs, SNP_CONFIG needs
SNP to be in INIT state. 

Thanks,
Ashish

>> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
>> ---

---

## [15] Alexey Kardashevskiy — 2025-01-07
*Subject: Re: [PATCH v3 2/7] crypto: ccp: Fix implicit SEV/SNP init and
 shutdown in ioctls*

On 4/1/25 07:00, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

same comment as in v2:

goto e_free_cert, not return, otherwise leaks memory.



> +		ret = __sev_platform_init_locked(&argp->error);
> +		if (ret)

same comment as in v2:


It is the same template 8 (?) times, I'd declare rc and error inside the 
"if (shutdown_required)" scope or even drop them and error messages as 
__sev_snp_shutdown_locked() prints dev_err() anyway.

if (shutdown_required)
     __sev_snp_shutdown_locked(&error, false);

and that's it. Thanks,

> +cleanup:
>   	kfree(blob);

---

## [16] Tom Lendacky — 2025-01-07
*Subject: Re: [PATCH v3 1/7] crypto: ccp: Move dev_info/err messages for
 SEV/SNP initialization*

On 1/3/25 13:59, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

This doesn't take into account Alexey's comment about which command
failed. I agree with him and you shouldn't use a common exit point.

Thanks,
Tom

> 
> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>

---

## [17] Tom Lendacky — 2025-01-07
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 1/3/25 14:01, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Actually, you're not removing it, yet...

> move it to KVM module load time so that KVM can do SEV/SNP platform
> initialization explicitly if it actually wants to use SEV/SNP

Will this cause issues if KVM is built-in and INIT_EX is being used
(init_ex_path ccp parameter)? The probe parameter is used for
initialization done before the filesystem is available.

Thanks,
Tom

>  	bool sev_snp_supported = false;
>  	bool sev_es_supported = false;

---

## [18] Kalra, Ashish — 2025-01-07
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 1/7/2025 10:42 AM, Tom Lendacky wrote:
> On 1/3/25 14:01, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

Yes, this will cause issues if KVM is builtin and INIT_EX is being used,
but my question is how will INIT_EX be used when we move SEV INIT
to KVM ?

If we continue to use the probe field here and also continue to support
psp_init_on_probe module parameter for CCP, how will SEV INIT_EX be
invoked ? 

How is SEV INIT_EX invoked in PSP driver currently if psp_init_on_probe
parameter is set to false ?

The KVM path to invoke sev_platform_init() when a SEV VM is being launched 
cannot be used because QEMU checks for SEV to be initialized before
invoking this code path to launch the guest.

Thanks,
Ashish

> Thanks,
> Tom

---

## [19] Kalra, Ashish — 2025-01-07
*Subject: Re: [PATCH v3 2/7] crypto: ccp: Fix implicit SEV/SNP init and
 shutdown in ioctls*

On 1/6/2025 9:29 PM, Alexey Kardashevskiy wrote:
> On 4/1/25 07:00, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>
 
Yes, makes sense to use the dev_err() in __sev_snp_shutdown_locked() as that is the whole purpose of the first patch in this series, but will
still have to declare error as a local as we can't use argp->error here.

Thanks, 
Ashish

> 
>> +cleanup:

---

## [20] Kalra, Ashish — 2025-01-07
*Subject: Re: [PATCH v3 2/7] crypto: ccp: Fix implicit SEV/SNP init and
 shutdown in ioctls*

On 1/6/2025 5:48 PM, Kalra, Ashish wrote:
> 
> 

Also note that it is important to do SEV Shutdown here with the SEV/SNP
init stuff moving to KVM, if we do an implicit SEV INIT here as part of
the SEV ioctls and do not follow it with SEV Shutdown then SEV will
remain in INIT state and then a future SNP INIT in KVM module load
will fail.

This was different earlier as SNP was initialized first when CCP
module is loaded, so SNP would already have been initialized when
the above SEV ioctls are issued.

Thanks,
Ashish

> 
> This patch only adds SEV shutdown to already implied init code as part

---

## [21] Kalra, Ashish — 2025-01-07
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

+Adding Peter

On 1/7/2025 12:34 PM, Kalra, Ashish wrote:
> 
> 

Peter, I believe that you have a different path to test SEV INIT_EX which 
won't be affected by this QEMU check. 

I will add back the probe field and psp_init_on_probe parameter for the 
CCP module, but i will need your help to test and verify if SEV INIT_EX
works with this patch-set.

Thanks,
Ashish

> 
>> Thanks,

---

## [22] Tom Lendacky — 2025-01-08
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 1/7/25 12:34, Kalra, Ashish wrote:
> On 1/7/2025 10:42 AM, Tom Lendacky wrote:
>> On 1/3/25 14:01, Ashish Kalra wrote:

Qemu only requires that for an SEV-ES guest. I was able to use the
init_ex_path=/root/... and psp_init_on_probe=0 to successfully delay SEV
INIT_EX and launch an SEV guest.

Thanks,
Tom

> 
> Thanks,

---

## [23] Kalra, Ashish — 2025-01-08
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 1/8/2025 11:22 AM, Tom Lendacky wrote:
> On 1/7/25 12:34, Kalra, Ashish wrote:
>> On 1/7/2025 10:42 AM, Tom Lendacky wrote:

Thanks Tom, i will make sure that we continue to support both the probe
field and psp_init_on_probe module parameter for CCP modules as part of v4.

>>
>>> Thanks,

---

## [24] Kalra, Ashish — 2025-01-10
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

Hello All,

On 1/8/2025 6:27 PM, Kalra, Ashish wrote:
> 
> 

It looks like i have hit a serious blocker issue with this approach of moving
SEV/SNP initialization to KVM module load time. 

While testing with kvm_amd and PSP driver built-in, it looks like kvm_amd
driver is being loaded/initialized before PSP driver is loaded, and that
causes sev_platform_init() call from sev_hardware_setup(kvm_amd) to fail:

[   10.717898] kvm_amd: TSC scaling supported
[   10.722470] kvm_amd: Nested Virtualization enabled
[   10.727816] kvm_amd: Nested Paging enabled
[   10.732388] kvm_amd: LBR virtualization supported
[   10.737639] kvm_amd: SEV enabled (ASIDs 100 - 509)
[   10.742985] kvm_amd: SEV-ES enabled (ASIDs 1 - 99)
[   10.748333] kvm_amd: SEV-SNP enabled (ASIDs 1 - 99)
[   10.753768] PSP driver not init                        <<<---- sev_platform_init() returns failure as PSP driver is still not initialized
[   10.757563] kvm_amd: Virtual VMLOAD VMSAVE supported
[   10.763124] kvm_amd: Virtual GIF supported
...
...
[   12.514857] ccp 0000:23:00.1: enabling device (0000 -> 0002)
[   12.521691] ccp 0000:23:00.1: no command queues available
[   12.527991] ccp 0000:23:00.1: sev enabled
[   12.532592] ccp 0000:23:00.1: psp enabled
[   12.537382] ccp 0000:a2:00.1: enabling device (0000 -> 0002)
[   12.544389] ccp 0000:a2:00.1: no command queues available
[   12.550627] ccp 0000:a2:00.1: psp enabled

depmod -> modules.builtin show kernel/arch/x86/kvm/kvm_amd.ko higher on the list and before kernel/drivers/crypto/ccp/ccp.ko

modules.builtin: 
kernel/arch/x86/kvm/kvm.ko
kernel/arch/x86/kvm/kvm-amd.ko
...
...
kernel/drivers/crypto/ccp/ccp.ko

I believe that the modules which are compiled first get called first and it looks like that the only way to change the order for
builtin modules is by changing which makefiles get compiled first ?

Is there a way to change the load order of built-in modules and/or change dependency of built-in modules ?

As of now, this looks like to be a blocker for moving SEV/SNP init to KVM module load time as this approach will not
work if kvm_amd is built-in. 

Thanks,
Ashish

>>>>
>>>>>  	bool sev_snp_supported = false;

---

## [25] Sean Christopherson — 2025-01-10
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Fri, Jan 10, 2025, Ashish Kalra wrote:
> It looks like i have hit a serious blocker issue with this approach of moving
> SEV/SNP initialization to KVM module load time. 

The least awful option I know of would be to have the PSP use a higher priority
initcall type so that it runs before the standard initcalls.  When compiled as
a module, all initcall types are #defined to module_init.

E.g. this should work, /cross fingers

diff --git a/drivers/crypto/ccp/sp-dev.c b/drivers/crypto/ccp/sp-dev.c
index 7eb3e4668286..02c49fbf6198 100644
--- a/drivers/crypto/ccp/sp-dev.c
+++ b/drivers/crypto/ccp/sp-dev.c
@@ -295,5 +295,6 @@ static void __exit sp_mod_exit(void)
 #endif
 }
 
-module_init(sp_mod_init);
+/* The PSP needs to be initialized before dependent modules, e.g. before KVM. */
+subsys_initcall(sp_mod_init);
 module_exit(sp_mod_exit);

---

## [26] Dionna Amalie Glaze — 2025-01-10
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Fri, Jan 10, 2025 at 4:40 PM Sean Christopherson <seanjc@google.com> wrote:
>
> On Fri, Jan 10, 2025, Ashish Kalra wrote:

I was 2 seconds from clicking send with this exact suggestion. There
are examples in 'drivers/' that use subsys_initcall / module_exit
pairs.

>  module_exit(sp_mod_exit);

---

## [27] Sean Christopherson — 2025-01-10
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Fri, Jan 10, 2025, Dionna Amalie Glaze wrote:
> On Fri, Jan 10, 2025 at 4:40 PM Sean Christopherson <seanjc@google.com> wrote:
> > > Is there a way to change the load order of built-in modules and/or change

Ha!  For once, I wasn't too slow due to writing an overly verbose message :-)

---

## [28] Kalra, Ashish — 2025-01-13
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 1/10/2025 6:40 PM, Sean Christopherson wrote:
> On Fri, Jan 10, 2025, Ashish Kalra wrote:
>> It looks like i have hit a serious blocker issue with this approach of moving

Thanks for the suggestion, but there are actually two major issues here: 

With the above change, PSP driver initialization fails as following:

...
[    7.274005] pci 0000:20:08.1: bridge window [mem 0xf6200000-0xf64fffff]: not claimed; can't enable device
[    7.277945] pci 0000:20:08.1: Error enabling bridge (-22), continuing
[    7.281947] ccp 0000:23:00.1: BAR 2 [mem 0xf6300000-0xf63fffff]: not claimed; can't enable device
[    7.285945] ccp 0000:23:00.1: pcim_enable_device failed (-22)
[    7.289943] ccp 0000:23:00.1: initialization failed
[    7.293944] ccp 0000:23:00.1: probe with driver ccp failed with error -22
[    7.301981] pci 0000:a0:08.1: bridge window [mem 0xb6200000-0xb63fffff]: not claimed; can't enable device
[    7.313956] pci 0000:a0:08.1: Error enabling bridge (-22), continuing
[    7.321947] ccp 0000:a2:00.1: BAR 2 [mem 0xb6200000-0xb62fffff]: not claimed; can't enable device
[    7.329945] ccp 0000:a2:00.1: pcim_enable_device failed (-22)
[    7.337943] ccp 0000:a2:00.1: initialization failed
[    7.341946] ccp 0000:a2:00.1: probe with driver ccp failed with error -22
...

It looks as PCI bus resource allocation is still not done, hence PSP driver cannot be enabled as early as subsys_initcall,
it can be initialized probably via device_initcall(), but then that will be too late as kvm_amd would have been initialized before that.

Additionally, it looks like that there is an issue with SNP host support being enabled with kvm_amd module being built-in:

SNP host support is enabled in snp_rmptable_init() in arch/x86/virt/svm/sev.c, which is invoked as a device_initcall(). 
Here device_initcall() is used as snp_rmptable_init() expects AMD IOMMU SNP support to be enabled prior to it and the AMD IOMMU
driver is initialized after PCI bus enumeration. 

Now, if kvm_amd module is built-in, it gets initialized before SNP host support is enabled in snp_rmptable_init() :

[   10.131811] kvm_amd: TSC scaling supported
[   10.136384] kvm_amd: Nested Virtualization enabled
[   10.141734] kvm_amd: Nested Paging enabled
[   10.146304] kvm_amd: LBR virtualization supported
[   10.151557] kvm_amd: SEV enabled (ASIDs 100 - 509)
[   10.156905] kvm_amd: SEV-ES enabled (ASIDs 1 - 99)
[   10.162256] kvm_amd: SEV-SNP enabled (ASIDs 1 - 99)
[   10.167701] PSP driver not init
[   10.171508] kvm_amd: Virtual VMLOAD VMSAVE supported
[   10.177052] kvm_amd: Virtual GIF supported
...
...
[   10.201648] kvm_amd: in svm_enable_virtualization_cpu WRMSR VM_HSAVE_PA non-zero

And then svm_x86_ops->enable_virtualization_cpu() (svm_enable_virtualization_cpu) programs MSR_VM_HSAVE_PA as following:
wrmsrl(MSR_VM_HSAVE_PA, sd->save_area_pa);

So VM_HSAVE_PA is non-zero before SNP support is enabled on all CPUs. 

snp_rmptable_init() gets invoked after svm_enable_virtualization_cpu() as following :
...
[   11.256138] kvm_amd: in svm_enable_virtualization_cpu WRMSR VM_HSAVE_PA non-zero
...
[   11.264918] SEV-SNP: in snp_rmptable_init

This triggers a #GP exception in snp_rmptable_init() when snp_enable() is invoked to set SNP_EN in SYSCFG MSR: 

[   11.294289] unchecked MSR access error: WRMSR to 0xc0010010 (tried to write 0x0000000003fc0000) at rIP: 0xffffffffaf5d5c28 (native_write_msr+0x8/0x30)
...
[   11.294404] Call Trace:
[   11.294482]  <IRQ>
[   11.294513]  ? show_stack_regs+0x26/0x30
[   11.294522]  ? ex_handler_msr+0x10f/0x180
[   11.294529]  ? search_extable+0x2b/0x40
[   11.294538]  ? fixup_exception+0x2dd/0x340
[   11.294542]  ? exc_general_protection+0x14f/0x440
[   11.294550]  ? asm_exc_general_protection+0x2b/0x30
[   11.294557]  ? __pfx_snp_enable+0x10/0x10
[   11.294567]  ? native_write_msr+0x8/0x30
[   11.294570]  ? __snp_enable+0x5d/0x70
[   11.294575]  snp_enable+0x19/0x20
[   11.294578]  __flush_smp_call_function_queue+0x9c/0x3a0
[   11.294586]  generic_smp_call_function_single_interrupt+0x17/0x20
[   11.294589]  __sysvec_call_function+0x20/0x90
[   11.294596]  sysvec_call_function+0x80/0xb0
[   11.294601]  </IRQ>
[   11.294603]  <TASK>
[   11.294605]  asm_sysvec_call_function+0x1f/0x30
...
[   11.294631]  arch_cpu_idle+0xd/0x20
[   11.294633]  default_idle_call+0x34/0xd0
[   11.294636]  do_idle+0x1f1/0x230
[   11.294643]  ? complete+0x71/0x80
[   11.294649]  cpu_startup_entry+0x30/0x40
[   11.294652]  start_secondary+0x12d/0x160
[   11.294655]  common_startup_64+0x13e/0x141
[   11.294662]  </TASK>

This #GP exception is getting triggered due to the following errata for AMD family 19h Models 10h-1Fh Processors:

Processor may generate spurious #GP(0) Exception on WRMSR instruction:
Description:
The Processor will generate a spurious #GP(0) Exception on a WRMSR instruction if the following conditions are all met:
- the target of the WRMSR is a SYSCFG register.
- the write changes the value of SYSCFG.SNPEn from 0 to 1.
- One of the threads that share the physical core has a non-zero value in the VM_HSAVE_PA MSR.

The suggested workaround is when enabling SNP, program VM_HSAVE_PA to 0h on both threads that share a physical core before setting SYSCFG.SNPEn

The document being referred to above:
https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/revision-guides/57095-PUB_1_01.pdf

Therefore, with kvm_amd module being built-in, KVM/SVM initialization happens before Host SNP is enabled and this SVM initialization 
sets VM_HSAVE_PA to non-zero, which then triggers this #GP when SYSCFG.SNPEn is being set and this will subsequently cause SNP_INIT(_EX) to fail
with INVALID_CONFIG error as SYSCFG[SnpEn] is not set on all CPUs.

So it looks like the current SNP host enabling code and effectively SNP is broken with respect to the KVM module being built-in.

Essentially SNP host enabling code should be invoked before KVM initialization, which is currently not the case when KVM is built-in.

Additionally, the PSP driver probably needs to be initialized at device_initcall level if it is built-in, but that is much later than KVM
module initialization, therefore, that is blocker for moving SEV/SNP initialization to KVM module load time instead of PSP module probe time.
Do note that i have verified and tested that PSP module initialization works when invoked as a device_initcall(). 

Thanks,
Ashish

---

## [29] Kalra, Ashish — 2025-01-14
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 1/13/2025 9:03 AM, Kalra, Ashish wrote:
> 
> On 1/10/2025 6:40 PM, Sean Christopherson wrote:

As a follow-up to the above issues, i have an important question: 

Do we really need kvm_amd module to be built-in for SEV/SNP support ?

Is there any usage case/scenario where the kvm_amd module needs to be built-in for SEV/SNP support ?

If we can have a requirement that kvm_amd will always be loaded as a module (for SEV/SNP usage case), then it automatically
fixes the above two issues & additionally we can continue on this approach to move SEV/SNP initialization stuff to KVM from
the PSP driver.

Tom and i had a discussion about it and we realized as so far no one has reported this issue of SNP support being broken with respect to
kvm_amd module being built-in (from the time SNP support has gone upstream), it looks like no one is currently using kvm_amd module being
built-in for SNP ?

Looking for feedback/comments on the above.

Thanks,
Ashish

---

## [30] Sean Christopherson — 2025-01-14
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Tue, Jan 14, 2025, Ashish Kalra wrote:
> On 1/13/2025 9:03 AM, Kalra, Ashish wrote:
> > SNP host support is enabled in snp_rmptable_init() in

Ugh.  So. Many. Dependencies.

That's a kernel bug, full stop.  RMP initialization very obviously is not device
initialization.

Why isn't snp_rmptable_init() called from mem_encrypt_init()?  AFAICT,
arch_cpu_finalize_init() is called after IOMMU initialziation.  And if that
doesn't work, hack it into arch_post_acpi_subsys_init().  Using device_initcall()
to initialization the RMP is insane, IMO.

> > Additionally, the PSP driver probably needs to be initialized at
> > device_initcall level if it is built-in, but that is much later than KVM

Yes.

> Is there any usage case/scenario where the kvm_amd module needs to be
> built-in for SEV/SNP support ?

Don't care.  I am 100% against setting a precedent of tying features to KVM
being a module or not, especially since this is a solvable problem.

Ideally, the initcall infrastructure would let modules express dependencies, but
I can appreciate that solving this generically would require a high amount of
complexity.

Having KVM explicitly call into the PSP driver as needed isn't difficult, just
gross.  But for me, it's still far better giving up and requiring everything to
be modules.

E.g.

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 943bd074a5d3..a2ee12e998f0 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2972,6 +2972,16 @@ void __init sev_hardware_setup(void)
            WARN_ON_ONCE(!boot_cpu_has(X86_FEATURE_FLUSHBYASID)))
                goto out;
 
+       /*
+        * The kernel's initcall infrastructure lacks the ability to express
+        * dependencies between initcalls, where as the modules infrastructure
+        * automatically handles dependencies via symbol loading.  Ensure the
+        * PSP SEV driver is initialized before proceeding if KVM is built-in,
+        * as the dependency isn't handled by the initcall infrastructure.
+        */
+       if (IS_BUILTIN(CONFIG_KVM_AMD) && sev_module_init())
+               goto out;
+
        /* Retrieve SEV CPUID information */
        cpuid(0x8000001f, &eax, &ebx, &ecx, &edx);
 
diff --git a/drivers/crypto/ccp/sp-dev.c b/drivers/crypto/ccp/sp-dev.c
index 7eb3e4668286..a0cdc03984cb 100644
--- a/drivers/crypto/ccp/sp-dev.c
+++ b/drivers/crypto/ccp/sp-dev.c
@@ -253,8 +253,12 @@ struct sp_device *sp_get_psp_master_device(void)
 static int __init sp_mod_init(void)
 {
 #ifdef CONFIG_X86
+       static bool initialized;
        int ret;
 
+       if (initialized)
+               return 0;
+
        ret = sp_pci_init();
        if (ret)
                return ret;
@@ -263,6 +267,7 @@ static int __init sp_mod_init(void)
        psp_pci_init();
 #endif
 
+       initialized = true;
        return 0;
 #endif
 
@@ -279,6 +284,13 @@ static int __init sp_mod_init(void)
        return -ENODEV;
 }
 
+#if IS_BUILTIN(CONFIG_KVM_AMD) && IS_ENABLED(CONFIG_KVM_AMD_SEV)
+int __init sev_module_init(void)
+{
+       return sp_mod_init();
+}
+#endif
+
 static void __exit sp_mod_exit(void)
 {
 #ifdef CONFIG_X86
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 903ddfea8585..0138d22b46ac 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -814,6 +814,8 @@ struct sev_data_snp_commit {
 
 #ifdef CONFIG_CRYPTO_DEV_SP_PSP
 
+int __init sev_module_init(void);
+
 /**
  * sev_platform_init - perform SEV INIT command
  *

---

## [31] Kalra, Ashish — 2025-01-15
*Subject: Re: [PATCH v3 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

Hello Sean,

On 1/14/2025 4:31 PM, Sean Christopherson wrote:
> On Tue, Jan 14, 2025, Ashish Kalra wrote:
>> On 1/13/2025 9:03 AM, Kalra, Ashish wrote:

I agree.

> 
> Why isn't snp_rmptable_init() called from mem_encrypt_init()?  AFAICT,

Currently SNP support on IOMMU is enabled via the following code path:

rootfs_initcall(pci_iommu_init) -> pci_iommu_init() -> amd_iommu_init() -> iommu_snp_enable()

And, smp_rmptable_init() needs to be executed after iommu_snp_enable() and that's why we can't 
call snp_rmptable_init() as early as mem_encrypt_init() or post arch ACPI callbacks, etc.

But, there is a patch from the AMD IOMMU team, which calls iommu_snp_enable() early after
early_amd_iommu_init() is executed and this will happen during AMD IOMMU driver initialization
with the following code path:

apic_intr_mode_init() -> enable_IR_x2apic() -> irq_remapping_enable() -> amd_iommu_enable() -> iommu_snp_enable()

This AMD IOMMU driver patch moves SNP enable check before enabling IOMMUs as certain IOMMU buffer
sizes may change depending on SNP support being enabled. 

With this AMD IOMMU driver patch applied, we can now call snp_rmptable_init() early with a subsys_initcall(). 

That fixes the issue with SNP host enabling code being called later than KVM initialization
with kvm_amd module built-in.

I will post a fix for the SNP host support broken with kvm_amd module built-in with this AMD IOMMU driver
patch to call iommu_snp_enable() early and the subsys_initcall() change for snp_rmptable_init() fix
on top of it. 

> 
>>> Additionally, the PSP driver probably needs to be initialized at

I have tested your patch for KVM explicitly calling into the PSP driver and this works well, with this
patch applied as expected PSP driver initialization completes before KVM initialization.

So we can continue with the approach to move SEV/SNP initialization stuff to KVM.
I will add your patch to the v4 of these series i am going to post next.

Thanks,
Ashish

---
