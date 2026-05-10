---
title: 'crypto: ccp - allow callers to use HV-Fixed page API when SEV is disabled'
date: 2026-02-06
last_reply: 2026-02-28
message_count: 3
participants: ['Ashish Kalra', 'Tom Lendacky', 'Herbert Xu']
---

## [1] Ashish Kalra — 2026-02-06

From: Ashish Kalra <ashish.kalra@amd.com>

When SEV is disabled, the HV-Fixed page allocation call fails, which in
turn causes SFS initialization to fail.

Fix the HV-Fixed API so callers (for example, SFS) can use it even when
SEV is disabled by performing normal page allocation and freeing.

Fixes: e09701dcdd9c ("crypto: ccp - Add new HV-Fixed page allocation/free API")
Cc: stable@vger.kernel.org
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 10 ++++------
 1 file changed, 4 insertions(+), 6 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 1cdadddb744e..0d90b5f6a454 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1105,15 +1105,12 @@ struct page *snp_alloc_hv_fixed_pages(unsigned int num_2mb_pages)
 {
 	struct psp_device *psp_master = psp_get_master_device();
 	struct snp_hv_fixed_pages_entry *entry;
-	struct sev_device *sev;
 	unsigned int order;
 	struct page *page;
 
-	if (!psp_master || !psp_master->sev_data)
+	if (!psp_master)
 		return NULL;
 
-	sev = psp_master->sev_data;
-
 	order = get_order(PMD_SIZE * num_2mb_pages);
 
 	/*
@@ -1126,7 +1123,8 @@ struct page *snp_alloc_hv_fixed_pages(unsigned int num_2mb_pages)
 	 * This API uses SNP_INIT_EX to transition allocated pages to HV_Fixed
 	 * page state, fail if SNP is already initialized.
 	 */
-	if (sev->snp_initialized)
+	if (psp_master->sev_data &&
+	    ((struct sev_device *)psp_master->sev_data)->snp_initialized)
 		return NULL;
 
 	/* Re-use freed pages that match the request */
@@ -1162,7 +1160,7 @@ void snp_free_hv_fixed_pages(struct page *page)
 	struct psp_device *psp_master = psp_get_master_device();
 	struct snp_hv_fixed_pages_entry *entry, *nentry;
 
-	if (!psp_master || !psp_master->sev_data)
+	if (!psp_master)
 		return;
 
 	/*

---

## [2] Tom Lendacky — 2026-02-09
*Subject: Re: [PATCH] crypto: ccp - allow callers to use HV-Fixed page API when
 SEV is disabled*

On 2/6/26 15:26, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  drivers/crypto/ccp/sev-dev.c | 10 ++++------

---

## [3] Herbert Xu — 2026-02-28
*Subject: Re: [PATCH] crypto: ccp - allow callers to use HV-Fixed page API
 when SEV is disabled*

On Fri, Feb 06, 2026 at 09:26:45PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Patch applied.  Thanks.

---
