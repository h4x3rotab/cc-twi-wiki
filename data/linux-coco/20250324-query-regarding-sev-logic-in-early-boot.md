---
title: 'query regarding SEV logic in early boot'
date: 2025-03-24
last_reply: 2025-03-25
message_count: 5
participants: ['Ard Biesheuvel', 'Tom Lendacky', 'Kirill A. Shutemov']
---

## [1] Ard Biesheuvel — 2025-03-24

L.S.,

As I am trying to disentangle the Linux early SEV boot code, the
legacy decompressor and the EFI stub, I noticed something that looks
broken to me, but I'm not quite sure how to fix it.

When booting via the EFI stub, the following call chain may occur:

setup_e820()
 process_unaccepted_memory()
  arch_accept_memory()
   snp_accept_memory()
    early_setup_ghcb()
     set_page_decrypted()
      set_clr_page_flags()

where the latter function relies on mapping_info to remap the GHCB
page as unencrypted. However, when entering via the EFI stub, this
struct is never initialized, and so I am struggling to see why this
works at all.

For context, I am looking into splitting/refactoring the decompressor
SEV startup code and the kernel proper's SEV startup code, in order to
a) use PIC codegen properly, and b) allow building a EFI-only bootable
image that does not include all the exception handling and demand
paging.

Any ideas?

---

## [2] Tom Lendacky — 2025-03-24
*Subject: Re: query regarding SEV logic in early boot*

On 3/24/25 12:28, Ard Biesheuvel wrote:
> L.S.,
> 

The latter function reads from the target page so that the page gets
faulted in via do_boot_page_fault(). do_boot_page_fault() calls
kernel_add_identity_map(), which calls kernel_ident_mapping_init() and
initializes the mapping_info struct.

At least that is how it is supposed to happen coming through the
decompressor. I couldn't recreate the path you sited until I tried an odd
size memory argument that was not 2M aligned (using 4097M on the qemu
command line fixed that). However, even that causes issues, because the
SEV_STATUS MSR doesn't get read until sev_enable() is called, which is
called after setup_e820(), so we actually can't even take the
snp_accept_memory() path.

But faking the SEV_STATUS MSR value does cause the code to get down to the
set_clr_page_flags() function and reading the input address contents
doesn't trigger do_boot_page_fault() to run because load_stage2_idt()
hasn't been called, which probably wouldn't matter anyway since the code
is running under the EFI page tables.

So, yes, this does appear broken.

Thanks,
Tom

> 
> For context, I am looking into splitting/refactoring the decompressor

---

## [3] Ard Biesheuvel — 2025-03-25
*Subject: Re: query regarding SEV logic in early boot*

(cc Kirill)

On Mon, 24 Mar 2025 at 20:14, Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 3/24/25 12:28, Ard Biesheuvel wrote:
...
> So, yes, this does appear broken.
>

OK, thanks for the analysis.

> The latter function reads from the target page so that the page gets
> faulted in via do_boot_page_fault(). do_boot_page_fault() calls

So we should never hit the page fault that triggers
kernel_ident_mapping_init() because all memory is already mapped (and
boot_ghcb_page is part of the image so it will definitely be mapped
even when not booting via EFI)

(For future reference, could you share the QEMU command line that you used?)

> But faking the SEV_STATUS MSR value does cause the code to get down to the
> set_clr_page_flags() function and reading the input address contents

Exactly, and that was the whole point of separating those code paths,
i.e., to get rid of all the demand paging logic and execute under the
EFI page tables (which use strict permissions for code and data, which
is a Microsoft requirement for secure boot signing)

So in a nutshell, the problem is that snp_accept_memory() calls into
the SEV code before sev_enable() has been called. But I wonder why
accepting memory is needed in the EFI stub at all?
(asking Kirill) Is it just to ensure that all unaccepted memory is at
the granularity provided by the bitmap? That could explain why nobody
ever noticed this.

Is there a problem with being conservative in the bitmap, and marking
misaligned chunks of accepted memory as unaccepted? AIUI, that would
remove the need entirely to accept any memory in the EFI stub - only
the decompressor code path would have a need for it.

---

## [4] Kirill A. Shutemov — 2025-03-25
*Subject: Re: query regarding SEV logic in early boot*

On Tue, Mar 25, 2025 at 08:22:50AM +0100, Ard Biesheuvel wrote:
> (cc Kirill)
> 

Yes, it is a problem.

It allows for double-accept (accept memory that is already accepted) which
opens us to manipulation from VMM. Malicious VMM can zero memory these
margins:

1. VMM remove memory in the margins.
2. VMM re-add the memory there.
3. Guest blindly accepts the memory.

And now previously accepted memory is zeroed by VMM.

Information in the bitmap must be precise.

---

## [5] Tom Lendacky — 2025-03-25
*Subject: Re: query regarding SEV logic in early boot*

On 3/25/25 02:22, Ard Biesheuvel wrote:
> (cc Kirill)
> 

I used the following Qemu command line:

./bin/qemu-system-x86_64 -enable-kvm \
 -cpu EPYC-v4,host-phys-bits=true -smp 1 \
 -machine type=q35,confidential-guest-support=sev0,memory-backend=ram1,vmport=off \
 -object memory-backend-memfd,id=ram1,size=4097M,share=true,prealloc=false \
 -object sev-snp-guest,id=sev0,policy=0xb0000,cbitpos=51,reduced-phys-bits=1 \
 -bios /root/kernels/qemu-install/OVMF.fd \
 -kernel /root/kernels/linux-build-x86_64/arch/x86/boot/bzImage \
 -append "console=ttyS0 earlyprintk=serial root=/dev/sda2" \
 -nographic -monitor pty -monitor unix:monitor,server,nowait \
 -gdb tcp::1234 -qmp tcp::4444,server,wait=off

Note, this doesn't have an initrd or guest image/disk, so the boot will
eventually fail, but it boots far enough along to encounter the issue
and test a fix.

Thanks,
Tom

> 
>> But faking the SEV_STATUS MSR value does cause the code to get down to the

---
