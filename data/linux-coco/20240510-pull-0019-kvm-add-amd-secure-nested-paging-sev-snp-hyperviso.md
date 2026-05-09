---
title: '[PULL 00/19] KVM: Add AMD Secure Nested Paging (SEV-SNP) Hypervisor Support'
date: 2024-05-10
last_reply: 2024-06-03
message_count: 7
participants: ['Michael Roth', 'Paolo Bonzini', 'Sean Christopherson']
---

## [1] Michael Roth — 2024-05-10

Hi Paolo,

This pull request contains v15 of the KVM SNP support patchset[1] along
with fixes and feedback from you and Sean regarding PSC request processing,
fast_page_fault() handling for SNP/TDX, and avoiding uncessary
PSMASH/zapping for KVM_EXIT_MEMORY_FAULT events. It's also been rebased
on top of kvm/queue (commit 1451476151e0), and re-tested with/without
2MB gmem pages enabled.

Thanks!

-Mike

[1] https://lore.kernel.org/kvm/20240501085210.2213060-1-michael.roth@amd.com/

The following changes since commit 1451476151e08e1e83ff07ce69dd0d1d025e976e:

  Merge commit 'kvm-coco-hooks' into HEAD (2024-05-10 13:20:42 -0400)

are available in the Git repository at:

  https://github.com/mdroth/linux.git tags/tags/kvm-queue-snp

for you to fetch changes up to 4b3f0135f759bb1a54bb28d644c38a7780150eda:

  crypto: ccp: Add the SNP_VLEK_LOAD command (2024-05-10 14:44:31 -0500)

----------------------------------------------------------------
Base x86 KVM support for running SEV-SNP guests:

 - add some basic infrastructure and introduces a new KVM_X86_SNP_VM
   vm_type to handle differences versus the existing KVM_X86_SEV_VM and
   KVM_X86_SEV_ES_VM types.

 - implement the KVM API to handle the creation of a cryptographic
   launch context, encrypt/measure the initial image into guest memory,
   and finalize it before launching it.

 - implement handling for various guest-generated events such as page
   state changes, onlining of additional vCPUs, etc.

 - implement the gmem/mmu hooks needed to prepare gmem-allocated pages
   before mapping them into guest private memory ranges as well as
   cleaning them up prior to returning them to the host for use as
   normal memory. Because those cleanup hooks supplant certain
   activities like issuing WBINVDs during KVM MMU invalidations, avoid
   duplicating that work to avoid unecessary overhead.

 - add support for the servicing of guest requests to handle things like
   attestation, as well as some related host-management interfaces to
   handle updating firmware's signing key for attestation requests

----------------------------------------------------------------
Ashish Kalra (1):
      KVM: SEV: Avoid WBINVD for HVA-based MMU notifications for SNP

Brijesh Singh (8):
      KVM: SEV: Add initial SEV-SNP support
      KVM: SEV: Add KVM_SEV_SNP_LAUNCH_START command
      KVM: SEV: Add KVM_SEV_SNP_LAUNCH_UPDATE command
      KVM: SEV: Add KVM_SEV_SNP_LAUNCH_FINISH command
      KVM: SEV: Add support to handle GHCB GPA register VMGEXIT
      KVM: SEV: Add support to handle RMP nested page faults
      KVM: SVM: Add module parameter to enable SEV-SNP
      KVM: SEV: Provide support for SNP_GUEST_REQUEST NAE event

Michael Roth (9):
      KVM: MMU: Disable fast path if KVM_EXIT_MEMORY_FAULT is needed
      KVM: SEV: Select KVM_GENERIC_PRIVATE_MEM when CONFIG_KVM_AMD_SEV=y
      KVM: SEV: Add support to handle MSR based Page State Change VMGEXIT
      KVM: SEV: Add support to handle Page State Change VMGEXIT
      KVM: SEV: Implement gmem hook for initializing private pages
      KVM: SEV: Implement gmem hook for invalidating private pages
      KVM: x86: Implement hook for determining max NPT mapping level
      KVM: SEV: Provide support for SNP_EXTENDED_GUEST_REQUEST NAE event
      crypto: ccp: Add the SNP_VLEK_LOAD command

Tom Lendacky (1):
      KVM: SEV: Support SEV-SNP AP Creation NAE event

 Documentation/virt/coco/sev-guest.rst              |   19 +
 Documentation/virt/kvm/api.rst                     |   87 ++
 .../virt/kvm/x86/amd-memory-encryption.rst         |  110 +-
 arch/x86/include/asm/kvm_host.h                    |    2 +
 arch/x86/include/asm/sev-common.h                  |   25 +
 arch/x86/include/asm/sev.h                         |    3 +
 arch/x86/include/asm/svm.h                         |    9 +-
 arch/x86/include/uapi/asm/kvm.h                    |   48 +
 arch/x86/kvm/Kconfig                               |    3 +
 arch/x86/kvm/mmu.h                                 |    2 -
 arch/x86/kvm/mmu/mmu.c                             |   25 +-
 arch/x86/kvm/svm/sev.c                             | 1546 +++++++++++++++++++-
 arch/x86/kvm/svm/svm.c                             |   37 +-
 arch/x86/kvm/svm/svm.h                             |   52 +
 arch/x86/kvm/trace.h                               |   31 +
 arch/x86/kvm/x86.c                                 |   17 +
 drivers/crypto/ccp/sev-dev.c                       |   36 +
 include/linux/psp-sev.h                            |    4 +-
 include/uapi/linux/kvm.h                           |   23 +
 include/uapi/linux/psp-sev.h                       |   27 +
 include/uapi/linux/sev-guest.h                     |    9 +
 virt/kvm/guest_memfd.c                             |    4 +-
 22 files changed, 2086 insertions(+), 33 deletions(-)

---

## [2] Paolo Bonzini — 2024-05-12
*Subject: Re: [PULL 00/19] KVM: Add AMD Secure Nested Paging (SEV-SNP)
 Hypervisor Support*

On Fri, May 10, 2024 at 11:17 PM Michael Roth <michael.roth@amd.com> wrote:
>
> Hi Paolo,

Pulled into kvm-coco-queue, thanks (and sorry for the sev_complete_psc
mess up - it seemed too good to be true that the PSC changes were all
fine...).

Paolo

> Thanks!
>

---

## [3] Paolo Bonzini — 2024-05-12
*Subject: Re: [PULL 00/19] KVM: Add AMD Secure Nested Paging (SEV-SNP)
 Hypervisor Support*

On Sun, May 12, 2024 at 9:14 AM Paolo Bonzini <pbonzini@redhat.com> wrote:
>
> On Fri, May 10, 2024 at 11:17 PM Michael Roth <michael.roth@amd.com> wrote:

... and there was a missing signoff in "KVM: SVM: Add module parameter
to enable SEV-SNP" so I ended up not using the pull request. But it
was still good to have it because it made it simpler to double check
what you tested vs. what I applied.

Also I have already received the full set of pull requests for
submaintainers, so I put it in kvm/next.  It's not impossible that it
ends up in the 6.10 merge window, so I might as well give it a week or
two in linux-next.

Paolo


Paolo

---

## [4] Michael Roth — 2024-05-12
*Subject: Re: [PULL 00/19] KVM: Add AMD Secure Nested Paging (SEV-SNP)
 Hypervisor Support*

On Sun, May 12, 2024 at 10:17:06AM +0200, Paolo Bonzini wrote:
> On Sun, May 12, 2024 at 9:14 AM Paolo Bonzini <pbonzini@redhat.com> wrote:
> >

That issue was actually introduced from my end while applying the changes,
so I think your suggested changes did pretty much work as-written. :)

> 
> ... and there was a missing signoff in "KVM: SVM: Add module parameter

Makes sense; glad to hear it! I've re-tested the kvm/next version and
everything looks good. Will also get our CI configured to monitor kvm/next
as well.

Thanks,

Mike

> 
> Paolo

---

## [5] Sean Christopherson — 2024-05-13
*Subject: Re: [PULL 00/19] KVM: Add AMD Secure Nested Paging (SEV-SNP)
 Hypervisor Support*

On Sun, May 12, 2024, Paolo Bonzini wrote:
> On Sun, May 12, 2024 at 9:14 AM Paolo Bonzini <pbonzini@redhat.com> wrote:
> >

I certainly don't object to getting coverage in linux-next, but unless we have a
very good reason to push for 6.10, which doesn't seem to be the case, my strong
preference is to wait until 6.11 for the official merge.  I haven't had a chance
to look at v15, and at a quick glance, the SNP_EXTENDED_GUEST_REQUEST support in
particular still looks kludgy.  In general, this all feels very rushed.

---

## [6] Michael Roth — 2024-05-30
*Subject: Re: [PULL 00/19] KVM: Add AMD Secure Nested Paging (SEV-SNP)
 Hypervisor Support*

On Fri, May 10, 2024 at 04:10:05PM -0500, Michael Roth wrote:
> Hi Paolo,
> 

As discussed during the PUCK call, here is a branch with fixup patches
that incorporate the additional review/testing that came in after these
patches were merged into kvm/next:

  https://github.com/mdroth/linux/commits/kvm-next-snp-fixes4/

They are intended to be squashed in but can also be applied on top if
that's preferable (but in that case the first 2 patches need to be
squashed together to maintain build bisectability):

 [SQUASH] KVM: SVM: Remove the need to trigger an UNBLOCK event on AP creation
   - drops handling for KVM_MP_STATE_UNINITIALIZED since no special
     handling for it will be needed until SVSM support is added in OVMF
     and the host kernel has the necessary support for running
     SVSM-enabled guests
   - to be squashed into:
     KVM: SEV: Support SEV-SNP AP Creation NAE event

 [SQUASH] KVM: SEV: Don't WARN() if RMP lookup fails when invalidating gmem pages
   - address the WARN() that Sean noticed when running guest_memfd_test
     kselftest on an AMD system without SNP enabled
   - to be squashed into:
     KVM: SEV: Implement gmem hook for invalidating private pages

 [SQUASH] KVM: SEV: Use new kvm_rmp_make_shared() naming
   - fixup to handle helper function being renamed in prior patch
   - to be squashed into:
     KVM: SEV: Add KVM_SEV_SNP_LAUNCH_FINISH command
     
 [SQUASH] KVM: SEV: Automatically switch reclaimed pages to shared
   - implement suggestion from Sean to always switch reclaimed pages to shared
     since that's what the callers all end up doing anyway
   - to be squashed into:
     KVM: SEV: Add KVM_SEV_SNP_LAUNCH_UPDATE command

As discussed at PUCK I will resubmit the guest requests patches
separately will all the pending changes incorporated.

Thanks!

-Mike

> 
> Thanks!

---

## [7] Paolo Bonzini — 2024-06-03
*Subject: Re: [PULL 00/19] KVM: Add AMD Secure Nested Paging (SEV-SNP)
 Hypervisor Support*

On Fri, May 31, 2024 at 5:23 AM Michael Roth <michael.roth@amd.com> wrote:
> As discussed during the PUCK call, here is a branch with fixup patches
> that incorporate the additional review/testing that came in after these

Yes, I'd rather not rebase kvm/next again so I applied them on top.
None of the issues are so egregiously bad.

Paolo

---
