---
title: 'Add SEV firmware hotloading'
date: 2024-11-07
last_reply: 2024-11-13
message_count: 35
participants: ['Dionna Glaze', 'Tom Lendacky', 'Kalra, Ashish', 'Sean Christopherson']
---

## [1] Dionna Glaze — 2024-11-07

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

Dionna Glaze (10):
  KVM: SVM: Fix gctx page leak on invalid inputs
  KVM: SVM: Fix snp_context_create error reporting
  firmware_loader: Move module refcounts to allow unloading
  crypto: ccp: Fix uapi definitions of PSP errors
  crypto: ccp: Add GCTX API to track ASID assignment
  crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support
  crypto: ccp: Add preferred access checking method
  KVM: SVM: move sev_issue_cmd_external_user to new API
  KVM: SVM: Use new ccp GCTX API
  KVM: SVM: Delay legacy platform initialization on SNP

 arch/x86/kvm/svm/sev.c                      | 104 ++++----
 drivers/base/firmware_loader/sysfs_upload.c |  16 +-
 drivers/crypto/ccp/Kconfig                  |  10 +
 drivers/crypto/ccp/Makefile                 |   1 +
 drivers/crypto/ccp/sev-dev.c                | 140 ++++++++--
 drivers/crypto/ccp/sev-dev.h                |  35 +++
 drivers/crypto/ccp/sev-fw.c                 | 267 ++++++++++++++++++++
 include/linux/psp-sev.h                     |  93 +++++--
 include/uapi/linux/psp-sev.h                |  21 +-
 9 files changed, 572 insertions(+), 115 deletions(-)
 create mode 100644 drivers/crypto/ccp/sev-fw.c

---

## [2] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 01/10] KVM: SVM: Fix gctx page leak on invalid inputs*

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

## [3] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 02/10] KVM: SVM: Fix snp_context_create error reporting*

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

## [4] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 03/10] firmware_loader: Move module refcounts to allow unloading*

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

## [5] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 04/10] crypto: ccp: Fix uapi definitions of PSP errors*

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

From: Alexey Kardashevskiy <aik@amd.com>
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

## [6] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 05/10] crypto: ccp: Add GCTX API to track ASID assignment*

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
 drivers/crypto/ccp/sev-dev.c | 107 +++++++++++++++++++++++++++++++++++
 drivers/crypto/ccp/sev-dev.h |   8 +++
 include/linux/psp-sev.h      |  52 +++++++++++++++++
 3 files changed, 167 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index af018afd9cd7f..036e8d5054fcc 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -109,6 +109,10 @@ static void *sev_init_ex_buffer;
  */
 static struct sev_data_range_list *snp_range_list;
 
+/* SEV ASID data tracks resources associated with an ASID to safely manage operations. */
+struct sev_asid_data *sev_asid_data;
+u32 nr_asids, sev_min_asid, sev_max_asid, sev_es_max_asid;
+
 static inline bool sev_version_greater_or_equal(u8 maj, u8 min)
 {
 	struct sev_device *sev = psp_master->sev_data;
@@ -1093,6 +1097,81 @@ static int snp_filter_reserved_mem_regions(struct resource *rs, void *arg)
 	return 0;
 }
 
+void *sev_snp_create_context(int asid, int *psp_ret)
+{
+	struct sev_data_snp_addr data = {};
+	void *context;
+	int rc;
+
+	if (!sev_asid_data)
+		return ERR_PTR(-ENODEV);
+
+	/* Can't create a context for a used ASID. */
+	if (sev_asid_data[asid].snp_context)
+		return ERR_PTR(-EBUSY);
+
+	/* Allocate memory for context page */
+	context = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT);
+	if (!context)
+		return ERR_PTR(-ENOMEM);
+
+	data.address = __psp_pa(context);
+	rc = sev_do_cmd(SEV_CMD_SNP_GCTX_CREATE, &data, psp_ret);
+	if (rc) {
+		pr_warn("Failed to create SEV-SNP context, rc %d fw_error %d",
+			rc, *psp_ret);
+		snp_free_firmware_page(context);
+		return ERR_PTR(-EIO);
+	}
+
+	sev_asid_data[asid].snp_context = context;
+
+	return context;
+}
+
+int sev_snp_activate_asid(int asid, int *psp_ret)
+{
+	struct sev_data_snp_activate data = {0};
+	void *context;
+
+	if (!sev_asid_data)
+		return -ENODEV;
+
+	context = sev_asid_data[asid].snp_context;
+	if (!context)
+		return -EINVAL;
+
+	data.gctx_paddr = __psp_pa(context);
+	data.asid = asid;
+	return sev_do_cmd(SEV_CMD_SNP_ACTIVATE, &data, psp_ret);
+}
+
+int sev_snp_guest_decommission(int asid, int *psp_ret)
+{
+	struct sev_data_snp_addr addr = {};
+	struct sev_asid_data *data = &sev_asid_data[asid];
+	int ret;
+
+	if (!sev_asid_data)
+		return -ENODEV;
+
+	/* If context is not created then do nothing */
+	if (!data->snp_context)
+		return 0;
+
+	/* Do the decommision, which will unbind the ASID from the SNP context */
+	addr.address = __sme_pa(data->snp_context);
+	ret = sev_do_cmd(SEV_CMD_SNP_DECOMMISSION, &addr, NULL);
+
+	if (WARN_ONCE(ret, "Failed to release guest context, ret %d", ret))
+		return ret;
+
+	snp_free_firmware_page(data->snp_context);
+	data->snp_context = NULL;
+
+	return 0;
+}
+
 static int __sev_snp_init_locked(int *error)
 {
 	struct psp_device *psp = psp_master;
@@ -1306,6 +1385,27 @@ static int __sev_platform_init_locked(int *error)
 	return 0;
 }
 
+static int __sev_asid_data_init(void)
+{
+	u32 eax, ebx;
+
+	if (sev_asid_data)
+		return 0;
+
+	cpuid(0x8000001f, &eax, &ebx, &sev_max_asid, &sev_min_asid);
+	if (!sev_max_asid)
+		return -ENODEV;
+
+	nr_asids = sev_max_asid + 1;
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
@@ -1319,6 +1419,10 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	if (sev->state == SEV_STATE_INIT)
 		return 0;
 
+	rc = __sev_asid_data_init();
+	if (rc)
+		return rc;
+
 	/*
 	 * Legacy guests cannot be running while SNP_INIT(_EX) is executing,
 	 * so perform SEV-SNP initialization at probe time.
@@ -2329,6 +2433,9 @@ static void __sev_firmware_shutdown(struct sev_device *sev, bool panic)
 		snp_range_list = NULL;
 	}
 
+	kfree(sev_asid_data);
+	sev_asid_data = NULL;
+
 	__sev_snp_shutdown_locked(&error, panic);
 }
 
diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index 3e4e5574e88a3..7d0fdfdda30b6 100644
--- a/drivers/crypto/ccp/sev-dev.h
+++ b/drivers/crypto/ccp/sev-dev.h
@@ -65,4 +65,12 @@ void sev_dev_destroy(struct psp_device *psp);
 void sev_pci_init(void);
 void sev_pci_exit(void);
 
+struct sev_asid_data {
+	void *snp_context;
+};
+
+/* Extern to be shared with firmware_upload API implementation if configured. */
+extern struct sev_asid_data *sev_asid_data;
+extern u32 nr_asids, sev_min_asid, sev_max_asid, sev_es_max_asid;
+
 #endif /* __SEV_DEV_H */
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index 903ddfea85850..ac36b5ddf717d 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -942,6 +942,58 @@ int sev_guest_decommission(struct sev_data_decommission *data, int *error);
  */
 int sev_do_cmd(int cmd, void *data, int *psp_ret);
 
+/**
+ * sev_snp_create_context - allocates an SNP context firmware page
+ *
+ * Associates the created context with the ASID that an activation
+ * call after SNP_LAUNCH_START will commit. The association is needed
+ * to track active guest context pages to refresh during firmware hotload.
+ *
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
+void *sev_snp_create_context(int asid, int *psp_ret);
+
+/**
+ * sev_snp_activate_asid - issues SNP_ACTIVATE for the ASID and associated guest context page.
+ *
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
+int sev_snp_activate_asid(int asid, int *psp_ret);
+
+/**
+ * sev_snp_guest_decommission - issues SNP_DECOMMISSION for an ASID's guest context page, and frees
+ * it.
+ *
+ * The caller must ensure mutual exclusion with any process that may deactivate ASIDs.
+ *
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
+int sev_snp_guest_decommission(int asid, int *psp_ret);
+
 void *psp_copy_user_blob(u64 uaddr, u32 len);
 void *snp_alloc_firmware_page(gfp_t mask);
 void snp_free_firmware_page(void *addr);

---

## [7] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 06/10] crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support*

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

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 drivers/crypto/ccp/Kconfig   |  10 ++
 drivers/crypto/ccp/Makefile  |   1 +
 drivers/crypto/ccp/sev-dev.c |  22 +--
 drivers/crypto/ccp/sev-dev.h |  27 ++++
 drivers/crypto/ccp/sev-fw.c  | 267 +++++++++++++++++++++++++++++++++++
 include/linux/psp-sev.h      |  17 +++
 6 files changed, 334 insertions(+), 10 deletions(-)
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
index 036e8d5054fcc..498ec8a0deeca 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -227,6 +227,7 @@ static int sev_cmd_buffer_len(int cmd)
 	case SEV_CMD_SNP_GUEST_REQUEST:		return sizeof(struct sev_data_snp_guest_request);
 	case SEV_CMD_SNP_CONFIG:		return sizeof(struct sev_user_data_snp_config);
 	case SEV_CMD_SNP_COMMIT:		return sizeof(struct sev_data_snp_commit);
+	case SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX:	return sizeof(struct sev_data_download_firmware_ex);
 	default:				return 0;
 	}
 
@@ -488,7 +489,7 @@ void snp_free_firmware_page(void *addr)
 }
 EXPORT_SYMBOL_GPL(snp_free_firmware_page);
 
-static void *sev_fw_alloc(unsigned long len)
+void *sev_fw_alloc(unsigned long len)
 {
 	struct page *page;
 
@@ -856,6 +857,10 @@ static int __sev_do_cmd_locked(int cmd, void *data, int *psp_ret)
 	if (WARN_ON_ONCE(!data != !buf_len))
 		return -EINVAL;
 
+	ret = sev_snp_synthetic_error(sev, psp_ret);
+	if (ret)
+		return ret;
+
 	/*
 	 * Copy the incoming data to driver's scratch buffer as __pa() will not
 	 * work for some memory, e.g. vmalloc'd addresses, and @data may not be
@@ -1632,7 +1637,7 @@ void *psp_copy_user_blob(u64 uaddr, u32 len)
 }
 EXPORT_SYMBOL_GPL(psp_copy_user_blob);
 
-static int sev_get_api_version(void)
+int sev_get_api_version(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
 	struct sev_user_data_status status;
@@ -1707,14 +1712,7 @@ static int sev_update_firmware(struct device *dev)
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
@@ -2378,6 +2376,8 @@ int sev_dev_init(struct psp_device *psp)
 	if (ret)
 		goto e_irq;
 
+	sev_snp_dev_init_firmware_upload(sev);
+
 	dev_notice(dev, "sev enabled\n");
 
 	return 0;
@@ -2459,6 +2459,8 @@ void sev_dev_destroy(struct psp_device *psp)
 		kref_put(&misc_dev->refcount, sev_exit);
 
 	psp_clear_sev_irq_handler(psp);
+
+	sev_snp_dev_init_firmware_upload(sev);
 }
 
 static int snp_shutdown_on_panic(struct notifier_block *nb,
diff --git a/drivers/crypto/ccp/sev-dev.h b/drivers/crypto/ccp/sev-dev.h
index 7d0fdfdda30b6..db65d2c7afe9b 100644
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
@@ -73,4 +87,17 @@ struct sev_asid_data {
 extern struct sev_asid_data *sev_asid_data;
 extern u32 nr_asids, sev_min_asid, sev_max_asid, sev_es_max_asid;
 
+void *sev_fw_alloc(unsigned long len);
+int sev_get_api_version(void);
+
+#ifdef CONFIG_CRYPTO_DEV_SP_PSP_FW_UPLOAD
+void sev_snp_dev_init_firmware_upload(struct sev_device *sev);
+void sev_snp_destroy_firmware_upload(struct sev_device *sev);
+int sev_snp_synthetic_error(struct sev_device *sev, int *psp_ret);
+#else
+static inline void sev_snp_dev_init_firmware_upload(struct sev_device *sev) { }
+static inline void sev_snp_destroy_firmware_upload(struct sev_device *sev) { }
+static inline int sev_snp_synthetic_error(struct sev_device *sev, int *psp_ret) { return 0; }
+#endif /* CONFIG_CRYPTO_DEV_SP_PSP_FW_UPLOAD */
+
 #endif /* __SEV_DEV_H */
diff --git a/drivers/crypto/ccp/sev-fw.c b/drivers/crypto/ccp/sev-fw.c
new file mode 100644
index 0000000000000..6a87872174ee5
--- /dev/null
+++ b/drivers/crypto/ccp/sev-fw.c
@@ -0,0 +1,267 @@
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
+	data_ex->fw_paddr = __psp_pa(fw_dest);
+	data_ex->fw_len = size;
+	data_ex->length = sizeof(struct sev_data_download_firmware_ex);
+	/* commit is purposefully unset for GCTX update failure to advise rollback */
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
+		dev_warn(sev->dev, "Firmware updated but unusable\n");
+		dev_warn(sev->dev, "Need to do manual firmware rollback!!!\n");
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
+static enum fw_upload_err snp_update_guest_statuses(struct sev_device *sev)
+{
+	struct sev_data_snp_guest_status status_data;
+	void *snp_guest_status;
+	enum fw_upload_err ret;
+	int error;
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
+	/*
+	 * After the last bound asid-to-gctx page is snp_unbound_gctx_end-many
+	 * unbound gctx pages that also need updating.
+	 */
+	for (int i = 1; i <= sev_es_max_asid; i++) {
+		if (!sev_asid_data[i].snp_context)
+			continue;
+
+		status_data.gctx_paddr = __psp_pa(sev_asid_data[i].snp_context);
+		status_data.address = __psp_pa(snp_guest_status);
+		ret = sev_do_cmd(SEV_CMD_SNP_GUEST_STATUS, &status_data, &error);
+		if (ret) {
+			/*
+			 * Handle race with SNP VM being destroyed/decommissoned,
+			 * if guest context page invalid error is returned,
+			 * assume guest has been destroyed.
+			 */
+			if (error == SEV_RET_INVALID_GUEST)
+				continue;
+			synthetic_restore_required = true;
+			dev_err(sev->dev, "SNP GCTX update error requires rollback: %#x\n",
+				error);
+			ret = FW_UPLOAD_ERR_RW_ERROR;
+			goto fw_err;
+		}
+	}
+fw_err:
+	snp_free_firmware_page(snp_guest_status);
+	return ret;
+}
+
+static enum fw_upload_err snp_dlfw_ex_write(struct fw_upload *fwl, const u8 *data,
+					    u32 offset, u32 size, u32 *written)
+{
+	/* fwl not-NULL guaranteed by firmware_upload API */
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
+	ret = snp_update_guest_statuses(sev);
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
+		dev_info(sev->dev, "SEV firmware same as old %d.%d.%d\n",
+			 api_major, api_minor, build);
+	}
+
+	*written = size;
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
+void sev_snp_dev_init_firmware_upload(struct sev_device *sev)
+{
+	struct fw_upload *fwl;
+
+	fwl = firmware_upload_register(THIS_MODULE, sev->dev, "snp_dlfw_ex", &snp_dlfw_ex_ops, sev);
+
+	if (IS_ERR(fwl))
+		dev_err(sev->dev, "SEV firmware upload initialization error %ld\n", PTR_ERR(fwl));
+	else
+		sev->fwl = fwl;
+}
+
+void sev_snp_destroy_firmware_upload(struct sev_device *sev)
+{
+	if (!sev || !sev->fwl)
+		return;
+
+	firmware_upload_unregister(sev->fwl);
+}
+
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index ac36b5ddf717d..b91cbdc208f49 100644
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

## [8] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 07/10] crypto: ccp: Add preferred access checking method*

sev_issue_cmd_external_user is the only function that checks permissions
before performing its task. With the new GCTX API, it's important to
establish permission once and have that determination dominate later API
uses. This is implicitly how ccp has been used by dominating uses of
sev_do_cmd by a successful sev_issue_cmd_external_user call.

Consider sev_issue_cmd_external_user deprecated by
checking if a held file descriptor passes file_is_sev, similar to the
file_is_kvm function.

This also fixes the header comment that the bad file error code is
-%EINVAL when in fact it is -%EBADF.

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
 drivers/crypto/ccp/sev-dev.c | 13 +++++++++++--
 include/linux/psp-sev.h      | 11 ++++++++++-
 2 files changed, 21 insertions(+), 3 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 498ec8a0deeca..f92e6a222da8a 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -8,6 +8,7 @@
  */
 
 #include <linux/bitfield.h>
+#include <linux/file.h>
 #include <linux/module.h>
 #include <linux/kernel.h>
 #include <linux/kthread.h>
@@ -2486,11 +2487,19 @@ static struct notifier_block snp_panic_notifier = {
 	.notifier_call = snp_shutdown_on_panic,
 };
 
+bool file_is_sev(struct file *p)
+{
+	return p && p->f_op == &sev_fops;
+}
+EXPORT_SYMBOL_GPL(file_is_sev);
+
 int sev_issue_cmd_external_user(struct file *filep, unsigned int cmd,
 				void *data, int *error)
 {
-	if (!filep || filep->f_op != &sev_fops)
-		return -EBADF;
+	int rc = file_is_sev(filep) ? 0 : -EBADF;
+
+	if (rc)
+		return rc;
 
 	return sev_do_cmd(cmd, data, error);
 }
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index b91cbdc208f49..ed85c0cfcfcbe 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -879,11 +879,18 @@ int sev_platform_status(struct sev_user_data_status *status, int *error);
  * -%ENOTSUPP  if the SEV does not support SEV
  * -%ETIMEDOUT if the SEV command timed out
  * -%EIO       if the SEV returned a non-zero return code
- * -%EINVAL    if the SEV file descriptor is not valid
+ * -%EBADF     if the file pointer is bad or does not grant access
  */
 int sev_issue_cmd_external_user(struct file *filep, unsigned int id,
 				void *data, int *error);
 
+/**
+ * file_is_sev - returns whether a file pointer is for the SEV device
+ *
+ * @filep - SEV device file pointer
+ */
+bool file_is_sev(struct file *filep);
+
 /**
  * sev_guest_deactivate - perform SEV DEACTIVATE command
  *
@@ -1039,6 +1046,8 @@ static inline int sev_guest_df_flush(int *error) { return -ENODEV; }
 static inline int
 sev_issue_cmd_external_user(struct file *filep, unsigned int id, void *data, int *error) { return -ENODEV; }
 
+static inline bool file_is_sev(struct file *filep) { return false; }
+
 static inline void *psp_copy_user_blob(u64 __user uaddr, u32 len) { return ERR_PTR(-EINVAL); }
 
 static inline void *snp_alloc_firmware_page(gfp_t mask)

---

## [9] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 08/10] KVM: SVM: move sev_issue_cmd_external_user to new API*

ccp now prefers all calls from external drivers to dominate all calls
into the driver on behalf of a user with a successful
sev_check_external_user call.

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
 arch/x86/kvm/svm/sev.c       | 18 +++++++++++++++---
 drivers/crypto/ccp/sev-dev.c | 12 ------------
 include/linux/psp-sev.h      | 27 ---------------------------
 3 files changed, 15 insertions(+), 42 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index d0e0152aefb32..cea41b8cdabe4 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -528,21 +528,33 @@ static int sev_bind_asid(struct kvm *kvm, unsigned int handle, int *error)
 	return ret;
 }
 
-static int __sev_issue_cmd(int fd, int id, void *data, int *error)
+static int sev_check_external_user(int fd)
 {
 	struct fd f;
-	int ret;
+	int ret = 0;
 
 	f = fdget(fd);
 	if (!fd_file(f))
 		return -EBADF;
 
-	ret = sev_issue_cmd_external_user(fd_file(f), id, data, error);
+	if (!file_is_sev(fd_file(f)))
+		ret = -EBADF;
 
 	fdput(f);
 	return ret;
 }
 
+static int __sev_issue_cmd(int fd, int id, void *data, int *error)
+{
+	int ret;
+
+	ret = sev_check_external_user(fd);
+	if (ret)
+		return ret;
+
+	return sev_do_cmd(id, data, error);
+}
+
 static int sev_issue_cmd(struct kvm *kvm, int id, void *data, int *error)
 {
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index f92e6a222da8a..67f6425b7ed07 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -2493,18 +2493,6 @@ bool file_is_sev(struct file *p)
 }
 EXPORT_SYMBOL_GPL(file_is_sev);
 
-int sev_issue_cmd_external_user(struct file *filep, unsigned int cmd,
-				void *data, int *error)
-{
-	int rc = file_is_sev(filep) ? 0 : -EBADF;
-
-	if (rc)
-		return rc;
-
-	return sev_do_cmd(cmd, data, error);
-}
-EXPORT_SYMBOL_GPL(sev_issue_cmd_external_user);
-
 void sev_pci_init(void)
 {
 	struct sev_device *sev = psp_master->sev_data;
diff --git a/include/linux/psp-sev.h b/include/linux/psp-sev.h
index ed85c0cfcfcbe..b4164d3600702 100644
--- a/include/linux/psp-sev.h
+++ b/include/linux/psp-sev.h
@@ -860,30 +860,6 @@ int sev_platform_init(struct sev_platform_init_args *args);
  */
 int sev_platform_status(struct sev_user_data_status *status, int *error);
 
-/**
- * sev_issue_cmd_external_user - issue SEV command by other driver with a file
- * handle.
- *
- * This function can be used by other drivers to issue a SEV command on
- * behalf of userspace. The caller must pass a valid SEV file descriptor
- * so that we know that it has access to SEV device.
- *
- * @filep - SEV device file pointer
- * @cmd - command to issue
- * @data - command buffer
- * @error: SEV command return code
- *
- * Returns:
- * 0 if the SEV successfully processed the command
- * -%ENODEV    if the SEV device is not available
- * -%ENOTSUPP  if the SEV does not support SEV
- * -%ETIMEDOUT if the SEV command timed out
- * -%EIO       if the SEV returned a non-zero return code
- * -%EBADF     if the file pointer is bad or does not grant access
- */
-int sev_issue_cmd_external_user(struct file *filep, unsigned int id,
-				void *data, int *error);
-
 /**
  * file_is_sev - returns whether a file pointer is for the SEV device
  *
@@ -1043,9 +1019,6 @@ sev_guest_activate(struct sev_data_activate *data, int *error) { return -ENODEV;
 
 static inline int sev_guest_df_flush(int *error) { return -ENODEV; }
 
-static inline int
-sev_issue_cmd_external_user(struct file *filep, unsigned int id, void *data, int *error) { return -ENODEV; }
-
 static inline bool file_is_sev(struct file *filep) { return false; }
 
 static inline void *psp_copy_user_blob(u64 __user uaddr, u32 len) { return ERR_PTR(-EINVAL); }

---

## [10] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 09/10] KVM: SVM: Use new ccp GCTX API*

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
 arch/x86/kvm/svm/sev.c | 74 ++++++++++++------------------------------
 1 file changed, 20 insertions(+), 54 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index cea41b8cdabe4..d7cef84750b33 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -89,7 +89,7 @@ static unsigned int nr_asids;
 static unsigned long *sev_asid_bitmap;
 static unsigned long *sev_reclaim_asid_bitmap;
 
-static int snp_decommission_context(struct kvm *kvm);
+static int kvm_decommission_snp_context(struct kvm *kvm);
 
 struct enc_region {
 	struct list_head list;
@@ -2168,51 +2168,12 @@ int sev_dev_get_attr(u32 group, u64 attr, u64 *val)
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
@@ -2238,14 +2199,19 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (params.policy & SNP_POLICY_MASK_SINGLE_SOCKET)
 		return -EINVAL;
 
-	sev->snp_context = snp_context_create(kvm, argp);
+	rc = sev_check_external_user(argp->sev_fd);
+	if (rc)
+		return rc;
+
+	asid = sev_get_asid(kvm);
+	sev->snp_context = sev_snp_create_context(asid, &argp->error);
 	if (IS_ERR(sev->snp_context))
 		return PTR_ERR(sev->snp_context);
 
 	start.gctx_paddr = __psp_pa(sev->snp_context);
 	start.policy = params.policy;
 	memcpy(start.gosvw, params.gosvw, sizeof(params.gosvw));
-	rc = __sev_issue_cmd(argp->sev_fd, SEV_CMD_SNP_LAUNCH_START, &start, &argp->error);
+	rc = sev_do_cmd(SEV_CMD_SNP_LAUNCH_START, &start, &argp->error);
 	if (rc) {
 		pr_debug("%s: SEV_CMD_SNP_LAUNCH_START firmware command failed, rc %d\n",
 			 __func__, rc);
@@ -2253,7 +2219,7 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	}
 
 	sev->fd = argp->sev_fd;
-	rc = snp_bind_asid(kvm, &argp->error);
+	rc = sev_snp_activate_asid(asid, &argp->error);
 	if (rc) {
 		pr_debug("%s: Failed to bind ASID to SEV-SNP context, rc %d\n",
 			 __func__, rc);
@@ -2263,7 +2229,7 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return 0;
 
 e_free_context:
-	snp_decommission_context(kvm);
+	kvm_decommission_snp_context(kvm);
 
 	return rc;
 }
@@ -2874,26 +2840,26 @@ int sev_vm_copy_enc_context_from(struct kvm *kvm, unsigned int source_fd)
 	return ret;
 }
 
-static int snp_decommission_context(struct kvm *kvm)
+static int kvm_decommission_snp_context(struct kvm *kvm)
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
+	ret = sev_snp_guest_decommission(sev->asid, &error);
 	up_write(&sev_deactivate_lock);
 
-	if (WARN_ONCE(ret, "Failed to release guest context, ret %d", ret))
+	if (WARN_ONCE(ret, "Failed to release guest context, ret %d fw err %d", ret, error))
 		return ret;
 
-	snp_free_firmware_page(sev->snp_context);
 	sev->snp_context = NULL;
 
 	return 0;
@@ -2947,7 +2913,7 @@ void sev_vm_destroy(struct kvm *kvm)
 		 * Decomission handles unbinding of the ASID. If it fails for
 		 * some unexpected reason, just leak the ASID.
 		 */
-		if (snp_decommission_context(kvm))
+		if (kvm_decommission_snp_context(kvm))
 			return;
 	} else {
 		sev_unbind_asid(kvm, sev->handle);

---

## [11] Dionna Glaze — 2024-11-07
*Subject: [PATCH v5 10/10] KVM: SVM: Delay legacy platform initialization on SNP*

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
index d7cef84750b33..0d57a0a6b30fc 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -444,7 +444,11 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	if (ret)
 		goto e_no_asid;
 
-	init_args.probe = false;
+	/*
+	 * Probe will skip SEV/SEV-ES platform initialization in order for
+	 * SNP firmware hotloading to be available when SEV-SNP VMs are running.
+	 */
+	init_args.probe = vm_type != KVM_X86_SEV_VM && vm_type != KVM_X86_SEV_ES_VM;
 	ret = sev_platform_init(&init_args);
 	if (ret)
 		goto e_free;

---

## [12] Dionna Amalie Glaze — 2024-11-08
*Subject: Re: [PATCH v5 06/10] crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support*

On Thu, Nov 7, 2024 at 3:28 PM Dionna Glaze <dionnaglaze@google.com> wrote:
>
> In order to support firmware hotloading, the DOWNLOAD_FIRMWARE_EX

I mistakenly dropped a tag when squashing:

Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>

> ---
>  drivers/crypto/ccp/Kconfig   |  10 ++

---

## [13] Tom Lendacky — 2024-11-08
*Subject: Re: [PATCH v5 04/10] crypto: ccp: Fix uapi definitions of PSP errors*

On 11/7/24 17:24, Dionna Glaze wrote:
> Additions to the error enum after the explicit 0x27 setting for
> SEV_RET_INVALID_KEY leads to incorrect value assignments.

It looks like you used the patch command to apply Alexey's patch, which
will end up making you the author.

You'll need to use git to make Alexey the author or use git to import the
patch from Alexey. Then you would just have Alexey's signed off followed
by yours as you have below without having to specify the From: in the
commit message.

Thanks,
Tom

> Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
> Signed-off-by: Dionna Glaze <dionnaglaze@google.com>

---

## [14] Tom Lendacky — 2024-11-08
*Subject: Re: [PATCH v5 05/10] crypto: ccp: Add GCTX API to track ASID
 assignment*

On 11/7/24 17:24, Dionna Glaze wrote:
> In preparation for SEV firmware hotloading support, introduce a new way
> to create, activate, and decommission GCTX pages such that ccp is has

s/is has/has/

> all GCTX pages available to update as needed.
> 

You should be consistent with capitalization of gctx and also capitalize ASID.

> 
> CC: Sean Christopherson <seanjc@google.com>

Should this be a WARN_ON_ONCE() check since we should really never
encounter this situation if things are programmed correctly, right?

Also, should the ASID value be vetted to ensure you don't go beyond the
end of the array?

> +		return ERR_PTR(-EBUSY);
> +

Since psp_ret could be NULL, maybe use a local int variable "error" that
can be supplied and then used below in the message unconditionally.

Then check check if psp_ret is non-NULL and assign "error" to it.

> +	if (rc) {
> +		pr_warn("Failed to create SEV-SNP context, rc %d fw_error %d",

I know this is replicating what snp_context_create() does, but the SEV and
SNP specs specify error codes in hex, so we could simplify the lookup
process by outputting a hex value for fw_error here. Not completely
necessary, but would be nice.

> +			rc, *psp_ret);
> +		snp_free_firmware_page(context);

Ditto on the ASID value vetting here.

> +	if (!context)

Ditto on the WARN_ON_ONCE since we should always have a context when this
is called.

> +		return -EINVAL;
> +

But, I don't think that SEV_CMD_SNP_ACTIVATE needs to be here since it
doesn't change anything related to the sev_asid_data struct. KVM has the
guest context and can issue the commands similar to the other commands KVM
issues that use the guest context. So this function can be removed and
still performed in KVM.

> +
> +int sev_snp_guest_decommission(int asid, int *psp_ret)

Should do ASID value checking before assigning.

> +	int ret;
> +

Ditto on the psp_ret thing here, too.

> +
> +	if (WARN_ONCE(ret, "Failed to release guest context, ret %d", ret))

And then this message can include the fw error for better debugging output.

> +		return ret;
> +

No need for the double underscore at the start of the function name.

> +{
> +	u32 eax, ebx;

Can we get rid of sev_max_asid and then just use nr_asids or sev_asids in
the cpuid() call and adjust by 1 after the above check.

> +	sev_es_max_asid = sev_min_asid - 1;
> +

Is this using the full ASID range in case we want to track non-SNP related
contexts in the future?

> +	if (!sev_asid_data)
> +		return -ENOMEM;

Move this to the patch that needs them made extern.

Thanks,
Tom

> +
>  #endif /* __SEV_DEV_H */

---

## [15] Tom Lendacky — 2024-11-08
*Subject: Re: [PATCH v5 06/10] crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support*

On 11/7/24 17:24, Dionna Glaze wrote:
> In order to support firmware hotloading, the DOWNLOAD_FIRMWARE_EX
> command must be available.

Please put a comment here on the reason for this call being here.

> +	ret = sev_snp_synthetic_error(sev, psp_ret);
> +	if (ret)

sev_snp_init_firmware_upload

Hmmm... I made these comments before but they haven't been incorporated.
Please go back and check all the previous series comments and say whether
you agree or disagree so that I can expect the review changes to be
present or not.

> +
>  	dev_notice(dev, "sev enabled\n");

destroy not init, as commented previously.

>  }
>  

CRYPTO_DEV_SP_PSP_FW_UPLOAD

> +	struct fw_upload *fwl;
> +	bool fw_cancel;

Add a blank line.

> +	return 0;
> +}

Move this above the start of the data_ex assignments.

> +
> +	ret = sev_do_cmd(SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX, data_ex, error);

Remove blank line.

> +	if (ret)
> +		goto free_err;

How does this ever get set back to false?

> +}
> +

This comment seems stale.

> +	 */
> +	for (int i = 1; i <= sev_es_max_asid; i++) {

Add a blank line here.

> +			synthetic_restore_required = true;
> +			dev_err(sev->dev, "SNP GCTX update error requires rollback: %#x\n",

Remove blank line.

> +	if (IS_ERR(fwl))
> +		dev_err(sev->dev, "SEV firmware upload initialization error %ld\n", PTR_ERR(fwl));

!sev was previously checked before calling this, so you only really need
the !sev-fwl check.

Thanks,
Tom

> +		return;
> +

---

## [16] Dionna Amalie Glaze — 2024-11-08
*Subject: Re: [PATCH v5 05/10] crypto: ccp: Add GCTX API to track ASID assignment*

On Fri, Nov 8, 2024 at 9:24 AM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 11/7/24 17:24, Dionna Glaze wrote:

My intention for adding it was for safety, not raw capability.
Is it not safer to ensure that the GCTX used for activation is the one
that is tracked?

>
> > +

Done.

> > +     int ret;
> > +

Done.

> > +
> > +     if (WARN_ONCE(ret, "Failed to release guest context, ret %d", ret))

Done.

> > +             return ret;
> > +
Done.

> > +{
> > +     u32 eax, ebx;
I'm not sure I know what you mean.
> > +     sev_es_max_asid = sev_min_asid - 1;
> > +

Correct. It's to prepare for sev_asid_data to become

struct sev_asid_data {
    union {
        void *snp_context;
        struct {
            u32 handle;
            u32 reserved:31;
            u32 legacy:1;
        } sev;
    };
};

This way we can introduce an ASID api that owns allocation and
synchronization of flushing.

/* allocates an asid, and if SEV-SNP, creates a GCTX page and returns
its physical address in gctx_paddr. */
int sev_alloc_asid(enum sev_asid_kind asid_kind, u64 *gtx_paddr, int *psp_ret)

/* legacy asids free the handle first if not already unbound. SEV-SNP
asids decommission the GCTX page and free the page first. */
int sev_free_asid(int asid, void (*cleanup)(int asid), int *psp_ret);

/* associates ASID with legacy handle and binds it */
int sev_bind_asid_handle(int asid, u32 handle, int *psp_ret);

/* frees a legacy handle associated with the given ASID [deactivate +
decommission] */
int sev_unbind_asid_handle(int asid, int *psp_ret);

Note that the activate / decommission GCTX API additions here are the
SEV-SNP analogy to the bind/unbind for legacy guests.

The sev_unbind_asid_handle function is needed for launch_start's or
receive_start's copy_to_user's failure to undo the successful bind
that preceded it.

This would move all the bitmap and locking onus onto ccp and out of
KVM. I don't see a way to not coordinate deactivation across drivers
awkwardly without also taking ownership of bind/unbind.

> > +     if (!sev_asid_data)
> > +             return -ENOMEM;



--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [17] Dionna Amalie Glaze — 2024-11-08
*Subject: Re: [PATCH v5 04/10] crypto: ccp: Fix uapi definitions of PSP errors*

On Fri, Nov 8, 2024 at 8:15 AM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 11/7/24 17:24, Dionna Glaze wrote:

Ah, okay. Amended with --author="Alexey Kardashevskiy <aik@amd.com>"


> Thanks,
> Tom



--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [18] Dionna Amalie Glaze — 2024-11-08
*Subject: Re: [PATCH v5 06/10] crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support*

On Fri, Nov 8, 2024 at 9:44 AM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 11/7/24 17:24, Dionna Glaze wrote:

Done.


> > +     ret = sev_snp_synthetic_error(sev, psp_ret);
> > +     if (ret)

My bad. I thought I had gotten everything.

Amendments in https://github.com/deeglaze/amdese-linux/tree/snp_hotload-v6

> > +
> >       dev_notice(dev, "sev enabled\n");

Got it.

> >  }
> >
Done.
> > +     return 0;
> > +}
Done.
> > +
> > +     ret = sev_do_cmd(SEV_CMD_SNP_DOWNLOAD_FIRMWARE_EX, data_ex, error);
Done.
> > +     if (ret)
> > +             goto free_err;
Good point. Reset to false in the prepare function.

> > +}
> > +
Done.
> > +                     synthetic_restore_required = true;
> > +                     dev_err(sev->dev, "SNP GCTX update error requires rollback: %#x\n",
Done.
> > +     if (IS_ERR(fwl))
> > +             dev_err(sev->dev, "SEV firmware upload initialization error %ld\n", PTR_ERR(fwl));
Done.

>
> Thanks,



--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [19] Tom Lendacky — 2024-11-11
*Subject: Re: [PATCH v5 05/10] crypto: ccp: Add GCTX API to track ASID
 assignment*

On 11/8/24 16:13, Dionna Amalie Glaze wrote:
> On Fri, Nov 8, 2024 at 9:24 AM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>>

>>
>> But, I don't think that SEV_CMD_SNP_ACTIVATE needs to be here since it

I'm not sure... all the code is really doing at this moment is tracking
guest context pages so that you can update them on firmware changes. Any
misuse of the context page and ASIDs can happen today in KVM so I'm not
sure it matters. And any duplicate ASID usage is recognized when
creating the guest context page.

I guess we can keep it here, though.

>>> +     cpuid(0x8000001f, &eax, &ebx, &sev_max_asid, &sev_min_asid);
>>> +     if (!sev_max_asid)

You only need one of either nr_asids or sev_max_asid. So you could do:

	cpuid(0x8000001f, &eax, &ebx, &sev_max_asid, &sev_min_asid);
	if (!sev_max_asid)
		return -ENODEV;

	/* Bump SEV ASIDs count to allow for simple array checking */
	sev_max_asid++;

Then you can get rid of nr_asids and just use sev_max_asid in the
appropriate places and manner.

Thanks,
Tom

>>> +     sev_es_max_asid = sev_min_asid - 1;
>>> +

---

## [20] Kalra, Ashish — 2024-11-11
*Subject: Re: [PATCH v5 05/10] crypto: ccp: Add GCTX API to track ASID
 assignment*

On 11/7/2024 5:24 PM, Dionna Glaze wrote:
> In preparation for SEV firmware hotloading support, introduce a new way
> to create, activate, and decommission GCTX pages such that ccp is has

This looks to be duplication of ASID management variables and support in KVM.

Probably this stuff needs to be merged with the ASID refactoring work being done to
move all SEV/SNP ASID allocation/management stuff to CCP from KVM.

> +
>  static inline bool sev_version_greater_or_equal(u8 maj, u8 min)

Again, looks to be duplicating ASID setup code in sev_hardware_setup() (in KVM),
maybe all this should be part of the ASID refactoring work to move all SEV/SNP
ASID code to CCP from KVM module, that should then really streamline all ASID/GCTX
tracking.

Thanks,
Ashish

> +
>  static int _sev_platform_init_locked(struct sev_platform_init_args *args)

---

## [21] Dionna Amalie Glaze — 2024-11-11
*Subject: Re: [PATCH v5 05/10] crypto: ccp: Add GCTX API to track ASID assignment*

On Mon, Nov 11, 2024 at 1:16 PM Kalra, Ashish <ashish.kalra@amd.com> wrote:
>
>

Agreed, though there will be duplication until all of the replacement
is ready and KVM can swap over.

> Probably this stuff needs to be merged with the ASID refactoring work being done to
> move all SEV/SNP ASID allocation/management stuff to CCP from KVM.

Who's doing that work? I'm not clear on timelines either. If it's
currently underway, do you see a rebase on this patch set as
particularly challenging?
I wouldn't want to block hotloading support until it's all ready.

> > +
> >  static inline bool sev_version_greater_or_equal(u8 maj, u8 min)

---

## [22] Kalra, Ashish — 2024-11-11
*Subject: Re: [PATCH v5 05/10] crypto: ccp: Add GCTX API to track ASID
 assignment*

On 11/11/2024 3:35 PM, Dionna Amalie Glaze wrote:
> On Mon, Nov 11, 2024 at 1:16 PM Kalra, Ashish <ashish.kalra@amd.com> wrote:
>>

I am currently working on this refactoring work.

> If it's
> currently underway, do you see a rebase on this patch set as

No i don't think it will be difficult to rebase the refactoring work 
with respect to this patchset.

Thanks,
Ashish

> I wouldn't want to block hotloading support until it's all ready.
>

---

## [23] Kalra, Ashish — 2024-11-11
*Subject: Re: [PATCH v5 06/10] crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support*

On 11/7/2024 5:24 PM, Dionna Glaze wrote:
> In order to support firmware hotloading, the DOWNLOAD_FIRMWARE_EX
> command must be available.

fw_cancel is still not being reset to false anywhere, so once set will always cancel
all firmware update requests.

Probably the prepare() callback can set fw_cancel to false at the start of all firmware
update operations.

Thanks,
Ashish

> +}
> +

---

## [24] Dionna Amalie Glaze — 2024-11-11
*Subject: Re: [PATCH v5 06/10] crypto: ccp: Add DOWNLOAD_FIRMWARE_EX support*

On Mon, Nov 11, 2024 at 2:10 PM Kalra, Ashish <ashish.kalra@amd.com> wrote:
>
>

Yes, this is what I have in -v6.
https://github.com/deeglaze/amdese-linux/tree/snp_hotload-v6
I'm waiting one more day on v5 to see if KVM folks have any comment
about the GCTX API before I send it out.

>
> Thanks,

---

## [25] Tom Lendacky — 2024-11-11
*Subject: Re: [PATCH v5 07/10] crypto: ccp: Add preferred access checking
 method*

On 11/7/24 17:24, Dionna Glaze wrote:
> sev_issue_cmd_external_user is the only function that checks permissions
> before performing its task. With the new GCTX API, it's important to

Same comment as before. This commit merely creates a helper function, so
this commit message is not appropriate.

> 
> CC: Sean Christopherson <seanjc@google.com>

Get rid of rc and just do:

	if (!file_is_sev(filep))
		return -EBADF;

Thanks,
Tom

>  
>  	return sev_do_cmd(cmd, data, error);

---

## [26] Tom Lendacky — 2024-11-12
*Subject: Re: [PATCH v5 08/10] KVM: SVM: move sev_issue_cmd_external_user to
 new API*

On 11/7/24 17:24, Dionna Glaze wrote:
> ccp now prefers all calls from external drivers to dominate all calls
> into the driver on behalf of a user with a successful

Would it be simpler to have the new APIs take an fd for an argument,
instead of doing this rework?

Thanks,
Tom

> 
> CC: Sean Christopherson <seanjc@google.com>

---

## [27] Tom Lendacky — 2024-11-12
*Subject: Re: [PATCH v5 09/10] KVM: SVM: Use new ccp GCTX API*

On 11/7/24 17:24, Dionna Glaze wrote:
> Guest context pages should be near 1-to-1 with allocated ASIDs. With the
> GCTX API, the ccp driver is better able to associate guest context pages

Why the name change? It seems like it just makes the patch a bit harder
to follow since there are two things going on.

Thanks,
Tom

>  
>  struct enc_region {

---

## [28] Tom Lendacky — 2024-11-12
*Subject: Re: [PATCH v5 10/10] KVM: SVM: Delay legacy platform initialization
 on SNP*

On 11/7/24 17:24, Dionna Glaze wrote:
> When no SEV or SEV-ES guests are active, then the firmware can be
> updated while (SEV-SNP) VM guests are active.

s/Probe/Setting probe/
s/in order/for an SEV-SNP guest in order/

> +	 * SNP firmware hotloading to be available when SEV-SNP VMs are running.

s/when/when only/

Thanks,
Tom

> +	 */
> +	init_args.probe = vm_type != KVM_X86_SEV_VM && vm_type != KVM_X86_SEV_ES_VM;

---

## [29] Dionna Amalie Glaze — 2024-11-12
*Subject: Re: [PATCH v5 08/10] KVM: SVM: move sev_issue_cmd_external_user to
 new API*

On Tue, Nov 12, 2024 at 7:52 AM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 11/7/24 17:24, Dionna Glaze wrote:

Simpler but I think worse?
The choice of using sev_do_cmd versus __sev_issue_cmd in kvm's
implementation is the matter of dominance of access checking.
There's no need to check the fd in the activate function or
decommission function. It's not needed to be checked in a loop for
snp_launch_update.
I can either complete the removal of __sev_issue_cmd in this patch or
move to make the context creation function take an fd. What do you
think is better?


>
> Thanks,



--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [30] Dionna Amalie Glaze — 2024-11-12
*Subject: Re: [PATCH v5 09/10] KVM: SVM: Use new ccp GCTX API*

> > diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
> > index cea41b8cdabe4..d7cef84750b33 100644

KVM and ccp both seem to like to name their functions starting with
sev_ or snp_, and it's particularly hard to determine provenance.

snp_decommision_context and sev_snp_guest_decommission... which is
from where? It's weird to me.

> Thanks,
> Tom

---

## [31] Dionna Amalie Glaze — 2024-11-12
*Subject: Re: [PATCH v5 07/10] crypto: ccp: Add preferred access checking method*

On Mon, Nov 11, 2024 at 2:46 PM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 11/7/24 17:24, Dionna Glaze wrote:

Is this a meta-comment about how the commit presupposes being in a
series with a goal, but should have a self-contained commit message? I
don't know what "same comment as before" you're referring to.
How about this:

crypto: ccp: Add file_is_sev to identify access

Access to the ccp driver only needs to be determined once, so
sev_issue_cmd_external_user called in a loop (e.g. for
SNP_LAUNCH_UPDATE) does more than it needs to.

The file_is_sev function allows the caller to determine access before using
sev_do_cmd or other API methods multiple times without extra access
checking.

This also fixes the header comment that the bad file error code is
-%EINVAL when in fact it is -%EBADF.

---

## [32] Tom Lendacky — 2024-11-12
*Subject: Re: [PATCH v5 07/10] crypto: ccp: Add preferred access checking
 method*

On 11/12/24 13:47, Dionna Amalie Glaze wrote:
> On Mon, Nov 11, 2024 at 2:46 PM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>>

I made the same comment in your previous series.

> How about this:
> 

once per KVM ioctl invocation

> sev_issue_cmd_external_user called in a loop (e.g. for
> SNP_LAUNCH_UPDATE) does more than it needs to.

Yes, I like this better.

Thanks,
Tom

> 
>

---

## [33] Tom Lendacky — 2024-11-12
*Subject: Re: [PATCH v5 09/10] KVM: SVM: Use new ccp GCTX API*

On 11/12/24 13:33, Dionna Amalie Glaze wrote:
>>> diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
>>> index cea41b8cdabe4..d7cef84750b33 100644

I guess I don't see the problem, a quick git grep -w of the name will
show you where each is. Its a static function in the file, so if
anything just changing/shortening the name to decommission_snp_context()
would be better (especially since nothing in the svm directory should
have a name that starts with kvm_).

Thanks,
Tom

> 
>> Thanks,

---

## [34] Tom Lendacky — 2024-11-12
*Subject: Re: [PATCH v5 08/10] KVM: SVM: move sev_issue_cmd_external_user to
 new API*

On 11/12/24 13:30, Dionna Amalie Glaze wrote:
> On Tue, Nov 12, 2024 at 7:52 AM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>>

Very true.

> I can either complete the removal of __sev_issue_cmd in this patch or
> move to make the context creation function take an fd. What do you

The re-work you're looking at doing is probably a patch series on its
own. I don't think you need to do all that work for this series. You
just need to be sure that each command invocation that requires the fd
check doesn't lose that in an ioctl() path for now.

Thanks,
Tom

> 
>

---

## [35] Sean Christopherson — 2024-11-13
*Subject: Re: [PATCH v5 09/10] KVM: SVM: Use new ccp GCTX API*

On Tue, Nov 12, 2024, Tom Lendacky wrote:
> On 11/12/24 13:33, Dionna Amalie Glaze wrote:
> >>> diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c

Eh, that creates just as many problems as it solves, because it mucks up the
namespace and leads to discontinuity between the decommission helper and things
like snp_launch_update_vmsa() and snp_launch_finish().

I agree that there isn't a strong need to fixup static symbols.  That said, I do
think drivers/crypto/ccp/sev-dev.c in particular needs a different namespace, and
needs to use it consistently, to make it somewhat obvious that it's (almost) all
about the PSP/ASP.

But IMO, an even bigger mess in that area is the lack of consistency in the APIs
themselves.  E.g. this code where KVM uses sev_do_cmd() directly for SNP, but
bounces through a wrapper for !SNP.  Eww.

	wbinvd_on_all_cpus();

	if (sev_snp_enabled)
		ret = sev_do_cmd(SEV_CMD_SNP_DF_FLUSH, NULL, &error);
	else
		ret = sev_guest_df_flush(&error);

	up_write(&sev_deactivate_lock);


And then KVM has snp_page_reclaim(), but the PSP/ASP driver has snp_reclaim_pages().

So if we want to start renaming things, I vote to go a step further and clean up
the APIs, e.g. with a goal of eliminating sev_do_cmd(), and possibly of making
the majority of the PSP-defined structures in include/linux/psp-sev.h "private"
to the PSP/ASP driver.

> would be better (especially since nothing in the svm directory should
> have a name that starts with kvm_).

+1 to not using "kvm_".  KVM often uses "kvm_" to differentiate globally visible
symbols from local (static) symbols.  I.e. prepending "kvm_" just trades one
confusing name for another.

---
