---
title: 'mm/page_alloc: Fix couple of unaccepted memory issues'
date: 2025-05-06
last_reply: 2025-05-07
message_count: 14
participants: ['Kirill A. Shutemov', 'Borislav Petkov', 'Brendan Jackman', 'Alexei Starovoitov', 'Andrew Morton']
---

## [1] Kirill A. Shutemov — 2025-05-06

Fix issues with unaccepted memory:

  - try_alloc_pages() gives up too early on machines with unaccepted
    memory;
  - race around zones_with_unaccepted_pages static branch;

Kirill A. Shutemov (2):
  mm/page_alloc: Ensure try_alloc_pages() plays well with unaccepted
    memory
  mm/page_alloc: Fix race condition in unaccepted memory handling

 mm/internal.h   |  1 -
 mm/mm_init.c    |  1 -
 mm/page_alloc.c | 73 ++++++++++---------------------------------------
 3 files changed, 14 insertions(+), 61 deletions(-)

---

## [2] Kirill A. Shutemov — 2025-05-06
*Subject: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well with unaccepted memory*

try_alloc_pages() will not attempt to allocate memory if the system has
*any* unaccepted memory. Memory is accepted as needed and can remain in
the system indefinitely, causing the interface to always fail.

Rather than immediately giving up, attempt to use already accepted
memory on free lists.

Pass 'alloc_flags' to cond_accept_memory() and do not accept new memory
for ALLOC_TRYLOCK requests.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Fixes: 97769a53f117 ("mm, bpf: Introduce try_alloc_pages() for opportunistic page allocation")
Cc: Alexei Starovoitov <ast@kernel.org>
Cc: Andrew Morton <akpm@linux-foundation.org>
Cc: Vlastimil Babka <vbabka@suse.cz>
Cc: Suren Baghdasaryan <surenb@google.com>
Cc: Michal Hocko <mhocko@suse.com>
Cc: Brendan Jackman <jackmanb@google.com>
Cc: Johannes Weiner <hannes@cmpxchg.org>
---
 mm/page_alloc.c | 28 +++++++++++++++-------------
 1 file changed, 15 insertions(+), 13 deletions(-)

diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index 5669baf2a6fe..5fccf5fce084 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -290,7 +290,8 @@ EXPORT_SYMBOL(nr_online_nodes);
 #endif
 
 static bool page_contains_unaccepted(struct page *page, unsigned int order);
-static bool cond_accept_memory(struct zone *zone, unsigned int order);
+static bool cond_accept_memory(struct zone *zone, unsigned int order,
+			       int alloc_flags);
 static bool __free_unaccepted(struct page *page);
 
 int page_group_by_mobility_disabled __read_mostly;
@@ -3616,7 +3617,7 @@ get_page_from_freelist(gfp_t gfp_mask, unsigned int order, int alloc_flags,
 			}
 		}
 
-		cond_accept_memory(zone, order);
+		cond_accept_memory(zone, order, alloc_flags);
 
 		/*
 		 * Detect whether the number of free pages is below high
@@ -3643,7 +3644,7 @@ get_page_from_freelist(gfp_t gfp_mask, unsigned int order, int alloc_flags,
 				       gfp_mask)) {
 			int ret;
 
-			if (cond_accept_memory(zone, order))
+			if (cond_accept_memory(zone, order, alloc_flags))
 				goto try_this_zone;
 
 			/*
@@ -3696,7 +3697,7 @@ get_page_from_freelist(gfp_t gfp_mask, unsigned int order, int alloc_flags,
 
 			return page;
 		} else {
-			if (cond_accept_memory(zone, order))
+			if (cond_accept_memory(zone, order, alloc_flags))
 				goto try_this_zone;
 
 			/* Try again if zone has deferred pages */
@@ -4849,7 +4850,7 @@ unsigned long alloc_pages_bulk_noprof(gfp_t gfp, int preferred_nid,
 			goto failed;
 		}
 
-		cond_accept_memory(zone, 0);
+		cond_accept_memory(zone, 0, alloc_flags);
 retry_this_zone:
 		mark = wmark_pages(zone, alloc_flags & ALLOC_WMARK_MASK) + nr_pages;
 		if (zone_watermark_fast(zone, 0,  mark,
@@ -4858,7 +4859,7 @@ unsigned long alloc_pages_bulk_noprof(gfp_t gfp, int preferred_nid,
 			break;
 		}
 
-		if (cond_accept_memory(zone, 0))
+		if (cond_accept_memory(zone, 0, alloc_flags))
 			goto retry_this_zone;
 
 		/* Try again if zone has deferred pages */
@@ -7284,7 +7285,8 @@ static inline bool has_unaccepted_memory(void)
 	return static_branch_unlikely(&zones_with_unaccepted_pages);
 }
 
-static bool cond_accept_memory(struct zone *zone, unsigned int order)
+static bool cond_accept_memory(struct zone *zone, unsigned int order,
+			       int alloc_flags)
 {
 	long to_accept, wmark;
 	bool ret = false;
@@ -7295,6 +7297,10 @@ static bool cond_accept_memory(struct zone *zone, unsigned int order)
 	if (list_empty(&zone->unaccepted_pages))
 		return false;
 
+	/* Bailout, since try_to_accept_memory_one() needs to take a lock */
+	if (alloc_flags & ALLOC_TRYLOCK)
+		return false;
+
 	wmark = promo_wmark_pages(zone);
 
 	/*
@@ -7351,7 +7357,8 @@ static bool page_contains_unaccepted(struct page *page, unsigned int order)
 	return false;
 }
 
-static bool cond_accept_memory(struct zone *zone, unsigned int order)
+static bool cond_accept_memory(struct zone *zone, unsigned int order,
+			       int alloc_flags)
 {
 	return false;
 }
@@ -7422,11 +7429,6 @@ struct page *try_alloc_pages_noprof(int nid, unsigned int order)
 	if (!pcp_allowed_order(order))
 		return NULL;
 
-#ifdef CONFIG_UNACCEPTED_MEMORY
-	/* Bailout, since try_to_accept_memory_one() needs to take a lock */
-	if (has_unaccepted_memory())
-		return NULL;
-#endif
 	/* Bailout, since _deferred_grow_zone() needs to take a lock */
 	if (deferred_pages_enabled())
 		return NULL;

---

## [3] Kirill A. Shutemov — 2025-05-06
*Subject: [PATCH 2/2] mm/page_alloc: Fix race condition in unaccepted memory handling*

The page allocator tracks the number of zones that have unaccepted
memory using static_branch_enc/dec() and uses that static branch in hot
paths to determine if it needs to deal with unaccepted memory.

Borisal and Thomas pointed out that the tracking is racy operations on
static_branch are not serialized against adding/removing unaccepted pages
to/from the zone.

The effect of this static_branch optimization is only visible on
microbenchmark.

Instead of adding more complexity around it, remove it altogether.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Fixes: dcdfdd40fa82 ("mm: Add support for unaccepted memory")
Link: https://lore.kernel.org/all/20250506092445.GBaBnVXXyvnazly6iF@fat_crate.local
Reported-by: Borislav Petkov <bp@alien8.de>
Reported-by: Thomas Gleixner <tglx@linutronix.de>
Cc: stable@vger.kernel.org # v6.5+
Cc: Andrew Morton <akpm@linux-foundation.org>
Cc: Vlastimil Babka <vbabka@suse.cz>
Cc: Suren Baghdasaryan <surenb@google.com>
Cc: Michal Hocko <mhocko@suse.com>
Cc: Brendan Jackman <jackmanb@google.com>
Cc: Johannes Weiner <hannes@cmpxchg.org>
---
 mm/internal.h   |  1 -
 mm/mm_init.c    |  1 -
 mm/page_alloc.c | 47 -----------------------------------------------
 3 files changed, 49 deletions(-)

diff --git a/mm/internal.h b/mm/internal.h
index e9695baa5922..50c2f590b2d0 100644
--- a/mm/internal.h
+++ b/mm/internal.h
@@ -1595,7 +1595,6 @@ unsigned long move_page_tables(struct pagetable_move_control *pmc);
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 void accept_page(struct page *page);
-void unaccepted_cleanup_work(struct work_struct *work);
 #else /* CONFIG_UNACCEPTED_MEMORY */
 static inline void accept_page(struct page *page)
 {
diff --git a/mm/mm_init.c b/mm/mm_init.c
index 9659689b8ace..84f14fa12d0d 100644
--- a/mm/mm_init.c
+++ b/mm/mm_init.c
@@ -1441,7 +1441,6 @@ static void __meminit zone_init_free_lists(struct zone *zone)
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 	INIT_LIST_HEAD(&zone->unaccepted_pages);
-	INIT_WORK(&zone->unaccepted_cleanup, unaccepted_cleanup_work);
 #endif
 }
 
diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index 5fccf5fce084..a4a4df2daedb 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -7175,16 +7175,8 @@ bool has_managed_dma(void)
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 
-/* Counts number of zones with unaccepted pages. */
-static DEFINE_STATIC_KEY_FALSE(zones_with_unaccepted_pages);
-
 static bool lazy_accept = true;
 
-void unaccepted_cleanup_work(struct work_struct *work)
-{
-	static_branch_dec(&zones_with_unaccepted_pages);
-}
-
 static int __init accept_memory_parse(char *p)
 {
 	if (!strcmp(p, "lazy")) {
@@ -7209,11 +7201,7 @@ static bool page_contains_unaccepted(struct page *page, unsigned int order)
 static void __accept_page(struct zone *zone, unsigned long *flags,
 			  struct page *page)
 {
-	bool last;
-
 	list_del(&page->lru);
-	last = list_empty(&zone->unaccepted_pages);
-
 	account_freepages(zone, -MAX_ORDER_NR_PAGES, MIGRATE_MOVABLE);
 	__mod_zone_page_state(zone, NR_UNACCEPTED, -MAX_ORDER_NR_PAGES);
 	__ClearPageUnaccepted(page);
@@ -7222,28 +7210,6 @@ static void __accept_page(struct zone *zone, unsigned long *flags,
 	accept_memory(page_to_phys(page), PAGE_SIZE << MAX_PAGE_ORDER);
 
 	__free_pages_ok(page, MAX_PAGE_ORDER, FPI_TO_TAIL);
-
-	if (last) {
-		/*
-		 * There are two corner cases:
-		 *
-		 * - If allocation occurs during the CPU bring up,
-		 *   static_branch_dec() cannot be used directly as
-		 *   it causes a deadlock on cpu_hotplug_lock.
-		 *
-		 *   Instead, use schedule_work() to prevent deadlock.
-		 *
-		 * - If allocation occurs before workqueues are initialized,
-		 *   static_branch_dec() should be called directly.
-		 *
-		 *   Workqueues are initialized before CPU bring up, so this
-		 *   will not conflict with the first scenario.
-		 */
-		if (system_wq)
-			schedule_work(&zone->unaccepted_cleanup);
-		else
-			unaccepted_cleanup_work(&zone->unaccepted_cleanup);
-	}
 }
 
 void accept_page(struct page *page)
@@ -7280,20 +7246,12 @@ static bool try_to_accept_memory_one(struct zone *zone)
 	return true;
 }
 
-static inline bool has_unaccepted_memory(void)
-{
-	return static_branch_unlikely(&zones_with_unaccepted_pages);
-}
-
 static bool cond_accept_memory(struct zone *zone, unsigned int order,
 			       int alloc_flags)
 {
 	long to_accept, wmark;
 	bool ret = false;
 
-	if (!has_unaccepted_memory())
-		return false;
-
 	if (list_empty(&zone->unaccepted_pages))
 		return false;
 
@@ -7331,22 +7289,17 @@ static bool __free_unaccepted(struct page *page)
 {
 	struct zone *zone = page_zone(page);
 	unsigned long flags;
-	bool first = false;
 
 	if (!lazy_accept)
 		return false;
 
 	spin_lock_irqsave(&zone->lock, flags);
-	first = list_empty(&zone->unaccepted_pages);
 	list_add_tail(&page->lru, &zone->unaccepted_pages);
 	account_freepages(zone, MAX_ORDER_NR_PAGES, MIGRATE_MOVABLE);
 	__mod_zone_page_state(zone, NR_UNACCEPTED, MAX_ORDER_NR_PAGES);
 	__SetPageUnaccepted(page);
 	spin_unlock_irqrestore(&zone->lock, flags);
 
-	if (first)
-		static_branch_inc(&zones_with_unaccepted_pages);
-
 	return true;
 }

---

## [4] Borislav Petkov — 2025-05-06
*Subject: Re: [PATCH 2/2] mm/page_alloc: Fix race condition in unaccepted
 memory handling*

On Tue, May 06, 2025 at 02:25:09PM +0300, Kirill A. Shutemov wrote:
> The page allocator tracks the number of zones that have unaccepted
> memory using static_branch_enc/dec() and uses that static branch in hot

Boris or Borislav would be nice.

> static_branch are not serialized against adding/removing unaccepted pages
> to/from the zone.

Also, that sentence needs massaging.

> The effect of this static_branch optimization is only visible on
> microbenchmark.

Yah, good idea.

> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> Fixes: dcdfdd40fa82 ("mm: Add support for unaccepted memory")

Tested-by: Borislav Petkov (AMD) <bp@alien8.de>

Thx for the quick fix.

---

## [5] Brendan Jackman — 2025-05-06
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue May 6, 2025 at 11:25 AM UTC, Kirill A. Shutemov wrote:
> +	/* Bailout, since try_to_accept_memory_one() needs to take a lock */
> +	if (alloc_flags & ALLOC_TRYLOCK)

Quick lazy question: why don't we just trylock it like we do for the zone
lock?

---

## [6] Kirill A. Shutemov — 2025-05-06
*Subject: [PATCHv2] mm/page_alloc: Fix race condition in unaccepted memory handling*

The page allocator tracks the number of zones that have unaccepted
memory using static_branch_enc/dec() and uses that static branch in hot
paths to determine if it needs to deal with unaccepted memory.

Borislav and Thomas pointed out that the tracking is racy: operations on
static_branch are not serialized against adding/removing unaccepted pages
to/from the zone.

Sanity checks inside static_branch machinery detects it:

WARNING: CPU: 0 PID: 10 at kernel/jump_label.c:276 __static_key_slow_dec_cpuslocked+0x8e/0xa0

The comment around the WARN() explains the problem:

	/*
	 * Warn about the '-1' case though; since that means a
	 * decrement is concurrent with a first (0->1) increment. IOW
	 * people are trying to disable something that wasn't yet fully
	 * enabled. This suggests an ordering problem on the user side.
	 */

The effect of this static_branch optimization is only visible on
microbenchmark.

Instead of adding more complexity around it, remove it altogether.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Fixes: dcdfdd40fa82 ("mm: Add support for unaccepted memory")
Link: https://lore.kernel.org/all/20250506092445.GBaBnVXXyvnazly6iF@fat_crate.local
Reported-by: Borislav Petkov <bp@alien8.de>
Tested-by: Borislav Petkov (AMD) <bp@alien8.de>
Reported-by: Thomas Gleixner <tglx@linutronix.de>
Cc: stable@vger.kernel.org # v6.5+
Cc: Andrew Morton <akpm@linux-foundation.org>
Cc: Vlastimil Babka <vbabka@suse.cz>
Cc: Suren Baghdasaryan <surenb@google.com>
Cc: Michal Hocko <mhocko@suse.com>
Cc: Brendan Jackman <jackmanb@google.com>
Cc: Johannes Weiner <hannes@cmpxchg.org>
---

 v2:
   - Update commit message;
   - Apply Borislav's Tested-by tag;

---
 mm/internal.h   |  1 -
 mm/mm_init.c    |  1 -
 mm/page_alloc.c | 47 -----------------------------------------------
 3 files changed, 49 deletions(-)

diff --git a/mm/internal.h b/mm/internal.h
index e9695baa5922..50c2f590b2d0 100644
--- a/mm/internal.h
+++ b/mm/internal.h
@@ -1595,7 +1595,6 @@ unsigned long move_page_tables(struct pagetable_move_control *pmc);
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 void accept_page(struct page *page);
-void unaccepted_cleanup_work(struct work_struct *work);
 #else /* CONFIG_UNACCEPTED_MEMORY */
 static inline void accept_page(struct page *page)
 {
diff --git a/mm/mm_init.c b/mm/mm_init.c
index 9659689b8ace..84f14fa12d0d 100644
--- a/mm/mm_init.c
+++ b/mm/mm_init.c
@@ -1441,7 +1441,6 @@ static void __meminit zone_init_free_lists(struct zone *zone)
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 	INIT_LIST_HEAD(&zone->unaccepted_pages);
-	INIT_WORK(&zone->unaccepted_cleanup, unaccepted_cleanup_work);
 #endif
 }
 
diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index 5fccf5fce084..a4a4df2daedb 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -7175,16 +7175,8 @@ bool has_managed_dma(void)
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 
-/* Counts number of zones with unaccepted pages. */
-static DEFINE_STATIC_KEY_FALSE(zones_with_unaccepted_pages);
-
 static bool lazy_accept = true;
 
-void unaccepted_cleanup_work(struct work_struct *work)
-{
-	static_branch_dec(&zones_with_unaccepted_pages);
-}
-
 static int __init accept_memory_parse(char *p)
 {
 	if (!strcmp(p, "lazy")) {
@@ -7209,11 +7201,7 @@ static bool page_contains_unaccepted(struct page *page, unsigned int order)
 static void __accept_page(struct zone *zone, unsigned long *flags,
 			  struct page *page)
 {
-	bool last;
-
 	list_del(&page->lru);
-	last = list_empty(&zone->unaccepted_pages);
-
 	account_freepages(zone, -MAX_ORDER_NR_PAGES, MIGRATE_MOVABLE);
 	__mod_zone_page_state(zone, NR_UNACCEPTED, -MAX_ORDER_NR_PAGES);
 	__ClearPageUnaccepted(page);
@@ -7222,28 +7210,6 @@ static void __accept_page(struct zone *zone, unsigned long *flags,
 	accept_memory(page_to_phys(page), PAGE_SIZE << MAX_PAGE_ORDER);
 
 	__free_pages_ok(page, MAX_PAGE_ORDER, FPI_TO_TAIL);
-
-	if (last) {
-		/*
-		 * There are two corner cases:
-		 *
-		 * - If allocation occurs during the CPU bring up,
-		 *   static_branch_dec() cannot be used directly as
-		 *   it causes a deadlock on cpu_hotplug_lock.
-		 *
-		 *   Instead, use schedule_work() to prevent deadlock.
-		 *
-		 * - If allocation occurs before workqueues are initialized,
-		 *   static_branch_dec() should be called directly.
-		 *
-		 *   Workqueues are initialized before CPU bring up, so this
-		 *   will not conflict with the first scenario.
-		 */
-		if (system_wq)
-			schedule_work(&zone->unaccepted_cleanup);
-		else
-			unaccepted_cleanup_work(&zone->unaccepted_cleanup);
-	}
 }
 
 void accept_page(struct page *page)
@@ -7280,20 +7246,12 @@ static bool try_to_accept_memory_one(struct zone *zone)
 	return true;
 }
 
-static inline bool has_unaccepted_memory(void)
-{
-	return static_branch_unlikely(&zones_with_unaccepted_pages);
-}
-
 static bool cond_accept_memory(struct zone *zone, unsigned int order,
 			       int alloc_flags)
 {
 	long to_accept, wmark;
 	bool ret = false;
 
-	if (!has_unaccepted_memory())
-		return false;
-
 	if (list_empty(&zone->unaccepted_pages))
 		return false;
 
@@ -7331,22 +7289,17 @@ static bool __free_unaccepted(struct page *page)
 {
 	struct zone *zone = page_zone(page);
 	unsigned long flags;
-	bool first = false;
 
 	if (!lazy_accept)
 		return false;
 
 	spin_lock_irqsave(&zone->lock, flags);
-	first = list_empty(&zone->unaccepted_pages);
 	list_add_tail(&page->lru, &zone->unaccepted_pages);
 	account_freepages(zone, MAX_ORDER_NR_PAGES, MIGRATE_MOVABLE);
 	__mod_zone_page_state(zone, NR_UNACCEPTED, MAX_ORDER_NR_PAGES);
 	__SetPageUnaccepted(page);
 	spin_unlock_irqrestore(&zone->lock, flags);
 
-	if (first)
-		static_branch_inc(&zones_with_unaccepted_pages);
-
 	return true;
 }

---

## [7] Kirill A. Shutemov — 2025-05-06
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue, May 06, 2025 at 01:20:25PM +0000, Brendan Jackman wrote:
> On Tue May 6, 2025 at 11:25 AM UTC, Kirill A. Shutemov wrote:
> > +	/* Bailout, since try_to_accept_memory_one() needs to take a lock */

It is not only zone lock. There's also unaccepted_memory_lock inside
accept_memory().

---

## [8] Alexei Starovoitov — 2025-05-06
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue, May 6, 2025 at 4:25 AM Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> try_alloc_pages() will not attempt to allocate memory if the system has

Thanks for working on this, but the fixes tag is overkill.
This limitation is not causing any issues in our setups.
Improving it is certainly better, of course.
Acked-by: Alexei Starovoitov <ast@kernel.org>

---

## [9] Kirill A. Shutemov — 2025-05-06
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue, May 06, 2025 at 10:18:21AM -0700, Alexei Starovoitov wrote:
> On Tue, May 6, 2025 at 4:25 AM Kirill A. Shutemov
> <kirill.shutemov@linux.intel.com> wrote:

Have you had chance to test it on any platform with unaccepted memory?
So far it is only Intel TDX and AMD SEV guests.

> Improving it is certainly better, of course.
> Acked-by: Alexei Starovoitov <ast@kernel.org>

Thanks!

---

## [10] Alexei Starovoitov — 2025-05-06
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue, May 6, 2025 at 12:00 PM Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> On Tue, May 06, 2025 at 10:18:21AM -0700, Alexei Starovoitov wrote:

We don't use them, and my understanding is that such
unaccepted memory will be there only during boot time.

---

## [11] Andrew Morton — 2025-05-06
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue,  6 May 2025 14:25:08 +0300 "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com> wrote:

> try_alloc_pages() will not attempt to allocate memory if the system has
> *any* unaccepted memory. Memory is accepted as needed and can remain in

What are the userspace-visible effects, please?

Was the omission of cc:stable intentional?  I cannot locally determine
this without the above info.

If the cc:stable omission was indeed intentional then it would be better
if this series was presented as two standalone patches.

---

## [12] Kirill A. Shutemov — 2025-05-07
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue, May 06, 2025 at 03:05:31PM -0700, Alexei Starovoitov wrote:
> On Tue, May 6, 2025 at 12:00 PM Kirill A. Shutemov
> <kirill.shutemov@linux.intel.com> wrote:

That's false. Unaccepted memory can be there indefinitely after boot. It
only gets accepted on demand.

---

## [13] Kirill A. Shutemov — 2025-05-07
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue, May 06, 2025 at 05:00:34PM -0700, Andrew Morton wrote:
> On Tue,  6 May 2025 14:25:08 +0300 "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com> wrote:
> 

I cannot say I fully understand the implications.

The interface obviously allows failure, but the caller might expect
eventual success on retry.

So far, only BPF uses the interface. Maybe Alexei can comment on what will
happen if the function always fails.

I noticed the issue by code analysis because the second patch removes
has_unaccepted_memory().

> Was the omission of cc:stable intentional?  I cannot locally determine
> this without the above info.

Given that the second patch cannot be applied to current Linus' tree
without this one, it is better to add stable@.

---

## [14] Brendan Jackman — 2025-05-07
*Subject: Re: [PATCH 1/2] mm/page_alloc: Ensure try_alloc_pages() plays well
 with unaccepted memory*

On Tue May 6, 2025 at 1:34 PM UTC, Kirill A. Shutemov wrote:
> On Tue, May 06, 2025 at 01:20:25PM +0000, Brendan Jackman wrote:
>> On Tue May 6, 2025 at 11:25 AM UTC, Kirill A. Shutemov wrote:

Right, but my lazy question was why can't we "just" trylock that too?

But anyway, that's no use because if we win the trylock we'd still have
to do __free_pages_ok().

---
