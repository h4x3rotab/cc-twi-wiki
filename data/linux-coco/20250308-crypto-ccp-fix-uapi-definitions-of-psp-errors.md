---
title: 'crypto: ccp: Fix uAPI definitions of PSP errors'
date: 2025-03-08
last_reply: 2025-03-15
message_count: 5
participants: ['Alexey Kardashevskiy', 'Dionna Amalie Glaze', 'Borislav Petkov', 'Herbert Xu']
---

## [1] Alexey Kardashevskiy — 2025-03-08

Additions to the error enum after explicit 0x27 setting for
SEV_RET_INVALID_KEY leads to incorrect value assignments.

Use explicit values to match the manufacturer specifications more
clearly.

Fixes: 3a45dc2b419e ("crypto: ccp: Define the SEV-SNP commands")
CC: stable@vger.kernel.org
Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---

Reposting as requested in
https://lore.kernel.org/r/Z7f2S3MigLEY80P2@gondor.apana.org.au

I wrote it in the first place but since then it travelled a lot,
feel free to correct the chain of SOBs and RB :)
---
 include/uapi/linux/psp-sev.h | 21 +++++++++++++-------
 1 file changed, 14 insertions(+), 7 deletions(-)

diff --git a/include/uapi/linux/psp-sev.h b/include/uapi/linux/psp-sev.h
index 832c15d9155b..eeb20dfb1fda 100644
--- a/include/uapi/linux/psp-sev.h
+++ b/include/uapi/linux/psp-sev.h
@@ -73,13 +73,20 @@ typedef enum {
 	SEV_RET_INVALID_PARAM,
 	SEV_RET_RESOURCE_LIMIT,
 	SEV_RET_SECURE_DATA_INVALID,
-	SEV_RET_INVALID_KEY = 0x27,
-	SEV_RET_INVALID_PAGE_SIZE,
-	SEV_RET_INVALID_PAGE_STATE,
-	SEV_RET_INVALID_MDATA_ENTRY,
-	SEV_RET_INVALID_PAGE_OWNER,
-	SEV_RET_INVALID_PAGE_AEAD_OFLOW,
-	SEV_RET_RMP_INIT_REQUIRED,
+	SEV_RET_INVALID_PAGE_SIZE          = 0x0019,
+	SEV_RET_INVALID_PAGE_STATE         = 0x001A,
+	SEV_RET_INVALID_MDATA_ENTRY        = 0x001B,
+	SEV_RET_INVALID_PAGE_OWNER         = 0x001C,
+	SEV_RET_AEAD_OFLOW                 = 0x001D,
+	SEV_RET_EXIT_RING_BUFFER           = 0x001F,
+	SEV_RET_RMP_INIT_REQUIRED          = 0x0020,
+	SEV_RET_BAD_SVN                    = 0x0021,
+	SEV_RET_BAD_VERSION                = 0x0022,
+	SEV_RET_SHUTDOWN_REQUIRED          = 0x0023,
+	SEV_RET_UPDATE_FAILED              = 0x0024,
+	SEV_RET_RESTORE_REQUIRED           = 0x0025,
+	SEV_RET_RMP_INITIALIZATION_FAILED  = 0x0026,
+	SEV_RET_INVALID_KEY                = 0x0027,
 	SEV_RET_MAX,
 } sev_ret_code;

---

## [2] Dionna Amalie Glaze — 2025-03-07
*Subject: Re: [PATCH] crypto: ccp: Fix uAPI definitions of PSP errors*

On Fri, Mar 7, 2025 at 5:10 PM Alexey Kardashevskiy <aik@amd.com> wrote:
>
> Additions to the error enum after explicit 0x27 setting for

It's all good. Thanks for seeing this through to the end.

---

## [3] Borislav Petkov — 2025-03-08
*Subject: Re: [PATCH] crypto: ccp: Fix uAPI definitions of PSP errors*

On Fri, Mar 07, 2025 at 09:40:52PM -0800, Dionna Amalie Glaze wrote:
> On Fri, Mar 7, 2025 at 5:10 PM Alexey Kardashevskiy <aik@amd.com> wrote:
> >

It should be corrected because the current SOB chain says that Dionna is the
author but From is yours, making you the author when it gets applied.

All is documented here and in the following sections:

https://kernel.org/doc/html/latest/process/submitting-patches.html#sign-your-work-the-developer-s-certificate-of-origin

---

## [4] Herbert Xu — 2025-03-15
*Subject: Re: [PATCH] crypto: ccp: Fix uAPI definitions of PSP errors*

On Sat, Mar 08, 2025 at 02:33:08PM +0100, Borislav Petkov wrote:
>
> It should be corrected because the current SOB chain says that Dionna is the

I'll fix this one by hand.

Thanks,

---

## [5] Herbert Xu — 2025-03-15
*Subject: Re: [PATCH] crypto: ccp: Fix uAPI definitions of PSP errors*

On Sat, Mar 08, 2025 at 12:10:28PM +1100, Alexey Kardashevskiy wrote:
> Additions to the error enum after explicit 0x27 setting for
> SEV_RET_INVALID_KEY leads to incorrect value assignments.

Patch applied.  Thanks.

---
