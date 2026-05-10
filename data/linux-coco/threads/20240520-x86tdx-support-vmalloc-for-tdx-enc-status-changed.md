---
title: 'x86/tdx: Support vmalloc() for tdx_enc_status_changed()'
date: 2024-05-20
last_reply: 2024-06-28
message_count: 4
participants: ['Dexuan Cui', 'Kirill A. Shutemov']
---

## [1] Dexuan Cui — 2024-05-20

When a TDX guest runs on Hyper-V, the hv_netvsc driver's netvsc_init_buf()
allocates buffers using vzalloc(), and needs to share the buffers with the
host OS by calling set_memory_decrypted(), which is not working for
vmalloc() yet. Add the support by handling the pages one by one.

Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Michael Kelley <mikelley@microsoft.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Cc: stable@vger.kernel.org # 6.6+
Signed-off-by: Dexuan Cui <decui@microsoft.com>
---

This is basically a repost of the second patch of the 2023 patchset:
https://lwn.net/ml/linux-kernel/20230811214826.9609-3-decui@microsoft.com/

The first patch of the patchset got merged into mainline, but unluckily the
second patch didn't, and I kind of lost track of it. Sorry.

Changes since the previous patchset (please refer to the link above):
  Added Rick's and Dave's Reviewed-by.
  Added Kai's Acked-by.
  Removeda the test "if (offset_in_page(start) != 0)" since we know the
  'start' is page-aligned: see __set_memory_enc_pgtable().

Please review. Thanks!
Dexuan

 arch/x86/coco/tdx/tdx.c | 35 ++++++++++++++++++++++++++++-------
 1 file changed, 28 insertions(+), 7 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c1cb90369915b..abf3cd591afd3 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -7,6 +7,7 @@
 #include <linux/cpufeature.h>
 #include <linux/export.h>
 #include <linux/io.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -778,6 +779,19 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
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
@@ -785,15 +799,22 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
  */
 static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 {
-	phys_addr_t start = __pa(vaddr);
-	phys_addr_t end   = __pa(vaddr + numpages * PAGE_SIZE);
+	unsigned long start = vaddr;
+	unsigned long end = start + numpages * PAGE_SIZE;
+	unsigned long step = end - start;
+	unsigned long addr;
 
-	if (!tdx_map_gpa(start, end, enc))
-		return false;
+	/* Step through page-by-page for vmalloc() mappings */
+	if (is_vmalloc_addr((void *)vaddr))
+		step = PAGE_SIZE;
 
-	/* shared->private conversion requires memory to be accepted before use */
-	if (enc)
-		return tdx_accept_memory(start, end);
+	for (addr = start; addr < end; addr += step) {
+		phys_addr_t start_pa = slow_virt_to_phys((void *)addr);
+		phys_addr_t end_pa   = start_pa + step;
+
+		if (!tdx_enc_status_changed_phys(start_pa, end_pa, enc))
+			return false;
+	}
 
 	return true;
 }

---

## [2] Dexuan Cui — 2024-06-19
*Subject: RE: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

> From: Dexuan Cui <decui@microsoft.com>
> Sent: Monday, May 20, 2024 7:13 PM

The patch still applies cleanly to 6.10-rc4.

A gentle ping.

---

## [3] Kirill A. Shutemov — 2024-06-28
*Subject: Re: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

On Mon, May 20, 2024 at 07:12:38PM -0700, Dexuan Cui wrote:
> @@ -785,15 +799,22 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
>   */

This patch collied with kexec changes. tdx_kexec_finish() calls
tdx_enc_status_changed() after clearing pte, so slow_virt_to_phys()
crashes on in.

Daxuan, could you check if the fixup below works for you on vmalloc
addresses?

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index ef8ec2425998..5e455c883bcc 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -813,8 +813,15 @@ static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 		step = PAGE_SIZE;
 
 	for (addr = start; addr < end; addr += step) {
-		phys_addr_t start_pa = slow_virt_to_phys((void *)addr);
-		phys_addr_t end_pa   = start_pa + step;
+		phys_addr_t start_pa;
+		phys_addr_t end_pa;
+
+		if (virt_addr_valid(addr))
+			start_pa = __pa(addr);
+		else
+			start_pa = slow_virt_to_phys((void *)addr);
+
+		end_pa = start_pa + step;
 
 		if (!tdx_enc_status_changed_phys(start_pa, end_pa, enc))
 			return false;

---

## [4] Dexuan Cui — 2024-06-28
*Subject: RE: [PATCH] x86/tdx: Support vmalloc() for tdx_enc_status_changed()*

> From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> Sent: Friday, June 28, 2024 3:05 AM

Hi Kirill, your fixup works for me.

BTW, I just realized that virt_addr_valid() returns false for a vmalloc'd address.

Thanks,
Dexuan

---
