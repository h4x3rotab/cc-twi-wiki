---
title: '[PATCH v6 1/2] KVM: Introduce KVM_EXIT_SNP_REQ_CERTS for SNP certificate-fetching'
date: 2025-05-21
last_reply: 2025-05-27
message_count: 2
participants: ['Sean Christopherson', 'Dionna Amalie Glaze']
---

## [1] Sean Christopherson — 2025-05-21

On Mon, Apr 28, 2025, Michael Roth wrote:
> For SEV-SNP, the host can optionally provide a certificate table to the
> guest when it issues an attestation request to firmware (see GHCB 2.0

Heh, gotta love the chaos that of tossing around a patch between its original
author and someone else.

The SoB chain should technically be:

Signed-off-by: Michael Roth <michael.roth@amd.com>
Signed-off-by: Melody Wang <huibo.wang@amd.com>
[Melody: Update the documentation scheme about how file locking is
         expected to happen]
Signed-off-by: Michael Roth <michael.roth@amd.com>

> ---
>  Documentation/virt/kvm/api.rst | 80 ++++++++++++++++++++++++++++++++++

Hmm, a bit late on feedback, but I think I'd prefer to provide the gpa, not the
gfn.  The address provided by the guest is a GPA, and similar KVM exits like
KVM_HC_MAP_GPA_RANGE provide gpa+npages.

> +			__u64 npages;
> +			__u64 ret;

KVM cannot guarantee the page is non-private.  Even if KVM is 100% certain the
page is shared when the userspace exit is initiated, unless KVM holds several
locks across the exit to userspace, nothing prevents the page from being converted
back to private.

> that userspace should use to write the contents of certificate data. 

Please don't write documentation in the style of the APM, i.e. don't describe
KVM's behavior in terms of what userspace should or should not do.  Userspace
can do whatever it wants, including terminating the guest.  What matters is what
information KVM will provide, and how KVM will respond to various userspace
actions.

> The format of this
> +certificate data is defined in the GHCB 2.0 specification (see section

As above, there is nothing userspace "must" do.      

Side topic, what sadist wrote the GHCB?  The "documentation" for MSG_REPORT_REQ
is garbage like this:

  If there are not enough guest pages to hold the certificate table and
  certificate data, the hypervisor will return the required number of pages
  needed to hold the certificate table and certificate data in the RBX register
  and set the SW_EXITINFO2 field to 0x0000000100000000

It's very frustrating that proper documentation of WTF 0x0000000100000000 means,
and where the seemingly magic values comes from, is left to software.

> +    the certificate table blob (in the format defined by the GHCB spec)
> +    into the address corresponding to `gfn` and set `ret` to 0 to indicate

And definitely don't mix "should" and "must".

My preference would be to first document what KVM will do/provide (which you've
done), and then document how KVM will complete the #VMGEXIT.  Leave all other
details to other documentation (more below on that).  E.g. (definitely audit
this for correctness):

----
::

    /* KVM_EXIT_SNP_REQ_CERTS */                                    
    struct kvm_exit_snp_req_certs {                                 
      __u64 gpa;                                              
      __u64 npages;                                           
      __u64 ret;                                              
    };          

KVM_EXIT_SNP_REQ_CERTS indicates an SEV-SNP guest with certificate requests
enabled (see KVM_SEV_SNP_ENABLE_REQ_CERTS) has generated an Extended Guest
Request NAE #VMGEXIT (SNP_GUEST_REQUEST) with message type MSG_REPORT_REQ,
i.e. has requested a certificate report from the hypervisor.

The 'gpa' and 'npages' are forwarded verbatim from the guest request (the RAX
and RBX GHCB fields respectively).  'ret' is not an "output" from KVM, and is
always '0' on exit.  KVM verifies the 'gpa' is 4KiB aligned prior to exiting to
userspace, but otherwise the information from the guest isn't validated.

Upon the next KVM_RUN, e.g. after userspace has serviced the request (or not),
KVM will complete the #VMGEXIT, using the 'ret' field to determine whether to
signal success or failure to the guest, and on failure, what reason code will
be communicated via SW_EXITINFO2.  If 'ret' is set to an unsupported value (see
the table below), KVM_RUN will fail with -EINVAL.  For a 'ret' of 'ENOSPC', KVM
also consumes the 'npages' field, i.e. userspace can use the field to inform
the guest of the number of pages needed to hold all certificates.

The supported 'ret' values and their respective SW_EXITINFO2 encodings:

  ======     =============================================================
  0          0x0, i.e. success.  KVM will emit an SNP_GUEST_REQUEST command
             to SNP firmware.
  ENOSPC     0x0000000100000000, i.e. not enough guest pages to hold the
             certificate table and certificate data.  KVM will also set the
             RBX field in the GHBC to 'npages'.
  EAGAIN     0x0000000200000000, i.e. the host is busy and the guest should
             retry the request.
  EIO        0xffffffff00000000, for all other errors (this return code is
             a KVM-defined hypervisor value, as allowed by the GHCB)
  ======     =============================================================
----

> +
> +  - All other possible values for `ret` are reserved for future use.

IMO, this is completely out of scope for KVM_EXIT_SNP_REQ_CERTS.  I would *love*
to see documentation for how userspace can implement attestation and certificate
management, but that belongs in Documentation/virt/kvm/x86/amd-memory-encryption.rst
as it obviously involves far more than just KVM_EXIT_SNP_REQ_CERTS.

>  .. _cap_enable:
>  

Maybe "to let userspace handle the request"?

> +	 * table in the guest-provided data pages.
>  	 */

As above, I think it makes sense to just do ".gpa = data_gpa".

> +			vcpu->run->snp_req_certs.npages = data_npages;
> +			vcpu->run->snp_req_certs.ret = 0;

Eh, I'd drop the comment.  KVM isn't "fetching" anything.

> diff --git a/include/uapi/linux/sev-guest.h b/include/uapi/linux/sev-guest.h
> index fcdfea767fca..38767aba4ff3 100644

This probably should go in arch/x86/include/uapi/asm/kvm.h, because it's not a
GHCB-defined error code.  And we really, really don't want guests taking specific
action for this error code, because that risks introducing VMM specific logic into
guest code that is supposed to be VMM agnostic.

---

## [2] Dionna Amalie Glaze — 2025-05-27

> Side topic, what sadist wrote the GHCB?  The "documentation" for MSG_REPORT_REQ
> is garbage like this:

Dude, please leave this kind of feedback in your head and treat your
collaborators with respect.

---
