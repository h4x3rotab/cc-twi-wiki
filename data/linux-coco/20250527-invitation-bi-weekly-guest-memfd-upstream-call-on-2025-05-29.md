---
title: '[Invitation] bi-weekly guest_memfd upstream call on 2025-05-29'
date: 2025-05-27
last_reply: 2025-05-27
message_count: 1
participants: ['David Hildenbrand']
---

## [1] David Hildenbrand — 2025-05-27

Hi everybody,

Our next guest_memfd upstream call is scheduled for Thursday,
2025-05-29 at 8:00 - 9:00am (GMT-07:00) Pacific Time - Vancouver.

We'll be using the following Google meet:
http://meet.google.com/wxp-wtju-jzw

The meeting notes can be found at [1], where we also link recordings and
collect current guest_memfd upstream proposals. If you want an google
calendar invitation that also covers all future meetings, just write me
a mail.

I have the following topics in mind:

(a) We'll continue our discussion on how to move forward with
     mmap() support ("stage 1"). So far I assume there are no big
     blockers.
(b) It seems as if there are some discussions to be had around the
     guest_memfd conversion ioctl.
(c) Likely it makes sense to talk about the series "New KVM ioctl to
     link a gmem inode to a new gmem file" [2], particularly, clarifying
     the use case and how it might (or might not) affect other related
     work.

To put something to discuss onto the agenda, reply to this mail or add
them to the "Topics/questions for next meeting(s)" section in the
meeting notes as a comment.

Cheers,

David

[1]
https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?usp=sharing
[2] https://lore.kernel.org/all/cover.1747368092.git.afranji@google.com/T/#u

---
