---
title: '6.18 CVM guest kernel boot issues with non-UEFI bootloader'
date: 2026-01-28
last_reply: 2026-01-30
message_count: 5
participants: ['Kevin Hui', 'Tom Lendacky', 'Ard Biesheuvel']
---

## [1] Kevin Hui — 2026-01-28

Hello,

We’ve been using a non-UEFI bootloader to launch SEV-SNP CVMs and noticed that
there’s an issue with booting the newest 6.18 guest kernel with
the stage0 bootloader (https://github.com/project-oak/oak/tree/main/stage0_bin).
The guest kernel boots successfully with 6.17 and below, but fails with 6.18. We
were able to reproduce this with host kernels 6.13.2 and 6.18.3 on Milan/Genoa
hosts.

We traced the commit that started causing boot issues to
68a501d7fd82454525797971c6a0005ceeb93153 and noticed that for some reason the
variable snp_vmpl was non-zero, even though our stack doesn’t run SVSM. This
triggers the sev_es_terminate() call and subsequently crashes the CVM. We
noticed that the commit removes a supposedly redundant rmpadjust() check, but
from our observations it seems that the failed rmpadjust() short-circuited the
check and avoided the underlying issue.

I was chatting with Tom about this, and taking a deeper look at the issue, we
suspect that the BSS is cleared after the sev_enable() call in
arch/x86/boot/compressed/head_64.S, and that because of this snp_vmpl contains
random junk and is not zeroed. When coming through UEFI, it seems that the BSS
is cleared via drivers/firmware/efi/libstub/x86-stub.c, but in a non-UEFI
bootloader there is no call to startup_64 and so this path is never invoked,
leaving whatever random data was in bss to remain.

Perhaps the proper fix for this is to put the variables that are set as part of
sev_enable() into .data so that both non-UEFI and UEFI bootloaders will have the
same treatment from the kernel, but I would love to hear everyone’s thoughts on
this.

Thanks,
Kevin

---

## [2] Tom Lendacky — 2026-01-30
*Subject: Re: 6.18 CVM guest kernel boot issues with non-UEFI bootloader*

Adding Ard

On 1/28/26 21:57, Kevin Hui wrote:
> Hello,
>

---

## [3] Ard Biesheuvel — 2026-01-30
*Subject: Re: 6.18 CVM guest kernel boot issues with non-UEFI bootloader*

Hi Tom Kevin,

On Fri, 30 Jan 2026, at 19:49, Tom Lendacky wrote:
> Adding Ard
>

If there is no call to startup_64(), where does the call to sev_enable() originate from?

>> Perhaps the proper fix for this is to put the variables that are set as part of
>> sev_enable() into .data so that both non-UEFI and UEFI bootloaders will have the

AIUI, the root cause of the issue is that C code is being called (sev_enable()) before BSS has been cleared, right?

If so, I don't think moving variables around is the right solution here: instead, BSS should be cleared before calling C code. And by the looks of it, this is not even SEV-specific, given that load_stage1_idt() is also a C function.

---

## [4] Tom Lendacky — 2026-01-30
*Subject: Re: 6.18 CVM guest kernel boot issues with non-UEFI bootloader*

On 1/30/26 14:49, Ard Biesheuvel wrote:
> Hi Tom Kevin,
> 

There is a call to startup_64().

> 
>>> Perhaps the proper fix for this is to put the variables that are set as part of

Right, but the issue also is that the BSS gets cleared after relocation,
too. So I don't think using BSS is correct, because it would have to be
cleared before the call to sev_enable(). But the call to clear the BSS
after relocation would have to stay because to, otherwise the guest crashes.

> 
> If so, I don't think moving variables around is the right solution here: instead, BSS should be cleared before calling C code. And by the looks of it, this is not even SEV-specific, given that load_stage1_idt() is also a C function.

Because of how things are called and because of the relocation, I think
putting the variables in .data is probably the right thing to do. I've
noticed a few other files under arch/x86/boot/compressed that have
variables defined with __section(".data") probably for the same reason.

The load_stage1_idt() function only works with variables on a stack or in
.data (boot_idt), which is probably why that works ok.

Thanks,
Tom

>

---

## [5] Ard Biesheuvel — 2026-01-30
*Subject: Re: 6.18 CVM guest kernel boot issues with non-UEFI bootloader*

On Fri, 30 Jan 2026, at 23:05, Tom Lendacky wrote:
> On 1/30/26 14:49, Ard Biesheuvel wrote:
>> Hi Tom Kevin,
...
>>>> Perhaps the proper fix for this is to put the variables that are set as part of
>>>> sev_enable() into .data so that both non-UEFI and UEFI bootloaders will have the

Yeah, and relocating the image should migrate the contents of BSS too. So I agree that this is tricky. I hate the decompressor ...

>> 
>> If so, I don't think moving variables around is the right solution here: instead, BSS should be cleared before calling C code. And by the looks of it, this is not even SEV-specific, given that load_stage1_idt() is also a C function.

Indeed. In fact, creating any global state before relocation is rather tricky because of how the image moves itself around. But I guess it is unavoidable here.

---
