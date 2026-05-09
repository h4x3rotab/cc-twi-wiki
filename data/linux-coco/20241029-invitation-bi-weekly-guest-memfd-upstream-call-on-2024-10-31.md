---
title: '[Invitation] bi-weekly guest_memfd upstream call on 2024-10-31'
date: 2024-10-29
last_reply: 2024-10-29
message_count: 1
participants: ['David Hildenbrand']
---

## [1] David Hildenbrand — 2024-10-29

Hi,

the next guest_memfd upstream call will happen this Thursday, 2024-10-31 
at at 9:00 - 10:00am (GMT-07:00) Pacific Time - Vancouver.

We'll be using the following Google meet: 
http://meet.google.com/wxp-wtju-jzw

The meeting notes are linked from the google calendar invitation. If you 
want an invitation that also covers all future meetings, just write me a 
mail.


To put something to discuss onto the agenda, reply to this mail or add 
them to the "Topics/questions for next meeting(s)" section in the 
meeting notes as a comment.

We'll continue our discussion on:
* Challenges with supporting huge pages
* Challenges with shared vs. private conversion (e.g., folio_put()
   callback)
* guest_memfd as a "library"

--

Current upstream proposals floating around:
* mmap support + shared vs. private [2]
* preparations [3] for huge/gigantic page support [4]
* guest_memfd as a "library" to make it independent of KVM [5]

[1] 
https://lkml.kernel.org/r/4b49248b-1cf1-44dc-9b50-ee551e1671ac@redhat.com
[2] https://lkml.kernel.org/r/20241010085930.1546800-1-tabba@google.com
[3] https://lkml.kernel.org/r/cover.1728684491.git.ackerleytng@google.com
[4] https://lkml.kernel.org/r/cover.1728684491.git.ackerleytng@google.com
[5] 
https://lkml.kernel.org/r/20240829-guest-memfd-lib-v2-0-b9afc1ff3656@quicinc.com

---
