---
title: '[Invitation] bi-weekly guest_memfd upstream call on 2025-04-17'
date: 2025-04-16
last_reply: 2025-04-17
message_count: 4
participants: ['David Hildenbrand', 'Shivank Garg', 'Chenyi Qiang']
---

## [1] David Hildenbrand — 2025-04-16

Hi everybody,

our next guest_memfd upstream call is scheduled for Thursday,
2025-04-17 at 8:00 - 9:00am (GMT-07:00) Pacific Time - Vancouver.

We'll be using the following Google meet:
http://meet.google.com/wxp-wtju-jzw

The meeting notes can be found at [1], where we also link recordings and
collect current guest_memfd upstream proposals. If you want an google
calendar invitation that also covers all future meetings, just write me
a mail.


If nothing else comes up, let's talk about the next steps to get basic 
mmap support [2] ready for upstream, to prepare for actual in-place 
conversion, direct-map removal and much more.

In particular, let's talk about what "basic mmap support" is, and what 
we can use it for without actual in-place conversion: IIUC "only shared 
memory in guest_memfd" use cases and some cases of software-protected 
VMs can use it.

Also, let's talk about the relationship/expectations between guest_memfd 
and the user (mmap) address when it comes to KVM memory slots that have 
a guest_memfd that supports "shared" memory.


To put something to discuss onto the agenda, reply to this mail or add
them to the "Topics/questions for next meeting(s)" section in the
meeting notes as a comment.

[1]
https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?usp=sharing
[2] 
https://lore.kernel.org/all/20250318161823.4005529-1-tabba@google.com/T/#u

---

## [2] Shivank Garg — 2025-04-16
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2025-04-17*

On 4/16/2025 5:28 PM, David Hildenbrand wrote:
> Hi everybody,
> 

Hi David,

I would like to discuss my V7 posting for Add NUMA mempolicy support
for KVM guest-memfd (https://lore.kernel.org/linux-mm/20250408112402.181574-1-shivankg@amd.com)
which incorporates feedback (using inodes for storing mempolicy) from my V6 posting.
I believe they're in better shape now.

Thanks,
Shivank

---

## [3] Chenyi Qiang — 2025-04-17
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2025-04-17*

On 4/16/2025 7:58 PM, David Hildenbrand wrote:
> Hi everybody,
> 

Hi David,

If we have time, I'd like to discuss about my v4 posting of shared
device assignment support
(https://lore.kernel.org/qemu-devel/20250407074939.18657-1-chenyi.qiang@intel.com/)
which introduces a new abstract parent class of RamDiscardManager, and a
new priority listener to apply to in-place conversion. Hope to get some
suggestion or confirmation if I'm in the correct direction.

Thanks
Chenyi

---

## [4] David Hildenbrand — 2025-04-17
*Subject: Re: [Invitation] bi-weekly guest_memfd upstream call on 2025-04-17*

On 17.04.25 04:46, Chenyi Qiang wrote:
> 
> 

Hi,

> If we have time, I'd like to discuss about my v4 posting of shared
> device assignment support

yes we can discuss that (and it's on my todo list as well to review). I 
suspect that it's mostly review that's missing at that point, and that 
it is conceptually ok.

Interestingly, I might be looking into virtio-mem support for 
confidential VMs at some point; I'll have to figure out how to allow for 
more states then :)

---
