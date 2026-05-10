---
title: 'mm/page_alloc: fix deadlock on cpu_hotplug_lock in __accept_page()'
date: 2025-03-29
last_reply: 2025-04-01
message_count: 3
participants: ['Kirill A. Shutemov', 'Dave Hansen']
---

## [1] Kirill A. Shutemov — 2025-03-29

When the last page in the zone is accepted, __accept_page() calls
static_branch_dec(). This function takes cpu_hotplug_lock, which can
lead to a deadlock if the allocation occurs during CPU bringup path as
_cpu_up() also takes the lock.

To prevent this deadlock, defer static_branch_dec() to a workqueue.

Call static_branch_dec() only when the workqueue is not yet initialized.
Workqueues are initialized before CPU bring up, so this will not
conflict with the first scenario.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Fixes: 55ad43e8ba0f ("mm: add a helper to accept page")
Reported-by: Srikanth Aithal <sraithal@amd.com>
Tested-by: Srikanth Aithal <sraithal@amd.com>
---
 include/linux/mmzone.h |  3 +++
 mm/internal.h          |  1 +
 mm/mm_init.c           |  1 +
 mm/page_alloc.c        | 28 ++++++++++++++++++++++++++--
 4 files changed, 31 insertions(+), 2 deletions(-)

diff --git a/include/linux/mmzone.h b/include/linux/mmzone.h
index 9540b41894da..9027f751b619 100644
--- a/include/linux/mmzone.h
+++ b/include/linux/mmzone.h
@@ -964,6 +964,9 @@ struct zone {
 #ifdef CONFIG_UNACCEPTED_MEMORY
 	/* Pages to be accepted. All pages on the list are MAX_PAGE_ORDER */
 	struct list_head	unaccepted_pages;
+
+	/* To be called once the last page in the zone is accepted */
+	struct work_struct	unaccepted_cleanup;
 #endif
 
 	/* zone flags, see below */
diff --git a/mm/internal.h b/mm/internal.h
index 109ef30fee11..f2e6d42af6eb 100644
--- a/mm/internal.h
+++ b/mm/internal.h
@@ -1516,6 +1516,7 @@ unsigned long move_page_tables(struct vm_area_struct *vma,
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 void accept_page(struct page *page);
+void unaccepted_cleanup_work(struct work_struct *work);
 #else /* CONFIG_UNACCEPTED_MEMORY */
 static inline void accept_page(struct page *page)
 {
diff --git a/mm/mm_init.c b/mm/mm_init.c
index 2630cc30147e..d5a51f65dc4d 100644
--- a/mm/mm_init.c
+++ b/mm/mm_init.c
@@ -1404,6 +1404,7 @@ static void __meminit zone_init_free_lists(struct zone *zone)
 
 #ifdef CONFIG_UNACCEPTED_MEMORY
 	INIT_LIST_HEAD(&zone->unaccepted_pages);
+	INIT_WORK(&zone->unaccepted_cleanup, unaccepted_cleanup_work);
 #endif
 }
 
diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index 4fe93029bcb6..e51304d3f126 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -6921,6 +6921,11 @@ static DEFINE_STATIC_KEY_FALSE(zones_with_unaccepted_pages);
 
 static bool lazy_accept = true;
 
+void unaccepted_cleanup_work(struct work_struct *work)
+{
+	static_branch_dec(&zones_with_unaccepted_pages);
+}
+
 static int __init accept_memory_parse(char *p)
 {
 	if (!strcmp(p, "lazy")) {
@@ -6959,8 +6964,27 @@ static void __accept_page(struct zone *zone, unsigned long *flags,
 
 	__free_pages_ok(page, MAX_PAGE_ORDER, FPI_TO_TAIL);
 
-	if (last)
-		static_branch_dec(&zones_with_unaccepted_pages);
+	if (last) {
+		/*
+		 * There are two corner cases:
+		 *
+		 * - If allocation occurs during the CPU bring up,
+		 *   static_branch_dec() cannot be used directly as
+		 *   it causes a deadlock on cpu_hotplug_lock.
+		 *
+		 *   Instead, use schedule_work() to prevent deadlock.
+		 *
+		 * - If allocation occurs before workqueues are initialized,
+		 *   static_branch_dec() should be called directly.
+		 *
+		 *   Workqueues are initialized before CPU bring up, so this
+		 *   will not conflict with the first scenario.
+		 */
+		if (system_wq)
+			schedule_work(&zone->unaccepted_cleanup);
+		else
+			unaccepted_cleanup_work(&zone->unaccepted_cleanup);
+	}
 }
 
 void accept_page(struct page *page)

---

## [2] Dave Hansen — 2025-03-31
*Subject: Re: [PATCH] mm/page_alloc: fix deadlock on cpu_hotplug_lock in
 __accept_page()*

On 3/29/25 10:10, Kirill A. Shutemov wrote:
> +		if (system_wq)
> +			schedule_work(&zone->unaccepted_cleanup);

The 'system_wq' check seems like an awfully big hack. No other
schedule_work() user does anything similar that I can find across the tree.

Instead of hacking in some internal state, could you use 'system_state',
like:

	if (system_state == SYSTEM_BOOTING)
		unaccepted_cleanup_work(&zone->unaccepted_cleanup);
	else
		schedule_work(&zone->unaccepted_cleanup);

The other method would be to make it more opportunistic? Basically,
detect when it might deadlock:

bool try_to_dec()
{
	if (!cpus_read_trylock())
		return false;

	static_branch_dec_cpuslocked(&zones_with_unaccepted_pages);
	cpus_read_unlock();

	return true;
}

That still requires a bit in the zone to say whether the
static_branch_dec() was deferred or not, though. It's kinda open-coding
schedule_work().

---

## [3] Kirill A. Shutemov — 2025-04-01
*Subject: Re: [PATCH] mm/page_alloc: fix deadlock on cpu_hotplug_lock in
 __accept_page()*

On Mon, Mar 31, 2025 at 12:07:07PM -0700, Dave Hansen wrote:
> On 3/29/25 10:10, Kirill A. Shutemov wrote:
> > +		if (system_wq)

I don't see how it is "an awfully big hack". It is "use system_wq if it is
ready".

Maybe it is going to be marginally cleaner if schedule_work() would be
open-coded:

		if (system_wq)
		        queue_work(system_wq, &zone->unaccepted_cleanup);
		else
			unaccepted_cleanup_work(&zone->unaccepted_cleanup);

?

> 
> Instead of hacking in some internal state, could you use 'system_state',

Really? The transition points between these states are arbitrary defined.
Who said that if we are out of SYSTEM_BOOTING we can use system_wq?
Tomorrow we can introduce additional state between BOOTING and SCHEDULING
and this code will be silently broken. The same for any new state before
BOOTING.

> The other method would be to make it more opportunistic? Basically,
> detect when it might deadlock:

It will also require special handling for soft CPU online/offline.

---
