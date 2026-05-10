---
title: "[v2] virt: tdx-guest: Don't free decrypted memory"
date: 2024-06-14
last_reply: 2024-06-17
message_count: 3
participants: ['Li RongQing', 'Edgecombe, Rick P', 'kirill.shutemov@linux.intel.com']
---

## [1] Li RongQing — 2024-06-14

In CoCo VMs it is possible for the untrusted host to cause
set_memory_decrypted() to fail such that an error is returned
and the resulting memory is shared. Callers need to take care
to handle these errors to avoid returning decrypted (shared)
memory to the page allocator, which could lead to functional
or security issues.

So when set_memory_decrypted fails, leak decrypted memory, and
print an error message

Signed-off-by: Li RongQing <lirongqing@baidu.com>
---
diff with v1: leak the page, and print error

 drivers/virt/coco/tdx-guest/tdx-guest.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 1253bf7..3a6e76c8 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -125,7 +125,7 @@ static void *alloc_quote_buf(void)
 		return NULL;
 
 	if (set_memory_decrypted((unsigned long)addr, count)) {
-		free_pages_exact(addr, len);
+		pr_err("Failed to set Quote buffer decrypted, leak the buffer\n");
 		return NULL;
 	}

---

## [2] Edgecombe, Rick P — 2024-06-14
*Subject: Re: [PATCH][v2] virt: tdx-guest: Don't free decrypted memory*

On Fri, 2024-06-14 at 13:14 +0800, Li RongQing wrote:
> In CoCo VMs it is possible for the untrusted host to cause
> set_memory_decrypted() to fail such that an error is returned

I'm not sure we need the error message, because the set_memory() failure we are
most worried about already has a WARN. But, I could be convinced either way. It
seems to fit with the other code in the file.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [3] kirill.shutemov@linux.intel.com — 2024-06-17
*Subject: Re: [PATCH][v2] virt: tdx-guest: Don't free decrypted memory*

On Fri, Jun 14, 2024 at 04:13:46PM +0000, Edgecombe, Rick P wrote:
> On Fri, 2024-06-14 at 13:14 +0800, Li RongQing wrote:
> > In CoCo VMs it is possible for the untrusted host to cause

Yeah, I think we should just remove the pr_err(). It will be shadowed by
the stack trace and WARN() anyway.

---
