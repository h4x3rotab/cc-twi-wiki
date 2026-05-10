---
title: 'SVSM Development Call July 2nd, 2025'
date: 2025-07-01
last_reply: 2025-07-15
message_count: 18
participants: ['Jörg Rödel', 'Gerd Hoffmann', 'Relph, Richard', 'Jon Lange']
---

## [1] Jörg Rödel — 2025-07-01

Hi,

Here is the usual call for agenda items for the this weeks SVSM
development call.  Please send me any agenda items you have in mind or
raise them in the meeting.

Currently on the agenda:

	* Update on Hardware for CI.
	* Follow-up on the Live Migration discussion from last week.

We will use the LF Zoom instance. Details of the meeting  can be found in our
governance repository at:

	https://github.com/coconut-svsm/governance

The link to the COCONUT-SVSM calendar is:

	https://zoom-lfx.platform.linuxfoundation.org/meetings/coconut-svsm?view=week

The meeting will be recorded and the recording eventually published.

See you all there.

Regards,

	J�rg

---

## [2] Jörg Rödel — 2025-07-04
*Subject: Re: SVSM Development Call July 2nd, 2025*

Meeting minutes are now posted:

	https://github.com/coconut-svsm/governance/pull/65

Cheers,

	Joerg

---

## [3] Gerd Hoffmann — 2025-07-04
*Subject: Re: SVSM Development Call July 2nd, 2025*

On Fri, Jul 04, 2025 at 10:12:03AM +0200, J�rg R�del wrote:
> Meeting minutes are now posted:
> 

<quote>
  SVSM deciding its memory needs and informing OVMF. Peter Fang started
  exploring this, but it's not trivial and will take time to establish a
  good protocol for memory consumption and handoff. 
</quote>

What exactly we are talking about?  In the call alot of the discussion
centered around tracking the state of pages, and it wasn't totally clear
whenever that was an independent discussion or not ...

From OVMF perspective I don't see this as a big problem, assuming we are
talking about static allocation.  The memory discovery code is designed
around e820.  Typically OVMF simply loads the e820 table from qemu via
fw_cfg.  But there are multiple ways to get the memory map, when running
on xen or cloud hypervisor things are handled in a different way.
Adding one more option for svsm surely is possible.

So svsm could reserve some memory block for itself, even dynamically
sized (looking at CPUs and memory installed to estimate how much it will
need for page tables etc).  Split the e820 entry where that memory is
taken from into two, one RAM and one RESERVED.  Pass that modified e820
table to OVMF, or provide some svsm protocol so OVMF can query that.

take care,
  Gerd

---

## [4] Jörg Rödel — 2025-07-04
*Subject: Re: SVSM Development Call July 2nd, 2025*

Hi Gerd,

On Fri, Jul 04, 2025 at 12:36:07PM +0200, Gerd Hoffmann wrote:
> On Fri, Jul 04, 2025 at 10:12:03AM +0200, J�rg R�del wrote:
> > Meeting minutes are now posted:

The idea is that COCONUT provides an IGVM memory map to OVMF, which takes it as
a base for its memory map instead of the E820 from FWCFG.

Longer term it would be great to fully enable OVMF for IGVM, so that it can
also consume some of the ACPI tables from there instead of FWCFG. But that is
future stuff, what we need for now is the memory map.

Regards,

	Joerg

---

## [5] Relph, Richard — 2025-07-07
*Subject: Re: SVSM Development Call July 2nd, 2025*

On 7/4/2025 11:39 AM, Jörg Rödel wrote:
> 
> Hi Gerd,

As I heard it, the concern is that maintaining page state in SVSM (not OVMF)
will eventually require SVSM to have access to a dynamic amount of memory.
Right now, AFAIK, SVSM has no way to request memory from either the host or the 
guest.

Richard

---

## [6] Gerd Hoffmann — 2025-07-08
*Subject: Re: SVSM Development Call July 2nd, 2025*

Hi,

> >> From OVMF perspective I don't see this as a big problem, assuming we are
> >> talking about static allocation.  The memory discovery code is designed

Should be easy on the edk2 side.  As mentioned the infrastructure to use
different sources for the memory map is already there.  Also OVMF must
do SVSM calls quite early to accept memory, so doing SVSM calls to get
the map is no problem too.

The interface should be usable without allocating memory, for example a
protocol which returns one entry per call so OVMF can loop over the
entries using the stack only should do the trick.

> > Longer term it would be great to fully enable OVMF for IGVM, so that it can
> > also consume some of the ACPI tables from there instead of FWCFG. But that is

ACPI is a bit more tricky because today the process is that OVMF goes
setup the hardware, then qemu goes generate ACPI tables matching the
setup, finally OVMF loads them from qemu.

But as far I know svsm does not want enter the hardware initialization
business, so fetching the tables in svsm instead is not going to work.

> As I heard it, the concern is that maintaining page state in SVSM (not OVMF)
> will eventually require SVSM to have access to a dynamic amount of memory.

I assume you mean dynamic at boot time?  i.e. instead of the fixed, 16M
allocation via RequiredMemory IGVM directive svsm estimates how much
it'll need and takes the required chunk of memory from guest RAM?

Once OVMF gets the memory map from svsm not qemu this should be doable,
svsm can simply mark it's own memory as reserved then.

take care,
  Gerd

---

## [7] Relph, Richard — 2025-07-08
*Subject: Re: SVSM Development Call July 2nd, 2025*

On 7/8/2025 9:12 AM, Gerd Hoffmann wrote:
> Caution: This message originated from an External Source. Use proper caution when opening attachments, clicking links, or responding.
> 

Jon Lange should weigh in here... he's the expert on this.
But I believe it would need to be dynamic at run-time.
Using 'worst case' allocations that might have every page ending up needing it's own page state entry leads to excessive memory reservations. While not having enough memory leads to fatal errors. Being able start with a "reasonable" amount for page state while allowing for expansion later if needed is the preferred solution. At least that's what I was hearing last Wednesday.

Richard

  i.e. instead of the fixed, 16M
> allocation via RequiredMemory IGVM directive svsm estimates how much
> it'll need and takes the required chunk of memory from guest RAM?

---

## [8] Gerd Hoffmann — 2025-07-09
*Subject: Re: SVSM Development Call July 2nd, 2025*

> > I assume you mean dynamic at boot time?
> 

i.e. support for SVSM_CORE_DEPOSIT_MEM ?

> Being able start with a "reasonable" amount for page state while
> allowing for expansion later if needed is the preferred solution.

What events would trigger the need for expansion?  Would OVMF (which
typically would run for a few seconds at boot) need to support that?
Or is that something only the linux kernel (or other guest kernels)
would have to worry about?

take care,
  Gerd

---

## [9] Jörg Rödel — 2025-07-09
*Subject: Re: SVSM Development Call July 2nd, 2025*

Hi Richard,

On Tue, Jul 08, 2025 at 10:12:09AM -0500, Relph, Richard wrote:
> Jon Lange should weigh in here... he's the expert on this.
> But I believe it would need to be dynamic at run-time.

I think it is reasonable to assume that the (Linux) guest will eventually use
all available memory, and thus it makes sense to allocate the page-state
tracking data structure(s) big enough to cover all all guest memory right from
the start.

This eliminates the need for runtime resizing of SVSM memory, which is also
only possible on platforms/configurations that use the SVSM protocol.

Regards,

	Joerg

---

## [10] Relph, Richard — 2025-07-09
*Subject: Re: SVSM Development Call July 2nd, 2025*

On 7/9/2025 4:43 AM, Gerd Hoffmann wrote:
>>> I assume you mean dynamic at boot time?
>>

I doubt OVMF would need to worry about it. It feels likely to me that whatever "reasonable" amount we have SVSM pre-allocate would cover whatever page state transitions OVMF might create.

Richard

---

## [11] Relph, Richard — 2025-07-09
*Subject: Re: SVSM Development Call July 2nd, 2025*

On 7/9/2025 7:02 AM, Jörg Rödel wrote:
> Hi Richard,
> 

A "one entry for every page" approach to the page state tracking information might be pretty large, worst case. I'd have to replay the conversation from last week, but my sense was there's a fair bit of information that might eventually want to be known about each page. Some form of compression feels appropriate, since adjacent pages will often have identical state. But, worst case, every page could have different state, especially as the information about each page grows.

But we've stretched beyond my understanding of all the kinds of information that we might want to track from SVSM. Jon and others would need to chime in. For my immediate needs (rebooting a guest from SVSM), all I need is one bit per page... and I was considering run-length encoding that since it feels to me at this point like OVMF and Linux both do SVSM validate operations on large contiguous blocks of pages.

I agree, though, that if the long-term goal of SVSM is to be able to support guest OSs that are blissfully ignorant of SNP and SVSM, we can't rely on the guest OS to cooperate and a worst-case pre-allocation would be required, absent a way to get more from the host OS.

Richard

> 
> Regards,

---

## [12] Jon Lange — 2025-07-10
*Subject: RE: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025*

> i.e. support for SVSM_CORE_DEPOSIT_MEM ?

No, the SVSM knows the full memory map at boot time and therefore can know the amount of memory required for all bitmaps as part of its boot flow.  The simplest approach will be for the SVSM to carve out whatever memory it requires, and to tell the guest (OVMF) what memory it has claimed for itself.  There is no need for additional bitmap memory unless the guest support memory ballooning, which I think we can consider out of scope for now.  So the question is what is the best way for the SVSM to advertise its carve-out to OVMF. 

It is the case that the guest can execute SVSM_CORE_PVALIDATE on every 4 KB page of available guest memory, and the SVSM must be prepared to handle such a case, so there must be sufficient space to track one bit per 4 KB page of available guest memory.  It is also safe for the SVSM to return an error on any SVSM_CORE_PVALIDATE request that does not correspond to known guest memory, since there is no expectation for such a PVALIDATE request to succeed if there is no evidence that there is physical memory backing such an address.

-Jon

-----Original Message-----
From: Gerd Hoffmann <kraxel@redhat.com> 
Sent: Wednesday, July 9, 2025 2:44 AM
To: Relph, Richard <richard.relph@amd.com>
Cc: J�rg R�del <joro@8bytes.org>; coconut-svsm@lists.linux.dev; linux-coco@lists.linux.dev
Subject: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025

> > I assume you mean dynamic at boot time?
> 

i.e. support for SVSM_CORE_DEPOSIT_MEM ?

> Being able start with a "reasonable" amount for page state while 
> allowing for expansion later if needed is the preferred solution.

What events would trigger the need for expansion?  Would OVMF (which typically would run for a few seconds at boot) need to support that?
Or is that something only the linux kernel (or other guest kernels) would have to worry about?

take care,
  Gerd

---

## [13] Gerd Hoffmann — 2025-07-11
*Subject: Re: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025*

On Thu, Jul 10, 2025 at 04:32:58AM +0000, Jon Lange wrote:
> > i.e. support for SVSM_CORE_DEPOSIT_MEM ?
> 

OVMF doing svsm calls for this should work fine (didn't actually test,
but OVMF does memory validate calls quite early at boot, so I don't
expect blockers).  A protocol along these lines should work I think:

memmap call #1

  IN  RAX    $protocol.1
  OUT RCX    number of entries

memmap call #2

  IN  RAX    $protocol.2
  IN  RCX    entry index
  OUT RCX    entry index
  OUT RDX    entry type (e820)
  OUT R8     entry address
  OUT R9     entry size

Comments?

take care,
  Gerd

---

## [14] Jon Lange — 2025-07-11
*Subject: RE: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025*

> OVMF doing svsm calls for this should work fine (didn't actually test, but OVMF does memory validate calls quite early at boot, so I don't expect blockers).  A protocol along these lines should work I think:

There are two challenges with using an SVSM protocol to discover the memory map.  First, at least as I have been led to believe, OVMF isn't able to execute SVSM calls prior to the point in time that it requires the memory map to be available.  More importantly, though, SVSM calls are only available on SEV-SNP architectures, but memory reserves for page bitmaps are required on all platforms that support COCONUT-SVSM (TDX today, and ARM-CCA in the future).  Devising a protocol that only works on one architecture doesn't leave us in a very good place for the future.  Whatever design we produce for TDX should work equally well on SEV-SNP and thus should be our first choice so we can minimize the amount of platform-specific logic.

-Jon 

-----Original Message-----
From: Gerd Hoffmann <kraxel@redhat.com> 
Sent: Friday, July 11, 2025 6:31 AM
To: Jon Lange <jlange@microsoft.com>
Cc: Relph, Richard <richard.relph@amd.com>; J�rg R�del <joro@8bytes.org>; coconut-svsm@lists.linux.dev; linux-coco@lists.linux.dev
Subject: Re: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025

On Thu, Jul 10, 2025 at 04:32:58AM +0000, Jon Lange wrote:
> > i.e. support for SVSM_CORE_DEPOSIT_MEM ?
> 

OVMF doing svsm calls for this should work fine (didn't actually test, but OVMF does memory validate calls quite early at boot, so I don't expect blockers).  A protocol along these lines should work I think:

memmap call #1

  IN  RAX    $protocol.1
  OUT RCX    number of entries

memmap call #2

  IN  RAX    $protocol.2
  IN  RCX    entry index
  OUT RCX    entry index
  OUT RDX    entry type (e820)
  OUT R8     entry address
  OUT R9     entry size

Comments?

take care,
  Gerd

---

## [15] Gerd Hoffmann — 2025-07-14
*Subject: Re: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025*

On Fri, Jul 11, 2025 at 05:24:06PM +0000, Jon Lange wrote:
> > OVMF doing svsm calls for this should work fine (didn't actually test, but OVMF does memory validate calls quite early at boot, so I don't expect blockers).  A protocol along these lines should work I think:
> 

This is not correct.  Experimental but working patches:
 * coconut: https://github.com/coconut-svsm/svsm/pull/760
 * edk2: https://github.com/kraxel/edk2/commits/devel/svsm-memmap/

> More importantly, though, SVSM calls are only available on SEV-SNP
> architectures, but memory reserves for page bitmaps are required on

Huh?  I've assumed svsm protocols can work on TDX too.

The calling convention for guests to call into svsm surely must be
different on TDX.  But I've expected some similar mechanism could be
used ...

> Whatever design we produce for TDX

Can you clarify what options exist on TDX?
Pointer to documentation is fine.

thanks,
  Gerd

---

## [16] Jon Lange — 2025-07-14
*Subject: RE: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025*

> Huh?  I've assumed svsm protocols can work on TDX too.

The idea of an SVSM protocol might be sensible, but there is no calling convention.  The TDX partitioning model and the SEV-SNP VMPL model have radically different concepts of control flow transfers, so the SVSM calling convention is not easily adapted to TDX.  Intel has never defined such a calling convention.  In the past, they have suggested that such a calling convention is not needed, because the L1 can trap and emulate calls (including TDCALL requests), but I think there is now an understanding that this is not sufficient.  However, I am not aware of any active work to define any type of L1/L2 calling convention.

I also know that for this specific question (memory carveouts), Intel's proposed direction was not to rely on an L1/L2 calling convention, but instead to rely on having the L1 place tables into the address space of OVMF before it begins execution.  This, of course, would work equally well on SEV-SNP or any other model in which an SVSM-type environment can execute before the guest firmware.  I know that Intel began investigating this work but I don't know how far it's gotten.

> Can you clarify what options exist on TDX?
> Pointer to documentation is fine.

Because no L1/L2 calling convention has been defined, there is no documentation I can refer you to.  The best I can suggest is the TDX Module ABI specification (which you can find by searching).  There is also the TDX GHCI specification, but this is designed for guest-to-host interaction, and cannot really be used for L1/L2 calls because L2 TDVMCALL invocations may go directly to the host in some configurations, so there is no way to guarantee that the L1 can observe any requests issued by the L2.

-Jon

-----Original Message-----
From: Gerd Hoffmann <kraxel@redhat.com>
Sent: Monday, July 14, 2025 3:49 AM
To: Jon Lange <jlange@microsoft.com>
Cc: Relph, Richard <richard.relph@amd.com>; J�rg R�del <joro@8bytes.org>; coconut-svsm@lists.linux.dev; linux-coco@lists.linux.dev
Subject: Re: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025

On Fri, Jul 11, 2025 at 05:24:06PM +0000, Jon Lange wrote:
> > OVMF doing svsm calls for this should work fine (didn't actually test, but OVMF does memory validate calls quite early at boot, so I don't expect blockers).  A protocol along these lines should work I think:
>

This is not correct.  Experimental but working patches:
 * coconut: https://github.com/coconut-svsm/svsm/pull/760
 * edk2: https://github.com/kraxel/edk2/commits/devel/svsm-memmap/

> More importantly, though, SVSM calls are only available on SEV-SNP
> architectures, but memory reserves for page bitmaps are required on

Huh?  I've assumed svsm protocols can work on TDX too.

The calling convention for guests to call into svsm surely must be
different on TDX.  But I've expected some similar mechanism could be
used ...

> Whatever design we produce for TDX

Can you clarify what options exist on TDX?
Pointer to documentation is fine.

thanks,
  Gerd

---

## [17] Gerd Hoffmann — 2025-07-15
*Subject: Re: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025*

On Mon, Jul 14, 2025 at 04:18:11PM +0000, Jon Lange wrote:
> > Huh?  I've assumed svsm protocols can work on TDX too.
> 

Ok, so unclear at this point in time what will happen here.

> I also know that for this specific question (memory carveouts),
> Intel's proposed direction was not to rely on an L1/L2 calling

Well, there is the TDX Virtual Firmware Design Guide:
https://cdrdv2-public.intel.com/733585/tdx-virtual-firmware-design-guide-rev-004-20231206.pdf

Section 4.2 "TD Hand-Off Block (HOB)" describes how information can be
passed from VMM to the firmware.  It's about EFI firmware running on TDX
directly, without SVSM, but I think the same should work for launching
EFI firmware under SVSM.

> I know that Intel began investigating this work but I don't know how
> far it's gotten.

This does NOT sound like Intel wants reuse the existing spec.  At the
same time it is totally unclear if and when we get more clarity here
from Intel.

Hmm.

I see the point in having only one implementation for this instead of
implementing this again and again for each platform supported.  But
waiting for Intel until we move forward doesn't look attractive either.

take care,
  Gerd

---

## [18] Jon Lange — 2025-07-15
*Subject: RE: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025*

> I see the point in having only one implementation for this instead of
> implementing this again and again for each platform supported.  But

We've discussed this topic in the Technical Steering Committee, and our perspective is that this work is critical but not urgent.  We are not aware of any immediate use cases that would encourage us to create cross-platform divergence just for the sake of getting something built in the short term.  If you are aware of any use cases, please let us know.  I would guess that if we can demonstrate some good reasons to get this done soon, then some volunteers might emerge to help with the cross-platform concerns sooner rather than later, and if not, we can have a good discussion about the right set of compromises.

-Jon

-----Original Message-----
From: Gerd Hoffmann <kraxel@redhat.com>
Sent: Tuesday, July 15, 2025 8:07 AM
To: Jon Lange <jlange@microsoft.com>
Cc: Relph, Richard <richard.relph@amd.com>; J�rg R�del <joro@8bytes.org>; coconut-svsm@lists.linux.dev; linux-coco@lists.linux.dev
Subject: Re: [EXTERNAL] Re: SVSM Development Call July 2nd, 2025

On Mon, Jul 14, 2025 at 04:18:11PM +0000, Jon Lange wrote:
> > Huh?  I've assumed svsm protocols can work on TDX too.
>

Ok, so unclear at this point in time what will happen here.

> I also know that for this specific question (memory carveouts),
> Intel's proposed direction was not to rely on an L1/L2 calling

Well, there is the TDX Virtual Firmware Design Guide:
https://cdrdv2-public.intel.com/733585/tdx-virtual-firmware-design-guide-rev-004-20231206.pdf

Section 4.2 "TD Hand-Off Block (HOB)" describes how information can be
passed from VMM to the firmware.  It's about EFI firmware running on TDX
directly, without SVSM, but I think the same should work for launching
EFI firmware under SVSM.

> I know that Intel began investigating this work but I don't know how
> far it's gotten.

This does NOT sound like Intel wants reuse the existing spec.  At the
same time it is totally unclear if and when we get more clarity here
from Intel.

Hmm.

I see the point in having only one implementation for this instead of
implementing this again and again for each platform supported.  But
waiting for Intel until we move forward doesn't look attractive either.

take care,
  Gerd

---
