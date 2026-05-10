---
title: 'SEV-SNP: Add KVM support for SNP certificate fetching'
date: 2025-01-20
last_reply: 2025-02-19
message_count: 7
participants: ['Melody Wang', 'Dionna Amalie Glaze', 'Sean Christopherson', 'Liam Merwick', 'Michael Roth']
---

## [1] Melody Wang — 2025-01-20

This patchset is also available at:

  https://github.com/amdese/linux/commits/snp-certs-v4

and is based on top of linux/master (619f0b6fad52)

v3 of these patches were previously submitted under:

  [PATCH v3 0/2] SEV-SNP: Add KVM support for SNP certificate fetching
  https://lore.kernel.org/all/20241218152226.1113411-1-michael.roth@amd.com/


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

  https://github.com/amdese/qemu/commits/snp-certs-rfc1-wip4

A basic command-line invocation for SNP with certificate data supplied
would be:

 qemu-system-x86_64 -smp 32,maxcpus=255 -cpu EPYC-Milan-v2
  -machine q35,confidential-guest-support=sev0,memory-backend=ram1
  -object memory-backend-memfd,id=ram1,size=4G,share=true,reserve=false
  -object sev-snp-guest,id=sev0,cbitpos=51,reduced-phys-bits=1,id-auth=,certs-path=/home/mroth/cert.blob
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

-Melody

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


Michael Roth (1):
  KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching

 Documentation/virt/kvm/api.rst  | 106 ++++++++++++++++++++++++++++++++
 arch/x86/include/asm/kvm_host.h |   1 +
 arch/x86/kvm/svm/sev.c          |  43 +++++++++++--
 arch/x86/kvm/x86.c              |  11 ++++
 include/uapi/linux/kvm.h        |  10 +++
 include/uapi/linux/sev-guest.h  |   8 +++
 6 files changed, 173 insertions(+), 6 deletions(-)

---

## [2] Melody Wang — 2025-01-20
*Subject: [PATCH v4 1/1] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching*

From: Michael Roth <michael.roth@amd.com>

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

Also introduce a KVM_CAP_EXIT_SNP_REQ_CERTS capability to enable/disable
the exit for cases where userspace does not support
certificate-fetching, in which case KVM will fall back to returning an
empty certificate table if the guest provides a buffer for it.

  [Melody: Update the documentation scheme about how file locking is
  expected to happen.]

Signed-off-by: Michael Roth <michael.roth@amd.com>
Signed-off-by: Melody Wang <huibo.wang@amd.com>
---
 Documentation/virt/kvm/api.rst  | 106 ++++++++++++++++++++++++++++++++
 arch/x86/include/asm/kvm_host.h |   1 +
 arch/x86/kvm/svm/sev.c          |  43 +++++++++++--
 arch/x86/kvm/x86.c              |  11 ++++
 include/uapi/linux/kvm.h        |  10 +++
 include/uapi/linux/sev-guest.h  |   8 +++
 6 files changed, 173 insertions(+), 6 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index f15b61317aad..f00db1e4c6cc 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7176,6 +7176,95 @@ Please note that the kernel is allowed to use the kvm_run structure as the
 primary storage for certain register types. Therefore, the kernel may use the
 values in kvm_run even if the corresponding bit in kvm_dirty_regs is not set.
 
+::
+
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct kvm_exit_snp_req_certs {
+			__u64 gfn;
+			__u32 npages;
+			__u32 ret;
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
+    either write an empty certificate table into the address corresponding
+    to `gfn`, or it can disable ``KVM_EXIT_SNP_REQ_CERTS`` (via
+    ``KVM_CAP_EXIT_SNP_REQ_CERTS``), in which case KVM will handle
+    returning an empty certificate table to the guest.
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
+  - If some other error occurred, userspace must set `ret` to ``EIO``.
+    (This is to reserve special meaning for unused error codes in the
+    future.)
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
+This scheme is recommended so that tools could naturally opt to use
+it rather than every service provider coming up with a different solution
+that they will need to work into some custom QEMU/VMM to solve the same
+problem.
+
+However, userspace is free to implement their own completely separate
+mechanism for handing all this and completely ignore file locking. QEMU is
+only trying to play nice with this above-mentioned reference implementation
+and cooperative management tools, and not trying to profess to provide any
+sort of synchronization for cases where those sorts of management-level
+updates are performed without utilizing this reference implementation for
+synchronization.
 
 .. _cap_enable:
 
@@ -9020,6 +9109,23 @@ Do not use KVM_X86_SW_PROTECTED_VM for "real" VMs, and especially not in
 production.  The behavior and effective ABI for software-protected VMs is
 unstable.
 
+8.42 KVM_CAP_EXIT_SNP_REQ_CERTS
+-------------------------------
+
+:Capability: KVM_CAP_EXIT_SNP_REQ_CERTS
+:Architectures: x86
+:Type: vm
+
+This capability, if enabled, will cause KVM to exit to userspace with
+KVM_EXIT_SNP_REQ_CERTS exit reason to allow for fetching SNP attestation
+certificates from userspace.
+
+Calling KVM_CHECK_EXTENSION for this capability will return a non-zero
+value to indicate KVM support for KVM_EXIT_SNP_REQ_CERTS.
+
+The 1st argument to KVM_ENABLE_CAP should be 1 to indicate userspace support
+for handling this event.
+
 9. Known KVM API problems
 =========================
 
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index e159e44a6a1b..dae1a572d770 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1438,6 +1438,7 @@ struct kvm_arch {
 	struct kvm_x86_msr_filter __rcu *msr_filter;
 
 	u32 hypercall_exit_enabled;
+	bool snp_certs_enabled;
 
 	/* Guest can access the SGX PROVISIONKEY. */
 	bool sgx_provisioning_allowed;
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 943bd074a5d3..4896c34ed318 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4064,6 +4064,30 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 	return ret;
 }
 
+static int snp_complete_req_certs(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_svm *svm = to_svm(vcpu);
+	struct vmcb_control_area *control = &svm->vmcb->control;
+
+	if (vcpu->run->snp_req_certs.ret) {
+		if (vcpu->run->snp_req_certs.ret == ENOSPC) {
+			vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->snp_req_certs.npages;
+			ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+						SNP_GUEST_ERR(SNP_GUEST_VMM_ERR_INVALID_LEN, 0));
+		} else if (vcpu->run->snp_req_certs.ret == EAGAIN) {
+			ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,
+						SNP_GUEST_ERR(SNP_GUEST_VMM_ERR_BUSY, 0));
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
 static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_gpa)
 {
 	struct kvm *kvm = svm->vcpu.kvm;
@@ -4079,12 +4103,10 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
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
 		struct kvm_vcpu *vcpu = &svm->vcpu;
@@ -4100,6 +4122,15 @@ static int snp_handle_ext_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t r
 		if (!PAGE_ALIGNED(data_gpa))
 			goto request_invalid;
 
+		if (vcpu->kvm->arch.snp_certs_enabled) {
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
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index c79a8cc57ba4..cdcdc5359a87 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -4782,6 +4782,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_READONLY_MEM:
 		r = kvm ? kvm_arch_has_readonly_mem(kvm) : 1;
 		break;
+	case KVM_CAP_EXIT_SNP_REQ_CERTS:
+		r = 1;
+		break;
 	default:
 		break;
 	}
@@ -6743,6 +6746,14 @@ int kvm_vm_ioctl_enable_cap(struct kvm *kvm,
 		mutex_unlock(&kvm->lock);
 		break;
 	}
+	case KVM_CAP_EXIT_SNP_REQ_CERTS:
+		if (cap->args[0] != 1) {
+			r = -EINVAL;
+			break;
+		}
+		kvm->arch.snp_certs_enabled = true;
+		r = 0;
+		break;
 	default:
 		r = -EINVAL;
 		break;
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 502ea63b5d2e..dcaadd6f5b18 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -135,6 +135,12 @@ struct kvm_xen_exit {
 	} u;
 };
 
+struct kvm_exit_snp_req_certs {
+	__u64 gfn;
+	__u32 npages;
+	__u32 ret;
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
@@ -446,6 +453,8 @@ struct kvm_run {
 			__u64 gpa;
 			__u64 size;
 		} memory_fault;
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct kvm_exit_snp_req_certs snp_req_certs;
 		/* Fix the size of the union. */
 		char padding[256];
 	};
@@ -933,6 +942,7 @@ struct kvm_enable_cap {
 #define KVM_CAP_PRE_FAULT_MEMORY 236
 #define KVM_CAP_X86_APIC_BUS_CYCLES_NS 237
 #define KVM_CAP_X86_GUEST_MODE 238
+#define KVM_CAP_EXIT_SNP_REQ_CERTS 239
 
 struct kvm_irq_routing_irqchip {
 	__u32 irqchip;
diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
index fcdfea767fca..4c4ed8bc71d7 100644
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
+#define SNP_GUEST_VMM_ERR_GENERIC       ((u32)~0U)
 
 #endif /* __UAPI_LINUX_SEV_GUEST_H_ */

---

## [3] Dionna Amalie Glaze — 2025-01-21
*Subject: Re: [PATCH v4 1/1] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching*

On Mon, Jan 20, 2025 at 1:58 PM Melody Wang <huibo.wang@amd.com> wrote:
>
> From: Michael Roth <michael.roth@amd.com>

Reviewed-by: Dionna Glaze <dionnaglaze@google.com>

> ---
>  Documentation/virt/kvm/api.rst  | 106 ++++++++++++++++++++++++++++++++

Discussion, not a change request: given that my proposed patch [1] to
add rate-limiting for guest messages to the PSP generally was
rejected, do we think it'd be proper to add a KVM_EXIT_SNP_REQ_MSG or
some such for the VMM to decide if the guest should have access to the
globally shared resource (PSP) via EAGAIN or 0?

[1] https://patchwork.kernel.org/project/kvm/cover/20230119213426.379312-1-dionnaglaze@google.com/

> +               } else {
> +                       ghcb_set_sw_exit_info_2(svm->sev_es.ghcb,

---

## [4] Sean Christopherson — 2025-01-21
*Subject: Re: [PATCH v4 1/1] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching*

On Tue, Jan 21, 2025, Dionna Amalie Glaze wrote:
> On Mon, Jan 20, 2025 at 1:58 PM Melody Wang <huibo.wang@amd.com> wrote:
> > diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c

For the record, it wasn't rejected outright.  I pointed out flaws in the proposed
behavior[*], and AFAICT no one ever responded.  If I fully reject something, I
promise I will make it abundantly clear :-)

[*] https://lore.kernel.org/all/Y8rEFpbMV58yJIKy@google.com

> do we think it'd be proper to add a KVM_EXIT_SNP_REQ_MSG or
> some such for the VMM to decide if the guest should have access to the

Can you elaborate?  I don't quite understand what you're suggesting.

> [1] https://patchwork.kernel.org/project/kvm/cover/20230119213426.379312-1-dionnaglaze@google.com/
>

---

## [5] Dionna Amalie Glaze — 2025-01-21
*Subject: Re: [PATCH v4 1/1] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching*

On Tue, Jan 21, 2025 at 8:52 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Tue, Jan 21, 2025, Dionna Amalie Glaze wrote:

Okay, well it was a no to the implementation strategy I had chosen and
did not have bandwidth to change. Your suggestion to exit to userspace
is more aligned with the topic of discussion now.

> [*] https://lore.kernel.org/all/Y8rEFpbMV58yJIKy@google.com
>

I just mean that instead of only exiting to the VMM on an extended
guest request and this capability enabled, all guest requests exit to
the VMM to make the decision to permit access to the device. EAGAIN
means busy, try again later, and 0 means permit the request. That
allows for implementation-specific throttling policies to be
implemented.

> > [1] https://patchwork.kernel.org/project/kvm/cover/20230119213426.379312-1-dionnaglaze@google.com/
> >

---

## [6] Liam Merwick — 2025-01-21
*Subject: Re: [PATCH v4 1/1] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP
 certificate-fetching*

On 20/01/2025 21:58, Melody Wang wrote:
> From: Michael Roth <michael.roth@amd.com>
> 

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>


> ---
>   Documentation/virt/kvm/api.rst  | 106 ++++++++++++++++++++++++++++++++

---

## [7] Michael Roth — 2025-02-19
*Subject: Re: [PATCH v4 1/1] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP
 certificate-fetching*

On Tue, Jan 21, 2025 at 09:19:08AM -0800, Dionna Amalie Glaze wrote:
> On Tue, Jan 21, 2025 at 8:52 AM Sean Christopherson <seanjc@google.com> wrote:
> >

Discussed this with Sean on the PUCK call last week and our thinking was
that tying throttling support to a new KVM_EXIT_* type would not be
compatible with existing userspaces unless it is opt-in, and requiring
userspace to opt-in would not be ideal if DoS on the part of guest-owner is
a concern.

So most likely the more generalized exit-to-userspace throttling behavior
would be tied to something pre-existing, like existing EAGAIN/EINTR handling
for the KVM_RUN ioctl or something along that line.

And if the throttling occurs as part of this particular path, we still have
the option of using the SNP_GUEST_VMM_ERR_BUSY response to guest to force a
retry while still giving userspace the immediate_exit-triggered exit it
needs to release the lock and complete things on its end.

So, since throttling support doesn't seem like a blocker for this series, I
went ahead and sent a v5 with some minor documentation updates:

  https://lore.kernel.org/kvm/20250219151505.3538323-1-michael.roth@amd.com/

Thanks!

-Mike

> 
> > > [1] https://patchwork.kernel.org/project/kvm/cover/20230119213426.379312-1-dionnaglaze@google.com/

---
