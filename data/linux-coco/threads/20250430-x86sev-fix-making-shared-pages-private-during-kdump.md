---
title: 'x86/sev: Fix making shared pages private during kdump'
date: 2025-04-30
last_reply: 2025-05-02
message_count: 5
participants: ['Ashish Kalra', 'Tom Lendacky', 'Borislav Petkov']
---

## [1] Ashish Kalra — 2025-04-30

From: Ashish Kalra <ashish.kalra@amd.com>

When the shared pages are being made private during kdump preparation
there are additional checks to handle shared GHCB pages.

These additional checks include handling the case of GHCB page being
contained within a huge page.

While handling the case of GHCB page contained within a huge page
any shared page just below the GHCB page gets skipped from being
transitioned back to private during kdump preparation.

This subsequently causes a 0x404 #VC exception when this skipped
shared page is accessed later while dumping guest memory during
vmcore generation via kdump.

Split the initial check for skipping the GHCB page into the page
being skipped fully containing the GHCB and GHCB being contained 
within a huge page. Also ensure that the skipped huge page
containing the GHCB page is transitioned back to private later
when changing GHCBs to private at end of kdump preparation.

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: stable@vger.kernel.org
Fixes: 3074152e56c9 ("x86/sev: Convert shared memory back to private on kexec")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c | 14 ++++++++++++--
 1 file changed, 12 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index d35fec7b164a..1f53383bd1fa 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1019,7 +1019,13 @@ static void unshare_all_memory(void)
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
@@ -1131,8 +1137,8 @@ static void shutdown_all_aps(void)
 void snp_kexec_finish(void)
 {
 	struct sev_es_runtime_data *data;
+	unsigned long size, mask;
 	unsigned int level, cpu;
-	unsigned long size;
 	struct ghcb *ghcb;
 	pte_t *pte;
 
@@ -1160,6 +1166,10 @@ void snp_kexec_finish(void)
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

## [2] Tom Lendacky — 2025-05-01
*Subject: Re: [PATCH v3] x86/sev: Fix making shared pages private during kdump*

On 4/30/25 18:17, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Why this was occurring is because the original check was incorrect. The
check for

 ghcb <= addr + size

can result in skipping a range that should not have been skipped because
the "addr + size" is actually the start of a page/range after the end of
the range being checked. If the ghcb address was equal to addr + size,
then it was mistakenly considered part of the range when it really wasn't.

I think the check could have just been changed to:

  if (addr <= ghcb && ghcb < addr + size) {

The new checks are a bit clearer in showing normal pages vs huge pages,
though, but you can clearly see the "ghcb < addr + size" change to do the
right thing in the huge page case.

While it is likely that a GHCB page hasn't been part of a huge page during
all the testing, the change in snp_kexec_finish() to mask the address is
the proper thing to do. It probably doesn't even need the if check as the
mask can just be applied no matter what.

Thanks,
Tom

> 
> This subsequently causes a 0x404 #VC exception when this skipped

---

## [3] Borislav Petkov — 2025-05-02
*Subject: Re: [PATCH v3] x86/sev: Fix making shared pages private during kdump*

On Thu, May 01, 2025 at 08:56:00AM -0500, Tom Lendacky wrote:
> On 4/30/25 18:17, Ashish Kalra wrote:
> > From: Ashish Kalra <ashish.kalra@amd.com>

Sounds like I'll be getting a v3.1 with Tom's suggestions?

Thx.

---

## [4] Kalra, Ashish — 2025-05-02
*Subject: Re: [PATCH v3] x86/sev: Fix making shared pages private during kdump*

Hello Tom,

On 5/1/2025 8:56 AM, Tom Lendacky wrote:
> On 4/30/25 18:17, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

Yes that is true. 

> can result in skipping a range that should not have been skipped because
> the "addr + size" is actually the start of a page/range after the end of
Yes. 
 
> The new checks are a bit clearer in showing normal pages vs huge pages,
> though, but you can clearly see the "ghcb < addr + size" change to do the

Yes the clarity in these checks tempts me to keep these new checks, but as
you mentioned the right thing to do probably is "ghcb < addr + size" change.
 
> 
> While it is likely that a GHCB page hasn't been part of a huge page during

I agree, i really don't need the check as i can simply apply the mask as
the mask is based on page level/size.

mask = page_level_mask(level);
ghcb = (struct ghcb *)((unsigned long)ghcb & mask);

Thanks,
Ashish
 
> Thanks,
> Tom

---

## [5] Tom Lendacky — 2025-05-02
*Subject: Re: [PATCH v3] x86/sev: Fix making shared pages private during kdump*

On 5/2/25 14:32, Kalra, Ashish wrote:
> Hello Tom,
> 

> 
> I agree, i really don't need the check as i can simply apply the mask as

There's also a lot of casting back and forth with the ghcb variable. It
might be better to define it as an unsigned long and reduce all that.

Thanks,
Tom

>

---
