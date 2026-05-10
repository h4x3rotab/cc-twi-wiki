---
title: 'mm/page_alloc: Fix memory accept before watermarks gets initialized'
date: 2025-03-10
last_reply: 2025-03-12
message_count: 5
participants: ['Kirill A. Shutemov', 'Vlastimil Babka', 'Gupta, Pankaj']
---

## [1] Kirill A. Shutemov — 2025-03-10

Watermarks are initialized during the postcore initcall. Until then, all
watermarks are set to zero. This causes cond_accept_memory() to
incorrectly skip memory acceptance because a watermark of 0 is always
met.

To ensure progress, accept one MAX_ORDER page if the watermark is zero.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reported-and-tested-by: Farrah Chen <farrah.chen@intel.com>
---
 mm/page_alloc.c | 14 ++++++++++++--
 1 file changed, 12 insertions(+), 2 deletions(-)

diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index 579789600a3c..4fe93029bcb6 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -7004,7 +7004,7 @@ static inline bool has_unaccepted_memory(void)
 
 static bool cond_accept_memory(struct zone *zone, unsigned int order)
 {
-	long to_accept;
+	long to_accept, wmark;
 	bool ret = false;
 
 	if (!has_unaccepted_memory())
@@ -7013,8 +7013,18 @@ static bool cond_accept_memory(struct zone *zone, unsigned int order)
 	if (list_empty(&zone->unaccepted_pages))
 		return false;
 
+	wmark = promo_wmark_pages(zone);
+
+	/*
+	 * Watermarks have not been initialized yet.
+	 *
+	 * Accepting one MAX_ORDER page to ensure progress.
+	 */
+	if (!wmark)
+		return try_to_accept_memory_one(zone);
+
 	/* How much to accept to get to promo watermark? */
-	to_accept = promo_wmark_pages(zone) -
+	to_accept = wmark -
 		    (zone_page_state(zone, NR_FREE_PAGES) -
 		    __zone_watermark_unusable_free(zone, order, 0) -
 		    zone_page_state(zone, NR_UNACCEPTED));

---

## [2] Vlastimil Babka — 2025-03-10
*Subject: Re: [PATCH] mm/page_alloc: Fix memory accept before watermarks gets
 initialized*

On 3/10/25 09:28, Kirill A. Shutemov wrote:
> Watermarks are initialized during the postcore initcall. Until then, all
> watermarks are set to zero. This causes cond_accept_memory() to

What are the user-visible consequences of that?

> To ensure progress, accept one MAX_ORDER page if the watermark is zero.
> 

Fixes:, Cc: stable etc?

> ---
>  mm/page_alloc.c | 14 ++++++++++++--

---

## [3] Kirill A. Shutemov — 2025-03-10
*Subject: Re: [PATCH] mm/page_alloc: Fix memory accept before watermarks gets
 initialized*

On Mon, Mar 10, 2025 at 12:37:25PM +0100, Vlastimil Babka wrote:
> On 3/10/25 09:28, Kirill A. Shutemov wrote:
> > Watermarks are initialized during the postcore initcall. Until then, all

Premature OOM on boot.

It can be triggered with certain combinations of number of vCPUs and
memory size.

> > To ensure progress, accept one MAX_ORDER page if the watermark is zero.
> > 

Fixes: dcdfdd40fa82 ("mm: Add support for unaccepted memory")
Cc: stable@@vger.kernel.org # v6.5+

---

## [4] Vlastimil Babka — 2025-03-11
*Subject: Re: [PATCH] mm/page_alloc: Fix memory accept before watermarks gets
 initialized*

On 3/10/25 09:28, Kirill A. Shutemov wrote:
> Watermarks are initialized during the postcore initcall. Until then, all
> watermarks are set to zero. This causes cond_accept_memory() to

Acked-by: Vlastimil Babka <vbabka@suse.cz>

> ---
>  mm/page_alloc.c | 14 ++++++++++++--

---

## [5] Gupta, Pankaj — 2025-03-12
*Subject: Re: [PATCH] mm/page_alloc: Fix memory accept before watermarks gets
 initialized*

> Watermarks are initialized during the postcore initcall. Until then, all
> watermarks are set to zero. This causes cond_accept_memory() to

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

Also, did a basic boot test of SNP guest kernel 6.14-rc6 with the patch 
applied on top.

> ---
>   mm/page_alloc.c | 14 ++++++++++++--

---
