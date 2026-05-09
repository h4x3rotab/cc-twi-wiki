---
title: 'crypto: ccp: Abort doing SEV INIT if SNP INIT fails'
date: 2025-03-18
last_reply: 2025-03-18
message_count: 3
participants: ['Ashish Kalra', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-03-18

From: Ashish Kalra <ashish.kalra@amd.com>

If SNP host support (SYSCFG.SNPEn) is set, then the RMP table must
be initialized before calling SEV INIT.

In other words, if SNP_INIT(_EX) is not issued or fails then
SEV INIT will fail if SNP host support (SYSCFG.SNPEn) is enabled.

Fixes: 1ca5614b84eed ("crypto: ccp: Add support to initialize the AMD-SP for SEV-SNP")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>

v2:
- Fix commit logs.
---
 drivers/crypto/ccp/sev-dev.c | 7 ++-----
 1 file changed, 2 insertions(+), 5 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 2e87ca0e292a..a0e3de94704e 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1112,7 +1112,7 @@ static int __sev_snp_init_locked(int *error)
 	if (!sev_version_greater_or_equal(SNP_MIN_API_MAJOR, SNP_MIN_API_MINOR)) {
 		dev_dbg(sev->dev, "SEV-SNP support requires firmware version >= %d:%d\n",
 			SNP_MIN_API_MAJOR, SNP_MIN_API_MINOR);
-		return 0;
+		return -EOPNOTSUPP;
 	}
 
 	/* SNP_INIT requires MSR_VM_HSAVE_PA to be cleared on all CPUs. */
@@ -1325,12 +1325,9 @@ static int _sev_platform_init_locked(struct sev_platform_init_args *args)
 	 */
 	rc = __sev_snp_init_locked(&args->error);
 	if (rc && rc != -ENODEV) {
-		/*
-		 * Don't abort the probe if SNP INIT failed,
-		 * continue to initialize the legacy SEV firmware.
-		 */
 		dev_err(sev->dev, "SEV-SNP: failed to INIT rc %d, error %#x\n",
 			rc, args->error);
+		return rc;
 	}
 
 	/* Defer legacy SEV/SEV-ES support if allowed by caller/module. */

---

## [2] Tom Lendacky — 2025-03-18
*Subject: Re: [PATCH v2] crypto: ccp: Abort doing SEV INIT if SNP INIT fails*

On 3/18/25 15:07, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Just wondering if this really needs a Fixes: tag. Either way SNP and SEV
won't be initialized, you're just returning earlier with an error code
rather than attempting the SEV_INIT(_EX) and getting back a failing
error code.

Thanks,
Tom

> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
>

---

## [3] Kalra, Ashish — 2025-03-18
*Subject: Re: [PATCH v2] crypto: ccp: Abort doing SEV INIT if SNP INIT fails*

Hello Tom,

On 3/18/2025 3:29 PM, Tom Lendacky wrote:
> On 3/18/25 15:07, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

Yes, that's true in a way, as continuing with SEV INIT after SNP INIT(_EX) failure
will still cause SEV INIT to fail, we are simply aborting here after 
SNP INIT(_EX) failure, so i will drop the Fixes: tag and post another version.

Thanks,
Ashish

> 
> Thanks,

---
