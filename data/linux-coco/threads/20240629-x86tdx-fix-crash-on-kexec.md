---
title: 'x86/tdx: Fix crash on kexec'
date: 2024-06-29
last_reply: 2024-07-08
message_count: 13
participants: ['Kirill A. Shutemov', 'Borislav Petkov', 'Dexuan Cui']
---

## [1] Kirill A. Shutemov — 2024-06-29

The function tdx_enc_status_changed() was modified to handle vmalloc()
mappings. It now utilizes slow_virt_to_phys() to determine the physical
address of the page by walking page tables and looking for the physical
address in the page table entry.

However, this adjustment conflicted with the enabling of kexec. The
function tdx_kexec_finish() clears the page table entry before calling
tdx_enc_status_changed(), causing a BUG_ON() error in
slow_virt_to_phys().

To address this issue, tdx_enc_status_change() should use __pa() to
obtain physical addresses whenever possible. The virt_addr_valid() check
will handle such cases, while any other scenarios, including vmalloc()
mappings, will resort to slow_virt_to_phys().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Fixes: e1b8ac3aae58 ("x86/tdx: Support vmalloc() for tdx_enc_status_changed()")
---
 arch/x86/coco/tdx/tdx.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index ef8ec2425998..8f471260924f 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -813,8 +813,16 @@ static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 		step = PAGE_SIZE;
 
 	for (addr = start; addr < end; addr += step) {
-		phys_addr_t start_pa = slow_virt_to_phys((void *)addr);
-		phys_addr_t end_pa   = start_pa + step;
+		phys_addr_t start_pa;
+		phys_addr_t end_pa;
+
+		/* The check fails on vmalloc() mappings */
+		if (virt_addr_valid(addr))
+			start_pa = __pa(addr);
+		else
+			start_pa = slow_virt_to_phys((void *)addr);
+
+		end_pa = start_pa + step;
 
 		if (!tdx_enc_status_changed_phys(start_pa, end_pa, enc))
 			return false;

---

## [2] Borislav Petkov — 2024-06-29
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Sat, Jun 29, 2024 at 04:06:20PM +0300, Kirill A. Shutemov wrote:
> The function tdx_enc_status_changed() was modified to handle vmalloc()
> mappings. It now utilizes slow_virt_to_phys() to determine the physical

I'm going to zap this one from x86/urgent and give you guys ample time to test
thus stuff better and longer.

Also, what is this e1b8ac3aae58 fixing and why is it urgent?

AFAICT, it can go through the normal merge window...

---

## [3] Kirill A. Shutemov — 2024-06-29
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Sat, Jun 29, 2024 at 03:59:33PM +0200, Borislav Petkov wrote:
> On Sat, Jun 29, 2024 at 04:06:20PM +0300, Kirill A. Shutemov wrote:
> > The function tdx_enc_status_changed() was modified to handle vmalloc()

Daxuan, how urgent is this fix for you?

---

## [4] Dexuan Cui — 2024-06-29
*Subject: RE: [PATCH] x86/tdx: Fix crash on kexec*

> From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> Sent: Saturday, June 29, 2024 7:04 AM

Hi Kirill, Boris,
IMO e1b8ac3aae58  is not urgent and can go through the normal merge window.
It would be great to add e1b8ac3aae58 to the branch x86/tdx.

Thanks,
Dexuan

---

## [5] Borislav Petkov — 2024-06-29
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Sat, Jun 29, 2024 at 07:27:57PM +0000, Dexuan Cui wrote:
> It would be great to add e1b8ac3aae58 to the branch x86/tdx.

Sure we will, once it is properly tested. This very thread says otherwise.

---

## [6] Dexuan Cui — 2024-07-03
*Subject: RE: [PATCH] x86/tdx: Fix crash on kexec*

> -----Original Message-----
> From: Borislav Petkov <bp@alien8.de>

Hi Kirill, Dave,
Do you think if it's a good idea if I post a new patch that combines
    e1b8ac3aae58 ("x86/tdx: Support vmalloc() for tdx_enc_status_changed()")
and
    your patch "[PATCH] x86/tdx: Fix crash on kexec"?
 
Or, maybe Dave can help combine the two patches into one?

Just wanted to make sure e1b8ac3aae58 won't get lost.

Thanks,
Dexuan

---

## [7] Kirill A. Shutemov — 2024-07-04
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Wed, Jul 03, 2024 at 07:16:47PM +0000, Dexuan Cui wrote:
> > -----Original Message-----
> > From: Borislav Petkov <bp@alien8.de>

Yeah, IIUC, that's what Borislav wanted. After proper testing.

---

## [8] Dexuan Cui — 2024-07-04
*Subject: RE: [PATCH] x86/tdx: Fix crash on kexec*

> From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> > [...]

Hi Kirill,  
I tested the 2 patches for a Linux VM on Hyper-V and all worked fine.

When you finish testing, please let me know so that I can post
a combined patch; alternatively, it would be better if you can help post
a combined patch.

Thanks,
Dexuan

---

## [9] Kirill A. Shutemov — 2024-07-08
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Thu, Jul 04, 2024 at 02:48:49PM +0000, Dexuan Cui wrote:
> > From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> > > [...]

Go ahead, post the new version.

Borislav, could you drop the original patch from tip tree?

---

## [10] Borislav Petkov — 2024-07-08
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Mon, Jul 08, 2024 at 03:34:34PM +0300, Kirill A. Shutemov wrote:
> Borislav, could you drop the original patch from tip tree?

Long gone already.

---

## [11] Kirill A. Shutemov — 2024-07-08
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Mon, Jul 08, 2024 at 03:32:42PM +0200, Borislav Petkov wrote:
> On Mon, Jul 08, 2024 at 03:34:34PM +0300, Kirill A. Shutemov wrote:
> > Borislav, could you drop the original patch from tip tree?

Hm. I still see it in tip/x86/cc branch which is merged in tip/master.

---

## [12] Borislav Petkov — 2024-07-08
*Subject: Re: [PATCH] x86/tdx: Fix crash on kexec*

On Mon, Jul 08, 2024 at 04:51:12PM +0300, Kirill A. Shutemov wrote:
> On Mon, Jul 08, 2024 at 03:32:42PM +0200, Borislav Petkov wrote:
> > On Mon, Jul 08, 2024 at 03:34:34PM +0300, Kirill A. Shutemov wrote:

Yeah, it should be gone now.

Thx.

---

## [13] Dexuan Cui — 2024-07-08
*Subject: RE: [PATCH] x86/tdx: Fix crash on kexec*

> From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> Sent: Monday, July 8, 2024 5:35 AM

I just posted the new version.

---
