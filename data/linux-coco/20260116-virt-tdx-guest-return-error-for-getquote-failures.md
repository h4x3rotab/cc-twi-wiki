---
title: 'virt: tdx-guest: Return error for GetQuote failures'
date: 2026-01-16
last_reply: 2026-01-16
message_count: 1
participants: ['Kuppuswamy Sathyanarayanan']
---

## [1] Kuppuswamy Sathyanarayanan — 2026-01-16

Currently, the GetQuote request handler returns explicit errors for
hypercall-level failures and timeouts, but it ignores some VMM
failures (e.g., GET_QUOTE_SERVICE_UNAVAILABLE), for which it returns
success with a zero-length Quote. This makes error handling in
userspace more complex.

The VMM reports failures via the status field in the shared GPA header,
which is inaccessible to userspace because only the Quote payload is
exposed to userspace. Parse the status field in the kernel and return
an error for Quote failures.

This preserves existing ABI behavior as userspace already treats a
zero-length Quote as a failure.

Refer to GHCI specification [1], section "TDG.VP.VMCALL <GetQuote>",
Table 3-10 and Table 3-11 for details on the GPA header and
GetQuote status codes.

Fixes: f4738f56d1dc ("virt: tdx-guest: Add Quote generation support using TSM_REPORTS")
Reported-by: Xiaoyao Li <xiaoyao.li@intel.com>
Closes: https://lore.kernel.org/linux-coco/6bdf569c-684a-4459-af7c-4430691804eb@linux.intel.com/T/#u
Closes: https://github.com/confidential-containers/guest-components/issues/823
Signed-off-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Tested-by: Mikko Ylinen <mikko.ylinen@linux.intel.com>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Link: https://cdrdv2.intel.com/v1/dl/getContent/858626 # [1]
---

Changes since v5:
 * Simplified the commit message to focus on the constraint of
   GPA header inaccessibility (Dave).
 * Reordered commit tags as per kernel process (Dave).
 * Refined the commit title to reflect the fix.
 * Replaced pr_err() with pr_debug() for error log to avoid dmesg spam.
 * Added Link to GHCI spec.

Changes since v4:
 * Rebased on top of v6.18-rc1
 * Added Tested-by tag from Mikko.
 * Added more details in commit log to clarify no user impact and also
   link to a related github issue.
 * Added error message for the failed case.

Changes since v3:
 * Rebased on top of v6.9-rc1
 * Added Dan's Reviewed-by tag.

Changes since v2:
 * Updated the commit log (Dan)
 * Removed pr_err message.

Changes since v1:
 * Updated the commit log (Kirill)
 drivers/virt/coco/tdx-guest/tdx-guest.c | 5 +++++
 1 file changed, 5 insertions(+)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 4e239ec960c9..a3c8f5c19bae 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -304,6 +304,11 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 		return ret;
 	}
 
+	if (quote_buf->status != GET_QUOTE_SUCCESS) {
+		pr_debug("GetQuote request failed, status:%llx\n", quote_buf->status);
+		return -EIO;
+	}
+
 	buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
 	if (!buf)
 		return -ENOMEM;

---
