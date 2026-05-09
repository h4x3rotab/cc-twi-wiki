---
title: '"Paravisor" Feature Enumeration'
date: 2026-01-05
last_reply: 2026-01-08
message_count: 17
participants: ['Dave Hansen', 'dan.j.williams@intel.com', 'Jon Lange', 'Sean Christopherson', 'Andrew Cooper', 'Edgecombe, Rick P', 'Kiryl Shutsemau']
---

## [1] Dave Hansen — 2026-01-05

First,

Jon and John gave a talk in Tokyo about feature enumeration under
paravisors:

> https://lpc.events/event/19/contributions/2188/attachments/1896/4057/05-Paravisor-Integration-with-Confidential-Services.pdf

The tl;dr for me at least was that they'd like a common and consistent
means of enumerating these features in OSes, regardless of the
environment: TDX, SEV-SNP or even ARM CCA.

I wanted to explore one corner of the solution space a bit. There was a
pretty limited audience of folks in the room. Please feel free to flesh
out the cc list with anyone I missed.

Dan Williams' first thought seemed to revolve around having some kind of
platform-independent device that could do the enumeration. Maybe a
synthetic PCI device. I'm sure Dan can chime in to fill in the details
that I missed.

I immediately just thought of CPUID. We already have a whole region of
CPUID (0x40000000) that hypervisors use to enumerate stuff to guests by
convention. It wouldn't be a large leap at all to carve out a chunk of
that so that paravisors can use it.

But the biggest barrier I see there is that our ARM friends don't have
CPUID. It seems like they _mostly_ have bit-by-bit aliases in ACPI or
DeviceTree for the x86 CPUID bits, like:

	X86_FEATURE_KVM_CLOCKSOURCE in arm,pvclock
or
	X86_FEATURE_KVM_STEAL_TIME  in arm,kvm-steal-time

As far as I can tell, these aliases are all done ad-hoc. This approach
could obviously be extended to paravisor features, but it would probably
be on the slow side to do it for each new feature.

It _seems_ like we could pick a chunk of CPUID space (say 32-bits of it)
and alias it 1:1 with some DeviceTree/ACPI property, say
"arm,paravisor-features". Kernel code would just be written to say
"check feature 13" and the arch-specific helpers would either steer that
to CPUID or DeviceTree.

Is there anything like that today that's cross-architecture and
cross-hypervisor? Is there anything stopping us from carving out a chunk
of CPUID for this purpose?

---

## [2] dan.j.williams@intel.com — 2026-01-05
*Subject: Re: "Paravisor" Feature Enumeration*

Dave Hansen wrote:
> First,
> 

More that it sounded like "just another firmware enumeration" problem,
where a platform device is one of the results along with related
firmware tables and objects.

> I immediately just thought of CPUID. We already have a whole region of
> CPUID (0x40000000) that hypervisors use to enumerate stuff to guests by

"Slow" as in standardization time?

> It _seems_ like we could pick a chunk of CPUID space (say 32-bits of it)
> and alias it 1:1 with some DeviceTree/ACPI property, say

That seems the definition of an ACPI description.

> Is there anything stopping us from carving out a chunk of CPUID for
> this purpose?

At what point does an ACPI property become a CPUID? In other words if
there is an ACPI / DeviceTree enumeration of CPU/platform capabilities
in firmware that can supsersede / extend native enumeration, does it
matter if x86 maps that to extended CPUID space and ARM maps it however
is convenient?

I have no problem with an extended CPUID concept, just trying to
understand more about the assumptions.

---

## [3] Jon Lange — 2026-01-06
*Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

It's not clear to me what advantages are gained by reflecting ACPI information into CPUID.  ACPI is already available and is usable across architectures, unlike CPUID.  What advantage is gained by replicating the information into CPUID?  Any advantage that doesn't have an equivalent on Arm just seems like it would perpetuate the cross-architecture problem and would lead right back to some other proposal that works on multiple architectures, so I'm very curious to understand how CPUID provides a meaningful advantage that doesn't invite new problems.

In the LPC session that Dave cites, Dan (I think it was Dan) threw out another suggestion: have the hypervisor driver detect the paravisor configuration using whatever is appropriate for that hypervisor architecture.  I find this to be a very attractive direction because it eliminates the need to define standards that can be supported across hypervisors (and across virtual firmware implementations), and reduces it just to a small set of concepts that can be fed into the kernel.  This could keep the enumeration out of the hands of ACPI altogether - thus no slow standards development.  Are there downsides to this approach that make it unattractive?

-Jon

-----Original Message-----
From: dan.j.williams@intel.com <dan.j.williams@intel.com> 
Sent: Monday, January 5, 2026 4:02 PM
To: Dave Hansen <dave.hansen@intel.com>; Jon Lange <jlange@microsoft.com>
Cc: Williams, Dan J <dan.j.williams@intel.com>; Sean Christopherson <seanjc@google.com>; Paolo Bonzini <pbonzini@redhat.com>; John Starks <John.Starks@microsoft.com>; Will Deacon <will@kernel.org>; Mark Rutland <mark.rutland@arm.com>; linux-coco@lists.linux.dev; LKML <linux-kernel@vger.kernel.org>; Kirill A. Shutemov <kirill.shutemov@linux.intel.com>; Edgecombe, Rick P <rick.p.edgecombe@intel.com>; Andrew Cooper <andrew.cooper3@citrix.com>
Subject: [EXTERNAL] Re: "Paravisor" Feature Enumeration

[You don't often get email from dan.j.williams@intel.com. Learn why this is important at https://aka.ms/LearnAboutSenderIdentification ]

Dave Hansen wrote:
> First,
>

More that it sounded like "just another firmware enumeration" problem, where a platform device is one of the results along with related firmware tables and objects.

> I immediately just thought of CPUID. We already have a whole region of 
> CPUID (0x40000000) that hypervisors use to enumerate stuff to guests 

"Slow" as in standardization time?

> It _seems_ like we could pick a chunk of CPUID space (say 32-bits of 
> it) and alias it 1:1 with some DeviceTree/ACPI property, say 

That seems the definition of an ACPI description.

> Is there anything stopping us from carving out a chunk of CPUID for 
> this purpose?

At what point does an ACPI property become a CPUID? In other words if there is an ACPI / DeviceTree enumeration of CPU/platform capabilities in firmware that can supsersede / extend native enumeration, does it matter if x86 maps that to extended CPUID space and ARM maps it however is convenient?

I have no problem with an extended CPUID concept, just trying to understand more about the assumptions.

---

## [4] Dave Hansen — 2026-01-05
*Subject: Re: "Paravisor" Feature Enumeration*

On 1/5/26 16:01, dan.j.williams@intel.com wrote:
> Dave Hansen wrote:
...
>> 	X86_FEATURE_KVM_CLOCKSOURCE in arm,pvclock
>> or

Yes.

...
>> Is there anything stopping us from carving out a chunk of CPUID for
>> this purpose?

The way it _seems_ to have worked until now is that KVM/x86 has led the
way by defining a CPUID bit for things like KVM_CLOCK of KVM_STEAL_TIME.
Then, the ARM folks came along and DeviceTree enumerations. Last, ACPI
came along with a way to package up all the DeviceTree enumerations into
a single table.

So, maybe that's a hack on a hack on a hack and we should just start
with ACPI this time. That would certainly make this pretty straightforward.

I'd love to hear a take from the x86/KVM folks, though.

---

## [5] Dave Hansen — 2026-01-05
*Subject: Re: "Paravisor" Feature Enumeration*

On 1/5/26 16:10, Jon Lange wrote:
> It's not clear to me what advantages are gained by reflecting ACPI
> information into CPUID.  ACPI is already available and is usable

If there is an ACPI approach that is expressive and agile enough to
convey the necessary information, then there's zero reason to replicate
it anywhere, CPUID included.

Like I said in the mail to Dan, I _think_ the current state of the art
for host=>guest enumeration involves ACPI wrapping DeviceTree properties
on ARM which mirror x86 CPUID bits.

> In the LPC session that Dave cites, Dan (I think it was Dan) threw
> out another suggestion: have the hypervisor driver detect the
I think you're saying that we'd have a fixed set of Linux-defined
features. Hypervisor drivers would set the features up. Generic,
architecture and vendor-neutral code would consume the feature enumeration.

That sounds familiar and sane to me. It's generally what we have with
the Linux-defined X86_FEATURE_* bits. Linux defines their behavior and
consumes them in generic code. x86 vendor-specific code sets them.

---

## [6] Sean Christopherson — 2026-01-05
*Subject: Re: "Paravisor" Feature Enumeration*

On Mon, Jan 05, 2026, Dave Hansen wrote:
> On 1/5/26 16:01, dan.j.williams@intel.com wrote:
> > Dave Hansen wrote:

KVM x86 is blissfully unaware of ACPI.  I believe the same goes for DeviceTree on
ARM64, but don't quote me on that.  I can't envision a world where KVM would ever
enumerate or parse ACPI, let alone make ACPI a hard requirement, so any features
that need KVM support need KVM specific uAPI and/or arch-specific enumeration.

KVM uses CPUID for *KVM-defined* PV features on x86 because KVM already advertises
support for CPUID-based features via KVM_GET_SUPPORTED_CPUID.  And KVM is handed a
userspace-defined virtual CPU module that includes virtual CPUID information
(KVM_SET_CPUID{,2}), which KVM can then use to know whether or not a feature is
enabled for a given guest.  I.e. using CPUID gets KVM all the uAPI and guest ABI
it needs for super cheap.

PV features/devices that are provided solely by the VMM are a completely different
matter.  E.g. KVM similiar has no direct knowledge of VirtIO.  There are plenty of
optimizations in KVM that exist to make VirtIO go faster, but like ACPI, KVM is
blissfully unaware of what VirtIO devices are exposed to a guest, where they reside
in the platform topology, how they are enumerated to the guest, etc.

Concretely, exactly what type of PV features are we talking about?  To me,
"Confidential Services" sounds like things that should be implemented as virtual
devices in userspace, attached via whatever bus the VMM is using (e.g. vmbus vs.
PCIe), and enumerated to the guest via whatever mechanism the VMM chooses (which
on x86 is pretty much guaranteed to be ACPI).

Trying to use CPUID for any such virtual devices will never fly in a KVM-based
setup (outside of completely private/proprietary environments).  KVM shouldn't
ever accept a patch to define a CPUID feature for something that is conceptually
a device, and Linux-as-a-guest shouldn't ever accept a patch to consume CPUID
entries defined by a VMM (even if that VMM is QEMU).

So unless we're talking about services that require specific, dedicated KVM
support, i.e. where the KVM involvement can't be abstracted in some generic way,
I don't think there's a whole lot to discuss (in a good way).

---

## [7] Andrew Cooper — 2026-01-06
*Subject: Re: "Paravisor" Feature Enumeration*

On 05/01/2026 9:42 pm, Dave Hansen wrote:
> First,
>

I agree that it seems like "just" an enumeration problem, but despite
attending the presentation and rereading the slides, I'm still not clear
on the precise scope.

Are we saying that, inside an opaque blob that a customer provides to a
CSP to run we might have:

* a paravisor and an unaware OS, or
* svsm and a fully-aware OS, or
* something in-between these two.

and we're looking a way to describe which piece of the interior stack
owns which capability/service?

If so, it can't come in from the outside; given that it's the capability
enumeration, there's a chicken/egg problem with verifying the integrity.

It seems like it needs to be produced by whatever the first code to run
is, after gathering capabilities in a vendor-specific way, and deciding
which services it wants to provide, and which to delegate.

And if so, then it definitely cannot be in CPUID because that needs to
be fixed from prior to the guest starting to run, and doesn't express
dynamic properties of the system[*]


I think the discussion would benefit greatly from having a couple of
concrete examples of data this wants to hold, and how it is to be used
at different levels of the interior software stack.

Thanks,

~Andrew

[*] Yes, I know CPUID does have some dynamic properties.  I think most
people would agree that life would be better without them.

---

## [8] Jon Lange — 2026-01-06
*Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

Andrew wrote:

> Are we saying that, inside an opaque blob that a customer provides to a CSP to run we might have:
> * a paravisor and an unaware OS, or

Here are two examples.  In both examples, the OS is running behind a paravisor but I wouldn't term it an "unaware OS".  Rather, the paravisor is present because of the set of services it provides, and it is running in paravisor mode (not SVSM mode) because the implementation benefits from taking full management responsibility for the confidential trust boundary (e.g. determination of when/how to validate/accept pages).  In such a configuration, where the paravisor has management responsibility for the confidential trust boundary, all of the enlightenments in the guest OS for managing confidentiality state must be suppressed.  The straightforward way to do this is for the paravisor to suppress the confidential VM enumeration information visible to the guest OS (the "SNP available" CPUID bit, or the "TDX active" bit, for example).

Note that this occurs out of necessity because we can't have the paravisor and the guest OS fighting over who has the right/responsibility to execute PVALIDATE, or TDG.MEM.PAGE.ACCEPT, or whatever.  The kernel today only has two concepts of its execution mode: either it is a confidential VM, in which case it takes full responsibility, or it is not a confidential VM, in which case it ignores the responsibility.  When a paravisor (not SVSM) is active, we have to operate in the second mode because the first mode would provoke precisely the conflict we're trying to avoid. 

First example: a confidential VM running under a paravisor wants to obtain an attestation report for itself to pass to a third party to vouch for the fact that it is a confidential VM.  Assume in this example that the relying party is aware of the paravisor and the paravisor's measurements, so the evidence provided in such an attestation report can successfully be verified as authentic.  In order for this to be possible, the kernel has to know that it's running in a confidential VM in a mode where attestation reports are available but where the responsibility for confidential memory state management is suppressed.  This is a third state beyond the two states described above.  This isn't just a userspace problem because access to the attestation service is mediated by a kernel-mode driver that needs to know how to configure itself (such configuration today is based on CPUID and not on ACPI).

Second example: a confidential VM running under a paravisor determines that one of the devices available to it is a TDISP device that requires the OS - not the paravisor - to perform the operations required to configure the device, to obtain and verify its attestation information, and to consent to activating the device in the TDISP RUN state.  In order for the OS to be able to execute that sequence, the device has to know that it is running as a confidential VM so it knows that TDISP configuration may be necessary.

We can quibble about whether there are better ways to accomplish these specific scenarios - for example, you could say that the availability of the attestation device should be handled by ACPI instead of CPUID and thus the firmware should take responsibility for figuring out whether it's present, and you could say that the PCI subsystem uses some additional information (possibly more ACPI information) to indicate that TDISP devices may be present.  However, these two examples are far from an exhaustive list and it's hard to imagine that we won't discover a third or fourth scenario that doesn't lend itself to bootstrapping in the firmware (and I'm even convinced that these two scenarios can neatly be handled by firmware conventions).  Defining "paravisor mode" gives us one more tool to figure out how to enable confidential services without requiring confidential management.

-Jon 

-----Original Message-----
From: Andrew Cooper <andrew.cooper3@citrix.com> 
Sent: Monday, January 5, 2026 5:45 PM
To: Dave Hansen <dave.hansen@intel.com>; Jon Lange <jlange@microsoft.com>
Cc: Andrew Cooper <andrew.cooper3@citrix.com>; Williams, Dan J <dan.j.williams@intel.com>; Sean Christopherson <seanjc@google.com>; Paolo Bonzini <pbonzini@redhat.com>; John Starks <John.Starks@microsoft.com>; Will Deacon <will@kernel.org>; Mark Rutland <mark.rutland@arm.com>; linux-coco@lists.linux.dev; LKML <linux-kernel@vger.kernel.org>; Kirill A. Shutemov <kirill.shutemov@linux.intel.com>; Edgecombe, Rick P <rick.p.edgecombe@intel.com>
Subject: [EXTERNAL] Re: "Paravisor" Feature Enumeration

On 05/01/2026 9:42 pm, Dave Hansen wrote:
> First,
>

I agree that it seems like "just" an enumeration problem, but despite attending the presentation and rereading the slides, I'm still not clear on the precise scope.

Are we saying that, inside an opaque blob that a customer provides to a CSP to run we might have:

* a paravisor and an unaware OS, or
* svsm and a fully-aware OS, or
* something in-between these two.

and we're looking a way to describe which piece of the interior stack owns which capability/service?

If so, it can't come in from the outside; given that it's the capability enumeration, there's a chicken/egg problem with verifying the integrity.

It seems like it needs to be produced by whatever the first code to run is, after gathering capabilities in a vendor-specific way, and deciding which services it wants to provide, and which to delegate.

And if so, then it definitely cannot be in CPUID because that needs to be fixed from prior to the guest starting to run, and doesn't express dynamic properties of the system[*]


I think the discussion would benefit greatly from having a couple of concrete examples of data this wants to hold, and how it is to be used at different levels of the interior software stack.

Thanks,

~Andrew

[*] Yes, I know CPUID does have some dynamic properties.� I think most people would agree that life would be better without them.

---

## [9] dan.j.williams@intel.com — 2026-01-05
*Subject: Re: "Paravisor" Feature Enumeration*

Dave Hansen wrote:
> On 1/5/26 16:01, dan.j.williams@intel.com wrote:
> > Dave Hansen wrote:

That speed problem is mitigated by the EFI/ACPI Code First process.
Linux and any other impacted implementation that want to be party to a
new mechanism just come to a public agreement on the mailing lists per
usual and ACPI Working Group acks/naks that public proposal. That
effectively gets you in the same ballpark of time as landing a new
invented Linux enumeration upstream.

There is a lag between the ack and the spec release, but the intention
is the ack means it is safe to assume a future version of the
specification will adopt the change.

---

## [10] Edgecombe, Rick P — 2026-01-06
*Subject: Re: "Paravisor" Feature Enumeration*

On Tue, 2026-01-06 at 01:44 +0000, Andrew Cooper wrote:
> I agree that it seems like "just" an enumeration problem, but despite
> attending the presentation and rereading the slides, I'm still not clear

For TDX, the guest has some control of the CPUID bits. Both via #VE
interception, and poking at the TDX module guest side interfaces to change which
CPUID leafs generate a #VE.

This is indeed a complication for "the outside". It handles some MSRs accesses
that depend on the CPUID config which it doesn't have final visibility into.

I would like to see less of that in the future. But marking off a certain range
of leafs to be handled by the paravisor/SVSM and that KVM/outside just ignores
seems better than current situation we already have at least. Not to dismiss the
other points.

---

## [11] Andrew Cooper — 2026-01-06
*Subject: Re: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

On 06/01/2026 2:12 am, Jon Lange wrote:
> Andrew wrote:
>

Thankyou - that is helpful.

So overall, we're wanting the paravisor to be able to express "You're in
a confidential VM, but you're not in charge" to the OS.

Hiding the SNP / TDX bit is of course necessary.  They have well defined
meanings which the OS cannot use when it's not in charge.

In your first example, when you say "attestation report", do you mean of
the whole encrypted VM, or only the "OS" part of it?  After all, a
paravisor could be running multiple OSes.

Whichever it is, this is clearly a service provided by the paravisor,
with some kind of API that's going to be of the from "execute
VM(M)CALL/etc with these regs".  TDISP is also CPU-initiated actions,
some of which may need a paravisor API.


What you're really describing is "just another hypervisor".  So really,
on x86, the paravisor (which does control CPUID in this scenario) ought
to hide the outer data, advertise itself at 0x4000_0000, and Linux wants
a new paravirt mode for this new kind of virtual platform, which is
probably not going to be very different from a typical KVM/XenHVM/HyperV
guest today.

Anything else, and it seems like you're just re-inventing the wheel but
a little more square.

Do you foresee a need to pass anything other than "here's a handful of
services that are available to you"?  An ACPI table might be an
approach, but this seems like it could be a leaf or two and nothing more.


There's no common enumeration scheme between different architectures,
but I'm a firm believer that things ought to be enumerated in the
typical way for the architecture/platform.  This means CPUID on x86, and
things like devicetree on ARM.  It's slightly ugly duplicating
information, but it's less ugly than shoehorning a non-typical
enumeration scheme in to an existing infrastructure.

~Andrew

---

## [12] Jon Lange — 2026-01-06
*Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

Andrew wrote:

> So overall, we're wanting the paravisor to be able to express "You're in
> a confidential VM, but you're not in charge" to the OS.

That is a great way to summarize the goal here.

> In your first example, when you say "attestation report", do you mean of
> the whole encrypted VM, or only the "OS" part of it?  After all, a

No, a paravisor can only run a single OS.  This is the key defining difference between a paravisor and a nested hypervisor.  This arises out of necessity from the confidential multi-privilege architectures that exist today; there is no architectural support for managing multiple guests.  So you can think of the paravisor as the entity that provides virtualization services to the single OS.

> What you're really describing is "just another hypervisor".  So really,
> on x86, the paravisor (which does control CPUID in this scenario) ought

This is the reason that I find it so attractive to embed this in the virtualization driver.  In the case of the Hyper-V paravisor, the paravisor exposes the same Hyper-V interface as the Hyper-V hypervisor does, including all of its synthetic CPUID leaves, synthetic MSRs, and hypercalls.  As you suggest, the OS will boot up, completely unaware that it is running in a confidential VM (because the paravisor hides SNP/TDX/RME) and at some point, when it is discovering the presence of what it thinks of as the "hypervisor", the "hypervisor" (which is the paravisor in this context) can just advertise its unique presence in its own dialect.  Hyper-V is already capable of doing this through a hypervisor feature enumeration called the "isolation configuration".  I think you are arguing the same point that I am increasingly coming to believe: the existing hypervisor interfaces are adequate to express this configuration.  In that case, the challenge before us now is how to teach the kernel that "paravisor mode" is meaningful so that state can be advertised across the system for use by those components that need to know (attestation and TDISP, in my examples).  But if this is a configuration that is enumerated by the virtualization driver, then it can't live in device tree nor in ACPI, because those are passed into the kernel and not generated by it.

> Do you foresee a need to pass anything other than "here's a handful of
> services that are available to you"?

Assuming we move past the question of "are we in paravisor mode", something that is less clear to me is how components like the attestation driver know how to consume the confidential services that exist.  A fully enlightened OS that knows that it is in charge also knows that it has direct access to all of the platform services that support confidentiality (whether it's specific SNP ABI calls, or TDG.* TDCALL leaves, or GHCB/GHCI interaction, or whatever).  But when running behind a paravisor, some of that access might be restricted, and it might not be possible for the existing drivers to work without modification.  Since none of these paravisor support services have been built yet, it's hard for me to predict what kinds of differences need to exist in these drivers between paravisor mode and fully enlightened mode - it might turn out to be none at all.  I suspect that we're going to have to just try to build something and see where the problems lie in practice, and that will information how much additional information might need to flow (which might go beyond "these services are available" to "here's how you access them").  I don't think it's too productive to conjecture any specifics now until we have code to point to, but this is a potential problem worth acknowledging.

My hope is to try to spend some time on supporting attestation with a paravisor in the next several months, but I don't know when I'll be able to set aside the time.  So somebody other than me might end up blazing the trail.

-Jon

-----Original Message-----
From: Andrew Cooper <andrew.cooper3@citrix.com> 
Sent: Tuesday, January 6, 2026 2:39 PM
To: Jon Lange <jlange@microsoft.com>; Dave Hansen <dave.hansen@intel.com>
Cc: Andrew Cooper <andrew.cooper3@citrix.com>; Williams, Dan J <dan.j.williams@intel.com>; Sean Christopherson <seanjc@google.com>; Paolo Bonzini <pbonzini@redhat.com>; John Starks <John.Starks@microsoft.com>; Will Deacon <will@kernel.org>; Mark Rutland <mark.rutland@arm.com>; linux-coco@lists.linux.dev; LKML <linux-kernel@vger.kernel.org>; Edgecombe, Rick P <rick.p.edgecombe@intel.com>
Subject: Re: [EXTERNAL] Re: "Paravisor" Feature Enumeration

On 06/01/2026 2:12 am, Jon Lange wrote:
> Andrew wrote:
>

Thankyou - that is helpful.

So overall, we're wanting the paravisor to be able to express "You're in
a confidential VM, but you're not in charge" to the OS.

Hiding the SNP / TDX bit is of course necessary.  They have well defined
meanings which the OS cannot use when it's not in charge.

In your first example, when you say "attestation report", do you mean of
the whole encrypted VM, or only the "OS" part of it?  After all, a
paravisor could be running multiple OSes.

Whichever it is, this is clearly a service provided by the paravisor,
with some kind of API that's going to be of the from "execute
VM(M)CALL/etc with these regs".  TDISP is also CPU-initiated actions,
some of which may need a paravisor API.


What you're really describing is "just another hypervisor".  So really,
on x86, the paravisor (which does control CPUID in this scenario) ought
to hide the outer data, advertise itself at 0x4000_0000, and Linux wants
a new paravirt mode for this new kind of virtual platform, which is
probably not going to be very different from a typical KVM/XenHVM/HyperV
guest today.

Anything else, and it seems like you're just re-inventing the wheel but
a little more square.

Do you foresee a need to pass anything other than "here's a handful of
services that are available to you"?  An ACPI table might be an
approach, but this seems like it could be a leaf or two and nothing more.


There's no common enumeration scheme between different architectures,
but I'm a firm believer that things ought to be enumerated in the
typical way for the architecture/platform.  This means CPUID on x86, and
things like devicetree on ARM.  It's slightly ugly duplicating
information, but it's less ugly than shoehorning a non-typical
enumeration scheme in to an existing infrastructure.

~Andrew

---

## [13] dan.j.williams@intel.com — 2026-01-06
*Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

Jon Lange wrote:
[..]
> > Do you foresee a need to pass anything other than "here's a handful of
> > services that are available to you"?

Where I get lost in this discussion is in the transition between wanting
to intercept operations like "private page acceptance" vs operations
like "guest OS is asking for an attestation report".

It sounds like the paravisor is going to hide confidential memory
management details like page-acceptance, but it is going to advertise
and intercept higher order operations like generate launch attestation
report and TDISP paths like lock device, get device report, accept/run
device.

So does this paravisor need low level intercepts via pv_ops and a
confidential memory-management model independent of TDX/SNP etc? Or,
does it only need the higher order common "services" like attestation
and TDISP.

---

## [14] Jon Lange — 2026-01-07
*Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

Dan W wrote:

> It sounds like the paravisor is going to hide confidential memory
> management details like page-acceptance, but it is going to advertise

I think that's roughly the right mental model.  The paravisor will additionally hide confidential details like MSR virtualization, I/O and MMIO handling, CPUID virtualization - all of the sorts of things that would generate #VE/#VC exceptions in a fully enlightened guest so that the guest doesn't have to worry about those, and the paravisor can provide useful functionality (like device emulation or hypervisor-type functionality) through those primitives.

> So does this paravisor need low level intercepts via pv_ops and a
> confidential memory-management model independent of TDX/SNP etc? Or,

I'm not following your question - I don't understand what you're envisioning when you describe confidential memory management independent of TDX/SNP.  It is the case that the paravisor is responsible for the confidentiality state of all memory, and therefore it will have some implementation to fulfill this responsibility.  It's natural for it to do so because its own operation has to integrate with the state of memory.  Following my earlier analogy that the paravisor acts like a nested hypervisor for a single (confidential) guest, the paravisor itself will have to implement all of the services necessary to satisfy the virtualization requirements of an unenlightened guest, which is far more than the "common services" that you mention.  Can you give some other examples of the sort of distinction you're trying to highlight?

-Jon

-----Original Message-----
From: dan.j.williams@intel.com <dan.j.williams@intel.com> 
Sent: Tuesday, January 6, 2026 5:58 PM
To: Jon Lange <jlange@microsoft.com>; Andrew Cooper <andrew.cooper3@citrix.com>; Dave Hansen <dave.hansen@intel.com>
Cc: Williams, Dan J <dan.j.williams@intel.com>; Sean Christopherson <seanjc@google.com>; Paolo Bonzini <pbonzini@redhat.com>; John Starks <John.Starks@microsoft.com>; Will Deacon <will@kernel.org>; Mark Rutland <mark.rutland@arm.com>; linux-coco@lists.linux.dev; LKML <linux-kernel@vger.kernel.org>; Edgecombe, Rick P <rick.p.edgecombe@intel.com>
Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration

Jon Lange wrote:
[..]
> > Do you foresee a need to pass anything other than "here's a handful of
> > services that are available to you"?

Where I get lost in this discussion is in the transition between wanting
to intercept operations like "private page acceptance" vs operations
like "guest OS is asking for an attestation report".

It sounds like the paravisor is going to hide confidential memory
management details like page-acceptance, but it is going to advertise
and intercept higher order operations like generate launch attestation
report and TDISP paths like lock device, get device report, accept/run
device.

So does this paravisor need low level intercepts via pv_ops and a
confidential memory-management model independent of TDX/SNP etc? Or,
does it only need the higher order common "services" like attestation
and TDISP.

---

## [15] Kiryl Shutsemau — 2026-01-07
*Subject: Re: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

On Tue, Jan 06, 2026 at 10:39:08PM +0000, Andrew Cooper wrote:
> On 06/01/2026 2:12 am, Jon Lange wrote:
> > Andrew wrote:

Hiding "TDX bit" is not necessary for TDX guest. Linux TDX guest kernel
can run both as L1 and L2 guest. Paravisor in L1 can redirect all
necessary operation to itself and it is transparent for L2.

It might be more relevant for the guest OSes which cannot be run as TDX
guest natively.

---

## [16] dan.j.williams@intel.com — 2026-01-07
*Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

Jon Lange wrote:
> Dan W wrote:
> 

Ah, anything that causes #VE/#VC helps, thanks.

> > So does this paravisor need low level intercepts via pv_ops and a
> > confidential memory-management model independent of TDX/SNP etc? Or,

So, I was trying to get to the actual ops that need to be intercepted,
and whether every operation that this paravisor wants to intercept
already has an existing indirection or what new indirections need to be
built. This probably becomes clearer when you have some time to build an
RFC, but the array of operations to touch exceeds traditional paravirt
hooks.

So, for example, paravirt ops do handle MSR virtualization:

struct pv_cpu_ops {
...
        u64 (*read_msr)(u32 msr);
        void (*write_msr)(u32 msr, u64 val);
...
};

Other operations are outside of paravirt hooks but do have generic
abstractions, like these for encrypted memory:

struct x86_guest {
        int (*enc_status_change_prepare)(unsigned long vaddr, int npages, bool enc);
        int (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
        bool (*enc_tlb_flush_required)(bool enc);
        bool (*enc_cache_flush_required)(void);
        void (*enc_kexec_begin)(void);
        void (*enc_kexec_finish)(void);
};

For attestation operations this effort would need to register its own
tsm_report interface:

tsm_report_register(...)

...and for TDISP it would probably need to register its own TSM device:

struct_group_tagged(pci_tsm_devsec_ops, devsec_ops,
	struct pci_tsm *(*lock)(struct tsm_dev *tsm_dev,
				struct pci_dev *pdev);
	void (*unlock)(struct pci_tsm *tsm);
	int (*accept)(struct pci_dev *pdev);
);

So my curiosity is whether there are other operations to capture that
are buried deeper in the arch implementations that do not have
abstractions today. Again, that is probably best addressed by an RFC
implementation.

---

## [17] Jon Lange — 2026-01-08
*Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration*

Dan, thanks for taking the time to clarify what you meant by PV.  I couldn't tell whether you were talking about paravisor functionality or paravirtualization operations, and now I get what you mean.

You wrote:

> So, I was trying to get to the actual ops that need to be intercepted, and whether
> every operation that this paravisor wants to intercept already has an existing

In the case of MSR - or anything else that's part of the core ISA - the paravisor handles this all transparently as part of its role as virtualization support - just like a hypervisor would do (again, that's part of the definition of paravisor mode).  I suspect the pv_ops structure you describe for MSR is designed to handle the abstractions around GHCB/GHCI for fully enlightened VMs, but in the case of a paravisor, the native RDMSR/WRMSR instructions work as expected so no paravirtualization is required.  In the paravisor scenario, this is true for every aspect of basic system execution.  Again, this is part of the core value of the paravisor: it just takes care of everything so the OS doesn't have to understand anything special about the confidential architecture.  To the extent that any pv_ops are required, they should just follow an existing virtualization path, because the paravisor is designed to mirror an established virtualization model.

> So my curiosity is whether there are other operations to capture that are
> buried deeper in the arch implementations that do not have abstractions

This is the big question, and I agree that we're not going to get very far until we start building real code.  In the example of attestation, I suspect that nothing special is required; the existing SNP and TDX platform services used by the OS should work transparently when running under a paravisor; SNP_GUEST_REQUEST over GHCB should behave as expected, and TDG.MR.REPORT will be intercepted and emulated by the L1, so no new convention should be required in either case.  The Arm CCA Planes architecture is not mature enough yet to be a firm basis for conjecture about how attestation report requests are managed, but I expect it to follow the same pattern as TDX and therefore should also work transparently.

The TDISP scenarios are much less clear, due in no small part to the fact that there is no code in the kernel yet to handle TDISP even for fully enlightened guests (as you are keenly aware).  As we design those interfaces for fully enlightened guests, it wouldn't be a bad idea to discuss how they would be handled in the paravisor case so we can minimize the need for pv_ops to handle the various configurations, but I don't want to predict how this unfolds until we actually have a real design for what TDISP negotiation will look like in at least one configuration.

-Jon

-----Original Message-----
From: dan.j.williams@intel.com <dan.j.williams@intel.com> 
Sent: Wednesday, January 7, 2026 10:42 AM
To: Jon Lange <jlange@microsoft.com>; dan.j.williams@intel.com; Andrew Cooper <andrew.cooper3@citrix.com>; Dave Hansen <dave.hansen@intel.com>
Cc: Sean Christopherson <seanjc@google.com>; Paolo Bonzini <pbonzini@redhat.com>; John Starks <John.Starks@microsoft.com>; Will Deacon <will@kernel.org>; Mark Rutland <mark.rutland@arm.com>; linux-coco@lists.linux.dev; LKML <linux-kernel@vger.kernel.org>; Edgecombe, Rick P <rick.p.edgecombe@intel.com>
Subject: RE: [EXTERNAL] Re: "Paravisor" Feature Enumeration

Jon Lange wrote:
> Dan W wrote:
> 

Ah, anything that causes #VE/#VC helps, thanks.

> > So does this paravisor need low level intercepts via pv_ops and a 
> > confidential memory-management model independent of TDX/SNP etc? Or, 

So, I was trying to get to the actual ops that need to be intercepted, and whether every operation that this paravisor wants to intercept already has an existing indirection or what new indirections need to be built. This probably becomes clearer when you have some time to build an RFC, but the array of operations to touch exceeds traditional paravirt hooks.

So, for example, paravirt ops do handle MSR virtualization:

struct pv_cpu_ops {
...
        u64 (*read_msr)(u32 msr);
        void (*write_msr)(u32 msr, u64 val); ...
};

Other operations are outside of paravirt hooks but do have generic abstractions, like these for encrypted memory:

struct x86_guest {
        int (*enc_status_change_prepare)(unsigned long vaddr, int npages, bool enc);
        int (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
        bool (*enc_tlb_flush_required)(bool enc);
        bool (*enc_cache_flush_required)(void);
        void (*enc_kexec_begin)(void);
        void (*enc_kexec_finish)(void);
};

For attestation operations this effort would need to register its own tsm_report interface:

tsm_report_register(...)

...and for TDISP it would probably need to register its own TSM device:

struct_group_tagged(pci_tsm_devsec_ops, devsec_ops,
	struct pci_tsm *(*lock)(struct tsm_dev *tsm_dev,
				struct pci_dev *pdev);
	void (*unlock)(struct pci_tsm *tsm);
	int (*accept)(struct pci_dev *pdev);
);

So my curiosity is whether there are other operations to capture that are buried deeper in the arch implementations that do not have abstractions today. Again, that is probably best addressed by an RFC implementation.

---
