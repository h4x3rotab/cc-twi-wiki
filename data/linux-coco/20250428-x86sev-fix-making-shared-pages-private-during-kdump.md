---
title: 'x86/sev: Fix making shared pages private during kdump'
date: 2025-04-28
last_reply: 2025-04-30
message_count: 3
participants: ['Ashish Kalra', 'Tom Lendacky', 'Borislav Petkov']
---

## [1] Ashish Kalra — 2025-04-28

From: Ashish Kalra <ashish.kalra@amd.com>

When the shared pages are being made private during kdump preparation
there are additional checks to handle shared GHCB pages.

These additional checks include handling the case of GHCB page being
contained within a huge page.

There is a bug in this additional check for GHCB page contained
within a huge page which causes any shared page just below the
per-cpu GHCB getting skipped from being transitioned back to private
before kdump preparation which subsequently causes a 0x404 #VC
exception when this shared page is accessed later while dumping guest
memory during vmcore generation via kdump.

Correct the detection and handling of GHCB pages contained within
a huge page.

Cc: stable@vger.kernel.org
Fixes: 3074152e56c9 ("x86/sev: Convert shared memory back to private on kexec")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c | 14 ++++++++++++--
 1 file changed, 12 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 870f4994a13d..ba601ef5242d 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -961,7 +961,13 @@ static void unshare_all_memory(void)
 			data = per_cpu(runtime_data, cpu);
 			ghcb = (unsigned long)&data->ghcb_page;
 
-			if (addr <= ghcb && ghcb <= addr + size) {
+			/* Handle the case of a huge page containing the GHCB page */
+			if (level == PG_LEVEL_4K && addr == ghcb) {
+				skipped_addr = true;
+				break;
+			}
+			if (level > PG_LEVEL_4K && addr <= ghcb &&
+			    ghcb < addr + size) {
 				skipped_addr = true;
 				break;
 			}
@@ -1074,8 +1080,8 @@ static void snp_shutdown_all_aps(void)
 void snp_kexec_finish(void)
 {
 	struct sev_es_runtime_data *data;
+	unsigned long size, mask;
 	unsigned int level, cpu;
-	unsigned long size;
 	struct ghcb *ghcb;
 	pte_t *pte;
 
@@ -1103,6 +1109,10 @@ void snp_kexec_finish(void)
 		ghcb = &data->ghcb_page;
 		pte = lookup_address((unsigned long)ghcb, &level);
 		size = page_level_size(level);
+		mask = page_level_mask(level);
+		/* Handle the case of a huge page containing the GHCB page */
+		if (level > PG_LEVEL_4K)
+			ghcb = (struct ghcb *)((unsigned long)ghcb & mask);
 		set_pte_enc(pte, level, (void *)ghcb);
 		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
 	}

---

## [2] Tom Lendacky — 2025-04-29
*Subject: Re: [PATCH v2] x86/sev: Fix making shared pages private during kdump*

On 4/28/25 14:26, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/coco/sev/core.c | 14 ++++++++++++--

---

## [3] Borislav Petkov — 2025-04-30
*Subject: Re: [PATCH v2] x86/sev: Fix making shared pages private during kdump*

On Mon, Apr 28, 2025 at 07:26:57PM +0000, Ashish Kalra wrote:
> There is a bug in this additional check for GHCB page contained

You don't write in the commit message that there is a bug - you explain what
the bug is.

> within a huge page which causes any shared page just below the
> per-cpu GHCB getting skipped from being transitioned back to private

And you explain that *not* in a single, never-ending sentence but in simpler,
smaller, more palatable sentences. Imagine you're trying to explain this to
your colleagues who are not in your head.

I've been staring at the diff and trying to reverse-engineer what you're
trying to tell me in the commit message and I have an idea but I'm not sure.
And when I'm not sure, it often means the commit message needs more work.

So try again pls.

Thx.

---
