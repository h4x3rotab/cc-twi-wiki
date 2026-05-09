---
title: 'Move initializing SEV/SNP functionality to KVM'
date: 2025-02-19
last_reply: 2025-02-20
message_count: 22
participants: ['Ashish Kalra', 'Dionna Amalie Glaze', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-02-19

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

v4:
- Rebase on linux-next which has the fix for SNP broken with kvm_amd
module built-in.
- Fix commit logs.
- Add explicit SEV/SNP initialization and shutdown error logs instead
of using a common exit point.
- Move SEV/SNP shutdown error logs from callers into __sev_platform_shutdown_locked()
and __sev_snp_shutdown_locked().
- Make sure that we continue to support both the probe field and psp_init_on_probe
module parameter for PSP module to support SEV INIT_EX.
- Add reviewed-by's.

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
  crypto: ccp: Move dev_info/err messages for SEV/SNP init and shutdown
  crypto: ccp: Ensure implicit SEV/SNP init and shutdown in ioctls
  crypto: ccp: Reset TMR size at SNP Shutdown
  crypto: ccp: Register SNP panic notifier only if SNP is enabled
  crypto: ccp: Add new SEV/SNP platform shutdown API
  KVM: SVM: Add support to initialize SEV/SNP functionality in KVM
  crypto: ccp: Move SEV/SNP Platform initialization to KVM

 arch/x86/kvm/svm/sev.c       |  15 +++
 drivers/crypto/ccp/sev-dev.c | 219 ++++++++++++++++++++++++-----------
 include/linux/psp-sev.h      |   3 +
 3 files changed, 171 insertions(+), 66 deletions(-)

---

## [2] Ashish Kalra — 2025-02-19
*Subject: [PATCH v4 1/7] crypto: ccp: Move dev_info/err messages for SEV/SNP init and shutdown*

From: Ashish Kalra <ashish.kalra@amd.com>

Move dev_info and dev_err messages related to SEV/SNP initialization
and shutdown into __sev_platform_init_locked(), __sev_snp_init_locked()
and __sev_platform_shutdown_locked(), __sev_snp_shutdown_locked() so
that they don't need to be issued from callers.

This allows both _sev_platform_init_locked() and various SEV/SNP ioctls
to call __sev_platform_init_locked(), __sev_snp_init_locked() and
__sev_platform_shutdown_locked(), __sev_snp_shutdown_locked() for
implicit SEV/SNP initialization and shutdown without additionally
printing any errors/success messages.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 39 +++++++++++++++++++++++++++---------
 1 file changed, 30 insertions(+), 9 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 2e87ca0e292a..8f5c474b9d1c 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1176,21 +1176,30 @@ static int __sev_snp_init_locked(int *error)
 	wbinvd_on_all_cpus();
 
 	rc = __sev_do_cmd_locked(cmd, arg, error);
-	if (rc)
+	if (rc) {
+		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
+			rc, *error);
 		return rc;
+	}
 
 	/* Prepare for first SNP guest launch after INIT. */
 	wbinvd_on_all_cpus();
 	rc = __sev_do_cmd_locked(SEV_CMD_SNP_DF_FLUSH, NULL, error);
-	if (rc)
+	if (rc) {
+		dev_err(sev->dev, "SEV-SNP: SNP_DF_FLUSH failed rc %d, error %#x\n",
+			rc, *error);
 		return rc;
+	}
 
 	sev->snp_initialized = true;
 	dev_dbg(sev->dev, "SEV-SNP firmware initialized\n");
 
+	dev_info(sev->dev, "SEV-SNP API:%d.%d build:%d\n", sev->api_major,
+		 sev->api_minor, sev->build);
+
 	sev_es_tmr_size = SNP_TMR_SIZE;
 
-	return rc;
+	return 0;
 }
 
 static void __sev_platform_init_handle_tmr(struct sev_device *sev)
@@ -1267,8 +1276,10 @@ static int __sev_platform_init_locked(int *error)
 	__sev_platform_init_handle_tmr(sev);
 
 	rc = __sev_platform_init_handle_init_ex_path(sev);
-	if (rc)
+	if (rc) {
+		dev_err(sev->dev, "SEV: handle_init_ex_path failed, rc %d\n", rc);
 		return rc;
+	}
 
 	rc = __sev_do_init_locked(&psp_ret);
 	if (rc && psp_ret == SEV_RET_SECURE_DATA_INVALID) {
@@ -1287,16 +1298,22 @@ static int __sev_platform_init_locked(int *error)
 	if (error)
 		*error = psp_ret;
 
-	if (rc)
+	if (rc) {
+		dev_err(sev->dev, "SEV: failed to INIT error %#x, rc %d\n",
+			psp_ret, rc);
 		return rc;
+	}
 
 	sev->state = SEV_STATE_INIT;
 
 	/* Prepare for first SEV guest launch after INIT */
 	wbinvd_on_all_cpus();
 	rc = __sev_do_cmd_locked(SEV_CMD_DF_FLUSH, NULL, error);
-	if (rc)
+	if (rc) {
+		dev_err(sev->dev, "SEV: DF_FLUSH failed %#x, rc %d\n",
+			*error, rc);
 		return rc;
+	}
 
 	dev_dbg(sev->dev, "SEV firmware initialized\n");
 
@@ -1367,8 +1384,11 @@ static int __sev_platform_shutdown_locked(int *error)
 		return 0;
 
 	ret = __sev_do_cmd_locked(SEV_CMD_SHUTDOWN, NULL, error);
-	if (ret)
+	if (ret) {
+		dev_err(sev->dev, "SEV: failed to SHUTDOWN error %#x, rc %d\n",
+			*error, ret);
 		return ret;
+	}
 
 	sev->state = SEV_STATE_UNINIT;
 	dev_dbg(sev->dev, "SEV firmware shutdown\n");
@@ -1684,7 +1704,7 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	if (*error == SEV_RET_DFFLUSH_REQUIRED) {
 		ret = __sev_do_cmd_locked(SEV_CMD_SNP_DF_FLUSH, NULL, NULL);
 		if (ret) {
-			dev_err(sev->dev, "SEV-SNP DF_FLUSH failed\n");
+			dev_err(sev->dev, "SEV-SNP DF_FLUSH failed, ret = %d\n", ret);
 			return ret;
 		}
 		/* reissue the shutdown command */
@@ -1692,7 +1712,8 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 					  error);
 	}
 	if (ret) {
-		dev_err(sev->dev, "SEV-SNP firmware shutdown failed\n");
+		dev_err(sev->dev, "SEV-SNP firmware shutdown failed, rc %d, error %#x\n",
+			ret, *error);
 		return ret;
 	}

---

## [3] Ashish Kalra — 2025-02-19
*Subject: [PATCH v4 2/7] crypto: ccp: Ensure implicit SEV/SNP init and shutdown in ioctls*

From: Ashish Kalra <ashish.kalra@amd.com>

Modify the behavior of implicit SEV initialization in some of the
SEV ioctls to do both SEV initialization and shutdown and add
implicit SNP initialization and shutdown to some of the SNP ioctls
so that the change of SEV/SNP platform initialization not being
done during PSP driver probe time does not break userspace tools
such as sevtool, etc.

Prior to this patch, SEV has always been initialized before these
ioctls as SEV initialization is done as part of PSP module probe,
but now with SEV initialization being moved to KVM module load instead
of PSP driver probe, the implied SEV INIT actually makes sense and gets
used and additionally to maintain SEV platform state consistency
before and after the ioctl SEV shutdown needs to be done after the
firmware call.

It is important to do SEV Shutdown here with the SEV/SNP initialization
moving to KVM, an implicit SEV INIT here as part of the SEV ioctls not
followed with SEV Shutdown will cause SEV to remain in INIT state and
then a future SNP INIT in KVM module load will fail.

Similarly, prior to this patch, SNP has always been initialized before
these ioctls as SNP initialization is done as part of PSP module probe,
therefore, to keep a consistent behavior, SNP init needs to be done
here implicitly as part of these ioctls followed with SNP shutdown
before returning from the ioctl to maintain the consistent platform
state before and after the ioctl.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 117 ++++++++++++++++++++++++++++-------
 1 file changed, 93 insertions(+), 24 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 8f5c474b9d1c..b06f43eb18f7 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1461,7 +1461,8 @@ static int sev_ioctl_do_platform_status(struct sev_issue_cmd *argp)
 static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	int rc;
+	bool shutdown_required = false;
+	int rc, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1470,19 +1471,26 @@ static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool wr
 		rc = __sev_platform_init_locked(&argp->error);
 		if (rc)
 			return rc;
+		shutdown_required = true;
 	}
 
-	return __sev_do_cmd_locked(cmd, NULL, &argp->error);
+	rc = __sev_do_cmd_locked(cmd, NULL, &argp->error);
+
+	if (shutdown_required)
+		__sev_platform_shutdown_locked(&error);
+
+	return rc;
 }
 
 static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_pek_csr input;
+	bool shutdown_required = false;
 	struct sev_data_pek_csr data;
 	void __user *input_address;
 	void *blob = NULL;
-	int ret;
+	int ret, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1513,6 +1521,7 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 		ret = __sev_platform_init_locked(&argp->error);
 		if (ret)
 			goto e_free_blob;
+		shutdown_required = true;
 	}
 
 	ret = __sev_do_cmd_locked(SEV_CMD_PEK_CSR, &data, &argp->error);
@@ -1531,6 +1540,9 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_blob:
+	if (shutdown_required)
+		__sev_platform_shutdown_locked(&error);
+
 	kfree(blob);
 	return ret;
 }
@@ -1747,8 +1759,9 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_pek_cert_import input;
 	struct sev_data_pek_cert_import data;
+	bool shutdown_required = false;
 	void *pek_blob, *oca_blob;
-	int ret;
+	int ret, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1780,11 +1793,15 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 		ret = __sev_platform_init_locked(&argp->error);
 		if (ret)
 			goto e_free_oca;
+		shutdown_required = true;
 	}
 
 	ret = __sev_do_cmd_locked(SEV_CMD_PEK_CERT_IMPORT, &data, &argp->error);
 
 e_free_oca:
+	if (shutdown_required)
+		__sev_platform_shutdown_locked(&error);
+
 	kfree(oca_blob);
 e_free_pek:
 	kfree(pek_blob);
@@ -1901,17 +1918,8 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
+	int ret, error;
 
 	if (copy_from_user(&input, (void __user *)argp->data, sizeof(input)))
 		return -EFAULT;
@@ -1952,6 +1960,16 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	data.cert_chain_len = input.cert_chain_len;
 
 cmd:
+	/* If platform is not in INIT state then transition it to INIT. */
+	if (sev->state != SEV_STATE_INIT) {
+		if (!writable)
+			goto e_free_cert;
+		ret = __sev_platform_init_locked(&argp->error);
+		if (ret)
+			goto e_free_cert;
+		shutdown_required = true;
+	}
+
 	ret = __sev_do_cmd_locked(SEV_CMD_PDH_CERT_EXPORT, &data, &argp->error);
 
 	/* If we query the length, FW responded with expected data. */
@@ -1978,6 +1996,9 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_cert:
+	if (shutdown_required)
+		__sev_platform_shutdown_locked(&error);
+
 	kfree(cert_blob);
 e_free_pdh:
 	kfree(pdh_blob);
@@ -1987,12 +2008,13 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 {
 	struct sev_device *sev = psp_master->sev_data;
+	bool shutdown_required = false;
 	struct sev_data_snp_addr buf;
 	struct page *status_page;
+	int ret, error;
 	void *data;
-	int ret;
 
-	if (!sev->snp_initialized || !argp->data)
+	if (!argp->data)
 		return -EINVAL;
 
 	status_page = alloc_page(GFP_KERNEL_ACCOUNT);
@@ -2001,6 +2023,13 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 
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
@@ -2029,6 +2058,9 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 		ret = -EFAULT;
 
 cleanup:
+	if (shutdown_required)
+		__sev_snp_shutdown_locked(&error, false);
+
 	__free_pages(status_page, 0);
 	return ret;
 }
@@ -2037,21 +2069,34 @@ static int sev_ioctl_do_snp_commit(struct sev_issue_cmd *argp)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_data_snp_commit buf;
+	bool shutdown_required = false;
+	int ret, error;
 
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
+	if (shutdown_required)
+		__sev_snp_shutdown_locked(&error, false);
+
+	return ret;
 }
 
 static int sev_ioctl_do_snp_set_config(struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_snp_config config;
+	bool shutdown_required = false;
+	int ret, error;
 
-	if (!sev->snp_initialized || !argp->data)
+	if (!argp->data)
 		return -EINVAL;
 
 	if (!writable)
@@ -2060,17 +2105,30 @@ static int sev_ioctl_do_snp_set_config(struct sev_issue_cmd *argp, bool writable
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
+	if (shutdown_required)
+		__sev_snp_shutdown_locked(&error, false);
+
+	return ret;
 }
 
 static int sev_ioctl_do_snp_vlek_load(struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_snp_vlek_load input;
+	bool shutdown_required = false;
+	int ret, error;
 	void *blob;
-	int ret;
 
-	if (!sev->snp_initialized || !argp->data)
+	if (!argp->data)
 		return -EINVAL;
 
 	if (!writable)
@@ -2089,8 +2147,19 @@ static int sev_ioctl_do_snp_vlek_load(struct sev_issue_cmd *argp, bool writable)
 
 	input.vlek_wrapped_address = __psp_pa(blob);
 
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&argp->error);
+		if (ret)
+			goto cleanup;
+		shutdown_required = true;
+	}
+
 	ret = __sev_do_cmd_locked(SEV_CMD_SNP_VLEK_LOAD, &input, &argp->error);
 
+	if (shutdown_required)
+		__sev_snp_shutdown_locked(&error, false);
+
+cleanup:
 	kfree(blob);
 
 	return ret;

---

## [4] Ashish Kalra — 2025-02-19
*Subject: [PATCH v4 3/7] crypto: ccp: Reset TMR size at SNP Shutdown*

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
index b06f43eb18f7..be8a84ce24c7 100644
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

## [5] Ashish Kalra — 2025-02-19
*Subject: [PATCH v4 4/7] crypto: ccp: Register SNP panic notifier only if SNP is enabled*

From: Ashish Kalra <ashish.kalra@amd.com>

Register the SNP panic notifier if and only if SNP is actually
initialized and deregistering the notifier when shutting down
SNP in PSP driver when KVM module is unloaded.

Currently the SNP panic notifier is being registered
irrespective of SNP being enabled/initialized and with this
change the SNP panic notifier is registered only if SNP
support is enabled and initialized.

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 22 +++++++++++++---------
 1 file changed, 13 insertions(+), 9 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index be8a84ce24c7..582304638319 100644
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
@@ -1197,6 +1204,9 @@ static int __sev_snp_init_locked(int *error)
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
 
@@ -2466,10 +2479,6 @@ static int snp_shutdown_on_panic(struct notifier_block *nb,
 	return NOTIFY_DONE;
 }
 
-static struct notifier_block snp_panic_notifier = {
-	.notifier_call = snp_shutdown_on_panic,
-};
-
 int sev_issue_cmd_external_user(struct file *filep, unsigned int cmd,
 				void *data, int *error)
 {
@@ -2518,8 +2527,6 @@ void sev_pci_init(void)
 	dev_info(sev->dev, "SEV%s API:%d.%d build:%d\n", sev->snp_initialized ?
 		"-SNP" : "", sev->api_major, sev->api_minor, sev->build);
 
-	atomic_notifier_chain_register(&panic_notifier_list,
-				       &snp_panic_notifier);
 	return;
 
 err:
@@ -2536,7 +2543,4 @@ void sev_pci_exit(void)
 		return;
 
 	sev_firmware_shutdown(sev);
-
-	atomic_notifier_chain_unregister(&panic_notifier_list,
-					 &snp_panic_notifier);
 }

---

## [6] Ashish Kalra — 2025-02-19
*Subject: [PATCH v4 5/7] crypto: ccp: Add new SEV/SNP platform shutdown API*

From: Ashish Kalra <ashish.kalra@amd.com>

Add new API interface to do SEV/SNP platform shutdown when KVM module
is unloaded.

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 13 +++++++++++++
 include/linux/psp-sev.h      |  3 +++
 2 files changed, 16 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 582304638319..f0f3e6d29200 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2445,6 +2445,19 @@ static void sev_firmware_shutdown(struct sev_device *sev)
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
index f3cad182d4ef..0b3a36bdaa90 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -954,6 +954,7 @@ int sev_do_cmd(int cmd, void *data, int *psp_ret);
 void *psp_copy_user_blob(u64 uaddr, u32 len);
 void *snp_alloc_firmware_page(gfp_t mask);
 void snp_free_firmware_page(void *addr);
+void sev_platform_shutdown(void);
 
 #else	/* !CONFIG_CRYPTO_DEV_SP_PSP */
 
@@ -988,6 +989,8 @@ static inline void *snp_alloc_firmware_page(gfp_t mask)
 
 static inline void snp_free_firmware_page(void *addr) { }
 
+static inline void sev_platform_shutdown(void) { }
+
 #endif	/* CONFIG_CRYPTO_DEV_SP_PSP */
 
 #endif	/* __PSP_SEV_H__ */

---

## [7] Ashish Kalra — 2025-02-19
*Subject: [PATCH v4 6/7] KVM: SVM: Add support to initialize SEV/SNP functionality in KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

Move platform initialization of SEV/SNP from PSP driver probe time to
KVM module load time so that KVM can do SEV/SNP platform initialization
explicitly if it actually wants to use SEV/SNP functionality.

Add support for KVM to explicitly call into the PSP driver at load time
to initialize SEV/SNP by default but this behavior can be altered with KVM
module parameters to not do SEV/SNP platform initialization at module load
time if required. Additionally SEV/SNP platform shutdown is invoked during
KVM module unload time.

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 74525651770a..213d4c15a9da 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2933,6 +2933,7 @@ void __init sev_set_cpu_caps(void)
 void __init sev_hardware_setup(void)
 {
 	unsigned int eax, ebx, ecx, edx, sev_asid_count, sev_es_asid_count;
+	struct sev_platform_init_args init_args = {0};
 	bool sev_snp_supported = false;
 	bool sev_es_supported = false;
 	bool sev_supported = false;
@@ -3059,6 +3060,17 @@ void __init sev_hardware_setup(void)
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
+	init_args.probe = true;
+	sev_platform_init(&init_args);
 }
 
 void sev_hardware_unsetup(void)
@@ -3074,6 +3086,9 @@ void sev_hardware_unsetup(void)
 
 	misc_cg_set_capacity(MISC_CG_RES_SEV, 0);
 	misc_cg_set_capacity(MISC_CG_RES_SEV_ES, 0);
+
+	/* Do SEV and SNP Shutdown */
+	sev_platform_shutdown();
 }
 
 int sev_cpu_init(struct svm_cpu_data *sd)

---

## [8] Ashish Kalra — 2025-02-19
*Subject: [PATCH v4 7/7] crypto: ccp: Move SEV/SNP Platform initialization to KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

SNP initialization is forced during PSP driver probe purely because SNP
can't be initialized if VMs are running.  But the only in-tree user of
SEV/SNP functionality is KVM, and KVM depends on PSP driver for the same.
Forcing SEV/SNP initialization because a hypervisor could be running
legacy non-confidential VMs make no sense.

This patch removes SEV/SNP initialization from the PSP driver probe
time and moves the requirement to initialize SEV/SNP functionality
to KVM if it wants to use SEV/SNP.

Suggested-by: Sean Christopherson <seanjc@google.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 25 +------------------------
 1 file changed, 1 insertion(+), 24 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index f0f3e6d29200..99a663dbc2b6 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1346,18 +1346,13 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
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
 
 	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */
@@ -2505,9 +2500,7 @@ EXPORT_SYMBOL_GPL(sev_issue_cmd_external_user);
 void sev_pci_init(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	struct sev_platform_init_args args = {0};
 	u8 api_major, api_minor, build;
-	int rc;
 
 	if (!sev)
 		return;
@@ -2530,16 +2523,6 @@ void sev_pci_init(void)
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
@@ -2550,10 +2533,4 @@ void sev_pci_init(void)
 
 void sev_pci_exit(void)
 {
-	struct sev_device *sev = psp_master->sev_data;
-
-	if (!sev)
-		return;
-
-	sev_firmware_shutdown(sev);
 }

---

## [9] Dionna Amalie Glaze — 2025-02-20
*Subject: Re: [PATCH v4 2/7] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

On Wed, Feb 19, 2025 at 12:53 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>

This error is discarded. Is that by design? If so, It'd be better to
call this ignored_error.

> +
> +       return rc;

Another discarded error. This function is called in different
locations in sev-dev.c with and without checking the result, which
seems problematic.

> +
>         kfree(blob);

Again.

> +
>         kfree(oca_blob);

Using argp->error for init instead of the ioctl-requested command
means that the user will have difficulty distinguishing which process
is at fault, no?

> +               if (ret)
> +                       goto e_free_cert;

Again.

> +
>         kfree(cert_blob);

Error provenance confusion.

> +               if (ret)
> +                       goto cleanup;

Error provenance confusion.

> +               if (ret)
> +                       return ret;

Again.

> +
> +       return ret;

Error provenance problem again.

> +               if (ret)
> +                       return ret;

Error provenance confusion.

> +               if (ret)
> +                       goto cleanup;

Again.

> +
> +cleanup:

---

## [10] Dionna Amalie Glaze — 2025-02-20
*Subject: Re: [PATCH v4 3/7] crypto: ccp: Reset TMR size at SNP Shutdown*

On Wed, Feb 19, 2025 at 12:53 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>
> From: Ashish Kalra <ashish.kalra@amd.com>

Acked-by: Dionna Glaze <dionnaglaze@google.com>

> ---
>  drivers/crypto/ccp/sev-dev.c | 3 +++

---

## [11] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v4 1/7] crypto: ccp: Move dev_info/err messages for
 SEV/SNP init and shutdown*

On 2/19/25 14:52, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

How about doing:

	dev_err(sev->dev, "SEV-SNP: %s failed rc %d, error %#x\n",
		cmd == SEV_CMD_SNP_INIT_EX ? "SNP_INIT_EX" : "SNP_INIT",
		rc, *error);

>  		return rc;
> +	}

Messages should be issued in __sev_platform_init_handle_init_ex_path().
The only non-zero rc value that doesn't cause a message would come from
sev_read_init_ex_file() when sev_init_ex_buffer is NULL, but
sev_read_init_ex_file() isn't called if the allocation for that buffer
fails. So I don't think this message is necessary. But double-check me
on that.

>  
>  	rc = __sev_do_init_locked(&psp_ret);

Similar to the SNP INIT comment above, how about:

	dev_err(sev->dev, "SEV: %s failed %#x, rc %d\n",
		sev_init_ex_buffer ? "INIT_EX" : "INIT", psp_ret, rc);

>  		return rc;
> +	}

Should provide as much info as possible, so create a local int variable
that you can pass into __sev_do_cmd_locked() and output that in the
failure message.

(I should go through this file later and make all the message formats
consistent.)

Thanks,
Tom

>  			return ret;
>  		}

---

## [12] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v4 3/7] crypto: ccp: Reset TMR size at SNP Shutdown*

On 2/19/25 14:53, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

This is a long run-on sentence, please re-work this to make it more
informative and clear as to what the issue is.

Other than that,

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> 
> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>

---

## [13] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v4 4/7] crypto: ccp: Register SNP panic notifier only if
 SNP is enabled*

On 2/19/25 14:53, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

/deregistering/unregister/

> SNP in PSP driver when KVM module is unloaded.

s/SNP.*/SNP./

The PSP driver and KVM reference isn't needed.

> 
> Currently the SNP panic notifier is being registered

s/being//

> irrespective of SNP being enabled/initialized and with this

s/intialized.*/intialized./

> change the SNP panic notifier is registered only if SNP
> support is enabled and initialized.

This paragraph should actually be the first paragraph of the commit
message, followed by the other paragraph. So something like...

Currently, the SNP panic notifier is registered on module
initialization, regardless of whether SNP is enabled or initialized.

Instead, register the SNP panic notifier only when SNP is actually
initialized and unregister the notifier when SNP is shutdown.

Thanks,
Tom

> 
> Reviewed-by: Dionna Glaze <dionnaglaze@google.com>

---

## [14] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v4 5/7] crypto: ccp: Add new SEV/SNP platform shutdown API*

On 2/19/25 14:54, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Just a nit below if you have to respin. Otherwise:

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> 
> Reviewed-by: Dionna Glaze <dionnaglaze@google.com>

	sev_firmware_shutdown(psp->master->sev_data);

and then you can get rid of the sev variable.

Thanks,
Tom

> +}
> +EXPORT_SYMBOL_GPL(sev_platform_shutdown);

---

## [15] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v4 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 2/19/25 14:54, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

s/PSP/CCP/

> KVM module load time so that KVM can do SEV/SNP platform initialization
> explicitly if it actually wants to use SEV/SNP functionality.

s/PSP/CCP/

> to initialize SEV/SNP by default but this behavior can be altered with KVM

s/by default but this/. If required, this/

> module parameters to not do SEV/SNP platform initialization at module load
> time if required. Additionally SEV/SNP platform shutdown is invoked during

s/if required//
s/Additionally/Additionally, a corresponding/

> KVM module unload time.

Some commit message comments and a minor comment below, otherwise:

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> 
> Suggested-by: Sean Christopherson <seanjc@google.com>

But won't this also do an SEV init as long as init_on_probe is true? And
isn't this true for even non-SEV VMs? You have to pause all VMs before
performing SNP INIT. In which case I don't see the point of this
comment. I think you really just want to say:

	/*
	 * Always perform SEV initialization at setup time to avoid
	 * complications with performing SEV initialization later
	 * (such as suspending active guests, etc.).
	 */

Not that that is much better... but it's more accurate.

Thanks,
Tom

> +	init_args.probe = true;
> +	sev_platform_init(&init_args);

---

## [16] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v4 7/7] crypto: ccp: Move SEV/SNP Platform initialization
 to KVM*

On 2/19/25 14:55, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Please don't remove the error information.

>  	}
>  

Should this remain? If there's a bug in KVM that somehow skips the
shutdown call, then SEV will remain initialized. I think the path is
safe to call a second time.

Thanks,
Tom


>  }

---

## [17] Kalra, Ashish — 2025-02-20
*Subject: Re: [PATCH v4 2/7] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

Hello Dionna,

On 2/20/2025 10:44 AM, Dionna Amalie Glaze wrote:
> On Wed, Feb 19, 2025 at 12:53 PM Ashish Kalra <Ashish.Kalra@amd.com> wrote:
>>

This is by design, we cannot overwrite the error for the original command being issued
here which in this case is do_pek_pdh_gen, hence we use a local error for the shutdown command.
And __sev_platform_shutdown_locked() has it's own error logging code, so it will be printing
the error message for the shutdown command failure, so the shutdown error is not eventually 
being ignored, that error log will assist in any inconsistent SEV/SNP platform state and 
subsequent errors.

>> +
>> +       return rc;

Not really, if shutdown fails for any reason, the error is printed. 
The return value here reflects the value of the original command/function.
The command/ioctl could have succeeded but the shutdown failed, hence, 
shutdown error is printed, but the return value reflects that the ioctl succeeded.

Additionally, in case of INIT before the command is issued, the command may
have failed without the SEV state being in INIT state, hence the error for the
INIT command failure is returned back from the ioctl.

> 
>> +

Not really, in case the SEV command has still not been issued, argp->error is still usable
and returned back to the caller (no need to use a local error here), we are not overwriting 
the argp->error used for the original command/ioctl here.

Thanks,
Ashish

>> +               if (ret)
>> +                       goto e_free_cert;

---

## [18] Kalra, Ashish — 2025-02-20
*Subject: Re: [PATCH v4 7/7] crypto: ccp: Move SEV/SNP Platform initialization
 to KVM*

Hello Tom,

On 2/20/2025 2:03 PM, Tom Lendacky wrote:
> On 2/19/25 14:55, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

The error(s) are already being printed in __sev_snp_init_locked() otherwise the same
error will be printed twice, hence removing it here.

>>  	}
>>  

Ok.

Thanks,
Ashish

---

## [19] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v4 7/7] crypto: ccp: Move SEV/SNP Platform initialization
 to KVM*

On 2/20/25 14:23, Kalra, Ashish wrote:
> Hello Tom,
> 

Sounds like this change should be in patch #1 then.

Thanks,
Tom

> 
>>>  	}

---

## [20] Dionna Amalie Glaze — 2025-02-20
*Subject: Re: [PATCH v4 2/7] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

On Thu, Feb 20, 2025 at 12:07 PM Kalra, Ashish <ashish.kalra@amd.com> wrote:
>
> Hello Dionna,

I mean in the case that argp->error is set to a value shared by the
command and init, it's hard to know what the problem was.
I'd like to ensure that the documentation is updated to reflect that
(in this case) if PDH_CERT_EXPORT returns INVALID_PLATFORM_STATE, then
it's because the platform was not in PSTATE.UNINIT state.
The new behavior of initializing when you need to now means that you
should have ruled out INVALID_PLATFORM_STATE as a possible value from
PDH_EXPORT_CERT. Same for SNP_CONFIG.

There is not a 1-to-1 mapping between the ioctl commands and the SEV
commands now, so I think you need extra documentation to clarify the
new error space for at least pdh_export and set_config

SNP_PLATFORM_STATUS, VLEK_LOAD, and SNP_COMMIT appear to not
necessarily have a provenance confusion after looking closer.

---

## [21] Kalra, Ashish — 2025-02-20
*Subject: Re: [PATCH v4 2/7] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

On 2/20/2025 3:37 PM, Dionna Amalie Glaze wrote:
> On Thu, Feb 20, 2025 at 12:07 PM Kalra, Ashish <ashish.kalra@amd.com> wrote:
>>

I am more of less trying to match the current behavior of sev_ioctl_do_pek_import()
or sev_ioctl_do_pdh_export().

All this is implementation specific handling so we can't update SEV/SNP firmware
API specs documentation for this new error space, this is not a firmware specific return code. 

But to maintain 1-to-1 mapping between the ioctl commands and the SEV/SNP commands, 
i think it will be better to handle this INIT in the same way as SHUTDOWN, which
is to use a local error for INIT and in case of implicit INIT failures, let the
error logs from __sev_platform_init_locked() OR __sev_snp_init_locked() be printed
and always return INVALID_PLATFORM_STATE as error back to the caller.

Thanks,
Ashish

---

## [22] Dionna Amalie Glaze — 2025-02-20
*Subject: Re: [PATCH v4 2/7] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

On Thu, Feb 20, 2025 at 2:18 PM Kalra, Ashish <ashish.kalra@amd.com> wrote:
>
> On 2/20/2025 3:37 PM, Dionna Amalie Glaze wrote:

I was just talking about the uapi for the ioctls, not AMD reference
documentation.

> But to maintain 1-to-1 mapping between the ioctl commands and the SEV/SNP commands,
> i think it will be better to handle this INIT in the same way as SHUTDOWN, which

---
