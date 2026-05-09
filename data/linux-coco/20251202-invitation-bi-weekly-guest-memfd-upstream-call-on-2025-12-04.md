---
title: '[Invitation] bi-weekly guest_memfd upstream call on 2025-12-04'
date: 2025-12-02
last_reply: 2026-01-07
message_count: 3
participants: ['David Hildenbrand (Red Hat)', 'dan.j.williams@intel.com']
---

## [1] David Hildenbrand (Red Hat) — 2025-12-02

Hi,

Our next guest_memfd upstream call is scheduled for Thursday,
2025-12-04 at 8:00 - 9:00am (GMT-08:00) Pacific Time - Vancouver.

We'll be using the following Google meet:
http://meet.google.com/wxp-wtju-jzw

The meeting notes can be found at [1], where we also link recordings and
collect current guest_memfd upstream proposals. If you want an google
calendar invitation that also covers all future meetings, just write me
a mail.

In this meeting, we'll have Ackerley continue giving us an overview of
work-in-progress HugeTLB support and discuss whatever comes up.

To put something to discuss onto the agenda, reply to this mail or add
them to the "Topics/questions for next meeting(s)" section in the
meeting notes as a comment.


This might be the last meeting this year: I will be traveling for LPC on 
December 11 and December 18. Then, Christmas is already around the 
corner and we'll skip the one on December 25. So we'll probably have our 
next meeting then on January 8.

[1]
https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?usp=sharing

---

## [2] dan.j.williams@intel.com — 2026-01-07
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2025-12-04*

David Hildenbrand (Red Hat) wrote:
[..]
> This might be the last meeting this year: I will be traveling for LPC on 
> December 11 and December 18. Then, Christmas is already around the 

Hi David,

Great seeing you at LPC! Can I grab some time on the agenda to
brainstorm the next level of detail on the topic I briefly ran by you in
the hallway track? I.e. is there a path to decouple dependencies and
land some of the low level huge page support upstream while the
guest_memfd reworks for in place conversion and hugetlbfs backing
continue to mature?

As you said this at a minimum needs to be crippled / not production
worthy to maintain focus and momentum on the guest_memfd rework
completion. The observation that shifted my thinking is that, given the
timelines and remaining work, there are solid steps that the low level
implementations can be landing and maturing in advance of that
integration. All net progress for upstream.

---

## [3] David Hildenbrand (Red Hat) — 2026-01-07
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2025-12-04*

On 1/7/26 21:42, dan.j.williams@intel.com wrote:
> David Hildenbrand (Red Hat) wrote:
> [..]

Hi Dan!

> 
> Great seeing you at LPC! 

Absolutely :)

> Can I grab some time on the agenda to
> brainstorm the next level of detail on the topic I briefly ran by you in

Yes, Ackerley already added that to the meeting agenda :)

> 
> As you said this at a minimum needs to be crippled / not production

Right, I think we're good as long as we don't start splitting folios on 
partial truncation. That is: only allow truncation in THP granularity.

I might not be around tomorrow and Ackerley will likely lead the 
meeting. I'll send out a reminder mail now that I realize I haven't ...

---
