---
title: 'page_alloc: allow migration of smaller hugepages during contig_alloc'
date: 2025-12-03
last_reply: 2025-12-18
message_count: 10
participants: ['Gregory Price', 'Johannes Weiner', 'Frank van der Linden', 'David Hildenbrand (Red Hat)']
---

## [1] Gregory Price — 2025-12-03

We presently skip regions with hugepages entirely when trying to do
contiguous page allocation.  This will cause otherwise-movable
2MB HugeTLB pages to be considered unmovable, and will make 1GB
hugepages more difficult to allocate on systems utilizing both.

Instead, if hugepage migration is enabled, consider regions with
hugepages smaller than the target contiguous allocation request
as valid targets for allocation.

isolate_migrate_pages_block() has similar logic, and the hugetlb code
does a migratable check in folio_isolate_hugetlb() during isolation.
So the code servicing the subsequent allocaiton and migration already
supports this exact use case (it's just unreachable).

To test, allocate a bunch of 2MB HugeTLB pages (in this case 48GB)
and then attempt to allocate some 1G HugeTLB pages (in this case 4GB)
(Scale to your machine's memory capacity).

echo 24576 > .../hugepages-2048kB/nr_hugepages
echo 4 > .../hugepages-1048576kB/nr_hugepages

Prior to this patch, the 1GB page allocation can fail if no contiguous
1GB pages remain.  After this patch, the kernel will try to move 2MB
pages and successfully allocate the 1GB pages (assuming overall
sufficient memory is available).

folio_alloc_gigantic() is the primary user of alloc_contig_pages(),
other users are debug or init-time allocations and largely unaffected.
- ppc/memtrace is a debugfs interface
- x86/tdx memory allocation occurs once on module-init
- kfence/core happens once on module (late) init
- THP uses it in debug_vm_pgtable_alloc_huge_page at __init time

Suggested-by: David Hildenbrand <david@redhat.com>
Link: https://lore.kernel.org/linux-mm/6fe3562d-49b2-4975-aa86-e139c535ad00@redhat.com/
Signed-off-by: Gregory Price <gourry@gourry.net>
Reviewed-by: Zi Yan <ziy@nvidia.com>
Reviewed-by: Wei Yang <richard.weiyang@gmail.com>
Reviewed-by: Oscar Salvador <osalvador@suse.de>
Acked-by: David Rientjes <rientjes@google.com>
Acked-by: David Hildenbrand <david@redhat.com>
Tested-by: Joshua Hahn <joshua.hahnjy@gmail.com>
---
 mm/page_alloc.c | 23 +++++++++++++++++++++--
 1 file changed, 21 insertions(+), 2 deletions(-)

diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index 95d8b812efd0..8ca3273f734a 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -7069,8 +7069,27 @@ static bool pfn_range_valid_contig(struct zone *z, unsigned long start_pfn,
 		if (PageReserved(page))
 			return false;
 
-		if (PageHuge(page))
-			return false;
+		/*
+		 * Only consider ranges containing hugepages if those pages are
+		 * smaller than the requested contiguous region.  e.g.:
+		 *     Move 2MB pages to free up a 1GB range.
+		 *     Don't move 1GB pages to free up a 2MB range.
+		 *
+		 * This makes contiguous allocation more reliable if multiple
+		 * hugepage sizes are used without causing needless movement.
+		 */
+		if (PageHuge(page)) {
+			unsigned int order;
+
+			if (!IS_ENABLED(CONFIG_ARCH_ENABLE_HUGEPAGE_MIGRATION))
+				return false;
+
+			page = compound_head(page);
+			order = compound_order(page);
+			if ((order >= MAX_FOLIO_ORDER) ||
+			    (nr_pages <= (1 << order)))
+				return false;
+		}
 	}
 	return true;
 }

---

## [2] Johannes Weiner — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On Wed, Dec 03, 2025 at 01:30:04AM -0500, Gregory Price wrote:
> We presently skip regions with hugepages entirely when trying to do
> contiguous page allocation.  This will cause otherwise-movable

This one makes sense to me.

> +		 *     Don't move 1GB pages to free up a 2MB range.

This one I might be missing something. We don't use cma for 2M pages,
so I don't see how we can end up in this path for 2M allocations.

The reason I'm bringing this up is because this function overall looks
kind of unnecessary. Page isolation checks all of these conditions
already, and arbitrates huge pages on hugepage_migration_supported() -
which seems to be the semantics you also desire here.

Would it make sense to just remove pfn_range_valid_contig()?

---

## [3] Gregory Price — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On Wed, Dec 03, 2025 at 12:32:09PM -0500, Johannes Weiner wrote:
> On Wed, Dec 03, 2025 at 01:30:04AM -0500, Gregory Price wrote:
> > -		if (PageHuge(page))

I used 2MB as an example, but the other users (listed in the changelog)
would run into these as well.  The contiguous order size seemed
different between each of the 4 users (memtrace, tx, kfence, thp debug).

> The reason I'm bringing this up is because this function overall looks
> kind of unnecessary. Page isolation checks all of these conditions

This seems like a pretty clear optimization that was added at some point
to prevent incurring the cost of starting to isolate 512MB of pages and
then having to go undo it because it ran into a single huge page.

        for_each_zone_zonelist_nodemask(zone, z, zonelist,
                                        gfp_zone(gfp_mask), nodemask) {

                spin_lock_irqsave(&zone->lock, flags);
                pfn = ALIGN(zone->zone_start_pfn, nr_pages);
                while (zone_spans_last_pfn(zone, pfn, nr_pages)) {
                        if (pfn_range_valid_contig(zone, pfn, nr_pages)) {

                                spin_unlock_irqrestore(&zone->lock, flags);
                                ret = __alloc_contig_pages(pfn, nr_pages,
                                                        gfp_mask);
                                spin_lock_irqsave(&zone->lock, flags);

                        }
                        pfn += nr_pages;
                }
                spin_unlock_irqrestore(&zone->lock, flags);
        }

and then

__alloc_contig_pages
	ret = start_isolate_page_range(start, end, mode);

This is called without pre-checking the range for unmovable pages.

Seems dangerous to remove without significant data.

~Gregory

---

## [4] Frank van der Linden — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On Wed, Dec 3, 2025 at 9:53 AM Gregory Price <gourry@gourry.net> wrote:
>
> On Wed, Dec 03, 2025 at 12:32:09PM -0500, Johannes Weiner wrote:

Yeah, the function itself makes sense: "check if this is actually a
contiguous range available within this zone, so no holes and/or
reserved pages".

The PageHuge() check seems a bit out of place there, if you just
removed it altogether you'd get the same results, right? The isolation
code will deal with it. But sure, it does potentially avoid doing some
unnecessary work.

- Frank

---

## [5] Johannes Weiner — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On Wed, Dec 03, 2025 at 12:53:12PM -0500, Gregory Price wrote:
> On Wed, Dec 03, 2025 at 12:32:09PM -0500, Johannes Weiner wrote:
> > The reason I'm bringing this up is because this function overall looks

Fair enough. It just caught my eye that the page allocator is running
all the same checks as page isolation itself.

I agree that a quick up front check is useful before updating hundreds
of page blocks, then failing and unrolling on the last one. Arguably
that should just be part of the isolation code, though, not a random
callsite. But that move is better done in a separate patch.

---

## [6] David Hildenbrand (Red Hat) — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On 12/3/25 19:01, Frank van der Linden wrote:
> On Wed, Dec 3, 2025 at 9:53 AM Gregory Price <gourry@gourry.net> wrote:
>>

commit 4d73ba5fa710fe7d432e0b271e6fecd252aef66e
Author: Mel Gorman <mgorman@techsingularity.net>
Date:   Fri Apr 14 15:14:29 2023 +0100

     mm: page_alloc: skip regions with hugetlbfs pages when allocating 1G pages
     
     A bug was reported by Yuanxi Liu where allocating 1G pages at runtime is
     taking an excessive amount of time for large amounts of memory.  Further
     testing allocating huge pages that the cost is linear i.e.  if allocating
     1G pages in batches of 10 then the time to allocate nr_hugepages from
     10->20->30->etc increases linearly even though 10 pages are allocated at
     each step.  Profiles indicated that much of the time is spent checking the
     validity within already existing huge pages and then attempting a
     migration that fails after isolating the range, draining pages and a whole
     lot of other useless work.
     
     Commit eb14d4eefdc4 ("mm,page_alloc: drop unnecessary checks from
     pfn_range_valid_contig") removed two checks, one which ignored huge pages
     for contiguous allocations as huge pages can sometimes migrate.  While
     there may be value on migrating a 2M page to satisfy a 1G allocation, it's
     potentially expensive if the 1G allocation fails and it's pointless to try
     moving a 1G page for a new 1G allocation or scan the tail pages for valid
     PFNs.
     
     Reintroduce the PageHuge check and assume any contiguous region with
     hugetlbfs pages is unsuitable for a new 1G allocation.

...

---

## [7] Gregory Price — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On Wed, Dec 03, 2025 at 08:43:29PM +0100, David Hildenbrand (Red Hat) wrote:
> On 12/3/25 19:01, Frank van der Linden wrote:
> > 

Worth noting that because this check really only applies to gigantic
page *reservation* (not faulting), this isn't necessarily incurred in a
time critical path.  So, maybe i'm biased here, the reliability increase
feels like a win even if the operation can take a very long time under
memory pressure scenarios (which seems like an outliar anyway).

~Gregory

---

## [8] David Hildenbrand (Red Hat) — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On 12/3/25 21:09, Gregory Price wrote:
> On Wed, Dec 03, 2025 at 08:43:29PM +0100, David Hildenbrand (Red Hat) wrote:
>> On 12/3/25 19:01, Frank van der Linden wrote:

Not sure I understand correctly. I think the fix from Mel was the right 
thing to do.

It does not make sense to try migrating a 1GB page when allocating a 1GB 
page. Ever.

---

## [9] Gregory Price — 2025-12-03
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On Wed, Dec 03, 2025 at 09:14:44PM +0100, David Hildenbrand (Red Hat) wrote:
> On 12/3/25 21:09, Gregory Price wrote:
> > On Wed, Dec 03, 2025 at 08:43:29PM +0100, David Hildenbrand (Red Hat) wrote:

Oh yeah I agree, this patch doesn't allow that either.

I was just saying his patch's restriction of omitting all HugeTLB
(including 2MB) was more aggressive than needed.

I.e. allowing movement of 2MB pages to increase reliability is (arguably)
worth the potential long-runtime that doing so may produce (because we no
longer filter out regions with 2MB pages).

tl;dr: just re-iterating the theory of this patch.

~Gregory

---

## [10] Gregory Price — 2025-12-18
*Subject: Re: [PATCH v4] page_alloc: allow migration of smaller hugepages
 during contig_alloc*

On Wed, Dec 03, 2025 at 08:43:29PM +0100, David Hildenbrand (Red Hat) wrote:
> > Yeah, the function itself makes sense: "check if this is actually a
> > contiguous range available within this zone, so no holes and/or

In separate discussion with Johannes, he also noted that this allocation
code is the right place to do this check - as you might want to move a
1GB page if you're trying to reserve a specific region of memory.

So this much I'm confident in now.  But going back to Mel's comment:

> 
> commit 4d73ba5fa710fe7d432e0b271e6fecd252aef66e

Mel is pointing out that allowing 2MB region scans can cause 1GB page
allocation to take a very long time - specifically if no 2MB pages are
available as migration targets.

Joshua's test demonstrates at least that if the pages are reserved, the
migration code will move those reservations around accordingly. Now that
I look at it, it's unclear whether he tested if this still works when
those pages are actually reserved AND allocated.

I would presume we would end up in the position Mel describes (where
migrations fail and allocation takes a long time).  That does seem
problematic unless we can reserve a new 2MB page outside the current
region and destroy the old one.

This at least would not cause a recursive call into this code as only
the gigantic page reservation interface hits this code.


So I'm at a bit of an impasse. I understand the performance issue here,
but being able to reliably allocate gigantic pages when a ton of 2MB
pages are already being used is also really nice.

Maybe we could do a first-pass / second-pass attempt where we filter on
PageHuge() on the first go, and then filter on (PageHuge() < alloc_size)
on the second go?

~Gregory

---
