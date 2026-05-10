---
title: 'x86/sev: Fix making shared pages private during kdump'
date: 2025-05-04
last_reply: 2025-05-04
message_count: 1
participants: ['Ashish Kalra']
---

## [1] Ashish Kalra — 2025-05-04

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

Cc: stable@vger.kernel.org
Fixes: 3074152e56c9 ("x86/sev: Convert shared memory back to private on kexec")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c | 14 ++++++++------
 1 file changed, 8 insertions(+), 6 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index d35fec7b164a..e39db6714f09 100644
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
@@ -1131,9 +1132,8 @@ static void shutdown_all_aps(void)
 void snp_kexec_finish(void)
 {
 	struct sev_es_runtime_data *data;
+	unsigned long size, ghcb;
 	unsigned int level, cpu;
-	unsigned long size;
-	struct ghcb *ghcb;
 	pte_t *pte;
 
 	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
@@ -1157,11 +1157,13 @@ void snp_kexec_finish(void)
 
 	for_each_possible_cpu(cpu) {
 		data = per_cpu(runtime_data, cpu);
-		ghcb = &data->ghcb_page;
-		pte = lookup_address((unsigned long)ghcb, &level);
+		ghcb = (unsigned long)&data->ghcb_page;
+		pte = lookup_address(ghcb, &level);
 		size = page_level_size(level);
+		/* Handle the case of a huge page containing the GHCB page */
+		ghcb &= page_level_mask(level);
 		set_pte_enc(pte, level, (void *)ghcb);
-		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
+		snp_set_memory_private(ghcb, (size / PAGE_SIZE));
 	}
 }

---
