---
title: '[RFC PATCH v2 4/4] tsm: Allow for extending and reading\n configured RTMRs'
date: 2024-05-10
last_reply: 2024-08-20
message_count: 8
participants: ['James Bottomley', 'Samuel Ortiz', 'Xing, Cedric', 'Qinkun Bao']
---

## [1] James Bottomley — 2024-05-10

I'm not really sure where to hang this, since there's no posted agenda
or materials for the CCC meeting today.  I'm afraid I also don't have a
copy of the presentation to point people who weren't at the meeting to.
However, it struck me you missed a third option: use the ima log
format.  This has the advantage that we can define additional events
and have them published with a kernel patch (the IMA log format is
defined in the kernel).  Thanks to the TCG, it's also CEL compatible
but doesn't require any sort of TCG blessing of the events.  Plus we
also have existing kernel infrastructure to log to that format.

Regards,

James

---

## [2] Samuel Ortiz — 2024-05-13

On Fri, May 10, 2024 at 10:57:37PM -0400, James Bottomley wrote:
> I'm not really sure where to hang this, since there's no posted agenda
> or materials for the CCC meeting today.

The agenda was posted on the linux-coco ml [1]. I sent a link to the
presentation slides [2] to the thread.

> However, it struck me you missed a third option: use the ima log
> format.  This has the advantage that we can define additional events

That's an interesting idea. It may avoid having to extend the CEL spec
with a new Content Type, but otoh the current spec defines which IMA
events are supported. So adding new ones may require to also eventually
extend the spec. But I guess since IMA is a Linux kernel subsystem,
changing the kernel code and ABI would de-facto extend the TCG CEL IMA
spec.

Here I assume you're talking about the IMA_TEMPLATE CEL specified
format, which is designed to accomodate for the current kernel IMA log
format. The main drawback of this format is that the digest does not
include the whole content event, making the CEL content type, the IMA
tag name and both lengths (for the content event and the IMA content)
untrusted for event log verifiers.

CEL defines another IMA format (IMA_TLV), that hashes the whole event
content. I think we should at least use that format as our output ABI,
if we want to use a TCG specified IMA content type.

Cheers,
Samuel.

[1] https://lore.kernel.org/linux-coco/61b65115-5945-4e27-89e4-bb6cba657f7f@linux.intel.com/
[2] https://docs.google.com/presentation/d/1qMk-8TiMigVmVAEDWXqPu9Jd7OJ8AGvCR34Lp2WunhU/edit?usp=sharing

> Regards,
>

---

## [3] James Bottomley — 2024-05-13

On Mon, 2024-05-13 at 12:16 +0200, Samuel Ortiz wrote:
> On Fri, May 10, 2024 at 10:57:37PM -0400, James Bottomley wrote:
> > I'm not really sure where to hang this, since there's no posted

That's great, thanks.

> > However, it struck me you missed a third option: use the ima log
> > format.  This has the advantage that we can define additional

That's what I was assuming since the TCG is currently deferring to IMA
in that regard.

> Here I assume you're talking about the IMA_TEMPLATE CEL specified
> format, which is designed to accomodate for the current kernel IMA

That's only because IMA doesn't yet have such an event.  If we're
assuming effectively designing an IMA log format for non repudiation of
external events, one can be added.  Although I wouldn't want to be
hasty: one of the big problems of all options is that no existing log
format really covers the measure container use case and we're not
completely sure what other use cases will arise (the firewall rules
measurements was one that regulated cloud providers seem to think would
be important ... and that has a periodic rush of events, but there will
be others).

However, the current IMA templates (event descriptions) are known by an
ASCII prefix (they all begin ima-):

https://docs.kernel.org/security/IMA-templates.html#supported-template-fields-and-descriptors

So it would be easy to add more with a non ima- prefix.  Note that this
doc is out of date an IMA does support hashes all the way to SHA256
although SHA384 isn't currently listed.

The current record fields are defined in

security/integrity/ima/ima_template.c

> CEL defines another IMA format (IMA_TLV), that hashes the whole event
> content. I think we should at least use that format as our output

Possibly.  Although avoiding double hashing may be a useful performance
measure (not really sure how fast records will come in yet).

James

---

## [4] Samuel Ortiz — 2024-05-14

On Mon, May 13, 2024 at 08:03:53AM -0600, James Bottomley wrote:
> On Mon, 2024-05-13 at 12:16 +0200, Samuel Ortiz wrote:
> > > However, it struck me you missed a third option: use the ima log

If we were to follow the IMA_TEMPLATE format as our output RTMR ABI for
the event log, adding one or more IMA events would not change the fact
that the event and content type would not be hashed into the extended
digest. Unless we want to specify a different behaviour for each IMA
event, and then verifiers would have interpret the digest construction
differently depending on the IMA_TEMPLATE nested event type. And that's
not pretty IMHO.

Using the IMA_TLV content type would make that cut cleaner at least. A
digest is built on the whole content event, for all event types. And the
content and event types are trusted, i.e. the verifier can securely map
events to the reported event types.

> Although I wouldn't want to be
> hasty: one of the big problems of all options is that no existing log

Right. A new CEL content type would give us more freedom in that regard,
as it would allow us to define our own event content value in a more
flexible way. Instead of the nested TLV approach that IMA_TLV follows,
having one where the T would be a max length string defining the creator
of the event (a.k.a. the attester), would avoid having to formally
define each and every new event. That's where option #2 in the
presentation was heading to.

Cheers,
Samuel.
>

---

## [5] Xing, Cedric — 2024-05-16

On 5/13/2024 10:08 PM, Samuel Ortiz wrote:
> On Mon, May 13, 2024 at 08:03:53AM -0600, James Bottomley wrote:
>> On Mon, 2024-05-13 at 12:16 +0200, Samuel Ortiz wrote:
Agreed. This misses the design objective of separating storage from 
semantics of event records.

> Using the IMA_TLV content type would make that cut cleaner at least. A
> digest is built on the whole content event, for all event types. And the
The numerical T would need to be allocated/tracked by a central 
registry. This won't work for applications designed/developed outside of 
the kernel community, as they won't have a reliable way to avoid 
conflicts with each other. Thus, T needs to be a string, but that 
violates IMA_TLV definition. This is kinda fitting a square peg into a 
round hole IMHO.

>> Although I wouldn't want to be
>> hasty: one of the big problems of all options is that no existing log
Agreed. In fact, the 2 primary design objectives of this event log are 
(1) to separate storage from semantics of event records and (2) to allow 
applications to define custom events and avoid conflicts with each other 
reliably. IMA_TLV meets the 1st objective but misses the 2nd; while 
IMA_TEMPLATE meets the 2nd but misses the 1st. And that's how we came to 
this Option #2.

-Cedric

---

## [6] Qinkun Bao — 2024-08-19
*Subject: Re: [RFC PATCH v2 0/4] tsm: Runtime measurement registers ABI*

A gentle ping on this email thread. We have tested the patch series [1] and will release a product based on the patch series. 

If the patch series can not get upstreamed, the whole confidential computing community can not have a way to measure the workload with RTMRs. Without the patch, RTMR3 is completely unused. The patch works perfectly for our usage case (Like the existing TPM ABI, the raw measurement is taken instead of recording the log entry.). Assuming RTMR serves as an alternative to TPM-based measurement, migrating existing software to the RTMR could be greatly simplified by developing an ABI that resembles the TPM.

I don’t object to having an ABI to take the log entry. For our usage case, we use the Canonical event log [2] to measure the workload. I do think that we should NOT block the patch series for several months to solve an issue that TPM can not solve. 

Link:
[1] https://lore.kernel.org/lkml/20240128212532.2754325-1-sameo@rivosinc.com/
[2] https://trustedcomputinggroup.org/resource/canonical-event-log-format/

---

## [7] Samuel Ortiz — 2024-08-20
*Subject: Re: [RFC PATCH v2 0/4] tsm: Runtime measurement registers ABI*

Qinkun,

I am working on a adding a patch that generates and exports a CEL, but
this takes longer than I was hoping for, mostly due to a lack of
bandwidth on my side. I will send a PoC for this as soon as I can, and
folks can improve it from there.

Cheers,
Samuel.

On Mon, Aug 19, 2024 at 02:25:15PM -0700, Qinkun Bao wrote:
> A gentle ping on this email thread. We have tested the patch series [1] and will release a product based on the patch series. 
>

---

## [8] Qinkun Bao — 2024-08-20
*Subject: Re: [RFC PATCH v2 0/4] tsm: Runtime measurement registers ABI*

Samuel,

Sounds great, thanks for the helpful information! I am looking forward to the
new patch.

Thanks,
Qinkun


On Tue, Aug 20, 2024 at 6:19 AM Samuel Ortiz <sameo@rivosinc.com> wrote:
>
> Qinkun,

---
