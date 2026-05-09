---
title: 'SEV-SNP: Add KVM support for attestation'
date: 2024-06-28
last_reply: 2024-06-28
message_count: 5
participants: ['Michael Roth']
---

## [1] Michael Roth — 2024-06-28

This patchset is also available at:

  https://github.com/amdese/linux/commits/snp-guest-req-v2

and is based on top of kvm-coco-queue (ace0c64d8975):

  https://git.kernel.org/pub/scm/virt/kvm/kvm.git/log/?h=kvm-coco-queue

As discussed on the PUCK call a few weeks backs, I'm re-submitting as a
separate patchset the SNP guest request support that was originally part of
the SNP KVM base support patchset that's now in kvm/next and will be in
kernel 6.11. This support is needed to ensure fully compliance with GHCB
2.0 specification and to support attestation in general, so I'm hoping it
can also make it into 6.11.

I've dropped patches 4-5 from v1 of this series that implemented
KVM_EXIT_COCO and handling for userspace-provided certificate data so that
there's more time to get the API ironed out.


Overview
--------

The GHCB 2.0 specification defines 2 GHCB request types to allow SNP guests
to send encrypted messages/requests to firmware: SNP Guest Requests and SNP
Extended Guest Requests. These encrypted messages are used for things like
servicing attestation requests issued by the guest. Implementing support for
these is required to be fully GHCB-compliant.

For the most part, KVM only needs to handle forwarding these requests to
firmware (to be issued via the SNP_GUEST_REQUEST firmware command defined
in the SEV-SNP Firmware ABI), and then forwarding the encrypted response to
the guest.

However, in the case of SNP Extended Guest Requests, the host is also
able to provide the certificate data corresponding to the endorsement key
used by firmware to sign attestation report requests. This certificate data
is provided by userspace because:

  1) It allows for different keys/key types to be used for each particular
     guest with requiring any sort of KVM API to configure the certificate
     table in advance on a per-guest basis.

  2) It provides additional flexibility with how attestation requests might
     be handled during live migration where the certificate data for
     source/dest might be different.

  3) It allows all synchronization between certificates and firmware/signing
     key updates to be handled purely by userspace rather than requiring
     some in-kernel mechanism to facilitate it. [1]

To support fetching certificate data from userspace, a new KVM exit type will
be needed to handle fetching the certificate from userspace. An attempt to
define a new KVM_EXIT_COCO/KVM_EXIT_COCO_REQ_CERTS exit type to handle this
was introduced in v1 of this patchset, but is still being discussed by
community, so for now this patchset only implements a stub version of SNP
Extended Guest Requests that does not provide certificate data, but is still
enough to provide compliance with the GHCB 2.0 spec.

[1] https://lore.kernel.org/kvm/ZS614OSoritrE1d2@google.com/

Any feedback/review is appreciated.

Thanks!

-Mike

Changes since v1:

 * Fix cleanup path when handling firmware error (Liam, Sean)
 * Use bounce-pages for interacting with firmware rather than passing in the
   guest-provided pages directly. (Sean)
 * Drop SNP_GUEST_VMM_ERR_GENERIC and rely solely on firmware-provided error
   code to report any firmware error to the guest. (Sean)
 * Use kvm_clear_guest() to handle writing empty certificate table instead 
   of kvm_write_guest() (Sean)
 * Add additional comments in commit messages and throughout code to better
   explain the interactions with firmware/guest. (Sean)
 * Drop 4K-alignment restrictions on the guest-provided req/resp buffers,
   since the GHCB-spec only specifically requires they fit within 4K,
   not necessarily that they be 4K-aligned. Additionally, the bounce
   pages passed to firmware will be 4K-aligned regardless.

Changes since splitting this off from v15 SNP KVM patchset:

 * Address clang-reported warnings regarding uninitialized variables 
 * Address a memory leak of the request/response buffer pages, and refactor
   the code based on Sean's suggestions:
   https://lore.kernel.org/kvm/ZktbBRLXeOp9X6aH@google.com/
 * Fix SNP Extended Guest Request handling to only attempt to fetch
   certificates if handling MSG_REQ_REPORT (attestation) message types
 * Drop KVM_EXIT_VMGEXIT and introduce KVM_EXIT_COCO events instead
 * Refactor patch layout for easier handling/review

----------------------------------------------------------------
Brijesh Singh (1):
      KVM: SEV: Provide support for SNP_GUEST_REQUEST NAE event

Michael Roth (2):
      x86/sev: Move sev_guest.h into common SEV header
      KVM: SEV: Provide support for SNP_EXTENDED_GUEST_REQUEST NAE event

 arch/x86/include/asm/sev.h              |  48 ++++++++
 arch/x86/kvm/svm/sev.c                  | 187 ++++++++++++++++++++++++++++++++
 arch/x86/kvm/svm/svm.h                  |   3 +
 drivers/virt/coco/sev-guest/sev-guest.c |   2 -
 drivers/virt/coco/sev-guest/sev-guest.h |  63 -----------
 include/uapi/linux/sev-guest.h          |   3 +
 6 files changed, 241 insertions(+), 65 deletions(-)
 delete mode 100644 drivers/virt/coco/sev-guest/sev-guest.h

---

## [2] Michael Roth — 2024-06-28
*Subject: [PATCH v2 1/3] KVM: SEV: Provide support for SNP_GUEST_REQUEST NAE event*

From: Brijesh Singh <brijesh.singh@amd.com>

Version 2 of GHCB specification added support for the SNP Guest Request
Message NAE event. The event allows for an SEV-SNP guest to make
requests to the SEV-SNP firmware through hypervisor using the
SNP_GUEST_REQUEST API defined in the SEV-SNP firmware specification.

This is used by guests primarily to request attestation reports from
firmware. There are other request types are available as well, but the
specifics of what guest requests are being made are opaque to the
hypervisor, which only serves as a proxy for the guest requests and
firmware responses.

Implement handling for these events.

When an SNP Guest Request is issued, the guest will provide its own
request/response pages, which could in theory be passed along directly
to firmware. However, these pages would need special care:

  - Both pages are from shared guest memory, so they need to be
    protected from migration/etc. occurring while firmware reads/writes
    to them. At a minimum, this requires elevating the ref counts and
    potentially needing an explicit pinning of the memory. This places
    additional restrictions on what type of memory backends userspace
    can use for shared guest memory since there would be some reliance
    on using refcounted pages.

  - The response page needs to be switched to Firmware-owned state
    before the firmware can write to it, which can lead to potential
    host RMP #PFs if the guest is misbehaved and hands the host a
    guest page that KVM is writing to for other reasons (e.g. virtio
    buffers).

Both of these issues can be avoided completely by using
separately-allocated bounce pages for both the request/response pages
and passing those to firmware instead. So that's the approach taken
here.

Signed-off-by: Brijesh Singh <brijesh.singh@amd.com>
Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Liam Merwick <liam.merwick@oracle.com>
[mdr: ensure FW command failures are indicated to guest, drop extended
 request handling to be re-written as separate patch, massage commit]
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c         | 131 +++++++++++++++++++++++++++++++++
 arch/x86/kvm/svm/svm.h         |   3 +
 include/uapi/linux/sev-guest.h |   3 +
 3 files changed, 137 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index df8818759698..e7f5225293ae 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/misc_cgroup.h>
 #include <linux/processor.h>
 #include <linux/trace_events.h>
+#include <uapi/linux/sev-guest.h>
 
 #include <asm/pkru.h>
 #include <asm/trapnr.h>
@@ -326,6 +327,78 @@ static void sev_unbind_asid(struct kvm *kvm, unsigned int handle)
 	sev_decommission(handle);
 }
 
+/*
+ * This sets up bounce buffers/firmware pages to handle SNP Guest Request
+ * messages (e.g. attestation requests). See "SNP Guest Request" in the GHCB
+ * 2.0 specification for more details.
+ *
+ * Technically, when an SNP Guest Request is issued, the guest will provide its
+ * own request/response pages, which could in theory be passed along directly
+ * to firmware rather than using bounce pages. However, these pages would need
+ * special care:
+ *
+ *   - Both pages are from shared guest memory, so they need to be protected
+ *     from migration/etc. occurring while firmware reads/writes to them. At a
+ *     minimum, this requires elevating the ref counts and potentially needing
+ *     an explicit pinning of the memory. This places additional restrictions
+ *     on what type of memory backends userspace can use for shared guest
+ *     memory since there is some reliance on using refcounted pages.
+ *
+ *   - The response page needs to be switched to Firmware-owned[1] state
+ *     before the firmware can write to it, which can lead to potential
+ *     host RMP #PFs if the guest is misbehaved and hands the host a
+ *     guest page that KVM might write to for other reasons (e.g. virtio
+ *     buffers/etc.).
+ *
+ * Both of these issues can be avoided completely by using separately-allocated
+ * bounce pages for both the request/response pages and passing those to
+ * firmware instead. So that's what is being set up here.
+ *
+ * Guest requests rely on message sequence numbers to ensure requests are
+ * issued to firmware in the order the guest issues them, so concurrent guest
+ * requests generally shouldn't happen. But a misbehaved guest could issue
+ * concurrent guest requests in theory, so a mutex is used to serialize
+ * access to the bounce buffers.
+ *
+ * [1] See the "Page States" section of the SEV-SNP Firmware ABI for more
+ *     details on Firmware-owned pages, along with "RMP and VMPL Access Checks"
+ *     in the APM for details on the related RMP restrictions.
+ */
+static int snp_guest_req_init(struct kvm *kvm)
+{
+	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
+	struct page *req_page;
+
+	req_page = alloc_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+	if (!req_page)
+		return -ENOMEM;
+
+	sev->guest_resp_buf = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+	if (!sev->guest_resp_buf) {
+		__free_page(req_page);
+		return -EIO;
+	}
+
+	sev->guest_req_buf = page_address(req_page);
+	mutex_init(&sev->guest_req_mutex);
+
+	return 0;
+}
+
+static void snp_guest_req_cleanup(struct kvm *kvm)
+{
+	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
+
+	if (sev->guest_resp_buf)
+		snp_free_firmware_page(sev->guest_resp_buf);
+
+	if (sev->guest_req_buf)
+		__free_page(virt_to_page(sev->guest_req_buf));
+
+	sev->guest_req_buf = NULL;
+	sev->guest_resp_buf = NULL;
+}
+
 static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 			    struct kvm_sev_init *data,
 			    unsigned long vm_type)
@@ -376,6 +449,10 @@ static int __sev_guest_init(struct kvm *kvm, struct kvm_sev_cmd *argp,
 	if (ret)
 		goto e_free;
 
+	/* This needs to happen after SEV/SNP firmware initialization. */
+	if (vm_type == KVM_X86_SNP_VM && snp_guest_req_init(kvm))
+		goto e_free;
+
 	INIT_LIST_HEAD(&sev->regions_list);
 	INIT_LIST_HEAD(&sev->mirror_vms);
 	sev->need_init = false;
@@ -2850,6 +2927,8 @@ void sev_vm_destroy(struct kvm *kvm)
 	}
 
 	if (sev_snp_guest(kvm)) {
+		snp_guest_req_cleanup(kvm);
+
 		/*
 		 * Decomission handles unbinding of the ASID. If it fails for
 		 * some unexpected reason, just leak the ASID.
@@ -3321,6 +3400,10 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 		if (!sev_snp_guest(vcpu->kvm) || !kvm_ghcb_sw_scratch_is_valid(svm))
 			goto vmgexit_err;
 		break;
+	case SVM_VMGEXIT_GUEST_REQUEST:
+		if (!sev_snp_guest(vcpu->kvm))
+			goto vmgexit_err;
+		break;
 	default:
 		reason = GHCB_ERR_INVALID_EVENT;
 		goto vmgexit_err;
@@ -3939,6 +4022,51 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 	return ret;
 }
 
+static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)
+{
+	struct sev_data_snp_guest_request data = {0};
+	struct kvm *kvm = svm->vcpu.kvm;
+	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
+	sev_ret_code fw_err = 0;
+	int ret;
+
+	if (!sev_snp_guest(kvm))
+		return -EINVAL;
+
+	mutex_lock(&sev->guest_req_mutex);
+
+	if (kvm_read_guest(kvm, req_gpa, sev->guest_req_buf, PAGE_SIZE)) {
+		ret = -EIO;
+		goto out_unlock;
+	}
+
+	data.gctx_paddr = __psp_pa(sev->snp_context);
+	data.req_paddr = __psp_pa(sev->guest_req_buf);
+	data.res_paddr = __psp_pa(sev->guest_resp_buf);
+
+	/*
+	 * Firmware failures are propagated on to guest, but any other failure
+	 * condition along the way should be reported to userspace. E.g. if
+	 * the PSP is dead and commands are timing out.
+	 */
+	ret = sev_issue_cmd(kvm, SEV_CMD_SNP_GUEST_REQUEST, &data, &fw_err);
+	if (ret && !fw_err)
+		goto out_unlock;
+
+	if (kvm_write_guest(kvm, resp_gpa, sev->guest_resp_buf, PAGE_SIZE)) {
+		ret = -EIO;
+		goto out_unlock;
+	}
+
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(0, fw_err));
+
+	ret = 1; /* resume guest */
+
+out_unlock:
+	mutex_unlock(&sev->guest_req_mutex);
+	return ret;
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4213,6 +4341,9 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 
 		ret = 1;
 		break;
+	case SVM_VMGEXIT_GUEST_REQUEST:
+		ret = snp_handle_guest_req(svm, control->exit_info_1, control->exit_info_2);
+		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
 		vcpu_unimpl(vcpu,
 			    "vmgexit: unsupported event - exit_info_1=%#llx, exit_info_2=%#llx\n",
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index d2397b98bbf0..1090068f8f70 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -95,6 +95,9 @@ struct kvm_sev_info {
 	struct misc_cg *misc_cg; /* For misc cgroup accounting */
 	atomic_t migration_in_progress;
 	void *snp_context;      /* SNP guest context page */
+	void *guest_req_buf;    /* Bounce buffer for SNP Guest Request input */
+	void *guest_resp_buf;   /* Bounce buffer for SNP Guest Request output */
+	struct mutex guest_req_mutex; /* Must acquire before using bounce buffers */
 };
 
 struct kvm_svm {
diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
index 154a87a1eca9..fcdfea767fca 100644
--- a/include/uapi/linux/sev-guest.h
+++ b/include/uapi/linux/sev-guest.h
@@ -89,6 +89,9 @@ struct snp_ext_report_req {
 #define SNP_GUEST_FW_ERR_MASK		GENMASK_ULL(31, 0)
 #define SNP_GUEST_VMM_ERR_SHIFT		32
 #define SNP_GUEST_VMM_ERR(x)		(((u64)x) << SNP_GUEST_VMM_ERR_SHIFT)
+#define SNP_GUEST_FW_ERR(x)		((x) & SNP_GUEST_FW_ERR_MASK)
+#define SNP_GUEST_ERR(vmm_err, fw_err)	(SNP_GUEST_VMM_ERR(vmm_err) | \
+					 SNP_GUEST_FW_ERR(fw_err))
 
 #define SNP_GUEST_VMM_ERR_INVALID_LEN	1
 #define SNP_GUEST_VMM_ERR_BUSY		2

---

## [3] Michael Roth — 2024-06-28
*Subject: [PATCH v2 2/3] x86/sev: Move sev_guest.h into common SEV header*

sev_guest.h currently contains various definitions relating to the
format of SNP_GUEST_REQUEST commands to SNP firmware. Currently only the
sev-guest driver makes use of them, but when the KVM side of this is
implemented there's a need to parse the SNP_GUEST_REQUEST header to
determine whether additional information needs to be provided to the
guest. Prepare for this by moving those definitions to a common header
that's shared by host/guest code so that KVM can also make use of them.

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Liam Merwick <liam.merwick@oracle.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/include/asm/sev.h              | 48 +++++++++++++++++++
 drivers/virt/coco/sev-guest/sev-guest.c |  2 -
 drivers/virt/coco/sev-guest/sev-guest.h | 63 -------------------------
 3 files changed, 48 insertions(+), 65 deletions(-)
 delete mode 100644 drivers/virt/coco/sev-guest/sev-guest.h

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 1936f37e3371..72f9ba3a2fee 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -119,6 +119,54 @@ struct snp_req_data {
 	unsigned int data_npages;
 };
 
+#define MAX_AUTHTAG_LEN		32
+
+/* See SNP spec SNP_GUEST_REQUEST section for the structure */
+enum msg_type {
+	SNP_MSG_TYPE_INVALID = 0,
+	SNP_MSG_CPUID_REQ,
+	SNP_MSG_CPUID_RSP,
+	SNP_MSG_KEY_REQ,
+	SNP_MSG_KEY_RSP,
+	SNP_MSG_REPORT_REQ,
+	SNP_MSG_REPORT_RSP,
+	SNP_MSG_EXPORT_REQ,
+	SNP_MSG_EXPORT_RSP,
+	SNP_MSG_IMPORT_REQ,
+	SNP_MSG_IMPORT_RSP,
+	SNP_MSG_ABSORB_REQ,
+	SNP_MSG_ABSORB_RSP,
+	SNP_MSG_VMRK_REQ,
+	SNP_MSG_VMRK_RSP,
+
+	SNP_MSG_TYPE_MAX
+};
+
+enum aead_algo {
+	SNP_AEAD_INVALID,
+	SNP_AEAD_AES_256_GCM,
+};
+
+struct snp_guest_msg_hdr {
+	u8 authtag[MAX_AUTHTAG_LEN];
+	u64 msg_seqno;
+	u8 rsvd1[8];
+	u8 algo;
+	u8 hdr_version;
+	u16 hdr_sz;
+	u8 msg_type;
+	u8 msg_version;
+	u16 msg_sz;
+	u32 rsvd2;
+	u8 msg_vmpck;
+	u8 rsvd3[35];
+} __packed;
+
+struct snp_guest_msg {
+	struct snp_guest_msg_hdr hdr;
+	u8 payload[4000];
+} __packed;
+
 struct sev_guest_platform_data {
 	u64 secrets_gpa;
 };
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 654290a8e1ba..f0ea26f18cbf 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -29,8 +29,6 @@
 #include <asm/svm.h>
 #include <asm/sev.h>
 
-#include "sev-guest.h"
-
 #define DEVICE_NAME	"sev-guest"
 #define AAD_LEN		48
 #define MSG_HDR_VER	1
diff --git a/drivers/virt/coco/sev-guest/sev-guest.h b/drivers/virt/coco/sev-guest/sev-guest.h
deleted file mode 100644
index 21bda26fdb95..000000000000
--- a/drivers/virt/coco/sev-guest/sev-guest.h
+++ /dev/null
@@ -1,63 +0,0 @@
-/* SPDX-License-Identifier: GPL-2.0-only */
-/*
- * Copyright (C) 2021 Advanced Micro Devices, Inc.
- *
- * Author: Brijesh Singh <brijesh.singh@amd.com>
- *
- * SEV-SNP API spec is available at https://developer.amd.com/sev
- */
-
-#ifndef __VIRT_SEVGUEST_H__
-#define __VIRT_SEVGUEST_H__
-
-#include <linux/types.h>
-
-#define MAX_AUTHTAG_LEN		32
-
-/* See SNP spec SNP_GUEST_REQUEST section for the structure */
-enum msg_type {
-	SNP_MSG_TYPE_INVALID = 0,
-	SNP_MSG_CPUID_REQ,
-	SNP_MSG_CPUID_RSP,
-	SNP_MSG_KEY_REQ,
-	SNP_MSG_KEY_RSP,
-	SNP_MSG_REPORT_REQ,
-	SNP_MSG_REPORT_RSP,
-	SNP_MSG_EXPORT_REQ,
-	SNP_MSG_EXPORT_RSP,
-	SNP_MSG_IMPORT_REQ,
-	SNP_MSG_IMPORT_RSP,
-	SNP_MSG_ABSORB_REQ,
-	SNP_MSG_ABSORB_RSP,
-	SNP_MSG_VMRK_REQ,
-	SNP_MSG_VMRK_RSP,
-
-	SNP_MSG_TYPE_MAX
-};
-
-enum aead_algo {
-	SNP_AEAD_INVALID,
-	SNP_AEAD_AES_256_GCM,
-};
-
-struct snp_guest_msg_hdr {
-	u8 authtag[MAX_AUTHTAG_LEN];
-	u64 msg_seqno;
-	u8 rsvd1[8];
-	u8 algo;
-	u8 hdr_version;
-	u16 hdr_sz;
-	u8 msg_type;
-	u8 msg_version;
-	u16 msg_sz;
-	u32 rsvd2;
-	u8 msg_vmpck;
-	u8 rsvd3[35];
-} __packed;
-
-struct snp_guest_msg {
-	struct snp_guest_msg_hdr hdr;
-	u8 payload[4000];
-} __packed;
-
-#endif /* __VIRT_SEVGUEST_H__ */

---

## [4] Michael Roth — 2024-06-28
*Subject: [PATCH v2 3/3] KVM: SEV: Provide support for SNP_EXTENDED_GUEST_REQUEST NAE event*

Version 2 of GHCB specification added support for the SNP Extended Guest
Request Message NAE event. This event serves a nearly identical purpose
to the previously-added SNP_GUEST_REQUEST event, but for certain message
types it allows the guest to supply a buffer to be used for additional
information in some cases.

Currently the GHCB spec only defines extended handling of this sort in
the case of attestation requests, where the additional buffer is used to
supply a table of certificate data corresponding to the attestion
report's signing key. Support for this extended handling will require
additional KVM APIs to handle coordinating with userspace.

Whether or not the hypervisor opts to provide this certificate data is
optional. However, support for processing SNP_EXTENDED_GUEST_REQUEST
GHCB requests is required by the GHCB 2.0 specification for SNP guests,
so for now implement a stub implementation that provides an empty
certificate table to the guest if it supplies an additional buffer, but
otherwise behaves identically to SNP_GUEST_REQUEST.

Reviewed-by: Carlos Bilbao <carlos.bilbao.osdev@gmail.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Liam Merwick <liam.merwick@oracle.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c | 56 ++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 56 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index e7f5225293ae..a26e5b191d4a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3401,6 +3401,7 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 			goto vmgexit_err;
 		break;
 	case SVM_VMGEXIT_GUEST_REQUEST:
+	case SVM_VMGEXIT_EXT_GUEST_REQUEST:
 		if (!sev_snp_guest(vcpu->kvm))
 			goto vmgexit_err;
 		break;
@@ -4067,6 +4068,58 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 	return ret;
 }
 
+static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)
+{
+	struct kvm *kvm = svm->vcpu.kvm;
+	u8 msg_type;
+
+	if (!sev_snp_guest(kvm))
+		return -EINVAL;
+
+	if (kvm_read_guest(kvm, req_gpa + offsetof(struct snp_guest_msg_hdr, msg_type),
+			   &msg_type, 1))
+		return -EIO;
+
+	/*
+	 * As per GHCB spec, requests of type MSG_REPORT_REQ also allow for
+	 * additional certificate data to be provided alongside the attestation
+	 * report via the guest-provided data pages indicated by RAX/RBX. The
+	 * certificate data is optional and requires additional KVM enablement
+	 * to provide an interface for userspace to provide it, but KVM still
+	 * needs to be able to handle extended guest requests either way. So
+	 * provide a stub implementation that will always return an empty
+	 * certificate table in the guest-provided data pages.
+	 */
+	if (msg_type == SNP_MSG_REPORT_REQ) {
+		struct kvm_vcpu *vcpu = &svm->vcpu;
+		u64 data_npages;
+		gpa_t data_gpa;
+
+		if (!kvm_ghcb_rax_is_valid(svm) || !kvm_ghcb_rbx_is_valid(svm))
+			goto request_invalid;
+
+		data_gpa = vcpu->arch.regs[VCPU_REGS_RAX];
+		data_npages = vcpu->arch.regs[VCPU_REGS_RBX];
+
+		if (!PAGE_ALIGNED(data_gpa))
+			goto request_invalid;
+
+		/*
+		 * As per GHCB spec (see "SNP Extended Guest Request"), the
+		 * certificate table is terminated by 24-bytes of zeroes.
+		 */
+		if (data_npages && kvm_clear_guest(kvm, data_gpa, 24))
+			return -EIO;
+	}
+
+	return snp_handle_guest_req(svm, req_gpa, resp_gpa);
+
+request_invalid:
+	ghcb_set_sw_exit_info_1(svm->sev_es.ghcb, 2);
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, GHCB_ERR_INVALID_INPUT);
+	return 1; /* resume guest */
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4344,6 +4397,9 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 	case SVM_VMGEXIT_GUEST_REQUEST:
 		ret = snp_handle_guest_req(svm, control->exit_info_1, control->exit_info_2);
 		break;
+	case SVM_VMGEXIT_EXT_GUEST_REQUEST:
+		ret = snp_handle_ext_guest_req(svm, control->exit_info_1, control->exit_info_2);
+		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
 		vcpu_unimpl(vcpu,
 			    "vmgexit: unsupported event - exit_info_1=%#llx, exit_info_2=%#llx\n",

---

## [5] Michael Roth — 2024-06-28
*Subject: Re: [PATCH v2 0/3] SEV-SNP: Add KVM support for attestation*

On Fri, Jun 28, 2024 at 01:52:41PM -0500, Michael Roth wrote:
> Changes since v1:
> 

It turns out my eyeballs were not functional when I reached that
conclusion and it's clearly documented that the pages needed to be
4K-aligned in the GHCB spec.

With the current implementation, KVM can actually handle unaligned
req/resp GPAs thanks to the bounce buffers, but it should still be
enforced. So I will resend a v3 with this change, but leave a bit more
time in case there are other review comments for v2.

Thanks,

Mike

>    not necessarily that they be 4K-aligned. Additionally, the bounce
>    pages passed to firmware will be 4K-aligned regardless.

---
