---
title: 'Move initializing SEV/SNP functionality to KVM'
date: 2025-03-06
last_reply: 2025-03-12
message_count: 17
participants: ['Ashish Kalra', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-03-06

From: Ashish Kalra <ashish.kalra@amd.com>

Remove initializing SEV/SNP functionality from PSP driver and instead add
support to KVM to explicitly initialize the PSP if KVM wants to use
SEV/SNP functionality.

This removes SEV/SNP initialization at PSP module probe time and does
on-demand SEV/SNP initialization when KVM really wants to use 
SEV/SNP functionality. This will allow running legacy non-confidential
VMs without initializating SEV functionality. 

The patch-set includes the fix to not continue with SEV INIT if SNP
INIT fails as RMP table must be initialized before calling SEV INIT
if host SNP support is enabled.

This will assist in adding SNP CipherTextHiding support and SEV firmware
hotloading support in KVM without sharing SEV ASID management and SNP
guest context support between PSP driver and KVM and keeping all that
support only in KVM.

To support SEV firmware hotloading, SEV Shutdown will be done explicitly
prior to DOWNLOAD_FIRMWARE_EX and SEV INIT post it to work with the
requirement of SEV to be in UNINIT state for DOWNLOAD_FIRMWARE_EX.
NOTE: SEV firmware hotloading will only be supported if there are no
active SEV/SEV-ES guests. 

v6:
- Add fix to not continue with SEV INIT if SNP INIT fails as RMP table 
must be initialized before calling SEV INIT if host SNP support is enabled.
- Ensure that for SEV IOCTLs requiring SEV to be initialized, 
_sev_platform_init_locked() is called instead of __sev_platform_init_locked()
to ensure that both implicit SNP and SEV INIT is done for these ioctls and
followed by __sev_firmware_shutdown() to do both SEV and SNP shutdown.
- Refactor doing SEV and SNP INIT implicitly for specific SEV and SNP
ioctls into sev_move_to_init_state() and snp_move_to_init_state(). 
- Ensure correct error code is returned from sev_ioctl_do_pdh_export() 
if platform is not in INIT state.
- Remove dev_info() from sev_pci_init() because this would have printed
a duplicate message.

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

Ashish Kalra (8):
  crypto: ccp: Abort doing SEV INIT if SNP INIT fails
  crypto: ccp: Move dev_info/err messages for SEV/SNP init and shutdown
  crypto: ccp: Ensure implicit SEV/SNP init and shutdown in ioctls
  crypto: ccp: Reset TMR size at SNP Shutdown
  crypto: ccp: Register SNP panic notifier only if SNP is enabled
  crypto: ccp: Add new SEV/SNP platform shutdown API
  KVM: SVM: Add support to initialize SEV/SNP functionality in KVM
  crypto: ccp: Move SEV/SNP Platform initialization to KVM

 arch/x86/kvm/svm/sev.c       |  12 ++
 drivers/crypto/ccp/sev-dev.c | 245 +++++++++++++++++++++++++----------
 include/linux/psp-sev.h      |   3 +
 3 files changed, 194 insertions(+), 66 deletions(-)

---

## [2] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 1/8] crypto: ccp: Abort doing SEV INIT if SNP INIT fails*

From: Ashish Kalra <ashish.kalra@amd.com>

If SNP host support (SYSCFG.SNPEn) is set, then RMP table must be
initialized up before calling SEV INIT.

In other words, if SNP_INIT(_EX) is not issued or fails then
SEV INIT will fail once SNP host support (SYSCFG.SNPEn) is enabled.

Fixes: 1ca5614b84eed ("crypto: ccp: Add support to initialize the AMD-SP for SEV-SNP")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 7 ++-----
 1 file changed, 2 insertions(+), 5 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 2e87ca0e292a..a0e3de94704e 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1112,7 +1112,7 @@ static int __sev_snp_init_locked(int *error)
 	if (!sev_version_greater_or_equal(SNP_MIN_API_MAJOR, SNP_MIN_API_MINOR)) {
 		dev_dbg(sev->dev, "SEV-SNP support requires firmware version >= %d:%d\n",
 			SNP_MIN_API_MAJOR, SNP_MIN_API_MINOR);
-		return 0;
+		return -EOPNOTSUPP;
 	}
 
 	/* SNP_INIT requires MSR_VM_HSAVE_PA to be cleared on all CPUs. */
@@ -1325,12 +1325,9 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	 */
 	rc = __sev_snp_init_locked(&args->error);
 	if (rc && rc != -ENODEV) {
-		/*
-		 * Don't abort the probe if SNP INIT failed,
-		 * continue to initialize the legacy SEV firmware.
-		 */
 		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
 			rc, args->error);
+		return rc;
 	}
 
 	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */

---

## [3] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 2/8] crypto: ccp: Move dev_info/err messages for SEV/SNP init and shutdown*

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

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 49 ++++++++++++++++++++++++------------
 1 file changed, 33 insertions(+), 16 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index a0e3de94704e..ccd7cc4b36d1 100644
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
 
@@ -1324,11 +1340,8 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	 * so perform SEV-SNP initialization at probe time.
 	 */
 	rc = __sev_snp_init_locked(&args->error);
-	if (rc && rc != -ENODEV) {
-		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
-			rc, args->error);
+	if (rc && rc != -ENODEV)
 		return rc;
-	}
 
 	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */
 	if (args->probe && !psp_init_on_probe)
@@ -1364,8 +1377,11 @@ static int __sev_platform_shutdown_locked(int *error)
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
@@ -1679,9 +1695,12 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	ret = __sev_do_cmd_locked(SEV_CMD_SNP_SHUTDOWN_EX, &data, error);
 	/* SHUTDOWN may require DF_FLUSH */
 	if (*error == SEV_RET_DFFLUSH_REQUIRED) {
-		ret = __sev_do_cmd_locked(SEV_CMD_SNP_DF_FLUSH, NULL, NULL);
+		int dfflush_error;
+
+		ret = __sev_do_cmd_locked(SEV_CMD_SNP_DF_FLUSH, NULL, &dfflush_error);
 		if (ret) {
-			dev_err(sev->dev, "SEV-SNP DF_FLUSH failed\n");
+			dev_err(sev->dev, "SEV-SNP DF_FLUSH failed, ret = %d, error = %#x\n",
+				ret, dfflush_error);
 			return ret;
 		}
 		/* reissue the shutdown command */
@@ -1689,7 +1708,8 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 					  error);
 	}
 	if (ret) {
-		dev_err(sev->dev, "SEV-SNP firmware shutdown failed\n");
+		dev_err(sev->dev, "SEV-SNP firmware shutdown failed, rc %d, error %#x\n",
+			ret, *error);
 		return ret;
 	}
 
@@ -2419,9 +2439,6 @@ void sev_pci_init(void)
 		dev_err(sev->dev, "SEV: failed to INIT error %#x, rc %d\n",
 			args.error, rc);
 
-	dev_info(sev->dev, "SEV%s API:%d.%d build:%d\n", sev->snp_initialized ?
-		"-SNP" : "", sev->api_major, sev->api_minor, sev->build);
-
 	atomic_notifier_chain_register(&panic_notifier_list,
 				       &snp_panic_notifier);
 	return;

---

## [4] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 3/8] crypto: ccp: Ensure implicit SEV/SNP init and shutdown in ioctls*

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

Also ensure that for these SEV ioctls both implicit SNP and SEV INIT is
done followed by both SEV and SNP shutdown as RMP table must be
initialized before calling SEV INIT if SNP host support is enabled.

Similarly, prior to this patch, SNP has always been initialized before
these ioctls as SNP initialization is done as part of PSP module probe,
therefore, to keep a consistent behavior, SNP init needs to be done
here implicitly as part of these ioctls followed with SNP shutdown
before returning from the ioctl to maintain the consistent platform
state before and after the ioctl.

Suggested-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 142 +++++++++++++++++++++++++++++------
 1 file changed, 119 insertions(+), 23 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index ccd7cc4b36d1..5bd3df377370 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -109,6 +109,8 @@ static void *sev_init_ex_buffer;
  */
 static struct sev_data_range_list *snp_range_list;
 
+static void __sev_firmware_shutdown(struct sev_device *sev, bool panic);
+
 static inline bool sev_version_greater_or_equal(u8 maj, u8 min)
 {
 	struct sev_device *sev = psp_master->sev_data;
@@ -1402,6 +1404,37 @@ static int sev_get_platform_state(int *state, int *error)
 	return rc;
 }
 
+static int sev_move_to_init_state(struct sev_issue_cmd *argp, bool *shutdown_required)
+{
+	struct sev_platform_init_args init_args = {0};
+	int rc;
+
+	rc = _sev_platform_init_locked(&init_args);
+	if (rc) {
+		argp->error = SEV_RET_INVALID_PLATFORM_STATE;
+		return rc;
+	}
+
+	*shutdown_required = true;
+
+	return 0;
+}
+
+static int snp_move_to_init_state(struct sev_issue_cmd *argp, bool *shutdown_required)
+{
+	int error, rc;
+
+	rc = __sev_snp_init_locked(&error);
+	if (rc) {
+		argp->error = SEV_RET_INVALID_PLATFORM_STATE;
+		return rc;
+	}
+
+	*shutdown_required = true;
+
+	return 0;
+}
+
 static int sev_ioctl_do_reset(struct sev_issue_cmd *argp, bool writable)
 {
 	int state, rc;
@@ -1454,24 +1487,31 @@ static int sev_ioctl_do_platform_status(struct sev_issue_cmd *argp)
 static int sev_ioctl_do_pek_pdh_gen(int cmd, struct sev_issue_cmd *argp, bool writable)
 {
 	struct sev_device *sev = psp_master->sev_data;
+	bool shutdown_required = false;
 	int rc;
 
 	if (!writable)
 		return -EPERM;
 
 	if (sev->state == SEV_STATE_UNINIT) {
-		rc = __sev_platform_init_locked(&argp->error);
+		rc = sev_move_to_init_state(argp, &shutdown_required);
 		if (rc)
 			return rc;
 	}
 
-	return __sev_do_cmd_locked(cmd, NULL, &argp->error);
+	rc = __sev_do_cmd_locked(cmd, NULL, &argp->error);
+
+	if (shutdown_required)
+		__sev_firmware_shutdown(sev, false);
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
@@ -1503,7 +1543,7 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 
 cmd:
 	if (sev->state == SEV_STATE_UNINIT) {
-		ret = __sev_platform_init_locked(&argp->error);
+		ret = sev_move_to_init_state(argp, &shutdown_required);
 		if (ret)
 			goto e_free_blob;
 	}
@@ -1524,6 +1564,9 @@ static int sev_ioctl_do_pek_csr(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_blob:
+	if (shutdown_required)
+		__sev_firmware_shutdown(sev, false);
+
 	kfree(blob);
 	return ret;
 }
@@ -1743,6 +1786,7 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_pek_cert_import input;
 	struct sev_data_pek_cert_import data;
+	bool shutdown_required = false;
 	void *pek_blob, *oca_blob;
 	int ret;
 
@@ -1773,7 +1817,7 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 
 	/* If platform is not in INIT state then transition it to INIT */
 	if (sev->state != SEV_STATE_INIT) {
-		ret = __sev_platform_init_locked(&argp->error);
+		ret = sev_move_to_init_state(argp, &shutdown_required);
 		if (ret)
 			goto e_free_oca;
 	}
@@ -1781,6 +1825,9 @@ static int sev_ioctl_do_pek_import(struct sev_issue_cmd *argp, bool writable)
 	ret = __sev_do_cmd_locked(SEV_CMD_PEK_CERT_IMPORT, &data, &argp->error);
 
 e_free_oca:
+	if (shutdown_required)
+		__sev_firmware_shutdown(sev, false);
+
 	kfree(oca_blob);
 e_free_pek:
 	kfree(pek_blob);
@@ -1897,18 +1944,9 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	struct sev_data_pdh_cert_export data;
 	void __user *input_cert_chain_address;
 	void __user *input_pdh_cert_address;
+	bool shutdown_required = false;
 	int ret;
 
-	/* If platform is not in INIT state then transition it to INIT. */
-	if (sev->state != SEV_STATE_INIT) {
-		if (!writable)
-			return -EPERM;
-
-		ret = __sev_platform_init_locked(&argp->error);
-		if (ret)
-			return ret;
-	}
-
 	if (copy_from_user(&input, (void __user *)argp->data, sizeof(input)))
 		return -EFAULT;
 
@@ -1948,6 +1986,17 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	data.cert_chain_len = input.cert_chain_len;
 
 cmd:
+	/* If platform is not in INIT state then transition it to INIT. */
+	if (sev->state != SEV_STATE_INIT) {
+		if (!writable) {
+			ret = -EPERM;
+			goto e_free_cert;
+		}
+		ret = sev_move_to_init_state(argp, &shutdown_required);
+		if (ret)
+			goto e_free_cert;
+	}
+
 	ret = __sev_do_cmd_locked(SEV_CMD_PDH_CERT_EXPORT, &data, &argp->error);
 
 	/* If we query the length, FW responded with expected data. */
@@ -1974,6 +2023,9 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
 	}
 
 e_free_cert:
+	if (shutdown_required)
+		__sev_firmware_shutdown(sev, false);
+
 	kfree(cert_blob);
 e_free_pdh:
 	kfree(pdh_blob);
@@ -1983,12 +2035,13 @@ static int sev_ioctl_do_pdh_export(struct sev_issue_cmd *argp, bool writable)
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
@@ -1997,6 +2050,12 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 
 	data = page_address(status_page);
 
+	if (!sev->snp_initialized) {
+		ret = snp_move_to_init_state(argp, &shutdown_required);
+		if (ret)
+			goto cleanup;
+	}
+
 	/*
 	 * Firmware expects status page to be in firmware-owned state, otherwise
 	 * it will report firmware error code INVALID_PAGE_STATE (0x1A).
@@ -2025,6 +2084,9 @@ static int sev_ioctl_do_snp_platform_status(struct sev_issue_cmd *argp)
 		ret = -EFAULT;
 
 cleanup:
+	if (shutdown_required)
+		__sev_snp_shutdown_locked(&error, false);
+
 	__free_pages(status_page, 0);
 	return ret;
 }
@@ -2033,21 +2095,33 @@ static int sev_ioctl_do_snp_commit(struct sev_issue_cmd *argp)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_data_snp_commit buf;
+	bool shutdown_required = false;
+	int ret, error;
 
-	if (!sev->snp_initialized)
-		return -EINVAL;
+	if (!sev->snp_initialized) {
+		ret = snp_move_to_init_state(argp, &shutdown_required);
+		if (ret)
+			return ret;
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
@@ -2056,17 +2130,29 @@ static int sev_ioctl_do_snp_set_config(struct sev_issue_cmd *argp, bool writable
 	if (copy_from_user(&config, (void __user *)argp->data, sizeof(config)))
 		return -EFAULT;
 
-	return __sev_do_cmd_locked(SEV_CMD_SNP_CONFIG, &config, &argp->error);
+	if (!sev->snp_initialized) {
+		ret = snp_move_to_init_state(argp, &shutdown_required);
+		if (ret)
+			return ret;
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
@@ -2085,8 +2171,18 @@ static int sev_ioctl_do_snp_vlek_load(struct sev_issue_cmd *argp, bool writable)
 
 	input.vlek_wrapped_address = __psp_pa(blob);
 
+	if (!sev->snp_initialized) {
+		ret = snp_move_to_init_state(argp, &shutdown_required);
+		if (ret)
+			goto cleanup;
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

## [5] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 4/8] crypto: ccp: Reset TMR size at SNP Shutdown*

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
index 5bd3df377370..08a6160f0072 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1778,6 +1778,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	sev->snp_initialized = false;
 	dev_dbg(sev->dev, "SEV-SNP firmware shutdown\n");
 
+	/* Reset TMR size back to default */
+	sev_es_tmr_size = SEV_TMR_SIZE;
+
 	return ret;
 }

---

## [6] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 5/8] crypto: ccp: Register SNP panic notifier only if SNP is enabled*

From: Ashish Kalra <ashish.kalra@amd.com>

Currently, the SNP panic notifier is registered on module initialization
regardless of whether SNP is being enabled or initialized.

Instead, register the SNP panic notifier only when SNP is actually
initialized and unregister the notifier when SNP is shutdown.

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>
Reviewed-by: Alexey Kardashevskiy <aik@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 22 +++++++++++++---------
 1 file changed, 13 insertions(+), 9 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 08a6160f0072..6fdbb3bf44b5 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -111,6 +111,13 @@ static struct sev_data_range_list *snp_range_list;
 
 static void __sev_firmware_shutdown(struct sev_device *sev, bool panic);
 
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
@@ -1200,6 +1207,9 @@ static int __sev_snp_init_locked(int *error)
 	dev_info(sev->dev, "SEV-SNP API:%d.%d build:%d\n", sev->api_major,
 		 sev->api_minor, sev->build);
 
+	atomic_notifier_chain_register(&panic_notifier_list,
+				       &snp_panic_notifier);
+
 	sev_es_tmr_size = SNP_TMR_SIZE;
 
 	return 0;
@@ -1778,6 +1788,9 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
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
@@ -2538,8 +2547,6 @@ void sev_pci_init(void)
 		dev_err(sev->dev, "SEV: failed to INIT error %#x, rc %d\n",
 			args.error, rc);
 
-	atomic_notifier_chain_register(&panic_notifier_list,
-				       &snp_panic_notifier);
 	return;
 
 err:
@@ -2556,7 +2563,4 @@ void sev_pci_exit(void)
 		return;
 
 	sev_firmware_shutdown(sev);
-
-	atomic_notifier_chain_unregister(&panic_notifier_list,
-					 &snp_panic_notifier);
 }

---

## [7] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 6/8] crypto: ccp: Add new SEV/SNP platform shutdown API*

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
index 6fdbb3bf44b5..671347702ae7 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2468,6 +2468,15 @@ static void sev_firmware_shutdown(struct sev_device *sev)
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

## [8] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 7/8] KVM: SVM: Add support to initialize SEV/SNP functionality in KVM*

From: Ashish Kalra <ashish.kalra@amd.com>

Move platform initialization of SEV/SNP from CCP driver probe time to
KVM module load time so that KVM can do SEV/SNP platform initialization
explicitly if it actually wants to use SEV/SNP functionality.

Add support for KVM to explicitly call into the CCP driver at load time
to initialize SEV/SNP. If required, this behavior can be altered with KVM
module parameters to not do SEV/SNP platform initialization at module load
time. Additionally, a corresponding SEV/SNP platform shutdown is invoked
during KVM module unload time.

Continue to support SEV deferred initialization as the user may have the
file containing SEV persistent data for SEV INIT_EX available only later
after module load/init.

Suggested-by: Sean Christopherson <seanjc@google.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 12 ++++++++++++
 1 file changed, 12 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 0bc708ee2788..7be4e1647903 100644
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
@@ -3059,6 +3060,15 @@ void __init sev_hardware_setup(void)
 	sev_supported_vmsa_features = 0;
 	if (sev_es_debug_swap_enabled)
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
+
+	if (!sev_enabled)
+		return;
+
+	/*
+	 * Do both SNP and SEV initialization at KVM module load.
+	 */
+	init_args.probe = true;
+	sev_platform_init(&init_args);
 }
 
 void sev_hardware_unsetup(void)
@@ -3074,6 +3084,8 @@ void sev_hardware_unsetup(void)
 
 	misc_cg_set_capacity(MISC_CG_RES_SEV, 0);
 	misc_cg_set_capacity(MISC_CG_RES_SEV_ES, 0);
+
+	sev_platform_shutdown();
 }
 
 int sev_cpu_init(struct svm_cpu_data *sd)

---

## [9] Ashish Kalra — 2025-03-06
*Subject: [PATCH v6 8/8] crypto: ccp: Move SEV/SNP Platform initialization to KVM*

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
 drivers/crypto/ccp/sev-dev.c | 13 -------------
 1 file changed, 13 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 671347702ae7..980b3d296dc6 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1347,10 +1347,6 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	if (sev->state == SEV_STATE_INIT)
 		return 0;
 
-	/*
-	 * Legacy guests cannot be running while SNP_INIT(_EX) is executing,
-	 * so perform SEV-SNP initialization at probe time.
-	 */
 	rc = __sev_snp_init_locked(&args->error);
 	if (rc && rc != -ENODEV)
 		return rc;
@@ -2524,9 +2520,7 @@ EXPORT_SYMBOL_GPL(sev_issue_cmd_external_user);
 void sev_pci_init(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
-	struct sev_platform_init_args args = {0};
 	u8 api_major, api_minor, build;
-	int rc;
 
 	if (!sev)
 		return;
@@ -2549,13 +2543,6 @@ void sev_pci_init(void)
 			 api_major, api_minor, build,
 			 sev->api_major, sev->api_minor, sev->build);
 
-	/* Initialize the platform */
-	args.probe = true;
-	rc = sev_platform_init(&args);
-	if (rc)
-		dev_err(sev->dev, "SEV: failed to INIT error %#x, rc %d\n",
-			args.error, rc);
-
 	return;
 
 err:

---

## [10] Tom Lendacky — 2025-03-07
*Subject: Re: [PATCH v6 1/8] crypto: ccp: Abort doing SEV INIT if SNP INIT
 fails*

On 3/6/25 17:09, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

s/RMP/the RMP/

> initialized up before calling SEV INIT.

s/up//

> 
> In other words, if SNP_INIT(_EX) is not issued or fails then

s/once/if/

> 
> Fixes: 1ca5614b84eed ("crypto: ccp: Add support to initialize the AMD-SP for SEV-SNP")

Can we get ride of this extra -ENODEV check? It can only be returned
because of the same check that is made earlier in this function so it
doesn't really serve any purpose from what I can tell.

Just make this "if (rc) {"

Thanks,
Tom

> -		/*
> -		 * Don't abort the probe if SNP INIT failed,

---

## [11] Tom Lendacky — 2025-03-07
*Subject: Re: [PATCH v6 1/8] crypto: ccp: Abort doing SEV INIT if SNP INIT
 fails*

On 3/7/25 14:54, Tom Lendacky wrote:
> On 3/6/25 17:09, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

My bad... -ENODEV is returned if cc_platform_has(CC_ATTR_HOST_SEV_SNP) is
false, never mind.

Thanks,
Tom

> 
> Thanks,

---

## [12] Kalra, Ashish — 2025-03-07
*Subject: Re: [PATCH v6 1/8] crypto: ccp: Abort doing SEV INIT if SNP INIT
 fails*

On 3/7/2025 2:57 PM, Tom Lendacky wrote:
> On 3/7/25 14:54, Tom Lendacky wrote:
>> On 3/6/25 17:09, Ashish Kalra wrote:

Yes, that's what i was going to reply with ... we want to continue with
SEV INIT if SNP host support is not enabled.

Thanks,
Ashish

> 
> Thanks,

---

## [13] Tom Lendacky — 2025-03-07
*Subject: Re: [PATCH v6 1/8] crypto: ccp: Abort doing SEV INIT if SNP INIT
 fails*

On 3/7/25 15:06, Kalra, Ashish wrote:
> On 3/7/2025 2:57 PM, Tom Lendacky wrote:
>> On 3/7/25 14:54, Tom Lendacky wrote:

Although we could get rid of that awkward if statement by doing...

	if (cc_platform_has(CC_ATTR_HOST_SEV_SNP)) {
		rc = __sev_snp_init_locked(&args->error);
		if (rc) {
			dev_err(sev->dev, ...
			return rc;
		}
	}

And deleting the cc_platform_has() check from __sev_snp_init_locked().

Thanks,
Tom

> 
> Thanks,

---

## [14] Tom Lendacky — 2025-03-07
*Subject: Re: [PATCH v6 3/8] crypto: ccp: Ensure implicit SEV/SNP init and
 shutdown in ioctls*

On 3/6/25 17:10, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  drivers/crypto/ccp/sev-dev.c | 142 +++++++++++++++++++++++++++++------

---

## [15] Kalra, Ashish — 2025-03-07
*Subject: Re: [PATCH v6 1/8] crypto: ccp: Abort doing SEV INIT if SNP INIT
 fails*

On 3/7/2025 3:29 PM, Tom Lendacky wrote:
> On 3/7/25 15:06, Kalra, Ashish wrote:
>> On 3/7/2025 2:57 PM, Tom Lendacky wrote:

We probably have to keep the cc_platform_has() check in
__sev_snp_init_locked() for the implicit SNP INIT being issued
for various SNP specific ioctl's (via snp_move_to_init_state()).

Thanks,
Ashish

>>>>
>>>>> -		/*

---

## [16] Tom Lendacky — 2025-03-07
*Subject: Re: [PATCH v6 1/8] crypto: ccp: Abort doing SEV INIT if SNP INIT
 fails*

On 3/7/25 15:39, Kalra, Ashish wrote:
> On 3/7/2025 3:29 PM, Tom Lendacky wrote:
>> On 3/7/25 15:06, Kalra, Ashish wrote:

Oh, yeah, the very next patch calls into __sev_snp_init_locked() now.

Thanks,
Tom

> 
> Thanks,

---

## [17] Kalra, Ashish — 2025-03-12
*Subject: Re: [PATCH v6 7/8] KVM: SVM: Add support to initialize SEV/SNP
 functionality in KVM*

Hello Sean,

On 3/6/2025 5:11 PM, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

I am looking for feedback on this patch.

Can we go ahead and merge this patch or are you looking for anything
to be changed specifically for this patch ?

The SNP CipherTextHiding support and SEV firmware hotloading patch-sets
are gated on this patch series, so it will be nice to have some feedback
on moving this patch-set forward.

Thanks,
Ashish

---
