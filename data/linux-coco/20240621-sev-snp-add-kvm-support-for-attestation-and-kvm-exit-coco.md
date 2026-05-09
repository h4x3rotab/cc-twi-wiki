---
title: 'SEV-SNP: Add KVM support for attestation and KVM_EXIT_COCO'
date: 2024-06-21
last_reply: 2024-11-20
message_count: 40
participants: ['Michael Roth', 'Liam Merwick', 'Tom Lendacky', 'Carlos Bilbao', 'Sean Christopherson', 'Peter Gonda', 'Binbin Wu', 'Dionna Amalie Glaze']
---

## [1] Michael Roth — 2024-06-21

This patchset is also available at:

  https://github.com/amdese/linux/commits/snp-guest-req-v1

and is based on top of kvm-coco-queue (ace0c64d8975):

  https://git.kernel.org/pub/scm/virt/kvm/kvm.git/log/?h=kvm-coco-queue

As discussed on the PUCK call a few weeks back, I'm re-submitting as a
separate patchset the SNP guest request support that was originally part of
the SNP KVM base support patchset that's now in kvm/next and will be in
kernel 6.11. This support is needed to ensure fully compliance with GHCB
2.0 specification and to support attestation in general, so I'm hoping it
can also make it into 6.11.

I've tried to organize things so the first 3 patches can be applied without
too much controversy and decoupled from any discussion regarding the
KVM_EXIT_COCO/KVM_EXIT_COCO_REQ_CERTS APIs, since the APIs are only needed
specifically to add optional support for userspace-provided certificate
data. That said, I have based those APIs around what was discussed during
the above-mentioned PUCK call, so I'm hoping the API bits aren't too far
off from whatever the consensus ends up being.


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

To support fetching certificate data from userspace, a new KVM exit type is
used to fetch the data similarly to KVM_EXIT_MMIO/etc. Since there is
potential for more CoCo-related exits, this series implements this as a more
general KVM_EXIT_COCO exit type, where individual sub-types can be enabled
similarly to how KVM_EXIT_HYPERCALL/KVM_CAP_EXIT_HYPERCALL are handling, and
then introduces the KVM_EXIT_COCO_REQ_CERTS sub-type to implement certficate
handling.

[1] https://lore.kernel.org/kvm/ZS614OSoritrE1d2@google.com/


Patch Layout
------------

1-3: These patches provide a base implementation of SNP_GUEST_REQUEST and
     SNP_EXTENDED_GUEST_REQUEST that satisfies the requirements of the GHCB
     2.0 specification, but does not implement optional support for providing
     a certificate table for SNP_EXTENDED_GUEST_REQUEST messages
     corresponding to attestation requests.

  4: This patch introduces/documents the KVM API for KVM_EXIT_COCO along with
     it's first sub-type, KVM_EXIT_COCO_REQ_CERTS, which will be used to
     fetch certificate table data from userspace.

  5: This patch makes use of the KVM_EXIT_COCO_REQ_CERTS event to allow
     certificate table data to be fetched from userspace and provided to the
     guest when attestation requests are issued via
     SNP_EXTENDED_GUEST_REQUEST messages.


Testing
-------

For testing this via QEMU, use the following tree:

  https://github.com/amdese/qemu/commits/snp-guest-req-v1-wip1

A basic command-line invocation for SNP would be:

 qemu-system-x86_64 -smp 32,maxcpus=255 -cpu EPYC-Milan-v2
  -machine q35,confidential-guest-support=sev0,memory-backend=ram1
  -object memory-backend-memfd,id=ram1,size=4G,share=true,reserve=false
  -object sev-snp-guest,id=sev0,cbitpos=51,reduced-phys-bits=1,id-auth=
  -bios OVMF_CODE-upstream-20240410-apic-mmio-fix1d-AmdSevX64.fd

With certificate data supplied:

 qemu-system-x86_64 -smp 32,maxcpus=255 -cpu EPYC-Milan-v2
  -machine q35,confidential-guest-support=sev0,memory-backend=ram1
  -object memory-backend-memfd,id=ram1,size=4G,share=true,reserve=false
  -object sev-snp-guest,id=sev0,cbitpos=51,reduced-phys-bits=1,id-auth=,certs-path=/home/mroth/cert.blob
  -bios OVMF_CODE-upstream-20240410-apic-mmio-fix1d-AmdSevX64.fd

The format of the certificate blob is defined in the GHCB 2.0 specification,
but if it's not being parsed on the guest-side then random data will suffice
for testing the KVM bits.


Any feedback/review is appreciated.

Thanks!

-Mike


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

Michael Roth (4):
      x86/sev: Move sev_guest.h into common SEV header
      KVM: SEV: Provide support for SNP_EXTENDED_GUEST_REQUEST NAE event
      KVM: Introduce KVM_EXIT_COCO exit type
      KVM: SEV: Add certificate support for SNP_EXTENDED_GUEST_REQUEST events

 Documentation/virt/kvm/api.rst          | 109 ++++++++++++++++++++++
 arch/x86/include/asm/kvm_host.h         |   1 +
 arch/x86/include/asm/sev.h              |  48 ++++++++++
 arch/x86/kvm/svm/sev.c                  | 158 ++++++++++++++++++++++++++++++++
 arch/x86/kvm/x86.c                      |  13 +++
 drivers/virt/coco/sev-guest/sev-guest.c |   2 -
 drivers/virt/coco/sev-guest/sev-guest.h |  63 -------------
 include/uapi/linux/kvm.h                |  20 ++++
 include/uapi/linux/sev-guest.h          |   9 ++
 9 files changed, 358 insertions(+), 65 deletions(-)
 delete mode 100644 drivers/virt/coco/sev-guest/sev-guest.h

---

## [2] Michael Roth — 2024-06-21
*Subject: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST NAE event*

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

Signed-off-by: Brijesh Singh <brijesh.singh@amd.com>
Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
[mdr: ensure FW command failures are indicated to guest, drop extended
 request handling to be re-written as separate patch, massage commit]
Signed-off-by: Michael Roth <michael.roth@amd.com>
Message-ID: <20240501085210.2213060-19-michael.roth@amd.com>
Signed-off-by: Paolo Bonzini <pbonzini@redhat.com>
---
 arch/x86/kvm/svm/sev.c         | 69 ++++++++++++++++++++++++++++++++++
 include/uapi/linux/sev-guest.h |  9 +++++
 2 files changed, 78 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index df8818759698..7338b987cadd 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/misc_cgroup.h>
 #include <linux/processor.h>
 #include <linux/trace_events.h>
+#include <uapi/linux/sev-guest.h>
 
 #include <asm/pkru.h>
 #include <asm/trapnr.h>
@@ -3321,6 +3322,10 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
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
@@ -3939,6 +3944,67 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 	return ret;
 }
 
+static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)
+{
+	struct sev_data_snp_guest_request data = {0};
+	struct kvm *kvm = svm->vcpu.kvm;
+	kvm_pfn_t req_pfn, resp_pfn;
+	sev_ret_code fw_err = 0;
+	int ret;
+
+	if (!sev_snp_guest(kvm) || !PAGE_ALIGNED(req_gpa) || !PAGE_ALIGNED(resp_gpa))
+		return -EINVAL;
+
+	req_pfn = gfn_to_pfn(kvm, gpa_to_gfn(req_gpa));
+	if (is_error_noslot_pfn(req_pfn))
+		return -EINVAL;
+
+	resp_pfn = gfn_to_pfn(kvm, gpa_to_gfn(resp_gpa));
+	if (is_error_noslot_pfn(resp_pfn)) {
+		ret = EINVAL;
+		goto release_req;
+	}
+
+	if (rmp_make_private(resp_pfn, 0, PG_LEVEL_4K, 0, true)) {
+		ret = -EINVAL;
+		kvm_release_pfn_clean(resp_pfn);
+		goto release_req;
+	}
+
+	data.gctx_paddr = __psp_pa(to_kvm_sev_info(kvm)->snp_context);
+	data.req_paddr = __sme_set(req_pfn << PAGE_SHIFT);
+	data.res_paddr = __sme_set(resp_pfn << PAGE_SHIFT);
+
+	ret = sev_issue_cmd(kvm, SEV_CMD_SNP_GUEST_REQUEST, &data, &fw_err);
+	if (ret)
+		return ret;
+
+	/*
+	 * If reclaim fails then there's a good chance the guest will no longer
+	 * be runnable so just let userspace terminate the guest.
+	 */
+	if (snp_page_reclaim(kvm, resp_pfn)) {
+		return -EIO;
+		goto release_req;
+	}
+
+	/*
+	 * As per GHCB spec, firmware failures should be communicated back to
+	 * the guest via SW_EXITINFO2 rather than be treated as immediately
+	 * fatal.
+	 */
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+				SNP_GUEST_ERR(ret ? SNP_GUEST_VMM_ERR_GENERIC : 0,
+					      fw_err));
+
+	ret = 1; /* resume guest */
+	kvm_release_pfn_dirty(resp_pfn);
+
+release_req:
+	kvm_release_pfn_clean(req_pfn);
+	return ret;
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4213,6 +4279,9 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 
 		ret = 1;
 		break;
+	case SVM_VMGEXIT_GUEST_REQUEST:
+		ret = snp_handle_guest_req(svm, control->exit_info_1, control->exit_info_2);
+		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
 		vcpu_unimpl(vcpu,
 			    "vmgexit: unsupported event - exit_info_1=%#llx, exit_info_2=%#llx\n",
diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
index 154a87a1eca9..7bd78e258569 100644
--- a/include/uapi/linux/sev-guest.h
+++ b/include/uapi/linux/sev-guest.h
@@ -89,8 +89,17 @@ struct snp_ext_report_req {
 #define SNP_GUEST_FW_ERR_MASK		GENMASK_ULL(31, 0)
 #define SNP_GUEST_VMM_ERR_SHIFT		32
 #define SNP_GUEST_VMM_ERR(x)		(((u64)x) << SNP_GUEST_VMM_ERR_SHIFT)
+#define SNP_GUEST_FW_ERR(x)		((x) & SNP_GUEST_FW_ERR_MASK)
+#define SNP_GUEST_ERR(vmm_err, fw_err)	(SNP_GUEST_VMM_ERR(vmm_err) | \
+					 SNP_GUEST_FW_ERR(fw_err))
 
+/*
+ * The GHCB spec only formally defines INVALID_LEN/BUSY VMM errors, but define
+ * a GENERIC error code such that it won't ever conflict with GHCB-defined
+ * errors if any get added in the future.
+ */
 #define SNP_GUEST_VMM_ERR_INVALID_LEN	1
 #define SNP_GUEST_VMM_ERR_BUSY		2
+#define SNP_GUEST_VMM_ERR_GENERIC	BIT(31)
 
 #endif /* __UAPI_LINUX_SEV_GUEST_H_ */

---

## [3] Michael Roth — 2024-06-21
*Subject: [PATCH v1 2/5] x86/sev: Move sev_guest.h into common SEV header*

sev_guest.h currently contains various definitions relating to the
format of SNP_GUEST_REQUEST commands to SNP firmware. Currently only the
sev-guest driver makes use of them, but when the KVM side of this is
implemented there's a need to parse the SNP_GUEST_REQUEST header to
determine whether additional information needs to be provided to the
guest. Prepare for this by moving those definitions to a common header
that's shared by host/guest code so that KVM can also make use of them.

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

## [4] Michael Roth — 2024-06-21
*Subject: [PATCH v1 3/5] KVM: SEV: Provide support for SNP_EXTENDED_GUEST_REQUEST NAE event*

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

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c | 60 ++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 60 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 7338b987cadd..b5dcf36b50f5 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3323,6 +3323,7 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
 			goto vmgexit_err;
 		break;
 	case SVM_VMGEXIT_GUEST_REQUEST:
+	case SVM_VMGEXIT_EXT_GUEST_REQUEST:
 		if (!sev_snp_guest(vcpu->kvm))
 			goto vmgexit_err;
 		break;
@@ -4005,6 +4006,62 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 	return ret;
 }
 
+/*
+ * As per GHCB spec (see "SNP Extended Guest Request"), the certificate table
+ * is terminated by 24-bytes of zeroes.
+ */
+static const u8 empty_certs_table[24];
+
+static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)
+{
+	struct kvm *kvm = svm->vcpu.kvm;
+	u8 msg_type;
+
+	if (!sev_snp_guest(kvm) || !PAGE_ALIGNED(req_gpa) || !PAGE_ALIGNED(resp_gpa))
+		return -EINVAL;
+
+	if (kvm_read_guest(kvm, req_gpa + offsetof(struct snp_guest_msg_hdr, msg_type),
+			   &msg_type, 1))
+		goto abort_request;
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
+			goto abort_request;
+
+		data_gpa = vcpu->arch.regs[VCPU_REGS_RAX];
+		data_npages = vcpu->arch.regs[VCPU_REGS_RBX];
+
+		if (!PAGE_ALIGNED(data_gpa))
+			goto abort_request;
+
+		if (data_npages &&
+		    kvm_write_guest(kvm, data_gpa, empty_certs_table,
+				    sizeof(empty_certs_table)))
+			goto abort_request;
+	}
+
+	return snp_handle_guest_req(svm, req_gpa, resp_gpa);
+
+abort_request:
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+				SNP_GUEST_ERR(SNP_GUEST_VMM_ERR_GENERIC, 0));
+	return 1; /* resume guest */
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4282,6 +4339,9 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
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

## [5] Michael Roth — 2024-06-21
*Subject: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

Confidential VMs have a number of additional requirements on the host
side which might involve interactions with userspace. One such case is
with SEV-SNP guests, where the host can optionally provide a certificate
table to the guest when it issues an attestation request to firmware
(see GHCB 2.0 specification regarding "SNP Extended Guest Requests").
This certificate table can then be used to verify the endorsement key
used by firmware to sign the attestation report.

While it is possible for guests to obtain the certificates through other
means, handling it via the host provides more flexibility in being able
to keep the certificate data in sync with the endorsement key throughout
host-side operations that might resulting in the endorsement key
changing.

In the case of KVM, userspace will be responsible for fetching the
certificate table and keeping it in sync with any modifications to the
endorsement key. Define a new KVM_EXIT_* event where userspace is
provided with the GPA of the buffer the guest has provided as part of
the attestation request so that userspace can write the certificate data
into it.

Since there is potential for additional CoCo-related events in the
future, introduce this in the form of a more general KVM_EXIT_COCO exit
type that handles multiple sub-types, similarly to KVM_EXIT_HYPERCALL,
and then define a KVM_EXIT_COCO_REQ_CERTS sub-type to handle the actual
certificate-fetching mentioned above.

Also introduce a KVM_CAP_EXIT_COCO capability to enable/disable
individual sub-types, similarly to KVM_CAP_EXIT_HYPERCALL. Since actual
support for KVM_EXIT_COCO_REQ_CERTS will be enabled in a subsequent
patch, don't yet allow it to be enabled.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 Documentation/virt/kvm/api.rst  | 109 ++++++++++++++++++++++++++++++++
 arch/x86/include/asm/kvm_host.h |   1 +
 arch/x86/kvm/x86.c              |  13 ++++
 include/uapi/linux/kvm.h        |  20 ++++++
 4 files changed, 143 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index ecfa25b505e7..2eea9828d9aa 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7122,6 +7122,97 @@ Please note that the kernel is allowed to use the kvm_run structure as the
 primary storage for certain register types. Therefore, the kernel may use the
 values in kvm_run even if the corresponding bit in kvm_dirty_regs is not set.
 
+::
+
+		/* KVM_EXIT_COCO */
+		struct kvm_exit_coco {
+		#define KVM_EXIT_COCO_REQ_CERTS			0
+		#define KVM_EXIT_COCO_MAX			1
+			__u8 nr;
+			__u8 pad0[7];
+			union {
+				struct {
+					__u64 gfn;
+					__u32 npages;
+		#define KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN		1
+		#define KVM_EXIT_COCO_REQ_CERTS_ERR_GENERIC		(1 << 31)
+					__u32 ret;
+				} req_certs;
+			};
+		};
+
+KVM_EXIT_COCO events are intended to handle cases where a confidential
+VM requires some action on the part of userspace, or cases where userspace
+needs to be informed of some activity relating to a confidential VM.
+
+A `kvm_exit_coco` structure is defined to encapsulate the data to be sent to
+or returned by userspace. The `nr` field defines the specific type of event
+that needs to be serviced, and that type is used as a discriminator to
+determine which union type should be used for input/output.
+
+The parameters for each of these event/union types are documented below:
+
+  - ``KVM_EXIT_COCO_REQ_CERTS``
+
+    This event provides a way to request certificate data from userspace and
+    have it written into guest memory. This is intended primarily to handle
+    attestation requests made by SEV-SNP guests (using the Extended Guest
+    Requests GHCB command as defined by the GHCB 2.0 specification for SEV-SNP
+    guests), where additional certificate data corresponding to the
+    endorsement key used by firmware to sign an attestation report can be
+    optionally provided by userspace to pass along to the guest together with
+    the firmware-provided attestation report.
+
+    In the case of ``KVM_EXIT_COCO_REQ_CERTS`` events, the `req_certs` union
+    type is used. KVM will supply in `gfn` the non-private guest page that
+    userspace should use to write the contents of certificate data. In the
+    case of SEV-SNP, the format of this certificate data is defined in the
+    GHCB 2.0 specification (see section "SNP Extended Guest Request"). KVM
+    will also supply in `npages` the number of contiguous pages available
+    for writing the certificate data into.
+
+      - If the supplied number of pages is sufficient, userspace must write
+        the certificate table blob (in the format defined by the GHCB spec)
+        into the address corresponding to `gfn` and set `ret` to 0 to indicate
+        success. If no certificate data is available, then userspace can
+        either write an empty certificate table into the address corresponding
+        to `gfn`, or it can disable ``KVM_EXIT_COCO_REQ_CERTS`` (via
+        ``KVM_CAP_EXIT_COCO``), in which case KVM will handle returning an
+        empty certificate table to the guest.
+
+      - If the number of pages supplied is not sufficient, userspace must set
+        the required number of pages in `npages` and then set `ret` to
+        ``KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN``.
+
+      - If some other error occurred, userspace must set `ret` to
+        ``KVM_EXIT_COCO_REQ_CERTS_ERR_GENERIC``.
+
+    NOTE: In the case of SEV-SNP, the endorsement key used by firmware may
+    change as a result of management activities like updating SEV-SNP firmware
+    or loading new endorsement keys, so some care should be taken to keep the
+    returned certificate data in sync with the actual endorsement key in use by
+    firmware at the time the attestation request is sent to SNP firmware. The
+    recommended scheme to do this is:
+
+      - The VMM should obtain a shared or exclusive lock on the path the
+        certificate blob file resides at before reading it and returning it to
+        KVM, and continue to hold the lock until the attestation request is
+        actually sent to firmware. To facilitate this, the VMM can set the
+        ``immediate_exit`` flag of kvm_run just after supplying the certificate
+        data, and just before and resuming the vCPU. This will ensure the vCPU
+        will exit again to userspace with ``-EINTR`` after it finishes fetching
+        the attestation request from firmware, at which point the VMM can
+        safely drop the file lock.
+
+      - Tools/libraries that perform updates to SNP firmware TCB values or
+        endorsement keys (e.g. via /dev/sev interfaces such as ``SNP_COMMIT``,
+        ``SNP_SET_CONFIG``, or ``SNP_VLEK_LOAD``, see
+        Documentation/virt/coco/sev-guest.rst for more details) in such a way
+        that the certificate blob needs to be updated, should similarly take an
+        exclusive lock on the certificate blob for the duration of any updates
+        to endorsement keys or the certificate blob contents to ensure that
+        VMMs using the above scheme will not return certificate blob data that
+        is out of sync with the endorsement key used by firmware.
 
 6. Capabilities that can be enabled on vCPUs
 ============================================
@@ -8895,6 +8986,24 @@ Do not use KVM_X86_SW_PROTECTED_VM for "real" VMs, and especially not in
 production.  The behavior and effective ABI for software-protected VMs is
 unstable.
 
+8.42 KVM_CAP_EXIT_COCO
+----------------------
+
+:Capability: KVM_CAP_EXIT_COCO
+:Architectures: x86
+:Type: vm
+
+This capability, if enabled, will cause KVM to exit to userspace with
+KVM_EXIT_COCO exit reason to process certain events related to confidential
+guests.
+
+Calling KVM_CHECK_EXTENSION for this capability will return a bitmask of
+KVM_EXIT_COCO event types that can be configured to exit to userspace.
+
+The argument to KVM_ENABLE_CAP is also a bitmask, and must be a subset
+of the result of KVM_CHECK_EXTENSION.  KVM will forward to userspace
+the event types whose corresponding bit is in the argument.
+
 9. Known KVM API problems
 =========================
 
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index cef323c801f2..4b90208f9df0 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1429,6 +1429,7 @@ struct kvm_arch {
 	struct kvm_x86_msr_filter __rcu *msr_filter;
 
 	u32 hypercall_exit_enabled;
+	u64 coco_exit_enabled;
 
 	/* Guest can access the SGX PROVISIONKEY. */
 	bool sgx_provisioning_allowed;
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index a6968eadd418..94c3a82b02c7 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -125,6 +125,8 @@ static u64 __read_mostly cr4_reserved_bits = CR4_RESERVED_BITS;
 #define KVM_X2APIC_API_VALID_FLAGS (KVM_X2APIC_API_USE_32BIT_IDS | \
                                     KVM_X2APIC_API_DISABLE_BROADCAST_QUIRK)
 
+#define KVM_EXIT_COCO_VALID_MASK 0
+
 static void update_cr8_intercept(struct kvm_vcpu *vcpu);
 static void process_nmi(struct kvm_vcpu *vcpu);
 static void __kvm_set_rflags(struct kvm_vcpu *vcpu, unsigned long rflags);
@@ -4826,6 +4828,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_VM_TYPES:
 		r = kvm_caps.supported_vm_types;
 		break;
+	case KVM_CAP_EXIT_COCO:
+		r = KVM_EXIT_COCO_VALID_MASK;
+		break;
 	default:
 		break;
 	}
@@ -6748,6 +6753,14 @@ int kvm_vm_ioctl_enable_cap(struct kvm *kvm,
 		}
 		mutex_unlock(&kvm->lock);
 		break;
+	case KVM_CAP_EXIT_COCO:
+		if (cap->args[0] & ~KVM_EXIT_COCO_VALID_MASK) {
+			r = -EINVAL;
+			break;
+		}
+		kvm->arch.coco_exit_enabled = cap->args[0];
+		r = 0;
+		break;
 	default:
 		r = -EINVAL;
 		break;
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index e5af8c692dc0..8a3a76679224 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -135,6 +135,22 @@ struct kvm_xen_exit {
 	} u;
 };
 
+struct kvm_exit_coco {
+#define KVM_EXIT_COCO_REQ_CERTS		0
+#define KVM_EXIT_COCO_MAX		1
+	__u8 nr;
+	__u8 pad0[7];
+	union {
+		struct {
+			__u64 gfn;
+			__u32 npages;
+#define KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN		1
+#define KVM_EXIT_COCO_REQ_CERTS_ERR_GENERIC		(1 << 31)
+			__u32 ret;
+		} req_certs;
+	};
+};
+
 #define KVM_S390_GET_SKEYS_NONE   1
 #define KVM_S390_SKEYS_MAX        1048576
 
@@ -178,6 +194,7 @@ struct kvm_xen_exit {
 #define KVM_EXIT_NOTIFY           37
 #define KVM_EXIT_LOONGARCH_IOCSR  38
 #define KVM_EXIT_MEMORY_FAULT     39
+#define KVM_EXIT_COCO             40
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -433,6 +450,8 @@ struct kvm_run {
 			__u64 gpa;
 			__u64 size;
 		} memory_fault;
+		/* KVM_EXIT_COCO */
+		struct kvm_exit_coco coco;
 		/* Fix the size of the union. */
 		char padding[256];
 	};
@@ -918,6 +937,7 @@ struct kvm_enable_cap {
 #define KVM_CAP_GUEST_MEMFD 234
 #define KVM_CAP_VM_TYPES 235
 #define KVM_CAP_PRE_FAULT_MEMORY 236
+#define KVM_CAP_EXIT_COCO 237
 
 struct kvm_irq_routing_irqchip {
 	__u32 irqchip;

---

## [6] Michael Roth — 2024-06-21
*Subject: [PATCH v1 5/5] KVM: SEV: Add certificate support for SNP_EXTENDED_GUEST_REQUEST events*

Currently KVM implements a stub version of SNP Extended Guest Requests
that always supplies NULL certificate data alongside the attestation
report. Make use of the newly-defined KVM_EXIT_COCO_REQ_CERTS event to
provide a way for userspace to optionally supply this certificate data.

This implements the actual handling for KVM_EXIT_COCO_REQ_CERTS, so
allow it to be enabled via KVM_CAP_EXIT_COCO.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c | 41 +++++++++++++++++++++++++++++++++++------
 arch/x86/kvm/x86.c     |  2 +-
 2 files changed, 36 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index b5dcf36b50f5..8af56a4544d1 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4006,6 +4006,27 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 	return ret;
 }
 
+static int snp_complete_req_certs(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_svm *svm = to_svm(vcpu);
+	struct vmcb_control_area *control = &svm->vmcb->control;
+
+	if (vcpu->run->coco.req_certs.ret) {
+		if (vcpu->run->coco.req_certs.ret == KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN) {
+			vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->coco.req_certs.npages;
+			ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+						SNP_GUEST_ERR(SNP_GUEST_VMM_ERR_INVALID_LEN, 0));
+		} else {
+			ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+						SNP_GUEST_ERR(SNP_GUEST_VMM_ERR_GENERIC, 0));
+		}
+
+		return 1; /* resume guest */
+	}
+
+	return snp_handle_guest_req(svm, control->exit_info_1, control->exit_info_2);
+}
+
 /*
  * As per GHCB spec (see "SNP Extended Guest Request"), the certificate table
  * is terminated by 24-bytes of zeroes.
@@ -4027,12 +4048,10 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 	/*
 	 * As per GHCB spec, requests of type MSG_REPORT_REQ also allow for
 	 * additional certificate data to be provided alongside the attestation
-	 * report via the guest-provided data pages indicated by RAX/RBX. The
-	 * certificate data is optional and requires additional KVM enablement
-	 * to provide an interface for userspace to provide it, but KVM still
-	 * needs to be able to handle extended guest requests either way. So
-	 * provide a stub implementation that will always return an empty
-	 * certificate table in the guest-provided data pages.
+	 * report via the guest-provided data pages indicated by RAX/RBX. If
+	 * userspace enables KVM_EXIT_COCO_REQ_CERTS, then exit to userspace
+	 * to fetch the certificate data. Otherwise, return an empty certificate
+	 * table in the guest-provided data pages.
 	 */
 	if (msg_type == SNP_MSG_REPORT_REQ) {
 		struct kvm_vcpu *vcpu = &svm->vcpu;
@@ -4048,6 +4067,16 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 		if (!PAGE_ALIGNED(data_gpa))
 			goto abort_request;
 
+		if ((vcpu->kvm->arch.coco_exit_enabled & BIT_ULL(KVM_EXIT_COCO_REQ_CERTS))) {
+			vcpu->run->exit_reason = KVM_EXIT_COCO;
+			vcpu->run->coco.nr = KVM_EXIT_COCO_REQ_CERTS;
+			vcpu->run->coco.req_certs.gfn = gpa_to_gfn(data_gpa);
+			vcpu->run->coco.req_certs.npages = data_npages;
+			vcpu->run->coco.req_certs.ret = 0;
+			vcpu->arch.complete_userspace_io = snp_complete_req_certs;
+			return 0; /* fetch certs from userspace */
+		}
+
 		if (data_npages &&
 		    kvm_write_guest(kvm, data_gpa, empty_certs_table,
 				    sizeof(empty_certs_table)))
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 94c3a82b02c7..1a0087af1714 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -125,7 +125,7 @@ static u64 __read_mostly cr4_reserved_bits = CR4_RESERVED_BITS;
 #define KVM_X2APIC_API_VALID_FLAGS (KVM_X2APIC_API_USE_32BIT_IDS | \
                                     KVM_X2APIC_API_DISABLE_BROADCAST_QUIRK)
 
-#define KVM_EXIT_COCO_VALID_MASK 0
+#define KVM_EXIT_COCO_VALID_MASK BIT_ULL(KVM_EXIT_COCO_REQ_CERTS)
 
 static void update_cr8_intercept(struct kvm_vcpu *vcpu);
 static void process_nmi(struct kvm_vcpu *vcpu);

---

## [7] Liam Merwick — 2024-06-21
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On 21/06/2024 14:40, Michael Roth wrote:
> From: Brijesh Singh <brijesh.singh@amd.com>
> 


Should this be goto release_req; ?
Does resp_pfn need to be dealt with as well?

> +
> +	/*


Should this be setting ret = -EIO ? Next line is unreachable.
Does resp_pfn need to be dealt with as well?


> +		goto release_req;
> +	}

Regards,
Liam

---

## [8] Michael Roth — 2024-06-21
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Fri, Jun 21, 2024 at 03:52:35PM +0000, Liam Merwick wrote:
> On 21/06/2024 14:40, Michael Roth wrote:
> > From: Brijesh Singh <brijesh.singh@amd.com>

Argh... yes. I folded some helper functions into here and missed updating
some of the return sites. I'll respond to this patch with a revised version.
Sorry for the noise.

-Mike

---

## [9] Liam Merwick — 2024-06-21
*Subject: Re: [PATCH v1 2/5] x86/sev: Move sev_guest.h into common SEV header*

On 21/06/2024 14:40, Michael Roth wrote:
> sev_guest.h currently contains various definitions relating to the
> format of SNP_GUEST_REQUEST commands to SNP firmware. Currently only the

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>


> ---
>   arch/x86/include/asm/sev.h              | 48 +++++++++++++++++++

---

## [10] Liam Merwick — 2024-06-21
*Subject: Re: [PATCH v1 3/5] KVM: SEV: Provide support for
 SNP_EXTENDED_GUEST_REQUEST NAE event*

On 21/06/2024 14:40, Michael Roth wrote:
> Version 2 of GHCB specification added support for the SNP Extended Guest
> Request Message NAE event. This event serves a nearly identical purpose

typo: attestion

> report's signing key. Support for this extended handling will require
> additional KVM APIs to handle coordinating with userspace.

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>


> ---
>   arch/x86/kvm/svm/sev.c | 60 ++++++++++++++++++++++++++++++++++++++++++

---

## [11] Michael Roth — 2024-06-21
*Subject: [PATCH v1-revised 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST NAE event*

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

Signed-off-by: Brijesh Singh <brijesh.singh@amd.com>
Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Co-developed-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
[mdr: ensure FW command failures are indicated to guest, drop extended
 request handling to be re-written as separate patch, massage commit]
Signed-off-by: Michael Roth <michael.roth@amd.com>
Message-ID: <20240501085210.2213060-19-michael.roth@amd.com>
Signed-off-by: Paolo Bonzini <pbonzini@redhat.com>
---
 arch/x86/kvm/svm/sev.c         | 73 ++++++++++++++++++++++++++++++++++
 include/uapi/linux/sev-guest.h |  9 +++++
 2 files changed, 82 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index df8818759698..d9921ea87a81 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/misc_cgroup.h>
 #include <linux/processor.h>
 #include <linux/trace_events.h>
+#include <uapi/linux/sev-guest.h>
 
 #include <asm/pkru.h>
 #include <asm/trapnr.h>
@@ -3321,6 +3322,10 @@ static int sev_es_validate_vmgexit(struct vcpu_svm *svm)
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
@@ -3939,6 +3944,71 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
 	return ret;
 }
 
+static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)
+{
+	struct sev_data_snp_guest_request data = {0};
+	struct kvm *kvm = svm->vcpu.kvm;
+	kvm_pfn_t req_pfn, resp_pfn;
+	sev_ret_code fw_err = 0;
+	int ret;
+
+	if (!sev_snp_guest(kvm) || !PAGE_ALIGNED(req_gpa) || !PAGE_ALIGNED(resp_gpa))
+		return -EINVAL;
+
+	req_pfn = gfn_to_pfn(kvm, gpa_to_gfn(req_gpa));
+	if (is_error_noslot_pfn(req_pfn))
+		return -EINVAL;
+
+	resp_pfn = gfn_to_pfn(kvm, gpa_to_gfn(resp_gpa));
+	if (is_error_noslot_pfn(resp_pfn)) {
+		ret = EINVAL;
+		goto release_req;
+	}
+
+	if (rmp_make_private(resp_pfn, 0, PG_LEVEL_4K, 0, true)) {
+		ret = -EINVAL;
+		kvm_release_pfn_clean(resp_pfn);
+		goto release_req;
+	}
+
+	data.gctx_paddr = __psp_pa(to_kvm_sev_info(kvm)->snp_context);
+	data.req_paddr = __sme_set(req_pfn << PAGE_SHIFT);
+	data.res_paddr = __sme_set(resp_pfn << PAGE_SHIFT);
+
+	/* Firmware failures are propagated on to guest. */
+	ret = sev_issue_cmd(kvm, SEV_CMD_SNP_GUEST_REQUEST, &data, &fw_err);
+	if (ret)
+		pr_debug("%s: guest request failed, ret %d fw_err %d",
+			 __func__, ret, fw_err);
+
+	/*
+	 * If reclaim fails then there's a good chance the guest will no longer
+	 * be runnable so just let userspace terminate the guest. Don't try to
+	 * release the resp_pfn page reference in that case since it is no
+	 * longer usable for future allocations.
+	 */
+	if (snp_page_reclaim(kvm, resp_pfn)) {
+		ret = -EIO;
+		goto release_req;
+	}
+
+	/*
+	 * As per GHCB spec, firmware failures should be communicated back to
+	 * the guest via SW_EXITINFO2 rather than be treated as immediately
+	 * fatal.
+	 */
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+				SNP_GUEST_ERR(ret ? SNP_GUEST_VMM_ERR_GENERIC : 0,
+					      fw_err));
+
+	ret = 1; /* resume guest */
+	kvm_release_pfn_dirty(resp_pfn);
+
+release_req:
+	kvm_release_pfn_clean(req_pfn);
+	return ret;
+}
+
 static int sev_handle_vmgexit_msr_protocol(struct vcpu_svm *svm)
 {
 	struct vmcb_control_area *control = &svm->vmcb->control;
@@ -4213,6 +4283,9 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 
 		ret = 1;
 		break;
+	case SVM_VMGEXIT_GUEST_REQUEST:
+		ret = snp_handle_guest_req(svm, control->exit_info_1, control->exit_info_2);
+		break;
 	case SVM_VMGEXIT_UNSUPPORTED_EVENT:
 		vcpu_unimpl(vcpu,
 			    "vmgexit: unsupported event - exit_info_1=%#llx, exit_info_2=%#llx\n",
diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
index 154a87a1eca9..7bd78e258569 100644
--- a/include/uapi/linux/sev-guest.h
+++ b/include/uapi/linux/sev-guest.h
@@ -89,8 +89,17 @@ struct snp_ext_report_req {
 #define SNP_GUEST_FW_ERR_MASK		GENMASK_ULL(31, 0)
 #define SNP_GUEST_VMM_ERR_SHIFT		32
 #define SNP_GUEST_VMM_ERR(x)		(((u64)x) << SNP_GUEST_VMM_ERR_SHIFT)
+#define SNP_GUEST_FW_ERR(x)		((x) & SNP_GUEST_FW_ERR_MASK)
+#define SNP_GUEST_ERR(vmm_err, fw_err)	(SNP_GUEST_VMM_ERR(vmm_err) | \
+					 SNP_GUEST_FW_ERR(fw_err))
 
+/*
+ * The GHCB spec only formally defines INVALID_LEN/BUSY VMM errors, but define
+ * a GENERIC error code such that it won't ever conflict with GHCB-defined
+ * errors if any get added in the future.
+ */
 #define SNP_GUEST_VMM_ERR_INVALID_LEN	1
 #define SNP_GUEST_VMM_ERR_BUSY		2
+#define SNP_GUEST_VMM_ERR_GENERIC	BIT(31)
 
 #endif /* __UAPI_LINUX_SEV_GUEST_H_ */

---

## [12] Tom Lendacky — 2024-06-21
*Subject: Re: [PATCH v1 2/5] x86/sev: Move sev_guest.h into common SEV header*

On 6/21/24 08:40, Michael Roth wrote:
> sev_guest.h currently contains various definitions relating to the
> format of SNP_GUEST_REQUEST commands to SNP firmware. Currently only the

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

Nikunj does something similar in his Secure TSC patches. So depending on
which series goes in first...

Thanks,
Tom

> ---
>  arch/x86/include/asm/sev.h              | 48 +++++++++++++++++++

---

## [13] Tom Lendacky — 2024-06-21
*Subject: Re: [PATCH v1 3/5] KVM: SEV: Provide support for
 SNP_EXTENDED_GUEST_REQUEST NAE event*

On 6/21/24 08:40, Michael Roth wrote:
> Version 2 of GHCB specification added support for the SNP Extended Guest
> Request Message NAE event. This event serves a nearly identical purpose

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/kvm/svm/sev.c | 60 ++++++++++++++++++++++++++++++++++++++++++

---

## [14] Liam Merwick — 2024-06-22
*Subject: Re: [PATCH v1-revised 1/5] KVM: SEV: Provide support for
 SNP_GUEST_REQUEST NAE event*

On 21/06/2024 18:15, Michael Roth wrote:
> From: Brijesh Singh <brijesh.singh@amd.com>
> 

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>

> ---
>   arch/x86/kvm/svm/sev.c         | 73 ++++++++++++++++++++++++++++++++++

---

## [15] Carlos Bilbao — 2024-06-22
*Subject: Re: [PATCH v1 3/5] KVM: SEV: Provide support for
 SNP_EXTENDED_GUEST_REQUEST NAE event*

Hello folks,

On 6/21/24 08:40, Michael Roth wrote:
> Version 2 of GHCB specification added support for the SNP Extended Guest
> Request Message NAE event. This event serves a nearly identical purpose


Should this be:
staticconstu8 empty_certs_table[24] = { 0};
Besides that,
Reviewed-by: Carlos Bilbao <carlos.bilbao.osdev@gmail.com>


> +
> +static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)


Thanks,
Carlos

---

## [16] Tom Lendacky — 2024-06-24
*Subject: Re: [PATCH v1 3/5] KVM: SEV: Provide support for
 SNP_EXTENDED_GUEST_REQUEST NAE event*

On 6/22/24 15:28, Carlos Bilbao wrote:
> Hello folks,

Hey Carlos,

> 
> On 6/21/24 08:40, Michael Roth wrote:

Statics are always initialized to zero, so not necessary.

Thanks,
Tom

> Besides that,
> Reviewed-by: Carlos Bilbao <carlos.bilbao.osdev@gmail.com>

---

## [17] Sean Christopherson — 2024-06-24
*Subject: Re: [PATCH v1 3/5] KVM: SEV: Provide support for SNP_EXTENDED_GUEST_REQUEST
 NAE event*

On Mon, Jun 24, 2024, Tom Lendacky wrote:
> On 6/22/24 15:28, Carlos Bilbao wrote:
> >> +/*

Heh, the whole thing is unnecessary.

	/*
  	 * As per GHCB spec (see "SNP Extended Guest Request"), the certificate
	 * table is terminated by 24 bytes of zeroes.
	 */
	if (data_npages && kvm_clear_guest(kvm, data_gpa, 24))
		goto abort_request;

---

## [18] Sean Christopherson — 2024-06-26
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Fri, Jun 21, 2024, Michael Roth wrote:
> @@ -3939,6 +3944,67 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)
>  	return ret;

This is going to sound odd, but I think we should use gfn_to_page(), i.e. require
that the page be a refcounted page so that it can be pinned.  Long story short,
one of my learnings from the whole non-refcounted pages saga is that doing DMA
to unpinned pages outside of mmu_lock is wildly unsafe, and for all intents and
purposes the ASP is a device doing DMA.  I'm also pretty sure KVM should actually
*pin* pages, as in FOLL_PIN, but I'm ok tackling that later.

For now, using gfn_to_pages() would avoid creating ABI (DMA to VM_PFNMAP and/or
VM_MIXEDMAP memory) that KVM probably doesn't want to support in the long term.

[*] https://lore.kernel.org/all/20240229025759.1187910-1-stevensd@google.com

> +	if (is_error_noslot_pfn(req_pfn))
> +		return -EINVAL;

I don't see how this is safe.  KVM holds no locks, i.e. can't guarantee that the
resp_pfn stays private for the duration of the operation.  And on the opposite
side, KVM can't guarantee that resp_pfn isn't being actively used by something
in the kernel, e.g. KVM might induce an unexpected #PF(RMP).

Why can't KVM require that the response/destination page already be private?  I'm
also somewhat confused by the reclaim below.  If KVM converts the response page
back to shared, doesn't that clobber the data?  If so, how does the guest actually
get the response?  I feel like I'm missing something.

Regardless of whether or not I'm missing something, this needs comments, and the
changelog needs to be rewritten with --verbose to explain what's going on.  

> +	data.gctx_paddr = __psp_pa(to_kvm_sev_info(kvm)->snp_context);
> +	data.req_paddr = __sme_set(req_pfn << PAGE_SHIFT);

This leaks both req_pfn and resp_pfn.

> +
> +	/*

---

## [19] Sean Christopherson — 2024-06-26
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Fri, Jun 21, 2024, Michael Roth wrote:
> diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
> index ecfa25b505e7..2eea9828d9aa 100644

Unless I'm mistaken, these error codes are defined by the GHCB, which means the
values matter, i.e. aren't arbitrary KVM-defined values.

I forget exactly what we discussed in PUCK, but for the error codes, I think KVM
should either define it's own values that are completely disconnected from any
"harware" spec, or KVM should very explicitly #define all hardware values and have
the semantics of "ret" be vendor specific.  A hybrid approach doesn't really work,
e.g. KVM_EXIT_COCO_REQ_CERTS_ERR_GENERIC isn't used anywhere and and looks quite odd.

My vote is for vendor specific error codes, because unlike having a common user
exit reason+struct, I don't think arch-neutral error codes will minimize KVM's ABI,
I think it'll do the exact opposite.  The only thing we need to require is that
'0' == success.

E.g. I think we can end up with something like:

  static int snp_complete_req_certs(struct kvm_vcpu *vcpu)
  {
	struct vcpu_svm *svm = to_svm(vcpu);
	struct vmcb_control_area *control = &svm->vmcb->control;

	if (vcpu->run->coco.req_certs.ret)
		if (vcpu->run->coco.req_certs.ret == SNP_GUEST_VMM_ERR_INVALID_LEN)
			vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->coco.req_certs.npages;

		ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
					SNP_GUEST_ERR(vcpu->run->coco.req_certs.ret, 0));
		return 1;
	}

	return snp_handle_guest_req(svm, control->exit_info_1, control->exit_info_2);
  }

> +					__u32 ret;
> +				} req_certs;

---

## [20] Sean Christopherson — 2024-06-26
*Subject: Re: [PATCH v1-revised 1/5] KVM: SEV: Provide support for
 SNP_GUEST_REQUEST NAE event*

On Fri, Jun 21, 2024, Michael Roth wrote:
> diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
> index 154a87a1eca9..7bd78e258569 100644

Related to my suggestion to not have KVM-defined error codes, if we go that route,
then I believe SNP_GUEST_VMM_ERR_GENERIC is unnecessary.

For snp_handle_guest_req(), if sev_issue_cmd() fails, KVM can/should do something
like:

	/* Forward non-firmware errors to userspace, e.g. if the PSP is dead. */
	if (ret && !fw_err)
		goto release_req;

	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(0, fw_err));

And then in snp_complete_req_certs(), we could either let userspace shove in any
error code whatsoever, or restrict userspace to known, GHCB-defined error codes,
e.g.
	int err;

	err  = READ_ONCE(vcpu->run->coco.req_certs.ret);
	if (err)
		if (err != SNP_GUEST_VMM_ERR_INVALID_LEN &&
		    err != SNP_GUEST_VMM_ERR_BUSY)
			return -EINVAL;

		if (err == SNP_GUEST_VMM_ERR_INVALID_LEN)
			vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->coco.req_certs.npages;

		ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(err, 0));
		return 1;
	}


>  
>  #endif /* __UAPI_LINUX_SEV_GUEST_H_ */

---

## [21] Michael Roth — 2024-06-26
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Wed, Jun 26, 2024 at 06:58:09AM -0700, Sean Christopherson wrote:
> On Fri, Jun 21, 2024, Michael Roth wrote:
> > @@ -3939,6 +3944,67 @@ static int sev_snp_ap_creation(struct vcpu_svm *svm)

That seems reasonable. Will switch this to gfn_to_page().

> 
> [*] https://lore.kernel.org/all/20240229025759.1187910-1-stevensd@google.com

When the page is set to private with asid=0,immutable=true arguments,
this puts the page in a special 'firmware-owned' state that specifically
to avoid any changes to the page state happening from under the ASPs feet.
The only way to switch the page to any other state at this point is to
issue the SEV_CMD_SNP_PAGE_RECLAIM request to the ASP via
snp_page_reclaim().

I could see the guest shooting itself in the foot by issuing 2 guest
requests with the same req_pfn/resp_pfn, but on the KVM side whichever
request issues rmp_make_private() first would succeed, and then the
2nd request would generate an EINVAL to userspace.

In that sense, rmp_make_private()/snp_page_reclaim() sort of pair to
lock/unlock a page that's being handed to the ASP. But this should be
better documented either way.

> resp_pfn stays private for the duration of the operation.  And on the opposite
> side, KVM can't guarantee that resp_pfn isn't being actively used by something

Hmm. This is a bit tricky. The GHCB spec states:

  The Guest Request NAE event requires two unique pages, one page for the
  request and one page for the response. Both pages must be assigned to the
  hypervisor (shared). The guest must supply the guest physical address of
  the pages (i.e., page aligned) as input.

  The hypervisor must translate the guest physical address (GPA) of each
  page into a system physical address (SPA). The SPA is used to verify that
  the request and response pages are assigned to the hypervisor.

At least for req_pfn, this makes sense because the header of the message
is actually plain text, and KVM does need to parse it to read the message
type from the header. It's just the req/resp payload that are encrypted
by the guest/firmware, i.e. it's not relying on hardware-based memory
encryption in this case.

Because of that though, I think we could potential address this by
allocating the req/resp page as separate pages outside of guest memory,
and simply copy the contents to/from the GPAs provided by the guest.
I'll look more into this approach.

If we go that route I think some of the concerns above go away as well,
but we might still need to a lock or something to serialize access to
these separate/intermediate pages to avoid needed to allocate them every
time or per-request.

> also somewhat confused by the reclaim below.  If KVM converts the response page
> back to shared, doesn't that clobber the data?  If so, how does the guest actually

In this case we're just setting it immutable/firmware-owned, which just
happens to be equivalent (in terms of the RMP table) to a guest-owned page,
but with rmp_entry.ASID=0/rmp_entry.immutable=true instead of
rmp_entry.ASID=<guest asid>/rmp_entry.immutable=false. So the contents remain
intact/readable after the reclaim.

> 
> Regardless of whether or not I'm missing something, this needs comments, and the

Sure, will add more comments and details in the commit msg for v2.

> 
> > +	data.gctx_paddr = __psp_pa(to_kvm_sev_info(kvm)->snp_context);

Yes, this one should be fixed up by the v1-revised version of the patch.

Thanks!

-Mike

> 
> > +

---

## [22] Sean Christopherson — 2024-06-26
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Wed, Jun 26, 2024, Michael Roth wrote:
> On Wed, Jun 26, 2024 at 06:58:09AM -0700, Sean Christopherson wrote:
> > [*] https://lore.kernel.org/all/20240229025759.1187910-1-stevensd@google.com

What about the host kernel though?  I don't see anything here that ensures resp_pfn
isn't "regular" memory, i.e. that ensure the page isn't being concurrently accessed
by the host kernel (or some other userspace process).

Or is the "private" memory still accessible by the host?

> > resp_pfn stays private for the duration of the operation.  And on the opposite
> > side, KVM can't guarantee that resp_pfn isn't being actively used by something

Ah, I see the @asid=0 now.  The @asid=0,@immutable=true should be a separate API,
because IIUC, this always holds true:

	!asid == immutable

E.g.

static int rmp_assign_pfn(u64 pfn, u64 gpa, enum pg_level level, u32 asid, bool immutable)
{
	struct rmp_state state;

	memset(&state, 0, sizeof(state));
	state.assigned = 1;
	state.asid = asid;
	state.immutable = immutable;
	state.gpa = gpa;
	state.pagesize = PG_LEVEL_TO_RMP(level);

	return rmpupdate(pfn, &state);	
}

/* Transition a page to guest-owned/private state in the RMP table. */
int rmp_make_private(u64 pfn, u64 gpa, enum pg_level level, u32 asid)
{
	if (WARN_ON_ONCE(!asid))
		return -EIO;

	return rmp_assign_pfn(pfn, gpa, level, asid, false);
}
EXPORT_SYMBOL_GPL(rmp_make_private);

/* Transition a page to AMD-SP owned state in the RMP table. */
int rmp_make_firmware(u64 pfn, u64 gpa)
{
	return rmp_assign_pfn(pfn, gpa, PG_LEVEL_4K, 0, true);
}
EXPORT_SYMBOL_GPL(rmp_make_firmware);

---

## [23] Michael Roth — 2024-06-26
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Wed, Jun 26, 2024 at 07:22:43AM -0700, Sean Christopherson wrote:
> On Fri, Jun 21, 2024, Michael Roth wrote:
> > diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst

They do happen to coincide with the GHCB-defined values:

  /*
   * The GHCB spec only formally defines INVALID_LEN/BUSY VMM errors, but define
   * a GENERIC error code such that it won't ever conflict with GHCB-defined
   * errors if any get added in the future.
   */
  #define SNP_GUEST_VMM_ERR_INVALID_LEN   1
  #define SNP_GUEST_VMM_ERR_BUSY          2
  #define SNP_GUEST_VMM_ERR_GENERIC       BIT(31)

and not totally by accident. But the KVM_EXIT_COCO_REQ_CERTS_ERR_* are
defined/documented without any reliance on the GHCB spec and are purely
KVM-defined. I just didn't really see any reason to pick different
numerical values since it seems like purposely obfuscating things for
no real reason. But the code itself doesn't rely on them being the same
as the spec defines, so we are free to define these however we'd like as
far as the KVM API goes.

> 
> I forget exactly what we discussed in PUCK, but for the error codes, I think KVM

I'd gotten the impression that option 1) is what we were sort of leaning
toward, and that's the approach taken here.

> the semantics of "ret" be vendor specific.  A hybrid approach doesn't really work,
> e.g. KVM_EXIT_COCO_REQ_CERTS_ERR_GENERIC isn't used anywhere and and looks quite odd.

This is a catch-all error for userspace to set if any issues are
encountered that don't map to any other
KVM_EXIT_COCO_REQ_CERTS_ERR_* cases (like INVALID_LEN). It's defined
purely for KVM/userspace and not based on any other spec.

> 
> My vote is for vendor specific error codes, because unlike having a common user

I think this makes sense if we think of using KVM_EXIT_COCO mainly an
interface for GHCB/GHCI interactions, but now that we're leveraging
KVM_HC_MAP_GPA_RANGE for page-state change requests, and TDX is planning
to do the same, it doesn't really seem like likely that exposing those
definitions to userspace at that level will reduce ABI.

For instance this is purely just a KVM interface to request a certificate
blob from userspace, which is a side-note as far as all the GHCB-defined
definitions KVM needs to deal with regarding handling GHCB
extended/non-extended guest requests. And KVM itself might have it's own
requirements on top for what it needs from userspace, and those
requirements might be separate from these vendor specs.

And if we expose things selectively to keep the ABI small, it's a bit
awkward too. For instance, KVM_EXIT_COCO_REQ_CERTS_ERR_* basically needs
a way to indicate success/fail/ENOMEM. Which we have with
(assuming 0==success):

  #define KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN         1
  #define KVM_EXIT_COCO_REQ_CERTS_ERR_GENERIC             (1 << 31)

But the GHCB also defines other values like:

  #define SNP_GUEST_VMM_ERR_BUSY          2  

which don't make much sense to handle on the userspace side and doesn't
really have anything to do with the KVM_EXIT_COCO_REQ_CERTS KVM event,
which is a separate/self-contained thing from the general guest request
protocol. So would we expose that as ABI or not? If not then we end up
with this weird splitting of code. And if yes, then we have to sort of
give userspace a way to discover whenever new error codes are added to
the GHCB spec, because KVM needs to understand these value too and
users might be running on older kernel where only the currently-defined
error codes are present understood.

E.g. if we started off implementing KVM_EXIT_COCO_REQ_CERTS without a
way to request a larger buffer from the guest, and it wasn't later
on that SNP_GUEST_VMM_ERR_INVALID_LEN was added, we'd probably need a
capability bit or something to see if KVM supports requesting larger
page sizes from the guest. Otherwise userspace might just set it because
the spec says it's valid, but it won't work as expected because KVM
hasn't implemented that.

I guess technically we could reason about this particular one based on
which GHCB protocol version was set via KVM_SEV_INIT2, but what if
KVM itself was adding that functionality separately from the spec, and
now we got this intermingling of specs.

> 
> E.g. I think we can end up with something like:

I'm not opposed to this approach, but just deciding which of:

  #define SNP_GUEST_VMM_ERR_INVALID_LEN   1
  #define SNP_GUEST_VMM_ERR_BUSY          2
  #define SNP_GUEST_VMM_ERR_GENERIC       BIT(31)

should be exposed to userspace based on how we've defined the
KVM_EXIT_COCO_REQ_CERTS already seems like an unecessary dilemma
versus just defining exactly what's needed and documenting that
in the KVM API.

If we anticipate needing to expose big chunks of GHCB/GHCI to
userspace for other reasons or future extensions of KVM_EXIT_COCO_*
then I definitely see the rationale to avoid duplication. But with
KVM_HC_MAP_GPA_RANGE case covered, I don't see any major reason to
think this will ever end up being the case.

It seems more likely this will just be KVM's handy place to handle "Hey
userspace, I need you to handle some CoCo-related stuff for me" and
it's really KVM that's driving those requirements vs. any particular
spec.

For instance, the certificate-fetching in the first place is only
handled by userspace because that's how KVM communinity decided to
handle it, not some general spec-driven requirement to handle these
sorts of things in userspace. Similarly for the KVM_HC_MAP_GPA_RANGE
that we originally considered this interface to handle: the fact that
userspace handles those requests is mainly a KVM/gmem design decision.

And like the KVM_HC_MAP_GPA_RANGE case, maybe we find there are cases
where a common KVM-defined event type can handle the requirements of
multiple specs with a common interface API, without exposing any
particular vendor definitions.

So based on that I sort of think giving KVM more flexibility on how it
wants to implement/document specific KVM_EXIT_COCO event types will
ultimately result in cleaner and more manageable ABI.

-Mike

> 			vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->coco.req_certs.npages;
>

---

## [24] Michael Roth — 2024-06-26
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Wed, Jun 26, 2024 at 10:13:44AM -0700, Sean Christopherson wrote:
> On Wed, Jun 26, 2024, Michael Roth wrote:
> > On Wed, Jun 26, 2024 at 06:58:09AM -0700, Sean Christopherson wrote:

It's accessible, but it is immutable according to RMP table, so so it would
require KVM to be elsewhere doing a write to the page, but that seems possible
if the guest is misbehaved. So I do think the RMP #PF concerns are warranted,
and that looking at using KVM-allocated intermediary/"bounce" pages to pass to
firmware is definitely worth looking into for v2 as that's just about the
safest way to guarantee nothing else will be writing to the page after
it gets set to immutable/firmware-owned.

> 
> > > resp_pfn stays private for the duration of the operation.  And on the opposite

That makes sense. I'll look at introducing rmp_make_firmware() as part of
the next revision.

-Mike

> 
> 	!asid == immutable

---

## [25] Sean Christopherson — 2024-06-26
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Wed, Jun 26, 2024, Michael Roth wrote:
> On Wed, Jun 26, 2024 at 10:13:44AM -0700, Sean Christopherson wrote:
> > On Wed, Jun 26, 2024, Michael Roth wrote:

I take it "immutable" means "read-only"?  If so, it would be super helpful to
document that in the APM.  I assumed "immutable" only meant that the RMP entry
itself is immutable, and that Assigned=AMD-SP is what prevented host accesses.

> but that seems possible if the guest is misbehaved. So I do think the RMP #PF
> concerns are warranted, and that looking at using KVM-allocated

---

## [26] Tom Lendacky — 2024-06-27
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On 6/26/24 14:54, Sean Christopherson wrote:
> On Wed, Jun 26, 2024, Michael Roth wrote:
>> On Wed, Jun 26, 2024 at 10:13:44AM -0700, Sean Christopherson wrote:

Not quite. It depends on the page state associated with the page. For
example, Hypervisor-Fixed pages have the immutable bit set, but can be
read and written.

The page states are documented in the SNP API (Chapter 5, Page
Management):

https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/56860.pdf

Thanks,
Tom

> 
>> but that seems possible if the guest is misbehaved. So I do think the RMP #PF

---

## [27] Sean Christopherson — 2024-06-27
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Thu, Jun 27, 2024, Tom Lendacky wrote:
> On 6/26/24 14:54, Sean Christopherson wrote:
> > On Wed, Jun 26, 2024, Michael Roth wrote:

Heh, but then that section says:

  Pages in the Firmware state are owned by the firmware. Because the RMP.Immutable
                                                         ^^^^^^^^^^^^^^^^^^^^^^^^^
  bit is set, the hypervisor cannot write to Firmware pages nor alter the RMP entry
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  with the RMPUPDATE instruction.

which to me very clearly suggests that the RMP.Immutable bit is what makes the
page read-only.

Can you ask^Wbribe someone to add a "Table 11. Page State Properties" or something?
E.g. to explicitly list out the read vs. write protections and the state of the
page's data (encrypted, integrity-protected, zeroed?, etc).  I've read through
all of "5.2 Page States" and genuinely have no clue as to what protections most
of the states have.

Ah, never mind, I found "Table 15-39. RMP Memory Access Checks" in the APM.  FWIW,
that somewhat contradicts this blurb from the SNP ABI spec:

  The content of a Context page is encrypted and integrity protected so that the
  hypervisor cannot read or write to it.

I also find that statement confusing.  IIUC, the fact that the Context page is
encrypted and integrity protected doesn't actually have anything to do with the
host's ability to access the data.  The host _can_ read the data, but it will get
ciphertext.  But the host can't write the data because the page isn't HV-owned.

Actually, isn't the intregrity protected part wrong?  I thought one of the benefits
of SNP vs. ES is that the RMP means the VMSA doesn't have to be integrity protected,
and so VMRUN and #VMEXIT transitions are faster because the CPU doesn't need to do
as much work.

---

## [28] Peter Gonda — 2024-06-27
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Thu, Jun 27, 2024 at 9:35 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Thu, Jun 27, 2024, Tom Lendacky wrote:

The statement is fairly vague so its a bit confusing that the
encryption scheme on the Context page doesn't include integrity. In
reality the encryption is AES-XTS with a physical address tweak so no
integrity. The integrity comes purely from the RMP with SNP, but it's
still integrity protected right? So I don't think that part is wrong.

---

## [29] Tom Lendacky — 2024-06-27
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On 6/27/24 10:35, Sean Christopherson wrote:
> On Thu, Jun 27, 2024, Tom Lendacky wrote:
>> On 6/26/24 14:54, Sean Christopherson wrote:

I'll get with the document owner and provide that feedback and see what we
can do to remove some of the ambiguity and improve upon it.

> 
> Ah, never mind, I found "Table 15-39. RMP Memory Access Checks" in the APM.  FWIW,

The RMP protection is what helps provide the integrity protection. So if a
hypervisor tries to write to a non-hypervisor owned page, it will generate
an RMP #PF. If the page can't be RMPUPDATEd (the immutable bit is set for
the page in the RMP), then the page can't be written to by the hypervisor.

If the page can be RMPUPDATEd and made hypervisor-owned and was previously
PVALIDATEd, then a guest access (as private) will generate a #NPF. If the
hypervisor then assigns the page to the guest (after having possibly
written to the page), the guest will then get a #VC and detect that the
integrity of the page may have been compromised and it should take action.

> of SNP vs. ES is that the RMP means the VMSA doesn't have to be integrity protected,
> and so VMRUN and #VMEXIT transitions are faster because the CPU doesn't need to do

That is one of the benefits. A page can only be turned into a VMSA page
via an SNP_LAUNCH_UPDATE (becoming part of the guest measurement) or via
RMPADJUST (which can only be executed in the guest), making it a guest
private page. If an RMPUPDATE is done by the hypervisor, the VMSA bit will
be cleared and the VMSA won't be runnable anymore.

Thanks,
Tom

---

## [30] Sean Christopherson — 2024-06-27
*Subject: Re: [PATCH v1 1/5] KVM: SEV: Provide support for SNP_GUEST_REQUEST
 NAE event*

On Thu, Jun 27, 2024, Tom Lendacky wrote:
> On 6/27/24 10:35, Sean Christopherson wrote:
> >> The page states are documented in the SNP API (Chapter 5, Page

Thanks!

> > Ah, never mind, I found "Table 15-39. RMP Memory Access Checks" in the APM.  FWIW,
> > that somewhat contradicts this blurb from the SNP ABI spec:

My confusion (ok, maybe it's more annoyance than true confusion) is that that
applies to _all_ non-hypervisor pages, not just Context pages.  Reading things
from a "the exception proves the rule" viewpoint, stating that Context pages are
encrypted and integrity protected strongly suggests that all other pages are NOT
encrypted and NOT integrity protected.

---

## [31] Sean Christopherson — 2024-06-28
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Wed, Jun 26, 2024, Michael Roth wrote:
> On Wed, Jun 26, 2024 at 07:22:43AM -0700, Sean Christopherson wrote:
> > On Fri, Jun 21, 2024, Michael Roth wrote:

For SNP.  For other vendors, the numbers look bizarre, e.g. why bit 31?  And the
fact that it appears to be a mask is even more odd.

> no real reason. But the code itself doesn't rely on them being the same
> as the spec defines, so we are free to define these however we'd like as

> > I forget exactly what we discussed in PUCK, but for the error codes, I think KVM
> > should either define it's own values that are completely disconnected from any

> And if we expose things selectively to keep the ABI small, it's a bit
> awkward too. For instance, KVM_EXIT_COCO_REQ_CERTS_ERR_* basically needs

Why not?  If userspace is waiting on a cert update for whatever reason, why can't
it signal "busy" to the guest?

> really have anything to do with the KVM_EXIT_COCO_REQ_CERTS KVM event,
> which is a separate/self-contained thing from the general guest request

Not necessarily.  So long as KVM doesn't need to manipulate guest state, e.g. to
set RBX (or whatever reg it is) for ERR_INVALID_LEN, then KVM doesn't need to
care/know about the error codes.  E.g. userspace could signal VMM_BUSY and KVM
would happily pass that to the guest.

> users might be running on older kernel where only the currently-defined
> error codes are present understood.

We'd need that regardless, no?  Even if some other architecture added a error
code for invalid length, KVM would need to reject that for SNP because KVM couldn't
translate ERR_INVALID_LEN into an SNP error code.  And when a KVM comes along
that does support that error code, KVM would need a way to advertise support.

But if KVM simply forwards error codes, then KVM only needs to advertise support
if KVM reacts to the error code.

As mentioned in the previous version, ideally userspace would need to set guest
regs for INVALID_LEN case, but I don't see a sane/reasonable way to do that.

> page sizes from the guest. Otherwise userspace might just set it because
> the spec says it's valid, but it won't work as expected because KVM

How would KVM do that?  

> > E.g. I think we can end up with something like:
> > 

But that's not what your code does.  It exposes gunk that isn't necessary
(ERR_GENERIC), and then doesn't enforce anything on the backend because
snp_complete_req_certs() interprets any non-zero "return" value as a "generic"
error.  If we actually want to maintain extensibility, then KVM needs to enforce
inputs.

And if we do that, then it doesn't really matter whether KVM defines arbitrary
error codes or reuses the GHCB codes, e.g. it'll either be:

        if (vcpu->run->coco.req_certs.ret)
                if (vcpu->run->coco.req_certs.ret != KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN)
			return -EINVAL;

                vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->coco.req_certs.npages;
                ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
                                        SNP_GUEST_ERR(vcpu->run->coco.req_certs.ret, 0));
                return 1;
        }

versus:

        if (vcpu->run->coco.req_certs.ret)
                if (vcpu->run->coco.req_certs.ret != SNP_GUEST_VMM_ERR_INVALID_LEN)
			return -EINVAL;

                vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->coco.req_certs.npages;
                ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
                                        SNP_GUEST_ERR(vcpu->run->coco.req_certs.ret, 0));
                return 1;
        }

(with variations depending on whether or not KVM allows SNP_GUEST_VMM_ERR_BUSY).
 
> If we anticipate needing to expose big chunks of GHCB/GHCI to
> userspace for other reasons or future extensions of KVM_EXIT_COCO_*

I don't disagree, I'm just not seeing how regurgitating the GHCB error codes
provides flexibility.  As above, unless KVM is super restrictive about which
error codes can be returned, KVM has zero flexibility.

Reusing exit reasons and whatnot, e.g. for KVM_HC_MAP_GPA_RANGE, is all about
reducing copy+paste and not having to deal with 14^W15 different standards.  Any
ABI flexibility gained is a nice bonus.  If we think there's actually a chance
that a different vendor can use KVM_EXIT_COCO_REQ_CERTS and userspace won't end
end up with wildly different implementations, then yeah, let's define generic
return codes.

But if we're just going to end up with a bunch of vendor error codes redefined
by KVM, I don't see the point.

Another way to approach this would be to use existing the errno values, i.e.
EINVAL and EBUSY in this case.  The upside is we don't have to define custom
return codes.  The downside is that KVM needs to translate (though if we actually
expect vendors to reuse KVM_EXIT_COCO_REQ_CERTS, odds are good at least one vendor
will need to translate, i.e. won't be able to use KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN
verbatim like SNP).

---

## [32] Michael Roth — 2024-06-28
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Fri, Jun 28, 2024 at 01:08:19PM -0700, Sean Christopherson wrote:
> On Wed, Jun 26, 2024, Michael Roth wrote:
> > On Wed, Jun 26, 2024 at 07:22:43AM -0700, Sean Christopherson wrote:

That's fair. Values 1 and 2 made sense so just re-use, but that results
in a awkward value for _GENERIC that's not really necessary for the KVM
side.

> 
> > no real reason. But the code itself doesn't rely on them being the same

My thinking was that userspace is free to take it's time and doesn't need
to report delays back to KVM. But it would reduce the potential for
soft-lockups in the guest, so it might make sense to work that into the
API.

But more to original point, there could be something added in the future
that really has nothing to do with anything involving KVM<->userspace
interaction and so would make no sense to expose to userspace.
Unfortunately I picked a bad example. :)

> 
> > really have anything to do with the KVM_EXIT_COCO_REQ_CERTS KVM event,

But given we already have an exception to that where KVM does need to
intervene for certain errors codes like ERR_INVALID_LEN that require
modifying guest state, it doesn't seem like a good starting position
to have to hope that it doesn't happen again.

It just doesn't seem necessary to put ourselves in a situation where
we'd need to be concerned by that at all. If the KVM API is a separate
and fairly self-contained thing then these decisions are set in stone
until we want to change it and not dictated/modified by changes to
anything external without our explicit consideration.

I know the certs things is GHCB-specific atm, but when the certs used
to live inside the kernel the KVM_EXIT_* wasn't needed at all, so
that's why I see this as more of a KVM interface thing rather than
a GHCB one. And maybe eventually some other CoCo implementation also
needs some interface for fetching certificates/blobs from userspace
and is able to re-use it still because it's not too SNP-specific
and the behavior isn't dictated by the GHCB spec (e.g.
ERR_INVALID_LEN might result in some other state needing to be
modified in their case rather than what the GHCB dictates.)

> 
> > users might be running on older kernel where only the currently-defined

But in that case it would be immediately obvious that if they
extended KVM_EXIT_COCO_REQ_CERTS (or whatever) they'd need to be aware
that other architectures are already using it and make the appropriate
accomodations to make those extensions discoverable.

> 
> But if KVM simply forwards error codes, then KVM only needs to advertise support

Forwards them where though? There's not really any reason that userspace
needs to be cognizant of that fact that error codes are being passed to
the guest. It needs to tell KVM either:

  a) success: here's the cert blob
  b) error: i need more space
  c) error: i'm busy (potentially)
  d) error: something bad on my end, handle it as you will

Being able to mediate all the architecture-specific details on the
backend without complicating the front-end we expose to userspace gives
more flexibility with how we handle compatibility stuff between
architectures. And we'd still only need to advertise what the interface
explicitly requires userspace to be aware of.

> 
> As mentioned in the previous version, ideally userspace would need to set guest

We had KVM_EXIT_VMGEXIT previously, where userspace had direct access to
the GHCB. I think TDX had similar. But that went away when we unified
under KVM_HC_MAP_GPA_RANGE.

No question that, in that case, it made sense to lean heavily on
GHCB-defined values/handling. But I thought KVM_EXIT_COCO was an attempt
to capitalize on the KVM_HC_MAP_GPA_RANGE success story and further move
toward providing more potential for common APIs for other CoCo stuff.

> 
> > page sizes from the guest. Otherwise userspace might just set it because

Hmm, good question. I don't think I was talking specifically about
KVM adding *_INVALID_LEN support outside of the GHCB spec at that point,
but I'm not sure I had a good example in mind. I certainly don't atm =\

> 
> > > E.g. I think we can end up with something like:

Agreed that I should be explicitly enforcing that only the defined error
codes should be getting returned by userspace. I think that's more of a bug
on my part rather than a consequence of design choices though.

> snp_complete_req_certs() interprets any non-zero "return" value as a "generic"
> error.  If we actually want to maintain extensibility, then KVM needs to enforce

For instance, the GHCB spec mentions:

    A SW_EXITINFO2 value of 0 indicates a successful completion of the SNP Guest Request.

and goes on to document *_INVALID_LEN and *_ERR_BUSY as other possible
values.

...but it doesn't really define anything for "unable to fetch certs", and
that's certainly a situation userspace might hit if it got
deleted/renamed/etc. It's trivial for KVM to just make up some specific
or generic error to handle this case with the current approach.

If we took that stance that userspace should just return what the GHCB
says, then the GHCB protocol does document a more generic set of error
hypervisor-specific error codes that can be set in SW_EXITINFO2 when
SW_EXITINFO1 is set to '2':

  Table 7: Invalid GHCB Reason Codes
  Value  Description
  0x0001 The GHCB address was not registered (SEV-SNP)
  0x0002 The GHCB Usage value was not valid
  0x0003 The SW_SCRATCH field was not valid / could not be mapped
  0x0004 The required input fields(s) for the NAE event were not marked valid
         in the GHCB VALID_BITMAP field
  0x0005 The NAE event input was not valid (e.g., an invalid SW_EXITINFO1 value
         for the AP Jump Table NAE event)
  0x0006 The NAE event was not valid
  0x0007-0xffff Reserved
  0x10000+ Available for hypervisor specific reason codes.

But in order for userspace to set them, we need to expose the notion of
SW_EXITINFO1 and SW_EXITINFO2 so it can set the appropriate values 
directly. But even then it's weird because lower 32-bits of SW_EXITINFO2
correspond to the fw_err passed back by SNP firmware, only KVM can set
that.

So you can't just point to the GHCB spec, you need to point to the GHCB
spec, expose bits and pieces of GHCB-defined values as ABI, and then layer
KVM-specific stuff on top like 'KVM will set the fw_err value so these
bits are actually off-limits for you', or potentially only give them the
upper 32-bits to work with and inform them to ignore the lower 32-bits
mentioned in the GHCB spec.

That sort of illustrates my concerns with this approach. It's
unpredictable what parts of the GHCB spec are/aren't applicable for
these particular interactions between KVM<->userspace, or how much
relying on that sort of approach will complicate
interfaces/documentation that might otherwise be much simpler KVM gives
itself the leeway to define them in the manner that is most convenient
to KVM.

> 
>         if (vcpu->run->coco.req_certs.ret)

>  
> > If we anticipate needing to expose big chunks of GHCB/GHCI to

I tried to give a better example above of why I think leaning too heavily
on the GHCB or other specs would potentially make for less-flexible
interfaces.

> 
> Reusing exit reasons and whatnot, e.g. for KVM_HC_MAP_GPA_RANGE, is all about

That's sort of my hope here. I know the certificate blob format itself
is SNP-specific, and most likely someone would need to massage it or
extend it for other applications, but at least it's not 100% guaranteed to
be useless for other archs. And if you want to take steps further toward
that goal, then maybe we can consider not even passing in the GPAs to
userspace and just have a KVM_EXIT_COCO_FETCH_BLOB interface along with
a scratch buffer somewhere to handle it or something.
> 
> But if we're just going to end up with a bunch of vendor error codes redefined

I also have no qualms about leaning on the GHCB spec where appropriate, or
even wholesale if the need arose. But I just don't think fetching the
certificate blob would benefit much from going down that route, and the
penalty for re-definitions in this case seems smaller than the additional
uAPI complexity we'd have exposing the sw_exitinfo1/sw_exitnfo2 fields needed
to fully allow userspace to code against the GHCB spec rather than a
self-contained KVM-defined abstraction layer.

> 
> Another way to approach this would be to use existing the errno values, i.e.

I think I would greatly prefer that as a middle ground between the 2
approaches. We wouldn't have to redefine anything, and we'd still have the
flexibility to document the meaning/handling of these errors code in the
KVM API documentation.

> expect vendors to reuse KVM_EXIT_COCO_REQ_CERTS, odds are good at least one vendor
> will need to translate, i.e. won't be able to use KVM_EXIT_COCO_REQ_CERTS_ERR_INVALID_LEN

If SNP translates right off the bat then I think that's a good sets a good
example for others who might be fishing for an interface they can re-use.

-Mike

---

## [33] Binbin Wu — 2024-07-26
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On 6/29/2024 8:36 AM, Michael Roth wrote:
> On Fri, Jun 28, 2024 at 01:08:19PM -0700, Sean Christopherson wrote:
>> On Wed, Jun 26, 2024, Michael Roth wrote:

TDX GHCI does have a similar PV interface for TDX guest to get quota, i.e.,
TDG.VP.VMCALL<GetQuote>.  This GetQuote PV interface is designed to invoke
a request to generate a TD-Quote signing by a service hosting TD-Quoting
Enclave operating in the host environment for a TD Report passed as a
parameter by the TD.
And the request will be forwarded to userspace for handling.

So like GHCB, TDX needs to pass a shared buffer to userspace, which is
specified by GPA and size (4K aligned) and get the error code from
userspace and forward the error code to guest.

But there are some differences from GHCB interface.
1. TDG.VP.VMCALL<GetQuote> is a a doorbell-like interface used to queue a
    request. I.e., it is an asynchronous request.  The error code represents
    the status of request queuing, *not* the status of TD Quote generation..
2. Besides the error code returned by userspace for GetQuote interface, the
    GHCI spec defines a "Status Code" field in the header of the shared 
buffer.
    The "Status Code" field is also updated by VMM during the real 
handling of
    getting quote (after TDG.VP.VMCALL<GetQuote> returned to guest).
    After the TDG.VP.VMCALL<GetQuote> returned and back to TD guest, the TD
    guest can poll the "Status Code" field to check if the processing is
    in-flight, succeeded or failed.
    Since the real handling of getting quota is happening in userspace, and
    it will interact directly with guest, for TDX, it has to expose TDX
    specific error code to userspace to update the result of quote 
generation.

Currently, TDX is about to add a new TDX specific KVM exit reason, i.e.,
KVM_EXIT_TDX_GET_QUOTE and its related data structure based on a previous
discussion. https://lore.kernel.org/kvm/Zg18ul8Q4PGQMWam@google.com/
For the error code returned by userspace, KVM simply forward the error code
to guest without further translation or handling.

I am neutral to have a common KVM exit reason to handle both GHCB for
REQ_CERTS and GHCI for GET_QUOTE.  But for the error code, can we uses 
vendor
specific error codes if KVM cares about the error code returned by userspace
in vendor specific complete_userspace_io callback?

BTW, here is the plan of 4 hypercalls needing to exit to userspace for
TDX basic support series:
TDG.VP.VMCALL<SetupEventNotifyInterrupt>
- Add a new KVM exit reason KVM_EXIT_TDX_SETUP_EVENT_NOTIFY
TDG.VP.VMCALL<GetQuote>
- Add a new KVM exit reason KVM_EXIT_TDX_GET_QUOTE
TDG.VP.VMCALL<MapGPA>
- Reuse KVM_EXIT_HYPERCALL with KVM_HC_MAP_GPA_RANGE
TDG.VP.VMCALL<ReportFatalError>
- Reuse KVM_EXIT_SYSTEM_EVENT but add a new type
   KVM_SYSTEM_EVENT_TDX_FATAL_ERROR

---

## [34] Dionna Amalie Glaze — 2024-09-13
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Fri, Jul 26, 2024 at 12:15 AM Binbin Wu <binbin.wu@linux.intel.com> wrote:
>
>

VMM_ERR_BUSY means something very specific to the GHCB protocol, which
is that a request that would normally have increased a message
sequence number was not able to be sent, and the exact same message
would need to be sent again, otherwise the cryptographic protocol
breaks down.
In the event of firmware hotloading, SNP_COMMIT, and needing to get
the right version of VCEK certificate to the VM guest, we could detect
a conflict and need to say VMM_ERR_BUSY2 (or something) that says try
again, but the sequence number did go up, we just couldn't coordinate
a non-atomic data transfer afterward to be correct.

There's a different way to solve the data race without a retry, but
I'm not 100% confident that we can really generalize the error space
across TEEs.

To support the coordination of SNP_DOWNLOAD_FIRMWARE_EX, SNP_COMMIT,
and extended guest requests, user space needs to be told which
TCB_VERSION certificate it needs to provide. It can be wrong if it
relies on its own call to SNP_PLATFORM_STATUS.
Given that userspace can't interpret the report (encrypted by VMPCK),
it won't know exactly which VCEK certificate to provide given that
SNP_COMMIT can happen before or after an attestation report is taken
and before KVM exits to userspace for the certificates.

We can extend the ccp driver to, on extended guest request, lock the
command buffer, get the REPORTED_TCB, complete the request, unlock the
command buffer, and return both the response and the REPORTED_TCB at
the time of the request. That will give userspace enough info to give
the right certificate. That would mean a more specific
KVM_EXIT_COCO_REQ_EXIT message than just where to put the certs. A
SEV-SNP TCB_VERSION is also platform-specific, so not particularly
generalizable to "COCO".

We could also say that extended_guest_request is inherently racy and
have AMD extend the GHCB spec with a new request type that doesn't
communicate with the ASP at all and instead just requests certificates
for a given REPORTED_TCB. The guest VM can read an attestation
report's reported_tcb field and craft this request. I don't know if we
want to have an arbitrary message passing interface between guest VM
and user space VMM without very specific restrictions. We ought to
just have paravirtualized I/O devices then.

> >>> and not totally by accident. But the KVM_EXIT_COCO_REQ_CERTS_ERR_* are
> >>> defined/documented without any reliance on the GHCB spec and are purely


--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [35] Sean Christopherson — 2024-10-28
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Fri, Sep 13, 2024, Dionna Amalie Glaze wrote:
> We can extend the ccp driver to, on extended guest request, lock the
> command buffer, get the REPORTED_TCB, complete the request, unlock the

Holding a lock across an exit to userspace seems wildly unsafe.

Can you explain the race that you are trying to close, with the exact "bad" sequence
of events laid out in chronological order, and an explanation of why the race can't
be sovled in userspace?  I read through your previous comment[*] (which I assume
is the race you want to close?), but I couldn't quite piece together exactly what's
broken.

[*] https://lore.kernel.org/all/CAAH4kHb03Una2kcvyC3W=1ZfANBWF_7a7zsSmWhr_r9g3rCDZw@mail.gmail.com

---

## [36] Dionna Amalie Glaze — 2024-11-01
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Mon, Oct 28, 2024 at 11:20 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Fri, Sep 13, 2024, Dionna Amalie Glaze wrote:

I wasn't suggesting this. I was suggesting adding a special ccp symbol
that would perform two sev commands under the same lock to ensure we
know the REPORTED_TCB that was used to derive the VCEK that signs an
attestation report in the MSG_REPORT_REQ guest request. We use that
atomicity to be sure that when we exit to user space to request
certificates that we're getting the right version certificates.

>
> Can you explain the race that you are trying to close, with the exact "bad" sequence

1. the control plane delivers a firmware update. Current TCB version
goes up. The machine signals that it needs new certificates before it
can commit.
2. VM performs an extended guest request.
3. KVM exits to user space to get certificates before getting the
report from firmware.
4. [what I understand Michael Roth was suggesting] User space grabs a
file lock to see if it can read the cached certificates. It reads the
certificates and releases the lock before returning to KVM.
5. the control plane delivers the certificates to the machine and
tells it to commit. The machine grabs the certificate file lock, runs
SNP_COMMIT, and releases the file lock. This command updates both
COMMITTED_TCB and REPORTED_TCB.
6. KVM asks firmware to complete the MSG_REPORT_REQ request, but it's
a different REPORTED_TCB.
7. Guest receives the wrong certificates for certifying the report it
just received.

The fact that 4 has to release the lock before getting the attestation
report is the problem.
If we instead get the report and know what the REPORTED_TCB was when
serving that request, then we can exit to user space requesting the
certificates for the report in hand.
A concurrent update can update the reported_tcb like in the above
scenario, but it won't interfere with certificates since the machine
should have certificates for both TCB_VERSIONs to provide until the
commit is complete.

I don't think it's workable to have 1 grab the file lock and for 5 to
release it. Waiting for a service to update stale certificates should
not block user attestation requests. It would make 4's failure to get
the lock return VMM_BUSY and eventually cause attestations to time out
in sev-guest.

>
> [*] https://lore.kernel.org/all/CAAH4kHb03Una2kcvyC3W=1ZfANBWF_7a7zsSmWhr_r9g3rCDZw@mail.gmail.com

---

## [37] Michael Roth — 2024-11-01
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Fri, Nov 01, 2024 at 01:53:26PM -0700, Dionna Amalie Glaze wrote:
> On Mon, Oct 28, 2024 at 11:20 AM Sean Christopherson <seanjc@google.com> wrote:
> >

Hi Dionna,

> 
> 1. the control plane delivers a firmware update. Current TCB version

We wouldn't actually release the lock before getting the attestation
report. There's more specifics on the suggested flow in the documentation
update accompanying this patch:

+    NOTE: In the case of SEV-SNP, the endorsement key used by firmware may
+    change as a result of management activities like updating SEV-SNP firmware
+    or loading new endorsement keys, so some care should be taken to keep the
+    returned certificate data in sync with the actual endorsement key in use by
+    firmware at the time the attestation request is sent to SNP firmware. The
+    recommended scheme to do this is:
+
+      - The VMM should obtain a shared or exclusive lock on the path the
+        certificate blob file resides at before reading it and returning it to
+        KVM, and continue to hold the lock until the attestation request is
+        actually sent to firmware. To facilitate this, the VMM can set the
+        ``immediate_exit`` flag of kvm_run just after supplying the certificate
+        data, and just before and resuming the vCPU. This will ensure the vCPU
+        will exit again to userspace with ``-EINTR`` after it finishes fetching
+        the attestation request from firmware, at which point the VMM can
+        safely drop the file lock.
+
+      - Tools/libraries that perform updates to SNP firmware TCB values or
+        endorsement keys (e.g. via /dev/sev interfaces such as ``SNP_COMMIT``,
+        ``SNP_SET_CONFIG``, or ``SNP_VLEK_LOAD``, see
+        Documentation/virt/coco/sev-guest.rst for more details) in such a way
+        that the certificate blob needs to be updated, should similarly take an
+        exclusive lock on the certificate blob for the duration of any updates
+        to endorsement keys or the certificate blob contents to ensure that
+        VMMs using the above scheme will not return certificate blob data that
+        is out of sync with the endorsement key used by firmware.

So #5 would not be able to obtain an exclusive file lock until userspace
receives confirmation that the attestation request was processed by
firmware. At that point it will be an accurate reflection of the
attestation state associated with that particular version of the
certificates that was fetched from userspace. So at that point the,
transaction is done at that point and userspace can safely release the lock.

-Mike

> If we instead get the report and know what the REPORTED_TCB was when
> serving that request, then we can exit to user space requesting the

---

## [38] Dionna Amalie Glaze — 2024-11-01
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Fri, Nov 1, 2024 at 3:04 PM Michael Roth <michael.roth@amd.com> wrote:
>
> On Fri, Nov 01, 2024 at 01:53:26PM -0700, Dionna Amalie Glaze wrote:

Thanks for the clarification. I'll need to understand this pathway
better in our VMM to test this patch series effectively.
Will get back to you.

> -Mike
>

---

## [39] Michael Roth — 2024-11-19
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On Fri, Jul 26, 2024 at 03:15:01PM +0800, Binbin Wu wrote:
> 
> 

A few weeks back we discussed during the PUCK call on whether it makes
sense for use a common exit type for REQ_CERTS and TDX_GET_QUOTE, and
due to the asynchronous/polling nature of TDX_GET_QUOTE, and the
somewhat-particular file-locking requirements that need to be built into
the REQ_CERTS handling, we'd decided that it's probably more trouble
than it's worth to try to merge the 2.

However, I'm still hoping that KVM_EXIT_COCO might still provide some
useful infrastructure for introducing something like
KVM_EXIT_COCO_GET_QUOTE that implements the TDX-specific requirements
more directly.

I've just submitted v2 of KVM_EXIT_COCO where the userspace-provided
error codes are reworked to be less dependent on specific spec-defined
values but instead relies on standard error codes that KVM can provide
special handling for internally when needed:

  https://lore.kernel.org/kvm/20241119133513.3612633-1-michael.roth@amd.com/

But I suppose in your case userspace would just return "SUCCESS"/0 and
then all the vendor-specific values are mainly in relation to the
"Status Code" field so it likely doesn't make a huge difference as far
as what userspace passes back to KVM.

Thanks,

Mike

> 
> BTW, here is the plan of 4 hypercalls needing to exit to userspace for

---

## [40] Binbin Wu — 2024-11-20
*Subject: Re: [PATCH v1 4/5] KVM: Introduce KVM_EXIT_COCO exit type*

On 11/19/2024 9:53 PM, Michael Roth wrote:
[...]
> A few weeks back we discussed during the PUCK call on whether it makes
> sense for use a common exit type for REQ_CERTS and TDX_GET_QUOTE, and
I am not sure it benefits much.
Since the handling codes of REQ_CERTS and  TDX_GET_QUOTE in userspace are
quite different, i.e., there will be little common code to reuse, but it
requires KVM to convert the error code from the KVM_EXIT_COCO version to
vendor specific versions.


>
> I've just submitted v2 of KVM_EXIT_COCO where the userspace-provided
According to GHCI spec, besides "TDG.VP.VMCALL_SUCCESS", there are two more
error codes "TDG.VP.VMCALL_RETRY" and "TDG.VP.VMCALL_INVALID_OPERAND".
"TDG.VP.VMCALL_RETRY" could cover EAGAIN.
"TDG.VP.VMCALL_INVALID_OPERAND" could be used to cover the other errors
returned, i.e., EIO and ENOSPC according to your proposal in v2.

> then all the vendor-specific values are mainly in relation to the
> "Status Code" field so it likely doesn't make a huge difference as far
[...]

---
