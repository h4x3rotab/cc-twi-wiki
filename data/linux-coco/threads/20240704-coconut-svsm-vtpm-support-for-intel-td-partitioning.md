---
title: 'Coconut-SVSM - vTPM support for Intel TD Partitioning'
date: 2024-07-04
last_reply: 2024-08-19
message_count: 23
participants: ['Yao, Jiewen', 'Dionna Amalie Glaze', 'James Bottomley', 'Reshetova, Elena', 'Claudio Siqueira de Carvalho']
---

## [1] Yao, Jiewen — 2024-07-04

Hi
We posted the initial version of vTPM support for Intel TD Partitioning feature to https://github.com/intel-staging/td-partitioning-svsm/tree/svsm-tdp-vtpm.

Feature includes:
- vTPM CRB MMIO interface
- vTPM CA generation with TDX remote attestation
- vTPM Endorsement Key certificate and CA provision
- TDP L2 guest vTPM detection through TDVMCALL
- SVSM vTPM startup and measurement (SVSM version and TDVF).
- Ephemeral vTPM NVS

This is initial version and we are working on the improvement.
Any feedback is welcome!


At same time, we find a potential issue https://github.com/coconut-svsm/svsm/issues/404. If you can take a look and provide your thoughts, that would be great.

Thank you
Yao, Jiewen

---

## [2] Yao, Jiewen — 2024-08-01
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

Hi
As follow up, we have drafted the vTPM document and put to https://github.com/intel-staging/td-partitioning-svsm/blob/svsm-tdp-vtpm/Documentation/TD%20Partitioning%20based%20virtual%20TPM%20Design%20Guide%20Rev%200.5.1.pdf.
It describes the current TD Partitioning based vTPM design.

The chapter 5 described the TDVMCALL between L2 guest and L1 VMM, to detect the presence of L1 vTPM service and initial measurement.
Please let us know if you have any feedback.

Thank you
Yao, Jiewen

> -----Original Message-----
> From: Yao, Jiewen <jiewen.yao@intel.com>

---

## [3] Dionna Amalie Glaze — 2024-08-01
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

Thanks for this writeup, Jiewen. I see some parallels to the evTPM
paper but some divergences that I find a little curious.

1. The EKpub is ephemeral and fully justified by the TD quote around
it, so there is no need for an X.509 certificate from within the SVSM.
There might be some value for the platform to countersign the EKpub
with some instance information, so if anything I would only consider
the Service CA-signed EK to make sense. The evTPM paper communicates
the "EK cert" by stashing the quote that wraps the EKpub in the NVRAM
index for the EK cert (0x1c00002). Indeed the authors of the paper
already changed Keylime to verify quotes in this form.

By requiring X.509 self-signing, you are now pulling in a bunch of
unnecessary serialization code. For the CA-signed EK, you can get an
X.509 cert in response to a Concise-CSR
https://www.ietf.org/archive/id/draft-ietf-cose-cbor-encoded-cert-07.html#name-c509-certificate-signing-re
where CBOR serialization is much simpler.

2. I can appreciate the separator events for avoiding an emulation
attack, but this limits your ability to have multiple L2 VMs with
their own vTPMs to be launched at different times. It seems more
appropriate to have a parent key that  each vTPM is underneath, but
I'm not savvy enough with the available hierarchies to know if that
parenting relationship is possible. This would actually make an EKcert
make sense, since it'd be signed by this parent key of the ephemeral
L1VMM. So, not one of your listed options.

This diverges from the evTPM paper since they were targeting SEV-SNP
without nested VMs.

3. Migration isn't discussed much. Do you have a mitigation in mind to
a platform-hosted attack where a migrated VM is cloned? The null
hierarchy seeds would be the same but the VMs would evolve differently
with different traffic and then compromise their security properties.
Maybe the migration TD just accepts a single connection from the
target VM and refuses any extra connection?

4. Clarification question: §2.6 a new paragraph starts with a
reference to a "connection between them" but I'm not sure who the
parties of the "them" are. Is this the connection of the TPM quote to
the TD quote by means of the TD quote containing a hash of the EKpub?
I could also read "them" as L1 and L2.

5. Clarification question: is the presence VMCALL's response HOBs for
the TDVF to add to the hob list for inclusion in the event log so that
there is no need for SVSM to produce an event log? In this case, why
in §2.4 step 3.1 the TDVF creates an event for the SVSM version?
Wouldn't SVSM be the appropriate one to report its version? Not sure
what I missed.

I caught some spelling and grammar errors if you'd like me to send
those off list.

On Thu, Aug 1, 2024 at 3:38 PM Yao, Jiewen <jiewen.yao@intel.com> wrote:
>
> Hi

---

## [4] Yao, Jiewen — 2024-08-02
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

Hi Dionna
Appreciate your valuable feedback!

I will be out of office in next week. As such I will response in next 2 weeks.

In the meantime, please send the list of error you find if possible. We will make sure it fixed in the next version.

Thank you
Yao, Jiewen


> -----Original Message-----
> From: Dionna Amalie Glaze <dionnaglaze@google.com>

---

## [5] James Bottomley — 2024-08-02
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Thu, 2024-08-01 at 22:38 +0000, Yao, Jiewen wrote:
> Hi
> As follow up, we have drafted the vTPM document and put to

So this design follows what was in the ephemeral vTPM paper

https://dl.acm.org/doi/abs/10.1145/3627106.3627112

and is what IBM demoed at LPC.  However, the weakness in this design is
that there's no challenge for the platform attestation used in place of
the EK certificate.  We tried to argue around that because the
ephemeral EK changes on every boot and should thus mitigate any replay
concerns, but that can't extend to a stateful vTPM and we needed to
support both (and letting the attesting party provide the nonce even in
terms of the EK hash is still not good security practice).  That's why
the SVSM API includes a vTPM attestation protocol that allows the
external verifier to provide a nonce and dispenses with the EK cert
emulation protocol.

Regards,

James

---

## [6] James Bottomley — 2024-08-02
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Thu, 2024-08-01 at 22:38 +0000, Yao, Jiewen wrote:
> Hi
> As follow up, we have drafted the vTPM document and put to

Just a note for the vTPM reference implementation which, I think,
applies to both you and the current SVSM-vTPM: the reference TPM
implementation has moved to

https://github.com/TrustedComputingGroup/TPM

And the one you list (https://github.com/microsoft/ms-tpm-20-ref) is
now a stale copy that isn't being kept up to date.

Regards,

James

---

## [7] Dionna Amalie Glaze — 2024-08-02
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

More questions / comments

1.1 "Get TPM AK Cert (signed by EK)". This is something I thought for
a long time too. That's not what the EK does. The EK does not sign
anything. It's used for proving ownership of both EK and AK for
ActivateCredential to get an AKcert from a trusted CA.
What is your intended communication channel between SVSM and a CA for
this credential activation?

2.2.2 item 6, migration needs to ensure that the vTPM state is not
duplicated, which is a possible host attack by spinning up two targets
and directing migration to both. This needs to be explicitly required
for TPM security.
2.2.3 item 8 I don't think the community has fully agreed that MMIO
should be the command pathway for SVSM-based vTPM due to performance
problems. This appears to disallow an SVSM service call implementation
as an enlightenment path.
2.4 the alternate entrypoint TD_PARAM is undocumented. Please add a
footnote that this will be in a future revision to the TDX module
reference.
item 2.1 The launch parameter (TD_HOB) is currently measured to MRTD,
so how is this data communicated to SVSM if it's meant to be measured
to RTMR[0] (and be a useful measurement, presumably because it wasn't
measured to MRTD?)

2.5.2 "TPM CRB interface attack" and "TPM command attack" could use
citations for what you mean.

On Fri, Aug 2, 2024 at 8:40 AM James Bottomley
<James.Bottomley@hansenpartnership.com> wrote:
>
> On Thu, 2024-08-01 at 22:38 +0000, Yao, Jiewen wrote:

---

## [8] James Bottomley — 2024-08-02
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Fri, 2024-08-02 at 18:54 -0700, Dionna Amalie Glaze wrote:
> More questions / comments
> 

Well, that's only if you need a privacy preserving mechanism for
certifying to outside entities.  If you're acting on behalf of the
machine to the machine owner, there's no credible point to the whole
encryption EK, signing AK dance and you might as well use a signing EK.

I just published tools for allowing certification of the null seed used
by the kernel for session salting:

https://lore.kernel.org/linux-integrity/20240802202606.12767-1-James.Bottomley@HansenPartnership.com

And it uses a signing EK for similar reasons (it's long lived and there
are no privacy concerns if it acts solely for the machine owner).

> 2.2.2 item 6, migration needs to ensure that the vTPM state is not
> duplicated, which is a possible host attack by spinning up two

Well, no, for the AMD SNP SVSM an enlightened TPM interface makes the
most sense because everything else is enlightened.  

That brings me to a curious point: is the Intel TDX SVSM going to
follow the SVSM protocol interface?  because if it is, it will
naturally inherit the enlightened interface (the code will be present
in the kernel, so it only needs activating).  However, if the Intel
SVSM were going to ignore the SVSM protocol spec then it would have to
reinvent everything and the CRB interface might make more sense.

Regards,

James

---

## [9] Reshetova, Elena — 2024-08-05
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

> On Fri, 2024-08-02 at 18:54 -0700, Dionna Amalie Glaze wrote:
> > More questions / comments

I cannot speak on behalf of the Intel TDX *SVSM* implementation, but for the
Linux guest kernel there is no intention at the moment to support smth
like SVSM protocol interface. We have made an evaluation on this during
the spring. There are no usecases currently that require such new protocol
introduction on Intel TDX and it does bring additional code complexity, etc.
If anyone believes otherwise, please let me know. 

Best Regards,
Elena. 

> 
> Regards,

---

## [10] James Bottomley — 2024-08-05
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Mon, 2024-08-05 at 09:55 +0000, Reshetova, Elena wrote:
> > On Fri, 2024-08-02 at 18:54 -0700, Dionna Amalie Glaze wrote:
[...]
> > 
> > That brings me to a curious point: is the Intel TDX SVSM going to

If you reinvent the vTPM communication interface, I can see you are
able to get away without that SVSM communication component. I assume
you've done the same for other SVSM provided services like
deposit/remove memory and vcpu create/delete, but what about migration
when it comes along?  Since the high level operations will be pretty
much identical on AMD and Intel it would be very annoying to have to do
it in completely different ways (with presumably different tools).

Regards,

James

---

## [11] Reshetova, Elena — 2024-08-06
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

> On Mon, 2024-08-05 at 09:55 +0000, Reshetova, Elena wrote:
> > > On Fri, 2024-08-02 at 18:54 -0700, Dionna Amalie Glaze wrote:

The goal is exactly the opposite, i.e. don't reinvent anything, but
try to stick with exiting ways on how we have been doing things so far in
Linux. In this light SVSM is an invention to do things.


 I assume
> you've done the same for other SVSM provided services like
> deposit/remove memory and vcpu create/delete, but what about migration

Could you please give an example of where let's say we are not ok with
existing Linux ways of depositing/removing memory? Why do we need
to create a new protocol like SVSM from guest kernel for doing this?
It can be done if there is a valid usecase of course. All I am saying is that
we haven’t found any yet.

 Since the high level operations will be pretty
> much identical on AMD and Intel it would be very annoying to have to do
> it in completely different ways (with presumably different tools).

Migration is a separate story, which i dont think has any conclusion yet
or agreement in the community. We (Intel TDX) have a way to migrate
the guest without the guest assistance, so we dont have a strict requirement
to migrate out of SVSM. It remains to be seen what method(s) is to be 
selected at the end. And if svsm-based migration method is going to be
supported for intel tdx, then it needs a separate analysis to determine
what is the actual required communication between the L2 guest and
SVSM in our case and whenever the usage of the SVSM-style protocol
is necessary.  

Imo migration is one of the topics that would be great to discuss at LPC.

Best Regards,
Elena. 

> 
> Regards,

---

## [12] Claudio Siqueira de Carvalho — 2024-08-06
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Tue, 2024-08-06 at 08:21 +0000, Reshetova, Elena wrote:
> > On Mon, 2024-08-05 at 09:55 +0000, Reshetova, Elena wrote:
> > > > On Fri, 2024-08-02 at 18:54 -0700, Dionna Amalie Glaze wrote:

How will Intel attest the SVSM services provided? In addition to the core
protocol and the VTPM protocol, the SVSM spec 1.0 also define the ATTEST
protocol which can be used to get an attestation report for the SVSM services,
endorsing the supported services and their respective payloads. The payload for
the VTPM service is the SVSM-vTPM EK pub.

Regards,
Claudio

> 
>

---

## [13] James Bottomley — 2024-08-06
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Tue, 2024-08-06 at 08:21 +0000, Reshetova, Elena wrote:
> > On Mon, 2024-08-05 at 09:55 +0000, Reshetova, Elena wrote:
> > > > On Fri, 2024-08-02 at 18:54 -0700, Dionna Amalie Glaze wrote:

You want the SVSM vTPM service for its tight binding to the guest VM, I
believe ... and you want to add a CRB emulation to the SVSM that
currently doesn't exist.

>  I assume you've done the same for other SVSM provided services like
> > deposit/remove memory and vcpu create/delete, but what about

OK, I looked but couldn't find it: how do you current add and remove
memory from the SVSM if you don't communicate with it?

>  Why do we need to create a new protocol like SVSM from guest kernel
> for doing this? It can be done if there is a valid usecase of course.

Even in your model the SVSM performs services on behalf of the guest. I
think you mostly use traps and emulation instead of communication along
enlightened interfaces to get the SVSM to perform the services but one
of the historical lessons of virtualization has been that paravirt
enlightenments are useful in places (most particularly drivers).

Regards,

James


>  Since the high level operations will be pretty
> > much identical on AMD and Intel it would be very annoying to have

---

## [14] James Bottomley — 2024-08-06
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Tue, 2024-08-06 at 15:51 +0000, Claudio Siqueira de Carvalho wrote:
> On Tue, 2024-08-06 at 08:21 +0000, Reshetova, Elena wrote:
> > > On Mon, 2024-08-05 at 09:55 +0000, Reshetova, Elena wrote:

It's in the document they provided at the top of this thread.  I gave
an analysis here:

https://lore.kernel.org/all/13ea31e26a9891722748c5d6e823f77b6c8b7809.camel@HansenPartnership.com/

But basically it's the old trick of using a hash of the public EK as
the nonce for a TDX atestation report and wrapping it in an EK
certificate.  The problem is it doesn't allow the attesting agent to
supply the challenge (nonce) so it's not best practice.

Regards,

James

---

## [15] Reshetova, Elena — 2024-08-07
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

> On Tue, 2024-08-06 at 08:21 +0000, Reshetova, Elena wrote:
> > > On Mon, 2024-08-05 at 09:55 +0000, Reshetova, Elena wrote:

I will leave it to Jiewen to comment on the vTPM case, he is more 
knowledgeable on the details here. 

> >  I assume you've done the same for other SVSM provided services like
> > > deposit/remove memory and vcpu create/delete, but what about

I think we would need to define the usecase precisely first to avoid
confusion. I guess you are talking about VM guest (L2 guest in
TDX terminology) OS possibility to add/remove memory in runtime, 
aka memory hotplug, correct? We have started to look into this
recently and Linux supports this capability via different paths,
including ACPI hotplug and virtio-mem. So, the goal to enable mem
hotplug would be to make sure that relevant code paths are
working for both 1) normal TDX Linux guest (running in L1 with
no SVSM) as well for L2 guest running under SVSM,
ideally using the same code in Linux guest. And this is where our
difference in architecture comes from: we can
use the same code in both L1 and L2 to do this, instead of having
the code of style: 

if (running in L1)
   do foo;
else
   do bar;

So we can issue a single paravirt call from both L1 and L2 to do required
things, i.e. memory acceptance (TDG.MEM.PAGE.ACCEPT in TDX terms), etc.
In case the call is issued by L2 (as any TDG.*call by L2), it will generate by
default (this can be configured by L1) an L2 -> L1 exit (host/L0 is not involved,
exit is pretty cheap since we stay in secure context), L1 can inspect the args
and decide to emulate/drop/reject/do whatever it needs with this. 


> 
> >  Why do we need to create a new protocol like SVSM from guest kernel

Yes, paravirt englightments are important and no one challenges this fact.
When we run Linux as normal TDX guest (without SVSM) it is already
enlightened and using our TDG.* paravirt interface to do many things.
The core idea here is to use the *same* paravirt interface also when running in
L2 under SVSM vs. doing one more enligthment for L2 case *specifically*.
And again, I repeat, if we see usecases that require this L2 specific engligthment,
then this approach can be reconsidered. At that moment we will have 
smth concrete to go to x86 maintainers and say that we have a valid reason
to start adding additional complexity into our tdx or core x86 specific code.
We dont have any concrete usecases to justify this complexity at the moment
on TDX.

All the above is of course only given the fact that we want to support both:
Linux running in L1 (with no SVSM) and Linux in L2 with SVSM. It is an interesting
discussion question for the community what setup (or both) makes sense in the long run.
So far, we are making sure we support both.

Best Regards,
Elena.

> 
> Regards,

---

## [16] Reshetova, Elena — 2024-08-07
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

> On Tue, 2024-08-06 at 15:51 +0000, Claudio Siqueira de Carvalho wrote:
> > On Tue, 2024-08-06 at 08:21 +0000, Reshetova, Elena wrote:

As you yourself mentioned earlier, for ephemeral vTPM it is 
acceptable. Persistent vTPM has not been in scope of this current
release so the requirement to provision the nonce hasn’t been
there. Again, once Jiewen comes back from the vacation, he can
share his thoughts on how persistent vTPM can be implemented 
in the future. 

You keep pointing out the problem of the 'absent nonce': it is not
possible for attesting agent to provide a nonce to be included into
attestation report/quote and saying that we are missing an interface
from the OS guest (L2 guest) to SVSM to supply this nonce to the SVSM.
Is this correct summary? If yes, we have an exiting interface
in Linux OS to ask for the report/quote via configfs-tsm interface
where a fresh nonce (or anything you need) can be provided.
This interface can be used without modifications from
L2 guest also (with SVSM emulation support of course).
The rest is up to vTPM and SVSM design on how to plug this into
persistent vTPM architecture. 

Best Regards,
Elena.

---

## [17] James Bottomley — 2024-08-07
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Wed, 2024-08-07 at 11:28 +0000, Reshetova, Elena wrote:
> > On Tue, 2024-08-06 at 15:51 +0000, Claudio Siqueira de Carvalho
> > wrote:

Sure ... the plan was always to do ephemeral first because it's easier.
The best practice comment is what the security guys told me when I
presented the public key hash as nonce scheme.  They can't find an
actual security flaw in it, but they say it's best practice to let the
relying party supply the nonce.

> You keep pointing out the problem of the 'absent nonce': it is not
> possible for attesting agent to provide a nonce to be included into

OK, so now I'm confused again.  In order to be reliable, the vTPM
attestation report must provably come only from the SVSM.  With AMD we
can do this because the VMPL level the report was generated at is
included in the signed data, so VMPL0 proves it was from the SVSM. 
Nothing prevents the guest from generating an almost identical report
using the attestation APIs, but that report would have VMPL2 as the
reporting level proving it didn't come from the SVSM.

I thought I picked up from the slides that the equivalent Intel scheme
poisons all the RTMRs with a separator before transitioning from the
SVSM to the guest (so after generating the vTPM report)?  Which seems
to indicate that after this is done, even the SVSM can't generate
reports with SVSM provenance any more.

> This interface can be used without modifications from
> L2 guest also (with SVSM emulation support of course).

So I'm sure you can come up with a different scheme to identify an SVSM
produced report that will work after it has transitioned to the guest,
but in order to have the SVSM generate the report, you'll still have to
communicate with it (to tell it the nonce and retrieve the report).

James

---

## [18] Reshetova, Elena — 2024-08-07
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

> On Wed, 2024-08-07 at 11:28 +0000, Reshetova, Elena wrote:
> > > On Tue, 2024-08-06 at 15:51 +0000, Claudio Siqueira de Carvalho

It would work differently in case of TDX. If L2 guest asks for an attestation
report via TDG.MR.REPORT (and provides a nonce), it will generate an
L2 -> L1 exit and no report will be created at this point.
Then L1 can ask for an actual report via once again calling TDG.MR.REPORT
and it has a way to insert anything in the report data, including nonce
from the L2. 

> 
> I thought I picked up from the slides that the equivalent Intel scheme

Again, this is the current design of ephemeral vTPM. The spec doesn’t
talk about the persistent case at all. 
Above I was only trying to explain how the nonce delivery and asking
for report can work from L2 guest. How you connect it to the persistent
vTPM design needs to be defined still. 

> 
> > This interface can be used without modifications from

Yes, this is exactly what I was trying to explain - it can be done via existing
TDG.MR.REPORT call both in L2 (with L1 assistance) and in L1. 

Best Regards,
Elena.
> 
> James

---

## [19] Yao, Jiewen — 2024-08-16
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

Hi
I am back from vocation and trying to answer rest of questions.

For CRB emulation, right, it is not present today.
We added https://github.com/intel-staging/td-partitioning-svsm/blob/svsm-tdp-vtpm/kernel/src/vtpm/ptp/crb.rs.

Thank you
Yao, Jiewen

> -----Original Message-----
> From: Reshetova, Elena <elena.reshetova@intel.com>

---

## [20] Yao, Jiewen — 2024-08-16
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

Thank you very much to let us know.

Currently, we are trying to reuse what coconut-svsm does as much as possible, and only change when it is necessary.

I agree that this should be done before final production phase.
I filed an issue https://github.com/coconut-svsm/svsm/issues/440, to track this migration task.


Thank you
Yao, Jiewen

> -----Original Message-----
> From: James Bottomley <James.Bottomley@HansenPartnership.com>

---

## [21] Yao, Jiewen — 2024-08-16
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

Yes, current intel TDP vTPM design only covers ephemeral vTPM solution. It is a known limitation.

I remember we have discussed persistent vTPM before, but we defer it because of complexity.

Is there a full persistent vTPM design ready in coconut-svsm now? E.g. how to protect the vTPM persistent NVS?

Thank you
Yao, Jiewen



> -----Original Message-----
> From: Reshetova, Elena <elena.reshetova@intel.com>

---

## [22] Dionna Amalie Glaze — 2024-08-16
*Subject: Re: Coconut-SVSM - vTPM support for Intel TD Partitioning*

On Thu, Aug 15, 2024 at 8:38 PM Yao, Jiewen <jiewen.yao@intel.com> wrote:
>
> Yes, current intel TDP vTPM design only covers ephemeral vTPM solution. It is a known limitation.

The design is ongoing in the early attestation document [1]. I
honestly don't think it can fully protect mutable NVS without
significant TCB increase since avoiding monotonic counter duplication
and rollback is hard. We can certainly persist an EK and SRK on first
boot and provision a sealing key for the NVS that's released with
early attestation, but that buys you... literally nothing? over the
evTPM solution of instead releasing the persistent SRK to the evTPM on
boot with early attestation. The EK would mean a "persistent
identity", but the way that you name the key to release is still going
to be a platform-controlled aspect. You can't avoid it. So just allow
your platform to sign an ephemeral EKpub cert with x509 extensions
that include platform identity information. That's more valuable,
since then you have a persistent identity that is backed by a
platform-held secret.

The EKpub cert is expected to be "signed" by the hardware attestation
to tie it back to the TEE, so I'm not sure even persisting the EK is
good from a security perspective since the certificate would have a
really old quote with no way to challenge it again. It might not be
best practice to make an ephemeral EKpub cert unchallengable, but at
least we can't find a flaw in it.

All this said, I think early attestation releasing some kind of key to
get access to some encrypted persisted blob is a common need between
evTPM full disk encryption support and persistent vTPM. We can execute
towards a standard pstore virtual device (virtio-blk?) to import a
sealed blob, and a standard network proxy device (virtio-vsock?) to
import a wrapped SRK from a key management service that has an
attestation verification policy protecting release.

[1] https://docs.google.com/document/d/11ZsxP8jsviP3ddp9Hrn0rf6inttNw_Pbnz0psXlxlPs/edit#heading=h.7jvpsq5illyd

---

## [23] Yao, Jiewen — 2024-08-19
*Subject: RE: Coconut-SVSM - vTPM support for Intel TD Partitioning*

Thanks for the sharing Dionna.

I am reading the early attestation doc and trying to put some comment there.

Thank you
Yao, Jiewen

> -----Original Message-----
> From: Dionna Amalie Glaze <dionnaglaze@google.com>

---
