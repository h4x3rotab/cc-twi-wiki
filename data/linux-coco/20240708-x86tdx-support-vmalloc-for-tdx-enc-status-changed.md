---
title: 'x86/tdx: Support vmalloc() for tdx_enc_status_changed()'
date: 2024-07-08
last_reply: 2024-07-10
message_count: 11
participants: ['Dexuan Cui', 'Borislav Petkov', 'Jiri Slaby']
---

## [1] Dexuan Cui — 2024-07-08

When a TDX guest runs on Hyper-V, the hv_netvsc driver's netvsc_init_buf()
allocates buffers using vzalloc(), and needs to share the buffers with the
host OS by calling set_memory_decrypted(), which is not working for
vmalloc() yet. Add the support by handling the pages one by one.

Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Dexuan Cui <decui@microsoft.com>
Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Michael Kelley <mikelley@microsoft.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Cc: stable@vger.kernel.org
---

Hi Boris, Kirill and all,
This patch was posted on May 20, 2024:
Link: https://lore.kernel.org/all/20240521021238.1803-1-decui%40microsoft.com

The patch caused an issue to Kirill's kexec TDX patchset, so Kirill fixed it:
Link: https://lore.kernel.org/all/uewczuxr5foiwe6wklhcgzi6ejfwgacxxoa67xadey62s46yro@quwpodezpxh5/
Kirill agreed that I should repost the patch with his fix combined, hence I'm
posting this new version, which is based on tip's master today (at the moment,
it's commit aa9d8caba6e4 ("Merge timers/core into tip/master")).

I suppose the patch would go in the branch tip/master or x86/tdx.

Thanks,
Dexuan

 arch/x86/coco/tdx/tdx.c | 43 ++++++++++++++++++++++++++++++++++-------
 1 file changed, 36 insertions(+), 7 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac25531..8f471260924f7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -782,6 +783,19 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 	return false;
 }
 
+static bool tdx_enc_status_changed_phys(phys_addr_t start, phys_addr_t end,
+					bool enc)
+{
+	if (!tdx_map_gpa(start, end, enc))
+		return false;
+
+	/* shared->private conversion requires memory to be accepted before use */
+	if (enc)
+		return tdx_accept_memory(start, end);
+
+	return true;
+}
+
 /*
  * Inform the VMM of the guest's intent for this physical page: shared with
  * the VMM or private to the guest.  The VMM is expected to change its mapping
@@ -789,15 +803,30 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
  */
 static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 {
-	phys_addr_t start = __pa(vaddr);
-	phys_addr_t end   = __pa(vaddr + numpages * PAGE_SIZE);
+	unsigned long start = vaddr;
+	unsigned long end = start + numpages * PAGE_SIZE;
+	unsigned long step = end - start;
+	unsigned long addr;
+
+	/* Step through page-by-page for vmalloc() mappings */
+	if (is_vmalloc_addr((void *)vaddr))
+		step = PAGE_SIZE;
+
+	for (addr = start; addr < end; addr += step) {
+		phys_addr_t start_pa;
+		phys_addr_t end_pa;
+
+		/* The check fails on vmalloc() mappings */
+		if (virt_addr_valid(addr))
+			start_pa = __pa(addr);
+		else
+			start_pa = slow_virt_to_phys((void *)addr);
 
-	if (!tdx_map_gpa(start, end, enc))
-		return false;
+		end_pa = start_pa + step;
 
-	/* shared->private conversion requires memory to be accepted before use */
-	if (enc)
-		return tdx_accept_memory(start, end);
+		if (!tdx_enc_status_changed_phys(start_pa, end_pa, enc))
+			return false;
+	}
 
 	return true;
 }

---

## [2] Borislav Petkov — 2024-07-08
*Subject: Re: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

On Mon, Jul 08, 2024 at 06:39:45PM +0000, Dexuan Cui wrote:
> When a TDX guest runs on Hyper-V, the hv_netvsc driver's netvsc_init_buf()
> allocates buffers using vzalloc(), and needs to share the buffers with the

"Add support..." and the patch is cc:stable?

This looks like it is fixing something and considering how you're rushing
this, I'd let this cook for a whole round and queue it after 6.11-rc1. So that
it gets tested properly.

> Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

When were you able to collect all those tags on a newly submitted patch?

Do you even know what the meaning of those tags is or you just slap them
willy-nilly, just for fun?

> Cc: stable@vger.kernel.org

Why?

Fixes: what?

From reading this, it seems to me you need to brush up on

https://kernel.org/doc/html/latest/process/submitting-patches.html

while waiting.

Thx.

---

## [3] Dexuan Cui — 2024-07-08
*Subject: RE: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

> From: Borislav Petkov <bp@alien8.de>
> [...]

I meant to use "Cc: stable@vger.kernel.org # 6.6+". 
Sorry for missing the "# 6.6+". 
 
> This looks like it is fixing something and considering how you're rushing
> this, I'd let this cook for a whole round and queue it after 6.11-rc1. So that

x86/tdx: Fix set_memory_decrypted() for vmalloc() buffers

When a TD mode Linux TDX VM runs on Hyper-V, the Linux hv_netvsc driver
needs to share a vmalloc()'d  buffer with the host OS: see
netvsc_init_buf() -> vmbus_establish_gpadl() -> ... ->
__vmbus_establish_gpadl() -> set_memory_decrypted().

Currently set_memory_decrypted() doesn't work for a vmalloc()'d  buffer
because tdx_enc_status_changed() uses __pa(vaddr), i.e., it assumes that
the 'vaddr' can't be from vmalloc(), and consequently hv_netvsc fails
to load.

Fix this by handling the pages one by one.

hv_netvsc is the first user of vmalloc() + set_memory_decrypted(), which
is why nobody noticed this until now.

v6.6 is a longterm kernel, which is used by some distros, so I hope
this patch can be in v6.6.y and newer, so it won't be carried out of tree.

I think the patch (without Kirill's kexec fix)  has been well tested, e.g.,
it has been in Ubuntu's linux-azure kernel for about 2 years. Kirill's 
kexec fix works in my testing and it looks safe to me. 

I hope this can be in 6.11-rc1 if you see no high risks. 
It's also fine to me if you decide to queue the patch after 6.11-rc1.

> > Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> > Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
https://lwn.net/ml/linux-kernel/20230412151937.pxfyralfichwzyv6@box/

> > Signed-off-by: Dexuan Cui <decui@microsoft.com>
> > Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git/commit/?id=e1b8ac3aae589bb57a2c2e49fa76235c687c4d23

> > Reviewed-by: Michael Kelley <mikelley@microsoft.com>
https://lwn.net/ml/linux-kernel/BYAPR21MB16885F59B6F5594F31AE957AD79A9@BYAPR21MB1688.namprd21.prod.outlook.com/

> > Reviewed-by: Kuppuswamy Sathyanarayanan
> <sathyanarayanan.kuppuswamy@linux.intel.com>
https://lwn.net/ml/linux-kernel/d20baf1e-a736-667f-2082-0c0539013f2b@linux.intel.com/

> > Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
https://lwn.net/ml/linux-kernel/e8b1b0b5f32115c0ef8f1aeb0b805c4d9a953b31.camel@intel.com/

> > Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
https://lwn.net/ml/linux-kernel/4732ef96-9a47-3513-4494-48e4684d65cd@intel.com/

> > Acked-by: Kai Huang <kai.huang@intel.com>
https://lwn.net/ml/linux-kernel/6b6e7f943b7e28fa6ae6c77e1002ac61c41c1ee2.camel@intel.com/

> When were you able to collect all those tags on a newly submitted patch?

This is not really a newly submitted patch :-)
Please refer to the links above.

v9 was posted here (Jun 2023): 
https://lwn.net/ml/linux-kernel/20230621191317.4129-3-decui@microsoft.com/

v10 was posted here (Aug 2023):
https://lwn.net/ml/linux-kernel/20230811214826.9609-3-decui%40microsoft.com/

The last submission was May 2024:
https://lwn.net/ml/linux-kernel/20240521021238.1803-1-decui@microsoft.com/
(Sorry, I should have made it clear that this is actually v11)

> Do you even know what the meaning of those tags is or you just slap them
> willy-nilly, just for fun?

The original patch was submitted in Nov 2022:
https://lwn.net/ml/linux-kernel/20221121195151.21812-4-decui@microsoft.com/

I added Kirill's Co-developed-by in v4 (Apr 2023)
https://lwn.net/ml/linux-kernel/20230412151937.pxfyralfichwzyv6@box/
and added Kirill's Signed-off-by in v5, and added other people's Reviewed-by
and Acked-by over time. There are only minor changes since v4, so I think
it's appropriate to keep all the tags in the final commit.

> > Cc: stable@vger.kernel.org
> 

Please refer to my reply above. 

This is not to fix a buggy commit. The described scenario never worked before,
so I suppose a "Fixes:" tag is not needed.

> From reading this, it seems to me you need to brush up on 
> https://kernel.org/doc/html/latest/process/submitting-patches.html
Thanks for the link! I read it and did learn something.

> while waiting.
> 

I hope I have provided a satisfactory reply above.

How do you like the v12 below? It's also attached.
If this looks good to you, I can post it today or tomorrow.

Thanks,
Dexuan

From 132f656fdbf3b4f00752140aac10f3674b598b5a Mon Sep 17 00:00:00 2001
From: Dexuan Cui <decui@microsoft.com>
Date: Mon, 20 May 2024 19:12:38 -0700
Subject: [PATCH v12] x86/tdx: Fix set_memory_decrypted() for vmalloc() buffers

When a TD mode Linux TDX VM runs on Hyper-V, the Linux hv_netvsc driver
needs to share a vmalloc()'d  buffer with the host OS: see
netvsc_init_buf() -> vmbus_establish_gpadl() -> ... ->
__vmbus_establish_gpadl() -> set_memory_decrypted().

Currently set_memory_decrypted() doesn't work for a vmalloc()'d  buffer
because tdx_enc_status_changed() uses __pa(vaddr), i.e., it assumes that
the 'vaddr' can't be from vmalloc(), and consequently hv_netvsc fails
to load.

Fix this by handling the pages one by one.

hv_netvsc is the first user of vmalloc() + set_memory_decrypted(), which
is why nobody noticed this until now.

Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Dexuan Cui <decui@microsoft.com>
Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Michael Kelley <mikelley@microsoft.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Cc: stable@vger.kernel.org # 6.6+
---
 arch/x86/coco/tdx/tdx.c | 43 ++++++++++++++++++++++++++++++++++-------
 1 file changed, 36 insertions(+), 7 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac25531..8f471260924f7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -782,6 +783,19 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 	return false;
 }
 
+static bool tdx_enc_status_changed_phys(phys_addr_t start, phys_addr_t end,
+					bool enc)
+{
+	if (!tdx_map_gpa(start, end, enc))
+		return false;
+
+	/* shared->private conversion requires memory to be accepted before use */
+	if (enc)
+		return tdx_accept_memory(start, end);
+
+	return true;
+}
+
 /*
  * Inform the VMM of the guest's intent for this physical page: shared with
  * the VMM or private to the guest.  The VMM is expected to change its mapping
@@ -789,15 +803,30 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
  */
 static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 {
-	phys_addr_t start = __pa(vaddr);
-	phys_addr_t end   = __pa(vaddr + numpages * PAGE_SIZE);
+	unsigned long start = vaddr;
+	unsigned long end = start + numpages * PAGE_SIZE;
+	unsigned long step = end - start;
+	unsigned long addr;
+
+	/* Step through page-by-page for vmalloc() mappings */
+	if (is_vmalloc_addr((void *)vaddr))
+		step = PAGE_SIZE;
+
+	for (addr = start; addr < end; addr += step) {
+		phys_addr_t start_pa;
+		phys_addr_t end_pa;
+
+		/* The check fails on vmalloc() mappings */
+		if (virt_addr_valid(addr))
+			start_pa = __pa(addr);
+		else
+			start_pa = slow_virt_to_phys((void *)addr);
 
-	if (!tdx_map_gpa(start, end, enc))
-		return false;
+		end_pa = start_pa + step;
 
-	/* shared->private conversion requires memory to be accepted before use */
-	if (enc)
-		return tdx_accept_memory(start, end);
+		if (!tdx_enc_status_changed_phys(start_pa, end_pa, enc))
+			return false;
+	}
 
 	return true;
 }

---

## [4] Jiri Slaby — 2024-07-09
*Subject: Re: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

On 08. 07. 24, 23:45, Dexuan Cui wrote:
>> From: Borislav Petkov <bp@alien8.de>
>>> Cc: stable@vger.kernel.org

If you cc stable, fixes *is* actually needed. So again, why to cc stable 
when this is a feature? I suppose you will receive a Greg-bot reply 
anyway ;).

>>  From reading this, it seems to me you need to brush up on
>> https://kernel.org/doc/html/latest/process/submitting-patches.html
...> I hope I have provided a satisfactory reply above.
> 
> How do you like the v12 below? It's also attached.

Then you need to enumerate what changed in v1..v12. In every single 
revision. Do it under the "---" line below. And add v12 to the subject 
as you did below (but not above).

>  From 132f656fdbf3b4f00752140aac10f3674b598b5a Mon Sep 17 00:00:00 2001
> From: Dexuan Cui <decui@microsoft.com>
...
> 
> hv_netvsc is the first user of vmalloc() + set_memory_decrypted(), which

The revision log belongs here. I believe you had to meet that 
requirement in the submittingpatches document.

And to avoid future confusion, I would list the links to received 
"Signed-off-by"/"Reviewed-by"s here too. The links you listed earlier.

>   arch/x86/coco/tdx/tdx.c | 43 ++++++++++++++++++++++++++++++++++-------
>   1 file changed, 36 insertions(+), 7 deletions(-)

regards,

---

## [5] Dexuan Cui — 2024-07-09
*Subject: RE: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

> From: Jiri Slaby <jirislaby@kernel.org>
>  [...]
Ok, I can add a tag to next version, i.e., v12:
Fixes: 68f2f2bc163d ("Drivers: hv: vmbus: Support fully enlightened TDX guests")

68f2f2bc163d is already in v6.6.
A v6.6 kernel works for a Linux TD-Mode TDX VM on Hyper-V, if the VM
doesn't have a virtual NIC device; if the VM has a vNIC, the hv_netvsc driver
fails to load and the VM gets stuck in the network init script. This patch fixes
the issue.

> when this is a feature? I suppose you will receive a Greg-bot reply
> anyway ;).
As explained above, my understanding is that this is more of a bug fix rather
than a feature, though the described NIC driver issue is specific to Hyper-V.
In the future, there might be new users of vmalloc() + set_memory_decrypted().

> > How do you like the v12 below? It's also attached.
> > If this looks good to you, I can post it today or tomorrow.
Ok, I'll post v12 tomorrow with changes enumerated from v1..v12.
 
> >  From 132f656fdbf3b4f00752140aac10f3674b598b5a Mon Sep 17
> 00:00:00 2001
Ok, will do.

> And to avoid future confusion, I would list the links to received
> "Signed-off-by"/"Reviewed-by"s here too. The links you listed earlier.
Ok, will do.

> regards,
> --

Thanks for your comments!

---

## [6] Borislav Petkov — 2024-07-09
*Subject: Re: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

On Mon, Jul 08, 2024 at 09:45:24PM +0000, Dexuan Cui wrote:
> x86/tdx: Fix set_memory_decrypted() for vmalloc() buffers
> 

So this is a corner-case thing. I guess CC:stable is ok, we have packported
similar "fixes" in the past.

> I think the patch (without Kirill's kexec fix)  has been well tested, e.g.,
> it has been in Ubuntu's linux-azure kernel for about 2 years. Kirill's 

You seem to think that a patch which has been tested in some out-of-tree
kernel,

- gets modified
- gets applied to the upstream kernel
- it *breaks* a use case,

and then it can still be considered tested.

Are you seriously claiming that?!

> I hope this can be in 6.11-rc1 if you see no high risks. 
> It's also fine to me if you decide to queue the patch after 6.11-rc1.

Yes, it will be after -rc1 because what you consider "tested" and what I do
consider "tested" can just as well be from two different planets.

> > > Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> > > Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

Since you'd go the length to quote the mail messages which gave you the tags
but you will not read what I point you to, lemme read it for you:

"Both Tested-by and Reviewed-by tags, once received on mailing list from
tester or reviewer, should be added by author to the applicable patches when
sending next versions.  However if the patch has changed substantially in
following version, these tags might not be applicable anymore and thus should
be removed.  Usually removal of someone's Tested-by or Reviewed-by tags should
be mentioned in the patch changelog (after the '---' separator)."

From Documentation/process/submitting-patches.rst

Again, if you want to keep sending patches to the kernel, I'd strongly urge
you to read that document!

> This is not really a newly submitted patch :-)

If you still think that and you want to keep your tags, all I can give you is
a big fat NAK until you read and understand how the process works.

Your decision.

---

## [7] Dexuan Cui — 2024-07-10
*Subject: RE: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

> From: Borislav Petkov <bp@alien8.de>
> Sent: Tuesday, July 9, 2024 4:07 AM

Thanks for sharing your thoughts! Then I'll use these in next version (v12):
Fixes: 68f2f2bc163d ("Drivers: hv: vmbus: Support fully enlightened TDX guests")
Cc: stable@vger.kernel.org # 6.6+
 
> > I think the patch (without Kirill's kexec fix)  has been well tested, e.g.,
> > it has been in Ubuntu's linux-azure kernel for about 2 years. Kirill's

I should have made it clear that I think Kirill helped fix and test this as well.
Besides Kirill's testing and my testing, I totally agree that more testing is
needed. I appreciate it very much if someone can help identify more
potential issues in the patch. I didn't mean to rush the patch.
 
> > I hope this can be in 6.11-rc1 if you see no high risks.
> > It's also fine to me if you decide to queue the patch after 6.11-rc1.

It's ok to me it will be after -rc1. I just thought the patch would get more
testing if it could be on some branch (e.g., x86/tdx ?) in the tip.git tree, e.g.,
if the patch is on some tip.git branch, I suppose the linux-next tree would
merge the patch so the patch will get more testing automatically. 

> Since you'd go the length to quote the mail messages which gave you the
> tags  but you will not read what I point you to, lemme read it for you:

I guess we have different options on whether "the patch has changed
substantially". My impression is that it hasn't. Please refer to the
changelogs of v9, v10 and v11:
https://lwn.net/ml/linux-kernel/20230621191317.4129-3-decui@microsoft.com/
https://lwn.net/ml/linux-kernel/20230811214826.9609-3-decui%40microsoft.com/
https://lwn.net/ml/linux-kernel/20240521021238.1803-1-decui@microsoft.com/
(v11 is basically a repost of v10)
I started to add people's tags since v4 and my impression is that since then
it's rebasing and minor changes. Anyway, I'll go through the history thoroughly
and document the changes in detail. I'll remove all the people's tags and
mention the removal in the changelog in next version (i.e., v12), and request
the people to review/ack again, and ask for Kirill's explicit permission for adding
the Co-developed-by and Signed-off-by.

> From Documentation/process/submitting-patches.rst
> 
Ok. I promise I'll read the document again, word by word.
 
> > This is not really a newly submitted patch :-)
> 

Stay tuned, please.  I'll try my best to make a good v12, which will have a
long changelog after the '---'.

Thanks,
Dexuan

---

## [8] Dexuan Cui — 2024-07-10
*Subject: RE: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

> I guess we have different options on whether "the patch has changed
Sorry for the typo -- I meant "opinions", not "options"...

---

## [9] Borislav Petkov — 2024-07-10
*Subject: Re: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

On Wed, Jul 10, 2024 at 07:48:14AM +0000, Dexuan Cui wrote:
> It's ok to me it will be after -rc1. I just thought the patch would get more
> testing if it could be on some branch (e.g., x86/tdx ?) in the tip.git tree, e.g.,

Yes, it will get more testing automatically but the period is important: if
I rush it now, it goes to Linus next week and then any fallout it causes needs
to be dealt with in mainline.

If I queue it after -rc1, it'll be only in tip and linux-next for an
additional 7 week cycle and I can always whack it if it breaks something. If
it doesn't, I can send it mainline in the 6.12 merge window.

But we won't have to revert it mainline.

See the difference?

> I guess we have different options on whether "the patch has changed
> substantially". My impression is that it hasn't.

If you're calling the difference between what I reverted and what you're
sending now unsubstantial:

--- /tmp/old	2024-07-10 10:03:20.016629439 +0200
+++ /tmp/new	2024-07-10 10:02:23.696872729 +0200
 diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
-index c1cb90369915..abf3cd591afd 100644
+index 078e2bac25531..8f471260924f7 100644
 --- a/arch/x86/coco/tdx/tdx.c
 +++ b/arch/x86/coco/tdx/tdx.c
-@@ -7,6 +7,7 @@
- #include <linux/cpufeature.h>
+@@ -8,6 +8,7 @@
  #include <linux/export.h>
  #include <linux/io.h>
+ #include <linux/kexec.h>
 +#include <linux/mm.h>
  #include <asm/coco.h>
  #include <asm/tdx.h>
  #include <asm/vmx.h>
-@@ -778,6 +779,19 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
+@@ -782,6 +783,19 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
  	return false;
  }
  
@@ -53,7 +86,7 @@ index c1cb90369915..abf3cd591afd 100644
  /*
   * Inform the VMM of the guest's intent for this physical page: shared with
   * the VMM or private to the guest.  The VMM is expected to change its mapping
-@@ -785,15 +799,22 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
+@@ -789,15 +803,30 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
   */
  static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
  {
@@ -63,23 +96,34 @@ index c1cb90369915..abf3cd591afd 100644
 +	unsigned long end = start + numpages * PAGE_SIZE;
 +	unsigned long step = end - start;
 +	unsigned long addr;
- 
--	if (!tdx_map_gpa(start, end, enc))
--		return false;
++
 +	/* Step through page-by-page for vmalloc() mappings */
 +	if (is_vmalloc_addr((void *)vaddr))
 +		step = PAGE_SIZE;
++
++	for (addr = start; addr < end; addr += step) {
++		phys_addr_t start_pa;
++		phys_addr_t end_pa;
++
++		/* The check fails on vmalloc() mappings */
++		if (virt_addr_valid(addr))
++			start_pa = __pa(addr);
++		else
++			start_pa = slow_virt_to_phys((void *)addr);
+ 
+-	if (!tdx_map_gpa(start, end, enc))
+-		return false;
++		end_pa = start_pa + step;
  
 -	/* shared->private conversion requires memory to be accepted before use */
 -	if (enc)
 -		return tdx_accept_memory(start, end);
-+	for (addr = start; addr < end; addr += step) {
-+		phys_addr_t start_pa = slow_virt_to_phys((void *)addr);
-+		phys_addr_t end_pa   = start_pa + step;
-+
 +		if (!tdx_enc_status_changed_phys(start_pa, end_pa, enc))
 +			return false;
 +	}
  
  	return true;
  }

especially for a patch which is already known to break things and where we're
especially careful, then yes, we strongly disagree here.

So yes, it will definitely not go in now.

> I started to add people's tags since v4 and my impression is that since then
> it's rebasing and minor changes.

When version N introduces changes like above in what is already non-trivial
code, you drop all tags. And if people want to review it again, then they
should give you those R-by tags.

Also, think about it: your patch broke a use case. How much are those R-by
tags worth if the patch is broken? And why do you want to hold on to them so
badly?

If a patch needs to be reverted because it breaks a use case, all reviewed and
acked tags should simply be removed too. It is that simple.

---

## [10] Dexuan Cui — 2024-07-10
*Subject: RE: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

> From: Borislav Petkov <bp@alien8.de>
> [...]

Got it. Thanks for the explanation!

> If you're calling the difference between what I reverted and what you're
> sending now unsubstantial:

I didn't expect that 'diff' could generate so many lines of changes :-)

> especially for a patch which is already known to break things and where
> we're  especially careful, then yes, we strongly disagree here.

Understood.
 
> When version N introduces changes like above in what is already non-
> trivial code, you drop all tags. And if people want to review it again,

Got it. Will reflect all the comments into the next version.

---

## [11] Borislav Petkov — 2024-07-10
*Subject: Re: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

On Wed, Jul 10, 2024 at 09:20:46AM +0000, Dexuan Cui wrote:
> I didn't expect that 'diff' could generate so many lines of changes :-)

It is not about the number of changed lines - it is about *what* gets changed.

A single character change can invalidate the tags of a patch and a huge
diffstat solely cleaning up whitespace will not, even though we prefer if
those get done in a separate patch to ease review.

I'm sure you can think of examples.

---
