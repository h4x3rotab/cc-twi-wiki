---
title: 'Development Plan Document'
date: 2024-05-10
last_reply: 2024-05-23
message_count: 9
participants: ['Jörg Rödel', 'Reshetova, Elena', 'Carlos López', 'Jörg Rödel']
---

## [1] Jörg Rödel — 2024-05-10

Hi,

As announced in the last meeting I am sharing a development plan
document which lists the in-progress and future work items to get
COCONUT-SVSM to the envisioned point.

The list is very likely incomplete and I am sure the document still has
a lot of room for improvement to become more useful, but I share it in
this initial state to discuss it early and align everyone on what is
planned.

The starting section lists the first priniciples I apply when thinking
about design choices. All following sections list work items.

The document is on GitHub in Markdown and PDF format:

	https://github.com/joergroedel/svsm-governance/blob/dev-plan/draft-development-plan.md

	https://github.com/joergroedel/svsm-governance/blob/dev-plan/draft-development-plan.pdf

The PDF version has a TOC which I find very useful. I encourage everyone
to have a look and bring any suggestions and questions to the next SVSM
development call on May 15th.

Regards,

	Joerg

P.S.: The PDF file was created with pandoc from the Markdown file, so
      the later contains some special markup which is not compatible
      with GitHub Markdown.

---

## [2] Jörg Rödel — 2024-05-14
*Subject: Re: [svsm-devel] Development Plan Document*

On Fri, May 10, 2024 at 12:17:26PM +0200, J�rg R�del wrote:
> The document is on GitHub in Markdown and PDF format:
> 

FYI, I just updated the documents with a new added section about
proposed core code work items. There are three new items there and I
moved two over from the Sec section.

Regards,

	Joerg

---

## [3] Reshetova, Elena — 2024-05-15
*Subject: RE: [svsm-devel] Development Plan Document*

> On Fri, May 10, 2024 at 12:17:26PM +0200, Jörg Rödel wrote:
> > The document is on GitHub in Markdown and PDF format:

Hi, 

Thank you, this is a great document to have!
Some questions/comments:

1. I was surprised to see a Service VM mode (page 4), because I haven’t
realized this is being considered for Coconut-svsm. Is there more information
on the use cases behind this? I can image these usecases myself, but would
be great to know the ones you are targeting. 

2. Section 9. Cryptography support. The requirement on the isolation
is somewhat confusing. It reads like the keys or cryptographic assets would
never leave the border of the cryptographic module (even in the 
encrypted form?), which I am not sure the requirement applicable for all
usecases. I think it would be better for the start to define the *purpose*
of the cryptographic layer in coconut-svsm: is it just a set of securely implemented
algorithms to be exposed for user-space or/and kernel processes to perform needed
cryptographic functions (like we have crypto API in Linux) or a real cryptographic
service is envisioned that would be managing the keys and exposing
crypto services based on these keys? If latter, such service scope needs to be
defined/specified. 

3. "Implement or port a cryptography library to Coconut-SVSM... ". 
This is going to be tricky to get right, especially given the future aim for FIPS
certification. Implementing crypto functions from scratch correctly
is pretty difficult, so typically we tend to rely on existing libraries that have
been verified to provide adequate implementation. I would suggest here to
build a list of crypto algorithms that is envisioned to be needed (smaller list
is better and preferably taking post-quantum requirements in account) and based
on this (and other requirements) make a selection. Even well-known rust
libraries like ring last time we checked didn’t do things like proper key zerozation, etc. 
Also, any crypto solution would need a secure cryptographic RNG which is
going to be a separate problem of its own unless everyone agrees that we can
directly use x86 platform provided RNGs or use their input to seed a
cryptographic CPRNG (Linux uses ChaCha but with FIPS certification in mind
the methods defined in NIST SP 800-90A/B/C should be considered instead). 

4. Section 12.1. User-mode security FW. I guess the aim here is to create 
a Mandatory Access Control FW, right (based on the comment about SELinux)? 
This seems to go together with section 10.4 for filesystem permission model
unless there an additional Discretionary Access control is envisioned for that. 

5. Section 12.2: by double-validation you mean the case when a private page
is added twice to the CVM (reaccept in TDX terms)? 

6. section 8.1. Syscall interface. For TDX we had to be very careful
on things like syscall entry and other critical places in Linux to make sure
we cannot get a #VE event (probably the same for #VC for AMD?) in the
middle of switching between the userspace and kernel state. TDX provides some
controls to enable to protect from unwanted #VE which probably will be
useful for coconut-svsm also as a security measure.  

7. Section 8.2. The instruction decoder needs to be explicitly stress-tested/
fuzzed. We are starting to look into this problem for Linux now since we
might need to allow userspace MMIO decoding in the TDX code, so maybe
we can reuse some of that work for this one here. 

8. One item I would add is that it would be good to document and check 
that all relevant (non-dynamic and with potential security implication) inputs 
from the host/VMM are measured by the Coconut-SVSM correctly
into platform specific attestation registers. This closely relates to 10.1, but
it is not about the higher level attestation service but about how coconut-svsm
measures itself and its own assets. Ideally this should work with both vTPM
service available and without.  

9. I remember in past we discussed about ACPI tables passthrough via coconut
-SVSM and generation in the Coconut-svsm. Should this also be listed for debate
purpose as it has its own benefits and challenges? 

Best Regards,
Elena.

---

## [4] Carlos López — 2024-05-15
*Subject: Re: [svsm-devel] Development Plan Document*

Hi,

On 15/5/24 12:20, Reshetova, Elena wrote:
> 5. Section 12.2: by double-validation you mean the case when a private page
> is added twice to the CVM (reaccept in TDX terms)?

I am not familiar with TDX, but I think so, yes. It means that the same
GPA is accepted twice by the guest. This opens a window for the
hypervisor to remap the GPA to a different HPA, at least on SEV-SNP.

Best,
Carlos

---

## [5] Reshetova, Elena — 2024-05-15
*Subject: RE: [svsm-devel] Development Plan Document*

> Hi,
> 

Sure, just wanted to double check. Double acceptance of the memory
is also a problem on TDX, because it can result in the private page 
suddenly containing zeros instead of the actual data. 

Best Regards,
Elena.

---

## [6] Jörg Rödel — 2024-05-15
*Subject: Re: [svsm-devel] Development Plan Document*

Hi Elena,

Thanks for reviewing the document and your feedback. Please see my
comments below.

On Wed, May 15, 2024 at 10:20:15AM +0000, Reshetova, Elena wrote:
> 1. I was surprised to see a Service VM mode (page 4), because I haven’t
> realized this is being considered for Coconut-svsm. Is there more information

For the Service VM Mode there are no specific use-cases yet, but I think
this will change in the coming months. The mode is listed for
completeness, the main purpose is to not rule out scenarios where
COCONUT runs on hardware without support for partitioning/privilege
levels and isolation needs to be achieved through VM boundaries.

It of course adds more complexity because in those scenarios there needs
to be stronger attestation and encrypted communication between the guest
OSes and the COCONUT service VM.

> 2. Section 9. Cryptography support. The requirement on the isolation
> is somewhat confusing. It reads like the keys or cryptographic assets would

The question targeted with the above point is the one about the
execution context of crypto code. There are two options on the table:

	1) Execute it in the same address space like the calling
	   context.

	2) Implement address space separation to make sure the calling
	   context and the crypto context can not interfer with each other.

I think there are good points for both solutions and I am not bound to
any yet. Also it is probably too early to make a decision. As you
also wrote it would be helpful to have a better understanding of the
crypto requirements across services offered by the SVSM. With the
learnings from that a better decision can be made.

> 3. "Implement or port a cryptography library to Coconut-SVSM... ". 
> This is going to be tricky to get right, especially given the future aim for FIPS

tl;dr: When a FIPS-certifiable Rust-based crypto lib is available I
       happily make use of that in the COCONUT-SVSM code base. Until
       that happens I am also fine with a C-based one.

Longer answer:

This point targets a FIPS-certifiable crypto library in Rust, which is
something I like to see happening so that COCONUT-SVSM can use it. I
know it is likely a very long way to get there, but in my view that
should be the goal. I also do not necessarily see that as an effort that
needs to happen in the COCONUT project itself. Maybe us expressing the
desire for a FIPS-certifiable Rust crypto library motivates one of the
existing project to work towards that goal.

Having crypto implemented in Rust is also no blocker for other work, as
for the time being a proven C-based implementation can be used.

(Btw, it is not explicitly listed in the document, but I have the same
 opinion about the TPM implementation).

> 4. Section 12.1. User-mode security FW. I guess the aim here is to create 
> a Mandatory Access Control FW, right (based on the comment about SELinux)? 

The user-mode security framework is an addition to the file-system
permission attributes. The reference to SELinux is probably wrong, I
envision it more like something comparable to seccomp.

The aim is to limit the syscall interface for services. The TPM service
for example has not need to modify guest OS state or memory.

> 5. Section 12.2: by double-validation you mean the case when a private page
> is added twice to the CVM (reaccept in TDX terms)?

Yes, the section is about mitigating attacks based on double validation
of pages. This is specific to AMD SEV-SNP, I think Intel TDX is not
affected by these attacks, but I have to double check. On AMD it is
possible that double validation gives the host multiple pages for the
same GPA which it can exchange at will without the guest noticing. The
only mitigation is to track the validation state of every page in the
SVSM.

> 6. section 8.1. Syscall interface. For TDX we had to be very careful
> on things like syscall entry and other critical places in Linux to make sure

Yes, I like to learn more about these controls. Currently it is less
problematic because the COCONUT kernel only offers Int80 syscall entry,
but if we decide to switch to SYSCALL this becomes very relevant.

> 7. Section 8.2. The instruction decoder needs to be explicitly stress-tested/
> fuzzed. We are starting to look into this problem for Linux now since we

That would be great! Help on instruction decoder fuzzing and re-using
existing funzzing code is certainly appreciated.

> 8. One item I would add is that it would be good to document and check 
> that all relevant (non-dynamic and with potential security implication) inputs 

I am not sure I fully understand the purpose, can you elaborate a bit on
what inputs we should taken into account for early attestation? Are you
thinking about ACPI tables and the memory map here?

> 9. I remember in past we discussed about ACPI tables passthrough via coconut
> -SVSM and generation in the Coconut-svsm. Should this also be listed for debate

Yes, that is missing, thanks. I will add a point for that to the
document.

Regards,

---

## [7] Jörg Rödel — 2024-05-16
*Subject: Re: [svsm-devel] Development Plan Document*

Hi,

On Fri, May 10, 2024 at 12:17:26PM +0200, J�rg R�del wrote:
> As announced in the last meeting I am sharing a development plan
> document which lists the in-progress and future work items to get

As discussed in the last meeting, I opened a PR adding the document to
the SVSM repository. Find the PR here:

	https://github.com/coconut-svsm/svsm/pull/344

Regards,

	Joerg

---

## [8] Reshetova, Elena — 2024-05-17
*Subject: RE: [svsm-devel] Development Plan Document*

Hi Joerg, 

Thank you for the clarifications! Please see my comments inline. 

> Hi Elena,
> 

Coconut as a service VM closely relates to the concept of service TDs that
we have in TDX (for example a Migration TD is an example of a such a service TD).
However, in my understanding there was not enough general
interest in this model (due to complexities of managing separate service VM
in addition to the guest OS VM) but looks like I had a wrong impression. 

> 
> > 2. Section 9. Cryptography support. The requirement on the isolation

Right, exactly, I was trying to understand which one of these is envisioned,
but looks like it is early to decide yet. 

> I think there are good points for both solutions and I am not bound to
> any yet. Also it is probably too early to make a decision. As you

Yes, makes sense. 

> 
> Longer answer:

Ok, then yes, it is more like seccomp style mechanism indeed.

> 
> > 5. Section 12.2: by double-validation you mean the case when a private page

We are affected by a double accept albeit differently. Since every page
that is accepted by a guest starts as a zero page, host/vmm can turn any
private page into a zero page (with potential security consequences) at
any time if acceptance status for the page is not tracked. 

On AMD it is
> possible that double validation gives the host multiple pages for the
> same GPA which it can exchange at will without the guest noticing. The

Yes, anything that can affect coconut-svsm itself and which can be
security-relevant but at the same time stays stable over different boots.
Memory map is likely not stable, so i dont think we can measure it, 
Coconut-svsm just should sanitize the values. ACPI tables is a candidate.
I know that currently coconut-svsm takes very little of such inputs/configurations,
but it will probably grow in the future, so having a guidance on what configuration
must be measured or not is good to have imo.

Best Regards,
Elena.
   
> 
> > 9. I remember in past we discussed about ACPI tables passthrough via coconut

---

## [9] Jörg Rödel — 2024-05-23
*Subject: Re: [svsm-devel] Development Plan Document*

Hi Elena,

On Fri, May 17, 2024 at 10:01:01AM +0000, Reshetova, Elena wrote:
> Coconut as a service VM closely relates to the concept of service TDs that
> we have in TDX (for example a Migration TD is an example of a such a service TD).

Service VMs might be a niche use-case in the end. But since there is not
much effort needed to make them work I see no reason to not support
them.

> We are affected by a double accept albeit differently. Since every page
> that is accepted by a guest starts as a zero page, host/vmm can turn any

Okay, right. Seems like the attacks work on Intel as well, just with a
different outcome. Anyway, the mitigation should work on TDX as well.

> Yes, anything that can affect coconut-svsm itself and which can be
> security-relevant but at the same time stays stable over different boots.

We briefly touched that topic in yesterdays development call, it seems
there are diverging requirements for different platforms. Some platforms
do not want to measure any configuration data while others want to
measure at least parts of it.

Currently IGVM is used to pass any configuration data to the SVSM and
the specification requires this data to be unmeasured. So an IGVM
extension would be needed as well to pass measured configuration data.

Regards,

	Joerg

---
