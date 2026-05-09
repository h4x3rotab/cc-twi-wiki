---
title: 'TDX: Enable Dynamic PAMT'
date: 2025-09-18
last_reply: 2025-10-15
message_count: 97
participants: ['Rick Edgecombe', 'Huang, Kai', 'Kiryl Shutsemau', 'Binbin Wu', 'Yan Zhao', 'Xiaoyao Li', 'Dave Hansen']
---

## [1] Rick Edgecombe — 2025-09-18

Hi,

This is 3rd revision of Dynamic PAMT, which is a new feature that reduces 
memory use of TDX.

On v2 (as well as in PUCK) there was some discussion of the 
refcount/locking design tradeoffs for Dynamic PAMT. In v2, I’ve basically 
gone through and tried to make the details around this more reviewable. 
The basic solution is the same as v2, with the changes more about moving 
code around or splitting implementations/optimizations. I’m hoping with 
this v3 we can close on whether that approach is good enough or not.

I think the patch quality is in ok shape, but still need some review. 
Maintainers, please feel free to let us go through this v3 for lower level 
code issues, but I would appreciate engagement on the overall design.

Another open still is performance testing, besides the bit about excluding 
contention of the global lock.

Lastly, Yan raised some last minute doubts internally about TDX module 
locking contention. I’m not sure there is a problem, but we can come to an 
agreement as part of the review.

PAMT Background
===============
The TDX module needs to keep data about each physical page it uses. It 
requires the kernel to give it memory to use for this purpose, called 
PAMT. Internally it wants space for metadata for each page *and* each page 
size. That is, if a page is mapped at 2MB in a TD, it doesn’t spread this 
tracking across the allocations it uses for 4KB page size usage of the 
same physical memory. It is designed to use a separate allocation for 
this.

So each memory region that the TDX module could use (aka TDMRs) has three 
of these PAMT allocations. They are all allocated during the global TDX 
initialization, regardless of if the memory is actually getting used for a 
TD. It uses up approximately 0.4% of system memory.

Dynamic PAMT (DPAMT)
====================
Fortunately, only using physical memory for areas of an address space that 
are actually in use is a familiar problem in system engineering, with a 
well trodden solution: page tables. It would be great if TDX could do 
something like that for PAMT. This is basically the idea for Dynamic PAMT.

However, there are some design aspects that could be surprising for anyone 
expecting “PAMT, but page tables”. The following describes these 
differences.

DPAMT Levels
------------
Dynamic PAMT focuses on the page size level that has the biggest PAMT 
allocation - 4KB page size. Since the 2MB and 1GB levels are smaller 
allocations, they are left as the fixed arrays, as in normal PAMT. But the 
4KB page sizes are actually not fully dynamic either, the TDX module still 
requires a physically contiguous space for tracking each 4KB page in a 
TDMR. But this space shrinks significantly, to currently 1 bit per page.

Page Sizes
----------
Like normal PAMT, Dynamic PAMT wants to provide a way for the TDX module 
to have separate PAMT tracking for different page sizes. But unlike normal 
PAMT, it does not seamlessly switch between the 2MB and 4KB page sizes 
without VMM action. It wants the PAMT mapped at the same level that the 
underlying TDX memory is using. In practice this means the VMM needs to 
update the PAMT depending on whether secure EPT pages are to be mapped at 
2MB or 4KB.

While demote/promote have internal handling for these updates (and support 
passing or returning the PAMT pages involved), PAGE.ADD/AUG don’t. Instead 
two new SEAMCALLs are provided for the VMM to configure the PAMT to the 
intended page size (i.e. 4KB if the page will be mapped at 4KB): 
TDH.PHYMEM.PAMT.ADD/REMOVE.

While some operations on TD memory can internally handle the PAMT 
adjustments, the opposite is not true. That is changes in PAMT don’t try 
to automatically change private S-EPT page sizes. Instead an attempt to 
remove 4KB size PAMT pages while will fail if any of the covering range are
in use.

Concurrency
-----------
For every 2MB physical range there could be many 4KB pages used by TDX 
(obviously). But each of those only needs one set of PAMT pages added. So 
on the first use of the 2MB region the DPAMT needs to be installed, and 
after none of the pages in that range are in use, it needs to be freed.

The TDX module actually does track how many pages are using each 2MB range 
and gives hints for refcount of zero. But it is incremented when the 2MB 
region use actually starts. Like:
1.  TDH.PHYMEM.PAMT.ADD (backing for
                         2MB range X,
                         for page Y)
2.  TDH.MEM.PAGE.AUG (page Y)        <- Increments refcount for X.
3.  TDH.MEM.PAGE.REMOVE (page Y)     <- Decrements refcount for X,
                                        gives hint in return value.
4.  TDH.PHYMEM.PAMT.REMOVE (range X) <- Remove, check that each 4KB
                                        page in X is free.

The internal refcount is tricky to use because of the window of time 
between TDH.PHYMEM.PAMT.ADD and TDH.MEM.PAGE.AUG. The PAMT.ADD adds the 
backing, but doesn’t tell the TDX module a VMM intends to map it. Consider 
the range X that includes page Y and Z, for an implementation that tries 
to use these hints:

CPU 0                              CPU 1
TDH.PHYMEM.PAMT.ADD X (returns
                       already
                       mapped)
                                   TDH.MEM.PAGE.REMOVE (Y) (returns
                                                            refcount 0
                                                            hint)
                                   TDH.PHYMEM.PAMT.REMOVE (X)
TDH.MEM.PAGE.AUG Z (fail)


So the TDX module’s DPAMT refcounts don't track what the VMM intends to do 
with the page, only what it has already done. This leaves a window that
needs to be covered.

TDX module locking
------------------
Inside the TDX module there are various locks. The TDX module does not 
wait when it encounters contention, instead it returns a BUSY error code. 
This leaves the VMM with an option to either loop around the SEAMCALL, or 
return an error to the calling code. In some cases in Linux there is not 
an option to return an error from the operation making the SEAMCALL. To 
avoid potentially an indeterminable amount of retries, it opts to kick all 
the threads associated with the TD out of the TDX module and retry. This 
retry operation is fairly easy to do from with KVM.

Since PAMT is a global resource, this means that this lock contention 
could be from any TD. For normal PAMT, the exclusive locks locks are only 
taken at the 4KB page size granularity. In practice, this means any page 
that is not shared  between TDs won’t have to worry about contention. 
However, for DPAMT this changes. The TDH.PHYMEM.PAMT.ADD/REMOVE calls take 
a PAMT lock at 2MB granularity. If two calls try to operate on the same 
2MB region at the same time, one will get the BUSY error code.


Linux Challenges
================
So for dynamic PAMT, Linux needs to:
 1. Allocate a different fixed sized allocation for each TDMR, for the 4KB
    page size (the 1 bit per page bitmap instead of the normal larger
    allocation)
 2. Allocate DPAMT for control structures.
 3. Allocate DPAMT 4KB page backings for all TD private memory (which is
    currently only 4KB) and S-EPT page tables.

1 is easy, just query the new size when DPAMT is in use and use that 
instead of the regular 4KB PAMT size. The bitmap allocation is even passed 
in the same field to the TDX module. If you takeaway the TDX docs naming 
around the bitmap, it’s like a buffer that changes size.

For 2 and 3, there is a lot to consider. For 2, it is relatively easy as 
long as we want to install PAMT on demand since these pages come straight 
from the page allocator and not guestmemfd.

For 3, upstream we currently only have 4KB pages, which means we could 
ignore a lot of the specifics about matching page sizes - there is only 
one. However, TDX huge pages is also in progress. So we should avoid a 
design that would need to be redone immediately.

Installing 4KB DPAMT backings
-----------------------------
Some TDX pages are used for TD control structures. These need to have new 
code to install 4KB DPAMT backings. But the main problem is how do this 
for private memory.

Linux needs to add the DPAMT backing private memory before the page gets 
mapped in the TD. Doing so inside the KVM MMU call paths adds 
complications around the BUSY error code, as described above. It would be 
tempting to install DPAMT pages from a guestmemfd callback. This could 
happen outside the KVM MMU locks.

But there are three complications with this. One is that in case of 2MB 
pages, the guest can control the page size. This means, even if 4KB page 
sizes are installed automatically, KVM would have to handle edge cases of 
PAMT adjustments at runtime anyway. For example memslot deletion and 
re-adding would trigger a zap of huge pages that are later remapped at 
4KB. This could *maybe* be worked around by some variant of this technique 
[0].

Another wrinkle is that Vishal@google has expressed a strong interest in 
saving PAMT memory at runtime in the case of 2MB TD private memory. He 
wants to support a use case where most TD memory is mapped at 2MB, so he 
wants to avoid the overhead of a worse case allocation that assumes all 
memory will be mapped at 4KB.

Finally, pre-installing DPAMT pages before the fault doesn’t help with 
mapping DPAMT pages for the external (S-EPT) page tables that are 
allocated for the fault. So some fault time logic is needed. We could 
pre-install DPAMT backing for the external page table cache, which would 
happen outside of the MMU lock. This would free us from having to update 
DPAMT inside MMU lock. But it would not free KVM from having to do 
anything around DPAMT during a fault.

Three non-show stopping issues tilts things towards using a fault time 
DPAMT installation approach for private memory.

Avoiding duplicate attempts to add/remove DPAMT 
-----------------------------------------------
As covered above, there isn’t a refcount in the TDX module that we can 
use. Using the hints returned by TDH.MEM.PAGE.AUG/REMOVE was tried in v1, 
and Kirill was unable to both overcome the races and make nice with new 
failure scenarios around DPAMT locks. So in v2 refcounts were allocated on 
the kernel side for each 2MB range covered by a TDMR (a range the TDX 
module might use). This adds some small memory overhead of 0.0002%, which 
is small compared to the 0.4% to 0.004% savings of Dynamic PAMT. The major 
downside is code complexity. These allocations are still large and involve 
managing vmalloc space. The v2 solution reserves a vmalloc space to cover 
the entire physical address space, and only maps pages for any ranges that 
are covered by a TDMR.

Avoiding contention
-------------------
As covered above, Linux needs to deal with getting BUSY error codes here. 
The allocation/mapping paths for all these pages can already handle 
failure, but the trickier case is the removal paths. As previously sparred 
with during the base series, TDX module expects to be able to fail these 
calls, but the kernel does not. Further, the refcounts can not act as a 
race free lock on their own. So some synchronization is needed before 
actually removing the DPAMT backings.

V2 of the series includes a global lock to be used around actual 
installation/removal of the DPAMT backing, combined with opportunistic 
checking outside the lock to avoid taking it most of the time. In testing, 
booting 10 16GB TDs, the lock only hit contention 1136 times, with 4ms 
waiting. This is very small for an operation that took 60s of wall time. 
So despite being an (ugly) global lock, the actual impact was small. It 
will probably further be reduced in the case of huge pages, where most of 
the time 4KB DPAMT installation will not be necessary.

Updates in v3
=============
Besides incorporating the feedback and general cleanups, the major design 
change was around how DPAMT backing pages are allocated in the fault path.

Allocating DPAMT pages in v2
----------------------------
In v2, there was a specific page cache added in the generic x86 KVM MMU 
for DPAMT pages. This was needed because much of the fault happens inside 
a spinlock. By the time the fault handler knows whether it needs to 
install DPAMT backing, it can no longer allocate pages. This is a common 
pattern in the KVM MMU, and so pages are pre-allocated before taking the 
MMU spinlock. This way they can be used later if needed.

But KVM’s page cache infrastructure is not easy to pass into the arch/86 
code and inside the global spin lock where the pages would be consumed. So 
instead it passed a pointer to a function inside KVM that it can call to 
allocate pages from the KVM page cache component. Since the control 
structures need DPAMT backing installed outside of the fault, the arch/x86 
code also had logic to allocate pages directly from the page allocator. 
Further, there were various resulting intermediate lists that had to be 
marshaled through the DPMAT allocation paths.

This was all a bit complicated to me.

Updates in v3
-------------
V3 redid the areas described above to try to simplify it.

The KVM MMU already has knowledge that TDX needs special memory allocated 
for S-EPT. From the fault handlers perspective, this could be seen as just 
more memory of the same type. So v3 just turns the external page table 
allocation to an x86 op, and provides another op to allocate from it. This 
is done as refactoring. Then when dynamic PAMT is added the extra pages 
can just be added from within the x86 op in TDX code.

For removing the function pointer callback scheme, the external page 
tables are switched to a dirt simple linked list based page cache. This is 
somewhat reinventing the wheel, but KVM’s kvm_mmu_memory_cache operations 
are not easy to expose to the core kernel, and also TDX doesn’t need much 
of the fanciness of initial values and things like that. Building it out 
of the kernels linked list is enough code reuse.

Today the TDX module needs 2 pages for 2MB region of 4KB size dynamic PAMT 
backing. It would be tempting to just pass two pages in, but the TDX 
module exposes the number of Dynamic PAMT pages it needs as a metadata 
value. So the size is technically variable. To handle this, the design 
just passes in the simple TDX page cache list in the calls that might need 
to allocate dynamic PAMT.

Considerations for v4
=====================
This solution seems workable. It isolated Dynamic PAMT to TDX code, and 
doesn’t introduce any extra constraints to generic x86 KVM code. But the 
refcounts and global lock in arch/x86 side of TDX are still ugly.

There has been some internal discussion about pursuing various schemes to 
avoid this. But before a potential redesign, I wanted to share the current 
version. Both to get feedback on the updates, and so we can consider how 
“good enough” the current design is.

Testing and branch
==================
Testing is a bit light currently. Just TDX selftests, simple TDX Linux
guest boot. The branch is here: 
https://github.com/intel/tdx/commits/dpamt_v3/

Based on kvm_x86/next (603c090664d3)

[0] https://lore.kernel.org/kvm/20250807094423.4644-1-yan.y.zhao@intel.com/

Kirill A. Shutemov (13):
  x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>
  x86/tdx: Add helpers to check return status codes
  x86/virt/tdx: Allocate page bitmap for Dynamic PAMT
  x86/virt/tdx: Allocate reference counters for PAMT memory
  x86/virt/tdx: Improve PAMT refcounters allocation for sparse memory
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
 arch/x86/coco/tdx/tdx.c                     |   6 +-
 arch/x86/include/asm/kvm-x86-ops.h          |   2 +
 arch/x86/include/asm/kvm_host.h             |  11 +-
 arch/x86/include/asm/shared/tdx.h           |   1 +
 arch/x86/include/asm/shared/tdx_errno.h     | 109 +++++
 arch/x86/include/asm/tdx.h                  |  76 ++-
 arch/x86/include/asm/tdx_global_metadata.h  |   1 +
 arch/x86/kvm/mmu/mmu.c                      |   4 +-
 arch/x86/kvm/mmu/mmu_internal.h             |   2 +-
 arch/x86/kvm/vmx/tdx.c                      | 157 ++++--
 arch/x86/kvm/vmx/tdx.h                      |   3 +-
 arch/x86/kvm/vmx/tdx_errno.h                |  40 --
 arch/x86/virt/vmx/tdx/tdx.c                 | 505 +++++++++++++++++---
 arch/x86/virt/vmx/tdx/tdx.h                 |   5 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |   3 +
 16 files changed, 766 insertions(+), 180 deletions(-)
 create mode 100644 arch/x86/include/asm/shared/tdx_errno.h
 delete mode 100644 arch/x86/kvm/vmx/tdx_errno.h

---

## [2] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Today there are two separate locations where TDX error codes are defined:
         arch/x86/include/asm/tdx.h
         arch/x86/kvm/vmx/tdx.h

They have some overlap that is already defined similarly. Reduce the
duplication and prepare to introduce some helpers for these error codes in
the central place by unifying them. Join them at:
        asm/shared/tdx_errno.h
...and update the headers that contained the duplicated definitions to
include the new unified header.

Opportunistically massage some comments. Also, adjust
_BITUL()->_BITULL() to address 32 bit build errors after the move.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v3:
 - Split from "x86/tdx: Consolidate TDX error handling" (Dave, Kai)
 - Write log (Rick)
 - Fix 32 bit build error
---
 arch/x86/include/asm/shared/tdx.h             |  1 +
 .../vmx => include/asm/shared}/tdx_errno.h    | 27 ++++++++++++++-----
 arch/x86/include/asm/tdx.h                    | 20 --------------
 arch/x86/kvm/vmx/tdx.h                        |  1 -
 4 files changed, 22 insertions(+), 27 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (66%)

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
similarity index 66%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/shared/tdx_errno.h
index 6ff4672c4181..f98924fe5198 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -1,14 +1,14 @@
 /* SPDX-License-Identifier: GPL-2.0 */
-/* architectural status code for SEAMCALL */
-
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
+#ifndef _X86_SHARED_TDX_ERRNO_H
+#define _X86_SHARED_TDX_ERRNO_H
 
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
@@ -17,6 +17,7 @@
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
+#define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
@@ -28,6 +29,20 @@
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
@@ -37,4 +52,4 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#endif /* _X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 7ddef3a69866..0e795e7c0b22 100644
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
index ca39a9391db1..f4e609a745ee 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -3,7 +3,6 @@
 #define __KVM_X86_VMX_TDX_H
 
 #include "tdx_arch.h"
-#include "tdx_errno.h"
 
 #ifdef CONFIG_KVM_INTEL_TDX
 #include "common.h"

---

## [3] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 02/16] x86/tdx: Add helpers to check return status codes*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The TDX error code has a complex structure. The upper 32 bits encode the
status code (higher level information), while the lower 32 bits provide
clues about the error, such as operand ID, CPUID leaf, MSR index, etc.

In practice, the kernel logic cares mostly about the status code. Whereas
the error details are more often dumped to warnings to be used as
debugging breadcrumbs. This results in a lot of code that masks the status
code and then checks the resulting value. Future code to support Dynamic
PAMT will add yet mode SEAMCALL error code checking. To prepare for this,
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
places (i.e. sc_retry_prerr()).

Finally, update the code that previously open coded the bit math to use
the helpers.

Link: https://lore.kernel.org/kvm/aJNycTvk1GEWgK_Q@google.com/
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v3:
 - Split from "x86/tdx: Consolidate TDX error handling" (Dave, Kai)
 - Change name from IS_TDX_ERR_FOO() to IS_TDX_FOO() after the
   conclusion to one of those naming debates. (Sean, Dave)
---
 arch/x86/coco/tdx/tdx.c                 |  6 +--
 arch/x86/include/asm/shared/tdx_errno.h | 54 ++++++++++++++++++++++++-
 arch/x86/include/asm/tdx.h              |  2 +-
 arch/x86/kvm/vmx/tdx.c                  | 44 +++++++++-----------
 arch/x86/virt/vmx/tdx/tdx.c             |  8 ++--
 5 files changed, 80 insertions(+), 34 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..96554748adaa 100644
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
@@ -316,7 +316,7 @@ static void reduce_unnecessary_ve(void)
 {
 	u64 err = tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
 
-	if (err == TDX_SUCCESS)
+	if (IS_TDX_SUCCESS(err))
 		return;
 
 	/*
diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index f98924fe5198..49ab7ecc7d54 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -2,8 +2,10 @@
 #ifndef _X86_SHARED_TDX_ERRNO_H
 #define _X86_SHARED_TDX_ERRNO_H
 
+#include <asm/trapnr.h>
+
 /* Upper 32 bit of the TDX error code encodes the status */
-#define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
+#define TDX_STATUS_MASK				0xFFFFFFFF00000000ULL
 
 /*
  * TDX SEAMCALL Status Codes
@@ -52,4 +54,54 @@
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
+static inline bool IS_TDX_SW_ERROR(u64 err)
+{
+	return (err & TDX_SW_ERROR) == TDX_SW_ERROR;
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
+	return (err & TDX_SEAMCALL_GP) == TDX_SEAMCALL_GP;
+}
+
+static inline bool IS_TDX_SEAMCALL_UD(u64 err)
+{
+	return (err & TDX_SEAMCALL_UD) == TDX_SEAMCALL_UD;
+}
+
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
+
+#endif /* __ASSEMBLER__ */
 #endif /* _X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 0e795e7c0b22..eedc479d23f5 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -94,7 +94,7 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 
 	do {
 		ret = func(fn, args);
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
+	} while (IS_TDX_RND_NO_ENTROPY(ret) && --retry);
 
 	return ret;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ff41d3d00380..a952c7b6a22d 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -207,12 +207,6 @@ static DEFINE_MUTEX(tdx_lock);
 
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
@@ -398,7 +392,7 @@ static void tdx_flush_vp(void *_arg)
 		 * migration.  No other thread uses TDVPR in those cases.
 		 */
 		err = tdh_vp_flush(&to_tdx(vcpu)->vp);
-		if (unlikely(err && err != TDX_VCPU_NOT_ASSOCIATED)) {
+		if (unlikely(!IS_TDX_VCPU_NOT_ASSOCIATED(err))) {
 			/*
 			 * This function is called in IPI context. Do not use
 			 * printk to avoid console semaphore.
@@ -455,7 +449,7 @@ static void smp_func_do_phymem_cache_wb(void *unused)
 	/*
 	 * TDH.PHYMEM.CACHE.WB flushes caches associated with any TDX private
 	 * KeyID on the package or core.  The TDX module may not finish the
-	 * cache flush but return TDX_INTERRUPTED_RESUMEABLE instead.  The
+	 * cache flush but return TDX_ERR_INTERRUPTED_RESUMEABLE instead.  The
 	 * kernel should retry it until it returns success w/o rescheduling.
 	 */
 	for (i = TDX_SEAMCALL_RETRIES; i > 0; i--) {
@@ -511,7 +505,7 @@ void tdx_mmu_release_hkid(struct kvm *kvm)
 	 * associations, as all vCPU fds have been released at this stage.
 	 */
 	err = tdh_mng_vpflushdone(&kvm_tdx->td);
-	if (err == TDX_FLUSHVP_NOT_DONE)
+	if (IS_TDX_FLUSHVP_NOT_DONE(err))
 		goto out;
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error(TDH_MNG_VPFLUSHDONE, err);
@@ -903,7 +897,7 @@ static __always_inline u32 tdx_to_vmx_exit_reason(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u32 exit_reason;
 
-	switch (tdx->vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) {
+	switch (TDX_STATUS(tdx->vp_enter_ret)) {
 	case TDX_SUCCESS:
 	case TDX_NON_RECOVERABLE_VCPU:
 	case TDX_NON_RECOVERABLE_TD:
@@ -977,7 +971,7 @@ static fastpath_t tdx_exit_handlers_fastpath(struct kvm_vcpu *vcpu)
 	 * EXIT_FASTPATH_REENTER_GUEST to exit fastpath, otherwise, the
 	 * requester may be blocked endlessly.
 	 */
-	if (unlikely(tdx_operand_busy(vp_enter_ret)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(vp_enter_ret)))
 		return EXIT_FASTPATH_EXIT_HANDLED;
 
 	return EXIT_FASTPATH_NONE;
@@ -1074,7 +1068,7 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	if (unlikely(tdx->vp_enter_ret == EXIT_REASON_EPT_MISCONFIG))
 		return EXIT_FASTPATH_NONE;
 
-	if (unlikely((tdx->vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR))
+	if (unlikely(IS_TDX_SW_ERROR(tdx->vp_enter_ret)))
 		return EXIT_FASTPATH_NONE;
 
 	if (unlikely(vmx_get_exit_reason(vcpu).basic == EXIT_REASON_MCE_DURING_VMENTRY))
@@ -1606,7 +1600,7 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	u64 err;
 
 	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, tdx_level, page, &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err))) {
+	if (unlikely(IS_TDX_OPERAND_BUSY(err))) {
 		tdx_unpin(kvm, page);
 		return -EBUSY;
 	}
@@ -1697,7 +1691,7 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
 	err = tdh_mem_page_remove(&kvm_tdx->td, gpa, tdx_level, &entry,
 				  &level_state);
 
-	if (unlikely(tdx_operand_busy(err))) {
+	if (unlikely(IS_TDX_OPERAND_BUSY(err))) {
 		/*
 		 * The second retry is expected to succeed after kicking off all
 		 * other vCPUs and prevent them from invoking TDH.VP.ENTER.
@@ -1734,7 +1728,7 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level, page, &entry,
 			       &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(IS_TDX_OPERAND_BUSY(err)))
 		return -EBUSY;
 
 	if (KVM_BUG_ON(err, kvm)) {
@@ -1791,7 +1785,7 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
 
-	if (unlikely(tdx_operand_busy(err))) {
+	if (unlikely(IS_TDX_OPERAND_BUSY(err))) {
 		/* After no vCPUs enter, the second retry is expected to succeed */
 		tdx_no_vcpus_enter_start(kvm);
 		err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
@@ -1847,7 +1841,7 @@ static void tdx_track(struct kvm *kvm)
 	lockdep_assert_held_write(&kvm->mmu_lock);
 
 	err = tdh_mem_track(&kvm_tdx->td);
-	if (unlikely(tdx_operand_busy(err))) {
+	if (unlikely(IS_TDX_OPERAND_BUSY(err))) {
 		/* After no vCPUs enter, the second retry is expected to succeed */
 		tdx_no_vcpus_enter_start(kvm);
 		err = tdh_mem_track(&kvm_tdx->td);
@@ -2068,7 +2062,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	 * Handle TDX SW errors, including TDX_SEAMCALL_UD, TDX_SEAMCALL_GP and
 	 * TDX_SEAMCALL_VMFAILINVALID.
 	 */
-	if (unlikely((vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR)) {
+	if (unlikely(IS_TDX_SW_ERROR(vp_enter_ret))) {
 		KVM_BUG_ON(!kvm_rebooting, vcpu->kvm);
 		goto unhandled_exit;
 	}
@@ -2079,7 +2073,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 		 * not enabled, TDX_NON_RECOVERABLE must be set.
 		 */
 		WARN_ON_ONCE(vcpu->arch.guest_state_protected &&
-				!(vp_enter_ret & TDX_NON_RECOVERABLE));
+			     !IS_TDX_NON_RECOVERABLE(vp_enter_ret));
 		vcpu->run->exit_reason = KVM_EXIT_FAIL_ENTRY;
 		vcpu->run->fail_entry.hardware_entry_failure_reason = exit_reason.full;
 		vcpu->run->fail_entry.cpu = vcpu->arch.last_vmentry_cpu;
@@ -2093,7 +2087,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	}
 
 	WARN_ON_ONCE(exit_reason.basic != EXIT_REASON_TRIPLE_FAULT &&
-		     (vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) != TDX_SUCCESS);
+		     !IS_TDX_SUCCESS(vp_enter_ret));
 
 	switch (exit_reason.basic) {
 	case EXIT_REASON_TRIPLE_FAULT:
@@ -2540,7 +2534,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	err = tdh_mng_create(&kvm_tdx->td, kvm_tdx->hkid);
 	mutex_unlock(&tdx_lock);
 
-	if (err == TDX_RND_NO_ENTROPY) {
+	if (IS_TDX_RND_NO_ENTROPY(err)) {
 		ret = -EAGAIN;
 		goto free_packages;
 	}
@@ -2582,7 +2576,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	kvm_tdx->td.tdcs_pages = tdcs_pages;
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
 		err = tdh_mng_addcx(&kvm_tdx->td, tdcs_pages[i]);
-		if (err == TDX_RND_NO_ENTROPY) {
+		if (IS_TDX_RND_NO_ENTROPY(err)) {
 			/* Here it's hard to allow userspace to retry. */
 			ret = -EAGAIN;
 			goto teardown;
@@ -2595,7 +2589,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	}
 
 	err = tdh_mng_init(&kvm_tdx->td, __pa(td_params), &rcx);
-	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_INVALID) {
+	if (IS_TDX_OPERAND_INVALID(err)) {
 		/*
 		 * Because a user gives operands, don't warn.
 		 * Return a hint to the user because it's sometimes hard for the
@@ -2888,7 +2882,7 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 		return -EINVAL;
 
 	cmd->hw_error = tdh_mr_finalize(&kvm_tdx->td);
-	if (tdx_operand_busy(cmd->hw_error))
+	if (IS_TDX_OPERAND_BUSY(cmd->hw_error))
 		return -EBUSY;
 	if (KVM_BUG_ON(cmd->hw_error, kvm)) {
 		pr_tdx_error(TDH_MR_FINALIZE, cmd->hw_error);
@@ -3209,7 +3203,7 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
 			       src_page, &entry, &level_state);
 	if (err) {
-		ret = unlikely(tdx_operand_busy(err)) ? -EBUSY : -EIO;
+		ret = unlikely(IS_TDX_OPERAND_BUSY(err)) ? -EBUSY : -EIO;
 		goto out;
 	}
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c7a9a087ccaf..e962fffa73a6 100644
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

## [4] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

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
v3:
 - New patch
---
 arch/x86/virt/vmx/tdx/tdx.c | 69 ++++++++++---------------------------
 1 file changed, 18 insertions(+), 51 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index e962fffa73a6..38dae825bbb9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -445,30 +445,16 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
  * PAMT size is always aligned up to 4K page boundary.
  */
 static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-				      u16 pamt_entry_size)
+				      u16 pamt_entry_size[])
 {
 	unsigned long pamt_sz, nr_pamt_entries;
+	const int tdx_pg_size_shift[] = { PAGE_SHIFT, PMD_SHIFT, PUD_SHIFT };
 
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
@@ -509,25 +495,19 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 			    struct list_head *tmb_list,
 			    u16 pamt_entry_size[])
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
+	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K, pamt_entry_size);
+	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M, pamt_entry_size);
+	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G, pamt_entry_size);
+	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
 
 	/*
 	 * Allocate one chunk of physically contiguous memory for all
@@ -535,26 +515,16 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * in overlapped TDMRs.
 	 */
 	pamt = alloc_contig_pages(tdmr_pamt_size >> PAGE_SHIFT, GFP_KERNEL,
-			nid, &node_online_map);
-	if (!pamt)
+				  nid, &node_online_map);
+	if (!pamt) {
+		/* Zero base so that the error path will skip freeing. */
+		tdmr->pamt_4k_base = 0;
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
@@ -585,10 +555,7 @@ static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 	tdmr_get_pamt(tdmr, &pamt_base, &pamt_size);
 
 	/* Do nothing if PAMT hasn't been allocated for this TDMR */
-	if (!pamt_size)
-		return;
-
-	if (WARN_ON_ONCE(!pamt_base))
+	if (!pamt_base)
 		return;
 
 	pamt_func(pamt_base, pamt_size);

---

## [5] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic PAMT*

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
v3:
 - Simplify pamt_4k_size calculation after addition of refactor patch
 - Write log
---
 arch/x86/include/asm/tdx.h                  |  5 +++++
 arch/x86/include/asm/tdx_global_metadata.h  |  1 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 19 ++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  3 +++
 4 files changed, 27 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index eedc479d23f5..b9bb052f4daa 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -107,6 +107,11 @@ int tdx_enable(void);
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
index 38dae825bbb9..4e4aa8927550 100644
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
+	return ALIGN(pamt_sz, PAGE_SIZE);
+}
+
 /*
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
@@ -504,7 +516,12 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * Calculate the PAMT size for each TDX supported page size
 	 * and the total PAMT size.
 	 */
-	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K, pamt_entry_size);
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		/* With Dynamic PAMT, PAMT_4K is replaced with a bitmap */
+		tdmr->pamt_4k_size = tdmr_get_pamt_bitmap_sz(tdmr);
+	} else {
+		tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K, pamt_entry_size);
+	}
 	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M, pamt_entry_size);
 	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G, pamt_entry_size);
 	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..683925bcc9eb 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -33,6 +33,9 @@ static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 		sysinfo_tdmr->pamt_2m_entry_size = val;
 	if (!ret && !(ret = read_sys_metadata_field(0x9100000100000012, &val)))
 		sysinfo_tdmr->pamt_1g_entry_size = val;
+	if (!ret && tdx_supports_dynamic_pamt(&tdx_sysinfo) &&
+	    !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
+		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;
 
 	return ret;
 }

---

## [6] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 05/16] x86/virt/tdx: Allocate reference counters for PAMT memory*

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
where the entire 52 address space is covered this would be 8GB. Then
the DPAMT refcount allocations could hypothetically exceed the savings
from Dynamic PAMT, which is 4GB per TB. This is probably unlikely.

However, future changes will reduce this refcount overhead to make DPAMT
always a net win.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[Add feedback, update log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v3:
 - Split out lazily populate optimization to next patch (Dave)
 - Add comment around pamt_refcounts (Dave)
 - Improve log
---
 arch/x86/virt/vmx/tdx/tdx.c | 47 ++++++++++++++++++++++++++++++++++++-
 1 file changed, 46 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4e4aa8927550..0ce4181ca352 100644
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
+	size_t size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	pamt_refcounts = vmalloc(size);
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
@@ -1074,10 +1113,14 @@ static int init_tdx_module(void)
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

## [7] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters allocation for sparse memory*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

init_pamt_metadata() allocates PAMT refcounters for all physical memory up
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
 arch/x86/virt/vmx/tdx/tdx.c | 120 ++++++++++++++++++++++++++++++++----
 1 file changed, 109 insertions(+), 11 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0ce4181ca352..d4b01656759a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -194,30 +194,119 @@ int tdx_cpu_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_cpu_enable);
 
-/*
- * Allocate PAMT reference counters for all physical memory.
- *
- * It consumes 2MiB for every 1TiB of physical memory.
- */
-static int init_pamt_metadata(void)
+/* Find PAMT refcount for a given physical address */
+static atomic_t *tdx_find_pamt_refcount(unsigned long hpa)
 {
-	size_t size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+	return &pamt_refcounts[hpa / PMD_SIZE];
+}
 
-	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
-		return 0;
+/* Map a page into the PAMT refcount vmalloc region */
+static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)
+{
+	struct page *page;
+	pte_t entry;
 
-	pamt_refcounts = vmalloc(size);
-	if (!pamt_refcounts)
+	page = alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!page)
 		return -ENOMEM;
 
+	entry = mk_pte(page, PAGE_KERNEL);
+
+	spin_lock(&init_mm.page_table_lock);
+	/*
+	 * PAMT refcount populations can overlap due to rounding of the
+	 * start/end pfn. Make sure another PAMT range didn't already
+	 * populate it.
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
+	unsigned long start, end;
+
+	start = (unsigned long)tdx_find_pamt_refcount(PFN_PHYS(start_pfn));
+	end   = (unsigned long)tdx_find_pamt_refcount(PFN_PHYS(end_pfn + 1));
+	start = round_down(start, PAGE_SIZE);
+	end   = round_up(end, PAGE_SIZE);
+
+	return apply_to_page_range(&init_mm, start, end - start,
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
+	size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+	size = round_up(size, PAGE_SIZE);
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
+	/* refount allocation is sparse, may not be populated */
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
@@ -288,10 +377,19 @@ static int build_tdx_memlist(struct list_head *tmb_list)
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

## [8] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

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
 arch/x86/include/asm/tdx.h  |   6 +
 arch/x86/virt/vmx/tdx/tdx.c | 216 ++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |   2 +
 3 files changed, 224 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index b9bb052f4daa..439dd5c5282e 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -116,6 +116,12 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
+int tdx_pamt_get(struct page *page);
+void tdx_pamt_put(struct page *page);
+
+struct page *tdx_alloc_page(void);
+void tdx_free_page(struct page *page);
+
 struct tdx_td {
 	/* TD root structure: */
 	struct page *tdr_page;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index d4b01656759a..af73b6c2e917 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1997,3 +1997,219 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+
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
+#define MAX_DPAMT_ARG_SIZE (sizeof(struct tdx_module_args) - \
+			    offsetof(struct tdx_module_args, rdx))
+
+/*
+ * Treat struct the registers like an array that starts at RDX, per
+ * TDX spec. Do some sanitychecks, and return an indexable type.
+ */
+static u64 *dpamt_args_array_ptr(struct tdx_module_args *args)
+{
+	WARN_ON_ONCE(tdx_dpamt_entry_pages() > MAX_DPAMT_ARG_SIZE);
+
+	/*
+	 * FORTIFY_SOUCE could inline this and complain when callers copy
+	 * across fields, which is exactly what this is supposed to be
+	 * used for. Obfuscate it.
+	 */
+	return (u64 *)((u8 *)args + offsetof(struct tdx_module_args, rdx));
+}
+
+static int alloc_pamt_array(u64 *pa_array)
+{
+	struct page *page;
+
+	for (int i = 0; i < tdx_dpamt_entry_pages(); i++) {
+		page = alloc_page(GFP_KERNEL);
+		if (!page)
+			return -ENOMEM;
+		pa_array[i] = page_to_phys(page);
+	}
+
+	return 0;
+}
+
+static void free_pamt_array(u64 *pa_array)
+{
+	for (int i = 0; i < tdx_dpamt_entry_pages(); i++) {
+		if (!pa_array[i])
+			break;
+
+		reset_tdx_pages(pa_array[i], PAGE_SIZE);
+
+		/*
+		 * It might have come from 'prealloc', but this is an error
+		 * path. Don't be fancy, just free them. TDH.PHYMEM.PAMT.ADD
+		 * only modifies RAX, so the encoded array is still in place.
+		 */
+		__free_page(phys_to_page(pa_array[i]));
+	}
+}
+
+/*
+ * Add PAMT memory for the given HPA. Return's negative error code
+ * for kernel side error conditions (-ENOMEM) and 1 for TDX Module
+ * error. In the case of TDX module error, the return code is stored
+ * in tdx_err.
+ */
+static u64 tdh_phymem_pamt_add(unsigned long hpa, u64 *pamt_pa_array)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	u64 *args_array = dpamt_args_array_ptr(&args);
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	/* Copy PAMT page PA's into the struct per the TDX ABI */
+	memcpy(args_array, pamt_pa_array,
+	       tdx_dpamt_entry_pages() * sizeof(*args_array));
+
+	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+}
+
+/* Remove PAMT memory for the given HPA */
+static u64 tdh_phymem_pamt_remove(unsigned long hpa, u64 *pamt_pa_array)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	u64 *args_array = dpamt_args_array_ptr(&args);
+	u64 ret;
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	ret = seamcall_ret(TDH_PHYMEM_PAMT_REMOVE, &args);
+	if (ret)
+		return ret;
+
+	/* Copy PAMT page PA's out of the struct per the TDX ABI */
+	memcpy(pamt_pa_array, args_array,
+	       tdx_dpamt_entry_pages() * sizeof(u64));
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
+	unsigned long hpa = ALIGN_DOWN(page_to_phys(page), PMD_SIZE);
+	u64 pamt_pa_array[MAX_DPAMT_ARG_SIZE];
+	atomic_t *pamt_refcount;
+	u64 tdx_status;
+	int ret;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	ret = alloc_pamt_array(pamt_pa_array);
+	if (ret)
+		return ret;
+
+	pamt_refcount = tdx_find_pamt_refcount(hpa);
+
+	scoped_guard(spinlock, &pamt_lock) {
+		if (atomic_read(pamt_refcount))
+			goto out_free;
+
+		tdx_status = tdh_phymem_pamt_add(hpa | TDX_PS_2M, pamt_pa_array);
+
+		if (IS_TDX_SUCCESS(tdx_status)) {
+			atomic_inc(pamt_refcount);
+		} else {
+			pr_err("TDH_PHYMEM_PAMT_ADD failed: %#llx\n", tdx_status);
+			goto out_free;
+		}
+	}
+
+	return ret;
+out_free:
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
+	unsigned long hpa = ALIGN_DOWN(page_to_phys(page), PMD_SIZE);
+	u64 pamt_pa_array[MAX_DPAMT_ARG_SIZE];
+	atomic_t *pamt_refcount;
+	u64 tdx_status;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	hpa = ALIGN_DOWN(hpa, PMD_SIZE);
+
+	pamt_refcount = tdx_find_pamt_refcount(hpa);
+
+	scoped_guard(spinlock, &pamt_lock) {
+		if (!atomic_read(pamt_refcount))
+			return;
+
+		tdx_status = tdh_phymem_pamt_remove(hpa | TDX_PS_2M, pamt_pa_array);
+
+		if (IS_TDX_SUCCESS(tdx_status)) {
+			atomic_dec(pamt_refcount);
+		} else {
+			pr_err("TDH_PHYMEM_PAMT_REMOVE failed: %#llx\n", tdx_status);
+			return;
+		}
+	}
+
+	free_pamt_array(pamt_pa_array);
+}
+EXPORT_SYMBOL_GPL(tdx_pamt_put);
+
+/* Allocate a page and make sure it is backed by PAMT memory */
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
+/* Free a page and release its PAMT memory */
+void tdx_free_page(struct page *page)
+{
+	if (!page)
+		return;
+
+	tdx_pamt_put(page);
+	__free_page(page);
+}
+EXPORT_SYMBOL_GPL(tdx_free_page);
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

## [9] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 08/16] x86/virt/tdx: Optimize tdx_alloc/free_page() helpers*

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
tdx_pamt_put() goes 1->0 outside the lock, but tdx_pamt_put() does 0-1
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
v3:
 - Split out optimization from “x86/virt/tdx: Add tdx_alloc/free_page() helpers”
 - Remove edge case handling that I could not find a reason for
 - Write log
---
 arch/x86/include/asm/shared/tdx_errno.h |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c             | 46 +++++++++++++++++++++----
 2 files changed, 42 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index 49ab7ecc7d54..4bc0b9c9e82b 100644
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
@@ -100,6 +101,7 @@ DEFINE_TDX_ERRNO_HELPER(TDX_SUCCESS);
 DEFINE_TDX_ERRNO_HELPER(TDX_RND_NO_ENTROPY);
 DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_INVALID);
 DEFINE_TDX_ERRNO_HELPER(TDX_OPERAND_BUSY);
+DEFINE_TDX_ERRNO_HELPER(TDX_HPA_RANGE_NOT_FREE);
 DEFINE_TDX_ERRNO_HELPER(TDX_VCPU_NOT_ASSOCIATED);
 DEFINE_TDX_ERRNO_HELPER(TDX_FLUSHVP_NOT_DONE);
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index af73b6c2e917..c25e238931a7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2117,7 +2117,7 @@ int tdx_pamt_get(struct page *page)
 	u64 pamt_pa_array[MAX_DPAMT_ARG_SIZE];
 	atomic_t *pamt_refcount;
 	u64 tdx_status;
-	int ret;
+	int ret = 0;
 
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
@@ -2128,14 +2128,40 @@ int tdx_pamt_get(struct page *page)
 
 	pamt_refcount = tdx_find_pamt_refcount(hpa);
 
+	if (atomic_inc_not_zero(pamt_refcount))
+		goto out_free;
+
 	scoped_guard(spinlock, &pamt_lock) {
-		if (atomic_read(pamt_refcount))
+		/*
+		 * Lost race to other tdx_pamt_add(). Other task has already allocated
+		 * PAMT memory for the HPA.
+		 */
+		if (atomic_read(pamt_refcount)) {
+			atomic_inc(pamt_refcount);
 			goto out_free;
+		}
 
 		tdx_status = tdh_phymem_pamt_add(hpa | TDX_PS_2M, pamt_pa_array);
 
 		if (IS_TDX_SUCCESS(tdx_status)) {
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
 			atomic_inc(pamt_refcount);
+			goto out_free;
 		} else {
 			pr_err("TDH_PHYMEM_PAMT_ADD failed: %#llx\n", tdx_status);
 			goto out_free;
@@ -2167,15 +2193,23 @@ void tdx_pamt_put(struct page *page)
 
 	pamt_refcount = tdx_find_pamt_refcount(hpa);
 
+	/*
+	 * Unlike the paired call in tdx_pamt_get(), decrement the refcount
+	 * outside the lock even if it's not the special 0<->1 transition.
+	 * See special logic around HPA_RANGE_NOT_FREE in tdx_pamt_get().
+	 */
+	if (!atomic_dec_and_test(pamt_refcount))
+		return;
+
 	scoped_guard(spinlock, &pamt_lock) {
-		if (!atomic_read(pamt_refcount))
+		/* Lost race with tdx_pamt_get() */
+		if (atomic_read(pamt_refcount))
 			return;
 
 		tdx_status = tdh_phymem_pamt_remove(hpa | TDX_PS_2M, pamt_pa_array);
 
-		if (IS_TDX_SUCCESS(tdx_status)) {
-			atomic_dec(pamt_refcount);
-		} else {
+		if (!IS_TDX_SUCCESS(tdx_status)) {
+			atomic_inc(pamt_refcount);
 			pr_err("TDH_PHYMEM_PAMT_REMOVE failed: %#llx\n", tdx_status);
 			return;
 		}

---

## [10] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 09/16] KVM: TDX: Allocate PAMT memory for TD control structures*

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
index a952c7b6a22d..40c2730ea2ac 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2482,7 +2482,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	atomic_inc(&nr_configured_hkid);
 
-	tdr_page = alloc_page(GFP_KERNEL);
+	tdr_page = tdx_alloc_page();
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2495,7 +2495,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL);
+		tdcs_pages[i] = tdx_alloc_page();
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2616,10 +2616,8 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
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
@@ -2635,15 +2633,13 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
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
 	kvm_tdx->td.tdr_page = 0;
 
 free_hkid:

---

## [11] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 10/16] KVM: TDX: Allocate PAMT memory for vCPU control structures*

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
index 40c2730ea2ac..dd2be7bedd48 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2941,7 +2941,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL);
+	page = tdx_alloc_page();
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2954,7 +2954,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL);
+		page = tdx_alloc_page();
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;
@@ -2978,7 +2978,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 			 * method, but the rest are freed here.
 			 */
 			for (; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-				__free_page(tdx->vp.tdcx_pages[i]);
+				tdx_free_page(tdx->vp.tdcx_pages[i]);
 				tdx->vp.tdcx_pages[i] = NULL;
 			}
 			return -EIO;
@@ -2997,16 +2997,14 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 
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
 	tdx->vp.tdvpr_page = 0;
 
 	return ret;

---

## [12] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

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
Further, these pages will need to be handed to the arch/86 side which used
them for DPAMT updates, which is hard for the existing KVM based cache.
The details living in core MMU code start to add up.

So in preparation to make it more complicated, move the external page
table cache into TDX code by putting it behind some x86 ops. Have one for
topping up and one for allocation. Don’t go so far to try to hide the
existence of external page tables completely from the generic MMU, as they
are currently stores in their mirror struct kvm_mmu_page and it’s quite
handy.

To plumb the memory cache operations through tdx.c, export some of
the functions temporarily. This will be removed in future changes.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v3:
 - New patch
---
 arch/x86/include/asm/kvm-x86-ops.h |  2 ++
 arch/x86/include/asm/kvm_host.h    | 11 ++++++-----
 arch/x86/kvm/mmu/mmu.c             |  4 +---
 arch/x86/kvm/mmu/mmu_internal.h    |  2 +-
 arch/x86/kvm/vmx/tdx.c             | 17 +++++++++++++++++
 arch/x86/kvm/vmx/tdx.h             |  2 ++
 virt/kvm/kvm_main.c                |  2 ++
 7 files changed, 31 insertions(+), 9 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 62c3e4de3303..a4e4c1333224 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -98,6 +98,8 @@ KVM_X86_OP_OPTIONAL(link_external_spt)
 KVM_X86_OP_OPTIONAL(set_external_spte)
 KVM_X86_OP_OPTIONAL(free_external_spt)
 KVM_X86_OP_OPTIONAL(remove_external_spte)
+KVM_X86_OP_OPTIONAL(alloc_external_fault_cache)
+KVM_X86_OP_OPTIONAL(topup_external_fault_cache)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index cb86f3cca3e9..e4cf0f40c757 100644
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
@@ -1856,6 +1851,12 @@ struct kvm_x86_ops {
 	int (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				    kvm_pfn_t pfn_for_gfn);
 
+	/* Allocation a pages from the external page cache. */
+	void *(*alloc_external_fault_cache)(struct kvm_vcpu *vcpu);
+
+	/* Top up extra pages needed for faulting in external page tables. */
+	int (*topup_external_fault_cache)(struct kvm_vcpu *vcpu);
+
 	bool (*has_wbinvd_exit)(void);
 
 	u64 (*get_l2_tsc_offset)(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 55335dbd70ce..b3feaee893b2 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -601,8 +601,7 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 	if (r)
 		return r;
 	if (kvm_has_mirrored_tdp(vcpu->kvm)) {
-		r = kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_external_spt_cache,
-					       PT64_ROOT_MAX_LEVEL);
+		r = kvm_x86_call(topup_external_fault_cache)(vcpu);
 		if (r)
 			return r;
 	}
@@ -625,7 +624,6 @@ static void mmu_free_memory_caches(struct kvm_vcpu *vcpu)
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_pte_list_desc_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadow_page_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadowed_info_cache);
-	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_external_spt_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_page_header_cache);
 }
 
diff --git a/arch/x86/kvm/mmu/mmu_internal.h b/arch/x86/kvm/mmu/mmu_internal.h
index ed5c01df21ba..1fa94ab100be 100644
--- a/arch/x86/kvm/mmu/mmu_internal.h
+++ b/arch/x86/kvm/mmu/mmu_internal.h
@@ -175,7 +175,7 @@ static inline void kvm_mmu_alloc_external_spt(struct kvm_vcpu *vcpu, struct kvm_
 	 * Therefore, KVM does not need to initialize or access external_spt.
 	 * KVM only interacts with sp->spt for private EPT operations.
 	 */
-	sp->external_spt = kvm_mmu_memory_cache_alloc(&vcpu->arch.mmu_external_spt_cache);
+	sp->external_spt = kvm_x86_call(alloc_external_fault_cache)(vcpu);
 }
 
 static inline gfn_t kvm_gfn_root_bits(const struct kvm *kvm, const struct kvm_mmu_page *root)
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index dd2be7bedd48..6c9e11be9705 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1590,6 +1590,21 @@ static void tdx_unpin(struct kvm *kvm, struct page *page)
 	put_page(page);
 }
 
+static void *tdx_alloc_external_fault_cache(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+
+	return kvm_mmu_memory_cache_alloc(&tdx->mmu_external_spt_cache);
+}
+
+static int tdx_topup_external_fault_cache(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+
+	return kvm_mmu_topup_memory_cache(&tdx->mmu_external_spt_cache,
+					  PT64_ROOT_MAX_LEVEL);
+}
+
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 			    enum pg_level level, struct page *page)
 {
@@ -3647,4 +3662,6 @@ void __init tdx_hardware_setup(void)
 	vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
 	vt_x86_ops.remove_external_spte = tdx_sept_remove_private_spte;
 	vt_x86_ops.protected_apic_has_interrupt = tdx_protected_apic_has_interrupt;
+	vt_x86_ops.topup_external_fault_cache = tdx_topup_external_fault_cache;
+	vt_x86_ops.alloc_external_fault_cache = tdx_alloc_external_fault_cache;
 }
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index f4e609a745ee..cd7993ef056e 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -70,6 +70,8 @@ struct vcpu_tdx {
 
 	u64 map_gpa_next;
 	u64 map_gpa_end;
+
+	struct kvm_mmu_memory_cache mmu_external_spt_cache;
 };
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err);
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index fee108988028..f05e6d43184b 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -404,6 +404,7 @@ int kvm_mmu_topup_memory_cache(struct kvm_mmu_memory_cache *mc, int min)
 {
 	return __kvm_mmu_topup_memory_cache(mc, KVM_ARCH_NR_OBJS_PER_MEMORY_CACHE, min);
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_topup_memory_cache);
 
 int kvm_mmu_memory_cache_nr_free_objects(struct kvm_mmu_memory_cache *mc)
 {
@@ -436,6 +437,7 @@ void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 	BUG_ON(!p);
 	return p;
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_memory_cache_alloc);
 #endif
 
 static void kvm_vcpu_init(struct kvm_vcpu *vcpu, struct kvm *kvm, unsigned id)

---

## [13] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for pre-allocating pages*

In the KVM fault path pagei, tables and private pages need to be
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

To avoid problem of needing the kernel to link to functionality in KVM,
a function pointer could be passed, however this makes the code
convoluted, when what is needed is barely more than a linked list. So
create a tiny, simpler version of KVM's kvm_mmu_memory_cache to use for
PAMT pages.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/tdx.h  | 43 ++++++++++++++++++++++++++++++++++++-
 arch/x86/kvm/vmx/tdx.c      | 16 +++++++++++---
 arch/x86/kvm/vmx/tdx.h      |  2 +-
 arch/x86/virt/vmx/tdx/tdx.c | 22 +++++++++++++------
 virt/kvm/kvm_main.c         |  2 --
 5 files changed, 72 insertions(+), 13 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 439dd5c5282e..e108b48af2c3 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -17,6 +17,7 @@
 #include <uapi/asm/mce.h>
 #include <asm/tdx_global_metadata.h>
 #include <linux/pgtable.h>
+#include <linux/memory.h>
 
 /*
  * Used by the #VE exception handler to gather the #VE exception
@@ -116,7 +117,46 @@ int tdx_guest_keyid_alloc(void);
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
+		struct page *page = alloc_page(GFP_KERNEL);
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
@@ -192,6 +232,7 @@ static inline int tdx_enable(void)  { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
+static inline int tdx_dpamt_entry_pages(void) { return 0; }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLER__ */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 6c9e11be9705..b274d350165c 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1593,16 +1593,26 @@ static void tdx_unpin(struct kvm *kvm, struct page *page)
 static void *tdx_alloc_external_fault_cache(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct page *page = get_tdx_prealloc_page(&tdx->prealloc);
 
-	return kvm_mmu_memory_cache_alloc(&tdx->mmu_external_spt_cache);
+	if (!page)
+		return NULL;
+
+	return page_address(page);
 }
 
 static int tdx_topup_external_fault_cache(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct tdx_prealloc *prealloc = &tdx->prealloc;
+	int min_fault_cache_size;
 
-	return kvm_mmu_topup_memory_cache(&tdx->mmu_external_spt_cache,
-					  PT64_ROOT_MAX_LEVEL);
+	/* External page tables */
+	min_fault_cache_size = PT64_ROOT_MAX_LEVEL;
+	/* Dynamic PAMT pages (if enabled) */
+	min_fault_cache_size += tdx_dpamt_entry_pages() * PT64_ROOT_MAX_LEVEL;
+
+	return topup_tdx_prealloc_page(prealloc, min_fault_cache_size);
 }
 
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index cd7993ef056e..68bb841c1b6c 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -71,7 +71,7 @@ struct vcpu_tdx {
 	u64 map_gpa_next;
 	u64 map_gpa_end;
 
-	struct kvm_mmu_memory_cache mmu_external_spt_cache;
+	struct tdx_prealloc prealloc;
 };
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c25e238931a7..b4edc3ee495c 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1999,13 +1999,23 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
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
+	return alloc_page(GFP_KERNEL);
+}
+
 
 /*
  * The TDX spec treats the registers like an array, as they are ordered
@@ -2032,12 +2042,12 @@ static u64 *dpamt_args_array_ptr(struct tdx_module_args *args)
 	return (u64 *)((u8 *)args + offsetof(struct tdx_module_args, rdx));
 }
 
-static int alloc_pamt_array(u64 *pa_array)
+static int alloc_pamt_array(u64 *pa_array, struct tdx_prealloc *prealloc)
 {
 	struct page *page;
 
 	for (int i = 0; i < tdx_dpamt_entry_pages(); i++) {
-		page = alloc_page(GFP_KERNEL);
+		page = alloc_dpamt_page(prealloc);
 		if (!page)
 			return -ENOMEM;
 		pa_array[i] = page_to_phys(page);
@@ -2111,7 +2121,7 @@ static u64 tdh_phymem_pamt_remove(unsigned long hpa, u64 *pamt_pa_array)
 static DEFINE_SPINLOCK(pamt_lock);
 
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
-int tdx_pamt_get(struct page *page)
+int tdx_pamt_get(struct page *page, struct tdx_prealloc *prealloc)
 {
 	unsigned long hpa = ALIGN_DOWN(page_to_phys(page), PMD_SIZE);
 	u64 pamt_pa_array[MAX_DPAMT_ARG_SIZE];
@@ -2122,7 +2132,7 @@ int tdx_pamt_get(struct page *page)
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
-	ret = alloc_pamt_array(pamt_pa_array);
+	ret = alloc_pamt_array(pamt_pa_array, prealloc);
 	if (ret)
 		return ret;
 
@@ -2228,7 +2238,7 @@ struct page *tdx_alloc_page(void)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page)) {
+	if (tdx_pamt_get(page, NULL)) {
 		__free_page(page);
 		return NULL;
 	}
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index f05e6d43184b..fee108988028 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -404,7 +404,6 @@ int kvm_mmu_topup_memory_cache(struct kvm_mmu_memory_cache *mc, int min)
 {
 	return __kvm_mmu_topup_memory_cache(mc, KVM_ARCH_NR_OBJS_PER_MEMORY_CACHE, min);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_topup_memory_cache);
 
 int kvm_mmu_memory_cache_nr_free_objects(struct kvm_mmu_memory_cache *mc)
 {
@@ -437,7 +436,6 @@ void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 	BUG_ON(!p);
 	return p;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_memory_cache_alloc);
 #endif
 
 static void kvm_vcpu_init(struct kvm_vcpu *vcpu, struct kvm *kvm, unsigned id)

---

## [14] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 13/16] KVM: TDX: Handle PAMT allocation in fault path*

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
v3:
 - Use new pre-allocation method
 - Updated log
 - Some extra safety around kvm_get_running_vcpu()
---
 arch/x86/kvm/vmx/tdx.c | 45 +++++++++++++++++++++++++++++++++++++-----
 1 file changed, 40 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index b274d350165c..a55a95558557 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -836,6 +836,7 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	struct page *page;
 	int i;
 
 	/*
@@ -862,6 +863,9 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 		tdx->vp.tdvpr_page = 0;
 	}
 
+	while ((page = get_tdx_prealloc_page(&tdx->prealloc)))
+		__free_page(page);
+
 	tdx->state = VCPU_TD_STATE_UNINITIALIZED;
 }
 
@@ -1665,13 +1669,23 @@ static int tdx_mem_page_record_premap_cnt(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, kvm_pfn_t pfn)
 {
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	struct page *page = pfn_to_page(pfn);
+	int ret;
+
+	if (KVM_BUG_ON(!vcpu, kvm))
+		return -EINVAL;
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return -EINVAL;
 
+	ret = tdx_pamt_get(page, &tdx->prealloc);
+	if (ret)
+		return ret;
+
 	/*
 	 * Because guest_memfd doesn't support page migration with
 	 * a_ops->migrate_folio (yet), no callback is triggered for KVM on page
@@ -1687,10 +1701,16 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * barrier in tdx_td_finalize().
 	 */
 	smp_rmb();
-	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
-		return tdx_mem_page_aug(kvm, gfn, level, page);
 
-	return tdx_mem_page_record_premap_cnt(kvm, gfn, level, pfn);
+	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
+		ret = tdx_mem_page_aug(kvm, gfn, level, page);
+	else
+		ret = tdx_mem_page_record_premap_cnt(kvm, gfn, level, pfn);
+
+	if (ret)
+		tdx_pamt_put(page);
+
+	return ret;
 }
 
 static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
@@ -1747,17 +1767,30 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
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
 
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error_2(TDH_MEM_SEPT_ADD, err, entry, level_state);
+		tdx_pamt_put(page);
 		return -EIO;
 	}
 
@@ -2966,6 +2999,8 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
+	INIT_LIST_HEAD(&tdx->prealloc.page_list);
+
 	page = tdx_alloc_page();
 	if (!page)
 		return -ENOMEM;

---

## [15] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 14/16] KVM: TDX: Reclaim PAMT memory*

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
v3:
 - Minor log tweak to conform kvm/x86 style.
---
 arch/x86/kvm/vmx/tdx.c | 15 ++++++++++++---
 1 file changed, 12 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index a55a95558557..9ee8f7f60acd 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -358,7 +358,7 @@ static void tdx_reclaim_control_page(struct page *ctrl_page)
 	if (tdx_reclaim_page(ctrl_page))
 		return;
 
-	__free_page(ctrl_page);
+	tdx_free_page(ctrl_page);
 }
 
 struct tdx_flush_vp_arg {
@@ -589,7 +589,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 	}
 	tdx_clear_page(kvm_tdx->td.tdr_page);
 
-	__free_page(kvm_tdx->td.tdr_page);
+	tdx_free_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 }
 
@@ -1759,6 +1759,7 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
 		return -EIO;
 	}
 	tdx_clear_page(page);
+	tdx_pamt_put(page);
 	tdx_unpin(kvm, page);
 	return 0;
 }
@@ -1852,6 +1853,7 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level) &&
 	    !KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm)) {
 		atomic64_dec(&kvm_tdx->nr_premapped);
+		tdx_pamt_put(page);
 		tdx_unpin(kvm, page);
 		return 0;
 	}
@@ -1916,6 +1918,8 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, void *private_spt)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct page *page = virt_to_page(private_spt);
+	int ret;
 
 	/*
 	 * free_external_spt() is only called after hkid is freed when TD is
@@ -1932,7 +1936,12 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
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
 
 static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,

---

## [16] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 15/16] x86/virt/tdx: Enable Dynamic PAMT*

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
v3:
 - No changes
---
 arch/x86/include/asm/tdx.h  | 6 +++++-
 arch/x86/virt/vmx/tdx/tdx.c | 8 ++++++++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 3 files changed, 13 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e108b48af2c3..d389dc07c718 100644
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
@@ -110,7 +114,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT;
 }
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index b4edc3ee495c..da21104575a6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1043,6 +1043,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
+#define TDX_SYS_CONFIG_DYNAMIC_PAMT	BIT(16)
+
 static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
@@ -1070,6 +1072,12 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
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

## [17] Rick Edgecombe — 2025-09-18
*Subject: [PATCH v3 16/16] Documentation/x86: Add documentation for TDX's Dynamic PAMT*

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
index 719043cd8b46..d07132c99cc6 100644
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

## [18] Huang, Kai — 2025-09-19
*Subject: Re: [PATCH v3 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

On Thu, 2025-09-18 at 16:22 -0700, Rick Edgecombe wrote:
> For each memory region that the TDX module might use (TDMR), the three
> separate PAMT allocations are needed. One for each supported page size

AFAICT you don't need pass the whole 'pamt_entry_size[]' array, passing
the correct pamt_entry_size should be enough.

>  {
>  	unsigned long pamt_sz, nr_pamt_entries;

Do you need to zero the base here?  IIUC, it hasn't been setup yet if PAMT
allocation fails.  All TDMRs are allocated with __GFP_ZERO, so it should
be 0 already when PAMT allocation fails here.

> -
> -	/*

---

## [19] Huang, Kai — 2025-09-19
*Subject: Re: [PATCH v3 02/16] x86/tdx: Add helpers to check return status
 codes*

On Thu, 2025-09-18 at 16:22 -0700, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 
		    ^
		    more

> do some cleanup to reduce the boiler plate error code parsing.
> 
	  ^
	  i.e. or e.g. ?
> 
> Finally, update the code that previously open coded the bit math to use

[...]

> +#include <asm/trapnr.h>
> +

Nit: the whitespace/tab change here is a bit odd?

>  
>  /*
[...]

> +static inline bool IS_TDX_SW_ERROR(u64 err)
> +{

[...]

> +#define DEFINE_TDX_ERRNO_HELPER(error)			\
> +	static inline bool IS_##error(u64 err)	\

Given:

+#define TDX_ERROR			_BITULL(63)
+#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))

I think IS_TDX_SW_ERROR() can also use the DEFINE_TDX_ERRNO_HELPER() ?

> +
> +DEFINE_TDX_ERRNO_HELPER(TDX_SUCCESS);

[...]

---

## [20] Huang, Kai — 2025-09-19
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Thu, 2025-09-18 at 16:22 -0700, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

The existing asm/shared/tdx.h is used for sharing TDX code between the
early compressed code and the normal kernel code after that, i.e., it's
not for sharing between TDX guest and host.

Any reason to put the new tdx_errno.h under asm/shared/ ?

---

## [21] Huang, Kai — 2025-09-19
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

> +/* Map a page into the PAMT refcount vmalloc region */
> +static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)

[...]

> Make sure another PAMT range didn't already
> +	 * populate it.

Make sure the same range only gets populated once ?

> +	if (pte_none(ptep_get(pte)))
> +		set_pte_at(&init_mm, addr, pte, entry);

(sorry didn't notice this in last version)

I don't quite follow why we need "end_pfn + 1" instead of just "end_pfn"?

IIUC this could result in an additional 2M range being populated
unnecessarily when the end_pfn is 2M aligned.

And ...

> +	start = round_down(start, PAGE_SIZE);
> +	end   = round_up(end, PAGE_SIZE);

... when max_pfn == end_pfn of the last TDX memory block, this could
result in an additional page of @pamt_refcounts being allocated, but it
will never be freed since free_pamt_metadata() will only free mapping up
to max_pfn.

Am I missing anything?

---

## [22] Kiryl Shutsemau — 2025-09-19
*Subject: Re: [PATCH v3 08/16] x86/virt/tdx: Optimize tdx_alloc/free_page()
 helpers*

On Thu, Sep 18, 2025 at 04:22:16PM -0700, Rick Edgecombe wrote:
> +		} else if (IS_TDX_HPA_RANGE_NOT_FREE(tdx_status)) {
> +			/*

It is still 0->1 transition. atomic_set(pamt_refcount, 1) would be
slightly faster here.

---

## [23] Kiryl Shutsemau — 2025-09-19
*Subject: Re: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Thu, Sep 18, 2025 at 04:22:19PM -0700, Rick Edgecombe wrote:
> Move mmu_external_spt_cache behind x86 ops.
> 

Makes sense.

Acked-by: Kiryl Shutsemau <kas@kernel.org>

---

## [24] Kiryl Shutsemau — 2025-09-19
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Thu, Sep 18, 2025 at 04:22:20PM -0700, Rick Edgecombe wrote:
> In the KVM fault path pagei, tables and private pages need to be

Typo.

> installed under a spin lock. This means that the operations around
> installing PAMT pages for them will not be able to allocate pages.

> +static inline struct page *get_tdx_prealloc_page(struct tdx_prealloc *prealloc)
> +{

For prealloc->cnt == 0, kvm_mmu_memory_cache_alloc() does allocation
with GFP_ATOMIC after WARN().

Do we want the same here?

---

## [25] Edgecombe, Rick P — 2025-09-19
*Subject: Re: [PATCH v3 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

On Fri, 2025-09-19 at 00:50 +0000, Huang, Kai wrote:
> > +				  nid, &node_online_map);
> > +	if (!pamt) {

Oh, you are right. It's zero allocated. Hmm a comment should probably go
somewhere still.

---

## [26] Huang, Kai — 2025-09-22
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

> +/*
> + * Simple structure for pre-allocating Dynamic

Since 'struct tdx_prealloc' replaces the KVM standard 'struct
kvm_mmu_memory_cache' for external page table, and it is allowed to fail
in "topup" operation, why not just call tdx_alloc_page() to "topup" page
for external page table here?

I don't think we need to keep all "DPAMT pages" in the pool, right?

If tdx_alloc_page() succeeds, then the "DPAMT pages" are also "topup"ed,
and PAMT entries for the 2M range of the SEPT page is ready too.

This at least avoids having to export tdx_dpamt_entry_pages(), which is
not nice IMHO.  And I think it should yield simpler code.

One more thinking:

I also have been thinking whether we can continue to use the KVM standard
'struct kvm_mmu_memory_cache' for S-EPT pages.  Below is one more idea for
your reference.

In the previous discussion I think we concluded the 'kmem_cache' doesn't
work nicely with DPAMT (due to the ctor() cannot fail etc).  And when we
don't use 'kmem_cache', KVM just call __get_free_page() to topup objects.
But we need tdx_alloc_page() for allocation here, so this is the problem.

If we add two callbacks for object allocation/free to 'struct
kvm_mmu_memory_cache', then we can have place to hook tdx_alloc_page().

Something like the below:

diff --git a/include/linux/kvm_types.h b/include/linux/kvm_types.h
index 827ecc0b7e10..5dbd80773689 100644
--- a/include/linux/kvm_types.h
+++ b/include/linux/kvm_types.h
@@ -88,6 +88,8 @@ struct kvm_mmu_memory_cache {
        gfp_t gfp_custom;
        u64 init_value;
        struct kmem_cache *kmem_cache;
+       void*(*obj_alloc)(gfp_t gfp);
+       void (*obj_free)(void *);
        int capacity;
        int nobjs;
        void **objects;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 6c07dd423458..df2c2100d656 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -355,7 +355,10 @@ static inline void *mmu_memory_cache_alloc_obj(struct
kvm_mmu_memory_cache *mc,
        if (mc->kmem_cache)
                return kmem_cache_alloc(mc->kmem_cache, gfp_flags);
 
-       page = (void *)__get_free_page(gfp_flags);
+       if (mc->obj_alloc)
+               page = mc->obj_alloc(gfp_flags);
+       else
+               page = (void *)__get_free_page(gfp_flags);
        if (page && mc->init_value)
                memset64(page, mc->init_value, PAGE_SIZE / sizeof(u64));
        return page;
@@ -415,6 +418,8 @@ void kvm_mmu_free_memory_cache(struct
kvm_mmu_memory_cache *mc)
        while (mc->nobjs) {
                if (mc->kmem_cache)
                        kmem_cache_free(mc->kmem_cache, mc->objects[--mc-
>nobjs]);
+               else if (mc->obj_free)
+                       mc->obj_free(mc->objects[--mc->nobjs]);
                else
                        free_page((unsigned long)mc->objects[--mc-
>nobjs]);
        }

---

## [27] Huang, Kai — 2025-09-22
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Thu, 2025-09-18 at 16:22 -0700, Edgecombe, Rick P wrote:
> +static void free_pamt_array(u64 *pa_array)
> +{

This needs rebasing I suppose.

> +
> +		/*

This comment shouldn't be in this patch?  The 'prealloc' concept doesn't
exist yet until patch 12 AFAICT.

---

## [28] Binbin Wu — 2025-09-23
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
[...]
> +/*
> + * SW-defined error codes.

TDX_ERROR and TDX_NON_RECOVERABLE are defined in TDX spec as the classes of TDX
Interface Functions Completion Status.

For clarity, is it better to move the two before the "SW-defined error codes"
comment?

> +#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
> +#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _ULL(0xFFFF0000))

---

## [29] Binbin Wu — 2025-09-23
*Subject: Re: [PATCH v3 02/16] x86/tdx: Add helpers to check return status
 codes*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
[...]
>   	/*
> diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h

TDX_STATUS() will be called in noinstr range.
I suppose __always_inline is still needed even if it's a single statement
function.

...
> @@ -903,7 +897,7 @@ static __always_inline u32 tdx_to_vmx_exit_reason(struct kvm_vcpu *vcpu)
>   	struct vcpu_tdx *tdx = to_tdx(vcpu);
[...]

---

## [30] Yan Zhao — 2025-09-23
*Subject: Re: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Thu, Sep 18, 2025 at 04:22:19PM -0700, Rick Edgecombe wrote:
> Move mmu_external_spt_cache behind x86 ops.
> 
Though pre-allocated pages are eventually freed in tdx_vcpu_free() in patch 13,
looks they are leaked in this patch.

BTW, why not invoke kvm_x86_call(free_external_fault_cache)(vcpu) here?
It looks more natural to free the remaining pre-allocated pages in
mmu_free_memory_caches(), which is invoked after kvm_mmu_unload(vcpu) while
tdx_vcpu_free() is before it. 

>  	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_page_header_cache);
>  }

---

## [31] Binbin Wu — 2025-09-23
*Subject: Re: [PATCH v3 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
[...]
> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> index 38dae825bbb9..4e4aa8927550 100644

Nit:
return PAGE_ALIGN(pamt_sz);

---

## [32] Binbin Wu — 2025-09-23
*Subject: Re: [PATCH v3 05/16] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>
                   ^
                  52-bit
> the DPAMT refcount allocations could hypothetically exceed the savings
> from Dynamic PAMT, which is 4GB per TB. This is probably unlikely.

Is there guarantee that max_pfn is PTRS_PER_PTE aligned?
If not, it should be rounded up.

> +
> +	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
[...]

---

## [33] Binbin Wu — 2025-09-23
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

On 9/19/2025 3:25 PM, Huang, Kai wrote:
>> +/* Map a page into the PAMT refcount vmalloc region */
>> +static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)

IIUC, this will not happen.
The +1 page will be converted to 4KB, and will be ignored since in
tdx_find_pamt_refcount() the address is divided by 2M.

To handle the address unaligned to 2M, +511 should be used instead of +1?

>
> And ...

refount -> refcount


>> +	if (!pte_none(entry)) {
>> +		pte_clear(&init_mm, addr, pte);

---

## [34] Binbin Wu — 2025-09-24
*Subject: Re: [PATCH v3 08/16] x86/virt/tdx: Optimize tdx_alloc/free_page()
 helpers*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>
                                                      ^
                                                 tdx_pamt_get() ?
> inside the lock. Because of this, there is a special race where
> tdx_pamt_put() could decrement the refcount to zero before the PAMT is
it's not -> it's ?

> +	 * See special logic around HPA_RANGE_NOT_FREE in tdx_pamt_get().
> +	 */

---

## [35] Huang, Kai — 2025-09-24
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

On Tue, 2025-09-23 at 17:38 +0800, Binbin Wu wrote:
> > > +/*
> > > + * Allocate PAMT reference counters for the given PFN range.

OK. Thanks for catching.  But I still don't get why we need end_pfn + 1.

Also, when end_pfn == 511, would this result in the second refcount being
returned for the @end, while the intention should be the first refcount?

For example, assuming we have a range [0, 2M), we only need one refcount.
And the PFN range (which comes from for_each_mem_pfn_range()) would be:

    start_pfn == 0
    end_pfn   == 512

This will results in @start pointing to the first refcount and @end
pointing to the second, IIUC.

So it seems we need:

    start = (unsigned long)tdx_find_pamt_refcount(PFN_PHYS(start_pfn));
    end   = (unsigned long)tdx_find_pamt_refcount(PFN_PHYS(end_pfn) - 1));
    start = round_down(start, PAGE_SIZE);
    end   = round_up(end, PAGE_SIZE);

?

---

## [36] Binbin Wu — 2025-09-24
*Subject: Re: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
> Move mmu_external_spt_cache behind x86 ops.
>
arch/86 -> arch/x86

> them for DPAMT updates, which is hard for the existing KVM based cache.
> The details living in core MMU code start to add up.
[...]

---

## [37] Binbin Wu — 2025-09-24
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

On 9/24/2025 2:50 PM, Huang, Kai wrote:
> On Tue, 2025-09-23 at 17:38 +0800, Binbin Wu wrote:
>>>> +/*

Checked again, this seems to be the right version.

>
> ?

---

## [38] Edgecombe, Rick P — 2025-09-25
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Tue, 2025-09-23 at 13:49 +0800, Binbin Wu wrote:
> > +/*
> > + * SW-defined error codes.

This hunk is a direct copy, any reason to change it in this patch?

---

## [39] Edgecombe, Rick P — 2025-09-25
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Fri, 2025-09-19 at 01:29 +0000, Huang, Kai wrote:
> The existing asm/shared/tdx.h is used for sharing TDX code between the
> early compressed code and the normal kernel code after that, i.e., it's

Well this series doesn't address this, but the compressed code could use
IS_TDX_SUCCESS(), etc. I assume the purpose was to put it in a place where all
callers could use them.

If you think that is good reasoning too, then I think it's worth mentioning in
the log.

---

## [40] Edgecombe, Rick P — 2025-09-25
*Subject: Re: [PATCH v3 02/16] x86/tdx: Add helpers to check return status
 codes*

On Tue, 2025-09-23 at 14:19 +0800, Binbin Wu wrote:
> > +static inline u64 TDX_STATUS(u64 err)
> > +{

Oh yea, good catch.

---

## [41] Edgecombe, Rick P — 2025-09-25
*Subject: Re: [PATCH v3 02/16] x86/tdx: Add helpers to check return status
 codes*

On Fri, 2025-09-19 at 01:26 +0000, Huang, Kai wrote:
> > +#include <asm/trapnr.h>
> > +

I don't see it. It keeps the alignment (that also matches the below hunk) with
the name length change. Check it in an editor.

> 
> >   

Good point.

---

## [42] Edgecombe, Rick P — 2025-09-25
*Subject: Re: [PATCH v3 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Tue, 2025-09-23 at 15:15 +0800, Binbin Wu wrote:
> Nit:
> return PAGE_ALIGN(pamt_sz);

Yep. thanks.

---

## [43] Huang, Kai — 2025-09-25
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Thu, 2025-09-25 at 23:23 +0000, Edgecombe, Rick P wrote:
> On Fri, 2025-09-19 at 01:29 +0000, Huang, Kai wrote:
> > The existing asm/shared/tdx.h is used for sharing TDX code between the

Sure. 

> 
> If you think that is good reasoning too, then I think it's worth mentioning in

I am fine either way.

Since (as you said) compressed code isn't changed to use IS_TDX_xx() in
this series, it's hard to see the reason (from the code change) why you
put it under asm/shared/ w/o explaining it in the changelog.

---

## [44] Yan Zhao — 2025-09-26
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Thu, Sep 18, 2025 at 04:22:20PM -0700, Rick Edgecombe wrote:
> In the KVM fault path pagei, tables and private pages need to be
> installed under a spin lock. This means that the operations around

min_fault_cache_size = PT64_ROOT_MAX_LEVEL - 1?
We don't need to allocate page for the root page.

> +	/* Dynamic PAMT pages (if enabled) */
> +	min_fault_cache_size += tdx_dpamt_entry_pages() * PT64_ROOT_MAX_LEVEL;
What about commenting that it's
tdx_dpamt_entry_pages() * ((PT64_ROOT_MAX_LEVEL - 1) + 1) ?
i.e.,
(PT64_ROOT_MAX_LEVEL  - 1) for page table pages, and 1 for guest private page.


> +	return topup_tdx_prealloc_page(prealloc, min_fault_cache_size);
>  }

---

## [45] Yan Zhao — 2025-09-26
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Thu, Sep 18, 2025 at 04:22:08PM -0700, Rick Edgecombe wrote:
> Hi,
> 
Yes, I found a contention issue that prevents us from dropping the global lock.
I've also written a sample test that demonstrates this contention.

    CPU 0                                     CPU 1
(a) TDH.PHYMEM.PAMT.ADD(A1, B1, xx1)      (b) TDH.PHYMEM.PAMT.ADD(B2, xx2, xx3)

A1, B2 are not from the same 2MB physical range,
B1, B2 are from the same 2MB physical range.
Physical addresses of xx1, xx2, xx3 are irrelevant.

(a) adds PAMT pages B1, xx1 for A1's 2MB physical range.
(b) adds PAMT pages xx2, xx3 for B2's 2MB physical range.

This could happen when host wants to AUG a 4KB page A1. So, it allocates 4KB
pages B1, xx1, and invokes (a).

Then host wants to AUG a 4KB page B2. Since there're no PAMT pages for B2's 2MB
physical range yet, host invokes (b).

(a) needs to hold shared lock of B1's 2MB PAMT entry.
(b) needs to hold exclusive lock of B2's 2MB PAMT entry.

---

## [46] Xiaoyao Li — 2025-09-26
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov"<kirill.shutemov@linux.intel.com>
> 

it's "arch/x86/kvm/vmx/tdx_errno.h" actually.

> They have some overlap that is already defined similarly. Reduce the
> duplication and prepare to introduce some helpers for these error codes in

---

## [47] Binbin Wu — 2025-09-26
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On 9/26/2025 7:09 AM, Edgecombe, Rick P wrote:
> On Tue, 2025-09-23 at 13:49 +0800, Binbin Wu wrote:
>>> +/*
yeah, it can be done separately.

---

## [48] Xiaoyao Li — 2025-09-26
*Subject: Re: [PATCH v3 02/16] x86/tdx: Add helpers to check return status
 codes*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

There are TDCALL_RETURN_CODE() usages left in tdx_mcall_extend_rtmr().
Please clean them up as well, and the definitions of TDCALL_RETURN_CODE 
macro and friends can be removed totally:


   /* TDX Module call error codes */
   #define TDCALL_RETURN_CODE(a)	((a) >> 32)
   #define TDCALL_INVALID_OPERAND	0xc0000100
   #define TDCALL_OPERAND_BUSY	0x80000200

> @@ -316,7 +316,7 @@ static void reduce_unnecessary_ve(void)
>   {

I would expect a separate patch to change it first to

	if ((err & TDX_STATUS_MASK) == TDX_SUCCESS)

because it certainly changes the semantic of the check.

And this applies to some other places below, e.g.,

 > -	if (err == TDX_FLUSHVP_NOT_DONE)
 > +	if (IS_TDX_FLUSHVP_NOT_DONE(err))

 > -	if (err == TDX_RND_NO_ENTROPY) {
 > +	if (IS_TDX_RND_NO_ENTROPY(err)) {


>   		return;
>   

This belongs to the previous patch, I think.

And in that patch, the <asm/trapnr.h> can be removed from
arch/x86/include/asm/tdx.h?

>   /* Upper 32 bit of the TDX error code encodes the status */
> -#define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL

Kai already catched that it can be defined with DEFINE_TDX_ERRNO_HELPER()

The background is that we wanted to use SEAMCALL return code to cover 
the #GP/#UD/VMFAILINVALID cases generally so that we asked TDX 
architecuts to reserve Class ID (0XFF) for software usage.

SW_ERROR is just a Linux defined status code (in the upper 32 bits), and 
details in the lower 32 bits to identify among #GP/#UD/VMFAILINVALID.

So ...

> +static inline bool IS_TDX_SEAMCALL_VMFAILINVALID(u64 err)
> +{

... TDX_SEAMCALL_{VMFAILINVALID,GP,UD} are full 64-bit return codes, not 
some masks. The check of

	(err & TDX_SEAMCALL_*) == TDX_SEAMCALL_*

isn't correct here and we need to check

	err == TDX_SEAMCALL_*;

e.g., The #UD is of number 6, which is 110b. If SEAMCALL could cause 
exception of vector 111b, 1110b, 1111b, they can pass the check of 
IS_TDX_SEAMCALL_UD()

---

## [49] Xiaoyao Li — 2025-09-26
*Subject: Re: [PATCH v3 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

+ Dan,

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
> diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
> index 13ad2663488b..683925bcc9eb 100644

It looks like the update is not produced by the script[1], but manually, 
right?

Looking at the history

   git log arch/x86/virt/vmx/tdx/tdx_global_metadata.c

It looks the expectation is always adding new fields by updating the 
script[1] and running it with the latest 'tdx_global_metadata.c'.

Dan Williams also expressed internally that we should have checked the 
script[1] into the kernel. I agree with him and it's never too late to 
do it.

[1]https://lore.kernel.org/kvm/0853b155ec9aac09c594caa60914ed6ea4dc0a71.camel@intel.com/

---

## [50] Dave Hansen — 2025-09-26
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On 9/25/25 19:28, Yan Zhao wrote:
>> Lastly, Yan raised some last minute doubts internally about TDX
>> module locking contention. I’m not sure there is a problem, but we
But what is the end result when this contention happens? Does everyone
livelock?

---

## [51] Dave Hansen — 2025-09-26
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On 9/18/25 16:22, Rick Edgecombe wrote:
> +/*
> + * Simple structure for pre-allocating Dynamic

This is compact and all. But it's really just an open-coded, simplified
version of what mempool_t plus mempool_init_page_pool() would do.

Could you take a look at that and double check that it's not a good fit
here, please?

---

## [52] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Fri, 2025-09-26 at 08:19 -0700, Dave Hansen wrote:
> On 9/18/25 16:22, Rick Edgecombe wrote:
> > +/*

Yes! I searched and was surprised there wasn't something like this. I
will give this one a try.

---

## [53] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Fri, 2025-09-26 at 07:09 -0700, Dave Hansen wrote:
> On 9/25/25 19:28, Yan Zhao wrote:
> > > Lastly, Yan raised some last minute doubts internally about TDX

You get a TDX_OPERAND_BUSY error code returned. Inside the TDX module
each lock is a try lock. The TDX module tries to take a sequence of
locks and if it meets any contention it will release them all and
return the TDX_OPERAND_BUSY. Some paths in KVM cannot handle failure
and so don't have a way to handle the error.

So another option to handling this is just to retry until you succeed.
Then you have a very strange spinlock with a heavyweight inner loop.
But since each time the locks are released, some astronomical bad
timing might prevent forward progress. On the KVM side we have avoided
looping. Although, I think we have not exhausted this path.

---

## [54] Dave Hansen — 2025-09-26
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On 9/26/25 09:02, Edgecombe, Rick P wrote:
> On Fri, 2025-09-26 at 07:09 -0700, Dave Hansen wrote:
>> On 9/25/25 19:28, Yan Zhao wrote:

If it can't return failure then the _only_ other option is to spin. Right?

I understand the reluctance to have such a nasty spin loop. But other
than reworking the KVM code to do the retries at a higher level, is
there another option?

---

## [55] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Fri, 2025-09-26 at 09:11 -0700, Dave Hansen wrote:
> If it can't return failure then the _only_ other option is to spin.
> Right?

Yea, but you could spin around the SEAMCALL or you could spin on
duplicate locks on the kernel side before making the SEAMCALL. Or put
more generally, you could prevent contention before you make the
SEACMALL. KVM does this also by kicking vCPUs out of the TDX module via
IPI in other cases.

> 
> I understand the reluctance to have such a nasty spin loop. But other

Re-working KVM code would be tough, although teaching KVM to fail zap
calls has come up before for TDX/gmem interactions. It was looked at
and decided to be too complex. Now I guess the benefit side of the
equation changes a little bit, but doing it only for TDX might still be
a bridge to far.

Unless anyone is holding onto another usage that might want this?

>  is there another option?

I don't see why we can't just duplicate the locking in a more matching
way on the kernel side. Before the plan to someday drop the global lock
if needed, was to switch to 2MB granular locks to match the TDX
module's exclusive lock internal behavior.

What Yan is basically pointing out is that there are shared locks that
are also taken on different ranges that could possibly contend with the
exclusive one that we are duplicating on the kernel side.

So the problem is not fundamental to the approach I think. We just took
a shortcut by ignoring the shared locks. For line-of-sight to a path to
remove the global lock someday, I think we could make the 2MB granular
locks be reader/writer to match the TDX module. Then around the
SEAMCALLs that take these locks, we could take them on the kernel side
in the right order for whichever SEAMCALL we are making.

And that would only be the plan if we wanted to improve scalability
someday without changing the TDX module.

---

## [56] Dave Hansen — 2025-09-26
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On 9/26/25 12:00, Edgecombe, Rick P wrote:
> So the problem is not fundamental to the approach I think. We just took
> a shortcut by ignoring the shared locks. For line-of-sight to a path to

Yeah, but what if the TDX module changes its locking scheme in 5 years
or 10? What happens to 6.17.9999-stable?

---

## [57] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Fri, 2025-09-26 at 12:03 -0700, Dave Hansen wrote:
> 
> Yeah, but what if the TDX module changes its locking scheme in 5

Yea, we expected we were turning the locking behavior into ABI even in
the existing S-EPT management code. To change it would require a host
opt-in.

We originally assured correctness via TDX module source code
inspection, but recently the TDX module folks pointed out that the TDX
module ABI docs actually list information about what locks are taken
for each SEAMCALL. Or in it's terms, which resources are held in which
context. It is in the tables labeled "Concurrency Restrictions". Lock
ordering (like we would need to do the above) is not listed though.

---

## [58] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 01/16] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Fri, 2025-09-26 at 12:52 +0800, Xiaoyao Li wrote:
> it's "arch/x86/kvm/vmx/tdx_errno.h" actually.

Doh! yes.

---

## [59] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 02/16] x86/tdx: Add helpers to check return status
 codes*

On Fri, 2025-09-26 at 14:32 +0800, Xiaoyao Li wrote:
> On 9/19/2025 7:22 AM, Rick Edgecombe wrote:
> >   	ret = __tdcall(TDG_MR_REPORT, &args);

Oh, good call.

> 
> 

I'm not sure. I see your point, but I'm not sure it's worth the extra
churn.

> 
> And this applies to some other places below, e.g.,

Yep, on both accounts.

> 
> >   /* Upper 32 bit of the TDX error code encodes the status */

Interesting history. The comment references this in an vague way, but I
can't find it in the official docs anywhere. Did I miss it?

> 
> SW_ERROR is just a Linux defined status code (in the upper 32 bits),

Right. Good catch.

---

## [60] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Fri, 2025-09-26 at 16:41 +0800, Xiaoyao Li wrote:
> It looks like the update is not produced by the script[1], but
> manually, right?

Yes, it's not symmetrical. It was probably added manually. I don't see
why we actually need the the part that makes it unsymmetrical
(tdx_supports_dynamic_pamt() check). In fact I think it's bad because
it depends on specific call order of the metadata reading to be valid.

Kirill, any reason we can't drop it?

As for a strict requirement to use the script, it wasn't my
understanding.

> 
> Dan Williams also expressed internally that we should have checked

Especially while the ABI docs file format is being revisited, it
doesn't seem like the right time to check it in.

For this patch we could have used it, however at this point it would
amount to verifying that it output the same few lines of code. Would
you like to do this test? (Assuming we can drop the
tdx_supports_dynamic_pamt() check) Probably a note that the code
generation matched our manual implementation would be a point of
reassurance to add to the log.

---

## [61] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Fri, 2025-09-26 at 09:44 +0800, Yan Zhao wrote:
> > -	return kvm_mmu_topup_memory_cache(&tdx-
> > >mmu_external_spt_cache,

Why change it in this patch?

> 
> > +	/* Dynamic PAMT pages (if enabled) */

Yes the comment could be improved. I'll enhance it. Thanks.

---

## [62] Dave Hansen — 2025-09-26
*Subject: Re: [PATCH v3 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On 9/26/25 14:57, Edgecombe, Rick P wrote:
> As for a strict requirement to use the script, it wasn't my
> understanding.

So, remember that all of this started because the TDX docs said that
they didn't document some necessary stuff and to go look in a JSON file
instead. The JSON file wasn't particularly human-readable, thus the
script was born to read it.

But it turns out that the JSON isn't stable. It also isn't authoritative
enough to write code from by itself. Nobody realized this when this
adventure started.

Anyway, long story short, the JSON experiment failed and we're back to
normal docs for TDX ABI definitions. Thus, the script can go away and
maybe we should make that code a bit less ugly now that humans are going
to be editing it all the time now.

---

## [63] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Tue, 2025-09-23 at 15:03 +0800, Yan Zhao wrote:
> > @@ -625,7 +624,6 @@ static void mmu_free_memory_caches(struct
> > kvm_vcpu *vcpu)

The thought was to reduce the number of TDX callbacks in core MMU code.

> It looks more natural to free the remaining pre-allocated pages in
> mmu_free_memory_caches(), which is invoked after kvm_mmu_unload(vcpu)

Hmm, that is not so tidy. But on balance I think it would still be
better to leave it more contained in TDX code. Any strong objection?

---

## [64] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Mon, 2025-09-22 at 11:27 +0000, Huang, Kai wrote:
> > +
> > +		/*


Oh, yep. The comment should be added when prealloc starts getting used.

---

## [65] Edgecombe, Rick P — 2025-09-26
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Mon, 2025-09-22 at 11:20 +0000, Huang, Kai wrote:
> Since 'struct tdx_prealloc' replaces the KVM standard 'struct
> kvm_mmu_memory_cache' for external page table, and it is allowed to

I sympathize with the intuition. It would be nice to just prep
everything and then operate on it like normal.

We want this to not have to be totally redone for huge pages. In the
huge pages case, we could do this approach for the page tables, but for
the private page itself, we don't know whether we need 4KB PAMT backing
or not. So we don't fully know whether a TDX private page needs PAMT
4KB backing or not before the fault.

So we would need, like, separate pools for page tables and private
pages. Or someway to unwind the wrong guess of small page. At that
point I don't think it's simpler.

> 
> I don't think we need to keep all "DPAMT pages" in the pool, right?

Not sure what you mean by this.

> 
> If tdx_alloc_page() succeeds, then the "DPAMT pages" are also

I mean less exports is better, but I don't follow what is so egregious.
It's not called from core KVM code.

> 
> One more thinking:

The point of the new struct was to hand it to the arch/x86 side of the
house. If we don't need to do that, then yes we could have options. And
Dave suggested another struct that could be used to hand off the cache.

> 
> In the previous discussion I think we concluded the 'kmem_cache'

kvm_mmu_memory_cache has a lot of options at this point. All we really
need is a list. I'm not sure it makes sense to keep cramming things
into it?

> 
> Something like the below:

---

## [66] Yan Zhao — 2025-09-28
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Sat, Sep 27, 2025 at 03:00:31AM +0800, Edgecombe, Rick P wrote:
> On Fri, 2025-09-26 at 09:11 -0700, Dave Hansen wrote:
> > If it can't return failure then the _only_ other option is to spin.
Not sure if that would work.

In the following scenario, where
(a) adds PAMT pages B1, xx1 for A1's 2MB physical range.
(b) adds PAMT pages A2, xx2 for B2's 2MB physical range.

A1, B2 are not from the same 2MB physical range,
A1, A2 are from the same 2MB physical range.
B1, B2 are from the same 2MB physical range.
Physical addresses of xx1, xx2 are irrelevant.


    CPU 0                                     CPU 1
    ---------------------------------         -----------------------------
    write_lock(&rwlock-of-range-A1);          write_lock(&rwlock-of-range-B2);
    read_lock(&rwlock-of-range-B1);           read_lock(&rwlock-of-range-A2);
    ...                                       ...
(a) TDH.PHYMEM.PAMT.ADD(A1, B1, xx1)      (b) TDH.PHYMEM.PAMT.ADD(B2, A2, xx2)
    ...                                       ...
    read_unlock(&rwlock-of-range-B1);         read_unlock(&rwlock-of-range-A2);
    write_unlock(&rwlock-of-range-A1);        write_unlock(&rwlock-of-range-B2);


To match the reader/writer locks in the TDX module, it looks like we may
encounter an AB-BA lock issue.

Do you have any suggestions for a better approach?

e.g., could the PAMT pages be allocated from a dedicated pool that ensures they
reside in different 2MB ranges from guest private pages and TD control pages?

> And that would only be the plan if we wanted to improve scalability
> someday without changing the TDX module.

---

## [67] Yan Zhao — 2025-09-28
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Sat, Sep 27, 2025 at 06:05:12AM +0800, Edgecombe, Rick P wrote:
> On Fri, 2025-09-26 at 09:44 +0800, Yan Zhao wrote:
> > > -	return kvm_mmu_topup_memory_cache(&tdx-
The previous size determined by TDP MMU core was just unnecessarily 1 more than
required (I guess it's due to historical reasons).

But since now the size is determined by TDX itself, I think it can be accurate.

> > > +	/* Dynamic PAMT pages (if enabled) */
> > > +	min_fault_cache_size += tdx_dpamt_entry_pages() *

---

## [68] Yan Zhao — 2025-09-28
*Subject: Re: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Sat, Sep 27, 2025 at 06:10:44AM +0800, Edgecombe, Rick P wrote:
> On Tue, 2025-09-23 at 15:03 +0800, Yan Zhao wrote:
> > > @@ -625,7 +624,6 @@ static void mmu_free_memory_caches(struct
No strong opinion.

But if we opt to do the free internal in tdx_vcpu_free(), it looks like this
patch needs to first invoke kvm_mmu_free_memory_cache() in tdx_vcpu_free().

Also, better to have a comment in mmu_free_memory_caches() to explain why
there's no corresponding free_external_fault_cache op.

---

## [69] Huang, Kai — 2025-09-28
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Fri, 2025-09-26 at 23:47 +0000, Edgecombe, Rick P wrote:
> On Mon, 2025-09-22 at 11:20 +0000, Huang, Kai wrote:
> > Since 'struct tdx_prealloc' replaces the KVM standard 'struct

The private page itself comes from the guest_memfd via page cache, so we
cannot use tdx_alloc_page() for it anyway but need to use tdx_pamt_get()
explicitly.

I don't know all details of exactly what is the interaction with huge page
here -- my imagine would be we only call tdx_pamt_get() when we found the
the private page is 4K but not 2M [*], but I don't see how this conflicts
with using tdx_alloc_page() for page table itself.

The point is page table itself is always 4K, therefore it has no
difference from control pages.

[*] this is actually an optimization but not a must for supporting
hugepage with DPAMT AFAICT.  Theoretically, we can always allocate DPAMT
pages upfront for hugepage at allocation time in guest_memfd regardless
whether it is actually mapped as hugepage in S-EPT, and we can free DPAMT
pages when we promote 4K pages to a hugepage in S-EPT to effectively
reduce DPAMT pages for hugepage.

> Or someway to unwind the wrong guess of small page. At that
> point I don't think it's simpler.

I mean we don't need to keep DPAMT pages in the list of 'struct
tdx_prealloc'.  tdx_pamt_put() get the DPAMT pages from the TDX module and
just frees them.

> 
> > 

It comes down to whether we want to continue to reuse
'kvm_mmu_memory_cache' (which is already implemented in KVM), or we want
to use a different infrastructure for tracking S-EPT pages.

Anyway just my 2cents for your reference.

---

## [70] Yan Zhao — 2025-09-29
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

> +/*
> + * The TDX spec treats the registers like an array, as they are ordered
The rdx doesn't work for tdh_mem_page_demote(), which copies the pamt pages
array starting from r12.

Is there a way to make this more generic?

> +/*
> + * Treat struct the registers like an array that starts at RDX, per
When the 1st alloc_page() succeeds but the 2nd alloc_page() fails, the 1st page
must be freed before returning an error. 

> +		pa_array[i] = page_to_phys(page);
> +	}

---

## [71] Kiryl Shutsemau — 2025-09-29
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Sun, Sep 28, 2025 at 09:34:14AM +0800, Yan Zhao wrote:
> On Sat, Sep 27, 2025 at 03:00:31AM +0800, Edgecombe, Rick P wrote:
> > On Fri, 2025-09-26 at 09:11 -0700, Dave Hansen wrote:

It can work: allocate 2M a time for PAMT and piecemeal it to TDX module
as needed. But it means if 2M allocation is failed, TDX is not functional.

Maybe just use a dedicated kmem_cache for PAMT allocations. Although, I
am not sure if there's a way to specify to kmem_cache what pages to ask
from page allocator.

---

## [72] Xiaoyao Li — 2025-09-29
*Subject: Re: [PATCH v3 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

On 9/19/2025 8:50 AM, Huang, Kai wrote:
>>   static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
>> -				      u16 pamt_entry_size)

While we are at it, how about just moving the definition of 
pamt_entry_size[] from construct_tdmrs() to here?

---

## [73] Huang, Kai — 2025-09-29
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Sun, 2025-09-28 at 22:56 +0000, Huang, Kai wrote:
> On Fri, 2025-09-26 at 23:47 +0000, Edgecombe, Rick P wrote:
> > On Mon, 2025-09-22 at 11:20 +0000, Huang, Kai wrote:

After second thought, please ignore the [*], since I am not sure whether
allocating DPAMT pages for hugepage upfront is a good idea.  I suppose
hugepage and 4K pages can convert to each other at runtime, so perhaps
it's better to handle DPAMT pages when KVM actually maps the leaf TDX
private page.

So seems it's inevitable we need to manage a pool for the leaf TDX private
pages -- for hugepage support at least, since w/o hugepage we may avoid
this pool (e.g., theoretically, we could do tdx_pamt_get() after
kvm_mmu_faultin_pfn() where fault->pfn is ready).

Given you said "We want this to not have to be totally redone for huge
pages.", I can see why you want to use a single pool for both page table
and the leaf TDX private pages.

But maybe another strategy is we could use simplest way for the initial
DPAMT support w/o huge page support first, and leave this to the hugepage
support series.  I don't know.  Just my 2cents.

---

## [74] Dave Hansen — 2025-09-29
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On 9/29/25 04:17, Kiryl Shutsemau wrote:
>> Do you have any suggestions for a better approach?
>>

That seems a bit obtuse rather than just respecting normal lock ordering
rules. No?

---

## [75] Edgecombe, Rick P — 2025-09-29
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Mon, 2025-09-29 at 09:22 -0700, Dave Hansen wrote:
> On 9/29/25 04:17, Kiryl Shutsemau wrote:
> > > Do you have any suggestions for a better approach?

I guess the TDX module can get away with doing them in whatever random order
because they are try-locks. Perhaps we could take them in PFN order? If need be
the TDX module could do the same.

> > It can work: allocate 2M a time for PAMT and piecemeal it to TDX module
> > as needed. But it means if 2M allocation is failed, TDX is not functional.

It might serve a purpose of proving that scalability is possible. I was thinking
if we had line of sight to improving it we could go with the "simple" solution
and wait until there is a problem. Is it reasonable?

But locking issues and state duplication between the TDX module and kernel are a
recurring pattern. The similar KVM MMU issue was probably the most contentious
design issue we had in the TDX base enabling together with the TD configuration
API. To me DPAMT is just more proof that this is not a rare conflict, but a
fundamental problem. If we do need to find a way to improve the DPAMT
scalability, I want to say we should actually think about the generic case and
try to solve that. But that needs much more thought...

---

## [76] Edgecombe, Rick P — 2025-09-29
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Mon, 2025-09-29 at 15:56 +0800, Yan Zhao wrote:
> > +/*
> > + * The TDX spec treats the registers like an array, as they are ordered

Sure we could just pass rdx/r12 as an arg. But I'd think to leave it to the
huage pages patches to add that tweak.

> 
> > +/*

Oops, yes. It needs a proper free path here. Thanks.

> 
> > +		pa_array[i] = page_to_phys(page);

---

## [77] Edgecombe, Rick P — 2025-09-29
*Subject: Re: [PATCH v3 05/16] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Tue, 2025-09-23 at 15:45 +0800, Binbin Wu wrote:
> > +/*
> > + * Allocate PAMT reference counters for all physical memory.

Vmalloc() should handle it?

---

## [78] Edgecombe, Rick P — 2025-09-29
*Subject: Re: [PATCH v3 03/16] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

On Mon, 2025-09-29 at 19:44 +0800, Xiaoyao Li wrote:
> On 9/19/2025 8:50 AM, Huang, Kai wrote:
> > >    static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,

Oh yea, that is better.

---

## [79] Dave Hansen — 2025-09-29
*Subject: Re: [PATCH v3 05/16] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On 9/29/25 10:41, Edgecombe, Rick P wrote:
> On Tue, 2025-09-23 at 15:45 +0800, Binbin Wu wrote:
>>> +/*

vmalloc() will, for instance, round up to 2 pages if you ask for 4097
bytes in 'size'. But that's not the problem. The 'size' calculation
itself is the problem.

You need exactly 2 MiB for every 1 TiB of memory, so let's say we have:

	max_pfn = 1<<28

(where 28 == 40-PAGE_SIZE) then size would be *exactly* 1<<21 (2 MiB).
Right?

But what if:

	max_pfn = (1<<28) + 1

Then size needs to be one more page. Right? But what would the code do?

---

## [80] Yan Zhao — 2025-09-30
*Subject: Re: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Thu, Sep 18, 2025 at 04:22:19PM -0700, Rick Edgecombe wrote:
>  	if (kvm_has_mirrored_tdp(vcpu->kvm)) {
> -		r = kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_external_spt_cache,
Another concern about the topup op is that it entirely hides the page count from
KVM mmu core and assumes the page table level KVM requests is always
PT64_ROOT_MAX_LEVEL.

This assumption will not hold true for split cache for huge pages, where only
a single level is needed and memory for sp, sp->spt, and sp->external_spt does
not need to be allocated from the split cache. [1].

[1] https://lore.kernel.org/all/20250807094604.4762-1-yan.y.zhao@intel.com/

---

## [81] Edgecombe, Rick P — 2025-09-30
*Subject: Re: [PATCH v3 05/16] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Mon, 2025-09-29 at 11:08 -0700, Dave Hansen wrote:
> On 9/29/25 10:41, Edgecombe, Rick P wrote:
> > On Tue, 2025-09-23 at 15:45 +0800, Binbin Wu wrote:

Doh, right. There is an additional issue. A later patch tweaks it to be:
+	size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+	size = round_up(size, PAGE_SIZE);

Perhaps an attempt to fix up the issue by Kirill? It should be fixed like Binbin
suggests, maybe:
+	size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);

Thanks, and sorry for not giving the comment the proper attention the first time
around.

---

## [82] Yan Zhao — 2025-09-30
*Subject: Re: [PATCH v3 13/16] KVM: TDX: Handle PAMT allocation in fault path*

On Thu, Sep 18, 2025 at 04:22:21PM -0700, Rick Edgecombe wrote:
> @@ -862,6 +863,9 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
>  		tdx->vp.tdvpr_page = 0;
tdx_vcpu_free() may be invoked even if the vcpu ioctl KVM_TDX_INIT_VCPU was
never called.

> @@ -2966,6 +2999,8 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
>  	int ret, i;
So, need to move this list init to tdx_vcpu_create().

>  	page = tdx_alloc_page();
>  	if (!page)

---

## [83] Xiaoyao Li — 2025-09-30
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 9/19/2025 7:22 AM, Rick Edgecombe wrote:

...

> +/* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
> +int tdx_pamt_get(struct page *page)

It's not what I expect the refcount to work (maybe I miss something 
seriously?)

My understanding/expectation is that, when refcount is not zero it needs 
to increment the refcount instead of simply return. And ...

> +			goto out_free;
> +

...

when refcount > 1, decrease it.
when refcount is 1, decrease it and remove the PAMT page pair.

> +			return;
> +

---

## [84] Dave Hansen — 2025-09-30
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 9/18/25 16:22, Rick Edgecombe wrote:
...
> +/*
> + * The TDX spec treats the registers like an array, as they are ordered

There are a lot of ways to to all of this jazz to alias an array over
the top of a bunch of named structure fields. My worry about this
approach is that it intentionally tries to hide the underlying type from
the compiler.

It could be done with a bunch of union/struct voodoo like 'struct page':

struct tdx_module_args {
	u64 rcx;
	union {
		struct {
			u64 rdx;
			u64 r8;
			u64 r9;
			...
		};
		u64 array[FOO];
	};
}

Or a separate structure:

struct tdx_module_array_args {
	u64 rcx;
	u64 array[FOO];
};

So that you could do something simpler:

u64 *dpamt_args_array_ptr(struct tdx_module_args *args)
{
	return ((struct tdx_module_array_args *)args)->array;
}

Along with one of these somewhere:

BUILD_BUG_ON(sizeof(struct tdx_module_array_args) !=
	     sizeof(struct tdx_module_array));

I personally find the offsetof() tricks to be harder to follow than
either of those.

> +static int alloc_pamt_array(u64 *pa_array)
> +{

One nit: this reset is unnecessary in the error cases here where the
array never gets handed to the TDX module. Right?

> +		/*
> +		 * It might have come from 'prealloc', but this is an error

This uses 'sizeof(*args_array)'.

> +	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
> +}

While this one is sizeof(u64).

Could we make it consistent, please?


> +/* Serializes adding/removing PAMT memory */
> +static DEFINE_SPINLOCK(pamt_lock);

I'm feeling like the states here are under-commented.

	1. PAMT already allocated
	2. 'pamt_pa_array' consumed, bump the refcount
	3. TDH_PHYMEM_PAMT_ADD failed

#1 and #3 need to free the allocation.

Could we add comments to that effect, please?

> +	}

This might get easier to read if the pr_err() gets dumped in
tdh_phymem_pamt_add() instead.

> +	return ret;
> +out_free:

It feels like there's some magic in terms of how the entire contents of
pamt_pa_array[] get zeroed so that this ends up being safe.

Could that get commented, please?

> +/* Allocate a page and make sure it is backed by PAMT memory */

This comment is giving the "what" but is weak on the "why". Could we add
this?

	This ensures that the page can be used as TDX private
	memory and obtain TDX protections.

> +struct page *tdx_alloc_page(void)
> +{

Also:

	After this, the page is can no longer be protected by TDX.

> +void tdx_free_page(struct page *page)
> +{

---

## [85] Edgecombe, Rick P — 2025-09-30
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Tue, 2025-09-30 at 08:25 -0700, Dave Hansen wrote:
> On 9/18/25 16:22, Rick Edgecombe wrote:
> ...

I was feeling good about it until I had to add that FORTIFY_SOUCE fix and almost
scrapped it. I should have taken the compiler issues as a bigger hint.

> 
> It could be done with a bunch of union/struct voodoo like 'struct page':

I think the union would be better, otherwise it gets a bit hidden how tdxcall.S
is plucking things out of the args struct.

Yan was asking if we could reuse some of this for the demote SEAMCALL which also
does an args array, but at a different offset. It would be nice if this thing
supported creating array's at different parts of the args struct without
defining a bunch of extra structs? Would something a little more dynamic still
be clear enough?

struct tdx_module_array_args {
	union {
		struct tdx_module_args args;
		u64 args_array[sizeof(struct tdx_module_args) / sizeof(u64)];
	};
};


#define MAX_TDX_ARG_SIZE(reg) (sizeof(struct tdx_module_args) - \
			       offsetof(struct tdx_module_args, reg))

static u64 *dpamt_args_array_ptr(struct tdx_module_array_args *args)
{
	WARN_ON_ONCE(tdx_dpamt_entry_pages() > MAX_TDX_ARG_SIZE(rdx));

	return &args->args_array[offsetof(struct tdx_module_args, rdx)];
}

Then for huge pages there could be a:
static u64 *demote_args_array_ptr(struct tdx_module_array_args *args)
{
	WARN_ON_ONCE(tdx_dpamt_entry_pages() > MAX_TDX_ARG_SIZE(r12));

	return &args->args_array[offsetof(struct tdx_module_args, r12)];
}

> 
> Along with one of these somewhere:

If it was ever passed to the TDX module I'd think we should reset it, but not
all of the error cases do. Maybe add a comment like:

/*
 * Reset pages unconditionally to cover cases
 * where they were passed to the TDX module.
 */

> 
> > +		/*

Oops, yes. Should standardize on sizeof(*args_array) I think.

> 
> 

Ok, maybe it even deserves a little design paragraph comment. I'll have to work
a bit longer on that.

> 
> > +	}


Good point.

/*
 * pamt_pa_array is populated up to tdx_dpamt_entry_pages() by the TDX
 * module with pages, or remains zero inited. free_pamt_array() can
 * handle either case. Just pass it unconditionally.
 */

> 
> > +/* Allocate a page and make sure it is backed by PAMT memory */

It sounds like the comment was trying to be imperative. Is it not needed here?
Alternatively:

        Return a page that can be be used as TDX private memory
        and obtain TDX protections.

> 
> > +struct page *tdx_alloc_page(void)

---

## [86] Dave Hansen — 2025-09-30
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 9/30/25 07:03, Xiaoyao Li wrote:
> My understanding/expectation is that, when refcount is not zero it needs
> to increment the refcount instead of simply return. And ...

That's a good point.

This doesn't properly handle the case where the PAMT exists and the
refcount is already incremented.

We need something like this with a fast path for a non-zero refcount
that doesn't take the lock:

	// When the refcount is nonzero, the PAMT is allocated already.
	// Bump it up and return.
	if (atomic_inc_not_zero(pamt_refcount))
		return;

	// No PAMT is present. Take the lock to ensure there is no race
	// to allocate it and proceed to allocate one.

	... existing code here

Without this, all of the atomic manipulation is within the lock and the
atomic_t could just be a plain int.

---

## [87] Edgecombe, Rick P — 2025-09-30
*Subject: Re: [PATCH v3 07/16] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Tue, 2025-09-30 at 22:03 +0800, Xiaoyao Li wrote:
> > +/* Bump PAMT refcount for the given page and allocate PAMT memory if needed
> > */

Argh, yes. The following optimization patch should change this to behave
normally with respect the refcount. I should have tested it with the
optimization patches removed, I'll do that next time.

> 
> > +			goto out_free;

---

## [88] Edgecombe, Rick P — 2025-09-30
*Subject: Re: [PATCH v3 11/16] KVM: TDX: Add x86 ops for external spt cache*

On Tue, 2025-09-30 at 09:02 +0800, Yan Zhao wrote:
> On Thu, Sep 18, 2025 at 04:22:19PM -0700, Rick Edgecombe wrote:
> >   	if (kvm_has_mirrored_tdp(vcpu->kvm)) {

That's a good point. Core MMU *does* care about the number of times it calls
alloc_external_fault_cache(). It should take a count with respect to that, and
internally TDX code can adjust it up to include DPAMT pages if needed.

> 
> This assumption will not hold true for split cache for huge pages, where only

---

## [89] Edgecombe, Rick P — 2025-09-30
*Subject: Re: [PATCH v3 13/16] KVM: TDX: Handle PAMT allocation in fault path*

On Tue, 2025-09-30 at 09:09 +0800, Yan Zhao wrote:
> On Thu, Sep 18, 2025 at 04:22:21PM -0700, Rick Edgecombe wrote:
> > @@ -862,6 +863,9 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)

Oh, nice catch. Thanks!

---

## [90] Edgecombe, Rick P — 2025-09-30
*Subject: Re: [PATCH v3 00/16] TDX: Enable Dynamic PAMT*

On Mon, 2025-09-29 at 09:58 -0700, Rick Edgecombe wrote:
> It might serve a purpose of proving that scalability is possible. I was thinking
> if we had line of sight to improving it we could go with the "simple" solution

We discussed this offline and the conclusion was to just keep a global
reader/writer lock as the backpocket solution. So DPAMT seamcalls take the
global reader, and if they get a BUSY code, they take the global lock as write
and retry. Similar to what KVM does on a per-VM scope, but globally and reduced
by the refcount.

But until there is a measured issue, just keep the simpler global exclusive lock
with the refcount to start. So unless anyone new chimes in, we can call this
closed.

---

## [91] Edgecombe, Rick P — 2025-10-01
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

On Wed, 2025-09-24 at 16:57 +0800, Binbin Wu wrote:
> > This will results in @start pointing to the first refcount and @end
> > pointing to the second, IIUC.

Thanks both for the analysis. I lazily created a test program to check some edge
cases and found the original and this version were both buggy. Clearly this code
needs to be clearer (as actually Dave pointed out in v2 and I failed to
address). Example (synthetic failure):

start_pfn = 0x80000
end_pfn =   0x80001

Original code: start = 0xff76ba4f9e034000
               end   = 0xff76ba4f9e034000

Above fix:     start = 0xff76ba4f9e034000
               end   = 0xff76ba4f9e034000

Part of the problem is that tdx_find_pamt_refcount() expects the hpa passed in
to be PMD aligned. The other callers of tdx_find_pamt_refcount() also make sure
that the PA passed in is 2MB aligned before calling, and compute this starting
with a PFN. So to try to make it easier to read and be correct what do you think
about the below:

static atomic_t *tdx_find_pamt_refcount(unsigned long pfn) {
    unsigned long hpa = ALIGN_DOWN(pfn, PMD_SIZE);

    return &pamt_refcounts[hpa / PMD_SIZE];
}

/*
 * 'start_pfn' is inclusive and 'end_pfn' is exclusive. Compute the 
 * page range to be inclusive of the start and end refcount
 * addresses and at least a page in size. The teardown logic needs
 * to handle potentially overlapping refcounts mappings resulting
 * from this.
 */
start = (unsigned long)tdx_find_pamt_refcount(start_pfn);
end   = (unsigned long)tdx_find_pamt_refcount(end_pfn - 1);
start = ALIGN_DOWN(start, PAGE_SIZE);
end   = ALIGN_DOWN(end, PAGE_SIZE) + PAGE_SIZE;

---

## [92] Huang, Kai — 2025-10-01
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

On Wed, 2025-10-01 at 00:32 +0000, Edgecombe, Rick P wrote:
> On Wed, 2025-09-24 at 16:57 +0800, Binbin Wu wrote:
> > > This will results in @start pointing to the first refcount and @end

Oh I think the problem of the "Above fix" is it fails when @start and @end
are the same and both are already page aligned.

> 
> Part of the problem is that tdx_find_pamt_refcount() expects the hpa passed in

Shouldn't it be:

	hpa = ALIGN_DOWN(PFN_PHYS(pfn), PMD_SIZE));
?
> 
>     return &pamt_refcounts[hpa / PMD_SIZE];

I think 'end_pfn' is exclusive is a little bit confusing?  It sounds like
the physical range from PFN_PHYS(end_pfn - 1) to PFN_PHYS(end_pfn) is also
exclusive, but it is actually not?  To me it's more like only the physical
address PFN_PHYS(end_pfn) is exclusive.

> Compute the 
>  * page range to be inclusive of the start and end refcount

This looks fine to me.  I mean the result should be correct, but the
'end_pfn - 1' (due to 'end_pfn' is exclusive) is a bit confusing to me as
said above, but maybe it's only me, so feel free to ignore.

Or, as said above, I think the problem of the "Above fix" is when
calculating the @end we didn't consider the case where it equals to @start
and is already page aligned.  Does below work (assuming
tdx_find_pamt_refcount() still takes 'hpa')?

    start = (unsigned long)tdx_find_pamt_refcount(PFN_PHYS(start_pfn));
    end   = (unsigned long)tdx_find_pamt_refcount(PFN_PHYS(end_pfn) - 1));
    start = PAGE_ALIGN_DOWN(start);
    end   = PAGE_ALIGN_DOWN(end) + PAGE_SIZE;

Anyway, don't have strong opinion here, so up to you.

---

## [93] Edgecombe, Rick P — 2025-10-01
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

On Wed, 2025-10-01 at 10:40 +0000, Huang, Kai wrote:
> On Wed, 2025-10-01 at 00:32 +0000, Edgecombe, Rick P wrote:
> > 

Err, yes.

> > 
> >     return &pamt_refcounts[hpa / PMD_SIZE];

It's trying to say that end_pfn is an exclusive range value, so the range in
question does not actually include end_pfn. That is how the calling code looked
to me, but please check.

Maybe I can clarify that start_pfn and end_pfn are a range? It seems redundant.

>   It sounds like
> the physical range from PFN_PHYS(end_pfn - 1) to PFN_PHYS(end_pfn) is also

Not sure what you mean. For clarity, when describing a range sometimes the start
or end include that value, and sometimes they don't. So exclusive here means
that the end_pfn is not included in the range. As in we don't need a refcount
allocation for end_pfn.

>   To me it's more like only the physical
> address PFN_PHYS(end_pfn) is exclusive.

Sorry, I'm not following the confusion. Maybe we can have a quick chat when you
come online.

> 
> Or, as said above, I think the problem of the "Above fix" is when

The refcounts are actually per page/pfn not per PA. So I think introducing the
concept of a refcount for a PA, especially as part of the interfaces is adding
confusion. The math happens to work out, but it's a layer of indirection.

The other problem this collides with is that tdx_find_pamt_refcount() callers
all have to convert PFN to PA. This should be fixed.


I guess we are really doing two separate calculations. First calculate the range
of refcounts we need, and then calculate the range of vmalloc space we need. How
about this, is it clearer to you? It is very specific about what/why we actually
are doing, but at the expense of minimizing operations. In this slow path, I
think clarity is the priority.

static int alloc_pamt_refcount(unsigned long start_pfn, unsigned long end_pfn)
{
	unsigned long refcount_first, refcount_last;
	unsigned long mapping_start, mapping_end;

	/*
	 * 'start_pfn' is inclusive and 'end_pfn' is exclusive. Find the
	 * range of refcounts the pfn range will need.
	 */
	refcount_first = (unsigned long)tdx_find_pamt_refcount(start_pfn);
	refcount_last   = (unsigned long)tdx_find_pamt_refcount(end_pfn - 1);

	/*
	 * Calculate the page aligned range that includes the refcounts. The
	 * teardown logic needs to handle potentially overlapping refcount
	 * mappings resulting from the alignments.
	 */
	mapping_start = round_down(refcount_first, PAGE_SIZE);
	mapping_end   = round_up(refcount_last + sizeof(*pamt_refcounts),
PAGE_SIZE);


	return apply_to_page_range(&init_mm, mapping_start, mapping_end -
mapping_start,
				   pamt_refcount_populate, NULL);
}

> 
> Anyway, don't have strong opinion here, so up to you.

---

## [94] Edgecombe, Rick P — 2025-10-01
*Subject: Re: [PATCH v3 12/16] x86/virt/tdx: Add helpers to allow for
 pre-allocating pages*

On Fri, 2025-09-19 at 10:55 +0100, Kiryl Shutsemau wrote:
> > installed under a spin lock. This means that the operations around
> > installing PAMT pages for them will not be able to allocate pages.

Uhh, hmm. I'd hope to keep it as simple as possible, but I suppose that this is
a regression from the current upstream level of safety. I'll add it.

---

## [95] Huang, Kai — 2025-10-01
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

On Wed, 2025-10-01 at 19:00 +0000, Edgecombe, Rick P wrote:
> I guess we are really doing two separate calculations. First calculate the range
> of refcounts we need, and then calculate the range of vmalloc space we need. How

Yeah it's better and clearer.  LGTM.  Thanks.

---

## [96] Edgecombe, Rick P — 2025-10-06
*Subject: Re: [PATCH v3 04/16] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Fri, 2025-09-26 at 14:57 -0700, Edgecombe, Rick P wrote:
> Yes, it's not symmetrical. It was probably added manually. I don't see
> why we actually need the the part that makes it unsymmetrical

Ah, actually the check is needed. The reason is that if the TDX module doesn't
support DPAMT, then a new kernel with these changes could fail to read the
metadata and, in turn, fail the call. This means the TDX module initialization
would fail, when really we want to just continue without Dynamic PAMT. I guess
as we move off of the base support, the validity of the metadata struct members
will start to depend on if the relevant feature is actually supported.

For this single conditional field it's hard to justify more then the simple
tdx_supports_dynamic_pamt() check, but if this keeps coming up we might want to
look at re-arranging the metadata such that we don't end up with scattered
checks all over.

I'll add a comment for now, and we can keep an eye on it:

	/*
	 * Don't fail here if tdx_supports_dynamic_pamt() isn't supported. The
	 * TDX code can fallback to normal PAMT if it's not supported.
	 */
	if (!ret && tdx_supports_dynamic_pamt(&tdx_sysinfo) &&
	    !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;

So the resulting logic is, if the module has the 'features0' bit set, then read
the field. If reading the field fails somehow, then fail the TDX module
initialization. We could also continue under normal PAMT, but then we would have
to make sure DPAMT wasn't tried if we allowed the initialization to continue
here. Let's keep it simpler.

---

## [97] Huang, Kai — 2025-10-15
*Subject: Re: [PATCH v3 06/16] x86/virt/tdx: Improve PAMT refcounters
 allocation for sparse memory*

> +/*
> + * Allocate PAMT reference counters for the given PFN range.

This alloc_pamt_refcount() needs to check whether DPAMT is supported
before calling apply_to_page_range().  Otherwise when DPAMT is not
supported the apply_to_page_range() panics due to the @pamt_refcounts is
never initialized to a proper value.

> @@ -288,10 +377,19 @@ static int build_tdx_memlist(struct list_head *tmb_list)
>  		ret = add_tdx_memblock(tmb_list, start_pfn, end_pfn, nid);

---
