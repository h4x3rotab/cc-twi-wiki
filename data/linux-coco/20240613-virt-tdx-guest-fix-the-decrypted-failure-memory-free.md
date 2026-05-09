---
title: 'virt: tdx-guest: Fix the decrypted failure memory free'
date: 2024-06-13
last_reply: 2024-06-14
message_count: 5
participants: ['Li RongQing', 'Dave Hansen', 'Edgecombe, Rick P']
---

## [1] Li RongQing — 2024-06-13

In CoCo VMs it is possible for the untrusted host to cause
set_memory_encrypted() or set_memory_decrypted() to fail such that an
error is returned and the resulting memory is shared. Callers need to
take care to handle these errors to avoid returning decrypted (shared)
memory to the page allocator, which could lead to functional or security
issues.

When set_memory_decrypted() fails, the memory should be encrypted
via set_memory_encrypted(); if encrypting the memory fails, leak it

Signed-off-by: Li RongQing <lirongqing@baidu.com>
---
 drivers/virt/coco/tdx-guest/tdx-guest.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 1253bf7..63271fc 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -125,7 +125,8 @@ static void *alloc_quote_buf(void)
 		return NULL;
 
 	if (set_memory_decrypted((unsigned long)addr, count)) {
-		free_pages_exact(addr, len);
+		if (!set_memory_encrypted((unsigned long)addr, count))
+			free_pages_exact(addr, len);
 		return NULL;
 	}

---

## [2] Dave Hansen — 2024-06-13
*Subject: Re: [PATCH] virt: tdx-guest: Fix the decrypted failure memory free*

On 6/13/24 04:19, Li RongQing wrote:
> When set_memory_decrypted() fails, the memory should be encrypted
> via set_memory_encrypted(); if encrypting the memory fails, leak it

Please, always cc LKML on this stuff.

Second, Rick was looking in this area, but I'm not sure we ever applied
his patches.  The idea was to never leak memory silently in these
failures.  Doesn't this silently leak memory?

---

## [3] Edgecombe, Rick P — 2024-06-13
*Subject: Re: [PATCH] virt: tdx-guest: Fix the decrypted failure memory free*

Thanks.

On Thu, 2024-06-13 at 19:19 +0800, Li RongQing wrote:
> In CoCo VMs it is possible for the untrusted host to cause
> set_memory_encrypted() or set_memory_decrypted() to fail such that an

In the other cases the general consensus was to not optimize for this failure.
As in, don't try to re-encrypt the pages first, just give up and leak them on
the first failure. So the fix could just be to remove the free_pages_exact()
call. I think we should stick with that pattern.

>                 return NULL;
>         }

On another note, it looks like that this one popped up after we made the
previous sweep to fix the pattern. Maybe it was in-flight at the time, but since
it even popped up in TDX specific code, it makes me wonder again about how we
can keep on top of the problem.

---

## [4] Edgecombe, Rick P — 2024-06-13
*Subject: Re: [PATCH] virt: tdx-guest: Fix the decrypted failure memory free*

On Thu, 2024-06-13 at 09:07 -0700, Dave Hansen wrote:
> Second, Rick was looking in this area, but I'm not sure we ever applied
> his patches.  The idea was to never leak memory silently in these

They did get applied actually. After a fair amount of discussion the solution
was to always leak the pages, and rely on the WARN that happens in set_memory()
to make noise about it.

It looks like this instance popped up after the sweep through the code was done.
(at least in my local branch with the patches for the fixes, this code was not
merged yet)

---

## [5] Li,Rongqing — 2024-06-14
*Subject: RE: [外部邮件] Re: [PATCH] virt: tdx-guest: Fix the decrypted failure memory free*

> In the other cases the general consensus was to not optimize for this failure.
> As in, don't try to re-encrypt the pages first, just give up and leak them on the

I see, I will send v2

Thanks

-Li

---
