---
title: 'x86/sev: Fix making shared pages private during kdump'
date: 2025-05-02
last_reply: 2025-05-05
message_count: 3
participants: ['Ashish Kalra', 'Ingo Molnar']
---

## [1] Ashish Kalra — 2025-05-02

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
 arch/x86/coco/sev/core.c | 15 +++++++++------
 1 file changed, 9 insertions(+), 6 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index d35fec7b164a..97e5d475b9f5 100644
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
+	unsigned long size, mask, ghcb;
 	unsigned int level, cpu;
-	unsigned long size;
-	struct ghcb *ghcb;
 	pte_t *pte;
 
 	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
@@ -1157,11 +1157,14 @@ void snp_kexec_finish(void)
 
 	for_each_possible_cpu(cpu) {
 		data = per_cpu(runtime_data, cpu);
-		ghcb = &data->ghcb_page;
-		pte = lookup_address((unsigned long)ghcb, &level);
+		ghcb = (unsigned long)&data->ghcb_page;
+		pte = lookup_address(ghcb, &level);
 		size = page_level_size(level);
+		mask = page_level_mask(level);
+		/* Handle the case of a huge page containing the GHCB page */
+		ghcb &= mask;
 		set_pte_enc(pte, level, (void *)ghcb);
-		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
+		snp_set_memory_private(ghcb, (size / PAGE_SIZE));
 	}
 }

---

## [2] Ingo Molnar — 2025-05-04
*Subject: Re: [PATCH v4] x86/sev: Fix making shared pages private during kdump*

* Ashish Kalra <Ashish.Kalra@amd.com> wrote:

>  
> -			if (addr <= ghcb && ghcb <= addr + size) {

So this patch just morphs the type of 'ghcb' from a typed pointer to 
unsigned long, while most 'ghcb' uses in coco/ are typed pointers?

That's just sloppy and fragile. Please just keep 'ghcb' a typed 
pointer, and introduce *another* variable for the virtual address to 
the hugepage.

>  	pte_t *pte;
>  

If 'ghcb' has the proper type then this ugly forced type-cast goes 
away.

> +		pte = lookup_address(ghcb, &level);
>  		size = page_level_size(level);

This too calls for using a separate variable for this, because after 
this masking 'ghcb' is very much *not* the location of a GHCB page 
anymore...

>  		set_pte_enc(pte, level, (void *)ghcb);
> -		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));

Do we know whether this is safe? Could the huge page around the GHCB 
page contain anything else? What is the structure of this memory area, 
is it all dedicated to the GHCB, or could it contain random other data?

Thanks,

	Ingo

---

## [3] Kalra, Ashish — 2025-05-05
*Subject: Re: [PATCH v4] x86/sev: Fix making shared pages private during kdump*

On 5/4/2025 4:21 AM, Ingo Molnar wrote:
> 
> * Ashish Kalra <Ashish.Kalra@amd.com> wrote:

Sure, i will use a separate variable for this and keep ghcb as a typed pointer.
 
>>  		set_pte_enc(pte, level, (void *)ghcb);
>> -		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));

There will be an issue if the huge page containing the GHCB 
has both private and shared memory contents in it.

When we skip a huge page containing the ghcb in unshare_all_memory()
then that huge page should have been containing all shared memory,
because if it had other private memory contents then there would be a
mismatch between NPT entry and RMP entry (as RMP would have 4K sub-entries
for private and shared mappings and then there would have been size type
mismatch between NPT and RMP tables) causing an RMP fault and then correspondingly
NPT would have been smashed/split into 4K private and shared mappings.

So at end of snp_kexec_finish(), when will be revisiting this huge page
again which contains the ghcb, it should be containing other shared memory
along with the ghcb as this whole range was skipped earlier and now
we should be able to convert this huge page back to private.

Thanks,
Ashish

> Thanks,
>

---
