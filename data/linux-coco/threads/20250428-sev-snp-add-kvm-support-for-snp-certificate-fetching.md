---
title: 'SEV-SNP: Add KVM support for SNP certificate fetching'
date: 2025-04-28
last_reply: 2025-04-29
message_count: 4
participants: ['Michael Roth', 'Liam Merwick']
---

## [1] Michael Roth — 2025-04-28

This patchset is also available at:

  https://github.com/amdese/linux/commits/snp-certs-v6

and is based on top of kvm/next (45eb29140e68)


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

To support fetching certificate data from userspace, a new KVM
KVM_EXIT_SNP_REQ_CERTS exit type is used to fetch the data similarly to
KVM_EXIT_MMIO/etc, with an associate KVM capability to detect/enable the
exits depending on whether userspace has been configured to provide
certificate data.

[1] https://lore.kernel.org/kvm/ZS614OSoritrE1d2@google.com/


Testing
-------

For testing this via QEMU, use the following tree:

  https://github.com/amdese/qemu/commits/snp-certs-rfc3-wip0

A basic command-line invocation for SNP with certificate data supplied
would be:

 qemu-system-x86_64 -smp 32,maxcpus=255 -cpu EPYC-Milan-v2
  -machine q35,confidential-guest-support=sev0,memory-backend=ram1
  -object memory-backend-memfd,id=ram1,size=4G,share=true,reserve=false
  -object sev-snp-guest,id=sev0,cbitpos=51,reduced-phys-bits=1,id-auth=,certs-filename=/home/mroth/cert.blob
  -bios OVMF.fd

Something like the following simple example can be used to simulate an
exclusive lock being held on the certificate by management tools performing an
update:

  #include <stdlib.h>
  #include <stdio.h>
  #define __USE_GNU
  #include <fcntl.h>
  #include <unistd.h>
  #include <errno.h>
  #include <stdbool.h>
  #include <sys/types.h>
  #include <sys/stat.h>
  
  int main(int argc, void **argv)
  {
      int ret, fd, i = 0;
      char *path = argv[1];
  
      struct flock fl = {
          .l_whence = SEEK_SET,
          .l_start = 0,
          .l_len = 0,
          .l_type = F_WRLCK
      };
  
      fd = open(path, O_RDWR);
      ret = fcntl(fd, F_OFD_SETLK, &fl);
      if (ret) {
          printf("error locking file, ret %d errno %d\n", ret, errno);
          return ret;
      }
  
      while (true) {
          i++;
          printf("now holding lock (%d seconds elapsed)...\n", i);
          usleep(1000 * 1000);
      }
  
      return 0;
  }

The format of the certificate blob is defined in the GHCB 2.0 specification,
but if it's not being parsed on the guest-side then random data will suffice
for testing the KVM bits.

Any feedback/review is appreciated.

Thanks!

-Mike

Changes since v5:

 * Drop KVM capability in favor of a KVM device attribute to advertise
   support to userspace, and introduce a new KVM_SEV_SNP_ENABLE_REQ_CERTS
   command to switch it on (Sean)
 * Only allow certificate-fetching to be enabled prior to starting any
   vCPUs to avoid races/unexpected behavior (Sean)
 * Drop unecessary cast in SNP_GUEST_VMM_ERR_GENERIC definition (Sean)
 * Add checks to enforce that userspace only uses EIO to indicate generic
   errors when fetching certificates to ensure that other error codes remain
   usable for other/future error conditions (Joerg, Sean)
 * Clean up setting of GHCB error codes via a small helper routine (Sean)
 * Use READ_ONCE() when checking userspace's return value in struct kvm_run
   (Sean)
 * Use u64 instead of u32 for npages/ret fields in the kvm_run struct (Sean)
 * Use a switch statement to handle individual error codes reported by
   userspace (Sean)
 * Move 'snp_certs_enabled' flag from struct kvm_arch to kvm_sev_info (Sean)
 * Documentation fix-ups (Sean)
 * Rebase to latest kvm/next

Changes since v4:

 * Minor documentation updates to make the implementation notes less
   specific to QEMU.
 * Collected Reviewed-by/Tested-by from v3 since there have been no
   functional changes since then and only minor documentation updates.
 * Rebased/re-tested on top of latest kvm/next (d3d0b8dfe060)

Changes since v3:

 * This version updates the documentation scheme about how file locking is
   expected to happen.

Changes since v2:

 * As per discussion during PUCK, drop all the KVM_EXIT_COCO infrastructure
   since there are enough differences with TDX's quote generation to make
   unifying the 2 exits over-complicated for userspace, and the code-sharing
   we stand to gain from placing everything under the KVM_EXIT_COCO_*
   umbrella are of questionable benefit.
 * Update/simplify documentation as per the above.
 * Rebase/re-test on top of latest kvm-coco-queue

Changes since v1:

 * Drop subtype-specific error codes. Instead use standard error codes like
   ENOSPC/etc. and let KVM determine whether a particular error requires
   special handling for a particular KVM_EXIT_COCO subtype. (Sean)
 * Introduce special handling for EAGAIN for KVM_EXIT_COCO_REQ_CERTS such
   that the guest can be instructed to retry if userspace is temporarily unable
   to immediately lock/provide the certificate data. (Sean)
 * Move the 'ret' field of struct kvm_exit_coco to the top-level so all
   sub-types can propagate error codes the same way.
 * Add more clarifying details in KVM documentation about the suggested
   file-locking scheme to avoid races between certificate requests and updates
   to SNP firmware that might modify the endorsement key corresponding to the
   certificate data.

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
Michael Roth (2):
      KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching
      KVM: SEV: Add KVM_SEV_SNP_ENABLE_REQ_CERTS command

 Documentation/virt/kvm/api.rst                     | 80 ++++++++++++++++++++++
 .../virt/kvm/x86/amd-memory-encryption.rst         | 17 ++++-
 arch/x86/include/uapi/asm/kvm.h                    |  2 +
 arch/x86/kvm/svm/sev.c                             | 67 ++++++++++++++++--
 arch/x86/kvm/svm/svm.h                             |  1 +
 include/uapi/linux/kvm.h                           |  9 +++
 include/uapi/linux/sev-guest.h                     |  8 +++
 7 files changed, 176 insertions(+), 8 deletions(-)

---

## [2] Michael Roth — 2025-04-28
*Subject: [PATCH v6 1/2] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching*

For SEV-SNP, the host can optionally provide a certificate table to the
guest when it issues an attestation request to firmware (see GHCB 2.0
specification regarding "SNP Extended Guest Requests"). This certificate
table can then be used to verify the endorsement key used by firmware to
sign the attestation report.

While it is possible for guests to obtain the certificates through other
means, handling it via the host provides more flexibility in being able
to keep the certificate data in sync with the endorsement key throughout
host-side operations that might resulting in the endorsement key
changing.

In the case of KVM, userspace will be responsible for fetching the
certificate table and keeping it in sync with any modifications to the
endorsement key by other userspace management tools. Define a new
KVM_EXIT_SNP_REQ_CERTS event where userspace is provided with the GPA of
the buffer the guest has provided as part of the attestation request so
that userspace can write the certificate data into it while relying on
filesystem-based locking to keep the certificates up-to-date relative to
the endorsement keys installed/utilized by firmware at the time the
certificates are fetched.

  [Melody: Update the documentation scheme about how file locking is
  expected to happen.]

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>
Tested-by: Liam Merwick <liam.merwick@oracle.com>
Tested-by: Dionna Glaze <dionnaglaze@google.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
Signed-off-by: Melody Wang <huibo.wang@amd.com>
---
 Documentation/virt/kvm/api.rst | 80 ++++++++++++++++++++++++++++++++++
 arch/x86/kvm/svm/sev.c         | 50 ++++++++++++++++++---
 arch/x86/kvm/svm/svm.h         |  1 +
 include/uapi/linux/kvm.h       |  9 ++++
 include/uapi/linux/sev-guest.h |  8 ++++
 5 files changed, 142 insertions(+), 6 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index ad1859f4699e..a838289618b5 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7194,6 +7194,86 @@ Please note that the kernel is allowed to use the kvm_run structure as the
 primary storage for certain register types. Therefore, the kernel may use the
 values in kvm_run even if the corresponding bit in kvm_dirty_regs is not set.
 
+::
+
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct kvm_exit_snp_req_certs {
+			__u64 gfn;
+			__u64 npages;
+			__u64 ret;
+		};
+
+This event provides a way to request certificate data from userspace and
+have it written into guest memory. This is intended to handle attestation
+requests made by SEV-SNP guests (using the Extended Guest Requests GHCB
+command as defined by the GHCB 2.0 specification for SEV-SNP guests),
+where additional certificate data corresponding to the endorsement key
+used by firmware to sign an attestation report can be optionally provided
+by userspace to pass along to the guest together with the
+firmware-provided attestation report.
+
+KVM will supply in `gfn` the non-private guest page that userspace should
+use to write the contents of certificate data. The format of this
+certificate data is defined in the GHCB 2.0 specification (see section
+"SNP Extended Guest Request"). KVM will also supply in `npages` the
+number of contiguous pages available for writing the certificate data
+into.
+
+  - If the supplied number of pages is sufficient, userspace must write
+    the certificate table blob (in the format defined by the GHCB spec)
+    into the address corresponding to `gfn` and set `ret` to 0 to indicate
+    success. If no certificate data is available, then userspace can
+    write an empty certificate table into the address corresponding to
+    `gfn`.
+
+  - If the number of pages supplied is not sufficient, userspace must set
+    the required number of pages in `npages` and then set `ret` to
+    ``ENOSPC``.
+
+  - If the certificate cannot be immediately provided, userspace should set
+    `ret` to ``EAGAIN``, which will inform the guest to retry the request
+    later. One scenario where this would be useful is if the certificate
+    is in the process of being updated and cannot be fetched until the
+    update completes (see the NOTE below regarding how file-locking can
+    be used to orchestrate such updates between management/guests).
+
+  - To indicate to the guest that a general error occurred while fetching
+    the certificate, userspace should set `ret` to ``EIO``.
+
+  - All other possible values for `ret` are reserved for future use.
+
+NOTE: The endorsement key used by firmware may change as a result of
+management activities like updating SEV-SNP firmware or loading new
+endorsement keys, so some care should be taken to keep the returned
+certificate data in sync with the actual endorsement key in use by
+firmware at the time the attestation request is sent to SNP firmware. The
+recommended scheme to do this is to use file locking (e.g. via fcntl()'s
+F_OFD_SETLK) in the following manner:
+
+  - The VMM should obtain a shared/read or exclusive/write lock on the
+  certificate blob file before reading it and returning it to KVM, and
+  continue to hold the lock until the attestation request is actually
+  sent to firmware. To facilitate this, the VMM can set the
+  ``immediate_exit`` flag of kvm_run just after supplying the
+  certificate data, and just before and resuming the vCPU. This will
+  ensure the vCPU will exit again to userspace with ``-EINTR`` after
+  it finishes fetching the attestation request from firmware, at which
+  point the VMM can safely drop the file lock.
+
+  - Tools/libraries that perform updates to SNP firmware TCB values or
+    endorsement keys (e.g. via /dev/sev interfaces such as ``SNP_COMMIT``,
+    ``SNP_SET_CONFIG``, or ``SNP_VLEK_LOAD``, see
+    Documentation/virt/coco/sev-guest.rst for more details) in such a way
+    that the certificate blob needs to be updated, should similarly take an
+    exclusive lock on the certificate blob for the duration of any updates
+    to endorsement keys or the certificate blob contents to ensure that
+    VMMs using the above scheme will not return certificate blob data that
+    is out of sync with the endorsement key used by firmware.
+
+This scheme is recommended so that tools can use a fairly generic/natural
+approach to synchronizing firmware/certificate updates via file-locking,
+which should make it easier to maintain interoperability across
+tools/VMMs/vendors.
 
 .. _cap_enable:
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 0bc708ee2788..b74e2be2cbaf 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4042,6 +4042,36 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 	return ret;
 }
 
+static int snp_req_certs_err(struct vcpu_svm *svm, u32 vmm_error)
+{
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(vmm_error, 0));
+
+	return 1; /* resume guest */
+}
+
+static int snp_complete_req_certs(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_svm *svm = to_svm(vcpu);
+	struct vmcb_control_area *control = &svm->vmcb->control;
+
+	switch (READ_ONCE(vcpu->run->snp_req_certs.ret)) {
+	case 0:
+		return snp_handle_guest_req(svm, control->exit_info_1,
+					    control->exit_info_2);
+	case ENOSPC:
+		vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->snp_req_certs.npages;
+		return snp_req_certs_err(svm, SNP_GUEST_VMM_ERR_INVALID_LEN);
+	case EAGAIN:
+		return snp_req_certs_err(svm, SNP_GUEST_VMM_ERR_BUSY);
+	case EIO:
+		return snp_req_certs_err(svm, SNP_GUEST_VMM_ERR_GENERIC);
+	default:
+		break;
+	}
+
+	return -EINVAL;
+}
+
 static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)
 {
 	struct kvm *kvm = svm->vcpu.kvm;
@@ -4057,14 +4087,13 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
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
+	 * userspace enables KVM_EXIT_SNP_REQ_CERTS, then exit to userspace
+	 * to fetch the certificate data. Otherwise, return an empty certificate
+	 * table in the guest-provided data pages.
 	 */
 	if (msg_type == SNP_MSG_REPORT_REQ) {
+		struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
 		struct kvm_vcpu *vcpu = &svm->vcpu;
 		u64 data_npages;
 		gpa_t data_gpa;
@@ -4078,6 +4107,15 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 		if (!PAGE_ALIGNED(data_gpa))
 			goto request_invalid;
 
+		if (sev->snp_certs_enabled) {
+			vcpu->run->exit_reason = KVM_EXIT_SNP_REQ_CERTS;
+			vcpu->run->snp_req_certs.gfn = gpa_to_gfn(data_gpa);
+			vcpu->run->snp_req_certs.npages = data_npages;
+			vcpu->run->snp_req_certs.ret = 0;
+			vcpu->arch.complete_userspace_io = snp_complete_req_certs;
+			return 0; /* fetch certs from userspace */
+		}
+
 		/*
 		 * As per GHCB spec (see "SNP Extended Guest Request"), the
 		 * certificate table is terminated by 24-bytes of zeroes.
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index d4490eaed55d..b7472c225812 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -112,6 +112,7 @@ struct kvm_sev_info {
 	void *guest_req_buf;    /* Bounce buffer for SNP Guest Request input */
 	void *guest_resp_buf;   /* Bounce buffer for SNP Guest Request output */
 	struct mutex guest_req_mutex; /* Must acquire before using bounce buffers */
+	bool snp_certs_enabled;	/* SNP certificate-fetching support. */
 };
 
 struct kvm_svm {
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index c6988e2c68d5..c07d0b1ce7d1 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -135,6 +135,12 @@ struct kvm_xen_exit {
 	} u;
 };
 
+struct kvm_exit_snp_req_certs {
+	__u64 gfn;
+	__u64 npages;
+	__u64 ret;
+};
+
 #define KVM_S390_GET_SKEYS_NONE   1
 #define KVM_S390_SKEYS_MAX        1048576
 
@@ -178,6 +184,7 @@ struct kvm_xen_exit {
 #define KVM_EXIT_NOTIFY           37
 #define KVM_EXIT_LOONGARCH_IOCSR  38
 #define KVM_EXIT_MEMORY_FAULT     39
+#define KVM_EXIT_SNP_REQ_CERTS    40
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -447,6 +454,8 @@ struct kvm_run {
 			__u64 gpa;
 			__u64 size;
 		} memory_fault;
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct kvm_exit_snp_req_certs snp_req_certs;
 		/* Fix the size of the union. */
 		char padding[256];
 	};
diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
index fcdfea767fca..38767aba4ff3 100644
--- a/include/uapi/linux/sev-guest.h
+++ b/include/uapi/linux/sev-guest.h
@@ -95,5 +95,13 @@ struct snp_ext_report_req {
 
 #define SNP_GUEST_VMM_ERR_INVALID_LEN	1
 #define SNP_GUEST_VMM_ERR_BUSY		2
+/*
+ * The GHCB spec essentially states that all non-zero error codes other than
+ * those explicitly defined above should be treated as an error by the guest.
+ * Define a generic error to cover that case, and choose a value that is not
+ * likely to overlap with new explicit error codes should more be added to
+ * the GHCB spec later.
+ */
+#define SNP_GUEST_VMM_ERR_GENERIC       (~0U)
 
 #endif /* __UAPI_LINUX_SEV_GUEST_H_ */

---

## [3] Michael Roth — 2025-04-28
*Subject: [PATCH v6 2/2] KVM: SEV: Add KVM_SEV_SNP_ENABLE_REQ_CERTS command*

Introduce a new command for KVM_MEMORY_ENCRYPT_OP ioctl that can be used
to enable fetching of endorsement key certificates from userspace via
the new KVM_EXIT_SNP_REQ_CERTS exit type. Also introduce a new
KVM_X86_SEV_SNP_REQ_CERTS KVM device attribute so that userspace can
query whether the kernel supports the new command/exit.

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 .../virt/kvm/x86/amd-memory-encryption.rst      | 17 ++++++++++++++++-
 arch/x86/include/uapi/asm/kvm.h                 |  2 ++
 arch/x86/kvm/svm/sev.c                          | 17 ++++++++++++++++-
 3 files changed, 34 insertions(+), 2 deletions(-)

diff --git a/Documentation/virt/kvm/x86/amd-memory-encryption.rst b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
index 1ddb6a86ce7f..cd680f129431 100644
--- a/Documentation/virt/kvm/x86/amd-memory-encryption.rst
+++ b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
@@ -572,6 +572,17 @@ Returns: 0 on success, -negative on error
 See SNP_LAUNCH_FINISH in the SEV-SNP specification [snp-fw-abi]_ for further
 details on the input parameters in ``struct kvm_sev_snp_launch_finish``.
 
+21. KVM_SEV_SNP_ENABLE_REQ_CERTS
+--------------------------------
+
+The KVM_SEV_SNP_ENABLE_REQ_CERTS command will configure KVM to exit to
+userspace with a ``KVM_EXIT_SNP_REQ_CERTS`` exit type as part of handling
+a guest attestation report, which will to allow userspace to provide a
+certificate corresponding to the endorsement key used by firmware to sign
+that attestation report.
+
+Returns: 0 on success, -negative on error
+
 Device attribute API
 ====================
 
@@ -579,11 +590,15 @@ Attributes of the SEV implementation can be retrieved through the
 ``KVM_HAS_DEVICE_ATTR`` and ``KVM_GET_DEVICE_ATTR`` ioctls on the ``/dev/kvm``
 device node, using group ``KVM_X86_GRP_SEV``.
 
-Currently only one attribute is implemented:
+The following attributes are currently implemented:
 
 * ``KVM_X86_SEV_VMSA_FEATURES``: return the set of all bits that
   are accepted in the ``vmsa_features`` of ``KVM_SEV_INIT2``.
 
+* ``KVM_X86_SEV_SNP_REQ_CERTS``: return a value of 1 if the kernel supports the
+  ``KVM_EXIT_SNP_REQ_CERTS`` exit, which allows for fetching endorsement key
+  certificates from userspace for each SNP attestation request the guest issues.
+
 Firmware Management
 ===================
 
diff --git a/arch/x86/include/uapi/asm/kvm.h b/arch/x86/include/uapi/asm/kvm.h
index 225a12e0d5d6..24045279dbea 100644
--- a/arch/x86/include/uapi/asm/kvm.h
+++ b/arch/x86/include/uapi/asm/kvm.h
@@ -468,6 +468,7 @@ struct kvm_sync_regs {
 /* vendor-specific groups and attributes for system fd */
 #define KVM_X86_GRP_SEV			1
 #  define KVM_X86_SEV_VMSA_FEATURES	0
+#  define KVM_X86_SEV_SNP_REQ_CERTS	1
 
 struct kvm_vmx_nested_state_data {
 	__u8 vmcs12[KVM_STATE_NESTED_VMX_VMCS_SIZE];
@@ -708,6 +709,7 @@ enum sev_cmd_id {
 	KVM_SEV_SNP_LAUNCH_START = 100,
 	KVM_SEV_SNP_LAUNCH_UPDATE,
 	KVM_SEV_SNP_LAUNCH_FINISH,
+	KVM_SEV_SNP_ENABLE_REQ_CERTS,
 
 	KVM_SEV_NR_MAX,
 };
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index b74e2be2cbaf..d5b4f308ab3a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2123,7 +2123,9 @@ int sev_dev_get_attr(u32 group, u64 attr, u64 *val)
 	case KVM_X86_SEV_VMSA_FEATURES:
 		*val = sev_supported_vmsa_features;
 		return 0;
-
+	case KVM_X86_SEV_SNP_REQ_CERTS:
+		*val = sev_snp_enabled ? 1 : 0;
+		return 0;
 	default:
 		return -ENXIO;
 	}
@@ -2535,6 +2537,16 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return ret;
 }
 
+static int snp_enable_certs(struct kvm *kvm)
+{
+	if (kvm->created_vcpus || !sev_snp_guest(kvm))
+		return -EINVAL;
+
+	to_kvm_sev_info(kvm)->snp_certs_enabled = true;
+
+	return 0;
+}
+
 int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 {
 	struct kvm_sev_cmd sev_cmd;
@@ -2640,6 +2652,9 @@ int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 	case KVM_SEV_SNP_LAUNCH_FINISH:
 		r = snp_launch_finish(kvm, &sev_cmd);
 		break;
+	case KVM_SEV_SNP_ENABLE_REQ_CERTS:
+		r = snp_enable_certs(kvm);
+		break;
 	default:
 		r = -EINVAL;
 		goto out;

---

## [4] Liam Merwick — 2025-04-29
*Subject: Re: [PATCH v6 2/2] KVM: SEV: Add KVM_SEV_SNP_ENABLE_REQ_CERTS command*

On 28/04/2025 20:51, Michael Roth wrote:
> Introduce a new command for KVM_MEMORY_ENCRYPT_OP ioctl that can be used
> to enable fetching of endorsement key certificates from userspace via

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>
Tested-by: Liam Merwick <liam.merwick@oracle.com>


> ---
>   .../virt/kvm/x86/amd-memory-encryption.rst      | 17 ++++++++++++++++-

---
