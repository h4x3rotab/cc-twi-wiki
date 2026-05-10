---
title: 'virt/tdx: Enhance tdx-guest driver with improved memory management'
date: 2025-03-09
last_reply: 2025-03-09
message_count: 2
participants: ['liu.yun@linux.dev', 'Dave Hansen']
---

## [1] liu.yun@linux.dev — 2025-03-09

From: Jackie Liu <liuyun01@kylinos.cn>

This patch refines the tdx-guest driver by introducing better memory
management and error handling practices. The use of the `__free` attribute
ensures that allocated memory for `reportdata` and `tdreport` is
automatically freed, reducing the risk of memory leaks. Additionally,
the manual mutex lock/unlock has been replaced with `scoped_cond_guard`
to ensure proper mutex handling and simplify the code.

Error handling has been streamlined by returning directly on failure,
eliminating unnecessary `goto` statements. These changes not only
enhance the robustness of the driver but also improve its readability
and maintainability.

Signed-off-by: Jackie Liu <liuyun01@kylinos.cn>
---
 drivers/virt/coco/tdx-guest/tdx-guest.c | 179 ++++++++++--------------
 1 file changed, 77 insertions(+), 102 deletions(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 224e7dde9cde..2b2aeae8d068 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -17,6 +17,7 @@
 #include <linux/delay.h>
 #include <linux/tsm.h>
 #include <linux/sizes.h>
+#include <linux/cleanup.h>
 
 #include <uapi/linux/tdx-guest.h>
 
@@ -68,37 +69,28 @@ static u32 getquote_timeout = 30;
 
 static long tdx_get_report0(struct tdx_report_req __user *req)
 {
-	u8 *reportdata, *tdreport;
 	long ret;
 
-	reportdata = kmalloc(TDX_REPORTDATA_LEN, GFP_KERNEL);
+	u8 *reportdata __free(kfree) = kmalloc(TDX_REPORTDATA_LEN, GFP_KERNEL);
 	if (!reportdata)
 		return -ENOMEM;
 
-	tdreport = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
-	if (!tdreport) {
-		ret = -ENOMEM;
-		goto out;
-	}
+	u8 *tdreport __free(kfree) = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
+	if (!tdreport)
+		return -ENOMEM;
 
-	if (copy_from_user(reportdata, req->reportdata, TDX_REPORTDATA_LEN)) {
-		ret = -EFAULT;
-		goto out;
-	}
+	if (copy_from_user(reportdata, req->reportdata, TDX_REPORTDATA_LEN))
+		return -EFAULT;
 
 	/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
 	ret = tdx_mcall_get_report0(reportdata, tdreport);
 	if (ret)
-		goto out;
+		return ret;
 
 	if (copy_to_user(req->tdreport, tdreport, TDX_REPORT_LEN))
-		ret = -EFAULT;
-
-out:
-	kfree(reportdata);
-	kfree(tdreport);
+		return -EFAULT;
 
-	return ret;
+	return 0;
 }
 
 static void free_quote_buf(void *buf)
@@ -159,92 +151,75 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 
 static int tdx_report_new(struct tsm_report *report, void *data)
 {
-	u8 *buf, *reportdata = NULL, *tdreport = NULL;
-	struct tdx_quote_buf *quote_buf = quote_data;
-	struct tsm_desc *desc = &report->desc;
-	int ret;
-	u64 err;
-
-	/* TODO: switch to guard(mutex_intr) */
-	if (mutex_lock_interruptible(&quote_lock))
-		return -EINTR;
-
-	/*
-	 * If the previous request is timedout or interrupted, and the
-	 * Quote buf status is still in GET_QUOTE_IN_FLIGHT (owned by
-	 * VMM), don't permit any new request.
-	 */
-	if (quote_buf->status == GET_QUOTE_IN_FLIGHT) {
-		ret = -EBUSY;
-		goto done;
-	}
-
-	if (desc->inblob_len != TDX_REPORTDATA_LEN) {
-		ret = -EINVAL;
-		goto done;
-	}
-
-	reportdata = kmalloc(TDX_REPORTDATA_LEN, GFP_KERNEL);
-	if (!reportdata) {
-		ret = -ENOMEM;
-		goto done;
-	}
-
-	tdreport = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
-	if (!tdreport) {
-		ret = -ENOMEM;
-		goto done;
+	scoped_cond_guard(mutex_intr, return -EINTR, &quote_lock) {
+		int ret;
+		u8 *buf;
+		struct tdx_quote_buf *quote_buf = quote_data;
+		struct tsm_desc *desc = &report->desc;
+		u64 err;
+
+		/*
+		 * If the previous request is timedout or interrupted, and the
+		 * Quote buf status is still in GET_QUOTE_IN_FLIGHT (owned by
+		 * VMM), don't permit any new request.
+		 */
+		if (quote_buf->status == GET_QUOTE_IN_FLIGHT)
+			return -EBUSY;
+
+		if (desc->inblob_len != TDX_REPORTDATA_LEN)
+			return -EINVAL;
+
+		u8 *reportdata __free(kfree) = kmalloc(TDX_REPORTDATA_LEN, GFP_KERNEL);
+		if (!reportdata)
+			return -ENOMEM;
+
+		u8 *tdreport __free(kfree) = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
+		if (!tdreport)
+			return -ENOMEM;
+
+		memcpy(reportdata, desc->inblob, desc->inblob_len);
+
+		/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
+		ret = tdx_mcall_get_report0(reportdata, tdreport);
+		if (ret) {
+			pr_err("GetReport call failed\n");
+			return ret;
+		}
+
+		memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
+
+		/* Update Quote buffer header */
+		quote_buf->version = GET_QUOTE_CMD_VER;
+		quote_buf->in_len = TDX_REPORT_LEN;
+
+		memcpy(quote_buf->data, tdreport, TDX_REPORT_LEN);
+
+		err = tdx_hcall_get_quote(quote_data, GET_QUOTE_BUF_SIZE);
+		if (err) {
+			pr_err("GetQuote hypercall failed, status:%llx\n", err);
+			return -EIO;
+		}
+
+		ret = wait_for_quote_completion(quote_buf, getquote_timeout);
+		if (ret) {
+			pr_err("GetQuote request timedout\n");
+			return ret;
+		}
+
+		buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
+		if (!buf)
+			return -ENOMEM;
+
+		report->outblob = buf;
+		report->outblob_len = quote_buf->out_len;
+
+		/*
+		 * TODO: parse the PEM-formatted cert chain out of the quote buffer when
+		 * provided
+		 */
 	}
 
-	memcpy(reportdata, desc->inblob, desc->inblob_len);
-
-	/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
-	ret = tdx_mcall_get_report0(reportdata, tdreport);
-	if (ret) {
-		pr_err("GetReport call failed\n");
-		goto done;
-	}
-
-	memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
-
-	/* Update Quote buffer header */
-	quote_buf->version = GET_QUOTE_CMD_VER;
-	quote_buf->in_len = TDX_REPORT_LEN;
-
-	memcpy(quote_buf->data, tdreport, TDX_REPORT_LEN);
-
-	err = tdx_hcall_get_quote(quote_data, GET_QUOTE_BUF_SIZE);
-	if (err) {
-		pr_err("GetQuote hypercall failed, status:%llx\n", err);
-		ret = -EIO;
-		goto done;
-	}
-
-	ret = wait_for_quote_completion(quote_buf, getquote_timeout);
-	if (ret) {
-		pr_err("GetQuote request timedout\n");
-		goto done;
-	}
-
-	buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
-	if (!buf) {
-		ret = -ENOMEM;
-		goto done;
-	}
-
-	report->outblob = buf;
-	report->outblob_len = quote_buf->out_len;
-
-	/*
-	 * TODO: parse the PEM-formatted cert chain out of the quote buffer when
-	 * provided
-	 */
-done:
-	mutex_unlock(&quote_lock);
-	kfree(reportdata);
-	kfree(tdreport);
-
-	return ret;
+	return 0;
 }
 
 static bool tdx_report_attr_visible(int n)

---

## [2] Dave Hansen — 2025-03-09
*Subject: Re: [PATCH] virt/tdx: Enhance tdx-guest driver with improved memory
 management*

On 3/9/25 07:04, liu.yun@linux.dev wrote:
> From: Jackie Liu <liuyun01@kylinos.cn>
> 

Thanks for the patch.

But, no, sorry, we're not going to take patches like this. If you're
refactoring the code for _other_ reasons and want to convert over to the
new fancy stuff, go ahead.

But, we're not going to introduce bugs (and this kind of rework *WILL*
have bugs), make everyone else's code harder to merge, and clutter up
the history just to move to the newest shiny thing.

I'd much rather folks spend their time reviewing code or fixing bugs
than just churning code around.

Also, if anyone _does_ make code to use these new locks, *PLEASE* don't
do it this way:

> +	scoped_cond_guard(mutex_intr, return -EINTR, &quote_lock) {
> +		int ret;

Indentation matters. Increasing the indenting on the whole function
makes it less readable. Don't do it like that ^.

I feel the need to reiterate: please don't send patches like this.
Please tell your friends.

---
