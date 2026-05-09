---
title: '[Invitation] bi-weekly guest_memfd upstream call on 2024-11-14'
date: 2024-11-12
last_reply: 2025-01-08
message_count: 11
participants: ['David Hildenbrand', 'Chao Gao', 'Gowans, James', 'Alexey Kardashevskiy']
---

## [1] David Hildenbrand — 2024-11-12

Hi,

the next guest_memfd upstream call will happen this Thursday, 2024-11-14
at at 9:00 - 10:00am (GMT-08:00) Pacific Time - Vancouver.

We'll be using the following Google meet:
http://meet.google.com/wxp-wtju-jzw

The meeting notes are linked from the google calendar invitation. If you
want an invitation that also covers all future meetings, just write me a
mail.

In this meeting we'll discuss:
* fbind() and NUMA mempolicy for guest_memfd
* Persisting guest_memfd across reboot / guest_memfs
* guest_memfd use cases for a PFN range allocator

And we'll continue our discussion on:
* Challenges with supporting huge pages
* Challenges with shared vs. private conversion
* guest_memfd as a "library"

To put something to discuss onto the agenda, reply to this mail or add
them to the "Topics/questions for next meeting(s)" section in the
meeting notes as a comment.

--

Current upstream proposals floating around:
* mmap support + shared vs. private [1]
* preparations [2] for huge/gigantic page support [3]
* guest_memfd as a "library" to make it independent of KVM [4]
* fbind() and NUMA mempolicy for guest_memfd [5]
* Hooking into folio_put() [6]

[1] https://lkml.kernel.org/r/20241010085930.1546800-1-tabba@google.com
[2] https://lkml.kernel.org/r/cover.1728684491.git.ackerleytng@google.com
[3] https://lkml.kernel.org/r/cover.1728684491.git.ackerleytng@google.com
[4]
https://lkml.kernel.org/r/20240829-guest-memfd-lib-v2-0-b9afc1ff3656@quicinc.com
[5] 
https://lore.kernel.org/all/20241105164549.154700-1-shivankg@amd.com/T/#u
[6] https://lkml.kernel.org/r/20241108162040.159038-1-tabba@google.com

---

## [2] Chao Gao — 2024-11-13
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2024-11-14*

On Tue, Nov 12, 2024 at 01:30:06PM +0100, David Hildenbrand wrote:
>Hi,
>

Hi David,

We would like to discuss how to adapt the proposal for shared device assignment
[1] to recent guest_memfd changes, such as the support of in-place conversion.

With in-place conversion, QEMU can map shared memory and supply the virtual
address to VFIO to set up DMA mappings. From this perspective, in-place
conversion doesn't change or require any changes to the way QEMU interacts
with VFIO. So, the key for device assignment remains updating DMA mappings
accordingly during shared/private conversions. It seems that whether in-place
conversion is in use (i.e., whether shared memory is managed by guest_memfd or
not) doesn't require big changes to that proposal. Not sure if anyone thinks
otherwise. We want to align with you on the direction for device assignment
support for guest_memfd.
(I set aside the idea of letting KVM manage the IOMMU page table in the above
 analysis because we probably won't get that support in the near future)

Could you please add this topic to the agenda?

btw, the current time slot is not very convenient for us. If possible, could we
schedule the meeting one hour earlier, if this works for others? Two hours
earlier would be even better

[1]: https://lore.kernel.org/all/20240725072118.358923-1-chenyi.qiang@intel.com/

---

## [3] David Hildenbrand — 2024-11-13
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2024-11-14*

On 13.11.24 07:06, Chao Gao wrote:
> On Tue, Nov 12, 2024 at 01:30:06PM +0100, David Hildenbrand wrote:
>> Hi,

Hi!

> 
> We would like to discuss how to adapt the proposal for shared device assignment

Makes sense.

> 
> With in-place conversion, QEMU can map shared memory and supply the virtual

Right. So devices would also only be to access "shared" memory.

> 
> Could you please add this topic to the agenda?

Will do. But I'm afraid the agenda for tomorrow is pretty packed, so we 
might not get to talk about it in more detail before the meeting in 2 weeks.

> 
> btw, the current time slot is not very convenient for us. If possible, could we

Time zones and daylight saving are confusing, so I'm relying on Google 
calender; it says that the meeting is going to be at 9am pacific time, 
which ends up being 6pm German time. I suspect that's 1am in China? :( I 
know that Gavin from Australia is also not able to join unfortunately 
... something like 4am for him.

We can discuss tomorrow if we could move it to 8am pacific time (which I 
would welcome as well :) ) for the next meeting. 7am pacific time is 
likely a bit of a stretch though.

---

## [4] Chao Gao — 2024-11-14
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2024-11-14*

>> With in-place conversion, QEMU can map shared memory and supply the virtual
>> address to VFIO to set up DMA mappings. From this perspective, in-place

Yes, this is the situation without TDX-Connect support. Even when TDX-Connect
comes into play, devices will initially be attached in shared mode and later
converted to private mode. From this perspective, TDX-Connect will be built on
this shared device assignment proposal.

>
>> 

Understood. is there any QEMU patch available for in-place conversion? we would
like to play with it and also do some experiments w/ assigned devices. This
might help us identify more potential issues for discussion.

>
>> 

Yes, this meeting starts at 1am in China.

>Gavin from Australia is also not able to join unfortunately ... something
>like 4am for him.

Thanks a lot.

---

## [5] David Hildenbrand — 2024-11-27
*Subject: [Invitation] bi-weekly guest_memfd upstream call on 2024-12-05*

Hi,

due to Thanksgiving, we'll move the call to next week. As discussed in 
the last meeting, we'll start the meeting 1h earlier.

So the next guest_memfd upstream call will happen Thursday next week, 
2024-12-05 at 8:00 - 9:00am (GMT-08:00) Pacific Time - Vancouver.

We'll be using the following Google meet:
http://meet.google.com/wxp-wtju-jzw

The meeting notes can be found at [1], where we also link recordings and 
collect current guest_memfd upstream proposals. If you want an google 
calendar invitation that also covers all future meetings, just write me 
a mail.

In this meeting we'll discuss:
* Persisting guest_memfd across reboot / guest_memfs
* Shared device assignment in QEMU
* guest_memfd population overhead

And we'll continue our discussion on:
* Challenges with supporting huge pages
* Challenges with shared vs. private conversion
* guest_memfd as a "library"

To put something to discuss onto the agenda, reply to this mail or add
them to the "Topics/questions for next meeting(s)" section in the
meeting notes as a comment.

[1] 
https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?usp=sharing

---

## [6] David Hildenbrand — 2024-12-10
*Subject: [Invitation] bi-weekly guest_memfd upstream call on 2024-12-12*

Hi everybody,

as announced, we'll already have our next guest_memfd upstream call -- 
likely the last one for this year -- this Thursday, 2024-12-12 at 8:00 - 
9:00am (GMT-08:00) Pacific Time - Vancouver.

We'll be using the following Google meet:
http://meet.google.com/wxp-wtju-jzw

The meeting notes can be found at [1], where we also link recordings and
collect current guest_memfd upstream proposals. If you want an google
calendar invitation that also covers all future meetings, just write me
a mail.

The agenda of the last meetings were pretty packed, I have the feeling 
that this one could end up a bit "lighter".

In this meeting we'll likely discuss:
  * Patrick: KVM gmem MMIO access challenges and KVM_X86_SW_PROTECTED_VM
    for arm
  * Aneesh: Feasibility of 4 KiB guests on 64 KiB host
  * Persisting guest_memfd across reboot / guest_memfs (if James is around)

And we'll continue our discussion on:
  * Challenges with supporting huge pages
  * Challenges with shared vs. private conversion
  * guest_memfd as a "library"

To put something to discuss onto the agenda, reply to this mail or add
them to the "Topics/questions for next meeting(s)" section in the
meeting notes as a comment.

[1] 
https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?usp=sharing

---

## [7] Gowans, James — 2024-12-11
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2024-12-12*

On Tue, 2024-12-10 at 15:25 +0100, David Hildenbrand wrote:
> In this meeting we'll likely discuss:
>   * Patrick: KVM gmem MMIO access challenges and KVM_X86_SW_PROTECTED_VM

I should be around and will be keen to discuss this. Where we landed
last on this topic was that guestmemfs should be modified to use the
guest_memfd library code to instantiate a real guest_memfd file when a
guestmemfs file is opened. Essentially the guestmemfs persistence will
mostly be a custom allocator behind the in-development guest_memfd
library code, including the ability to restore guest_memfd mappings when
re-opening the file after kexec.

The main dependency here is on the guest_memfd library effort.
Discussion on how that's going and making sure that the guestmemfs
persistence use case is covered will be useful. 

We need to make sure that the guest_memfd library supports:
1. Defining a custom allocator other than buddy-list managed pages so
that a persistent reserved memory pool can be used.
2. Being able to re-drive or fault in mappings for a file after kexec.
In all likelihood the allocator code path and equally restore previously
allocated pages.
3. Support huge/gigantic mappings
4. Support mmaping the guest_memfd file; for non-CoCo VMs this will be
necessary for PV devices. I realise that this is a whole can of worms
currently under discussion and not specific to this use case.

So, let's socialise this revised guestmemfs approach, and next steps for
the library development.

> 
> And we'll continue our discussion on:


JG



Amazon Development Centre (South Africa) (Proprietary) Limited
29 Gogosoa Street, Observatory, Cape Town, Western Cape, 7925, South Africa
Registration Number: 2004 / 034463 / 07

---

## [8] Alexey Kardashevskiy — 2024-12-24
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2024-11-14*

On 14/11/24 13:27, Chao Gao wrote:
>>> With in-place conversion, QEMU can map shared memory and supply the virtual
>>> address to VFIO to set up DMA mappings. From this perspective, in-place


Have you found out if there are patches, somewhere? I am interested too. 
Thanks,

---

## [9] David Hildenbrand — 2024-12-24
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2024-11-14*

On 24.12.24 05:21, Alexey Kardashevskiy wrote:
> On 14/11/24 13:27, Chao Gao wrote:
>>>> With in-place conversion, QEMU can map shared memory and supply the virtual

I remember that so far only Kernel patches are available [1], I assume 
because Google focuses on other user space than QEMU. So I suspect the 
QEMU integration is still TBD.


[1] https://lkml.kernel.org/r/20241213164811.2006197-1-tabba@google.com

---

## [10] Alexey Kardashevskiy — 2024-12-27
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2024-11-14*

On 24/12/24 22:27, David Hildenbrand wrote:
> On 24.12.24 05:21, Alexey Kardashevskiy wrote:
>> On 14/11/24 13:27, Chao Gao wrote:

thanks for confirming. I saw that but could not spot the in-place 
conversion there. And I had to re-watch how pKVM actually works :)

---

## [11] David Hildenbrand — 2025-01-08
*Subject: [Invitation] bi-weekly guest_memfd upstream call on 2025-01-09*

Hi everybody,

Happy New Year! I just returned from PTO, so I'm a bit late with the 
invitation ...

We'll have our next guest_memfd upstream call tomorrow,  Thursday, 
2025-01-09 at 8:00 - 9:00am (GMT-08:00) Pacific Time - Vancouver.

We'll be using the following Google meet:
http://meet.google.com/wxp-wtju-jzw

The meeting notes can be found at [1], where we also link recordings and
collect current guest_memfd upstream proposals. If you want an google
calendar invitation that also covers all future meetings, just write me
a mail.

We don't have a lot yet on the agenda, so maybe this meeting will be 
less packed? :)

In this meeting we'll likely talk about:
  * Fuad's updated "restricted mapping" series from 2024-12-13. Hopefully
    Fuad can give us an overview :)
  * Michael's 2MN THP series (although Michael will likely not be around)

And we'll continue our discussion on:
  * Challenges with supporting huge pages
  * Challenges with shared vs. private conversion
  * guest_memfd as a "library"

To put something to discuss onto the agenda, reply to this mail or add
them to the "Topics/questions for next meeting(s)" section in the
meeting notes as a comment.

[1]
https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?usp=sharing

---
