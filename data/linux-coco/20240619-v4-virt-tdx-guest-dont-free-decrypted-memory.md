---
title: "[v4] virt: tdx-guest: Don't free decrypted memory"
date: 2024-06-19
last_reply: 2024-12-02
message_count: 6
participants: ['Li RongQing', 'Edgecombe, Rick P', 'Dave Hansen']
---

## [1] Li RongQing — 2024-06-19

In CoCo VMs it is possible for the untrusted host to cause
set_memory_decrypted() to fail such that an error is returned
and the resulting memory is shared. Callers need to take care
to handle these errors to avoid returning decrypted (shared)
memory to the page allocator, which could lead to functional
or security issues.

Leak the decrypted memory when set_memory_decrypted() fails,
and don't need to print an error since set_memory_decrypted()
will call WARN_ONCE().

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Li RongQing <lirongqing@baidu.com>
---
 diff with v3: modify the commit log as suggested by Kirill
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

## [2] Li,Rongqing — 2024-07-04
*Subject: RE: [PATCH][v4] virt: tdx-guest: Don't free decrypted memory*

> In CoCo VMs it is possible for the untrusted host to cause
> set_memory_decrypted() to fail such that an error is returned and the resulting


 Ping

Thank

-LiRongQing

---

## [3] Li,Rongqing — 2024-11-27
*Subject: 答复: [PATCH][v4] virt: tdx-guest: Don't free decrypted memory*

> > In CoCo VMs it is possible for the untrusted host to cause
> > set_memory_decrypted() to fail such that an error is returned and the



Ping

---

## [4] Edgecombe, Rick P — 2024-11-27
*Subject: Re: [PATCH][v4] virt: tdx-guest: Don't free decrypted memory*

On Wed, 2024-06-19 at 19:18 +0800, Li RongQing wrote:
> In CoCo VMs it is possible for the untrusted host to cause
> set_memory_decrypted() to fail such that an error is returned

It needs a Fixes tag.
Fixes: f4738f56d1dc ("virt: tdx-guest: Add Quote generation support using
TSM_REPORTS")

I think it is a worthwhile fix. Without it the guest can be tricked into freeing
shared pages, or trying to execute from them and crashing.

I'm not sure how we missed this case, but from the fixes commit date it may have
been in-flight somewhere when I was doing the treewide search.

---

## [5] Dave Hansen — 2024-12-02
*Subject: Re: [PATCH][v4] virt: tdx-guest: Don't free decrypted memory*

On 11/27/24 08:48, Edgecombe, Rick P wrote:
> On Wed, 2024-06-19 at 19:18 +0800, Li RongQing wrote:
>> In CoCo VMs it is possible for the untrusted host to cause

Does this need a "Fixes" and cc:stable@?

---

## [6] Edgecombe, Rick P — 2024-12-02
*Subject: Re: [PATCH][v4] virt: tdx-guest: Don't free decrypted memory*

On Mon, 2024-12-02 at 10:05 -0800, Dave Hansen wrote:
> On 11/27/24 08:48, Edgecombe, Rick P wrote:
> > On Wed, 2024-06-19 at 19:18 +0800, Li RongQing wrote:

Oh yea, probably worth a cc:stable too.

---
