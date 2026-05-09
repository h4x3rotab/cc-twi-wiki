---
title: 'kexec_core: Accept unaccepted kexec destination addresses'
date: 2024-10-21
last_reply: 2024-12-04
message_count: 18
participants: ['Yan Zhao', 'Eric W. Biederman', 'Kirill A. Shutemov', 'Kirill A. Shutemov', 'Baoquan He']
---

## [1] Yan Zhao — 2024-10-21

The kexec destination addresses (incluing those for purgatory, the new
kernel, boot params/cmdline, and initrd) are searched from the free area of
memblock or RAM resources. Since they are not allocated by the currently
running kernel, it is not guaranteed that they are accepted before
relocating the new kernel.

Accept the destination addresses for the new kernel, as the new kernel may
not be able to or may not accept them by itself.

Place the "accept" code immediately after the destination addresses pass
sanity checks, so the code can be shared by both users of the kexec_load
and kexec_file_load system calls.

Cc: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
---
 kernel/kexec_core.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/kernel/kexec_core.c b/kernel/kexec_core.c
index c0caa14880c3..d97376eafc1a 100644
--- a/kernel/kexec_core.c
+++ b/kernel/kexec_core.c
@@ -210,6 +210,16 @@ int sanity_check_segment_list(struct kimage *image)
 	}
 #endif
 
+	/*
+	 * The destination addresses are searched from free memory ranges rather
+	 * than being allocated from the current kernel, so they are not
+	 * guaranteed to be accepted by the current kernel.
+	 * Accept those initial pages for the new kernel since it may not be
+	 * able to accept them by itself.
+	 */
+	for (i = 0; i < nr_segments; i++)
+		accept_memory(image->segment[i].mem, image->segment[i].memsz);
+
 	return 0;
 }
 
base-commit: 8cf0b93919e13d1e8d4466eb4080a4c4d9d66d7b

---

## [2] Eric W. Biederman — 2024-10-21
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

Yan Zhao <yan.y.zhao@intel.com> writes:

> The kexec destination addresses (incluing those for purgatory, the new
> kernel, boot params/cmdline, and initrd) are searched from the free area of

I am not at all certain this is sufficient, and I am a bit flummoxed
about the need to ever ``accept'' memory lazily.

In a past life I wrote bootup firmware, and as part of that was the code
to initialize the contents of memory.  When properly tuned and setup it
would never take more than a second to just blast initial values into
memory.  That is because the ratio of memory per memory controller to
memory bandwidth stayed roughly constant while I was paying attention.
I expect that ratio to continue staying roughly constant or systems
will quickly start developing unacceptable boot times.

As I recall Intel TDX is where the contents of memory are encrypted per
virtual machine.  Which implies that you have the same challenge as
bootup initializing memory, and that is what ``accepting'' memory is.

I am concerned that an unfiltered accept_memory may result in memory
that has already been ``accepted'' being accepted again.  This has
the potential to be wasteful in the best case, and the potential to
cause memory that is in use to be reinitialized losing the values
that are currently stored there.

I am concerned that the target kernel won't know about about accepting
memory, or might not perform the work early enough and try to use memory
without accepting it first.

I would much prefer if getting into kexec_load would force the memory
acceptance out of lazy mode (or possibly not even work in lazy mode).
That keeps things simple for now.

Once enough people have machines requiring the use of accept_memory
we can worry about optimizing things and pushing the accept_memory call
down into kexec_load.



Ugh.  I just noticed another issue.  Unless the memory we are talking
about is the memory reserved for kexec on panic kernels the memory needs
struct pages and everything setup so it can be allocated from anyway.

Which is to say I think this is has the potential to conflict with
the accounting in try_to_accept_memory.

Please just make memory acceptance ``eager'' non-lazy when using kexec.
Unless someone has messed their implementation badly it won't be a
significant amount of time in human terms, and it makes the code
so much easier to understand and think about.

Eric


> Cc: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [3] Yan Zhao — 2024-10-22
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Mon, Oct 21, 2024 at 09:33:17AM -0500, Eric W. Biederman wrote:
> Yan Zhao <yan.y.zhao@intel.com> writes:
> 
Yes, the kernel actually will accept initial memory used by itself in
extract_kernel(), as in arch/x86/boot/compressed/misc.c.

But the target kernel may not be able to accept memory for purgatory.
And it's currently does not accept memory for boot params/cmdline,
and initrd .

> 
> I am concerned that an unfiltered accept_memory may result in memory
accept_memory() will not accept memory that has already been accepted.
An unaccepted->bitmap is maintained and queried before accepting.
(this is at least the implementation in
drivers/firmware/efi/unaccepted_memory.c)

If it's still a concern to you, is it better to add a check like this?

if (range_contains_unaccepted_memory(mstart, size))
	accept_memory(mstart, size);

> 
> I am concerned that the target kernel won't know about about accepting
The target kernel does accept memory before use it. But not including those
in kexec segments for purgatory, boot params/cmdline, and initrd.


> I would much prefer if getting into kexec_load would force the memory
> acceptance out of lazy mode (or possibly not even work in lazy mode).
Then could we put the accept into machine_kexec(), given that accept_memory()
will not fail?

> 
> Please just make memory acceptance ``eager'' non-lazy when using kexec.
yes, it's also an approach if the above cannot convince you.

> 
>

---

## [4] Kirill A. Shutemov — 2024-10-22
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Mon, Oct 21, 2024 at 09:33:17AM -0500, Eric W. Biederman wrote:
> Yan Zhao <yan.y.zhao@intel.com> writes:
> 

It is not unfiltered. We check it against bitmap that maintains the
accept status of the memory block.

> This has
> the potential to be wasteful in the best case, and the potential to

The bitmap I mentioned above passed between two kernels via an EFI config
table. This mechanism predates kexec enabling of the systems with
unaccepted memory support, so there should not be a problem.

> I would much prefer if getting into kexec_load would force the memory
> acceptance out of lazy mode (or possibly not even work in lazy mode).

You can always force this behaviour with accept_memory=eager, but it is
waaay slower for larger VMs. It is especially bad idea if kexec used as
initial bootloader and most of the memory is not yet accepted by the time
kexec is triggered.

> Once enough people have machines requiring the use of accept_memory
> we can worry about optimizing things and pushing the accept_memory call

It is already here and it works. Despite some bugs that need to be
addressed.

> Ugh.  I just noticed another issue.  Unless the memory we are talking
> about is the memory reserved for kexec on panic kernels the memory needs

I am not sure I follow. Could you please elaborate?

> Which is to say I think this is has the potential to conflict with
> the accounting in try_to_accept_memory.

Waiting minutes to get VM booted to shell is not feasible for most
deployments. Lazy is sane default to me.

---

## [5] Eric W. Biederman — 2024-10-23
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

"Kirill A. Shutemov" <kirill@shutemov.name> writes:

> Waiting minutes to get VM booted to shell is not feasible for most
> deployments. Lazy is sane default to me.

Huh?

Unless my guesses about what is happening are wrong lazy is hiding
a serious implementation deficiency.  From all hardware I have seen
taking minutes is absolutely ridiculous.

Does writing to all of memory at full speed take minutes?  How can such
a system be functional?

If you don't actually have to write to the pages and it is just some
accounting function it is even more ridiculous.


I had previously thought that accept_memory was the firmware call.
Now that I see that it is just a wrapper for some hardware specific
calls I am even more perplexed.


Quite honestly what this looks like to me is that someone failed to
enable write-combining or write-back caching when writing to memory
when initializing the protected memory.  With the result that everything
is moving dog slow, and people are introducing complexity left and write
to avoid that bad implementation.


Can someone please explain to me why this accept_memory stuff has to be
slow, why it has to take minutes to do it's job.

I would much rather spend my time figuring out how to make accept_memory
run at a reasonable speed than to litter the kernel with more of this
nonsense.

Eric

---

## [6] Yan Zhao — 2024-10-24
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Wed, Oct 23, 2024 at 10:44:11AM -0500, Eric W. Biederman wrote:
> "Kirill A. Shutemov" <kirill@shutemov.name> writes:
> 
This kexec patch is a fix to a guest(TD)'s kexce failure.

For a linux guest, the accept_memory() happens before the guest accesses a page.
It will (if the guest is a TD)
(1) trigger the host to allocate the physical page on host to map the accessed
    guest page, which might be slow with wait and sleep involved, depending on
    the memory pressure on host.
(2) initializing the protected page.

Actually most of guest memory are not accessed by guest during the guest life
cycle. accept_memory() may cause the host to commit a never-to-be-used page,
with the host physical page not even being able to get swapped out.

That's why we need a lazy accept, which does not accept_memory() until after a
page is allocated by the kernel (in alloc_page(s)).

> I would much rather spend my time figuring out how to make accept_memory
> run at a reasonable speed than to litter the kernel with more of this

---

## [7] Yan Zhao — 2024-10-24
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Thu, Oct 24, 2024 at 08:15:13AM +0800, Yan Zhao wrote:
> On Wed, Oct 23, 2024 at 10:44:11AM -0500, Eric W. Biederman wrote:
> > "Kirill A. Shutemov" <kirill@shutemov.name> writes:
                                                                        ^^^^^^^^
s/accessed/specified

>     guest page, which might be slow with wait and sleep involved, depending on
>     the memory pressure on host.

---

## [8] Kirill A. Shutemov — 2024-10-25
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Wed, Oct 23, 2024 at 10:44:11AM -0500, Eric W. Biederman wrote:
> "Kirill A. Shutemov" <kirill@shutemov.name> writes:
> 

It is not only memory write (to encrypt the memory), but also TDCALL which
is TD-exit on every page. That is costly in TDX case.

On single vCPU it takes about a minute to accept 90GiB of memory.

It improves a bit with number of vCPUs. It is 40 seconds with 4 vCPU, but
it doesn't scale past that in my setup.

But it is all rather pathological: VMM doesn't support huge pages yet and
all memory is accepted in 4K chunks. Bringing 2M support would cut number
of TDCALLs by 512.

Once memory accepted, memory access cost is comparable to bare metal minus
usual virtualisation tax on page walk.

I don't know what the picture looks like in AMD case.
j
> If you don't actually have to write to the pages and it is just some
> accounting function it is even more ridiculous.

It is hypercall basically. The feature is only used in guests so far.

---

## [9] Kirill A. Shutemov — 2024-11-04
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Fri, Oct 25, 2024 at 04:56:41PM +0300, Kirill A. Shutemov wrote:
> On Wed, Oct 23, 2024 at 10:44:11AM -0500, Eric W. Biederman wrote:
> > "Kirill A. Shutemov" <kirill@shutemov.name> writes:

Eric, can we get the patch applied? It fixes a crash.

---

## [10] Kirill A. Shutemov — 2024-11-08
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Mon, Nov 04, 2024 at 10:35:53AM +0200, Kirill A. Shutemov wrote:
> On Fri, Oct 25, 2024 at 04:56:41PM +0300, Kirill A. Shutemov wrote:
> > On Wed, Oct 23, 2024 at 10:44:11AM -0500, Eric W. Biederman wrote:

Ping?

---

## [11] Baoquan He — 2024-11-26
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On 10/24/24 at 08:15am, Yan Zhao wrote:
> On Wed, Oct 23, 2024 at 10:44:11AM -0500, Eric W. Biederman wrote:
> > "Kirill A. Shutemov" <kirill@shutemov.name> writes:

So this sounds to me more like a business requirement on cloud platform,
e.g if one customer books a guest instance with 60G memory, while the
customer actually always only cost 20G memory at most. Then the 40G memory
can be saved to reduce pressure for host. I could be shallow, just a wild
guess.

If my guess is right, at least those cloud service providers must like this
accept_memory feature very much.

> 
> That's why we need a lazy accept, which does not accept_memory() until after a

By the way, I have two questions, maybe very shallow.

1) why can't we only find those already accepted memory to put kexec
kernel/initrd/bootparam/purgatory?

2) why can't we accept memory for (kernel, boot params/cmdline/initrd)
in 2nd kernel? Surely this purgatory still need be accepted in 1st kernel.
Sorry, I just read accept_memory() code, haven't gone through x86 boot
code flow.

Thanks
Baoquan

---

## [12] Yan Zhao — 2024-11-27
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Tue, Nov 26, 2024 at 07:38:05PM +0800, Baoquan He wrote:
> On 10/24/24 at 08:15am, Yan Zhao wrote:
> > On Wed, Oct 23, 2024 at 10:44:11AM -0500, Eric W. Biederman wrote:
Yes.

> I could be shallow, just a wild guess.
> If my guess is right, at least those cloud service providers must like this

Currently, the first kernel only accepts memory during the memory allocation in
a lazy accept mode. Besides reducing boot time, it's also good for memory
over-commitment as you mentioned above.

My understanding of why the memory for the kernel/initrd/bootparam/purgatory is
not allocated from the first kernel is that this memory usually needs to be
physically contiguous. Since this memory will not be used by the first kernel,
looking up from free RAM has a lower chance of failure compared to allocating it
from the first kernel, especially when memory pressure is high in the first
kernel.

 
> 2) why can't we accept memory for (kernel, boot params/cmdline/initrd)
> in 2nd kernel? Surely this purgatory still need be accepted in 1st kernel.
If a page is not already accepted, invoking accept_memory() will trigger a
memory accept to zero-out the page content. So, for the pages passed to the
second kernel, they must have been accepted before page content is copied in.

For boot params/cmdline/initrd, perhaps we could make those pages in shared
memory initially and have the second kernel to accept private memory for copy.
However, that would be very complex and IMHO not ideal.

---

## [13] Baoquan He — 2024-11-28
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On 11/27/24 at 06:01pm, Yan Zhao wrote:
> On Tue, Nov 26, 2024 at 07:38:05PM +0800, Baoquan He wrote:
> > On 10/24/24 at 08:15am, Yan Zhao wrote:

That's very interesting, thanks for confirming.

> 
> > I could be shallow, just a wild guess.

Well, there could be misunderstanding here.The final loaded position of
kernel/initrd/bootparam/purgatory is not searched from free RAM, it's
just from RAM on x86. Means it possibly have been allocated and being
used by other component of 1st kernel. Not like kdump, the 2nd kernel of
kexec reboot doesn't care about 1st kernel's memory usage. We will copy
them from intermediat position to the designated location when jumping.

If we take this way, we need search unaccepted->bitmap top down or
bottom up, according to setting. Then another suit of functions need
be provided. That looks a little complicated.

kexec_add_buffer()
-->arch_kexec_locate_mem_hole()
   -->kexec_locate_mem_hole()
      -->kexec_walk_memblock(kbuf, locate_mem_hole_callback) -- on arm64
      -->kexec_walk_resources(kbuf, locate_mem_hole_callback) -- on x86
         -->walk_system_ram_res_rev()

Besides, the change in your patch has one issue. Usually we do kexec load to
read in the kernel/initrd/bootparam/purgatory, while they are loaded to
the destinations till kexec jumping. We could do kexec loading while 
never trigger the jumping, your change have done the accept_memory().
But this doesn't impact much because it always searched and found the
same location on one system.

> from the first kernel, especially when memory pressure is high in the first
> kernel.

I asked this because I saw your reply to Eric in another thread, quote
your saying at below. I am wondering why kernel can accept itself, why
other parts can't do it similarly.
=====
Yes, the kernel actually will accept initial memory used by itself in
extract_kernel(), as in arch/x86/boot/compressed/misc.c.

But the target kernel may not be able to accept memory for purgatory.
And it's currently does not accept memory for boot params/cmdline,
and initrd .
====

---

## [14] Yan Zhao — 2024-11-29
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Thu, Nov 28, 2024 at 11:19:20PM +0800, Baoquan He wrote:
> On 11/27/24 at 06:01pm, Yan Zhao wrote:
> > On Tue, Nov 26, 2024 at 07:38:05PM +0800, Baoquan He wrote:
Oh, by free RAM, I mean system RAM that is marked as
IORESOURCE_SYSTEM_RAM | IORESOURCE_BUSY, but not marked as
IORESOURCE_SYSRAM_DRIVER_MANAGED.


> just from RAM on x86. Means it possibly have been allocated and being
> used by other component of 1st kernel. Not like kdump, the 2nd kernel of
Yes, it's entirely possible that the destination address being searched out has
already been allocated and is in use by the 1st kernel. e.g. for
KEXEC_TYPE_DEFAULT, the source page for each segment is allocated from the 1st
kernel, and it is allowed to have the same address as its corresponding
destination address.

However, it's not guaranteed that the destination address must have been
allocated by the 1st kernel.

> kexec reboot doesn't care about 1st kernel's memory usage. We will copy
> them from intermediat position to the designated location when jumping.
Right. If it's not guaranteed that the destination address has been accepted
before this copying, the copying could trigger an error due to accessing an
unaccepted page, which could be fatal for a linux TDX guest.

> If we take this way, we need search unaccepted->bitmap top down or
> bottom up, according to setting. Then another suit of functions need
Do you mean searching only accepted pages as destination addresses?
That might increase the chance of failure compared to accepting the addressed
being searched out.

> kexec_add_buffer()
> -->arch_kexec_locate_mem_hole()

Yes.


> Besides, the change in your patch has one issue. Usually we do kexec load to
> read in the kernel/initrd/bootparam/purgatory, while they are loaded to
Right.
Do you think it's good to move the accept to machine_kexec()?
The machine_kexec() is platform specific though.

> > from the first kernel, especially when memory pressure is high in the first
> > kernel.
Thanks for pointing this out.
I also found that my previous reply was confusing and misleading.

The 2nd kernel will accept the addresses before it decompresses itself there.
Since these addresses are somewhere "random", the 2nd kernel (and for the 1st
kernel for itself) needs to call accept_memory() in case that they might not
have been accepted.

So, previously, I thought a workable approach might be for kexec to map the
destination addresses in shared memory, perform the copy/jump, and then have the
2nd kernel accept the addresses for decompressing and other parts.
However, aside from the complications and security concerns, this approach is
problematic because the 2nd kernel may clear the pages by accepting them if the
addresses for decompressing overlap with the ones before decompressing.

That said, would it be acceptable if I update the patch log and maybe also move
the accept call to machine_kexec()?

New patch log:
The kexec segments's destination addresses are searched from the memblock
or RAM resources. They are not allocated by the first kernel, though they
may overlap with the memory in used by the first kernel. So, it is not
guaranteed that they are accepted before kexec relocates to the second
kernel.

Accept the destination addresses before kexec relocates to the second
kernel, since kexec would access them by swapping content of source and
destination pages.

---

## [15] Baoquan He — 2024-12-02
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On 11/29/24 at 01:52pm, Yan Zhao wrote:
> On Thu, Nov 28, 2024 at 11:19:20PM +0800, Baoquan He wrote:
> > On 11/27/24 at 06:01pm, Yan Zhao wrote:

Oh, I just said the opposite. I meant we could search according to the
current unaccepted->bitmap to make sure the destination area definitely
have been accepted. This is the best if doable, while I know it's not
easy.

> 
> > If we take this way, we need search unaccepted->bitmap top down or

I am not sure if it's appropriate to accept in machine_kexec(). 

> 
> > > from the first kernel, especially when memory pressure is high in the first

Hmm, I think a repost seems necessary, even though this patch looks good
to me. If I do, I would add a cover letter to present with several sections:

1) background information: to explain what scenario the accept memory is
used for. And why accept all memory in kexec reboot case is not
expected.
2) the current problem: a brief description of the problem and itsroot cause;
3) How to fix it: here we can list all possible solutions we can thin of
and what drawbacks they have so that they are not chosen. Then we can
come to the final sotution that your current patch has to resort to
take.

As kexec maintainer, Eric's concerns are very important and need be resolved 
with as much information as possible to let him be happy with the
change, at least let him not hate it. This is my personal suggestion as a
reviewer. You can put them into cover letter if you think it's not good to add
them all in a standalone patch.

> 
> New patch log:

---

## [16] Yan Zhao — 2024-12-03
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Mon, Dec 02, 2024 at 10:17:16PM +0800, Baoquan He wrote:
> On 11/29/24 at 01:52pm, Yan Zhao wrote:
> > On Thu, Nov 28, 2024 at 11:19:20PM +0800, Baoquan He wrote:
Well, this sounds like introducing a new constraint in addition to the current
checking of !kimage_is_destination_range() in locate_mem_hole_top_down() or
locate_mem_hole_bottom_up(). (powerpc also has a different implementation).

This could make the success unpredictable, depending on how many pages have
been accepted by the 1st kernel and the layout of the accepted pages(e.g.,
whether they are physically contiguous). The 1st kernel would also have no
reliable way to ensure success except by accepting all the guest pages.

> > 
> > > If we take this way, we need search unaccepted->bitmap top down or
Thanks for this suggestion!
 
> As kexec maintainer, Eric's concerns are very important and need be resolved 
> with as much information as possible to let him be happy with the
My apologies. I will first repost a new version with the current implementation,
including more background and explanations to address Eric's concerns.

Thank you!

> 
> >

---

## [17] Baoquan He — 2024-12-03
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On 12/03/24 at 06:06pm, Yan Zhao wrote:
> On Mon, Dec 02, 2024 at 10:17:16PM +0800, Baoquan He wrote:
> > On 11/29/24 at 01:52pm, Yan Zhao wrote:

Yeah, when I finished reading accept_memory code, this is the first idea
which come up into my mind. If it can be made, it's the most ideal. When
I tried to make a draft change, it does introduce a lot of code change and
add very much complication and I just gave up.

Maybe this can be added to cover-letter too to tell this possible path we
explored.

---

## [18] Yan Zhao — 2024-12-04
*Subject: Re: [PATCH] kexec_core: Accept unaccepted kexec destination addresses*

On Tue, Dec 03, 2024 at 06:30:36PM +0800, Baoquan He wrote:
> On 12/03/24 at 06:06pm, Yan Zhao wrote:
> > On Mon, Dec 02, 2024 at 10:17:16PM +0800, Baoquan He wrote:
...
> > > Oh, I just said the opposite. I meant we could search according to the
> > > current unaccepted->bitmap to make sure the destination area definitely
Ok.

---
