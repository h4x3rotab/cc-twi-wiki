---
title: 'sample/tsm-mr: Use SHA-2 library APIs'
date: 2026-03-18
last_reply: 2026-03-19
message_count: 4
participants: ['Eric Biggers', 'Arnd Bergmann', 'Dan Williams']
---

## [1] Eric Biggers — 2026-03-18

Given that tsm_mr_sample has a particular set of algorithms that it
wants, just use the library APIs for those algorithms rather than
crypto_shash.  This is more straightforward and a bit more efficient.

This fixes an issue where this module failed to build due to the kconfig
options CRYPTO and CRYPTO_HASH not being selected.  Also, even if it
built, crypto_alloc_shash() could fail at runtime due to the needed
algorithms not being available.

The library functions simply use direct linking.  So if it builds, which
it will due to the kconfig options being enabled, they are available.

Fixes: f6953f1f9ec4 ("tsm-mr: Add tsm-mr sample code")
Fixes: 44a3873df811 ("coco/guest: Remove unneeded selection of CRYPTO")
Signed-off-by: Eric Biggers <ebiggers@kernel.org>
---

I'd like to take this via libcrypto-next, as that is where
"coco/guest: Remove unneeded selection of CRYPTO" is.

This is an alternative to
https://lore.kernel.org/r/20260318105200.1985712-1-arnd@kernel.org

 samples/Kconfig                |  2 +
 samples/tsm-mr/tsm_mr_sample.c | 68 +++++++++++++++++-----------------
 2 files changed, 35 insertions(+), 35 deletions(-)

diff --git a/samples/Kconfig b/samples/Kconfig
index 5bc7c9e5a59e..a75e8e78330d 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -184,10 +184,12 @@ config SAMPLE_TIMER
 	bool "Timer sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
 
 config SAMPLE_TSM_MR
 	tristate "TSM measurement sample"
+	select CRYPTO_LIB_SHA256
+	select CRYPTO_LIB_SHA512
 	select TSM_MEASUREMENTS
 	select VIRT_DRIVERS
 	help
 	  Build a sample module that emulates MRs (Measurement Registers) and
 	  exposes them to user mode applications through the TSM sysfs
diff --git a/samples/tsm-mr/tsm_mr_sample.c b/samples/tsm-mr/tsm_mr_sample.c
index a2c652148639..c79dbc1e0456 100644
--- a/samples/tsm-mr/tsm_mr_sample.c
+++ b/samples/tsm-mr/tsm_mr_sample.c
@@ -4,11 +4,11 @@
 #define pr_fmt(x) KBUILD_MODNAME ": " x
 
 #include <linux/module.h>
 #include <linux/tsm-mr.h>
 #include <linux/miscdevice.h>
-#include <crypto/hash.h>
+#include <crypto/sha2.h>
 
 static struct {
 	u8 static_mr[SHA384_DIGEST_SIZE];
 	u8 config_mr[SHA512_DIGEST_SIZE];
 	u8 rtmr0[SHA256_DIGEST_SIZE];
@@ -21,51 +21,49 @@ static struct {
 	.rtmr1 = "rtmr1",
 };
 
 static int sample_report_refresh(const struct tsm_measurements *tm)
 {
-	struct crypto_shash *tfm;
-	int rc;
-
-	tfm = crypto_alloc_shash(hash_algo_name[HASH_ALGO_SHA512], 0, 0);
-	if (IS_ERR(tfm)) {
-		pr_err("crypto_alloc_shash failed: %ld\n", PTR_ERR(tfm));
-		return PTR_ERR(tfm);
-	}
-
-	rc = crypto_shash_tfm_digest(tfm, (u8 *)&sample_report,
-				     offsetof(typeof(sample_report),
-					      report_digest),
-				     sample_report.report_digest);
-	crypto_free_shash(tfm);
-	if (rc)
-		pr_err("crypto_shash_tfm_digest failed: %d\n", rc);
-	return rc;
+	sha512((const u8 *)&sample_report,
+	       offsetof(typeof(sample_report), report_digest),
+	       sample_report.report_digest);
+	return 0;
 }
 
 static int sample_report_extend_mr(const struct tsm_measurements *tm,
 				   const struct tsm_measurement_register *mr,
 				   const u8 *data)
 {
-	SHASH_DESC_ON_STACK(desc, 0);
-	int rc;
-
-	desc->tfm = crypto_alloc_shash(hash_algo_name[mr->mr_hash], 0, 0);
-	if (IS_ERR(desc->tfm)) {
-		pr_err("crypto_alloc_shash failed: %ld\n", PTR_ERR(desc->tfm));
-		return PTR_ERR(desc->tfm);
+	union {
+		struct sha256_ctx sha256;
+		struct sha384_ctx sha384;
+		struct sha512_ctx sha512;
+	} ctx;
+
+	switch (mr->mr_hash) {
+	case HASH_ALGO_SHA256:
+		sha256_init(&ctx.sha256);
+		sha256_update(&ctx.sha256, mr->mr_value, mr->mr_size);
+		sha256_update(&ctx.sha256, data, mr->mr_size);
+		sha256_final(&ctx.sha256, mr->mr_value);
+		return 0;
+	case HASH_ALGO_SHA384:
+		sha384_init(&ctx.sha384);
+		sha384_update(&ctx.sha384, mr->mr_value, mr->mr_size);
+		sha384_update(&ctx.sha384, data, mr->mr_size);
+		sha384_final(&ctx.sha384, mr->mr_value);
+		return 0;
+	case HASH_ALGO_SHA512:
+		sha512_init(&ctx.sha512);
+		sha512_update(&ctx.sha512, mr->mr_value, mr->mr_size);
+		sha512_update(&ctx.sha512, data, mr->mr_size);
+		sha512_final(&ctx.sha512, mr->mr_value);
+		return 0;
+	default:
+		pr_err("Unsupported hash algorithm: %d\n", mr->mr_hash);
+		return -EOPNOTSUPP;
 	}
-
-	rc = crypto_shash_init(desc);
-	if (!rc)
-		rc = crypto_shash_update(desc, mr->mr_value, mr->mr_size);
-	if (!rc)
-		rc = crypto_shash_finup(desc, data, mr->mr_size, mr->mr_value);
-	crypto_free_shash(desc->tfm);
-	if (rc)
-		pr_err("SHA calculation failed: %d\n", rc);
-	return rc;
 }
 
 #define MR_(mr, hash) .mr_value = &sample_report.mr, TSM_MR_(mr, hash)
 static const struct tsm_measurement_register sample_mrs[] = {
 	/* static MR, read-only */

---

## [2] Arnd Bergmann — 2026-03-18
*Subject: Re: [PATCH] sample/tsm-mr: Use SHA-2 library APIs*

On Wed, Mar 18, 2026, at 17:42, Eric Biggers wrote:
> Given that tsm_mr_sample has a particular set of algorithms that it
> wants, just use the library APIs for those algorithms rather than

Thanks for fixing this! It is indeed nicer than the fix
I sent earlier today.

Acked-by: Arnd Bergmann <arnd@arndb.de>

---

## [3] Eric Biggers — 2026-03-19
*Subject: Re: [PATCH] sample/tsm-mr: Use SHA-2 library APIs*

On Wed, Mar 18, 2026 at 08:57:01PM +0100, Arnd Bergmann wrote:
> On Wed, Mar 18, 2026, at 17:42, Eric Biggers wrote:
> > Given that tsm_mr_sample has a particular set of algorithms that it

Thanks.  Additional acks from the people owning this code (Dan, Cedric?)
would be appreciated.  But since this fixes a build error and is related
to the crypto library, I went ahead and applied this to
https://git.kernel.org/pub/scm/linux/kernel/git/ebiggers/linux.git/log/?h=libcrypto-next

I also found that the build error is pre-existing, as CRYPTO_HASH was
not being selected.  "coco/guest: Remove unneeded selection of CRYPTO"
just made it a bit easier to encounter, by not selecting CRYPTO either.

So I updated the second paragraph of the commit message to:

    This also fixes a bug where this module failed to build if it was
    enabled without CRYPTO_HASH happening to be set elsewhere in the
    kconfig.  (With the concurrent change to make TSM_MEASUREMENTS stop
    selecting CRYPTO, this existing build error would have become easier to
    encounter, as well.)  Also, even if it built, crypto_alloc_shash() could
    fail at runtime due to the needed algorithms not being available.

I also put this commit before "coco/guest: Remove unneeded selection of
CRYPTO" and dropped the Fixes reference to that.  So now it just has:

    Fixes: f6953f1f9ec4 ("tsm-mr: Add tsm-mr sample code")

- Eric

---

## [4] Dan Williams — 2026-03-19
*Subject: Re: [PATCH] sample/tsm-mr: Use SHA-2 library APIs*

Eric Biggers wrote:
> On Wed, Mar 18, 2026 at 08:57:01PM +0100, Arnd Bergmann wrote:
> > On Wed, Mar 18, 2026, at 17:42, Eric Biggers wrote:


It looks good to me:

Acked-by: Dan Williams <dan.j.williams@intel.com>

Feel free to take it through your tree since I have nothing immediately
pending for tsm.git.

---
