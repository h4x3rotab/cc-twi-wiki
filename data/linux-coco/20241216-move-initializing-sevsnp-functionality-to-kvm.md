---
title: 'Move initializing SEV/SNP functionality to KVM'
date: 2024-12-16
last_reply: 2025-01-07
message_count: 32
participants: ['Ashish Kalra', 'Dionna Amalie Glaze', 'Sean Christopherson', 'Daniel P. Berrangé', 'Alexey Kardashevskiy', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2024-12-16

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

The on-demand SEV initialization support requires a fix in QEMU to 
remove check for SEV initialization to be done prior to launching
SEV/SEV-ES VMs. 
NOTE: With the above fix for QEMU, older QEMU versions will be broken
with respect to launching SEV/SEV-ES VMs with the newer kernel/KVM as
older QEMU versions require SEV initialization to be done before
launching SEV/SEV-ES VMs.

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

Ashish Kalra (9):
  crypto: ccp: Move dev_info/err messages for SEV/SNP initialization
  crypto: ccp: Fix implicit SEV/SNP init and shutdown in ioctls
  crypto: ccp: Reset TMR size at SNP Shutdown
  crypto: ccp: Register SNP panic notifier only if SNP is enabled
  crypto: ccp: Add new SEV platform shutdown API
  crypto: ccp: Add new SEV/SNP platform shutdown API
  crypto: ccp: Add new SEV/SNP platform initialization API
  KVM: SVM: Add support to initialize SEV/SNP functionality in KVM
  crypto: ccp: Move SEV/SNP Platform initialization to KVM

 arch/x86/kvm/svm/sev.c       |  33 +++-
 drivers/crypto/ccp/sev-dev.c | 283 ++++++++++++++++++++++++-----------
 include/linux/psp-sev.h      |  27 +++-
 3 files changed, 248 insertions(+), 95 deletions(-)

---

## [2] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 1/9] crypto: ccp: Move dev_info/err messages for SEV/SNP initialization*

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

## [3] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 2/9] crypto: ccp: Fix implicit SEV/SNP init and shutdown in ioctls*

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

## [4] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 3/9] crypto: ccp: Reset TMR size at SNP Shutdown*

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

## [5] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 4/9] crypto: ccp: Register SNP panic notifier only if SNP is enabled*

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

## [6] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 5/9] crypto: ccp: Add new SEV platform shutdown API*

From: Ashish Kalra <ashish.kalra@amd.com>

Add new API interface to do SEV platform shutdown, separating SNP and SEV
platform shutdown interfaces allow KVM the ability to shutdown SEV when
last SEV VM is destroyed which will assist in SEV firmware hotloading as
SEV must be in UNINIT state for SNP DOWNLOAD_FIRMWARE_EX command.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 12 ++++++++++++
 include/linux/psp-sev.h      |  3 +++
 2 files changed, 15 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 7c15dec55f58..cef0b590ca66 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2469,6 +2469,18 @@ static void sev_firmware_shutdown(struct sev_device *sev)
 	mutex_unlock(&sev_cmd_mutex);
 }
 
+void sev_platform_shutdown(void)
+{
+	if (!psp_master || !psp_master->sev_data)
+		return;
+
+	mutex_lock(&sev_cmd_mutex);
+	__sev_platform_shutdown_locked(NULL);
+	mutex_unlock(&sev_cmd_mutex);
+
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

## [7] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 6/9] crypto: ccp: Add new SEV/SNP platform shutdown API*

From: Ashish Kalra <ashish.kalra@amd.com>

Add new API interface to do SEV/SNP platform shutdown when KVM module
is unloaded. This interface does a full SEV and SNP shutdown.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 13 +++++++++++++
 include/linux/psp-sev.h      |  3 +++
 2 files changed, 16 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index cef0b590ca66..001e7a401a6d 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2481,6 +2481,19 @@ void sev_platform_shutdown(void)
 }
 EXPORT_SYMBOL_GPL(sev_platform_shutdown);
 
+void sev_snp_platform_shutdown(void)
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
+EXPORT_SYMBOL_GPL(sev_snp_platform_shutdown);
+
 void sev_dev_destroy(struct psp_device *psp)
 {
 	struct sev_device *sev = psp->sev_data;
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index fea20fbe2a8a..335b29b31457 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -946,6 +946,7 @@ void *psp_copy_user_blob(u64 uaddr, u32 len);
 void *snp_alloc_firmware_page(gfp_t mask);
 void snp_free_firmware_page(void *addr);
 void sev_platform_shutdown(void);
+void sev_snp_platform_shutdown(void);
 
 #else	/* !CONFIG_CRYPTO_DEV_SP_PSP */
 
@@ -982,6 +983,8 @@ static inline void snp_free_firmware_page(void *addr) { }
 
 static inline void sev_platform_shutdown(void) { }
 
+static inline void sev_snp_platform_shutdown(void) { }
+
 #endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
 
 #endif	/* __PSP_SEV_H__ */

---

## [8] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 7/9] crypto: ccp: Add new SEV/SNP platform initialization API*

From: Ashish Kalra <ashish.kalra@amd.com>

Add new SNP platform initialization API to allow separate SEV and SNP
initialization.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 15 +++++++++++++++
 include/linux/psp-sev.h      | 17 +++++++++++++++++
 2 files changed, 32 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 001e7a401a6d..53c438b2b712 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1375,6 +1375,21 @@ int sev_platform_init(struct sev_platform_init_args *args)
 }
 EXPORT_SYMBOL_GPL(sev_platform_init);
 
+int sev_snp_platform_init(struct sev_platform_init_args *args)
+{
+	int rc;
+
+	if (!psp_master || !psp_master->sev_data)
+		return -ENODEV;
+
+	mutex_lock(&sev_cmd_mutex);
+	rc = __sev_snp_init_locked(&args->error);
+	mutex_unlock(&sev_cmd_mutex);
+
+	return rc;
+}
+EXPORT_SYMBOL_GPL(sev_snp_platform_init);
+
 static int __sev_platform_shutdown_locked(int *error)
 {
 	struct psp_device *psp = psp_master;
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 335b29b31457..e50643aef8a9 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -828,6 +828,21 @@ struct sev_data_snp_commit {
  */
 int sev_platform_init(struct sev_platform_init_args *args);
 
+/**
+ * sev_snp_platform_init - perform SNP INIT command
+ *
+ * @args: struct sev_platform_init_args to pass in arguments
+ *
+ * Returns:
+ * 0 if the SEV successfully processed the command
+ * -%ENODEV    if the SNP support is not enabled
+ * -%ENOMEM    if the SNP range list allocation failed
+ * -%E2BIG     if the HV_Fixed list is too big
+ * -%ETIMEDOUT if the SEV command timed out
+ * -%EIO       if the SEV returned a non-zero return code
+ */
+int sev_snp_platform_init(struct sev_platform_init_args *args);
+
 /**
  * sev_platform_status - perform SEV PLATFORM_STATUS command
  *
@@ -955,6 +970,8 @@ sev_platform_status(struct sev_user_data_status *status, int *error) { return -E
 
 static inline int sev_platform_init(struct sev_platform_init_args *args) { return -ENODEV; }
 
+static inline int sev_snp_platform_init(struct sev_platform_init_args *args) { return -ENODEV; }
+
 static inline int
 sev_guest_deactivate(struct sev_data_deactivate *data, int *error) { return -ENODEV; }

---

## [9] Ashish Kalra — 2024-12-16
*Subject: [PATCH v2 8/9] KVM: SVM: Add support to initialize SEV/SNP functionality in KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

Remove platform initialization of SEV/SNP from PSP driver probe time and
move it to KVM module load time so that KVM can do SEV/SNP platform
initialization explicitly if it actually wants to use SEV/SNP
functionality.

With this patch, KVM will explicitly call into the PSP driver at load time
to initialize SNP by default while SEV initialization is done on-demand
when SEV/SEV-ES VMs are being launched.

Additionally do SEV platform shutdown when all SEV/SEV-ES VMs have been
destroyed to support SEV firmware hotloading and do full SEV and SNP
platform shutdown during KVM module unload time.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 33 +++++++++++++++++++++++++++++----
 1 file changed, 29 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 72674b8825c4..d55e281ac798 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -86,6 +86,7 @@ unsigned int max_sev_asid;
 static unsigned int min_sev_asid;
 static unsigned long sev_me_mask;
 static unsigned int nr_asids;
+static unsigned int nr_sev_vms_active;
 static unsigned long *sev_asid_bitmap;
 static unsigned long *sev_reclaim_asid_bitmap;
 
@@ -444,10 +445,16 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	if (ret)
 		goto e_no_asid;
 
-	init_args.probe = false;
-	ret = sev_platform_init(&init_args);
-	if (ret)
-		goto e_free;
+	if ((vm_type == KVM_X86_SEV_VM) ||
+	    (vm_type == KVM_X86_SEV_ES_VM)) {
+		down_write(&sev_deactivate_lock);
+		ret = sev_platform_init(&init_args);
+		if (!ret)
+			++nr_sev_vms_active;
+		up_write(&sev_deactivate_lock);
+		if (ret)
+			goto e_free;
+	}
 
 	/* This needs to happen after SEV/SNP firmware initialization. */
 	if (vm_type == KVM_X86_SNP_VM) {
@@ -2942,6 +2949,10 @@ void sev_vm_destroy(struct kvm *kvm)
 			return;
 	} else {
 		sev_unbind_asid(kvm, sev->handle);
+		down_write(&sev_deactivate_lock);
+		if (--nr_sev_vms_active == 0)
+			sev_platform_shutdown();
+		up_write(&sev_deactivate_lock);
 	}
 
 	sev_asid_free(sev);
@@ -2966,6 +2977,7 @@ void __init sev_set_cpu_caps(void)
 void __init sev_hardware_setup(void)
 {
 	unsigned int eax, ebx, ecx, edx, sev_asid_count, sev_es_asid_count;
+	struct sev_platform_init_args init_args = {0};
 	bool sev_snp_supported = false;
 	bool sev_es_supported = false;
 	bool sev_supported = false;
@@ -3082,6 +3094,16 @@ void __init sev_hardware_setup(void)
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
+	sev_snp_platform_init(&init_args);
 }
 
 void sev_hardware_unsetup(void)
@@ -3097,6 +3119,9 @@ void sev_hardware_unsetup(void)
 
 	misc_cg_set_capacity(MISC_CG_RES_SEV, 0);
 	misc_cg_set_capacity(MISC_CG_RES_SEV_ES, 0);
+
+	/* Do SEV and SNP Shutdown */
+	sev_snp_platform_shutdown();
 }
 
 int sev_cpu_init(struct svm_cpu_data *sd)

---

## [10] Ashish Kalra — 2024-12-17
*Subject: [PATCH v2 9/9] crypto: ccp: Move SEV/SNP Platform initialization to KVM*

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
Remove _sev_platform_init_locked() as it not used anymore and to
support separate SNP and SEV initialization sev_platform_init() is
now modified to do only SEV initialization and call
__sev_platform_init_locked() directly.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 55 +-----------------------------------
 include/linux/psp-sev.h      |  4 ---
 2 files changed, 1 insertion(+), 58 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 53c438b2b712..fbae688e4b7d 100644
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
@@ -1329,46 +1325,12 @@ static int __sev_platform_init_locked(int *error)
 	return rc;
 }
 
-static int _sev_platform_init_locked(struct sev_platform_init_args *args)
-{
-	struct sev_device *sev;
-	int rc;
-
-	if (!psp_master || !psp_master->sev_data)
-		return -ENODEV;
-
-	sev = psp_master->sev_data;
-
-	if (sev->state == SEV_STATE_INIT)
-		return 0;
-
-	/*
-	 * Legacy guests cannot be running while SNP_INIT(_EX) is executing,
-	 * so perform SEV-SNP initialization at probe time.
-	 */
-	rc = __sev_snp_init_locked(&args->error);
-	if (rc && rc != -ENODEV) {
-		/*
-		 * Don't abort the probe if SNP INIT failed,
-		 * continue to initialize the legacy SEV firmware.
-		 */
-		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
-			rc, args->error);
-	}
-
-	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */
-	if (args->probe && !psp_init_on_probe)
-		return 0;
-
-	return __sev_platform_init_locked(&args->error);
-}
-
 int sev_platform_init(struct sev_platform_init_args *args)
 {
 	int rc;
 
 	mutex_lock(&sev_cmd_mutex);
-	rc = _sev_platform_init_locked(args);
+	rc = __sev_platform_init_locked(&args->error);
 	mutex_unlock(&sev_cmd_mutex);
 
 	return rc;
@@ -2556,9 +2518,7 @@ EXPORT_SYMBOL_GPL(sev_issue_cmd_external_user);
 void sev_pci_init(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	struct sev_platform_init_args args = {0};
 	u8 api_major, api_minor, build;
-	int rc;
 
 	if (!sev)
 		return;
@@ -2581,16 +2541,6 @@ void sev_pci_init(void)
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
@@ -2605,7 +2555,4 @@ void sev_pci_exit(void)
 
 	if (!sev)
 		return;
-
-	sev_firmware_shutdown(sev);
-
 }
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index e50643aef8a9..dec89fc0b356 100644
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

## [11] Dionna Amalie Glaze — 2024-12-17
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On Mon, Dec 16, 2024 at 3:57 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>

> The on-demand SEV initialization support requires a fix in QEMU to
> remove check for SEV initialization to be done prior to launching

I don't think this is okay. I think you need to introduce a KVM
capability to switch over to the new way of initializing SEV VMs and
deprecate the old way so it doesn't need to be supported for any new
additions to the interface.

---

## [12] Kalra, Ashish — 2024-12-17
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On 12/17/2024 10:00 AM, Dionna Amalie Glaze wrote:
> On Mon, Dec 16, 2024 at 3:57 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>>

But that means KVM will need to support both mechanisms of doing SEV initialization - during KVM module load time 
and the deferred/lazy (on-demand) SEV INIT during VM launch.

Thanks,
Ashish

---

## [13] Sean Christopherson — 2024-12-17
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On Tue, Dec 17, 2024, Ashish Kalra wrote:
> 
> 

What's the QEMU change?  Dionna is right, we can't break userspace, but maybe
there's an alternative to supporting both models.

---

## [14] Dionna Amalie Glaze — 2024-12-17
*Subject: Re: [PATCH v2 4/9] crypto: ccp: Register SNP panic notifier only if
 SNP is enabled*

On Mon, Dec 16, 2024 at 3:58 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>

---

## [15] Kalra, Ashish — 2024-12-17
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On 12/17/2024 3:37 PM, Sean Christopherson wrote:
> On Tue, Dec 17, 2024, Ashish Kalra wrote:
>>

Here is the QEMU fix : (makes a SEV PLATFORM STATUS firmware call via PSP driver ioctl
to check if SEV is in INIT state)
 
diff --git a/target/i386/sev.c b/target/i386/sev.c
index 1a4eb1ada6..4fa8665395 100644
--- a/target/i386/sev.c
+++ b/target/i386/sev.c
@@ -1503,15 +1503,6 @@ static int sev_common_kvm_init(ConfidentialGuestSupport *cgs, Error **errp)
         }
     }

-    if (sev_es_enabled() && !sev_snp_enabled()) {
-        if (!(status.flags & SEV_STATUS_FLAGS_CONFIG_ES)) {
-            error_setg(errp, "%s: guest policy requires SEV-ES, but "
-                         "host SEV-ES support unavailable",
-                         __func__);
-            return -1;
-        }
-    }
-
     trace_kvm_sev_init();
     switch (x86_klass->kvm_type(X86_CONFIDENTIAL_GUEST(sev_common))) {
     case KVM_X86_DEFAULT_VM:

---

## [16] Daniel P. Berrangé — 2024-12-18
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On Tue, Dec 17, 2024 at 05:16:01PM -0600, Kalra, Ashish wrote:
> 
> 

Sigh, that code exists in all versions of QEMU that shipped with SEV-ES
support. IOW the proposed kernel change is not limited to breaking
"older QEMU versions". Every QEMU for the last 3 years will break,
including the newest version released last week. Please don't do that.

If the kvm-svm  kmod supports both load time init and lazy init, then
the QEMU incompatibility still exists, and will likely get pushed on
users by the OS distro forcing use of the lazy-load option :-(

With regards,
Daniel

---

## [17] Sean Christopherson — 2024-12-18
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On Tue, Dec 17, 2024, Ashish Kalra wrote:
> On 12/17/2024 3:37 PM, Sean Christopherson wrote:
> > On Tue, Dec 17, 2024, Ashish Kalra wrote:

Aside from breaking userspace, removing a sanity check is not a "fix".

Can't we simply have the kernel do __sev_platform_init_locked() on-demand for
SEV_PLATFORM_STATUS?  The goal with lazy initialization is defer initialization
until it's necessary so that userspace can do firmware updates.  And it's quite
clearly necessary in this case, so...

---

## [18] Kalra, Ashish — 2024-12-18
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On 12/18/2024 1:10 PM, Sean Christopherson wrote:
> On Tue, Dec 17, 2024, Ashish Kalra wrote:
>> On 12/17/2024 3:37 PM, Sean Christopherson wrote:

Actually this sanity check is not really required, if SEV INIT is not done before 
launching a SEV/SEV-ES VM, then LAUNCH_START will fail with invalid platform state
error as below:

...
qemu-system-x86_64: sev_launch_start: LAUNCH_START ret=1 fw_error=1 'Platform state is invalid'
...

So we can safely remove this check without causing a SEV/SEV-ES VM to blow up or something.

> 
> Can't we simply have the kernel do __sev_platform_init_locked() on-demand for

I don't think we want to do that, probably want to return "raw" status back to userspace,
if SEV INIT has not been done we probably need to return back that status, otherwise
it may break some other userspace tool.

Now, looking at this qemu check we will always have issues launching SEV/SEV-ES VMs
with SEV INIT on demand as this check enforces SEV INIT to be done before launching
the VMs. And then this causes issues with SEV firmware hotloading as the check 
enforces SEV INIT before launching VMs and once SEV INIT is done we can't do 
firmware  hotloading.

But, i believe there is another alternative approach : 

- PSP driver can call SEV Shutdown right before calling DLFW_EX and then do
a SEV INIT after successful DLFW_EX, in other words, we wrap DLFW_EX with 
SEV_SHUTDOWN prior to it and SEV INIT post it. This approach will also allow
us to do both SNP and SEV INIT at KVM module load time, there is no need to
do SEV INIT lazily or on demand before SEV/SEV-ES VM launch.

This approach should work without any changes in qemu and also allow 
SEV firmware hotloading without having any concerns about SEV INIT state.

Thanks,
Ashish

---

## [19] Kalra, Ashish — 2024-12-19
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On 12/18/2024 7:11 PM, Kalra, Ashish wrote:
> 
> On 12/18/2024 1:10 PM, Sean Christopherson wrote:

And to add here that SEV Shutdown will succeed with active SEV and SNP guests. 

SEV Shutdown (internally) marks all SEV asids as invalid and decommission all
SEV guests and does not affect SNP guests. 

So any active SEV guests will be implicitly shutdown and SNP guests will not be 
affected after SEV Shutdown right before doing SEV firmware hotloading and
calling DLFW_EX command. 

It should be fine to expect that there are no active SEV guests or any active
SEV guests will be shutdown as part of SEV firmware hotloading while keeping 
SNP guests running. 

Thanks,
Ashish

---

## [20] Dionna Amalie Glaze — 2024-12-19
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On Thu, Dec 19, 2024 at 2:04 PM Kalra, Ashish <ashish.kalra@amd.com> wrote:
>
>

Please don't implicitly shut down VMs. At least have a safe and unsafe
option for dlfw_ex where the default is to not destroy active
workloads.
That's why the 2022 patch series for Intel SGX EUPDATESVN on microcode
hotload was shot down.
It's very rude to destroy running workloads because a system update
was scheduled.

> It should be fine to expect that there are no active SEV guests or any active
> SEV guests will be shutdown as part of SEV firmware hotloading while keeping

---

## [21] Daniel P. Berrangé — 2024-12-20
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On Thu, Dec 19, 2024 at 04:04:45PM -0600, Kalra, Ashish wrote:
> 
> 

That's a pretty subtle distinction that I don't think host admins will
be likely to either learn about or remember. IMHO if there are active
SEV guests, the kernel should refuse the run the operation, rather
than kill running guests. The host admin must decide whether it is
appropriate to shutdown the guests in order to be able to run the
upgrade.

With regards,
Daniel

---

## [22] Sean Christopherson — 2024-12-20
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On Fri, Dec 20, 2024, Daniel P. Berrangé wrote:
> On Thu, Dec 19, 2024 at 04:04:45PM -0600, Kalra, Ashish wrote:
> > On 12/18/2024 7:11 PM, Kalra, Ashish wrote:

+1 to this and what Dionna said.  Aside from being a horrible experience for
userspace, trying to forcefully stop actions from within the kernel gets ugly.

---

## [23] Kalra, Ashish — 2024-12-20
*Subject: Re: [PATCH v2 0/9] Move initializing SEV/SNP functionality to KVM*

On 12/20/2024 10:25 AM, Sean Christopherson wrote:
> On Fri, Dec 20, 2024, Daniel P. Berrangé wrote:
>> On Thu, Dec 19, 2024 at 04:04:45PM -0600, Kalra, Ashish wrote:

Ok, SEV firmware hotloading will refuse the operation if there are active
SEV/SEV-ES guests.

SNP firmware hotloading/DLFW_EX is anyway transparent to SNP guests.

If there are no active SEV/SEV-ES guests, DLFW_EX will do SEV Shutdown
prior to it and SEV INIT post it, to work with the requirement of SEV
to be in UNINIT state to do DLFW_EX.

KVM module load time will do both SNP and SEV INIT. 

There is no reason to support lazy/on-demand SEV INIT when the first SEV VM
is launched, and that anyway can't be supported till qemu is changed to remove
the check for SEV INIT to be done before launching SEV/SEV-ES VMs.

Hopefully this should be the final design for SEV/SNP platform initialization
changes and SEV firmware hotloading support which i can go ahead and implement
and if someone has comments or concerns with the above please let me know.

Thanks,
Ashish

---

## [24] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [PATCH v2 1/9] crypto: ccp: Move dev_info/err messages for
 SEV/SNP initialization*

On 17/12/24 10:57, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

It is not actually removing anything, only adding.

> 
> This allows both _sev_platform_init_locked() and various SEV/SNP ioctls

here ...

>   
>   	/* Prepare for first SNP guest launch after INIT. */

... and here are different calls, and the message below is going to say 
"failed to INIT" when it actually failed to SEV_CMD_SNP_DF_FLUSH in this 
case. I'd like separate dev_err() for both. Other errors in this 
function do have own dev_err() already.


>   	sev->snp_initialized = true;
>   	dev_dbg(sev->dev, "SEV-SNP firmware initialized\n");

The same comment here. For example, I saw the "invalid page state" error 
from the PSP soooo many times so I believe any command can return it :) 
Thanks,


> +	return rc;
>   }

---

## [25] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [PATCH v2 2/9] crypto: ccp: Fix implicit SEV/SNP init and
 shutdown in ioctls*

On 17/12/24 10:57, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

goto e_free_cert, not return, otherwise leaks memory.


> +		ret = __sev_platform_init_locked(&argp->error);
> +		if (ret)


It is the same template 8 times, I'd declare rc and error inside the "if 
(shutdown_required)" scope or even drop them and error messages as 
__sev_snp_shutdown_locked() prints dev_err() anyway.

if (shutdown_required)
	__sev_snp_shutdown_locked(&error, false);

and that's it. Thanks,

> +
> +cleanup:

---

## [26] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [PATCH v2 3/9] crypto: ccp: Reset TMR size at SNP Shutdown*

On 17/12/24 10:58, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 


It is declared as:

static size_t sev_es_tmr_size = SEV_TMR_SIZE;

and then re-assigned again in __sev_snp_init_locked() to the same value 
of SNP_TMR_SIZE. When can sev_es_tmr_size become something else than 
SEV_TMR_SIZE? I did grep 10b2c8a67c4b (kvm/next) and 85ef1ac03941 
(AMDESE/snp-host-latest) but could not find it. Stale code may be? Thanks,


> +
>   	return ret;

---

## [27] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [PATCH v2 4/9] crypto: ccp: Register SNP panic notifier only if
 SNP is enabled*

On 17/12/24 10:58, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

A nit: I'd probably move the hunk right before __sev_snp_init_locked(). 
And the body of snp_shutdown_on_panic(), just to keep SNP code together. 
Not sure about the result though so feel free to ignore :)


>   static inline bool sev_version_greater_or_equal(u8 maj, u8 min)
>   {

can remove the above empty line too. Otherwise

Reviewed-by: Alexey Kardashevskiy <aik@amd.com>


> -	atomic_notifier_chain_unregister(&panic_notifier_list,
> -					 &snp_panic_notifier);

---

## [28] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [PATCH v2 7/9] crypto: ccp: Add new SEV/SNP platform
 initialization API*

On 17/12/24 10:59, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 


I'm told that in 2024 we should use guard(mutex)(&sev_cmd_mutex) and 
drop explicit mutex_unlock(). I'm not a huge fan but there is a point :)


> +	rc = __sev_snp_init_locked(&args->error);
> +	mutex_unlock(&sev_cmd_mutex);

The only caller ignores these, may be drop the returning value and print 
the errors inside sev_snp_platform_init() (if whatever 
__sev_snp_init_locked() already prints is not enough)?

Also, looks like 5/9 6/9 7/9 can be squashed into one patch, they touch 
the same files, equally do nothing until later patches, pretty straight 
forward. Thanks,


> + */
> +int sev_snp_platform_init(struct sev_platform_init_args *args);

---

## [29] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [PATCH v2 9/9] crypto: ccp: Move SEV/SNP Platform initialization
 to KVM*

On 17/12/24 11:00, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Can remove the above 4 lines too. Otherwise

Reviewed-by: Alexey Kardashevskiy <aik@amd.com>


> -
> -	sev_firmware_shutdown(sev);

---

## [30] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [PATCH v2 8/9] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 17/12/24 10:59, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

{} (without '0') should do the trick too.

>   	bool sev_snp_supported = false;
>   	bool sev_es_supported = false;

Out of curiosity - is not SNP INIT what "enables SNP system-wide"? What 
is that thing which SNP INIT does to allow SEV VMs to run? Thanks,


> +	 */
> +	sev_snp_platform_init(&init_args);

---

## [31] Tom Lendacky — 2025-01-03
*Subject: Re: [PATCH v2 3/9] crypto: ccp: Reset TMR size at SNP Shutdown*

On 12/27/24 03:07, Alexey Kardashevskiy wrote:
> On 17/12/24 10:58, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

When SNP has not been initialized using SNP_INIT(_EX), the TMR size must
be 1MB in size (SEV_TMR_SIZE), but when SNP_INIT_(EX) has been executed,
the TMR must be 2MB (SNP_TMR_SIZE) in size. This series is working towards
removing the initialization of SNP and/or SEV from the CCP initialization
and moving it to KVM, which means that we can have SNP init'd, then
shutdown and then SEV init'd. In this case, the TMR size must be the
SEV_TMR_SIZE value, so it is being reset after an SNP shutdown.

Thanks,
Tom

> 
>

---

## [32] Alexey Kardashevskiy — 2025-01-07
*Subject: Re: [PATCH v2 3/9] crypto: ccp: Reset TMR size at SNP Shutdown*

On 4/1/25 04:00, Tom Lendacky wrote:
> On 12/27/24 03:07, Alexey Kardashevskiy wrote:
>> On 17/12/24 10:58, Ashish Kalra wrote:

ah my bad, it is SEV_ vs SNP_, I am sort of used to SEV_ vs SEV_SNP_ and 
missed the distinction. sorry for the noise. Thanks,


> removing the initialization of SNP and/or SEV from the CCP initialization
> and moving it to KVM, which means that we can have SNP init'd, then

---
