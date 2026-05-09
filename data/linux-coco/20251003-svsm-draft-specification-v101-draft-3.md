---
title: 'SVSM draft specification (v1.01 draft #3)'
date: 2025-10-03
last_reply: 2025-11-12
message_count: 15
participants: ['Tom Lendacky', 'Nicolai Stange', 'Relph, Richard', 'Jon Lange', 'James Bottomley', 'Melody Wang', 'Carlos López']
---

## [1] Tom Lendacky — 2025-10-03

Attached is the next version of the draft SVSM specification with the
following changes since the previous version:

  - APIC emulation protocol added
    - Coconut-SVSM will need to be audited, as the current APIC emulation
      code does not completely match the "Alternate Injection Support"
      specification on which this protocol is based.
  - Reboot protocol added
  - Core protocol v2 update:
    - New flag to allow fallback from 2M to 4K during SVSM_CORE_PVALIDATE
      when RMPADJUST/PVALIDATE return size mismatch

Please review. If there are no or only minor comments, this draft will
become the next version of the specification.

Thanks,
Tom

---

## [2] Nicolai Stange — 2025-10-04
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

Hi Tom,

Tom Lendacky <thomas.lendacky@amd.com> writes:

> Attached is the next version of the draft SVSM specification with the
> following changes since the previous version:

there's an ongoing discussion at GH ([1]) on how a reboot should
interact with the _TPM_Init (think an emulated TPM power cycle) and that
should probably get resolved before making the spec update effective.

I'm trying my best to summarize the problem in what follows, James
(CCed) might have some additional input.

So, naively, a cold reset of the firmware, which qualifies as a reset of
what's called the "Root of Trust for Measurement" (RTM) in TCG
terminology, would require a reset of the TPM, i.e. to make it enter the
_TPM_Init state, c.f. the TCG TPM 2.0 Library v184, part 1
("Architecture"), sec. 10.2.2 ("Initialization State"). Quote: "It
should not be possible to reset the TPM without resetting the RTM. It
should not be possible to reset the RTM without resetting the TPM."

In particular, a reset of the TPM causes a reinitialization of all PCRs
to their respective default values as defined in the platform profile
(constant all-zeroes or all-ones in most cases).

At the current stage of the SVSM development, that's fine and could
easily get implemented.

However, James remarked in the course of the linked GH discussion that
establishing such semantics now would prohibit us from letting the SVSM
measure dynamic parts + configuration of itself into the TPM PCRs in the
future. IIUC, the idea is to record standard TCG events capturing the
dynamic aspects of the SVSM into the firmware's PCR-measured eventlog
(for the firmware event log c.f. [2], EFI_TCG2_PROTOCOL.GetEventLog),
which is quite appealing, because it would integrate transparently with
existing workflows and tools like `tpm2_eventlog` etc..

So assuming we do not want to preclude the implementation of something
like that in the future, the question is how to define interactions with
the new `SVSM_REBOOT_EXECUTE` protocol command.

From a high-level, AFAICT, we probably would have to
a.) Convey all or a subsequence of the eventlog to the relaunched
    firmware. If a subsequence, then that would have to contain all TCG
    event records relevant to the SVSM's self-measurements.
b.) Either do a "partial" TPM reset, making it to re-enter _TPM_Init,
    but keep some subset of PCRs (*) at their current values in case the
    full event log is conveyed, or do a full TPM reset and issue initial
    PCR extends from the SVSM corresponding to the to be conveyed log in
    case of a proper subsequence.

The "relevant log subsequence" option is technically feasible in theory,
but would require the SVSM to keep a log of its own events for the
replay at firmware relaunch. James, who entered the GH discussion with a
suggestion to hand the full log over with some mechanism resembling the
one from Linux kexec warm reboots, later on mentioned some drawbacks
with the approach of having the SVSM replay an internally stored log at
firmware relaunch, please refer to [1] for details.

I myself don't have an opinion on the topic, but as a hand-over
mechanism for the TCG event log would likely require support from the
newly proposed `SVSM_REBOOT_EXECUTE` command, I wanted to make you aware
of the pending discussion.

Thanks!

Nicolai

[1] https://github.com/coconut-svsm/svsm/pull/808#issuecomment-3361113788
[2] https://trustedcomputinggroup.org/resource/tcg-efi-protocol-specification/

(*) Which one is not clear to me yet -- the obvious candidate is PCR[0]
    and possibly some more, but there might be interactions with the
    H-CRTM semantics, which require to initialize the PCR[0] differently
    depending on whether the firmware issued a H-CRTM measurement
    sequence before invoking TPM2_Startup() or not, c.f. TCG TPM 2.0
    Library v184, part 1, ("Architecture"), sec. 32.3 ("H-CRTM before
    TPM2_Startup() and TPM2_Startup() without H-CRTM").

> Please review. If there are no or only minor comments, this draft will
> become the next version of the specification.

---

## [3] Relph, Richard — 2025-10-06
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

Nicolai,
    I disagree with the premise “that establishing such semantics now would prohibit us” from doing anything whatsoever in the future. The new Reset command has flags. It’s in a completely separate, versioned protocol that can be extended with additional commands. Though the current spec says this command will live ‘forever’, I’m OK with having the protocol specify a minimum version that would, in the future, even permit this command to be unusable.
    For now, we can mandate that the reset command does not alter or modify TPM state in any way and leave it up to the VMPL 2 guest to decide what to do.
    Alternatively, we could specify that the command reset the TPM and RTM as if it were a power off/on cycle.
    Or use one of the flag bits to differentiate between these 2 simple possibilities.
    Anything else seems like it would be unnecessarily complicated at this point in time.
Richard

> On Oct 4, 2025, at 6:19 AM, Nicolai Stange <nstange@suse.de> wrote:
>

---

## [4] Nicolai Stange — 2025-10-06
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

Hi Richard,

"Relph, Richard" <Richard.Relph@amd.com> writes:

>     I disagree with the premise “that establishing such semantics now
> would prohibit us” from doing anything whatsoever in the future. The

just to make it explicit: AFAIU, flags are insufficient for implementing
an event log handover mechanism like James proposed. What would be
needed for that is a means to pass the event log from the guest into
`SVSM_REBOOT_EXECUTE` for handover to the relaunched guest. But granted,
given the current lack of any defined mechanism for injecting such an
eventlog back into the restarted guest again, it would be quite a task
to define all that coherently protocol-wise at this point.


> It’s in a completely separate, versioned protocol that can be extended
> with additional commands. Though the current spec says this command

You mean like bumping the protocol version the day the SVSM wants to do
self-measurements into the TPM PCRs and say something along the lines of
"starting from version XY, `SVSM_REBOOT_EXECUTE` has become undefined,
please use `SVSM_REBOOT_EXECUTE_EX` instead"? Perhaps not ideal in terms
of future interoperability, but definitely fine as far as I'm concerned.


> For now, we can mandate that the reset command does not alter or
> modify TPM state in any way

The option to do nothing isn't really a good one IMO:
1.) The restarted guest would not be able to present a complete,
    verifiable event log for a remote attestation, because it's lacking
    the head part of what's been extended into the PCRs. That is, remote
    attestation of the restarted guest would be impossible (at least
    if supposed to cover the boot event log).
2.) There are potential security implications with e.g. a restarted
    "bad" guest continuing on the TPM state of a preceding "good" one.

> and leave it up to the VMPL 2 guest to decide what to do.
> Alternatively, we could specify that the command reset the TPM and

> Anything else seems like it would be unnecessarily complicated at
> this point in time.

Not for me to judge upon really, I merely wanted to give a heads-up that
there is a related discussion happening over at GH in the first place.

Thanks,

Nicolai

---

## [5] Tom Lendacky — 2025-10-06
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

On 10/4/25 06:19, Nicolai Stange wrote:
> Hi Tom,
> 

Right, the base idea of a reboot would be that everything should appear
as if the guest was re-launched.

> 
> In particular, a reset of the TPM causes a reinitialization of all PCRs

Yes.

> 
> At the current stage of the SVSM development, that's fine and could

Couldn't that be replayed by the SVSM into the TPM on "reboot?"

> 
> So assuming we do not want to preclude the implementation of something

Maybe we need a QUERY command to determine if REBOOT is possible then.
If we add/have dynamic measurements but they can't be replayed back into
the TPM to present a "fresh" boot environment, then the QUERY command
returns an indicator that REBOOT is not possible.

Thoughts?

Thanks,
Tom

> 
> Thanks!

---

## [6] Relph, Richard — 2025-10-06
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

> On Oct 6, 2025, at 11:17 AM, Nicolai Stange <nstange@suse.de> wrote:
> 

That’s my understanding of what James is proposing as well.

>> It’s in a completely separate, versioned protocol that can be extended
>> with additional commands. Though the current spec says this command

Right. Or simply add the _EX command and leave the existing “no data moved” command in place for those environments that want something more like a power off/on cycle (and backward compatibility.)

>> For now, we can mandate that the reset command does not alter or
>> modify TPM state in any way

I note that TPM is an optional component of an SVSM build at this point.
And even if it is included, not everyone using SVSM may require or even want it.
The TCG mandates a *minimum* log size of 64K. I’ve seen a claim that IBM Power systems support a 64M log! Just how much space do we want to dedicate in SVSM for preserving the log across a reset of the guest?
Finally, there’s nothing preventing a guest OS from preserving the log in coordination with the rebooted guest BIOS without any involvement from SVSM whatsoever. There are other means for transporting the log than through the SVSM.

>> and leave it up to the VMPL 2 guest to decide what to do.
>> Alternatively, we could specify that the command reset the TPM and

And I very much appreciate you summarizing that conversation for this wider list.

Thank you,
Richard

> 
> Thanks,

---

## [7] Jon Lange — 2025-10-07
*Subject: RE: [EXTERNAL] Re: SVSM draft specification (v1.01 draft #3)*

Tom said something that concerns me greatly:

> Right, the base idea of a reboot would be that everything should appear as if the guest was re-launched.

This is a great principle to state, but one that will almost certainly be unable to make correct in the way the guest expects.  Because the SVSM does not restart, any code in the SVSM that must return to the reset state must implement explicit code to do so.  We could certainly define some sort of subscription mechanism that permits each running service to be advised when a guest reboot occurs, but it's up to each service to implement it correctly.  Any service that fails to implement this correctly will violate the expectation of the guest.  If we had a bunch of existing code, it would be a lost cause to audit 100% of it and confirm that it conforms to the reboot expectations.  We have at least a fighting chance given that we have very little existing code, but declaring a requirement to new code to implement reboot correctly doesn't mean that it's reasonable - or even possible - for new code modules to do so.

On top of that, remember that one goal of the COCONUT-SVSM project is to provide cross-platform compatibility for any functionality that isn't coupled to a single architecture.  There's nothing about reboot that is inherently bound to SEV-SNP, so there will be an expectation that this can be supported on Intel TDX or Arm CCA.  Both of those architectures implement one-way extensible measurement registers, and I fully expect that in the future, the COCONUT-SVSM kernel will offer services to enable use of those measurement registers.  When such registers are used, it is impossible for the SVSM to return to a reset state because the underlying platform doesn't permit any rollback of measurement registers.  In fact, I wouldn't be surprised if AMD defines such registers in the future as well, so this may end up being a universal problem.  I don't know how to reconcile "appear as if the guest was re-launched" with one-way extensible measurements.

We are defining the reboot protocol as its own protocol, with the ability to define extensibility in any way we want.  I think we are going to be in a much better position if we define reboot this way: (a) executing reboot restarts the guest but has no effect by itself on any other SVSM state, (b) the reboot protocol is defined to offer extension points that permit other protocols to advertise whether they can participate in reboot, or whether their state persists across guest reboots, and (c) the guest must opt into service resets for the set of services that it expects to reset, which of course will be constrained by the set of services that support reset.  Such a design makes the operation of reboot entirely explicit, with no unpleasant surprises that arise because some SVSM service failed to implement reboot correctly - or failed to realize it was supposed to implement it at all.

-Jon

-----Original Message-----
From: Tom Lendacky <thomas.lendacky@amd.com> 
Sent: Monday, October 6, 2025 10:57 AM
To: Nicolai Stange <nstange@suse.de>
Cc: coconut-svsm@lists.linux.dev; linux-coco@lists.linux.dev; Jon Lange <jlange@microsoft.com>; kraxel@redhat.com; Relph, Richard <Richard.Relph@amd.com>; Rodel, Jorg <Joerg.Roedel@amd.com>; Melody Wang <huibo.wang@amd.com>; James Bottomley <James.Bottomley@HansenPartnership.com>
Subject: [EXTERNAL] Re: SVSM draft specification (v1.01 draft #3)

On 10/4/25 06:19, Nicolai Stange wrote:
> Hi Tom,
> 

Right, the base idea of a reboot would be that everything should appear as if the guest was re-launched.

> 
> In particular, a reset of the TPM causes a reinitialization of all 

Yes.

> 
> At the current stage of the SVSM development, that's fine and could 

Couldn't that be replayed by the SVSM into the TPM on "reboot?"

> 
> So assuming we do not want to preclude the implementation of something 

Maybe we need a QUERY command to determine if REBOOT is possible then.
If we add/have dynamic measurements but they can't be replayed back into the TPM to present a "fresh" boot environment, then the QUERY command returns an indicator that REBOOT is not possible.

Thoughts?

Thanks,
Tom

> 
> Thanks!

---

## [8] James Bottomley — 2025-10-06
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

On Mon, 2025-10-06 at 12:56 -0500, Tom Lendacky wrote:
> On 10/4/25 06:19, Nicolai Stange wrote:
> > Hi Tom,

In Linux we have kexec reboot, which doesn't reset the TPM, it merely
carries the logs across without resetting the PCRs, even though the
guest gets relaunched.

> > In particular, a reset of the TPM causes a reinitialization of all
> > PCRs to their respective default values as defined in the platform

This was discussed in the referenced issue.  What I said then was:

---
In theory, yes, but it depends on the mechanism.  What we'd discussed
before was making OVMF responsible for the SVSM measurement log, so we
could simply do additional TCG measurements into standard PCRs and they
would automatically be part of remote verification and the SVSM
wouldn't need to keep the log.  Now we'd actually have to keep that log
inside the SVSM as well to do the replay.

There's also a security point: just in time measurements into a non-
repudiable store have well known and hard to influence properties i.e.
very little attack surface.  If we do the above the security properties
alter (the initial measurements are potentially no longer just in time,
so the auditability becomes more suspect) and the SVSM log store itself
now becomes part of the attack surface, which is quite a huge
expansion.
---

I really think the kexec model where the TPM PCRs don't reset and the
log carries over is the correct one.  And, as Jon pointed out, it would
also work in RTMR environments which can't be reset without a full VM
reboot anyway.

Regards,

James

---

## [9] Tom Lendacky — 2025-10-07
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

On 10/6/25 21:59, James Bottomley wrote:
> On Mon, 2025-10-06 at 12:56 -0500, Tom Lendacky wrote:
>> On 10/4/25 06:19, Nicolai Stange wrote:

I really don't want to delay the release of the next version of the SVSM
spec. While this is all being discussed and worked out, I'll just remove
the the Reboot protocol at this point so that the Core protocol update,
vTPM protocol update and the new APIC emulation protocol and UEFI MM
protocol can get finalized and published.

Thanks,
Tom

> 
> Regards,

---

## [10] Relph, Richard — 2025-10-07
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

All,
  After chatting with Tom some, I’d like to restate the issues as I see them.
  My background is deeply embedded systems, notably in this context, PSP FW for the various flavors of SEV through the Genoa generation, and this is my first foray in to writing code for Linux, EDK2, or SVSM. And in Rust. So I claim ZERO expertise here.

   I was asked to enhance SVSM with a capability to “reboot” the VMPL 2 guest, without exiting QEMU, and without relying on kexec(). We discussed this, briefly, in some Coconut-SVSM meetings in the April and May time frame.

   For purposes of this work, and this discussion, I make the following assumptions about the use case for a reboot command:
   The reason for not wanting to exit QEMU is to maintain control of the resources allocated to QEMU… vCPUs, memory, what have you. Exiting QEMU would release those resources and who knows what might happen if that happens. Plus, of course, the time to re-acquire all the desired resources upon restarting QEMU would add, potentially significantly, to reboot time.
   The reason for not wanting to use kexec() could be to change some setting in the BIOS or boot a different OS.

    Exiting - for any reason - and re-starting QEMU would reset QEMU's vTPM. QEMU’s vTPM state can be persisted across reboots in a host file, but the vTPM itself undergoes something like a HW TPM’s power on reset each time QEMU starts. I don’t know how SVSM’s vTPM implementation models a persistent vTPM, though I assume it can. QEMU also offers the ability to NOT persist its vTPM across QEMU invocations. And however SVSM’s vTPM models a persistent vTPM, it, like a HW TPM, must be able to survive an asynchronous power cycle, even of the host. So providing a REBOOT mechanism in SVSM that also resets the vTPM, whether persistent or not, is definitely “in scope” as I see it. Whatever other REBOOT modes might be desired, this one seems necessary to me.

    If you disagree, please help me understand what I’m missing.

    The draft 1.01 spec comprehends something like this behavior. It doesn’t say what happens to guest state, including the vTPM, when a REBOOT_EXECUTE command is sent. I agree that needs to be clarified. The intent is that the system state be whatever it would be if the system-wide reset line had been asserted.

   James has put forth another reboot mode… one that, as I understand it, propagates the vTPM event log from Linux, through SVSM, to OVMF, offering kexec()-like functionality in terms of vTPM log maintenance. But kexec() doesn’t go through SVSM or OVMF at all. While I see some value in doing this, it seems to me a significantly different behavior than the reboot I described above. And more importantly, it seems a much larger task, since - AFAIK - EDK2/OVMF has no notion of accepting a TPM event log. Getting that community to buy in to the need and then put forth the resources to specify and implement this seems a long shot to me.

   Given the value that some customers see in an SVSM-based reboot facility along the lines of a power cycle, I think it’s important to not delay the reboot facility until all the other spec-level features for vTPM event log propagation are in place. When those other dependencies are sufficiently resolved, we can extend the reboot protocol spec to include a new command.

   As for how code in SVSM, outside the reboot protocol code, gets ‘reset’, I think that is an implementation detail that need not delay the specification.

   Tom and I discussed augmenting the spec to include a reboot query capability so the VMPL 2 guest can discover what kinds of reboot, if any, are supported. I’m fine with that.

Richard

---

## [11] Melody Wang — 2025-11-02
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

Hi Tom,

In the section 9.1 SVSM_APIC_QUERY_FEATURES call,

"The APIC emulation supports the following APIC registers:"

The Destination Format Register (DFR) is also mentioned in the Alternate 
Injection spec from Jon Lange.

However, the DFR and the LDR both are not implemented in the SVSM code 
now, so the question is : should we remove the DFR and LDR from the spec 
or should we implement these two registers in the SVSM?

On 10/3/25 9:01 AM, Tom Lendacky wrote:
> Attached is the next version of the draft SVSM specification with the
> following changes since the previous version:

---

## [12] Melody Wang — 2025-11-04
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

Hi Tom,

The Destination Format Register (DFR) is no longer needed and is not 
supported in X2APIC, so that answers my question.

The question still remains open is that whether LDR should be supported 
in the SVSM.

Thanks,
Melody

On 11/2/25 6:28 PM, Melody Wang wrote:
> Hi Tom,
>

---

## [13] Melody Wang — 2025-11-05
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

Sorry the last email was not sent to the mailing list, resend this email 
to fix it.

Hi Jon,

As mentioned in my previous two emails, the DFR is no longer needed and 
isn’t supported in X2APIC. Should we remove the DFR from the Alternate 
Injection spec?

Also, the LDR isn’t currently implemented in the SVSM. Should we plan to 
add it, or remove it from the spec as well?

Thanks,
Melody

On 11/5/25 5:07 PM, Wang, Huibo wrote:
> 
> Hi Jon,

---

## [14] Jon Lange — 2025-11-07
*Subject: RE: [EXTERNAL] Re: SVSM draft specification (v1.01 draft #3)*

I agree that we should remove the DFR since it is not supported in X2 mode.

We should probably implement LDR.  Each emulated APIC knows what its logical destination ID is (it has to do this to handle IPIs correctly) and therefore it can supply the correct value of LDR.  This is certainly more secure for the guest OS than having the guest OS rely on getting the correct ID from the untrusted host.

-Jon

-----Original Message-----
From: Melody Wang <huibo.wang@amd.com> 
Sent: Wednesday, November 5, 2025 7:40 PM
To: Lendacky, Thomas <Thomas.Lendacky@amd.com>; coconut-svsm@lists.linux.dev; linux-coco@lists.linux.dev; Jon Lange <jlange@microsoft.com>
Cc: kraxel@redhat.com; Relph, Richard <Richard.Relph@amd.com>; Rodel, Jorg <Joerg.Roedel@amd.com>
Subject: [EXTERNAL] Re: SVSM draft specification (v1.01 draft #3)

Sorry the last email was not sent to the mailing list, resend this email to fix it.

Hi Jon,

As mentioned in my previous two emails, the DFR is no longer needed and isn’t supported in X2APIC. Should we remove the DFR from the Alternate Injection spec?

Also, the LDR isn’t currently implemented in the SVSM. Should we plan to add it, or remove it from the spec as well?

Thanks,
Melody

On 11/5/25 5:07 PM, Wang, Huibo wrote:
> 
> Hi Jon,

--
Thanks,
Melody

---

## [15] Carlos López — 2025-11-12
*Subject: Re: SVSM draft specification (v1.01 draft #3)*

Hi,

On 10/3/25 6:01 PM, Tom Lendacky wrote:
> Attached is the next version of the draft SVSM specification with the
> following changes since the previous version:

Just one small comment on the APIC protocol, related to PR #850 [0]: the
section for SVSM_APIC_WRITE_REGISTER states the behavior for invalid
register addresses, but not for invalid values (e.g. an unsupported
delivery mode in ICR in the case of that PR). I think this should be
explicitly stated, and more precisely, I would suggest explaining
whether the value of that register is changed or not if the write is
rejected (I would assume it is not).

Thanks,
Carlos

[0] https://github.com/coconut-svsm/svsm/pull/850

---
