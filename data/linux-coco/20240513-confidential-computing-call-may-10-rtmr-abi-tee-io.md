---
title: 'Confidential Computing call May 10: RTMR ABI & TEE I/O'
date: 2024-05-13
last_reply: 2024-06-12
message_count: 11
participants: ['Samuel Ortiz', 'Alexander Graf', 'Reshetova, Elena', 'James Bottomley', 'Steve Rutherford']
---

## [1] Samuel Ortiz — 2024-05-13

On Fri, May 03, 2024 at 02:55:20PM -0500, Dan Middleton wrote:
> Hi
> Next Friday, May 10th at 9am PDT, we have a Confidential Computing

Thanks all for the discussions. The slides that were presented for the
RTMR ABI v3 are here:
https://docs.google.com/presentation/d/1qMk-8TiMigVmVAEDWXqPu9Jd7OJ8AGvCR34Lp2WunhU/edit?usp=sharing

Cheers,
Samuel.

---

## [2] Alexander Graf — 2024-06-07

Hi Dan,

On 03.05.24 21:55, Dan Middleton wrote:
>
> Hi


I haven't seen an email for today's call, so let me throw my topic 
suggestion here:

I would like to talk about "confidential kexec" today: A kexec mechanism 
that allows you to destroy the confidential VM you're in and recreate a 
new one based on a payload of the old one. With that, we would have a 
very easy and clean mechanism to bootstrap a VM into a fully measured 
new execution stack.


Thanks,

Alex





Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [3] Reshetova, Elena — 2024-06-07
*Subject: RE: Confidential Computing call May 10: RTMR ABI & TEE I/O*

> Hi Dan,
> 

Interesting topic, I am curious of the requirements!
Sounds like you want a local fast migration, i.e. a migration to a new
CoCo VM on the same platform? I guess the difference would be the absence
of the online migration phase since you are probably ok stopping the
original CoCo VM first. 



> 
>

---

## [4] Alexander Graf — 2024-06-07

On 07.06.24 16:46, Reshetova, Elena wrote:
>> Hi Dan,
>>


Almost. I basically want the VM to be able to provide a new early 
measurement. So the opposite of migration: With migration, I want to 
preserve previous state. Here, the main motivation is to get rid of any 
previous state except the new "seed" for the target VM.

There are 2 main use cases for this:

1) Measurement purely based on initial launch measurements. If the full 
OS is inside an initramfs, we can provide firmware+kernel+initramfs as 
"seed". The CoCo env would measure everything and I have an easy path to 
validate authenticity of my target environment. I also have an easy path 
to update the VM and then measure without replaying any event logs.

2) Update SVSM (or similar). Often today, you want to implement TPMs and 
inside a higher privileged component that is really part of the VM. To 
update it, you could use in-VM mechanisms, but that leaves a path where 
you boot with an old version -> exploit -> update to the new. If we 
could "reboot"/kexec into a new SVSM, we could reason about its 
confidentiality with a 100% guarantee.


Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [5] James Bottomley — 2024-06-08

On Fri, 2024-06-07 at 18:05 +0200, Alexander Graf wrote:
> 
> On 07.06.24 16:46, Reshetova, Elena wrote:

With an SVSM (that you're not replacing, so the initial launch
measurement remains valid) this one is easy: it can reinit everything
(including the vTPM) and redo a measured boot.  So here you have
exactly the same measurements as though it were a clean boot. 

> 2) Update SVSM (or similar). Often today, you want to implement TPMs
> and inside a higher privileged component that is really part of the

This one's a bit more difficult because the initial launch measurement
becomes invalid if the SVSM is replaced.  What I'd suggest happens here
is that the SVSM reinit everything (including the vTPM), then measure a
"replace SVSM" record containing both the old and new SVSM measurements
and then do a measured boot.  That way an attesting system can tie the
old launch measurement to the updated SVSM.

James

---

## [6] Alexander Graf — 2024-06-10

Hey James,

On 08.06.24 16:41, James Bottomley wrote:
>
> On Fri, 2024-06-07 at 18:05 +0200, Alexander Graf wrote:


That assumes you want an SVSM in the first place. I

   a) Don't think you really need to and
   b) Believe it should come from the customer, not the cloud provider, 
as it's the highest privileged piece of code in your VM


For both, the easy solution is to allow a customer to reboot into their 
own "initial launch measurement" from a currently running VM.

> measurement remains valid) this one is easy: it can reinit everything
> (including the vTPM) and redo a measured boot.  So here you have


This only works if the SVSM doesn't have any security vulnerabilities. 
If it does, you can't trust the measurement anymore and your whole 
update path is out of the window. For CoCo, we need to make sure that 
there is a viable way for users to run secure versions of all code 
without depending on the merit of their infrastructure provider, no?


Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [7] Reshetova, Elena — 2024-06-12
*Subject: RE: Confidential Computing call May 10: RTMR ABI & TEE I/O*

> 
> On 07.06.24 16:46, Reshetova, Elena wrote:

I think I am still confused on the problem statement. You are saying that
CoCo customers should be able to update their coco VMs (with SVSM or without)
without CSP intervention, which fully makes sense. But at the same time
you want to do it without a coco VM reboot (which is the easiest way of
solving this with existing means), but via some kind of fast runtime kexec
of the whole machine? Why? If customer is updating its coco VM, it should
be ok for them to save data and take a full reboot, why not?  
I do agree that there is another problem currently with the fact how hard
it is to reason about the state of the full SW stack of CoCo VM (many
measurements, many updated components, long event log, things that
might not get measured, etc.), but it seems a different problem to the 
one you are stating or? 

Best Regards,
Elena.



> 
>

---

## [8] Alexander Graf — 2024-06-12

Hi Elena,

On 12.06.24 13:19, Reshetova, Elena wrote:
>> On 07.06.24 16:46, Reshetova, Elena wrote:
>>>> Hi Dan,


I *want* a full coco VM reboot. But I also want the pre-reboot VM to 
provide the initial launch data for the post-reboot VM.

The typical reboot case (CoCo or not) is that a VM always starts with 
initial launch data that the VM provider provisions. That means again 
the "typical" path is that you boot with initial launch data that your 
VM provider dictates: Either explicitly (like in EC2, where we give you 
a publicly, reproducibly built OVMF binary) or implicitly through a 
selection of "known good launch data" you can choose from.

You can in theory even set up side channels from the customer to your 
provider to upload new "known good launch data". But that's complicated 
for all layers because it requires API privileges the VM may not 
otherwise require and it means you need to store and transfer that data 
across the control plane of the target launch stack.

My proposal above was to do a reboot, but instead of seeding the 
"initial launch data" from the provider, you just seed it from the 
pre-reboot environment. That way customers can reboot into any version 
of code they like and 100% own their measurements in a VM provider 
agnostic way.

Kexec comes into play because from a customer experience, the flow 
should ideally be as easy as saying "kexec me into this new firmware". I 
say kexec here because it's the closest analogy we have in Linux to 
"reboot, but with a pre-reboot provided payload". The fact that kexec 
doesn't perform a reboot today but simulates it using fancy stunts is an 
implementation detail IMHO.


Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [9] James Bottomley — 2024-06-12

On Mon, 2024-06-10 at 14:09 +0200, Alexander Graf wrote:
> On 08.06.24 16:41, James Bottomley wrote:
> > On Fri, 2024-06-07 at 18:05 +0200, Alexander Graf wrote:
[...]
> > > 1) Measurement purely based on initial launch measurements. If
> > > the full OS is inside an initramfs, we can provide

Well, yes.  This is a flexibility issue.  If you don't have a highly
privileged SVSM like entity to fix up issues and add features, you're
left with only the hardware lifecycle.

>  I
>    a) Don't think you really need to and

Most CSPs are already doing something similar to this even for non-
confidential VMs.

>    b) Believe it should come from the customer, not the cloud
> provider, as it's the highest privileged piece of code in your VM

No, the security processor firmware is the highest privilege level ...
and that doesn't come from the customer ...

The point is not that the customer should own the component and be
forced to supply it, it's that the customer should be able to inspect
it and verify the measurement corresponds to the inspected code. 
Ideally, if we get commonality of SVSMs, it becomes a singular trusted
component (like shim/grub) in the boot sequence.

> For both, the easy solution is to allow a customer to reboot into
> their own "initial launch measurement" from a currently running VM.

How, though?  The current SNP launch measurement won't change across a
kexec reboot.  If you have a mechanism that allows it to be updated
from the kernel, that will be subject to attack by a kernel exploit, so
letting a more privileged and protected entity control that seems to be
a better security model.

[...]
> > > 2) Update SVSM (or similar). Often today, you want to implement
> > > TPMs and inside a higher privileged component that is really part

In the same way that any VM kexec reboot only works if the security
processor doesn't have any vulnerabilities.  If you have a
vulnerability, either in the ASP or the SVSM you have to assess whether
it's been exploited before deciding to kexec reboot or tear down and
reinit with an updated TCB.

> If it does, you can't trust the measurement anymore and your whole 
> update path is out of the window. For CoCo, we need to make sure that

That's not possible to guarantee in practice because of potential
vulnerabilities in other code/firmware aspects of the system regardless
of whether there's an SVSM.  The point being that you *always* have
this problem regardless of whether an SVSM is present or not.

James

---

## [10] Reshetova, Elena — 2024-06-12
*Subject: RE: Confidential Computing call May 10: RTMR ABI & TEE I/O*

> Hi Elena,
> 


Thank you for clarifying this! I think I got too much into thinking of kexec
runtime update. I think this came from you originally saying that you want
to preserve the *payload of the original VM* in:

" I would like to talk about "confidential kexec" today: A kexec mechanism
that allows you to destroy the confidential VM you're in and recreate a
new one based on a payload of the old one "

And by VM payload I thought of some state in memory. 

But you just want to provide a way
for customer to supply the CoCo VM SW components (somehow, tbd details)
and have a way for customer to ask to reboot into this content. The actual
customer data is still comes from protected disk and the full attestation
process must be done for this new VM (with customer somehow
updating the new target measurement for VM in respected KBS)
 before it can get access to this disk. 

But still one question: why does this mechanism has to be from *within* the 
CoCo VM itself? Is it in order not to design CSP-specific mechanism for
doing it via some CSP-provided web interface? 

But I do like the idea in principle, we can indeed currently change only guest
kernel via kexec, but we dont have a way to do the same for virtual FW
and other potential components included in CoCo VM at least generically. 

Best Regards,
Elena.


> 
>

---

## [11] Steve Rutherford — 2024-06-12

On Wed, Jun 12, 2024 at 6:19 AM Reshetova, Elena
<elena.reshetova@intel.com> wrote:
>
>

I have the same question. This design feels like a way to side step
adding API surface by instead adding an even more inflexible kernel
ABI surface. And, on top of that, requiring an extra reboot in order
to initialize a CC VM. Why not skip that step and just initialize the
VM to the "correct" state in the first place? Interfaces like this
seem most appropriate at the CSP API level.

It also leaves me with latent questions about firmware, since this
seems to imply customer controlled firmware. Not totally sure this is
inherently problematic, but it's not something I'm excited to maintain
compatibility with.

Thanks,
--Steve


>
> But I do like the idea in principle, we can indeed currently change only guest

---
