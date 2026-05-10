---
title: 'coco/guest: Remove unneeded selection of CRYPTO'
date: 2025-12-03
last_reply: 2026-03-15
message_count: 5
participants: ['Eric Biggers', 'Dan Williams']
---

## [1] Eric Biggers — 2025-12-03

All that's needed here is CRYPTO_HASH_INFO.  It used to be the case that
CRYPTO_HASH_INFO was visible only when CRYPTO, but that was fixed by
commit aacb37f597d0 ("lib/crypto: hash_info: Move hash_info.c into
lib/crypto/").  Now CRYPTO_HASH_INFO can be selected directly.

Signed-off-by: Eric Biggers <ebiggers@kernel.org>
---
 drivers/virt/coco/guest/Kconfig | 1 -
 1 file changed, 1 deletion(-)

diff --git a/drivers/virt/coco/guest/Kconfig b/drivers/virt/coco/guest/Kconfig
index 3d5e1d05bf34..da570dc4bd48 100644
--- a/drivers/virt/coco/guest/Kconfig
+++ b/drivers/virt/coco/guest/Kconfig
@@ -11,7 +11,6 @@ config TSM_REPORTS
 	tristate
 
 config TSM_MEASUREMENTS
 	select TSM_GUEST
 	select CRYPTO_HASH_INFO
-	select CRYPTO
 	bool

base-commit: b2c27842ba853508b0da00187a7508eb3a96c8f7

---

## [2] Eric Biggers — 2026-01-08
*Subject: Re: [PATCH] coco/guest: Remove unneeded selection of CRYPTO*

On Wed, Dec 03, 2025 at 09:55:12PM -0800, Eric Biggers wrote:
> All that's needed here is CRYPTO_HASH_INFO.  It used to be the case that
> CRYPTO_HASH_INFO was visible only when CRYPTO, but that was fixed by

Any interest in applying this patch?

- Eric

---

## [3] Eric Biggers — 2026-03-14
*Subject: Re: [PATCH] coco/guest: Remove unneeded selection of CRYPTO*

On Thu, Jan 08, 2026 at 06:26:22PM -0800, Eric Biggers wrote:
> On Wed, Dec 03, 2025 at 09:55:12PM -0800, Eric Biggers wrote:
> > All that's needed here is CRYPTO_HASH_INFO.  It used to be the case that

Ping.

If there continues to be no response, I'll take this patch via
libcrypto-next.

- Eric

---

## [4] Dan Williams — 2026-03-14
*Subject: Re: [PATCH] coco/guest: Remove unneeded selection of CRYPTO*

Eric Biggers wrote:
> On Thu, Jan 08, 2026 at 06:26:22PM -0800, Eric Biggers wrote:
> > On Wed, Dec 03, 2025 at 09:55:12PM -0800, Eric Biggers wrote:

Apologies, not sure how I missed this.

Acked-by: Dan Williams <dan.j.williams@intel.com>

...and yes, fine for this to go through libcrypto-next.

---

## [5] Eric Biggers — 2026-03-15
*Subject: Re: [PATCH] coco/guest: Remove unneeded selection of CRYPTO*

On Sat, Mar 14, 2026 at 03:04:02PM -0700, Dan Williams wrote:
> Eric Biggers wrote:
> > On Thu, Jan 08, 2026 at 06:26:22PM -0800, Eric Biggers wrote:

Applied to https://git.kernel.org/pub/scm/linux/kernel/git/ebiggers/linux.git/log/?h=libcrypto-next

- Eric

---
