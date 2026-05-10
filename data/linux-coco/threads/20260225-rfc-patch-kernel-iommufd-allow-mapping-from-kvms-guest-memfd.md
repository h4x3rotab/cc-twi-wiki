---
title: "[RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd"
date: 2026-02-25
last_reply: 2026-02-28
message_count: 15
participants: ['Alexey Kardashevskiy', 'Sean Christopherson', 'Ackerley Tng', 'Jason Gunthorpe', 'Xu Yilun']
---

## [1] Alexey Kardashevskiy — 2026-02-25

CoCo VMs get their private memory allocated from guest_memfd
("gmemfd") which is a KVM facility similar to memfd.
The gmemfds does not allow mapping private memory to the userspace
so the IOMMU_IOAS_MAP ioctl does not work.

Use the existing IOMMU_IOAS_MAP_FILE ioctl to allow mapping from
fd + offset. Detect the gmemfd case in pfn_reader_user_pin().

For the new guest_memfd type, no additional reference is taken as
pinning is guaranteed by the KVM guest_memfd library.

There is no KVM-GMEMFD->IOMMUFD direct notification mechanism as
the assumption is that:
1) page stage change events will be handled by VMM which is going
to call IOMMUFD to remap pages;
2) shrinking GMEMFD equals to VM memory unplug and VMM is going to
handle it.

Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

This is for Trusted IO == TEE-IO == PCIe TDISP, etc.

Previously posted here:
https://lore.kernel.org/r/20250218111017.491719-13-aik@amd.com
The main comment was "what is the lifetime of those folios()" and
GMEMFD + QEMU should take care of it.

And horrendous stuff like this is not really useful:
https://github.com/AMDESE/linux-kvm/commit/7d73fd2cccb8489b1

---
 include/linux/kvm_host.h      |  4 +
 drivers/iommu/iommufd/pages.c | 80 ++++++++++++++++++--
 virt/kvm/guest_memfd.c        | 36 +++++++++
 3 files changed, 113 insertions(+), 7 deletions(-)

diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 995db7a7ba57..9369cf22b24e 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2673,4 +2673,8 @@ unsigned long kvm_get_vm_memory_attributes(struct kvm *kvm, gfn_t gfn);
 int kvm_vm_ioctl_set_mem_attributes(struct kvm *kvm,
 					   struct kvm_memory_attributes2 *attrs);
 
+bool kvm_is_gmemfd(struct file *file);
+struct folio *kvm_gmemfd_get_pfn(struct file *file, unsigned long index,
+				 unsigned long *pfn, int *max_order);
+
 #endif
diff --git a/drivers/iommu/iommufd/pages.c b/drivers/iommu/iommufd/pages.c
index dbe51ecb9a20..4c07e39e17d0 100644
--- a/drivers/iommu/iommufd/pages.c
+++ b/drivers/iommu/iommufd/pages.c
@@ -56,6 +56,9 @@
 #include <linux/slab.h>
 #include <linux/sched/mm.h>
 #include <linux/vfio_pci_core.h>
+#include <linux/pagemap.h>
+#include <linux/memcontrol.h>
+#include <linux/kvm_host.h>
 
 #include "double_span.h"
 #include "io_pagetable.h"
@@ -660,7 +663,8 @@ static void batch_from_pages(struct pfn_batch *batch, struct page **pages,
 }
 
 static int batch_from_folios(struct pfn_batch *batch, struct folio ***folios_p,
-			     unsigned long *offset_p, unsigned long npages)
+			     unsigned long *offset_p, unsigned long npages,
+			     bool do_pin)
 {
 	int rc = 0;
 	struct folio **folios = *folios_p;
@@ -676,7 +680,7 @@ static int batch_from_folios(struct pfn_batch *batch, struct folio ***folios_p,
 
 		if (!batch_add_pfn_num(batch, pfn, nr, BATCH_CPU_MEMORY))
 			break;
-		if (nr > 1) {
+		if (nr > 1 && do_pin) {
 			rc = folio_add_pins(folio, nr - 1);
 			if (rc) {
 				batch_remove_pfn_num(batch, nr);
@@ -697,6 +701,7 @@ static int batch_from_folios(struct pfn_batch *batch, struct folio ***folios_p,
 static void batch_unpin(struct pfn_batch *batch, struct iopt_pages *pages,
 			unsigned int first_page_off, size_t npages)
 {
+	bool do_unpin = !kvm_is_gmemfd(pages->file);
 	unsigned int cur = 0;
 
 	while (first_page_off) {
@@ -710,9 +715,12 @@ static void batch_unpin(struct pfn_batch *batch, struct iopt_pages *pages,
 		size_t to_unpin = min_t(size_t, npages,
 					batch->npfns[cur] - first_page_off);
 
-		unpin_user_page_range_dirty_lock(
-			pfn_to_page(batch->pfns[cur] + first_page_off),
-			to_unpin, pages->writable);
+		/* Do nothing for guest_memfd */
+		if (do_unpin)
+			unpin_user_page_range_dirty_lock(
+				pfn_to_page(batch->pfns[cur] + first_page_off),
+				to_unpin, pages->writable);
+
 		iopt_pages_sub_npinned(pages, to_unpin);
 		cur++;
 		first_page_off = 0;
@@ -872,6 +880,57 @@ static long pin_memfd_pages(struct pfn_reader_user *user, unsigned long start,
 	return npages_out;
 }
 
+static long pin_guest_memfd_pages(struct pfn_reader_user *user, loff_t start, unsigned long npages)
+{
+	struct page **upages = user->upages;
+	unsigned long offset = 0;
+	loff_t uptr = start;
+	long rc = 0;
+
+	for (unsigned long i = 0; (uptr - start) < (npages << PAGE_SHIFT); ++i) {
+		unsigned long gfn = 0, pfn = 0;
+		int max_order = 0;
+		struct folio *folio;
+
+		folio = kvm_gmemfd_get_pfn(user->file, uptr >> PAGE_SHIFT, &pfn, &max_order);
+		if (IS_ERR(folio))
+			rc = PTR_ERR(folio);
+
+		if (rc == -EINVAL && i == 0) {
+			pr_err_once("Must be vfio mmio at gfn=%lx pfn=%lx, skipping\n", gfn, pfn);
+			return rc;
+		}
+
+		if (rc) {
+			pr_err("%s: %ld %ld %lx -> %lx\n", __func__,
+			       rc, i, (unsigned long) uptr, (unsigned long) pfn);
+			break;
+		}
+
+		if (i == 0)
+			offset = offset_in_folio(folio, start) >> PAGE_SHIFT;
+
+		user->ufolios[i] = folio;
+
+		if (upages) {
+			unsigned long np = (1UL << (max_order + PAGE_SHIFT)) - offset_in_folio(folio, uptr);
+
+			for (unsigned long j = 0; j < np; ++j)
+				*upages++ = folio_page(folio, offset + j);
+		}
+
+		uptr += (1UL << (max_order + PAGE_SHIFT)) - offset_in_folio(folio, uptr);
+	}
+
+	if (!rc) {
+		rc = npages;
+		user->ufolios_next = user->ufolios;
+		user->ufolios_offset = offset;
+	}
+
+	return rc;
+}
+
 static int pfn_reader_user_pin(struct pfn_reader_user *user,
 			       struct iopt_pages *pages,
 			       unsigned long start_index,
@@ -925,7 +984,13 @@ static int pfn_reader_user_pin(struct pfn_reader_user *user,
 
 	if (user->file) {
 		start = pages->start + (start_index * PAGE_SIZE);
-		rc = pin_memfd_pages(user, start, npages);
+		if (kvm_is_gmemfd(pages->file)) {
+			rc = pin_guest_memfd_pages(user, start, npages);
+		} else {
+			pr_err("UNEXP PINFD start=%lx sz=%lx file=%lx",
+				start, npages << PAGE_SHIFT, (ulong) pages->file);
+			rc = pin_memfd_pages(user, start, npages);
+		}
 	} else if (!remote_mm) {
 		uptr = (uintptr_t)(pages->uptr + start_index * PAGE_SIZE);
 		rc = pin_user_pages_fast(uptr, npages, user->gup_flags,
@@ -1221,7 +1286,8 @@ static int pfn_reader_fill_span(struct pfn_reader *pfns)
 				 npages);
 	else
 		rc = batch_from_folios(&pfns->batch, &user->ufolios_next,
-				       &user->ufolios_offset, npages);
+				       &user->ufolios_offset, npages,
+				       !kvm_is_gmemfd(pfns->pages->file));
 	return rc;
 }
 
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index e4e21068cf2a..2a313888c21b 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1794,3 +1794,39 @@ void kvm_gmem_exit(void)
 	rcu_barrier();
 	kmem_cache_destroy(kvm_gmem_inode_cachep);
 }
+
+bool kvm_is_gmemfd(struct file *file)
+{
+	if (!file)
+		return false;
+
+	if (file->f_op != &kvm_gmem_fops)
+		return false;
+
+	return true;
+}
+EXPORT_SYMBOL_GPL(kvm_is_gmemfd);
+
+struct folio *kvm_gmemfd_get_pfn(struct file *file, unsigned long index,
+				 unsigned long *pfn, int *max_order)
+{
+	struct inode *inode = file_inode(file);
+	struct folio *folio;
+
+	if (!inode || !kvm_is_gmemfd(file))
+		return NULL;
+
+	folio = kvm_gmem_get_folio(inode, index);
+	if (!folio)
+		return NULL;
+
+
+	*pfn = folio_pfn(folio) + (index & (folio_nr_pages(folio) - 1));
+	*max_order = folio_order(folio);
+
+	folio_put(folio);
+	folio_unlock(folio);
+
+	return folio;
+}
+EXPORT_SYMBOL_GPL(kvm_gmemfd_get_pfn);

---

## [2] Sean Christopherson — 2026-02-25
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Wed, Feb 25, 2026, Alexey Kardashevskiy wrote:
> For the new guest_memfd type, no additional reference is taken as
> pinning is guaranteed by the KVM guest_memfd library.

The VMM is outside of the kernel's effective TCB.  Assuming the VMM will always
do the right thing is a non-starter.

---

## [3] Alexey Kardashevskiy — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On 26/2/26 00:55, Sean Christopherson wrote:
> On Wed, Feb 25, 2026, Alexey Kardashevskiy wrote:
>> For the new guest_memfd type, no additional reference is taken as

Right.

But, say, for 1), VMM does not the right thing and skips on PSC - the AMD host will observe IOMMU fault events - noisy but harmless. I wonder if it is different for others though.

Truncating gmemfd is bad, is having gmemfd->iommufd notification going to be enough for a starter? Thanks,

---

## [4] Ackerley Tng — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

Sean Christopherson <seanjc@google.com> writes:

> On Wed, Feb 25, 2026, Alexey Kardashevskiy wrote:
>> For the new guest_memfd type, no additional reference is taken as

I think looking up the guest_memfd file from the userspace address
(uptr) is a good start, and in order not to assume much of the userspace
VMM, we could register the mapping with guest_memfd, so that when
there's a conversion or truncation, guest_memfd will invalidate the
registered mapping in addition to the rest of the mappings being
invalidated.

At LPC (2025) [1][2], people pointed out that needing to force unmapping during
page state changes (aka conversions) are a TDX-only issue. It seems like
on SNP and ARM, the faults generated due to the host accessing guest
private memory can be caught and handled, so it's not super terrible if
there's no unmapping during conversions. Perhaps Alexey and Aneesh can
explain more :)

Will said pKVM actually would rather not unmap from the IOMMU on
conversions.

I didn't think of this before LPC but forcing unmapping during
truncation (aka shrinking guest_memfd) is probably necessary for overall
system stability and correctness, so notifying and having guest_memfd
track where its pages were mapped in the IOMMU is necessary. Whether or
not to unmap during conversions could be a arch-specific thing, but all
architectures would want the memory unmapped if the memory is removed
from guest_memfd ownership.

[1] Slides: https://lpc.events/event/19/contributions/2184/attachments/1752/3816/2025-12-12-lpc-coco-mc-optimizing-guest-memfd-conversions.pdf
[2] Notes: https://github.com/joergroedel/coco-microconference/blob/main/2025/optimizing_guest_memfd_shared_private_conversions.md

---

## [5] Jason Gunthorpe — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026 at 12:19:52AM -0800, Ackerley Tng wrote:
> Sean Christopherson <seanjc@google.com> writes:
> 

Please no, if we need complicated things like notifiers then it is
better to start directly with the struct file interface and get
immediately into some guestmemfd API instead of trying to get their
from a VMA. A VMA doesn't help in any way and just complicates things.

> I didn't think of this before LPC but forcing unmapping during
> truncation (aka shrinking guest_memfd) is probably necessary for overall

Things like truncate are a bit easier to handle, you do need a
protective notifier, but if it detects truncate while an iommufd area
still covers the truncated region it can just revoke the whole
area. Userspace made a mistake and gets burned but the kernel is
safe. We don't need something complicated kernel side to automatically
handle removing just the slice of truncated guestmemfd, for example.

If guestmemfd is fully pinned and cannot free memory outside of
truncate that may be good enough (though somehow I think that is not
the case) - and I don't understand what issues Intel has with iommu
access.

Jason

---

## [6] Jason Gunthorpe — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026 at 05:47:50PM +1100, Alexey Kardashevskiy wrote:
> 
> 

ARM is also supposed to be safe as GPT faults are contained, IIRC.

However, it is not like AMD in many important ways here. Critically ARM
has a split guest physical space where the low addresses are all
private and the upper addresses are all shared.

Thus on Linux the iommu should be programed with the shared pages
mapped into the shared address range. It would be wasteful to program
it with large amounts of IOPTEs that are already know to be private.

I think if you are fully doing in-place conversion then you could
program the entire shared address range to point to the memory pool
(eg with 1G huge pages) and rely entirely on the GPT to arbitrate
access. I don't think that is implemented in Linux though?

While on AMD, IIRC, the iommu should be programed with both the shared
and private pages in the respective GPA locations, but due to the RMP
matching insanity you have to keep restructuring the IOPTEs to exactly
match the RMP layout.

I have no idea what Intel needs.

Jason

---

## [7] Sean Christopherson — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026, Jason Gunthorpe wrote:
> On Thu, Feb 26, 2026 at 12:19:52AM -0800, Ackerley Tng wrote:
> > Sean Christopherson <seanjc@google.com> writes:

+1000.  Anything that _requires_ a VMA to do something with guest_memfd is broken
by design.

> > I didn't think of this before LPC but forcing unmapping during
> > truncation (aka shrinking guest_memfd) is probably necessary for overall

Yeah, as long as the behavior is well-documented from time zero, we can probably
get away with fairly draconian behavior.

> If guestmemfd is fully pinned and cannot free memory outside of
> truncate that may be good enough (though somehow I think that is not

With in-place conversion, PUNCH_HOLE and private=>shared conversions are the only
two ways to partial "remove" memory from guest_memfd, so it may really be that
simple.

---

## [8] Jason Gunthorpe — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026 at 02:40:50PM -0800, Sean Christopherson wrote:

> > If guestmemfd is fully pinned and cannot free memory outside of
> > truncate that may be good enough (though somehow I think that is not

PUNCH_HOLE can be treated like truncate right?

I'm confused though - I thought in-place conversion ment that
private<->shared re-used the existing memory allocation? Why does it
"remove" memory?

Or perhaps more broadly, where is the shared memory kept/accessed in
these guest memfd systems?

Jason

---

## [9] Sean Christopherson — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026, Jason Gunthorpe wrote:
> On Thu, Feb 26, 2026 at 02:40:50PM -0800, Sean Christopherson wrote:
> 

Yep.  Tomato, tomato.  I called out PUNCH_HOLE because guest_memfd doesn't support
a pure truncate, the size is immutable (ignoring that destroying the inode is kinda
sorta a truncate).

> I'm confused though - I thought in-place conversion ment that
> private<->shared re-used the existing memory allocation? Why does it

Oh, the physical memory doesn't change, but the IOMMU might care that memory is
being converted from private<=>shared.  AMD IOMMU probably doesn't?  But unless
Intel IOMMU reuses S-EPT from the VM itself, the IOMMU page tables will need to
be updated.

FWIW, conceptually, we're basically treating private=>shared in particular as
"free() + alloc()" that just so happens to guarantee the allocated page is the same.

---

## [10] Jason Gunthorpe — 2026-02-26
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026 at 04:28:53PM -0800, Sean Christopherson wrote:
> > I'm confused though - I thought in-place conversion ment that
> > private<->shared re-used the existing memory allocation? Why does it

Okay, so then it is probably OK for AMD and ARM to just let
shared/private happen and whatever userspace does or doesn't do is not
important. The IOPTE will point at guaranteed allocated memory and any
faults caused by imporerly putting private in a shared slot will be
contained.

I have no idea what happens to Intel if the shared IOMMU points to a
private page? The machine catches fire and daemons spawn from a
fissure?

Or maybe we are lucky and it generates a nice contained fault like the
other two so we don't need to build something elaborate and special to
make up for horrible hardware? Pretty please?

Jason

---

## [11] Xu Yilun — 2026-02-27
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026 at 09:09:02PM -0400, Jason Gunthorpe wrote:
> On Thu, Feb 26, 2026 at 04:28:53PM -0800, Sean Christopherson wrote:
> > > I'm confused though - I thought in-place conversion ment that

Intel secure IOMMU does reuse S-EPT, but that doesn't mean IOMMU mapping
stay still, at least IOTLB needs flush.

> > be updated.
> 

Will cause host machine check and host restart, same as host CPU
accessing encrypted memory. Intel TDX has no lower level privilege
protection table so the wrong accessing will actually impact the
memory encryption engine.

> 
> Or maybe we are lucky and it generates a nice contained fault like the

---

## [12] Xu Yilun — 2026-02-27
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Thu, Feb 26, 2026 at 03:27:00PM -0400, Jason Gunthorpe wrote:
> On Thu, Feb 26, 2026 at 05:47:50PM +1100, Alexey Kardashevskiy wrote:
> > 

Intel TDX will cause host machine check and restart, which are not
contained.

> 
> However, it is not like AMD in many important ways here. Critically ARM

This is same as Intel TDX, the GPA shared bit are used by IOMMU to
target shared/private. You can imagine for T=1, there are 2 IOPTs, or
1 IOPT with all private at lower address & all shared at higher address.

> 
> Thus on Linux the iommu should be programed with the shared pages

For Intel TDX, it is not just a waste, the redundant IOMMU mappings are
dangerous.

> 
> I think if you are fully doing in-place conversion then you could

Secure part of IOPT (lower address) reuses KVM MMU (S-EPT) so needs no
extra update but needs a global IOTLB flush. The Shared part of IOPT
for T=1 needs update based on GPA.

> 
> Jason

---

## [13] Jason Gunthorpe — 2026-02-27
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Fri, Feb 27, 2026 at 06:35:44PM +0800, Xu Yilun wrote:

> Will cause host machine check and host restart, same as host CPU
> accessing encrypted memory. Intel TDX has no lower level privilege

Blah, of course it does.

So Intel needs a two step synchronization to wipe the IOPTEs before
any shared private conversions and restore the right ones after.

AMD needs a nasty HW synchronization with RMP changes, but otherwise
wants to map the entire physical space.

ARM doesn't care much, I think it could safely do either approach?

These are very different behaviors so I would expect that userspace
needs to signal which of the two it wants.

It feels like we need a fairly complex dedicated synchronization logic
in iommufd coupled to the shared/private machinery in guestmemfd

Not really sure how to implement the Intel version right now, it is
sort of like a nasty version of SVA..

Jason

---

## [14] Xu Yilun — 2026-02-28
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Fri, Feb 27, 2026 at 09:18:15AM -0400, Jason Gunthorpe wrote:
> On Fri, Feb 27, 2026 at 06:35:44PM +0800, Xu Yilun wrote:
> 

Mainly about shared IOPTE (for both T=0 table & T=1 table): "unmap
before conversion to private" & "map after conversion to shared"

I see there are already some consideration in QEMU to support in-place
conversion + shared passthrough [*], using uptr, but seems that's
exactly what you are objecting to.

[*]: https://lore.kernel.org/all/18f64464-2ead-42d4-aeaa-f781020dca05@intel.com/

For Intel, T=1 private IOPTE reuses S-EPT, this is the real CC business
and the correctness is managed by KVM & firmware, no notification
needed.

Further more, I think "unmap shared IOPTE before conversion to private"
may be the only concern to ensure kernel safety, other steps could be
fully left to userspace. Hope the downgrading from "remap" to
"invalidate" simplifies the notification.

> 
> AMD needs a nasty HW synchronization with RMP changes, but otherwise

---

## [15] Jason Gunthorpe — 2026-02-28
*Subject: Re: [RFC PATCH kernel] iommufd: Allow mapping from KVM's guest_memfd*

On Sat, Feb 28, 2026 at 12:14:25PM +0800, Xu Yilun wrote:
> On Fri, Feb 27, 2026 at 09:18:15AM -0400, Jason Gunthorpe wrote:
> > On Fri, Feb 27, 2026 at 06:35:44PM +0800, Xu Yilun wrote:

There is some ugly stuff in qemu trying to make this work with VFIO..

> Further more, I think "unmap shared IOPTE before conversion to private"
> may be the only concern to ensure kernel safety, other steps could be

Maybe, but there is still the large issue of how to deal with
fragmenting the mapping and breaking/re-consolidating huge pages,
which is not trivial..

To really make this work well we may need iommufd to actively mirror
the guestmemfd into IOPTEs and dynamically track changes.

I will think about it..

Jason

---
