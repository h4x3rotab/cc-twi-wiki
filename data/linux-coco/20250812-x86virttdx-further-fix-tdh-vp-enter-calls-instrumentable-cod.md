---
title: 'x86/virt/tdx: Further fix tdh_vp_enter() calls instrumentable code warning'
date: 2025-08-12
last_reply: 2025-08-12
message_count: 1
participants: ['Kai Huang']
---

## [1] Kai Huang — 2025-08-12

tdh_vp_enter() needs to be marked noinstr, which means it can't call any
non-inlined noinstr functions.  Commit e9f17038d814 ("x86/tdx: mark
tdh_vp_enter() as __flatten") tried to address a build warning caused by
tdx_tdvpr_pa() not getting inlined.  Unfortunately that commit didn't
fix the warning completely due to the inconsistent behavior of the
__flatten annotation.

There are two problems that can come up depending on the compiler and
config.  One is that tdx_tdvpr_pa() doesn't get inlined, the other is
that page_to_phys() doesn't get inlined.

The __flatten annotation makes the compiler inline all function calls
that the annotated function makes, and the aforementioned commit assumed
this is always honored, recursively.  But it turns out it's not always
true:

 - Gcc may ignore __flatten when CONFIG_CC_OPTIMIZE_FOR_SIZE=y.
 - Clang doesn't support recursive inlining for __flatten, which can
   trigger another similar warning when page_to_phys() calls pfn_valid()
   when CONFIG_DEBUG_VIRTUAL=y.

Therefore using __flatten is not the right fix.

To fix the first problem, remove the __flatten for tdh_vp_enter() and
instead annotate tdx_tdvpr_pa() with __always_inline to make sure it is
always inlined.

To fix the second problem, change tdx_tdvpr_pa() to use
PFN_PHYS(page_to_pfn()) instead of page_to_phys() so that there will be
no more function call inside tdx_tdvpr_pa()[*].

The TDVPR page is always an actual page out of page allocator, so the
additional warning around pfn_valid() check in page_to_phys() doesn't
help a lot anyway.  It's not worth complicating the code for such
warning when CONFIG_DEBUG_VIRTUAL=y.

[*] Since commit cba5d9b3e99d ("x86/mm/64: Make SPARSEMEM_VMEMMAP the
    only memory model") page_to_pfn() has been a simple macro without
    any function call.

Fixes: e9f17038d814 ("x86/tdx: mark tdh_vp_enter() as __flatten")
Cc: stable@vger.kernel.org
Signed-off-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
v3 -> v4:

 - Add "Cc: stable@vger.kernel.org".
 - Re-generate based on today's tip/master.

v2 -> v3:
 - Add Kirill's Reviewed-by.
 - Re-generate based on today's tip/x86/tdx.

v1 -> v2:
 - Add Rick's Reviewed-by.
 - Re-generate based on today's tip/master.

---
 arch/x86/virt/vmx/tdx/tdx.c | 11 ++++++++---
 1 file changed, 8 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c7a9a087ccaf..f92ceaea2726 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1502,9 +1502,14 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
-static inline u64 tdx_tdvpr_pa(struct tdx_vp *td)
+static __always_inline u64 tdx_tdvpr_pa(struct tdx_vp *td)
 {
-	return page_to_phys(td->tdvpr_page);
+	/*
+	 * Don't use page_to_phys() because tdh_vp_enter() calls this
+	 * function from 'noinstr' code, and page_to_phys() can call
+	 * uninlined functions on some compiler/configs.
+	 */
+	return PFN_PHYS(page_to_pfn(td->tdvpr_page));
 }
 
 /*
@@ -1518,7 +1523,7 @@ static void tdx_clflush_page(struct page *page)
 	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
 }
 
-noinstr __flatten u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
+noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = tdx_tdvpr_pa(td);
 

base-commit: 4b6b14d20bc04dcab6dd3ad0d5a50a0f473d1c18

---
