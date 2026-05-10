---
title: 'x86/sev: Fix making shared pages private during kdump'
date: 2025-05-06
last_reply: 2025-05-07
message_count: 3
participants: ['Ashish Kalra', 'Borislav Petkov', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-05-06

From: Ashish Kalra <ashish.kalra@amd.com>

When the shared pages are being made private during kdump preparation
there are additional checks to handle shared GHCB pages.

These additional checks include handling the case of GHCB page being
contained within a huge page.

The check for handling the case of GHCB contained within a huge
page incorrectly skips a page just below the GHCB page from being
transitioned back to private during kdump preparation.

This skipped page causes a 0x404 #VC exception when it is accessed
later while dumping guest memory during vmcore generation via kdump.

Correct the range to be checked for GHCB contained in a huge page.
Also ensure that the skipped huge page containing the GHCB page is
transitioned back to private by applying the correct address mask
later when changing GHCBs to private at end of kdump preparation.

Fixes: 3074152e56c9 ("x86/sev: Convert shared memory back to private on kexec")
Cc: stable@vger.kernel.org
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c | 11 +++++++----
 1 file changed, 7 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index d35fec7b164a..30b74e4e4e88 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1019,7 +1019,8 @@ static void unshare_all_memory(void)
 			data = per_cpu(runtime_data, cpu);
 			ghcb = (unsigned long)&data->ghcb_page;
 
-			if (addr <= ghcb && ghcb <= addr + size) {
+			/* Handle the case of a huge page containing the GHCB page */
+			if (addr <= ghcb && ghcb < addr + size) {
 				skipped_addr = true;
 				break;
 			}
@@ -1131,8 +1132,8 @@ static void shutdown_all_aps(void)
 void snp_kexec_finish(void)
 {
 	struct sev_es_runtime_data *data;
+	unsigned long size, addr;
 	unsigned int level, cpu;
-	unsigned long size;
 	struct ghcb *ghcb;
 	pte_t *pte;
 
@@ -1160,8 +1161,10 @@ void snp_kexec_finish(void)
 		ghcb = &data->ghcb_page;
 		pte = lookup_address((unsigned long)ghcb, &level);
 		size = page_level_size(level);
-		set_pte_enc(pte, level, (void *)ghcb);
-		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
+		/* Handle the case of a huge page containing the GHCB page */
+		addr = (unsigned long)ghcb & page_level_mask(level);
+		set_pte_enc(pte, level, (void *)addr);
+		snp_set_memory_private(addr, (size / PAGE_SIZE));
 	}
 }

---

## [2] Borislav Petkov — 2025-05-07
*Subject: Re: [PATCH v5] x86/sev: Fix making shared pages private during kdump*

On Tue, May 06, 2025 at 06:35:29PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Ok, I've pushed both patches here:

https://git.kernel.org/pub/scm/linux/kernel/git/bp/bp.git/log/?h=tip-x86-urgent-sev

Please have those who are affected by the issues test and report back.

Thx.

---

## [3] Tom Lendacky — 2025-05-07
*Subject: Re: [PATCH v5] x86/sev: Fix making shared pages private during kdump*

On 5/6/25 13:35, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/coco/sev/core.c | 11 +++++++----

---
