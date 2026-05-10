---
title: 'Move initializing SEV/SNP functionality to KVM'
date: 2025-02-25
last_reply: 2025-03-12
message_count: 23
participants: ['Ashish Kalra', 'kernel test robot', 'Sean Christopherson', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-02-25

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

v5:
- To maintain 1-to-1 mapping between the ioctl commands and the SEV/SNP commands, 
handle the implicit INIT in the same way as SHUTDOWN, which is to use a local error
for INIT and in case of implicit INIT failures, let the error logs from 
__sev_platform_init_locked() OR __sev_snp_init_locked() be printed and always return
INVALID_PLATFORM_STATE as error back to the caller.
- Add better error logging for SEV/SNP INIT and SHUTDOWN commands.
- Fix commit logs.
- Add more acked-by's, reviewed-by's, suggested-by's.

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
 drivers/crypto/ccp/sev-dev.c | 239 +++++++++++++++++++++++++----------
 include/linux/psp-sev.h      |   3 +
 3 files changed, 190 insertions(+), 67 deletions(-)

---

## [2] Ashish Kalra — 2025-02-25
*Subject: [PATCH v5 1/7] crypto: ccp: Move dev_info/err messages for SEV/SNP init and shutdown*

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
 drivers/crypto/ccp/sev-dev.c | 44 ++++++++++++++++++++++++++----------
 1 file changed, 32 insertions(+), 12 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 2e87ca0e292a..8962a0dbc66f 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1176,21 +1176,31 @@ static int __sev_snp_init_locked(int *error)
 	wbinvd_on_all_cpus();
 
 	rc = __sev_do_cmd_locked(cmd, arg, error);
-	if (rc)
+	if (rc) {
+		dev_err(sev->dev, "SEV-SNP: %s failed rc %d, error %#x\n",
+			cmd == SEV_CMD_SNP_INIT_EX ? "SNP_INIT_EX" : "SNP_INIT",
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
@@ -1287,16 +1297,22 @@ static int __sev_platform_init_locked(int *error)
 	if (error)
 		*error = psp_ret;
 
-	if (rc)
+	if (rc) {
+		dev_err(sev->dev, "SEV: %s failed %#x, rc %d\n",
+			sev_init_ex_buffer ? "INIT_EX" : "INIT", psp_ret, rc);
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
 
@@ -1329,8 +1345,7 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 		 * Don't abort the probe if SNP INIT failed,
 		 * continue to initialize the legacy SEV firmware.
 		 */
-		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
-			rc, args->error);
+		dev_err(sev->dev, "SEV-SNP: failed to INIT, continue SEV INIT\n");
 	}
 
 	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */
@@ -1367,8 +1382,11 @@ static int __sev_platform_shutdown_locked(int *error)
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
@@ -1654,7 +1672,7 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	struct psp_device *psp = psp_master;
 	struct sev_device *sev;
 	struct sev_data_snp_shutdown_ex data;
-	int ret;
+	int ret, psp_error;
 
 	if (!psp || !psp->sev_data)
 		return 0;
@@ -1682,9 +1700,10 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	ret = __sev_do_cmd_locked(SEV_CMD_SNP_SHUTDOWN_EX, &data, error);
 	/* SHUTDOWN may require DF_FLUSH */
 	if (*error == SEV_RET_DFFLUSH_REQUIRED) {
-		ret = __sev_do_cmd_locked(SEV_CMD_SNP_DF_FLUSH, NULL, NULL);
+		ret = __sev_do_cmd_locked(SEV_CMD_SNP_DF_FLUSH, NULL, &psp_error);
 		if (ret) {
-			dev_err(sev->dev, "SEV-SNP DF_FLUSH failed\n");
+			dev_err(sev->dev, "SEV-SNP DF_FLUSH failed, ret = %d, error = %#x\n",
+				ret, psp_error);
 			return ret;
 		}
 		/* reissue the shutdown command */
@@ -1692,7 +1711,8 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 					  error);
 	}
 	if (ret) {
-		dev_err(sev->dev, "SEV-SNP firmware shutdown failed\n");
+		dev_err(sev->dev, "SEV-SNP firmware shutdown failed, rc %d, error %#x\n",
+			ret, *error);
 		return ret;
 	}

---

## [3] Ashish Kalra — 2025-02-25
*Subject: [PATCH v5 2/7] crypto: ccp: Ensure implicit SEV/SNP init and shutdown in ioctls*

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

Suggested-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 145 +++++++++++++++++++++++++++--------
 1 file changed, 115 insertions(+), 30 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 8962a0dbc66f..14847f1c05fc 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1459,28 +1459,38 @@ static int sev_ioctl_do_platform_status(struct sev_issue_cmd *argp)
 static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	int rc;
+	bool shutdown_required = false;
+	int rc, error;
 
 	if (!writable)
 		return -EPERM;
 
 	if (sev->state == SEV_STATE_UNINIT) {
-		rc = __sev_platform_init_locked(&argp->error);
-		if (rc)
+		rc = __sev_platform_init_locked(&error);
+		if (rc) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
 			return rc;
+		}
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
@@ -1508,9 +1518,12 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 
 cmd:
 	if (sev->state == SEV_STATE_UNINIT) {
-		ret = __sev_platform_init_locked(&argp->error);
-		if (ret)
+		ret = __sev_platform_init_locked(&error);
+		if (ret) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
 			goto e_free_blob;
+		}
+		shutdown_required = true;
 	}
 
 	ret = __sev_do_cmd_locked(SEV_CMD_PEK_CSR, &data, &argp->error);
@@ -1529,6 +1542,9 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_blob:
+	if (shutdown_required)
+		__sev_platform_shutdown_locked(&error);
+
 	kfree(blob);
 	return ret;
 }
@@ -1746,8 +1762,9 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_pek_cert_import input;
 	struct sev_data_pek_cert_import data;
+	bool shutdown_required = false;
 	void *pek_blob, *oca_blob;
-	int ret;
+	int ret, error;
 
 	if (!writable)
 		return -EPERM;
@@ -1776,14 +1793,20 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 
 	/* If platform is not in INIT state then transition it to INIT */
 	if (sev->state != SEV_STATE_INIT) {
-		ret = __sev_platform_init_locked(&argp->error);
-		if (ret)
+		ret = __sev_platform_init_locked(&error);
+		if (ret) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
 			goto e_free_oca;
+		}
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
@@ -1900,17 +1923,8 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
@@ -1951,6 +1965,18 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	data.cert_chain_len = input.cert_chain_len;
 
 cmd:
+	/* If platform is not in INIT state then transition it to INIT. */
+	if (sev->state != SEV_STATE_INIT) {
+		if (!writable)
+			goto e_free_cert;
+		ret = __sev_platform_init_locked(&error);
+		if (ret) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
+			goto e_free_cert;
+		}
+		shutdown_required = true;
+	}
+
 	ret = __sev_do_cmd_locked(SEV_CMD_PDH_CERT_EXPORT, &data, &argp->error);
 
 	/* If we query the length, FW responded with expected data. */
@@ -1977,6 +2003,9 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_cert:
+	if (shutdown_required)
+		__sev_platform_shutdown_locked(&error);
+
 	kfree(cert_blob);
 e_free_pdh:
 	kfree(pdh_blob);
@@ -1986,12 +2015,13 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
@@ -2000,6 +2030,15 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 
 	data = page_address(status_page);
 
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&error);
+		if (ret) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
+			goto cleanup;
+		}
+		shutdown_required = true;
+	}
+
 	/*
 	 * Firmware expects status page to be in firmware-owned state, otherwise
 	 * it will report firmware error code INVALID_PAGE_STATE (0x1A).
@@ -2028,6 +2067,9 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 		ret = -EFAULT;
 
 cleanup:
+	if (shutdown_required)
+		__sev_snp_shutdown_locked(&error, false);
+
 	__free_pages(status_page, 0);
 	return ret;
 }
@@ -2036,21 +2078,36 @@ static int sev_ioctl_do_snp_commit(struct sev_issue_cmd *argp)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_data_snp_commit buf;
+	bool shutdown_required = false;
+	int ret, error;
 
-	if (!sev->snp_initialized)
-		return -EINVAL;
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&error);
+		if (ret) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
+			return ret;
+		}
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
@@ -2059,17 +2116,32 @@ static int sev_ioctl_do_snp_set_config(struct sev_issue_cmd *argp, bool writable
 	if (copy_from_user(&config, (void __user *)argp->data, sizeof(config)))
 		return -EFAULT;
 
-	return __sev_do_cmd_locked(SEV_CMD_SNP_CONFIG, &config, &argp->error);
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&error);
+		if (ret) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
+			return ret;
+		}
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
@@ -2088,8 +2160,21 @@ static int sev_ioctl_do_snp_vlek_load(struct sev_issue_cmd *argp, bool writable)
 
 	input.vlek_wrapped_address = __psp_pa(blob);
 
+	if (!sev->snp_initialized) {
+		ret = __sev_snp_init_locked(&error);
+		if (ret) {
+			argp->error = SEV_RET_INVALID_PLATFORM_STATE;
+			goto cleanup;
+		}
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

## [4] Ashish Kalra — 2025-02-25
*Subject: [PATCH v5 3/7] crypto: ccp: Reset TMR size at SNP Shutdown*

From: Ashish Kalra <ashish.kalra@amd.com>

Implicit SNP initialization as part of some SNP ioctls modify TMR size
to be SNP compliant which followed by SNP shutdown will leave the
TMR size modified and then subsequently cause SEV only initialization
to fail, hence, reset TMR size to default at SNP Shutdown.

Acked-by: Dionna Glaze <dionnaglaze@google.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 3 +++
 1 file changed, 3 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 14847f1c05fc..c784de6c77c3 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1754,6 +1754,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	sev->snp_initialized = false;
 	dev_dbg(sev->dev, "SEV-SNP firmware shutdown\n");
 
+	/* Reset TMR size back to default */
+	sev_es_tmr_size = SEV_TMR_SIZE;
+
 	return ret;
 }

---

## [5] Ashish Kalra — 2025-02-25
*Subject: [PATCH v5 4/7] crypto: ccp: Register SNP panic notifier only if SNP is enabled*

From: Ashish Kalra <ashish.kalra@amd.com>

Currently, the SNP panic notifier is registered on module initialization
regardless of whether SNP is being enabled or initialized.

Instead, register the SNP panic notifier only when SNP is actually
initialized and unregister the notifier when SNP is shutdown.

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 22 +++++++++++++---------
 1 file changed, 13 insertions(+), 9 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index c784de6c77c3..b3479a2896d0 100644
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
@@ -1198,6 +1205,9 @@ static int __sev_snp_init_locked(int *error)
 	dev_info(sev->dev, "SEV-SNP API:%d.%d build:%d\n", sev->api_major,
 		 sev->api_minor, sev->build);
 
+	atomic_notifier_chain_register(&panic_notifier_list,
+				       &snp_panic_notifier);
+
 	sev_es_tmr_size = SNP_TMR_SIZE;
 
 	return 0;
@@ -1754,6 +1764,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	sev->snp_initialized = false;
 	dev_dbg(sev->dev, "SEV-SNP firmware shutdown\n");
 
+	atomic_notifier_chain_unregister(&panic_notifier_list,
+					 &snp_panic_notifier);
+
 	/* Reset TMR size back to default */
 	sev_es_tmr_size = SEV_TMR_SIZE;
 
@@ -2481,10 +2494,6 @@ static int snp_shutdown_on_panic(struct notifier_block *nb,
 	return NOTIFY_DONE;
 }
 
-static struct notifier_block snp_panic_notifier = {
-	.notifier_call = snp_shutdown_on_panic,
-};
-
 int sev_issue_cmd_external_user(struct file *filep, unsigned int cmd,
 				void *data, int *error)
 {
@@ -2533,8 +2542,6 @@ void sev_pci_init(void)
 	dev_info(sev->dev, "SEV%s API:%d.%d build:%d\n", sev->snp_initialized ?
 		"-SNP" : "", sev->api_major, sev->api_minor, sev->build);
 
-	atomic_notifier_chain_register(&panic_notifier_list,
-				       &snp_panic_notifier);
 	return;
 
 err:
@@ -2551,7 +2558,4 @@ void sev_pci_exit(void)
 		return;
 
 	sev_firmware_shutdown(sev);
-
-	atomic_notifier_chain_unregister(&panic_notifier_list,
-					 &snp_panic_notifier);
 }

---

## [6] Ashish Kalra — 2025-02-25
*Subject: [PATCH v5 5/7] crypto: ccp: Add new SEV/SNP platform shutdown API*

From: Ashish Kalra <ashish.kalra@amd.com>

Add new API interface to do SEV/SNP platform shutdown when KVM module
is unloaded.

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 9 +++++++++
 include/linux/psp-sev.h      | 3 +++
 2 files changed, 12 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index b3479a2896d0..cde6ebab589d 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2460,6 +2460,15 @@ static void sev_firmware_shutdown(struct sev_device *sev)
 	mutex_unlock(&sev_cmd_mutex);
 }
 
+void sev_platform_shutdown(void)
+{
+	if (!psp_master || !psp_master->sev_data)
+		return;
+
+	sev_firmware_shutdown(psp_master->sev_data);
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

## [7] Ashish Kalra — 2025-02-25
*Subject: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP functionality in KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

Move platform initialization of SEV/SNP from CCP driver probe time to
KVM module load time so that KVM can do SEV/SNP platform initialization
explicitly if it actually wants to use SEV/SNP functionality.

Add support for KVM to explicitly call into the CCP driver at load time
to initialize SEV/SNP. If required, this behavior can be altered with KVM
module parameters to not do SEV/SNP platform initialization at module load
time. Additionally, a corresponding SEV/SNP platform shutdown is invoked
during KVM module unload time.

Suggested-by: Sean Christopherson <seanjc@google.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 74525651770a..0bc6c0486071 100644
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
+	 * Always perform SEV initialization at setup time to avoid
+	 * complications when performing SEV initialization later
+	 * (such as suspending active guests, etc.).
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

## [8] Ashish Kalra — 2025-02-25
*Subject: [PATCH v5 7/7] crypto: ccp: Move SEV/SNP Platform initialization to KVM*

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
 drivers/crypto/ccp/sev-dev.c | 16 ----------------
 1 file changed, 16 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index cde6ebab589d..42988d757665 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1345,10 +1345,6 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	if (sev->state == SEV_STATE_INIT)
 		return 0;
 
-	/*
-	 * Legacy guests cannot be running while SNP_INIT(_EX) is executing,
-	 * so perform SEV-SNP initialization at probe time.
-	 */
 	rc = __sev_snp_init_locked(&args->error);
 	if (rc && rc != -ENODEV) {
 		/*
@@ -2516,9 +2512,7 @@ EXPORT_SYMBOL_GPL(sev_issue_cmd_external_user);
 void sev_pci_init(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	struct sev_platform_init_args args = {0};
 	u8 api_major, api_minor, build;
-	int rc;
 
 	if (!sev)
 		return;
@@ -2541,16 +2535,6 @@ void sev_pci_init(void)
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

---

## [9] kernel test robot — 2025-02-28
*Subject: Re: [PATCH v5 2/7] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

Hi Ashish,

kernel test robot noticed the following build warnings:

[auto build test WARNING on herbert-cryptodev-2.6/master]
[also build test WARNING on kvm/queue kvm/next linus/master v6.14-rc4 next-20250227]
[cannot apply to kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Ashish-Kalra/crypto-ccp-Move-dev_info-err-messages-for-SEV-SNP-init-and-shutdown/20250226-050640
base:   https://git.kernel.org/pub/scm/linux/kernel/git/herbert/cryptodev-2.6.git master
patch link:    https://lore.kernel.org/r/1d7b31af0eb36d860907c1e89e553e642f3882e0.1740512583.git.ashish.kalra%40amd.com
patch subject: [PATCH v5 2/7] crypto: ccp: Ensure implicit SEV/SNP init and shutdown in ioctls
config: x86_64-allyesconfig (https://download.01.org/0day-ci/archive/20250228/202502280243.uLlWONet-lkp@intel.com/config)
compiler: clang version 19.1.7 (https://github.com/llvm/llvm-project cd708029e0b2869e80abe31ddb175f7c35361f90)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250228/202502280243.uLlWONet-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202502280243.uLlWONet-lkp@intel.com/

All warnings (new ones prefixed by >>):

   In file included from drivers/crypto/ccp/sev-dev.c:22:
   In file included from include/linux/ccp.h:14:
   In file included from include/linux/scatterlist.h:8:
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
>> drivers/crypto/ccp/sev-dev.c:1970:7: warning: variable 'ret' is used uninitialized whenever 'if' condition is true [-Wsometimes-uninitialized]
    1970 |                 if (!writable)
         |                     ^~~~~~~~~
   drivers/crypto/ccp/sev-dev.c:2012:9: note: uninitialized use occurs here
    2012 |         return ret;
         |                ^~~
   drivers/crypto/ccp/sev-dev.c:1970:3: note: remove the 'if' if its condition is always false
    1970 |                 if (!writable)
         |                 ^~~~~~~~~~~~~~
    1971 |                         goto e_free_cert;
         |                         ~~~~~~~~~~~~~~~~
   drivers/crypto/ccp/sev-dev.c:1927:9: note: initialize the variable 'ret' to silence this warning
    1927 |         int ret, error;
         |                ^
         |                 = 0
   4 warnings generated.


vim +1970 drivers/crypto/ccp/sev-dev.c

  1917	
  1918	static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
  1919	{
  1920		struct sev_device *sev = psp_master->sev_data;
  1921		struct sev_user_data_pdh_cert_export input;
  1922		void *pdh_blob = NULL, *cert_blob = NULL;
  1923		struct sev_data_pdh_cert_export data;
  1924		void __user *input_cert_chain_address;
  1925		void __user *input_pdh_cert_address;
  1926		bool shutdown_required = false;
  1927		int ret, error;
  1928	
  1929		if (copy_from_user(&input, (void __user *)argp->data, sizeof(input)))
  1930			return -EFAULT;
  1931	
  1932		memset(&data, 0, sizeof(data));
  1933	
  1934		/* Userspace wants to query the certificate length. */
  1935		if (!input.pdh_cert_address ||
  1936		    !input.pdh_cert_len ||
  1937		    !input.cert_chain_address)
  1938			goto cmd;
  1939	
  1940		input_pdh_cert_address = (void __user *)input.pdh_cert_address;
  1941		input_cert_chain_address = (void __user *)input.cert_chain_address;
  1942	
  1943		/* Allocate a physically contiguous buffer to store the PDH blob. */
  1944		if (input.pdh_cert_len > SEV_FW_BLOB_MAX_SIZE)
  1945			return -EFAULT;
  1946	
  1947		/* Allocate a physically contiguous buffer to store the cert chain blob. */
  1948		if (input.cert_chain_len > SEV_FW_BLOB_MAX_SIZE)
  1949			return -EFAULT;
  1950	
  1951		pdh_blob = kzalloc(input.pdh_cert_len, GFP_KERNEL);
  1952		if (!pdh_blob)
  1953			return -ENOMEM;
  1954	
  1955		data.pdh_cert_address = __psp_pa(pdh_blob);
  1956		data.pdh_cert_len = input.pdh_cert_len;
  1957	
  1958		cert_blob = kzalloc(input.cert_chain_len, GFP_KERNEL);
  1959		if (!cert_blob) {
  1960			ret = -ENOMEM;
  1961			goto e_free_pdh;
  1962		}
  1963	
  1964		data.cert_chain_address = __psp_pa(cert_blob);
  1965		data.cert_chain_len = input.cert_chain_len;
  1966	
  1967	cmd:
  1968		/* If platform is not in INIT state then transition it to INIT. */
  1969		if (sev->state != SEV_STATE_INIT) {
> 1970			if (!writable)
  1971				goto e_free_cert;
  1972			ret = __sev_platform_init_locked(&error);
  1973			if (ret) {
  1974				argp->error = SEV_RET_INVALID_PLATFORM_STATE;
  1975				goto e_free_cert;
  1976			}
  1977			shutdown_required = true;
  1978		}
  1979	
  1980		ret = __sev_do_cmd_locked(SEV_CMD_PDH_CERT_EXPORT, &data, &argp->error);
  1981	
  1982		/* If we query the length, FW responded with expected data. */
  1983		input.cert_chain_len = data.cert_chain_len;
  1984		input.pdh_cert_len = data.pdh_cert_len;
  1985	
  1986		if (copy_to_user((void __user *)argp->data, &input, sizeof(input))) {
  1987			ret = -EFAULT;
  1988			goto e_free_cert;
  1989		}
  1990	
  1991		if (pdh_blob) {
  1992			if (copy_to_user(input_pdh_cert_address,
  1993					 pdh_blob, input.pdh_cert_len)) {
  1994				ret = -EFAULT;
  1995				goto e_free_cert;
  1996			}
  1997		}
  1998	
  1999		if (cert_blob) {
  2000			if (copy_to_user(input_cert_chain_address,
  2001					 cert_blob, input.cert_chain_len))
  2002				ret = -EFAULT;
  2003		}
  2004	
  2005	e_free_cert:
  2006		if (shutdown_required)
  2007			__sev_platform_shutdown_locked(&error);
  2008	
  2009		kfree(cert_blob);
  2010	e_free_pdh:
  2011		kfree(pdh_blob);
  2012		return ret;
  2013	}
  2014

---

## [10] Sean Christopherson — 2025-02-28
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Tue, Feb 25, 2025, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

This is misleading and wildly incomplete.  *SEV* doesn't have complications, *SNP*
has complications.  And looking through sev_platform_init(), all of this code
is buggy.

The sev_platform_init() return code is completely disconnected from SNP setup.
It can return errors even if SNP setup succeeds, and can return success even if
SNP setup fails.

I also think it makes sense to require SNP to be initialized during KVM setup.
I don't see anything in __sev_snp_init_locked() that suggests SNP initialization
can magically succeed at runtime if it failed at boot.  To keep things sane and
simple, I think KVM should reject module load if SNP is requested, setup fails,
and kvm-amd.ko is a module.  If kvm-amd.ko is built-in and SNP fails, just disable
SNP support.  I.e. when possible, let userspace decide what to do, but don't bring
down all of KVM just because SNP setup failed.

The attached patches are compile-tested (mostly), can you please test them and
slot them in?

> +	 */
> +	init_args.probe = true;

Meh, just omit this comment.  

> +	sev_platform_shutdown();
>  }

---

## [11] Kalra, Ashish — 2025-02-28
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

Hello Sean,

On 2/28/2025 12:31 PM, Sean Christopherson wrote:
> On Tue, Feb 25, 2025, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

There are a few important considerations here: 

This is true that we require SNP to be initialized during KVM setup 
and also as mentioned earlier we need SNP to be initialized (SNP_INIT_EX
should be done) for SEV INIT to succeed if SNP host support is enabled.

So we essentially have to do SNP_INIT(_EX) for launching SEV/SEV-ES VMs when
SNP host support is enabled. In other words, if SNP_INIT(_EX) is not issued or 
fails then SEV/SEV-ES VMs can't be launched once SNP host support (SYSCFG.SNPEn) 
is enabled as SEV INIT will fail in such a situation.

And the other consideration is that runtime setup of especially SEV-ES VMs will not
work if/when first SEV-ES VM is launched, if SEV INIT has not been issued at 
KVM setup time.

This is because qemu has a check for SEV INIT to have been done (via SEV platform
status command) prior to launching SEV-ES VMs via KVM_SEV_INIT2 ioctl. 

So effectively, __sev_guest_init() does not get invoked in case of launching 
SEV_ES VMs, if sev_platform_init() has not been done to issue SEV INIT in 
sev_hardware_setup().

In other words the deferred initialization only works for SEV VMs and not SEV-ES VMs.

For this reason, we decided to do sev_platform_init() to do both SNP and SEV/SEV-ES
initialization (SEV INIT) as part of sev_hardware_setup() and then do an implicit
SEV shutdown prior to SNP_DOWNLOAD_FIRMWARE_EX command followed by (implicit) SEV INIT
after the DLFW_EX command to facilitate SEV firmware hotloading.

Thanks,
Ashish

> I don't see anything in __sev_snp_init_locked() that suggests SNP initialization
> can magically succeed at runtime if it failed at boot.  To keep things sane and

---

## [12] Sean Christopherson — 2025-02-28
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Fri, Feb 28, 2025, Ashish Kalra wrote:
> Hello Sean,
> 

Doesn't that mean sev_platform_init() is broken and should error out if SNP
setup fails?  Because this doesn't match the above (or I'm misreading one or both).

	rc = __sev_snp_init_locked(&args->error);
	if (rc && rc != -ENODEV) {
		/*
		 * Don't abort the probe if SNP INIT failed,
		 * continue to initialize the legacy SEV firmware.
		 */
		dev_err(sev->dev, "SEV-SNP: failed to INIT, continue SEV INIT\n");
	}

And doesn't the min version check completely wreck everything?  I.e. if SNP *must*
be initialized if SYSCFG.SNPEn is set in order to utilize SEV/SEV-ES, then shouldn't
this be a fatal error too?

	if (!sev_version_greater_or_equal(SNP_MIN_API_MAJOR, SNP_MIN_API_MINOR)) {
		dev_dbg(sev->dev, "SEV-SNP support requires firmware version >= %d:%d\n",
			SNP_MIN_API_MAJOR, SNP_MIN_API_MINOR);
		return 0;
	}

And then aren't all of the bare calls to __sev_platform_init_locked() broken too?
E.g. if userspace calls sev_ioctl_do_pek_csr() without loading KVM, then SNP won't
be initialized and __sev_platform_init_locked() will fail, no?

> And the other consideration is that runtime setup of especially SEV-ES VMs will not
> work if/when first SEV-ES VM is launched, if SEV INIT has not been issued at 

In that case, I vote to kill off deferred initialization entirely, and commit to
enabling all of SEV+ when KVM loads (which we should have done from day one).
Assuming we can do that in a way that's compatible with the /dev/sev ioctls.

---

## [13] Tom Lendacky — 2025-03-03
*Subject: Re: [PATCH v5 1/7] crypto: ccp: Move dev_info/err messages for
 SEV/SNP init and shutdown*

On 2/25/25 14:59, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Move the psp_error variable into the if statement where it is used and
name it dfflush_error.

With that,

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

>  
>  	if (!psp || !psp->sev_data)

---

## [14] Tom Lendacky — 2025-03-03
*Subject: Re: [PATCH v5 2/7] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

On 2/25/25 15:00, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

I see this block of code multiple times throughout this patch, both for
SEV and SNP. Can this be consolidated into one or two functions that get
called? Maybe something like:

	rc = sev_move_to_cmd_state(argp, &shutdown_required);

Thanks,
Tom

>  
> -	return __sev_do_cmd_locked(cmd, NULL, &argp->error);

---

## [15] Tom Lendacky — 2025-03-03
*Subject: Re: [PATCH v5 4/7] crypto: ccp: Register SNP panic notifier only if
 SNP is enabled*

On 2/25/25 15:00, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  drivers/crypto/ccp/sev-dev.c | 22 +++++++++++++---------

---

## [16] Tom Lendacky — 2025-03-03
*Subject: Re: [PATCH v5 7/7] crypto: ccp: Move SEV/SNP Platform initialization
 to KVM*

On 2/25/25 15:02, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Should this dev_info() have been removed in patch #1? Because it looks
like this would have been a duplicate message after the first patch, right?

Thanks,
Tom

> -
>  	return;

---

## [17] Kalra, Ashish — 2025-03-03
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

Hello Sean,

On 2/28/2025 4:32 PM, Sean Christopherson wrote:
> On Fri, Feb 28, 2025, Ashish Kalra wrote:
>> Hello Sean,

Yes, i realized this is true and we need to return here if rc != -ENODEV.

So i will add a pre-patch to the series to fix this.

> And doesn't the min version check completely wreck everything?  I.e. if SNP *must*
> be initialized if SYSCFG.SNPEn is set in order to utilize SEV/SEV-ES, then shouldn't

Yes, this is also true, we need to return an error here.

> And then aren't all of the bare calls to __sev_platform_init_locked() broken too?
> E.g. if userspace calls sev_ioctl_do_pek_csr() without loading KVM, then SNP won't

Yes, we should be calling _sev_platform_init_locked() here instead of__sev_platform_init_locked()
to ensure that both implicit SNP and SEV INIT is done for these ioctls and followed by 
__sev_firmware_shutdown() to do both SEV and SNP shutdown.

> 
>> And the other consideration is that runtime setup of especially SEV-ES VMs will not

Yes, that's what seems to be the right approach to enabling all SEV+ when KVM loads. 

For SEV firmware hotloading we will do implicit SEV Shutdown prior to DLFW_EX
and SEV (re)INIT after that to ensure that SEV is in UNINIT state before
DLFW_EX.

We still probably want to keep the deferred initialization for SEV in 
__sev_guest_init() by calling sev_platform_init() to support the SEV INIT_EX
case.

Thanks,
Ashish

---

## [18] Sean Christopherson — 2025-03-03
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Mon, Mar 03, 2025, Ashish Kalra wrote:
> On 2/28/2025 4:32 PM, Sean Christopherson wrote:
> > On Fri, Feb 28, 2025, Ashish Kalra wrote:

Refresh me, how does INIT_EX fit into all of this?  I.e. why does it need special
casing?

---

## [19] Kalra, Ashish — 2025-03-03
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 3/3/2025 2:49 PM, Sean Christopherson wrote:
> On Mon, Mar 03, 2025, Ashish Kalra wrote:
>> On 2/28/2025 4:32 PM, Sean Christopherson wrote:

For SEV INIT_EX, we need the filesystem to be up and running as the user-supplied
SEV related persistent data is read from a regular file and provided to the
INIT_EX command.

Now, with the modified SEV/SNP init flow, when SEV/SNP initialization is 
performed during KVM module load, then as i believe the filesystem will be
mounted before KVM module loads, so SEV INIT_EX can be supported without
any issues.

Therefore, we don't need deferred initialization support for SEV INIT_EX
in case of KVM being loaded as a module.

But if KVM module is built-in, then filesystem will not be mounted when 
SEV/SNP initialization is done during KVM initialization and in that case
SEV INIT_EX cannot be supported. 

Therefore to support SEV INIT_EX when KVM module is built-in, the following
will need to be done:

- Boot kernel with psp_init_on_probe=false command line.
- This ensures that during KVM initialization, only SNP INIT is done.
- Later at runtime, when filesystem has already been mounted, 
SEV VM launch will trigger deferred SEV (INIT_EX) initialization
(via the __sev_guest_init() -> sev_platform_init() code path).

NOTE: psp_init_on_probe module parameter and deferred SEV initialization
during SEV VM launch (__sev_guest_init()->sev_platform_init()) was added
specifically to support SEV INIT_EX case.

Thanks,
Ashish

---

## [20] Sean Christopherson — 2025-03-04
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On Mon, Mar 03, 2025, Ashish Kalra wrote:
> On 3/3/2025 2:49 PM, Sean Christopherson wrote:
> > On Mon, Mar 03, 2025, Ashish Kalra wrote:

Ugh.  That's quite the unworkable mess.  sev_hardware_setup() can't determine
if SEV/SEV-ES is fully supported without initializing the platform, but userspace
needs KVM to do initialization so that SEV platform status reads out correctly.

Aha!

Isn't that a Google problem?  And one that resolves itself if initialization is
done on kvm-amd.ko load?

A system/kernel _could_ be configured to use a path during initcalls, with the
approproate initramfs magic.  So there's no hard requirement that makes init_ex_path
incompatible with CRYPTO_DEV_CCP_DD=y or CONFIG_KVM_AMD=y.  Google's environment
simply doesn't jump through those hoops.

But Google _does_ build kvm-amd.ko as a module.

So rather than carry a bunch of hard-to-follow code (and potentially impossible
constraints), always do initialization at kvm-amd.ko load, and require the platform
owner to ensure init_ex_path can be resolved when sev_hardware_setup() runs, i.e.
when kvm-amd.ko is loaded or its initcall runs.

---

## [21] Kalra, Ashish — 2025-03-04
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 3/4/2025 3:58 PM, Sean Christopherson wrote:
> On Mon, Mar 03, 2025, Ashish Kalra wrote:
>> On 3/3/2025 2:49 PM, Sean Christopherson wrote:

Yes, SEV INIT_EX is mainly used/required by Google.

> 
> A system/kernel _could_ be configured to use a path during initcalls, with the

So you are proposing that we drop all deferred initialization support for SEV, i.e,
we drop the psp_init_on_probe module parameter for CCP driver, remove the probe
field from sev_platform_init_args and correspondingly drop any support to skip/defer
SEV INIT in _sev_platform_init_locked() and then also drop all existing support in
KVM for SEV deferred initialization, i.e, remove the call to sev_platform_init()
from __sev_guest_init().

Thanks,
Ashish

---

## [22] Kalra, Ashish — 2025-03-05
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

On 3/4/2025 7:58 PM, Kalra, Ashish wrote:
> 
> On 3/4/2025 3:58 PM, Sean Christopherson wrote:

Also looking at the patch commit logs for psp_init_on_probe parameter:
https://lore.kernel.org/lkml/20211115174102.2211126-5-pgonda@google.com/

User may decouple module init from PSP init due to use of the INIT_EX support in
upcoming patch which allows for users to save PSP's internal state to file. The
file may be unavailable at module init.

So it probably makes sense to keep SEV deferred initialization support there, as it may
not only be filesystem unavailability at CCP module load (or KVM module load with new flow),
but user may have the file available only later after module load/init.

Thanks,
Ashish

---

## [23] Kalra, Ashish — 2025-03-12
*Subject: Re: [PATCH v5 6/7] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

Hello Sean,

On 3/4/2025 3:58 PM, Sean Christopherson wrote:
> On Mon, Mar 03, 2025, Ashish Kalra wrote:
>> On 3/3/2025 2:49 PM, Sean Christopherson wrote:

Revisiting this one again and following up on it: 

Actually SEV platform status command does not need SEV INIT to have been
done, this command can be executed in SEV UNINIT state. 

Hence, qemu can issue SEV PLATFORM_STATUS command to determine if SEV-ES is
initialized (i.e. SEV INIT has been completed) before launching SEV-ES
VMs. 

The issue is this additional check in qemu to ensure SEV INIT 
has been done before launching SEV-ES VMs, as below: 

target/i386/sev.c:
..
static int sev_common_kvm_init(..)
{
..
	sev_platform_ioctl(sev_fd, SEV_PLATFORM_STATUS, &status, &fw_error);
..
	if (sev_es_enabled() && !sev_snp_enabled()) {
		if (!(status.flags & SEV_STATUS_FLAGS_CONFIG_ES)) {
			error_setg(errp, "%s: guest policy requires SEV-ES, but "
					"host SEV-ES support unavailable", ..
		}
	}
..
	sev_ioctl(sev_fd, KVM_SEV_INIT2, &args, &fw_error);
..
}

So v6 of this patch-series always does both SEV and SNP INIT(_EX) at kvm-amd.ko
load. 

But also does keep the SEV deferred initialization support in __sev_guest_init()
to handle SEV INIT_EX, in case the file containing SEV persistent data is
available later after module load.

Let me know if you have any more questions on this.

Thanks,
Ashish

> Aha!
>

---
