---
title: "Accept unaccepted kexec segments' destination addresses"
date: 2024-12-13
last_reply: 2025-03-13
message_count: 24
participants: ['Yan Zhao', 'Kirill A. Shutemov', 'Baoquan He', 'Eric W. Biederman', 'Dave Hansen', 'Kirill A. Shutemov', 'Jianxiong Gao', 'Ashish Kalra', 'Andrew Morton']
---

## [1] Yan Zhao — 2024-12-13

Hi Eric,

This is a repost of the patch "kexec_core: Accept unaccepted kexec
destination addresses" [1], rebased to v6.13-rc2.

The code implementation remains unchanged, but the patch message now
includes more background and explanations to address previous concerns from
you and Baoquan.

Additionally, below is a more detailed explanation of unaccepted memory in
TDX. Please let me know if it is still not clear enough.


== UnAccepted memory in TDX ==

Intel TDX (Trusted Domain Extension) provides a hardware-based trusted
execution environment for TDs (hardware-isolated VMs). The host OS is not
trusted. Although it allocates physical pages for TDs, it does not and
cannot know the content of TD's pages.

TD's memory is added via two methods by invoking different instructions in
the host:
1. For TD's initial private memory, such as for firmware HOBs:
   - This type of memory is added without requiring the TD's acceptance.
   - The TD will perform attestation of the page GPA and content later.

2. For TD's runtime private memory:
   - After the host adds memory, it is pending for the TD's acceptance.

Memory added by method 1 is not relevant to the unaccepted memory we will
discuss.

For memory added by method 2, the TD's acceptance can occur before or after
the TD's memory access:
(a) Access first:
    - TD accesses a private GPA,
    - Host OS allocates physical memory,
    - Host OS requests hardware to map the physical page to the GPA,
    - TD accepts the GPA.

(b) Accept first:
    - TD accepts a private GPA,
    - Host OS allocates physical memory,
    - Host OS requests hardware to map the physical page to the GPA,
    - TD accesses the GPA.

For "(a) Access first", it is regarded as unsafe for a Linux guest and is
therefore not chosen.
For "(b) Accept first", the TD's "accept" operation includes the following
steps:
- Trigger a VM-exit
- The host OS allocates a physical page and requests hardware to map the
  physical page to the GPA.
- Initialize the physical page with content set to 0.
- Encrypt the memory 


To enable the "Accept first" approach, an "unaccepted memory" mechanism is
used, which requires cooperation from the virtual firmware and the Linux
guest.

1. The host OS adds initial private memory that does not require TD's
   acceptance. The host OS composes EFI_HOB_RESOURCE_DESCRIPTORs and loads
   the virtual firmware first. Guest RAM, excluding that for initial
   memory, is reported as UNACCEPTED in the descriptor.

2. The virtual firmware parses the descriptors and accepts the UNACCEPTED
   memory below 4G. It then excludes the below-4G range from the UNACCEPTED
   range.

3. The virtual firmware loads the Linux guest image (the address to load is
   below 4G).

4. The Linux guest requests the UNACCEPTED bitmap from the virtual
   firmware:
   - Locate EFI_UNACCEPTED_MEMORY entries from the memory map returned by
     the efi_get_memory_map boot service.
   - Request via EFI boot service to allocate an unaccepted_table in memory
     of type EFI_ACPI_RECLAIM_MEMORY (E820_TYPE_ACPI) to hold the
     unaccepted bitmap.
   - Install the unaccepted_table as an EFI configuration table via the
     boot service.
   - Initialize the unaccepted bitmap according to the
     EFI_UNACCEPTED_MEMORY entries.

5. The Linux guest decompresses the kernel image. It accepts the target GPA
   for decompression first in case it is not accepted by the virtual
   firmware.

6. The Linux guest calls memblock_free_all() to put all memory into the
   freelists for the buddy allocator. memblock_free_all() further calls
   down to __free_pages_core() to handle memory in 4M (order 10) units.

  - In eager mode, the Linux guest accepts all memory and appends it to the
    freelists.
  - In lazy mode, the Linux guest checks if the entire 4M memory has been
    accepted by querying the unaccepted bitmap.
    a) If all memory is accepted, it adds the 4M memory to the freelists.
    b) If any memory is unaccepted (even if the range contains accepted
       pages), the Linux guest does not add the 4M memory to the freelists.
       Instead, it queues the first page in the 4M range onto the list
       zone->unaccepted_pages and sets the first page with the Unaccepted
       flag.

7. When there is not enough free memory, cond_accept_memory() in the Linux
   guest calls try_to_accept_memory_one() to dequeue a page from the list
   zone->unaccepted_pages, clear its Unaccepted flag, accept the entire 4M
   memory range represented by the page, and add the 4M memory to the
   freelists.


== Conclusion ==
- The zone->unaccepted_pages is a mechanism to conditionally make accepted
  private memory available to the page allocators.
- The unaccepted bitmap resides in the firmware's reserved memory and
  persists across guest OSs. It records exactly which pages have not been
  accepted.
- Memory ranges represented by zone->unaccepted_pages may contain accepted
  pages.


For kexec in TDs,
- If the segments' destination addresses are within the range managed by
  the buddy allocator, the pages must have been in an accepted state.
  Calling accept_memory() will check the unaccepted bitmap and do nothing.
- If the segments' destination addresses are not yet managed by the buddy
  allocator, the pages may or may not have been accepted.
  Calling accept_memory() will perform the "accept" operation if they are
  not accepted.

For the kexec's second guest kernel, it obtains the unaccepted bitmap by
locating the unaccepted_table in the EFI configuration tables. So, pages
unset in the unaccepted bitmap are not accepted repeatedly.


The unaccepted table/bitmap is only useful for TDs. For a Linux host, it
will detect that the physical firmware does not support the memory
acceptance protocol, and accept_memory() will simply bail out.

Thanks
Yan

[1] https://lore.kernel.org/all/20241021034553.18824-1-yan.y.zhao@intel.com

Yan Zhao (1):
  kexec_core: Accept unaccepted kexec segments' destination addresses

 kernel/kexec_core.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

---

## [2] Yan Zhao — 2024-12-13
*Subject: [PATCH v2 1/1] kexec_core: Accept unaccepted kexec segments' destination addresses*

In TDX, to run a linux guest, TDs (hardware-isolated VMs) must accept
before accessing private memory. Accessing private memory before acceptance
is considered a fatal error and may result in the termination of the TD.

The "accepting memory" operation in guest includes the following steps:
- trigger a VM-exit
- the host OS allocates a physical page and requests hardware to map the
  physical page to the GPA.
- initialize memory content to 0.
- encrypt the memory

For a Linux guest, eagerly accepting all memory during kernel boot can slow
down the boot process and cause unnecessary memory occupation on the host
for pages that may never be accessed. Therefore, Linux guests usually opt
for a lazy mode to delay page acceptance operations by not moving the pages
to the buddy allocator's freelists. Instead, the kernel tracks memory
in 4M units and places them in a zone->unaccepted_pages list if any page in
the entire 4M range is in an unaccepted state (even if part of the memory
range may have been accepted by firmware or the kernel). When the kernel
does not have enough free pages, it will move memory from the
zone->unaccepted_pages list and accept it, ensuring that the memory is
accepted before moving it to the freelists and being available to the buddy
allocator.

The kexec segments' destination addresses are not allocated by the buddy
allocator. Instead, they are searched from normal system RAM (top-down or
bottom-up) and exclude driver-managed memory, ACPI, persistent, and
reserved memory... Although these addresses may fall within the memory
range managed by the buddy allocator (which must be in an accepted state),
they could also be outside that range and in an unaccepted state.

Since the kexec code will access the segments' destination addresses during
the kexec process by swapping their content with the segments' source
pages, it is necessary to accept the memory before performing the swap
operations.

Accept the destination addresses during the kexec load, immediately after
they pass sanity checks. This ensures the code is located in a common place
shared by both the kexec_load and kexec_file_load system calls.

This will not conflict with the accounting in try_to_accept_memory_one()
since the accounting is set during kernel boot and decremented when pages
are moved to the freelists. There is no harm in invoking accept_memory() on
a page before making it available to the buddy allocator.

No need to worry about re-accepting memory since accept_memory() checks the
unaccepted bitmap before accepting a memory page.

Although a user may perform kexec loading without ever triggering the jump,
it doesn't impact much since kexec loading is not in a performance-critical
path. Additionally, the destination addresses are always searched and found
in the same location on a given system.

Changes to the destination address searching logic to locate only memory in
either unaccepted or accepted status are unnecessary and complicated.

Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Cc: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Cc: Baoquan He <bhe@redhat.com>
---
 kernel/kexec_core.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/kernel/kexec_core.c b/kernel/kexec_core.c
index c0caa14880c3..f8eee0516bd9 100644
--- a/kernel/kexec_core.c
+++ b/kernel/kexec_core.c
@@ -210,6 +210,16 @@ int sanity_check_segment_list(struct kimage *image)
 	}
 #endif
 
+	/*
+	 * The destination addresses are searched from system RAM rather than
+	 * being allocated from the buddy allocator, so they are not guaranteed
+	 * to be accepted by the current kernel.  Accept the destination
+	 * addresses before kexec swaps their content with the segments' source
+	 * pages to avoid accessing memory before it is accepted.
+	 */
+	for (i = 0; i < nr_segments; i++)
+		accept_memory(image->segment[i].mem, image->segment[i].memsz);
+
 	return 0;
 }

---

## [3] Kirill A. Shutemov — 2025-01-13
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Fri, Dec 13, 2024 at 05:49:30PM +0800, Yan Zhao wrote:
> Hi Eric,
> 

Can we get this patch applied?

---

## [4] Baoquan He — 2025-01-13
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On 01/13/25 at 12:01pm, Kirill A. Shutemov wrote:
> On Fri, Dec 13, 2024 at 05:49:30PM +0800, Yan Zhao wrote:
> > Hi Eric,

This looks good to me. In v1, we have analyzed all other possible
solutions, however change in this patch seems the simplest and most
accepatable one. 

If Eric has no objection, maybe Andrew can help pick this into his tree.

Thanks
Baoquan

---

## [5] Eric W. Biederman — 2025-01-13
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

Baoquan He <bhe@redhat.com> writes:

> On 01/13/25 at 12:01pm, Kirill A. Shutemov wrote:
>> On Fri, Dec 13, 2024 at 05:49:30PM +0800, Yan Zhao wrote:

Truly?  I will go back and look and see what I missed but I haven't seen
anything that I addressed my original objections.

To repeat my objection.  The problem I saw was that the performance of
the accepted memory paradigm was so terrible that they had to resort to
lazily ``accepting'' memory, which leads to hacks in kexec.  I would not
like to included hacks in kexec just so that other people can avoid
fixing their bugs.

I did see a coherent explanation of the bad performance that pointed the
finger squarely at the fact that everything is happening a page at a
time.  AKA that the design of the ACPI interface has a flaw that needs
to be fixed.

I really don't think we should be making complicated work-arounds for
someone else's bad software decision just because someone immortalized
their bad decision in a standard.  Just accepting all of memory and
letting the folks who made the bad decision deal with the consequences
seems much more reasonable to me.

> If Eric has no objection, maybe Andrew can help pick this into his
> tree.

I have a new objection.  I believe ``unaccepted memory'' and especially
lazily initialized ``unaccepted memory'' is an information leak that
could defeat the purpose of encrypted memory.  For that reason I have
Cc'd the security list.  I don't know who to CC to get expertise on this
issue, and the security list folks should.

Unless I am misunderstanding things the big idea with encrypted
memory is that the hypervisor won't be able to figure out what you
are doing, because it can't read your memory.

My concern is that by making the ``acceptance'' of memory lazy, that
there is a fairly strong indication of the function of different parts
of memory.  I expect that signal is strong enough to defeat whatever
elements of memory address randomization that we implement in the
kernel.

So not only does it appear to me that implementation of ``accepting''
memory has a stupidly slow implementation, somewhat enshrined by a bad
page at a time ACPI standard, but it appears to me that lazily
``accepting'' that memory probably defeats the purpose of having
encrypted memory.

I think the actual solution is to remove all code except for the
"accept_memory=eager" code paths.  AKA delete the "accept_memory=lazy"
code.  At that point there are no more changes that need to be made to
kexec.

Eric

---

## [6] Baoquan He — 2025-01-14
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

Hi Eric,

On 01/13/25 at 08:59am, Eric W. Biederman wrote:
> Baoquan He <bhe@redhat.com> writes:
> 

Ah, I didn't realized you object the accept_memory feature itself, sorry
about that. I personally dislike accept_memory either since there's
already DEFERRED_STRUCT_PAGE_INIT feature to improve the boot time
memory init. While talking about the passive providing RAM to guest
system when actually demanded, this seems to be helpful to save RAM
memory for cloud provider's host system, this is what I think is
valuable of the accept_memory, even though Intel engineer avoids to
delcare it formally.

Anyway, I would like to ack it based on accept_memory feature having
already been merged into mainline kernel. If the feature itself is
objected, the top priority is discussing to decide if we should take it
off in kernel or how limitedly it's being used in kernel, or vice versa,
whether supporting it in kexec truly is another story.

Thanks a lot for your thought sharing with elaborate explanation.

Thanks
Baoquan

> 
> > If Eric has no objection, maybe Andrew can help pick this into his

---

## [7] Yan Zhao — 2025-01-14
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Mon, Jan 13, 2025 at 08:59:29AM -0600, Eric W. Biederman wrote:
> Baoquan He <bhe@redhat.com> writes:
> 
Hi Eric,
Your previous concerns in v1 [1] include:

1. "an unfiltered accept_memory may result in memory that has already been
   ``accepted'' being accepted again.
2. "target kernel won't know about about accepting memory, or might not perform
   the work early enough and try to use memory without accepting it first."
3. "this is has the potential to conflict with the accounting in
   try_to_accept_memory"

For 1/2, as we explained in [2], accept_memory() is not unfiltered. A bitmap in
       the virtual firmware maintains the accepted/unaccepted status and the
       bitmap is passed across the kernels.

For 3, sorry that I didn't explain clearly enough in v1, so I explained it in
       detail in the v2's cover letter (please check bullet 6 in [3]).
       The accounting in try_to_accept_memory_one() includes
       zone->unaccepted_pages,
       zone_page_state(zone, NR_FREE_PAGES),
       zone_page_state(zone, NR_UNACCEPTED),
       which are updated in try_to_accept_memory_one()-->__accept_page().

       However, the accounting will not be affected by invoking accept_memory()
       in kexec, since accept_memory() does not modify them, and it's correct to
       do so because of the way how the "accept_memory=lazy" works:
       
       (1) when to release free pages to the buddy allocator in
        memblock_free_all() during kernel boot, "accept_memory=lazy" withholds
        some pages out of the buddy allocator by recording them in the
        zone->unaccepted_pages list. The NR_FREE_PAGES, NR_UNACCEPTED are
        increased accordingly. By NR_UNACCEPTED, it just means the count of
        pages that are potentially available but currently not available to
        buddy's freelists. It does not mean alls the pages must be in
        unaccepted status.
        (see __free_pages_core() and __free_unaccepted()).
       (2) When the kernel runs out of memory, indicated by no enough
        NR_UNACCEPTED, it invokes
        cond_accept_memory()-->try_to_accept_memory_one()-->__accept_page() to
        put the pages from zone->unaccepted_pages to buddy's freelists and
        further call accept_memory() to accept those pages.
       Before (2), though accept_memory() can also accept a page, the page is
       not available to the buddy and hence not available to other kernel
       components. When accept_memory() is invoked in (2), the page will not be
       re-accepted.

The reason for this series to have kexec to accept_memory() to kexec segments'
destination addresses is that those addresses are not necessarily allocated by
the first kernel's buddy allocator. So, before kexec accessing those pages
(which could be earlier than the second kernel), we invoke the accept_memory()
to trigger the physical page allocation in host, GFN->PFN mapping, physical page
initialization and encryption. After that, kexec can copy source pages into the
destination pages and start the transition to the second kernel.

With that, do you still think this patch is a hack ?

[1] https://lore.kernel.org/all/87frop8r0y.fsf@email.froward.int.ebiederm.org/
[2] https://lore.kernel.org/all/tpbcun3d4wrnbtsvx3b3hjpdl47f2zuxvx6zqsjoelazdt3eyv@kgqnedtcejta/
[3] https://lore.kernel.org/all/20241213094930.748-1-yan.y.zhao@intel.com


> 
> I did see a coherent explanation of the bad performance that pointed the
By flaw, do you mean accepting page by page?

The accept_memory() only takes effect in a guest, demanding physical page
allocation in host OS, which is slow by nature. It's also the truth that
once a page has been accepted, it cannot be swapped out in host.

> I really don't think we should be making complicated work-arounds for
> someone else's bad software decision just because someone immortalized
Do you mean before the lazy acceptance, the host can access the page?
Or are you referring to that the host can know the GFN of a page when it
responds to the page allocation request?

For the former, the page will be regarded as private by the guest only after
it's accepted in the guest. So no data will be leaked before guest completes
accept_memory() that initializes the memory data to 0 and encrypts the memory.

For the latter, the lazy memory acceptance still happens in a bulk way, i.e.
not in response to the guest accessing of a specific memory.
So, I can't see which information is leaked.

> Cc'd the security list.  I don't know who to CC to get expertise on this
> issue, and the security list folks should.
There might be some misunderstanding.
A page will only be regarded as private by the guest after the guest's explicit
acceptance of the memory.

> 
> My concern is that by making the ``acceptance'' of memory lazy, that
memory randomization also invokes accept_memory() in extract_kernel().

> So not only does it appear to me that implementation of ``accepting''
> memory has a stupidly slow implementation, somewhat enshrined by a bad
Not only for performance, but also for memory over-commitment.

Hope the above explanations have addressed your concerns.
Please let me know if anything still doesn't sound correct to you.

Thanks
Yan

> I think the actual solution is to remove all code except for the
> "accept_memory=eager" code paths.  AKA delete the "accept_memory=lazy"

---

## [8] Kirill A. Shutemov — 2025-01-14
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Mon, Jan 13, 2025 at 08:59:29AM -0600, Eric W. Biederman wrote:
> Baoquan He <bhe@redhat.com> writes:
> 

The interface of accepting memory is platform specific. EFI (not ACPI)
only provides a way to enumerate which memory is unaccepted.

> I really don't think we should be making complicated work-arounds for
> someone else's bad software decision just because someone immortalized

Note that these work-arounds are needed only because kexec allocates
memory in a hackish way bypassing page allocator.

I don't like that unaccepted memory details leaks into kexec code either.
But it happens because kexec is special and requires special handling.

> > If Eric has no objection, maybe Andrew can help pick this into his
> > tree.

It is outside of TDX (and I believe SEV) threat model. In TDX case, VMM
can block access to arbitrary guest memory range which would cause TD-exit
if guest touches it. The blocking is required to do some of memory
maintenance operations, like promoting 4k pages to 2M or relocating a
guest page to a different host physical address.

Lazy memory accept doesn't change anything from security PoV here.

---

## [9] Dave Hansen — 2025-02-13
*Subject: Re: [PATCH v2 1/1] kexec_core: Accept unaccepted kexec segments'
 destination addresses*

On 12/13/24 01:54, Yan Zhao wrote:
> +	/*
> +	 * The destination addresses are searched from system RAM rather than

The "searched from system RAM" phrase both here and in the changelog
doesn't quite parse for me.

Also "System RAM" is the normal phrase that I use to describe the memory
that mostly ends up _going_ into the buddy allocator. It's not just me:

	cat /proc/iomem  | grep 'System RAM'

I think a more useful comment (and changelog) might be something like this:

	The core kernel focuses on accepting memory which is known to be
	System RAM. However, there might be areas that are reserved in
	the memory map, not exposed to the kernel as "System RAM" and
	not accepted by firmware. Accept the memory before kexec touches
	it.

---

## [10] Dave Hansen — 2025-02-13
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On 1/13/25 06:59, Eric W. Biederman wrote:
...
> I have a new objection.  I believe ``unaccepted memory'' and especially
> lazily initialized ``unaccepted memory'' is an information leak that

At a super high level, you are right. Accepting memory tells the
hypervisor that the guest is _allocating_ memory. It even tells the host
what the guest physical address of the memory is. But that's far below
the standard we've usually exercised in the kernel for rejecting on
security concerns.

Did anyone on the security list raise any issues here? I've asked them
about a few things in the past and usually I've thought that no news is
good news.

> My concern is that by making the ``acceptance'' of memory lazy, that
> there is a fairly strong indication of the function of different parts

In the end, the information that the hypervisor gets is that the guest
allocated _some_ page within a 4MB physical region and the time. It gets
that signal once per boot for each region. It will mostly see a pattern
of acceptance going top-down from high to low physical addresses.

The hypervisor never learns anything about KASLR. The fact that the
physical allocation patterns are predictable (with or without memory
acceptance) is one of the reasons KASLR is in place.

I don't think memory acceptance has any real impact on "memory address
randomization". This is especially true because it's a once-per-boot
signal, not a continuous thing that can be leveraged. 4MB is also
awfully coarse.

> So not only does it appear to me that implementation of ``accepting''
> memory has a stupidly slow implementation, somewhat enshrined by a bad

Memory acceptance is pitifully slow. But it's slow because it
fundamentally requires getting guest memory into a known state before
guest use. You either have slow memory acceptance as a thing or you have
slow guest boot.

Are there any other CoCo systems that don't have to zero memory like TDX
does? On the x86 side, we have SGX the various flavors of SEV. They all,
as far as I know, require some kind of slow "conversion" process when
pages change security domains.

> I think the actual solution is to remove all code except for the
> "accept_memory=eager" code paths.  AKA delete the "accept_memory=lazy"

That was my first instinct too: lazy acceptance is too complicated to
live and must die.

It sounds like you're advocating for the "slow guest boot" option.
Kirill, can you remind us how fast a guest boots to the shell for
modestly-sized (say 256GB) memory with "accept_memory=eager" versus
"accept_memory=lazy"? IIRC, it was a pretty remarkable difference.

Eric, I wasn't planning on ripping the lazy acceptance code out of
arch/x86. I haven't heard any rumblings from the mm folks that it's
causing problems over there either. This seems like something we want to
fix and I _think_ the core kexec code is the right place to fix this issue.

There are definitely ways to work around this in arch code, but they
seem rather distasteful and I'd rather not go there.

---

## [11] Kirill A. Shutemov — 2025-02-14
*Subject: Re: [PATCH v2 1/1] kexec_core: Accept unaccepted kexec segments'
 destination addresses*

On Thu, Feb 13, 2025 at 07:50:42AM -0800, Dave Hansen wrote:
> On 12/13/24 01:54, Yan Zhao wrote:
> > +	/*

If kernel compiled with CONFIG_UNACCEPTED_MEMORY, EFI_UNACCEPTED_MEMORY
is part of System RAM. It translates to E820_TYPE_RAM. See setup_e820() in
EFI stub.

---

## [12] Kirill A. Shutemov — 2025-02-14
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Thu, Feb 13, 2025 at 07:55:15AM -0800, Dave Hansen wrote:
> On 1/13/25 06:59, Eric W. Biederman wrote:
> ...

I only have 128GB machine readily available and posted some number on
other thread[1]:

  On single vCPU it takes about a minute to accept 90GiB of memory.

  It improves a bit with number of vCPUs. It is 40 seconds with 4 vCPU, but
  it doesn't scale past that in my setup.

I've mentioned it before in other thread:

[1] https://lore.kernel.org/all/ihzvi5pwn5hrn4ky2ehjqztjxoixaiaby4igmeihqfehy2vrii@tsg6j5qvmyrm

---

## [13] Dave Hansen — 2025-02-14
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On 2/14/25 05:46, Kirill A. Shutemov wrote:
>> It sounds like you're advocating for the "slow guest boot" option.
>> Kirill, can you remind us how fast a guest boots to the shell for

Oh, wow, from that other thread, you've been trying to get this crash
fix accepted since November?

From the looks of it, Eric stopped responding to that thread. I _think_
you gave a reasonable explanation of why memory acceptance is slow. He
then popped back up last month raising security concerns. But I don't
see anyone that shares those concerns.

The unaccepted memory stuff is also _already_ touching the page
allocator. If it's a dumb idea, then we should be gleefully ripping it
out of the page allocator, not rejecting a 2-line kexec patch.

Baoquan has also said this looks good to him.

I'm happy to give Eric another week to respond in case he's on vacation
or something, but I'm honestly not seeing a good reason to hold this bug
fix up.

Andrew, is this the kind of thing you can stick into mm and hold on to
for a bit while we give Eric time to respond?

---

## [14] Jianxiong Gao — 2025-02-19
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination addresses*

> > It sounds like you're advocating for the "slow guest boot" option.
> > Kirill, can you remind us how fast a guest boots to the shell for
We have seen similar boot performance improvements on our larger shapes
of VMs. Both lazy accept and kexec with TDX are important features for us.


--
Jianxiong Gao

---

## [15] Dave Hansen — 2025-02-19
*Subject: Re: [PATCH v2 1/1] kexec_core: Accept unaccepted kexec segments'
 destination addresses*

On 12/13/24 01:54, Yan Zhao wrote:
> Accept the destination addresses during the kexec load, immediately after
> they pass sanity checks. This ensures the code is located in a common place

So, we've got an end-user-visible bug. Eric raised some good concerns
about the hardware and firmware design, but I think they've all been
addressed. The only other even solution I've seen proposed is to not do
unaccepted memory in the first place. I don't think that's viable or
justified, especially since we've got at least one end user[1] that
seems to think unaccepted memory fits their needs.

This bug can _probably_ be fixed in arch/x86 as well, but having the
solution in general code seems like the right place to me:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

Andrew, it seems like a lot of kexec work flows through you. Are you the
right one to pick this up?

1.
https://lore.kernel.org/all/CAMGD6P3r-S-Va-TRvVjZ808on9+-wFJ_VeTpQ+FEN1jBbhmnXw@mail.gmail.com/

---

## [16] Ashish Kalra — 2025-02-20
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination addresses*

> On Thu, Feb 13, 2025 at 07:55:15AM -0800, Dave Hansen wrote:
>> On 1/13/25 06:59, Eric W. Biederman wrote:

>I only have 128GB machine readily available and posted some number on
>other thread[1]:

>  On single vCPU it takes about a minute to accept 90GiB of memory.

>  It improves a bit with number of vCPUs. It is 40 seconds with 4 vCPU, but
>  it doesn't scale past that in my setup.

>I've mentioned it before in other thread:

>[1] https://lore.kernel.org/all/ihzvi5pwn5hrn4ky2ehjqztjxoixaiaby4igmeihqfehy2vrii@tsg6j5qvmyrm

We essentially rely on lazy acceptance support for reducing SNP guest boot time.

Here are some performance numbers for SNP guests which i have here after discussing with
Michael Roth (who is also CCed here): 

Just did quick boot of a 128GB SNP guest with accept_memory=lazy guest kernel parameter
and that took 22s to boot, and with accept_memory=eager it takes 3 minutes and 47s, so it 
is a remarkable difference.

Thanks,
Ashish

>-- 
>  Kiryl Shutsemau / Kirill A. Shutemov

---

## [17] Kirill A. Shutemov — 2025-03-04
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Fri, Feb 14, 2025 at 08:20:07AM -0800, Dave Hansen wrote:
> On 2/14/25 05:46, Kirill A. Shutemov wrote:
> >> It sounds like you're advocating for the "slow guest boot" option.

Andrew, Eric, can we get this patch in?

---

## [18] Eric W. Biederman — 2025-03-04
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

"Kirill A. Shutemov" <kirill.shutemov@linux.intel.com> writes:

> On Fri, Feb 14, 2025 at 08:20:07AM -0800, Dave Hansen wrote:
>> On 2/14/25 05:46, Kirill A. Shutemov wrote:

How goes the work to fix this horrifically slow firmware interface?

Eric

---

## [19] Dave Hansen — 2025-03-04
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On 3/4/25 10:49, Eric W. Biederman wrote:
> How goes the work to fix this horrifically slow firmware interface?

The firmware interface isn't actually all that slow.

The fundamental requirement is that confidential computing environments
need to be handed memory in a known-benign state. For AMD SEV
historically, that's meant doing things like flushing the caches so that
old cache evictions don't write to new data. For SGX, it's meant having
the CPU zero pages (in microcode) before adding them to an enclave.

For TDX, it's meant ensuring that TDX protections are in place, like the
memory integrity and "TD bit". But, those can't actually be set until
the page has been assigned to a TD since the integrity data is dependent
on the per-TD encryption key. But, the "memory integrity and TD bit" are
stored waaaaaaaay out in DRAM because they're pretty large structures
and aren't practical to store inside the CPU.

Even when the firmware isn't in play, it's still expensive to "convert"
pages back and forth to protected or not. See __prep_encrypted_page in
the MKTME series[1], for example. It was quite slow, requiring memset()s
and cache flushing, even though there was no firmware in sight. That's
exactly what the firmware is doing when you ask it to accept memory.

In other words, the process of ensuring that memory is sanitized before
going into a confidential computing environment is slow, not the
firmware interface.

I think what you're effectively asking for is either making DRAM faster,
or some other architecture that doesn't rely on going all the way out to
DRAM to sanitize a page.


1.
https://lore.kernel.org/lkml/20190731150813.26289-8-kirill.shutemov@linux.intel.com/t/

---

## [20] Andrew Morton — 2025-03-04
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Mon, 13 Jan 2025 19:12:27 +0800 Baoquan He <bhe@redhat.com> wrote:

> On 01/13/25 at 12:01pm, Kirill A. Shutemov wrote:
> > On Fri, Dec 13, 2024 at 05:49:30PM +0800, Yan Zhao wrote:

OK, but that patch is the only thing in the world which is older than me.

Yan, can you please refresh, retest and resend?

Also, please consolidate the changelogging into a single email -
a single-patch series with a coverletter is just weird.

Putting the [0/n] info into the singleton patch's changelog is more
reader-friendly, and that's what counts, no?

Thanks.

---

## [21] Andrew Morton — 2025-03-04
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Tue, 4 Mar 2025 15:43:53 -0800 Andrew Morton <akpm@linux-foundation.org> wrote:

> On Mon, 13 Jan 2025 19:12:27 +0800 Baoquan He <bhe@redhat.com> wrote:
> 

Oh, I remember this patch.

Eric, your feedback has been unusably-by-me enigmatic :(

In fact the whole multi-month review discussion has been quite
indecisive.

Yan, please go back through the discussion and incorporate reviewer
feedback into the changelogs: describe the possible issues which people
have raised and your responses to those.  Then resend and then let us
restart the review process.  With less reviewer latency please!

---

## [22] Andrew Morton — 2025-03-04
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Tue, 4 Mar 2025 15:53:27 -0800 Andrew Morton <akpm@linux-foundation.org> wrote:

> Yan, please go back through the discussion and incorporate reviewer
> feedback into the changelogs: describe the possible issues which people

Meanwhile, I'll add this old patch to mm.git to get some testing coverage.

---

## [23] Dave Hansen — 2025-03-12
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On 3/4/25 11:16, Dave Hansen wrote:
> On 3/4/25 10:49, Eric W. Biederman wrote:
>> How goes the work to fix this horrifically slow firmware interface?

Hey Eric,

I've noticed a trend on this series. It seems like every time there's
some forward progress on a fix, you pop up, and ask a question. Someone
answers the question. Then, a couple of months later, you seem to pop up
again and ask another form of the same question. It kinda seems to me
like you may not be thoroughly reading the answers from the previous
round of discussion. Or, maybe you're like me and have a hard time
recalling any discussions more than a week ago. ;)

Either way, I hope you're finally convinced that the hardware design
here is reasonable.

If not, I'd really like to continue the conversation now when this is
all fresh in our heads instead of having to poke at cold brain cells in
another month.

Any more questions, or can we finally put this issue to bed?

---

## [24] Kirill A. Shutemov — 2025-03-13
*Subject: Re: [PATCH v2 0/1] Accept unaccepted kexec segments' destination
 addresses*

On Tue, Mar 04, 2025 at 03:53:27PM -0800, Andrew Morton wrote:
> Yan, please go back through the discussion and incorporate reviewer
> feedback into the changelogs: describe the possible issues which people

Just in case it got missed, the updated patch is here:

https://lore.kernel.org/all/20250307084411.2150367-1-kirill.shutemov@linux.intel.com

---
