---
title: 'SEV-SNP: Add KVM support for SNP certificate fetching'
date: 2026-01-09
last_reply: 2026-02-03
message_count: 6
participants: ['Michael Roth', 'Liam Merwick', 'Sean Christopherson']
---

## [1] Michael Roth — 2026-01-09

This patchset is also available at:

  https://github.com/amdese/linux/commits/snp-certs-v7

and is based on top of kvm/next (0499add8efd7)


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

  https://github.com/amdese/qemu/commits/snp-certs-rfc3-wip1

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

Changes since v6:

 * Incorporate documentation/comment suggestions from Sean, along with
   additional clarity/grammar fixups.
 * Don't define SNP_GUEST_VMM_ERR_GENERIC for general use within kernel,
   instead limit it to a KVM-specific choice of value in lieu of any
   formally-defined guest message return code for generic/undefined errors.
 * switch struct kvm_exit_snp_req_certs to using a 'gpa' argument instead
   of 'gfn' (Sean)
 * rebase to kvm/next, re-test, and collect R-b/T-b's

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

 Documentation/virt/kvm/api.rst                     | 44 ++++++++++++
 .../virt/kvm/x86/amd-memory-encryption.rst         | 52 ++++++++++++++-
 arch/x86/include/uapi/asm/kvm.h                    |  2 +
 arch/x86/kvm/svm/sev.c                             | 78 ++++++++++++++++++++--
 arch/x86/kvm/svm/svm.h                             |  1 +
 include/uapi/linux/kvm.h                           |  9 +++
 6 files changed, 179 insertions(+), 7 deletions(-)

---

## [2] Michael Roth — 2026-01-09
*Subject: [PATCH v7 1/2] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching*

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

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>
Tested-by: Liam Merwick <liam.merwick@oracle.com>
Tested-by: Dionna Glaze <dionnaglaze@google.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
[Melody: Update the documentation scheme about how file locking is
         expected to happen.]
Signed-off-by: Melody Wang <huibo.wang@amd.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 Documentation/virt/kvm/api.rst | 44 ++++++++++++++++++++++++
 arch/x86/kvm/svm/sev.c         | 62 ++++++++++++++++++++++++++++++----
 arch/x86/kvm/svm/svm.h         |  1 +
 include/uapi/linux/kvm.h       |  9 +++++
 4 files changed, 110 insertions(+), 6 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 01a3abef8abb..aa8b192179c2 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7353,6 +7353,50 @@ Please note that the kernel is allowed to use the kvm_run structure as the
 primary storage for certain register types. Therefore, the kernel may use the
 values in kvm_run even if the corresponding bit in kvm_dirty_regs is not set.
 
+::
+
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct kvm_exit_snp_req_certs {
+			__u64 gpa;
+			__u64 npages;
+			__u64 ret;
+		};
+
+KVM_EXIT_SNP_REQ_CERTS indicates an SEV-SNP guest with certificate-fetching
+enabled (see KVM_SEV_SNP_ENABLE_REQ_CERTS) has generated an Extended Guest
+Request NAE #VMGEXIT (SNP_GUEST_REQUEST) with message type MSG_REPORT_REQ,
+i.e. has requested an attestation report from firmware, and would like the
+certificate data corresponding the attestation report signature to be
+provided by the hypervisor as part of the request.
+
+To allow for userspace to provide the certificate, the 'gpa' and 'npages'
+are forwarded verbatim from the guest request (the RAX and RBX GHCB fields
+respectively).  'ret' is not an "output" from KVM, and is always '0' on
+exit.  KVM verifies the 'gpa' is 4KiB aligned prior to exiting to userspace,
+but otherwise the information from the guest isn't validated.
+
+Upon the next KVM_RUN, e.g. after userspace has serviced the request (or not),
+KVM will complete the #VMGEXIT, using the 'ret' field to determine whether to
+signal success or failure to the guest, and on failure, what reason code will
+be communicated via SW_EXITINFO2.  If 'ret' is set to an unsupported value (see
+the table below), KVM_RUN will fail with -EINVAL.  For a 'ret' of 'ENOSPC', KVM
+also consumes the 'npages' field, i.e. userspace can use the field to inform
+the guest of the number of pages needed to hold all the certificate data.
+
+The supported 'ret' values and their respective SW_EXITINFO2 encodings:
+
+  ======     =============================================================
+  0          0x0, i.e. success.  KVM will emit an SNP_GUEST_REQUEST command
+             to SNP firmware.
+  ENOSPC     0x0000000100000000, i.e. not enough guest pages to hold the
+             certificate table and certificate data.  KVM will also set the
+             RBX field in the GHBC to 'npages'.
+  EAGAIN     0x0000000200000000, i.e. the host is busy and the guest should
+             retry the request.
+  EIO        0xffffffff00000000, for all other errors (this return code is
+             a KVM-defined hypervisor value, as allowed by the GHCB)
+  ======     =============================================================
+
 
 .. _cap_enable:
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f59c65abe3cf..2405c6fad95c 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -41,6 +41,16 @@
 
 #define GHCB_HV_FT_SUPPORTED	(GHCB_HV_FT_SNP | GHCB_HV_FT_SNP_AP_CREATION)
 
+/*
+ * The GHCB spec essentially states that all non-zero error codes other than
+ * those explicitly defined above should be treated as an error by the guest.
+ * Define a generic error to cover that case, and choose a value that is not
+ * likely to overlap with new explicit error codes should more be added to
+ * the GHCB spec later. KVM will use this to report generic errors when
+ * handling SNP guest requests.
+ */
+#define SNP_GUEST_VMM_ERR_GENERIC       (~0U)
+
 /* enable/disable SEV support */
 static bool sev_enabled = true;
 module_param_named(sev, sev_enabled, bool, 0444);
@@ -4155,6 +4165,36 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
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
@@ -4170,14 +4210,15 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
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
+	 * to give userspace an opportunity to provide the certificate data
+	 * before issuing/completing the attestation request. Otherwise, return
+	 * an empty certificate table in the guest-provided data pages and
+	 * handle the attestation request immediately.
 	 */
 	if (msg_type == SNP_MSG_REPORT_REQ) {
+		struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
 		struct kvm_vcpu *vcpu = &svm->vcpu;
 		u64 data_npages;
 		gpa_t data_gpa;
@@ -4191,6 +4232,15 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 		if (!PAGE_ALIGNED(data_gpa))
 			goto request_invalid;
 
+		if (sev->snp_certs_enabled) {
+			vcpu->run->exit_reason = KVM_EXIT_SNP_REQ_CERTS;
+			vcpu->run->snp_req_certs.gpa = data_gpa;
+			vcpu->run->snp_req_certs.npages = data_npages;
+			vcpu->run->snp_req_certs.ret = 0;
+			vcpu->arch.complete_userspace_io = snp_complete_req_certs;
+			return 0;
+		}
+
 		/*
 		 * As per GHCB spec (see "SNP Extended Guest Request"), the
 		 * certificate table is terminated by 24-bytes of zeroes.
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 01be93a53d07..eac1cbd3debe 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -115,6 +115,7 @@ struct kvm_sev_info {
 	void *guest_resp_buf;   /* Bounce buffer for SNP Guest Request output */
 	struct mutex guest_req_mutex; /* Must acquire before using bounce buffers */
 	cpumask_var_t have_run_cpus; /* CPUs that have done VMRUN for this VM. */
+	bool snp_certs_enabled;	/* SNP certificate-fetching support. */
 };
 
 struct kvm_svm {
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index dddb781b0507..8cd107cdcf0b 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -135,6 +135,12 @@ struct kvm_xen_exit {
 	} u;
 };
 
+struct kvm_exit_snp_req_certs {
+	__u64 gpa;
+	__u64 npages;
+	__u64 ret;
+};
+
 #define KVM_S390_GET_SKEYS_NONE   1
 #define KVM_S390_SKEYS_MAX        1048576
 
@@ -180,6 +186,7 @@ struct kvm_xen_exit {
 #define KVM_EXIT_MEMORY_FAULT     39
 #define KVM_EXIT_TDX              40
 #define KVM_EXIT_ARM_SEA          41
+#define KVM_EXIT_SNP_REQ_CERTS    42
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -482,6 +489,8 @@ struct kvm_run {
 			__u64 gva;
 			__u64 gpa;
 		} arm_sea;
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct kvm_exit_snp_req_certs snp_req_certs;
 		/* Fix the size of the union. */
 		char padding[256];
 	};

---

## [3] Michael Roth — 2026-01-09
*Subject: [PATCH v7 2/2] KVM: SEV: Add KVM_SEV_SNP_ENABLE_REQ_CERTS command*

Introduce a new command for KVM_MEMORY_ENCRYPT_OP ioctl that can be used
to enable fetching of endorsement key certificates from userspace via
the new KVM_EXIT_SNP_REQ_CERTS exit type. Also introduce a new
KVM_X86_SEV_SNP_REQ_CERTS KVM device attribute so that userspace can
query whether the kernel supports the new command/exit.

Suggested-by: Sean Christopherson <seanjc@google.com>
Reviewed-by: Liam Merwick <liam.merwick@oracle.com>
Tested-by: Liam Merwick <liam.merwick@oracle.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 .../virt/kvm/x86/amd-memory-encryption.rst    | 52 ++++++++++++++++++-
 arch/x86/include/uapi/asm/kvm.h               |  2 +
 arch/x86/kvm/svm/sev.c                        | 16 ++++++
 3 files changed, 69 insertions(+), 1 deletion(-)

diff --git a/Documentation/virt/kvm/x86/amd-memory-encryption.rst b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
index 1ddb6a86ce7f..543b5e5dd8d4 100644
--- a/Documentation/virt/kvm/x86/amd-memory-encryption.rst
+++ b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
@@ -572,6 +572,52 @@ Returns: 0 on success, -negative on error
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
+NOTE: The endorsement key used by firmware may change as a result of
+management activities like updating SEV-SNP firmware or loading new
+endorsement keys, so some care should be taken to keep the returned
+certificate data in sync with the actual endorsement key in use by
+firmware at the time the attestation request is sent to SNP firmware. The
+recommended scheme to do this is to use file locking (e.g. via fcntl()'s
+F_OFD_SETLK) in the following manner:
+
+  - Prior to obtaining/providing certificate data as part of servicing an
+    exit type of ``KVM_EXIT_SNP_REQ_CERTS``, the VMM should obtain a
+    shared/read or exclusive/write lock on the certificate blob file before
+    reading it and returning it to KVM, and continue to hold the lock until
+    the attestation request is actually sent to firmware. To facilitate
+    this, the VMM can set the ``immediate_exit`` flag of kvm_run just after
+    supplying the certificate data, and just before resuming the vCPU.
+    This will ensure the vCPU will exit again to userspace with ``-EINTR``
+    after it finishes fetching the attestation request from firmware, at
+    which point the VMM can safely drop the file lock.
+
+  - Tools/libraries that perform updates to SNP firmware TCB values or
+    endorsement keys (e.g. via /dev/sev interfaces such as ``SNP_COMMIT``,
+    ``SNP_SET_CONFIG``, or ``SNP_VLEK_LOAD``, see
+    Documentation/virt/coco/sev-guest.rst for more details) in such a way
+    that the certificate blob needs to be updated, should similarly take an
+    exclusive lock on the certificate blob for the duration of any updates
+    to endorsement keys or the certificate blob contents to ensure that
+    VMMs using the above scheme will not return certificate blob data that
+    is out of sync with the endorsement key used by firmware at the time
+    the attestation request is actually issued.
+
+This scheme is recommended so that tools can use a fairly generic/natural
+approach to synchronizing firmware/certificate updates via file-locking,
+which should make it easier to maintain interoperability across
+tools/VMMs/vendors.
+
 Device attribute API
 ====================
 
@@ -579,11 +625,15 @@ Attributes of the SEV implementation can be retrieved through the
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
index 7ceff6583652..b2c928c5965d 100644
--- a/arch/x86/include/uapi/asm/kvm.h
+++ b/arch/x86/include/uapi/asm/kvm.h
@@ -503,6 +503,7 @@ struct kvm_sync_regs {
 #define KVM_X86_GRP_SEV			1
 #  define KVM_X86_SEV_VMSA_FEATURES	0
 #  define KVM_X86_SNP_POLICY_BITS	1
+#  define KVM_X86_SEV_SNP_REQ_CERTS	2
 
 struct kvm_vmx_nested_state_data {
 	__u8 vmcs12[KVM_STATE_NESTED_VMX_VMCS_SIZE];
@@ -743,6 +744,7 @@ enum sev_cmd_id {
 	KVM_SEV_SNP_LAUNCH_START = 100,
 	KVM_SEV_SNP_LAUNCH_UPDATE,
 	KVM_SEV_SNP_LAUNCH_FINISH,
+	KVM_SEV_SNP_ENABLE_REQ_CERTS,
 
 	KVM_SEV_NR_MAX,
 };
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 2405c6fad95c..695463bc6c5b 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2161,6 +2161,9 @@ int sev_dev_get_attr(u32 group, u64 attr, u64 *val)
 		*val = snp_supported_policy_bits;
 		return 0;
 
+	case KVM_X86_SEV_SNP_REQ_CERTS:
+		*val = sev_snp_enabled ? 1 : 0;
+		return 0;
 	default:
 		return -ENXIO;
 	}
@@ -2577,6 +2580,16 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
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
@@ -2682,6 +2695,9 @@ int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
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

## [4] Liam Merwick — 2026-01-13
*Subject: Re: [PATCH v7 0/2] SEV-SNP: Add KVM support for SNP certificate
 fetching*

On 09/01/2026 23:17, Michael Roth wrote:
> This patchset is also available at:
> 

(...)

> 
> Changes since v6:

v7 also
Tested-by: Liam Merwick <liam.merwick@oracle.com>


(...)
> 
> ----------------------------------------------------------------

---

## [5] Sean Christopherson — 2026-01-23
*Subject: Re: [PATCH v7 1/2] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching*

On Fri, Jan 09, 2026, Michael Roth wrote:
> +KVM_EXIT_SNP_REQ_CERTS indicates an SEV-SNP guest with certificate-fetching
> +enabled (see KVM_SEV_SNP_ENABLE_REQ_CERTS) has generated an Extended Guest
                                  ^
                                  |
                                  to


I'll fixup when applying.  Thanks for the *fantastic* documentation!

---

## [6] Sean Christopherson — 2026-02-03
*Subject: Re: [PATCH v7 0/2] SEV-SNP: Add KVM support for SNP certificate fetching*

On Fri, 09 Jan 2026 17:17:31 -0600, Michael Roth wrote:
> This patchset is also available at:
> 

Applied to kvm-x86 svm, thanks!

[1/2] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching
      https://github.com/kvm-x86/linux/commit/fa9893fadbc2
[2/2] KVM: SEV: Add KVM_SEV_SNP_ENABLE_REQ_CERTS command
      https://github.com/kvm-x86/linux/commit/20c3c4108d58

--
https://github.com/kvm-x86/linux/tree/next

---
