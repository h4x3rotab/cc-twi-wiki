---
title: 'TDX: Enable Dynamic PAMT'
date: 2025-11-20
last_reply: 2026-01-29
message_count: 106
participants: ['Rick Edgecombe', 'Binbin Wu', 'Sagi Shahar', 'Vishal Annapurve', 'Huang, Kai', 'Nikolay Borisov', 'Kiryl Shutsemau', 'Dave Hansen', 'Yan Zhao', 'Xu Yilun', 'Sean Christopherson']
---

## [1] Rick Edgecombe — 2025-11-20

Hi, 

This is 4th revision of Dynamic PAMT, which is a new feature that reduces 
the memory use of TDX. For background information, see the v3 
coverletter[0]. V4 mostly consists of incorporating the feedback from v3. 
Notably what it *doesn’t* change is the solution for pre-allocating DPAMT
backing pages. (more info below in “Changes”)

I think this series isn’t quite ready to ask for merging just yet. I’d 
appreciate another round of review especially looking for any issues in the
refcount allocation/mapping and the pamt get/put lock-refcount dance. And
hopefully collect some RBs.

Sean/Paolo, we have mostly banished this all to TDX code except for “KVM: 
TDX: Add x86 ops for external spt cache” patch. That and “x86/virt/tdx: 
Add helpers to allow for pre-allocating pages” are probably the remaining 
possibly controversial parts of your domain. If you only have a short time 
to spend at this point, I’d point you at those two patches.

Since most of the changes are in arch/x86, I’d think this feature could be
a candidate for eventually merging through tip with Sean or Paolo’s ack.
But it is currently based on kvm-x86/next in order to build on top of the 
post-populate cleanup series. Next time I’ll probably target tip if people 
think that is a good way forward.

Changes
=======
There were two good suggestions around the pre-allocated pages solution
last time, but neither ended up working out:

1. Dave suggested to use mempool_t instead of the linked list based 
structure, in order to not re-invent the wheel. This turned out to not 
quite fit. The problems were that there wasn’t really a “topup” mechanism, 
or an atomic fallback (which matches the kvm cache behavior). This results 
in very similar code being built around mempool that was built around the 
linked list. It was an overall harder to follow solution for not much code 
savings. 

I strongly considered going back to Kiryl’s original solution which passed 
a callback function pointer for allocating DPAMT pages, and an opaque
void * that the callback could use to find the kvm_mmu_memory_cache. I
thought that readability issues of passing the opaque void * between
subsystems outweighed the small code duplication in the simple, familiar
patterned linked list-based code. So I ended up leaving it. 

2. Kai suggested (but later retracted the idea) that since the external 
page table cache was moved to TDX code, it could simply install DPAMT 
pages for the cache at topup time. Then the installation of DPAMT backing 
for S-EPT page tables could be done outside of the mmu_lock. It could also 
be argued that it makes the design simpler in a way, because the external
page table cache acts like it did before. Anything in there could be simply
used. 

At the time my argument against this was that whether a huge page would be 
installed (and thus, whether DPAMT backing was needed) for the guest 
private memory would not be known until later, so early install solution
would need special late handling for TDX huge pages. After some internal
discussions I at looked how we could simplify the series by punting on TDX
huge pages needs. 

But it turns out that this other design was actually more complex and had 
more LOC than the previous solution. So it was dropped, and again, I went 
back to the original solution. 


I’m really starting to think that, while the overall solution here isn’t 
the most elegant, we might not have much more to squeeze from it. So 
design-wise, I think we should think about calling it done. 

Testing
=======
Based on kvm-x86/next (4531ff85d925). Testing was the usual, except I also 
tested with TDX modules that don't support DPAMT, and with the two 
optimization patches removed: “Improve PAMT refcounters allocation for 
sparse memory” and “x86/virt/tdx: Optimize tdx_alloc/free_page() helpers”.

[0] https://lore.kernel.org/kvm/20250918232224.2202592-1-rick.p.edgecombe@intel.com/ 


Kirill A. Shutemov (13):
  x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>
  x86/tdx: Add helpers to check return status codes
  x86/virt/tdx: Allocate page bitmap for Dynamic PAMT
  x86/virt/tdx: Allocate reference counters for PAMT memory
  x86/virt/tdx: Improve PAMT refcounts allocation for sparse memory
  x86/virt/tdx: Add tdx_alloc/free_page() helpers
  x86/virt/tdx: Optimize tdx_alloc/free_page() helpers
  KVM: TDX: Allocate PAMT memory for TD control structures
  KVM: TDX: Allocate PAMT memory for vCPU control structures
  KVM: TDX: Handle PAMT allocation in fault path
  KVM: TDX: Reclaim PAMT memory
  x86/virt/tdx: Enable Dynamic PAMT
  Documentation/x86: Add documentation for TDX's Dynamic PAMT

Rick Edgecombe (3):
  x86/virt/tdx: Simplify tdmr_get_pamt_sz()
  KVM: TDX: Add x86 ops for external spt cache
  x86/virt/tdx: Add helpers to allow for pre-allocating pages

 Documentation/arch/x86/tdx.rst              |  21 +
 arch/x86/coco/tdx/tdx.c                     |  10 +-
 arch/x86/include/asm/kvm-x86-ops.h          |   3 +
 arch/x86/include/asm/kvm_host.h             |  14 +-
 arch/x86/include/asm/shared/tdx.h           |   8 +
 arch/x86/include/asm/shared/tdx_errno.h     | 104 ++++
 arch/x86/include/asm/tdx.h                  |  78 ++-
 arch/x86/include/asm/tdx_global_metadata.h  |   1 +
 arch/x86/kvm/mmu/mmu.c                      |   6 +-
 arch/x86/kvm/mmu/mmu_internal.h             |   2 +-
 arch/x86/kvm/vmx/tdx.c                      | 160 ++++--
 arch/x86/kvm/vmx/tdx.h                      |   3 +-
 arch/x86/kvm/vmx/tdx_errno.h                |  40 --
 arch/x86/virt/vmx/tdx/tdx.c                 | 587 +++++++++++++++++---
 arch/x86/virt/vmx/tdx/tdx.h                 |   5 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |   7 +
 16 files changed, 854 insertions(+), 195 deletions(-)
 create mode 100644 arch/x86/include/asm/shared/tdx_errno.h
 delete mode 100644 arch/x86/kvm/vmx/tdx_errno.h

---

## [2] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 01/16] x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Today there are two separate locations where TDX error codes are defined:
         arch/x86/include/asm/tdx.h
         arch/x86/kvm/vmx/tdx_errno.h

They have some overlap that is already defined similarly. Reduce the
duplication and prepare to introduce some helpers for these error codes in
the central place by unifying them. Join them at:
        asm/shared/tdx_errno.h
...and update the headers that contained the duplicated definitions to
include the new unified header.

"asm/shared" is used for sharing TDX code between the early compressed
code and the normal kernel code. While the compressed code for the guest
doesn't use these error code header definitions today, it does make the
types of calls that return the values they define. So place the defines in
"shared" location so that it can, but leave such cleanups for future
changes.

Opportunistically massage some comments. Also, adjust
_BITUL()->_BITULL() to address 32 bit build errors after the move.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Justify "asm/shared" location in log (Kai)
 - Fix "vmx" directory name in log (Xiaoyao)
 - Add asm/trapnr.h include in this patch intead of the next (Xiaoyao)

v3:
 - Split from "x86/tdx: Consolidate TDX error handling" (Dave, Kai)
 - Write log (Rick)
 - Fix 32 bit build error
---
 arch/x86/include/asm/shared/tdx.h             |  1 +
 .../vmx => include/asm/shared}/tdx_errno.h    | 27 +++++++++++++++----
 arch/x86/include/asm/tdx.h                    | 20 --------------
 arch/x86/kvm/vmx/tdx.h                        |  1 -
 4 files changed, 23 insertions(+), 26 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (65%)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 8bc074c8d7c6..6a1646fc2b2f 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -4,6 +4,7 @@
 
 #include <linux/bits.h>
 #include <linux/types.h>
+#include <asm/shared/tdx_errno.h>
 
 #define TDX_HYPERCALL_STANDARD  0
 
diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
similarity index 65%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/shared/tdx_errno.h
index 6ff4672c4181..3aa74f6a6119 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -1,14 +1,16 @@
 /* SPDX-License-Identifier: GPL-2.0 */
-/* architectural status code for SEAMCALL */
+#ifndef _X86_SHARED_TDX_ERRNO_H
+#define _X86_SHARED_TDX_ERRNO_H
 
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
+#include <asm/trapnr.h>
 
+/* Upper 32 bit of the TDX error code encodes the status */
 #define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
 
 /*
- * TDX SEAMCALL Status Codes (returned in RAX)
+ * TDX SEAMCALL Status Codes
  */
+#define TDX_SUCCESS				0ULL
 #define TDX_NON_RECOVERABLE_VCPU		0x4000000100000000ULL
 #define TDX_NON_RECOVERABLE_TD			0x4000000200000000ULL
 #define TDX_NON_RECOVERABLE_TD_NON_ACCESSIBLE	0x6000000500000000ULL
@@ -17,6 +19,7 @@
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
+#define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
@@ -28,6 +31,20 @@
 #define TDX_EPT_ENTRY_STATE_INCORRECT		0xC0000B0D00000000ULL
 #define TDX_METADATA_FIELD_NOT_READABLE		0xC0000C0200000000ULL
 
+/*
+ * SW-defined error codes.
+ *
+ * Bits 47:40 == 0xFF indicate Reserved status code class that never used by
+ * TDX module.
+ */
+#define TDX_ERROR			_BITULL(63)
+#define TDX_NON_RECOVERABLE		_BITULL(62)
+#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
+#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _ULL(0xFFFF0000))
+
+#define TDX_SEAMCALL_GP			(TDX_SW_ERROR | X86_TRAP_GP)
+#define TDX_SEAMCALL_UD			(TDX_SW_ERROR | X86_TRAP_UD)
+
 /*
  * TDX module operand ID, appears in 31:0 part of error code as
  * detail information
@@ -37,4 +54,4 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#endif /* _X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 6b338d7f01b7..2f3e16b93b4c 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -12,26 +12,6 @@
 #include <asm/trapnr.h>
 #include <asm/shared/tdx.h>
 
-/*
- * SW-defined error codes.
- *
- * Bits 47:40 == 0xFF indicate Reserved status code class that never used by
- * TDX module.
- */
-#define TDX_ERROR			_BITUL(63)
-#define TDX_NON_RECOVERABLE		_BITUL(62)
-#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
-#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _UL(0xFFFF0000))
-
-#define TDX_SEAMCALL_GP			(TDX_SW_ERROR | X86_TRAP_GP)
-#define TDX_SEAMCALL_UD			(TDX_SW_ERROR | X86_TRAP_UD)
-
-/*
- * TDX module SEAMCALL leaf function error codes
- */
-#define TDX_SUCCESS		0ULL
-#define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
-
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index 45b5183ccb36..ce2720a028ad 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -3,7 +3,6 @@
 #define __KVM_X86_VMX_TDX_H
 
 #include "tdx_arch.h"
-#include "tdx_errno.h"
 
 #ifdef CONFIG_KVM_INTEL_TDX
 #include "common.h"

---

## [3] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 02/16] x86/tdx: Add helpers to check return status codes*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The TDX error code has a complex structure. The upper 32 bits encode the
status code (higher level information), while the lower 32 bits provide
clues about the error, such as operand ID, CPUID leaf, MSR index, etc.

In practice, the kernel logic cares mostly about the status code. Whereas
the error details are more often dumped to warnings to be used as
debugging breadcrumbs. This results in a lot of code that masks the status
code and then checks the resulting value. Future code to support Dynamic
PAMT will add yet more SEAMCALL error code checking. To prepare for this,
do some cleanup to reduce the boiler plate error code parsing.

Since the lower bits that contain details are needed for both error
printing and a few cases where the logical code flow does depend on them,
don’t reduce the boiler plate by masking the detail bits inside the
SEAMCALL wrappers, returning only the status code. Instead, create some
helpers to perform the needed masking and comparisons.

For the status code based checks, create a macro for generating the
helpers based on the name. Name the helpers IS_TDX_FOO(), based on the
discussion in the Link.

Many of the checks that consult the error details are only done in a
single place. It could be argued that there is not any code savings by
adding helpers for these checks. Add helpers for them anyway so that the
checks look consistent when uses with checks that are used in multiple
places (e.g. sc_retry_prerr()).

Finally, update the code that previously open coded the bit math to use
the helpers.

Link: https://lore.kernel.org/kvm/aJNycTvk1GEWgK_Q@google.com/
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Switch tdx_mcall_extend_rtmr() to new helpers (Xiaoyao)
 - Move asm/trapnr.h to previous patch (Xiaoyao)
 - Use DEFINE_TDX_ERRNO_HELPER() for IS_TDX_SW_ERROR() (Kai)
 - Don't treat TDX_SEAMCALL_GP/UD like a mask (Xiaoyao)
 - Log typos (Kai)

v3:
 - Split from "x86/tdx: Consolidate TDX error handling" (Dave, Kai)
 - Change name from IS_TDX_ERR_FOO() to IS_TDX_FOO() after the
   conclusion to one of those naming debates. (Sean, Dave)
---
 arch/x86/coco/tdx/tdx.c                 | 10 +++---
 arch/x86/include/asm/shared/tdx_errno.h | 47 ++++++++++++++++++++++++-
 arch/x86/include/asm/tdx.h              |  2 +-
 arch/x86/kvm/vmx/tdx.c                  | 41 ++++++++++-----------
 arch/x86/virt/vmx/tdx/tdx.c             |  8 ++---
 5 files changed, 74 insertions(+), 34 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..167c5b273c40 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -129,9 +129,9 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 
 	ret = __tdcall(TDG_MR_REPORT, &args);
 	if (ret) {
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
+		if (IS_TDX_OPERAND_INVALID(ret))
 			return -ENXIO;
-		else if (TDCALL_RETURN_CODE(ret) == TDCALL_OPERAND_BUSY)
+		else if (IS_TDX_OPERAND_BUSY(ret))
 			return -EBUSY;
 		return -EIO;
 	}
@@ -165,9 +165,9 @@ int tdx_mcall_extend_rtmr(u8 index, u8 *data)
 
 	ret = __tdcall(TDG_MR_RTMR_EXTEND, &args);
 	if (ret) {
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
+		if (IS_TDX_OPERAND_INVALID(ret))
 			return -ENXIO;
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_OPERAND_BUSY)
+		if (IS_TDX_OPERAND_BUSY(ret))
 			return -EBUSY;
 		return -EIO;
 	}
@@ -316,7 +316,7 @@ static void reduce_unnecessary_ve(void)
 {
 	u64 err = tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
 
-	if (err == TDX_SUCCESS)
+	if (IS_TDX_SUCCESS(err))
 		return;
 
 	/*
diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index 3aa74f6a6119..e302aed31b50 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -5,7 +5,7 @@
 #include <asm/trapnr.h>
 
 /* Upper 32 bit of the TDX error code encodes the status */
-#define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
+#define TDX_STATUS_MASK				0xFFFFFFFF00000000ULL
 
 /*
  * TDX SEAMCALL Status Codes
@@ -54,4 +54,49 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
+#ifndef __ASSEMBLER__
+#include <linux/bits.h>
+#include <linux/types.h>
+
+static inline u64 TDX_STATUS(u64 err)
+{
+	return err & TDX_STATUS_MASK;
+}
+
+static inline bool IS_TDX_NON_RECOVERABLE(u64 err)
+{
+	return (err & TDX_NON_RECOVERABLE) == TDX_NON_RECOVERABLE;
+}
+
+static inline bool IS_TDX_SEAMCALL_VMFAILINVALID(u64 err)
+{
+	return (err & TDX_SEAMCALL_VMFAILINVALID) ==
+		TDX_SEAMCALL_VMFAILINVALID;
+}
+
+static inline bool IS_TDX_SEAMCALL_GP(u64 err)
+{
+	return err == TDX_SEAMCALL_GP;
+}
+
+static inline bool IS_TDX_SEAMCALL_UD(u64 err)
+{
+	return err == TDX_SEAMCALL_UD;
+}
+
+#define DEFINE_TDX_ERRNO_HELPER(error)			\
+	static inline bool IS_##error(u64 err)	\
+	{						\
+		return TDX_STATUS(err) == error;	\
+	}
+
+DEFINE_TDX_ERRNO_HELPER(TDX_SUCCESS);
+DEFINE_TDX_ERRNO_HELPER(TDX_RND_NO_ENTROPY);
+DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_INVALID);
+DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_BUSY);
+DEFINE_TDX_ERRNO_HELPER(TDX_VCPU_NOT_ASSOCIATED);
+DEFINE_TDX_ERRNO_HELPER(TDX_FLUSHVP_NOT_DONE);
+DEFINE_TDX_ERRNO_HELPER(TDX_SW_ERROR);
+
+#endif /* __ASSEMBLER__ */
 #endif /* _X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 2f3e16b93b4c..99bbeed8fb28 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -117,7 +117,7 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 		preempt_disable();
 		ret = __seamcall_dirty_cache(func, fn, args);
 		preempt_enable();
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
+	} while (IS_TDX_RND_NO_ENTROPY(ret) && --retry);
 
 	return ret;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index e6105a527372..0eed334176b3 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -220,12 +220,6 @@ static DEFINE_MUTEX(tdx_lock);
 
 static atomic_t nr_configured_hkid;
 
-static bool tdx_operand_busy(u64 err)
-{
-	return (err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_BUSY;
-}
-
-
 /*
  * A per-CPU list of TD vCPUs associated with a given CPU.
  * Protected by interrupt mask. Only manipulated by the CPU owning this per-CPU
@@ -312,7 +306,7 @@ static inline void tdx_disassociate_vp(struct kvm_vcpu *vcpu)
 	lockdep_assert_held_write(&kvm->mmu_lock);				\
 										\
 	__err = tdh_func(args);							\
-	if (unlikely(tdx_operand_busy(__err))) {				\
+	if (unlikely(IS_TDX_OPERAND_BUSY(__err))) {				\
 		WRITE_ONCE(__kvm_tdx->wait_for_sept_zap, true);			\
 		kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);	\
 										\
@@ -400,7 +394,7 @@ static void tdx_flush_vp(void *_arg)
 		 * migration.  No other thread uses TDVPR in those cases.
 		 */
 		err = tdh_vp_flush(&to_tdx(vcpu)->vp);
-		if (unlikely(err && err != TDX_VCPU_NOT_ASSOCIATED)) {
+		if (unlikely(!IS_TDX_VCPU_NOT_ASSOCIATED(err))) {
 			/*
 			 * This function is called in IPI context. Do not use
 			 * printk to avoid console semaphore.
@@ -467,7 +461,7 @@ static void smp_func_do_phymem_cache_wb(void *unused)
 	/*
 	 * TDH.PHYMEM.CACHE.WB flushes caches associated with any TDX private
 	 * KeyID on the package or core.  The TDX module may not finish the
-	 * cache flush but return TDX_INTERRUPTED_RESUMEABLE instead.  The
+	 * cache flush but return TDX_ERR_INTERRUPTED_RESUMEABLE instead.  The
 	 * kernel should retry it until it returns success w/o rescheduling.
 	 */
 	for (i = TDX_SEAMCALL_RETRIES; i > 0; i--) {
@@ -522,7 +516,7 @@ void tdx_mmu_release_hkid(struct kvm *kvm)
 	 * associations, as all vCPU fds have been released at this stage.
 	 */
 	err = tdh_mng_vpflushdone(&kvm_tdx->td);
-	if (err == TDX_FLUSHVP_NOT_DONE)
+	if (IS_TDX_FLUSHVP_NOT_DONE(err))
 		goto out;
 	if (TDX_BUG_ON(err, TDH_MNG_VPFLUSHDONE, kvm)) {
 		pr_err("tdh_mng_vpflushdone() failed. HKID %d is leaked.\n",
@@ -937,7 +931,7 @@ static __always_inline u32 tdx_to_vmx_exit_reason(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u32 exit_reason;
 
-	switch (tdx->vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) {
+	switch (TDX_STATUS(tdx->vp_enter_ret)) {
 	case TDX_SUCCESS:
 	case TDX_NON_RECOVERABLE_VCPU:
 	case TDX_NON_RECOVERABLE_TD:
@@ -1011,7 +1005,7 @@ static fastpath_t tdx_exit_handlers_fastpath(struct kvm_vcpu *vcpu)
 	 * EXIT_FASTPATH_REENTER_GUEST to exit fastpath, otherwise, the
 	 * requester may be blocked endlessly.
 	 */
-	if (unlikely(tdx_operand_busy(vp_enter_ret)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(vp_enter_ret)))
 		return EXIT_FASTPATH_EXIT_HANDLED;
 
 	return EXIT_FASTPATH_NONE;
@@ -1107,7 +1101,7 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	if (unlikely(tdx->vp_enter_ret == EXIT_REASON_EPT_MISCONFIG))
 		return EXIT_FASTPATH_NONE;
 
-	if (unlikely((tdx->vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR))
+	if (unlikely(IS_TDX_SW_ERROR(tdx->vp_enter_ret)))
 		return EXIT_FASTPATH_NONE;
 
 	if (unlikely(vmx_get_exit_reason(vcpu).basic == EXIT_REASON_MCE_DURING_VMENTRY))
@@ -1639,7 +1633,7 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 
 	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
 			       kvm_tdx->page_add_src, &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_ADD, entry, level_state, kvm))
@@ -1659,7 +1653,8 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	u64 err;
 
 	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, tdx_level, page, &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+
+	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_AUG, entry, level_state, kvm))
@@ -1709,7 +1704,7 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level, page, &entry,
 			       &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
 	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
@@ -1996,7 +1991,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	 * Handle TDX SW errors, including TDX_SEAMCALL_UD, TDX_SEAMCALL_GP and
 	 * TDX_SEAMCALL_VMFAILINVALID.
 	 */
-	if (unlikely((vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR)) {
+	if (unlikely(IS_TDX_SW_ERROR(vp_enter_ret))) {
 		KVM_BUG_ON(!kvm_rebooting, vcpu->kvm);
 		goto unhandled_exit;
 	}
@@ -2007,7 +2002,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 		 * not enabled, TDX_NON_RECOVERABLE must be set.
 		 */
 		WARN_ON_ONCE(vcpu->arch.guest_state_protected &&
-				!(vp_enter_ret & TDX_NON_RECOVERABLE));
+			     !IS_TDX_NON_RECOVERABLE(vp_enter_ret));
 		vcpu->run->exit_reason = KVM_EXIT_FAIL_ENTRY;
 		vcpu->run->fail_entry.hardware_entry_failure_reason = exit_reason.full;
 		vcpu->run->fail_entry.cpu = vcpu->arch.last_vmentry_cpu;
@@ -2021,7 +2016,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	}
 
 	WARN_ON_ONCE(exit_reason.basic != EXIT_REASON_TRIPLE_FAULT &&
-		     (vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) != TDX_SUCCESS);
+		     !IS_TDX_SUCCESS(vp_enter_ret));
 
 	switch (exit_reason.basic) {
 	case EXIT_REASON_TRIPLE_FAULT:
@@ -2455,7 +2450,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	err = tdh_mng_create(&kvm_tdx->td, kvm_tdx->hkid);
 	mutex_unlock(&tdx_lock);
 
-	if (err == TDX_RND_NO_ENTROPY) {
+	if (IS_TDX_RND_NO_ENTROPY(err)) {
 		ret = -EAGAIN;
 		goto free_packages;
 	}
@@ -2496,7 +2491,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	kvm_tdx->td.tdcs_pages = tdcs_pages;
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
 		err = tdh_mng_addcx(&kvm_tdx->td, tdcs_pages[i]);
-		if (err == TDX_RND_NO_ENTROPY) {
+		if (IS_TDX_RND_NO_ENTROPY(err)) {
 			/* Here it's hard to allow userspace to retry. */
 			ret = -EAGAIN;
 			goto teardown;
@@ -2508,7 +2503,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	}
 
 	err = tdh_mng_init(&kvm_tdx->td, __pa(td_params), &rcx);
-	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_INVALID) {
+	if (IS_TDX_OPERAND_INVALID(err)) {
 		/*
 		 * Because a user gives operands, don't warn.
 		 * Return a hint to the user because it's sometimes hard for the
@@ -2822,7 +2817,7 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 		return -EINVAL;
 
 	cmd->hw_error = tdh_mr_finalize(&kvm_tdx->td);
-	if (tdx_operand_busy(cmd->hw_error))
+	if (IS_TDX_OPERAND_BUSY(cmd->hw_error))
 		return -EBUSY;
 	if (TDX_BUG_ON(cmd->hw_error, TDH_MR_FINALIZE, kvm))
 		return -EIO;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index eac403248462..290f5e9c98c8 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -81,16 +81,16 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 {
 	u64 sret = sc_retry(func, fn, args);
 
-	if (sret == TDX_SUCCESS)
+	if (IS_TDX_SUCCESS(sret))
 		return 0;
 
-	if (sret == TDX_SEAMCALL_VMFAILINVALID)
+	if (IS_TDX_SEAMCALL_VMFAILINVALID(sret))
 		return -ENODEV;
 
-	if (sret == TDX_SEAMCALL_GP)
+	if (IS_TDX_SEAMCALL_GP(sret))
 		return -EOPNOTSUPP;
 
-	if (sret == TDX_SEAMCALL_UD)
+	if (IS_TDX_SEAMCALL_UD(sret))
 		return -EACCES;
 
 	err_func(fn, sret, args);

---

## [4] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

For each memory region that the TDX module might use (TDMR), the three
separate PAMT allocations are needed. One for each supported page size
(1GB, 2MB, 4KB). These store information on each page in the TDMR. In
Linux, they are allocated out of one physically contiguous block, in order
to more efficiently use some internal TDX module book keeping resources.
So some simple math is needed to break the single large allocation into
three smaller allocations for each page size.

There are some commonalities in the math needed to calculate the base and
size for each smaller allocation, and so an effort was made to share logic
across the three. Unfortunately doing this turned out naturally tortured,
with a loop iterating over the three page sizes, only to call into a
function with a case statement for each page size. In the future Dynamic
PAMT will add more logic that is special to the 4KB page size, making the
benefit of the math sharing even more questionable.

Three is not a very high number, so get rid of the loop and just duplicate
the small calculation three times. In doing so, setup for future Dynamic
PAMT changes and drop a net 33 lines of code.

Since the loop that iterates over it is gone, further simplify the code by
dropping the array of intermediate size and base storage. Just store the
values to their final locations. Accept the small complication of having
to clear tdmr->pamt_4k_base in the error path, so that tdmr_do_pamt_func()
will not try to operate on the TDMR struct when attempting to free it.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Just refer to global var instead of passing pamt_entry_size around
   (Xiaoyao)
 - Remove setting pamt_4k_base to zero, because it already is zero.
   Adjust the comment appropriately (Kai)

v3:
 - New patch
---
 arch/x86/virt/vmx/tdx/tdx.c | 93 ++++++++++++-------------------------
 1 file changed, 29 insertions(+), 64 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 290f5e9c98c8..f2b16a91ba58 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -444,31 +444,21 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
  */
-static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-				      u16 pamt_entry_size)
+static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz)
 {
 	unsigned long pamt_sz, nr_pamt_entries;
+	const int tdx_pg_size_shift[] = { PAGE_SHIFT, PMD_SHIFT, PUD_SHIFT };
+	const u16 pamt_entry_size[TDX_PS_NR] = {
+		tdx_sysinfo.tdmr.pamt_4k_entry_size,
+		tdx_sysinfo.tdmr.pamt_2m_entry_size,
+		tdx_sysinfo.tdmr.pamt_1g_entry_size,
+	};
 
-	switch (pgsz) {
-	case TDX_PS_4K:
-		nr_pamt_entries = tdmr->size >> PAGE_SHIFT;
-		break;
-	case TDX_PS_2M:
-		nr_pamt_entries = tdmr->size >> PMD_SHIFT;
-		break;
-	case TDX_PS_1G:
-		nr_pamt_entries = tdmr->size >> PUD_SHIFT;
-		break;
-	default:
-		WARN_ON_ONCE(1);
-		return 0;
-	}
+	nr_pamt_entries = tdmr->size >> tdx_pg_size_shift[pgsz];
+	pamt_sz = nr_pamt_entries * pamt_entry_size[pgsz];
 
-	pamt_sz = nr_pamt_entries * pamt_entry_size;
 	/* TDX requires PAMT size must be 4K aligned */
-	pamt_sz = ALIGN(pamt_sz, PAGE_SIZE);
-
-	return pamt_sz;
+	return PAGE_ALIGN(pamt_sz);
 }
 
 /*
@@ -506,28 +496,21 @@ static int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_list)
  * within @tdmr, and set up PAMTs for @tdmr.
  */
 static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
-			    struct list_head *tmb_list,
-			    u16 pamt_entry_size[])
+			    struct list_head *tmb_list)
 {
-	unsigned long pamt_base[TDX_PS_NR];
-	unsigned long pamt_size[TDX_PS_NR];
-	unsigned long tdmr_pamt_base;
 	unsigned long tdmr_pamt_size;
 	struct page *pamt;
-	int pgsz, nid;
-
+	int nid;
 	nid = tdmr_get_nid(tdmr, tmb_list);
 
 	/*
 	 * Calculate the PAMT size for each TDX supported page size
 	 * and the total PAMT size.
 	 */
-	tdmr_pamt_size = 0;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-		pamt_size[pgsz] = tdmr_get_pamt_sz(tdmr, pgsz,
-					pamt_entry_size[pgsz]);
-		tdmr_pamt_size += pamt_size[pgsz];
-	}
+	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M);
+	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G);
+	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
 
 	/*
 	 * Allocate one chunk of physically contiguous memory for all
@@ -535,26 +518,18 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * in overlapped TDMRs.
 	 */
 	pamt = alloc_contig_pages(tdmr_pamt_size >> PAGE_SHIFT, GFP_KERNEL,
-			nid, &node_online_map);
-	if (!pamt)
+				  nid, &node_online_map);
+	if (!pamt) {
+		/*
+		 * tdmr->pamt_4k_base is zero so the
+		 * error path will skip freeing.
+		 */
 		return -ENOMEM;
-
-	/*
-	 * Break the contiguous allocation back up into the
-	 * individual PAMTs for each page size.
-	 */
-	tdmr_pamt_base = page_to_pfn(pamt) << PAGE_SHIFT;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-		pamt_base[pgsz] = tdmr_pamt_base;
-		tdmr_pamt_base += pamt_size[pgsz];
 	}
 
-	tdmr->pamt_4k_base = pamt_base[TDX_PS_4K];
-	tdmr->pamt_4k_size = pamt_size[TDX_PS_4K];
-	tdmr->pamt_2m_base = pamt_base[TDX_PS_2M];
-	tdmr->pamt_2m_size = pamt_size[TDX_PS_2M];
-	tdmr->pamt_1g_base = pamt_base[TDX_PS_1G];
-	tdmr->pamt_1g_size = pamt_size[TDX_PS_1G];
+	tdmr->pamt_4k_base = page_to_phys(pamt);
+	tdmr->pamt_2m_base = tdmr->pamt_4k_base + tdmr->pamt_4k_size;
+	tdmr->pamt_1g_base = tdmr->pamt_2m_base + tdmr->pamt_2m_size;
 
 	return 0;
 }
@@ -585,10 +560,7 @@ static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 	tdmr_get_pamt(tdmr, &pamt_base, &pamt_size);
 
 	/* Do nothing if PAMT hasn't been allocated for this TDMR */
-	if (!pamt_size)
-		return;
-
-	if (WARN_ON_ONCE(!pamt_base))
+	if (!pamt_base)
 		return;
 
 	pamt_func(pamt_base, pamt_size);
@@ -614,14 +586,12 @@ static void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
 
 /* Allocate and set up PAMTs for all TDMRs */
 static int tdmrs_set_up_pamt_all(struct tdmr_info_list *tdmr_list,
-				 struct list_head *tmb_list,
-				 u16 pamt_entry_size[])
+				 struct list_head *tmb_list)
 {
 	int i, ret = 0;
 
 	for (i = 0; i < tdmr_list->nr_consumed_tdmrs; i++) {
-		ret = tdmr_set_up_pamt(tdmr_entry(tdmr_list, i), tmb_list,
-				pamt_entry_size);
+		ret = tdmr_set_up_pamt(tdmr_entry(tdmr_list, i), tmb_list);
 		if (ret)
 			goto err;
 	}
@@ -902,18 +872,13 @@ static int construct_tdmrs(struct list_head *tmb_list,
 			   struct tdmr_info_list *tdmr_list,
 			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
-	u16 pamt_entry_size[TDX_PS_NR] = {
-		sysinfo_tdmr->pamt_4k_entry_size,
-		sysinfo_tdmr->pamt_2m_entry_size,
-		sysinfo_tdmr->pamt_1g_entry_size,
-	};
 	int ret;
 
 	ret = fill_out_tdmrs(tmb_list, tdmr_list);
 	if (ret)
 		return ret;
 
-	ret = tdmrs_set_up_pamt_all(tdmr_list, tmb_list, pamt_entry_size);
+	ret = tdmrs_set_up_pamt_all(tdmr_list, tmb_list);
 	if (ret)
 		return ret;

---

## [5] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic PAMT*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The Physical Address Metadata Table (PAMT) holds TDX metadata for physical
memory and must be allocated by the kernel during TDX module
initialization.

The exact size of the required PAMT memory is determined by the TDX module
and may vary between TDX module versions. Currently it is approximately
0.4% of the system memory. This is a significant commitment, especially if
it is not known upfront whether the machine will run any TDX guests.

For normal PAMT, each memory region that the TDX module might use (TDMR)
needs three separate PAMT allocations. One for each supported page size
(1GB, 2MB, 4KB).

At a high level, Dynamic PAMT still has the 1GB and 2MB levels allocated
on TDX module initialization, but the 4KB level allocated dynamically at
TD runtime. However, in the details, the TDX module still needs some per
4KB page data. The TDX module exposed how many bits per page need to be
allocated (currently it is 1). The bits-per-page value can then be used to
calculate the size to pass in place of the 4KB allocations in the TDMR,
which TDX specs call "PAMT_PAGE_BITMAP".

So in effect, Dynamic PAMT just needs a different (smaller) size
allocation for the 4KB level part of the allocation. Although it is
functionally something different, it is passed in the same way the 4KB page
size PAMT allocation is.

Begin to implement Dynamic PAMT in the kernel by reading the bits-per-page
needed for Dynamic PAMT. Calculate the size needed for the bitmap,
and use it instead of the 4KB size determined for normal PAMT, in the case
of Dynamic PAMT. In doing so, reduce the static allocations to
approximately 0.004%, a 100x improvement.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Enhanced log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Use PAGE_ALIGN (Binbin)
 - Add comment about why tdx_supports_dynamic_pamt() is checked in
   metadata reading.

v3:
 - Simplify pamt_4k_size calculation after addition of refactor patch
 - Write log
---
 arch/x86/include/asm/tdx.h                  |  5 +++++
 arch/x86/include/asm/tdx_global_metadata.h  |  1 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 19 ++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  7 +++++++
 4 files changed, 31 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 99bbeed8fb28..cf51ccd16194 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -130,6 +130,11 @@ int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
+static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
+{
+	return false; /* To be enabled when kernel is ready */
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 060a2ad744bf..5eb808b23997 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -15,6 +15,7 @@ struct tdx_sys_info_tdmr {
 	u16 pamt_4k_entry_size;
 	u16 pamt_2m_entry_size;
 	u16 pamt_1g_entry_size;
+	u8  pamt_page_bitmap_entry_bits;
 };
 
 struct tdx_sys_info_td_ctrl {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f2b16a91ba58..6c522db71265 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -440,6 +440,18 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
 	return 0;
 }
 
+static unsigned long tdmr_get_pamt_bitmap_sz(struct tdmr_info *tdmr)
+{
+	unsigned long pamt_sz, nr_pamt_entries;
+	int bits_per_entry;
+
+	bits_per_entry = tdx_sysinfo.tdmr.pamt_page_bitmap_entry_bits;
+	nr_pamt_entries = tdmr->size >> PAGE_SHIFT;
+	pamt_sz = DIV_ROUND_UP(nr_pamt_entries * bits_per_entry, BITS_PER_BYTE);
+
+	return PAGE_ALIGN(pamt_sz);
+}
+
 /*
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
@@ -507,7 +519,12 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * Calculate the PAMT size for each TDX supported page size
 	 * and the total PAMT size.
 	 */
-	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		/* With Dynamic PAMT, PAMT_4K is replaced with a bitmap */
+		tdmr->pamt_4k_size = tdmr_get_pamt_bitmap_sz(tdmr);
+	} else {
+		tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	}
 	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M);
 	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G);
 	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..00ab0e550636 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -33,6 +33,13 @@ static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 		sysinfo_tdmr->pamt_2m_entry_size = val;
 	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000012, &val)))
 		sysinfo_tdmr->pamt_1g_entry_size = val;
+	/*
+	 * Don't fail here if tdx_supports_dynamic_pamt() isn't supported. The
+	 * TDX code can fallback to normal PAMT if it's not supported.
+	 */
+	if (!ret && tdx_supports_dynamic_pamt(&tdx_sysinfo) &&
+	    !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
+		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;
 
 	return ret;
 }

---

## [6] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 05/16] x86/virt/tdx: Allocate reference counters for PAMT memory*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The PAMT memory holds metadata for TDX protected memory. With Dynamic
PAMT, the 4KB range of PAMT is allocated on demand. The kernel supplies
the TDX module with a page pair that covers 2MB of host physical memory.

The kernel must provide this page pair before using pages from the range
for TDX. If this is not done, any SEAMCALL that attempts to use the memory
will fail.

Allocate reference counters for every 2MB range to track PAMT memory usage.
This is necessary to accurately determine when PAMT memory needs to be
allocated and when it can be freed.

This allocation will currently consume 2 MB for every 1 TB of address
space from 0 to max_pfn (highest pfn of RAM). The allocation size will
depend on how the ram is physically laid out. In a worse case scenario
where the entire 52 bit address space is covered this would be 8GB. Then
the DPAMT refcount allocations could hypothetically exceed the savings
from Dynamic PAMT, which is 4GB per TB. This is probably unlikely.

However, future changes will reduce this refcount overhead to make DPAMT
always a net win.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Log typo (Binbin)
 - round correctly when computing PAMT refcount size (Binbin)
 - Zero refcount vmalloc allocation (Note: This got replaced in
   optimization patch with a zero-ed allocation, but this showed up in
   testing with the optimization patches removed. Since it's fixed
   before this code is exercised, it's not a bisectability issue, but fix
   it anyway.)

v3:
 - Split out lazily populate optimization to next patch (Dave)
 - Add comment around pamt_refcounts (Dave)
 - Improve log
---
 arch/x86/virt/vmx/tdx/tdx.c | 47 ++++++++++++++++++++++++++++++++++++-
 1 file changed, 46 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 6c522db71265..c28d4d11736c 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -29,6 +29,7 @@
 #include <linux/acpi.h>
 #include <linux/suspend.h>
 #include <linux/idr.h>
+#include <linux/vmalloc.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -50,6 +51,16 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
+/*
+ * On a machine with Dynamic PAMT, the kernel maintains a reference counter
+ * for every 2M range. The counter indicates how many users there are for
+ * the PAMT memory of the 2M range.
+ *
+ * The kernel allocates PAMT memory when the first user arrives and
+ * frees it when the last user has left.
+ */
+static atomic_t *pamt_refcounts;
+
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
 
@@ -183,6 +194,34 @@ int tdx_cpu_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_cpu_enable);
 
+/*
+ * Allocate PAMT reference counters for all physical memory.
+ *
+ * It consumes 2MiB for every 1TiB of physical memory.
+ */
+static int init_pamt_metadata(void)
+{
+	size_t size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	pamt_refcounts = __vmalloc(size, GFP_KERNEL | __GFP_ZERO);
+	if (!pamt_refcounts)
+		return -ENOMEM;
+
+	return 0;
+}
+
+static void free_pamt_metadata(void)
+{
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	vfree(pamt_refcounts);
+	pamt_refcounts = NULL;
+}
+
 /*
  * Add a memory region as a TDX memory block.  The caller must make sure
  * all memory regions are added in address ascending order and don't
@@ -1082,10 +1121,14 @@ static int init_tdx_module(void)
 	 */
 	get_online_mems();
 
-	ret = build_tdx_memlist(&tdx_memlist);
+	ret = init_pamt_metadata();
 	if (ret)
 		goto out_put_tdxmem;
 
+	ret = build_tdx_memlist(&tdx_memlist);
+	if (ret)
+		goto err_free_pamt_metadata;
+
 	/* Allocate enough space for constructing TDMRs */
 	ret = alloc_tdmr_list(&tdx_tdmr_list, &tdx_sysinfo.tdmr);
 	if (ret)
@@ -1135,6 +1178,8 @@ static int init_tdx_module(void)
 	free_tdmr_list(&tdx_tdmr_list);
 err_free_tdxmem:
 	free_tdx_memlist(&tdx_memlist);
+err_free_pamt_metadata:
+	free_pamt_metadata();
 	goto out_put_tdxmem;
 }

---

## [7] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation for sparse memory*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

init_pamt_metadata() allocates PAMT refcounts for all physical memory up
to max_pfn. It might be suboptimal if the physical memory layout is
discontinuous and has large holes.

The refcount allocation vmalloc allocation. This is necessary to support a
large allocation size. The virtually contiguous property also makes it
easy to find a specific 2MB range’s refcount since it can simply be
indexed.

Since vmalloc mappings support remapping during normal kernel runtime,
switch to an approach that only populates refcount pages for the vmalloc
mapping when there is actually memory for that range. This means any holes
in the physical address space won’t use actual physical memory.

The validity of this memory optimization is based on a couple assumptions:
1. Physical holes in the ram layout are commonly large enough for it to be
   worth it.
2. An alternative approach that looks the refcounts via some more layered
   data structure wouldn’t overly complicate the lookups. Or at least
   more than the complexity of managing the vmalloc mapping.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Fix refcount allocation size calculation. (Kai, Binbin)
 - Fix/improve comments. (Kai, Binbin)
 - Simplify tdx_find_pamt_refcount() implemenation and callers by making
   it take a PFN and calculating it directly rather than going through a
   PA intermediate.
 - Check tdx_supports_dynamic_pamt() in alloc_pamt_refcount() to prevent
   crash when TDX module does not support DPAMT. (Kai)
 - Log change refcounters->refcount to be consistent

v3:
 - Split from "x86/virt/tdx: Allocate reference counters for
   PAMT memory" (Dave)
 - Rename tdx_get_pamt_refcount()->tdx_find_pamt_refcount() (Dave)
 - Drop duplicate pte_none() check (Dave)
 - Align assignments in alloc_pamt_refcount() (Kai)
 - Add comment in pamt_refcount_depopulate() to clarify teardown
   logic (Dave)
 - Drop __va(PFN_PHYS(pte_pfn(ptep_get()))) pile on for simpler method.
   (Dave)
 - Improve log
---
 arch/x86/virt/vmx/tdx/tdx.c | 136 +++++++++++++++++++++++++++++++++---
 1 file changed, 125 insertions(+), 11 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c28d4d11736c..edf9182ed86d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -194,30 +194,135 @@ int tdx_cpu_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_cpu_enable);
 
-/*
- * Allocate PAMT reference counters for all physical memory.
- *
- * It consumes 2MiB for every 1TiB of physical memory.
- */
-static int init_pamt_metadata(void)
+/* Find PAMT refcount for a given physical address */
+static atomic_t *tdx_find_pamt_refcount(unsigned long pfn)
 {
-	size_t size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);
+	/* Find which PMD a PFN is in. */
+	unsigned long index = pfn >> (PMD_SHIFT - PAGE_SHIFT);
 
-	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
-		return 0;
+	return &pamt_refcounts[index];
+}
 
-	pamt_refcounts = __vmalloc(size, GFP_KERNEL | __GFP_ZERO);
-	if (!pamt_refcounts)
+/* Map a page into the PAMT refcount vmalloc region */
+static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)
+{
+	struct page *page;
+	pte_t entry;
+
+	page = alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!page)
 		return -ENOMEM;
 
+	entry = mk_pte(page, PAGE_KERNEL);
+
+	spin_lock(&init_mm.page_table_lock);
+	/*
+	 * PAMT refcount populations can overlap due to rounding of the
+	 * start/end pfn. Make sure the PAMT range is only populated once.
+	 */
+	if (pte_none(ptep_get(pte)))
+		set_pte_at(&init_mm, addr, pte, entry);
+	else
+		__free_page(page);
+	spin_unlock(&init_mm.page_table_lock);
+
 	return 0;
 }
 
+/*
+ * Allocate PAMT reference counters for the given PFN range.
+ *
+ * It consumes 2MiB for every 1TiB of physical memory.
+ */
+static int alloc_pamt_refcount(unsigned long start_pfn, unsigned long end_pfn)
+{
+	unsigned long refcount_first, refcount_last;
+	unsigned long mapping_start, mapping_end;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	/*
+	 * 'start_pfn' is inclusive and 'end_pfn' is exclusive. Find the
+	 * range of refcounts the pfn range will need.
+	 */
+	refcount_first = (unsigned long)tdx_find_pamt_refcount(start_pfn);
+	refcount_last   = (unsigned long)tdx_find_pamt_refcount(end_pfn - 1);
+
+	/*
+	 * Calculate the page aligned range that includes the refcounts. The
+	 * teardown logic needs to handle potentially overlapping refcount
+	 * mappings resulting from the alignments.
+	 */
+	mapping_start = round_down(refcount_first, PAGE_SIZE);
+	mapping_end   = round_up(refcount_last + sizeof(*pamt_refcounts), PAGE_SIZE);
+
+
+	return apply_to_page_range(&init_mm, mapping_start, mapping_end - mapping_start,
+				   pamt_refcount_populate, NULL);
+}
+
+/*
+ * Reserve vmalloc range for PAMT reference counters. It covers all physical
+ * address space up to max_pfn. It is going to be populated from
+ * build_tdx_memlist() only for present memory that available for TDX use.
+ *
+ * It reserves 2MiB of virtual address space for every 1TiB of physical memory.
+ */
+static int init_pamt_metadata(void)
+{
+	struct vm_struct *area;
+	size_t size;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);
+
+	area = get_vm_area(size, VM_SPARSE);
+	if (!area)
+		return -ENOMEM;
+
+	pamt_refcounts = area->addr;
+	return 0;
+}
+
+/* Unmap a page from the PAMT refcount vmalloc region */
+static int pamt_refcount_depopulate(pte_t *pte, unsigned long addr, void *data)
+{
+	struct page *page;
+	pte_t entry;
+
+	spin_lock(&init_mm.page_table_lock);
+
+	entry = ptep_get(pte);
+	/* refcount allocation is sparse, may not be populated */
+	if (!pte_none(entry)) {
+		pte_clear(&init_mm, addr, pte);
+		page = pte_page(entry);
+		__free_page(page);
+	}
+
+	spin_unlock(&init_mm.page_table_lock);
+
+	return 0;
+}
+
+/* Unmap all PAMT refcount pages and free vmalloc range */
 static void free_pamt_metadata(void)
 {
+	size_t size;
+
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return;
 
+	size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+	size = round_up(size, PAGE_SIZE);
+
+	apply_to_existing_page_range(&init_mm,
+				     (unsigned long)pamt_refcounts,
+				     size, pamt_refcount_depopulate,
+				     NULL);
 	vfree(pamt_refcounts);
 	pamt_refcounts = NULL;
 }
@@ -288,10 +393,19 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 		ret = add_tdx_memblock(tmb_list, start_pfn, end_pfn, nid);
 		if (ret)
 			goto err;
+
+		/* Allocated PAMT refcountes for the memblock */
+		ret = alloc_pamt_refcount(start_pfn, end_pfn);
+		if (ret)
+			goto err;
 	}
 
 	return 0;
 err:
+	/*
+	 * Only free TDX memory blocks here, PAMT refcount pages
+	 * will be freed in the init_tdx_module() error path.
+	 */
 	free_tdx_memlist(tmb_list);
 	return ret;
 }

---

## [8] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Add helpers to use when allocating or preparing pages that need DPAMT
backing. Make them handle races internally for the case of multiple
callers trying operate on the same 2MB range simultaneously.

While the TDX initialization code in arch/x86 uses pages with 2MB
alignment, KVM will need to hand 4KB pages for it to use. Under DPAMT,
these pages will need DPAMT backing 4KB backing.

Add tdx_alloc_page() and tdx_free_page() to handle both page allocation
and DPAMT installation. Make them behave like normal alloc/free functions
where allocation can fail in the case of no memory, but free (with any
necessary DPAMT release) always succeeds. Do this so they can support the
existing TDX flows that require cleanups to succeed. Also create
tdx_pamt_put()/tdx_pamt_get() to handle installing DPAMT 4KB backing for
pages that are already allocated (such as external page tables, or S-EPT
pages).

Allocate the pages as GFP_KERNEL_ACCOUNT based on that the allocations
will be easily user triggerable.

Since the source of these pages is the page allocator, multiple TDs could
each get 4KB pages that are covered by the same 2MB range. When this
happens only one page pair needs to be installed to cover the 2MB range.
Similarly, when one page is freed, the DPAMT backing cannot be freed until
all TDX pages in the range are no longer in use. Have the helpers manage
these races internally.

So the requirements are that:

1. Free path cannot fail (i.e. no TDX module BUSY errors).
2. Allocation paths need to handle finding that DPAMT backing is already
   installed, and only return an error in the case of no memory, not in the
   case of losing races with other’s trying to operate on the same DPAMT
   range.
3. Free paths cannot fail, and also need to clean up the DPAMT backing
   when the last page in the 2MB range is no longer needed by TDX.

Previous changes allocated refcounts to be used to track how many 4KB
pages are in use by TDX for each 2MB region. So update those inside the
helpers and use them to decide when to actually install the DPAMT backing
pages.

tdx_pamt_put() needs to guarantee the DPAMT is installed before returning
so that racing threads don’t tell the TDX module to operate on the page
before it’s installed. Take a lock while adjusting the refcount and doing
the actual TDH.PHYMEM.PAMT.ADD/REMOVE to make sure these happen
atomically. The lock is heavyweight, but will be optimized in future
changes. Just do the simple solution before any complex improvements.

TDH.PHYMEM.PAMT.ADD/REMOVE take exclusive locks at the granularity each
2MB range. A simultaneous attempt to operate on the same 2MB region would
result in a BUSY error code returned from the SEAMCALL. Since the
invocation of SEAMCALLs are behind a lock, this won’t conflict.

Besides the contention between TDH.PHYMEM.PAMT.ADD/REMOVE, many other
SEAMCALLs take the same 2MB granularity locks as shared. This means any
attempt to operate on the page by the TDX module while simultaneously
doing PAMT.ADD/REMOVE will result in a BUSY error. This should not happen,
as the PAMT pages always has to be installed before giving the pages to
the TDX module anyway.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Update tdx_find_pamt_refcount() calls to pass PFN and rely on
   internal PMD bucket calculations. Based on changes in previous patch.
 - Pull calculation TDX DPAMT 2MB range arg into helper.
 - Fix alloc_pamt_array() doesn't zero array on allocation failure (Yan)
 - Move "prealloc" comment to future patch. (Kai)
 - Use union for dpamt page array. (Dave)
 - Use sizeof(*args_array) everywhere instead of sizeof(u64) in some
   places. (Dave)
 - Fix refcount inc/dec cases. (Xiaoyao)
 - Rearrange error handling in tdx_pamt_get()/tdx_pamt_put() to remove
   some indented lines.
 - Make alloc_pamt_array() use GFP_KERNEL_ACCOUNT like the pre-fault
   path does later.

v3:
 - Fix hard to follow iteration over struct members.
 - Simplify the code by removing the intermediate lists of pages.
 - Clear PAMT pages before freeing. (Adrian)
 - Rename tdx_nr_pamt_pages(). (Dave)
 - Add comments some comments, but thought the simpler code needed
   less. So not as much as seem to be requested. (Dave)
 - Fix asymmetry in which level of the add/remove helpers global lock is
   held.
 - Split out optimization.
 - Write log.
 - Flatten call hierarchies and adjust errors accordingly.
---
 arch/x86/include/asm/shared/tdx.h |   7 +
 arch/x86/include/asm/tdx.h        |   8 +-
 arch/x86/virt/vmx/tdx/tdx.c       | 258 ++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h       |   2 +
 4 files changed, 274 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 6a1646fc2b2f..cc2f251cb791 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -145,6 +145,13 @@ struct tdx_module_args {
 	u64 rsi;
 };
 
+struct tdx_module_array_args {
+	union {
+		struct tdx_module_args args;
+		u64 args_array[sizeof(struct tdx_module_args) / sizeof(u64)];
+	};
+};
+
 /* Used to communicate with the TDX module */
 u64 __tdcall(u64 fn, struct tdx_module_args *args);
 u64 __tdcall_ret(u64 fn, struct tdx_module_args *args);
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index cf51ccd16194..914213123d94 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -135,11 +135,17 @@ static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 	return false; /* To be enabled when kernel is ready */
 }
 
+void tdx_quirk_reset_page(struct page *page);
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
-void tdx_quirk_reset_page(struct page *page);
+int tdx_pamt_get(struct page *page);
+void tdx_pamt_put(struct page *page);
+
+struct page *tdx_alloc_page(void);
+void tdx_free_page(struct page *page);
 
 struct tdx_td {
 	/* TD root structure: */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index edf9182ed86d..745b308785d6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2009,6 +2009,264 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
 
+/* Number PAMT pages to be provided to TDX module per 2M region of PA */
+static int tdx_dpamt_entry_pages(void)
+{
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
+}
+
+/*
+ * The TDX spec treats the registers like an array, as they are ordered
+ * in the struct. The array size is limited by the number or registers,
+ * so define the max size it could be for worst case allocations and sanity
+ * checking.
+ */
+#define MAX_TDX_ARG_SIZE(reg) (sizeof(struct tdx_module_args) - \
+			       offsetof(struct tdx_module_args, reg))
+#define TDX_ARG_INDEX(reg) (offsetof(struct tdx_module_args, reg) / \
+			    sizeof(u64))
+
+/*
+ * Treat struct the registers like an array that starts at RDX, per
+ * TDX spec. Do some sanitychecks, and return an indexable type.
+ */
+static u64 *dpamt_args_array_ptr(struct tdx_module_array_args *args)
+{
+	WARN_ON_ONCE(tdx_dpamt_entry_pages() > MAX_TDX_ARG_SIZE(rdx));
+
+	return &args->args_array[TDX_ARG_INDEX(rdx)];
+}
+
+static int alloc_pamt_array(u64 *pa_array)
+{
+	struct page *page;
+	int i;
+
+	for (i = 0; i < tdx_dpamt_entry_pages(); i++) {
+		page = alloc_page(GFP_KERNEL_ACCOUNT);
+		if (!page)
+			goto err;
+		pa_array[i] = page_to_phys(page);
+	}
+
+	return 0;
+err:
+	/*
+	 * Zero the rest of the array to help with
+	 * freeing in error paths.
+	 */
+	for (; i < tdx_dpamt_entry_pages(); i++)
+		pa_array[i] = 0;
+	return -ENOMEM;
+}
+
+static void free_pamt_array(u64 *pa_array)
+{
+	for (int i = 0; i < tdx_dpamt_entry_pages(); i++) {
+		if (!pa_array[i])
+			break;
+
+		/*
+		 * Reset pages unconditionally to cover cases
+		 * where they were passed to the TDX module.
+		 */
+		tdx_quirk_reset_paddr(pa_array[i], PAGE_SIZE);
+
+		__free_page(phys_to_page(pa_array[i]));
+	}
+}
+
+/*
+ * Calculate the arg needed for operating on the DPAMT backing for
+ * a given 4KB page.
+ */
+static u64 pamt_2mb_arg(struct page *page)
+{
+	unsigned long hpa_2mb = ALIGN_DOWN(page_to_phys(page), PMD_SIZE);
+
+	return hpa_2mb | TDX_PS_2M;
+}
+
+/*
+ * Add PAMT backing for the given page. Return's negative error code
+ * for kernel side error conditions (-ENOMEM) and 1 for TDX Module
+ * error. In the case of TDX module error, the return code is stored
+ * in tdx_err.
+ */
+static u64 tdh_phymem_pamt_add(struct page *page, u64 *pamt_pa_array)
+{
+	struct tdx_module_array_args args = {
+		.args.rcx = pamt_2mb_arg(page)
+	};
+	u64 *dpamt_arg_array = dpamt_args_array_ptr(&args);
+
+	/* Copy PAMT page PA's into the struct per the TDX ABI */
+	memcpy(dpamt_arg_array, pamt_pa_array,
+	       tdx_dpamt_entry_pages() * sizeof(*dpamt_arg_array));
+
+	return seamcall(TDH_PHYMEM_PAMT_ADD, &args.args);
+}
+
+/* Remove PAMT backing for the given page. */
+static u64 tdh_phymem_pamt_remove(struct page *page, u64 *pamt_pa_array)
+{
+	struct tdx_module_array_args args = {
+		.args.rcx = pamt_2mb_arg(page),
+	};
+	u64 *args_array = dpamt_args_array_ptr(&args);
+	u64 ret;
+
+	ret = seamcall_ret(TDH_PHYMEM_PAMT_REMOVE, &args.args);
+	if (ret)
+		return ret;
+
+	/* Copy PAMT page PA's out of the struct per the TDX ABI */
+	memcpy(pamt_pa_array, args_array,
+	       tdx_dpamt_entry_pages() * sizeof(*args_array));
+
+	return ret;
+}
+
+/* Serializes adding/removing PAMT memory */
+static DEFINE_SPINLOCK(pamt_lock);
+
+/* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
+int tdx_pamt_get(struct page *page)
+{
+	u64 pamt_pa_array[MAX_TDX_ARG_SIZE(rdx)];
+	atomic_t *pamt_refcount;
+	u64 tdx_status;
+	int ret;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	ret = alloc_pamt_array(pamt_pa_array);
+	if (ret)
+		goto out_free;
+
+	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+
+	scoped_guard(spinlock, &pamt_lock) {
+		/*
+		 * If the pamt page is already added (i.e. refcount >= 1),
+		 * then just increment the refcount.
+		 */
+		if (atomic_read(pamt_refcount)) {
+			atomic_inc(pamt_refcount);
+			goto out_free;
+		}
+
+		/* Try to add the pamt page and take the refcount 0->1. */
+
+		tdx_status = tdh_phymem_pamt_add(page, pamt_pa_array);
+		if (!IS_TDX_SUCCESS(tdx_status)) {
+			pr_err("TDH_PHYMEM_PAMT_ADD failed: %#llx\n", tdx_status);
+			goto out_free;
+		}
+
+		atomic_inc(pamt_refcount);
+	}
+
+	return ret;
+out_free:
+	/*
+	 * pamt_pa_array is populated or zeroed up to tdx_dpamt_entry_pages()
+	 * above. free_pamt_array() can handle either case.
+	 */
+	free_pamt_array(pamt_pa_array);
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tdx_pamt_get);
+
+/*
+ * Drop PAMT refcount for the given page and free PAMT memory if it is no
+ * longer needed.
+ */
+void tdx_pamt_put(struct page *page)
+{
+	u64 pamt_pa_array[MAX_TDX_ARG_SIZE(rdx)];
+	atomic_t *pamt_refcount;
+	u64 tdx_status;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+
+	scoped_guard(spinlock, &pamt_lock) {
+		/*
+		 * If the there are more than 1 references on the pamt page,
+		 * don't remove it yet. Just decrement the refcount.
+		 */
+		if (atomic_read(pamt_refcount) > 1) {
+			atomic_dec(pamt_refcount);
+			return;
+		}
+
+		/* Try to remove the pamt page and take the refcount 1->0. */
+
+		tdx_status = tdh_phymem_pamt_remove(page, pamt_pa_array);
+		if (!IS_TDX_SUCCESS(tdx_status)) {
+			pr_err("TDH_PHYMEM_PAMT_REMOVE failed: %#llx\n", tdx_status);
+
+			/*
+			 * Don't free pamt_pa_array as it could hold garbage
+			 * when tdh_phymem_pamt_remove() fails.
+			 */
+			return;
+		}
+
+		atomic_dec(pamt_refcount);
+	}
+
+	/*
+	 * pamt_pa_array is populated up to tdx_dpamt_entry_pages() by the TDX
+	 * module with pages, or remains zero inited. free_pamt_array() can
+	 * handle either case. Just pass it unconditionally.
+	 */
+	free_pamt_array(pamt_pa_array);
+}
+EXPORT_SYMBOL_GPL(tdx_pamt_put);
+
+/*
+ * Return a page that can be used as TDX private memory
+ * and obtain TDX protections.
+ */
+struct page *tdx_alloc_page(void)
+{
+	struct page *page;
+
+	page = alloc_page(GFP_KERNEL);
+	if (!page)
+		return NULL;
+
+	if (tdx_pamt_get(page)) {
+		__free_page(page);
+		return NULL;
+	}
+
+	return page;
+}
+EXPORT_SYMBOL_GPL(tdx_alloc_page);
+
+/*
+ * Free a page that was used as TDX private memory. After this,
+ * the page is no longer protected by TDX.
+ */
+void tdx_free_page(struct page *page)
+{
+	if (!page)
+		return;
+
+	tdx_pamt_put(page);
+	__free_page(page);
+}
+EXPORT_SYMBOL_GPL(tdx_free_page);
+
 #ifdef CONFIG_KEXEC_CORE
 void tdx_cpu_flush_cache_for_kexec(void)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 82bb82be8567..46c4214b79fb 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,8 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_PHYMEM_PAMT_ADD		58
+#define TDH_PHYMEM_PAMT_REMOVE		59
 
 /*
  * SEAMCALL leaf:

---

## [9] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 08/16] x86/virt/tdx: Optimize tdx_alloc/free_page() helpers*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Optimize the PAMT alloc/free helpers to avoid taking the global lock when
possible.

The recently introduced PAMT alloc/free helpers maintain a refcount to
keep track of when it is ok to reclaim and free a 4KB PAMT page. This
refcount is protected by a global lock in order to guarantee that races
don’t result in the PAMT getting freed while another caller requests it
be mapped. But a global lock is a bit heavyweight, especially since the
refcounts can be (already are) updated atomically.

A simple approach would be to increment/decrement the refcount outside of
the lock before actually adjusting the PAMT, and only adjust the PAMT if
the refcount transitions from/to 0. This would correctly allocate and free
the PAMT page without getting out of sync. But there it leaves a race
where a simultaneous caller could see the refcount already incremented and
return before it is actually mapped.

So treat the refcount 0->1 case as a special case. On add, if the refcount
is zero *don’t* increment the refcount outside the lock (to 1). Always
take the lock in that case and only set the refcount to 1 after the PAMT
is actually added. This way simultaneous adders, when PAMT is not
installed yet, will take the slow lock path.

On the 1->0 case, it is ok to return from tdx_pamt_put() when the DPAMT is
not actually freed yet, so the basic approach works. Just decrement the
refcount before  taking the lock. Only do the lock and removal of the PAMT
when the refcount goes to zero.

There is an asymmetry between tdx_pamt_get() and tdx_pamt_put() in that
tdx_pamt_put() goes 1->0 outside the lock, but tdx_pamt_get() does 0-1
inside the lock. Because of this, there is a special race where
tdx_pamt_put() could decrement the refcount to zero before the PAMT is
actually removed, and tdx_pamt_get() could try to do a PAMT.ADD when the
page is already mapped. Luckily the TDX module will tell return a special
error that tells us we hit this case. So handle it specially by looking
for the error code.

The optimization is a little special, so make the code extra commented
and verbose.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Clean up code, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Use atomic_set() in the HPA_RANGE_NOT_FREE case (Kiryl)
 - Log, comment typos (Binbin)
 - Move PAMT page allocation after refcount check in tdx_pamt_get() to
   avoid an alloc/free in the common path.

v3:
 - Split out optimization from “x86/virt/tdx: Add tdx_alloc/free_page() helpers”
 - Remove edge case handling that I could not find a reason for
 - Write log
---
 arch/x86/include/asm/shared/tdx_errno.h |  2 +
 arch/x86/virt/vmx/tdx/tdx.c             | 68 ++++++++++++++++++-------
 2 files changed, 53 insertions(+), 17 deletions(-)

diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index e302aed31b50..acf7197527da 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -21,6 +21,7 @@
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
 #define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
+#define TDX_HPA_RANGE_NOT_FREE			0xC000030400000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
 #define TDX_KEY_STATE_INCORRECT			0xC000081100000000ULL
@@ -94,6 +95,7 @@ DEFINE_TDX_ERRNO_HELPER(TDX_SUCCESS);
 DEFINE_TDX_ERRNO_HELPER(TDX_RND_NO_ENTROPY);
 DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_INVALID);
 DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_BUSY);
+DEFINE_TDX_ERRNO_HELPER(TDX_HPA_RANGE_NOT_FREE);
 DEFINE_TDX_ERRNO_HELPER(TDX_VCPU_NOT_ASSOCIATED);
 DEFINE_TDX_ERRNO_HELPER(TDX_FLUSHVP_NOT_DONE);
 DEFINE_TDX_ERRNO_HELPER(TDX_SW_ERROR);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 745b308785d6..39e2e448c8ba 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2139,21 +2139,28 @@ int tdx_pamt_get(struct page *page)
 	u64 pamt_pa_array[MAX_TDX_ARG_SIZE(rdx)];
 	atomic_t *pamt_refcount;
 	u64 tdx_status;
-	int ret;
+	int ret = 0;
 
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
+	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
+
+	/*
+	 * If the pamt page is already added (i.e. refcount >= 1),
+	 * then just increment the refcount.
+	 */
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
 	ret = alloc_pamt_array(pamt_pa_array);
 	if (ret)
 		goto out_free;
 
-	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
-
 	scoped_guard(spinlock, &pamt_lock) {
 		/*
-		 * If the pamt page is already added (i.e. refcount >= 1),
-		 * then just increment the refcount.
+		 * Lost race to other tdx_pamt_add(). Other task has already allocated
+		 * PAMT memory for the HPA.
 		 */
 		if (atomic_read(pamt_refcount)) {
 			atomic_inc(pamt_refcount);
@@ -2163,12 +2170,29 @@ int tdx_pamt_get(struct page *page)
 		/* Try to add the pamt page and take the refcount 0->1. */
 
 		tdx_status = tdh_phymem_pamt_add(page, pamt_pa_array);
-		if (!IS_TDX_SUCCESS(tdx_status)) {
+		if (IS_TDX_SUCCESS(tdx_status)) {
+			/*
+			 * The refcount is zero, and this locked path is the only way to
+			 * increase it from 0-1. If the PAMT.ADD was successful, set it
+			 * to 1 (obviously).
+			 */
+			atomic_set(pamt_refcount, 1);
+		} else if (IS_TDX_HPA_RANGE_NOT_FREE(tdx_status)) {
+			/*
+			 * Less obviously, another CPU's call to tdx_pamt_put() could have
+			 * decremented the refcount before entering its lock section.
+			 * In this case, the PAMT is not actually removed yet. Luckily
+			 * TDX module tells about this case, so increment the refcount
+			 * 0-1, so tdx_pamt_put() skips its pending PAMT.REMOVE.
+			 *
+			 * The call didn't need the pages though, so free them.
+			 */
+			atomic_set(pamt_refcount, 1);
+			goto out_free;
+		} else {
 			pr_err("TDH_PHYMEM_PAMT_ADD failed: %#llx\n", tdx_status);
 			goto out_free;
 		}
-
-		atomic_inc(pamt_refcount);
 	}
 
 	return ret;
@@ -2197,20 +2221,32 @@ void tdx_pamt_put(struct page *page)
 
 	pamt_refcount = tdx_find_pamt_refcount(page_to_pfn(page));
 
+	/*
+	 * If the there are more than 1 references on the pamt page,
+	 * don't remove it yet. Just decrement the refcount.
+	 *
+	 * Unlike the paired call in tdx_pamt_get(), decrement the refcount
+	 * outside the lock even if it's the special 0<->1 transition. See
+	 * special logic around HPA_RANGE_NOT_FREE in tdx_pamt_get().
+	 */
+	if (!atomic_dec_and_test(pamt_refcount))
+		return;
+
 	scoped_guard(spinlock, &pamt_lock) {
-		/*
-		 * If the there are more than 1 references on the pamt page,
-		 * don't remove it yet. Just decrement the refcount.
-		 */
-		if (atomic_read(pamt_refcount) > 1) {
-			atomic_dec(pamt_refcount);
+		/* Lost race with tdx_pamt_get(). */
+		if (atomic_read(pamt_refcount))
 			return;
-		}
 
 		/* Try to remove the pamt page and take the refcount 1->0. */
 
 		tdx_status = tdh_phymem_pamt_remove(page, pamt_pa_array);
 		if (!IS_TDX_SUCCESS(tdx_status)) {
+			/*
+			 * Since the refcount was optimistically decremented above
+			 * outside the lock, revert it if there is a failure.
+			 */
+			atomic_inc(pamt_refcount);
+
 			pr_err("TDH_PHYMEM_PAMT_REMOVE failed: %#llx\n", tdx_status);
 
 			/*
@@ -2219,8 +2255,6 @@ void tdx_pamt_put(struct page *page)
 			 */
 			return;
 		}
-
-		atomic_dec(pamt_refcount);
 	}
 
 	/*

---

## [10] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 09/16] KVM: TDX: Allocate PAMT memory for TD control structures*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

TDX TD control structures are provided to the TDX module at 4KB page size
and require PAMT backing. This means for Dynamic PAMT they need to also
have 4KB backings installed.

Previous changes introduced tdx_alloc_page()/tdx_free_page() that can
allocate a page and automatically handle the DPAMT maintenance. Use them
for vCPU control structures instead of alloc_page()/__free_page().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v3:
 - Write log. Rename from “KVM: TDX: Allocate PAMT memory in __tdx_td_init()”
---
 arch/x86/kvm/vmx/tdx.c | 16 ++++++----------
 1 file changed, 6 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0eed334176b3..8c4c1221e311 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2398,7 +2398,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	atomic_inc(&nr_configured_hkid);
 
-	tdr_page = alloc_page(GFP_KERNEL);
+	tdr_page = tdx_alloc_page();
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2411,7 +2411,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL);
+		tdcs_pages[i] = tdx_alloc_page();
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2529,10 +2529,8 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 teardown:
 	/* Only free pages not yet added, so start at 'i' */
 	for (; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i]) {
-			__free_page(tdcs_pages[i]);
-			tdcs_pages[i] = NULL;
-		}
+		tdx_free_page(tdcs_pages[i]);
+		tdcs_pages[i] = NULL;
 	}
 	if (!kvm_tdx->td.tdcs_pages)
 		kfree(tdcs_pages);
@@ -2548,15 +2546,13 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 free_tdcs:
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i])
-			__free_page(tdcs_pages[i]);
+		tdx_free_page(tdcs_pages[i]);
 	}
 	kfree(tdcs_pages);
 	kvm_tdx->td.tdcs_pages = NULL;
 
 free_tdr:
-	if (tdr_page)
-		__free_page(tdr_page);
+	tdx_free_page(tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 
 free_hkid:

---

## [11] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 10/16] KVM: TDX: Allocate PAMT memory for vCPU control structures*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

TDX vCPU control structures are provided to the TDX module at 4KB page
size and require PAMT backing. This means for Dynamic PAMT they need to
also have 4KB backings installed.

Previous changes introduced tdx_alloc_page()/tdx_free_page() that can
allocate a page and automatically handle the DPAMT maintenance. Use them
for vCPU control structures instead of alloc_page()/__free_page().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v3:
 - Write log. Reame from “Allocate PAMT memory for TDH.VP.CREATE and
   TDH.VP.ADDCX”.
 - Remove new line damage
---
 arch/x86/kvm/vmx/tdx.c | 12 +++++-------
 1 file changed, 5 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 8c4c1221e311..b6d7f4b5f40f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2882,7 +2882,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL);
+	page = tdx_alloc_page();
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2902,7 +2902,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL);
+		page = tdx_alloc_page();
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;
@@ -2924,7 +2924,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 			 * method, but the rest are freed here.
 			 */
 			for (; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-				__free_page(tdx->vp.tdcx_pages[i]);
+				tdx_free_page(tdx->vp.tdcx_pages[i]);
 				tdx->vp.tdcx_pages[i] = NULL;
 			}
 			return -EIO;
@@ -2952,16 +2952,14 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 
 free_tdcx:
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		if (tdx->vp.tdcx_pages[i])
-			__free_page(tdx->vp.tdcx_pages[i]);
+		tdx_free_page(tdx->vp.tdcx_pages[i]);
 		tdx->vp.tdcx_pages[i] = NULL;
 	}
 	kfree(tdx->vp.tdcx_pages);
 	tdx->vp.tdcx_pages = NULL;
 
 free_tdvpr:
-	if (tdx->vp.tdvpr_page)
-		__free_page(tdx->vp.tdvpr_page);
+	tdx_free_page(tdx->vp.tdvpr_page);
 	tdx->vp.tdvpr_page = NULL;
 	tdx->vp.tdvpr_pa = 0;

---

## [12] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

Move mmu_external_spt_cache behind x86 ops.

In the mirror/external MMU concept, the KVM MMU manages a non-active EPT
tree for private memory (the mirror). The actual active EPT tree the
private memory is protected inside the TDX module. Whenever the mirror EPT
is changed, it needs to call out into one of a set of x86 opts that
implement various update operation with TDX specific SEAMCALLs and other
tricks. These implementations operate on the TDX S-EPT (the external).

In reality these external operations are designed narrowly with respect to
TDX particulars. On the surface, what TDX specific things are happening to
fulfill these update operations are mostly hidden from the MMU, but there
is one particular area of interest where some details leak through.

The S-EPT needs pages to use for the S-EPT page tables. These page tables
need to be allocated before taking the mmu lock, like all the rest. So the
KVM MMU pre-allocates pages for TDX to use for the S-EPT in the same place
where it pre-allocates the other page tables. It’s not too bad and fits
nicely with the others.

However, Dynamic PAMT will need even more pages for the same operations.
Further, these pages will need to be handed to the arch/x86 side which used
them for DPAMT updates, which is hard for the existing KVM based cache.
The details living in core MMU code start to add up.

So in preparation to make it more complicated, move the external page
table cache into TDX code by putting it behind some x86 ops. Have one for
topping up and one for allocation. Don’t go so far to try to hide the
existence of external page tables completely from the generic MMU, as they
are currently stored in their mirror struct kvm_mmu_page and it’s quite
handy.

To plumb the memory cache operations through tdx.c, export some of
the functions temporarily. This will be removed in future changes.

Acked-by: Kiryl Shutsemau <kas@kernel.org>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Add Kiryl ack
 - Log typo (Binbin)
 - Add pages arg to topup_external_fault_cache() (Yan)
 - After more consideration, create free_external_fault_cache()
   as suggest by (Yan)

v3:
 - New patch
---
 arch/x86/include/asm/kvm-x86-ops.h |  3 +++
 arch/x86/include/asm/kvm_host.h    | 14 +++++++++-----
 arch/x86/kvm/mmu/mmu.c             |  6 +++---
 arch/x86/kvm/mmu/mmu_internal.h    |  2 +-
 arch/x86/kvm/vmx/tdx.c             | 24 ++++++++++++++++++++++++
 arch/x86/kvm/vmx/tdx.h             |  2 ++
 virt/kvm/kvm_main.c                |  3 +++
 7 files changed, 45 insertions(+), 9 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index de709fb5bd76..58c5c9b082ca 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -98,6 +98,9 @@ KVM_X86_OP_OPTIONAL(link_external_spt)
 KVM_X86_OP_OPTIONAL(set_external_spte)
 KVM_X86_OP_OPTIONAL(free_external_spt)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
+KVM_X86_OP_OPTIONAL(alloc_external_fault_cache)
+KVM_X86_OP_OPTIONAL(topup_external_fault_cache)
+KVM_X86_OP_OPTIONAL(free_external_fault_cache)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 8d8cc059fed6..dde94b84610c 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -855,11 +855,6 @@ struct kvm_vcpu_arch {
 	struct kvm_mmu_memory_cache mmu_shadow_page_cache;
 	struct kvm_mmu_memory_cache mmu_shadowed_info_cache;
 	struct kvm_mmu_memory_cache mmu_page_header_cache;
-	/*
-	 * This cache is to allocate external page table. E.g. private EPT used
-	 * by the TDX module.
-	 */
-	struct kvm_mmu_memory_cache mmu_external_spt_cache;
 
 	/*
 	 * QEMU userspace and the guest each have their own FPU state.
@@ -1856,6 +1851,15 @@ struct kvm_x86_ops {
 	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				     u64 mirror_spte);
 
+	/* Allocation a pages from the external page cache. */
+	void *(*alloc_external_fault_cache)(struct kvm_vcpu *vcpu);
+
+	/* Top up extra pages needed for faulting in external page tables. */
+	int (*topup_external_fault_cache)(struct kvm_vcpu *vcpu, unsigned int cnt);
+
+	/* Free in external page fault cache. */
+	void (*free_external_fault_cache)(struct kvm_vcpu *vcpu);
+
 	bool (*has_wbinvd_exit)(void);
 
 	u64 (*get_l2_tsc_offset)(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 3cfabfbdd843..3b1b91fd37dd 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -601,8 +601,7 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 	if (r)
 		return r;
 	if (kvm_has_mirrored_tdp(vcpu->kvm)) {
-		r = kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_external_spt_cache,
-					       PT64_ROOT_MAX_LEVEL);
+		r = kvm_x86_call(topup_external_fault_cache)(vcpu, PT64_ROOT_MAX_LEVEL);
 		if (r)
 			return r;
 	}
@@ -625,8 +624,9 @@ static void mmu_free_memory_caches(struct kvm_vcpu *vcpu)
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_pte_list_desc_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadow_page_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadowed_info_cache);
-	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_external_spt_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_page_header_cache);
+	if (kvm_has_mirrored_tdp(vcpu->kvm))
+		kvm_x86_call(free_external_fault_cache)(vcpu);
 }
 
 static void mmu_free_pte_list_desc(struct pte_list_desc *pte_list_desc)
diff --git a/arch/x86/kvm/mmu/mmu_internal.h b/arch/x86/kvm/mmu/mmu_internal.h
index 73cdcbccc89e..12234ee468ce 100644
--- a/arch/x86/kvm/mmu/mmu_internal.h
+++ b/arch/x86/kvm/mmu/mmu_internal.h
@@ -165,7 +165,7 @@ static inline void kvm_mmu_alloc_external_spt(struct kvm_vcpu *vcpu, struct kvm_
 	 * Therefore, KVM does not need to initialize or access external_spt.
 	 * KVM only interacts with sp->spt for private EPT operations.
 	 */
-	sp->external_spt = kvm_mmu_memory_cache_alloc(&vcpu->arch.mmu_external_spt_cache);
+	sp->external_spt = kvm_x86_call(alloc_external_fault_cache)(vcpu);
 }
 
 static inline gfn_t kvm_gfn_root_bits(const struct kvm *kvm, const struct kvm_mmu_page *root)
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index b6d7f4b5f40f..260bb0e6eb44 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1642,6 +1642,27 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 	return 0;
 }
 
+static void *tdx_alloc_external_fault_cache(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+
+	return kvm_mmu_memory_cache_alloc(&tdx->mmu_external_spt_cache);
+}
+
+static int tdx_topup_external_fault_cache(struct kvm_vcpu *vcpu, unsigned int cnt)
+{
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+
+	return kvm_mmu_topup_memory_cache(&tdx->mmu_external_spt_cache, cnt);
+}
+
+static void tdx_free_external_fault_cache(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+
+	kvm_mmu_free_memory_cache(&tdx->mmu_external_spt_cache);
+}
+
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 			    enum pg_level level, kvm_pfn_t pfn)
 {
@@ -3602,4 +3623,7 @@ void __init tdx_hardware_setup(void)
 	vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
 	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;
 	vt_x86_ops.protected_apic_has_interrupt = tdx_protected_apic_has_interrupt;
+	vt_x86_ops.alloc_external_fault_cache = tdx_alloc_external_fault_cache;
+	vt_x86_ops.topup_external_fault_cache = tdx_topup_external_fault_cache;
+	vt_x86_ops.free_external_fault_cache = tdx_free_external_fault_cache;
 }
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ce2720a028ad..1eefa1b0df5e 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -73,6 +73,8 @@ struct vcpu_tdx {
 
 	u64 map_gpa_next;
 	u64 map_gpa_end;
+
+	struct kvm_mmu_memory_cache mmu_external_spt_cache;
 };
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err);
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 9eca084bdcbe..cff24b950baa 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -404,6 +404,7 @@ int kvm_mmu_topup_memory_cache(struct kvm_mmu_memory_cache *mc, int min)
 {
 	return __kvm_mmu_topup_memory_cache(mc, KVM_ARCH_NR_OBJS_PER_MEMORY_CACHE, min);
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_topup_memory_cache);
 
 int kvm_mmu_memory_cache_nr_free_objects(struct kvm_mmu_memory_cache *mc)
 {
@@ -424,6 +425,7 @@ void kvm_mmu_free_memory_cache(struct kvm_mmu_memory_cache *mc)
 	mc->objects = NULL;
 	mc->capacity = 0;
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_free_memory_cache);
 
 void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 {
@@ -436,6 +438,7 @@ void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 	BUG_ON(!p);
 	return p;
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_memory_cache_alloc);
 #endif
 
 static void kvm_vcpu_init(struct kvm_vcpu *vcpu, struct kvm *kvm, unsigned id)

---

## [13] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for pre-allocating pages*

In the KVM fault path page, tables and private pages need to be
installed under a spin lock. This means that the operations around
installing PAMT pages for them will not be able to allocate pages.

Create a small structure to allow passing a list of pre-allocated pages
that PAMT operations can use. Have the structure keep a count such that
it can be stored on KVM's vCPU structure, and "topped up" for each fault.
This is consistent with how KVM manages similar caches and will fit better
than allocating and freeing all possible needed pages each time.

Adding this structure duplicates a fancier one that lives in KVM 'struct
kvm_mmu_memory_cache'. While the struct itself is easy to expose, the
functions that operate on it are a bit big to put in a header, which
would be needed to use them from the core kernel. So don't pursue this
option.

To avoid the problem of needing the kernel to link to functionality in
KVM, a function pointer could be passed, however this makes the code
convoluted, when what is needed is barely more than a linked list. So
create a tiny, simpler version of KVM's kvm_mmu_memory_cache to use for
PAMT pages.

Don't use mempool_t for this because there is no appropriate topup
mechanism. The mempool_resize() operation is the closest, but it
reallocates an array each time. It also does not have a way to pass
GFP_KERNEL_ACCOUNT to page allocations during resize. So it would need to
be amended, and the problems that caused GFP_KERNEL_ACCOUNT to be
prevented in that operation dealt with. The other option would be simply
allocate pages from TDX code and free them to the pool in order to
implement the top up operation, but this is not really any savings over
the simple linked list.

Allocate the pages as GFP_KERNEL_ACCOUNT based on that the allocations
will be easily user triggerable, and for the future huge pages case (which
advanced cgroups caring setups are likely to use), will also mostly be
associated with the specific TD. So better to be GFP_KERNEL_ACCOUNT,
despite the fact that sometimes the pages may later on only be backing
some other cgroup’s TD memory.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Change to GFP_KERNEL_ACCOUNT to match replaced kvm_mmu_memory_cache
 - Add GFP_ATOMIC backup, like kvm_mmu_memory_cache has (Kiryl)
 - Explain why not to use mempool (Dave)
 - Tweak local vars to be more reverse christmas tree by deleting some
   that were only added for reasons that go away in this patch anyway
---
 arch/x86/include/asm/tdx.h  | 43 ++++++++++++++++++++++++++++++++++++-
 arch/x86/kvm/vmx/tdx.c      | 21 +++++++++++++-----
 arch/x86/kvm/vmx/tdx.h      |  2 +-
 arch/x86/virt/vmx/tdx/tdx.c | 22 +++++++++++++------
 virt/kvm/kvm_main.c         |  3 ---
 5 files changed, 75 insertions(+), 16 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 914213123d94..416ca9a738ee 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -17,6 +17,7 @@
 #include <uapi/asm/mce.h>
 #include <asm/tdx_global_metadata.h>
 #include <linux/pgtable.h>
+#include <linux/memory.h>
 
 /*
  * Used by the #VE exception handler to gather the #VE exception
@@ -141,7 +142,46 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
-int tdx_pamt_get(struct page *page);
+int tdx_dpamt_entry_pages(void);
+
+/*
+ * Simple structure for pre-allocating Dynamic
+ * PAMT pages outside of locks.
+ */
+struct tdx_prealloc {
+	struct list_head page_list;
+	int cnt;
+};
+
+static inline struct page *get_tdx_prealloc_page(struct tdx_prealloc *prealloc)
+{
+	struct page *page;
+
+	page = list_first_entry_or_null(&prealloc->page_list, struct page, lru);
+	if (page) {
+		list_del(&page->lru);
+		prealloc->cnt--;
+	}
+
+	return page;
+}
+
+static inline int topup_tdx_prealloc_page(struct tdx_prealloc *prealloc, unsigned int min_size)
+{
+	while (prealloc->cnt < min_size) {
+		struct page *page = alloc_page(GFP_KERNEL_ACCOUNT);
+
+		if (!page)
+			return -ENOMEM;
+
+		list_add(&page->lru, &prealloc->page_list);
+		prealloc->cnt++;
+	}
+
+	return 0;
+}
+
+int tdx_pamt_get(struct page *page, struct tdx_prealloc *prealloc);
 void tdx_pamt_put(struct page *page);
 
 struct page *tdx_alloc_page(void);
@@ -219,6 +259,7 @@ static inline int tdx_enable(void)  { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
+static inline int tdx_dpamt_entry_pages(void) { return 0; }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #ifdef CONFIG_KEXEC_CORE
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 260bb0e6eb44..61a058a8f159 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1644,23 +1644,34 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 
 static void *tdx_alloc_external_fault_cache(struct kvm_vcpu *vcpu)
 {
-	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct page *page = get_tdx_prealloc_page(&to_tdx(vcpu)->prealloc);
 
-	return kvm_mmu_memory_cache_alloc(&tdx->mmu_external_spt_cache);
+	if (WARN_ON_ONCE(!page))
+		return (void *)__get_free_page(GFP_ATOMIC | __GFP_ACCOUNT);
+
+	return page_address(page);
 }
 
 static int tdx_topup_external_fault_cache(struct kvm_vcpu *vcpu, unsigned int cnt)
 {
-	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct tdx_prealloc *prealloc = &to_tdx(vcpu)->prealloc;
+	int min_fault_cache_size;
 
-	return kvm_mmu_topup_memory_cache(&tdx->mmu_external_spt_cache, cnt);
+	/* External page tables */
+	min_fault_cache_size = cnt;
+	/* Dynamic PAMT pages (if enabled) */
+	min_fault_cache_size += tdx_dpamt_entry_pages() * PT64_ROOT_MAX_LEVEL;
+
+	return topup_tdx_prealloc_page(prealloc, min_fault_cache_size);
 }
 
 static void tdx_free_external_fault_cache(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct page *page;
 
-	kvm_mmu_free_memory_cache(&tdx->mmu_external_spt_cache);
+	while ((page = get_tdx_prealloc_page(&tdx->prealloc)))
+		__free_page(page);
 }
 
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index 1eefa1b0df5e..43dd295b7fd6 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -74,7 +74,7 @@ struct vcpu_tdx {
 	u64 map_gpa_next;
 	u64 map_gpa_end;
 
-	struct kvm_mmu_memory_cache mmu_external_spt_cache;
+	struct tdx_prealloc prealloc;
 };
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 39e2e448c8ba..74b0342b7570 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2010,13 +2010,23 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
 
 /* Number PAMT pages to be provided to TDX module per 2M region of PA */
-static int tdx_dpamt_entry_pages(void)
+int tdx_dpamt_entry_pages(void)
 {
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
 	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
 }
+EXPORT_SYMBOL_GPL(tdx_dpamt_entry_pages);
+
+static struct page *alloc_dpamt_page(struct tdx_prealloc *prealloc)
+{
+	if (prealloc)
+		return get_tdx_prealloc_page(prealloc);
+
+	return alloc_page(GFP_KERNEL_ACCOUNT);
+}
+
 
 /*
  * The TDX spec treats the registers like an array, as they are ordered
@@ -2040,13 +2050,13 @@ static u64 *dpamt_args_array_ptr(struct tdx_module_array_args *args)
 	return &args->args_array[TDX_ARG_INDEX(rdx)];
 }
 
-static int alloc_pamt_array(u64 *pa_array)
+static int alloc_pamt_array(u64 *pa_array, struct tdx_prealloc *prealloc)
 {
 	struct page *page;
 	int i;
 
 	for (i = 0; i < tdx_dpamt_entry_pages(); i++) {
-		page = alloc_page(GFP_KERNEL_ACCOUNT);
+		page = alloc_dpamt_page(prealloc);
 		if (!page)
 			goto err;
 		pa_array[i] = page_to_phys(page);
@@ -2134,7 +2144,7 @@ static u64 tdh_phymem_pamt_remove(struct page *page, u64 *pamt_pa_array)
 static DEFINE_SPINLOCK(pamt_lock);
 
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
-int tdx_pamt_get(struct page *page)
+int tdx_pamt_get(struct page *page, struct tdx_prealloc *prealloc)
 {
 	u64 pamt_pa_array[MAX_TDX_ARG_SIZE(rdx)];
 	atomic_t *pamt_refcount;
@@ -2153,7 +2163,7 @@ int tdx_pamt_get(struct page *page)
 	if (atomic_inc_not_zero(pamt_refcount))
 		return 0;
 
-	ret = alloc_pamt_array(pamt_pa_array);
+	ret = alloc_pamt_array(pamt_pa_array, prealloc);
 	if (ret)
 		goto out_free;
 
@@ -2278,7 +2288,7 @@ struct page *tdx_alloc_page(void)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page)) {
+	if (tdx_pamt_get(page, NULL)) {
 		__free_page(page);
 		return NULL;
 	}
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index cff24b950baa..9eca084bdcbe 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -404,7 +404,6 @@ int kvm_mmu_topup_memory_cache(struct kvm_mmu_memory_cache *mc, int min)
 {
 	return __kvm_mmu_topup_memory_cache(mc, KVM_ARCH_NR_OBJS_PER_MEMORY_CACHE, min);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_topup_memory_cache);
 
 int kvm_mmu_memory_cache_nr_free_objects(struct kvm_mmu_memory_cache *mc)
 {
@@ -425,7 +424,6 @@ void kvm_mmu_free_memory_cache(struct kvm_mmu_memory_cache *mc)
 	mc->objects = NULL;
 	mc->capacity = 0;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_free_memory_cache);
 
 void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 {
@@ -438,7 +436,6 @@ void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 	BUG_ON(!p);
 	return p;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_memory_cache_alloc);
 #endif
 
 static void kvm_vcpu_init(struct kvm_vcpu *vcpu, struct kvm *kvm, unsigned id)

---

## [14] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 13/16] KVM: TDX: Handle PAMT allocation in fault path*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Install PAMT pages for TDX call backs called during the fault path.

There are two distinct cases when the kernel needs to allocate PAMT memory
in the fault path: for SEPT page tables in tdx_sept_link_private_spt() and
for leaf pages in tdx_sept_set_private_spte().

These code paths run in atomic context. Previous changes have made the
fault path top up the per-VCPU pool for memory allocations. Use it to do
tdx_pamt_get/put() for the fault path operations.

In the generic MMU these ops are inside functions that don’t always
operate from the vCPU contexts (for example zap paths), which means they
don’t have a struct kvm_vcpu handy. But for TDX they are always in a vCPU
context. Since the pool of pre-allocated pages is on the vCPU, use
kvm_get_running_vcpu() to get the vCPU. In case a new path appears where
this is not the  case, leave some KVM_BUG_ON()’s.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Do prealloc.page_list initialization in tdx_td_vcpu_init() in case
   userspace doesn't call KVM_TDX_INIT_VCPU.

v3:
 - Use new pre-allocation method
 - Updated log
 - Some extra safety around kvm_get_running_vcpu()
---
 arch/x86/kvm/vmx/tdx.c | 44 ++++++++++++++++++++++++++++++++++++------
 1 file changed, 38 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 61a058a8f159..24322263ac27 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -683,6 +683,8 @@ int tdx_vcpu_create(struct kvm_vcpu *vcpu)
 	if (!irqchip_split(vcpu->kvm))
 		return -EINVAL;
 
+	INIT_LIST_HEAD(&tdx->prealloc.page_list);
+
 	fpstate_set_confidential(&vcpu->arch.guest_fpu);
 	vcpu->arch.apic->guest_apic_protected = true;
 	INIT_LIST_HEAD(&tdx->vt.pi_wakeup_list);
@@ -1698,8 +1700,15 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, u64 mirror_spte)
 {
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct page *page = pfn_to_page(pfn);
+	int ret;
+
+	if (KVM_BUG_ON(!vcpu, kvm))
+		return -EINVAL;
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
@@ -1708,6 +1717,10 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	WARN_ON_ONCE(!is_shadow_present_pte(mirror_spte) ||
 		     (mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
+	ret = tdx_pamt_get(page, &tdx->prealloc);
+	if (ret)
+		return ret;
+
 	/*
 	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()
 	 * before kvm_tdx->state.  Userspace must not be allowed to pre-fault
@@ -1720,27 +1733,46 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * If the TD isn't finalized/runnable, then userspace is initializing
 	 * the VM image via KVM_TDX_INIT_MEM_REGION; ADD the page to the TD.
 	 */
-	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
-		return tdx_mem_page_add(kvm, gfn, level, pfn);
+	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
+		ret = tdx_mem_page_aug(kvm, gfn, level, pfn);
+	else
+		ret = tdx_mem_page_add(kvm, gfn, level, pfn);
 
-	return tdx_mem_page_aug(kvm, gfn, level, pfn);
+	if (ret)
+		tdx_pamt_put(page);
+
+	return ret;
 }
 
 static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, void *private_spt)
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
-	gpa_t gpa = gfn_to_gpa(gfn);
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct page *page = virt_to_page(private_spt);
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
+	int ret;
+
+	if (KVM_BUG_ON(!vcpu, kvm))
+		return -EINVAL;
+
+	ret = tdx_pamt_get(page, &tdx->prealloc);
+	if (ret)
+		return ret;
 
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level, page, &entry,
 			       &level_state);
-	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(err))) {
+		tdx_pamt_put(page);
 		return -EBUSY;
+	}
 
-	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
+	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm)) {
+		tdx_pamt_put(page);
 		return -EIO;
+	}
 
 	return 0;
 }

---

## [15] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 14/16] KVM: TDX: Reclaim PAMT memory*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Call tdx_free_page() and tdx_pamt_put() on the paths that free TDX
pages.

The PAMT memory holds metadata for TDX-protected memory. With Dynamic
PAMT, PAMT_4K is allocated on demand. The kernel supplies the TDX module
with a few pages that cover 2M of host physical memory.

PAMT memory can be reclaimed when the last user is gone. It can happen
in a few code paths:

- On TDH.PHYMEM.PAGE.RECLAIM in tdx_reclaim_td_control_pages() and
  tdx_reclaim_page().

- On TDH.MEM.PAGE.REMOVE in tdx_sept_drop_private_spte().

- In tdx_sept_zap_private_spte() for pages that were in the queue to be
  added with TDH.MEM.PAGE.ADD, but it never happened due to an error.

- In tdx_sept_free_private_spt() for SEPT pages;

Add tdx_pamt_put() for memory that comes from guest_memfd and use
tdx_free_page() for the rest.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Minor log tweak]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v4:
 - Rebasing on post-populate series required some changes on how PAMT
   refcounting was handled in the KVM_TDX_INIT_MEM_REGION path. Now
   instead of incrementing DPAMT refcount on the fake add in the fault
   path, it only increments it when tdh_mem_page_add() actually succeeds,
   like in tdx_mem_page_aug(). Because of this, the special handling for
   the case tdx_is_sept_zap_err_due_to_premap() cared about is unneeded.

v3:
 - Minor log tweak to conform kvm/x86 style.
---
 arch/x86/kvm/vmx/tdx.c | 14 +++++++++++---
 1 file changed, 11 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 24322263ac27..f8de50e7dc7f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -360,7 +360,7 @@ static void tdx_reclaim_control_page(struct page *ctrl_page)
 	if (tdx_reclaim_page(ctrl_page))
 		return;
 
-	__free_page(ctrl_page);
+	tdx_free_page(ctrl_page);
 }
 
 struct tdx_flush_vp_arg {
@@ -597,7 +597,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 
 	tdx_quirk_reset_page(kvm_tdx->td.tdr_page);
 
-	__free_page(kvm_tdx->td.tdr_page);
+	tdx_free_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 }
 
@@ -1827,6 +1827,8 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, void *private_spt)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct page *page = virt_to_page(private_spt);
+	int ret;
 
 	/*
 	 * free_external_spt() is only called after hkid is freed when TD is
@@ -1843,7 +1845,12 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 	 * The HKID assigned to this TD was already freed and cache was
 	 * already flushed. We don't have to flush again.
 	 */
-	return tdx_reclaim_page(virt_to_page(private_spt));
+	ret = tdx_reclaim_page(virt_to_page(private_spt));
+	if (ret)
+		return ret;
+
+	tdx_pamt_put(page);
+	return 0;
 }
 
 static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
@@ -1895,6 +1902,7 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 		return;
 
 	tdx_quirk_reset_page(page);
+	tdx_pamt_put(page);
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,

---

## [16] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 15/16] x86/virt/tdx: Enable Dynamic PAMT*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The Physical Address Metadata Table (PAMT) holds TDX metadata for
physical memory and must be allocated by the kernel during TDX module
initialization.

The exact size of the required PAMT memory is determined by the TDX
module and may vary between TDX module versions, but currently it is
approximately 0.4% of the system memory. This is a significant
commitment, especially if it is not known upfront whether the machine
will run any TDX guests.

The Dynamic PAMT feature reduces static PAMT allocations. PAMT_1G and
PAMT_2M levels are still allocated on TDX module initialization, but the
PAMT_4K level is allocated dynamically, reducing static allocations to
approximately 0.004% of the system memory.

All pieces are in place. Enable Dynamic PAMT if it is supported.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/tdx.h  | 6 +++++-
 arch/x86/virt/vmx/tdx/tdx.c | 8 ++++++++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 3 files changed, 13 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 416ca9a738ee..0ccd0e0e0df7 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -12,6 +12,10 @@
 #include <asm/trapnr.h>
 #include <asm/shared/tdx.h>
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD		BIT_ULL(18)
+#define TDX_FEATURES0_DYNAMIC_PAMT		BIT_ULL(36)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -133,7 +137,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT;
 }
 
 void tdx_quirk_reset_page(struct page *page);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 74b0342b7570..144e62303aa3 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1067,6 +1067,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
+#define TDX_SYS_CONFIG_DYNAMIC_PAMT	BIT(16)
+
 static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
@@ -1094,6 +1096,12 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
+
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		pr_info("Enable Dynamic PAMT\n");
+		args.r8 |= TDX_SYS_CONFIG_DYNAMIC_PAMT;
+	}
+
 	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
 
 	/* Free the array as it is not required anymore. */
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 46c4214b79fb..096c78a1d438 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -86,9 +86,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [17] Rick Edgecombe — 2025-11-20
*Subject: [PATCH v4 16/16] Documentation/x86: Add documentation for TDX's Dynamic PAMT*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Expand TDX documentation to include information on the Dynamic PAMT
feature.

The new section explains PAMT support in the TDX module and how Dynamic
PAMT affects the kernel memory use.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v3:
 - Trim down docs to be about things that user cares about, instead
   of development history and other details like this.
---
 Documentation/arch/x86/tdx.rst | 21 +++++++++++++++++++++
 1 file changed, 21 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 61670e7df2f7..8d45d31fee29 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -99,6 +99,27 @@ initialize::
 
   [..] virt/tdx: module initialization failed ...
 
+Dynamic PAMT
+------------
+
+PAMT is memory that the TDX module needs to keep data about each page
+(think like struct page). It needs to handed to the TDX module for its
+exclusive use. For normal PAMT, this is installed when the TDX module
+is first loaded and comes to about 0.4% of system memory.
+
+Dynamic PAMT is a TDX feature that allows VMM to allocate part of the
+PAMT as needed (the parts for tracking 4KB size pages). The other page
+sizes (1GB and 2MB) are still allocated statically at the time of
+TDX module initialization. This reduces the amount of memory that TDX
+uses while TDs are not in use.
+
+When Dynamic PAMT is in use, dmesg shows it like:
+  [..] virt/tdx: Enable Dynamic PAMT
+  [..] virt/tdx: 10092 KB allocated for PAMT
+  [..] virt/tdx: module initialized
+
+Dynamic PAMT is enabled automatically if supported.
+
 TDX Interaction to Other Kernel Components
 ------------------------------------------

---

## [18] Binbin Wu — 2025-11-24
*Subject: Re: [PATCH v4 02/16] x86/tdx: Add helpers to check return status
 codes*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
[...]
>
> diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c

After the changes in tdx_mcall_get_report0() and tdx_mcall_extend_rtmr(), the
macros defined in arch/x86/coco/tdx/tdx.c can be removed:

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..f72b7dfdacd1 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -33,11 +33,6 @@
  #define VE_GET_PORT_NUM(e)     ((e) >> 16)
  #define VE_IS_IO_STRING(e)     ((e) & BIT(4))

-/* TDX Module call error codes */
-#define TDCALL_RETURN_CODE(a)  ((a) >> 32)
-#define TDCALL_INVALID_OPERAND 0xc0000100
-#define TDCALL_OPERAND_BUSY    0x80000200
-
  #define TDREPORT_SUBTYPE_0     0

  static atomic_long_t nr_shared;

>   			return -EBUSY;
>   		return -EIO;

Should be tagged with __always_inline since it's used in noinstr range.

[...]

---

## [19] Binbin Wu — 2025-11-24
*Subject: Re: [PATCH v4 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> For each memory region that the TDX module might use (TDMR), the three
> separate PAMT allocations are needed. One for each supported page size

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One nit below.

[...]
> @@ -535,26 +518,18 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
>   	 * in overlapped TDMRs.
Nit:
Do you think it's OK to move the comment up so to avoid multiple lines of
comments as well as the curly braces?

         /* tdmr->pamt_4k_base is zero so the error path will skip freeing. */
         if (!pamt)
             return -ENOMEM;

> -
> -	/*
[...]

---

## [20] Edgecombe, Rick P — 2025-11-24
*Subject: Re: [PATCH v4 02/16] x86/tdx: Add helpers to check return status
 codes*

On Mon, 2025-11-24 at 16:56 +0800, Binbin Wu wrote:
> > +static inline u64 TDX_STATUS(u64 err)
> > +{

Nice, catch. Yes both should be done.

---

## [21] Edgecombe, Rick P — 2025-11-24
*Subject: Re: [PATCH v4 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

On Mon, 2025-11-24 at 17:26 +0800, Binbin Wu wrote:
> Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

Thanks.

> 
> One nit below.

Yea, I think that is a good point. But I'm also thinking that this comment is
not clear enough. There is no error path to speak of in this function, so maybe:

	/*
	 * tdmr->pamt_4k_base is still zero so the error 
	 * path of the caller will skip freeing the pamt.
	 */

If you agree I will keep your RB.

> 
>          /* tdmr->pamt_4k_base is zero so the error path will skip freeing. */

---

## [22] Sagi Shahar — 2025-11-24
*Subject: Re: [PATCH v4 00/16] TDX: Enable Dynamic PAMT*

On Thu, Nov 20, 2025 at 6:51 PM Rick Edgecombe
<rick.p.edgecombe@intel.com> wrote:
>
> Hi,

Tested-by: Sagi Shahar <sagis@google.com>

---

## [23] Binbin Wu — 2025-11-25
*Subject: Re: [PATCH v4 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

On 11/25/2025 3:47 AM, Edgecombe, Rick P wrote:
> On Mon, 2025-11-24 at 17:26 +0800, Binbin Wu wrote:
>> Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Yes, please.

>>           /* tdmr->pamt_4k_base is zero so the error path will skip freeing. */
>>           if (!pamt)

---

## [24] Binbin Wu — 2025-11-25
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One nit below.

[...]
> diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
> index 13ad2663488b..00ab0e550636 100644

A bit weird to say "if tdx_supports_dynamic_pamt() isn't supported", how about
using "if dynamic PAMT isn't supported"?

> +	 * TDX code can fallback to normal PAMT if it's not supported.
> +	 */

---

## [25] Binbin Wu — 2025-11-25
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
[...]
> +
> +/* Unmap a page from the PAMT refcount vmalloc region */

Not sure this comment about "sparse" is accurate since this function is called via
apply_to_existing_page_range().

And the check for not present just for sanity check?
> +	if (!pte_none(entry)) {
> +		pte_clear(&init_mm, addr, pte);

---

## [26] Binbin Wu — 2025-11-25
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
[...]
>   
> +/* Number PAMT pages to be provided to TDX module per 2M region of PA */
           ^                                             ^
           of                                           2MB
> +static int tdx_dpamt_entry_pages(void)
> +{

This should be the maximum number of registers could be used to pass the
addresses of the pages (or other information), it needs to be divided by sizeof(u64).

Also, "SIZE" in the name could be confusing.

> +#define TDX_ARG_INDEX(reg) (offsetof(struct tdx_module_args, reg) / \
> +			    sizeof(u64))
sanitychecks -> sanity checks

> + */
[...]
> +/* Serializes adding/removing PAMT memory */
> +static DEFINE_SPINLOCK(pamt_lock);

So far, all atomic operations are inside the spinlock.
May be better to add some info in the change log that atomic is needed due to
the optimization in the later patch?

> +			goto out_free;
> +		}

Can use pr_tdx_error().

Aslo, so for in this patch, when this SEAMCALL failed, does it indicate a bug?

> +			goto out_free;
> +		}

Maybe just return 0 here since all error paths must be directed to out_free.

> +out_free:
> +	/*
[...]

---

## [27] Binbin Wu — 2025-11-25
*Subject: Re: [PATCH v4 09/16] KVM: TDX: Allocate PAMT memory for TD control
 structures*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>

vCPU -> TD

>
> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
One typo above.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
> v3:

---

## [28] Binbin Wu — 2025-11-25
*Subject: Re: [PATCH v4 10/16] KVM: TDX: Allocate PAMT memory for vCPU control
 structures*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
> v3:

---

## [29] Vishal Annapurve — 2025-11-25
*Subject: Re: [PATCH v4 00/16] TDX: Enable Dynamic PAMT*

On Thu, Nov 20, 2025 at 4:51 PM Rick Edgecombe
<rick.p.edgecombe@intel.com> wrote:
>
> Hi,

acked-by: Vishal Annapurve <vannapurve@google.com>.

---

## [30] Huang, Kai — 2025-11-25
*Subject: Re: [PATCH v4 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

> --- a/arch/x86/kvm/vmx/tdx_errno.h
> +++ b/arch/x86/include/asm/shared/tdx_errno.h

AFAICT other files under asm/shared/ all use

  #ifdef  _ASM_X86_SHARED_xx_H
  ...

I guess it's better to follow this pattern.

>  
> -#ifndef __KVM_X86_TDX_ERRNO_H

Nit:

I don't quite follow this change.  Just curious: is it because "returned in RAX"
doesn't apply to all error codes any more?

>   */
> +#define TDX_SUCCESS				0ULL

I think you can remove <asm/trapnr.h> here since now <asm/tdx.h> is no longer
using any definitions from it.  And <asm/shared/tdx_errno.h> now includes it
directly.

---

## [31] Huang, Kai — 2025-11-25
*Subject: Re: [PATCH v4 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Tue, 2025-11-25 at 22:30 +0000, Huang, Kai wrote:
> >   /*
> > - * TDX SEAMCALL Status Codes (returned in RAX)

Also forgot to say, AFAICT these error codes will also be used by TDX guest,
therefore you might want to drop the "SEAMCALL" part from the status codes.

> 
> >    */

---

## [32] Huang, Kai — 2025-11-25
*Subject: Re: [PATCH v4 02/16] x86/tdx: Add helpers to check return status
 codes*

On Thu, 2025-11-20 at 16:51 -0800, Rick Edgecombe wrote:
> diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
> index 3aa74f6a6119..e302aed31b50 100644

IMHO:

You might want to move #include <linux/bits.h> out of __ASSEMBLER__ to the top
of this file since macros like GENMASK_ULL() are used by SW-defined error codes
already.  And you might want to move the inclusion of this header to the
previous patch when these error codes were moved to <asm/shared/tdx_errno.h>.

You may also move <linux/types.h> out of __ASSEMBLER__ since AFAICT this file is
assembly inclusion safe.

> +
> +static inline u64 TDX_STATUS(u64 err)

---

## [33] Huang, Kai — 2025-11-26
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, 2025-11-20 at 16:51 -0800, Rick Edgecombe wrote:
> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
> index cf51ccd16194..914213123d94 100644

I don't think it's mandatory to move the declaration of tdx_quirk_reset_page()?

---

## [34] Binbin Wu — 2025-11-26
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> In the KVM fault path page, tables and private pages need to be
"In the KVM fault path page, tables ..." should be
"In the KVM fault path, page tables ..."

> installed under a spin lock. This means that the operations around
> installing PAMT pages for them will not be able to allocate pages.
[...]
> @@ -141,7 +142,46 @@ int tdx_guest_keyid_alloc(void);
>   u32 tdx_get_nr_guest_keyids(void);

It's not just for Dynamic PAMT pages, but also external page table pages.

> + */
> +struct tdx_prealloc {

kvm_mmu_memory_cache_alloc() calls BUG_ON() if the atomic allocation failed.
Do we want to follow?

> +
> +	return page_address(page);

Is the value PT64_ROOT_MAX_LEVEL intended, since dynamic PAMT pages are only
needed for 4KB level?

> +
> +	return topup_tdx_prealloc_page(prealloc, min_fault_cache_size);
[...]

---

## [35] Binbin Wu — 2025-11-26
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On 11/26/2025 11:40 AM, Binbin Wu wrote:
>> index 260bb0e6eb44..61a058a8f159 100644
>> --- a/arch/x86/kvm/vmx/tdx.c
Please ignore this one.

---

## [36] Binbin Wu — 2025-11-26
*Subject: Re: [PATCH v4 13/16] KVM: TDX: Handle PAMT allocation in fault path*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>

Should this change be moved to patch 12?
Because the pre-alloc page list has started to be used in patch 12 for external
page tables even without enabling dynamic PAMT.

>   	fpstate_set_confidential(&vcpu->arch.guest_fpu);
>   	vcpu->arch.apic->guest_apic_protected = true;
[...]

---

## [37] Binbin Wu — 2025-11-26
*Subject: Re: [PATCH v4 14/16] KVM: TDX: Reclaim PAMT memory*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>

External page table pages are not from guest_memfd,  but tdx_pamt_put() is used
in tdx_sept_free_private_spt() for them.

>
> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [38] Binbin Wu — 2025-11-26
*Subject: Re: [PATCH v4 16/16] Documentation/x86: Add documentation for TDX's
 Dynamic PAMT*

On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>
                                         ^
                                         be
> +exclusive use. For normal PAMT, this is installed when the TDX module
> +is first loaded and comes to about 0.4% of system memory.

---

## [39] Nikolay Borisov — 2025-11-26
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On 21.11.25 г. 2:51 ч., Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

nit: Something's odd with the first sentence, perhaps an "is a" before 
is missing before "vmalloc"?

> large allocation size. The virtually contiguous property also makes it
> easy to find a specific 2MB range’s refcount since it can simply be

<snip>

> ---
>   arch/x86/virt/vmx/tdx/tdx.c | 136 +++++++++++++++++++++++++++++++++---

nit: Wouldn't it be better to perform the pte_none() check before doing 
the allocation thus avoiding needless allocations? I.e do the 
alloc/mk_pte only after we are 100% sure we are going to use this entry.

> +
>   	return 0;

    <snip>

---

## [40] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Tue, 2025-11-25 at 09:50 +0800, Binbin Wu wrote:
> Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

Thanks.

> 
> One nit below.


> 
> [...]

Yes, good point, I'll use your suggestion.

---

## [41] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 16/16] Documentation/x86: Add documentation for TDX's
 Dynamic PAMT*

On Wed, 2025-11-26 at 18:33 +0800, Binbin Wu wrote:
> > +PAMT is memory that the TDX module needs to keep data about each page
> > +(think like struct page). It needs to handed to the TDX module for its

Oh, yep, thanks.

---

## [42] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

Kiryl, curious if you have any comments on the below...

On Wed, 2025-11-26 at 16:45 +0200, Nikolay Borisov wrote:
> > +static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void
> > *data)

Yes, but I'm also wondering why it needs init_mm.page_table_lock at all. Here is
my reasoning for why it doesn't:

apply_to_page_range() takes init_mm.page_table_lock internally when it modified
page tables in the address range (vmalloc). It needs to do this to avoid races
with other allocations that share the upper level page tables, which could be on
the ends of area that TDX reserves.

But pamt_refcount_populate() is only operating on the PTE's for the address
range that TDX code already controls. Vmalloc should not free the PMD underneath
the PTE operation because there is an allocation in any page tables it covers.
So we can skip the lock and also do the pte_none() check before the page
allocation as Nikolay suggests.

Same for the depopulate path.

---

## [43] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On Tue, 2025-11-25 at 11:15 +0800, Binbin Wu wrote:
> On 11/21/2025 8:51 AM, Rick Edgecombe wrote:
> [...]

Yes, I don't see what that comment is referring to. But we do need it, because
hypothetically the refcount mapping could have failed halfway. So we will have
pte_none()s for the ranges that didn't get populated. I'll use:

/* Refcount mapping could have failed part way, handle aborted mappings. */

---

## [44] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Tue, 2025-11-25 at 16:09 +0800, Binbin Wu wrote:
> 
> On 11/21/2025 8:51 AM, Rick Edgecombe wrote:

Sounds good.

> > +static int tdx_dpamt_entry_pages(void)
> > +{

Oops, right.

> 
> Also, "SIZE" in the name could be confusing.

Yes LENGTH is probably better.

> 
> > +#define TDX_ARG_INDEX(reg) (offsetof(struct tdx_module_args, reg) / \

Yea, I really debated this. Changing to atomics is more churn, but doing part of
the optimizations early is weird too. I think I might go with the more churn
approach.

> 
> > +			goto out_free;

Not in arch/x86, plus it became TDX_BUG_ON() in the cleanup series.

> 
> Aslo, so for in this patch, when this SEAMCALL failed, does it indicate a bug?

Yes. This should set ret to an error value too. Yes SEAMCALL failure indicates a
bug, but it should be harmless to the host. tdx_pamt_get() returns a failure so
the calling code can handle it. The tdx_pamt_put() is a little weirder. We can
have the option to keep the refcount elevated if remove fails. This means DPAMT
stays addded for this 2MB range. I think it is ok for 4KB guest memory. It
basically means a DPAMT page will stay in place forever in the case of a bug,
which is the current non-dynamic PAMT situation. So I'm not sure if a full WARN
is needed.

But I'm just realizing that the page it is backing could reform it's way into a
2MB page. Then, after the TDX huge pages series, it could end up getting mapped
as 2MB private memory. In which case the PAMT.REMOVE needs to succeed before
adding the page as 2MB. Hmm, need to check TDX huge page series, because I think
this is not handled. So when TDX huge pages comes, a WARN might be more
appropriate.

We might need to make tdx_pamt_put() return an error for huge pages, and treat
failure like the other TDX remove failures, or maybe just a WARN. I'd lean
towards just the WARN. Do you have any better ideas?

> 
> > +			goto out_free;

Yes.

> 
> > +out_free:

---

## [45] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Wed, 2025-11-26 at 01:21 +0000, Huang, Kai wrote:
> >  }
> >  

Sure, I'll fix it.

---

## [46] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Wed, 2025-11-26 at 11:40 +0800, Binbin Wu wrote:
> 
> On 11/21/2025 8:51 AM, Rick Edgecombe wrote:

Right, thanks.

> 
> > installed under a spin lock. This means that the operations around

I'll adjust.

> 
> > + */

Ignoring, per your other comment. But we don't want to add BUG_ON()s in general.
> 
> > +

I'm not sure I follow. We need DPAMT backing for each S-EPT page table.

---

## [47] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 13/16] KVM: TDX: Handle PAMT allocation in fault path*

On Wed, 2025-11-26 at 13:56 +0800, Binbin Wu wrote:
> > --- a/arch/x86/kvm/vmx/tdx.c
> > +++ b/arch/x86/kvm/vmx/tdx.c

Oh, yes. thanks.

---

## [48] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 14/16] KVM: TDX: Reclaim PAMT memory*

On Wed, 2025-11-26 at 16:53 +0800, Binbin Wu wrote:
> > Add tdx_pamt_put() for memory that comes from guest_memfd and use
> > tdx_free_page() for the rest.

Right, this could be "...for pages that are passed from outside of TDX code...

---

## [49] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Tue, 2025-11-25 at 22:30 +0000, Huang, Kai wrote:
> > --- a/arch/x86/kvm/vmx/tdx_errno.h
> > +++ b/arch/x86/include/asm/shared/tdx_errno.h

Oh, wow you're right. Will update it.
> 
> >  

This change was originally from Kiryl. I'm not sure. AFAIK they should all be
RAX. I'd be fine to remove it, but I do think the RAX part is a bit extraneous.
But this patch doesn't require it, so happy to shrink the diff.

> 
> >   */

Yep, you're right.

---

## [50] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Tue, 2025-11-25 at 22:44 +0000, Huang, Kai wrote:
> Also forgot to say, AFAICT these error codes will also be used by TDX guest,
> therefore you might want to drop the "SEAMCALL" part from the status codes.

Oh, yes. That comment tweak is actually relevent to this patch.

---

## [51] Edgecombe, Rick P — 2025-11-26
*Subject: Re: [PATCH v4 02/16] x86/tdx: Add helpers to check return status
 codes*

On Tue, 2025-11-25 at 23:07 +0000, Huang, Kai wrote:
> On Thu, 2025-11-20 at 16:51 -0800, Rick Edgecombe wrote:
> > diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h

Yea that makes sense.

> 
> You may also move <linux/types.h> out of __ASSEMBLER__ since AFAICT this file is

Sure.

---

## [52] Binbin Wu — 2025-11-27
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On 11/27/2025 6:33 AM, Edgecombe, Rick P wrote:
>>>     
>>>     static int tdx_topup_external_fault_cache(struct kvm_vcpu *vcpu, unsigned int cnt)
Oh, right!

IIUIC,  PT64_ROOT_MAX_LEVEL is actually
- PT64_ROOT_MAX_LEVEL - 1 for S-ETP pages since root page is not needed.
- 1 for TD private memory page

It's better to add a comment about it.

---

## [53] Nikolay Borisov — 2025-11-27
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On 26.11.25 г. 22:47 ч., Edgecombe, Rick P wrote:
> Kiryl, curious if you have any comments on the below...
> 
 > > But pamt_refcount_populate() is only operating on the PTE's for the 
address
> range that TDX code already controls. Vmalloc should not free the PMD underneath
> the PTE operation because there is an allocation in any page tables it covers.

I agree with your analysis but this needs to be described not only in 
the commit message but also as a code comment because you intentionally 
omit locking since that particular pte (at that point) can only have a 
single user so no race conditions are possible.

> 
> Same for the depopulate path.

---

## [54] Nikolay Borisov — 2025-11-27
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 21.11.25 г. 2:51 ч., Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

That paragraph is rather hard to parse. KVM will need to hand 4k pages 
to whom? The tdx init code? Also the last sentence with the 2 "backing" 
words is hard to parse. Does it say that the 4k pages that KVM need to 
pass must be backed by DPAMT pages i.e like a chicken and egg problem?

> 
> Add tdx_alloc_page() and tdx_free_page() to handle both page allocation

<snip>


> +
> +/* Serializes adding/removing PAMT memory */

Replace this pair of read/inc with a single call to atomic_inc_not_zero()

> +
> +		/* Try to add the pamt page and take the refcount 0->1. */

nit: Could be replaced with : atomic_add_unless(pamt_refcount, -1, 1);

Probably it would have been better to simply use atomic64_dec_and_test 
and if it returns true do the phymem_pamt_remove, but I suspect you 
can't do it because in case it fails you don't want to decrement the 
last refcount, though that could be remedied by an extra atomic_int in 
the failure path. I guess it might be worth simplifying since the extra 
inc will only be needed in exceptional cases (we don't expect failure ot 
be the usual path) and freeing is not a fast path.

> +
> +		/* Try to remove the pamt page and take the refcount 1->0. */

<snip>

---

## [55] Kiryl Shutsemau — 2025-11-27
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On Wed, Nov 26, 2025 at 08:47:19PM +0000, Edgecombe, Rick P wrote:
> On Tue, 2025-11-25 at 11:15 +0800, Binbin Wu wrote:
> > On 11/21/2025 8:51 AM, Rick Edgecombe wrote:

It is possible that we can have holes in physical address space between
0 and max_pfn. You need the check even outside of "failed halfway"
scenario.

---

## [56] Kiryl Shutsemau — 2025-11-27
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On Wed, Nov 26, 2025 at 08:47:07PM +0000, Edgecombe, Rick P wrote:
> Kiryl, curious if you have any comments on the below...
> 

I cannot remember/find a good reason to keep the locking around.

---

## [57] Nikolay Borisov — 2025-11-27
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 21.11.25 г. 2:51 ч., Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

Isn't this guaranteed to return 2 always as per the ABI? Can't the 
allocation of the 2 pages be moved closer to where it's used - in 
tdh_phymem_pamt_add which will simplify things a bit?

<snip>

---

## [58] Edgecombe, Rick P — 2025-12-01
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On Thu, 2025-11-27 at 15:57 +0000, Kiryl Shutsemau wrote:
> > Yes, I don't see what that comment is referring to. But we do need it,
> > because hypothetically the refcount mapping could have failed halfway. So we

Err. right. Was thinking of for_each_mem_pfn_range() on the populate side.
pamt_refcount_depopulate() is just called with the whole refcount virtual
address range. I'll add both reasons to the comment.

---

## [59] Edgecombe, Rick P — 2025-12-01
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, 2025-11-27 at 14:29 +0200, Nikolay Borisov wrote:
> > While the TDX initialization code in arch/x86 uses pages with 2MB
> > alignment, KVM will need to hand 4KB pages for it to use. Under DPAMT,

You're right it's confusing and also a slightly misleading typo, maybe this is
an improvement?

   While the TDX module initialization code in arch/x86 only hands pages to the
   TDX module with 2MB alignment, KVM will need to hand pages to the TDX module
   at 4KB granularity. Under DPAMT, such pages will require performing the
   TDH.PHYMEM.PAMT.ADD SEAMCALL to give a page pair the the TDX module to use
   for PAMT tracking at the 4KB page size page.

Note: There is no chicken or egg problem, TDH.PHYMEM.PAMT.ADD handles it.

> 
> > 

From the thread with Binbin on this patch, the atomics aren't really needed
until the optimization patch. So was thinking to actually use a simpler non-
atomic operations.

> 
> > +

The goal of this patch is to be as simple and obviously correct as possible.
Then the next patch "x86/virt/tdx: Optimize tdx_alloc/free_page() helpers"
should have the optimized versions. Do you have any similar suggestions on the
code after the next patch is applied?

---

## [60] Edgecombe, Rick P — 2025-12-01
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, 2025-11-27 at 18:11 +0200, Nikolay Borisov wrote:
> > +/* Number PAMT pages to be provided to TDX module per 2M region of PA */
> > +static int tdx_dpamt_entry_pages(void)

Yea, it could be simpler if it was always guaranteed to be 2 pages. But it was
my understanding that it would not be a fixed size. Can you point to what docs
makes you think that?

Another option would be to ask TDX folks to make it fixed, and then require an
opt-in for it to be expanded later if needed. I would have to check on them on
the reasoning for it being dynamic sized. I'm not sure if it is *that*
complicated at this point though. Once there is more than one, the loops becomes
tempting. And if we loop over 2 we could easily loop over n.

---

## [61] Nikolay Borisov — 2025-12-02
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 2.12.25 г. 0:39 ч., Edgecombe, Rick P wrote:
> On Thu, 2025-11-27 at 18:11 +0200, Nikolay Borisov wrote:
>>> +/* Number PAMT pages to be provided to TDX module per 2M region of PA */

Looking at the PHYMEM.PAMT.ADD ABI spec the pages being added are always 
put into pair in rdx/r8. So e.g. looking into tdh_phymem_pamt_add rcx is 
set to a 2mb page, and subsequently we have the memcpy which simply sets 
the rdx/r8 input argument registers, no ? Or am I misunderstanding the 
code?
> 
> Another option would be to ask TDX folks to make it fixed, and then require an

---

## [62] Edgecombe, Rick P — 2025-12-02
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Tue, 2025-12-02 at 09:38 +0200, Nikolay Borisov wrote:
> > Yea, it could be simpler if it was always guaranteed to be 2 pages. But it
> > was

Hmm, you are totally right. The docs specify the size of the 4k entries, but
doesn't specify that Dynamic PAMT is supposed to provide larger sizes in the
other registers. A reasonable reading could assume 2 pages always, and the usage
of the other registers seems like an assumption.

Kirill, any history here?

Otherwise, we could turn tdx_dpamt_entry_pages() into a define and shrink the
stack allocated buffers. I'll see how much removing the loops helps.

---

## [63] Kiryl Shutsemau — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Tue, Dec 02, 2025 at 08:02:38PM +0000, Edgecombe, Rick P wrote:
> On Tue, 2025-12-02 at 09:38 +0200, Nikolay Borisov wrote:
> > > Yea, it could be simpler if it was always guaranteed to be 2 pages. But it

There was a plan to future prove DPAMT by allowing PAMT descriptor to
grow in the future. The concrete approach was not settled last time I
checked. This code was my attempt to accommodate it. I don't know if it
fits the current plan.

---

## [64] Nikolay Borisov — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 3.12.25 г. 15:46 ч., Kiryl Shutsemau wrote:
> On Tue, Dec 02, 2025 at 08:02:38PM +0000, Edgecombe, Rick P wrote:
>> On Tue, 2025-12-02 at 09:38 +0200, Nikolay Borisov wrote:

Considering this, I'd opt for the simplest possible approach that works 
_now_. If in the future there are changes to the ABI let's introduce 
them incrementally when their time comes.

---

## [65] Dave Hansen — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 12/3/25 05:48, Nikolay Borisov wrote:
>> There was a plan to future prove DPAMT by allowing PAMT descriptor to
>> grow in the future. The concrete approach was not settled last time I

It's fixed at a "page pair" in the ABI documentation, no?

If Intel wants anything else, it should have documented that as the ABI.
So, as far as the code goes, it's a "page pair" now and forever. Linux
does not need to go out of its way to make it inflexible, but there's no
need to add complexity now for some future that may never come.

I agree with Nikolay: KISS.

---

## [66] Edgecombe, Rick P — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Wed, 2025-12-03 at 07:41 -0800, Dave Hansen wrote:
> It's fixed at a "page pair" in the ABI documentation, no?
> 

Thanks Dave. Yes, let's stick to the spec. I'm going to try to pull the loops
out too because we can get rid of the union array thing too.

Thanks for the catch Nikolay.

---

## [67] Dave Hansen — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 12/3/25 10:15, Edgecombe, Rick P wrote:
> On Wed, 2025-12-03 at 07:41 -0800, Dave Hansen wrote:
>> It's fixed at a "page pair" in the ABI documentation, no?

Also, I honestly don't see the problem with just allocating an order-1
page for this. Yeah, the TDX modules doesn't need physically contiguous
pages, but it's easier for _us_ to lug them around if they are
physically contiguous.

Plus, if you permanently allocate 2 order-0 pages, you are _probably_
going to permanently destroy 2 potential future 2MB pages. The order-1
allocation will only destroy 1.

---

## [68] Edgecombe, Rick P — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Wed, 2025-12-03 at 10:21 -0800, Dave Hansen wrote:
> > Thanks Dave. Yes, let's stick to the spec. I'm going to try to pull the
> > loops

We have two spin locks to contend with for these allocations. One is the global
spin lock on the arch/x86 side. In this case, the the pages don't have to be
passed far, like:

tdx_pamt_get(some_page, NULL)
	page1 = alloc()
	page2 = alloc()

	scoped_guard(spinlock, &pamt_lock) {
		tdh_phymem_pamt_add(.., page1, page2)
			/* Pack into struct */
			seamcall()
	}

I think it's not too bad?

Then there is the KVM MMU spin lock during the fault path. This lock happens way
up the call chain. It goes something like:

topup_tdx_pages_cache() /* Add order-0 pages for S-EPT page tables and dpamt */ 

spin_lock()

... many calls ...
        order_0_s_ept_page table = alloc_from_order_0_cache();

        tdx_sept_link_private_spt(order_0_s_ept_page)
                tdx_pamt_get(order_0_s_ept_page, order_0_cache)
                        /* alloc two pages from order_0_cache for dpamt */

        tdx_sept_set_private_spte(guest_page)
                tdx_pamt_get(guest_page, order_0_cache)
                        /* alloc two pages from order_0_cache for dpamt*/

spin_unlock()


So if we decide to pass a single order-1 page into tdx_pamt_get() instead of
order_0_cache, we can stop passing the cache between KVM and arch/x86, but we
then need two cache's instead of one. One for order-0 S-EPT page tables and one
for order-1 DPAMT page pairs.

Also, if we have to allocate the order-1 page in each caller, it simplifies the
arch/x86 code, but duplicates the allocation in the KVM callers (only 2 today
though).

So I'm suspicious it's not going to be a big win, but I'll give it a try.

> 
> Plus, if you permanently allocate 2 order-0 pages, you are _probably_

Doesn't the buddy allocator try to avoid splitting larger blocks? I guess you
mean in the worst case, but the DPAMT should also not be allocated forever
either. So I think it's only at the intersection of two worst cases? Worth it?

---

## [69] Dave Hansen — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 12/3/25 11:59, Edgecombe, Rick P wrote:
> On Wed, 2025-12-03 at 10:21 -0800, Dave Hansen wrote:
>>> Thanks Dave. Yes, let's stick to the spec. I'm going to try to pull the

No, that's not bad.

The thing I thought was annoying was in the past when there were a bunch
of functions with two explicit page pointers plumbed in to them.

> So if we decide to pass a single order-1 page into tdx_pamt_get() instead of
> order_0_cache, we can stop passing the cache between KVM and arch/x86, but we

Yeah, the value of doing order-1 is super low if it means managing a
second cache.

>> Plus, if you permanently allocate 2 order-0 pages, you are _probably_
>> going to permanently destroy 2 potential future 2MB pages. The order-1

It's not splitting them in this case. They're *already* split:

# cat /proc/buddyinfo
...
Node 0, zone   Normal  32903  33566 ...

See, there are already ~33,000 4k pages sitting there. Those will be
consumed first on any 4k allocation. So, yeah, it'll avoid splitting an
8k block to get 4k pages normally.

BTW, I *DO* expect the DPAMT pages to be mostly allocated forever. Maybe
I'm just a pessimist, but you can't get them back for compaction or
reclaim, so they're basically untouchable. Sure, if you kill all the TDX
guests you get them back, but that's a very different kind of kernel
memory from stuff that's truly reclaimable under pressure.

---

## [70] Edgecombe, Rick P — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Wed, 2025-12-03 at 12:13 -0800, Dave Hansen wrote:
> BTW, I *DO* expect the DPAMT pages to be mostly allocated forever. Maybe
> I'm just a pessimist, but you can't get them back for compaction or

If we want to improve it (later) we could topup via a single higher order
allocation. So like if we need 15 pages we could round up to an order-4, then
hand them out individually. But I suspect someone would want to see some proof
before that kind of tweak.

So I take it you are ok to leave the general approach, but worth trying to
remove the dynamic sizing.

---

## [71] Dave Hansen — 2025-12-03
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 12/3/25 13:39, Edgecombe, Rick P wrote:
> So I take it you are ok to leave the general approach, but worth trying to
> remove the dynamic sizing.

Yeah, that sounds fine.

---

## [72] Yan Zhao — 2025-12-08
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, Nov 20, 2025 at 04:51:16PM -0800, Rick Edgecombe wrote:
> +static int alloc_pamt_array(u64 *pa_array)
> +{
On failure to allocate the 2nd page, instead of zeroing out the rest of the
array and having the caller invoke free_pamt_array() to free the 1st page,
could we free the 1st page here directly?

Upon alloc_pamt_array() error, the pages shouldn't have been passed to the TDX
module, so there's no need to invoke tdx_quirk_reset_paddr() as in
free_pamt_array(), right?

It's also somewhat strange to have the caller to invoke free_pamt_array() after
alloc_pamt_array() fails.

> +	/*
> +	 * Zero the rest of the array to help with
...
> +/* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
> +int tdx_pamt_get(struct page *page)

---

## [73] Edgecombe, Rick P — 2025-12-08
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Mon, 2025-12-08 at 17:15 +0800, Yan Zhao wrote:
> On failure to allocate the 2nd page, instead of zeroing out the rest of the
> array and having the caller invoke free_pamt_array() to free the 1st page,

We don't want to optimize the error path. So I think less code is better than
making it slightly faster in an ultra rare case.

> 
> It's also somewhat strange to have the caller to invoke free_pamt_array() after

Yea, I agree this code is a bit odd. Based on the discussion with Nikolay and
Dave, this can be less variable. It should get simplified as part of that.

---

## [74] Edgecombe, Rick P — 2025-12-11
*Subject: Re: [PATCH v4 06/16] x86/virt/tdx: Improve PAMT refcounts allocation
 for sparse memory*

On Thu, 2025-11-27 at 09:36 +0200, Nikolay Borisov wrote:
> I agree with your analysis but this needs to be described not only in 
> the commit message but also as a code comment because you intentionally 

While commenting and writing up the log reasoning for why this is safe, I ended
up revisiting why we need to do all this manual PTE modification in the first
place. 

In Kiryl's v2 he had the vmalloc area allocated with VM_IOREMAP. Kai asked why,
and seemingly as a result, it was changed to VM_SPARSE. It turns out the
VM_SPARSE flag is a newer thing for dealing with sparsely populated vmalloc
address space mappings, exactly like we have here. It comes with some helpers
for mapping and unmapping sparse vmalloc ranges. So I played around with these a
bit.

The current apply_to_page_range() version is optimally efficient, but the
allocation is a one-time operation, and the freeing is actually only called in
an error path. I'm not sure it needs to be optimal.

If you use the helpers to populate, you pretty much just need to allocate all
the pages up front, and then call vm_area_map_pages() to map them. To unmap (the
error path), the code pattern is to iterate through the mapping a page at a
time, fetch the page with vmalloc_to_page(), unmap and free the page. At most
this is 2,097,152 iterations. Not fast, but not going to hang boot either.

So rather than the try to justify the locking, I'm thinking to go with a
stupider, simpler mapping/unmapping method that uses the ready made VM_SPARSE
helpers.

I hate to change things at this point, but I think the discussed reasoning is
going to beg the question of why it needs to be complicated.

---

## [75] Xu Yilun — 2025-12-24
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

> diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
> index 13ad2663488b..00ab0e550636 100644

Is it better we seal the awkward pattern inside the if (dpamt supported)  block:

	if (tdx_support_dynamic_pamt(&tdx_sysinfo))
		if (!ret && !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
			sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;

so we don't have to get used to another variant of the awkward pattern :)

Thanks,
Yilun

>  
>  	return ret;

---

## [76] Edgecombe, Rick P — 2026-01-05
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Wed, 2025-12-24 at 17:10 +0800, Xu Yilun wrote:
> Is it better we seal the awkward pattern inside the if (dpamt supported)  block:
> 

The extra indentation might be objectionable.

But I agree that line is too hard to read. It actually already caused some
confusion, which precipitated the comment. I played around with it and was
thinking to go with this instead to make it fit the pattern better. What do you
think?

static int get_tdx_sys_info_dpamt_bits(struct tdx_sys_info_tdmr *sysinfo_tdmr,
u64 *val)
{
	/*
	 * Don't let the metadata reading fail if dynamic PAMT isn't
	 * supported. The TDX code can fallback to normal PAMT in
	 * this case.
	 */
	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
		*val = 0;
		return 0;
	}

	return read_sys_metadata_field(0x9100000100000013, val);
}

static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
{
	int ret = 0;
	u64 val;

	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000008, &val)))
		sysinfo_tdmr->max_tdmrs = val;
	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000009, &val)))
		sysinfo_tdmr->max_reserved_per_tdmr = val;
	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000010, &val)))
		sysinfo_tdmr->pamt_4k_entry_size = val;
	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000011, &val)))
		sysinfo_tdmr->pamt_2m_entry_size = val;
	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000012, &val)))
		sysinfo_tdmr->pamt_1g_entry_size = val;
	if (!ret && !(ret = get_tdx_sys_info_dpamt_bits(sysinfo_tdmr, &val)))
		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;

	return ret;
}

---

## [77] Xu Yilun — 2026-01-06
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Mon, Jan 05, 2026 at 10:06:31PM +0000, Edgecombe, Rick P wrote:
> On Wed, 2025-12-24 at 17:10 +0800, Xu Yilun wrote:
> > Is it better we seal the awkward pattern inside the if (dpamt supported)  block:

Yes the extra indentation is unconventional, but everything here is, and
we know we will eventually change them all. So I more prefer simple
changes based on:

  if (!ret && !(ret = read_sys_metadata_field(0xABCDEF, &val)))

rather than neat but more LOC (when both are easy to read).

Anyway, this is trivial concern. I have more optional fields to add and
will follow the final decision.

---

## [78] Edgecombe, Rick P — 2026-01-06
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Tue, 2026-01-06 at 12:01 +0800, Xu Yilun wrote:
> Yes the extra indentation is unconventional, but everything here is,
> and we know we will eventually change them all. So I more prefer

This whole code style was optimized to be verifiable, not for LOC. Kai
originally had several macro based solution that had a bunch of code
reuse before this style got settled on as part of the code gen. It
would definitely be a good thing to review the previous versions before
working on yet another solution to metadata reading.

> 
> Anyway, this is trivial concern. I have more optional fields to add

This is the kind of thing that shouldn't need a clever solution. There
*should* be a way to more simply copy structured data from the TDX
module.

I do think this is a good area for cleanup, but let's not overhaul it
just to get a small incremental benefit. If we need a new interface in
the TDX module, let's explore it and actually get to something simple.

---

## [79] Xu Yilun — 2026-01-07
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Tue, Jan 06, 2026 at 05:00:48PM +0000, Edgecombe, Rick P wrote:
> On Tue, 2026-01-06 at 12:01 +0800, Xu Yilun wrote:
> > Yes the extra indentation is unconventional, but everything here is,

Yeah, I know the code style in this block is the result of several
rounds discussion, refined but not intend for human read. So I suggest
we only keep the existing steorotypes:

  if (!ret && !(ret = read_sys_metadata_field(0xABCDEF, &val)))
	sysinfo_xxx->xxxxx = val;
and

  ret = ret ?: get_tdx_sys_info_xxx(&sysinfo->xxx);

isolate them, don't create other varients/hybrids of them such as:

  if (!ret && !(ret = get_tdx_sys_info_dpamt_bits(sysinfo_tdmr, &val)))

when we need other logics, to avoid extensive review effort.


That's why I'm more fond of my version, it embraces the steorotype with
a nature "if" for extra logic:

  if (tdx_support_dynamic_pamt(&tdx_sysinfo))
	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;

But anyway, if anyone is really uncomfortable with the indentation,
ignore my version.

[...]

> > Anyway, this is trivial concern. I have more optional fields to add
> > and will follow the final decision.

Agree. I definitely don't want a new TDX module interface for now.

> the TDX module, let's explore it and actually get to something simple.

---

## [80] Edgecombe, Rick P — 2026-01-07
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Wed, 2026-01-07 at 14:01 +0800, Xu Yilun wrote:
> > I do think this is a good area for cleanup, but let's not overhaul
> > it

No, I was suggesting to think about a new TDX module interface if that
is what it takes to really simplify it. For example, something like a
consistent TDH.SYS.RDALL. For TDX module changes to be available in the
future (for example at the time of the other optional metadata), we
actually need to start the process now.

---

## [81] Xu Yilun — 2026-01-08
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Wed, Jan 07, 2026 at 02:41:44PM +0000, Edgecombe, Rick P wrote:
> On Wed, 2026-01-07 at 14:01 +0800, Xu Yilun wrote:
> > > I do think this is a good area for cleanup, but let's not overhaul

I actually don't understand why a RDALL seamcall could eliminate
the check "if (some_optional_feature_exists) read_it;". IIUC, The check
exists because kernel doesn't trust TDX Module so kernel wants to verify
the correctness/consistency of the data, otherwise we could accept
whatever TDX Module tells us, do the below for each field:

  static int read_sys_metadata_field(u64 field_id, u64 *data)
  {
	...
	ret = seamcall(TDH_SYS_RD, &args);
	if (ret == TDX_SUCCESS) {
		*data = args.r8;
		return 0;
	}

	/* The field doesn't exist */
	if (ret == TDX_METADATA_FIELD_ID_INCORRECT) {
		*data = 0;
		return 0;
	}

	...

	/* Real reading error */
	return -EFAULT;
  }

The trustness doesn't change no matter how kernel retrieves these data,
by a series of RD or a RDALL.

Thanks,
Yilun

> future (for example at the time of the other optional metadata), we
> actually need to start the process now.

---

## [82] Edgecombe, Rick P — 2026-01-08
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Thu, 2026-01-08 at 20:53 +0800, Xu Yilun wrote:
> I actually don't understand why a RDALL seamcall could eliminate
> the check "if (some_optional_feature_exists) read_it;". IIUC, The

Having it be field specific behavior (like the diff I posted) means we
don't need to worry about TDX module bugs where some field read fails
and we don't catch it.

By RDALL, I mean a simpler way to bulk read the metadata. So for future
looking changes, let's think about what we need and not try to find yet
more clever ways to code around the current interface. The amount of
code and discussion on TDX metadata reading is just too high. Please go
back and look at the earlier threads if you haven't yet.

---

## [83] Xu Yilun — 2026-01-09
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Thu, Jan 08, 2026 at 04:52:10PM +0000, Edgecombe, Rick P wrote:
> On Thu, 2026-01-08 at 20:53 +0800, Xu Yilun wrote:
> > I actually don't understand why a RDALL seamcall could eliminate

We still need this specific behavior when we bulk read. Can you accept
a successfully returned blob with TDX_FEATURES0_DYNAMIC_PAMT set but
pamt_page_bitmap_entry_bits field missing? I assume no, so we still
need:

	if (blob->tdx_feature0 & TDX_FEATURES0_DYNAMIC_PAMT)
		check blob->pamt_page_bitmap_entry_bits validity;

BTW: ret == TDX_METADATA_FIELD_ID_INCORRECT is not something bad, TDX
Module is effectively telling us the field doesn't exist.

> 
> By RDALL, I mean a simpler way to bulk read the metadata. So for future

I understand. But as I mentioned that has nothing to do with the
optional feature checking.

> looking changes, let's think about what we need and not try to find yet
> more clever ways to code around the current interface. The amount of

I don't think so, cause I don't see much benifit bulk reading could
bring to us. Bulk reading basically retrieves an _unverified_ blob from
TDX Module. I believe it could also been achieved by a simple iteration
of existing single reads. The major work, data verification, is still
there.

On the other hand, the cost of a newly designed firmware interface for
an already online functionality is not low, especially when you want
backward compatibility to old TDX Module. The worst case is we keep both
sets of the code...

> code and discussion on TDX metadata reading is just too high. Please go
> back and look at the earlier threads if you haven't yet.

I've read most of the threads before my first posting on this topic.
Most of the discussion/effort focus on the effective data verification.
But I haven't found any decisive evidence that bulk reading could
contribute on it.

---

## [84] Edgecombe, Rick P — 2026-01-09
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Fri, 2026-01-09 at 10:18 +0800, Xu Yilun wrote:
> On the other hand, the cost of a newly designed firmware interface
> for an already online functionality is not low, especially when you

I think TDX module changes are something to consider long term. We
already discussed not overhauling the metadata reading again ahead of
the current work, so I don't think there is anything else to discuss
here.

---

## [85] Xu Yilun — 2026-01-12
*Subject: Re: [PATCH v4 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Fri, Jan 09, 2026 at 04:05:30PM +0000, Edgecombe, Rick P wrote:
> On Fri, 2026-01-09 at 10:18 +0800, Xu Yilun wrote:
> > On the other hand, the cost of a newly designed firmware interface

I agree. We don't have to introduce new interfaces for optional feature
checking. That's another topic.

---

## [86] Sean Christopherson — 2026-01-16
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, Nov 20, 2025, Rick Edgecombe wrote:
> +/*
> + * Return a page that can be used as TDX private memory

Wrap at ~80.

This comment is also misleading, arguably wrong.  Because from KVM's perspective,
these APIs are _never_ used to back TDX private memory.  They are used only for
control pages, which yeah, I suppose might be encrypted with the guest's private
key, but most readers will interpret "used as TDX private memory" to mean that
these are _the_ source of pages for guest private memory.

> + */
> +struct page *tdx_alloc_page(void)

And in a similar vein, given terminology in other places, maybe call these
tdx_{alloc,free}_control_page()?

> +{
> +	struct page *page;

GFP_KERNEL_ACCOUNT, all of these allocations are tied to a VM.

> +	if (!page)
> +		return NULL;

Note, these can all now be EXPORT_SYMBOL_FOR_KVM.

---

## [87] Edgecombe, Rick P — 2026-01-16
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Fri, 2026-01-16 at 15:17 -0800, Sean Christopherson wrote:
> On Thu, Nov 20, 2025, Rick Edgecombe wrote:
> > +/*

Maybe just drop "private" and call it TDX memory?

> 
> > + */

True, that is the only use today, but also there is nothing control page
specific about the functions themselves. I'm ok changing it, but I'm not sure it
helps that much.

> 
> > +{

Yes, thanks.

> 
> > +	if (!page)

Sure.

---

## [88] Dave Hansen — 2026-01-16
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 1/16/26 15:17, Sean Christopherson wrote:
>> +struct page *tdx_alloc_page(void)
> And in a similar vein, given terminology in other places, maybe call these

Ack on the naming, especially if they're never used as normal guest
memory and are *only* for TDX module metadata that the guest never
actually sees.

---

## [89] Sean Christopherson — 2026-01-16
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Thu, Nov 20, 2025, Rick Edgecombe wrote:
> Move mmu_external_spt_cache behind x86 ops.
> 

NAK.  I kinda sorta get why you did this?  But the pages KVM uses for page tables
are KVM's, not to be mixed with PAMT pages.

Eww.  Definitely a hard "no".  In tdp_mmu_alloc_sp_for_split(), the allocation
comes from KVM:

	if (mirror) {
		sp->external_spt = (void *)get_zeroed_page(GFP_KERNEL_ACCOUNT);
		if (!sp->external_spt) {
			free_page((unsigned long)sp->spt);
			kmem_cache_free(mmu_page_header_cache, sp);
			return NULL;
		}
	}

But then in kvm_tdp_mmu_map(), via kvm_mmu_alloc_external_spt(), the allocation
comes from get_tdx_prealloc_page()

  static void *tdx_alloc_external_fault_cache(struct kvm_vcpu *vcpu)
  {
	struct page *page = get_tdx_prealloc_page(&to_tdx(vcpu)->prealloc);

	if (WARN_ON_ONCE(!page))
		return (void *)__get_free_page(GFP_ATOMIC | __GFP_ACCOUNT);

	return page_address(page);
  }

But then regardles of where the page came from, KVM frees it.  Seriously.

  static void tdp_mmu_free_sp(struct kvm_mmu_page *sp)
  {
	free_page((unsigned long)sp->external_spt);  <=====
	free_page((unsigned long)sp->spt);
	kmem_cache_free(mmu_page_header_cache, sp);
  }

Oh, and the hugepage series also fumbles its topup (why there's yet another
topup API, I have no idea).

  static int tdx_topup_vm_split_cache(struct kvm *kvm, enum pg_level level)
  {
	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
	struct tdx_prealloc *prealloc = &kvm_tdx->prealloc_split_cache;
	int cnt = tdx_min_split_cache_sz(kvm, level);

	while (READ_ONCE(prealloc->cnt) < cnt) {
		struct page *page = alloc_page(GFP_KERNEL);  <==== GFP_KERNEL_ACCOUNT

		if (!page)
			return -ENOMEM;

		spin_lock(&kvm_tdx->prealloc_split_cache_lock);
		list_add(&page->lru, &prealloc->page_list);
		prealloc->cnt++;
		spin_unlock(&kvm_tdx->prealloc_split_cache_lock);
	}

	return 0;
  }

---

## [90] Sean Christopherson — 2026-01-16
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Thu, Nov 20, 2025, Rick Edgecombe wrote:
> ---
> v4:

LOL, having fun reinventing kvm_mmu_memory_cache? :-D

>  - Explain why not to use mempool (Dave)
>  - Tweak local vars to be more reverse christmas tree by deleting some

> +/*
> + * Simple structure for pre-allocating Dynamic

As called out in an earlier patch, it's not just PAMT pages.

> + */
> +struct tdx_prealloc {

Huh, TIL that page->lru is fair game for private usage when the page is kernel-
allocated.  

> +		prealloc->cnt++;
>

No.  Either put the ownership of the PAMT cache in arch/x86/virt/vmx/tdx/tdx.c
or use kvm_mmu_memory_cache.  Don't add a custom caching scheme in KVM.
  
>  /* Number PAMT pages to be provided to TDX module per 2M region of PA */
> -static int tdx_dpamt_entry_pages(void)

A comment here stating the "common" number of entries would be helper.  I have no
clue as to the magnitude.  E.g. this could be 2 or it could be 200, I genuinely
have no idea.

---

## [91] Yan Zhao — 2026-01-19
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Fri, Jan 16, 2026 at 04:53:57PM -0800, Sean Christopherson wrote:
> On Thu, Nov 20, 2025, Rick Edgecombe wrote:
> > Move mmu_external_spt_cache behind x86 ops.
IMHO, it's by design. I don't see a problem with KVM freeing the sp->external_spt,
regardless of whether it's from:
(1) KVM's mmu cache,
(2) tdp_mmu_alloc_sp_for_split(), or
(3) tdx_alloc_external_fault_cache().
Please correct me if I missed anything.

None of (1)-(3) keeps the pages in list after KVM obtains the pages and maps
them into SPTEs.

So, with SPTEs as the pages' sole consumer, it's perfectly fine for KVM to free
the pages when freeing SPTEs. No?

Also, in the current upstream code, after tdp_mmu_split_huge_pages_root() is
invoked for dirty tracking, some sp->spt are allocated from
tdp_mmu_alloc_sp_for_split(), while others are from kvm_mmu_memory_cache_alloc().
However, tdp_mmu_free_sp() can still free them without any problem.

> Oh, and the hugepage series also fumbles its topup (why there's yet another
> topup API, I have no idea).
Introducing another topup API is because in the hugepage usage, the split occurs
in a non-vCPU context. So, the "kvm_tdx->prealloc_split_cache" is per-VM, since
hugepage cannot reuse tdx_topup_external_fault_cache().
(Please also see the patch log of
"[PATCH v3 19/24] KVM: x86: Introduce per-VM external cache for splitting" [1]).

[1] https://lore.kernel.org/all/20260106102331.25244-1-yan.y.zhao@intel.com.

>   static int tdx_topup_vm_split_cache(struct kvm *kvm, enum pg_level level)
>   {
Thanks for caching. Will use GFP_KERNEL_ACCOUNT instead.

> 		if (!page)
> 			return -ENOMEM;

I didn't have tdx_topup_vm_split_cache() reuse topup_tdx_prealloc_page() (as
used by tdx_topup_external_fault_cache()). This is due to the need to add the
spinlock kvm_tdx->prealloc_split_cache_lock to protect page enqueuing and
dequeuing.  (I've pasted the explanation of the per-VM external cache for
splitting and its lock protections from [2] below as an "Appendix" for your
convenience).

If we can have the split for huge pages not reuse
tdp_mmu_split_huge_pages_root() (i.e., create a specific interface for
kvm_split_cross_boundary_leafs() instead of reusing
tdp_mmu_split_huge_pages_root(), as I asked about in [3]), we can preallocate
enough pages and hold mmu_lock without releasing it for memory allocation. Then,
this spinlock kvm_tdx->prealloc_split_cache_lock would not be needed.

[2] https://lore.kernel.org/all/20260106101646.24809-1-yan.y.zhao@intel.com
[3] https://lore.kernel.org/all/aW2Iwpuwoyod8eQc@yzhao56-desk.sh.intel.com
> 		list_add(&page->lru, &prealloc->page_list);
> 		prealloc->cnt++;
Appendix:
Explanation of the per-VM external cache for splitting huge pages from the
cover letter of huge pages v3 [2]:

"
9. DPAMT
   Currently, DPAMT's involvement with TDX huge page is limited to page
   splitting.

   As shown in the following call stack, DPAMT pages used by splitting are
   pre-allocated and queued in the per-VM external split cache. They are
   dequeued and consumed in tdx_sept_split_private_spte().

   kvm_split_cross_boundary_leafs
     kvm_tdp_mmu_gfn_range_split_cross_boundary_leafs
       tdp_mmu_split_huge_pages_root
 (*)      1) tdp_mmu_alloc_sp_for_split()
  +-----2.1) need_topup_external_split_cache(): check if enough pages in
  |          the external split cache. Go to 3 if pages are enough.
  |  +--2.2) topup_external_split_cache(): preallocate/enqueue pages in
  |  |       the external split cache.
  |  |    3) tdp_mmu_split_huge_page
  |  |         tdp_mmu_link_sp
  |  |           tdp_mmu_iter_set_spte
  |  |(**)         tdp_mmu_set_spte
  |  |               split_external_spte
  |  |                 kvm_x86_call(split_external_spte)
  |  |                   tdx_sept_split_private_spte
  |  |                   3.1) BLOCK, TRACK
  +--+-------------------3.2) Dequeue PAMT pages from the external split
  |  |                        cache for the new sept page
  |  |                   3.3) PAMT_ADD for the new sept page
  +--+-------------------3.4) Dequeue PAMT pages from the external split
                              cache for the 2MB guest private memory.
                         3.5) DEMOTE.
                         3.6) Update PAMT refcount of the 2MB guest private
                              memory.

   (*) The write mmu_lock is held across the checking of enough pages in
       cache in step 2.1 and the page dequeuing in steps 3.2 and 3.4, so
       it's ensured that dequeuing has enough pages in cache.

  (**) A spinlock prealloc_split_cache_lock is used inside the TDX's cache
       implementation to protect page enqueuing in step 2.2 and page
       dequeuing in steps 3.2 and 3.4.
"

---

## [92] Huang, Kai — 2026-01-20
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Thu, 2025-11-27 at 10:38 +0800, Binbin Wu wrote:
> 
> On 11/27/2025 6:33 AM, Edgecombe, Rick P wrote:

But theoretically we don't need a pair of DPAMT pages for one 4K S-EPT
page -- we only need a pair for a entire 2M range.  If these S-EPT pages
in the fault path are allocated from the same 2M range, we are actually
over allocating DPAMT pages.

And AFAICT unfortunately there's no way to resolve this, unless we use
tdx_alloc_page() for S-EPT pages.

---

## [93] Yan Zhao — 2026-01-20
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Tue, Jan 20, 2026 at 03:10:59PM +0800, Huang, Kai wrote:
> On Thu, 2025-11-27 at 10:38 +0800, Binbin Wu wrote:
> > 
topup() always ensures that the min page count in cache is the max count of
pages a fault needs.

For example, mmu_topup_memory_caches() ensures there are at least
PT64_ROOT_MAX_LEVEL pages in mmu_page_header_cache, which are not always
consumed by each fault.

But in the worst-case conditions, we actually need that many.

In the end, the unused pages in cache will be freed by mmu_free_memory_caches().

> And AFAICT unfortunately there's no way to resolve this, unless we use
So, I don't think it's a problem.

And I agree with Binbin :)

> tdx_alloc_page() for S-EPT pages.

---

## [94] Huang, Kai — 2026-01-20
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

> 
> But in the worst-case conditions, we actually need that many.

Right.  Overcharging is not an issue, on the contrary, we need to make
sure there's enough pages so we really need to consider the worst case.

I am not sure what I was thinking :-)

---

## [95] Huang, Kai — 2026-01-20
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Mon, 2026-01-19 at 10:31 +0800, Yan Zhao wrote:
> On Fri, Jan 16, 2026 at 04:53:57PM -0800, Sean Christopherson wrote:
> > On Thu, Nov 20, 2025, Rick Edgecombe wrote:

Well I think it's for consistency, and IMHO you can even argue this is a
bug in the current code, because IIUC there's indeed one issue in the
current code.

When sp->spt is allocated via per-vCPU mmu_shadow_page_cache, it is
actually initialized to SHADOW_NONPRESENT_VALUE:

        vcpu->arch.mmu_shadow_page_cache.init_value =                    
                SHADOW_NONPRESENT_VALUE;                                 

So the way sp->spt is allocated in tdp_mmu_alloc_sp_for_split() is
actually broken IMHO because entries in sp->spt is never initialized.

Fortunately tdp_mmu_alloc_sp_for_split() isn't reachable for TDX guests,
so we are lucky so far.

A per-VM cache requires more code to handle, but to me I still think we
should just use the same way to allocate staff when possible, and that
includes spt->external_spt.

---

## [96] Yan Zhao — 2026-01-20
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Tue, Jan 20, 2026 at 04:42:37PM +0800, Huang, Kai wrote:
> On Mon, 2026-01-19 at 10:31 +0800, Yan Zhao wrote:
> > On Fri, Jan 16, 2026 at 04:53:57PM -0800, Sean Christopherson wrote:
The sp->spt allocated in tdp_mmu_alloc_sp_for_split() is initialized in
tdp_mmu_split_huge_page()...

> Fortunately tdp_mmu_alloc_sp_for_split() isn't reachable for TDX guests,
> so we are lucky so far.

---

## [97] Huang, Kai — 2026-01-20
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Tue, 2026-01-20 at 17:18 +0800, Yan Zhao wrote:
> > When sp->spt is allocated via per-vCPU mmu_shadow_page_cache, it is
> > actually initialized to SHADOW_NONPRESENT_VALUE:

Oh right, we already have a huge SPTE to copy from in this case, so no
problem here, but seems the inconsistency is still there to me.

---

## [98] Edgecombe, Rick P — 2026-01-20
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

Sean, really appreciate you taking a look despite being overbooked.

On Fri, 2026-01-16 at 16:53 -0800, Sean Christopherson wrote:
> NAK.  I kinda sorta get why you did this?  But the pages KVM uses for page tables
> are KVM's, not to be mixed with PAMT pages.

Ah, this is from the TDX huge pages series. There is a bit of fallout from TDX 
/coco's eternal nemesis: stacks of code all being co-designed at once.

Dave has been directing us recently to focus on only the needs of the current
series. Now that we can test at each incremental step we don't have the same
problems as before. But of course there is still desire for updated TDX huge
pages, etc to help with development of all the other WIP stuff.

For this design aspect of how the topup caches work for DPAMT, he asked
specifically for the DPAMT patches to *not* consider how TDX huge pages will use
them.

Now the TDX huge pages coverletter asked you to look at some aspects of that,
and traditionally KVM side has preferred to look at how the code is all going to
work together. The presentation of this was a bit rushed and confused, but
looking forward, how do you want to do this?

After the 130 patches ordeal, I'm a bit amenable to Dave's view. What do you
think?

> 
> But then in kvm_tdp_mmu_map(), via kvm_mmu_alloc_external_spt(), the allocation

Ah! Ok, we might have a good option here. Kai had suggested that instead of pre-
faulting all the pages that we might need for DPAMT backing, we pre-install the
DPAMT backing for all pages in the external page table cache at top-up time. It
has a complication for TDX huge pages, which needs to decide late if a page is
huge and needs dpamt backing or not, but based on Dave's direction above I gave
it a try. A downside for pure DPAMT was that it needed to handle the freeing
specially because it needed to potentially reclaim the DPAMT backing. This
required an x86 op for freeing these pages, and was a bit more code on the KVM
side in general.

But if the asymmetry is a problem either way, maybe I'll give it a try for v5. 

> 	free_page((unsigned long)sp->spt);
> 	kmem_cache_free(mmu_page_header_cache, sp);

---

## [99] Sean Christopherson — 2026-01-20
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Thu, Nov 20, 2025, Rick Edgecombe wrote:
>  static int tdx_topup_external_fault_cache(struct kvm_vcpu *vcpu, unsigned int cnt)
>  {

The caller passed in number of pages to be added as @cnt, don't hardcode what
could be conflicting information.  If the caller wants to add 50 pages, then this
code damn well needs to prepare for adding 50 pages, not 5.

---

## [100] Edgecombe, Rick P — 2026-01-21
*Subject: Re: [PATCH v4 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Tue, 2026-01-20 at 16:52 -0800, Sean Christopherson wrote:
> The caller passed in number of pages to be added as @cnt, don't hardcode what
> could be conflicting information.  If the caller wants to add 50 pages, then this

Doh, yes totally.

---

## [101] Sean Christopherson — 2026-01-21
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Tue, Jan 20, 2026, Rick P Edgecombe wrote:
> Sean, really appreciate you taking a look despite being overbooked.
> 

IMO, it's largely irrelevant for this discussion.  Bluntly, the code proposed
here is simply bad.  S-EPT hugepage support just makes it worse.

The core issue is that the ownership of the pre-allocation cache is split across
KVM and the TDX subsystem (and within KVM, between tdx.c and the MMU), which makes
it extremely difficult to understand who is responsible for what, which in turn
leads to brittle code, and sets the hugepage series up to fail, e.g. by unnecessarily
mixing S-EPT page allocation with PAMT maintenance.q

That aside, I generally agree with Dave.  The only caveat I'll throw in is that
I do think we need to _at least_ consider how things will likely play out when
all is said and done, otherwise we'll probably paint ourselves into a corner.
E.g. we don't need to know exactly how S-EPT hugepage support will interact with
DPAMT, but IMO we do need to be aware that KVM will need to demote pages outside
of vCPU context, and thus will need to pre-allocate pages for PAMT without having
a loaded/running vCPU.  That knowledge doesn't require active support in the
DPAMT series, but it most definitely influences design decisions.

---

## [102] Edgecombe, Rick P — 2026-01-21
*Subject: Re: [PATCH v4 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Wed, 2026-01-21 at 14:12 -0800, Sean Christopherson wrote:
> IMO, it's largely irrelevant for this discussion.  Bluntly, the code proposed
> here is simply bad.

FWIW, I wasn't ecstatic about it, but was starting to doubt we could find a
better solution after a string of failed POCs. Will take this feedback under
consideration for the future.

>   S-EPT hugepage support just makes it worse.
> 

...or require more extensive changes with relevant huge page related
justification, right? We are not defining uABI I think.

> 
> That aside, I generally agree with Dave.  

Ok.

> The only caveat I'll throw in is that
> I do think we need to _at least_ consider how things will likely play out when

Well this is the tricky part then.

> E.g. we don't need to know exactly how S-EPT hugepage support will interact with
> DPAMT, but IMO we do need to be aware that KVM will need to demote pages outside

I see what you are saying here though. It depends on how you look at it a bit.

---

## [103] Sean Christopherson — 2026-01-28
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

Gah, forgot to hit "send" on this.

On Wed, Nov 26, 2025, Rick P Edgecombe wrote:
> On Tue, 2025-11-25 at 16:09 +0800, Binbin Wu wrote:
> > On 11/21/2025 8:51 AM, Rick Edgecombe wrote:

Honestly, the entire scheme is a mess.  Four days of staring at this and I finally
undertand what the code is doing.  The whole "struct tdx_module_array_args" union
is completely unnecessary, the resulting args.args crud is ugly, having a pile of
duplicate accessors is brittle, the code obfuscates a simple concept, and the end
result doesn't provide any actual protection since the kernel will happily overflow
the buffer after the WARN.

It's also relying on the developer to correctly copy+paste the same register in
multiple locations: ~5 depending on how you want to count.

  static u64 *dpamt_args_array_ptr_r12(struct tdx_module_array_args *args)
                                   #1
  {
	WARN_ON_ONCE(tdx_dpamt_entry_pages() > MAX_TDX_ARGS(r12));
                                                            #2

	return &args->args_array[TDX_ARG_INDEX(r12)];
                                               #3


	u64 guest_memory_pamt_page[MAX_TDX_ARGS(r12)];
                                                #4


	u64 *args_array = dpamt_args_array_ptr_r12(&args);
                                                   #5

After all of that boilerplate, the caller _still_ has to do the actual memcpy(),
and for me at least, all of the above makes it _harder_ to understand what the code
is doing.

Drop the struct+union overlay and just provide a helper with wrappers to copy
to/from a tdx_module_args structure.  It's far from bulletproof, but it at least
avoids an immediate buffer overflow, and defers to the kernel owner with respect
to handling uninitialized stack data.

/*
 * For SEAMCALLs that pass a bundle of pages, the TDX spec treats the registers
 * like an array, as they are ordered in the struct.  The effective array size
 * is (obviously) limited by the number or registers, relative to the starting
 * register.  Fill the register array at a given starting register, with sanity
 * checks to avoid overflowing the args structure.
 */
static void dpamt_copy_regs_array(struct tdx_module_args *args, void *reg,
				  u64 *pamt_pa_array, bool copy_to_regs)
{
	int size = tdx_dpamt_entry_pages() * sizeof(*pamt_pa_array);

	if (WARN_ON_ONCE(reg + size > (void *)args) + sizeof(*args))
		return;

	/* Copy PAMT page PA's to/from the struct per the TDX ABI. */
	if (copy_to_regs)
		memcpy(reg, pamt_pa_array, size);
	else
		memcpy(pamt_pa_array, reg, size);
}

#define dpamt_copy_from_regs(dst, args, reg)	\
	dpamt_copy_regs_array(args, &(args)->reg, dst, false)

#define dpamt_copy_to_regs(args, reg, src)	\
	dpamt_copy_regs_array(args, &(args)->reg, src, true)

As far as the on-stack allocations go, why bother being precise?  Except for
paranoid setups which explicitly initialize the stack, "allocating" ~48 unused
bytes is literally free.  Not to mention the cost relative to the latency of a
SEAMCALL is in the noise.

/*
 * When declaring PAMT arrays on the stack, use the maximum theoretical number
 * of entries that can be squeezed into a SEAMCALL, as stack allocations are
 * practically free, i.e. any wasted space is a non-issue.
 */
#define MAX_NR_DPAMT_ARGS (sizeof(struct tdx_module_args) / sizeof(u64))


With that, callers don't have to regurgitate the same register multiple times,
and we don't need a new wrapper for every variation of SEAMCALL.  E.g.


	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];

	...

	bool dpamt = tdx_supports_dynamic_pamt(&tdx_sysinfo) && level == PG_LEVEL_2M;
	u64 pamt_pa_array[MAX_NR_DPAMT_ARGS];
	struct tdx_module_args args = {
		.rcx = gpa | pg_level_to_tdx_sept_level(level),
		.rdx = tdx_tdr_pa(td),
		.r8 = page_to_phys(new_sp),
	};
	u64 ret;

	if (!tdx_supports_demote_nointerrupt(&tdx_sysinfo))
		return TDX_SW_ERROR;

	if (dpamt) {
		if (alloc_pamt_array(pamt_pa_array, pamt_cache))
			return TDX_SW_ERROR;

		dpamt_copy_to_regs(&args, r12, pamt_pa_array);
	}

Which to me is easier to read and much more intuitive than:


	u64 guest_memory_pamt_page[MAX_TDX_ARGS(r12)];
	struct tdx_module_array_args args = {
		.args.rcx = gpa | pg_level_to_tdx_sept_level(level),
		.args.rdx = tdx_tdr_pa(td),
		.args.r8 = PFN_PHYS(page_to_pfn(new_sp)),
	};
	struct tdx_module_array_args retry_args;
	int i = 0;
	u64 ret;

	if (dpamt) {
		u64 *args_array = dpamt_args_array_ptr_r12(&args);

		if (alloc_pamt_array(guest_memory_pamt_page, pamt_cache))
			return TDX_SW_ERROR;

		/*
		 * Copy PAMT page PAs of the guest memory into the struct per the
		 * TDX ABI
		 */
		memcpy(args_array, guest_memory_pamt_page,
		       tdx_dpamt_entry_pages() * sizeof(*args_array));
	}

---

## [104] Edgecombe, Rick P — 2026-01-29
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Wed, 2026-01-28 at 17:19 -0800, Sean Christopherson wrote:
> Honestly, the entire scheme is a mess.  Four days of staring at this
> and I finally undertand what the code is doing.  The whole "struct

The original sin for this, as was spotted by Nikilay in v3, is actually
that it turns out that the whole variable length thing was intended to
give the TDX module flexibility *if* it wanted to increase it in the
future. As in it's not required today. Worse, whether it would actually
grow in the specific way the code assumes is not covered in the spec.
Apparently it was based on some past internal discussions. So the
agreement on v3 was to just support the fixed two page size in the
spec.

Here was the end of that thread:
https://lore.kernel.org/kvm/da3701ea-08ea-45c9-94a8-355205a45f8e@intel.com/

This simplifies the whole thing, no union, no worse case allocations,
etc. I'm just getting back and going through mail so will check out
your full solution. (Thanks!) But from the below I think the fixed
array size code will be better still.

> 
> It's also relying on the developer to correctly copy+paste the same

Yea it could probably use another DEFINE or two to make it less error
prone. Vanilla DPAMT has 4 instances of rdx.

> 
> After all of that boilerplate, the caller _still_ has to do the

What you have here is close to what I had done when I first took this
series. But it ran afoul of FORTIFY_SOUCE and required some horrible
casting to trick it. I wonder if this code will hit that issue too.
Dave didn't like the solution and suggested the union actually:
https://lore.kernel.org/kvm/355ad607-52ed-42cc-9a48-63aaa49f4c68@intel.com/#t

I'm aware of your tendency to dislike union based solutions. But since
this was purely contained to tip, I went with Dave's preference.

But I think it's all moot because the fixed size-2 solution doesn't
need union or array copying. They can be just normal tdx_module_args
args.

---

## [105] Sean Christopherson — 2026-01-29
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, Jan 29, 2026, Rick P Edgecombe wrote:
> On Wed, 2026-01-28 at 17:19 -0800, Sean Christopherson wrote:
> > Honestly, the entire scheme is a mess.  Four days of staring at this

Heh, I was _this_ close to suggesting we add a compile-time assert on the incoming
size of the array (and effective regs array), with a constant max size supported
by the kernel.  It wouldn't eliminate the array shenanigans, but it would let us
make them more or less bombproof.

> Yea it could probably use another DEFINE or two to make it less error
> prone. Vanilla DPAMT has 4 instances of rdx.

For me, it's not just a syntax problem.  It's the approach of getting a pointer
to the middle of structure and then doing a memcpy() at a later point in time.
More below.

> What you have here is close to what I had done when I first took this
> series. But it ran afoul of FORTIFY_SOUCE and required some horrible

AFAICT, FORTIFY_SOURCE doesn't complain.

> Dave didn't like the solution and suggested the union actually:
> https://lore.kernel.org/kvm/355ad607-52ed-42cc-9a48-63aaa49f4c68@intel.com/#t

What you proposed is fundamentally quite different than what I'm proposing.  I'm
not complaining about the union, I'm complaining about providing a helper to grab
a pointer to the middle of a struct and then open coding memcpy() calls using
that pointer.  I find that _extremely_ difficult to grok, because it does a poor
job of capturing the intent (copy these values to this sequence of registers).

The decouple pointer+memcpy() approach also bleeds gory details about how PAMT
pages are passed in multiple args throughout all SEAMCALL APIs that have such
args.  I want the APIs to not have to care about the underlying mechanics of how
PAMT pages are copied from an array to registers, e.g. so that readers of the
code can focus on the semantics of the SEAMCALL and the pieces of logic that are
unique to each SEAMCALL.

In other words, I see the necessity for a union as being a symptom of the flawed
approach.

> I'm aware of your tendency to dislike union based solutions. But since
> this was purely contained to tip, I went with Dave's preference.

---

## [106] Edgecombe, Rick P — 2026-01-29
*Subject: Re: [PATCH v4 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, 2026-01-29 at 11:09 -0800, Sean Christopherson wrote:
> What you proposed is fundamentally quite different than what I'm
> proposing.  I'm not complaining about the union, I'm complaining

Ah ok, fair enough.

---
