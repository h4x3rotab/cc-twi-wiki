---
title: 'sample/tsm-mr: Fix missing static for sample_report'
date: 2025-05-08
last_reply: 2025-05-13
message_count: 2
participants: ['Cedric Xing', 'Dan Williams']
---

## [1] Cedric Xing — 2025-05-08

0day robot reports 'sample_report' can be static, fix it up.

Reported-by: kernel test robot <lkp@intel.com>
Closes: https://lore.kernel.org/oe-kbuild-all/202505090938.avfIhLsl-lkp@intel.com/
Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 samples/tsm-mr/tsm_mr_sample.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/samples/tsm-mr/tsm_mr_sample.c b/samples/tsm-mr/tsm_mr_sample.c
index f3e16301de40..a2c652148639 100644
--- a/samples/tsm-mr/tsm_mr_sample.c
+++ b/samples/tsm-mr/tsm_mr_sample.c
@@ -8,7 +8,7 @@
 #include <linux/miscdevice.h>
 #include <crypto/hash.h>
 
-struct {
+static struct {
 	u8 static_mr[SHA384_DIGEST_SIZE];
 	u8 config_mr[SHA512_DIGEST_SIZE];
 	u8 rtmr0[SHA256_DIGEST_SIZE];

---

## [2] Dan Williams — 2025-05-13
*Subject: Re: [PATCH] sample/tsm-mr: Fix missing static for sample_report*

Cedric Xing wrote:
> 0day robot reports 'sample_report' can be static, fix it up.
> 

Looks good, applied.

---
