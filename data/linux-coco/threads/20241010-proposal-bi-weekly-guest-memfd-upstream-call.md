---
title: 'Proposal: bi-weekly guest_memfd upstream call'
date: 2024-10-10
last_reply: 2024-11-15
message_count: 20
participants: ['David Hildenbrand', 'Vishal Annapurve', 'Fuad Tabba', 'Ackerley Tng', 'Sean Christopherson', 'Dan Williams', 'Michael Roth', 'Gupta, Pankaj', 'Vlastimil Babka', 'Patrick Roy', 'Suzuki K Poulose', 'Gavin Shan', 'Kalra, Ashish', 'Amit Shah']
---

## [1] David Hildenbrand — 2024-10-10

Ahoihoi,

while talking to a bunch of folks at LPC about guest_memfd, it was 
raised that there isn't really a place for people to discuss the 
development of guest_memfd on a regular basis.

There is a KVM upstream call, but guest_memfd is on its way of not being 
guest_memfd specific ("library") and there is the bi-weekly MM alignment 
call, but we're not going to hijack that meeting completely + a lot of 
guest_memfd stuff doesn't need all the MM experts ;)

So my proposal would be to have a bi-weekly meeting, to discuss ongoing 
development of guest_memfd, in particular:

(1) Organize development: (do we need 3 different implementation
     of mmap() support ? ;) )
(2) Discuss current progress and challenges
(3) Cover future ideas and directions
(4) Whatever else makes sense

Topic-wise it's relatively clear: guest_memfd extensions were one of the 
hot topics at LPC ;)

I would suggest every second Thursdays from 9:00 - 10:00am PDT (GMT-7), 
starting Thursday next week (2024-10-17).

We would be using Google Meet.


Thoughts?

---

## [2] Vishal Annapurve — 2024-10-10
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On Thu, Oct 10, 2024 at 7:11 PM David Hildenbrand <david@redhat.com> wrote:
>
> Ahoihoi,

Thanks for starting this discussion! A dedicated forum for covering
guest memfd specific topics sounds great. Suggested time slot works
for me.

Regards,
Vishal

>
> We would be using Google Meet.

---

## [3] Fuad Tabba — 2024-10-10
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On Thu, 10 Oct 2024 at 14:41, David Hildenbrand <david@redhat.com> wrote:
>
> Ahoihoi,

That works for me, thanks!

One thing to note, we're coming up to the period where the US/Europe
move away from daylight savings, but not at the same time. Just
something to keep in mind :)

Cheers,
/fuad

> --
> Cheers,

---

## [4] David Hildenbrand — 2024-10-10
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On 10.10.24 16:30, Fuad Tabba wrote:
> On Thu, 10 Oct 2024 at 14:41, David Hildenbrand <david@redhat.com> wrote:
>>

Right, I'm located in Germany, so it will be a different "late" for me. 
(see how nice I am to US people :P )

---

## [5] Ackerley Tng — 2024-10-10
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

David Hildenbrand <david@redhat.com> writes:

> Ahoihoi,
>

This time works for me as well, thank you!

>
> We would be using Google Meet.

Thanks too! Shall we use http://meet.google.com/wxp-wtju-jzw ?

And here's a calendar event if you'd like notifications:
https://calendar.google.com/calendar/event?action=TEMPLATE&tmeid=NDJvYjBha3FlMWpxdHFzMGNpNnQzZDk5cjBfMjAyNDEwMTdUMTYwMDAwWiBhY2tlcmxleXRuZ0Bnb29nbGUuY29t&tmsrc=ackerleytng%40google.com&scp=ALL

>
>

---

## [6] David Hildenbrand — 2024-10-11
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On 10.10.24 19:14, Ackerley Tng wrote:
> David Hildenbrand <david@redhat.com> writes:
> 

I assume that room cannot be joined when you are not around (e.g., using 
it right now makes me "Ask to join"). Can that be changed?

Otherwise, I think I can provide a room (Red Hat is using Google 
Mail/Meet etc.)

Thanks!

---

## [7] Sean Christopherson — 2024-10-11
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On Fri, Oct 11, 2024, David Hildenbrand wrote:
> On 10.10.24 19:14, Ackerley Tng wrote:
> > David Hildenbrand <david@redhat.com> writes:

Yeah, it can be changed.  I did it for the PUCK Meet, but I forget the exact steps :-)

> Otherwise, I think I can provide a room (Red Hat is using Google Mail/Meet
> etc.)

---

## [8] Ackerley Tng — 2024-10-11
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

David Hildenbrand <david@redhat.com> writes:

> On 10.10.24 19:14, Ackerley Tng wrote:
>> David Hildenbrand <david@redhat.com> writes:

Thanks for testing and pointing this out! My bad. I've changed the
settings to make it open to all, and tested it using my personal gmail
account.

Please let me know if it still doesn't work for anyone!

> Otherwise, I think I can provide a room (Red Hat is using Google 
> Mail/Meet etc.)

---

## [9] Dan Williams — 2024-10-11
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

David Hildenbrand wrote:
> Ahoihoi,
> 

Sounds like a great idea to me, thanks for setting this up!

---

## [10] Michael Roth — 2024-10-11
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On Thu, Oct 10, 2024 at 07:50:12PM +0530, Vishal Annapurve wrote:
> On Thu, Oct 10, 2024 at 7:11 PM David Hildenbrand <david@redhat.com> wrote:
> >

+1

Thanks David!

-Mike

> 
> Regards,

---

## [11] Gupta, Pankaj — 2024-10-12
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On 10/10/2024 3:39 PM, David Hildenbrand wrote:
> Ahoihoi,
> 

Thanks for setting this up. Want to join as well.

Best regards,
Pankaj

>

---

## [12] Vlastimil Babka — 2024-10-14
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On 10/10/24 19:14, Ackerley Tng wrote:
> David Hildenbrand <david@redhat.com> writes:
> 

works for me!

> 
> This time works for me as well, thank you!

So is it going to be this one?

> 
> And here's a calendar event if you'd like notifications:

gcal says it cannot find such event?

>>
>>

---

## [13] David Hildenbrand — 2024-10-14
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On 14.10.24 11:05, Vlastimil Babka wrote:
> On 10/10/24 19:14, Ackerley Tng wrote:
>> David Hildenbrand <david@redhat.com> writes:

I'll follow up with a proper invitation mail today or tomorrow.

> 
>>

Calender needs to be public. Let me give it a try and include it in the 
mail I'll send out (then, I can also modify/cancel the event etc. ).

---

## [14] Patrick Roy — 2024-10-15
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On Thu, 2024-10-10 at 14:39 +0100, David Hildenbrand wrote:
> Ahoihoi,
> 

Sounds like a great idea to me, I'd also like to join :)

Best, 
Patrick

---

## [15] Suzuki K Poulose — 2024-10-16
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

Hi David,


On 10/10/2024 14:39, David Hildenbrand wrote:
> Ahoihoi,
>

Thanks for setting this up, please could you count me in ?


Suzuki

IMPORTANT NOTICE: The contents of this email and any attachments are confidential and may also be privileged. If you are not the intended recipient, please notify the sender immediately and do not disclose the contents to any other person, use it for any purpose, or store or copy the information in any medium. Thank you.

---

## [16] Gavin Shan — 2024-10-16
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

Hi David,

On 10/10/24 11:39 PM, David Hildenbrand wrote:
> Ahoihoi,
> 

Thanks for organizing it. I'm intrested and please include me if there
is a invite.

Thanks,
Gavin

---

## [17] Kalra, Ashish — 2024-10-21
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On 10/10/2024 8:39 AM, David Hildenbrand wrote:
> Ahoihoi,
> 

Thanks for setting this up. Want to join as well.

Thanks, Ashish

---

## [18] Ackerley Tng — 2024-11-04
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

David Hildenbrand <david@redhat.com> writes:

> Ahoihoi,
>

We've been taking recordings of these meetings with attendees'
permission and the recordings are kind of stuck in a Google drive
now.

People interested in watching the recordings need to request access to
the meetings.

I would like to make these recordings more public and lower
administrative overheads of requesting/giving access by hosting the
videos somewhere.

Does anyone have any suggestions/preferences on a video hosting service?

Otherwise I'll default to using YouTube since that's also where LPC and
LSF/MM videos are hosted.

---

## [19] David Hildenbrand — 2024-11-14
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On 04.11.24 21:36, Ackerley Tng wrote:
> David Hildenbrand <david@redhat.com> writes:
> 

Makes sense to me, but I would like for them to only be detectable via 
link, not via the youtube search.

We could add links to the gdoc notes.

Let's discuss that today in the call real quick.

---

## [20] Amit Shah — 2024-11-15
*Subject: Re: Proposal: bi-weekly guest_memfd upstream call*

On Mon, 2024-11-04 at 20:36 +0000, Ackerley Tng wrote:
> David Hildenbrand <david@redhat.com> writes:
> 

[...]

Please add me to the meeting invite.

Thanks,
		Amit

---
