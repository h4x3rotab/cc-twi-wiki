---
title: '[PATCH v2 00/18] PCI device authentication'
date: 2025-05-20
last_reply: 2025-05-29
message_count: 3
participants: ['Alexey Kardashevskiy', 'Lukas Wunner']
---

## [1] Alexey Kardashevskiy — 2025-05-20

On 13/2/25 03:36, Lukas Wunner wrote:
> On Tue, Feb 11, 2025 at 12:30:21PM +1100, Alexey Kardashevskiy wrote:
>>>> On 1/7/24 05:35, Lukas Wunner wrote:

Any luck with these? Asking as there is another respin  https://lore.kernel.org/r/20250516054732.2055093-1-dan.j.williams@intel.com  and it considers merge with yours. Thanks,

> specifically the migration to netlink for retrieval of signatures
> and measurements as discussed at Plumbers.

---

## [2] Alexey Kardashevskiy — 2025-05-29

On 20/5/25 18:35, Alexey Kardashevskiy wrote:
> 
> 

Ping?

> 
>> specifically the migration to netlink for retrieval of signatures

---

## [3] Lukas Wunner — 2025-05-29

On Thu, May 29, 2025 at 03:29:23PM +1000, Alexey Kardashevskiy wrote:
> On 20/5/25 18:35, Alexey Kardashevskiy wrote:
> > On 13/2/25 03:36, Lukas Wunner wrote:

I intend to push a new version to my repo after the merge window closes
and that'll use netlink multicast to convey signatures to userspace.

Thanks,

Lukas

---
