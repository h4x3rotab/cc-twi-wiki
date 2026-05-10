---
title: "[v3] virt: tdx-guest: Don't free decrypted memory"
date: 2024-06-19
last_reply: 2024-06-19
message_count: 2
participants: ['Li RongQing', 'Kirill A. Shutemov']
---

## [1] Li RongQing — 2024-06-19

In CoCo VMs it is possible for the untrusted host to cause
set_memory_decrypted() to fail such that an error is returned
and the resulting memory is shared. Callers need to take care
to handle these errors to avoid returning decrypted (shared)
memory to the page allocator, which could lead to functional
or security issues. So leak the decrypted memory when
set_memory_decrypted fails, and don't need to print an error
since set_memory_decrypted will call WARN_ONCE.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Li RongQing <lirongqing@baidu.com>
---
 diff with v2: remove print error
 diff with v1: leak the page, and print error

 drivers/virt/coco/tdx-guest/tdx-guest.c | 4 +---
 1 file changed, 1 insertion(+), 3 deletions(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 1253bf7..8575d98 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -124,10 +124,8 @@ static void *alloc_quote_buf(void)
 	if (!addr)
 		return NULL;
 
-	if (set_memory_decrypted((unsigned long)addr, count)) {
-		free_pages_exact(addr, len);
+	if (set_memory_decrypted((unsigned long)addr, count))
 		return NULL;
-	}
 
 	return addr;
 }

---

## [2] Kirill A. Shutemov — 2024-06-19
*Subject: Re: [PATCH][v3] virt: tdx-guest: Don't free decrypted memory*

On Wed, Jun 19, 2024 at 04:47:50PM +0800, Li RongQing wrote:
> In CoCo VMs it is possible for the untrusted host to cause
> set_memory_decrypted() to fail such that an error is returned

Add "()" for set_memory_decrypted() and WARN_ONCE().

And put the solution into a separate paragraph:

s/ So leak/\n\nLeak/

> Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
> Signed-off-by: Li RongQing <lirongqing@baidu.com>

Otherwise, looks good:

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---
