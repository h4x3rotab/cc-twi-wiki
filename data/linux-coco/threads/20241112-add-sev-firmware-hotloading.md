---
title: 'Add SEV firmware hotloading'
date: 2024-11-12
last_reply: 2025-03-07
message_count: 23
participants: ['Dionna Glaze', 'Dan Williams', 'Tom Lendacky', 'Sean Christopherson', 'Russ Weight', 'Borislav Petkov', 'Herbert Xu']
---

## [1] Dionna Glaze — 2024-11-12

The SEV-SNP API specifies a command for hotloading the SEV firmware.
when no SEV or SEV-ES guests are running. The firmware hotloading
support is dependent on the firmware_upload API for better ease-of-use,
and to not necessarily require SEV firmware hotloading support when
building the ccp driver.

For safety, there are steps the kernel should take before allowing a
firmware to be committed:

1. Writeback invalidate all.
2. Data fabric flush.
3. All GCTX pages must be updated successfully with SNP_GUEST_STATUS

The snp_context_create function had the possibility to leak GCTX pages,
so the first patch fixes that bug in KVM. The second patch fixes the
error reporting for snp_context_create.

The ccp driver must continue to be unloadable, so the third patch in
this series fixes a cyclic refcount bug in firmware_loader.

The support for hotloading in ccp introduces new error values that can
be returned to user space, but there was an existing bug with firmware
error code number assignments, so the fourth patch fixes the uapi
definitions while adding the new needed error codes.

The fifth patch adds a new GCTX API for managing SNP context pages and
how they relate to the ASID allocated to the VM. This is needed because
once firmware is hotloaded, all GCTX pages must be updated before the
firmware is committed in order to avoid VM corruption. The ASID
association is to bound the number of pages that ccp must have capacity
to track.

The sixth patch adds SEV_CMD_DOWNLOAD_FIRMWARE_EX support with its
required cache invalidation steps. The command is made accessible not
through the ioctl interface, but with the firmware_upload API to prefer
the more generic API. The upload does _not_ commit the firmware since
there is necessary follow-up logic that should run before commit, and
a separate use of SNP_COMMIT also updates REPORTED_TCB, which might not
be what the operator wants. User space has to coordinate certificate
availability before updating REPORTED_TCB to provide correct behavior
for the extended guest request GHCB API.
When the firmware successfully updates, the GCTX pages are all
refreshed by iterating over the tracked pages from the GTX API.
If any single page's update fails, the drive treats itself as if the
firmware were in a bad state and needs an immediate restore. All
commands that are not DOWNLOAD_FIRMWARE_EX will fail with
RESTORE_REQUIRED, similar to SEV FW on older PSP bootloaders.

The seventh and eight patches are a small cleanup of how to manage
access to the SEV device that follows a similar pattern to kvm. This is
needed to not conflate access permissions with the GCTX API.

The ninth patch switches KVM over to use the new GCTX API.

The last patch avoids platform initialization for KVM VM guests when
vm_type is not legacy SEV/SEV-ES.

The KVM_EXIT for requesting certificates on extended guest request is
not part of this patch series. Any such support must be designed with
races between SNP_COMMIT and servicing extended guest requests such that
the REPORTED_TCB in an attestation_report always correctly corresponds
to the certificates returned by the extended guest request handler.

Changes from v5:
  - Fixed attribution for Alexey's error patch.
  - Removed the new access-checking method in favor of taking the device
    fd in the new API. A follow-up series should clean up the already
    existing over-checking of the fd.
  - Removed unnecessary name change in kvm.
  - Added comment about probe field use in KVM.
  - Added more error checking for asid argument values.
  - Made GCTX->guest context, asid->ASID changes in comments.
Changes from v4:
  - Added a snp_context_create error message fix to KVM.
  - Added a PSP error code fix from Alexey Kardashevskiy.
  - Changed tracking logic from command inspection to an explicit
    guest context API.
  - Switched KVM's SNP context management to the new API.
  - Separated sev_issue_cmd_external_user's permission logic into a
    different function that should be used to instead dominate calls
    that derive from external user actions.
  - Switched KVM to the new function to complete the deprecation of
    sev_issue_cmd_external_user.
  - Squashed download_firmware_ex and firmare_upload API instantiation
    since the former wasn't self-contained.
Changes from v3:
  - Removed added init_args field since it was duplicative of probe.
  - Split ccp change into three changes.
  - Included Alexey Kardashevskiy's memset(data_ex, 0, sizeof(*data_ex))
    fix.
Changes from v2:
  - Fix download_firmware_ex struct definition to be the proper size,
    and clear to 0 before using. Thanks to Alexey Kardashevskiy.
Changes from v1:
  - Fix double-free with incorrect goto label on error.
  - checkpatch cleanup.
  - firmware_loader comment cleanup and one-use local variable inlining.

Alexey Kardashevskiy (1):
  crypto: ccp: Fix uapi definitions of PSP errors

Dionna Glaze (7):
  KVM: SVM: Fix gctx page leak on invalid inputs
  KVM: SVM: Fix snp_context_create error reporting
  firmware_loader: Move module refcounts to allow unloading
  crypto: ccp: Add GCTX API to track ASID assignment
  crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support
  KVM: SVM: Use new ccp GCTX API
  KVM: SVM: Delay legacy platform initialization on SNP

 arch/x86/kvm/svm/sev.c                      |  72 ++---
 drivers/base/firmware_loader/sysfs_upload.c |  16 +-
 drivers/crypto/ccp/Kconfig                  |  10 +
 drivers/crypto/ccp/Makefile                 |   1 +
 drivers/crypto/ccp/sev-dev.c                | 186 ++++++++++++-
 drivers/crypto/ccp/sev-dev.h                |  35 +++
 drivers/crypto/ccp/sev-fw.c                 | 281 ++++++++++++++++++++
 include/linux/psp-sev.h                     |  72 +++++
 include/uapi/linux/psp-sev.h                |  21 +-
 9 files changed, 614 insertions(+), 80 deletions(-)
 create mode 100644 drivers/crypto/ccp/sev-fw.c

---

## [2] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 1/8] KVM: SVM: Fix gctx page leak on invalid inputs*

Ensure that snp gctx page allocation is adequately deallocated on
failure during snp_launch_start.

Fixes: 136d8bc931c8 ("KVM: SEV: Add KVM_SEV_SNP_LAUNCH_START command")

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>
CC: stable@vger.kernel.org

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
Acked-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/svm/sev.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index c6c8524859001..357906375ec59 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2212,10 +2212,6 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (sev->snp_context)
 		return -EINVAL;
 
-	sev->snp_context = snp_context_create(kvm, argp);
-	if (!sev->snp_context)
-		return -ENOTTY;
-
 	if (params.flags)
 		return -EINVAL;
 
@@ -2230,6 +2226,10 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (params.policy & SNP_POLICY_MASK_SINGLE_SOCKET)
 		return -EINVAL;
 
+	sev->snp_context = snp_context_create(kvm, argp);
+	if (!sev->snp_context)
+		return -ENOTTY;
+
 	start.gctx_paddr = __psp_pa(sev->snp_context);
 	start.policy = params.policy;
 	memcpy(start.gosvw, params.gosvw, sizeof(params.gosvw));

---

## [3] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 2/8] KVM: SVM: Fix snp_context_create error reporting*

Failure to allocate should not return -ENOTTY.
Command failure has multiple possible error modes.

Fixes: 136d8bc931c8 ("KVM: SEV: Add KVM_SEV_SNP_LAUNCH_START command")

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>
CC: stable@vger.kernel.org

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 arch/x86/kvm/svm/sev.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 357906375ec59..d0e0152aefb32 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2171,7 +2171,7 @@ static void *snp_context_create(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	/* Allocate memory for context page */
 	context = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT);
 	if (!context)
-		return NULL;
+		return ERR_PTR(-ENOMEM);
 
 	data.address = __psp_pa(context);
 	rc = __sev_issue_cmd(argp->sev_fd, SEV_CMD_SNP_GCTX_CREATE, &data, &argp->error);
@@ -2179,7 +2179,7 @@ static void *snp_context_create(struct kvm *kvm, struct kvm_sev_cmd *argp)
 		pr_warn("Failed to create SEV-SNP context, rc %d fw_error %d",
 			rc, argp->error);
 		snp_free_firmware_page(context);
-		return NULL;
+		return ERR_PTR(rc);
 	}
 
 	return context;
@@ -2227,8 +2227,8 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 		return -EINVAL;
 
 	sev->snp_context = snp_context_create(kvm, argp);
-	if (!sev->snp_context)
-		return -ENOTTY;
+	if (IS_ERR(sev->snp_context))
+		return PTR_ERR(sev->snp_context);
 
 	start.gctx_paddr = __psp_pa(sev->snp_context);
 	start.policy = params.policy;

---

## [4] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 3/8] firmware_loader: Move module refcounts to allow unloading*

If a kernel module registers a firmware upload API ops set, then it's
unable to be moved due to effectively a cyclic reference that the module
depends on the upload which depends on the module.

Instead, only require the try_module_get when an upload is requested to
disallow unloading a module only while the upload is in progress.

Fixes: 97730bbb242c ("firmware_loader: Add firmware-upload support")

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>

Tested-by: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Russ Weight <russ.weight@linux.dev>
Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 drivers/base/firmware_loader/sysfs_upload.c | 16 +++++++---------
 1 file changed, 7 insertions(+), 9 deletions(-)

diff --git a/drivers/base/firmware_loader/sysfs_upload.c b/drivers/base/firmware_loader/sysfs_upload.c
index 829270067d163..7d9c6aef7720a 100644
--- a/drivers/base/firmware_loader/sysfs_upload.c
+++ b/drivers/base/firmware_loader/sysfs_upload.c
@@ -204,6 +204,7 @@ static void fw_upload_main(struct work_struct *work)
 		fwlp->ops->cleanup(fwl);
 
 putdev_exit:
+	module_put(fwlp->module);
 	put_device(fw_dev->parent);
 
 	/*
@@ -239,6 +240,9 @@ int fw_upload_start(struct fw_sysfs *fw_sysfs)
 	}
 
 	fwlp = fw_sysfs->fw_upload_priv;
+	if (!try_module_get(fwlp->module)) /* released in fw_upload_main */
+		return -EFAULT;
+
 	mutex_lock(&fwlp->lock);
 
 	/* Do not interfere with an on-going fw_upload */
@@ -310,13 +314,10 @@ firmware_upload_register(struct module *module, struct device *parent,
 		return ERR_PTR(-EINVAL);
 	}
 
-	if (!try_module_get(module))
-		return ERR_PTR(-EFAULT);
-
 	fw_upload = kzalloc(sizeof(*fw_upload), GFP_KERNEL);
 	if (!fw_upload) {
 		ret = -ENOMEM;
-		goto exit_module_put;
+		goto exit_err;
 	}
 
 	fw_upload_priv = kzalloc(sizeof(*fw_upload_priv), GFP_KERNEL);
@@ -358,7 +359,7 @@ firmware_upload_register(struct module *module, struct device *parent,
 	if (ret) {
 		dev_err(fw_dev, "%s: device_register failed\n", __func__);
 		put_device(fw_dev);
-		goto exit_module_put;
+		goto exit_err;
 	}
 
 	return fw_upload;
@@ -372,8 +373,7 @@ firmware_upload_register(struct module *module, struct device *parent,
 free_fw_upload:
 	kfree(fw_upload);
 
-exit_module_put:
-	module_put(module);
+exit_err:
 
 	return ERR_PTR(ret);
 }
@@ -387,7 +387,6 @@ void firmware_upload_unregister(struct fw_upload *fw_upload)
 {
 	struct fw_sysfs *fw_sysfs = fw_upload->priv;
 	struct fw_upload_priv *fw_upload_priv = fw_sysfs->fw_upload_priv;
-	struct module *module = fw_upload_priv->module;
 
 	mutex_lock(&fw_upload_priv->lock);
 	if (fw_upload_priv->progress == FW_UPLOAD_PROG_IDLE) {
@@ -403,6 +402,5 @@ void firmware_upload_unregister(struct fw_upload *fw_upload)
 
 unregister:
 	device_unregister(&fw_sysfs->dev);
-	module_put(module);
 }
 EXPORT_SYMBOL_GPL(firmware_upload_unregister);

---

## [5] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 4/8] crypto: ccp: Fix uapi definitions of PSP errors*

From: Alexey Kardashevskiy <aik@amd.com>

Additions to the error enum after the explicit 0x27 setting for
SEV_RET_INVALID_KEY leads to incorrect value assignments.

Use explicit values to match the manufacturer specifications more
clearly.

Fixes: 3a45dc2b419e ("crypto: ccp: Define the SEV-SNP commands")

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>
CC: stable@vger.kernel.org

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 include/uapi/linux/psp-sev.h | 21 ++++++++++++++-------
 1 file changed, 14 insertions(+), 7 deletions(-)

diff --git a/include/uapi/linux/psp-sev.h b/include/uapi/linux/psp-sev.h
index 832c15d9155bd..eeb20dfb1fdaa 100644
--- a/include/uapi/linux/psp-sev.h
+++ b/include/uapi/linux/psp-sev.h
@@ -73,13 +73,20 @@ typedef enum {
 	SEV_RET_INVALID_PARAM,
 	SEV_RET_RESOURCE_LIMIT,
 	SEV_RET_SECURE_DATA_INVALID,
-	SEV_RET_INVALID_KEY = 0x27,
-	SEV_RET_INVALID_PAGE_SIZE,
-	SEV_RET_INVALID_PAGE_STATE,
-	SEV_RET_INVALID_MDATA_ENTRY,
-	SEV_RET_INVALID_PAGE_OWNER,
-	SEV_RET_INVALID_PAGE_AEAD_OFLOW,
-	SEV_RET_RMP_INIT_REQUIRED,
+	SEV_RET_INVALID_PAGE_SIZE          = 0x0019,
+	SEV_RET_INVALID_PAGE_STATE         = 0x001A,
+	SEV_RET_INVALID_MDATA_ENTRY        = 0x001B,
+	SEV_RET_INVALID_PAGE_OWNER         = 0x001C,
+	SEV_RET_AEAD_OFLOW                 = 0x001D,
+	SEV_RET_EXIT_RING_BUFFER           = 0x001F,
+	SEV_RET_RMP_INIT_REQUIRED          = 0x0020,
+	SEV_RET_BAD_SVN                    = 0x0021,
+	SEV_RET_BAD_VERSION                = 0x0022,
+	SEV_RET_SHUTDOWN_REQUIRED          = 0x0023,
+	SEV_RET_UPDATE_FAILED              = 0x0024,
+	SEV_RET_RESTORE_REQUIRED           = 0x0025,
+	SEV_RET_RMP_INITIALIZATION_FAILED  = 0x0026,
+	SEV_RET_INVALID_KEY                = 0x0027,
 	SEV_RET_MAX,
 } sev_ret_code;

---

## [6] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 5/8] crypto: ccp: Add GCTX API to track ASID assignment*

In preparation for SEV firmware hotloading support, introduce a new way
to create, activate, and decommission GCTX pages such that ccp is has
all GCTX pages available to update as needed.

Compliance with SEV-SNP API section 3.3 Firmware Updates and 4.1.1
Live Update: before a firmware is committed, all active GCTX pages
should be updated with SNP_GUEST_STATUS to ensure their data structure
remains consistent for the new firmware version.
There can only be CPUID 0x8000001f_EDX-1 many SEV-SNP asids in use at
one time, so this map associates asid to gctx in order to track which
addresses are active gctx pages that need updating. When an asid and
gctx page are decommissioned, the page is removed from tracking for
update-purposes.

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 drivers/crypto/ccp/sev-dev.c | 159 ++++++++++++++++++++++++++++++++++-
 drivers/crypto/ccp/sev-dev.h |   4 +
 include/linux/psp-sev.h      |  55 ++++++++++++
 3 files changed, 217 insertions(+), 1 deletion(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index af018afd9cd7f..d8c35b8478ff5 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -8,6 +8,7 @@
  */
 
 #include <linux/bitfield.h>
+#include <linux/file.h>
 #include <linux/module.h>
 #include <linux/kernel.h>
 #include <linux/kthread.h>
@@ -109,6 +110,10 @@ static void *sev_init_ex_buffer;
  */
 static struct sev_data_range_list *snp_range_list;
 
+/* SEV ASID data tracks resources associated with an ASID to safely manage operations. */
+struct sev_asid_data *sev_asid_data;
+u32 nr_asids, sev_min_asid, sev_es_max_asid;
+
 static inline bool sev_version_greater_or_equal(u8 maj, u8 min)
 {
 	struct sev_device *sev = psp_master->sev_data;
@@ -1093,6 +1098,109 @@ static int snp_filter_reserved_mem_regions(struct resource *rs, void *arg)
 	return 0;
 }
 
+static bool sev_check_external_user(int fd);
+void *sev_snp_create_context(int fd, int asid, int *psp_ret)
+{
+	struct sev_data_snp_addr data = {};
+	void *context;
+	int rc, error;
+
+	if (!sev_check_external_user(fd))
+		return ERR_PTR(-EBADF);
+
+	if (!sev_asid_data)
+		return ERR_PTR(-ENODEV);
+
+	if (asid < 0 || asid >= nr_asids)
+		return ERR_PTR(-EINVAL);
+
+	/* Can't create a context for a used ASID. */
+	if (WARN_ON_ONCE(sev_asid_data[asid].snp_context))
+		return ERR_PTR(-EBUSY);
+
+	/* Allocate memory for context page */
+	context = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT);
+	if (!context)
+		return ERR_PTR(-ENOMEM);
+
+	data.address = __psp_pa(context);
+	rc = sev_do_cmd(SEV_CMD_SNP_GCTX_CREATE, &data, &error);
+	if (rc) {
+		pr_warn("Failed to create SEV-SNP context, rc=%d fw_error=0x%x",
+			rc, error);
+		if (psp_ret)
+			*psp_ret = error;
+		snp_free_firmware_page(context);
+		return ERR_PTR(-EIO);
+	}
+
+	sev_asid_data[asid].snp_context = context;
+
+	return context;
+}
+EXPORT_SYMBOL_GPL(sev_snp_create_context);
+
+int sev_snp_activate_asid(int fd, int asid, int *psp_ret)
+{
+	struct sev_data_snp_activate data = {0};
+	void *context;
+
+	if (!sev_check_external_user(fd))
+		return -EBADF;
+
+	if (!sev_asid_data)
+		return -ENODEV;
+
+	if (asid < 0 || asid >= nr_asids)
+		return -EINVAL;
+
+	context = sev_asid_data[asid].snp_context;
+	if (WARN_ON_ONCE(!context))
+		return -EINVAL;
+
+	data.gctx_paddr = __psp_pa(context);
+	data.asid = asid;
+	return sev_do_cmd(SEV_CMD_SNP_ACTIVATE, &data, psp_ret);
+}
+EXPORT_SYMBOL_GPL(sev_snp_activate_asid);
+
+int sev_snp_guest_decommission(int fd, int asid, int *psp_ret)
+{
+	struct sev_data_snp_addr addr = {};
+	struct sev_asid_data *data;
+	int ret, error;
+
+	if (!sev_check_external_user(fd))
+		return -EBADF;
+
+	if (!sev_asid_data)
+		return -ENODEV;
+
+	if (asid < 0 || asid >= nr_asids)
+		return -EINVAL;
+
+	data = &sev_asid_data[asid];
+	/* If context is not created then do nothing */
+	if (!data->snp_context)
+		return 0;
+
+	/* Do the decommission, which will unbind the ASID from the SNP context */
+	addr.address = __sme_pa(data->snp_context);
+	ret = sev_do_cmd(SEV_CMD_SNP_DECOMMISSION, &addr, &error);
+
+	if (WARN_ONCE(ret, "Failed to release guest context, rc=%d, fw_error=0x%x", ret, error)) {
+		if (psp_ret)
+			*psp_ret = error;
+		return ret;
+	}
+
+	snp_free_firmware_page(data->snp_context);
+	data->snp_context = NULL;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(sev_snp_guest_decommission);
+
 static int __sev_snp_init_locked(int *error)
 {
 	struct psp_device *psp = psp_master;
@@ -1306,6 +1414,27 @@ static int __sev_platform_init_locked(int *error)
 	return 0;
 }
 
+static int sev_asid_data_init(void)
+{
+	u32 eax, ebx, ecx;
+
+	if (sev_asid_data)
+		return 0;
+
+	cpuid(0x8000001f, &eax, &ebx, &ecx, &sev_min_asid);
+	if (!ecx)
+		return -ENODEV;
+
+	nr_asids = ecx + 1;
+	sev_es_max_asid = sev_min_asid - 1;
+
+	sev_asid_data = kcalloc(nr_asids, sizeof(*sev_asid_data), GFP_KERNEL);
+	if (!sev_asid_data)
+		return -ENOMEM;
+
+	return 0;
+}
+
 static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 {
 	struct sev_device *sev;
@@ -1319,6 +1448,10 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	if (sev->state == SEV_STATE_INIT)
 		return 0;
 
+	rc = sev_asid_data_init();
+	if (rc)
+		return rc;
+
 	/*
 	 * Legacy guests cannot be running while SNP_INIT(_EX) is executing,
 	 * so perform SEV-SNP initialization at probe time.
@@ -2329,6 +2462,9 @@ static void __sev_firmware_shutdown(struct sev_device *sev, bool panic)
 		snp_range_list = NULL;
 	}
 
+	kfree(sev_asid_data);
+	sev_asid_data = NULL;
+
 	__sev_snp_shutdown_locked(&error, panic);
 }
 
@@ -2377,10 +2513,31 @@ static struct notifier_block snp_panic_notifier = {
 	.notifier_call = snp_shutdown_on_panic,
 };
 
+static bool file_is_sev(struct file *filep)
+{
+	return filep && filep->f_op == &sev_fops;
+}
+
+static bool sev_check_external_user(int fd)
+{
+	struct fd f;
+	bool ret = true;
+
+	f = fdget(fd);
+	if (!fd_file(f))
+		return false;
+
+	if (!file_is_sev(fd_file(f)))
+		ret = false;
+
+	fdput(f);
+	return ret;
+}
+
 int sev_issue_cmd_external_user(struct file *filep, unsigned int cmd,
 				void *data, int *error)
 {
-	if (!filep || filep->f_op != &sev_fops)
+	if (!file_is_sev(filep))
 		return -EBADF;
 
 	return sev_do_cmd(cmd, data, error);
diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index 3e4e5574e88a3..ccf3ba78d8332 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -65,4 +65,8 @@ void sev_dev_destroy(struct psp_device *psp);
 void sev_pci_init(void);
 void sev_pci_exit(void);
 
+struct sev_asid_data {
+	void *snp_context;
+};
+
 #endif /* __SEV_DEV_H */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 903ddfea85850..0b3b7707ccb21 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -942,6 +942,61 @@ int sev_guest_decommission(struct sev_data_decommission *data, int *error);
  */
 int sev_do_cmd(int cmd, void *data, int *psp_ret);
 
+/**
+ * sev_snp_create_context - allocates an SNP context firmware page
+ *
+ * Associates the created context with the ASID that an activation
+ * call after SNP_LAUNCH_START will commit. The association is needed
+ * to track active guest context pages to refresh during firmware hotload.
+ *
+ * @fd:      A file descriptor for the SEV device
+ * @asid:    The ASID allocated to the caller that will be used in a subsequent SNP_ACTIVATE.
+ * @psp_ret: sev command return code.
+ *
+ * Returns:
+ * A pointer to the SNP context page, or an ERR_PTR of
+ * -%ENODEV    if the PSP device is not available
+ * -%ENOTSUPP  if PSP device does not support SEV
+ * -%ETIMEDOUT if the SEV command timed out
+ * -%EIO       if PSP device returned a non-zero return code
+ */
+void *sev_snp_create_context(int fd, int asid, int *psp_ret);
+
+/**
+ * sev_snp_activate_asid - issues SNP_ACTIVATE for the ASID and associated guest context page.
+ *
+ * @fd:      A file descriptor for the SEV device
+ * @asid:    The ASID to activate.
+ * @psp_ret: sev command return code.
+ *
+ * Returns:
+ * 0 if the SEV device successfully processed the command
+ * -%ENODEV    if the PSP device is not available
+ * -%ENOTSUPP  if PSP device does not support SEV
+ * -%ETIMEDOUT if the SEV command timed out
+ * -%EIO       if PSP device returned a non-zero return code
+ */
+int sev_snp_activate_asid(int fd, int asid, int *psp_ret);
+
+/**
+ * sev_snp_guest_decommission - issues SNP_DECOMMISSION for an ASID's guest context page, and frees
+ * it.
+ *
+ * The caller must ensure mutual exclusion with any process that may deactivate ASIDs.
+ *
+ * @fd:      A file descriptor for the SEV device
+ * @asid:    The ASID to activate.
+ * @psp_ret: sev command return code.
+ *
+ * Returns:
+ * 0 if the SEV device successfully processed the command
+ * -%ENODEV    if the PSP device is not available
+ * -%ENOTSUPP  if PSP device does not support SEV
+ * -%ETIMEDOUT if the SEV command timed out
+ * -%EIO       if PSP device returned a non-zero return code
+ */
+int sev_snp_guest_decommission(int fd, int asid, int *psp_ret);
+
 void *psp_copy_user_blob(u64 uaddr, u32 len);
 void *snp_alloc_firmware_page(gfp_t mask);
 void snp_free_firmware_page(void *addr);

---

## [7] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 6/8] crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support*

In order to support firmware hotloading, the DOWNLOAD_FIRMWARE_EX
command must be available.

The DOWNLOAD_FIRMWARE_EX command requires cache flushing and introduces
new error codes that could be returned to user space.

Access to the command is through the firmware_upload API rather than
through the ioctl interface to prefer a common interface.

On init, the ccp device will make /sys/class/firmware/amd/loading etc
firmware upload API attributes available to late-load a SEV-SNP firmware
binary.

The firmware_upload API errors reported are actionable in the following
ways:
* FW_UPLOAD_ERR_HW_ERROR: the machine is in an unstable state and must
  be reset.
* FW_UPLOAD_ERR_RW_ERROR: the firmware update went bad but can be
  recovered by hotloading the previous firmware version.
  Also used in the case that the kernel used the API wrong (bug).
* FW_UPLOAD_ERR_FW_INVALID: user error with the data provided, but no
  instability is expected and no recovery actions are needed.
* FW_UPLOAD_ERR_BUSY: upload attempted at a bad time either due to
  overload or the machine is in the wrong platform state.

synthetic_restore_required:
Instead of tracking the status of whether an individual GCTX is safe for
use in a firmware command, force all following commands to fail with an
error that is indicative of needing a firmware rollback.

To test:
1. Build the kernel enabling SEV-SNP as normal and add CONFIG_FW_UPLOAD=y.
2. Add the following to your kernel_cmdline: ccp.psp_init_on_probe=0.
3.Get an AMD SEV-SNP firmware sbin appropriate to your Epyc chip model at
https://www.amd.com/en/developer/sev.html and extract to get a .sbin
file.
4. Run the following with your sbinfile in FW:

echo 1 > /sys/class/firmware/snp_dlfw_ex/loading
cat "${FW?}" > /sys/class/firmware/snp_dlfw_ex/data
echo 0 > /sys/class/firmware/snp_dlfw_ex/loading

5. Verify the firmware update message in dmesg.

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>

Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 drivers/crypto/ccp/Kconfig   |  10 ++
 drivers/crypto/ccp/Makefile  |   1 +
 drivers/crypto/ccp/sev-dev.c |  27 ++--
 drivers/crypto/ccp/sev-dev.h |  31 ++++
 drivers/crypto/ccp/sev-fw.c  | 281 +++++++++++++++++++++++++++++++++++
 include/linux/psp-sev.h      |  17 +++
 6 files changed, 357 insertions(+), 10 deletions(-)
 create mode 100644 drivers/crypto/ccp/sev-fw.c

diff --git a/drivers/crypto/ccp/Kconfig b/drivers/crypto/ccp/Kconfig
index f394e45e11ab4..40be991f15d28 100644
--- a/drivers/crypto/ccp/Kconfig
+++ b/drivers/crypto/ccp/Kconfig
@@ -46,6 +46,16 @@ config CRYPTO_DEV_SP_PSP
 	 along with software-based Trusted Execution Environment (TEE) to
 	 enable third-party trusted applications.
 
+config CRYPTO_DEV_SP_PSP_FW_UPLOAD
+	bool "Platform Security Processor (PSP) device with firmware hotloading"
+	default y
+	depends on CRYPTO_DEV_SP_PSP && FW_LOADER && FW_UPLOAD
+	help
+	 Provide support for AMD Platform Security Processor firmware.
+	 The PSP firmware can be updated while no SEV or SEV-ES VMs are active.
+	 Users of this feature should be aware of the error modes that indicate
+	 required manual rollback or reset due to instablity.
+
 config CRYPTO_DEV_CCP_DEBUGFS
 	bool "Enable CCP Internals in DebugFS"
 	default n
diff --git a/drivers/crypto/ccp/Makefile b/drivers/crypto/ccp/Makefile
index 394484929dae3..5ce69134ec48b 100644
--- a/drivers/crypto/ccp/Makefile
+++ b/drivers/crypto/ccp/Makefile
@@ -14,6 +14,7 @@ ccp-$(CONFIG_CRYPTO_DEV_SP_PSP) += psp-dev.o \
                                    platform-access.o \
                                    dbc.o \
                                    hsti.o
+ccp-$(CONFIG_CRYPTO_DEV_SP_PSP_FW_UPLOAD) += sev-fw.o
 
 obj-$(CONFIG_CRYPTO_DEV_CCP_CRYPTO) += ccp-crypto.o
 ccp-crypto-objs := ccp-crypto-main.o \
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index d8c35b8478ff5..a8f5e35ab8a0a 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -228,6 +228,7 @@ static int sev_cmd_buffer_len(int cmd)
 	case SEV_CMD_SNP_GUEST_REQUEST:		return sizeof(struct sev_data_snp_guest_request);
 	case SEV_CMD_SNP_CONFIG:		return sizeof(struct sev_user_data_snp_config);
 	case SEV_CMD_SNP_COMMIT:		return sizeof(struct sev_data_snp_commit);
+	case SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX:	return sizeof(struct sev_data_download_firmware_ex);
 	default:				return 0;
 	}
 
@@ -489,7 +490,7 @@ void snp_free_firmware_page(void *addr)
 }
 EXPORT_SYMBOL_GPL(snp_free_firmware_page);
 
-static void *sev_fw_alloc(unsigned long len)
+void *sev_fw_alloc(unsigned long len)
 {
 	struct page *page;
 
@@ -857,6 +858,15 @@ static int __sev_do_cmd_locked(int cmd, void *data, int *psp_ret)
 	if (WARN_ON_ONCE(!data != !buf_len))
 		return -EINVAL;
 
+	/* Firmware hotloading can fail to update some guest context pages, in which case
+	 * user space should roll back the firmware instead of committing it. This is already
+	 * a firmware error code called RESTORE_REQUIRED, so report that error if VMs would
+	 * be corrupted if user space were to commit the firmware.
+	 */
+	ret = sev_snp_synthetic_error(sev, psp_ret);
+	if (ret)
+		return ret;
+
 	/*
 	 * Copy the incoming data to driver's scratch buffer as __pa() will not
 	 * work for some memory, e.g. vmalloc'd addresses, and @data may not be
@@ -1661,7 +1671,7 @@ void *psp_copy_user_blob(u64 uaddr, u32 len)
 }
 EXPORT_SYMBOL_GPL(psp_copy_user_blob);
 
-static int sev_get_api_version(void)
+int sev_get_api_version(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_status status;
@@ -1736,14 +1746,7 @@ static int sev_update_firmware(struct device *dev)
 		return -1;
 	}
 
-	/*
-	 * SEV FW expects the physical address given to it to be 32
-	 * byte aligned. Memory allocated has structure placed at the
-	 * beginning followed by the firmware being passed to the SEV
-	 * FW. Allocate enough memory for data structure + alignment
-	 * padding + SEV FW.
-	 */
-	data_size = ALIGN(sizeof(struct sev_data_download_firmware), 32);
+	data_size = ALIGN(sizeof(struct sev_data_download_firmware), SEV_FW_ALIGNMENT);
 
 	order = get_order(firmware->size + data_size);
 	p = alloc_pages(GFP_KERNEL, order);
@@ -2407,6 +2410,8 @@ int sev_dev_init(struct psp_device *psp)
 	if (ret)
 		goto e_irq;
 
+	snp_init_firmware_upload(sev);
+
 	dev_notice(dev, "sev enabled\n");
 
 	return 0;
@@ -2488,6 +2493,8 @@ void sev_dev_destroy(struct psp_device *psp)
 		kref_put(&misc_dev->refcount, sev_exit);
 
 	psp_clear_sev_irq_handler(psp);
+
+	snp_destroy_firmware_upload(sev);
 }
 
 static int snp_shutdown_on_panic(struct notifier_block *nb,
diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index ccf3ba78d8332..2417bcce97848 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -29,6 +29,15 @@
 #define SEV_CMD_COMPLETE		BIT(1)
 #define SEV_CMDRESP_IOC			BIT(0)
 
+/*
+ * SEV FW expects the physical address given to it to be 32
+ * byte aligned. Memory allocated has structure placed at the
+ * beginning followed by the firmware being passed to the SEV
+ * FW. Allocate enough memory for data structure + alignment
+ * padding + SEV FW.
+ */
+#define SEV_FW_ALIGNMENT       32
+
 struct sev_misc_dev {
 	struct kref refcount;
 	struct miscdevice misc;
@@ -57,6 +66,11 @@ struct sev_device {
 	bool cmd_buf_backup_active;
 
 	bool snp_initialized;
+
+#ifdef CONFIG_FW_UPLOAD
+	struct fw_upload *fwl;
+	bool fw_cancel;
+#endif /* CONFIG_FW_UPLOAD */
 };
 
 int sev_dev_init(struct psp_device *psp);
@@ -69,4 +83,21 @@ struct sev_asid_data {
 	void *snp_context;
 };
 
+/* Extern to be shared with firmware_upload API implementation if configured. */
+extern struct sev_asid_data *sev_asid_data;
+extern u32 nr_asids, sev_min_asid, sev_max_asid, sev_es_max_asid;
+
+void *sev_fw_alloc(unsigned long len);
+int sev_get_api_version(void);
+
+#ifdef CONFIG_CRYPTO_DEV_SP_PSP_FW_UPLOAD
+void snp_init_firmware_upload(struct sev_device *sev);
+void snp_destroy_firmware_upload(struct sev_device *sev);
+int sev_snp_synthetic_error(struct sev_device *sev, int *psp_ret);
+#else
+static inline void snp_init_firmware_upload(struct sev_device *sev) { }
+static inline void snp_destroy_firmware_upload(struct sev_device *sev) { }
+static inline int sev_snp_synthetic_error(struct sev_device *sev, int *psp_ret) { return 0; }
+#endif /* CONFIG_CRYPTO_DEV_SP_PSP_FW_UPLOAD */
+
 #endif /* __SEV_DEV_H */
diff --git a/drivers/crypto/ccp/sev-fw.c b/drivers/crypto/ccp/sev-fw.c
new file mode 100644
index 0000000000000..327feb846e5be
--- /dev/null
+++ b/drivers/crypto/ccp/sev-fw.c
@@ -0,0 +1,281 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * AMD Secure Encrypted Virtualization (SEV) firmware upload API
+ */
+
+#include <linux/firmware.h>
+#include <linux/psp.h>
+#include <linux/psp-sev.h>
+
+#include <asm/sev.h>
+
+#include "sev-dev.h"
+
+static bool synthetic_restore_required;
+
+int sev_snp_synthetic_error(struct sev_device *sev, int *psp_ret)
+{
+	if (synthetic_restore_required) {
+		*psp_ret = SEV_RET_RESTORE_REQUIRED;
+		return -EIO;
+	}
+
+	return 0;
+}
+
+static int sev_snp_download_firmware_ex(struct sev_device *sev, const u8 *data, u32 size,
+					int *error)
+{
+	struct sev_data_download_firmware_ex *data_ex;
+	int ret, order;
+	struct page *p;
+	u64 data_size;
+	void *fw_dest;
+
+	data_size = ALIGN(sizeof(struct sev_data_download_firmware_ex), SEV_FW_ALIGNMENT);
+
+	order = get_order(size + data_size);
+	p = alloc_pages(GFP_KERNEL, order);
+	if (!p)
+		return -ENOMEM;
+
+	/*
+	 * Copy firmware data to a kernel allocated contiguous
+	 * memory region.
+	 */
+	data_ex = page_address(p);
+	fw_dest = page_address(p) + data_size;
+	memset(data_ex, 0, data_size);
+	memcpy(fw_dest, data, size);
+
+	/* commit is purposefully unset for GCTX update failure to advise rollback */
+	data_ex->fw_paddr = __psp_pa(fw_dest);
+	data_ex->fw_len = size;
+	data_ex->length = sizeof(struct sev_data_download_firmware_ex);
+
+	ret = sev_do_cmd(SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX, data_ex, error);
+
+	if (ret)
+		goto free_err;
+
+	/* Need to do a DF_FLUSH after live firmware update */
+	wbinvd_on_all_cpus();
+	ret = sev_do_cmd(SEV_CMD_SNP_DF_FLUSH, NULL, error);
+	if (ret)
+		dev_dbg(sev->dev, "DF_FLUSH error %d\n", *error);
+
+free_err:
+	__free_pages(p, order);
+	return ret;
+}
+
+static enum fw_upload_err snp_dlfw_ex_prepare(struct fw_upload *fw_upload,
+					      const u8 *data, u32 size)
+{
+	struct sev_device *sev = fw_upload->dd_handle;
+
+	sev->fw_cancel = false;
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static enum fw_upload_err snp_dlfw_ex_poll_complete(struct fw_upload *fw_upload)
+{
+	return FW_UPLOAD_ERR_NONE;
+}
+
+/* Cancel can be called asynchronously, but DOWNLOAD_FIRMWARE_EX is atomic and cannot
+ * be canceled. There is no need to synchronize updates to fw_cancel.
+ */
+static void snp_dlfw_ex_cancel(struct fw_upload *fw_upload)
+{
+	/* fw_upload not-NULL guaranteed by firmware_upload API */
+	struct sev_device *sev = fw_upload->dd_handle;
+
+	sev->fw_cancel = true;
+}
+
+static enum fw_upload_err snp_dlfw_ex_err_translate(struct sev_device *sev, int psp_ret)
+{
+	dev_dbg(sev->dev, "Failed to update SEV firmware: %#x\n", psp_ret);
+
+	/*
+	 * Operation error:
+	 *   HW_ERROR: Critical error. Machine needs repairs now.
+	 *   RW_ERROR: Severe error. Roll back to the prior version to recover.
+	 * User error:
+	 *   FW_INVALID: Bad input for this interface.
+	 *   BUSY: Wrong machine state to run download_firmware_ex.
+	 */
+	switch (psp_ret) {
+	case SEV_RET_RESTORE_REQUIRED:
+		dev_warn(sev->dev, "Firmware updated but unusable. Rollback!!!\n");
+		return FW_UPLOAD_ERR_RW_ERROR;
+	case SEV_RET_SHUTDOWN_REQUIRED:
+		/* No state changes made. Not a hardware error. */
+		dev_warn(sev->dev, "Firmware image cannot be live updated\n");
+		return FW_UPLOAD_ERR_FW_INVALID;
+	case SEV_RET_BAD_VERSION:
+		/* No state changes made. Not a hardware error. */
+		dev_warn(sev->dev, "Firmware image is not well formed\n");
+		return FW_UPLOAD_ERR_FW_INVALID;
+		/* SEV-specific errors that can still happen. */
+	case SEV_RET_BAD_SIGNATURE:
+		/* No state changes made. Not a hardware error. */
+		dev_warn(sev->dev, "Firmware image signature is bad\n");
+		return FW_UPLOAD_ERR_FW_INVALID;
+	case SEV_RET_INVALID_PLATFORM_STATE:
+		/* Calling at the wrong time. Not a hardware error. */
+		dev_warn(sev->dev, "Firmware not updated as SEV in INIT state\n");
+		return FW_UPLOAD_ERR_BUSY;
+	case SEV_RET_HWSEV_RET_UNSAFE:
+		dev_err(sev->dev, "Firmware is unstable. Reset your machine!!!\n");
+		return FW_UPLOAD_ERR_HW_ERROR;
+		/* Kernel bug cases. */
+	case SEV_RET_INVALID_PARAM:
+		dev_err(sev->dev, "Download-firmware-EX invalid parameter\n");
+		return FW_UPLOAD_ERR_RW_ERROR;
+	case SEV_RET_INVALID_ADDRESS:
+		dev_err(sev->dev, "Download-firmware-EX invalid address\n");
+		return FW_UPLOAD_ERR_RW_ERROR;
+	default:
+		dev_err(sev->dev, "Unhandled download_firmware_ex err %d\n", psp_ret);
+		return FW_UPLOAD_ERR_HW_ERROR;
+	}
+}
+
+static enum fw_upload_err snp_update_guest_contexts(struct sev_device *sev)
+{
+	struct sev_data_snp_guest_status status_data;
+	void *snp_guest_status;
+	enum fw_upload_err ret = FW_UPLOAD_ERR_NONE;
+	int rc, error;
+
+	/*
+	 * Force an update of guest context pages after SEV firmware
+	 * live update by issuing SNP_GUEST_STATUS on all guest
+	 * context pages.
+	 */
+	snp_guest_status = sev_fw_alloc(PAGE_SIZE);
+	if (!snp_guest_status)
+		return FW_UPLOAD_ERR_INVALID_SIZE;
+
+	for (int i = 1; i <= sev_es_max_asid; i++) {
+		if (!sev_asid_data[i].snp_context)
+			continue;
+
+		status_data.gctx_paddr = __psp_pa(sev_asid_data[i].snp_context);
+		status_data.address = __psp_pa(snp_guest_status);
+		rc = sev_do_cmd(SEV_CMD_SNP_GUEST_STATUS, &status_data, &error);
+		if (!rc)
+			continue;
+
+		/*
+		 * Handle race with SNP VM being destroyed/decommissoned,
+		 * if guest context page invalid error is returned,
+		 * assume guest has been destroyed.
+		 */
+		if (error == SEV_RET_INVALID_GUEST)
+			continue;
+
+		/* Guest context page update failure should force userspace to rollback,
+		 * so make all non-DOWNLOAD_FIRMWARE_EX commands fail with RESTORE_REQUIRED.
+		 * This emulates the behavior of the firmware on an older PSP bootloader version
+		 * that couldn't auto-restore on DOWNLOAD_FIRMWARE_EX failure. However, the error
+		 * is still relevant to this follow-up guest update failure.
+		 */
+		synthetic_restore_required = true;
+		dev_err(sev->dev,
+			"SNP guest context update error, rc=%d, fw_error=0x%x. Rollback!!!\n",
+			rc, error);
+		ret = FW_UPLOAD_ERR_RW_ERROR;
+		break;
+	}
+
+	snp_free_firmware_page(snp_guest_status);
+	return ret;
+}
+
+static enum fw_upload_err snp_dlfw_ex_write(struct fw_upload *fwl, const u8 *data,
+					    u32 offset, u32 size, u32 *written)
+{
+	/* fwl not-NULL guaranteed by firmware_upload API, and sev is non-NULL by precondition to
+	 * snp_init_firmware_upload.
+	 */
+	struct sev_device *sev = fwl->dd_handle;
+	u8 api_major, api_minor, build;
+	int ret, error;
+
+	if (!sev)
+		return FW_UPLOAD_ERR_HW_ERROR;
+
+	if (sev->fw_cancel)
+		return FW_UPLOAD_ERR_CANCELED;
+
+	/*
+	 * SEV firmware update is a one-shot update operation, the write()
+	 * callback to be invoked multiple times for the same update is
+	 * unexpected.
+	 */
+	if (offset)
+		return FW_UPLOAD_ERR_INVALID_SIZE;
+
+	if (sev_get_api_version())
+		return FW_UPLOAD_ERR_HW_ERROR;
+
+	api_major = sev->api_major;
+	api_minor = sev->api_minor;
+	build     = sev->build;
+
+	ret = sev_snp_download_firmware_ex(sev, data, size, &error);
+	if (ret)
+		return snp_dlfw_ex_err_translate(sev, error);
+
+	ret = snp_update_guest_contexts(sev);
+	if (ret)
+		return ret;
+
+	sev_get_api_version();
+	if (api_major != sev->api_major || api_minor != sev->api_minor ||
+	    build != sev->build) {
+		dev_info(sev->dev, "SEV firmware updated from %d.%d.%d to %d.%d.%d\n",
+			 api_major, api_minor, build,
+			 sev->api_major, sev->api_minor, sev->build);
+	} else {
+		dev_info(sev->dev, "SEV firmware not updated, same as current version %d.%d.%d\n",
+			 api_major, api_minor, build);
+	}
+
+	*written = size;
+
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static const struct fw_upload_ops snp_dlfw_ex_ops = {
+	.prepare = snp_dlfw_ex_prepare,
+	.write = snp_dlfw_ex_write,
+	.poll_complete = snp_dlfw_ex_poll_complete,
+	.cancel = snp_dlfw_ex_cancel,
+};
+
+/* PREREQUISITE: sev is non-NULL */
+void snp_init_firmware_upload(struct sev_device *sev)
+{
+	struct fw_upload *fwl;
+
+	fwl = firmware_upload_register(THIS_MODULE, sev->dev, "snp_dlfw_ex", &snp_dlfw_ex_ops, sev);
+	if (IS_ERR(fwl)) {
+		dev_err(sev->dev, "SEV firmware upload initialization error %ld\n", PTR_ERR(fwl));
+		return;
+	}
+
+	sev->fwl = fwl;
+}
+
+/* PREREQUISITE: sev is non-NULL */
+void snp_destroy_firmware_upload(struct sev_device *sev)
+{
+	if (!sev->fwl)
+		return;
+
+	firmware_upload_unregister(sev->fwl);
+}
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 0b3b7707ccb21..9ad941e36bb63 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -185,6 +185,23 @@ struct sev_data_download_firmware {
 	u32 len;				/* In */
 } __packed;
 
+/**
+ * struct sev_data_download_firmware_ex - DOWNLOAD_FIRMWARE_EX command parameters
+ *
+ * @length: length of this command buffer
+ * @fw_paddr: physical address of firmware image
+ * @fw_len: len of the firmware image
+ * @commit: automatically commit the newly installed image
+ */
+struct sev_data_download_firmware_ex {
+	u32 length;				/* In */
+	u32 reserved;				/* In */
+	u64 fw_paddr;				/* In */
+	u32 fw_len;				/* In */
+	u32 commit:1;				/* In */
+	u32 reserved2:31;			/* In */
+} __packed;
+
 /**
  * struct sev_data_get_id - GET_ID command parameters
  *

---

## [8] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 7/8] KVM: SVM: Use new ccp GCTX API*

Guest context pages should be near 1-to-1 with allocated ASIDs. With the
GCTX API, the ccp driver is better able to associate guest context pages
with the ASID that is/will be bound to it.

This is important to the firmware hotloading implementation to not
corrupt any running VM's guest context page before userspace commits a
new firmware.

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 arch/x86/kvm/svm/sev.c | 60 ++++++++----------------------------------
 1 file changed, 11 insertions(+), 49 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index d0e0152aefb32..5e6d1f1c14dfd 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2156,51 +2156,12 @@ int sev_dev_get_attr(u32 group, u64 attr, u64 *val)
 	}
 }
 
-/*
- * The guest context contains all the information, keys and metadata
- * associated with the guest that the firmware tracks to implement SEV
- * and SNP features. The firmware stores the guest context in hypervisor
- * provide page via the SNP_GCTX_CREATE command.
- */
-static void *snp_context_create(struct kvm *kvm, struct kvm_sev_cmd *argp)
-{
-	struct sev_data_snp_addr data = {};
-	void *context;
-	int rc;
-
-	/* Allocate memory for context page */
-	context = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT);
-	if (!context)
-		return ERR_PTR(-ENOMEM);
-
-	data.address = __psp_pa(context);
-	rc = __sev_issue_cmd(argp->sev_fd, SEV_CMD_SNP_GCTX_CREATE, &data, &argp->error);
-	if (rc) {
-		pr_warn("Failed to create SEV-SNP context, rc %d fw_error %d",
-			rc, argp->error);
-		snp_free_firmware_page(context);
-		return ERR_PTR(rc);
-	}
-
-	return context;
-}
-
-static int snp_bind_asid(struct kvm *kvm, int *error)
-{
-	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
-	struct sev_data_snp_activate data = {0};
-
-	data.gctx_paddr = __psp_pa(sev->snp_context);
-	data.asid = sev_get_asid(kvm);
-	return sev_issue_cmd(kvm, SEV_CMD_SNP_ACTIVATE, &data, error);
-}
-
 static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 {
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
 	struct sev_data_snp_launch_start start = {0};
 	struct kvm_sev_snp_launch_start params;
-	int rc;
+	int rc, asid;
 
 	if (!sev_snp_guest(kvm))
 		return -ENOTTY;
@@ -2226,7 +2187,8 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (params.policy & SNP_POLICY_MASK_SINGLE_SOCKET)
 		return -EINVAL;
 
-	sev->snp_context = snp_context_create(kvm, argp);
+	asid = sev_get_asid(kvm);
+	sev->snp_context = sev_snp_create_context(argp->sev_fd, asid, &argp->error);
 	if (IS_ERR(sev->snp_context))
 		return PTR_ERR(sev->snp_context);
 
@@ -2241,7 +2203,7 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	}
 
 	sev->fd = argp->sev_fd;
-	rc = snp_bind_asid(kvm, &argp->error);
+	rc = sev_snp_activate_asid(sev->fd, asid, &argp->error);
 	if (rc) {
 		pr_debug("%s: Failed to bind ASID to SEV-SNP context, rc %d\n",
 			 __func__, rc);
@@ -2865,23 +2827,23 @@ int sev_vm_copy_enc_context_from(struct kvm *kvm, unsigned int source_fd)
 static int snp_decommission_context(struct kvm *kvm)
 {
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
-	struct sev_data_snp_addr data = {};
-	int ret;
+	int ret, error;
 
 	/* If context is not created then do nothing */
 	if (!sev->snp_context)
 		return 0;
 
-	/* Do the decommision, which will unbind the ASID from the SNP context */
-	data.address = __sme_pa(sev->snp_context);
+	/*
+	 * Do the decommision, which will unbind the ASID from the SNP context
+	 * and free the context page.
+	 */
 	down_write(&sev_deactivate_lock);
-	ret = sev_do_cmd(SEV_CMD_SNP_DECOMMISSION, &data, NULL);
+	ret = sev_snp_guest_decommission(sev->fd, sev->asid, &error);
 	up_write(&sev_deactivate_lock);
 
-	if (WARN_ONCE(ret, "Failed to release guest context, ret %d", ret))
+	if (WARN_ONCE(ret, "Failed to release guest context, ret %d fw err %d", ret, error))
 		return ret;
 
-	snp_free_firmware_page(sev->snp_context);
 	sev->snp_context = NULL;
 
 	return 0;

---

## [9] Dionna Glaze — 2024-11-12
*Subject: [PATCH v6 8/8] KVM: SVM: Delay legacy platform initialization on SNP*

When no SEV or SEV-ES guests are active, then the firmware can be
updated while (SEV-SNP) VM guests are active.

CC: Sean Christopherson <seanjc@google.com>
CC: Paolo Bonzini <pbonzini@redhat.com>
CC: Thomas Gleixner <tglx@linutronix.de>
CC: Ingo Molnar <mingo@redhat.com>
CC: Borislav Petkov <bp@alien8.de>
CC: Dave Hansen <dave.hansen@linux.intel.com>
CC: Ashish Kalra <ashish.kalra@amd.com>
CC: Tom Lendacky <thomas.lendacky@amd.com>
CC: John Allen <john.allen@amd.com>
CC: Herbert Xu <herbert@gondor.apana.org.au>
CC: "David S. Miller" <davem@davemloft.net>
CC: Michael Roth <michael.roth@amd.com>
CC: Luis Chamberlain <mcgrof@kernel.org>
CC: Russ Weight <russ.weight@linux.dev>
CC: Danilo Krummrich <dakr@redhat.com>
CC: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
CC: "Rafael J. Wysocki" <rafael@kernel.org>
CC: Tianfei zhang <tianfei.zhang@intel.com>
CC: Alexey Kardashevskiy <aik@amd.com>

Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 arch/x86/kvm/svm/sev.c | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 5e6d1f1c14dfd..507ed87749f55 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -444,7 +444,11 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	if (ret)
 		goto e_no_asid;
 
-	init_args.probe = false;
+	/*
+	 * Setting probe will skip SEV/SEV-ES platform initialization for an SEV-SNP guest in order
+	 * for SNP firmware hotloading to be available when only SEV-SNP VMs are running.
+	 */
+	init_args.probe = vm_type != KVM_X86_SEV_VM && vm_type != KVM_X86_SEV_ES_VM;
 	ret = sev_platform_init(&init_args);
 	if (ret)
 		goto e_free;

---

## [10] Dan Williams — 2024-11-12
*Subject: Re: [PATCH v6 3/8] firmware_loader: Move module refcounts to allow
 unloading*

Dionna Glaze wrote:
> If a kernel module registers a firmware upload API ops set, then it's
> unable to be moved due to effectively a cyclic reference that the module

Oh, interesting, I wondered why CXL did not uncover this loop in its
usage only to realize that CXL calls firmware registration from the
cxl_pci module, but the @module paramter passed to
firmware_upload_register() is the cxl_core module. I.e. we are
accidentally avoiding the problem. I assume other CONFIG_FW_UPLOAD users
simply do not test module removal.

However, I think the fix is simply to remove all module reference taking
by the firmware_loader core. It is the consumer's responsibility to call
firmware_upload_unregister() in its module removal path and that should
flush any and all future usage of the passed in ops structure.

---

## [11] Tom Lendacky — 2024-11-13
*Subject: Re: [PATCH v6 2/8] KVM: SVM: Fix snp_context_create error reporting*

On 11/12/24 17:22, Dionna Glaze wrote:
> Failure to allocate should not return -ENOTTY.
> Command failure has multiple possible error modes.

Since you can now get an error value set into sev->snp_context, a lot of
the NULL checks will be altered. You should create a local variable to
hold the returned value of snp_context_create() and only set
sev->snp_context if not an error.

Thanks,
Tom

> -	if (!sev->snp_context)
> -		return -ENOTTY;

---

## [12] Sean Christopherson — 2024-11-13
*Subject: Re: [PATCH v6 5/8] crypto: ccp: Add GCTX API to track ASID assignment*

On Tue, Nov 12, 2024, Dionna Glaze wrote:
> @@ -109,6 +110,10 @@ static void *sev_init_ex_buffer;
>   */

Tracking contexts in an array that's indexed per ASID is unsafe and unnecessarily
splits ASID management across KVM and the PSP driver.  There is zero reason the
PSP driver needs to care about ASIDs.  Attempting to police KVM is futile, and
leads to bloated, convoluted code.

AFAICT, there is nothing to guard against a use-after-free in 
snp_update_guest_contexts().  The need to handle SEV_RET_INVALID_GUEST is a pretty
big clue that there are races between KVM and firmware updates.

		if (!sev_asid_data[i].snp_context)
			continue;

		status_data.gctx_paddr = __psp_pa(sev_asid_data[i].snp_context);
		status_data.address = __psp_pa(snp_guest_status);
		rc = sev_do_cmd(SEV_CMD_SNP_GUEST_STATUS, &status_data, &error);
		if (!rc)
			continue;

		/*
		 * Handle race with SNP VM being destroyed/decommissoned,
		 * if guest context page invalid error is returned,
		 * assume guest has been destroyed.
		 */
		if (error == SEV_RET_INVALID_GUEST)
			continue;

Using an array is also inefficient, as it requires iterating over all possible
ASIDs, many of which may be unused.

Furthermore, handling this in the PSP driver (correctly) leads to unnecessary
locking.  KVM already protects SNP ASID allocations with sev_deactivate_lock, I
see zero reason to complicate things with another lock.

The "rollback" mechanism is also broken.  If SEV_CMD_SNP_GUEST_STATUS fails,
synthetic_restore_required is set and never cleared, and impacts *all* SEV PSP
commands.  I.e. failure to update one guest context comletely cripples the entire
system.  Not to mention synthetic_restore_required also lacks any form of SMP
synchronication.

I also don't see how a rollback is possible if an error occurs after one or more
guest contexts have been updated.  Presumably trying to rollback in that state
will leave the updated guests in a bad state.  Of course, I don't see any rollback
code as nothing ever clears synthetic_restore_required, so what's intented to
happen is entirely unclear.

I also don't see anything in this series that explains why a SEV_CMD_SNP_GUEST_STATUS
failure shouldn't be treated as a fatal error.  Of the error codes listed in the
SNP ABI, everything except UPDATE_FAILED is clearly a software bug.  And I can't
find anything that explains when UPDATE_FAILED will be returned.

  Table 80. Status Codes for SNP_GUEST_STATUS
  Status                          Condition
  SUCCESS                         Successful completion.
  INVALID_PLATFORM_STATE          The platform is not in the INIT state.
  INVALID_ADDRESS                 The address is invalid for use by the firmware.
  INVALID_PARAM                   MBZ fields are not zero.
  INVALID_GUEST                   The guest context page was invalid.
  INVALID_PAGE_STATE              The guest status page was not in the correct state.
  INVALID_PAGE_SIZE               The guest status page was not the correct size.
  UPDATE_FAILED                   Update of the firmware internal state or a guest context page has failed.

Somewhat off the cuff, I think the only sane way to approach this is to call into
KVM when doing a firmware update, and let KVM react accordingly.   E.g. let KVM
walk its list of VMs in order to update SNP VMs, taking kvm_lock and the somewhat
misnamed sev_deactivate_lock() as needed.  Then if updating a guest context fails,
terminate _that_ VM, and move on to the next VM.

Side topic, I don't see any code that ensures no SEV or SEV-ES VMs are running.
Is the idea to let userspace throw noodles at the PSP and see what sticks?

+        Provide support for AMD Platform Security Processor firmware.
+        The PSP firmware can be updated while no SEV or SEV-ES VMs are active.
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
+        Users of this feature should be aware of the error modes that indicate
+        required manual rollback or reset due to instablity.

---

## [13] Tom Lendacky — 2024-11-13
*Subject: Re: [PATCH v6 4/8] crypto: ccp: Fix uapi definitions of PSP errors*

On 11/12/24 17:22, Dionna Glaze wrote:
> From: Alexey Kardashevskiy <aik@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  include/uapi/linux/psp-sev.h | 21 ++++++++++++++-------

---

## [14] Dionna Amalie Glaze — 2024-11-13
*Subject: Re: [PATCH v6 3/8] firmware_loader: Move module refcounts to allow unloading*

On Tue, Nov 12, 2024 at 6:40 PM Dan Williams <dan.j.williams@intel.com> wrote:
>...
> However, I think the fix is simply to remove all module reference taking

That would suggest the addition of the refcounting in v1 to fix a test
means the test_firmware is wrong?
https://lore.kernel.org/all/20220421212204.36052-5-russell.h.weight@intel.com/

Adding Kees in case he knows better.

---

## [15] Russ Weight — 2024-11-14
*Subject: Re: [PATCH v6 3/8] firmware_loader: Move module refcounts to allow
 unloading*

On Tue, Nov 12, 2024 at 06:40:28PM -0800, Dan Williams wrote:
> Dionna Glaze wrote:
> > If a kernel module registers a firmware upload API ops set, then it's

As I understand it, if a module directly references symbols in another 
module, then the reference count is automatically incremented to ensure
that the dependent symbols are available to the consumer.

In this case, the firmware_loader does not directly reference symbol
names in the device driver that registered it. The call-back function
pointers are provided during registration. Without explicitly
incrementing the module reference count, it is possible to remove the
device driver while leaving the firmware loader instance (and sysfs
entries) intact. Accessing those sysfs nodes would result in
references to pointers that are no longer valid.

Clearly this would be an unexpected/unusual case. Someone with root
access would have to remove the device driver. I'm not sure how much
effort should be expended in preventing it - but this is the reasoning
behind the incrementing/decrementing of the module reference counts.

- Russ

---

## [16] Dan Williams — 2024-11-14
*Subject: Re: [PATCH v6 3/8] firmware_loader: Move module refcounts to allow
 unloading*

Russ Weight wrote:
[..]
> Clearly this would be an unexpected/unusual case. Someone with root
> access would have to remove the device driver. I'm not sure how much

The module reference needs to be held only if the producer of those
symbols can be removed without triggering some coordinated removal with
action consumer. A driver that fails to call
firmware_upload_unregister() in its module removal path is simply a driver
with a memory-leak and use-after-free bug, not something the firmware
upload core needs to worry about.

So, the prevention mechanism is "thou shalt use
firmware_upload_unregister() correctly", and when that is in place
explicit module references are not only redundant, but trying to
implement them causes circular dependency loops.

---

## [17] Tom Lendacky — 2024-11-14
*Subject: Re: [PATCH v6 3/8] firmware_loader: Move module refcounts to allow
 unloading*

On 11/14/24 12:17, Dan Williams wrote:
> Russ Weight wrote:
> [..]

I believe that is how other similar services, like debugfs, work, the
module is responsible for cleaning up.

Thanks,
Tom

---

## [18] Russ Weight — 2024-11-15
*Subject: Re: [PATCH v6 3/8] firmware_loader: Move module refcounts to allow
 unloading*

On Thu, Nov 14, 2024 at 01:30:16PM -0600, Tom Lendacky wrote:
> On 11/14/24 12:17, Dan Williams wrote:
> > Russ Weight wrote:

Thanks for the explanation. Makes total sense to me. I agree that the
module reference counts can/should be removed.

- Russ
> 
> I believe that is how other similar services, like debugfs, work, the

---

## [19] Tom Lendacky — 2025-02-20
*Subject: Re: [PATCH v6 4/8] crypto: ccp: Fix uapi definitions of PSP errors*

On 11/13/24 10:24, Tom Lendacky wrote:
> On 11/12/24 17:22, Dionna Glaze wrote:
>> From: Alexey Kardashevskiy <aik@amd.com>

@Boris or @Herbert, can we pick up this fix separate from this series?
It can probably go through either the tip tree or crypto tree.

Thanks,
Tom

> 
>> ---

---

## [20] Borislav Petkov — 2025-02-20
*Subject: Re: [PATCH v6 4/8] crypto: ccp: Fix uapi definitions of PSP errors*

On Thu, Feb 20, 2025 at 10:34:51AM -0600, Tom Lendacky wrote:
> @Boris or @Herbert, can we pick up this fix separate from this series?
> It can probably go through either the tip tree or crypto tree.

This usually goes through the crypto tree. Unless Herbert really wants me to
pick it up...

---

## [21] Herbert Xu — 2025-02-21
*Subject: Re: [PATCH v6 4/8] crypto: ccp: Fix uapi definitions of PSP errors*

On Thu, Feb 20, 2025 at 10:34:51AM -0600, Tom Lendacky wrote:
>
> @Boris or @Herbert, can we pick up this fix separate from this series?

Please repost this patch by itself.

Thanks!

---

## [22] Tom Lendacky — 2025-03-07
*Subject: Re: [PATCH v6 4/8] crypto: ccp: Fix uapi definitions of PSP errors*

On 2/20/25 10:47, Borislav Petkov wrote:
> On Thu, Feb 20, 2025 at 10:34:51AM -0600, Tom Lendacky wrote:
>> @Boris or @Herbert, can we pick up this fix separate from this series?

Herbert, any concerns picking up this patch?

Thanks,
Tom

>

---

## [23] Tom Lendacky — 2025-03-07
*Subject: Re: [PATCH v6 4/8] crypto: ccp: Fix uapi definitions of PSP errors*

On 3/7/25 14:28, Tom Lendacky wrote:
> On 2/20/25 10:47, Borislav Petkov wrote:
>> On Thu, Feb 20, 2025 at 10:34:51AM -0600, Tom Lendacky wrote:

Sorry, looks like your previous response got lost in my email system.
Either Alexey or I will re-send.

Thanks,
Tom

> 
> Thanks,

---
