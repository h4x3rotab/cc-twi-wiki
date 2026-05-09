---
title: 'SVSM Development Call - June 12th, 2024'
date: 2024-06-11
last_reply: 2024-06-12
message_count: 5
participants: ['Claudio Siqueira de Carvalho', 'Stefano Garzarella', 'Yao, Jiewen', 'James Bottomley']
---

## [1] Claudio Siqueira de Carvalho — 2024-06-11

Hi,

I would like to add two topics to the SVSM meeting agenda:

- What does TPM locality[1] mean for the SVSM vTPM?
- Is there any SVSM boot event that we want to record in the TPM PCRs/Event log?
E.g. a SVSM configuration, the OVMF hash, etc

[1]
https://trustedcomputinggroup.org/wp-content/uploads/PC-Client-Specific-Platform-TPM-Profile-for-TPM-2p0-v1p05p_r14_pub.pdf

Thanks,
Claudio

---

## [2] Stefano Garzarella — 2024-06-12
*Subject: Re: [svsm-devel] SVSM Development Call - June 12th, 2024*

Hi Claudio,

On Tue, Jun 11, 2024 at 10:46 PM Claudio Siqueira de Carvalho
<cclaudio@ibm.com> wrote:
>
> Hi,

I won't be able to participate in today's call because I'm on my way
to Brno for DevConf, so I post a few thoughts below.

>
> - What does TPM locality[1] mean for the SVSM vTPM?

Interesting, IIUC an example could be to use different "localities"
for SVSM itself, edk2, kernel, etc.  right ?

> - Is there any SVSM boot event that we want to record in the TPM PCRs/Event log?
> E.g. a SVSM configuration, the OVMF hash, etc

Talking with Daniel, it seems that now EDK2 is self-measuring itself
in PCR0, so maybe it would be better to do this in SVSM.
So it would be nice to have SVSM measuring itself in PCR0, SVSM
measuring EDK2 in PCR0, and EDK2 stopping doing it.

Obviously SVSM and EDK2 are already measured by the SNP attestation
report, so it's not a blocking thing for now, since the guest OS can
use that mechanism to measure them.

Thanks for raising these topics!
Stefano

>
> [1]

---

## [3] Yao, Jiewen — 2024-06-12
*Subject: RE: [svsm-devel] SVSM Development Call - June 12th, 2024*

Comment below:


> -----Original Message-----
> From: Svsm-devel <svsm-devel-bounces@coconut-svsm.dev> On Behalf Of

[Jiewen] The main usage of TPM locality is to support DRTM model, but not SRTM.
I am not sure the value to support locality if we just adopt SRTM.



> 
> > - Is there any SVSM boot event that we want to record in the TPM PCRs/Event

[Jiewen] Yes. Intel is working on a patch to let SVSM measure EDK2 OVMF directly to PCR[0].
With this change, the EDK2 OVMF over SVSM will skip the PCR[0] measurement but only create event log.



> 
> Obviously SVSM and EDK2 are already measured by the SNP attestation

---

## [4] James Bottomley — 2024-06-12
*Subject: Re: SVSM Development Call - June 12th, 2024*

On Tue, 2024-06-11 at 20:46 +0000, Claudio Siqueira de Carvalho wrote:
> Hi,
> 

Well, unlike the physical TPM, which is locked to locality zero unless
you do a dynamic launch, the SVSM vTPM protocol supports any locality
(in that way it's the same as a vTPM attached to a VM).  This would
allow us to operate userspace and the kernel at different localities
meaning there could be key sealing policies that won't allow a key to
unseal in the userspace locality (i.e. kernel only).  Adding
functionality like this doesn't require the SVSM to police localities
(the kernel does it).

Policing localities is more problematic for the SVSM.  It means that
the SVSM must ensure that a particular locality request comes from a
particular trust level.  For instance in a dynamic launch, the TIS TPM
polices localities by replicating register access pages (one for each
locality) and then the chipset blocks access to some of them as the
boot continues.

The problem for the SVSM-vTPM is that it's hard to employ this type of
access sealing mechanism without an additional command and enlightening
all the OS components to use it, so unless there's a reason to reserve
a locality exclusively for the SVSM (say to unseal a provided secret
only for it) 

> - Is there any SVSM boot event that we want to record in the TPM
> PCRs/Event log?

OVMF records all the mandatory TCG measured boot events, including its
own measurement.  This, unfortunately, includes the static core root of
trust (SCRT) measurement, which is supposed to be the first entry.  We
could still add preceding SVSM measurements, but this would be a
technical spec violation.

Probably what needs to happen is that the SVSM-vTPM should be
responsible for the SCRT Measurement and OVMF should detect the
presence of the SVSM and assume it's been done.  That would give us
scope for adding the SVSM configuration to the SCRT measurement.

Regards,

James

---

## [5] James Bottomley — 2024-06-12
*Subject: Re: [svsm-devel] SVSM Development Call - June 12th, 2024*

On Wed, 2024-06-12 at 12:00 +0200, Stefano Garzarella wrote:
> Hi Claudio,
> 

Actually, that's not quite how it should work.  edk2 has a 3 phase
measurement sequence: the SEC phase which is the current static root of
trust adds a self measurement then measures PEI (actually this is a bit
of a lie: that's what the spec says EFI is supposed to do, but not what
OVMF actually does because SEC originally didn't have the cryptographic
ability to do a measurement) and hands off to it.  PEI eventually
measures DXE and hands off to it.  To keep the sequence correct, the
SVSM-vTPM should really only measure SEC before handing off to it.

What really happens is that PEI adds both the SCRT measurement and its
own measurement and then measures DXE.  I've asked several times if we
could fix this, because it really is a measured boot hole.

James

---
