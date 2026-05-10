---
title: '[RFC 0/3] Enlightened vTPM support for SVSM on SEV-SNP'
date: 2024-11-06
last_reply: 2024-11-06
message_count: 3
participants: ['Stefano Garzarella', 'James Bottomley']
---

## [1] Stefano Garzarella — 2024-11-06

Hi James,

On Tue, Jan 03, 2023 at 04:01:33PM -0500, James Bottomley wrote:
>This is a sketch for how a fully enlightened vTPM driver would work.
>The idea is that the SVSM responds on function 8 to vTPM requests, so

Thanks for this series, I'd like to restart this work and Claudio 
pointed me here.

IIUC the last version we have is the one in Coconut [1] which is based 
on this series, but with some changes on top from Claudio to probe SVSM 
and check if TPM commands are supported or not.

I already rebased them for 6.11 here [2] and we will include them in the 
next coconut-svsm branch, but in the meantime I think nothing is 
blocking us to upstream them, so I can take care of Linux patches, while 
Oliver (in CC) is working on the EDK2 patch.

IIUC the only thing missing from the patches we have in Coconut are the 
fixes to Don's comments. Do you have a branch or patches with them 
already fixed?
Otherwise I can do it on top of the patches we have in Coconut.

Any other things to fix/improve that you can think of?

Let me know if it is okay with you that I will restart working on these 
patches.

Thanks,
Stefano

[1] https://github.com/coconut-svsm/linux/tree/svsm
[2] https://github.com/coconut-svsm/linux/pull/8

---

## [2] James Bottomley — 2024-11-06

On Wed, 2024-11-06 at 12:19 +0100, Stefano Garzarella wrote:
> Hi James,
> 

What are Don's comments? Did you mean Dov and this one:

https://lore.kernel.org/linux-coco/f7d0bd07-ba1b-894e-5e39-15fb1817bc8b@linux.ibm.com/

? Sure, but I thought Claudio had already addressed those? I can take a
look to see where this is, but I haven't been following closely.

> Otherwise I can do it on top of the patches we have in Coconut.
> 

The original was pretty simple: a platform TPM with a single
send/receive and the implementation inside the SVSM call code. I think
the only real change is switching from the msr method of calling to the
ghcb one, which it looks like is already done (or at least indirected
to the proper snp wrapper routine that does it)?

Regards,

James

---

## [3] Stefano Garzarella — 2024-11-06

On Wed, Nov 06, 2024 at 09:54:15AM -0500, James Bottomley wrote:
>On Wed, 2024-11-06 at 12:19 +0100, Stefano Garzarella wrote:
>> Hi James,

Ooops, yep I meant Dov's comments (exactly that thread), sorry about 
that!

>Sure, but I thought Claudio had already addressed those? I can take a
>look to see where this is, but I haven't been following closely.

Sure, I haven't seen those changes in the Coconut branch, but they seem 
straightforward such that I could make them if they got lost, no 
problem.

>
>> Otherwise I can do it on top of the patches we have in Coconut.

Yeah, that part should be fixed in the Coconut version since we now call 
svsm_perform_call_protocol() that should handles ghcb/msr IIUC.

Thanks,
Stefano

---
