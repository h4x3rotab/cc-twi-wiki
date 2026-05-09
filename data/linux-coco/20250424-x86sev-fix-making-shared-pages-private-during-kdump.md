---
title: 'x86/sev: Fix making shared pages private during kdump'
date: 2025-04-24
last_reply: 2025-04-24
message_count: 3
participants: ['Ashish Kalra', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-04-24

From: Ashish Kalra <ashish.kalra@amd.com>

When the shared pages are being made private during kdump preparation
there are additional checks to handle shared GHCB pages.

These additional checks include handling the case of GHCB page being
contained within a 2MB page.

There is a bug in this additional check for GHCB page contained
within a 2MB page which causes any shared page just below the
per-cpu GHCB getting skipped from being transitioned back to private
before kdump preparation which subsequently causes a 0x404 #VC
exception when this shared page is accessed later while dumping guest
memory during vmcore generation via kdump. 

Correct the detection and handling of GHCB pages contained within
a 2MB page.

Cc: stable@vger.kernel.org
Fixes: 3074152e56c9 ("x86/sev: Convert shared memory back to private on kexec")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c | 11 ++++++++++-
 1 file changed, 10 insertions(+), 1 deletion(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 2c27d4b3985c..16d874f4dcd3 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -926,7 +926,13 @@ static void unshare_all_memory(void)
 			data = per_cpu(runtime_data, cpu);
 			ghcb = (unsigned long)&data->ghcb_page;
 
-			if (addr <= ghcb && ghcb <= addr + size) {
+			/* Handle the case of 2MB page containing the GHCB page */
+			if (level == PG_LEVEL_4K && addr == ghcb) {
+				skipped_addr = true;
+				break;
+			}
+			if (level > PG_LEVEL_4K && addr <= ghcb &&
+			    ghcb < addr + size) {
 				skipped_addr = true;
 				break;
 			}
@@ -1106,6 +1112,9 @@ void snp_kexec_finish(void)
 		ghcb = &data->ghcb_page;
 		pte = lookup_address((unsigned long)ghcb, &level);
 		size = page_level_size(level);
+		/* Handle the case of 2MB page containing the GHCB page */
+		if (level > PG_LEVEL_4K)
+			ghcb = (struct ghcb *)((unsigned long)ghcb & PMD_MASK);
 		set_pte_enc(pte, level, (void *)ghcb);
 		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
 	}

---

## [2] Tom Lendacky — 2025-04-24
*Subject: Re: [PATCH] x86/sev: Fix making shared pages private during kdump*

On 4/24/25 09:27, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

s/2MB page/a huge page/

> +			if (level == PG_LEVEL_4K && addr == ghcb) {
> +				skipped_addr = true;

For safety, shouldn't the mask be based on the level/size that is returned?

Thanks,
Tom

>  		set_pte_enc(pte, level, (void *)ghcb);
>  		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));

---

## [3] Kalra, Ashish — 2025-04-24
*Subject: Re: [PATCH] x86/sev: Fix making shared pages private during kdump*

Hello Tom,

On 4/24/2025 10:29 AM, Tom Lendacky wrote:
> On 4/24/25 09:27, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

Yes that makes sense and i will fix it accordingly.

Thanks,
Ashish
 
> Thanks,
> Tom

---
