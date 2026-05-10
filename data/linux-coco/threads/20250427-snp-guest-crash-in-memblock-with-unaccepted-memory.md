---
title: 'SNP guest crash in memblock with unaccepted memory'
date: 2025-04-27
last_reply: 2025-04-30
message_count: 8
participants: ['Tom Lendacky', 'David Hildenbrand', 'Mike Rapoport', 'Kirill A. Shutemov']
---

## [1] Tom Lendacky — 2025-04-27

Hi Kirill,

Every now and then I experience an SNP guest boot failure for accessing
memory that hasn't been accepted. I managed to get a back trace:

  RIP: 0010:memcpy_orig+0x68/0x130
  Code: ...
  RSP: 0000:ffffffff9cc03ce8 EFLAGS: 00010006
  RAX: ff11001ff83e5000 RBX: 0000000000000000 RCX: fffffffffffff000
  RDX: 0000000000000bc0 RSI: ffffffff9dba8860 RDI: ff11001ff83e5c00
  RBP: 0000000000002000 R08: 0000000000000000 R09: 0000000000002000
  R10: 000000207fffe000 R11: 0000040000000000 R12: ffffffff9d06ef78
  R13: ff11001ff83e5000 R14: ffffffff9dba7c60 R15: 0000000000000c00
  memblock_double_array+0xff/0x310
  memblock_add_range+0x1fb/0x2f0
  memblock_reserve+0x4f/0xa0
  memblock_alloc_range_nid+0xac/0x130
  memblock_alloc_internal+0x53/0xc0
  memblock_alloc_try_nid+0x3d/0xa0
  swiotlb_init_remap+0x149/0x2f0
  mem_init+0xb/0xb0
  mm_core_init+0x8f/0x350
  start_kernel+0x17e/0x5d0
  x86_64_start_reservations+0x14/0x30
  x86_64_start_kernel+0x92/0xa0
  secondary_startup_64_no_verify+0x194/0x19b

I don't know a lot about memblock, but it appears that it needs to
allocate more memory for it's regions array and returns a range of memory
that hasn't been accepted. When the memcpy() runs, the SNP guest gets a
#VC 0x404 because of this.

Do you think it is as simple as calling accept_memory() on the memory
range returned from memblock_find_in_range() in memblock_double_array()?

Thanks,
Tom

---

## [2] David Hildenbrand — 2025-04-28
*Subject: Re: SNP guest crash in memblock with unaccepted memory*

On 27.04.25 17:01, Tom Lendacky wrote:
> Hi Kirill,
> 

(not Kirill, but replying :) )

Yeah, we seem to be effectively allocating memory from memblock ("from 
ourselves") without considering that memory must be accepted first.

accept_memory() on the new memory (in case of !slab) should be the right 
thing to do.

---

## [3] Tom Lendacky — 2025-04-28
*Subject: Re: SNP guest crash in memblock with unaccepted memory*

On 4/28/25 09:04, David Hildenbrand wrote:
> On 27.04.25 17:01, Tom Lendacky wrote:
>> Hi Kirill,

Thanks, David. Let me add a call in for accept_memory in the !slab case
and see if that resolves it. May take a bit to repro, but should find
out eventually.

I'll submit a patch once I verify.

Thanks,
Tom

>

---

## [4] David Hildenbrand — 2025-04-28
*Subject: Re: SNP guest crash in memblock with unaccepted memory*

On 28.04.25 20:10, Tom Lendacky wrote:
> On 4/28/25 09:04, David Hildenbrand wrote:
>> On 27.04.25 17:01, Tom Lendacky wrote:

BTW, I was wondering if we could use memblock_alloc_range_nid() in 
memblock_double_array(); maybe not that easy, just a thought.

---

## [5] Mike Rapoport — 2025-04-29
*Subject: Re: SNP guest crash in memblock with unaccepted memory*

On Mon, Apr 28, 2025 at 01:10:31PM -0500, Tom Lendacky wrote:
> On 4/28/25 09:04, David Hildenbrand wrote:
> > On 27.04.25 17:01, Tom Lendacky wrote:

I think sticking a loop of memblock_alloc() somewhere before mm_core_init()
should trigger the issue.
 
> I'll submit a patch once I verify.
>

---

## [6] Mike Rapoport — 2025-04-29
*Subject: Re: SNP guest crash in memblock with unaccepted memory*

On Mon, Apr 28, 2025 at 11:00:36PM +0200, David Hildenbrand wrote:
> On 28.04.25 20:10, Tom Lendacky wrote:
> > On 4/28/25 09:04, David Hildenbrand wrote:

Not easy at all for memblock.reserved, memblock_double_array() makes sure
to avoid memory that's being reserved in this call chain:

memblock_alloc_range_nid()
	memblock_reserve()
		memblock_add_range()
			memblock_double_array()

 
> -- 
> Cheers,

---

## [7] Kirill A. Shutemov — 2025-04-30
*Subject: Re: SNP guest crash in memblock with unaccepted memory*

On Mon, Apr 28, 2025 at 04:04:50PM +0200, David Hildenbrand wrote:
> On 27.04.25 17:01, Tom Lendacky wrote:
> > Hi Kirill,

Right, it should do the trick.

BTW, Mike, is there any other codepath where memblock allocates memory for
itself? We need to cover them too.

---

## [8] Mike Rapoport — 2025-04-30
*Subject: Re: SNP guest crash in memblock with unaccepted memory*

On Wed, Apr 30, 2025 at 12:14:08PM +0300, Kirill A. Shutemov wrote:
> On Mon, Apr 28, 2025 at 04:04:50PM +0200, David Hildenbrand wrote:
> > On 27.04.25 17:01, Tom Lendacky wrote:

memblock_double_arrayi() is the only place where memblock allocates memory
for itself.
 
> -- 
>   Kiryl Shutsemau / Kirill A. Shutemov

---
