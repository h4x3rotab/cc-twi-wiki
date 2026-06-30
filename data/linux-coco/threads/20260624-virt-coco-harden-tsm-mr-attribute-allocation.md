---
title: 'virt: coco: harden TSM MR attribute allocation'
date: 2026-06-24
last_reply: 2026-06-24
message_count: 1
participants: ['Yousef Alhouseen']
---

## [1] Yousef Alhouseen — 2026-06-24

tsm_mr_create_attribute_group() combines the bin_attribute pointer table
and generated MR name strings into one allocation. It open-coded both the
aggregate name length calculation and the final allocation size as plain
additions and multiplication.

The current in-tree caller uses a small static MR table, but this helper is
exported for confidential-computing guest drivers. Reject impossible MR
definitions instead of allowing arithmetic wraparound to under-allocate the
combined attributes buffer.

Use size_add() and array_size() for the name-length accumulation and the
final allocation size.

Signed-off-by: Yousef Alhouseen <alhouseenyousef@gmail.com>
---
 drivers/virt/coco/guest/tsm-mr.c | 24 +++++++++++++++++-------
 1 file changed, 17 insertions(+), 7 deletions(-)

diff --git a/drivers/virt/coco/guest/tsm-mr.c b/drivers/virt/coco/guest/tsm-mr.c
index 657b9c573..789988111 100644
--- a/drivers/virt/coco/guest/tsm-mr.c
+++ b/drivers/virt/coco/guest/tsm-mr.c
@@ -140,7 +140,11 @@ static ssize_t tm_digest_write(struct file *filp, struct kobject *kobj,
 const struct attribute_group *
 tsm_mr_create_attribute_group(const struct tsm_measurements *tm)
 {
+	const struct bin_attribute **attrs __free(kfree) = NULL;
+	struct tm_context *ctx __free(kfree) = NULL;
+	size_t attrs_size, name_len;
 	size_t nlen;
+	char *name, *end;
 
 	if (!tm || !tm->mrs)
 		return ERR_PTR(-EINVAL);
@@ -164,8 +168,12 @@ tsm_mr_create_attribute_group(const struct tsm_measurements *tm)
 			return ERR_PTR(-EINVAL);
 
 		/* MR sysfs attribute names have the form of MRNAME:HASH */
-		nlen += strlen(tm->mrs[i].mr_name) + 1 +
-			strlen(hash_algo_name[tm->mrs[i].mr_hash]) + 1;
+		name_len = size_add(strlen(tm->mrs[i].mr_name),
+				    strlen(hash_algo_name[tm->mrs[i].mr_hash]));
+		name_len = size_add(name_len, 2);
+		nlen = size_add(nlen, name_len);
+		if (name_len == SIZE_MAX || nlen == SIZE_MAX)
+			return ERR_PTR(-EINVAL);
 	}
 
 	/*
@@ -173,11 +181,13 @@ tsm_mr_create_attribute_group(const struct tsm_measurements *tm)
 	 * so that we don't have to free MR names one-by-one in
 	 * tsm_mr_free_attribute_group()
 	 */
-	const struct bin_attribute **attrs __free(kfree) =
-		kzalloc(sizeof(*attrs) * (tm->nr_mrs + 1) + nlen, GFP_KERNEL);
-	struct tm_context *ctx __free(kfree) =
-		kzalloc_flex(*ctx, mrs, tm->nr_mrs);
-	char *name, *end;
+	attrs_size = size_add(array_size(size_add(tm->nr_mrs, 1),
+					 sizeof(*attrs)), nlen);
+	if (attrs_size == SIZE_MAX)
+		return ERR_PTR(-EINVAL);
+
+	attrs = kzalloc(attrs_size, GFP_KERNEL);
+	ctx = kzalloc_flex(*ctx, mrs, tm->nr_mrs);
 
 	if (!ctx || !attrs)
 		return ERR_PTR(-ENOMEM);

---
