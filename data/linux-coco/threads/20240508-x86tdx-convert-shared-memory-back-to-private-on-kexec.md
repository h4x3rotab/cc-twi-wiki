---
title: '[PATCHv10 10/18] x86/tdx: Convert shared memory back to private\n on kexec'
date: 2024-05-08
last_reply: 2024-05-10
message_count: 8
participants: ['Borislav Petkov', 'Kirill A. Shutemov', 'Vitaly Kuznetsov', 'Ruirui Yang', 'Dave Young', 'Kalra, Ashish']
---

## [1] Borislav Petkov — 2024-05-08

On Mon, May 06, 2024 at 06:37:19PM +0300, Kirill A. Shutemov wrote:
> "second kernel" is nomenclature kexec folks are using, but okay.

And the "third kernel" is the one which got kexec-ed the second time?

You can make it: "The second, kexec-ed kernel" and then it is perfectly
clear.

> > > +	/*
> > > +	 * Crash kernel reaches here with interrupts disabled: can't wait for

But you have the comment above it which already explains what's going
on...

> > Why are we printing something here if we're not really acting up on it?
> > 

Sure but you'll leave a trace if you panic right then and there, on the
first failure. Why noodle through the pages if the first failure is
already fatal?

> One possible reason for the failure is if kdump raced with memory
> conversion. In this case shared bit in page table got set (or not cleared

Lemme make sure I understand what you're saying here:

1. This is a fatal failure and we should panic

However,

2. the kexec-ed kernel is using a different page table so there won't be
   a mismatch between shared/private marking of the page so it doesn't
   matter

Close?

---

## [2] Borislav Petkov — 2024-05-08
*Subject: Re: [PATCHv10 11/18] x86/mm: Make e820_end_ram_pfn() cover
 E820_TYPE_ACPI ranges*

On Tue, Apr 09, 2024 at 02:30:03PM +0300, Kirill A. Shutemov wrote:
> Subject: Re: [PATCHv10 11/18] x86/mm: Make e820_end_ram_pfn() cover E820_TYPE_ACPI ranges
						^^^^^^^

e820__end_of_ram_pfn()

> e820__end_of_ram_pfn() is used to calculate max_pfn which, among other
> things, guides where direct mapping ends. Any memory above max_pfn is

RAM

...

---

## [3] Borislav Petkov — 2024-05-08
*Subject: Re: [PATCHv10 13/18] x86/acpi: Rename fields in
 acpi_madt_multiproc_wakeup structure*

On Tue, Apr 09, 2024 at 02:30:05PM +0300, Kirill A. Shutemov wrote:
> To prepare for the addition of support for MADT wakeup structure version

"In order to support... "

> 1, it is necessary to provide more appropriate names for the fields in
> the structure.

From Documentation/process/submitting-patches.rst:

 "Describe your changes in imperative mood, e.g. "make xyzzy do frotz"
  instead of "[This patch] makes xyzzy do frotz" or "[I] changed xyzzy
  to do frotz", as if you are giving orders to the codebase to change
  its behaviour."

So:

"Rename 'mailbox_version' to 'version' because... "

> the version of the structure and the related protocols, rather than the
> version of the mailbox. This field has not been utilized in the code

Ditto.

---

## [4] Kirill A. Shutemov — 2024-05-08

On Wed, May 08, 2024 at 02:04:22PM +0200, Borislav Petkov wrote:
> On Mon, May 06, 2024 at 06:37:19PM +0300, Kirill A. Shutemov wrote:
> > "second kernel" is nomenclature kexec folks are using, but okay.

Okay.

> > One possible reason for the failure is if kdump raced with memory
> > conversion. In this case shared bit in page table got set (or not cleared

Yes.

One other point is even if the failure is real and we cannot touch the
page as private, kdump kernel will boot fine as it uses pre-reserved
memory. What happens next depends on what dumping process does. We have
reasonable chance to produce useful dump on crash.

---

## [5] Vitaly Kuznetsov — 2024-05-09
*Subject: Re: [PATCH v4 0/4] x86/snp: Add kexec support*

Alexander Graf <graf@amazon.com> writes:

> Correct. With IMA, you even do exactly that: Enforce a signature check 
> of the next binary with kexec.

...

>
> I'm happy for CoCo to stay smoke and mirrors :). 

"Only a Sith deals in absolutes" :-)

> But I believe that if 
> you want to genuinely draw a trust chain back to an AMD/Intel 

Launch measurements are what they are, they describe the state of your
guest before it started booting. There are multiple mechanisms in Linux
which change CPL0 code already: self-modifying code like static keys,
loadable modules, runtime patching, kexec,... In case some specific
deployment requires stronger guarantees we can probably introduce
something like 'full lockdown' mode (as a compile time option, I guess)
which would disable all of the aforementioned mechanisms. It will still
not be a hard proof that the running code matches launch measurements
(because vulnerabilities/bugs may still exist) I guess but could be an
improvement.

Basically, what I wanted to argue is that kexec does not need to be
treated 'specially' for CVMs if we keep all other ways to modify kernel
code. Making these methods 'attestable' is currently a challenge indeed.

---

## [6] Ruirui Yang — 2024-05-09
*Subject: Re: [PATCH v6 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Fri, Apr 26, 2024 at 04:33:48PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

efi_mem_reserve is used to reserve boot service memory eg. bgrt, but
it is not necessary for kexec boot, as there are no boot services in
kexec reboot at all after the 1st kernel ExitBootServices().

The UEFI memmap passed to kexec kernel includes not only the runtime
service memory map but also the boot service memory ranges which were
reserved by the 1st kernel with efi_mem_reserve, and those boot service
memory ranges have already been marked "EFI_MEMORY_RUNTIME" attribute. 

Take example of bgrt, the saved memory is there only for people to check
the bgrt image info via /sys/firmware/acpi/bgrt/*, and it is not used in
early boot phase by boot services.

Above is the reason why the efi_mem_reserve can be skipped for kexec
booting.  But as I suggested before I personally think that checking
EFI_MEMORY_RUNTIME attribute set or not looks better than checking
efi_setup.

>  	if (efi_mem_desc_lookup(addr, &md) ||
>  	    md.type != EFI_BOOT_SERVICES_DATA) {

---

## [7] Dave Young — 2024-05-09
*Subject: Re: [PATCH v6 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Thu, 9 May 2024 at 17:56, Ruirui Yang <ruirui.yang@linux.dev> wrote:
>
> On Fri, Apr 26, 2024 at 04:33:48PM +0000, Ashish Kalra wrote:

I recently applied the linux.dev mail with my Chinese pinyin name  for
use when I do not have vpn access.   So just to clarify a bit, I'm the
same person here :)

---

## [8] Kalra, Ashish — 2024-05-10
*Subject: Re: [PATCH v6 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 5/9/2024 4:56 AM, Ruirui Yang wrote:

> On Fri, Apr 26, 2024 at 04:33:48PM +0000, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

Thanks for reviewing the patch.

I will move back to checking the md attribute instead of checking 
efi_setup as i was doing previously and resubmit this patch.

Thanks, Ashish

>
>>   	if (efi_mem_desc_lookup(addr, &md) ||

---
